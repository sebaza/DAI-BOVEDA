"""View "Lo que viene": populations, range, Art. 46 threshold, no double counting, groups of any size and the reproduction gate."""
import json
import re

import numpy as np
import pandas as pd
import pytest

from evaluation import modelos_conservados as MC
from evaluation import vista_proyeccion as VP
from pipelines.marts import vista_proyeccion as MV


# ------------------------------------------------------------------------------------------------ helpers
def poblacion(inicio, n, cohorte, k, modelo, corte, horizonte, p, facultad="Ingeniería", obs=0, p2=None, persona=None):
    ids = np.arange(inicio, inicio + n)
    d = pd.DataFrame({"episodio_id": ids, "persona_key": [f"x{i}" for i in ids] if persona is None else persona,
                      "facultad": facultad, "cohorte": cohorte, "k": k, "modelo": modelo, "corte": corte,
                      "horizonte": horizonte, "p": float(p), "obs": np.arange(n) < obs})
    if p2 is not None:                                  # egress block: cumulative at the nominal duration and two semesters later
        d["p_nominal"], d["p_nominal_mas_2"] = float(p), float(p2)
        d["per_nominal"], d["per_nominal_mas_2"] = "203010", "203110"
    return d


def eliminacion(n25=30, n24=25, facultad="Ingeniería"):
    return pd.concat([poblacion(1, n25, 2025, 2, "gru_adm", "202520", "202620", 0.1, facultad, obs=3),
                      poblacion(1000, n24, 2024, 4, "gru_agg", "202520", "202620", 0.2, facultad, obs=2)], ignore_index=True)


PER_ATT = {"202610": "202610", "202620": "202620"}


def intento(ep, codigo, opo, periodo="202610", aprobado=False, evaluado=True):
    return {"episodio_id": ep, "periodo": periodo, "codigo_asignatura": codigo, "oportunidad": opo,
            "es_intento_evaluado": evaluado, "aprobado_curricular": aprobado}


def intentos_y_actuales():
    """58 current students by Art. 46 distance: 12 at the threshold (6 courses failed in the 2nd opportunity), 22 at one (5 of 2nd plus
    a pending course failed once; or 1 course of 3rd plus a course failed twice), 12 at two (4 of 2nd, all pending) and 12 far away
    (no failure at all)."""
    filas, grupos, ep = [], {}, 0
    plan = [("umbral", 12, lambda e: [intento(e, f"C{j}", 2) for j in range(6)]),
            ("a1_rep2", 11, lambda e: [intento(e, f"C{j}", 2) for j in range(5)] + [intento(e, "C9", 1)]),
            ("a1_rep3", 11, lambda e: [intento(e, "C0", 3), intento(e, "C1", 2)]),
            ("a2", 12, lambda e: [intento(e, f"C{j}", 2) for j in range(4)]),
            ("lejos", 12, lambda e: [intento(e, "C0", 1, aprobado=True)])]
    for nombre, n, f in plan:
        for _ in range(n):
            ep += 1
            filas += f(ep)
            grupos[ep] = nombre
    actuales = pd.DataFrame({"episodio_id": list(grupos), "facultad": "Ingeniería", "cod_programa": "P1", "cohorte": 2023,
                             "persona_key": [f"p{e}" for e in grupos]})
    return pd.DataFrame(filas), actuales, grupos


# ------------------------------------------------------------------------------------------------ the spec table
def test_poblaciones_match_the_spec_table():
    assert VP.CORTE_ACTUAL == "202610"
    assert VP.POBLACIONES == (
        {"bloque": "continuidad", "tarea": "t1", "k": 1, "modelo": "cb_ben_pit", "cohorte": 2026},
        {"bloque": "continuidad", "tarea": "t1", "k": 2, "modelo": "lr_acad", "cohorte": 2025},
        {"bloque": "eliminacion", "tarea": "t5", "k": 2, "modelo": "gru_adm", "cohorte": 2025},
        {"bloque": "eliminacion", "tarea": "t5", "k": 4, "modelo": "gru_agg", "cohorte": 2024},
        {"bloque": "egreso", "tarea": "t3", "k": 0, "modelo": "dt_lr_adm", "cohorte": 2026},
        {"bloque": "egreso", "tarea": "t3", "k": 2, "modelo": "nn_gru", "cohorte": 2025},
        {"bloque": "egreso", "tarea": "t3", "k": 4, "modelo": "nn_gru", "cohorte": 2024})
    for p in VP.POBLACIONES:                       # every population is a kept model
        assert (p["tarea"], p["k"], p["modelo"]) in MC.CLAVES


# ------------------------------------------------------------------------------------------------ range
def test_rango_is_sum_and_normal_interval():
    s, lo, hi = VP.rango(np.array([0.5] * 100))
    assert s == pytest.approx(50) and lo == pytest.approx(50 - 9.8) and hi == pytest.approx(50 + 9.8)


def test_rango_is_clipped_to_zero_and_n():
    s, lo, hi = VP.rango(np.array([0.99, 0.99, 0.01]))
    assert 0 <= lo <= s <= hi <= 3
    assert VP.rango(np.zeros(5)) == (0.0, 0.0, 0.0)
    assert VP.rango(np.ones(5)) == (5.0, 5.0, 5.0)


