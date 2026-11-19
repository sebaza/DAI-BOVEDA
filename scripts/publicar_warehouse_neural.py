"""Publishes the DAI Neural public-route responses to the institutional warehouse (for the GitHub Pages site).

WHAT IT DOES
------------
Calls every published `GET /neural/*` route of the Boveda app in process (TestClient, no server), against the local Neural
database (`--origen`, READ ONLY), and stores the JSON bodies byte for byte in `<esquema>.neural_respuesta`
(`(ruta, consulta)` is the canonical key of `_neural_publicacion.canonizar`). One row in `neural_publicacion` records when,
how many and how big. Only aggregate responses leave the machine: the identity-key gate (`revisar_identidad`) aborts the whole
publication, naming only the offending JSON paths, if any body carries an identity key.

The access gates are overridden with a fixed user without personal data (`exportador@local`). `/neural/aceptacion` is stored
as the acceptance text with `aceptada: false` (an empty in-memory access repository: no Boveda table is read).

WRITING
-------
One transaction: DDL (`backend/sql/008_neural_publicacion_warehouse.sql`), grant copy (the SELECT grants of
`<esquema>.percepcion_hecho_diario`; none if that table does not exist), DELETE of both tables, batched inserts, publication
row. Any failure rolls everything back. Origin and destination must not be the same database.

URLs come from `--origen` / `--destino` or `NEURAL_DATABASE_URL` / `NEURAL_WH_DATABASE_URL` and are NEVER printed. Output: the
response count, total bytes, the largest route and timing.

Exit code: 0 ok; 1 failure; 2 usage/configuration. `--dry-run` collects and checks, then stops (no `--destino` needed).

Usage:
    backend\\.venv\\Scripts\\python.exe -I scripts/publicar_warehouse_neural.py --dry-run
    backend\\.venv\\Scripts\\python.exe -I scripts/publicar_warehouse_neural.py --destino <url>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
# `python -I` adds neither the script directory nor the cwd to sys.path.
for _p in (str(BACKEND), str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine, make_url  # noqa: E402

from _neural_publicacion import canonizar, combinaciones, revisar_identidad  # noqa: E402

VAR_ORIGEN = "NEURAL_DATABASE_URL"
VAR_DESTINO = "NEURAL_WH_DATABASE_URL"
VERSION_EXPORTADOR = "2026-11-19"
LOTE = 200
DDL = BACKEND / "sql" / "008_neural_publicacion_warehouse.sql"
TABLA_REFERENCIA = "percepcion_hecho_diario"   # its ACL is copied onto the Neural tables
_NOMBRE_ESQUEMA = re.compile(r"[a-z_][a-z0-9_]*")


class PublicacionError(Exception):
    """Expected failure; the message is safe to show (no values, no URLs)."""


# ---------------------------------------------------------------------------
# Same-database guard (copy of the Percepcion writer's: importing it would drag its crypto requirements)
# ---------------------------------------------------------------------------
_LOCALES = {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _extremo(url: str) -> tuple[str, int, str]:
    """(host, port, database) normalized: lowercase, loopback unified, default port, libpq `?host=` over the URL host."""
    u = make_url(url)
    host = u.query.get("host") or u.host or ""
    if isinstance(host, (tuple, list)):
        host = host[0] if host else ""
    host = str(host).strip().strip("[]").lower()
    if host in _LOCALES:
        host = "localhost"
    puerto = u.query.get("port") or u.port or 5432
    return host, int(puerto), u.database or ""


def _identidad(eng: Engine) -> dict:
    """Who the server is: database, address/port and, if the role may, the cluster id (None when unreadable)."""
    with eng.connect() as con:
        base, addr, puerto = con.execute(text(
            "SELECT current_database(), inet_server_addr()::text, inet_server_port()")).one()
        try:
            with con.begin_nested():
                sysid = con.execute(text("SELECT system_identifier FROM pg_control_system()")).scalar()
        except Exception:   # noqa: BLE001 - no permission: use the rest
            sysid = None
    return {"base": base, "addr": addr, "puerto": puerto, "sysid": sysid}


def _misma_instancia(eng_o: Engine, eng_d: Engine) -> bool:
    o, d = _identidad(eng_o), _identidad(eng_d)
    if o["base"] != d["base"]:
        return False
    if o["sysid"] is not None and d["sysid"] is not None:
        return o["sysid"] == d["sysid"]
    if o["addr"] is not None and d["addr"] is not None:
        return (o["addr"], o["puerto"]) == (d["addr"], d["puerto"])
    return False


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
def recolectar(origen: str, salida=print) -> list[tuple[str, str, bytes]]:
    """GET of every published route, in process, against `origen` (READ ONLY). Returns (ruta, consulta, body bytes).

    Any non-200 aborts naming the URL and the status."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.schemas import AuthUser
    from app.services import accesos
    from app.services.accesos import InMemoryAccessRepository
    from app.services.neural import aceptacion
    from app.services.neural.db import crear_engine, get_neural_conn

    usuario = AuthUser(email="exportador@local", name="exportador", auth_mode="session")
    engine = crear_engine(origen)

    def _conn():
        with engine.connect() as con:
            yield con

    app.dependency_overrides[aceptacion.exigir_modulo] = lambda: usuario
    app.dependency_overrides[aceptacion.require_aceptacion] = lambda: usuario
    app.dependency_overrides[get_neural_conn] = _conn
    accesos.configure(InMemoryAccessRepository())   # nobody accepted: the stored /neural/aceptacion has aceptada=false
    cuerpos: dict[str, bytes] = {}
    try:
        cliente = TestClient(app)   # no lifespan: the routes need no startup work (and Percepcion init is not wanted here)
        def pedir(url: str) -> bytes:
            if url not in cuerpos:
                r = cliente.get(url)
                if r.status_code != 200:
                    raise PublicacionError(f"{url} answered {r.status_code}: nothing was published.")
                cuerpos[url] = r.content
            return cuerpos[url]

        urls = combinaciones(lambda u: json.loads(pedir(u)))
        salida(f"Combinations to collect: {len(urls)}")
        return [(*canonizar(u), pedir(u)) for u in urls]
    finally:
        app.dependency_overrides.pop(aceptacion.exigir_modulo, None)
        app.dependency_overrides.pop(aceptacion.require_aceptacion, None)
        app.dependency_overrides.pop(get_neural_conn, None)
        accesos.reset()
        engine.dispose()


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def _sentencias(esquema: str) -> list[str]:
    """The DDL file with the schema substituted, split into statements (no comments, no blanks)."""
    sql = "\n".join(ln for ln in DDL.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("--"))
    return [s.strip() for s in sql.replace("__ESQUEMA__", esquema).split(";") if s.strip()]


