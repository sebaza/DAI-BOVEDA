"""build_core against stg-shaped tables in schema ``neural_test`` loaded with the synthetic histories.

The stg and core DDL of sql/core is replayed with both schemas mapped to ``neural_test`` (their table names do
not collide). The dictionaries are read from the real ``neural_meta`` (read only). Skipped without DEV_*.
"""
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pipelines.common.pseudo import docente_key, persona_key
from pipelines.migrate import split_statements
from pipelines.normalize import build_core as bc
from tests.fixtures import synthetic_histories as H

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(k) for k in ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")),
        reason="DEV_* environment variables not set",
    ),
]

SECRET = "t" * 64
SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "core"
T = "neural_test"
PK_I, PK_II, PK_III = (persona_key(r, SECRET) for r in (H.RUT_I, H.RUT_II, H.RUT_III))
PK_POST = persona_key("44444444-4", SECRET)
PK_P54 = persona_key("66666666-7", SECRET)           # only grade-history rows (P54): no state, so no episode
PK_APPLICANT = persona_key("55555555-5", SECRET)
DOC_A, DOC_B = docente_key("66666666-6", SECRET), docente_key("77777777-7", SECRET)


def _ddl():
    out = []
    for name in ("003_stg.sql", "004_core.sql", "006_stg_malla_programa.sql", "007_asignatura_malla_duplicados.sql",
                 "019_etapa_a_core.sql"):
        text = (SQL_DIR / name).read_text(encoding="utf-8")
        text = text.replace("neural_stg.", f"{T}.").replace("neural_core.", f"{T}.")
        text = re.sub(r"\s+REFERENCES neural_meta\.carga_extraccion \(carga_id\)", "", text)
        # the real dictionaries (neural_meta) are read only here: skip the statements that change them
        out.extend(st for st in split_statements(text) if "neural_meta.calendario_periodo" not in st)
    return out


def _insert(cur, table, rows):
    for row in rows:
        cols = ", ".join(row)
        marks = ", ".join(["%s"] * len(row))
        cur.execute(f"INSERT INTO {T}.{table} ({cols}) VALUES ({marks})", list(row.values()))


def _estado(pk, e, plan=None):
    return {"carga_id": 1, "persona_key": pk, "sorlcur": e.sorlcur, "periodo": e.periodo, "plan_estudios": plan,
            "catalogo": e.catalogo, "cod_admision": e.cod_admision, "periodo_admision": e.periodo_admision,
            "cod_programa": e.cod_programa, "cod_estado": e.cod_estado,
            "fecha_estado": datetime.combine(e.fecha_estado, datetime.min.time()) if e.fecha_estado else None,
            "sexo": "F" if pk == PK_I else "M"}


def _nota(pk, n):
    return {"carga_id": 1, "persona_key": pk, "periodo": n.periodo, "cod_carrera": n.cod_carrera,
            "catalogo": n.catalogo, "materia": n.materia, "curso": n.curso, "titulo": f"{n.materia} {n.curso}",
            "nota": n.nota, "creditos": n.creditos, "oportunidad": n.oportunidad, "nrc": n.nrc,
            "comentario": n.comentario or None}


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        c.autocommit = True
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")
        c.execute(f"CREATE SCHEMA {T}")
        for stmt in _ddl():
            c.execute(stmt)
        with c.cursor() as cur:
            _load(cur)
        yield c
        c.execute(f"DROP SCHEMA IF EXISTS {T} CASCADE")


