"""Classical survival baselines of T3: Aalen-Johansen per program and cause-specific Cox proportional hazards.

Both return the predicted cumulative incidence of egress, ``F1`` (n, U), over the model times ``u = 1 .. U`` (semesters
after the cut). Cox is fitted with lifelines (L2-penalized); the competing exit has its own Cox model, and the two
hazards are combined in discrete time (``models.t3_data.cif_desde_riesgos``) so that the cumulative incidences obey
``F1 + F2 + S = 1``.
"""
from __future__ import annotations

import warnings
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from evaluation import metrics_t3 as M3
from models.t3_data import cif_desde_riesgos

MIN_N_PROGRAMA = 50              # programs with fewer train rows use the pooled estimate


class AJPrograma:
    """Aalen-Johansen estimate by program (``programa=True``) or pooled, learned on train."""

    def __init__(self, U: int, programa: bool = True, min_n: int = MIN_N_PROGRAMA):
        self.U, self.programa, self.min_n = U, programa, min_n

    def fit(self, train: pd.DataFrame) -> "AJPrograma":
        grid = np.arange(1, self.U + 1)
        self.global_ = M3.aalen_johansen(train["u"].to_numpy(), train["causa"].to_numpy(), grid)["F1"]
        self.tabla: Dict[str, np.ndarray] = {}
        if self.programa:
            for prog, d in train.groupby("cod_programa"):
                if len(d) >= self.min_n:
                    self.tabla[prog] = M3.aalen_johansen(d["u"].to_numpy(), d["causa"].to_numpy(), grid)["F1"]
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        out = np.tile(self.global_, (len(df), 1))
        if self.programa:
            for i, prog in enumerate(df["cod_programa"].to_numpy()):
                f = self.tabla.get(prog)
                if f is not None:
                    out[i] = f
        return out


def _cox(X: np.ndarray, u: np.ndarray, evento: np.ndarray, columnas: Sequence[str], penalizador: float):
    from lifelines import CoxPHFitter

    df = pd.DataFrame(X, columns=list(columnas))
    df["u"], df["e"] = u.astype("float64"), evento.astype("int64")
    m = CoxPHFitter(penalizer=penalizador, l1_ratio=0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(df, duration_col="u", event_col="e", fit_options={"step_size": 0.5})
    return m


class CoxCausaEspecifica:
    """Two penalized Cox models (cause 1 and cause 2), the other cause treated as censoring in each."""

    def __init__(self, U: int, penalizador: float = 0.1):
        self.U, self.penalizador = U, penalizador

    def fit(self, X: np.ndarray, u: np.ndarray, causa: np.ndarray) -> "CoxCausaEspecifica":
        self.activas = np.flatnonzero(X.std(axis=0) > 1e-8)                  # constant columns carry no information
        self.columnas = [f"x{i}" for i in self.activas]
        Xa = X[:, self.activas]
        self.m1 = _cox(Xa, u, causa == 1, self.columnas, self.penalizador)
        self.m2 = _cox(Xa, u, causa == 2, self.columnas, self.penalizador)
        return self

    def _incrementos(self, modelo, Xa: np.ndarray) -> np.ndarray:
        grid = np.arange(1, self.U + 1)           # lifelines pads times before the first event with the first value
        h = modelo.predict_cumulative_hazard(pd.DataFrame(Xa, columns=self.columnas), times=grid)
        return np.diff(h.to_numpy().T, axis=1, prepend=0.0)                  # (n, U): increments of the cumulative hazard

    def predict(self, X: np.ndarray) -> np.ndarray:
        Xa = X[:, self.activas]
        d1, d2 = self._incrementos(self.m1, Xa), self._incrementos(self.m2, Xa)
        tot = d1 + d2
        h_tot = 1.0 - np.exp(-tot)
        cuota = np.divide(d1, tot, out=np.zeros_like(d1), where=tot > 0)
        return cif_desde_riesgos(h_tot * cuota, h_tot * (1.0 - cuota))["F1"]

    def n_variables(self) -> int:
        return len(self.activas)
