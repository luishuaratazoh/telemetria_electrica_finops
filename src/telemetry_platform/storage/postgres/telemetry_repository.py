"""Persistencia de mediciones y perfiles de carga."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from psycopg2.extras import RealDictCursor, execute_values

from .connection import get_connection

_INSERT_MEASUREMENTS = """
    INSERT INTO telemetry.measurements (event_time, device_id, variable_id, value, quality)
    VALUES %s
    ON CONFLICT (device_id, variable_id, event_time) DO NOTHING
    RETURNING 1
"""

_INSERT_PROFILES = """
    INSERT INTO metering.load_profiles (time, meter_id, active_energy, demand)
    VALUES %s
    ON CONFLICT (meter_id, time) DO NOTHING
    RETURNING 1
"""


def insert_measurements(rows: Sequence[tuple]) -> int:
    """rows: (event_time, device_id, variable_id, value, quality). Devuelve filas realmente insertadas."""
    if not rows:
        return 0
    with get_connection() as conn, conn.cursor() as cur:
        res = execute_values(cur, _INSERT_MEASUREMENTS, rows, page_size=5000, fetch=True)
        return len(res)


def insert_load_profiles(rows: Sequence[tuple]) -> int:
    """rows: (time, meter_id, active_energy, demand)."""
    if not rows:
        return 0
    with get_connection() as conn, conn.cursor() as cur:
        res = execute_values(cur, _INSERT_PROFILES, rows, page_size=5000, fetch=True)
        return len(res)


def latest(asset_id: str | None = None, substation: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    sql = "SELECT * FROM telemetry.v_latest_measurements WHERE TRUE"
    params: list[Any] = []
    if asset_id:
        sql += " AND asset_id = %s"
        params.append(asset_id)
    if substation:
        sql += " AND substation_code = %s"
        params.append(substation)
    sql += " ORDER BY asset_id, variable LIMIT %s"
    params.append(limit)
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def history(asset_id: str, variable: str, start: datetime, end: datetime, limit: int = 1000) -> list[dict[str, Any]]:
    sql = """
        SELECT m.event_time, m.value, m.quality, v.unit
        FROM telemetry.measurements m
        JOIN master.devices d   ON d.id = m.device_id
        JOIN master.variables v ON v.id = m.variable_id
        WHERE d.asset_id = %s AND v.name = %s AND m.event_time >= %s AND m.event_time < %s
        ORDER BY m.event_time DESC
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (asset_id, variable, start, end, limit))
        return cur.fetchall()


def meter_profiles(asset_id: str, start: datetime, end: datetime, limit: int = 1000) -> list[dict[str, Any]]:
    sql = """
        SELECT p.time, p.active_energy, p.demand
        FROM metering.load_profiles p
        JOIN master.devices d ON d.id = p.meter_id
        WHERE d.asset_id = %s AND p.time >= %s AND p.time < %s
        ORDER BY p.time DESC LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (asset_id, start, end, limit))
        return cur.fetchall()


def aggregate_hourly(start: datetime, end: datetime) -> int:
    """Agregacion horaria en SQL (idempotente). Devuelve filas afectadas."""
    sql = """
        INSERT INTO telemetry.measurements_hourly
            (bucket, device_id, variable_id, avg_value, min_value, max_value, samples)
        SELECT time_bucket('1 hour', event_time), device_id, variable_id,
               AVG(value), MIN(value), MAX(value), COUNT(*)
        FROM telemetry.measurements
        WHERE event_time >= %s AND event_time < %s AND quality <> 'BAD'
        GROUP BY 1, 2, 3
        ON CONFLICT (device_id, variable_id, bucket) DO UPDATE
           SET avg_value = EXCLUDED.avg_value, min_value = EXCLUDED.min_value,
               max_value = EXCLUDED.max_value, samples = EXCLUDED.samples
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (start, end))
        return cur.rowcount
