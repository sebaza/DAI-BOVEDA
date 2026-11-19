from decimal import Decimal

import pytest

from pipelines.normalize.admission import (
    Via,
    derive_postulacion,
    parse_score,
    parse_scores,
    via_priority,
)

ESPECIAL = "2. Ingreso Especial o Directo"
REGULAR = "1. Ingreso Regular o Centralizada"


def V(cod, matricula="N", tq=None):
    default_tq = {"PC": ESPECIAL, "BE": ESPECIAL, "LS": REGULAR, "LE": REGULAR, "RP": REGULAR}
    return Via(cod_admision=cod, matricula=matricula, tipo_qualitas=tq or default_tq.get(cod, "Desconocido"))


# ---- scores (ae) ------------------------------------------------------------
@pytest.mark.parametrize("raw,val", [("650,5", Decimal("650.5")), ("650.5", Decimal("650.5")), (" 700 ", Decimal("700")), ("5,6", Decimal("5.6"))])
def test_ae_score_parses_comma_and_dot(raw, val):
    p = parse_score(raw)
    assert p.status == "ok" and p.value == val


@pytest.mark.parametrize("raw", [None, "", "  "])
def test_ae_empty_score_is_explicit_empty(raw):
    p = parse_score(raw)
    assert p.status == "vacio" and p.value is None


@pytest.mark.parametrize("raw", ["abc", "6,5,1", "-3", "N/A"])
def test_ae_invalid_score_is_null_with_flag(raw):
    p = parse_score(raw)
    assert p.status == "invalido" and p.value is None


def test_parse_scores_reports_overall_ok_flag():
    values, ok = parse_scores({"puntaje_nem": "6,1", "puntaje_leng": "xx", "ponderado": ""})
    assert values == {"puntaje_nem": Decimal("6.1"), "puntaje_leng": None, "ponderado": None}
    assert ok is False
    _, ok2 = parse_scores({"puntaje_nem": "6,1", "ponderado": ""})
    assert ok2 is True


# ---- route priority (al) ----------------------------------------------------
def test_priority_tiers():
    assert via_priority("PC", ESPECIAL) == 1
    assert via_priority("BE", ESPECIAL) == 1
    for cod in ("LS", "RP", "OV", "OA"):
        assert via_priority(cod, REGULAR) == 2
    assert via_priority("LE", REGULAR) == 3
    # DAI 11-11-2026: waitlist routes of special programs are waitlists, even though
    # their tipo_qualitas is class 2 (r3#R02).
    for cod in ("EB", "EC", "EM", "EP"):
        assert via_priority(cod, ESPECIAL) == 3
    assert via_priority("NN", "Desconocido") == 4
    assert via_priority("CC", "3. Otros Ingresos o Cambio de Carrera") == 4


def test_al_special_route_beats_selection_and_waitlist():
    p = derive_postulacion([V("LE"), V("LS"), V("PC")])
    assert p.cod_admision_elegida == "PC" and p.n_vias == 3


def test_al_pace_bea_beats_waitlist():
    assert derive_postulacion([V("LE"), V("BE")]).cod_admision_elegida == "BE"


def test_al_selection_beats_waitlist():
    assert derive_postulacion([V("LE"), V("LS")]).cod_admision_elegida == "LS"


def test_al_priority_tie_prefers_enrolled_row():
    p = derive_postulacion([V("LS", "N"), V("RP", "Y")])
    assert p.cod_admision_elegida == "RP" and p.matricula_elegida == "Y"


def test_al_tie_without_enrollment_signal_is_deterministic():
    a = derive_postulacion([V("RP"), V("LS")])
    b = derive_postulacion([V("LS"), V("RP")])
    assert a.cod_admision_elegida == b.cod_admision_elegida == "LS"


def test_al_alguna_via_matriculo_even_if_chosen_route_is_not_enrolled():
    p = derive_postulacion([V("PC", "N"), V("LE", "Y")])
    assert p.cod_admision_elegida == "PC" and p.matricula_elegida == "N"
    assert p.alguna_via_matriculo is True
    assert derive_postulacion([V("PC", "N"), V("LE", "N")]).alguna_via_matriculo is False


def test_al_single_route_and_empty_input():
    assert derive_postulacion([V("LS", "Y")]).n_vias == 1
    with pytest.raises(ValueError):
        derive_postulacion([])
