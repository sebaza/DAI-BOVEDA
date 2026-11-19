"""Report blocks of the T3 benefits section: formatting, decimal comma and the splice into the document."""
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("informe_t3_beneficios", RAIZ / "tools" / "informe_t3_beneficios.py")
IB = importlib.util.module_from_spec(spec)
sys.modules["informe_t3_beneficios"] = IB
spec.loader.exec_module(IB)


def punto(p, lo, hi):
    return {"punto": p, "lo": lo, "hi": hi}


def res_min():
    base = {"c_12": punto(0.85, 0.84, 0.86), "ibs": punto(0.05, 0.049, 0.051)}
    ben = {"c_12": punto(0.852, 0.84, 0.86), "ibs": punto(0.0499, 0.049, 0.051)}
    delta = {"c_12": punto(0.002, -0.001, 0.005), "ibs": punto(-0.0001, -0.0003, 0.0001)}
    ev = {"gru_acad": base, "gru_previo_todo": ben, "__delta__gru_previo_todo__gru_acad": delta}
    return {"ks": [4], "reglas": ["previo"], "hash_beneficios": "h", "hash_snapshot_ext": "e", "segundos_totales": 60.0,
            "por_k": {"4": {"k": 4, "n": {"train": 100, "valid": 50, "test": 70}, "reglas": ["previo"], "no_aplicable": [],
                            "cobertura": {"previo": {"train": 0.3, "valid": 1.0, "test": 1.0}}, "familias": ["gru"], "bloques": ["todo"],
                            "valid": ev, "test": ev, "decisiones": {"gru_previo_todo__vs__gru_acad": {"adopta": False}},
                            "incidencia_media_test": {"12": {"n": 70, "observada": 0.4, "gru_acad": 0.41, "gru_previo_todo": 0.42}},
                            "grupos": {"previo": {"programa": {"filas": [], "resumen": {"grupos": 3, "visibles": 0, "bajo_umbral": 2,
                                                                                        "suprimidos_n_menor_10": 1}}}}}}}


def test_formatting_uses_the_decimal_comma_and_intervals():
    assert IB.ic(punto(0.0123, -0.001, 0.02), 3, True) == "+0,012 [-0,001; +0,020]"
    assert IB.pct(0.1234) == "12,3 %" and IB.pp(-0.021) == "-2,1 pp"


def test_tables_render_and_never_list_suppressed_groups():
    r = res_min()
    assert "0,850 [0,840; 0,860]" in IB.tabla_ablacion(r, "4", "previo")
    assert "no" in IB.tabla_deltas(r, "4", "previo").splitlines()[-1]
    assert "suprimidos: 1." in IB.tabla_grupos(r, "4", "previo", "programa")
    assert "adopta" in IB.tabla_decision(r)


def test_not_applicable_rules_are_marked():
    r = res_min()
    r["por_k"]["4"]["no_aplicable"] = ["previo"]
    assert "No aplicable" in IB.tabla_ablacion(r, "4", "previo")


def test_marker_substitution():
    datos = {"res": res_min(), "diag": {"por_corte": {}}, "oficial": None}
    assert IB.valor("bv:4.test.gru_acad.c_12", datos) == "0,850 [0,840; 0,860]"
    assert IB.valor("bd:4.valid.gru_previo_todo.gru_acad.c_12", datos) == "+0,002 [-0,001; +0,005]"
    assert IB.valor("bmeta:minutos", datos) == "1"


def test_splice_replaces_the_section_and_keeps_the_rest():
    doc = "# T\n\n## 10. Reproducibilidad\n\ntexto\n"
    sec = IB.MARCA_SECCION + "\n\ncontenido\n"
    uno = IB.insertar_en_documento(doc, sec)
    assert uno.count(IB.MARCA_SECCION) == 1 and uno.startswith(doc.rstrip())
    dos = IB.insertar_en_documento(uno, IB.MARCA_SECCION + "\n\notro\n")
    assert dos.count(IB.MARCA_SECCION) == 1 and "otro" in dos and "contenido" not in dos and "## 10. Reproducibilidad" in dos
