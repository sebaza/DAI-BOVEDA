"""CLI: ``python -m pipelines.marts`` rebuilds neural_mart from neural_core (one transaction)."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .build import build, censoring_report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the neural_mart tables from neural_core.")
    parser.parse_args(argv)
    try:
        from ..common.db import dev_connection

        with dev_connection() as conn:
            build(conn)
            for name, value in censoring_report(conn).items():
                print(f"censuradas {name}: {value}")
    except Exception as exc:  # never print secrets: none are in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
