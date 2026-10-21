"""ENSAYO DE COMUNICACIÓN — «¿esta publicación va a generar conversación?»

La pregunta B del plan de simulación, que es la ÚNICA de las cuatro que quedó viva.

POR QUÉ ESTA Y NO PREDECIR EL ÍNDICE
------------------------------------
La pregunta A —anticipar el índice semanal— se cerró con dos evidencias: el modelo
poblacional no supera la vara ni con la postura vieja ni con la mejorada, y la cota
in-sample deja 0,6 puntos de margen contra 0,58 de mínimo detectable. Tampoco hay
camino de datos: esperar son 5,7 años y ni sextuplicando el volumen se pasa de ~130
semanas evaluables.

Esta pregunta cambia la variable a predecir y con eso se vuelve contestable: hay
6.153 publicaciones, un tercio con conversación, y el efecto de cada rasgo está
medido CON CONTROL INTRA-CUENTA (comparando cada cuenta consigo misma).

MEDIR LA COMBINACIÓN ANTES QUE SUMARLA
--------------------------------------
Lo obvio sería sumar los efectos de los rasgos elegidos. Pero eso asume que no
interactúan, y no hay razón para creerlo: un reel con tres emojis puede no rendir la
suma de las dos cosas por separado.

Con 6.153 publicaciones no hace falta asumirlo. Si la combinación exacta tiene
muestra suficiente, se informa **la tasa observada** —que es un dato, no un modelo— y
solo se cae a la suma cuando la combinación es rara. La respuesta DECLARA de cuál de
las dos vías salió, porque no valen lo mismo.

LO QUE ESTE BLOQUE NO ES
------------------------
No predice el índice: predice si va a haber conversación, no de qué color. Y no es
causal — que los reels correlacionen con más conversación no prueba que convertir un
post en reel la produzca.
"""
from __future__ import annotations

import unittest

from app.services.percepcion import comunicacion


class TestEnsayoPuro(unittest.TestCase):
    """La estimación, aislada de la base."""

    # Un catálogo de efectos como el que devuelve `efecto_de_caracteristicas`.
    EFECTOS = [
        {"rasgo": "es_reel", "etiqueta": "Publicar como reel",
         "efecto_intra": 13.9, "margen": 3.5, "solido": True},
        {"rasgo": "emojis_3_o_mas", "etiqueta": "Usar 3 emojis o más",
         "efecto_intra": 4.9, "margen": 2.3, "solido": True},
        {"rasgo": "hace_una_pregunta", "etiqueta": "Hacer una pregunta",
         "efecto_intra": -2.7, "margen": 3.4, "solido": False},
    ]

    def test_sin_rasgos_devuelve_la_tasa_base(self):
        """Una publicación sin ninguna característica es la publicación promedio."""
        r = comunicacion.estimar_conversacion(32.4, self.EFECTOS, set(), observado=None)

        self.assertAlmostEqual(r["probabilidad"], 32.4, places=6)
        self.assertEqual(r["fuente"], "base")

    def test_un_rasgo_solido_suma_su_efecto_intra_cuenta(self):
        """El intra-cuenta y no el crudo: el crudo mide QUIÉN publica."""
        r = comunicacion.estimar_conversacion(32.4, self.EFECTOS, {"es_reel"}, observado=None)

        self.assertAlmostEqual(r["probabilidad"], 32.4 + 13.9, places=6)
        self.assertEqual(r["fuente"], "estimado")

    def test_un_rasgo_NO_solido_no_mueve_el_numero(self):
        """Y se declara, en vez de desaparecer.

        Un efecto que no superó su margen ni el test de signos no es un efecto
        chico: es uno que no se pudo distinguir del azar. Sumarlo sería inventar.
        """
        r = comunicacion.estimar_conversacion(
            32.4, self.EFECTOS, {"hace_una_pregunta"}, observado=None)

        self.assertAlmostEqual(r["probabilidad"], 32.4, places=6)
        self.assertIn("hace_una_pregunta", [a["rasgo"] for a in r["ignorados"]])

    def test_los_margenes_se_combinan_en_cuadratura_no_se_suman(self):
        """Sumar los márgenes exageraría la incertidumbre de una combinación."""
        r = comunicacion.estimar_conversacion(
            32.4, self.EFECTOS, {"es_reel", "emojis_3_o_mas"}, observado=None)

        self.assertAlmostEqual(r["probabilidad"], 32.4 + 13.9 + 4.9, places=6)
        # Redondeado a un decimal, como sale a pantalla: 4,2 y no 3,5+2,3 = 5,8.
        self.assertAlmostEqual(r["margen"], round((3.5**2 + 2.3**2) ** 0.5, 1), places=6)
        self.assertLess(r["margen"], 3.5 + 2.3, "sumarlos exageraría la incertidumbre")

    def test_la_probabilidad_nunca_se_sale_de_0_a_100(self):
        """Sumar efectos puede pasarse; una probabilidad de 112 % no significa nada."""
        enormes = [{"rasgo": f"r{i}", "etiqueta": f"r{i}", "efecto_intra": 40.0,
                    "margen": 1.0, "solido": True} for i in range(4)]

        alto = comunicacion.estimar_conversacion(50.0, enormes, {"r0", "r1", "r2"}, observado=None)
        bajo = comunicacion.estimar_conversacion(
            10.0, [{"rasgo": "x", "etiqueta": "x", "efecto_intra": -80.0,
                    "margen": 1.0, "solido": True}], {"x"}, observado=None)

        self.assertLessEqual(alto["probabilidad"], 100.0)
        self.assertGreaterEqual(bajo["probabilidad"], 0.0)

    def test_con_muestra_de_la_combinacion_usa_LO_OBSERVADO(self):
        """EL PUNTO DEL BLOQUE. Un dato le gana a un modelo aditivo.

        Si esa combinación exacta existe en el corpus con muestra suficiente, no hay
        por qué asumir que los rasgos no interactúan: se cuenta.
        """
        r = comunicacion.estimar_conversacion(
            32.4, self.EFECTOS, {"es_reel"}, observado={"n": 120, "conversan": 66})

        self.assertAlmostEqual(r["probabilidad"], 55.0, places=6)
        self.assertEqual(r["fuente"], "observado")
        self.assertEqual(r["n_observado"], 120)

    def test_una_muestra_flaca_no_se_usa_y_cae_a_la_estimacion(self):
        """Con pocas publicaciones la tasa observada oscila más que el efecto que mide."""
        r = comunicacion.estimar_conversacion(
            32.4, self.EFECTOS, {"es_reel"},
            observado={"n": comunicacion.MIN_COMBINACION - 1, "conversan": 1})

        self.assertEqual(r["fuente"], "estimado")

    def test_declara_los_rasgos_que_si_movieron_el_numero(self):
        """Un número sin su desglose no se puede discutir con quien comunica."""
        r = comunicacion.estimar_conversacion(
            32.4, self.EFECTOS, {"es_reel", "hace_una_pregunta"}, observado=None)

        aplicados = {a["rasgo"]: a["efecto"] for a in r["aplicados"]}
        self.assertEqual(aplicados, {"es_reel": 13.9})

    def test_avisa_cuando_se_apilan_demasiados_rasgos(self):
        """La suma de efectos se vuelve menos creíble cuanto más rasgos se apilan."""
        r = comunicacion.estimar_conversacion(
            32.4, self.EFECTOS, {"es_reel", "emojis_3_o_mas"}, observado=None)

        self.assertTrue(any("interact" in a.lower() or "suma" in a.lower()
                            for a in r["avisos"]),
                        f"sin aviso sobre la suma: {r['avisos']}")

    def test_un_rasgo_desconocido_no_rompe_nada(self):
        r = comunicacion.estimar_conversacion(32.4, self.EFECTOS, {"inventado"}, observado=None)

        self.assertAlmostEqual(r["probabilidad"], 32.4, places=6)


