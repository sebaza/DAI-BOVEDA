"""Benchmark runner for T1 (docs/08_benchmark_t1.md).

``python -m evaluation.run_benchmark --k 1 2`` trains the baselines, logistic regression, CatBoost and the GRU on the
snapshot in the localhost dev DB, evaluates valid and test and writes AGGREGATES to ``artefactos/resultados_t1*.json``
(gitignored). Individual predictions are kept only as gitignored ``artefactos/preds/*.npz`` files.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from models import baseline, catboost_modelo, data as D, gru as G, logistica, seguimiento as S
from . import metrics as M
from . import subgrupos as SG
from pipelines.snapshots.rules import TRAIN_DESDE_OFICIAL

SEMILLAS = (0, 1, 2)
GRUPO_DE = {"lr_pre": "pre_entry", "lr_acad": "pre_entry+academico", "cb_pre": "pre_entry",
            "cb_acad": "pre_entry+academico", "gru_seq": "pre_entry+secuencia"}


def sufijo_preds(train_desde: Optional[int]) -> str:
    """Suffix of ``artefactos/preds/t1_k*.npz``: official run has none; sensitivity runs are named explicitly."""
    if train_desde == TRAIN_DESDE_OFICIAL:
        return ""
    return "_todos_anios" if train_desde is None else f"_desde{train_desde}"


def _resumen_n(df: pd.DataFrame) -> Dict:
    return {s: {"n": int((df["split"] == s).sum()), "eventos": int(df.loc[df["split"] == s, "y"].sum()),
                "tasa": float(df.loc[df["split"] == s, "y"].mean())} for s in D.SPLITS}


def _semillas(valores: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    out = {}
    for k in M.METRICAS:
        v = np.array([r[k] for r in valores], dtype="float64")
        out[k] = {"media": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0}
    return out


def entrenar_k(snap: pd.DataFrame, sem: pd.DataFrame, k: int, semillas, train_desde: Optional[int], log) -> Dict:
    df = D.seleccionar_modelado(snap, k=k, train_desde=train_desde)
    tr, va, te = (df[df["split"] == s].reset_index(drop=True) for s in D.SPLITS)
    sets = {"valid": va, "test": te}
    preds: Dict[str, Dict[str, np.ndarray]] = {"valid": {}, "test": {}}
    por_semilla: Dict[str, List[Dict[str, Dict[str, float]]]] = {}
    tiempos: Dict[str, float] = {}
    info: Dict[str, Dict] = {}

    def guardar(nombre, p_va, p_te):
        preds["valid"][nombre], preds["test"][nombre] = p_va, p_te

    # 1. historical rate
    t0 = time.perf_counter()
    b = baseline.TasaHistorica().fit(tr)
    guardar("baseline_tasa", b.predict(va), b.predict(te))
    tiempos["baseline_tasa"] = time.perf_counter() - t0
    log(f"k={k} baseline listo")

    for grupo_nombre, (num, cat) in D.GRUPOS.items():
        sufijo = "pre" if grupo_nombre == "pre_entry" else "acad"
        prep = D.Preprocesador(num, cat).fit(tr)
        # 2. logistic regression
        t0 = time.perf_counter()
        Xtr, Xva, Xte = (prep.transform(x) for x in (tr, va, te))
        m, inf = logistica.ajustar(Xtr, tr["y"].to_numpy(), Xva, va["y"].to_numpy())
        guardar(f"lr_{sufijo}", m.predict_proba(Xva)[:, 1], m.predict_proba(Xte)[:, 1])
        tiempos[f"lr_{sufijo}"] = time.perf_counter() - t0
        info[f"lr_{sufijo}"] = {kk: v for kk, v in inf.items() if kk != "busqueda"}
        info[f"lr_{sufijo}"]["n_variables"] = int(Xtr.shape[1])
        log(f"k={k} lr_{sufijo}: C={inf['C']} peso={inf['class_weight']} AP valid={inf['ap_valid']:.4f}")
        # 3. CatBoost (seed ensemble)
        t0 = time.perf_counter()
        Ctr, Cva, Cte = (prep.transform_catboost(x) for x in (tr, va, te))
        pv, pt, its, ind = [], [], [], []
        for s in semillas:
            cb, cinf = catboost_modelo.ajustar(Ctr, tr["y"], Cva, va["y"], cat, seed=s)
            p_va, p_te = catboost_modelo.predecir(cb, Cva, cat), catboost_modelo.predecir(cb, Cte, cat)
            pv.append(p_va), pt.append(p_te), its.append(cinf["mejor_iteracion"])
            ind.append({"valid": M.metricas(va["y"].to_numpy(), p_va), "test": M.metricas(te["y"].to_numpy(), p_te)})
        guardar(f"cb_{sufijo}", np.mean(pv, axis=0), np.mean(pt, axis=0))
        tiempos[f"cb_{sufijo}"] = time.perf_counter() - t0
        por_semilla[f"cb_{sufijo}"] = ind
        info[f"cb_{sufijo}"] = {"mejores_iteraciones": its, "n_variables": len(num) + len(cat),
                                "params": {kk: str(v) for kk, v in catboost_modelo.PARAMS.items()}}
        log(f"k={k} cb_{sufijo}: iteraciones={its}")

    # 4. GRU: static pre-entry profile + sequence of the semester vectors 1..k
    num, cat = D.GRUPOS["pre_entry"]
    prep = D.Preprocesador(num, cat).fit(tr)

    def conj(x):
        return G.Conjunto(D.construir_secuencias(x, sem, k), prep.transform_num(x), prep.transform_cat_codes(x),
                          x["y"].to_numpy())

    ctr, cva, cte = conj(tr), conj(va), conj(te)
    pv, pt, ind, runs = [], [], [], []
    import torch
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    for s in semillas:
        r = G.entrenar(ctr, cva, prep.cardinalidades(), seed=s, device=dev)
        p_va, p_te = G.predecir(r["model"], cva, dev), G.predecir(r["model"], cte, dev)
        pv.append(p_va), pt.append(p_te)
        ind.append({"valid": M.metricas(va["y"].to_numpy(), p_va), "test": M.metricas(te["y"].to_numpy(), p_te)})
        runs.append({kk: v for kk, v in r.items() if kk != "model"})
        log(f"k={k} gru seed={s}: AP valid={r['ap_valid']:.4f} epoca={r['mejor_epoca']} "
            f"{r['segundos']:.0f}s gpu={r['gpu_pico_mb']:.0f}MB")
    guardar("gru_seq", np.mean(pv, axis=0), np.mean(pt, axis=0))
    por_semilla["gru_seq"] = ind
    tiempos["gru_seq"] = float(sum(r["segundos"] for r in runs))
    info["gru_seq"] = {"semillas": runs, "hidden": G.HIDDEN, "static_dim": G.STATIC_DIM, "batch": G.BATCH,
                       "lr": G.LR, "weight_decay": G.WD, "max_epocas": G.MAX_EPOCHS, "paciencia": G.PACIENCIA,
                       "n_variables_estaticas": int(ctr.num.shape[1]), "d_secuencia": int(ctr.seq.shape[2])}

    # evaluation
    res: Dict = {"k": k, "n": _resumen_n(df), "grupos": GRUPO_DE, "info": info, "tiempos_s": tiempos,
                 "train_desde": train_desde, "hash_datos": S.hash_datos(df, ["episodio_id", "k", "y", "split"]),
                 "semillas": {n: {s: _semillas([r[s] for r in v]) for s in ("valid", "test")}
                              for n, v in por_semilla.items()}}
    for nombre_split, d in sets.items():
        y = d["y"].to_numpy()
        res[nombre_split] = M.bootstrap(y, preds[nombre_split], n_boot=BOOT, seed=7, referencia="baseline_tasa")
        if "cb_acad" in preds[nombre_split]:
            extra = M.bootstrap(y, {"gru_seq": preds[nombre_split]["gru_seq"], "cb_acad": preds[nombre_split]["cb_acad"]},
                                n_boot=BOOT, seed=7, referencia="cb_acad")
            res[nombre_split]["__delta_gru_vs_cb_acad"] = extra["__delta__gru_seq"]
    y_te = te["y"].to_numpy()
    res["calibracion_test"] = {n: M.tabla_confiabilidad(y_te, p) for n, p in preds["test"].items()}
    res["subgrupos_test"] = {n: SG.todos(te, y_te, p) for n, p in preds["test"].items()}
    res["brecha_sexo_test"] = {n: SG.brechas_sexo(t["sexo"]) for n, t in res["subgrupos_test"].items()}
    # raw predictions stay in gitignored artefacts
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(S.ARTEFACTOS / "preds" / f"t1_k{k}{sufijo_preds(train_desde)}.npz",
                        episodio_valid=va["episodio_id"].to_numpy(), episodio_test=te["episodio_id"].to_numpy(),
                        **{f"valid__{n}": p for n, p in preds["valid"].items()},
                        **{f"test__{n}": p for n, p in preds["test"].items()})
    return res


def registrar_mlflow(res: Dict, snapshot_hash: str, etiqueta: str) -> None:
    mlflow = S.iniciar_mlflow()
    codigo = S.version_codigo()
    k = res["k"]
    for nombre in res["test"]:
        if nombre.startswith("__"):
            continue
        met = {}
        for split in ("valid", "test"):
            for m_, v in res[split][nombre].items():
                met[f"{split}_{m_}"] = v["punto"]
                met[f"{split}_{m_}_lo"], met[f"{split}_{m_}_hi"] = v["lo"], v["hi"]
        met["segundos_entrenamiento"] = res["tiempos_s"][nombre]
        if nombre == "gru_seq":
            met["gpu_pico_mb"] = max(r["gpu_pico_mb"] for r in res["info"]["gru_seq"]["semillas"])
        params = {"k": k, "modelo": nombre, "grupo": GRUPO_DE.get(nombre, "perfil_historico"),
                  "train_desde": res["train_desde"], "n_train": res["n"]["train"]["n"],
                  "n_valid": res["n"]["valid"]["n"], "n_test": res["n"]["test"]["n"],
                  **{kk: json.dumps(v)[:240] for kk, v in res["info"].get(nombre, {}).items() if kk != "semillas"}}
        S.registrar(mlflow, f"{etiqueta}_k{k}_{nombre}", params, met,
                    {"hash_datos": res["hash_datos"], "hash_snapshot": snapshot_hash, "version_codigo": codigo,
                     "tarea": "T1", "evento": "no_continua"})


BOOT = 1000


def parsear(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """CLI. Official configuration: train from cohort 2015 (DAI P49/P50); ``--todos-los-anios`` is the sensitivity run."""
    ap = argparse.ArgumentParser(description="Train and evaluate the T1 benchmark.")
    ap.add_argument("--k", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--train-desde", type=int, default=TRAIN_DESDE_OFICIAL,
                    help=f"first cohort year kept in train (official: {TRAIN_DESDE_OFICIAL})")
    ap.add_argument("--todos-los-anios", action="store_true",
                    help="sensitivity: keep every train cohort (<= 2019), ignoring --train-desde")
    ap.add_argument("--salida", default=None, help="artefact name (default resultados_t1, or resultados_t1_todos_anios)")
    args = ap.parse_args(argv)
    if args.todos_los_anios:
        args.train_desde = None
    if args.salida is None:
        args.salida = "resultados_t1_todos_anios" if args.train_desde is None else "resultados_t1"
    return args


def main(argv: Optional[List[str]] = None) -> int:
    global BOOT
    args = parsear(argv)
    BOOT = args.boot
    try:
        from pipelines.common.db import dev_connection

        with dev_connection() as conn:
            snap, sem = D.cargar_desde_db(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t1_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
        resultados = {}
        for k in args.k:
            res = entrenar_k(snap, sem, k, SEMILLAS[: args.seeds], args.train_desde, lambda m: print(m, flush=True))
            registrar_mlflow(res, snapshot_hash, args.salida)
            resultados[f"k{k}"] = res
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / f"{args.salida}.json").write_text(
            json.dumps({"snapshot_hash": snapshot_hash, "version_codigo": S.version_codigo(), "resultados": resultados},
                       indent=1, default=float), encoding="utf-8")
        print(f"escrito artefactos/{args.salida}.json")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
