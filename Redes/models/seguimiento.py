"""Experiment tracking: MLflow (local file store, gitignored) with data hash and a git-free code version."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
MLRUNS = RAIZ / "mlruns"
ARTEFACTOS = RAIZ / "artefactos"
EXPERIMENTO = "t1_continuidad_1_anio"


def version_codigo() -> str:
    """sha256 over the model, evaluation and snapshot-rule sources (no git involved)."""
    h = hashlib.sha256()
    archivos = sorted(list((RAIZ / "models").glob("*.py")) + list((RAIZ / "evaluation").glob("*.py"))
                      + [RAIZ / "pipelines" / "snapshots" / "rules.py", RAIZ / "pipelines" / "snapshots" / "features.py"])
    for p in archivos:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def hash_datos(df: pd.DataFrame, columnas) -> str:
    cols = [c for c in columnas if c in df.columns]
    hv = pd.util.hash_pandas_object(df[cols].astype(str), index=False).to_numpy()
    return hashlib.sha256(hv.tobytes()).hexdigest()


def iniciar_mlflow():
    import mlflow

    MLRUNS.mkdir(exist_ok=True)
    mlflow.set_tracking_uri(MLRUNS.as_uri())
    mlflow.set_experiment(EXPERIMENTO)
    return mlflow


def registrar(mlflow, nombre: str, params: Dict, metricas: Dict[str, float], etiquetas: Dict[str, str]) -> None:
    with mlflow.start_run(run_name=nombre):
        mlflow.log_params({k: str(v)[:250] for k, v in params.items()})
        mlflow.log_metrics({k: float(v) for k, v in metricas.items() if v is not None and not np.isnan(v)})
        mlflow.set_tags(etiquetas)
