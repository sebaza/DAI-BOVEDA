"""Cifrado reversible del texto crudo (fase A2): `cripto`, lectores, migración y sincronización.

Las claves se generan dentro de cada test con `os.urandom` (nunca hay una clave literal) y los
textos son sintéticos. Ningún test imprime texto ni claves.
"""
from __future__ import annotations

import base64
import importlib.util
import os
import zlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base
from app.services.percepcion import cripto, curacion, derivados, sincronizacion, subtemas
from app.services.percepcion.models import (
    PercepcionComentario as C,
    PercepcionComentarioEtiqueta as E,
    PercepcionComentarioFamilia as F,
    PercepcionComentarioSubtema as CS,
    PercepcionComentarioToken as T,
    PercepcionCuenta as Cu,
    PercepcionPublicacion as P,
    PercepcionPublicacionRasgo as R,
    PercepcionScore as S,
    PercepcionSubtema as Sub,
)


def _clave() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def _cargar_script(nombre: str):
    ruta = Path(__file__).resolve().parents[2] / "scripts" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cifrar_textos = _cargar_script("cifrar_textos_percepcion")
generar_claves = _cargar_script("generar_claves_percepcion")


@pytest.fixture()
def claves(monkeypatch):
    """Configura claves nuevas sobre el singleton de settings; devuelve un manejador."""
    s = get_settings()

    class Manejador:
        def poner(self, texto=None, id_=None, version="1", anteriores=""):
            monkeypatch.setattr(s, "percepcion_clave_texto", texto if texto is not None else _clave())
            monkeypatch.setattr(s, "percepcion_clave_id", id_ if id_ is not None else _clave())
            monkeypatch.setattr(s, "percepcion_clave_version", version)
            monkeypatch.setattr(s, "percepcion_claves_anteriores", anteriores)

        def quitar(self):
            for n in ("percepcion_clave_texto", "percepcion_clave_id", "percepcion_claves_anteriores"):
                monkeypatch.setattr(s, n, "")

    m = Manejador()
    m.poner()
    return m


# ---------------------------------------------------------------- cripto
def test_ida_y_vuelta_y_formato(claves):
    c = cripto.cifrar("Hola ñandú 😀", "comentario:1")
    assert c.startswith("enc:1:") and cripto.es_cifrado(c)
    assert "ñandú" not in c
    assert cripto.descifrar(c, "comentario:1") == "Hola ñandú 😀"


def test_nonce_distinto_en_cada_llamada(claves):
    a = cripto.cifrar("igual", "comentario:1")
    b = cripto.cifrar("igual", "comentario:1")
    assert a != b
    assert cripto.descifrar(a, "comentario:1") == cripto.descifrar(b, "comentario:1") == "igual"


def test_none_y_vacio_pasan_sin_cambios(claves):
    assert cripto.cifrar(None, "comentario:1") is None
    assert cripto.cifrar("", "comentario:1") == ""
    assert cripto.descifrar(None, "comentario:1") is None
    assert cripto.descifrar("", "comentario:1") == ""


def test_clave_equivocada_falla(claves):
    c = cripto.cifrar("secreto", "comentario:1")
    claves.poner()                       # otra clave, misma versión
    with pytest.raises(cripto.TextoIlegible):
        cripto.descifrar(c, "comentario:1")


def test_alterado_falla(claves):
    c = cripto.cifrar("secreto", "comentario:1")
    cuerpo = c.split(":", 2)[2]
    cambiado = ("A" if cuerpo[20] != "A" else "B")
    alterado = "enc:1:" + cuerpo[:20] + cambiado + cuerpo[21:]
    with pytest.raises(cripto.TextoIlegible):
        cripto.descifrar(alterado, "comentario:1")
    with pytest.raises(cripto.TextoIlegible):
        cripto.descifrar(c[:-4], "comentario:1")     # truncado


