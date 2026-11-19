"""Rows of ``neural_mart.vista_proyeccion`` (migration 032) from ``artefactos/vista_proyeccion.json`` (aggregates only)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Tuple

UCN = "Toda la UCN"
BLOQUES = ("continuidad", "eliminacion", "egreso", "umbral")
META = ("version", "corte", "filtros", "programas", "modelos", "poblaciones", "sin_proyeccion")


def filas(doc: Mapping[str, Any]) -> List[Tuple[str, str, str]]:
    """``(bloque, facultad, contenido_json)`` rows: one per block and filter, plus ``meta`` under "Toda la UCN"."""
    out: List[Tuple[str, str, str]] = [("meta", UCN, _json({k: doc.get(k) for k in META}))]
    for bloque in BLOQUES:
        for filtro, contenido in sorted((doc.get(bloque) or {}).items()):
            out.append((bloque, filtro, _json(contenido)))
    return out


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, allow_nan=False)


def escribir(conn, doc: Mapping[str, Any], mart_schema: str = "neural_mart") -> Dict[str, int]:
    """Replace the content of ``vista_proyeccion`` in ONE transaction (a failure leaves the previous content)."""
    from ..migrate import ALLOWED_SCHEMAS

    if mart_schema not in ALLOWED_SCHEMAS:
        raise ValueError(f"schema {mart_schema!r} is not one of {ALLOWED_SCHEMAS}")
    rows = filas(doc)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {mart_schema}.vista_proyeccion")
            cur.executemany(
                f"INSERT INTO {mart_schema}.vista_proyeccion (bloque, facultad, contenido) VALUES (%s, %s, %s::jsonb)", rows)
    return {"vista_proyeccion": len(rows)}
