"""Weighted metrics equal sklearn with sample_weight; ranking metrics per (student, period); cluster bootstrap."""
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("sklearn")
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

from evaluation import metrics_t2 as M2  # noqa: E402


def _datos(seed=0, n=3000, n_grupos=600):
    rng = np.random.default_rng(seed)
    g = rng.integers(0, n_grupos, n)
    g = np.unique(g, return_inverse=True)[1]
    p = np.round(rng.random(n), 2)                       # ties on purpose
    y = (rng.random(n) < 0.15 + 0.5 * p).astype(int)
    return y, p, g


def test_weighted_ap_and_auc_match_sklearn_with_ties_and_weights():
    y, p, g = _datos()
    w = np.random.default_rng(1).integers(0, 4, len(y)).astype("float64")
    ev = M2.Evaluador(y, p, g)
    r = ev.metricas(w, np.ones(ev.n_grupos))
    assert r["ap"] == pytest.approx(average_precision_score(y, p, sample_weight=w))
    assert r["roc_auc"] == pytest.approx(roc_auc_score(y, p, sample_weight=w))
    assert r["ap_aprob"] == pytest.approx(average_precision_score(1 - y, 1 - p, sample_weight=w))
    assert r["brier"] == pytest.approx(np.average((p - y) ** 2, weights=w))


def test_unweighted_point_estimate_matches_sklearn():
    y, p, g = _datos(2)
    r = M2.puntuales(y, p, g)
    assert r["ap"] == pytest.approx(average_precision_score(y, p))
    assert r["roc_auc"] == pytest.approx(roc_auc_score(y, p))


def test_ranking_metrics_on_a_hand_made_case():
    # group 0: scores rank the failed course first; group 1: failed course ranked second of three; group 2: no failure
    g = np.array([0, 0, 0, 1, 1, 1, 2, 2])
    y = np.array([1, 0, 0, 0, 1, 0, 0, 0])
    p = np.array([.9, .5, .1, .8, .6, .1, .3, .2])
    rec, prec, el = M2.ranking_por_grupo(y, p, g, (1, 2))[1]
    assert el.tolist() == [1.0, 1.0, 0.0]
    assert rec.tolist()[:2] == [1.0, 0.0] and prec.tolist()[:2] == [1.0, 0.0]
    rec2, prec2, _ = M2.ranking_por_grupo(y, p, g, (1, 2))[2]
    assert rec2.tolist()[:2] == [1.0, 1.0] and prec2.tolist()[:2] == [0.5, 0.5]
    ref = M2.referencia_azar(y, g, (1, 2))
    assert ref["n_grupos_elegibles"] == 2
    assert ref["recall_at_1"] == pytest.approx(np.mean([1 / 3, 1 / 3])) and ref["precision_at_1"] == pytest.approx(1 / 3)


def test_ranking_ties_are_broken_deterministically_by_seed():
    g = np.zeros(6, dtype=int)
    y = np.array([1, 0, 0, 0, 0, 0])
    p = np.full(6, 0.5)
    a = M2.ranking_por_grupo(y, p, g, (1,), semilla=3)[1][0]
    b = M2.ranking_por_grupo(y, p, g, (1,), semilla=3)[1][0]
    assert a.tolist() == b.tolist()


def test_cluster_bootstrap_is_paired_and_resamples_groups():
    y, p, g = _datos(4, 4000, 800)
    rng = np.random.default_rng(5)
    peor = np.clip(p + rng.normal(0, 0.4, len(p)), 0, 1)
    out = M2.bootstrap(y, {"a": p, "b": peor}, g, n_boot=60, seed=1, pares=[("a", "b")])
    for m in ("a", "b"):
        for k in M2.METRICAS:
            v = out[m][k]
            assert v["lo"] <= v["hi"]
            if k != "ece":
                assert v["lo"] - 1e-9 <= v["punto"] <= v["hi"] + 1e-9
    d = out["__delta__a__b"]["ap"]
    assert d["punto"] == pytest.approx(out["a"]["ap"]["punto"] - out["b"]["ap"]["punto"])
    assert d["lo"] > 0                                                      # a is clearly better than the noisy copy


def test_reliability_table_covers_all_rows():
    y, p, g = _datos(6)
    t = M2.tabla_confiabilidad(y, p)
    assert sum(r["n"] for r in t) == len(y)
