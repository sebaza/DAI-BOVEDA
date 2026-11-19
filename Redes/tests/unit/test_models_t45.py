"""T4/T5 models: row selection and targets, leakage guard on the feature sets, multiclass helpers and the rule that keeps
the classical model unless a network clearly beats it. No database."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")
pytest.importorskip("torch")

from evaluation import run_t45 as R                      # noqa: E402
from models import t45_data as TD                        # noqa: E402
from models import t45_multiclase as MC                  # noqa: E402
from pipelines.snapshots import rules_t45 as R45         # noqa: E402


def _snap():
    filas = []
    for i, (k, split, res) in enumerate([
            (2, "train", "continua"), (2, "train", "transicion"), (2, "train", "eliminacion"), (2, "valid", "otra_salida"),
            (2, "test", "egreso"), (2, "test", "censurado"), (2, "posterior", "continua"), (2, "train", "transicion_ambigua"),
            (4, "train", "continua")]):
        filas.append({"episodio_id": i, "k": k, "split": split, "resultado": res, "persona_key": f"p{i}", "cod_programa": "C1",
                      "eliminacion_con_reintegro": False, "eliminacion_efectiva": res == "eliminacion", "horizonte_e_dudoso": False})
    return pd.DataFrame(filas)


def test_selection_keeps_only_observed_unambiguous_rows_of_the_three_splits():
    d = TD.seleccionar(_snap(), 2)
    assert sorted(d["resultado"]) == ["continua", "egreso", "eliminacion", "otra_salida", "transicion"]
    assert set(d["split"]) <= {"train", "valid", "test"}


def test_targets_are_exclusive_and_the_class_index_follows_the_declared_order():
    d = TD.seleccionar(_snap(), 2)
    assert not ((d["y4"] == 1) & (d["y5"] == 1)).any()
    assert d.loc[d["resultado"] == "transicion", "y4"].iloc[0] == 1 and d["y4"].sum() == 1 and d["y5"].sum() == 1
    assert (d["yc"].map(dict(enumerate(TD.CLASES))) == d["resultado"]).all()
    assert TD.CLASES == R45.CLASES


def test_the_feature_sets_have_no_labels_sex_cohort_or_identity():
    for num, cat in TD.GRUPOS.values():
        TD.verificar_sin_fuga(num, cat)
    for malo in ("resultado", "sexo_equidad", "cohorte_anio", "persona_key", "episodio_especialidad_id", "hubo_transicion_en_horizonte",
                 "otra_salida_tipo", "y4", "seguimiento_max", "split", "k"):
        with pytest.raises(ValueError):
            TD.verificar_sin_fuga(["creditos_aprobados", malo], [])


def test_multiclass_class_frequencies_shrink_small_programs_to_the_global_ones():
    tr = pd.DataFrame({"yc": [0] * 80 + [3] * 20 + [0] * 5, "cod_programa": ["A"] * 100 + ["B"] * 5})
    m = MC.TasaClases().fit(tr)
    p = m.predict(pd.DataFrame({"cod_programa": ["A", "B", "Z"]}))
    assert p.shape == (3, MC.N_CLASES) and np.allclose(p.sum(axis=1), 1.0)
    assert p[0, 3] == pytest.approx((20 + 20 * m.global_[3]) / 120)            # program A: its own rate, lightly shrunk
    assert np.allclose(p[1], m.global_) and np.allclose(p[2], m.global_)      # fewer than MIN_N rows / unseen: the global ones


def test_a_class_missing_from_training_gets_the_floor_and_probabilities_still_sum_to_one():
    p = MC._completar(np.array([[0.7, 0.3]]), [0, 3])
    assert p.shape == (1, 5) and p.sum() == pytest.approx(1.0) and p[0, 1] > 0 and p[0, 0] > p[0, 3]


def test_the_classical_model_stays_unless_the_network_wins_on_valid_and_its_paired_test_interval_is_above_zero():
    sel = {"clasico": "cb_agg", "red": "gru_agg"}
    ap = {"cb_agg": 0.40, "gru_agg": 0.42}
    assert R.decidir_conservado(sel, {"lo": 0.001, "punto": 0.01, "hi": 0.02}, ap) == "gru_agg"
    assert R.decidir_conservado(sel, {"lo": -0.01, "punto": 0.01, "hi": 0.03}, ap) == "cb_agg"      # not significant
    assert R.decidir_conservado(sel, {"lo": 0.001, "punto": 0.01, "hi": 0.02}, {"cb_agg": 0.43, "gru_agg": 0.42}) == "cb_agg"
    assert R.decidir_conservado({"clasico": "lr_agg", "red": None}, None, {"lr_agg": 0.3}) == "lr_agg"


def test_best_models_are_chosen_with_the_validation_ap_only():
    rng = np.random.default_rng(0)
    y = (rng.random(600) < 0.2).astype(int)
    buena = np.clip(y * 0.5 + rng.random(600) * 0.5, 0, 1)
    mala = rng.random(600)
    p = {"baseline_tasa": mala, "lr_adm": mala, "lr_agg": buena, "cb_adm": mala, "cb_agg": mala, "gru_adm": buena, "gru_agg": mala}
    s = R.elegir_modelos(p, y)
    assert s == {"clasico": "lr_agg", "red": "gru_adm"}


def test_the_code_version_covers_the_new_sources():
    v1 = R.version_codigo_t45()
    assert len(v1) == 64 and v1 == R.version_codigo_t45()


# ---------------------------------------------------------------------------------------------
# stage B: the three evaluations of T5 (current label, elimination without reintegro, doubtful horizons excluded)
# ---------------------------------------------------------------------------------------------
def test_the_effective_elimination_target_is_an_elimination_without_reintegro():
    s = _snap()
    s["eliminacion_con_reintegro"] = s["resultado"] == "eliminacion"
    s["eliminacion_efectiva"] = False
    extra = pd.DataFrame([{"episodio_id": 90, "k": 2, "split": "train", "resultado": "eliminacion", "persona_key": "p90",
                           "cod_programa": "C1", "eliminacion_con_reintegro": False, "eliminacion_efectiva": True,
                           "horizonte_e_dudoso": False}])
    d = TD.seleccionar(pd.concat([s, extra], ignore_index=True), 2)
    assert d["y5"].sum() == 2 and d["y5e"].sum() == 1
    assert (d["y5e"] <= d["y5"]).all()                                  # an effective elimination is always an elimination
    assert d.loc[d["y5e"] == 1, "episodio_id"].tolist() == [90]
    assert TD.TARGETS["T5E"] == ("y5e", "eliminacion_efectiva")


def test_the_new_labels_and_flags_are_never_features():
    for malo in ("y5e", "eliminacion_con_reintegro", "eliminacion_efectiva", "horizonte_e_dudoso"):
        with pytest.raises(ValueError):
            TD.verificar_sin_fuga([malo], [])
    for num, cat in TD.GRUPOS.values():
        assert not {"eliminacion_con_reintegro", "eliminacion_efectiva", "horizonte_e_dudoso"} & set(num + cat)


def test_the_doubtful_horizon_sensitivity_drops_exactly_the_flagged_rows():
    rng = np.random.default_rng(0)
    n = 600
    te = pd.DataFrame({"persona_key": [f"p{i}" for i in range(n)], "horizonte_e_dudoso": np.arange(n) >= 400})
    y = (rng.random(n) < 0.15).astype(int)
    p = np.clip(0.15 + 0.3 * (y - 0.15) + rng.normal(0, 0.1, n), 0.01, 0.99)
    out = R.sensibilidad_horizonte_dudoso(te, y, {"m": p, "baseline_tasa": np.full(n, 0.15)}, "m", 100)
    assert out["n"] == 400 and out["n_excluidas"] == 200 and out["n_total_test"] == n
    assert out["eventos"] == int(y[:400].sum()) and out["evaluado"]
    assert out["modelos"]["m"]["ap"]["lo"] <= out["modelos"]["m"]["ap"]["punto"] <= out["modelos"]["m"]["ap"]["hi"]
    assert "delta_ap_vs_base" in out
    todas = te.assign(horizonte_e_dudoso=True)
    assert R.sensibilidad_horizonte_dudoso(todas, y, {"m": p, "baseline_tasa": p}, "m", 100)["evaluado"] is False
