"""Administra quién entra a la Bóveda DAI: administradores globales y accesos por módulo.

Las listas viven en PostgreSQL (esquema `boveda`, ver backend/sql/). No hay interfaz de
administración: se manejan solo con este script. Los cambios rigen en la siguiente petición
del usuario afectado (la app no cachea el rol).

    python scripts/boveda_accesos.py agregar-admin <correo>
    python scripts/boveda_accesos.py quitar-admin <correo>
    python scripts/boveda_accesos.py dar-acceso <modulo> <correo> <lector|equipo>
    python scripts/boveda_accesos.py quitar-acceso <modulo> <correo>
    python scripts/boveda_accesos.py listar [--modulo <modulo>]

Opciones comunes de escritura: `--por <nombre>` (quién hace el cambio; por defecto, el
usuario del sistema operativo).

Conexión: la variable BOVEDA_DATABASE_URL, del entorno o de backend/.env (URL de SQLAlchemy,
p. ej. `postgresql+psycopg://usuario:clave@host:5432/base`). El script NUNCA imprime la URL.

Corre con el venv del backend: `backend\\.venv\\Scripts\\python.exe scripts\\boveda_accesos.py ...`
Código de salida 0 = listo; 1 = error (módulo inexistente, correo o rol inválidos, sin
conexión); 2 = uso incorrecto de los argumentos.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.accesos import (  # noqa: E402
    AccessError,
    AccessManager,
    PostgresAccessRepository,
)


def cargar_entorno() -> None:
    """Carga backend/.env sin pisar variables que ya estén en el entorno."""
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")


def _abrir_gestor() -> AccessManager:
    cargar_entorno()
    url = os.getenv("BOVEDA_DATABASE_URL", "").strip()
    if not url:
        raise AccessError(
            "Falta BOVEDA_DATABASE_URL (en el entorno o en backend/.env): "
            "no sé a qué base conectarme."
        )
    try:
        return PostgresAccessRepository.from_url(url)
    except Exception as exc:  # noqa: BLE001 - nunca se muestra el mensaje: podría traer la URL
        raise AccessError(
            f"No se pudo preparar la conexión ({type(exc).__name__}). "
            "Revisa BOVEDA_DATABASE_URL y que `psycopg` esté instalado."
        ) from None


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boveda_accesos.py",
        description="Administra los accesos de la Bóveda DAI (administradores globales y accesos por módulo).",
    )
    sub = parser.add_subparsers(dest="comando", required=True, metavar="comando")

    def con_por(p: argparse.ArgumentParser) -> None:
        p.add_argument("--por", default=None, help="quién hace el cambio (def.: usuario del sistema)")

    p = sub.add_parser("agregar-admin", help="agrega un administrador global")
    p.add_argument("correo")
    con_por(p)

    p = sub.add_parser("quitar-admin", help="quita un administrador global")
    p.add_argument("correo")

    p = sub.add_parser("dar-acceso", help="da (o cambia) el rol de un correo en un módulo")
    p.add_argument("modulo")
    p.add_argument("correo")
    p.add_argument("rol", help="lector (solo lectura) o equipo (lectura y escritura)")
    con_por(p)

    p = sub.add_parser("quitar-acceso", help="quita el acceso de un correo a un módulo")
    p.add_argument("modulo")
    p.add_argument("correo")

    p = sub.add_parser("listar", help="muestra administradores y accesos")
    p.add_argument("--modulo", default=None, help="solo los accesos de este módulo")
    return parser


def _listar(gestor: AccessManager, modulo: str | None) -> None:
    listado = gestor.list_all(modulo)
    if not listado.administradores and not listado.accesos:
        print("Nadie tiene acceso todavía (sin filas no entra nadie).")
        return
    print("Administradores globales (abren todos los módulos activos):")
    for correo in listado.administradores or ["(ninguno)"]:
        print(f"  {correo}")
    por_modulo: dict[str, list] = {}
    for a in listado.accesos:
        por_modulo.setdefault(a.modulo_id, []).append(a)
    if modulo and modulo not in por_modulo:
        por_modulo[modulo] = []
    for mod in sorted(por_modulo):
        print(f"Módulo {mod}:")
        for a in por_modulo[mod] or []:
            print(f"  {a.rol:<8} {a.email}" + (f"  (por {a.creado_por})" if a.creado_por else ""))
        if not por_modulo[mod]:
            print("  (sin accesos)")


def main(argv: list[str] | None = None, repo: AccessManager | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):  # consolas Windows sin UTF-8: no romper por una tilde
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = _crear_parser().parse_args(argv)
    por = getattr(args, "por", None) or getpass.getuser()
    gestor = repo
    try:
        if gestor is None:
            gestor = _abrir_gestor()
        if args.comando == "agregar-admin":
            gestor.add_admin(args.correo, by=por)
            print(f"Administrador agregado: {args.correo.strip().lower()}")
        elif args.comando == "quitar-admin":
            correo = args.correo.strip().lower()
            if gestor.remove_admin(args.correo):
                print(f"Administrador quitado: {correo}")
            else:
                print(f"{correo} no era administrador; no hay nada que quitar.")
        elif args.comando == "dar-acceso":
            gestor.grant_access(args.modulo, args.correo, args.rol, by=por)
            print(f"Acceso listo: {args.correo.strip().lower()} -> {args.modulo} ({args.rol.strip().lower()})")
        elif args.comando == "quitar-acceso":
            correo = args.correo.strip().lower()
            if gestor.revoke_access(args.modulo, args.correo):
                print(f"Acceso quitado: {correo} ya no entra a {args.modulo}.")
            else:
                print(f"{correo} no tenía acceso a {args.modulo}; no hay nada que quitar.")
        elif args.comando == "listar":
            _listar(gestor, args.modulo)
    except AccessError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if repo is None:  # la conexión la abrí yo: la cierro yo
            dispose = getattr(gestor, "dispose", None)
            if callable(dispose):
                dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
