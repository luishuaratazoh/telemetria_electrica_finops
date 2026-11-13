"""Colector Modbus TCP/RTU (fase futura; requiere `pip install pymodbus`). Por ahora el simulador alimenta el edge."""
from __future__ import annotations

from typing import Any, Iterable

from .base import BaseCollector


class ModbusCollector(BaseCollector):
    def __init__(self, host: str, port: int = 502, unit_id: int = 1) -> None:
        self.host, self.port, self.unit_id = host, port, unit_id

    def poll(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError("Adaptador Modbus pendiente: ver pymodbus.client.ModbusTcpClient")
