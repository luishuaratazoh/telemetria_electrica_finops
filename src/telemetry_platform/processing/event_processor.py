"""Procesadores de eventos, estados de interruptor, metadatos de oscilografia y ajustes."""
from __future__ import annotations

import json
from typing import Sequence

from psycopg2.extras import Json

from telemetry_platform.common.config import get_settings
from telemetry_platform.storage.object_store.file_repository import FileRepository
from telemetry_platform.storage.postgres import assets_repository, events_repository
from telemetry_platform.storage.postgres.assets_repository import AssetCache

from .quality import BreakerMsg, EventMsg, OscillographyMsg, ProcessResult, SettingsMsg, parse_messages


class EventProcessor:
    table = "events.electrical_events"

    def __init__(self, cache: AssetCache) -> None:
        self.cache = cache

    def process(self, raws: Sequence[dict]) -> ProcessResult:
        valid, rejected = parse_messages(EventMsg, raws)
        rows = []
        for m in valid:
            did = self.cache.device_id(m.asset_id)
            if did is None:
                rejected.append((m.model_dump(mode="json"), f"desconocido: {m.asset_id}"))
                continue
            rows.append((did, m.event_type, m.event_time, m.severity, Json(m.details)))
        inserted = events_repository.insert_events(rows)
        return ProcessResult(inserted, len(rows) - inserted, rejected)


class BreakerProcessor:
    table = "events.breaker_states"

    def __init__(self, cache: AssetCache) -> None:
        self.cache = cache

    def process(self, raws: Sequence[dict]) -> ProcessResult:
        valid, rejected = parse_messages(BreakerMsg, raws)
        rows = []
        for m in valid:
            did = self.cache.device_id(m.asset_id)
            if did is None:
                rejected.append((m.model_dump(mode="json"), f"desconocido: {m.asset_id}"))
                continue
            rows.append((did, m.event_time, m.position, m.operations))
        inserted = events_repository.insert_breaker_states(rows)
        return ProcessResult(inserted, len(rows) - inserted, rejected)


class OscillographyProcessor:
    table = "files.device_files"

    def __init__(self, cache: AssetCache) -> None:
        self.cache = cache

    def process(self, raws: Sequence[dict]) -> ProcessResult:
        valid, rejected = parse_messages(OscillographyMsg, raws)
        inserted = 0
        for m in valid:
            did = self.cache.device_id(m.asset_id)
            if did is None:
                rejected.append((m.model_dump(mode="json"), f"desconocido: {m.asset_id}"))
                continue
            for f in m.files:
                assets_repository.insert_device_file(
                    did, f.file_type, f.bucket, f.object_key, f.checksum or "", f.size_bytes or 0, m.event_time
                )
                inserted += 1
        return ProcessResult(inserted, 0, rejected)


class SettingsProcessor:
    """Guarda el JSON original de ajustes en MinIO (archivo) y la version en PostgreSQL (metadatos)."""

    table = "protection.settings_versions"

    def __init__(self, cache: AssetCache, file_repo: FileRepository | None) -> None:
        self.cache = cache
        self.file_repo = file_repo

    def process(self, raws: Sequence[dict]) -> ProcessResult:
        valid, rejected = parse_messages(SettingsMsg, raws)
        inserted = 0
        bucket = get_settings().bucket_settings
        for m in valid:
            did = self.cache.device_id(m.asset_id)
            if did is None:
                rejected.append((m.model_dump(mode="json"), f"desconocido: {m.asset_id}"))
                continue
            file_id = None
            if self.file_repo is not None:
                key = f"{m.substation_id}/{m.asset_id}/v{m.version:05d}.json"
                data = json.dumps(m.model_dump(mode="json"), indent=1).encode()
                meta = self.file_repo.store_bytes(bucket, key, data, "settings_json", "application/json")
                file_id = assets_repository.insert_device_file(
                    did, meta["file_type"], bucket, key, meta["checksum"], meta["size_bytes"], m.effective_time
                )
            if assets_repository.insert_settings_version(
                did, m.version, m.setting_group, m.effective_time, file_id, m.params
            ):
                inserted += 1
        return ProcessResult(inserted, len(valid) - inserted, rejected)
