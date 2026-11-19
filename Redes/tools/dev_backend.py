"""Dev launcher: start the Bóveda backend with the DAI Neural env resolved at runtime.

No secret is written anywhere; values are resolved in memory and passed to uvicorn:
  - backend/.env is loaded (BOVEDA_DATABASE_URL, session secrets, ...).
  - NEURAL_DATABASE_URL: taken from the environment/.env if present; otherwise derived from
    BOVEDA_DATABASE_URL, only when that URL points at localhost (same dev database), adding
    search_path=neural_mart,neural_core,neural_meta. The Neural engine is read-only anyway.
The Bóveda serves aggregates only, so the pseudonymization key is never loaded here.

Usage (from the repo root): backend/.venv/Scripts/python.exe Redes/tools/dev_backend.py [--port 8012]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
SEARCH_PATH = "neural_mart,neural_core,neural_meta"


def derive_neural_url(boveda_url: str) -> str | None:
    """Neural URL from the Bóveda URL when it targets localhost; None otherwise."""
    if not boveda_url:
        return None
    parts = urlsplit(boveda_url)
    if parts.hostname not in ("localhost", "127.0.0.1", "::1"):
        return None
    base = boveda_url.split("?", 1)[0]
    return f"{base}?options={quote('-c search_path=' + SEARCH_PATH)}"


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
    if not os.environ.get("NEURAL_DATABASE_URL"):
        url = derive_neural_url(os.environ.get("BOVEDA_DATABASE_URL", "").strip())
        if url:
            os.environ["NEURAL_DATABASE_URL"] = url
        else:
            print("NEURAL_DATABASE_URL not set and not derivable; /neural/* will answer 503.", file=sys.stderr)

    port = "8012"
    if "--port" in sys.argv:
        port = sys.argv[sys.argv.index("--port") + 1]
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=int(port), app_dir=str(BACKEND))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
