"""Metrics, calibration, bootstrap and subgroup tables (no database)."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from evaluation import metrics as M  # noqa: E402
from evaluation import subgrupos as SG  # noqa: E402
from models.baseline import TasaHistorica  # noqa: E402


def test_perfect_and_inverted_rankings():
    y = np.array([0, 0, 0, 0, 1, 1, 0, 0, 0, 0])
    good = np.array([.1, .1, .1, .1, .9, .8, .1, .1, .1, .1])
    m = M.metricas(y, good)
    assert m["ap"] == pytest.approx(1.0) and m["roc_auc"] == pytest.approx(1.0)
    assert m["recall_10"] == pytest.approx(0.5) and m["precision_10"] == pytest.approx(1.0)   # top 1 of 10 rows
    assert M.metricas(y, 1 - good)["roc_auc"] == pytest.approx(0.0)


def test_brier_matches_the_definition():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.8, 0.2, 0.4, 0.6])
    assert M.metricas(y, p)["brier"] == pytest.approx(np.mean([0.04, 0.04, 0.36, 0.36]))


def test_top_decile_is_ceil_and_deterministic_with_ties():
    p = np.zeros(25)
    assert len(M.top_k_indices(p)) == 3
    assert list(M.top_k_indices(p)) == [0, 1, 2]


def test_reliability_table_and_ece_of_a_calibrated_score():
    rng = np.random.default_rng(1)
    p = rng.random(20000)
    y = (rng.random(20000) < p).astype(int)
    tabla = M.tabla_confiabilidad(y, p)
    assert len(tabla) == 10 and sum(r["n"] for r in tabla) == 20000
    assert [r["decil"] for r in tabla] == list(range(1, 11))
    assert all(abs(r["n"] - 2000) <= 2 for r in tabla)
    assert M.ece(y, p) < 0.02
    assert M.ece(y, np.clip(p * 0.2, 0, 1)) > 0.2                 # a badly calibrated score is penalized


def test_ece_with_constant_scores_does_not_fail():
    y = np.array([0, 1, 0, 0, 1, 0, 0, 0, 0, 0])
    assert M.ece(y, np.full(10, 0.2)) == pytest.approx(0.0, abs=1e-9)


def test_bootstrap_interval_contains_the_point_and_is_paired():
    rng = np.random.default_rng(2)
    y = (rng.random(600) < 0.2).astype(int)
    good = y * 0.5 + rng.random(600) * 0.6
    bad = rng.random(600)
    out = M.bootstrap(y, {"bad": bad, "good": good}, n_boot=100, seed=3, referencia="bad")
    for m in ("good", "bad"):
        for k in M.METRICAS:
            v = out[m][k]
            assert v["lo"] <= v["punto"] + 1e-9 and v["punto"] - 1e-9 <= v["hi"] or k == "ece"
    d = out["__delta__good"]["ap"]
    assert d["punto"] == pytest.approx(out["good"]["ap"]["punto"] - out["bad"]["ap"]["punto"])
    assert d["lo"] > 0                                            # the informative score beats noise in every resample


def test_bootstrap_is_reproducible():
    y = (np.random.default_rng(0).random(300) < 0.3).astype(int)
    p = np.random.default_rng(1).random(300)
    a = M.bootstrap(y, {"m": p}, n_boot=30, seed=5)
    b = M.bootstrap(y, {"m": p}, n_boot=30, seed=5)
    assert a == b


def test_subgroup_tables_drop_small_groups_and_report_gaps():
    rng = np.random.default_rng(4)
    n = 400
    df = pd.DataFrame({"cod_programa": rng.choice(["A", "B"], n), "cohorte_anio": 2022, "via_clase": "regular",
                       "sexo_equidad": np.where(np.arange(n) < 150, "F", "M")})
    df.loc[0, "cod_programa"] = "TINY"
    y = (rng.random(n) < 0.2).astype(int)
    p = rng.random(n)
    t = SG.todos(df, y, p)
    assert {r["grupo"] for r in t["programa"]} == {"A", "B"}         # TINY (n < 100) dropped
    assert {r["grupo"] for r in t["sexo"]} == {"F", "M"}
    gaps = SG.brechas_sexo(t["sexo"])
    f = next(r for r in t["sexo"] if r["grupo"] == "F")
    m = next(r for r in t["sexo"] if r["grupo"] == "M")
    assert gaps["ap"] == pytest.approx(f["ap"] - m["ap"])


def test_historical_rate_baseline_uses_train_rates_and_global_fallback():
    tr = pd.DataFrame({"cod_programa": ["A"] * 30 + ["B"] * 5, "k": 1, "y": [1] * 6 + [0] * 24 + [1] * 5})
    b = TasaHistorica(min_n=20).fit(tr)
    te = pd.DataFrame({"cod_programa": ["A", "B", "Z"], "k": 1})
    p = b.predict(te)
    assert p[0] == pytest.approx(0.2)
    assert p[1] == pytest.approx(tr["y"].mean()) == pytest.approx(p[2])   # B has < 20 rows, Z unseen
