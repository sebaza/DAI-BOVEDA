"""Sincroniza de forma INCREMENTAL el SQLite del worker con el Postgres de la Bóveda.

QUÉ HACE
--------
Lee `percepcion_real.db` (SOLO LECTURA: `mode=ro`) e INSERTA en el esquema `percepcion` lo
que el destino no tiene, por `id`: cuentas, publicaciones, comentarios, scores y eventos,
en orden de claves foráneas. Después, en la MISMA transacción, reagrega
`percepcion_hecho_diario` respetando la curación (`curacion.reagregar`) y reconstruye
tokens/familias/rasgos (`derivados.reconstruir`; `--sin-derivados` lo omite).

QUÉ NO HACE
-----------
* Nunca hace UPDATE: el tema curado y todo lo editado en la Bóveda queda intacto.
* No toca correcciones, resúmenes, temas custom ni contexto. A diferencia de
  `migrar_percepcion_postgres.py --reemplazar`, no borra nada.
* Si un `id` existe en ambos lados con otra clave natural, o una fila nueva choca por clave
  natural con otro `id`, o apunta a un padre inexistente, ABORTA sin escribir.

ROL
---
Las tablas crudas solo las puede escribir el dueño: use la URL de administración
(`--url` o `PERCEPCION_ADMIN_DATABASE_URL`). Con `--dry-run` (solo lee el destino y no
selecciona texto) sirve el rol de la app (`PERCEPCION_DATABASE_URL`).

RESPALDO
--------
Antes de escribir (no en `--dry-run`) se exportan las correcciones y los nombres manuales de
subtemas a `backend/respaldos/sync-<UTC>.json`. Nunca incluye texto de comentarios, pero las
correcciones traen `justificacion` y `autor` (texto de administradores): el archivo es local y
está en .gitignore.

Imprime solo conteos y tiempos; jamás la URL. Ante un error muestra solo la clase de la
excepción (los mensajes del driver pueden traer URL o datos de filas).

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts\\sincronizar_percepcion_worker.py --dry-run
    $env:PERCEPCION_ADMIN_DATABASE_URL = "postgresql+psycopg://..."
    backend\\.venv\\Scripts\\python.exe -I scripts\\sincronizar_percepcion_worker.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
# `python -I` no agrega el directorio del script ni el cwd al sys.path.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.services.percepcion import sincronizacion  # noqa: E402
from app.services.percepcion.pg import url_con_esquema  # noqa: E402

ORIGEN_POR_DEFECTO = Path(
    r"C:\Users\sezad\Documents\GitHub\Sentiment_Analisys_University\percepcion_real.db"
)
RESPALDOS = BACKEND / "respaldos"


def _url_destino(arg: str | None, dry_run: bool) -> str | None:
    if arg:
        return arg
    admin = os.environ.get("PERCEPCION_ADMIN_DATABASE_URL", "").strip()
    if admin or not dry_run:
        return admin or None
    # Simulación: alcanza con el rol de la app (solo lectura).
    propia = os.environ.get("PERCEPCION_DATABASE_URL", "").strip()
    if propia:
        return propia
    from app.config import get_settings

    return get_settings().percepcion_database_url.strip() or None


def _imprimir(res: sincronizacion.Resultado, simular: bool) -> None:
    verbo = "se insertarían" if simular else "insertadas"
    for tabla, n in res.insertados.items():
        print(f"  {tabla}: {n} {verbo}")
    if res.conflictos:
        print("  CONFLICTOS: " + ", ".join(f"{t}={n}" for t, n in res.conflictos.items()))
    else:
        print("  conflictos: 0")
    if res.hechos is not None:
        print(f"  hechos diarios reagregados: {res.hechos}")
    if res.derivados is not None:
        print("  derivados: " + ", ".join(f"{k}={v}" for k, v in res.derivados.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sincroniza incrementalmente el worker con la Bóveda.")
    ap.add_argument("--origen", type=Path,
                    default=Path(os.environ.get("PERCEPCION_WORKER_SQLITE") or ORIGEN_POR_DEFECTO),
                    help="SQLite del worker (env PERCEPCION_WORKER_SQLITE)")
    ap.add_argument("--url", default=None,
                    help="URL del destino (por defecto PERCEPCION_ADMIN_DATABASE_URL); no se imprime")
    ap.add_argument("--dry-run", action="store_true", help="calcula e informa; no escribe nada")
    ap.add_argument("--sin-derivados", action="store_true",
                    help="no reagrega hechos diarios ni reconstruye tokens/familias/rasgos")
    args = ap.parse_args(argv)

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass

    url = _url_destino(args.url, args.dry_run)
    if not url:
        print("Falta el destino: la escritura exige el rol dueño de las tablas. Pasa --url o "
              "define PERCEPCION_ADMIN_DATABASE_URL.", file=sys.stderr)
        return 2
    if not args.origen.is_file():
        print(f"No existe la base de origen: {args.origen}", file=sys.stderr)
        return 2

    inicio = time.monotonic()
    eng_origen = create_engine(
        f"sqlite:///file:{args.origen.resolve().as_posix()}?mode=ro&uri=true", future=True)
    eng_destino = create_engine(
        url_con_esquema(url) if url.startswith("postgresql") else url, future=True)
    try:
        with Session(eng_origen) as src, Session(eng_destino) as dst:
            if args.dry_run:
                print("Simulación (no se escribe nada):")
                res = sincronizacion.sincronizar(src, dst, simular=True)
                dst.rollback()
                _imprimir(res, simular=True)
                print(f"Listo en {time.monotonic() - inicio:.1f} s.")
                return 1 if res.conflictos else 0

            try:
                res = sincronizacion.sincronizar(src, dst, simular=True)
                if res.conflictos:
                    dst.rollback()
                    raise sincronizacion.ConflictoSincronizacion(res.conflictos)
                ruta = sincronizacion.respaldar(dst, RESPALDOS)
                print(f"Respaldo de curación: {ruta.relative_to(RAIZ)}")
                res = sincronizacion.sincronizar(src, dst, con_derivados=not args.sin_derivados)
                dst.commit()
            except BaseException:
                dst.rollback()
                raise
            _imprimir(res, simular=False)
            print(f"Sincronización completa en {time.monotonic() - inicio:.1f} s.")
            print("Siguiente paso: scripts/agrupar_subtemas_percepcion.py --vetar ... "
                  "(reasigna subtemas a los comentarios nuevos).")
    except sincronizacion.ConflictoSincronizacion as exc:
        print("ABORTADO, no se escribió nada. Conflictos: " + ", ".join(
            f"{t}={n}" for t, n in exc.conflictos.items()), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - los mensajes del driver pueden traer URL o filas
        print(f"ERROR inesperado ({type(exc).__name__}). No se escribió nada.", file=sys.stderr)
        return 1
    finally:
        eng_origen.dispose()
        eng_destino.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
