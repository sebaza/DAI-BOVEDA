"""Loading, feature sets and discrete-time expansion of the T3 snapshot (docs/10_benchmark_t3.md).

Feature sets (nested): ``adm`` = pre-entry profile + program facts known at enrollment; ``adm+agg`` = + academic
aggregates up to the cut. The preprocessing (medians, scaling, vocabularies) is fitted on TRAIN only
(``models.data.Preprocesador``). ``sexo_equidad`` and every label column are never features.

Time scale of the models: ``u = tiempo - k`` regular semesters after the cut, ``u = 1 .. JMAX - k``. A row is censored
at ``u`` when ``causa`` is 0; the person-period expansion has one row per at-risk semester with outcome 0 (survived),
1 (egress / titulation) or 2 (definitive exit).
"""
from __future__ import annotations

import io
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from models.data import MM_COLS, PCT_COLS, PRUEBA_COL, Preprocesador, construir_secuencias   # noqa: F401  (re-exported)
from pipelines.snapshots import features_t3 as F3

JMAX = 20                       # last slot modelled (events later than this are censored there)
SPLITS = ("train", "valid", "test", "posterior")
# The admission year is NOT a model input: the splits are by cohort, so a numeric year can only be extrapolated (a first
# run with it made the networks fail on the 2021-2022 control cohorts) and the egress timing changes between cohorts
# for reasons that no admission year can explain (P60). It stays in the snapshot for splits and subgroup tables.
# D47: ``trayectoria_plan_comun`` (admission fact) and ``especialidad_conocida_al_corte`` (a specialty state recorded at or
# before the cut) are point-in-time safe, so they are inputs; the program columns are those in force at the cut.
ADM_NUM = ["preferencia", "con_postulacion", *MM_COLS, "duracion_nominal", "creditos_malla_total", "malla_conocida",
           "trayectoria_plan_comun", "especialidad_conocida_al_corte"]
ADM_CAT = [*F3.FEATURE_COLS_CAT, PRUEBA_COL]          # stage B: scale-corrected scores + the admission test
# Academic features robust to P58 (201920 / 202010 have no failures recorded, and the test cohorts 2019-2020 have one of
# their first semesters in them): credits, rates and means computed over the recorded semesters only, plus enrollment and
# malla progress. The attempt COUNTS and the last-semester trio would look different for those cohorts only because of
# the missing failures, so they stay in the snapshot but out of the models (the GRU gets explicit missing indicators).
ACAD_ROBUSTAS = ["creditos_aprobados", "tasa_aprobacion", "promedio_evaluado", "convalidaciones", "cursos_verano_invierno",
                 "n_interrupcion", "cambios_catalogo", "semestres_matriculados", "creditos_esperados", "avance_malla",
                 "fraccion_malla"]
AGG_NUM = ADM_NUM + ACAD_ROBUSTAS
GRUPOS: Dict[str, Tuple[List[str], List[str]]] = {"adm": (ADM_NUM, ADM_CAT), "adm+agg": (AGG_NUM, ADM_CAT)}
PROHIBIDAS = {"sexo_equidad", "cohorte_anio", "sexo", "persona_key", "episodio_id", "split", "k", "periodo_admision",
              *F3.LABEL_COLS, "u", "y", "t_evento", "evento"}
BOOL_COLS = ["con_postulacion", "malla_conocida", "salida_a_otro_programa", "trayectoria_plan_comun",
             "especialidad_conocida_al_corte"]
TEXT_COLS = ["persona_key", "cod_programa", "periodo_admision", "split", "salida_tipo", "via_clase", "cod_admision",
             "sede", "tipo_colegio", "depend_colegio", "region_colegio", "sexo_equidad", PRUEBA_COL]


def verificar_sin_fuga(num: Sequence[str], cat: Sequence[str]) -> None:
    mal = PROHIBIDAS & (set(num) | set(cat))
    if mal:
        raise ValueError(f"forbidden model features: {sorted(mal)}")


def cargar(conn, mart_schema: str = "neural_mart") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """``snapshot_t3`` and ``snapshot_t3_semestre`` (typed copies; read only)."""
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

    snap = leer("snapshot_t3")
    for c in BOOL_COLS:
        if c in snap:
            snap[c] = snap[c].astype("boolean")
    for c in TEXT_COLS:
        if c in snap:
            snap[c] = snap[c].astype(object).where(snap[c].notna(), None)
    sem = leer("snapshot_t3_semestre")
    for c in ("matriculado", "interrupcion"):
        sem[c] = sem[c].astype(bool)
    return snap, sem


