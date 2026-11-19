"""Build ``neural_mart.snapshot_t6`` (task T6, docs/12_benchmark_t6.md).

``python -m pipelines.snapshots.t6`` reads ``neural_core`` (localhost dev DB only), builds the point-in-time snapshot with
``features_t6.construir_snapshot_t6`` and replaces the table in ONE transaction. Output: counts only. Needs migrations
013, 014 and 018 (``python -m pipelines.migrate``). Population: T3 units (D47) that reached egreso; label: first enrolled
UCN postgrado semester (``neural_core.matricula_postgrado``).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from typing import Callable, Dict, List, Optional

import pandas as pd

from ..migrate import ALLOWED_SCHEMAS
from . import features_t6 as F6
from . import rules_t3 as R3
from . import rules_t6 as R6
from . import t1 as T1
from . import t3 as T3

Q_POSTGRADO = "SELECT persona_key, cod_programa, periodo, estado_matricula, cod_estado FROM {core}.matricula_postgrado"
# P77: enrolled (M) states of the postgrado state source and the level of each program
Q_ESTADOS_POS = "SELECT persona_key, cod_programa, periodo, cod_estado FROM {core}.estado_postgrado WHERE cod_estado = 'M'"
Q_PROGRAMAS_POS = "SELECT cod_programa, nivel_derivado FROM {core}.programa_postgrado"
ENTEROS = ("episodio_id", "cohorte_anio", "anio_egreso", "seguimiento", "tiempo", "evento", "tiempo_cualquier_fila",
           "evento_cualquier_fila", "intentos_evaluados", "aprobados", "reprobados", "n_notas_promedio", "convalidaciones",
           "cursos_verano_invierno", "n_interrupcion", "cambios_catalogo", "semestres_matriculados",
           "intentos_ult_semestre", "n_sem_sin_reprobacion", "semestres_a_egreso", "evento_estados", "tiempo_estados")


def cargar(conn, schemas: Dict[str, str]):
    ep, es, it, via, tit, malla, prog_cat, latest = T3.cargar(conn, schemas)
    pg = T1._read(conn, Q_POSTGRADO, schemas)
    pos = T1._read(conn, Q_ESTADOS_POS, schemas)
    niveles = T1._read(conn, Q_PROGRAMAS_POS, schemas)
    return ep, es, it, via, tit, malla, prog_cat, pg, pos, niveles, latest


def preparar_tabla(snap: pd.DataFrame) -> pd.DataFrame:
    s = snap.copy()
    s["episodio_especialidad_id"] = s["episodio_especialidad_id"].astype("Int64").astype(object).where(
        s["episodio_especialidad_id"].notna(), None)
    s["nivel_estados"] = s["nivel_estados"].astype(object).where(s["nivel_estados"].notna(), None)
    for col in ("trayectoria_plan_comun", "especialidad_conocida_al_corte", "titulado_al_corte", "previo_estados"):
        s[col] = s[col].astype(bool)
    for col in ENTEROS:
        s[col] = s[col].astype("int64")
    return s[F6.SNAPSHOT_COLS_T6]


def resumen_filas(snap: pd.DataFrame) -> pd.DataFrame:
    """Counts per split / event (no individual rows)."""
    return snap.groupby(["split", "evento"]).size().rename("n").reset_index()


def hash_snapshot(snap: pd.DataFrame) -> str:
    cols = ["episodio_id", "anio_egreso", "tiempo", "evento", "seguimiento", "creditos_aprobados", "semestres_a_egreso"]
    h = pd.util.hash_pandas_object(snap[cols].astype(str), index=False).to_numpy()
    return hashlib.sha256(h.tobytes()).hexdigest()


def build(conn, core_schema="neural_core", mart_schema="neural_mart", meta_schema="neural_meta",
          out: Callable[[str], None] = print):
    for schema in (core_schema, mart_schema, meta_schema):
        if schema not in ALLOWED_SCHEMAS:
            raise RuntimeError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    schemas = {"core": core_schema, "mart": mart_schema, "meta": meta_schema}
    t0 = time.monotonic()
    ep, es, it, via, tit, malla, prog_cat, pg, pos, niveles, latest = cargar(conn, schemas)
    out(f"cargado: {len(ep):,} episodios, {len(es):,} estados, {len(it):,} intentos, {len(pg):,} filas de postgrado "
        f"y {len(pos):,} matriculas de la fuente de estados de postgrado "
        f"({time.monotonic() - t0:.0f} s); periodo maximo regular {latest}, ultimo periodo cerrado {R3.periodo_cierre(latest)}")
    snap, embudo = F6.construir_snapshot_t6(ep, es, it, via, tit, malla, prog_cat, pg, latest, pos, niveles)
    s = preparar_tabla(snap)
    out(f"construido: {len(s):,} filas (una por trayectoria egresada) ({time.monotonic() - t0:.0f} s)")
    digest = hash_snapshot(snap)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart_schema}.snapshot_t6, {mart_schema}.snapshot_t6_resumen")
        T1._copy(conn, f"{mart_schema}.snapshot_t6", F6.SNAPSHOT_COLS_T6, s)
        with conn.cursor() as cur:
            rows = [("periodo_maximo", latest, "ultimo periodo regular con estados (en curso)"),
                    ("periodo_cierre", str(R3.periodo_cierre(latest)), "ultimo periodo regular cerrado: limite del seguimiento"),
                    ("ordinal_cierre", str(R6.ordinal_cierre(latest)), "semestre calendario del cierre (50 = primer semestre, 60 = segundo)"),
                    ("hash_datos", digest, "sha256 de (trayectoria, anio de egreso, tiempo, evento, seguimiento, creditos, semestres)"),
                    ("postgrado_filas", str(len(pg)), "filas de neural_core.matricula_postgrado leidas"),
                    ("estados_pos_matriculas", str(len(pos)), "matriculas (M) de neural_core.estado_postgrado leidas (P77)")]
            rows += [(f"embudo_{key}", str(valor), None) for key, valor in embudo.items()]
            cur.executemany(f"INSERT INTO {mart_schema}.snapshot_t6_resumen (clave, valor, nota) VALUES (%s, %s, %s)", rows)
    out(resumen_filas(snap).to_string(index=False))
    out(f"embudo: {embudo}")
    out(f"hash de datos: {digest}")
    out(f"total: {time.monotonic() - t0:.0f} s (una transaccion)")
    return snap, embudo


def main(argv: Optional[List[str]] = None) -> int:
    argparse.ArgumentParser(description="Rebuild neural_mart.snapshot_t6 (task T6) from neural_core.").parse_args(argv)
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
