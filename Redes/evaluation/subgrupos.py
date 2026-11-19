"""Descriptive subgroup and fairness tables (aggregates only; groups with fewer than ``N_MIN`` rows are dropped)."""
from __future__ import annotations

from typing import Dict, List, Mapping

import numpy as np
import pandas as pd

from .metrics import ece, metricas, recall_precision_top

N_MIN_PROGRAMA = 100
N_MIN_GRUPO = 30


def tabla_grupo(df: pd.DataFrame, y: np.ndarray, p: np.ndarray, columna: str, n_min: int) -> List[Dict]:
    """One row per group: n, observed rate, mean risk, AP, ROC-AUC, recall@10, ECE and calibration gap."""
    rows = []
    values = df[columna].astype("object").where(df[columna].notna(), "sin_dato")
    for valor, idx in values.groupby(values).indices.items():
        if len(idx) < n_min:
            continue
        yg, pg = y[idx], p[idx]
        m = metricas(yg, pg)
        rec, prec = recall_precision_top(yg, pg)
        rows.append({
            "grupo": str(valor), "n": int(len(idx)), "tasa_observada": float(yg.mean()),
            "riesgo_medio": float(pg.mean()), "brecha_calibracion": float(pg.mean() - yg.mean()),
            "ap": m["ap"], "roc_auc": m["roc_auc"], "recall_10": rec, "ece": m["ece"],
        })
    return sorted(rows, key=lambda r: r["grupo"])


def brechas_sexo(tabla: List[Dict]) -> Dict[str, float]:
    """Gaps F - M of the sex table (descriptive; sex is not a model input)."""
    por = {r["grupo"]: r for r in tabla}
    if "F" not in por or "M" not in por:
        return {}
    return {k: float(por["F"][k] - por["M"][k]) for k in ("tasa_observada", "riesgo_medio", "brecha_calibracion",
                                                          "ap", "recall_10", "ece")}


def todos(df: pd.DataFrame, y: np.ndarray, p: np.ndarray) -> Mapping[str, List[Dict]]:
    return {
        "programa": tabla_grupo(df, y, p, "cod_programa", N_MIN_PROGRAMA),
        "cohorte": tabla_grupo(df, y, p, "cohorte_anio", N_MIN_GRUPO),
        "via": tabla_grupo(df, y, p, "via_clase", N_MIN_GRUPO),
        "sexo": tabla_grupo(df, y, p, "sexo_equidad", N_MIN_GRUPO),
    }
