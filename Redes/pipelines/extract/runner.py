"""Extraction runner: stream a Warehouse view, pseudonymize, COPY into ``neural_stg``.

The Warehouse is only read (``warehouse_connection`` forces a read-only session, SELECT only).
Each run is recorded in ``neural_meta.carga_extraccion``. Output is counts only: never rows or keys.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from ..common import huella
from ..common.config import hmac_secret
from ..normalize.cargas import pick_vigente
from . import sources as S

ITERSIZE = 20_000
EXTRACT_TIMEOUT_MS = 900_000  # per statement (each FETCH of one batch is a statement)
SCHEMA_STG = "neural_stg"


@dataclass
class SourceResult:
    fuente: str
    status: str                # loaded | skipped | verified | error
    filas_origen: Optional[int] = None
    filas_insertadas: Optional[int] = None
    filas_omitidas: int = 0
    seconds: float = 0.0
    timestamp_carga_wh: Optional[int] = None
    carga_id: Optional[int] = None
    detail: str = ""


# ---- Warehouse metadata -----------------------------------------------------------------------
def warehouse_timestamp(wh_conn, source: S.Source) -> Optional[int]:
    """The Warehouse load timestamp of the current view content (epoch ms), or None if not tracked."""
    kind = source.ts.kind
    if kind == "none":
        return None
    with wh_conn.cursor() as cur:
        if kind == "cargas":
            cur.execute(f"SELECT timestamp_carga, vigente FROM {source.ts.table}")
            cargas = [{"timestamp_carga": r[0], "vigente": r[1]} for r in cur.fetchall()]
            return int(pick_vigente(cargas)["timestamp_carga"])
        cur.execute(f"SELECT max(timestamp_carga) FROM {source.ts.table}")
        value = cur.fetchone()[0]
    return None if value is None else int(value)


def count_view(wh_conn, view: str) -> int:
    with wh_conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {view}")
        return int(cur.fetchone()[0])


def count_source(wh_conn, source: S.Source) -> int:
    """Rows the source SELECT returns (the view count unless the source aggregates)."""
    if source.sql is None:
        return count_view(wh_conn, source.view)
    with wh_conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM ({source.sql}) AS t")
        return int(cur.fetchone()[0])


# ---- dev metadata -----------------------------------------------------------------------------
def find_ok_run(dev, fuente: str, ts: Optional[int], filas_origen: int) -> Optional[int]:
    """carga_id of an 'ok' run for the same Warehouse load.

    With a timestamp: same (fuente, timestamp). Without one (views that do not track loads) the
    row count is the only available proxy for "unchanged".
    """
    with dev.cursor() as cur:
        if ts is not None:
            cur.execute(
                "SELECT carga_id FROM neural_meta.carga_extraccion "
                "WHERE fuente = %s AND timestamp_carga_wh = %s AND estado = 'ok'", (fuente, ts))
        else:
            cur.execute(
                "SELECT carga_id FROM neural_meta.carga_extraccion "
                "WHERE fuente = %s AND timestamp_carga_wh IS NULL AND estado = 'ok' AND filas_origen = %s "
                "ORDER BY carga_id DESC LIMIT 1", (fuente, filas_origen))
        row = cur.fetchone()
    return None if row is None else int(row[0])


def _open_run(dev, fuente: str, ts: Optional[int], filas_origen: int, sha: str, reuse: Optional[int]) -> int:
    with dev.cursor() as cur:
        if reuse is not None:  # forced reload keeps the same provenance row (and its audit results)
            cur.execute(
                "UPDATE neural_meta.carga_extraccion SET estado = 'en_curso', filas_origen = %s, "
                "filas_insertadas = NULL, sql_sha256 = %s, iniciado_en = now(), terminado_en = NULL "
                "WHERE carga_id = %s", (filas_origen, sha, reuse))
            carga_id = reuse
        else:
            cur.execute(
                "INSERT INTO neural_meta.carga_extraccion (fuente, timestamp_carga_wh, filas_origen, sql_sha256) "
                "VALUES (%s, %s, %s, %s) RETURNING carga_id", (fuente, ts, filas_origen, sha))
            carga_id = int(cur.fetchone()[0])
    dev.commit()
    return carga_id


def _close_run(dev, carga_id: int, estado: str, inserted: Optional[int]) -> None:
    with dev.cursor() as cur:
        cur.execute(
            "UPDATE neural_meta.carga_extraccion SET estado = %s, filas_insertadas = %s, terminado_en = now() "
            "WHERE carga_id = %s", (estado, inserted, carga_id))
    dev.commit()


# ---- streaming load ---------------------------------------------------------------------------
def stream_rows(wh_conn, sql: str, name: str) -> Iterable[tuple]:
    with wh_conn.cursor(name=name) as cur:
        cur.itersize = ITERSIZE
        cur.execute(sql)
        for row in cur:
            yield row


def load_source(wh_conn, dev, source: S.Source, carga_id: int, secret: str) -> "tuple[int, int]":
    """Truncate the stg table and COPY the pseudonymized rows. Returns (inserted, skipped)."""
    transform = S.RowTransformer(source, secret)
    cols = ", ".join(("carga_id",) + source.stg_columns)
    table = f"{SCHEMA_STG}.{source.stg_table}"
    inserted = 0
    with dev.cursor() as cur:
        cur.execute(f"TRUNCATE {table} RESTART IDENTITY")
        with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as copy:
            for raw in stream_rows(wh_conn, source.select_sql, f"ext_{source.fuente}"[:60]):
                row = transform(raw)
                if row is None:
                    continue
                copy.write_row((carga_id,) + row)
                inserted += 1
    return inserted, transform.skipped


def extract_source(wh_conn, dev, source: S.Source, secret: str, force: bool) -> SourceResult:
    t0 = time.perf_counter()
    S.assert_safe_columns(source)
    ts = warehouse_timestamp(wh_conn, source)
    origin = count_source(wh_conn, source)
    existing = find_ok_run(dev, source.fuente, ts, origin)
    if S.should_skip(existing is not None, force):
        return SourceResult(source.fuente, "skipped", origin, None, 0, time.perf_counter() - t0, ts, existing,
                            "already loaded for this Warehouse load")
    carga_id = _open_run(dev, source.fuente, ts, origin, source.sql_sha256, existing)
    try:
        inserted, skipped = load_source(wh_conn, dev, source, carga_id, secret)
        dev.commit()
    except Exception:
        dev.rollback()
        wh_conn.rollback()
        _close_run(dev, carga_id, "error", None)
        raise
    wh_conn.rollback()  # end the read-only transaction opened for the named cursor
    _close_run(dev, carga_id, "ok", inserted)
    detail = "" if inserted + skipped == origin else f"origin {origin} != inserted {inserted} + skipped {skipped}"
    return SourceResult(source.fuente, "loaded", origin, inserted, skipped, time.perf_counter() - t0, ts,
                        carga_id, detail)


def _norm_tipo(values) -> tuple:
    """Compare names ignoring cosmetic trailing commas/spaces."""
    return tuple(None if v is None else v.strip().rstrip(",").strip() for v in values)


def verify_tipo_admision(wh_conn, dev, force: bool) -> SourceResult:
    """The dictionary is seeded; check it equals the Warehouse view instead of copying it."""
    t0 = time.perf_counter()
    with wh_conn.cursor() as cur:
        cur.execute(S.TIPO_ADMISION_SQL)
        wh_all = cur.fetchall()
    wh_conn.rollback()
    with dev.cursor() as cur:
        cur.execute("SELECT cod_admision, admision, tipo_qualitas, tipo_cna FROM neural_meta.dic_tipo_admision")
        dev_rows = {r[0]: _norm_tipo(r[1:]) for r in cur.fetchall()}
    null_code = sum(1 for r in wh_all if r[0] is None)  # a Warehouse row without code cannot be keyed
    wh_rows = {r[0]: _norm_tipo(r[1:]) for r in wh_all if r[0] is not None}
    same = sum(1 for k, v in wh_rows.items() if dev_rows.get(k) == v)
    only_wh, only_dev = set(wh_rows) - set(dev_rows), set(dev_rows) - set(wh_rows)
    ok = same == len(wh_rows) and not only_wh and not only_dev
    sha = hashlib.sha256(S.TIPO_ADMISION_SQL.encode()).hexdigest()
    previous = find_ok_run(dev, S.TIPO_ADMISION_FUENTE, None, len(wh_all))   # one provenance row, refreshed
    carga_id = _open_run(dev, S.TIPO_ADMISION_FUENTE, None, len(wh_all), sha, previous)
    _close_run(dev, carga_id, "ok" if ok else "error", same)
    detail = (f"dictionary equals the Warehouse view (ignoring trailing punctuation in names; "
              f"{null_code} Warehouse row(s) without code)") if ok else (
        f"{len(wh_rows) - same} differing/missing codes; only_wh={len(only_wh)} only_dev={len(only_dev)}")
    return SourceResult(S.TIPO_ADMISION_FUENTE, "verified" if ok else "error", len(wh_all), same, 0,
                        time.perf_counter() - t0, None, carga_id, detail)


def run(only: Optional[List[str]] = None, force: bool = False, secret: Optional[str] = None, force_todo: bool = False,
        wh_factory: Optional[Callable] = None, dev_factory: Optional[Callable] = None,
        out: Callable[[str], None] = print) -> List[SourceResult]:
    from ..common.db import dev_connection, warehouse_connection

    secret = secret or hmac_secret()
    wh_factory = wh_factory or (lambda: warehouse_connection(statement_timeout_ms=EXTRACT_TIMEOUT_MS))
    dev_factory = dev_factory or dev_connection
    known = S.all_fuentes()
    wanted = list(known) if not only else only
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise ValueError(f"unknown source(s): {unknown}; valid: {list(known)}")

    results: List[SourceResult] = []
    with dev_factory() as dev:
        if force_todo:  # full reload: the current key becomes the reference
            huella.reemplazar(dev, secret)
            force = True
        else:  # abort before touching anything when the key is not the one used for the existing loads
            huella.verificar_o_registrar(dev, secret)
        for fuente in wanted:
            with wh_factory() as wh:  # fresh read-only session per source
                try:
                    if fuente == S.TIPO_ADMISION_FUENTE:
                        res = verify_tipo_admision(wh, dev, force)
                    else:
                        res = extract_source(wh, dev, S.by_name(fuente), secret, force)
                except Exception as exc:
                    res = SourceResult(fuente, "error", detail=f"{type(exc).__name__}: {str(exc)[:200]}")
            results.append(res)
            out(format_result(res))
    return results


def format_result(r: SourceResult) -> str:
    return (f"{r.fuente:32} {r.status:9} origen={r.filas_origen} insertadas={r.filas_insertadas} "
            f"omitidas={r.filas_omitidas} ts={r.timestamp_carga_wh} carga={r.carga_id} "
            f"{r.seconds:7.1f}s {r.detail}")
