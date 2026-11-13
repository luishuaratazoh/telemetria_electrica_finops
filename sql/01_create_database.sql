-- La base "electrical_telemetry" la crea la imagen Docker via POSTGRES_DB.
-- Este script solo habilita las extensiones necesarias dentro de ella.
CREATE EXTENSION IF NOT EXISTS timescaledb;
