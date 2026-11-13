"""Inventario (subestaciones/equipos), cache de IDs, metadatos de archivos y ajustes."""
from __future__ import annotations

import time
from typing import Any, Sequence

from psycopg2.extras import Json, RealDictCursor, execute_values

from .connection import get_connection


def upsert_substations(subs: Sequence[dict[str, Any]]) -> int:
    rows = [(s["code"], s["name"], s["region"], s["latitude"], s["longitude"], s["load_profile"]) for s in subs]
    sql = """
        INSERT INTO master.substations (code, name, region, latitude, longitude, load_profile)
        VALUES %s ON CONFLICT (code) DO NOTHING RETURNING 1
    """
    with get_connection() as conn, conn.cursor() as cur:
        return len(execute_values(cur, sql, rows, fetch=True))


def upsert_devices(devices: Sequence[dict[str, Any]]) -> int:
    rows = [
        (d["asset_id"], d["substation_code"], d["device_type"], d["manufacturer"], d["model"]) for d in devices
    ]
    sql = """
        INSERT INTO master.devices (asset_id, substation_id, device_type, manufacturer, model)
        SELECT v.asset_id, s.id, v.device_type, v.manufacturer, v.model
        FROM (VALUES %s) AS v(asset_id, substation_code, device_type, manufacturer, model)
        JOIN master.substations s ON s.code = v.substation_code
        ON CONFLICT (asset_id) DO NOTHING
        RETURNING 1
    """
    inserted = 0
    with get_connection() as conn, conn.cursor() as cur:
        for i in range(0, len(rows), 5000):
            inserted += len(execute_values(cur, sql, rows[i : i + 5000], page_size=5000, fetch=True))
    return inserted


def load_device_map() -> dict[str, int]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT asset_id, id FROM master.devices")
        return {a: i for a, i in cur.fetchall()}


def load_variable_map() -> dict[str, int]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, id FROM master.variables")
        return {n: i for n, i in cur.fetchall()}


class AssetCache:
    """Mapas asset_id->device_id y variable->id. Refresca (con limite de frecuencia) ante un desconocido."""

    def __init__(self, min_refresh_seconds: float = 5.0) -> None:
        self._min_refresh = min_refresh_seconds
        self._devices: dict[str, int] = {}
        self._variables: dict[str, int] = {}
        self._last_refresh = 0.0
        self.refresh()

    def refresh(self) -> None:
        self._devices = load_device_map()
        self._variables = load_variable_map()
        self._last_refresh = time.monotonic()

    def device_id(self, asset_id: str) -> int | None:
        did = self._devices.get(asset_id)
        if did is None and time.monotonic() - self._last_refresh > self._min_refresh:
            self.refresh()
            did = self._devices.get(asset_id)
        return did

    def variable_id(self, name: str) -> int | None:
        return self._variables.get(name)


def list_substations() -> list[dict[str, Any]]:
    sql = """
        SELECT s.code, s.name, s.region, s.latitude, s.longitude, s.load_profile,
               COUNT(d.id) AS devices
        FROM master.substations s LEFT JOIN master.devices d ON d.substation_id = s.id
        GROUP BY s.id ORDER BY s.code
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return cur.fetchall()


def list_devices(
    substation: str | None = None, device_type: str | None = None, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    sql = """
        SELECT d.asset_id, s.code AS substation_code, d.device_type, d.manufacturer, d.model, d.active
        FROM master.devices d JOIN master.substations s ON s.id = d.substation_id
        WHERE (%s::text IS NULL OR s.code = %s) AND (%s::text IS NULL OR d.device_type = %s)
        ORDER BY d.asset_id LIMIT %s OFFSET %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (substation, substation, device_type, device_type, limit, offset))
        return cur.fetchall()


def insert_device_file(
    device_id: int, file_type: str, bucket: str, object_key: str, checksum: str, size_bytes: int, event_time=None
) -> int:
    sql = """
        INSERT INTO files.device_files (device_id, file_type, bucket, object_key, checksum, size_bytes, event_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (bucket, object_key) DO UPDATE SET checksum = EXCLUDED.checksum
        RETURNING id
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (device_id, file_type, bucket, object_key, checksum, size_bytes, event_time))
        return cur.fetchone()[0]


def list_files(file_type: str | None = None, asset_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    sql = """
        SELECT f.id, d.asset_id, f.file_type, f.bucket, f.object_key, f.size_bytes, f.checksum,
               f.event_time, f.created_at
        FROM files.device_files f JOIN master.devices d ON d.id = f.device_id
        WHERE (%s::text IS NULL OR f.file_type = %s) AND (%s::text IS NULL OR d.asset_id = %s)
        ORDER BY f.created_at DESC LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (file_type, file_type, asset_id, asset_id, limit))
        return cur.fetchall()


def insert_settings_version(
    device_id: int, version: int, setting_group: int, effective_time, file_id: int | None, params: dict
) -> bool:
    sql = """
        INSERT INTO protection.settings_versions (device_id, version, setting_group, effective_time, file_id, params)
        VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (device_id, version) DO NOTHING
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (device_id, version, setting_group, effective_time, file_id, Json(params)))
        return cur.rowcount == 1


def settings_history(asset_id: str, limit: int = 100) -> list[dict[str, Any]]:
    sql = """
        SELECT d.asset_id, sv.version, sv.setting_group, sv.effective_time, sv.file_id, sv.params
        FROM protection.settings_versions sv JOIN master.devices d ON d.id = sv.device_id
        WHERE (%s::text IS NULL OR d.asset_id = %s)
        ORDER BY sv.effective_time DESC LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (asset_id, asset_id, limit))
        return cur.fetchall()
