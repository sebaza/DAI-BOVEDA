"""Admission: score parsing and application-route priority (RA30, RA31)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Mapping, Optional, Sequence, Tuple

_SCORE = re.compile(r"\d+(?:[.,]\d+)?", re.ASCII)

TIPO_ESPECIAL = "2. Ingreso Especial o Directo"
_SELECCION_REGULAR = frozenset({"LS", "RP", "OV", "OA"})
# LE plus the waitlists of special programs (BEA, PACE, Mujeres científicas, Excepción
# Rep). The latter carry tipo_qualitas class 2 but are waitlists (DAI 11-11-2026).
_LISTA_ESPERA = frozenset({"LE", "EB", "EC", "EM", "EP"})


@dataclass(frozen=True)
class ScoreParse:
    value: Optional[Decimal]
    status: str  # ok | vacio | invalido


def parse_score(raw: Optional[str]) -> ScoreParse:
    """Text score -> numeric, or ``None`` with an explicit status (never a silent zero)."""
    if raw is None or not raw.strip():
        return ScoreParse(None, "vacio")
    text = raw.strip()
    if not _SCORE.fullmatch(text):
        return ScoreParse(None, "invalido")
    return ScoreParse(Decimal(text.replace(",", ".")), "ok")


def parse_scores(fields: Mapping[str, Optional[str]]) -> Tuple[Dict[str, Optional[Decimal]], bool]:
    """Parse several score fields; the flag is False if any non-empty value failed to parse."""
    values: Dict[str, Optional[Decimal]] = {}
    ok = True
    for name, raw in fields.items():
        p = parse_score(raw)
        values[name] = p.value
        if p.status == "invalido":
            ok = False
    return values, ok


def via_priority(cod_admision: str, tipo_qualitas: Optional[str]) -> int:
    """Route priority, lower wins: special (1) > regular selection (2) > waitlist (3) > rest (4)."""
    if cod_admision in _LISTA_ESPERA:
        return 3
    if (tipo_qualitas or "").startswith("2."):
        return 1
    if cod_admision in _SELECCION_REGULAR:
        return 2
    return 4


@dataclass(frozen=True)
class Via:
    cod_admision: str
    matricula: str  # 'Y' | 'N'
    tipo_qualitas: Optional[str] = None


@dataclass(frozen=True)
class Postulacion:
    cod_admision_elegida: str
    matricula_elegida: str
    alguna_via_matriculo: bool
    n_vias: int


def derive_postulacion(vias: Sequence[Via]) -> Postulacion:
    """Pick the route for one (year_admision, persona, cod_carrera).

    Lowest priority number wins; a tie goes to the enrolled row ('Y'); any
    remaining tie is broken by ``cod_admision`` so the result is deterministic.
    """
    if not vias:
        raise ValueError("a postulacion needs at least one route")
    best = min(
        vias,
        key=lambda v: (via_priority(v.cod_admision, v.tipo_qualitas), v.matricula != "Y", v.cod_admision),
    )
    return Postulacion(
        cod_admision_elegida=best.cod_admision,
        matricula_elegida=best.matricula,
        alguna_via_matriculo=any(v.matricula == "Y" for v in vias),
        n_vias=len(vias),
    )
