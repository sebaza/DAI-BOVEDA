"""Per-task summary (T1-T6) for the "Modelos" view: pure transformation of the five result files, aggregates only."""
import pytest

from pipelines.marts import resumen_tareas as RT


def m(punto, lo, hi):
    return {"punto": punto, "lo": lo, "hi": hi}


def cal(modelo_riesgo=0.1, obs=0.1):
    return [{"decil": d, "n": 100, "riesgo_medio": modelo_riesgo, "tasa_observada": obs} for d in (1, 2)]


PROGRAMAS = {
    "8001": ("DERECHO", "Facultad de Ciencias Jurídicas"),
    "8002": ("PSICOLOGÍA", "Facultad de Humanidades"),
    "8003": ("MEDICINA", "Facultad de Medicina"),
}


def fila_t1(grupo, n, tasa, riesgo):
    return {"grupo": grupo, "n": n, "tasa_observada": tasa, "riesgo_medio": riesgo, "brecha_calibracion": riesgo - tasa,
            "ap": 0.3, "roc_auc": 0.8}


def t1(con_k2=False):
    test = {"baseline_tasa": {"ap": m(0.07, 0.06, 0.08)}, "cb_acad": {"ap": m(0.34, 0.28, 0.39), "roc_auc": m(0.85, 0.83, 0.87)},
            "gru_seq": {"ap": m(0.325, 0.27, 0.38)},
            "__delta__cb_acad": {"ap": m(0.27, 0.2, 0.3)}, "__delta_gru_vs_cb_acad": {"ap": m(-0.03, -0.05, -0.01)}}
    r = {"k": 1, "n": {"train": {"n": 12000, "eventos": 750, "tasa": 0.0625}, "valid": {"n": 4000, "eventos": 190, "tasa": 0.0475},
                       "test": {"n": 4934, "eventos": 280, "tasa": 0.0567}},
         "test": test, "calibracion_test": {"cb_acad": cal(), "baseline_tasa": cal()},
         "subgrupos_test": {"cb_acad": {"programa": [
             fila_t1("8001", 200, 0.10, 0.08),       # 20 events: listed
             fila_t1("8002", 150, 0.03, 0.05),       # 4.5 events: suppressed (fewer than 10 events)
             fila_t1("8003", 8, 0.5, 0.4)]}}}        # n < 10: suppressed
    if not con_k2:
        return {"resultados": {"k1": r}}
    r2 = {"k": 2, "n": r["n"], "test": {"baseline_tasa": {"ap": m(0.1, 0.09, 0.11)}, "lr_acad": {"ap": m(0.537, 0.5, 0.57)},
                                       "cb_acad": {"ap": m(0.552, 0.52, 0.58)}, "gru_seq": {"ap": m(0.526, 0.49, 0.56)}},
          "calibracion_test": {"lr_acad": cal(), "cb_acad": cal(), "baseline_tasa": cal()},
          "subgrupos_test": {"lr_acad": {"programa": [fila_t1("8001", 200, 0.10, 0.09)]},
                             "cb_acad": {"programa": [fila_t1("8001", 200, 0.10, 0.08), fila_t1("8002", 300, 0.2, 0.2)]}}}
    return {"resultados": {"k1": r, "k2": r2}}


def t2():
    test = {"baseline": {"ap": m(0.36, 0.35, 0.37)}, "cb_c": {"ap": m(0.54, 0.53, 0.55)},
            "cb_c_nuevas": {"ap": m(0.545, 0.535, 0.555)}, "nn_gnn": {"ap": m(0.52, 0.51, 0.53)},
            "nn_mlp": {"ap": m(0.52, 0.51, 0.53)}, "__delta__nn_gnn__nn_mlp": {"ap": m(0.0, -0.001, 0.001)}}

    def banda(o, p):
        return {"observada": m(o, o - 0.02, o + 0.02), "predicha": m(p, p - 0.02, p + 0.02), "base": m(0.2, 0.2, 0.2), "ap": 0.5}

    bandas = {b: banda(0.25, 0.22) for b in ("reprobado", "unanimidad", "distincion", "maxima_distincion")}
    resumen = {"grupos_total": 3, "grupos_listados": 2, "n_min": 100, "n_suprimir": 10,
               "mae_modelo": {b: m(0.04, 0.03, 0.05) for b in bandas}, "mae_base": {b: m(0.06, 0.05, 0.07) for b in bandas},
               "spearman": {b: m(0.9, 0.8, 0.95) for b in bandas}}
    ev = {"test": test, "calibracion_test": {"cb_c": cal(), "baseline": cal()},
          "bandas": {"etiquetas": {"reprobado": "Reprobado", "unanimidad": "Aprobado por Unanimidad",
                                   "distincion": "Aprobado con Distinción", "maxima_distincion": "Aprobado con Máxima Distinción"},
                     "grupos": {"test": {
                         "programa": {"filas": [{"grupo": "8001", "n": 500, "bandas": bandas, "nombre": "DERECHO",
                                                 "facultad": "Facultad de Ciencias Jurídicas"},
                                                {"grupo": "8002", "n": 7, "bandas": bandas, "nombre": "PSICOLOGÍA",
                                                 "facultad": "Facultad de Humanidades"}],
                                      "resumen": resumen},
                         "facultad": {"filas": [{"grupo": "Facultad de Ciencias Jurídicas", "n": 500, "bandas": bandas}],
                                      "resumen": resumen}}}}}
    split = {s: {"n": n, "reprobados": r, "tasa_reprobacion": r / n} for s, n, r in
             (("train", 1000, 160), ("valid", 400, 50), ("test", 500, 70), ("posterior", 200, 30))}
    return {"evaluacion": ev, "descriptivo": {"split": split}, "info": {}}


