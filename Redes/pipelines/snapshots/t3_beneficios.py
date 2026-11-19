"""Build the benefit features of T3 (``neural_mart.snapshot_t3_beneficios``) and the late-cut extension (``snapshot_t3_ext*``).

``python -m pipelines.snapshots.t3_beneficios`` (localhost dev DB only; needs migrations 013, 014, 024 and 027 and a built
``snapshot_t3``):

1. builds the T3 snapshot at the late cuts ``k = 8, 10`` with the SAME construction as the official one (``features_t3``) and
   stores it in ``snapshot_t3_ext`` / ``snapshot_t3_ext_semestre`` (the official tables are not touched);
2. builds the benefit features of every cut ``k in {2, 4, 8, 10}`` under both point-in-time rules (``rules_beneficios_t3``) and
   replaces ``snapshot_t3_beneficios`` in ONE transaction. Output: counts only, never a row of a person.

Run it again after every rebuild of ``snapshot_t3`` (the side table is keyed by episode and the official one is refilled).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from ..migrate import ALLOWED_SCHEMAS
from . import features_beneficios_t3 as FT
from . import features_t3 as F3
from . import rules_beneficios_t3 as RT
from . import rules_t3 as R3
from . import t1 as T1
from . import t3 as T3

Q_CORTES = "SELECT episodio_id, k, persona_key, cod_programa, periodo_admision FROM {mart}.snapshot_t3 WHERE k = ANY(%s)"
Q_INGRESO = "SELECT episodio_id, cod_programa AS cod_programa_ingreso FROM {core}.episodio_programa"
COLS_TABLA = ["episodio_id", "k", "regla", "ben_sin_dato", "anio_ben", "tiene_gratuidad", "tiene_credito", "tiene_beca_estatal",
              "tiene_beca_ucn", "merito_ingreso", "merito_e1", "n_beneficios", "monto_sem1", "anios_con_gratuidad",
              "expiro_gratuidad", "etapa_capstone", "expiro_alguna", "capstone_alguna", "perdida_sin_dato", "perdio_gratuidad",
              "perdio_credito", "perdio_cualquier_beneficio", "obtuvo_gratuidad", "banda_decil", "banda_decil_eq"]


def preparar_cortes(snap: pd.DataFrame, ingreso: pd.DataFrame) -> pd.DataFrame:
    """Cut rows for the benefit features: admission program and the period at which each cut ends."""
    c = snap[["episodio_id", "k", "persona_key", "cod_programa", "periodo_admision"]].merge(ingreso, on="episodio_id", how="left")
    c["periodo_corte"] = [RT.periodo_corte(p, int(k)) for p, k in zip(c["periodo_admision"], c["k"])]
    return c


def construir_filas(cortes: pd.DataFrame, beneficios: pd.DataFrame) -> pd.DataFrame:
    """One row per (episode, k, rule); ``banda_decil_eq`` is the band of the cut year (descriptive, fairness only)."""
    por_regla = {r: FT.features_beneficios_t3(cortes, beneficios, r) for r in RT.REGLAS}
    banda_eq = por_regla["con_t"].set_index(["episodio_id", "k"])["banda_decil"]
    filas = []
    for regla, f in por_regla.items():
        f = f.copy()
        f.insert(2, "regla", regla)
        f["banda_decil_eq"] = banda_eq.reindex(pd.MultiIndex.from_frame(f[["episodio_id", "k"]])).to_numpy()
        filas.append(f)
    out = pd.concat(filas, ignore_index=True)
    for col in ("episodio_id", "k", "ben_sin_dato", "perdida_sin_dato"):
        out[col] = out[col].astype("int64")
    out["anio_ben"] = out["anio_ben"].astype("Int64").astype(object).where(out["anio_ben"].notna(), None)
    for col in ("banda_decil", "banda_decil_eq"):
        out[col] = out[col].astype(object).where(out[col].notna(), None)
    return out[COLS_TABLA]


def resumen_cobertura(filas: pd.DataFrame) -> pd.DataFrame:
    """Counts per k / rule: rows and share with data (aggregates only)."""
    g = filas.groupby(["k", "regla"])
    return pd.DataFrame({"n": g.size(), "con_dato": g["ben_sin_dato"].apply(lambda s: int((s == 0).sum()))}).reset_index()


def construir_extension(conn, schemas: Dict[str, str], out: Callable[[str], None]):
    t0 = time.monotonic()
    ep, es, it, via, tit, malla, prog_cat, latest = T3.cargar(conn, schemas)
    snap, sem, embudo = F3.construir_snapshot_t3(ep, es, it, via, tit, malla, prog_cat, latest, ks=RT.K_EXTENSION)
    s, t = T3.preparar_tablas(snap, sem)
    out(f"extension k={RT.K_EXTENSION}: {len(s):,} filas (episodio, k), {len(t):,} filas de semestre ({time.monotonic() - t0:.0f} s)")
    digest = T3.hash_snapshot(snap)
    mart = schemas["mart"]
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart}.snapshot_t3_ext, {mart}.snapshot_t3_ext_semestre, {mart}.snapshot_t3_ext_resumen")
        T1._copy(conn, f"{mart}.snapshot_t3_ext", F3.SNAPSHOT_COLS_T3, s)
        T1._copy(conn, f"{mart}.snapshot_t3_ext_semestre", T3.SEMESTRE_COLS, t)
        rows = [("periodo_cierre", R3.periodo_cierre(latest), None), ("hash_datos", digest, "sha256 as snapshot_t3, late cuts"),
                ("ks", ",".join(map(str, RT.K_EXTENSION)), None)]
        for e in embudo:
            for key, valor in e.items():
                if key != "k":
                    rows.append((f"embudo_k{e['k']}_{key}", str(valor), None))
        with conn.cursor() as cur:
            cur.executemany(f"INSERT INTO {mart}.snapshot_t3_ext_resumen (clave, valor, nota) VALUES (%s, %s, %s)", rows)
    out(T3.resumen_filas(snap).to_string(index=False))
    return snap


def build(conn, out: Callable[[str], None] = print, solo_beneficios: bool = False) -> pd.DataFrame:
    schemas = {"core": "neural_core", "mart": "neural_mart", "meta": "neural_meta", "stg": "neural_stg"}
    for schema in schemas.values():
        if schema not in ALLOWED_SCHEMAS:
            raise RuntimeError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    t0 = time.monotonic()
    if solo_beneficios:
        with conn.cursor() as cur:
            cur.execute(Q_CORTES.format(**schemas).replace("snapshot_t3 ", "snapshot_t3_ext ") + "", (list(RT.K_EXTENSION),))
            cols = [d.name for d in cur.description]
            ext = pd.DataFrame(cur.fetchall(), columns=cols)
    else:
        ext = construir_extension(conn, schemas, out)
    with conn.cursor() as cur:
        cur.execute(Q_CORTES.format(**schemas), (list(RT.K_OFICIALES),))
        oficial = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    ingreso = T1._read(conn, Q_INGRESO, schemas)
    ben = T1._read(conn, T1.Q_BENEFICIOS, {"stg": schemas["stg"]})
    ben["periodo"] = pd.to_numeric(ben["periodo"]).astype("int64")
    ben["benef_sem1"] = pd.to_numeric(ben["benef_sem1"]).astype("float64")
    cortes = preparar_cortes(pd.concat([oficial, ext[["episodio_id", "k", "persona_key", "cod_programa", "periodo_admision"]]],
                                       ignore_index=True), ingreso)
    filas = construir_filas(cortes, ben)
    cob = resumen_cobertura(filas)
    mart = schemas["mart"]
    digest = hashlib.sha256(pd.util.hash_pandas_object(filas[["episodio_id", "k", "regla", "ben_sin_dato", "n_beneficios"]].astype(str),
                                                       index=False).to_numpy().tobytes()).hexdigest()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart}.snapshot_t3_beneficios, {mart}.snapshot_t3_beneficios_resumen")
        T1._copy(conn, f"{mart}.snapshot_t3_beneficios", COLS_TABLA, filas)
        rows = [("hash_beneficios", digest, "sha256 of (episode, k, rule, ben_sin_dato, n_beneficios)"),
                ("anio_beneficios_max", str(int(ben["periodo"].max())), "latest benefit year loaded"),
                ("ks", ",".join(map(str, RT.K_BENEFICIOS)), None)]
        rows += [(f"filas_k{r.k}_{r.regla}", str(r.n), None) for r in cob.itertuples()]
        rows += [(f"con_dato_k{r.k}_{r.regla}", str(r.con_dato), None) for r in cob.itertuples()]
        with conn.cursor() as cur:
            cur.executemany(f"INSERT INTO {mart}.snapshot_t3_beneficios_resumen (clave, valor, nota) VALUES (%s, %s, %s)", rows)
    out(cob.to_string(index=False))
    out(f"hash: {digest}; total {time.monotonic() - t0:.0f} s (una transaccion por tabla)")
    return filas


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the T3 benefit features and the late-cut extension.")
    ap.add_argument("--solo-beneficios", action="store_true", help="skip the extension rebuild (it must already exist)")
    args = ap.parse_args(argv)
    try:
        from ..common.db import dev_connection

        with dev_connection() as conn:
            build(conn, solo_beneficios=args.solo_beneficios)
    except Exception as exc:  # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
