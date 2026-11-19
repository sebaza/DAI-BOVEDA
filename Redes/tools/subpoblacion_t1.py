"""Does the risk signal come only from students who had no evaluated course in semester k?

Aggregate check on the test split: event rate and AP of the CatBoost "ingreso + agregados" predictions inside the rows
with and without evaluated attempts in the last semester before the cutoff. Reads the gitignored predictions and the
snapshot (dev DB, read only); prints markdown with counts and rates only. ``python tools/subpoblacion_t1.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from evaluation import metrics as M  # noqa: E402
from models.seguimiento import ARTEFACTOS  # noqa: E402


def tabla() -> str:
    from pipelines.common.db import dev_connection

    with dev_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT episodio_id, k, intentos_ult_semestre, continua FROM neural_mart.snapshot_t1 "
                    "WHERE estado_muestra = 'observada'")
        info = {(e, k): (int(n), int(not c)) for e, k, n, c in cur.fetchall()}
    out = ["| k | Subpoblación (test) | n | Eventos | Tasa | AP CatBoost | AP Logística | AP GRU |",
           "|---|---|---|---|---|---|---|---|"]
    for k in (1, 2):
        z = np.load(ARTEFACTOS / "preds" / f"t1_k{k}.npz")
        ids = z["episodio_test"]
        n_ult = np.array([info[(int(e), k)][0] for e in ids])
        y = np.array([info[(int(e), k)][1] for e in ids])
        for nombre, mask in (("sin intentos evaluados en el semestre k", n_ult == 0),
                             ("con al menos un intento evaluado en el semestre k", n_ult > 0)):
            aps = []
            for m in ("cb_acad", "lr_acad", "gru_seq"):
                p = z[f"test__{m}"][mask]
                aps.append(f"{M.metricas(y[mask], p)['ap']:.3f}" if 0 < y[mask].sum() < mask.sum() else "—")
            out.append(f"| {k} | {nombre} | {int(mask.sum())} | {int(y[mask].sum())} | {y[mask].mean():.3f} | "
                       + " | ".join(aps) + " |")
    return "\n".join(out)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print(tabla())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
