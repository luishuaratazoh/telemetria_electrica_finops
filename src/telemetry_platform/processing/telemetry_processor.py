"""Procesa telemetry.raw: valida, mapea IDs, deduplica e inserta en lote."""
from __future__ import annotations

from typing import Sequence

from telemetry_platform.common.timestamps import epoch_micros
from telemetry_platform.storage.postgres import telemetry_repository
from telemetry_platform.storage.postgres.assets_repository import AssetCache

from .deduplication import deduplicate_indices
from .quality import MeasurementMsg, ProcessResult, parse_messages


class TelemetryProcessor:
    table = "telemetry.measurements"

    def __init__(self, cache: AssetCache) -> None:
        self.cache = cache

    def process(self, raws: Sequence[dict]) -> ProcessResult:
        valid, rejected = parse_messages(MeasurementMsg, raws)
        rows: list[tuple] = []
        keys: list[tuple[int, int, int]] = []
        for m in valid:
            did = self.cache.device_id(m.asset_id)
            vid = self.cache.variable_id(m.measurement_type)
            if did is None or vid is None:
                rejected.append((m.model_dump(mode="json"), f"desconocido: {m.asset_id}/{m.measurement_type}"))
                continue
            rows.append((m.event_time, did, vid, m.value, m.quality))
            keys.append((did, vid, epoch_micros(m.event_time)))

        keep = deduplicate_indices(keys)
        unique_rows = [rows[i] for i in keep]
        inserted = telemetry_repository.insert_measurements(unique_rows)
        return ProcessResult(inserted=inserted, duplicates=len(rows) - inserted, rejected=rejected)
