"""Leakage diagnostic of the benefits (aggregates only): presence by outcome, in-year leavers and the load history."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from evaluation import diagnostico_beneficios as DB   # noqa: E402


def marco():
    return pd.DataFrame({
        "k": [1] * 6 + [2] * 4,
        "continua": [True, True, True, False, False, False, True, True, False, False],
        "tiene_fila": [1, 1, 0, 1, 0, 0, 1, 1, 1, 0],
        "s1_pos": [1, 1, 0, 1, 0, 0, 1, 1, 1, 0],
        "s2_pos": [1, 1, 0, 0, 0, 0, 1, 1, 0, 0],
    })


def test_presence_by_outcome_reports_rates_and_the_gap_per_k():
    t = DB.presencia_por_resultado(marco(), ["tiene_fila", "s2_pos"], n_min=1)
    k1 = next(r for r in t if r["k"] == 1)
    assert k1["continua"]["n"] == 3 and k1["no_continua"]["n"] == 3
    assert k1["continua"]["tiene_fila"] == pytest.approx(2 / 3) and k1["no_continua"]["tiene_fila"] == pytest.approx(1 / 3)
    assert k1["brecha"]["s2_pos"] == pytest.approx(2 / 3 - 0.0)


def test_small_groups_are_not_published():
    t = DB.presencia_por_resultado(marco(), ["tiene_fila"], n_min=4)
    assert all(r["continua"] is None or r["continua"]["n"] >= 4 for r in t)
    assert next(r for r in t if r["k"] == 1)["continua"] is None


def test_in_year_leavers_compare_stayers_and_leavers_of_the_admission_year():
    d = pd.DataFrame({"matriculado_2": [True] * 4 + [False] * 3, "tiene_fila": [1, 1, 1, 0, 0, 0, 1],
                      "s2_pos": [1, 1, 0, 0, 0, 0, 0]})
    t = DB.salida_en_el_anio(d, ["tiene_fila", "s2_pos"], n_min=3)
    assert t["se_queda"]["n"] == 4 and t["sale"]["n"] == 3
    assert t["se_queda"]["tiene_fila"] == pytest.approx(0.75) and t["sale"]["tiene_fila"] == pytest.approx(1 / 3)
    assert t["brecha"]["tiene_fila"] == pytest.approx(0.75 - 1 / 3)


def test_load_history_measures_late_rows_and_second_semester_zeroing():
    historia = [("2025-04-22", 17000, 11000), ("2025-07-28", 21000, 14600), ("2025-11-10", 22900, 15300),
                ("2026-01-19", 23000, 14900), ("2026-10-19", 23000, 14880)]
    r = DB.historia_de_cargas(historia, corte="2025-07-31", cierre="2025-11-30")
    assert r["filas_final"] == 23000
    assert r["filas_tardias_despues_del_corte"] == pytest.approx(1 - 21000 / 23000)
    assert r["sem2_anulado_despues_del_cierre"] == pytest.approx(1 - 14880 / 15300)
    assert r["filas_en_el_cierre"] == 22900
    assert r["filas_netas_despues_del_cierre"] == pytest.approx(1 - 22900 / 23000)
