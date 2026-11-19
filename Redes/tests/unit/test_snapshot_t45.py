"""T4/T5 snapshot ("transicion real de programa" and "eliminacion", docs/11_benchmark_t4_t5.md): pure label rules,
mutually exclusive outcome at the horizon, censoring, Plan Comun handling (a specialty election is NOT a transition) and
the perturbation leakage guards. No database."""
import itertools

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.marts import rules_traslados as RT                  # noqa: E402
from pipelines.snapshots import features_t3 as F3                  # noqa: E402
from pipelines.snapshots import features_t45 as F45                # noqa: E402
from pipelines.snapshots import rules_t3 as R3                     # noqa: E402
from pipelines.snapshots import rules_t45 as R45                   # noqa: E402
from tests.unit import test_snapshot_t3_plan_comun as PCW          # noqa: E402
from tests.unit.test_snapshot_t3 import (                          # noqa: E402
    LATEST, MALLA, NO_EGRESO, NO_INTENTOS, NO_VIA, PROG_CAT, _sintetico, ep, episodios, estados, fila, intentos,
    matriculado, per)

ADM = "201610"          # cohort 2016 (train); 21 slots of follow-up with LATEST = 202620


def traslados(*rows):
    """(origen, destino, tipo, ambiguo, primer_periodo_destino[, ultimo_periodo_origen]); without the last origin period the
    transfer has gap 0 (it is the first destination period)."""
    return pd.DataFrame([dict(zip(F45.COLS_TRASLADOS, r if len(r) == len(F45.COLS_TRASLADOS) else (*r, r[4])))
                         for r in rows], columns=F45.COLS_TRASLADOS)


NO_TRASLADOS = traslados()


def construir45(e, s, a=NO_INTENTOS, tr=NO_TRASLADOS, egreso=NO_EGRESO, malla=MALLA, prog_cat=PROG_CAT, ks=(2, 4),
                latest=LATEST):
    return F45.construir_snapshot_t45(e, s, a, NO_VIA, egreso, malla, prog_cat, tr, latest, ks)


# ---------------------------------------------------------------------------------------------
# pure rules
# ---------------------------------------------------------------------------------------------
def test_split_follows_the_cohort_with_a_short_horizon_and_the_t1_boundaries():
    assert [R45.split_cohorte(a) for a in (2014, 2015, 2019, 2020, 2021, 2022, 2023, 2024)] == [
        "anterior", "train", "train", "valid", "valid", "test", "test", "posterior"]
    assert R45.KS == (2, 4) and R45.HORIZONTE_SEMESTRES == 2


def test_only_the_explicit_elimination_state_is_an_academic_elimination():
    """E (Eliminado) is the academic elimination; every other exit state is voluntary, administrative or disciplinary
    and stays out of T5 (ambiguous codes are kept out and recorded as a question, P70)."""
    assert R45.CODIGOS_ELIMINACION == frozenset({"E"})
    salidas = {c for c, clase in F45.CLASE_DE_ESTADO.items() if clase == "salida"}
    assert salidas == R45.CODIGOS_ELIMINACION | R45.CODIGOS_OTRA_SALIDA
    assert not R45.CODIGOS_ELIMINACION & R45.CODIGOS_OTRA_SALIDA
    assert {"B", "F", "O", "R", "3", "9", "X", "6", "H"} == R45.CODIGOS_OTRA_SALIDA


def test_only_changes_that_leave_the_origin_program_are_transitions():
    assert R45.TIPOS_TRANSICION == {"cambio_carrera", "traslado_sede", "traslado_otro"}
    assert R45.TIPOS_TRANSICION == {t for t, v in RT.CUENTA_ABANDONO.items() if v}
    for tipo in ("eleccion_especialidad", "continuacion_estudios", "cambio_ciclo"):
        assert R45.clase_traslado(tipo, False) is None
        assert R45.clase_traslado(tipo, True) is None
    assert R45.clase_traslado("cambio_carrera", False) == "transicion"
    assert R45.clase_traslado("traslado_otro", True) == "transicion_ambigua"


