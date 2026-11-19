"""Benchmark runner for T2 (docs/09_benchmark_t2.md): approval of a course attempt, with and without the curriculum graph.

``python -m evaluation.run_t2`` trains the baseline, logistic regression and CatBoost on the feature sets a..d, CatBoost
with GraphSAGE course embeddings, and the end-to-end networks (GNN / MLP / no course representation), evaluates valid,
test and posterior and writes AGGREGATES to ``artefactos/resultados_t2.json`` (gitignored). Individual predictions are
kept only as gitignored ``artefactos/preds/t2_*.npz``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from models import catboost_modelo, logistica, seguimiento as S, t2_data as TD, t2_deriva as DV, t2_grafo as G
from . import facultades as FA
from . import metrics_t2 as M2
from . import t2_bandas as TB
from pipelines.snapshots import rules_t2 as R2
from sklearn.metrics import average_precision_score, roc_auc_score

SEMILLAS = (0, 1, 2)
SPLITS_EVAL = ("valid", "test", "posterior")
CB_PARAMS = dict(iterations=2000, learning_rate=0.08, depth=6, l2_leaf_reg=5.0, early_stopping_rounds=80,
                 eval_metric="Logloss", loss_function="Logloss", boost_from_average=True, thread_count=-1,
                 verbose=False, allow_writing_files=False)
NOMBRES_NN = {"nn_gnn": "gnn", "nn_gnn_prereq": "gnn", "nn_mlp": "mlp", "nn_ninguno": "ninguno"}
EXPERIMENTO_T2 = "t2_aprobacion_por_intento"
NN_EVAL_CADA = 40            # optimizer steps between validation evaluations of the networks (~1/4 epoch)
NN_PACIENCIA = 8             # evaluations without improvement


def ram_pico_mb() -> Optional[float]:
    """Peak working set of this process (Windows API through ctypes; None elsewhere)."""
    try:
        import ctypes
        from ctypes import wintypes

        class Contadores(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = Contadores()
        c.cb = ctypes.sizeof(c)
        k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Contadores), wintypes.DWORD]
        ok = psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return float(c.PeakWorkingSetSize) / 2 ** 20 if ok else None
    except Exception:
        return None


def cb_ajustar(Xtr, ytr, Xva, yva, cat: List[str], semilla: int):
    from catboost import CatBoostClassifier, Pool
    m = CatBoostClassifier(random_seed=semilla, **CB_PARAMS)
    m.fit(Pool(Xtr, ytr, cat_features=cat), eval_set=Pool(Xva, yva, cat_features=cat), use_best_model=True)
    return m


def cb_predecir(m, X, cat):
    from catboost import Pool
    return m.predict_proba(Pool(X, cat_features=cat))[:, 1]


def cargar_grafo_db(conn):
    """Malla, prerequisite edges and PRE-2015 pass rates per course (aggregate query; no individual rows)."""
    def leer(sql):
        with conn.cursor() as cur:
            cur.execute(sql)
            return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    malla = leer("SELECT cod_programa, catalogo, codigo_asignatura, semestre, creditos, formacion, depto "
                 "FROM neural_core.asignatura_malla")
    for c in ("semestre", "creditos"):
        malla[c] = pd.to_numeric(malla[c]).astype("float64")
    pre = leer("SELECT cod_programa, catalogo, codigo_requisito, codigo_asignatura FROM neural_core.prerrequisito")
    stats = leer("SELECT codigo_asignatura AS codigo, count(*) AS n, sum((nota_numerica >= 4.0)::int) AS aprob "
                 "FROM neural_core.intento_asignatura WHERE es_intento_evaluado AND nota_numerica IS NOT NULL "
                 "AND periodo < '201510' AND codigo_asignatura IS NOT NULL GROUP BY 1")
    for c in ("n", "aprob"):
        stats[c] = pd.to_numeric(stats[c]).astype("float64")
    return malla, pre, stats


Q_TABLA_CURSOS = """
SELECT i.codigo_asignatura, e.cod_programa AS prog, i.periodo, count(*)::float8 AS n,
       sum((i.nota_numerica >= 4.0)::int)::float8 AS a, sum(i.nota_numerica)::float8 AS s
FROM neural_core.intento_asignatura i LEFT JOIN neural_core.episodio_programa e ON e.episodio_id = i.episodio_id
WHERE i.es_intento_evaluado AND i.nota_numerica IS NOT NULL AND i.codigo_asignatura IS NOT NULL
  AND i.periodo NOT IN ('201920', '202010') GROUP BY 1, 2, 3
