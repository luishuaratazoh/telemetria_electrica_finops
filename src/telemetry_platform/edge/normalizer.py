"""Convierte estructuras propias de cada fabricante/dispositivo al esquema comun."""
from __future__ import annotations

from typing import Any

from telemetry_platform.common.constants import DEVICE_METER, DEVICE_RELAY, QUALITY_GOOD, UNITS

SOURCE = "simulator"

_RELAY_FIELDS = {
    "voltage_kv": "voltage",
    "current_a": "current",
    "active_power_kw": "active_power",
    "reactive_power_kvar": "reactive_power",
    "frequency_hz": "frequency",
}


def _measurement(asset: str, substation: str, device_type: str, mtype: str, value: float, ts: str) -> dict[str, Any]:
    return {
        "asset_id": asset,
        "substation_id": substation,
        "device_type": device_type,
        "measurement_type": mtype,
        "value": round(float(value), 4),
        "unit": UNITS[mtype],
        "event_time": ts,
        "quality": QUALITY_GOOD,
        "source": SOURCE,
    }


def normalize_relay(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _measurement(raw["relay"], raw["substation"], DEVICE_RELAY, mtype, raw[field], raw["ts"])
        for field, mtype in _RELAY_FIELDS.items()
        if raw.get(field) is not None
    ]


def normalize_meter(raw: dict[str, Any]) -> dict[str, Any]:
    """Un perfil de carga por medidor/intervalo (topic meters.profiles)."""
    return {
        "asset_id": raw["meter"],
        "substation_id": raw["substation"],
        "device_type": DEVICE_METER,
        "event_time": raw["ts"],
        "active_energy": float(raw["kwh"]),
        "demand": float(raw["kw"]),
        "source": SOURCE,
    }


def normalize_breaker(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": raw["breaker"],
        "substation_id": raw["substation"],
        "event_time": raw["ts"],
        "position": raw["position"],
        "operations": int(raw["operations"]),
        "source": SOURCE,
    }


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": raw["device"],
        "substation_id": raw["substation"],
        "event_type": raw["type"],
        "severity": raw["severity"],
        "event_time": raw["ts"],
        "details": raw.get("details", {}),
        "source": SOURCE,
    }


def normalize_settings(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": raw["device"],
        "substation_id": raw["substation"],
        "version": int(raw["version"]),
        "setting_group": int(raw["setting_group"]),
        "effective_time": raw["effective_time"],
        "params": raw["params"],
        "source": SOURCE,
    }
