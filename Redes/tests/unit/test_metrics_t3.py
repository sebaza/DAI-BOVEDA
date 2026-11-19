"""Survival metrics of T3 against hand-computed cases: Aalen-Johansen vs the naive KM, Kaplan-Meier of the censoring,
Uno's truncated C-index (with a competing event and IPCW weights), IPCW Brier, time-dependent AUC, integrated Brier,
horizon eligibility and the paired bootstrap. Numpy only (the GPU kernels are checked against the numpy ones)."""
import numpy as np
import pytest

pytest.importorskip("sklearn")

from evaluation import metrics_t3 as M3   # noqa: E402


# ---------------------------------------------------------------------------------------------
# Aalen-Johansen and Kaplan-Meier
# ---------------------------------------------------------------------------------------------
def test_aalen_johansen_matches_the_hand_computation():
    t = np.array([1, 1, 2, 3, 3])
    c = np.array([1, 2, 1, 0, 2])
    r = M3.aalen_johansen(t, c, grid=np.array([0, 1, 2, 3, 4]))
    assert r["S"] == pytest.approx([1.0, 0.6, 0.4, 0.2, 0.2])
    assert r["F1"] == pytest.approx([0.0, 0.2, 0.4, 0.4, 0.4])
    assert r["F2"] == pytest.approx([0.0, 0.2, 0.2, 0.4, 0.4])
    assert r["S"] + r["F1"] + r["F2"] == pytest.approx(np.ones(5))


def test_naive_km_overstates_the_cumulative_incidence_when_a_competing_event_exists():
    t = np.array([1, 1, 2, 3, 3])
    c = np.array([1, 2, 1, 0, 2])
    ingenuo = M3.incidencia_ingenua(t, c, grid=np.array([1, 2, 3]))
    assert ingenuo == pytest.approx([0.2, 1 - 0.8 * (2 / 3), 1 - 0.8 * (2 / 3)])
    aj = M3.aalen_johansen(t, c, grid=np.array([1, 2, 3]))["F1"]
    assert (ingenuo >= aj - 1e-12).all() and ingenuo[-1] > aj[-1]


def test_without_competing_events_and_censoring_the_cif_is_the_empirical_distribution():
    t = np.array([1, 2, 2, 4])
    c = np.ones(4, dtype=int)
    aj = M3.aalen_johansen(t, c, grid=np.array([1, 2, 3, 4]))["F1"]
    assert aj == pytest.approx([0.25, 0.75, 0.75, 1.0])


def test_censoring_distribution_is_the_km_of_the_censoring_times():
    t = np.array([1, 2, 3, 4, 5])
    c = np.array([1, 0, 1, 0, 1])
    g = M3.supervivencia_censura(t, c, en=np.array([1, 2, 3, 4, 5]), antes=True)     # G(t-)
    assert g == pytest.approx([1.0, 1.0, 0.75, 0.75, 0.375])
    g_en = M3.supervivencia_censura(t, c, en=np.array([1, 2, 3, 4, 5]), antes=False)  # G(t)
    assert g_en == pytest.approx([1.0, 0.75, 0.75, 0.375, 0.375])


def test_a_competing_event_is_not_a_censoring_for_g():
    t = np.array([1, 2, 3])
    c = np.array([1, 2, 0])
    g = M3.supervivencia_censura(t, c, en=np.array([3]), antes=False)
    assert g == pytest.approx([0.0])                     # only the last subject is censored, and it was alone at risk


# ---------------------------------------------------------------------------------------------
# C-index (Uno, truncated, with a competing event)
# ---------------------------------------------------------------------------------------------
def test_c_index_without_censoring():
    t = np.array([1, 2, 3, 4])
    c = np.ones(4, dtype=int)
    r = np.array([0.9, 0.7, 0.8, 0.1])
    assert M3.c_index_uno(t, c, r, tau=10) == pytest.approx(5 / 6)
    assert M3.c_index_uno(t, c, r, tau=2.5) == pytest.approx(4 / 5)       # only the events up to the horizon are cases


def test_c_index_counts_tied_scores_as_one_half_and_ties_in_time_are_not_comparable():
    t = np.array([1, 2])
    c = np.ones(2, dtype=int)
    assert M3.c_index_uno(t, c, np.array([0.5, 0.5]), tau=5) == pytest.approx(0.5)
    t2 = np.array([2, 2, 3])
    assert M3.c_index_uno(t2, np.ones(3, dtype=int), np.array([0.1, 0.9, 0.0]), tau=5) == pytest.approx(1.0)  # (1,2) tie in time dropped


