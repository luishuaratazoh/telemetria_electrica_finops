"""Medidor inteligente virtual: perfil de carga (demanda y energia del intervalo)."""
from __future__ import annotations

import random
from datetime import datetime

from telemetry_platform.common.timestamps import to_iso


class MeterSimulator:
    def __init__(self, asset_id: str, substation: str, base_kw: float, rng: random.Random) -> None:
        self.asset_id = asset_id
        self.substation = substation
        self.base_kw = base_kw
        self.rng = rng

    def generate_profile(self, now: datetime, load_factor: float, interval_minutes: float) -> dict:
        kw = max(self.base_kw * load_factor * (1 + self.rng.gauss(0, 0.08)), 0.0)
        return {
            "meter": self.asset_id,
            "substation": self.substation,
            "ts": to_iso(now),
            "kw": round(kw, 3),
            "kwh": round(kw * interval_minutes / 60.0, 4),
        }