@pytest.mark.parametrize("args,esperado", [
    # k, t_egreso, t_eliminacion, t_transicion, t_ambigua, matriculado_h, t_max
    ((2, None, None, None, None, True, 10), "continua"),
    ((2, None, None, None, None, False, 10), "otra_salida"),
    ((2, 4, None, None, None, False, 10), "egreso"),
    ((2, None, 3, None, None, False, 10), "eliminacion"),
    ((2, None, None, 3, None, True, 10), "transicion"),
    ((2, None, None, None, 4, True, 10), "transicion_ambigua"),
    ((2, None, 5, None, None, True, 10), "continua"),                  # past the horizon: not an event
    ((2, None, 2, None, None, True, 10), "continua"),                  # at or before the cut: not in (k, k + 2]
    ((2, 5, None, 4, None, True, 10), "transicion"),                   # egress after the horizon does not count
    ((2, None, 4, 3, None, False, 10), "transicion"),                  # the earliest event wins
    ((2, None, 3, 4, None, False, 10), "eliminacion"),
    ((2, 3, 3, 3, 3, False, 10), "egreso"),                            # ties: egreso > eliminacion > transicion > ambigua
    ((2, None, 3, 3, 3, False, 10), "eliminacion"),
    ((2, None, None, 3, 3, False, 10), "transicion"),
    ((2, None, None, None, None, True, 3), "censurado"),               # the horizon (slot 4) is not closed
    ((2, 3, None, None, None, False, 3), "censurado"),                 # no label without the closed horizon
    ((2, None, None, None, None, True, 4), "continua"),                # exactly closed
    ((4, None, 6, None, None, False, 6), "eliminacion"),
])
def test_resolution_of_the_outcome(args, esperado):
    assert R45.resolver_resultado(*args) == esperado


def test_vectorized_resolution_equals_the_scalar_rule_on_a_grid():
    nan = float("nan")
    filas = [dict(k=k, t_egreso=a, t_eliminacion=b, t_transicion=c, t_ambigua=d, matriculado_h=m, t_max=t)
             for k, a, b, c, d, m, t in itertools.product(
                 [2, 4], [nan, 3, 5], [nan, 3, 4, 7], [nan, 3, 4, 6], [nan, 3, 6], [False, True], [4, 5, 6, 9])]
    out = F45.resolver_resultados(pd.DataFrame(filas))
    for i, f in enumerate(filas):
        esperado = R45.resolver_resultado(f["k"], f["t_egreso"], f["t_eliminacion"], f["t_transicion"], f["t_ambigua"],
                                          f["matriculado_h"], f["t_max"])
        assert out.iloc[i] == esperado, f


# ---------------------------------------------------------------------------------------------
# a small world: one episode per situation (admission 201610, cut k = 2 -> horizon slot 4)
# ---------------------------------------------------------------------------------------------
def mundo():
    adm = ADM
    eps, est, tr = [], [], []

    def dest(eid, persona, desde, hasta, prog="C2"):
        eps.append(ep(eid, persona=persona, prog=prog))
        est.extend((persona, eid, per(adm, j), "M") for j in range(desde, hasta + 1))

    def uno(eid, hasta=2, extra=()):
        eps.append(ep(eid))
        est.extend(matriculado(eid, adm, 1, hasta))
        est.extend((f"p{eid}", eid, per(adm, j), c) for j, c in extra)

    uno(1, 6)                                                           # continua
    uno(2)                                                              # otra_salida (ausencia)
    uno(3, extra=[(3, "B")])                                            # otra_salida (renuncia)
    uno(4, extra=[(3, "E")])                                            # eliminacion
    uno(5, 4, extra=[(5, "E")])                                         # E after the horizon, enrolled at the horizon: continua
    uno(6, 3, extra=[(4, "Z")])                                         # egreso
    uno(7); dest(207, "p7", 3, 6); tr.append((7, 207, "cambio_carrera", False, per(adm, 3)))
    uno(8); dest(208, "p8", 3, 6); tr.append((8, 208, "eleccion_especialidad", False, per(adm, 3)))
    uno(9); dest(209, "p9", 3, 6); tr.append((9, 209, "cambio_ciclo", False, per(adm, 3)))
    uno(10); dest(210, "p10", 3, 6); tr.append((10, 210, "cambio_carrera", True, per(adm, 3)))
    uno(11, 4); dest(211, "p11", 5, 8); tr.append((11, 211, "traslado_sede", False, per(adm, 5)))
    uno(12); dest(212, "p12", 2, 5); tr.append((12, 212, "cambio_carrera", False, per(adm, 2)))   # already started at the cut
    uno(13, extra=[(3, "E")]); dest(213, "p13", 3, 6); tr.append((13, 213, "traslado_otro", False, per(adm, 3)))
    uno(14, extra=[(4, "E")]); dest(214, "p14", 3, 6); tr.append((14, 214, "traslado_otro", False, per(adm, 3)))
    eps.append(ep(15, adm="202510")); est.extend(matriculado(15, "202510", 1, 2))                # horizon not closed
    uno(16, extra=[(3, "P"), (4, "P")])                                 # interruption through the horizon: otra_salida
    uno(17, 4)                                                          # egress through the titulacion table
    uno(18, extra=[(3, "X")])                                           # expelled: not an academic elimination
    uno(19, extra=[(3, "6")])
    uno(20, 4, extra=[(6, "E")])                                        # k = 4: E at slot 6 -> eliminacion
    uno(21, 4, extra=[(7, "E")])                                        # k = 4: E at slot 7 (after) and not enrolled: otra_salida
    egreso = pd.DataFrame({"persona_key": ["p17"], "episodio_id": [17], "periodo": [per(adm, 3)]})
    return episodios(*eps), estados(*est), traslados(*tr), egreso


