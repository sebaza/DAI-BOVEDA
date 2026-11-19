"""Build ``neural_mart.snapshot_t2`` (task T2, docs/09_benchmark_t2.md).

``python -m pipelines.snapshots.t2`` reads ``neural_core`` (localhost dev DB only), builds the point-in-time snapshot with
``features_t2.construir_snapshot_t2`` and replaces the table in ONE transaction. Output: counts only.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from typing import Callable, Dict, List, Optional

import pandas as pd

from ..migrate import ALLOWED_SCHEMAS
from . import features_t2 as F2
from .t1 import Q_EPISODIOS, Q_ESTADOS, Q_LATEST, Q_VIA, _copy, _read

Q_INTENTOS_T2 = """
SELECT intento_id, persona_key, episodio_id, periodo, codigo_asignatura, catalogo, nrc, oportunidad,
       es_intento_evaluado, nota_numerica, nota_es_heredada, resultado_tipo, aprobado_curricular, creditos,
       creditos_reconocidos
FROM {core}.intento_asignatura
"""
Q_MALLA = ("SELECT cod_programa, catalogo, codigo_asignatura, semestre, creditos, formacion, depto "
           "FROM {core}.asignatura_malla")
Q_PREREQ = "SELECT cod_programa, catalogo, codigo_requisito, codigo_asignatura FROM {core}.prerrequisito"
Q_DOCENTES = "SELECT periodo, nrc, docente_key FROM {core}.seccion_docente"
# P117-P127: static department of each course = the department code that the grade history reports most often for it (0 courses have two).
Q_DEPTOS = """
SELECT codigo_asignatura, cod_depto FROM (
    SELECT materia || '-' || curso AS codigo_asignatura, cod_depto,
           row_number() OVER (PARTITION BY materia || '-' || curso ORDER BY count(*) DESC, cod_depto) AS rn
    FROM {stg}.ban_historia_notas WHERE cod_depto IS NOT NULL GROUP BY 1, 2) x