def test_c_index_with_a_competing_event_treats_it_as_never_having_the_event():
    t = np.array([1, 2, 3])
    c = np.array([1, 2, 1])
    assert M3.c_index_uno(t, c, np.array([0.9, 0.1, 0.5]), tau=10) == pytest.approx(1.0)
    assert M3.c_index_uno(t, c, np.array([0.9, 0.8, 0.5]), tau=10) == pytest.approx(2 / 3)


def test_c_index_with_ipcw_weights_matches_the_hand_computation():
    t = np.array([1, 2, 3, 5])
    c = np.array([1, 0, 1, 0])
    r = np.array([0.5, 0.9, 0.2, 0.1])
    g = np.array([0.5, 1.0, 0.8, 1.0])                   # G(T_i) of each subject
    esperado = (4.0 * 2 + 1 / 0.64) / (4.0 * 3 + 1 / 0.64)
    assert M3.c_index_uno(t, c, r, tau=10, g=g) == pytest.approx(esperado)


def test_c_index_is_nan_without_comparable_pairs():
    assert np.isnan(M3.c_index_uno(np.array([1, 2]), np.array([0, 0]), np.array([0.1, 0.2]), tau=5))


# ---------------------------------------------------------------------------------------------
# Brier (IPCW), time-dependent AUC, eligibility, integrated Brier
# ---------------------------------------------------------------------------------------------
def test_ipcw_brier_matches_the_hand_computation():
    t = np.array([1, 2, 3, 4])
    c = np.array([1, 0, 1, 2])
    f = np.array([0.9, 0.5, 0.6, 0.2])
    assert M3.brier_ipcw(t, c, f, tau=3) == pytest.approx(0.31 / 4)


def test_ipcw_brier_without_censoring_is_the_plain_brier():
    t = np.array([1, 5, 2, 7])
    c = np.array([1, 2, 1, 1])
    f = np.array([0.7, 0.1, 0.4, 0.6])
    y = ((c == 1) & (t <= 4)).astype(float)
    assert M3.brier_ipcw(t, c, f, tau=4) == pytest.approx(np.mean((f - y) ** 2))


def test_auc_with_ties():
    y = np.array([1, 0, 1, 0])
    s = np.array([0.8, 0.8, 0.4, 0.2])
    assert M3.auc(y, s) == pytest.approx(0.625)
    assert np.isnan(M3.auc(np.ones(3), np.array([0.1, 0.2, 0.3])))


def test_horizon_eligibility_and_outcome():
    t = np.array([3, 12, 8, 14, 9])
    c = np.array([1, 1, 0, 2, 0])
    seg = np.array([15, 15, 8, 15, 11])
    elegible, y = M3.resultado_horizonte(t, c, seg, tau=10)
    assert elegible.tolist() == [True, True, False, True, True]        # censored at 8 < 10: unknown status at 10
    assert y[elegible].tolist() == [1, 0, 0, 0]                          # the egress at 12 and the exit at 14 are not events by 10


def test_integrated_brier_is_the_mean_brier_over_the_grid_of_eligible_subjects():
    t = np.array([2, 3, 6, 6])
    c = np.array([1, 2, 1, 0])
    seg = np.array([6, 6, 6, 6])
    f = np.array([[0.5, 0.5, 0.5], [0.0, 0.1, 0.1], [0.2, 0.4, 0.8], [0.0, 0.0, 0.0]])
    grid = np.array([2, 4, 6])
    b = [np.mean((f[:, j] - ((c == 1) & (t <= g)).astype(float)) ** 2) for j, g in enumerate(grid)]
    assert M3.ibs(t, c, seg, f, grid) == pytest.approx(np.mean(b))


def test_ibs_ignores_subjects_not_followed_up_to_the_end_of_the_grid():
    t = np.array([2, 3, 6])
    c = np.array([1, 0, 1])
    seg = np.array([6, 4, 6])
    f = np.array([[0.5, 0.5], [0.9, 0.9], [0.1, 0.1]])
    grid = np.array([2, 6])
    sin_ellos = M3.ibs(t[[0, 2]], c[[0, 2]], seg[[0, 2]], f[[0, 2]], grid)
    assert M3.ibs(t, c, seg, f, grid) == pytest.approx(sin_ellos)


# ---------------------------------------------------------------------------------------------
# evaluator, bootstrap, GPU kernels
# ---------------------------------------------------------------------------------------------
def _muestra(n=600, seed=0):
    """Discrete-time data after a cut at slot 2: hazard h_i = 0.12 exp(0.4 z_i), 20 % of the events are competing."""
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    h = np.clip(0.12 * np.exp(0.4 * z), 0, 0.6)
    t = 2 + rng.geometric(h)
    causa = np.where(rng.random(n) < 0.2, 2, 1)
    seg = rng.choice([14, 16, 18], n)
    causa = np.where(t > seg, 0, causa)
    t = np.minimum(t, seg)
    slots = np.arange(3, 15)
    f = 0.8 * (1 - (1 - h)[:, None] ** (slots - 2)[None, :])
    return t, causa, seg, z, slots, f


