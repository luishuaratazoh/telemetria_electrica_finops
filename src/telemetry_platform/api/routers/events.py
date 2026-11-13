from datetime import datetime

from fastapi import APIRouter, Query

from telemetry_platform.api.schemas.devices import EventOut
from telemetry_platform.storage.postgres import events_repository

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
def events(
    substation: str | None = None,
    asset_id: str | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    limit: int = Query(100, le=5000),
):
    return events_repository.list_events(substation, asset_id, event_type, since, limit)


@router.get("/trips", response_model=list[EventOut])
def trips(substation: str | None = None, since: datetime | None = None, limit: int = Query(100, le=5000)):
    return events_repository.list_events(substation, None, "trip", since, limit)
