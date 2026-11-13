"""Procesa meters.profiles -> metering.load_profiles."""
from __future__ import annotations

from typing import Sequence

from telemetry_platform.storage.postgres import telemetry_repository
from telemetry_platform.storage.postgres.assets_repository import AssetCache

from .quality import ProcessResult, ProfileMsg, parse_messages


class MeterProcessor:
    table = "metering.load_profiles"

    def __init__(self, cache: AssetCache) -> None:
        self.cache = cache

    def process(self, raws: Sequence[dict]) -> ProcessResult:
        valid, rejected = parse_messages(ProfileMsg, raws)
        rows = []
        for m in valid:
            did = self.cache.device_id(m.asset_id)
            if did is None:
                rejected.append((m.model_dump(mode="json"), f"medidor desconocido: {m.asset_id}"))
                continue
            rows.append((m.event_time, did, m.active_energy, m.demand))
        inserted = telemetry_repository.insert_load_profiles(rows)
        return ProcessResult(inserted=inserted, duplicates=len(rows) - inserted, rejected=rejected)
