"""Pure definitions of tasks T4 ("transicion real de programa") and T5 ("eliminacion"), docs/11_benchmark_t4_t5.md.

* Unit: a T3 trajectory (undergraduate episode of the T1 population, cohorts 2015 or later, exchange programs out, an
  Ingenieria Civil Plan Comun merged with its specialty, D47) at risk at the cut ``k`` = end of the ``k``-th REGULAR
  semester since admission, ``k`` in 2, 4 (the T3 cut helpers and eligibility are reused).
* Horizon: the next two regular semesters, i.e. the slots ``k + 1 .. k + 2``. A row is observable (not censored) only
  when slot ``k + 2`` is a CLOSED regular period (``seguimiento_max >= k + 2``).
* One mutually exclusive outcome per row (earliest event inside the horizon; ties by the order egreso, eliminacion,
  transicion, transicion_ambigua; no event: enrolled at the horizon -> continua, otherwise otra_salida):
  ``continua``, ``egreso``, ``transicion`` (T4), ``eliminacion`` (T5), ``otra_salida``; ``transicion_ambigua`` and
  ``censurado`` are kept in the snapshot but never used by a model.
* T4 event: the person starts another undergraduate program by change of degree, campus transfer or any other transfer
  (``neural_mart.programa_traslados``, D48-D50), dated at the EXIT from the origin program, i.e. its last period (P71, stage B;
  before it was the first period of the destination; the two coincide in the 80 % of the transfers with gap 0). The election of a specialty (Plan Comun), a cycle change and a
  continuation after graduating are expected progression and never events.
* T5 event: a state ``E`` (Eliminado) of the trajectory. The other exit states (voluntary withdrawal, non-enrollment,
  disciplinary sanctions) are NOT academic eliminations and fall in ``otra_salida`` (P70).
"""
from __future__ import annotations

from typing import Optional

from ..marts import rules_traslados as RT
from . import rules_t3 as R3

KS = (2, 4)
HORIZONTE_SEMESTRES = 2
COHORTE_MIN = R3.COHORTE_MIN
TRAIN_HASTA, VALID_HASTA, TEST_HASTA = 2019, 2021, 2023     # the T1 boundaries: the horizon is short, so follow-up allows them
CLASES = ("continua", "egreso", "transicion", "eliminacion", "otra_salida")
EXCLUIDAS = ("transicion_ambigua", "censurado")
RESULTADOS = CLASES + EXCLUIDAS
ORDEN_PRECEDENCIA = ("egreso", "eliminacion", "transicion", "transicion_ambigua")
CODIGOS_ELIMINACION = frozenset({"E"})
# every other state of class ``salida`` (dic_estado): Renuncia Alumno/Admision, No Continuidad, Retracto, No Matricula
# Admision, Matricula Anulada, Expulsado, Sancionado Eliminado, Sancionado. Not an academic elimination (P70).
CODIGOS_OTRA_SALIDA = frozenset({"B", "F", "O", "R", "3", "9", "X", "6", "H"})
# Last regular period whose number of ``E`` states looks complete: from 202420 on they fall to a quarter or less of the
# comparable periods (290 in 202420, 128 in 202510, 532 in 202520 against 1.100-1.300 in the second semesters before), while
# the transfers keep their level. Banner is checking it (P75, pending). Used for the sensitivity analysis of T5 and for the
# ``horizonte_e_dudoso`` flag of the snapshot; the outcome labels are never changed by it.
E_COMPLETO_HASTA = "202410"
# P72 (DAI, 13-11-2026): an elimination usually comes together with a reintegro (a letter to the council). Reintegro states
# (stage A used I and Y; P88 corrected it to I only).
CODIGOS_REINTEGRO = frozenset({"I"})        # P88 (DAI): only I; Y is "Reintegro por Rectificacion", not a reintegro
TIPOS_TRANSICION = frozenset(t for t, cuenta in RT.CUENTA_ABANDONO.items() if cuenta)
OTRA_SALIDA_TIPOS = ("salida_explicita", "interrupcion", "ausencia")


def split_cohorte(anio: int) -> str:
    if anio < COHORTE_MIN:
        return "anterior"
    if anio <= TRAIN_HASTA:
        return "train"
    if anio <= VALID_HASTA:
        return "valid"
    if anio <= TEST_HASTA:
        return "test"
    return "posterior"


def clase_traslado(tipo: Optional[str], ambiguo: bool) -> Optional[str]:
    """``transicion`` / ``transicion_ambigua`` for the transfer types that leave the origin program, else ``None``."""
    if tipo not in TIPOS_TRANSICION:
        return None
    return "transicion_ambigua" if ambiguo else "transicion"


def eliminacion_con_reintegro(eliminacion, reintegro) -> bool:
    """P72: is the elimination followed by a reintegro? Both are ``(slot, orden_canonico)`` pairs (``reintegro`` ``None``
    when there is none). The reintegro must come later in slot, or in the same slot and recorded after the ``E``."""
    return reintegro is not None and tuple(reintegro) > tuple(eliminacion)


def horizonte_e_dudoso(ultimo_periodo_horizonte) -> bool:
    """P75: the horizon reaches a period whose ``E`` recording is in doubt (after ``E_COMPLETO_HASTA``)."""
    return isinstance(ultimo_periodo_horizonte, str) and ultimo_periodo_horizonte > E_COMPLETO_HASTA


def _hay(x) -> bool:
    return x is not None and x == x


def resolver_resultado(k: int, t_egreso, t_eliminacion, t_transicion, t_ambigua, matriculado_h: bool, t_max: int,
                       horizonte: int = HORIZONTE_SEMESTRES) -> str:
    """Outcome of a row from the slots (``None`` / NaN when absent) of its events.

    An event counts when its slot lies in ``(k, k + horizonte]``; the earliest wins and ties follow
    ``ORDEN_PRECEDENCIA``. Without events the row is ``continua`` when the person is enrolled in any UCN program at the
    horizon period and ``otra_salida`` otherwise. A horizon that is not closed (``t_max < k + horizonte``) gives
    ``censurado``: no label without the closed horizon.
    """
    h = k + horizonte
    if t_max < h:
        return "censurado"
    candidatos = [t_egreso, t_eliminacion, t_transicion, t_ambigua]
    dentro = [(t, i) for i, t in enumerate(candidatos) if _hay(t) and k < t <= h]
    if dentro:
        return ORDEN_PRECEDENCIA[min(dentro)[1]]
    return "continua" if matriculado_h else "otra_salida"
