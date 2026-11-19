"""Apply ``sql/core/NNN_*.sql`` to the localhost dev database.

* Only schemas ``neural_*`` may be touched; every file is statically checked
  before any statement runs (a simple guard, not a SQL parser).
* Applied files are recorded in ``neural_meta.schema_migraciones`` with their
  sha256. Re-running is a no-op; a file edited after being applied is refused.

Usage: ``python -m pipelines.migrate [--dir sql/core] [--dry-run]``
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ALLOWED_SCHEMAS = ("neural_meta", "neural_stg", "neural_core", "neural_mart", "neural_test")
SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "core"

_BOOTSTRAP = """
CREATE SCHEMA IF NOT EXISTS neural_meta;
CREATE TABLE IF NOT EXISTS neural_meta.schema_migraciones (
    nombre      text        PRIMARY KEY,
    sha256      text        NOT NULL,
    aplicado_en timestamptz NOT NULL DEFAULT now()
);
"""


class MigrationError(RuntimeError):
    """A migration was refused (guard violation or checksum drift)."""


# ---------------------------------------------------------------------------
# statement splitting and masking
# ---------------------------------------------------------------------------
def split_statements(text: str) -> List[str]:
    """Split on ``;`` outside strings/comments. Comments are removed from the output."""
    out, buf = [], []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "-" and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            buf.append(" ")
            continue
        if c == "'":
            j = i + 1
            while j < n:
                if text[j] == "'":
                    if text.startswith("''", j):
                        j += 2
                        continue
                    break
                j += 1
            buf.append(text[i : j + 1])
            i = j + 1
            continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


_STRING = re.compile(r"'(?:[^']|'')*'")
_NAME = r"([a-z_][a-z0-9_]*)(?:\.([a-z_][a-z0-9_]*))?"


def _check_target(schema: Optional[str], what: str, problems: List[str]) -> None:
    if schema is None:
        problems.append(f"{what} must be schema-qualified with one of {ALLOWED_SCHEMAS}")
    elif schema.lower() not in ALLOWED_SCHEMAS:
        problems.append(f"{what} targets schema '{schema}', outside {ALLOWED_SCHEMAS}")


def check_statement(stmt: str) -> List[str]:
    """Return the list of guard violations for one statement (empty = accepted)."""
    problems: List[str] = []
    for lit in _STRING.findall(stmt):
        inner = lit[1:-1]
        m = re.fullmatch(r"([a-z_][a-z0-9_]*)\.[a-z_][a-z0-9_]*", inner, flags=re.I)
        if m and m.group(1).lower() not in ALLOWED_SCHEMAS:
            problems.append(f"string literal references schema '{m.group(1)}'")
    masked = " ".join(_STRING.sub("''", stmt).split())
    if "$" in masked:
        return problems + ["dollar quoting / DO blocks are not supported"]
    if '"' in masked:
        return problems + ["quoted identifiers are not supported"]

    low = masked.lower()
    head = re.match(r"(create|alter|drop|insert|update|delete|comment|truncate)\b", low)
    if not head:
        return problems + [f"statement type not allowed: {low.split(' ')[0]!r}"]
    verb = head.group(1)

    if verb == "create":
        m = re.match(r"create (?:unique )?(?:or replace )?(?:materialized )?(schema|table|view|sequence|type|index)\b", low)
        if not m:
            return problems + ["only CREATE SCHEMA/TABLE/VIEW/SEQUENCE/TYPE/INDEX are allowed"]
        kind = m.group(1)
        if kind == "schema":
            t = re.match(rf"create schema (?:if not exists )?{_NAME}", low)
            if not t or t.group(2) is not None or t.group(1) not in ALLOWED_SCHEMAS:
                problems.append("CREATE SCHEMA outside the allowed neural_* list")
        elif kind == "index":
            t = re.search(rf"\bon (?:only )?{_NAME}", low)
            _check_target(t.group(1) if t and t.group(2) else None, "CREATE INDEX target", problems)
        else:
            t = re.match(rf"create (?:or replace )?(?:materialized )?{kind} (?:if not exists )?{_NAME}", low)
            _check_target(t.group(1) if t and t.group(2) else None, f"CREATE {kind.upper()}", problems)
    elif verb == "drop":
        t = re.match(rf"drop (schema|table|view|index) (?:if exists )?{_NAME}", low)
        if not t:
            problems.append("unsupported DROP")
        elif t.group(1) == "schema":
            if t.group(3) is not None or t.group(2) != "neural_test":
                problems.append("DROP SCHEMA is only allowed for neural_test")
        else:
            _check_target(t.group(2) if t.group(3) else None, "DROP target", problems)
    elif verb == "alter":
        t = re.match(rf"alter (?:table|view) (?:if exists )?(?:only )?{_NAME}", low)
        _check_target(t.group(1) if t and t.group(2) else None, "ALTER target", problems)
    elif verb == "comment":
        t = re.match(rf"comment on (schema|table|view|column) {_NAME}", low)
        if not t:
            problems.append("unsupported COMMENT")
        elif t.group(1) == "schema":
            if t.group(3) is not None or t.group(2) not in ALLOWED_SCHEMAS:
                problems.append("COMMENT ON SCHEMA outside the allowed list")
        else:
            _check_target(t.group(2) if t.group(3) else None, "COMMENT target", problems)
    # insert / update / delete / truncate targets are covered by the reference scan below.

    for m in re.finditer(rf"\b(from|join|references|into|update|truncate)\s+(?:only\s+)?(?:table\s+)?{_NAME}(\()?", low):
        kw, first, second, paren = m.group(1), m.group(2), m.group(3), m.group(4)
        prev = low[: m.start()].split()[-1:] or [""]
        if kw == "update" and prev[0] in ("on", "do", "for"):
            continue
        if kw in ("from", "join") and second is None and paren:
            continue  # set-returning function call such as generate_series(...)
        if first in ("cascade", "restrict"):
            continue
        _check_target(first if second else None, f"{kw.upper()} reference", problems)
    return problems


def validate_sql(text: str, filename: str) -> List[str]:
    """Check every statement; raise ``MigrationError`` naming the file on any violation."""
    statements = split_statements(text)
    errors = []
    for stmt in statements:
        for p in check_statement(stmt):
            errors.append(f"{p}: {' '.join(stmt.split())[:90]}")
    if errors:
        raise MigrationError(f"{filename} refused by the schema guard:\n  " + "\n  ".join(errors))
    return statements


# ---------------------------------------------------------------------------
# discovery, hashing, applying
# ---------------------------------------------------------------------------
_FILE = re.compile(r"^\d{3}_.+\.sql$")


def discover_migrations(directory: Path) -> List[Path]:
    return sorted(p for p in Path(directory).iterdir() if p.is_file() and _FILE.match(p.name))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def apply_migrations(conn, directory: Path = SQL_DIR) -> List[Tuple[str, str]]:
    """Apply pending files. Returns ``[(name, 'applied' | 'skipped')]``."""
    files = discover_migrations(directory)
    loaded = []
    for f in files:  # validate everything before touching the database
        text = f.read_text(encoding="utf-8")
        loaded.append((f.name, text, validate_sql(text, f.name)))
    boot = validate_sql(_BOOTSTRAP, "<bootstrap>")
    conn.autocommit = True  # so each conn.transaction() block is a real transaction

    with conn.transaction():
        with conn.cursor() as cur:
            for stmt in boot:
                cur.execute(stmt)

    results = []
    for name, text, statements in loaded:
        digest = sha256_text(text)
        with conn.cursor() as cur:
            cur.execute("SELECT sha256 FROM neural_meta.schema_migraciones WHERE nombre = %s", (name,))
            row = cur.fetchone()
        if row is not None:
            if row[0] != digest:
                raise MigrationError(
                    f"{name} was edited after being applied (recorded {row[0][:12]}, now {digest[:12]}); "
                    "add a new numbered migration instead"
                )
            results.append((name, "skipped"))
            continue
        with conn.transaction():
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
                cur.execute(
                    "INSERT INTO neural_meta.schema_migraciones (nombre, sha256) VALUES (%s, %s)",
                    (name, digest),
                )
        results.append((name, "applied"))
    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Apply DAI Neural SQL migrations to the dev database.")
    parser.add_argument("--dir", type=Path, default=SQL_DIR, help="migration directory (default: sql/core)")
    parser.add_argument("--dry-run", action="store_true", help="only run the schema guard; no connection")
    args = parser.parse_args(argv)

    try:
        if args.dry_run:
            for f in discover_migrations(args.dir):
                validate_sql(f.read_text(encoding="utf-8"), f.name)
                print(f"ok      {f.name}")
            return 0
        from .common.db import dev_connection

        with dev_connection() as conn:
            for name, status in apply_migrations(conn, args.dir):
                print(f"{status:8}{name}")
    except Exception as exc:  # report cleanly; never print secrets (none are in messages)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