def _resultados(snap, k):
    return snap[snap["k"] == k].set_index("episodio_id")["resultado"].to_dict()


def test_outcome_of_each_situation_at_k2():
    e, s, tr, eg = mundo()
    snap, _, _ = construir45(e, s, tr=tr, egreso=eg)
    r = _resultados(snap, 2)
    esperado = {1: "continua", 2: "otra_salida", 3: "otra_salida", 4: "eliminacion", 5: "continua", 6: "egreso",
                7: "transicion", 8: "continua", 9: "continua", 10: "transicion_ambigua", 11: "continua",
                13: "eliminacion", 14: "transicion", 15: "censurado", 16: "otra_salida", 17: "egreso",
                18: "otra_salida", 19: "otra_salida", 20: "continua", 21: "continua", 212: "continua"}
    assert r == esperado
    assert 12 not in r                                                  # destination already started at the cut: not a prediction target


def test_outcome_of_each_situation_at_k4():
    """Horizon = slots 5-6; only the episodes enrolled at slot 4 and not graduated are at risk."""
    e, s, tr, eg = mundo()
    snap, _, _ = construir45(e, s, tr=tr, egreso=eg)
    r = {e_: v for e_, v in _resultados(snap, 4).items() if e_ < 100}          # the destination episodes are units too
    assert r == {1: "continua", 5: "eliminacion", 11: "transicion", 20: "eliminacion", 21: "otra_salida"}


def test_outcomes_are_mutually_exclusive_and_exhaustive_and_binary_targets_never_overlap():
    e, s, tr, eg = mundo()
    snap, _, _ = construir45(e, s, tr=tr, egreso=eg)
    assert snap["resultado"].isin(R45.RESULTADOS).all()
    y4, y5 = (snap["resultado"] == "transicion"), (snap["resultado"] == "eliminacion")
    assert not (y4 & y5).any()
    assert set(snap["resultado"]) <= set(R45.RESULTADOS)
    assert snap["resultado"].notna().all()


def test_the_overlap_flags_keep_what_the_exclusive_outcome_hides():
    e, s, tr, eg = mundo()
    snap, _, _ = construir45(e, s, tr=tr, egreso=eg)
    r13, r14 = fila(snap, 13, 2), fila(snap, 14, 2)
    assert r13["resultado"] == "eliminacion" and r13["hubo_transicion_en_horizonte"] and r13["hubo_eliminacion_en_horizonte"]
    assert r14["resultado"] == "transicion" and r14["hubo_transicion_en_horizonte"] and r14["hubo_eliminacion_en_horizonte"]
    assert not fila(snap, 8, 2)["hubo_transicion_en_horizonte"]         # a specialty election is not a transition


