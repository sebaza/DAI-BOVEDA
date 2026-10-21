from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.schemas import AuthUser, GoogleTokenRequest
from app.services.auth import (
    AccountNotAuthorizedError,
    GoogleAuthError,
    build_dev_user,
    build_login_response,
    get_auth_config,
    get_authenticated_user,
    get_session_user,
    is_dev,
    verify_google_credential,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def auth_config():
    return get_auth_config()


@router.get("/session-user")
def session_user(user: AuthUser = Depends(get_authenticated_user)):
    """The session's user, re-validated: 403 if the account no longer has any access."""
    return user


@router.get("/me")
def me(user: AuthUser = Depends(get_session_user)):
    """The session's user with ``is_admin`` and ``modulos``, freshly resolved from the
    database. Unlike ``/session-user`` it answers 200 for a valid session whose account has
    no access (``allowed: false``, ``modulos: []``): it only ever describes the caller."""
    return user


def _guard_dev_only() -> None:
    """dev-login mints a session WITHOUT OAuth: it must not exist outside development.
    404 (not 403) so as not to reveal the route. Anything but an explicit APP_ENV=dev is
    treated as non-dev (fail closed)."""
    if not is_dev():
        raise HTTPException(404, "Not Found")


@router.get("/dev-login")
def dev_login(email: str | None = Query(default=None), name: str | None = Query(default=None)):
    _guard_dev_only()
    user = build_dev_user(email=email, name=name)
    # The dev user's access is resolved from the database like anyone else's. The only
    # leniency: with BOVEDA_DATABASE_URL empty (nothing to resolve against) the session is
    # still issued so the app can be opened, and it simply has no modules.
    if not user.allowed and get_settings().boveda_database_url:
        raise HTTPException(403, "Esta cuenta no está autorizada para acceder a la Bóveda DAI.")
    return build_login_response(
        user,
        message="Usuario de desarrollo validado.",
        next_step="Solo disponible con APP_ENV=dev; en producción se usa Google.",
    )


@router.post("/google/verify")
def verify_google_login(payload: GoogleTokenRequest):
    try:
        user = verify_google_credential(payload.credential)
    except AccountNotAuthorizedError as exc:
        raise HTTPException(403, str(exc)) from exc
    except GoogleAuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    return build_login_response(
        user,
        message="Usuario autenticado con Google.",
        next_step="Sesión activa para la Bóveda DAI.",
    )
