"""Soporte de los tests de Percepción contra PostgreSQL (opt-in).

SE SALTAN salvo que ``PERCEPCION_TEST_DATABASE_URL`` esté definida (URL SQLAlchemy de una
base Postgres donde se pueda crear un esquema). Cada test trabaja en un esquema
descartable (``percepcion_test`` por defecto) que se crea y se elimina por completo: el
esquema real ``percepcion`` no se toca nunca. La URL va solo por línea de comandos.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text

from app.database import Base
from app.services.percepcion import models  # noqa: F401  (registra las tablas)
from app.services.percepcion.pg import url_con_esquema

URL = os.environ.get("PERCEPCION_TEST_DATABASE_URL", "").strip()
requiere_pg = pytest.mark.skipif(not URL, reason="PERCEPCION_TEST_DATABASE_URL no está definida")

ESQUEMA_TEST = "percepcion_test"


@contextmanager
def esquema_efimero(esquema: str = ESQUEMA_TEST, *, crear_tablas: bool = True):
    """Crea el esquema (borrando uno previo del mismo nombre), cede su URL y lo elimina."""
    assert esquema != "percepcion", "los tests nunca usan el esquema real"
    admin = create_engine(URL, future=True)
    with admin.begin() as con:
        con.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        con.execute(text(f'CREATE SCHEMA "{esquema}"'))
    url = url_con_esquema(URL, esquema)
    try:
        if crear_tablas:
            eng = create_engine(url, future=True)
            Base.metadata.create_all(eng)
            eng.dispose()
        yield url
    finally:
        with admin.begin() as con:
            con.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        admin.dispose()
