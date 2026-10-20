"""Tests del RESUMEN SEMANAL por LLM del módulo Percepción.

Van en su propio archivo (y no en `test_percepcion.py`, que ya lleva 2.600 líneas)
porque lo que fijan es distinto: acá no se prueba un cálculo, se prueba **cuándo se
paga**.

El requisito del feature es «que solo se corra al cargar los datos». La Torre no se
entera de la ingesta del worker —son procesos separados y su base se abre en modo
`query_only`—, así que eso se implementa con una huella de los datos. Estos tests
son el contrato de esa huella: un estado de los datos, una llamada al LLM. Ni una más.
"""
from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

from sqlalchemy import text, update

from app.services.percepcion import resumen_llm
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionCuenta,
    PercepcionHechoDiario,
    PercepcionPublicacion,
    PercepcionResumenSemanal,
    PercepcionScore,
)
from tests.test_percepcion import _memoria_completa


class TestResumenSemanal(unittest.TestCase):
    def setUp(self):
        self.db = _memoria_completa()
        PercepcionResumenSemanal.__table__.create(self.db.get_bind(), checkfirst=True)
        # Semana del lunes 05/01/2026: una charla en Antofagasta con tres reacciones.
        self.lunes = date(2026, 1, 5)
        self.db.add(PercepcionCuenta(
            id=1, handle="ucn", nombre="UCN", tipo="institucional",
            campus="Antofagasta", facultad="Ingeniería", departamento=None, carrera=None))
        self.db.add(PercepcionPublicacion(
            id=1, cuenta_id=1, external_id="p1",
            fecha_publicacion=datetime(2026, 1, 6), tipo="post",
            caption="Charla magistral de robótica en el Campus Antofagasta",
            n_comentarios=3, n_likes=40))
        for i, (texto, sent) in enumerate(
            [("excelente charla", "POS"), ("muy buena", "POS"), ("no me convencio", "NEG")],
            start=1,
        ):
            self.db.add(PercepcionComentario(
                id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"hash{i}",
                texto=texto, fecha_comentario=datetime(2026, 1, 6, 12), idioma="es",
                n_likes=2, tema="academico", tema_confianza=0.9))
            self.db.add(PercepcionScore(
                id=i, comentario_id=i, modelo="test", sentimiento=sent,
                prob_pos=1.0 if sent == "POS" else 0.0, prob_neu=0.0,
                prob_neg=1.0 if sent == "NEG" else 0.0,
                emocion="joy", prob_emocion=0.9))
        self.db.add(PercepcionHechoDiario(
            fecha=date(2026, 1, 6), campus="Antofagasta", facultad="Ingeniería",
            departamento=None, tema="academico", n_comentarios=3, n_pos=2, n_neu=0,
            n_neg=1, suma_peso=3.0, peso_pos=2.0, peso_neg=1.0, suma_pos=2.0,
            suma_neg=1.0, suma_ganadora=3.0, emociones={"joy": 3}))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _alcance(self, **kw):
        base = dict(semana_inicio=self.lunes, nivel="campus", dimension="Antofagasta")
        base.update(kw)
        return base

    # ------------------------------------------------------------------ #
    # Insumos: el paquete determinista que se le entrega al redactor.
    # ------------------------------------------------------------------ #
    def test_los_insumos_traen_periodo_temas_y_publicaciones(self):
        ins = resumen_llm.insumos_semana(self.db, **self._alcance())
        self.assertEqual(ins["periodo"]["desde"], self.lunes)
        self.assertEqual(ins["n_comentarios"], 3)
        self.assertTrue(any(t["tema"] == "academico" for t in ins["temas"]))
        # La CAPTION es la que cuenta qué pasó. Los comentarios miden 43 caracteres
        # promedio ("💚", "felicidades"): son la reacción, no el hecho.
        self.assertIn("robótica", ins["publicaciones"][0]["caption"])
        self.assertEqual(ins["publicaciones"][0]["n_comentarios_en_la_semana"], 3)

    def test_las_cifras_de_publicacion_cierran_con_el_total_de_la_semana(self):
        """Regresión: se mandaba el contador HISTÓRICO del post, no el de la semana.

        Medido sobre la semana del 20/07/2026: total semanal 151, y las publicaciones
        que se le pasaban al modelo sumaban 337 — una sola decía 252. El modelo
        escribió obedientemente "reunió 252 comentarios" en un texto que decía 151.
        Nadie inventó nada: el insumo era incoherente. Y una cifra que no cierra con
        otra del mismo párrafo tira abajo la credibilidad de todo el tablero.
        """
        # El post ya trae 999 en su contador histórico de Instagram...
        self.db.execute(update(PercepcionPublicacion)
                        .where(PercepcionPublicacion.id == 1)
                        .values(n_comentarios=999))
        # ...y un comentario MUY viejo, que no es de esta semana.
        self.db.add(PercepcionComentario(
            id=99, publicacion_id=1, external_id="viejo", autor_hash="hx",
            texto="de otra semana", fecha_comentario=datetime(2025, 6, 1),
            idioma="es", n_likes=0, tema="academico", tema_confianza=0.5))
        self.db.commit()

        ins = resumen_llm.insumos_semana(self.db, **self._alcance())
        suma = sum(p["n_comentarios_en_la_semana"] for p in ins["publicaciones"])
        self.assertEqual(suma, ins["n_comentarios"],
                         "las publicaciones no suman el total de la semana")
        self.assertNotIn("999", json.dumps(ins, ensure_ascii=False, default=str),
                         "el contador histórico del post se filtró al prompt")

    def test_entra_un_post_viejo_que_recibe_comentarios_esta_semana(self):
        """Un post del domingo anterior que explota el lunes ES de esta semana.

        Filtrar por fecha de PUBLICACIÓN lo dejaba afuera, y con él la explicación de
        por qué se disparó la conversación.
        """
        self.db.add(PercepcionPublicacion(
            id=2, cuenta_id=1, external_id="p2",
            fecha_publicacion=datetime(2025, 12, 30),  # publicado semanas antes
            tipo="post", caption="Convocatoria antigua que volvio a moverse",
            n_comentarios=1, n_likes=0))
        for i in (201, 202):
            self.db.add(PercepcionComentario(
                id=i, publicacion_id=2, external_id=f"c{i}", autor_hash=f"h{i}",
                texto="reflote", fecha_comentario=datetime(2026, 1, 7, 9),
                idioma="es", n_likes=0, tema="academico", tema_confianza=0.5))
            self.db.add(PercepcionScore(
                id=i, comentario_id=i, modelo="test", sentimiento="POS",
                prob_pos=1.0, prob_neu=0.0, prob_neg=0.0, emocion="joy",
                prob_emocion=0.9))
        self.db.commit()

        ins = resumen_llm.insumos_semana(self.db, **self._alcance())
        captions = [p["caption"] for p in ins["publicaciones"]]
        self.assertTrue(any("volvio a moverse" in c for c in captions),
                        "un post viejo con actividad esta semana quedó invisible")

    def test_los_conteos_los_pone_el_agregado_no_el_llm(self):
        """El LLM interpreta, no cuenta. Si contara, se equivocaría y nadie lo vería."""
        ins = resumen_llm.insumos_semana(self.db, **self._alcance())
        tema = next(t for t in ins["temas"] if t["tema"] == "academico")
        self.assertEqual(tema["n_comentarios"], 3)
        self.assertEqual(ins["distribucion"], {"positivo": 2, "neutral": 0, "negativo": 1})

    def test_una_semana_sin_datos_no_arma_insumos(self):
        self.assertIsNone(
            resumen_llm.insumos_semana(self.db, **self._alcance(semana_inicio=date(2025, 3, 3)))
        )

    def test_el_alcance_filtra_por_sede(self):
        self.assertIsNone(
            resumen_llm.insumos_semana(self.db, **self._alcance(dimension="Coquimbo")),
            "Coquimbo no comentó esa semana; no hay nada que resumir",
        )

    # ------------------------------------------------------------------ #
    # Anti-PII: el contrato duro de todo el módulo.
    # ------------------------------------------------------------------ #
    def test_nunca_viajan_textos_de_comentarios_al_llm(self):
        """Las captions son de la UCN; los comentarios son de terceros.

        Mandar los comentarios a OpenAI sería exportarlos, y encima no haría falta:
        los conteos ya vienen exactos del agregado.
        """
        crudo = json.dumps(
            resumen_llm.insumos_semana(self.db, **self._alcance()),
            ensure_ascii=False, default=str,
        )
        for texto in ("excelente charla", "muy buena", "no me convencio"):
            self.assertNotIn(texto, crudo)
        self.assertNotIn("hash1", crudo)

    # ------------------------------------------------------------------ #
    # La huella: la señal de "hay datos nuevos".
    # ------------------------------------------------------------------ #
    def test_la_huella_es_estable_entre_corridas(self):
        a = resumen_llm.huella(resumen_llm.insumos_semana(self.db, **self._alcance()))
        b = resumen_llm.huella(resumen_llm.insumos_semana(self.db, **self._alcance()))
        self.assertEqual(a, b, "sin datos nuevos la huella NO puede moverse")

    def test_la_huella_cambia_cuando_entra_un_comentario(self):
        antes = resumen_llm.huella(resumen_llm.insumos_semana(self.db, **self._alcance()))
        self._ingestar_mas()
        despues = resumen_llm.huella(resumen_llm.insumos_semana(self.db, **self._alcance()))
        self.assertNotEqual(antes, despues)

    def test_la_huella_cambia_al_cambiar_de_modelo(self):
        """Sin esto, bajar de Opus a Haiku dejaba en pantalla el texto de Opus."""
        ins = resumen_llm.insumos_semana(self.db, **self._alcance())
        self.assertNotEqual(
            resumen_llm.huella(ins, modelo="claude-opus-5"),
            resumen_llm.huella(ins, modelo="claude-haiku-4-5"),
        )

    def test_la_huella_cambia_al_corregir_el_prompt(self):
        """Una regla nueva no sirve de nada si los textos viejos no se rehacen."""
        ins = resumen_llm.insumos_semana(self.db, **self._alcance())
        antes = resumen_llm.huella(ins, modelo="m")
        with mock.patch.object(resumen_llm, "INSTRUCCIONES",
                               resumen_llm.INSTRUCCIONES + "\n11) Regla nueva."):
            despues = resumen_llm.huella(ins, modelo="m")
        self.assertNotEqual(antes, despues)

    def _ingestar_mas(self):
        """Simula una ingesta del worker sobre esa semana."""
        self.db.execute(
            update(PercepcionHechoDiario)
            .where(PercepcionHechoDiario.fecha == date(2026, 1, 6))
            .values(n_comentarios=9, n_pos=8, suma_pos=8.0, suma_peso=9.0,
                    suma_ganadora=9.0)
        )
        self.db.commit()

    # ------------------------------------------------------------------ #
    # El caché: acá se decide el gasto.
    # ------------------------------------------------------------------ #
    def _con_llm(self, texto="Resumen de prueba."):
        llamadas: list = []

        def _fake(insumos):
            llamadas.append(insumos)
            return {"texto": texto, "modelo": "gpt-test", "input_tokens": 1000,
                    "output_tokens": 200, "costo_usd": 0.0013}

        return llamadas, mock.patch.object(resumen_llm, "_redactar", _fake)

    def test_la_primera_vez_genera_y_guarda(self):
        llamadas, parche = self._con_llm()
        with parche:
            r = resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
        self.assertEqual(len(llamadas), 1)
        self.assertEqual(r["texto"], "Resumen de prueba.")
        self.assertFalse(r["desde_cache"])
        self.assertEqual(self.db.query(PercepcionResumenSemanal).count(), 1)

    def test_la_segunda_vez_NO_llama_al_llm(self):
        """El test que justifica la tabla entera: sin datos nuevos, gasto CERO."""
        llamadas, parche = self._con_llm()
        with parche:
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
            r = resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
        self.assertEqual(len(llamadas), 1, "se pagó dos veces por los mismos datos")
        self.assertTrue(r["desde_cache"])
        self.assertEqual(r["texto"], "Resumen de prueba.")

    def test_si_entran_datos_nuevos_se_regenera(self):
        llamadas, parche = self._con_llm()
        with parche:
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
            self._ingestar_mas()
            r = resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
        self.assertEqual(len(llamadas), 2, "llegaron datos nuevos y no se regeneró")
        self.assertFalse(r["desde_cache"])
        # Una fila por (semana, alcance): se ACTUALIZA, no se acumula historia.
        self.assertEqual(self.db.query(PercepcionResumenSemanal).count(), 1)

    def test_cada_sede_tiene_su_propia_fila(self):
        self.db.add(PercepcionHechoDiario(
            fecha=date(2026, 1, 7), campus="Coquimbo", facultad=None, departamento=None,
            tema="academico", n_comentarios=5, n_pos=4, n_neu=0, n_neg=1,
            suma_peso=5.0, peso_pos=4.0, peso_neg=1.0, suma_pos=4.0, suma_neg=1.0,
            suma_ganadora=5.0, emociones={"joy": 5}))
        self.db.commit()
        llamadas, parche = self._con_llm()
        with parche:
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance(dimension="Coquimbo"))
        self.assertEqual(len(llamadas), 2)
        self.assertEqual(self.db.query(PercepcionResumenSemanal).count(), 2)

    def test_una_semana_vacia_no_gasta_un_solo_token(self):
        llamadas, parche = self._con_llm()
        with parche:
            r = resumen_llm.resumen_semanal(
                self.db, self.db, **self._alcance(semana_inicio=date(2025, 3, 3)))
        self.assertEqual(len(llamadas), 0)
        self.assertFalse(r["hay_datos"])
        self.assertIsNone(r["texto"])

    def test_sin_api_key_degrada_con_aviso_y_no_revienta(self):
        def _sin_key(_insumos):
            raise resumen_llm.ResumenNoDisponible("falta OPENAI_API_KEY")

        with mock.patch.object(resumen_llm, "_redactar", _sin_key):
            r = resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
        self.assertIsNone(r["texto"])
        self.assertIn("OPENAI_API_KEY", r["aviso"])
        self.assertTrue(r["hay_datos"], "los datos existen; lo que falta es el redactor")

    def test_un_fallo_del_llm_no_borra_el_resumen_anterior(self):
        """Degradar tiene que devolver lo último bueno, no dejar la pantalla en blanco."""
        llamadas, parche = self._con_llm(texto="El resumen bueno.")
        with parche:
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
        self._ingestar_mas()

        def _explota(_insumos):
            raise resumen_llm.ResumenNoDisponible("OpenAI caído")

        with mock.patch.object(resumen_llm, "_redactar", _explota):
            r = resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
        self.assertEqual(r["texto"], "El resumen bueno.")
        self.assertTrue(r["desactualizado"], "hay que avisar que no refleja lo último")
        self.assertIn("OpenAI caído", r["aviso"])

    def test_forzar_regenera_aunque_la_huella_coincida(self):
        llamadas, parche = self._con_llm()
        with parche:
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance(forzar=True))
        self.assertEqual(len(llamadas), 2)

    def test_se_guarda_el_costo_de_cada_generacion(self):
        """«Cuánto gasta esto por semana» tiene que poder contestarse por período."""
        _llamadas, parche = self._con_llm()
        with parche:
            resumen_llm.resumen_semanal(self.db, self.db, **self._alcance())
        fila = self.db.query(PercepcionResumenSemanal).one()
        self.assertEqual(fila.input_tokens, 1000)
        self.assertEqual(fila.output_tokens, 200)
        self.assertAlmostEqual(fila.costo_usd, 0.0013)
        self.assertEqual(fila.modelo, "gpt-test")

    # ------------------------------------------------------------------ #
    # Anclaje temporal.
    # ------------------------------------------------------------------ #
    def test_la_ultima_semana_se_deduce_de_los_datos_no_del_reloj(self):
        """Anclar a `hoy` daría una semana vacía apenas el worker se atrasa un día."""
        self.assertEqual(resumen_llm.ultima_semana(self.db), self.lunes)

    def test_sin_semana_explicita_resume_la_ultima_con_datos(self):
        llamadas, parche = self._con_llm()
        with parche:
            r = resumen_llm.resumen_semanal(self.db, self.db, nivel="campus",
                                            dimension="Antofagasta")
        self.assertEqual(len(llamadas), 1)
        self.assertEqual(r["periodo"]["desde"], self.lunes)


