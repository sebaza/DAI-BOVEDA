"""Exporter of the model summary (aggregates only): pure transformation of the three result JSON files."""
import pytest

from pipelines.marts import resumen_modelos as RM


def m(punto, lo, hi):
    return {"punto": punto, "lo": lo, "hi": hi}


def t1():
    test = {
        "baseline_tasa": {"ap": m(0.07, 0.06, 0.08)},
        "cb_acad": {"ap": m(0.34, 0.28, 0.39), "roc_auc": m(0.85, 0.83, 0.87)},
        "gru_seq": {"ap": m(0.325, 0.27, 0.38)},
        "__delta__cb_acad": {"ap": m(0.27, 0.2, 0.3)},
        "__delta_gru_vs_cb_acad": {"ap": m(-0.015, -0.036, 0.007)},
    }
    info = {"gru_seq": {"semillas": [{"n_parametros": 16561}, {"n_parametros": 16561}], "hidden": 48, "static_dim": 32,
                        "d_secuencia": 13, "n_variables_estaticas": 20},
            "cb_acad": {"mejores_iteraciones": [107, 120, 122], "n_variables": 33,
                        "params": {"depth": "6", "learning_rate": "0.05", "iterations": "1500"}}}
    return {"resultados": {"k1": {"k": 1, "n": {"test": {"n": 4934, "eventos": 280}}, "test": test, "info": info}}}


def t2():
    test = {
        "baseline": {"ap": m(0.38, 0.37, 0.39)},
        "cb_b": {"ap": m(0.535, 0.528, 0.543)}, "cb_c": {"ap": m(0.538, 0.531, 0.545)},
        "nn_gnn": {"ap": m(0.527, 0.52, 0.535)}, "nn_mlp": {"ap": m(0.527, 0.52, 0.534)},
        "__delta__cb_c__cb_b": {"ap": m(0.003, 0.002, 0.004), "brier": m(-0.0009, -0.001, -0.0007)},
        "__delta__nn_gnn__nn_mlp": {"ap": m(0.0, -0.001, 0.002)},
        "cb_c_decay": {"ap": m(0.539, 0.532, 0.546)},
        "__delta__cb_c_decay__cb_c": {"ap": m(0.001, -0.001, 0.003)},
        "__n_boot": 200,
    }
    info = {"nn_gnn": {"semillas": [{"n_parametros": 108955}], "hidden": [256, 128]},
            "grafo": {"n_nodos": 9982, "n_aristas_prerrequisito": 9020}}
    return {"evaluacion": {"test": test}, "info": info, "descriptivo": {"split": {"test": {"n": 233001}}}}


def t3():
    test = {
        "cox_agg": {"c_12": m(0.81, 0.80, 0.82), "ibs": m(0.046, 0.044, 0.048)},
        "nn_gru": {"c_12": m(0.835, 0.825, 0.845), "ibs": m(0.0438, 0.042, 0.046)},
        "__delta__nn_gru__cox_agg": {"c_12": m(0.017, 0.011, 0.023), "ibs": m(-0.002, -0.004, -0.0001)},
        "__n": 4343,
    }
    info = {"2": {"nn_gru": {"semillas": [{"n_parametros": 32075}], "hidden": [128, 64], "gru_hidden": 48},
                  "dt_cb_agg": {"mejores_iteraciones": [639, 470, 418], "n_variables": 35}}}
    k2 = {"test": test, "n_split": {"test": 4343}}
    return {"por_k": {"2": k2}, "info": info}


@pytest.fixture()
def resumen():
    return RM.construir(t1(), t2(), t3())


def index(filas, *claves):
    return {tuple(f[c] for c in claves): f for f in filas}


def test_metrics_carry_value_interval_and_the_ladder_rung(resumen):
    f = index(resumen["metricas"], "tarea", "corte_k", "modelo", "metrica")
    ap = f[("t1", 1, "cb_acad", "ap")]
    assert (ap["valor"], ap["ic_inf"], ap["ic_sup"], ap["conjunto"], ap["n_evaluacion"]) == (0.34, 0.28, 0.39, "test", 4934)
    assert ap["escalon"] == 2 and ap["familia"] == "arboles" and "CatBoost" in ap["modelo_nombre"]
    assert f[("t1", 1, "gru_seq", "ap")]["escalon"] == 3 and f[("t1", 1, "gru_seq", "ap")]["familia"] == "red"
    assert f[("t2", 0, "nn_gnn", "ap")]["familia"] == "red_grafo"
    c12 = f[("t3", 2, "nn_gru", "c_12")]
    assert c12["valor"] == 0.835 and c12["n_evaluacion"] == 4343


def test_private_or_bookkeeping_keys_never_become_rows(resumen):
    modelos = {f["modelo"] for f in resumen["metricas"]}
    assert not any(x.startswith("__") for x in modelos)
    assert not any(f["metrica"].startswith("__") for f in resumen["metricas"])


