"""Pure helpers used by build_core (sex resolution, text parsing, duplicate handling)."""
from datetime import date
from decimal import Decimal

import pytest

from pipelines.normalize.core_helpers import (
    choose_malla_row,
    parse_date_text,
    parse_decimal_text,
    parse_int_text,
    parse_semestre,
    resolve_sexo,
    tipo_renuncia,
)


# ---- sexo (M1): never guessed ------------------------------------------------------------------
def test_sexo_single_value_across_sources():
    assert resolve_sexo({"estados": ["F"], "admision": ["f"]}) == ("F", False)


def test_sexo_vocabularies_of_states_and_admission_agree():
    assert resolve_sexo({"estados": ["MASCULINO"], "admision": ["M"]}) == ("M", False)
    assert resolve_sexo({"estados": ["FEMENINO"], "admision": ["M"]}) == (None, True)
    assert resolve_sexo({"estados": ["FEMENINO"], "admision": ["N"]}) == (None, True)   # unknown labels never merge


def test_sexo_only_one_source():
    assert resolve_sexo({"admision": ["M"]}) == ("M", False)


def test_sexo_conflict_between_sources_is_not_resolved():
    assert resolve_sexo({"estados": ["F"], "admision": ["M"]}) == (None, True)


def test_sexo_conflict_inside_one_source():
    assert resolve_sexo({"estados": ["F", "M"]}) == (None, True)


def test_sexo_missing_or_blank():
    assert resolve_sexo({}) == (None, False)
    assert resolve_sexo({"estados": [None, "  ", ""]}) == (None, False)


# ---- text parsing --------------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [("3", 3), (" 10 ", 10), ("2.0", 2), ("", None), (None, None), ("x", None), ("2.5", None)])
def test_parse_int_text(raw, expected):
    assert parse_int_text(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("12,5", Decimal("12.5")), ("6.0", Decimal("6.0")), (" 4 ", Decimal("4")), ("", None), (None, None), ("abc", None)])
def test_parse_decimal_text(raw, expected):
    assert parse_decimal_text(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2024-03-05", date(2024, 3, 5)),
    ("2024-03-05 10:11:12", date(2024, 3, 5)),
    ("05/03/2024", date(2024, 3, 5)),
    ("20240305", date(2024, 3, 5)),
    ("", None), (None, None), ("32/13/2024", None), ("not a date", None),
])
def test_parse_date_text(raw, expected):
    assert parse_date_text(raw) == expected


# ---- renuncia type -------------------------------------------------------------------------------
def test_tipo_renuncia_from_estado():
    assert tipo_renuncia("RENUNCIADA MANUAL") == "MANUAL"
    assert tipo_renuncia("renunciada web") == "WEB"
    assert tipo_renuncia("INSCRITO") is None
    assert tipo_renuncia(None) is None


# ---- official malla duplicates -------------------------------------------------------------------
def _m(semestre="1", cred="6", formacion="F", nombre="ALGEBRA", area="A", depto="D", dd="Depto"):
    return {"semestre": semestre, "creditos": cred, "formacion": formacion, "nombre": nombre,
            "area": area, "depto": depto, "depto_desc": dd}


def test_malla_identical_duplicates_are_not_a_conflict():
    row, conflict, n = choose_malla_row([_m(), _m()])
    assert n == 2 and conflict is False and row == _m()


def test_malla_conflict_picks_the_lowest_semester_deterministically():
    a, b = _m(semestre="3"), _m(semestre="2", formacion="G")
    row1, conflict1, _ = choose_malla_row([a, b])
    row2, conflict2, _ = choose_malla_row([b, a])
    assert conflict1 and conflict2
    assert row1 == row2 == b


def test_malla_nulls_sort_last():
    a, b = _m(formacion=None), _m(formacion="F")
    row, conflict, _ = choose_malla_row([a, b])
    assert conflict and row["formacion"] == "F"


@pytest.mark.parametrize("raw,expected", [
    ("Semestre 09 CP", 9), ("Semestre 01 CB", 1), ("Semestre 03", 3), ("Año 01 CP", None),
    ("Area 02 CP", None), ("4", 4), ("", None), (None, None)])
def test_parse_semestre(raw, expected):
    assert parse_semestre(raw) == expected
