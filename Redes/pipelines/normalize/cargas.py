"""Load (carga) selection: the vigente load wins, never the max timestamp (RA32)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence


def pick_vigente(cargas: Sequence[Mapping]) -> Mapping:
    """Return the single load flagged ``vigente``; zero or several is an error."""
    vigentes = [c for c in cargas if c.get("vigente") is True]
    if len(vigentes) != 1:
        raise ValueError(f"expected exactly one vigente load, found {len(vigentes)}")
    return vigentes[0]


def epoch_ms_to_datetime(ms: int) -> datetime:
    """``timestamp_carga`` is epoch milliseconds."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
