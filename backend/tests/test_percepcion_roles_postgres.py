"""Fase 3b — los roles de base de datos de verdad (opt-in: ``PERCEPCION_TEST_DATABASE_URL``).

Se crean esquemas y roles DESCARTABLES (``percepcion_rt``/``boveda_rt`` y
``rt_boveda_app``/``rt_boveda_proceso``) aplicando el MISMO ``003_percepcion_roles.sql`` que
producción, con los nombres reemplazados. Nunca se toca el esquema ``percepcion`` real ni los
roles ``boveda_app``/``boveda_proceso``.

Qué se prueba, contra un Postgres real y no contra un mock:

* ``boveda_app`` NO puede leer ``texto``/``caption`` (``permission denied``), pero sí el resto;
* ``boveda_app`` puede las escrituras legítimas de la Bóveda y ninguna más;
* ``boveda_proceso`` sí lee el texto;
* PUBLIC no tiene nada;
* todos los GET fuera de la Curación responden 200 conectados como ``boveda_app``, y la
  Curación responde 200 por el motor privilegiado y FALLA si se la conecta al rol de la API.
"""
from __future__ import annotations

import importlib.util
import secrets
from datetime import datetime
from pathlib import Path

import psycopg.errors
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.services import accesos
from app.services.accesos import InMemoryAccessRepository
from app.services.percepcion import curacion, derivados, models
from app.services.percepcion.db import (
    crear_engine,
    get_percepcion_db,
    get_percepcion_proceso_db,
    get_percepcion_write_db,
)
from app.services.percepcion.pg import url_con_esquema
from pg_percepcion import URL, requiere_pg
from tests.test_anonimizacion_api import ADMIN, EQUIPO, _h, _rutas_get, _url

pytestmark = requiere_pg

RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "crear_roles_percepcion.py"
_spec = importlib.util.spec_from_file_location("crear_roles_percepcion", RUTA_SCRIPT)
roles_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(roles_mod)

ESQ = "percepcion_rt"
ESQ_BOVEDA = "boveda_rt"
APP = "rt_boveda_app"
PROCESO = "rt_boveda_proceso"
OTRO = "rt_sin_permisos"
NOMBRES = dict(esq_percepcion=ESQ, esq_boveda=ESQ_BOVEDA, rol_app=APP, rol_proceso=PROCESO)
CENTINELA = "CENTINELA TEXTO CRUDO 7f3a"


def _url_rol(rol: str, clave: str, esquema: str = ESQ) -> str:
    return url_con_esquema(
        make_url(URL).set(username=rol, password=clave).render_as_string(hide_password=False), esquema)


def _limpiar(admin) -> None:
    with admin.begin() as con:
        for e in (ESQ, ESQ_BOVEDA):
            con.execute(text(f'DROP SCHEMA IF EXISTS "{e}" CASCADE'))
        for r in (APP, PROCESO, OTRO):
            if con.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": r}).first():
                con.execute(text(f"DROP OWNED BY {r}"))
            con.execute(text(f"DROP ROLE IF EXISTS {r}"))


