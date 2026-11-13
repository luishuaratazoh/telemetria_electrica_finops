from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from telemetry_platform.api.schemas.devices import BreakerStatusOut, DeviceOut
from telemetry_platform.storage.postgres import assets_repository, events_repository, telemetry_repository

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=list[DeviceOut])
def devices(device_type: str | None = None, limit: int = Query(100, le=5000), offset: int = 0):
    return assets_repository.list_devices(None, device_type, limit, offset)


@router.get("/breakers/status", response_model=list[BreakerStatusOut])
def breakers_status(substation: str | None = None, limit: int = Query(200, le=5000)):
    return events_repository.breaker_status(substation, limit)


@router.get("/meters/profiles")
def meter_profiles(
    asset_id: str, hours: int = Query(24, le=720), limit: int = Query(1000, le=10000)
):
    end = datetime.now(timezone.utc)
    return telemetry_repository.meter_profiles(asset_id, end - timedelta(hours=hours), end, limit)


@router.get("/devices/settings/history")
def settings_history(asset_id: str | None = None, limit: int = Query(100, le=1000)):
    return assets_repository.settings_history(asset_id, limit)
