"""Indicadores electricos basicos."""
from __future__ import annotations

import math


def apparent_power(p_kw: float, q_kvar: float) -> float:
    return math.hypot(p_kw, q_kvar)


def power_factor(p_kw: float, q_kvar: float) -> float:
    s = apparent_power(p_kw, q_kvar)
    return p_kw / s if s else 1.0


def voltage_deviation_pct(v_kv: float, nominal_kv: float = 10.0) -> float:
    return (v_kv - nominal_kv) / nominal_kv * 100.0


def load_factor(avg_kw: float, peak_kw: float) -> float:
    return avg_kw / peak_kw if peak_kw else 0.0
