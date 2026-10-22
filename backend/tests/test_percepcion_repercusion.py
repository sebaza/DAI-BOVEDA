"""Repercusión: comentarios que etiquetan a otras personas.

Cubre el contador (`derivados.contar_etiquetas`), la tabla derivada, el subtema fijo
«Etiquetan a otras personas» y el endpoint `/percepcion/repercusion`. Los handles de los
tests son centinelas: no pueden aparecer en ninguna respuesta.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.schemas import AuthUser
from app.services import accesos
from app.services import auth as auth_service
from app.services.accesos import InMemoryAccessRepository
from app.services.percepcion import derivados, models, subtemas
from app.services.percepcion.db import get_percepcion_db
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionComentarioEtiqueta,
    PercepcionComentarioSubtema,
    PercepcionCuenta,
    PercepcionPublicacion,
    PercepcionScore,
    PercepcionSubtema,
)

LECTOR = "lector@ucn.cl"


# ------------------------------------------------------------ contar_etiquetas
def test_contar_etiquetas_menciones_y_handles_sin_arroba():
    assert derivados.contar_etiquetas("hola @ana y @luis.perez") == 2
    assert derivados.contar_etiquetas("Participando:B tote.mny_ cldliio_") == 2
    assert derivados.contar_etiquetas("sin nadie") == 0
    assert derivados.contar_etiquetas("") == 0 and derivados.contar_etiquetas(None) == 0


def test_contar_etiquetas_ignora_frases_scraper_urls_numeros_y_hashtags():
    assert derivados.contar_etiquetas("mira https://x.cl/a_b_c ahora") == 0
    assert derivados.contar_etiquetas("a las 10:30 en 2026 #ucn2026") == 0


def test_contar_etiquetas_no_confunde_horas_unidades_ni_mayusculas():
    for texto in ("nos vemos a las 10pm", "llego 8am", "3ra vez", "red 5G", "covid19",
                  "COVID-19", "saludos Dr.Perez", "ok_YA"):
        assert derivados.contar_etiquetas(texto) == 0, texto
    assert derivados.contar_etiquetas("maria23 y juan.perez, ven") == 2
    assert derivados.contar_etiquetas("Seca! comments from Facebook") == 0


def test_contar_etiquetas_es_cota_inferior():
    # Un handle de solo letras sin "@" no se distingue de una palabra: no se cuenta.
    assert derivados.contar_etiquetas("jmanuuu ignaciamilann") == 0


# ------------------------------------------------------------ datos
def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


# (id, publicacion, texto, fecha)
LU1, LU2 = datetime(2026, 1, 5, 10), datetime(2026, 1, 13, 10)    # lunes y martes de otra semana
COMENTARIOS = [
    (1, 1, "gracias @secretohandle", LU1),            # etiqueta, pero dice algo
    (2, 1, "@secretohandle @otro_x", LU1),            # solo etiquetas (2)
    (3, 1, "buen día", LU1),
    (4, 1, "vamos", LU1),
    (5, 2, "tote.mny_ cldl_", LU2),                   # solo etiquetas (2), handles sin @
    (6, 2, "hola equipo", LU2),
    (7, 2, "gran trabajo", LU2),
]


def _sembrar(db):
    db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN Antofagasta", tipo="institucional",
                            campus="Antofagasta", facultad="Ingeniería"))
    db.add(PercepcionCuenta(id=2, handle="ucn_coq", nombre="UCN Coquimbo", tipo="institucional",
                            campus="Coquimbo", facultad="Ciencias"))
    for pid, cuenta, f in ((1, 1, datetime(2026, 1, 3)), (2, 2, datetime(2026, 1, 10))):
        db.add(PercepcionPublicacion(id=pid, cuenta_id=cuenta, external_id=f"p{pid}", tipo="post",
                                     fecha_publicacion=f, caption="CAPTIONSECRETO", n_likes=1))
    for cid, pid, texto, fecha in COMENTARIOS:
        db.add(PercepcionComentario(id=cid, publicacion_id=pid, external_id=f"c{cid}",
                                    autor_hash=f"h{cid}", texto=texto, fecha_comentario=fecha,
                                    idioma="es", n_likes=0, tema="vida_estudiantil"))
        db.add(PercepcionScore(id=cid, comentario_id=cid, modelo="t", sentimiento="POS",
                               prob_pos=1.0, prob_neu=0.0, prob_neg=0.0,
                               emocion="joy", prob_emocion=0.9))
    db.commit()
    derivados.reconstruir(db)
    db.commit()


# ------------------------------------------------------------ tabla derivada
def test_reconstruir_llena_la_tabla_de_etiquetas_sin_handles():
    db = _db()()
    _sembrar(db)
    filas = {c: (n, s) for c, n, s in db.execute(select(
        PercepcionComentarioEtiqueta.comentario_id, PercepcionComentarioEtiqueta.n_etiquetas,
        PercepcionComentarioEtiqueta.solo_etiquetas))}
    assert filas == {1: (1, False), 2: (2, True), 3: (0, False), 4: (0, False),
                     5: (2, True), 6: (0, False), 7: (0, False)}
    assert {c.name for c in PercepcionComentarioEtiqueta.__table__.c} == {
        "comentario_id", "n_etiquetas", "solo_etiquetas"}
    r = derivados.reconstruir(db)              # idempotente
    assert r["etiquetas"] == 3
    assert db.query(PercepcionComentarioEtiqueta).count() == 7


# ------------------------------------------------------------ subtema fijo
def _embedder_registrado(vistos):
    def f(textos):
        vistos.extend(textos)
        return np.array([[1.0, 0.0] for _ in textos])
    return f


def test_los_que_solo_etiquetan_van_a_su_grupo_y_no_se_embeben():
    sesion = _db()
    db = sesion()
    _sembrar(db)
    db.add(PercepcionComentario(id=8, publicacion_id=1, external_id="c8", autor_hash="h8",
                                texto="https://x.cl", fecha_comentario=LU1, idioma="es", n_likes=0,
                                tema="vida_estudiantil"))      # vacío y sin etiquetas
    db.commit()
    vistos: list[str] = []
    r = subtemas.reconstruir_subtemas(db, _embedder_registrado(vistos), modelo="fake",
                                      ahora=datetime(2026, 2, 1))
    db.commit()
    assert vistos and all(v.strip() for v in vistos)           # nunca un texto vacío
    assert len(vistos) == 5                                    # 1, 3, 4, 6, 7
    subs = db.execute(select(PercepcionSubtema).order_by(PercepcionSubtema.orden)).scalars().all()
    # Primero los grupos normales, luego «Etiquetan…», al final «Otros».
    assert [s.etiqueta for s in subs][-2:] == [subtemas.ETIQUETA_ETIQUETAS, subtemas.ETIQUETA_OTROS]
    assert subs[-2].terminos == [] and subs[-2].n_comentarios == 2
    assert subs[-1].n_comentarios == 1
    asig = dict(db.execute(select(PercepcionComentarioSubtema.comentario_id,
                                  PercepcionComentarioSubtema.subtema_id)).all())
    assert asig[2] == asig[5] == subs[-2].id and asig[8] == subs[-1].id
    assert asig[1] not in (subs[-2].id, subs[-1].id)
    assert r["etiquetan"] == 2 and r["asignados"] == 8


def test_el_grupo_de_etiquetas_conserva_el_nombre_manual():
    sesion = _db()
    db = sesion()
    _sembrar(db)
    emb = _embedder_registrado([])
    subtemas.reconstruir_subtemas(db, emb, modelo="fake", ahora=datetime(2026, 2, 1))
    db.commit()
    g = db.execute(select(PercepcionSubtema).where(
        PercepcionSubtema.etiqueta == subtemas.ETIQUETA_ETIQUETAS)).scalar_one()
    g.etiqueta_manual, g.renombrado_por = "Repercusión", "alguien@ucn.cl"
    db.commit()
    subtemas.reconstruir_subtemas(db, emb, modelo="fake", ahora=datetime(2026, 3, 1))
    db.commit()
    g = db.execute(select(PercepcionSubtema).where(
        PercepcionSubtema.etiqueta == subtemas.ETIQUETA_ETIQUETAS)).scalar_one()
    assert g.etiqueta_manual == "Repercusión"


def test_etiquetar_da_nombre_fijo_al_grupo_de_etiquetas():
    r = subtemas.etiquetar({1: {"algo"}, 2: set()}, {1: "a", 2: "b"},
                           {1: 0, 2: subtemas.ETIQUETAS})
    assert r[subtemas.ETIQUETAS] == (subtemas.ETIQUETA_ETIQUETAS, [])


# ------------------------------------------------------------ endpoint
@pytest.fixture()
def cliente():
    Sesion = _db()
    db = Sesion()
    _sembrar(db)

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
            yield c, Sesion
    finally:
        app.dependency_overrides.pop(get_percepcion_db, None)
        accesos.reset()
        db.close()


def _h():
    user = AuthUser(email=LECTOR, name=LECTOR, auth_mode="google")
    token = auth_service.build_login_response(user, message="", next_step="").session_token
    return {"Authorization": f"Bearer {token}"}


def test_repercusion_totales_semanas_y_publicaciones(cliente):
    c, _ = cliente
    r = c.get("/percepcion/repercusion", params={"dias": 36500}, headers=_h())
    assert r.status_code == 200
    j = r.json()
    assert j["disponible"] is True
    assert (j["comentarios"], j["con_etiqueta"], j["solo_etiquetas"], j["porcentaje"]) == (7, 3, 2, 42.9)
    assert j["semanas"] == [
        {"semana": "2026-01-05", "comentarios": 4, "con_etiqueta": 2, "porcentaje": 50.0},
        {"semana": "2026-01-12", "comentarios": 3, "con_etiqueta": 1, "porcentaje": 33.3},
    ]
    assert j["publicaciones"] == [
        {"publicacion_id": 1, "fecha": "2026-01-03", "cuenta": "UCN Antofagasta",
         "n_comentarios": 4, "con_etiqueta": 2, "porcentaje": 50.0},
        {"publicacion_id": 2, "fecha": "2026-01-10", "cuenta": "UCN Coquimbo",
         "n_comentarios": 3, "con_etiqueta": 1, "porcentaje": 33.3},
    ]


def test_repercusion_respeta_filtros_y_limite(cliente):
    c, _ = cliente
    j = c.get("/percepcion/repercusion", params={"dias": 36500, "sede": "Coquimbo"},
              headers=_h()).json()
    assert (j["comentarios"], j["con_etiqueta"], j["porcentaje"]) == (3, 1, 33.3)
    assert [p["publicacion_id"] for p in j["publicaciones"]] == [2]
    j = c.get("/percepcion/repercusion", params={"dias": 36500, "tema": "academico"},
              headers=_h()).json()
    assert j["disponible"] is True and j["comentarios"] == 0 and j["publicaciones"] == []
    j = c.get("/percepcion/repercusion", params={"dias": 36500, "limite": 1}, headers=_h()).json()
    assert len(j["publicaciones"]) == 1
    j = c.get("/percepcion/repercusion",
              params={"fecha_desde": "2026-01-12", "fecha_hasta": "2026-01-14"}, headers=_h()).json()
    assert j["comentarios"] == 3


def test_repercusion_no_devuelve_texto_ni_handles(cliente):
    c, _ = cliente
    r = c.get("/percepcion/repercusion", params={"dias": 36500}, headers=_h())
    for centinela in ("secretohandle", "otro_x", "tote", "cldl", "CAPTIONSECRETO", "gracias", "h2"):
        assert centinela not in r.text


def test_repercusion_sin_la_tabla_no_falla(cliente):
    c, Sesion = cliente
    s = Sesion()
    PercepcionComentarioEtiqueta.__table__.drop(s.get_bind())
    s.close()
    r = c.get("/percepcion/repercusion", params={"dias": 36500}, headers=_h())
    assert r.status_code == 200
    j = r.json()
    assert j["disponible"] is False and j["comentarios"] == 0
    assert j["semanas"] == [] and j["publicaciones"] == []


def test_repercusion_requiere_sesion(cliente):
    c, _ = cliente
    assert c.get("/percepcion/repercusion").status_code in (401, 403)
