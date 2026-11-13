"""Deduplicacion por lote con Polars (solo columnas enteras: robusto y rapido)."""
from __future__ import annotations

from typing import Sequence

import polars as pl


def deduplicate_indices(keys: Sequence[tuple[int, int, int]]) -> list[int]:
    """keys: (device_id, variable_id, event_time_epoch_us). Devuelve indices a conservar (el ultimo de cada clave)."""
    if len(keys) < 2:
        return list(range(len(keys)))
    df = pl.DataFrame(
        {
            "i": list(range(len(keys))),
            "a": [k[0] for k in keys],
            "b": [k[1] for k in keys],
            "c": [k[2] for k in keys],
        }
    )
    return df.unique(subset=["a", "b", "c"], keep="last", maintain_order=True)["i"].to_list()