def _copiar_grants(con, esquema: str, salida) -> None:
    """SELECT grants of `<esquema>.percepcion_hecho_diario` copied onto both Neural tables (SELECT only)."""
    if con.execute(text("SELECT to_regclass(:t)"), {"t": f'"{esquema}".{TABLA_REFERENCIA}'}).scalar() is None:
        salida(f"Grants: {esquema}.{TABLA_REFERENCIA} does not exist; nothing granted.")
        return
    roles = con.execute(text(
        "SELECT DISTINCT CASE WHEN a.grantee = 0 THEN 'PUBLIC' "
        "ELSE (SELECT rolname FROM pg_roles r WHERE r.oid = a.grantee) END "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "CROSS JOIN LATERAL aclexplode(c.relacl) a "
        "WHERE n.nspname = :e AND c.relname = :t AND a.privilege_type = 'SELECT'"),
        {"e": esquema, "t": TABLA_REFERENCIA}).scalars().all()
    roles = sorted(r for r in roles if r)
    for rol in roles:
        destino = "PUBLIC" if rol == "PUBLIC" else '"' + rol.replace('"', '""') + '"'
        for tabla in ("neural_respuesta", "neural_publicacion"):
            con.execute(text(f'GRANT SELECT ON TABLE "{esquema}".{tabla} TO {destino}'))
    salida(f"Grants: SELECT copied for {len(roles)} role(s).")


