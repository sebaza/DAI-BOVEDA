"""The per-task exporter writes its tables in ONE transaction inside ``neural_test`` (migration 023 replayed there)."""
import os

import pytest

from pipelines.marts import resumen_tareas as RT
from pipelines.migrate import split_statements
from tests.integration import test_build_core as TB
from tests.unit.test_resumen_tareas import PROGRAMAS, t1, t2, t3, t45, t6

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
        for name in ("023_resumen_tareas.sql", "028_resumen_grupo_t3_eventos.sql", "033_sin_supresion.sql",
                     "034_grupo_intervalos.sql"):
            text = (TB.SQL_DIR / name).read_text(encoding="utf-8").replace("neural_mart.", f"{T}.")
            for stmt in split_statements(text):
                c.execute(stmt)
        yield c
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")


def resumen():
    return RT.construir(t1(), t2(), t3(), t45(), t6(), PROGRAMAS)


def test_export_fills_every_table_and_is_idempotent(conn):
    r = resumen()
    primera = RT.escribir(conn, r, mart_schema=T)
    assert all(n > 0 for n in primera.values()) and primera["resumen_tarea"] == 6
    assert RT.escribir(conn, r, mart_schema=T) == primera
    assert conn.execute(f"SELECT count(*) FROM {T}.resumen_tarea_grupo").fetchone()[0] == primera["resumen_tarea_grupo"]


def test_a_failed_export_leaves_the_previous_summary(conn):
    r = resumen()
    RT.escribir(conn, r, mart_schema=T)
    malo = {**r, "delta": r["delta"] + [{**r["delta"][0], "veredicto": "invalido"}]}
    with pytest.raises(Exception):
        RT.escribir(conn, malo, mart_schema=T)
    assert conn.execute(f"SELECT count(*) FROM {T}.resumen_tarea_delta").fetchone()[0] == len(r["delta"])


def test_migration_033_drops_size_checks(conn):
    r = resumen()
    chico = {**r["grupo"][0], "n": 3, "eventos": 1}
    escrito = RT.escribir(conn, {**r, "grupo": [chico]}, mart_schema=T)
    assert escrito["resumen_tarea_grupo"] == 1
    assert conn.execute(f"SELECT n, eventos FROM {T}.resumen_tarea_grupo").fetchone() == (3, 1)
    conn.execute(f"INSERT INTO {T}.resumen_tarea_calibracion (tarea, variante, corte_k, modelo, decil, n) "
                 f"VALUES ('t1', 'v', 1, 'm', 1, 2)")
    cols = {c for (c,) in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s",
                                       (T,)).fetchall()}
    assert not cols & {"grupos_suprimidos", "n_min", "eventos_min"}


def test_the_schema_must_be_allowed(conn):
    with pytest.raises(ValueError):
        RT.escribir(conn, resumen(), mart_schema="public")


def test_migration_034_stores_the_intervals_the_small_case_mark_and_the_extra_levels(conn):
    from tests.unit.test_resumen_tareas import GT_JSON

    r = RT.construir(t1(), t2(), t3(), t45(), t6(), PROGRAMAS, grupos_todos=GT_JSON)
    escrito = RT.escribir(conn, r, mart_schema=T)
    assert escrito["resumen_tarea_grupo"] == len(r["grupo"])
    niveles = {n for (n,) in conn.execute(f"SELECT DISTINCT nivel FROM {T}.resumen_tarea_grupo").fetchall()}
    assert {"programa", "facultad", "sexo", "nivel_postgrado"} <= niveles
    fila = conn.execute(f"SELECT ap_lo, ap_hi, auc_lo, auc_hi, tasa_lo, tasa_hi, esperado_lo, esperado_hi, pocos_casos, n "
                        f"FROM {T}.resumen_tarea_grupo WHERE tarea = 't1' AND variante = 'base' AND nivel = 'programa' "
                        f"AND grupo = '8002'").fetchone()
    assert all(v is not None for v in fila[:8]) and fila[8] is True and fila[9] == 9
    assert conn.execute(f"SELECT count(*) FROM {T}.resumen_tarea_grupo WHERE pocos_casos <> (n < 10)").fetchone()[0] == 0
    malo = {**r["grupo"][0], "nivel": "inventado", "grupo": "x"}
    with pytest.raises(Exception):
        RT.escribir(conn, {**r, "grupo": [malo]}, mart_schema=T)
