"""Benchmark runner for T3 (docs/10_benchmark_t3.md): time to graduation with censoring and a competing exit.

``python -m evaluation.run_t3`` trains, for each cut k (0 = at enrollment, 2, 4): Aalen-Johansen (pooled and per program),
cause-specific Cox, person-period logistic regression and CatBoost, and the neural discrete-time competing-risks MLP
and GRU (3 seeds, GPU) on the nested feature sets ``adm`` / ``adm+agg``; evaluates valid (cohort 2018), test (cohorts
2019-2020) and posterior (2021-2022, control) at fixed horizons with an episode bootstrap, and writes AGGREGATES to
``artefactos/resultados_t3.json`` (gitignored). Individual cumulative incidences are kept only as gitignored
``artefactos/preds/t3_*.npz``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from evaluation import metrics_t3 as M3
from evaluation.run_t2 import ram_pico_mb
from models import seguimiento as S
from models.data import Preprocesador
from models import t3_data as TD
from models import t3_discreto as DT
from models import t3_redes as NR
from models import t3_supervivencia as SV

SEMILLAS = (0, 1, 2)
EXPERIMENTO_T3 = "t3_tiempo_hasta_titulacion"
KS = (0, 2, 4)
EVAL_SPLITS = ("valid", "test", "posterior")
HORIZONTES = {"valid": (10, 12, 14), "test": (10, 12, 14), "posterior": (8, 10)}
IBS_HASTA = {"valid": 12, "test": 12, "posterior": 8}
GRID_PENALIZADOR = (0.0003, 0.001, 0.01, 0.1, 1.0)
MIN_PROGRAMA_SUBGRUPO = 500
PROGRAMAS_MIN_ALT = 150
CLASICOS = ("km_global", "km_programa", "cox_adm", "cox_agg", "dt_lr_adm", "dt_lr_agg", "dt_cb_adm", "dt_cb_agg")
NEURALES = ("nn_mlp_adm", "nn_mlp_agg", "nn_gru")


def version_codigo_t3() -> str:
    from pathlib import Path

    raiz = Path(S.RAIZ)
    h = hashlib.sha256(S.version_codigo().encode())
    for p in (raiz / "pipelines" / "snapshots" / "rules_t3.py", raiz / "pipelines" / "snapshots" / "features_t3.py"):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def modelos_de(k: int) -> List[str]:
    base = ["km_global", "km_programa", "cox_adm", "dt_lr_adm", "dt_cb_adm", "nn_mlp_adm"]
    return base if k == 0 else ["km_global", "km_programa", "cox_adm", "cox_agg", "dt_lr_adm", "dt_lr_agg",
                                "dt_cb_adm", "dt_cb_agg", "nn_mlp_adm", "nn_mlp_agg", "nn_gru"]


def ibs_valid(F: np.ndarray, d: pd.DataFrame, k: int) -> float:
    grid = np.arange(k + 1, M3.IBS_HASTA + 1)
    return M3.ibs(d["tiempo"].to_numpy(), d["causa"].to_numpy(), d["seguimiento_max"].to_numpy(), F[:, : len(grid)], grid)


# ---------------------------------------------------------------------------------------------
# training of one cut
# ---------------------------------------------------------------------------------------------
def entrenar_k(snap: pd.DataFrame, sem: pd.DataFrame, k: int, seeds, log, solo=None) -> Dict:
    import torch

    parts = TD.particion(snap, k)
    tr, va = parts["train"], parts["valid"]
    U = TD.JMAX - k
    preds: Dict[str, Dict[str, np.ndarray]] = {s: {} for s in EVAL_SPLITS}
    tiempos: Dict[str, float] = {}
    info: Dict[str, Dict] = {}
    por_semilla: Dict[str, List] = {}
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def quiere(n):
        return n in modelos_de(k) and (solo is None or n in solo)

    def guardar(nombre, fn):
        for s in EVAL_SPLITS:
            preds[s][nombre] = fn(parts[s])

    # 1 Aalen-Johansen
    for nombre, por_prog in (("km_global", False), ("km_programa", True)):
        if quiere(nombre):
            t0 = time.perf_counter()
            m = SV.AJPrograma(U, programa=por_prog).fit(tr)
            guardar(nombre, m.predict)
            tiempos[nombre] = time.perf_counter() - t0
            info[nombre] = {"programas_con_curva_propia": len(getattr(m, "tabla", {})), "min_n": SV.MIN_N_PROGRAMA}
            log(f"k={k} {nombre}: {tiempos[nombre]:.1f} s")

    preps = {}
    for g in ("adm", "adm+agg"):
        if k == 0 and g == "adm+agg":
            continue
        num, cat = TD.GRUPOS[g]
        TD.verificar_sin_fuga(num, cat)
        preps[g] = Preprocesador(num, cat).fit(tr)

    sufijo = {"adm": "adm", "adm+agg": "agg"}
    for g, prep in preps.items():
        suf = sufijo[g]
        # 2 Cox
        if quiere(f"cox_{suf}"):
            t0 = time.perf_counter()
            Xtr, Xva = prep.transform(tr), prep.transform(va)
            mejor = None
            busqueda = []
            for pen in GRID_PENALIZADOR:
                m = SV.CoxCausaEspecifica(U, pen).fit(Xtr, tr["u"].to_numpy(), tr["causa"].to_numpy())
                ib = ibs_valid(m.predict(Xva), va, k)
                busqueda.append({"penalizador": pen, "ibs_valid": ib})
                if mejor is None or ib < mejor[0]:
                    mejor = (ib, m, pen)
            m = mejor[1]
            guardar(f"cox_{suf}", lambda d: m.predict(prep.transform(d)))
            tiempos[f"cox_{suf}"] = time.perf_counter() - t0
            info[f"cox_{suf}"] = {"penalizador": mejor[2], "ibs_valid": mejor[0], "n_variables": m.n_variables(),
                                  "busqueda": busqueda}
            log(f"k={k} cox_{suf}: penalizador={mejor[2]} IBS valid={mejor[0]:.4f} ({tiempos[f'cox_{suf}']:.0f} s)")
            del Xtr, Xva
        # 3a person-period logistic
        if quiere(f"dt_lr_{suf}"):
            t0 = time.perf_counter()
            m, inf = DT.logistica_ajustar(prep, tr, va, k)
            guardar(f"dt_lr_{suf}", lambda d: DT.logistica_cif(m, prep, d, k))
            tiempos[f"dt_lr_{suf}"] = time.perf_counter() - t0
            info[f"dt_lr_{suf}"] = dict(inf)
            log(f"k={k} dt_lr_{suf}: C={inf['C']} logloss valid={inf['logloss_valid']:.4f} ({tiempos[f'dt_lr_{suf}']:.0f} s)")
        # 3b person-period CatBoost (3 seeds)
        if quiere(f"dt_cb_{suf}"):
            t0 = time.perf_counter()
            ms, its = [], []
            for s in seeds:
                m, inf = DT.catboost_ajustar(prep, tr, va, k, s)
                ms.append(m), its.append(inf["mejor_iteracion"])
            guardar(f"dt_cb_{suf}", lambda d: DT.catboost_cif(ms, prep, d, k))
            tiempos[f"dt_cb_{suf}"] = time.perf_counter() - t0
            info[f"dt_cb_{suf}"] = {"mejores_iteraciones": its, "n_variables": len(prep.num_cols) + len(prep.cat_cols) + 2,
                                    "params": {kk: str(v) for kk, v in DT.CB_PARAMS.items()}}
            if suf == "agg" or k == 0:
                imp = pd.Series(np.mean([c.get_feature_importance() for c in ms], axis=0),
                                index=list(prep.num_cols) + list(prep.cat_cols) + ["slot", "slot_rel_nominal"])
                info[f"dt_cb_{suf}"]["importancia_top15"] = {a: float(b) for a, b in imp.sort_values(ascending=False).head(15).items()}
            log(f"k={k} dt_cb_{suf}: iteraciones={its} ({tiempos[f'dt_cb_{suf}']:.0f} s)")
            del ms

    # 4 neural networks
    secuencias = {}
    if k > 0:
        for s, d in parts.items():
            secuencias[s] = TD.construir_secuencias_t3(d, sem, k)
    for nombre, g, con_seq in (("nn_mlp_adm", "adm", False), ("nn_mlp_agg", "adm+agg", False), ("nn_gru", "adm+agg", True)):
        if not quiere(nombre) or g not in preps:
            continue
        prep = preps[g]

        def conj(d, s):
            return NR.ConjuntoT3(prep.transform_num(d), prep.transform_cat_codes(d), d["u"].to_numpy(),
                                 d["causa"].to_numpy(), secuencias[s] if con_seq else None)

        ctr, cva = conj(tr, "train"), conj(va, "valid")
        cjs = {s: conj(parts[s], s) for s in EVAL_SPLITS}
        pv = {s: [] for s in EVAL_SPLITS}
        runs, ind = [], []
        for s in seeds:
            r = NR.entrenar(ctr, cva, prep.cardinalidades(), U, s, dev)
            fs = {sp: NR.predecir_cif(r["model"], cjs[sp], dev) for sp in EVAL_SPLITS}
            for sp in EVAL_SPLITS:
                pv[sp].append(fs[sp])
            ind.append({sp: M3.Evaluador(parts[sp]["tiempo"], parts[sp]["causa"], parts[sp]["seguimiento_max"],
                                         np.arange(k + 1, TD.JMAX + 1), {"m": fs[sp]}, HORIZONTES[sp],
                                         IBS_HASTA[sp]).metricas(np.arange(len(parts[sp])))["m"]
                        for sp in ("valid", "test")})
            runs.append({kk: v for kk, v in r.items() if kk != "model"})
            log(f"k={k} {nombre} seed={s}: NLL valid={r['nll_valid']:.4f} epoca={r['mejor_epoca']} "
                f"{r['segundos']:.0f} s gpu={r['gpu_pico_mb']:.0f} MB")
            del r
        for sp in EVAL_SPLITS:
            preds[sp][nombre] = np.mean(pv[sp], axis=0)
        por_semilla[nombre] = ind
        tiempos[nombre] = float(sum(r["segundos"] for r in runs))
        info[nombre] = {"semillas": runs, "gpu_pico_mb": max(r["gpu_pico_mb"] for r in runs), "hidden": list(NR.HIDDEN),
                        "batch": NR.BATCH, "lr": NR.LR, "weight_decay": NR.WD, "paciencia": NR.PACIENCIA,
                        "gru_hidden": NR.GRU_HIDDEN if con_seq else None}
    return {"parts": parts, "preds": preds, "tiempos": tiempos, "info": info, "por_semilla": por_semilla}


# ---------------------------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------------------------
def pares_t3(k: int, mejor_clasico: str, modelos: List[str]) -> List:
    pares = [("km_programa", "km_global"), ("cox_adm", "km_programa"), ("cox_agg", "cox_adm"), ("dt_lr_adm", "cox_adm"),
             ("dt_lr_agg", "cox_agg"), ("dt_lr_agg", "dt_lr_adm"), ("dt_cb_adm", "dt_lr_adm"), ("dt_cb_agg", "dt_lr_agg"),
             ("dt_cb_agg", "dt_cb_adm"), ("dt_cb_agg", "cox_agg"), ("nn_mlp_adm", "dt_cb_adm"), ("nn_mlp_adm", "dt_lr_adm"),
             ("nn_mlp_agg", "nn_mlp_adm"), ("nn_mlp_agg", "dt_cb_agg"), ("nn_gru", "nn_mlp_agg"), ("nn_gru", "dt_cb_agg"),
             ("nn_mlp_adm", "cox_adm"), ("nn_mlp_agg", "dt_lr_agg"), ("nn_mlp_agg", "cox_agg"), ("nn_gru", "cox_agg"),
             ("dt_lr_adm", "km_programa"), ("dt_cb_adm", "km_programa"), ("cox_adm", "km_global"),
             ("nn_mlp_agg", mejor_clasico), ("nn_gru", mejor_clasico), ("nn_mlp_adm", mejor_clasico),
             (mejor_clasico, "km_global"), (mejor_clasico, "km_programa")]
    return [(a, b) for a, b in dict.fromkeys(pares) if a in modelos and b in modelos and a != b]


def tabla_subgrupo(d: pd.DataFrame, F: np.ndarray, k: int, tau: int, col, n_min: int) -> List[Dict]:
    """Per group, among the episodes followed up to ``tau``: n, observed and predicted incidence, calibration gap, AUC."""
    el, y = M3.resultado_horizonte(d["tiempo"], d["causa"], d["seguimiento_max"], tau)
    f = F[:, tau - k - 1]
    valores = col(d) if callable(col) else d[col].astype(object).where(d[col].notna(), "sin_dato").astype(str)
    valores = pd.Series(np.asarray(valores, dtype=object), index=d.index)
    rows = []
    for valor, idx in valores[el].groupby(valores[el]).indices.items():
        yy, ff = y[el][idx], f[el][idx]
        if len(idx) < n_min:
            continue
        rows.append({"grupo": str(valor), "n": int(len(idx)), "incidencia_observada": float(yy.mean()),
                     "incidencia_predicha": float(ff.mean()), "brecha_calibracion": float(ff.mean() - yy.mean()),
                     "auc": M3.auc(yy, ff)})
    return sorted(rows, key=lambda r: r["grupo"])


def subgrupos(d: pd.DataFrame, F: np.ndarray, k: int, tau: int = 12) -> Dict[str, List[Dict]]:
    dur = d["duracion_nominal"].map(lambda v: "sin_dato" if pd.isna(v) else "<=8" if v <= 8 else "10" if v == 10 else ">=12")
    return {
        "programa": tabla_subgrupo(d, F, k, tau, "cod_programa", MIN_PROGRAMA_SUBGRUPO),
        "programa_n150": tabla_subgrupo(d, F, k, tau, "cod_programa", PROGRAMAS_MIN_ALT),
        "via": tabla_subgrupo(d, F, k, tau, "via_clase", 100),
        "sexo": tabla_subgrupo(d, F, k, tau, "sexo_equidad", 100),
        "duracion_nominal": tabla_subgrupo(d, F, k, tau, lambda x: dur, 100),
        "cohorte": tabla_subgrupo(d, F, k, tau, lambda x: x["cohorte_anio"].astype(str), 100),
        # D47: trajectories admitted to Ingenieria Civil Plan Comun (merged with their specialty) against the rest; n >= 10
        "plan_comun": tabla_subgrupo(d, F, k, tau, lambda x: x["trayectoria_plan_comun"].map(
            {True: "plan_comun", False: "otras_trayectorias"}), 10),
    }


def evaluar_k(res: Dict, k: int, boot: int, log, device: Optional[str]) -> Dict:
    parts, preds = res["parts"], res["preds"]
    slots = np.arange(k + 1, TD.JMAX + 1)
    va = parts["valid"]
    ibs_v = {m: ibs_valid(F, va, k) for m, F in preds["valid"].items()}
    cla = {m: v for m, v in ibs_v.items() if m in CLASICOS}
    mejor = min(cla, key=cla.get)
    pares = pares_t3(k, mejor, list(preds["valid"]))
    out: Dict = {"mejor_clasico_valid": mejor, "ibs_valid": ibs_v, "pares": [list(p) for p in pares]}
    backend = "torch" if device else "numpy"
    for sp in EVAL_SPLITS:
        d = parts[sp]
        ev = M3.Evaluador(d["tiempo"], d["causa"], d["seguimiento_max"], slots, preds[sp], HORIZONTES[sp],
                          IBS_HASTA[sp], backend=backend, device=device)
        nb = boot if sp != "posterior" else min(boot, 300)
        t0 = time.perf_counter()
        out[sp] = ev.bootstrap(n_boot=nb, seed=7, pares=pares)
        out[sp]["__n"] = int(len(d))
        out[sp]["__elegibles"] = {str(h): int((d["seguimiento_max"] >= h).sum()) for h in HORIZONTES[sp]}
        log(f"k={k} bootstrap {sp}: {nb} remuestreos, {time.perf_counter() - t0:.0f} s")
    te = parts["test"]
    claves = [m for m in dict.fromkeys(["km_global", "km_programa", "cox_adm", "cox_agg", mejor, "dt_cb_adm", "dt_cb_agg",
                                        "nn_mlp_agg", "nn_gru"]) if m in preds["test"]]
    out["calibracion_test"] = {str(tau): {m: M3.calibracion_horizonte(te["tiempo"], te["causa"], te["seguimiento_max"],
                                                                     preds["test"][m][:, tau - k - 1], tau)
                                          for m in claves} for tau in (10, 12)}
    out["subgrupos_test"] = {m: subgrupos(te, preds["test"][m], k) for m in claves}
    out["modelos_subgrupo"] = claves
    # observed vs predicted mean incidence per horizon (test)
    out["incidencia_media_test"] = {}
    for tau in HORIZONTES["test"]:
        el, y = M3.resultado_horizonte(te["tiempo"], te["causa"], te["seguimiento_max"], tau)
        out["incidencia_media_test"][str(tau)] = {
            "n": int(el.sum()), "observada": float(y[el].mean()),
            **{m: float(preds["test"][m][el, tau - k - 1].mean()) for m in claves}}
    return out


# ---------------------------------------------------------------------------------------------
# descriptive
# ---------------------------------------------------------------------------------------------
def descriptivo(snap: pd.DataFrame) -> Dict:
    out: Dict = {"por_k_split": {}, "por_cohorte": {}, "incidencia_comparada": {}, "salida": {}, "duracion_nominal": {}}
    for k in KS:
        d = snap[snap["k"] == k]
        out["por_k_split"][str(k)] = {}
        for s in TD.SPLITS:
            x = d[d["split"] == s]
            if not len(x):
                continue
            out["por_k_split"][str(k)][s] = {
                "n": int(len(x)), "egreso": int((x["causa"] == 1).sum()), "salida": int((x["causa"] == 2).sum()),
                "censura": int((x["causa"] == 0).sum()), "seguimiento_min": int(x["seguimiento_max"].min()),
                "seguimiento_max": int(x["seguimiento_max"].max()), "tiempo_mediano_egreso": float(x.loc[x["causa"] == 1, "tiempo"].median()) if (x["causa"] == 1).any() else None}
    out["plan_comun"] = descriptivo_plan_comun(snap)
    d2 = snap[snap["k"] == 2]
    for a, x in d2.groupby("cohorte_anio"):
        out["por_cohorte"][str(a)] = {"n": int(len(x)), "egreso": float((x["causa"] == 1).mean()),
                                      "salida": float((x["causa"] == 2).mean()), "censura": float((x["causa"] == 0).mean()),
                                      "seguimiento_mediano": float(x["seguimiento_max"].median())}
    # Aalen-Johansen vs the naive 1 - KM, from the admission (k = 0), by split
    d0 = snap[snap["k"] == 0]
    for s in ("train", "valid", "test"):
        x = d0[d0["split"] == s]
        grid = np.arange(4, int(min(x["seguimiento_max"].max(), 18)) + 1, 2)
        aj = M3.aalen_johansen(x["tiempo"].to_numpy(), x["causa"].to_numpy(), grid)
        ing = M3.incidencia_ingenua(x["tiempo"].to_numpy(), x["causa"].to_numpy(), grid)
        out["incidencia_comparada"][s] = {"slots": grid.tolist(), "F1": aj["F1"].tolist(), "F2": aj["F2"].tolist(),
                                          "ingenua": ing.tolist(), "n": int(len(x))}
    for s in ("train", "valid", "test", "posterior"):
        x = d2[(d2["split"] == s) & (d2["causa"] == 2)]
        if len(x):
            out["salida"][s] = {"n": int(len(x)), "explicita": int((x["salida_tipo"] == "explicita").sum()),
                                "ausencia": int((x["salida_tipo"] == "ausencia").sum()),
                                "a_otro_programa_explicita": int(((x["salida_tipo"] == "explicita") & (x["salida_a_otro_programa"] == True)).sum()),   # noqa: E712
                                "a_otro_programa_ausencia": int(((x["salida_tipo"] == "ausencia") & (x["salida_a_otro_programa"] == True)).sum())}  # noqa: E712
    x = d2[d2["split"].isin(["train", "valid", "test"])]
    g = x.groupby(x["duracion_nominal"].fillna(-1))
    out["duracion_nominal"] = {str(int(a)): {"n": int(len(v)), "egreso": float((v["causa"] == 1).mean()),
                                            "salida": float((v["causa"] == 2).mean())} for a, v in g}
    return out


def descriptivo_plan_comun(snap: pd.DataFrame) -> Dict:
    """Outcomes of the Plan Comun trajectories per cut and split, linked to a specialty or not (D47; aggregates only)."""
    out: Dict = {}
    for k in KS:
        d = snap[(snap["k"] == k) & snap["trayectoria_plan_comun"].astype(bool)]
        out[str(k)] = {}
        for s in TD.SPLITS:
            x = d[d["split"] == s]
            if not len(x):
                continue
            out[str(k)][s] = {}
            for grupo, y in (("unidas", x[x["episodio_especialidad_id"].notna()]),
                             ("sin_continuacion", x[x["episodio_especialidad_id"].isna()])):
                out[str(k)][s][grupo] = {
                    "n": int(len(y)), "egreso": int((y["causa"] == 1).sum()), "salida": int((y["causa"] == 2).sum()),
                    "censura": int((y["causa"] == 0).sum()),
                    "tiempo_mediano_egreso": float(y.loc[y["causa"] == 1, "tiempo"].median()) if (y["causa"] == 1).any() else None}
    return out


def consistencia(conn) -> Dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT clave, valor FROM neural_mart.snapshot_t3_resumen WHERE clave LIKE 'consistencia_%' ORDER BY 1")
        return {c.replace("consistencia_", ""): v for c, v in cur.fetchall()}


def guardar_preds(parts, preds, k):
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    for sp in EVAL_SPLITS:
        np.savez_compressed(S.ARTEFACTOS / "preds" / f"t3_k{k}_{sp}.npz", episodio_id=parts[sp]["episodio_id"].to_numpy(),
                            **{n: p.astype("float32") for n, p in preds[sp].items()})


def registrar_mlflow(k: int, res: Dict, ev: Dict, snapshot_hash: str, etiqueta: str) -> None:
    mlflow = S.iniciar_mlflow()
    mlflow.set_experiment(EXPERIMENTO_T3)
    codigo = version_codigo_t3()
    for nombre in res["preds"]["test"]:
        met = {}
        for sp in EVAL_SPLITS:
            for m_, v in ev[sp][nombre].items():
                met[f"{sp}_{m_}"] = v["punto"]
                met[f"{sp}_{m_}_lo"], met[f"{sp}_{m_}_hi"] = v["lo"], v["hi"]
        met["segundos_entrenamiento"] = res["tiempos"].get(nombre, 0.0)
        params = {"modelo": nombre, "k": k, "n_train": len(res["parts"]["train"]), "n_valid": len(res["parts"]["valid"]),
                  "n_test": len(res["parts"]["test"]),
                  **{kk: json.dumps(v)[:240] for kk, v in res["info"].get(nombre, {}).items() if kk not in ("semillas", "busqueda")}}
        S.registrar(mlflow, f"{etiqueta}_k{k}_{nombre}", params, met,
                    {"hash_snapshot": snapshot_hash, "version_codigo": codigo, "tarea": "T3", "evento": "egreso_titulacion"})


def parsear(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train and evaluate the T3 benchmark.")
    ap.add_argument("--k", type=int, nargs="*", default=list(KS))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--salida", default="resultados_t3")
    ap.add_argument("--solo", nargs="*", default=None, help="subset of models (development only)")
    ap.add_argument("--sin-gpu-bootstrap", action="store_true", help="evaluate the bootstrap on the CPU")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    try:
        import torch
        from pipelines.common.db import dev_connection

        t_ini = time.perf_counter()
        with dev_connection() as conn:
            snap, sem = TD.cargar(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t3_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
                cur.execute("SELECT clave, valor FROM neural_mart.snapshot_t3_resumen WHERE clave LIKE 'embudo_%' ORDER BY 1")
                embudo_raw = dict(cur.fetchall())
                cur.execute("SELECT valor FROM neural_mart.snapshot_t3_resumen WHERE clave = 'periodo_cierre'")
                cierre = cur.fetchone()[0]
            cons = consistencia(conn)
        print(f"snapshot cargado: {len(snap):,} filas, RAM pico {ram_pico_mb()} MB", flush=True)
        device = None if args.sin_gpu_bootstrap or not torch.cuda.is_available() else "cuda"
        out = {"snapshot_hash": snapshot_hash, "version_codigo": version_codigo_t3(), "periodo_cierre": cierre,
               "embudo": embudo_raw, "consistencia": cons, "descriptivo": descriptivo(snap), "por_k": {},
               "tiempos_s": {}, "info": {}, "semillas": {}, "ks": args.k}
        for k in args.k:
            res = entrenar_k(snap, sem, k, SEMILLAS[: args.seeds], lambda m: print(m, flush=True), args.solo)
            ev = evaluar_k(res, k, args.boot, lambda m: print(m, flush=True), device)
            out["por_k"][str(k)] = ev
            out["tiempos_s"][str(k)], out["info"][str(k)], out["semillas"][str(k)] = res["tiempos"], res["info"], res["por_semilla"]
            out["por_k"][str(k)]["n_split"] = {s: int(len(res["parts"][s])) for s in TD.SPLITS}
            guardar_preds(res["parts"], res["preds"], k)
            if not args.solo:
                registrar_mlflow(k, res, ev, snapshot_hash, args.salida)
            del res
        out["ram_pico_mb"] = ram_pico_mb()
        out["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        out["segundos_totales"] = time.perf_counter() - t_ini
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / f"{args.salida}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print(f"escrito artefactos/{args.salida}.json ({out['segundos_totales']:.0f} s, RAM pico {out['ram_pico_mb']} MB)")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
