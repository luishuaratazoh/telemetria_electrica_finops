from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from telemetry_platform.api.schemas.telemetry import HistoryPointOut, LatestMeasurementOut
from telemetry_platform.storage.postgres import telemetry_repository

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/latest", response_model=list[LatestMeasurementOut])
def latest(asset_id: str | None = None, substation: str | None = None, limit: int = Query(100, le=5000)):
    return telemetry_repository.latest(asset_id, substation, limit)


@router.get("/history", response_model=list[HistoryPointOut])
def history(
    asset_id: str,
    variable: str = "active_power",
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(1000, le=20000),
):
    end = end or datetime.now(timezone.utc)
    start = start or end - timedelta(hours=1)
    return telemetry_repository.history(asset_id, variable, start, end, limit)
