"""The model behind each block of the views "Lo que pasó" and "Lo que viene" (plan 2026-11-18, Task 8).

Every block, and every cohort of a projection block, says which model produced it. The object is built here, once, from the registry
of kept models (``evaluation.modelos_conservados.CLAVES``) and the Spanish names of ``pipelines.marts.resumen_tareas`` (``FICHAS`` for
the task, ``MODELOS`` for the model), so no name table is written twice:

``{"tarea": "T1", "tarea_nombre": str, "modelo": str, "modelo_nombre": str, "k": int, "corte": str, "particion": str,
"tipo": "esperado" | "proyeccion"}``

* ``esperado``     the model's expectation on the held-out test cohorts, set against what happened;
* ``proyeccion``   the model applied to the students who are current at the close of the cut.

A block that only counts what was observed carries ``modelo = None``. A block that uses several models carries ``modelo = None`` and
the distinct models in ``modelos`` (each cohort of its detail carries its own ``modelo``).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from evaluation import modelos_conservados as MC

TIPOS = ("esperado", "proyeccion")
CORTE_INGRESO = "ingreso"
CORTE_ANTES_DEL_PERIODO = "inicio de cada período"


def corte_texto(k: int) -> str:
    """Reader's name of the cut: ``k`` = number of semesters lived (``0`` = admission)."""
    k = int(k)
    if k < 1:
        return CORTE_INGRESO
    return "1.er semestre" if k == 1 else f"{k}.º semestre"


def _registro():
    from pipelines.marts import resumen_tareas as RT           # lazy: resumen_tareas imports other evaluation modules

    return RT


def nombre_tarea(tarea: str) -> str:
    """Spanish name of a task without its code: ``"T1 · Continuidad"`` -> ``"Continuidad"``."""
    ficha = _registro().FICHAS[tarea.lower()]["nombre"]
    return ficha.split(" · ", 1)[1] if " · " in ficha else ficha


def modelo_visible(tarea: str, k: int, modelo: str, particion: str, tipo: str, corte: Optional[str] = None) -> Dict[str, Any]:
    """The model object of a block or of a cohort. ``tarea`` is ``"t1"`` or ``"T1"``; the model must be one of the kept ones."""
    tarea = tarea.lower()
    if (tarea, int(k), modelo) not in MC.CLAVES:
        raise KeyError(f"{(tarea, k, modelo)} is not a kept model (evaluation.modelos_conservados.CLAVES)")
    if tipo not in TIPOS:
        raise ValueError(f"tipo must be one of {TIPOS}")
    return {"tarea": tarea.upper(), "tarea_nombre": nombre_tarea(tarea), "modelo": modelo,
            "modelo_nombre": _registro().MODELOS[tarea][modelo][0], "k": int(k),
            "corte": corte if corte is not None else corte_texto(k), "particion": particion, "tipo": tipo}


def distintos(modelos: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The distinct model objects, in order of first appearance."""
    vistos: List[Dict[str, Any]] = []
    for m in modelos:
        if m is not None and dict(m) not in vistos:
            vistos.append(dict(m))
    return vistos


def etiquetar(contenidos: Mapping[str, Dict[str, Any]], modelo: Optional[Mapping[str, Any]] = None,
              modelos: Optional[Sequence[Mapping[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    """Adds ``modelo`` (and ``modelos`` for a multi-model block) to the content of every filter of a block, in place."""
    for c in contenidos.values():
        c["modelo"] = dict(modelo) if modelo is not None else None
        if modelos is not None:
            c["modelos"] = [dict(m) for m in modelos]
    return dict(contenidos)
