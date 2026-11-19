"""Point-in-time benefit features from the load history (``rules_beneficios_cargas`` holds the rule and its reasons).

``features_beneficios_cargas(cortes, cargas, calendario)`` takes the cut rows (``episodio_id``, ``k``, ``persona_key``,
``cod_programa``, ``periodo_corte``), the compressed history (one row per year / person / program / code / coverage with
``first_ts``, ``last_ts`` and ``sem1_primera`` / ``sem1_ultima``) and the calendar of loads (``timestamp_carga``, ``periodo`` = year), and returns one
row per cut with the SAME columns as ``features_beneficios`` (``COLS_BENEFICIOS``), so the benefit models can score it unchanged.
The loss variables are not defined here (they exist only at k = 4, which has no history): they are NaN with ``perdida_sin_dato`` = 1.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from . import features_beneficios as FB
from . import rules_beneficios_cargas as RC

COLS_SALIDA = ["episodio_id", "k", *FB.COLS_BENEFICIOS]


def calendario_por_anio(calendario: pd.DataFrame) -> Dict[int, np.ndarray]:
    """``{year: sorted array of load timestamps that contain that year}``."""
    return {int(a): np.sort(g["timestamp_carga"].astype("int64").unique()) for a, g in calendario.groupby("periodo")}


def carga_de_corte(cortes: pd.DataFrame, cal: Dict[int, np.ndarray]) -> pd.DataFrame:
    """Copy of the cuts with ``_fila`` (position), ``_t`` (cut year), ``_carga`` (last load of the year on or before the cut date,
    <NA> when the year has no history or no load by then) and ``_con_historial``."""
    c = cortes[["episodio_id", "k", "persona_key", "cod_programa", "periodo_corte"]].reset_index(drop=True).copy()
    c["_fila"] = np.arange(len(c))
    c["_t"] = c["periodo_corte"].str.slice(0, 4).astype(int)
    historial = RC.anios_con_historial({a: int(v[0]) for a, v in cal.items() if len(v)})
    carga = [RC.ultima_carga_hasta(cal[t], RC.ts_fin_del_dia(RC.fecha_corte(p))) if historial.get(t, False) else None
             for t, p in zip(c["_t"], c["periodo_corte"])]
    c["_carga"] = pd.array(carga, dtype="Int64")
    c["_con_historial"] = c["_carga"].notna()
    return c


def filas_visibles(c: pd.DataFrame, cargas: pd.DataFrame) -> pd.DataFrame:
    """History rows visible at each cut (see ``rules_beneficios_cargas.visible``), one row per (cut, visible benefit row)."""
    con = c.loc[c["_con_historial"], ["_fila", "persona_key", "cod_programa", "_t", "_carga"]]
    m = con.merge(cargas.rename(columns={"cod_carrera": "cod_programa", "periodo": "_t"}),
                  on=["persona_key", "cod_programa", "_t"], how="inner")
    carga = m["_carga"].astype("int64").to_numpy()
    return m.loc[(m["first_ts"].astype("int64").to_numpy() <= carga) & (carga <= m["last_ts"].astype("int64").to_numpy())]


def features_beneficios_cargas(cortes: pd.DataFrame, cargas: pd.DataFrame, calendario: pd.DataFrame) -> pd.DataFrame:
    c = carga_de_corte(cortes, calendario_por_anio(calendario))
    m = filas_visibles(c, cargas)
    # same family logic as the final-view features: a frame whose "person" is the cut row, so each cut aggregates only its own
    # visible rows (two cuts of one person in the same year can have different cut dates)
    monto = RC.montos_corregidos(m["sem1_primera"].to_numpy("float64"), m["sem1_ultima"].to_numpy("float64"))   # P97 / D111
    b = pd.DataFrame({"periodo": 0, "persona_key": m["_fila"].astype(str).to_numpy(), "cod_carrera": "x",
                      "codigo": m["codigo"].to_numpy(), "benef_sem1": monto})
    anual = FB._por_anio(b)
    a = anual.drop(columns=["cod_carrera", "periodo"]).rename(columns={"persona_key": "_fila"})
    a["_fila"] = a["_fila"].astype(int)
    # a cut whose visible rows include an amount that is not used (variation >= 90 %) gets no amount at all
    invalida = set(m.loc[np.isnan(monto), "_fila"].astype(int))
    r = c[["_fila", "episodio_id", "k", "_con_historial"]].merge(a, on="_fila", how="left")
    monto_invalido = r["_fila"].isin(invalida).to_numpy()
    sin_dato = (~r["_con_historial"]).to_numpy()
    for col in ("gratuidad", "credito", "beca_estatal", "beca_ucn", "merito", "merito_e1", "d7", "d89", "expiro", "capstone",
                "n", "monto"):
        r[col] = r[col].astype("float64").fillna(0.0)
    out = pd.DataFrame({"episodio_id": r["episodio_id"], "k": r["k"], "ben_sin_dato": sin_dato.astype(int)})
    out["tiene_gratuidad"], out["tiene_credito"] = r["gratuidad"], r["credito"]
    out["tiene_beca_estatal"], out["tiene_beca_ucn"] = r["beca_estatal"], r["beca_ucn"]
    out["merito_ingreso"], out["merito_e1"] = r["merito"], r["merito_e1"]
    out["banda_decil"] = pd.Series(FB._banda(r["gratuidad"], r["d7"], r["d89"]), index=r.index, dtype="object")
    out["expiro_gratuidad"], out["etapa_capstone"] = r["expiro"], r["capstone"]
    out["n_beneficios"], out["monto_sem1"] = r["n"], r["monto"]
    for col in FB._NUM_NIVEL:
        out[col] = out[col].astype("float64").where(~sin_dato, np.nan)
    out["monto_sem1"] = out["monto_sem1"].where(~monto_invalido, np.nan)
    out["banda_decil"] = out["banda_decil"].where(~sin_dato, None)
    out["perdida_sin_dato"] = 1
    for col in FB.COLS_PERDIDA:
        out[col] = np.nan
    return out[COLS_SALIDA].reset_index(drop=True)
