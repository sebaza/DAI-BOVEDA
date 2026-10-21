"""Crea (o actualiza) los roles de base de datos `boveda_app` y `boveda_proceso`.

Aplica `backend/sql/003_percepcion_roles.sql` y fija las contraseñas de los dos roles.

POR QUÉ
-------
Para que la API normal (`boveda_app`) no pueda leer `percepcion_comentario.texto` ni
`percepcion_publicacion.caption`, ni siquiera por un bug o una consulta mal escrita. El rol
`boveda_proceso` sí puede y solo lo usan la Curación de administradores, la lectura de captions
del resumen semanal y los scripts de precálculo. Ver el README (sección Datos).

CÓMO
----
Las contraseñas se leen SOLO del entorno (nunca van en un archivo ni en la línea de comandos del
programa, y no se imprimen):

    PERCEPCION_APP_DB_PASSWORD        contraseña de boveda_app
    PERCEPCION_PROCESO_DB_PASSWORD    contraseña de boveda_proceso

Si falta alguna, el script se NIEGA a continuar (no deja roles a medias ni sin contraseña).

La conexión debe ser de un usuario que sea DUEÑO de las tablas o superusuario. Su URL se toma de
`--admin-url` o de `PERCEPCION_ADMIN_DATABASE_URL` y tampoco se imprime.

Uso (PowerShell):
    $env:PERCEPCION_APP_DB_PASSWORD = "..."; $env:PERCEPCION_PROCESO_DB_PASSWORD = "..."
    $env:PERCEPCION_ADMIN_DATABASE_URL = "postgresql+psycopg://postgres:...@localhost:5432/postgres"
    backend\\.venv\\Scripts\\python.exe -I scripts/crear_roles_percepcion.py

Es idempotente: se puede correr de nuevo para rotar contraseñas o para otorgar permisos a tablas
creadas después.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_SQL = RAIZ / "backend" / "sql" / "003_percepcion_roles.sql"
BACKEND = RAIZ / "backend"
if str(BACKEND) not in sys.path:      # `python -I` no agrega el cwd
    sys.path.insert(0, str(BACKEND))

VAR_APP = "PERCEPCION_APP_DB_PASSWORD"
VAR_PROCESO = "PERCEPCION_PROCESO_DB_PASSWORD"
VAR_ADMIN_URL = "PERCEPCION_ADMIN_DATABASE_URL"

PARAMS = {
    "esq_percepcion": "percepcion",
    "esq_boveda": "boveda",
    "rol_app": "boveda_app",
    "rol_proceso": "boveda_proceso",
}
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_LINEA_PARAM = re.compile(r"^(\s*)(\w+)(\s+text := ')[^']*(';)(.*-- @param.*)$", re.MULTILINE)


class FaltanContrasenas(RuntimeError):
    pass


def contrasenas_del_entorno(env=None) -> tuple[str, str]:
    """(app, proceso) del entorno; lanza `FaltanContrasenas` nombrando las variables ausentes."""
    env = os.environ if env is None else env
    app, proceso = (env.get(VAR_APP) or "").strip(), (env.get(VAR_PROCESO) or "").strip()
    faltan = [n for n, v in ((VAR_APP, app), (VAR_PROCESO, proceso)) if not v]
    if faltan:
        raise FaltanContrasenas("Falta definir en el entorno: " + ", ".join(faltan))
    if app == proceso:
        raise FaltanContrasenas(
            "Las dos contraseñas son iguales: si una se filtra, el rol sin acceso al texto deja "
            "de servir. Usa contraseñas distintas.")
    return app, proceso


def sql_roles(**cambios: str) -> str:
    """Contenido de 003_percepcion_roles.sql, con los nombres de esquemas/roles reemplazados."""
    texto = RUTA_SQL.read_text(encoding="utf-8")
    valores = {**PARAMS, **cambios}
    desconocidos = set(valores) - set(PARAMS)
    if desconocidos:
        raise ValueError(f"parámetros desconocidos: {sorted(desconocidos)}")
    for nombre, valor in valores.items():
        if not _IDENT.match(valor):
            raise ValueError(f"{nombre}: identificador no válido")

    def _sub(m: re.Match) -> str:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{valores[m.group(2)]}{m.group(4)}{m.group(5)}"

    return _LINEA_PARAM.sub(_sub, texto)


def _conninfo(url: str) -> str:
    from sqlalchemy.engine import make_url
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def aplicar(url_admin: str, password_app: str, password_proceso: str, **nombres: str) -> None:
    """Corre el SQL y fija las contraseñas, todo en UNA transacción (o nada)."""
    import psycopg
    from psycopg import sql

    valores = {**PARAMS, **nombres}
    script = sql_roles(**nombres)
    with psycopg.connect(_conninfo(url_admin)) as con:
        # Sin parámetros: el DO usa format('%I'), y psycopg solo interpreta '%' si se le pasan.
        con.execute(script)
        for rol, clave in ((valores["rol_app"], password_app),
                           (valores["rol_proceso"], password_proceso)):
            con.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(rol), sql.Literal(clave)))
        # `with` hace commit al salir sin excepción y rollback si la hubo.


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Crea los roles boveda_app y boveda_proceso.")
    ap.add_argument("--admin-url", default=None,
                    help=f"URL de un usuario dueño de las tablas o superusuario (o {VAR_ADMIN_URL})")
    args = ap.parse_args(argv)

    try:
        password_app, password_proceso = contrasenas_del_entorno()
    except FaltanContrasenas as e:
        print(str(e), file=sys.stderr)
        return 2
    url = (args.admin_url or os.environ.get(VAR_ADMIN_URL, "")).strip()
    if not url.startswith("postgresql"):
        print(f"Falta la URL de administración: pasa --admin-url o define {VAR_ADMIN_URL}.", file=sys.stderr)
        return 2
    try:
        aplicar(url, password_app, password_proceso)
    except Exception as e:  # noqa: BLE001 - nunca imprimir el mensaje: puede traer la URL o una clave
        print(f"No se pudieron crear los roles ({type(e).__name__}). "
              "Revisa que la URL sea de un dueño/superusuario y que las migraciones estén aplicadas.",
              file=sys.stderr)
        return 1
    print(f"Roles listos: {PARAMS['rol_app']} (API) y {PARAMS['rol_proceso']} (Curación y scripts).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
