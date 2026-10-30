"""Aplica `backend/sql/004_percepcion_warehouse.sql`: permisos de Percepción en el almacén.

Solo OTORGA permisos a dos roles que ya existen (los crea el DBA, con su contraseña; este script
no crea roles ni toca contraseñas):

    --rol-escritor   procesos Python y Curación local: SELECT/INSERT/UPDATE/DELETE + secuencias
    --rol-lector     la API Node (wh-api): SELECT

La URL debe ser de un usuario DUEÑO de las tablas o superusuario: se toma de `--admin-url` o de
`PERCEPCION_WH_ADMIN_DATABASE_URL` y no se imprime. Es idempotente (ver el SQL).

Uso (PowerShell):
    $env:PERCEPCION_WH_ADMIN_DATABASE_URL = "postgresql+psycopg://dueno:...@host:5432/almacen"
    backend\\.venv\\Scripts\\python.exe -I scripts/otorgar_permisos_warehouse_percepcion.py `
        --rol-escritor NOMBRE_ESCRITOR --rol-lector NOMBRE_LECTOR
    # Para ver el SQL final sin conectarse:  ... --solo-imprimir
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_SQL = RAIZ / "backend" / "sql" / "004_percepcion_warehouse.sql"
BACKEND = RAIZ / "backend"
if str(BACKEND) not in sys.path:      # `python -I` no agrega el cwd
    sys.path.insert(0, str(BACKEND))

VAR_ADMIN_URL = "PERCEPCION_WH_ADMIN_DATABASE_URL"

PARAMS = {"esq_percepcion": "percepcion", "rol_escritor": "", "rol_lector": ""}
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_LINEA_PARAM = re.compile(r"^(\s*)(\w+)(\s+text := ')[^']*(';)(.*-- @param.*)$", re.MULTILINE)


def sql_permisos(**cambios: str) -> str:
    """Contenido de 004_percepcion_warehouse.sql con los nombres reemplazados en las líneas `@param`."""
    valores = {**PARAMS, **cambios}
    desconocidos = set(valores) - set(PARAMS)
    if desconocidos:
        raise ValueError(f"parámetros desconocidos: {sorted(desconocidos)}")
    for nombre, valor in valores.items():
        if valor != "" and not _IDENT.match(valor):
            raise ValueError(f"{nombre}: identificador no válido (minúsculas, dígitos y guion bajo)")
    for nombre in ("rol_escritor", "rol_lector"):
        if not valores[nombre]:
            raise ValueError(f"{nombre}: es obligatorio")
    if valores["rol_escritor"] == valores["rol_lector"]:
        raise ValueError("el escritor y el lector deben ser roles distintos")

    def _sub(m: re.Match) -> str:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{valores[m.group(2)]}{m.group(4)}{m.group(5)}"

    return _LINEA_PARAM.sub(_sub, RUTA_SQL.read_text(encoding="utf-8"))


def _conninfo(url: str) -> str:
    from sqlalchemy.engine import make_url
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def aplicar(url_admin: str, **nombres: str) -> None:
    """Corre el SQL en UNA transacción (o nada)."""
    import psycopg

    script = sql_permisos(**nombres)
    with psycopg.connect(_conninfo(url_admin)) as con:
        # Sin parámetros: el DO usa format('%I'), y psycopg solo interpreta '%' si se le pasan.
        con.execute(script)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Otorga los permisos de Percepción en el almacén.")
    ap.add_argument("--rol-escritor", required=True, help="rol de los procesos Python y la Curación")
    ap.add_argument("--rol-lector", required=True, help="rol de solo lectura de la API Node")
    ap.add_argument("--esquema", default="percepcion")
    ap.add_argument("--admin-url", default=None,
                    help=f"URL de un usuario dueño de las tablas o superusuario (o {VAR_ADMIN_URL})")
    ap.add_argument("--solo-imprimir", action="store_true", help="imprime el SQL final y no se conecta")
    args = ap.parse_args(argv)

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass

    nombres = {"rol_escritor": args.rol_escritor, "rol_lector": args.rol_lector,
               "esq_percepcion": args.esquema}
    try:
        script = sql_permisos(**nombres)
    except ValueError as e:
        print(f"Parámetros inválidos: {e}", file=sys.stderr)
        return 2
    if args.solo_imprimir:
        print(script)
        return 0
    url = (args.admin_url or os.environ.get(VAR_ADMIN_URL, "")).strip()
    if not url.startswith("postgresql"):
        print(f"Falta la URL de administración: pasa --admin-url o define {VAR_ADMIN_URL}.", file=sys.stderr)
        return 2
    try:
        aplicar(url, **nombres)
    except Exception as e:  # noqa: BLE001 - nunca imprimir el mensaje: puede traer la URL
        print(f"No se pudieron otorgar los permisos ({type(e).__name__}). Revisa que la URL sea del "
              "dueño/superusuario, que los dos roles existan y que el esquema ya esté cargado.",
              file=sys.stderr)
        return 1
    print(f"Permisos listos en el esquema {args.esquema}: escritor={args.rol_escritor}, "
          f"lector={args.rol_lector}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