def test_other_exit_types_and_the_funnel():
    e, s, tr, eg = mundo()
    snap, _, emb = construir45(e, s, tr=tr, egreso=eg)
    t = snap.set_index(["episodio_id", "k"])["otra_salida_tipo"]
    assert t[(2, 2)] == "ausencia" and t[(3, 2)] == "salida_explicita" and t[(16, 2)] == "interrupcion"
    assert t[(18, 2)] == "salida_explicita"
    assert pd.isna(t[(1, 2)])                                           # only for the outcome 'otra_salida'
    f2 = [x for x in emb if x["k"] == 2][0]
    assert f2["transicion_iniciada_en_corte"] == 1
    assert f2["censurados"] == 1
    assert f2["elegibles"] == f2["elegibles_t3"] - f2["transicion_iniciada_en_corte"]


def test_follow_up_is_counted_from_the_admission_semester_and_censoring_needs_the_closed_horizon():
    e, s, tr, eg = mundo()
    snap, _, _ = construir45(e, s, tr=tr, egreso=eg)
    r = fila(snap, 15, 2)
    assert r["seguimiento_max"] == 3 and r["resultado"] == "censurado"
    assert fila(snap, 1, 2)["seguimiento_max"] == 21


# ---------------------------------------------------------------------------------------------
# Plan Comun (D47): the election of the specialty is expected progression, not a transition
# ---------------------------------------------------------------------------------------------
def mundo_pc():
    eps, est, tr = [], [], []
    adm = PCW.ADM
    # A: PC (slots 1-2) -> specialty from slot 3: the election falls in the k = 2 horizon and is NOT a transition
    e_, s_ = PCW.unidad(101, 201, "pA", esp_desde=3, esp_hasta=9, final=("Z", 10))
    eps += e_; est += s_; tr.append((101, 201, "eleccion_especialidad", False, per(adm, 3)))
    # B: same, and the specialty episode later leaves through a change of degree at slot 6 (inside the k = 4 horizon)
    e_, s_ = PCW.unidad(102, 202, "pB", esp_desde=3, esp_hasta=5, final=None)
    eps += e_; est += s_
    eps.append(ep(302, persona="pB", prog="C2")); est += PCW.mat(302, "pB", adm, 6, 9, "C2")
    tr += [(102, 202, "eleccion_especialidad", False, per(adm, 3)), (202, 302, "cambio_carrera", False, per(adm, 6))]
    # C: PC without continuation that leaves through a change of degree at slot 3
    eps.append(PCW.ep(103, persona="pC", prog=PCW.PC)); est += PCW.mat(103, "pC", adm, 1, 2, PCW.PC)
    eps.append(ep(303, persona="pC", prog="C2")); est += PCW.mat(303, "pC", adm, 3, 8, "C2")
    tr.append((103, 303, "cambio_carrera", False, per(adm, 3)))
    # D: PC without continuation and without any later program: not enrolled at the horizon
    eps.append(PCW.ep(104, persona="pD", prog=PCW.PC)); est += PCW.mat(104, "pD", adm, 1, 2, PCW.PC)
    return episodios(*eps), PCW.estados_x(*est), traslados(*tr)


def test_specialty_election_is_not_a_transition_but_a_later_change_of_degree_is():
    e, s, tr = mundo_pc()
    snap, _, _ = construir45(e, s, tr=tr, malla=PCW.MALLA, prog_cat=PCW.PROG_CAT)
    assert _resultados(snap, 2) == {101: "continua", 102: "continua", 103: "transicion", 104: "otra_salida"}
    r4 = _resultados(snap, 4)
    assert r4[102] == "transicion"                                      # the origin episode is the absorbed specialty
    assert r4[101] == "continua"
    assert 201 not in snap["episodio_id"].to_numpy() and 202 not in snap["episodio_id"].to_numpy()   # never a unit of its own
    assert not fila(snap, 101, 2)["hubo_transicion_en_horizonte"]


def test_the_plan_comun_unit_keeps_its_admission_cohort_and_audit_link():
    e, s, tr = mundo_pc()
    snap, _, _ = construir45(e, s, tr=tr, malla=PCW.MALLA, prog_cat=PCW.PROG_CAT)
    r = fila(snap, 101, 2)
    assert r["cohorte_anio"] == 2016 and r["split"] == "train" and r["episodio_especialidad_id"] == 201
    assert not r["especialidad_conocida_al_corte"]                      # the specialty starts after the cut
    assert fila(snap, 101, 4)["especialidad_conocida_al_corte"]


