"""Derivados del texto: tokenizador compartido, reconstrucción y agregados sobre tokens.

Desde la Fase 3b la API normal NO lee `percepcion_comentario.texto` ni
`percepcion_publicacion.caption`: lee tablas derivadas que llena un proceso privilegiado
(`scripts/precalcular_tokens_percepcion.py`). Estos tests fijan tres cosas:

* el tokenizador es UNA sola función, usada por el precálculo y por lo que quede en
  `repository` (no pueden divergir);
* la reconstrucción es completa, idempotente y atómica;
* los agregados calculados sobre tokens dan lo mismo que calcularlos sobre el texto.
"""
from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.services.percepcion import derivados, lexico, repository
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionComentarioFamilia,
    PercepcionComentarioToken,
    PercepcionCuenta,
    PercepcionPublicacion,
    PercepcionPublicacionRasgo,
    PercepcionScore,
)

TEXTOS = [
    ("el arancel el arancel y otra vez arancel subió", "NEG", "anger", "matricula_aranceles"),
    ("Hay paro mañana? la asamblea decide https://x.cl @alguien", "NEG", "fear", "organizacion_estudiantil"),
    ("Seca! comments from Facebook marcha blanca", "POS", "joy", "otros"),
    ("jajaja toma de la universidad 😂 smacaya", "NEU", "humor_ironia", "otros"),
    ("arancel caro, la matrícula también", "NEG", "anger", "matricula_aranceles"),
    ("", "NEU", None, "otros"),
]


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _sembrar(db, textos=TEXTOS):
    db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="institucional",
                            campus="Antofagasta", facultad="Ingeniería"))
    db.add(PercepcionPublicacion(id=1, cuenta_id=1, external_id="p1", tipo="reel",
                                 fecha_publicacion=datetime(2026, 1, 3, 12),
                                 caption="¿Vienes? 😀😀😀 #a #b #c @ucn", n_likes=1))
    db.add(PercepcionPublicacion(id=2, cuenta_id=1, external_id="p2", tipo="post",
                                 fecha_publicacion=datetime(2026, 1, 4), caption=None))
    for i, (texto, sent, emo, tema) in enumerate(textos, start=1):
        db.add(PercepcionComentario(
            id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}", texto=texto,
            fecha_comentario=datetime(2026, 1, 2), idioma="es", n_likes=0, tema=tema))
        db.add(PercepcionScore(id=i, comentario_id=i, modelo="t", sentimiento=sent,
                               prob_pos=float(sent == "POS"), prob_neu=float(sent == "NEU"),
                               prob_neg=float(sent == "NEG"), emocion=emo, prob_emocion=.9))
    db.commit()


class TestTokenizadorCompartido(unittest.TestCase):
    def test_repository_usa_la_misma_funcion(self):
        # Si alguien reimplementa el tokenizador en `repository`, el precálculo y el
        # cálculo en vivo pueden divergir en silencio.
        self.assertIs(repository._tokenizar, derivados.tokenizar)

    def test_quita_pii_y_ruido(self):
        t = derivados.tokenizar("Hay paro https://x.cl @alguien smacaya tote.mny_ See translation")
        self.assertEqual(t, ["paro"])

    def test_excluir_equivale_a_filtrar_despues(self):
        # La API aplica `excluir` sobre los tokens guardados: debe dar lo mismo que
        # haberlo aplicado al tokenizar.
        for texto, *_ in TEXTOS:
            excl = {"arancel", "paro"}
            self.assertEqual(
                [p for p in derivados.tokenizar(texto) if p not in excl],
                derivados.tokenizar(texto, excl))

    def test_tokens_unicos_por_comentario(self):
        self.assertEqual(derivados.tokens_de("arancel arancel caro"), {"arancel", "caro"})

    def test_familias_son_las_del_lexico(self):
        for texto, *_ in TEXTOS:
            self.assertEqual(derivados.familias_de(texto), lexico.detectar(texto))

    def test_rasgos_de_caption(self):
        r = derivados.rasgos_caption("¿Vienes? 😀😀😀 #a #b #c @ucn")
        self.assertTrue(all(r[k] for k in ("emojis_3_o_mas", "menciona_cuentas",
                                           "hashtags_3_o_mas", "hace_una_pregunta")))
        self.assertFalse(r["texto_largo"])
        v = derivados.rasgos_caption(None)
        self.assertTrue(v["sin_texto"])
        self.assertFalse(any(v[k] for k in v if k != "sin_texto"))


