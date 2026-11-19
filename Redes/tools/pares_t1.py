"""Paired bootstrap differences between the three "ingreso + academico" models (logistic, CatBoost, GRU).

Reads the gitignored predictions ``artefactos/preds/t1_k*.npz`` and the labels of the snapshot (dev DB, read only) and
prints aggregate tables (markdown). ``python tools/pares_t1.py [sufijo]``; no suffix = official run (train from 2015);
``_todos_anios`` selects the all-years sensitivity files (``t1_k1_todos_anios.npz``).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from evaluation import metrics as M  # noqa: E402
from models.seguimiento import ARTEFACTOS  # noqa: E402

PARES = [("cb_acad", "lr_acad", "CatBoost − Logística"), ("gru_seq", "lr_acad", "GRU − Logística"),
         ("gru_seq", "cb_acad", "GRU − CatBoost")]


def tablas(sufijo: str = "") -> dict:
    """``{(k, split): markdown}`` of the paired differences; reads the predictions and the snapshot labels."""
    from pipelines.common.db import dev_connection

    with dev_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT episodio_id, k, continua FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'observada'")
        y_de = {(e, k): int(not c) for e, k, c in cur.fetchall()}
    out = {}
    f = lambda d, dec=3: f"{d['punto']:+.{dec}f} [{d['lo']:+.{dec}f}; {d['hi']:+.{dec}f}]"
    for archivo in sorted((ARTEFACTOS / "preds").glob(f"t1_k*{sufijo}.npz")):
        if not sufijo and ("desde" in archivo.name or "todos" in archivo.name):
            continue
        k = int(archivo.name.split("_k")[1][0])
        z = np.load(archivo)
        for split in ("test", "valid"):
            y = np.array([y_de[(int(e), k)] for e in z[f"episodio_{split}"]])
            scores = {m: z[f"{split}__{m}"] for m in ("lr_acad", "cb_acad", "gru_seq")}
            lineas = ["| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |", "|---|---|---|---|---|"]
            for a, b, nombre in PARES:
                r = M.bootstrap(y, {a: scores[a], b: scores[b]}, n_boot=1000, seed=11, referencia=b)[f"__delta__{a}"]
                lineas.append(f"| {nombre} | {f(r['ap'])} | {f(r['roc_auc'])} | {f(r['brier'], 4)} | {f(r['ece'])} |")
            out[(k, split)] = "\n".join(lineas)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sufijo = sys.argv[1] if len(sys.argv) > 1 else ""
    for (k, split), tabla in sorted(tablas(sufijo).items()):
        print(f"\n### k = {k} · {split}\n\n{tabla}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