class TestUnidadesDestacadas(unittest.TestCase):
    """Lo que hace que un resumen global no sea un promedio que tapa.

    Si una sede se desploma y otra sube, el índice institucional no se mueve. Sin
    este bloque el resumen diría "semana estable", que es literalmente falso.
    """

    def setUp(self):
        self.db = _memoria_completa()
        PercepcionResumenSemanal.__table__.create(self.db.get_bind(), checkfirst=True)
        self.lunes = date(2026, 1, 5)

    def tearDown(self):
        self.db.close()

    def _hecho(self, dia: date, *, campus=None, facultad=None, departamento=None,
               n_pos=0, n_neu=0, n_neg=0):
        n = n_pos + n_neu + n_neg
        self.db.add(PercepcionHechoDiario(
            fecha=dia, campus=campus, facultad=facultad, departamento=departamento,
            tema="academico", n_comentarios=n, n_pos=n_pos, n_neu=n_neu, n_neg=n_neg,
            suma_peso=float(n), peso_pos=float(n_pos), peso_neg=float(n_neg),
            suma_pos=float(n_pos), suma_neg=float(n_neg), suma_ganadora=float(n),
            emociones={"joy": n_pos, "anger": n_neg}))

    def _destacadas(self):
        ins = resumen_llm.insumos_semana(self.db, semana_inicio=self.lunes, nivel="global")
        return ins["unidades_destacadas"] if ins else []

    def test_el_promedio_estable_no_esconde_dos_sedes_que_se_cruzaron(self):
        """El caso que motiva todo el bloque: global plano, sedes en direcciones opuestas."""
        anterior = self.lunes - timedelta(days=5)
        # Semana previa: A muy bien, B muy mal.
        self._hecho(anterior, campus="Antofagasta", n_pos=18, n_neg=2)
        self._hecho(anterior, campus="Coquimbo", n_pos=2, n_neg=18)
        # Esta semana: se dan vuelta. El índice global queda igual.
        self._hecho(self.lunes + timedelta(days=1), campus="Antofagasta", n_pos=2, n_neg=18)
        self._hecho(self.lunes + timedelta(days=1), campus="Coquimbo", n_pos=18, n_neg=2)
        self.db.commit()

        ins = resumen_llm.insumos_semana(self.db, semana_inicio=self.lunes, nivel="global")
        anterior_g = ins["semana_anterior"]
        self.assertAlmostEqual(ins["indice"], anterior_g["indice"], places=6,
                               msg="el escenario exige que el global NO se mueva")

        nombres = {u["nombre"]: u for u in ins["unidades_destacadas"]}
        self.assertIn("Antofagasta", nombres)
        self.assertIn("Coquimbo", nombres)
        self.assertLess(nombres["Antofagasta"]["delta_indice"], 0)
        self.assertGreater(nombres["Coquimbo"]["delta_indice"], 0)

    def test_una_unidad_que_no_se_movio_no_se_menciona(self):
        for dia in (self.lunes - timedelta(days=5), self.lunes + timedelta(days=1)):
            self._hecho(dia, campus="Antofagasta", n_pos=10, n_neu=2)
        self.db.commit()
        self.assertEqual(self._destacadas(), [])

    def test_no_se_menciona_una_unidad_por_debajo_del_piso(self):
        """Con 1 comentario, un solo comentario mueve el índice entero: es ruido."""
        self._hecho(self.lunes + timedelta(days=1), campus="Coquimbo", n_neg=1)
        self._hecho(self.lunes + timedelta(days=1), campus="Antofagasta", n_pos=20)
        self.db.commit()
        self.assertNotIn("Coquimbo", {u["nombre"] for u in self._destacadas()})

    def test_la_concentracion_de_negativos_se_menciona_aunque_nada_se_haya_movido(self):
        self._hecho(self.lunes + timedelta(days=1), facultad="Ingeniería", n_pos=5, n_neg=4)
        self.db.commit()
        u = next(x for x in self._destacadas() if x["nombre"] == "Ingeniería")
        self.assertIn("negativos", u["motivo"])
        self.assertEqual(u["nivel"], "facultad")

    def test_una_unidad_nueva_se_marca_como_aparicion(self):
        self._hecho(self.lunes + timedelta(days=1), departamento="Depto Química",
                    n_pos=6, n_neu=1)
        self.db.commit()
        u = next(x for x in self._destacadas() if x["nombre"] == "Depto Química")
        self.assertIn("aparece", u["motivo"])
        self.assertEqual(u["nivel"], "departamento")

    def test_la_evidencia_insuficiente_viaja_al_prompt(self):
        """El redactor tiene que poder modular el verbo; sin este flag, afirma de más."""
        self._hecho(self.lunes + timedelta(days=1), campus="Coquimbo", n_pos=6, n_neg=3)
        self.db.commit()
        u = next(x for x in self._destacadas() if x["nombre"] == "Coquimbo")
        self.assertFalse(u["evidencia_suficiente"], "9 comentarios no son 30")

    def test_en_un_alcance_de_sede_no_se_comparan_sedes(self):
        """Con la sede ya fijada, comparar sedes es compararla consigo misma."""
        self._hecho(self.lunes + timedelta(days=1), campus="Antofagasta", n_pos=20, n_neg=5)
        self.db.commit()
        ins = resumen_llm.insumos_semana(self.db, semana_inicio=self.lunes,
                                         nivel="campus", dimension="Antofagasta")
        self.assertEqual(ins["unidades_destacadas"], [])

    def test_el_tope_evita_que_el_resumen_sea_un_ranking(self):
        for i in range(12):
            self._hecho(self.lunes + timedelta(days=1), departamento=f"Depto {i}",
                        n_pos=6, n_neg=4)
        self.db.commit()
        self.assertLessEqual(len(self._destacadas()), resumen_llm.MAX_UNIDADES_DESTACADAS)


