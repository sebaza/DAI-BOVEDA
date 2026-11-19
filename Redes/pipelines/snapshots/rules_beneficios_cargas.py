"""Pure rules of the point-in-time view of the student benefits built from the load history (DAI 16-11-2026, P90/P91/P93).

The Warehouse keeps every load of ``banner_beneficios_full`` (``timestamp_carga`` in epoch milliseconds). The DAI confirmed that
there is NO assignment date (P90): the closest thing is the first load in which a row appears. The load history is compressed to one
row per (year, person, program, code, coverage) with ``first_ts`` / ``last_ts`` (first and last load that contain the row).

Point-in-time rule (D96). For a cut date ``c`` and a benefit year ``t``:

* ``L`` is the last load of year ``t`` whose date is on or before ``c`` (the calendar of the loads of the year);
* a row of year ``t`` is VISIBLE at ``c`` iff ``first_ts <= L <= last_ts``: it had already been loaded at ``L`` and it had not been
  retired before ``L`` (a row that disappears and reappears is treated as present; the share is measured in the diagnostic);
* if year ``t`` has no history (its first load is later than the end of the year itself: the whole year arrived at once in the first
  load of 2024) or has no load on or before ``c``, the year is UNKNOWN at that cut (NaN + indicator), never 0 (D90);
* the first-semester amount is the CORRECTED amount ``sem1_ultima`` (P97 / D111): the DAI states that the amounts change after the
  first load because failed uploads are fixed, and the current amounts are the right ones (in 2025, 5,177 rows were lowered by a
  median ratio of 0.805, 97 % of them first loaded by one same load). A correction fixes the same fact, it is not later information
  about the student. If the first and the last amount differ by 90 % or more (mostly from or to zero, which can be a real loss or
  gain of the benefit rather than a fix) the amount is not used (NaN). ``benef_sem2`` and ``total`` are never used (D92).

Apart from that deliberate exception, nothing of the compressed row that lies after the cut date (``last_ts`` beyond ``L``,
``n_loads``, ``presente_ultima_carga``, the second-semester amounts) changes the visibility or the features.

Cut dates: the same calendar used by the leakage diagnostic (``evaluation/diagnostico_beneficios.py``): the end of the first
semester (period suffix ``10``) is July 31 and the end of the year (suffix ``20``) is November 30 of the cut year.
"""
from __future__ import annotations

import datetime as dt
from typing import Dict, Optional, Sequence

import numpy as np

CORTE_SEM1 = (7, 31)
CORTE_CIERRE = (11, 30)
_UN_DIA_MS = 86_400_000
UMBRAL_VARIACION_MONTO = 0.90               # P97 / D111: a first-to-last change of 90 % or more is not taken as a correction


def monto_corregido(primera: float, ultima: float) -> float:
    """First-semester amount of a row: the last-load (corrected) amount, or NaN if it varies 90 % or more from the first load.

    The variation is ``|ultima - primera| / max(|primera|, |ultima|)`` (0 when both are 0). A missing side falls back to the
    other one."""
    p_nan, u_nan = np.isnan(primera), np.isnan(ultima)
    if p_nan or u_nan:
        return float("nan") if (p_nan and u_nan) else float(primera if u_nan else ultima)
    mayor = max(abs(primera), abs(ultima))
    if mayor == 0:
        return 0.0
    return float("nan") if abs(ultima - primera) / mayor >= UMBRAL_VARIACION_MONTO else float(ultima)


def montos_corregidos(primera: np.ndarray, ultima: np.ndarray) -> np.ndarray:
    """Vectorised :func:`monto_corregido`."""
    p, u = np.asarray(primera, dtype="float64"), np.asarray(ultima, dtype="float64")
    out = np.where(np.isnan(u), p, u)
    ambos = ~np.isnan(p) & ~np.isnan(u)
    mayor = np.maximum(np.abs(p), np.abs(u))
    with np.errstate(invalid="ignore", divide="ignore"):
        var = np.where(mayor > 0, np.abs(u - p) / np.where(mayor > 0, mayor, 1.0), 0.0)
    return np.where(ambos & (var >= UMBRAL_VARIACION_MONTO), np.nan, out)


def fecha_corte(periodo_corte: str) -> dt.date:
    """Cut date of a regular cut period (``AAAA10`` -> July 31, ``AAAA20`` -> November 30 of that year)."""
    anio, sufijo = int(periodo_corte[:4]), periodo_corte[4:6]
    mes, dia = CORTE_SEM1 if sufijo == "10" else CORTE_CIERRE
    return dt.date(anio, mes, dia)


def ts_fin_del_dia(fecha: dt.date) -> int:
    """Epoch milliseconds (UTC) of the last millisecond of ``fecha`` (the loads are dated in UTC)."""
    inicio = dt.datetime(fecha.year, fecha.month, fecha.day, tzinfo=dt.timezone.utc)
    return int(inicio.timestamp() * 1000) + _UN_DIA_MS - 1


def ts_a_fecha(ts: int) -> dt.date:
    return dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).date()


def anios_con_historial(primera_carga_por_anio: Dict[int, int]) -> Dict[int, bool]:
    """A year has load history iff its first load is dated in the year itself or earlier (the rows were loaded as the year went on).

    Years whose first load came after the year was over (2017-2023 arrived together on 2024-01-08) have no history: that first
    load says nothing about when a row was assigned."""
    return {a: ts_a_fecha(ts).year <= a for a, ts in primera_carga_por_anio.items()}


def ultima_carga_hasta(cargas_ts: Sequence[int], corte_ts: int) -> Optional[int]:
    """Last load (epoch ms) on or before ``corte_ts`` among the sorted loads of a year; None if there is none."""
    arr = np.asarray(cargas_ts, dtype="int64")
    i = int(np.searchsorted(arr, corte_ts, side="right"))
    return int(arr[i - 1]) if i > 0 else None


def visible(first_ts: int, last_ts: int, carga_corte: Optional[int]) -> bool:
    """Is a row visible at the cut whose last load of the year on or before the cut date is ``carga_corte``?"""
    return carga_corte is not None and first_ts <= carga_corte <= last_ts
