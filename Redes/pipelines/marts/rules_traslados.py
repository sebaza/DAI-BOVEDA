"""Pure rules behind ``neural_mart.programa_traslados`` (P61, D48-D52).

One row = one transition of a person from an origin program episode to the NEXT undergraduate episode of a
different program. The SQL in ``sql.py`` implements the same definitions; ``tests/integration/test_marts.py`` checks
that both agree on the synthetic histories.

Conservative rules (docs/00_plan.md D48-D52):

* Undergraduate episodes only; exchange programs (0003, 0006) and the non-regular admissions (IN, PE, IE) are out.
* A transition needs two different programs. The destination is the next episode of the person by first period;
  the only exception is an Ingenieria Civil Plan Comun origin, linked to the first later specialty (D47 rule).
* The destination must start 0 to 2 regular slots after the last period of the origin (``VENTANA``). Earlier starts
  are overlaps (simultaneous programs), later ones are re-entries years afterwards: neither is a transfer.
* The type, in this order: specialty election (D47 link, or an ``ES`` admission), cycle change (state D in the origin),
  change of degree (``CC``), campus change (``CS``), other transfer.

DAI answers of 13-11-2026 (stage A of the consolidated rebuild):

* P69: studying another program after graduating is NOT a transfer. It never reaches ``programa_traslados``; it is kept
  as a note (``relacion_sin_traslado`` = ``continuacion_estudios``).
* P64: simultaneous enrollments are not excluded from any population (double degrees exist). Overlapping episodes
  without a baja are a *double program* (not a transfer); a baja (class ``salida``) in the origin of an overlap is an exit
  of that program, which the states already record (not a transfer either). Both are only counted as notes.
"""
from __future__ import annotations

from typing import Optional

from ..snapshots import rules_t3 as R3
from ..snapshots.rules import ADMISIONES_EXCLUIDAS

TIPOS = ("eleccion_especialidad", "cambio_ciclo", "cambio_carrera", "traslado_sede", "traslado_otro")
# Relations between two episodes that are NOT a transfer (P64, P69): counted as notes only.
RELACIONES_SIN_TRASLADO = ("continuacion_estudios", "doble_programa", "superposicion_con_baja")
# Only a change of program that is neither a specialty election, a cycle change nor a continuation after graduating
# is a loss for the origin program (DAI, P61).
CUENTA_ABANDONO = {
    "eleccion_especialidad": False, "cambio_ciclo": False,
    "cambio_carrera": True, "traslado_sede": True, "traslado_otro": True,
}
VENTANA_MIN, VENTANA_MAX = 0, 2     # regular slots between the last period of the origin and the first of the destination
ADMISION_ELECCION = "ES"
ADMISION_CAMBIO_CARRERA = "CC"
ADMISION_CAMBIO_SEDE = "CS"
CLASE_EGRESO = "egreso_titulacion"
CLASE_BAJA = "salida"
CLASE_CICLO = "cambio_ciclo"
PROGRAMAS_EXCLUIDOS = R3.PROGRAMAS_INTERCAMBIO
ADMISIONES_EXCLUIDAS_TRASLADO = ADMISIONES_EXCLUIDAS


def brecha(ultimo_origen: Optional[str], primer_destino: Optional[str]) -> Optional[int]:
    """Regular slots from the last period of the origin to the first period of the destination."""
    a, b = R3.ordinal_periodo(ultimo_origen), R3.ordinal_periodo(primer_destino)
    return None if a is None or b is None else b - a


def es_eleccion_d47(cod_origen: str, cod_destino: str, primer_origen: Optional[str], ultimo_origen: Optional[str],
                    primer_destino: Optional[str]) -> bool:
    """Ingenieria Civil Plan Comun -> Ingenieria Civil specialty by the D47 rule (no ES nor same admission needed)."""
    if cod_origen not in R3.PLAN_COMUN_ING_CIVIL or cod_destino not in R3.ESPECIALIDADES_ING_CIVIL:
        return False
    inicio, fin, nuevo = R3.ordinal_periodo(primer_origen), R3.ordinal_periodo(ultimo_origen), R3.ordinal_periodo(primer_destino)
    if inicio is None or nuevo is None or nuevo <= inicio:
        return False
    return R3.dentro_de_ventana_vinculo(ultimo_origen, primer_destino) and fin is not None


def clasificar(cod_origen: str, cod_destino: str, cod_admision_destino: Optional[str], clase_origen: Optional[str],
               primer_origen: Optional[str], ultimo_origen: Optional[str], primer_destino: Optional[str]) -> Optional[str]:
    """Type of the transition, or ``None`` when it is not a transfer under the conservative rules."""
    if cod_origen == cod_destino or cod_origen in PROGRAMAS_EXCLUIDOS or cod_destino in PROGRAMAS_EXCLUIDOS:
        return None
    if es_eleccion_d47(cod_origen, cod_destino, primer_origen, ultimo_origen, primer_destino):
        return "eleccion_especialidad"
    b = brecha(ultimo_origen, primer_destino)
    if b is None or not VENTANA_MIN <= b <= VENTANA_MAX:
        return None
    if cod_admision_destino == ADMISION_ELECCION:
        return "eleccion_especialidad"
    if clase_origen == CLASE_EGRESO:
        return None                                  # P69: continuation after graduating is not a transfer
    if clase_origen == CLASE_CICLO:
        return "cambio_ciclo"
    if cod_admision_destino == ADMISION_CAMBIO_CARRERA:
        return "cambio_carrera"
    if cod_admision_destino == ADMISION_CAMBIO_SEDE:
        return "traslado_sede"
    return "traslado_otro"


def relacion_sin_traslado(cod_origen: str, cod_destino: str, cod_admision_destino: Optional[str], clase_origen: Optional[str],
                          primer_origen: Optional[str], ultimo_origen: Optional[str], primer_destino: Optional[str]) -> Optional[str]:
    """Relation of two episodes that is neither a transfer nor ignored: ``continuacion_estudios`` (P69),
    ``doble_programa`` (overlap without a baja) or ``superposicion_con_baja`` (overlap whose origin ends in a baja) (P64).
    ``None`` for a transfer or for episodes with nothing to note."""
    if cod_origen == cod_destino or cod_origen in PROGRAMAS_EXCLUIDOS or cod_destino in PROGRAMAS_EXCLUIDOS:
        return None
    if es_eleccion_d47(cod_origen, cod_destino, primer_origen, ultimo_origen, primer_destino):
        return None
    b = brecha(ultimo_origen, primer_destino)
    if b is None:
        return None
    if b < VENTANA_MIN:
        return "superposicion_con_baja" if clase_origen == CLASE_BAJA else "doble_programa"
    if b <= VENTANA_MAX and cod_admision_destino != ADMISION_ELECCION and clase_origen == CLASE_EGRESO:
        return "continuacion_estudios"
    return None
