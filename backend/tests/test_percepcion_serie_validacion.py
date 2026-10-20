"""Sobre QUÉ SERIE se valida un pronóstico: la del tablero o la canónica.

El problema
-----------
El tablero muestra el índice PONDERADO por tema (y desde 09-2026, con el crédito
recortado por atribuibilidad). Los baselines de `prediccion` corrían sobre el índice
CANÓNICO —conteos crudos— así que la vara del proyecto y el número que mira el director
eran dos series distintas: sd 10,51 contra 9,08.

No era un olvido. `serie_semanal` lo decía: «lo que se pronostica tiene que poder
verificarse contando». Y había una razón técnica más dura: `_ruido()` es un estimador
BINOMIAL sobre los conteos, y un índice ponderado rompe ese modelo de ruido. Por eso la
mejora del 15 % que se midió el 01-09-2026 (media móvil 8,57 → 7,30 con el ponderado)
nunca se pudo integrar.

Este archivo fija la salida: el estimador de ruido GENERALIZADO, que acepta cualquier
esquema de pesos y se reduce exactamente al binomial cuando los pesos valen 1.

La matemática
-------------
Por comentario i, el aporte al índice es

    Z_i = +wc(tema_i)  si POS ·  −wd(tema_i) si NEG ·  0 si NEU

    índice = 50 + 50·(1/n)·Σ Z_i

Con los comentarios independientes y el tema fijo dentro de cada grupo (que es el grano
de `percepcion_hecho_diario`, así que no hace falta ninguna migración):

    Var(Z | tema t) = wc_t²·p_t + wd_t²·q_t − (wc_t·p_t − wd_t·q_t)²
    Var(índice)     = (50/n)² · Σ_t n_t · Var(Z | t)
    ruido           = 50·√( Σ_t n_t · Var(Z|t) ) / n

Con wc = wd = 1 y un solo grupo se reduce a

    Var(Z) = p + q − (p−q)² = p(1−p) + q(1−q) + 2pq

que es exactamente la fórmula binomial anterior. Ese caso límite es el primer test del
archivo, y es lo que hace confiable a todo lo demás: si la generalización no reprodujera
el número viejo, estaría midiendo otra cosa.

El suavizado de Laplace se aplica DENTRO de cada tema (`p_t = (npos_t+1)/(n_t+3)`). Con
temas de pocos comentarios eso infla el ruido, y es el lado correcto para errar: un
ruido sobreestimado hace la vara MÁS exigente, nunca más laxa.
"""
from __future__ import annotations

import math
import unittest
from datetime import date, timedelta

from app.services.percepcion import ponderacion, prediccion, repository
from app.services.percepcion.models import PercepcionHechoDiario

from tests.test_percepcion import _memoria


def _ruido_binomial(npos: int, nneu: int, nneg: int) -> float:
    """La fórmula ANTERIOR, escrita acá para poder contrastar contra ella.

    Si la generalización deja de reproducir esto, el cambio rompió el estimador.
    """
    tot = npos + nneu + nneg
    if tot < 1:
        return 0.0
    den = tot + 3
    p, q = (npos + 1) / den, (nneg + 1) / den
    var = (p * (1 - p) + q * (1 - q) + 2 * p * q) / tot
    return 50.0 * math.sqrt(max(var, 0.0))