"""
VIDA_MEDIA_ANIOS, VENTANA_ANIOS = 2.0, 3.0         # P55 ablation (stage B): decay half-life and window of the recent history
CB_BANDAS = dict(iterations=1200, learning_rate=0.1, depth=6, l2_leaf_reg=5.0, early_stopping_rounds=60, eval_metric="MultiClass",
                 loss_function="MultiClass", thread_count=-1, verbose=False, allow_writing_files=False)


def cargar_tabla_cursos(conn) -> pd.DataFrame:
    """Aggregate attempts per (course, program of the episode, period): the same attempts that feed the snapshot's pass rates."""
    with conn.cursor() as cur:
        cur.execute(Q_TABLA_CURSOS)
        return pd.DataFrame(cur.fetchall(), columns=["codigo_asignatura", "prog", "periodo", "n", "a", "s"])


def con_estadisticas_recientes(d: pd.DataFrame, tabla: pd.DataFrame, modo: str) -> pd.DataFrame:
    """Copy of the rows with the seven course statistics of the snapshot replaced by their recent-weighted versions."""
    clave = pd.DataFrame({"codigo_asignatura": d["codigo_asignatura"].astype(object), "cod_programa": d["cod_programa"].astype(object),
                          "periodo": d["periodo"].astype(str), "episodio_id": d["episodio_id"].to_numpy()})
    nuevo = DV.estadisticas_recientes(clave, tabla, modo, VIDA_MEDIA_ANIOS, VENTANA_ANIOS)
    out = d.copy()
    for c in DV.COLUMNAS:
        out[c] = nuevo[c].astype("float32").to_numpy()
    return out


def entrenar_bandas(parts: Dict[str, pd.DataFrame], conjunto: str, semilla: int, log) -> Dict:
    """CatBoost MultiClass of the four grade bands on feature set ``conjunto`` + the frequency baseline."""
    from catboost import CatBoostClassifier, Pool
    tr, va = parts["train"], parts["valid"]
    num, cat = TD.CONJUNTOS[conjunto]
    prep = TD.PreprocesadorT2(num, cat).fit(tr)
    ytr, yva = TB.y_banda(tr), TB.y_banda(va)
    t0 = time.perf_counter()
    m = CatBoostClassifier(random_seed=semilla, classes_count=len(TB.CLASES), **CB_BANDAS)
    m.fit(Pool(prep.transform_catboost(tr), ytr, cat_features=cat), eval_set=Pool(prep.transform_catboost(va), yva, cat_features=cat),
          use_best_model=True)
    P = {sp: m.predict_proba(Pool(prep.transform_catboost(parts[sp]), cat_features=cat)) for sp in SPLITS_EVAL}
    seg = time.perf_counter() - t0
    log(f"bandas (conjunto {conjunto}): iteracion={int(m.get_best_iteration())} ({seg:.0f} s)")
    base = {sp: TB.frecuencias(ytr, len(parts[sp])) for sp in SPLITS_EVAL}
    return {"conjunto": conjunto, "preds": {"cb_bandas": P, "frecuencias": base}, "segundos": seg,
            "info": {"conjunto": conjunto, "mejor_iteracion": int(m.get_best_iteration()), "semilla": semilla, "clases": list(TB.CLASES),
                     "params": {k: str(v) for k, v in CB_BANDAS.items()}, "n_variables": len(num) + len(cat)}}


