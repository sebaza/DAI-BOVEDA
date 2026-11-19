"""T3 snapshot ("tiempo hasta titulacion"): pure rules, event resolution (egress / competing exit / censoring), eligibility
funnel, point-in-time features and the perturbation leakage guards. No database."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.marts.rules import base_ordinal                    # noqa: E402
from pipelines.snapshots import features_t3 as F3                  # noqa: E402
from pipelines.snapshots import rules as R                         # noqa: E402
from pipelines.snapshots import rules_t3 as R3                     # noqa: E402

LATEST = "202620"      # in progress; the last CLOSED regular period is 202610


def per(adm: str, j: int) -> str:
    """Regular period of slot ``j`` (1 = admission semester) for an admission period."""
    return R.ordinal_a_periodo(base_ordinal(adm) + j - 1)


# ---------------------------------------------------------------------------------------------
# pure rules
# ---------------------------------------------------------------------------------------------
def test_last_closed_period_is_the_regular_period_before_the_latest():
    assert R3.periodo_cierre("202620") == "202610"
    assert R3.periodo_cierre("202610") == "202520"
    assert R3.periodo_cierre("202615") is None


def test_follow_up_slots_are_counted_from_the_admission_semester():
    assert R3.slot_cierre("201610", "202620") == 21          # 201610 .. 202610
    assert R3.slot_cierre("201620", "202620") == 20
    assert R3.slot_cierre("201601", "202620") == 21          # non-regular admission maps to its semester
    assert R3.slot_cierre("202610", "202620") == 1
    assert R3.slot_cierre("202620", "202620") == 0


def test_split_is_by_admission_cohort():
    assert [R3.split_cohorte(a) for a in (2014, 2015, 2017, 2018, 2019, 2020, 2021)] == [
        "anterior", "train", "train", "valid", "test", "test", "posterior"]


@pytest.mark.parametrize("args,esperado", [
    ((11, None, 12, 18), (11, 1, None)),                            # egress inside the follow-up
    ((19, None, 17, 18), (18, 0, None)),                            # egress after the closed periods: censored
    ((7, 6, 9, 18), (7, 1, None)),                                  # egress wins over an earlier exit state
    ((None, 6, 5, 18), (6, 2, "explicita")),                        # explicit definitive exit
    ((None, None, 5, 18), (6, 2, "ausencia")),                      # sustained absence: one slot after the last activity
    ((None, None, 18, 18), (18, 0, None)),                          # active until the last closed period
    ((None, None, 17, 18), (18, 0, None)),                          # absent in only one closed period: not yet an exit
    ((None, None, 16, 18), (17, 2, "ausencia")),                    # absent in the last two closed periods
    ((19, None, 5, 18), (18, 0, None)),                             # an egress exists (late): never an absence
    ((None, 19, 5, 18), (18, 0, None)),                             # exit state after the closed periods: censored
    ((None, 18, 18, 18), (18, 2, "explicita")),                     # exit exactly at the limit is observed
])
def test_event_resolution(args, esperado):
    t_eg, t_sal, t_act, t_max = args
    assert R3.resolver_evento(t_eg, t_sal, t_act, t_max) == esperado


def test_event_resolution_caps_the_window():
    assert R3.resolver_evento(None, None, None, 23) == (20, 0, None)
    assert R3.resolver_evento(21, None, None, 23) == (20, 0, None)
    assert R3.resolver_evento(20, None, None, 23) == (20, 1, None)
    assert R3.resolver_evento(None, 22, 5, 23) == (20, 0, None)               # an exit past the window is censored there


def test_vectorized_resolution_equals_the_scalar_rule_on_a_grid():
    import itertools

    nan = float("nan")
    filas = [dict(t_egreso=a, t_salida_def=b, ultima_actividad=c, t_max=m)
             for a, b, c, m in itertools.product([nan, 3, 9, 20, 22], [nan, 2, 9, 21, 23], [nan, 1, 8, 19, 22], [5, 21, 23])]
    h = pd.DataFrame(filas)
    h["t_titulacion"] = nan
    out = F3.resolver_eventos(h)
    for i, f in enumerate(filas):
        esperado = R3.resolver_evento(f["t_egreso"], f["t_salida_def"], f["ultima_actividad"], f["t_max"])
        assert (out.iloc[i]["tiempo"], out.iloc[i]["causa"], out.iloc[i]["salida_tipo"]) == esperado, f


# ---------------------------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------------------------
def episodios(*rows):
    cols = ["episodio_id", "persona_key", "cod_programa", "periodo_admision", "cod_admision", "id_nivel", "sede",
            "tipo_qualitas", "sexo", "catalogo_inicial"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)


def ep(eid, persona=None, adm="201610", prog="C1", cod="LS", nivel=1, cat="2019"):
    return (eid, persona or f"p{eid}", prog, adm, cod, nivel, 1, "1. Ingreso Regular o Centralizada", "F", cat)


def estados(*rows):
    """(persona, episodio_id, periodo, cod_estado)."""
    out = [{"persona_key": p, "episodio_id": e, "periodo": per_, "cod_estado": c, "cod_programa": "C1",
            "catalogo": "2019", "es_correccion_sistema": False, "orden_canonico": i + 1}
           for i, (p, e, per_, c) in enumerate(rows)]
    df = pd.DataFrame(out, columns=["persona_key", "episodio_id", "periodo", "cod_estado", "cod_programa", "catalogo",
                                    "es_correccion_sistema", "orden_canonico"])
    df["episodio_id"] = df["episodio_id"].astype("Int64")
    return df


def matriculado(eid, adm, desde, hasta, persona=None):
    persona = persona or f"p{eid}"
    return [(persona, eid, per(adm, j), "M") for j in range(desde, hasta + 1)]


def intentos(*rows):
    """(episodio_id, periodo, nota|'DPA', codigo)."""
    out = []
    for i, (eid, periodo, nota, codigo) in enumerate(rows):
        tipo = "convalidacion" if nota == "DPA" else "evaluado"
        ev = tipo == "evaluado"
        out.append({"intento_id": i + 1, "episodio_id": eid, "periodo": periodo, "codigo_asignatura": codigo,
                    "es_intento_evaluado": ev, "nota_numerica": float(nota) if ev else np.nan,
                    "nota_es_heredada": False, "resultado_tipo": tipo,
                    "aprobado_curricular": (float(nota) >= 4.0) if ev else True, "creditos": 6.0,
                    "creditos_reconocidos": np.nan if ev else 6.0})
    return pd.DataFrame(out, columns=["intento_id", "episodio_id", "periodo", "codigo_asignatura",
                                      "es_intento_evaluado", "nota_numerica", "nota_es_heredada", "resultado_tipo",
                                      "aprobado_curricular", "creditos", "creditos_reconocidos"])


NO_INTENTOS = intentos()
NO_EGRESO = pd.DataFrame({"persona_key": [], "episodio_id": [], "periodo": []})
NO_VIA = pd.DataFrame(columns=["postulacion_via_id", "year_admision", "persona_key", "cod_carrera", "cod_admision",
                               "preferencia", "matricula", "puntaje_leng", "puntaje_mat", "puntaje_ciencias",
                               "puntaje_historia", "puntaje_nem", "puntaje_ranking", "notas_em", "ponderado",
                               "tipo_colegio", "depend_colegio", "region_colegio"])
MALLA = pd.DataFrame([("C1", "2019", "A", 1, 6.0), ("C1", "2019", "B", 1, 6.0), ("C1", "2019", "C", 2, 6.0),
                      ("C1", "2019", "D", 5, 6.0)],
                     columns=["cod_programa", "catalogo", "codigo_asignatura", "semestre", "creditos"])
PROG_CAT = pd.DataFrame([("C1", "2019", 10)], columns=["cod_programa", "catalogo", "duracion"])


def construir(e, s, a=NO_INTENTOS, egreso=NO_EGRESO, malla=MALLA, prog_cat=PROG_CAT, ks=(0, 2, 4), latest=LATEST):
    return F3.construir_snapshot_t3(e, s, a, NO_VIA, egreso, malla, prog_cat, latest, ks)


def fila(snap, eid, k):
    r = snap[(snap["episodio_id"] == eid) & (snap["k"] == k)]
    assert len(r) == 1, (eid, k, len(r))
    return r.iloc[0]


def mundo():
    """A small world with one episode per situation (admission 201610; 21 slots of follow-up)."""
    adm = "201610"
    est = []
    eps = []
    # 1: egress at slot 5 (Z), enrolled until slot 4
    eps.append(ep(1)); est += matriculado(1, adm, 1, 4) + [("p1", 1, per(adm, 5), "Z")]
    # 2: explicit exit at slot 3 (E); enrolled in slots 1 and 2
    eps.append(ep(2)); est += matriculado(2, adm, 1, 2) + [("p2", 2, per(adm, 3), "E")]
    # 3: an exit state that is reversed (reintegro) and a later egress at slot 9: the exit is not definitive
    eps.append(ep(3)); est += matriculado(3, adm, 1, 2) + [("p3", 3, per(adm, 3), "E"), ("p3", 3, per(adm, 4), "I")] \
        + matriculado(3, adm, 5, 8) + [("p3", 3, per(adm, 9), "Z")]
    # 4: sustained absence after slot 3
    eps.append(ep(4)); est += matriculado(4, adm, 1, 3)
    # 5: interruption is not an exit; active until the last closed period
    eps.append(ep(5)); est += matriculado(5, adm, 1, 2) + [("p5", 5, per(adm, 3), "P"), ("p5", 5, per(adm, 4), "P")] \
        + matriculado(5, adm, 5, 21)
    # 6: the egress is recorded in the period in progress (202620): administratively censored
    eps.append(ep(6)); est += matriculado(6, adm, 1, 21) + [("p6", 6, "202620", "Z")]
    # 7: egress only through the titulacion table
    eps.append(ep(7)); est += matriculado(7, adm, 1, 8)
    # 8: graduated before the k = 2 cut
    eps.append(ep(8)); est += matriculado(8, adm, 1, 2) + [("p8", 8, per(adm, 2), "Z")]
    # 9: exit recorded in the cut period of k = 2
    eps.append(ep(9)); est += matriculado(9, adm, 1, 2) + [("p9", 9, per(adm, 2), "E")]
    # 10: cohort 2014 (before the window) and 11: a postgraduate episode
    eps.append(ep(10, adm="201410")); est += matriculado(10, "201410", 1, 4)
    eps.append(ep(11, nivel=8)); est += matriculado(11, adm, 1, 4)
    # 12: exit state at slot 6 and the egress at slot 7: the egress wins
    eps.append(ep(12)); est += matriculado(12, adm, 1, 5) + [("p12", 12, per(adm, 6), "E"), ("p12", 12, per(adm, 7), "Z")]
    egreso = pd.DataFrame({"persona_key": ["p7"], "episodio_id": [7], "periodo": [per(adm, 8)]})
    return episodios(*eps), estados(*est), egreso


# ---------------------------------------------------------------------------------------------
# labels, censoring and funnel
# ---------------------------------------------------------------------------------------------
def test_labels_times_and_causes():
    e, s, eg = mundo()
    snap, _, embudo = construir(e, s, egreso=eg)
    r = fila(snap, 1, 2)
    assert (r["tiempo"], r["causa"], r["seguimiento_max"]) == (5, R3.EGRESO, 21)
    r = fila(snap, 1, 4)
    assert (r["tiempo"], r["causa"]) == (5, R3.EGRESO)                          # still at risk at k = 4, one semester left
    r = fila(snap, 2, 2)
    assert (r["tiempo"], r["causa"], r["salida_tipo"]) == (3, R3.SALIDA, "explicita")
    r = fila(snap, 3, 2)
    assert (r["tiempo"], r["causa"]) == (9, R3.EGRESO)                          # the reversed exit is ignored
    r = fila(snap, 4, 2)
    assert (r["tiempo"], r["causa"], r["salida_tipo"]) == (4, R3.SALIDA, "ausencia")
    r = fila(snap, 5, 2)
    assert (r["tiempo"], r["causa"]) == (20, R3.CENSURA)                        # interruptions are not exits (window cap 20)
    r = fila(snap, 6, 2)
    assert (r["tiempo"], r["causa"]) == (20, R3.CENSURA)                        # egress in 202620: censored
    r = fila(snap, 7, 2)
    assert (r["tiempo"], r["causa"]) == (8, R3.EGRESO)                          # titulacion table only
    r = fila(snap, 12, 2)
    assert (r["tiempo"], r["causa"]) == (7, R3.EGRESO)


def test_eligibility_funnel_and_exclusions():
    e, s, eg = mundo()
    snap, _, embudo = construir(e, s, egreso=eg)
    por_k = {r["k"]: r for r in embudo}
    assert por_k[2]["poblacion"] == 10                                           # episodios 10 (2014) and 11 (nivel) are out
    assert por_k[2]["cohortes_anteriores_excluidas"] == 1
    assert 8 not in set(snap.loc[snap["k"] == 2, "episodio_id"])                 # already graduated at the cut
    assert por_k[2]["ya_egresado_o_titulado"] == 1
    assert 9 not in set(snap.loc[snap["k"] == 2, "episodio_id"])                 # exit recorded in the cut period
    assert por_k[2]["salida_en_corte"] == 1
    assert 2 not in set(snap.loc[snap["k"] == 4, "episodio_id"])                 # not enrolled at slot 4
    assert 4 not in set(snap.loc[snap["k"] == 4, "episodio_id"])
    assert por_k[2]["elegibles"] == len(snap[snap["k"] == 2])
    for r in embudo:
        assert r["poblacion"] - r["sin_matricula_en_corte"] - r["salida_en_corte"] - r["ya_egresado_o_titulado"] \
            - r["sin_seguimiento"] == r["elegibles"]


def test_k0_is_at_enrollment_and_keeps_the_early_events():
    e, s, eg = mundo()
    snap, _, _ = construir(e, s, egreso=eg)
    assert (fila(snap, 8, 0)["tiempo"], fila(snap, 8, 0)["causa"]) == (2, R3.EGRESO)   # graduated at slot 2
    assert (fila(snap, 9, 0)["tiempo"], fila(snap, 9, 0)["causa"]) == (2, R3.SALIDA)
    k0 = snap[snap["k"] == 0]
    assert (k0["creditos_aprobados"] == 0).all() and (k0["intentos_evaluados"] == 0).all()
    assert k0["creditos_esperados"].isna().all()


def test_time_after_the_cut_is_positive_for_every_row():
    e, s, eg = mundo()
    snap, _, _ = construir(e, s, egreso=eg)
    assert (snap["tiempo"] > snap["k"]).all()
    assert (snap["tiempo"] <= snap["seguimiento_max"]).all()
    assert (snap["tiempo"] <= R3.VENTANA_SLOTS).all()
    assert set(snap["causa"]) <= {0, 1, 2}


def test_titulacion_time_is_a_separate_endpoint():
    e, s, eg = mundo()
    adm = "201610"
    s = pd.concat([s, estados(("p1", 1, per(adm, 7), "U"))], ignore_index=True)
    snap, _, _ = construir(e, s, egreso=eg)
    assert fila(snap, 1, 2)["tiempo_titulacion"] == 7 and fila(snap, 1, 2)["tiempo"] == 5     # egress 5, title 7
    assert fila(snap, 7, 2)["tiempo_titulacion"] == 8
    assert pd.isna(fila(snap, 2, 2)["tiempo_titulacion"])


def test_transfer_to_another_program_is_flagged_for_exits_only():
    e, s, eg = mundo()
    adm = "201610"
    e = pd.concat([e, episodios(ep(20, persona="p2", prog="C2", adm=per(adm, 4)))], ignore_index=True)
    s = pd.concat([s, estados(("p2", 20, per(adm, 4), "N"), ("p2", 20, per(adm, 5), "M"))], ignore_index=True)
    snap, _, _ = construir(e, s, egreso=eg)
    assert fila(snap, 2, 2)["salida_a_otro_programa"] == True       # noqa: E712  (np.bool_)
    assert fila(snap, 4, 2)["salida_a_otro_programa"] == False      # noqa: E712
    assert pd.isna(fila(snap, 1, 2)["salida_a_otro_programa"])


def test_follow_up_depends_on_the_admission_semester():
    adm = "201620"
    e = episodios(ep(1, adm=adm))
    s = estados(*matriculado(1, adm, 1, 20))
    snap, _, _ = construir(e, s)
    r = fila(snap, 1, 2)
    assert (r["seguimiento_max"], r["tiempo"], r["causa"]) == (20, 20, R3.CENSURA)


# ---------------------------------------------------------------------------------------------
# features: program, P58, sex
# ---------------------------------------------------------------------------------------------
def test_program_features_and_malla_progress():
    adm = "201610"
    e = episodios(ep(1))
    s = estados(*matriculado(1, adm, 1, 5))
    a = intentos((1, per(adm, 1), 5.0, "A"), (1, per(adm, 1), 5.0, "B"), (1, per(adm, 2), 3.0, "C"),
                 (1, per(adm, 3), 5.0, "D"))
    snap, _, _ = construir(e, s, a)
    r = fila(snap, 1, 2)
    assert r["duracion_nominal"] == 10 and r["creditos_malla_total"] == 24.0 and r["malla_conocida"]
    assert r["creditos_esperados"] == 18.0 and r["creditos_aprobados"] == 12.0
    assert r["avance_malla"] == pytest.approx(12.0 / 18.0) and r["fraccion_malla"] == pytest.approx(0.5)
    r4 = fila(snap, 1, 4)
    assert r4["creditos_aprobados"] == 18.0                                   # D approved in slot 3 counts at k = 4
    assert r4["creditos_esperados"] == 18.0                                   # semestre 5 of the malla is beyond k = 4


def test_nominal_duration_falls_back_to_the_malla_and_unknown_malla_is_flagged():
    e = episodios(ep(1), ep(2, prog="X9"))
    s = estados(*matriculado(1, "201610", 1, 3), *matriculado(2, "201610", 1, 3))
    snap, _, _ = construir(e, s, prog_cat=PROG_CAT.iloc[0:0])
    assert fila(snap, 1, 2)["duracion_nominal"] == 5                          # max semestre of the malla
    r = fila(snap, 2, 2)
    assert not r["malla_conocida"] and np.isnan(r["duracion_nominal"]) and np.isnan(r["avance_malla"])


def test_periods_without_recorded_failures_keep_credits_but_not_pass_rates():
    adm = "201910"                                                            # slots: 201910, 201920, 202010, 202020
    e = episodios(ep(1, adm=adm))
    s = estados(*matriculado(1, adm, 1, 5))
    a = intentos((1, "201910", 3.0, "A"), (1, "201920", 4.0, "B"), (1, "202010", 4.0, "C"), (1, "202020", 3.0, "D"))
    snap, _, _ = construir(e, s, a)
    r = fila(snap, 1, 4)
    assert r["creditos_aprobados"] == 12.0                                    # B and C count as credits
    assert (r["intentos_evaluados"], r["aprobados"], r["reprobados"]) == (2, 0, 2)   # only A and D enter the rate
    assert r["n_sem_sin_reprobacion"] == 2
    assert fila(snap, 1, 2)["n_sem_sin_reprobacion"] == 1


def test_sex_is_only_for_fairness_and_labels_are_not_features():
    assert "sexo_equidad" in F3.SNAPSHOT_COLS_T3 and "sexo" not in F3.SNAPSHOT_COLS_T3
    modelo = set(F3.FEATURE_COLS_ADMISION) | set(F3.FEATURE_COLS_CAT) | set(F3.FEATURE_COLS_ACADEMICO)
    assert not modelo & F3.LABEL_COLS
    assert "sexo_equidad" not in modelo and "persona_key" not in modelo and "split" not in modelo


# ---------------------------------------------------------------------------------------------
# generic leakage guards: facts after the cut never change the features
# ---------------------------------------------------------------------------------------------
def _sintetico(seed=0, n=60):
    rng = np.random.default_rng(seed)
    adms = ["201510", "201520", "201610", "201710", "201810", "201910"]
    eps, est, filas = [], [], []
    for i in range(n):
        adm = str(rng.choice(adms))
        eid = i + 1
        eps.append(ep(eid, adm=adm))
        ult = int(rng.integers(2, 12))
        est += matriculado(eid, adm, 1, ult)
        for j in range(1, ult + 1):
            for c in rng.choice(list("ABCD"), size=int(rng.integers(0, 3)), replace=False):
                filas.append((eid, per(adm, j), float(np.round(rng.uniform(2, 7), 1)), str(c)))
        if rng.random() < 0.3:
            est.append((f"p{eid}", eid, per(adm, ult + 1), "E"))
        elif rng.random() < 0.3:
            est.append((f"p{eid}", eid, per(adm, ult + 1), "Z"))
        if rng.random() < 0.2:
            est.append((f"p{eid}", eid, per(adm, 2), "P"))
    return episodios(*eps), estados(*est), intentos(*filas)


FEATURES = [c for c in F3.SNAPSHOT_COLS_T3 if c not in
            {"episodio_id", "k", "persona_key", "periodo_admision", "split", "sexo_equidad", *F3.LABEL_COLS}]


def _comparar(a, b, k):
    a, b = a[a["k"] == k].set_index("episodio_id"), b[b["k"] == k].set_index("episodio_id")
    assert list(a.index) == list(b.index) and len(a) > 15
    for c in FEATURES:
        x, y = a[c], b[c]
        assert ((x == y) | (x.isna() & y.isna())).all(), c


@pytest.mark.parametrize("k", [2, 4])
def test_changing_facts_after_the_cut_never_changes_the_features(k):
    e, s, a = _sintetico()
    base, _, _ = construir(e, s, a)
    corte = lambda adm: per(adm, k)                                          # noqa: E731
    adm = e.set_index("episodio_id")["periodo_admision"]
    a2 = a.copy()
    tarde = a2["periodo"] > a2["episodio_id"].map(adm).map(corte)
    rng = np.random.default_rng(9)
    a2.loc[tarde, "nota_numerica"] = rng.uniform(1, 7, int(tarde.sum())).round(1)
    a2.loc[tarde, "aprobado_curricular"] = a2.loc[tarde, "nota_numerica"] >= 4.0
    s2 = s.copy()
    lim = s2["episodio_id"].astype(int).map(adm).map(corte)
    despues = s2["periodo"] > lim
    s2 = s2.loc[~despues | (rng.random(len(s2)) < 0.5)].copy()               # drop half of the later states
    extra = estados(*[(f"p{i}", i, per(adm[i], k + 1), "E") for i in adm.index[::3]])
    s2 = pd.concat([s2, extra], ignore_index=True)
    pert, _, _ = construir(e, s2, a2)
    _comparar(base, pert, k)
    assert (base["tiempo"].to_numpy() != pert.set_index(["episodio_id", "k"]).reindex(
        base.set_index(["episodio_id", "k"]).index)["tiempo"].to_numpy()).any()   # the perturbation did change labels


@pytest.mark.parametrize("k", [2, 4])
def test_deleting_all_later_periods_never_changes_the_features(k):
    e, s, a = _sintetico(seed=4)
    base, _, _ = construir(e, s, a)
    adm = e.set_index("episodio_id")["periodo_admision"]
    lim_e = s["episodio_id"].astype(int).map(adm).map(lambda p: per(p, k))
    corto_s = s.loc[s["periodo"] <= lim_e].reset_index(drop=True)
    lim_a = a["episodio_id"].map(adm).map(lambda p: per(p, k))
    corto_a = a.loc[a["periodo"] <= lim_a].reset_index(drop=True)
    corto, _, _ = construir(e, corto_s, corto_a)
    assert set(base.loc[base["k"] == k, "episodio_id"]) == set(corto.loc[corto["k"] == k, "episodio_id"])
    _comparar(base, corto, k)


def test_the_label_function_of_the_snapshot_would_fail_if_it_used_the_future_of_the_features():
    """Mutation check: the guard above must be able to fail, i.e. features do change when a PRE-cut fact changes."""
    e, s, a = _sintetico(seed=2)
    base, _, _ = construir(e, s, a)
    adm = e.set_index("episodio_id")["periodo_admision"]
    a2 = a.copy()
    pre = a2["periodo"] <= a2["episodio_id"].map(adm).map(lambda p: per(p, 2))
    a2.loc[pre, "nota_numerica"] = 7.0
    a2.loc[pre, "aprobado_curricular"] = True
    pert, _, _ = construir(e, s, a2)
    with pytest.raises(AssertionError):
        _comparar(base, pert, 2)


# ---------------------------------------------------------------------------------------------
# agreement between the egress states and the titulacion table
# ---------------------------------------------------------------------------------------------
def test_source_consistency_counts():
    e, s, eg = mundo()
    adm = "201610"
    s = pd.concat([s, estados(("p1", 1, per(adm, 7), "U"), ("p3", 3, per(adm, 9), "U"))], ignore_index=True)
    eg = pd.concat([eg, pd.DataFrame({"persona_key": ["p3", "x"], "episodio_id": [3, np.nan], "periodo": [per(adm, 8), "202010"]})],
                   ignore_index=True)
    pop, _ = F3.poblacion_t3(e)
    c = F3.consistencia_fuentes(pop, s, eg, LATEST)
    assert c["episodios"] == 10
    assert c["con_estado_egreso_titulacion"] == 5          # episodes 1, 3, 6, 8 and 12
    assert c["con_fila_titulacion"] == 2 and c["solo_fila"] == 1 and c["ambos"] == 1   # 7 only through the table, 3 with both
    assert c["solo_estado"] == 4
    assert c["con_estado_titulado"] == 2 and c["estado_titulado_sin_fila"] == 1        # episode 1 has U without a row
    assert c["fila_un_slot_antes_del_estado_titulado"] == 1                             # episode 3: row at slot 8, U at 9
    assert c["salida_definitiva_antes_del_egreso"] == 1 and c["egreso_posterior_al_cierre"] == 1
    assert c["filas_titulacion_sin_episodio"] == 1
