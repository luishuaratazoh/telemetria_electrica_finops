"""Deteccion simple de anomalias (z-score movil) sobre una serie."""
from __future__ import annotations

import polars as pl


def zscore_anomalies(df: pl.DataFrame, column: str = "value", window: int = 30, threshold: float = 3.0) -> pl.DataFrame:
    """Devuelve las filas cuyo |z| respecto a la ventana movil previa supera el umbral."""
    return (
        df.with_columns(
            pl.col(column).rolling_mean(window_size=window, min_samples=window // 2).alias("_mean"),
            pl.col(column).rolling_std(window_size=window, min_samples=window // 2).alias("_std"),
        )
        .with_columns(((pl.col(column) - pl.col("_mean")) / pl.col("_std")).alias("zscore"))
        .filter(pl.col("zscore").abs() > threshold)
        .drop(["_mean", "_std"])
    )
