"""Renombrar subtemas desde Curación: endpoint solo admin y nombres que sobreviven a la reconstrucción."""
from __future__ import annotations

import importlib.util
import zlib
from datetime import datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.schemas import AuthUser
from app.services import accesos
from app.services import auth as auth_service
from app.services.accesos import InMemoryAccessRepository
from app.services.percepcion import derivados, models, subtemas
from app.services.percepcion.db import get_percepcion_db, get_percepcion_write_db

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("sklearn") is None, reason="scikit-learn no está instalado")

EQUIPO = "equipo@ucn.cl"
ADMIN = "admin@ucn.cl"
PALABRAS = {"a": "gratuidad", "b": "estacionamiento"}
S = models.PercepcionSubtema


def _embedder(textos):
    filas = []
    for t in textos:
        v = np.zeros(8)
        v[0 if "gratuidad" in t else 1] = 1.0
        v += np.random.default_rng(zlib.crc32(t.encode())).normal(0, 0.02, 8)
        filas.append(v)
    return np.array(filas)


def _correr(db):
    r = subtemas.reconstruir_subtemas(db, _embedder, modelo="fake", ahora=datetime(2026, 2, 1),
                                      min_tamano=5)
    db.commit()
    return r


@pytest.fixture()
def entorno():
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
    _correr(db)

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
            yield c, db
    finally:
        app.dependency_overrides.pop(get_percepcion_db, None)
        app.dependency_overrides.pop(get_percepcion_write_db, None)
        accesos.reset()
        db.close()


def _h(email):
    user = AuthUser(email=email, name=email, auth_mode="google")
    token = auth_service.build_login_response(user, message="", next_step="").session_token
    return {"Authorization": f"Bearer {token}"}


def _id(db, etiqueta):
    return db.execute(select(S.id).where(S.etiqueta == etiqueta)).scalar_one()


def _put(c, sid, etiqueta, quien=ADMIN):
    return c.put(f"/percepcion/curacion/subtemas/{sid}", json={"etiqueta": etiqueta}, headers=_h(quien))


def _etiquetas_api(c):
    cuerpo = c.get("/percepcion/subtemas", headers=_h(ADMIN)).json()
    return {s["id"]: s for t in cuerpo["temas"] for s in t["subtemas"]}


# ------------------------------------------------------------------ endpoint
def test_equipo_no_puede_renombrar(entorno):
    c, db = entorno
    assert _put(c, _id(db, "Gratuidad"), "Becas", quien=EQUIPO).status_code == 403


def test_sin_sesion_no_renombra(entorno):
    c, db = entorno
    assert c.put(f"/percepcion/curacion/subtemas/{_id(db, 'Gratuidad')}",
                 json={"etiqueta": "Becas"}).status_code in (401, 403)


def test_admin_renombra_y_se_ve_en_todas_partes(entorno):
    c, db = entorno
    sid = _id(db, "Gratuidad")
    r = _put(c, sid, "  Becas   y  gratuidad ")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["id"] == sid and cuerpo["etiqueta"] == "Becas y gratuidad"
    assert cuerpo["etiqueta_auto"] == "Gratuidad" and cuerpo["manual"] is True
    s = _etiquetas_api(c)[sid]
    assert s["etiqueta"] == "Becas y gratuidad" and s["manual"] is True
    items = c.get("/percepcion/comentarios", params={"dias": 36500, "limite": 100},
                  headers=_h(ADMIN)).json()["items"]
    assert {i["subtema_label"] for i in items} == {"Becas y gratuidad", "Estacionamiento"}
    db.expire_all()
    fila = db.get(S, sid)
    assert fila.renombrado_por == ADMIN and fila.renombrado_en is not None
    assert fila.etiqueta == "Gratuidad"                       # la automática no se toca


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_volver_a_automatico(entorno, valor):
    c, db = entorno
    sid = _id(db, "Gratuidad")
    assert _put(c, sid, "Becas").status_code == 200
    r = _put(c, sid, valor)
    assert r.status_code == 200 and r.json()["manual"] is False and r.json()["etiqueta"] == "Gratuidad"
    assert _etiquetas_api(c)[sid]["etiqueta"] == "Gratuidad"
    db.expire_all()
    assert db.get(S, sid).etiqueta_manual is None


@pytest.mark.parametrize("valor", ["x" * 81, "@usuario", "hola @usuario", "http://x", "mira www.ucn.cl",
                                   "ucn.cl/becas", "con\x00control", "tab\taqui", "salto\nlinea"])
def test_etiquetas_invalidas_dan_422(entorno, valor):
    c, db = entorno
    sid = _id(db, "Gratuidad")
    r = _put(c, sid, valor)
    assert r.status_code == 422, valor
    assert _etiquetas_api(c)[sid]["manual"] is False


