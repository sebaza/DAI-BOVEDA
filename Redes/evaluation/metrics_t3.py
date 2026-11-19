"""Survival metrics of T3 ("tiempo hasta titulacion", docs/10_benchmark_t3.md): nonparametric estimators, Uno's truncated
C-index, IPCW Brier / integrated Brier, time-dependent AUC and an episode bootstrap with paired differences.

Everything is written for a competing-risks setting: cause 1 = egress / titulation (the event of interest), cause 2 =
definitive exit, 0 = censored. A model's score is the predicted cumulative incidence of cause 1, ``F1(t | x)``, at the
absolute slots (regular semesters since admission) it was asked for.

Censoring in T3 is purely administrative: it depends only on the admission semester (``seguimiento``). Hence the
horizon metrics use the episodes followed up to the horizon (``resultado_horizonte``), for which the censoring weight
is exactly 1 (stratifying the IPCW weights by admission semester gives the same sample); the general IPCW versions
(``c_index_uno(g=...)``, ``brier_ipcw``) are kept and tested for any other censoring.

Numpy is the reference; ``Evaluador(backend="torch")`` evaluates the pairwise kernels on the GPU for the bootstrap.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import rankdata

HORIZONTES = (10, 12, 14)
IBS_HASTA = 12
BINS = 10
BLOQUE_NUMPY = 512
BLOQUE_TORCH = 4096


# ---------------------------------------------------------------------------------------------
# nonparametric estimators
# ---------------------------------------------------------------------------------------------
def _en_grilla(tiempos: np.ndarray, valores: np.ndarray, grid: np.ndarray, antes: float) -> np.ndarray:
    """Right-continuous step function ``valores`` defined at ``tiempos`` evaluated on ``grid`` (``antes`` before the first)."""
    pos = np.searchsorted(tiempos, grid, side="right") - 1
    return np.where(pos >= 0, valores[np.maximum(pos, 0)], antes)


def aalen_johansen(tiempo, causa, grid) -> Dict[str, np.ndarray]:
    """Aalen-Johansen estimate on integer times: overall survival ``S`` and cumulative incidences ``F1``, ``F2``."""
    t = np.asarray(tiempo, dtype="float64")
    c = np.asarray(causa)
    grid = np.asarray(grid, dtype="float64")
    u = np.unique(t)
    n = np.array([(t >= x).sum() for x in u], dtype="float64")
    d1 = np.array([((t == x) & (c == 1)).sum() for x in u], dtype="float64")
    d2 = np.array([((t == x) & (c == 2)).sum() for x in u], dtype="float64")
    s = np.empty(len(u))
    f1 = np.empty(len(u))
    f2 = np.empty(len(u))
    s_prev, a1, a2 = 1.0, 0.0, 0.0
    for i in range(len(u)):
        a1 += s_prev * d1[i] / n[i]
        a2 += s_prev * d2[i] / n[i]
        s_prev *= 1.0 - (d1[i] + d2[i]) / n[i]
        s[i], f1[i], f2[i] = s_prev, a1, a2
    return {"S": _en_grilla(u, s, grid, 1.0), "F1": _en_grilla(u, f1, grid, 0.0), "F2": _en_grilla(u, f2, grid, 0.0)}


def incidencia_ingenua(tiempo, causa, grid) -> np.ndarray:
    """``1 - KM`` of cause 1 treating the competing event as censoring (the biased naive estimate; reported for contrast)."""
    t = np.asarray(tiempo, dtype="float64")
    c = np.asarray(causa)
    u = np.unique(t)
    s, prev = np.empty(len(u)), 1.0
    for i, x in enumerate(u):
        n = (t >= x).sum()
        d = ((t == x) & (c == 1)).sum()
        prev *= 1.0 - d / n
        s[i] = prev
    return 1.0 - _en_grilla(u, s, np.asarray(grid, dtype="float64"), 1.0)


def supervivencia_censura(tiempo, causa, en, antes: bool = False) -> np.ndarray:
    """Kaplan-Meier of the CENSORING distribution (event = causa 0; a competing event is not a censoring).

    ``antes=True`` returns ``G(t-)`` (the weight of a subject whose event happens at ``t``), else ``G(t)``.
    """
    t = np.asarray(tiempo, dtype="float64")
    c = np.asarray(causa)
    u = np.unique(t[c == 0])
    g, prev = np.empty(len(u)), 1.0
    for i, x in enumerate(u):
        prev *= 1.0 - ((t == x) & (c == 0)).sum() / (t >= x).sum()
        g[i] = prev
    en = np.asarray(en, dtype="float64")
    if antes:
        pos = np.searchsorted(u, en, side="left") - 1                  # strictly before
        return np.where(pos >= 0, g[np.maximum(pos, 0)] if len(g) else 1.0, 1.0)
    return _en_grilla(u, g, en, 1.0) if len(u) else np.ones(len(en))


# ---------------------------------------------------------------------------------------------
# horizon outcome, AUC, Brier
# ---------------------------------------------------------------------------------------------
def resultado_horizonte(tiempo, causa, seguimiento, tau: float) -> Tuple[np.ndarray, np.ndarray]:
    """``(elegible, y)``: followed up to ``tau`` (no censoring uncertainty) and graduated (cause 1) by ``tau``."""
    t, c, seg = np.asarray(tiempo), np.asarray(causa), np.asarray(seguimiento)
    return seg >= tau, ((c == 1) & (t <= tau)).astype("int8")


def auc(y, score) -> float:
    """ROC-AUC (Mann-Whitney, ties count one half); NaN when a class is empty."""
    y = np.asarray(y).astype(bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(np.asarray(score, dtype="float64"))
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def brier_ipcw(tiempo, causa, f, tau: float) -> float:
    """IPCW Brier of ``F1(tau | x)``: events by ``tau`` weigh ``1/G(T-)``, subjects beyond ``tau`` weigh ``1/G(tau)``."""
    t = np.asarray(tiempo, dtype="float64")
    c = np.asarray(causa)
    f = np.asarray(f, dtype="float64")
    g_tau = float(supervivencia_censura(t, c, [tau])[0])
    if g_tau <= 0:
        return float("nan")
    antes = t <= tau
    obs = antes & (c != 0)
    w_ev = 1.0 / np.maximum(supervivencia_censura(t, c, t, antes=True), 1e-12)
    y = (c == 1).astype("float64")
    suma = np.where(obs, w_ev * (y - f) ** 2, 0.0) + np.where(t > tau, f ** 2 / g_tau, 0.0)
    return float(suma.sum() / len(t))


def ibs(tiempo, causa, seguimiento, f, grid) -> float:
    """Integrated Brier score of ``F1``: mean over the integer ``grid`` of the Brier score among the episodes followed
    up to the END of the grid. ``f`` has one column per grid point."""
    t, c, seg = np.asarray(tiempo), np.asarray(causa), np.asarray(seguimiento)
    grid = np.asarray(grid)
    ok = seg >= grid.max()
    y = ((c[ok, None] == 1) & (t[ok, None] <= grid[None, :])).astype("float64")
    return float(np.mean(np.mean((np.asarray(f)[ok] - y) ** 2, axis=0)))


# ---------------------------------------------------------------------------------------------
# pairwise kernels (numpy or torch)
# ---------------------------------------------------------------------------------------------
def _core_c(t, ef, caso, w, r, xp, bloque):
    """Weighted numerator and denominator of Uno's C over the case rows ``caso`` (index array)."""
    num = den = 0.0
    for i in range(0, len(caso), bloque):
        ib = caso[i:i + bloque]
        comp = ef[None, :] > t[ib][:, None]
        mayor = (r[ib][:, None] > r[None, :]) * 1.0 + (r[ib][:, None] == r[None, :]) * 0.5
        wb = w[ib][:, None]
        num += float((wb * comp * mayor).sum())
        den += float((wb * comp).sum())
    return num, den


