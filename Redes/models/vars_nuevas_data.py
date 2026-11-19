"""Loading and column blocks of the new variables of T3-T6 (side tables of migration 031).

The official snapshots are never changed: the new columns are merged by key onto ``snapshot_t3`` / ``snapshot_t45`` (episode
and ``k``) and ``snapshot_t6`` (episode), and a feature set is the kept one plus a block. Blocks are pre-specified here (not
chosen on the data); ``columnas_validas`` only drops the columns that are entirely missing in the TRAIN rows of a cut (for
``k = 0`` the attempt-based columns do not exist). Preprocessing (median, scaling, missing indicators) stays the fitted-on-train
``models.data.Preprocesador``. ``sexo``, ``cohorte_anio`` and every label stay forbidden.
"""
from __future__ import annotations

import io
from typing import Dict, List, Sequence, Tuple

import pandas as pd

from pipelines.snapshots import features_variables as FV

BLOQUES: Dict[str, List[str]] = {
    # T3: remaining credits and speed (P126 corrected totals), reach rule (P121), Capstone / practice (P125)
    "cred": ["creditos_malla_total_corr", "malla_creditos_confiable", "creditos_restantes", "velocidad_aprobacion",
             "velocidad_relativa"],
    "alc": list(FV.VARS_ALCANCE),
    "tit": ["cap_inscrito", "cap_aprobado", "prac_inscrita", "prac_aprobada", "malla_tiene_capstone", "malla_tiene_practica"],
    # T5: regulatory risk under the regulation in force (P117 / P118)
    "reg": list(FV.VARS_REGLAMENTO),
    # T4: own versus general formation and earlier program changes
    "t4": list(FV.VARS_T4),
}
BLOQUES["t3"] = [*BLOQUES["cred"], *BLOQUES["alc"], *BLOQUES["tit"]]
BLOQUES["reg_alc"] = [*BLOQUES["reg"], *BLOQUES["alc"]]
BLOQUES["todo"] = list(FV.VARIABLES_NUEVAS)
# T6 (one row per graduate): the program area is a categorical column, the rest are numeric
T6_NUM = ["ranking_prom_egreso", "nota_titulo", "nota_practica"]
T6_BLOQUES: Dict[str, Tuple[List[str], List[str]]] = {
    "area": ([], ["area_conocimiento"]),
    "ranking": (["ranking_prom_egreso"], []),
    "titulo": (["nota_titulo", "nota_practica"], []),
    "todo": (T6_NUM, ["area_conocimiento"]),
}
PROHIBIDAS_NUEVAS = {"sexo", "sexo_equidad", "cohorte_anio", "anio_egreso", "persona_key", "episodio_id", "split", "k"}


def _leer(conn, sql: str) -> pd.DataFrame:
    buf = io.BytesIO()
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM ({sql}) q LIMIT 0")
        cols = [d.name for d in cur.description]
    with conn.cursor() as cur:
        with cur.copy(f"COPY ({sql}) TO STDOUT WITH (FORMAT CSV)") as cp:
            for chunk in cp:
                buf.write(bytes(chunk))
    buf.seek(0)
    return pd.read_csv(buf, header=None, names=cols, true_values=["t"], false_values=["f"], keep_default_na=False, na_values=[""])


def cargar_nuevas(conn, mart_schema: str = "neural_mart", core_schema: str = "neural_core") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """``(variables T3/T4/T5, variables T6 with the program area)`` (read only)."""
    v3 = _leer(conn, f"SELECT * FROM {mart_schema}.snapshot_variables_nuevas ORDER BY 1, 2")
    for c in FV.VARS_BOOL:
        v3[c] = v3[c].astype(bool)
    v6 = _leer(conn, f"SELECT v.*, p.area_conocimiento::text AS area_conocimiento FROM {mart_schema}.snapshot_variables_nuevas_t6 v "
                     f"LEFT JOIN (SELECT s.episodio_id, pr.area_conocimiento FROM {mart_schema}.snapshot_t6 s "
                     f"JOIN {core_schema}.programa pr ON pr.cod_programa = s.cod_programa) p USING (episodio_id) ORDER BY 1")
    v6["area_conocimiento"] = v6["area_conocimiento"].astype(object).where(v6["area_conocimiento"].notna(), None)
    return v3, v6


def unir(snap: pd.DataFrame, v3: pd.DataFrame) -> pd.DataFrame:
    """Left merge of the new variables onto a T3 / T4 / T5 snapshot by ``(episodio_id, k)``; the rows and their order are kept
    and the boolean columns become 0 / 1 floats (a model input is numeric)."""
    antes = len(snap)
    out = snap.merge(v3, on=["episodio_id", "k"], how="left", validate="one_to_one")
    if len(out) != antes:
        raise ValueError("the merge of the new variables changed the number of rows")
    for c in FV.VARS_BOOL:
        out[c] = out[c].astype("float64")
    return out


def columnas_validas(train: pd.DataFrame, cols: Sequence[str]) -> List[str]:
    """Columns of a block with at least one value in the training rows (the others are constant NaN at that cut)."""
    return [c for c in cols if c in train.columns and train[c].notna().any()]


def verificar_sin_fuga_nuevas(cols: Sequence[str]) -> None:
    mal = PROHIBIDAS_NUEVAS & set(cols)
    if mal:
        raise ValueError(f"forbidden model features: {sorted(mal)}")
