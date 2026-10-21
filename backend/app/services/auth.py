"""Authentication and access control for Boveda DAI.

Modeled on the Torre (Google ID token verified server side + own HMAC-signed session
token) but with a very different access policy: this app exists because the Percepcion
data is SENSITIVE, so access is LIST-ONLY and fails closed.

* Per-module lists in PostgreSQL (``boveda.accesos_modulo``): ``lector`` (read) and
  ``equipo`` (read + write).
* Global administrators (``boveda.administradores``): open every ACTIVE module and are the
  only ones allowed into the curation endpoints that return raw comment text.
* No rows (or a database that cannot be reached) => nobody gets in. Maintenance is done
  with ``scripts/boveda_accesos.py``.

The role is NEVER trusted from the token: it is re-resolved from the database on every
request, so revoking a row takes effect on the next request, even for a still-valid
token. The only thing the token carries is ``auth_mode == "dev"``, honoured exclusively
while APP_ENV=dev.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Header, HTTPException
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import (
    ROLES_ESCRITURA,
    AppRole,
    AuthConfigResponse,
    AuthUser,
    LoginResponse,
    ModuloAcceso,
)
from app.services import accesos


class GoogleAuthError(Exception):
    pass


class AccountNotAuthorizedError(GoogleAuthError):
    """The Google identity is valid but the account has no access (HTTP 403, not 401)."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(f"{raw}{padding}")


def _sign_session_payload(payload_b64: str) -> str:
    secret = get_settings().app_session_secret.encode("utf-8")
    digest = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def is_dev() -> bool:
    return (get_settings().app_env or "").strip().lower() == "dev"


# --------------------------------------------------------------------------- #
# Access resolution (database, fail closed)
# --------------------------------------------------------------------------- #
_PRIORIDAD_ROL = {AppRole.admin: 3, AppRole.equipo: 2, AppRole.lector: 1}


def resolve_access(email: str, *, auth_mode: str = "session") -> tuple[bool, list[ModuloAcceso]]:
    """``(is_admin, active modules the account can open)``. Empty = not allowed (fail closed).

    A dev session is honoured only while APP_ENV=dev, so a dev token is worthless anywhere
    else even if the same email happens to have access in the database.
    """
    lowered = (email or "").strip().lower()
    if not lowered:
        return False, []
    if auth_mode == "dev" and not is_dev():
        return False, []
    repo = accesos.get_repository()
    return repo.is_admin(lowered), repo.modules_for(lowered)


def _build_auth_user(
    *,
    email: str,
    name: str,
    auth_mode: str,
    picture: str | None = None,
    hosted_domain: str | None = None,
) -> AuthUser:
    is_admin, modulos = resolve_access(email, auth_mode=auth_mode)
    # Summary role kept for compatibility: the best one across modules (admin if global admin).
    role = AppRole.admin if is_admin else max(
        (m.rol for m in modulos), key=lambda r: _PRIORIDAD_ROL[r], default=None
    )
    return AuthUser(
        email=email,
        name=name,
        allowed=is_admin or bool(modulos),
        auth_mode=auth_mode,
        role=role,
        is_admin=is_admin,
        modulos=modulos,
        picture=picture,
        hosted_domain=hosted_domain,
    )


def build_dev_user(email: str | None = None, name: str | None = None) -> AuthUser:
    settings = get_settings()
    return _build_auth_user(
        email=email or settings.dev_default_user_email,
        name=name or settings.dev_default_user_name,
        auth_mode="dev",
    )


