"""Gateway edge: normaliza, valida calidad, aplica deadband, publica (con buffer local) y mide uso."""
from __future__ import annotations

from typing import Any

from telemetry_platform.common.config import get_settings, load_yaml, resolve_path
from telemetry_platform.common.logging import get_logger
from telemetry_platform.finops.usage_tracker import UsageTracker
from telemetry_platform.messaging import topics as T
from telemetry_platform.messaging.producer import MessagePublisher

from .collectors.file_collector import FileCollector
from .deadband import DeadbandFilter
from .local_buffer import LocalBuffer
from .normalizer import (
    normalize_breaker,
    normalize_event,
    normalize_meter,
    normalize_relay,
    normalize_settings,
)
from .validator import assess_quality

log = get_logger(__name__)


class EdgeGateway:
    def __init__(self, publisher: MessagePublisher, tracker: UsageTracker, file_repo=None, acq_cfg: dict | None = None):
        cfg = acq_cfg or load_yaml("acquisition.yaml")
        db = cfg["deadband"]
        self.publisher = publisher
        self.tracker = tracker
        self.deadband = DeadbandFilter(db["thresholds_pct"], db["heartbeat_seconds"], db["enabled"])
        self.buffer = LocalBuffer(cfg["buffer"]["max_items"])
        self.file_collector: FileCollector | None = None
        if file_repo is not None:
            osc_dir = resolve_path(load_yaml("simulator.yaml")["oscillography_dir"])
            self.file_collector = FileCollector(
                osc_dir, file_repo, get_settings().bucket_oscillography, self.send, cfg["files"]["delete_after_upload"]
            )

    # ---------------------------------------------------------------- envio
    def send(self, topic: str, msg: dict[str, Any], key: str | None = None) -> None:
        try:
            if len(self.buffer):
                self._drain()
            n = self.publisher.publish(topic, msg, key)
            self.tracker.incr("messages_published", 1, topic)
            self.tracker.incr("bytes_published", n, topic)
        except ConnectionError:
            self.buffer.add(topic, msg, key)
            self.tracker.incr("messages_buffered", 1, topic)

    def _drain(self, n: int = 5000) -> None:
        batch = self.buffer.pop_batch(n)
        for i, (topic, msg, key) in enumerate(batch):
            try:
                size = self.publisher.publish(topic, msg, key)
                self.tracker.incr("messages_published", 1, topic)
                self.tracker.incr("bytes_published", size, topic)
            except ConnectionError:
                self.buffer.push_front(batch[i:])
                raise

    # ---------------------------------------------------------------- manejadores
    def handle_relay(self, raw: dict[str, Any]) -> None:
        for m in normalize_relay(raw):
            m["quality"] = assess_quality(m["measurement_type"], m["value"])
            if m["quality"] == "GOOD" and not self.deadband.should_publish(
                m["asset_id"], m["measurement_type"], m["value"]
            ):
                self.tracker.incr("messages_suppressed", 1, "deadband")
                continue
            self.send(T.TELEMETRY_RAW, m, m["asset_id"])

    def handle_meter(self, raw: dict[str, Any]) -> None:
        m = normalize_meter(raw)
        self.send(T.METERS_PROFILES, m, m["asset_id"])

    def handle_breaker(self, raw: dict[str, Any]) -> None:
        m = normalize_breaker(raw)
        self.send(T.BREAKERS_STATUS, m, m["asset_id"])

    def handle_event(self, raw: dict[str, Any]) -> None:
        m = normalize_event(raw)
        self.send(T.PROTECTION_EVENTS, m, m["asset_id"])

    def handle_settings(self, raw: dict[str, Any]) -> None:
        m = normalize_settings(raw)
        self.send(T.DEVICES_SETTINGS, m, m["asset_id"])

    def collect_files(self) -> int:
        return self.file_collector.scan() if self.file_collector else 0

    def close(self) -> None:
        self.collect_files()
        self.publisher.flush(10.0)
        self.tracker.flush()
        if len(self.buffer):
            log.warning("%d mensajes quedaron en el buffer local sin publicar", len(self.buffer))