def evaluar_bandas(res: Dict, boot: int, log) -> Dict:
    """Metrics against the frequency baseline (person-grouped bootstrap) and the aggregated forecasts by programa / facultad."""
    parts, b, programas = res["parts"], res["bandas"], res["programas"]
    out: Dict = {"conjunto": b["conjunto"], "clases": list(TB.CLASES), "etiquetas": R2.ETIQUETA_BANDA, "cortes": list(R2.CORTES_BANDA),
                 "info": b["info"], "metricas": {}, "distribucion": {}, "grupos": {}}
    n_boot = {"valid": min(boot, 150), "test": min(boot, 300), "posterior": min(boot, 150)}
    for sp in SPLITS_EVAL:
        d = parts[sp]
        y = TB.y_banda(d)
        out["distribucion"][sp] = {"n": int(len(y)), **{c: float((y == i).mean()) for i, c in enumerate(TB.CLASES)}}
        out["metricas"][sp] = TB.bootstrap(y, {m: p[sp] for m, p in b["preds"].items()}, d["persona_key"].to_numpy(), n_boot[sp], 7,
                                           [("cb_bandas", "frecuencias")])
        log(f"bandas {sp}: logloss {out['metricas'][sp]['cb_bandas']['logloss']['punto']:.4f} frente a "
            f"{out['metricas'][sp]['frecuencias']['logloss']['punto']:.4f}")
    # aggregated forecasts: test, and valid + test (more groups reach the thresholds)
    vt = pd.concat([parts["valid"], parts["test"]], ignore_index=True)
    marcos = {"test": (parts["test"], b["preds"]["cb_bandas"]["test"], b["preds"]["frecuencias"]["test"]),
              "valid_test": (vt, np.vstack([b["preds"]["cb_bandas"]["valid"], b["preds"]["cb_bandas"]["test"]]),
                             np.vstack([b["preds"]["frecuencias"]["valid"], b["preds"]["frecuencias"]["test"]]))}
    for nombre, (d, P, Pb) in marcos.items():
        y = TB.y_banda(d)
        prog = d["cod_programa"].astype(object)
        fac = FA.facultad_de(prog, programas)
        pers = d["persona_key"].to_numpy()
        tp = TB.tabla_grupos(prog.to_numpy(), y, P, Pb, pers, n_boot=min(boot, 500), seed=11)
        for f in tp["filas"]:
            f["nombre"] = str(programas.loc[f["grupo"], "nombre_programa"]) if f["grupo"] in programas.index else ""
            f["facultad"] = str(programas.loc[f["grupo"], "facultad_nombre"]) if f["grupo"] in programas.index else ""
        out["grupos"][nombre] = {"programa": tp, "facultad": TB.tabla_grupos(fac.to_numpy(), y, P, Pb, pers, n_boot=min(boot, 500), seed=13)}
        log(f"bandas {nombre}: {tp['resumen']['grupos_listados']} programas listados")
    return out


def resumen_split(df: pd.DataFrame) -> Dict:
    out = {}
    for s in TD.SPLITS:
        d = df[df["split"] == s]
        out[s] = {"n": int(len(d)), "reprobados": int(d["y"].sum()), "tasa_reprobacion": float(d["y"].mean()),
                  "personas": int(d["persona_key"].nunique()), "cursos": int(d["codigo_asignatura"].nunique()),
                  "grupos_persona_periodo": int(len(d.groupby(["persona_key", "periodo"], observed=True)))}
    return out


def descriptivo(df: pd.DataFrame) -> Dict:
    out: Dict = {"split": resumen_split(df), "cobertura": {}, "por_periodo": {}, "por_oportunidad": {}}
    for s in TD.SPLITS:
        d = df[df["split"] == s]
        out["cobertura"][s] = {
            "en_malla": float(d["en_malla"].mean()), "malla_conocida": float(d["malla_conocida"].mean()),
            "info_prereq": float(d["info_prereq"].mean()),
            "con_prerrequisitos": float((d["n_prereq"] > 0).mean()),
            "con_prerrequisitos_entre_info": float((d.loc[d["info_prereq"] == 1, "n_prereq"] > 0).mean()),
            "tiene_docente": float(d["tiene_docente"].mean()), "con_historia_curso": float((d["n_hist_curso"] > 0).mean()),
            "repetido": float((d["n_prev_curso"] > 0).mean()), "oportunidad_mayor_1": float((d["oportunidad"] > 1).mean()),
        }
    pp = df.groupby("periodo", observed=True).agg(n=("y", "size"), tasa=("y", "mean"))
    out["por_periodo"] = {k: {"n": int(v.n), "tasa_reprobacion": float(v.tasa)} for k, v in pp.iterrows()}
    op = df.assign(op=df["oportunidad"].clip(upper=3)).groupby(["split", "op"], observed=True).agg(
        n=("y", "size"), tasa=("y", "mean"))
    out["por_oportunidad"] = {f"{s}|{int(o)}": {"n": int(v.n), "tasa_reprobacion": float(v.tasa)}
                              for (s, o), v in op.iterrows()}
    return out


def tabla_subgrupo(d: pd.DataFrame, y: np.ndarray, p: np.ndarray, col, n_min: int) -> List[Dict]:
    valores = col(d) if callable(col) else d[col].astype(object).where(d[col].notna(), "sin_dato").astype(str)
    rows = []
    for valor, idx in pd.Series(valores).groupby(valores.to_numpy() if hasattr(valores, "to_numpy") else valores
                                                  ).indices.items():
        if len(idx) < n_min:
            continue
        yg, pg = y[idx], p[idx]
        ap = float(average_precision_score(yg, pg)) if 0 < yg.sum() < len(yg) else float("nan")
        auc = float(roc_auc_score(yg, pg)) if 0 < yg.sum() < len(yg) else float("nan")
        rows.append({"grupo": str(valor), "n": int(len(idx)), "tasa_observada": float(yg.mean()),
                     "riesgo_medio": float(pg.mean()), "brecha_calibracion": float(pg.mean() - yg.mean()),
                     "ap": ap, "roc_auc": auc})
    return sorted(rows, key=lambda r: r["grupo"])


