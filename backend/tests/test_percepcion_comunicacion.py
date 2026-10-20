"""Tests del efecto de la COMUNICACIÓN (pregunta B del plan de simulación).

El test central es el del confounding: si una característica la usan sobre todo las
cuentas que ya generaban conversación, el efecto crudo la premia sin que la
característica haga nada. Distinguir esos dos casos es la razón de ser del módulo.
"""
from __future__ import annotations

import unittest
from datetime import datetime

from app.services.percepcion import comunicacion
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionCuenta,
    PercepcionPublicacion,
)

from tests.test_percepcion import _memoria_completa


class TestEfectoDeComunicacion(unittest.TestCase):
    def setUp(self):
        self.db = _memoria_completa()
        self._pid = 0
        self._cid = 0
        self._cuentas: dict[str, int] = {}

    def tearDown(self):
        self.db.close()

    def _cuenta(self, nombre: str) -> int:
        if nombre not in self._cuentas:
            cid = len(self._cuentas) + 1
            self.db.add(PercepcionCuenta(
                id=cid, handle=nombre, nombre=nombre, tipo="institucional",
                campus="Antofagasta", facultad=None, departamento=None, carrera=None))
            self._cuentas[nombre] = cid
        return self._cuentas[nombre]

    def _post(self, cuenta: str, *, reel: bool, conversa: bool, caption: str = "hola mundo"):
        self._pid += 1
        self.db.add(PercepcionPublicacion(
            id=self._pid, cuenta_id=self._cuenta(cuenta), external_id=f"p{self._pid}",
            fecha_publicacion=datetime(2026, 3, 4), tipo="reel" if reel else "post",
            caption=caption, n_comentarios=1 if conversa else 0, n_likes=0))
        if conversa:
            self._cid += 1
            self.db.add(PercepcionComentario(
                id=self._cid, publicacion_id=self._pid, external_id=f"c{self._cid}",
                autor_hash=f"h{self._cid}", texto="x",
                fecha_comentario=datetime(2026, 3, 5), idioma="es", n_likes=0,
                tema="academico", tema_confianza=0.5))

    def _rasgo(self, nombre: str):
        r = comunicacion.efecto_de_caracteristicas(self.db)
        return next((f for f in r["caracteristicas"] if f["rasgo"] == nombre), None), r

    # ------------------------------------------------------------------ #
    # El corazón: separar el efecto del formato del efecto de la cuenta.
    # ------------------------------------------------------------------ #
    def test_un_efecto_que_es_de_la_CUENTA_no_se_reporta_como_solido(self):
        """Cuenta A hace solo reels y conversa mucho; B hace solo posts y no.

        En crudo el reel parece funcionar. Pero ninguna cuenta usa los dos formatos,
        así que no hay con qué compararla consigo misma: el efecto NO es sólido.
        """
        for i in range(40):
            self._post("A ruidosa", reel=True, conversa=i < 36)    # 90 %
        for i in range(40):
            self._post("B callada", reel=False, conversa=i < 4)    # 10 %
        self.db.commit()

        f, _ = self._rasgo("es_reel")
        self.assertIsNotNone(f)
        self.assertGreater(f["efecto_crudo"], 50, "el efecto crudo es enorme")
        self.assertEqual(f["cuentas_comparables"], 0, "ninguna cuenta usa ambos")
        self.assertFalse(f["solido"], "sin control intra-cuenta no puede ser sólido")

    def test_un_efecto_REAL_se_sostiene_dentro_de_cada_cuenta(self):
        # Seis cuentas, cada una publica ambos formatos y en todas el reel gana.
        for c in range(6):
            for i in range(10):
                self._post(f"cuenta{c}", reel=False, conversa=i < 2)   # 20 %
            for i in range(10):
                self._post(f"cuenta{c}", reel=True, conversa=i < 8)    # 80 %
        self.db.commit()

        f, _ = self._rasgo("es_reel")
        self.assertEqual(f["cuentas_comparables"], 6)
        self.assertEqual(f["cuentas_a_favor"], 6)
        self.assertGreater(f["efecto_intra"], 50)
        self.assertTrue(f["solido"])

    def test_una_caracteristica_que_no_hace_nada_no_sale_solida(self):
        for c in range(6):
            for i in range(20):
                # La conversación no depende del formato: alterna igual en ambos.
                self._post(f"cuenta{c}", reel=(i % 2 == 0), conversa=(i % 4 < 2))
        self.db.commit()
        f, _ = self._rasgo("es_reel")
        self.assertFalse(f["solido"])

    def test_el_orden_es_por_efecto_INTRA_no_por_el_crudo(self):
        for c in range(6):
            for i in range(10):
                self._post(f"c{c}", reel=False, conversa=i < 2, caption="corto")
            for i in range(10):
                self._post(f"c{c}", reel=True, conversa=i < 9, caption="corto")
        self.db.commit()
        _, r = self._rasgo("es_reel")
        intras = [abs(f["efecto_intra"] or 0) for f in r["caracteristicas"]]
        self.assertEqual(intras, sorted(intras, reverse=True))

    # ------------------------------------------------------------------ #
    # Higiene.
    # ------------------------------------------------------------------ #
    def test_no_usa_nada_que_dependa_de_la_reaccion(self):
        """Likes o comentarios como predictores serían fuga: YA son la reacción."""
        rasgos = comunicacion._caracteristicas("hola", "post", datetime(2026, 3, 4))
        for prohibido in ("like", "comentario", "conversa"):
            self.assertFalse(any(prohibido in k for k in rasgos),
                             f"'{prohibido}' no puede ser un predictor")

    def test_una_caracteristica_con_pocos_casos_no_se_reporta(self):
        for i in range(40):
            self._post("unica", reel=(i < 3), conversa=True)   # 3 reels: muy pocos
        self.db.commit()
        f, _ = self._rasgo("es_reel")
        self.assertIsNone(f, "con 3 casos no se puede afirmar nada")

    def test_la_tasa_base_es_la_proporcion_que_conversa(self):
        for i in range(100):
            self._post("c", reel=False, conversa=i < 30)
        self.db.commit()
        _, r = self._rasgo("es_reel")
        self.assertEqual(r["publicaciones"], 100)
        self.assertEqual(r["con_conversacion"], 30)
        self.assertEqual(r["tasa_base"], 30.0)

    def test_siempre_avisa_que_es_correlacion_y_no_causa(self):
        self.db.commit()
        r = comunicacion.efecto_de_caracteristicas(self.db)
        self.assertTrue(any("no causa" in a for a in r["avisos"]))

    def test_avisa_cuando_un_efecto_crudo_no_sobrevive_al_control(self):
        for i in range(40):
            self._post("A ruidosa", reel=True, conversa=i < 36)
        for i in range(40):
            self._post("B callada", reel=False, conversa=i < 4)
        self.db.commit()
        r = comunicacion.efecto_de_caracteristicas(self.db)
        self.assertTrue(any("quién publica" in a for a in r["avisos"]))

    def test_sin_publicaciones_no_revienta(self):
        r = comunicacion.efecto_de_caracteristicas(self.db)
        self.assertEqual(r["publicaciones"], 0)
        self.assertEqual(r["caracteristicas"], [])

    # ------------------------------------------------------------------ #
    def test_el_test_de_signos_reconoce_lo_unanime_y_lo_parejo(self):
        self.assertLess(comunicacion._p_signos(19, 24), 0.05)
        self.assertGreater(comunicacion._p_signos(13, 24), 0.05)
        self.assertEqual(comunicacion._p_signos(12, 24), 1.0)


if __name__ == "__main__":
    unittest.main()
