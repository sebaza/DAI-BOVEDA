"""Permanence blocks of the view "Lo que pasó": entry profile and first-semester failures versus who continued (T1, k = 1).

Both blocks read the T1 test frame of ``evaluation.vista_historica`` (one row per episode, ``y`` = 1 when the student did NOT
continue, ``p`` = predicted risk of the kept model). They are ASSOCIATIONS between a characteristic and continuing, not causes.

Every group is published with its exact ``n`` whatever its size (no size-based «otros» row); ``otros_cambio`` is a class of entry
route (change of program or other entries), not a size bucket. A group without students is not listed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

VIA = {"regular": "Ingreso regular", "especial": "Ingreso especial", "otros_cambio": "Cambio de carrera u otros ingresos"}
SIN_DATO = "Sin dato"
QUINTILES = ("Q1 (puntaje más bajo)", "Q2", "Q3", "Q4", "Q5 (puntaje más alto)")
REPROBACIONES = ("0", "1", "2", "3+")


def _pct(a: float, n: int) -> Optional[float]:
    return None if not n else float(a) / float(n)


def _publicar(filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"grupo": f["grupo"], "etiqueta": f["etiqueta"], "n": int(f["n"]),
             "pct_siguieron": _pct(f["siguieron"], f["n"]), "pct_esperado": _pct(f["esperados"], f["n"])} for f in filas]


def _grupos(d: pd.DataFrame, clave: pd.Series, etiquetas: Dict[str, str], orden: List[str]) -> List[Dict[str, Any]]:
    """One row per group of ``clave`` (``n``, ``siguieron``, ``esperados``) in ``orden``; unknown groups follow."""
    y, p = d["y"].to_numpy(dtype="float64"), d["p"].to_numpy(dtype="float64")
    k = clave.fillna("sin_dato").astype(str).to_numpy()
    vistos = orden + sorted(set(k) - set(orden))
    filas = []
    for g in vistos:
        m = k == g
        if m.any():
            filas.append({"grupo": g, "etiqueta": etiquetas.get(g, SIN_DATO if g == "sin_dato" else g), "n": int(m.sum()),
                          "siguieron": float((1.0 - y[m]).sum()), "esperados": float((1.0 - p[m]).sum())})
    return filas


# ------------------------------------------------------------------------------------------------ entry profile
def agregar_quintiles(d: pd.DataFrame) -> pd.DataFrame:
    """Adds ``puntaje_q`` ("q1".."q5", ``NaN`` without a score): quintiles of ``pct_ponderado`` of the frame given (the UCN)."""
    if "pct_ponderado" not in d:
        return d
    q = pd.qcut(d["pct_ponderado"].astype("float64"), 5, labels=False, duplicates="drop")
    return d.assign(puntaje_q=q.map(lambda v: None if pd.isna(v) else f"q{int(v) + 1}"))


def _grupo_colegio(t: Any) -> str:
    if not isinstance(t, str) or not t.strip():
        return "sin_dato"
    return {"H": "humanista", "T": "tecnico"}.get(t.strip()[0].upper(), "otro")


def bloque_perfil(d: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """``{n, nota_asociacion, dimensiones: [{dimension, filas}]}``; a dimension that cannot be published is left out."""
    n = int(len(d))
    if n == 0 or not {"y", "p"} <= set(d.columns):
        return None
    dims: List[Dict[str, Any]] = []
    candidatas = []
    if "via_clase" in d:
        via = d["via_clase"].replace({"otra": "otros_cambio"})          # the rare "otra" entry route is a class of entry: it maps to the other changes
        candidatas.append(("via", _grupos(d, via, VIA, list(VIA))))
    if "tipo_colegio" in d:
        etq = {"humanista": "Colegio científico-humanista", "tecnico": "Colegio técnico-profesional", "otro": "Otro tipo de colegio"}
        candidatas.append(("colegio", _grupos(d, d["tipo_colegio"].map(_grupo_colegio), etq, ["humanista", "tecnico", "otro"])))
    if "pct_ponderado" in d:
        d = d if "puntaje_q" in d else agregar_quintiles(d)
        etq = {f"q{i + 1}": e for i, e in enumerate(QUINTILES)}
        etq["sin_dato"] = "Sin puntaje de ingreso"
        candidatas.append(("puntaje", _grupos(d, d["puntaje_q"], etq, list(etq)[:-1])))
    for nombre, filas in candidatas:
        if filas:
            dims.append({"dimension": nombre, "filas": _publicar(filas)})
    return {"n": n, "nota_asociacion": True, "dimensiones": dims} if dims else None


# --------------------------------------------------------------------------------------------- first semester
def _bucket(r: Any) -> str:
    return "3+" if r >= 3 else str(int(r))


def bloque_primer_semestre(d: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """``{n, filas: [{reprobaciones, n, pct_siguieron}]}``: continuing by failures of the first semester (0, 1, 2, 3 or more)."""
    n = int(len(d))
    if n == 0 or not {"reprobados", "y", "p"} <= set(d.columns):
        return None
    d = d.loc[d["reprobados"].notna()]
    clave = d["reprobados"].map(_bucket)
    filas = [dict(f, reprobaciones=f["grupo"]) for f in _grupos(d, clave, {}, list(REPROBACIONES))]
    if not filas:
        return None
    return {"n": int(len(d)), "nota_asociacion": True,
            "filas": [{"reprobaciones": f["grupo"], "n": int(f["n"]), "pct_siguieron": _pct(f["siguieron"], f["n"])} for f in filas]}
