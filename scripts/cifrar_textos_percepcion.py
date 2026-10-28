"""Cifra EN SITIO el texto de comentarios y los captions ya guardados (fase A2).

QUÉ HACE
--------
Recorre `percepcion_comentario.texto` y `percepcion_publicacion.caption` y reemplaza cada
valor en claro por su versión cifrada (AES-256-GCM, ver `services/percepcion/cripto.py`).
Todo en UNA transacción: si algo falla no queda nada a medias. Es idempotente: solo toca las
filas que no están ya en el estado destino, así que se puede repetir.

* `--dry-run`: solo cuenta cuántas filas cambiarían (no escribe ni necesita claves).
* `--descifrar`: operación inversa (rollback). Necesita las mismas claves.
* Si una columna tuviera un largo máximo que el texto cifrado pudiera exceder, la ensancha a
  TEXT (solo Postgres, como dueño, solo si hace falta). En las bases del proyecto ya son TEXT.

CONEXIÓN
--------
`--url` o `PERCEPCION_ADMIN_DATABASE_URL`: hace falta el rol DUEÑO (los roles de la app no
pueden hacer UPDATE de estas columnas). A las URL de Postgres se les aplica el esquema
`percepcion`. La URL y el texto no se imprimen jamás: solo conteos y, ante un error, la clase
de la excepción.

ANTES DE CORRER
---------------
Hacer una copia de la base. Con las claves ya en `backend/.env` (ver
`scripts/generar_claves_percepcion.py`). Si se pierde PERCEPCION_CLAVE_TEXTO el texto cifrado
es irrecuperable.

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts/cifrar_textos_percepcion.py --dry-run
    backend\\.venv\\Scripts\\python.exe -I scripts/cifrar_textos_percepcion.py
    backend\\.venv\\Scripts\\python.exe -I scripts/cifrar_textos_percepcion.py --descifrar
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
if str(BACKEND) not in sys.path:      # `python -I` no agrega el cwd
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import Text, create_engine, func, inspect, select, text, update  # noqa: E402

from app.services.percepcion import cripto  # noqa: E402
from app.services.percepcion.models import (  # noqa: E402
    PercepcionComentario,
    PercepcionPublicacion,
)

VAR_ADMIN_URL = "PERCEPCION_ADMIN_DATABASE_URL"
LOTE = 500

# (modelo, columna, función de cifrado por fila, función de descifrado por fila)
OBJETIVOS = [
    (PercepcionComentario, "texto", cripto.cifrar_texto, cripto.texto_de),
    (PercepcionPublicacion, "caption", cripto.cifrar_caption, cripto.caption_de),
]


def _ensanchar_si_hace_falta(conn, modelo, columna: str, *, dry_run: bool) -> bool:
    """Convierte la columna a TEXT si tiene un largo máximo que el cifrado podría exceder."""
    tabla = modelo.__table__
    info = next((c for c in inspect(conn).get_columns(tabla.name) if c["name"] == columna), None)
    largo = getattr(info["type"], "length", None) if info else None
    if not largo or isinstance(info["type"], Text):
        return False
    col = tabla.c[columna]
    max_chars = conn.execute(select(func.max(func.length(col)))).scalar() or 0
    # Cota pesimista: 4 bytes por carácter, + nonce y tag (28), base64 (x4/3) y el prefijo.
    necesario = ((max_chars * 4 + 28) * 4) // 3 + 32
    if necesario <= largo:
        return False
    if not dry_run:
        if conn.dialect.name != "postgresql":
            raise RuntimeError("columna con largo máximo insuficiente")
        conn.execute(text(f'ALTER TABLE "{tabla.name}" ALTER COLUMN "{columna}" TYPE TEXT'))
    return True


def _genuino(descifrar_fila, id_, valor) -> bool:
    if not cripto.es_cifrado(valor):
        return False
    try:
        descifrar_fila(id_, valor)
    except cripto.TextoIlegible:
        return False
    return True


def transformar(conn, *, descifrar: bool = False, dry_run: bool = False, lote: int = LOTE) -> dict:
    """Cifra (o descifra) en sitio dentro de la transacción de `conn`. NO hace commit.

    Devuelve conteos por columna: {"tabla.columna": {"cambiadas": n, "ya_listas": m}} más
    {"columnas_ensanchadas": k}. Nunca devuelve ni imprime texto.
    """
    if not dry_run and not cripto.hay_clave():
        raise cripto.ClaveNoConfigurada(f"{cripto.VAR_CLAVE_TEXTO} no está configurada.")
    resumen: dict = {"columnas_ensanchadas": 0}
    # Con clave, "ya cifrado" exige que descifre de verdad (la forma `enc:...` se puede forjar).
    verificable = cripto.hay_clave()
    for modelo, columna, cifrar_fila, descifrar_fila in OBJETIVOS:
        tabla = modelo.__table__
        col = tabla.c[columna]
        if not descifrar and _ensanchar_si_hace_falta(conn, modelo, columna, dry_run=dry_run):
            resumen["columnas_ensanchadas"] += 1
        cambiadas = ya = 0
        ilegibles: list[int] = []        # solo ids (--descifrar): cifrados que no abren
        ultimo = 0
        while True:
            filas = conn.execute(
                select(tabla.c.id, col).where(tabla.c.id > ultimo, col.is_not(None), col != "")
                .order_by(tabla.c.id).limit(lote)
            ).all()
            if not filas:
                break
            ultimo = filas[-1][0]
            for id_, valor in filas:
                if descifrar:
                    if not cripto.es_cifrado(valor):
                        ya += 1
                        continue
                    try:
                        nuevo = descifrar_fila(id_, valor)
                    except cripto.TextoIlegible:
                        ilegibles.append(id_)       # se informa y se deja como está
                        continue
                else:
                    if (_genuino(descifrar_fila, id_, valor) if verificable else cripto.es_cifrado(valor)):
                        ya += 1
                        continue
                    nuevo = None if dry_run else cifrar_fila(id_, valor)
                cambiadas += 1
                if dry_run:
                    continue
                conn.execute(update(tabla).where(tabla.c.id == id_).values({columna: nuevo}))
        resumen[f"{tabla.name}.{columna}"] = {"cambiadas": cambiadas, "ya_listas": ya,
                                              "ilegibles": len(ilegibles)}
        resumen.setdefault("ids_ilegibles", {})[f"{tabla.name}.{columna}"] = ilegibles
    return resumen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cifra en sitio texto y captions de Percepción.")
    ap.add_argument("--url", default=None,
                    help=f"URL de la base (por defecto {VAR_ADMIN_URL}); no se imprime")
    ap.add_argument("--dry-run", action="store_true", help="solo cuenta; no escribe")
    ap.add_argument("--descifrar", action="store_true", help="operación inversa (rollback)")
    args = ap.parse_args(argv)

    url = (args.url or os.environ.get(VAR_ADMIN_URL, "")).strip()
    if not url:
        print(f"Falta el destino: pasa --url o define {VAR_ADMIN_URL} (rol dueño).", file=sys.stderr)
        return 2
    if url.startswith("postgresql"):
        from app.services.percepcion.pg import url_con_esquema
        url = url_con_esquema(url)

    engine = create_engine(url, future=True)
    try:
        with engine.begin() as conn:       # una transacción: confirma al salir, revierte si falla
            r = transformar(conn, descifrar=args.descifrar, dry_run=args.dry_run)
    except Exception as e:  # noqa: BLE001 - el mensaje del driver puede traer la URL o texto de filas
        print(f"No se pudo completar ({type(e).__name__}). No se escribió nada.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    modo = "descifrar" if args.descifrar else "cifrar"
    print(f"{'Simulación de ' if args.dry_run else ''}{modo} — conteos:")
    for clave, v in r.items():
        if isinstance(v, dict) and "cambiadas" in v:      # columnas; "ids_ilegibles" va aparte
            print(f"  {clave}: cambiadas={v['cambiadas']} ya_listas={v['ya_listas']} "
                  f"ilegibles={v['ilegibles']}")
    for clave, ids in r.get("ids_ilegibles", {}).items():
        if ids:
            print(f"  ids ilegibles en {clave} (no se tocaron): {ids[:50]}{' ...' if len(ids) > 50 else ''}")
    if r["columnas_ensanchadas"]:
        print(f"  columnas ensanchadas a TEXT: {r['columnas_ensanchadas']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
