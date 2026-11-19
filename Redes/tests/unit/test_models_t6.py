"""T6 models: feature sets without leakage, baseline by program, penalized Cox. No database."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("lifelines")

from evaluation import metrics_t6 as M6                  # noqa: E402
from models import t6_data as TD                         # noqa: E402
from models import t6_modelos as MD                      # noqa: E402
from pipelines.snapshots import features_t6 as F6        # noqa: E402


def test_feature_sets_never_contain_sex_cohort_year_of_egress_or_labels():
    for nombre, (num, cat) in TD.GRUPOS.items():
        TD.verificar_sin_fuga(num, cat)
        assert not TD.PROHIBIDAS & (set(num) | set(cat)), nombre
    for malo in ("sexo_equidad", "sexo", "cohorte_anio", "anio_egreso", "tiempo", "evento", "seguimiento",
                 "evento_cualquier_fila", "tiempo_cualquier_fila", "episodio_especialidad_id", "split", "persona_key"):
        with pytest.raises(ValueError):
            TD.verificar_sin_fuga([malo], [])
        with pytest.raises(ValueError):
            TD.verificar_sin_fuga([], [malo])


def test_every_model_feature_is_a_snapshot_feature_or_the_static_faculty():
    permitidas = set(F6.FEATURE_COLS_T6) | {"facultad"} | set(F6.F.ADMISION_P47)      # stage B: mm_* + the test
    for num, cat in TD.GRUPOS.values():
        assert set(num) | set(cat) <= permitidas
    assert set(TD.GRUPOS["perfil"][0]) < set(TD.GRUPOS["perfil+academico"][0])
    assert {"titulado_al_corte", "exceso_duracion", "promedio_evaluado"} <= set(TD.GRUPOS["perfil+academico"][0])
    assert "promedio_evaluado" not in TD.GRUPOS["perfil"][0]
    # the attempt counts and the last-semester trio are out (P58)
    assert not {"intentos_evaluados", "reprobados", "tasa_ult_semestre"} & set(TD.GRUPOS["perfil+academico"][0])


def _datos(n=1200, seed=0):
    rng = np.random.default_rng(seed)
    prog = rng.choice(["A", "B", "C", "RARO"], size=n, p=[0.45, 0.35, 0.17, 0.03])
    x = rng.normal(size=n)
    base = np.where(prog == "A", 0.02, np.where(prog == "B", 0.12, 0.05))
    lam = base * np.exp(0.9 * x)
    t_ev = rng.geometric(np.clip(lam, 1e-4, 0.9))
    seg = rng.integers(2, 9, n)
    ev = (t_ev <= seg).astype(int)
    t = np.where(ev == 1, t_ev, seg)
    return pd.DataFrame({"cod_programa": prog, "x": x, "tiempo": t, "evento": ev, "seguimiento": seg})


def test_baseline_by_program_equals_the_program_kaplan_meier_and_falls_back_to_the_pooled_one():
    d = _datos()
    m = MD.BaselinePrograma((2, 4), min_n=50).fit(d)
    pred = m.predict(d)
    a = d[d["cod_programa"] == "A"]
    esperado = M6.incidencia_acumulada(a["tiempo"], a["evento"], [2, 4])
    assert pred[(d["cod_programa"] == "A").to_numpy()][0] == pytest.approx(esperado)
    pooled = M6.incidencia_acumulada(d["tiempo"], d["evento"], [2, 4])
    assert pred[(d["cod_programa"] == "RARO").to_numpy()][0] == pytest.approx(pooled)   # fewer than min_n rows
    assert (np.diff(pred, axis=1) >= -1e-12).all()


def test_baseline_predicts_unseen_programs_with_the_pooled_incidence():
    d = _datos()
    m = MD.BaselinePrograma((2, 4), min_n=50).fit(d)
    nuevo = d.head(3).assign(cod_programa="NUEVO")
    assert m.predict(nuevo)[0] == pytest.approx(M6.incidencia_acumulada(d["tiempo"], d["evento"], [2, 4]))


def test_cox_orders_by_the_covariate_and_the_incidence_grows_with_the_horizon():
    d = _datos(n=2500)
    X = d[["x"]].to_numpy("float64")
    m = MD.CoxT6((2, 4, 8), penalizador=0.01).fit(X, d["tiempo"].to_numpy(), d["evento"].to_numpy())
    p = m.predict(X)
    assert p.shape == (len(d), 3) and ((p >= 0) & (p <= 1)).all()
    assert (np.diff(p, axis=1) >= -1e-12).all()
    assert np.corrcoef(p[:, 0], d["x"])[0, 1] > 0.5
    assert m.n_variables() == 1


def test_cox_drops_constant_columns_and_a_stronger_penalty_shrinks_the_effect():
    d = _datos(n=2500)
    X = np.column_stack([d["x"].to_numpy(), np.ones(len(d))])
    debil = MD.CoxT6((2, 4), penalizador=0.001).fit(X, d["tiempo"].to_numpy(), d["evento"].to_numpy())
    fuerte = MD.CoxT6((2, 4), penalizador=100.0).fit(X, d["tiempo"].to_numpy(), d["evento"].to_numpy())
    assert debil.n_variables() == 1
    assert np.std(fuerte.predict(X)[:, 0]) < np.std(debil.predict(X)[:, 0])


def test_the_penalty_is_chosen_on_validation_and_returned_with_the_search():
    tr, va = _datos(n=2000, seed=1), _datos(n=1200, seed=2)
    m, info = MD.ajustar_cox((2, 4), tr[["x"]].to_numpy("float64"), tr["tiempo"].to_numpy(), tr["evento"].to_numpy(),
                             va[["x"]].to_numpy("float64"), va["tiempo"].to_numpy(), va["evento"].to_numpy(),
                             grid=(0.001, 0.1, 10.0), tau=4)
    assert info["penalizador"] in (0.001, 0.1, 10.0) and len(info["busqueda"]) == 3
    assert info["c_valid"] == max(b["c_valid"] for b in info["busqueda"])
    assert m.penalizador == info["penalizador"]