# ---------------------------------------------------------------------------------------------
# leakage guards: facts after the cut never change the features
# ---------------------------------------------------------------------------------------------
FEATURES = list(F45.FEATURE_COLS_T45)


def _traslados_sinteticos(e, seed=1):
    rng = np.random.default_rng(seed)
    adm = e.set_index("episodio_id")["periodo_admision"]
    filas = []
    for eid in adm.index[::2]:
        j = int(rng.integers(3, 8))
        filas.append((int(eid), 9000 + int(eid), str(rng.choice(["cambio_carrera", "traslado_otro", "traslado_sede",
                                                                   "eleccion_especialidad", "cambio_ciclo"])),
                      bool(rng.random() < 0.1), per(adm[eid], j)))
    return traslados(*filas)


def _comparar(a, b, k):
    a, b = a[a["k"] == k].set_index("episodio_id"), b[b["k"] == k].set_index("episodio_id")
    assert list(a.index) == list(b.index) and len(a) > 15
    for c in FEATURES:
        x, y = a[c], b[c]
        assert ((x == y) | (x.isna() & y.isna())).all(), c


@pytest.mark.parametrize("k", [2, 4])
def test_changing_facts_after_the_cut_never_changes_the_features(k):
    e, s, a = _sintetico()
    tr = _traslados_sinteticos(e)
    base, _, _ = construir45(e, s, a, tr)
    adm = e.set_index("episodio_id")["periodo_admision"]
    corte = lambda p: per(p, k)                                                      # noqa: E731
    a2 = a.copy()
    tarde = a2["periodo"] > a2["episodio_id"].map(adm).map(corte)
    rng = np.random.default_rng(9)
    a2.loc[tarde, "nota_numerica"] = rng.uniform(1, 7, int(tarde.sum())).round(1)
    a2.loc[tarde, "aprobado_curricular"] = a2.loc[tarde, "nota_numerica"] >= 4.0
    s2 = s.copy()
    lim = s2["episodio_id"].astype(int).map(adm).map(corte)
    s2 = s2.loc[~(s2["periodo"] > lim) | (rng.random(len(s2)) < 0.5)].copy()           # drop half of the later states
    extra = estados(*[(f"p{i}", i, per(adm[i], k + 1), "E") for i in adm.index[::3]])
    s2 = pd.concat([s2, extra], ignore_index=True)
    # transfers: the whole table is label-side information, but only those AFTER the cut may change (an earlier one is
    # known at the cut and decides eligibility, like D24)
    tr2 = tr.copy()
    despues = tr2["primer_periodo_destino"] > tr2["origen_episodio_id"].map(adm).map(corte)
    tr2.loc[despues, "tipo"] = "cambio_carrera"
    tr2 = pd.concat([tr2, traslados(*[(int(i), 7000 + int(i), "traslado_otro", False, per(adm[i], k + 1))
                                      for i in adm.index[1::4]])], ignore_index=True)
    pert, _, _ = construir45(e, s2, a2, tr2)
    _comparar(base, pert, k)
    comparados = base.set_index(["episodio_id", "k"]).join(pert.set_index(["episodio_id", "k"]), rsuffix="_p", how="inner")
    assert (comparados["resultado"] != comparados["resultado_p"]).any()                # the perturbation did change the labels


@pytest.mark.parametrize("k", [2, 4])
def test_deleting_all_later_periods_never_changes_the_features(k):
    e, s, a = _sintetico(seed=4)
    tr = _traslados_sinteticos(e, 5)
    adm = e.set_index("episodio_id")["periodo_admision"]
    tr = tr.loc[tr["primer_periodo_destino"] > tr["origen_episodio_id"].map(adm).map(lambda p: per(p, k))]
    base, _, _ = construir45(e, s, a, tr)
    lim_e = s["episodio_id"].astype(int).map(adm).map(lambda p: per(p, k))
    corto_s = s.loc[s["periodo"] <= lim_e].reset_index(drop=True)
    lim_a = a["episodio_id"].map(adm).map(lambda p: per(p, k))
    corto_a = a.loc[a["periodo"] <= lim_a].reset_index(drop=True)
    corto, _, _ = construir45(e, corto_s, corto_a, NO_TRASLADOS)
    assert set(base.loc[base["k"] == k, "episodio_id"]) == set(corto.loc[corto["k"] == k, "episodio_id"])
    _comparar(base, corto, k)


