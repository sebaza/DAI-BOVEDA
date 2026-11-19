"""Pure rules shared by the mart builder (SQL must agree with these; see integration/test_marts.py)."""
from datetime import date

import pytest

from pipelines.marts import rules as R
from pipelines.marts import sql as S


def test_regular_ordinal_only_for_10_and_20():
    assert R.regular_ordinal("201910") == 2019 * 2
    assert R.regular_ordinal("201920") == 2019 * 2 + 1
    for p in ("201915", "201925", "201901", "201950", "201960", "201911", "201921", None, "2019", "abc"):
        assert R.regular_ordinal(p) is None


def test_semestre_k_counts_regular_periods_since_admission():
    assert R.semestre_k("201910", "201910") == 1
    assert R.semestre_k("201920", "201910") == 2
    assert R.semestre_k("202010", "201910") == 3
    assert R.semestre_k("202020", "201910") == 4
    assert R.semestre_k("202010", "201920") == 2      # an admission in the second semester starts at 20


def test_semestre_k_is_none_for_non_regular_or_before_admission():
    assert R.semestre_k("201915", "201910") is None   # summer course
    assert R.semestre_k("201810", "201910") is None   # before admission
    assert R.semestre_k("202010", None) is None


def test_non_regular_admission_period_maps_to_its_semester():
    assert R.base_ordinal("201901") == 2019 * 2       # 01 sorts with the first semester
    assert R.base_ordinal("201925") == 2019 * 2 + 1
    assert R.semestre_k("201910", "201901") == 1


def test_marts_have_no_size_threshold():
    assert not hasattr(R, "N_MIN") and not hasattr(R, "suprimir")
    assert not any("nmin" in sql for _t, sql in S.BUILD_ORDER)


def test_duracion_anios_rounds_semesters_up():
    assert R.duracion_anios(10) == 5 and R.duracion_anios(9) == 5 and R.duracion_anios(1) == 1
    assert R.duracion_anios(None) is None and R.duracion_anios(0) is None


def test_censoring_requires_the_window_to_end_before_the_latest_period():
    latest = R.regular_ordinal("202620")
    assert R.censurado(R.base_ordinal("201910"), 5, latest) is False    # ends 202320
    assert R.censurado(R.base_ordinal("202210"), 5, latest) is True     # ends 202720
    # a window that ends exactly at the latest (possibly in-progress) period is censored
    assert R.censurado(R.base_ordinal("201710"), 5, R.regular_ordinal("202120")) is True
    assert R.censurado(R.base_ordinal("201710"), 5, R.regular_ordinal("202210")) is False


def test_retention_observability_uses_semester_three():
    latest = R.regular_ordinal("202620")
    assert R.retencion_observable(R.base_ordinal("202410"), latest) is True    # semester 3 = 202510
    assert R.retencion_observable(R.base_ordinal("202510"), latest) is True    # semester 3 = 202610 < latest
    assert R.retencion_observable(R.base_ordinal("202520"), latest) is False   # semester 3 = 202620 = latest


def test_banda_from_percent_rank_gives_five_bands():
    assert R.banda_from_percent_rank(0.0) == 1
    assert R.banda_from_percent_rank(0.19) == 1
    assert R.banda_from_percent_rank(0.2) == 2
    assert R.banda_from_percent_rank(0.79) == 4
    assert R.banda_from_percent_rank(0.8) == 5
    assert R.banda_from_percent_rank(1.0) == 5


def test_bandas_ties_share_a_band_and_singletons_get_the_lowest():
    assert R.bandas([500.0]) == [1]
    assert R.bandas([400, 400, 400, 400, 400]) == [1, 1, 1, 1, 1]
    out = R.bandas([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
    assert out[0] == 1 and out[-1] == 5 and out == sorted(out)
    assert set(out) == {1, 2, 3, 4, 5}


def test_periodo_de_fecha_maps_dates_to_semesters():
    assert R.periodo_de_fecha(date(2021, 12, 15)) == "202120"
    assert R.periodo_de_fecha(date(2022, 1, 20)) == "202120"      # January closes the previous second semester
    assert R.periodo_de_fecha(date(2022, 4, 1)) == "202210"
    assert R.periodo_de_fecha(date(2022, 8, 1)) == "202220"
    assert R.periodo_de_fecha(None) is None
