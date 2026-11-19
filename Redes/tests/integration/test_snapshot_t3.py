"""Invariants of the built ``neural_mart.snapshot_t3`` and an independent SQL recomputation of labels and features
(read only). Skipped without DEV_* or an empty snapshot."""
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


def slot(p, a):
    return SLOT.format(p=p, a=a)


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM neural_mart.snapshot_t3")
            if cur.fetchone()[0] == 0:
                pytest.skip("snapshot_t3 not built (python -m pipelines.snapshots.t3)")
        yield c


def scalar(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def test_times_are_after_the_cut_inside_the_follow_up_and_the_window(conn):
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t3 WHERE tiempo <= k OR tiempo > seguimiento_max "
                        "OR tiempo > 20") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t3 WHERE causa = 0 "
                        "AND tiempo <> least(seguimiento_max, 20)") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t3 WHERE (causa = 2) <> (salida_tipo IS NOT NULL)") == 0


def test_follow_up_is_the_closed_period_minus_the_admission_semester(conn):
    cierre = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t3_resumen WHERE clave = 'periodo_cierre'")
    latest = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t3_resumen WHERE clave = 'periodo_maximo'")
    assert cierre < latest                                               # the latest period is still in progress
    assert cierre.isdigit() and len(cierre) == 6
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t3 WHERE seguimiento_max <> {slot(repr(cierre), 'periodo_admision')}") == 0


def test_splits_follow_the_admission_cohort(conn):
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t3 WHERE split <> CASE
        WHEN cohorte_anio <= 2017 THEN 'train' WHEN cohorte_anio = 2018 THEN 'valid'
        WHEN cohorte_anio <= 2020 THEN 'test' ELSE 'posterior' END""") == 0
    assert scalar(conn, "SELECT min(cohorte_anio) FROM neural_mart.snapshot_t3") >= 2015


def test_every_row_was_enrolled_at_the_cut_and_not_graduated_before_it(conn):
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t3 s
        WHERE NOT EXISTS (SELECT 1 FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
                          WHERE e.episodio_id IN (s.episodio_id, s.episodio_especialidad_id) AND d.clase_estado IN ('matricula')
                            AND e.periodo ~ '^[0-9]{{4}}(10|20)$' AND {slot('e.periodo', 's.periodo_admision')} = greatest(s.k, 1))
        AND s.episodio_id % 7 = 0""") == 0
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t3 s
        WHERE s.k >= 1 AND EXISTS (SELECT 1 FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
                          WHERE e.episodio_id = COALESCE(s.episodio_especialidad_id, s.episodio_id)
                            AND d.clase_estado = 'egreso_titulacion'
                            AND {slot('e.periodo', 's.periodo_admision')} <= s.k)""") == 0


def test_egress_time_matches_an_independent_sql_recomputation(conn):
    """tiempo of an egress row = first slot of an egreso_titulacion state or linked titulacion row."""
    assert scalar(conn, f"""
        WITH muestra AS (SELECT episodio_id, episodio_especialidad_id, periodo_admision, tiempo FROM neural_mart.snapshot_t3
                         WHERE k = 2 AND causa = 1 AND (episodio_id % 11 = 0 OR episodio_especialidad_id IS NOT NULL)),
        est AS (SELECT m.episodio_id, min({slot('e.periodo', 'm.periodo_admision')}) AS t
                FROM muestra m JOIN neural_core.evento_estado e ON e.episodio_id = COALESCE(m.episodio_especialidad_id, m.episodio_id)
                JOIN neural_meta.dic_estado d USING (cod_estado)
                WHERE d.clase_estado = 'egreso_titulacion' AND NOT e.es_correccion_sistema GROUP BY 1),
        tit AS (SELECT m.episodio_id, min({slot("(CASE WHEN extract(month FROM t.fecha_titulacion) <= 2 THEN (extract(year FROM t.fecha_titulacion) - 1)::text || '20' WHEN extract(month FROM t.fecha_titulacion) <= 7 THEN extract(year FROM t.fecha_titulacion)::text || '10' ELSE extract(year FROM t.fecha_titulacion)::text || '20' END)", 'm.periodo_admision')}) AS t
                FROM muestra m JOIN neural_core.titulacion t ON t.episodio_id = COALESCE(m.episodio_especialidad_id, m.episodio_id) GROUP BY 1)
        SELECT count(*) FROM muestra m LEFT JOIN est USING (episodio_id) LEFT JOIN tit USING (episodio_id)
        WHERE m.tiempo <> least(est.t, tit.t)""") == 0


def test_explicit_exit_has_no_enrolled_state_after_it_and_censored_rows_have_no_observed_event(conn):
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t3 s
        WHERE s.causa = 2 AND s.salida_tipo = 'explicita' AND EXISTS (
            SELECT 1 FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
            WHERE e.episodio_id IN (s.episodio_id, s.episodio_especialidad_id) AND d.clase_estado = 'matricula'
              AND e.periodo ~ '^[0-9]{{4}}(10|20)$' AND {slot('e.periodo', 's.periodo_admision')} > s.tiempo)""") == 0
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t3 s
        WHERE s.causa = 0 AND EXISTS (
            SELECT 1 FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
            WHERE e.episodio_id = COALESCE(s.episodio_especialidad_id, s.episodio_id)
              AND d.clase_estado = 'egreso_titulacion' AND NOT e.es_correccion_sistema
              AND {slot('e.periodo', 's.periodo_admision')} <= s.tiempo)""") == 0


def test_enrolled_semesters_and_attempts_match_an_independent_recomputation(conn):
    assert scalar(conn, f"""
        WITH muestra AS (SELECT episodio_id, episodio_especialidad_id, periodo_admision, k, semestres_matriculados,
                                intentos_evaluados
                         FROM neural_mart.snapshot_t3 WHERE k IN (2, 4)
                           AND (episodio_id % 13 = 0 OR (episodio_especialidad_id IS NOT NULL AND episodio_id % 3 = 0))),
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


