"""Carga de Percepción al almacén (`scripts/publicar_warehouse_percepcion.py`), fase A3.

Origen y destino son SQLite en archivos temporales (la lógica es la misma; lo específico de
Postgres -esquema, TRUNCATE, secuencias- queda cubierto por `TestContraPostgres`, opt-in con
PERCEPCION_TEST_DATABASE_URL). Las claves se generan en cada test con `os.urandom`; los textos
son sintéticos y ningún assert imprime texto.
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
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base
from app.services.percepcion import cripto, derivados, subtemas
from app.services.percepcion.models import (
    META_AUTOR_SEUDONIMIZADO,
    META_EXT_COMENTARIO_SEUDONIMIZADO,
    PercepcionComentario as C,
    PercepcionComentarioEtiqueta as E,
    PercepcionComentarioFamilia as F,
    PercepcionComentarioSubtema as CS,
    PercepcionComentarioToken as T,
    PercepcionCorreccion as Corr,
    PercepcionCuenta as Cu,
    PercepcionEvento as Ev,
    PercepcionMeta,
    PercepcionPublicacion as P,
    PercepcionPublicacionRasgo as R,
    PercepcionResumenSemanal as Res,
    PercepcionScore as S,
    PercepcionSubtema as Sub,
    PercepcionTemaCustom as Tc,
)
from pg_percepcion import URL, esquema_efimero, requiere_pg

RUTA = Path(__file__).resolve().parents[2] / "scripts" / "publicar_warehouse_percepcion.py"
_spec = importlib.util.spec_from_file_location("publicar_warehouse_percepcion", RUTA)
pub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pub)

necesita_sklearn = pytest.mark.skipif(
    importlib.util.find_spec("sklearn") is None, reason="scikit-learn no está instalado")

F0 = datetime(2026, 1, 2, 10)
TEXTOS = [
    "el arancel sube cada año en la universidad",
    "la beca de alimentación no alcanzó este semestre",
    "estacionamiento lleno otra vez en el campus",
    "la gratuidad cubre pocos estudiantes de la región",
]


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


def _motor(ruta: Path):
    return create_engine(f"sqlite:///{ruta.as_posix()}", future=True)


def _llenar(eng, n: int = 24) -> None:
    """Origen con la forma de la Bóveda actual: texto/caption CIFRADOS, autor_hash del worker."""
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng, future=True)()
    db.add(Cu(id=1, handle="ucn", nombre="UCN", tipo="institucional", campus="Antofagasta",
              facultad="Ingeniería", origen="interno"))
    db.add(P(id=1, cuenta_id=1, external_id="p1", tipo="post", fecha_publicacion=F0, n_likes=1,
             caption=cripto.cifrar_caption(1, "Gran #marcha en el campus 😀 ¿vienes?")))
    db.add(P(id=2, cuenta_id=1, external_id="p2", tipo="reel", fecha_publicacion=F0, n_likes=1,
             caption=None))
    for i in range(1, n + 1):
        grupo_a = i <= n // 2
        # Grupo A: 6 autores distintos. Grupo B: solo 2 (los términos de B no deben calificar).
        autor = f"hash-worker-{i % 6}" if grupo_a else f"hash-worker-b{i % 2}"
        t = TEXTOS[i % len(TEXTOS)] + (" gratuidad" if grupo_a else " estacionamiento") + f" {i}"
        db.add(C(id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=autor,
                 texto=cripto.cifrar_texto(i, t), fecha_comentario=F0, idioma="es", n_likes=1,
                 tema="otros" if i % 3 == 0 else "academico", tema_confianza=0.9))
        db.add(S(id=i, comentario_id=i, modelo="t", sentimiento="NEG", prob_pos=0.0, prob_neu=0.1,
                 prob_neg=0.9, emocion="anger", prob_emocion=0.9))
    db.add(Corr(comentario_id=1, campo="tema", valor_original="otros", valor_nuevo="academico",
                justificacion="revisión manual", autor="ana@ucn.cl", creado_en=F0, confirmado=False))
    db.add(Tc(clave="beca", etiqueta="Becas", keywords=["beca"], creado_en=F0))
    db.add(Ev(nombre="Paro", tipo="paro", fecha_inicio=F0.date()))
    db.add(Res(semana_inicio=F0.date(), nivel="global", dimension="", huella="h", texto="resumen",
               generado_en=F0))
    db.commit()
    derivados.reconstruir(db)
    db.commit()
    db.close()


def _embedder(textos):
    filas = []
    for t in textos:
        v = np.zeros(8)
        v[0 if "gratuidad" in t else 1] = 1.0
        v += np.random.default_rng(zlib.crc32(t.encode())).normal(0, 0.02, 8)
        filas.append(v)
    return np.array(filas)


@pytest.fixture()
def bases(tmp_path, claves):
    origen, destino = _motor(tmp_path / "origen.db"), _motor(tmp_path / "destino.db")
    _llenar(origen)
    yield origen, destino
    origen.dispose()
    destino.dispose()


def _publicar(origen, destino, **kw):
    return pub.publicar(origen, destino, salida=lambda *_: None, **kw)


def _filas(eng, sql: str):
    with eng.connect() as con:
        return con.execute(text(sql)).all()


def _tablas_percepcion() -> set[str]:
    return {t.name for t in Base.metadata.sorted_tables if t.name.startswith("percepcion_")}


# ------------------------------------------------------------------- copia completa
def test_copia_todas_las_tablas_con_los_mismos_conteos(bases):
    origen, destino = bases
    copiadas = _publicar(origen, destino)
    esperadas = _tablas_percepcion() - {"percepcion_meta"}
    assert set(copiadas) == esperadas
    # La lista de tablas incluye curación y estado, no solo las del worker.
    assert {"percepcion_correccion", "percepcion_tema_custom", "percepcion_evento",
            "percepcion_resumen_semanal", "percepcion_subtema", "percepcion_comentario_subtema",
            "percepcion_comentario_token", "percepcion_comentario_familia",
            "percepcion_comentario_etiqueta", "percepcion_publicacion_rasgo"} <= esperadas
    for tabla in esperadas:
        n_o = _filas(origen, f"SELECT COUNT(*) FROM {tabla}")[0][0]
        n_d = _filas(destino, f"SELECT COUNT(*) FROM {tabla}")[0][0]
        assert n_o == n_d == copiadas[tabla], tabla
    assert copiadas["percepcion_comentario"] == 24 and copiadas["percepcion_correccion"] == 1


def test_escribe_la_marca_de_seudonimizacion(bases):
    origen, destino = bases
    _publicar(origen, destino)
    marcas = _filas(destino, "SELECT clave, valor FROM percepcion_meta")
    assert sorted(marcas) == sorted([(META_AUTOR_SEUDONIMIZADO, "true"),
                                     (META_EXT_COMENTARIO_SEUDONIMIZADO, "true")])


# ------------------------------------------------------------------- autor_hash
def test_autor_hash_se_seudonimiza_de_forma_determinista(bases):
    origen, destino = bases
    _publicar(origen, destino)
    o = dict(_filas(origen, "SELECT id, autor_hash FROM percepcion_comentario"))
    d = dict(_filas(destino, "SELECT id, autor_hash FROM percepcion_comentario"))
    assert set(o) == set(d)
    for id_, original in o.items():
        assert d[id_] == cripto.seudonimo(original, "autor")
        assert d[id_] != original and len(d[id_]) == 64
    # Misma persona -> mismo seudónimo; el conteo de autores distintos no cambia.
    assert len(set(o.values())) == len(set(d.values())) == 8
    # Segunda carga (otro destino) con las mismas claves: idéntico.
    otro = _motor(Path(destino.url.database).with_name("otro.db"))
    _publicar(origen, otro)
    assert dict(_filas(otro, "SELECT id, autor_hash FROM percepcion_comentario")) == d
    otro.dispose()


def test_external_id_de_comentarios_se_seudonimiza_de_forma_determinista(bases):
    origen, destino = bases
    _publicar(origen, destino)
    o = dict(_filas(origen, "SELECT id, external_id FROM percepcion_comentario"))
    d = dict(_filas(destino, "SELECT id, external_id FROM percepcion_comentario"))
    assert set(o) == set(d)
    for id_, original in o.items():
        assert d[id_] == cripto.seudonimo(original, "comentario_ext")
        assert d[id_] != original and len(d[id_]) == 64 <= 80
    assert len(set(d.values())) == len(o)
    # El dominio separa usos: no coincide con el seudónimo de autor del mismo valor.
    assert cripto.seudonimo("c1", "comentario_ext") != cripto.seudonimo("c1", "autor")


def test_publicacion_y_cuenta_no_se_tocan(bases):
    origen, destino = bases
    _publicar(origen, destino)
    for sql in ("SELECT id, external_id FROM percepcion_publicacion ORDER BY id",
                "SELECT id, handle FROM percepcion_cuenta ORDER BY id"):
        assert _filas(origen, sql) == _filas(destino, sql)


# ------------------------------------------------------------------- texto cifrado
def test_texto_y_caption_se_copian_identicos_y_siguen_descifrando(bases):
    origen, destino = bases
    _publicar(origen, destino)
    for tabla, col, ctx in (("percepcion_comentario", "texto", cripto.contexto_comentario),
                            ("percepcion_publicacion", "caption", cripto.contexto_publicacion)):
        o = dict(_filas(origen, f"SELECT id, {col} FROM {tabla}"))
        d = dict(_filas(destino, f"SELECT id, {col} FROM {tabla}"))
        assert o == d
        for id_, v in d.items():
            if v is not None:
                assert v.startswith("enc:1:")
                assert cripto.descifrar(v, ctx(id_)) is not None
    assert cripto.descifrar(dict(_filas(destino, "SELECT id, texto FROM percepcion_comentario"))[1],
                            cripto.contexto_comentario(1)).startswith("la beca")


def _meter_claro(origen):
    with origen.begin() as con:
        con.execute(text("UPDATE percepcion_comentario SET texto = 'texto sin cifrar centinela' "
                         "WHERE id = 5"))
        # Imita la forma `enc:` sin ser un cifrado real (forjado).
        con.execute(text("UPDATE percepcion_comentario SET texto = :f WHERE id = 6"),
                    {"f": "enc:1:" + "A" * 60})


def test_texto_en_claro_aborta_sin_escribir_y_sin_filtrarlo(bases):
    origen, destino = bases
    _meter_claro(origen)
    with pytest.raises(pub.PublicacionError) as exc:
        _publicar(origen, destino)
    assert "percepcion_comentario.texto=2" in str(exc.value)
    assert "centinela" not in str(exc.value)
    assert inspect(destino).get_table_names() == []   # ni siquiera se crearon las tablas


def test_permitir_claro_deja_pasar_el_texto(bases):
    origen, destino = bases
    _meter_claro(origen)
    _publicar(origen, destino, permitir_claro=True)
    d = dict(_filas(destino, "SELECT id, texto FROM percepcion_comentario"))
    assert d[5] == "texto sin cifrar centinela"
    assert d == dict(_filas(origen, "SELECT id, texto FROM percepcion_comentario"))


def test_sin_claves_se_niega(bases, monkeypatch, claves):
    origen, destino = bases
    monkeypatch.setattr(claves, "percepcion_clave_id", "")
    with pytest.raises(pub.ConfiguracionError, match="PERCEPCION_CLAVE_ID"):
        _publicar(origen, destino)
    monkeypatch.setattr(claves, "percepcion_clave_id", _clave())
    monkeypatch.setattr(claves, "percepcion_clave_texto", "")
    with pytest.raises(pub.ConfiguracionError, match="PERCEPCION_CLAVE_TEXTO"):
        _publicar(origen, destino)
    assert inspect(destino).get_table_names() == []


@pytest.mark.parametrize("clave", [META_AUTOR_SEUDONIMIZADO, META_EXT_COMENTARIO_SEUDONIMIZADO])
def test_origen_ya_marcado_se_niega(bases, clave):
    origen, destino = bases
    with origen.begin() as con:
        con.execute(PercepcionMeta.__table__.insert().values(clave=clave, valor="true"))
    with pytest.raises(pub.PublicacionError, match="ya está marcado"):
        _publicar(origen, destino)


def test_sin_destino_solo_se_permite_en_dry_run(bases):
    origen, _ = bases
    with pytest.raises(pub.PublicacionError, match="Falta el destino"):
        _publicar(origen, None)


def test_validacion_detecta_un_cifrado_roto_y_revierte(bases, monkeypatch):
    origen, destino = bases
    real = pub._copiar_tabla

    def rota(src, dst, tabla, columnas, lote, cache):
        n = real(src, dst, tabla, columnas, lote, cache)
        if tabla.name == "percepcion_comentario":   # intercambia dos textos: mismo formato, AAD ajeno
            dst.execute(text("UPDATE percepcion_comentario SET texto = CASE id "
                             "WHEN 1 THEN (SELECT texto FROM percepcion_comentario WHERE id = 2) "
                             "WHEN 2 THEN (SELECT texto FROM percepcion_comentario WHERE id = 1) "
                             "ELSE texto END"))
        return n
    monkeypatch.setattr(pub, "_copiar_tabla", rota)
    with pytest.raises(pub.PublicacionError, match="verificación de cifrado"):
        _publicar(origen, destino)
    assert _filas(destino, "SELECT COUNT(*) FROM percepcion_comentario") == [(0,)]


def test_validacion_detecta_ids_distintos_aunque_el_conteo_coincida(bases, monkeypatch):
    origen, destino = bases
    real = pub._copiar_tabla

    def rota(src, dst, tabla, columnas, lote, cache):
        n = real(src, dst, tabla, columnas, lote, cache)
        if tabla.name == "percepcion_cuenta":
            dst.execute(text("UPDATE percepcion_cuenta SET id = id + 100"))
        return n
    monkeypatch.setattr(pub, "_copiar_tabla", rota)
    with pytest.raises(pub.PublicacionError, match="ids de percepcion_cuenta"):
        _publicar(origen, destino)
    assert _filas(destino, "SELECT COUNT(*) FROM percepcion_cuenta") == [(0,)]


def test_origen_se_lee_en_una_sola_instantanea():
    fuente = RUTA.read_text(encoding="utf-8")
    assert "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY" in fuente


# ------------------------------------------------------------------- origen distinto de destino
@pytest.mark.parametrize("a,b,iguales", [
    ("postgresql://u:p@LOCALHOST/db", "postgresql+psycopg://x:y@127.0.0.1:5432/db", True),
    ("postgresql://u@[::1]/db", "postgresql://u@localhost:5432/db", True),
    ("postgresql://u@/db", "postgresql://u@localhost/db", True),
    ("postgresql://u@a/db?host=Srv.Example", "postgresql://u@srv.example/db", True),
    ("postgresql://u@SRV.example:5432/db", "postgresql://u@srv.example/db", True),
    ("postgresql://u@srv/db", "postgresql://u@srv:5433/db", False),
    ("postgresql://u@srv/db", "postgresql://u@srv/otra", False),
    ("postgresql://u@srv/db", "postgresql://u@otro/db", False),
])
def test_misma_base_normaliza_host_puerto_y_loopback(a, b, iguales):
    assert pub._misma_base(a, b, "percepcion", "percepcion") is iguales


def test_misma_base_con_esquemas_distintos_no_es_la_misma():
    assert not pub._misma_base("postgresql://u@h/db", "postgresql://u@h/db", "a", "b")


def _ident(addr="1.1.1.1", puerto=5432, sysid=None, base="x"):
    return {"base": base, "addr": addr, "puerto": puerto, "sysid": sysid}


@pytest.mark.parametrize("o,d,esperado", [
    (_ident(sysid=7), _ident(addr="2.2.2.2", puerto=1, sysid=7), True),
    (_ident(sysid=7), _ident(sysid=8), False),
    (_ident(), _ident(), True),
    (_ident(), _ident(puerto=5433), False),
    (_ident(addr=None, puerto=None), _ident(addr=None, puerto=None), False),
    (_ident(sysid=7), _ident(sysid=7, base="y"), False),
])
def test_misma_instancia_compara_lo_que_dice_el_servidor(monkeypatch, o, d, esperado):
    respuestas = iter([o, d])
    monkeypatch.setattr(pub, "_identidad", lambda eng: next(respuestas))
    assert pub._misma_instancia(object(), object()) is esperado


def test_publicar_se_niega_si_el_servidor_dice_que_es_la_misma_base(claves, monkeypatch):
    monkeypatch.setattr(pub, "_misma_instancia", lambda a, b: True)
    eng_o = create_engine("postgresql+psycopg://u:p@alias-uno/db", future=True)
    eng_d = create_engine("postgresql+psycopg://u:p@alias-dos/db", future=True)
    try:
        with pytest.raises(pub.PublicacionError, match="misma base"):
            pub.publicar(eng_o, eng_d, esquema="percepcion", esquema_origen="percepcion",
                         salida=lambda *_: None)
    finally:
        eng_o.dispose()
        eng_d.dispose()


# ------------------------------------------------------------------- destino con datos / dry-run
def test_se_niega_si_el_destino_tiene_datos_salvo_reemplazar(bases):
    origen, destino = bases
    _publicar(origen, destino)
    with destino.begin() as con:   # trabajo hecho en el almacén que NO debe perderse
        con.execute(text("UPDATE percepcion_cuenta SET nombre = 'EDITADO' WHERE id = 1"))
    with pytest.raises(pub.PublicacionError, match="--reemplazar"):
        _publicar(origen, destino)
    assert _filas(destino, "SELECT nombre FROM percepcion_cuenta WHERE id = 1") == [("EDITADO",)]

    _publicar(origen, destino, reemplazar=True)
    assert _filas(destino, "SELECT nombre FROM percepcion_cuenta WHERE id = 1") == [("UCN",)]
    assert _filas(destino, "SELECT COUNT(*) FROM percepcion_comentario") == [(24,)]
    assert _filas(destino, "SELECT COUNT(*) FROM percepcion_meta") == [(2,)]


def test_dry_run_no_escribe_nada(bases):
    origen, destino = bases
    copiadas = _publicar(origen, destino, dry_run=True)
    assert copiadas["percepcion_comentario"] == 24
    assert inspect(destino).get_table_names() == []
    # También sin destino (solo se revisa el origen).
    assert _publicar(origen, None, dry_run=True)["percepcion_comentario"] == 24


def test_dry_run_detecta_texto_en_claro(bases):
    origen, destino = bases
    _meter_claro(origen)
    with pytest.raises(pub.PublicacionError):
        _publicar(origen, destino, dry_run=True)


def test_dry_run_no_modifica_un_destino_con_datos(bases):
    origen, destino = bases
    _publicar(origen, destino)
    lineas: list[str] = []
    pub.publicar(origen, destino, dry_run=True, salida=lineas.append)
    assert any("destino con datos en" in l and "--reemplazar" in l for l in lineas)
    assert _filas(destino, "SELECT COUNT(*) FROM percepcion_comentario") == [(24,)]


def test_informa_columnas_a_revisar_sin_valores(bases):
    origen, destino = bases
    lineas: list[str] = []
    pub.publicar(origen, destino, salida=lineas.append)
    salida = "\n".join(lineas)
    assert "percepcion_correccion.autor: 1 filas" in salida
    assert "percepcion_comentario_token.token" in salida
    assert "ana@ucn.cl" not in salida and "revisión manual" not in salida


# ------------------------------------------------------------------- CLI
def test_main_sin_urls_o_sin_postgres_sale_con_2(monkeypatch, capsys):
    monkeypatch.delenv(pub.VAR_ORIGEN, raising=False)
    monkeypatch.delenv(pub.VAR_DESTINO, raising=False)
    assert pub.main([]) == 2
    assert pub.VAR_ORIGEN in capsys.readouterr().err
    assert pub.main(["--origen", "postgresql://u:p@h/db"]) == 2
    assert pub.VAR_DESTINO in capsys.readouterr().err
    assert pub.main(["--origen", "sqlite:///x.db", "--destino", "postgresql://u:p@h/db"]) == 2
    assert "PostgreSQL" in capsys.readouterr().err


def test_main_rechaza_origen_igual_a_destino(capsys):
    url = "postgresql+psycopg://u:clave-secreta@h:5432/db"
    assert pub.main(["--origen", url, "--destino", url]) == 2
    err = capsys.readouterr().err
    assert "misma base" in err and "clave-secreta" not in err


def test_main_error_inesperado_muestra_solo_la_clase(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("postgresql://u:clave-secreta@h/db")
    monkeypatch.setattr(pub, "publicar_urls", boom)
    assert pub.main(["--origen", "postgresql://a/x", "--destino", "postgresql://b/y"]) == 1
    err = capsys.readouterr().err
    assert "RuntimeError" in err and "clave-secreta" not in err


# ------------------------------------------------------------------- derivados y subtemas
def _derivados(db):
    return {
        "tokens": sorted(db.execute(select(T.comentario_id, T.token)).all()),
        "familias": sorted(db.execute(select(F.comentario_id, F.familia)).all()),
        "etiquetas": sorted(db.execute(select(E.comentario_id, E.n_etiquetas, E.solo_etiquetas)).all()),
        "rasgos": sorted(tuple(r) for r in db.execute(select(*R.__table__.c)).all()),
    }


def _subtemas(db):
    subtemas.reconstruir_subtemas(db, _embedder, modelo="fake", ahora=datetime(2026, 2, 1), min_tamano=5)
    db.commit()
    etiqueta = {i: (t, e, tuple(tt), n) for i, t, e, tt, n in
                db.execute(select(Sub.id, Sub.tema, Sub.etiqueta, Sub.terminos, Sub.n_comentarios)).all()}
    return sorted((cid, etiqueta[sid]) for cid, sid in db.execute(
        select(CS.comentario_id, CS.subtema_id)).all())


def test_derivados_reconstruidos_en_el_destino_son_los_del_origen(bases):
    origen, destino = bases
    _publicar(origen, destino)
    so, sd = sessionmaker(bind=origen, future=True)(), sessionmaker(bind=destino, future=True)()
    try:
        del_origen = _derivados(so)
        assert del_origen == _derivados(sd)          # lo copiado
        derivados.reconstruir(sd)                    # lo recalculado en el almacén
        sd.commit()
        assert _derivados(sd) == del_origen
    finally:
        so.close()
        sd.close()


@necesita_sklearn
def test_subtemas_en_el_destino_son_los_del_origen_con_autores_seudonimizados(bases):
    origen, destino = bases
    _publicar(origen, destino)
    so, sd = sessionmaker(bind=origen, future=True)(), sessionmaker(bind=destino, future=True)()
    try:
        # Los umbrales anti-PII (>= 3 autores distintos por término) dependen de autor_hash.
        esperado = _subtemas(so)
        assert esperado
        assert _subtemas(sd) == esperado
        assert sd.scalar(select(func.count(func.distinct(C.autor_hash)))) == 8
    finally:
        so.close()
        sd.close()


# ------------------------------------------------------------------- Postgres (opt-in)
@requiere_pg
class TestContraPostgres:
    def test_carga_entre_esquemas_con_secuencias_y_marca(self, claves, tmp_path):
        # El origen es un esquema descartable con los datos; el destino, otro vacío.
        with esquema_efimero("percepcion_test_wh_o") as url_o, \
                esquema_efimero("percepcion_test_wh_d", crear_tablas=False) as url_d:
            eng_o = create_engine(url_o, future=True)
            _llenar(eng_o)
            eng_d = create_engine(url_d, future=True)
            try:
                copiadas = pub.publicar(eng_o, eng_d, esquema="percepcion_test_wh_d",
                                        salida=lambda *_: None)
                assert copiadas["percepcion_comentario"] == 24
                with eng_d.begin() as con:
                    assert con.execute(text("SELECT valor FROM percepcion_meta")).scalar_one() == "true"
                    nuevo = con.execute(text(
                        "INSERT INTO percepcion_cuenta (handle, nombre, tipo) "
                        "VALUES ('n','n','n') RETURNING id")).scalar_one()
                    assert nuevo == 2          # la secuencia quedó en max(id)+1
                with pytest.raises(pub.PublicacionError, match="--reemplazar"):
                    pub.publicar(eng_o, eng_d, esquema="percepcion_test_wh_d", salida=lambda *_: None)
                pub.publicar(eng_o, eng_d, esquema="percepcion_test_wh_d", reemplazar=True,
                             salida=lambda *_: None)
            finally:
                eng_o.dispose()
                eng_d.dispose()


