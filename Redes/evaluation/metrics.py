"""Binary-risk metrics for T1 (event = no_continua) with bootstrap confidence intervals.

All functions take numpy arrays: ``y`` in {0, 1} and ``p`` a risk score (a probability for calibration metrics).
"""
from __future__ import annotations

import math
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_auc_score

METRICAS = ("ap", "roc_auc", "brier", "ece", "recall_10", "precision_10")
TOP_FRACCION = 0.10


def top_k_indices(p: np.ndarray, fraccion: float = TOP_FRACCION) -> np.ndarray:
    """Indices of the ``ceil(fraccion * n)`` highest scores; ties are broken by position (stable, deterministic)."""
    n = len(p)
    k = max(1, math.ceil(fraccion * n))
    return np.argsort(-p, kind="stable")[:k]


def recall_precision_top(y: np.ndarray, p: np.ndarray, fraccion: float = TOP_FRACCION) -> Tuple[float, float]:
    idx = top_k_indices(p, fraccion)
    hits = float(y[idx].sum())
    total = float(y.sum())
    return (hits / total if total > 0 else float("nan")), hits / len(idx)


def tabla_confiabilidad(y: np.ndarray, p: np.ndarray, bins: int = 10) -> List[Dict[str, float]]:
    """Reliability table by (approximately) equal-count deciles of the predicted risk.

    The bin comes from the average rank, so tied scores always share a bin (a score with few distinct values, such
    as the historical-rate baseline, yields fewer, larger bins instead of an arbitrary split of ties).
    """
    n = len(p)
    rank = rankdata(p, method="average")
    which = np.minimum(bins - 1, np.floor((rank - 1) / n * bins).astype(int))
    rows = []
    for b in range(bins):
        idx = np.flatnonzero(which == b)
        if len(idx) == 0:
            continue
        rows.append({"decil": b + 1, "n": int(len(idx)), "riesgo_medio": float(p[idx].mean()),
                     "tasa_observada": float(y[idx].mean())})
    return rows


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error over equal-count bins: sum_b n_b/n * |observed_b - predicted_b|."""
    n = len(p)
    return float(sum(r["n"] / n * abs(r["tasa_observada"] - r["riesgo_medio"]) for r in tabla_confiabilidad(y, p, bins)))


def metricas(y: np.ndarray, p: np.ndarray) -> Dict[str, float]:
    y = np.asarray(y)
    p = np.asarray(p, dtype="float64")
    if y.min() == y.max():                       # a single class: ranking metrics are undefined
        ap = auc = float("nan")
    else:
        ap, auc = float(average_precision_score(y, p)), float(roc_auc_score(y, p))
    rec, prec = recall_precision_top(y, p)
    return {"ap": ap, "roc_auc": auc, "brier": float(np.mean((p - y) ** 2)), "ece": ece(y, p),
            "recall_10": rec, "precision_10": prec}


def bootstrap(
    y: np.ndarray,
    scores: Mapping[str, np.ndarray],
    n_boot: int = 1000,
    seed: int = 0,
    referencia: Optional[str] = None,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """95% percentile intervals with the SAME resamples for every model (so paired differences are valid).

    Returns ``{modelo: {metrica: {punto, lo, hi}}}`` plus, when ``referencia`` is given, ``"__delta__<modelo>"`` entries
    with the paired difference ``modelo - referencia``.
    """
    y = np.asarray(y)
    rng = np.random.default_rng(seed)
    n = len(y)
    names = list(scores)
    point = {m: metricas(y, scores[m]) for m in names}
    draws: Dict[str, Dict[str, List[float]]] = {m: {k: [] for k in METRICAS} for m in names}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        if yb.min() == yb.max():
            continue
        for m in names:
            r = metricas(yb, np.asarray(scores[m])[idx])
            for k in METRICAS:
                draws[m][k].append(r[k])
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for m in names:
        out[m] = {}
        for k in METRICAS:
            d = np.array(draws[m][k], dtype="float64")
            out[m][k] = {"punto": point[m][k], "lo": float(np.nanpercentile(d, 2.5)),
                         "hi": float(np.nanpercentile(d, 97.5))}
    if referencia is not None:
        for m in names:
            if m == referencia:
                continue
            out[f"__delta__{m}"] = {}
            for k in METRICAS:
                d = np.array(draws[m][k]) - np.array(draws[referencia][k])
                out[f"__delta__{m}"][k] = {"punto": point[m][k] - point[referencia][k],
                                           "lo": float(np.nanpercentile(d, 2.5)),
                                           "hi": float(np.nanpercentile(d, 97.5))}
    return out
