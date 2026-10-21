"""Behavioural contract of the access port, shared by every adapter.

``test_accesos_memoria.py`` runs it against the in-memory fake (always) and
``test_accesos_postgres.py`` against the real PostgreSQL adapter (only when
``BOVEDA_TEST_DATABASE_URL`` is set). A subclass provides the ``entorno`` fixture.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest

from app.schemas import AppRole
from app.services.accesos import (
    AuditError,
    InvalidEmailError,
    InvalidRoleError,
    UnknownModuleError,
)

MOD = "mod_a"
MOD_B = "mod_b"
INACTIVO = "mod_off"
EMAIL = "persona@ucn.cl"


@dataclass
class Entorno:
    repo: object  # AccessRepository + AccessManager
    crear_modulo: Callable[..., None]  # (id, nombre, activo=True)
    leer_auditoria: Callable[[], list[dict]]  # [{admin_email, modulo_id, endpoint, comentario_ids}]


class ContratoAccesos:
    @pytest.fixture()
    def env(self, entorno: Entorno) -> Entorno:
        entorno.crear_modulo(MOD, "Módulo A")
        entorno.crear_modulo(MOD_B, "Módulo B")
        entorno.crear_modulo(INACTIVO, "Módulo apagado", activo=False)
        return entorno

    # --- unknown email: fail closed ---
    def test_unknown_email_gets_nothing(self, env):
        r = env.repo
        assert r.is_admin(EMAIL) is False
        assert r.role_for(EMAIL, MOD) is None
        assert r.modules_for(EMAIL) == []

    def test_empty_email_gets_nothing(self, env):
        assert env.repo.is_admin("") is False
        assert env.repo.role_for("   ", MOD) is None
        assert env.repo.modules_for("") == []

    # --- per-module access ---
    def test_reader_and_team_roles(self, env):
        r = env.repo
        r.grant_access(MOD, EMAIL, "lector", by="t")
        r.grant_access(MOD_B, EMAIL, "equipo", by="t")
        assert r.role_for(EMAIL, MOD) == AppRole.lector
        assert r.role_for(EMAIL, MOD_B) == AppRole.equipo
        assert r.role_for(EMAIL, "inexistente") is None
        mods = {m.id: (m.nombre, m.rol) for m in r.modules_for(EMAIL)}
        assert mods == {MOD: ("Módulo A", AppRole.lector), MOD_B: ("Módulo B", AppRole.equipo)}

    def test_email_is_normalized_everywhere(self, env):
        r = env.repo
        r.grant_access(MOD, "  Persona@UCN.cl ", "lector", by="t")
        assert r.role_for("PERSONA@ucn.CL", MOD) == AppRole.lector
        assert [m.id for m in r.modules_for(" persona@ucn.cl")] == [MOD]

    def test_grant_is_an_upsert_of_the_role(self, env):
        r = env.repo
        r.grant_access(MOD, EMAIL, "lector", by="t")
        r.grant_access(MOD, EMAIL, "equipo", by="t")
        assert r.role_for(EMAIL, MOD) == AppRole.equipo
        assert len(r.list_all(MOD).accesos) == 1

    def test_revoke_access(self, env):
        r = env.repo
        r.grant_access(MOD, EMAIL, "lector", by="t")
        assert r.revoke_access(MOD, EMAIL) is True
        assert r.role_for(EMAIL, MOD) is None
        assert r.revoke_access(MOD, EMAIL) is False

    def test_access_to_one_module_is_not_access_to_another(self, env):
        env.repo.grant_access(MOD, EMAIL, "equipo", by="t")
        assert env.repo.role_for(EMAIL, MOD_B) is None

    def test_inactive_module_grants_nothing(self, env):
        r = env.repo
        r.grant_access(INACTIVO, EMAIL, "equipo", by="t")
        assert r.role_for(EMAIL, INACTIVO) is None
        assert r.modules_for(EMAIL) == []

    # --- global admins ---
    def test_admin_opens_every_active_module(self, env):
        r = env.repo
        r.add_admin(EMAIL, by="t")
        assert r.is_admin(EMAIL) is True
        assert r.role_for(EMAIL, MOD) == AppRole.admin
        assert r.role_for(EMAIL, MOD_B) == AppRole.admin
        # >= : a real database may hold other (real) modules besides the test ones
        assert {MOD, MOD_B} <= {m.id for m in r.modules_for(EMAIL)}
        assert all(m.rol == AppRole.admin for m in r.modules_for(EMAIL))

    def test_admin_gets_nothing_in_an_inactive_module(self, env):
        env.repo.add_admin(EMAIL, by="t")
        assert env.repo.role_for(EMAIL, INACTIVO) is None
        assert INACTIVO not in {m.id for m in env.repo.modules_for(EMAIL)}

    def test_admin_role_wins_over_a_module_role(self, env):
        r = env.repo
        r.grant_access(MOD, EMAIL, "lector", by="t")
        r.add_admin(EMAIL, by="t")
        assert r.role_for(EMAIL, MOD) == AppRole.admin

    def test_remove_admin(self, env):
        r = env.repo
        r.add_admin(EMAIL, by="t")
        assert r.remove_admin(EMAIL) is True
        assert r.is_admin(EMAIL) is False
        assert r.remove_admin(EMAIL) is False

    def test_add_admin_twice_is_harmless(self, env):
        env.repo.add_admin(EMAIL, by="t")
        env.repo.add_admin(EMAIL, by="t")
        assert env.repo.list_all().administradores.count(EMAIL) == 1

    # --- validation ---
    def test_unknown_module_is_rejected(self, env):
        with pytest.raises(UnknownModuleError):
            env.repo.grant_access("no_existe", EMAIL, "lector", by="t")

    def test_invalid_role_is_rejected(self, env):
        with pytest.raises(InvalidRoleError):
            env.repo.grant_access(MOD, EMAIL, "admin", by="t")  # admin is global, not per module

    @pytest.mark.parametrize("malo", ["", "sin-arroba", "@ucn.cl", "dos palabras@ucn.cl"])
    def test_invalid_email_is_rejected(self, env, malo):
        with pytest.raises(InvalidEmailError):
            env.repo.add_admin(malo, by="t")
        with pytest.raises(InvalidEmailError):
            env.repo.grant_access(MOD, malo, "lector", by="t")

    # --- listing ---
    def test_list_all_and_filtered(self, env):
        r = env.repo
        r.add_admin("jefe@ucn.cl", by="t")
        r.grant_access(MOD, "a@ucn.cl", "lector", by="uno")
        r.grant_access(MOD_B, "b@ucn.cl", "equipo", by="dos")
        todo = r.list_all()
        assert "jefe@ucn.cl" in todo.administradores
        propios = [a for a in todo.accesos if a.modulo_id in (MOD, MOD_B)]  # a real DB has other rows
        assert {(a.modulo_id, a.email, a.rol) for a in propios} == {
            (MOD, "a@ucn.cl", "lector"),
            (MOD_B, "b@ucn.cl", "equipo"),
        }
        solo_a = r.list_all(MOD)
        assert [(a.modulo_id, a.email) for a in solo_a.accesos] == [(MOD, "a@ucn.cl")]
        assert [a.creado_por for a in solo_a.accesos] == ["uno"]
        with pytest.raises(UnknownModuleError):
            r.list_all("no_existe")

    # --- audit ---
    def test_record_text_view_persists_who_what_where(self, env):
        env.repo.record_text_view("Jefe@UCN.cl", MOD, "/x/comentarios", [3, 1, 2])
        filas = env.leer_auditoria()
        assert len(filas) == 1
        assert filas[0]["admin_email"] == "jefe@ucn.cl"
        assert filas[0]["modulo_id"] == MOD
        assert filas[0]["endpoint"] == "/x/comentarios"
        assert sorted(filas[0]["comentario_ids"]) == [1, 2, 3]

    def test_record_text_view_for_an_unknown_module_fails(self, env):
        with pytest.raises(AuditError):
            env.repo.record_text_view("jefe@ucn.cl", "no_existe", "/x", [1])
        assert env.leer_auditoria() == []
