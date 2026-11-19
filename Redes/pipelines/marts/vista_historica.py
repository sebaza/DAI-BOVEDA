"""Rows of ``neural_mart.vista_historica`` (migration 029) from ``artefactos/vista_historica.json`` (aggregates only)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Tuple

UCN = "Toda la UCN"
BLOQUES = ("semestres", "siguieron", "eliminados", "alcance", "perfil_ingreso", "primer_semestre", "ramos_reprobados", "ramos_esperado",
           "cuellos_botella", "semestre_malla", "causales_programa", "tiempo_egreso", "senales", "esperar_semestre")
META = ("version", "modelo_t1", "modelo_t5", "filtros", "programas", "modelos", "cohortes", "periodo_causales_desde")


def filas(doc: Mapping[str, Any]) -> List[Tuple[str, str, str]]:
    """``(bloque, facultad, contenido_json)`` rows: one per block and filter, plus ``meta`` and ``por_facultad`` under "Toda la UCN"."""
    out: List[Tuple[str, str, str]] = [("meta", UCN, _json({k: doc.get(k) for k in META}))]
    for bloque in BLOQUES:
        for filtro, contenido in sorted((doc.get(bloque) or {}).items()):
            out.append((bloque, filtro, _json(contenido)))
    if doc.get("por_facultad"):
        out.append(("por_facultad", UCN, _json(doc["por_facultad"])))
    return out


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, allow_nan=False)


def escribir(conn, doc: Mapping[str, Any], mart_schema: str = "neural_mart") -> Dict[str, int]:
    """Replace the content of ``vista_historica`` in ONE transaction (a failure leaves the previous content)."""
    from ..migrate import ALLOWED_SCHEMAS

    if mart_schema not in ALLOWED_SCHEMAS:
        raise ValueError(f"schema {mart_schema!r} is not one of {ALLOWED_SCHEMAS}")
    rows = filas(doc)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {mart_schema}.vista_historica")
            cur.executemany(
                f"INSERT INTO {mart_schema}.vista_historica (bloque, facultad, contenido) VALUES (%s, %s, %s::jsonb)", rows)
    return {"vista_historica": len(rows)}
