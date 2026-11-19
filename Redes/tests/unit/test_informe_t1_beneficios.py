"""Formatting of the benefits section of docs/08 (synthetic aggregates, no database)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import informe_t1_beneficios as IB   # noqa: E402


def m(p, lo=None, hi=None):
    return {"punto": p, "lo": p - 0.02 if lo is None else lo, "hi": p + 0.02 if hi is None else hi}


def bloque_metricas(ap):
    return {k: m(ap if k == "ap" else 0.1) for k in ("ap", "roc_auc", "brier", "ece", "recall_10", "precision_10")}


def resultado():
    modelos = ["baseline_tasa", "lr_acad", "lr_ben", "cb_acad", "cb_ben"]
    split = {n: bloque_metricas(0.3 + 0.01 * i) for i, n in enumerate(modelos)}
    split["cb_ben__vs__cb_acad"] = {k: m(0.012, 0.001, 0.02) for k in ("ap", "roc_auc", "brier")}
    split["lr_ben__vs__lr_acad"] = {k: m(-0.004, -0.02, 0.01) for k in ("ap", "roc_auc", "brier")}
    return {"k": 2, "n": {s: {"n": 1000, "eventos": 100, "tasa": 0.1, "personas": 990} for s in ("train", "valid", "test")},
            "valid": split, "test": split,
            "seleccion": {"elegibles": ["lr_acad", "cb_acad", "cb_ben"], "conservado": "cb_ben", "beneficios_certificables": True,
                          "ap_valid": {"cb_ben": 0.41}},
            "grupos": {"programa": {"filas": [{"grupo": "8616", "nombre": "Ingeniería X", "n": 150, "eventos": 20, "ap": 0.4,
                                               "tasa_observada": m(0.13), "riesgo_medio": m(0.12), "brecha": m(-0.01)}],
                                    "resumen": {"grupos_reportables": 1, "grupos_total": 3, "n_min": 100, "eventos_min": 10,
                                                "mae_modelo": m(0.02), "mae_base": m(0.03), "spearman_modelo": m(0.7)}},
                       "facultad": {"filas": [], "resumen": {"grupos_reportables": 0, "grupos_total": 1, "n_min": 100, "eventos_min": 10}}},
            "importancia": {"cb_ben": {"semillas": 3, "n_muestra_shap": 4000, "suma_pct_beneficios": 5.0,
                                       "top": [{"variable": "tasa_ult_semestre", "importancia_pct": 20.0, "shap_medio_abs": 0.4, "rango": 1},
                                               {"variable": "tiene_gratuidad", "importancia_pct": 4.0, "shap_medio_abs": 0.1, "rango": 2}],
                                       "beneficios": [{"variable": "tiene_gratuidad", "importancia_pct": 4.0, "shap_medio_abs": 0.1, "rango": 2},
                                                      {"variable": "n_beneficios", "importancia_pct": 1.0, "shap_medio_abs": 0.01, "rango": 9}]}}}


def test_spanish_decimal_comma_and_signs():
    assert IB.punto(0.1234) == "0,123" and IB.punto(0.012, 3, True) == "+0,012" and IB.pct(0.1234) == "12,3 %"
    assert IB.con_ic(m(0.5, 0.4, 0.6)) == "0,500 [0,400; 0,600]"


def test_the_ablation_tables_list_the_models_and_the_paired_differences():
    r = resultado()
    assert "CatBoost, + beneficios" in IB.tabla_modelos(r, "test")
    d = IB.tabla_deltas(r, "valid")
    assert "CatBoost, + beneficios − CatBoost, ingreso + agregados" in d and "+0,012 [+0,001; +0,020]" in d


def test_before_after_table_has_both_families_and_both_partitions():
    t = IB.tabla_antes_despues(resultado(), None)
    assert t.count("| CatBoost |") == 2 and t.count("| Logística |") == 2


def test_importance_marks_benefit_variables_and_lists_those_outside_the_top():
    t = IB.tabla_importancia(resultado(), "cb_ben")
    assert "`tiene_gratuidad` (beneficio)" in t and "`n_beneficios`" in t and "Suma de la importancia" in t


def test_group_tables_use_names_and_state_the_suppression_rule():
    t = IB.tabla_grupos(resultado(), "programa")
    assert "8616 Ingeniería X" in t and "1 de 3 grupos" in t and "n ≥ 100" in t


def test_values_resolve_paths_of_the_json():
    ben = {"resultados": {"k2": resultado()}}
    assert IB.valor(ben, "k2.test.cb_ben.ap", False) == "0,340"
    assert IB.valor(ben, "k2.valid.cb_ben__vs__cb_acad.ap", True) == "+0,012 [+0,001; +0,020]"


def test_values_resolve_the_sensitivity_blocks():
    ben = {"resultados": {"k1": resultado()}, "sensibilidad": {"sin_salidas_en_el_anio": {"k1": resultado()}, "desde_2017": {"k1": resultado()}}}
    assert IB.valor(ben, "sin_salidas.k1.test.cb_ben__vs__cb_acad.ap", True) == "+0,012 [+0,001; +0,020]"
    assert IB.valor(ben, "desde_2017.k1.test.cb_ben.ap", False) == "0,340"
