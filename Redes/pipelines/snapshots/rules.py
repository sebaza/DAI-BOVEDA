"""Pure definitions of task T1 ("continuidad a un año", docs/08_benchmark_t1.md).

* The cutoff of ``k`` is the ``k``-th REGULAR period (suffix 10/20) counted from the admission semester
  (``marts.rules.semestre_k``). The horizon is the regular period two regular periods later (one year).
* A fact belongs to the *slot* ``j`` of its period when ``regular_period(j-1) < periodo <= regular_period(j)``.
  Hence ``periodo <= cutoff(k)  <=>  slot <= k``: summer/winter courses (15/25) count for the features of the
  cutoff that follows them, never for an earlier one.
* Coverage: the states table records second semesters (suffix 20) completely only from 2015 (before that the
  number of people with an enrolled state in a 20 period is about one eighth of the 10 periods); a cutoff or a
  horizon in such a period is *sin_cobertura*, not a dropout.
"""
from __future__ import annotations

import re
from typing import Optional

from ..marts.rules import base_ordinal, regular_ordinal

KS = (1, 2)
KS_EXTENSION = (4,)                          # secondary evaluation (D91): end of the second year, enables the benefit-loss variables
KS_TODOS = KS + KS_EXTENSION
HORIZONTE_SEMESTRES = 2                     # regular periods after the cutoff (one year)
COBERTURA_20_DESDE = "201520"               # first 20 period with complete state coverage
TRAIN_HASTA, VALID_HASTA, TEST_HASTA = 2019, 2021, 2023
TRAIN_DESDE_OFICIAL = 2015                 # official training window (DAI P49/P50, 12-11-2026); earlier cohorts stay in the snapshot
ADMISIONES_EXCLUIDAS = frozenset({"IN", "PE", "IE"})   # exchange, special plans, special student
NIVEL_PREGRADO = 1

_PERIODO = re.compile(r"(\d{4})(\d{2})", re.ASCII)


def ordinal_a_periodo(ordinal: int) -> str:
    """Inverse of ``regular_ordinal``: even -> ``AAAA10``, odd -> ``AAAA20``."""
    return f"{ordinal // 2}{'10' if ordinal % 2 == 0 else '20'}"


def corte_periodo(periodo_admision: Optional[str], k: int) -> Optional[str]:
    base = base_ordinal(periodo_admision)
    if base is None or k < 1:
        return None
    return ordinal_a_periodo(base + k - 1)


def horizonte_periodo(corte: Optional[str], semestres: int = HORIZONTE_SEMESTRES) -> Optional[str]:
    ordinal = regular_ordinal(corte)
    if ordinal is None:
        return None
    return ordinal_a_periodo(ordinal + semestres)


def slot_de_periodo(periodo: Optional[str], periodo_admision: Optional[str]) -> Optional[int]:
    """Slot ``j`` (1 = admission semester) of any period; ``None`` before admission or if malformed."""
    m = _PERIODO.fullmatch(periodo or "")
    base = base_ordinal(periodo_admision)
    if not m or base is None:
        return None
    anio, sufijo = int(m.group(1)), m.group(2)
    if sufijo <= "10":
        ordinal = anio * 2
    elif sufijo <= "20":
        ordinal = anio * 2 + 1
    else:
        ordinal = (anio + 1) * 2
    j = ordinal - base + 1
    return j if j >= 1 else None


def periodo_con_cobertura(periodo: Optional[str]) -> bool:
    if regular_ordinal(periodo) is None:
        return False
    return periodo[4:] == "10" or periodo >= COBERTURA_20_DESDE


def estado_muestra(corte: str, horizonte: str, latest: str) -> str:
    """``censurada`` (horizon not before the latest period), ``sin_cobertura`` or ``observada``."""
    if horizonte >= latest:
        return "censurada"
    if not (periodo_con_cobertura(corte) and periodo_con_cobertura(horizonte)):
        return "sin_cobertura"
    return "observada"


def split_cohorte(anio: int) -> str:
    if anio <= TRAIN_HASTA:
        return "train"
    if anio <= VALID_HASTA:
        return "valid"
    if anio <= TEST_HASTA:
        return "test"
    return "posterior"


def es_poblacion_t1(id_nivel: Optional[int], cod_admision: Optional[str]) -> bool:
    return id_nivel == NIVEL_PREGRADO and cod_admision not in ADMISIONES_EXCLUIDAS


def via_clase(tipo_qualitas: Optional[str]) -> str:
    if tipo_qualitas is None:
        return "sin_dato"
    if tipo_qualitas.startswith("1."):
        return "regular"
    if tipo_qualitas.startswith("2."):
        return "especial"
    if tipo_qualitas.startswith("3."):
        return "otros_cambio"
    return "otra"


def _prefijo(texto: Optional[str]) -> Optional[str]:
    text = texto.strip() if isinstance(texto, str) else ""
    if not text:
        return None
    return text.split("-", 1)[0].strip() or None


def codigo_colegio(tipo_colegio: Optional[str]) -> Optional[str]:
    """``H1-Humanista ...`` -> ``H1``."""
    return _prefijo(tipo_colegio)


def codigo_dependencia(depend_colegio: Optional[str]) -> Optional[str]:
    """``4-Particular NO subvencionado`` and ``4-Particular No subvencionado`` -> ``4``."""
    return _prefijo(depend_colegio)


# ---- P47 (DAI, 13-11-2026): admission test by process year -------------------------------------------------------------
# "The test is identified by the date it was taken: PSU, then PDT, then PAES". The source has no sitting date, only the
# admission process year, so the boundary is the process year (assumption S21, to confirm in P87): PSU up to the 2020
# process, PDT for the 2021 and 2022 processes, PAES from the 2023 process.
PSU_HASTA, PDT_HASTA = 2020, 2022
PRUEBAS = ("PSU", "PDT", "PAES")
# A score above this multiple of the median of its (test, year, field) is an order-of-magnitude reading error (557,00 read
# as 55700) and is not a score; every legitimate scale of the sources stays well below 2x its median.
FACTOR_ESCALA = 3.0


def reescala_decimal(x):
    """The weighted score arrives as 557.00, 5570 and 55700 inside one process year (measured: about half of the 2025 and 2026
    rows carry a x10 or x100 scale). A positive value of 1000 or more is divided by the power of ten that leaves three integer
    digits; below 1000 it is already on the base scale (a value under 100 cannot be told apart from a different score)."""
    if x is None or not x > 0 or x < 1000:
        return x
    return x / 10.0 ** (len(str(int(x))) - 3)


def prueba_admision(anio) -> Optional[str]:
    """``PSU`` / ``PDT`` / ``PAES`` from the admission process year (int or text), ``None`` when it is not a year."""
    try:
        y = int(anio)
    except (TypeError, ValueError):
        return None
    if y <= PSU_HASTA:
        return "PSU"
    return "PDT" if y <= PDT_HASTA else "PAES"