def subgrupos(d: pd.DataFrame, y: np.ndarray, p: np.ndarray) -> Dict[str, List[Dict]]:
    sem = d["sem_malla"].map(lambda v: "fuera_de_malla" if pd.isna(v) else f"{int(min(v, 10)):02d}")
    op = d["oportunidad"].map(lambda v: "sin_dato" if pd.isna(v) else "1" if v <= 1 else "2" if v == 2 else "3+")
    return {
        "programa": tabla_subgrupo(d, y, p, "cod_programa", 500),
        "sem_malla": tabla_subgrupo(d, y, p, lambda x: sem, 100),
        "oportunidad": tabla_subgrupo(d, y, p, lambda x: op, 100),
        "sexo": tabla_subgrupo(d, y, p, "sexo_equidad", 100),
        "en_malla": tabla_subgrupo(d, y, p, lambda x: x["en_malla"].map({1.0: "en_malla", 0.0: "fuera_de_malla"}), 100),
        "info_prereq": tabla_subgrupo(d, y, p, lambda x: x["info_prereq"].map({1.0: "con_info", 0.0: "sin_info"}), 100),
    }


def entrenar_todo(df: pd.DataFrame, conn, seeds, log, solo=None) -> Dict:
    import torch
    parts = TD.particion(df)
    tr, va, te, po = (parts[s] for s in TD.SPLITS)
    ytr, yva = tr["y"].to_numpy(), va["y"].to_numpy()
    preds: Dict[str, Dict[str, np.ndarray]] = {s: {} for s in SPLITS_EVAL}
    tiempos: Dict[str, float] = {}
    info: Dict[str, Dict] = {}
    por_semilla: Dict[str, List] = {}

    def guardar(nombre, fn):
        for s in SPLITS_EVAL:
            preds[s][nombre] = fn(parts[s])

    def quiere(n):
        return solo is None or n in solo

    # 1 baseline
    guardar("baseline", lambda d: (1.0 - d["tasa_hist_curso_suav"]).to_numpy("float64"))
    tiempos["baseline"] = 0.0

    # 2/3 logistic regression and CatBoost on the nested sets
    for nombre in ("a", "b", "c", "d"):
        num, cat = TD.CONJUNTOS[nombre]
        prep = TD.PreprocesadorT2(num, cat).fit(tr)
        if quiere(f"lr_{nombre}"):
            t0 = time.perf_counter()
            Xtr = prep.transform(tr)
            Xva = prep.transform(va)
            m, inf = logistica.ajustar(Xtr, ytr, Xva, yva, grid_c=(0.0003, 0.001, 0.003, 0.01, 0.03, 0.3), pesos=(None,))
            del Xtr
            guardar(f"lr_{nombre}", lambda d, m=m: m.predict_proba(prep.transform(d))[:, 1])
            tiempos[f"lr_{nombre}"] = time.perf_counter() - t0
            info[f"lr_{nombre}"] = {"C": inf["C"], "ap_valid": inf["ap_valid"], "n_variables": int(Xva.shape[1])}
            log(f"lr_{nombre}: C={inf['C']} AP valid={inf['ap_valid']:.4f} ({tiempos[f'lr_{nombre}']:.0f} s)")
            del Xva
        if quiere(f"cb_{nombre}"):
            t0 = time.perf_counter()
            Ctr, Cva = prep.transform_catboost(tr), prep.transform_catboost(va)
            cms, its, ind = [], [], []
            for s in seeds:
                cb = cb_ajustar(Ctr, ytr, Cva, yva, cat, s)
                cms.append(cb), its.append(int(cb.get_best_iteration()))
            guardar(f"cb_{nombre}", lambda d: np.mean([cb_predecir(c, prep.transform_catboost(d), cat) for c in cms], axis=0))
            tiempos[f"cb_{nombre}"] = time.perf_counter() - t0
            info[f"cb_{nombre}"] = {"mejores_iteraciones": its, "n_variables": len(num) + len(cat),
                                    "params": {k: str(v) for k, v in CB_PARAMS.items()}}
            log(f"cb_{nombre}: iteraciones={its} ({tiempos[f'cb_{nombre}']:.0f} s)")
            if nombre == "c":
                imp = pd.Series(np.mean([c.get_feature_importance() for c in cms], axis=0), index=num + cat)
                info["cb_c"]["importancia_top15"] = {k: float(v) for k, v in imp.sort_values(ascending=False).head(15).items()}
            del Ctr, Cva, cms

    # 3b control: course identity as a categorical
    if quiere("cb_c_id"):
        num, cat = TD.CONJUNTOS["c_id"]
        prep = TD.PreprocesadorT2(num, cat).fit(tr)
        t0 = time.perf_counter()
        Ctr, Cva = prep.transform_catboost(tr), prep.transform_catboost(va)
        cms = [cb_ajustar(Ctr, ytr, Cva, yva, cat, s) for s in seeds]
        guardar("cb_c_id", lambda d: np.mean([cb_predecir(c, prep.transform_catboost(d), cat) for c in cms], axis=0))
        tiempos["cb_c_id"] = time.perf_counter() - t0
        info["cb_c_id"] = {"mejores_iteraciones": [int(c.get_best_iteration()) for c in cms]}
        log(f"cb_c_id: {info['cb_c_id']['mejores_iteraciones']} ({tiempos['cb_c_id']:.0f} s)")
        del Ctr, Cva, cms

    # 4 course graph: self-supervised embeddings -> CatBoost (d')
    malla, pre, stats = cargar_grafo_db(conn)
    nodos = pd.Index(pd.unique(pd.concat([df["codigo_asignatura"].astype(object), malla["codigo_asignatura"],
                                           pre["codigo_requisito"], pre["codigo_asignatura"]]).dropna()))
    tr_nodo = G.indices(nodos, tr["codigo_asignatura"].astype(object))
    grp_tr = M2.reconstruir_grupos(tr["persona_key"], tr["periodo"])
    co = G.pares_coinscripcion(grp_tr, tr_nodo)
    d_grafo = G.construir_datos(nodos, malla, pre, stats, co)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    info["grafo"] = {"n_nodos": int(len(nodos)), "n_aristas_prerrequisito": int(len(d_grafo.aristas)),
                     "n_pares_coinscripcion": int(len(co)), "min_coinscripcion": G.MIN_COOC,
                     "nodos_con_malla": int((d_grafo.x_num[:, -2] == 0).sum())}
    enl = []
    for s in seeds:
        r = G.entrenar_enlaces(d_grafo, semilla=s, device=dev)
        enl.append({k: r[k] for k in ("ap_enlaces", "auc_enlaces", "ap_grado", "auc_grado", "n_val", "segundos")})
        if s == seeds[0]:
            emb = r["embeddings"]
    info["grafo"]["enlaces"] = enl
    log(f"grafo: {info['grafo']['n_nodos']} nodos, {info['grafo']['n_aristas_prerrequisito']} aristas, "
        f"{len(co)} pares de coinscripcion; enlaces AP={[round(e['ap_enlaces'], 3) for e in enl]}")
    if quiere("cb_cemb"):
        num, cat = TD.CONJUNTOS["c"]
        prep = TD.PreprocesadorT2(num, cat).fit(tr)
        nombres_emb = [f"emb_{i}" for i in range(emb.shape[1])]

        def con_emb(d):
            x = prep.transform_catboost(d)
            e = pd.DataFrame(emb[G.indices(nodos, d["codigo_asignatura"].astype(object))], columns=nombres_emb,
                             index=x.index)
            return pd.concat([x, e], axis=1)

        t0 = time.perf_counter()
        Ctr, Cva = con_emb(tr), con_emb(va)
        cms = [cb_ajustar(Ctr, ytr, Cva, yva, cat, s) for s in seeds]
        guardar("cb_cemb", lambda d: np.mean([cb_predecir(c, con_emb(d), cat) for c in cms], axis=0))
        tiempos["cb_cemb"] = time.perf_counter() - t0
        info["cb_cemb"] = {"mejores_iteraciones": [int(c.get_best_iteration()) for c in cms], "dim_embedding": len(nombres_emb)}
        log(f"cb_cemb: {info['cb_cemb']['mejores_iteraciones']} ({tiempos['cb_cemb']:.0f} s)")
        del Ctr, Cva, cms

    # 5 end-to-end networks on set c
    num, cat = TD.CONJUNTOS["c"]
    prep = TD.PreprocesadorT2(num, cat).fit(tr)

    def conj(d):
        return G.ConjuntoT2(prep.transform_num(d), prep.transform_cat_codes(d),
                            G.indices(nodos, d["codigo_asignatura"].astype(object)), d["y"].to_numpy())

    ctr, cva = conj(tr), conj(va)
    cjs = {s: conj(parts[s]) for s in SPLITS_EVAL}
    for nombre, modo in NOMBRES_NN.items():
        if not quiere(nombre):
            continue
        usar_co = nombre != "nn_gnn_prereq"
        pv = {s: [] for s in SPLITS_EVAL}
        runs, ind = [], []
        for s in seeds:
            r = G.entrenar(ctr, cva, prep.cardinalidades(), d_grafo, modo, s, dev, usar_co=usar_co,
                           eval_cada=NN_EVAL_CADA, paciencia=NN_PACIENCIA)
            pr = {sp: G.predecir(r["model"], cjs[sp], r["grafo_t"], r["adj"], dev) for sp in SPLITS_EVAL}
            for sp in SPLITS_EVAL:
                pv[sp].append(pr[sp])
            ind.append({sp: M2.puntuales(parts[sp]["y"].to_numpy(), pr[sp],
                                         M2.reconstruir_grupos(parts[sp]["persona_key"], parts[sp]["periodo"]))
                        for sp in ("valid", "test")})
            runs.append({k: v for k, v in r.items() if k not in ("model", "grafo_t", "adj")})
            log(f"{nombre} seed={s}: AP valid={r['ap_valid']:.4f} epoca={r['mejor_epoca']:.2f}/{r['epocas']:.2f} "
                f"{r['segundos']:.0f} s gpu={r['gpu_pico_mb']:.0f} MB")
            del r
        for sp in SPLITS_EVAL:
            preds[sp][nombre] = np.mean(pv[sp], axis=0)
        por_semilla[nombre] = ind
        tiempos[nombre] = float(sum(r["segundos"] for r in runs))
        info[nombre] = {"semillas": [{k: v for k, v in r.items() if k != "hist_ap"} for r in runs],
                        "gpu_pico_mb": max(r["gpu_pico_mb"] for r in runs), "hidden": list(G.HIDDEN),
                        "batch": G.BATCH, "lr": G.LR, "weight_decay": G.WD, "paciencia_evaluaciones": NN_PACIENCIA,
                        "evaluar_cada_pasos": NN_EVAL_CADA}
    # 6 P55 ablation: course statistics weighted toward the recent past (set c, same model otherwise)
    tabla_cursos = None
    for nombre, modo in (("cb_c_decay", "decaimiento"), ("cb_c_vent", "ventana")):
        if not quiere(nombre):
            continue
        if tabla_cursos is None:
            tabla_cursos = cargar_tabla_cursos(conn)
        t0 = time.perf_counter()
        pr = {s: con_estadisticas_recientes(parts[s], tabla_cursos, modo) for s in TD.SPLITS}
        num, cat = TD.CONJUNTOS["c"]
        prep2 = TD.PreprocesadorT2(num, cat).fit(pr["train"])
        Ctr, Cva = prep2.transform_catboost(pr["train"]), prep2.transform_catboost(pr["valid"])
        cms = [cb_ajustar(Ctr, ytr, Cva, yva, cat, s) for s in seeds]
        for sp in SPLITS_EVAL:
            preds[sp][nombre] = np.mean([cb_predecir(c, prep2.transform_catboost(pr[sp]), cat) for c in cms], axis=0)
        tiempos[nombre] = time.perf_counter() - t0
        info[nombre] = {"mejores_iteraciones": [int(c.get_best_iteration()) for c in cms], "modo": modo,
                        "vida_media_anios": VIDA_MEDIA_ANIOS, "ventana_anios": VENTANA_ANIOS, "columnas_reemplazadas": DV.COLUMNAS}
        log(f"{nombre}: {info[nombre]['mejores_iteraciones']} ({tiempos[nombre]:.0f} s)")
        del pr, Ctr, Cva, cms

    # 7 grade bands (P74 / P84): CatBoost multiclass on the better of (b) and (c) by the validation AP of the binary models
    bandas = None
    if quiere("cb_bandas"):
        ap_v = {c: average_precision_score(yva, preds["valid"][f"cb_{c}"]) for c in ("b", "c") if f"cb_{c}" in preds["valid"]}
        conjunto = max(ap_v, key=ap_v.get) if ap_v else "c"
        bandas = entrenar_bandas(parts, conjunto, seeds[0], log)
        tiempos["cb_bandas"] = bandas["segundos"]
        info["cb_bandas"] = bandas["info"]
    return {"parts": parts, "preds": preds, "tiempos": tiempos, "info": info, "por_semilla": por_semilla, "bandas": bandas}


