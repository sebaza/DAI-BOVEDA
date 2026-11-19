"""Loading and feature sets of the T2 snapshot (docs/09_benchmark_t2.md).

Feature sets (each one adds a block to the previous one):
  a  student + load of the period          b  + course statistics (expanding, strictly past)
  c  + explicit prerequisite graph         d  + teacher / section history (ablation, 2016+)
  c_id = c + the course identity as a categorical (control for the GNN embeddings)
The preprocessing (medians, scaling, vocabularies) is fitted on TRAIN only (``models.data.Preprocesador``).
``sexo_equidad`` is never a feature; ``docente_key`` is not even stored in the snapshot.
"""
from __future__ import annotations

import io
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from pipelines.snapshots import features as F
from pipelines.snapshots import features_t2 as F2

SPLITS = ("train", "valid", "test", "posterior")
BOOL_COLS = ["aprobo_antes_curso", "con_postulacion", "en_malla", "malla_conocida", "info_prereq", "tiene_docente"]
TEXT_COLS = ["persona_key", "periodo", "cod_programa", "catalogo", "codigo_asignatura", "split", "via_clase",
             "cod_admision", "sede", "tipo_colegio", "depend_colegio", "region_colegio", "formacion", "depto",
             "sexo_equidad", "prueba_admision", "banda_nota"]

# Stage B (D81): scale-corrected min-max scores (P47) and the admission test replace the rank percentiles ``pct_*``.
A_NUM = ([c for c in F2.FEATURE_COLS_ESTUDIANTE if c not in F.SCORE_COLS] + list(F.MM_COLS) + F2.FEATURE_COLS_CARGA)
A_CAT = F2.FEATURE_COLS_CAT_ESTUDIANTE + [F.PRUEBA_COL]
B_NUM = A_NUM + F2.FEATURE_COLS_CURSO
B_CAT = A_CAT + F2.FEATURE_COLS_CAT_CURSO
C_NUM = B_NUM + F2.FEATURE_COLS_PRERREQ
D_NUM = C_NUM + F2.FEATURE_COLS_DOCENTE
C_NUEVAS_NUM = C_NUM + F2.FEATURE_COLS_NUEVAS_T2           # P117-P127: department record + previous regular semester
CONJUNTOS: Dict[str, Tuple[List[str], List[str]]] = {
    "a": (A_NUM, A_CAT),
    "b": (B_NUM, B_CAT),
    "c": (C_NUM, B_CAT),
    "d": (D_NUM, B_CAT),
    "c_id": (C_NUM, B_CAT + ["codigo_asignatura"]),
    "c_nuevas": (C_NUEVAS_NUM, B_CAT),
}
PRIOR_OUTCOME = {"y", "banda_nota", "split", "sexo_equidad", "persona_key", "intento_id", "episodio_id", "nota"}


def verificar_sin_fuga(num: List[str], cat: List[str]) -> None:
    mal = PRIOR_OUTCOME & (set(num) | set(cat))
    if mal:
        raise ValueError(f"forbidden model features: {sorted(mal)}")


def cargar(conn, mart_schema: str = "neural_mart") -> pd.DataFrame:
    """Whole ``snapshot_t2`` through COPY ... CSV (compact dtypes, no Python tuples)."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {mart_schema}.snapshot_t2 LIMIT 0")
        cols = [d.name for d in cur.description]
    buf = io.BytesIO()
    with conn.cursor() as cur:
        with cur.copy(f"COPY (SELECT * FROM {mart_schema}.snapshot_t2 ORDER BY intento_id) TO STDOUT WITH (FORMAT CSV)") as cp:
            for chunk in cp:
                buf.write(bytes(chunk))
    buf.seek(0)
    dtypes = {c: "string" for c in TEXT_COLS}
    for c in BOOL_COLS:
        dtypes[c] = "string"
    df = pd.read_csv(buf, header=None, names=cols, dtype=dtypes, na_values=[""], keep_default_na=False,
                     low_memory=False)
    for c in BOOL_COLS:
        df[c] = df[c].map({"t": 1.0, "f": 0.0}).astype("float32")
    for c in df.columns:
        if c in TEXT_COLS:
            df[c] = df[c].astype("category") if c != "persona_key" else df[c].astype(object)
        elif c not in ("intento_id", "episodio_id"):
            df[c] = df[c].astype("float32")
    return df


def particion(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    return {s: df[df["split"] == s].reset_index(drop=True) for s in SPLITS}


class PreprocesadorT2:
    """Median imputation + missing indicators + standardization + category vocabularies, fitted on train only."""

    def __init__(self, num_cols, cat_cols, min_count: int = 30):
        verificar_sin_fuga(list(num_cols), list(cat_cols))
        self.num_cols, self.cat_cols, self.min_count = list(num_cols), list(cat_cols), min_count

    def fit(self, train: pd.DataFrame) -> "PreprocesadorT2":
        num = train[self.num_cols].astype("float32")
        self.medianas = num.median().fillna(0.0)
        self.con_indicador = [c for c in self.num_cols if num[c].isna().any()]
        filled = num.fillna(self.medianas)
        self.medias = filled.mean()
        self.desvios = filled.std(ddof=0).replace(0.0, 1.0).fillna(1.0)
        self.vocab: Dict[str, List[str]] = {}
        for c in self.cat_cols:
            vc = train[c].astype(object).where(train[c].notna(), "sin_dato").astype(str).value_counts()
            self.vocab[c] = sorted(vc.index[vc >= self.min_count])
        return self

    def transform_num(self, df: pd.DataFrame) -> np.ndarray:
        num = df[self.num_cols].astype("float32")
        ind = (num[self.con_indicador].isna().to_numpy("float32") if self.con_indicador
               else np.zeros((len(df), 0), "float32"))
        z = ((num.fillna(self.medianas) - self.medias) / self.desvios).to_numpy("float32")
        return np.hstack([z, ind]).astype("float32")

    def nombres_num(self) -> List[str]:
        return self.num_cols + [f"{c}__na" for c in self.con_indicador]

    def transform_cat_codes(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for c in self.cat_cols:
            index = {v: i + 1 for i, v in enumerate(self.vocab[c])}
            s = df[c].astype(object).where(df[c].notna(), "sin_dato").astype(str)
            cols.append(s.map(index).fillna(0).astype("int64").to_numpy())
        return np.stack(cols, axis=1) if cols else np.zeros((len(df), 0), "int64")

    def cardinalidades(self) -> List[int]:
        return [len(self.vocab[c]) + 1 for c in self.cat_cols]

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Dense matrix for linear models: numeric block + one-hot of the vocabularies."""
        codes = self.transform_cat_codes(df)
        cards = self.cardinalidades()
        out = np.zeros((len(df), len(self.nombres_num()) + sum(cards)), "float32")
        out[:, :len(self.nombres_num())] = self.transform_num(df)
        off = len(self.nombres_num())
        for i, card in enumerate(cards):
            out[np.arange(len(df)), off + codes[:, i]] = 1.0
            off += card
        return out

    def transform_catboost(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df[self.num_cols].astype("float32").copy()
        for c in self.cat_cols:
            out[c] = df[c].astype(object).where(df[c].notna(), "sin_dato").astype(str)
        return out