class TestRuidoGeneralizado(unittest.TestCase):
    """El estimador nuevo, aislado de la base."""

    def test_con_pesos_uno_reproduce_el_binomial_exacto(self):
        """El caso límite que valida toda la generalización.

        Un solo tema, crédito y daño = 1: tiene que dar el MISMO número que la
        fórmula binomial de siempre, no uno parecido.
        """
        for npos, nneu, nneg in ((30, 0, 10), (5, 40, 5), (100, 20, 3), (1, 1, 1)):
            with self.subTest(npos=npos, nneu=nneu, nneg=nneg):
                obtenido = prediccion._ruido_ponderado(
                    [(npos, nneu, nneg, 1.0, 1.0)], npos + nneu + nneg)

                self.assertAlmostEqual(
                    obtenido, _ruido_binomial(npos, nneu, nneg), places=9,
                    msg="la generalización tiene que contener al caso anterior")

    def test_un_tema_liviano_aporta_menos_ruido(self):
        """Si el tema pesa menos, mueve menos el índice y por lo tanto lo ensucia menos."""
        pesado = prediccion._ruido_ponderado([(30, 0, 10, 1.0, 1.0)], 40)
        liviano = prediccion._ruido_ponderado([(30, 0, 10, 0.1, 0.1)], 40)

        self.assertLess(liviano, pesado)

    def test_una_semana_toda_neutra_casi_no_tiene_ruido_de_signo(self):
        """Los neutros no aportan crédito ni daño: no pueden mover el índice.

        No da 0 exacto por el suavizado de Laplace, que es deliberado: afirmar
        varianza cero sobre una muestra finita sería una certeza falsa.
        """
        ruido = prediccion._ruido_ponderado([(0, 100, 0, 1.0, 1.0)], 100)

        self.assertGreater(ruido, 0.0)
        self.assertLess(ruido, prediccion._ruido_ponderado([(50, 0, 50, 1.0, 1.0)], 100))

    def test_suma_el_aporte_de_cada_tema_por_separado(self):
        """Dos temas con pesos distintos: el ruido sale de sumar sus varianzas.

        Es lo que permite calcularlo sin bajar al comentario individual.
        """
        grupos = [(20, 0, 0, 1.0, 1.0), (0, 0, 20, 0.1, 0.1)]

        obtenido = prediccion._ruido_ponderado(grupos, 40)

        def var(npos, nneu, nneg, wc, wd):
            n = npos + nneu + nneg
            den = n + 3
            p, q = (npos + 1) / den, (nneg + 1) / den
            return n * (wc * wc * p + wd * wd * q - (wc * p - wd * q) ** 2)

        esperado = 50.0 * math.sqrt(sum(var(*g) for g in grupos)) / 40
        self.assertAlmostEqual(obtenido, esperado, places=9)

    def test_sin_comentarios_no_inventa_ruido(self):
        self.assertEqual(prediccion._ruido_ponderado([], 0), 0.0)


class TestSerieDeValidacion(unittest.TestCase):
    """La serie que alimenta el backtesting."""

    def setUp(self):
        self.db = _memoria()
        self.lunes = date(2026, 1, 5)

    def tearDown(self):
        self.db.close()

    def _hecho(self, i: int, tema: str, *, n_pos=0, n_neu=0, n_neg=0):
        n = n_pos + n_neu + n_neg
        self.db.add(PercepcionHechoDiario(
            fecha=self.lunes + timedelta(days=7 * i), campus="Antofagasta",
            tema=tema, n_comentarios=n, n_pos=n_pos, n_neu=n_neu, n_neg=n_neg,
            suma_peso=float(n), peso_pos=float(n_pos), peso_neg=float(n_neg),
            suma_pos=float(n_pos), suma_neg=float(n_neg), suma_ganadora=float(n)))

    def test_sin_ponderar_la_serie_no_cambia(self):
        """No-regresión: `ponderar_tema=False` da el número de siempre.

        El canónico tiene que seguir disponible: es la serie con la que se leyó toda
        la historia del proyecto y la única que se verifica contando.
        """
        self._hecho(0, "mascotas", n_pos=30, n_neg=10)
        self.db.commit()

        p = prediccion.serie_semanal(self.db, ponderar_tema=False)[0]

        self.assertAlmostEqual(p["indice"], 75.0)          # 50 + 50·(30−10)/40
        self.assertAlmostEqual(p["ruido"], _ruido_binomial(30, 0, 10), places=9)

    def test_ponderada_aplica_credito_y_dano_del_tema(self):
        """`mascotas`: peso 0,1 y no atribuible → crédito 0,05 · daño 0,10."""
        self._hecho(0, "mascotas", n_pos=30, n_neg=10)
        self.db.commit()

        p = prediccion.serie_semanal(self.db, ponderar_tema=True)[0]

        # (0,05·30 − 0,10·10)/40 = (1,5 − 1,0)/40
        self.assertAlmostEqual(p["indice"], 50 + 50 * 0.5 / 40, places=6)

    def test_mezcla_de_temas_pondera_cada_uno_por_separado(self):
        """El peso se aplica ANTES de sumar, que es lo que el grano por tema permite."""
        self._hecho(0, "academico", n_pos=20, n_neg=0)                 # atribuible, 0,9
        self._hecho(0, "mascotas", n_pos=0, n_neg=20)                  # 0,1 al daño
        self.db.commit()

        p = prediccion.serie_semanal(self.db, ponderar_tema=True)[0]

        esperado = 50 + 50 * (0.9 * 20 - 0.1 * 20) / 40
        self.assertAlmostEqual(p["indice"], esperado, places=6)
        self.assertEqual(p["n"], 40, "el denominador cuenta comentarios, no pesos")

    def test_la_serie_ponderada_coincide_con_el_indice_DEL_TABLERO(self):
        """EL PUNTO DE TODO EL EJERCICIO: una sola serie, dos lecturas coherentes.

        Si el pronóstico se valida contra un número distinto del que muestra el
        tablero, «el modelo le ganó a la vara» y «el índice subió» hablan de cosas
        distintas y nadie puede juntarlas. Este test ata las dos rutas de cálculo.
        """
        self._hecho(0, "academico", n_pos=20, n_neu=5, n_neg=5)
        self._hecho(0, "mascotas", n_pos=10, n_neu=0, n_neg=10)
        self.db.commit()

        de_la_serie = prediccion.serie_semanal(self.db, ponderar_tema=True)[0]["indice"]
        del_tablero = repository.resumen(
            self.db, dias=1, peso_likes=0.0, vida_media=0,
            fecha_desde=self.lunes, fecha_hasta=self.lunes + timedelta(days=6),
        )["indice_promedio"]

        self.assertAlmostEqual(de_la_serie, del_tablero, places=6)

    def test_el_ruido_ponderado_es_menor_que_el_canonico_en_temas_livianos(self):
        """Menos peso mueve menos el índice: la serie ponderada es menos ruidosa.

        Es la razón por la que ponderar mejoró el MAE un 15 % cuando se midió, y
        también por la que el TECHO se achica: hay menos ruido que ganarle.
        """
        self._hecho(0, "mascotas", n_pos=30, n_neg=10)
        self.db.commit()

        pond = prediccion.serie_semanal(self.db, ponderar_tema=True)[0]["ruido"]
        canon = prediccion.serie_semanal(self.db, ponderar_tema=False)[0]["ruido"]

        self.assertLess(pond, canon)

    def test_el_volumen_no_depende_del_esquema_de_pesos(self):
        """`n` cuenta comentarios. Ponderar no puede encoger la muestra."""
        self._hecho(0, "mascotas", n_pos=30, n_neg=10)
        self.db.commit()

        con = prediccion.serie_semanal(self.db, ponderar_tema=True)[0]
        sin = prediccion.serie_semanal(self.db, ponderar_tema=False)[0]

        self.assertEqual(con["n"], sin["n"])
        self.assertEqual(con["n"], 40)

    def test_el_filtro_de_semanas_flacas_es_el_mismo_en_los_dos_esquemas(self):
        """Si ponderar sacara semanas de la serie, los dos esquemas no serían comparables."""
        self._hecho(0, "mascotas", n_pos=30, n_neg=10)   # n=40
        self._hecho(1, "mascotas", n_pos=3, n_neg=1)     # n=4
        self.db.commit()

        self.assertEqual(len(prediccion.serie_semanal(self.db, ponderar_tema=True)), 1)
        self.assertEqual(len(prediccion.serie_semanal(self.db, ponderar_tema=False)), 1)