def incorporar_previo(res: Dict, nombre: str) -> Dict:
    """Keep the predictions, timings and info of the models that were not retrained (same snapshot rows, checked)."""
    prev = json.loads((S.ARTEFACTOS / f"{nombre}.json").read_text(encoding="utf-8"))
    for sp in SPLITS_EVAL:
        z = np.load(S.ARTEFACTOS / "preds" / f"t2_{sp}.npz")
        if not np.array_equal(z["intento_id"], res["parts"][sp]["intento_id"].to_numpy()):
            raise RuntimeError(f"previous predictions of {sp} do not match the current snapshot rows")
        for n in z.files:
            if n != "intento_id" and n not in res["preds"][sp]:
                res["preds"][sp][n] = z[n]
    res["tiempos"] = {**prev["tiempos_s"], **res["tiempos"]}
    res["info"] = {**prev["info"], **res["info"]}
    res["por_semilla"] = {**prev["semillas"], **res["por_semilla"]}
    return res


def pares_comparacion(preds_valid: Dict[str, np.ndarray], yva: np.ndarray) -> List:
    cbs = [m for m in preds_valid if m.startswith("cb_") and m not in ("cb_c_id", "cb_cemb")]
    mejor_cb = max(cbs, key=lambda m: average_precision_score(yva, preds_valid[m])) if cbs else None
    pares = [("lr_a", "baseline"), ("lr_b", "lr_a"), ("lr_c", "lr_b"), ("lr_d", "lr_c"),
             ("cb_a", "baseline"), ("cb_b", "cb_a"), ("cb_c", "cb_b"), ("cb_d", "cb_c"),
             ("cb_cemb", "cb_c"), ("cb_c_id", "cb_c"), ("cb_cemb", "cb_c_id"), ("cb_b", "baseline"),
             ("nn_gnn", "nn_mlp"), ("nn_gnn", "nn_ninguno"), ("nn_gnn", "nn_gnn_prereq"), ("nn_mlp", "nn_ninguno"),
             ("nn_gnn", "cb_c"), ("cb_c", "lr_c"), ("cb_c", "baseline"), ("lr_b", "baseline"), ("cb_d", "cb_b"),
             ("cb_cemb", "cb_b"), ("nn_gnn_prereq", "cb_c"), ("nn_ninguno", "cb_c"),
             ("cb_c_decay", "cb_c"), ("cb_c_vent", "cb_c"), ("cb_c_decay", "cb_c_vent")]
    if mejor_cb:
        pares += [("nn_gnn", mejor_cb), (mejor_cb, "baseline"), (mejor_cb, "lr_c")]
    return [(a, b) for a, b in dict.fromkeys(pares) if a in preds_valid and b in preds_valid], mejor_cb


