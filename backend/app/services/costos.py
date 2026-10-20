"""Minimal LLM cost helpers for the weekly Percepcion summary.

The Torre keeps a full costs service (GCP billing export + an ``llm_usage`` table in its
operational database). Boveda has neither, so this module keeps only what
``services/percepcion/resumen_llm.py`` and its tests need:

* ``PRECIOS_LLM_DEFAULT`` / ``precios_para_modelo`` / ``costo_estimado_usd``: identical
  price table and cost formula (USD per million tokens, list prices; ESTIMATES).
* ``registrar_uso_llm``: STUB. It only logs the call (model, feature, tokens, estimated
  cost) and never raises. There is no ``llm_usage`` table here; the cost of each weekly
  summary is still stored on the ``percepcion_resumen_semanal`` row by ``resumen_llm``.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger("boveda.costos")

# Prices per MILLION tokens (USD). Estimates to size relative spend, not an invoice.
# Extend/override with LLM_PRECIOS_JSON.
PRECIOS_LLM_DEFAULT: dict[str, dict[str, float]] = {
    "claude-opus-4-8": {"input_usd_por_millon": 5.0, "output_usd_por_millon": 25.0},
    # Still a valid value of PERCEPCION_RESUMEN_MODELO (the weekly summary can move
    # model by env var without touching code).
    "claude-opus-5": {"input_usd_por_millon": 5.0, "output_usd_por_millon": 25.0},
    # List price (a promotional price existed until 2026-08-31 and is deliberately NOT used).
    "claude-sonnet-5": {"input_usd_por_millon": 3.0, "output_usd_por_millon": 15.0},
    # REAL default of the weekly summary (resumen_llm.MODELO_ANTHROPIC).
    "claude-haiku-4-5": {"input_usd_por_millon": 1.0, "output_usd_por_millon": 5.0},
    # Legacy OpenAI models, kept so old rows can still be costed.
    "gpt-5.4-mini": {"input_usd_por_millon": 0.75, "output_usd_por_millon": 4.5},
    "gpt-5-mini": {"input_usd_por_millon": 0.25, "output_usd_por_millon": 2.0},
    "default": {"input_usd_por_millon": 5.0, "output_usd_por_millon": 25.0},
}

# Prompt-cache multipliers over the INPUT price (Anthropic): reads ~0.1x, writes ~1.25x (5 min TTL).
FACTOR_CACHE_LECTURA = 0.1
FACTOR_CACHE_ESCRITURA = 1.25


def tabla_precios_llm() -> dict[str, dict[str, float]]:
    """Default prices plus overrides from LLM_PRECIOS_JSON (best effort)."""
    tabla = {k: dict(v) for k, v in PRECIOS_LLM_DEFAULT.items()}
    raw = getattr(get_settings(), "llm_precios_json", "") or ""
    if raw.strip():
        try:
            extra = json.loads(raw)
            if isinstance(extra, dict):
                for nombre, fila in extra.items():
                    if isinstance(fila, dict):
                        tabla[str(nombre)] = {str(k): float(v) for k, v in fila.items()}
        except Exception:
            pass  # a bad JSON in the env must never break cost tracking
    return tabla


def precios_para_modelo(modelo: str, precios: dict[str, dict[str, float]] | None = None) -> dict[str, float]:
    """Price row: exact match -> prefix match -> 'default'."""
    tabla = precios if precios is not None else tabla_precios_llm()
    clave = (modelo or "").strip()
    if clave in tabla:
        return tabla[clave]
    for nombre, fila in tabla.items():
        if nombre != "default" and clave.startswith(nombre):
            return fila
    return tabla.get("default", PRECIOS_LLM_DEFAULT["default"])


def costo_estimado_usd(
    modelo: str,
    input_tokens: int,
    output_tokens: int,
    precios: dict[str, dict[str, float]] | None = None,
    cache_lectura_tokens: int = 0,
    cache_escritura_tokens: int = 0,
) -> float:
    """USD cost of one call. ``input_tokens`` is the NON-cached remainder: the Messages
    API reports cache tokens in their own fields, so adding them here would count twice."""
    fila = precios_para_modelo(modelo, precios)
    entrada = float(fila.get("input_usd_por_millon", 0.0))
    salida = float(fila.get("output_usd_por_millon", 0.0))
    por_millon = lambda n: max(0, int(n)) / 1_000_000.0  # noqa: E731
    return (
        por_millon(input_tokens) * entrada
        + por_millon(cache_lectura_tokens) * entrada * FACTOR_CACHE_LECTURA
        + por_millon(cache_escritura_tokens) * entrada * FACTOR_CACHE_ESCRITURA
        + por_millon(output_tokens) * salida
    )


def _tokens(usage: Any, *claves: str) -> int:
    if not isinstance(usage, dict):
        return 0
    for clave in claves:
        valor = usage.get(clave)
        if valor is not None:
            try:
                return max(0, int(valor))
            except (TypeError, ValueError):
                continue
    return 0


def registrar_uso_llm(modelo: str, feature: str, usage: Any, session_factory: Any = None) -> bool:
    """STUB of the Torre's ``llm_usage`` tracker: logs the call and returns False
    ("not persisted"). Never raises, as the original contract requires."""
    try:
        entrada = _tokens(usage, "input_tokens", "prompt_tokens")
        salida = _tokens(usage, "output_tokens", "completion_tokens")
        costo = costo_estimado_usd(
            modelo or "",
            entrada,
            salida,
            cache_lectura_tokens=_tokens(usage, "cache_read_input_tokens"),
            cache_escritura_tokens=_tokens(usage, "cache_creation_input_tokens"),
        )
        logger.info(
            "LLM usage model=%s feature=%s input_tokens=%d output_tokens=%d est_cost_usd=%.6f",
            modelo, feature, entrada, salida, costo,
        )
    except Exception:  # noqa: BLE001
        pass
    return False
