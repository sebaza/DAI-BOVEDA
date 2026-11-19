"""T6 runner: viability gate, event counts per horizon, strata of the descriptive tables and the model-keeping rule.
Pure functions only (no database, no training)."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("lifelines")

from evaluation import run_t6 as RUN                     # noqa: E402


def _snap():
    # split, seguimiento, tiempo, evento
    filas = []
    for sp, n, seg, ev in (("train", 400, 12, 40), ("valid", 200, 6, 30), ("test", 300, 3, 35)):
        for i in range(n):
            e = 1 if i < ev else 0
            filas.append({"split": sp, "seguimiento": seg, "evento": e, "tiempo": 1 + (i % seg) if e else seg,
                          "persona_key": f"{sp}{i}", "cod_programa": "A", "sexo_equidad": "F" if i % 2 else "M",
                          "promedio_evaluado": 4.0 + (i % 30) / 10, "exceso_duracion": (i % 5) - 2.0,
                          "titulado_al_corte": bool(i % 3 == 0), "anio_egreso": 2020 + i % 4})
    return pd.DataFrame(filas)


def test_events_per_split_and_per_horizon_use_complete_follow_up():
    s = _snap()
    assert RUN.eventos_por_particion(s) == {"train": 40, "valid": 30, "test": 35}
    h = RUN.eventos_por_horizonte(s, (2, 4, 8))
    assert h[2]["train"]["n"] == 400 and h[2]["test"]["n"] == 300
    assert h[4]["test"]["n"] == 0 and h[4]["test"]["eventos"] == 0           # test follow-up is 3 semesters
    assert h[8]["valid"]["n"] == 0 and h[8]["train"]["n"] == 400
    assert h[2]["test"]["eventos"] == int(((s.split == "test") & (s.evento == 1) & (s.tiempo <= 2)).sum())


def test_viability_decision_is_explicit_about_each_model_family():
    v = RUN.viabilidad({"train": 50, "valid": 34, "test": 58})
    assert v["clasico"] is True and v["catboost"] is False and v["red"] is False
    assert v["umbrales"] == {"clasico": 30, "catboost": 100, "red": 300}
    v = RUN.viabilidad({"train": 15, "valid": 32, "test": 8})
    assert v["clasico"] is False and v["catboost"] is False
    v = RUN.viabilidad({"train": 400, "valid": 120, "test": 150})
    assert v["clasico"] and v["catboost"] and not v["red"]


def test_strata_for_the_descriptive_tables():
    s = _snap()
    e = RUN.estratos(s)
    assert set(e) == {"sexo", "anio_egreso", "titulado_al_corte", "promedio", "duracion"}
    assert set(e["promedio"].dropna().unique()) == {"T1 (más bajo)", "T2", "T3 (más alto)"}
    assert set(e["duracion"].dropna().unique()) <= {"en la duración nominal o antes", "con atraso"}
    assert e["promedio"].isna().sum() == 0 and len(e["sexo"]) == len(s)


def test_a_model_replaces_the_baseline_only_when_the_paired_interval_is_above_zero():
    assert RUN.decidir_conservado("cox_agg", {"punto": 0.02, "lo": 0.001, "hi": 0.04}) == "cox_agg"
    assert RUN.decidir_conservado("cox_agg", {"punto": 0.02, "lo": -0.01, "hi": 0.05}) == "baseline_programa"
    assert RUN.decidir_conservado("cox_agg", None) == "baseline_programa"
    assert RUN.decidir_conservado(None, {"punto": 0.5, "lo": 0.4, "hi": 0.6}) == "baseline_programa"
    assert RUN.decidir_conservado("cox_agg", {"punto": 0.02, "lo": float("nan"), "hi": float("nan")}) == "baseline_programa"


# ---------------------------------------------------------------------------------------------
# stage B (P86): the postgrado STATE source is the primary event; the enrollment-status source is the sensitivity run
# ---------------------------------------------------------------------------------------------
def _snap_estados():
    s = _snap()
    n = len(s)
    rng = np.random.default_rng(0)
    s["evento_estados"] = (rng.random(n) < 0.2).astype(int)
    s["tiempo_estados"] = np.where(s["evento_estados"] == 1, 1, s["seguimiento"])
    s["previo_estados"] = rng.random(n) < 0.05
    s["nivel_estados"] = np.where(s["evento_estados"] == 1, rng.choice(["magister", "doctorado", "otro"], n), None)
    return s


def test_the_primary_event_comes_from_the_state_source_without_prior_enrollment():
    s = _snap_estados()
    d = RUN.con_evento(s, "estados")
    assert len(d) == int((~s["previo_estados"]).sum())                    # a prior enrollment is not at risk of a FIRST one (D65)
    assert d["evento"].sum() == s.loc[~s["previo_estados"], "evento_estados"].sum()
    assert (d["tiempo"] == s.loc[~s["previo_estados"], "tiempo_estados"].to_numpy()).all()
    assert RUN.FUENTE_PRINCIPAL == "estados"


def test_the_previous_source_is_kept_untouched_as_the_sensitivity_run():
    s = _snap_estados()
    pd.testing.assert_frame_equal(RUN.con_evento(s, "matricula"), s)
    with pytest.raises(ValueError):
        RUN.con_evento(s, "otra")


def test_events_by_level_and_cause_specific_incidence_count_each_level_once():
    s = RUN.con_evento(_snap_estados(), "estados")
    n = RUN.eventos_por_nivel(s)
    assert sum(n["total"].values()) == int(s["evento"].sum())
    assert set(n["total"]) <= {"magister", "doctorado", "otro"}
    assert sum(sum(v.values()) for v in n["por_particion"].values()) == int(s["evento"].sum())
    assert not any(0 < x < 10 for v in n["por_particion"].values() for x in v.values())      # small cells are hidden (none shown as 1-9)
