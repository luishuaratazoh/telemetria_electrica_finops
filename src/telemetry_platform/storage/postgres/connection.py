"""Pool de conexiones psycopg2 (SQL directo, sin ORM)."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.pool import ThreadedConnectionPool

from telemetry_platform.common.config import get_settings
from telemetry_platform.common.logging import get_logger

log = get_logger(__name__)

_pool: ThreadedConnectionPool | None = None
_lock = threading.Lock()


def get_pool(minconn: int = 1, maxconn: int = 10) -> ThreadedConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadedConnectionPool(minconn, maxconn, dsn=get_settings().dsn)
        return _pool


@contextmanager
def get_connection() -> Iterator[PgConnection]:
    """Entrega una conexion del pool; hace commit al salir y rollback ante error."""
    pool = get_pool()
    conn = pool.getconn()
    while conn.closed:  # descartar conexiones muertas (p.ej. tras reiniciar PostgreSQL)
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    broken = False
    try:
        yield conn
        conn.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn, close=broken or bool(conn.closed))


def close_pool() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


def wait_for_db(timeout: float = 60.0) -> None:
    """Espera a que PostgreSQL acepte conexiones (util al arrancar contenedores)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            conn = psycopg2.connect(get_settings().dsn, connect_timeout=3)
            conn.close()
            return
        except psycopg2.OperationalError as exc:
            if time.monotonic() > deadline:
                raise
            log.info("Esperando PostgreSQL... (%s)", str(exc).strip().splitlines()[0])
            time.sleep(2)
