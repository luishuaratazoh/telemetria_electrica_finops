from __future__ import annotations

from datetime import datetime

from telemetry_platform.common.timestamps import to_iso


class BreakerSimulator:
    def __init__(self, asset_id: str, substation: str) -> None:
        self.asset_id = asset_id
        self.substation = substation
        self.is_open = False
        self.operations = 0

    def trip(self) -> None:
        if not self.is_open:
            self.is_open = True
            self.operations += 1

    def close(self) -> None:
        if self.is_open:
            self.is_open = False
            self.operations += 1

    def state(self, now: datetime) -> dict:
        return {
            "breaker": self.asset_id,
            "substation": self.substation,
            "ts": to_iso(now),
            "position": "OPEN" if self.is_open else "CLOSED",
            "operations": self.operations,
        }
