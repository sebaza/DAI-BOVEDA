"""Metrics of T6 ("matricula en postgrado UCN despues del egreso", docs/12_benchmark_t6.md).

* Cumulative incidence = ``1 - Kaplan-Meier`` of the single event (no competing event is modelled: an exit from the
  university does not stop a person from enrolling in a UCN postgrado later), with 95 % percentile intervals from the
  bootstrap GROUPED BY PERSON of ``metrics_t45.remuestreos``.
* Horizon metrics (AP, ROC-AUC, Brier, ECE, ...) use only the units followed up to the horizon, for which the censoring
  weight is exactly 1 (the censoring is administrative: it depends only on the semester of egreso).
* Group tables follow D61: a group is reported only with at least ``N_MIN`` units and ``EVENTOS_MIN`` events; the others
  are suppressed and only counted.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from pipelines.snapshots import rules_t6 as R6

from . import grupos_t45 as GR
from . import metrics as M
from . import metrics_t3 as M3
from . import metrics_t45 as M45

N_MIN = GR.N_MIN
EVENTOS_MIN = GR.EVENTOS_MIN


# ---------------------------------------------------------------------------------------------
# cumulative incidence
# ---------------------------------------------------------------------------------------------
def incidencia_acumulada(tiempo, evento, taus: Sequence[int]) -> np.ndarray:
    """``1 - KM`` of the event at the semesters ``taus`` (zeros when nobody has the event)."""
    t = np.asarray(tiempo, dtype="float64")
    e = np.asarray(evento).astype("int64")
    if len(t) == 0:
        return np.full(len(taus), np.nan)
    return M3.aalen_johansen(t, e, np.asarray(taus, dtype="float64"))["F1"]


def incidencia_con_ic(tiempo, evento, taus: Sequence[int], idxs: Sequence[np.ndarray]) -> Dict[int, Dict[str, float]]:
    """Point estimate and 95 % interval of the cumulative incidence at each ``tau`` (grouped bootstrap ``idxs``)."""
    t, e = np.asarray(tiempo), np.asarray(evento)
    punto = incidencia_acumulada(t, e, taus)
    draws = np.array([incidencia_acumulada(t[i], e[i], taus) for i in idxs]) if len(idxs) else np.empty((0, len(taus)))
    out: Dict[int, Dict[str, float]] = {}
    for j, tau in enumerate(taus):
        lo, hi = M45._pct(draws[:, j]) if len(draws) else (float("nan"), float("nan"))
        out[int(tau)] = {"punto": float(punto[j]), "lo": lo, "hi": hi}
    return out


def tabla_incidencia_grupos(grupo, tiempo, evento, taus: Sequence[int], idxs: Sequence[np.ndarray],
                            n_min: int = N_MIN, eventos_min: int = EVENTOS_MIN, seguimiento=None) -> Dict:
    """Observed cumulative incidence of each reportable group; suppressed groups are only counted.

    With ``seguimiento`` each row also carries ``en_riesgo``: the units of the group followed up to each ``tau`` (the
    incidence at a ``tau`` beyond the follow-up of most of the group is a plateau, not an estimate).
    """
    t, e = np.asarray(tiempo), np.asarray(evento)
    seg = None if seguimiento is None else np.asarray(seguimiento)
    codigos, nombres, n, ev, rep = GR.clasificar_grupos(np.asarray(grupo), e, n_min, eventos_min)
    filas: List[Dict] = []
    for gi in np.flatnonzero(rep):
        filas_g = np.flatnonzero(codigos == gi)
        sub = [i[codigos[i] == gi] for i in idxs]
        sub = [s for s in sub if len(s)]
        fila = {"grupo": str(nombres[gi]), "n": int(n[gi]), "eventos": int(ev[gi]),
                "incidencia": incidencia_con_ic(t[filas_g], e[filas_g], taus, [np.searchsorted(filas_g, s) for s in sub])}
        if seg is not None:
            fila["en_riesgo"] = {int(tau): int((seg[filas_g] >= tau).sum()) for tau in taus}
        filas.append(fila)
    resumen: Dict = {"grupos_total": int(len(nombres)), "grupos_reportables": int(rep.sum()),
                     "grupos_suprimidos": int((~rep).sum()), "filas_total": int(len(t)),
                     "filas_en_reportables": int(n[rep].sum()), "eventos_total": int(ev.sum()),
                     "eventos_en_reportables": int(ev[rep].sum()), "n_min": n_min, "eventos_min": eventos_min}
    if filas:
        ult = int(taus[-1])
        orden = sorted(filas, key=lambda r: -r["incidencia"][ult]["punto"])
        top = min(GR.TOP, len(filas) // 2) if len(filas) >= 2 else len(filas)
        resumen["ranking"] = {"tau": ult, "superior": [r["grupo"] for r in orden[:top]],
                              "inferior": [r["grupo"] for r in orden[::-1][:top]], "tamano": top}
    return {"filas": sorted(filas, key=lambda r: r["grupo"]), "resumen": resumen}


# ---------------------------------------------------------------------------------------------
# horizon metrics
# ---------------------------------------------------------------------------------------------
def evaluar_horizonte(tiempo, evento, seguimiento, scores: Mapping[str, np.ndarray], tau: int, personas,
                      n_boot: int = 1000, pares: Sequence[Tuple[str, str]] = (), seed: int = 7) -> Dict:
    """Binary metrics at the horizon ``tau`` among the units followed up to it, with the person-grouped bootstrap and the
    paired differences ``a - b`` of ``pares``. ``scores[m]`` is the predicted cumulative incidence at ``tau`` of every unit."""
    el, y = R6.resultado_horizonte(tiempo, evento, seguimiento, tau)
    y = y[el].astype("int64")
    out: Dict = {"tau": int(tau), "n": int(el.sum()), "eventos": int(y.sum()),
                 "tasa": float(y.mean()) if len(y) else float("nan"),
                 "conclusivo": bool(y.sum() >= R6.MIN_EVENTOS_CLASICO and (len(y) - y.sum()) >= R6.MIN_EVENTOS_CLASICO),
                 "modelos": {}, "pares": {}}
    if len(y) == 0 or y.min() == y.max():
        return out
    idxs = M45.remuestreos(np.asarray(personas)[el], n_boot, seed=seed)
    ev = M45.bootstrap_agrupado(y, {m: np.asarray(s)[el] for m, s in scores.items()}, idxs, pares)
    for k, v in ev.items():
        (out["pares"] if "__vs__" in k else out["modelos"])[k] = v
    return out


def calibracion_horizonte(tiempo, evento, seguimiento, f_tau, tau: int, bins: int = 10) -> List[Dict[str, float]]:
    """Predicted vs observed incidence by (approximately) equal-count deciles among the units followed up to ``tau``."""
    el, y = R6.resultado_horizonte(tiempo, evento, seguimiento, tau)
    return M.tabla_confiabilidad(y[el].astype("float64"), np.asarray(f_tau, dtype="float64")[el], bins)


def agrupar_calibracion(tabla: List[Dict[str, float]], eventos_min: int = EVENTOS_MIN) -> List[Dict[str, float]]:
    """Merge the adjacent bins of a reliability table, from the highest risk down, until each one has at least
    ``eventos_min`` observed events (the last bin is merged into the previous one if it falls short). A table with fewer
    events than ``eventos_min`` becomes a single bin. No bin of 1 to ``eventos_min - 1`` events is ever reported."""
    bins = sorted(tabla, key=lambda f: -f["riesgo_medio"])
    out: List[Dict[str, float]] = []
    n = ev = 0
    riesgo = 0.0
    for f in bins:
        n += f["n"]
        ev += f["tasa_observada"] * f["n"]
        riesgo += f["riesgo_medio"] * f["n"]
        if round(ev) >= eventos_min:
            out.append({"n": int(n), "riesgo_medio": riesgo / n, "tasa_observada": ev / n})
            n = ev = 0
            riesgo = 0.0
    if n:
        if out:
            a = out[-1]
            tot = a["n"] + n
            out[-1] = {"n": int(tot), "riesgo_medio": (a["riesgo_medio"] * a["n"] + riesgo) / tot,
                       "tasa_observada": (a["tasa_observada"] * a["n"] + ev) / tot}
        else:
            out.append({"n": int(n), "riesgo_medio": riesgo / n, "tasa_observada": ev / n})
    for i, f in enumerate(out):
        f["grupo"] = i + 1
    return out
