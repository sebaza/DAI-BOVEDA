"""`scripts/verificar_paridad_percepcion.py`: la comparación de JSON es la parte con lógica.

Solo se prueba `diferencias` (pura): ignora el orden de las claves, compara números con
tolerancia y reporta RUTAS, nunca valores (las respuestas pueden traer texto de comentarios).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / "scripts" / "verificar_paridad_percepcion.py"
_spec = importlib.util.spec_from_file_location("verificar_paridad_percepcion", RUTA)
paridad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(paridad)


def test_iguales_aunque_cambie_el_orden_de_las_claves():
    assert paridad.diferencias({"a": 1, "b": [1, 2]}, {"b": [1, 2], "a": 1}) == []


def test_numeros_con_tolerancia_pero_no_mas():
    assert paridad.diferencias({"x": 0.1 + 0.2}, {"x": 0.3}) == []
    assert paridad.diferencias({"x": 1.0}, {"x": 1.001}) == ["$.x"]


def test_entero_y_flotante_equivalentes_se_igualan():
    assert paridad.diferencias({"x": 3}, {"x": 3.0}) == []


def test_bool_no_es_numero():
    assert paridad.diferencias({"x": True}, {"x": 1}) == ["$.x"]


def test_reporta_rutas_de_claves_ausentes_y_listas_de_distinto_largo():
    d = paridad.diferencias({"a": {"b": 1}, "l": [1, 2, 3]}, {"a": {}, "l": [1, 2]})
    assert "$.a.b" in d and "$.l" in d


def test_las_rutas_nunca_incluyen_valores():
    d = paridad.diferencias({"texto": "secreto-uno"}, {"texto": "secreto-dos"})
    assert d == ["$.texto"]
    assert "secreto" not in " ".join(d)


def test_diferencia_dentro_de_una_lista_indica_el_indice():
    assert paridad.diferencias({"l": [{"n": 1}, {"n": 2}]}, {"l": [{"n": 1}, {"n": 9}]}) == ["$.l[1].n"]
