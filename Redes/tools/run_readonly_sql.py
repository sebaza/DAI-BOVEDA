"""Run aggregate-only discovery SQL against the Warehouse in a READ-ONLY session.

Usage:
    WH_PASSWORD=... python run_readonly_sql.py <file.sql> [--only R01,R02] [--out results.txt]

Connection parameters come from environment variables (never from the repo):
    WH_HOST, WH_PORT (5432), WH_DB, WH_USER, WH_PASSWORD

Safety:
    - Session forced to default_transaction_read_only=on and a statement timeout.
    - Each block must start with SELECT or WITH; anything else is refused.
    - Blocks are delimited by header lines of the form "-- Rxx | description".
    - Queries are expected to return aggregates only (no RUT, names or individual grades).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import psycopg

HEADER = re.compile(r"^--\s*(R\d+[A-Za-z]?)\s*\|\s*(.*)$")
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|truncate|drop|alter|create|grant|revoke|copy|merge|call|do|vacuum)\b",
    re.IGNORECASE,
)
MAX_ROWS = 300


def parse_blocks(text: str) -> list[tuple[str, str, str]]:
    blocks: list[tuple[str, str, str]] = []
    current: list[str] = []
    qid = desc = None
    for line in text.splitlines():
        m = HEADER.match(line)
        if m:
            if qid:
                blocks.append((qid, desc, "\n".join(current)))
            qid, desc, current = m.group(1), m.group(2), []
        elif qid:
            current.append(line)
    if qid:
        blocks.append((qid, desc, "\n".join(current)))
    return blocks


def strip_comments(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--")).strip().rstrip(";").strip()


def check_safe(sql: str) -> None:
    head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    if head not in ("SELECT", "WITH"):
        raise ValueError(f"refused: block must start with SELECT/WITH, got {head!r}")
    if ";" in sql:
        raise ValueError("refused: multiple statements in one block")
    if FORBIDDEN.search(sql):
        raise ValueError("refused: forbidden keyword in block")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sql_file")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--timeout-ms", type=int, default=300000)
    args = ap.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    with open(args.sql_file, encoding="utf-8") as fh:
        blocks = parse_blocks(fh.read())

    out = open(args.out, "a", encoding="utf-8") if args.out else sys.stdout
    conn = psycopg.connect(
        host=os.environ["WH_HOST"],
        port=int(os.environ.get("WH_PORT", "5432")),
        dbname=os.environ["WH_DB"],
        user=os.environ["WH_USER"],
        password=os.environ["WH_PASSWORD"],
        options=f"-c default_transaction_read_only=on -c statement_timeout={args.timeout_ms}",
        connect_timeout=15,
    )
    conn.autocommit = True
    try:
        for qid, desc, raw in blocks:
            if only and qid not in only:
                continue
            sql = strip_comments(raw)
            print(f"\n{qid} | {desc}", file=out)
            try:
                check_safe(sql)
                t0 = time.time()
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cols = [d.name for d in cur.description]
                    rows = cur.fetchmany(MAX_ROWS + 1)
                print("\t".join(cols), file=out)
                for r in rows[:MAX_ROWS]:
                    print("\t".join("[NULL]" if v is None else str(v) for v in r), file=out)
                if len(rows) > MAX_ROWS:
                    print(f"... truncated at {MAX_ROWS} rows", file=out)
                print(f"({time.time() - t0:.1f}s)", file=out)
            except Exception as exc:  # report and continue with the next block
                print(f"ERROR: {type(exc).__name__}: {exc}".splitlines()[0], file=out)
            out.flush()
    finally:
        conn.close()
        if out is not sys.stdout:
            out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
