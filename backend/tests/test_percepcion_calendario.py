"""Tests de la carga del calendario académico (Fase 0.1 del plan de simulación)."""
from __future__ import annotations

import unittest
from datetime import date

from app.services.percepcion import calendario
from app.services.percepcion.models import PercepcionEvento

from tests.test_percepcion import _memoria


class TestCalendarioUCN(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()

    def tearDown(self):
        self.db.close()

    # ------------------------------------------------------------------ #
    # El archivo.
    # ------------------------------------------------------------------ #
    def test_el_archivo_existe_y_se_lee(self):
        eventos = calendario.leer_calendario()
        self.assertGreater(len(eventos), 50, "el calendario 2022-2026 debería traer decenas")

    def test_todas_las_fechas_son_coherentes(self):
        for e in calendario.leer_calendario():
            with self.subTest(evento=e["nombre"]):
                if e["fecha_fin"] is not None:
                    self.assertGreaterEqual(
                        e["fecha_fin"], e["fecha_inicio"],
                        "un evento no puede terminar antes de empezar")

    def test_todos_los_tipos_son_validos(self):
        from app.services.percepcion.eventos import _TIPOS_VALIDOS

        for e in calendario.leer_calendario():
            with self.subTest(evento=e["nombre"]):
                self.assertIn(e["tipo"], _TIPOS_VALIDOS)

    def test_toda_confianza_es_una_de_las_tres(self):
        validas = {"confirmado", "estimado", "planificado"}
        for e in calendario.leer_calendario():
            with self.subTest(evento=e["nombre"]):
                self.assertIn(e["confianza"], validas)

    def test_los_nombres_entran_en_la_columna(self):
        largo = PercepcionEvento.__table__.c["nombre"].type.length
        for e in calendario.leer_calendario():
            with self.subTest(evento=e["nombre"]):
                self.assertLessEqual(len(e["nombre"]), largo)

    def test_no_hay_dos_eventos_con_la_misma_clave_natural(self):
        """La clave (nombre, fecha_inicio) es la que hace idempotente la carga."""
        claves = [(e["nombre"], e["fecha_inicio"]) for e in calendario.leer_calendario()]
        self.assertEqual(len(claves), len(set(claves)), "hay claves duplicadas en el JSON")

    # ------------------------------------------------------------------ #
    # La carga.
    # ------------------------------------------------------------------ #
    def test_carga_los_eventos(self):
        r = calendario.cargar(self.db)
        self.assertEqual(r["nuevos"], r["en_archivo"])
        self.assertEqual(self.db.query(PercepcionEvento).count(), r["en_archivo"])

    def test_es_idempotente(self):
        calendario.cargar(self.db)
        n = self.db.query(PercepcionEvento).count()
        r = calendario.cargar(self.db)
        self.assertEqual(r["nuevos"], 0, "una segunda carga duplicó eventos")
        self.assertEqual(r["actualizados"], 0)
        self.assertEqual(self.db.query(PercepcionEvento).count(), n)

    def test_el_dry_run_no_escribe(self):
        r = calendario.cargar(self.db, dry_run=True)
        self.assertGreater(r["nuevos"], 0)
        self.assertEqual(self.db.query(PercepcionEvento).count(), 0)

    def test_actualiza_en_vez_de_duplicar_cuando_cambia_una_fecha_de_fin(self):
        """Si la fuente confirma el término de un paro estimado, tiene que llegar."""
        calendario.cargar(self.db)
        # Tiene que ser uno que YA tenga fecha de fin: el paro de 2022 viene sin
        # término documentado, así que borrárselo no sería un cambio.
        ev = self.db.query(PercepcionEvento).filter(
            PercepcionEvento.tipo == "paro",
            PercepcionEvento.fecha_fin.is_not(None)).first()
        self.assertIsNotNone(ev, "el calendario debería traer paros con término")
        ev.fecha_fin = None
        ev.confianza = "estimado"
        self.db.commit()

        r = calendario.cargar(self.db)
        self.assertEqual(r["nuevos"], 0)
        self.assertGreaterEqual(r["actualizados"], 1)

    def test_un_evento_cargado_a_mano_no_se_pisa(self):
        """El ABM del panel sigue funcionando: la carga no borra lo que no es suyo."""
        self.db.add(PercepcionEvento(
            nombre="Algo cargado desde el panel", tipo="otro",
            fecha_inicio=date(2026, 3, 1), ambito="global"))
        self.db.commit()
        calendario.cargar(self.db)
        self.assertIsNotNone(
            self.db.query(PercepcionEvento).filter(
                PercepcionEvento.nombre == "Algo cargado desde el panel").first())

    def test_sincronizar_retira_lo_que_ya_no_esta_en_el_archivo(self):
        """Hizo falta al fusionar los hitos de semestre en un período único.

        Sin esto, los 20 hitos viejos quedaban huérfanos conviviendo con los períodos
        nuevos, y la franja mostraba las dos versiones del mismo semestre.
        """
        calendario.cargar(self.db)
        self.db.add(PercepcionEvento(
            nombre="Hito viejo del calendario", tipo="otro",
            fecha_inicio=date(2024, 5, 5), ambito="global",
            fuente=calendario.FUENTE_CALENDARIO))
        self.db.commit()

        r = calendario.cargar(self.db)
        self.assertEqual(r["retirados"], 1)
        self.assertIsNone(
            self.db.query(PercepcionEvento).filter(
                PercepcionEvento.nombre == "Hito viejo del calendario").first())

    def test_sincronizar_NO_borra_lo_cargado_a_mano(self):
        """El filtro por fuente es lo único que separa limpiar de destruir."""
        calendario.cargar(self.db)
        self.db.add(PercepcionEvento(
            nombre="Marca puesta por una persona", tipo="otro",
            fecha_inicio=date(2024, 5, 5), ambito="global"))  # fuente = NULL
        self.db.commit()

        r = calendario.cargar(self.db)
        self.assertEqual(r["retirados"], 0)
        self.assertIsNotNone(
            self.db.query(PercepcionEvento).filter(
                PercepcionEvento.nombre == "Marca puesta por una persona").first())

    def test_ningun_receso_dura_un_disparate(self):
        """Regresión de un error propio: deducir el fin de TODOS los recesos.

        Al completar los que venían sin `fecha_fin`, un script tocó también los que
        ya lo declaraban: la Pausa Académica 2022 pasó de 5 días a 98, y las Semanas
        de Autocuidado de 6 a 147. Las fechas se veían plausibles una por una; solo
        listar las duraciones juntas lo hizo evidente.
        """
        for e in calendario.leer_calendario():
            if e["tipo"] != "receso" or e["fecha_fin"] is None:
                continue
            dias = (e["fecha_fin"] - e["fecha_inicio"]).days + 1
            with self.subTest(receso=e["nombre"]):
                self.assertGreater(dias, 0)
                # Las vacaciones de verano son las más largas (~91 días). Cualquier
                # cosa por encima de eso es un fin mal deducido, no un receso.
                self.assertLessEqual(
                    dias, 100,
                    f"{e['nombre']} dura {dias} días: se estiró hasta otro período")

    def test_una_semana_de_autocuidado_dura_una_semana(self):
        """El caso concreto que rompió el bug. Nombre y duración tienen que coincidir."""
        semanas = [e for e in calendario.leer_calendario()
                   if "Autocuidado" in e["nombre"] and e["fecha_fin"]]
        self.assertGreaterEqual(len(semanas), 4)
        for e in semanas:
            dias = (e["fecha_fin"] - e["fecha_inicio"]).days + 1
            with self.subTest(evento=e["nombre"]):
                self.assertLessEqual(dias, 10, "una 'semana' de más de 10 días no es una semana")

    def test_los_recesos_con_fin_deducido_quedan_marcados_como_estimados(self):
        """El inicio está documentado; el término lo inferimos. El rango es estimado."""
        deducidos = [e for e in calendario.leer_calendario()
                     if e["tipo"] == "receso" and "DEDUCIDO" in (e["descripcion"] or "")]
        self.assertGreaterEqual(len(deducidos), 5)
        for e in deducidos:
            with self.subTest(receso=e["nombre"]):
                self.assertIn(e["confianza"], {"estimado", "planificado"},
                              "un fin inferido no puede figurar como confirmado")

    def test_un_receso_termina_antes_de_que_empiecen_las_clases(self):
        """La regla que define la deducción: el receso dura hasta que vuelven las clases."""
        eventos = calendario.leer_calendario()
        inicios = sorted(e["fecha_inicio"] for e in eventos if e["tipo"] == "semestre")
        for e in eventos:
            if e["tipo"] != "receso" or not e["fecha_fin"]:
                continue
            siguientes = [i for i in inicios if i > e["fecha_inicio"]]
            if not siguientes:
                continue
            with self.subTest(receso=e["nombre"]):
                self.assertLess(e["fecha_fin"], min(siguientes),
                                "el receso se solapa con el inicio del período lectivo")

    def test_los_semestres_son_periodos_y_no_dos_puntos(self):
        """Lo que informa es el tramo entre inicio y fin, no las dos fechas sueltas."""
        calendario.cargar(self.db)
        semestres = self.db.query(PercepcionEvento).filter(
            PercepcionEvento.tipo == "semestre").all()
        self.assertGreaterEqual(len(semestres), 10, "faltan períodos lectivos")
        for s in semestres:
            with self.subTest(semestre=s.nombre):
                self.assertIsNotNone(s.fecha_fin, "un semestre sin fin es un punto")
                self.assertGreater((s.fecha_fin - s.fecha_inicio).days, 30)

    def test_ya_no_quedan_hitos_sueltos_de_inicio_o_fin_de_semestre(self):
        for e in calendario.leer_calendario():
            with self.subTest(evento=e["nombre"]):
                self.assertNotIn("Inicio de clases", e["nombre"])
                self.assertNotIn("Último día de clases", e["nombre"])

    def test_la_recalendarizacion_queda_como_DOS_periodos(self):
        """El semestre programado y el efectivo son tramos distintos, no un hito."""
        calendario.cargar(self.db)
        nombres = {e.nombre: e for e in self.db.query(PercepcionEvento).all()}
        prog = nombres["I semestre 2026 (programado)"]
        efec = nombres["I semestre 2026 (efectivo Antofagasta)"]
        self.assertEqual(prog.confianza, "planificado")
        self.assertEqual(efec.confianza, "confirmado")
        self.assertGreater(efec.fecha_fin, prog.fecha_fin,
                           "el paro extendió el semestre: el efectivo dura más")

    # ------------------------------------------------------------------ #
    # Los episodios — el insumo de la pregunta C.
    # ------------------------------------------------------------------ #
    def test_los_episodios_disruptivos_cubren_los_paros_conocidos(self):
        calendario.cargar(self.db)
        eps = calendario.episodios_disruptivos(self.db)
        anios = {e["desde"].year for e in eps}
        # La fuente documenta movilizaciones en estos cinco años.
        for anio in (2022, 2023, 2024, 2025, 2026):
            with self.subTest(anio=anio):
                self.assertIn(anio, anios)

    def test_solo_confirmados_deja_fuera_las_fechas_estimadas(self):
        """Medir DURACIÓN con fechas aproximadas mide la suposición, no el hecho."""
        calendario.cargar(self.db)
        todos = calendario.episodios_disruptivos(self.db)
        firmes = calendario.episodios_disruptivos(self.db, solo_confirmados=True)
        self.assertLess(len(firmes), len(todos),
                        "el calendario declara episodios con fechas sin verificar")
        self.assertTrue(all(e["confianza"] == "confirmado" for e in firmes))

    def test_la_toma_y_el_paro_de_2026_son_episodios_distintos(self):
        """El levantamiento de la toma NO terminó el paro: son dos hechos.

        Fusionarlos daría una duración equivocada y borraría el hallazgo de que las
        clases siguieron suspendidas una semana más.
        """
        calendario.cargar(self.db)
        eps = [e for e in calendario.episodios_disruptivos(self.db)
               if e["desde"].year == 2026]
        toma = next(e for e in eps if e["tipo"] == "toma" and e["desde"] == date(2026, 6, 15))
        paro = next(e for e in eps if e["tipo"] == "paro" and e["desde"] == date(2026, 6, 15))
        self.assertEqual(toma["hasta"], date(2026, 6, 26))
        self.assertEqual(paro["hasta"], date(2026, 7, 3))
        self.assertGreater(paro["dias"], toma["dias"])

    # `test_la_recalendarizacion_queda_como_DOS_periodos` reemplaza al test que
    # comparaba los hitos sueltos "Último día de clases 2026 (programado/efectivo)".
    # Esos hitos ya no existen: se fusionaron en períodos lectivos.


if __name__ == "__main__":
    unittest.main()
