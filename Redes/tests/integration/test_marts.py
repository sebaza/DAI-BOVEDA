"""neural_mart built from the synthetic histories (plus a few extra people) inside schema ``neural_test``.

Core tables are replayed there exactly as in test_build_core; the mart DDL (migration 009) is replayed with
``neural_mart`` mapped to ``neural_test``. Dictionaries are read from the real ``neural_meta`` (read only).
Skipped without DEV_*.
"""
import os
import re
from datetime import date
from decimal import Decimal

import pytest

from pipelines.common.pseudo import persona_key
from pipelines.marts import build as mb
from pipelines.marts import rules as R
from pipelines.migrate import split_statements
from pipelines.normalize import build_core as bc
from tests.fixtures import synthetic_histories as H
from tests.integration import test_build_core as TB

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(k) for k in ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")),
        reason="DEV_* environment variables not set",
    ),
]

T = TB.T
SECRET = TB.SECRET
PK_I, PK_II, PK_III = TB.PK_I, TB.PK_II, TB.PK_III
PK_X1, PK_X2, PK_LATE, PK_A1, PK_A2 = (persona_key(r, SECRET) for r in (
    "91111111-1", "92222222-2", "88888888-8", "93333333-3", "94444444-4"))
MART_DDL = TB.SQL_DIR / "009_mart.sql"
TRASLADOS_DDL = TB.SQL_DIR / "015_programa_traslados.sql"
NOTAS_DDL = TB.SQL_DIR / "021_etapa_a_marts.sql"
SIN_SUPRESION_DDL = TB.SQL_DIR / "033_sin_supresion.sql"


def _mart_ddl():
    out = []
    for path in (MART_DDL, TRASLADOS_DDL, NOTAS_DDL, SIN_SUPRESION_DDL):
        out += split_statements(path.read_text(encoding="utf-8").replace("neural_mart.", f"{T}."))
    return out


_e, _n = H._e, H._n

def _ruta(n):
    return persona_key(f"95{n:06d}-0", SECRET)


# Transfers between programs (P61). Brand-new program codes so that the cohorts above keep their counts.
PK_ES, PK_CC, PK_OVL, PK_LATE_RE, PK_SAME, PK_GRAD, PK_EXCH, PK_AMB, PK_POST, PK_VIA_ES, PK_CS, PK_OVL_BAJA, PK_OVL_GRAD = (
    _ruta(i) for i in range(1, 14))


def _ep(sorlcur0, prog, adm, pa, cat, periodos, estados=None):
    """States of one episode: ``periodos`` with N + M in the first one and M afterwards, unless ``estados`` is given."""
    out, s = [], sorlcur0
    for i, per in enumerate(periodos):
        cods = [estados[i]] if estados else (["N", "M"] if i == 0 else ["M"])
        for cod in cods:
            out.append(_e(s, per, cod, prog, adm, pa, cat))
            s += 1
    return out