def t3():
    test = {"km_programa": {"c_12": m(0.70, 0.69, 0.71)}, "dt_cb_agg": {"c_12": m(0.82, 0.81, 0.83), "ibs": m(0.046, 0.044, 0.048)},
            "nn_gru": {"c_12": m(0.84, 0.83, 0.85), "ibs": m(0.042, 0.04, 0.044)},
            "__delta__nn_gru__dt_cb_agg": {"c_12": m(0.04, 0.03, 0.05)}}
    bloque = {"mejor_clasico_valid": "dt_cb_agg", "test": test, "n_split": {"train": 6000, "valid": 2000, "test": 4000},
              "calibracion_test": {"12": {"dt_cb_agg": cal(0.3, 0.33), "km_programa": cal(0.3, 0.33), "nn_gru": cal(0.3, 0.33)}},
              "subgrupos_test": {"nn_gru": {"programa_n150": [
                  {"grupo": "8001", "n": 300, "incidencia_observada": 0.40, "incidencia_predicha": 0.39,
                   "brecha_calibracion": -0.01, "auc": 0.82}]},
                                 "dt_cb_agg": {"programa_n150": [
                  {"grupo": "8001", "n": 300, "incidencia_observada": 0.40, "incidencia_predicha": 0.38,
                   "brecha_calibracion": -0.02, "auc": 0.8},
                  {"grupo": "8002", "n": 200, "incidencia_observada": 0.02, "incidencia_predicha": 0.05,
                   "brecha_calibracion": 0.03, "auc": 0.6}]}}}
    d = {"por_k_split": {"2": {s: {"n": n, "egreso": e, "salida": 10, "censura": 5} for s, n, e in
                               (("train", 6000, 2000), ("valid", 2000, 700), ("test", 4000, 1500))}}}
    return {"por_k": {"2": bloque}, "descriptivo": d}


def grupo_t45(grupo, n, ev, obs, riesgo, nombre=None):
    f = {"grupo": grupo, "n": n, "eventos": ev, "ap": 0.4, "roc_auc": 0.8, "tasa_observada": m(obs, obs - 0.01, obs + 0.01),
         "riesgo_medio": m(riesgo, riesgo - 0.01, riesgo + 0.01), "riesgo_medio_base": m(0.1, 0.1, 0.1)}
    if nombre:
        f["nombre"] = nombre
    return f


def objetivo(conservado, programas, facultades):
    tests = {"baseline_tasa": {"ap": m(0.03, 0.02, 0.04)}, conservado: {"ap": m(0.1, 0.07, 0.14), "roc_auc": m(0.73, 0.69, 0.77)},
             "gru_adm": {"ap": m(0.09, 0.06, 0.13)}, "gru_adm__vs__" + conservado: {"ap": m(-0.01, -0.03, 0.01)}}
    resumen = {"grupos_total": 3, "grupos_reportables": 1, "grupos_suprimidos": 2, "n_min": 100, "eventos_min": 10,
               "mae_modelo": m(0.07, 0.06, 0.08), "mae_base": m(0.01, 0.0, 0.02), "spearman_modelo": m(0.7, -0.6, 0.9)}
    return {"n": {"train": {"n": 1000, "eventos": 30, "tasa": 0.03}, "valid": {"n": 400, "eventos": 12, "tasa": 0.03},
                  "test": {"n": 500, "eventos": 15, "tasa": 0.03}},
            "seleccion": {"conservado": conservado}, "test": tests, "calibracion_test": {conservado: cal(0.10, 0.03)},
            "grupos": {"programa": {"filas": programas, "resumen": resumen}, "facultad": {"filas": facultades, "resumen": resumen}}}


def t45():
    prog = [grupo_t45("8001", 300, 20, 0.07, 0.15, "DERECHO"), grupo_t45("8002", 120, 5, 0.04, 0.1, "PSICOLOGÍA")]
    fac = [grupo_t45("Facultad de Ciencias Jurídicas", 300, 20, 0.07, 0.15)]
    t5 = objetivo("cb_agg", prog, fac)
    t5["sensibilidad_registro_e"] = {"evaluado": True, "n": 200, "eventos": 40, "tasa_observada": 0.2, "periodo_limite": "202410",
                                    "modelos": {"cb_agg": {"riesgo_medio": 0.1, "ap": m(0.64, 0.58, 0.69), "roc_auc": m(0.9, 0.89, 0.91)},
                                                "baseline_tasa": {"riesgo_medio": 0.12, "ap": m(0.17, 0.14, 0.19)}}}
    return {"por_k": {"2": {"targets": {"T4": objetivo("lr_agg", prog, fac), "T5": t5, "T5E": objetivo("cb_agg", prog, fac)}}}}


def t6():
    def inc(a, b):
        return {"2": m(a, a - 0.01, a + 0.01), "4": m(b, b - 0.01, b + 0.01)}

    mods = {"baseline_programa": {"ap": m(0.029, 0.02, 0.042)}, "cox_perfil": {"ap": m(0.046, 0.03, 0.077)},
            "cox_agg": {"ap": m(0.037, 0.026, 0.055)}}
    hor = {"test": {"2": {"n": 2100, "eventos": 46, "tasa": 0.0219, "conclusivo": True, "modelos": mods,
                          "pares": {"cox_perfil__vs__baseline_programa": {"ap": m(0.017, 0.005, 0.043)}}},
                    "4": {"n": 864, "eventos": 12, "tasa": 0.0139, "conclusivo": False, "modelos": mods, "pares": {}},
                    "8": {"n": 0, "eventos": 0, "tasa": float("nan"), "conclusivo": False, "modelos": {}}}}
    grupos = {"programa": {"filas": [{"grupo": "8001", "n": 583, "eventos": 11, "incidencia": inc(0.01, 0.015),
                                      "en_riesgo": {"2": 519, "4": 440}, "nombre": "DERECHO"},
                                     {"grupo": "8002", "n": 100, "eventos": 6, "incidencia": inc(0.01, 0.015),
                                      "en_riesgo": {"2": 90, "4": 80}, "nombre": "PSICOLOGÍA"}],
                           "resumen": {"grupos_total": 2, "grupos_reportables": 1}},
              "facultad": {"filas": [{"grupo": "Facultad de Ciencias", "n": 313, "eventos": 27, "incidencia": inc(0.08, 0.09),
                                      "en_riesgo": {"2": 252, "4": 176}}], "resumen": {"grupos_total": 1, "grupos_reportables": 1}}}
    por_h = {"2": {s: {"n": n, "eventos": e} for s, n, e in (("train", 2598, 23), ("valid", 1457, 28), ("test", 2100, 46))},
             "4": {s: {"n": n, "eventos": e} for s, n, e in (("train", 2598, 33), ("valid", 1457, 45), ("test", 864, 12))}}
    return {"descriptivo": {"grupos": grupos, "por_horizonte": por_h},
            "modelos": {"horizontes": hor, "seleccion": {"tau": 2, "conservado": "cox_perfil"},
                        "calibracion_test": {"baseline_programa": [{"n": 883, "riesgo_medio": 0.01, "tasa_observada": 0.03, "grupo": 1}],
                                             "cox_perfil": [{"n": 210, "riesgo_medio": 0.014, "tasa_observada": 0.057, "grupo": 1}]}},
            "incidencia_por_nivel": {"magister": {"eventos": 158, "incidencia": inc(0.013, 0.019)},
                                     "doctorado": {"eventos": 23, "incidencia": inc(0.0024, 0.0032)},
                                     "otro": {"eventos": 4, "incidencia": inc(0.001, 0.002)}},
            "taus": [2, 4, 8], "tau_principal": 2, "n_unidades": 7091}