def test_cambiar_de_fila_falla(claves):
    c = cripto.cifrar_texto(7, "secreto")
    assert cripto.texto_de(7, c) == "secreto"
    with pytest.raises(cripto.TextoIlegible):
        cripto.texto_de(8, c)                        # movido a otro comentario
    with pytest.raises(cripto.TextoIlegible):
        cripto.caption_de(7, c)                      # movido a otra tabla


def test_texto_plano_pasa_igual(claves):
    assert cripto.descifrar("hola mundo", "comentario:1") == "hola mundo"
    assert cripto.descifrar("enc: no es un cifrado", "comentario:1") == "enc: no es un cifrado"
    assert not cripto.es_cifrado("hola") and not cripto.es_cifrado(None)


def test_cifrado_sin_clave_lanza_clave_no_configurada(claves):
    c = cripto.cifrar("secreto", "comentario:1")
    claves.quitar()
    with pytest.raises(cripto.ClaveNoConfigurada) as exc:
        cripto.descifrar(c, "comentario:1")
    assert cripto.VAR_CLAVE_TEXTO in str(exc.value)
    with pytest.raises(cripto.ClaveNoConfigurada):
        cripto.cifrar("otro", "comentario:1")


def test_rotacion_las_claves_anteriores_siguen_descifrando(claves):
    vieja = _clave()
    claves.poner(texto=vieja, version="1")
    c1 = cripto.cifrar("antes", "comentario:1")
    claves.poner(texto=_clave(), version="2", anteriores=f"1:{vieja}")
    c2 = cripto.cifrar("despues", "comentario:1")
    assert c1.startswith("enc:1:") and c2.startswith("enc:2:")
    assert cripto.descifrar(c1, "comentario:1") == "antes"
    assert cripto.descifrar(c2, "comentario:1") == "despues"
    claves.poner(texto=_clave(), version="2", anteriores="")       # sin la clave vieja
    with pytest.raises(cripto.TextoIlegible):                      # aislable, no detiene el lote
        cripto.descifrar(c1, "comentario:1")


def test_version_desconocida_forjada_no_detiene_los_lotes(claves):
    forjado = "enc:9:" + "a" * 40                                  # un comentario público así
    fallos: list[int] = []
    assert cripto.texto_de_seguro(7, forjado, fallos) == "" and fallos == [7]
    assert cripto.es_genuino(forjado, "comentario:7") is False     # la migración lo cifra
    claves.poner(texto="", anteriores="")                          # sin ninguna clave
    with pytest.raises(cripto.ClaveNoConfigurada):
        cripto.descifrar(forjado, "comentario:7")


def test_seudonimo_determinista_y_separado_por_dominio(claves):
    a = cripto.seudonimo("autor123", "autor")
    assert a == cripto.seudonimo("autor123", "autor")
    assert len(a) == 64 and int(a, 16) >= 0
    assert a != cripto.seudonimo("autor123", "etiqueta")
    assert a != cripto.seudonimo("autor124", "autor")
    claves.poner()                                                 # otra clave de id
    assert a != cripto.seudonimo("autor123", "autor")


def test_seudonimo_sin_clave_id_falla(claves):
    s = get_settings()
    claves.poner(id_="")
    assert s.percepcion_clave_id == ""
    with pytest.raises(cripto.ClaveNoConfigurada):
        cripto.seudonimo("x", "autor")


@pytest.mark.parametrize("mala", ["no es base64 !!", base64.urlsafe_b64encode(b"corta").decode(),
                                  base64.urlsafe_b64encode(os.urandom(33)).decode()])
def test_validacion_de_claves_nombra_la_variable_no_el_valor(claves, mala):
    claves.poner(texto=mala)
    with pytest.raises(cripto.ClaveInvalida) as exc:
        cripto.cifrar("x", "comentario:1")
    assert cripto.VAR_CLAVE_TEXTO in str(exc.value)
    assert mala.strip() not in str(exc.value)
    claves.poner(id_=mala)
    with pytest.raises(cripto.ClaveInvalida) as exc2:
        cripto.seudonimo("x", "autor")
    assert cripto.VAR_CLAVE_ID in str(exc2.value) and mala not in str(exc2.value)


