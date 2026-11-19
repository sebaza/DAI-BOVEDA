"""Plain input rows for the pure normalization functions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class EstadoRow:
    """One row of ``ban_estados_academicos`` for a single (already pseudonymized) person."""

    sorlcur: int
    periodo: str
    cod_programa: str
    cod_estado: Optional[str]
    cod_admision: Optional[str]
    periodo_admision: Optional[str]
    catalogo: Optional[str] = None
    fecha_estado: Optional[date] = None


@dataclass(frozen=True)
class NotaRow:
    """One row of ``ban_historia_notas`` (grade text is kept raw)."""

    periodo: str
    cod_carrera: str
    catalogo: Optional[str]
    materia: str
    curso: str
    nota: Optional[str]
    comentario: Optional[str]
    oportunidad: Optional[str]
    nrc: Optional[str]
    creditos: Optional[int] = None