# ------------------------------------------------------------------------------------------------ Art. 46 threshold
def test_umbral_categories_are_exclusive_and_use_art46():
    intentos, actuales, grupos = intentos_y_actuales()
    u = VP.umbral_actual(intentos, actuales).set_index("episodio_id")
    dist = {"umbral": 0, "a1_rep2": 1, "a1_rep3": 1, "a2": 2, "lejos": 6}
    for ep, g in grupos.items():
        assert u.loc[ep, "distancia"] == dist[g], g
    assert u.loc[1, "reg_rep2_total"] == 6 and u.loc[1, "reg_rep3_cursos"] == 0         # 6 rep2 -> at the threshold
    assert u.loc[25, "reg_rep3_cursos"] == 1 and u.loc[25, "pend_2da"] == 1             # 1 course of 3rd + one failed twice -> one away
    b = VP.bloque_umbral(u.reset_index())
    assert b["n"] == 58 and b["nota_p58"] is True
    assert (b["en_umbral"], b["a_1"], b["a_2"], b["lejos"]) == (12, 22, 12, 12)
    assert b["en_umbral"] + b["a_1"] + b["a_2"] + b["lejos"] == b["n"]


def test_distance_counts_the_failures_still_needed():
    def d(rep2=0, rep3=0, p1=0, p2=0):
        c = pd.DataFrame({"episodio_id": [1], "reg_rep2_total": [rep2], "reg_rep3_cursos": [rep3], "pend_1ra": [p1], "pend_2da": [p2]})
        return int(VP.distancia_umbral(c).loc[0, "distancia"])

    assert d() == 6                                   # no failures: 12 for the 2nd criterion, 3 + 3 for the 3rd
    assert d(rep3=2) == 0 and d(rep2=6) == 0
    assert d(rep2=5) == 2                             # the missing course must fail twice ...
    assert d(rep2=5, p1=1) == 1                       # ... unless one is pending after a failed 1st opportunity
    assert d(rep3=1, p2=1) == 1                       # a course at risk of the 3rd opportunity
    assert d(rep3=1) == 3                             # no course at risk: it needs three failures
    assert d(p2=2) == 2 and d(p1=2) == 4


def test_a_course_failed_twice_in_second_opportunity_counts_once_and_passes_do_not_count():
    intentos = pd.DataFrame([intento(1, "C0", 2), intento(1, "C0", 2, periodo="202520"), intento(1, "C1", 2, aprobado=True),
                             intento(1, "C2", 2, evaluado=False)])
    u = VP.umbral_actual(intentos, pd.DataFrame({"episodio_id": [1], "facultad": ["X"]}))
    assert u.loc[0, "reg_rep2_total"] == 1


def test_future_attempts_do_not_change_the_threshold():
    intentos, actuales, _ = intentos_y_actuales()
    antes = VP.umbral_actual(intentos, actuales)
    futuro = pd.DataFrame([intento(e, f"F{j}", 2, periodo="202620") for e in actuales["episodio_id"] for j in range(3)]
                          + [intento(e, "F9", 3, periodo="202710") for e in actuales["episodio_id"]])
    despues = VP.umbral_actual(pd.concat([intentos, futuro], ignore_index=True), actuales)
    pd.testing.assert_frame_equal(antes, despues)


def test_umbral_has_all_four_categories_for_small_faculty():
    u = pd.DataFrame({"episodio_id": range(60), "distancia": [0] * 4 + [1] * 6 + [2] * 20 + [3] * 30})
    b = VP.bloque_umbral(u)
    assert (b["n"], b["en_umbral"], b["a_1"], b["a_2"], b["lejos"]) == (60, 4, 6, 20, 30)
    assert "otros" not in b and b["en_umbral"] + b["a_1"] + b["a_2"] + b["lejos"] == b["n"]
    chica = VP.bloque_umbral(pd.DataFrame({"episodio_id": range(3), "distancia": [0, 0, 5]}))
    assert (chica["n"], chica["en_umbral"], chica["a_1"], chica["a_2"], chica["lejos"]) == (3, 2, 0, 0, 1)    # empty categories are 0, never missing


def test_threshold_block_is_published_for_a_few_students_and_none_for_nobody():
    assert VP.bloque_umbral(pd.DataFrame({"episodio_id": range(9), "distancia": [0] * 9}))["en_umbral"] == 9
    assert VP.bloque_umbral(pd.DataFrame({"episodio_id": [], "distancia": []})) is None


# ------------------------------------------------------------------------------------------------ blocks
def test_nobody_is_counted_twice_within_a_block():
    d = eliminacion()
    b = VP.bloque_eliminacion(d)
    assert b["n"] == 55 and sum(c["n"] for c in b["por_cohorte"]) == b["n"]
    assert d["episodio_id"].is_unique
    esperado = 30 * 0.1 + 25 * 0.2
    assert b["esperados"] == pytest.approx(esperado, abs=0.05) and b["lo"] < b["esperados"] < b["hi"]
    solapada = pd.concat([d, d.iloc[:3]], ignore_index=True)
    with pytest.raises(ValueError, match="twice"):
        VP.bloque_eliminacion(solapada)


