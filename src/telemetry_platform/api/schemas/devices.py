from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SubstationOut(BaseModel):
    code: str
    name: str
    region: str | None
    latitude: float | None
    longitude: float | None
    load_profile: str
    devices: int


class DeviceOut(BaseModel):
    asset_id: str
    substation_code: str
    device_type: str
    manufacturer: str | None
    model: str | None
    active: bool


class BreakerStatusOut(BaseModel):
    asset_id: str
    substation_code: str
    position: str
    operations: int
    event_time: datetime


class EventOut(BaseModel):
    id: int
    asset_id: str
    substation_code: str
    event_type: str
    severity: str
    event_time: datetime
    details: dict[str, Any]
