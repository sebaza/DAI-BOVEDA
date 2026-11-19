"""Build ``neural_mart.snapshot_t1`` / ``snapshot_t1_semestre`` (task T1, docs/08_benchmark_t1.md).

``python -m pipelines.snapshots.t1`` reads ``neural_core`` (localhost dev DB only), builds the point-in-time
snapshot with ``features.construir_snapshot`` and replaces both tables in ONE transaction. Output: counts only.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import sys
import time
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from ..marts.rules import periodo_de_fecha
from ..migrate import ALLOWED_SCHEMAS
from . import features as F
from . import features_beneficios as FB
from . import features_t1_nuevas as FN
from . import rules as R

SNAPSHOT_COLS: List[str] = [
    "episodio_id", "k", "persona_key", "cod_programa", "periodo_admision", "cohorte_anio", "periodo_corte",
    "periodo_horizonte", "split", "estado_muestra", "continua", "continua_mismo_programa", "no_continua_tipo",
    "cod_admision", "via_clase", "sede", "tipo_colegio", "depend_colegio", "region_colegio", "preferencia",
    "con_postulacion", *F.SCORE_COLS, "creditos_aprobados", "intentos_evaluados", "aprobados", "reprobados",
    "tasa_aprobacion", "promedio_evaluado", "n_notas_promedio", "convalidaciones", "cursos_verano_invierno",
    "n_interrupcion", "cambios_catalogo", "semestres_matriculados", "intentos_ult_semestre", "tasa_ult_semestre",
    "promedio_ult_semestre", "sexo_equidad", *F.ADMISION_P47, *FB.COLS_BENEFICIOS, *FN.COLS_NUEVAS_T1,
]
SEMESTRE_COLS: List[str] = [
    "episodio_id", "j", "matriculado", "interrupcion", "intentos_evaluados", "aprobados", "reprobados",
    "convalidaciones", "creditos_aprobados", "cursos_verano_invierno", "promedio", "n_notas_promedio",
    "creditos_acumulados",
]

Q_EPISODIOS = """
SELECT e.episodio_id, e.persona_key, e.cod_programa, e.periodo_admision, e.cod_admision, p.id_nivel,
       p.sede::text AS sede, d.tipo_qualitas, per.sexo
FROM {core}.episodio_programa e
LEFT JOIN {core}.programa p ON p.cod_programa = e.cod_programa
LEFT JOIN {meta}.dic_tipo_admision d ON d.cod_admision = e.cod_admision
LEFT JOIN {core}.persona per ON per.persona_key = e.persona_key
"""
Q_ESTADOS = """
SELECT persona_key, episodio_id, periodo, orden_canonico, cod_estado, cod_programa, catalogo, es_correccion_sistema
FROM {core}.evento_estado
"""
Q_INTENTOS = """
SELECT intento_id, episodio_id, periodo, codigo_asignatura, es_intento_evaluado, nota_numerica, nota_es_heredada,
       resultado_tipo, aprobado_curricular, creditos, creditos_reconocidos
FROM {core}.intento_asignatura WHERE episodio_id IS NOT NULL
"""
Q_VIA = """
SELECT postulacion_via_id, year_admision, persona_key, cod_carrera, cod_admision, preferencia, matricula,
       puntaje_leng, puntaje_mat, puntaje_ciencias, puntaje_historia, puntaje_nem, puntaje_ranking, notas_em,
       ponderado, tipo_colegio, depend_colegio, region_colegio
