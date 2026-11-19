"""Model 3: CatBoost with native categoricals, early stopping on the validation log-loss.

A first run stopped on PRAUC: with a validation set from a different period the best PRAUC iteration varied from 12 to
79 between seeds and the early ones left the probabilities uncalibrated (ECE up to 0.11). Stopping on log-loss and
starting from the average rate (``boost_from_average``) is stable and calibration aware; the ranking metrics are
reported unchanged on the test set.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool

PARAMS = dict(iterations=1500, learning_rate=0.05, depth=6, l2_leaf_reg=5.0, early_stopping_rounds=100,
              eval_metric="Logloss", loss_function="Logloss", boost_from_average=True, thread_count=16, verbose=False, allow_writing_files=False)


def ajustar(X_tr: pd.DataFrame, y_tr, X_va: pd.DataFrame, y_va, cat_cols: Sequence[str], seed: int = 0):
    m = CatBoostClassifier(random_seed=seed, **PARAMS)
    m.fit(Pool(X_tr, y_tr, cat_features=list(cat_cols)), eval_set=Pool(X_va, y_va, cat_features=list(cat_cols)),
          use_best_model=True)
    return m, {"mejor_iteracion": int(m.get_best_iteration()), "params": {**PARAMS, "random_seed": seed}}


def predecir(m: CatBoostClassifier, X: pd.DataFrame, cat_cols: Sequence[str]) -> np.ndarray:
    return m.predict_proba(Pool(X, cat_features=list(cat_cols)))[:, 1]
