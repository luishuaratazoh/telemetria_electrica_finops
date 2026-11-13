"""Aplica politicas de retencion/compresion (palancas FinOps de almacenamiento) en TimescaleDB."""
from __future__ import annotations

from telemetry_platform.common.logging import get_logger
from telemetry_platform.storage.postgres.connection import get_connection

log = get_logger(__name__)


def apply_policies(retention_days: int, compress_after_days: int) -> None:
    if compress_after_days >= retention_days:
        raise ValueError("compress_after_days debe ser menor que retention_days")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT remove_retention_policy('telemetry.measurements', if_exists => TRUE)")
        cur.execute("SELECT remove_compression_policy('telemetry.measurements', if_exists => TRUE)")
        cur.execute(
            "SELECT add_compression_policy('telemetry.measurements', make_interval(days => %s))", (compress_after_days,)
        )
        cur.execute(
            "SELECT add_retention_policy('telemetry.measurements', make_interval(days => %s))", (retention_days,)
        )
    log.info("Politicas aplicadas: comprimir tras %s dias, retener %s dias", compress_after_days, retention_days)
