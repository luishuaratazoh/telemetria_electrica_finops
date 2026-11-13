"""Consumidor: Redpanda -> procesamiento -> PostgreSQL (+ DLQ para mensajes rechazados).  python scripts/run_consumer.py"""
import json
import signal
import threading
import time
from collections import defaultdict

import _bootstrap  # noqa: F401
from prometheus_client import start_http_server

from telemetry_platform.common.config import get_settings
from telemetry_platform.common.logging import get_logger
from telemetry_platform.finops.usage_tracker import UsageTracker
from telemetry_platform.messaging import topics as T
from telemetry_platform.messaging.consumer import BatchConsumer
from telemetry_platform.messaging.producer import KafkaPublisher
from telemetry_platform.processing.event_processor import (
    BreakerProcessor,
    EventProcessor,
    OscillographyProcessor,
    SettingsProcessor,
)
from telemetry_platform.processing.meter_processor import MeterProcessor
from telemetry_platform.processing.telemetry_processor import TelemetryProcessor
from telemetry_platform.storage.object_store.file_repository import FileRepository
from telemetry_platform.storage.object_store.minio_client import MinioStorage
from telemetry_platform.storage.postgres.assets_repository import AssetCache
from telemetry_platform.storage.postgres.connection import close_pool, wait_for_db

log = get_logger("run_consumer")


def main() -> None:
    s = get_settings()
    wait_for_db()
    try:
        start_http_server(s.consumer_metrics_port)
    except OSError:
        log.warning("Puerto de metricas %s ocupado; se omite", s.consumer_metrics_port)

    cache = AssetCache()
    if not cache._devices:
        log.warning("master.devices esta vacio: ejecuta primero  python scripts/seed_devices.py")
    file_repo = FileRepository(MinioStorage(), expire_days=s.oscillography_retention_days)
    processors = {
        T.TELEMETRY_RAW: TelemetryProcessor(cache),
        T.METERS_PROFILES: MeterProcessor(cache),
        T.PROTECTION_EVENTS: EventProcessor(cache),
        T.BREAKERS_STATUS: BreakerProcessor(cache),
        T.OSCILLOGRAPHY_METADATA: OscillographyProcessor(cache),
        T.DEVICES_SETTINGS: SettingsProcessor(cache, file_repo),
    }
    tracker = UsageTracker("consumer")
    dlq = KafkaPublisher(s.kafka_bootstrap_servers, "telemetry-dlq")

    def handler(msgs) -> None:
        t0 = time.perf_counter()
        by_topic: dict[str, list[dict]] = defaultdict(list)
        for m in msgs:
            tracker.incr("messages_consumed", 1, m.topic())
            tracker.incr("bytes_consumed", len(m.value() or b""), m.topic())
            try:
                by_topic[m.topic()].append(json.loads(m.value()))
            except (ValueError, TypeError):
                tracker.incr("messages_rejected", 1, "invalid_json")
                dlq.publish(T.DLQ, {"topic": m.topic(), "error": "invalid_json", "payload": str(m.value())[:500]})
        for topic, raws in by_topic.items():
            proc = processors[topic]
            res = proc.process(raws)
            tracker.incr("rows_inserted", res.inserted, proc.table)
            tracker.incr("rows_duplicate", res.duplicates, proc.table)
            for payload, reason in res.rejected:
                tracker.incr("messages_rejected", 1, topic)
                dlq.publish(T.DLQ, {"topic": topic, "error": reason, "payload": payload})
        log.info("lote de %d mensajes en %.3fs", len(msgs), time.perf_counter() - t0)

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    consumer = BatchConsumer(s.kafka_bootstrap_servers, s.kafka_group_id, T.CONSUMED_TOPICS)
    try:
        consumer.run(handler, stop, on_idle=tracker.flush)
    finally:
        tracker.flush()
        dlq.flush()
        close_pool()
        log.info("Consumidor detenido")


if __name__ == "__main__":
    main()
