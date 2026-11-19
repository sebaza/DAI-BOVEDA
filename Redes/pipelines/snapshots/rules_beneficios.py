"""Pure definitions of the student-benefit variables of T1 (``banner.banner_beneficios``, DAI 16-11-2026).

The table has one row per (YEAR, person, program, benefit, coverage). A benefit is identified by its ``codigo`` (the names carry
encoding noise), and the families below are defined on the code. Decisions D90-D95 (``docs/00_plan.md``):

* Point in time: the benefit variables of a cut are the facts of the CALENDAR YEAR of the cut period, restricted to the
  episode's program (a row of another program is ignored). Nothing of the following year is read, because the absence of a
  benefit in the next year is mechanically tied to not enrolling in it (it would leak the outcome).
* ``benef_sem2`` and ``total`` are never features: the load history shows second-semester amounts being zeroed after the
  year closes for part of the students (diagnostic in ``docs/08_benchmark_t1.md``); only ``benef_sem1`` enters.
* Loss variables compare year ``t - 1`` with the cut year ``t`` and exist only at ``K_PERDIDA`` (k = 4).
* The table starts in ``ANIO_MIN``; a year without data is UNKNOWN (NaN + indicator), never 0.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

ANIO_MIN = 2017
K_PERDIDA = (4,)

FAMILIAS = ("gratuidad", "credito", "beca_estatal", "beca_ucn")
_MERITO = {"PI_01": 70, "PI_02": 75, "PI_03": 85, "PI_04": 85, "PI_06": 85}      # "Beneficio por Posicionamiento X%"
_MERITO_E1 = "PE_01"
_DECIL = {"QI_07": "7", "DC_07": "7", "QI_89": "8-9", "DC_89": "8-9"}              # "Rebaja Arancel Decil 7 / 8-9"
_EXPIRACION = re.compile(r"R[EB]_G(\d)_")                                          # "Expiracion Gratuidad N+1 / N+2"


def _prefijo(codigo: str) -> str:
    return codigo[:5]


def clasificar(codigo: Optional[str]) -> Dict:
    """Flags of one benefit code: ``familia`` (one of ``FAMILIAS`` or None), ``merito`` (0/70/75/85), ``merito_e1``, ``decil``
    ('7' / '8-9' / None), ``expiro`` (0 / 1 = N+1 / 2 = N+2) and ``capstone``."""
    c = (codigo or "").strip().upper()
    familia = None
    if c.startswith(("GG_94", "GU_00")):
        familia = "gratuidad"
    elif c.startswith(("C_1_", "C_70_")):
        familia = "credito"
    elif c.startswith("BG_"):
        familia = "beca_estatal"
    elif c.startswith("BI_"):
        familia = "beca_ucn"
    m = _EXPIRACION.match(c)
    return {
        "familia": familia,
        "merito": _MERITO.get(_prefijo(c), 0),
        "merito_e1": _prefijo(c) == _MERITO_E1,
        "decil": _DECIL.get(_prefijo(c)),
        "expiro": int(m.group(1)) if m else 0,
        "capstone": c.startswith("PC_"),
    }


def anio_con_dato(anio: Optional[int], anio_max: int) -> bool:
    """A year is covered when it lies inside the loaded range; outside it the variables are unknown."""
    return anio is not None and ANIO_MIN <= anio <= anio_max
