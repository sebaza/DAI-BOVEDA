"""Pure rules of the T1 snapshot (docs/08_benchmark_t1.md). No database, no pandas."""
import pytest

from pipelines.snapshots import rules as R


def test_corte_is_the_kth_regular_period_since_admission():
    assert R.corte_periodo("201910", 1) == "201910"
    assert R.corte_periodo("201910", 2) == "201920"
    assert R.corte_periodo("201920", 1) == "201920"
    assert R.corte_periodo("201920", 2) == "202010"
    assert R.corte_periodo("201901", 1) == "201910"      # non-regular admission maps to its semester
    assert R.corte_periodo(None, 1) is None


def test_horizon_is_two_regular_periods_after_the_cutoff():
    assert R.horizonte_periodo("201910") == "202010"
    assert R.horizonte_periodo("201920") == "202020"
    assert R.horizonte_periodo("202520") == "202620"
    assert R.horizonte_periodo("201915") is None          # a cutoff is always a regular period


@pytest.mark.parametrize("k", [1, 2, 3, 4])
@pytest.mark.parametrize("adm", ["201910", "201920", "201901", "202010"])
def test_label_period_is_strictly_after_the_cutoff(adm, k):
    corte = R.corte_periodo(adm, k)
    assert R.horizonte_periodo(corte) > corte


@pytest.mark.parametrize("periodo,adm,j", [
    ("201910", "201910", 1),     # admission semester
    ("201915", "201910", 2),     # winter course goes with the NEXT regular semester (periodo > 201910)
    ("201920", "201910", 2),
    ("201925", "201910", 3),     # summer course goes with the following first semester
    ("202010", "201910", 3),
    ("201901", "201910", 1),     # sorts before the 10 period
    ("201810", "201910", None),  # before admission
    ("201925", "201920", 2),
    ("bad", "201910", None),
])
def test_slot_is_the_ceiling_regular_period(periodo, adm, j):
    assert R.slot_de_periodo(periodo, adm) == j


def test_slot_is_consistent_with_period_order_for_any_cutoff():
    # periodo <= corte(k)  <=>  slot <= k : the property that makes features point in time
    adm = "201910"
    for k in (1, 2, 3):
        corte = R.corte_periodo(adm, k)
        for p in ("201910", "201915", "201920", "201925", "202010", "202015", "202020", "202025", "202110"):
            slot = R.slot_de_periodo(p, adm)
            assert (slot is not None and slot <= k) == (p <= corte)


def test_coverage_second_semesters_before_2015_are_incomplete():
    assert R.periodo_con_cobertura("201010")
    assert R.periodo_con_cobertura("201410")
    assert not R.periodo_con_cobertura("201420")
    assert R.periodo_con_cobertura("201510")
    assert R.periodo_con_cobertura("201520")
    assert not R.periodo_con_cobertura("201915")      # not a regular period
    assert not R.periodo_con_cobertura(None)


def test_sample_status_censoring_has_priority_over_coverage():
    assert R.estado_muestra("202520", "202620", "202620") == "censurada"
    assert R.estado_muestra("202510", "202610", "202620") == "observada"
    assert R.estado_muestra("202610", "202710", "202620") == "censurada"
    assert R.estado_muestra("201220", "201320", "202620") == "sin_cobertura"
    assert R.estado_muestra("201310", "201410", "202620") == "observada"
    assert R.estado_muestra("201420", "201510", "202620") == "sin_cobertura"


@pytest.mark.parametrize("anio,split", [
    (2008, "train"), (2019, "train"), (2020, "valid"), (2021, "valid"),
    (2022, "test"), (2023, "test"), (2024, "posterior"), (2026, "posterior"),
])
def test_split_by_cohort_year(anio, split):
    assert R.split_cohorte(anio) == split


def test_population_filter_excludes_exchange_and_special_plans_and_postgrado():
    assert R.es_poblacion_t1(id_nivel=1, cod_admision="LS")
    assert R.es_poblacion_t1(id_nivel=1, cod_admision="CC")
    for adm in ("IN", "PE", "IE"):
        assert not R.es_poblacion_t1(id_nivel=1, cod_admision=adm)
    assert not R.es_poblacion_t1(id_nivel=8, cod_admision="LS")      # plan especial de titulacion
    assert not R.es_poblacion_t1(id_nivel=None, cod_admision="LS")


def test_via_clase_comes_from_tipo_qualitas():
    assert R.via_clase("1. Ingreso Regular o Centralizada") == "regular"
    assert R.via_clase("2. Ingreso Especial o Directo") == "especial"
    assert R.via_clase("3. Otros Ingresos o Cambio de Carrera") == "otros_cambio"
    assert R.via_clase("Desconocido") == "otra"
    assert R.via_clase(None) == "sin_dato"


def test_school_codes_are_normalized():
    assert R.codigo_colegio("H1-Humanista Científico Diurno") == "H1"
    assert R.codigo_colegio("") is None
    assert R.codigo_colegio(None) is None
    assert R.codigo_dependencia("4-Particular NO subvencionado") == "4"
    assert R.codigo_dependencia("4-Particular No subvencionado") == "4"
    assert R.codigo_dependencia("") is None
