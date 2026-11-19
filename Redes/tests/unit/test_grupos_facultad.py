"""Faculty / program groups of T1 base and T3 from saved predictions (D115): aggregation and alignment; every group is listed."""
import numpy as np
import pandas as pd
import pytest

from evaluation import grupos_facultad as GF

PROG_DF = pd.DataFrame({"facultad_nombre": ["Facultad A", "Facultad A", "Facultad B"]}, index=["P1", "P2", "P3"])


def _snap_t1(n=400, seed=0):
    rng = np.random.default_rng(seed)
    cod = np.array(["P1", "P2", "P3"])[np.arange(n) % 3]
    return pd.DataFrame({"episodio_id": np.arange(n), "persona_key": np.arange(n) // 2, "cod_programa": cod, "k": 1,
                         "split": "test", "estado_muestra": "observada",
                         "continua": pd.array(rng.random(n) > 0.3, dtype="boolean")})


def test_alinear_reorders_to_the_prediction_order_and_rejects_unknown_ids():
    df = pd.DataFrame({"episodio_id": [10, 11, 12]})
    assert GF.alinear(np.array([12, 10, 11]), df).tolist() == [2, 0, 1]
    with pytest.raises(ValueError):
        GF.alinear(np.array([10, 99]), df)
    with pytest.raises(ValueError):
        GF.alinear(np.array([10, 10]), df)


def test_t1_block_has_program_and_faculty_levels_and_lists_every_group():
    snap = _snap_t1()
    ids = snap["episodio_id"].to_numpy()[::-1].copy()                # predictions in another order than the snapshot
    rng = np.random.default_rng(1)
    preds = {"episodio_test": ids, "test__cb_acad": rng.random(len(ids)), "test__baseline_tasa": np.full(len(ids), 0.3)}
    blk = GF.bloque_t1(snap, preds, 1, PROG_DF, n_boot=20)
    assert blk["modelo"] == "cb_acad" and blk["n_test"] == 400
    fac = blk["grupos"]["facultad"]["filas"]
    assert {f["grupo"] for f in fac} == {"Facultad A", "Facultad B"}
    assert sum(f["n"] for f in fac) == 400
    for nivel in ("programa", "facultad"):
        for f in blk["grupos"][nivel]["filas"]:
            assert f["tasa_observada"]["lo"] <= f["tasa_observada"]["punto"] <= f["tasa_observada"]["hi"]
    y = (~snap["continua"].astype(bool)).to_numpy()
    a = snap["cod_programa"].isin(["P1", "P2"]).to_numpy()
    assert [f for f in fac if f["grupo"] == "Facultad A"][0]["tasa_observada"]["punto"] == pytest.approx(y[a].mean())


def test_unknown_program_falls_in_sin_facultad_never_a_bare_code():
    snap = _snap_t1()
    snap.loc[snap["cod_programa"] == "P3", "cod_programa"] = "PX"
    preds = {"episodio_test": snap["episodio_id"].to_numpy(), "test__cb_acad": np.full(len(snap), 0.3),
             "test__baseline_tasa": np.full(len(snap), 0.3)}
    blk = GF.bloque_t1(snap, preds, 1, PROG_DF, n_boot=5)
    assert "Sin facultad" in {f["grupo"] for f in blk["grupos"]["facultad"]["filas"]}


def test_t3_block_uses_episodes_followed_up_to_twelve_and_incidence_at_twelve():
    n, k = 600, 2
    rng = np.random.default_rng(2)
    cod = np.array(["P1", "P2", "P3"])[np.arange(n) % 3]
    seg = np.where(np.arange(n) % 10 == 0, 8, 14)                    # 10 % not followed up to 12
    snap = pd.DataFrame({"episodio_id": np.arange(n), "persona_key": np.arange(n), "cod_programa": cod, "k": k, "split": "test",
                         "tiempo": np.minimum(seg, rng.integers(6, 15, n)), "seguimiento_max": seg})
    snap["causa"] = np.where(rng.random(n) < 0.5, 1, 0)
    F = np.sort(rng.random((n, 18)), axis=1).astype("float32")
    preds = {"episodio_id": snap["episodio_id"].to_numpy(), "nn_gru": F, "km_programa": F * 0.9}
    blk = GF.bloque_t3(snap, preds, k, PROG_DF, n_boot=10, modelo="nn_gru")
    el = seg >= 12
    assert blk["n_test"] == int(el.sum()) and blk["horizonte"] == 12
    y = ((snap["causa"] == 1) & (snap["tiempo"] <= 12)).to_numpy()
    fila = [f for f in blk["grupos"]["facultad"]["filas"] if f["grupo"] == "Facultad B"][0]
    b = el & (cod == "P3")
    assert fila["n"] == int(b.sum()) and fila["eventos"] == int(y[b].sum())
    assert fila["tasa_observada"]["punto"] == pytest.approx(y[b].mean())
    assert fila["riesgo_medio"]["punto"] == pytest.approx(F[b, 12 - k - 1].mean(), rel=1e-5)


