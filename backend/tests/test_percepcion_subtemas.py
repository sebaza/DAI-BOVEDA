"""Subtemas locales (Fase 3c): agrupación por embeddings + etiqueta anonimizada.

Los tests NO necesitan torch: el embedder se inyecta (uno falso y determinista). Solo
`agrupar` usa scikit-learn (que llega con sentence-transformers); si falta, se saltan.
"""
from __future__ import annotations

import importlib.util
import zlib
from datetime import datetime

import numpy as np
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.services.percepcion import derivados, subtemas
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionComentarioSubtema,
    PercepcionCuenta,
    PercepcionPublicacion,
    PercepcionSubtema,
)

necesita_sklearn = pytest.mark.skipif(
    importlib.util.find_spec("sklearn") is None, reason="scikit-learn no está instalado")


# ------------------------------------------------------------------ limpiar
def test_limpiar_quita_scraper_urls_y_menciones():
    t = subtemas.limpiar("Seca la marcha https://x.cl @alguien tote.mny_ See translation View all 8 replies")
    assert "http" not in t and "@" not in t and "tote" not in t
    assert "marcha" in t.lower()
    assert "translation" not in t.lower()


def test_limpiar_vacio():
    assert subtemas.limpiar("") == ""
    assert subtemas.limpiar(None) == ""


# ------------------------------------------------------------------ agrupar
def _blobs(tamanos, dim=16, semilla=1):
    """Grupos bien separados: cada uno alrededor de un eje distinto."""
    rng = np.random.default_rng(semilla)
    filas = []
    for i, n in enumerate(tamanos):
        centro = np.zeros(dim)
        centro[i] = 1.0
        filas.append(centro + rng.normal(0, 0.03, size=(n, dim)))
    return np.vstack(filas)


@necesita_sklearn
def test_agrupar_encuentra_el_k_correcto():
    emb = _blobs([20, 20, 20])
    lab = subtemas.agrupar(emb)
    assert len(lab) == 60
    assert sorted(set(lab)) == [0, 1, 2]
    for ini in (0, 20, 40):            # cada grupo cae entero en un solo cluster
        assert len(set(lab[ini:ini + 20])) == 1


@necesita_sklearn
def test_agrupar_es_determinista():
    emb = _blobs([20, 20, 20])
    assert subtemas.agrupar(emb) == subtemas.agrupar(emb)


@necesita_sklearn
def test_agrupar_manda_los_clusters_chicos_a_otros():
    emb = _blobs([20, 20, 3])
    lab = subtemas.agrupar(emb, min_tamano=8)
    assert set(lab[40:]) == {subtemas.OTROS}
    assert subtemas.OTROS not in lab[:40]
    assert sorted(set(lab) - {subtemas.OTROS}) == [0, 1]


@necesita_sklearn
def test_agrupar_tema_grande_se_parte_al_menos_en_k_minimo():
    # Sin estructura fuerte la silueta prefiere k=2; un tema grande debe partirse más fino.
    emb = np.random.default_rng(3).normal(size=(1000, 16))
    lab = subtemas.agrupar(emb)
    assert subtemas.k_minimo(1000) == 5
    assert len(set(lab) - {subtemas.OTROS}) >= 5


def test_k_minimo_crece_con_el_tema_y_respeta_los_topes():
    assert subtemas.k_minimo(60) == 2
    assert subtemas.k_minimo(400) == 3
    assert subtemas.k_minimo(100_000) == 8                  # nunca pasa k_max
    assert subtemas.k_minimo(1000, min_tamano=300) == 3     # cada cluster debe caber


def test_agrupar_tema_chico_es_un_solo_cluster():
    emb = _blobs([7, 8])                # 15 < 2 * 8
    assert subtemas.agrupar(emb, min_tamano=8) == [0] * 15


def test_agrupar_vacio():
    assert subtemas.agrupar(np.zeros((0, 4))) == []


# ------------------------------------------------------------------ etiquetar
def _tema(n_por_grupo=12):
    """Dos grupos; cada uno con una palabra frecuente y de muchas personas distintas."""
    tokens, autores, asign = {}, {}, {}
    cid = 0
    for grupo, palabra in ((0, "gratuidad"), (1, "estacionamiento")):
        for _ in range(n_por_grupo):
            cid += 1
            tokens[cid] = {palabra}
            autores[cid] = f"a{cid}"
            asign[cid] = grupo
    return tokens, autores, asign


def test_etiquetar_usa_terminos_frecuentes_de_varias_personas():
    tokens, autores, asign = _tema()
    r = subtemas.etiquetar(tokens, autores, asign)
    assert r[0] == ("Gratuidad", ["gratuidad"])
    assert r[1][0] == "Estacionamiento"


def test_etiquetar_excluye_termino_en_menos_de_5_comentarios():
    tokens, autores, asign = _tema()
    for cid in range(1, 5):             # "rarisimo" en 4 comentarios de 4 autores
        tokens[cid].add("rarisimo")
    r = subtemas.etiquetar(tokens, autores, asign)
    assert "rarisimo" not in r[0][1]