def test_elimination_reports_what_already_happened_apart_and_never_adds_it_to_the_expected():
    d = eliminacion()
    b = VP.bloque_eliminacion(d)
    assert b["observados_hasta_hoy"] == 5                                             # 3 + 2 observed: exact
    assert b["periodo_observado"] == "202610" and b["orientativo"] is True
    d2 = d.assign(obs=True)
    b2 = VP.bloque_eliminacion(d2)
    assert b2["observados_hasta_hoy"] == 55
    assert b2["esperados"] == b["esperados"]                                         # unchanged by what was observed
    assert all("observados_hasta_hoy" not in c for c in b2["por_cohorte"])           # reported once, for the whole block


def test_every_cohort_entry_carries_its_cut_and_horizon():
    c = VP.bloque_eliminacion(eliminacion())["por_cohorte"]
    assert {(e["cohorte"], e["k"], e["modelo"]["modelo"], e["corte"], e["horizonte"]) for e in c} == {
        (2025, 2, "gru_adm", "202520", "202620"), (2024, 4, "gru_agg", "202520", "202620")}


def test_small_cohort_groups_are_listed_one_by_one_without_otros():
    d = pd.concat([poblacion(1, 30, 2025, 2, "gru_adm", "202520", "202620", 0.1),
                   poblacion(1000, 4, 2024, 4, "gru_agg", "202520", "202620", 0.2),
                   poblacion(2000, 6, 2023, 4, "gru_agg", "202510", "202610", 0.2)], ignore_index=True)
    b = VP.bloque_eliminacion(d)
    assert b["n"] == 40 and sum(c["n"] for c in b["por_cohorte"]) == 40
    assert [(c["cohorte"], c["n"]) for c in b["por_cohorte"]] == [(2025, 30), (2024, 4), (2023, 6)]
    assert all(c["cohorte"] != "otros" for c in b["por_cohorte"])


def test_projection_published_for_group_of_one():
    d = poblacion(1, 1, 2026, 1, "cb_ben_pit", "202610", "202710", 0.8)
    b = VP.bloque_continuidad(d)
    assert b["n"] == 1 and b["esperados"] == pytest.approx(0.8) and "lo" in b and "hi" in b
    assert 0 <= b["lo"] <= b["esperados"] <= b["hi"] <= 1
    assert b["por_cohorte"][0]["esperados"] == pytest.approx(0.8) and "lo" in b["por_cohorte"][0]
    e = poblacion(1, 1, 2025, 2, "nn_gru", "202520", "nominal_mas_2", 0.3, p2=0.5)
    e["trunc"] = False
    g = VP.bloque_egreso(e)
    assert g["nominal"]["esperados"] == pytest.approx(0.3) and g["nominal"]["lo"] <= 0.3 <= g["nominal"]["hi"]


def test_block_is_none_only_for_nobody():
    assert VP.bloque_continuidad(poblacion(1, 9, 2026, 1, "cb_ben_pit", "202610", "202710", 0.8))["n"] == 9
    assert VP.bloque_continuidad(poblacion(1, 0, 2026, 1, "cb_ben_pit", "202610", "202710", 0.8)) is None


def test_continuity_expected_is_the_sum_of_the_probability_of_continuing():
    d = pd.concat([poblacion(1, 40, 2026, 1, "cb_ben_pit", "202610", "202710", 0.9),
                   poblacion(1000, 20, 2025, 2, "lr_acad", "202520", "202620", 0.7)], ignore_index=True)
    b = VP.bloque_continuidad(d)
    assert b["n"] == 60 and b["esperados"] == pytest.approx(40 * 0.9 + 20 * 0.7, abs=0.05)
    assert 0 <= b["lo"] < b["esperados"] < b["hi"] <= 60


def test_egress_hito_is_the_cumulative_incidence_at_the_nominal_slot_with_its_calendar_period():
    cif = np.tile(np.linspace(0.05, 1.0, 20), (2, 1))                      # k = 0: u = 1..20
    p, per, trunc = VP.hito_egreso(cif, ["202610", "202610"], np.array([10, 8]), 0, 0)
    assert p[0] == pytest.approx(cif[0, 9]) and p[1] == pytest.approx(cif[1, 7])    # u = slot - k
    assert per == ["203020", "202920"] and not trunc.any()                          # slot 10 of 202610 is 203020
    p2, per2, _ = VP.hito_egreso(cif, ["202610", "202610"], np.array([10, 8]), 0, 2)
    assert p2[0] == pytest.approx(cif[0, 11]) and per2[0] == "203120"
    p4, per4, _ = VP.hito_egreso(cif[:, :16], ["202410", "202410"], np.array([10, 10]), 4, 0)       # k = 4: U = 16, u = 6
    assert p4[0] == pytest.approx(cif[0, 5]) and per4[0] == "202820"


