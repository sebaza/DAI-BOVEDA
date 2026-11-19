"""T1 re-evaluation of the student benefits with POINT-IN-TIME features from the load history (16-11-2026, D96-D99;
docs/08_benchmark_t1.md section 15).

``python -m evaluation.run_beneficios_cargas_t1`` trains the SAME models as ``run_beneficios_t1`` (CatBoost with 3 seeds, logistic
regression with C chosen on valid; official training window, cohorts from 2015) on the FINAL view of the benefits, and scores the
evaluation rows twice: with the final-view features (what the snapshot has) and with the point-in-time features of
``features_beneficios_cargas``. Training stays on the final view (biased) because there is no load history before 2024.

The evaluation rows are the observed T1 rows whose cut year has load history (cut in 2024 or later: the cohorts 2024-2025 and the
2023 second-semester admissions at k = 2). They are outside the official test window (cohorts 2022-2023), so there is no separate
valid: the decision rule D93 (paired AP gain over the same model without benefits, interval above 0) is applied to this set itself and
the verdict is provisional until a prospective hold-out matures.

Writes AGGREGATES to ``artefactos/resultados_t1_beneficios_cargas.json`` (gitignored): no row, prediction or amount.
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
from pipelines.snapshots import features_beneficios_cargas as FC
from pipelines.snapshots.rules import TRAIN_DESDE_OFICIAL
from . import facultades as FA
from . import grupos_t45 as GR
from . import metrics as M
from . import metrics_t45 as M45

SEMILLAS = (0, 1, 2)
KS = (1, 2)
OFICIAL = {1: "cb_acad", 2: "lr_acad"}                    # the official model of each k (D93)
ACAD, BEN = D.GRUPOS["pre_entry+academico"], D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios"]
ANIO_PIT_DESDE = 2024                                    # first cut year with load history
REPRODUCCION_VALID_AP = {1: {"cb_acad": 0.318, "cb_ben": 0.331, "lr_acad": 0.299, "lr_ben": 0.336},
                         2: {"cb_acad": 0.495, "cb_ben": 0.501, "lr_acad": 0.501, "lr_ben": 0.509}}   # docs/08 section 14.3


# ---------------------------------------------------------------------------------------------------- pure helpers
def filas_de_evaluacion(snap: pd.DataFrame, k: int, desde: int = ANIO_PIT_DESDE) -> pd.DataFrame:
    """Observed rows of ``k`` whose cut year is ``desde`` or later (the years with load history), with the label ``y``."""
    anio = snap["periodo_corte"].str.slice(0, 4).astype(int)
    m = (snap["k"] == k) & (snap["estado_muestra"] == "observada") & snap["continua"].notna() & (anio >= desde)
    out = snap.loc[m].copy()
    out["anio_corte"] = anio[m].to_numpy()
    out["y"] = (~out["continua"].astype(bool)).astype("int8")
    return out.reset_index(drop=True)


def sustituir_beneficios(df: pd.DataFrame, pit: pd.DataFrame) -> pd.DataFrame:
    """Copy of ``df`` whose benefit columns are the point-in-time ones (merged on episode and k; row order kept)."""
    cols = list(FB.COLS_BENEFICIOS)
    sin = df.drop(columns=[c for c in cols if c in df.columns])
    m = sin.merge(pit[["episodio_id", "k", *cols]], on=["episodio_id", "k"], how="left", validate="one_to_one")
    return m[list(df.columns)].reset_index(drop=True)


def decision_d93(ev: Dict, por_anio: Dict[str, Dict], familia: str, ref: str = "acad", variante: str = "pit",
                 exigir_cada_anio: bool = True) -> Dict:
    """D93 on the evaluation set: the benefit model of ``familia`` competes only if its paired AP gain over the same model without
    benefits has a 95 % interval above 0 and a positive point estimate in EACH cut year (consistency)."""
    clave = f"{familia}_ben_{variante}__vs__{familia}_{ref}"
    d = ev[clave]["ap"]
    anios = {a: e[clave]["ap"]["punto"] for a, e in por_anio.items() if clave in e}
    consistente = (bool(anios) and all(v > 0 for v in anios.values())) if exigir_cada_anio else True
    return {"modelo": f"{familia}_ben_{variante}", "contra": f"{familia}_{ref}", "delta_ap": d["punto"], "lo": d["lo"], "hi": d["hi"],
            "ic_sobre_cero": bool(d["lo"] > 0), "delta_ap_por_anio": anios, "positivo_en_cada_anio": consistente,
            "elegible": bool(d["lo"] > 0 and consistente)}


def agrupar_con_oficial(grupo: np.ndarray, y: np.ndarray, p_ben: np.ndarray, p_oficial: np.ndarray, idxs, nombres=None) -> Dict:
    """Group table (``grupos_t45.tabla_agregada``: only groups with n >= 100 and >= 10 events are listed; the rest are counted) of
    the point-in-time benefit model against the official model, plus the AP of both in each listed group."""
    t = GR.tabla_agregada(grupo, y, p_ben, p_oficial, idxs)
    codigos, nom, _, _, _ = GR.clasificar_grupos(grupo, y)
    por = {str(n): i for i, n in enumerate(nom)}
    for fila in t["filas"]:
        m = codigos == por[fila["grupo"]]
        yg = np.asarray(y)[m]
        fila["ap_oficial"] = float(M.metricas(yg.astype(int), np.asarray(p_oficial)[m])["ap"]) if yg.min() != yg.max() else float("nan")
        if nombres is not None and fila["grupo"] in nombres:
            fila["nombre"] = str(nombres[fila["grupo"]])
    return t


# ---------------------------------------------------------------------------------------------------- training
def ajustar_modelos(tr: pd.DataFrame, va: pd.DataFrame, num, cat, semillas, familias=("lr", "cb")) -> Dict:
    """Fit the preprocessor and the requested families on train (valid tunes C / stops CatBoost): ``{"prep", "lr", "info_lr", "cbs"}``.
    Same recipe as ``run_beneficios_t1.ajustar_conjunto``; ``ajustar_y_predecir`` only adds the predictions."""
    prep = D.Preprocesador(num, cat).fit(tr)
    out: Dict = {"prep": prep}
    if "lr" in familias:
        Xtr, Xva = prep.transform(tr), prep.transform(va)
        lr, inf = logistica.ajustar(Xtr, tr["y"].to_numpy(), Xva, va["y"].to_numpy())
        out.update({"lr": lr, "info_lr": {"C": inf["C"], "ap_valid": inf["ap_valid"]}})
    if "cb" in familias:
        Ctr, Cva = prep.transform_catboost(tr), prep.transform_catboost(va)
        out["cbs"] = [catboost_modelo.ajustar(Ctr, tr["y"], Cva, va["y"], cat, seed=s)[0] for s in semillas]
    return out


def ajustar_y_predecir(tr: pd.DataFrame, va: pd.DataFrame, evals: Dict[str, pd.DataFrame], num, cat, semillas) -> Dict:
    """Logistic regression (C tuned on valid) and CatBoost (seed ensemble) fitted on train; predictions for valid and every frame
    of ``evals``. Same recipe as ``run_beneficios_t1.ajustar_conjunto``."""
    m = ajustar_modelos(tr, va, num, cat, semillas)
    prep, lr = m["prep"], m["lr"]
    Xva = prep.transform(va)
    out = {"lr": {"valid": lr.predict_proba(Xva)[:, 1], **{n: lr.predict_proba(prep.transform(e))[:, 1] for n, e in evals.items()}},
           "info_lr": m["info_lr"]}
    Cva = prep.transform_catboost(va)
    Ce = {n: prep.transform_catboost(e) for n, e in evals.items()}
    pred = {"valid": [], **{n: [] for n in evals}}
    for cb in m["cbs"]:
        pred["valid"].append(catboost_modelo.predecir(cb, Cva, cat))
        for n in evals:
            pred[n].append(catboost_modelo.predecir(cb, Ce[n], cat))
    out["cb"] = {n: np.mean(v, axis=0) for n, v in pred.items()}
    return out


def evaluar_k(snap: pd.DataFrame, pit_feats: pd.DataFrame, k: int, semillas, n_boot: int, log, programas=None) -> Dict:
    df = D.seleccionar_modelado(snap, k=k, train_desde=TRAIN_DESDE_OFICIAL)
    tr, va = (df[df["split"] == s].reset_index(drop=True) for s in ("train", "valid"))
    ev_final = filas_de_evaluacion(snap, k)
    ev_pit = sustituir_beneficios(ev_final, pit_feats)
    assert (ev_pit["ben_sin_dato"] == 0).all(), "every evaluation row must have load history at its cut"
    evals_acad = {"final": ev_final}
    evals_ben = {"final": ev_final, "pit": ev_pit}
    t0 = time.perf_counter()
    r_acad = ajustar_y_predecir(tr, va, evals_acad, *ACAD, semillas)
    r_ben = ajustar_y_predecir(tr, va, evals_ben, *BEN, semillas)
    log(f"k={k}: trained in {time.perf_counter() - t0:.0f}s; train n={len(tr)}, valid n={len(va)}, eval n={len(ev_final)}")
    preds = {"baseline_tasa": baseline.TasaHistorica().fit(tr).predict(ev_final)}
    ap_valid = {}
    for fam in ("lr", "cb"):
        preds[f"{fam}_acad"] = r_acad[fam]["final"]
        preds[f"{fam}_ben_final"] = r_ben[fam]["final"]
        preds[f"{fam}_ben_pit"] = r_ben[fam]["pit"]
        ap_valid[f"{fam}_acad"] = float(M.metricas(va["y"].to_numpy(), r_acad[fam]["valid"])["ap"])
        ap_valid[f"{fam}_ben"] = float(M.metricas(va["y"].to_numpy(), r_ben[fam]["valid"])["ap"])
    y = ev_final["y"].to_numpy()
    oficial = OFICIAL[k]
    pares = []
    for fam in ("lr", "cb"):
        pares += [(f"{fam}_ben_pit", f"{fam}_acad"), (f"{fam}_ben_final", f"{fam}_acad"), (f"{fam}_ben_pit", f"{fam}_ben_final")]
    pares += [(f"{fam}_ben_pit", oficial) for fam in ("lr", "cb") if f"{fam}_acad" != oficial] + [(oficial, "baseline_tasa")]
    idx = M45.remuestreos(ev_final["persona_key"].to_numpy(), n_boot, seed=11)
    ev = M45.bootstrap_agrupado(y, preds, idx, pares)
    por_anio = {}
    for a in sorted(ev_final["anio_corte"].unique()):
        m = (ev_final["anio_corte"] == a).to_numpy()
        ia = M45.remuestreos(ev_final.loc[m, "persona_key"].to_numpy(), n_boot, seed=13 + int(a))
        por_anio[str(int(a))] = {"n": int(m.sum()), "eventos": int(y[m].sum()),
                                 **M45.bootstrap_agrupado(y[m], {n: p[m] for n, p in preds.items()}, ia, pares)}
    res: Dict = {
        "k": k, "oficial": oficial,
        "n": {"train": int(len(tr)), "valid": int(len(va)), "evaluacion": int(len(ev_final)), "eventos": int(y.sum()),
              "tasa": float(y.mean()), "personas": int(ev_final["persona_key"].nunique()),
              "por_anio_corte": {str(int(a)): int((ev_final["anio_corte"] == a).sum()) for a in sorted(ev_final["anio_corte"].unique())}},
        "reproduccion_valid": {"ap_valid": ap_valid, "esperado_docs_08_14_3": REPRODUCCION_VALID_AP[k],
                               "difiere_menos_de_0_003": all(abs(ap_valid[m] - v) < 0.003 for m, v in REPRODUCCION_VALID_AP[k].items())},
        "evaluacion": ev, "por_anio": por_anio,
        "d93": {fam: decision_d93(ev, por_anio, fam) for fam in ("lr", "cb")},
        "d93_vista_final": {fam: decision_d93(ev, por_anio, fam, variante="final") for fam in ("lr", "cb")},
        "info": {"lr_acad": r_acad["info_lr"], "lr_ben": r_ben["info_lr"]},
        "hash_datos": S.hash_datos(ev_final, ["episodio_id", "k", "y"]),
    }
    # the benefit variables that changed between the two views (aggregates over the evaluation rows)
    cambia = {}
    for c in ("tiene_gratuidad", "tiene_credito", "tiene_beca_estatal", "tiene_beca_ucn", "merito_ingreso", "n_beneficios", "monto_sem1"):
        cambia[c] = {"final_media": float(ev_final[c].astype(float).mean()), "pit_media": float(ev_pit[c].astype(float).mean())}
    cambia["con_alguna_fila"] = {"final": float((ev_final["n_beneficios"] > 0).mean()), "pit": float((ev_pit["n_beneficios"] > 0).mean())}
    res["variables"] = cambia
    # sensitivity (k = 1): without the students who leave during the admission year (the effect is not observable at the cut)
    if k == 1:
        sale = ev_final["sale_anio"].to_numpy()
        m = ~sale
        isn = M45.remuestreos(ev_final.loc[m, "persona_key"].to_numpy(), n_boot, seed=17)
        res["sin_salidas_en_el_anio"] = {"n": int(m.sum()), "eventos": int(y[m].sum()), "excluidas": int(sale.sum()),
                                         **M45.bootstrap_agrupado(y[m], {n: p[m] for n, p in preds.items()}, isn, pares)}
        res["d93_sin_salidas"] = {fam: decision_d93(res["sin_salidas_en_el_anio"], {}, fam, exigir_cada_anio=False) for fam in ("lr", "cb")}
    # by programa and facultad: the point-in-time benefit model with the best AP against the official model
    mejor = max(("lr_ben_pit", "cb_ben_pit"), key=lambda n: ev[n]["ap"]["punto"])
    fac = FA.facultad_de(ev_final["cod_programa"], programas)
    nombres = {str(c): str(n) for c, n in programas["nombre_programa"].items()}
    res["grupos"] = {"modelo": mejor, "contra": oficial,
                     "programa": agrupar_con_oficial(ev_final["cod_programa"].to_numpy(), y, preds[mejor], preds[oficial], idx, nombres),
                     "facultad": agrupar_con_oficial(fac.to_numpy(), y, preds[mejor], preds[oficial], idx)}
    res["calibracion"] = {m: M.tabla_confiabilidad(y, p) for m, p in preds.items() if m in (oficial, mejor, mejor.replace("_pit", "_final"))}
    return res


def sale_en_el_anio(snap: pd.DataFrame, sem: pd.DataFrame) -> pd.Series:
    from .run_beneficios_t1 import sale_en_el_anio as f
    return f(snap, sem)


def parsear(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="T1 benefits with point-in-time features from the load history.")
    ap.add_argument("--k", type=int, nargs="+", default=list(KS))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--salida", default="resultados_t1_beneficios_cargas")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    log = lambda m: print(m, flush=True)   # noqa: E731
    try:
        from pipelines.common.db import dev_connection
        from . import diagnostico_beneficios_cargas as DC

        with dev_connection() as conn:
            snap, sem = D.cargar_desde_db(conn)
            cargas, calendario, _ = DC.cargar(conn)
            programas = FA.cargar_programas(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t1_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
        snap["sale_anio"] = sale_en_el_anio(snap, sem)
        eval_rows = pd.concat([filas_de_evaluacion(snap, k) for k in args.k])
        pit = FC.features_beneficios_cargas(eval_rows, cargas, calendario)
        out: Dict = {"snapshot_hash": snapshot_hash, "version_codigo": S.version_codigo(), "resultados": {}}
        for k in args.k:
            out["resultados"][f"k{k}"] = evaluar_k(snap, pit, k, SEMILLAS[: args.seeds], args.boot, log, programas)
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
