"""Loading, feature sets and targets of the T4/T5 snapshot (docs/11_benchmark_t4_t5.md).

Same feature sets as T3 (``models.t3_data``): ``adm`` = pre-entry profile + program facts in force at the cut;
``adm+agg`` = + the academic aggregates up to the cut that are robust to P58. Preprocessing is fitted on TRAIN only
(``models.data.Preprocesador``). ``sexo_equidad``, ``cohorte_anio`` and every label column are never features.

Targets of one row (the outcome is mutually exclusive): ``y4`` = ``transicion`` (T4), ``y5`` = ``eliminacion`` (T5),
``yc`` = index of the outcome in ``CLASES`` (multiclass view). Only rows with an observed, unambiguous outcome and a
train / valid / test split are used (``seleccionar``).
"""
from __future__ import annotations

import io
from typing import Dict, Sequence, Tuple

import numpy as np
import pandas as pd

from models import t3_data as TD
from models.data import Preprocesador, construir_secuencias   # noqa: F401  (re-exported)
from pipelines.snapshots import features_t45 as F45
from pipelines.snapshots import rules_t45 as R45

CLASES = R45.CLASES                                   # continua, egreso, transicion, eliminacion, otra_salida
SPLITS = ("train", "valid", "test")
GRUPOS: Dict[str, Tuple[list, list]] = TD.GRUPOS
PROHIBIDAS = {*TD.PROHIBIDAS, "resultado", "otra_salida_tipo", "hubo_transicion_en_horizonte",
              "hubo_eliminacion_en_horizonte", "eliminacion_con_reintegro", "eliminacion_efectiva", "horizonte_e_dudoso",
              "y4", "y5", "y5e", "yc"}
BOOL_COLS = ["con_postulacion", "malla_conocida", "trayectoria_plan_comun", "especialidad_conocida_al_corte",
             "hubo_transicion_en_horizonte", "hubo_eliminacion_en_horizonte", "eliminacion_con_reintegro",
             "eliminacion_efectiva", "horizonte_e_dudoso"]
TEXT_COLS = ["persona_key", "cod_programa", "periodo_admision", "split", "resultado", "otra_salida_tipo", "via_clase",
             "cod_admision", "sede", "tipo_colegio", "depend_colegio", "region_colegio", "sexo_equidad", TD.PRUEBA_COL]
# T5E (stage B): the elimination WITHOUT reintegro (P72 / P88, reintegro = state I); same population and models as T5
TARGETS = {"T4": ("y4", "transicion"), "T5": ("y5", "eliminacion"), "T5E": ("y5e", "eliminacion_efectiva")}


def verificar_sin_fuga(num: Sequence[str], cat: Sequence[str]) -> None:
    mal = PROHIBIDAS & (set(num) | set(cat))
    if mal:
        raise ValueError(f"forbidden model features: {sorted(mal)}")


def cargar(conn, mart_schema: str = "neural_mart") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """``snapshot_t45`` and ``snapshot_t45_semestre`` (typed copies; read only)."""
    def leer(tabla: str) -> pd.DataFrame:
        buf = io.BytesIO()
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {mart_schema}.{tabla} LIMIT 0")
            cols = [d.name for d in cur.description]
        with conn.cursor() as cur:
            with cur.copy(f"COPY (SELECT * FROM {mart_schema}.{tabla} ORDER BY 1, 2) TO STDOUT WITH (FORMAT CSV)") as cp:
                for chunk in cp:
                    buf.write(bytes(chunk))
        buf.seek(0)
        return pd.read_csv(buf, header=None, names=cols, dtype={c: "string" for c in TEXT_COLS},
                           true_values=["t"], false_values=["f"], keep_default_na=False, na_values=[""])

    snap = leer("snapshot_t45")
    for c in BOOL_COLS:
        snap[c] = snap[c].astype("boolean")
    for c in TEXT_COLS:
        if c in snap:
            snap[c] = snap[c].astype(object).where(snap[c].notna(), None)
    sem = leer("snapshot_t45_semestre")
    for c in ("matriculado", "interrupcion"):
        sem[c] = sem[c].astype(bool)
    return snap, sem


def seleccionar(snap: pd.DataFrame, k: int) -> pd.DataFrame:
    """Rows of cut ``k`` usable for training and evaluation, with the targets ``y4``, ``y5`` and ``yc``."""
    m = (snap["k"] == k) & snap["split"].isin(SPLITS) & snap["resultado"].isin(CLASES)
    d = snap.loc[m].copy()
    d["y4"] = (d["resultado"] == "transicion").astype("int8")
    d["y5"] = (d["resultado"] == "eliminacion").astype("int8")
    d["y5e"] = ((d["resultado"] == "eliminacion") & d["eliminacion_efectiva"].astype(bool)).astype("int8")
    d["yc"] = d["resultado"].map({c: i for i, c in enumerate(CLASES)}).astype("int64")
    return d.reset_index(drop=True)


def particion(snap: pd.DataFrame, k: int) -> Dict[str, pd.DataFrame]:
    d = seleccionar(snap, k)
    return {s: d.loc[d["split"] == s].reset_index(drop=True) for s in SPLITS}


def construir_secuencias_t45(snap: pd.DataFrame, semestres: pd.DataFrame, k: int) -> np.ndarray:
    """The T3 sequence channels (P58-robust) of the slots ``1..k`` of each row's trajectory."""
    return TD.construir_secuencias_t3(snap, semestres, k)
