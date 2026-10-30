"""Verifica que la API de Percepción responda LO MISMO sobre SQLite y sobre PostgreSQL.

CÓMO
----
Levanta la app FastAPI en proceso (TestClient, sin red), con una sesión de administrador
sobre un repositorio de accesos en memoria, y llama a una batería de GET representativos
DOS veces: una con la dependencia de base apuntando al SQLite de origen (solo lectura) y
otra apuntando al Postgres migrado. Luego compara los JSON: ignora el orden de las claves
y compara números con una tolerancia chica (SQLite y Postgres suman flotantes en distinto
orden).

SEGURIDAD
---------
* Solo imprime NOMBRES de endpoint y OK/DIFF con las RUTAS que difieren (`$.items[3].n`);
  nunca valores: varias respuestas traen texto de comentarios.
* El SQLite se abre `mode=ro`; el Postgres, con el motor de solo lectura.
* Antes de importar la app se fuerzan URLs de base DESCARTABLES y se vacían las claves de
  LLM: `services/percepcion/db.py` crea engines y corre DDL al importarse, y no queremos
  que eso toque ni la base real ni el `.env` de `backend/`. No se llama a
  `/resumen-semanal` (puede gastar plata); sí a `/resumen-semanal/semanas`.
* La URL de Postgres se toma de `--postgres` o de `PERCEPCION_DATABASE_URL` y no se imprime.

PASO AL ALMACÉN (fase A3)
-------------------------
Sirve para comprobar que el almacén responde lo mismo que la Bóveda actual, con las claves de
`PERCEPCION_CLAVE_TEXTO`/`PERCEPCION_CLAVE_ID` configuradas (las respuestas de Curación descifran
el texto). ANTES de cambiar las URLs:
    ... --guardar-referencia ref.json --referencia-desde-postgres <URL de la Bóveda actual>
DESPUÉS de cargar el almacén:
    ... --contra-referencia ref.json --postgres <URL del almacén>
`ref.json` contiene lo que devuelven los endpoints de curación (texto): bórralo al terminar.

Código de salida: 0 si todo es OK; 1 si algún endpoint difiere o falla.

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts/verificar_paridad_percepcion.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
ORIGEN_POR_DEFECTO = BACKEND / "percepcion_real.db"

# Tolerancia numérica: relativa chica y absoluta aún menor.
REL_TOL = 1e-6
ABS_TOL = 1e-9
MAX_RUTAS = 12


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def diferencias(a, b, ruta: str = "$") -> list[str]:
    """Rutas JSON donde `a` y `b` difieren. Nunca devuelve valores."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{ruta}.{k}")
            else:
                out += diferencias(a[k], b[k], f"{ruta}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [ruta]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diferencias(x, y, f"{ruta}[{i}]")
        return out
    if _es_numero(a) and _es_numero(b):
        return [] if math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL) else [ruta]
    return [] if (type(a) is type(b) and a == b) else [ruta]


def _canonico(v):
    """Forma sin orden de las listas: para distinguir un empate mal ordenado de un dato distinto."""
    if isinstance(v, dict):
        return {k: _canonico(x) for k, x in v.items()}
    if isinstance(v, list):
        return sorted((_canonico(x) for x in v), key=lambda x: json.dumps(x, sort_keys=True, default=str))
    if isinstance(v, float):
        return round(v, 6)
    return v


def solo_orden(a, b) -> bool:
    """True si `a` y `b` tienen el MISMO contenido y solo cambia el orden de alguna lista.

    Pasa cuando una consulta ordena por una clave con empates (p. ej. `n_otros`): el SQL
    no garantiza el orden de las filas empatadas ni en SQLite ni en Postgres, así que
    cada motor devuelve el suyo. Es una diferencia de orden, no de datos.
    """
    return not diferencias(_canonico(a), _canonico(b))


