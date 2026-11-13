"""Chequeos de calidad cada 15 minutos: frescura, ratio de datos BAD, reles silenciosos."""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def _checks(**_):
    from telemetry_platform.processing.quality import run_quality_checks

    r = run_quality_checks(window_minutes=30)
    print(r)
    if r["rows"] == 0:
        raise ValueError("Sin datos en los ultimos 30 min (esta corriendo simulador + consumidor?)")
    if r["bad_ratio"] > 0.05:
        raise ValueError(f"Ratio de datos BAD alto: {r['bad_ratio']:.2%}")


with DAG(
    "data_quality",
    start_date=datetime(2026, 1, 1),
    schedule="*/15 * * * *",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["telemetry", "quality"],
) as dag:
    PythonOperator(task_id="run_checks", python_callable=_checks)
