"""Registro oscilografico simulado en formato COMTRADE ASCII (.cfg + .dat), 6 canales analogicos."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

FREQ = 60.0
SAMPLES_PER_CYCLE = 16
CYCLES = 10
FAULT_START_CYCLE = 3
CHANNELS = ["IA", "IB", "IC", "VA", "VB", "VC"]


def _ts(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%d/%m/%Y,%H:%M:%S.%f")


def generate_comtrade(
    station: str, device: str, now: datetime, nominal_current: float, fault_current: float, nominal_kv: float,
    rng: random.Random,
) -> tuple[str, str]:
    """Devuelve (contenido .cfg, contenido .dat)."""
    n = SAMPLES_PER_CYCLE * CYCLES
    rate = int(FREQ * SAMPLES_PER_CYCLE)
    faulted_phase = rng.randrange(3)
    scale_i, scale_v = 10.0, 1.0  # cuentas por A / V (primario simplificado)

    cfg = [
        f"{station},{device},1999",
        f"{len(CHANNELS)},{len(CHANNELS)}A,0D",
    ]
    for k, ch in enumerate(CHANNELS, start=1):
        unit = "A" if ch.startswith("I") else "V"
        phase = ch[-1]
        cfg.append(f"{k},{ch},{phase},,{unit},{1 / (scale_i if unit == 'A' else scale_v)},0,0,-32767,32767,1,1,P")
    start = now - timedelta(seconds=FAULT_START_CYCLE / FREQ)
    cfg += [f"{int(FREQ)}", "1", f"{rate},{n}", _ts(start), _ts(now), "ASCII", "1"]

    rows = []
    i_nom_peak = nominal_current * math.sqrt(2)
    i_flt_peak = fault_current * math.sqrt(2)
    v_peak = nominal_kv * 1000 / math.sqrt(3) * math.sqrt(2)
    for s in range(n):
        t = s / rate
        cycle = s // SAMPLES_PER_CYCLE
        vals = []
        for ph in range(3):
            ang = 2 * math.pi * FREQ * t - ph * 2 * math.pi / 3
            in_fault = cycle >= FAULT_START_CYCLE and ph == faulted_phase
            amp = i_flt_peak if in_fault else i_nom_peak
            vals.append(amp * math.sin(ang - (0.9 if in_fault else 0.3)) + rng.gauss(0, 0.5))
        for ph in range(3):
            ang = 2 * math.pi * FREQ * t - ph * 2 * math.pi / 3
            sag = 0.75 if (cycle >= FAULT_START_CYCLE and ph == faulted_phase) else 1.0
            vals.append(v_peak * sag * math.sin(ang) + rng.gauss(0, 5))
        counts = [int(max(min(v * (scale_i if k < 3 else scale_v), 32767), -32767)) for k, v in enumerate(vals)]
        rows.append(f"{s + 1},{int(t * 1e6)}," + ",".join(str(c) for c in counts))
    return "\n".join(cfg) + "\n", "\n".join(rows) + "\n"
