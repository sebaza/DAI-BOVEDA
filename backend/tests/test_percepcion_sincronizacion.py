"""Sincronización incremental worker (SQLite) -> Bóveda (`services/percepcion/sincronizacion.py`).

Dos bases en memoria con los modelos: el ORIGEN con la forma del worker y el DESTINO con la
de la Bóveda (incluye derivadas). Los textos llevan centinelas para comprobar que el
respaldo jamás contiene texto de comentarios.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.percepcion import sincronizacion
from app.services.percepcion.models import (
    PercepcionComentario as C,
    PercepcionComentarioToken as T,
    PercepcionCorreccion as Corr,
    PercepcionCuenta as Cu,
    PercepcionEvento as Ev,
    PercepcionHechoDiario as H,
    PercepcionPublicacion as P,
    PercepcionScore as S,
    PercepcionSubtema as Sub,
)

CENTINELA = "zzcentinelaunico"
F = datetime(2026, 3, 2, 10)


def _sesion(ruta):
    # Archivo y no ":memory:" con StaticPool: ahí `reagregar` inspecciona con OTRA
    # conexión, y en SQLite en memoria es la misma, así que el inspect revertiría los INSERT.
    eng = create_engine(f"sqlite:///{ruta.as_posix()}", future=True)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, future=True)()


def _cuenta(s, id_):
    s.add(Cu(id=id_, handle=f"h{id_}", nombre="N", tipo="institucional", campus="Antofagasta",
             facultad="Ingeniería", origen="interno"))


def _pub(s, id_, cuenta_id, ext=None):
    s.add(P(id=id_, cuenta_id=cuenta_id, external_id=ext or f"p{id_}", fecha_publicacion=F,
            tipo="post", caption=f"caption {CENTINELA}", n_comentarios=0, n_likes=0))


def _com(s, id_, pub_id, tema="otros", ext=None, sent="POS"):
    s.add(C(id=id_, publicacion_id=pub_id, external_id=ext or f"c{id_}", autor_hash=f"a{id_}",
            texto=f"el arancel {CENTINELA} {id_}", fecha_comentario=F, idioma="es",
            n_likes=0, tema=tema, tema_confianza=0.5))
    s.add(S(id=id_, comentario_id=id_, modelo="m", sentimiento=sent, prob_pos=0.9,
            prob_neu=0.05, prob_neg=0.05))


@pytest.fixture
def bases(tmp_path):
    origen, destino = _sesion(tmp_path / "origen.db"), _sesion(tmp_path / "destino.db")
    # Ambos: cuenta 1, pub 1, comentarios 1 y 2 (el 1 con tema curado en el destino).
    for s in (origen, destino):
        _cuenta(s, 1)
        _pub(s, 1, 1)
        _com(s, 1, 1, tema="infraestructura" if s is destino else "otros")
        _com(s, 2, 1)
    # Origen adelantado: cuenta 2, pub 2, comentarios 3 y 4, un evento.
    _cuenta(origen, 2)
    _pub(origen, 2, 2)
    _com(origen, 3, 2, tema="matricula_aranceles")
    _com(origen, 4, 1, tema="otros", sent="NEG")
    origen.add(Ev(id=1, nombre="Paro", tipo="paro", fecha_inicio=date(2026, 3, 1)))
    origen.commit()
    destino.commit()
    yield origen, destino
    origen.close()
    destino.close()


def _n(s, modelo):
    return s.scalar(select(func.count()).select_from(modelo))


def test_inserta_solo_lo_nuevo_en_orden_de_claves(bases):
    origen, destino = bases
    r = sincronizacion.sincronizar(origen, destino)
    destino.commit()
    assert r.insertados == {
        "percepcion_cuenta": 1, "percepcion_publicacion": 1, "percepcion_comentario": 2,
        "percepcion_score": 2, "percepcion_evento": 1,
    }
    assert list(r.insertados) == ["percepcion_cuenta", "percepcion_publicacion",
                                  "percepcion_comentario", "percepcion_score", "percepcion_evento"]
    assert _n(destino, C) == 4 and _n(destino, S) == 4 and _n(destino, Cu) == 2


def test_no_pisa_el_tema_curado_aunque_el_origen_difiera(bases):
    origen, destino = bases
    sincronizacion.sincronizar(origen, destino)
    destino.commit()
    assert destino.get(C, 1).tema == "infraestructura"
    assert origen.get(C, 1).tema == "otros"


def test_idempotente(bases):
    origen, destino = bases
    sincronizacion.sincronizar(origen, destino)
    destino.commit()
    r = sincronizacion.sincronizar(origen, destino)
    assert sum(r.insertados.values()) == 0


def test_conflicto_mismo_id_otra_clave_natural_aborta_sin_escribir(bases):
    origen, destino = bases
    origen.get(C, 2).external_id = "distinto"
    origen.commit()
    with pytest.raises(sincronizacion.ConflictoSincronizacion) as exc:
        sincronizacion.sincronizar(origen, destino)
    assert exc.value.conflictos["percepcion_comentario"] == 1
    destino.rollback()
    assert _n(destino, C) == 2 and _n(destino, Cu) == 1 and _n(destino, Ev) == 0


def test_conflicto_clave_natural_nueva_ya_existe_con_otro_id(bases):
    origen, destino = bases
    # Id nuevo (9) pero (publicacion 1, 'c1') ya existe en el destino con id 1.
    origen.add(C(id=9, publicacion_id=1, external_id="c1", autor_hash="x", texto="t",
                 fecha_comentario=F, idioma="es", n_likes=0))
    origen.commit()
    with pytest.raises(sincronizacion.ConflictoSincronizacion) as exc:
        sincronizacion.sincronizar(origen, destino)
    assert exc.value.conflictos["percepcion_comentario"] == 1
    assert _n(destino, C) == 2


def test_cuenta_nueva_con_handle_existente_aborta(bases):
    origen, destino = bases
    origen.add(Cu(id=9, handle="h1", nombre="N", tipo="institucional", campus="Antofagasta",
                  facultad="Ingeniería", origen="interno"))
    origen.commit()
    with pytest.raises(sincronizacion.ConflictoSincronizacion) as exc:
        sincronizacion.sincronizar(origen, destino)
    assert exc.value.conflictos["percepcion_cuenta"] == 1
    destino.rollback()
    assert _n(destino, Cu) == 1


def test_evento_nuevo_igual_a_uno_manual_con_otro_id_aborta(bases):
    origen, destino = bases
    destino.add(Ev(id=50, nombre="Paro", tipo="paro", fecha_inicio=date(2026, 5, 1)))
    destino.commit()
    origen.add(Ev(id=7, nombre="Paro", tipo="paro", fecha_inicio=date(2026, 5, 1), fuente="worker"))
    origen.commit()
    with pytest.raises(sincronizacion.ConflictoSincronizacion) as exc:
        sincronizacion.sincronizar(origen, destino)
    assert exc.value.conflictos["percepcion_evento"] == 1
    destino.rollback()
    assert _n(destino, Ev) == 1


def test_huerfano_aborta(bases):
    origen, destino = bases
    origen.add(C(id=9, publicacion_id=999, external_id="c9", autor_hash="x", texto="t",
                 fecha_comentario=F, idioma="es", n_likes=0))
    origen.commit()
    with pytest.raises(sincronizacion.ConflictoSincronizacion):
        sincronizacion.sincronizar(origen, destino)
    assert _n(destino, C) == 2


def test_dry_run_no_escribe_y_cuenta(bases):
    origen, destino = bases
    r = sincronizacion.sincronizar(origen, destino, simular=True)
    destino.rollback()
    assert r.insertados["percepcion_comentario"] == 2
    assert _n(destino, C) == 2 and _n(destino, Ev) == 0 and _n(destino, H) == 0


def test_dry_run_con_conflictos_los_informa_sin_lanzar(bases):
    origen, destino = bases
    origen.get(C, 2).external_id = "distinto"
    origen.commit()
    r = sincronizacion.sincronizar(origen, destino, simular=True)
    assert r.conflictos["percepcion_comentario"] == 1


def test_hecho_diario_se_reconstruye_respetando_la_curacion(bases):
    origen, destino = bases
    sincronizacion.sincronizar(origen, destino)
    destino.commit()
    por_tema = {t: n for t, n in destino.execute(
        select(H.tema, func.sum(H.n_comentarios)).group_by(H.tema))}
    # Comentario 1 conserva el tema curado; 2 y 4 son 'otros'; 3 es el nuevo.
    assert por_tema == {"infraestructura": 1, "otros": 2, "matricula_aranceles": 1}


def test_derivados_incluyen_los_comentarios_nuevos(bases):
    origen, destino = bases
    sincronizacion.sincronizar(origen, destino)
    destino.commit()
    con_tokens = set(destino.scalars(select(T.comentario_id).distinct()))
    assert {3, 4} <= con_tokens


def test_sin_derivados_no_toca_hechos_ni_tokens(bases):
    origen, destino = bases
    r = sincronizacion.sincronizar(origen, destino, con_derivados=False)
    destino.commit()
    assert r.hechos is None and _n(destino, H) == 0 and _n(destino, T) == 0


def test_respaldo_tiene_conteos_y_nunca_texto_de_comentarios(bases, tmp_path):
    _, destino = bases
    destino.add(Corr(comentario_id=1, campo="tema", valor_original="otros",
                     valor_nuevo="infraestructura", justificacion="revisión manual",
                     autor="ana@ucn.cl", creado_en=F))
    destino.add(Sub(tema="otros", orden=1, etiqueta="e", terminos=[], n_comentarios=1,
                    modelo="m", generado_en=F, etiqueta_manual="Nombre puesto"))
    destino.commit()
    ruta = sincronizacion.respaldar(destino, tmp_path, ahora=datetime(2026, 1, 2, 3, 4, 5))
    assert ruta.name == "sync-20260102T030405Z.json"
    crudo = ruta.read_text(encoding="utf-8")
    assert CENTINELA not in crudo and "arancel" not in crudo
    datos = json.loads(crudo)
    assert datos["conteos"] == {"percepcion_correccion": 1, "percepcion_subtema": 1}
    assert datos["percepcion_correccion"][0]["valor_nuevo"] == "infraestructura"
    assert datos["percepcion_subtema"][0]["etiqueta_manual"] == "Nombre puesto"