@pytest.fixture(scope="module")
def resumen():
    return RT.construir(t1(), t2(), t3(), t45(), t6(), PROGRAMAS)


def filas(resumen, tabla, **cond):
    return [f for f in resumen[tabla] if all(f.get(k) == v for k, v in cond.items())]


def test_there_is_one_card_per_task_with_status_and_plain_question(resumen):
    tareas = {f["tarea"]: f for f in resumen["tarea"]}
    assert sorted(tareas) == ["t1", "t2", "t3", "t4", "t5", "t6"]
    assert tareas["t6"]["estado"] == "exploratorio" and tareas["t5"]["estado"] == "dato_en_revision"
    assert tareas["t1"]["estado"] == "completo" and tareas["t4"]["estado"] == "completo"
    for f in tareas.values():
        assert f["pregunta"].startswith("¿") and f["poblacion"] and f["veredicto_redes"] and f["evento"]


def test_t2_kept_model_is_cb_c_nuevas_per_d118(resumen):
    v = filas(resumen, "vista", tarea="t2", variante="base", corte_k=0)[0]
    assert v["conservado_modelo"] == "cb_c_nuevas"
    kept = filas(resumen, "metrica", tarea="t2", corte_k=0, conservado=True)
    assert kept and {f["modelo"] for f in kept} == {"cb_c_nuevas"}


def test_every_task_has_one_principal_view_and_the_kept_model_is_marked(resumen):
    for t in ("t1", "t2", "t3", "t4", "t5", "t6"):
        assert len(filas(resumen, "vista", tarea=t, principal=True)) == 1
    v = filas(resumen, "vista", tarea="t4", variante="base", corte_k=2)[0]
    assert v["conservado_modelo"] == "lr_agg" and v["referencia_modelo"] == "baseline_tasa"
    assert v["pronostico_agregado"] == "no_confiable"
    assert filas(resumen, "vista", tarea="t6")[0]["pronostico_agregado"] == "no_disponible"
    assert {(f["variante"]) for f in filas(resumen, "vista", tarea="t5")} == {"actual", "efectiva", "sin_dudosos"}
    kept = filas(resumen, "metrica", tarea="t4", corte_k=2, conservado=True)
    assert {f["modelo"] for f in kept} == {"lr_agg"}


def test_t5_has_three_evaluations_and_the_third_only_keeps_two_models(resumen):
    mods = {f["modelo"] for f in filas(resumen, "metrica", tarea="t5", variante="sin_dudosos", corte_k=2)}
    assert mods == {"cb_agg", "baseline_tasa"}
    ap = filas(resumen, "metrica", tarea="t5", variante="sin_dudosos", modelo="cb_agg", metrica="ap")[0]
    assert (ap["valor"], ap["ic_inf"], ap["ic_sup"]) == (0.64, 0.58, 0.69)


def test_partitions_carry_n_events_and_rate(resumen):
    p = {f["particion"]: f for f in filas(resumen, "particion", tarea="t1", corte_k=1)}
    assert p["test"]["n"] == 4934 and p["test"]["eventos"] == 280 and p["train"]["tasa"] == pytest.approx(0.0625)
    t2 = {f["particion"]: f for f in filas(resumen, "particion", tarea="t2")}
    assert t2["test"]["eventos"] == 70 and t2["test"]["tasa"] == pytest.approx(0.14)
    t6 = {f["particion"]: f for f in filas(resumen, "particion", tarea="t6", variante="h2")}
    assert t6["test"]["n"] == 2100 and t6["test"]["eventos"] == 46
    t3 = {f["particion"]: f for f in filas(resumen, "particion", tarea="t3", corte_k=2)}
    assert t3["test"]["eventos"] == 1500 and t3["test"]["tasa"] == pytest.approx(0.375)


def test_metrics_deltas_and_calibration_come_from_the_results(resumen):
    ap = filas(resumen, "metrica", tarea="t1", corte_k=1, modelo="cb_acad", metrica="ap")[0]
    assert (ap["valor"], ap["ic_inf"], ap["ic_sup"], ap["n_evaluacion"]) == (0.34, 0.28, 0.39, 4934)
    assert ap["conservado"] is True
    d = filas(resumen, "delta", tarea="t1", modelo_a="gru_seq", modelo_b="cb_acad", metrica="ap")[0]
    assert d["veredicto"] == "empeora"
    d4 = filas(resumen, "delta", tarea="t4", modelo_a="gru_adm", modelo_b="lr_agg", metrica="ap")[0]
    assert d4["veredicto"] == "sin_diferencia"
    d6 = filas(resumen, "delta", tarea="t6", variante="h2", modelo_a="cox_perfil", modelo_b="baseline_programa")[0]
    assert d6["veredicto"] == "mejora"
    assert len(filas(resumen, "calibracion", tarea="t3", corte_k=2, modelo="dt_cb_agg")) == 2
    assert filas(resumen, "calibracion", tarea="t6", variante="h2", modelo="cox_perfil")[0]["tasa_observada"] == pytest.approx(0.057)


