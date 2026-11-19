"""Exit blocks of the view "Lo que pasó": causes of elimination by program and time to graduate (egreso) by program.

* ``bloque_causales_programa``  eliminations of undergraduate episodes from ``PERIODO_CAUSAL_DESDE`` to ``PERIODO_TOTALES_HASTA``
  grouped as in P117. Rows are programs (faculties under "Toda la UCN"), every one with its exact total; each row lists the six
  causes of the P117 list with their exact count (no size-based «otros» row).
* ``bloque_tiempo``  share of the cohorts that graduated within the nominal duration, +1 and +2 years, among the episodes with
  at least ``duracion + 4`` semesters of follow-up (T3 snapshot, k = 0). Every program with at least one episode is published.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from evaluation.vista_historica import GRUPOS_CAUSAL, PERIODO_CAUSAL_DESDE, PERIODO_TOTALES_HASTA, grupo_causal

REGLA_DURACION = ("Duración nominal = mayor semestre de la malla de cada generación; se cuentan solo las generaciones con al menos "
                  "la duración más 4 semestres de seguimiento. «A tiempo» = egreso dentro de la duración; «+1» y «+2» = hasta 2 y 4 "
                  "semestres más.")
SEMESTRES_MAS = {"pct_a_tiempo": 0, "pct_mas_1": 2, "pct_mas_2": 4}
CAUSA_EGRESO = 1                      # snapshot_t3 ``causa``: 1 = egreso


def _conteos(g: pd.DataFrame) -> Dict[str, int]:
    grupos = g["cod_causal"].map(grupo_causal).value_counts()
    return {k: int(grupos.get(k, 0)) for k in GRUPOS_CAUSAL}


def _causales(conteos: Dict[str, int]) -> List[Dict[str, Any]]:
    return [{"grupo": k, "etiqueta": GRUPOS_CAUSAL[k][0], "n": n} for k, n in conteos.items()]


def una_por_episodio(causas: pd.DataFrame) -> pd.DataFrame:
    """The eliminations of the window ``PERIODO_CAUSAL_DESDE`` .. ``PERIODO_TOTALES_HASTA``, one per episode (the last one). Every
    cause table of the view starts from this frame so two blocks about the same topic can never differ by a window or a duplicate."""
    d = causas.loc[(causas["periodo"] >= PERIODO_CAUSAL_DESDE) & (causas["periodo"] <= PERIODO_TOTALES_HASTA)]
    return d.sort_values("periodo").drop_duplicates("episodio_id", keep="last")


def bloque_causales_programa(causas: pd.DataFrame, por: str = "programa") -> Optional[Dict[str, Any]]:
    """``{desde, hasta, filas: [{cod_programa, programa, total, causales}]}``; ``por="facultad"`` makes each row a faculty.

    ``causas``: ``episodio_id, periodo, cod_programa, programa, facultad, cod_causal`` (one row per elimination)."""
    d = una_por_episodio(causas)                                                   # one elimination per episode
    if d.empty:
        return None
    clave = "facultad" if por == "facultad" else "cod_programa"
    out = []
    for k, g in d.groupby(clave, sort=True, dropna=False):
        nombres = g["programa"].dropna()
        nombre = str(k) if por == "facultad" or nombres.empty else str(nombres.iloc[0])
        out.append({"cod_programa": None if por == "facultad" else str(k), "programa": nombre, "total": int(len(g)),
                    "causales": _causales(_conteos(g))})
    return {"desde": PERIODO_CAUSAL_DESDE, "hasta": PERIODO_TOTALES_HASTA, "nivel": por, "filas": out}


def _pct_acumulado(egr: int, n: int) -> Optional[float]:
    """Cumulative share of the episodes that graduated; ``None`` for an empty group."""
    return egr / n if n else None


def bloque_tiempo(t3: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """``{regla_duracion, filas: [{cod_programa, programa, n, duracion_nominal_sem, pct_a_tiempo, pct_mas_1, pct_mas_2}]}``.

    ``t3``: ``cod_programa, programa, duracion_nominal_sem, seguimiento_max, tiempo, causa`` (one row per episode). The duration is
    the one of the episode's own curriculum; the row shows the most frequent one of the program."""
    dur = t3["duracion_nominal_sem"]
    d = t3.loc[t3["seguimiento_max"] >= dur + 4]
    filas = []
    for k, g in d.groupby("cod_programa", sort=True):
        n = int(len(g))
        egr = g["causa"] == CAUSA_EGRESO
        fila: Dict[str, Any] = {"cod_programa": str(k), "programa": str(g["programa"].iloc[0]), "n": n,
                                "duracion_nominal_sem": int(g["duracion_nominal_sem"].mode().min())}
        for campo, extra in SEMESTRES_MAS.items():
            hasta = int((egr & (g["tiempo"] <= g["duracion_nominal_sem"] + extra)).sum())
            fila[campo] = _pct_acumulado(hasta, n)
        filas.append(fila)
    return {"regla_duracion": REGLA_DURACION, "filas": filas} if filas else None
