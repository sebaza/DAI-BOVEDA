"""Tests de la SEÑAL DE CONFLICTO.

El test central es el de sensibilidad a la ventana. Una versión anterior de este
módulo comparaba contra UN período previo y daba una alerta contundente sobre el
episodio "Toma Campus Angamos": adversos de 4,6 % a 12,9 %. Era un artefacto —
adentro de esa ventana caía Fiestas Patrias 2024, una semana de mucho comentario
amable que corría el promedio. Con ventanas de 7 a 21 días, el mismo episodio daba
que los adversos BAJABAN.

Un número que cambia de signo según dónde se ponga el corte no es un hallazgo. Estos
tests fijan que el módulo lo detecte y se abstenga en vez de elegir la ventana que
más impresiona.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.services.percepcion import conflicto
from app.services.percepcion.models import PercepcionHechoDiario

from tests.test_percepcion import _memoria


class TestSenalDeConflicto(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()
        self.fin = date(2026, 6, 30)

    def tearDown(self):
        self.db.close()

    def _dia(self, d: date, *, pos: int, neu: int, neg: int, campus="Antofagasta"):
        n = pos + neu + neg
        if n == 0:
            return
        self.db.add(PercepcionHechoDiario(
            fecha=d, campus=campus, facultad=None, departamento=None, tema="academico",
            n_comentarios=n, n_pos=pos, n_neu=neu, n_neg=neg,
            suma_peso=float(n), peso_pos=float(pos), peso_neg=float(neg),
            suma_pos=float(pos), suma_neg=float(neg), suma_ganadora=float(n),
            emociones={"joy": pos}))

    def _tramo(self, hasta: date, dias: int, *, pos: int, neu: int, neg: int):
        for i in range(dias):
            self._dia(hasta - timedelta(days=i), pos=pos, neu=neu, neg=neg)

    def _senal(self, **kw):
        return conflicto.senal_de_conflicto(self.db, dias=30, **kw)

    # ------------------------------------------------------------------ #
    # LA RAZÓN DE SER: no afirmar lo que depende de la ventana.
    # ------------------------------------------------------------------ #
    def test_se_abstiene_cuando_el_signo_cambia_segun_la_ventana(self):
        """Reproduce "Toma Campus Angamos": un pico amable lejano da vuelta el signo.

        Cerca (7-21 días) el conflicto venía ALTO; lejos (28-90) queda un pico de
        comentarios amables que baja el promedio previo y hace parecer que subió.
        """
        # Actual: 30 días con 10 % de adversos.
        self._tramo(self.fin, 30, pos=8, neu=1, neg=1)
        # Las 3 semanas previas: conflicto ALTO (25 %).
        self._tramo(self.fin - timedelta(days=30), 21, pos=6, neu=1, neg=3)
        # Antes de eso: un pico enorme de comentarios amables (el "Fiestas Patrias").
        self._tramo(self.fin - timedelta(days=52), 40, pos=48, neu=1, neg=1)
        self.db.commit()

        r = self._senal()
        self.assertFalse(r["consistente"], "el signo cambia y no lo detectó")
        self.assertIsNone(r["tendencia"])
        self.assertIn("signo", r["explicacion"])
        self.assertTrue(any("SENSIBLE" in a for a in r["avisos"]))

    def test_afirma_cuando_el_signo_aguanta_TODAS_las_ventanas(self):
        self._tramo(self.fin, 30, pos=4, neu=1, neg=5)                       # 50 % adversos
        self._tramo(self.fin - timedelta(days=30), 90, pos=8, neu=1, neg=1)  # 10 % siempre
        self.db.commit()
        r = self._senal()
        self.assertTrue(r["consistente"])
        self.assertEqual(r["tendencia"], "sube")
        self.assertIn("TODAS", r["explicacion"])

    def test_detecta_la_baja_consistente(self):
        self._tramo(self.fin, 30, pos=8, neu=1, neg=1)
        self._tramo(self.fin - timedelta(days=30), 90, pos=4, neu=1, neg=5)
        self.db.commit()
        r = self._senal()
        self.assertTrue(r["consistente"])
        self.assertEqual(r["tendencia"], "baja")

    def test_detecta_la_estabilidad(self):
        self._tramo(self.fin, 30, pos=8, neu=1, neg=1)
        self._tramo(self.fin - timedelta(days=30), 90, pos=8, neu=1, neg=1)
        self.db.commit()
        r = self._senal()
        self.assertTrue(r["consistente"])
        self.assertEqual(r["tendencia"], "igual")

    def test_barre_varias_ventanas_y_las_expone(self):
        """El lector tiene que poder ver el barrido, no solo su conclusión."""
        self._tramo(self.fin, 30, pos=4, neu=1, neg=5)
        self._tramo(self.fin - timedelta(days=30), 90, pos=8, neu=1, neg=1)
        self.db.commit()
        r = self._senal()
        self.assertGreaterEqual(len(r["comparaciones"]), 4)
        dias = [c["dias_previos"] for c in r["comparaciones"]]
        self.assertEqual(dias, sorted(dias))
        for c in r["comparaciones"]:
            self.assertIn(c["signo"], {"sube", "baja", "igual"})

    def test_el_delta_tipico_es_la_MEDIANA_no_el_promedio(self):
        """Una ventana atípica no debe arrastrar el resumen del barrido."""
        self._tramo(self.fin, 30, pos=4, neu=1, neg=5)
        self._tramo(self.fin - timedelta(days=30), 90, pos=8, neu=1, neg=1)
        self.db.commit()
        r = self._senal()
        deltas = sorted(c["delta_adversos"] for c in r["comparaciones"])
        self.assertEqual(r["delta_tipico"], deltas[len(deltas) // 2])

    # ------------------------------------------------------------------ #
    # El volumen, que es lo que un promedio esconde.
    # ------------------------------------------------------------------ #
    def test_informa_el_VOLUMEN_adverso_no_solo_la_proporcion(self):
        self._tramo(self.fin, 30, pos=6, neu=1, neg=3)
        self.db.commit()
        r = self._senal()
        self.assertEqual(r["actual"]["n_adversos"], 90)
        self.assertEqual(r["actual"]["pct_adversos"], 30.0)

    def test_el_indice_se_puede_verificar_contando(self):
        self._tramo(self.fin, 30, pos=6, neu=0, neg=2)   # 50+50*4/8 = 75
        self.db.commit()
        self.assertEqual(self._senal()["actual"]["indice"], 75.0)

    # ------------------------------------------------------------------ #
    # Honestidad sobre los límites.
    # ------------------------------------------------------------------ #
    def test_siempre_avisa_que_el_conflicto_medido_es_un_PISO(self):
        self._tramo(self.fin, 30, pos=6, neu=1, neg=3)
        self.db.commit()
        self.assertTrue(any("igual o mayor" in a for a in self._senal()["avisos"]))

    def test_cero_adversos_se_reporta_con_su_advertencia(self):
        self._tramo(self.fin, 30, pos=9, neu=1, neg=0)
        self.db.commit()
        r = self._senal()
        self.assertEqual(r["actual"]["n_adversos"], 0)
        self.assertTrue(any("oculta" in a for a in r["avisos"]))

    def test_sin_periodo_previo_da_el_volumen_pero_no_la_variacion(self):
        self._tramo(self.fin, 30, pos=6, neu=1, neg=3)
        self.db.commit()
        r = self._senal()
        self.assertEqual(r["comparaciones"], [])
        self.assertFalse(r["consistente"])
        self.assertGreater(r["actual"]["n_adversos"], 0)
        self.assertTrue(any("no se puede medir" in a for a in r["avisos"]))

    def test_con_UNA_sola_ventana_no_se_declara_consistencia(self):
        """«El signo aguanta en todas las ventanas» con una ventana es cierto por
        vacuidad, y suena mucho más firme de lo que es."""
        # Las ventanas previas son ANIDADAS: si la de 7 días llega al mínimo, todas
        # llegan. El caso de una sola comparación es el inverso — actividad únicamente
        # LEJOS, de modo que solo la ventana más larga junte volumen.
        self._tramo(self.fin, 30, pos=4, neu=1, neg=5)
        self._tramo(self.fin - timedelta(days=88), 8, pos=8, neu=1, neg=1)
        self.db.commit()
        r = self._senal()
        self.assertEqual(len(r["comparaciones"]), 1,
                         "solo la ventana de 90 días debería juntar volumen")
        self.assertFalse(r["consistente"], "declaró consistencia sobre una comparación")
        self.assertIsNone(r["tendencia"])
        self.assertIn("no se afirma nada", r["explicacion"])

    def test_una_ventana_previa_flaca_no_se_usa_para_comparar(self):
        self._tramo(self.fin, 30, pos=6, neu=1, neg=3)
        self._dia(self.fin - timedelta(days=31), pos=1, neu=0, neg=0)
        self.db.commit()
        self.assertEqual(self._senal()["comparaciones"], [])

    def test_sin_datos_no_revienta(self):
        r = self._senal()
        self.assertFalse(r["hay_datos"])
        self.assertFalse(r["consistente"])

    def test_respeta_el_filtro_de_sede(self):
        self._tramo(self.fin, 30, pos=1, neu=1, neg=8)
        for i in range(30):
            self._dia(self.fin - timedelta(days=i), pos=9, neu=1, neg=0, campus="Coquimbo")
        self.db.commit()
        self.assertEqual(self._senal(campus="Coquimbo")["actual"]["n_adversos"], 0)


if __name__ == "__main__":
    unittest.main()
