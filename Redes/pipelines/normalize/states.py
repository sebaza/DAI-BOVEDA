"""State dictionary (R01 + approved ``clase_estado``) and canonical ordering (RA01-RA06)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from .models import EstadoRow

# cod_estado -> (nombre_estado as in R01, clase_estado approved in 05 section 3, M4)
ESTADOS: Dict[str, Tuple[str, str]] = {
    "M": ("Matriculado", "matricula"),
    "J": ("Matrícula en Trámite", "matricula"),
    "N": ("Nuevo", "matricula"),
    "Ñ": ("Matricula Fuera Periodo", "matricula"),
    "P": ("Retiro Temporal", "interrupcion"),
    "Q": ("Retiro Temporal Excepción", "interrupcion"),
    "4": ("Suspensión Temporal", "interrupcion"),
    "A": ("Anulación de Semestre", "interrupcion"),
    "S": ("Intercambio Saliente Total", "interrupcion"),
    "#": ("Intercambio Saliente Parcial", "interrupcion"),
    "E": ("Eliminado", "salida"),
    "B": ("Renuncia Alumno", "salida"),
    "F": ("Renuncia Admisión", "salida"),
    "O": ("No Continuidad", "salida"),
    "R": ("Retracto", "salida"),
    "3": ("No Matricula Admision", "salida"),
    "9": ("Matricula Anulada", "salida"),
    "X": ("Expulsado", "salida"),
    "6": ("Sancionado Eliminado", "salida"),
    "H": ("Sancionado", "salida"),
    "I": ("Reintegro", "reingreso"),
    "Y": ("Reintegro por Rectificación", "reingreso"),
    "D": ("Cambio de Ciclo", "cambio_ciclo"),
    "G": ("Egresado", "egreso_titulacion"),
    "Z": ("Malla Completa", "egreso_titulacion"),
    "K": ("Expediente Titulo", "egreso_titulacion"),
    "L": ("Licenciado", "egreso_titulacion"),
    "U": ("Titulado", "egreso_titulacion"),
    "1": ("Reversa Cambio Ciclo Prof", "correccion_sistema"),
    "2": ("Reversa G, K, Reciclaje, CPlan", "correccion_sistema"),
    "5": ("Reversa Malla Completa", "correccion_sistema"),
    "T": ("Intercambio Entrante", "otro"),
    "0": ("No Regular", "otro"),
}

CORRECCION_SISTEMA = frozenset(c for c, (_, clase) in ESTADOS.items() if clase == "correccion_sistema")


@dataclass(frozen=True)
class EstadoInfo:
    cod_estado: Optional[str]
    nombre_estado: Optional[str]
    clase_estado: str
    es_correccion_sistema: bool
    conocido: bool
    sin_codigo: bool


def classify_estado(cod_estado: Optional[str]) -> EstadoInfo:
    """Look a state code up. Unknown codes and NULL are kept, never rejected (RA05)."""
    code = (cod_estado or "").strip() or None
    if code is None:
        return EstadoInfo(None, None, "otro", False, False, True)
    if code not in ESTADOS:
        return EstadoInfo(code, None, "otro", False, False, False)
    nombre, clase = ESTADOS[code]
    return EstadoInfo(code, nombre, clase, code in CORRECCION_SISTEMA, True, False)


def canonical_order(rows: Sequence[EstadoRow]) -> list:
    """Order one person's states by (``periodo``, ``sorlcur``). Both stay as attributes.

    ``sorlcur`` is unique per person (C01); a duplicate is a data error and
    raises instead of being silently resolved.
    """
    seen = set()
    for r in rows:
        if r.sorlcur in seen:
            raise ValueError(f"duplicate sorlcur {r.sorlcur} for one person")
        seen.add(r.sorlcur)
    return sorted(rows, key=lambda r: (r.periodo, r.sorlcur))
