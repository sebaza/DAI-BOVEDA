"""Discrete-time hazard models of T3: person-period multinomial logistic regression and CatBoost.

One row per episode x at-risk semester after the cut, with outcome 0 (survives the semester), 1 (egress / titulation) or
2 (definitive exit). The multiclass probabilities of a semester are the cause-specific discrete hazards; the cumulative
incidence of egress follows from ``t3_data.cif_desde_riesgos``. Both models learn on TRAIN and stop / tune on the
person-period log-loss of VALID (a proper scoring rule of the whole hazard, not of one horizon).
"""
from __future__ import annotations

import warnings
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

from models.data import Preprocesador
from models.t3_data import JMAX, cif_desde_riesgos, columnas_tiempo, expandir_persona_periodo

GRID_C = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
CB_PARAMS = dict(iterations=1200, learning_rate=0.08, depth=6, l2_leaf_reg=5.0, early_stopping_rounds=60,
                 loss_function="MultiClass", eval_metric="MultiClass", thread_count=-1, verbose=False,
                 allow_writing_files=False)


def _rejilla(df: pd.DataFrame, k: int) -> Tuple[np.ndarray, np.ndarray]:
    """All (episode, slot) pairs ``k+1 .. JMAX`` in episode-major order (for prediction)."""
    U = JMAX - k
    return np.repeat(np.arange(len(df)), U), np.tile(np.arange(k + 1, JMAX + 1), len(df))


def _one_hot_slot(j: np.ndarray, k: int) -> np.ndarray:
    oh = np.zeros((len(j), JMAX - k), dtype="float32")
    oh[np.arange(len(j)), j - k - 1] = 1.0
    return oh


def _x_logistica(prep: Preprocesador, df: pd.DataFrame, fila: np.ndarray, j: np.ndarray, k: int,
                 estatica: Optional[np.ndarray] = None) -> np.ndarray:
    est = prep.transform(df) if estatica is None else estatica
    return np.hstack([est[fila], _one_hot_slot(j, k)])


def logistica_ajustar(prep: Preprocesador, tr: pd.DataFrame, va: pd.DataFrame, k: int,
                      grid_c: Sequence[float] = GRID_C, seed: int = 0):
    """Return ``(modelo, info)``; the winner minimizes the person-period log-loss on valid."""
    f_tr, j_tr, y_tr = expandir_persona_periodo(tr, k)
    f_va, j_va, y_va = expandir_persona_periodo(va, k)
    Xtr = _x_logistica(prep, tr, f_tr, j_tr, k)
    Xva = _x_logistica(prep, va, f_va, j_va, k)
    mejor, busqueda = None, []
    for c in grid_c:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = LogisticRegression(C=c, max_iter=400, solver="lbfgs", random_state=seed)
            m.fit(Xtr, y_tr)
        ll = float(log_loss(y_va, m.predict_proba(Xva), labels=[0, 1, 2]))
        busqueda.append({"C": c, "logloss_valid": ll})
        if mejor is None or ll < mejor[0]:
            mejor = (ll, m, c)
    return mejor[1], {"C": mejor[2], "logloss_valid": mejor[0], "n_variables": int(Xtr.shape[1]),
                      "filas_persona_periodo": int(len(y_tr)), "busqueda": busqueda}


def logistica_cif(modelo: LogisticRegression, prep: Preprocesador, df: pd.DataFrame, k: int) -> np.ndarray:
    est = prep.transform(df)
    fila, j = _rejilla(df, k)
    p = modelo.predict_proba(_x_logistica(prep, df, fila, j, k, est))
    p = p.reshape(len(df), JMAX - k, 3)
    return cif_desde_riesgos(p[:, :, 1], p[:, :, 2])["F1"]


def _x_catboost(prep: Preprocesador, df: pd.DataFrame, fila: np.ndarray, j: np.ndarray) -> pd.DataFrame:
    base = prep.transform_catboost(df).iloc[fila].reset_index(drop=True)
    t = columnas_tiempo(j, df["duracion_nominal"].to_numpy("float64")[fila])
    return pd.concat([base, t], axis=1)


def catboost_ajustar(prep: Preprocesador, tr: pd.DataFrame, va: pd.DataFrame, k: int, seed: int):
    from catboost import CatBoostClassifier, Pool

    f_tr, j_tr, y_tr = expandir_persona_periodo(tr, k)
    f_va, j_va, y_va = expandir_persona_periodo(va, k)
    cat = list(prep.cat_cols)
    Xtr, Xva = _x_catboost(prep, tr, f_tr, j_tr), _x_catboost(prep, va, f_va, j_va)
    m = CatBoostClassifier(random_seed=seed, **CB_PARAMS)
    m.fit(Pool(Xtr, y_tr, cat_features=cat), eval_set=Pool(Xva, y_va, cat_features=cat), use_best_model=True)
    return m, {"mejor_iteracion": int(m.get_best_iteration()), "filas_persona_periodo": int(len(y_tr))}


def catboost_cif(modelos, prep: Preprocesador, df: pd.DataFrame, k: int) -> np.ndarray:
    """Mean over seeds of the cumulative incidence of egress."""
    from catboost import Pool

    fila, j = _rejilla(df, k)
    X = _x_catboost(prep, df, fila, j)
    cat = list(prep.cat_cols)
    out = []
    for m in modelos:
        p = m.predict_proba(Pool(X, cat_features=cat)).reshape(len(df), JMAX - k, 3)
        out.append(cif_desde_riesgos(p[:, :, 1], p[:, :, 2])["F1"])
    return np.mean(out, axis=0)
