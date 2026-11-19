"""T1 ablation of the new variables of 18-11-2026 (P117-P127) under the selection rule D114 (docs/08_benchmark_t1.md section 16).

``python -m evaluation.run_nuevas_t1`` trains, on the official window (cohorts from 2015), the kept model of each ``k`` (``cb_acad`` at
``k = 1``, ``lr_acad`` at ``k = 2``; the academic variables) and the same two families with the new variables (``pre_entry+academico+
nuevas``; one more group per block of variables, diagnostic only). The decision follows D114: the candidate is chosen on VALID with AP,
it replaces the kept model only if the paired valid difference (bootstrap by person) has an interval that excludes 0 in its favour, ties
keep the simpler model (logistic < CatBoost); the test only confirms.

It also repeats the comparison of the model of the cohorts from 2024 at ``k = 1`` (CatBoost + benefits with the point-in-time view, D113)
adding the new variables: valid = cut year 2024, test = cut year 2025, as in D112.

Writes AGGREGATES to ``artefactos/resultados_t1_nuevas.json`` and the predictions (valid and test) to ``artefactos/preds/t1_nuevas_k*.npz``
(gitignored). It never touches the files of the kept models.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from models import baseline, data as D, seguimiento as S
from pipelines.snapshots.rules import TRAIN_DESDE_OFICIAL
from . import metrics as M
from . import metrics_t45 as M45
from .run_beneficios_cargas_t1 import ajustar_y_predecir, filas_de_evaluacion, sustituir_beneficios

SEMILLAS = (0, 1, 2)
KS = (1, 2)
KEPT = {1: "cb_acad", 2: "lr_acad"}                       # D114: kept model of each k
GRUPO_ACAD = "pre_entry+academico"
GRUPO_NUEVAS = "pre_entry+academico+nuevas"
PRIMARIOS = ("lr_nuevas", "cb_nuevas")                    # the candidates of the decision (every block, both families)
SIMPLICIDAD = {"lr": 0, "cb": 1}                          # D114: logistic < CatBoost
ANIO_PIT = (2024, 2025)                                   # valid and test of the benefits model (D112)


# ---------------------------------------------------------------------------------------------------- pure helpers
def nombre_modelo(familia: str, grupo: str) -> str:
    """``cb_acad`` for the academic group, ``cb_nuevas`` for the full new set and ``cb_nuevas_<bloque>`` for one block."""
    if grupo == GRUPO_ACAD:
        return f"{familia}_acad"
    if grupo == GRUPO_NUEVAS:
        return f"{familia}_nuevas"
    return f"{familia}_nuevas_{grupo.split('+')[-1]}"


def decision_d114(ev_valid: Dict, kept: str, candidatos: Sequence[str]) -> Dict:
    """D114 on valid: a candidate replaces ``kept`` only if its paired AP difference has an interval above 0; among eligible
    candidates the best valid AP wins and an AP tie goes to the simpler family. ``ev_valid`` is ``bootstrap_agrupado`` output."""
    filas = []
    for c in candidatos:
        d = ev_valid[f"{c}__vs__{kept}"]["ap"]
        filas.append({"modelo": c, "ap_valid": ev_valid[c]["ap"]["punto"], "delta_ap": d["punto"], "lo": d["lo"], "hi": d["hi"],
                      "ic_excluye_cero_a_favor": bool(d["lo"] > 0)})
    elegibles = [f for f in filas if f["ic_excluye_cero_a_favor"]]
    if not elegibles:
        return {"kept": kept, "decision": "se_conserva", "modelo": kept, "candidatos": filas}
    mejor = sorted(elegibles, key=lambda f: (-round(f["ap_valid"], 6), SIMPLICIDAD[f["modelo"][:2]]))[0]
    return {"kept": kept, "decision": "reemplaza", "modelo": mejor["modelo"], "candidatos": filas}


def rango_pit(ev: pd.DataFrame, anio: int) -> np.ndarray:
    return (ev["anio_corte"] == anio).to_numpy()


# ---------------------------------------------------------------------------------------------------- training and evaluation
def evaluar_k(snap: pd.DataFrame, k: int, semillas, n_boot: int, log) -> Dict:
    df = D.seleccionar_modelado(snap, k=k, train_desde=TRAIN_DESDE_OFICIAL)
    tr, va, te = (df[df["split"] == s].reset_index(drop=True) for s in D.SPLITS)
    grupos = {GRUPO_ACAD: D.GRUPOS[GRUPO_ACAD], **D.GRUPOS_NUEVAS}
    preds: Dict[str, Dict[str, np.ndarray]] = {"valid": {"baseline_tasa": baseline.TasaHistorica().fit(tr).predict(va)},
                                               "test": {"baseline_tasa": baseline.TasaHistorica().fit(tr).predict(te)}}
    info: Dict[str, Dict] = {}
    for g, (num, cat) in grupos.items():
        t0 = time.perf_counter()
        r = ajustar_y_predecir(tr, va, {"test": te}, num, cat, semillas)
        for fam in ("lr", "cb"):
            nombre = nombre_modelo(fam, g)
            preds["valid"][nombre], preds["test"][nombre] = r[fam]["valid"], r[fam]["test"]
        info[nombre_modelo("lr", g)] = {"C": r["info_lr"]["C"], "n_variables": len(num) + len(cat)}
        log(f"k={k} {g}: {time.perf_counter() - t0:.0f}s  AP valid lr={M.metricas(va['y'].to_numpy(), r['lr']['valid'])['ap']:.4f} "
            f"cb={M.metricas(va['y'].to_numpy(), r['cb']['valid'])['ap']:.4f}")
    kept = KEPT[k]
    nuevos = [n for n in preds["valid"] if "_nuevas" in n]
    pares = [(c, kept) for c in nuevos] + [("cb_nuevas", "lr_nuevas"), ("cb_acad", "lr_acad"), (kept, "baseline_tasa"),
                                           ("lr_nuevas", "lr_acad"), ("cb_nuevas", "cb_acad")]
    pares = [p for p in dict.fromkeys(pares)]
    res: Dict = {"k": k, "kept": kept,
                 "n": {s: {"n": int(len(d)), "eventos": int(d["y"].sum()), "personas": int(d["persona_key"].nunique())}
                       for s, d in zip(("train", "valid", "test"), (tr, va, te))},
                 "info": info, "hash_datos": S.hash_datos(df, ["episodio_id", "k", "y", "split"])}
    for nombre_split, d in (("valid", va), ("test", te)):
        idx = M45.remuestreos(d["persona_key"].to_numpy(), n_boot, seed=7 if nombre_split == "valid" else 9)
        res[nombre_split] = M45.bootstrap_agrupado(d["y"].to_numpy(), preds[nombre_split], idx, pares)
    res["d114"] = decision_d114(res["valid"], kept, PRIMARIOS)
    res["d114_bloques_diagnostico"] = decision_d114(res["valid"], kept, [n for n in nuevos if n not in PRIMARIOS])
    y_te = te["y"].to_numpy()
    res["calibracion_test"] = {n: M.tabla_confiabilidad(y_te, p) for n, p in preds["test"].items() if n in (kept, "cb_nuevas", "lr_nuevas")}
    res["_preds"] = {"episodio_valid": va["episodio_id"].to_numpy(), "episodio_test": te["episodio_id"].to_numpy(), "preds": preds}
    return res


def evaluar_pit(snap: pd.DataFrame, cargas, calendario, semillas, n_boot: int, log, k: int = 1) -> Dict:
    """Cohorts from 2024: CatBoost + benefits (point-in-time view, D113) against the same plus the new variables."""
    from pipelines.snapshots import features_beneficios_cargas as FC

    df = D.seleccionar_modelado(snap, k=k, train_desde=TRAIN_DESDE_OFICIAL)
    tr, va = (df[df["split"] == s].reset_index(drop=True) for s in ("train", "valid"))
    ev_final = filas_de_evaluacion(snap, k)
    ev = sustituir_beneficios(ev_final, FC.features_beneficios_cargas(ev_final, cargas, calendario))
    assert (ev["ben_sin_dato"] == 0).all()
    ben_num, ben_cat = D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios"]
    r_ben = ajustar_y_predecir(tr, va, {"pit": ev}, ben_num, ben_cat, semillas)
    r_nue = ajustar_y_predecir(tr, va, {"pit": ev}, ben_num + D.NUEVAS_NUM, ben_cat, semillas)
    preds = {"baseline_tasa": baseline.TasaHistorica().fit(tr).predict(ev),
             "lr_ben_pit": r_ben["lr"]["pit"], "cb_ben_pit": r_ben["cb"]["pit"],
             "lr_ben_nuevas_pit": r_nue["lr"]["pit"], "cb_ben_nuevas_pit": r_nue["cb"]["pit"]}
    pares = [("cb_ben_nuevas_pit", "cb_ben_pit"), ("lr_ben_nuevas_pit", "cb_ben_pit"), ("lr_ben_nuevas_pit", "lr_ben_pit"),
             ("cb_ben_pit", "baseline_tasa")]
    out: Dict = {"k": k, "kept": "cb_ben_pit"}
    y = ev["y"].to_numpy()
    for nombre, anio in (("valid", ANIO_PIT[0]), ("test", ANIO_PIT[1])):
        m = rango_pit(ev, anio)
        idx = M45.remuestreos(ev.loc[m, "persona_key"].to_numpy(), n_boot, seed=21 + anio)
        out[nombre] = {"anio_corte": anio, "n": int(m.sum()), "eventos": int(y[m].sum()),
                       **M45.bootstrap_agrupado(y[m], {n: p[m] for n, p in preds.items()}, idx, pares)}
    out["d114"] = decision_d114(out["valid"], "cb_ben_pit", ("cb_ben_nuevas_pit", "lr_ben_nuevas_pit"))
    out["_preds"] = {"episodio": ev["episodio_id"].to_numpy(), "anio_corte": ev["anio_corte"].to_numpy(), "preds": preds}
    log(f"k={k} cohortes >= 2024: n={len(ev)}")
    return out


def guardar_preds(res: Dict, nombre: str) -> None:
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    p = res.pop("_preds")
    if "episodio_valid" in p:
        np.savez_compressed(S.ARTEFACTOS / "preds" / f"{nombre}.npz", episodio_valid=p["episodio_valid"],
                            episodio_test=p["episodio_test"], **{f"valid__{n}": v for n, v in p["preds"]["valid"].items()},
                            **{f"test__{n}": v for n, v in p["preds"]["test"].items()})
    else:
        np.savez_compressed(S.ARTEFACTOS / "preds" / f"{nombre}.npz", episodio=p["episodio"], anio_corte=p["anio_corte"],
                            **{f"pit__{n}": v for n, v in p["preds"].items()})


def parsear(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="T1 ablation of the new variables under D114.")
    ap.add_argument("--k", type=int, nargs="+", default=list(KS))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--sin-pit", action="store_true", help="skip the comparison of the cohorts from 2024")
    ap.add_argument("--salida", default="resultados_t1_nuevas")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    log = lambda m: print(m, flush=True)   # noqa: E731
    try:
        from pipelines.common.db import dev_connection
        from . import diagnostico_beneficios_cargas as DC

        with dev_connection() as conn:
            snap, _ = D.cargar_desde_db(conn)
            cargas, calendario, _ = DC.cargar(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t1_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
        out: Dict = {"snapshot_hash": snapshot_hash, "version_codigo": S.version_codigo(), "resultados": {}}
        S.ARTEFACTOS.mkdir(exist_ok=True)
        for k in args.k:
            res = evaluar_k(snap, k, SEMILLAS[: args.seeds], args.boot, log)
            guardar_preds(res, f"t1_nuevas_k{k}")
            out["resultados"][f"k{k}"] = res
            (S.ARTEFACTOS / f"{args.salida}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        if not args.sin_pit and 1 in args.k:
            res = evaluar_pit(snap, cargas, calendario, SEMILLAS[: args.seeds], args.boot, log, k=1)
            guardar_preds(res, "t1_nuevas_pit_k1")
            out["resultados"]["k1_desde2024"] = res
            (S.ARTEFACTOS / f"{args.salida}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print(f"escrito artefactos/{args.salida}.json")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
