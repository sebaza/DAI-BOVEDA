"""Invariants of the built ``neural_mart.snapshot_t2`` and an independent SQL recomputation of the point-in-time
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


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM neural_mart.snapshot_t2")
            if cur.fetchone()[0] == 0:
                pytest.skip("snapshot_t2 not built (python -m pipelines.snapshots.t2)")
        yield c


def scalar(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def test_rows_are_regular_periods_inside_the_window_with_consistent_splits(conn):
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t2 WHERE substr(periodo, 5, 2) NOT IN ('10', '20')") == 0
    latest = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t2_resumen WHERE clave = 'periodo_maximo'")
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t2 WHERE periodo < '201510' OR periodo > '202520' "
                        "OR periodo >= %s", (latest,)) == 0
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t2 WHERE split <> CASE
        WHEN periodo <= '202020' THEN 'train' WHEN periodo <= '202220' THEN 'valid'
        WHEN periodo <= '202420' THEN 'test' ELSE 'posterior' END""") == 0


def test_periods_without_recorded_failures_are_absent(conn):
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t2 WHERE periodo IN ('201920', '202010')") == 0


def test_label_is_the_grade_below_four_of_an_evaluated_attempt(conn):
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t2 s JOIN neural_core.intento_asignatura i USING (intento_id)
        WHERE NOT i.es_intento_evaluado OR i.nota_numerica IS NULL
           OR s.y <> (i.nota_numerica < 4.0)::int""") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t2 s JOIN neural_core.intento_asignatura i "
                        "USING (intento_id) WHERE i.resultado_tipo <> 'evaluado'") == 0


def test_k_matches_the_admission_semester(conn):
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t2 s JOIN neural_core.episodio_programa e USING (episodio_id)
        WHERE (substr(s.periodo, 1, 4)::int * 2 + (substr(s.periodo, 5, 2) = '20')::int)
            - (substr(e.periodo_admision, 1, 4)::int * 2 + (substr(e.periodo_admision, 5, 2) >= '20')::int) + 1 <> s.k""") == 0


def test_course_history_matches_an_independent_sql_recomputation(conn):
    """n_hist_curso = evaluated attempts of the course with periodo STRICTLY before the attempt's period."""
    assert scalar(conn, """
        WITH muestra AS (SELECT intento_id, periodo, codigo_asignatura, n_hist_curso, tasa_hist_curso
                         FROM neural_mart.snapshot_t2 WHERE intento_id % 9973 = 0),
        h AS (SELECT m.intento_id, count(i.intento_id) AS n, avg((i.nota_numerica >= 4.0)::int) AS tasa
              FROM muestra m
              LEFT JOIN neural_core.intento_asignatura i
                ON i.codigo_asignatura = m.codigo_asignatura AND i.es_intento_evaluado
               AND i.nota_numerica IS NOT NULL AND i.periodo < m.periodo
               AND i.periodo NOT IN ('201920', '202010')
              GROUP BY m.intento_id)
        SELECT count(*) FROM muestra m JOIN h USING (intento_id)
        WHERE h.n <> m.n_hist_curso OR abs(coalesce(h.tasa, 0) - coalesce(m.tasa_hist_curso, 0)) > 1e-5""") == 0


def test_student_history_matches_an_independent_sql_recomputation(conn):
    assert scalar(conn, """
        WITH muestra AS (SELECT intento_id, episodio_id, periodo, n_intentos_acum, n_reprob_acum
                         FROM neural_mart.snapshot_t2 WHERE intento_id % 10007 = 0),
        h AS (SELECT m.intento_id,
                     count(i.intento_id) FILTER (WHERE i.es_intento_evaluado AND i.nota_numerica IS NOT NULL) AS n,
                     count(i.intento_id) FILTER (WHERE i.es_intento_evaluado AND i.nota_numerica IS NOT NULL
                                                 AND NOT i.aprobado_curricular) AS r
              FROM muestra m
              LEFT JOIN neural_core.intento_asignatura i ON i.episodio_id = m.episodio_id AND i.periodo < m.periodo
                   AND i.periodo NOT IN ('201920', '202010')
              GROUP BY m.intento_id)
        SELECT count(*) FROM muestra m JOIN h USING (intento_id) WHERE h.n <> m.n_intentos_acum OR h.r <> m.n_reprob_acum""") == 0


def test_prerequisite_counts_match_the_edge_table(conn):
    assert scalar(conn, """
        WITH muestra AS (SELECT s.intento_id, s.n_prereq, e.cod_programa, s.catalogo, s.codigo_asignatura
                         FROM neural_mart.snapshot_t2 s JOIN neural_core.episodio_programa e USING (episodio_id)
                         WHERE s.info_prereq AND s.intento_id % 1999 = 0)
        SELECT count(*) FROM muestra m
        WHERE m.n_prereq <> (SELECT count(DISTINCT codigo_requisito) FROM neural_core.prerrequisito p
                             WHERE p.cod_programa = m.cod_programa AND p.catalogo = m.catalogo
                               AND p.codigo_asignatura = m.codigo_asignatura)""") == 0


def test_no_sex_or_teacher_key_in_the_table(conn):
    cols = {r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns "
                                       "WHERE table_schema = 'neural_mart' AND table_name = 'snapshot_t2'")}
    assert "sexo" not in cols and "docente_key" not in cols and "nrc" not in cols