def test_kept_model_follows_the_valid_selection_rule_d114():
    resumen = RT.construir(t1(con_k2=True), t2(), t3(), t45(), t6(), PROGRAMAS)
    # T1: k = 1 CatBoost, k = 2 logistic (GRU and CatBoost tie on valid, the simpler model stays)
    v1 = {(f["corte_k"]): f for f in filas(resumen, "vista", tarea="t1", variante="base")}
    assert v1[1]["conservado_modelo"] == "cb_acad" and v1[2]["conservado_modelo"] == "lr_acad"
    assert "D114" in v1[2]["nota"] and v1[1]["nota"] is None
    kept = filas(resumen, "metrica", tarea="t1", variante="base", corte_k=2, conservado=True)
    assert {f["modelo"] for f in kept} == {"lr_acad"}
    # groups come from the kept model
    g = filas(resumen, "grupo", tarea="t1", corte_k=2, nivel="programa")
    assert [x["grupo"] for x in g] == ["8001"] and g[0]["esperada"] == 0.09
    # T3: the GRU is kept at k = 2 (mejor_clasico_valid is the classical, not the kept model), groups from the GRU
    v3 = filas(resumen, "vista", tarea="t3", corte_k=2)[0]
    assert v3["conservado_modelo"] == "nn_gru" and "D114" in v3["nota"] and "vienen del mejor clásico" not in v3["nota"]
    assert {f["modelo"] for f in filas(resumen, "metrica", tarea="t3", corte_k=2, conservado=True)} == {"nn_gru"}
    g3 = filas(resumen, "grupo", tarea="t3", corte_k=2, nivel="programa")
    assert [x["grupo"] for x in g3] == ["8001"] and g3[0]["esperada"] == 0.39
    ficha = {f["tarea"]: f for f in resumen["tarea"]}["t3"]["veredicto_redes"]
    assert "GRU" in ficha and "Red GRU" in ficha and "ΔC(12)" in ficha


def test_t3_falls_back_to_the_classical_groups_when_the_kept_network_has_none():
    t3b = t3()
    del t3b["por_k"]["2"]["subgrupos_test"]["nn_gru"]
    out = RT.construir(t1(), t2(), t3b, t45(), t6(), PROGRAMAS)
    v = filas(out, "vista", tarea="t3", corte_k=2)[0]
    assert v["conservado_modelo"] == "nn_gru" and "vienen del mejor clásico" in v["nota"]
    assert [x["grupo"] for x in filas(out, "grupo", tarea="t3", corte_k=2, nivel="programa")] == ["8001", "8002"]   # D116: T3 lifts the events rule (8002 has n = 200)


def test_t6_keeps_the_two_horizons_that_have_a_test_set_and_flags_the_inconclusive_one(resumen):
    vistas = {f["variante"]: f for f in filas(resumen, "vista", tarea="t6")}
    assert set(vistas) == {"h2", "h4"} and vistas["h2"]["concluyente"] is True and vistas["h4"]["concluyente"] is False
    assert vistas["h2"]["conservado_modelo"] == "cox_perfil" and vistas["h2"]["principal"] is True


def test_names_come_from_the_dictionary_and_no_group_is_hidden(resumen):
    t1 = filas(resumen, "grupo", tarea="t1", corte_k=1, nivel="programa")
    assert [g["grupo"] for g in t1] == ["8001", "8002", "8003"]     # 8002 (4.5 events) and 8003 (n = 8) are listed too
    assert t1[0]["nombre"] == "DERECHO" and t1[0]["facultad"] == "Facultad de Ciencias Jurídicas"
    assert t1[0]["observada"] == 0.10 and t1[0]["esperada"] == 0.08
    assert [g["n"] for g in t1] == [200, 150, 8] and t1[2]["ap"] == 0.3         # model figures are not blanked by size
    t2 = filas(resumen, "grupo", tarea="t2", nivel="programa")
    assert {g["grupo"] for g in t2} == {"8001", "8002"} and len(t2) == 8        # one row per grade band; 8002 has n = 7
    assert {g["categoria"] for g in t2} == {"reprobado", "unanimidad", "distincion", "maxima_distincion"}
    assert [g["grupo"] for g in filas(resumen, "grupo", tarea="t3", corte_k=2, nivel="programa")] == ["8001"]
    fac = filas(resumen, "grupo", tarea="t2", nivel="facultad")
    assert {g["nombre"] for g in fac} == {"Facultad de Ciencias Jurídicas"}


def test_the_publication_rules_are_gone_from_the_module():
    for nombre in ("N_MIN", "N_MODELO", "_publicable"):
        assert not hasattr(RT, nombre), nombre


def test_calibration_keeps_small_deciles():
    t1b = t1()
    t1b["resultados"]["k1"]["calibracion_test"]["cb_acad"] = [
        {"decil": 1, "n": 3, "riesgo_medio": 0.1, "tasa_observada": 0.0}, {"decil": 2, "n": 9, "riesgo_medio": 0.2, "tasa_observada": 0.1}]
    out = RT.construir(t1b, t2(), t3(), t45(), t6(), PROGRAMAS)
    cal_k1 = filas(out, "calibracion", tarea="t1", variante="base", corte_k=1, modelo="cb_acad")
    assert [(c["decil"], c["n"]) for c in cal_k1] == [(1, 3), (2, 9)]


