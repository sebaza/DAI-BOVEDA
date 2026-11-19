"""D114 check for T4/T5: is the best network better than the best classical model ON VALID, with a paired interval?

``run_t45`` kept a network only if its paired AP difference over the best classical model had an interval above zero on
TEST (``decidir_conservado``), so test took part in the choice. D114 (16-11-2026) selects on valid only: the network is
kept iff its paired valid AP difference (bootstrap grouped by person) has an interval above zero; otherwise the best
classical model on valid stays. This module recomputes that from the saved valid predictions
(``artefactos/preds/t45_k{k}_valid.npz``, gitignored) and the labels of ``neural_mart.snapshot_t45``; it writes aggregates
only to ``artefactos/seleccion_valid_t45.json``.

``python -m evaluation.seleccion_valid_t45 [--boot 1000]`` (dev DB credentials in ``DEV_*``).
"""
from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from evaluation import metrics_t45 as M45
from evaluation import run_t45 as R
from models import t45_data as TD
from models import seguimiento as S

KS = (2, 4)


def decidir_d114(red: Optional[str], clasico: str, delta_valid: Optional[Dict[str, float]]) -> str:
    """D114: the network is kept only if its paired valid difference over the best classical model is above zero."""
    if red is None or delta_valid is None:
        return clasico
    return red if delta_valid["lo"] > 0 else clasico


def evaluar(valid: pd.DataFrame, preds: Dict[str, Dict[str, np.ndarray]], n_boot: int) -> Dict:
    idxs = M45.remuestreos(valid["persona_key"].to_numpy(), n_boot, seed=7)
    out: Dict = {}
    for tgt, (col, _) in TD.TARGETS.items():
        y = valid[col].to_numpy()
        pv = preds[tgt]
        sel = R.elegir_modelos(pv, y)
        red, clasico = sel["red"], sel["clasico"]
        ev = M45.bootstrap_agrupado(y, {m: pv[m] for m in (red, clasico) if m}, idxs, [(red, clasico)] if red else [])
        delta = ev.get(f"{red}__vs__{clasico}", {}).get("ap") if red else None
        out[tgt] = {"clasico": clasico, "red": red,
                    "ap_valid": {m: float(ev[m]["ap"]["punto"]) for m in (red, clasico) if m},
                    "delta_red_vs_clasico_valid": delta,
                    "conservado_d114": decidir_d114(red, clasico, delta)}
    return out


def _cargar_preds(k: int, episodios: np.ndarray) -> Dict[str, Dict[str, np.ndarray]]:
    z = np.load(S.ARTEFACTOS / "preds" / f"t45_k{k}_valid.npz")
    pos = pd.Series(np.arange(len(z["episodio_id"])), index=z["episodio_id"]).reindex(episodios)
    if pos.isna().any():
        raise RuntimeError(f"k={k}: valid predictions do not cover the valid snapshot; rerun run_t45")
    orden = pos.to_numpy().astype(int)
    out: Dict[str, Dict[str, np.ndarray]] = {t: {} for t in TD.TARGETS}
    for clave in z.files:
        if "__" in clave and clave.split("__", 1)[0] in TD.TARGETS:
            tgt, modelo = clave.split("__", 1)
            out[tgt][modelo] = z[clave][orden]
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args(argv)
    from pipelines.common.db import dev_connection
    with dev_connection() as conn:
        snap, _ = TD.cargar(conn)
    res: Dict = {}
    for k in KS:
        valid = TD.particion(snap, k)["valid"].reset_index(drop=True)
        r = evaluar(valid, _cargar_preds(k, valid["episodio_id"].to_numpy()), args.boot)
        res[str(k)] = r
        for tgt, v in r.items():
            d = v["delta_red_vs_clasico_valid"]
            dtxt = f"{d['punto']:+.4f} [{d['lo']:+.4f}; {d['hi']:+.4f}]" if d else "-"
            print(f"k={k} {tgt}: clasico={v['clasico']} red={v['red']} AP valid={v['ap_valid']} delta={dtxt} "
                  f"-> conservado D114={v['conservado_d114']}")
    (S.ARTEFACTOS / "seleccion_valid_t45.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("escrito artefactos/seleccion_valid_t45.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