class TestSemanasDisponibles(unittest.TestCase):
    """El catálogo que alimenta la navegación ← → del bloque.

    El front no puede adivinar a qué semanas puede ir: si ofreciera un rango de
    fechas libre, la mayoría de los saltos caerían en semanas sin un solo comentario
    y el usuario vería el empty-state una y otra vez sin entender por qué.
    """

    def setUp(self):
        self.db = _memoria_completa()
        PercepcionResumenSemanal.__table__.create(self.db.get_bind(), checkfirst=True)
        # Tres semanas con datos, y un HUECO deliberado en la del 12/01.
        for dia, n in ((date(2026, 1, 6), 3), (date(2026, 1, 21), 7),
                       (date(2026, 1, 27), 5)):
            self.db.add(PercepcionHechoDiario(
                fecha=dia, campus="Antofagasta", facultad=None, departamento=None,
                tema="academico", n_comentarios=n, n_pos=n, n_neu=0, n_neg=0,
                suma_peso=float(n), peso_pos=float(n), peso_neg=0.0,
                suma_pos=float(n), suma_neg=0.0, suma_ganadora=float(n),
                emociones={"joy": n}))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_lista_las_semanas_con_datos_de_la_mas_nueva_a_la_mas_vieja(self):
        semanas = resumen_llm.semanas_disponibles(self.db)
        self.assertEqual([s["semana"] for s in semanas],
                         [date(2026, 1, 26), date(2026, 1, 19), date(2026, 1, 5)])

    def test_no_lista_semanas_sin_un_solo_comentario(self):
        """Un hueco en la ingesta no debe aparecer como una semana navegable."""
        self.assertNotIn(date(2026, 1, 12),
                         [s["semana"] for s in resumen_llm.semanas_disponibles(self.db)])

    def test_cada_semana_trae_su_volumen(self):
        por_semana = {s["semana"]: s["n_comentarios"]
                      for s in resumen_llm.semanas_disponibles(self.db)}
        self.assertEqual(por_semana[date(2026, 1, 5)], 3)
        self.assertEqual(por_semana[date(2026, 1, 19)], 7)

    def test_marca_cuales_ya_tienen_resumen_escrito(self):
        """Para que la UI distinga navegar (gratis) de generar (cuesta)."""
        self.db.add(PercepcionResumenSemanal(
            semana_inicio=date(2026, 1, 19), nivel="global", dimension="",
            huella="h", texto="ya escrito", modelo="m"))
        self.db.commit()
        estado = {s["semana"]: s["tiene_resumen"]
                  for s in resumen_llm.semanas_disponibles(self.db)}
        self.assertTrue(estado[date(2026, 1, 19)])
        self.assertFalse(estado[date(2026, 1, 5)])

    def test_un_resumen_de_OTRO_alcance_no_marca_la_semana_global(self):
        self.db.add(PercepcionResumenSemanal(
            semana_inicio=date(2026, 1, 19), nivel="campus", dimension="Antofagasta",
            huella="h", texto="de una sede", modelo="m"))
        self.db.commit()
        estado = {s["semana"]: s["tiene_resumen"]
                  for s in resumen_llm.semanas_disponibles(self.db)}
        self.assertFalse(estado[date(2026, 1, 19)])

    def test_el_limite_recorta_por_las_mas_recientes(self):
        semanas = resumen_llm.semanas_disponibles(self.db, limite=2)
        self.assertEqual([s["semana"] for s in semanas],
                         [date(2026, 1, 26), date(2026, 1, 19)])

    def test_sin_datos_devuelve_lista_vacia_y_no_revienta(self):
        vacia = _memoria_completa()
        try:
            self.assertEqual(resumen_llm.semanas_disponibles(vacia), [])
        finally:
            vacia.close()


