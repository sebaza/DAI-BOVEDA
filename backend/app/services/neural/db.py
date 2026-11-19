"""Lazy READ-ONLY engine for the Neural database.

Unlike ``services/percepcion/db.py`` nothing is created at import time: the app boots without
``NEURAL_DATABASE_URL`` and the module answers 503 until it is set. No ``create_all``, no DDL.

Every connection is opened as ``TRANSACTION READ ONLY`` with a statement timeout. It is done by event (not by
``options=`` in ``connect_args``) because the URL already carries ``options`` with the ``search_path`` that picks
the ``neural_*`` schemas, and a second ``options`` would override it.
"""
from __future__ import annotations

import threading
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine

from app.services.neural.config import database_url

STATEMENT_TIMEOUT_MS = 20_000

_lock = threading.Lock()
_cache: tuple[str, Engine] | None = None  # (url it was built from, engine)


def crear_engine(url: str) -> Engine:
    engine = create_engine(url, future=True, pool_pre_ping=True, pool_recycle=1800, pool_size=5, max_overflow=5)

    @event.listens_for(engine, "connect")
    def _solo_lectura(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        try:
            cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            cur.execute(f"SET statement_timeout = {int(STATEMENT_TIMEOUT_MS)}")
        finally:
            cur.close()
        dbapi_conn.commit()  # a session-level SET survives only if the transaction closes

    return engine


def get_engine() -> Engine:
    """Engine for the current ``NEURAL_DATABASE_URL`` (rebuilt if the variable changes)."""
    global _cache
    url = database_url()
    with _lock:
        if _cache is None or _cache[0] != url:
            if _cache is not None:
                _cache[1].dispose()
            _cache = (url, crear_engine(url))
        return _cache[1]


def reset() -> None:
    """Dispose the cached engine (tests)."""
    global _cache
    with _lock:
        if _cache is not None:
            _cache[1].dispose()
        _cache = None


def get_neural_conn() -> Iterator[Connection]:
    """FastAPI dependency: one read-only connection per request."""
    conn = get_engine().connect()
    try:
        yield conn
    finally:
        conn.close()
