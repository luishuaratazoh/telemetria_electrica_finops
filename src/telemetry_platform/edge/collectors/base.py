from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable


class BaseCollector(ABC):
    """Contrato de un colector de campo: entrega lecturas crudas al normalizador."""

    @abstractmethod
    def poll(self) -> Iterable[dict[str, Any]]: ...
