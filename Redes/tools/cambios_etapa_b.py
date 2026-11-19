"""Before / after tables of the consolidated rebuild (stage B, 13-11-2026), shared by the ``informe_*`` generators.

The previous aggregate JSONs are kept in ``artefactos/_previo/`` while the report is generated (gitignored, deleted at the end
of stage B); every row is a metric with its 95 % interval before (stage A data, old features) and after. Aggregates only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefactos"
PREVIO = ART / "_previo"
TITULO = "Cambios de la reconstrucción consolidada (13-11-2026)"


def coma(t: str) -> str:
    return t.replace(".", ",")


def cargar_previo(nombre: str) -> Optional[Dict]:
    p = PREVIO / f"{nombre}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ruta(obj, camino: Sequence):
    """Value at ``camino`` (keys / indexes) or ``None`` when any step is missing."""
    x = obj
    for p in camino:
        try:
            x = x[p]
        except (KeyError, IndexError, TypeError):
            return None
    return x


def celda(v, dec: int = 3) -> str:
    """``punto [lo; hi]`` of a metric dict, a plain number, or a dash."""
    if v is None:
        return "—"
    if isinstance(v, dict) and "punto" in v:
        if v["punto"] != v["punto"]:
            return "—"
        if v.get("lo") is None or v["lo"] != v["lo"]:
            return coma(f"{v['punto']:.{dec}f}")
        return coma(f"{v['punto']:.{dec}f} [{v['lo']:.{dec}f}; {v['hi']:.{dec}f}]")
    if isinstance(v, (int, float)):
        return coma(f"{v:.{dec}f}") if isinstance(v, float) else f"{v:,}".replace(",", ".")
    return str(v)


def delta(a, b, dec: int = 3) -> str:
    pa = a["punto"] if isinstance(a, dict) else a
    pb = b["punto"] if isinstance(b, dict) else b
    if pa is None or pb is None or pa != pa or pb != pb:
        return "—"
    return coma(f"{pb - pa:+.{dec}f}")


def tabla(filas: Sequence[Tuple[str, object, object, int]], cab: Tuple[str, str] = ("Antes", "Después")) -> List[str]:
    """``filas``: (etiqueta, antes, después, decimales); values are metric dicts, numbers, strings or ``None``."""
    out = [f"| Métrica | {cab[0]} | {cab[1]} | Cambio |", "|---|---|---|---|"]
    for etq, a, b, d in filas:
        out.append(f"| {etq} | {celda(a, d)} | {celda(b, d)} | {delta(a, b, d) if not isinstance(a, str) and not isinstance(b, str) else '—'} |")
    return out


def sin_previo() -> List[str]:
    return ["No hay resultados previos disponibles para comparar (la carpeta `artefactos/_previo/` ya no existe); consulte la versión anterior de este documento."]