def _load(cur):
    _insert(cur, "ban_estados_academicos",
            [_estado(PK_I, e) for e in H.HISTORY_I_ESTADOS] + [_estado(PK_II, e) for e in H.HISTORY_II_ESTADOS]
            + [_estado(PK_III, e) for e in H.HISTORY_III_ESTADOS])
    _insert(cur, "ban_historia_notas",
            [_nota(PK_I, n) for n in H.HISTORY_I_NOTAS] + [_nota(PK_II, n) for n in H.HISTORY_II_NOTAS]
            + [_nota(PK_III, n) for n in H.HISTORY_III_NOTAS] + [_nota(PK_P54, n) for n in H.HISTORY_P54_NOTAS])
    _insert(cur, "programa_d", [
        {"carga_id": 1, "id": 1, "cod_banner": "C101", "valid_program": True, "nombre_programa": "P1", "facultad": 7},
        {"carga_id": 1, "id": 2, "cod_banner": "C201", "valid_program": True, "nombre_programa": "P2"},
        {"carga_id": 1, "id": 5, "cod_banner": "C999", "valid_program": False, "programa_predecesor": 99},
    ])
    mal = lambda prog, cat, mc, sem, nombre: {  # noqa: E731
        "carga_id": 1, "malla_program_code": prog, "malla_ctlg": cat, "malla_materiacurso": mc,
        "malla_semestre": sem, "malla_formacion": "F", "malla_creditaje": "6", "malla_asignatura": nombre,
        "malla_area": "A", "malla_depto": "D", "malla_depto_desc": "Depto"}
    _insert(cur, "ban_malla_programa", [
        mal("C101", "2019", "MAT-00001", "Semestre 01 CB", "ALGEBRA"),
        mal("C101", "2019", "MAT-00001", "Semestre 02 CB", "ALGEBRA"),          # duplicate that disagrees
        mal("C101", "2019", "MAT-00002", "Semestre 03 CB", "CALCULO"),
        mal("C101", "2019", "PRAC-04001", "Semestre 10 CP", "PRACTICA PROFESIONAL"),
        mal("C201", "2018", "QUI-00001", "Año 01 CB", "QUIMICA"),
    ])
    _insert(cur, "banner_catalogos", [{"carga_id": 1, "cod_carrera": "C101", "catalogo": "2019", "duracion": 10}])
    pre = lambda asig, req: {"carga_id": 1, "cod_programa": "1", "catalogo": "2019",  # noqa: E731
                             "codigo_asignatura": asig, "codigo_asignatura_repreq": req}
    _insert(cur, "malla_programa_prereq", [
        pre("MAT-00002", "MAT-00001"), pre("MAT-00002", "MAT-00001"),          # repeated edge
        pre("PRAC-04001", "QUI-00001"),                                       # requirement lives in another program
        pre("PRAC-04001", "ZZZZ-99999"),                                      # requirement in no malla
    ])
    sec = lambda periodo, nrc, doc, tipo: {"carga_id": 1, "periodo": periodo, "nrc": nrc, "paralelo": "1",  # noqa: E731
                                           "carrera": "C101", "sede": "S", "cod_asignatura": "MAT-00001",
                                           "docente_key": doc, "tipo_profesor": tipo}
    _insert(cur, "ban_oferta_academica", [
        sec("201910", "1001", DOC_A, "P"), sec("201910", "1001", DOC_B, "A"), sec("201910", "1001", DOC_A, "P"),
        sec("201920", "1002", None, None),
    ])
    adm = lambda pk, cod, mat, year="201910", **kw: {"carga_id": 1, "persona_key": pk, "year_admision": year,  # noqa: E731
                                                     "cod_carrera": "C101", "cod_admision": cod, "matricula": mat,
                                                     "fecha_matricula": "2019-03-04", "puntaje_nem": "650,5",
                                                     "puntaje_mat": "abc", "sexo": kw.get("sexo", "F"),
                                                     "region_colegio": "Coquimbo"}
    _insert(cur, "banner_admision", [
        adm(PK_I, "LE", "N"), adm(PK_I, "LS", "Y"),                           # regular beats waitlist
        adm(PK_II, "PC", "N"), adm(PK_II, "LS", "N"),                         # special beats regular
        adm(PK_APPLICANT, "LS", "N", sexo="M"),                               # applicant that never enrolled
        adm(None, "LS", "N"),                                                 # no RUT: kept in stg, not in core
    ])
    ins = lambda pk, periodo, nrc, mat, estado, aprob, nota, opor, cat: {  # noqa: E731
        "carga_id": 1, "persona_key": pk, "periodo": periodo, "nrc": nrc, "materia_curso_inscrito": mat,
        "estado": estado, "aprobacion": aprob, "nota": nota, "oportunidad": opor, "materia_curso_catalogo": cat,
        "titulo_catalogo": "T", "catalogo_malla": "2019", "nivel": "PRE", "titulo_inscrito": "TI"}
    _insert(cur, "ban_inscripciones", [
        ins(PK_III, "202510", "5001", "ALG-00001", "INSCRITO", "APROBADA", "5,5", 1, "ALG-00010"),
        ins(PK_III, "202510", "5001", "ALG-00001", "INSCRITO", "APROBADA", "5,5", 1, "ALG-00011"),  # 2 equivalences
        ins(PK_III, "202510", "5002", "FIS-00001", "RENUNCIADA WEB", None, None, 1, "FIS-00001"),
        ins(PK_III, "202520", "5003", "FIS-00001", "RENUNCIADA MANUAL", None, None, 1, "FIS-00001"),  # repeated
        ins(PK_III, "202510", "5004", "QUI-00001", "INSCRITO", None, None, 1, "QUI-00001"),         # in progress
        ins(PK_III, "202510", "5005", "ING-00001", "INSCRITO", "REPROBADA", "3,0", 1, "ING-00001"),
        ins(PK_III, "202510", "5005", "ING-00001", "RENUNCIADA WF", None, None, 1, "ING-00001"),    # estado conflict
        ins(PK_III, "202510", "5006", "CONV-00001", "CONV/INY", "APROBADA", "DPA", 1, "CONV-00001"),
    ])
    _insert(cur, "banner_titulados", [
        {"carga_id": 1, "persona_key": PK_I, "codigo_carrera": "C101", "catalogo": "2019",
         "fecha_titulacion": date(2021, 12, 15), "year_ingreso": 2019, "tipo_admision": "LS"},
        {"carga_id": 1, "persona_key": PK_I, "codigo_carrera": "C101", "catalogo": "2019",       # exact repeat
         "fecha_titulacion": date(2021, 12, 15), "year_ingreso": 2019, "tipo_admision": "LS"},
        {"carga_id": 1, "persona_key": PK_II, "codigo_carrera": "C999", "catalogo": "2005",
         "fecha_titulacion": date(2022, 1, 1)},
    ])
    _insert(cur, "facultad_d", [
        {"carga_id": 1, "id": 7, "cod_unidad_organica": "01012300000000", "nombre_unidad": "Facultad de Economia",
         "nivel_jerarquico": "3", "cod_sede": "1", "nombre_vigente": "FACULTAD DE ECONOMIA"},
        {"carga_id": 1, "id": 8, "cod_unidad_organica": "01012400000000", "nombre_unidad": "Facultad de Humanidades",
         "nivel_jerarquico": "3", "cod_sede": "1", "nombre_vigente": "FACULTAD DE HUMANIDADES"},
    ])
    pos = lambda pk, sorl, periodo, prog, estado, nombre, estandar: {  # noqa: E731
        "carga_id": 1, "persona_key": pk, "sorlcur": sorl, "periodo": periodo, "cod_programa": prog, "cod_estado": estado,
        "nombre_estado": {"M": "Matriculado", "W": "Post-Graduado"}.get(estado), "nombre_banner": nombre,
        "nombre_estandar": estandar, "fecha_estado": datetime(2021, 3, 1)}
    _insert(cur, "ban_estados_academicos_pos", [
        pos(PK_POST, 1, "202150", "6013", "M", "Magister en Arquitectura", "MAGÍSTER EN ARQUITECTURA"),
        pos(PK_POST, 2, "202160", "6013", "M", "Magister en Arquitectura", "MAGÍSTER EN ARQUITECTURA"),
        pos(PK_POST, 3, "202250", "6013", "W", "Magister en Arquitectura", "MAGÍSTER EN ARQUITECTURA"),
        pos(PK_I, 1, "202250", "6889", "M", "Doc En Antropologia", "DOCTORADO EN ANTROPOLOGÍA"),
        pos(PK_I, 2, "202250", "7006", "J", "Post-Titulo Cirugia General", "FORMACIÓN DE ESPECIALISTA EN CIRUGÍA GENERAL"),
        pos(PK_I, 3, "202250", "0033", "M", "Prog. Ficticio Post. Ant.", None),
    ])
    _insert(cur, "banner_estudiantes_postgrado", [
        {"carga_id": 1, "persona_key": PK_POST, "cod_programa": "P900", "periodo": "202510", "cod_estado": "M",
         "estado": "Matriculado", "fecha_estado": date(2025, 3, 1)},
    ])


