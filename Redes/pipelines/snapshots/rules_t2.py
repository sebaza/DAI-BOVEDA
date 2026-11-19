"""Pure definitions of task T2 ("aprobacion por intento", docs/09_benchmark_t2.md).

* Unit: an evaluated attempt (numeric grade; not convalidation, inherited grade, renuncia or in-progress) of a REGULAR
  period (suffix 10/20) of an undergraduate episode (same population filter as T1). Event: REPROBACION (grade < 4.0).
* Prediction moment: just before period ``p`` starts. Every history feature uses facts with ``periodo < p`` (strictly);
  the only things taken from ``p`` itself are what is known at enrollment (the course roster, the course, its attempt
  number and its section).
* Splits are by the period of the attempt (temporal), not by cohort; the same person may appear in several splits.
"""
from __future__ import annotations

import re
from typing import Optional

from ..marts.rules import regular_ordinal
from .rules import ADMISIONES_EXCLUIDAS, NIVEL_PREGRADO  # noqa: F401  (same population filter as T1)

PERIODO_MIN = "201510"                  # first period of the official window (DAI P49/P50)
PERIODO_MAX = "202520"                  # 202610 / 202620 are in progress
TRAIN_HASTA, VALID_HASTA, TEST_HASTA = "202020", "202220", "202420"      # last period of each split
# Periods in which the recorded grades have (almost) no failures: 201920 (social unrest) and 202010 (COVID-19). The
# share of grades < 4.0 among evaluated attempts is 0.000 in both (14-19 % in the neighbouring periods; P58). They are not
# units of T2 and their attempts do not feed the pass-rate statistics (they still count for credits and prerequisites).
PERIODOS_SIN_REPROBACION = frozenset({"201920", "202010"})
SPLITS = ("train", "valid", "test")
UMBRAL_APROBACION = 4.0
# P74 (DAI, 13-11-2026): grade bands of an attempt, conventional Chilean cut points (team decision D75, to confirm in P84):
# reprobado < 4.0, minima 4.0-4.9, aprobatoria 5.0-5.9, sobresaliente >= 6.0. The label side of the multiclass task.
# P84 (DAI, 13-11-2026) replaced them by the institutional recognition scale: reprobado < 4.0; "Aprobado por Unanimidad"
# [4.0, 5.4); "Aprobado con Distincion" [5.4, 6.4); "Aprobado con Maxima Distincion" [6.4, 7.0] (half-open, so grades with two
# decimals fall in one band). The degree grade (70 % courses + 30 % titulacion exam) is not modelled here (P89).
CORTES_BANDA = (4.0, 5.4, 6.4)
BANDAS = ("reprobado", "unanimidad", "distincion", "maxima_distincion")
ETIQUETA_BANDA = {"reprobado": "Reprobado", "unanimidad": "Aprobado por Unanimidad", "distincion": "Aprobado con Distinción",
                  "maxima_distincion": "Aprobado con Máxima Distinción"}
SUAVIZADO_M = 10.0                      # pseudo-observations of the shrinkage toward the prior rate
KS_RANKING = (1, 2)

_PERIODO = re.compile(r"\d{6}", re.ASCII)


def periodo_a_int(periodo: str) -> int:
    return int(periodo)


def es_periodo_regular(periodo: Optional[str]) -> bool:
    return bool(periodo) and _PERIODO.fullmatch(periodo) is not None and regular_ordinal(periodo) is not None


def en_ventana(periodo: Optional[str], latest: str) -> bool:
    """Regular period inside 2015-2025 that is already closed (strictly before the latest, in-progress one)."""
    return es_periodo_regular(periodo) and PERIODO_MIN <= periodo <= PERIODO_MAX and periodo < latest


def sin_reprobacion(periodo: Optional[str]) -> bool:
    return periodo in PERIODOS_SIN_REPROBACION


def split_periodo(periodo: str) -> str:
    """train 2015-2020, valid 2021-2022, test 2023-2024, posterior 2025 (by the attempt period)."""
    if periodo <= TRAIN_HASTA:
        return "train"
    if periodo <= VALID_HASTA:
        return "valid"
    if periodo <= TEST_HASTA:
        return "test"
    return "posterior"


def reprobado(nota: Optional[float]) -> bool:
    return nota is not None and nota < UMBRAL_APROBACION


def banda_nota(nota) -> Optional[str]:
    """Grade band of a numeric grade (``None`` for a missing one). The cut points belong to the upper band."""
    if nota is None or nota != nota:
        return None
    n = 0
    for corte in CORTES_BANDA:
        if nota >= corte:
            n += 1
    return BANDAS[n]
