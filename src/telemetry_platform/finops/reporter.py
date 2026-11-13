"""Reporte FinOps: uso medido -> costo mensual estimado (volumen actual y flota completa) -> palancas de ahorro.

Uso:  python scripts/finops_report.py [--hours 24] [--save] [--apply-policies]
"""
from __future__ import annotations

from datetime import date
from typing import Any

from telemetry_platform.common.config import get_settings, load_yaml
from telemetry_platform.finops import cost_model as cm
from telemetry_platform.finops import repository as repo

MIN_ROWS_FOR_MEASURED_BPR = 10_000


def _g(totals: dict, component: str, metric: str, label: str | None = None) -> float:
    return sum(
        v for (c, m, lb), v in totals.items() if c == component and m == metric and (label is None or lb == label)
    )


def build_report(hours: float = 24.0, save: bool = False) -> dict[str, Any]:
    cfg = load_yaml("app.yaml")["finops"]
    rates = repo.load_rates()
    totals, observed_h = repo.usage_totals(hours)
    observed_h = max(observed_h, 1 / 60)  # al menos 1 minuto para evitar divisiones por ~0
    per_day = 24.0 / observed_h

    consumed = _g(totals, "consumer", "messages_consumed", "telemetry.raw")
    bytes_consumed = _g(totals, "consumer", "bytes_consumed", "telemetry.raw")
    rows_ins = _g(totals, "consumer", "rows_inserted", "telemetry.measurements")
    published = _g(totals, "edge", "messages_published", "telemetry.raw")
    suppressed = _g(totals, "edge", "messages_suppressed")
    saving = suppressed / (suppressed + published) if (suppressed + published) else 0.0

    avg_msg = bytes_consumed / consumed if consumed else cfg["default_message_bytes"]

    approx_rows = repo.approx_rows("telemetry.measurements")
    storage = repo.storage_by_table()
    meas_bytes = next((r["bytes"] for r in storage if r["table_name"] == "telemetry.measurements"), 0)
    # El tamano medido incluye compresion; solo es fiable como bytes/fila bruta si no hay chunks comprimidos.
    comp = repo.compression_stats("telemetry.measurements")
    compressed = bool(comp and (comp.get("number_compressed_chunks") or 0) > 0)
    if approx_rows >= MIN_ROWS_FOR_MEASURED_BPR and not compressed:
        bpr = meas_bytes / approx_rows
        bpr_src = "medido"
    else:
        bpr = cfg["default_bytes_per_row"]
        bpr_src = "supuesto (config)"

    n_files, avg_file = repo.file_stats("comtrade_dat")
    avg_file_bytes = avg_file or cfg["default_file_bytes"]

    params = dict(
        retention_days=get_settings().finops_retention_days,
        compress_after_days=get_settings().finops_compress_after_days,
        compression_ratio=cfg["compression_ratio_assumed"],
        object_retention_days=get_settings().oscillography_retention_days,
        consumer_groups=cfg["consumer_groups"],
    )
    sizing = {k: cm.Sizing(**v) for k, v in cfg["sizing"].items()}

    measured_w = cm.Workload(
        messages_per_day=consumed * per_day,
        avg_message_bytes=avg_msg,
        rows_per_day=rows_ins * per_day,
        bytes_per_row=bpr,
        files_per_day=n_files / max(observed_h / 24.0, 1e-6) if n_files else 0.0,
        avg_file_bytes=avg_file_bytes,
    )
    fleet = cfg["full_fleet"]
    full_w = cm.full_fleet_workload(fleet, saving, avg_msg, bpr, avg_file_bytes)

    devices_now = sum(repo.device_counts().values())
    devices_full = fleet["relays"] + fleet["meters"] + fleet["breakers"]

    scenarios: dict[str, dict[str, Any]] = {}
    for name, w, devices in (("gcp_measured", measured_w, devices_now), ("gcp_full_scale", full_w, devices_full)):
        lines = cm.estimate(w, sizing[name], rates, **params)
        scenarios[name] = {
            "workload": w,
            "lines": lines,
            "economics": cm.unit_economics(lines, w, devices),
        }
        if save:
            repo.save_estimates(
                date.today(), name, [(ln.resource, ln.quantity, ln.unit, ln.unit_cost_usd, ln.cost_usd) for ln in lines]
            )

    levers = cm.what_if(full_w, sizing["gcp_full_scale"], fleet, saving, rates, params)

    budget_status = []
    for b in repo.budgets():
        sc = scenarios.get(b["scenario"])
        if not sc:
            continue
        spent = sc["economics"]["total_usd_month"]
        pct = spent / float(b["monthly_budget_usd"]) * 100 if b["monthly_budget_usd"] else 0
        status = "OVER" if pct > 100 else "WARN" if pct >= float(b["alert_threshold_pct"]) else "OK"
        budget_status.append({**b, "estimated_usd": spent, "pct": round(pct, 1), "status": status})

    return {
        "window_hours_requested": hours,
        "observed_hours": round(observed_h, 3),
        "measured": {
            "messages_consumed": consumed,
            "rows_inserted": rows_ins,
            "avg_message_bytes": round(avg_msg, 1),
            "bytes_per_row": round(bpr, 1),
            "bytes_per_row_source": bpr_src,
            "deadband_saving": round(saving, 4),
            "measurements_table_bytes": meas_bytes,
            "compression": comp,
        },
        "scenarios": scenarios,
        "levers": levers,
        "budgets": budget_status,
        "storage": storage,
    }