def test_egress_milestone_already_in_the_past_is_not_a_projection():
    cif = np.tile(np.linspace(0.05, 1.0, 16), (3, 1))                      # k = 4, cohort 2024: slot 5 is 202610 (already happened)
    p, per, _ = VP.hito_egreso(cif, ["202410"] * 3, np.array([4, 5, 7]), 4, 0)       # duration <= k, = the closed period, ahead
    assert np.isnan(p[0]) and np.isnan(p[1]) and per[:2] == [None, None]
    assert p[2] == pytest.approx(cif[2, 2]) and per[2] > "202610"
    p2, per2, _ = VP.hito_egreso(cif, ["202410"] * 3, np.array([2, 3, 4]), 4, 2)     # nominal + 2 <= k for the first one
    assert np.isnan(p2[0]) and np.isnan(p2[1]) and per2[2] == "202620" and not np.isnan(p2[2])


def test_egress_milestone_beyond_the_model_horizon_is_clipped_and_flagged():
    cif = np.tile(np.linspace(0.05, 1.0, 16), (1, 1))                      # k = 4: U = 16
    p, per, trunc = VP.hito_egreso(cif, ["202410"], np.array([19]), 4, 0)            # u = 15 fits; with +2 it does not
    assert not trunc[0]
    p, per, trunc = VP.hito_egreso(cif, ["202410"], np.array([19]), 4, 2)            # u = 17 > 16
    assert trunc[0] and p[0] == pytest.approx(cif[0, 15])


def test_egress_block_counts_milestones_already_past_apart_and_keeps_periods_in_the_future():
    d = pd.concat([poblacion(1, 40, 2025, 2, "nn_gru", "202520", "nominal_mas_2", 0.3, p2=0.5)], ignore_index=True)
    d.loc[:11, ["p_nominal", "per_nominal"]] = [np.nan, None]
    d["trunc"] = False
    b = VP.bloque_egreso(d)
    assert b["ya_pasado_nominal"] == 12 and b["ya_pasado_nominal_mas_2"] == 0 and b["horizonte_truncado"] == 0
    assert b["nominal"]["esperados"] == pytest.approx(28 * 0.3, abs=0.05)             # the past rows are out of the figure
    assert b["nominal"]["desde"] > "202610" and b["nominal_mas_2"]["esperados"] == pytest.approx(40 * 0.5, abs=0.05)


def test_egress_block_has_the_expected_at_nominal_and_nominal_plus_two_with_their_periods():
    d = pd.concat([poblacion(1, 40, 2026, 0, "dt_lr_adm", "202610", "nominal_mas_2", 0.2, p2=0.4),
                   poblacion(1000, 30, 2025, 2, "nn_gru", "202520", "nominal_mas_2", 0.3, p2=0.5)], ignore_index=True)
    b = VP.bloque_egreso(d)
    assert b["n"] == 70 and "regla" in b and "anios" not in b
    assert b["nominal"]["esperados"] == pytest.approx(40 * 0.2 + 30 * 0.3, abs=0.05)
    assert b["nominal_mas_2"]["esperados"] == pytest.approx(40 * 0.4 + 30 * 0.5, abs=0.05)
    assert (b["nominal"]["desde"], b["nominal"]["hasta"]) == ("203010", "203010")
    assert b["nominal"]["lo"] <= b["nominal"]["esperados"] <= b["nominal"]["hi"]
    assert sum(c["n"] for c in b["por_cohorte"]) == 70
    assert all({"nominal", "nominal_mas_2"} <= set(c) for c in b["por_cohorte"])


def test_egress_milestone_with_few_rows_ahead_or_past_is_published_with_exact_counts():
    d = poblacion(1, 40, 2025, 2, "nn_gru", "202520", "nominal_mas_2", 0.3, p2=0.5)
    d["trunc"] = False
    d.loc[:34, ["p_nominal", "per_nominal"]] = [np.nan, None]                     # 5 rows ahead
    d.loc[:6, ["p_nominal_mas_2", "per_nominal_mas_2"]] = [np.nan, None]          # 7 already past
    b = VP.bloque_egreso(d)
    assert b["nominal"]["esperados"] == pytest.approx(5 * 0.3, abs=0.05)
    assert b["nominal_mas_2"]["esperados"] == pytest.approx(33 * 0.5, abs=0.05)
    assert b["por_cohorte"][0]["nominal"] is not None
    assert b["ya_pasado_nominal"] == 35 and b["ya_pasado_nominal_mas_2"] == 7


def test_egress_milestone_with_nobody_ahead_has_no_figure():
    d = poblacion(1, 12, 2025, 2, "nn_gru", "202520", "nominal_mas_2", 0.3, p2=0.5)
    d["trunc"] = False
    d[["p_nominal", "per_nominal"]] = [np.nan, None]
    b = VP.bloque_egreso(d)
    assert b["nominal"] is None and b["ya_pasado_nominal"] == 12 and b["nominal_mas_2"] is not None


