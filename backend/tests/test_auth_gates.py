"""Access gates of Boveda DAI: per-module lists in the database, global admins, fail closed.

These tests run the real FastAPI app (``app.main``) against the throwaway SQLite database
that ``conftest.py`` forces for the Percepcion data, and swap the access adapter for the
in-memory fake (``accesos.configure``). Session tokens are minted with the same code the
login endpoints use. Raw-text curation endpoints are stubbed at the service layer: the
subject here is who gets in and what is audited, not the Percepcion data.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.main import app
from app.schemas import AuthUser
from app.services import accesos
from app.services import auth as auth_service
from app.services.accesos import InMemoryAccessRepository, PostgresAccessRepository
from app.services.percepcion import curacion
from app.services.percepcion.eventos import TIPOS_EVENTO

LECTOR = "lector@ucn.cl"
EQUIPO = "equipo@ucn.cl"
ADMIN = "admin@ucn.cl"
AJENO = "cualquiera@ucn.cl"  # a valid *.ucn.cl account with NO access anywhere
DEV = "dev@boveda.local"
URL_CONFIGURADA = "postgresql+psycopg://configurada-solo-en-test"

TEXTO_CRUDO = "texto crudo de un comentario real"


@pytest.fixture()
def settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "dev")
    monkeypatch.setattr(s, "tasks_trigger_token", "")
    monkeypatch.setattr(s, "boveda_database_url", URL_CONFIGURADA)
    return s


@pytest.fixture()
def repo(settings):
    r = InMemoryAccessRepository()
    r.add_module("percepcion", "Termómetro Institucional")
    r.grant_access("percepcion", LECTOR, "lector", by="test")
    r.grant_access("percepcion", EQUIPO, "equipo", by="test")
    r.grant_access("percepcion", DEV, "equipo", by="test")
    r.add_admin(ADMIN, by="test")
    accesos.configure(r)
    yield r
    accesos.reset()


@pytest.fixture()
def client(repo):
    with TestClient(app) as c:  # context manager => lifespan => create_all
        yield c


def _token(email: str, auth_mode: str = "google") -> str:
    """A correctly SIGNED session for `email`, exactly as login would mint it. The role is
    not part of the token: the server re-resolves it from the database on every request."""
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


@pytest.fixture()
def texto_crudo(monkeypatch):
    """Stub the two raw-text curation services with fixed comment ids (11 and 12)."""
    monkeypatch.setattr(
        curacion, "comentarios_a_curar",
        lambda db, **k: {"items": [
            {"id": 11, "texto": TEXTO_CRUDO, "fecha": date(2026, 5, 4), "sentimiento": "NEG",
             "caption": "c", "cuenta": "x"},
            {"id": 12, "texto": TEXTO_CRUDO, "fecha": date(2026, 5, 5), "sentimiento": "POS",
             "caption": "c", "cuenta": "x"},
        ]},
    )
    monkeypatch.setattr(
        curacion, "comentarios_para_scoring",
        lambda db, **k: {"items": [
            {"id": 21, "texto": TEXTO_CRUDO, "fecha": date(2026, 5, 4), "sentimiento": "NEG",
             "sentimiento_label": "Negativo"},
        ], "orden": "duda", "revisados": 0, "pendientes": 1},
    )


RUTAS_TEXTO = ("/percepcion/curacion/comentarios", "/percepcion/curacion/scoring")


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


def test_unknown_account_cannot_read(client):
    """Being a valid institutional account is NOT enough: access lives in the database."""
    assert client.get("/percepcion/filtros", headers=_h(AJENO)).status_code == 403
    assert client.get("/auth/session-user", headers=_h(AJENO)).status_code == 403


def test_reader_can_read_and_sees_its_modules(client):
    assert client.get("/percepcion/filtros", headers=_h(LECTOR)).status_code == 200
    me = client.get("/auth/session-user", headers=_h(LECTOR)).json()
    assert me["role"] == "lector" and me["allowed"] is True and me["is_admin"] is False
    assert me["modulos"] == [{"id": "percepcion", "nombre": "Termómetro Institucional", "rol": "lector"}]


def test_team_can_read(client):
    assert client.get("/percepcion/filtros", headers=_h(EQUIPO)).status_code == 200
    assert client.get("/auth/session-user", headers=_h(EQUIPO)).json()["role"] == "equipo"


def test_admin_opens_every_active_module(client, repo):
    repo.add_module("otro", "Otro módulo")
    assert client.get("/percepcion/filtros", headers=_h(ADMIN)).status_code == 200
    me = client.get("/auth/me", headers=_h(ADMIN)).json()
    assert me["is_admin"] is True and me["role"] == "admin" and me["allowed"] is True
    assert {(m["id"], m["rol"]) for m in me["modulos"]} == {("percepcion", "admin"), ("otro", "admin")}


def test_email_match_is_case_insensitive(client):
    assert client.get("/percepcion/filtros", headers=_h("Lector@UCN.cl")).status_code == 200


def test_access_is_per_module(client, repo):
    """Access to one module is not access to another: a user of 'otro' cannot open Percepcion."""
    repo.add_module("otro", "Otro módulo")
    repo.grant_access("otro", "solo-otro@ucn.cl", "equipo", by="test")
    assert client.get("/percepcion/filtros", headers=_h("solo-otro@ucn.cl")).status_code == 403
    # ...though it is a valid account (it has a module), so the session itself is fine
    me = client.get("/auth/session-user", headers=_h("solo-otro@ucn.cl"))
    assert me.status_code == 200 and [m["id"] for m in me.json()["modulos"]] == ["otro"]


def test_empty_database_nobody_gets_in(client, repo):
    """Fail closed. A previously valid token stops working the moment the rows are gone."""
    token = _h(LECTOR)
    repo.revoke_access("percepcion", LECTOR)
    repo.revoke_access("percepcion", EQUIPO)
    repo.remove_admin(ADMIN)
    assert client.get("/percepcion/filtros", headers=token).status_code == 403
    assert client.get("/percepcion/filtros", headers=_h(EQUIPO)).status_code == 403
    assert client.get("/percepcion/filtros", headers=_h(ADMIN)).status_code == 403


def test_inactive_module_denies_everyone_even_admins(client, repo):
    repo.set_module_active("percepcion", False)
    for email in (LECTOR, EQUIPO, ADMIN):
        assert client.get("/percepcion/filtros", headers=_h(email)).status_code == 403, email
    assert client.get("/percepcion/curacion/comentarios", headers=_h(ADMIN)).status_code == 403
    # reader/team have no other module: not even a session. The admin keeps a session but sees none.
    assert client.get("/auth/session-user", headers=_h(LECTOR)).status_code == 403
    me = client.get("/auth/session-user", headers=_h(ADMIN))
    assert me.status_code == 200 and me.json()["modulos"] == []


def test_database_error_denies_access(client):
    """A database that cannot be reached must DENY, never allow."""
    @contextmanager
    def caida():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield  # pragma: no cover

    accesos.configure(PostgresAccessRepository(caida))
    for email in (LECTOR, EQUIPO, ADMIN):
        assert client.get("/percepcion/filtros", headers=_h(email)).status_code == 403, email
        assert client.get("/auth/session-user", headers=_h(email)).status_code == 403, email


def test_role_is_not_taken_from_the_token(client):
    """A reader cannot promote itself by editing the payload: the signature breaks, and
    even a signed payload carrying role=admin is ignored (the role is never read)."""
    user = AuthUser(email=LECTOR, name="x", auth_mode="google")
    resp = auth_service.build_login_response(user, message="", next_step="")
    payload_b64, _sig = resp.session_token.split(".", 1)
    payload = json.loads(auth_service._b64url_decode(payload_b64))
    payload.update({"role": "admin", "is_admin": True})
    evil_b64 = auth_service._b64url_encode(json.dumps(payload).encode())
    signed = f"{evil_b64}.{auth_service._sign_session_payload(evil_b64)}"
    h = {"Authorization": f"Bearer {signed}"}
    assert client.post("/percepcion/eventos", json=_evento_body(), headers=h).status_code == 403
    assert client.get(RUTAS_TEXTO[0], headers=h).status_code == 403


def test_revoking_an_admin_takes_effect_on_the_next_request(client, repo):
    h = _h(ADMIN)
    assert client.get("/percepcion/filtros", headers=h).status_code == 200
    repo.remove_admin(ADMIN)
    assert client.get("/percepcion/filtros", headers=h).status_code == 403


# --------------------------------------------------------------------------- #
# Writes: team (and admins) only
# --------------------------------------------------------------------------- #
def test_write_without_token_is_401(client):
    assert client.post("/percepcion/eventos", json=_evento_body()).status_code == 401


def test_reader_cannot_write_events(client):
    h = _h(LECTOR)
    assert client.post("/percepcion/eventos", json=_evento_body(), headers=h).status_code == 403
    assert client.put("/percepcion/eventos/1", json=_evento_body(), headers=h).status_code == 403
    assert client.delete("/percepcion/eventos/1", headers=h).status_code == 403


RUTAS_CURACION_ESCRITURA = (
    "/percepcion/curacion/tema",
    "/percepcion/curacion/publicacion/1",
    "/percepcion/curacion/comentario/1",
    "/percepcion/curacion/sentimiento/1",
    "/percepcion/curacion/tema/1",
    "/percepcion/curacion/postura/1",
    "/percepcion/curacion/emocion/1",
)


def test_reader_cannot_write_curation(client):
    for path in RUTAS_CURACION_ESCRITURA:
        assert client.post(path, json={}, headers=_h(LECTOR)).status_code == 403, path


def test_team_cannot_write_curation_it_is_an_admin_feature(client):
    for path in RUTAS_CURACION_ESCRITURA:
        assert client.post(path, json={}, headers=_h(EQUIPO)).status_code == 403, path


def test_admin_passes_the_curation_write_gate(client):
    """Not 401/403: the (empty) body then fails validation, which proves the gate let it in."""
    for path in RUTAS_CURACION_ESCRITURA:
        assert client.post(path, json={}, headers=_h(ADMIN)).status_code == 422, path


def test_unknown_account_cannot_write(client):
    assert client.post("/percepcion/eventos", json=_evento_body(), headers=_h(AJENO)).status_code == 403


def test_team_can_write_events_roundtrip(client):
    h = _h(EQUIPO)
    created = client.post("/percepcion/eventos", json=_evento_body(), headers=h)
    assert created.status_code == 200, created.text
    evento_id = created.json()["id"]
    assert client.put(f"/percepcion/eventos/{evento_id}", json=_evento_body(), headers=h).status_code == 200
    assert client.delete(f"/percepcion/eventos/{evento_id}", headers=h).status_code == 200


def test_admin_can_write_events(client):
    created = client.post("/percepcion/eventos", json=_evento_body(), headers=_h(ADMIN))
    assert created.status_code == 200, created.text


def test_reader_cannot_force_the_paid_weekly_summary(client):
    """GET, but it re-pays the model and writes: reserved to the team."""
    assert client.get("/percepcion/resumen-semanal?forzar=true", headers=_h(LECTOR)).status_code == 403
    # the team passes the gate (it then degrades by itself without an API key / data)
    assert client.get("/percepcion/resumen-semanal?forzar=true", headers=_h(EQUIPO)).status_code != 403
    # ...and a reader can still read the cached one
    assert client.get("/percepcion/resumen-semanal", headers=_h(LECTOR)).status_code != 403


# --------------------------------------------------------------------------- #
# Raw comment text: admins only, and every view is audited
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ruta", RUTAS_TEXTO)
def test_raw_text_requires_a_session(client, ruta):
    assert client.get(ruta).status_code == 401


@pytest.mark.parametrize("ruta", RUTAS_TEXTO)
def test_reader_and_team_cannot_fetch_raw_text(client, repo, texto_crudo, ruta):
    for email in (LECTOR, EQUIPO, AJENO):
        r = client.get(ruta, headers=_h(email))
        assert r.status_code == 403, (email, r.status_code)
        assert TEXTO_CRUDO not in r.text
    assert repo.vistas == []  # nothing was served, nothing is audited


def test_admin_fetches_raw_text_and_the_view_is_audited(client, repo, texto_crudo):
    r = client.get(RUTAS_TEXTO[0], headers=_h(ADMIN))
    assert r.status_code == 200 and r.json()["items"][0]["texto"] == TEXTO_CRUDO
    r2 = client.get(RUTAS_TEXTO[1] + "?limite=5", headers=_h("ADMIN@ucn.cl"))
    assert r2.status_code == 200 and r2.json()["items"][0]["id"] == 21

    assert len(repo.vistas) == 2
    primera, segunda = repo.vistas
    assert primera["admin_email"] == ADMIN and primera["modulo_id"] == "percepcion"
    assert primera["endpoint"] == "/percepcion/curacion/comentarios"
    assert primera["comentario_ids"] == [11, 12]
    assert segunda["endpoint"] == "/percepcion/curacion/scoring"
    assert segunda["comentario_ids"] == [21]


def test_a_view_with_no_comments_is_not_recorded(client, repo, monkeypatch):
    monkeypatch.setattr(curacion, "comentarios_a_curar", lambda db, **k: {"items": []})
    assert client.get(RUTAS_TEXTO[0], headers=_h(ADMIN)).status_code == 200
    assert repo.vistas == []


@pytest.mark.parametrize("ruta", RUTAS_TEXTO)
def test_if_the_audit_fails_no_text_is_delivered(client, repo, texto_crudo, ruta):
    repo.fallar_auditoria = True
    r = client.get(ruta, headers=_h(ADMIN))
    assert r.status_code >= 500
    assert TEXTO_CRUDO not in r.text
    assert repo.vistas == []


def test_curation_reads_without_raw_text_are_admin_only_too(client):
    for path in ("/percepcion/curacion/temas", "/percepcion/curacion/calidad",
                 "/percepcion/curacion/correcciones", "/percepcion/curacion/publicaciones",
                 "/percepcion/curacion/scoring/opciones"):
        assert client.get(path, headers=_h(EQUIPO)).status_code == 403, path
        assert client.get(path, headers=_h(ADMIN)).status_code == 200, path


# --------------------------------------------------------------------------- #
# dev-login
# --------------------------------------------------------------------------- #
def test_dev_login_resolves_access_from_the_database(client):
    r = client.get("/auth/dev-login")
    assert r.status_code == 200
    body = r.json()
    assert [m["id"] for m in body["user"]["modulos"]] == ["percepcion"]
    assert body["user"]["role"] == "equipo"
    token = body["session_token"]
    assert client.get("/percepcion/filtros", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/auth/config").json()["dev_login_enabled"] is True


def test_dev_login_for_an_account_without_access_is_403(client):
    assert client.get("/auth/dev-login", params={"email": "intruso@example.com"}).status_code == 403


def test_dev_login_without_database_url_issues_a_session_with_no_modules(client, monkeypatch, settings):
    """Dev with BOVEDA_DATABASE_URL empty: the session exists, but denies everything."""
    monkeypatch.setattr(settings, "boveda_database_url", "")
    accesos.reset()  # drop the fake: the null adapter built from an empty URL denies everyone
    r = client.get("/auth/dev-login")
    assert r.status_code == 200
    assert r.json()["user"]["modulos"] == [] and r.json()["user"]["allowed"] is False
    h = {"Authorization": f"Bearer {r.json()['session_token']}"}
    me = client.get("/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["modulos"] == [] and me.json()["is_admin"] is False
    assert client.get("/percepcion/filtros", headers=h).status_code == 403


def test_dev_login_does_not_exist_outside_dev(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "app_env", "prod")
    assert client.get("/auth/dev-login").status_code == 404
    assert client.get("/auth/config").json()["dev_login_enabled"] is False


def test_dev_token_is_worthless_outside_dev(client, monkeypatch, settings):
    """Even if the dev email happens to have access in the database."""
    token = client.get("/auth/dev-login").json()["session_token"]
    monkeypatch.setattr(settings, "app_env", "prod")
    assert client.get("/percepcion/filtros", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_get_settings_refuses_default_secret_outside_dev(monkeypatch):
    """The boot check lives in get_settings(): with APP_ENV != dev and the default
    (or empty) secret it must raise instead of signing sessions with a public key."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("BOVEDA_DATABASE_URL", URL_CONFIGURADA)
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


