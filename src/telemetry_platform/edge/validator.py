"""Calidad de la medicion: GOOD / SUSPECT / BAD."""
from __future__ import annotations

import math

from telemetry_platform.common.constants import (
    HARD_RANGES,
    NORMAL_RANGES,
    QUALITY_BAD,
    QUALITY_GOOD,
    QUALITY_SUSPECT,
)


def assess_quality(measurement_type: str, value: float) -> str:
    if value is None or isinstance(value, bool) or math.isnan(value) or math.isinf(value):
        return QUALITY_BAD
    lo, hi = HARD_RANGES.get(measurement_type, (-math.inf, math.inf))
    if not lo <= value <= hi:
        return QUALITY_BAD
    nlo, nhi = NORMAL_RANGES.get(measurement_type, (-math.inf, math.inf))
    if not nlo <= value <= nhi:
        return QUALITY_SUSPECT
    return QUALITY_GOOD
