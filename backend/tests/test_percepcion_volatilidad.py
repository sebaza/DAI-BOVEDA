"""Tests de VOLATILIDAD por unidad (pregunta D del plan de simulación).

Lo que fijan estos tests no es una fórmula: es la diferencia entre un hallazgo y un
artefacto. Ordenar unidades por la desviación estándar cruda de su índice mide
**tamaño de muestra disfrazado de volatilidad** — una unidad con 5 comentarios por
semana oscila sola, y el ranking terminaría diciendo "las facultades chicas son
inestables", que es aritmética, no información.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.services.percepcion import volatilidad
from app.services.percepcion.models import PercepcionHechoDiario

from tests.test_percepcion import _memoria


class TestVolatilidadPorUnidad(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()
        self.lunes = date(2026, 1, 5)

    def tearDown(self):
        self.db.close()

    def _semana(self, i: int, *, facultad: str, n_pos: int, n_neu: int, n_neg: int):
        """Una semana de una unidad, con su reparto de tono."""
        n = n_pos + n_neu + n_neg
        self.db.add(PercepcionHechoDiario(
            fecha=self.lunes + timedelta(days=7 * i), campus="Antofagasta",
            facultad=facultad, departamento=None, tema="academico",
            n_comentarios=n, n_pos=n_pos, n_neu=n_neu, n_neg=n_neg,
            suma_peso=float(n), peso_pos=float(n_pos), peso_neg=float(n_neg),
            suma_pos=float(n_pos), suma_neg=float(n_neg), suma_ganadora=float(n),
            emociones={"joy": n_pos}))

    def _unidades(self, **kw):
        r = volatilidad.volatilidad_por_unidad(self.db, nivel="facultad", **kw)
        return {u["nombre"]: u for u in r["unidades"]}, r

    # ------------------------------------------------------------------ #
    # El corazón del asunto: descontar el ruido de muestreo.
    # ------------------------------------------------------------------ #
    def test_una_unidad_chica_que_oscila_no_le_gana_a_una_grande_que_oscila_igual(self):
        """Misma oscilación aparente, distinto n: la chica es ruido, la grande no.

        Es el test que justifica todo el módulo. Sin descontar el ruido, las dos
        saldrían empatadas y la conclusión sería falsa.
        """
        for i in range(10):
            # CHICA: 4 comentarios por semana, alterna 100% pos / 100% neg.
            # Con n=4 esa oscilación es perfectamente esperable por azar.
            self._semana(i, facultad="Chica",
                         n_pos=4 if i % 2 == 0 else 0, n_neu=0,
                         n_neg=0 if i % 2 == 0 else 4)
            # GRANDE: 100 por semana, misma oscilación extrema. Con n=100 eso NO
            # puede pasar por azar: es señal.
            self._semana(i, facultad="Grande",
                         n_pos=100 if i % 2 == 0 else 0, n_neu=0,
                         n_neg=0 if i % 2 == 0 else 100)
        self.db.commit()

        u, _ = self._unidades(n_min_semana=3, min_semanas=6)
        self.assertIn("Grande", u)
        self.assertIn("Chica", u)
        # Las dos tienen la MISMA sd observada (oscilan igual de fuerte)...
        self.assertAlmostEqual(u["Chica"]["sd_observada"], u["Grande"]["sd_observada"],
                               places=6)
        # ...pero la de la chica se explica por muestreo y la de la grande no.
        self.assertGreater(u["Chica"]["sd_ruido"], u["Grande"]["sd_ruido"])
        self.assertGreater(u["Grande"]["volatilidad_real"], u["Chica"]["volatilidad_real"])

    def test_una_unidad_estable_no_aparece_como_volatil(self):
        for i in range(10):
            self._semana(i, facultad="Estable", n_pos=30, n_neu=10, n_neg=10)
        self.db.commit()
        u, _ = self._unidades(n_min_semana=5, min_semanas=6)
        # Índice idéntico todas las semanas => sd observada 0 => no supera al ruido.
        self.assertEqual(u["Estable"]["sd_observada"], 0.0)
        self.assertIsNone(u["Estable"]["volatilidad_real"])

    def test_sin_senal_devuelve_None_y_no_cero(self):
        """Cero AFIRMA estabilidad. None dice 'no se puede saber'. No es lo mismo."""
        for i in range(8):
            self._semana(i, facultad="Ruidosa",
                         n_pos=5 if i % 2 == 0 else 3, n_neu=0,
                         n_neg=3 if i % 2 == 0 else 5)
        self.db.commit()
        u, _ = self._unidades(n_min_semana=5, min_semanas=6)
        if "Ruidosa" in u:
            self.assertIsNone(u["Ruidosa"]["volatilidad_real"])

    # ------------------------------------------------------------------ #
    # Umbrales de evidencia.
    # ------------------------------------------------------------------ #
    def test_una_unidad_con_pocas_semanas_queda_fuera_del_ranking(self):
        for i in range(3):
            self._semana(i, facultad="Fugaz", n_pos=20, n_neu=0, n_neg=10)
        self.db.commit()
        u, r = self._unidades(n_min_semana=5, min_semanas=6)
        self.assertNotIn("Fugaz", u)
        self.assertIn("Fugaz", r["sin_evidencia"])

    def test_las_semanas_flacas_no_cuentan(self):
        """Una semana de 2 comentarios no informa sobre la volatilidad de nadie."""
        for i in range(10):
            self._semana(i, facultad="Flaca", n_pos=1, n_neu=0, n_neg=1)
        self.db.commit()
        u, r = self._unidades(n_min_semana=5, min_semanas=6)
        self.assertNotIn("Flaca", u)

    def test_marca_cuando_el_volumen_es_bajo_para_afirmar(self):
        for i in range(10):
            self._semana(i, facultad="Justa",
                         n_pos=6 if i % 2 == 0 else 2, n_neu=0,
                         n_neg=2 if i % 2 == 0 else 6)
        self.db.commit()
        u, _ = self._unidades(n_min_semana=5, min_semanas=6)
        self.assertIn("Justa", u)
        self.assertFalse(u["Justa"]["evidencia_suficiente"],
                         "8 comentarios por semana no son los 30 que pide el módulo")

    # ------------------------------------------------------------------ #
    # Orden y avisos.
    # ------------------------------------------------------------------ #
    def test_ordena_por_volatilidad_real_no_por_la_observada(self):
        """Con la MISMA oscilación aparente, adelante va la que tiene más volumen.

        La oscilación tiene que ser idéntica en las dos: si a la chica se le da un
        vaivén más extremo, gana con razón —alternar 100 %/0 % diez semanas seguidas
        no es azar ni con n=4— y el test dejaría de probar lo que dice probar.
        """
        for i in range(10):
            alto = i % 2 == 0
            self._semana(i, facultad="Chica",
                         n_pos=3 if alto else 1, n_neu=0, n_neg=1 if alto else 3)
            self._semana(i, facultad="Grande",
                         n_pos=75 if alto else 25, n_neu=0, n_neg=25 if alto else 75)
        self.db.commit()
        u, r = self._unidades(n_min_semana=3, min_semanas=6)
        # Misma sd observada: las dos alternan entre los mismos dos índices.
        self.assertAlmostEqual(u["Chica"]["sd_observada"], u["Grande"]["sd_observada"],
                               places=6)
        nombres = [x["nombre"] for x in r["unidades"]]
        self.assertEqual(nombres[0], "Grande",
                         "ordenó por sd cruda: eso rankea tamaño de muestra")

    def test_avisa_que_las_posiciones_vecinas_no_son_distinguibles(self):
        """Dos unidades casi idénticas tienen que salir marcadas como empatadas."""
        for i in range(10):
            alto = i % 2 == 0
            pos, neg = (20, 10) if alto else (10, 20)
            self._semana(i, facultad="A", n_pos=pos, n_neu=0, n_neg=neg)
            # B es idéntica a A salvo en UNA semana. Su volatilidad real queda a
            # menos de DELTA_DISTINGUIBLE de la de A: empatadas dentro del error.
            if i == 9:
                pos, neg = 11, 19
            self._semana(i, facultad="B", n_pos=pos, n_neu=0, n_neg=neg)
        self.db.commit()
        u, r = self._unidades(n_min_semana=5, min_semanas=6)
        self.assertLess(
            abs(u["A"]["volatilidad_real"] - u["B"]["volatilidad_real"]),
            volatilidad.DELTA_DISTINGUIBLE,
            "el escenario exige que las dos queden dentro del error",
        )
        self.assertTrue(any("vecina" in a.lower() or "cercan" in a.lower()
                            for a in r["avisos"]),
                        "sin este aviso el ranking se lee como un orden exacto")

    def test_avisa_cuando_hay_muy_pocas_unidades_para_comparar(self):
        for i in range(10):
            self._semana(i, facultad="Unica", n_pos=20 if i % 2 else 10, n_neu=0,
                         n_neg=10 if i % 2 else 20)
        self.db.commit()
        _, r = self._unidades(n_min_semana=5, min_semanas=6)
        self.assertTrue(any("compar" in a.lower() for a in r["avisos"]),
                        "un ranking de una sola unidad no es un ranking")

    # ------------------------------------------------------------------ #
    # Bordes.
    # ------------------------------------------------------------------ #
    def test_sin_datos_no_revienta(self):
        r = volatilidad.volatilidad_por_unidad(self.db, nivel="facultad")
        self.assertEqual(r["unidades"], [])
        self.assertEqual(r["sin_evidencia"], [])

    def test_los_tres_niveles_estan_soportados(self):
        for i in range(10):
            self._semana(i, facultad="F", n_pos=20 if i % 2 else 10, n_neu=0,
                         n_neg=10 if i % 2 else 20)
        self.db.commit()
        for nivel in ("campus", "facultad", "departamento"):
            with self.subTest(nivel=nivel):
                r = volatilidad.volatilidad_por_unidad(self.db, nivel=nivel,
                                                       n_min_semana=5, min_semanas=6)
                self.assertEqual(r["nivel"], nivel)

    def test_el_indice_medio_se_puede_verificar_contando(self):
        """Sin ponderar por likes ni por recencia: el número tiene que ser reproducible."""
        for i in range(8):
            self._semana(i, facultad="Fija", n_pos=30, n_neu=0, n_neg=10)
        self.db.commit()
        u, _ = self._unidades(n_min_semana=5, min_semanas=6)
        # 50 + 50*(30-10)/40 = 75
        self.assertAlmostEqual(u["Fija"]["indice_medio"], 75.0, places=6)


if __name__ == "__main__":
    unittest.main()
