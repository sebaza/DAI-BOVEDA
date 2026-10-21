"""API de subtemas: la etiqueta aparece en las fichas y en /percepcion/subtemas, sin texto."""
from __future__ import annotations

import importlib.util
import zlib
from datetime import datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.schemas import AuthUser
from app.services import accesos
from app.services import auth as auth_service
from app.services.accesos import InMemoryAccessRepository
from app.services.percepcion import derivados, models, subtemas
from app.services.percepcion.db import get_percepcion_db

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("sklearn") is None, reason="scikit-learn no está instalado")

LECTOR = "lector@ucn.cl"
PALABRAS = {"a": "gratuidad", "b": "estacionamiento"}


def _embedder(textos):
    filas = []
    for t in textos:
        v = np.zeros(8)
        v[0 if "gratuidad" in t else 1] = 1.0
        v += np.random.default_rng(zlib.crc32(t.encode())).normal(0, 0.02, 8)
        filas.append(v)
    return np.array(filas)


@pytest.fixture()
def cliente():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    models.Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, future=True)
    db = Sesion()
    db.add(models.PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="institucional",
                                   campus="Antofagasta", facultad="Ingeniería"))
    db.add(models.PercepcionPublicacion(id=1, cuenta_id=1, external_id="p1", tipo="post",
                                        fecha_publicacion=datetime(2026, 1, 1), caption="x", n_likes=1))
    for i in range(1, 25):
        g = "a" if i <= 12 else "b"
        db.add(models.PercepcionComentario(
            id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}",
            texto=f"secretoxyz{i} {PALABRAS[g]} del campus", fecha_comentario=datetime(2026, 1, 2),
            idioma="es", n_likes=1, tema="academico", tema_confianza=0.9))
        db.add(models.PercepcionScore(id=i, comentario_id=i, modelo="t", sentimiento="NEG",
                                      prob_pos=0.0, prob_neu=0.0, prob_neg=1.0,
                                      emocion="anger", prob_emocion=0.9))
    db.commit()
    derivados.reconstruir(db)
    subtemas.reconstruir_subtemas(db, _embedder, modelo="fake", ahora=datetime(2026, 2, 1), min_tamano=5)
    db.commit()

    def _sesion():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    repo = InMemoryAccessRepository()
    repo.add_module("percepcion", "Termómetro Institucional")
    repo.grant_access("percepcion", LECTOR, "lector", by="test")
    accesos.configure(repo)
    app.dependency_overrides[get_percepcion_db] = _sesion
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_percepcion_db, None)
        accesos.reset()
        db.close()


def _h():
    user = AuthUser(email=LECTOR, name=LECTOR, auth_mode="google")
    token = auth_service.build_login_response(user, message="", next_step="").session_token
    return {"Authorization": f"Bearer {token}"}


def test_comentarios_traen_el_subtema(cliente):
    r = cliente.get("/percepcion/comentarios", params={"dias": 36500, "limite": 100}, headers=_h())
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 24
    assert {i["subtema_label"] for i in items} == {"Gratuidad", "Estacionamiento"}
    assert all(isinstance(i["subtema"], int) for i in items)
    assert "secretoxyz" not in r.text


def test_comentarios_sin_subtema_devuelven_null(cliente):
    from app.services.percepcion.db import get_percepcion_db as dep
    s = next(app.dependency_overrides[dep]())
    s.execute(models.PercepcionComentarioSubtema.__table__.delete())
    s.commit()
    r = cliente.get("/percepcion/comentarios", params={"dias": 36500}, headers=_h())
    assert all(i["subtema"] is None and i["subtema_label"] is None for i in r.json()["items"])


def test_endpoint_subtemas(cliente):
    r = cliente.get("/percepcion/subtemas", headers=_h())
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["modelo"] == "fake" and cuerpo["generado_en"].startswith("2026-02-01")
    assert [t["tema"] for t in cuerpo["temas"]] == ["academico"]
    subs = cuerpo["temas"][0]["subtemas"]
    assert sorted(s["etiqueta"] for s in subs) == ["Estacionamiento", "Gratuidad"]
    assert all(s["n_comentarios"] == 12 and s["terminos"] and "id" in s for s in subs)
    assert "secretoxyz" not in r.text


def test_endpoint_subtemas_filtra_por_tema(cliente):
    assert cliente.get("/percepcion/subtemas", params={"tema": "otros"}, headers=_h()).json()["temas"] == []
    assert len(cliente.get("/percepcion/subtemas", params={"tema": "academico"},
                           headers=_h()).json()["temas"]) == 1


def test_endpoint_subtemas_requiere_sesion(cliente):
    assert cliente.get("/percepcion/subtemas").status_code in (401, 403)


def test_sin_las_tablas_de_subtemas_la_api_sigue_andando(cliente):
    from app.services.percepcion.db import get_percepcion_db as dep
    s = next(app.dependency_overrides[dep]())
    s.close()
    bind = s.get_bind()
    models.PercepcionComentarioSubtema.__table__.drop(bind)
    models.PercepcionSubtema.__table__.drop(bind)
    r = cliente.get("/percepcion/comentarios", params={"dias": 36500}, headers=_h())
    assert r.status_code == 200 and all(i["subtema_label"] is None for i in r.json()["items"])
    assert cliente.get("/percepcion/subtemas", headers=_h()).json()["temas"] == []
