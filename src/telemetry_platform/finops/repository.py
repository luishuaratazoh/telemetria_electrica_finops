"""Acceso a datos FinOps (psycopg2)."""
from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from psycopg2.extras import RealDictCursor, execute_values

from telemetry_platform.storage.postgres.connection import get_connection


def record_usage(rows: Sequence[tuple]) -> None:
    """rows: (component, metric, label, value)."""
    if not rows:
        return
    with get_connection() as conn, conn.cursor() as cur:
        execute_values(
            cur, "INSERT INTO finops.usage_metrics (component, metric, label, value) VALUES %s", rows
        )


def usage_totals(hours: float) -> tuple[dict[tuple[str, str, str], float], float]:
    """Suma de metricas en la ventana y horas realmente observadas (entre primer y ultimo registro)."""
    sql = """
        SELECT component, metric, label, SUM(value) AS total
        FROM finops.usage_metrics WHERE time > now() - make_interval(secs => %s)
        GROUP BY 1, 2, 3
    """
    span_sql = """
        SELECT COALESCE(EXTRACT(EPOCH FROM (MAX(time) - MIN(time))) / 3600.0, 0)
        FROM finops.usage_metrics WHERE time > now() - make_interval(secs => %s)
    """
    secs = hours * 3600
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (secs,))
        totals = {(c, m, lb): float(v) for c, m, lb, v in cur.fetchall()}
        cur.execute(span_sql, (secs,))
        observed = float(cur.fetchone()[0])
    return totals, observed


def storage_by_table() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT table_name, bytes FROM finops.v_storage_by_table ORDER BY bytes DESC")
        return cur.fetchall()


def approx_rows(hypertable: str) -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT approximate_row_count(%s)", (hypertable,))
        return int(cur.fetchone()[0] or 0)


def compression_stats(hypertable: str) -> dict[str, Any] | None:
    sql = """
        SELECT total_chunks, number_compressed_chunks,
               before_compression_total_bytes AS before_bytes, after_compression_total_bytes AS after_bytes
        FROM hypertable_compression_stats(%s)
    """
    try:
        with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (hypertable,))
            return cur.fetchone()
    except Exception:
        return None


def device_counts() -> dict[str, int]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT device_type, COUNT(*) FROM master.devices GROUP BY 1")
        return {t: int(n) for t, n in cur.fetchall()}


def file_stats(file_type: str = "comtrade_dat") -> tuple[float, float]:
    """(archivos, tamano medio en bytes) por tipo."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*), COALESCE(AVG(size_bytes), 0) FROM files.device_files WHERE file_type = %s", (file_type,)
        )
        n, avg = cur.fetchone()
        return float(n), float(avg)


def load_rates() -> dict[str, float]:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT resource, unit_cost_usd FROM finops.cost_rates")
            return {r: float(c) for r, c in cur.fetchall()}
    except Exception:
        return {}


def budgets() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT name, scenario, monthly_budget_usd, alert_threshold_pct FROM finops.budgets")
        return cur.fetchall()


def save_estimates(day: date, scenario: str, lines: Sequence[tuple]) -> None:
    """lines: (resource, quantity, unit, unit_cost_usd, est_cost_usd). Reemplaza el dia/escenario."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM finops.cost_estimates WHERE day = %s AND scenario = %s", (day, scenario))
        execute_values(
            cur,
            "INSERT INTO finops.cost_estimates (day, scenario, resource, quantity, unit, unit_cost_usd, est_cost_usd) VALUES %s",
            [(day, scenario, *ln) for ln in lines],
        )


def latest_estimates(scenario: str | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM finops.v_latest_cost_estimates WHERE (%s::text IS NULL OR scenario = %s) ORDER BY scenario, est_cost_usd DESC",
            (scenario, scenario),
        )
        return cur.fetchall()
