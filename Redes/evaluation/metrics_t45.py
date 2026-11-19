"""Metrics of T4 / T5: binary risk with a bootstrap GROUPED BY PERSON, paired differences between models, multiclass view.

* ``remuestreos`` draws the same persons for every model and metric (so paired differences are valid) and keeps every
  row of a drawn person together (a person can have more than one trajectory).
* Binary metrics are those of ``evaluation.metrics`` (AP, ROC-AUC, Brier, ECE, recall / precision at 10 %).
* The multiclass view reports the log-loss, the multiclass Brier score and the one-vs-rest AP / ROC-AUC of each class.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from . import metrics as M

METRICAS = M.METRICAS


# ---------------------------------------------------------------------------------------------
# grouped resampling
# ---------------------------------------------------------------------------------------------
def remuestreos(grupos: Sequence, n_boot: int, seed: int = 0) -> List[np.ndarray]:
    """``n_boot`` index arrays: persons drawn with replacement, all the rows of a drawn person included."""
    codigos, unicos = pd.factorize(np.asarray(grupos))
    n_g = len(unicos)
    orden = np.argsort(codigos, kind="stable")
    cuentas = np.bincount(codigos, minlength=n_g)
    inicio = np.concatenate([[0], np.cumsum(cuentas)[:-1]])
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_boot):
        pick = rng.integers(0, n_g, n_g)
        largos = cuentas[pick]
        desplazamiento = np.repeat(inicio[pick] - (np.cumsum(largos) - largos), largos)
        out.append(orden[desplazamiento + np.arange(int(largos.sum()))])
    return out


def _pct(d: np.ndarray) -> Tuple[float, float]:
    d = d[~np.isnan(d)]
    if len(d) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def bootstrap_agrupado(y: np.ndarray, scores: Mapping[str, np.ndarray], idxs: Sequence[np.ndarray],
                       pares: Sequence[Tuple[str, str]] = ()) -> Dict[str, Dict[str, Dict[str, float]]]:
    """95 % percentile intervals of every metric of every model and of the paired differences ``a - b`` of ``pares``.

    Returns ``{modelo: {metrica: {punto, lo, hi}}}`` plus ``"a__vs__b"`` entries with the paired differences.
    """
    y = np.asarray(y)
    names = list(scores)
    sc = {m: np.asarray(scores[m], dtype="float64") for m in names}
    point = {m: M.metricas(y, sc[m]) for m in names}
    draws: Dict[str, Dict[str, List[float]]] = {m: {k: [] for k in METRICAS} for m in names}
    for idx in idxs:
        yb = y[idx]
        if yb.min() == yb.max():
            for m in names:
                for k in METRICAS:
                    draws[m][k].append(float("nan"))
            continue
        for m in names:
            r = M.metricas(yb, sc[m][idx])
            for k in METRICAS:
                draws[m][k].append(r[k])
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for m in names:
        out[m] = {}
        for k in METRICAS:
            lo, hi = _pct(np.array(draws[m][k]))
            out[m][k] = {"punto": point[m][k], "lo": lo, "hi": hi}
    for a, b in pares:
        if a not in sc or b not in sc:
            continue
        out[f"{a}__vs__{b}"] = {}
        for k in METRICAS:
            lo, hi = _pct(np.array(draws[a][k]) - np.array(draws[b][k]))
            out[f"{a}__vs__{b}"][k] = {"punto": point[a][k] - point[b][k], "lo": lo, "hi": hi}
    return out


# ---------------------------------------------------------------------------------------------
# multiclass view
# ---------------------------------------------------------------------------------------------
def metricas_multiclase(yc: np.ndarray, P: np.ndarray, clases: Sequence[str], eventos_min: int = 10) -> Dict[str, float]:
    """Log-loss, multiclass Brier and one-vs-rest AP / ROC-AUC of each class (NaN when it has fewer than ``eventos_min``
    events or all the rows)."""
    yc = np.asarray(yc)
    P = np.clip(np.asarray(P, dtype="float64"), 1e-12, 1.0)
    P = P / P.sum(axis=1, keepdims=True)
    n, c = P.shape
    onehot = np.zeros_like(P)
    onehot[np.arange(n), yc] = 1.0
    out = {"logloss": float(-np.mean(np.log(P[np.arange(n), yc]))), "brier_mc": float(np.mean(np.sum((P - onehot) ** 2, axis=1)))}
    aps = []
    for j, nombre in enumerate(clases):
        yj = onehot[:, j]
        ev = int(yj.sum())
        if ev < eventos_min or ev == n:
            out[f"ap_{nombre}"] = out[f"roc_auc_{nombre}"] = float("nan")
            continue
        out[f"ap_{nombre}"] = float(average_precision_score(yj, P[:, j]))
        out[f"roc_auc_{nombre}"] = float(roc_auc_score(yj, P[:, j]))
        aps.append(out[f"ap_{nombre}"])
    out["ap_macro"] = float(np.mean(aps)) if aps else float("nan")
    return out


def bootstrap_multiclase(yc: np.ndarray, probas: Mapping[str, np.ndarray], clases: Sequence[str],
                         idxs: Sequence[np.ndarray], pares: Sequence[Tuple[str, str]] = ()) -> Dict[str, Dict[str, Dict[str, float]]]:
    yc = np.asarray(yc)
    names = list(probas)
    point = {m: metricas_multiclase(yc, probas[m], clases) for m in names}
    claves = list(point[names[0]])
    draws = {m: {k: [] for k in claves} for m in names}
    for idx in idxs:
        yb = yc[idx]
        for m in names:
            r = metricas_multiclase(yb, np.asarray(probas[m])[idx], clases)
            for k in claves:
                draws[m][k].append(r[k])
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for m in names:
        out[m] = {}
        for k in claves:
            lo, hi = _pct(np.array(draws[m][k]))
            out[m][k] = {"punto": point[m][k], "lo": lo, "hi": hi}
    for a, b in pares:
        if a in point and b in point:
            out[f"{a}__vs__{b}"] = {}
            for k in claves:
                lo, hi = _pct(np.array(draws[a][k]) - np.array(draws[b][k]))
                out[f"{a}__vs__{b}"][k] = {"punto": point[a][k] - point[b][k], "lo": lo, "hi": hi}
    return out
