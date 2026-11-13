# Electrical Telemetry Platform (local + FinOps)

Plataforma local de telemetría eléctrica: simulador → edge (normaliza/valida/deadband) → Redpanda → procesamiento → PostgreSQL/TimescaleDB + MinIO → FastAPI + Grafana, con **FinOps** integrado (medición de uso, modelo de costos GCP-equivalente, palancas de ahorro y presupuestos).

## 1. Requisitos (instalar una vez)

| Qué | Para qué | Comprobar |
|---|---|---|
| Docker Desktop (con WSL2) | PostgreSQL, Redpanda, MinIO, Grafana, Prometheus, Airflow | `docker version` y `docker compose version` |
| Python 3.10–3.13 (recomendado 3.12) | Simulador, consumidor, API | `python --version` |
| VS Code + extensión Python | Editar y depurar | – |

Memoria: con 16 GB, levanta primero `core + streaming + storage` y añade `monitoring` y `orchestration` después (cada servicio tiene `mem_limit`).

## 2. Instalación del entorno Python

PowerShell, desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .          # opcional: los scripts ya funcionan sin esto
pytest                    # 18 tests unitarios, no necesitan Docker
```

(En WSL/Ubuntu: `source .venv/bin/activate`.) Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

En VS Code: `Ctrl+Shift+P` → *Python: Select Interpreter* → `.venv`.

## 3. Levantar la infraestructura (por etapas)

El archivo `.env` ya tiene todas las variables y credenciales locales.

```powershell
# Etapa 1: base de datos + API
docker compose --profile core up -d --build
# Etapa 2: + mensajeria y almacenamiento de objetos
docker compose --profile core --profile streaming --profile storage up -d --build
# Etapa 3: + observabilidad
docker compose --profile core --profile streaming --profile storage --profile monitoring up -d
# Etapa 4 (pesado): + Airflow
docker compose --profile orchestration up -d
```

> Los scripts SQL de `sql/` se ejecutan **solo la primera vez** que se crea el volumen. Para recrear la BD desde cero: `docker compose --profile core down -v`.

Verifica todo:

```powershell
python scripts/check_env.py
docker compose ps
```

## 4. Ejecutar el pipeline

Abre **tres terminales** (con el venv activado):

```powershell
# (una vez) topicos y datos maestros
python scripts/create_topics.py
python scripts/seed_devices.py                 # modo functional: 3 SE, 30 reles, 300 medidores, 12 interruptores

# Terminal A: consumidor (Redpanda -> PostgreSQL)
python scripts/run_consumer.py