def evaluar(res: Dict, boot: int, log) -> Dict:
    parts, preds = res["parts"], res["preds"]
    pares, mejor_cb = pares_comparacion(preds["valid"], parts["valid"]["y"].to_numpy())
    out: Dict = {"mejor_catboost_valid": mejor_cb, "pares": [list(p) for p in pares]}
    for sp in SPLITS_EVAL:
        d = parts[sp]
        y = d["y"].to_numpy()
        g = M2.reconstruir_grupos(d["persona_key"], d["periodo"])
        t0 = time.perf_counter()
        nb = boot if sp != "posterior" else min(boot, 300)
        out[sp] = M2.bootstrap(y, preds[sp], g, n_boot=nb, seed=7, pares=pares)
        out[sp]["__azar"] = M2.referencia_azar(y, g)
        out[sp]["__n_boot"] = nb
        log(f"bootstrap {sp}: {nb} remuestreos, {time.perf_counter() - t0:.0f} s")
    yte = parts["test"]["y"].to_numpy()
    out["calibracion_test"] = {n: M2.tabla_confiabilidad(yte, p) for n, p in preds["test"].items()}
    claves = [m for m in ("baseline", "cb_b", "cb_c", "cb_cemb", mejor_cb, "nn_gnn") if m in preds["test"]]
    out["subgrupos_test"] = {m: subgrupos(parts["test"], yte, preds["test"][m]) for m in dict.fromkeys(claves)}
    # AP by period (stability) for the main models
    per = parts["test"]["periodo"].astype(str).to_numpy()
    out["ap_por_periodo_test"] = {
        m: {pp: float(average_precision_score(yte[per == pp], preds["test"][m][per == pp])) for pp in sorted(set(per))}
        for m in dict.fromkeys(claves)}
    if res.get("bandas"):
        out["bandas"] = evaluar_bandas(res, boot, log)
    return out


