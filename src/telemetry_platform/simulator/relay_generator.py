"""Rele de proteccion virtual (tipo SEL-751). Modelo trifasico simplificado, NO un modelo electromagnetico."""
from __future__ import annotations

import math
import random
from datetime import datetime

from telemetry_platform.common.timestamps import to_iso

from .breaker_generator import BreakerSimulator

SQRT3 = math.sqrt(3)


class RelaySimulator:
    def __init__(self, asset_id: str, substation: str, nominal_kv: float, nominal_current: float, rng: random.Random,
                 breaker: BreakerSimulator | None = None) -> None:
        self.asset_id = asset_id
        self.substation = substation
        self.nominal_kv = nominal_kv
        self.nominal_current = nominal_current
        self.rng = rng
        self.breaker = breaker
        self.pending_fault_sample = False
        self.fault_peak_current = 0.0
        self.in_fault = False

    def start_fault(self) -> float:
        """Marca una falla: la proxima muestra captura la corriente de falla."""
        self.pending_fault_sample = True
        self.in_fault = True
        self.fault_peak_current = self.nominal_current * self.rng.uniform(5.0, 8.0)
        return self.fault_peak_current

    def clear_fault(self) -> None:
        self.in_fault = False

    def generate_measurement(self, now: datetime, load_factor: float) -> dict:
        g = self.rng.gauss
        pf = min(max(0.95 + g(0, 0.005), 0.85), 1.0)
        v = self.nominal_kv * (1 + g(0, 0.004))
        f = 60.0 + g(0, 0.01)

        if self.pending_fault_sample:
            i = self.fault_peak_current
            v *= self.rng.uniform(0.7, 0.9)
            self.pending_fault_sample = False
        elif self.breaker is not None and self.breaker.is_open:
            i = abs(g(0, 0.2))  # interruptor abierto: sin carga
            v = self.nominal_kv * (1 + g(0, 0.004))
        else:
            i = self.nominal_current * load_factor * (1 + g(0, 0.02))

        p = SQRT3 * v * i * pf                      # kW  (kV * A)
        q = p * math.tan(math.acos(pf))             # kvar
        return {
            "relay": self.asset_id,
            "substation": self.substation,
            "ts": to_iso(now),
            "voltage_kv": v,
            "current_a": i,
            "active_power_kw": p,
            "reactive_power_kvar": q,
            "frequency_hz": f,
        }
