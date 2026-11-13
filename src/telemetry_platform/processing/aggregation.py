"""Agregaciones: en memoria con Polars y en SQL (TimescaleDB time_bucket)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

import polars as pl

from telemetry_platform.storage.postgres import telemetry_repository


def rows_to_frame(rows: Sequence[tuple], columns: Sequence[str]) -> pl.DataFrame:
    """Convierte filas psycopg2 a DataFrame; los datetimes se pasan a UTC naive (Polars los maneja sin zonas raras)."""
    clean = [
        tuple(v.astimezone(timezone.utc).replace(tzinfo=None) if isinstance(v, datetime) else v for v in r) for r in rows
    ]
    return pl.DataFrame(clean, schema=list(columns), orient="row")


def aggregate_frame(df: pl.DataFrame, every: str = "1h") -> pl.DataFrame:
    """Espera columnas event_time, device_id, variable_id, value."""
    return (
        df.sort("event_time")
        .group_by_dynamic("event_time", every=every, group_by=["device_id", "variable_id"])
        .agg(
            pl.col("value").mean().alias("avg_value"),
            pl.col("value").min().alias("min_value"),
            pl.col("value").max().alias("max_value"),
            pl.len().alias("samples"),
        )
    )


def run_hourly_aggregation(hours_back: int = 2) -> int:
    """Agrega las ultimas N horas completas (idempotente)."""
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours_back)
    return telemetry_repository.aggregate_hourly(start, end + timedelta(hours=1))
