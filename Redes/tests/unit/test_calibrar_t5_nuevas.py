"""Calibration of the new T5 models (valid only, person-grouped cross-fitting). No database."""
import inspect

import pytest

np = pytest.importorskip("numpy")

from evaluation import calibrar_t5_nuevas as C   # noqa: E402


def _datos(n=1200, seed=0, sesgo=1.0):
    """Over-confident scores: the true risk is a shrunk version of the score."""
    rng = np.random.default_rng(seed)
    z = rng.normal(-1.5, 1.2, n)
    y = (rng.random(n) < 1 / (1 + np.exp(-(0.6 * z - 0.3)))).astype(int)
    p = 1 / (1 + np.exp(-sesgo * z))
    g = rng.integers(0, n // 2, n)                       # persons with about two rows each
    return y, p, g


def test_platt_is_monotone_and_reduces_the_brier_of_an_overconfident_score():
    y, p, _ = _datos()
    cal = C.PlattCalibrador().ajustar(p, y)
    q = cal.predecir(p)
    assert np.all((q >= 0) & (q <= 1))
    orden = np.argsort(p)
    assert np.all(np.diff(q[orden]) >= -1e-12)
    assert np.mean((q - y) ** 2) < np.mean((p - y) ** 2)


def test_isotonic_is_monotone_and_bounded():
    y, p, _ = _datos()
    q = C.IsotonicaCalibrador().ajustar(p, y).predecir(p)
    orden = np.argsort(p)
    assert np.all(np.diff(q[orden]) >= -1e-12) and q.min() >= 0 and q.max() <= 1


def test_calibrators_roundtrip_through_their_parameters():
    y, p, _ = _datos()
    for cls in (C.PlattCalibrador, C.IsotonicaCalibrador):
        cal = cls().ajustar(p, y)
        otra = cls.desde_parametros(cal.parametros())
        assert np.allclose(cal.predecir(p), otra.predecir(p))


def test_folds_never_split_a_person():
    _, _, g = _datos()
    f = C.folds_por_persona(g, 5, seed=0)
    for persona in np.unique(g):
        assert len(set(f[g == persona])) == 1
    assert set(f) == set(range(5))


def test_cross_fit_prediction_of_a_row_never_uses_its_own_fold():
    y, p, g = _datos()
    f = C.folds_por_persona(g, 5, seed=0)
    q = C.ajuste_cruzado(C.PlattCalibrador, y, p, f)
    # replacing the labels of one fold must leave the predictions of that very fold unchanged
    y2 = y.copy()
    y2[f == 0] = 1 - y2[f == 0]
    q2 = C.ajuste_cruzado(C.PlattCalibrador, y2, p, f)
    assert np.allclose(q[f == 0], q2[f == 0])
    assert not np.allclose(q[f != 0], q2[f != 0])


def test_method_choice_prefers_the_lower_brier_and_ties_go_to_platt():
    assert C.elegir_metodo(0.0500, 0.0510) == "platt"
    assert C.elegir_metodo(0.0510, 0.0500) == "isotonica"
    assert C.elegir_metodo(0.0500, 0.0500) == "platt"


def test_fitting_never_sees_test_data():
    # structural: the entry point takes no test labels, and test scores cannot change the fitted calibrator
    assert not any("y_test" in n or "yte" in n for n in inspect.signature(C.calibrar).parameters)
    yv, pv, gv = _datos(seed=1)
    _, pt1, _ = _datos(seed=2)
    _, pt2, _ = _datos(seed=3, sesgo=2.0)
    a, b = C.calibrar(yv, pv, gv, pt1), C.calibrar(yv, pv, gv, pt2)
    assert a["metodo"] == b["metodo"] and a["parametros"] == b["parametros"]
    assert np.array_equal(a["valid_cruzado"], b["valid_cruzado"])
    assert not np.array_equal(a["test"], b["test"])


def test_calibrar_returns_cross_fitted_valid_and_a_test_vector_in_range():
    yv, pv, gv = _datos(seed=4)
    _, pt, _ = _datos(seed=5)
    r = C.calibrar(yv, pv, gv, pt)
    assert r["metodo"] in ("platt", "isotonica") and set(r["brier_cruzado"]) == {"platt", "isotonica"}
    assert len(r["valid_cruzado"]) == len(yv) and len(r["test"]) == len(pt)
    assert 0 <= r["test"].min() and r["test"].max() <= 1


def test_ranking_metrics_are_preserved_by_platt():
    yv, pv, gv = _datos(seed=6)
    r = C.calibrar(yv, pv, gv, pv, metodo="platt")
    from evaluation import metrics as M
    a, b = M.metricas(yv, pv), M.metricas(yv, r["test"])
    assert abs(a["ap"] - b["ap"]) < 1e-9 and abs(a["roc_auc"] - b["roc_auc"]) < 1e-9


def test_publish_adds_keys_and_leaves_existing_arrays_bit_identical(tmp_path):
    ruta = tmp_path / "t45_k2_valid.npz"
    base = {"episodio_id": np.arange(5), "T5__x": np.linspace(0, 1, 5, dtype="float32"), "T4__y": np.ones(5, dtype="float32")}
    np.savez_compressed(ruta, **base)
    C.agregar_clave(ruta, "T5__x_cal", np.full(5, 0.3, dtype="float32"))
    z = np.load(ruta)
    assert all(np.array_equal(z[k], v) for k, v in base.items()) and np.allclose(z["T5__x_cal"], 0.3)
    with pytest.raises(ValueError):
        C.agregar_clave(ruta, "T5__x_cal", np.zeros(4, dtype="float32"))      # wrong length
