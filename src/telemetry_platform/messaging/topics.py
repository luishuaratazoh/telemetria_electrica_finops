"""Topicos y su configuracion. Retencion corta = menor costo de almacenamiento del broker (FinOps)."""

TELEMETRY_RAW = "telemetry.raw"
PROTECTION_EVENTS = "protection.events"
BREAKERS_STATUS = "breakers.status"
METERS_PROFILES = "meters.profiles"
OSCILLOGRAPHY_METADATA = "oscillography.metadata"
DEVICES_SETTINGS = "devices.settings"
DLQ = "telemetry.dlq"

HOUR_MS = 3_600_000

TOPIC_SPECS: dict[str, dict[str, int]] = {
    TELEMETRY_RAW: {"partitions": 6, "retention_ms": 24 * HOUR_MS},
    PROTECTION_EVENTS: {"partitions": 3, "retention_ms": 72 * HOUR_MS},
    BREAKERS_STATUS: {"partitions": 3, "retention_ms": 72 * HOUR_MS},
    METERS_PROFILES: {"partitions": 6, "retention_ms": 48 * HOUR_MS},
    OSCILLOGRAPHY_METADATA: {"partitions": 1, "retention_ms": 72 * HOUR_MS},
    DEVICES_SETTINGS: {"partitions": 1, "retention_ms": 168 * HOUR_MS},
    DLQ: {"partitions": 1, "retention_ms": 168 * HOUR_MS},
}

CONSUMED_TOPICS = [
    TELEMETRY_RAW,
    PROTECTION_EVENTS,
    BREAKERS_STATUS,
    METERS_PROFILES,
    OSCILLOGRAPHY_METADATA,
    DEVICES_SETTINGS,
]
