"""Access layer of Boveda DAI (hexagonal): port, PostgreSQL adapter and in-memory fake.

Composition root: ``get_repository()`` is what the app uses. It builds the PostgreSQL
adapter from ``BOVEDA_DATABASE_URL`` (cached per URL) and, if that URL is empty or the
adapter cannot be built, a deny-everything repository. Tests inject a fake with
``configure(...)`` and undo it with ``reset()``.
"""
from __future__ import annotations

import logging
from typing import Sequence

from app.config import get_settings
from app.schemas import AppRole, ModuloAcceso
from app.services.accesos.memoria import InMemoryAccessRepository
from app.services.accesos.postgres import PostgresAccessRepository
from app.services.accesos.puerto import (
    ROLES_MODULO,
    AccessDatabaseError,
    AccessEntry,
    AccessError,
    AccessManager,
    AccessRepository,
    AuditError,
    InvalidEmailError,
    InvalidRoleError,
    Listing,
    UnknownModuleError,
    normalize_email,
    validate_email,
    validate_role,
)

__all__ = [
    "ROLES_MODULO",
    "AccessDatabaseError",
    "AccessEntry",
    "AccessError",
    "AccessManager",
    "AccessRepository",
    "AuditError",
    "DenyAllAccessRepository",
    "InMemoryAccessRepository",
    "InvalidEmailError",
    "InvalidRoleError",
    "Listing",
    "PostgresAccessRepository",
    "UnknownModuleError",
    "configure",
    "get_repository",
    "normalize_email",
    "reset",
    "validate_email",
    "validate_role",
]

logger = logging.getLogger("boveda")


class DenyAllAccessRepository:
    """Used when there is no usable access database: nobody gets in (fail closed)."""

    def __init__(self, motivo: str) -> None:
        self._motivo = motivo

    def is_admin(self, email: str) -> bool:
        return False

    def role_for(self, email: str, module_id: str) -> AppRole | None:
        return None

    def modules_for(self, email: str) -> list[ModuloAcceso]:
        return []

    def record_text_view(
        self, admin_email: str, module_id: str, endpoint: str, comment_ids: Sequence[int]
    ) -> None:
        raise AuditError(self._motivo)


_override: AccessRepository | None = None
_default: tuple[str, AccessRepository] | None = None  # (url it was built from, repository)


def configure(repo: AccessRepository) -> None:
    """Use ``repo`` instead of the one built from settings (tests)."""
    global _override
    _override = repo


def reset() -> None:
    """Drop the injected repository and the cached default."""
    global _override, _default
    _override = None
    if _default is not None:
        dispose = getattr(_default[1], "dispose", None)
        if callable(dispose):
            dispose()
    _default = None


def _build_default(url: str) -> AccessRepository:
    if not url:
        logger.warning(
            "BOVEDA_DATABASE_URL no está configurada: se deniega el acceso a todos los usuarios."
        )
        return DenyAllAccessRepository("BOVEDA_DATABASE_URL no está configurada.")
    try:
        return PostgresAccessRepository.from_url(url)
    except Exception as exc:  # noqa: BLE001 - bad URL / missing driver: fail closed
        # Class name only: the message of a URL parse error can echo the URL.
        logger.error("No se pudo crear la conexión de accesos (%s): se deniega a todos.", type(exc).__name__)
        return DenyAllAccessRepository("La conexión a la base de accesos no está disponible.")


def get_repository() -> AccessRepository:
    global _default
    if _override is not None:
        return _override
    url = get_settings().boveda_database_url
    if _default is None or _default[0] != url:
        reset()
        _default = (url, _build_default(url))
    return _default[1]