FROM {core}.postulacion_via
"""
Q_TITULACION = "SELECT persona_key, episodio_id, fecha_titulacion FROM {core}.titulacion"
Q_BENEFICIOS = """
SELECT periodo, persona_key, cod_carrera, codigo, benef_sem1 FROM {stg}.banner_beneficios
"""
# New variables (P117-P127, migration 030): read apart from the queries above because other snapshots reuse those.
Q_OPORTUNIDAD = "SELECT intento_id, oportunidad FROM {core}.intento_asignatura WHERE episodio_id IS NOT NULL"
Q_FECHAS = "SELECT persona_key, orden_canonico, fecha_estado_original, fecha_marcador FROM {core}.evento_estado"
Q_CATALOGO_INICIAL = "SELECT episodio_id, catalogo_inicial FROM {core}.episodio_programa"
Q_MALLA_T1 = "SELECT cod_programa, catalogo, codigo_asignatura, semestre, creditos FROM {core}.asignatura_malla"
Q_LATEST = """
SELECT max(periodo) FROM {core}.evento_estado
WHERE NOT es_correccion_sistema AND periodo ~ '^[0-9]{{4}}(10|20)$'
"""


def _read(conn, sql: str, schemas: Dict[str, str]) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql.format(**schemas))
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def cargar(conn, schemas: Dict[str, str]):
    ep = _read(conn, Q_EPISODIOS, schemas)
    ep["id_nivel"] = pd.to_numeric(ep["id_nivel"]).astype("Int64")
    es = _read(conn, Q_ESTADOS, schemas)
    es["episodio_id"] = es["episodio_id"].astype("Int64")
    it = _read(conn, Q_INTENTOS, schemas)
    for col in ("nota_numerica", "creditos", "creditos_reconocidos"):
        it[col] = pd.to_numeric(it[col]).astype("float64")
    it["periodo"] = it["periodo"].astype("category")
    it["resultado_tipo"] = it["resultado_tipo"].astype("category")
    via = _read(conn, Q_VIA, schemas)
    for col in ("puntaje_leng", "puntaje_mat", "puntaje_ciencias", "puntaje_historia", "puntaje_nem",
                "puntaje_ranking", "notas_em", "ponderado"):
        via[col] = pd.to_numeric(via[col]).astype("float64")
    tit = _read(conn, Q_TITULACION, schemas)
    tit["periodo"] = tit["fecha_titulacion"].map(periodo_de_fecha)
    tit = tit.loc[tit["periodo"].notna(), ["persona_key", "episodio_id", "periodo"]]
    ben = _read(conn, Q_BENEFICIOS, schemas)
    ben["benef_sem1"] = pd.to_numeric(ben["benef_sem1"]).astype("float64")
    with conn.cursor() as cur:
        cur.execute(Q_LATEST.format(**schemas))
        latest = cur.fetchone()[0]
    if latest is None:
        raise RuntimeError("no regular period in evento_estado: build neural_core first")
    return ep, es, it, via, tit, latest, ben


def cargar_nuevas(conn, schemas: Dict[str, str], ep: pd.DataFrame, es: pd.DataFrame, it: pd.DataFrame):
    """Adds ``oportunidad`` to the attempts, the state dates to the states and ``catalogo_inicial`` to the episodes; returns the malla."""
    it = it.merge(_read(conn, Q_OPORTUNIDAD, schemas), on="intento_id", how="left", validate="one_to_one")
    es = es.merge(_read(conn, Q_FECHAS, schemas), on=["persona_key", "orden_canonico"], how="left", validate="one_to_one")
    ep = ep.merge(_read(conn, Q_CATALOGO_INICIAL, schemas), on="episodio_id", how="left", validate="one_to_one")
    malla = _read(conn, Q_MALLA_T1, schemas)
    for col in ("semestre", "creditos"):
        malla[col] = pd.to_numeric(malla[col]).astype("float64")
    return ep, es, it, malla


def _py(value):
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (float, np.floating)):
        return None if math.isnan(value) else float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _copy(conn, table: str, columns: List[str], frame: pd.DataFrame) -> None:
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
            for row in frame[columns].itertuples(index=False, name=None):
                copy.write_row([_py(v) for v in row])


def preparar_tablas(snap: pd.DataFrame, sem: pd.DataFrame):
    s = snap.copy()
    s["continua"] = s["continua"].astype(object).where(s["continua"].notna(), None)
    s["continua_mismo_programa"] = s["continua_mismo_programa"].astype(object).where(
        s["continua_mismo_programa"].notna(), None)
    for col in ("episodio_id", "k", "cohorte_anio", "intentos_evaluados", "aprobados", "reprobados",
                "n_notas_promedio", "convalidaciones", "cursos_verano_invierno", "n_interrupcion",
                "cambios_catalogo", "semestres_matriculados", "intentos_ult_semestre", "ben_sin_dato",
                "perdida_sin_dato"):
        if col in s:
            s[col] = s[col].astype("int64")
    t = sem.rename(columns={"mat": "matriculado", "int": "interrupcion", "ie": "intentos_evaluados",
                            "ae": "aprobados", "re": "reprobados", "cv": "convalidaciones",
                            "cred": "creditos_aprobados", "vi": "cursos_verano_invierno",
                            "nn": "n_notas_promedio", "cred_ac": "creditos_acumulados"}).copy()
    t["promedio"] = t["sn"] / t["n_notas_promedio"].where(t["n_notas_promedio"] > 0)
    t["matriculado"] = t["matriculado"].astype(bool)
    t["interrupcion"] = t["interrupcion"].astype(bool)
    for col in ("episodio_id", "j", "intentos_evaluados", "aprobados", "reprobados", "convalidaciones",
                "cursos_verano_invierno", "n_notas_promedio"):
        t[col] = t[col].astype("int64")
    return s, t


def resumen_filas(snap: pd.DataFrame) -> pd.DataFrame:
    """Counts per k / split / sample status / label (no individual rows)."""
    g = snap.assign(label=snap["continua"].map({True: "continua", False: "no_continua"}).fillna("sin_etiqueta"))
    return g.groupby(["k", "split", "estado_muestra", "label"]).size().rename("n").reset_index()


def hash_snapshot(snap: pd.DataFrame, ks=R.KS) -> str:
    """Hash of the rows of the given ks (default: the OFFICIAL ks 1 and 2, so adding the k = 4 extension or new feature
    columns does not change the hash that identifies the official data)."""
    cols = ["episodio_id", "k", "estado_muestra", "continua", "creditos_aprobados", "intentos_evaluados"]
    sel = snap.loc[snap["k"].isin(list(ks))]
    h = pd.util.hash_pandas_object(sel[cols].astype(str), index=False).to_numpy()
    return hashlib.sha256(h.tobytes()).hexdigest()


def build(conn, core_schema="neural_core", mart_schema="neural_mart", meta_schema="neural_meta",
          out: Callable[[str], None] = print, stg_schema="neural_stg"):
    for schema in (core_schema, mart_schema, meta_schema, stg_schema):
        if schema not in ALLOWED_SCHEMAS:
            raise RuntimeError(f"schema {schema!r} is not one of {ALLOWED_SCHEMAS}")
    schemas = {"core": core_schema, "mart": mart_schema, "meta": meta_schema, "stg": stg_schema}
    t0 = time.monotonic()
    ep, es, it, via, tit, latest, ben = cargar(conn, schemas)
    out(f"cargado: {len(ep):,} episodios, {len(es):,} estados, {len(it):,} intentos, {len(via):,} vias, "
        f"{len(ben):,} filas de beneficios "
        f"({time.monotonic() - t0:.0f} s); periodo maximo regular {latest}")
    ep, es, it, malla = cargar_nuevas(conn, schemas, ep, es, it)
    snap, sem, embudo = F.construir_snapshot(ep, es, it, via, tit, latest, R.KS_TODOS, beneficios=ben, malla=malla)
    s, t = preparar_tablas(snap, sem)
    out(f"construido: {len(s):,} filas (episodio, k), {len(t):,} filas de semestre ({time.monotonic() - t0:.0f} s)")
    digest = hash_snapshot(snap)
    digest_ext = hash_snapshot(snap, R.KS_EXTENSION)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {mart_schema}.snapshot_t1, {mart_schema}.snapshot_t1_semestre, "
                        f"{mart_schema}.snapshot_t1_resumen")
        _copy(conn, f"{mart_schema}.snapshot_t1", SNAPSHOT_COLS, s)
        _copy(conn, f"{mart_schema}.snapshot_t1_semestre", SEMESTRE_COLS, t)
        with conn.cursor() as cur:
            rows = [("periodo_maximo", latest, "ultimo periodo regular con estados; horizontes >= este quedan censurados"),
                    ("hash_datos", digest, "sha256 de (episodio, k, estado, etiqueta, creditos, intentos) de los k oficiales 1 y 2"),
                    ("hash_datos_k4", digest_ext, "igual para la extension k = 4 (D91)")]
            for e in embudo:
                for key in ("poblacion", "sin_matricula_en_k", "salida_en_corte", "ya_egresado_o_titulado", "elegibles"):
                    rows.append((f"embudo_k{e['k']}_{key}", str(e[key]), None))
            cur.executemany(f"INSERT INTO {mart_schema}.snapshot_t1_resumen (clave, valor, nota) VALUES (%s, %s, %s)",
                            rows)
    res = resumen_filas(snap)
    out(res.to_string(index=False))
    out(f"hash de datos: {digest}")
    out(f"total: {time.monotonic() - t0:.0f} s (una transaccion)")
    return snap, embudo, res


def main(argv: Optional[List[str]] = None) -> int:
    argparse.ArgumentParser(description="Rebuild neural_mart.snapshot_t1 (task T1) from neural_core.").parse_args(argv)
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