@pytest.fixture(scope="module")
def entorno():
    admin = create_engine(URL, future=True)
    _limpiar(admin)
    with admin.begin() as con:
        con.execute(text(f'CREATE SCHEMA "{ESQ}"'))
        con.execute(text(f'CREATE SCHEMA "{ESQ_BOVEDA}"'))
        con.execute(text(f"CREATE ROLE {OTRO}"))
        con.execute(text(f"""
            CREATE TABLE {ESQ_BOVEDA}.modulos (id text PRIMARY KEY, nombre text NOT NULL);
            CREATE TABLE {ESQ_BOVEDA}.accesos_modulo (
                id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, modulo_id text, email text, rol text);
            CREATE TABLE {ESQ_BOVEDA}.administradores (email text PRIMARY KEY);
            CREATE TABLE {ESQ_BOVEDA}.auditoria_texto (
                id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, admin_email text NOT NULL,
                modulo_id text NOT NULL, endpoint text NOT NULL, comentario_ids bigint[] NOT NULL,
                visto_en timestamptz NOT NULL DEFAULT now());
            INSERT INTO {ESQ_BOVEDA}.modulos VALUES ('percepcion', 'Termómetro');
        """))
    eng_dueno = create_engine(url_con_esquema(URL, ESQ), future=True)
    models.Base.metadata.create_all(
        eng_dueno, tables=[t for t in models.Base.metadata.sorted_tables
                           if t.name.startswith("percepcion_")])
    db = sessionmaker(bind=eng_dueno, future=True)()
    db.add(models.PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="institucional",
                                   campus="Antofagasta", facultad="Ingeniería", origen="interno"))
    db.add(models.PercepcionPublicacion(
        id=1, cuenta_id=1, external_id="p1", fecha_publicacion=datetime(2026, 1, 1), tipo="post",
        caption="CENTINELA CAPTION 9b2c ¿paro?", n_comentarios=12, n_likes=3))
    for i in range(1, 13):
        sent = "NEG" if i % 2 else "POS"
        db.add(models.PercepcionComentario(
            id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}",
            texto=f"{CENTINELA} paro toma {i}", fecha_comentario=datetime(2026, 1, 2 + i % 3),
            idioma="es", n_likes=i, tema="otros" if i == 1 else "academico", tema_confianza=0.9))
        db.add(models.PercepcionScore(
            id=i, comentario_id=i, modelo="test", sentimiento=sent,
            prob_pos=float(sent == "POS"), prob_neu=0.0, prob_neg=float(sent == "NEG"),
            emocion="anger", prob_emocion=0.9))
    db.commit()
    curacion.reagregar(db)
    derivados.reconstruir(db)
    db.commit()
    db.close()

    clave_app, clave_proceso = secrets.token_hex(12), secrets.token_hex(12)
    roles_mod.aplicar(URL, clave_app, clave_proceso, **NOMBRES)
    try:
        yield {"app": _url_rol(APP, clave_app), "proceso": _url_rol(PROCESO, clave_proceso),
               "clave_app": clave_app, "clave_proceso": clave_proceso}
    finally:
        eng_dueno.dispose()
        _limpiar(admin)
        admin.dispose()


@pytest.fixture()
def con_app(entorno):
    eng = create_engine(entorno["app"], future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def con_proceso(entorno):
    eng = create_engine(entorno["proceso"], future=True)
    yield eng
    eng.dispose()


def _denegado(eng, sentencia: str) -> None:
    """La sentencia falla con permission denied (se compara la CLASE del error, no el texto)."""
    with pytest.raises(DBAPIError) as exc:
        with eng.begin() as con:
            con.execute(text(sentencia))
    assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege), sentencia


def _ok(eng, sentencia: str):
    with eng.begin() as con:
        r = con.execute(text(sentencia))
        return r.all() if r.returns_rows else []


# --------------------------------------------------------------------------- lectura
def test_app_no_puede_leer_texto_ni_caption(con_app):
    _denegado(con_app, "SELECT texto FROM percepcion_comentario LIMIT 1")
    _denegado(con_app, "SELECT caption FROM percepcion_publicacion LIMIT 1")
    _denegado(con_app, "SELECT * FROM percepcion_comentario LIMIT 1")
    _denegado(con_app, "SELECT * FROM percepcion_publicacion LIMIT 1")
    _denegado(con_app, "SELECT length(texto) FROM percepcion_comentario")
    _denegado(con_app, "SELECT id FROM percepcion_comentario WHERE texto LIKE '%paro%'")


def test_app_si_lee_el_resto(con_app):
    assert _ok(con_app, "SELECT id, tema FROM percepcion_comentario")
    assert _ok(con_app, "SELECT count(*) FROM percepcion_comentario")[0][0] == 12
    assert _ok(con_app, "SELECT id, tipo, n_likes FROM percepcion_publicacion")
    assert _ok(con_app, "SELECT token FROM percepcion_comentario_token LIMIT 1")
    assert _ok(con_app, "SELECT familia FROM percepcion_comentario_familia LIMIT 1")
    assert _ok(con_app, "SELECT emojis_3_o_mas FROM percepcion_publicacion_rasgo")
    assert _ok(con_app, "SELECT sentimiento FROM percepcion_score")
    assert _ok(con_app, "SELECT count(*) FROM percepcion_hecho_diario")


