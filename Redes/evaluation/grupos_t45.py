"""Aggregate forecasts by group (programa, facultad) for T4 / T5: reportability, calibration of the group rate, ranking.

These are AGGREGATE forecasts (the expected rate of a group), not individual ones. A group is reported only when it has
at least ``N_MIN`` rows AND at least ``EVENTOS_MIN`` events in the evaluated split; the others are suppressed and only
counted (how many groups, how many rows). Every reported rate has a 95 % interval from the person-grouped bootstrap.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import metrics as M
from .metrics_t45 import _pct

N_MIN = 100
EVENTOS_MIN = 10
TOP = 10


def es_reportable(n: int, eventos: int, n_min: int = N_MIN, eventos_min: int = EVENTOS_MIN) -> bool:
    return n >= n_min and eventos >= eventos_min


def clasificar_grupos(grupo: np.ndarray, y: np.ndarray, n_min: int = N_MIN, eventos_min: int = EVENTOS_MIN):
    """``(codigos, nombres, n, eventos, reportable)`` of the groups of ``grupo`` (missing values form their own group)."""
    g = pd.Series(grupo, dtype="object").where(pd.Series(grupo).notna(), "sin_dato").astype(str)
    codigos, nombres = pd.factorize(g)
    n = np.bincount(codigos, minlength=len(nombres))
    ev = np.bincount(codigos, weights=np.asarray(y, dtype="float64"), minlength=len(nombres)).astype(int)
    rep = np.array([es_reportable(int(a), int(b), n_min, eventos_min) for a, b in zip(n, ev)])
    return codigos, np.asarray(nombres), n, ev, rep


def _tasas(codigos, y, p, idx, n_grupos):
    """Observed and predicted mean per group for the resample ``idx`` (NaN for an empty group)."""
    c = codigos[idx]
    n = np.bincount(c, minlength=n_grupos).astype("float64")
    with np.errstate(invalid="ignore", divide="ignore"):
        obs = np.bincount(c, weights=y[idx], minlength=n_grupos) / n
        pred = np.bincount(c, weights=p[idx], minlength=n_grupos) / n
    return n, obs, pred


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 3 or np.ptp(a[ok]) == 0 or np.ptp(b[ok]) == 0:
        return float("nan")
    return float(spearmanr(a[ok], b[ok]).correlation)


def tabla_agregada(grupo: np.ndarray, y: np.ndarray, p_modelo: np.ndarray, p_base: np.ndarray,
                   idxs: Sequence[np.ndarray], n_min: int = N_MIN, eventos_min: int = EVENTOS_MIN) -> Dict:
    """Group table of one level.

    ``filas``: for each reportable group, ``n``, ``eventos``, the observed rate, the mean predicted risk and the gap
    (predicted - observed) of the model and of the baseline, each with an interval, and the per-group AP / ROC-AUC (point
    estimates). ``resumen``: group counts and coverage, the n-weighted mean absolute gap of the model and of the baseline
    (and its difference) and the Spearman correlation between predicted and observed rates, with intervals.
    """
    y = np.asarray(y, dtype="float64")
    p_modelo, p_base = np.asarray(p_modelo, dtype="float64"), np.asarray(p_base, dtype="float64")
    codigos, nombres, n, ev, rep = clasificar_grupos(grupo, y, n_min, eventos_min)
    G = len(nombres)
    todos = np.arange(len(y))
    n0, obs0, pred0 = _tasas(codigos, y, p_modelo, todos, G)
    _, _, base0 = _tasas(codigos, y, p_base, todos, G)
    sel = np.flatnonzero(rep)
    d_obs, d_pred, d_base, d_n = [], [], [], []
    for idx in idxs:
        nb, ob, pb = _tasas(codigos, y, p_modelo, idx, G)
        _, _, bb = _tasas(codigos, y, p_base, idx, G)
        d_n.append(nb[sel]), d_obs.append(ob[sel]), d_pred.append(pb[sel]), d_base.append(bb[sel])
    d_n, d_obs, d_pred, d_base = (np.array(a) for a in (d_n, d_obs, d_pred, d_base))
    filas: List[Dict] = []
    for j, gi in enumerate(sel):
        m = codigos == gi
        yg = y[m]
        ap = auc = float("nan")
        if yg.min() != yg.max():
            mm = M.metricas(yg.astype(int), p_modelo[m])
            ap, auc = mm["ap"], mm["roc_auc"]
        fila = {"grupo": str(nombres[gi]), "n": int(n[gi]), "eventos": int(ev[gi]), "ap": ap, "roc_auc": auc}
        for nombre, punto, serie in (("tasa_observada", obs0[gi], d_obs[:, j]), ("riesgo_medio", pred0[gi], d_pred[:, j]),
                                     ("riesgo_medio_base", base0[gi], d_base[:, j])):
            lo, hi = _pct(serie)
            fila[nombre] = {"punto": float(punto), "lo": lo, "hi": hi}
        for nombre, serie_p, punto_p in (("brecha", d_pred, pred0[gi]), ("brecha_base", d_base, base0[gi])):
            lo, hi = _pct(serie_p[:, j] - d_obs[:, j])
            fila[nombre] = {"punto": float(punto_p - obs0[gi]), "lo": lo, "hi": hi}
        filas.append(fila)
    resumen: Dict = {"grupos_total": int(G), "grupos_reportables": int(rep.sum()), "grupos_suprimidos": int((~rep).sum()),
                     "filas_total": int(len(y)), "filas_en_reportables": int(n[rep].sum()),
                     "eventos_total": int(ev.sum()), "eventos_en_reportables": int(ev[rep].sum()),
                     "n_min": n_min, "eventos_min": eventos_min}
    if len(sel):
        w = n[sel] / n[sel].sum()
        mae = float(np.sum(w * np.abs(pred0[sel] - obs0[sel])))
        mae_b = float(np.sum(w * np.abs(base0[sel] - obs0[sel])))
        wd = d_n / d_n.sum(axis=1, keepdims=True)
        mae_d = np.sum(wd * np.abs(d_pred - d_obs), axis=1)
        mae_bd = np.sum(wd * np.abs(d_base - d_obs), axis=1)
        sp_d = np.array([_spearman(d_pred[i], d_obs[i]) for i in range(len(d_obs))])
        spb_d = np.array([_spearman(d_base[i], d_obs[i]) for i in range(len(d_obs))])
        for nombre, punto, serie in (("mae_modelo", mae, mae_d), ("mae_base", mae_b, mae_bd), ("mae_modelo_menos_base", mae - mae_b, mae_d - mae_bd),
                                     ("spearman_modelo", _spearman(pred0[sel], obs0[sel]), sp_d),
                                     ("spearman_base", _spearman(base0[sel], obs0[sel]), spb_d)):
            lo, hi = _pct(serie)
            resumen[nombre] = {"punto": float(punto), "lo": lo, "hi": hi}
        # pooled rate: a consistency check (the mean predicted risk of the reportable rows against the observed rate)
        resumen["tasa_observada_global"] = float(y[rep[codigos]].mean())
        resumen["riesgo_medio_global"] = float(p_modelo[rep[codigos]].mean())
        # rankings (the groups are reportable, so no suppressed group appears)
        orden_obs = sorted(filas, key=lambda r: -r["tasa_observada"]["punto"])
        orden_pred = sorted(filas, key=lambda r: -r["riesgo_medio"]["punto"])
        top = min(TOP, len(filas) // 2) if len(filas) >= 2 else len(filas)
        resumen["ranking"] = {"top_observado": [r["grupo"] for r in orden_obs[:top]],
                              "bottom_observado": [r["grupo"] for r in orden_obs[::-1][:top]],
                              "top_predicho": [r["grupo"] for r in orden_pred[:top]],
                              "bottom_predicho": [r["grupo"] for r in orden_pred[::-1][:top]],
                              "tamano": top}
        k_top = min(5, len(filas))
        resumen["coincidencia_top"] = {"k": k_top, "n": len({r["grupo"] for r in orden_obs[:k_top]} & {r["grupo"] for r in orden_pred[:k_top]})}
    return {"filas": sorted(filas, key=lambda r: r["grupo"]), "resumen": resumen}