def seleccionar(snap: pd.DataFrame, k: int, splits: Sequence[str] = SPLITS) -> pd.DataFrame:
    """Rows of cut ``k`` of the requested splits, with the model time ``u`` (semesters after the cut)."""
    d = snap.loc[(snap["k"] == k) & snap["split"].isin(splits)].copy()
    d["u"] = (d["tiempo"] - k).astype("int64")
    d["causa"] = d["causa"].astype("int64")
    return d.reset_index(drop=True)


def particion(snap: pd.DataFrame, k: int) -> Dict[str, pd.DataFrame]:
    d = seleccionar(snap, k)
    return {s: d.loc[d["split"] == s].reset_index(drop=True) for s in SPLITS}


# ---------------------------------------------------------------------------------------------
# sequences (P58-robust channels)
# ---------------------------------------------------------------------------------------------
SEQ_COLS_T3 = ["matriculado", "interrupcion", "creditos_aprobados", "creditos_acumulados", "convalidaciones",
               "cursos_verano_invierno"]


def construir_secuencias_t3(snap: pd.DataFrame, semestres: pd.DataFrame, k: int) -> np.ndarray:
    """Array ``(n, k, len(SEQ_COLS_T3))``: the vectors of slots ``1..k`` of each row's episode, in order.

    Fixed, domain-based scaling (nothing is fitted). Only channels that P58 leaves intact: enrollment, interruption and
    the credits approved (an approval is always recorded; the failures of 201920 / 202010 are not). Attempt counts, pass
    rates and grades are not sequence inputs: a semester without recorded failures would look like an inactive one.
    """
    sem = semestres.loc[semestres["j"] <= k].sort_values(["episodio_id", "j"])
    cols = [sem["matriculado"].astype(float), sem["interrupcion"].astype(float),
            sem["creditos_aprobados"].astype(float) / 30.0, sem["creditos_acumulados"].astype(float) / 60.0,
            sem["convalidaciones"] / 10.0, sem["cursos_verano_invierno"] / 5.0]
    x = np.stack([c.to_numpy("float32") for c in cols], axis=1)
    idx = pd.MultiIndex.from_arrays([sem["episodio_id"].to_numpy(), sem["j"].to_numpy()])
    out = np.zeros((len(snap), k, x.shape[1]), "float32")
    eid = snap["episodio_id"].to_numpy()
    for j in range(1, k + 1):
        pos = idx.get_indexer(pd.MultiIndex.from_arrays([eid, np.full(len(eid), j)]))
        if (pos < 0).any():
            raise ValueError("missing semester rows for some episodes")
        out[:, j - 1] = x[pos]
    return out


# ---------------------------------------------------------------------------------------------
# discrete time
# ---------------------------------------------------------------------------------------------
def expandir_persona_periodo(df: pd.DataFrame, k: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Person-period expansion: ``(fila, j, y)``.

    ``fila`` indexes ``df``; ``j`` is the absolute slot of the at-risk semester (``k+1 .. tiempo``); ``y`` is 0 while the
    episode survives the semester and ``causa`` in the last one (0 when censored there).
    """
    n_per = (df["tiempo"].to_numpy("int64") - k)
    if (n_per < 1).any():
        raise ValueError("every row must be at risk for at least one semester after the cut")
    fila = np.repeat(np.arange(len(df)), n_per)
    inicio = np.repeat(np.cumsum(n_per) - n_per, n_per)
    j = k + 1 + (np.arange(len(fila)) - inicio)
    y = np.zeros(len(fila), dtype="int64")
    ultimo = np.cumsum(n_per) - 1
    y[ultimo] = df["causa"].to_numpy("int64")
    return fila, j.astype("int64"), y


def cif_desde_riesgos(h1: np.ndarray, h2: np.ndarray) -> Dict[str, np.ndarray]:
    """Cumulative incidences from discrete cause-specific hazards ``(n, U)``: ``F_c(u) = sum_{s<=u} S(s-1) h_c(s)``."""
    h1, h2 = np.clip(h1, 0.0, 1.0), np.clip(h2, 0.0, 1.0)
    tot = np.minimum(h1 + h2, 1.0)
    s_ant = np.cumprod(np.concatenate([np.ones((len(h1), 1)), 1.0 - tot[:, :-1]], axis=1), axis=1)
    return {"F1": np.cumsum(s_ant * h1, axis=1), "F2": np.cumsum(s_ant * h2, axis=1),
            "S": np.cumprod(1.0 - tot, axis=1)}


def columnas_tiempo(j: np.ndarray, duracion: np.ndarray) -> pd.DataFrame:
    """Time covariates of a person-period row: absolute slot and distance to the nominal duration of the program."""
    return pd.DataFrame({"slot": j.astype("float64"), "slot_rel_nominal": j.astype("float64") - duracion})
