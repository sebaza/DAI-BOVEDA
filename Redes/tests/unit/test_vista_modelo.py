"""Blocks "Cómo decide el modelo": families of inputs, permutation importance and the wait-a-semester comparison."""
import numpy as np
import pandas as pd
import pytest

from evaluation import familias_variables as FV
from evaluation import vista_historica as VH
from evaluation import vista_modelo as VM
from models import data as D
from models import t2_data as TD2
from models import t3_data as TD3


def test_every_model_input_has_a_family():
    columnas = set()
    for num, cat in (D.GRUPOS["pre_entry+academico"], TD2.CONJUNTOS["c_nuevas"], TD3.GRUPOS["adm"], TD3.GRUPOS["adm+agg"]):
        columnas |= set(num) | set(cat)
    assert columnas - set(FV.FAMILIA) == set()
    assert set(FV.FAMILIA.values()) <= set(FV.ETIQUETA_FAMILIA)
    assert not [c for c in FV.FAMILIA if "sexo" in c]                         # sex is never an input


def test_sequence_channels_have_a_family():
    assert {f"seq:{c}" for c in TD3.SEQ_COLS_T3} <= set(FV.FAMILIA)


class Logistico:
    """Stub model: probability driven only by ``x1``; ``ruido`` is ignored."""
    def predecir(self, filas, sem=None):
        return 1 / (1 + np.exp(-3.0 * filas["x1"].to_numpy()))


def test_permutation_ranks_the_informative_family_first():
    rng = np.random.default_rng(1)
    n = 3000
    filas = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n), "ruido": rng.normal(size=n)})
    y = (rng.random(n) < 1 / (1 + np.exp(-3.0 * filas["x1"].to_numpy()))).astype(int)
    res = VM.importancia_permutacion(Logistico(), filas, None, y, {"x": ["x1"], "otra": ["x2"], "ruido": ["ruido"]}, repeticiones=3)
    assert res[0]["familia"] == "x" and res[0]["caida_ap"] > 0.1
    assert [r["caida_ap"] for r in res] == sorted((r["caida_ap"] for r in res), reverse=True)
    positivas = [r["peso_pct"] for r in res if r["caida_ap"] > 0]
    assert sum(positivas) == pytest.approx(100.0)
    assert all(r["peso_pct"] == 0 for r in res if r["caida_ap"] <= 0)
    assert set(res[0]) == {"familia", "etiqueta", "caida_ap", "peso_pct"}


def test_permutation_is_reproducible_and_does_not_touch_the_input_frame():
    rng = np.random.default_rng(2)
    filas = pd.DataFrame({"x1": rng.normal(size=500), "x2": rng.normal(size=500)})
    y = (rng.random(500) < 0.3).astype(int)
    antes = filas.copy()
    a = VM.importancia_permutacion(Logistico(), filas, None, y, {"x": ["x1"], "o": ["x2"]}, repeticiones=2, semilla=7)
    b = VM.importancia_permutacion(Logistico(), filas, None, y, {"x": ["x1"], "o": ["x2"]}, repeticiones=2, semilla=7)
    assert a == b
    pd.testing.assert_frame_equal(filas, antes)


def test_esperar_uses_de_cada_10_of_curva_alcance():
    rng = np.random.default_rng(3)
    y1, y2 = (rng.random(2000) < 0.2).astype(int), (rng.random(1500) < 0.2).astype(int)
    p1, p2 = y1 * 0.5 + rng.random(2000) * 0.5, y2 * 0.9 + rng.random(1500) * 0.1
    b = VM.bloque_esperar([{"tarea": "t1", "k_antes": 1, "k_despues": 2, "y_antes": y1, "p_antes": p1, "y_despues": y2, "p_despues": p2}])
    assert b["nota_poblaciones"] is True
    c = b["comparaciones"][0]
    assert (c["tarea"], c["k_antes"], c["k_despues"]) == ("t1", 1, 2)
    assert c["de_cada_10_antes"] == VH.curva_alcance(y1, p1)["de_cada_10"]
    assert c["de_cada_10_despues"] == VH.curva_alcance(y2, p2)["de_cada_10"]
    assert c["de_cada_10_despues"] > c["de_cada_10_antes"]


def test_bloque_senales_keeps_top_five_per_task():
    imp = [{"familia": f"f{i}", "etiqueta": f"F{i}", "caida_ap": 0.1 - i * 0.01, "peso_pct": 10.0} for i in range(8)]
    b = VM.bloque_senales([{"tarea": "t1", "k": 1, "modelo": "cb_acad", "importancia": imp, "n_muestra": 500}])
    t = b["tareas"][0]
    assert [s["familia"] for s in t["senales"]] == ["f0", "f1", "f2", "f3", "f4"]
    assert t["n_muestra"] == 500 and (t["tarea"], t["k"], t["modelo"]) == ("t1", 1, "cb_acad")


def test_document_stores_the_model_blocks_under_ucn_only():
    from pipelines.marts import vista_historica as MV

    rng = np.random.default_rng(4)
    n = 300
    fac = np.array(["Facultad A", "Facultad B"])[rng.integers(0, 2, n)]
    t3 = pd.DataFrame({"tiempo": rng.integers(1, 13, n), "causa": rng.integers(0, 3, n), "eliminado": False, "facultad": fac, "cohorte_anio": 2018})
    t1 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022})
    t5 = pd.DataFrame({"facultad": fac, "cohorte_anio": 2022, "resultado": "continua", "p": rng.random(n) * 0.3})
    causas = pd.DataFrame({"facultad": fac, "cod_causal": "0B"})
    sen = {"tareas": [{"tarea": "t1", "k": 1, "modelo": "cb_acad", "n_muestra": 300, "senales": []}]}
    esp = {"comparaciones": [], "nota_poblaciones": True}
    doc = VH.construir_documento(t3, t1, (rng.random(n) < 0.2).astype(int), rng.random(n), t5, causas, senales=sen, esperar_semestre=esp)
    assert set(doc["senales"]) == {"Toda la UCN"} and set(doc["esperar_semestre"]) == {"Toda la UCN"}
    assert {k: v for k, v in doc["senales"]["Toda la UCN"].items() if k not in ("modelo", "modelos", "aplica_a_poblacion")} == sen
    assert {k: v for k, v in doc["esperar_semestre"]["Toda la UCN"].items() if k not in ("modelo", "modelos", "aplica_a_poblacion")} == esp
    assert doc["senales"]["Toda la UCN"]["aplica_a_poblacion"] is False and doc["esperar_semestre"]["Toda la UCN"]["aplica_a_poblacion"] is False
    assert {"senales", "esperar_semestre"} <= set(MV.BLOQUES)
    assert {b for b, f, _ in MV.filas(doc) if b in ("senales", "esperar_semestre")} == {"senales", "esperar_semestre"}
    assert VH.construir_documento(t3, t1, (rng.random(n) < 0.2).astype(int), rng.random(n), t5, causas)["senales"] == {}
