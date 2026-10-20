"""Cola ESTRATIFICADA: conseguir adversos sin perder la validez de la estimación.

EL PROBLEMA QUE RESUELVE
------------------------
El lado adverso de la regla de postura tiene 21 ejemplos humanos sin sesgo, y con 21
no se calibra nada — es la razón por la que ninguna variante probada movió el recall.
Para llegar a 50 hay dos caminos y los dos tienen un defecto:

* `MUESTRA_ALEATORIA` da una estimación válida de la calidad global, pero el adverso
  es el 12,8 % de lo anotado: hacen falta **227 anotaciones** más.
* `MUESTRA_ADVERSOS` concentra el trabajo donde rinde (35 % de adversos, 83
  anotaciones), pero al estar dirigida **no sirve para estimar nada**: el acuerdo
  medido ahí es un piso, no el valor real.

La cola estratificada es la salida clásica a ese dilema. Parte el corpus en dos
estratos por el puntaje de candidato adverso, anota DESPROPORCIONADAMENTE en el
estrato rico, y RE-PESA cada estrato por su tamaño real al calcular cualquier
métrica. La estimación sigue siendo insesgada y los adversos llegan mucho antes:

    estrato   N corpus   % corpus   tasa de adversos
    rico           711       8,7 %        35 %
    pobre        7.463      91,3 %        10 %

    al azar                         227 anotaciones
    70 % rico / 30 % pobre          105 anotaciones  <- esta cola
    todo dirigido                    83 anotaciones  (no evaluable)

**La validación de que el método está bien calibrado ya se hizo contra los datos
reales**: re-pesando los 164 casos aleatorios ya anotados por su estrato se obtiene
12,4 % de adversos, contra el 12,8 % observado directamente. Si el re-pesado
estuviera mal, esos dos números no coincidirían.

⚠️ LO QUE HAY QUE NO OLVIDAR: una métrica calculada sobre esta cola SIN re-pesar está
sesgada hacia arriba en adversos, porque el estrato rico está sobrerrepresentado a
propósito. Por eso `repesar_por_estrato` no es opcional, y por eso `origen_muestra`
sigue guardándose en cada corrección.
"""
from __future__ import annotations

import unittest

from app.services.percepcion import curacion
from app.services.percepcion.models import MUESTRA_ESTRATIFICADA


class TestEstrato(unittest.TestCase):
    """A qué estrato cae cada comentario."""

    def test_un_positivo_con_lexico_de_conflicto_es_estrato_rico(self):
        """POS/NEU hablando de un paro es justo el caso que la regla no puede ver."""
        e = curacion._estrato_de("POS", "vamos compañeros con el paro", "", None)

        self.assertEqual(e, curacion.ESTRATO_RICO)

    def test_un_positivo_comun_es_estrato_pobre(self):
        e = curacion._estrato_de("POS", "qué linda la foto", "", None)

        self.assertEqual(e, curacion.ESTRATO_POBRE)

    def test_un_negativo_liso_es_estrato_pobre(self):
        """Un NEG ya es adverso por la regla: anotarlo no aporta información nueva."""
        e = curacion._estrato_de("NEG", "pésimo servicio", "", None)

        self.assertEqual(e, curacion.ESTRATO_POBRE)

    def test_los_dos_estratos_cubren_todo(self):
        """Sin partición completa el re-pesado no suma 1 y la estimación se rompe."""
        casos = [("POS", "hola", "", None), ("NEG", "mal", "", None),
                 ("NEU", "paro mañana", "toma del campus", "federacion")]
        for sent, txt, cap, tipo in casos:
            with self.subTest(sent=sent):
                self.assertIn(curacion._estrato_de(sent, txt, cap, tipo),
                              (curacion.ESTRATO_RICO, curacion.ESTRATO_POBRE))


