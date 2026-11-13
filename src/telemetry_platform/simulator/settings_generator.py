"""Versiones de ajustes de proteccion (grupos de ajuste, arranque de sobrecorriente, curva)."""
from __future__ import annotations

import random
from datetime import datetime

from telemetry_platform.common.timestamps import to_iso

CURVES = ["U1", "U2", "U3", "C1", "C2", "C3"]


class SettingsSimulator:
    def __init__(self, relays: dict[str, tuple[str, float]], rng: random.Random) -> None:
        """relays: asset_id -> (substation, nominal_current)."""
        self.rng = rng
        self.relays = relays
        self.versions: dict[str, int] = {}

    def _message(self, asset: str, now: datetime) -> dict:
        sub, nominal = self.relays[asset]
        version = self.versions.get(asset, 0) + 1
        self.versions[asset] = version
        return {
            "device": asset,
            "substation": sub,
            "version": version,
            "setting_group": self.rng.randint(1, 3),
            "effective_time": to_iso(now),
            "params": {
                "pickup_50_a": round(nominal * self.rng.uniform(4.0, 6.0), 1),
                "pickup_51_a": round(nominal * self.rng.uniform(1.2, 1.5), 1),
                "time_dial": round(self.rng.uniform(0.5, 3.0), 2),
                "curve": self.rng.choice(CURVES),
            },
        }

    def initial(self, now: datetime) -> list[dict]:
        return [self._message(a, now) for a in self.relays]

    def maybe_change(self, now: datetime, probability: float) -> list[dict]:
        if self.relays and self.rng.random() < probability:
            return [self._message(self.rng.choice(list(self.relays)), now)]
        return []
