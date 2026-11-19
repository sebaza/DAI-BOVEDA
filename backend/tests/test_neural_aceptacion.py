"""Acceptance gate of DAI Neural: every data route answers 403 until the CURRENT confidentiality text is accepted.

Runs the real app against the in-memory access adapter; no Neural database is needed because the gate fires
before any data dependency (NEURAL_DATABASE_URL is empty in the suite: a request that got past the gate would
answer 503, never 403).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.schemas import AuthUser
from app.services import accesos
from app.services import auth as auth_service
from app.services.accesos import AccessDatabaseError, InMemoryAccessRepository
from app.services.neural import aceptacion

LECTOR = "lector@ucn.cl"
AJENO = "cualquiera@ucn.cl"
VIEJA = "2025-01-01"


@pytest.fixture()
def repo(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "dev")
    monkeypatch.setattr(s, "boveda_database_url", "postgresql+psycopg://configurada-solo-en-test")
    r = InMemoryAccessRepository()
    r.add_module("neural", "DAI Neural")
    r.grant_access("neural", LECTOR, "lector", by="test")
    accesos.configure(r)
    yield r
    accesos.reset()


@pytest.fixture()
def client(repo):
    with TestClient(app) as c:
        yield c


def _h(email: str) -> dict:
    user = AuthUser(email=email, name=email, auth_mode="google")
    token = auth_service.build_login_response(user, message="", next_step="").session_token
    return {"Authorization": f"Bearer {token}"}


def test_get_acceptance_returns_text_version_and_false_before_accepting(client):
    r = client.get("/neural/aceptacion", headers=_h(LECTOR))
    assert r.status_code == 200
    assert r.json() == {"version": "2026-11-18", "texto": aceptacion.TEXTO, "aceptada": False}
    assert aceptacion.TEXTO.startswith("Declaro que soy una persona de confianza de la Dirección de Análisis Institucional")
    assert "Ley 19.628" in aceptacion.TEXTO and "Ley 21.719" in aceptacion.TEXTO


def test_post_acceptance_records_and_unlocks_routes(client, repo):
    h = _h(LECTOR)
    assert client.get("/neural/programas", headers=h).status_code == 403
    assert client.post("/neural/aceptacion", json={"version": aceptacion.VERSION}, headers=h).status_code == 204
    assert repo.acepto("neural", LECTOR, aceptacion.VERSION) is True
    assert client.get("/neural/aceptacion", headers=h).json()["aceptada"] is True
    # Past the gate: the (empty in tests) Neural database is what answers now.
    assert client.get("/neural/programas", headers=h).status_code == 503


def test_post_with_old_version_returns_409_and_records_nothing(client, repo):
    r = client.post("/neural/aceptacion", json={"version": VIEJA}, headers=_h(LECTOR))
    assert r.status_code == 409
    assert repo.acepto("neural", LECTOR, VIEJA) is False
    assert repo.acepto("neural", LECTOR, aceptacion.VERSION) is False


def test_acceptance_endpoints_need_session_and_module(client):
    assert client.get("/neural/aceptacion").status_code == 401
    assert client.get("/neural/aceptacion", headers=_h(AJENO)).status_code == 403
    assert client.post("/neural/aceptacion", json={"version": aceptacion.VERSION}, headers=_h(AJENO)).status_code == 403


def _recorrer(rutas):
    """(path, methods) of every route, also through the lazily included routers of recent FastAPI versions."""
    for r in rutas:
        if hasattr(r, "effective_route_contexts"):
            yield from ((c.path, c.original_route.methods) for c in r.effective_route_contexts())
        elif hasattr(r, "path"):
            yield r.path, getattr(r, "methods", None) or set()


def _rutas_neural():
    todas = {(p, frozenset(m)) for p, m in _recorrer(app.routes)}
    rutas = [(p, set(m)) for p, m in todas if p.startswith("/neural") and p != "/neural/aceptacion"]
    # Cross-check against the public OpenAPI document: no documented neural route may be missing from the walk.
    documentadas = {p for p in app.openapi()["paths"] if p.startswith("/neural") and p != "/neural/aceptacion"}
    assert documentadas <= {p for p, _ in rutas}
    return rutas


def test_every_neural_route_requires_current_acceptance(client):
    rutas = _rutas_neural()
    assert len(rutas) >= 10, "the route walk found too few neural routes"
    for ruta, metodos in rutas:
        path = ruta.replace("{", "").replace("}", "")  # e.g. /neural/programa/cod/cohortes
        for metodo in sorted(metodos - {"HEAD", "OPTIONS"}):
            r = client.request(metodo, path, headers=_h(LECTOR))
            assert r.status_code == 403, f"{metodo} {ruta} -> {r.status_code}"
            assert r.json()["detail"] == {"codigo": "aceptacion_requerida", "version": aceptacion.VERSION}, ruta


def test_older_version_acceptance_does_not_unlock(client, repo):
    repo.registrar_aceptacion("neural", LECTOR, VIEJA)
    r = client.get("/neural/programas", headers=_h(LECTOR))
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "aceptacion_requerida"
    assert client.get("/neural/aceptacion", headers=_h(LECTOR)).json()["aceptada"] is False


def test_acceptance_of_one_person_does_not_unlock_another(client, repo):
    repo.grant_access("neural", "otro@ucn.cl", "lector", by="test")
    repo.registrar_aceptacion("neural", LECTOR, aceptacion.VERSION)
    assert client.get("/neural/programas", headers=_h("otro@ucn.cl")).status_code == 403


def test_gate_fails_closed_when_access_store_errors(client, repo):
    repo.registrar_aceptacion("neural", LECTOR, aceptacion.VERSION)
    repo.fallar_aceptacion = True
    h = _h(LECTOR)
    r = client.get("/neural/programas", headers=h)
    assert r.status_code in (403, 503)
    # Reading the state and recording it fail closed too: no 2xx, no grant.
    assert client.get("/neural/aceptacion", headers=h).status_code == 503
    assert client.post("/neural/aceptacion", json={"version": aceptacion.VERSION}, headers=h).status_code == 503


def test_failed_recording_does_not_unlock(client, repo):
    repo.fallar_aceptacion = True
    assert client.post("/neural/aceptacion", json={"version": aceptacion.VERSION}, headers=_h(LECTOR)).status_code == 503
    repo.fallar_aceptacion = False
    assert client.get("/neural/programas", headers=_h(LECTOR)).status_code == 403


def test_deny_all_repository_never_grants():
    r = accesos.DenyAllAccessRepository("sin base")
    with pytest.raises(AccessDatabaseError):
        r.acepto("neural", LECTOR, aceptacion.VERSION)
    with pytest.raises(AccessDatabaseError):
        r.registrar_aceptacion("neural", LECTOR, aceptacion.VERSION)
