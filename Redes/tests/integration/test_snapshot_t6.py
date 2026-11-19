"""Invariants of the built ``neural_mart.snapshot_t6`` and an independent SQL recomputation of the labels and some
features (read only). Skipped without DEV_* or an empty snapshot."""
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(k) for k in ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")),
        reason="DEV_* environment variables not set",
    ),
]

SLOT = """(CASE WHEN right({p}, 2) <= '10' THEN left({p}, 4)::int * 2 WHEN right({p}, 2) <= '20' THEN left({p}, 4)::int * 2 + 1
          ELSE (left({p}, 4)::int + 1) * 2 END) - (left({a}, 4)::int * 2 + (right({a}, 2) >= '20')::int) + 1"""
ORD_EGRESO = "(left(s.periodo_admision, 4)::int * 2 + (right(s.periodo_admision, 2) >= '20')::int + s.semestres_a_egreso - 1)"
PG_ORD = "(left(m.periodo, 4)::int * 2 + (right(m.periodo, 2) = '60')::int)"


def slot(p, a):
    return SLOT.format(p=p, a=a)


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM neural_mart.snapshot_t6")
            if cur.fetchone()[0] == 0:
                pytest.skip("snapshot_t6 not built (python -m pipelines.snapshots.t6)")
        yield c


def scalar(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def cierre(conn):
    return int(scalar(conn, "SELECT valor FROM neural_mart.snapshot_t6_resumen WHERE clave = 'ordinal_cierre'"))


def test_the_closed_limit_is_the_last_closed_regular_period(conn):
    c = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t6_resumen WHERE clave = 'periodo_cierre'")
    latest = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t6_resumen WHERE clave = 'periodo_maximo'")
    assert c < latest and cierre(conn) == int(c[:4]) * 2 + (c[4:] == "20")


def test_splits_follow_the_year_of_egress_and_the_year_is_derived_from_the_cut(conn):
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t6 WHERE split <> CASE WHEN anio_egreso <= 2022 THEN 'train' "
                        "WHEN anio_egreso = 2023 THEN 'valid' ELSE 'test' END") == 0
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t6 s WHERE s.anio_egreso <> {ORD_EGRESO} / 2") == 0
    assert scalar(conn, "SELECT min(cohorte_anio) FROM neural_mart.snapshot_t6") >= 2015


def test_follow_up_time_and_censoring(conn):
    c = cierre(conn)
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t6 s WHERE s.seguimiento <> {c} - {ORD_EGRESO}") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t6 WHERE tiempo < 1 OR tiempo > seguimiento") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t6 WHERE evento = 0 AND tiempo <> seguimiento") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t6 WHERE tiempo_cualquier_fila < 1 "
                        "OR tiempo_cualquier_fila > seguimiento OR (evento_cualquier_fila = 0 AND tiempo_cualquier_fila <> seguimiento)") == 0
    # the sensitivity (any row) can only add events and bring them earlier
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t6 WHERE evento = 1 AND (evento_cualquier_fila = 0 "
                        "OR tiempo_cualquier_fila > tiempo)") == 0


def test_label_matches_an_independent_sql_recomputation(conn):
    """tiempo = first ENROLLED postgrado semester of the person minus the egreso semester, if inside the follow-up."""
    assert scalar(conn, f"""
        WITH primera AS (SELECT m.persona_key, min({PG_ORD}) AS o FROM neural_core.matricula_postgrado m
                         WHERE m.estado_matricula = 'MATRICULADO' GROUP BY 1)
        SELECT count(*) FROM neural_mart.snapshot_t6 s LEFT JOIN primera p USING (persona_key)
        WHERE s.evento <> (CASE WHEN p.o IS NOT NULL AND p.o - {ORD_EGRESO} BETWEEN 1 AND s.seguimiento THEN 1 ELSE 0 END)
           OR (s.evento = 1 AND s.tiempo <> p.o - {ORD_EGRESO})""") == 0
    assert scalar(conn, f"""
        SELECT count(*) FROM neural_mart.snapshot_t6 s
        WHERE s.evento_cualquier_fila = 1 AND NOT EXISTS (SELECT 1 FROM neural_core.matricula_postgrado m
              WHERE m.persona_key = s.persona_key AND {PG_ORD} = {ORD_EGRESO} + s.tiempo_cualquier_fila)""") == 0