# --------------------------------------------------------------------------- #
# Session tokens
# --------------------------------------------------------------------------- #
def build_login_response(user: AuthUser, *, message: str, next_step: str) -> LoginResponse:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.app_session_ttl_seconds)
    payload = {
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "hosted_domain": user.hosted_domain,
        "auth_mode": user.auth_mode,
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_hex(8),
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    token = f"{payload_b64}.{_sign_session_payload(payload_b64)}"
    return LoginResponse(
        message=message,
        user=user,
        next_step=next_step,
        session_token=token,
        expires_at=expires_at.isoformat(),
    )


def verify_session_token(token: str) -> AuthUser:
    if not token or "." not in token:
        raise GoogleAuthError("Sesión inválida o incompleta.")
    payload_b64, signature = token.split(".", 1)
    expected = _sign_session_payload(payload_b64)
    if not hmac.compare_digest(signature, expected):
        raise GoogleAuthError("Sesión inválida: firma incorrecta.")
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise GoogleAuthError("Sesión inválida: contenido no legible.") from exc

    if int(payload.get("exp") or 0) <= int(datetime.now(UTC).timestamp()):
        raise GoogleAuthError("La sesión expiró. Vuelve a iniciar sesión.")

    # Access comes from the database, never from the payload.
    return _build_auth_user(
        email=str(payload.get("email") or ""),
        name=str(payload.get("name") or ""),
        auth_mode=str(payload.get("auth_mode") or "session"),
        picture=payload.get("picture"),
        hosted_domain=payload.get("hosted_domain"),
    )


# --------------------------------------------------------------------------- #
# FastAPI dependencies
# --------------------------------------------------------------------------- #
def get_session_user(authorization: str | None = Header(default=None)) -> AuthUser:
    """Any valid session, WITHOUT requiring access (401 if missing/invalid). The returned
    user carries ``allowed`` / ``is_admin`` / ``modulos`` freshly resolved from the database."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Falta Authorization Bearer para acceder a este recurso.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_session_token(token)
    except GoogleAuthError as exc:
        raise HTTPException(401, str(exc)) from exc


def get_authenticated_user(user: AuthUser = Depends(get_session_user)) -> AuthUser:
    """Any ALLOWED user (an admin, or someone with access to at least one active module).
    401 without a valid session, 403 if the account has no access."""
    if not user.allowed:
        raise HTTPException(403, "Tu cuenta no tiene acceso a la Bóveda DAI.")
    return user


def check_module_access(user: AuthUser, module_id: str, *, write: bool = False) -> ModuloAcceso:
    """Raise 403 unless ``user`` may open ``module_id`` (and, if ``write``, change things in
    it: roles ``equipo`` and ``admin``). Unknown or inactive modules grant nothing."""
    acceso = user.acceso_a(module_id)
    if acceso is None:
        raise HTTPException(403, "Tu cuenta no tiene acceso a este módulo.")
    if write and acceso.rol not in ROLES_ESCRITURA:
        raise HTTPException(403, "Esta acción es solo para el equipo DAI.")
    return acceso


def require_module(module_id: str, *, write: bool = False):
    """Dependency factory: the user must have access to ``module_id`` (and write access when
    ``write=True``). 401 without session, 403 without access."""

    def dependency(user: AuthUser = Depends(get_authenticated_user)) -> AuthUser:
        check_module_access(user, module_id, write=write)
        return user

    return dependency


def require_admin(user: AuthUser = Depends(get_authenticated_user)) -> AuthUser:
    """Global administrators only (raw comment text, curation)."""
    if not user.is_admin:
        raise HTTPException(403, "Este recurso es solo para administradores de la Bóveda DAI.")
    return user


# --------------------------------------------------------------------------- #
# Config + Google sign-in
# --------------------------------------------------------------------------- #
def get_auth_config() -> AuthConfigResponse:
    settings = get_settings()
    enabled = settings.google_oauth_enabled and bool(settings.google_client_id)
    return AuthConfigResponse(
        google_oauth_enabled=enabled,
        google_client_id=settings.google_client_id if enabled else None,
        # dev-login only exists in development (404 elsewhere); do not advertise a dead endpoint.
        dev_login_enabled=is_dev(),
    )


def verify_google_credential(credential: str) -> AuthUser:
    settings = get_settings()
    if not settings.google_oauth_enabled or not settings.google_client_id:
        raise GoogleAuthError("Google OAuth no está configurado en el backend.")

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        payload = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except (ValueError, ValidationError) as exc:
        raise GoogleAuthError(f"No se pudo verificar el token de Google: {exc}") from exc

    email = payload.get("email")
    if not email:
        raise GoogleAuthError("El token de Google no trae email.")
    if not payload.get("email_verified", False):
        raise GoogleAuthError("La cuenta Google no tiene email verificado.")

    user = _build_auth_user(
        email=email,
        name=payload.get("name") or email,
        auth_mode="google",
        picture=payload.get("picture"),
        hosted_domain=payload.get("hd") or (email.split("@", 1)[1] if "@" in email else None),
    )
    if not user.allowed:
        # Do not mint a session for an account without access.
        raise AccountNotAuthorizedError("Esta cuenta no está autorizada para acceder a la Bóveda DAI.")
    return user
