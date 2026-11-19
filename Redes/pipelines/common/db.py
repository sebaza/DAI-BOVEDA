"""Database connections.

The Warehouse connection always forces a read-only session; the dev connection
targets the localhost database that holds the ``neural_*`` schemas.
"""
from __future__ import annotations

from typing import Mapping, Optional

import psycopg

from .config import DbConfig, load_db_config

WAREHOUSE_STATEMENT_TIMEOUT_MS = 120_000


def warehouse_options(statement_timeout_ms: int = WAREHOUSE_STATEMENT_TIMEOUT_MS) -> str:
    """libpq ``options`` string forcing a read-only session with a timeout."""
    if statement_timeout_ms <= 0:
        raise ValueError("statement_timeout_ms must be positive")
    return (
        "-c default_transaction_read_only=on "
        f"-c statement_timeout={int(statement_timeout_ms)}"
    )


def _connect(cfg: DbConfig, **extra) -> psycopg.Connection:
    return psycopg.connect(
        host=cfg.host, port=cfg.port, dbname=cfg.dbname, user=cfg.user,
        password=cfg.password, **extra,
    )


def warehouse_connection(
    env: Optional[Mapping[str, str]] = None,
    statement_timeout_ms: int = WAREHOUSE_STATEMENT_TIMEOUT_MS,
) -> psycopg.Connection:
    """Read-only Warehouse connection (``WH_*`` variables). Not used yet."""
    cfg = load_db_config("WH", env)
    conn = _connect(
        cfg,
        options=warehouse_options(statement_timeout_ms),
        application_name="dai_neural_extract",
    )
    conn.read_only = True
    return conn


def dev_connection(env: Optional[Mapping[str, str]] = None) -> psycopg.Connection:
    """Connection to the localhost dev database (``DEV_*`` variables)."""
    return _connect(load_db_config("DEV", env), application_name="dai_neural_dev")
