"""Fail closed: a broken or missing database must DENY, never allow."""
from __future__ import annotations

import logging
from contextlib import contextmanager

import pytest
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.services import accesos
from app.services.accesos import AuditError, PostgresAccessRepository


@contextmanager
def _db_caida():
    raise OperationalError("SELECT 1", {}, Exception("connection refused"))
    yield  # pragma: no cover


@pytest.fixture(autouse=True)
def _limpio():
    accesos.reset()
    yield
    accesos.reset()


def test_database_error_denies_every_lookup():
    repo = PostgresAccessRepository(_db_caida)
    assert repo.is_admin("a@ucn.cl") is False
    assert repo.role_for("a@ucn.cl", "percepcion") is None
    assert repo.modules_for("a@ucn.cl") == []


def test_database_error_makes_the_audit_write_fail_loudly():
    repo = PostgresAccessRepository(_db_caida)
    with pytest.raises(AuditError):
        repo.record_text_view("a@ucn.cl", "percepcion", "/x", [1])


def test_without_database_url_everybody_is_denied_and_a_warning_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), "boveda_database_url", "")
    with caplog.at_level(logging.WARNING, logger="boveda"):
        repo = accesos.get_repository()
    assert repo.is_admin("dev@boveda.local") is False
    assert repo.role_for("dev@boveda.local", "percepcion") is None
    assert repo.modules_for("dev@boveda.local") == []
    with pytest.raises(AuditError):
        repo.record_text_view("dev@boveda.local", "percepcion", "/x", [1])
    assert any("BOVEDA_DATABASE_URL" in r.getMessage() for r in caplog.records)


def test_the_database_url_is_never_logged(monkeypatch, caplog):
    secreto = "postgresql+psycopg://usuario:clave-secreta@127.0.0.1:1/nada"
    monkeypatch.setattr(get_settings(), "boveda_database_url", secreto)
    with caplog.at_level(logging.DEBUG, logger="boveda"):
        repo = accesos.get_repository()
        repo.is_admin("a@ucn.cl")  # nothing listens on :1 => denied, error logged
    assert "clave-secreta" not in caplog.text


def test_configure_overrides_and_reset_restores(monkeypatch):
    monkeypatch.setattr(get_settings(), "boveda_database_url", "")
    fake = accesos.InMemoryAccessRepository()
    accesos.configure(fake)
    assert accesos.get_repository() is fake
    accesos.reset()
    assert accesos.get_repository() is not fake
