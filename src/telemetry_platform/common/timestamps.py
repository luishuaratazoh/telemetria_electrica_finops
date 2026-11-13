from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    """ISO 8601 en UTC con sufijo Z (ej. 2026-11-11T15:00:00.123Z)."""
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def epoch_micros(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000)
