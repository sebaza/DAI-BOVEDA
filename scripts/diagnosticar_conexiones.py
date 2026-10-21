"""Check the database URLs the backend reads from backend/.env, without printing secrets.

For each URL it shows the user, the password length, whether the password has characters
that break a URL unless escaped, and whether a connection succeeds.

    backend\\.venv\\Scripts\\python.exe -I scripts\\diagnosticar_conexiones.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import get_settings  # noqa: E402

CARACTERES_RAROS = set("@:/#%?&$ \"'")


def revisar(nombre: str, url: str) -> bool:
    if not url:
        print(f"{nombre:<10} sin configurar")
        return False
    try:
        u = make_url(url)
    except Exception as exc:  # noqa: BLE001
        print(f"{nombre:<10} URL inválida ({type(exc).__name__})")
        return False
    clave = u.password or ""
    raros = bool(CARACTERES_RAROS & set(clave))
    try:
        engine = create_engine(u, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        estado = "CONECTA"
    except Exception as exc:  # noqa: BLE001
        mensaje = str(getattr(exc, "orig", exc)).splitlines()[0][:120]
        estado = f"FALLA: {mensaje}"
    print(f"{nombre:<10} usuario={u.username} | largo clave={len(clave)} | caracteres raros={raros} | {estado}")
    return estado == "CONECTA"


def main() -> int:
    s = get_settings()
    ok = [
        revisar("app", s.percepcion_database_url),
        revisar("proceso", getattr(s, "percepcion_proceso_database_url", "") or ""),
        revisar("boveda", s.boveda_database_url),
    ]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
