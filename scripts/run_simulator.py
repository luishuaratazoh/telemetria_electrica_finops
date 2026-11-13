"""Simulador + gateway edge -> Redpanda (+ MinIO para oscilografias).

  python scripts/run_simulator.py                         # modo del .env (functional)
  python scripts/run_simulator.py --mode load --ticks 20  # flota completa, 20 ticks
  python scripts/run_simulator.py --dry-run --ticks 3     # sin broker ni MinIO
"""
import argparse
import signal
import threading

import _bootstrap  # noqa: F401
from prometheus_client import start_http_server

from telemetry_platform.common.config import get_settings, load_yaml
from telemetry_platform.common.logging import get_logger
from telemetry_platform.edge.main import EdgeGateway
from telemetry_platform.finops.usage_tracker import UsageTracker
from telemetry_platform.messaging.producer import KafkaPublisher, NullPublisher
from telemetry_platform.simulator.main import Simulator
from telemetry_platform.simulator.substation_generator import build_topology
from telemetry_platform.storage.object_store.file_repository import FileRepository
from telemetry_platform.storage.object_store.minio_client import MinioStorage

log = get_logger("run_simulator")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=None)
    ap.add_argument("--ticks", type=int, default=None, help="numero de ticks (por defecto: infinito)")
    ap.add_argument("--dry-run", action="store_true", help="no publica ni sube archivos")
    ap.add_argument("--no-persist-usage", action="store_true", help="no guardar uso FinOps en PostgreSQL")
    args = ap.parse_args()

    s = get_settings()
    sim_cfg = load_yaml("simulator.yaml")
    acq = load_yaml("acquisition.yaml")
    mode = args.mode or s.simulator_mode
    topo = build_topology(sim_cfg["modes"][mode], sim_cfg["seed"])
    log.info("Modo %s", mode)

    try:
        start_http_server(s.simulator_metrics_port)
    except OSError:
        log.warning("Puerto de metricas %s ocupado; se omite", s.simulator_metrics_port)

    if args.dry_run:
        publisher, file_repo = NullPublisher(), None
    else:
        k = acq["kafka"]
        publisher = KafkaPublisher(
            s.kafka_bootstrap_servers, "telemetry-edge", k["linger_ms"], k["batch_num_messages"], k["compression"]
        )
        file_repo = FileRepository(MinioStorage(), expire_days=s.oscillography_retention_days)

    tracker = UsageTracker("edge", persist=not (args.dry_run or args.no_persist_usage))
    gateway = EdgeGateway(publisher, tracker, file_repo, acq)
    sim = Simulator(topo, gateway, sim_cfg)

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    sim.run(max_ticks=args.ticks, stop_event=stop)
    log.info("Simulador detenido tras %d ticks", sim.tick_no)


if __name__ == "__main__":
    main()
