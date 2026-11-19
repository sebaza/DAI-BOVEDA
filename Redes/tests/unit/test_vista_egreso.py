"""View "Lo que pasó": causes of elimination and time to graduate by program."""
import numpy as np
import pandas as pd
import pytest

from evaluation import vista_egreso as VE


def _causas(pequenos=(6, 7)):
    filas, i = [], 0
    for cod, nombre, fac, n in (("P1", "Prog uno", "F1", 60), ("P2", "Prog dos", "F1", 40),
                                ("P3", "Prog tres", "F2", pequenos[0]), ("P4", "Prog cuatro", "F2", pequenos[1])):
        for j in range(n):
            i += 1
            filas.append({"episodio_id": i, "periodo": "202010", "cod_programa": cod, "programa": nombre, "facultad": fac,
                          "cod_causal": ["0B", "0C", "0D", "0A"][j % 4] if j % 5 else "5A"})
    return pd.DataFrame(filas)


def test_small_program_is_published_with_its_exact_counts():
    b = VE.bloque_causales_programa(_causas())
    assert [f["programa"] for f in b["filas"]] == ["Prog uno", "Prog dos", "Prog tres", "Prog cuatro"]
    assert [f["total"] for f in b["filas"]] == [60, 40, 6, 7] and (b["desde"], b["hasta"]) == ("201610", "202520")
    assert all(f["cod_programa"] is not None for f in b["filas"])


def test_no_size_based_otros_row_anywhere():
    b = VE.bloque_causales_programa(_causas(pequenos=(1, 2)))
    assert all("otros" not in f["programa"].lower() and f["cod_programa"] for f in b["filas"])
    for f in b["filas"]:
        assert all(c["grupo"] != "otros" for c in f["causales"])
    assert "OTROS_PROGRAMAS" not in dir(VE)


def test_causales_publish_every_cause_with_its_exact_count_in_each_row():
    b = VE.bloque_causales_programa(_causas(pequenos=(4, 5)))
    for f in b["filas"]:
        assert [c["grupo"] for c in f["causales"]] == list(VE.GRUPOS_CAUSAL)
        assert sum(c["n"] for c in f["causales"]) == f["total"]
    d = _causas()
    assert VE.bloque_causales_programa(d[d["periodo"] < "201610"]) is None    # outside the window nothing remains
    assert VE.bloque_causales_programa(d[d["cod_programa"] == "P3"])["filas"][0]["total"] == 6


def test_causales_by_faculty_rows_are_faculties():
    b = VE.bloque_causales_programa(_causas(pequenos=(20, 20)), por="facultad")
    assert b["nivel"] == "facultad" and [f["programa"] for f in b["filas"]] == ["F1", "F2"]
    assert all(f["cod_programa"] is None for f in b["filas"])


def _t3():
    rng = np.random.default_rng(0)
    filas = []
    for cod, n in (("P1", 60), ("P2", 8)):
        for e in rng.random(n) < 0.6:
            filas.append({"cod_programa": cod, "programa": f"Prog {cod}", "duracion_nominal_sem": 10, "seguimiento_max": 16,
                          "tiempo": int(rng.integers(9, 15)), "causa": 1 if e else 2})
    filas.append({"cod_programa": "P1", "programa": "Prog P1", "duracion_nominal_sem": 10, "seguimiento_max": 12, "tiempo": 5, "causa": 1})
    return pd.DataFrame(filas)


def test_tiempo_publishes_small_programs_with_exact_shares():
    b = VE.bloque_tiempo(_t3())
    assert [f["cod_programa"] for f in b["filas"]] == ["P1", "P2"]       # P2 has 8; the episode with follow-up 12 < 10 + 4 is not counted
    f = b["filas"][0]
    assert f["n"] == 60 and f["duracion_nominal_sem"] == 10 and b["filas"][1]["n"] == 8
    present = [f["pct_a_tiempo"], f["pct_mas_1"], f["pct_mas_2"]]
    assert all(v is not None and 0 <= v <= 1 for v in present) and present == sorted(present)      # cumulative
    assert "regla_duracion" in b


def test_tiempo_shares_are_never_hidden_for_small_counts():
    d = pd.DataFrame({"cod_programa": "P1", "programa": "p", "duracion_nominal_sem": 10, "seguimiento_max": 20,
                      "tiempo": [10] * 3 + [12] * 27 + [14] * 20, "causa": 1})
    f = VE.bloque_tiempo(d)["filas"][0]
    assert f["pct_a_tiempo"] == pytest.approx(3 / 50) and f["pct_mas_1"] == pytest.approx(30 / 50) and f["pct_mas_2"] == 1.0
    d = pd.DataFrame({"cod_programa": "P1", "programa": "p", "duracion_nominal_sem": 10, "seguimiento_max": 20,
                      "tiempo": [10] * 10 + [12] * 5 + [14] * 20 + [30] * 15, "causa": [1] * 35 + [2] * 15})
    f = VE.bloque_tiempo(d)["filas"][0]
    assert (f["pct_a_tiempo"], f["pct_mas_1"], f["pct_mas_2"]) == (pytest.approx(10 / 50), pytest.approx(15 / 50), pytest.approx(35 / 50))


def test_zero_n_group_has_null_pct():
    assert VE._pct_acumulado(0, 0) is None and VE._pct_acumulado(0, 5) == 0.0
    # real blocks: a cause with n = 0 inside a program row carries its count and no percentage; a program nobody graduates from has 0 %
    f = VE.bloque_causales_programa(_causas(pequenos=(3, 3)))["filas"][2]
    cero = [c for c in f["causales"] if c["n"] == 0]
    assert cero and all("pct" not in c for c in f["causales"]) and sum(c["n"] for c in f["causales"]) == f["total"]
    d = pd.DataFrame({"cod_programa": "P1", "programa": "p", "duracion_nominal_sem": 10, "seguimiento_max": 20,
                      "tiempo": [30] * 4, "causa": [2] * 4})
    r = VE.bloque_tiempo(d)["filas"][0]
    assert r["n"] == 4 and (r["pct_a_tiempo"], r["pct_mas_1"], r["pct_mas_2"]) == (0.0, 0.0, 0.0)
