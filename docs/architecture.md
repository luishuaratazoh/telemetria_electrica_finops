# Arquitectura

```
Simulador (Python)  ->  Edge gateway  ->  Redpanda  ->  Consumidor/Procesadores  ->  PostgreSQL + TimescaleDB
 reles/medidores/       normaliza          topics         validacion pydantic          measurements (hypertable)
 interruptores/         calidad GOOD/      telemetry.raw  dedupe (Polars)              events / metering / protection
 fallas/oscilografia    SUSPECT/BAD        protection.*   DLQ: telemetry.dlq           files (metadatos)
        |               deadband (FinOps)   breakers.*                                        |
        |               buffer local        meters.*                                          v
        +--> .cfg/.dat --> FileCollector -> MinIO (oscillography, device-settings)       FastAPI / Grafana
                                                                                          Airflow (batch)
FinOps: UsageTracker (edge + consumer) -> finops.usage_metrics + Prometheus -> cost_model -> reporter/API/Grafana
```

Principios: separacion de responsabilidades por modulo; interfaces `MessagePublisher` y `ObjectStorage` para migrar a Pub/Sub y Cloud Storage; SQL directo con psycopg2 en repositorios; idempotencia por `ON CONFLICT DO NOTHING`; `event_time` vs `ingest_time` separados.
