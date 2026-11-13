"""Modelo de costos (funciones puras, sin I/O): volumen -> recursos cloud equivalentes -> USD/mes.

Las tarifas son ILUSTRATIVAS (tabla finops.cost_rates). Sirven para comparar escenarios y palancas,
no como cotizacion: valida con la calculadora oficial del proveedor antes de decidir.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

GIB = 1024**3
DAYS_PER_MONTH = 30
HOURS_PER_MONTH = 730

DEFAULT_RATES = {
    "messaging_ingest": 0.04,
    "object_storage": 0.02,
    "db_storage": 0.17,
    "db_compute": 0.0413,
    "db_memory": 0.007,
    "compute_pipeline": 0.033,
}

UNITS = {
    "messaging_ingest": "GiB",
    "object_storage": "GiB-month",
    "db_storage": "GiB-month",
    "db_compute": "vCPU-hour",
    "db_memory": "GiB-hour",
    "compute_pipeline": "vCPU-hour",
}


@dataclass(frozen=True)
class Workload:
    messages_per_day: float
    avg_message_bytes: float
    rows_per_day: float
    bytes_per_row: float
    files_per_day: float = 0.0
    avg_file_bytes: float = 0.0


@dataclass(frozen=True)
class Sizing:
    db_vcpus: float
    db_memory_gib: float
    pipeline_vcpus: float


@dataclass(frozen=True)
class CostLine:
    resource: str
    quantity: float
    unit: str
    unit_cost_usd: float
    cost_usd: float


def estimate(
    w: Workload,
    sizing: Sizing,
    rates: dict[str, float] | None = None,
    retention_days: int = 30,
    compress_after_days: int = 2,
    compression_ratio: float = 10.0,
    object_retention_days: int = 90,
    consumer_groups: int = 1,
) -> list[CostLine]:
    r = {**DEFAULT_RATES, **(rates or {})}

    monthly_bytes = w.messages_per_day * DAYS_PER_MONTH * w.avg_message_bytes
    messaging_gib = monthly_bytes * (1 + consumer_groups) / GIB  # 1 publicacion + N entregas

    raw_days = min(compress_after_days, retention_days)
    compressed_days = max(retention_days - raw_days, 0)
    db_gib = w.rows_per_day * w.bytes_per_row * (raw_days + compressed_days / max(compression_ratio, 1.0)) / GIB

    obj_gib = w.files_per_day * w.avg_file_bytes * object_retention_days / GIB

    quantities = {
        "messaging_ingest": messaging_gib,
        "db_storage": db_gib,
        "object_storage": obj_gib,
        "db_compute": sizing.db_vcpus * HOURS_PER_MONTH,
        "db_memory": sizing.db_memory_gib * HOURS_PER_MONTH,
        "compute_pipeline": sizing.pipeline_vcpus * HOURS_PER_MONTH,
    }
    return [
        CostLine(res, q, UNITS[res], r[res], round(q * r[res], 4)) for res, q in quantities.items()
    ]


def total(lines: list[CostLine]) -> float:
    return round(sum(ln.cost_usd for ln in lines), 2)


def full_fleet_workload(
    fleet: dict,
    deadband_saving: float,
    avg_message_bytes: float,
    bytes_per_row: float,
    avg_file_bytes: float,
) -> Workload:
    """Proyecta el volumen diario de la flota completa aplicando el ahorro de deadband medido."""
    saving = min(max(deadband_saving, 0.0), 0.99)
    relay_msgs = fleet["relays"] * fleet["relay_variables"] * 86400 / fleet["relay_sample_seconds"] * (1 - saving)
    meter_msgs = fleet["meters"] * (1440 / fleet["meter_profile_minutes"])
    files = fleet["relays"] * fleet["trips_per_relay_per_month"] / DAYS_PER_MONTH
    return Workload(
        messages_per_day=relay_msgs + meter_msgs,
        avg_message_bytes=avg_message_bytes,
        rows_per_day=relay_msgs + meter_msgs,
        bytes_per_row=bytes_per_row,
        files_per_day=files,
        avg_file_bytes=avg_file_bytes,
    )


def unit_economics(lines: list[CostLine], w: Workload, devices: int) -> dict[str, float]:
    t = total(lines)
    rows_month = w.rows_per_day * DAYS_PER_MONTH
    return {
        "total_usd_month": t,
        "usd_per_million_rows": round(t / (rows_month / 1e6), 4) if rows_month else 0.0,
        "usd_per_device_month": round(t / devices, 4) if devices else 0.0,
    }


def what_if(
    base_workload: Workload,
    sizing: Sizing,
    fleet: dict,
    deadband_saving: float,
    rates: dict[str, float] | None,
    params: dict,
) -> list[dict]:
    """Palancas de ahorro sobre el escenario de flota completa. Devuelve ahorro USD/mes por palanca."""
    base_total = total(estimate(base_workload, sizing, rates, **params))
    out = []

    def run(name: str, w: Workload | None = None, **override):
        p = {**params, **override}
        t = total(estimate(w or base_workload, sizing, rates, **p))
        out.append({"lever": name, "total_usd_month": t, "saving_usd_month": round(base_total - t, 2)})

    slower = {**fleet, "relay_sample_seconds": fleet["relay_sample_seconds"] * 2}
    w2 = full_fleet_workload(
        slower, deadband_saving, base_workload.avg_message_bytes, base_workload.bytes_per_row, base_workload.avg_file_bytes
    )
    run("Muestreo de reles al doble de periodo", w=w2)
    w3 = full_fleet_workload(
        fleet, min(deadband_saving + 0.10, 0.99), base_workload.avg_message_bytes, base_workload.bytes_per_row,
        base_workload.avg_file_bytes,
    )
    run("Deadband +10 puntos de ahorro", w=w3)
    run("Retencion de telemetria cruda a la mitad", retention_days=max(params["retention_days"] // 2, 1))
    run("Comprimir desde el dia 1", compress_after_days=1)
    run("Retencion de oscilografias 30 dias", object_retention_days=30)
    return sorted(out, key=lambda d: -d["saving_usd_month"])


def with_sizing(s: Sizing, **kw) -> Sizing:
    return replace(s, **kw)
