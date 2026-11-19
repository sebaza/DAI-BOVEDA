"""T3 models on synthetic data: person-period expansion, cumulative incidence from discrete hazards, Aalen-Johansen by
program, cause-specific Cox, person-period logistic / CatBoost, and the neural competing-risks networks (likelihood,
shapes, determinism, learning). No database."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")
torch = pytest.importorskip("torch")

from models import t3_data as TD          # noqa: E402
from models import t3_discreto as DT      # noqa: E402
from models import t3_redes as NR         # noqa: E402
from models import t3_supervivencia as SV  # noqa: E402
from models.data import Preprocesador     # noqa: E402

K = 2


def sintetico(n=900, seed=0, k=K):
    """Egress hazard rises with ``x``; exits are independent of it. Times after the cut in 1..JMAX-k."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    h1 = np.clip(0.10 * np.exp(0.9 * x), 0.005, 0.5)
    h2 = np.full(n, 0.05)
    t1 = rng.geometric(h1)
    t2 = rng.geometric(h2)
    U = TD.JMAX - k
    u = np.minimum(np.minimum(t1, t2), U)
    causa = np.where(np.minimum(t1, t2) > U, 0, np.where(t1 <= t2, 1, 2))
    df = pd.DataFrame({"x": x, "duracion_nominal": 10.0, "cod_programa": np.where(x > 0, "A", "B"),
                       "u": u, "tiempo": u + k, "causa": causa, "split": "train", "k": k,
                       "persona_key": [f"p{i}" for i in range(n)], "episodio_id": np.arange(n)})
    return df


# ---------------------------------------------------------------------------------------------
# discrete time
# ---------------------------------------------------------------------------------------------
def test_person_period_expansion():
    df = pd.DataFrame({"tiempo": [3, 5], "causa": [1, 0]})
    fila, j, y = TD.expandir_persona_periodo(df, K)
    assert fila.tolist() == [0, 1, 1, 1] and j.tolist() == [3, 3, 4, 5] and y.tolist() == [1, 0, 0, 0]
    df2 = pd.DataFrame({"tiempo": [6, 4], "causa": [2, 1]})
    fila, j, y = TD.expandir_persona_periodo(df2, K)
    assert fila.tolist() == [0] * 4 + [1] * 2 and j.tolist() == [3, 4, 5, 6, 3, 4] and y.tolist() == [0, 0, 0, 2, 0, 1]


def test_expansion_rejects_rows_not_at_risk_after_the_cut():
    with pytest.raises(ValueError):
        TD.expandir_persona_periodo(pd.DataFrame({"tiempo": [2], "causa": [1]}), K)


def test_cumulative_incidences_from_constant_hazards():
    h1, h2 = np.full((1, 3), 0.1), np.full((1, 3), 0.2)
    r = TD.cif_desde_riesgos(h1, h2)
    assert r["F1"][0] == pytest.approx([0.1, 0.1 + 0.7 * 0.1, 0.1 + 0.7 * 0.1 + 0.49 * 0.1])
    assert r["F2"][0] == pytest.approx([0.2, 0.2 + 0.7 * 0.2, 0.2 + 0.7 * 0.2 + 0.49 * 0.2])
    assert (r["F1"] + r["F2"] + r["S"])[0] == pytest.approx([1.0, 1.0, 1.0])


def test_no_forbidden_feature_in_the_feature_sets():
    for num, cat in TD.GRUPOS.values():
        TD.verificar_sin_fuga(num, cat)
        assert not set(num + cat) & {"sexo_equidad", "tiempo", "causa", "seguimiento_max", "tiempo_titulacion"}
    with pytest.raises(ValueError):
        TD.verificar_sin_fuga(["x", "sexo_equidad"], [])
    with pytest.raises(ValueError):
        TD.verificar_sin_fuga(["tiempo"], [])
    assert set(TD.ADM_NUM) < set(TD.AGG_NUM)
    with pytest.raises(ValueError):
        TD.verificar_sin_fuga(["cohorte_anio"], [])                  # a numeric admission year cannot be learned out of time
    assert "cohorte_anio" not in set(TD.AGG_NUM) | set(TD.ADM_CAT)


def test_feature_sets_only_use_snapshot_columns():
    from pipelines.snapshots import features_t3 as F3

    for num, cat in TD.GRUPOS.values():
        assert set(num + cat) <= set(F3.SNAPSHOT_COLS_T3)