def test_t5_and_t6_groups(resumen):
    t5 = filas(resumen, "grupo", tarea="t5", variante="actual", corte_k=2, nivel="programa")
    assert {g["grupo"] for g in t5} == {"8001", "8002"} and t5[0]["esperada"] == 0.15 and t5[0]["observada"] == 0.07
    t6 = filas(resumen, "grupo", tarea="t6", variante="h2", nivel="programa")
    assert [g["grupo"] for g in t6] == ["8001", "8002"] and t6[0]["esperada"] is None and t6[0]["observada"] == 0.01
    assert filas(resumen, "grupo", tarea="t6", variante="h4", nivel="facultad")[0]["nombre"] == "Facultad de Ciencias"
    niveles = {g["grupo"] for g in filas(resumen, "grupo", tarea="t6", variante="h2", nivel="nivel_postgrado")}
    assert niveles == {"magister", "doctorado", "otro"}              # 'otro' has 4 events and is listed


def test_group_summaries_count_the_listed_groups_and_carry_no_suppression_keys(resumen):
    r = filas(resumen, "grupo_resumen", tarea="t5", variante="actual", corte_k=2, nivel="programa")[0]
    assert r["grupos_total"] == 3 and r["grupos_reportables"] == 2 and r["spearman"] == 0.7
    assert filas(resumen, "grupo_resumen", tarea="t2", nivel="programa", categoria="reprobado")[0]["mae_modelo"] == 0.04
    for f in resumen["grupo_resumen"]:
        assert not ({"grupos_suprimidos", "n_min", "eventos_min"} & set(f))


# ---- grupos_todos.json: every group, any size -------------------------------------------------------------------------------
def fila_gt(grupo, n, ev, tasa, esp, ap=0.4, auc=0.8):
    return {"grupo": grupo, "n": n, "eventos": ev, "tasa": tasa, "tasa_lo": None if tasa is None else tasa - 0.01,
            "tasa_hi": None if tasa is None else tasa + 0.01, "esperado": esp, "esperado_lo": esp - 0.01, "esperado_hi": esp + 0.01,
            "referencia": 0.1, "ap": ap, "ap_lo": None if ap is None else ap - 0.1, "ap_hi": None if ap is None else ap + 0.1,
            "auc": auc, "auc_lo": None if auc is None else auc - 0.1, "auc_hi": None if auc is None else auc + 0.1,
            "pocos_casos": n < 10}


def bloque_gt(modelo, programa, facultad):
    return {"modelo": modelo, "referencia": "ref", "n": 1000, "eventos": 100,
            "dimensiones": {"programa": programa, "facultad": facultad, "sexo": [fila_gt("F", 500, 50, 0.1, 0.1)]}}


def _prog_gt():
    return [fila_gt("8001", 200, 20, 0.10, 0.08), fila_gt("8002", 9, 1, 0.111, 0.10), fila_gt("8003", 1, 0, 0.0, 0.05, None, None)]


def _fac_gt():
    return [fila_gt("Facultad de Ciencias Jurídicas", 500, 50, 0.1, 0.09), fila_gt("Facultad pequeña", 5, 2, 0.4, 0.3)]


def _todos_los_bloques():
    def b(modelo, **extra):
        return {**bloque_gt(modelo, _prog_gt(), _fac_gt()), **extra}

    bandas = {f"banda_{x}": {"0": b("cb_bandas", banda=x)} for x in ("unanimidad", "distincion", "maxima_distincion")}
    return {
        "t1": {"base": {"1": b("cb_acad")}, "beneficios_corte": {"1": b("cb_ben_pit")},
               "beneficios": {"1": b("cb_acad"), "2": b("cb_ben")}, "extension_k4": {"4": b("cb_ben")}},
        "t2": {"base": {"0": b("cb_c_nuevas")}, **bandas},
        "t3": {"base": {"2": b("nn_gru")}},
        "t4": {"base": {"2": b("lr_agg")}},
        "t5": {"actual": {"2": b("cb_agg")}, "efectiva": {"2": b("cb_agg")}},
        "t6": {"h2": {"0": b("cox_perfil", horizonte=2)}, "h4": {"0": b("cox_perfil", horizonte=4)}}}


GT_JSON = {"tareas": _todos_los_bloques()}


def _gt_grupos(out, tarea, variante, k, nivel, **cond):
    return [g for g in out["grupo"] if g["tarea"] == tarea and g["variante"] == variante and g["corte_k"] == k and g["nivel"] == nivel
            and all(g.get(c) == v for c, v in cond.items())]


def _construir_gt(gt=GT_JSON, **kw):
    return RT.construir(t1(), t2(), t3(), t45(), t6(), PROGRAMAS, grupos_todos=gt, **kw)


def test_resumen_tareas_publishes_groups_of_any_size():
    out = _construir_gt()
    prog = {g["grupo"]: g for g in _gt_grupos(out, "t1", "base", 1, "programa")}
    assert set(prog) == {"8001", "8002", "8003"} and [prog[g]["n"] for g in ("8001", "8002", "8003")] == [200, 9, 1]
    assert prog["8002"]["ap"] == 0.4 and prog["8002"]["roc_auc"] == 0.8                  # model figures kept for n < 10
    assert prog["8003"]["ap"] is None and prog["8003"]["observada"] == 0.0 and prog["8003"]["eventos"] == 0
    assert prog["8001"]["obs_inf"] == pytest.approx(0.09) and prog["8001"]["esp_sup"] == pytest.approx(0.09)
    assert prog["8001"]["nombre"] == "DERECHO" and prog["8001"]["facultad"] == "Facultad de Ciencias Jurídicas"
    fac = {g["grupo"]: g for g in _gt_grupos(out, "t1", "base", 1, "facultad")}
    assert set(fac) == {"Facultad de Ciencias Jurídicas", "Facultad pequeña"} and fac["Facultad pequeña"]["n"] == 5
    assert fac["Facultad pequeña"]["ap"] == 0.4 and fac["Facultad pequeña"]["facultad"] is None
    r = filas(out, "grupo_resumen", tarea="t1", variante="base", corte_k=1, nivel="programa")[0]
    assert r["grupos_total"] == 3 and r["grupos_reportables"] == 3 and r["mae_modelo"] is not None
    assert [g["n"] for g in _gt_grupos(out, "t3", "base", 2, "programa")] == [200, 9, 1]
    assert {g["grupo"] for g in _gt_grupos(out, "t5", "actual", 2, "programa")} == {"8001", "8002", "8003"}


