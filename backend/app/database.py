"""Declarative ``Base`` shared by the Percepcion models.

Boveda has no operational database of its own: the only persistent state is the
Percepcion database, whose engines live in ``app.services.percepcion.db``. This module
only exposes the ``Base`` that ``services/percepcion/models.py`` imports.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