def guardar_preds(parts, preds, bandas=None):
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    for sp in SPLITS_EVAL:
        np.savez_compressed(S.ARTEFACTOS / "preds" / f"t2_{sp}.npz", intento_id=parts[sp]["intento_id"].to_numpy(),
                            **{n: p for n, p in preds[sp].items()})
        if bandas:
            np.savez_compressed(S.ARTEFACTOS / "preds" / f"t2_bandas_{sp}.npz", intento_id=parts[sp]["intento_id"].to_numpy(),
                                **{n: p[sp].astype("float32") for n, p in bandas["preds"].items()})


def registrar_mlflow(res: Dict, ev: Dict, snapshot_hash: str, etiqueta: str) -> None:
    mlflow = S.iniciar_mlflow()
    mlflow.set_experiment(EXPERIMENTO_T2)
    codigo = S.version_codigo()
    for nombre in res["preds"]["test"]:
        met = {}
        for sp in ("valid", "test", "posterior"):
            for m_, v in ev[sp][nombre].items():
                met[f"{sp}_{m_}"] = v["punto"]
                met[f"{sp}_{m_}_lo"], met[f"{sp}_{m_}_hi"] = v["lo"], v["hi"]
        met["segundos_entrenamiento"] = res["tiempos"].get(nombre, 0.0)
        params = {"modelo": nombre, "n_train": len(res["parts"]["train"]), "n_valid": len(res["parts"]["valid"]),
                  "n_test": len(res["parts"]["test"]),
                  **{k: json.dumps(v)[:240] for k, v in res["info"].get(nombre, {}).items() if k != "semillas"}}
        S.registrar(mlflow, f"{etiqueta}_{nombre}", params, met,
                    {"hash_snapshot": snapshot_hash, "version_codigo": codigo, "tarea": "T2", "evento": "reprobacion"})


