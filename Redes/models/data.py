"""Loading, selection and train-only preprocessing of the T1 snapshot (docs/08_benchmark_t1.md).

* ``seleccionar_modelado`` is the single gate that keeps censored / uncovered / post-2023 rows out of
  training and evaluation.
* ``Preprocesador`` learns medians, means, standard deviations and category vocabularies from the TRAIN rows
  only; validation and test are only transformed.
* ``sexo_equidad`` is never a feature (decision M1): it travels in the frame for the fairness tables.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PCT_COLS = ["pct_leng", "pct_mat", "pct_ciencias", "pct_historia", "pct_nem", "pct_ranking", "pct_notas_em",
            "pct_ponderado"]
# Stage B (D81): the admission scores are the min-max columns by test, year and field (P47) plus the test itself. The
# percentile columns rank raw values that mix scales (``ponderado`` arrives as 557 / 5570 / 55700 within one process) and
# do not tell the tests apart, so they stay in the snapshots for audit but are no longer features in any task.
MM_COLS = ["mm_leng", "mm_mat", "mm_ciencias", "mm_historia", "mm_nem", "mm_ranking", "mm_notas_em", "mm_ponderado"]
PRUEBA_COL = "prueba_admision"
PRE_CAT = ["cod_programa", "via_clase", "cod_admision", "sede", "tipo_colegio", "depend_colegio", "region_colegio", PRUEBA_COL]
PRE_NUM = ["cohorte_anio", "preferencia", "con_postulacion", *MM_COLS]
ACAD_NUM = ["creditos_aprobados", "intentos_evaluados", "aprobados", "reprobados", "tasa_aprobacion",
            "promedio_evaluado", "n_notas_promedio", "convalidaciones", "cursos_verano_invierno", "n_interrupcion",
            "cambios_catalogo", "semestres_matriculados", "intentos_ult_semestre", "tasa_ult_semestre",
            "promedio_ult_semestre"]
# Benefits (D90-D95): the second-semester amount and the total are zeroed after the year closes for part of the students, so
# they reveal leaving; they are refused here as well as left out of the snapshot.
FORBIDDEN = {"sexo_equidad", "sexo", "continua", "continua_mismo_programa", "no_continua_tipo", "persona_key",
             "episodio_id", "periodo_horizonte", "split", "estado_muestra",
             "benef_sem2", "total", "monto_sem2", "monto_total"}
SPLITS = ("train", "valid", "test")
SEQ_COLS = ["matriculado", "interrupcion", "intentos_evaluados", "aprobados", "reprobados", "convalidaciones",
            "creditos_aprobados", "cursos_verano_invierno", "tasa", "tiene_tasa", "promedio", "tiene_promedio",
            "creditos_acumulados"]

GRUPOS = {
    "pre_entry": (PRE_NUM, PRE_CAT),
    "pre_entry+academico": (PRE_NUM + ACAD_NUM, PRE_CAT),
}

# Benefit ablation (16-11-2026): a separate dictionary so the official ladder (``GRUPOS``) never changes.
BEN_NUM = ["ben_sin_dato", "tiene_gratuidad", "tiene_credito", "tiene_beca_estatal", "tiene_beca_ucn", "merito_ingreso",
           "merito_e1", "expiro_gratuidad", "etapa_capstone", "n_beneficios", "monto_sem1"]
BEN_CAT = ["banda_decil"]
PERDIDA_NUM = ["perdida_sin_dato", "perdio_gratuidad", "perdio_credito", "perdio_cualquier_beneficio", "obtuvo_gratuidad"]
GRUPOS_BENEFICIOS = {
    "pre_entry+academico+beneficios": (PRE_NUM + ACAD_NUM + BEN_NUM, PRE_CAT + BEN_CAT),
    "pre_entry+academico+beneficios+perdidas": (PRE_NUM + ACAD_NUM + BEN_NUM + PERDIDA_NUM, PRE_CAT + BEN_CAT),
}


# New variables of 18-11-2026 (P117-P127, ``pipelines/snapshots/features_t1_nuevas.py``): a separate dictionary so the official ladder
# (``GRUPOS``) never changes. One group per block (diagnostic) and one with every block (the candidate of D114).
NUEVAS_BLOQUES_T1 = {
    "rendimiento": ["creditos_aprob_ult_sem", "delta_promedio_sem", "delta_promedio_acum"],
    "oportunidades": ["repro_oport2", "repro_oport3", "ramos_repetidos", "n_sem_sin_reprob"],
    "malla": ["creditos_esperados", "avance_malla", "fraccion_malla"],
    "carga": ["ramos_ins_ult", "delta_ramos_ins", "creditos_ins_ult", "delta_creditos_ins"],
    "retiros": ["n_retiro_temporal", "n_anulacion", "sem_desde_ultimo_retiro", "dias_desde_ultimo_retiro"],
}
NUEVAS_NUM = [c for cols in NUEVAS_BLOQUES_T1.values() for c in cols]
GRUPOS_NUEVAS = {"pre_entry+academico+nuevas": (PRE_NUM + ACAD_NUM + NUEVAS_NUM, PRE_CAT),
                 **{f"pre_entry+academico+{b}": (PRE_NUM + ACAD_NUM + cols, PRE_CAT) for b, cols in NUEVAS_BLOQUES_T1.items()}}


def seleccionar_modelado(df: pd.DataFrame, k: Optional[int] = None, train_desde: Optional[int] = None) -> pd.DataFrame:
    """Rows usable for training / evaluation: observed label, split in train/valid/test.

    ``train_desde`` (sensitivity analysis) drops train rows of earlier cohorts; valid/test never change.
    """
    m = (df["estado_muestra"] == "observada") & df["split"].isin(SPLITS) & df["continua"].notna()
    if k is not None:
        m &= df["k"] == k
    if train_desde is not None:
        m &= ~((df["split"] == "train") & (df["cohorte_anio"] < train_desde))
    out = df.loc[m].copy()
    out["y"] = (~out["continua"].astype(bool)).astype("int8")      # event of interest: no_continua
    return out.reset_index(drop=True)


def assert_sin_fuga(columns: Sequence[str]) -> None:
    bad = FORBIDDEN & set(columns)
    if bad:
        raise ValueError(f"forbidden model features: {sorted(bad)}")


class Preprocesador:
    """Median imputation + missing indicators + standardization + category vocabularies, fitted on train only."""

    def __init__(self, num_cols: Sequence[str], cat_cols: Sequence[str], min_count: int = 30):
        assert_sin_fuga(list(num_cols) + list(cat_cols))
        self.num_cols, self.cat_cols, self.min_count = list(num_cols), list(cat_cols), min_count
        self.fitted = False

    def fit(self, train: pd.DataFrame) -> "Preprocesador":
        num = train[self.num_cols].astype("float64")
        self.medianas = num.median().fillna(0.0)
        self.con_indicador = [c for c in self.num_cols if num[c].isna().any()]
        filled = num.fillna(self.medianas)
        self.medias = filled.mean()
        self.desvios = filled.std(ddof=0).replace(0.0, 1.0).fillna(1.0)
        self.vocab: Dict[str, List[str]] = {}
        for c in self.cat_cols:
            vc = train[c].fillna("sin_dato").astype(str).value_counts()
            self.vocab[c] = sorted(vc.index[vc >= self.min_count])
        self.fitted = True
        return self

    # numeric block: standardized values then missing indicators
    def transform_num(self, df: pd.DataFrame) -> np.ndarray:
        num = df[self.num_cols].astype("float64")
        ind = num[self.con_indicador].isna().astype("float32").to_numpy() if self.con_indicador else np.zeros((len(df), 0), "float32")
        z = ((num.fillna(self.medianas) - self.medias) / self.desvios).to_numpy("float32")
        return np.hstack([z, ind]).astype("float32")

    def nombres_num(self) -> List[str]:
        return self.num_cols + [f"{c}__na" for c in self.con_indicador]

    # categorical codes: 0 = rare / unseen / missing
    def transform_cat_codes(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for c in self.cat_cols:
            index = {v: i + 1 for i, v in enumerate(self.vocab[c])}
            cols.append(df[c].fillna("sin_dato").astype(str).map(index).fillna(0).astype("int64").to_numpy())
        return np.stack(cols, axis=1) if cols else np.zeros((len(df), 0), "int64")

    def cardinalidades(self) -> List[int]:
        return [len(self.vocab[c]) + 1 for c in self.cat_cols]

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Dense matrix for linear models: numeric block + one-hot of the vocabularies."""
        parts = [self.transform_num(df)]
        codes = self.transform_cat_codes(df)
        for i, card in enumerate(self.cardinalidades()):
            oh = np.zeros((len(df), card), "float32")
            oh[np.arange(len(df)), codes[:, i]] = 1.0
            parts.append(oh)
        return np.hstack(parts)

    def transform_catboost(self, df: pd.DataFrame) -> pd.DataFrame:
        """Raw numerics (NaN kept, CatBoost handles them) and string categories."""
        out = df[self.num_cols].astype("float64").copy()
        for c in self.cat_cols:
            out[c] = df[c].fillna("sin_dato").astype(str)
        return out


