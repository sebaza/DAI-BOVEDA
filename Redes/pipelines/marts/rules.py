"""Pure rules behind the ``neural_mart`` tables.

The SQL in ``sql.py`` implements the same definitions; ``tests/integration/test_marts.py`` checks that the two
agree on the synthetic histories. Counts are never computed here, only definitions.

* A *regular* period ends in 10 or 20 (RA11). ``semestre_k`` counts regular periods from the admission period
  (k = 1 at the admission semester); summer/winter and other periods have no ``semestre_k``.
* Every group size is published: there is no minimum-size rule.
* Censoring: a window of ``k`` years from admission is observed only when its last semester is strictly before
  the latest period in the data (that period may still be in progress).
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import List, Optional, Sequence

BANDAS = 5          # quintiles of the weighted score

_PERIODO = re.compile(r"(\d{4})(\d{2})", re.ASCII)


def regular_ordinal(periodo: Optional[str]) -> Optional[int]:
    """Semester ordinal of a regular period (``AAAA10`` / ``AAAA20``); ``None`` for any other period."""
    m = _PERIODO.fullmatch(periodo or "")
    if not m or m.group(2) not in ("10", "20"):
        return None
    return int(m.group(1)) * 2 + (0 if m.group(2) == "10" else 1)


def base_ordinal(periodo_admision: Optional[str]) -> Optional[int]:
    """Ordinal of the admission semester; non-regular suffixes (01, 15, 25...) map to the semester they fall in."""
    m = _PERIODO.fullmatch(periodo_admision or "")
    if not m:
        return None
    return int(m.group(1)) * 2 + (1 if m.group(2) >= "20" else 0)


def semestre_k(periodo: Optional[str], periodo_admision: Optional[str]) -> Optional[int]:
    """1-based count of regular periods since admission, or ``None`` (non-regular period, before admission)."""
    ord_p, base = regular_ordinal(periodo), base_ordinal(periodo_admision)
    if ord_p is None or base is None:
        return None
    k = ord_p - base + 1
    return k if k >= 1 else None


def duracion_anios(duracion_semestres: Optional[int]) -> Optional[int]:
    """``programa_catalogo.duracion`` is in semesters (titulados show 10 -> about 6 years of real time)."""
    if not duracion_semestres or duracion_semestres <= 0:
        return None
    return math.ceil(duracion_semestres / 2)


def censurado(base: int, anios: int, latest: int) -> bool:
    """True when the window of ``anios`` years from the admission semester is not fully observed."""
    return base + 2 * anios - 1 >= latest


def retencion_observable(base: int, latest: int) -> bool:
    """First-year retention looks at semester 3; it must be strictly before the latest period."""
    return base + 2 < latest


def banda_from_percent_rank(pr: float) -> int:
    return min(BANDAS, math.floor(pr * BANDAS) + 1)


def bandas(values: Sequence[float]) -> List[int]:
    """Band 1..5 of each value from its ``percent_rank`` inside the group (ties share a band)."""
    n = len(values)
    if n <= 1:
        return [1] * n
    ordered = sorted(values)
    out = []
    for v in values:
        below = sum(1 for x in ordered if x < v)
        out.append(banda_from_percent_rank(below / (n - 1)))
    return out


def periodo_de_fecha(d: Optional[date]) -> Optional[str]:
    """Academic period a date falls in: Jan-Feb close the previous second semester."""
    if d is None:
        return None
    if d.month <= 2:
        return f"{d.year - 1}20"
    return f"{d.year}10" if d.month <= 7 else f"{d.year}20"
