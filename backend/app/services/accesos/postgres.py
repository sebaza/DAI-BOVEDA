"""PostgreSQL adapter of the access port (schema ``boveda``, see ``backend/sql/``).

Fail closed: every LOOKUP catches any error and answers "no access"; only the audit write
and the maintenance operations raise. Errors are logged by CLASS NAME only: a driver
message can echo connection details, and the database URL must never reach a log.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.schemas import AppRole, ModuloAcceso
from app.services.accesos.puerto import (
    AccessDatabaseError,
    AccessEntry,
    AuditError,
    Listing,
    UnknownModuleError,
    normalize_email,
    validate_email,
    validate_role,
)

logger = logging.getLogger("boveda")

# How a unit of work is opened: a context manager yielding a Connection inside a
# transaction that commits on success and rolls back on error (``engine.begin`` in
# production; the integration tests pass a savepoint on a transaction they roll back).
Abrir = Callable[[], ContextManager[Connection]]

_SQL_ES_ADMIN = text("SELECT 1 FROM boveda.administradores WHERE email = :email")

# Admins take the role `admin` on every ACTIVE module; others, the role of their row.
# An inactive (or unknown) module yields no row at all => no access, even for admins.
_SQL_ROL = text(
    """
    SELECT CASE WHEN EXISTS (SELECT 1 FROM boveda.administradores a WHERE a.email = :email)
                THEN 'admin' ELSE ac.rol END AS rol
      FROM boveda.modulos m
      LEFT JOIN boveda.accesos_modulo ac ON ac.modulo_id = m.id AND ac.email = :email
     WHERE m.id = :modulo AND m.activo
    """
)

_SQL_MODULOS = text(
    """
    SELECT m.id, m.nombre,
           CASE WHEN adm.email IS NOT NULL THEN 'admin' ELSE ac.rol END AS rol
      FROM boveda.modulos m
      LEFT JOIN boveda.administradores adm ON adm.email = :email
      LEFT JOIN boveda.accesos_modulo ac ON ac.modulo_id = m.id AND ac.email = :email
     WHERE m.activo AND (adm.email IS NOT NULL OR ac.email IS NOT NULL)
     ORDER BY m.nombre, m.id
    """
)

_SQL_AUDITAR = text(
    """
    INSERT INTO boveda.auditoria_texto (admin_email, modulo_id, endpoint, comentario_ids)
    VALUES (:email, :modulo, :endpoint, CAST(:ids AS bigint[]))
    """
)


class PostgresAccessRepository:
    def __init__(self, abrir: Abrir) -> None:
        self._abrir = abrir
        self._engine = None

    @classmethod
    def from_url(cls, url: str) -> "PostgresAccessRepository":
        kwargs: dict = {"future": True, "pool_pre_ping": True, "pool_recycle": 1800}
        if make_url(url).get_backend_name() == "postgresql":
            kwargs["connect_args"] = {"connect_timeout": 5}  # fail fast: an unreachable DB denies
        engine = create_engine(url, **kwargs)
        repo = cls(engine.begin)
        repo._engine = engine
        return repo

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()

    # ------------------------------------------------------------------ #
    # AccessRepository: lookups (never raise, deny on any error)
    # ------------------------------------------------------------------ #
    def is_admin(self, email: str) -> bool:
        email = normalize_email(email)
        if not email:
            return False
        try:
            with self._abrir() as con:
                return con.execute(_SQL_ES_ADMIN, {"email": email}).first() is not None
        except Exception as exc:  # noqa: BLE001 - fail closed
            _log_denegado("is_admin", exc)
            return False

    def role_for(self, email: str, module_id: str) -> AppRole | None:
        email = normalize_email(email)
        if not email or not module_id:
            return None
        try:
            with self._abrir() as con:
                fila = con.execute(_SQL_ROL, {"email": email, "modulo": module_id}).first()
            return _rol(fila[0]) if fila else None
        except Exception as exc:  # noqa: BLE001 - fail closed
            _log_denegado("role_for", exc)
            return None

    def modules_for(self, email: str) -> list[ModuloAcceso]:
        email = normalize_email(email)
        if not email:
            return []
        try:
            with self._abrir() as con:
                filas = con.execute(_SQL_MODULOS, {"email": email}).all()
            modulos = [(id_, nombre, _rol(rol)) for id_, nombre, rol in filas]
            return [ModuloAcceso(id=i, nombre=n, rol=r) for i, n, r in modulos if r is not None]
        except Exception as exc:  # noqa: BLE001 - fail closed
            _log_denegado("modules_for", exc)
            return []

    # ------------------------------------------------------------------ #
    # AccessRepository: audit (raises)
    # ------------------------------------------------------------------ #
    def record_text_view(
        self, admin_email: str, module_id: str, endpoint: str, comment_ids: Sequence[int]
    ) -> None:
        # Array literal built from ints only (int() rejects anything else), so it can
        # never carry SQL, and it needs no driver-specific array adaptation.
        ids = "{" + ",".join(str(int(i)) for i in comment_ids) + "}"
        try:
            with self._abrir() as con:
                con.execute(
                    _SQL_AUDITAR,
                    {"email": normalize_email(admin_email), "modulo": module_id,
                     "endpoint": endpoint, "ids": ids},
                )
        except Exception as exc:  # noqa: BLE001 - the caller must refuse to serve the text
            logger.error("No se pudo registrar la auditoría de texto (%s).", type(exc).__name__)
            raise AuditError("No se pudo registrar la auditoría de texto.") from exc

    # ------------------------------------------------------------------ #
    # AccessManager (raises domain errors / AccessDatabaseError)
    # ------------------------------------------------------------------ #
    def _existe_modulo(self, con: Connection, module_id: str) -> None:
        if con.execute(text("SELECT 1 FROM boveda.modulos WHERE id = :m"), {"m": module_id}).first() is None:
            raise UnknownModuleError(f"El módulo {module_id!r} no existe.")

    def add_admin(self, email: str, *, by: str | None = None) -> None:
        email = validate_email(email)
        with self._gestion() as con:
            con.execute(
                text(
                    "INSERT INTO boveda.administradores (email, creado_por) VALUES (:e, :por) "
                    "ON CONFLICT (email) DO NOTHING"
                ),
                {"e": email, "por": by},
            )

    def remove_admin(self, email: str) -> bool:
        email = validate_email(email)
        with self._gestion() as con:
            return con.execute(text("DELETE FROM boveda.administradores WHERE email = :e"), {"e": email}).rowcount > 0

    def grant_access(self, module_id: str, email: str, rol: str, *, by: str | None = None) -> None:
        email, rol = validate_email(email), validate_role(rol)
        with self._gestion() as con:
            self._existe_modulo(con, module_id)
            con.execute(
                text(
                    "INSERT INTO boveda.accesos_modulo (modulo_id, email, rol, creado_por) "
                    "VALUES (:m, :e, :r, :por) "
                    "ON CONFLICT (modulo_id, email) DO UPDATE SET rol = EXCLUDED.rol"
                ),
                {"m": module_id, "e": email, "r": rol, "por": by},
            )

    def revoke_access(self, module_id: str, email: str) -> bool:
        email = validate_email(email)
        with self._gestion() as con:
            self._existe_modulo(con, module_id)
            return con.execute(
                text("DELETE FROM boveda.accesos_modulo WHERE modulo_id = :m AND email = :e"),
                {"m": module_id, "e": email},
            ).rowcount > 0

    def list_all(self, module_id: str | None = None) -> Listing:
        with self._gestion() as con:
            if module_id is not None:
                self._existe_modulo(con, module_id)
            admins = [r[0] for r in con.execute(text("SELECT email FROM boveda.administradores ORDER BY email"))]
            filas = con.execute(
                text(
                    "SELECT modulo_id, email, rol, creado_por FROM boveda.accesos_modulo "
                    "WHERE (CAST(:m AS text) IS NULL OR modulo_id = :m) ORDER BY modulo_id, email"
                ),
                {"m": module_id},
            ).all()
        return Listing(
            administradores=admins,
            accesos=[AccessEntry(modulo_id=m, email=e, rol=r, creado_por=p) for m, e, r, p in filas],
        )

    @contextmanager
    def _gestion(self) -> Iterator[Connection]:
        """A unit of work for maintenance: database failures become ``AccessDatabaseError``
        (domain errors raised inside pass through untouched)."""
        try:
            with self._abrir() as con:
                yield con
        except SQLAlchemyError as exc:
            raise AccessDatabaseError(_mensaje_bd(exc)) from exc


def _mensaje_bd(exc: BaseException) -> str:
    return f"Error de base de datos ({type(exc).__name__}). Revisa BOVEDA_DATABASE_URL y que las migraciones de backend/sql/ estén aplicadas."


def _rol(valor: str | None) -> AppRole | None:
    try:
        return AppRole(valor) if valor else None
    except ValueError:
        return None  # unknown role string: deny


def _log_denegado(operacion: str, exc: BaseException) -> None:
    logger.error("Consulta de accesos fallida en %s (%s): se deniega.", operacion, type(exc).__name__)
