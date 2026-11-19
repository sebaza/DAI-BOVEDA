"""Benchmark runner for T4 ("transicion real de programa") and T5 ("eliminacion"), docs/11_benchmark_t4_t5.md.

``python -m evaluation.run_t45`` trains, for each cut k (2, 4) and each binary target, the ablation ladder on the same
population: historical rate by program, logistic regression and CatBoost on the admission profile and on profile +
academic aggregates, and a GRU over the semester sequence (profile / profile + aggregates; 3 seeds, GPU). It also trains
a multiclass view of the five outcomes. Valid (cohorts 2020-2021) selects, test (2022-2023) reports with a bootstrap
GROUPED BY PERSON; the aggregate forecasts by programa and by facultad are evaluated on test. Writes AGGREGATES to
``artefactos/resultados_t45.json`` (gitignored); individual predictions only as gitignored ``artefactos/preds/t45_*.npz``.
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

from evaluation import facultades as FA
from evaluation import grupos_t45 as GR
from evaluation import metrics as M
from evaluation import metrics_t45 as M45
from evaluation import subgrupos as SG
from evaluation.run_t2 import ram_pico_mb
from models import baseline, catboost_modelo, gru as G, logistica
from models import seguimiento as S
from models import t45_data as TD
from models import t45_multiclase as MC
from models.data import Preprocesador
from pipelines.snapshots import rules as R
from pipelines.snapshots import rules_t45 as R45

SEMILLAS = (0, 1, 2)
EXPERIMENTO_T45 = "t45_transicion_eliminacion"
KS = R45.KS
BINARIOS = ("baseline_tasa", "lr_adm", "lr_agg", "cb_adm", "cb_agg", "gru_adm", "gru_agg")
CLASICOS = ("lr_adm", "lr_agg", "cb_adm", "cb_agg")
REDES = ("gru_adm", "gru_agg")
GRUPO_DE = {"lr_adm": "adm", "cb_adm": "adm", "gru_adm": "adm", "lr_agg": "adm+agg", "cb_agg": "adm+agg",
            "gru_agg": "adm+agg"}
PARES_BASE = [("lr_adm", "baseline_tasa"), ("cb_adm", "baseline_tasa"), ("lr_agg", "lr_adm"), ("cb_agg", "cb_adm"),
              ("cb_adm", "lr_adm"), ("cb_agg", "lr_agg"), ("gru_adm", "cb_adm"), ("gru_agg", "cb_agg"),
              ("gru_agg", "lr_agg"), ("gru_adm", "lr_adm"), ("gru_agg", "gru_adm"), ("cb_agg", "baseline_tasa")]
PARES_MC = [("mc_lr_agg", "mc_base"), ("mc_cb_agg", "mc_base"), ("mc_cb_agg", "mc_lr_agg")]


def version_codigo_t45() -> str:
    from pathlib import Path

    raiz = Path(S.RAIZ)
    h = hashlib.sha256(S.version_codigo().encode())
    for p in sorted([raiz / "pipelines" / "snapshots" / n for n in ("rules_t3.py", "features_t3.py", "rules_t45.py", "features_t45.py")]
                    + [raiz / "pipelines" / "marts" / "rules_traslados.py"]
                    + [raiz / "models" / n for n in ("t3_data.py", "t45_data.py", "t45_multiclase.py")]):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------
# training of one cut
# ---------------------------------------------------------------------------------------------
def entrenar_k(snap: pd.DataFrame, sem: pd.DataFrame, k: int, seeds, log, solo=None) -> Dict:
    import torch

    parts = TD.particion(snap, k)
    tr, va, te = parts["train"], parts["valid"], parts["test"]
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    preds: Dict[str, Dict[str, Dict[str, np.ndarray]]] = {t: {"valid": {}, "test": {}} for t in TD.TARGETS}
    tiempos: Dict[str, Dict[str, float]] = {t: {} for t in TD.TARGETS}
    info: Dict[str, Dict[str, Dict]] = {t: {} for t in TD.TARGETS}
    por_semilla: Dict[str, Dict[str, List]] = {t: {} for t in TD.TARGETS}

    preps = {}
    for g, (num, cat) in TD.GRUPOS.items():
        TD.verificar_sin_fuga(num, cat)
        preps[g] = Preprocesador(num, cat).fit(tr)
    mats = {}
    for g, prep in preps.items():
        mats[g] = {"lr": [prep.transform(x) for x in (tr, va, te)], "cb": [prep.transform_catboost(x) for x in (tr, va, te)]}
    seqs = [TD.construir_secuencias_t45(x, sem, k) for x in (tr, va, te)]

    for tgt, (col, _) in TD.TARGETS.items():
        ytr, yva, yte = tr[col].to_numpy(), va[col].to_numpy(), te[col].to_numpy()
        pv, pt, ti, inf = preds[tgt]["valid"], preds[tgt]["test"], tiempos[tgt], info[tgt]

        def quiere(n):
            return solo is None or n in solo

        t0 = time.perf_counter()
        b = baseline.TasaHistorica().fit(tr.assign(y=ytr))
        pv["baseline_tasa"], pt["baseline_tasa"] = b.predict(va), b.predict(te)
        ti["baseline_tasa"] = time.perf_counter() - t0
        for g, suf in (("adm", "adm"), ("adm+agg", "agg")):
            num, cat = TD.GRUPOS[g]
            if quiere(f"lr_{suf}"):
                t0 = time.perf_counter()
                Xtr, Xva, Xte = mats[g]["lr"]
                m, i = logistica.ajustar(Xtr, ytr, Xva, yva)
                pv[f"lr_{suf}"], pt[f"lr_{suf}"] = m.predict_proba(Xva)[:, 1], m.predict_proba(Xte)[:, 1]
                ti[f"lr_{suf}"] = time.perf_counter() - t0
                inf[f"lr_{suf}"] = {kk: v for kk, v in i.items() if kk != "busqueda"} | {"n_variables": int(Xtr.shape[1])}
                log(f"k={k} {tgt} lr_{suf}: C={i['C']} AP valid={i['ap_valid']:.4f}")
            if quiere(f"cb_{suf}"):
                t0 = time.perf_counter()
                Ctr, Cva, Cte = mats[g]["cb"]
                av, at, its, ind = [], [], [], []
                for s in seeds:
                    cb, ci = catboost_modelo.ajustar(Ctr, ytr, Cva, yva, cat, seed=s)
                    a, c = catboost_modelo.predecir(cb, Cva, cat), catboost_modelo.predecir(cb, Cte, cat)
                    av.append(a), at.append(c), its.append(ci["mejor_iteracion"])
                    ind.append({"valid": M.metricas(yva, a), "test": M.metricas(yte, c)})
                pv[f"cb_{suf}"], pt[f"cb_{suf}"] = np.mean(av, axis=0), np.mean(at, axis=0)
                ti[f"cb_{suf}"] = time.perf_counter() - t0
                por_semilla[tgt][f"cb_{suf}"] = ind
                inf[f"cb_{suf}"] = {"mejores_iteraciones": its, "n_variables": len(num) + len(cat),
                                    "params": {kk: str(v) for kk, v in catboost_modelo.PARAMS.items()}}
                log(f"k={k} {tgt} cb_{suf}: iteraciones={its}")
            if quiere(f"gru_{suf}"):
                prep = preps[g]
                conj = [G.Conjunto(s_, prep.transform_num(x), prep.transform_cat_codes(x), x[col].to_numpy())
                        for s_, x in zip(seqs, (tr, va, te))]
                av, at, ind, runs = [], [], [], []
                for s in seeds:
                    r = G.entrenar(conj[0], conj[1], prep.cardinalidades(), seed=s, device=dev)
                    a, c = G.predecir(r["model"], conj[1], dev), G.predecir(r["model"], conj[2], dev)
                    av.append(a), at.append(c)
                    ind.append({"valid": M.metricas(yva, a), "test": M.metricas(yte, c)})
                    runs.append({kk: v for kk, v in r.items() if kk != "model"})
                    log(f"k={k} {tgt} gru_{suf} seed={s}: AP valid={r['ap_valid']:.4f} epoca={r['mejor_epoca']} "
                        f"{r['segundos']:.0f} s gpu={r['gpu_pico_mb']:.0f} MB")
                    del r
                pv[f"gru_{suf}"], pt[f"gru_{suf}"] = np.mean(av, axis=0), np.mean(at, axis=0)
                ti[f"gru_{suf}"] = float(sum(r_["segundos"] for r_ in runs))
                por_semilla[tgt][f"gru_{suf}"] = ind
                inf[f"gru_{suf}"] = {"semillas": runs, "hidden": G.HIDDEN, "static_dim": G.STATIC_DIM, "batch": G.BATCH,
                                     "lr": G.LR, "weight_decay": G.WD, "max_epocas": G.MAX_EPOCHS, "paciencia": G.PACIENCIA,
                                     "n_variables_estaticas": int(conj[0].num.shape[1]), "d_secuencia": int(conj[0].seq.shape[2]),
                                     "gpu_pico_mb": max(r_["gpu_pico_mb"] for r_ in runs)}

    # multiclass view (profile + aggregates)
    mc_p: Dict[str, Dict[str, np.ndarray]] = {"valid": {}, "test": {}}
    mc_t: Dict[str, float] = {}
    mc_i: Dict[str, Dict] = {}
    ytr_c, yva_c = tr["yc"].to_numpy(), va["yc"].to_numpy()
    t0 = time.perf_counter()
    b = MC.TasaClases().fit(tr)
    mc_p["valid"]["mc_base"], mc_p["test"]["mc_base"] = b.predict(va), b.predict(te)
    mc_t["mc_base"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    Xtr, Xva, Xte = mats["adm+agg"]["lr"]
    m, i = MC.logistica_multiclase(Xtr, ytr_c, Xva, yva_c)
    mc_p["valid"]["mc_lr_agg"], mc_p["test"]["mc_lr_agg"] = MC.predecir_logistica(m, Xva), MC.predecir_logistica(m, Xte)
    mc_t["mc_lr_agg"], mc_i["mc_lr_agg"] = time.perf_counter() - t0, i
    log(f"k={k} multiclase lr: C={i['C']} logloss valid={i['logloss_valid']:.4f}")
    t0 = time.perf_counter()
    cat = TD.GRUPOS["adm+agg"][1]
    Ctr, Cva, Cte = mats["adm+agg"]["cb"]
    av, at, its = [], [], []
    for s in seeds:
        cb, ci = MC.catboost_multiclase(Ctr, ytr_c, Cva, yva_c, cat, seed=s)
        av.append(MC.predecir_catboost(cb, Cva, cat)), at.append(MC.predecir_catboost(cb, Cte, cat)), its.append(ci["mejor_iteracion"])
    mc_p["valid"]["mc_cb_agg"], mc_p["test"]["mc_cb_agg"] = np.mean(av, axis=0), np.mean(at, axis=0)
    mc_t["mc_cb_agg"], mc_i["mc_cb_agg"] = time.perf_counter() - t0, {"mejores_iteraciones": its}
    log(f"k={k} multiclase cb: iteraciones={its}")
    return {"parts": parts, "preds": preds, "tiempos": tiempos, "info": info, "por_semilla": por_semilla,
            "mc": {"preds": mc_p, "tiempos": mc_t, "info": mc_i}}


# ---------------------------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------------------------
def elegir_modelos(p_valid: Dict[str, np.ndarray], yva: np.ndarray) -> Dict[str, str]:
    """Best classical model and best network by the validation AP."""
    ap = {m: M.metricas(yva, p)["ap"] for m, p in p_valid.items() if m != "baseline_tasa"}
    clasico = max((m for m in CLASICOS if m in ap), key=lambda m: ap[m])
    red = max((m for m in REDES if m in ap), key=lambda m: ap[m]) if any(m in ap for m in REDES) else None
    return {"clasico": clasico, "red": red}


def decidir_conservado(sel: Dict[str, str], delta_red_vs_clasico: Optional[Dict[str, float]], ap_valid: Dict[str, float]) -> str:
    """The network is kept only if it beats the best classical model on valid AND its paired VALID AP difference (bootstrap
    grouped by person) has an interval above zero; otherwise the classical one stays (D114: test never chooses; until
    16-11-2026 the interval was the test one)."""
    red, clasico = sel["red"], sel["clasico"]
    if red is None or delta_red_vs_clasico is None:
        return clasico
    if ap_valid[red] > ap_valid[clasico] and delta_red_vs_clasico["lo"] > 0:
        return red
    return clasico


def evaluar_k(res: Dict, k: int, n_boot: int, log, programas: pd.DataFrame, objetivos=None, conservado_forzado=None,
              pares_extra=None, multiclase: bool = True) -> Dict:
    """Evaluation of one cut. ``objetivos`` restricts the targets, ``conservado_forzado`` (``{target: model}``) overrides the
    D114 choice (a model adopted after the benchmark, e.g. ``calibrar_t5_nuevas``), ``pares_extra`` (``{target: [(a, b)]}``)
    adds paired differences and ``multiclase=False`` skips the multiclass view. The defaults reproduce the benchmark."""
    parts = res["parts"]
    va, te = parts["valid"], parts["test"]
    idxs = M45.remuestreos(te["persona_key"].to_numpy(), n_boot, seed=7)
    idxs_va = M45.remuestreos(va["persona_key"].to_numpy(), n_boot, seed=7)
    fac = lambda d: FA.facultad_de(d["cod_programa"], programas)   # noqa: E731  (faculty NAMES, stage B)
    te = te.assign(facultad=fac(te))
    vt = pd.concat([va, te.drop(columns="facultad")], ignore_index=True)           # complementary: valid + test (more groups reach 10 events)
    vt = vt.assign(facultad=fac(vt))
    idxs_vt = M45.remuestreos(vt["persona_key"].to_numpy(), n_boot, seed=11)
    out: Dict = {"n_split": {s: int(len(parts[s])) for s in TD.SPLITS},
                 "n_personas_test": int(te["persona_key"].nunique()), "targets": {}}
    for tgt, (col, nombre) in TD.TARGETS.items():
        if objetivos is not None and tgt not in objetivos:
            continue
        yva, yte = va[col].to_numpy(), te[col].to_numpy()
        pv, pt = res["preds"][tgt]["valid"], res["preds"][tgt]["test"]
        sel = elegir_modelos(pv, yva)
        ap_valid = {m: M.metricas(yva, p)["ap"] for m, p in pv.items()}
        pares = [p for p in PARES_BASE if p[0] in pt and p[1] in pt]
        pares += [p for p in (pares_extra or {}).get(tgt, []) if p[0] in pt and p[1] in pt and p not in pares]
        if sel["red"]:
            pares += [(sel["red"], sel["clasico"])]
        ev = M45.bootstrap_agrupado(yte, pt, idxs, pares)
        delta_red_valid = None
        if sel["red"]:                       # D114: the network-vs-classical interval is computed on VALID
            ev_va = M45.bootstrap_agrupado(yva, {m: pv[m] for m in (sel["red"], sel["clasico"])}, idxs_va,
                                           [(sel["red"], sel["clasico"])])
            delta_red_valid = ev_va[f"{sel['red']}__vs__{sel['clasico']}"]["ap"]
        conservado = decidir_conservado(sel, delta_red_valid, ap_valid)
        if conservado_forzado and tgt in conservado_forzado:
            conservado = conservado_forzado[tgt]
        log(f"k={k} {tgt}: mejor clasico={sel['clasico']} mejor red={sel['red']} conservado={conservado}")
        p_c, p_b = pt[conservado], pt["baseline_tasa"]
        t_out: Dict = {
            "n": {s: {"n": int(len(parts[s])), "eventos": int(parts[s][col].sum()), "tasa": float(parts[s][col].mean())} for s in TD.SPLITS},
            "seleccion": {**sel, "conservado": conservado, "ap_valid": ap_valid,
                          "delta_red_vs_clasico_valid": delta_red_valid},
            "valid": {m: M.metricas(yva, p) for m, p in pv.items()},
            "test": ev,
            "calibracion_test": {m: M.tabla_confiabilidad(yte, pt[m]) for m in (conservado, "baseline_tasa")},
        }
        t_out["grupos"] = {
            "programa": GR.tabla_agregada(te["cod_programa"].to_numpy(), yte, p_c, p_b, idxs),
            "facultad": GR.tabla_agregada(te["facultad"].to_numpy(), yte, p_c, p_b, idxs),
        }
        yvt = vt[col].to_numpy()
        pvt_c, pvt_b = np.concatenate([pv[conservado], p_c]), np.concatenate([pv["baseline_tasa"], p_b])
        t_out["grupos_valid_test"] = {
            "programa": GR.tabla_agregada(vt["cod_programa"].to_numpy(), yvt, pvt_c, pvt_b, idxs_vt),
            "facultad": GR.tabla_agregada(vt["facultad"].to_numpy(), yvt, pvt_c, pvt_b, idxs_vt),
        }
        for nivel in (t_out["grupos"], t_out["grupos_valid_test"]):
            for fila in nivel["programa"]["filas"]:
                if fila["grupo"] in programas.index:
                    fila["nombre"] = str(programas.loc[fila["grupo"], "nombre_programa"])
        sub = {"sexo": SG.tabla_grupo(te, yte, p_c, "sexo_equidad", SG.N_MIN_GRUPO),
               "cohorte": SG.tabla_grupo(te, yte, p_c, "cohorte_anio", SG.N_MIN_GRUPO),
               "via": SG.tabla_grupo(te, yte, p_c, "via_clase", SG.N_MIN_GRUPO),
               "plan_comun": SG.tabla_grupo(te.assign(pc=te["trayectoria_plan_comun"].map({True: "plan_comun", False: "otros"})), yte, p_c, "pc", 30)}
        t_out["subgrupos_test"] = sub
        t_out["brecha_sexo"] = SG.brechas_sexo(sub["sexo"])
        if tgt in ("T5", "T5E"):
            t_out["sensibilidad_registro_e"] = sensibilidad_horizonte_dudoso(te, yte, pt, conservado, n_boot)
        out["targets"][tgt] = t_out
        log(f"k={k} {tgt}: evaluado ({len(idxs)} remuestreos)")
    if not multiclase:
        return out
    # multiclass
    yc_te = te["yc"].to_numpy()
    mcp = res["mc"]["preds"]
    mc_ev = M45.bootstrap_multiclase(yc_te, mcp["test"], TD.CLASES, idxs, PARES_MC)
    mc_valid = {m: M45.metricas_multiclase(va["yc"].to_numpy(), p, TD.CLASES) for m, p in mcp["valid"].items()}
    out["multiclase"] = {"clases": list(TD.CLASES), "valid": mc_valid, "test": mc_ev,
                         "n_clase_test": {c: int((yc_te == i).sum()) for i, c in enumerate(TD.CLASES)},
                         "matriz_promedio_test": {m: {c: float(p[:, i].mean()) for i, c in enumerate(TD.CLASES)} for m, p in mcp["test"].items()},
                         "tasas_observadas_test": {c: float((yc_te == i).mean()) for i, c in enumerate(TD.CLASES)}}
    return out


def sensibilidad_horizonte_dudoso(te: pd.DataFrame, yte: np.ndarray, pt: Dict[str, np.ndarray], conservado: str, n_boot: int) -> Dict:
    """Evaluation (c) of T5: the test rows WITHOUT ``horizonte_e_dudoso`` (the horizon reaches no period after
    ``E_COMPLETO_HASTA``, from which ``E`` looks under-recorded, P75). The flag is a snapshot column. ``evaluado`` is False
    when fewer than ``N_MIN`` rows or ``EVENTOS_MIN`` events remain (always the case for ``k`` = 4). Besides the metrics of the
    kept model and of the baseline there is the paired AP difference between them (bootstrap grouped by person)."""
    m = ~te["horizonte_e_dudoso"].to_numpy(bool)
    out: Dict = {"periodo_limite": R45.E_COMPLETO_HASTA, "n": int(m.sum()), "eventos": int(yte[m].sum()), "n_total_test": int(len(m)),
                 "n_excluidas": int((~m).sum()), "eventos_excluidas": int(yte[~m].sum())}
    if m.sum() < GR.N_MIN or yte[m].sum() < GR.EVENTOS_MIN:
        out["evaluado"] = False
        return out
    y, idx = yte[m], M45.remuestreos(te.loc[m, "persona_key"].to_numpy(), n_boot, seed=13)
    ev = M45.bootstrap_agrupado(y, {conservado: pt[conservado][m], "baseline_tasa": pt["baseline_tasa"][m]}, idx,
                                [(conservado, "baseline_tasa")])
    out.update({"evaluado": True, "tasa_observada": float(y.mean()), "modelos": {
        n: {"riesgo_medio": float(pt[n][m].mean()), "ap": ev[n]["ap"], "roc_auc": ev[n]["roc_auc"], "brier": ev[n]["brier"], "ece": ev[n]["ece"]}
        for n in (conservado, "baseline_tasa")}, "delta_ap_vs_base": ev[f"{conservado}__vs__baseline_tasa"]["ap"]})
    return out


def registro_eliminacion(conn) -> List[Dict]:
    """Aggregate count of ``E`` states and of enrolled states per regular period since 2018 (descriptive; P75)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT periodo, count(*) FILTER (WHERE cod_estado = 'E') AS e,
                   count(*) FILTER (WHERE cod_estado IN ('M', 'N', 'J')) AS matriculados
            FROM neural_core.evento_estado
            WHERE NOT es_correccion_sistema AND periodo ~ '^20(1[89]|2[0-6])(10|20)$' GROUP BY 1 ORDER BY 1""")
        return [{"periodo": p, "e": int(e), "matriculados": int(m)} for p, e, m in cur.fetchall()]


def descriptivo(snap: pd.DataFrame) -> Dict:
    """Counts per k / split / outcome (all outcomes, including the excluded ones) and the other-exit types."""
    g = snap.groupby(["k", "split", "resultado"]).size().rename("n").reset_index()
    cuentas: Dict = {}
    for r in g.itertuples(index=False):
        cuentas.setdefault(str(r.k), {}).setdefault(r.split, {})[r.resultado] = int(r.n)
    tipos = snap.loc[snap["resultado"] == "otra_salida"].groupby(["k", "split", "otra_salida_tipo"]).size().rename("n").reset_index()
    t: Dict = {}
    for r in tipos.itertuples(index=False):
        t.setdefault(str(r.k), {}).setdefault(r.split, {})[r.otra_salida_tipo] = int(r.n)
    solap = snap.loc[snap["split"].isin(TD.SPLITS)].groupby(["k", "split"]).apply(
        lambda d: int((d["hubo_transicion_en_horizonte"] & d["hubo_eliminacion_en_horizonte"]).sum()), include_groups=False)
    return {"cuentas": cuentas, "otra_salida_tipos": t,
            "eliminacion_y_transicion": {f"{k}.{s}": int(v) for (k, s), v in solap.items()}}


def causales_eliminacion(conn) -> List[Dict]:
    """Aggregate distribution of the causal code of the state E inside the horizon of the T5 rows (groups under 10 people
    are folded into 'otros'); descriptive support for P70."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH r AS (SELECT s.episodio_id, s.k, s.periodo_admision, COALESCE(s.episodio_especialidad_id, s.episodio_id) AS ep
                       FROM neural_mart.snapshot_t45 s WHERE s.resultado = 'eliminacion' AND s.split IN ('train', 'valid', 'test')),
            c AS (SELECT DISTINCT ON (r.episodio_id, r.k) r.episodio_id, r.k, COALESCE(e.cod_causal, 'sin_causal') AS causal
                  FROM r JOIN neural_core.evento_estado e ON e.episodio_id = r.ep AND e.cod_estado = 'E' AND NOT e.es_correccion_sistema
                  ORDER BY r.episodio_id, r.k, e.periodo)
            SELECT causal, count(*) AS n FROM c GROUP BY 1 ORDER BY 2 DESC""")
        filas = cur.fetchall()
    total = sum(n for _, n in filas)
    visibles = [(c, int(n)) for c, n in filas if n >= 10]
    resto = total - sum(n for _, n in visibles)
    out = [{"causal": c, "n": n} for c, n in visibles]
    if resto:
        out.append({"causal": "otros", "n": int(resto)})
    return out


def guardar_preds(parts, preds, mc, k):
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    for sp in ("valid", "test"):
        datos = {f"{t}__{n}": p.astype("float32") for t in TD.TARGETS for n, p in preds[t][sp].items()}
        datos |= {n: p.astype("float32") for n, p in mc["preds"][sp].items()}
        np.savez_compressed(S.ARTEFACTOS / "preds" / f"t45_k{k}_{sp}.npz", episodio_id=parts[sp]["episodio_id"].to_numpy(), **datos)


def registrar_mlflow(k: int, res: Dict, ev: Dict, snapshot_hash: str, etiqueta: str) -> None:
    mlflow = S.iniciar_mlflow()
    mlflow.set_experiment(EXPERIMENTO_T45)
    codigo = version_codigo_t45()
    for tgt in TD.TARGETS:
        for nombre in res["preds"][tgt]["test"]:
            met = {}
            for m_, v in ev["targets"][tgt]["test"][nombre].items():
                met[f"test_{m_}"], met[f"test_{m_}_lo"], met[f"test_{m_}_hi"] = v["punto"], v["lo"], v["hi"]
            for m_, v in ev["targets"][tgt]["valid"][nombre].items():
                met[f"valid_{m_}"] = v
            met["segundos_entrenamiento"] = res["tiempos"][tgt].get(nombre, 0.0)
            params = {"modelo": nombre, "k": k, "tarea": tgt, "grupo": GRUPO_DE.get(nombre, "programa"),
                      "n_train": len(res["parts"]["train"]), "n_valid": len(res["parts"]["valid"]), "n_test": len(res["parts"]["test"]),
                      **{kk: json.dumps(v)[:240] for kk, v in res["info"][tgt].get(nombre, {}).items() if kk not in ("semillas", "busqueda")}}
            S.registrar(mlflow, f"{etiqueta}_{tgt}_k{k}_{nombre}", params, met,
                        {"hash_snapshot": snapshot_hash, "version_codigo": codigo, "tarea": tgt,
                         "evento": TD.TARGETS[tgt][1]})
    for nombre in res["mc"]["preds"]["test"]:
        met = {f"test_{m_}": v["punto"] for m_, v in ev["multiclase"]["test"][nombre].items()}
        met["segundos_entrenamiento"] = res["mc"]["tiempos"].get(nombre, 0.0)
        S.registrar(mlflow, f"{etiqueta}_multiclase_k{k}_{nombre}", {"modelo": nombre, "k": k, "tarea": "multiclase", "n_train": len(res["parts"]["train"])},
                    met, {"hash_snapshot": snapshot_hash, "version_codigo": codigo, "tarea": "T4_T5", "evento": "resultado_multiclase"})


def parsear(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train and evaluate the T4 / T5 benchmark.")
    ap.add_argument("--k", type=int, nargs="*", default=list(KS))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--salida", default="resultados_t45")
    ap.add_argument("--solo", nargs="*", default=None, help="subset of models (development only)")
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
                cur.execute("SELECT valor FROM neural_mart.snapshot_t45_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
                cur.execute("SELECT clave, valor FROM neural_mart.snapshot_t45_resumen WHERE clave LIKE 'embudo_%' ORDER BY 1")
                embudo = dict(cur.fetchall())
                cur.execute("SELECT valor FROM neural_mart.snapshot_t45_resumen WHERE clave = 'periodo_cierre'")
                cierre = cur.fetchone()[0]
            programas = FA.cargar_programas(conn)
            causales = causales_eliminacion(conn)
            registro_e = registro_eliminacion(conn)
        print(f"snapshot cargado: {len(snap):,} filas, RAM pico {ram_pico_mb()} MB", flush=True)
        out = {"snapshot_hash": snapshot_hash, "version_codigo": version_codigo_t45(), "periodo_cierre": cierre, "embudo": embudo,
               "descriptivo": descriptivo(snap), "causales_eliminacion": causales, "registro_e": registro_e, "por_k": {}, "tiempos_s": {}, "info": {},
               "semillas": {}, "ks": args.k, "n_boot": args.boot}
        for k in args.k:
            res = entrenar_k(snap, sem, k, SEMILLAS[: args.seeds], lambda m: print(m, flush=True), args.solo)
            ev = evaluar_k(res, k, args.boot, lambda m: print(m, flush=True), programas)
            out["por_k"][str(k)] = ev
            out["tiempos_s"][str(k)] = {**res["tiempos"], "multiclase": res["mc"]["tiempos"]}
            out["info"][str(k)] = {**res["info"], "multiclase": res["mc"]["info"]}
            out["semillas"][str(k)] = res["por_semilla"]
            guardar_preds(res["parts"], res["preds"], res["mc"], k)
            if not args.solo:
                registrar_mlflow(k, res, ev, snapshot_hash, args.salida)
            del res
        out["ram_pico_mb"] = ram_pico_mb()
        out["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        out["segundos_totales"] = time.perf_counter() - t_ini
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / f"{args.salida}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print(f"escrito artefactos/{args.salida}.json ({out['segundos_totales']:.0f} s, RAM pico {out['ram_pico_mb']} MB)")
        print("FIN")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