def test_no_sex_in_the_table_and_no_missing_malla_flag_inconsistency(conn):
    cols = {r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns "
                                       "WHERE table_schema = 'neural_mart' AND table_name = 'snapshot_t3'")}
    assert "sexo" not in cols and "sexo_equidad" in cols
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t3 WHERE malla_conocida AND creditos_malla_total IS NULL") == 0


# ---------------------------------------------------------------------------------------------
# D47: exchange programs out, Ingenieria Civil Plan Comun merged with its specialty
# ---------------------------------------------------------------------------------------------
def _lista(codigos):
    return ", ".join(repr(c) for c in sorted(codigos))


ORD = """(CASE WHEN right({p}, 2) <= '10' THEN left({p}, 4)::int * 2 WHEN right({p}, 2) <= '20' THEN left({p}, 4)::int * 2 + 1
          ELSE (left({p}, 4)::int + 1) * 2 END)"""


def ordinal(p):
    return ORD.format(p=p)


FACTS = """WITH f AS (SELECT episodio_id, min(periodo) AS pmin, max(periodo) AS pmax FROM neural_core.evento_estado
                   WHERE NOT es_correccion_sistema AND episodio_id IS NOT NULL GROUP BY 1)"""


def test_pinned_program_codes_match_the_program_names(conn):
    from pipelines.snapshots import rules_t3 as R3

    def codigos(where):
        return {r[0] for r in conn.execute(f"SELECT cod_programa FROM neural_core.programa WHERE {where}")}

    assert codigos("nombre_programa ILIKE '%INTERCAMBIO%'") == set(R3.PROGRAMAS_INTERCAMBIO)
    assert codigos("nombre_programa ILIKE '%PLAN COM%'") == set(R3.PLAN_COMUN_CODIGOS)
    assert codigos("nombre_programa ILIKE 'INGENIER_A CIVIL PLAN COM%'") == set(R3.PLAN_COMUN_ING_CIVIL)
    assert codigos("id_nivel = 1 AND nombre_programa ILIKE 'INGENIER_A CIVIL%' AND nombre_programa NOT ILIKE '%PLAN COM%'") \
        == set(R3.ESPECIALIDADES_ING_CIVIL)


