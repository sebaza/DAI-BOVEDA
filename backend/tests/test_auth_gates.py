"""Access gates of Boveda DAI: allowlist-only, fail closed, writes reserved to the team.

These tests run the real FastAPI app (``app.main``) against the throwaway SQLite
database that ``conftest.py`` forces, and mint session tokens with the same code the
login endpoints use.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.schemas import AuthUser
from app.services import auth as auth_service
from app.services.percepcion.eventos import TIPOS_EVENTO

LECTOR = "lector@ucn.cl"
EQUIPO = "equipo@ucn.cl"
AJENO = "cualquiera@ucn.cl"  # a valid *.ucn.cl account that is NOT allowlisted


@pytest.fixture()
def settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "dev")
    monkeypatch.setattr(s, "boveda_allowed_emails", [LECTOR])
    monkeypatch.setattr(s, "boveda_team_emails", [EQUIPO])
    monkeypatch.setattr(s, "tasks_trigger_token", "")
    return s


@pytest.fixture()
def client(settings):
    with TestClient(app) as c:  # context manager => lifespan => create_all
        yield c


def _token(email: str, auth_mode: str = "google") -> str:
    """A correctly SIGNED session for `email`, exactly as login would mint it. The role is
    not part of the token: the server re-resolves it from the allowlists."""
    user = AuthUser(email=email, name=email, auth_mode=auth_mode)
    return auth_service.build_login_response(user, message="", next_step="").session_token


def _h(email: str, auth_mode: str = "google") -> dict:
    return {"Authorization": f"Bearer {_token(email, auth_mode)}"}


def _evento_body() -> dict:
    return {
        "nombre": "Evento de prueba",
        "tipo": TIPOS_EVENTO[0]["tipo"],
        "fecha_inicio": "2026-05-04",
        "descripcion": "creado por un test",
    }


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_percepcion_read_without_token_is_401(client):
    assert client.get("/percepcion/filtros").status_code == 401


def test_percepcion_read_with_garbage_or_tampered_token_is_401(client):
    assert client.get("/percepcion/filtros", headers={"Authorization": "Bearer nope"}).status_code == 401
    good = _token(LECTOR)
    payload, sig = good.split(".", 1)
    forged = f"{payload}.{'A' * len(sig)}"
    assert client.get("/percepcion/filtros", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_unlisted_ucn_account_cannot_read(client):
    """Being a valid institutional account is NOT enough: allowlist only."""
    assert client.get("/percepcion/filtros", headers=_h(AJENO)).status_code == 403
    assert client.get("/auth/session-user", headers=_h(AJENO)).status_code == 403


def test_reader_can_read(client):
    r = client.get("/percepcion/filtros", headers=_h(LECTOR))
    assert r.status_code == 200
    me = client.get("/auth/session-user", headers=_h(LECTOR)).json()
    assert me["role"] == "lector" and me["allowed"] is True


def test_team_can_read_without_being_in_the_reader_list(client):
    assert client.get("/percepcion/filtros", headers=_h(EQUIPO)).status_code == 200
    assert client.get("/auth/session-user", headers=_h(EQUIPO)).json()["role"] == "equipo"


def test_email_match_is_case_insensitive(client):
    assert client.get("/percepcion/filtros", headers=_h("Lector@UCN.cl")).status_code == 200


def test_empty_allowlists_nobody_gets_in(client, monkeypatch, settings):
    """Fail closed. A previously valid token stops working the moment the lists are empty."""
    token = _h(LECTOR)
    monkeypatch.setattr(settings, "boveda_allowed_emails", [])
    monkeypatch.setattr(settings, "boveda_team_emails", [])
    assert client.get("/percepcion/filtros", headers=token).status_code == 403
    assert client.get("/percepcion/filtros", headers=_h(EQUIPO)).status_code == 403


def test_role_is_not_taken_from_the_token(client):
    """A reader cannot promote itself by editing the payload: the signature breaks, and
    even a signed payload carrying role=equipo is ignored (the role is never read)."""
    user = AuthUser(email=LECTOR, name="x", auth_mode="google")
    resp = auth_service.build_login_response(user, message="", next_step="")
    payload_b64, _sig = resp.session_token.split(".", 1)
    payload = json.loads(auth_service._b64url_decode(payload_b64))
    payload["role"] = "equipo"
    evil_b64 = auth_service._b64url_encode(json.dumps(payload).encode())
    signed = f"{evil_b64}.{auth_service._sign_session_payload(evil_b64)}"
    r = client.post("/percepcion/eventos", json=_evento_body(), headers={"Authorization": f"Bearer {signed}"})
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# Writes: team only
# --------------------------------------------------------------------------- #
def test_write_without_token_is_401(client):
    assert client.post("/percepcion/eventos", json=_evento_body()).status_code == 401


def test_reader_cannot_write_events(client):
    h = _h(LECTOR)
    assert client.post("/percepcion/eventos", json=_evento_body(), headers=h).status_code == 403
    assert client.put("/percepcion/eventos/1", json=_evento_body(), headers=h).status_code == 403
    assert client.delete("/percepcion/eventos/1", headers=h).status_code == 403


def test_reader_cannot_write_curation(client):
    h = _h(LECTOR)
    for path in (
        "/percepcion/curacion/tema",
        "/percepcion/curacion/publicacion/1",
        "/percepcion/curacion/comentario/1",
        "/percepcion/curacion/sentimiento/1",
        "/percepcion/curacion/tema/1",
        "/percepcion/curacion/postura/1",
        "/percepcion/curacion/emocion/1",
    ):
        assert client.post(path, json={}, headers=h).status_code == 403, path


def test_unlisted_account_cannot_write(client):
    assert client.post("/percepcion/eventos", json=_evento_body(), headers=_h(AJENO)).status_code == 403


def test_team_can_write_events_roundtrip(client):
    h = _h(EQUIPO)
    created = client.post("/percepcion/eventos", json=_evento_body(), headers=h)
    assert created.status_code == 200, created.text
    evento_id = created.json()["id"]
    assert client.put(f"/percepcion/eventos/{evento_id}", json=_evento_body(), headers=h).status_code == 200
    assert client.delete(f"/percepcion/eventos/{evento_id}", headers=h).status_code == 200


def test_reader_cannot_force_the_paid_weekly_summary(client):
    """GET, but it re-pays the model and writes: reserved to the team."""
    assert client.get("/percepcion/resumen-semanal?forzar=true", headers=_h(LECTOR)).status_code == 403
    # the team passes the gate (it then degrades by itself without an API key / data)
    assert client.get("/percepcion/resumen-semanal?forzar=true", headers=_h(EQUIPO)).status_code != 403


# --------------------------------------------------------------------------- #
# dev-login
# --------------------------------------------------------------------------- #
def test_dev_login_works_in_dev_even_with_empty_allowlists(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "boveda_allowed_emails", [])
    monkeypatch.setattr(settings, "boveda_team_emails", [])
    r = client.get("/auth/dev-login")
    assert r.status_code == 200
    token = r.json()["session_token"]
    assert client.get("/percepcion/filtros", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/auth/config").json()["dev_login_enabled"] is True


def test_dev_login_does_not_exist_outside_dev(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "app_env", "prod")
    assert client.get("/auth/dev-login").status_code == 404
    assert client.get("/auth/config").json()["dev_login_enabled"] is False


def test_dev_token_is_worthless_outside_dev(client, monkeypatch, settings):
    r = client.get("/auth/dev-login", params={"email": "intruso@example.com"})
    token = r.json()["session_token"]
    monkeypatch.setattr(settings, "app_env", "prod")
    assert client.get("/percepcion/filtros", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_get_settings_refuses_default_secret_outside_dev(monkeypatch):
    """The boot check lives in get_settings(): with APP_ENV != dev and the default
    (or empty) secret it must raise instead of signing sessions with a public key."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_SESSION_SECRET", "boveda-dai-dev-session-secret")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            get_settings()
        monkeypatch.setenv("APP_SESSION_SECRET", "")
        get_settings.cache_clear()
        with pytest.raises(RuntimeError):
            get_settings()
        monkeypatch.setenv("APP_SESSION_SECRET", "a-real-strong-secret")
        get_settings.cache_clear()
        assert get_settings().app_env == "prod"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        get_settings()  # re-prime with the test environment