def test_proceso_si_lee_el_texto(con_proceso):
    assert _ok(con_proceso, "SELECT texto FROM percepcion_comentario LIMIT 1")[0][0].startswith("CENTINELA")
    assert _ok(con_proceso, "SELECT caption FROM percepcion_publicacion LIMIT 1")


def test_la_orm_no_pide_las_columnas_crudas(entorno):
    # `db.get(C, id)` (lo que hace corregir_tema) no debe seleccionar `texto`.
    eng = crear_engine(entorno["app"], solo_lectura=False)
    try:
        s = sessionmaker(bind=eng, future=True)()
        com = s.get(models.PercepcionComentario, 2)
        assert com is not None and com.tema is not None
        pub = s.get(models.PercepcionPublicacion, 1)
        assert pub is not None and pub.tipo == "post"
        s.close()
    finally:
        eng.dispose()


# -------------------------------------------------------------------------- escritura
def test_app_hace_las_escrituras_legitimas(con_app):
    _ok(con_app, "UPDATE percepcion_comentario SET tema = 'otros', tema_confianza = 1.0 WHERE id = 3")
    _ok(con_app, "UPDATE percepcion_score SET sentimiento = 'NEU', prob_pos = 0.1, prob_neu = 0.8, "
                 "prob_neg = 0.1, emocion = 'joy', prob_emocion = 1.0, modelo = 'm+correccion_manual' WHERE id = 3")
    _ok(con_app, "INSERT INTO percepcion_tema_custom (clave, etiqueta, keywords, creado_en) "
                 "VALUES ('rt_tema', 'Tema', '[]', now())")
    _ok(con_app, "INSERT INTO percepcion_evento (nombre, tipo, fecha_inicio) VALUES ('e', 'paro', '2026-01-02')")
    _ok(con_app, "UPDATE percepcion_evento SET nombre = 'f'")
    _ok(con_app, "DELETE FROM percepcion_evento")
    _ok(con_app, "INSERT INTO percepcion_correccion (comentario_id, campo, valor_nuevo) VALUES (3, 'tema', 'otros')")
    _ok(con_app, "INSERT INTO percepcion_resumen_semanal (semana_inicio, nivel, dimension, huella, texto) "
                 "VALUES ('2026-01-05', 'global', '', 'h', 't')")
    _ok(con_app, "UPDATE percepcion_resumen_semanal SET texto = 'u'")
    _ok(con_app, "DELETE FROM percepcion_resumen_semanal")
    _ok(con_app, "DELETE FROM percepcion_hecho_diario WHERE id = -1")
    # La recomputación de los hechos del tablero (curacion.reagregar) también va por este rol.
    s = sessionmaker(bind=con_app, future=True)()
    try:
        assert curacion.reagregar(s) > 0
    finally:
        s.close()


def test_app_no_hace_escrituras_de_mas(con_app):
    _denegado(con_app, "UPDATE percepcion_comentario SET texto = 'x'")
    _denegado(con_app, "UPDATE percepcion_publicacion SET caption = 'x'")
    _denegado(con_app, "UPDATE percepcion_comentario SET autor_hash = 'x'")
    _denegado(con_app, "INSERT INTO percepcion_comentario (id, publicacion_id, external_id, autor_hash, texto, "
                       "fecha_comentario) VALUES (99, 1, 'x', 'x', 'x', now())")
    _denegado(con_app, "DELETE FROM percepcion_comentario")
    _denegado(con_app, "DELETE FROM percepcion_score")
    _denegado(con_app, "INSERT INTO percepcion_comentario_token (comentario_id, token) VALUES (1, 'x')")
    _denegado(con_app, "DELETE FROM percepcion_comentario_token")
    _denegado(con_app, "DELETE FROM percepcion_correccion")
    _denegado(con_app, "CREATE TABLE percepcion_rt.nueva (id int)")
    _denegado(con_app, "TRUNCATE percepcion_hecho_diario")


