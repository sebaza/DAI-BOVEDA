"""T2 grade-band model (P74 / P84) and its aggregated forecasts by programa and facultad: metrics against the frequency
baseline, person-grouped bootstrap, suppression rules (n < 10 never listed; n >= 100 for a listed group; a class with fewer
than 10 events in a group has no cell). No database."""
import numpy as np
import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from evaluation import t2_bandas as TB            # noqa: E402
from pipelines.snapshots import rules_t2 as R2    # noqa: E402

C = len(R2.BANDAS)


def sintetico(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    logits = np.column_stack([-1.2 - 0.9 * x, 0.2 - 0.2 * x, 0.1 + 0.3 * x, -0.6 + 0.9 * x])
    p = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    y = np.array([rng.choice(C, p=r) for r in p])
    return y, p, rng.integers(0, n // 3, n)


def test_the_labels_follow_the_declared_band_order():
    d = pd.DataFrame({"banda_nota": list(R2.BANDAS) + ["distincion"]})
    assert TB.y_banda(d).tolist() == [0, 1, 2, 3, 2]
    assert TB.CLASES == R2.BANDAS


def test_the_frequency_baseline_is_the_train_distribution_and_the_model_beats_it():
    y, p, pers = sintetico()
    base = TB.frecuencias(y[:2000], len(y))
    assert base.shape == (len(y), C) and base[0].sum() == pytest.approx(1.0)
    assert np.allclose(base[0], np.bincount(y[:2000], minlength=C) / 2000)
    m_mod, m_base = TB.metricas(y, p), TB.metricas(y, base)
    assert m_mod["logloss"] < m_base["logloss"]
    assert m_mod["logloss"] == pytest.approx(-np.mean(np.log(p[np.arange(len(y)), y])))
    assert all(m_mod[f"ap_{c}"] > m_base[f"ap_{c}"] for c in R2.BANDAS)


def test_the_bootstrap_resamples_persons_and_gives_paired_differences():
    y, p, pers = sintetico(2500)
    base = TB.frecuencias(y[:1000], len(y))
    out = TB.bootstrap(y, {"m": p, "base": base}, pers, n_boot=60, seed=1, pares=[("m", "base")])
    r = out["m"]["logloss"]
    assert r["lo"] <= r["punto"] <= r["hi"]
    d = out["m__vs__base"]["logloss"]
    assert d["hi"] < 0                                              # the model is clearly better in log-loss
    assert out["m"]["ap_reprobado"]["punto"] > out["base"]["ap_reprobado"]["punto"]


def test_groups_under_10_are_never_listed_and_under_100_are_only_counted():
    rng = np.random.default_rng(3)
    tam = {"A": 400, "B": 120, "C": 60, "D": 9, "E": 3}
    grupo = np.concatenate([[g] * n for g, n in tam.items()])
    n = len(grupo)
    y = rng.integers(0, C, n)
    p = np.full((n, C), 1.0 / C)
    t = TB.tabla_grupos(grupo, y, p, TB.frecuencias(y, n), rng.integers(0, 10 ** 6, n), n_boot=30, seed=0)
    assert [f["grupo"] for f in t["filas"]] == ["A", "B"]
    r = t["resumen"]
    assert r["grupos_total"] == 5 and r["grupos_listados"] == 2
    assert r["grupos_100_o_mas"] == 2 and r["grupos_10_a_99"] == 1 and r["grupos_menos_10"] == 2
    assert r["filas_total"] == n and r["filas_en_listados"] == 520
    assert "E" not in str(t) and "'D'" not in str(t)               # a group of 3 or 9 attempts leaves no trace except the count


def test_a_class_with_fewer_than_10_events_in_a_group_has_no_cell():
    rng = np.random.default_rng(4)
    n = 300
    y = np.where(rng.random(n) < 0.03, 3, rng.integers(0, 3, n))     # class 3 is rare: < 10 events in the group
    y[:5] = 3
    p = np.full((n, C), 0.25)
    t = TB.tabla_grupos(np.array(["A"] * n), y, p, TB.frecuencias(y, n), rng.integers(0, 10 ** 6, n), n_boot=20, seed=0)
    fila = t["filas"][0]
    assert int((y == 3).sum()) < 10
    assert fila["bandas"]["maxima_distincion"]["observada"] is None and fila["bandas"]["maxima_distincion"]["predicha"] is None
    assert fila["bandas"]["reprobado"]["observada"]["punto"] == pytest.approx((y == 0).mean())
    assert fila["bandas"]["reprobado"]["predicha"]["punto"] == pytest.approx(0.25)


def test_the_gap_of_a_group_is_predicted_minus_observed_with_an_interval_and_a_baseline_gap():
    y, p, pers = sintetico(6000, seed=2)
    grupo = np.array(["G%d" % (i % 4) for i in range(len(y))])
    t = TB.tabla_grupos(grupo, y, p, TB.frecuencias(y, len(y)), pers, n_boot=80, seed=0)
    for f in t["filas"]:
        b = f["bandas"]["reprobado"]
        assert b["brecha"]["punto"] == pytest.approx(b["predicha"]["punto"] - b["observada"]["punto"])
        assert b["brecha"]["lo"] <= b["brecha"]["punto"] <= b["brecha"]["hi"]
        assert "brecha_base" in b
    assert t["resumen"]["mae_modelo"]["reprobado"]["punto"] >= 0
