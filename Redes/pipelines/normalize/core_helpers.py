"""Small pure helpers for ``build_core``: sex resolution, text parsing, duplicate handling."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple


_SEXO_ALIASES = {"MASCULINO": "M", "HOMBRE": "M", "M": "M", "FEMENINO": "F", "MUJER": "F", "F": "F"}


def normalize_sexo(raw: Optional[str]) -> Optional[str]:
    """States use MASCULINO/FEMENINO and admission M/F: both map to M/F. Any other label is kept as is."""
    text = (raw or "").strip().upper()
    if not text:
        return None
    return _SEXO_ALIASES.get(text, text)


def resolve_sexo(by_source: Mapping[str, Iterable[Optional[str]]]) -> Tuple[Optional[str], bool]:
    """Single value across all sources, or ``(None, True)`` when they disagree (never guessed)."""
    seen = set()
    for values in by_source.values():
        for v in values:
            norm = normalize_sexo(v)
            if norm:
                seen.add(norm)
    if not seen:
        return None, False
    if len(seen) == 1:
        return next(iter(seen)), False
    return None, True


_INT = re.compile(r"[+-]?\d+(?:\.0+)?", re.ASCII)


def parse_int_text(raw: Optional[str]) -> Optional[int]:
    """Integer in text form (``'3'``, ``'3.0'``); anything else is ``None``."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not _INT.fullmatch(text):
        return None
    return int(Decimal(text))


def parse_decimal_text(raw: Optional[str]) -> Optional[Decimal]:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d", "%d-%m-%Y", "%Y/%m/%d")


def parse_date_text(raw: Optional[str]) -> Optional[date]:
    """Date in text form; a time part after the date is ignored. Unparseable is ``None``."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    head = re.split(r"[ T]", text, maxsplit=1)[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(head, fmt).date()
        except ValueError:
            continue
    return None


_SEMESTRE = re.compile(r"Semestre\s+(\d+)(?:\s+(CB|CP))?", re.ASCII | re.IGNORECASE)


def parse_semestre(raw: Optional[str]) -> Optional[int]:
    """``'Semestre 09 CP'`` -> 9. Annual or area labels (``'Año 01'``) are not semesters -> ``None``;
    a bare integer is accepted. The original label is kept elsewhere."""
    if raw is None:
        return None
    text = str(raw).strip()
    m = _SEMESTRE.fullmatch(text)
    if m:
        return int(m.group(1))
    return parse_int_text(text)


def tipo_renuncia(estado: Optional[str]) -> Optional[str]:
    """``RENUNCIADA MANUAL|WF|WEB`` -> the channel; any other state -> ``None``."""
    status = (estado or "").strip().upper()
    if not status.startswith("RENUNCIADA"):
        return None
    return status[len("RENUNCIADA"):].strip() or None


_MALLA_FIELDS = ("semestre", "creditos", "formacion", "nombre", "area", "depto", "depto_desc")


def _sort_key(row: Mapping[str, Optional[str]]) -> tuple:
    def semestre(v):
        n = parse_semestre(v)
        return (1, 0) if n is None else (0, n)

    return (semestre(row.get("semestre")),) + tuple(
        (1, "") if row.get(f) is None else (0, str(row.get(f))) for f in _MALLA_FIELDS[1:]
    )


def choose_malla_row(rows: Sequence[Mapping[str, Optional[str]]]) -> Tuple[Mapping[str, Optional[str]], bool, int]:
    """Collapse source rows of one (programa, catalogo, asignatura).

    Returns ``(chosen_row, atributos_conflicto, filas_origen)``. Identical rows are not a conflict;
    otherwise the row with the lowest semester (NULLs last) wins deterministically and the conflict
    is flagged, so nothing is silently merged.
    """
    ordered: List[Mapping[str, Optional[str]]] = sorted(rows, key=_sort_key)
    distinct = {tuple(r.get(f) for f in _MALLA_FIELDS) for r in ordered}
    return ordered[0], len(distinct) > 1, len(ordered)