def test_missing_app_env_means_production(monkeypatch):
    """A deploy that forgets APP_ENV must not silently become dev (dev-login enabled):
    unset or blank APP_ENV is production, so the boot checks apply."""
    monkeypatch.setenv("BOVEDA_DATABASE_URL", URL_CONFIGURADA)
    monkeypatch.setenv("APP_SESSION_SECRET", "boveda-dai-dev-session-secret")
    for valor in (None, "", "   "):
        if valor is None:
            monkeypatch.delenv("APP_ENV", raising=False)
        else:
            monkeypatch.setenv("APP_ENV", valor)
        get_settings.cache_clear()
        try:
            with pytest.raises(RuntimeError):
                get_settings()
        finally:
            get_settings.cache_clear()
    monkeypatch.setenv("APP_SESSION_SECRET", "a-real-strong-secret")
    monkeypatch.delenv("APP_ENV", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().app_env != "dev"
        assert auth_service.is_dev() is False
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        get_settings()


def test_get_settings_refuses_empty_database_url_outside_dev(monkeypatch):
    """Without the access database nobody could be authorised: refuse to boot instead of
    running a deployment that denies every user."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_SESSION_SECRET", "a-real-strong-secret")
    monkeypatch.setenv("BOVEDA_DATABASE_URL", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="BOVEDA_DATABASE_URL"):
            get_settings()
        monkeypatch.setenv("BOVEDA_DATABASE_URL", "   ")
        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="BOVEDA_DATABASE_URL"):
            get_settings()
        # ...but dev may run without it (and then denies everyone)
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("BOVEDA_DATABASE_URL", "")
        get_settings.cache_clear()
        assert get_settings().boveda_database_url == ""
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        get_settings()


def test_the_old_env_allowlists_are_gone(monkeypatch):
    """BOVEDA_ALLOWED_EMAILS / BOVEDA_TEAM_EMAILS no longer grant anything (no fallback)."""
    monkeypatch.setenv("BOVEDA_ALLOWED_EMAILS", "viejo@ucn.cl")
    monkeypatch.setenv("BOVEDA_TEAM_EMAILS", "viejo@ucn.cl")
    from app.config import Settings

    s = Settings()
    assert not hasattr(s, "boveda_allowed_emails") and not hasattr(s, "boveda_team_emails")


# --------------------------------------------------------------------------- #
# Google sign-in must not mint sessions for accounts without access
# --------------------------------------------------------------------------- #
def _google_devuelve(monkeypatch, settings, claims: dict):
    monkeypatch.setattr(settings, "google_client_id", "client-id.apps.googleusercontent.com")
    import google.oauth2.id_token as id_token

    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *a, **k: claims)


def test_google_verify_rejects_account_without_access(client, monkeypatch, settings):
    _google_devuelve(monkeypatch, settings, {"email": AJENO, "email_verified": True, "name": "Ajeno"})
    r = client.post("/auth/google/verify", json={"credential": "x"})
    assert r.status_code == 403
    assert "session_token" not in r.text


def test_google_verify_issues_a_session_with_modules(client, monkeypatch, settings):
    _google_devuelve(monkeypatch, settings, {"email": LECTOR, "email_verified": True, "name": "Lector"})
    ok = client.post("/auth/google/verify", json={"credential": "x"})
    assert ok.status_code == 200
    user = ok.json()["user"]
    assert user["role"] == "lector" and user["is_admin"] is False
    assert [m["id"] for m in user["modulos"]] == ["percepcion"]


def test_google_verify_lets_an_admin_in(client, monkeypatch, settings):
    _google_devuelve(monkeypatch, settings, {"email": ADMIN, "email_verified": True, "name": "Admin"})
    ok = client.post("/auth/google/verify", json={"credential": "x"})
    assert ok.status_code == 200 and ok.json()["user"]["is_admin"] is True


def test_google_verify_lets_an_admin_in_even_with_no_active_module(client, repo, monkeypatch, settings):
    repo.set_module_active("percepcion", False)
    _google_devuelve(monkeypatch, settings, {"email": ADMIN, "email_verified": True, "name": "Admin"})
    ok = client.post("/auth/google/verify", json={"credential": "x"})
    assert ok.status_code == 200 and ok.json()["user"]["modulos"] == []


def test_google_verify_rejects_a_user_whose_only_module_is_inactive(client, repo, monkeypatch, settings):
    repo.set_module_active("percepcion", False)
    _google_devuelve(monkeypatch, settings, {"email": LECTOR, "email_verified": True, "name": "Lector"})
    assert client.post("/auth/google/verify", json={"credential": "x"}).status_code == 403


def test_google_verify_rejects_unverified_email(client, monkeypatch, settings):
    _google_devuelve(monkeypatch, settings, {"email": LECTOR, "email_verified": False})
    assert client.post("/auth/google/verify", json={"credential": "x"}).status_code == 401


def test_google_verify_rejects_an_invalid_token(client, monkeypatch, settings):
    monkeypatch.setattr(settings, "google_client_id", "client-id.apps.googleusercontent.com")
    import google.oauth2.id_token as id_token

    def boom(*a, **k):
        raise ValueError("token inválido")

    monkeypatch.setattr(id_token, "verify_oauth2_token", boom)
    assert client.post("/auth/google/verify", json={"credential": "x"}).status_code == 401


# --------------------------------------------------------------------------- #
# Reusable dependencies
# --------------------------------------------------------------------------- #
def test_require_module_and_require_admin_dependencies(repo):
    """The factory is reusable by future modules: 'percepcion' is just a module id."""
    from fastapi import Depends, FastAPI

    probe = FastAPI()

    @probe.get("/leer")
    def leer(user=Depends(auth_service.require_module("percepcion"))):
        return {"ok": user.email}

    @probe.post("/escribir")
    def escribir(user=Depends(auth_service.require_module("percepcion", write=True))):
        return {"ok": user.email}

    @probe.get("/otro")
    def otro(user=Depends(auth_service.require_module("otro"))):
        return {"ok": user.email}

    @probe.get("/admin")
    def solo_admin(user=Depends(auth_service.require_admin)):
        return {"ok": user.email}

    with TestClient(probe) as c:
        assert c.get("/leer").status_code == 401
        assert c.get("/leer", headers=_h(LECTOR)).status_code == 200
        assert c.get("/leer", headers=_h(AJENO)).status_code == 403
        assert c.post("/escribir", headers=_h(LECTOR)).status_code == 403
        assert c.post("/escribir", headers=_h(EQUIPO)).status_code == 200
        assert c.post("/escribir", headers=_h(ADMIN)).status_code == 200
        assert c.get("/otro", headers=_h(EQUIPO)).status_code == 403  # unknown module => deny
        assert c.get("/otro", headers=_h(ADMIN)).status_code == 403  # ...even to admins
        assert c.get("/admin", headers=_h(EQUIPO)).status_code == 403
        assert c.get("/admin", headers=_h(ADMIN)).status_code == 200


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
    # a team or admin session is NOT a substitute for the trigger token
    assert client.post("/tasks/run/percepcion-resumen", headers=_h(EQUIPO)).status_code == 403
    assert client.post("/tasks/run/percepcion-resumen", headers=_h(ADMIN)).status_code == 403


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