@pytest.fixture(scope="module")
def built(conn):
    ctx = bc.build(conn, stg_schema=T, core_schema=T, meta_schema="neural_meta", corte=H.CORTE, out=lambda _m: None)
    return ctx


def q(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ---- persona ---------------------------------------------------------------------------------------
def test_persona_covers_trajectory_sources_but_not_applicants(conn, built):
    keys = {r[0] for r in q(conn, f"SELECT persona_key FROM {T}.persona")}
    assert keys == {PK_I, PK_II, PK_III, PK_POST, PK_P54}
    assert PK_APPLICANT not in keys


def test_persona_sexo_from_estados(conn, built):
    sexo = dict(q(conn, f"SELECT persona_key, sexo FROM {T}.persona"))
    assert sexo[PK_I] == "F" and sexo[PK_III] == "M"


def test_persona_sexo_conflict_between_sources_is_flagged_not_guessed(conn, built):
    # PK_II is 'M' in estados and 'F' in admision (default of the helper): a conflict.
    row = q(conn, f"SELECT sexo, sexo_conflicto FROM {T}.persona WHERE persona_key = %s", (PK_II,))[0]
    assert row == (None, True)
    assert q(conn, f"SELECT sexo_conflicto FROM {T}.persona WHERE persona_key = %s", (PK_I,))[0][0] is False


# ---- episodes and states ------------------------------------------------------------------------------
def test_episode_counts_per_person(conn, built):
    counts = dict(q(conn, f"SELECT persona_key, count(*) FROM {T}.episodio_programa GROUP BY 1"))
    assert counts == {PK_I: 1, PK_II: 2, PK_III: 1}


def test_every_state_row_becomes_an_event(conn, built):
    n_stg = q(conn, f"SELECT count(*) FROM {T}.ban_estados_academicos")[0][0]
    assert q(conn, f"SELECT count(*) FROM {T}.evento_estado")[0][0] == n_stg == 27


def test_reversal_is_kept_flagged_and_outside_every_episode(conn, built):
    row = q(conn, f"SELECT es_correccion_sistema, episodio_id, tramo_n FROM {T}.evento_estado "
                  f"WHERE persona_key = %s AND cod_estado = '2'", (PK_II,))[0]
    assert row == (True, None, None)


def test_canonical_order_is_periodo_then_sorlcur(conn, built):
    rows = q(conn, f"SELECT sorlcur, orden_canonico FROM {T}.evento_estado WHERE persona_key = %s", (PK_II,))
    order = dict(rows)
    assert order[22] < order[21]          # period 202115 sorts before 202120 although sorlcur is larger
    assert sorted(order.values()) == list(range(1, 12))


def test_null_date_gets_the_neighbour_interval(conn, built):
    row = q(conn, f"SELECT fecha_estado_original, fecha_min, fecha_max, fecha_aproximada, sin_intervalo "
                  f"FROM {T}.evento_estado WHERE persona_key = %s AND sorlcur = 11", (PK_II,))[0]
    assert row == (None, date(2019, 3, 20), date(2020, 3, 9), True, False)


def test_internal_cycle_change_is_not_a_new_episode(conn, built):
    row = q(conn, f"SELECT n_estados, n_tramos, catalogo_inicial, catalogo_final, ultimo_estado_clase "
                  f"FROM {T}.episodio_programa WHERE persona_key = %s", (PK_III,))[0]
    assert row == (8, 1, "2017", "2018", "egreso_titulacion")


def test_program_change_makes_a_second_episode(conn, built):
    rows = q(conn, f"SELECT cod_programa, cod_admision FROM {T}.episodio_programa WHERE persona_key = %s "
                   f"ORDER BY episodio_id", (PK_II,))
    assert rows == [("C201", "LS"), ("C305", "CC")]


# ---- attempts ---------------------------------------------------------------------------------------------
def test_one_attempt_per_history_row(conn, built):
    assert q(conn, f"SELECT count(*) FROM {T}.intento_asignatura")[0][0] == 17 + len(H.HISTORY_P54_NOTAS)


def test_p54_the_highest_oportunidad_is_the_result_and_the_earlier_rows_are_flagged_and_not_evaluated(conn, built):
    rows = q(conn, f"SELECT oportunidad, reemplazada_mismo_periodo, es_intento_evaluado, aprobado_curricular, "
                   f"nota_numerica FROM {T}.intento_asignatura WHERE persona_key = %s AND materia = 'ZZZ' "
                   f"AND periodo = '201910' ORDER BY oportunidad", (PK_P54,))
    assert rows == [(1, True, False, None, Decimal("2.0")), (2, True, False, None, Decimal("5.0")),
                    (3, False, True, False, Decimal("3.0"))]            # the last attempt wins even when it fails
    assert built.notes["intento_grupos_con_varias_filas_evaluadas"] == 1
    assert built.notes["intento_reemplazados_mismo_periodo"] == 2


def test_p54_single_rows_conva_and_dpa_are_never_replaced(conn, built):
    assert q(conn, f"SELECT count(*) FROM {T}.intento_asignatura WHERE reemplazada_mismo_periodo")[0][0] == 2
    assert q(conn, f"SELECT count(*) FROM {T}.intento_asignatura WHERE resultado_tipo <> 'evaluado' "
                   f"AND reemplazada_mismo_periodo")[0][0] == 0
    assert q(conn, f"SELECT count(*) FROM {T}.intento_asignatura WHERE es_intento_evaluado AND reemplazada_mismo_periodo")[0][0] == 0


# ---- P76 / P77 ----------------------------------------------------------------------------------------------
def test_p76_faculty_names_come_from_the_dictionary_and_reach_the_program(conn, built):
    assert q(conn, f"SELECT facultad_id, nombre_facultad FROM {T}.facultad ORDER BY 1") == [
        (7, "Facultad de Economia"), (8, "Facultad de Humanidades")]
    assert q(conn, f"SELECT p.facultad, f.nombre_facultad FROM {T}.programa p LEFT JOIN {T}.facultad f "
                   f"ON f.facultad_id = p.facultad WHERE p.cod_programa = 'C101'") == [(7, "Facultad de Economia")]
    assert q(conn, f"SELECT f.nombre_facultad FROM {T}.programa p LEFT JOIN {T}.facultad f "
                   f"ON f.facultad_id = p.facultad WHERE p.cod_programa = 'C201'") == [(None,)]


def test_p77_postgrado_states_and_programs_with_a_level_from_the_name(conn, built):
    assert q(conn, f"SELECT count(*) FROM {T}.estado_postgrado")[0][0] == 6
    assert q(conn, f"SELECT cod_programa, nivel_derivado, filas, primer_periodo, ultimo_periodo "
                   f"FROM {T}.programa_postgrado ORDER BY cod_programa") == [
        ("0033", "sin_nombre", 1, "202250", "202250"), ("6013", "magister", 3, "202150", "202250"),
        ("6889", "doctorado", 1, "202250", "202250"), ("7006", "otro", 1, "202250", "202250")]
    assert built.notes["postgrado_programas_sin_nombre_estandar"] == 1


def test_exact_four_passes(conn, built):
    row = q(conn, f"SELECT nota_numerica, aprobado_curricular, es_intento_evaluado FROM {T}.intento_asignatura "
                  f"WHERE persona_key = %s AND materia = 'FIS' AND oportunidad = 2", (PK_I,))[0]
    assert row == (Decimal("4.0"), True, True)


def test_dpa_is_convalidation_not_a_failed_attempt(conn, built):
    row = q(conn, f"SELECT resultado_tipo, nota_numerica, aprobado_curricular, es_intento_evaluado, nota_parse "
                  f"FROM {T}.intento_asignatura WHERE persona_key = %s AND nota_texto = 'DPA' AND periodo = '202110'",
            (PK_II,))[0]
    assert row == ("convalidacion", None, True, False, "dpa")


def test_conva_keeps_the_inherited_grade_but_is_not_evaluated(conn, built):
    row = q(conn, f"SELECT resultado_tipo, nota_numerica, nota_es_heredada, es_intento_evaluado "
                  f"FROM {T}.intento_asignatura WHERE persona_key = %s AND comentario_codigo = 'CONVA'", (PK_III,))[0]
    assert row == ("convalidacion", Decimal("5.5"), True, False)


def test_attempt_episode_assignment(conn, built):
    flags = q(conn, f"SELECT periodo, episodio_id IS NOT NULL, sin_episodio, episodio_ambiguo "
                    f"FROM {T}.intento_asignatura WHERE persona_key = %s ORDER BY periodo, nrc", (PK_II,))
    by_period = {p: (a, s, am) for p, a, s, am in flags}
    assert by_period["201915"] == (True, False, False)      # summer course inside the first episode
    assert by_period["200510"] == (False, True, False)      # program without episode
    assert by_period["202110"] == (True, False, False)


def test_attempt_code_format(conn, built):
    fmt = dict(q(conn, f"SELECT materia, formato_codigo FROM {T}.intento_asignatura"))
    assert fmt["PRAC"] == "AAAA-99999" and fmt["OLD"] == "otro"        # three-letter subject code
    assert q(conn, f"SELECT codigo_asignatura FROM {T}.intento_asignatura WHERE materia = 'MAT' AND curso = '00001' "
                   f"AND persona_key = %s", (PK_I,))[0][0] == "MAT-00001"


# ---- admission ----------------------------------------------------------------------------------------------
def test_postulacion_via_keeps_every_row_with_a_person(conn, built):
    assert q(conn, f"SELECT count(*) FROM {T}.postulacion_via")[0][0] == 5
    assert built.notes["postulacion_via_sin_persona"] == 1


def test_score_parsing_flags_unparseable_text(conn, built):
    row = q(conn, f"SELECT puntaje_nem, puntaje_mat, puntaje_parse_ok, fecha_matricula FROM {T}.postulacion_via "
                  f"WHERE persona_key = %s AND cod_admision = 'LS'", (PK_I,))[0]
    assert row == (Decimal("650.5"), None, False, date(2019, 3, 4))


def test_route_choice_by_priority(conn, built):
    rows = {pk: (adm, mat, any_y, n) for pk, adm, mat, any_y, n in q(
        conn, f"SELECT persona_key, cod_admision_elegida, matricula_elegida, alguna_via_matriculo, n_vias "
              f"FROM {T}.postulacion")}
    assert rows[PK_I] == ("LS", "Y", True, 2)
    assert rows[PK_II] == ("PC", "N", False, 2)


# ---- catalog ------------------------------------------------------------------------------------------------
def test_programa_flags(conn, built):
    rows = {c: (v, p) for c, v, p in q(conn, f"SELECT cod_programa, valid_program, predecesor_inexistente FROM {T}.programa")}
    assert rows == {"C101": (True, False), "C201": (True, False), "C999": (False, True)}


def test_malla_duplicates_are_collapsed_and_flagged(conn, built):
    row = q(conn, f"SELECT semestre, semestre_texto, filas_origen, atributos_conflicto FROM {T}.asignatura_malla "
                  f"WHERE cod_programa = 'C101' AND codigo_asignatura = 'MAT-00001'")[0]
    assert row == (1, "Semestre 01 CB", 2, True)
    annual = q(conn, f"SELECT semestre, semestre_texto FROM {T}.asignatura_malla WHERE codigo_asignatura = 'QUI-00001'")[0]
    assert annual == (None, "Año 01 CB")


def test_milestones_by_name_are_never_validated(conn, built):
    rows = q(conn, f"SELECT codigo_asignatura, tipo_hito, metodo, validado FROM {T}.hito_formativo")
    assert rows == [("PRAC-04001", "practica", "regex_nombre_v1", False)]


def test_prerequisites_are_deduplicated_and_classified_without_dropping_edges(conn, built):
    rows = {(a, r): (n, ae, re_, otro, cl) for a, r, n, ae, re_, otro, cl in q(
        conn, f"SELECT codigo_asignatura, codigo_requisito, filas_origen, asig_en_malla, req_en_malla, "
              f"req_en_otro_programa, clasificacion FROM {T}.prerrequisito")}
    assert rows[("MAT-00002", "MAT-00001")] == (2, True, True, False, "misma_malla")
    assert rows[("PRAC-04001", "QUI-00001")] == (1, True, False, True, "otro_programa")
    assert rows[("PRAC-04001", "ZZZZ-99999")] == (1, True, False, False, "ninguna")
    assert len(rows) == 3


def test_programa_catalogo_covers_malla_pairs(conn, built):
    assert q(conn, f"SELECT cod_programa, catalogo, duracion FROM {T}.programa_catalogo ORDER BY 1") == [
        ("C101", "2019", 10), ("C201", "2018", None)]


# ---- inscriptions ---------------------------------------------------------------------------------------------
def test_inscription_grain_and_equivalences(conn, built):
    parent = q(conn, f"SELECT inscripcion_id, n_equivalencias FROM {T}.inscripcion_asignatura "
                     f"WHERE nrc = '5001'")[0]
    assert parent[1] == 2
    kids = q(conn, f"SELECT materia_curso_catalogo, filas_origen FROM {T}.inscripcion_equivalencia "
                   f"WHERE inscripcion_id = %s ORDER BY 1", (parent[0],))
    assert kids == [("ALG-00010", 1), ("ALG-00011", 1)]
    assert q(conn, f"SELECT count(*) FROM {T}.inscripcion_asignatura")[0][0] == 7


def test_estado_conflict_keeps_both_rows_flagged(conn, built):
    rows = q(conn, f"SELECT estado, estado_conflicto FROM {T}.inscripcion_asignatura WHERE nrc = '5005' ORDER BY estado")
    assert rows == [("INSCRITO", True), ("RENUNCIADA WF", True)]


def test_inscription_results(conn, built):
    res = {nrc: (rt, ap) for nrc, rt, ap in q(
        conn, f"SELECT nrc, resultado_tipo, aprobado_curricular FROM {T}.inscripcion_asignatura "
              f"WHERE estado = 'INSCRITO' OR left(estado, 4) = 'CONV'")}
    assert res["5001"] == ("evaluado", True)
    assert res["5004"] == ("en_curso", None)
    assert res["5005"] == ("evaluado", False)
    assert res["5006"] == ("convalidacion", True)


def test_second_renuncia_to_same_course_is_flagged(conn, built):
    rows = q(conn, f"SELECT nrc, tipo_renuncia, renuncia_repetida FROM {T}.inscripcion_asignatura "
                   f"WHERE es_renuncia AND materia_curso_inscrito = 'FIS-00001' ORDER BY periodo")
    assert rows == [("5002", "WEB", False), ("5003", "MANUAL", True)]


# ---- sections, outcomes ---------------------------------------------------------------------------------------
def test_sections_and_teacher_bridge_do_not_multiply(conn, built):
    assert q(conn, f"SELECT count(*) FROM {T}.seccion")[0][0] == 2
    assert q(conn, f"SELECT count(*) FROM {T}.seccion_docente")[0][0] == 2
    assert {r[0] for r in q(conn, f"SELECT docente_key FROM {T}.seccion_docente")} == {DOC_A, DOC_B}


def test_titulacion_links_the_single_matching_episode(conn, built):
    rows = {(pk, c): eid is not None for pk, c, eid in q(
        conn, f"SELECT persona_key, codigo_carrera, episodio_id FROM {T}.titulacion")}
    assert rows == {(PK_I, "C101"): True, (PK_II, "C999"): False}
    assert built.notes["titulacion_filas_repetidas_en_clave"] == 1


def test_postgrado_rows(conn, built):
    assert q(conn, f"SELECT count(*) FROM {T}.matricula_postgrado")[0][0] == 1


# ---- rebuild -----------------------------------------------------------------------------------------------------
def test_rebuild_is_idempotent(conn, built):
    before = {t: q(conn, f"SELECT count(*) FROM {T}.{t}")[0][0] for t in (
        "persona", "episodio_programa", "evento_estado", "intento_asignatura", "inscripcion_asignatura", "facultad",
        "estado_postgrado", "programa_postgrado",
        "inscripcion_equivalencia", "postulacion_via", "postulacion", "seccion", "titulacion")}
    bc.build(conn, stg_schema=T, core_schema=T, meta_schema="neural_meta", corte=H.CORTE, out=lambda _m: None)
    after = {t: q(conn, f"SELECT count(*) FROM {T}.{t}")[0][0] for t in before}
    assert after == before


def test_partial_rebuild_pulls_in_dependents():
    assert bc.expand_steps(["episodio"]) == ["episodio", "intento", "titulacion"]
    assert bc.expand_steps(["persona"]) == ["persona", "episodio", "intento", "inscripcion", "titulacion", "postgrado"]
    assert bc.expand_steps(["seccion"]) == ["seccion"]
    with pytest.raises(ValueError):
        bc.expand_steps(["nope"])


def test_failure_rolls_everything_back(conn):
    before = q(conn, f"SELECT count(*) FROM {T}.seccion")[0][0]
    assert before == 2
    conn.execute(f"ALTER TABLE {T}.ban_oferta_academica RENAME TO ban_oferta_tmp")
    try:
        with pytest.raises(Exception):
            bc.build(conn, stg_schema=T, core_schema=T, meta_schema="neural_meta", corte=H.CORTE, only=["seccion"],
                     out=lambda _m: None)
    finally:
        conn.execute(f"ALTER TABLE {T}.ban_oferta_tmp RENAME TO ban_oferta_academica")
    assert q(conn, f"SELECT count(*) FROM {T}.seccion")[0][0] == before   # the TRUNCATE was rolled back


def test_core_schema_must_be_allowed(conn):
    with pytest.raises(ValueError):
        bc.build(conn, stg_schema="public", core_schema=T, corte=H.CORTE)
