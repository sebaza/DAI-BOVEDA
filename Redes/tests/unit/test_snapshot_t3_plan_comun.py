"""T3 population change (D47, P62): exclusion of the exchange programs and merge of Ingenieria Civil Plan Comun with its
specialty into ONE trajectory. Pure rules, linking, no double counting, event/time of merged trajectories and the
point-in-time guards (the future specialty never reaches an earlier cut). No database."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features_t3 as F3                  # noqa: E402
from pipelines.snapshots import rules_t3 as R3                     # noqa: E402
from tests.unit.test_snapshot_t3 import (                          # noqa: E402
    LATEST, NO_EGRESO, NO_VIA, ep, episodios, fila, intentos, per)

ADM = "201610"                       # cohort 2016 (train)
PC, ESP, ESP2, ESP_LARGA = "8643", "8613", "8616", "8553"
MALLA = pd.DataFrame(
    [(PC, "2019", "A", 1, 6.0), (PC, "2019", "B", 1, 6.0), (PC, "2019", "C", 2, 6.0)]
    + [(p, "2019", c, s, 6.0) for p in (ESP, ESP2, ESP_LARGA)
       for c, s in (("P", 1), ("Q", 1), ("R", 2), ("S", 3), ("T", 4), ("U", 5))],
    columns=["cod_programa", "catalogo", "codigo_asignatura", "semestre", "creditos"])
PROG_CAT = pd.DataFrame([(PC, "2019", 2), (ESP, "2019", 10), (ESP2, "2019", 10), (ESP_LARGA, "2019", 14)],
                        columns=["cod_programa", "catalogo", "duracion"])


def estados_x(*rows):
    """(persona, episodio_id, periodo, cod_estado[, cod_programa[, catalogo]])."""
    out = [{"persona_key": r[0], "episodio_id": r[1], "periodo": r[2], "cod_estado": r[3],
            "cod_programa": r[4] if len(r) > 4 else "C1", "catalogo": r[5] if len(r) > 5 else "2019",
            "es_correccion_sistema": False, "orden_canonico": i + 1} for i, r in enumerate(rows)]
    df = pd.DataFrame(out, columns=["persona_key", "episodio_id", "periodo", "cod_estado", "cod_programa", "catalogo",
                                    "es_correccion_sistema", "orden_canonico"])
    df["episodio_id"] = df["episodio_id"].astype("Int64")
    return df


def mat(eid, persona, adm, desde, hasta, prog="C1", cat="2019"):
    return [(persona, eid, per(adm, j), "M", prog, cat) for j in range(desde, hasta + 1)]


def unidad(eid_pc, eid_esp, persona, *, esp_desde=2, esp_hasta=9, final=("Z", 10), pc_salida=None, adm=ADM, adm_esp=None,
           prog_esp=ESP, cod_esp="ES", cat_esp="2019"):
    """Plan Comun episode (slots 1-2) and its specialty. ``final`` = (state, slot) closing the specialty (or None)."""
    adm_esp = adm_esp or adm
    eps = [ep(eid_pc, persona=persona, adm=adm, prog=PC), ep(eid_esp, persona=persona, adm=adm_esp, prog=prog_esp,
                                                                cod=cod_esp, cat=cat_esp)]
    est = mat(eid_pc, persona, adm, 1, 2, PC) + mat(eid_esp, persona, adm, esp_desde, esp_hasta, prog_esp, cat_esp)
    if pc_salida:
        est.append((persona, eid_pc, per(adm, pc_salida[1]), pc_salida[0], PC, "2019"))
    if final:
        est.append((persona, eid_esp, per(adm, final[1]), final[0], prog_esp, cat_esp))
    return eps, est


def mundo_pc():
    """Merged trajectories and controls. Specialty episode ids are 2xx; Plan Comun ids 1xx."""
    eps, est, att = [], [], []
    # 101: specialty starts at slot 2 (known at k = 2), the Plan Comun episode records an exit at slot 2; egress at slot 10
    e_, s_ = unidad(101, 201, "pA", esp_desde=2, final=("Z", 10), pc_salida=("E", 2))
    eps += e_; est += s_
    att += [(101, per(ADM, 1), 5.0, "A"), (101, per(ADM, 1), 5.0, "B"), (201, per(ADM, 3), 5.0, "S"),
            (201, per(ADM, 5), 5.0, "T")]
    # 102: specialty starts at slot 3 (gap 1); explicit exit of the specialty at slot 9
    e_, s_ = unidad(102, 202, "pB", esp_desde=3, esp_hasta=8, final=("E", 9))
    eps += e_; est += s_
    att += [(102, per(ADM, 1), 5.0, "A"), (102, per(ADM, 1), 5.0, "B"), (202, per(ADM, 3), 5.0, "P"),
            (202, per(ADM, 4), 5.0, "Q"), (202, per(ADM, 6), 5.0, "R")]
    # 103: specialty admitted two semesters later (LS, gap 2), then silence: absence one slot after the last activity (9)
    e_, s_ = unidad(103, 203, "pC", esp_desde=4, esp_hasta=9, final=None, adm_esp=per(ADM, 3), cod_esp="LS")
    eps += e_; est += s_
    att += [(103, per(ADM, 1), 5.0, "A"), (203, per(ADM, 4), 5.0, "P"), (203, per(ADM, 5), 5.0, "Q")]
    # 104: Plan Comun with an exit and no continuation (today's handling)
    eps.append(ep(104, persona="pD", prog=PC)); est += mat(104, "pD", ADM, 1, 2, PC) + [("pD", 104, per(ADM, 3), "E", PC, "2019")]
    att += [(104, per(ADM, 1), 5.0, "A")]
    # 105..108: more linked trajectories of the same shape as 101 (they keep the learned constant stable)
    for i, eid in enumerate((105, 106, 107, 108)):
        e_, s_ = unidad(eid, eid + 100, f"pE{i}", esp_desde=2, final=("Z", 10))
        eps += e_; est += s_
        att += [(eid, per(ADM, 1), 5.0, "A")]
    # 301: ordinary student of a specialty; 401: exchange student
    eps.append(ep(301, persona="pF", prog=ESP)); est += mat(301, "pF", ADM, 1, 6, ESP) + [("pF", 301, per(ADM, 7), "Z", ESP, "2019")]
    eps.append(ep(401, persona="pG", prog="0003")); est += mat(401, "pG", ADM, 1, 4, "0003")
    return episodios(*eps), estados_x(*est), intentos(*att)


def construir(e, s, a, ks=(0, 2, 4)):
    return F3.construir_snapshot_t3(e, s, a, NO_VIA, NO_EGRESO, MALLA, PROG_CAT, LATEST, ks)


ESPECIALIDADES = {201, 202, 203, 205, 206, 207, 208}
UNIDADES_PC = {101, 102, 103, 105, 106, 107, 108}


# ---------------------------------------------------------------------------------------------
# pinned program identities
# ---------------------------------------------------------------------------------------------
def test_program_constants_are_pinned_by_code():
    assert R3.PROGRAMAS_INTERCAMBIO == frozenset({"0003", "0006"})
    assert R3.PLAN_COMUN_ING_CIVIL == frozenset({"8633", "8643"})
    assert R3.PLAN_COMUN_CODIGOS == frozenset({"8113", "8413", "8433", "8493", "8633", "8643"})
    assert R3.PLAN_COMUN_ING_CIVIL < R3.PLAN_COMUN_CODIGOS
    assert not R3.ESPECIALIDADES_ING_CIVIL & R3.PLAN_COMUN_CODIGOS
    assert {"8613", "8616", "8603", "8553", "8693"} <= R3.ESPECIALIDADES_ING_CIVIL
    assert not R3.ESPECIALIDADES_ING_CIVIL & R3.PROGRAMAS_INTERCAMBIO


def test_period_ordinals_and_the_link_window():
    assert R3.ordinal_periodo("201610") + 1 == R3.ordinal_periodo("201620")
    assert R3.ordinal_periodo("201615") == R3.ordinal_periodo("201620")           # summer maps to the next regular slot rule
    assert R3.ordinal_periodo("201625") == R3.ordinal_periodo("201710")
    assert R3.ordinal_periodo("2016") is None and R3.ordinal_periodo(None) is None
    assert R3.dentro_de_ventana_vinculo("201620", "201710") is True                # one regular period after
    assert R3.dentro_de_ventana_vinculo("201620", "201720") is True                # two periods after
    assert R3.dentro_de_ventana_vinculo("201620", "201810") is False               # three periods after
    assert R3.dentro_de_ventana_vinculo("201620", "201620") is True                # same period as the last one


# ---------------------------------------------------------------------------------------------
# exclusion of the exchange programs
# ---------------------------------------------------------------------------------------------
def test_exchange_programs_are_excluded_by_program_identity_not_by_duration():
    e = episodios(ep(1, prog="0003"), ep(2, prog="0006"), ep(3, prog="8613"), ep(4, prog="X1"))
    pop, previas = F3.poblacion_t3(e)
    assert set(pop["episodio_id"]) == {3, 4}              # the exchange programs go even with a regular admission code
    assert previas == 0


def test_exchange_rows_leave_the_snapshot_and_the_funnel_counts_them():
    e, s, a = mundo_pc()
    snap, _, embudo = construir(e, s, a)
    assert 401 not in set(snap["episodio_id"])
    por_k = {r["k"]: r for r in embudo}
    assert por_k[2]["intercambio_excluidos"] == 1
    assert por_k[2]["intercambio_elegibles_excluidos"] == 1                        # eligible at k = 2 had it stayed
    assert por_k[4]["intercambio_elegibles_excluidos"] == 1
    assert por_k[0]["intercambio_elegibles_excluidos"] == 1


# ---------------------------------------------------------------------------------------------
# linking rule
# ---------------------------------------------------------------------------------------------
def _vinculos(eps, est):
    e = episodios(*eps)
    return F3.vincular_plan_comun(e, estados_x(*est))


def _par(start_esp, hasta_esp=None, **kw):
    e_, s_ = unidad(1, 2, "pX", esp_desde=start_esp, esp_hasta=hasta_esp or start_esp + 2, final=None, **kw)
    return e_, s_


@pytest.mark.parametrize("desde,vinculada", [(2, True), (3, True), (4, True), (5, False), (7, False)])
def test_link_window_is_two_regular_periods_after_the_last_plan_comun_period(desde, vinculada):
    e_, s_ = _par(desde)                       # Plan Comun lasts slots 1-2
    v = _vinculos(e_, s_)
    assert (len(v) == 1) is vinculada
    if vinculada:
        assert v.iloc[0]["episodio_id"] == 1 and v.iloc[0]["episodio_esp"] == 2


def test_specialty_before_the_plan_comun_or_of_another_family_or_another_person_is_not_linked():
    antes = [ep(1, persona="pX", prog=PC, adm="201710"), ep(2, persona="pX", prog=ESP, adm="201610")]
    est = mat(1, "pX", "201710", 1, 2, PC) + mat(2, "pX", "201610", 1, 6, ESP)
    assert len(_vinculos(antes, est)) == 0                                          # the specialty starts earlier
    otra = [ep(1, persona="pX", prog=PC), ep(2, persona="pX", prog="C1")]
    assert len(_vinculos(otra, mat(1, "pX", ADM, 1, 2, PC) + mat(2, "pX", ADM, 3, 6, "C1"))) == 0
    otra_persona = [ep(1, persona="pX", prog=PC), ep(2, persona="pY", prog=ESP)]
    assert len(_vinculos(otra_persona, mat(1, "pX", ADM, 1, 2, PC) + mat(2, "pY", ADM, 3, 6, ESP))) == 0
    otro_nivel = [ep(1, persona="pX", prog=PC), ep(2, persona="pX", prog=ESP, nivel=8)]
    assert len(_vinculos(otro_nivel, mat(1, "pX", ADM, 1, 2, PC) + mat(2, "pX", ADM, 3, 6, ESP))) == 0


def test_the_first_later_specialty_is_the_one_linked_and_other_programs_in_between_are_ignored():
    eps = [ep(1, persona="pX", prog=PC), ep(2, persona="pX", prog="C1"), ep(3, persona="pX", prog=ESP),
           ep(4, persona="pX", prog=ESP2)]
    est = mat(1, "pX", ADM, 1, 2, PC) + mat(2, "pX", ADM, 2, 2, "C1") + mat(3, "pX", ADM, 3, 6, ESP) \
        + mat(4, "pX", ADM, 4, 7, ESP2)
    v = _vinculos(eps, est)
    assert len(v) == 1 and v.iloc[0]["episodio_esp"] == 3 and v.iloc[0]["cod_programa_esp"] == ESP


def test_a_later_specialty_beyond_the_window_does_not_rescue_the_first_one_out_of_the_window():
    """'First later episode' is decided before the window: the earlier one (out of the window) blocks the later one."""
    eps = [ep(1, persona="pX", prog=PC), ep(2, persona="pX", prog=ESP), ep(3, persona="pX", prog=ESP2)]
    # both start after the window (slot 6 and 8): neither links
    est = mat(1, "pX", ADM, 1, 2, PC) + mat(2, "pX", ADM, 6, 8, ESP) + mat(3, "pX", ADM, 8, 9, ESP2)
    assert len(_vinculos(eps, est)) == 0


def test_a_specialty_is_linked_to_one_plan_comun_only():
    eps = [ep(1, persona="pX", prog=PC), ep(2, persona="pX", prog=PC, adm=per(ADM, 2)), ep(3, persona="pX", prog=ESP)]
    est = mat(1, "pX", ADM, 1, 3, PC) + mat(2, "pX", ADM, 3, 4, PC) + mat(3, "pX", ADM, 5, 9, ESP)
    v = _vinculos(eps, est)
    assert list(v["episodio_esp"]) == [3] and list(v["episodio_id"]) == [2]        # the closer (later) Plan Comun keeps it


def test_requirements_on_admission_code_or_period_are_not_imposed():
    e_, s_ = unidad(1, 2, "pX", esp_desde=3, adm_esp=per(ADM, 3), cod_esp="LS", final=None)     # different period, LS
    assert len(_vinculos(e_, s_)) == 1


# ---------------------------------------------------------------------------------------------
# one trajectory, no double counting
# ---------------------------------------------------------------------------------------------
def test_the_linked_specialty_episode_is_not_a_separate_unit():
    e, s, a = mundo_pc()
    snap, _, embudo = construir(e, s, a)
    assert not ESPECIALIDADES & set(snap["episodio_id"])
    # one row per person and cut for the merged people
    d = snap[snap["persona_key"].isin(["pA", "pB", "pC"])]
    assert d.groupby(["k", "persona_key"]).size().max() == 1
    por_k = {r["k"]: r for r in embudo}
    assert por_k[2]["especialidades_absorbidas"] == 7
    assert por_k[2]["plan_comun_unidos"] == 7 and por_k[2]["plan_comun_sin_continuacion"] == 1
    assert por_k[2]["plan_comun_episodios"] == 8
    # an ordinary specialty student (301) stays as its own unit
    assert 301 in set(snap["episodio_id"])
    for r in embudo:
        assert r["poblacion"] - r["sin_matricula_en_corte"] - r["salida_en_corte"] - r["ya_egresado_o_titulado"] \
            - r["sin_seguimiento"] == r["elegibles"]


def test_the_double_counts_avoided_are_reported_per_cut():
    e, s, a = mundo_pc()
    _, _, embudo = construir(e, s, a)
    por_k = {r["k"]: r for r in embudo}
    # k = 0: absorbed specialties that would have been eligible at the cut as a separate unit (they enroll in slot 1? no)
    assert por_k[0]["especialidades_absorbidas_elegibles"] == 0                    # none of them is enrolled in slot 1
    assert por_k[2]["especialidades_absorbidas_elegibles"] >= 5                    # those that start at slot 2 would be counted twice


# ---------------------------------------------------------------------------------------------
# event and time of merged trajectories
# ---------------------------------------------------------------------------------------------
def test_event_and_time_come_from_the_specialty_counted_from_the_plan_comun_admission():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    for k in (0, 2):
        r = fila(snap, 101, k)
        assert (r["tiempo"], r["causa"]) == (10, R3.EGRESO)                          # egress of the specialty, slot 10
    r = fila(snap, 101, 4)
    assert (r["tiempo"], r["causa"]) == (10, R3.EGRESO)
    r = fila(snap, 102, 2)
    assert (r["tiempo"], r["causa"], r["salida_tipo"]) == (9, R3.SALIDA, "explicita")   # exit state of the specialty
    r = fila(snap, 103, 4)
    assert (r["tiempo"], r["causa"], r["salida_tipo"]) == (10, R3.SALIDA, "ausencia")   # absence after slot 9 (LS, later admission)
    assert pd.isna(fila(snap, 101, 2)["salida_a_otro_programa"])
    assert fila(snap, 102, 2)["salida_a_otro_programa"] == False                   # noqa: E712  (the absorbed specialty is not "another program")


def test_the_plan_comun_exit_of_a_linked_trajectory_is_not_an_exit_of_the_trajectory():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    # 101 has an exit state in the Plan Comun episode at slot 2 (the cut period of k = 2): it is still at risk
    assert 101 in set(snap.loc[snap["k"] == 2, "episodio_id"])
    assert fila(snap, 101, 2)["causa"] == R3.EGRESO


def test_plan_comun_without_continuation_keeps_todays_handling():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    r = fila(snap, 104, 2)
    assert (r["tiempo"], r["causa"], r["salida_tipo"]) == (3, R3.SALIDA, "explicita")
    assert r["cod_programa"] == PC and bool(r["trayectoria_plan_comun"]) and not bool(r["especialidad_conocida_al_corte"])
    assert pd.isna(r["episodio_especialidad_id"])


def test_the_covariates_and_split_of_a_merged_trajectory_are_those_of_the_plan_comun_admission():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    r = fila(snap, 103, 4)
    assert r["periodo_admision"] == ADM and r["cohorte_anio"] == 2016 and r["split"] == "train"
    assert r["cod_admision"] == "LS"                                                # Plan Comun's own admission profile
    assert r["episodio_especialidad_id"] == 203


# ---------------------------------------------------------------------------------------------
# program in force at the cut, flags and the learned constant
# ---------------------------------------------------------------------------------------------
def test_program_features_follow_the_program_in_force_at_each_cut():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    r0 = fila(snap, 101, 0)                                                         # k = 0: Plan Comun, specialty never known
    assert r0["cod_programa"] == PC and not bool(r0["especialidad_conocida_al_corte"]) and bool(r0["trayectoria_plan_comun"])
    assert r0["creditos_malla_total"] == 18.0 and bool(r0["malla_conocida"])
    r2 = fila(snap, 101, 2)                                                         # specialty first state at slot 2: known
    assert r2["cod_programa"] == ESP and bool(r2["especialidad_conocida_al_corte"])
    assert r2["creditos_malla_total"] == 36.0 and r2["duracion_nominal"] == 10
    assert r2["creditos_esperados"] == 18.0 and r2["creditos_aprobados"] == 12.0
    assert r2["avance_malla"] == pytest.approx(12.0 / 18.0) and r2["fraccion_malla"] == pytest.approx(12.0 / 36.0)
    r4 = fila(snap, 101, 4)
    assert r4["cod_programa"] == ESP and r4["creditos_esperados"] == 30.0
    assert r4["creditos_aprobados"] == 18.0                                          # PC (A, B) + specialty S at slot 3


def test_a_specialty_that_starts_after_the_cut_is_unknown_at_the_cut():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    r2 = fila(snap, 102, 2)                                                         # specialty starts at slot 3
    assert r2["cod_programa"] == PC and not bool(r2["especialidad_conocida_al_corte"])
    assert r2["creditos_malla_total"] == 18.0 and r2["creditos_esperados"] == 18.0
    assert r2["creditos_aprobados"] == 12.0 and r2["avance_malla"] == pytest.approx(12.0 / 18.0)
    r4 = fila(snap, 102, 4)
    assert r4["cod_programa"] == ESP and bool(r4["especialidad_conocida_al_corte"])
    assert r4["creditos_aprobados"] == 24.0                                         # + P at slot 3, Q at slot 4


def test_specialty_admitted_later_counts_its_own_semesters_for_the_expected_credits():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    r4 = fila(snap, 103, 4)                                                         # specialty admitted 2 slots after the PC
    assert r4["cod_programa"] == ESP and bool(r4["especialidad_conocida_al_corte"])
    assert r4["creditos_esperados"] == 18.0                                          # malla semesters <= 4 - 2
    assert r4["duracion_nominal"] == 12                                              # 2 + nominal 10 of the specialty


def test_nominal_duration_before_the_specialty_is_known_is_the_plan_comun_value_plus_a_train_constant():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    # constant = median over TRAIN linked trajectories of (specialty offset + nominal duration) minus the Plan Comun duration
    assert fila(snap, 101, 0)["duracion_nominal"] == 10.0                            # 2 + (10 - 2)
    assert fila(snap, 104, 0)["duracion_nominal"] == 10.0                            # unlinked Plan Comun gets the same value
    assert fila(snap, 102, 2)["duracion_nominal"] == 10.0


def test_the_constant_is_learned_from_train_only():
    e, s, a = mundo_pc()
    base, _, _ = construir(e, s, a)
    # a VALID-cohort trajectory (2018) whose specialty is 14 semesters long must not move the constant
    e2, s2 = unidad(150, 250, "pZ", adm="201810", prog_esp=ESP_LARGA, final=("Z", 12))
    e_all = pd.concat([e, episodios(*e2)], ignore_index=True)
    s_all = pd.concat([s, estados_x(*s2)], ignore_index=True)
    snap, _, _ = construir(e_all, s_all, a)
    assert fila(snap, 101, 0)["duracion_nominal"] == fila(base, 101, 0)["duracion_nominal"]
    assert fila(snap, 150, 0)["duracion_nominal"] == 10.0                            # valid unit gets the train constant too
    # ...while the train specialties do move it
    e3, s3 = [], []
    for i in range(10):
        a_, b_ = unidad(500 + i, 600 + i, f"pT{i}", prog_esp=ESP_LARGA, final=("Z", 12))
        e3 += a_; s3 += b_
    snap2, _, _ = construir(pd.concat([e, episodios(*e3)], ignore_index=True),
                            pd.concat([s, estados_x(*s3)], ignore_index=True), a)
    assert fila(snap2, 101, 0)["duracion_nominal"] > 10.0


def test_flags_are_known_at_the_cut_and_do_not_reveal_whether_a_continuation_exists():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    k0 = snap[snap["k"] == 0]
    linked, alone = k0[k0["episodio_id"] == 102].iloc[0], k0[k0["episodio_id"] == 104].iloc[0]
    for col in ("trayectoria_plan_comun", "especialidad_conocida_al_corte", "cod_programa", "duracion_nominal",
                "creditos_malla_total", "malla_conocida"):
        assert linked[col] == alone[col], col                                         # identical covariates at k = 0
    assert not snap.loc[snap["k"] == 0, "especialidad_conocida_al_corte"].any()
    assert not snap.loc[~snap["trayectoria_plan_comun"].astype(bool), "especialidad_conocida_al_corte"].any()


def test_flags_are_model_features_and_the_link_id_is_not():
    assert "trayectoria_plan_comun" in F3.FEATURE_COLS_ADMISION
    assert "especialidad_conocida_al_corte" in F3.FEATURE_COLS_ADMISION
    assert "episodio_especialidad_id" in F3.LABEL_COLS                              # audit column of the link: never a feature
    assert "episodio_especialidad_id" not in set(F3.FEATURE_COLS_ADMISION) | set(F3.FEATURE_COLS_ACADEMICO)


def test_catalog_changes_are_counted_within_each_episode_not_across_the_program_change():
    e, s, a = mundo_pc()
    snap, _, _ = construir(e, s, a)
    assert fila(snap, 101, 4)["cambios_catalogo"] == 0                               # PC cat 2019 -> specialty cat 2019: none
    e2, s2 = unidad(150, 250, "pZ", cat_esp="2020", final=("Z", 10))
    snap2, _, _ = construir(pd.concat([e, episodios(*e2)], ignore_index=True), pd.concat([s, estados_x(*s2)], ignore_index=True), a)
    assert fila(snap2, 150, 4)["cambios_catalogo"] == 0                              # a different catalog in ANOTHER episode


def test_academic_aggregates_span_both_episodes_and_count_a_course_once():
    e, s, a = mundo_pc()
    a2 = pd.concat([a, intentos((201, per(ADM, 2), 5.0, "A"))], ignore_index=True)   # same course code approved again in the specialty
    a2["intento_id"] = range(1, len(a2) + 1)
    snap, _, _ = construir(e, s, a2)
    assert fila(snap, 101, 2)["creditos_aprobados"] == 12.0                           # A counted once, not 18
    assert fila(snap, 101, 2)["semestres_matriculados"] == 2


# ---------------------------------------------------------------------------------------------
# point in time: the future specialty never reaches an earlier cut
# ---------------------------------------------------------------------------------------------
NO_FEATURE = {"episodio_id", "k", "persona_key", "periodo_admision", "split", "sexo_equidad", *F3.LABEL_COLS}
FEATURES = [c for c in F3.SNAPSHOT_COLS_T3 if c not in NO_FEATURE]


def _igual(a, b, k):
    a, b = a[a["k"] == k].set_index("episodio_id"), b[b["k"] == k].set_index("episodio_id")
    assert list(a.index) == list(b.index) and len(a) >= 5
    for c in FEATURES:
        x, y = a[c], b[c]
        assert ((x == y) | (x.isna() & y.isna())).all(), (k, c)


def _corte(k):
    return lambda p: per(p, k)


@pytest.mark.parametrize("k", [0, 2, 4])
def test_perturbing_specialty_facts_after_the_cut_never_changes_the_features(k):
    e, s, a = mundo_pc()
    base, _, _ = construir(e, s, a)
    esp_ids = [i for i in ESPECIALIDADES]
    lim = per(ADM, k) if k >= 1 else "000000"
    a2 = a.copy()
    tarde = a2["episodio_id"].isin(esp_ids) & (a2["periodo"] > lim)
    a2.loc[tarde, "nota_numerica"] = 1.5
    a2.loc[tarde, "aprobado_curricular"] = False
    s2 = s.copy()
    tarde_s = s2["episodio_id"].astype(int).isin(esp_ids) & (s2["periodo"] > lim)
    s2 = s2.loc[~(tarde_s & (np.arange(len(s2)) % 2 == 0))].copy()                    # drop half of the later specialty states
    extra = estados_x(*[("pA", 201, per(ADM, 12), "E", ESP, "2019")])
    s2 = pd.concat([s2, extra], ignore_index=True)
    pert, _, _ = construir(e, s2, a2)
    _igual(base, pert, k)


@pytest.mark.parametrize("k", [2, 4])
def test_deleting_all_later_periods_of_the_specialty_never_changes_the_features(k):
    e, s, a = mundo_pc()
    base, _, _ = construir(e, s, a)
    esp_ids = list(ESPECIALIDADES)
    lim = per(ADM, k)
    s2 = s.loc[~(s["episodio_id"].astype(int).isin(esp_ids) & (s["periodo"] > lim))].reset_index(drop=True)
    a2 = a.loc[~(a["episodio_id"].isin(esp_ids) & (a["periodo"] > lim))].reset_index(drop=True)
    corto, _, _ = construir(e, s2, a2)
    _igual(base, corto, k)


@pytest.mark.parametrize("k", [0, 2])
def test_changing_the_future_specialty_program_never_changes_earlier_cuts(k):
    """102's specialty starts at slot 3: at k = 0 and 2 neither its program nor its catalog may reach the features."""
    e, s, a = mundo_pc()
    base, _, _ = construir(e, s, a)
    e2 = e.copy()
    e2.loc[e2["episodio_id"] == 202, ["cod_programa", "catalogo_inicial"]] = [ESP_LARGA, "2019"]
    s2 = s.copy()
    s2.loc[s2["episodio_id"].astype("Int64") == 202, "cod_programa"] = ESP_LARGA
    pert, _, _ = construir(e2, s2, a)
    _igual(base, pert, k)
    # ...and at k = 4 the new program is the one in force
    assert fila(pert, 102, 4)["cod_programa"] == ESP_LARGA