TRASLADOS_ESTADOS = {
    PK_ES: _ep(1, "8643", "LS", "201910", "2019", ["201910", "201920"])
    + _ep(10, "8553", "ES", "202010", "2020", ["202010", "202020"]),
    PK_CC: _ep(1, "T100", "LS", "201910", "2019", ["201910", "201920"]) + _ep(10, "T200", "CC", "202010", "2020", ["202010"]),
    PK_OVL: _ep(1, "T150", "LS", "201910", "2019", ["201910", "201920", "202010"])
    + _ep(10, "T200", "CC", "201920", "2019", ["201920"]),
    PK_LATE_RE: _ep(1, "T150", "LS", "201910", "2019", ["201910"]) + _ep(10, "T200", "CC", "202110", "2021", ["202110"]),
    PK_SAME: _ep(1, "T160", "LS", "201910", "2019", ["201910"]) + _ep(10, "T160", "LS", "202010", "2020", ["202010"]),
    PK_GRAD: _ep(1, "T100", "LS", "201910", "2019", ["201910", "201920", "202010"], ["N", "M", "G"])
    + _ep(10, "T200", "LS", "202020", "2020", ["202020"]),
    PK_EXCH: _ep(1, "0003", "LS", "201910", "2019", ["201910"]) + _ep(10, "T170", "LS", "202010", "2020", ["202010"]),
    PK_AMB: _ep(1, "T100", "LS", "201910", "2019", ["201910"]) + _ep(10, "T200", "LS", "202010", "2020", ["202010"])
    + _ep(20, "T300", "LS", "202010", "2020", ["202010"]),
    PK_POST: _ep(1, "P900", "LS", "201910", "2019", ["201910"]) + _ep(10, "T170", "LS", "202010", "2020", ["202010"]),
    PK_VIA_ES: _ep(1, "8496", "LS", "201910", "2019", ["201910", "201920"])
    + _ep(10, "8403", "ES", "202010", "2020", ["202010"]),
    PK_CS: _ep(1, "T100", "LS", "201910", "2019", ["201910"]) + _ep(10, "T400", "CS", "202010", "2020", ["202010"]),
    # P64: the origin of an overlap ends in a baja (B): an exit of that program, not a transfer
    PK_OVL_BAJA: _ep(1, "T180", "LS", "201910", "2019", ["201910", "201920", "202010"], ["N", "M", "B"])
    + _ep(10, "T200", "CC", "201920", "2019", ["201920"]),
    # P64: a double degree: the origin graduates while the second program is already running (no baja)
    PK_OVL_GRAD: _ep(1, "T190", "LS", "201910", "2019", ["201910", "201920", "202010"], ["N", "M", "G"])
    + _ep(10, "T200", "CC", "201920", "2019", ["201920"]),
}
TRASLADOS_PROGRAMAS = [("8643", 11, 1), ("8553", 12, 1), ("T100", 13, 1), ("T200", 14, 1), ("T300", 15, 1),
                       ("T400", 16, 1), ("T150", 21, 1), ("T180", 24, 1), ("T190", 25, 1), ("T160", 22, 1), ("T170", 23, 1), ("0003", 17, 1), ("P900", 18, 2), ("8496", 19, 1), ("8403", 20, 1)]

EXTRA_ESTADOS = {
    PK_X1: [_e(1, "201910", "N", "C101", "LS", "201910", "2019"), _e(2, "201910", "M", "C101", "LS", "201910", "2019"),
            _e(3, "201920", "M", "C101", "LS", "201910", "2019"), _e(4, "202010", "M", "C101", "LS", "201910", "2019")],
    PK_X2: [_e(1, "201910", "N", "C101", "LS", "201910", "2019"), _e(2, "201910", "M", "C101", "LS", "201910", "2019"),
            _e(3, "201920", "M", "C101", "LS", "201910", "2019"), _e(4, "202010", "E", "C101", "LS", "201910", "2019")],
    # a person present in the latest period (202620) of the data, with a course in progress
    PK_LATE: [_e(1, "202110", "M", "C101", "LS", "202110", "2019"), _e(2, "202510", "M", "C101", "LS", "202110", "2019"),
              _e(3, "202610", "M", "C101", "LS", "202110", "2019"), _e(4, "202620", "M", "C101", "LS", "202110", "2019")],
}
EXTRA_NOTAS = {
    PK_X1: [_n("201910", "C101", "2019", "MAT", "00001", "6,0", nrc="7001"),
            _n("201920", "C101", "2019", "MAT", "00002", "2,0", nrc="7002")],
    PK_X2: [_n("201910", "C101", "2019", "MAT", "00001", "3,0", nrc="7003"),
            _n("201920", "C101", "2019", "MAT", "00001", "4,5", opor="2", nrc="7004")],
}


