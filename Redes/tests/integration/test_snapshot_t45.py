"""Invariants of the built ``neural_mart.snapshot_t45`` and an independent SQL recomputation of the outcomes (read only).
Skipped without DEV_* or an empty snapshot."""
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
TIPOS = "('cambio_carrera', 'traslado_sede', 'traslado_otro')"


def slot(p, a):
    return SLOT.format(p=p, a=a)


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM neural_mart.snapshot_t45")
            if cur.fetchone()[0] == 0:
                pytest.skip("snapshot_t45 not built (python -m pipelines.snapshots.t45)")
        yield c


def scalar(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


# the unit's own episodes: the trajectory episode and, for a merged Plan Comun, its specialty
EPS = "IN (s.episodio_id, s.episodio_especialidad_id)"


def test_cuts_splits_and_outcome_vocabulary(conn):
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t45 WHERE k NOT IN (2, 4)") == 0
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t45 WHERE split <> CASE
        WHEN cohorte_anio <= 2019 THEN 'train' WHEN cohorte_anio <= 2021 THEN 'valid'
        WHEN cohorte_anio <= 2023 THEN 'test' ELSE 'posterior' END""") == 0
    assert scalar(conn, "SELECT min(cohorte_anio) FROM neural_mart.snapshot_t45") >= 2015
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t45 WHERE (otra_salida_tipo IS NOT NULL) "
                        "<> (resultado = 'otra_salida')") == 0


def test_censoring_is_exactly_an_unclosed_horizon(conn):
    cierre = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t45_resumen WHERE clave = 'periodo_cierre'")
    latest = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t45_resumen WHERE clave = 'periodo_maximo'")
    assert cierre < latest
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t45 WHERE seguimiento_max <> {slot(repr(cierre), 'periodo_admision')}") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t45 WHERE (resultado = 'censurado') <> (seguimiento_max < k + 2)") == 0


def test_every_row_was_enrolled_at_the_cut(conn):
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t45 s
        WHERE s.episodio_id % 7 = 0 AND NOT EXISTS (
            SELECT 1 FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
            WHERE e.episodio_id {EPS} AND d.clase_estado = 'matricula' AND NOT e.es_correccion_sistema
              AND e.periodo ~ '^[0-9]{{4}}(10|20)$' AND {slot('e.periodo', 's.periodo_admision')} = s.k)""") == 0


def test_a_transition_already_started_at_the_cut_is_never_a_row(conn):
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t45 s JOIN neural_mart.programa_traslados t
        ON t.origen_episodio_id {EPS} WHERE t.tipo IN {TIPOS}
          AND {slot('t.primer_periodo_destino', 's.periodo_admision')} <= s.k""") == 0


def test_every_transition_row_has_a_real_transfer_in_the_horizon(conn):
    """T4 label => a non-ambiguous transfer of a leaving type whose exit from the origin (P71) is in (k, k + 2]."""
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t45 s
        WHERE s.resultado = 'transicion' AND NOT EXISTS (
            SELECT 1 FROM neural_mart.programa_traslados t WHERE t.origen_episodio_id {EPS} AND t.tipo IN {TIPOS}
              AND NOT t.ambiguo AND {slot('t.ultimo_periodo_origen', 's.periodo_admision')} BETWEEN s.k + 1 AND s.k + 2)""") == 0


def test_a_specialty_election_never_makes_a_transition(conn):
    """The Plan Comun -> specialty election is expected progression: a merged trajectory is a T4 event only through a
    transfer of a leaving type, never through its election."""
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t45 s
        WHERE s.resultado = 'transicion' AND NOT EXISTS (
            SELECT 1 FROM neural_mart.programa_traslados t WHERE t.origen_episodio_id {EPS}
              AND t.tipo IN {TIPOS} AND NOT t.ambiguo)""") == 0
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t45 s
        WHERE s.hubo_transicion_en_horizonte AND NOT EXISTS (
            SELECT 1 FROM neural_mart.programa_traslados t WHERE t.origen_episodio_id {EPS}
              AND t.tipo IN {TIPOS} AND NOT t.ambiguo)""") == 0


def test_transition_outcome_matches_an_independent_recomputation_up_to_precedence(conn):
    """A sample: every certain transfer in the horizon is a 'transicion' unless an earlier or equal event takes precedence."""
    assert scalar(conn, f"""
        WITH m AS (SELECT s.* FROM neural_mart.snapshot_t45 s WHERE s.episodio_id % 5 = 0 AND s.resultado <> 'censurado'),
        tr AS (SELECT m.episodio_id, m.k, min({slot('t.ultimo_periodo_origen', 'm.periodo_admision')}) AS t
               FROM m JOIN neural_mart.programa_traslados t ON t.origen_episodio_id IN (m.episodio_id, m.episodio_especialidad_id)
               WHERE t.tipo IN {TIPOS} AND NOT t.ambiguo GROUP BY 1, 2)
        SELECT count(*) FROM m JOIN tr USING (episodio_id, k)
        WHERE tr.t BETWEEN m.k + 1 AND m.k + 2 AND m.resultado NOT IN ('transicion', 'eliminacion', 'egreso')""") == 0


