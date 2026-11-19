"""Environment-variable configuration. No secret has a default value."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str = field(repr=False)


_SUFFIXES = ("HOST", "PORT", "DB", "USER", "PASSWORD")


def load_db_config(prefix: str, env: Optional[Mapping[str, str]] = None) -> DbConfig:
    """Read ``<prefix>_HOST/PORT/DB/USER/PASSWORD`` (prefix ``DEV`` or ``WH``)."""
    env = os.environ if env is None else env
    names = {s: f"{prefix}_{s}" for s in _SUFFIXES}
    missing = [n for n in names.values() if not (env.get(n) or "").strip()]
    if missing:
        raise ConfigError("Missing required environment variables: " + ", ".join(missing))
    try:
        port = int(env[names["PORT"]])
    except ValueError as exc:
        raise ConfigError(f"{names['PORT']} must be an integer") from exc
    return DbConfig(
        host=env[names["HOST"]].strip(),
        port=port,
        dbname=env[names["DB"]].strip(),
        user=env[names["USER"]].strip(),
        password=env[names["PASSWORD"]],
    )


def hmac_secret(env: Optional[Mapping[str, str]] = None) -> str:
    """Return the pseudonymization secret from ``DAI_NEURAL_HMAC_KEY``."""
    env = os.environ if env is None else env
    value = env.get("DAI_NEURAL_HMAC_KEY") or ""
    if not value.strip():
        raise ConfigError("Missing required environment variable: DAI_NEURAL_HMAC_KEY")
    return value