def test_claves_anteriores_mal_formadas(claves):
    claves.poner(anteriores="sin-dos-puntos")
    with pytest.raises(cripto.ClaveInvalida) as exc:
        cripto.cifrar("x", "comentario:1")
    assert cripto.VAR_CLAVES_ANTERIORES in str(exc.value)
    malo = "corta"
    claves.poner(anteriores=f"1:{malo}")
    with pytest.raises(cripto.ClaveInvalida) as exc2:
        cripto.cifrar("x", "comentario:1")
    assert malo not in str(exc2.value)


def test_generar_claves_son_validas_y_distintas(claves):
    g = generar_claves.generar_claves()
    assert set(g) == {"PERCEPCION_CLAVE_TEXTO", "PERCEPCION_CLAVE_ID"}
    assert g["PERCEPCION_CLAVE_TEXTO"] != g["PERCEPCION_CLAVE_ID"]
    claves.poner(texto=g["PERCEPCION_CLAVE_TEXTO"], id_=g["PERCEPCION_CLAVE_ID"])
    assert cripto.descifrar(cripto.cifrar("ok", "comentario:1"), "comentario:1") == "ok"
    assert len(cripto.seudonimo("x", "autor")) == 64


# ---------------------------------------------------------------- lectores y migración
TEXTOS = [
    "el arancel el arancel y otra vez arancel subió",
    "Hay paro mañana? la asamblea decide https://x.cl @alguien",
    "Seca! comments from Facebook marcha blanca",
    "jajaja toma de la universidad 😂 @pedro @maria",
    "arancel caro, la matrícula también",
    "gratuidad para todos los campus de la ucn",
    "estacionamiento lleno otra vez en el campus",
]


def _db(n: int = 24):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, future=True)()
    db.add(Cu(id=1, handle="ucn", nombre="UCN", tipo="institucional", campus="Antofagasta",
              facultad="Ingeniería"))
    db.add(P(id=1, cuenta_id=1, external_id="p1", tipo="post", fecha_publicacion=datetime(2026, 1, 1),
             caption="Gran #marcha en el campus 😀 ¿vienes? @ucn", n_likes=1))
    db.add(P(id=2, cuenta_id=1, external_id="p2", tipo="reel", fecha_publicacion=datetime(2026, 1, 2),
             caption=None, n_likes=1))
    for i in range(1, n + 1):
        t = TEXTOS[i % len(TEXTOS)] + (" gratuidad" if i <= n // 2 else " estacionamiento") + f" {i}"
        db.add(C(id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}", texto=t,
                 fecha_comentario=datetime(2026, 1, 2), idioma="es", n_likes=1,
                 tema="otros" if i % 3 == 0 else "academico", tema_confianza=0.9))
        db.add(S(id=i, comentario_id=i, modelo="t", sentimiento="NEG", prob_pos=0.0, prob_neu=0.1,
                 prob_neg=0.9, emocion="anger", prob_emocion=0.9))
    db.commit()
    return engine, db


def _derivados(db):
    return {
        "tokens": sorted(db.execute(select(T.comentario_id, T.token)).all()),
        "familias": sorted(db.execute(select(F.comentario_id, F.familia)).all()),
        "etiquetas": sorted(db.execute(select(E.comentario_id, E.n_etiquetas, E.solo_etiquetas)).all()),
        "rasgos": sorted(tuple(r) for r in db.execute(select(*R.__table__.c)).all()),
    }


def _embedder(textos):
    filas = []
    for t in textos:
        v = np.zeros(8)
        v[0 if "gratuidad" in t else 1] = 1.0
        v += np.random.default_rng(zlib.crc32(t.encode())).normal(0, 0.02, 8)
        filas.append(v)
    return np.array(filas)