class TestGuardarrailDeCifras(unittest.TestCase):
    """El prompt PROHÍBE inventar cifras. Medido: igual pasa ~1 de cada 10 corridas.

    Pedirlo no alcanza; hay que verificarlo. Y se puede verificar barato, porque todo
    número legítimo está en los insumos. La comprobación es sintáctica a propósito:
    preguntarle a otro modelo si el texto está bien sería tapar un problema de
    confiabilidad con más de lo mismo.
    """

    def setUp(self):
        self.db = _memoria_completa()
        PercepcionResumenSemanal.__table__.create(self.db.get_bind(), checkfirst=True)
        self.lunes = date(2026, 1, 5)
        self.db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN",
                                     tipo="institucional", campus="Antofagasta",
                                     facultad=None, departamento=None, carrera=None))
        self.db.add(PercepcionPublicacion(
            id=1, cuenta_id=1, external_id="p1", fecha_publicacion=datetime(2026, 1, 6),
            tipo="post", caption="Charla", n_comentarios=3, n_likes=0))
        for i, sent in enumerate(["POS", "POS", "NEG"], start=1):
            self.db.add(PercepcionComentario(
                id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}",
                texto="x", fecha_comentario=datetime(2026, 1, 6, 12), idioma="es",
                n_likes=0, tema="academico", tema_confianza=0.9))
            self.db.add(PercepcionScore(
                id=i, comentario_id=i, modelo="t", sentimiento=sent,
                prob_pos=1.0 if sent == "POS" else 0.0, prob_neu=0.0,
                prob_neg=1.0 if sent == "NEG" else 0.0, emocion="joy", prob_emocion=0.9))
        self.db.add(PercepcionHechoDiario(
            fecha=date(2026, 1, 6), campus="Antofagasta", facultad=None,
            departamento=None, tema="academico", n_comentarios=3, n_pos=2, n_neu=0,
            n_neg=1, suma_peso=3.0, peso_pos=2.0, peso_neg=1.0, suma_pos=2.0,
            suma_neg=1.0, suma_ganadora=3.0, emociones={"joy": 3}))
        self.db.commit()
        self.ins = resumen_llm.insumos_semana(self.db, semana_inicio=self.lunes,
                                              nivel="global")

    def tearDown(self):
        self.db.close()

    def test_las_cifras_de_los_insumos_pasan(self):
        texto = "Se registraron 3 comentarios: 2 positivos y 1 negativo."
        self.assertEqual(resumen_llm.cifras_no_justificadas(texto, self.ins), [])

    def test_una_cifra_que_no_esta_en_los_datos_se_detecta(self):
        texto = "Se registraron 3 comentarios y la publicación reunió 252."
        self.assertIn("252.0", resumen_llm.cifras_no_justificadas(texto, self.ins))

    def test_el_redondeo_no_cuenta_como_invento(self):
        """"58,7" citado como "59" es la misma cifra, no una inventada."""
        indice = self.ins["indice"]
        self.assertIsNotNone(indice)
        texto = f"El índice fue de {round(indice)} puntos."
        self.assertEqual(resumen_llm.cifras_no_justificadas(texto, self.ins), [])

    def test_las_fechas_del_periodo_son_citables(self):
        texto = "Entre el 5 y el 11 de enero de 2026 hubo 3 comentarios."
        self.assertEqual(resumen_llm.cifras_no_justificadas(texto, self.ins), [])

    def test_reintenta_una_vez_cuando_detecta_una_cifra_inventada(self):
        salidas = [
            {"texto": "Hubo 3 comentarios y 999 menciones.", "modelo": "m",
             "input_tokens": 100, "output_tokens": 10, "costo_usd": 0.001},
            {"texto": "Hubo 3 comentarios.", "modelo": "m",
             "input_tokens": 100, "output_tokens": 10, "costo_usd": 0.001},
        ]
        llamadas = []

        def _fake(_ins):
            llamadas.append(1)
            return salidas[len(llamadas) - 1]

        with mock.patch.object(resumen_llm, "_redactar", _fake):
            r = resumen_llm._generar_verificado(self.ins)
        self.assertEqual(len(llamadas), 2, "no reintentó ante una cifra inventada")
        self.assertEqual(r["texto"], "Hubo 3 comentarios.")
        self.assertEqual(r["cifras_dudosas"], [])
        # Se pagaron las DOS llamadas: el costo guardado tiene que decir la verdad.
        self.assertAlmostEqual(r["costo_usd"], 0.002)

    def test_no_reintenta_si_el_primer_texto_ya_es_limpio(self):
        llamadas = []

        def _fake(_ins):
            llamadas.append(1)
            return {"texto": "Hubo 3 comentarios.", "modelo": "m", "input_tokens": 1,
                    "output_tokens": 1, "costo_usd": 0.001}

        with mock.patch.object(resumen_llm, "_redactar", _fake):
            resumen_llm._generar_verificado(self.ins)
        self.assertEqual(len(llamadas), 1, "pagó un reintento sin necesitarlo")

    def test_si_el_reintento_tambien_falla_se_publica_con_advertencia(self):
        """Colgar el bloque esperando un texto perfecto es peor que advertir."""
        def _fake(_ins):
            return {"texto": "Hubo 3 comentarios y 999 menciones.", "modelo": "m",
                    "input_tokens": 1, "output_tokens": 1, "costo_usd": 0.001}

        with mock.patch.object(resumen_llm, "_redactar", _fake):
            r = resumen_llm.resumen_semanal(self.db, self.db, semana_inicio=self.lunes,
                                            nivel="global")
        self.assertIn("999.0", r["cifras_dudosas"])
        self.assertIsNotNone(r["texto"], "se perdió un texto por el que ya se pagó")
        self.assertIn("no están en los datos", r["aviso"])


