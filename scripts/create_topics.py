"""Crea los topicos en Redpanda/Kafka.  python scripts/create_topics.py"""
import time

import _bootstrap  # noqa: F401
from confluent_kafka.admin import AdminClient, NewTopic

from telemetry_platform.common.config import get_settings
from telemetry_platform.common.logging import get_logger
from telemetry_platform.messaging.topics import TOPIC_SPECS

log = get_logger("create_topics")


def main() -> None:
    admin = AdminClient({"bootstrap.servers": get_settings().kafka_bootstrap_servers})
    for attempt in range(15):
        try:
            admin.list_topics(timeout=5)
            break
        except Exception:
            log.info("Esperando al broker... (%s)", attempt + 1)
            time.sleep(2)
    new = [
        NewTopic(
            name,
            num_partitions=spec["partitions"],
            replication_factor=1,
            config={"retention.ms": str(spec["retention_ms"]), "compression.type": "producer"},
        )
        for name, spec in TOPIC_SPECS.items()
    ]
    for name, fut in admin.create_topics(new).items():
        try:
            fut.result()
            log.info("Topic creado: %s", name)
        except Exception as exc:
            if "TOPIC_ALREADY_EXISTS" in str(exc):
                log.info("Topic ya existe: %s", name)
            else:
                log.error("Error creando %s: %s", name, exc)


if __name__ == "__main__":
    main()
