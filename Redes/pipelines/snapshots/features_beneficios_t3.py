"""Point-in-time benefit features of the T3 snapshot (``rules_beneficios_t3`` holds the rules and the reasons).

``features_beneficios_t3(cortes, beneficios, regla)`` takes the cut rows (``episodio_id``, ``k``, ``persona_key``, ``cod_programa``
= program in force at the cut, ``cod_programa_ingreso`` = program of the admission, ``periodo_admision``, ``periodo_corte``) and the
benefit rows (``periodo`` = year, ``persona_key``, ``cod_carrera``, ``codigo``, ``benef_sem1``) and returns one row per cut. A row
of another program is ignored (D91); nothing later than the latest allowed year and no second-semester amount is ever read.
Helpers of ``features_beneficios`` (T1) are imported, never edited.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from . import features_beneficios as FB
from . import rules_beneficios_t3 as RT

COLS_FIN = ["tiene_gratuidad", "tiene_credito", "tiene_beca_estatal", "tiene_beca_ucn", "merito_ingreso", "merito_e1",
            "n_beneficios", "monto_sem1", "anios_con_gratuidad"]
COLS_PERDIDA = ["perdio_gratuidad", "perdio_credito", "perdio_cualquier_beneficio", "obtuvo_gratuidad"]
COLS_EXPCAP = ["expiro_gratuidad", "etapa_capstone", "expiro_alguna", "capstone_alguna"]
COLS_BENEFICIOS_T3 = ["ben_sin_dato", "anio_ben", *COLS_FIN, *COLS_EXPCAP, "perdida_sin_dato", *COLS_PERDIDA, "banda_decil"]
_FLAGS = ["gratuidad", "credito", "beca_estatal", "beca_ucn", "merito", "merito_e1", "d7", "d89", "expiro", "capstone"]


def _pares_programa(c: pd.DataFrame) -> pd.DataFrame:
    """One row per (cut row, program code): the program in force at the cut and the admission program (deduplicated)."""
    a = c[["_row", "cod_programa"]].rename(columns={"cod_programa": "cod_carrera"})
    b = c[["_row", "cod_programa_ingreso"]].rename(columns={"cod_programa_ingreso": "cod_carrera"})
    return pd.concat([a, b], ignore_index=True).dropna().drop_duplicates()


def _valores_anuales(c: pd.DataFrame, anual: pd.DataFrame, anio_min: pd.Series, anio_max: pd.Series) -> pd.DataFrame:
    """Per (row, year) of each window the flags of the benefit rows of the student in the allowed programs (0 when absent)."""
    n = (anio_max - anio_min + 1).clip(lower=0).to_numpy("int64")
    fila = np.repeat(c["_row"].to_numpy(), n)
    inicio = np.repeat(np.cumsum(n) - n, n)
    anio = np.repeat(anio_min.to_numpy("int64"), n) + (np.arange(len(fila)) - inicio)
    w = pd.DataFrame({"_row": fila, "periodo": anio})
    w = w.merge(c[["_row", "persona_key"]], on="_row")
    w = w.merge(_pares_programa(c), on="_row")
    w = w.merge(anual, on=["persona_key", "cod_carrera", "periodo"], how="left")
    agg = {f: (f, "max") for f in _FLAGS}
    agg.update(n=("n", "sum"), monto=("monto", "sum"))
    return w.groupby(["_row", "periodo"], as_index=False).agg(**agg).fillna(0.0)


def features_beneficios_t3(cortes: pd.DataFrame, beneficios: pd.DataFrame, regla: str) -> pd.DataFrame:
    c = cortes[["episodio_id", "k", "persona_key", "cod_programa", "cod_programa_ingreso", "periodo_admision",
                "periodo_corte"]].reset_index(drop=True).copy()
    c["_row"] = np.arange(len(c))
    anio_dato_max = int(beneficios["periodo"].max()) if len(beneficios) else RT.ANIO_MIN - 1
    a = c["periodo_corte"].map(lambda p: RT.anio_maximo(regla, p))
    a0 = c["periodo_admision"].map(RT.anio_inicio)
    con_dato = (a.notna() & a0.notna() & (a >= a0) & (a <= anio_dato_max)).to_numpy()
    a0_eff = a0.fillna(0).astype("int64")
    a_eff = a.fillna(0).astype("int64").where(con_dato, a0_eff)
    ventana_max = a_eff.where(con_dato, a0_eff - 1)                      # empty window when there is no data
    v = _valores_anuales(c, FB._por_anio(beneficios), a0_eff, ventana_max)
    v = v.set_index(pd.MultiIndex.from_arrays([v["_row"].to_numpy(), v["periodo"].to_numpy()]))

    def en(anio: pd.Series, col: str) -> np.ndarray:
        pos = v.index.get_indexer(pd.MultiIndex.from_arrays([c["_row"].to_numpy(), anio.to_numpy()]))
        if len(v) == 0:
            return np.full(len(c), np.nan)
        return np.where(pos >= 0, v[col].to_numpy()[np.maximum(pos, 0)], np.nan)

    out = c[["episodio_id", "k"]].copy()
    out["ben_sin_dato"] = (~con_dato).astype(int)
    out["anio_ben"] = np.where(con_dato, a_eff, np.nan)
    nivel = {col: en(a_eff, col) for col in (*_FLAGS, "n", "monto")}
    sin = ~con_dato
    for dst, src in (("tiene_gratuidad", "gratuidad"), ("tiene_credito", "credito"), ("tiene_beca_estatal", "beca_estatal"),
                     ("tiene_beca_ucn", "beca_ucn"), ("merito_ingreso", "merito"), ("merito_e1", "merito_e1"),
                     ("expiro_gratuidad", "expiro"), ("etapa_capstone", "capstone"), ("n_beneficios", "n"),
                     ("monto_sem1", "monto")):
        out[dst] = np.where(sin, np.nan, nivel[src])
    banda = np.where(nivel["gratuidad"] == 1, "<=6", np.where(nivel["d7"] == 1, "7", np.where(nivel["d89"] == 1, "8-9", "desconocida")))
    out["banda_decil"] = pd.Series(np.where(sin, None, banda), index=out.index, dtype="object")

    # accumulated over the window of the student (admission year .. latest allowed year)
    acum = v.groupby(level=0).agg(grat=("gratuidad", "sum"), exp=("expiro", "max"), cap=("capstone", "max"))
    acum = acum.reindex(c["_row"].to_numpy())
    ventana_incompleta = (c["periodo_admision"].map(RT.anio_admision) < RT.ANIO_MIN).to_numpy()   # years before the table starts
    out["anios_con_gratuidad"] = np.where(sin | ventana_incompleta, np.nan, acum["grat"].to_numpy())
    out["expiro_alguna"] = np.where(sin, np.nan, acum["exp"].to_numpy())
    out["capstone_alguna"] = np.where(sin, np.nan, acum["cap"].to_numpy())

    # year-over-year loss: needs the year before the latest allowed one inside the window
    previo = a_eff - 1
    con_perdida = con_dato & (previo.to_numpy() >= a0_eff.to_numpy())
    g0, c0, n0 = (en(previo, x) for x in ("gratuidad", "credito", "n"))
    g1, c1, n1 = nivel["gratuidad"], nivel["credito"], nivel["n"]
    out["perdida_sin_dato"] = (~con_perdida).astype(int)
    valores = {"perdio_gratuidad": (g0 == 1) & (g1 == 0), "perdio_credito": (c0 == 1) & (c1 == 0),
               "perdio_cualquier_beneficio": (n0 > 0) & (n1 == 0), "obtuvo_gratuidad": (g0 == 0) & (g1 == 1)}
    for col in COLS_PERDIDA:
        out[col] = np.where(con_perdida, valores[col].astype("float64"), np.nan)
    return out[["episodio_id", "k", *COLS_BENEFICIOS_T3]].reset_index(drop=True)


def columnas_numericas(bloque: str) -> List[str]:
    """Numeric model columns of a block: ``fin``, ``expcap`` or ``todo`` (``banda_decil`` is fairness-only, never a feature)."""
    if bloque == "fin":
        return ["ben_sin_dato", *COLS_FIN, "perdida_sin_dato", *COLS_PERDIDA]
    if bloque == "expcap":
        return ["ben_sin_dato", *COLS_EXPCAP]
    if bloque == "todo":
        return ["ben_sin_dato", *COLS_FIN, *COLS_EXPCAP, "perdida_sin_dato", *COLS_PERDIDA]
    raise ValueError(bloque)
