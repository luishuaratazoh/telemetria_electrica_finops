"""API REST. Ejecutar: uvicorn telemetry_platform.api.main:app --reload  (docs en /docs)."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, make_asgi_app

from telemetry_platform import __version__
from telemetry_platform.api.routers import devices, events, finops, oscillography, substations, telemetry
from telemetry_platform.common.logging import get_logger
from telemetry_platform.storage.postgres.connection import close_pool, get_connection, get_pool

log = get_logger(__name__)

HTTP_REQUESTS = Counter("api_http_requests_total", "Peticiones HTTP", ["method", "path", "status"])
HTTP_LATENCY = Histogram("api_http_request_seconds", "Latencia HTTP", ["path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_pool()
    yield
    close_pool()


app = FastAPI(title="Electrical Telemetry Platform", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
    HTTP_LATENCY.labels(path).observe(time.perf_counter() - t0)
    return response


@app.get("/health", tags=["system"])
def health():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
    return {"status": "ok", "version": __version__}


for r in (substations.router, devices.router, telemetry.router, events.router, oscillography.router, finops.router):
    app.include_router(r)

app.mount("/metrics", make_asgi_app())


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/ui/")


# Interfaz web (misma origen que la API: sin CORS). Abrir http://localhost:8000/ui/
app.mount("/ui", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")
