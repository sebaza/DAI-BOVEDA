"""Copia la base de Percepción de SQLite (`percepcion_real.db`) a PostgreSQL.

QUÉ HACE
--------
Lee las tablas `percepcion_*` del SQLite del worker (SOLO LECTURA: se abre con
`mode=ro`) y las escribe en el esquema `percepcion` de un Postgres, TODO dentro de UNA
transacción: si algo falla no queda nada a medias.

* El esquema y las tablas salen de los MODELOS (`create_all`), que son la fuente de
  verdad; no hay un SQL de migración paralelo que pueda desalinearse.
* Los valores pasan por los TIPOS de los modelos: fechas guardadas como texto pasan a
  `date`/`datetime`, los 0/1 a `bool` y los JSON se parsean y reserializan.
* Antes de insertar se validan los largos de TODA columna de texto contra el largo real
  de la columna en el destino. SQLite no valida `VARCHAR(n)`; Postgres sí, y reventaba a
  mitad de la copia. Si algo no entra, se aborta nombrando `tabla.columna` (nunca valores).
* Al final se reinician las secuencias a `max(id)+1` y se compara tabla por tabla el
  conteo del origen contra el del destino. Cualquier diferencia: código de salida != 0 y
  la transacción se revierte.

QUÉ NO HACE
-----------
No destruye datos en silencio: si alguna tabla del destino ya tiene filas, se niega,
salvo `--reemplazar`, que las vacía (`TRUNCATE ... RESTART IDENTITY CASCADE`) y recarga.
⚠️ Recargar SOBRESCRIBE lo que la Bóveda haya escrito en Postgres desde la última copia
(correcciones, eventos, temas custom, resúmenes): el worker sigue escribiendo SQLite.

La URL del destino se toma de `--destino` o de `PERCEPCION_DATABASE_URL` y NUNCA se imprime.
El esquema se fija por `search_path` en la conexión (`--esquema`, por defecto `percepcion`).

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts/migrar_percepcion_postgres.py
    backend\\.venv\\Scripts\\python.exe -I scripts/migrar_percepcion_postgres.py --reemplazar
    backend\\.venv\\Scripts\\python.exe -I scripts/migrar_percepcion_postgres.py --origen otra.db --destino postgresql+psycopg://...
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
# `python -I` no agrega el directorio del script ni el cwd al sys.path.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import (  # noqa: E402
    JSON,
    String,
    bindparam,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine  # noqa: E402

from app.database import Base  # noqa: E402
from app.services.percepcion import models  # noqa: E402,F401  (registra las tablas)
from app.services.percepcion.pg import ESQUEMA_PERCEPCION, url_con_esquema  # noqa: E402

ORIGEN_POR_DEFECTO = BACKEND / "percepcion_real.db"
LOTE_POR_DEFECTO = 1000
_NOMBRE_ESQUEMA = re.compile(r"^[a-z_][a-z0-9_]*$")


class MigracionError(Exception):
    """Falla esperable de la migración; el mensaje es apto para mostrar (sin valores)."""


def _tablas():
    """Tablas de los modelos en orden seguro para claves foráneas (padres primero)."""
    return [t for t in Base.metadata.sorted_tables if t.name.startswith("percepcion_")]


def abrir_origen(ruta: Path) -> Engine:
    """SQLite del worker en SOLO LECTURA: ni un byte se escribe en el origen."""
    if not ruta.is_file():
        raise MigracionError(f"No existe la base de origen: {ruta}")
    return create_engine(f"sqlite:///file:{ruta.resolve().as_posix()}?mode=ro&uri=true", future=True)


def _columnas_comunes(origen: Connection, tabla) -> list[str] | None:
    """Columnas del modelo que existen en el origen (None si la tabla no existe).

    Un origen anterior a una migración del worker puede no tener alguna columna nueva
    (p. ej. `origen`): se copia lo que hay y el resto queda NULL en vez de reventar.
    """
    insp = inspect(origen)
    if not insp.has_table(tabla.name):
        return None
    en_origen = {c["name"] for c in insp.get_columns(tabla.name)}
    return [c.name for c in tabla.columns if c.name in en_origen]


def largos_destino(destino: Connection, esquema: str) -> dict[str, dict[str, int]]:
    """Largo real de cada columna de texto con límite en el destino: {tabla: {col: n}}.

    Se lee de la base y no del modelo: una tabla creada antes de ensanchar el modelo
    conserva el largo viejo, y ese es el que Postgres hace cumplir.
    """
    insp = inspect(destino)
    largos: dict[str, dict[str, int]] = {}
    for tabla in _tablas():
        por_columna: dict[str, int] = {}
        for col in insp.get_columns(tabla.name, schema=esquema):
            n = getattr(col["type"], "length", None)
            if isinstance(col["type"], String) and n:
                por_columna[col["name"]] = n
        largos[tabla.name] = por_columna
    return largos


def validar_largos(origen: Connection, largos: dict[str, dict[str, int]]) -> list[str]:
    """Columnas del origen cuyo texto más largo no entra en el destino.

    Devuelve mensajes `tabla.columna (máx. X > N)`: largos y nombres, jamás valores.
    """
    problemas: list[str] = []
    for tabla in _tablas():
        comunes = _columnas_comunes(origen, tabla)
        if comunes is None:
            continue
        for nombre, limite in largos.get(tabla.name, {}).items():
            if nombre not in comunes:
                continue
            maximo = origen.execute(
                text(f'SELECT MAX(LENGTH("{nombre}")) FROM "{tabla.name}"')
            ).scalar()
            if maximo is not None and maximo > limite:
                problemas.append(f"{tabla.name}.{nombre} (máx. {maximo} > {limite})")
    return problemas


def _insert(tabla, columnas: list[str]):
    """INSERT del Core con un bindparam por columna.

    Las columnas JSON se declaran `none_as_null=True`: un `None` del origen queda como NULL
    de SQL y no como el literal JSON `null`, que SQLAlchemy escribiría por defecto.
    """
    params = {}
    for nombre in columnas:
        tipo = tabla.c[nombre].type
        params[nombre] = bindparam(nombre, type_=JSON(none_as_null=True) if isinstance(tipo, JSON) else tipo)
    return tabla.insert().values(params)


def _copiar_tabla(origen: Connection, destino: Connection, tabla, columnas: list[str], lote: int) -> int:
    lectura = origen.execution_options(stream_results=True).execute(
        select(*[tabla.c[n] for n in columnas])
    )
    insert = _insert(tabla, columnas)
    copiadas = 0
    for filas in lectura.partitions(lote):
        destino.execute(insert, [dict(f._mapping) for f in filas])
        copiadas += len(filas)
    return copiadas


def _reiniciar_secuencias(destino: Connection, esquema: str) -> None:
    """Deja cada secuencia de `id` en max(id)+1: el próximo INSERT no choca con lo copiado."""
    for tabla in _tablas():
        if "id" not in tabla.c:
            continue
        destino.execute(
            text(
                "SELECT setval(pg_get_serial_sequence(:calificada, 'id'), "
                f'COALESCE((SELECT MAX(id) FROM "{esquema}"."{tabla.name}"), 0) + 1, false) '
                "WHERE pg_get_serial_sequence(:calificada, 'id') IS NOT NULL"
            ),
            {"calificada": f'"{esquema}"."{tabla.name}"'},
        )


def _con_filas(destino: Connection, esquema: str) -> list[str]:
    return [
        t.name
        for t in _tablas()
        if destino.execute(text(f'SELECT EXISTS (SELECT 1 FROM "{esquema}"."{t.name}")')).scalar()
    ]


def migrar(
    origen: Path,
    destino_url: str,
    *,
    esquema: str = ESQUEMA_PERCEPCION,
    reemplazar: bool = False,
    lote: int = LOTE_POR_DEFECTO,
    salida=print,
) -> dict[str, int]:
    """Copia origen -> destino en una transacción. Devuelve {tabla: filas copiadas}.

    Lanza `MigracionError` ante cualquier problema; en ese caso el destino queda intacto.
    """
    if not _NOMBRE_ESQUEMA.match(esquema):
        raise MigracionError("El nombre del esquema solo admite minúsculas, dígitos y guion bajo.")
    if not destino_url.startswith("postgresql"):
        raise MigracionError("El destino debe ser una URL de PostgreSQL (postgresql+psycopg://...).")

    eng_origen = abrir_origen(origen)
    eng_destino = create_engine(url_con_esquema(destino_url, esquema), future=True)
    copiadas: dict[str, int] = {}
    try:
        with eng_origen.connect() as src, eng_destino.begin() as dst:
            dst.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"'))
            Base.metadata.create_all(dst)

            existentes = _con_filas(dst, esquema)
            if existentes and not reemplazar:
                raise MigracionError(
                    "El destino ya tiene datos en: " + ", ".join(existentes) + ". No se toca nada. "
                    "Usa --reemplazar para vaciarlas y recargar (sobrescribe lo escrito en Postgres)."
                )

            # Tablas `percepcion_*` del origen que los modelos no conocen (p. ej. la
            # `percepcion_contexto` del worker, que la Torre no usa): NO se copian, y se avisa.
            modeladas = {t.name for t in _tablas()}
            for nombre in sorted(inspect(src).get_table_names()):
                if nombre.startswith("percepcion_") and nombre not in modeladas:
                    n = src.execute(text(f'SELECT COUNT(*) FROM "{nombre}"')).scalar()
                    salida(f"  {nombre}: sin modelo en la Torre, NO se copia ({n} filas)")

            problemas = validar_largos(src, largos_destino(dst, esquema))
            if problemas:
                raise MigracionError(
                    "Estas columnas tienen texto más largo que el límite del destino; ensancha el "
                    "modelo y la columna antes de migrar: " + "; ".join(problemas)
                )

            if existentes:
                nombres = ", ".join(f'"{esquema}"."{t.name}"' for t in _tablas())
                dst.execute(text(f"TRUNCATE TABLE {nombres} RESTART IDENTITY CASCADE"))

            for tabla in _tablas():
                columnas = _columnas_comunes(src, tabla)
                if columnas is None:
                    salida(f"  {tabla.name}: no existe en el origen, se omite")
                    copiadas[tabla.name] = 0
                    continue
                copiadas[tabla.name] = _copiar_tabla(src, dst, tabla, columnas, lote)

            _reiniciar_secuencias(dst, esquema)

            diferencias: list[str] = []
            for tabla in _tablas():
                n_origen = (
                    src.execute(text(f'SELECT COUNT(*) FROM "{tabla.name}"')).scalar()
                    if inspect(src).has_table(tabla.name)
                    else 0
                )
                n_destino = dst.execute(text(f'SELECT COUNT(*) FROM "{esquema}"."{tabla.name}"')).scalar()
                marca = "OK" if n_origen == n_destino else "DIFERENTE"
                salida(f"  {tabla.name}: origen {n_origen} -> destino {n_destino}  {marca}")
                if n_origen != n_destino:
                    diferencias.append(tabla.name)
            if diferencias:
                raise MigracionError(
                    "Los conteos no coinciden en: " + ", ".join(diferencias) + ". Se revierte todo."
                )
    finally:
        eng_origen.dispose()
        eng_destino.dispose()
    return copiadas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Migra la base de Percepción de SQLite a PostgreSQL.")
    ap.add_argument("--origen", type=Path, default=ORIGEN_POR_DEFECTO,
                    help="SQLite de origen (por defecto backend/percepcion_real.db)")
    ap.add_argument("--destino", default=None,
                    help="URL SQLAlchemy de Postgres (por defecto, PERCEPCION_DATABASE_URL); no se imprime")
    ap.add_argument("--esquema", default=ESQUEMA_PERCEPCION, help="esquema destino (por defecto percepcion)")
    ap.add_argument("--reemplazar", action="store_true",
                    help="vaciar las tablas del destino que ya tengan filas y recargarlas")
    ap.add_argument("--lote", type=int, default=LOTE_POR_DEFECTO, help="filas por INSERT")
    args = ap.parse_args(argv)

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass

    destino = args.destino or os.environ.get("PERCEPCION_DATABASE_URL", "").strip()
    if not destino:
        print("Falta el destino: pasa --destino o define PERCEPCION_DATABASE_URL.", file=sys.stderr)
        return 2

    print(f"Origen: {args.origen}  ->  esquema destino: {args.esquema}"
          f"{'  (reemplazando)' if args.reemplazar else ''}")
    try:
        copiadas = migrar(args.origen, destino, esquema=args.esquema,
                          reemplazar=args.reemplazar, lote=args.lote)
    except MigracionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - nunca imprimir la URL ni su contraseña
        mensaje = str(exc)
        for secreto in {destino, make_secret(destino)}:
            if secreto:
                mensaje = mensaje.replace(secreto, "***")
        print(f"ERROR inesperado ({type(exc).__name__}): {mensaje[:500]}", file=sys.stderr)
        return 1
    print(f"Migración completa: {sum(copiadas.values())} filas en {len(copiadas)} tablas.")
    return 0


def make_secret(url: str) -> str:
    """La contraseña de la URL, para filtrarla de un mensaje de error."""
    from sqlalchemy.engine import make_url

    try:
        return make_url(url).password or ""
    except Exception:
        return ""


if __name__ == "__main__":
    sys.exit(main())