def test_exchange_programs_are_not_in_the_snapshot(conn):
    from pipelines.snapshots import rules_t3 as R3

    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t3 s
        JOIN neural_core.episodio_programa e USING (episodio_id) WHERE e.cod_programa IN ({_lista(R3.PROGRAMAS_INTERCAMBIO)})""") == 0
    assert scalar(conn, "SELECT valor::int FROM neural_mart.snapshot_t3_resumen WHERE clave = 'embudo_k0_intercambio_excluidos'") > 0


def test_a_linked_specialty_is_never_a_separate_unit_and_belongs_to_one_trajectory(conn):
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t3 s
        WHERE s.episodio_id IN (SELECT episodio_especialidad_id FROM neural_mart.snapshot_t3 WHERE episodio_especialidad_id IS NOT NULL)""") == 0
    assert scalar(conn, """SELECT count(*) FROM (SELECT episodio_especialidad_id FROM neural_mart.snapshot_t3
        WHERE episodio_especialidad_id IS NOT NULL GROUP BY 1 HAVING count(DISTINCT episodio_id) > 1) x""") == 0
    assert scalar(conn, """SELECT count(*) FROM (SELECT episodio_id FROM neural_mart.snapshot_t3
        GROUP BY 1 HAVING count(DISTINCT coalesce(episodio_especialidad_id, -1)) > 1) x""") == 0      # the link is per unit
    assert scalar(conn, "SELECT count(DISTINCT episodio_especialidad_id) FROM neural_mart.snapshot_t3") > 300


def test_every_link_satisfies_the_rule_recomputed_in_sql(conn):
    """Same person, Plan Comun -> Ingenieria Civil specialty of level 1, the specialty is the FIRST later one and starts
    at most 2 regular periods after the last Plan Comun period."""
    from pipelines.snapshots import rules_t3 as R3

    assert scalar(conn, FACTS + f"""
        , l AS (SELECT DISTINCT episodio_id AS pc, episodio_especialidad_id AS sp FROM neural_mart.snapshot_t3
                WHERE episodio_especialidad_id IS NOT NULL)
        SELECT count(*) FROM l
        JOIN neural_core.episodio_programa a ON a.episodio_id = l.pc JOIN neural_core.episodio_programa b ON b.episodio_id = l.sp
        JOIN neural_core.programa pb ON pb.cod_programa = b.cod_programa
        JOIN f fa ON fa.episodio_id = l.pc JOIN f fb ON fb.episodio_id = l.sp
        WHERE a.persona_key <> b.persona_key OR a.cod_programa NOT IN ({_lista(R3.PLAN_COMUN_ING_CIVIL)})
           OR b.cod_programa NOT IN ({_lista(R3.ESPECIALIDADES_ING_CIVIL)}) OR pb.id_nivel <> 1
           OR {ordinal('fb.pmin')} <= {ordinal('fa.pmin')} OR {ordinal('fb.pmin')} - {ordinal('fa.pmax')} > 2
           OR EXISTS (SELECT 1 FROM neural_core.episodio_programa c JOIN f fc ON fc.episodio_id = c.episodio_id
                      WHERE c.persona_key = a.persona_key AND c.episodio_id <> l.sp
                        AND c.cod_programa IN ({_lista(R3.ESPECIALIDADES_ING_CIVIL)})
                        AND {ordinal('fc.pmin')} > {ordinal('fa.pmin')}
                        AND ({ordinal('fc.pmin')} < {ordinal('fb.pmin')}
                             OR ({ordinal('fc.pmin')} = {ordinal('fb.pmin')} AND c.episodio_id < l.sp)))""") == 0


