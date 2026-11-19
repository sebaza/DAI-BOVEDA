"""Ablation "+ beneficios" of T1 and its k = 4 extension (16-11-2026, decisions D90-D95; docs/08_benchmark_t1.md).

``python -m evaluation.run_beneficios_t1`` keeps the models, seeds, splits and the official training window of
``run_benchmark.py`` (CatBoost with 3 seeds and the logistic regression) and adds, on top of the best feature set
(``pre_entry+academico``), the step "+ beneficios" (and, at k = 4, "+ perdidas"). Everything is evaluated with the bootstrap
grouped by person, with paired differences on the SAME resamples. Selection happens on valid:

* a benefit model competes only if its paired AP gain over the same model without benefits has an interval above zero on valid;
* at k = 1 no benefit model competes: the cut is in the middle of the year and the benefit rows of the final view are not the
  rows that existed at the cut (late rows, rows removed for people who leave; ``diagnostico_beneficios.py``). The k = 1 numbers
  are reported as a sensitivity, with and without the students who leave during the admission year.

Writes AGGREGATES to ``artefactos/resultados_t1_beneficios.json`` (gitignored); no individual row or prediction.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from models import baseline, catboost_modelo, data as D, logistica, seguimiento as S
from pipelines.snapshots import features_beneficios as FB
from pipelines.snapshots.rules import TRAIN_DESDE_OFICIAL
from . import facultades as FA
from . import grupos_t45 as GR
from . import metrics as M
from . import metrics_t45 as M45
from . import subgrupos as SG

SEMILLAS = (0, 1, 2)
KS = (1, 2, 4)
SIN_CERTIFICAR = (1,)                      # k at which no benefit model can be selected (mid-year cut)
MUESTRA_SHAP = 4000
TOP_IMPORTANCIA = 15
CONJUNTOS = {"acad": D.GRUPOS["pre_entry+academico"],
             "ben": D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios"],
             "ben_perd": D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios+perdidas"]}
BEN_VARIABLES = set(D.BEN_NUM) | set(D.BEN_CAT) | set(D.PERDIDA_NUM)


# ---------------------------------------------------------------------------------------------------- pure helpers
def conjuntos_de(k: int) -> List[str]:
    return ["acad", "ben", "ben_perd"] if k in FB.RB.K_PERDIDA else ["acad", "ben"]


def _lo(ev: Dict, clave: str) -> Optional[float]:
    return ev[clave]["ap"]["lo"] if clave in ev else None


def elegibles(k: int, nombres: Sequence[str], ev_valid: Dict) -> List[str]:
    """Models that may be selected on valid (see the module docstring)."""
    out = []
    for m in nombres:
        familia, _, tag = m.partition("_")
        if tag == "acad":
            out.append(m)
        elif tag == "ben":
            lo = _lo(ev_valid, f"{m}__vs__{familia}_acad")
            if k not in SIN_CERTIFICAR and lo is not None and lo > 0:
                out.append(m)
        elif tag == "ben_perd":
            lo = _lo(ev_valid, f"{m}__vs__{familia}_ben")
            if f"{familia}_ben" in out and lo is not None and lo > 0:
                out.append(m)
    return out


def elegir(ap_valid: Dict[str, float], candidatos: Sequence[str]) -> str:
    return max(candidatos, key=lambda m: ap_valid[m])


def sale_en_el_anio(snap: pd.DataFrame, sem: pd.DataFrame) -> pd.Series:
    """True for a k = 1 row of a first-semester admission whose episode is not enrolled in the second semester (slot 2)."""
    mat2 = sem.loc[sem["j"] == 2].drop_duplicates("episodio_id").set_index("episodio_id")["matriculado"].astype(bool)
    no_mat = ~snap["episodio_id"].map(mat2).fillna(True).astype(bool)
    return (snap["k"] == 1) & (snap["periodo_admision"].str.slice(4, 6) == "10") & no_mat


def tabla_importancia(nombres: Sequence[str], imp: np.ndarray, shap: np.ndarray, top: int = TOP_IMPORTANCIA) -> Dict:
    """Aggregate importance (CatBoost PredictionValuesChange, in %) and mean |SHAP| per variable; top list plus every benefit
    variable (whatever its rank)."""
    imp = np.asarray(imp, dtype="float64")
    pct = 100.0 * imp / imp.sum() if imp.sum() > 0 else imp
    orden = np.argsort(-imp, kind="stable")
    filas = [{"variable": nombres[i], "importancia": float(imp[i]), "importancia_pct": float(pct[i]),
              "shap_medio_abs": float(shap[i]), "rango": r + 1} for r, i in enumerate(orden)]
    return {"top": filas[:top], "beneficios": [f for f in filas if f["variable"] in BEN_VARIABLES],
            "suma_pct_beneficios": float(sum(f["importancia_pct"] for f in filas if f["variable"] in BEN_VARIABLES))}


# ---------------------------------------------------------------------------------------------------- training
def ajustar_conjunto(tr, va, te, num, cat, semillas, guardar_modelos: bool):
    """Logistic regression (C tuned on valid) and CatBoost (seed ensemble) on one feature set."""
    prep = D.Preprocesador(num, cat).fit(tr)
    t0 = time.perf_counter()
    Xtr, Xva, Xte = (prep.transform(x) for x in (tr, va, te))
    lr, inf = logistica.ajustar(Xtr, tr["y"].to_numpy(), Xva, va["y"].to_numpy())
    out = {"lr": (lr.predict_proba(Xva)[:, 1], lr.predict_proba(Xte)[:, 1]),
           "info_lr": {"C": inf["C"], "ap_valid": inf["ap_valid"], "n_variables": int(Xtr.shape[1])},
           "seg_lr": time.perf_counter() - t0}
    t0 = time.perf_counter()
    Ctr, Cva, Cte = (prep.transform_catboost(x) for x in (tr, va, te))
    pv, pt, its, modelos = [], [], [], []
    for s in semillas:
        cb, cinf = catboost_modelo.ajustar(Ctr, tr["y"], Cva, va["y"], cat, seed=s)
        pv.append(catboost_modelo.predecir(cb, Cva, cat)), pt.append(catboost_modelo.predecir(cb, Cte, cat))
        its.append(cinf["mejor_iteracion"])
        modelos.append(cb)
    out["cb"] = (np.mean(pv, axis=0), np.mean(pt, axis=0))
    out["info_cb"] = {"mejores_iteraciones": its, "n_variables": len(num) + len(cat)}
    out["seg_cb"] = time.perf_counter() - t0
    if guardar_modelos:
        out["modelos_cb"], out["Cte"], out["cat"] = modelos, Cte, list(cat)
    return out


def importancia_catboost(modelos, Cte: pd.DataFrame, cat: Sequence[str]) -> Dict:
    """Mean over seeds of the CatBoost importance and of the mean |SHAP| on a seeded sample of the test rows."""
    from catboost import Pool

    muestra = Cte.sample(n=min(MUESTRA_SHAP, len(Cte)), random_state=0)
    nombres = list(modelos[0].feature_names_)
    imp = np.mean([m.get_feature_importance() for m in modelos], axis=0)
    shap = np.mean([np.abs(m.get_feature_importance(Pool(muestra, cat_features=list(cat)), type="ShapValues")[:, :-1]).mean(axis=0)
                    for m in modelos], axis=0)
    return {**tabla_importancia(nombres, imp, shap), "n_muestra_shap": int(len(muestra)), "semillas": len(modelos)}


# ---------------------------------------------------------------------------------------------------- evaluation
def entrenar_k(snap, sem, k, train_desde, semillas, n_boot, log, programas=None, completo=True, sin_salidas=False):
    df = D.seleccionar_modelado(snap, k=k, train_desde=train_desde)
    if sin_salidas:
        df = df.loc[~df["sale_anio"]].reset_index(drop=True)
    tr, va, te = (df[df["split"] == s].reset_index(drop=True) for s in D.SPLITS)
    preds: Dict[str, Dict[str, np.ndarray]] = {"valid": {}, "test": {}}
    infos: Dict = {}
    tiempos: Dict[str, float] = {}
    b = baseline.TasaHistorica().fit(tr)
    preds["valid"]["baseline_tasa"], preds["test"]["baseline_tasa"] = b.predict(va), b.predict(te)
    importancia: Dict = {}
    for tag in conjuntos_de(k):
        num, cat = CONJUNTOS[tag]
        r = ajustar_conjunto(tr, va, te, num, cat, semillas, guardar_modelos=completo and tag != "acad")
        for fam in ("lr", "cb"):
            preds["valid"][f"{fam}_{tag}"], preds["test"][f"{fam}_{tag}"] = r[fam]
            infos[f"{fam}_{tag}"] = r[f"info_{fam}"]
            tiempos[f"{fam}_{tag}"] = r[f"seg_{fam}"]
        if "modelos_cb" in r:
            importancia[f"cb_{tag}"] = importancia_catboost(r["modelos_cb"], r["Cte"], r["cat"])
        log(f"k={k} train>={train_desde} {tag}: AP valid lr={M.metricas(va['y'].to_numpy(), r['lr'][0])['ap']:.4f} "
            f"cb={M.metricas(va['y'].to_numpy(), r['cb'][0])['ap']:.4f}")
    nombres = [n for n in preds["test"] if n != "baseline_tasa"]
    pares = []
    for fam in ("lr", "cb"):
        pares += [(f"{fam}_ben", f"{fam}_acad")]
        if k in FB.RB.K_PERDIDA:
            pares += [(f"{fam}_ben_perd", f"{fam}_ben"), (f"{fam}_ben_perd", f"{fam}_acad")]
    pares += [(f"{fam}_acad", "baseline_tasa") for fam in ("lr", "cb")] + [("cb_ben", "lr_acad")]
    yva, yte = va["y"].to_numpy(), te["y"].to_numpy()
    idx_va = M45.remuestreos(va["persona_key"].to_numpy(), n_boot, seed=5)
    idx_te = M45.remuestreos(te["persona_key"].to_numpy(), n_boot, seed=7)
    ev_valid = M45.bootstrap_agrupado(yva, preds["valid"], idx_va, pares)
    ev_test = M45.bootstrap_agrupado(yte, preds["test"], idx_te, pares)
    ap_valid = {m: ev_valid[m]["ap"]["punto"] for m in preds["valid"]}
    el = elegibles(k, nombres, ev_valid)
    conservado = elegir(ap_valid, el)
    res: Dict = {"k": k, "train_desde": train_desde, "sin_salidas_en_el_anio": sin_salidas,
                 "n": {s: {"n": int(len(d)), "eventos": int(d["y"].sum()), "tasa": float(d["y"].mean()),
                           "personas": int(d["persona_key"].nunique())} for s, d in zip(D.SPLITS, (tr, va, te))},
                 "valid": ev_valid, "test": ev_test,
                 "seleccion": {"elegibles": el, "conservado": conservado, "ap_valid": ap_valid,
                               "base": "cb_acad", "regla": "ap_valid_maximo_entre_elegibles",
                               "beneficios_certificables": k not in SIN_CERTIFICAR},
                 "info": infos, "tiempos_s": tiempos, "hash_datos": S.hash_datos(df, ["episodio_id", "k", "y", "split"])}
    log(f"k={k} train>={train_desde} sin_salidas={sin_salidas}: elegibles={el} conservado={conservado}")
    if not completo:
        return res
    p_c, p_b = preds["test"][conservado], preds["test"]["baseline_tasa"]
    fac = FA.facultad_de(te["cod_programa"], programas)
    te = te.assign(facultad=fac)
    sub = {}
    for m, p in preds["test"].items():
        t = dict(SG.todos(te, yte, p))
        t["facultad"] = SG.tabla_grupo(te, yte, p, "facultad", SG.N_MIN_PROGRAMA)
        t["banda_decil"] = SG.tabla_grupo(te, yte, p, "banda_decil", SG.N_MIN_GRUPO)
        sub[m] = t
    grupos = {"programa": GR.tabla_agregada(te["cod_programa"].to_numpy(), yte, p_c, p_b, idx_te),
              "facultad": GR.tabla_agregada(fac.to_numpy(), yte, p_c, p_b, idx_te)}
    for fila in grupos["programa"]["filas"]:
        if fila["grupo"] in programas.index:
            fila["nombre"] = str(programas.loc[fila["grupo"], "nombre_programa"])
    res.update({
        "calibracion_test": {m: M.tabla_confiabilidad(yte, p) for m, p in preds["test"].items()},
        "subgrupos_test": sub, "brecha_sexo_test": {m: SG.brechas_sexo(t["sexo"]) for m, t in sub.items()},
        "grupos": grupos, "importancia": importancia,
        "equidad": {"conservado": conservado, "base": "cb_acad",
                    "sexo": {m: SG.tabla_grupo(te, yte, preds["test"][m], "sexo_equidad", SG.N_MIN_GRUPO) for m in (conservado, "cb_acad")},
                    "banda_decil": {m: SG.tabla_grupo(te, yte, preds["test"][m], "banda_decil", SG.N_MIN_GRUPO)
                                    for m in (conservado, "cb_acad")}},
    })
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(S.ARTEFACTOS / "preds" / f"t1_beneficios_k{k}_desde{train_desde}.npz",
                        episodio_valid=va["episodio_id"].to_numpy(), episodio_test=te["episodio_id"].to_numpy(),
                        **{f"valid__{n}": p for n, p in preds["valid"].items()},
                        **{f"test__{n}": p for n, p in preds["test"].items()})
    return res


def evaluar_sin_salidas_test(snap, k, train_desde, semillas, n_boot, log):
    """Sensitivity of k = 1: the same ablation without the students who leave during the admission year (train, valid, test)."""
    return entrenar_k(snap, None, k, train_desde, semillas, n_boot, log, completo=False, sin_salidas=True)


def registrar_mlflow(res: Dict, snapshot_hash: str, etiqueta: str) -> None:
    mlflow = S.iniciar_mlflow()
    codigo = S.version_codigo()
    k = res["k"]
    for nombre in res["test"]:
        if "__vs__" in nombre:
            continue
        met = {}
        for split in ("valid", "test"):
            for m_, v in res[split][nombre].items():
                met[f"{split}_{m_}"] = v["punto"]
                met[f"{split}_{m_}_lo"], met[f"{split}_{m_}_hi"] = v["lo"], v["hi"]
        params = {"k": k, "modelo": nombre, "train_desde": res["train_desde"], "n_train": res["n"]["train"]["n"],
                  "n_valid": res["n"]["valid"]["n"], "n_test": res["n"]["test"]["n"]}
        S.registrar(mlflow, f"{etiqueta}_k{k}_{nombre}", params, met,
                    {"hash_datos": res["hash_datos"], "hash_snapshot": snapshot_hash, "version_codigo": codigo,
                     "tarea": "T1", "evento": "no_continua", "analisis": "beneficios"})


def parsear(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="T1 ablation with student benefits (+ k = 4 extension).")
    ap.add_argument("--k", type=int, nargs="+", default=list(KS))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--train-desde", type=int, default=TRAIN_DESDE_OFICIAL)
    ap.add_argument("--sin-sensibilidades", action="store_true")
    ap.add_argument("--salida", default="resultados_t1_beneficios")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    log = lambda m: print(m, flush=True)   # noqa: E731
    try:
        from pipelines.common.db import dev_connection

        with dev_connection() as conn:
            snap, sem = D.cargar_desde_db(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t1_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
            programas = FA.cargar_programas(conn)
        snap["sale_anio"] = sale_en_el_anio(snap, sem)
        semillas = SEMILLAS[: args.seeds]
        out: Dict = {"snapshot_hash": snapshot_hash, "version_codigo": S.version_codigo(), "resultados": {},
                     "sensibilidad": {"desde_2017": {}, "sin_salidas_en_el_anio": {}}}
        for k in args.k:
            res = entrenar_k(snap, sem, k, args.train_desde, semillas, args.boot, log, programas)
            registrar_mlflow(res, snapshot_hash, args.salida)
            out["resultados"][f"k{k}"] = res
            if not args.sin_sensibilidades:
                out["sensibilidad"]["desde_2017"][f"k{k}"] = entrenar_k(snap, sem, k, 2017, semillas, args.boot, log, completo=False)
                if k in SIN_CERTIFICAR:
                    out["sensibilidad"]["sin_salidas_en_el_anio"][f"k{k}"] = evaluar_sin_salidas_test(
                        snap, k, args.train_desde, semillas, args.boot, log)
            S.ARTEFACTOS.mkdir(exist_ok=True)
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