def test_egress_milestone_with_ten_rows_ahead_and_none_past_is_published():
    d = poblacion(1, 40, 2025, 2, "nn_gru", "202520", "nominal_mas_2", 0.3, p2=0.5)
    d["trunc"] = False
    d.loc[:29, ["p_nominal", "per_nominal"]] = [np.nan, None]                     # exactly 10 ahead
    b = VP.bloque_egreso(d)
    assert b["nominal"]["esperados"] == pytest.approx(10 * 0.3, abs=0.05) and b["nominal_mas_2"] is not None


# ------------------------------------------------------------------------------------------------ current students
def _unidades():
    pop = pd.DataFrame({"episodio_id": [1, 2, 3, 4, 5, 6], "persona_key": list("abcdef"), "cod_programa": "P1",
                        "periodo_admision": ["202410", "202410", "202410", "202410", "202610", "202310"]})
    e = pd.DataFrame([
        (1, "202610", 1, "M"), (2, "202610", 1, "E"), (3, "202610", 1, "G"), (4, "202520", 1, "M"),        # 4: nothing in 202610
        (5, "202610", 1, "N"), (6, "202610", 1, "M"), (6, "202620", 2, "E")], columns=["episodio_id", "periodo", "orden_canonico", "cod_estado"])
    e["es_correccion_sistema"] = False
    return pop, e


def test_current_students_need_enrolment_or_attempts_in_the_last_closed_period_and_no_exit():
    pop, e = _unidades()
    it = pd.DataFrame([intento(4, "C0", 1, periodo="202610"), intento(2, "C0", 1, periodo="202610")])
    a = VP.seleccionar_actuales(pop, e, it, titulados=set())
    # 1 enrolled; 2 eliminated at the close; 3 graduated; 4 attempts in 202610 (counts); 5 new; 6 the 202620 elimination is not read
    assert sorted(a["episodio_id"]) == [1, 4, 5, 6]


def test_nothing_of_the_period_in_progress_makes_a_student_current_or_ended():
    pop, e = _unidades()
    solo_futuro = pd.DataFrame([intento(4, "C0", 1, periodo="202620")])
    a = VP.seleccionar_actuales(pop, e, solo_futuro, titulados=set())
    assert 4 not in set(a["episodio_id"]) and 6 in set(a["episodio_id"])         # 202620 attempts do not enrol; 202620 E does not end


def test_a_graduation_row_ends_the_student_and_a_reintegro_brings_them_back():
    pop, e = _unidades()
    e = pd.concat([e, pd.DataFrame([(2, "202610", 2, "I")], columns=["episodio_id", "periodo", "orden_canonico", "cod_estado"]).assign(
        es_correccion_sistema=False)], ignore_index=True)
    a = VP.seleccionar_actuales(pop, e, pd.DataFrame(columns=["episodio_id", "periodo"]), titulados={1})
    assert sorted(a["episodio_id"]) == [2, 5, 6]


# ------------------------------------------------------------------------------------------------ the document
def documento(**kw):
    intentos, actuales, _ = intentos_y_actuales()
    pob = {"continuidad": pd.concat([poblacion(5000, 40, 2026, 1, "cb_ben_pit", "202610", "202710", 0.9),
                                     poblacion(6000, 20, 2025, 2, "lr_acad", "202520", "202620", 0.7)], ignore_index=True),
           "eliminacion": eliminacion(),
           "egreso": poblacion(7000, 40, 2026, 0, "dt_lr_adm", "202610", "202820", 0.0, p2=0.05)}
    pob.update(kw)
    return VP.construir_documento(actuales, intentos, pob)


def test_document_has_the_published_shape():
    d = documento()
    assert d["version"] == 1 and d["corte"] == "202610" and "n_min" not in d
    assert set(d) >= {"filtros", "sin_proyeccion", "continuidad", "eliminacion", "egreso", "umbral"}
    assert d["filtros"][0] == VP.UCN and VP.UCN in d["continuidad"] and d["umbral"][VP.UCN]["n"] == 58
    assert d["eliminacion"][VP.UCN]["orientativo"] is True


def test_students_without_a_model_population_are_counted_apart():
    d = documento()
    assert d["sin_proyeccion"]["n"] == 58                    # none of the 58 current students (persons p1..p58) is in a population
    en_pob = documento(continuidad=poblacion(1, 20, 2026, 1, "cb_ben_pit", "202610", "202710", 0.9, persona=[f"p{i}" for i in range(1, 21)]))
    assert en_pob["sin_proyeccion"]["n"] == 38


def test_document_has_no_person_level_keys():
    txt = re.sub(r'"modelo_nombre": "[^"]*"', "", json.dumps(documento(), ensure_ascii=False))      # a model's NAME may say "persona-período"
    for prohibido in ("episodio", "persona", "docente", "nrc", "seccion", "sección"):
        assert prohibido not in txt.lower(), prohibido
    assert not re.search(r"[0-9a-f]{64}", txt)


def test_small_faculty_block_is_published_with_exact_counts():
    pob = eliminacion(n25=2, n24=1, facultad="Salud")
    d = documento(eliminacion=pd.concat([eliminacion(), pob.assign(episodio_id=pob["episodio_id"] + 90000)], ignore_index=True))
    s = d["eliminacion"]["Salud"]
    assert s["n"] == 3 and [c["n"] for c in s["por_cohorte"]] == [2, 1]
    assert s["esperados"] == pytest.approx(2 * 0.1 + 0.2, abs=0.05)
    assert d["eliminacion"][VP.UCN]["n"] == 58
    assert "otros" not in json.dumps(d)


