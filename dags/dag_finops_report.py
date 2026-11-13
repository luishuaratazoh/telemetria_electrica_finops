"""Diario: calcula y guarda estimaciones de costo (las lee Grafana) y falla si se excede un presupuesto."""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def _report(**_):
    from telemetry_platform.finops import reporter

    rep = reporter.build_report(hours=24, save=True)
    print(reporter.format_report(rep))
    over = [b for b in rep["budgets"] if b["status"] == "OVER"]
    if over:
        raise ValueError(f"Presupuesto excedido: {[b['name'] for b in over]}")


with DAG(
    "finops_daily_report",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["finops"],
) as dag:
    PythonOperator(task_id="cost_report", python_callable=_report)