def test_largo_maximo_80_es_valido(entorno):
    c, db = entorno
    assert _put(c, _id(db, "Gratuidad"), "x" * 80).status_code == 200


def test_subtema_inexistente_da_404(entorno):
    c, _ = entorno
    assert _put(c, 99999, "Becas").status_code == 404


def test_sin_tablas_de_subtemas_da_404(entorno):
    c, db = entorno
    bind = db.get_bind()
    db.close()
    models.PercepcionComentarioSubtema.__table__.drop(bind)
    models.PercepcionSubtema.__table__.drop(bind)
    assert _put(c, 1, "Becas").status_code == 404


# ------------------------------------------------------------------ reconstrucción
def test_la_reconstruccion_conserva_el_nombre_manual(entorno):
    c, db = entorno
    assert _put(c, _id(db, "Gratuidad"), "Becas").status_code == 200
    r = _correr(db)
    assert r["nombres_manuales_conservados"] == 1 and r["nombres_manuales_descartados"] == 0
    nuevas = _etiquetas_api(c)
    assert sorted(s["etiqueta"] for s in nuevas.values()) == ["Becas", "Estacionamiento"]
    fila = db.execute(select(S).where(S.etiqueta == "Gratuidad")).scalar_one()
    assert fila.etiqueta_manual == "Becas" and fila.renombrado_por == ADMIN
    assert fila.renombrado_en is not None
    assert "secretoxyz" not in repr(r).lower()


def test_la_reconstruccion_descarta_el_nombre_si_cambia_la_membresia(entorno):
    c, db = entorno
    assert _put(c, _id(db, "Gratuidad"), "Becas").status_code == 200
    # 8 de los 12 comentarios de "Gratuidad" pasan a hablar de otra cosa: Jaccard < 0.5.
    for i in range(1, 9):
        db.execute(update(models.PercepcionComentario).where(models.PercepcionComentario.id == i)
                   .values(texto=f"secretoxyz{i} estacionamiento del campus"))
    db.commit()
    r = _correr(db)
    assert r["nombres_manuales_conservados"] == 0 and r["nombres_manuales_descartados"] == 1
    assert db.execute(select(S).where(S.etiqueta_manual.is_not(None))).first() is None


def test_un_nombre_manual_no_se_usa_dos_veces(entorno):
    c, db = entorno
    assert _put(c, _id(db, "Gratuidad"), "Becas").status_code == 200
    assert _put(c, _id(db, "Estacionamiento"), "Parking").status_code == 200
    r = _correr(db)
    assert r["nombres_manuales_conservados"] == 2
    assert sorted(s.etiqueta_manual for s in db.execute(select(S)).scalars()) == ["Becas", "Parking"]


def test_dry_run_informa_sin_escribir(entorno):
    c, db = entorno
    assert _put(c, _id(db, "Gratuidad"), "Becas").status_code == 200
    r = subtemas.reconstruir_subtemas(db, _embedder, modelo="fake", ahora=datetime(2026, 2, 1),
                                      min_tamano=5, escribir=False)
    assert r["nombres_manuales_conservados"] == 1
    assert db.execute(select(S).where(S.etiqueta_manual == "Becas")).first() is not None


@pytest.mark.parametrize("valor", ["hola ＠usuario", "mira ucn．cl", "ㅤㅤ", "ㅤ"])
def test_variantes_unicode_no_cuelan_arrobas_enlaces_ni_nombres_vacios(entorno, valor):
    c, db = entorno
    r = _put(c, _id(db, "Gratuidad"), valor)
    assert r.status_code == 422, valor


def test_renombrar_con_la_etiqueta_automatica_vigente(entorno):
    c, db = entorno
    sid = _id(db, "Gratuidad")
    r = c.put(f"/percepcion/curacion/subtemas/{sid}",
              json={"etiqueta": "Becas", "etiqueta_auto": "Gratuidad"}, headers=_h(ADMIN))
    assert r.status_code == 200 and r.json()["etiqueta"] == "Becas"


def test_lista_vieja_da_409_y_no_renombra(entorno):
    # Los ids cambian al reconstruir: si la pantalla quedó con una etiqueta automática que ya
    # no es la de ese id, no se renombra a ciegas.
    c, db = entorno
    sid = _id(db, "Gratuidad")
    r = c.put(f"/percepcion/curacion/subtemas/{sid}",
              json={"etiqueta": "Becas", "etiqueta_auto": "Otra cosa"}, headers=_h(ADMIN))
    assert r.status_code == 409
    assert _etiquetas_api(c)[sid]["manual"] is False
