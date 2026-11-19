"""Metrics of T2 (event = reprobacion): weighted AP / ROC-AUC / Brier / ECE, per-(student, period) ranking metrics
(Recall@K, Precision@K) and a CLUSTER bootstrap that resamples (student, period) groups.

Bootstrap: one multinomial draw of group counts per replicate, shared by every model (so paired differences are valid).
Row weights are the counts of their group. Each model's ordering is sorted once; a replicate only needs weighted
cumulative sums, which equals ``sklearn`` with ``sample_weight`` (tested).
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

METRICAS = ("ap", "ap_aprob", "roc_auc", "brier", "ece", "recall_at_1", "precision_at_1", "recall_at_2",
            "precision_at_2")
KS = (1, 2)
BINS = 10


class Ordenado:
    """Scores sorted once (descending, stable) with the tie boundaries needed for AP / AUC with weights."""

    def __init__(self, y: np.ndarray, p: np.ndarray):
        self.n = len(y)
        self.order = np.argsort(-p, kind="stable")
        ps = p[self.order]
        self.y = y[self.order].astype("float64")
        self.fin = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])        # last index of every tie group

    def ap_auc(self, w: np.ndarray) -> Tuple[float, float]:
        ws = w[self.order]
        tp = np.cumsum(ws * self.y)[self.fin]
        fp = np.cumsum(ws * (1.0 - self.y))[self.fin]
        pos, neg = tp[-1], fp[-1]
        if pos <= 0 or neg <= 0:
            return float("nan"), float("nan")
        precision = np.divide(tp, tp + fp, out=np.zeros_like(tp), where=(tp + fp) > 0)
        recall = tp / pos
        ap = float(np.sum(np.diff(recall, prepend=0.0) * precision))
        fpr, tpr = np.r_[0.0, fp / neg], np.r_[0.0, recall]
        auc = float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2.0))
        return ap, auc


class Evaluador:
    """Precomputed structures of one (y, p, groups) triple; ``metricas(w)`` evaluates all metrics under row weights."""

    def __init__(self, y: np.ndarray, p: np.ndarray, grupo: np.ndarray, semilla: int = 0):
        self.y = np.asarray(y).astype("float64")
        self.p = np.asarray(p, dtype="float64")
        self.grupo = np.asarray(grupo)
        self.pos = Ordenado(self.y, self.p)
        self.neg = Ordenado(1.0 - self.y, 1.0 - self.p)
        rank = _rank_promedio(self.p)
        self.bin = np.minimum(BINS - 1, np.floor((rank - 1) / len(self.p) * BINS).astype(int))
        self.n_grupos = int(self.grupo.max()) + 1
        self.rank_grupo = ranking_por_grupo(self.y, self.p, self.grupo, KS, semilla)

    def metricas(self, w: np.ndarray, cg: Optional[np.ndarray] = None) -> Dict[str, float]:
        """``w``: row weights; ``cg``: group weights (default: derived from ``w`` is not possible, so pass both)."""
        ap, auc = self.pos.ap_auc(w)
        ap_neg, _ = self.neg.ap_auc(w)
        sw = w.sum()
        brier = float(np.sum(w * (self.p - self.y) ** 2) / sw)
        nb = np.bincount(self.bin, w, BINS)
        sp = np.bincount(self.bin, w * self.p, BINS)
        sy = np.bincount(self.bin, w * self.y, BINS)
        ece = float(np.sum(np.abs(sy - sp)) / sw)
        out = {"ap": ap, "ap_aprob": ap_neg, "roc_auc": auc, "brier": brier, "ece": ece}
        for k in KS:
            rec, prec, elegible = self.rank_grupo[k]
            cw = cg * elegible
            denom = cw.sum()
            out[f"recall_at_{k}"] = float(np.sum(cw * rec) / denom) if denom > 0 else float("nan")
            out[f"precision_at_{k}"] = float(np.sum(cw * prec) / denom) if denom > 0 else float("nan")
        return out


def _rank_promedio(p: np.ndarray) -> np.ndarray:
    from scipy.stats import rankdata
    return rankdata(p, method="average")


def ranking_por_grupo(y: np.ndarray, p: np.ndarray, grupo: np.ndarray, ks: Sequence[int] = KS, semilla: int = 0
                      ) -> Dict[int, Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Per group: Recall@K and Precision@K of the top-K courses by risk; ties broken by a seeded random key.

    A group is *elegible* when it has >= 2 courses and at least one failed course (otherwise ranking is trivial or
    recall undefined). Returns ``{K: (recall[g], precision[g], elegible[g])}`` with arrays of length ``n_grupos``.
    """
    g = np.asarray(grupo)
    ng = int(g.max()) + 1
    azar = np.random.default_rng(semilla).random(len(p))
    order = np.lexsort((azar, -p, g))
    gs, ys = g[order], y[order]
    n = np.bincount(g, minlength=ng).astype("float64")
    f = np.bincount(g, weights=y, minlength=ng)
    inicio = np.r_[0, np.cumsum(n)[:-1]].astype("int64")
    pos_en_grupo = np.arange(len(g)) - inicio[gs]
    elegible = ((n >= 2) & (f >= 1)).astype("float64")
    out = {}
    for k in ks:
        hits = np.bincount(gs, weights=ys * (pos_en_grupo < k), minlength=ng)
        rec = np.divide(hits, f, out=np.zeros(ng), where=f > 0)
        prec = hits / np.minimum(k, np.maximum(n, 1.0))
        out[k] = (rec, prec, elegible)
    return out


