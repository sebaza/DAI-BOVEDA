"""Classical survival models of T6 (docs/12_benchmark_t6.md): historical cumulative incidence by program (baseline) and an
L2-penalized Cox proportional hazards model. Both return the predicted cumulative incidence ``F(tau | x)`` at the requested
semesters after the egreso ``taus`` as an array ``(n, len(taus))``. Boosted trees and networks are not implemented: the number
of events does not support them (``rules_t6.MIN_EVENTOS_CATBOOST`` / ``MIN_EVENTOS_RED``, D68).
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from evaluation import metrics_t3 as M3
from evaluation import metrics_t6 as M6
from models.t3_supervivencia import _cox

MIN_N_PROGRAMA = 50              # programs with fewer train rows use the pooled estimate
GRID_PENALIZADOR = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)


class BaselinePrograma:
    """1 - Kaplan-Meier by program (``cod_programa``) learned on train; pooled estimate for small or unseen programs."""

    def __init__(self, taus: Sequence[int], min_n: int = MIN_N_PROGRAMA):
        self.taus, self.min_n = list(taus), min_n

    def fit(self, train: pd.DataFrame) -> "BaselinePrograma":
        self.global_ = M6.incidencia_acumulada(train["tiempo"], train["evento"], self.taus)
        self.tabla: Dict[str, np.ndarray] = {}
        for prog, d in train.groupby("cod_programa"):
            if len(d) >= self.min_n:
                self.tabla[prog] = M6.incidencia_acumulada(d["tiempo"], d["evento"], self.taus)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        out = np.tile(self.global_, (len(df), 1))
        for i, prog in enumerate(df["cod_programa"].to_numpy()):
            f = self.tabla.get(prog)
            if f is not None:
                out[i] = f
        return out


class CoxT6:
    """L2-penalized Cox model (lifelines); constant columns carry no information and are dropped."""

    def __init__(self, taus: Sequence[int], penalizador: float = 0.1):
        self.taus, self.penalizador = list(taus), penalizador

    def fit(self, X: np.ndarray, tiempo: np.ndarray, evento: np.ndarray) -> "CoxT6":
        self.activas = np.flatnonzero(X.std(axis=0) > 1e-8)
        self.columnas = [f"x{i}" for i in self.activas]
        self.global_ = M6.incidencia_acumulada(tiempo, evento, self.taus)
        self.modelo = _cox(X[:, self.activas], tiempo, evento, self.columnas, self.penalizador) if len(self.activas) else None
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.modelo is None:
            return np.tile(self.global_, (len(X), 1))
        h = self.modelo.predict_cumulative_hazard(pd.DataFrame(X[:, self.activas], columns=self.columnas), times=self.taus)
        return 1.0 - np.exp(-h.to_numpy().T)

    def n_variables(self) -> int:
        return len(self.activas)


def ajustar_cox(taus: Sequence[int], X_tr, t_tr, e_tr, X_va, t_va, e_va, grid: Sequence[float] = GRID_PENALIZADOR,
                tau: Optional[int] = None) -> Tuple[CoxT6, Dict]:
    """Choose the penalty by the concordance on valid truncated at ``tau`` (ties: the stronger penalty)."""
    tau = int(tau if tau is not None else list(taus)[-1])
    j = list(taus).index(tau)
    busqueda, mejor = [], None
    for pen in grid:
        m = CoxT6(taus, pen).fit(X_tr, t_tr, e_tr)
        c = M3.c_index_uno(t_va, e_va, m.predict(X_va)[:, j], tau)
        busqueda.append({"penalizador": pen, "c_valid": float(c)})
        if mejor is None or c >= mejor[0]:
            mejor = (c, m, pen)
    return mejor[1], {"penalizador": mejor[2], "c_valid": float(mejor[0]), "tau": tau, "busqueda": busqueda,
                      "n_variables": mejor[1].n_variables()}