def _subtemas(db):
    subtemas.reconstruir_subtemas(db, _embedder, modelo="fake", ahora=datetime(2026, 2, 1), min_tamano=5)
    db.commit()
    etiqueta = {i: (t, e, tuple(tt)) for i, t, e, tt in
                db.execute(select(Sub.id, Sub.tema, Sub.etiqueta, Sub.terminos)).all()}
    return sorted((cid, etiqueta[sid]) for cid, sid in db.execute(
        select(CS.comentario_id, CS.subtema_id)).all())


def _crudo(db):
    return {i: t for i, t in db.execute(text("SELECT id, texto FROM percepcion_comentario"))}, \
           {i: c for i, c in db.execute(text("SELECT id, caption FROM percepcion_publicacion"))}


def test_migracion_cifra_y_derivados_quedan_identicos(claves):
    engine, db = _db()
    derivados.reconstruir(db)
    db.commit()
    antes = _derivados(db)
    antes_sub = _subtemas(db) if importlib.util.find_spec("sklearn") else None
    com0, pub0 = _crudo(db)

    with engine.begin() as conn:
        r = cifrar_textos.transformar(conn)
    assert r["percepcion_comentario.texto"] == {"cambiadas": 24, "ya_listas": 0, "ilegibles": 0}
    assert r["percepcion_publicacion.caption"] == {"cambiadas": 1, "ya_listas": 0, "ilegibles": 0}   # el NULL no cuenta

    db.expire_all()
    com1, pub1 = _crudo(db)
    assert all(cripto.es_cifrado(v) for v in com1.values())
    assert cripto.es_cifrado(pub1[1]) and pub1[2] is None
    assert not any("arancel" in v for v in com1.values())

    derivados.reconstruir(db)
    db.commit()
    assert _derivados(db) == antes
    if antes_sub is not None:
        assert _subtemas(db) == antes_sub

    # Idempotente: otra pasada no cambia nada.
    with engine.begin() as conn:
        r2 = cifrar_textos.transformar(conn)
    assert r2["percepcion_comentario.texto"] == {"cambiadas": 0, "ya_listas": 24, "ilegibles": 0}
    assert _crudo(db)[0] == com1

    # --descifrar restaura EXACTAMENTE lo original.
    with engine.begin() as conn:
        r3 = cifrar_textos.transformar(conn, descifrar=True)
    assert r3["percepcion_comentario.texto"]["cambiadas"] == 24
    db.expire_all()
    assert _crudo(db) == (com0, pub0)
    with engine.begin() as conn:
        assert cifrar_textos.transformar(conn, descifrar=True)["percepcion_comentario.texto"]["cambiadas"] == 0


def test_dry_run_solo_cuenta_y_no_necesita_claves(claves):
    engine, db = _db(6)
    com0, pub0 = _crudo(db)
    claves.quitar()
    with engine.begin() as conn:
        r = cifrar_textos.transformar(conn, dry_run=True)
    assert r["percepcion_comentario.texto"]["cambiadas"] == 6
    assert _crudo(db) == (com0, pub0)


def test_main_imprime_ambas_columnas_sin_texto(claves, monkeypatch, capsys):
    engine, db = _db(6)
    monkeypatch.setattr(cifrar_textos, "create_engine", lambda *a, **k: engine)
    monkeypatch.setattr(engine, "dispose", lambda: None)    # la base en memoria muere al cerrar
    for argv in (["--url", "sqlite://", "--dry-run"], ["--url", "sqlite://"]):
        assert cifrar_textos.main(argv) == 0
        salida = capsys.readouterr().out
        assert "percepcion_comentario.texto: cambiadas=" in salida
        assert "percepcion_publicacion.caption: cambiadas=" in salida
        assert "arancel" not in salida and "marcha" not in salida


def test_migracion_sin_claves_no_escribe_nada(claves):
    engine, db = _db(3)
    com0, _ = _crudo(db)
    claves.quitar()
    with pytest.raises(cripto.ClaveNoConfigurada):
        with engine.begin() as conn:
            cifrar_textos.transformar(conn)
    assert _crudo(db)[0] == com0