def test_the_guard_can_fail_features_do_change_when_a_pre_cut_fact_changes():
    e, s, a = _sintetico(seed=2)
    base, _, _ = construir45(e, s, a)
    adm = e.set_index("episodio_id")["periodo_admision"]
    a2 = a.copy()
    pre = a2["periodo"] <= a2["episodio_id"].map(adm).map(lambda p: per(p, 2))
    a2.loc[pre, "nota_numerica"] = 7.0
    a2.loc[pre, "aprobado_curricular"] = True
    pert, _, _ = construir45(e, s, a2)
    with pytest.raises(AssertionError):
        _comparar(base, pert, 2)


def test_features_equal_the_t3_features_of_the_same_rows_and_no_label_or_sex_is_a_feature():
    e, s, a = _sintetico(seed=3)
    snap45, _, _ = construir45(e, s, a)
    snap3, _, _ = F3.construir_snapshot_t3(e, s, a, NO_VIA, NO_EGRESO, MALLA, PROG_CAT, LATEST, (2, 4))
    m = snap45.merge(snap3, on=["episodio_id", "k"], suffixes=("", "_t3"))
    assert len(m) == len(snap45) > 15
    for c in FEATURES:
        assert ((m[c] == m[c + "_t3"]) | (m[c].isna() & m[c + "_t3"].isna())).all(), c
    assert not {"persona_key", "split", "k", "periodo_admision", "cohorte_anio", "episodio_id"} & set(F45.FEATURE_COLS_T45)
    assert "sexo_equidad" in F45.SNAPSHOT_COLS_T45 and "sexo" not in F45.SNAPSHOT_COLS_T45
    assert not set(F45.LABEL_COLS_T45) & set(F45.FEATURE_COLS_T45)


def test_semester_table_covers_every_row_and_only_slots_up_to_k():
    e, s, a = _sintetico(seed=5)
    snap, sem, _ = construir45(e, s, a)
    assert set(snap["episodio_id"]) <= set(sem["episodio_id"])
    assert sem["j"].max() <= 4 and sem["j"].min() == 1


# ---------------------------------------------------------------------------------------------
# P72 / P75 (DAI, 13-11-2026): elimination with / without reintegro and the doubtful-recording horizon (snapshot only)
# ---------------------------------------------------------------------------------------------
def test_p72_a_reintegro_must_follow_the_elimination_in_slot_then_in_canonical_order():
    assert R45.eliminacion_con_reintegro((3, 5), (4, 6)) is True
    assert R45.eliminacion_con_reintegro((3, 5), (3, 6)) is True            # same period, recorded after the E
    assert R45.eliminacion_con_reintegro((3, 5), (3, 4)) is False           # recorded before the E: not a follow-up
    assert R45.eliminacion_con_reintegro((3, 5), (2, 9)) is False
    assert R45.eliminacion_con_reintegro((3, 5), None) is False


def test_p88_the_only_reintegro_state_is_i_and_y_is_a_rectification():
    assert R45.CODIGOS_REINTEGRO == frozenset({"I"})
    assert "Y" in {c for c, clase in F45.CLASE_DE_ESTADO.items() if clase == "reingreso"}      # still a reingreso state
    assert "Y" not in R45.CODIGOS_REINTEGRO


@pytest.mark.parametrize("periodo,dudoso", [("202410", False), ("202420", True), ("202510", True), ("201720", False),
                                            (None, False)])
def test_p75_horizons_ending_in_202420_or_later_touch_the_doubtful_recording_of_e(periodo, dudoso):
    assert R45.horizonte_e_dudoso(periodo) is dudoso
    assert R45.E_COMPLETO_HASTA == "202410"


