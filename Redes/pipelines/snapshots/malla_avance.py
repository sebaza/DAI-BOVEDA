"""Curricular-lag helper shared by the snapshots that need the credits expected by the malla at a semester ``k``.

The T3 snapshot (``features_t3.features_programa``) computes ``creditos_esperados`` and ``creditos_malla_total`` from the malla of the
initial catalog of the episode. This module holds the same minimal logic for the other tasks WITHOUT editing the T3 files (another
line of work owns them); ``tests/unit/test_features_t1_nuevas.py`` checks that both give identical values, so a change in one is
caught in the other. The malla is static, so nothing here depends on the cut date.
"""
from __future__ import annotations

from typing import Sequence

import pandas as pd


def creditos_malla(pop: pd.DataFrame, malla: pd.DataFrame, ks: Sequence[int]) -> pd.DataFrame:
    """One row per episode of ``pop`` (columns ``episodio_id``, ``cod_programa``, ``catalogo_inicial``) with the total credits of
    its malla (``creditos_malla_total``) and the credits of the courses of semester ``<= k`` (``_ce{k}``). NaN when the malla of the
    program and initial catalog is unknown."""
    m = malla.loc[malla["semestre"].notna()].copy()
    m["creditos"] = pd.to_numeric(m["creditos"], errors="coerce").fillna(0.0)
    g = m.groupby(["cod_programa", "catalogo"])
    t = pd.DataFrame({"creditos_malla_total": g["creditos"].sum()})
    for k in ks:
        if k >= 1:
            t[f"_ce{k}"] = m.loc[m["semestre"] <= k].groupby(["cod_programa", "catalogo"])["creditos"].sum()
    t = t.reset_index()
    t["malla_conocida"] = True
    x = pop[["episodio_id", "cod_programa", "catalogo_inicial"]].merge(
        t, left_on=["cod_programa", "catalogo_inicial"], right_on=["cod_programa", "catalogo"], how="left")
    x["malla_conocida"] = x["malla_conocida"].eq(True)
    for k in ks:
        if k >= 1:
            x[f"_ce{k}"] = x[f"_ce{k}"].fillna(0.0).where(x["malla_conocida"])
    return x.drop(columns=["cod_programa", "catalogo_inicial", "catalogo", "malla_conocida"]).reset_index(drop=True)