def test_umbral_block_is_published_for_every_filter():
    d = documento()
    assert d["umbral"][VP.UCN]["n"] == 58 and "otros" not in d["umbral"][VP.UCN]


# ------------------------------------------------------------------------------------------------ gate and mart
def test_projection_aborts_when_a_model_does_not_reproduce(tmp_path, monkeypatch):
    def no_reproduce(conn, tarea, k, nombre, artefactos):
        raise MC.ReproduccionFallida(f"{tarea} k={k} {nombre}: max|dp|=0.5 exceeds the tolerance")

    intentos, actuales, _ = intentos_y_actuales()
    monkeypatch.setattr(VP, "_cuentas_actuales", lambda conn, art: (actuales, VP.contar_umbral(intentos, actuales), {}))
    monkeypatch.setattr(VP.FA, "cargar_programas", lambda conn: pd.DataFrame({"facultad_nombre": ["Ingeniería"]}, index=["P1"]))
    monkeypatch.setattr(VP.MC, "cargar_o_ajustar", no_reproduce)
    monkeypatch.setattr(VP, "_filas_de_poblacion", lambda conn, pob, personas=None: (pd.DataFrame({"episodio_id": [1]}), None))
    with pytest.raises(MC.ReproduccionFallida, match="exceeds the tolerance"):
        VP.construir(None, tmp_path)
    assert not (tmp_path / "vista_proyeccion.json").exists()


def test_mart_rows_are_one_per_block_and_filter_plus_meta():
    rows = MV.filas(documento())
    bloques = {b for b, _, _ in rows}
    assert bloques == {"meta", "continuidad", "eliminacion", "egreso", "umbral"}
    assert ("meta", VP.UCN) in {(b, f) for b, f, _ in rows}
    for _, _, contenido in rows:
        json.loads(contenido)
    meta = json.loads(next(c for b, f, c in rows if b == "meta"))
    assert meta["corte"] == "202610" and meta["sin_proyeccion"]["n"] == 58 and "n_min" not in meta


class ModeloFalso:
    def __init__(self):
        self.llamadas = 0

    def predecir(self, filas, sem=None):
        self.llamadas += 1
        return filas["x"].to_numpy() * 0.1


def _preparar_cache(monkeypatch, filas):
    modelo = ModeloFalso()
    verificaciones = []
    monkeypatch.setattr(VP, "_filas_de_poblacion", lambda conn, pob, personas=None: (filas["f"], None))
    monkeypatch.setattr(VP.MC, "cargar_o_ajustar", lambda conn, t, k, n, art: verificaciones.append(1) or modelo)
    return modelo, verificaciones


def test_a_changed_feature_value_with_the_same_ids_is_a_cache_miss(tmp_path, monkeypatch):
    f = {"f": pd.DataFrame({"episodio_id": [1, 2], "persona_key": ["a", "b"], "cod_programa": "P1", "periodo_admision": "202510", "x": [1.0, 2.0]})}
    modelo, _ = _preparar_cache(monkeypatch, f)
    pob = VP.POBLACIONES[1]                                        # t1 lr_acad
    VP._salida_modelo(None, pob, tmp_path)
    VP._salida_modelo(None, pob, tmp_path)
    assert modelo.llamadas == 1 and len(list((tmp_path / "proyeccion_cache").glob("*.npy"))) == 1
    f["f"] = f["f"].assign(x=[1.0, 2.5])                           # same ids, one feature changed
    out = VP._salida_modelo(None, pob, tmp_path)
    assert modelo.llamadas == 2 and out["salida"][1] == pytest.approx(0.25)


def test_a_cache_hit_still_runs_the_reproduction_check(tmp_path, monkeypatch):
    f = {"f": pd.DataFrame({"episodio_id": [1, 2], "persona_key": ["a", "b"], "cod_programa": "P1", "periodo_admision": "202510", "x": [1.0, 2.0]})}
    modelo, verificaciones = _preparar_cache(monkeypatch, f)
    pob = VP.POBLACIONES[1]
    VP._salida_modelo(None, pob, tmp_path)
    VP._salida_modelo(None, pob, tmp_path)                         # hit
    assert len(verificaciones) == 2 and modelo.llamadas == 1       # verified both times, predicted once

    def no_reproduce(conn, t, k, n, art):
        raise MC.ReproduccionFallida("max|dp|=0.5 exceeds the tolerance")

    monkeypatch.setattr(VP.MC, "cargar_o_ajustar", no_reproduce)
    with pytest.raises(MC.ReproduccionFallida):
        VP._salida_modelo(None, pob, tmp_path)                     # a hit does not bypass the gate
    assert not (tmp_path / "vista_proyeccion.json").exists()


