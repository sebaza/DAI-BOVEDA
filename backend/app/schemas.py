"""Auth schemas."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AppRole(str, Enum):
    """Access roles. ``lector`` = read only; ``equipo`` = DAI team (read + write);
    ``admin`` = global administrator (acts with full rights in every active module and is
    the only one allowed into the raw-text curation endpoints). ``lector`` and ``equipo``
    are granted PER MODULE; ``admin`` is global."""

    admin = "admin"
    equipo = "equipo"
    lector = "lector"


# Roles that may write inside a module.
ROLES_ESCRITURA = frozenset({AppRole.equipo, AppRole.admin})


class ModuloAcceso(BaseModel):
    """A module the user can open, and with which role."""

    id: str
    nombre: str
    rol: AppRole


class AuthUser(BaseModel):
    email: str
    name: str = ""
    # True when the account is an admin or has access to at least one ACTIVE module.
    allowed: bool = False
    auth_mode: str = "session"
    # Summary role, kept for compatibility: admin > equipo > lector (best across modules).
    role: AppRole | None = None
    is_admin: bool = False
    modulos: list[ModuloAcceso] = []
    picture: str | None = None
    hosted_domain: str | None = None

    @property
    def is_team(self) -> bool:
        return self.allowed and self.role in ROLES_ESCRITURA

    def acceso_a(self, module_id: str) -> ModuloAcceso | None:
        """The user's access to ``module_id`` (None = none). Admins carry every active module."""
        return next((m for m in self.modulos if m.id == module_id), None)


class AuthConfigResponse(BaseModel):
    google_oauth_enabled: bool
    google_client_id: str | None = None
    dev_login_enabled: bool = False


class GoogleTokenRequest(BaseModel):
    credential: str


class LoginResponse(BaseModel):
    message: str
    user: AuthUser
    next_step: str
    session_token: str
    expires_at: str
