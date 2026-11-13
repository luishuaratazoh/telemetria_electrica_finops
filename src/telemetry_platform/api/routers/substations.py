from fastapi import APIRouter, Query

from telemetry_platform.api.schemas.devices import DeviceOut, SubstationOut
from telemetry_platform.storage.postgres import assets_repository

router = APIRouter(tags=["substations"])


@router.get("/substations", response_model=list[SubstationOut])
def substations():
    return assets_repository.list_substations()


@router.get("/substations/{code}/devices", response_model=list[DeviceOut])
def substation_devices(
    code: str, device_type: str | None = None, limit: int = Query(100, le=5000), offset: int = 0
):
    return assets_repository.list_devices(code, device_type, limit, offset)
