"""Rebuild ``neural_mart`` from ``neural_core``: every mart table is truncated and refilled in ONE transaction,
so a failure leaves the previous marts untouched. Output is counts and timings only.

The schema names are parameters so the integration test can run the same code against ``neural_test``.
"""
from __future__ import annotations

import sys
import time
from typing import Callable, Dict, Optional

from ..migrate import ALLOWED_SCHEMAS
from . import sql as S
from .rules import regular_ordinal


class MartError(RuntimeError):
    pass


def build(
    conn,
    core_schema: str = "neural_core",
    mart_schema: str = "neural_mart",
    meta_schema: str = "neural_meta",
    out: Callable[[str], None] = print,
) -> Dict[str, int]:
    for schema in (core_schema, mart_schema, meta_schema):
        if schema not in ALLOWED_SCHEMAS:
            raise MartError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    schemas = {"core": core_schema, "mart": mart_schema, "meta": meta_schema}
    counts: Dict[str, int] = {}
    t_all = time.monotonic()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(S.render(S.LATEST_PERIODO, schemas))
            latest = cur.fetchone()[0]
            if latest is None:
                raise MartError("no regular period in evento_estado: build neural_core first")
            params = {"latest": latest, "latest_ord": regular_ordinal(latest)}
            out(f"periodo maximo (regular): {latest}")
            cur.execute("SET LOCAL work_mem = '256MB'")   # the malla join sorts millions of rows
            tables = ", ".join(f"{mart_schema}.{t}" for t in S.MART_TABLES)
            cur.execute(f"TRUNCATE {tables}")
            for table, sql in S.BUILD_ORDER:
                t0 = time.monotonic()
                cur.execute(S.render(sql, schemas), params)
                cur.execute(f"SELECT count(*) FROM {mart_schema}.{table}")
                counts[table] = cur.fetchone()[0]
                cur.execute(
                    f"INSERT INTO {mart_schema}.mart_construccion (mart, filas, periodo_maximo) "
                    f"VALUES (%s, %s, %s) ON CONFLICT (mart) DO UPDATE SET filas = EXCLUDED.filas, "
                    f"construido_en = now(), periodo_maximo = EXCLUDED.periodo_maximo",
                    (table, counts[table], latest),
                )
                out(f"{table:22}{counts[table]:>12,} filas  {time.monotonic() - t0:6.1f} s")
                sys.stdout.flush()
    out(f"total: {time.monotonic() - t_all:.1f} s (una transaccion)")
    return counts


def censoring_report(conn, mart_schema: str = "neural_mart") -> Dict[str, str]:
    """Counts of censored rows (no person-level data)."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FILTER (WHERE censurado_d), count(*) FROM {mart_schema}.cohorte_resultado")
        a, b = cur.fetchone()
    return {"cohorte_resultado": f"{a} de {b}"}
