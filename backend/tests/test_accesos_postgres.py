"""Integration: the PostgreSQL adapter against a real database.

SKIPPED unless ``BOVEDA_TEST_DATABASE_URL`` is set (SQLAlchemy URL of a database where
``backend/sql/001_boveda_access.sql`` and ``002_boveda_admin_audit.sql`` are applied).
Every test runs inside one transaction that is ROLLED BACK, so nothing is left in the
``boveda`` schema. Pass the URL on the command line only; never commit it.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text

from app.services.accesos import PostgresAccessRepository
from contrato_accesos import ContratoAccesos, Entorno

URL = os.environ.get("BOVEDA_TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not URL, reason="BOVEDA_TEST_DATABASE_URL no está definida")


class TestPostgres(ContratoAccesos):
    @pytest.fixture()
    def entorno(self) -> Entorno:
        engine = create_engine(URL, future=True)
        conn = engine.connect()
        outer = conn.begin()  # rolled back at teardown: no residue

        @contextmanager
        def abrir():
            # Savepoint per operation, so a failing statement (FK violation, ...) does not
            # poison the whole test transaction.
            with conn.begin_nested():
                yield conn

        repo = PostgresAccessRepository(abrir)

        def crear_modulo(id: str, nombre: str, activo: bool = True) -> None:
            conn.execute(
                text("INSERT INTO boveda.modulos (id, nombre, activo) VALUES (:i, :n, :a)"),
                {"i": id, "n": nombre, "a": activo},
            )

        # Only rows written by this test: the local DB may already hold real audit rows.
        tope = conn.execute(text("SELECT coalesce(max(id), 0) FROM boveda.auditoria_texto")).scalar()

        def leer_auditoria() -> list[dict]:
            filas = conn.execute(
                text(
                    "SELECT admin_email, modulo_id, endpoint, comentario_ids "
                    "FROM boveda.auditoria_texto WHERE id > :tope ORDER BY id"
                ),
                {"tope": tope},
            ).mappings()
            return [dict(f) for f in filas]

        try:
            yield Entorno(repo=repo, crear_modulo=crear_modulo, leer_auditoria=leer_auditoria)
        finally:
            outer.rollback()
            conn.close()
            engine.dispose()


def test_rollback_leaves_no_residue():
    """Runs after the contract (file order): no test module or access row survives."""
    engine = create_engine(URL, future=True)
    try:
        with engine.connect() as c:
            modulos = c.execute(text("SELECT count(*) FROM boveda.modulos WHERE id LIKE 'mod\\_%'")).scalar_one()
            accesos = c.execute(text("SELECT count(*) FROM boveda.accesos_modulo WHERE email LIKE '%@ucn.cl'")).scalar_one()
            auditoria = c.execute(text("SELECT count(*) FROM boveda.auditoria_texto WHERE modulo_id LIKE 'mod\\_%'")).scalar_one()
    finally:
        engine.dispose()
    assert (modulos, accesos, auditoria) == (0, 0, 0)