def parsear(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train and evaluate the T2 benchmark.")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--salida", default="resultados_t2")
    ap.add_argument("--solo", nargs="*", default=None, help="subset of models (development only)")
    ap.add_argument("--reusar", default=None,
                    help="artefact name of a previous complete run: its predictions/info are kept for the models not in --solo")
    ap.add_argument("--muestra", type=int, default=None, help="train on a random fraction 1/N of TRAIN groups (smoke test)")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    try:
        from pipelines.common.db import dev_connection

        t_ini = time.perf_counter()
        with dev_connection() as conn:
            df = TD.cargar(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t2_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
                cur.execute("SELECT clave, valor, nota FROM neural_mart.snapshot_t2_resumen WHERE clave LIKE 'embudo_%' ORDER BY 1")
                embudo = [{"paso": r[2], "n": int(r[1])} for r in cur.fetchall()]
            print(f"snapshot cargado: {len(df):,} filas, RAM pico {ram_pico_mb()} MB", flush=True)
            if args.muestra:
                keep = df["split"] != "train"
                tr = df[df["split"] == "train"]
                pers = tr["persona_key"].drop_duplicates().sample(frac=1 / args.muestra, random_state=0)
                df = df[keep | df["persona_key"].isin(pers)].reset_index(drop=True)
            res = entrenar_todo(df, conn, SEMILLAS[: args.seeds], lambda m: print(m, flush=True), args.solo)
            res["programas"] = FA.cargar_programas(conn)
        if args.reusar:
            res = incorporar_previo(res, args.reusar)
        ev = evaluar(res, args.boot, lambda m: print(m, flush=True))
        out = {"snapshot_hash": snapshot_hash, "version_codigo": S.version_codigo(), "embudo": embudo,
               "descriptivo": descriptivo(df), "evaluacion": ev, "tiempos_s": res["tiempos"], "info": res["info"],
               "semillas": res["por_semilla"], "ram_pico_mb": ram_pico_mb(),
               "segundos_totales": time.perf_counter() - t_ini}
        if args.reusar:                       # time and memory of the kept models come from the previous run
            prev = json.loads((S.ARTEFACTOS / f"{args.reusar}.json").read_text(encoding="utf-8"))
            out["segundos_totales"] += prev["segundos_totales"]
            out["ram_pico_mb"] = max(out["ram_pico_mb"] or 0.0, prev["ram_pico_mb"] or 0.0)
        S.ARTEFACTOS.mkdir(exist_ok=True)
        guardar_preds(res["parts"], res["preds"], res.get("bandas"))
        if not args.muestra and not args.reusar:
            registrar_mlflow(res, ev, snapshot_hash, args.salida)
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