def test_migracion_atomica_si_falla_a_mitad(claves, monkeypatch):
    engine, db = _db(6)
    com0, pub0 = _crudo(db)
    llamadas = {"n": 0}
    real = cripto.cifrar_texto

    def falla(id_, valor):
        llamadas["n"] += 1
        if llamadas["n"] == 4:
            raise RuntimeError("falla simulada")
        return real(id_, valor)

    monkeypatch.setattr(cifrar_textos, "OBJETIVOS",
                        [(cifrar_textos.OBJETIVOS[0][0], "texto", falla, cripto.texto_de),
                         cifrar_textos.OBJETIVOS[1]])
    with pytest.raises(RuntimeError):
        with engine.begin() as conn:
            cifrar_textos.transformar(conn)
    db.expire_all()
    assert _crudo(db) == (com0, pub0)


def test_curacion_devuelve_el_mismo_texto_con_y_sin_cifrado(claves):
    engine, db = _db()

    def vistas():
        a = curacion.comentarios_a_curar(db, limite=50)
        b = curacion.publicaciones_a_curar(db)
        c = curacion.comentarios_para_scoring(db, limite=50, orden="reciente", solo_pendientes=False)
        d = curacion.comentarios_para_scoring(db, limite=50, orden="aleatorio", solo_pendientes=False)
        e = curacion.comentarios_para_scoring(db, limite=50, orden="adversos", solo_pendientes=False)
        f = curacion.comentarios_para_scoring(db, limite=50, orden="estratificado", solo_pendientes=False)
        return a, b, c, d, e, f

    antes = vistas()
    assert antes[0]["items"] and antes[2]["items"]
    with engine.begin() as conn:
        cifrar_textos.transformar(conn)
    db.expire_all()
    despues = vistas()
    assert despues == antes
    assert any(i["caption"].startswith("Gran #marcha") for i in despues[0]["items"])


def test_resumen_descifra_los_captions(claves):
    from app.services.percepcion import resumen_llm
    engine, db = _db(6)
    alc = {"campus": None, "facultad": None}
    args = (db, datetime(2026, 1, 1).date(), datetime(2026, 1, 31).date(), alc)
    antes = resumen_llm._publicaciones(*args)
    assert antes and antes[0]["caption"].startswith("Gran #marcha")
    with engine.begin() as conn:
        cifrar_textos.transformar(conn)
    db.expire_all()
    assert resumen_llm._publicaciones(*args) == antes


# ---------------------------------------------------------------- sincronización
def _origen_destino(tmp_path):
    def sesion(ruta):
        eng = create_engine(f"sqlite:///{ruta.as_posix()}", future=True)
        Base.metadata.create_all(eng)
        return sessionmaker(bind=eng, future=True)()
    o, d = sesion(tmp_path / "o.db"), sesion(tmp_path / "d.db")
    o.add(Cu(id=1, handle="h", nombre="N", tipo="institucional", campus="Antofagasta",
             facultad="Ingeniería", origen="interno"))
    o.add(P(id=3, cuenta_id=1, external_id="p3", fecha_publicacion=datetime(2026, 3, 2), tipo="post",
            caption="caption sintetico", n_comentarios=0, n_likes=0))
    o.add(C(id=9, publicacion_id=3, external_id="c9", autor_hash="a9", texto="comentario sintetico",
            fecha_comentario=datetime(2026, 3, 2), idioma="es", n_likes=0, tema="otros", tema_confianza=0.5))
    o.add(S(id=9, comentario_id=9, modelo="m", sentimiento="POS", prob_pos=0.9, prob_neu=0.05, prob_neg=0.05))
    o.commit()
    return o, d


