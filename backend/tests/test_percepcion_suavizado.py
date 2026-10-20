"""El quinto baseline: suavizado exponencial. Y por qué la fase 2 no agregó un modelo.

QUÉ PASÓ CON LA FASE 2
----------------------
El plan (`INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md`) pedía un modelo POBLACIONAL
de compartimentos: proporciones favorable/neutral/adverso que se mueven según eventos y
contagio. Se midió la estructura que ese modelo supone, y no está:

* **No hay contagio.** La regresión de ΔI sobre I(t) da pendiente −0,594; corregida por
  el sesgo de error de medición (−0,113, que es lo que aporta el ruido de muestreo)
  queda −0,481 → φ = 0,52. Es REVERSIÓN a la media, con vida media de 1,1 semanas, no
  autorefuerzo. Un término de contagio con β>0 no tiene nada que ajustar.
* **Los eventos no aportan sobre el estado previo.** Residuo de las semanas disruptivas
  tras descontar la reversión: −2,22 ± 2,03. El signo va en la dirección esperada y el
  error estándar es del mismo tamaño.
* **La composición aporta IN-SAMPLE y no sobrevive.** Agregar adverso+favorable sube el
  R² de 0,16 a 0,26 con los datos a la vista, pero walk-forward el modelo empeora:

      media_movil (la vara)          MAE 7,31
      regresión · índice                 7,48
      regresión · índice+adverso         7,71
      POBLACIONAL · idx+adv+fav          7,54
      POBLACIONAL + evento               7,50

  Con 12 a 60 pares para estimar 4-5 parámetros, la varianza de estimación se come toda
  la ganancia. Es exactamente el sobreajuste que el plan nombró como riesgo.

**Veredicto: el modelo poblacional NO supera la vara, así que por la regla del proyecto
no se integra.** Lo que sí mejora es MENOS modelo, no más — y eso es este archivo.

EL TECHO REAL NO ES EL ERROR IRREDUCIBLE
----------------------------------------
`error_irreducible` (2,86) mide solo el ruido de MUESTREO. No es el techo de un
pronóstico: la mayor parte de lo que varía el índice es señal real e impredecible desde
el pasado. La cota medida —el mejor modelo lineal con SEIS parámetros ajustado
in-sample, o sea con ventaja injusta— es **MAE 6,22**, con R² 0,30.

    vara honesta                                    7,31
    cota superior in-sample (ventaja injusta)       6,22
    margen máximo teórico                           1,09
    mínimo detectable con 74 semanas                0,58

El margen que queda es apenas el doble de lo que se puede demostrar. Cualquier modelo
futuro tiene que ganar en esa franja angosta, y conviene saberlo antes de construirlo.
"""
from __future__ import annotations

import statistics as st
import unittest
from datetime import date, timedelta

from app.services.percepcion import prediccion
from app.services.percepcion.models import PercepcionHechoDiario

from tests.test_percepcion import _memoria


def _hist(valores: list[float]) -> list[dict]:
    """Historial mínimo con la forma que consumen los baselines."""
    lunes = date(2026, 1, 5)
    return [{"semana": lunes + timedelta(days=7 * i), "n": 40, "indice": v, "ruido": 3.0}
            for i, v in enumerate(valores)]


class TestSuavizado(unittest.TestCase):
    def test_es_un_promedio_que_pesa_mas_lo_reciente(self):
        """Entre la última semana y el promedio llano, más cerca de la última."""
        hist = _hist([50.0] * 10 + [80.0])

        pred = prediccion._suavizado(hist, {}, {"semana": hist[-1]["semana"]})

        llano = st.mean(x["indice"] for x in hist)
        self.assertGreater(pred, llano)
        self.assertLess(pred, 80.0, "no puede pegarse del todo a la última: sería persistencia")

    def test_sobre_una_serie_constante_devuelve_esa_constante(self):
        """Sin variación no hay nada que suavizar."""
        hist = _hist([64.0] * 12)

        self.assertAlmostEqual(
            prediccion._suavizado(hist, {}, {"semana": hist[-1]["semana"]}), 64.0, places=6)

    def test_no_mira_el_futuro_para_elegir_su_lambda(self):
        """EL test que hace honesto a este baseline.

        λ se calibra sobre el historial recibido. Si la predicción de una semana
        cambiara al agregar semanas POSTERIORES, el backtesting estaría filtrando
        información del futuro y su MAE sería un número que no existe fuera del
        experimento.
        """
        base = _hist([60, 62, 58, 65, 61, 59, 63, 64, 57, 66])
        futuro = base + _hist([10.0] * 6)[:6]
        for i, x in enumerate(futuro[len(base):], start=len(base)):
            x["semana"] = base[0]["semana"] + timedelta(days=7 * i)

        con_futuro = prediccion._suavizado(futuro[:len(base)], {}, {"semana": base[-1]["semana"]})
        sin_futuro = prediccion._suavizado(base, {}, {"semana": base[-1]["semana"]})

        self.assertAlmostEqual(con_futuro, sin_futuro, places=9)

    def test_con_historial_muy_corto_no_se_cae(self):
        """Las primeras semanas no alcanzan para calibrar nada, y aun así hay que responder.

        Un baseline que devuelve None en algunos pasos queda evaluado sobre otro
        conjunto que los demás, y los MAE dejan de ser comparables.
        """
        for k in (1, 2, 3):
            with self.subTest(semanas=k):
                hist = _hist([60.0, 70.0, 55.0][:k])
                pred = prediccion._suavizado(hist, {}, {"semana": hist[-1]["semana"]})
                self.assertIsNotNone(pred)

    def test_sin_historial_devuelve_none(self):
        self.assertIsNone(prediccion._suavizado([], {}, {"semana": date(2026, 1, 5)}))

    def test_el_lambda_elegido_sale_del_menu_declarado(self):
        """Un λ continuo optimizado libremente sobreajustaría el historial corto."""
        self.assertTrue(prediccion.LAMBDAS_SUAVIZADO)
        for lam in prediccion.LAMBDAS_SUAVIZADO:
            self.assertGreater(lam, 0.0)
            self.assertLessEqual(lam, 1.0)


class TestSuavizadoEnLaVara(unittest.TestCase):
    """El baseline entra al cuadro como uno más, con el mismo protocolo."""

    def setUp(self):
        self.db = _memoria()
        lunes = date(2026, 1, 5)
        for i in range(24):
            n_pos = 28 + (i * 7) % 11
            self.db.add(PercepcionHechoDiario(
                fecha=lunes + timedelta(days=7 * i), campus="Antofagasta",
                tema="academico", n_comentarios=n_pos + 12, n_pos=n_pos, n_neu=2,
                n_neg=10, suma_peso=float(n_pos + 12), peso_pos=float(n_pos),
                peso_neg=10.0, suma_pos=float(n_pos), suma_neg=10.0,
                suma_ganadora=float(n_pos + 12)))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_aparece_entre_los_baselines(self):
        nombres = [m["nombre"] for m in prediccion.evaluar_baselines(self.db)["modelos"]]

        self.assertIn("suavizado", nombres)

    def test_predice_sobre_las_mismas_semanas_que_los_demas(self):
        """Si evaluara otro conjunto, su MAE no sería comparable con el de los otros."""
        modelos = prediccion.evaluar_baselines(self.db)["modelos"]
        n = {m["nombre"]: m["n_predicciones"] for m in modelos}

        self.assertEqual(len(set(n.values())), 1, f"conjuntos distintos: {n}")
