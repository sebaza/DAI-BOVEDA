"""Port of the access layer (hexagonal): what the app needs to know about WHO may open WHAT.

The domain side (``services/auth.py`` and the routers) only talks to these protocols. The
PostgreSQL adapter (``postgres.py``) and the in-memory fake used by the tests
(``memoria.py``) implement them, and ``tests/contrato_accesos.py`` holds the behavioural
contract both must honour.

Fail closed is part of the contract: the four LOOKUPS never raise. If the answer cannot
be determined (database down, missing row, unknown module) they answer "no access".
``record_text_view`` is the opposite on purpose: if the audit cannot be written it raises
``AuditError`` so the caller refuses to deliver the text.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.schemas import AppRole, ModuloAcceso

# Roles that can be granted PER MODULE. `admin` is global (see AccessManager.add_admin).
ROLES_MODULO = ("lector", "equipo")


class AccessError(Exception):
    """Base of the errors raised by the access layer (messages are user-facing, in Spanish)."""


class InvalidEmailError(AccessError, ValueError):
    pass


class InvalidRoleError(AccessError, ValueError):
    pass


class UnknownModuleError(AccessError, LookupError):
    pass


class AuditError(AccessError):
    """The text-view audit record could not be written."""


class AccessDatabaseError(AccessError):
    """The access database could not be reached or answered with an error."""


def normalize_email(email: str | None) -> str:
    """Canonical form used for every lookup and every stored row."""
    return (email or "").strip().lower()


def validate_email(email: str | None) -> str:
    """Normalized email, or ``InvalidEmailError``. Mirrors the CHECK of the SQL tables
    (lowercase, ``@`` not in first position) plus no whitespace."""
    limpio = normalize_email(email)
    if not limpio or any(c.isspace() for c in limpio) or limpio.find("@") < 1:
        raise InvalidEmailError(f"Correo inválido: {email!r}.")
    return limpio


def validate_role(rol: str | None) -> str:
    limpio = (rol or "").strip().lower()
    if limpio not in ROLES_MODULO:
        raise InvalidRoleError(f"Rol inválido {rol!r}: usa uno de {', '.join(ROLES_MODULO)}.")
    return limpio


@dataclass(frozen=True)
class AccessEntry:
    """One row of a module's access list."""

    modulo_id: str
    email: str
    rol: str
    creado_por: str | None = None


@dataclass(frozen=True)
class Listing:
    administradores: list[str]
    accesos: list[AccessEntry]


class AccessRepository(Protocol):
    """What the running app needs. Lookups never raise (deny on any doubt)."""

    def is_admin(self, email: str) -> bool:
        """Is ``email`` a global administrator?"""

    def role_for(self, email: str, module_id: str) -> AppRole | None:
        """Effective role of ``email`` in ``module_id``: ``admin`` for administrators,
        else the module role. ``None`` if no access OR the module is inactive/unknown
        (an inactive module grants nothing, not even to administrators)."""

    def modules_for(self, email: str) -> list[ModuloAcceso]:
        """Every ACTIVE module ``email`` can open. Administrators get all of them, with
        role ``admin``."""

    def record_text_view(
        self, admin_email: str, module_id: str, endpoint: str, comment_ids: Sequence[int]
    ) -> None:
        """Audit: ``admin_email`` was served the raw text of ``comment_ids`` by ``endpoint``.
        Raises ``AuditError`` if it could not be recorded."""


class AccessManager(Protocol):
    """Maintenance of the lists (used by ``scripts/boveda_accesos.py``). Unlike the
    lookups, these raise: ``InvalidEmailError``, ``InvalidRoleError``,
    ``UnknownModuleError`` or ``AccessDatabaseError``."""

    def add_admin(self, email: str, *, by: str | None = None) -> None: ...

    def remove_admin(self, email: str) -> bool:
        """True if it was an administrator."""

    def grant_access(self, module_id: str, email: str, rol: str, *, by: str | None = None) -> None:
        """Insert or change (upsert) the role of ``email`` in ``module_id``."""

    def revoke_access(self, module_id: str, email: str) -> bool:
        """True if there was an access to remove."""

    def list_all(self, module_id: str | None = None) -> Listing:
        """All administrators plus the access rows (of one module, or of every module)."""
