"""Baseline 1: historical no_continua rate by (programa, k), learned on train; global rate as fallback."""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_N = 20      # programs with fewer train rows use the global rate


class TasaHistorica:
    def __init__(self, min_n: int = MIN_N):
        self.min_n = min_n

    def fit(self, train: pd.DataFrame) -> "TasaHistorica":
        y = train["y"].astype(float)
        self.global_ = float(y.mean())
        g = y.groupby([train["cod_programa"], train["k"]]).agg(["mean", "size"])
        self.tabla = {key: row["mean"] for key, row in g.iterrows() if row["size"] >= self.min_n}
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        keys = zip(df["cod_programa"], df["k"])
        return np.array([self.tabla.get(key, self.global_) for key in keys], dtype="float64")
