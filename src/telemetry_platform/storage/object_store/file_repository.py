"""Subida de archivos con checksum; devuelve los metadatos que se registran en PostgreSQL."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .minio_client import ObjectStorage


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FileRepository:
    def __init__(self, storage: ObjectStorage, expire_days: int | None = None) -> None:
        self.storage = storage
        self.expire_days = expire_days

    def store_bytes(
        self, bucket: str, key: str, data: bytes, file_type: str, content_type: str = "application/octet-stream"
    ) -> dict[str, Any]:
        self.storage.ensure_bucket(bucket, self.expire_days)
        self.storage.upload_bytes(bucket, key, data, content_type)
        return {
            "file_type": file_type,
            "bucket": bucket,
            "object_key": key,
            "checksum": sha256_bytes(data),
            "size_bytes": len(data),
        }

    def store_local_file(self, bucket: str, key: str, path: Path, file_type: str) -> dict[str, Any]:
        return self.store_bytes(bucket, key, path.read_bytes(), file_type)
