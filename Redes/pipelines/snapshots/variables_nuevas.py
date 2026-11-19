"""Build the side tables of the new variables of T3-T6 (``neural_mart.snapshot_variables_nuevas`` and ``..._t6``).

``python -m pipelines.snapshots.variables_nuevas`` (localhost dev DB only; needs migration 031 and built ``snapshot_t3`` and
``snapshot_t6``) reads ``neural_core`` and the cuts of the official snapshots, builds the variables with
``features_variables`` and replaces both tables in ONE transaction. The official snapshots are not touched. Output: counts
only, never a row of a person. Run it again after every rebuild of ``snapshot_t3`` / ``snapshot_t6``.
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
from . import features as F
from . import features_t3 as F3
from . import features_variables as FV
from . import t1 as T1
from . import t3 as T3

Q_CORTES_T3 = "SELECT episodio_id, k, persona_key, cod_programa, periodo_admision FROM {mart}.snapshot_t3"
Q_CORTES_T6 = "SELECT episodio_id, semestres_a_egreso AS k, cod_programa, periodo_admision, promedio_evaluado FROM {mart}.snapshot_t6"
Q_INTENTOS_X = """
SELECT intento_id, oportunidad, titulo, cod_carrera, catalogo FROM {core}.intento_asignatura WHERE episodio_id IS NOT NULL
"""
Q_MALLA_X = """
SELECT cod_programa, catalogo, codigo_asignatura, semestre, semestre_texto, creditos, formacion, nombre_asignatura
FROM {core}.asignatura_malla
"""
COLS_TABLA_T3 = ["episodio_id", "k", *FV.VARIABLES_NUEVAS]
COLS_TABLA_T6 = ["episodio_id", "ranking_prom_egreso", "nota_titulo", "nota_practica"]


def _preparar(f: pd.DataFrame, columnas: List[str], bools: List[str]) -> pd.DataFrame:
    out = f[columnas].copy()
    for c in columnas:
        if c in ("episodio_id", "k"):
            out[c] = out[c].astype("int64")
        elif c in bools:
            out[c] = out[c].astype(bool)
        else:
            out[c] = out[c].astype("float64").astype(object).where(out[c].notna(), None)
    return out


def construir(conn, schemas: Dict[str, str], out: Callable[[str], None] = print):
    """``(variables_t3, variables_t6)`` as DataFrames ready to copy."""
    t0 = time.monotonic()
    ep, es, it, via, tit, malla, prog_cat, latest = T3.cargar(conn, schemas)
    del via
    extra = T1._read(conn, Q_INTENTOS_X, schemas)
    extra["oportunidad"] = pd.to_numeric(extra["oportunidad"]).astype("float64")
    it = it.merge(extra, on="intento_id", how="left")
    del extra
    mx = T1._read(conn, Q_MALLA_X, schemas)
    out(f"cargado ({time.monotonic() - t0:.0f} s): {len(it):,} intentos, {len(mx):,} filas de malla")
    u = F3.unidades_t3(ep, es, tit, it)
    pop = u.pop
    cortes = T1._read(conn, Q_CORTES_T3, schemas)
    cortes["k"] = cortes["k"].astype("int64")
    v3 = FV.construir_variables(cortes, pop, u.intentos, mx, ep, prog_cat)
    out(f"variables T3/T4/T5: {len(v3):,} filas ({time.monotonic() - t0:.0f} s)")

    c6 = T1._read(conn, Q_CORTES_T6, schemas)
    c6["k"] = c6["k"].astype("int64")
    c6["promedio_evaluado"] = pd.to_numeric(c6["promedio_evaluado"]).astype("float64")
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    c6["ord_egreso"] = base.reindex(c6["episodio_id"]).to_numpy() + c6["k"].to_numpy() - 1
    rk = FV.ranking_egreso(c6)
    nt = FV.nota_titulo(u.intentos, c6[["episodio_id", "k"]], pop)
    v6 = c6[["episodio_id"]].merge(rk, on="episodio_id", how="left").merge(nt, on="episodio_id", how="left")
    out(f"variables T6: {len(v6):,} filas ({time.monotonic() - t0:.0f} s)")
    return v3, v6


def cobertura(v3: pd.DataFrame, v6: pd.DataFrame) -> Dict[str, str]:
    """Share of non-missing values per variable and k (aggregates only)."""
    res: Dict[str, str] = {}
    for k, g in v3.groupby("k"):
        for c in FV.VARIABLES_NUEVAS:
            res[f"cobertura_k{k}_{c}"] = f"{float(g[c].notna().mean()):.4f}"
    for c in COLS_TABLA_T6[1:]:
        res[f"cobertura_t6_{c}"] = f"{float(v6[c].notna().mean()):.4f}"
    return res


def build(conn, out: Callable[[str], None] = print):
    schemas = {"core": "neural_core", "mart": "neural_mart", "meta": "neural_meta", "stg": "neural_stg"}
    for schema in schemas.values():
        if schema not in ALLOWED_SCHEMAS:
            raise RuntimeError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    t0 = time.monotonic()
    v3, v6 = construir(conn, schemas, out)
    t3 = _preparar(v3, COLS_TABLA_T3, FV.VARS_BOOL)
    t6 = _preparar(v6, COLS_TABLA_T6, [])
    digest = hashlib.sha256(pd.util.hash_pandas_object(
        v3[["episodio_id", "k", "reg_rep2_total", "creditos_malla_total_corr", "alc_rezago"]].astype(str), index=False
    ).to_numpy().tobytes()).hexdigest()
    cob = cobertura(v3, v6)
    mart = schemas["mart"]
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart}.snapshot_variables_nuevas, {mart}.snapshot_variables_nuevas_t6, "
                        f"{mart}.snapshot_variables_nuevas_resumen")
        T1._copy(conn, f"{mart}.snapshot_variables_nuevas", COLS_TABLA_T3, t3)
        T1._copy(conn, f"{mart}.snapshot_variables_nuevas_t6", COLS_TABLA_T6, t6)
        rows = [("hash_datos", digest, "sha256 of (episode, k, reg_rep2_total, total_corr, rezago)"),
                ("filas_t3", str(len(t3)), None), ("filas_t6", str(len(t6)), None)]
        rows += [(k, v, None) for k, v in cob.items()]
        with conn.cursor() as cur:
            cur.executemany(f"INSERT INTO {mart}.snapshot_variables_nuevas_resumen (clave, valor, nota) VALUES (%s, %s, %s)", rows)
    out(f"hash: {digest}; total {time.monotonic() - t0:.0f} s (una transaccion)")
    return v3, v6


def main(argv: Optional[List[str]] = None) -> int:
    argparse.ArgumentParser(description="Build the side tables of the new variables of T3-T6.").parse_args(argv)
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
