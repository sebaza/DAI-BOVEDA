"""In-memory implementation of the access port, for unit tests and the CLI tests.

Honours the same contract as the PostgreSQL adapter (``tests/contrato_accesos.py``).
It also exposes knobs a real database cannot offer on demand: ``fallar_auditoria`` to
simulate an audit that cannot be written, and ``vistas`` to inspect what was recorded.
"""
from __future__ import annotations

from typing import Sequence

from app.schemas import AppRole, ModuloAcceso
from app.services.accesos.puerto import (
    AccessEntry,
    AuditError,
    Listing,
    UnknownModuleError,
    normalize_email,
    validate_email,
    validate_role,
)


class InMemoryAccessRepository:
    def __init__(self) -> None:
        self._modulos: dict[str, tuple[str, bool]] = {}  # id -> (nombre, activo)
        self._admins: dict[str, str | None] = {}  # email -> creado_por
        self._accesos: dict[tuple[str, str], tuple[str, str | None]] = {}  # (modulo, email) -> (rol, por)
        self.vistas: list[dict] = []
        self.fallar_auditoria = False

    # --- test setup ---
    def add_module(self, module_id: str, nombre: str, *, activo: bool = True) -> None:
        self._modulos[module_id] = (nombre, activo)

    def set_module_active(self, module_id: str, activo: bool) -> None:
        nombre, _ = self._modulos[module_id]
        self._modulos[module_id] = (nombre, activo)

    def _activo(self, module_id: str) -> bool:
        return self._modulos.get(module_id, ("", False))[1]

    # --- AccessRepository ---
    def is_admin(self, email: str) -> bool:
        return normalize_email(email) in self._admins

    def role_for(self, email: str, module_id: str) -> AppRole | None:
        email = normalize_email(email)
        if not email or not self._activo(module_id):
            return None
        if email in self._admins:
            return AppRole.admin
        entrada = self._accesos.get((module_id, email))
        return AppRole(entrada[0]) if entrada else None

    def modules_for(self, email: str) -> list[ModuloAcceso]:
        email = normalize_email(email)
        if not email:
            return []
        es_admin = email in self._admins
        salida = []
        for module_id, (nombre, activo) in self._modulos.items():
            if not activo:
                continue
            if es_admin:
                salida.append(ModuloAcceso(id=module_id, nombre=nombre, rol=AppRole.admin))
            elif (module_id, email) in self._accesos:
                rol = AppRole(self._accesos[(module_id, email)][0])
                salida.append(ModuloAcceso(id=module_id, nombre=nombre, rol=rol))
        return sorted(salida, key=lambda m: m.nombre)

    def record_text_view(
        self, admin_email: str, module_id: str, endpoint: str, comment_ids: Sequence[int]
    ) -> None:
        if self.fallar_auditoria:
            raise AuditError("Simulación: no se pudo escribir la auditoría.")
        if module_id not in self._modulos:
            raise AuditError(f"Módulo desconocido: {module_id!r}.")
        self.vistas.append(
            {
                "admin_email": normalize_email(admin_email),
                "modulo_id": module_id,
                "endpoint": endpoint,
                "comentario_ids": [int(i) for i in comment_ids],
            }
        )

    # --- AccessManager ---
    def _exigir_modulo(self, module_id: str) -> None:
        if module_id not in self._modulos:
            raise UnknownModuleError(f"El módulo {module_id!r} no existe.")

    def add_admin(self, email: str, *, by: str | None = None) -> None:
        self._admins.setdefault(validate_email(email), by)

    def remove_admin(self, email: str) -> bool:
        return self._admins.pop(validate_email(email), "ausente") != "ausente"

    def grant_access(self, module_id: str, email: str, rol: str, *, by: str | None = None) -> None:
        email, rol = validate_email(email), validate_role(rol)
        self._exigir_modulo(module_id)
        anterior = self._accesos.get((module_id, email))
        self._accesos[(module_id, email)] = (rol, anterior[1] if anterior else by)

    def revoke_access(self, module_id: str, email: str) -> bool:
        email = validate_email(email)
        self._exigir_modulo(module_id)
        return self._accesos.pop((module_id, email), None) is not None

    def list_all(self, module_id: str | None = None) -> Listing:
        if module_id is not None:
            self._exigir_modulo(module_id)
        accesos = [
            AccessEntry(modulo_id=m, email=e, rol=rol, creado_por=por)
            for (m, e), (rol, por) in sorted(self._accesos.items())
            if module_id is None or m == module_id
        ]
        return Listing(administradores=sorted(self._admins), accesos=accesos)