def _endpoints(filtros: dict) -> list[tuple[str, str, dict]]:
    """(nombre, ruta, params). Los filtros salen de las opciones reales de la base."""
    campus = (filtros.get("sedes") or filtros.get("campus") or [None])[0]
    facultad = (filtros.get("facultades") or [None])[0]
    tema = (filtros.get("temas") or [None])[0]
    if isinstance(campus, dict):
        campus = campus.get("valor") or campus.get("id") or campus.get("nombre")
    if isinstance(facultad, dict):
        facultad = facultad.get("valor") or facultad.get("id") or facultad.get("nombre")
    if isinstance(tema, dict):
        tema = tema.get("valor") or tema.get("clave") or tema.get("id")
    acotado: dict = {"dias": 365}
    if campus:
        acotado["sede"] = campus
    if facultad:
        acotado["facultad"] = facultad
    if tema:
        acotado["tema"] = tema
    pesos = {"dias": 180, "peso_likes": 0.5, "vida_media": 14}
    todo = {"dias": 36500}
    p = "/percepcion"
    return [
        ("filtros", f"{p}/filtros", {}),
        ("resumen (default)", f"{p}/resumen", {}),
        ("resumen (acotado)", f"{p}/resumen", acotado),
        ("resumen (pesos)", f"{p}/resumen", pesos),
        ("resumen (todo)", f"{p}/resumen", todo),
        ("evolucion", f"{p}/evolucion", {"dias": 365}),
        ("evolucion (acotado)", f"{p}/evolucion", acotado),
        ("por-tema", f"{p}/por-tema", {"dias": 365}),
        ("por-unidad facultad", f"{p}/por-unidad", {"dias": 365, "nivel": "facultad"}),
        ("por-unidad campus", f"{p}/por-unidad", {"dias": 365, "nivel": "campus"}),
        ("por-unidad departamento", f"{p}/por-unidad", {"dias": 365, "nivel": "departamento"}),
        ("emociones", f"{p}/emociones", {"dias": 365}),
        ("concentracion", f"{p}/concentracion", {"dias": 365}),
        ("postura", f"{p}/postura", {"dias": 365}),
        ("postura (acotado)", f"{p}/postura", acotado),
        ("nube", f"{p}/nube", {"dias": 365, "limite": 60}),
        ("sintesis", f"{p}/sintesis", {"dias": 365}),
        ("publicaciones-dominantes", f"{p}/publicaciones-dominantes", {"dias": 365}),
        ("destacados", f"{p}/destacados", {"dias": 365}),
        ("terminos", f"{p}/terminos", {"dias": 365}),
        ("impacto-palabras", f"{p}/impacto-palabras", {"dias": 90}),
        ("eventos", f"{p}/eventos", {"dias": 400}),
        ("eventos/tipos", f"{p}/eventos/tipos", {}),
        ("eventos/todos (calendario)", f"{p}/eventos/todos", {}),
        ("anomalias", f"{p}/anomalias", {"dias": 365}),
        ("comentarios", f"{p}/comentarios", {"dias": 365, "limite": 30}),
        ("comentarios (NEG)", f"{p}/comentarios", {"dias": 365, "limite": 30, "sentimiento": "NEG"}),
        ("conflicto", f"{p}/conflicto", {"dias": 90}),
        ("comunicacion", f"{p}/comunicacion", {}),
        ("ensayo", f"{p}/ensayo", {}),
        ("shock", f"{p}/shock", {}),
        ("baselines", f"{p}/baselines", {}),
        ("volatilidad", f"{p}/volatilidad", {}),
        ("resumen-semanal/semanas", f"{p}/resumen-semanal/semanas", {}),
        ("curacion/temas", f"{p}/curacion/temas", {}),
        ("curacion/publicaciones", f"{p}/curacion/publicaciones", {}),
        ("curacion/comentarios", f"{p}/curacion/comentarios", {}),
        ("curacion/scoring/opciones", f"{p}/curacion/scoring/opciones", {}),
        ("curacion/scoring (duda)", f"{p}/curacion/scoring", {"orden": "duda", "limite": 50}),
        ("curacion/scoring (reciente)", f"{p}/curacion/scoring", {"orden": "reciente", "limite": 50}),
        ("curacion/calidad", f"{p}/curacion/calidad", {}),
        ("curacion/correcciones", f"{p}/curacion/correcciones", {"limite": 100}),
    ]


