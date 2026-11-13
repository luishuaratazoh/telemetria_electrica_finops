"""Diario: agregacion horaria de telemetria + resumen de carga por subestacion (factor de carga)."""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def _hourly(**_):
    from telemetry_platform.processing.aggregation import run_hourly_aggregation

    print("filas agregadas:", run_hourly_aggregation(hours_back=26))


def _daily_summary(ds=None, **_):
    from datetime import date

    from telemetry_platform.analytics.load_profiles import compute_daily_summary

    day = date.fromisoformat(ds) - timedelta(days=1)
    print(f"resumen {day}: {compute_daily_summary(day)} subestaciones")


with DAG(
    "meter_profiles_daily",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["telemetry", "metering"],
) as dag:
    t1 = PythonOperator(task_id="hourly_aggregation", python_callable=_hourly)
    t2 = PythonOperator(task_id="daily_load_summary", python_callable=_daily_summary)
    t1 >> t2
