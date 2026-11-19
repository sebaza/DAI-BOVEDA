"""Neural configuration, read from the environment at call time (never cached, never logged).

* ``NEURAL_DATABASE_URL``: SQLAlchemy URL (``postgresql+psycopg://...``) whose ``options`` set
  ``-c search_path=neural_mart,neural_core,neural_meta``. Unset => the module answers 503.
"""
from __future__ import annotations

import os


class NeuralNoConfigurado(RuntimeError):
    """A required setting is missing. The message never contains a setting value."""


def database_url() -> str:
    url = os.getenv("NEURAL_DATABASE_URL", "").strip()
    if not url:
        raise NeuralNoConfigurado("DAI Neural no está configurado en el servidor.")
    return url