def test_proceso_reconstruye_los_derivados(con_proceso):
    s = sessionmaker(bind=con_proceso, future=True)()
    try:
        r = derivados.reconstruir(s)
        s.commit()
    finally:
        s.close()
    assert r["comentarios"] == 12 and r["tokens"] > 0


def test_esquema_boveda_de_la_app(con_app):
    _ok(con_app, f"SELECT id FROM {ESQ_BOVEDA}.modulos")
    _ok(con_app, f"SELECT email FROM {ESQ_BOVEDA}.administradores")
    _ok(con_app, f"SELECT email, rol FROM {ESQ_BOVEDA}.accesos_modulo")
    _ok(con_app, f"INSERT INTO {ESQ_BOVEDA}.auditoria_texto (admin_email, modulo_id, endpoint, comentario_ids) "
                 "VALUES ('a@ucn.cl', 'percepcion', '/x', ARRAY[1,2]::bigint[])")
    _denegado(con_app, f"SELECT * FROM {ESQ_BOVEDA}.auditoria_texto")
    _denegado(con_app, f"DELETE FROM {ESQ_BOVEDA}.administradores")
    _denegado(con_app, f"INSERT INTO {ESQ_BOVEDA}.administradores (email) VALUES ('x@ucn.cl')")
    _denegado(con_app, f"UPDATE {ESQ_BOVEDA}.accesos_modulo SET rol = 'equipo'")


def test_public_no_tiene_nada(entorno):
    admin = create_engine(URL, future=True)
    try:
        with admin.connect() as con:
            for tabla in (f"{ESQ}.percepcion_comentario", f"{ESQ_BOVEDA}.administradores"):
                assert not con.execute(
                    text("SELECT has_table_privilege(:r, :t, 'SELECT')"), {"r": OTRO, "t": tabla}).scalar_one()
            for esq in (ESQ, ESQ_BOVEDA):
                assert not con.execute(
                    text("SELECT has_schema_privilege(:r, :e, 'USAGE')"), {"r": OTRO, "e": esq}).scalar_one()
            # proceso no necesita el esquema boveda.
            assert not con.execute(text("SELECT has_schema_privilege(:r, :e, 'USAGE')"),
                                   {"r": PROCESO, "e": ESQ_BOVEDA}).scalar_one()
            # Tabla nueva: PUBLIC y la app no la ven; el rol de proceso sí (default privileges).
            con.execute(text(f"CREATE TABLE {ESQ}.percepcion_futura (id int, texto text)"))
            try:
                assert not con.execute(text("SELECT has_table_privilege(:r, :t, 'SELECT')"),
                                       {"r": APP, "t": f"{ESQ}.percepcion_futura"}).scalar_one()
                assert not con.execute(text("SELECT has_table_privilege(:r, :t, 'SELECT')"),
                                       {"r": OTRO, "t": f"{ESQ}.percepcion_futura"}).scalar_one()
            finally:
                con.rollback()
    finally:
        admin.dispose()


def test_el_sql_es_idempotente(entorno):
    roles_mod.aplicar(URL, entorno["clave_app"], entorno["clave_proceso"], **NOMBRES)
    eng = create_engine(entorno["app"], future=True)
    try:
        _denegado(eng, "SELECT texto FROM percepcion_comentario LIMIT 1")
        assert _ok(eng, "SELECT count(*) FROM percepcion_comentario")[0][0] == 12
    finally:
        eng.dispose()