def test_mutation_the_guard_can_fail_when_the_specialty_known_at_the_cut_changes():
    e, s, a = mundo_pc()
    base, _, _ = construir(e, s, a)
    e2 = e.copy()
    e2.loc[e2["episodio_id"] == 201, "cod_programa"] = ESP_LARGA
    pert, _, _ = construir(e2, s, a)
    with pytest.raises(AssertionError):
        _igual(base, pert, 2)                                                        # 201 starts at slot 2: known at k = 2


def test_removing_the_specialty_leaves_the_features_of_the_cut_before_it_unchanged():
    e, s, a = mundo_pc()
    base, _, _ = construir(e, s, a)
    quitar = (s["episodio_id"].astype(int) == 202)
    s2 = s.loc[~quitar].reset_index(drop=True)
    sin, _, _ = construir(e, s2, a.loc[a["episodio_id"] != 202].reset_index(drop=True))
    _igual(base, sin, 2)


def test_vectorized_ordinal_equals_the_scalar_rule_on_a_grid():
    periodos = [f"{a}{s}" for a in (2014, 2015, 2019, 2026) for s in ("10", "15", "20", "25", "01", "00")]
    periodos += ["2016", "", "abcdef", None]
    v = F3._ordinal_slot(pd.Series(periodos, dtype="object"))
    for p, x in zip(periodos, v):
        esperado = R3.ordinal_periodo(p)
        assert (np.isnan(x) and esperado is None) or x == esperado, p


def test_a_snapshot_without_any_plan_comun_has_the_flags_off_and_no_constant():
    adm = ADM
    e = episodios(ep(1, persona="pa", prog=ESP))
    s = estados_x(*mat(1, "pa", adm, 1, 6, ESP))
    snap, _, embudo = construir(e, s, intentos())
    assert not snap["trayectoria_plan_comun"].any() and not snap["especialidad_conocida_al_corte"].any()
    assert snap["episodio_especialidad_id"].isna().all()
    assert embudo[0]["plan_comun_unidos"] == 0 and embudo[0]["constante_duracion_plan_comun"] == 0.0