# --------------------------------------------------------------------------- #
# Google sign-in must not mint sessions for unlisted accounts
# --------------------------------------------------------------------------- #
def test_google_verify_rejects_unlisted_account(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "google_client_id", "client-id.apps.googleusercontent.com")
    import google.oauth2.id_token as id_token

    monkeypatch.setattr(
        id_token, "verify_oauth2_token",
        lambda *a, **k: {"email": AJENO, "email_verified": True, "name": "Ajeno"},
    )
    r = client.post("/auth/google/verify", json={"credential": "x"})
    assert r.status_code == 401

    monkeypatch.setattr(
        id_token, "verify_oauth2_token",
        lambda *a, **k: {"email": LECTOR, "email_verified": True, "name": "Lector"},
    )
    ok = client.post("/auth/google/verify", json={"credential": "x"})
    assert ok.status_code == 200
    assert ok.json()["user"]["role"] == "lector"


def test_google_verify_rejects_unverified_email(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "google_client_id", "client-id.apps.googleusercontent.com")
    import google.oauth2.id_token as id_token

    monkeypatch.setattr(
        id_token, "verify_oauth2_token",
        lambda *a, **k: {"email": LECTOR, "email_verified": False},
    )
    assert client.post("/auth/google/verify", json={"credential": "x"}).status_code == 401


# --------------------------------------------------------------------------- #
# Scheduled task trigger
# --------------------------------------------------------------------------- #
def test_task_trigger_disabled_without_configured_token(client):
    r = client.post("/tasks/run/percepcion-resumen", headers={"X-Tasks-Token": "anything"})
    assert r.status_code == 403


def test_task_trigger_rejects_wrong_token_and_session_auth(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "tasks_trigger_token", "s3cret")
    assert client.post("/tasks/run/percepcion-resumen").status_code == 403
    assert client.post("/tasks/run/percepcion-resumen", headers={"X-Tasks-Token": "wrong"}).status_code == 403
    # a team session is NOT a substitute for the trigger token
    assert client.post("/tasks/run/percepcion-resumen", headers=_h(EQUIPO)).status_code == 403


def test_task_trigger_with_valid_token_runs(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "tasks_trigger_token", "s3cret")
    from app.services.percepcion import resumen_llm

    monkeypatch.setattr(
        resumen_llm, "generar_tras_ingesta",
        lambda semanas=1, forzar=False: {"status": "ok", "semanas_pedidas": semanas, "forzar": forzar},
    )
    r = client.post("/tasks/run/percepcion-resumen?semanas=2", headers={"X-Tasks-Token": "s3cret"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "semanas_pedidas": 2, "forzar": False}
    # legacy Torre prefix keeps working for a worker that has not switched yet
    legacy = client.post("/ai-tasks/run/percepcion-resumen", headers={"X-Tasks-Token": "s3cret"})
    assert legacy.status_code == 200