def test_comparar_filas_reports_common_and_missing_groups():
    nuevas = [{"grupo": "a", "n": 100, "tasa_observada": {"punto": 0.1}, "riesgo_medio": {"punto": 0.2}}]
    previas = [{"grupo": "a", "n": 100, "tasa_observada": 0.1, "riesgo_medio": 0.2},
               {"grupo": "b", "n": 120, "tasa_observada": 0.0, "riesgo_medio": 0.1}]
    r = GF.comparar_filas(nuevas, previas, "tasa_observada", "riesgo_medio", "tasa_observada", "riesgo_medio")
    assert r["comunes"] == 1 and r["solo_previas"] == 1 and r["n_distinto"] == 0 and r["max_dif_observada"] == 0


def test_sin_nan_makes_the_block_json_safe():
    assert GF.sin_nan({"a": [float("nan"), 1.0, np.float32("inf")]}) == {"a": [None, 1.0, None]}


# ------------------------------------------------------------------------------------------------- D116 (T3 confidence)
def _snap_t3_d116(k=2):
    """P1: 75 followed-up episodes, 5 egresos; P2: 9, 3 egresos; P3: 200, 60 egresos."""
    tam = {"P1": (75, 5), "P2": (9, 3), "P3": (200, 60)}
    filas = []
    for cod, (n, ev) in tam.items():
        for i in range(n):
            egreso = i < ev
            filas.append({"cod_programa": cod, "tiempo": 8 if egreso else 14, "causa": 1 if egreso else 0})
    d = pd.DataFrame(filas)
    d["episodio_id"] = np.arange(len(d))
    d["persona_key"] = np.arange(len(d))
    d["k"], d["split"], d["seguimiento_max"] = k, "test", 14
    return d


def _bloque_t3_d116():
    snap = _snap_t3_d116()
    rng = np.random.default_rng(3)
    F = np.sort(rng.random((len(snap), 18)), axis=1).astype("float32")
    preds = {"episodio_id": snap["episodio_id"].to_numpy(), "nn_gru": F, "km_programa": F * 0.9}
    return GF.bloque_t3(snap, preds, 2, PROG_DF, n_boot=10, modelo="nn_gru")


def test_confianza_t3_formula():
    assert GF.confianza_t3(75, 5) == pytest.approx(0.5)
    assert GF.confianza_t3(150, 10) == 1.0 and GF.confianza_t3(900, 360) == 1.0
    assert GF.confianza_t3(40, 20) == pytest.approx(40 / 150) and GF.confianza_t3(10, 0) == 0.0


def test_t3_lists_every_group_with_confidence_even_under_ten_people():
    prog = {f["grupo"]: f for f in _bloque_t3_d116()["grupos"]["programa"]["filas"]}
    assert set(prog) == {"P1", "P2", "P3"}                             # P2 has n = 9 and is listed
    assert prog["P2"]["n"] == 9 and prog["P2"]["confianza"] == pytest.approx(min(1, 9 / 150, 3 / 10))
    assert prog["P1"]["n"] == 75 and prog["P1"]["eventos"] == 5 and prog["P1"]["confianza"] == pytest.approx(0.5)
    assert prog["P3"]["confianza"] == 1.0
    fac = {f["grupo"]: f for f in _bloque_t3_d116()["grupos"]["facultad"]["filas"]}
    assert fac["Facultad A"]["n"] == 84


def test_t3_group_metrics_are_kept_for_small_groups():
    prog = {f["grupo"]: f for f in _bloque_t3_d116()["grupos"]["programa"]["filas"]}
    assert np.isfinite(prog["P1"]["ap"]) and np.isfinite(prog["P1"]["roc_auc"])      # n = 75 and 5 events: no blanking
    assert np.isfinite(prog["P3"]["ap"]) and np.isfinite(prog["P3"]["roc_auc"])


def test_the_publication_constants_are_gone():
    for nombre in ("N_MIN_T3", "N_METRICAS_GRUPO", "EVENTOS_MIN", "EVENTOS_MIN_T3"):
        assert not hasattr(GF, nombre), nombre