WHERE rn = 1
"""

INT_COLS = ["n_notas_acum", "n_reprob_acum", "n_intentos_acum", "n_interrupcion", "sem_matriculados", "oportunidad",
            "n_prev_curso", "cohorte_anio"]
BOOL_COLS = ["aprobo_antes_curso", "con_postulacion", "en_malla", "malla_conocida", "info_prereq", "tiene_docente"]


def cargar(conn, schemas: Dict[str, str]):
    ep = _read(conn, Q_EPISODIOS, schemas)
    ep["id_nivel"] = pd.to_numeric(ep["id_nivel"]).astype("Int64")
    es = _read(conn, Q_ESTADOS, schemas)
    es["episodio_id"] = es["episodio_id"].astype("Int64")
    it = _read(conn, Q_INTENTOS_T2, schemas)
    for col in ("nota_numerica", "creditos", "creditos_reconocidos"):
        it[col] = pd.to_numeric(it[col]).astype("float64")
    it["episodio_id"] = it["episodio_id"].astype("Int64")
    via = _read(conn, Q_VIA, schemas)
    for col in ("puntaje_leng", "puntaje_mat", "puntaje_ciencias", "puntaje_historia", "puntaje_nem",
                "puntaje_ranking", "notas_em", "ponderado"):
        via[col] = pd.to_numeric(via[col]).astype("float64")
    malla = _read(conn, Q_MALLA, schemas)
    for col in ("semestre", "creditos"):
        malla[col] = pd.to_numeric(malla[col]).astype("float64")
    prereq = _read(conn, Q_PREREQ, schemas)
    doc = _read(conn, Q_DOCENTES, schemas)
    deptos = _read(conn, Q_DEPTOS, schemas)
    with conn.cursor() as cur:
        cur.execute(Q_LATEST.format(**schemas))
        latest = cur.fetchone()[0]
    if latest is None:
        raise RuntimeError("no regular period in evento_estado: build neural_core first")
    return ep, es, it, via, malla, prereq, doc, deptos, latest


def preparar_tabla(snap: pd.DataFrame) -> pd.DataFrame:
    s = snap.copy()
    for c in BOOL_COLS:
        s[c] = s[c].astype(object).where(s[c].notna(), None)
    for c in INT_COLS:
        s[c] = s[c].round().astype("Int64")
    s["y"] = s["y"].astype("int64")
    s["k"] = s["k"].astype("int64")
    s["episodio_id"] = s["episodio_id"].astype("int64")
    return s


def resumen_filas(snap: pd.DataFrame) -> pd.DataFrame:
    """Counts per split (no individual rows)."""
    g = snap.groupby("split").agg(n=("y", "size"), reprobados=("y", "sum"), personas=("persona_key", "nunique"))
    g["tasa_reprobacion"] = g["reprobados"] / g["n"]
    return g.reset_index()


def hash_snapshot(snap: pd.DataFrame) -> str:
    cols = ["intento_id", "y", "n_hist_curso", "n_intentos_acum", "n_prereq"]
    h = pd.util.hash_pandas_object(snap[cols].astype(str), index=False).to_numpy()
    return hashlib.sha256(h.tobytes()).hexdigest()


def build(conn, core_schema="neural_core", mart_schema="neural_mart", meta_schema="neural_meta",
          out: Callable[[str], None] = print, stg_schema="neural_stg"):
    for schema in (core_schema, mart_schema, meta_schema, stg_schema):
        if schema not in ALLOWED_SCHEMAS:
            raise RuntimeError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    schemas = {"core": core_schema, "mart": mart_schema, "meta": meta_schema, "stg": stg_schema}
    t0 = time.monotonic()
    ep, es, it, via, malla, prereq, doc, deptos, latest = cargar(conn, schemas)
    out(f"cargado: {len(ep):,} episodios, {len(es):,} estados, {len(it):,} intentos, {len(malla):,} filas de malla, "
        f"{len(prereq):,} prerrequisitos, {len(doc):,} secciones-docente, {len(deptos):,} cursos con departamento "
        f"({time.monotonic() - t0:.0f} s); "
        f"periodo maximo regular {latest}")
    snap, embudo = F2.construir_snapshot_t2(ep, it, es, via, malla, prereq, doc, latest, deptos=deptos)
    del it, es
    out(f"construido: {len(snap):,} filas ({time.monotonic() - t0:.0f} s)")
    digest = hash_snapshot(snap)
    tabla = preparar_tabla(snap)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart_schema}.snapshot_t2, {mart_schema}.snapshot_t2_resumen")
        _copy(conn, f"{mart_schema}.snapshot_t2", F2.SNAPSHOT_COLS_T2, tabla)
        with conn.cursor() as cur:
            rows = [("periodo_maximo", latest, "ultimo periodo regular con estados; los periodos >= este quedan fuera"),
                    ("hash_datos", digest, "sha256 de (intento, y, n_hist_curso, n_intentos_acum, n_prereq)")]
            for i, e in enumerate(embudo):
                rows.append((f"embudo_{i + 1:02d}", str(e["n"]), e["paso"]))
            cur.executemany(f"INSERT INTO {mart_schema}.snapshot_t2_resumen (clave, valor, nota) VALUES (%s, %s, %s)",
                            rows)
    res = resumen_filas(snap)
    out(res.to_string(index=False))
    for e in embudo:
        out(f"  embudo: {e['n']:>10,}  {e['paso']}")
    out(f"hash de datos: {digest}")
    out(f"total: {time.monotonic() - t0:.0f} s (una transaccion)")
    return snap, embudo, res


def main(argv: Optional[List[str]] = None) -> int:
    argparse.ArgumentParser(description="Rebuild neural_mart.snapshot_t2 (task T2) from neural_core.").parse_args(argv)
    try:
        from ..common.db import dev_connection

        with dev_connection() as conn:
            build(conn)
    except Exception as exc:  # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
