"""Pure rules of the new variables of T3-T6 (docs/10, 11 and 12, section "variables nuevas"; DAI answers P117, P118, P121,
P122, P125, P126).

* Academic regulation: the old one (Art. 50 Ciclo Basico / Art. 52 Ciclo Profesional, until 202510) and the new one (Art. 46,
  from 202520). The thresholds below are the ones the DAI gave in P117 / P118; the distances to them are computed under
  BOTH regulations at every cut, so a model never has to guess which one applies.
* Cycle: the suffix ``CB`` / ``CP`` of the malla semester text (P122).
* Reach (``alcance``, P121): a student cannot enrol a course more than four semesters ahead of the oldest pending course.
* Courses identified by name (P125): Capstone Project, titulo / grado activities and professional practice.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

REGLAMENTO_NUEVO_DESDE = "202520"       # first period governed by Art. 46 (P118); the 5x causal codes start here
# Old regulation (Art. 50 Ciclo Basico, Art. 52 Ciclo Profesional): a student is eliminated at or above these counts.
UMBRAL_2DA_CB_ANTIGUO = 5               # "more than four" courses failed in the 2nd opportunity (50-C)
UMBRAL_2DA_CP_ANTIGUO = 3               # "three or more" Ciclo Profesional courses failed in the 2nd opportunity (52-A)
UMBRAL_3RA_ANTIGUO = 1                  # one course failed in the 3rd opportunity (50-B, 52-B)
PERIODOS_AVANCE_ANTIGUO = 2             # progress below 50 % in two consecutive periods (52-C)
AVANCE_MINIMO = 0.5
# New regulation (Art. 46, from 202520).
UMBRAL_2DA_NUEVO = 6                    # six or more failures in the 2nd opportunity over the career (46-A)
UMBRAL_3RA_NUEVO = 2                    # two distinct courses failed in the 3rd opportunity (46-B)
ALCANCE_SEMESTRES = 4                   # "elastic band" of the reach rule (P121)
# A malla total is plausible when its credits per nominal semester are near the 30-credit scale seen in the malla
# (after collapsing the elective pools); outside this range the plan is partial or in another unit (P126).
CREDITOS_POR_SEMESTRE_MIN, CREDITOS_POR_SEMESTRE_MAX = 15.0, 40.0
MIN_PARES_RANKING = 10                  # peers needed for a graduation ranking


def reglamento_vigente(periodo: Optional[str]) -> Optional[str]:
    """``antiguo`` before 202520, ``nuevo`` from then on (``None`` for a malformed period)."""
    if not isinstance(periodo, str) or len(periodo) != 6 or not periodo.isdigit():
        return None
    return "nuevo" if periodo >= REGLAMENTO_NUEVO_DESDE else "antiguo"


def ciclo_de_semestre_texto(texto: Optional[str]) -> Optional[str]:
    """``CB`` / ``CP`` suffix of a malla semester text («Semestre 03 CP», «Año 02 CB»); ``None`` when there is none (P122)."""
    if not isinstance(texto, str):
        return None
    m = re.search(r"\b(CB|CP)\s*$", texto.strip().upper())
    return m.group(1) if m else None


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", base.lower().replace("�", "")).strip()


_CAPSTONE = re.compile(r"\bcapstone\b")
_CAPSTONE_INTRO = re.compile(r"^(int\.?|introduccion) al capstone")
_TITULO = re.compile(r"(actividad|trabajo|examen|proyecto|anteproyecto|seminario|memoria|tesis)( de| del)? ?(titulo|titulacion|grado|memoria)"
                     r"|^memoria\b|^tesis\b|^examen de grado")
_PRACTICA = re.compile(r"^(practica\b|internado\b)")


def clasificar_titulo(nombre: Optional[str]) -> Optional[str]:
    """``capstone`` / ``titulo`` / ``practica`` from the course name (P125), else ``None``.

    The introduction to the Capstone is not the Capstone; «Derecho y practica medica» or «filosofia practica» are not practice
    (the match is on the START of the name). Priority: capstone, titulo, practica.
    """
    if not isinstance(nombre, str) or not nombre.strip():
        return None
    t = _normalizar(nombre)
    if _CAPSTONE.search(t):
        return None if _CAPSTONE_INTRO.search(t) else "capstone"
    if _TITULO.search(t):
        return "titulo"
    if _PRACTICA.search(t):
        return "practica"
    return None


def tipo_formacion(codigo: Optional[str]) -> str:
    """``propia`` / ``general`` / ``otra`` from the ``malla_formacion`` code of a course of the malla.

    P40: the prefixes are department codes (``depto`` UNFP = Formacion Profesional, UNFG = Formacion General, UNFV = Formacion
    General Valorica; UNFE are the general electives). ``general`` = UNFG / UNFV / UNFE (transversal formation of the
    university); ``propia`` = UNFP (professional formation) or no code at all (the disciplinary core of the program: basic
    sciences, own departments); ``otra`` = the minor prefixes (UNFI, UNFC, UNES, UNFB). The meaning is the study's reading of the
    codes and stays open with the DAI.
    """
    if not isinstance(codigo, str) or not codigo:
        return "propia"
    return {"UNFP": "propia", "UNFG": "general", "UNFV": "general", "UNFE": "general"}.get(codigo[:4], "otra")