def test_sincronizacion_cifra_las_filas_nuevas(claves, tmp_path):
    o, d = _origen_destino(tmp_path)
    res = sincronizacion.sincronizar(o, d)
    d.commit()
    assert res.sin_cifrar == 0
    com, pub = _crudo(d)
    assert cripto.es_cifrado(com[9]) and cripto.es_cifrado(pub[3])
    assert cripto.texto_de(9, com[9]) == "comentario sintetico"
    assert cripto.caption_de(3, pub[3]) == "caption sintetico"
    # El origen (worker) no se toca.
    assert _crudo(o)[0][9] == "comentario sintetico"
    # Los derivados se calcularon con el texto en claro (descifrado en memoria).
    assert d.execute(select(T.token).where(T.comentario_id == 9)).all()


def test_sincronizacion_sin_claves_inserta_en_claro_y_cuenta(claves, tmp_path):
    claves.quitar()
    o, d = _origen_destino(tmp_path)
    res = sincronizacion.sincronizar(o, d)
    d.commit()
    assert res.sin_cifrar == 2
    com, pub = _crudo(d)
    assert com[9] == "comentario sintetico" and pub[3] == "caption sintetico"


def test_migrar_postgres_cifra_al_copiar(claves):
    mig = _cargar_script("migrar_percepcion_postgres")
    assert mig._columna_cifrable("percepcion_comentario", ["id", "texto"])[0] == "texto"
    assert mig._columna_cifrable("percepcion_publicacion", ["id", "caption"])[0] == "caption"
    assert mig._columna_cifrable("percepcion_score", ["id", "texto"]) is None


# ---------------------------------------------------------------- revisión: formato forjable
FALSO = "enc:1:" + "A" * 38        # comentario público que imita la forma de un cifrado


def test_el_formato_no_acepta_salto_de_linea_final(claves):
    assert cripto.es_cifrado(FALSO) and not cripto.es_cifrado(FALSO + "\n")
    assert cripto.descifrar(FALSO + "\n", "comentario:1") == FALSO + "\n"      # pasa como texto


def test_es_genuino_distingue_lo_forjado(claves):
    real = cripto.cifrar_texto(5, "algo")
    assert cripto.es_genuino(real, "comentario:5")
    assert not cripto.es_genuino(real, "comentario:6")          # otra fila
    assert not cripto.es_genuino(FALSO, "comentario:5")
    assert not cripto.es_genuino("texto normal", "comentario:5")


def test_texto_de_seguro_aisla_lo_ilegible_y_propaga_la_falta_de_clave(claves):
    fallos: list[int] = []
    assert cripto.texto_de_seguro(3, FALSO, fallos) == "" and fallos == [3]
    assert cripto.caption_de_seguro(4, FALSO, fallos) == "" and fallos == [3, 4]
    real = cripto.cifrar_texto(9, "hola")
    claves.quitar()
    with pytest.raises(cripto.ClaveNoConfigurada):
        cripto.texto_de_seguro(9, real, fallos)


def test_comentario_forjado_no_tumba_derivados_ni_subtemas_y_se_cuenta(claves):
    engine, db = _db()
    db.execute(text("UPDATE percepcion_comentario SET texto = :t WHERE id = 2"), {"t": FALSO})
    db.execute(text("UPDATE percepcion_publicacion SET caption = :t WHERE id = 1"), {"t": FALSO})
    db.commit()
    with engine.begin() as conn:
        r = cifrar_textos.transformar(conn)
    # Los forjados NO cuentan como ya cifrados: se cifran, así que todo queda auténtico.
    assert r["percepcion_comentario.texto"]["cambiadas"] == 24
    db.expire_all()
    com, pub = _crudo(db)
    assert all(cripto.es_genuino(v, f"comentario:{i}") for i, v in com.items())
    assert cripto.caption_de(1, pub[1]) == FALSO

    # Si igualmente llega un ilegible, el reconstruir sigue y lo informa.
    db.execute(text("UPDATE percepcion_comentario SET texto = :t WHERE id = 2"), {"t": FALSO})
    db.commit()
    assert derivados.reconstruir(db)["ilegibles"] == 1
    if importlib.util.find_spec("sklearn"):
        assert subtemas.reconstruir_subtemas(db, _embedder, modelo="f", ahora=datetime(2026, 2, 1),
                                             min_tamano=5)["ilegibles"] == 1
    # Curación sigue sirviendo la cola.
    assert curacion.comentarios_a_curar(db, limite=50)["items"]