# Terminal B: simulador + edge (-> Redpanda, oscilografias -> MinIO)
python scripts/run_simulator.py
```

Modo carga (flota completa 40 SE / 4000 reles / 50 000 medidores / 1000 interruptores):

```powershell
python scripts/seed_devices.py --mode load
python scripts/run_simulator.py --mode load --ticks 20
python scripts/benchmark_pipeline.py --rows 200000                 # capacidad de insercion
python scripts/benchmark_pipeline.py --messages 200000 --kafka     # capacidad de publicacion
python scripts/benchmark_pipeline.py --cleanup
```

Pruebas sin broker: `python scripts/run_simulator.py --dry-run --ticks 3 --no-persist-usage`.

También puedes correr consumidor y simulador en contenedores: `docker compose --profile core --profile streaming --profile storage --profile app up -d`.

## 5. Dónde ver los datos

| Qué | URL / comando | Credenciales |
|---|---|---|
| **Interfaz web** (menú desplegable, tablas, histórico/online) | http://localhost:8000/ui/ | – |
| **API** (Swagger) | http://localhost:8000/docs | – |
| **Grafana** (dashboard *Telemetria Electrica + FinOps*) | http://localhost:3000 | admin / admin |
| **Redpanda Console** (topics, mensajes, DLQ) | http://localhost:8080 | – |
| **MinIO Console** (oscilografías, ajustes) | http://localhost:9001 | minioadmin / minioadmin123 |
| **Prometheus** | http://localhost:9090 | – |
| **Airflow** | http://localhost:8081 | usuario `admin`; contraseña: `docker compose exec airflow cat /opt/airflow/standalone_admin_password.txt` |
| **PostgreSQL** | `localhost:55432` (`POSTGRES_PORT` en `.env`), BD `electrical_telemetry` | telemetry / telemetry_local_pw |

Consultas por SQL (DBeaver, DataGrip, VS Code SQLTools o `docker compose exec postgres psql -U telemetry -d electrical_telemetry`):

```sql
SELECT * FROM telemetry.v_latest_measurements LIMIT 20;
SELECT * FROM events.v_trips ORDER BY event_time DESC LIMIT 10;
SELECT * FROM events.breaker_states ORDER BY event_time DESC LIMIT 10;
SELECT * FROM files.device_files ORDER BY created_at DESC LIMIT 10;
SELECT quality, COUNT(*) FROM telemetry.measurements GROUP BY 1;
SELECT AVG(ingest_time - event_time) AS lag FROM telemetry.measurements;   -- retraso de ingesta
```

Consultas por API:

```powershell
curl http://localhost:8000/substations
curl "http://localhost:8000/telemetry/latest?substation=SE_001&limit=10"
curl "http://localhost:8000/telemetry/history?asset_id=SEL_751_00001&variable=active_power"
curl http://localhost:8000/events/trips
curl http://localhost:8000/breakers/status
curl http://localhost:8000/oscillography
curl "http://localhost:8000/finops/report?hours=1"
```

Analítica local sobre datos exportados: `duckdb` está instalado (`python -c "import duckdb; ..."`).

## 6. FinOps: cómo está integrado

| Pieza | Dónde | Qué hace |
|---|---|---|
| **Medición de uso** | `finops/usage_tracker.py` → `finops.usage_metrics` + Prometheus | Mensajes/bytes publicados, suprimidos por deadband, consumidos, filas insertadas, duplicados, rechazados |
| **Modelo de costos** | `finops/cost_model.py` + tarifas `finops.cost_rates` | Volumen → GiB de mensajería, almacenamiento (con compresión/retención), objetos, cómputo → USD/mes |
| **Dos escenarios** | `gcp_measured` y `gcp_full_scale` | Costo del volumen *real medido* y proyección a **4 000 relés + 50 000 medidores + 1 000 interruptores** |
| **Unit economics** | `reporter.py` | USD por millón de filas y por dispositivo-mes |
| **Palancas (what-if)** | `cost_model.what_if` | Ahorro estimado: muestrear menos, más deadband, retención menor, comprimir antes |
| **Presupuestos** | `finops.budgets` | Estado OK / WARN / OVER por escenario (el DAG falla si se excede) |
| **Showback** | `finops.v_rows_per_substation_1h` | Filas por subestación (asignación de costo) |
| **Controles reales de costo** | `deadband`, compresión `lz4`, retención de topics, compresión/retención TimescaleDB, *lifecycle* en MinIO, `mem_limit` en Docker, retención Prometheus 7 d | Ahorro efectivo, no solo reportado |

```powershell
python scripts/finops_report.py --hours 1 --save     # imprime reporte y guarda estimaciones (Grafana las muestra)
python scripts/finops_report.py --apply-policies     # aplica FINOPS_RETENTION_DAYS / FINOPS_COMPRESS_AFTER_DAYS
```

**Importante:** las tarifas (`sql/03_create_tables.sql`) son *ilustrativas*, equivalentes aproximados de GCP. Cámbialas con `UPDATE finops.cost_rates ...` usando la calculadora oficial. El costo de la proyección completa depende mucho de `relay_sample_seconds` en `configs/app.yaml` (5 s por defecto) y del ahorro de deadband medido, así que corre el simulador unos minutos antes de leer el reporte.

## 7. Estructura

```
configs/      YAML (simulador, adquisicion/deadband, FinOps, logging)
sql/          DDL: esquemas, hypertables, politicas de compresion/retencion, vistas (incl. finops)
docker/       Dockerfile de la app, prometheus, grafana (datasource + dashboard), init de Postgres
dags/         Airflow: calidad, perfiles de carga, oscilografias, mantenimiento, reporte FinOps
src/telemetry_platform/
  simulator/  datos artificiales      edge/       normaliza, valida, deadband, buffer, colector de archivos
  messaging/  Kafka producer/consumer processing/ validacion, dedupe (Polars), agregacion
  storage/    psycopg2 + MinIO        api/        FastAPI (+ /finops, /metrics)
  analytics/  perfiles, indicadores   finops/     tracker, modelo de costos, reporter, politicas
scripts/      create_topics, seed_devices, run_simulator, run_consumer, benchmark, finops_report, check_env
tests/        unit (sin Docker)
```

## 8. Problemas frecuentes

- **`docker compose` falla con `dockerDesktopLinuxEngine`**: abre Docker Desktop y espera a que diga *Running*.
- **Puerto ocupado** (8080, 9000...): cambia el mapeo en `compose.yaml`. Para PostgreSQL cambia `POSTGRES_PORT` en `.env` (por defecto 55432 porque 5432/5433 suelen estar ocupados por un Postgres local; recrea con `docker compose up -d postgres`).
- **MinIO**: usa la imagen `cgr.dev/chainguard/minio:latest` porque `minio/minio` ya no se publica en Docker Hub/quay.
- **Consumidor rechaza todo / DLQ crece**: faltó `python scripts/seed_devices.py` (con el mismo `--mode` que el simulador).
- **Redpanda no arranca**: sube el límite de memoria de WSL2 (`%UserProfile%\.wslconfig`: `memory=8GB`) y reinicia Docker.
- **Cambié los SQL y no se aplican**: solo corren al crear el volumen → `docker compose --profile core down -v`.
- **Airflow tarda** en el primer arranque (instala paquetes y migra BD): mira `docker compose logs -f airflow`.


