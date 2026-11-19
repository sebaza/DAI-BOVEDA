"""Build ``neural_mart.snapshot_t3`` / ``snapshot_t3_semestre`` (task T3, docs/10_benchmark_t3.md).

``python -m pipelines.snapshots.t3`` reads ``neural_core`` (localhost dev DB only), builds the point-in-time
snapshot with ``features_t3.construir_snapshot_t3`` and replaces the tables in ONE transaction. Output: counts only.
Needs migrations 013 and 014 (``python -m pipelines.migrate``). Population: D47 (exchange out, Plan Comun merged).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from typing import Callable, Dict, List, Optional

import pandas as pd

from ..marts.rules import periodo_de_fecha
from ..migrate import ALLOWED_SCHEMAS
from . import features_t3 as F3
from . import rules_t3 as R3
from . import t1 as T1

SEMESTRE_COLS: List[str] = T1.SEMESTRE_COLS
Q_EPISODIOS_T3 = """
SELECT e.episodio_id, e.persona_key, e.cod_programa, e.periodo_admision, e.cod_admision, e.catalogo_inicial,
       p.id_nivel, p.sede::text AS sede, d.tipo_qualitas, per.sexo
FROM {core}.episodio_programa e
LEFT JOIN {core}.programa p ON p.cod_programa = e.cod_programa
LEFT JOIN {meta}.dic_tipo_admision d ON d.cod_admision = e.cod_admision
LEFT JOIN {core}.persona per ON per.persona_key = e.persona_key
"""
Q_MALLA = "SELECT cod_programa, catalogo, codigo_asignatura, semestre, creditos FROM {core}.asignatura_malla"
Q_PROG_CAT = "SELECT cod_programa, catalogo, duracion FROM {core}.programa_catalogo"


def cargar(conn, schemas: Dict[str, str]):
    ep = T1._read(conn, Q_EPISODIOS_T3, schemas)
    ep["id_nivel"] = pd.to_numeric(ep["id_nivel"]).astype("Int64")
    es = T1._read(conn, T1.Q_ESTADOS, schemas)
    es["episodio_id"] = es["episodio_id"].astype("Int64")
    it = T1._read(conn, T1.Q_INTENTOS, schemas)
    for col in ("nota_numerica", "creditos", "creditos_reconocidos"):
        it[col] = pd.to_numeric(it[col]).astype("float64")
    it["periodo"] = it["periodo"].astype("category")
    it["resultado_tipo"] = it["resultado_tipo"].astype("category")
    via = T1._read(conn, T1.Q_VIA, schemas)
    for col in ("puntaje_leng", "puntaje_mat", "puntaje_ciencias", "puntaje_historia", "puntaje_nem",
                "puntaje_ranking", "notas_em", "ponderado"):
        via[col] = pd.to_numeric(via[col]).astype("float64")
    tit = T1._read(conn, T1.Q_TITULACION, schemas)
    tit["periodo"] = tit["fecha_titulacion"].map(periodo_de_fecha)
    tit = tit.loc[tit["periodo"].notna(), ["persona_key", "episodio_id", "periodo"]]
    malla = T1._read(conn, Q_MALLA, schemas)
    for col in ("semestre", "creditos"):
        malla[col] = pd.to_numeric(malla[col]).astype("float64")
    prog_cat = T1._read(conn, Q_PROG_CAT, schemas)
    with conn.cursor() as cur:
        cur.execute(T1.Q_LATEST.format(**schemas))
        latest = cur.fetchone()[0]
    if latest is None:
        raise RuntimeError("no regular period in evento_estado: build neural_core first")
    return ep, es, it, via, tit, malla, prog_cat, latest


def preparar_tablas(snap: pd.DataFrame, sem: pd.DataFrame):
    s = snap.copy()
    s["salida_a_otro_programa"] = s["salida_a_otro_programa"].astype(object).where(
        s["salida_a_otro_programa"].notna(), None)
    s["tiempo_titulacion"] = s["tiempo_titulacion"].astype("Int64").astype(object).where(
        s["tiempo_titulacion"].notna(), None)
    s["episodio_especialidad_id"] = s["episodio_especialidad_id"].astype("Int64").astype(object).where(
        s["episodio_especialidad_id"].notna(), None)
    for col in ("trayectoria_plan_comun", "especialidad_conocida_al_corte"):
        s[col] = s[col].astype(bool)
    s["salida_tipo"] = s["salida_tipo"].astype(object).where(s["salida_tipo"].notna(), None)
    for col in ("episodio_id", "k", "cohorte_anio", "seguimiento_max", "tiempo", "causa", "intentos_evaluados",
                "aprobados", "reprobados", "n_notas_promedio", "convalidaciones", "cursos_verano_invierno",
                "n_interrupcion", "cambios_catalogo", "semestres_matriculados", "intentos_ult_semestre",
                "n_sem_sin_reprobacion"):
        s[col] = s[col].astype("int64")
    _, t = T1.preparar_tablas(snap.iloc[:0].assign(continua=None, continua_mismo_programa=None), sem)
    return s, t


def resumen_filas(snap: pd.DataFrame) -> pd.DataFrame:
    """Counts per k / split / cause (no individual rows)."""
    return snap.groupby(["k", "split", "causa"]).size().rename("n").reset_index()


def hash_snapshot(snap: pd.DataFrame) -> str:
    cols = ["episodio_id", "k", "tiempo", "causa", "seguimiento_max", "creditos_aprobados", "intentos_evaluados"]
    h = pd.util.hash_pandas_object(snap[cols].astype(str), index=False).to_numpy()
    return hashlib.sha256(h.tobytes()).hexdigest()


def build(conn, core_schema="neural_core", mart_schema="neural_mart", meta_schema="neural_meta",
          out: Callable[[str], None] = print):
    for schema in (core_schema, mart_schema, meta_schema):
        if schema not in ALLOWED_SCHEMAS:
            raise RuntimeError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    schemas = {"core": core_schema, "mart": mart_schema, "meta": meta_schema}
    t0 = time.monotonic()
    ep, es, it, via, tit, malla, prog_cat, latest = cargar(conn, schemas)
    out(f"cargado: {len(ep):,} episodios, {len(es):,} estados, {len(it):,} intentos ({time.monotonic() - t0:.0f} s); "
        f"periodo maximo regular {latest}, ultimo periodo cerrado {R3.periodo_cierre(latest)}")
    snap, sem, embudo = F3.construir_snapshot_t3(ep, es, it, via, tit, malla, prog_cat, latest)
    s, t = preparar_tablas(snap, sem)
    out(f"construido: {len(s):,} filas (episodio, k), {len(t):,} filas de semestre ({time.monotonic() - t0:.0f} s)")
    digest = hash_snapshot(snap)
    u = F3.unidades_t3(ep, es, tit)
    cons = F3.consistencia_fuentes(u.pop, u.estados, u.egreso, latest)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart_schema}.snapshot_t3, {mart_schema}.snapshot_t3_semestre, "
                        f"{mart_schema}.snapshot_t3_resumen")
        T1._copy(conn, f"{mart_schema}.snapshot_t3", F3.SNAPSHOT_COLS_T3, s)
        T1._copy(conn, f"{mart_schema}.snapshot_t3_semestre", SEMESTRE_COLS, t)
        with conn.cursor() as cur:
            rows = [("periodo_maximo", latest, "ultimo periodo regular con estados (en curso)"),
                    ("periodo_cierre", R3.periodo_cierre(latest), "ultimo periodo regular cerrado: limite del seguimiento"),
                    ("hash_datos", digest, "sha256 de (episodio, k, tiempo, causa, seguimiento, creditos, intentos)")]
            rows += [(f"consistencia_{k_}", str(v), None) for k_, v in cons.items()]
            for e in embudo:
                for key, valor in e.items():
                    if key != "k":
                        rows.append((f"embudo_k{e['k']}_{key}", str(valor), None))
            cur.executemany(f"INSERT INTO {mart_schema}.snapshot_t3_resumen (clave, valor, nota) VALUES (%s, %s, %s)",
                            rows)
    out(resumen_filas(snap).to_string(index=False))
    out(f"hash de datos: {digest}")
    out(f"total: {time.monotonic() - t0:.0f} s (una transaccion)")
    return snap, embudo


def main(argv: Optional[List[str]] = None) -> int:
    argparse.ArgumentParser(description="Rebuild neural_mart.snapshot_t3 (task T3) from neural_core.").parse_args(argv)
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
