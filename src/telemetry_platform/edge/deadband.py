"""Filtro de banda muerta: no publica si el valor casi no cambio (palanca FinOps de ingestion)."""
from __future__ import annotations

import time


class DeadbandFilter:
    def __init__(self, thresholds_pct: dict[str, float], heartbeat_seconds: float = 60.0, enabled: bool = True) -> None:
        self.thresholds = thresholds_pct
        self.heartbeat = heartbeat_seconds
        self.enabled = enabled
        self._last: dict[tuple[str, str], tuple[float, float]] = {}  # key -> (valor, instante monotonic)

    def should_publish(self, asset_id: str, measurement_type: str, value: float, now: float | None = None) -> bool:
        if not self.enabled or measurement_type not in self.thresholds:
            return True
        now = time.monotonic() if now is None else now
        key = (asset_id, measurement_type)
        last = self._last.get(key)
        if last is not None:
            last_value, last_t = last
            ref = abs(last_value) if abs(last_value) > 1e-9 else 1.0
            change_pct = abs(value - last_value) / ref * 100.0
            if change_pct < self.thresholds[measurement_type] and (now - last_t) < self.heartbeat:
                return False
        self._last[key] = (value, now)
        return True
