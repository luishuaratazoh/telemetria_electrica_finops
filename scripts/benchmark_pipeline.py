"""Benchmark de capacidad (ingesta directa a PostgreSQL y/o publicacion a Redpanda) + costo asociado.

  python scripts/benchmark_pipeline.py --rows 200000            # inserta filas sinteticas en BD
  python scripts/benchmark_pipeline.py --messages 200000 --kafka   # publica a telemetry.bench (no al topic real)
Requiere haber ejecutado seed_devices.py.  Las filas de benchmark usan event_time historico (dia -400..) para
no mezclarse con datos reales; se pueden borrar con --cleanup.
"""
import argparse
import random
import time
from datetime import datetime, timedelta, timezone

import _bootstrap  # noqa: F401

from telemetry_platform.common.config import get_settings
from telemetry_platform.messaging.producer import KafkaPublisher
from telemetry_platform.storage.postgres import telemetry_repository
from telemetry_platform.storage.postgres.assets_repository import AssetCache
from telemetry_platform.storage.postgres.connection import close_pool, get_connection

BENCH_START = datetime(2000, 1, 1, tzinfo=timezone.utc)  # fuera de la retencion; evita mezclar con datos reales


def bench_db(n: int, batch: int) -> None:
    cache = AssetCache()
    devices = list(cache._devices.values())
    if not devices:
        raise SystemExit("master.devices vacio: ejecuta scripts/seed_devices.py")
    rng = random.Random(1)
    t0, inserted, i = time.perf_counter(), 0, 0
    while i < n:
        rows = [
            (BENCH_START + timedelta(seconds=i + k), rng.choice(devices), rng.randint(1, 6), rng.uniform(0, 100), "GOOD")
            for k in range(min(batch, n - i))
        ]
        inserted += telemetry_repository.insert_measurements(rows)
        i += len(rows)
    dt = time.perf_counter() - t0
    print(f"[DB] {inserted:,} filas en {dt:.2f}s -> {inserted / dt:,.0f} filas/s")
    print(f"     A ese ritmo, 4000 reles x 5 variables cada 5s (20,000 filas/s sin deadband) "
          f"{'SE SOSTIENE' if inserted / dt >= 20000 else 'NO se sostiene en un solo consumidor'}")


def bench_kafka(n: int) -> None:
    pub = KafkaPublisher(get_settings().kafka_bootstrap_servers, "bench")
    msg = {"asset_id": "SEL_751_00001", "substation_id": "SE_001", "device_type": "protection_relay",
           "measurement_type": "active_power", "value": 1234.5678, "unit": "kW",
           "event_time": "2026-11-11T15:00:00.000Z", "quality": "GOOD", "source": "simulator"}
    t0, size = time.perf_counter(), 0
    for _ in range(n):
        size += pub.publish("telemetry.bench", msg, msg["asset_id"])
    pub.flush(30)
    dt = time.perf_counter() - t0
    print(f"[Kafka] {n:,} mensajes en {dt:.2f}s -> {n / dt:,.0f} msg/s, {size / n:.0f} B/msg, {size / 1e6:.1f} MB")
    gib_month_at_rate = (n / dt) * 86400 * 30 * (size / n) / 1024**3
    print(f"        Trafico mensual si se sostuviera ese ritmo: {gib_month_at_rate:,.0f} GiB (ver costo en finops_report)")


def cleanup() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM telemetry.measurements WHERE event_time < '2001-01-01'")
        print(f"Filas de benchmark eliminadas: {cur.rowcount:,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=0)
    ap.add_argument("--messages", type=int, default=0)
    ap.add_argument("--kafka", action="store_true")
    ap.add_argument("--batch", type=int, default=5000)
    ap.add_argument("--cleanup", action="store_true")
    a = ap.parse_args()
    if a.rows:
        bench_db(a.rows, a.batch)
    if a.kafka and a.messages:
        bench_kafka(a.messages)
    if a.cleanup:
        cleanup()
    close_pool()