class TestRepesado(unittest.TestCase):
    """El re-pesado, aislado de la base. Es la pieza que hace válida a la cola."""

    def test_con_estratos_del_mismo_tamano_es_el_promedio_simple(self):
        """Caso de control: sin desbalance, re-pesar no puede cambiar nada."""
        v = curacion.repesar_por_estrato(
            {"rico": (10, 5), "pobre": (10, 5)}, {"rico": 100, "pobre": 100})

        self.assertAlmostEqual(v, 0.5, places=9)

    def test_recupera_la_tasa_real_cuando_el_rico_esta_sobremuestreado(self):
        """EL test que justifica todo el archivo.

        Corpus: 100 del estrato rico con 50 % de adversos y 900 del pobre con 10 %.
        La tasa real es (100·0,5 + 900·0,1)/1000 = 0,14.

        Si se anotan 50 de cada estrato —o sea el rico 9 veces sobrerrepresentado—,
        el promedio simple da 0,30, más del doble. El re-pesado devuelve 0,14.
        """
        muestra = {"rico": (50, 25), "pobre": (50, 5)}      # 50 % y 10 %
        tamanos = {"rico": 100, "pobre": 900}

        simple = (25 + 5) / (50 + 50)
        repesado = curacion.repesar_por_estrato(muestra, tamanos)

        self.assertAlmostEqual(simple, 0.30, places=9)
        self.assertAlmostEqual(repesado, 0.14, places=9)

    def test_un_estrato_sin_anotar_no_inventa_un_numero(self):
        """Si falta un estrato entero, la estimación global no se puede afirmar."""
        self.assertIsNone(curacion.repesar_por_estrato(
            {"rico": (10, 5), "pobre": (0, 0)}, {"rico": 100, "pobre": 900}))

    def test_sin_anotaciones_devuelve_none(self):
        self.assertIsNone(curacion.repesar_por_estrato({}, {"rico": 100}))

    def test_un_estrato_de_tamano_cero_no_divide_por_cero(self):
        v = curacion.repesar_por_estrato(
            {"rico": (10, 5), "pobre": (10, 1)}, {"rico": 100, "pobre": 0})

        self.assertAlmostEqual(v, 0.5, places=9)


class TestColaEstratificada(unittest.TestCase):
    """La cola en sí, contra una base real en memoria."""

    def setUp(self):
        from datetime import datetime
        from app.services.percepcion.models import (
            PercepcionComentario, PercepcionCuenta, PercepcionPublicacion, PercepcionScore,
        )
        # `_memoria()` solo crea hechos y eventos; esta cola baja al corpus crudo.
        from tests.test_percepcion import _memoria_completa
        self.db = _memoria_completa()
        self.db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="ucn"))
        self.db.add(PercepcionPublicacion(
            id=1, cuenta_id=1, external_id="p1", caption="", tipo="post",
            fecha_publicacion=datetime(2026, 5, 1), n_likes=0))
        # 20 del estrato rico (POS con léxico de conflicto) y 80 del pobre.
        for i in range(100):
            rico = i < 20
            texto = "vamos con el paro compañeros" if rico else "muy linda la actividad"
            self.db.add(PercepcionComentario(
                id=i + 1, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}",
                texto=texto, fecha_comentario=datetime(2026, 5, 2), n_likes=0,
                tema="vida_estudiantil"))
            self.db.add(PercepcionScore(
                id=i + 1, comentario_id=i + 1, modelo="m", sentimiento="POS",
                prob_pos=0.8, prob_neu=0.1, prob_neg=0.1))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _pedir(self, limite=20, semilla=7):
        return curacion.comentarios_para_scoring(
            self.db, limite=limite, orden=MUESTRA_ESTRATIFICADA, semilla=semilla)

    def test_sobremuestrea_el_estrato_rico_sin_dejar_fuera_al_pobre(self):
        """Ni todo dirigido (no evaluable) ni todo al azar (caro). Las dos cosas."""
        items = self._pedir(limite=20)["items"]
        ricos = sum(1 for it in items
                    if curacion._estrato_de("POS", it["texto"], "", None) == curacion.ESTRATO_RICO)

        self.assertGreater(ricos, len(items) // 2, "el rico tiene que estar sobrerrepresentado")
        self.assertLess(ricos, len(items), "pero el pobre no puede quedar sin muestra")

    def test_es_reproducible_con_la_misma_semilla(self):
        """Sin esto, dos personas anotarían muestras distintas y no serían comparables."""
        a = [it["id"] for it in self._pedir(semilla=11)["items"]]
        b = [it["id"] for it in self._pedir(semilla=11)["items"]]

        self.assertEqual(a, b)

    def test_semillas_distintas_dan_muestras_distintas(self):
        a = {it["id"] for it in self._pedir(semilla=1)["items"]}
        b = {it["id"] for it in self._pedir(semilla=99)["items"]}

        self.assertNotEqual(a, b)

    def test_declara_su_origen_para_que_el_repesado_sea_posible(self):
        """`origen_muestra` es lo que después permite separar los estratos."""
        self.assertEqual(self._pedir()["orden"], MUESTRA_ESTRATIFICADA)
