"""Academic period parsing: ``AAAA`` + suffix (RA11). Unknown suffixes are kept."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_PERIODO = re.compile(r"(\d{4})(\d{2})", re.ASCII)

ATIPICOS = frozenset({"otro", "excepcional"})

_TIPO = {
    "10": "regular_1",
    "20": "regular_2",
    "15": "invierno",       # P45 (DAI, 13-11-2026): suffix 15 = winter session
    "25": "verano",         # P45: suffix 25 = summer session
    "21": "excepcional",    # P45: suffix 21 = exceptional cases (atypical, kept)
    "50": "postgrado",
    "60": "postgrado",
}


@dataclass(frozen=True)
class PeriodInfo:
    periodo: str
    anio: int
    sufijo: str
    tipo_periodo: str
    periodo_atipico: bool
    orden_regular: Optional[int]


def parse_periodo(periodo: Optional[str]) -> Optional[PeriodInfo]:
    """Parse a 6-digit period. Malformed input returns ``None`` (explicit, caller flags it)."""
    if periodo is None:
        return None
    m = _PERIODO.fullmatch(periodo)
    if not m:
        return None
    anio, sufijo = int(m.group(1)), m.group(2)
    tipo = _TIPO.get(sufijo, "otro")
    orden = anio * 2 + (0 if sufijo == "10" else 1) if tipo in ("regular_1", "regular_2") else None
    return PeriodInfo(
        periodo=periodo,
        anio=anio,
        sufijo=sufijo,
        tipo_periodo=tipo,
        periodo_atipico=(tipo in ATIPICOS),
        orden_regular=orden,
    )


def tipo_periodo(periodo: Optional[str]) -> Optional[str]:
    info = parse_periodo(periodo)
    return info.tipo_periodo if info else None
