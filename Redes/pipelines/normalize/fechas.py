"""NULL-date interval imputation and future-date markers (RA03, RA04).

The original date is never overwritten and no event is ever created.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from .models import EstadoRow


@dataclass(frozen=True)
class FechaInfo:
    fecha_estado: Optional[date]  # original value, untouched
    fecha_min: Optional[date]
    fecha_max: Optional[date]
    fecha_aproximada: bool
    sin_intervalo: bool
    intervalo_invertido: bool
    fecha_marcador: bool  # date after the extraction cutoff: a future-state marker


def usable_date(info: FechaInfo) -> Optional[date]:
    """The date that may anchor time-to-event: real, non-future and present."""
    if info.fecha_estado is None or info.fecha_marcador:
        return None
    return info.fecha_estado


def impute_dates(ordered: Sequence[EstadoRow], corte: date) -> list:
    """Per-state date info for rows already in canonical order.

    A date after ``corte`` is a marker: it keeps its value but is neither a
    neighbour for other rows nor an anchor.
    """
    markers = [r.fecha_estado is not None and r.fecha_estado > corte for r in ordered]
    usable = [None if (r.fecha_estado is None or m) else r.fecha_estado for r, m in zip(ordered, markers)]
    n = len(ordered)

    prev = [None] * n
    last = None
    for i in range(n):
        prev[i] = last
        if usable[i] is not None:
            last = usable[i]
    nxt = [None] * n
    last = None
    for i in range(n - 1, -1, -1):
        nxt[i] = last
        if usable[i] is not None:
            last = usable[i]

    out = []
    for i, r in enumerate(ordered):
        if markers[i]:
            out.append(FechaInfo(r.fecha_estado, None, None, False, False, False, True))
        elif usable[i] is not None:
            out.append(FechaInfo(r.fecha_estado, usable[i], usable[i], False, False, False, False))
        else:
            lo, hi = prev[i], nxt[i]
            if lo is None and hi is None:
                out.append(FechaInfo(None, None, None, False, True, False, False))
            elif lo is not None and hi is not None and lo > hi:
                out.append(FechaInfo(None, None, None, False, True, True, False))
            else:
                out.append(FechaInfo(None, lo, hi, True, False, False, False))
    return out