def test_group_rows_carry_the_intervals_the_small_case_mark_and_every_dimension():
    out = _construir_gt()
    prog = {g["grupo"]: g for g in _gt_grupos(out, "t1", "base", 1, "programa")}
    g = prog["8001"]
    assert (g["ap_lo"], g["ap_hi"], g["auc_lo"], g["auc_hi"]) == pytest.approx((0.3, 0.5, 0.7, 0.9))
    assert (g["tasa_lo"], g["tasa_hi"], g["esperado_lo"], g["esperado_hi"]) == pytest.approx((0.09, 0.11, 0.07, 0.09))
    assert [prog[x]["pocos_casos"] for x in ("8001", "8002", "8003")] == [False, True, True]
    assert prog["8003"]["ap_lo"] is None and prog["8003"]["auc_hi"] is None
    sexo = _gt_grupos(out, "t1", "base", 1, "sexo")
    assert [(f["grupo"], f["nombre"], f["facultad"], f["pocos_casos"]) for f in sexo] == [("F", "F", None, False)]
    assert {f["nivel"] for f in out["grupo"]} >= {"programa", "facultad", "sexo", "nivel_postgrado"}
    for f in out["grupo"]:
        assert isinstance(f["pocos_casos"], bool) and f["pocos_casos"] == (f["n"] < RT.POCOS_CASOS)


def test_t2_lists_every_group_of_all_four_grade_bands_from_grupos_todos():
    out = _construir_gt()
    otras = _gt_grupos(out, "t2", "base", 0, "programa")
    assert {g["categoria"] for g in otras} == {"reprobado", "unanimidad", "distincion", "maxima_distincion"}
    for banda in ("reprobado", "unanimidad", "distincion", "maxima_distincion"):
        assert sorted(g["n"] for g in otras if g["categoria"] == banda) == [1, 9, 200], banda   # no n >= 100 filter
        r = [x for x in out["grupo_resumen"] if x["tarea"] == "t2" and x["nivel"] == "programa" and x["categoria"] == banda][0]
        assert r["grupos_reportables"] == 3


def test_t1_benefit_ablations_and_t6_groups_come_from_grupos_todos():
    out = _construir_gt(t1_beneficios=t1_beneficios())
    for variante, k in (("beneficios", 1), ("beneficios", 2), ("extension_k4", 4)):
        assert sorted(g["n"] for g in _gt_grupos(out, "t1", variante, k, "programa")) == [1, 9, 200], (variante, k)
    for variante in ("h2", "h4"):
        prog = {g["grupo"]: g for g in _gt_grupos(out, "t6", variante, 0, "programa")}
        assert set(prog) == {"8001", "8002", "8003"} and prog["8002"]["esperada"] is not None and prog["8002"]["ap"] == 0.4
        assert len(_gt_grupos(out, "t6", variante, 0, "facultad")) == 2
        assert {g["grupo"] for g in _gt_grupos(out, "t6", variante, 0, "nivel_postgrado")} == {"magister", "doctorado", "otro"}


def test_the_official_cut_view_reads_its_groups_from_grupos_todos():
    out = _construir_gt(t1_beneficios=t1_beneficios(), t1_beneficios_cargas=t1_beneficios_cargas())
    assert sorted(g["n"] for g in _gt_grupos(out, "t1", "beneficios_corte", 1, "programa")) == [1, 9, 200]


def test_a_missing_or_foreign_block_is_an_error_not_a_fallback():
    sin = {"tareas": {**_todos_los_bloques(), "t2": {"base": _todos_los_bloques()["t2"]["base"]}}}
    with pytest.raises(ValueError, match=r"grupos_todos.*t2.*banda_unanimidad"):
        _construir_gt(sin)
    otro = {"tareas": {**_todos_los_bloques(), "t1": {"base": {"1": bloque_gt("lr_acad", _prog_gt(), _fac_gt())}}}}
    with pytest.raises(ValueError, match=r"grupos_todos.*lr_acad.*cb_acad"):
        _construir_gt(otro)
    sin_t6 = {"tareas": {k: v for k, v in _todos_los_bloques().items() if k != "t6"}}
    with pytest.raises(ValueError, match=r"grupos_todos.*t6"):
        _construir_gt(sin_t6)
    with pytest.raises(ValueError, match="grupos_todos"):
        _construir_gt({})


def test_notes_carry_the_data_caveats_and_pending_decisions(resumen):
    textos = " ".join(f["texto"] for f in resumen["nota"] if f["tarea"] == "t5")
    assert "P75" in textos and "202420" in textos
    assert any(f["tarea"] == "t2" and "P55" in f["texto"] and f["tipo"] == "pendiente" for f in resumen["nota"])
    assert any(f["tarea"] == "t6" and "P80" in f["texto"] for f in resumen["nota"])
    assert any(f["tarea"] in ("t1", "t2", "t3") and "P58" in f["texto"] for f in resumen["nota"])
    assert any(f["tarea"] == "t5" and f["tipo"] == "dato" for f in resumen["nota"])


def test_no_row_carries_a_person_key_or_an_individual_prediction(resumen):
    prohibidas = {"persona_key", "episodio_id", "rut", "prediccion", "y_pred"}
    for tabla, rows in resumen.items():
        for f in rows:
            assert not (prohibidas & set(f)), tabla


