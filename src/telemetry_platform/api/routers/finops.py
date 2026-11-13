"""Endpoints FinOps: costos, almacenamiento, presupuestos."""
from fastapi import APIRouter, Query

from telemetry_platform.finops import reporter
from telemetry_platform.finops import repository as finops_repo

router = APIRouter(prefix="/finops", tags=["finops"])


@router.get("/report")
def report(hours: float = Query(24.0, gt=0, le=720), save: bool = False):
    """Reporte completo: uso medido, escenarios de costo, palancas de ahorro y presupuestos."""
    return reporter.to_jsonable(reporter.build_report(hours, save=save))


@router.get("/storage")
def storage():
    return finops_repo.storage_by_table()


@router.get("/costs")
def costs(scenario: str | None = None):
    """Ultimas estimaciones guardadas (python scripts/finops_report.py --save)."""
    return finops_repo.latest_estimates(scenario)


@router.get("/budgets")
def budgets():
    return finops_repo.budgets()
