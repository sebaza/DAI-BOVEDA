"""Helpers of the T3 runner: model lists per cut, subgroup tables (small groups suppressed), paired comparisons and the
code version. No database."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("torch")
pytest.importorskip("sklearn")

from evaluation import run_t3 as R   # noqa: E402


def test_models_at_enrollment_have_no_academic_inputs():
    m0, m2 = R.modelos_de(0), R.modelos_de(2)
    assert not [m for m in m0 if m.endswith("_agg") or m == "nn_gru"]
    assert {"cox_agg", "dt_cb_agg", "nn_gru"} <= set(m2)
    assert set(m0) <= set(m2)


def test_subgroup_table_suppresses_small_groups_and_reports_calibration():
    n = 400
    rng = np.random.default_rng(0)
    d = pd.DataFrame({"tiempo": rng.integers(3, 15, n), "causa": rng.choice([0, 1, 2], n), "seguimiento_max": 15,
                      "cod_programa": np.where(np.arange(n) < 390, "A", "B")})
    F = rng.random((n, 18))
    F = np.sort(F, axis=1)
    t = R.tabla_subgrupo(d, F, 2, 12, "cod_programa", 30)
    assert [r["grupo"] for r in t] == ["A"]                             # B has 10 rows < 30
    assert t[0]["n"] == 390
    assert t[0]["brecha_calibracion"] == pytest.approx(t[0]["incidencia_predicha"] - t[0]["incidencia_observada"])


def test_subgroup_table_only_counts_episodes_followed_up_to_the_horizon():
    d = pd.DataFrame({"tiempo": [5, 6, 7, 8], "causa": [1, 1, 1, 1], "seguimiento_max": [8, 8, 11, 14],
                      "g": ["a"] * 4})
    F = np.full((4, 18), 0.5)
    t = R.tabla_subgrupo(d, F, 2, 12, "g", 1)
    assert t[0]["n"] == 1                                               # only the episode with follow-up 14 reaches slot 12


def test_paired_comparisons_use_only_models_that_were_trained():
    pares = R.pares_t3(2, "cox_agg", ["km_global", "km_programa", "cox_adm", "cox_agg", "nn_gru"])
    assert ("km_programa", "km_global") in pares and ("nn_gru", "cox_agg") in pares
    assert all(a != b for a, b in pares)
    assert not [p for p in pares if "dt_cb_agg" in p]


def test_code_version_is_a_stable_sha256():
    v = R.version_codigo_t3()
    assert len(v) == 64 and v == R.version_codigo_t3()


def _snap_pc(n=60):
    rng = np.random.default_rng(1)
    d = pd.DataFrame({
        "k": 2, "split": np.where(np.arange(n) < 30, "train", "test"),
        "causa": rng.choice([0, 1, 2], n), "tiempo": rng.integers(3, 15, n), "seguimiento_max": 15,
        "duracion_nominal": 10.0, "cohorte_anio": 2019, "cod_programa": "A", "via_clase": "regular", "sexo_equidad": "F",
        "trayectoria_plan_comun": np.arange(n) % 3 == 0,
        "episodio_especialidad_id": np.where(np.arange(n) % 6 == 0, 1000 + np.arange(n), np.nan)})
    return d


def test_plan_comun_subgroup_is_reported_and_small_groups_are_suppressed():
    d = _snap_pc()
    t = d[d["split"] == "test"].reset_index(drop=True)
    F = np.sort(np.random.default_rng(0).random((len(t), 18)), axis=1)
    g = R.subgrupos(t, F, 2)["plan_comun"]
    assert {r["grupo"] for r in g} == {"plan_comun", "otras_trayectorias"} and all(r["n"] >= 10 for r in g)
    chico = t.iloc[:25].reset_index(drop=True)                          # fewer than 10 Plan Comun rows: suppressed
    g2 = R.subgrupos(chico, F[:25], 2)["plan_comun"]
    assert all(r["n"] >= 10 for r in g2) and "plan_comun" not in {r["grupo"] for r in g2}


def test_descriptive_plan_comun_counts_linked_and_unlinked_trajectories():
    d = _snap_pc()
    d0 = pd.concat([d.assign(k=0), d.assign(k=2), d.assign(k=4)], ignore_index=True)
    out = R.descriptivo_plan_comun(d0)
    x = out["2"]["train"]
    assert x["unidas"]["n"] + x["sin_continuacion"]["n"] == int(((d["split"] == "train") & d["trayectoria_plan_comun"]).sum())
    assert x["unidas"]["egreso"] + x["unidas"]["salida"] + x["unidas"]["censura"] == x["unidas"]["n"]