class TestUnicidadDelCache(unittest.TestCase):
    """Regresión: el caché llegó a guardar DOS filas del mismo alcance.

    Observado en la base real: dos filas de (2026-08-17, global, NULL) con la MISMA
    huella, separadas por 54 ms. O sea, dos generaciones pagadas por los mismos datos
    — exactamente lo que este feature promete evitar. Pasa con dos requests
    concurrentes: ambas miran el caché, ninguna encuentra nada, las dos generan.
    """

    def setUp(self):
        self.db = _memoria_completa()
        PercepcionResumenSemanal.__table__.create(self.db.get_bind(), checkfirst=True)
        self.lunes = date(2026, 1, 5)

    def tearDown(self):
        self.db.close()

    def _fila(self, **kw):
        base = dict(semana_inicio=self.lunes, nivel="global", dimension="",
                    huella="h", texto="t", modelo="m", input_tokens=1,
                    output_tokens=1, costo_usd=0.001, generado_en=datetime(2026, 1, 6))
        base.update(kw)
        f = PercepcionResumenSemanal(**base)
        self.db.add(f)
        return f

    def test_la_base_rechaza_dos_filas_del_mismo_alcance(self):
        from sqlalchemy.exc import IntegrityError

        self._fila()
        self.db.commit()
        self._fila()
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_el_alcance_global_guarda_cadena_vacia_no_null(self):
        """Con NULL el UNIQUE no protege: en SQL `NULL != NULL`."""
        self.assertEqual(resumen_llm._clave_dimension(None), "")
        self.assertEqual(resumen_llm._clave_dimension(""), "")
        self.assertEqual(resumen_llm._clave_dimension("Antofagasta"), "Antofagasta")

    def test_dos_alcances_distintos_si_conviven(self):
        self._fila(nivel="global", dimension="")
        self._fila(nivel="campus", dimension="Antofagasta")
        self._fila(nivel="campus", dimension="Coquimbo")
        self.db.commit()
        self.assertEqual(self.db.query(PercepcionResumenSemanal).count(), 3)

    def _tabla_legacy(self):
        """Recrea la tabla como estaba ANTES del fix: `dimension` nullable, sin único.

        Es la forma real que hoy tiene la base del worker, así que los dos tests de
        abajo prueban el estado que existe en producción, no uno hipotético.
        """
        self.db.execute(text("DROP TABLE percepcion_resumen_semanal"))
        self.db.execute(text(
            "CREATE TABLE percepcion_resumen_semanal ("
            " id INTEGER PRIMARY KEY, semana_inicio DATE, nivel VARCHAR(20),"
            " dimension VARCHAR(160), huella VARCHAR(64), texto TEXT,"
            " modelo VARCHAR(120), input_tokens INTEGER, output_tokens INTEGER,"
            " costo_usd FLOAT, generado_en DATETIME)"
        ))
        self.db.commit()

    def test_con_duplicados_heredados_gana_el_mas_reciente(self):
        """Sin orden explícito el caché devolvería cualquiera — a veces el texto viejo."""
        self._tabla_legacy()
        self.db.execute(text(
            "INSERT INTO percepcion_resumen_semanal "
            "(semana_inicio, nivel, dimension, huella, texto, modelo) VALUES "
            "('2026-01-05','global','','h','viejo','m'),"
            "('2026-01-05','global','','h','nuevo','m')"
        ))
        self.db.commit()
        self.assertEqual(resumen_llm._fila(self.db, self.lunes, "global", None).texto,
                         "nuevo")

    def test_una_fila_heredada_con_null_se_sigue_encontrando(self):
        """Si la normalización no pudo correr, el caché no debe romperse ni repagar."""
        self._tabla_legacy()
        self.db.execute(text(
            "INSERT INTO percepcion_resumen_semanal "
            "(semana_inicio, nivel, dimension, huella, texto, modelo) VALUES "
            "('2026-01-05','global',NULL,'h','heredado','m')"
        ))
        self.db.commit()
        fila = resumen_llm._fila(self.db, self.lunes, "global", None)
        self.assertIsNotNone(fila, "una fila con dimension NULL quedó invisible")
        self.assertEqual(fila.texto, "heredado")

    def test_la_migracion_normaliza_deduplica_y_hace_unica_la_clave(self):
        """El camino completo sobre una base que YA tenía la tabla vieja con basura."""
        from sqlalchemy.exc import IntegrityError

        self._tabla_legacy()
        self.db.execute(text(
            "INSERT INTO percepcion_resumen_semanal "
            "(semana_inicio, nivel, dimension, huella, texto, modelo) VALUES "
            "('2026-01-05','global',NULL,'h','viejo','m'),"
            "('2026-01-05','global',NULL,'h','nuevo','m'),"
            "('2026-01-05','campus','Antofagasta','h','otro','m')"
        ))
        self.db.commit()

        from app.services.percepcion import db as pdb

        with mock.patch.object(pdb, "percepcion_write_engine", self.db.get_bind()):
            self.assertTrue(pdb._asegurar_unicidad_resumen())

        filas = self.db.execute(text(
            "SELECT nivel, dimension, texto FROM percepcion_resumen_semanal ORDER BY id"
        )).all()
        self.assertEqual(len(filas), 2, "no deduplicó")
        self.assertIn(("global", "", "nuevo"), filas, "conservó el viejo en vez del nuevo")
        self.assertIn(("campus", "Antofagasta", "otro"), filas, "borró un alcance distinto")

        # Y a partir de acá la base RECHAZA el duplicado por sí sola. Un INSERT crudo
        # se ejecuta al toque (no espera al commit), así que el assert va sobre él.
        with self.assertRaises(IntegrityError):
            self.db.execute(text(
                "INSERT INTO percepcion_resumen_semanal "
                "(semana_inicio, nivel, dimension, huella, texto, modelo) VALUES "
                "('2026-01-05','global','','h','tercero','m')"
            ))
        self.db.rollback()

    def test_la_migracion_es_idempotente(self):
        from app.services.percepcion import db as pdb

        with mock.patch.object(pdb, "percepcion_write_engine", self.db.get_bind()):
            self.assertTrue(pdb._asegurar_unicidad_resumen())
            self.assertTrue(pdb._asegurar_unicidad_resumen())