def mundo_p72():
    eps, est = [], []

    def uno(eid, adm=ADM, hasta=2, extra=()):
        eps.append(ep(eid, adm=adm))
        est.extend(matriculado(eid, adm, 1, hasta))
        est.extend((f"p{eid}", eid, per(adm, j), c) for j, c in extra)

    uno(31, extra=[(3, "E"), (4, "I")])                    # E then reintegro inside the horizon
    uno(32, extra=[(3, "E")])                              # E without reintegro
    uno(33, extra=[(4, "E"), (5, "I")])                    # the reintegro falls after the horizon: not seen at the cut
    uno(34, extra=[(3, "E"), (3, "Y")])                    # Y (Reintegro por Rectificacion) is NOT a reintegro (P88)
    uno(35, extra=[(3, "I"), (3, "E")])                    # recorded before the E: not a follow-up
    uno(36)                                                # no elimination
    uno(37, extra=[(3, "B")])                              # another exit: no elimination
    uno(38, extra=[(3, "E"), (4, "I"), (4, "E")])          # a second E after the reintegro: the FIRST E decides
    eps.append(ep(39, adm="202510")); est.extend(matriculado(39, "202510", 1, 2))        # horizon not closed
    uno(41, adm="202310")                                  # horizon 202410-202420: touches the doubtful recording
    uno(42, adm="202220")                                  # horizon 202320-202410: complete
    uno(43, adm="202310", extra=[(3, "E")])                # E in a doubtful horizon
    return episodios(*eps), estados(*est)


def test_p72_elimination_with_reintegro_versus_effective_elimination_inside_the_horizon():
    e, s = mundo_p72()
    snap, _, _ = construir45(e, s)
    r = snap[snap["k"] == 2].set_index("episodio_id")
    con = {i for i in r.index if r.loc[i, "eliminacion_con_reintegro"]}
    efectiva = {i for i in r.index if r.loc[i, "eliminacion_efectiva"]}
    assert con == {31, 38} and efectiva == {32, 33, 34, 35, 43}
    assert not (con & efectiva)
    assert (con | efectiva) == {i for i in r.index if r.loc[i, "hubo_eliminacion_en_horizonte"]}
    assert not r.loc[[36, 37, 41, 42], ["eliminacion_con_reintegro", "eliminacion_efectiva"]].any().any()


def test_p72_the_exclusive_outcome_is_unchanged_and_a_censored_row_has_no_elimination_label():
    e, s = mundo_p72()
    snap, _, _ = construir45(e, s)
    r = snap[snap["k"] == 2].set_index("episodio_id")
    assert {31: "eliminacion", 32: "eliminacion", 33: "eliminacion", 36: "otra_salida"}.items() <= r["resultado"].to_dict().items()
    assert r.loc[39, "resultado"] == "censurado"
    assert not r.loc[39, ["eliminacion_con_reintegro", "eliminacion_efectiva", "horizonte_e_dudoso"]].any()


def test_p75_the_doubtful_horizon_flag_marks_rows_whose_horizon_reaches_202420():
    e, s = mundo_p72()
    snap, _, _ = construir45(e, s)
    r = snap[snap["k"] == 2].set_index("episodio_id")["horizonte_e_dudoso"]
    assert bool(r[41]) and bool(r[43])
    assert not r[42] and not r[31] and not r[36]


def test_p72_labels_are_label_side_never_features_and_the_snapshot_columns_include_them():
    for c in ("eliminacion_con_reintegro", "eliminacion_efectiva", "horizonte_e_dudoso"):
        assert c in F45.SNAPSHOT_COLS_T45 and c in F45.LABEL_COLS_T45
        assert c not in F45.FEATURE_COLS_T45


def test_p72_a_reintegro_after_the_cut_never_changes_the_features():
    """Deleting every state after the horizon leaves the features and the labels of the horizon unchanged."""
    e, s = mundo_p72()
    base, _, _ = construir45(e, s)
    corto = s[~((s["episodio_id"] == 33) & (s["cod_estado"] == "I"))]          # the reintegro at slot 5 is beyond the horizon
    cambiado, _, _ = construir45(e, corto)
    cols = [c for c in base.columns if c not in ("seguimiento_max", "k")]
    a = base[base["episodio_id"] == 33].set_index("k")[cols]
    b = cambiado[cambiado["episodio_id"] == 33].set_index("k")[cols]
    assert bool(a.loc[2, "eliminacion_efectiva"])
    assert (a.loc[2].astype(str) == b.loc[2].astype(str)).all()          # NaN-safe


