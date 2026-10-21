"""Guardia de anonimización: la API NO muestra texto crudo fuera de la curación.

El texto de los comentarios y los captions de las publicaciones se guardan tal cual,
pero solo las pantallas de ``/percepcion/curacion/*`` (solo administradores, con
auditoría) los devuelven. Las demás vistas pueden DERIVAR agregados del texto (nube,
términos, impacto de palabras), pero no mostrarlo.

El recorrido es sobre ``app.routes``: un GET nuevo bajo ``/percepcion`` queda cubierto
solo, y si no se sabe llamar el test FALLA en vez de saltárselo.
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest
from fastapi.dependencies.utils import get_flat_dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.routers.percepcion import router as router_percepcion
from app.schemas import AuthUser
from app.services import accesos
from app.services import auth as auth_service
from app.services.accesos import InMemoryAccessRepository
from app.services.percepcion import models
from app.services.percepcion.db import get_percepcion_db, get_percepcion_write_db

CENTINELA_TEXTO = "CENTINELA TEXTO CRUDO 7f3a"
CENTINELA_CAPTION = "CENTINELA CAPTION 9b2c"
EQUIPO = "equipo@ucn.cl"
ADMIN = "admin@ucn.cl"

# Valores por defecto para los query params obligatorios que aparezcan en el futuro.
_DEFECTOS_QUERY = {"int": 1, "float": 1.0, "bool": False, "str": "x"}


def _h(email: str) -> dict:
    user = AuthUser(email=email, name=email, auth_mode="google")
    token = auth_service.build_login_response(user, message="", next_step="").session_token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def cliente():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    for t in models.Base.metadata.sorted_tables:
        if t.name.startswith("percepcion_"):
            t.create(engine)
    Sesion = sessionmaker(bind=engine, future=True)
    db = Sesion()
    db.add(models.PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="institucional",
                                   campus="Antofagasta", facultad="Ingeniería",
                                   departamento=None, carrera=None))
    db.add(models.PercepcionPublicacion(
        id=1, cuenta_id=1, external_id="p1", fecha_publicacion=datetime(2026, 1, 1),
        tipo="post", caption=f"{CENTINELA_CAPTION} paro", n_comentarios=12, n_likes=3))
    for i in range(1, 13):
        sent = "NEG" if i % 2 else "POS"
        db.add(models.PercepcionComentario(
            id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}",
            texto=f"{CENTINELA_TEXTO} paro toma {i}", fecha_comentario=datetime(2026, 1, 2 + i % 3),
            idioma="es", n_likes=i, tema="otros" if i == 1 else "academico", tema_confianza=0.9))
        db.add(models.PercepcionScore(
            id=i, comentario_id=i, modelo="test", sentimiento=sent,
            prob_pos=1.0 if sent == "POS" else 0.0, prob_neu=0.0,
            prob_neg=1.0 if sent == "NEG" else 0.0, emocion="anger", prob_emocion=0.9))
    db.commit()

    def _sesion():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    repo = InMemoryAccessRepository()
    repo.add_module("percepcion", "Termómetro Institucional")
    repo.grant_access("percepcion", EQUIPO, "equipo", by="test")
    repo.add_admin(ADMIN, by="test")
    accesos.configure(repo)
    app.dependency_overrides[get_percepcion_db] = _sesion
    app.dependency_overrides[get_percepcion_write_db] = _sesion
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_percepcion_db, None)
        app.dependency_overrides.pop(get_percepcion_write_db, None)
        accesos.reset()
        db.close()


def _rutas_get() -> list[APIRoute]:
    return [r for r in router_percepcion.routes
            if isinstance(r, APIRoute) and r.path.startswith("/percepcion")
            and "GET" in r.methods]


def _url(ruta: APIRoute) -> str:
    """URL llamable de un GET; si no se sabe armar, FALLA (no se salta)."""
    plano = get_flat_dependant(ruta.dependant)
    if plano.path_params:
        pytest.fail(f"{ruta.path}: tiene parámetros de ruta; agrégalo al enumerador de la guardia")
    params = []
    for p in plano.query_params:
        if p.field_info.is_required():
            tipo = getattr(p.field_info.annotation, "__name__", "str")
            if tipo not in _DEFECTOS_QUERY:
                pytest.fail(f"{ruta.path}: query obligatorio '{p.name}' ({tipo}) sin valor por defecto en la guardia")
            params.append(f"{p.name}={_DEFECTOS_QUERY[tipo]}")
    return ruta.path + ("?" + "&".join(params) if params else "")


def _cuerpo(cliente, ruta, email) -> str:
    r = cliente.get(_url(ruta), headers=_h(email))
    assert r.status_code == 200, f"{ruta.path} respondió {r.status_code}; la guardia no pudo leerla"
    return r.text.lower()


def test_hay_rutas_que_recorrer():
    rutas = {r.path for r in _rutas_get()}
    assert "/percepcion/comentarios" in rutas and "/percepcion/curacion/comentarios" in rutas
    assert len(rutas) > 20


@pytest.mark.parametrize("email", [EQUIPO, ADMIN])
def test_ningun_get_fuera_de_la_curacion_devuelve_texto_crudo(cliente, email):
    filtrados = []
    for ruta in _rutas_get():
        if ruta.path.startswith("/percepcion/curacion"):
            continue
        cuerpo = _cuerpo(cliente, ruta, email)
        if any(c.lower() in cuerpo for c in (CENTINELA_TEXTO, CENTINELA_CAPTION)):
            filtrados.append(ruta.path)
    assert not filtrados, f"rutas que exponen texto crudo a {email}: {filtrados}"


def test_equipo_no_ve_texto_crudo_en_ninguna_ruta_ni_en_la_curacion(cliente):
    for ruta in _rutas_get():
        if ruta.path.startswith("/percepcion/curacion"):
            r = cliente.get(_url(ruta), headers=_h(EQUIPO))
            assert r.status_code == 403, ruta.path
            continue
        cuerpo = _cuerpo(cliente, ruta, EQUIPO)
        assert not re.search(r"centinela (texto|caption)", cuerpo), ruta.path


def test_la_curacion_del_admin_sigue_mostrando_el_texto(cliente):
    r = cliente.get("/percepcion/curacion/comentarios", headers=_h(ADMIN))
    assert r.status_code == 200
    assert CENTINELA_TEXTO in r.text
