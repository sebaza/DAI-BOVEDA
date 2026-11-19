"""Calibration of the new T5 models (D120) on VALID only, and the T5 block that the Boveda publishes with them.

The two candidates of ``ablacion_variables`` that D114 adopted for T5 (``cb_agg+reg_alc`` at k = 2, ``lr_agg+reg_alc`` at
k = 4) rank better than the kept GRUs but calibrate worse (``docs/11_benchmark_t4_t5.md`` 13.4). This module fixes that
before they are published:

* Platt (logistic on the logit of the score) and isotonic calibrators are fitted on VALID predictions only. The method is
  chosen per k by the lower Brier of a person-grouped K-fold cross-fit INSIDE valid (a tie goes to Platt, the simpler one);
  test never takes part in fitting or choosing. The chosen calibrator is then fitted on all of valid and applied to test.
* The calibrated predictions are added as new keys ``T5__<alias>_cal`` to ``artefactos/preds/t45_k{k}_{valid,test}.npz``
  (valid: the cross-fitted predictions, so valid metrics stay honest; test: the full-valid calibrator). Arrays already in the
  files are verified bit-identical.
* ``artefactos/calibracion_t5_nuevas.json`` (gitignored, aggregates only) keeps the calibrator parameters, the before / after
  metrics and ``bloque_t5``: the T5 block of ``resultados_t45.json`` recomputed with the calibrated candidate as the kept
  model (same bootstrap, groups and sensitivity as ``run_t45.evaluar_k``). ``pipelines.marts.resumen_tareas`` merges it.

``python -m evaluation.calibrar_t5_nuevas [--boot 1000]`` (dev DB credentials in ``DEV_*``; labels and person keys come from
``neural_mart.snapshot_t45``).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from evaluation import metrics as M

# k -> (kept model before D120, candidate adopted by D114 in ``ablacion_variables --tarea t45-final``)
CONSERVADO_ANTERIOR = {2: "gru_adm", 4: "gru_agg"}
CANDIDATO = {2: "cb_agg_reg_alc", 4: "lr_agg_reg_alc"}
CLASICO_MISMA_FAMILIA = {2: "cb_agg", 4: "lr_agg"}
SUFIJO = "_cal"
N_FOLDS = 5
SEMILLA = 0
EPS = 1e-6


def modelo_calibrado(k: int) -> str:
    return CANDIDATO[k] + SUFIJO


# ---------------------------------------------------------------------------------------------
# calibrators
# ---------------------------------------------------------------------------------------------
def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype="float64"), EPS, 1 - EPS)
    return np.log(p / (1 - p))


class PlattCalibrador:
    """Logistic regression on the logit of the score: ``sigmoid(a * logit(p) + b)`` (monotone for a > 0)."""
    nombre = "platt"

    def __init__(self, a: float = 1.0, b: float = 0.0):
        self.a, self.b = float(a), float(b)

    def ajustar(self, p, y) -> "PlattCalibrador":
        from sklearn.linear_model import LogisticRegression

        m = LogisticRegression(penalty=None, solver="lbfgs", max_iter=1000).fit(_logit(p).reshape(-1, 1), np.asarray(y))
        self.a, self.b = float(m.coef_[0, 0]), float(m.intercept_[0])
        return self

    def predecir(self, p) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-(self.a * _logit(p) + self.b)))

    def parametros(self) -> Dict:
        return {"metodo": self.nombre, "a": self.a, "b": self.b}

    @classmethod
    def desde_parametros(cls, d: Dict) -> "PlattCalibrador":
        return cls(d["a"], d["b"])


class IsotonicaCalibrador:
    """Isotonic regression (piecewise-linear interpolation of the fitted thresholds, clipped outside the fitted range)."""
    nombre = "isotonica"

    def __init__(self, x: Optional[Sequence[float]] = None, y: Optional[Sequence[float]] = None):
        self.x = None if x is None else np.asarray(x, dtype="float64")
        self.y = None if y is None else np.asarray(y, dtype="float64")

    def ajustar(self, p, y) -> "IsotonicaCalibrador":
        from sklearn.isotonic import IsotonicRegression

        m = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(np.asarray(p, dtype="float64"), np.asarray(y))
        self.x, self.y = np.asarray(m.X_thresholds_, dtype="float64"), np.asarray(m.y_thresholds_, dtype="float64")
        return self

    def predecir(self, p) -> np.ndarray:
        return np.interp(np.asarray(p, dtype="float64"), self.x, self.y)

    def parametros(self) -> Dict:
        return {"metodo": self.nombre, "x": self.x.tolist(), "y": self.y.tolist()}

    @classmethod
    def desde_parametros(cls, d: Dict) -> "IsotonicaCalibrador":
        return cls(d["x"], d["y"])


CALIBRADORES = {"platt": PlattCalibrador, "isotonica": IsotonicaCalibrador}


# ---------------------------------------------------------------------------------------------
# cross-fitting inside valid and method choice (pure)
# ---------------------------------------------------------------------------------------------
def folds_por_persona(grupos: Sequence, n_folds: int = N_FOLDS, seed: int = SEMILLA) -> np.ndarray:
    """Fold of every row; all the rows of a person share the fold (persons are shuffled, then dealt round robin)."""
    import pandas as pd

    codigos, unicos = pd.factorize(np.asarray(grupos))
    orden = np.random.default_rng(seed).permutation(len(unicos))
    fold_de_persona = np.empty(len(unicos), dtype=int)
    fold_de_persona[orden] = np.arange(len(unicos)) % n_folds
    return fold_de_persona[codigos]


def ajuste_cruzado(cls, y: np.ndarray, p: np.ndarray, folds: np.ndarray) -> np.ndarray:
    """Out-of-fold calibrated scores: each row is calibrated by a calibrator fitted on the other folds."""
    y, p = np.asarray(y), np.asarray(p, dtype="float64")
    q = np.empty(len(p), dtype="float64")
    for f in np.unique(folds):
        dentro = folds == f
        q[dentro] = cls().ajustar(p[~dentro], y[~dentro]).predecir(p[dentro])
    return q


def elegir_metodo(brier_platt: float, brier_isotonica: float) -> str:
    """Lower cross-fitted Brier; a tie keeps the simpler Platt."""
    return "isotonica" if brier_isotonica < brier_platt else "platt"


def calibrar(y_valid, p_valid, grupos_valid, p_test, n_folds: int = N_FOLDS, seed: int = SEMILLA, metodo: Optional[str] = None) -> Dict:
    """Fit on valid only. There is deliberately no argument for test labels: the test scores are only transformed.

    Returns the chosen ``metodo``, the cross-fitted Briers of both methods, the fitted ``parametros`` (all of valid), the
    cross-fitted valid predictions (``valid_cruzado``, of the chosen method) and the calibrated ``test`` scores."""
    y_valid = np.asarray(y_valid)
    p_valid = np.asarray(p_valid, dtype="float64")
    folds = folds_por_persona(grupos_valid, n_folds, seed)
    cruzado = {n: ajuste_cruzado(cls, y_valid, p_valid, folds) for n, cls in CALIBRADORES.items()}
    brier = {n: float(np.mean((q - y_valid) ** 2)) for n, q in cruzado.items()}
    elegido = metodo or elegir_metodo(brier["platt"], brier["isotonica"])
    cal = CALIBRADORES[elegido]().ajustar(p_valid, y_valid)
    return {"metodo": elegido, "brier_cruzado": brier, "parametros": cal.parametros(), "n_folds": int(n_folds), "semilla": int(seed),
            "valid_cruzado": cruzado[elegido], "valid_cruzado_todos": cruzado, "test": cal.predecir(p_test)}


# ---------------------------------------------------------------------------------------------
# additive publication of the predictions
# ---------------------------------------------------------------------------------------------
def agregar_clave(ruta: Path, clave: str, valores: np.ndarray) -> None:
    """Add (or replace) ``clave`` in an npz; every array that was already there must stay bit-identical."""
    z = dict(np.load(ruta))
    if len(valores) != len(z["episodio_id"]):
        raise ValueError(f"{Path(ruta).name}: {clave} has {len(valores)} rows, the file {len(z['episodio_id'])}")
    original = {n: v.copy() for n, v in z.items() if n != clave}
    z[clave] = np.asarray(valores).astype("float32")
    np.savez_compressed(ruta, **z)
    nuevo = np.load(ruta)
    if any(not np.array_equal(nuevo[n], original[n]) for n in original):
        raise RuntimeError(f"{Path(ruta).name}: an array that was already there changed")


# ---------------------------------------------------------------------------------------------
# database part
# ---------------------------------------------------------------------------------------------
def _metricas4(y, p) -> Dict[str, float]:
    m = M.metricas(y, p)
    return {k: float(m[k]) for k in ("ap", "roc_auc", "brier", "ece")}


def _alinear(ids: np.ndarray, z, clave: str) -> np.ndarray:
    import pandas as pd

    pos = pd.Series(np.arange(len(z["episodio_id"])), index=z["episodio_id"]).reindex(ids)
    if pos.isna().any():
        raise RuntimeError("saved predictions do not cover the rows: rerun the benchmark runner")
    return z[clave][pos.to_numpy().astype(int)].astype("float64")


def calibrar_k(parts, k: int, preds_dir: Path) -> Tuple[Dict, Dict[str, Dict[str, np.ndarray]]]:
    """Calibrates the candidate of cut ``k``; returns the aggregates and the T5 predictions of valid and test by model."""
    from models import t45_data as TD

    col = TD.TARGETS["T5"][0]
    va, te = parts["valid"], parts["test"]
    y = {"valid": va[col].to_numpy(), "test": te[col].to_numpy()}
    z = {s: np.load(preds_dir / f"t45_k{k}_{s}.npz") for s in ("valid", "test")}
    ids = {"valid": va["episodio_id"].to_numpy(), "test": te["episodio_id"].to_numpy()}
    for s in ("valid", "test"):
        if not np.array_equal(z[s]["episodio_id"], ids[s]):
            raise RuntimeError(f"t45_k{k}_{s}.npz: row order differs from the snapshot")
    preds = {s: {c[4:]: z[s][c].astype("float64") for c in z[s].files if c.startswith("T5__")} for s in ("valid", "test")}
    cand, kept = CANDIDATO[k], CONSERVADO_ANTERIOR[k]
    nombre_cal = modelo_calibrado(k)
    # the candidate is always the UNcalibrated key; a ``_cal`` key left by an earlier run is overwritten below
    r = calibrar(y["valid"], preds["valid"][cand], va["persona_key"].to_numpy(), preds["test"][cand])
    preds["valid"][nombre_cal], preds["test"][nombre_cal] = r["valid_cruzado"], r["test"]
    comp = {
        "valid_cruzado": {"conservado_anterior": _metricas4(y["valid"], preds["valid"][kept]),
                          "sin_calibrar": _metricas4(y["valid"], preds["valid"][cand]),
                          "calibrado": _metricas4(y["valid"], r["valid_cruzado"]),
                          "calibrado_platt": _metricas4(y["valid"], r["valid_cruzado_todos"]["platt"]),
                          "calibrado_isotonica": _metricas4(y["valid"], r["valid_cruzado_todos"]["isotonica"])},
        "test": {"conservado_anterior": _metricas4(y["test"], preds["test"][kept]),
                 "sin_calibrar": _metricas4(y["test"], preds["test"][cand]),
                 "calibrado": _metricas4(y["test"], r["test"])},
    }
    info = {"k": k, "conservado_anterior": kept, "candidato": cand, "modelo_publicado": nombre_cal, "metodo": r["metodo"],
            "brier_cruzado": r["brier_cruzado"], "parametros": r["parametros"], "n_folds": r["n_folds"], "semilla": r["semilla"],
            "n": {"valid": int(len(va)), "test": int(len(te))},
            "eventos": {"valid": int(y["valid"].sum()), "test": int(y["test"].sum())},
            "tasa_observada": {"valid": float(y["valid"].mean()), "test": float(y["test"].mean())},
            "riesgo_medio": {s: {"conservado_anterior": float(preds[s][kept].mean()), "sin_calibrar": float(preds[s][cand].mean()),
                                 "calibrado": float(preds[s][nombre_cal].mean())} for s in ("valid", "test")},
            "comparacion": comp}
    return info, preds


def bloque_t5(parts, k: int, preds: Dict[str, Dict[str, np.ndarray]], n_boot: int, programas, log) -> Dict:
    """The T5 block of ``evaluar_k`` with the calibrated candidate as the kept model (and the other models as before)."""
    from evaluation import run_t45 as R

    kept, cand, cal = CONSERVADO_ANTERIOR[k], CANDIDATO[k], modelo_calibrado(k)
    res = {"parts": parts, "preds": {"T5": {s: {m: p for m, p in preds[s].items()} for s in ("valid", "test")}}}
    pares = [(cal, "baseline_tasa"), (cal, cand), (cal, CLASICO_MISMA_FAMILIA[k]), (kept, cal), (kept, "baseline_tasa")]
    ev = R.evaluar_k(res, k, n_boot, log, programas, objetivos=("T5",), conservado_forzado={"T5": cal},
                     pares_extra={"T5": pares}, multiclase=False)
    bloque = ev["targets"]["T5"]
    bloque["seleccion"]["conservado_anterior"] = kept
    return bloque


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--sin-publicar", action="store_true", help="do not add the calibrated keys to the npz files")
    args = ap.parse_args(argv)
    try:
        from evaluation import facultades as FA
        from models import seguimiento as S
        from models import t45_data as TD
        from pipelines.common.db import dev_connection

        preds_dir = S.ARTEFACTOS / "preds"
        with dev_connection() as conn:
            snap, _ = TD.cargar(conn)
            programas = FA.cargar_programas(conn)
        out: Dict = {"version": 1, "regla": "D120: calibrar sobre valid (Platt o isotónica por Brier cruzado) antes de publicar", "por_k": {}}
        for k in CANDIDATO:
            parts = TD.particion(snap, k)
            info, preds = calibrar_k(parts, k, preds_dir)
            print(f"k={k}: {info['candidato']} -> metodo {info['metodo']} (Brier cruzado {info['brier_cruzado']})", flush=True)
            for etapa in ("valid_cruzado", "test"):
                for nombre, m in info["comparacion"][etapa].items():
                    print(f"  {etapa:14} {nombre:22} " + " ".join(f"{a}={v:.4f}" for a, v in m.items()), flush=True)
            if not args.sin_publicar:
                for s in ("valid", "test"):
                    agregar_clave(preds_dir / f"t45_k{k}_{s}.npz", f"T5__{modelo_calibrado(k)}", preds[s][modelo_calibrado(k)])
            info["bloque_t5"] = bloque_t5(parts, k, preds, args.boot, programas, lambda m: print(m, flush=True))
            out["por_k"][str(k)] = info
        (S.ARTEFACTOS / "calibracion_t5_nuevas.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print("escrito artefactos/calibracion_t5_nuevas.json")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
