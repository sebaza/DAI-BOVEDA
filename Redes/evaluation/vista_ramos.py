"""Course blocks of the view "Lo que pasó": which courses fail most, how many more than expected, which ones hold back the most
students and how failing varies along the curriculum.

Inputs are AGGREGATED attempts (one row per program x course, built in SQL / from the saved predictions of the kept T2 model
``cb_c_nuevas``): nothing at the level of a section, a NRC or a teacher ever reaches this module, so none can reach the output.
Only evaluated attempts count and the P58 periods 201920 and 202010 are left out of every failure count.

Every course (or department) with at least one attempt is listed whatever its size, with its exact counts; a rate over no attempts
is ``None``.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

VENTANA_DESDE, VENTANA_HASTA = "202110", "202520"          # last five complete years ending 202520
PERIODOS_P58 = ("201920", "202010")                        # not a failure count (P58)
VENTANAS_ESPERADO = {"prueba": ("202310", "202420"), "posterior": ("202510", "202520")}
SEMESTRES_MALLA = range(1, 13)
Z95 = 1.96


def _listable(intentos: Any) -> bool:
    """Listed course row: at least one attempt (the failures do not matter: a course nobody failed is still a figure)."""
    return intentos >= 1


def _por_curso(a: pd.DataFrame) -> pd.DataFrame:
    """Sum the aggregated rows (one per program) into one row per course."""
    base = a.groupby("codigo", sort=True).agg(nombre=("nombre", "first"), depto=("depto", "first"), intentos=("intentos", "sum"),
                                              reprobados=("reprobados", "sum")).reset_index()
    return base


def wilson(k: float, n: float) -> Tuple[float, float]:
    """95 % Wilson interval ``(lo, hi)`` of the proportion ``k / n`` (``n >= 1``)."""
    p = k / n
    z2 = Z95 * Z95
    centro = (p + z2 / (2 * n)) / (1 + z2 / n)
    mitad = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centro - mitad), min(1.0, centro + mitad)


# --------------------------------------------------------------------------------------------- most failed courses
def bloque_reprobados(a: pd.DataFrame, top: int = 15) -> Optional[Dict[str, Any]]:
    """``{desde, hasta, por_tasa, por_volumen}``: the courses with the highest failure rate and with the most failures.

    ``por_tasa`` is ordered by the lower bound of the 95 % Wilson interval of the rate (ties: more attempts), so a course with one
    attempt cannot outrank a course with a high rate over many; every course with at least one attempt stays eligible. Each row
    carries the rate, its attempts, failures and the interval ``lo`` / ``hi``."""
    if a.empty:
        return None
    c = _por_curso(a)
    c = c.loc[[_listable(i) for i in c["intentos"]]]
    if c.empty:
        return None
    c = c.assign(tasa=c["reprobados"] / c["intentos"])
    c = c.assign(lo=[wilson(r, i)[0] for r, i in zip(c["reprobados"], c["intentos"])], hi=[wilson(r, i)[1] for r, i in zip(c["reprobados"], c["intentos"])])

    def filas(d: pd.DataFrame) -> List[Dict[str, Any]]:
        return [{"codigo": str(r.codigo), "nombre": r.nombre, "depto": r.depto, "intentos": int(r.intentos),
                 "reprobados": int(r.reprobados), "tasa": float(r.tasa), "lo": round(float(r.lo), 4), "hi": round(float(r.hi), 4)}
                for r in d.head(top).itertuples()]

    return {"desde": VENTANA_DESDE, "hasta": VENTANA_HASTA,
            "por_tasa": filas(c.sort_values(["lo", "intentos", "codigo"], ascending=[False, False, True])),
            "por_volumen": filas(c.sort_values(["reprobados", "tasa", "codigo"], ascending=[False, False, True]))}


# ------------------------------------------------------------------------------------- failures versus expected
def _tabla_esperado(w: pd.DataFrame, clave: List[str], top: int) -> List[Dict[str, Any]]:
    g = w.groupby(clave, sort=True, dropna=True).agg(intentos=("intentos", "sum"), observados=("observados", "sum"),
                                                     esperados=("esperados", "sum"), varianza=("varianza", "sum")).reset_index()
    g = g.loc[[_listable(i) for i in g["intentos"]]]
    g = g.assign(diferencia=g["observados"] - g["esperados"])
    g = g.sort_values(["diferencia"] + clave, ascending=[False] + [True] * len(clave)).head(top)
    filas = []
    for r in g.to_dict("records"):
        mitad = Z95 * math.sqrt(max(float(r["varianza"]), 0.0))
        fila = {k: (str(r[k]) if k in ("codigo", "depto") else r[k]) for k in clave}
        fila.update({"intentos": int(r["intentos"]), "observados": int(r["observados"]), "esperados": round(float(r["esperados"]), 1),
                     "diferencia": round(float(r["diferencia"]), 1), "lo": round(float(r["diferencia"]) - mitad, 1),
                     "hi": round(float(r["diferencia"]) + mitad, 1)})
        filas.append(fila)
    return filas


def bloque_esperado(a: pd.DataFrame, top: int = 10) -> Optional[Dict[str, Any]]:
    """Courses and departments that failed more than the kept model expected, by window (``ventana``: prueba / posterior).

    ``a`` has one row per window x program x course with ``intentos``, ``observados`` (failures), ``esperados`` (sum of p) and
    ``varianza`` (sum of p (1 - p)). The interval is ``diferencia`` +/- 1.96 sqrt(variance)."""
    ventanas: Dict[str, Any] = {}
    for nombre, (desde, hasta) in VENTANAS_ESPERADO.items():
        w = a.loc[a["ventana"] == nombre]
        if w.empty:
            continue
        ramos = _tabla_esperado(w.assign(codigo=w["codigo"].astype(str)), ["codigo", "nombre"], top)
        w2 = w.loc[w["depto"].notna()].assign(depto_desc=lambda x: x["depto_desc"].fillna(x["depto"]))
        deptos = _tabla_esperado(w2, ["depto", "depto_desc"], top) if len(w2) else []
        if ramos or deptos:
            ventanas[nombre] = {"desde": desde, "hasta": hasta, "ramos": ramos, "deptos": deptos}
    return {"ventanas": ventanas} if ventanas else None


# ------------------------------------------------------------------------------------------------ bottlenecks
def dependientes(prerreq: pd.DataFrame) -> Dict[str, int]:
    """Descendants of every course in the prerequisite graph (union of the edges of every catalog, each course counted once).

    ``prerreq`` has ``codigo_requisito`` and ``codigo_asignatura``; the edge goes from the requirement to the course that needs it."""
    hijos: Dict[str, set] = {}
    for req, asig in zip(prerreq["codigo_requisito"], prerreq["codigo_asignatura"]):
        if isinstance(req, str) and isinstance(asig, str) and req != asig:
            hijos.setdefault(req, set()).add(asig)
    out: Dict[str, int] = {}
    for raiz in hijos:
        vistos, pila = set(), [raiz]
        while pila:
            for h in hijos.get(pila.pop(), ()):
                if h not in vistos and h != raiz:
                    vistos.add(h)
                    pila.append(h)
        out[raiz] = len(vistos)
    return out


def bloque_cuellos(a: pd.DataFrame, prerreq: pd.DataFrame, top: int = 15, deps: Optional[Mapping[str, int]] = None) -> Optional[Dict[str, Any]]:
    """Courses ranked by ``impacto = reprobados x dependientes`` (failures times the courses that need it, directly or not)."""
    if a.empty or prerreq is None or prerreq.empty:
        return None
    deps = deps if deps is not None else dependientes(prerreq)
    c = _por_curso(a)
    c = c.loc[[_listable(i) for i in c["intentos"]]]
    c = c.assign(dependientes=c["codigo"].map(lambda k: deps.get(str(k), 0)))
    c = c.loc[c["dependientes"] > 0]
    if c.empty:
        return None
    c = c.assign(impacto=c["reprobados"] * c["dependientes"]).sort_values(["impacto", "codigo"], ascending=[False, True]).head(top)
    return {"filas": [{"codigo": str(r.codigo), "nombre": r.nombre, "reprobados": int(r.reprobados),
                       "dependientes": int(r.dependientes), "impacto": int(r.impacto)} for r in c.itertuples()]}


# --------------------------------------------------------------------------------------------- along the curriculum
def bloque_semestre_malla(a: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Failure rate by the semester of the curriculum in which the course sits (1-12), with exact counts; a semester without
    attempts has no rate."""
    if a.empty or "semestre" not in a:
        return None
    g = a.loc[a["semestre"].isin(list(SEMESTRES_MALLA))].groupby("semestre")[["intentos", "reprobados"]].sum()
    filas = []
    for s in SEMESTRES_MALLA:
        if s not in g.index:
            continue
        i, r = int(g.at[s, "intentos"]), int(g.at[s, "reprobados"])
        filas.append({"semestre": int(s), "intentos": i, "reprobados": r, "tasa": r / i if i else None})
    return {"filas": filas} if filas else None