def test_nobody_enrolled_in_postgrado_at_or_before_the_egress_is_a_unit(conn):
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t6 s JOIN neural_core.matricula_postgrado m USING (persona_key)
        WHERE m.estado_matricula = 'MATRICULADO' AND {PG_ORD} <= {ORD_EGRESO}""") == 0
    assert int(scalar(conn, "SELECT valor FROM neural_mart.snapshot_t6_resumen WHERE clave = 'embudo_postgrado_previo_durante'")) > 0


def test_funnel_identity_in_the_summary(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT replace(clave, 'embudo_', ''), valor FROM neural_mart.snapshot_t6_resumen WHERE clave LIKE 'embudo_%'")
        f = {k: int(v) for k, v in cur.fetchall()}
    assert f["poblacion"] - f["sin_egreso"] == f["egresados"]
    assert f["egresados"] - f["egreso_antes_de_la_fuente"] - f["postgrado_previo_antes"] - f["postgrado_previo_durante"] \
        - f["sin_seguimiento"] == f["elegibles"]
    assert f["elegibles"] == scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t6")
    assert f["eventos"] == scalar(conn, "SELECT sum(evento) FROM neural_mart.snapshot_t6")


def test_no_egress_state_precedes_the_cut(conn):
    """For units without a Plan Comun link: the first egreso_titulacion state is never before the cut."""
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t6 s
        WHERE s.episodio_especialidad_id IS NULL AND EXISTS (SELECT 1 FROM neural_core.evento_estado e
              JOIN neural_meta.dic_estado d USING (cod_estado)
              WHERE e.episodio_id = s.episodio_id AND d.clase_estado = 'egreso_titulacion' AND NOT e.es_correccion_sistema
                AND {slot('e.periodo', 's.periodo_admision')} < s.semestres_a_egreso)""") == 0


def test_enrolled_semesters_and_attempts_up_to_the_cut_match_an_independent_recomputation(conn):
    assert scalar(conn, f"""
        WITH muestra AS (SELECT episodio_id, episodio_especialidad_id, periodo_admision, semestres_a_egreso AS k,
                                semestres_matriculados, intentos_evaluados
                         FROM neural_mart.snapshot_t6 WHERE episodio_id % 9 = 0),
        h AS (SELECT m.episodio_id,
                     (SELECT count(DISTINCT e.periodo) FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
                      WHERE e.episodio_id IN (m.episodio_id, m.episodio_especialidad_id)
                        AND d.clase_estado IN ('matricula', 'reingreso', 'cambio_ciclo')
                        AND NOT e.es_correccion_sistema AND e.periodo ~ '^[0-9]{{4}}(10|20)$'
                        AND {slot('e.periodo', 'm.periodo_admision')} BETWEEN 1 AND m.k) AS sem,
                     (SELECT count(*) FROM neural_core.intento_asignatura i
                      WHERE i.episodio_id IN (m.episodio_id, m.episodio_especialidad_id) AND i.es_intento_evaluado
                        AND i.periodo NOT IN ('201920', '202010')
                        AND {slot('i.periodo', 'm.periodo_admision')} BETWEEN 1 AND m.k) AS ie
              FROM muestra m)
        SELECT count(*) FROM muestra m JOIN h USING (episodio_id) WHERE h.sem <> m.semestres_matriculados OR h.ie <> m.intentos_evaluados""") == 0


def test_titulacion_u_by_the_cut_is_supported_by_a_state_u_or_a_titulacion_row(conn):
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t6 s
        WHERE s.titulado_al_corte AND s.episodio_especialidad_id IS NULL AND NOT EXISTS (
            SELECT 1 FROM neural_core.evento_estado e WHERE e.episodio_id = s.episodio_id AND e.cod_estado = 'U'
              AND NOT e.es_correccion_sistema AND {slot('e.periodo', 's.periodo_admision')} <= s.semestres_a_egreso)
        AND NOT EXISTS (SELECT 1 FROM neural_core.titulacion t WHERE t.episodio_id = s.episodio_id)""") == 0


def test_no_sex_no_postgrado_detail_and_the_malla_flag_is_consistent(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'neural_mart' AND table_name = 'snapshot_t6'")
        cols = {r[0] for r in cur.fetchall()}
    assert "sexo" not in cols and "sexo_equidad" in cols
    assert not {c for c in cols if "postgrado" in c}
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t6 WHERE malla_conocida AND creditos_malla_total IS NULL") == 0
