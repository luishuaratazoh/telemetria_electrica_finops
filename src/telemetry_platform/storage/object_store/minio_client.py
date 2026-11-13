"""Almacenamiento de objetos. ObjectStorage es la interfaz; MinioStorage la implementacion local.
Para migrar a GCP bastara crear GCSStorage con la misma interfaz."""
from __future__ import annotations

import io
from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path

from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

from telemetry_platform.common.config import get_settings
from telemetry_platform.common.logging import get_logger

log = get_logger(__name__)


class ObjectStorage(ABC):
    @abstractmethod
    def ensure_bucket(self, bucket: str, expire_days: int | None = None) -> None: ...

    @abstractmethod
    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...

    @abstractmethod
    def upload_file(self, bucket: str, key: str, file_path: str | Path) -> None: ...

    @abstractmethod
    def download(self, bucket: str, key: str, destination: str | Path) -> None: ...

    @abstractmethod
    def exists(self, bucket: str, key: str) -> bool: ...

    @abstractmethod
    def list_keys(self, bucket: str, prefix: str = "") -> list[tuple[str, int]]: ...


class MinioStorage(ObjectStorage):
    def __init__(self, client: Minio | None = None) -> None:
        s = get_settings()
        self.client = client or Minio(
            s.minio_endpoint, access_key=s.minio_access_key, secret_key=s.minio_secret_key, secure=s.minio_secure
        )
        self._ready: set[str] = set()

    def ensure_bucket(self, bucket: str, expire_days: int | None = None) -> None:
        if bucket in self._ready:
            return
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
            log.info("Bucket creado: %s", bucket)
        if expire_days:
            # FinOps: expiracion automatica de objetos (equivalente a lifecycle rules de Cloud Storage).
            try:
                cfg = LifecycleConfig(
                    [Rule(ENABLED, rule_filter=Filter(prefix=""), rule_id="expire-old", expiration=Expiration(days=expire_days))]
                )
                self.client.set_bucket_lifecycle(bucket, cfg)
            except Exception as exc:  # no es critico
                log.warning("No se pudo fijar lifecycle en %s: %s", bucket, exc)
        self._ready.add(bucket)

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)

    def upload_file(self, bucket: str, key: str, file_path: str | Path) -> None:
        self.client.fput_object(bucket, key, str(file_path))

    def download(self, bucket: str, key: str, destination: str | Path) -> None:
        self.client.fget_object(bucket, key, str(destination))

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.stat_object(bucket, key)
            return True
        except Exception:
            return False

    def list_keys(self, bucket: str, prefix: str = "") -> list[tuple[str, int]]:
        return [(o.object_name, o.size or 0) for o in self.client.list_objects(bucket, prefix=prefix, recursive=True)]

    def presigned_url(self, bucket: str, key: str, minutes: int = 15) -> str:
        s = get_settings()
        client = self.client
        if s.minio_public_endpoint and s.minio_public_endpoint != s.minio_endpoint:
            # Dentro de Docker el endpoint es "minio:9000", inalcanzable desde el navegador: se firma con el
            # host publico (region fija para no consultar la red).
            client = Minio(
                s.minio_public_endpoint, access_key=s.minio_access_key, secret_key=s.minio_secret_key,
                secure=s.minio_secure, region="us-east-1",
            )
        return client.presigned_get_object(bucket, key, expires=timedelta(minutes=minutes))
