"""New variables of T3-T6 (docs/10, 11, 12 "variables nuevas"): pure rules, malla totals (P126), regulatory risk (P117/P118),
curricular reach (P121), progress speed, Capstone / practice by name (P125), own-vs-general performance, previous program
changes and the T6 graduation ranking. Point-in-time perturbation guards. No database."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features_variables as FV          # noqa: E402
from pipelines.snapshots import rules_variables as RV             # noqa: E402

ADM = "201710"            # slot 1 = 201710, 2 = 201720, 3 = 201810, 4 = 201820, 5 = 201910 ...
PER = {1: "201710", 2: "201720", 3: "201810", 4: "201820", 5: "201910", 6: "201920", 7: "202010"}


# ---------------------------------------------------------------------------------------------
# pure rules
# ---------------------------------------------------------------------------------------------
def test_regulation_in_force_changes_at_202520():
    assert RV.reglamento_vigente("202510") == "antiguo"
    assert RV.reglamento_vigente("202520") == "nuevo"
    assert RV.reglamento_vigente("202610") == "nuevo"
    assert RV.reglamento_vigente(None) is None


def test_cycle_comes_from_the_malla_semester_text():
    assert RV.ciclo_de_semestre_texto("Semestre 03 CP") == "CP"
    assert RV.ciclo_de_semestre_texto("Semestre 01 CB") == "CB"
    assert RV.ciclo_de_semestre_texto("Año 02 CP") == "CP"
    assert RV.ciclo_de_semestre_texto("Semestre 05") is None
    assert RV.ciclo_de_semestre_texto(None) is None


@pytest.mark.parametrize("nombre,esperado", [
    ("Capstone Project", "capstone"), ("PROYECTO DE TÍTULO - CAPSTONE", "capstone"), ("Int. al Capstone Project", None),
    ("Examen de Título ", "titulo"), ("Examen de Grado", "titulo"), ("Actividad de Titulación 2", "titulo"),
    ("Trabajo de Grado I", "titulo"), ("Seminario de Título II", "titulo"), ("Anteproyecto de Título", "titulo"),
    ("Práctica Pre-Profesional", "practica"), ("Practica Profesional 2", "practica"), ("Internado Cirugía", "practica"),
    ("Derecho y Práctica Médica", None), ("Hatha Yoga: Filosofía Práctica", None), ("Cálculo I", None), (None, None)])
def test_titulo_course_classification_by_name(nombre, esperado):
    assert RV.clasificar_titulo(nombre) == esperado


@pytest.mark.parametrize("codigo,esperado", [
    ("UNFP09338", "propia"), (None, "propia"), (float("nan"), "propia"), ("UNFG01148", "general"), ("UNFV00012", "general"),
    ("UNFE00001", "general"), ("UNFI00001", "otra"), ("UNES00001", "otra")])
def test_formation_type_from_the_malla_code(codigo, esperado):
    # P40: the prefixes are department codes. UNFP = Formacion Profesional, UNFG / UNFV / UNFE = general, valorica and elective
    # general formation; a course without code is the disciplinary core of the program (own).
    assert RV.tipo_formacion(codigo) == esperado


def test_thresholds_of_both_regulations():
    assert RV.UMBRAL_2DA_CB_ANTIGUO == 5 and RV.UMBRAL_2DA_CP_ANTIGUO == 3 and RV.UMBRAL_3RA_ANTIGUO == 1
    assert RV.UMBRAL_2DA_NUEVO == 6 and RV.UMBRAL_3RA_NUEVO == 2 and RV.PERIODOS_AVANCE_ANTIGUO == 2
    assert RV.ALCANCE_SEMESTRES == 4


# ---------------------------------------------------------------------------------------------
# malla totals (P126)
# ---------------------------------------------------------------------------------------------
def _malla(filas):
    cols = ["cod_programa", "catalogo", "codigo_asignatura", "semestre", "semestre_texto", "creditos", "formacion",
            "nombre_asignatura"]
    return pd.DataFrame(filas, columns=cols)


def test_elective_pool_counts_once_not_once_per_alternative():
    fijos = [("P1", "201910", f"0001-0000{i}", i, f"Semestre 0{i} CB", 30.0, None, f"Ramo {i}") for i in range(1, 4)]
    pool = [("P1", "201910", f"0002-{i:05d}", 3, "Semestre 03 CB", 4.0, "UNFG01148", f"Electivo {i}") for i in range(10)]
    t = FV.totales_malla(_malla(fijos + pool), pd.DataFrame({"cod_programa": ["P1"], "catalogo": ["201910"], "duracion": [3]}))
    r = t.set_index(["cod_programa", "catalogo"]).loc[("P1", "201910")]
    assert r["creditos_malla_bruto"] == 90.0 + 40.0               # the old sum: every alternative counted
    assert r["creditos_malla_total_corr"] == 90.0 + 4.0           # one slot per pool (same formation code and semester)
    assert r["n_pools"] == 1


def test_total_is_reliable_only_near_the_per_semester_scale():
    ok = [("P1", "201910", f"0001-0000{i}", i, "Semestre 01 CB", 30.0, None, f"Ramo {i}") for i in range(1, 5)]   # 120 / 4 = 30
    corto = [("P2", "201910", "0001-00001", 1, "Semestre 01 CB", 7.0, None, "Solo")]                              # 7 / 4 = 1.75
    pc = pd.DataFrame({"cod_programa": ["P1", "P2"], "catalogo": ["201910", "201910"], "duracion": [4, 4]})
    t = FV.totales_malla(_malla(ok + corto), pc).set_index("cod_programa")
    assert bool(t.loc["P1", "malla_creditos_confiable"]) is True
    assert bool(t.loc["P2", "malla_creditos_confiable"]) is False


def test_malla_flags_for_capstone_and_practice():
    f = [("P1", "201910", "0001-00001", 1, "Semestre 01 CB", 30.0, None, "Cálculo"),
         ("P1", "201910", "0001-00002", 10, "Semestre 10 CP", 30.0, None, "Capstone Project"),
         ("P1", "201910", "0001-00003", 9, "Semestre 09 CP", 10.0, None, "Práctica Profesional")]
    t = FV.totales_malla(_malla(f), pd.DataFrame({"cod_programa": ["P1"], "catalogo": ["201910"], "duracion": [10]}))
    r = t.iloc[0]
    assert bool(r["malla_tiene_capstone"]) and bool(r["malla_tiene_practica"])


# ---------------------------------------------------------------------------------------------
# attempts-based features
# ---------------------------------------------------------------------------------------------
MALLA = _malla([
    ("P1", "201910", "0001-00001", 1, "Semestre 01 CB", 4.0, "UNFG00001", "Calculo I"),
    ("P1", "201910", "0001-00002", 2, "Semestre 02 CB", 4.0, "UNFP00002", "Fisica I"),
    ("P1", "201910", "0001-00003", 2, "Semestre 02 CB", 4.0, "UNFP00003", "Quimica"),
    ("P1", "201910", "0001-00004", 3, "Semestre 03 CB", 4.0, "UNFP00004", "Algebra"),
    ("P1", "201910", "0001-00007", 7, "Semestre 07 CP", 4.0, "UNFP00007", "Control"),
    ("P1", "201910", "0001-00008", 9, "Semestre 09 CP", 4.0, "UNFP00008", "Capstone Project"),
    ("P1", "201910", "0001-00009", 9, "Semestre 09 CP", 4.0, "UNFP00009", "Práctica Profesional"),
    ("P1", "201910", "0001-00010", 5, "Semestre 05 CP", 4.0, "UNFP00010", "Termodinamica"),
    ("P1", "201910", "0001-00011", 6, "Semestre 06 CP", 4.0, "UNFP00011", "Fluidos"),
    ("P1", "201910", "0001-00012", 8, "Semestre 08 CP", 4.0, "UNFP00012", "Redes"),
])
POP = pd.DataFrame({"episodio_id": [1], "persona_key": ["a"], "periodo_admision": [ADM], "cod_programa": ["P1"],
                    "catalogo_inicial": ["201910"]})
CORTES = pd.DataFrame({"episodio_id": [1, 1], "k": [2, 4], "periodo_admision": [ADM, ADM], "cod_programa": ["P1", "P1"]})
EPISODIOS = pd.DataFrame({"episodio_id": [1], "persona_key": ["a"], "periodo_admision": [ADM], "cod_admision": ["RE"],
                          "id_nivel": [1], "cod_programa": ["P1"]})
PC = pd.DataFrame({"cod_programa": ["P1"], "catalogo": ["201910"], "duracion": [10]})


def att(slot, cod, opo, aprobado, nota=None, cred=4.0, titulo=None, evaluado=True, ep=1):
    nota = nota if nota is not None else (5.0 if aprobado else 3.0)
    return {"episodio_id": ep, "periodo": PER[slot], "codigo_asignatura": cod, "oportunidad": opo,
            "es_intento_evaluado": evaluado, "aprobado_curricular": aprobado, "nota_numerica": nota,
            "nota_es_heredada": False, "resultado_tipo": "evaluado", "creditos": cred, "creditos_reconocidos": None,
            "titulo": titulo, "cod_carrera": "P1", "catalogo": "201910"}


def construir(intentos, cortes=CORTES, malla=MALLA, episodios=EPISODIOS):
    it = pd.DataFrame(intentos)
    return FV.construir_variables(cortes, POP, it, malla, episodios, PC).set_index(["episodio_id", "k"])


def test_failed_in_second_and_third_opportunity_are_counted_per_course_and_cycle():
    f = construir([
        att(1, "0001-00001", 1, False), att(2, "0001-00001", 2, False), att(3, "0001-00001", 3, False),   # fails 1, 2 and 3
        att(1, "0001-00002", 1, False), att(2, "0001-00002", 2, False),                                    # fails 1, 2 (pending)
        att(2, "0001-00003", 1, False), att(3, "0001-00003", 2, True),                                     # fails 1, approves 2
    ])
    r = f.loc[(1, 4)]
    assert r["reg_rep2_total"] == 2          # Calculo I and Fisica I failed their 2nd opportunity
    assert r["reg_rep2_cb"] == 2 and r["reg_rep2_cp"] == 0
    assert r["reg_rep3_cursos"] == 1         # Calculo I failed its 3rd
    assert r["reg_cursos_riesgo_3ra"] == 1   # Fisica I: latest attempt failed in the 2nd opportunity
    assert r["reg_pendientes_reprobados"] == 2
    # old regulation (Ciclo Basico student): five 2nd-opportunity failures eliminate; one 3rd-opportunity failure does
    assert r["reg_dist_2da_antiguo"] == 5 - 2 and r["reg_dist_3ra_antiguo"] == 0
    # new regulation: six 2nd-opportunity failures; two distinct courses in the 3rd
    assert r["reg_dist_2da_nuevo"] == 6 - 2 and r["reg_dist_3ra_nuevo"] == 2 - 1


def test_cycle_professional_student_uses_the_stricter_second_opportunity_limit():
    f = construir([att(3, "0001-00007", 1, False), att(4, "0001-00007", 2, False)] +
                  [att(4, "0001-00010", 1, True)])
    r = f.loc[(1, 4)]
    assert r["reg_ciclo_cb_actual"] == 0 and r["reg_rep2_cp"] == 1
    assert r["reg_dist_2da_antiguo"] == 3 - 1


def test_failures_of_the_periods_without_recorded_failures_are_not_counted_P58():
    cortes = pd.DataFrame({"episodio_id": [1], "k": [6], "periodo_admision": [ADM], "cod_programa": ["P1"]})
    f = construir([att(5, "0001-00001", 1, False), att(6, "0001-00001", 2, False, evaluado=False),  # 201920: P58
                   att(6, "0001-00002", 1, True)], cortes=cortes)
    r = f.loc[(1, 6)]
    assert r["reg_rep2_total"] == 0           # the second-opportunity failure sits in 201920: unknown, not zero evidence
    assert r["reg_cursos_riesgo_3ra"] == 0


def test_low_progress_streak_counts_consecutive_recorded_semesters_under_half_of_the_enrolled_credits():
    f = construir([att(1, "0001-00001", 1, False), att(1, "0001-00002", 1, True),            # 4 / 8 = 0.5  (not below)
                   att(2, "0001-00003", 1, False), att(2, "0001-00004", 1, False),            # 0 / 8
                   att(3, "0001-00001", 2, False), att(3, "0001-00003", 2, False),            # 0 / 8
                   att(4, "0001-00001", 3, True), att(4, "0001-00003", 3, True)])             # 8 / 8
    assert f.loc[(1, 2)]["reg_n_sem_avance_lt50"] == 1 and f.loc[(1, 2)]["reg_consec_avance_lt50"] == 1
    r4 = f.loc[(1, 4)]
    assert r4["reg_n_sem_avance_lt50"] == 2 and r4["reg_consec_avance_lt50"] == 0     # the streak ended in slot 4
    assert f.loc[(1, 4)]["reg_dist_avance_antiguo"] == 2


def test_reach_rule_measures_the_gap_between_the_oldest_pending_course_and_the_current_semester():
    f = construir([att(1, "0001-00002", 1, False),                                  # semester-2 course failed, never approved
                   att(2, "0001-00007", 1, True),                                    # semester-7 course taken in the last slot
                   att(2, "0001-00003", 1, True)])
    r = f.loc[(1, 2)]
    assert r["alc_sem_pendiente_antiguo"] == 2
    assert r["alc_rezago"] == 7 - 2
    assert bool(r["alc_pendiente_gt4"]) is True
    assert r["alc_n_bloqueados"] == 3          # semesters 8 and 9 (two courses) beyond 2 + 4 = 6 ... Redes, Capstone, Practica


def test_reach_rule_is_empty_without_pending_courses():
    f = construir([att(1, "0001-00001", 1, True), att(2, "0001-00002", 1, True)])
    r = f.loc[(1, 2)]
    assert np.isnan(r["alc_sem_pendiente_antiguo"]) and r["alc_n_bloqueados"] == 0 and bool(r["alc_pendiente_gt4"]) is False


def test_remaining_credits_and_speed_use_the_corrected_total():
    f = construir([att(1, "0001-00001", 1, True), att(2, "0001-00002", 1, True), att(2, "0001-00003", 1, True)])
    r = f.loc[(1, 2)]
    assert r["creditos_malla_total_corr"] == 40.0                       # ten 4-credit courses
    # the malla total is 40 for a 10-semester program: 4 per semester is below the per-semester scale -> not reliable
    assert bool(r["malla_creditos_confiable"]) is False and np.isnan(r["creditos_restantes"])


def test_remaining_credits_when_the_total_is_reliable():
    malla = _malla([("P1", "201910", f"0001-{i:05d}", i, "Semestre 01 CB", 30.0, None, f"R{i}") for i in range(1, 11)])
    it = [{**att(1, "0001-00001", 1, True, cred=30.0)}, {**att(2, "0001-00002", 1, True, cred=30.0)}]
    f = construir(it, malla=malla)
    r = f.loc[(1, 2)]
    assert bool(r["malla_creditos_confiable"]) is True and r["creditos_malla_total_corr"] == 300.0
    assert r["creditos_restantes"] == 300.0 - 60.0
    assert r["velocidad_aprobacion"] == pytest.approx(60.0 / 2)         # credits approved per enrolled semester
    assert r["velocidad_relativa"] == pytest.approx(30.0 / (300.0 / 10))


def test_capstone_and_practice_flags_at_the_cut():
    f = construir([att(1, "0001-00001", 1, True),
                   att(2, "0001-00008", 1, False, titulo="Capstone Project"),
                   att(2, "0001-00009", 1, True, titulo="Practica Profesional")])
    r = f.loc[(1, 2)]
    assert r["cap_inscrito"] == 1 and r["cap_aprobado"] == 0 and r["prac_inscrita"] == 1 and r["prac_aprobada"] == 1
    assert bool(r["malla_tiene_capstone"]) and bool(r["malla_tiene_practica"])


def test_own_versus_general_formation_performance():
    f = construir([att(1, "0001-00001", 1, True, nota=6.0),            # UNFG: general
                   att(1, "0001-00002", 1, True, nota=5.0), att(1, "0001-00003", 1, False, nota=3.0)])   # UNFP: own
    r = f.loc[(1, 2)]
    assert r["n_generales_eval"] == 1 and r["n_propios_eval"] == 2
    assert r["prom_generales"] == pytest.approx(6.0) and r["prom_propios"] == pytest.approx(4.0)
    assert r["tasa_propios"] == pytest.approx(0.5) and r["tasa_generales"] == pytest.approx(1.0)
    assert r["brecha_propios_generales"] == pytest.approx(4.0 - 6.0)


def test_previous_program_changes_are_the_episodes_admitted_before_this_one():
    ep = pd.DataFrame({"episodio_id": [1, 2, 3, 4], "persona_key": ["a", "a", "a", "b"],
                       "periodo_admision": ["201510", "201610", ADM, ADM], "cod_admision": ["RE", "CC", "CC", "CC"],
                       "id_nivel": [1, 1, 1, 1], "cod_programa": ["P9", "P8", "P1", "P1"]})
    pop = POP.assign(episodio_id=3, persona_key="a")
    cortes = CORTES.assign(episodio_id=3)
    f = FV.construir_variables(cortes, pop, pd.DataFrame([att(1, "0001-00001", 1, True, ep=3)]), MALLA, ep, PC).set_index(["episodio_id", "k"])
    r = f.loc[(3, 2)]
    assert r["n_episodios_previos"] == 2 and r["n_cc_previos"] == 1       # episode 2 (CC) and episode 1; later ones do not count


# ---------------------------------------------------------------------------------------------
# point-in-time guard: nothing after the cut may change a feature
# ---------------------------------------------------------------------------------------------
def test_attempts_after_the_cut_never_change_a_feature():
    base = [att(1, "0001-00001", 1, False), att(2, "0001-00001", 2, False), att(1, "0001-00002", 1, True),
            att(2, "0001-00008", 1, True, titulo="Capstone Project")]
    futuro = [att(3, "0001-00001", 3, False), att(4, "0001-00003", 1, False), att(4, "0001-00009", 1, True, titulo="Practica Profesional")]
    a = construir(base).loc[(1, 2)]
    b = construir(base + futuro).loc[(1, 2)]
    pd.testing.assert_series_equal(a, b)
    # the later cut does see the added attempts
    assert not construir(base).loc[(1, 4)].equals(construir(base + futuro).loc[(1, 4)])


def test_k_zero_has_only_static_malla_facts():
    cortes = pd.DataFrame({"episodio_id": [1], "k": [0], "periodo_admision": [ADM], "cod_programa": ["P1"]})
    f = construir([att(1, "0001-00001", 1, True)], cortes=cortes)
    r = f.loc[(1, 0)]
    assert r["creditos_malla_total_corr"] == 40.0 and bool(r["malla_tiene_capstone"])
    assert np.isnan(r["creditos_restantes"]) and np.isnan(r["reg_rep2_total"]) and np.isnan(r["cap_inscrito"])


# ---------------------------------------------------------------------------------------------
# T6: graduation ranking within the program, using earlier graduates only
# ---------------------------------------------------------------------------------------------
def test_graduation_ranking_uses_only_graduates_up_to_the_same_semester():
    d = pd.DataFrame({"episodio_id": [1, 2, 3, 4, 5, 6], "cod_programa": ["P1"] * 6,
                      "ord_egreso": [100, 101, 102, 103, 104, 105],
                      "promedio_evaluado": [4.0, 5.0, 6.0, 5.5, 4.5, 7.0]})
    r = FV.ranking_egreso(d, n_min=3, ventana=100).set_index("episodio_id")["ranking_prom_egreso"]
    assert np.isnan(r.loc[1]) and np.isnan(r.loc[2])                    # fewer than n_min earlier-or-same graduates
    assert r.loc[3] == pytest.approx(1.0)                                # best among the first three
    assert r.loc[5] == pytest.approx(2 / 5)                              # 4.0 and 4.5 are <= 4.5 among the five
    # perturbation: a later graduate cannot change the ranking of an earlier one
    d2 = pd.concat([d, pd.DataFrame({"episodio_id": [9], "cod_programa": ["P1"], "ord_egreso": [200], "promedio_evaluado": [1.0]})])
    r2 = FV.ranking_egreso(d2, n_min=3, ventana=100).set_index("episodio_id")["ranking_prom_egreso"]
    pd.testing.assert_series_equal(r.dropna(), r2.loc[r.dropna().index])


def test_graduation_ranking_is_within_program():
    d = pd.DataFrame({"episodio_id": [1, 2, 3, 4, 5, 6], "cod_programa": ["P1", "P1", "P1", "P2", "P2", "P2"],
                      "ord_egreso": [100, 100, 100, 100, 100, 100], "promedio_evaluado": [4.0, 5.0, 6.0, 6.5, 6.6, 6.7]})
    r = FV.ranking_egreso(d, n_min=3, ventana=100).set_index("episodio_id")["ranking_prom_egreso"]
    assert r.loc[3] > r.loc[1] and r.loc[6] > r.loc[4]
    assert r.loc[3] == pytest.approx(r.loc[6])                            # best of its own program in both


def test_titulo_grade_uses_the_last_evaluated_attempt_up_to_the_cut_only():
    it = pd.DataFrame([att(1, "0001-00008", 1, False, nota=3.0, titulo="Capstone Project"),
                       att(2, "0001-00008", 2, True, nota=5.5, titulo="Capstone Project"),
                       att(3, "0001-00008", 3, True, nota=7.0, titulo="Capstone Project"),      # after the cut
                       att(2, "0001-00009", 1, True, nota=6.0, titulo="Práctica Profesional")])
    cortes = pd.DataFrame({"episodio_id": [1], "k": [2]})
    r = FV.nota_titulo(it, cortes, POP).iloc[0]
    assert r["nota_titulo"] == pytest.approx(5.5) and r["nota_practica"] == pytest.approx(6.0)


def test_titulo_grade_is_missing_without_any_such_course():
    r = FV.nota_titulo(pd.DataFrame([att(1, "0001-00001", 1, True)]), pd.DataFrame({"episodio_id": [1], "k": [2]}), POP).iloc[0]
    assert np.isnan(r["nota_titulo"]) and np.isnan(r["nota_practica"])
