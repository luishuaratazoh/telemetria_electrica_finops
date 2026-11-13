"""Medicion de uso (base de FinOps): contadores Prometheus + persistencia periodica en finops.usage_metrics.

Metricas: messages_published, bytes_published, messages_suppressed (deadband), messages_consumed,
bytes_consumed, rows_inserted, rows_duplicate, messages_rejected.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from prometheus_client import Counter

from telemetry_platform.common.logging import get_logger

log = get_logger(__name__)

_PROM: dict[str, Counter] = {}
_PROM_LOCK = threading.Lock()


def _prom_counter(metric: str) -> Counter:
    with _PROM_LOCK:
        if metric not in _PROM:
            _PROM[metric] = Counter(f"telemetry_{metric}", f"Uso medido: {metric}", ["component", "label"])
        return _PROM[metric]


class UsageTracker:
    def __init__(self, component: str, persist: bool = True, flush_seconds: float = 30.0) -> None:
        self.component = component
        self.persist = persist
        self.flush_seconds = flush_seconds
        self._acc: dict[tuple[str, str], float] = defaultdict(float)
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()

    def incr(self, metric: str, value: float = 1, label: str = "") -> None:
        _prom_counter(metric).labels(component=self.component, label=label).inc(value)
        if not self.persist:
            return
        with self._lock:
            self._acc[(metric, label)] += value
        if time.monotonic() - self._last_flush >= self.flush_seconds:
            self.flush()

    def flush(self) -> None:
        with self._lock:
            items = list(self._acc.items())
            self._acc.clear()
            self._last_flush = time.monotonic()
        if not items or not self.persist:
            return
        rows = [(self.component, m, lb, v) for (m, lb), v in items]
        try:
            from telemetry_platform.finops import repository

            repository.record_usage(rows)
        except Exception as exc:  # la medicion nunca debe tumbar el pipeline
            log.warning("No se pudo persistir uso FinOps: %s", exc)
            with self._lock:  # reinyectar para el proximo intento
                for (m, lb), v in items:
                    self._acc[(m, lb)] += v
