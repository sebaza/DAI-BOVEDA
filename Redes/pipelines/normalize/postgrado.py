"""Postgrado programs: level from the standard name (P77) and the semester of a postgrado period (P79)."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

NIVELES = ("magister", "doctorado", "diplomado", "otro", "sin_nombre")

_PERIODO = re.compile(r"(\d{4})(10|20|50|60)", re.ASCII)


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _prefijo(nombre: Optional[str]) -> Optional[str]:
    t = _sin_tildes((nombre or "").strip()).upper()
    if t.startswith("MAGISTER"):
        return "magister"
    if t.startswith("DOCTOR"):
        return "doctorado"
    if t.startswith("DIPLOMADO"):
        return "diplomado"
    return None


def nivel_postgrado(nombre_estandar: Optional[str], nombre_banner: Optional[str] = None) -> str:
    """``magister`` / ``doctorado`` / ``diplomado`` / ``otro`` (post-titulo, medical specialty) / ``sin_nombre``.

    The standard name decides. Without it the Banner name is used only when it starts with the full word (``Magister``,
    ``Doct...``, ``Diplomado``); an abbreviation (``Mg``, ``Doc``) or a fictitious program is not derivable.
    """
    if (nombre_estandar or "").strip():
        return _prefijo(nombre_estandar) or "otro"
    return _prefijo(nombre_banner) or "sin_nombre"


def ordinal_estado_postgrado(periodo: Optional[str]) -> Optional[int]:
    """Calendar-semester ordinal of a postgrado state period: ``AAAA50`` / ``AAAA10`` -> first semester of ``AAAA``,
    ``AAAA60`` / ``AAAA20`` -> second (P79). Any other suffix gives ``None``."""
    m = _PERIODO.fullmatch(periodo or "")
    if not m:
        return None
    return int(m.group(1)) * 2 + (0 if m.group(2) in ("10", "50") else 1)