def _extra_load(cur):
    cur.execute(f"UPDATE {T}.programa_d SET id_nivel = 1")           # the synthetic programs are undergraduate
    TB._insert(cur, "programa_d", [{"carga_id": 1, "id": i, "cod_banner": cod, "valid_program": True,
                                    "nombre_programa": f"P{cod}", "id_nivel": nivel}
                                   for cod, i, nivel in TRASLADOS_PROGRAMAS])
    TB._insert(cur, "ban_estados_academicos",
               [TB._estado(pk, e) for pk, es in {**EXTRA_ESTADOS, **TRASLADOS_ESTADOS}.items() for e in es])
    TB._insert(cur, "ban_historia_notas", [TB._nota(pk, n) for pk, ns in EXTRA_NOTAS.items() for n in ns])
    mal = lambda prog, cat, mc, sem, nombre: {  # noqa: E731
        "carga_id": 1, "malla_program_code": prog, "malla_ctlg": cat, "malla_materiacurso": mc,
        "malla_semestre": sem, "malla_formacion": "F", "malla_creditaje": "6", "malla_asignatura": nombre,
        "malla_area": "A", "malla_depto": "D", "malla_depto_desc": "Depto"}
    TB._insert(cur, "ban_malla_programa", [  # catalog of history III: both its convalidations are in the malla
        mal("C401", "2018", "ALG-00002", "Semestre 02 CB", "ALGEBRA II"),
        mal("C401", "2018", "FIS-00003", "Semestre 03 CB", "FISICA III"),
        mal("C401", "2018", "ZZZ-00009", "Semestre 04 CB", "NUNCA CURSADA"),
    ])
    TB._insert(cur, "programa_d", [{"carga_id": 1, "id": 7, "cod_banner": "C401", "valid_program": True,
                                    "nombre_programa": "P4", "id_nivel": 1}])
    adm = lambda pk, cod, mat, pond: {  # noqa: E731
        "carga_id": 1, "persona_key": pk, "year_admision": "201910", "cod_carrera": "C101", "cod_admision": cod,
        "matricula": mat, "ponderado": pond, "sexo": "M"}
    TB._insert(cur, "banner_admision", [
        adm(PK_I, "LS", "Y", "800,0"), adm(PK_X1, "LS", "Y", "600,0"), adm(PK_X2, "LS", "Y", "500,0"),
        adm(PK_A1, "LS", "N", "900,0"), adm(PK_A2, "LS", "N", "400,0"),
    ])
    TB._insert(cur, "ban_inscripciones", [{
        "carga_id": 1, "persona_key": PK_LATE, "periodo": "202620", "nrc": "9001", "materia_curso_inscrito": "MAT-00002",
        "estado": "INSCRITO", "aprobacion": None, "nota": None, "oportunidad": 1, "materia_curso_catalogo": "MAT-00002",
        "titulo_catalogo": "T", "catalogo_malla": "2019", "nivel": "PRE", "titulo_inscrito": "TI"}])


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        c.autocommit = True
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")
        c.execute(f"CREATE SCHEMA {T}")
        for stmt in TB._ddl() + _mart_ddl():
            c.execute(stmt)
        with c.cursor() as cur:
            TB._load(cur)
            _extra_load(cur)
        bc.build(c, stg_schema=T, core_schema=T, meta_schema="neural_meta", corte=H.CORTE, out=lambda _m: None)
        yield c
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")


_last = {"built": False}


def build_marts(conn):
    if not _last["built"]:
        mb.build(conn, core_schema=T, mart_schema=T, meta_schema="neural_meta", out=lambda _m: None)
        _last["built"] = True
    return conn


@pytest.fixture()
def marts(conn):
    """Marts built for every group size: the tiny synthetic cohorts show their statistics."""
    return build_marts(conn)


