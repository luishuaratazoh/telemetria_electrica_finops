"""Fallas simuladas: alarma de sobrecorriente -> disparo -> apertura -> recierre."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime

from telemetry_platform.common.timestamps import to_iso

from .breaker_generator import BreakerSimulator
from .relay_generator import RelaySimulator


@dataclass
class TripRecord:
    relay: RelaySimulator
    peak_current: float
    time: datetime


@dataclass
class _ActiveFault:
    relay: RelaySimulator
    ticks_left: int


class EventGenerator:
    def __init__(self, relays: dict[str, RelaySimulator], breakers: dict[str, BreakerSimulator],
                 rng: random.Random, fault_probability: float, reclose_ticks: int) -> None:
        self.relays = relays
        self.breakers = breakers
        self.rng = rng
        self.fault_probability = fault_probability
        self.reclose_ticks = reclose_ticks
        self._ids = list(relays)
        self._active: list[_ActiveFault] = []

    @staticmethod
    def _event(relay: RelaySimulator, etype: str, severity: str, now: datetime, details: dict) -> dict:
        return {
            "device": relay.asset_id,
            "substation": relay.substation,
            "type": etype,
            "severity": severity,
            "ts": to_iso(now),
            "details": details,
        }

    def tick(self, now: datetime) -> tuple[list[dict], list[dict], list[TripRecord]]:
        """Devuelve (eventos, cambios de estado de interruptor, disparos con oscilografia)."""
        events: list[dict] = []
        breaker_changes: list[dict] = []
        trips: list[TripRecord] = []

        # recierres
        still: list[_ActiveFault] = []
        for f in self._active:
            f.ticks_left -= 1
            if f.ticks_left <= 0:
                f.relay.clear_fault()
                brk = f.relay.breaker
                if brk is not None:
                    brk.close()
                    breaker_changes.append(brk.state(now))
                events.append(self._event(f.relay, "reclose", "INFO", now, {"breaker": brk.asset_id if brk else None}))
            else:
                still.append(f)
        self._active = still

        # nueva falla
        if self._ids and self.rng.random() < self.fault_probability:
            relay = self.relays[self.rng.choice(self._ids)]
            if not relay.in_fault:
                peak = relay.start_fault()
                events.append(self._event(relay, "overcurrent_alarm", "WARNING", now,
                                          {"peak_current_a": round(peak, 1), "element": "51"}))
                trip_details = {"peak_current_a": round(peak, 1), "element": "50", "breaker": None}
                brk = relay.breaker
                if brk is not None:
                    brk.trip()
                    breaker_changes.append(brk.state(now))
                    trip_details["breaker"] = brk.asset_id
                events.append(self._event(relay, "trip", "CRITICAL", now, trip_details))
                trips.append(TripRecord(relay, peak, now))
                self._active.append(_ActiveFault(relay, self.reclose_ticks))
        return events, breaker_changes, trips