# ---------------------------------------------------------------------------------------------
# sequences
# ---------------------------------------------------------------------------------------------
def _escala_secuencia(sem: pd.DataFrame) -> np.ndarray:
    """Fixed, domain-based scaling of the per-semester vector (no fitting, so nothing can leak)."""
    ie = sem["intentos_evaluados"].astype("float64")
    tasa = (sem["aprobados"] / ie.where(ie > 0)).fillna(0.0)
    prom = sem["promedio"].astype("float64")
    cols = [
        sem["matriculado"].astype(float), sem["interrupcion"].astype(float),
        ie / 10.0, sem["aprobados"] / 10.0, sem["reprobados"] / 10.0, sem["convalidaciones"] / 10.0,
        sem["creditos_aprobados"].astype(float) / 30.0, sem["cursos_verano_invierno"] / 5.0,
        tasa, (ie > 0).astype(float), ((prom - 4.0) / 1.5).fillna(0.0), prom.notna().astype(float),
        sem["creditos_acumulados"].astype(float) / 60.0,
    ]
    return np.stack([c.to_numpy("float32") for c in cols], axis=1)


def construir_secuencias(snap: pd.DataFrame, semestres: pd.DataFrame, k: int) -> np.ndarray:
    """Array ``(n, k, len(SEQ_COLS))``: the vectors of slots ``1..k`` of each row's episode, in order.

    ``semestres`` holds one row per (episode, slot); only slots ``<= k`` are read, so nothing later than the
    cutoff can enter.
    """
    sem = semestres.loc[semestres["j"] <= k].sort_values(["episodio_id", "j"])
    x = _escala_secuencia(sem)
    pos = {(e, j): i for i, (e, j) in enumerate(zip(sem["episodio_id"].to_numpy(), sem["j"].to_numpy()))}
    out = np.zeros((len(snap), k, x.shape[1]), "float32")
    for r, e in enumerate(snap["episodio_id"].to_numpy()):
        for j in range(1, k + 1):
            out[r, j - 1] = x[pos[(e, j)]]
    return out


# ---------------------------------------------------------------------------------------------
# database access (localhost dev DB, read only)
# ---------------------------------------------------------------------------------------------
def cargar_desde_db(conn, mart_schema: str = "neural_mart") -> Tuple[pd.DataFrame, pd.DataFrame]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {mart_schema}.snapshot_t1")
        snap = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        cur.execute(f"SELECT * FROM {mart_schema}.snapshot_t1_semestre")
        sem = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    for c in snap.columns:
        if snap[c].dtype == object and c not in ("continua", "continua_mismo_programa") and snap[c].map(
                lambda v: v is None or isinstance(v, (int, float)) or hasattr(v, "as_tuple")).all():
            snap[c] = pd.to_numeric(snap[c], errors="coerce")
    for c in ("continua", "continua_mismo_programa"):
        snap[c] = snap[c].astype("boolean")
    for c in ("creditos_aprobados", "promedio", "creditos_acumulados"):
        if c in sem:
            sem[c] = pd.to_numeric(sem[c]).astype("float64")
    sem["promedio"] = pd.to_numeric(sem["promedio"]).astype("float64")
    return snap, sem
