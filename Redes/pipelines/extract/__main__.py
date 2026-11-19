"""CLI: ``python -m pipelines.extract [--only fuente,...] [--force | --force-todo] [--registrar-huella]``."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import sources as S
from .runner import run


def registrar_huella() -> int:
    from ..common import huella
    from ..common.config import hmac_secret
    from ..common.db import dev_connection

    with dev_connection() as dev:
        estado = huella.registrar(dev, hmac_secret())
    print({"registrada": "huella registrada", "coincide": "huella ya existente: coincide",
           "no_coincide": "huella ya existente: NO coincide"}[estado])
    return 1 if estado == "no_coincide" else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract the Warehouse views into neural_stg (pseudonymized).")
    parser.add_argument("--only", help="comma-separated sources; valid: " + ", ".join(S.all_fuentes()))
    parser.add_argument("--force", action="store_true", help="reload even if the Warehouse load is already loaded")
    parser.add_argument("--force-todo", action="store_true",
                        help="reload everything and adopt the current HMAC key as the reference (replaces the stored fingerprint)")
    parser.add_argument("--registrar-huella", action="store_true",
                        help="only register the current HMAC key fingerprint if none is stored, then exit")
    args = parser.parse_args(argv)
    if args.registrar_huella:
        try:
            return registrar_huella()
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    only = [s.strip() for s in args.only.split(",") if s.strip()] if args.only else None
    try:
        results = run(only=only, force=args.force, force_todo=args.force_todo)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1 if any(r.status == "error" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
