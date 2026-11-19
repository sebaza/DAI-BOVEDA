"""Point-in-time benefit features of the T1 snapshot (``rules_beneficios`` holds the definitions and the reasons).

``features_beneficios(cortes, beneficios)`` takes the cut rows (``episodio_id``, ``k``, ``persona_key``, ``cod_programa``,
``periodo_corte``) and the benefit rows (``periodo`` = year, ``persona_key``, ``cod_carrera``, ``codigo``, ``benef_sem1``) and
returns one row per cut. Nothing later than the cut year and no second-semester amount is ever read.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from . import rules_beneficios as RB

COLS_PERDIDA = ["perdio_gratuidad", "perdio_credito", "perdio_cualquier_beneficio", "obtuvo_gratuidad"]
COLS_NIVEL = ["tiene_gratuidad", "tiene_credito", "tiene_beca_estatal", "tiene_beca_ucn", "merito_ingreso", "merito_e1",
              "banda_decil", "expiro_gratuidad", "etapa_capstone", "n_beneficios", "monto_sem1"]
COLS_BENEFICIOS = ["ben_sin_dato", *COLS_NIVEL, "perdida_sin_dato", *COLS_PERDIDA]
_NUM_NIVEL = [c for c in COLS_NIVEL if c != "banda_decil"]
_COLS_ANUAL = ["persona_key", "cod_carrera", "periodo", "gratuidad", "credito", "beca_estatal", "beca_ucn", "merito",
               "merito_e1", "d7", "d89", "expiro", "capstone", "n", "monto"]


def _por_anio(beneficios: pd.DataFrame) -> pd.DataFrame:
    """One row per (persona, programa, anio) with the family flags of that year."""
    if len(beneficios) == 0:
        return pd.DataFrame(columns=_COLS_ANUAL)
    b = beneficios[["periodo", "persona_key", "cod_carrera", "codigo", "benef_sem1"]].copy()
    flags = {c: RB.clasificar(c) for c in b["codigo"].dropna().unique()}
    for campo in ("familia", "merito", "merito_e1", "decil", "expiro", "capstone"):
        b[campo] = b["codigo"].map(lambda c, campo=campo: flags[c][campo] if c in flags else None)
    for fam in RB.FAMILIAS:
        b[fam] = (b["familia"] == fam).astype(int)
    b["merito"] = b["merito"].fillna(0).astype(int)
    b["merito_e1"] = b["merito_e1"].fillna(False).astype(int)
    b["d7"] = (b["decil"] == "7").astype(int)
    b["d89"] = (b["decil"] == "8-9").astype(int)
    b["expiro"] = b["expiro"].fillna(0).astype(int)
    b["capstone"] = b["capstone"].fillna(False).astype(int)
    b["n"] = 1
    b["monto"] = pd.to_numeric(b["benef_sem1"], errors="coerce").fillna(0.0)
    return b.groupby(["persona_key", "cod_carrera", "periodo"], as_index=False).agg(
        gratuidad=("gratuidad", "max"), credito=("credito", "max"), beca_estatal=("beca_estatal", "max"),
        beca_ucn=("beca_ucn", "max"), merito=("merito", "max"), merito_e1=("merito_e1", "max"), d7=("d7", "max"),
        d89=("d89", "max"), expiro=("expiro", "max"), capstone=("capstone", "max"), n=("n", "sum"),
        monto=("monto", "sum"))


def _banda(gratuidad, d7, d89) -> np.ndarray:
    return np.where(gratuidad == 1, "<=6", np.where(d7 == 1, "7", np.where(d89 == 1, "8-9", "desconocida")))


def features_beneficios(cortes: pd.DataFrame, beneficios: pd.DataFrame,
                        ks_perdida: Sequence[int] = RB.K_PERDIDA) -> pd.DataFrame:
    c = cortes[["episodio_id", "k", "persona_key", "cod_programa", "periodo_corte"]].reset_index(drop=True).copy()
    anio_max = int(beneficios["periodo"].max()) if len(beneficios) else RB.ANIO_MIN - 1
    anual = _por_anio(beneficios)
    c["_t"] = c["periodo_corte"].str.slice(0, 4).astype(int)
    c["ben_sin_dato"] = (~((c["_t"] >= RB.ANIO_MIN) & (c["_t"] <= anio_max))).astype(int)
    a = anual.rename(columns={"cod_carrera": "cod_programa", "periodo": "_t"})
    m = c.merge(a, on=["persona_key", "cod_programa", "_t"], how="left")
    sin_dato = (m["ben_sin_dato"] == 1).to_numpy()
    for col in ("gratuidad", "credito", "beca_estatal", "beca_ucn", "merito", "merito_e1", "d7", "d89", "expiro",
                "capstone", "n", "monto"):
        m[col] = m[col].fillna(0.0)
    out = c[["episodio_id", "k", "ben_sin_dato"]].copy()
    out["tiene_gratuidad"], out["tiene_credito"] = m["gratuidad"], m["credito"]
    out["tiene_beca_estatal"], out["tiene_beca_ucn"] = m["beca_estatal"], m["beca_ucn"]
    out["merito_ingreso"], out["merito_e1"] = m["merito"], m["merito_e1"]
    out["banda_decil"] = pd.Series(_banda(m["gratuidad"], m["d7"], m["d89"]), index=c.index, dtype="object")
    out["expiro_gratuidad"], out["etapa_capstone"] = m["expiro"], m["capstone"]
    out["n_beneficios"], out["monto_sem1"] = m["n"], m["monto"]
    for col in _NUM_NIVEL:
        out[col] = out[col].astype("float64").where(~sin_dato, np.nan)
    out["banda_decil"] = out["banda_decil"].where(~sin_dato, None)

    # loss variables: the year before the cut year against the cut year, only at ks_perdida
    p = anual.rename(columns={"cod_carrera": "cod_programa", "periodo": "_tp"})
    c["_tp"] = c["_t"] - 1
    prev = c[["persona_key", "cod_programa", "_tp"]].merge(
        p[["persona_key", "cod_programa", "_tp", "gratuidad", "credito", "n"]],
        on=["persona_key", "cod_programa", "_tp"], how="left")
    g0, c0, n0 = (prev[x].fillna(0.0).to_numpy() for x in ("gratuidad", "credito", "n"))
    tiene_g, tiene_c, n1 = (m[x].to_numpy() for x in ("gratuidad", "credito", "n"))
    con_perdida = (c["k"].isin(list(ks_perdida)) & (c["_tp"] >= RB.ANIO_MIN) & (c["_t"] <= anio_max)).to_numpy()
    out["perdida_sin_dato"] = (~con_perdida).astype(int)
    valores = {
        "perdio_gratuidad": (g0 == 1) & (tiene_g == 0),
        "perdio_credito": (c0 == 1) & (tiene_c == 0),
        "perdio_cualquier_beneficio": (n0 > 0) & (n1 == 0),
        "obtuvo_gratuidad": (g0 == 0) & (tiene_g == 1),
    }
    for col in COLS_PERDIDA:
        out[col] = np.where(con_perdida, valores[col].astype("float64"), np.nan)
    return out[["episodio_id", "k", *COLS_BENEFICIOS]].reset_index(drop=True)
