"""Tests de los BASELINES de predicción (pregunta A del plan de simulación).

Lo que fijan no es la precisión de un pronóstico: es que la evaluación sea honesta.
Un backtesting mal armado —que mire el futuro, que compare modelos sobre conjuntos
distintos, o que ignore el error irreducible— produce números excelentes y falsos, y
eso es peor que no medir.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.services.percepcion import prediccion
from app.services.percepcion.models import PercepcionEvento, PercepcionHechoDiario

from tests.test_percepcion import _memoria


class TestSerieYCategorias(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()
        self.lunes = date(2026, 1, 5)

    def tearDown(self):
        self.db.close()

    def _sem(self, i: int, *, n_pos: int, n_neu: int = 0, n_neg: int = 0):
        n = n_pos + n_neu + n_neg
        self.db.add(PercepcionHechoDiario(
            fecha=self.lunes + timedelta(days=7 * i), campus="Antofagasta",
            facultad=None, departamento=None, tema="academico",
            n_comentarios=n, n_pos=n_pos, n_neu=n_neu, n_neg=n_neg,
            suma_peso=float(n), peso_pos=float(n_pos), peso_neg=float(n_neg),
            suma_pos=float(n_pos), suma_neg=float(n_neg), suma_ganadora=float(n),
            emociones={"joy": n_pos}))

    def test_la_serie_descarta_semanas_flacas(self):
        self._sem(0, n_pos=30, n_neg=10)   # n=40, entra
        self._sem(1, n_pos=3, n_neg=1)     # n=4, no
        self.db.commit()
        serie = prediccion.serie_semanal(self.db, n_min=20)
        self.assertEqual(len(serie), 1)
        self.assertEqual(serie[0]["n"], 40)

    def test_el_indice_canonico_se_puede_verificar_contando(self):
        """Con `ponderar_tema=False` el número sale de contar, y eso sigue valiendo.

        Es la propiedad por la que la vara corrió sobre esta serie hasta 09-2026: un
        pronóstico se contrasta contra algo que cualquiera puede recalcular a mano.
        """
        self._sem(0, n_pos=30, n_neg=10)
        self.db.commit()
        # 50 + 50*(30-10)/40 = 75
        self.assertAlmostEqual(
            prediccion.serie_semanal(self.db, ponderar_tema=False)[0]["indice"], 75.0)

    def test_por_defecto_se_valida_contra_LA_SERIE_DEL_TABLERO(self):
        """La vara corre sobre el índice ponderado, que es el que mira quien decide.

        Resuelto el 08-09-2026 midiendo las dos sobre los 4 años reales: la ponderada
        da 15 % menos de MAE (7,31 contra 8,62), mejor relación ruido/sd (0,32 contra
        0,41) y el mismo margen para que un modelo aporte (techo 4,45 contra 4,32).
        No pierde una sola semana.

        `academico` pesa 0,9 y es atribuible, así que crédito y daño valen 0,9:
        50 + 50·(0,9·30 − 0,9·10)/40 = 72,5.
        """
        self._sem(0, n_pos=30, n_neg=10)
        self.db.commit()

        self.assertAlmostEqual(prediccion.serie_semanal(self.db)[0]["indice"], 72.5)
        self.assertTrue(prediccion.PONDERAR_TEMA_VALIDACION)

    def test_la_vara_declara_contra_que_serie_corrio(self):
        """Un MAE sin su serie no se puede comparar con otro MAE."""
        self._sem(0, n_pos=30, n_neg=10)
        self.db.commit()

        self.assertEqual(prediccion.evaluar_baselines(self.db)["serie"], "ponderada")

    def test_cada_semana_trae_su_ruido_y_es_positivo(self):
        self._sem(0, n_pos=30, n_neg=10)
        self.db.commit()
        self.assertGreater(prediccion.serie_semanal(self.db)[0]["ruido"], 0.0,
                           "una semana homogénea con ruido 0 sería una certeza falsa")

    def test_la_serie_sale_ordenada_en_el_tiempo(self):
        for i in (3, 0, 2, 1):
            self._sem(i, n_pos=30, n_neg=10)
        self.db.commit()
        semanas = [x["semana"] for x in prediccion.serie_semanal(self.db)]
        self.assertEqual(semanas, sorted(semanas), "sin orden, el walk-forward miraría el futuro")

    # --- categorías de calendario --- #
    def test_un_paro_marca_la_semana_como_disruptiva(self):
        self.db.add(PercepcionEvento(
            nombre="Paro", tipo="paro", fecha_inicio=self.lunes + timedelta(days=2),
            fecha_fin=self.lunes + timedelta(days=4), ambito="global"))
        self.db.commit()
        cats = prediccion.categorias_por_semana(self.db, [self.lunes])
        self.assertEqual(cats[self.lunes], prediccion.CAT_DISRUPTIVA)

    def test_el_paro_le_gana_al_receso_cuando_se_solapan(self):
        """Sin un orden explícito, el resultado dependería del orden de la base."""
        self.db.add(PercepcionEvento(nombre="Receso", tipo="receso",
                                     fecha_inicio=self.lunes, fecha_fin=self.lunes + timedelta(days=6),
                                     ambito="global"))
        self.db.add(PercepcionEvento(nombre="Paro", tipo="paro",
                                     fecha_inicio=self.lunes, fecha_fin=self.lunes + timedelta(days=6),
                                     ambito="global"))
        self.db.commit()
        cats = prediccion.categorias_por_semana(self.db, [self.lunes])
        self.assertEqual(cats[self.lunes], prediccion.CAT_DISRUPTIVA)

    def test_un_evento_que_solo_toca_el_borde_de_la_semana_cuenta(self):
        """Un paro que arranca el domingo afecta esa semana, no solo la siguiente."""
        cats = prediccion.categorias_por_semana(self.db, [self.lunes])
        self.db.add(PercepcionEvento(
            nombre="Paro", tipo="paro", fecha_inicio=self.lunes + timedelta(days=6),
            ambito="global"))
        self.db.commit()
        cats = prediccion.categorias_por_semana(self.db, [self.lunes])
        self.assertEqual(cats[self.lunes], prediccion.CAT_DISRUPTIVA)

    def test_una_semana_sin_eventos_es_normal(self):
        self.assertEqual(
            prediccion.categorias_por_semana(self.db, [self.lunes])[self.lunes],
            prediccion.CAT_NORMAL)


class TestEvaluacionDeBaselines(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()
        self.lunes = date(2025, 1, 6)

    def tearDown(self):
        self.db.close()

    def _sem(self, i: int, pos: int, neg: int, neu: int = 0):
        n = pos + neg + neu
        self.db.add(PercepcionHechoDiario(
            fecha=self.lunes + timedelta(days=7 * i), campus="Antofagasta",
            facultad=None, departamento=None, tema="academico",
            n_comentarios=n, n_pos=pos, n_neu=neu, n_neg=neg,
            suma_peso=float(n), peso_pos=float(pos), peso_neg=float(neg),
            suma_pos=float(pos), suma_neg=float(neg), suma_ganadora=float(n),
            emociones={"joy": pos}))

    def _serie_plana(self, semanas: int = 20):
        for i in range(semanas):
            self._sem(i, 30, 10)
        self.db.commit()

    def test_con_pocas_semanas_no_evalua_y_lo_dice(self):
        for i in range(3):
            self._sem(i, 30, 10)
        self.db.commit()
        r = prediccion.evaluar_baselines(self.db)
        self.assertEqual(r["evaluadas"], 0)
        self.assertEqual(r["modelos"], [])
        self.assertTrue(any("se necesitan más" in a for a in r["avisos"]))

    def test_sobre_una_serie_constante_todos_aciertan(self):
        self._serie_plana()
        r = prediccion.evaluar_baselines(self.db)
        self.assertGreater(len(r["modelos"]), 0)
        for m in r["modelos"]:
            with self.subTest(modelo=m["nombre"]):
                self.assertAlmostEqual(m["mae"], 0.0, places=6)

    def test_todos_los_modelos_se_evaluan_sobre_LAS_MISMAS_semanas(self):
        """Comparar MAE de conjuntos distintos no compara nada.

        Por eso los baselines caen a la media en vez de devolver None cuando les
        falta su dato preferido.
        """
        for i in range(20):
            self._sem(i, 30 + (i % 5), 10)
        self.db.commit()
        r = prediccion.evaluar_baselines(self.db)
        n = {m["n_predicciones"] for m in r["modelos"]}
        self.assertEqual(len(n), 1, f"los modelos predijeron distinta cantidad: {n}")
        self.assertEqual(n.pop(), r["evaluadas"])

    def test_el_walk_forward_no_mira_el_futuro(self):
        """Si mirara adelante, un salto brusco no le costaría error a persistencia."""
        for i in range(12):
            self._sem(i, 35, 5)          # índice alto y estable
        for i in range(12, 20):
            self._sem(i, 5, 35)          # se da vuelta de golpe
        self.db.commit()
        r = prediccion.evaluar_baselines(self.db)
        pers = next(m for m in r["modelos"] if m["nombre"] == "persistencia")
        self.assertGreater(pers["mae"], 0.0,
                           "con un quiebre así, un backtesting honesto TIENE que errar")

    def test_reporta_el_error_irreducible(self):
        self._serie_plana()
        r = prediccion.evaluar_baselines(self.db)
        self.assertIsNotNone(r["error_irreducible"])
        self.assertGreater(r["error_irreducible"], 0.0)

    def test_marca_al_modelo_que_ya_toco_el_piso_de_ruido(self):
        self._serie_plana()
        r = prediccion.evaluar_baselines(self.db)
        mejor = r["modelos"][0]
        self.assertTrue(mejor["indistinguible_del_techo"])
        self.assertTrue(any("irreducible" in a for a in r["avisos"]))

    def test_avisa_cuando_dos_modelos_empatan(self):
        self._serie_plana()
        r = prediccion.evaluar_baselines(self.db)
        self.assertTrue(any("empatados" in a for a in r["avisos"]))

    def test_siempre_recuerda_que_son_la_vara_y_no_un_modelo(self):
        self._serie_plana()
        r = prediccion.evaluar_baselines(self.db)
        self.assertTrue(any("no se integra" in a for a in r["avisos"]),
                        "sin esta regla a la vista, el cuadro se lee como un campeonato")

    def test_el_baseline_de_calendario_aprende_el_efecto_de_un_paro(self):
        """Si las semanas de paro son sistemáticamente peores, tiene que capturarlo."""
        for i in range(20):
            hay_paro = i % 5 == 4
            if hay_paro:
                self._sem(i, 10, 30)
                self.db.add(PercepcionEvento(
                    nombre=f"Paro {i}", tipo="paro",
                    fecha_inicio=self.lunes + timedelta(days=7 * i),
                    fecha_fin=self.lunes + timedelta(days=7 * i + 6), ambito="global"))
            else:
                self._sem(i, 30, 10)
        self.db.commit()
        r = prediccion.evaluar_baselines(self.db)
        cal = next(m for m in r["modelos"] if m["nombre"] == "calendario")
        pers = next(m for m in r["modelos"] if m["nombre"] == "persistencia")
        self.assertLess(cal["mae"], pers["mae"],
                        "con un efecto de paro tan marcado, el calendario debería ganar")

    def test_los_modelos_salen_ordenados_del_mejor_al_peor(self):
        for i in range(20):
            self._sem(i, 30 + (i % 7), 10)
        self.db.commit()
        maes = [m["mae"] for m in prediccion.evaluar_baselines(self.db)["modelos"]]
        self.assertEqual(maes, sorted(maes))


if __name__ == "__main__":
    unittest.main()
