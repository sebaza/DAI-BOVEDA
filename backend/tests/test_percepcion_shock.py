"""Tests de la RESPUESTA A SHOCK (pregunta C del plan de simulación).

Lo que fijan es sobre todo lo que el módulo NO debe hacer: promediar episodios que
no se pueden medir, confundir «no recuperado» con «no medible», o medir un paro de
una sede contra el índice de toda la universidad. Cualquiera de las tres produce un
número presentable y falso.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.services.percepcion import shock
from app.services.percepcion.models import PercepcionEvento, PercepcionHechoDiario

from tests.test_percepcion import _memoria


class TestPerfilDeEpisodio(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()
        # El paro va del lunes 06/04/2026 al domingo 12/04.
        self.ini = date(2026, 4, 6)
        self.fin = date(2026, 4, 12)

    def tearDown(self):
        self.db.close()

    def _dia(self, d: date, *, pos: int, neg: int, campus: str = "Antofagasta"):
        n = pos + neg
        self.db.add(PercepcionHechoDiario(
            fecha=d, campus=campus, facultad=None, departamento=None, tema="academico",
            n_comentarios=n, n_pos=pos, n_neu=0, n_neg=neg,
            suma_peso=float(n), peso_pos=float(pos), peso_neg=float(neg),
            suma_pos=float(pos), suma_neg=float(neg), suma_ganadora=float(n),
            emociones={"joy": pos}))

    def _llenar(self, desde: date, dias: int, *, pos: int, neg: int,
                campus: str = "Antofagasta"):
        for i in range(dias):
            self._dia(desde + timedelta(days=i), pos=pos, neg=neg, campus=campus)

    def _episodio(self, **kw):
        base = {"nombre": "Paro", "tipo": "paro", "desde": self.ini, "hasta": self.fin,
                "ambito": "Antofagasta", "confianza": "confirmado", "dias": 7}
        base.update(kw)
        return base

    # ------------------------------------------------------------------ #
    def test_mide_la_caida_contra_las_cuatro_semanas_previas(self):
        # Previo alto (índice 75), durante bajo (índice 25).
        self._llenar(self.ini - timedelta(days=56), 56, pos=6, neg=2)   # 50+50*4/8 = 75
        self._llenar(self.ini, 7, pos=2, neg=6)                         # 50+50*(-4)/8 = 25
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertEqual(p["indice_previo"], 75.0)
        self.assertEqual(p["indice_durante"], 25.0)
        self.assertEqual(p["caida"], -50.0)
        self.assertEqual(p["evidencia"], shock.EVIDENCIA_SUFICIENTE)

    def test_un_paro_de_una_sede_no_se_mide_contra_las_otras(self):
        """Diluirlo con sedes que no lo vivieron da un efecto más chico que el real."""
        self._llenar(self.ini - timedelta(days=56), 56, pos=6, neg=2)
        self._llenar(self.ini, 7, pos=2, neg=6)
        # Coquimbo, en paz, con MUCHO volumen: si el ámbito se ignorara, taparía todo.
        self._llenar(self.ini, 7, pos=200, neg=0, campus="Coquimbo")
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertEqual(p["indice_durante"], 25.0,
                         "el índice del episodio se contaminó con otra sede")

    def test_sin_volumen_previo_la_evidencia_es_insuficiente(self):
        self._llenar(self.ini, 7, pos=2, neg=6)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertIsNone(p["indice_previo"])
        self.assertIsNone(p["caida"])
        self.assertEqual(p["evidencia"], shock.EVIDENCIA_PARCIAL)

    def test_sin_datos_de_ningun_lado_la_evidencia_es_nula(self):
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertEqual(p["evidencia"], shock.EVIDENCIA_NULA)
        self.assertIsNone(p["caida"])

    def test_una_ventana_flaca_no_cuenta_como_medible(self):
        """Cuatro comentarios en cuatro semanas no informan sobre nada."""
        for i in range(0, 56, 14):
            self._dia(self.ini - timedelta(days=56 - i), pos=1, neg=0)
        self._llenar(self.ini, 7, pos=2, neg=6)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertIsNone(p["indice_previo"])

    def test_devuelve_las_cinco_ventanas(self):
        self._llenar(self.ini - timedelta(days=56), 130, pos=6, neg=2)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertEqual(len(p["ventanas"]), 5)
        self.assertEqual(p["ventanas"][2]["etiqueta"], "durante")

    # ------------------------------------------------------------------ #
    # Recuperación.
    # ------------------------------------------------------------------ #
    def test_detecta_en_cuantas_semanas_vuelve_al_nivel_previo(self):
        self._llenar(self.ini - timedelta(days=56), 56, pos=6, neg=2)  # previo 75
        self._llenar(self.ini, 7, pos=2, neg=6)                        # durante 25
        # Dos semanas malas y a la tercera vuelve al nivel previo.
        self._llenar(self.fin + timedelta(days=1), 14, pos=4, neg=4)   # 50
        self._llenar(self.fin + timedelta(days=15), 21, pos=6, neg=2)  # 75
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertEqual(p["recuperado_en_semanas"], 3)
        self.assertIsNone(p["motivo_recuperacion"])

    def test_no_recuperado_es_un_hallazgo_no_una_falta_de_dato(self):
        self._llenar(self.ini - timedelta(days=56), 56, pos=6, neg=2)
        self._llenar(self.ini, 7, pos=2, neg=6)
        self._llenar(self.fin + timedelta(days=1), 90, pos=4, neg=4)   # nunca vuelve a 75
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertIsNone(p["recuperado_en_semanas"])
        self.assertIn("no se sostuvo", p["motivo_recuperacion"])

    def test_sin_datos_posteriores_lo_dice_distinto_de_no_recuperado(self):
        """«No recuperó» y «no se pudo medir» son hallazgo y falta de dato: distintos."""
        self._llenar(self.ini - timedelta(days=56), 56, pos=6, neg=2)
        self._llenar(self.ini, 7, pos=2, neg=6)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertIsNone(p["recuperado_en_semanas"])
        self.assertIn("medibles", p["motivo_recuperacion"])
        self.assertNotIn("no se sostuvo", p["motivo_recuperacion"])

    def test_sin_nivel_previo_no_se_puede_hablar_de_recuperacion(self):
        self._llenar(self.ini, 7, pos=2, neg=6)
        self._llenar(self.fin + timedelta(days=1), 60, pos=6, neg=2)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertIsNone(p["recuperado_en_semanas"])
        self.assertIn("previo", p["motivo_recuperacion"])


class TestRespuestaAShock(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()

    def tearDown(self):
        self.db.close()

    def _paro(self, ini: date, fin: date, *, confianza="confirmado", ambito="Antofagasta"):
        self.db.add(PercepcionEvento(
            nombre=f"Paro {ini}", tipo="paro", fecha_inicio=ini, fecha_fin=fin,
            ambito=ambito, confianza=confianza))

    def _llenar(self, desde: date, dias: int, *, pos: int, neg: int):
        for i in range(dias):
            n = pos + neg
            self.db.add(PercepcionHechoDiario(
                fecha=desde + timedelta(days=i), campus="Antofagasta", facultad=None,
                departamento=None, tema="academico", n_comentarios=n, n_pos=pos,
                n_neu=0, n_neg=neg, suma_peso=float(n), peso_pos=float(pos),
                peso_neg=float(neg), suma_pos=float(pos), suma_neg=float(neg),
                suma_ganadora=float(n), emociones={"joy": pos}))

    def test_no_promedia_cuando_hay_un_solo_episodio_medible(self):
        """Un «rango» construido sobre un caso es ese caso disfrazado de estadística."""
        ini = date(2026, 4, 6)
        self._paro(ini, ini + timedelta(days=6))
        self._llenar(ini - timedelta(days=56), 63, pos=6, neg=2)
        self.db.commit()
        r = shock.respuesta_a_shock(self.db)
        self.assertEqual(r["medibles"], 1)
        self.assertIsNone(r["caida_rango"])
        self.assertTrue(any("no se puede promediar" in a for a in r["avisos"]))

    def test_informa_rango_con_dos_o_mas_episodios_medibles(self):
        for mes in (4, 9):
            ini = date(2026, mes, 6)
            self._paro(ini, ini + timedelta(days=6))
            self._llenar(ini - timedelta(days=56), 63, pos=6, neg=2)
        self.db.commit()
        r = shock.respuesta_a_shock(self.db)
        self.assertEqual(r["medibles"], 2)
        self.assertIsNotNone(r["caida_rango"])

    def test_los_medibles_van_primero(self):
        viejo = date(2022, 5, 2)      # sin corpus alrededor
        nuevo = date(2026, 4, 6)
        self._paro(viejo, viejo + timedelta(days=6))
        self._paro(nuevo, nuevo + timedelta(days=6))
        self._llenar(nuevo - timedelta(days=56), 63, pos=6, neg=2)
        self.db.commit()
        r = shock.respuesta_a_shock(self.db)
        self.assertEqual(r["episodios"][0]["evidencia"], shock.EVIDENCIA_SUFICIENTE)

    def test_avisa_cuantos_episodios_no_se_pueden_medir(self):
        viejo = date(2022, 5, 2)
        self._paro(viejo, viejo + timedelta(days=6))
        self.db.commit()
        r = shock.respuesta_a_shock(self.db)
        self.assertTrue(any("no se pueden medir" in a for a in r["avisos"]))

    def test_avisa_sobre_los_episodios_de_fecha_estimada(self):
        ini = date(2026, 4, 6)
        self._paro(ini, ini + timedelta(days=6), confianza="estimado")
        self.db.commit()
        r = shock.respuesta_a_shock(self.db)
        self.assertTrue(any("ESTIMADAS" in a for a in r["avisos"]))

    def test_solo_confirmados_deja_fuera_las_estimadas(self):
        ini = date(2026, 4, 6)
        self._paro(ini, ini + timedelta(days=6), confianza="estimado")
        self.db.commit()
        self.assertEqual(shock.respuesta_a_shock(self.db, solo_confirmados=True)["total"], 0)
        self.assertEqual(shock.respuesta_a_shock(self.db)["total"], 1)

    def test_sin_episodios_no_revienta(self):
        r = shock.respuesta_a_shock(self.db)
        self.assertEqual(r["episodios"], [])
        self.assertEqual(r["medibles"], 0)

    def test_la_toma_y_el_paro_del_mismo_conflicto_cuentan_como_UN_shock(self):
        """En el calendario van separados —y con razón— pero es una sola interrupción.

        Sin fusionar, los dos episodios medibles del corpus se contaban como cuatro
        con números idénticos, y el resultado parecía tener el doble de evidencia.
        """
        ini = date(2026, 6, 15)
        self.db.add(PercepcionEvento(nombre="Toma Casa Central", tipo="toma",
                                     fecha_inicio=ini, fecha_fin=date(2026, 6, 26),
                                     ambito="Antofagasta", confianza="confirmado"))
        self.db.add(PercepcionEvento(nombre="Paralización general junio-julio", tipo="paro",
                                     fecha_inicio=ini, fecha_fin=date(2026, 7, 3),
                                     ambito="Antofagasta", confianza="confirmado"))
        self._llenar(ini - timedelta(days=56), 120, pos=6, neg=2)
        self.db.commit()
        r = shock.respuesta_a_shock(self.db)
        self.assertEqual(r["total"], 1, "la toma y el paro se contaron dos veces")
        ep = r["episodios"][0]
        self.assertEqual(len(ep["componentes"]), 2)
        # El período es la UNIÓN: hasta el fin del paro, no el de la toma.
        self.assertEqual(ep["hasta"], date(2026, 7, 3))
        self.assertEqual(ep["tipo"], "paro")

    def test_dos_conflictos_separados_en_el_tiempo_NO_se_fusionan(self):
        for mes in (4, 10):
            ini = date(2026, mes, 6)
            self._paro(ini, ini + timedelta(days=6))
        self.db.commit()
        self.assertEqual(shock.respuesta_a_shock(self.db)["total"], 2)

    def test_dos_conflictos_simultaneos_en_SEDES_distintas_no_se_fusionan(self):
        ini = date(2026, 6, 15)
        self._paro(ini, ini + timedelta(days=6), ambito="Antofagasta")
        self._paro(ini, ini + timedelta(days=6), ambito="Coquimbo")
        self.db.commit()
        self.assertEqual(shock.respuesta_a_shock(self.db)["total"], 2)

    def test_el_grupo_hereda_la_confianza_mas_debil(self):
        """Si una parte tiene fechas estimadas, el conjunto tampoco está confirmado."""
        ini = date(2026, 6, 15)
        self._paro(ini, date(2026, 6, 26), confianza="confirmado")
        self._paro(date(2026, 6, 20), date(2026, 7, 3), confianza="estimado")
        self.db.commit()
        r = shock.respuesta_a_shock(self.db)
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["episodios"][0]["confianza"], "estimado")


class TestUmbralesDeC(unittest.TestCase):
    """Los dos umbrales que separan una medición de una casualidad."""

    def setUp(self):
        self.db = _memoria()
        self.ini = date(2026, 4, 6)
        self.fin = date(2026, 4, 12)

    def tearDown(self):
        self.db.close()

    def _dia(self, d: date, *, pos: int, neg: int):
        n = pos + neg
        if n == 0:
            return
        self.db.add(PercepcionHechoDiario(
            fecha=d, campus="Antofagasta", facultad=None, departamento=None,
            tema="academico", n_comentarios=n, n_pos=pos, n_neu=0, n_neg=neg,
            suma_peso=float(n), peso_pos=float(pos), peso_neg=float(neg),
            suma_pos=float(pos), suma_neg=float(neg), suma_ganadora=float(n),
            emociones={"joy": pos}))

    def _episodio(self):
        return {"nombre": "Paro", "tipo": "paro", "desde": self.ini, "hasta": self.fin,
                "ambito": "Antofagasta", "confianza": "confirmado", "dias": 7}

    def test_una_ventana_de_baja_DENSIDAD_no_es_medible(self):
        """28 comentarios en 28 días pasaban el umbral viejo. Es 1 por día.

        Es literalmente lo que hizo que octubre 2024 apareciera con un índice previo
        de 48,2 en un tramo donde toda la serie tenía UNA semana con volumen.
        """
        for i in range(28):
            self._dia(self.ini - timedelta(days=28 - i), pos=1, neg=0)
        for i in range(7):
            self._dia(self.ini + timedelta(days=i), pos=2, neg=6)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertIsNone(p["indice_previo"],
                          "una ventana de ~1 comentario por día no puede ser referencia")

    def test_un_pico_de_una_semana_no_es_recuperacion(self):
        """La serie real post-paro hace 51 → 87 → 85 → 65 → 83 → 68: eso es oscilar."""
        for i in range(28):
            self._dia(self.ini - timedelta(days=28 - i), pos=12, neg=4)   # previo 75
        for i in range(7):
            self._dia(self.ini + timedelta(days=i), pos=4, neg=12)
        # +1 mala, +2 buena (pico), +3 mala otra vez.
        patron = [(4, 12), (12, 4), (4, 12), (4, 12), (4, 12), (4, 12)]
        for k, (pos, neg) in enumerate(patron):
            for i in range(7):
                self._dia(self.fin + timedelta(days=1 + k * 7 + i), pos=pos, neg=neg)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertIsNone(p["recuperado_en_semanas"],
                          "un pico aislado se contó como recuperación")
        self.assertIn("sostuvo", p["motivo_recuperacion"])

    def test_tres_semanas_seguidas_arriba_SI_son_recuperacion(self):
        for i in range(28):
            self._dia(self.ini - timedelta(days=28 - i), pos=12, neg=4)
        for i in range(7):
            self._dia(self.ini + timedelta(days=i), pos=4, neg=12)
        for k in range(6):
            pos, neg = (4, 12) if k == 0 else (12, 4)
            for i in range(7):
                self._dia(self.fin + timedelta(days=1 + k * 7 + i), pos=pos, neg=neg)
        self.db.commit()
        p = shock.perfil_episodio(self.db, self._episodio())
        self.assertEqual(p["recuperado_en_semanas"], 2,
                         "la recuperación empieza donde arranca la racha")


if __name__ == "__main__":
    unittest.main()