def test_no_plan_comun_with_a_valid_continuation_was_left_unlinked(conn):
    from pipelines.snapshots import rules_t3 as R3

    assert scalar(conn, FACTS + f"""
        , u AS (SELECT DISTINCT episodio_id FROM neural_mart.snapshot_t3 WHERE episodio_especialidad_id IS NULL
                AND trayectoria_plan_comun),
        linked AS (SELECT DISTINCT episodio_especialidad_id AS sp FROM neural_mart.snapshot_t3 WHERE episodio_especialidad_id IS NOT NULL),
        primero AS (SELECT DISTINCT ON (u.episodio_id) u.episodio_id AS pc, c.episodio_id AS sp, fc.pmin, fa.pmax
                    FROM u JOIN neural_core.episodio_programa a ON a.episodio_id = u.episodio_id JOIN f fa ON fa.episodio_id = a.episodio_id
                    JOIN neural_core.episodio_programa c ON c.persona_key = a.persona_key AND c.cod_programa IN ({_lista(R3.ESPECIALIDADES_ING_CIVIL)})
                    JOIN f fc ON fc.episodio_id = c.episodio_id
                    WHERE {ordinal('fc.pmin')} > {ordinal('fa.pmin')}
                    ORDER BY u.episodio_id, {ordinal('fc.pmin')}, c.episodio_id)
        SELECT count(*) FROM primero p WHERE {ordinal('p.pmin')} - {ordinal('p.pmax')} <= 2 AND p.sp NOT IN (SELECT sp FROM linked)""") == 0


def test_program_in_force_and_flags_follow_the_specialty_start_recomputed_in_sql(conn):
    """The specialty is known at the cut iff its first state is at or before the cut; the program columns follow."""
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t3 WHERE k = 0 AND especialidad_conocida_al_corte") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t3 WHERE especialidad_conocida_al_corte AND episodio_especialidad_id IS NULL") == 0
    assert scalar(conn, FACTS + f"""
        SELECT count(*) FROM neural_mart.snapshot_t3 s JOIN neural_core.episodio_programa b ON b.episodio_id = s.episodio_especialidad_id
        JOIN f fb ON fb.episodio_id = b.episodio_id
        WHERE s.especialidad_conocida_al_corte <> (s.k >= 1 AND {slot('fb.pmin', 's.periodo_admision')} <= s.k)
           OR s.cod_programa <> CASE WHEN s.especialidad_conocida_al_corte THEN b.cod_programa
                                     ELSE (SELECT cod_programa FROM neural_core.episodio_programa WHERE episodio_id = s.episodio_id) END""") == 0
    # an admission fact: every unit admitted to Plan Comun carries the flag, whether or not it has a continuation
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t3 s JOIN neural_core.episodio_programa e USING (episodio_id)
        WHERE s.trayectoria_plan_comun <> (e.cod_programa IN ('8633', '8643'))""") == 0
    # before the specialty is known the program columns are the Plan Comun ones, identical for linked and unlinked units
    assert scalar(conn, """SELECT count(DISTINCT (duracion_nominal, creditos_malla_total, malla_conocida)) FROM neural_mart.snapshot_t3
        WHERE k = 0 AND trayectoria_plan_comun AND cod_programa = '8643' AND malla_conocida""") <= 3


def test_events_of_merged_trajectories_come_from_the_specialty_counted_from_the_plan_comun_admission(conn):
    # an explicit exit of a merged trajectory is a salida state of the SPECIALTY at slot tiempo
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t3 s
        WHERE s.episodio_especialidad_id IS NOT NULL AND s.k = 2 AND s.causa = 2 AND s.salida_tipo = 'explicita'
          AND NOT EXISTS (SELECT 1 FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
                          WHERE e.episodio_id = s.episodio_especialidad_id AND d.clase_estado = 'salida'
                            AND NOT e.es_correccion_sistema AND {slot('e.periodo', 's.periodo_admision')} = s.tiempo)""") == 0
    # the Plan Comun exit is not the exit of the trajectory: some merged rows are still at risk after it
    assert scalar(conn, f"""SELECT count(*) FROM neural_mart.snapshot_t3 s
        WHERE s.episodio_especialidad_id IS NOT NULL AND s.k = 2 AND s.tiempo > 2""") > 100
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t3 WHERE episodio_especialidad_id IS NOT NULL AND k = 2 AND causa = 1") > 0
