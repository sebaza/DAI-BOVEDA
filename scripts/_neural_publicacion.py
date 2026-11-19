"""Shared pieces of the Neural publication to GitHub Pages: canonical key, combinations to publish, identity gate.

The canonical key (`canonizar`) is the lookup key of a stored response; the same rules are ported to Node in wh-api and checked
against the same fixture (backend/tests/fixtures/neural_canon_casos.json). No database access here.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, quote, urlsplit, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.neural.rules import TIPOS_TRASLADO  # noqa: E402

_UCN = "Toda la UCN"  # the unfiltered entry of the faculty cascade: published as the URL without a query
_ESCAPE_INVALIDO = re.compile(r"%(?![0-9A-Fa-f]{2})")
_NIVELES = ("programa", "facultad", "sexo", "via", "tipo_colegio")
_SEMESTRE_MAX_MALLA = 4

# Identity keys that must never reach the published responses (at any depth).
_CLAVES_IDENTIDAD = frozenset({
    "rut", "dv", "paterno", "materno", "nombre_estud", "nombre_prof", "nombre_banner", "email", "correo", "telefono",
    "fecha_nacimiento", "docente_key", "nrc", "seccion", "id_estudiante", "pidm",
})


def canonizar(url: str) -> tuple[str, str]:
    """Canonical (path, query) of a route URL: the lookup key of a stored response.

    The path is percent-decoded and loses a trailing slash (the root stays). The query is decoded (UTF-8, ``+`` is a space),
    loses empty values, is sorted by key then value and is joined as ``k=v`` with ``&`` without re-encoding.

    Strict: raises ValueError on a ``%`` not followed by two hex digits or on escapes that are not valid UTF-8 (the Node port
    answers 404 in both cases)."""
    partes = urlsplit(url)
    if _ESCAPE_INVALIDO.search(partes.path) or _ESCAPE_INVALIDO.search(partes.query):
        raise ValueError(f"invalid percent escape in {url!r}")
    ruta = unquote(partes.path, errors="strict")
    if len(ruta) > 1:
        ruta = ruta.rstrip("/") or "/"
    pares = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True, encoding="utf-8", errors="strict") if v != ""]
    return ruta, "&".join(f"{k}={v}" for k, v in sorted(pares))


def _enc(valor: object) -> str:
    """``encodeURIComponent`` of the frontend."""
    return quote(str(valor), safe="-_.!~*'()")


def _con_query(ruta: str, pares: list[tuple[str, str]]) -> str:
    return ruta + ("?" + "&".join(f"{k}={v}" for k, v in pares) if pares else "")


def _consultas_traslados(max_anio: int | None) -> list[list[tuple[str, str]]]:
    """The 42 queries of the transfers views, in the order the frontend builds them (anio_desde, tipo, solo_abandono).
    Without ``anio_hasta``: the published site never sets it."""
    desdes: list[int | None] = [None]
    if max_anio is not None:
        desdes += [max_anio - 9, max_anio - 4]
    tipos: list[str | None] = [None, *TIPOS_TRASLADO]
    consultas = []
    for desde in desdes:
        for tipo in tipos:
            for solo in (False, True):
                pares: list[tuple[str, str]] = []
                if desde is not None:
                    pares.append(("anio_desde", str(desde)))
                if tipo:
                    pares.append(("tipo", tipo))
                if solo:
                    pares.append(("solo_abandono", "true"))
                consultas.append(pares)
    return consultas


def _filtros_de(respuesta: dict) -> list[str]:
    """URLs of one view (historico / proyeccion): without filter, then each faculty and each program of its own hierarchy."""
    facultades: list[str] = []
    programas: list[str] = []
    for f in respuesta.get("jerarquia") or []:
        if f.get("facultad") != _UCN:
            facultades.append(f["facultad"])
        programas.extend(p["codigo"] for p in f.get("programas") or [])
    return [*(f"?facultad={_enc(x)}" for x in facultades), *(f"?programa={_enc(x)}" for x in programas)]


def _sin_repetir(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def combinaciones(get: Callable[[str], dict]) -> list[str]:
    """Exact URLs (path plus query, as ``frontend/src/lib/neural.ts`` builds them) of the responses to publish.

    ``get`` returns the JSON of a listing route; it is only called for the listings the combinations derive from."""
    urls: list[str] = ["/neural/aceptacion", "/neural/programas", "/neural/calidad", "/neural/modelos/resumen",
                       "/neural/modelos/tareas"]

    for vista in ("historico", "proyeccion"):
        ruta = f"/neural/{vista}"
        urls.append(ruta)
        urls.extend(ruta + q for q in _filtros_de(get(ruta)))

    programas = [p["cod_programa"] for p in get("/neural/programas")]
    urls.extend(f"/neural/programa/{_enc(c)}/cohortes" for c in programas)

    for t in (x["tarea"] for x in get("/neural/modelos/tareas")["tareas"]):
        urls.append(f"/neural/modelos/tarea/{t}")
        niveles = [*_NIVELES, "nivel_postgrado"] if t == "t6" else _NIVELES
        for v in get(f"/neural/modelos/tarea/{t}")["vistas"]:
            for n in niveles:
                urls.append(f"/neural/modelos/tarea/{t}/grupos?nivel={n}&variante={_enc(v['variante'])}&corte={v['corte_k']}")

    malla = f"/neural/modelos/malla-ejemplo?semestre_max={_SEMESTRE_MAX_MALLA}"
    urls.append(malla)
    urls.extend(f"{malla}&cod_programa={_enc(c)}" for c in programas)

    resumen = get("/neural/traslados/resumen")
    consultas = _consultas_traslados((resumen.get("anios_disponibles") or {}).get("hasta"))
    urls.extend(_con_query("/neural/traslados/resumen", q) for q in consultas)
    con_balance = _sin_repetir([*programas, *(b["cod_programa"] for b in resumen.get("balance") or [])])
    for c in con_balance:
        urls.extend(_con_query(f"/neural/traslados/programa/{_enc(c)}", q) for q in consultas)

    return _sin_repetir(urls)


def revisar_identidad(obj: object) -> list[str]:
    """JSON paths of every offending key: an identity key at any depth, or a non-empty list under a key ending in
    ``_estudiantes``. Empty means clean. Keys are compared case-insensitively (a port must do the same). The bare ``nombre`` is not
    an identity key: programs, groups, models and courses carry it in every public response."""
    ofensores: list[str] = []

    def recorrer(valor: object, ruta: str) -> None:
        if isinstance(valor, dict):
            for k, v in valor.items():
                sub = f"{ruta}.{k}" if ruta else str(k)
                clave = str(k).lower()
                if clave in _CLAVES_IDENTIDAD or (clave.endswith("_estudiantes") and isinstance(v, list) and v):
                    ofensores.append(sub)
                recorrer(v, sub)
        elif isinstance(valor, list):
            for i, v in enumerate(valor):
                recorrer(v, f"{ruta}[{i}]")

    recorrer(obj, "")
    return ofensores