class TestReconstruir(unittest.TestCase):
    def setUp(self):
        self.db = _db()
        _sembrar(self.db)

    def tearDown(self):
        self.db.close()

    def _filas(self, modelo):
        return {tuple(f) for f in self.db.execute(select(*modelo.__table__.c)).all()}

    def test_llena_tokens_familias_y_rasgos(self):
        r = derivados.reconstruir(self.db)
        esperado = {(i, p) for i, (t, *_) in enumerate(TEXTOS, 1) for p in derivados.tokens_de(t)}
        self.assertEqual(self._filas(PercepcionComentarioToken), esperado)
        fam = {(i, f) for i, (t, *_) in enumerate(TEXTOS, 1) for f in lexico.detectar(t)}
        self.assertEqual(self._filas(PercepcionComentarioFamilia), fam)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(PercepcionPublicacionRasgo)), 2)
        self.assertEqual(r["tokens"], len(esperado))
        self.assertEqual(r["familias"], len(fam))
        self.assertEqual(r["rasgos"], 2)
        self.assertEqual(r["comentarios"], len(TEXTOS))

    def test_idempotente(self):
        derivados.reconstruir(self.db)
        antes = (self._filas(PercepcionComentarioToken), self._filas(PercepcionComentarioFamilia),
                 self._filas(PercepcionPublicacionRasgo))
        derivados.reconstruir(self.db)
        despues = (self._filas(PercepcionComentarioToken), self._filas(PercepcionComentarioFamilia),
                   self._filas(PercepcionPublicacionRasgo))
        self.assertEqual(antes, despues)

    def test_reconstruye_borrando_lo_obsoleto(self):
        derivados.reconstruir(self.db)
        self.db.add(PercepcionComentarioToken(comentario_id=1, token="fantasma"))
        self.db.commit()
        derivados.reconstruir(self.db)
        self.assertNotIn((1, "fantasma"), self._filas(PercepcionComentarioToken))

    def test_atomica_si_falla_deja_lo_anterior(self):
        derivados.reconstruir(self.db)
        self.db.commit()
        antes = self._filas(PercepcionComentarioToken)
        with mock.patch.object(derivados, "tokens_de", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                derivados.reconstruir(self.db)
        self.db.rollback()
        self.assertEqual(self._filas(PercepcionComentarioToken), antes)


class TestAgregadosSobreTokens(unittest.TestCase):
    """Las vistas leen tokens; el resultado debe ser el que daría el texto."""

    def setUp(self):
        self.db = _db()
        _sembrar(self.db)
        derivados.reconstruir(self.db)

    def tearDown(self):
        self.db.close()

    def test_nube_igual_a_contar_sobre_el_texto(self):
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1, agrupar_variantes=False,
                                     limite=500)
        esperado: dict[str, int] = {}
        for texto, *_ in TEXTOS:
            for p in set(derivados.tokenizar(texto)):
                esperado[p] = esperado.get(p, 0) + 1
        self.assertEqual({p["texto"]: p["n"] for p in n["palabras"]}, esperado)
        self.assertEqual(n["n_comentarios"], len(TEXTOS))   # incluso el comentario sin tokens

    def test_nube_respeta_excluir(self):
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1, excluir=["Arancel"],
                                     agrupar_variantes=False)
        self.assertNotIn("arancel", [p["texto"] for p in n["palabras"]])

    def test_terminos_cuentan_comentarios_por_familia(self):
        r = repository.terminos_vigilancia(self.db, dias=3650)
        por = {f["clave"]: f["n_menciones"] for f in r["familias"]}
        esperado: dict[str, int] = {}
        for texto, *_ in TEXTOS:
            for k in lexico.detectar(texto):
                esperado[k] = esperado.get(k, 0) + 1
        self.assertEqual(por, esperado)
        self.assertEqual(r["global"]["n_comentarios"], len(TEXTOS))

    def test_no_se_lee_el_texto_crudo(self):
        # Con el texto vaciado después del precálculo, las vistas dan lo mismo.
        antes = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1)
        antes_t = repository.terminos_vigilancia(self.db, dias=3650)
        self.db.execute(PercepcionComentario.__table__.update().values(texto="x"))
        self.db.execute(PercepcionPublicacion.__table__.update().values(caption="x"))
        self.db.commit()
        self.assertEqual(repository.nube_palabras(self.db, dias=3650, min_frecuencia=1), antes)
        self.assertEqual(repository.terminos_vigilancia(self.db, dias=3650), antes_t)

    def test_destacados_y_impacto_no_usan_texto(self):
        antes = repository.destacados(self.db, dias=3650, min_global=1)["palabras"]
        self.assertTrue(antes)
        self.db.execute(PercepcionComentario.__table__.update().values(texto="x"))
        self.db.commit()
        self.assertEqual(repository.destacados(self.db, dias=3650, min_global=1)["palabras"], antes)


if __name__ == "__main__":
    unittest.main()
