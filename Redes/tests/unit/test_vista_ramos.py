"""View "Lo que pasó": failed courses, failures versus expected, bottlenecks and curriculum semester."""
import json

import numpy as np
import pandas as pd
import pytest

from evaluation import vista_ramos as VR


def _a():
    return pd.DataFrame({
        "codigo": ["A1", "B1", "C1", "D1", "E1"], "nombre": ["Alfa", "Beta", "Gama", "Delta", "Eps"], "depto": ["DM"] * 5,
        "semestre": [1, 2, 3, 3, 14],
        "intentos": [200, 300, 9, 100, 500], "reprobados": [100, 30, 9, 8, 50]})


def test_reprobados_lists_every_course_with_at_least_one_attempt():
    b = VR.bloque_reprobados(_a())
    assert [r["codigo"] for r in b["por_tasa"]] == ["C1", "A1", "E1", "B1", "D1"]       # C1: 9 attempts, 9 failures (rate 1.0); tie 0.1: more failures first
    assert [r["codigo"] for r in b["por_volumen"]][0] == "A1"
    assert (b["desde"], b["hasta"]) == ("202110", "202520") and b["por_tasa"][0]["tasa"] == pytest.approx(1.0)
    assert len(VR.bloque_reprobados(_a(), top=2)["por_tasa"]) == 2


def test_rate_ranking_orders_by_wilson_lower_bound():
    a = pd.DataFrame({"codigo": ["U", "G", "M"], "nombre": ["uno", "grande", "medio"], "depto": "d",
                      "intentos": [1, 100, 3], "reprobados": [1, 60, 3]})
    b = VR.bloque_reprobados(a)
    assert [r["codigo"] for r in b["por_tasa"]] == ["G", "M", "U"]          # 1/1 ranks last despite its 100 %
    g = b["por_tasa"][0]
    assert g["tasa"] == pytest.approx(0.6) and g["intentos"] == 100 and g["reprobados"] == 60 and g["lo"] < 0.6 < g["hi"]
    assert 0 <= b["por_tasa"][2]["lo"] < b["por_tasa"][2]["hi"] <= 1
    assert [r["codigo"] for r in b["por_volumen"]] == ["G", "M", "U"]


def test_reprobados_keeps_a_course_with_few_passes_or_few_failures():
    a = pd.DataFrame({"codigo": ["X", "Y"], "nombre": ["x", "y"], "depto": ["d", "d"], "intentos": [105, 3], "reprobados": [100, 0]})
    b = VR.bloque_reprobados(a)
    assert [r["codigo"] for r in b["por_tasa"]] == ["X", "Y"] and b["por_tasa"][1]["intentos"] == 3
    assert VR.bloque_reprobados(a.iloc[0:0]) is None


def _esperado(seed=1, n=40):
    rng = np.random.default_rng(seed)
    p = rng.uniform(0.1, 0.4, size=n)
    return pd.DataFrame({
        "ventana": ["prueba"] * (n // 2) + ["posterior"] * (n - n // 2), "cod_programa": "8213",
        "codigo": [f"C{i}" for i in range(n)], "nombre": [f"Curso {i}" for i in range(n)], "depto": ["DM", "DQ"] * (n // 2),
        "depto_desc": ["Matemática", "Química"] * (n // 2), "intentos": 200, "observados": rng.binomial(200, p),
        "esperados": 200 * p, "varianza": 200 * p * (1 - p)})


def test_esperado_interval_brackets_the_difference_and_has_no_section_keys():
    b = VR.bloque_esperado(_esperado())
    assert set(b["ventanas"]) == {"prueba", "posterior"}
    assert b["ventanas"]["prueba"]["desde"] == "202310" and b["ventanas"]["posterior"]["hasta"] == "202520"
    filas = b["ventanas"]["prueba"]["ramos"]
    assert 0 < len(filas) <= 10
    assert [r["diferencia"] for r in filas] == sorted((r["diferencia"] for r in filas), reverse=True)
    for r in filas + b["ventanas"]["prueba"]["deptos"]:
        assert r["lo"] <= r["diferencia"] <= r["hi"] and r["intentos"] >= 10
    txt = json.dumps(b).lower()
    assert not any(k in txt for k in ("nrc", "docente", "seccion", "sección"))


def test_esperado_keeps_courses_with_few_attempts():
    a = _esperado()
    a.loc[a.index[0], ["intentos", "observados", "esperados", "varianza"]] = [3, 3, 0.0, 0.0]        # a course with 3 attempts
    r = next(x for x in VR.bloque_esperado(a, top=100)["ventanas"]["prueba"]["ramos"] if x["codigo"] == "C0")
    assert r["intentos"] == 3


def test_cuellos_counts_descendants_once():
    # A -> B -> C and A -> D (catalog 1); the same B -> C and A -> B appear again in catalog 2
    prerreq = pd.DataFrame({"cod_programa": ["p"] * 3 + ["q"] * 2, "catalogo": ["1"] * 3 + ["2"] * 2,
                            "codigo_requisito": ["A", "B", "A", "A", "B"], "codigo_asignatura": ["B", "C", "D", "B", "C"]})
    assert VR.dependientes(prerreq) == {"A": 3, "B": 1}
    a = pd.DataFrame({"codigo": ["A", "B", "C"], "nombre": ["a", "b", "c"], "depto": "d", "intentos": [100, 100, 100],
                      "reprobados": [20, 50, 60]})
    b = VR.bloque_cuellos(a, prerreq)
    assert [(r["codigo"], r["dependientes"], r["impacto"]) for r in b["filas"]] == [("A", 3, 60), ("B", 1, 50)]


def test_semestre_malla_publishes_every_semester_with_attempts_and_exact_counts():
    b = VR.bloque_semestre_malla(_a())
    assert [f["semestre"] for f in b["filas"]] == [1, 2, 3]       # 14 is out of range
    assert b["filas"][2]["intentos"] == 109 and b["filas"][2]["reprobados"] == 17
    a = pd.DataFrame({"semestre": [1, 2], "intentos": [5, 0], "reprobados": [4, 0]})
    f = VR.bloque_semestre_malla(a)["filas"]
    assert f[0]["reprobados"] == 4 and f[0]["tasa"] == pytest.approx(0.8)


def test_zero_n_group_has_null_pct():
    a = pd.DataFrame({"semestre": [1, 2], "intentos": [5, 0], "reprobados": [4, 0]})
    f = {x["semestre"]: x for x in VR.bloque_semestre_malla(a)["filas"]}
    assert f[2]["intentos"] == 0 and f[2]["tasa"] is None         # no attempts: no rate, no division by zero


def test_preparar_esperado_joins_by_intento_and_carries_no_section_column():
    snap = pd.DataFrame({"intento_id": np.arange(30), "cod_programa": "8213", "codigo_asignatura": "C1",
                         "periodo": ["202310"] * 15 + ["202510"] * 15, "y": [1, 0, 0] * 10})
    pr = {"prueba": {"intento_id": np.arange(15), "m": np.full(15, 0.3)},
          "posterior": {"intento_id": np.arange(15, 30), "m": np.full(15, 0.5)}}
    nombres = pd.DataFrame({"codigo": ["C1"], "nombre": ["Curso"], "depto": ["DM"], "depto_desc": ["Matemática"]})
    d = VR.preparar_esperado(snap, pr, "m", nombres)
    assert len(d) == 2 and set(d["ventana"]) == {"prueba", "posterior"}
    assert d.loc[d["ventana"] == "prueba", "esperados"].iloc[0] == pytest.approx(4.5)
    assert not any(c in d.columns for c in ("nrc", "docente_key", "seccion"))
