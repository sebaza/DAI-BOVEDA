"""Pure helpers of the Neural module: transfer balance, the «pocos casos» mark and field whitelists. Nothing here hides data."""
import pytest

from app.services.neural import rules


# --------------------------------------------------------------------------- #
# Program transfers (P61)
# --------------------------------------------------------------------------- #
def test_balance_serves_every_count_even_when_small():
    b = rules.balance_programa(ganados=4, ganados_eleccion=0, perdidos=3, perdidos_eleccion=0)
    assert b == {"ganados_total": 4, "perdidos_total": 3, "neto_total": 1,
                 "ganados_sin_eleccion": 4, "perdidos_sin_eleccion": 3, "neto_sin_eleccion": 1}
    b = rules.balance_programa(ganados=40, ganados_eleccion=0, perdidos=0, perdidos_eleccion=0)
    assert b["perdidos_total"] == 0 and b["neto_total"] == 40


def test_balance_without_specialty_election_subtracts_it():
    b = rules.balance_programa(ganados=300, ganados_eleccion=200, perdidos=30, perdidos_eleccion=0)
    assert (b["ganados_total"], b["ganados_sin_eleccion"], b["neto_total"], b["neto_sin_eleccion"]) == (300, 100, 270, 70)
    b = rules.balance_programa(ganados=105, ganados_eleccion=5, perdidos=60, perdidos_eleccion=0)
    assert b["ganados_sin_eleccion"] == 100 and b["neto_sin_eleccion"] == 40            # a small election count is not hidden


def test_transfer_types_are_declared_with_their_meaning():
    assert set(rules.TIPOS_TRASLADO) == {"eleccion_especialidad", "cambio_ciclo", "continuacion_estudios",
                                         "cambio_carrera", "traslado_sede", "traslado_otro"}
    assert rules.TIPOS_TRASLADO["eleccion_especialidad"]["cuenta_abandono"] is False
    assert rules.TIPOS_TRASLADO["cambio_carrera"]["cuenta_abandono"] is True


def test_the_suppression_helpers_are_gone():
    for retirado in ("conteo", "balance_oculto", "flujos_principales", "grupo_publicable", "metricas_modelo_publicables",
                     "confianza_t3", "agrupar_otros", "complementar_filtros", "complementar_listas", "total_sin_resto_chico",
                     "depurar_semestres", "depurar_umbral", "depurar_proyeccion_bloque", "N_MIN_DEFECTO", "N_MIN_METRICAS_GRUPO"):
        assert not hasattr(rules, retirado), retirado


# --------------------------------------------------------------------------- #
# «Pocos casos»: a mark, never a filter
# --------------------------------------------------------------------------- #
def test_pocos_casos_marks_groups_under_ten_people():
    assert rules.POCOS_CASOS == 10
    assert [rules.pocos_casos(n) for n in (0, 1, 9)] == [True, True, True]
    assert [rules.pocos_casos(n) for n in (10, 11, 4934)] == [False, False, False]
    assert rules.pocos_casos(None) is False                  # nothing known: no mark, no crash


# --------------------------------------------------------------------------- #
# Field whitelists: rows are rebuilt field by field, whatever else the document carries
# --------------------------------------------------------------------------- #
def test_senales_and_esperar_copy_only_known_fields():
    b = {"tareas": [{"tarea": "t1", "k": 1, "modelo": "m", "n_muestra": 500, "persona_key": "x",
                     "senales": [{"familia": "f", "etiqueta": "F", "peso_pct": 10.0, "caida_ap": 0.1, "extra": 1}]},
                    {"tarea": "t3", "k": 0, "modelo": "m", "n_muestra": 5, "senales": []}]}
    r = rules.campos_senales(b)
    assert [t["n_muestra"] for t in r["tareas"]] == [500, 5]                      # a small sample is served too
    assert "persona_key" not in r["tareas"][0] and "extra" not in r["tareas"][0]["senales"][0]
    assert rules.campos_senales({"tareas": []}) is None and rules.campos_senales(None) is None
    c = {"comparaciones": [{"tarea": "t1", "k_antes": 1, "k_despues": 2, "de_cada_10_antes": 5.0, "de_cada_10_despues": None, "otro": 1}],
         "nota_poblaciones": True}
    assert rules.campos_esperar(c) == {"comparaciones": [{"tarea": "t1", "k_antes": 1, "k_despues": 2, "de_cada_10_antes": 5.0,
                                                          "de_cada_10_despues": None}], "nota_poblaciones": True,
                                    "aplica_a_poblacion": False, "modelo": None, "modelos": None}
    assert rules.campos_esperar(None) is None
    m = {"tarea": "T1", "modelo": "cb_acad"}                                      # the model label goes through; the flag is always False
    r = rules.campos_senales({**b, "aplica_a_poblacion": True, "modelo": None, "modelos": [m]})
    assert r["aplica_a_poblacion"] is False and r["modelos"] == [m] and r["modelo"] is None