def test_elimination_matches_an_independent_recomputation(conn):
    """T5 label <=> a state E of the trajectory inside (k, k + 2], unless an egress comes first or ties."""
    base = f"""
        WITH m AS (SELECT s.* FROM neural_mart.snapshot_t45 s WHERE s.episodio_id % 5 = 0 AND s.resultado <> 'censurado'),
        el AS (SELECT m.episodio_id, m.k, min({slot('e.periodo', 'm.periodo_admision')}) AS t
               FROM m JOIN neural_core.evento_estado e ON e.episodio_id = COALESCE(m.episodio_especialidad_id, m.episodio_id)
               WHERE e.cod_estado = 'E' AND NOT e.es_correccion_sistema
                 AND {slot('e.periodo', 'm.periodo_admision')} BETWEEN m.k + 1 AND m.k + 2 GROUP BY 1, 2)
        """
    assert scalar(conn, base + """SELECT count(*) FROM m LEFT JOIN el USING (episodio_id, k)
        WHERE m.resultado = 'eliminacion' AND el.t IS NULL""") == 0
    assert scalar(conn, base + """SELECT count(*) FROM m JOIN el USING (episodio_id, k)
        WHERE m.resultado NOT IN ('eliminacion', 'egreso', 'transicion')""") == 0
    assert scalar(conn, base + """SELECT count(*) FROM m WHERE m.hubo_eliminacion_en_horizonte AND NOT EXISTS (
        SELECT 1 FROM el WHERE el.episodio_id = m.episodio_id AND el.k = m.k)""") == 0


def test_only_the_state_e_is_an_elimination(conn):
    """Exit states that are not E (renuncia, sancion, expulsion, no continuidad...) never produce the T5 label."""
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t45 s
        WHERE s.resultado = 'eliminacion' AND NOT EXISTS (
            SELECT 1 FROM neural_core.evento_estado e WHERE e.episodio_id = COALESCE(s.episodio_especialidad_id, s.episodio_id)
              AND e.cod_estado = 'E' AND NOT e.es_correccion_sistema
              AND {slot('e.periodo', 's.periodo_admision')} BETWEEN s.k + 1 AND s.k + 2)""") == 0


def test_continuity_at_the_horizon_matches_an_independent_recomputation(conn):
    """No event + enrolled in any program of the person at the horizon period = continua; otherwise otra_salida."""
    enrolled = f"""EXISTS (SELECT 1 FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
        WHERE e.persona_key = s.persona_key AND d.clase_estado IN ('matricula', 'reingreso', 'cambio_ciclo')
          AND NOT e.es_correccion_sistema AND e.periodo ~ '^[0-9]{{4}}(10|20)$'
          AND {slot('e.periodo', 's.periodo_admision')} = s.k + 2)"""
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t45 s WHERE s.episodio_id % 3 = 0 "
                        f"AND s.resultado = 'continua' AND NOT {enrolled}") == 0
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t45 s WHERE s.episodio_id % 3 = 0 "
                        f"AND s.resultado = 'otra_salida' AND {enrolled}") == 0


def test_academic_aggregates_match_an_independent_recomputation(conn):
    assert scalar(conn, f"""
        WITH muestra AS (SELECT episodio_id, episodio_especialidad_id, periodo_admision, k, semestres_matriculados,
                                intentos_evaluados
                         FROM neural_mart.snapshot_t45 s WHERE s.episodio_id % 13 = 0),
        h AS (SELECT m.episodio_id, m.k,
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
        SELECT count(*) FROM muestra m JOIN h USING (episodio_id, k) WHERE h.sem <> m.semestres_matriculados OR h.ie <> m.intentos_evaluados""") == 0


def test_features_equal_the_t3_snapshot_of_the_same_rows(conn):
    """T3 and T4/T5 share the construction: the shared columns of the shared rows are identical."""
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM neural_mart.snapshot_t3")
        if cur.fetchone()[0] == 0:
            pytest.skip("snapshot_t3 not built")
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t45 a JOIN neural_mart.snapshot_t3 b USING (episodio_id, k)
        WHERE a.creditos_aprobados IS DISTINCT FROM b.creditos_aprobados OR a.cod_programa IS DISTINCT FROM b.cod_programa
           OR a.duracion_nominal IS DISTINCT FROM b.duracion_nominal
           OR a.semestres_matriculados IS DISTINCT FROM b.semestres_matriculados OR a.pct_mat IS DISTINCT FROM b.pct_mat""") == 0
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t45 a
        WHERE NOT EXISTS (SELECT 1 FROM neural_mart.snapshot_t3 b WHERE b.episodio_id = a.episodio_id AND b.k = a.k)""") == 0


def test_no_sex_in_the_table_and_the_semester_table_covers_the_rows(conn):
    cols = {r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns "
                                       "WHERE table_schema = 'neural_mart' AND table_name = 'snapshot_t45'")}
    assert "sexo" not in cols and "sexo_equidad" in cols
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t45 s WHERE NOT EXISTS (
        SELECT 1 FROM neural_mart.snapshot_t45_semestre t WHERE t.episodio_id = s.episodio_id AND t.j = s.k)""") == 0
