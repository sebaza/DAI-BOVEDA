"""Build ``neural_mart.snapshot_t45`` / ``snapshot_t45_semestre`` (tasks T4 and T5, docs/11_benchmark_t4_t5.md).

``python -m pipelines.snapshots.t45`` reads ``neural_core`` and ``neural_mart.programa_traslados`` (localhost dev DB only),
builds the point-in-time snapshot with ``features_t45.construir_snapshot_t45`` and replaces the tables in ONE transaction.
Output: counts only. Needs migrations 013-015 and 017 (``python -m pipelines.migrate``) and the transfers mart
(``python -m pipelines.marts``).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from typing import Callable, Dict, List, Optional

import pandas as pd

from ..migrate import ALLOWED_SCHEMAS
from . import features_t45 as F45
from . import rules_t3 as R3
from . import t1 as T1
from . import t3 as T3

Q_TRASLADOS = """
SELECT origen_episodio_id, destino_episodio_id, tipo, ambiguo, primer_periodo_destino, ultimo_periodo_origen
FROM {mart}.programa_traslados
"""


def cargar(conn, schemas: Dict[str, str]):
    ep, es, it, via, tit, malla, prog_cat, latest = T3.cargar(conn, schemas)
    tr = T1._read(conn, Q_TRASLADOS, schemas)
    tr["ambiguo"] = tr["ambiguo"].astype(bool)
    return ep, es, it, via, tit, malla, prog_cat, tr, latest


def preparar_tablas(snap: pd.DataFrame, sem: pd.DataFrame):
    s = snap.copy()
    s["episodio_especialidad_id"] = s["episodio_especialidad_id"].astype("Int64").astype(object).where(
        s["episodio_especialidad_id"].notna(), None)
    for col in ("trayectoria_plan_comun", "especialidad_conocida_al_corte", "hubo_transicion_en_horizonte",
                "hubo_eliminacion_en_horizonte", "eliminacion_con_reintegro", "eliminacion_efectiva",
                "horizonte_e_dudoso"):
        s[col] = s[col].astype(bool)
    s["otra_salida_tipo"] = s["otra_salida_tipo"].astype(object).where(s["otra_salida_tipo"].notna(), None)
    for col in ("episodio_id", "k", "cohorte_anio", "seguimiento_max", "intentos_evaluados", "aprobados", "reprobados",
                "n_notas_promedio", "convalidaciones", "cursos_verano_invierno", "n_interrupcion", "cambios_catalogo",
                "semestres_matriculados", "intentos_ult_semestre", "n_sem_sin_reprobacion"):
        s[col] = s[col].astype("int64")
    _, t = T1.preparar_tablas(snap.iloc[:0].assign(continua=None, continua_mismo_programa=None), sem)
    return s, t


def resumen_filas(snap: pd.DataFrame) -> pd.DataFrame:
    """Counts per k / split / outcome (no individual rows)."""
    return snap.groupby(["k", "split", "resultado"]).size().rename("n").reset_index()


def hash_snapshot(snap: pd.DataFrame) -> str:
    cols = ["episodio_id", "k", "resultado", "seguimiento_max", "creditos_aprobados", "intentos_evaluados"]
    h = pd.util.hash_pandas_object(snap[cols].astype(str), index=False).to_numpy()
    return hashlib.sha256(h.tobytes()).hexdigest()


def build(conn, core_schema="neural_core", mart_schema="neural_mart", meta_schema="neural_meta",
          out: Callable[[str], None] = print):
    for schema in (core_schema, mart_schema, meta_schema):
        if schema not in ALLOWED_SCHEMAS:
            raise RuntimeError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    schemas = {"core": core_schema, "mart": mart_schema, "meta": meta_schema}
    t0 = time.monotonic()
    ep, es, it, via, tit, malla, prog_cat, tr, latest = cargar(conn, schemas)
    out(f"cargado: {len(ep):,} episodios, {len(es):,} estados, {len(it):,} intentos, {len(tr):,} traslados "
        f"({time.monotonic() - t0:.0f} s); periodo maximo regular {latest}, ultimo periodo cerrado {R3.periodo_cierre(latest)}")
    snap, sem, embudo = F45.construir_snapshot_t45(ep, es, it, via, tit, malla, prog_cat, tr, latest)
    s, t = preparar_tablas(snap, sem)
    out(f"construido: {len(s):,} filas (trayectoria, k), {len(t):,} filas de semestre ({time.monotonic() - t0:.0f} s)")
    digest = hash_snapshot(snap)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart_schema}.snapshot_t45, {mart_schema}.snapshot_t45_semestre, "
                        f"{mart_schema}.snapshot_t45_resumen")
        T1._copy(conn, f"{mart_schema}.snapshot_t45", F45.SNAPSHOT_COLS_T45, s)
        T1._copy(conn, f"{mart_schema}.snapshot_t45_semestre", T1.SEMESTRE_COLS, t)
        with conn.cursor() as cur:
            rows = [("periodo_maximo", latest, "ultimo periodo regular con estados (en curso)"),
                    ("periodo_cierre", R3.periodo_cierre(latest), "ultimo periodo regular cerrado: limite del seguimiento"),
                    ("hash_datos", digest, "sha256 de (trayectoria, k, resultado, seguimiento, creditos, intentos)"),
                    ("traslados_filas", str(len(tr)), "filas de neural_mart.programa_traslados leidas")]
            for e in embudo:
                for key, valor in e.items():
                    if key != "k":
                        rows.append((f"embudo_k{e['k']}_{key}", str(valor), None))
            cur.executemany(f"INSERT INTO {mart_schema}.snapshot_t45_resumen (clave, valor, nota) VALUES (%s, %s, %s)",
                            rows)
    out(resumen_filas(snap).to_string(index=False))
    out(f"hash de datos: {digest}")
    out(f"total: {time.monotonic() - t0:.0f} s (una transaccion)")
    return snap, embudo


def main(argv: Optional[List[str]] = None) -> int:
    argparse.ArgumentParser(description="Rebuild neural_mart.snapshot_t45 (tasks T4 and T5) from neural_core.").parse_args(argv)
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
