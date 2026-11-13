-- Ultima medicion por dispositivo/variable (ventana de 15 min para acotar el costo de la consulta).
CREATE OR REPLACE VIEW telemetry.v_latest_measurements AS
SELECT DISTINCT ON (m.device_id, m.variable_id)
       d.asset_id, s.code AS substation_code, d.device_type,
       v.name AS variable, v.unit, m.value, m.quality, m.event_time, m.ingest_time
FROM telemetry.measurements m
JOIN master.devices d     ON d.id = m.device_id
JOIN master.substations s ON s.id = d.substation_id
JOIN master.variables v   ON v.id = m.variable_id
WHERE m.event_time > now() - INTERVAL '15 minutes'
ORDER BY m.device_id, m.variable_id, m.event_time DESC;

CREATE OR REPLACE VIEW events.v_trips AS
SELECT e.id, d.asset_id, s.code AS substation_code, e.event_type, e.severity, e.event_time, e.details
FROM events.electrical_events e
JOIN master.devices d     ON d.id = e.device_id
JOIN master.substations s ON s.id = d.substation_id
WHERE e.event_type = 'trip';

-- ---------------------------------------------------------------------
-- FinOps
-- ---------------------------------------------------------------------
-- Almacenamiento por tabla (hypertables incluyen todos sus chunks).
CREATE OR REPLACE VIEW finops.v_storage_by_table AS
SELECT 'telemetry.measurements'::text AS table_name, COALESCE(hypertable_size('telemetry.measurements'), 0)::bigint AS bytes
UNION ALL
SELECT 'metering.load_profiles', COALESCE(hypertable_size('metering.load_profiles'), 0)::bigint
UNION ALL
SELECT n.nspname || '.' || c.relname, pg_total_relation_size(c.oid)::bigint
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND (n.nspname IN ('master', 'events', 'protection', 'files', 'audit', 'finops')
       OR (n.nspname = 'telemetry' AND c.relname = 'measurements_hourly')
       OR (n.nspname = 'metering'  AND c.relname = 'daily_load_summary'));

CREATE OR REPLACE VIEW finops.v_ingest_daily AS
SELECT date_trunc('day', time) AS day, component, metric, label, SUM(value) AS total
FROM finops.usage_metrics
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW finops.v_latest_cost_estimates AS
SELECT * FROM finops.cost_estimates
WHERE day = (SELECT MAX(day) FROM finops.cost_estimates);

-- Showback: filas ingeridas en la ultima hora por subestacion (asignacion de costo por "centro").
CREATE OR REPLACE VIEW finops.v_rows_per_substation_1h AS
SELECT s.code AS substation_code, COUNT(*) AS rows_1h
FROM telemetry.measurements m
JOIN master.devices d     ON d.id = m.device_id
JOIN master.substations s ON s.id = d.substation_id
WHERE m.ingest_time > now() - INTERVAL '1 hour'
GROUP BY s.code;
