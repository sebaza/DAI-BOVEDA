from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import GoogleTokenRequest
from app.services.auth import (
    GoogleAuthError,
    build_dev_user,
    build_login_response,
    get_auth_config,
    get_authenticated_user,
    is_dev,
    verify_google_credential,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def auth_config():
    return get_auth_config()


@router.get("/session-user")
def session_user(user=Depends(get_authenticated_user)):
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
    # In dev the dev session is DAI team; see services.auth.resolve_role.
    return build_login_response(
        user,
        message="Usuario de desarrollo validado.",
        next_step="Solo disponible con APP_ENV=dev; en producción se usa Google.",
    )


@router.post("/google/verify")
def verify_google_login(payload: GoogleTokenRequest):
    try:
        user = verify_google_credential(payload.credential)
    except GoogleAuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    return build_login_response(
        user,
        message="Usuario autenticado con Google.",
        next_step="Sesión activa para la Bóveda DAI.",
    )
