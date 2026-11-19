from decimal import Decimal

import pytest

from pipelines.normalize.grades import (
    APROBACION_MINIMA,
    approval_rate_by_attempt,
    average_grade,
    classify_historia,
    classify_inscripcion,
    credits_recognized,
    flag_duplicate_renuncias,
    parse_grade_text,
)

D = Decimal


# ---- parsing (RA12, test ae) ------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [("4,0", D("4.0")), ("4.0", D("4.0")), (" 5,5 ", D("5.5")), ("3.9", D("3.9")), ("7", D("7")), ("1,0", D("1.0"))],
)
def test_parse_numeric_comma_or_dot(raw, expected):
    p = parse_grade_text(raw)
    assert p.kind == "numeric" and p.value == expected


def test_parse_dpa_is_case_insensitive_and_has_no_value():
    for raw in ("DPA", " dpa "):
        p = parse_grade_text(raw)
        assert p.kind == "dpa" and p.value is None


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_parse_empty_is_explicit(raw):
    assert parse_grade_text(raw).kind == "empty"


@pytest.mark.parametrize("raw", ["abc", "4,0,1", "4..0", "-1", "8,5", "NP", "4-0", "40"])
def test_parse_invalid_is_explicit_never_silent(raw):
    p = parse_grade_text(raw)
    assert p.kind == "invalid" and p.value is None and p.raw == raw


# ---- historia (a)(b)(c)(d)(af)(ai)(aj) --------------------------------------
def test_a_3_9_fails():
    r = classify_historia("3,9")
    assert (r.resultado_tipo, r.aprobado_curricular, r.es_intento_evaluado) == ("evaluado", False, True)


def test_b_4_0_passes_exactly():
    assert APROBACION_MINIMA == D("4.0")
    r = classify_historia("4.0")
    assert r.aprobado_curricular is True and r.nota_numerica == D("4.0")


def test_c_4_1_passes():
    assert classify_historia("4,1").aprobado_curricular is True


def test_d_dpa_is_curricular_approval_without_grade_or_attempt():
    r = classify_historia("DPA")
    assert r.resultado_tipo == "convalidacion"
    assert r.nota_numerica is None and r.nota_es_heredada is False
    assert r.aprobado_curricular is True and r.es_intento_evaluado is False


def test_af_4_0_with_second_opportunity_still_passes():
    r = classify_historia("4,0", oportunidad=2)
    assert r.aprobado_curricular is True and r.es_intento_evaluado is True


def test_ai_conva_numeric_is_inherited_not_evaluated():
    r = classify_historia("5,5", comentario="CONVA")
    assert r.resultado_tipo == "convalidacion"
    assert r.nota_numerica == D("5.5") and r.nota_es_heredada is True
    assert r.aprobado_curricular is True and r.es_intento_evaluado is False


def test_conva_with_inherited_grade_below_4_is_not_approved():
    r = classify_historia("3,5", comentario="CONVA")
    assert r.resultado_tipo == "convalidacion" and r.aprobado_curricular is False
    assert r.es_intento_evaluado is False


def test_conva_without_numeric_grade_is_unknown_approval():
    r = classify_historia("", comentario="CONVA")
    assert r.resultado_tipo == "convalidacion" and r.aprobado_curricular is None


def test_aj_other_comment_codes_are_normal_rows():
    r = classify_historia("5,0", comentario="CCAT")
    assert r.resultado_tipo == "evaluado" and r.es_intento_evaluado is True
    assert r.comentario_codigo == "CCAT"


def test_invalid_text_is_otro_and_never_evaluated():
    r = classify_historia("XX")
    assert r.resultado_tipo == "otro" and r.nota_numerica is None
    assert r.aprobado_curricular is None and r.es_intento_evaluado is False
    assert r.nota_parse == "invalid"


# ---- inscripciones (t)(v) ---------------------------------------------------
def test_t_conv_iny_approved_numeric_is_convalidation():
    r = classify_inscripcion("5,0", "APROBADA", "CONV/INY")
    assert r.resultado_tipo == "convalidacion" and r.es_intento_evaluado is False
    assert r.aprobado_curricular is True and r.nota_es_heredada is True


def test_t_conv_iny_reprobada_is_not_curricular_approval():
    r = classify_inscripcion("3,0", "REPROBADA", "CONV/INY")
    assert r.resultado_tipo == "convalidacion"
    assert r.aprobado_curricular is False and r.es_intento_evaluado is False


def test_conv_with_dpa_has_no_grade():
    r = classify_inscripcion("DPA", "APROBADA", "CONV/INY")
    assert r.nota_numerica is None and r.nota_es_heredada is False and r.aprobado_curricular is True


def test_v_inscrito_without_aprobacion_is_in_progress():
    r = classify_inscripcion(None, None, "INSCRITO")
    assert r.resultado_tipo == "en_curso" and r.es_intento_evaluado is False
    assert r.aprobado_curricular is None


