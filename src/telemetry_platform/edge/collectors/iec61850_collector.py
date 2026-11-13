"""Colector IEC 61850 MMS/GOOSE (fase futura; posible integracion con libiec61850)."""
from __future__ import annotations

from typing import Any, Iterable

from .base import BaseCollector


class Iec61850Collector(BaseCollector):
    def poll(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError("Adaptador IEC 61850 pendiente")
