"""Contratos de mensajes (pydantic) y chequeos de calidad de datos en BD."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Sequence, Type, TypeVar

from pydantic import BaseModel, Field, ValidationError

from telemetry_platform.storage.postgres.connection import get_connection


class MeasurementMsg(BaseModel):
    asset_id: str
    substation_id: str
    device_type: str
    measurement_type: str
    value: float = Field(allow_inf_nan=False)
    unit: str
    event_time: datetime
    quality: Literal["GOOD", "SUSPECT", "BAD"] = "GOOD"
    source: str = "unknown"


class ProfileMsg(BaseModel):
    asset_id: str
    substation_id: str
    event_time: datetime
    active_energy: float = Field(allow_inf_nan=False, ge=0)
    demand: float = Field(allow_inf_nan=False, ge=0)


class BreakerMsg(BaseModel):
    asset_id: str
    substation_id: str
    event_time: datetime
    position: Literal["OPEN", "CLOSED"]
    operations: int = 0


class EventMsg(BaseModel):
    asset_id: str
    substation_id: str
    event_type: str
    severity: str = "INFO"
    event_time: datetime
    details: dict[str, Any] = {}


class FileInfo(BaseModel):
    file_type: str
    bucket: str
    object_key: str
    checksum: str | None = None
    size_bytes: int | None = None


class OscillographyMsg(BaseModel):
    asset_id: str
    substation_id: str
    event_time: datetime
    peak_current_a: float | None = None
    files: list[FileInfo]


class SettingsMsg(BaseModel):
    asset_id: str
    substation_id: str
    version: int
    setting_group: int = 1
    effective_time: datetime
    params: dict[str, Any] = {}


@dataclass
class ProcessResult:
    inserted: int = 0
    duplicates: int = 0
    rejected: list[tuple[dict, str]] = field(default_factory=list)


M = TypeVar("M", bound=BaseModel)


def parse_messages(model: Type[M], raws: Sequence[dict]) -> tuple[list[M], list[tuple[dict, str]]]:
    valid: list[M] = []
    rejected: list[tuple[dict, str]] = []
    for raw in raws:
        try:
            valid.append(model.model_validate(raw))
        except ValidationError as exc:
            rejected.append((raw, "schema: " + exc.errors()[0]["msg"]))
    return valid, rejected


# ----------------------------------------------------------------- chequeos en BD (usados por Airflow)
def run_quality_checks(window_minutes: int = 60) -> dict[str, Any]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE quality = 'BAD'),
                   COUNT(*) FILTER (WHERE quality = 'SUSPECT'),
                   MAX(ingest_time),
                   COALESCE(EXTRACT(EPOCH FROM AVG(ingest_time - event_time)), 0)
            FROM telemetry.measurements
            WHERE ingest_time > now() - make_interval(mins => %s)
            """,
            (window_minutes,),
        )
        total, bad, suspect, last_ingest, avg_lag = cur.fetchone()
        cur.execute(
            """
            SELECT COUNT(*) FROM master.devices d
            WHERE d.device_type = 'protection_relay' AND NOT EXISTS (
                SELECT 1 FROM telemetry.measurements m
                WHERE m.device_id = d.id AND m.event_time > now() - make_interval(mins => %s))
            """,
            (window_minutes,),
        )
        silent_relays = cur.fetchone()[0]
    return {
        "window_minutes": window_minutes,
        "rows": total,
        "bad_ratio": (bad / total) if total else 0.0,
        "suspect_ratio": (suspect / total) if total else 0.0,
        "last_ingest": last_ingest,
        "avg_ingest_lag_seconds": float(avg_lag),
        "silent_relays": silent_relays,
    }
