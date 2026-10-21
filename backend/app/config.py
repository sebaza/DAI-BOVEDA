"""Settings for Boveda DAI.

Mirrors the layout of the Torre's ``app.config`` so the Percepcion module (copied as is)
keeps working: ``BASE_DIR``, ``get_settings()`` and the ``percepcion_*`` knobs keep
their names. Everything is read from the environment (``backend/.env`` in local dev).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# backend/  (config.py -> app -> backend)
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# Default session secret (dev only). Booting outside APP_ENV=dev with it (or empty) is
# refused by get_settings(): sessions would be signed with a public key.
_DEV_SESSION_SECRET_DEFAULT = "boveda-dai-dev-session-secret"


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", ""}


class Settings:
    """Read once per process (see ``get_settings``). Values are read in ``__init__`` so a
    fresh instance always reflects the current environment (useful for tests)."""

    def __init__(self) -> None:
        # --- App / sessions ---
        self.app_name: str = os.getenv("APP_NAME", "Boveda DAI")
        # Unset/blank APP_ENV is production: a deploy that forgets it must not enable dev-login.
        self.app_env: str = os.getenv("APP_ENV", "").strip() or "production"
        self.app_session_secret: str = os.getenv("APP_SESSION_SECRET", _DEV_SESSION_SECRET_DEFAULT)
        self.app_session_ttl_seconds: int = int(os.getenv("APP_SESSION_TTL_SECONDS", "28800"))
        self.cors_origins: list[str] = [
            origin.strip()
            for origin in os.getenv(
                "BACKEND_CORS_ORIGINS",
                "http://localhost:3001,http://127.0.0.1:3001,http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if origin.strip()
        ]

        # --- Google sign-in (Identity Services ID token, verified server side) ---
        self.google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
        self.google_oauth_enabled: bool = os.getenv("GOOGLE_OAUTH_ENABLED", "1") == "1"

        # --- Access control: lists in PostgreSQL, fail closed ---
        # SQLAlchemy URL of the database holding the `boveda` schema (per-module access
        # lists, global admins, text-view audit; see backend/sql/). The former env
        # allowlists (BOVEDA_ALLOWED_EMAILS / BOVEDA_TEAM_EMAILS) no longer exist.
        # Empty => nobody gets in (and get_settings() refuses to boot outside dev).
        self.boveda_database_url: str = os.getenv("BOVEDA_DATABASE_URL", "").strip()
        self.dev_default_user_email: str = os.getenv("DEV_DEFAULT_USER_EMAIL", "dev@boveda.local")
        self.dev_default_user_name: str = os.getenv("DEV_DEFAULT_USER_NAME", "Equipo DAI (dev)")

        # --- Scheduled tasks ---
        self.tasks_trigger_token: str = os.getenv("TASKS_TRIGGER_TOKEN", "")

        # --- Databases ---
        # Operational URL is only the FALLBACK of the percepcion engine (see
        # services/percepcion/db.py). Local default: a SQLite file under backend/.
        self.operational_database_url: str = os.getenv(
            "OPERATIONAL_DATABASE_URL", f"sqlite:///{(BASE_DIR / 'percepcion.db').as_posix()}"
        )
        # Mirror tables written by the external worker (repo Sentiment_Analisys_University).
        self.percepcion_database_url: str = os.getenv("PERCEPCION_DATABASE_URL", "")
        # Optional second connection with a DB role that CAN read raw comment text/captions
        # (boveda_proceso). Only the admin Curacion endpoints and the weekly-summary caption
        # read use it. Empty => falls back to PERCEPCION_DATABASE_URL (single-credential setup).
        self.percepcion_proceso_database_url: str = os.getenv("PERCEPCION_PROCESO_DATABASE_URL", "").strip()

        # --- Percepcion knobs (see the Torre docs / services/percepcion/*) ---
        # Model of the weekly LLM summary. Empty => resumen_llm.MODELO_ANTHROPIC.
        self.percepcion_resumen_modelo: str = os.getenv("PERCEPCION_RESUMEN_MODELO", "")
        # Alert detection unit, in weeks (default 2 = fortnight). See repository.UNIDAD_DETECCION_SEMANAS.
        self.percepcion_unidad_deteccion_semanas: int = max(
            1, int(os.getenv("PERCEPCION_UNIDAD_DETECCION_SEMANAS", "2") or 2)
        )
        # Fraction of topic weight kept by the credit of a positive whose topic is not
        # attributable to the institution. See ponderacion.CREDITO_NO_ATRIBUIBLE.
        self.percepcion_credito_no_atribuible: float = min(
            1.0, max(0.0, float(os.getenv("PERCEPCION_CREDITO_NO_ATRIBUIBLE", "0.5") or 0.5))
        )
        # A NEUTRAL comment on a student-federation account counts as adverse.
        # See postura.NEU_FEDERACION_ES_ADVERSO.
        self.percepcion_neu_federacion_adverso: bool = _env_flag("PERCEPCION_NEU_FEDERACION_ADVERSO", "1")

        # --- LLM providers ---
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-5.4-mini")
        # Optional JSON overriding/extending the price table (USD per million tokens).
        self.llm_precios_json: str = os.getenv("LLM_PRECIOS_JSON", "")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Fail closed: outside dev, refuse to boot with the default (or empty) session secret.
    if (settings.app_env or "").strip().lower() != "dev":
        secret = (settings.app_session_secret or "").strip()
        if not secret or secret == _DEV_SESSION_SECRET_DEFAULT:
            raise RuntimeError(
                "APP_SESSION_SECRET is not configured (or uses the dev default) with "
                "APP_ENV != 'dev'. Set a strong secret before starting outside development."
            )
        # Fail closed: without the access database nobody could be authorised.
        if not (settings.boveda_database_url or "").strip():
            raise RuntimeError(
                "BOVEDA_DATABASE_URL is not configured with APP_ENV != 'dev'. Set the "
                "SQLAlchemy URL of the database that holds the `boveda` schema "
                "(see backend/sql/) before starting outside development."
            )
    return settings
