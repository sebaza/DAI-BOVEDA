"""Pure point-in-time rules of the student-benefit variables of T3 (``banner.banner_beneficios``; decisions D100-D109).

Facts (DAI, 16-11-2026): the table is annual, it holds the FINAL state of each year (people who leave lose their row or get the
second-semester amount zeroed afterwards, D92), there is no assignment date and no load history before 2024 (P90, P93).

Rule of a T3 cut (end of the ``k``-th regular semester since admission, period ``periodo_corte`` ending in ``10`` or ``20``):

* ``previo`` (DEFAULT, the one the adoption criterion is judged on): only calendar years STRICTLY BEFORE the year of the cut.
* ``con_t`` (sensitivity): at an END-OF-YEAR cut (period ``AAAA20``) the cut year itself is also read; at a mid-year cut
  (``AAAA10``) it behaves like ``previo``. Only the first-semester amount is ever a feature (``benef_sem2`` and ``total`` are not).

Both rules read only years inside the own window of the student (``max(ANIO_MIN, admission year) .. latest allowed year``): a year
before admission is not "no benefit", it is "not yet a student" and is treated as unknown (NaN + indicator), exactly like the years
before the table starts (``ANIO_MIN``) or after the latest loaded one. Loss variables compare the latest allowed year with the
year before it and need both years inside the window.
"""
from __future__ import annotations

from typing import Optional

from ..marts.rules import base_ordinal
from .rules import ordinal_a_periodo
from .rules_beneficios import ANIO_MIN  # noqa: F401  (re-exported)

REGLAS = ("previo", "con_t")
REGLA_DEFECTO = "previo"
K_OFICIALES = (2, 4)               # cuts of the official T3 snapshot that can see benefits (k = 0 is "at enrollment")
K_EXTENSION = (8, 10)              # late cuts (extension): the expiry / Capstone flags appear 4-6 years after admission
K_BENEFICIOS = K_OFICIALES + K_EXTENSION


def anio_de_periodo(periodo: Optional[str]) -> Optional[int]:
    if not isinstance(periodo, str) or len(periodo) != 6 or not periodo.isdigit():
        return None
    return int(periodo[:4])


def periodo_corte(periodo_admision: Optional[str], k: int) -> Optional[str]:
    """Regular period at which the ``k``-th regular semester since admission ends."""
    base = base_ordinal(periodo_admision)
    return None if base is None or k < 1 else ordinal_a_periodo(base + k - 1)


def anio_admision(periodo_admision: Optional[str]) -> Optional[int]:
    """Calendar year of the admission semester (a ``15``/``25`` period maps to the regular semester it falls in)."""
    base = base_ordinal(periodo_admision)
    return None if base is None else base // 2


def es_corte_fin_de_anio(periodo_cut: Optional[str]) -> bool:
    return isinstance(periodo_cut, str) and periodo_cut[4:] == "20"


def anio_maximo(regla: str, periodo_cut: Optional[str]) -> Optional[int]:
    """Latest calendar year a cut may read under ``regla`` (never a year after the cut year)."""
    anio = anio_de_periodo(periodo_cut)
    if anio is None:
        return None
    if regla == "previo":
        return anio - 1
    if regla == "con_t":
        return anio if es_corte_fin_de_anio(periodo_cut) else anio - 1
    raise ValueError(f"unknown rule {regla!r}")


def anio_inicio(periodo_admision: Optional[str]) -> Optional[int]:
    """First year of the window of the student: the admission year, never before the table starts."""
    a = anio_admision(periodo_admision)
    return None if a is None else max(ANIO_MIN, a)