def test_every_exported_value_is_numeric_or_text_and_nothing_individual(resumen):
    claves = set().union(*(f.keys() for f in resumen["metricas"] + resumen["deltas"] + resumen["info"]))
    assert not claves & {"persona_key", "episodio_id", "rut", "prediccion", "y_pred", "probabilidad"}


def test_deltas_are_normalised_to_a_minus_b_with_a_verdict(resumen):
    d = index(resumen["deltas"], "tarea", "corte_k", "modelo_a", "modelo_b", "metrica")
    assert d[("t1", 1, "gru_seq", "cb_acad", "ap")]["veredicto"] == "sin_diferencia"
    assert d[("t1", 1, "cb_acad", "baseline_tasa", "ap")]["veredicto"] == "mejora"       # __delta__X is versus the baseline
    assert d[("t2", 0, "cb_c", "cb_b", "ap")]["veredicto"] == "mejora"
    assert d[("t2", 0, "nn_gnn", "nn_mlp", "ap")]["veredicto"] == "sin_diferencia"
    assert d[("t3", 2, "nn_gru", "cox_agg", "c_12")]["veredicto"] == "mejora"


def test_for_error_metrics_a_negative_interval_is_an_improvement(resumen):
    d = index(resumen["deltas"], "tarea", "corte_k", "modelo_a", "modelo_b", "metrica")
    assert d[("t2", 0, "cb_c", "cb_b", "brier")]["veredicto"] == "mejora"
    assert d[("t3", 2, "nn_gru", "cox_agg", "ibs")]["veredicto"] == "mejora"
    assert RM.veredicto("ap", -0.02, -0.01) == "empeora"
    assert RM.veredicto("brier", 0.01, 0.02) == "empeora"
    assert RM.veredicto("ap", None, None) == "sin_diferencia"


def test_architecture_info_comes_from_the_logged_configuration(resumen):
    i = index(resumen["info"], "tarea", "corte_k", "modelo", "clave")
    assert i[("t1", 1, "gru_seq", "n_parametros")]["valor_num"] == 16561
    assert i[("t1", 1, "gru_seq", "hidden")]["valor_num"] == 48
    assert i[("t2", 0, "nn_gnn", "hidden")]["valor_texto"] == "256-128"
    assert i[("t3", 2, "nn_gru", "gru_hidden")]["valor_num"] == 48
    assert i[("t3", 2, "dt_cb_agg", "iteraciones")]["valor_num"] == 470            # median of the seeds
    assert i[("t1", 1, "cb_acad", "profundidad")]["valor_num"] == 6
    assert i[("t2", 0, "grafo", "n_nodos")]["valor_num"] == 9982


def test_headlines_state_the_verdict_with_the_interval_in_spanish(resumen):
    t = {x["clave"]: x for x in resumen["titulares"]}
    assert "t1_gru_vs_arboles_k1" in t and "t2_prerrequisitos" in t and "t2_grafo" in t and "t3_gru_vs_cox_k2" in t
    assert "no se distingue" in t["t1_gru_vs_arboles_k1"]["texto"] and "-0,015" in t["t1_gru_vs_arboles_k1"]["texto"]
    assert "0,003 [0,002; 0,004]" in t["t2_prerrequisitos"]["texto"]
    assert "supera" in t["t3_gru_vs_cox_k2"]["texto"]
    ordenes = [(x["tarea"], x["orden"]) for x in resumen["titulares"]]
    assert len(set(ordenes)) == len(ordenes)


def test_missing_sections_are_skipped_not_fatal():
    r = RM.construir({"resultados": {}}, {"evaluacion": {"test": {}}}, {"por_k": {}})
    assert r["metricas"] == [] and r["deltas"] == [] and r["titulares"] == []


def test_the_architecture_constants_are_read_from_the_model_code():
    pytest.importorskip("torch")
    filas = RM.arquitectura_desde_codigo()
    i = index(filas, "modelo", "clave")
    assert i[("nn_gru", "gru_hidden")]["valor_num"] == 48                    # models/t3_redes.GRU_HIDDEN
    assert i[("nn_gru", "capas")]["valor_texto"] == "128-64"
    assert i[("gru_t1", "hidden")]["valor_num"] == 48                        # models/gru.HIDDEN
    assert i[("nn_gnn", "sage_d_hid")]["valor_num"] == 64
    assert i[("nn_gnn", "sage_d_out")]["valor_num"] == 32
    assert i[("nn_gnn", "capas_sage")]["valor_num"] == 2
    assert i[("catboost", "profundidad")]["valor_num"] == 6


def test_the_p55_recent_statistics_ablation_is_exported_with_its_verdict(resumen):
    f = index(resumen["metricas"], "tarea", "corte_k", "modelo", "metrica")
    assert f[("t2", 0, "cb_c_decay", "ap")]["escalon"] == 5
    d = index(resumen["deltas"], "tarea", "corte_k", "modelo_a", "modelo_b", "metrica")
    assert d[("t2", 0, "cb_c_decay", "cb_c", "ap")]["veredicto"] == "sin_diferencia"
    t = {x["clave"]: x for x in resumen["titulares"]}
    assert "no se distingue" in t["t2_deriva_decay"]["texto"]