def q(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def episodio(conn, pk, prog):
    return q(conn, f"SELECT episodio_id FROM {T}.episodio_programa WHERE persona_key = %s AND cod_programa = %s "
                   f"ORDER BY episodio_id", (pk, prog))[0][0]


# ---- indicador_periodo ----------------------------------------------------------------------------------------
def test_indicators_history_i_period_by_period(conn, marts):
    ep = episodio(conn, PK_I, "C101")
    rows = q(conn, f"SELECT periodo, semestre_k, intentos_evaluados, aprobados_evaluados, reprobados, convalidaciones, "
                   f"creditos_aprobados_curriculares, promedio_periodo, n_notas_promedio, creditos_acumulados, "
                   f"promedio_acumulado, n_notas_acumulado, ramos_aprobados_acumulados FROM {T}.indicador_periodo "
                   f"WHERE episodio_id = %s ORDER BY periodo", (ep,))
    d = Decimal
    assert rows[0] == ("201910", 1, 2, 1, 1, 0, d(6), d("4.550"), 2, d(6), d("4.550"), 2, 1)
    assert rows[1] == ("201920", 2, 1, 1, 0, 0, d(6), d("4.000"), 1, d(12), d("4.367"), 3, 2)   # exact 4.0 passes
    assert rows[2][:2] == ("202010", 3) and rows[2][9:] == (d(18), d("4.300"), 4, 3)
    assert rows[3][:2] == ("202020", 4) and rows[3][9:] == (d(24), d("4.640"), 5, 4)
    assert [r[0] for r in rows[4:]] == ["202110", "202120"]                 # state-only periods keep the totals
    assert rows[4][2] == 0 and rows[4][7] is None and rows[4][9:] == (d(24), d("4.640"), 5, 4)


def test_a_failed_then_passed_course_counts_credits_once(conn, marts):
    ep = episodio(conn, PK_X2, "C101")
    rows = q(conn, f"SELECT periodo, creditos_aprobados_curriculares, creditos_acumulados, ramos_aprobados_acumulados, "
                   f"intentos_evaluados_acumulados, aprobados_evaluados_acumulados FROM {T}.indicador_periodo "
                   f"WHERE episodio_id = %s ORDER BY periodo", (ep,))
    assert rows[0][:2] == ("201910", 0) and rows[0][2:] == (0, 0, 1, 0)
    assert rows[1][:2] == ("201920", 6) and rows[1][2:] == (6, 1, 2, 1)


def test_dpa_and_conva_are_out_of_averages_but_in_progress(conn, marts):
    ep = episodio(conn, PK_III, "C401")
    rows = {r[0]: r for r in q(
        conn, f"SELECT periodo, intentos_evaluados, convalidaciones, creditos_aprobados_curriculares, promedio_periodo, "
              f"n_notas_promedio, promedio_acumulado, n_notas_acumulado, ramos_aprobados_acumulados "
              f"FROM {T}.indicador_periodo WHERE episodio_id = %s", (ep,))}
    r = rows["201810"]          # DPA + CONVA (inherited 5.5)
    assert r[1:3] == (0, 2) and r[3] == 12                       # two convalidations: progress yes
    assert r[4] is None and r[5] == 0                           # but no grade enters the period average
    assert r[6] == Decimal("5.500") and r[7] == 1               # accumulated average only has the 201710 grade
    assert r[8] == 3


def test_semestre_k_matches_the_python_rule(conn, marts):
    rows = q(conn, f"SELECT i.periodo, e.periodo_admision, i.semestre_k, i.periodo_regular FROM {T}.indicador_periodo i "
                   f"JOIN {T}.episodio_programa e USING (episodio_id)")
    assert len(rows) > 30
    for periodo, adm, k, regular in rows:
        assert k == R.semestre_k(periodo, adm), (periodo, adm)
        assert regular == (R.regular_ordinal(periodo) is not None)


def test_non_regular_period_has_no_semestre_k(conn, marts):
    ep = episodio(conn, PK_II, "C201")
    row = q(conn, f"SELECT semestre_k, periodo_regular, intentos_evaluados FROM {T}.indicador_periodo "
                  f"WHERE episodio_id = %s AND periodo = '201915'", (ep,))[0]
    assert row == (None, False, 1)                              # the summer course is kept, without a semester


def test_unassigned_attempts_do_not_enter_any_indicator(conn, marts):
    n_ind = q(conn, f"SELECT coalesce(sum(intentos_evaluados + convalidaciones), 0) FROM {T}.indicador_periodo")[0][0]
    n_att = q(conn, f"SELECT count(*) FROM {T}.intento_asignatura WHERE episodio_id IS NOT NULL AND "
                    f"(es_intento_evaluado OR resultado_tipo = 'convalidacion')")[0][0]
    assert n_ind == n_att


# ---- ficha_episodio ---------------------------------------------------------------------------------------------
def test_ficha_history_i(conn, marts):
    row = q(conn, f"SELECT cod_programa, cod_admision, admision, periodo_admision, primer_periodo, ultimo_periodo, "
                  f"semestres_regulares_cursados, ultimo_cod_estado, ultimo_estado_clase, titulado, egresado, "
                  f"periodo_titulacion, creditos_acumulados, promedio_acumulado, n_notas_acumulado, "
                  f"tasa_aprobacion_intento, intentos_evaluados, aprobados_evaluados, nombre_programa "
                  f"FROM {T}.ficha_episodio WHERE persona_key = %s", (PK_I,))[0]
    assert row == ("C101", "LS", "IRP-Lista de selección", "201910", "201910", "202120", 4, "U", "egreso_titulacion",
                   True, True, "202120", Decimal(24), Decimal("4.640"), 5, Decimal("0.8000"), 5, 4, "P1")


def test_ficha_history_iii_graduated_state_without_titulacion_row(conn, marts):
    row = q(conn, f"SELECT titulado, egresado, ultimo_cod_estado FROM {T}.ficha_episodio WHERE persona_key = %s",
            (PK_III,))[0]
    assert row == (False, True, "G")


def test_ficha_excludes_system_reversals_from_the_last_state(conn, marts):
    # history II first episode ends with M at 202020 after the reversal code '2' at 202010
    row = q(conn, f"SELECT ultimo_cod_estado, semestres_regulares_cursados FROM {T}.ficha_episodio "
                  f"WHERE persona_key = %s AND cod_programa = 'C201'", (PK_II,))[0]
    assert row == ("M", 4)


def test_retention_flag(conn, marts):
    flags = dict(q(conn, f"SELECT persona_key, retencion_1er_anio FROM {T}.ficha_episodio WHERE cod_programa = 'C101'"))
    assert flags[PK_I] is True and flags[PK_X1] is True and flags[PK_X2] is False
    assert flags[PK_LATE] is False        # observable (202210 < latest) and no enrolled state in semester 3


# ---- avance_malla ----------------------------------------------------------------------------------------------------
def _malla(conn, pk, prog):
    ep = episodio(conn, pk, prog)
    return {r[0]: r[1:] for r in q(
        conn, f"SELECT codigo_asignatura, estado_ramo, n_intentos_evaluados, mejor_nota, ultimo_periodo, es_hito, tipo_hito, "
              f"semestre FROM {T}.avance_malla WHERE episodio_id = %s", (ep,))}


def test_malla_states_for_the_catalog_of_the_episode(conn, marts):
    m = _malla(conn, PK_I, "C101")
    assert set(m) == {"MAT-00001", "MAT-00002", "PRAC-04001"}      # FIS is not in the official malla; all were attempted
    assert m["MAT-00001"] == ("aprobada", 1, Decimal("5.2"), "201910", False, None, 1)
    assert m["PRAC-04001"][0] == "aprobada" and m["PRAC-04001"][4:6] == (True, "practica")


def test_malla_failed_pending_and_not_taken(conn, marts):
    m = _malla(conn, PK_X1, "C101")
    assert m["MAT-00001"][0] == "aprobada" and m["MAT-00002"][0] == "reprobada_pendiente"
    assert m["MAT-00002"][1:3] == (1, Decimal("2.0"))
    assert "PRAC-04001" not in m                                   # sparse: not taken -> no row (the API derives it)
    m2 = _malla(conn, PK_X2, "C101")
    assert m2["MAT-00001"][:2] == ("aprobada", 2)                  # two evaluated attempts, best grade 4.5
    assert m2["MAT-00001"][2] == Decimal("4.5")


def test_malla_convalidated_courses(conn, marts):
    m = _malla(conn, PK_III, "C401")
    assert m["ALG-00002"][0] == "convalidada" and m["FIS-00003"][0] == "convalidada"
    assert m["ALG-00002"][1] == 0                                  # no evaluated attempt behind it
    assert "ZZZ-00009" not in m


def test_malla_in_progress_comes_from_the_current_inscription(conn, marts):
    m = _malla(conn, PK_LATE, "C101")
    assert m["MAT-00002"][0] == "en_curso" and "MAT-00001" not in m


def test_the_mart_never_stores_not_taken_rows(conn, marts):
    assert q(conn, f"SELECT count(*) FROM {T}.avance_malla WHERE estado_ramo = 'no_cursada'")[0][0] == 0


def test_episodes_without_a_malla_have_no_nodes(conn, marts):
    ep = episodio(conn, PK_II, "C305")
    assert q(conn, f"SELECT count(*) FROM {T}.avance_malla WHERE episodio_id = %s", (ep,))[0][0] == 0


# ---- cohorts -----------------------------------------------------------------------------------------------------------
def test_cohort_semester_percentiles(conn, marts):
    row = q(conn, f"SELECT n_episodios, n_activos, n_promedio, creditos_p25, creditos_p50, creditos_p75, "
                  f"promedio_p25, promedio_p50, promedio_p75 FROM {T}.cohorte_semestre "
                  f"WHERE cod_programa = 'C101' AND cohorte = '201910' AND semestre_k = 1")[0]
    assert row[:3] == (3, 3, 3)
    assert row[3:6] == (Decimal(3), Decimal(6), Decimal(6))        # credits 0 / 6 / 6
    assert row[6:] == (Decimal("3.775"), Decimal("4.550"), Decimal("5.275"))   # averages 3.0 / 4.55 / 6.0


def test_active_means_an_enrolled_state_in_the_semester(conn, marts):
    rows = dict(q(conn, f"SELECT semestre_k, n_activos FROM {T}.cohorte_semestre "
                        f"WHERE cod_programa = 'C101' AND cohorte = '201910'"))
    assert rows == {1: 3, 2: 3, 3: 2, 4: 1}                         # X2 leaves (E) in 202010; only PK_I reaches k=4


def test_latest_period_is_not_used_in_cohort_statistics(conn, marts):
    ks = {r[0] for r in q(conn, f"SELECT semestre_k FROM {T}.cohorte_semestre WHERE cod_programa = 'C101' "
                                f"AND cohorte = '202110'")}
    assert 10 not in ks and 9 in ks                                 # 202620 would be k=10: still running, excluded


def test_program_level_population_pools_all_cohorts(conn, marts):
    row = q(conn, f"SELECT n_activos FROM {T}.programa_semestre WHERE cod_programa = 'C101' AND semestre_k = 1")[0]
    assert row[0] == 4                                              # 3 from 201910 plus PK_LATE (202110)


def test_groups_below_ten_publish_statistics(conn, marts):
    row = q(conn, f"SELECT n_activos, creditos_p50, promedio_p50 FROM {T}.cohorte_semestre "
                  f"WHERE cod_programa = 'C101' AND cohorte = '201910' AND semestre_k = 1")[0]
    assert row == (3, Decimal(6), Decimal("4.550"))                # a 3-person cohort gets its percentiles
    row = q(conn, f"SELECT n_ingreso, titulados_d, titulados_d1, n_retenidos FROM {T}.cohorte_resultado "
                  f"WHERE cod_programa = 'C101' AND cohorte = '201910'")[0]
    assert row == (3, 1, 1, 2)
    assert q(conn, f"SELECT count(*) FROM {T}.cohorte_semestre WHERE n_episodios < 10 AND creditos_p50 IS NULL "
                   f"AND n_activos > 0")[0][0] == 0


def test_suppression_columns_are_gone(conn, marts):
    cols = {c for (c,) in q(conn, "SELECT column_name FROM information_schema.columns WHERE table_schema = %s", (T,))}
    assert not cols & {"suprimido", "suprimido_promedio", "n_min"}


def test_build_records_the_latest_period(conn, marts):
    assert q(conn, f"SELECT DISTINCT periodo_maximo FROM {T}.mart_construccion") == [("202620",)]


def test_cohort_result_counts_and_censoring(conn, marts):
    row = q(conn, f"SELECT n_ingreso, duracion, duracion_anios, censurado_d, censurado_d1, censurado_d2, titulados_d, "
                  f"titulados_d1, titulados_d2, censurado_retencion, n_retencion_obs, n_retenidos "
                  f"FROM {T}.cohorte_resultado WHERE cod_programa = 'C101' AND cohorte = '201910'")[0]
    assert row == (3, 10, 5, False, False, False, 1, 1, 1, False, 3, 2)


def test_recent_cohort_is_censored_not_zero(conn, marts):
    row = q(conn, f"SELECT censurado_d, censurado_d1, censurado_d2, titulados_d, titulados_d1, titulados_d2 "
                  f"FROM {T}.cohorte_resultado WHERE cod_programa = 'C101' AND cohorte = '202110'")[0]
    assert row == (False, True, True, 0, None, None)               # 5 years ended 202520 < 202620; 6 and 7 not yet


def test_cohort_without_a_known_duration_is_censored_for_every_horizon(conn, marts):
    row = q(conn, f"SELECT duracion, duracion_anios, censurado_d, censurado_d1, censurado_d2, titulados_d "
                  f"FROM {T}.cohorte_resultado WHERE cod_programa = 'C201' AND cohorte = '201810'")[0]
    assert row == (None, None, True, True, True, None)


# ---- postulante_contexto ------------------------------------------------------------------------------------------------
def test_bands_are_quintiles_by_percent_rank_and_match_python(conn, marts):
    expected = dict(zip([800, 600, 500, 900, 400], R.bandas([800, 600, 500, 900, 400])))
    assert expected == {800: 4, 600: 3, 500: 2, 900: 5, 400: 1}
    rows = {b: r for b, *r in q(
        conn, f"SELECT banda_ponderado, n_postulantes, n_matriculados, n_vinculados, n_retencion_obs, "
              f"n_retenidos, censurado_titulacion, duracion_anios, n_titulacion_obs, n_titulados "
              f"FROM {T}.postulante_contexto WHERE cod_carrera = 'C101' AND year_admision = '201910'")}
    assert sorted(rows) == [1, 2, 3, 4, 5]
    assert rows[4] == [1, 1, 1, 1, 1, False, 5, 1, 1]       # PK_I: retained and titulated
    assert rows[2] == [1, 1, 1, 1, 0, False, 5, 1, 0]       # PK_X2: left in 202010
    assert rows[5] == [1, 0, 0, 0, 0, False, 5, 0, 0]              # applicant that never enrolled: true zeros


def test_context_publishes_counts_for_small_groups(conn, marts):
    rows = q(conn, f"SELECT n_vinculados, n_retenidos, n_titulados FROM {T}.postulante_contexto "
                   f"WHERE cod_carrera = 'C101' AND year_admision = '201910' AND banda_ponderado = 4")
    assert rows == [(1, 1, 1)]


# ---- privacy ---------------------------------------------------------------------------------------------------------------
def test_no_mart_column_looks_personal_or_teacher_related(conn, marts):
    mart_tables = [t for (t,) in q(conn, "SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (T,))]
    for t in ("indicador_periodo", "ficha_episodio", "avance_malla", "cohorte_semestre", "programa_semestre",
              "cohorte_resultado", "postulante_contexto", "programa_traslados"):
        assert t in mart_tables
        tcols = [c for (c,) in q(conn, "SELECT column_name FROM information_schema.columns WHERE table_schema = %s "
                                       "AND table_name = %s", (T, t))]
        assert "docente_key" not in tcols and "sexo" not in tcols and "rut" not in tcols
        assert not any(re.search(r"correo|email|telefono|nacimiento", c) for c in tcols)


def test_rebuild_is_idempotent(conn, marts):
    before = {t: q(conn, f"SELECT count(*) FROM {T}.{t}")[0][0] for t in (
        "indicador_periodo", "ficha_episodio", "avance_malla", "cohorte_semestre", "cohorte_resultado")}
    _last["built"] = False
    build_marts(conn)
    after = {t: q(conn, f"SELECT count(*) FROM {T}.{t}")[0][0] for t in before}
    assert after == before


def test_failed_build_leaves_previous_marts_untouched(conn, marts):
    before = q(conn, f"SELECT count(*) FROM {T}.indicador_periodo")[0][0]
    conn.execute(f"ALTER TABLE {T}.postulante_contexto RENAME TO postulante_tmp")
    try:
        with pytest.raises(Exception):
            _last["built"] = False
            build_marts(conn)
    finally:
        conn.execute(f"ALTER TABLE {T}.postulante_tmp RENAME TO postulante_contexto")
        _last["built"] = False
    assert q(conn, f"SELECT count(*) FROM {T}.indicador_periodo")[0][0] == before


def test_mart_schema_must_be_allowed(conn):
    with pytest.raises(mb.MartError):
        mb.build(conn, core_schema=T, mart_schema="public", meta_schema="neural_meta", out=lambda _m: None)


# ---- programa_traslados (P61) -------------------------------------------------------------------------------------
def traslado(conn, pk):
    return q(conn, f"SELECT cod_programa_origen, cod_programa_destino, tipo, regla, cuenta_abandono, ambiguo, "
                   f"brecha_periodos, anio_traslado FROM {T}.programa_traslados WHERE persona_key = %s", (pk,))


def test_specialty_election_links_plan_comun_with_the_d47_rule_and_is_not_a_loss(conn, marts):
    assert traslado(conn, PK_ES) == [("8643", "8553", "eleccion_especialidad", "d47", False, False, 1, 2020)]


def test_a_change_of_degree_counts_as_abandonment_of_the_origin(conn, marts):
    assert traslado(conn, PK_CC) == [("T100", "T200", "cambio_carrera", "ventana", True, False, 1, 2020)]


def test_campus_change_and_es_admission_from_other_plan_comun(conn, marts):
    assert [r[2:5] for r in traslado(conn, PK_CS)] == [("traslado_sede", "ventana", True)]
    assert [r[2:5] for r in traslado(conn, PK_VIA_ES)] == [("eleccion_especialidad", "via_es", False)]


def test_p69_graduates_who_study_something_else_are_not_a_transfer_but_are_noted(conn, marts):
    assert traslado(conn, PK_GRAD) == []
    assert dict(q(conn, f"SELECT clave, valor FROM {T}.programa_traslados_nota"))["continuacion_estudios"] == 1


def test_p64_overlaps_are_not_transfers_and_are_counted_as_notes(conn, marts):
    assert traslado(conn, PK_OVL_BAJA) == [] and traslado(conn, PK_OVL_GRAD) == []
    notas = dict(q(conn, f"SELECT clave, valor FROM {T}.programa_traslados_nota"))
    assert notas["doble_programa"] == 2                  # PK_OVL (still enrolled) and PK_OVL_GRAD (double degree)
    assert notas["superposicion_con_baja"] == 1          # PK_OVL_BAJA
    assert set(notas) == {"continuacion_estudios", "doble_programa", "superposicion_con_baja"}


def test_p64_overlapping_episodes_stay_in_the_populations(conn, marts):
    """Both episodes of a double program keep their own rows in the episode-level marts (nothing is excluded)."""
    for pk in (PK_OVL, PK_OVL_BAJA, PK_OVL_GRAD):
        assert q(conn, f"SELECT count(*) FROM {T}.ficha_episodio WHERE persona_key = %s", (pk,))[0][0] == 2


@pytest.mark.parametrize("nombre", ["PK_OVL", "PK_LATE_RE", "PK_SAME", "PK_EXCH", "PK_POST"])
def test_overlaps_late_reentries_same_program_exchange_and_postgraduate_are_not_transfers(conn, marts, nombre):
    assert traslado(conn, globals()[nombre]) == []


def test_a_third_program_in_the_same_window_makes_the_transfer_ambiguous(conn, marts):
    rows = {r[0]: r for r in traslado(conn, PK_AMB)}
    assert rows["T100"][1] == "T200" and rows["T100"][5] is True       # T300 also starts inside the window
    assert rows["T200"][1] == "T300" and rows["T200"][5] is False      # simultaneous starts chain one after the other


def test_mart_rows_match_the_python_classification(conn, marts):
    from pipelines.marts import rules_traslados as RT

    rows = q(conn, f"SELECT t.tipo, o.cod_programa, d.cod_programa, d.cod_admision, o.ultimo_estado_clase, "
                   f"o.primer_periodo, o.ultimo_periodo, d.primer_periodo, t.cuenta_abandono "
                   f"FROM {T}.programa_traslados t "
                   f"JOIN {T}.episodio_programa o ON o.episodio_id = t.origen_episodio_id "
                   f"JOIN {T}.episodio_programa d ON d.episodio_id = t.destino_episodio_id")
    assert len(rows) >= 6
    for tipo, co, cd, adm, clase, p0, p1, d0, cuenta in rows:
        assert RT.clasificar(co, cd, adm, clase, p0, p1, d0) == tipo
        assert RT.relacion_sin_traslado(co, cd, adm, clase, p0, p1, d0) is None      # a transfer has no relation note
        assert RT.CUENTA_ABANDONO[tipo] == cuenta



def test_each_origin_has_at_most_one_transition_and_no_row_goes_to_the_same_program(conn, marts):
    assert q(conn, f"SELECT count(*) - count(DISTINCT origen_episodio_id) FROM {T}.programa_traslados")[0][0] == 0
    assert q(conn, f"SELECT count(*) FROM {T}.programa_traslados "
                   f"WHERE cod_programa_origen = cod_programa_destino")[0][0] == 0