def test_inscrito_with_result_is_evaluated():
    r = classify_inscripcion("3,5", "REPROBADA", "INSCRITO")
    assert r.resultado_tipo == "evaluado" and r.es_intento_evaluado is True
    assert r.aprobado_curricular is False


def test_renuncia_is_out_of_attempts_even_when_reprobada():
    for estado, aprob in (("RENUNCIADA MANUAL", None), ("RENUNCIADA WF", "REPROBADA")):
        r = classify_inscripcion(None, aprob, estado)
        assert r.resultado_tipo == "renuncia" and r.es_intento_evaluado is False
        assert r.aprobado_curricular is False


def test_label_numeric_mismatch_is_flagged_not_hidden():
    r = classify_inscripcion("5,0", "REPROBADA", "INSCRITO")
    assert r.aprobado_curricular is True and r.aprobacion_discrepa is True


def test_unknown_estado_is_otro():
    r = classify_inscripcion("5,0", "APROBADA", "ALGO NUEVO")
    assert r.resultado_tipo == "otro" and r.es_intento_evaluado is False


# ---- e: DPA does not move averages or rates --------------------------------
def test_e_dpa_does_not_change_mean_or_rate():
    base = [classify_historia(n) for n in ("5,0", "3,0", "4,0")]
    with_dpa = base + [classify_historia("DPA")] * 5 + [classify_historia("5,5", comentario="CONVA")]
    assert average_grade(base) == average_grade(with_dpa) == D("4.0")
    assert approval_rate_by_attempt(base) == approval_rate_by_attempt(with_dpa) == (2, 3)


def test_average_of_nothing_is_none():
    assert average_grade([classify_historia("DPA")]) is None
    assert approval_rate_by_attempt([]) == (0, 0)


# ---- g: equivalent convalidation does not duplicate credits ----------------
def test_g_equivalent_course_counts_credits_once_and_invents_no_grade():
    approved = classify_historia("5,0")
    convalidated = classify_historia("DPA")
    assert convalidated.nota_numerica is None
    items = [
        ("EQ-MAT1", 6, approved.aprobado_curricular),
        ("EQ-MAT1", 6, convalidated.aprobado_curricular),
        ("EQ-FIS1", 5, True),
        ("EQ-QUI1", 4, False),
        ("EQ-NS", 3, None),
    ]
    assert credits_recognized(items) == 11


# ---- w: duplicated renuncias ------------------------------------------------
def test_w_second_renuncia_to_same_course_is_an_anomaly():
    rows = [
        ("p1", "202510", "MAT-00001", "renuncia"),
        ("p1", "202520", "MAT-00001", "renuncia"),
        ("p1", "202520", "FIS-00001", "renuncia"),
        ("p2", "202520", "MAT-00001", "renuncia"),
        ("p1", "202610", "MAT-00001", "evaluado"),
    ]
    assert flag_duplicate_renuncias(rows) == [False, True, False, False, False]


# ---------------------------------------------------------------------------------------------
# P54 (DAI, 13-11-2026): several evaluated rows of one (persona, periodo, asignatura) -> the highest oportunidad wins
# ---------------------------------------------------------------------------------------------
def _fila(grupo, oportunidad, carga=1, fila=0):
    return (grupo, oportunidad, carga, fila)


def test_p54_the_highest_oportunidad_is_the_result_and_the_earlier_rows_are_replaced():
    from pipelines.normalize.grades import flag_replaced_same_period

    rows = [_fila("g", 1, fila=1), _fila("g", 2, fila=2), _fila("g", 3, fila=3)]
    assert flag_replaced_same_period(rows) == [True, True, False]


def test_p54_input_order_does_not_matter_and_groups_are_independent():
    from pipelines.normalize.grades import flag_replaced_same_period

    rows = [_fila("a", 2, fila=1), _fila("b", 1, fila=2), _fila("a", 1, fila=3), _fila("c", 4, fila=4), _fila("c", 5, fila=5)]
    assert flag_replaced_same_period(rows) == [False, False, True, True, False]


def test_p54_a_single_row_is_never_replaced():
    from pipelines.normalize.grades import flag_replaced_same_period

    assert flag_replaced_same_period([_fila("g", 1)]) == [False]
    assert flag_replaced_same_period([]) == []


def test_p54_tie_on_oportunidad_keeps_the_most_recent_load_then_the_latest_row():
    from pipelines.normalize.grades import flag_replaced_same_period

    assert flag_replaced_same_period([_fila("g", 2, carga=1, fila=9), _fila("g", 2, carga=2, fila=1)]) == [True, False]
    assert flag_replaced_same_period([_fila("g", 2, carga=1, fila=1), _fila("g", 2, carga=1, fila=2)]) == [True, False]


def test_p54_a_missing_oportunidad_loses_against_any_number():
    from pipelines.normalize.grades import flag_replaced_same_period

    assert flag_replaced_same_period([_fila("g", None, fila=2), _fila("g", 1, fila=1)]) == [True, False]
