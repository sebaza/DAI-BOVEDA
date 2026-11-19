"""T6 evaluation: cumulative incidence with a person-grouped bootstrap, horizon metrics on complete follow-up, suppression
of small groups (n < 100 or fewer than 10 events) and the viability gate. No database."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from evaluation import metrics_t45 as M45                # noqa: E402
from evaluation import metrics_t6 as M6                  # noqa: E402


# ---------------------------------------------------------------------------------------------
# cumulative incidence (Kaplan-Meier) against hand-computed values
# ---------------------------------------------------------------------------------------------
def test_cumulative_incidence_by_hand():
    # times 1, 2, 2, 3, 4 with events 1, 1, 0, 1, 0. At risk: t=1 -> 5 (1 event), t=2 -> 4 (1 event, 1 censored),
    # t=3 -> 2 (1 event), t=4 -> 1 (censored). S = 0.8, 0.6, 0.3, 0.3.
    t = np.array([1, 2, 2, 3, 4])
    e = np.array([1, 1, 0, 1, 0])
    f = M6.incidencia_acumulada(t, e, [1, 2, 3, 4, 8])
    assert f == pytest.approx([0.2, 0.4, 0.7, 0.7, 0.7])


def test_no_events_gives_zero_incidence_and_it_never_decreases():
    assert M6.incidencia_acumulada(np.array([3, 5, 7]), np.array([0, 0, 0]), [1, 4, 8]).tolist() == [0.0, 0.0, 0.0]
    rng = np.random.default_rng(1)
    t = rng.integers(1, 10, 300)
    e = (rng.random(300) < 0.3).astype(int)
    f = M6.incidencia_acumulada(t, e, list(range(1, 10)))
    assert (np.diff(f) >= -1e-12).all()


def test_interval_contains_the_point_and_uses_whole_persons():
    rng = np.random.default_rng(2)
    n = 600
    t = rng.integers(1, 9, n)
    e = (rng.random(n) < 0.15).astype(int)
    personas = np.arange(n)
    idxs = M45.remuestreos(personas, 200, seed=3)
    r = M6.incidencia_con_ic(t, e, [2, 4], idxs)
    for tau in (2, 4):
        d = r[tau]
        assert d["lo"] <= d["punto"] <= d["hi"]
    assert r[2]["punto"] == pytest.approx(M6.incidencia_acumulada(t, e, [2])[0])


# ---------------------------------------------------------------------------------------------
# group tables: suppression and reportability
# ---------------------------------------------------------------------------------------------
def _grupos(n_por_grupo, eventos_por_grupo, seed=0):
    rng = np.random.default_rng(seed)
    g, t, e = [], [], []
    for nombre, n in n_por_grupo.items():
        ev = eventos_por_grupo[nombre]
        g += [nombre] * n
        e += [1] * ev + [0] * (n - ev)
        t += list(rng.integers(1, 5, ev)) + [6] * (n - ev)
    return np.array(g), np.array(t), np.array(e)


def test_groups_below_the_thresholds_are_suppressed_and_only_counted():
    g, t, e = _grupos({"A": 300, "B": 100, "C": 99, "D": 500, "E": 8, "F": 400},
                      {"A": 25, "B": 10, "C": 20, "D": 9, "E": 4, "F": 0})
    idxs = M45.remuestreos(np.arange(len(g)), 100, seed=1)
    r = M6.tabla_incidencia_grupos(g, t, e, [4], idxs)
    nombres = [f["grupo"] for f in r["filas"]]
    assert nombres == ["A", "B"]                        # C: n < 100, D: < 10 events, E: tiny, F: no events
    res = r["resumen"]
    assert res["grupos_total"] == 6 and res["grupos_reportables"] == 2 and res["grupos_suprimidos"] == 4
    assert res["filas_en_reportables"] == 400 and res["eventos_en_reportables"] == 35
    assert res["n_min"] == 100 and res["eventos_min"] == 10
    for f in r["filas"]:
        assert f["n"] >= 100 and f["eventos"] >= 10
        d = f["incidencia"][4]
        assert d["lo"] <= d["punto"] <= d["hi"]


def test_nothing_about_a_suppressed_group_leaves_the_table():
    g, t, e = _grupos({"A": 300, "pequeno": 8}, {"A": 25, "pequeno": 4})
    r = M6.tabla_incidencia_grupos(g, t, e, [4], M45.remuestreos(np.arange(len(g)), 50, seed=1))
    assert "pequeno" not in str(r["filas"]) and "pequeno" not in str(r["resumen"])


# ---------------------------------------------------------------------------------------------
# horizon metrics
# ---------------------------------------------------------------------------------------------
def _horizonte(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    p = 1 / (1 + np.exp(-(1.4 * x - 3.0)))
    ev = rng.random(n) < p
    t = np.where(ev, rng.integers(1, 3, n), 8)
    seg = rng.integers(1, 9, n)
    e = (ev & (t <= seg)).astype(int)
    t = np.where(e == 1, t, seg)
    ruido = rng.normal(size=n)
    return t, e, seg, {"bueno": p, "malo": 1 / (1 + np.exp(-(1.4 * ruido - 3.0)))}, np.arange(n)


def test_horizon_metrics_use_only_rows_followed_up_to_the_horizon():
    t, e, seg, sc, personas = _horizonte()
    r = M6.evaluar_horizonte(t, e, seg, sc, 4, personas, n_boot=100, pares=[("bueno", "malo")])
    assert r["n"] == int((seg >= 4).sum())
    y = ((e == 1) & (t <= 4))[seg >= 4]
    assert r["eventos"] == int(y.sum())
    ap = r["modelos"]["bueno"]["ap"]
    assert ap["lo"] <= ap["punto"] <= ap["hi"]
    assert r["pares"]["bueno__vs__malo"]["ap"]["punto"] == pytest.approx(ap["punto"] - r["modelos"]["malo"]["ap"]["punto"])


def test_a_horizon_with_few_events_is_not_conclusive():
    t, e, seg, sc, personas = _horizonte()
    e2 = np.where(np.arange(len(e)) % 150 == 0, 1, 0)
    t2 = np.where(e2 == 1, 1, seg)
    r = M6.evaluar_horizonte(t2, e2, seg, sc, 4, personas, n_boot=20)
    assert r["eventos"] < 30 and r["conclusivo"] is False
    t, e, seg, sc, personas = _horizonte(n=6000)
    assert M6.evaluar_horizonte(t, e, seg, sc, 2, personas, n_boot=20)["conclusivo"] is True


def test_calibration_table_of_a_horizon_is_by_deciles():
    t, e, seg, sc, personas = _horizonte(n=4000)
    tabla = M6.calibracion_horizonte(t, e, seg, sc["bueno"], 4)
    assert 1 <= len(tabla) <= 10 and sum(f["n"] for f in tabla) == int((seg >= 4).sum())


def test_groups_report_how_many_units_are_still_at_risk_at_each_horizon():
    g, t, e = _grupos({"A": 300}, {"A": 25})
    seg = np.where(np.arange(len(g)) < 100, 8, 2)
    r = M6.tabla_incidencia_grupos(g, t, e, [2, 4, 8], M45.remuestreos(np.arange(len(g)), 30, seed=1), seguimiento=seg)
    assert r["filas"][0]["en_riesgo"] == {2: 300, 4: 100, 8: 100}


def test_calibration_bins_are_merged_until_each_has_enough_events():
    eventos = [0, 1, 0, 2, 1, 0, 3, 5, 8, 10]                                     # 30 events, deciles from low to high risk
    tabla = [{"decil": i + 1, "n": 100, "riesgo_medio": 0.01 * (i + 1), "tasa_observada": e / 100} for i, e in enumerate(eventos)]
    r = M6.agrupar_calibracion(tabla, eventos_min=10)
    # from the top: decile 10 alone (10 events); deciles 9 + 8 (13 events); the 7 events left join the last bin
    assert [f["n"] for f in r] == [100, 900]
    assert [round(f["tasa_observada"] * f["n"]) for f in r] == [10, 20]
    assert r[0]["riesgo_medio"] > r[1]["riesgo_medio"] and [f["grupo"] for f in r] == [1, 2]
    # fewer events than the minimum: a single bin with everything, and no bin ever has 1-9 events
    pocos = M6.agrupar_calibracion(tabla[:3], eventos_min=10)
    assert len(pocos) == 1 and pocos[0]["n"] == 300
    for f in r:
        assert round(f["tasa_observada"] * f["n"]) >= 10
