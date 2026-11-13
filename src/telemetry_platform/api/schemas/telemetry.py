from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LatestMeasurementOut(BaseModel):
    asset_id: str
    substation_code: str
    device_type: str
    variable: str
    unit: str
    value: float
    quality: str
    event_time: datetime
    ingest_time: datetime


class HistoryPointOut(BaseModel):
    event_time: datetime
    value: float
    quality: str
    unit: str