class TestLaVaraDeclaraSuSerie(unittest.TestCase):
    """Un cuadro de baselines que no dice sobre qué serie corrió no se puede leer."""

    def setUp(self):
        self.db = _memoria()
        self.lunes = date(2026, 1, 5)
        for i in range(14):
            n_pos = 30 + (i % 5)
            self.db.add(PercepcionHechoDiario(
                fecha=self.lunes + timedelta(days=7 * i), campus="Antofagasta",
                tema="academico", n_comentarios=n_pos + 10, n_pos=n_pos, n_neu=0,
                n_neg=10, suma_peso=float(n_pos + 10), peso_pos=float(n_pos),
                peso_neg=10.0, suma_pos=float(n_pos), suma_neg=10.0,
                suma_ganadora=float(n_pos + 10)))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_la_respuesta_declara_sobre_que_serie_se_midio(self):
        """Sin esto, dos personas con distinta configuración comparan MAE incomparables.

        Mismo criterio que `unidad_semanas` en la detección de anomalías: el panel
        declara la configuración con la que se calculó lo que muestra.
        """
        r = prediccion.evaluar_baselines(self.db, ponderar_tema=True)

        self.assertIn("serie", r)
        self.assertEqual(r["serie"], "ponderada")
        self.assertEqual(
            prediccion.evaluar_baselines(self.db, ponderar_tema=False)["serie"],
            "canonica")

    def test_el_techo_y_la_vara_salen_de_la_misma_serie(self):
        """Comparar el MAE de una serie contra el ruido de la otra sería un sinsentido."""
        r = prediccion.evaluar_baselines(self.db, ponderar_tema=True)

        self.assertIsNotNone(r["error_irreducible"])
        self.assertGreater(r["error_irreducible"], 0)
        self.assertIsNotNone(r["desvio_serie"])

    def test_los_dos_esquemas_evaluan_las_mismas_semanas(self):
        """Si cambiara el conjunto evaluado, los MAE no serían comparables entre sí."""
        pond = prediccion.evaluar_baselines(self.db, ponderar_tema=True)
        canon = prediccion.evaluar_baselines(self.db, ponderar_tema=False)

        self.assertEqual(pond["evaluadas"], canon["evaluadas"])
        self.assertEqual(pond["semanas_con_datos"], canon["semanas_con_datos"])