def test_cache_key_covers_the_model_file_and_the_saved_predictions_file(tmp_path, monkeypatch):
    f = {"f": pd.DataFrame({"episodio_id": [1], "persona_key": ["a"], "cod_programa": "P1", "periodo_admision": "202510", "x": [1.0]})}
    modelo, _ = _preparar_cache(monkeypatch, f)
    pob = VP.POBLACIONES[1]
    VP._salida_modelo(None, pob, tmp_path)
    (tmp_path / "preds").mkdir()
    (tmp_path / "preds" / "t1_nuevas_k2.npz").write_bytes(b"saved predictions v2")        # the file it is verified against appeared / changed
    VP._salida_modelo(None, pob, tmp_path)
    assert modelo.llamadas == 2


# ------------------------------------------------------------------------------------------------ population selection
def test_population_is_selected_by_cohort_k_cut_and_current_at_that_cut_never_by_the_label(monkeypatch):
    snap = pd.DataFrame({
        "episodio_id": [1, 2, 3, 4, 5, 6], "persona_key": list("abcdef"), "k": 2, "cohorte_anio": [2025, 2025, 2025, 2025, 2024, 2025],
        "periodo_admision": ["202510"] * 4 + ["202410", "202520"], "causa": [0, 2, 1, 0, 0, 0],
        "resultado": ["censurado", "eliminacion", "egreso", "censurado", "censurado", "censurado"]})
    monkeypatch.setattr(VP.MC, "snapshot_t3", lambda conn: (snap, None))
    monkeypatch.setattr(VP.MC, "snapshot_t5", lambda conn: (snap, None))
    # cut 202520 (admission 202510): a, b, c, e current; b was eliminated in 202610 and c graduated in 202610 (so they are NOT current
    # at 202610) but they were at their cut and the model predicts exactly those events: they stay in. d was not current at the cut.
    # f (admission 202520) has its cut at 202610 and is current then. e belongs to another cohort.
    personas = {"202520": {"a", "b", "c", "e"}, "202610": {"a", "f"}}
    for pob in (VP.POBLACIONES[5], VP.POBLACIONES[2]):             # T3 k=2 and T5 k=2, cohort 2025
        filas, _ = VP._filas_de_poblacion(None, pob, personas=personas)
        assert sorted(filas["episodio_id"]) == [1, 2, 3, 6]


def test_current_at_an_earlier_cut_ignores_what_happened_afterwards():
    pop, e = _unidades()                                   # 6: M 202610, E 202620; 2: E 202610
    e = pd.concat([e, pd.DataFrame([(2, "202520", 0, "M")], columns=["episodio_id", "periodo", "orden_canonico", "cod_estado"]).assign(
        es_correccion_sistema=False)], ignore_index=True)
    a = VP.seleccionar_actuales(pop, e, pd.DataFrame(columns=["episodio_id", "periodo"]), titulados={}, corte="202520")
    assert sorted(a["episodio_id"]) == [2, 4]              # 2 was enrolled in 202520 (eliminated only in 202610); 4 too
    t = VP.seleccionar_actuales(pop, e, pd.DataFrame(columns=["episodio_id", "periodo"]), titulados={2: "202610", 4: "202520"}, corte="202520")
    assert sorted(t["episodio_id"]) == [2]                 # a degree of 202610 is after that cut; a degree of 202520 is not


def test_elimination_after_the_cut_still_counts_in_the_observed_so_far():
    d = eliminacion()
    d["obs"] = True                                        # everybody eliminated in 202610, still part of the cohort of the cut
    b = VP.bloque_eliminacion(d)
    assert b["n"] == 55 and b["observados_hasta_hoy"] == 55


def test_population_excludes_rows_whose_cut_is_not_closed(monkeypatch):
    snap = pd.DataFrame({"episodio_id": [1, 2], "persona_key": ["a", "b"], "k": 1, "cohorte_anio": 2026,
                         "periodo_corte": ["202610", "202620"], "estado_muestra": ["censurada", "censurada"]})
    monkeypatch.setattr(VP.MC, "snapshot_t1", lambda conn: snap)
    filas, _ = VP._filas_de_poblacion(None, VP.POBLACIONES[0], personas={"202610": {"a", "b"}, "202620": {"a", "b"}})
    assert list(filas["episodio_id"]) == [1]


def test_benefit_model_rows_without_load_history_are_counted_in_each_entry():
    d = pd.concat([poblacion(1, 40, 2026, 1, "cb_ben_pit", "202610", "202710", 0.9),
                   poblacion(1000, 30, 2025, 2, "lr_acad", "202520", "202620", 0.7)], ignore_index=True)
    d["sin_hist"] = np.where(d["modelo"] == "cb_ben_pit", np.arange(len(d)) < 12, np.nan)
    c = {e["modelo"]["modelo"]: e for e in VP.bloque_continuidad(d)["por_cohorte"]}
    assert c["cb_ben_pit"]["sin_historial_beneficios"] == 12 and "sin_historial_beneficios" not in c["lr_acad"]
    d["sin_hist"] = np.where(d["modelo"] == "cb_ben_pit", np.arange(len(d)) < 4, np.nan)
    assert VP.bloque_continuidad(d)["por_cohorte"][0]["sin_historial_beneficios"] == 4         # 1-9: exact


