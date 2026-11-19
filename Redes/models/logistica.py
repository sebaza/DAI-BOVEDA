"""Baseline 2: regularized logistic regression on one-hot + standardized features, C tuned on valid.

``class_weight`` is considered but not adopted: re-weighting classes raises the AP a little on some splits yet shifts
the predicted probabilities far from the observed rates (ECE up to 0.27 in a first run), and T1 is meant to give
usable risk probabilities. The best re-weighted fit is recorded in ``info`` for transparency.
"""
from __future__ import annotations

import warnings
from typing import Sequence

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score

GRID_C = (0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
GRID_PESO = (None, "balanced")


def ajustar(X_tr, y_tr, X_va, y_va, grid_c: Sequence[float] = GRID_C, pesos=GRID_PESO, seed: int = 0):
    """Return ``(modelo, info)``; the winner maximizes AP on valid among the unweighted fits (ties: smaller C)."""
    mejor, mejor_pesado, info = None, None, {"busqueda": []}
    for peso in pesos:
        for c in grid_c:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m = LogisticRegression(C=c, class_weight=peso, max_iter=3000, solver="lbfgs", random_state=seed)
                m.fit(X_tr, y_tr)
            ap = float(average_precision_score(y_va, m.predict_proba(X_va)[:, 1]))
            info["busqueda"].append({"C": c, "class_weight": peso or "none", "ap_valid": ap})
            if peso is None:
                if mejor is None or ap > mejor[0]:
                    mejor = (ap, m, c, peso)
            elif mejor_pesado is None or ap > mejor_pesado[0]:
                mejor_pesado = (ap, c, peso)
    info.update({"C": mejor[2], "class_weight": "none", "ap_valid": mejor[0]})
    if mejor_pesado is not None:
        info["mejor_con_pesos"] = {"C": mejor_pesado[1], "class_weight": mejor_pesado[2], "ap_valid": mejor_pesado[0]}
    return mejor[1], info