def publicar(destino_url: str | None, esquema: str, respuestas: list[tuple[str, str, bytes]], dry_run: bool,
             salida=print) -> int:
    """Checks the responses and (unless `dry_run`) replaces the published set in one transaction. Exit code (0 ok, 1 failure).

    The identity gate runs first on every body: any offender aborts before the destination is touched."""
    t0 = time.monotonic()
    if not _NOMBRE_ESQUEMA.fullmatch(esquema):
        salida("Invalid schema name (lowercase letters, digits and underscore only).")
        return 1
    for ruta, consulta, cuerpo in respuestas:
        try:
            ofensores = revisar_identidad(json.loads(cuerpo))
        except ValueError:
            salida(f"Body of {ruta} is not valid JSON: nothing was published.")
            return 1
        if ofensores:
            salida(f"Identity keys found in {ruta}{'?' + consulta if consulta else ''}: " + ", ".join(ofensores[:10])
                   + ". Nothing was published.")
            return 1
    vistas: set[tuple[str, str]] = set()
    repetidas: list[str] = []
    for ruta, consulta, _ in respuestas:
        if (ruta, consulta) in vistas:
            repetidas.append(ruta)
        vistas.add((ruta, consulta))
    if repetidas:
        salida(f"Duplicate (ruta, consulta) keys: {len(repetidas)}; first ruta: {repetidas[0]}. Nothing was published.")
        return 1
    total = sum(len(c) for _, _, c in respuestas)
    mayor = max(respuestas, key=lambda r: len(r[2]), default=None)
    salida(f"Responses: {len(respuestas)}; total bytes: {total}"
           + (f"; largest: {mayor[0]}{'?' + mayor[1] if mayor[1] else ''} ({len(mayor[2])} bytes)" if mayor else ""))
    if dry_run:
        salida(f"Dry run: nothing written ({time.monotonic() - t0:.1f}s).")
        return 0
    if not destino_url:
        salida("Missing destination.")
        return 1
    ahora = datetime.now(timezone.utc)
    eng = create_engine(destino_url, future=True)
    try:
        with eng.begin() as con:   # one transaction: any failure rolls everything back
            for sentencia in _sentencias(esquema):
                con.execute(text(sentencia))
            _copiar_grants(con, esquema, salida)
            con.execute(text(f'DELETE FROM "{esquema}".neural_respuesta'))
            con.execute(text(f'DELETE FROM "{esquema}".neural_publicacion'))
            insert = text(f'INSERT INTO "{esquema}".neural_respuesta (ruta, consulta, contenido, generado_en) '
                          "VALUES (:ruta, :consulta, CAST(:contenido AS jsonb), :ahora)")
            for i in range(0, len(respuestas), LOTE):
                con.execute(insert, [{"ruta": r, "consulta": q, "contenido": c.decode("utf-8"), "ahora": ahora}
                                     for r, q, c in respuestas[i:i + LOTE]])
            con.execute(text(f'INSERT INTO "{esquema}".neural_publicacion '
                             "(id, publicado_en, version_exportador, respuestas, bytes) "
                             "VALUES (1, :ahora, :v, :n, :b)"),
                        {"ahora": ahora, "v": VERSION_EXPORTADOR, "n": len(respuestas), "b": total})
    except Exception as exc:   # noqa: BLE001 - the driver message may carry the URL or values
        salida(f"Write failed ({type(exc).__name__}). Nothing was published.")
        return 1
    finally:
        eng.dispose()
    salida(f"Published in {time.monotonic() - t0:.1f}s.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Publishes the DAI Neural public responses to the institutional warehouse.")
    ap.add_argument("--origen", default=None, help=f"local Neural database URL (or {VAR_ORIGEN}); never printed")
    ap.add_argument("--destino", default=None, help=f"warehouse URL (or {VAR_DESTINO}); never printed")
    ap.add_argument("--esquema", default="percepcion", help="destination schema (default percepcion)")
    ap.add_argument("--dry-run", action="store_true", help="collect and check; write nothing")
    args = ap.parse_args(argv)

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:   # noqa: BLE001
            pass

    origen = (args.origen or os.environ.get(VAR_ORIGEN, "")).strip()
    destino = (args.destino or os.environ.get(VAR_DESTINO, "")).strip()
    if not origen:
        print(f"Missing origin: pass --origen or set {VAR_ORIGEN}.", file=sys.stderr)
        return 2
    if not destino and not args.dry_run:
        print(f"Missing destination: pass --destino or set {VAR_DESTINO}.", file=sys.stderr)
        return 2
    if not _NOMBRE_ESQUEMA.fullmatch(args.esquema):
        print("Invalid schema name (lowercase letters, digits and underscore only).", file=sys.stderr)
        return 2
    for url in (origen, destino):
        if url and not url.startswith("postgresql"):
            print("URLs must be PostgreSQL URLs (postgresql+psycopg://...).", file=sys.stderr)
            return 2

    try:
        if destino:
            if _extremo(origen) == _extremo(destino):
                print("Origin and destination are the same host, port and database: refused.", file=sys.stderr)
                return 2
            eng_o, eng_d = create_engine(origen, future=True), create_engine(destino, future=True)
            try:
                if _misma_instancia(eng_o, eng_d):
                    print("The server confirms origin and destination are the same database: refused.", file=sys.stderr)
                    return 1
            finally:
                eng_o.dispose()
                eng_d.dispose()
        respuestas = recolectar(origen)
        return publicar(destino or None, args.esquema, respuestas, args.dry_run)
    except PublicacionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:   # noqa: BLE001 - the driver message may carry a URL or rows
        print(f"Unexpected error ({type(exc).__name__}). Nothing was published.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
