"""Colector de archivos: sube oscilografias (.cfg/.dat) a MinIO y publica sus metadatos."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from telemetry_platform.common.logging import get_logger
from telemetry_platform.messaging.topics import OSCILLOGRAPHY_METADATA
from telemetry_platform.storage.object_store.file_repository import FileRepository

log = get_logger(__name__)

Publish = Callable[[str, dict[str, Any], str | None], None]


class FileCollector:
    def __init__(
        self, watch_dir: Path, file_repo: FileRepository, bucket: str, publish: Publish, delete_after_upload: bool = True
    ) -> None:
        self.watch_dir = watch_dir
        self.file_repo = file_repo
        self.bucket = bucket
        self.publish = publish
        self.delete_after_upload = delete_after_upload

    def scan(self) -> int:
        """Procesa registros completos (existe el .json sidecar). Devuelve cuantos se subieron."""
        if not self.watch_dir.exists():
            return 0
        done = 0
        for meta_path in sorted(self.watch_dir.rglob("*.json")):
            cfg, dat = meta_path.with_suffix(".cfg"), meta_path.with_suffix(".dat")
            if not (cfg.exists() and dat.exists()):
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                day = meta["event_time"][:10].replace("-", "/")
                prefix = f"{meta['substation']}/{meta['asset_id']}/{day}/{meta_path.stem}"
                files = [
                    self.file_repo.store_local_file(self.bucket, f"{prefix}.cfg", cfg, "comtrade_cfg"),
                    self.file_repo.store_local_file(self.bucket, f"{prefix}.dat", dat, "comtrade_dat"),
                ]
                self.publish(
                    OSCILLOGRAPHY_METADATA,
                    {
                        "asset_id": meta["asset_id"],
                        "substation_id": meta["substation"],
                        "event_time": meta["event_time"],
                        "peak_current_a": meta.get("peak_current_a"),
                        "files": files,
                    },
                    meta["asset_id"],
                )
                if self.delete_after_upload:
                    for p in (cfg, dat, meta_path):
                        p.unlink(missing_ok=True)
                done += 1
            except Exception as exc:
                log.warning("No se pudo procesar %s: %s", meta_path.name, exc)
        return done