# ---- T1 with benefits (16-11-2026) -------------------------------------------------------------------------------------------
def t1_beneficios():
    def bloque(k, conservado, certificable):
        test = {"baseline_tasa": {"ap": m(0.07, 0.06, 0.08)}, "cb_acad": {"ap": m(0.34, 0.28, 0.39)},
                "lr_acad": {"ap": m(0.30, 0.25, 0.35)}, "cb_ben": {"ap": m(0.36, 0.30, 0.41)}, "lr_ben": {"ap": m(0.31, 0.26, 0.36)},
                "cb_ben__vs__cb_acad": {"ap": m(0.02, 0.005, 0.03)}, "cb_acad__vs__baseline_tasa": {"ap": m(0.27, 0.2, 0.3)}}
        if k == 4:
            test.update({"cb_ben_perd": {"ap": m(0.37, 0.3, 0.42)}, "cb_ben_perd__vs__cb_ben": {"ap": m(0.01, -0.01, 0.02)}})
        grupos = {"programa": {"filas": [{"grupo": "8001", "n": 200, "eventos": 20, "ap": 0.3, "roc_auc": 0.8,
                                          "tasa_observada": m(0.1, 0.07, 0.13), "riesgo_medio": m(0.09, 0.08, 0.1),
                                          "riesgo_medio_base": m(0.08, 0.07, 0.09)},
                                         {"grupo": "8002", "n": 150, "eventos": 4, "ap": 0.3, "roc_auc": 0.8,
                                          "tasa_observada": m(0.03, 0.0, 0.06), "riesgo_medio": m(0.05, 0.04, 0.06),
                                          "riesgo_medio_base": m(0.05, 0.04, 0.06)}],
                               "resumen": {"grupos_total": 3, "grupos_reportables": 2, "n_min": 100, "eventos_min": 10}},
                  "facultad": {"filas": [{"grupo": "Facultad de Ciencias Jurídicas", "n": 300, "eventos": 30, "ap": 0.31, "roc_auc": 0.8,
                                          "tasa_observada": m(0.1, 0.07, 0.13), "riesgo_medio": m(0.09, 0.08, 0.1),
                                          "riesgo_medio_base": m(0.08, 0.07, 0.09)}],
                               "resumen": {"grupos_total": 1, "grupos_reportables": 1, "n_min": 100, "eventos_min": 10}}}
        return {"k": k, "n": {"train": {"n": 9000, "eventos": 700, "tasa": 0.07}, "valid": {"n": 3000, "eventos": 300, "tasa": 0.1},
                              "test": {"n": 4000, "eventos": 250, "tasa": 0.0625}},
                "test": test, "calibracion_test": {conservado: cal(), "baseline_tasa": cal()}, "grupos": grupos,
                "seleccion": {"conservado": conservado, "beneficios_certificables": certificable}}

    return {"resultados": {"k1": bloque(1, "cb_acad", False), "k2": bloque(2, "cb_ben", True), "k4": bloque(4, "cb_ben", True)}}


@pytest.fixture(scope="module")
def resumen_ben():
    return RT.construir(t1(), t2(), t3(), t45(), t6(), PROGRAMAS, t1_beneficios=t1_beneficios())


def test_without_the_benefit_file_t1_is_exactly_the_official_view(resumen):
    assert {(f["variante"], f["corte_k"]) for f in filas(resumen, "vista", tarea="t1")} == {("base", 1)}


def test_benefit_views_add_k1_k2_and_the_k4_extension_without_a_second_principal(resumen_ben):
    vistas = {(f["variante"], f["corte_k"]): f for f in filas(resumen_ben, "vista", tarea="t1")}
    assert set(vistas) == {("base", 1), ("beneficios", 1), ("beneficios", 2), ("extension_k4", 4)}
    assert len(filas(resumen_ben, "vista", tarea="t1", principal=True)) == 1 and vistas[("base", 1)]["principal"] is True
    assert vistas[("beneficios", 2)]["conservado_modelo"] == "cb_ben" and vistas[("beneficios", 1)]["conservado_modelo"] == "cb_acad"
    assert "k = 4" in vistas[("extension_k4", 4)]["etiqueta"] and "beneficios" in vistas[("beneficios", 2)]["etiqueta"].lower()
    assert vistas[("beneficios", 1)]["nota"] and "no" in vistas[("beneficios", 1)]["nota"].lower()


def test_benefit_models_have_names_rungs_and_deltas(resumen_ben):
    kept = filas(resumen_ben, "metrica", tarea="t1", variante="beneficios", corte_k=2, conservado=True)
    assert {f["modelo"] for f in kept} == {"cb_ben"}
    assert all(f["escalon_nombre"] and f["modelo_nombre"] for f in kept)
    d = [f for f in filas(resumen_ben, "delta", tarea="t1", variante="beneficios", corte_k=2) if f["metrica"] == "ap"]
    assert any(f["modelo_a"] == "cb_ben" and f["modelo_b"] == "cb_acad" and f["veredicto"] == "mejora" for f in d)
    assert any(f["modelo_a"] == "cb_ben_perd" for f in filas(resumen_ben, "delta", tarea="t1", variante="extension_k4"))


def test_t1_now_has_a_faculty_view_and_lists_every_group(resumen_ben):
    fac = filas(resumen_ben, "grupo", tarea="t1", variante="beneficios", corte_k=2, nivel="facultad")
    assert [f["grupo"] for f in fac] == ["Facultad de Ciencias Jurídicas"] and fac[0]["facultad"] is None
    prog = filas(resumen_ben, "grupo", tarea="t1", variante="beneficios", corte_k=2, nivel="programa")
    assert [f["grupo"] for f in prog] == ["8001", "8002"] and prog[0]["nombre"] == "DERECHO"      # 8002 has 4 events