def test_etiquetar_incluye_termino_en_5_comentarios_de_3_autores():
    tokens, autores, asign = _tema()
    for cid in range(1, 6):
        tokens[cid].add("justo")
        autores[cid] = f"x{cid % 3}"
    r = subtemas.etiquetar(tokens, autores, asign)
    assert "justo" in r[0][1]


def test_etiquetar_excluye_termino_de_menos_de_3_autores():
    tokens, autores, asign = _tema()
    for cid in range(1, 9):             # 8 comentarios pero de 2 autores
        tokens[cid].add("sospechoso")
        autores[cid] = f"x{cid % 2}"
    r = subtemas.etiquetar(tokens, autores, asign)
    assert all("sospechoso" not in terms for _, terms in r.values())


def test_etiquetar_excluye_palabras_cortas_y_stopwords():
    tokens, autores, asign = _tema()
    for cid in tokens:
        tokens[cid] |= {"uno", "para", "sea"}
    r = subtemas.etiquetar(tokens, autores, asign)
    assert all(not ({"uno", "para", "sea"} & set(t)) for _, t in r.values())


def test_etiquetar_excluye_lo_que_dice_la_mayoria_del_tema():
    # Un término presente en casi todo el tema no distingue subtemas (y es lo que
    # dejaría pasar contenido repetido tipo plantilla).
    tokens, autores, asign = _tema()
    for cid in tokens:
        tokens[cid].add("omnipresente")
    r = subtemas.etiquetar(tokens, autores, asign)
    assert all("omnipresente" not in t for _, t in r.values())


def test_etiquetar_sin_autor_no_cuenta_como_autor_distinto():
    tokens, autores, asign = _tema()
    for cid in range(1, 9):             # 8 comentarios: 2 autores reales + sin autor
        tokens[cid].add("anonimo")
        autores[cid] = None if cid % 3 == 0 else f"x{cid % 2}"
    r = subtemas.etiquetar(tokens, autores, asign)
    assert all("anonimo" not in t for _, t in r.values())


def test_etiquetar_descarta_terminos_largos_y_cabe_en_la_columna():
    tokens, autores, asign = _tema()
    largo = "a" * 60
    for cid in tokens:
        if asign[cid] == 0:
            tokens[cid].add(largo)
    r = subtemas.etiquetar(tokens, autores, asign)
    assert largo not in r[0][1]
    assert all(len(e) <= subtemas.LARGO_ETIQUETA for e, _ in r.values())


def test_etiquetar_cae_a_subtema_n_si_nada_califica():
    tokens = {i: {f"palabra{i}"} for i in range(1, 25)}
    autores = {i: f"a{i}" for i in tokens}
    asign = {i: (0 if i <= 12 else 1) for i in tokens}
    r = subtemas.etiquetar(tokens, autores, asign)
    assert r[0] == ("Subtema 1", []) and r[1] == ("Subtema 2", [])


def test_etiquetar_etiquetas_distintas_y_otros():
    tokens, autores, asign = _tema()
    n = len(tokens)
    for _ in range(12):                 # un tercer grupo que dice lo mismo que el 0
        n += 1
        tokens[n] = {"gratuidad"}
        autores[n] = f"b{n}"
        asign[n] = 2
    n += 1
    tokens[n], autores[n], asign[n] = {"suelto"}, f"b{n}", subtemas.OTROS
    r = subtemas.etiquetar(tokens, autores, asign)
    assert len({r[c][0] for c in (0, 1, 2)}) == 3
    assert r[subtemas.OTROS] == ("Otros", [])


# ------------------------------------------------------------------ reconstruir
def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


PALABRAS = {"a": "gratuidad", "b": "estacionamiento"}


def _sembrar(db, n=24, tema="academico"):
    db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="institucional",
                            campus="Antofagasta", facultad="Ingeniería"))
    db.add(PercepcionPublicacion(id=1, cuenta_id=1, external_id="p1", tipo="post",
                                 fecha_publicacion=datetime(2026, 1, 3), caption="x", n_likes=1))
    for i in range(1, n + 1):
        grupo = "a" if i <= n // 2 else "b"
        db.add(PercepcionComentario(
            id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}",
            texto=f"secretoxyz{i} {PALABRAS[grupo]} del campus", fecha_comentario=datetime(2026, 1, 2),
            idioma="es", n_likes=0, tema=tema))
    db.add(PercepcionComentario(id=n + 1, publicacion_id=1, external_id="sin", autor_hash="hz",
                                texto="comentario sin tema", fecha_comentario=datetime(2026, 1, 2),
                                idioma="es", n_likes=0, tema=None))
    db.commit()
    derivados.reconstruir(db)
    db.commit()


def embedder_falso(textos):
    """Determinista: el eje depende de la palabra clave, más un ruido fijo por texto."""
    filas = []
    for t in textos:
        v = np.zeros(8)
        v[0 if "gratuidad" in t else 1] = 1.0
        v += np.random.default_rng(zlib.crc32(t.encode())).normal(0, 0.02, 8)
        filas.append(v)
    return np.array(filas)


