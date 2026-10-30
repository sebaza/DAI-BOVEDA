"""Sincronización hacia el almacén: `autor_hash` y `external_id` nuevos seudonimizados solo si el destino está marcado.

Las marcas son las filas `autor_seudonimizado` y `ext_comentario_seudonimizado` (ambas `true`) de
`percepcion_meta` (las escribe
`scripts/publicar_warehouse_percepcion.py`). Mismas bases de archivo que
`test_percepcion_sincronizacion.py`; claves generadas en cada test.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base
from app.services.percepcion import cripto, sincronizacion
from app.services.percepcion.models import (
    META_AUTOR_SEUDONIMIZADO,
    META_EXT_COMENTARIO_SEUDONIMIZADO,
    PercepcionComentario as C,
    PercepcionCuenta as Cu,
    PercepcionMeta,
    PercepcionPublicacion as P,
    PercepcionScore as S,
)

F = datetime(2026, 3, 2, 10)


def _clave() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


@pytest.fixture()
def claves(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "percepcion_clave_texto", _clave())
    monkeypatch.setattr(s, "percepcion_clave_id", _clave())
    monkeypatch.setattr(s, "percepcion_clave_version", "1")
    monkeypatch.setattr(s, "percepcion_claves_anteriores", "")
    return s


def _sesion(ruta):
    eng = create_engine(f"sqlite:///{ruta.as_posix()}", future=True)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, future=True)()


def _com(s, id_, ext=None):
    s.add(C(id=id_, publicacion_id=1, external_id=ext or f"c{id_}", autor_hash=f"autor-worker-{id_}",
            texto=f"comentario {id_}", fecha_comentario=F, idioma="es", n_likes=0,
            tema="otros", tema_confianza=0.5))
    s.add(S(id=id_, comentario_id=id_, modelo="m", sentimiento="POS", prob_pos=0.9,
            prob_neu=0.05, prob_neg=0.05))


@pytest.fixture()
def bases(tmp_path, claves):
    """Destino con el comentario 1 (ya cargado); el origen suma el 2 y el 3."""
    origen, destino = _sesion(tmp_path / "o.db"), _sesion(tmp_path / "d.db")
    for s in (origen, destino):
        s.add(Cu(id=1, handle="h1", nombre="N", tipo="institucional", campus="Antofagasta",
                 facultad="Ingeniería", origen="interno"))
        s.add(P(id=1, cuenta_id=1, external_id="p1", fecha_publicacion=F, tipo="post",
                caption=None, n_comentarios=0, n_likes=0))
        _com(s, 1)
    _com(origen, 2)
    _com(origen, 3)
    origen.commit()
    destino.commit()
    yield origen, destino
    origen.close()
    destino.close()


def _marcar(destino, autor="true", ext="true"):
    """Marca el destino como almacén y deja el comentario 1 como lo dejaría la carga (seudonimizado)."""
    if autor is not None:
        destino.add(PercepcionMeta(clave=META_AUTOR_SEUDONIMIZADO, valor=autor))
    if ext is not None:
        destino.add(PercepcionMeta(clave=META_EXT_COMENTARIO_SEUDONIMIZADO, valor=ext))
    c = destino.get(C, 1)
    c.autor_hash = cripto.seudonimo("autor-worker-1", "autor")
    c.external_id = cripto.seudonimo("c1", "comentario_ext")
    destino.commit()


def _autores(s):
    return dict(s.execute(select(C.id, C.autor_hash)).all())


def _externos(s):
    return dict(s.execute(select(C.id, C.external_id)).all())


def test_destino_marcado_seudonimiza_autor_y_external_id_nuevos(bases):
    origen, destino = bases
    _marcar(destino)
    r = sincronizacion.sincronizar(origen, destino)
    destino.commit()
    a, e = _autores(destino), _externos(destino)
    assert r.autor_seudonimizado and r.autores_seudonimizados == 2
    assert a[1] == cripto.seudonimo("autor-worker-1", "autor")      # lo que ya estaba no se toca
    for i in (2, 3):
        assert a[i] == cripto.seudonimo(f"autor-worker-{i}", "autor") != f"autor-worker-{i}"
        assert e[i] == cripto.seudonimo(f"c{i}", "comentario_ext") != f"c{i}"
        assert len(e[i]) == 64 <= 80                                  # cabe en String(80)
    assert _externos(origen)[2] == "c2"                               # el worker no se modifica


def test_destino_marcado_no_aplica_el_seudonimo_dos_veces_y_reconoce_lo_presente(bases):
    origen, destino = bases
    _marcar(destino)
    sincronizacion.sincronizar(origen, destino)
    destino.commit()
    antes = (_autores(destino), _externos(destino))
    r = sincronizacion.sincronizar(origen, destino)
    destino.commit()
    # La clave natural del origen se compara ya seudonimizada: nada se duplica ni choca.
    assert sum(r.insertados.values()) == 0 and r.autores_seudonimizados == 0 and not r.conflictos
    assert (_autores(destino), _externos(destino)) == antes
    assert _autores(origen)[2] == "autor-worker-2"


def test_destino_marcado_detecta_conflictos_de_clave_natural(bases):
    origen, destino = bases
    _marcar(destino)
    # Mismo id, otra clave natural.
    origen.get(C, 1).external_id = "distinto"
    origen.commit()
    r = sincronizacion.sincronizar(origen, destino, simular=True)
    assert r.conflictos["percepcion_comentario"] == 1
    with pytest.raises(sincronizacion.ConflictoSincronizacion):
        sincronizacion.sincronizar(origen, destino)
    destino.rollback()
    assert set(_autores(destino)) == {1}


def test_destino_marcado_clave_natural_nueva_que_ya_existe_con_otro_id(bases):
    origen, destino = bases
    _marcar(destino)
    # Id nuevo (9) pero (publicacion 1, 'c1') ya existe en el destino (con id 1, seudonimizado).
    origen.add(C(id=9, publicacion_id=1, external_id="c1", autor_hash="x", texto="t",
                 fecha_comentario=F, idioma="es", n_likes=0))
    origen.commit()
    with pytest.raises(sincronizacion.ConflictoSincronizacion) as exc:
        sincronizacion.sincronizar(origen, destino)
    assert exc.value.conflictos["percepcion_comentario"] == 1


def test_destino_sin_marca_conserva_autor_y_external_id_del_worker(bases):
    origen, destino = bases
    r = sincronizacion.sincronizar(origen, destino)
    destino.commit()
    assert not r.autor_seudonimizado and r.autores_seudonimizados == 0
    assert _autores(destino) == {1: "autor-worker-1", 2: "autor-worker-2", 3: "autor-worker-3"}
    assert _externos(destino) == {1: "c1", 2: "c2", 3: "c3"}


def test_marca_distinta_de_true_no_cuenta(bases):
    origen, destino = bases
    _marcar(destino, "false", "false")
    destino.get(C, 1).external_id = "c1"
    destino.commit()
    sincronizacion.sincronizar(origen, destino)
    destino.commit()
    assert _autores(destino)[2] == "autor-worker-2" and _externos(destino)[2] == "c2"


@pytest.mark.parametrize("autor,ext", [("true", None), (None, "true"), ("true", "false"), ("false", "true")])
def test_una_sola_marca_es_inconsistente_y_se_niega(bases, autor, ext):
    origen, destino = bases
    _marcar(destino, autor, ext)
    with pytest.raises(sincronizacion.MarcasInconsistentes):
        sincronizacion.sincronizar(origen, destino)
    with pytest.raises(sincronizacion.MarcasInconsistentes):
        sincronizacion.sincronizar(origen, destino, simular=True)
    destino.rollback()
    assert set(_autores(destino)) == {1}


def test_marcado_sin_clave_de_id_se_niega_antes_de_escribir(bases, monkeypatch, claves):
    origen, destino = bases
    _marcar(destino)
    monkeypatch.setattr(claves, "percepcion_clave_id", "")
    with pytest.raises(cripto.ClaveNoConfigurada, match="PERCEPCION_CLAVE_ID"):
        sincronizacion.sincronizar(origen, destino)
    destino.rollback()
    assert set(_autores(destino)) == {1}
    # También la simulación avisa: mejor enterarse en el ensayo que a mitad de la corrida real.
    with pytest.raises(cripto.ClaveNoConfigurada):
        sincronizacion.sincronizar(origen, destino, simular=True)


def test_sin_marca_y_sin_clave_de_id_funciona_como_siempre(bases, monkeypatch, claves):
    origen, destino = bases
    monkeypatch.setattr(claves, "percepcion_clave_id", "")
    sincronizacion.sincronizar(origen, destino)
    destino.commit()
    assert set(_autores(destino)) == {1, 2, 3}
