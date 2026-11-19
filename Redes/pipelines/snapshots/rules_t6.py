"""Pure definitions of task T6 ("matricula en postgrado UCN despues del egreso", docs/12_benchmark_t6.md).

* Unit: a T3 trajectory (D47) that reached egreso (state of class ``egreso_titulacion`` or a linked ``titulacion`` row) in a
  CLOSED regular period. The cut is the egreso semester: every feature is a fact of the slots ``<= k`` with ``k`` = slot of
  the egreso.
* Event: the first period in which the same person is ENROLLED (``estado_matricula`` = MATRICULADO) in any UCN postgrado
  program (``neural_core.matricula_postgrado``). The source has no program names or level, so magister, doctorado,
  diplomado and postitulo cannot be told apart (P77). Only UCN postgrado enrollment is observable: nothing here says
  anything about postgrado studies elsewhere.
* Time scale: calendar semesters after the egreso. A postgrado period ``AAAA50`` falls in the first semester of the year
  (like ``AAAA10``) and ``AAAA60`` in the second (like ``AAAA20``); the egreso semester is the regular semester of its slot.
* Prior enrollments: a person already enrolled in a postgrado program before the admission, during the episode or in the
  egreso semester is not at risk of a FIRST enrollment after the egreso; the unit is excluded and counted (D65).
* Censoring: administrative, at the last CLOSED regular period (the postgrado period ``AAAA50`` of that year is closed,
  ``AAAA60`` of a later year is not).
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from ..marts.rules import regular_ordinal
from .rules_t3 import periodo_cierre

HORIZONTES = (2, 4, 8)                         # semesters after the egreso: 1, 2 and 4 years
ANIOS_DE = {2: 1, 4: 2, 8: 4}
TRAIN_HASTA, VALID_HASTA = 2022, 2023           # years of egreso; 2024 onwards is test
SPLITS = ("train", "valid", "test")
ESTADO_MATRICULADO = "MATRICULADO"
ORDINAL_INICIO_FUENTE = 2016 * 2                # the postgrado source starts at 201650
MIN_EVENTOS_CLASICO = 30                        # per partition: baseline and Cox
MIN_EVENTOS_CATBOOST = 100                      # training events for a boosted model with early stopping
MIN_EVENTOS_RED = 300                           # training events for a neural network
ESTADOS = ("evento", "censurado", "previo", "sin_seguimiento", "antes_de_la_fuente")
# P77 / P78 / P80 (DAI, 13-11-2026): the postgrado STATE source (``ban_estados_academicos_pos``) goes back to 2008 and has the
# program names. "Enrolled" = state ``M`` (Matriculado); ``J`` (en tramite) and ``W`` (Post-Graduado = graduated from a
# postgrado program, P78) are not. Level of the first enrolled semester, by priority when several programs coincide.
ESTADO_MATRICULADO_POS = "M"
NIVELES_ESTADOS = ("doctorado", "magister", "diplomado", "otro")

_PERIODO = re.compile(r"(\d{4})(50|60)", re.ASCII)


def ordinal_postgrado(periodo: Optional[str]) -> Optional[int]:
    """Semester ordinal of a postgrado period (``AAAA50`` -> first semester, ``AAAA60`` -> second); ``None`` otherwise."""
    m = _PERIODO.fullmatch(periodo or "")
    if not m:
        return None
    return int(m.group(1)) * 2 + (0 if m.group(2) == "50" else 1)


def ordinal_cierre(latest: Optional[str]) -> Optional[int]:
    """Ordinal of the last closed regular period (the one before the latest recorded, which is still in progress)."""
    return regular_ordinal(periodo_cierre(latest))


def nivel_evento(niveles: Sequence[str]) -> Optional[str]:
    """Level of the event among the programs of its semester: the highest of doctorado > magister > diplomado > otro;
    ``sin_nombre`` (fictitious or unnamed program) counts as ``otro``; ``None`` without programs."""
    vistos = {("otro" if n == "sin_nombre" else n) for n in niveles}
    for n in NIVELES_ESTADOS:
        if n in vistos:
            return n
    return None


def resolver_evento_estados(ord_egreso: int, matriculas: Sequence[Tuple[int, str]],
                            ord_cierre: int) -> Tuple[bool, int, int, Optional[str]]:
    """``(previo, evento, tiempo, nivel)`` from the enrolled postgrado semesters ``(ordinal, nivel)`` of the person in the
    state source. ``previo``: enrolled at or before the egreso semester (the unit is NOT excluded here; the legacy label
    columns keep their own exclusion). The event is the first enrolled semester strictly after the egreso and within the
    closed follow-up; ``tiempo`` = semesters to it, or the follow-up when there is none."""
    seguimiento = int(ord_cierre - ord_egreso)
    previo = any(o <= ord_egreso for o, _ in matriculas)
    despues = sorted(o for o, _ in matriculas if o > ord_egreso)
    if despues and despues[0] - ord_egreso <= seguimiento:
        primero = despues[0]
        return previo, 1, int(primero - ord_egreso), nivel_evento([n for o, n in matriculas if o == primero])
    return previo, 0, seguimiento, None


def split_egreso(anio: int) -> str:
    if anio <= TRAIN_HASTA:
        return "train"
    if anio <= VALID_HASTA:
        return "valid"
    return "test"


def resolver_evento(ord_egreso: int, ord_primera, ord_cierre: int) -> Tuple[str, Optional[int], Optional[int]]:
    """``(estado, tiempo, evento)`` of a unit. ``ord_primera``: first enrolled postgrado semester (``None`` / NaN if none).

    ``estado`` is ``antes_de_la_fuente`` (the egreso precedes the postgrado source: a prior enrollment cannot be seen),
    ``previo`` (first enrollment at or before the egreso semester), ``sin_seguimiento`` (no closed semester after the
    egreso), ``evento`` or ``censurado`` (``tiempo`` = semesters after the egreso, ``evento`` = 1 / 0).
    """
    if ord_egreso < ORDINAL_INICIO_FUENTE:
        return "antes_de_la_fuente", None, None
    hay = ord_primera is not None and ord_primera == ord_primera
    if hay and ord_primera <= ord_egreso:
        return "previo", None, None
    seg = int(ord_cierre - ord_egreso)
    if seg < 1:
        return "sin_seguimiento", None, None
    if hay and ord_primera - ord_egreso <= seg:
        return "evento", int(ord_primera - ord_egreso), 1
    return "censurado", seg, 0


def resultado_horizonte(tiempo, evento, seguimiento, tau: float) -> Tuple[np.ndarray, np.ndarray]:
    """``(elegible, y)``: followed up to ``tau`` (no censoring uncertainty) and enrolled by ``tau``."""
    t, e, seg = np.asarray(tiempo), np.asarray(evento), np.asarray(seguimiento)
    return seg >= tau, ((e == 1) & (t <= tau)).astype("int8")


def viable(eventos_por_particion: Dict[str, int], minimo: int = MIN_EVENTOS_CLASICO) -> bool:
    """A benchmark is viable only when every partition (train, valid and test) has at least ``minimo`` events."""
    return all(eventos_por_particion.get(s, 0) >= minimo for s in SPLITS)