def test_evaluator_point_estimates_equal_the_plain_functions():
    t, c, seg, z, slots, f = _muestra()
    ev = M3.Evaluador(t, c, seg, slots, {"modelo": f, "azar": np.full_like(f, 0.3)}, horizontes=(10, 12), ibs_hasta=12)
    r = ev.metricas(np.arange(len(t)))
    el, y = M3.resultado_horizonte(t, c, seg, 10)
    col = list(slots).index(10)
    assert r["modelo"]["auc_10"] == pytest.approx(M3.auc(y[el], f[el, col]))
    assert r["modelo"]["brier_10"] == pytest.approx(np.mean((f[el, col] - y[el]) ** 2))
    assert r["modelo"]["c_10"] == pytest.approx(M3.c_index_uno(t[el], c[el], f[el, col], tau=10))
    assert r["azar"]["auc_10"] == pytest.approx(0.5)
    grid = np.arange(3, 13)
    assert r["modelo"]["ibs"] == pytest.approx(M3.ibs(t, c, seg, f[:, : len(grid)], grid))


def test_torch_kernels_equal_the_numpy_ones():
    torch = pytest.importorskip("torch")
    t, c, seg, z, slots, f = _muestra(seed=3)
    a = M3.Evaluador(t, c, seg, slots, {"m": f}, horizontes=(10, 12), ibs_hasta=12, backend="numpy")
    b = M3.Evaluador(t, c, seg, slots, {"m": f}, horizontes=(10, 12), ibs_hasta=12, backend="torch", device="cpu")
    idx = np.random.default_rng(2).integers(0, len(t), len(t))
    ra, rb = a.metricas(idx)["m"], b.metricas(idx)["m"]
    for k in ra:
        assert ra[k] == pytest.approx(rb[k], rel=1e-9, abs=1e-12), k


def test_bootstrap_is_paired_reproducible_and_brackets_the_point():
    t, c, seg, z, slots, f = _muestra(seed=5)
    slots_ = np.arange(3, 15)
    peor = np.tile(0.8 * (1 - 0.88 ** (slots_ - 2)), (len(t), 1))                # no covariates
    ev = M3.Evaluador(t, c, seg, slots, {"bueno": f, "peor": peor}, horizontes=(10, 12), ibs_hasta=12)
    r1 = ev.bootstrap(n_boot=60, seed=4, pares=[("bueno", "peor")])
    r2 = ev.bootstrap(n_boot=60, seed=4, pares=[("bueno", "peor")])
    assert r1 == r2
    m = r1["bueno"]["auc_10"]
    assert m["lo"] <= m["punto"] <= m["hi"]
    d = r1["__delta__bueno__peor"]["ibs"]
    assert d["punto"] == pytest.approx(r1["bueno"]["ibs"]["punto"] - r1["peor"]["ibs"]["punto"])
    assert d["punto"] < 0 and d["lo"] <= d["punto"] <= d["hi"]            # the model with the covariate has the lower IBS


def test_calibration_table_by_decile_at_a_horizon():
    t, c, seg, z, slots, f = _muestra(seed=1)
    tabla = M3.calibracion_horizonte(t, c, seg, f[:, list(slots).index(10)], 10)
    assert sum(r["n"] for r in tabla) == int((seg >= 10).sum())
    assert all(0 <= r["tasa_observada"] <= 1 for r in tabla)


# ---------------------------------------------------------------------------------------------
# cross-checks against lifelines (when installed)
# ---------------------------------------------------------------------------------------------
def test_aalen_johansen_and_harrell_agree_with_lifelines_without_ties():
    lifelines = pytest.importorskip("lifelines")
    from lifelines.utils import concordance_index

    rng = np.random.default_rng(11)
    n = 300
    t = rng.permutation(n) + 1.0                                    # no ties
    c = rng.choice([0, 1, 2], n, p=[0.2, 0.5, 0.3])
    grid = np.arange(1, n + 1, 25)
    aj = lifelines.AalenJohansenFitter(calculate_variance=False, seed=1)
    aj.fit(t, c, event_of_interest=1)
    ref = aj.cumulative_density_.iloc[:, 0]
    mine = M3.aalen_johansen(t, c, grid)["F1"]
    esperado = np.array([ref.loc[:g].iloc[-1] for g in grid])
    assert mine == pytest.approx(esperado, abs=1e-9)
    # no censoring, one event type: truncated C at a large tau equals Harrell's C
    c1 = np.ones(n, dtype=int)
    risk = rng.normal(size=n) - 0.02 * t
    assert M3.c_index_uno(t, c1, risk, tau=1e9) == pytest.approx(concordance_index(t, -risk, c1))
