"""Runs only when the DEV_* variables point at the localhost dev database."""
import os

import pytest

from pipelines.migrate import ALLOWED_SCHEMAS, apply_migrations
from pipelines.normalize.states import ESTADOS

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(k) for k in ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")),
        reason="DEV_* environment variables not set",
    ),
]


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        yield c


def test_migrations_are_idempotent(conn):
    apply_migrations(conn)
    second = apply_migrations(conn)
    assert second and all(status == "skipped" for _, status in second)


def test_dictionaries_are_seeded(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM neural_meta.dic_estado")
        assert cur.fetchone()[0] == len(ESTADOS)
        cur.execute("SELECT count(*) FROM neural_meta.dic_tipo_admision")
        assert cur.fetchone()[0] == 52
        cur.execute("SELECT cod_admision, prioridad_via FROM neural_meta.dic_tipo_admision WHERE cod_admision IN ('PC','LS','LE','NN')")
        assert dict(cur.fetchall()) == {"PC": 1, "LS": 2, "LE": 3, "NN": 4}


def test_route_priority_sql_matches_python(conn):
    from pipelines.normalize.admission import via_priority

    with conn.cursor() as cur:
        cur.execute("SELECT cod_admision, tipo_qualitas, prioridad_via FROM neural_meta.dic_tipo_admision")
        rows = cur.fetchall()
    assert rows
    for cod, tipo_qualitas, prioridad in rows:
        assert via_priority(cod, tipo_qualitas) == prioridad, cod
    assert {cod: p for cod, _, p in rows if cod in ("EB", "EC", "EM", "EP")} == {"EB": 3, "EC": 3, "EM": 3, "EP": 3}


def test_calendar_matches_python_rules(conn):
    from pipelines.normalize.periods import parse_periodo

    with conn.cursor() as cur:
        cur.execute("SELECT periodo, tipo_periodo, periodo_atipico, orden_regular FROM neural_meta.calendario_periodo")
        rows = cur.fetchall()
    assert rows
    for periodo, tipo, atipico, orden in rows:
        info = parse_periodo(periodo)
        assert (info.tipo_periodo, info.periodo_atipico, info.orden_regular) == (tipo, atipico, orden)


def test_created_objects_live_only_in_neural_schemas(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname LIKE 'neural\\_%'"
        )
        assert {r[0] for r in cur.fetchall()} <= set(ALLOWED_SCHEMAS)


def test_huella_clave_table_is_single_row_and_hex_only(conn):
    import psycopg

    apply_migrations(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('neural_meta.huella_clave') IS NOT NULL")
        assert cur.fetchone()[0] is True
    for valores in ((2, "a" * 64), (1, "no-es-hex")):
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.cursor() as cur:
                cur.execute("INSERT INTO neural_meta.huella_clave (id, huella) VALUES (%s, %s)", valores)
        conn.rollback()
