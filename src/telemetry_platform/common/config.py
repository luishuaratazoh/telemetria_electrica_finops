"""Configuracion: variables de entorno (.env) + archivos YAML de configs/."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

# .../src/telemetry_platform/common/config.py -> raiz del proyecto
ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "configs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"), env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "electrical_telemetry"
    postgres_user: str = "telemetry"
    postgres_password: str = "telemetry_local_pw"

    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_group_id: str = "telemetry-processor"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_secure: bool = False
    minio_public_endpoint: str | None = None  # host visible desde el navegador (URLs prefirmadas)
    bucket_oscillography: str = "oscillography"
    bucket_settings: str = "device-settings"

    simulator_mode: str = "functional"
    consumer_metrics_port: int = 8001
    simulator_metrics_port: int = 8002

    finops_monthly_budget_usd: float = 50.0
    finops_retention_days: int = 30
    finops_compress_after_days: int = 2
    oscillography_retention_days: int = 90

    @property
    def dsn(self) -> str:
        from psycopg2.extensions import make_dsn

        return make_dsn(
            host=self.postgres_host,
            port=self.postgres_port,
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password,
            application_name="telemetry_platform",
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=None)
def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resolve_path(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p
