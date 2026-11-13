"""Inserta subestaciones y dispositivos en PostgreSQL.  python scripts/seed_devices.py [--mode functional|load]"""
import argparse

import _bootstrap  # noqa: F401

from telemetry_platform.common.config import get_settings, load_yaml
from telemetry_platform.common.logging import get_logger
from telemetry_platform.simulator.substation_generator import build_topology
from telemetry_platform.storage.postgres import assets_repository
from telemetry_platform.storage.postgres.connection import close_pool, wait_for_db

log = get_logger("seed_devices")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=None, help="functional | load (por defecto SIMULATOR_MODE)")
    args = ap.parse_args()

    cfg = load_yaml("simulator.yaml")
    mode = args.mode or get_settings().simulator_mode
    topo = build_topology(cfg["modes"][mode], cfg["seed"])

    wait_for_db()
    ns = assets_repository.upsert_substations([s.__dict__ for s in topo.substations])
    nd = assets_repository.upsert_devices([d.__dict__ for d in topo.devices])
    log.info("Modo %s: %d subestaciones nuevas, %d dispositivos nuevos (de %d)", mode, ns, nd, len(topo.devices))
    close_pool()


if __name__ == "__main__":
    main()