class TestEnsayoContraLaBase(unittest.TestCase):
    """La función de servicio completa, que además busca la combinación en el corpus."""

    def setUp(self):
        from datetime import datetime
        from app.services.percepcion.models import (
            PercepcionComentario, PercepcionCuenta, PercepcionPublicacion, PercepcionScore,
        )
        from tests.test_percepcion import _commit_y_derivar, _memoria
        self.db = _memoria()
        # SEIS cuentas. El rasgo se declara sólido solo si el test de SIGNOS
        # intra-cuenta descarta el azar, y ese test es de DOS COLAS: con cinco
        # cuentas todas a favor da p = 2·0,5⁵ = 0,0625, que no pasa el 0,05. Con
        # seis, 0,031. Un fixture que no puede producir un sólido no prueba nada.
        for cid in range(1, 7):
            self.db.add(PercepcionCuenta(id=cid, handle=f"c{cid}", nombre=f"C{cid}",
                                         tipo="institucional"))
        # Por cuenta: 20 reels que conversan y 20 posts que no.
        n = 0
        for cuenta in range(1, 7):
            for reel in (True, False):
                for i in range(20):
                    n += 1
                    self.db.add(PercepcionPublicacion(
                        id=n, cuenta_id=cuenta, external_id=f"p{n}",
                        tipo="reel" if reel else "post",
                        # Caption NEUTRO a propósito: sin emojis, sin @, sin #, sin
                        # signo de pregunta, y largo suficiente para que no dispare
                        # `sin_texto`. Con "hola" el rasgo activo era {es_reel,
                        # sin_texto} y la combinación pedida en el test nunca
                        # coincidía, así que el ensayo caía a la vía estimada.
                        caption="Comunicado de la unidad sobre las actividades del mes",
                        fecha_publicacion=datetime(2026, 3, 3), n_likes=0))
                    if reel:
                        self.db.add(PercepcionComentario(
                            id=n, publicacion_id=n, external_id=f"c{n}", autor_hash=f"h{n}",
                            texto="me gusta", fecha_comentario=datetime(2026, 3, 4), n_likes=0))
                        self.db.add(PercepcionScore(
                            id=n, comentario_id=n, modelo="t", sentimiento="POS",
                            prob_pos=1.0, prob_neu=0.0, prob_neg=0.0))
        _commit_y_derivar(self.db)

    def tearDown(self):
        self.db.close()

    def test_un_reel_da_mas_que_un_post_en_este_corpus(self):
        """Verificación de punta a punta: la señal sembrada tiene que aparecer."""
        con = comunicacion.ensayar(self.db, {"es_reel"})
        sin = comunicacion.ensayar(self.db, set())

        self.assertGreater(con["probabilidad"], sin["probabilidad"])

    def test_devuelve_el_catalogo_de_rasgos_para_poder_elegir(self):
        """La UI necesita saber qué se puede activar y cuáles son sólidos."""
        r = comunicacion.ensayar(self.db, set())

        self.assertTrue(r["rasgos"])
        for it in r["rasgos"]:
            self.assertIn("rasgo", it)
            self.assertIn("etiqueta", it)
            self.assertIn("solido", it)

    def test_sin_publicaciones_no_inventa_una_probabilidad(self):
        from tests.test_percepcion import _commit_y_derivar, _memoria
        vacia = _memoria()
        try:
            self.assertIsNone(comunicacion.ensayar(vacia, {"es_reel"})["probabilidad"])
        finally:
            vacia.close()
