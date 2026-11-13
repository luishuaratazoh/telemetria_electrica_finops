"""Productor de mensajes. MessagePublisher es la interfaz (futuro: PubSubPublisher)."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from confluent_kafka import KafkaException, Producer

from telemetry_platform.common.logging import get_logger

log = get_logger(__name__)


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":"), default=str).encode("utf-8")


class MessagePublisher(ABC):
    @abstractmethod
    def publish(self, topic: str, message: dict[str, Any], key: str | None = None) -> int:
        """Publica un mensaje y devuelve su tamano en bytes."""

    @abstractmethod
    def flush(self, timeout: float = 10.0) -> None: ...


class NullPublisher(MessagePublisher):
    """Para --dry-run: cuenta bytes pero no envia nada."""

    def publish(self, topic: str, message: dict[str, Any], key: str | None = None) -> int:
        return len(encode(message))

    def flush(self, timeout: float = 10.0) -> None:
        return None


class KafkaPublisher(MessagePublisher):
    def __init__(
        self,
        bootstrap_servers: str,
        client_id: str = "telemetry-edge",
        linger_ms: int = 50,
        batch_num_messages: int = 10000,
        compression: str = "lz4",
    ) -> None:
        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "client.id": client_id,
                "linger.ms": linger_ms,
                "batch.num.messages": batch_num_messages,
                "compression.type": compression,
                "enable.idempotence": True,
                "queue.buffering.max.messages": 500_000,
            }
        )
        self.delivery_errors = 0

    def _on_delivery(self, err, msg) -> None:
        if err is not None:
            self.delivery_errors += 1
            log.error("Entrega fallida en %s: %s", msg.topic(), err)

    def publish(self, topic: str, message: dict[str, Any], key: str | None = None) -> int:
        payload = encode(message)
        k = key.encode("utf-8") if key else None
        try:
            self._producer.produce(topic, value=payload, key=k, on_delivery=self._on_delivery)
        except BufferError:
            self._producer.poll(1.0)  # cola llena: dar tiempo a enviar y reintentar
            try:
                self._producer.produce(topic, value=payload, key=k, on_delivery=self._on_delivery)
            except (BufferError, KafkaException) as exc:
                raise ConnectionError(f"Broker no disponible: {exc}") from exc
        self._producer.poll(0)
        return len(payload)

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout)
