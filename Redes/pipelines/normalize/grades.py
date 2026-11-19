"""Grade parsing and result classification (RA12-RA23).

Nothing here fails silently: unparseable text is reported as ``invalid`` and the
row becomes ``resultado_tipo='otro'``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional, Sequence, Tuple

APROBACION_MINIMA = Decimal("4.0")
NOTA_MIN = Decimal("0")
NOTA_MAX = Decimal("7.0")

_NUMERIC = re.compile(r"^\d+(?:[.,]\d+)?$")


@dataclass(frozen=True)
class GradeParse:
    kind: str  # numeric | dpa | empty | invalid
    value: Optional[Decimal]
    raw: Optional[str]


def parse_grade_text(raw: Optional[str]) -> GradeParse:
    """Parse a grade text. Comma or dot decimals; ``DPA``; empty; invalid."""
    if raw is None or not raw.strip():
        return GradeParse("empty", None, raw)
    text = raw.strip()
    if text.upper() == "DPA":
        return GradeParse("dpa", None, raw)
    if not _NUMERIC.match(text):
        return GradeParse("invalid", None, raw)
    value = Decimal(text.replace(",", "."))
    if not (NOTA_MIN <= value <= NOTA_MAX):
        return GradeParse("invalid", None, raw)
    return GradeParse("numeric", value, raw)


@dataclass(frozen=True)
class ResultadoIntento:
    resultado_tipo: str  # evaluado | convalidacion | renuncia | en_curso | otro
    nota_numerica: Optional[Decimal]
    nota_es_heredada: bool
    aprobado_curricular: Optional[bool]
    es_intento_evaluado: bool
    nota_parse: str
    fuente_resultado: str
    comentario_codigo: Optional[str] = None
    aprobacion_discrepa: bool = False


def _passes(value: Decimal) -> bool:
    return value >= APROBACION_MINIMA


def classify_historia(
    nota: Optional[str],
    comentario: Optional[str] = None,
    oportunidad: object = None,  # noqa: ARG001 - kept on purpose: opportunity never changes the rule (RA23)
) -> ResultadoIntento:
    """Classify a ``ban_historia_notas`` row."""
    p = parse_grade_text(nota)
    code = (comentario or "").strip().upper() or None
    common = dict(nota_parse=p.kind, fuente_resultado="historia", comentario_codigo=code)

    if p.kind == "dpa":
        return ResultadoIntento("convalidacion", None, False, True, False, **common)
    if code == "CONVA":
        if p.kind == "numeric":
            return ResultadoIntento("convalidacion", p.value, True, _passes(p.value), False, **common)
        return ResultadoIntento("convalidacion", None, False, None, False, **common)
    if p.kind == "numeric":
        return ResultadoIntento("evaluado", p.value, False, _passes(p.value), True, **common)
    return ResultadoIntento("otro", None, False, None, False, **common)


def classify_inscripcion(
    nota: Optional[str], aprobacion: Optional[str], estado: Optional[str]
) -> ResultadoIntento:
    """Classify a ``ban_inscripciones`` row."""
    p = parse_grade_text(nota)
    status = (estado or "").strip().upper()
    label = (aprobacion or "").strip().upper() or None
    common = dict(nota_parse=p.kind, fuente_resultado="inscripcion")

    if status.startswith("RENUNCIADA"):
        return ResultadoIntento("renuncia", None, False, False, False, **common)
    if status.startswith("CONV"):
        approved = label == "APROBADA"
        if p.kind == "numeric":
            return ResultadoIntento("convalidacion", p.value, True, approved, False, **common)
        return ResultadoIntento("convalidacion", None, False, approved, False, **common)
    if p.kind == "dpa":
        return ResultadoIntento("convalidacion", None, False, True, False, **common)
    if status == "INSCRITO":
        if label is None:
            return ResultadoIntento("en_curso", None, False, None, False, **common)
        if p.kind == "numeric":
            by_grade = _passes(p.value)
            by_label = label == "APROBADA"
            return ResultadoIntento(
                "evaluado", p.value, False, by_grade, True,
                aprobacion_discrepa=(by_grade != by_label), **common,
            )
        return ResultadoIntento("otro", None, False, label == "APROBADA", False, **common)
    return ResultadoIntento("otro", None, False, None, False, **common)


def average_grade(results: Iterable[ResultadoIntento]) -> Optional[Decimal]:
    """Mean of numeric grades of evaluated attempts only (never DPA / CONVA / renuncia)."""
    values = [r.nota_numerica for r in results if r.es_intento_evaluado and r.nota_numerica is not None]
    if not values:
        return None
    return sum(values, Decimal("0")) / len(values)


def approval_rate_by_attempt(results: Iterable[ResultadoIntento]) -> Tuple[int, int]:
    """``(approved, total)`` over evaluated attempts; the caller reports both."""
    evaluated = [r for r in results if r.es_intento_evaluado]
    return sum(1 for r in evaluated if r.aprobado_curricular), len(evaluated)


def credits_recognized(items: Iterable[Tuple[str, int, Optional[bool]]]) -> int:
    """Credits recognized once per equivalence group.

    ``items`` are ``(equivalencia_key, creditos, aprobado_curricular)``; only
    ``True`` counts, and an equivalence group contributes its largest credit
    value once (no double counting between an approval and its convalidation).
    """
    best: dict = {}
    for key, creditos, approved in items:
        if approved is True:
            best[key] = max(best.get(key, 0), creditos or 0)
    return sum(best.values())


def flag_duplicate_renuncias(rows: Sequence[Tuple[str, str, str, str]]) -> list:
    """Flag repeated renuncias to the same course by the same person.

    ``rows`` are ``(persona_key, periodo, codigo_asignatura, resultado_tipo)``.
    The earliest renuncia (by period, then input order) counts; later ones are
    anomalies. Returns booleans aligned with the input.
    """
    flags = [False] * len(rows)
    order = sorted(
        (i for i, r in enumerate(rows) if r[3] == "renuncia"),
        key=lambda i: (rows[i][0], rows[i][2], rows[i][1], i),
    )
    seen = set()
    for i in order:
        key = (rows[i][0], rows[i][2])
        if key in seen:
            flags[i] = True
        seen.add(key)
    return flags


def flag_replaced_same_period(rows: Sequence[Tuple[object, Optional[int], int, int]]) -> list:
    """P54 (DAI, 13-11-2026): flag the EVALUATED rows replaced by a later attempt of the same period.

    ``rows`` are ``(group, oportunidad, carga_id, row_id)`` of evaluated rows, where ``group`` identifies one
    (persona, periodo, asignatura). In each group the result is the row with the highest ``oportunidad``; a tie goes to
    the most recent load (``carga_id``) and then to the latest row (``row_id``); a missing ``oportunidad`` loses to any
    number. Every other row of the group is returned ``True`` (kept in core, out of the evaluated attempts). The output
    is aligned with the input.
    """
    best: dict = {}
    for i, (group, oportunidad, carga, row_id) in enumerate(rows):
        rank = (-1 if oportunidad is None else oportunidad, carga, row_id)
        if group not in best or rank > best[group][0]:
            best[group] = (rank, i)
    return [best[group][1] != i for i, (group, *_rest) in enumerate(rows)]
