from fastapi import APIRouter, HTTPException, Query

from telemetry_platform.storage.object_store.minio_client import MinioStorage
from telemetry_platform.storage.postgres import assets_repository

router = APIRouter(prefix="/oscillography", tags=["oscillography"])


@router.get("")
def list_oscillography(asset_id: str | None = None, limit: int = Query(100, le=1000)):
    files = assets_repository.list_files(None, asset_id, limit * 2)
    return [f for f in files if f["file_type"].startswith("comtrade")][:limit]


@router.get("/{file_id}/url")
def download_url(file_id: int):
    """URL temporal (15 min) para descargar el archivo desde MinIO."""
    match = next((f for f in assets_repository.list_files(None, None, 5000) if f["id"] == file_id), None)
    if not match:
        raise HTTPException(404, "archivo no encontrado")
    return {"url": MinioStorage().presigned_url(match["bucket"], match["object_key"])}
