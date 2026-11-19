"""Sections, teachers and graduations (RA24, RA25, RA33)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Set, Tuple

OFERTA_DESDE = "201610"  # the academic offer exists from 2016 on (R13)


@dataclass
class SeccionIndex:
    secciones: Set[Tuple[str, str]] = field(default_factory=set)
    puente: Set[Tuple[str, str, str]] = field(default_factory=set)  # (periodo, nrc, docente_key)

    @classmethod
    def from_oferta(cls, rows: Iterable[Tuple[str, str, Optional[str]]]) -> "SeccionIndex":
        """Build the section set (DISTINCT periodo, nrc) and the many-to-many teacher bridge."""
        idx = cls()
        for periodo, nrc, docente in rows:
            idx.secciones.add((periodo, nrc))
            if docente:
                idx.puente.add((periodo, nrc, docente))
        return idx


@dataclass(frozen=True)
class SeccionLink:
    tiene_seccion: bool
    docentes: Optional[Tuple[str, ...]]  # None = unknown teacher (not "zero teachers")
    anterior_a_oferta: bool


def link_intento_to_section(periodo: str, nrc: str, idx: SeccionIndex) -> SeccionLink:
    """One attempt links to one section; teachers come from the bridge and never multiply attempts."""
    if periodo < OFERTA_DESDE:
        return SeccionLink(False, None, True)
    if (periodo, nrc) not in idx.secciones:
        return SeccionLink(False, None, False)
    docentes = tuple(sorted(d for p, n, d in idx.puente if (p, n) == (periodo, nrc)))
    return SeccionLink(True, docentes, False)


def titulacion_key(persona_key: str, codigo_carrera: str, catalogo: Optional[str], fecha_titulacion: Optional[str]):
    """Natural key of a graduation; one person may have several (double degree)."""
    return (persona_key, codigo_carrera, catalogo, fecha_titulacion)
