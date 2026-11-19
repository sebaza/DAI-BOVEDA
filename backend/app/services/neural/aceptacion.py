"""Confidentiality acceptance gate of DAI Neural.

The module no longer hides small groups: its protection is that each person declares, once per text version,
that they are a trusted person of the DAI and will use the data internally. The acceptance (who, when, which
version) lives in the access database (``boveda.aceptaciones_modulo``); the Neural connection is read only.

Server-enforced and fail closed: a route behind ``require_aceptacion`` answers 403 until the CURRENT version is
accepted, and 503 (never a grant) when the access store cannot answer.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException

from app.schemas import AuthUser
from app.services import accesos
from app.services.auth import require_module

MODULO = "neural"
VERSION = "2026-11-18"
TEXTO = (
    "Declaro que soy una persona de confianza de la Dirección de Análisis Institucional (DAI), que conozco la "
    "Ley 19.628 sobre protección de la vida privada y la Ley 21.719 sobre protección de datos personales, y que "
    "usaré esta información solo para fines internos de la UCN, sin difundirla ni intentar identificar a personas."
)

logger = logging.getLogger("boveda")

# One shared instance: FastAPI caches dependencies per callable, so the module check runs once per request.
exigir_modulo = require_module(MODULO)


def esta_aceptada(email: str) -> bool:
    """True only if ``email`` accepted the current version. Raises ``HTTPException(503)`` if the store fails."""
    try:
        return bool(accesos.get_repository().acepto(MODULO, email, VERSION))
    except Exception as exc:  # noqa: BLE001 - could not check: never grant
        logger.error("Neural: no se pudo consultar la aceptación (%s).", type(exc).__name__)
        raise HTTPException(503, "No se pudo verificar la aceptación de confidencialidad.") from exc


def registrar(email: str) -> None:
    """Record the acceptance of the current version. Raises ``HTTPException(503)`` if it cannot be written."""
    try:
        accesos.get_repository().registrar_aceptacion(MODULO, email, VERSION)
    except Exception as exc:  # noqa: BLE001 - not recorded: the caller must not report success
        logger.error("Neural: no se pudo registrar la aceptación (%s).", type(exc).__name__)
        raise HTTPException(503, "No se pudo registrar la aceptación de confidencialidad.") from exc


def require_aceptacion(user: AuthUser = Depends(exigir_modulo)) -> AuthUser:
    """Dependency of every Neural data route: module access first (401/403), then the current acceptance."""
    if not esta_aceptada(user.email):
        raise HTTPException(403, {"codigo": "aceptacion_requerida", "version": VERSION})
    return user
