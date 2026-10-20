"""Auth schemas."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AppRole(str, Enum):
    """Session roles. ``equipo`` = DAI team (read + write); ``lector`` = read only."""

    equipo = "equipo"
    lector = "lector"


class AuthUser(BaseModel):
    email: str
    name: str = ""
    allowed: bool = False
    auth_mode: str = "session"
    role: AppRole | None = None
    picture: str | None = None
    hosted_domain: str | None = None

    @property
    def is_team(self) -> bool:
        return self.allowed and self.role == AppRole.equipo


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