def referencia_azar(y: np.ndarray, grupo: np.ndarray, ks: Sequence[int] = KS) -> Dict[str, float]:
    """Expected Recall@K / Precision@K of a random ranking over the elegible groups (closed form)."""
    g = np.asarray(grupo)
    ng = int(g.max()) + 1
    n = np.bincount(g, minlength=ng).astype("float64")
    f = np.bincount(g, weights=y, minlength=ng)
    el = (n >= 2) & (f >= 1)
    out = {"n_grupos_elegibles": int(el.sum())}
    for k in ks:
        kk = np.minimum(k, n)
        out[f"recall_at_{k}"] = float(np.mean((kk / n)[el]))               # E[hits]/f = K'/n
        out[f"precision_at_{k}"] = float(np.mean((f / n)[el]))             # E[hits]/K' = f/n
    return out


def reconstruir_grupos(persona: Sequence, periodo: Sequence) -> np.ndarray:
    """Integer id of every (student, period) pair."""
    import pandas as pd
    return pd.factorize(pd.Series(persona).astype(str) + "|" + pd.Series(periodo).astype(str))[0].astype("int64")


def puntuales(y, p, grupo, semilla: int = 0) -> Dict[str, float]:
    ev = Evaluador(y, p, grupo, semilla)
    return ev.metricas(np.ones(len(ev.y)), np.ones(ev.n_grupos))


def bootstrap(y: np.ndarray, scores: Mapping[str, np.ndarray], grupo: np.ndarray, n_boot: int = 1000, seed: int = 0,
              pares: Optional[Sequence[Tuple[str, str]]] = None, semilla_ranking: int = 0) -> Dict[str, Dict]:
    """95 % percentile intervals resampling groups; ``pares`` = [(a, b)] adds paired differences ``a - b``.

    Returns ``{modelo: {metrica: {punto, lo, hi}}}`` and ``"__delta__a__b"`` entries.
    """
    y = np.asarray(y)
    g = np.asarray(grupo)
    rng = np.random.default_rng(seed)
    ng = int(g.max()) + 1
    evs = {m: Evaluador(y, np.asarray(p), g, semilla_ranking) for m, p in scores.items()}
    punto = {m: ev.metricas(np.ones(len(y)), np.ones(ng)) for m, ev in evs.items()}
    draws = {m: {k: np.empty(n_boot) for k in METRICAS} for m in evs}
    for b in range(n_boot):
        cg = rng.multinomial(ng, np.full(ng, 1.0 / ng)).astype("float64")
        w = cg[g]
        for m, ev in evs.items():
            r = ev.metricas(w, cg)
            for k in METRICAS:
                draws[m][k][b] = r[k]
    out: Dict[str, Dict] = {}
    for m in evs:
        out[m] = {k: {"punto": punto[m][k], "lo": float(np.nanpercentile(draws[m][k], 2.5)),
                      "hi": float(np.nanpercentile(draws[m][k], 97.5))} for k in METRICAS}
    for a, c in pares or []:
        if a in evs and c in evs:
            out[f"__delta__{a}__{c}"] = {
                k: {"punto": punto[a][k] - punto[c][k],
                    "lo": float(np.nanpercentile(draws[a][k] - draws[c][k], 2.5)),
                    "hi": float(np.nanpercentile(draws[a][k] - draws[c][k], 97.5))} for k in METRICAS}
    return out


def tabla_confiabilidad(y: np.ndarray, p: np.ndarray, bins: int = BINS) -> List[Dict[str, float]]:
    rank = _rank_promedio(p)
    which = np.minimum(bins - 1, np.floor((rank - 1) / len(p) * bins).astype(int))
    rows = []
    for b in range(bins):
        idx = np.flatnonzero(which == b)
        if len(idx):
            rows.append({"decil": b + 1, "n": int(len(idx)), "riesgo_medio": float(p[idx].mean()),
                         "tasa_observada": float(y[idx].mean())})
    return rows