def _correr(db, **kw):
    r = subtemas.reconstruir_subtemas(db, embedder_falso, modelo="fake",
                                      ahora=datetime(2026, 2, 1), **kw)
    db.commit()
    return r


@necesita_sklearn
def test_reconstruir_escribe_ambas_tablas_sin_devolver_texto():
    db = _db()
    _sembrar(db)
    r = _correr(db, min_tamano=5)
    assert "secretoxyz" not in repr(r).lower()
    subs = db.execute(select(PercepcionSubtema).order_by(PercepcionSubtema.orden)).scalars().all()
    asig = db.execute(select(PercepcionComentarioSubtema)).scalars().all()
    assert len(subs) == 2 and len(asig) == 24                  # el comentario sin tema no entra
    assert {s.tema for s in subs} == {"academico"}
    assert sorted(s.etiqueta for s in subs) == ["Estacionamiento", "Gratuidad"]
    assert all(s.modelo == "fake" and s.n_comentarios == 12 for s in subs)
    assert r["asignados"] == 24 and r["subtemas"] == 2
    assert all("secreto" not in s.etiqueta.lower() for s in subs)


@necesita_sklearn
def test_reconstruir_es_idempotente():
    db = _db()
    _sembrar(db)

    def foto():
        return (db.execute(select(PercepcionSubtema.etiqueta, PercepcionSubtema.n_comentarios)
                           .order_by(PercepcionSubtema.orden)).all(),
                db.execute(select(PercepcionComentarioSubtema.comentario_id).order_by(
                    PercepcionComentarioSubtema.comentario_id)).all())

    _correr(db, min_tamano=5)
    a = foto()
    _correr(db, min_tamano=5)
    assert foto() == a
    assert db.query(PercepcionSubtema).count() == 2


def test_reconstruir_sin_escribir_no_toca_las_tablas():
    db = _db()
    _sembrar(db, n=6)
    r = _correr(db, escribir=False)
    assert r["asignados"] == 6
    assert db.query(PercepcionSubtema).count() == 0


def test_reconstruir_tema_chico_queda_en_un_subtema():
    db = _db()
    _sembrar(db, n=6)
    _correr(db)
    subs = db.execute(select(PercepcionSubtema)).scalars().all()
    assert len(subs) == 1 and subs[0].n_comentarios == 6 and subs[0].etiqueta.startswith("Subtema")


# ------------------------------------------------------------ nombres propios
def test_nombres_propios_detecta_palabras_con_mayuscula_a_mitad_de_frase():
    textos = ["felicitaciones al profe Juan Morales", "grande Juan Morales!",
              "gracias juan Morales por todo", "vamos Morales y Juan"]
    assert {"juan", "morales"} <= subtemas.nombres_propios(textos)


def test_nombres_propios_ignora_inicio_de_frase_y_mayusculas_sostenidas():
    textos = ["Gracias por todo. Gracias de nuevo", "Gracias totales", "MUY BIEN profe",
              "muy bien", "excelente. Excelente trabajo", "Excelente"]
    assert subtemas.nombres_propios(textos) == set()


def test_nombres_propios_exige_varias_apariciones():
    assert subtemas.nombres_propios(["saludos a Pedro", "hola Pedro"]) == set()


def test_etiquetar_excluye_los_terminos_vetados():
    tokens, autores, asign = _tema()
    r = subtemas.etiquetar(tokens, autores, asign, excluir={"gratuidad"})
    assert "gratuidad" not in r[0][1]
    assert r[0][0] == "Subtema 1"


def test_usuarios_mencionados_junta_las_menciones_del_corpus():
    # El handle completo, pegado sin signos (como lo deja el tokenizador) y sus partes largas.
    textos = ["gracias @Jo.Flores_sc por todo", "vamos @maria", "sin menciones", None]
    assert subtemas.usuarios_mencionados(textos) == {"jo.flores_sc", "jofloressc", "flores", "maria"}


def test_etiquetar_descarta_lo_que_no_parece_palabra():
    # El script le pasa un criterio basado en el tokenizador del modelo: un handle se parte
    # en muchos trozos y una palabra real en uno o dos.
    tokens, autores, asign = _tema()
    r = subtemas.etiquetar(tokens, autores, asign, es_palabra=lambda t: t != "estacionamiento")
    assert r[0][1] == ["gratuidad"]
    assert r[1][0] == "Subtema 2"


@necesita_sklearn
def test_reconstruir_aplica_vetos_y_criterio_de_palabra():
    db = _db()
    _sembrar(db)
    _correr(db, vetar={"gratuidad"}, es_palabra=lambda t: t != "estacionamiento")
    terminos = {t for (ts,) in db.execute(select(PercepcionSubtema.terminos)) for t in ts}
    assert not ({"gratuidad", "estacionamiento"} & terminos)
