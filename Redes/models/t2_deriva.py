"""P55 ablation of T2 (stage B, docs/09_benchmark_t2.md): course statistics weighted toward the recent past.

The snapshot's course pass-rate statistics are expanding histories (every earlier period weighs the same). The pass rates
drift (a level shift in 2020-2022, D80), so the ablation recomputes the same statistics with an exponential decay in time
(half-life ``vida_media_anios``) or with a window of the last ``ventana_anios`` years, from the aggregate table of evaluated
attempts per (course, program of the episode, period). Only periods STRICTLY earlier than the period of the row count
(point in time). Aggregates only: no person key enters.

Time unit ``tt`` = quarters of a year (period suffix 10 = 0, 15 = 1, 20 = 2, 25 = 3), so a winter / summer period lies
between the two regular ones.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

COLUMNAS: List[str] = ["tasa_hist_curso", "n_hist_curso", "prom_hist_curso", "tasa_hist_curso_suav", "tasa_hist_curso_prog",
                       "n_hist_curso_prog", "tasa_hist_media_carga"]
_SUFIJO = {"10": 0, "15": 1, "20": 2, "25": 3}
PRIOR_SIN_HISTORIA = 0.8          # as in the expanding snapshot


def tiempo(periodo) -> int:
    p = str(periodo)
    return int(p[:4]) * 4 + _SUFIJO.get(p[4:6], 0)


def _acumulado(clave: np.ndarray, tt: np.ndarray, valores: np.ndarray) -> pd.DataFrame:
    """Per (key, tt): inclusive running sums of the columns of ``valores`` (2-D)."""
    d = pd.DataFrame(valores, columns=["n", "a", "s"])
    d["k"], d["t"] = clave, tt
    g = d.groupby(["k", "t"], sort=True).sum().reset_index().sort_values(["k", "t"], kind="stable")
    for c in ("n", "a", "s"):
        g[c] = g.groupby("k", sort=False)[c].cumsum()
    return g


def _previo(clave: np.ndarray, tt: np.ndarray, acum: pd.DataFrame) -> np.ndarray:
    """Running sums of the latest ``acum`` row of the same key with ``t`` STRICTLY smaller than ``tt`` (zeros if none)."""
    izq = pd.DataFrame({"k": clave, "t": tt, "i": np.arange(len(clave))}).sort_values("t", kind="stable")
    r = acum.sort_values("t", kind="stable")
    m = pd.merge_asof(izq, r, on="t", by="k", allow_exact_matches=False, direction="backward").sort_values("i")
    return m[["n", "a", "s"]].fillna(0.0).to_numpy("float64")


def _sumas(clave_t, tt_t, clave_e, tt_e, vals_e, modo, vida, ventana, u0):
    """Weighted sums (n, a, s) of the earlier periods for each row of T."""
    if modo == "decaimiento":
        esc = 2.0 ** ((tt_e - u0) / (4.0 * vida))                         # weight at t_T is 2 ** -((t_T - t_e) / (4 v))
        acum = _acumulado(clave_e, tt_e, vals_e * esc[:, None])
        return _previo(clave_t, tt_t, acum) * (2.0 ** (-(tt_t - u0) / (4.0 * vida)))[:, None]
    wq = int(round(ventana * 4))
    acum = _acumulado(clave_e, tt_e, vals_e)
    return _previo(clave_t, tt_t, acum) - _previo(clave_t, tt_t - wq + 1, acum)


def estadisticas_recientes(T: pd.DataFrame, tabla: pd.DataFrame, modo: str, vida_media_anios: float = 2.0,
                           ventana_anios: float = 3.0, m: float = 10.0) -> pd.DataFrame:
    """The ``COLUMNAS`` of every row of ``T`` (``codigo_asignatura``, ``cod_programa``, ``periodo``, ``episodio_id``) from
    ``tabla`` (``codigo_asignatura``, ``prog``, ``periodo``, ``n``, ``a``, ``s``: attempts, passes and sum of grades)."""
    if modo not in ("decaimiento", "ventana"):
        raise ValueError(modo)
    cod = pd.Index(pd.unique(pd.concat([tabla["codigo_asignatura"], T["codigo_asignatura"]])))
    prog = pd.Index(pd.unique(pd.concat([tabla["prog"].dropna(), T["cod_programa"].dropna()])))
    c_e, c_t = cod.get_indexer(tabla["codigo_asignatura"]).astype("int64"), cod.get_indexer(T["codigo_asignatura"]).astype("int64")
    p_e, p_t = prog.get_indexer(tabla["prog"]).astype("int64"), prog.get_indexer(T["cod_programa"]).astype("int64")
    tt_e = np.array([tiempo(p) for p in tabla["periodo"]], dtype="int64")
    tt_t = np.array([tiempo(p) for p in T["periodo"]], dtype="int64")
    u0 = float(min(tt_e.min(), tt_t.min()))
    vals = tabla[["n", "a", "s"]].to_numpy("float64")
    kw = dict(modo=modo, vida=vida_media_anios, ventana=ventana_anios, u0=u0)
    curso = _sumas(c_t, tt_t, c_e, tt_e, vals, **kw)
    glob = _sumas(np.zeros(len(T), "int64"), tt_t, np.zeros(len(tabla), "int64"), tt_e, vals, **kw)
    con_prog = p_e >= 0
    clave_ep = c_e[con_prog] * np.int64(100_003) + p_e[con_prog]
    clave_tp = np.where(p_t >= 0, c_t * np.int64(100_003) + p_t, -1)
    prg = _sumas(clave_tp, tt_t, clave_ep, tt_e[con_prog], vals[con_prog], **kw)
    prg[p_t < 0] = 0.0
    n, a, s = curso[:, 0], curso[:, 1], curso[:, 2]
    prior = np.where(glob[:, 0] > 0, glob[:, 1] / np.where(glob[:, 0] > 0, glob[:, 0], 1.0), PRIOR_SIN_HISTORIA)
    suav = (a + m * prior) / (n + m)
    out = pd.DataFrame(index=T.index)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["tasa_hist_curso"] = np.where(n > 1e-12, a / n, np.nan)
        out["prom_hist_curso"] = np.where(n > 1e-12, s / n, np.nan)
    out["n_hist_curso"] = np.where(n > 1e-12, n, 0.0)
    out["tasa_hist_curso_suav"] = suav
    out["n_hist_curso_prog"] = np.where(prg[:, 0] > 1e-12, prg[:, 0], 0.0)
    out["tasa_hist_curso_prog"] = (prg[:, 1] + m * suav) / (prg[:, 0] + m)
    out["tasa_hist_media_carga"] = out.groupby([T["episodio_id"].to_numpy(), T["periodo"].astype(str).to_numpy()])[
        "tasa_hist_curso_suav"].transform("mean")
    return out[COLUMNAS]