# ---------------------------------------------------------------------------------------------
# P71 (stage B): the moment of a transfer is the exit from the origin program (its last period), not the first period of the
# destination; the transfers with gap 0 (80 %) are dated as before
# ---------------------------------------------------------------------------------------------
def mundo_p71():
    adm = ADM
    eps, est, tr = [], [], []

    def origen(eid, hasta):
        eps.append(ep(eid))
        est.extend(matriculado(eid, adm, 1, hasta))

    def destino(eid, persona, desde, hasta):
        eps.append(ep(eid, persona=persona, prog="C2"))
        est.extend((persona, eid, per(adm, j), "M") for j in range(desde, hasta + 1))

    origen(31, 4); destino(231, "p31", 6, 8)       # exit at slot 4 (inside the horizon of k = 2), destination at slot 6
    tr.append((31, 231, "cambio_carrera", False, per(adm, 6), per(adm, 4)))
    origen(32, 2); destino(232, "p32", 4, 7)       # exit at the cut (slot 2), destination at slot 4 (inside the horizon)
    tr.append((32, 232, "cambio_carrera", False, per(adm, 4), per(adm, 2)))
    origen(33, 4); destino(233, "p33", 4, 7)       # gap 0: last origin period = first destination period = slot 4
    tr.append((33, 233, "traslado_otro", False, per(adm, 4), per(adm, 4)))
    origen(34, 4); destino(234, "p34", 2, 6)       # double enrollment: the destination started at the cut (slot 2)
    tr.append((34, 234, "cambio_carrera", False, per(adm, 2), per(adm, 4)))
    origen(35, 6); destino(235, "p35", 8, 9)       # exit at slot 6: outside the horizon of k = 2, inside the one of k = 4
    tr.append((35, 235, "traslado_sede", False, per(adm, 8), per(adm, 6)))
    return episodios(*eps), estados(*est), traslados(*tr)


def test_the_moment_of_a_transfer_is_the_exit_from_the_origin_program():
    e, s, tr = mundo_p71()
    snap, _, _ = construir45(e, s, tr=tr)
    r2, r4 = _resultados(snap, 2), _resultados(snap, 4)
    assert r2[31] == "transicion"             # the exit (slot 4) is in (2, 4] although the destination starts at slot 6
    assert r2[33] == "transicion"             # gap 0: the same date as before
    assert r2[35] == "continua"               # the exit (slot 6) is after the horizon
    assert r4[35] == "transicion"             # ... and inside the horizon (5, 6] of k = 4
    assert fila(snap, 31, 2)["hubo_transicion_en_horizonte"]


def test_a_transfer_dated_at_the_cut_is_not_an_event_of_that_row_and_is_counted():
    """The exit at the cut is not inside (k, k + 2]: the row stays 'continua' (enrolled at the horizon in the destination),
    and the audit count keeps the number of rows where the old dating would have said transicion."""
    e, s, tr = mundo_p71()
    snap, _, emb = construir45(e, s, tr=tr)
    assert _resultados(snap, 2)[32] == "continua"
    f2 = [x for x in emb if x["k"] == 2][0]
    assert f2["traslado_fechado_en_el_corte"] == 1


def test_the_exclusion_of_a_transition_started_at_the_cut_still_uses_the_destination_start():
    e, s, tr = mundo_p71()
    snap, _, _ = construir45(e, s, tr=tr)
    assert 34 not in _resultados(snap, 2)      # destination at slot 2 = the cut: known at the cut (D53), as before


def test_without_the_last_origin_period_the_destination_period_is_used():
    e, s, tr = mundo_p71()
    sin = tr.assign(ultimo_periodo_origen=None)
    snap, _, _ = construir45(e, s, tr=sin)
    r2 = _resultados(snap, 2)
    assert r2[31] == "continua" and r2[32] == "transicion"        # the old dating (first period of the destination)


def test_the_transitions_after_the_horizon_use_the_exit_date_too():
    e, s, tr = mundo_p71()
    assert F45.traslados_por_unidad(tr, pd.DataFrame({"episodio_esp": [], "episodio_id": []}), e.assign(episodio_id=e["episodio_id"]))[
        "ultimo_periodo_origen"].notna().all()
