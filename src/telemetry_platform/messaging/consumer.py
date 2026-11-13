"""Consumidor por lotes con commit manual (at-least-once; la BD es idempotente via ON CONFLICT)."""
from __future__ import annotations

import threading
import time
from typing import Callable, Sequence

from confluent_kafka import Consumer, KafkaError, Message

from telemetry_platform.common.logging import get_logger

log = get_logger(__name__)


class BatchConsumer:
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topics: Sequence[str],
        batch_size: int = 2000,
        batch_timeout: float = 1.0,
        max_retries: int = 5,
    ) -> None:
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "fetch.min.bytes": 1,
            }
        )
        self._topics = list(topics)
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_retries = max_retries

    def run(
        self,
        handler: Callable[[list[Message]], None],
        stop_event: threading.Event | None = None,
        on_idle: Callable[[], None] | None = None,
    ) -> None:
        stop_event = stop_event or threading.Event()
        self._consumer.subscribe(self._topics)
        log.info("Consumiendo topicos: %s", self._topics)
        try:
            while not stop_event.is_set():
                raw = self._consumer.consume(num_messages=self.batch_size, timeout=self.batch_timeout)
                msgs: list[Message] = []
                for m in raw:
                    if m.error():
                        if m.error().code() != KafkaError._PARTITION_EOF:
                            log.warning("Error de Kafka: %s", m.error())
                        continue
                    msgs.append(m)
                if not msgs:
                    if on_idle:
                        on_idle()
                    continue
                self._handle_with_retry(handler, msgs)
                self._consumer.commit(asynchronous=False)
        finally:
            self._consumer.close()

    def _handle_with_retry(self, handler: Callable[[list[Message]], None], msgs: list[Message]) -> None:
        for attempt in range(1, self.max_retries + 1):
            try:
                handler(msgs)
                return
            except Exception:
                log.exception("Fallo procesando lote (intento %s/%s)", attempt, self.max_retries)
                if attempt == self.max_retries:
                    raise
                time.sleep(min(2**attempt, 15))
