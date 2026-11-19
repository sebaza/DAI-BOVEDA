"""New T2 variables of 18-11-2026 (P117-P127): the student's average in the courses of the same department and the performance of the
previous regular semester. Strict past only (same guard as the rest of the T2 snapshot). No database."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features_t2 as F2   # noqa: E402
from tests.unit.test_snapshot_t2 import (            # noqa: E402
    LATEST, MALLA, PRE, SIN_DOC, VIA, ep, episodios, estados, intentos)

DEPTOS = pd.DataFrame({"codigo_asignatura": ["A", "B", "C", "D"], "cod_depto": ["D1", "D1", "D2", None]})


def construir(ep_, it, deptos=DEPTOS):
    snap, _ = F2.construir_snapshot_t2(ep_, it, estados(), VIA, MALLA, PRE, SIN_DOC, LATEST, deptos=deptos)
    return snap


def fila(snap, persona, periodo, codigo):
    r = snap[(snap["persona_key"] == persona) & (snap["periodo"] == periodo) & (snap["codigo_asignatura"] == codigo)]
    assert len(r) == 1
    return r.iloc[0]


def test_new_columns_exist_and_are_nan_without_a_department_table():
    e = episodios(ep(1, "p1"))
    it = intentos(("p1", 1, "201510", "A", 6.0), ("p1", 1, "201520", "B", 5.0))
    snap, _ = F2.construir_snapshot_t2(e, it, estados(), VIA, MALLA, PRE, SIN_DOC, LATEST)
    assert set(F2.FEATURE_COLS_NUEVAS_T2) <= set(snap.columns)
    assert snap[["prom_depto", "n_depto", "dif_prom_depto"]].isna().all().all()
    assert snap["prom_sem_prev"].notna().any()                                  # the recent performance does not need the table


def test_department_average_uses_only_earlier_attempts_of_the_same_department():
    e = episodios(ep(1, "p1"))
    it = intentos(
        ("p1", 1, "201510", "A", 6.0), ("p1", 1, "201510", "C", 3.0), ("p1", 1, "201510", "B", 2.0),
        ("p1", 1, "201520", "B", 4.0), ("p1", 1, "201520", "C", 5.0),
        ("p1", 1, "201610", "A", 7.0),
    )
    s = construir(e, it)
    primero = fila(s, "p1", "201510", "A")
    assert np.isnan(primero["prom_depto"]) and primero["n_depto"] == 0           # known department, no history
    b = fila(s, "p1", "201520", "B")
    assert b["prom_depto"] == pytest.approx(4.0) and b["n_depto"] == 2          # A=6.0 and B=2.0 of 201510, not the same period
    assert b["dif_prom_depto"] == pytest.approx(4.0 - b["prom_acum"])
    c = fila(s, "p1", "201520", "C")
    assert c["prom_depto"] == pytest.approx(3.0) and c["n_depto"] == 1
    a = fila(s, "p1", "201610", "A")
    assert a["prom_depto"] == pytest.approx((6.0 + 2.0 + 4.0) / 3) and a["n_depto"] == 3


def test_unknown_department_gives_missing_values_and_other_students_do_not_mix():
    e = episodios(ep(1, "p1"), ep(2, "p2"))
    it = intentos(("p1", 1, "201510", "A", 6.0), ("p2", 2, "201510", "A", 2.0), ("p1", 1, "201520", "D", 5.0),
                  ("p2", 2, "201520", "B", 5.0), ("p1", 1, "201520", "B", 5.0))
    s = construir(e, it)
    d = fila(s, "p1", "201520", "D")
    assert np.isnan(d["prom_depto"]) and np.isnan(d["n_depto"])
    assert fila(s, "p1", "201520", "B")["prom_depto"] == pytest.approx(6.0)
    assert fila(s, "p2", "201520", "B")["prom_depto"] == pytest.approx(2.0)


def test_previous_semester_is_the_last_regular_period_with_evaluated_attempts():
    e = episodios(ep(1, "p1"))
    it = intentos(
        ("p1", 1, "201510", "A", 6.0), ("p1", 1, "201510", "B", 2.0),            # 201510: average 4.0, pass rate 0.5
        ("p1", 1, "201515", "C", 1.0),                                           # summer course: not a regular semester
        ("p1", 1, "201610", "A", 5.0),                                           # 201520 had no attempts: previous is 201510
        ("p1", 1, "201620", "B", 5.0),                                           # previous is 201610: average 5.0, pass rate 1.0
    )
    s = construir(e, it)
    assert np.isnan(fila(s, "p1", "201510", "A")["prom_sem_prev"])
    r = fila(s, "p1", "201610", "A")
    assert r["prom_sem_prev"] == pytest.approx(4.0) and r["tasa_sem_prev"] == pytest.approx(0.5)
    r = fila(s, "p1", "201620", "B")
    assert r["prom_sem_prev"] == pytest.approx(5.0) and r["tasa_sem_prev"] == pytest.approx(1.0)


def test_periods_without_recorded_failures_do_not_feed_the_recent_performance():
    e = episodios(ep(1, "p1", adm="201910"))
    it = intentos(("p1", 1, "201910", "A", 5.0), ("p1", 1, "201920", "B", 7.0), ("p1", 1, "202020", "C", 5.0))
    s = construir(e, it)
    r = fila(s, "p1", "202020", "C")
    assert r["prom_sem_prev"] == pytest.approx(5.0)                              # 201920 is skipped (P58), 201910 is the previous


@pytest.mark.parametrize("corte", ["201610", "201620"])
def test_changing_or_deleting_facts_of_period_p_or_later_never_changes_the_new_features(corte):
    e = episodios(ep(1, "p1"))
    it = intentos(
        ("p1", 1, "201510", "A", 6.0), ("p1", 1, "201520", "B", 3.0), ("p1", 1, "201610", "A", 5.0),
        ("p1", 1, "201620", "B", 4.0), ("p1", 1, "201710", "A", 2.0),
    )
    cols = F2.FEATURE_COLS_NUEVAS_T2
    base = fila(construir(e, it), "p1", corte, "A" if corte == "201610" else "B")[cols]
    otro = it.copy()
    m = otro["periodo"] >= corte
    otro.loc[m & (otro["periodo"] != corte), "nota_numerica"] = 7.0
    otro.loc[m & (otro["periodo"] == corte), "nota_numerica"] = 1.0               # even the grade of the attempt itself
    changed = fila(construir(e, otro), "p1", corte, "A" if corte == "201610" else "B")[cols]
    pd.testing.assert_series_equal(base, changed)
    borrado = it.loc[(it["periodo"] < corte) | ((it["periodo"] == corte) & (it["codigo_asignatura"] == ("A" if corte == "201610" else "B")))]
    pd.testing.assert_series_equal(base, fila(construir(e, borrado), "p1", corte, "A" if corte == "201610" else "B")[cols])


def test_new_columns_are_not_label_side_and_the_feature_set_extends_the_best_one():
    from models import t2_data as TD

    assert not ({"y", "banda_nota"} & set(F2.FEATURE_COLS_NUEVAS_T2))
    num, cat = TD.CONJUNTOS["c_nuevas"]
    assert set(F2.FEATURE_COLS_NUEVAS_T2) <= set(num) and set(TD.CONJUNTOS["c"][0]) <= set(num) and cat == TD.CONJUNTOS["c"][1]
    TD.verificar_sin_fuga(num, cat)
