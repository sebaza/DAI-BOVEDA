"""Percepción sobre PostgreSQL: las consultas del módulo y el blindaje de solo lectura.

Opt-in: se SALTA sin ``PERCEPCION_TEST_DATABASE_URL`` (ver ``pg_percepcion.py``). Cada test
corre en un esquema descartable ``percepcion_test``; el esquema real nunca se toca.

Qué se cubre y por qué no basta con los tests sobre SQLite:

* SQLite acepta ``SELECT c.nombre ... GROUP BY p.id`` (columna "desnuda"); Postgres lo
  rechaza con ``GroupingError``. Le pasó a ``curacion.publicaciones_a_curar``.
* Postgres devuelve ``Decimal`` para algunas agregaciones; la capa de servicios debe
  entregar ``int``/``float`` nativos.
* ``PRAGMA query_only=ON`` es de SQLite: en Postgres el motor de lectura se blinda con
  ``default_transaction_read_only``.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg.errors
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.services.percepcion import curacion, repository
from app.services.percepcion.db import crear_engine
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionCuenta,
    PercepcionPublicacion,
    PercepcionScore,
)
from pg_percepcion import esquema_efimero, requiere_pg

pytestmark = requiere_pg

HOY = date(2026, 3, 30)


def _sembrar(db) -> None:
    """Dos cuentas, tres publicaciones y 30 comentarios repartidos en 10 días."""
    db.add_all([
        PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="institucional",
                         campus="Antofagasta", facultad="Ingeniería", origen="interno"),
        PercepcionCuenta(id=2, handle="fac", nombre="Facultad", tipo="facultad",
                         campus="Coquimbo", facultad="Ciencias", origen="interno"),
    ])
    for pid, cuenta in ((1, 1), (2, 1), (3, 2)):
        db.add(PercepcionPublicacion(
            id=pid, cuenta_id=cuenta, external_id=f"p{pid}", tipo="post",
            fecha_publicacion=datetime(2026, 3, 1), caption=f"publicación {pid}",
            n_comentarios=10, n_likes=pid))
    sents = ("POS", "NEU", "NEG")
    for i in range(1, 31):
        pub = 1 + (i % 3)
        db.add(PercepcionComentario(
            id=i, publicacion_id=pub, external_id=f"c{i}", autor_hash=f"h{i}",
            texto=f"comentario número {i} sobre la matrícula y los aranceles",
            fecha_comentario=datetime.combine(HOY - timedelta(days=i % 10), datetime.min.time()),
            idioma="es", n_likes=i % 4,
            tema="otros" if i % 2 else "infraestructura", tema_confianza=0.5))
        db.add(PercepcionScore(
            id=i, comentario_id=i, modelo="test", sentimiento=sents[i % 3],
            prob_pos=0.8 if i % 3 == 0 else 0.1, prob_neu=0.1,
            prob_neg=0.8 if i % 3 == 2 else 0.1,
            emocion="alegria" if i % 3 == 0 else "enojo", prob_emocion=0.7,
            scored_en=datetime(2026, 3, 30)))
    db.commit()
    curacion.reagregar(db)


@pytest.fixture(scope="module")
def sesion():
    with esquema_efimero() as url:
        engine = create_engine(url, future=True)
        db = sessionmaker(bind=engine, future=True)()
        _sembrar(db)
        try:
            yield db
        finally:
            db.close()
            engine.dispose()


def _decimales(obj, ruta="$") -> list[str]:
    if isinstance(obj, Decimal):
        return [ruta]
    if isinstance(obj, dict):
        return [r for k, v in obj.items() for r in _decimales(v, f"{ruta}.{k}")]
    if isinstance(obj, (list, tuple)):
        return [r for i, v in enumerate(obj) for r in _decimales(v, f"{ruta}[{i}]")]
    return []


def test_publicaciones_a_curar_no_revienta_el_group_by(sesion):
    res = curacion.publicaciones_a_curar(sesion, solo_con_otros=False)
    assert {i["id"] for i in res["items"]} == {1, 2, 3}
    assert all(isinstance(i["n_comentarios"], int) and isinstance(i["n_otros"], int)
               for i in res["items"])
    assert sum(i["n_comentarios"] for i in res["items"]) == 30


def test_servicios_no_devuelven_decimal(sesion):
    llamadas = {
        "resumen": repository.resumen(sesion, dias=60),
        "evolucion": repository.evolucion(sesion, dias=60),
        "por_tema": repository.por_tema(sesion, dias=60),
        "por_unidad": repository.por_unidad(sesion, dias=60),
        "emociones": repository.emociones(sesion, dias=60),
        "anomalias": repository.anomalias(sesion, dias=60),
        "concentracion": repository.concentracion_temas(sesion, dias=60),
        "postura": repository.postura_institucional(sesion, dias=60),
        "publicaciones_a_curar": curacion.publicaciones_a_curar(sesion, solo_con_otros=False),
    }
    for nombre, valor in llamadas.items():
        assert _decimales(valor) == [], nombre


def test_motor_de_lectura_no_puede_escribir():
    with esquema_efimero("percepcion_test_ro") as url:
        lector = crear_engine(url, solo_lectura=True)
        try:
            with lector.connect() as con:
                assert con.execute(text("SELECT count(*) FROM percepcion_cuenta")).scalar_one() == 0
            # Se compara la CLASE del error y no su mensaje: el servidor lo localiza.
            with pytest.raises(DBAPIError) as exc:
                with lector.begin() as con:
                    con.execute(text(
                        "INSERT INTO percepcion_cuenta (id, handle, nombre, tipo) "
                        "VALUES (1, 'x', 'x', 'x')"))
            assert isinstance(exc.value.orig, psycopg.errors.ReadOnlySqlTransaction)
        finally:
            lector.dispose()


def test_motor_de_lectura_respeta_el_esquema_de_la_url():
    with esquema_efimero("percepcion_test_ro2") as url:
        lector = crear_engine(url, solo_lectura=True)
        try:
            with lector.connect() as con:
                assert con.execute(text("SELECT current_schema()")).scalar_one() == "percepcion_test_ro2"
        finally:
            lector.dispose()


def test_motor_de_escritura_si_escribe():
    with esquema_efimero("percepcion_test_rw") as url:
        escritor = crear_engine(url, solo_lectura=False)
        try:
            with escritor.begin() as con:
                con.execute(text(
                    "INSERT INTO percepcion_cuenta (id, handle, nombre, tipo) "
                    "VALUES (1, 'x', 'x', 'x')"))
            with escritor.connect() as con:
                assert con.execute(text("SELECT count(*) FROM percepcion_cuenta")).scalar_one() == 1
        finally:
            escritor.dispose()


def test_publicaciones_a_curar_desempata_por_id(sesion):
    """Las tres publicaciones empatan en `n_otros`: sin desempate explícito el orden (y qué
    filas sobreviven al `limite`) lo decide el motor, y SQLite y Postgres elegían distinto."""
    res = curacion.publicaciones_a_curar(sesion, solo_con_otros=True, limite=2)
    assert [i["id"] for i in res["items"]] == [1, 2]


# ---------------------------------------------------------------------------
# Escrituras (curación, eventos, caché de resúmenes) sobre Postgres
# ---------------------------------------------------------------------------

@pytest.fixture()
def sesion_escritura():
    with esquema_efimero("percepcion_test_w") as url:
        engine = create_engine(url, future=True)
        db = sessionmaker(bind=engine, future=True)()
        _sembrar(db)
        try:
            yield db
        finally:
            db.close()
            engine.dispose()


def test_curacion_escribe_y_reagrega_en_postgres(sesion_escritura):
    db = sesion_escritura
    tema = curacion.crear_tema_custom(db, "Becas y gratuidad", ["beca", "Gratuidad"])
    assert tema["keywords"] == ["beca", "gratuidad"]

    r = curacion.asignar_tema_comentario(db, 1, tema["tema"])
    assert r["comentarios_actualizados"] == 1 and r["hechos"] > 0
    r = curacion.asignar_tema_publicacion(db, 2, "infraestructura")
    assert r["comentarios_actualizados"] >= 1

    curacion.corregir_sentimiento(db, 2, "NEG", "prueba", "t@ucn.cl")
    curacion.corregir_emocion(db, 2, "enojo", "prueba", "t@ucn.cl")
    curacion.corregir_tema(db, 3, tema["tema"], "prueba", "t@ucn.cl")
    curacion.corregir_postura(db, 3, "adverso", "prueba", "t@ucn.cl")
    assert db.execute(text("SELECT count(*) FROM percepcion_correccion")).scalar_one() >= 4
    replay = curacion.replay_correcciones(db)
    assert isinstance(replay, dict)
    assert curacion.correcciones_recientes(db, limite=10)["items"]


def test_eventos_abm_en_postgres(sesion_escritura):
    from app.services.percepcion import eventos
    ev = eventos.crear(sesion_escritura, nombre="Paro de prueba", tipo="paro",
                       fecha_inicio=date(2026, 3, 10))
    ev2 = eventos.actualizar(sesion_escritura, ev["id"], nombre="Paro", tipo="paro",
                             fecha_inicio=date(2026, 3, 10), fecha_fin=date(2026, 3, 12))
    assert ev2["id"] == ev["id"]
    assert [e["id"] for e in eventos.listar(sesion_escritura)["items"]] == [ev["id"]]
    assert eventos.eliminar(sesion_escritura, ev["id"])["eliminado"] is True


def test_resumen_semanal_se_cachea_en_postgres(sesion_escritura):
    """`_guardar` traga cualquier excepción: si el INSERT/UNIQUE fallara en Postgres, el
    resumen se regeneraría (y se pagaría) en cada request sin que nada lo avisara."""
    from unittest import mock
    from app.services.percepcion import resumen_llm

    llamadas: list = []

    def _fake(insumos):
        llamadas.append(1)
        return {"texto": "Resumen de prueba.", "modelo": "m", "input_tokens": 1,
                "output_tokens": 1, "costo_usd": 0.001}

    with mock.patch.object(resumen_llm, "_redactar", _fake):
        primera = resumen_llm.resumen_semanal(sesion_escritura, sesion_escritura, nivel="global")
        segunda = resumen_llm.resumen_semanal(sesion_escritura, sesion_escritura, nivel="global")
    assert primera["hay_datos"] and not primera["desde_cache"]
    assert segunda["desde_cache"] is True
    assert len(llamadas) == 1
    assert sesion_escritura.execute(text(
        "SELECT count(*) FROM percepcion_resumen_semanal")).scalar_one() == 1


def test_ddl_de_arranque_funciona_en_postgres():
    """`_asegurar_columnas` y `_asegurar_unicidad_resumen` tragan sus errores: sobre
    Postgres tienen que HACER lo que dicen, no fallar en silencio."""
    from unittest import mock

    from app.services.percepcion import db as pdb
    from app.services.percepcion.models import PercepcionCorreccion

    with esquema_efimero("percepcion_test_ddl") as url:
        engine = create_engine(url, future=True)
        try:
            with engine.begin() as con:
                con.execute(text("ALTER TABLE percepcion_correccion DROP COLUMN prob_tema_orig"))
                con.execute(text(
                    "INSERT INTO percepcion_resumen_semanal (semana_inicio, nivel, dimension, huella, texto) "
                    "VALUES ('2026-03-02', 'global', '', 'h', 't')"))
            with mock.patch.object(pdb, "percepcion_write_engine", engine):
                assert pdb._asegurar_columnas(PercepcionCorreccion.__table__) == ["prob_tema_orig"]
                assert pdb._asegurar_columnas(PercepcionCorreccion.__table__) == []  # idempotente
                assert pdb._asegurar_unicidad_resumen() is True
        finally:
            engine.dispose()