def _core_auc(y, s, xp, bloque):
    """Pairwise ROC-AUC on tensors (the numpy path ranks instead)."""
    pos = xp.nonzero(y)[:, 0]
    neg = xp.nonzero(~y)[:, 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    num = 0.0
    for i in range(0, len(pos), bloque):
        sb = s[pos[i:i + bloque]][:, None]
        num += float(((sb > s[neg][None, :]) * 1.0 + (sb == s[neg][None, :]) * 0.5).sum())
    return num / (len(pos) * len(neg))


def c_index_uno(tiempo, causa, riesgo, tau: float, g=None) -> float:
    """Uno's C-index truncated at ``tau`` for cause 1 with a competing event (Wolbers et al.).

    Cases: cause-1 events with ``T <= tau``. A subject ``j`` is comparable to a case ``i`` if ``T_j > T_i`` or ``j`` had the
    competing event (it never has the event of interest). Pairs are weighted by ``1/G(T_i)^2`` (``g`` = ``G(T_i)`` per
    subject; omitted = no censoring). Tied risks count one half, tied times are not comparable.
    """
    t = np.asarray(tiempo, dtype="float64")
    c = np.asarray(causa)
    r = np.asarray(riesgo, dtype="float64")
    ef = np.where(c == 2, np.inf, t)
    caso = np.flatnonzero((c == 1) & (t <= tau))
    w = np.ones(len(t)) if g is None else 1.0 / np.maximum(np.asarray(g, dtype="float64"), 1e-12) ** 2
    num, den = _core_c(t, ef, caso, w, r, np, BLOQUE_NUMPY)
    return num / den if den > 0 else float("nan")


def calibracion_horizonte(tiempo, causa, seguimiento, f_tau, tau: float, bins: int = BINS) -> List[Dict[str, float]]:
    """Predicted vs observed cumulative incidence by (approximately) equal-count deciles, among followed-up episodes."""
    from .metrics import tabla_confiabilidad

    el, y = resultado_horizonte(tiempo, causa, seguimiento, tau)
    return tabla_confiabilidad(y[el].astype("float64"), np.asarray(f_tau, dtype="float64")[el], bins)


# ---------------------------------------------------------------------------------------------
# evaluator and bootstrap
# ---------------------------------------------------------------------------------------------
class Evaluador:
    """Metrics of several models on one evaluation set; ``metricas(idx)`` evaluates a (re)sample of its rows.

    ``scores[model]``: array ``(n, len(slots))`` with ``F1(slot | x)`` for the absolute ``slots`` (consecutive, starting
    at ``k + 1``). Per horizon ``tau`` (a slot): C-index truncated at ``tau``, ROC-AUC and Brier of ``F1(tau)`` among the
    episodes followed up to ``tau``; plus the integrated Brier score over the slots ``<= ibs_hasta``.
    """

    def __init__(self, tiempo, causa, seguimiento, slots, scores: Mapping[str, np.ndarray],
                 horizontes: Sequence[int] = HORIZONTES, ibs_hasta: int = IBS_HASTA, backend: str = "numpy",
                 device: Optional[str] = None):
        self.t = np.asarray(tiempo, dtype="float64")
        self.c = np.asarray(causa).astype("int64")
        self.seg = np.asarray(seguimiento, dtype="float64")
        self.slots = [int(s) for s in slots]
        self.modelos = list(scores)
        self.horizontes = [h for h in horizontes if h in self.slots]
        self.col_ibs = [i for i, s in enumerate(self.slots) if s <= ibs_hasta]
        self.backend = backend
        self.n = len(self.t)
        self.F = {m: np.asarray(scores[m], dtype="float64") for m in self.modelos}
        self.claves = [f"{k}_{h}" for h in self.horizontes for k in ("c", "auc", "brier")] + ["ibs"]
        if backend == "torch":
            import torch

            self.xp = torch
            self.dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
            as_t = lambda a, dt=torch.float64: torch.as_tensor(np.asarray(a), dtype=dt, device=self.dev)  # noqa: E731
            self._T, self._C, self._SEG = as_t(self.t), as_t(self.c, torch.int64), as_t(self.seg)
            self._F = {m: as_t(self.F[m]) for m in self.modelos}
        else:
            self.xp = np

    # -- one sample --------------------------------------------------------------------------
    def metricas(self, idx: np.ndarray) -> Dict[str, Dict[str, float]]:
        if self.backend == "torch":
            return self._metricas_torch(idx)
        idx = np.asarray(idx)
        t, c, seg = self.t[idx], self.c[idx], self.seg[idx]
        out: Dict[str, Dict[str, float]] = {}
        for m in self.modelos:
            f = self.F[m][idx]
            r: Dict[str, float] = {}
            for h in self.horizontes:
                col = self.slots.index(h)
                el = seg >= h
                y = ((c == 1) & (t <= h))[el]
                fh = f[el, col]
                r[f"c_{h}"] = c_index_uno(t[el], c[el], fh, tau=h)
                r[f"auc_{h}"] = auc(y, fh)
                r[f"brier_{h}"] = float(np.mean((fh - y) ** 2)) if el.any() else float("nan")
            r["ibs"] = self._ibs(t, c, seg, f)
            out[m] = r
        return out

    def _ibs(self, t, c, seg, f) -> float:
        grid = np.array([self.slots[i] for i in self.col_ibs])
        if len(grid) == 0:
            return float("nan")
        ok = seg >= grid.max()
        if not ok.any():
            return float("nan")
        y = ((c[ok, None] == 1) & (t[ok, None] <= grid[None, :])).astype("float64")
        return float(np.mean(np.mean((f[ok][:, self.col_ibs] - y) ** 2, axis=0)))

    def _metricas_torch(self, idx) -> Dict[str, Dict[str, float]]:
        torch = self.xp
        ix = torch.as_tensor(np.asarray(idx), dtype=torch.int64, device=self.dev)
        t, c, seg = self._T[ix], self._C[ix], self._SEG[ix]
        out: Dict[str, Dict[str, float]] = {}
        for m in self.modelos:
            f = self._F[m][ix]
            r: Dict[str, float] = {}
            for h in self.horizontes:
                col = self.slots.index(h)
                el = seg >= h
                te, ce, fh = t[el], c[el], f[el, col]
                y = (ce == 1) & (te <= h)
                caso = torch.nonzero(y)[:, 0]
                if len(caso):
                    ef = torch.where(ce == 2, torch.full_like(te, float("inf")), te)
                    num, den = _core_c(te, ef, caso, torch.ones_like(te), fh, torch, BLOQUE_TORCH)
                    r[f"c_{h}"] = num / den if den > 0 else float("nan")
                else:
                    r[f"c_{h}"] = float("nan")
                r[f"auc_{h}"] = _core_auc(y, fh, torch, BLOQUE_TORCH)
                r[f"brier_{h}"] = float(((fh - y.double()) ** 2).mean()) if len(te) else float("nan")
            grid = torch.as_tensor([self.slots[i] for i in self.col_ibs], dtype=torch.float64, device=self.dev)
            ok = seg >= grid.max()
            if bool(ok.any()):
                yy = ((c[ok, None] == 1) & (t[ok, None] <= grid[None, :])).double()
                r["ibs"] = float(((f[ok][:, self.col_ibs] - yy) ** 2).mean(dim=0).mean())
            else:
                r["ibs"] = float("nan")
            out[m] = r
        return out

    # -- bootstrap ---------------------------------------------------------------------------
    def bootstrap(self, n_boot: int = 1000, seed: int = 0,
                  pares: Sequence[Tuple[str, str]] = ()) -> Dict[str, Dict[str, Dict[str, float]]]:
        """95 % percentile intervals resampling episodes, with the SAME resamples for every model.

        Returns ``{modelo: {metrica: {punto, lo, hi}}}`` and, for each ``(a, b)`` of ``pares``,
        ``"__delta__a__b"`` entries with the paired difference ``a - b``.
        """
        rng = np.random.default_rng(seed)
        punto = self.metricas(np.arange(self.n))
        draws: Dict[str, Dict[str, List[float]]] = {m: {k: [] for k in self.claves} for m in self.modelos}
        for _ in range(n_boot):
            res = self.metricas(rng.integers(0, self.n, self.n))
            for m in self.modelos:
                for k in self.claves:
                    draws[m][k].append(res[m][k])
        out: Dict[str, Dict[str, Dict[str, float]]] = {}
        for m in self.modelos:
            out[m] = {k: _resumen(punto[m][k], np.array(draws[m][k])) for k in self.claves}
        for a, b in pares:
            if a in draws and b in draws:
                out[f"__delta__{a}__{b}"] = {
                    k: _resumen(punto[a][k] - punto[b][k], np.array(draws[a][k]) - np.array(draws[b][k]))
                    for k in self.claves}
        out["__n_boot"] = n_boot
        return out


def _resumen(punto: float, d: np.ndarray) -> Dict[str, float]:
    d = d[~np.isnan(d)]
    if len(d) == 0:
        return {"punto": float(punto), "lo": float("nan"), "hi": float("nan")}
    return {"punto": float(punto), "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5))}