def to_jsonable(report: dict[str, Any]) -> dict[str, Any]:
    """Version serializable (para la API)."""
    out = dict(report)
    out["scenarios"] = {
        name: {
            "workload": sc["workload"].__dict__,
            "lines": [ln.__dict__ for ln in sc["lines"]],
            "economics": sc["economics"],
        }
        for name, sc in report["scenarios"].items()
    }
    out["budgets"] = [{**b, "monthly_budget_usd": float(b["monthly_budget_usd"]), "alert_threshold_pct": float(b["alert_threshold_pct"])} for b in report["budgets"]]
    return out


def format_report(rep: dict[str, Any]) -> str:
    m = rep["measured"]
    L = []
    L.append("=" * 74)
    L.append(f" REPORTE FINOPS  (ventana observada: {rep['observed_hours']} h)")
    L.append("=" * 74)
    L.append(f" Mensajes consumidos (telemetry.raw): {m['messages_consumed']:,.0f}")
    L.append(f" Filas insertadas                   : {m['rows_inserted']:,.0f}")
    L.append(f" Bytes medios por mensaje           : {m['avg_message_bytes']}")
    L.append(f" Bytes por fila ({m['bytes_per_row_source']:<17}): {m['bytes_per_row']}")
    L.append(f" Ahorro por deadband                : {m['deadband_saving'] * 100:.1f} %")
    for name, sc in rep["scenarios"].items():
        e = sc["economics"]
        L.append("")
        L.append(f"--- Escenario {name}  (USD/mes ilustrativos)")
        L.append(f"    mensajes/dia={sc['workload'].messages_per_day:,.0f}  filas/dia={sc['workload'].rows_per_day:,.0f}")
        for ln in sorted(sc["lines"], key=lambda x: -x.cost_usd):
            L.append(f"    {ln.resource:<18} {ln.quantity:>14,.1f} {ln.unit:<10} x {ln.unit_cost_usd:<8} = ${ln.cost_usd:>10,.2f}")
        L.append(
            f"    TOTAL ${e['total_usd_month']:,.2f}/mes | ${e['usd_per_million_rows']} por millon de filas | "
            f"${e['usd_per_device_month']} por dispositivo-mes"
        )
    L.append("")
    L.append("--- Palancas de ahorro (flota completa, USD/mes)")
    for lv in rep["levers"]:
        L.append(f"    {lv['lever']:<45} ahorro ${lv['saving_usd_month']:>9,.2f}")
    L.append("")
    L.append("--- Presupuestos")
    for b in rep["budgets"]:
        L.append(
            f"    [{b['status']:<4}] {b['name']:<22} {b['scenario']:<15} "
            f"${b['estimated_usd']:,.2f} de ${float(b['monthly_budget_usd']):,.2f} ({b['pct']}%)"
        )
    L.append("")
    L.append("--- Almacenamiento por tabla")
    for r in rep["storage"][:8]:
        L.append(f"    {r['table_name']:<35} {r['bytes'] / 1024 / 1024:>10,.2f} MiB")
    return "\n".join(L)
