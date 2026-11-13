-- =====================================================================
-- master
-- =====================================================================
CREATE TABLE IF NOT EXISTS master.substations (
    id            SERIAL PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    region        TEXT,
    latitude      DOUBLE PRECISION,
    longitude     DOUBLE PRECISION,
    load_profile  TEXT NOT NULL DEFAULT 'residential',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS master.devices (
    id             SERIAL PRIMARY KEY,
    asset_id       TEXT NOT NULL UNIQUE,
    substation_id  INT  NOT NULL REFERENCES master.substations (id),
    device_type    TEXT NOT NULL CHECK (device_type IN ('protection_relay', 'smart_meter', 'breaker')),
    manufacturer   TEXT,
    model          TEXT,
    active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS master.variables (
    id    SMALLINT PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    unit  TEXT NOT NULL
);

INSERT INTO master.variables (id, name, unit) VALUES
    (1, 'voltage',        'kV'),
    (2, 'current',        'A'),
    (3, 'active_power',   'kW'),
    (4, 'reactive_power', 'kvar'),
    (5, 'apparent_power', 'kVA'),
    (6, 'frequency',      'Hz'),
    (7, 'energy',         'kWh'),
    (8, 'demand',         'kW')
ON CONFLICT (id) DO NOTHING;

-- =====================================================================
-- telemetry  (event_time = cuando ocurrio; ingest_time = cuando llego)
-- =====================================================================
CREATE TABLE IF NOT EXISTS telemetry.measurements (
    event_time   TIMESTAMPTZ      NOT NULL,
    ingest_time  TIMESTAMPTZ      NOT NULL DEFAULT now(),
    device_id    INT              NOT NULL,
    variable_id  SMALLINT         NOT NULL,
    value        DOUBLE PRECISION NOT NULL,
    quality      TEXT             NOT NULL DEFAULT 'GOOD'
);

SELECT create_hypertable('telemetry.measurements', 'event_time',
                         chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS telemetry.measurements_hourly (
    bucket       TIMESTAMPTZ      NOT NULL,
    device_id    INT              NOT NULL,
    variable_id  SMALLINT         NOT NULL,
    avg_value    DOUBLE PRECISION,
    min_value    DOUBLE PRECISION,
    max_value    DOUBLE PRECISION,
    samples      INT,
    PRIMARY KEY (device_id, variable_id, bucket)
);

-- =====================================================================
-- events
-- =====================================================================
CREATE TABLE IF NOT EXISTS events.electrical_events (
    id           BIGSERIAL PRIMARY KEY,
    device_id    INT         NOT NULL,
    event_type   TEXT        NOT NULL,
    event_time   TIMESTAMPTZ NOT NULL,
    severity     TEXT        NOT NULL DEFAULT 'INFO',
    details      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    ingest_time  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (device_id, event_type, event_time)
);

CREATE TABLE IF NOT EXISTS events.breaker_states (
    device_id   INT         NOT NULL,
    event_time  TIMESTAMPTZ NOT NULL,
    position    TEXT        NOT NULL CHECK (position IN ('OPEN', 'CLOSED')),
    operations  INT         NOT NULL DEFAULT 0,
    PRIMARY KEY (device_id, event_time)
);

-- =====================================================================
-- metering
-- =====================================================================
CREATE TABLE IF NOT EXISTS metering.load_profiles (
    time           TIMESTAMPTZ      NOT NULL,
    meter_id       INT              NOT NULL,
    active_energy  DOUBLE PRECISION NOT NULL,
    demand         DOUBLE PRECISION NOT NULL
);

SELECT create_hypertable('metering.load_profiles', 'time',
                         chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS metering.daily_load_summary (
    day            DATE   NOT NULL,
    substation_id  INT    NOT NULL,
    peak_kw        DOUBLE PRECISION,
    avg_kw         DOUBLE PRECISION,
    load_factor    DOUBLE PRECISION,
    PRIMARY KEY (day, substation_id)
);

-- =====================================================================
-- files / protection / audit
-- =====================================================================
CREATE TABLE IF NOT EXISTS files.device_files (
    id           BIGSERIAL PRIMARY KEY,
    device_id    INT         NOT NULL,
    file_type    TEXT        NOT NULL,
    bucket       TEXT        NOT NULL,
    object_key   TEXT        NOT NULL,
    checksum     TEXT,
    size_bytes   BIGINT,
    event_time   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (bucket, object_key)
);

CREATE TABLE IF NOT EXISTS protection.settings_versions (
    id              BIGSERIAL PRIMARY KEY,
    device_id       INT         NOT NULL,
    version         INT         NOT NULL,
    setting_group   SMALLINT    NOT NULL DEFAULT 1,
    effective_time  TIMESTAMPTZ NOT NULL,
    file_id         BIGINT REFERENCES files.device_files (id),
    params          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (device_id, version)
);

CREATE TABLE IF NOT EXISTS audit.change_log (
    id          BIGSERIAL PRIMARY KEY,
    table_name  TEXT        NOT NULL,
    operation   TEXT        NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    details     JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- =====================================================================
-- finops
-- =====================================================================
-- Tarifas de referencia (equivalente cloud GCP). SON ILUSTRATIVAS: ajusta con la calculadora oficial.
CREATE TABLE IF NOT EXISTS finops.cost_rates (
    resource       TEXT PRIMARY KEY,
    unit           TEXT NOT NULL,
    unit_cost_usd  NUMERIC(12, 6) NOT NULL,
    gcp_service    TEXT,
    notes          TEXT
);

INSERT INTO finops.cost_rates (resource, unit, unit_cost_usd, gcp_service, notes) VALUES
    ('messaging_ingest',  'GiB',        0.040000, 'Pub/Sub',               'Publicacion + entrega por suscripcion'),
    ('object_storage',    'GiB-month',  0.020000, 'Cloud Storage Standard', 'Oscilografias y archivos de configuracion'),
    ('db_storage',        'GiB-month',  0.170000, 'Cloud SQL SSD',          'Almacenamiento PostgreSQL/Timescale'),
    ('db_compute',        'vCPU-hour',  0.041300, 'Cloud SQL',              'CPU de la base de datos'),
    ('db_memory',         'GiB-hour',   0.007000, 'Cloud SQL',              'Memoria de la base de datos'),
    ('compute_pipeline',  'vCPU-hour',  0.033000, 'Cloud Run / GKE',        'Consumidores, API, edge gateway')
ON CONFLICT (resource) DO NOTHING;

-- Metricas de uso medidas por el pipeline (deltas por intervalo de flush).
CREATE TABLE IF NOT EXISTS finops.usage_metrics (
    time       TIMESTAMPTZ      NOT NULL DEFAULT now(),
    component  TEXT             NOT NULL,   -- edge | consumer | api ...
    metric     TEXT             NOT NULL,   -- messages_published, bytes_consumed, rows_inserted ...
    label      TEXT             NOT NULL DEFAULT '',  -- topic / tabla / motivo
    value      DOUBLE PRECISION NOT NULL
);

-- Estimaciones diarias de costo por escenario.
CREATE TABLE IF NOT EXISTS finops.cost_estimates (
    day            DATE        NOT NULL,
    scenario       TEXT        NOT NULL,    -- gcp_measured | gcp_full_scale
    resource       TEXT        NOT NULL,
    quantity       DOUBLE PRECISION NOT NULL,
    unit           TEXT        NOT NULL,
    unit_cost_usd  NUMERIC(12, 6) NOT NULL,
    est_cost_usd   NUMERIC(14, 4) NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (day, scenario, resource)
);

CREATE TABLE IF NOT EXISTS finops.budgets (
    name                 TEXT PRIMARY KEY,
    scenario             TEXT NOT NULL,
    monthly_budget_usd   NUMERIC(14, 2) NOT NULL,
    alert_threshold_pct  NUMERIC(5, 2)  NOT NULL DEFAULT 80
);

INSERT INTO finops.budgets (name, scenario, monthly_budget_usd, alert_threshold_pct) VALUES
    ('demo_gcp_equivalent', 'gcp_measured',   100.00,   80),
    ('full_fleet_target',   'gcp_full_scale', 1000.00, 80)
ON CONFLICT (name) DO NOTHING;
