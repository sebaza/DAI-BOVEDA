"""Fase 3b — la conexión privilegiada (la única que lee texto crudo) está acotada.

Estos tests no necesitan Postgres: fijan por inspección del código QUIÉN puede usar el
motor privilegiado y QUIÉN puede nombrar las columnas crudas (`texto`, `caption`). Si
alguien las usa fuera de la Curación o del resumen semanal, la suite falla.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from app.services.percepcion import db as pdb

APP = Path(__file__).resolve().parents[1] / "app"

# Nombres que dan acceso al rol que SÍ puede leer texto/caption.
PRIVILEGIADOS = ("percepcion_proceso_engine", "PercepcionProcesoSessionLocal",
                 "get_percepcion_proceso_db")

# Quién puede importarlos. `db.py` los define; el router los usa solo en los endpoints
# de curación y en el resumen semanal (ver el test de abajo); `resumen_llm` los usa para
# la tarea posterior a la ingesta.
MODULOS_PRIVILEGIADOS = {
    "services/percepcion/db.py",
    "routers/percepcion.py",
    "services/percepcion/resumen_llm.py",
}

# Quién puede nombrar las columnas crudas. `derivados` las lee para precalcular,
# `curacion` es la cola de revisión de administradores, `resumen_llm` envía captions
# truncadas al modelo y `models` las define.
MODULOS_CON_TEXTO_CRUDO = {
    "services/percepcion/models.py",
    "services/percepcion/derivados.py",
    "services/percepcion/curacion.py",
    "services/percepcion/resumen_llm.py",
}
_PATRON_CRUDO = re.compile(
    r"\b(?:C|P|PercepcionComentario|PercepcionPublicacion)\.(?:texto|caption)\b")


def _fuentes() -> dict[str, str]:
    return {p.relative_to(APP).as_posix(): p.read_text(encoding="utf-8")
            for p in APP.rglob("*.py")}


class TestAlcanceDelMotorPrivilegiado(unittest.TestCase):
    def test_solo_los_modulos_autorizados_lo_nombran(self):
        for ruta, fuente in _fuentes().items():
            if any(n in fuente for n in PRIVILEGIADOS):
                self.assertIn(
                    ruta, MODULOS_PRIVILEGIADOS,
                    f"{ruta} usa el motor privilegiado y no está autorizado: solo la Curación "
                    "(texto crudo) y el resumen semanal (captions) pueden hacerlo.")

    def test_en_el_router_solo_curacion_y_resumen_semanal(self):
        fuente = (APP / "routers/percepcion.py").read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        usan: list[str] = []
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.FunctionDef):
                continue
            if not any(n in (ast.get_source_segment(fuente, nodo) or "") for n in PRIVILEGIADOS):
                continue
            rutas = [ast.literal_eval(d.args[0]) for d in nodo.decorator_list
                     if isinstance(d, ast.Call) and d.args and isinstance(d.args[0], ast.Constant)]
            usan.append(f"{nodo.name} {rutas}")
            self.assertTrue(
                rutas and all(r.startswith(("/curacion/", "/resumen-semanal")) for r in rutas),
                f"el endpoint {nodo.name} {rutas} usa el motor privilegiado y no es de Curación "
                "ni el resumen semanal")
        self.assertTrue(usan, "la Curación debería usar el motor privilegiado para leer texto")

    def test_solo_los_modulos_autorizados_nombran_las_columnas_crudas(self):
        for ruta, fuente in _fuentes().items():
            if _PATRON_CRUDO.search(fuente):
                self.assertIn(
                    ruta, MODULOS_CON_TEXTO_CRUDO,
                    f"{ruta} lee texto/caption: la API normal no tiene permiso sobre esas columnas. "
                    "Usa las tablas derivadas (derivados.py).")

    def test_las_columnas_crudas_son_deferred_en_el_orm(self):
        # Una carga de la entidad (`db.get(C, id)`) no debe pedirlas al servidor.
        from app.services.percepcion.models import PercepcionComentario, PercepcionPublicacion
        self.assertTrue(PercepcionComentario.__mapper__.columns["texto"] is not None)
        self.assertTrue(PercepcionComentario.__mapper__.attrs["texto"].deferred)
        self.assertTrue(PercepcionPublicacion.__mapper__.attrs["caption"].deferred)


class TestUrlPrivilegiada(unittest.TestCase):
    def test_sin_url_propia_cae_a_la_de_la_app(self):
        # Compatibilidad: con una sola variable (PERCEPCION_DATABASE_URL) todo sigue andando.
        self.assertEqual(pdb.resolver_url_proceso("postgresql://app", ""), "postgresql://app")
        self.assertEqual(pdb.resolver_url_proceso("postgresql://app", "  "), "postgresql://app")

    def test_con_url_propia_la_usa(self):
        self.assertEqual(pdb.resolver_url_proceso("postgresql://app", "postgresql://proceso"),
                         "postgresql://proceso")

    def test_el_motor_privilegiado_existe_y_es_de_lectura(self):
        self.assertIsNotNone(pdb.percepcion_proceso_engine)
        # La lectura de texto no necesita escribir: el motor privilegiado es de solo lectura.
        self.assertIsNot(pdb.percepcion_proceso_engine, pdb.percepcion_write_engine)

    def test_configuracion_expone_la_variable(self):
        from app.config import get_settings
        self.assertTrue(hasattr(get_settings(), "percepcion_proceso_database_url"))


if __name__ == "__main__":
    unittest.main()
