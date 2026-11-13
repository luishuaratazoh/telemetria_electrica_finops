"""Semanal: ANALYZE de tablas principales y reporte de compresion/tamano."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def _analyze(**_):
    from telemetry_platform.storage.postgres.connection import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        for t in ("telemetry.measurements", "metering.load_profiles", "events.electrical_events", "master.devices"):
            cur.execute(f"ANALYZE {t}")


def _report(**_):
    from telemetry_platform.finops import repository

    for r in repository.storage_by_table():
        print(f"{r['table_name']:<35} {r['bytes'] / 1024 / 1024:,.1f} MiB")
    print("compresion:", repository.compression_stats("telemetry.measurements"))


with DAG(
    "database_maintenance",
    start_date=datetime(2026, 1, 1),
    schedule="@weekly",
    catchup=False,
    tags=["telemetry", "maintenance", "finops"],
) as dag:
    a = PythonOperator(task_id="analyze_tables", python_callable=_analyze)
    b = PythonOperator(task_id="storage_report", python_callable=_report)
    a >> b