# ---------------------------------------------------------------------------------------------
# classical
# ---------------------------------------------------------------------------------------------
def test_aalen_johansen_by_program_falls_back_to_the_pooled_estimate_for_small_programs():
    df = sintetico(400)
    df.loc[:4, "cod_programa"] = "RARO"
    m = SV.AJPrograma(TD.JMAX - K, programa=True, min_n=50).fit(df)
    f = m.predict(df.iloc[:6])
    pooled = SV.AJPrograma(TD.JMAX - K, programa=False).fit(df).predict(df.iloc[:1])[0]
    assert f[0] == pytest.approx(pooled)                       # RARO has 5 rows < 50
    assert not np.allclose(f[5], pooled)                        # a large program has its own curve
    assert (np.diff(f, axis=1) >= -1e-12).all() and f.max() <= 1.0


def test_cox_ranks_the_high_hazard_group_higher():
    pytest.importorskip("lifelines")
    df = sintetico(800)
    X = df[["x"]].to_numpy()
    m = SV.CoxCausaEspecifica(TD.JMAX - K, penalizador=0.01).fit(X, df["u"].to_numpy(), df["causa"].to_numpy())
    f = m.predict(np.array([[-1.5], [0.0], [1.5]]))
    assert f.shape == (3, TD.JMAX - K)
    assert (f[2] > f[1]).all() and (f[1] > f[0]).all()
    assert (np.diff(f, axis=1) >= -1e-12).all() and f.max() <= 1.0 and f.min() >= 0.0


def test_person_period_logistic_learns_the_covariate_and_gives_monotone_curves():
    df = sintetico(900)
    tr, va = df.iloc[:600].reset_index(drop=True), df.iloc[600:].reset_index(drop=True)
    prep = Preprocesador(["x", "duracion_nominal"], ["cod_programa"], min_count=5).fit(tr)
    m, info = DT.logistica_ajustar(prep, tr, va, K, grid_c=(0.1, 1.0))
    f = DT.logistica_cif(m, prep, pd.DataFrame({"x": [-1.5, 1.5], "duracion_nominal": 10.0, "cod_programa": ["B", "A"]}), K)
    assert f.shape == (2, TD.JMAX - K) and (f[1] > f[0]).all()
    assert (np.diff(f, axis=1) >= -1e-12).all()
    assert info["C"] in (0.1, 1.0) and info["filas_persona_periodo"] == int(tr["u"].sum())


def test_catboost_person_period_smoke():
    pytest.importorskip("catboost")
    df = sintetico(600, seed=2)
    tr, va = df.iloc[:400].reset_index(drop=True), df.iloc[400:].reset_index(drop=True)
    prep = Preprocesador(["x", "duracion_nominal"], ["cod_programa"], min_count=5).fit(tr)
    old = dict(DT.CB_PARAMS)
    DT.CB_PARAMS.update(iterations=60, early_stopping_rounds=20, thread_count=2)
    try:
        m, info = DT.catboost_ajustar(prep, tr, va, K, seed=0)
    finally:
        DT.CB_PARAMS.clear()
        DT.CB_PARAMS.update(old)
    f = DT.catboost_cif([m], prep, pd.DataFrame({"x": [-1.5, 1.5], "duracion_nominal": 10.0, "cod_programa": ["B", "A"]}), K)
    assert f.shape == (2, TD.JMAX - K) and f[1, -1] > f[0, -1]


# ---------------------------------------------------------------------------------------------
# neural
# ---------------------------------------------------------------------------------------------
def test_nll_counts_every_observed_semester_with_the_class_of_the_last_one():
    logits = torch.zeros(2, 5, 3)
    u = torch.tensor([2, 4])
    causa = torch.tensor([1, 0])
    assert float(NR.nll(logits, u, causa)) == pytest.approx((2 + 4) / 2 * np.log(3))
    sesgado = torch.zeros(1, 3, 3)
    sesgado[0, :, 0] = 2.0
    p = torch.softmax(sesgado, dim=2)[0]
    esperado = -(torch.log(p[0, 0]) + torch.log(p[1, 0]) + torch.log(p[2, 2]))
    assert float(NR.nll(sesgado, torch.tensor([3]), torch.tensor([2]))) == pytest.approx(float(esperado))


def _conjunto(df, k=K, con_seq=False):
    X = df[["x"]].to_numpy("float32")
    cats = (df["cod_programa"] == "A").astype("int64").to_numpy()[:, None] + 1
    seq = np.repeat(X[:, None, :], k, axis=1) if con_seq else None
    return NR.ConjuntoT3(X, cats, df["u"].to_numpy(), df["causa"].to_numpy(), seq)


