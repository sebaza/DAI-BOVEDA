"""Model figures for EVERY group, whatever its size (plan 2026-11-18, Task 5): rebuilt from saved predictions, never retrained."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

from evaluation import grupos_todos as GT

ARTEFACTOS = Path(__file__).resolve().parents[2] / "artefactos"


def _datos(tam, seed=0, prev=0.3):
    """One synthetic row per person; group ``g{i}`` has ``tam[i]`` rows."""
    rng = np.random.default_rng(seed)
    grupo = np.concatenate([[f"g{i}"] * n for i, n in enumerate(tam)])
    y = (rng.random(len(grupo)) < prev).astype("int8")
    p = np.round(np.clip(0.3 * y + rng.random(len(grupo)) * 0.7, 0, 1), 2)       # rounded: plenty of ties
    return grupo, y, p, np.full(len(grupo), 0.3), np.arange(len(grupo))


def _filas(tam, n_boot=60, **kw):
    grupo, y, p, base, personas = _datos(tam, **kw)
    return {f["grupo"]: f for f in GT.tabla_grupos(grupo, y, p, base, personas, n_boot=n_boot)}


def test_every_group_is_listed_including_n_below_ten():
    filas = _filas([1, 5, 9, 10, 40])
    assert set(filas) == {"g0", "g1", "g2", "g3", "g4"}
    assert [filas[g]["n"] for g in sorted(filas)] == [1, 5, 9, 10, 40]
    assert {g: f["pocos_casos"] for g, f in filas.items()} == {"g0": True, "g1": True, "g2": True, "g3": False, "g4": False}
    assert GT.POCOS_CASOS == 10


def test_metrics_are_none_without_events_or_single_class():
    grupo = np.array(["sin_eventos"] * 6 + ["todos_evento"] * 5 + ["uno"] + ["mixto"] * 8)
    y = np.array([0] * 6 + [1] * 5 + [1] + [1, 0, 1, 0, 0, 1, 0, 0], dtype="int8")
    p = np.linspace(0.05, 0.95, len(y))
    filas = {f["grupo"]: f for f in GT.tabla_grupos(grupo, y, p, np.full(len(y), 0.2), np.arange(len(y)), n_boot=30)}
    for g in ("sin_eventos", "todos_evento", "uno"):
        assert all(filas[g][c] is None for c in ("ap", "ap_lo", "ap_hi", "auc", "auc_lo", "auc_hi")), g
        assert filas[g]["tasa"] is not None and filas[g]["esperado"] is not None
    assert filas["sin_eventos"]["eventos"] == 0 and filas["sin_eventos"]["tasa"] == 0.0
    assert filas["mixto"]["ap"] is not None and filas["mixto"]["auc"] is not None
    # nothing is NaN once serialised
    json.dumps(GT.sin_nan({"filas": list(filas.values())}), allow_nan=False)


def test_bootstrap_ci_contains_point_estimate_and_is_seeded():
    a = _filas([400, 250], n_boot=200)
    b = _filas([400, 250], n_boot=200)
    assert a == b                                                   # seed 0: identical runs
    for f in a.values():
        for m in ("ap", "auc", "tasa", "esperado"):
            assert f[f"{m}_lo"] <= f[m] <= f[f"{m}_hi"], (f["grupo"], m)
    grupo, y, p, base, personas = _datos([400, 250])
    otra = GT.tabla_grupos(grupo, y, p, base, personas, n_boot=200, seed=1)
    assert [f["ap_lo"] for f in otra] != [a[f["grupo"]]["ap_lo"] for f in otra]
    assert GT.SEMILLA == 0 and GT.N_BOOT == 1000


def test_point_estimates_match_sklearn_with_tied_scores():
    grupo, y, p, base, personas = _datos([7, 30, 120], seed=3)
    filas = {f["grupo"]: f for f in GT.tabla_grupos(grupo, y, p, base, personas, n_boot=5)}
    for g, f in filas.items():
        m = grupo == g
        assert f["ap"] == pytest.approx(average_precision_score(y[m], p[m]), abs=1e-12)
        assert f["auc"] == pytest.approx(roc_auc_score(y[m], p[m]), abs=1e-12)
        assert f["tasa"] == pytest.approx(y[m].mean()) and f["esperado"] == pytest.approx(p[m].mean())
        assert f["referencia"] == pytest.approx(0.3)


def test_weighted_metrics_equal_metrics_of_the_resampled_rows():
    grupo, y, p, _, _ = _datos([20, 60], seed=4)
    codigos = pd.factorize(grupo)[0]
    w = np.random.default_rng(9).integers(0, 4, len(y)).astype("float64")
    ap, auc = GT.Dimension(codigos, y, p).metricas(w)
    rep = np.repeat(np.arange(len(y)), w.astype(int))
    for g in (0, 1):
        idx = rep[codigos[rep] == g]
        assert ap[g] == pytest.approx(average_precision_score(y[idx], p[idx]), abs=1e-12)
        assert auc[g] == pytest.approx(roc_auc_score(y[idx], p[idx]), abs=1e-12)


def test_the_bootstrap_draws_persons_not_rows():
    """Two rows of one person always enter together: a group made of one person has the same point and every resample."""
    grupo = np.array(["a", "a", "b", "b", "b", "b"])
    y = np.array([1, 0, 1, 0, 0, 1], dtype="int8")
    p = np.array([0.9, 0.2, 0.8, 0.1, 0.3, 0.6])
    personas = np.array([1, 1, 2, 3, 4, 5])
    filas = {f["grupo"]: f for f in GT.tabla_grupos(grupo, y, p, np.full(6, 0.4), personas, n_boot=50)}
    assert filas["a"]["n"] == 2 and filas["a"]["tasa"] == 0.5


def test_dimensions_are_the_ones_of_the_current_group_tables():
    assert [d for d, _ in GT.DIMENSIONES] == ["programa", "facultad", "sexo", "via", "tipo_colegio"]


def test_block_lists_every_dimension_with_small_groups():
    n = 300
    rng = np.random.default_rng(5)
    df = pd.DataFrame({"cod_programa": np.array(["P1", "P2", "P3"])[np.arange(n) % 3], "facultad": "F",
                       "sexo_equidad": np.where(np.arange(n) % 50 == 0, "X", "F"), "via_clase": "regular",
                       "tipo_colegio": "municipal", "persona_key": np.arange(n)})
    df.loc[:5, "cod_programa"] = "RARO"                          # 6 rows: below ten
    y = (rng.random(n) < 0.2).astype("int8")
    blk = GT.bloque(df, y, rng.random(n), np.full(n, 0.2), "m", "ref", n_boot=10)
    assert blk["modelo"] == "m" and blk["referencia"] == "ref" and blk["n"] == n and blk["eventos"] == int(y.sum())
    assert set(blk["dimensiones"]) == {"programa", "facultad", "sexo", "via", "tipo_colegio"}
    raro = [f for f in blk["dimensiones"]["programa"] if f["grupo"] == "RARO"][0]
    assert raro["n"] == 6 and raro["pocos_casos"] is True
    assert any(f["grupo"] == "X" and f["pocos_casos"] for f in blk["dimensiones"]["sexo"])


def test_t1_block_aligns_predictions_by_episode_and_keeps_every_program():
    n = 200
    snap = pd.DataFrame({"episodio_id": np.arange(n), "persona_key": np.arange(n) // 2, "k": 1, "split": "test",
                         "estado_muestra": "observada", "continua": pd.array(np.arange(n) % 4 != 0, dtype="boolean"),
                         "cod_programa": np.array(["P1", "P2", "P3"])[np.arange(n) % 3], "sexo_equidad": "F",
                         "via_clase": "regular", "tipo_colegio": "municipal"})
    snap.loc[snap.index[:4], "cod_programa"] = "PX"
    prog = pd.DataFrame({"facultad_nombre": ["Facultad A", "Facultad A", "Facultad B"]}, index=["P1", "P2", "P3"])
    ids = snap["episodio_id"].to_numpy()[::-1].copy()
    preds = {"episodio_test": ids, "test__cb_acad": np.linspace(0, 1, n), "test__baseline_tasa": np.full(n, 0.25)}
    blk = GT.bloque_t1(snap, preds, 1, prog, n_boot=5)
    assert blk["modelo"] == "cb_acad" and blk["n"] == n
    assert "Sin facultad" in {f["grupo"] for f in blk["dimensiones"]["facultad"]}
    assert sum(f["n"] for f in blk["dimensiones"]["programa"]) == n


def test_t3_block_uses_the_episodes_followed_up_to_twelve():
    n, k = 300, 2
    rng = np.random.default_rng(2)
    seg = np.where(np.arange(n) % 10 == 0, 8, 14)
    snap = pd.DataFrame({"episodio_id": np.arange(n), "persona_key": np.arange(n), "k": k, "split": "test",
                         "cod_programa": np.array(["P1", "P2", "P3"])[np.arange(n) % 3], "tiempo": np.minimum(seg, rng.integers(6, 15, n)),
                         "seguimiento_max": seg, "causa": np.where(rng.random(n) < 0.5, 1, 0), "sexo_equidad": "F",
                         "via_clase": "regular", "tipo_colegio": "municipal"})
    F = np.sort(rng.random((n, 18)), axis=1).astype("float32")
    preds = {"episodio_id": snap["episodio_id"].to_numpy(), "nn_gru": F, "km_programa": F * 0.9}
    prog = pd.DataFrame({"facultad_nombre": ["Facultad A", "Facultad A", "Facultad B"]}, index=["P1", "P2", "P3"])
    blk = GT.bloque_t3(snap, preds, k, prog, n_boot=5, modelo="nn_gru")
    el = seg >= 12
    assert blk["n"] == int(el.sum()) and blk["horizonte"] == 12
    assert sum(f["n"] for f in blk["dimensiones"]["programa"]) == int(el.sum())


def test_no_key_or_person_field_reaches_a_block():
    n = 40
    df = pd.DataFrame({"cod_programa": "P1", "facultad": "F", "sexo_equidad": "F", "via_clase": "v", "tipo_colegio": "t",
                       "persona_key": np.arange(n)})
    blk = GT.bloque(df, (np.arange(n) % 3 == 0).astype("int8"), np.linspace(0, 1, n), np.full(n, 0.3), "m", "r", n_boot=5)
    texto = json.dumps(GT.sin_nan(blk), allow_nan=False)
    assert "persona_key" not in texto and "episodio" not in texto


# ----------------------------------------------------------------------------------------- parity with today's tables
@pytest.mark.skipif(not (ARTEFACTOS / "grupos_todos.json").exists(), reason="grupos_todos.json not produced")
def test_group_metrics_match_existing_tables_for_reportable_groups():
    doc = json.loads((ARTEFACTOS / "grupos_todos.json").read_text(encoding="utf-8"))
    paridad = GT.verificar(doc, ARTEFACTOS)
    assert paridad, "no table could be compared"
    for clave, v in paridad.items():
        assert v["comparados"] > 0, clave
        tol = GT.tolerancia(clave)
        assert v["max_dif_ap"] <= tol and v["max_dif_auc"] <= tol and v.get("max_dif_tasa", 0.0) <= 1e-9, (clave, v)
        assert v["n_distinto"] == 0, clave
        assert v.get("faltan", 0) == 0, clave                      # no benchmark group may be missing from our tables
    claves = set(paridad)
    esperadas = {"t2_banda_unanimidad_programa", "t2_banda_distincion_facultad", "t2_banda_maxima_distincion_programa",
                 "t1_beneficios_k1_programa", "t1_beneficios_k2_facultad", "t1_extension_k4_programa", "t6_h2_programa",
                 "t6_h2_facultad", "t6_h4_n"}
    assert esperadas <= claves, esperadas - claves


@pytest.mark.skipif(not (ARTEFACTOS / "grupos_todos.json").exists(), reason="grupos_todos.json not produced")
def test_the_artefact_is_json_safe_and_marks_small_groups():
    texto = (ARTEFACTOS / "grupos_todos.json").read_text(encoding="utf-8")
    assert "NaN" not in texto and "Infinity" not in texto and "persona_key" not in texto
    doc = json.loads(texto)
    filas = [f for t in doc["tareas"].values() for v in t.values() for b in v.values() for fs in b["dimensiones"].values() for f in fs]
    assert filas and any(f["pocos_casos"] for f in filas)
    assert all(f["pocos_casos"] == (f["n"] < 10) for f in filas)


def _snap_t6(n, offset, split, seed):
    rng = np.random.default_rng(seed)
    seg = np.where(np.arange(n) % 4 == 0, 1, 6)
    return pd.DataFrame({"episodio_id": offset + np.arange(n), "persona_key": offset + np.arange(n), "split": split,
                         "cod_programa": np.array(["P1", "P2"])[np.arange(n) % 2], "tiempo": np.minimum(seg, rng.integers(1, 8, n)),
                         "evento": (rng.random(n) < 0.3).astype(int), "seguimiento": seg, "sexo_equidad": "F", "via_clase": "regular",
                         "tipo_colegio": "municipal"}), seg


def test_t6_block_pools_valid_and_test_units_followed_up_to_the_horizon():
    rng = np.random.default_rng(6)
    sv, seg_v = _snap_t6(120, 0, "valid", 1)
    st, seg_t = _snap_t6(80, 1000, "test", 2)
    snap = pd.concat([sv, st], ignore_index=True)
    def preds(s):
        return {"episodio_id": s["episodio_id"].to_numpy()[::-1].copy(), "cox__tau2": rng.random(len(s)).astype("float32"),
                "baseline_programa__tau2": np.full(len(s), 0.2, dtype="float32")}
    prog = pd.DataFrame({"facultad_nombre": ["Facultad A", "Facultad B"]}, index=["P1", "P2"])
    blk = GT.bloque_t6(snap, {"valid": preds(sv), "test": preds(st)}, 2, "cox", prog, n_boot=5)
    assert blk["n"] == int((seg_v >= 2).sum() + (seg_t >= 2).sum()) and blk["horizonte"] == 2 and blk["modelo"] == "cox"
    assert blk["particiones"] == ["valid", "test"]
    assert sum(f["n"] for f in blk["dimensiones"]["programa"]) == blk["n"]


def _snap_t2(n):
    rng = np.random.default_rng(8)
    return pd.DataFrame({"intento_id": np.arange(n), "persona_key": np.arange(n) // 3, "y": 0,
                         "banda_nota": rng.choice(GT.R2.BANDAS, n, p=[0.15, 0.4, 0.3, 0.15]),
                         "cod_programa": np.array(["P1", "P2", "RARO"])[np.where(np.arange(n) < 5, 2, np.arange(n) % 2)],
                         "sexo_equidad": "F", "via_clase": "regular", "tipo_colegio": "municipal"})


def test_t2_band_blocks_list_every_group_for_the_three_other_bands():
    n = 600
    snap = _snap_t2(n)
    rng = np.random.default_rng(9)
    P = rng.dirichlet(np.ones(4), n).astype("float32")
    F = np.tile(np.array([0.15, 0.4, 0.3, 0.15], dtype="float32"), (n, 1))
    ids = snap["intento_id"].to_numpy()[::-1].copy()
    prog = pd.DataFrame({"facultad_nombre": ["Facultad A", "Facultad B"]}, index=["P1", "P2"])
    bl = GT.bloques_t2_bandas(snap, ids, P[::-1], F[::-1], prog, n_boot=5)
    assert set(bl) == {"banda_unanimidad", "banda_distincion", "banda_maxima_distincion"}
    for variante, b in bl.items():
        banda = variante[len("banda_"):]
        assert b["modelo"] == "cb_bandas" and b["referencia"] == "frecuencias" and b["banda"] == banda
        assert b["eventos"] == int((snap["banda_nota"] == banda).sum()) and b["n"] == n
        assert set(b["dimensiones"]) == {"programa", "facultad"}
        raro = [f for f in b["dimensiones"]["programa"] if f["grupo"] == "RARO"][0]
        assert raro["n"] == 5 and raro["pocos_casos"] is True        # listed although it has five attempts


def test_t1_ablation_block_takes_the_ablation_s_kept_model_and_any_cut():
    n = 160
    snap = pd.DataFrame({"episodio_id": np.arange(n), "persona_key": np.arange(n), "k": 4, "split": "test",
                         "estado_muestra": "observada", "continua": pd.array(np.arange(n) % 5 != 0, dtype="boolean"),
                         "cod_programa": np.array(["P1", "P2"])[np.arange(n) % 2], "sexo_equidad": "F", "via_clase": "regular",
                         "tipo_colegio": "municipal"})
    prog = pd.DataFrame({"facultad_nombre": ["Facultad A", "Facultad B"]}, index=["P1", "P2"])
    preds = {"episodio_test": snap["episodio_id"].to_numpy(), "test__cb_acad": np.linspace(0, 1, n),
             "test__lr_acad": np.linspace(1, 0, n), "test__baseline_tasa": np.full(n, 0.2)}
    blk = GT.bloque_t1(snap, preds, 4, prog, n_boot=5, modelo="lr_acad")
    assert blk["modelo"] == "lr_acad" and blk["n"] == n
    assert blk["dimensiones"]["programa"][0]["esperado"] == pytest.approx(np.linspace(1, 0, n)[::2].mean())


def test_the_comparison_reports_benchmark_groups_missing_from_our_table():
    nuevas = [{"grupo": "a", "n": 5, "ap": 0.5, "auc": 0.6}]
    previas = [{"grupo": "a", "n": 5, "ap": 0.5, "roc_auc": 0.6}, {"grupo": "b", "n": 20, "ap": 0.1, "roc_auc": 0.2}]
    r = GT._comparar(nuevas, previas, "ap", "roc_auc")
    assert r["comparados"] == 1 and r["faltan"] == 1


def _exportador():
    import importlib.util

    spec = importlib.util.spec_from_file_location("exportar_resumen_modelos", ARTEFACTOS.parent / "tools" / "exportar_resumen_modelos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_exporter_reads_grupos_todos_and_not_grupos_facultad(tmp_path):
    exp = _exportador()
    (tmp_path / "grupos_todos.json").write_text(json.dumps({"tareas": {}}), encoding="utf-8")
    (tmp_path / "grupos_facultad.json").write_text(json.dumps({"t1": {}}), encoding="utf-8")
    assert exp.cargar_grupos_todos(tmp_path) == {"tareas": {}}
    assert not hasattr(exp, "cargar_grupos_facultad")


def test_the_exporter_refuses_to_run_without_grupos_todos(tmp_path):
    exp = _exportador()
    with pytest.raises(FileNotFoundError, match=r"grupos_todos\.json.*evaluation\.grupos_todos"):
        exp.cargar_grupos_todos(tmp_path)


def _doc_registro(modelos=None):
    from evaluation import modelos_conservados as MC

    donde = {("t1", 1, "cb_acad"): ("t1", "base", 1), ("t1", 1, "cb_ben_pit"): ("t1", "beneficios_corte", 1),
             ("t1", 2, "lr_acad"): ("t1", "base", 2), ("t2", 0, "cb_c_nuevas"): ("t2", "base", 0),
             ("t3", 0, "dt_lr_adm"): ("t3", "base", 0), ("t3", 2, "nn_gru"): ("t3", "base", 2), ("t3", 4, "nn_gru"): ("t3", "base", 4),
             ("t5", 2, "gru_adm"): ("t5", "actual", 2), ("t5", 4, "gru_agg"): ("t5", "actual", 4)}
    assert set(donde) == set(MC.CLAVES)                      # the test follows the registry
    tareas = {}
    for clave, (tarea, variante, k) in donde.items():
        nombre = (modelos or {}).get(clave, clave[2])
        tareas.setdefault(tarea, {}).setdefault(variante, {})[str(k)] = {"modelo": nombre, "dimensiones": {"programa": []}}
    return {"tareas": tareas}


def test_the_exporter_checks_every_kept_model_against_the_registry():
    exp = _exportador()
    exp.validar_grupos_todos(_doc_registro())                # complete and equal: silent
    with pytest.raises(ValueError, match=r"lr_acad.*t3/base/k=2.*nn_gru"):
        exp.validar_grupos_todos(_doc_registro({("t3", 2, "nn_gru"): "lr_acad"}))
    sin = _doc_registro()
    del sin["tareas"]["t2"]
    with pytest.raises(ValueError, match=r"t2/base/k=0"):
        exp.validar_grupos_todos(sin)


def test_the_comparison_checks_the_observed_rate_and_the_tolerance_of_float32_sources():
    nuevas = [{"grupo": "a", "n": 5, "tasa": 0.4, "ap": 0.5, "auc": None}]
    ok = GT._comparar(nuevas, [{"grupo": "a", "n": 5, "tasa": 0.4, "ap": 0.5}], "ap", None)
    assert ok["max_dif_tasa"] == 0.0
    mal = GT._comparar(nuevas, [{"grupo": "a", "n": 5, "tasa": 0.5, "ap": 0.5}], "ap", None)
    assert mal["max_dif_tasa"] == pytest.approx(0.1)
    assert GT.tolerancia("t2_banda_distincion_programa") == 2e-6 and GT.tolerancia("t1_k1_programa") == 1e-6
