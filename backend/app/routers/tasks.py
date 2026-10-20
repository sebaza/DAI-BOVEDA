"""Trigger routes for scheduled work (no user session).

Protected by a shared token in the ``X-Tasks-Token`` header (TASKS_TRIGGER_TOKEN). With
no token configured the routes are disabled (403): fail closed.

The router is mounted twice in ``app.main``: under ``/tasks`` (canonical) and under
``/ai-tasks`` (the prefix the Torre used, kept so a worker that still has the old path
only needs to change the host).
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import get_settings
from app.services.percepcion import resumen_llm

router = APIRouter(tags=["tasks"])


def _require_tasks_token(x_tasks_token: str | None) -> None:
    """Validate X-Tasks-Token against TASKS_TRIGGER_TOKEN."""
    expected = (getattr(get_settings(), "tasks_trigger_token", "") or "").strip()
    if not expected:
        raise HTTPException(403, "Trigger deshabilitado: configura TASKS_TRIGGER_TOKEN.")
    # Constant-time comparison (no timing side channel to recover the token).
    if not hmac.compare_digest((x_tasks_token or "").strip(), expected):
        raise HTTPException(403, "Token inválido.")


@router.post("/run/percepcion-resumen")
def run_percepcion_resumen(
    semanas: int = Query(1, ge=1, le=12),
    forzar: bool = Query(False),
    x_tasks_token: str | None = Header(default=None, alias="X-Tasks-Token"),
):
    """Generate the WEEKLY Percepcion summary. Fired AFTER an ingestion.

    The last cell of the worker's ``migraciones/correr_migracion.py`` calls it, which is
    where the flow "ingest locally -> upload -> rebuild facts" ends. So the summary is
    computed exactly when there is new data, without a scheduler.

    NOT COST-IDEMPOTENT, BUT ALMOST: the service compares the sha256 fingerprint of the
    week's inputs against the stored one and only calls the model when they changed.
    Firing it twice in a row with no ingestion in between costs nothing (the response
    says ``generados: 0`` and ``costo_usd_total: 0``).

    ``semanas`` regenerates backwards from the last week with data. ``forzar`` ignores
    the fingerprint and pays again: for when the prompt changed, not for normal use.
    """
    _require_tasks_token(x_tasks_token)
    try:
        return resumen_llm.generar_tras_ingesta(semanas=semanas, forzar=forzar)
    except Exception as exc:  # never 5xx: the runner must not blow up because of this
        return {"status": "error", "fuente": "percepcion-resumen", "reason": str(exc)[:300]}
