"""Programs, course codes, prerequisites and milestone detection (RA10, RA27-RA29)."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Collection, Iterable, List, Optional, Set, Tuple

# ---- course codes (RA28) ----------------------------------------------------
_FMT_STD = re.compile(r"[A-Z]{4}-\d{5}", re.ASCII)
_FMT_ALT = re.compile(r"[A-Z]{3}\d-\d{5}", re.ASCII)


@dataclass(frozen=True)
class CodigoAsignatura:
    codigo: str
    formato: str  # AAAA-99999 | AAA9-99999 | otro


def codigo_asignatura(materia: str, curso: str) -> CodigoAsignatura:
    """``materia`` + ``-`` + ``curso`` (history has no hyphen, malla has one)."""
    code = f"{(materia or '').strip().upper()}-{(curso or '').strip()}"
    if _FMT_STD.fullmatch(code):
        return CodigoAsignatura(code, "AAAA-99999")
    if _FMT_ALT.fullmatch(code):
        return CodigoAsignatura(code, "AAA9-99999")
    return CodigoAsignatura(code, "otro")


# ---- programs (RA10) --------------------------------------------------------
@dataclass(frozen=True)
class ProgramaFlags:
    programa_no_valido: bool
    predecesor_inexistente: bool


def classify_programa(valid_program: bool, programa_predecesor: Optional[int], ids_existentes: Collection[int]) -> ProgramaFlags:
    """Keep every program; only mark invalid ones and predecessors that do not exist."""
    missing = programa_predecesor is not None and programa_predecesor not in ids_existentes
    return ProgramaFlags(programa_no_valido=not bool(valid_program), predecesor_inexistente=missing)


# ---- prerequisites (RA27) ---------------------------------------------------
@dataclass(frozen=True)
class PrereqEdge:
    cod_programa: str
    catalogo: str
    codigo_requisito: str  # codigo_asignatura_repreq: must be approved first
    codigo_asignatura: str  # the course that needs it
    filas_origen: int


def dedupe_prereq(rows: Iterable[Tuple[str, str, str, str]]) -> List[PrereqEdge]:
    """Collapse repeated edges, keeping the source row count.

    Input rows are ``(cod_programa, catalogo, codigo_asignatura, codigo_asignatura_repreq)``.
    The edge direction is requisito -> asignatura (P46).
    """
    counts = Counter((p, c, req, asig) for p, c, asig, req in rows)
    return [PrereqEdge(p, c, req, asig, n) for (p, c, req, asig), n in counts.items()]


def classify_prereq_edge(
    edge: PrereqEdge,
    malla_mismo_catalogo: Collection[str],
    malla_otro_catalogo: Collection[str],
    codigos_otro_programa: Collection[str],
) -> str:
    """Where is the requirement? No edge is ever dropped."""
    req = edge.codigo_requisito
    if req in malla_mismo_catalogo:
        return "misma_malla"
    if req in malla_otro_catalogo:
        return "otro_catalogo"
    if req in codigos_otro_programa:
        return "otro_programa"
    return "ninguna"


@dataclass
class PrereqGraph:
    edges: Set[Tuple[str, str]] = field(default_factory=set)  # (requisito, asignatura)


def prereq_graph(edges: Iterable[PrereqEdge]) -> PrereqGraph:
    return PrereqGraph({(e.codigo_requisito, e.codigo_asignatura) for e in edges})


def is_takeable(course: str, graph: PrereqGraph, approved: Collection[str]) -> bool:
    """A course is takeable when every requirement pointing at it is approved."""
    return all(req in approved for req, target in graph.edges if target == course)


# ---- milestones (RA29) ------------------------------------------------------
@dataclass(frozen=True)
class Hito:
    tipo_hito: str
    metodo: str = "regex_nombre_v1"
    validado: bool = False  # expert review is still required (P26)


_HITO_PATTERNS = [
    ("capstone", re.compile(r"\bCAPSTONE\b", re.I)),
    ("practica", re.compile(r"\bPR[AÁ]CTICA\b", re.I)),
    ("memoria", re.compile(r"\bMEMORIA\b", re.I)),
    ("seminario", re.compile(r"\bSEMINARIO\b", re.I)),
    ("proyecto", re.compile(r"\bPROYECTO\b", re.I)),
]


def detect_hito(nombre: Optional[str]) -> Optional[Hito]:
    """Name-based milestone detection, versioned and never treated as validated."""
    text = nombre or ""
    for tipo, pattern in _HITO_PATTERNS:
        if pattern.search(text):
            return Hito(tipo)
    return None