# ------------------------------------------------------------------------ la API entera
@pytest.fixture()
def cliente_roles(entorno):
    motor_app = crear_engine(entorno["app"], solo_lectura=True)
    motor_app_w = crear_engine(entorno["app"], solo_lectura=False)
    motor_proceso = crear_engine(entorno["proceso"], solo_lectura=True)
    f_app = sessionmaker(bind=motor_app, autoflush=False, future=True)
    f_app_w = sessionmaker(bind=motor_app_w, autoflush=False, future=True)
    f_proceso = sessionmaker(bind=motor_proceso, autoflush=False, future=True)
    destino = {"proceso": f_proceso}

    def _abrir(fabrica):
        def _dep():
            s = fabrica()
            try:
                yield s
            finally:
                s.close()
        return _dep

    def _proceso():
        s = destino["proceso"]()
        try:
            yield s
        finally:
            s.close()

    repo = InMemoryAccessRepository()
    repo.add_module("percepcion", "Termómetro Institucional")
    repo.grant_access("percepcion", EQUIPO, "equipo", by="test")
    repo.add_admin(ADMIN, by="test")
    accesos.configure(repo)
    app.dependency_overrides[get_percepcion_db] = _abrir(f_app)
    app.dependency_overrides[get_percepcion_write_db] = _abrir(f_app_w)
    app.dependency_overrides[get_percepcion_proceso_db] = _proceso
    try:
        with TestClient(app) as c:
            yield c, destino, f_app
    finally:
        for dep in (get_percepcion_db, get_percepcion_write_db, get_percepcion_proceso_db):
            app.dependency_overrides.pop(dep, None)
        accesos.reset()
        for e in (motor_app, motor_app_w, motor_proceso):
            e.dispose()


def test_todo_get_fuera_de_la_curacion_responde_200_como_boveda_app(cliente_roles):
    cliente, _, _ = cliente_roles
    rutas = [r for r in _rutas_get() if not r.path.startswith("/percepcion/curacion")]
    assert len(rutas) > 20
    malas = {}
    for ruta in rutas:
        r = cliente.get(_url(ruta), headers=_h(EQUIPO))
        if r.status_code != 200:
            malas[ruta.path] = r.status_code
    assert not malas, f"endpoints que fallan conectados como boveda_app: {malas}"


def test_las_vistas_derivadas_dan_datos_como_boveda_app(cliente_roles):
    cliente, _, _ = cliente_roles
    nube = cliente.get("/percepcion/nube?dias=3650&limite=20", headers=_h(EQUIPO)).json()
    assert nube["hay_datos"] and any(p["texto"] == "paro" for p in nube["palabras"])
    term = cliente.get("/percepcion/terminos?dias=3650", headers=_h(EQUIPO)).json()
    assert any(f["clave"] == "paro" for f in term["familias"])


def test_la_curacion_funciona_por_el_motor_privilegiado(cliente_roles):
    cliente, _, _ = cliente_roles
    for ruta in _rutas_get():
        if ruta.path.startswith("/percepcion/curacion"):
            r = cliente.get(_url(ruta), headers=_h(ADMIN))
            assert r.status_code == 200, ruta.path
    r = cliente.get("/percepcion/curacion/comentarios", headers=_h(ADMIN))
    assert CENTINELA in r.text


def test_la_curacion_falla_si_se_la_conecta_al_rol_de_la_api(cliente_roles):
    # Control negativo: demuestra que lo que hace funcionar la Curación es el rol privilegiado.
    cliente, destino, f_app = cliente_roles
    destino["proceso"] = f_app
    with pytest.raises(Exception) as exc:
        cliente.get("/percepcion/curacion/comentarios", headers=_h(ADMIN))
    assert "InsufficientPrivilege" in repr(exc.value) or "permission denied" in repr(exc.value).lower()


def test_publicaciones_del_resumen_requieren_el_rol_privilegiado(entorno):
    from datetime import date
    from app.services.percepcion import resumen_llm
    eng_proceso = create_engine(entorno["proceso"], future=True)
    eng_app = create_engine(entorno["app"], future=True)
    alc = {"campus": None, "facultad": None}
    try:
        with sessionmaker(bind=eng_proceso, future=True)() as s:
            pubs = resumen_llm._publicaciones(s, date(2026, 1, 1), date(2026, 1, 31), alc)
            assert pubs and "CENTINELA CAPTION" in pubs[0]["caption"]
        with sessionmaker(bind=eng_app, future=True)() as s:
            with pytest.raises(DBAPIError) as exc:
                resumen_llm._publicaciones(s, date(2026, 1, 1), date(2026, 1, 31), alc)
            assert isinstance(exc.value.orig, psycopg.errors.InsufficientPrivilege)
    finally:
        eng_proceso.dispose()
        eng_app.dispose()
