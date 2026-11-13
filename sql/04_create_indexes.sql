-- Indices (el unico indice unico incluye la columna de particion, requisito de TimescaleDB).
-- Tambien garantiza idempotencia: reentregas de Kafka no duplican filas (ON CONFLICT DO NOTHING).
CREATE UNIQUE INDEX IF NOT EXISTS ux_measurements_key
    ON telemetry.measurements (device_id, variable_id, event_time);

CREATE UNIQUE INDEX IF NOT EXISTS ux_load_profiles_key
    ON metering.load_profiles (meter_id, time);

CREATE INDEX IF NOT EXISTS ix_events_device_time ON events.electrical_events (device_id, event_time DESC);
CREATE INDEX IF NOT EXISTS ix_events_type_time   ON events.electrical_events (event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS ix_devices_substation ON master.devices (substation_id, device_type);
CREATE INDEX IF NOT EXISTS ix_files_device       ON files.device_files (device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_usage_time         ON finops.usage_metrics (time DESC, component, metric);

-- ---------------------------------------------------------------------
-- FinOps: compresion y retencion (principales palancas de costo de almacenamiento).
-- Se pueden reajustar luego con:  python scripts/finops_report.py --apply-policies
-- ---------------------------------------------------------------------
ALTER TABLE telemetry.measurements SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, variable_id',
    timescaledb.compress_orderby   = 'event_time DESC'
);
SELECT add_compression_policy('telemetry.measurements', INTERVAL '2 days', if_not_exists => TRUE);
SELECT add_retention_policy('telemetry.measurements',   INTERVAL '30 days', if_not_exists => TRUE);

ALTER TABLE metering.load_profiles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'meter_id',
    timescaledb.compress_orderby   = 'time DESC'
);
SELECT add_compression_policy('metering.load_profiles', INTERVAL '14 days', if_not_exists => TRUE);
SELECT add_retention_policy('metering.load_profiles',   INTERVAL '365 days', if_not_exists => TRUE);
