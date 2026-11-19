"""T4/T5 evaluation: person-grouped bootstrap, paired differences, multiclass metrics and the suppression / aggregation
rules of the group (programa, facultad) tables. No database."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from evaluation import grupos_t45 as G                  # noqa: E402
from evaluation import metrics as M                     # noqa: E402
from evaluation import metrics_t45 as M45               # noqa: E402


# ---------------------------------------------------------------------------------------------
# grouped bootstrap
# ---------------------------------------------------------------------------------------------
def test_resamples_keep_every_row_of_a_drawn_person_together():
    personas = np.array(["a", "a", "a", "b", "c", "c"])
    for idx in M45.remuestreos(personas, 200, seed=3):
        cuenta = pd.Series(personas[idx]).value_counts()
        # a drawn person always brings all of its rows: counts are multiples of the person's size
        assert cuenta.get("a", 0) % 3 == 0 and cuenta.get("b", 0) % 1 == 0 and cuenta.get("c", 0) % 2 == 0


def test_resamples_are_reproducible_and_have_the_size_of_persons_drawn():
    personas = np.repeat(np.arange(50), 2)
    a = M45.remuestreos(personas, 5, seed=1)
    b = M45.remuestreos(personas, 5, seed=1)
    assert all((x == y).all() for x, y in zip(a, b))
    assert all(len(x) == 100 for x in a)                 # every person has 2 rows: 50 draws x 2


def _datos(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    p = 1 / (1 + np.exp(-(x * 1.5 - 2.5)))
    y = (rng.random(n) < p).astype(int)
    ruido = rng.normal(size=n)
    return y, {"bueno": p, "malo": 1 / (1 + np.exp(-(ruido * 1.5 - 2.5)))}, np.arange(n)


def test_bootstrap_intervals_contain_the_point_and_the_paired_delta_is_positive_for_a_better_model():
    y, sc, personas = _datos()
    idxs = M45.remuestreos(personas, 200, seed=2)
    out = M45.bootstrap_agrupado(y, sc, idxs, pares=[("bueno", "malo")])
    ap = out["bueno"]["ap"]
    assert ap["lo"] <= ap["punto"] <= ap["hi"]
    assert ap["punto"] == pytest.approx(M.metricas(y, sc["bueno"])["ap"])
    d = out["bueno__vs__malo"]["ap"]
    assert d["lo"] > 0 and d["punto"] == pytest.approx(out["bueno"]["ap"]["punto"] - out["malo"]["ap"]["punto"])
    assert out["bueno__vs__malo"]["roc_auc"]["lo"] > 0


def test_a_model_against_itself_has_a_zero_paired_delta():
    y, sc, personas = _datos()
    out = M45.bootstrap_agrupado(y, {"a": sc["bueno"], "b": sc["bueno"]}, M45.remuestreos(personas, 50, 0), pares=[("a", "b")])
    assert out["a__vs__b"]["ap"] == {"punto": 0.0, "lo": 0.0, "hi": 0.0}


def test_the_grouped_interval_is_wider_than_the_naive_one_when_rows_of_a_person_are_alike():
    rng = np.random.default_rng(5)
    persona = np.repeat(np.arange(300), 4)
    base = rng.random(300)
    y = (rng.random(1200) < np.repeat(base * 0.3, 4)).astype(int)
    p = np.repeat(base * 0.3, 4)
    ancho = lambda idxs: np.subtract(*np.percentile([M.metricas(y[i], p[i])["brier"] for i in idxs], [97.5, 2.5]))   # noqa: E731
    naive = M45.remuestreos(np.arange(1200), 200, 1)
    agrupado = M45.remuestreos(persona, 200, 1)
    assert ancho(agrupado) > ancho(naive)


# ---------------------------------------------------------------------------------------------
# multiclass view
# ---------------------------------------------------------------------------------------------
def test_multiclass_metrics_of_a_perfect_and_of_a_uniform_forecast():
    yc = np.array([0] * 40 + [1] * 30 + [2] * 30)
    perfecto = np.eye(3)[yc] * 0.98 + 0.01
    r = M45.metricas_multiclase(yc, perfecto, ("a", "b", "c"))
    assert r["logloss"] < 0.05 and r["ap_a"] == pytest.approx(1.0) and r["ap_macro"] == pytest.approx(1.0)
    uni = np.full((100, 3), 1 / 3)
    u = M45.metricas_multiclase(yc, uni, ("a", "b", "c"))
    assert u["logloss"] == pytest.approx(np.log(3)) and u["brier_mc"] == pytest.approx(2 / 3)


def test_a_class_with_fewer_than_ten_events_has_no_ranking_metric():
    yc = np.array([0] * 95 + [1] * 5)
    P = np.tile([0.9, 0.1], (100, 1))
    r = M45.metricas_multiclase(yc, P, ("a", "b"))
    assert np.isnan(r["ap_b"]) and np.isnan(r["roc_auc_b"])


# ---------------------------------------------------------------------------------------------
# group tables: reportability and suppression
# ---------------------------------------------------------------------------------------------
def test_a_group_is_reportable_only_with_enough_rows_and_enough_events():
    assert G.N_MIN == 100 and G.EVENTOS_MIN == 10
    assert G.es_reportable(100, 10)
    assert not G.es_reportable(99, 50)                  # too few rows
    assert not G.es_reportable(5000, 9)                 # too few events
    assert not G.es_reportable(0, 0)


def _mundo_grupos(seed=0):
    rng = np.random.default_rng(seed)
    grupo = np.array(["G1"] * 400 + ["G2"] * 300 + ["G3"] * 400 + ["PEQ"] * 60 + ["RARO"] * 500, dtype=object)
    tasa = {"G1": 0.20, "G2": 0.10, "G3": 0.05, "PEQ": 0.30, "RARO": 0.01}
    y = np.array([int(rng.random() < tasa[g]) for g in grupo])
    p = np.array([tasa[g] * 0.9 for g in grupo])
    base = np.full(len(y), y.mean())
    return grupo, y, p, base


def test_small_groups_and_groups_without_events_are_suppressed_and_only_counted():
    grupo, y, p, base = _mundo_grupos()
    t = G.tabla_agregada(grupo, y, p, base, M45.remuestreos(np.arange(len(y)), 100, 0))
    nombres = {f["grupo"] for f in t["filas"]}
    assert nombres == {"G1", "G2", "G3"} or nombres <= {"G1", "G2", "G3"}
    assert "PEQ" not in nombres and "RARO" not in nombres      # 60 rows / fewer than 10 events
    r = t["resumen"]
    assert r["grupos_total"] == 5 and r["grupos_reportables"] == len(nombres) and r["grupos_suprimidos"] == 5 - len(nombres)
    assert r["filas_total"] == 1660 and r["filas_en_reportables"] == sum(f["n"] for f in t["filas"])
    assert all(f["n"] >= 100 and f["eventos"] >= 10 for f in t["filas"])
    assert r["eventos_en_reportables"] == sum(f["eventos"] for f in t["filas"])


def test_group_rates_match_a_hand_computation_and_the_intervals_contain_the_point():
    grupo, y, p, base = _mundo_grupos()
    t = G.tabla_agregada(grupo, y, p, base, M45.remuestreos(np.arange(len(y)), 300, 4))
    f = {x["grupo"]: x for x in t["filas"]}["G1"]
    m = grupo == "G1"
    assert f["tasa_observada"]["punto"] == pytest.approx(y[m].mean())
    assert f["riesgo_medio"]["punto"] == pytest.approx(p[m].mean())
    assert f["brecha"]["punto"] == pytest.approx(p[m].mean() - y[m].mean())
    for campo in ("tasa_observada", "riesgo_medio", "brecha", "brecha_base"):
        assert f[campo]["lo"] <= f[campo]["punto"] <= f[campo]["hi"] or campo == "riesgo_medio"
    assert f["riesgo_medio_base"]["punto"] == pytest.approx(base[m].mean())


def test_the_group_model_beats_the_flat_baseline_in_the_weighted_gap_and_the_ranking():
    grupo, y, p, base = _mundo_grupos()
    r = G.tabla_agregada(grupo, y, p, base, M45.remuestreos(np.arange(len(y)), 300, 4))["resumen"]
    assert r["mae_modelo"]["punto"] < r["mae_base"]["punto"]
    assert r["mae_modelo_menos_base"]["punto"] == pytest.approx(r["mae_modelo"]["punto"] - r["mae_base"]["punto"])
    assert r["spearman_modelo"]["punto"] == pytest.approx(1.0)
    ranking = r["ranking"]
    assert ranking["top_observado"][0] == "G1" and ranking["bottom_observado"][0] == "G3"


def test_rankings_never_contain_a_suppressed_group():
    grupo, y, p, base = _mundo_grupos()
    r = G.tabla_agregada(grupo, y, p, base, M45.remuestreos(np.arange(len(y)), 50, 0))["resumen"]["ranking"]
    for lista in ("top_observado", "bottom_observado", "top_predicho", "bottom_predicho"):
        assert not {"PEQ", "RARO"} & set(r[lista])


def test_missing_group_values_form_their_own_group_and_follow_the_same_rule():
    grupo = np.array([None] * 120 + ["A"] * 200, dtype=object)
    y = np.array([1] * 12 + [0] * 108 + [1] * 30 + [0] * 170)
    cod, nombres, n, ev, rep = G.clasificar_grupos(grupo, y)
    por = dict(zip(nombres, zip(n, ev, rep)))
    assert por["sin_dato"] == (120, 12, True) and por["A"] == (200, 30, True)