def test_network_shapes_determinism_and_learning():
    df = sintetico(1200, seed=1)
    tr, va = df.iloc[:900].reset_index(drop=True), df.iloc[900:].reset_index(drop=True)
    U = TD.JMAX - K
    ctr, cva = _conjunto(tr), _conjunto(va)
    dev = torch.device("cpu")
    r1 = NR.entrenar(ctr, cva, [3], U, seed=0, device=dev)
    r2 = NR.entrenar(ctr, cva, [3], U, seed=0, device=dev)
    f1 = NR.predecir_cif(r1["model"], cva, dev)
    f2 = NR.predecir_cif(r2["model"], cva, dev)
    assert f1.shape == (len(va), U) and np.allclose(f1, f2)                 # same seed, same network
    assert (np.diff(f1, axis=1) >= -1e-9).all() and f1.min() >= 0 and f1.max() <= 1
    sin_entrenar = NR.RedRiesgos(1, [3], U)
    base = NR._nll_valid(sin_entrenar.to(dev), cva, dev)
    assert r1["nll_valid"] < base                                           # it learned something
    hi = va["x"].to_numpy() > 0.5
    assert f1[hi, -1].mean() > f1[~hi & (va["x"].to_numpy() < -0.5), -1].mean()


def test_gru_variant_trains_and_uses_the_sequence_input():
    df = sintetico(600, seed=4)
    tr, va = df.iloc[:450].reset_index(drop=True), df.iloc[450:].reset_index(drop=True)
    U = TD.JMAX - K
    dev = torch.device("cpu")
    r = NR.entrenar(_conjunto(tr, con_seq=True), _conjunto(va, con_seq=True), [3], U, seed=0, device=dev)
    f = NR.predecir_cif(r["model"], _conjunto(va, con_seq=True), dev)
    assert f.shape == (len(va), U) and r["n_parametros"] > 0
    assert r["model"].gru is not None


# ---------------------------------------------------------------------------------------------
# sequences and P58-robust feature sets
# ---------------------------------------------------------------------------------------------
def _semestres():
    filas = []
    for e in (1, 2):
        for j in range(1, 5):
            filas.append({"episodio_id": e, "j": j, "matriculado": True, "interrupcion": False,
                          "intentos_evaluados": 0 if (e == 1 and j == 2) else 5, "aprobados": 0 if (e == 1 and j == 2) else 4,
                          "reprobados": 1, "convalidaciones": 0, "creditos_aprobados": 24.0 + 100 * j + (1000 if e == 2 else 0),
                          "cursos_verano_invierno": 0, "promedio": np.nan if (e == 1 and j == 2) else 5.0,
                          "n_notas_promedio": 4, "creditos_acumulados": 10.0 * j})
    return pd.DataFrame(filas)


def test_t3_sequences_use_only_slots_up_to_k_and_do_not_depend_on_attempts():
    sem = _semestres()
    snap = pd.DataFrame({"episodio_id": [2, 1]})
    x = TD.construir_secuencias_t3(snap, sem, 2)
    assert x.shape == (2, 2, len(TD.SEQ_COLS_T3))
    ci = TD.SEQ_COLS_T3.index("creditos_aprobados")
    assert x[0, 1, ci] == pytest.approx((24.0 + 200 + 1000) / 30.0)                   # row 0 is episode 2, slot 2
    sem3 = sem.copy()
    sem3["intentos_evaluados"], sem3["aprobados"], sem3["reprobados"] = 0, 0, 0
    sem3["promedio"] = np.nan                                                           # P58-like: attempts and grades vanish
    assert np.array_equal(x, TD.construir_secuencias_t3(snap, sem3, 2))
    sem2 = sem.copy()
    sem2.loc[sem2["j"] > 2, "creditos_aprobados"] = 999.0                               # later slots never enter
    assert np.array_equal(x, TD.construir_secuencias_t3(snap, sem2, 2))
    assert not {"intentos_evaluados", "aprobados", "reprobados"} & set(TD.SEQ_COLS_T3)


def test_model_feature_sets_leave_out_the_attempt_counts_and_the_last_semester_trio():
    modelo = set(TD.AGG_NUM)
    assert {"creditos_aprobados", "tasa_aprobacion", "avance_malla"} <= modelo
    assert not modelo & {"intentos_evaluados", "aprobados", "reprobados", "n_notas_promedio", "intentos_ult_semestre",
                         "tasa_ult_semestre", "promedio_ult_semestre", "n_sem_sin_reprobacion"}