# ------------------------------------------------------------------------------------------------ program filter and model behind each block
PROGRAMAS = pd.DataFrame({"nombre_programa": ["Uno", "Dos"], "facultad_nombre": ["Ingeniería", "Salud"]},
                         index=pd.Index(["P1", "P2"], name="cod_programa"))


def _con_programa(d, cod_por_fila):
    """Splits a population in two programs of two faculties (P1 Ingeniería, P2 Salud) by the row position."""
    cod = np.where(np.arange(len(d)) % cod_por_fila == 0, "P2", "P1")
    return d.assign(cod_programa=cod, facultad=np.where(cod == "P2", "Salud", "Ingeniería"))


def _documento_programas():
    pob = {"continuidad": pd.concat([poblacion(5000, 40, 2026, 1, "cb_ben_pit", "202610", "202710", 0.9),
                                     poblacion(6000, 20, 2025, 2, "lr_acad", "202520", "202620", 0.7)], ignore_index=True),
           "eliminacion": eliminacion(),
           "egreso": poblacion(7000, 40, 2026, 0, "dt_lr_adm", "202610", "202820", 0.0, p2=0.05)}
    pob = {b: _con_programa(d, 20) for b, d in pob.items()}
    pob["continuidad"].loc[pob["continuidad"].index[-1], "cod_programa"] = "P2"
    intentos, actuales, _ = intentos_y_actuales()
    return VP.construir_documento(actuales, intentos, pob, programas=PROGRAMAS)


def test_every_block_is_published_per_program_in_the_projection():
    d = _documento_programas()
    for bloque in VP.BLOQUES:
        assert "P1" in d[bloque], bloque                                  # P1 is in every population and in the current students
    for bloque in ("continuidad", "eliminacion", "egreso"):
        assert "P2" in d[bloque] and d[bloque]["P2"]["n"] < d[bloque][VP.UCN]["n"]
    assert d["umbral"]["P1"]["n"] == 58 and "P2" not in d["umbral"]       # nobody of P2 is current: no block, not an empty one
    assert d["continuidad"]["P1"]["n"] + d["continuidad"]["P2"]["n"] == d["continuidad"][VP.UCN]["n"]
    assert d["filtros"] == [VP.UCN, "Ingeniería", "Salud"]               # the existing filters do not change


def test_program_filter_carries_faculty_and_name_in_the_projection():
    d = _documento_programas()
    assert d["programas"] == [{"codigo": "P1", "nombre": "Uno", "facultad": "Ingeniería"}, {"codigo": "P2", "nombre": "Dos", "facultad": "Salud"}]
    assert "programas" in MV.META and "modelos" in MV.META
    meta = json.loads(next(c for b, f, c in MV.filas(d) if b == "meta"))
    assert meta["programas"] == d["programas"]
    assert ("continuidad", "P2") in {(b, f) for b, f, _ in MV.filas(d)}


def test_projection_cohorts_each_declare_task_model_and_cut():
    d = _documento_programas()
    for filtro in (VP.UCN, "P1", "P2"):
        cont = {c["cohorte"]: c["modelo"] for c in d["continuidad"][filtro]["por_cohorte"]}
        assert (cont[2026]["tarea"], cont[2026]["tarea_nombre"], cont[2026]["k"], cont[2026]["modelo"]) == ("T1", "Continuidad", 1, "cb_ben_pit")
        assert (cont[2026]["corte"], cont[2026]["tipo"]) == ("1.er semestre", "proyeccion")
        assert (cont[2025]["tarea"], cont[2025]["k"], cont[2025]["modelo"], cont[2025]["corte"]) == ("T1", 2, "lr_acad", "2.º semestre")
    elim = {c["cohorte"]: c["modelo"] for c in d["eliminacion"][VP.UCN]["por_cohorte"]}
    assert [(elim[2025]["tarea"], elim[2025]["modelo"], elim[2025]["k"]), (elim[2024]["tarea"], elim[2024]["modelo"], elim[2024]["k"])] == \
        [("T5", "gru_adm", 2), ("T5", "gru_agg", 4)]
    egr = d["egreso"][VP.UCN]["por_cohorte"][0]["modelo"]
    assert (egr["tarea"], egr["modelo"], egr["k"], egr["corte"], egr["tipo"]) == ("T3", "dt_lr_adm", 0, "ingreso", "proyeccion")
    for m in (cont[2026], cont[2025], elim[2024], egr):
        assert m["modelo_nombre"] and m["tarea_nombre"] and m["particion"]


def test_projection_blocks_list_their_models_and_the_threshold_is_observed():
    d = _documento_programas()
    for bloque in ("continuidad", "eliminacion", "egreso"):
        b = d[bloque]["P1"]
        assert b["modelo"] is None and {m["modelo"] for m in b["modelos"]} == {c["modelo"]["modelo"] for c in b["por_cohorte"]}
    assert d["umbral"]["P1"]["modelo"] is None and "modelos" not in d["umbral"]["P1"]
    assert d["modelos"]["umbral"] is None and {m["modelo"] for m in d["modelos"]["continuidad"]} == {"cb_ben_pit", "lr_acad"}