class TestSeleccionDeModelo(unittest.TestCase):
    """El parámetro `effort` no existe en toda la familia Claude.

    `PERCEPCION_RESUMEN_MODELO` está para poder cambiar de modelo sin tocar código.
    Si `output_config.effort` viajara siempre, ese setting rompería el feature con un
    400 apenas alguien pusiera Haiku o Sonnet 4.5 — que es exactamente el caso de uso
    para el que se creó. Estos tests fijan la compatibilidad.
    """

    def test_el_default_es_el_modelo_que_gano_la_comparacion(self):
        self.assertEqual(resumen_llm.MODELO_ANTHROPIC, "claude-haiku-4-5")

    def test_haiku_no_acepta_effort(self):
        self.assertFalse(resumen_llm.soporta_effort("claude-haiku-4-5"))
        self.assertFalse(resumen_llm.soporta_effort("claude-sonnet-4-5"))

    def test_la_familia_opus_y_sonnet_5_si_lo_aceptan(self):
        for modelo in ("claude-opus-5", "claude-sonnet-5", "claude-opus-4-8",
                       "claude-sonnet-4-6", "claude-fable-5"):
            with self.subTest(modelo=modelo):
                self.assertTrue(resumen_llm.soporta_effort(modelo))

    def test_un_modelo_desconocido_no_manda_effort(self):
        """Ante la duda, la opción que no rompe: sin effort la llamada siempre corre."""
        self.assertFalse(resumen_llm.soporta_effort("claude-modelo-que-no-existe"))
        self.assertFalse(resumen_llm.soporta_effort(""))

    def test_los_modelos_usables_tienen_precio_cargado(self):
        """Sin precio, `costo_usd` da 0 y el feature miente sobre lo que gasta."""
        from app.services.costos import PRECIOS_LLM_DEFAULT

        for modelo in ("claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5"):
            with self.subTest(modelo=modelo):
                self.assertIn(modelo, PRECIOS_LLM_DEFAULT)


if __name__ == "__main__":
    unittest.main()
