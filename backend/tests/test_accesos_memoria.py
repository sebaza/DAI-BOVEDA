"""The in-memory fake honours the same contract as the PostgreSQL adapter."""
from __future__ import annotations

import pytest

from app.services.accesos import InMemoryAccessRepository
from contrato_accesos import ContratoAccesos, Entorno


class TestMemoria(ContratoAccesos):
    @pytest.fixture()
    def entorno(self) -> Entorno:
        repo = InMemoryAccessRepository()
        return Entorno(
            repo=repo,
            crear_modulo=lambda id, nombre, activo=True: repo.add_module(id, nombre, activo=activo),
            leer_auditoria=lambda: list(repo.vistas),
        )
