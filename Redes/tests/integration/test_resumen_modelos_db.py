"""The exporter writes the summary tables in ONE transaction inside ``neural_test`` (migration 016 replayed there)."""
import os

import pytest

from pipelines.marts import resumen_modelos as RM
from pipelines.migrate import split_statements
from tests.integration import test_build_core as TB
from tests.unit.test_resumen_modelos import t1, t2, t3

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(k) for k in ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")),
        reason="DEV_* environment variables not set",
    ),
]
T = TB.T


@pytest.fixture()
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        c.autocommit = True
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")
        c.execute(f"CREATE SCHEMA {T}")
        text = (TB.SQL_DIR / "016_resumen_modelos.sql").read_text(encoding="utf-8").replace("neural_mart.", f"{T}.")
        for stmt in split_statements(text):
            c.execute(stmt)
        yield c
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")


def count(conn, tabla):
    return conn.execute(f"SELECT count(*) FROM {T}.{tabla}").fetchone()[0]


def test_export_fills_every_table_and_is_idempotent(conn):
    resumen = RM.construir(t1(), t2(), t3())
    primera = RM.escribir(conn, resumen, mart_schema=T)
    assert primera["resumen_modelos"] == len(resumen["metricas"]) > 0
    assert primera["resumen_modelos_delta"] == len(resumen["deltas"]) > 0
    segunda = RM.escribir(conn, resumen, mart_schema=T)
    assert segunda == primera
    assert count(conn, "resumen_modelos") == primera["resumen_modelos"]
    assert conn.execute(f"SELECT filas FROM {T}.resumen_modelos_construccion").fetchone()[0] == sum(primera.values())


def test_a_failed_export_leaves_the_previous_summary(conn):
    resumen = RM.construir(t1(), t2(), t3())
    RM.escribir(conn, resumen, mart_schema=T)
    antes = count(conn, "resumen_modelos")
    malo = {**resumen, "deltas": resumen["deltas"] + [{**resumen["deltas"][0], "veredicto": "invalido"}]}
    with pytest.raises(Exception):
        RM.escribir(conn, malo, mart_schema=T)
    assert count(conn, "resumen_modelos") == antes and count(conn, "resumen_modelos_delta") == len(resumen["deltas"])


def test_the_schema_must_be_allowed(conn):
    with pytest.raises(ValueError):
        RM.escribir(conn, RM.construir(t1(), t2(), t3()), mart_schema="public")
