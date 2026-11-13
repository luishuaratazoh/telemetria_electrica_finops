"""Verifica conectividad con PostgreSQL, Redpanda y MinIO.  python scripts/check_env.py"""
import _bootstrap  # noqa: F401

from telemetry_platform.common.config import get_settings


def check_pg() -> str:
    import psycopg2

    conn = psycopg2.connect(get_settings().dsn, connect_timeout=5)
    cur = conn.cursor()
    cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
    row = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM master.variables")
    n = cur.fetchone()[0]
    conn.close()
    return f"TimescaleDB {row[0] if row else 'NO INSTALADO'}, variables={n}"


def check_kafka() -> str:
    from confluent_kafka.admin import AdminClient

    md = AdminClient({"bootstrap.servers": get_settings().kafka_bootstrap_servers}).list_topics(timeout=5)
    return f"{len(md.brokers)} broker(s), {len(md.topics)} topics"


def check_minio() -> str:
    from telemetry_platform.storage.object_store.minio_client import MinioStorage

    return f"buckets={[b.name for b in MinioStorage().client.list_buckets()]}"


if __name__ == "__main__":
    for name, fn in (("PostgreSQL", check_pg), ("Redpanda", check_kafka), ("MinIO", check_minio)):
        try:
            print(f"[ OK ] {name:<11} {fn()}")
        except Exception as exc:
            print(f"[FAIL] {name:<11} {str(exc).strip().splitlines()[0][:150]}")
