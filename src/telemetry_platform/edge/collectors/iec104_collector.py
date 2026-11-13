"""Colector IEC 60870-5-104 (fase futura)."""
from __future__ import annotations

from typing import Any, Iterable

from .base import BaseCollector


class Iec104Collector(BaseCollector):
    def poll(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError("Adaptador IEC 60870-5-104 pendiente")
