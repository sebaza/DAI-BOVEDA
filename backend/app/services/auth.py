"""Authentication and access control for Boveda DAI.

Modeled on the Torre (Google ID token verified server side + own HMAC-signed session
token) but with a very different access policy: this app exists because the Percepcion
data is SENSITIVE, so access is ALLOWLIST-ONLY and fails closed.

* ``BOVEDA_ALLOWED_EMAILS``: can read.
* ``BOVEDA_TEAM_EMAILS``: DAI team, can read and write (implicitly allowed to read).
* Empty lists => nobody gets in. Only exception: ``/auth/dev-login`` when APP_ENV=dev.

The role is NEVER trusted from the token: it is re-resolved from the allowlists on every
request, so removing an email from the env revokes access as soon as the process
restarts, even for a still-valid token. The only thing the token can add is
``auth_mode == "dev"``, honoured exclusively while APP_ENV=dev.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Header, HTTPException
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import AppRole, AuthConfigResponse, AuthUser, LoginResponse


class GoogleAuthError(Exception):
    pass


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
# Allowlist resolution
# --------------------------------------------------------------------------- #
def resolve_role(email: str, *, auth_mode: str = "session") -> AppRole | None:
    """Role for ``email`` according to the allowlists. ``None`` = not allowed (fail closed)."""
    lowered = (email or "").strip().lower()
    if not lowered:
        return None
    settings = get_settings()
    if lowered in settings.boveda_team_emails:
        return AppRole.equipo
    if lowered in settings.boveda_allowed_emails:
        return AppRole.lector
    # Dev sessions are minted by /auth/dev-login, which only exists when APP_ENV=dev.
    # Honoured only while still in dev, so a dev token is worthless anywhere else.
    if auth_mode == "dev" and is_dev():
        return AppRole.equipo
    return None


def _build_auth_user(
    *,
    email: str,
    name: str,
    auth_mode: str,
    picture: str | None = None,
    hosted_domain: str | None = None,
) -> AuthUser:
    role = resolve_role(email, auth_mode=auth_mode)
    return AuthUser(
        email=email,
        name=name,
        allowed=role is not None,
        auth_mode=auth_mode,
        role=role,
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

    # Role comes from the allowlists, never from the payload.
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
def get_authenticated_user(authorization: str | None = Header(default=None)) -> AuthUser:
    """Any ALLOWED user (reader or team). 401 without a valid session, 403 if not allowlisted."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Falta Authorization Bearer para acceder a este recurso.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        user = verify_session_token(token)
    except GoogleAuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    if not user.allowed:
        raise HTTPException(403, "Tu cuenta no tiene acceso a la Bóveda DAI.")
    return user


def get_team_user(authorization: str | None = Header(default=None)) -> AuthUser:
    """DAI team only (write access)."""
    user = get_authenticated_user(authorization)
    if not user.is_team:
        raise HTTPException(403, "Este recurso es solo para el equipo DAI.")
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
        # Do not mint a session for an unlisted account.
        raise GoogleAuthError("Esta cuenta no está autorizada para acceder a la Bóveda DAI.")
    return user
