"""Perfiles de carga: curva horaria y factor de carga por subestacion."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import polars as pl

from telemetry_platform.processing.aggregation import rows_to_frame
from telemetry_platform.storage.postgres.connection import get_connection


def hourly_curve(frame: pl.DataFrame) -> pl.DataFrame:
    """frame: columnas time, demand. Devuelve demanda media/maxima por hora del dia."""
    return (
        frame.with_columns(pl.col("time").dt.hour().alias("hour"))
        .group_by("hour")
        .agg(pl.col("demand").mean().alias("avg_kw"), pl.col("demand").max().alias("peak_kw"))
        .sort("hour")
    )


def compute_daily_summary(day: date) -> int:
    """Calcula y guarda pico/promedio/factor de carga por subestacion para un dia (idempotente)."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    sql = """
        WITH per_ts AS (
            SELECT d.substation_id, p.time, SUM(p.demand) AS kw
            FROM metering.load_profiles p JOIN master.devices d ON d.id = p.meter_id
            WHERE p.time >= %s AND p.time < %s
            GROUP BY d.substation_id, p.time)
        INSERT INTO metering.daily_load_summary (day, substation_id, peak_kw, avg_kw, load_factor)
        SELECT %s, substation_id, MAX(kw), AVG(kw), AVG(kw) / NULLIF(MAX(kw), 0)
        FROM per_ts GROUP BY substation_id
        ON CONFLICT (day, substation_id) DO UPDATE
            SET peak_kw = EXCLUDED.peak_kw, avg_kw = EXCLUDED.avg_kw, load_factor = EXCLUDED.load_factor
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (start, end, day))
        return cur.rowcount


def substation_curve(substation_code: str, day: date) -> pl.DataFrame:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    sql = """
        SELECT p.time, p.demand FROM metering.load_profiles p
        JOIN master.devices d ON d.id = p.meter_id JOIN master.substations s ON s.id = d.substation_id
        WHERE s.code = %s AND p.time >= %s AND p.time < %s
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (substation_code, start, start + timedelta(days=1)))
        rows = cur.fetchall()
    if not rows:
        return pl.DataFrame({"hour": [], "avg_kw": [], "peak_kw": []})
    return hourly_curve(rows_to_frame(rows, ["time", "demand"]))
