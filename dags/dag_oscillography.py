"""Diario: verifica que cada oscilografia registrada exista en MinIO (detecta huerfanos / faltantes)."""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def _verify(**_):
    from telemetry_platform.storage.object_store.minio_client import MinioStorage
    from telemetry_platform.storage.postgres import assets_repository

    storage = MinioStorage()
    missing = []
    records = assets_repository.list_files(limit=1000)
    for f in records:
        if f["file_type"].startswith("comtrade") and not storage.exists(f["bucket"], f["object_key"]):
            missing.append(f["object_key"])
    print(f"verificados={len(records)} faltantes={len(missing)}")
    if missing:
        raise ValueError(f"Archivos registrados que no existen en MinIO: {missing[:10]}")


with DAG(
    "oscillography_integrity",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={"retries": 0},
    tags=["telemetry", "files"],
) as dag:
    PythonOperator(task_id="verify_objects", python_callable=_verify)
