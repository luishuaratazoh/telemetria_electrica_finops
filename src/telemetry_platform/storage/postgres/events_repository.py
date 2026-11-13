"""Persistencia de eventos electricos y estados de interruptores."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from psycopg2.extras import RealDictCursor, execute_values

from .connection import get_connection


def insert_events(rows: Sequence[tuple]) -> int:
    """rows: (device_id, event_type, event_time, severity, Json(details))."""
    if not rows:
        return 0
    sql = """
        INSERT INTO events.electrical_events (device_id, event_type, event_time, severity, details)
        VALUES %s ON CONFLICT (device_id, event_type, event_time) DO NOTHING RETURNING 1
    """
    with get_connection() as conn, conn.cursor() as cur:
        return len(execute_values(cur, sql, rows, page_size=2000, fetch=True))


def insert_breaker_states(rows: Sequence[tuple]) -> int:
    """rows: (device_id, event_time, position, operations)."""
    if not rows:
        return 0
    sql = """
        INSERT INTO events.breaker_states (device_id, event_time, position, operations)
        VALUES %s ON CONFLICT (device_id, event_time) DO NOTHING RETURNING 1
    """
    with get_connection() as conn, conn.cursor() as cur:
        return len(execute_values(cur, sql, rows, page_size=2000, fetch=True))


def list_events(
    substation: str | None = None,
    asset_id: str | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql = """
        SELECT e.id, d.asset_id, s.code AS substation_code, e.event_type, e.severity, e.event_time, e.details
        FROM events.electrical_events e
        JOIN master.devices d     ON d.id = e.device_id
        JOIN master.substations s ON s.id = d.substation_id
        WHERE TRUE
    """
    params: list[Any] = []
    for cond, val in (
        ("s.code = %s", substation),
        ("d.asset_id = %s", asset_id),
        ("e.event_type = %s", event_type),
        ("e.event_time >= %s", since),
    ):
        if val is not None:
            sql += f" AND {cond}"
            params.append(val)
    sql += " ORDER BY e.event_time DESC LIMIT %s"
    params.append(limit)
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def breaker_status(substation: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    sql = """
        SELECT DISTINCT ON (b.device_id)
               d.asset_id, s.code AS substation_code, b.position, b.operations, b.event_time
        FROM events.breaker_states b
        JOIN master.devices d     ON d.id = b.device_id
        JOIN master.substations s ON s.id = d.substation_id
        WHERE (%s::text IS NULL OR s.code = %s)
        ORDER BY b.device_id, b.event_time DESC
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (substation, substation, limit))
        return cur.fetchall()
