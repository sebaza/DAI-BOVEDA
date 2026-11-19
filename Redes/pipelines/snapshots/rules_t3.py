"""Pure definitions of task T3 ("tiempo hasta titulacion", docs/10_benchmark_t3.md): survival with censoring and a
competing event.

* Unit: an undergraduate episode (same population as T1, D23) at risk at the cut ``k`` = end of the ``k``-th REGULAR
  semester since admission (``k`` in 0, 2, 4; ``k = 0`` is "at enrollment": only admission facts are known).
* Time: the SLOT ``j`` of ``rules.slot_de_periodo`` (1 = admission semester), i.e. regular semesters since admission.
  The time since the cut is ``j - k``; every model works on that scale and every report on the absolute one.
* Event 1: first egreso / titulacion of the episode (a state of class ``egreso_titulacion`` or a linked
  ``titulacion`` row). Event 2 (competing): definitive exit of the episode (an explicit exit state that is not
  followed by any enrolled state, or a sustained absence with no egress). Interruptions are not exits.
* Censoring: administrative only. Events after the last CLOSED regular period (the one before the latest recorded,
  in-progress period) or after slot ``VENTANA_SLOTS`` are censored at that limit.
"""
from __future__ import annotations

from typing import Optional, Tuple

from ..marts.rules import base_ordinal, regular_ordinal
from .rules import ADMISIONES_EXCLUIDAS, NIVEL_PREGRADO, es_poblacion_t1, ordinal_a_periodo  # noqa: F401

KS = (0, 2, 4)
COHORTE_MIN = 2015                  # states before 2015 are incomplete (P49/P50): the snapshot starts there
TRAIN_HASTA, VALID_HASTA, TEST_HASTA = 2017, 2018, 2020
VENTANA_SLOTS = 20                  # events later than this slot are censored there (no horizon beyond 14 is reported)
AUSENCIA_PERIODOS = 2               # regular closed periods without any enrolled / interruption state => absence
HORIZONTES = (10, 12, 14)           # slots since admission: the modal nominal duration (5 years), +2, +4
IBS_HASTA = 12                      # the integrated Brier score covers slots k+1 .. IBS_HASTA
CENSURA, EGRESO, SALIDA = 0, 1, 2
SALIDA_EXPLICITA, SALIDA_AUSENCIA = "explicita", "ausencia"
# Periods in which no failure was recorded (P58): their attempts feed credits but not pass-rate statistics.
PERIODOS_SIN_REPROBACION = frozenset({"201920", "202010"})


def periodo_cierre(latest: Optional[str]) -> Optional[str]:
    """Last CLOSED regular period: the regular period before the latest recorded one (which is still in progress)."""
    ordinal = regular_ordinal(latest)
    return None if ordinal is None else ordinal_a_periodo(ordinal - 1)


def slot_cierre(periodo_admision: Optional[str], latest: Optional[str]) -> Optional[int]:
    """Last observable slot of an episode (administrative follow-up, in regular semesters since admission)."""
    base, cierre = base_ordinal(periodo_admision), regular_ordinal(periodo_cierre(latest))
    if base is None or cierre is None:
        return None
    return cierre - base + 1


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


def _hay(x) -> bool:
    return x is not None and x == x


def resolver_evento(
    t_egreso, t_salida_def, ultima_actividad, t_max: int, ventana: int = VENTANA_SLOTS
) -> Tuple[int, int, Optional[str]]:
    """``(tiempo, causa, salida_tipo)`` of an episode from the slots of its facts (None / NaN when absent).

    * ``t_egreso``: first slot with an egress/titulation fact; ``t_salida_def``: first exit state at or after the last
      enrolled slot; ``ultima_actividad``: last slot with an enrolled or interruption state (also beyond ``t_max``).
    * Egress observed inside the limit always wins (graduation is verified, an earlier exit state is administrative).
    * Otherwise the exit: the explicit definitive one, else an absence (no egress at all and nothing in the last
      ``AUSENCIA_PERIODOS`` closed periods) one slot after the last activity.
    * An event past the limit is censored at the limit (``causa`` 0).
    """
    limite = min(t_max, ventana)
    if _hay(t_egreso) and t_egreso <= limite:
        return int(t_egreso), EGRESO, None
    t_x, tipo = None, None
    if _hay(t_salida_def):
        t_x, tipo = int(t_salida_def), SALIDA_EXPLICITA
    elif not _hay(t_egreso) and _hay(ultima_actividad) and ultima_actividad <= t_max - AUSENCIA_PERIODOS:
        t_x, tipo = int(ultima_actividad) + 1, SALIDA_AUSENCIA
    if t_x is not None and t_x <= limite:
        return t_x, SALIDA, tipo
    return limite, CENSURA, None


# ---------------------------------------------------------------------------------------------
# population by program identity (D47, P62)
# ---------------------------------------------------------------------------------------------
# "PROGRAMA DE INTERCAMBIO": students of foreign universities on short stays; they cannot egress by nature (DAI, P62).
# Pinned by CODE (never by duration); integration test checks the names in neural_core.programa.
PROGRAMAS_INTERCAMBIO = frozenset({"0003", "0006"})
# "... PLAN COMUN": bachillerato-like programs. Only the Ingenieria Civil one has episodes in the cohorts >= 2015; after
# completing its malla the student requests a change into an Ingenieria Civil specialty (DAI, P62).
PLAN_COMUN_ING_CIVIL = frozenset({"8633", "8643"})
PLAN_COMUN_CODIGOS = frozenset({"8113", "8413", "8433", "8493", "8633", "8643"})
# Undergraduate Ingenieria Civil specialties (name starts with INGENIERIA CIVIL, level 1, not Plan Comun).
ESPECIALIDADES_ING_CIVIL = frozenset({
    "5683", "8273", "8553", "8603", "8606", "8613", "8616", "8623", "8653", "8683", "8693", "8953", "8963", "8973"})
VENTANA_VINCULO_PERIODOS = 2        # the specialty starts at most this many regular periods after the last Plan Comun one


def ordinal_periodo(periodo: Optional[str]) -> Optional[int]:
    """Ordinal of the regular slot of any period (10 -> even, 15 and 20 -> odd, 25 -> next 10), as ``slot_de_periodo``."""
    if not isinstance(periodo, str) or len(periodo) != 6 or not periodo.isdigit():
        return None
    anio, sufijo = int(periodo[:4]), periodo[4:]
    if sufijo <= "10":
        return anio * 2
    if sufijo <= "20":
        return anio * 2 + 1
    return (anio + 1) * 2


def dentro_de_ventana_vinculo(ultimo_plan_comun: Optional[str], inicio_especialidad: Optional[str]) -> bool:
    """Does the specialty start no later than ``VENTANA_VINCULO_PERIODOS`` regular periods after the Plan Comun's last one?"""
    a, b = ordinal_periodo(ultimo_plan_comun), ordinal_periodo(inicio_especialidad)
    return a is not None and b is not None and b - a <= VENTANA_VINCULO_PERIODOS