# ---- T1 official k = 1 model from the 2024 cohort (D113) -----------------------------------------------------------------------
def t1_beneficios_cargas():
    anio = lambda n, ev, ap_b: {"n": n, "eventos": ev, "baseline_tasa": {"ap": m(0.06, 0.05, 0.08)},
                                "lr_acad": {"ap": m(0.20, 0.15, 0.26)}, "cb_acad": {"ap": m(0.205, 0.16, 0.26)},
                                "cb_ben_final": {"ap": m(0.26, 0.2, 0.33)}, "cb_ben_pit": {"ap": m(ap_b, 0.2, 0.3)},
                                "cb_ben_pit__vs__cb_acad": {"ap": m(0.043, 0.011, 0.07), "roc_auc": m(0.014, 0.003, 0.027)},
                                "cb_acad__vs__baseline_tasa": {"ap": m(0.14, 0.1, 0.18)},
                                "cb_ben_final__vs__cb_acad": {"ap": m(0.05, 0.0, 0.1)}}
    grupos = {"programa": {"filas": [{"grupo": "8001", "n": 165, "eventos": 15, "ap": 0.38, "roc_auc": 0.88,
                                      "tasa_observada": m(0.09, 0.05, 0.13), "riesgo_medio": m(0.07, 0.05, 0.08),
                                      "riesgo_medio_base": m(0.07, 0.05, 0.08)},
                                     {"grupo": "8002", "n": 150, "eventos": 4, "ap": 0.3, "roc_auc": 0.8,
                                      "tasa_observada": m(0.03, 0.0, 0.06), "riesgo_medio": m(0.05, 0.04, 0.06),
                                      "riesgo_medio_base": m(0.05, 0.04, 0.06)}],
                           "resumen": {"grupos_total": 3, "grupos_reportables": 1, "n_min": 100, "eventos_min": 10}},
              "facultad": {"filas": [{"grupo": "Facultad de Ciencias Jurídicas", "n": 300, "eventos": 30, "ap": 0.31, "roc_auc": 0.8,
                                      "tasa_observada": m(0.1, 0.07, 0.13), "riesgo_medio": m(0.09, 0.08, 0.1),
                                      "riesgo_medio_base": m(0.08, 0.07, 0.09)}],
                           "resumen": {"grupos_total": 1, "grupos_reportables": 1, "n_min": 100, "eventos_min": 10}}}
    k1 = {"k": 1, "oficial": "cb_acad", "n": {"train": 12012, "valid": 4192, "evaluacion": 5397},
          "por_anio": {"2024": anio(2687, 111, 0.25), "2025": anio(2710, 112, 0.248)},
          "calibracion": {"cb_acad": cal(), "cb_ben_pit": cal(), "cb_ben_final": cal()}, "grupos": grupos}
    return {"resultados": {"k1": k1, "k2": {"k": 2}}}


@pytest.fixture(scope="module")
def resumen_corte():
    return RT.construir(t1(), t2(), t3(), t45(), t6(), PROGRAMAS, t1_beneficios=t1_beneficios(),
                        t1_beneficios_cargas=t1_beneficios_cargas())


def test_official_cut_variant_is_added_k1_only_and_not_principal(resumen_corte):
    v = filas(resumen_corte, "vista", tarea="t1", variante="beneficios_corte")
    assert [(f["corte_k"], f["principal"], f["conservado_modelo"]) for f in v] == [(1, False, "cb_ben_pit")]
    assert "2024" in v[0]["etiqueta"] and "D113" in v[0]["nota"]
    assert len(filas(resumen_corte, "vista", tarea="t1", principal=True)) == 1


def test_official_cut_variant_shows_only_academic_vs_adopted_with_valid_2024_and_test_2025(resumen_corte):
    mets = filas(resumen_corte, "metrica", tarea="t1", variante="beneficios_corte")
    assert {f["modelo"] for f in mets} == {"baseline_tasa", "cb_acad", "cb_ben_pit"}
    ap = filas(resumen_corte, "metrica", tarea="t1", variante="beneficios_corte", modelo="cb_ben_pit", metrica="ap")[0]
    assert ap["valor"] == pytest.approx(0.248) and ap["n_evaluacion"] == 2710 and ap["conservado"] is True
    part = {f["particion"]: f for f in filas(resumen_corte, "particion", tarea="t1", variante="beneficios_corte")}
    assert (part["valid"]["n"], part["valid"]["eventos"], part["test"]["n"], part["test"]["eventos"]) == (2687, 111, 2710, 112)
    d = filas(resumen_corte, "delta", tarea="t1", variante="beneficios_corte", modelo_a="cb_ben_pit", modelo_b="cb_acad", metrica="ap")
    assert d[0]["delta"] == pytest.approx(0.043) and d[0]["veredicto"] == "mejora"
    assert {(f["modelo_a"]) for f in filas(resumen_corte, "delta", tarea="t1", variante="beneficios_corte")} == {"cb_ben_pit", "cb_acad"}
    assert {f["modelo"] for f in filas(resumen_corte, "calibracion", tarea="t1", variante="beneficios_corte")} == {"cb_acad", "cb_ben_pit"}


def test_official_cut_variant_lists_every_group(resumen_corte):
    prog = filas(resumen_corte, "grupo", tarea="t1", variante="beneficios_corte", nivel="programa")
    assert [f["grupo"] for f in prog] == ["8001", "8002"] and prog[0]["nombre"] == "DERECHO"
    fac = filas(resumen_corte, "grupo", tarea="t1", variante="beneficios_corte", nivel="facultad")
    assert [f["grupo"] for f in fac] == ["Facultad de Ciencias Jurídicas"]


def test_old_benefit_k1_note_points_to_the_official_variant(resumen_corte):
    nota = filas(resumen_corte, "vista", tarea="t1", variante="beneficios", corte_k=1)[0]["nota"]
    assert "§14" in nota and "D113" in nota and "2024" in nota


def test_without_the_cargas_file_there_is_no_official_cut_variant(resumen_ben):
    assert not filas(resumen_ben, "vista", tarea="t1", variante="beneficios_corte")


def test_t5_verdict_says_the_gru_is_kept_per_d114(resumen):
    t5 = [f for f in resumen["tarea"] if f["tarea"] == "t5"][0]
    assert "se conserva la GRU" in t5["veredicto_redes"] and "modelo clásico en las tres" not in t5["veredicto_redes"]