def test_descifrar_informa_ilegibles_y_sigue(claves):
    engine, db = _db(6)
    db.execute(text("UPDATE percepcion_comentario SET texto = :t WHERE id = 2"), {"t": FALSO})
    db.commit()
    with engine.begin() as conn:
        cifrar_textos.transformar(conn)
    # Se corrompe una fila ya cifrada.
    db.execute(text("UPDATE percepcion_comentario SET texto = :t WHERE id = 3"), {"t": FALSO})
    db.commit()
    with engine.begin() as conn:
        r = cifrar_textos.transformar(conn, descifrar=True)
    assert r["percepcion_comentario.texto"]["ilegibles"] == 1
    assert r["ids_ilegibles"]["percepcion_comentario.texto"] == [3]
    assert r["percepcion_comentario.texto"]["cambiadas"] == 5
    assert _crudo(db)[0][2] == FALSO              # el que era forjado vuelve a su valor original


def test_sincronizacion_cifra_un_texto_forjado_de_origen(claves, tmp_path):
    o, d = _origen_destino(tmp_path)
    o.execute(text("UPDATE percepcion_comentario SET texto = :t"), {"t": FALSO})
    o.commit()
    sincronizacion.sincronizar(o, d)
    d.commit()
    assert cripto.texto_de(9, _crudo(d)[0][9]) == FALSO
    assert cripto.es_genuino(_crudo(d)[0][9], "comentario:9")


# ---------------------------------------------------------------- revisión: 503 sin clave
def test_api_sin_clave_responde_503_fijo(claves, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    @app.get("/_prueba_cripto")
    def _boom():
        raise cripto.ClaveNoConfigurada("PERCEPCION_CLAVE_TEXTO no está configurada.")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/_prueba_cripto")
    assert r.status_code == 503
    assert r.json() == {"detail": "Cifrado no configurado en el servidor"}


# ---------------------------------------------------------------- revisión: estado mixto
def test_sincronizar_se_niega_sin_clave_si_el_destino_ya_tiene_cifrados(claves, tmp_path):
    o, d = _origen_destino(tmp_path)
    d.add(Cu(id=1, handle="h", nombre="N", tipo="institucional", campus="Antofagasta",
             facultad="Ingeniería", origen="interno"))
    d.add(P(id=1, cuenta_id=1, external_id="p1", fecha_publicacion=datetime(2026, 3, 1), tipo="post",
            caption=cripto.cifrar_caption(1, "viejo"), n_comentarios=0, n_likes=0))
    d.commit()
    claves.quitar()
    with pytest.raises(cripto.ClaveNoConfigurada):
        sincronizacion.sincronizar(o, d)
    d.rollback()
    assert d.execute(select(C.id)).all() == []                 # no se insertó nada
    res = sincronizacion.sincronizar(o, d, permitir_claro=True, con_derivados=False)
    assert res.sin_cifrar == 2


# ---------------------------------------------------------------- revisión: seudónimo
def test_seudonimo_sin_ambiguedad_de_concatenacion(claves):
    assert cripto.seudonimo("b:c", "a") != cripto.seudonimo("c", "a:b")
    with pytest.raises(ValueError):
        cripto.seudonimo("x", "a\x00b")


def test_seudonimo_rechaza_clave_id_igual_a_clave_texto(claves):
    k = _clave()
    claves.poner(texto=k, id_=k)
    with pytest.raises(cripto.ClaveInvalida) as exc:
        cripto.seudonimo("x", "autor")
    assert cripto.VAR_CLAVE_ID in str(exc.value) and k not in str(exc.value)
