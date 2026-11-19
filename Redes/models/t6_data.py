"""Loading and feature sets of the T6 snapshot (docs/12_benchmark_t6.md).

Feature sets (nested): ``perfil`` = pre-entry profile + program facts in force at the cut + the faculty of the program
(a static attribute of the program); ``perfil+academico`` = + the academic record up to the egreso robust to P58, the time
to egreso against the nominal duration and whether a titulacion ``U`` is known by the cut. Preprocessing is fitted on TRAIN
only (``models.data.Preprocesador``). ``sexo_equidad``, ``cohorte_anio``, the year of egreso and every label column are never
features. The program itself enters through the historical baseline, not as a one-hot of ~100 levels with 50 events.
"""
from __future__ import annotations

from typing import Dict, Sequence, Tuple

import pandas as pd

from models import t3_data as TD3
from pipelines.snapshots import features_t6 as F6
from pipelines.snapshots import rules_t6 as R6

SPLITS = R6.SPLITS
PERFIL_NUM = list(TD3.ADM_NUM)
ACAD_NUM = [*TD3.ACAD_ROBUSTAS, *F6.NUEVAS]
CAT = ["via_clase", "sede", "facultad", TD3.PRUEBA_COL]
GRUPOS: Dict[str, Tuple[list, list]] = {"perfil": (PERFIL_NUM, CAT), "perfil+academico": (PERFIL_NUM + ACAD_NUM, CAT)}
PROHIBIDAS = {"sexo_equidad", "sexo", "cohorte_anio", "anio_egreso", "persona_key", "episodio_id", "split", "periodo_admision",
              "u", "y", *F6.LABEL_COLS_T6}
TEXT_COLS = ["persona_key", "cod_programa", "periodo_admision", "split", "via_clase", "cod_admision", "sede", "tipo_colegio",
             "depend_colegio", "region_colegio", "sexo_equidad", "facultad", TD3.PRUEBA_COL, "nivel_estados"]
BOOL_COLS = ["con_postulacion", "malla_conocida", "trayectoria_plan_comun", "especialidad_conocida_al_corte", "titulado_al_corte", "previo_estados"]


def verificar_sin_fuga(num: Sequence[str], cat: Sequence[str]) -> None:
    mal = PROHIBIDAS & (set(num) | set(cat))
    if mal:
        raise ValueError(f"forbidden model features: {sorted(mal)}")


def cargar(conn, mart_schema: str = "neural_mart", core_schema: str = "neural_core") -> pd.DataFrame:
    """``snapshot_t6`` with the faculty code of the program in force at the cut (read only)."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT s.*, p.facultad::text AS facultad FROM {mart_schema}.snapshot_t6 s "
                    f"LEFT JOIN {core_schema}.programa p USING (cod_programa) ORDER BY s.episodio_id")
        cols = [d.name for d in cur.description]
        snap = pd.DataFrame(cur.fetchall(), columns=cols)
    for c in snap.columns:
        if c in TEXT_COLS or c == "episodio_especialidad_id":
            continue
        if c in BOOL_COLS:
            snap[c] = snap[c].astype(bool)
        else:
            snap[c] = pd.to_numeric(snap[c])
    for c in TEXT_COLS:
        snap[c] = snap[c].astype(object).where(snap[c].notna(), None)
    return snap


def particion(snap: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    return {s: snap.loc[snap["split"] == s].reset_index(drop=True) for s in SPLITS}