def _preparar_entorno() -> Path:
    """Fuerza bases descartables ANTES de importar la app. Devuelve el directorio temporal."""
    tmp = Path(tempfile.mkdtemp(prefix="paridad_percepcion_"))
    os.environ["APP_ENV"] = "dev"
    os.environ["APP_SESSION_SECRET"] = "paridad-secret-no-es-el-de-desarrollo"
    os.environ["PERCEPCION_DATABASE_URL"] = f"sqlite:///{(tmp / 'descartable.db').as_posix()}"
    os.environ["OPERATIONAL_DATABASE_URL"] = f"sqlite:///{(tmp / 'operacional.db').as_posix()}"
    os.environ["BOVEDA_DATABASE_URL"] = ""
    os.environ["TASKS_TRIGGER_TOKEN"] = ""
    os.environ["ANTHROPIC_API_KEY"] = ""
    os.environ["OPENAI_API_KEY"] = ""
    return tmp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Paridad de la API de Percepción: SQLite vs PostgreSQL.")
    ap.add_argument("--sqlite", type=Path, default=ORIGEN_POR_DEFECTO, help="SQLite de origen")
    ap.add_argument("--postgres", default=None,
                    help="URL de Postgres (por defecto PERCEPCION_DATABASE_URL); no se imprime")
    ap.add_argument("--esquema", default="percepcion")
    ap.add_argument("--guardar-referencia", type=Path, default=None, metavar="ARCHIVO",
                    help="Solo SQLite: guarda las respuestas del código ACTUAL (cálculo sobre texto) "
                         "en ARCHIVO (JSON local; contiene lo que devuelven los endpoints de curación: "
                         "bórralo después) y termina. No requiere Postgres.")
    ap.add_argument("--referencia-desde-postgres", default=None, metavar="URL",
                    help="Con --guardar-referencia: toma la referencia de ESTE Postgres (p. ej. la Bóveda "
                         "actual, ANTES de pasar al almacén) en vez del SQLite; no se imprime. "
                         "Después, --contra-referencia + --postgres apuntando al almacén.")
    ap.add_argument("--contra-referencia", type=Path, default=None, metavar="ARCHIVO",
                    help="Compara el Postgres (cálculo sobre tokens precalculados) contra una referencia "
                         "guardada antes con --guardar-referencia: prueba que refactorizar no cambió resultados.")
    args = ap.parse_args(argv)

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass

    url_pg = args.postgres or os.environ.get("PERCEPCION_DATABASE_URL", "").strip()
    if not args.guardar_referencia and not url_pg.startswith("postgresql"):
        print("Falta la URL de Postgres: pasa --postgres o define PERCEPCION_DATABASE_URL.", file=sys.stderr)
        return 2
    if args.referencia_desde_postgres and not args.guardar_referencia:
        print("--referencia-desde-postgres solo se usa junto con --guardar-referencia.", file=sys.stderr)
        return 2
    if args.referencia_desde_postgres and not args.referencia_desde_postgres.startswith("postgresql"):
        print("--referencia-desde-postgres debe ser una URL de PostgreSQL.", file=sys.stderr)
        return 2
    if not args.referencia_desde_postgres and not args.sqlite.is_file():
        print(f"No existe el SQLite de origen: {args.sqlite}", file=sys.stderr)
        return 2

    tmp = _preparar_entorno()  # ← antes de importar la app
    sys.path.insert(0, str(BACKEND))
    try:
        return _comparar(args.sqlite, url_pg, args.esquema,
                         guardar=args.guardar_referencia, referencia=args.contra_referencia,
                         origen_pg=args.referencia_desde_postgres)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _comparar(ruta_sqlite: Path, url_pg: str, esquema: str, *,
              guardar: Path | None = None, referencia: Path | None = None,
              origen_pg: str | None = None) -> int:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.main import app
    from app.schemas import AuthUser
    from app.services import accesos
    from app.services import auth as auth_service
    from app.services.accesos import InMemoryAccessRepository
    from app.services.percepcion.db import (
        crear_engine,
        get_percepcion_db,
        get_percepcion_proceso_db,
        get_percepcion_write_db,
    )
    from app.services.percepcion.pg import url_con_esquema

    s = get_settings()
    s.app_env = "dev"
    s.tasks_trigger_token = ""
    s.boveda_database_url = "postgresql+psycopg://configurada-solo-en-esta-verificacion"

    admin = "paridad@ucn.cl"
    repo = InMemoryAccessRepository()
    repo.add_module("percepcion", "Termómetro Institucional")
    repo.add_admin(admin, by="paridad")
    accesos.configure(repo)
    token = auth_service.build_login_response(
        AuthUser(email=admin, name=admin, auth_mode="google"), message="", next_step=""
    ).session_token
    cabecera = {"Authorization": f"Bearer {token}"}

    if origen_pg:
        # La referencia sale de otro Postgres (la Bóveda actual), con el motor de solo lectura.
        motor_ref = crear_engine(url_con_esquema(origen_pg, esquema), solo_lectura=True)
    else:
        motor_ref = crear_engine(
            f"sqlite:///file:{ruta_sqlite.resolve().as_posix()}?mode=ro&uri=true", solo_lectura=True)
    motores = {"sqlite": motor_ref}   # la clave "sqlite" es solo la etiqueta del lado de referencia
    if not guardar:
        motores["postgres"] = crear_engine(url_con_esquema(url_pg, esquema), solo_lectura=True)
    fabricas = {k: sessionmaker(bind=e, autoflush=False, autocommit=False, future=True)
                for k, e in motores.items()}
    activo = {"motor": "sqlite"}

    def _sesion():
        db = fabricas[activo["motor"]]()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_percepcion_db] = _sesion
    app.dependency_overrides[get_percepcion_write_db] = _sesion
    app.dependency_overrides[get_percepcion_proceso_db] = _sesion
    cliente = TestClient(app, raise_server_exceptions=False)

    def pedir(motor: str, ruta: str, params: dict):
        activo["motor"] = motor
        r = cliente.get(ruta, params=params, headers=cabecera)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None

    fallos = 0
    ordenes = 0
    try:
        estado, filtros = pedir("sqlite", "/percepcion/filtros", {})
        if estado != 200 or not isinstance(filtros, dict):
            print(f"No se pudieron leer los filtros del SQLite (HTTP {estado}).", file=sys.stderr)
            return 1
        if guardar:
            volcado = {n: pedir("sqlite", r, p) for n, r, p in _endpoints(filtros)}
            guardar.write_text(json.dumps(volcado, default=str), encoding="utf-8")
            malos = [n for n, (e, _) in volcado.items() if e != 200]
            print(f"Referencia guardada: {len(volcado)} endpoints, {len(malos)} con HTTP != 200.")
            return 1 if malos else 0
        previa = json.loads(referencia.read_text(encoding="utf-8")) if referencia else None
        for nombre, ruta, params in _endpoints(filtros):
            if previa is not None:
                # Referencia (código viejo, texto) vs Postgres (código nuevo, tokens).
                e1, j1 = previa[nombre]
                e2, j2 = pedir("postgres", ruta, params)
            else:
                (e1, j1), (e2, j2) = pedir("sqlite", ruta, params), pedir("postgres", ruta, params)
            if e1 != 200 or e2 != 200:
                print(f"{nombre:34s} ERROR  HTTP sqlite={e1} postgres={e2}")
                fallos += 1
                continue
            dif = diferencias(j1, j2)
            if not dif:
                print(f"{nombre:34s} OK")
            elif solo_orden(j1, j2):
                # Mismo contenido; cambia el orden de las filas empatadas. Se informa, no falla.
                print(f"{nombre:34s} ORDEN  mismo contenido, otro orden entre empates")
                ordenes += 1
            else:
                fallos += 1
                vistas = ", ".join(dif[:MAX_RUTAS]) + (f" (+{len(dif) - MAX_RUTAS} más)" if len(dif) > MAX_RUTAS else "")
                print(f"{nombre:34s} DIFF  {vistas}")
    finally:
        app.dependency_overrides.clear()
        accesos.reset()
        for e in motores.values():
            e.dispose()
    resto = f" ({ordenes} solo difieren en el orden de empates)" if ordenes else ""
    print(f"\n{'Todo coincide.' if not fallos else f'{fallos} endpoint(s) con diferencias o errores.'}{resto}")
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(main())
