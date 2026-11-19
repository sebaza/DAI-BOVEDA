"""Multiclass view of T4 / T5: one model of the five outcomes at the horizon (continua, egreso, transicion, eliminacion,
otra_salida), so that the competing outcomes are explicit.

* ``TasaClases``: class frequencies by program learned on train (shrunk to the global ones for small programs).
* ``logistica_multiclase``: regularized multinomial logistic regression, C tuned on the validation log-loss.
* ``catboost_multiclase``: CatBoost ``MultiClass`` with native categoricals, early stopping on the validation log-loss.
"""
from __future__ import annotations

import warnings
from typing import Sequence

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

N_CLASES = 5
GRID_C = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0)
MIN_N = 20
SUAVIZADO = 20.0           # pseudo-observations of the global distribution added to every program
PARAMS = dict(iterations=1500, learning_rate=0.05, depth=6, l2_leaf_reg=5.0, early_stopping_rounds=100,
              eval_metric="MultiClass", loss_function="MultiClass", thread_count=16, verbose=False,
              allow_writing_files=False)


def _completar(p: np.ndarray, clases: Sequence[int], n_clases: int = N_CLASES, piso: float = 1e-6) -> np.ndarray:
    """Probabilities with one column per class (a class absent from training gets the floor)."""
    out = np.full((len(p), n_clases), piso)
    out[:, list(clases)] = p
    return out / out.sum(axis=1, keepdims=True)


class TasaClases:
    def __init__(self, suavizado: float = SUAVIZADO, min_n: int = MIN_N):
        self.suavizado, self.min_n = suavizado, min_n

    def fit(self, train: pd.DataFrame) -> "TasaClases":
        y = train["yc"].to_numpy()
        self.global_ = np.bincount(y, minlength=N_CLASES) / len(y)
        self.tabla = {}
        for prog, idx in train.groupby("cod_programa").indices.items():
            if len(idx) < self.min_n:
                continue
            c = np.bincount(y[idx], minlength=N_CLASES)
            self.tabla[prog] = (c + self.suavizado * self.global_) / (len(idx) + self.suavizado)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return np.stack([self.tabla.get(p, self.global_) for p in df["cod_programa"]])


def logistica_multiclase(X_tr, y_tr, X_va, y_va, grid_c: Sequence[float] = GRID_C, seed: int = 0):
    mejor = None
    for c in grid_c:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = LogisticRegression(C=c, max_iter=3000, solver="lbfgs", random_state=seed).fit(X_tr, y_tr)
        p = _completar(m.predict_proba(X_va), m.classes_)
        ll = float(log_loss(y_va, p, labels=list(range(N_CLASES))))
        if mejor is None or ll < mejor[0]:
            mejor = (ll, m, c)
    return mejor[1], {"C": mejor[2], "logloss_valid": mejor[0]}


def predecir_logistica(m: LogisticRegression, X) -> np.ndarray:
    return _completar(m.predict_proba(X), m.classes_)


def catboost_multiclase(X_tr: pd.DataFrame, y_tr, X_va: pd.DataFrame, y_va, cat_cols: Sequence[str], seed: int = 0):
    m = CatBoostClassifier(random_seed=seed, classes_count=N_CLASES, **PARAMS)
    m.fit(Pool(X_tr, y_tr, cat_features=list(cat_cols)), eval_set=Pool(X_va, y_va, cat_features=list(cat_cols)),
          use_best_model=True)
    return m, {"mejor_iteracion": int(m.get_best_iteration())}


def predecir_catboost(m: CatBoostClassifier, X: pd.DataFrame, cat_cols: Sequence[str]) -> np.ndarray:
    return _completar(m.predict_proba(Pool(X, cat_features=list(cat_cols))), [int(c) for c in m.classes_])
