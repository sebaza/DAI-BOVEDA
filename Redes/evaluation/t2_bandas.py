"""T2 grade-band model (P74 / P84, stage B): metrics of the four-band multiclass forecast and its AGGREGATED forecasts by
group (programa, facultad).

Bands (``rules_t2.BANDAS``): reprobado, unanimidad, distincion, maxima_distincion (the institutional recognition scale).
Metrics: log-loss, multiclass Brier and the one-vs-rest AP of each band against the frequency baseline (the class
distribution of train), with a bootstrap GROUPED BY PERSON (each replicate draws person weights; one draw is shared by every
model, so paired differences are valid).

Aggregated forecasts are not individual ones: a group's expected share of each band is the mean predicted probability.
Suppression: a group with fewer than ``N_SUPRIMIR`` attempts leaves no trace except in the counts; a group with fewer than
``N_MIN`` is only counted; a listed group shows the share of a band only when the group has at least ``EVENTOS_MIN``
attempts in that band.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score

from evaluation.metrics_t2 import Ordenado
from pipelines.snapshots import rules_t2 as R2

CLASES = R2.BANDAS
N_SUPRIMIR = 10
N_MIN = 100
EVENTOS_MIN = 10
TOP = 5


def y_banda(df: pd.DataFrame) -> np.ndarray:
    idx = {c: i for i, c in enumerate(CLASES)}
    return df["banda_nota"].map(idx).astype("int64").to_numpy()


def frecuencias(y_train: np.ndarray, n: int) -> np.ndarray:
    """Frequency baseline: the class distribution of the training rows, repeated ``n`` times."""
    f = np.bincount(np.asarray(y_train), minlength=len(CLASES)) / len(y_train)
    return np.tile(f, (n, 1))


def _norm(P: np.ndarray) -> np.ndarray:
    P = np.clip(np.asarray(P, dtype="float64"), 1e-12, 1.0)
    return P / P.sum(axis=1, keepdims=True)


# ---------------------------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------------------------
def metricas(y: np.ndarray, P: np.ndarray, w: Optional[np.ndarray] = None, orden: Optional[List[Ordenado]] = None,
             eventos_min: int = EVENTOS_MIN) -> Dict[str, float]:
    """Log-loss, multiclass Brier and per-band AP (NaN when the band has fewer than ``eventos_min`` rows) and their macro mean."""
    y = np.asarray(y)
    P = _norm(P)
    n = len(y)
    w = np.ones(n) if w is None else w
    sw = w.sum()
    pk = P[np.arange(n), y]
    onehot = np.zeros_like(P)
    onehot[np.arange(n), y] = 1.0
    out = {"logloss": float(-(w * np.log(pk)).sum() / sw), "brier_mc": float((w * ((P - onehot) ** 2).sum(axis=1)).sum() / sw)}
    aps = []
    for j, c in enumerate(CLASES):
        yj = onehot[:, j]
        if (yj > 0).sum() < eventos_min or (yj > 0).all():
            out[f"ap_{c}"] = float("nan")
            continue
        o = orden[j] if orden is not None else Ordenado(yj, P[:, j])
        out[f"ap_{c}"] = o.ap_auc(w)[0]
        aps.append(out[f"ap_{c}"])
    out["ap_macro"] = float(np.mean(aps)) if aps else float("nan")
    return out


def _pct(x: np.ndarray) -> Tuple[float, float]:
    x = x[~np.isnan(x)]
    return (float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))) if len(x) else (float("nan"), float("nan"))


def _pesos_persona(codigos: np.ndarray, n_personas: int, rng) -> np.ndarray:
    """Row weights of one person-level bootstrap replicate (multinomial counts of persons)."""
    return rng.multinomial(n_personas, np.full(n_personas, 1.0 / n_personas)).astype("float64")[codigos]


def bootstrap(y: np.ndarray, probas: Mapping[str, np.ndarray], persona: Sequence, n_boot: int = 300, seed: int = 0,
              pares: Sequence[Tuple[str, str]] = ()) -> Dict[str, Dict[str, Dict[str, float]]]:
    """``{modelo: {metrica: {punto, lo, hi}}}`` and ``"a__vs__b"`` paired differences, resampling persons."""
    y = np.asarray(y)
    codigos, uniq = pd.factorize(pd.Series(persona).astype(str))
    npers = len(uniq)
    nombres = list(probas)
    P = {m: _norm(probas[m]) for m in nombres}
    ordenes = {m: [Ordenado((y == j).astype("float64"), P[m][:, j]) for j in range(len(CLASES))] for m in nombres}
    punto = {m: metricas(y, P[m], None, ordenes[m]) for m in nombres}
    claves = list(punto[nombres[0]])
    draws = {m: {k: np.empty(n_boot) for k in claves} for m in nombres}
    rng = np.random.default_rng(seed)
    for b in range(n_boot):
        w = _pesos_persona(codigos, npers, rng)
        for m in nombres:
            r = metricas(y, P[m], w, ordenes[m])
            for k in claves:
                draws[m][k][b] = r[k]
    out: Dict = {}
    for m in nombres:
        out[m] = {k: dict(zip(("lo", "hi"), _pct(draws[m][k])), punto=punto[m][k]) for k in claves}
    for a, bn in pares:
        if a in punto and bn in punto:
            out[f"{a}__vs__{bn}"] = {k: dict(zip(("lo", "hi"), _pct(draws[a][k] - draws[bn][k])), punto=punto[a][k] - punto[bn][k])
                                     for k in claves}
    return out


# ---------------------------------------------------------------------------------------------
# aggregated forecasts by group
# ---------------------------------------------------------------------------------------------
def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 3 or np.ptp(a[ok]) == 0 or np.ptp(b[ok]) == 0:
        return float("nan")
    return float(spearmanr(a[ok], b[ok]).correlation)


def tabla_grupos(grupo: np.ndarray, y: np.ndarray, P: np.ndarray, P_base: np.ndarray, persona: Sequence, n_boot: int = 500,
                 seed: int = 0, n_min: int = N_MIN, n_suprimir: int = N_SUPRIMIR, eventos_min: int = EVENTOS_MIN) -> Dict:
    """Group table of one level: for every listed group (n >= ``n_min``) the observed and predicted share of each band, the
    gap (predicted - observed) of the model and of the baseline with 95 % intervals, and the per-band AP (point). A band cell
    is ``None`` when the group has fewer than ``eventos_min`` attempts in the band. ``resumen`` counts the groups by size
    (never naming a group under ``n_min``), the weighted mean absolute gap of model and baseline per band and the Spearman
    correlation between predicted and observed shares."""
    y = np.asarray(y)
    P, P_base = _norm(P), _norm(P_base)
    g = pd.Series(grupo, dtype="object")
    g = g.where(g.notna(), "sin_dato").astype(str)
    cod, nombres = pd.factorize(g)
    G, nC = len(nombres), len(CLASES)
    n_g = np.bincount(cod, minlength=G)
    listado = np.flatnonzero(n_g >= n_min)
    onehot = np.zeros((len(y), nC))
    onehot[np.arange(len(y)), y] = 1.0
    ev = np.stack([np.bincount(cod, weights=onehot[:, j], minlength=G) for j in range(nC)], axis=1)     # (G, C)
    celda = ev >= eventos_min
    pcod, puniq = pd.factorize(pd.Series(persona).astype(str))

    def medias(w):
        n = np.bincount(cod, weights=w, minlength=G)
        with np.errstate(invalid="ignore", divide="ignore"):
            obs = np.stack([np.bincount(cod, weights=w * onehot[:, j], minlength=G) / n for j in range(nC)], axis=1)
            mod = np.stack([np.bincount(cod, weights=w * P[:, j], minlength=G) / n for j in range(nC)], axis=1)
            bas = np.stack([np.bincount(cod, weights=w * P_base[:, j], minlength=G) / n for j in range(nC)], axis=1)
        return n, obs, mod, bas

    n0, obs0, mod0, bas0 = medias(np.ones(len(y)))
    rng = np.random.default_rng(seed)
    D_n, D_o, D_m, D_b = [], [], [], []
    for _ in range(n_boot):
        n_, o_, m_, b_ = medias(_pesos_persona(pcod, len(puniq), rng))
        D_n.append(n_[listado]), D_o.append(o_[listado]), D_m.append(m_[listado]), D_b.append(b_[listado])
    D_n, D_o, D_m, D_b = (np.array(a) for a in (D_n, D_o, D_m, D_b))
    filas = []
    for j_, gi in enumerate(listado):
        fila: Dict = {"grupo": str(nombres[gi]), "n": int(n_g[gi]), "bandas": {}}
        sel = cod == gi
        for c, nombre in enumerate(CLASES):
            if not celda[gi, c]:
                fila["bandas"][nombre] = {"observada": None, "predicha": None, "brecha": None, "brecha_base": None, "ap": None}
                continue
            cel: Dict = {}
            for clave, punto, serie in (("observada", obs0[gi, c], D_o[:, j_, c]), ("predicha", mod0[gi, c], D_m[:, j_, c]),
                                        ("base", bas0[gi, c], D_b[:, j_, c])):
                lo, hi = _pct(serie)
                cel[clave] = {"punto": float(punto), "lo": lo, "hi": hi}
            for clave, punto, serie in (("brecha", mod0[gi, c] - obs0[gi, c], D_m[:, j_, c] - D_o[:, j_, c]),
                                        ("brecha_base", bas0[gi, c] - obs0[gi, c], D_b[:, j_, c] - D_o[:, j_, c])):
                lo, hi = _pct(serie)
                cel[clave] = {"punto": float(punto), "lo": lo, "hi": hi}
            yj = onehot[sel, c]
            cel["ap"] = float(average_precision_score(yj, P[sel, c])) if 0 < yj.sum() < len(yj) else None
            fila["bandas"][nombre] = cel
        filas.append(fila)
    resumen: Dict = {"grupos_total": int(G), "grupos_listados": int(len(listado)), "grupos_100_o_mas": int(len(listado)),
                     "grupos_10_a_99": int(((n_g >= n_suprimir) & (n_g < n_min)).sum()), "grupos_menos_10": int((n_g < n_suprimir).sum()),
                     "filas_total": int(len(y)), "filas_en_listados": int(n_g[listado].sum()), "n_min": n_min,
                     "n_suprimir": n_suprimir, "eventos_min": eventos_min, "mae_modelo": {}, "mae_base": {}, "spearman": {}, "ranking": {}}
    for c, nombre in enumerate(CLASES):
        ok = celda[listado, c]
        if ok.sum() < 3:
            continue
        idx = listado[ok]
        w = n_g[idx] / n_g[idx].sum()
        wd = D_n[:, ok] / D_n[:, ok].sum(axis=1, keepdims=True)
        for clave, punto, serie in (("mae_modelo", np.sum(w * np.abs(mod0[idx, c] - obs0[idx, c])),
                                     np.sum(wd * np.abs(D_m[:, ok, c] - D_o[:, ok, c]), axis=1)),
                                    ("mae_base", np.sum(w * np.abs(bas0[idx, c] - obs0[idx, c])),
                                     np.sum(wd * np.abs(D_b[:, ok, c] - D_o[:, ok, c]), axis=1))):
            lo, hi = _pct(serie)
            resumen[clave][nombre] = {"punto": float(punto), "lo": lo, "hi": hi}
        sp = np.array([_spearman(D_m[i, ok, c], D_o[i, ok, c]) for i in range(len(D_o))])
        lo, hi = _pct(sp)
        resumen["spearman"][nombre] = {"punto": _spearman(mod0[idx, c], obs0[idx, c]), "lo": lo, "hi": hi}
        top = min(TOP, len(idx) // 2) if len(idx) >= 2 else len(idx)
        por_obs, por_pred = idx[np.argsort(-obs0[idx, c])], idx[np.argsort(-mod0[idx, c])]
        resumen["ranking"][nombre] = {"top_observado": [str(nombres[i]) for i in por_obs[:top]],
                                      "bottom_observado": [str(nombres[i]) for i in por_obs[::-1][:top]],
                                      "top_predicho": [str(nombres[i]) for i in por_pred[:top]],
                                      "bottom_predicho": [str(nombres[i]) for i in por_pred[::-1][:top]], "tamano": top}
    return {"filas": sorted(filas, key=lambda r: r["grupo"]), "resumen": resumen}