# --------------------------------------------------------------------------------------------------- preparation
def preparar_esperado(snap: pd.DataFrame, preds: Mapping[str, Mapping[str, np.ndarray]], modelo: str,
                      nombres: pd.DataFrame) -> pd.DataFrame:
    """Aggregates the T2 snapshot rows of each window with the saved predictions of ``modelo`` (joined by ``intento_id``).

    ``snap``: ``intento_id, cod_programa, codigo_asignatura, depto, periodo, y``; ``preds``: window -> ``{intento_id, modelo}``;
    ``nombres``: ``codigo, nombre, depto, depto_desc`` (one row per course). Returns ``ventana, cod_programa, codigo, nombre, depto, depto_desc,
    intentos, observados, esperados, varianza`` (no section / teacher column exists in the inputs)."""
    partes = []
    for ventana, (desde, hasta) in VENTANAS_ESPERADO.items():
        z = preds.get(ventana)
        if z is None:
            continue
        p = pd.Series(np.asarray(z[modelo], dtype="float64"), index=np.asarray(z["intento_id"]))
        s = snap.loc[snap["periodo"].between(desde, hasta) & snap["intento_id"].isin(p.index)].copy()
        s["p"] = p.reindex(s["intento_id"]).to_numpy()
        s["var"] = s["p"] * (1.0 - s["p"])
        g = s.groupby(["cod_programa", "codigo_asignatura"]).agg(
            intentos=("y", "size"), observados=("y", "sum"), esperados=("p", "sum"), varianza=("var", "sum")).reset_index()
        partes.append(g.assign(ventana=ventana))
    cols = ["ventana", "cod_programa", "codigo", "nombre", "depto", "depto_desc", "intentos", "observados", "esperados", "varianza"]
    if not partes:
        return pd.DataFrame(columns=cols)
    d = pd.concat(partes, ignore_index=True).rename(columns={"codigo_asignatura": "codigo"})
    d = d.merge(nombres[["codigo", "nombre", "depto", "depto_desc"]].drop_duplicates("codigo"), on="codigo", how="left")
    d["nombre"] = d["nombre"].fillna(d["codigo"].astype(str))
    return d[cols]
