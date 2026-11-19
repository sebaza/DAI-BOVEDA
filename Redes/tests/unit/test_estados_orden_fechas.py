from datetime import date

import pytest

from pipelines.normalize.fechas import impute_dates, usable_date
from pipelines.normalize.models import EstadoRow
from pipelines.normalize.states import ESTADOS, canonical_order, classify_estado

CORTE = date(2026, 11, 11)


def E(sorlcur, periodo, cod_estado="M", fecha=None, prog="P1", adm="LS", pa="202010"):
    return EstadoRow(sorlcur, periodo, prog, cod_estado, adm, pa, "2020", fecha)


# ---- dictionary -------------------------------------------------------------
def test_dictionary_has_the_33_codes_of_r01():
    assert len(ESTADOS) == 33


def test_classes_follow_the_approved_grouping():
    assert classify_estado("M").clase_estado == "matricula"
    assert classify_estado("P").clase_estado == "interrupcion"
    assert classify_estado("E").clase_estado == "salida"
    assert classify_estado("I").clase_estado == "reingreso"
    assert classify_estado("D").clase_estado == "cambio_ciclo"
    assert classify_estado("U").clase_estado == "egreso_titulacion"
    assert classify_estado("T").clase_estado == "otro"


@pytest.mark.parametrize("code", ["1", "2", "5"])
def test_m_reversal_codes_are_flagged_system_corrections(code):
    info = classify_estado(code)
    assert info.es_correccion_sistema is True and info.clase_estado == "correccion_sistema"


def test_m_other_codes_are_not_corrections():
    assert not any(classify_estado(c).es_correccion_sistema for c in ESTADOS if c not in "125")


def test_m_unknown_code_is_kept_without_error():
    info = classify_estado("?")
    assert info.conocido is False and info.cod_estado == "?" and info.clase_estado == "otro"
    assert info.es_correccion_sistema is False


@pytest.mark.parametrize("raw", [None, "", "  "])
def test_m_null_code_is_kept_with_sin_codigo_mark(raw):
    info = classify_estado(raw)
    assert info.sin_codigo is True and info.cod_estado is None and info.clase_estado == "otro"


# ---- canonical order (f)(i)(j) ----------------------------------------------
def test_i_order_is_periodo_then_sorlcur_and_both_are_kept():
    rows = [E(10, "202020"), E(11, "201920"), E(12, "202020"), E(13, "201910")]
    ordered = canonical_order(rows)
    assert [r.sorlcur for r in ordered] == [13, 11, 10, 12]
    assert [(r.sorlcur, r.periodo) for r in ordered][0] == (13, "201910")


def test_j_sorlcur_gaps_give_three_events_not_forty():
    rows = [E(40, "202110"), E(3, "202010"), E(7, "202020")]
    ordered = canonical_order(rows)
    assert len(ordered) == 3
    assert [r.sorlcur for r in ordered] == [3, 7, 40]


def test_duplicate_sorlcur_is_rejected_loudly():
    with pytest.raises(ValueError):
        canonical_order([E(1, "202010"), E(1, "202020")])


# ---- dates (h)(k)(l) --------------------------------------------------------
def test_k_null_between_two_dated_states_gets_neighbour_interval():
    rows = canonical_order(
        [E(1, "202010", fecha=date(2020, 3, 1)), E(2, "202020"), E(3, "202110", fecha=date(2021, 3, 1))]
    )
    infos = impute_dates(rows, CORTE)
    mid = infos[1]
    assert mid.fecha_estado is None
    assert (mid.fecha_min, mid.fecha_max) == (date(2020, 3, 1), date(2021, 3, 1))
    assert mid.fecha_aproximada is True and mid.sin_intervalo is False
    assert infos[0].fecha_aproximada is False and infos[0].fecha_min == infos[0].fecha_max == date(2020, 3, 1)


def test_k_inverted_interval_has_no_interval():
    rows = canonical_order(
        [E(1, "202010", fecha=date(2021, 3, 1)), E(2, "202020"), E(3, "202110", fecha=date(2020, 3, 1))]
    )
    mid = impute_dates(rows, CORTE)[1]
    assert mid.sin_intervalo is True and mid.intervalo_invertido is True
    assert mid.fecha_min is None and mid.fecha_max is None and mid.fecha_estado is None


def test_k_no_neighbours_means_no_interval():
    infos = impute_dates(canonical_order([E(1, "202010"), E(2, "202020")]), CORTE)
    assert all(i.sin_intervalo and i.fecha_min is None and i.fecha_max is None for i in infos)


def test_k_one_sided_interval_is_open():
    rows = canonical_order([E(1, "202010", fecha=date(2020, 3, 1)), E(2, "202020")])
    last = impute_dates(rows, CORTE)[1]
    assert (last.fecha_min, last.fecha_max) == (date(2020, 3, 1), None)
    assert last.sin_intervalo is False and last.fecha_aproximada is True
    rows = canonical_order([E(1, "202010"), E(2, "202020", fecha=date(2020, 9, 1))])
    first = impute_dates(rows, CORTE)[0]
    assert (first.fecha_min, first.fecha_max) == (None, date(2020, 9, 1))


def test_h_null_dates_never_create_events_or_future_dates():
    rows = canonical_order([E(1, "202010"), E(2, "202020"), E(3, "202110")])
    infos = impute_dates(rows, CORTE)
    assert len(infos) == len(rows)
    assert all(i.fecha_estado is None and i.fecha_marcador is False for i in infos)
    assert all(usable_date(i) is None for i in infos)


def test_l_future_date_is_a_marker_and_not_a_neighbour_or_anchor():
    rows = canonical_order(
        [
            E(1, "202010", fecha=date(2020, 3, 1)),
            E(2, "202020"),
            E(3, "202110", cod_estado="B", fecha=date(2026, 12, 31)),
        ]
    )
    infos = impute_dates(rows, CORTE)
    marker = infos[2]
    assert marker.fecha_marcador is True and marker.fecha_estado == date(2026, 12, 31)
    assert usable_date(marker) is None
    assert infos[1].fecha_max is None  # the marker did not become the interval end
    assert infos[1].fecha_min == date(2020, 3, 1)


def test_date_equal_to_cutoff_is_not_future():
    rows = canonical_order([E(1, "202010", fecha=CORTE)])
    info = impute_dates(rows, CORTE)[0]
    assert info.fecha_marcador is False and usable_date(info) == CORTE
