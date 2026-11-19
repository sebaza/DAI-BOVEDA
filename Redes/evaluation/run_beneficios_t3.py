"""Ablation "+ beneficios" of T3 (16-11-2026, decisions D100-D109; docs/10_benchmark_t3.md section 11).

``python -m evaluation.run_beneficios_t3`` keeps the splits (cohort train 2015-2017 / valid 2018 / test 2019-2020), the metrics
(C-index truncated at 10/12/14 semesters since admission, IBS up to slot 12, calibration), the episode bootstrap with paired
differences on the SAME resamples, and the models of the official T3 benchmark: person-period logistic regression, person-period
CatBoost (3 seeds) and the GRU of discrete competing risks (3 seeds, GPU). On top of the official feature set (``adm+agg`` =
``acad``) it adds three benefit blocks under each point-in-time rule of ``rules_beneficios_t3``:

* ``fin``     financing facts (gratuity, credit, grants, merit, amounts, years with gratuity, year-over-year losses);
* ``expcap``  the expiry-of-gratuity (N+1 / N+2) and Capstone flags alone (the hypothesis of the weekly plan);
* ``todo``    both.

Cuts: the official ``k = 2, 4`` (``snapshot_t3``) and the late cuts ``k = 8, 10`` (``snapshot_t3_ext``), where the flags of the
hypothesis exist at all (they appear 4-6 years after admission). ``banda_decil`` is never a model feature (fairness only).

Adoption criterion (D100): a benefit model of the OFFICIAL cuts replaces the one without benefits only if, under the default rule
``previo``, its paired DeltaC(12) on valid has a 95 % interval above 0 or its DeltaIBS on valid has an interval below 0, and on test
neither metric moves significantly the wrong way and the metric that qualified does not move the wrong way in its point estimate.
The sensitivity rule ``con_t`` and the late cuts are reported but never adopted.

Writes AGGREGATES to ``artefactos/resultados_t3_beneficios.json`` (gitignored); individual predictions only as gitignored npz.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from evaluation import facultades as FA
from evaluation import metrics_t3 as M3
from evaluation.run_t3 import HORIZONTES, IBS_HASTA, SEMILLAS, ibs_valid
from models import seguimiento as S
from models import t3_data as TD
from models import t3_discreto as DT
from models import t3_redes as NR
from models.data import Preprocesador
from pipelines.snapshots import features_beneficios_t3 as FT
from pipelines.snapshots import rules_beneficios_t3 as RT

EVAL_SPLITS = ("valid", "test")
FAMILIAS = ("lr", "cb", "gru")
NOMBRE_FAMILIA = {"lr": "Logística persona-período", "cb": "CatBoost persona-período", "gru": "Red GRU de riesgos discretos"}
BLOQUES = ("fin", "expcap", "todo")
NOMBRE_BLOQUE = {"acad": "ingreso + agregados", "fin": "+ financiamiento", "expcap": "+ expiración y Capstone",
                 "todo": "+ beneficios (todo)"}
COBERTURA_MIN = 0.05                   # a (k, rule) with less data than this share of the cut rows is "not applicable"
TAU = 12
N_MIN_GRUPO, EVENTOS_MIN, N_SUPRESION = 100, 10, 10
COLS_BEN = [c for c in FT.COLS_BENEFICIOS_T3 if c != "anio_ben"] + ["anio_ben", "banda_decil_eq"]


# ---------------------------------------------------------------------------------------------------- pure helpers
def nombre_modelo(fam: str, regla: Optional[str], bloque: str) -> str:
    return f"{fam}_acad" if bloque == "acad" else f"{fam}_{regla}_{bloque}"


def conjunto_columnas(bloque: str) -> Tuple[List[str], List[str]]:
    num, cat = TD.GRUPOS["adm+agg"]
    if bloque == "acad":
        return list(num), list(cat)
    return list(num) + FT.columnas_numericas(bloque), list(cat)


def favorable(metrica: str, valor: float) -> bool:
    """Is a paired difference a gain? C-index: positive; integrated Brier score: negative."""
    return valor > 0 if metrica.startswith("c_") else valor < 0


def desfavorable_significativo(metrica: str, d: Dict[str, float]) -> bool:
    return d["hi"] < 0 if metrica.startswith("c_") else d["lo"] > 0


def favorable_significativo(metrica: str, d: Dict[str, float]) -> bool:
    return d["lo"] > 0 if metrica.startswith("c_") else d["hi"] < 0


def decidir(delta_valid: Dict[str, Dict[str, float]], delta_test: Dict[str, Dict[str, float]],
            metricas: Sequence[str] = (f"c_{TAU}", "ibs")) -> Dict:
    """Adoption criterion (D100) for one paired comparison ``benefit model - model without benefits``."""
    calificadas = [m for m in metricas if favorable_significativo(m, delta_valid[m])]
    no_peor_test = (bool(calificadas)
                    and all(favorable(m, delta_test[m]["punto"]) for m in calificadas)
                    and not any(desfavorable_significativo(m, delta_test[m]) for m in metricas))
    return {"metricas_que_califican_en_valid": calificadas, "no_peor_en_test": no_peor_test,
            "adopta": bool(calificadas) and no_peor_test}


def suprimir_grupos(filas: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
    """Keep the groups with n >= N_MIN_GRUPO and >= EVENTOS_MIN events; count the rest (never list a group with n < N_SUPRESION)."""
    visibles = [f for f in filas if f["n"] >= N_MIN_GRUPO and f["eventos"] >= EVENTOS_MIN]
    return visibles, {"grupos": len(filas), "visibles": len(visibles),
                      "bajo_umbral": sum(1 for f in filas if N_SUPRESION <= f["n"] and f not in visibles),
                      "suprimidos_n_menor_10": sum(1 for f in filas if f["n"] < N_SUPRESION)}


def tabla_grupos(d: pd.DataFrame, F_base: np.ndarray, F_ben: np.ndarray, k: int, grupos: pd.Series, tau: int = TAU) -> Dict:
    """Per group, among the episodes followed up to ``tau``: n, events, observed and predicted incidence, C(tau) and AUC of both models."""
    el, y = M3.resultado_horizonte(d["tiempo"], d["causa"], d["seguimiento_max"], tau)
    col = tau - k - 1
    t, c = d["tiempo"].to_numpy(), d["causa"].to_numpy()
    g = pd.Series(np.asarray(grupos, dtype=object), index=d.index)
    g = g.where(g.notna(), "sin_dato").astype(str)
    filas = []
    for valor, idx in g[el].groupby(g[el]).indices.items():
        pos = np.flatnonzero(el)[idx]
        n, ev = int(len(pos)), int(y[pos].sum())
        fila = {"grupo": str(valor), "n": n, "eventos": ev}
        if n >= N_SUPRESION:
            fila.update({"observada": float(y[pos].mean())})
            if n >= N_MIN_GRUPO and ev >= EVENTOS_MIN:
                for tag, F in (("base", F_base), ("ben", F_ben)):
                    fila[f"predicha_{tag}"] = float(F[pos, col].mean())
                    fila[f"c_{tag}"] = M3.c_index_uno(t[pos], c[pos], F[pos, col], tau=tau)
                    fila[f"auc_{tag}"] = M3.auc(y[pos], F[pos, col])
        filas.append(fila)
    visibles, resumen = suprimir_grupos(filas)
    return {"filas": sorted(visibles, key=lambda r: -r["n"]), "resumen": resumen}


# ---------------------------------------------------------------------------------------------------- data
def _leer_tabla(conn, tabla: str, texto: Sequence[str], bools: Sequence[str] = ()) -> pd.DataFrame:
    buf = io.BytesIO()
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM neural_mart.{tabla} LIMIT 0")
        cols = [d.name for d in cur.description]
    with conn.cursor() as cur:
        with cur.copy(f"COPY (SELECT * FROM neural_mart.{tabla} ORDER BY 1, 2) TO STDOUT WITH (FORMAT CSV)") as cp:
            for chunk in cp:
                buf.write(bytes(chunk))
    buf.seek(0)
    return pd.read_csv(buf, header=None, names=cols, dtype={c: "string" for c in texto}, true_values=["t"],
                       false_values=["f"], keep_default_na=False, na_values=[""])


def cargar_snapshot_ext(conn) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """The late-cut snapshot (same typing as ``t3_data.cargar``)."""
    snap = _leer_tabla(conn, "snapshot_t3_ext", TD.TEXT_COLS)
    for c in TD.BOOL_COLS:
        if c in snap:
            snap[c] = snap[c].astype("boolean")
    for c in TD.TEXT_COLS:
        if c in snap:
            snap[c] = snap[c].astype(object).where(snap[c].notna(), None)
    sem = _leer_tabla(conn, "snapshot_t3_ext_semestre", ())
    for c in ("matriculado", "interrupcion"):
        sem[c] = sem[c].astype(bool)
    return snap, sem


def cargar_beneficios(conn) -> pd.DataFrame:
    b = _leer_tabla(conn, "snapshot_t3_beneficios", ("regla", "banda_decil", "banda_decil_eq"))
    for c in ("banda_decil", "banda_decil_eq"):
        b[c] = b[c].astype(object).where(b[c].notna(), None)
    return b


def con_beneficios(snap: pd.DataFrame, ben: pd.DataFrame, regla: str) -> pd.DataFrame:
    x = snap.merge(ben.loc[ben["regla"] == regla].drop(columns="regla"), on=["episodio_id", "k"], how="left")
    if x["ben_sin_dato"].isna().any():
        raise RuntimeError("benefit snapshot out of date: rebuild it with `python -m pipelines.snapshots.t3_beneficios`")
    return x


def cobertura(parts: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    return {s: float((d["ben_sin_dato"] == 0).mean()) if len(d) else 0.0 for s, d in parts.items()}


# ---------------------------------------------------------------------------------------------------- training
def entrenar_conjunto(parts: Dict[str, pd.DataFrame], sem: pd.DataFrame, k: int, num: List[str], cat: List[str],
                      semillas: Sequence[int], log, familias: Sequence[str] = FAMILIAS, etiqueta: str = "") -> Tuple[Dict, Dict]:
    """Predictions ``F1`` of valid and test for each family on one feature set; fitted on train, tuned on valid."""
    import torch

    TD.verificar_sin_fuga(num, cat)
    tr, va = parts["train"], parts["valid"]
    prep = Preprocesador(num, cat).fit(tr)
    preds: Dict[str, Dict[str, np.ndarray]] = {f: {} for f in familias}
    info: Dict[str, Dict] = {}
    if "lr" in familias:
        t0 = time.perf_counter()
        m, inf = DT.logistica_ajustar(prep, tr, va, k)
        for s in EVAL_SPLITS:
            preds["lr"][s] = DT.logistica_cif(m, prep, parts[s], k)
        info["lr"] = {"C": inf["C"], "logloss_valid": inf["logloss_valid"], "n_variables": inf["n_variables"],
                      "segundos": time.perf_counter() - t0}
    if "cb" in familias:
        t0 = time.perf_counter()
        ms, its = [], []
        for sd in semillas:
            m, inf = DT.catboost_ajustar(prep, tr, va, k, sd)
            ms.append(m), its.append(inf["mejor_iteracion"])
        for s in EVAL_SPLITS:
            preds["cb"][s] = DT.catboost_cif(ms, prep, parts[s], k)
        info["cb"] = {"mejores_iteraciones": its, "segundos": time.perf_counter() - t0}
        del ms
    if "gru" in familias:
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        seq = {s: TD.construir_secuencias_t3(parts[s], sem, k) for s in ("train", *EVAL_SPLITS)}

        def conj(d, s):
            return NR.ConjuntoT3(prep.transform_num(d), prep.transform_cat_codes(d), d["u"].to_numpy(), d["causa"].to_numpy(), seq[s])

        ctr, cva = conj(tr, "train"), conj(va, "valid")
        cjs = {s: conj(parts[s], s) for s in EVAL_SPLITS}
        pv = {s: [] for s in EVAL_SPLITS}
        runs = []
        t0 = time.perf_counter()
        for sd in semillas:
            r = NR.entrenar(ctr, cva, prep.cardinalidades(), TD.JMAX - k, sd, dev)
            for s in EVAL_SPLITS:
                pv[s].append(NR.predecir_cif(r["model"], cjs[s], dev))
            runs.append({"nll_valid": r["nll_valid"], "mejor_epoca": r["mejor_epoca"]})
            del r
        for s in EVAL_SPLITS:
            preds["gru"][s] = np.mean(pv[s], axis=0)
        info["gru"] = {"semillas": runs, "segundos": time.perf_counter() - t0}
    log(f"k={k} {etiqueta}: " + ", ".join(f"{f} {info[f]['segundos']:.0f} s" for f in familias))
    return preds, info


# ---------------------------------------------------------------------------------------------------- one cut
def correr_k(snap: pd.DataFrame, sem: pd.DataFrame, ben: pd.DataFrame, k: int, reglas: Sequence[str], semillas, n_boot: int,
             log, familias: Sequence[str] = FAMILIAS, bloques: Sequence[str] = BLOQUES, device: Optional[str] = None,
             programas: Optional[pd.DataFrame] = None) -> Dict:
    sk = snap.loc[snap["k"] == k]
    base_parts = TD.particion(sk, k)
    res: Dict = {"k": k, "n": {s: int(len(d)) for s, d in base_parts.items()}, "cobertura": {}, "no_aplicable": [], "info": {},
                 "reglas": list(reglas), "bloques": list(bloques), "familias": list(familias)}
    preds: Dict[str, Dict[str, np.ndarray]] = {s: {} for s in EVAL_SPLITS}
    pp, inf = entrenar_conjunto(base_parts, sem, k, *conjunto_columnas("acad"), semillas, log, familias, "acad")
    for fam in familias:
        for s in EVAL_SPLITS:
            preds[s][nombre_modelo(fam, None, "acad")] = pp[fam][s]
        res["info"][nombre_modelo(fam, None, "acad")] = inf[fam]
    partes_regla: Dict[str, Dict[str, pd.DataFrame]] = {}
    for regla in reglas:
        parts = TD.particion(con_beneficios(sk, ben, regla), k)
        partes_regla[regla] = parts
        res["cobertura"][regla] = cobertura(parts)
        if min(res["cobertura"][regla]["train"], res["cobertura"][regla]["test"]) < COBERTURA_MIN:
            res["no_aplicable"].append(regla)
            log(f"k={k} regla {regla}: cobertura {res['cobertura'][regla]} < {COBERTURA_MIN}: no aplicable")
            continue
        for bloque in bloques:
            pp, inf = entrenar_conjunto(parts, sem, k, *conjunto_columnas(bloque), semillas, log, familias, f"{regla}/{bloque}")
            for fam in familias:
                nm = nombre_modelo(fam, regla, bloque)
                for s in EVAL_SPLITS:
                    preds[s][nm] = pp[fam][s]
                res["info"][nm] = inf[fam]
    modelos = list(preds["valid"])
    pares = []
    for fam in familias:
        base = nombre_modelo(fam, None, "acad")
        for regla in reglas:
            if regla in res["no_aplicable"]:
                continue
            for bloque in bloques:
                pares.append((nombre_modelo(fam, regla, bloque), base))
            if "todo" in bloques and "fin" in bloques:
                pares.append((nombre_modelo(fam, regla, "todo"), nombre_modelo(fam, regla, "fin")))
            if "todo" in bloques and "expcap" in bloques:
                pares.append((nombre_modelo(fam, regla, "todo"), nombre_modelo(fam, regla, "expcap")))
    if {"gru", "cb"} <= set(familias):
        pares.append((nombre_modelo("gru", None, "acad"), nombre_modelo("cb", None, "acad")))
    slots = np.arange(k + 1, TD.JMAX + 1)
    backend = "torch" if device else "numpy"
    res["ibs_valid"] = {m: ibs_valid(F, base_parts["valid"], k) for m, F in preds["valid"].items()}
    for s in EVAL_SPLITS:
        d = base_parts[s]
        ev = M3.Evaluador(d["tiempo"], d["causa"], d["seguimiento_max"], slots, preds[s], HORIZONTES[s], IBS_HASTA[s],
                          backend=backend, device=device)
        t0 = time.perf_counter()
        res[s] = ev.bootstrap(n_boot=n_boot, seed=7, pares=pares)
        res[s]["__n"] = int(len(d))
        res[s]["__elegibles"] = {str(h): int((d["seguimiento_max"] >= h).sum()) for h in HORIZONTES[s]}
        log(f"k={k} bootstrap {s}: {n_boot} remuestreos, {time.perf_counter() - t0:.0f} s")
    res["pares"] = [list(p) for p in pares]
    res["decisiones"] = {}
    for a, b in pares:
        if not b.endswith("_acad") or a.endswith("_acad"):
            continue
        da, db = res["valid"][f"__delta__{a}__{b}"], res["test"][f"__delta__{a}__{b}"]
        res["decisiones"][f"{a}__vs__{b}"] = decidir(da, db)
    # groups and fairness (test; GRU of each rule against the GRU without benefits, block "todo")
    if programas is not None:
        te = base_parts["test"]
        fam = "gru" if "gru" in familias else familias[0]
        res["grupos"] = {}
        for regla in reglas:
            nm = nombre_modelo(fam, regla, "todo")
            if regla in res["no_aplicable"] or nm not in preds["test"]:
                continue
            Fb, Fn = preds["test"][nombre_modelo(fam, None, "acad")], preds["test"][nm]
            dte = partes_regla[regla]["test"]
            facultad = FA.facultad_de(dte["cod_programa"], programas)
            res["grupos"][regla] = {
                "modelo": nm, "base": nombre_modelo(fam, None, "acad"),
                "programa": tabla_grupos(dte, Fb, Fn, k, dte["cod_programa"]),
                "facultad": tabla_grupos(dte, Fb, Fn, k, facultad),
                "sexo": tabla_grupos(dte, Fb, Fn, k, dte["sexo_equidad"]),
                "banda_decil": tabla_grupos(dte, Fb, Fn, k, dte["banda_decil_eq"])}
            for fila in res["grupos"][regla]["programa"]["filas"]:
                if fila["grupo"] in programas.index:
                    fila["nombre"] = str(programas.loc[fila["grupo"], "nombre_programa"])
    # observed vs predicted mean incidence at the horizons (test)
    te = base_parts["test"]
    res["incidencia_media_test"] = {}
    for tau in HORIZONTES["test"]:
        if tau <= k:
            continue
        el, y = M3.resultado_horizonte(te["tiempo"], te["causa"], te["seguimiento_max"], tau)
        res["incidencia_media_test"][str(tau)] = {"n": int(el.sum()), "observada": float(y[el].mean()),
                                                  **{m: float(preds["test"][m][el, tau - k - 1].mean()) for m in modelos}}
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(S.ARTEFACTOS / "preds" / f"t3_beneficios_k{k}.npz",
                        **{f"{s}__{m}": p.astype("float32") for s in EVAL_SPLITS for m, p in preds[s].items()},
                        episodio_valid=base_parts["valid"]["episodio_id"].to_numpy(), episodio_test=base_parts["test"]["episodio_id"].to_numpy())
    return res


def parsear(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="T3 ablation with student benefits.")
    ap.add_argument("--k", type=int, nargs="+", default=list(RT.K_BENEFICIOS))
    ap.add_argument("--reglas", nargs="+", default=list(RT.REGLAS))
    ap.add_argument("--familias", nargs="+", default=list(FAMILIAS))
    ap.add_argument("--bloques", nargs="+", default=list(BLOQUES))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--salida", default="resultados_t3_beneficios")
    ap.add_argument("--sin-gpu-bootstrap", action="store_true")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    log = lambda m: print(m, flush=True)   # noqa: E731
    try:
        import torch
        from pipelines.common.db import dev_connection

        t_ini = time.perf_counter()
        with dev_connection() as conn:
            snap_of, sem_of = TD.cargar(conn)
            snap_ext, sem_ext = cargar_snapshot_ext(conn)
            ben = cargar_beneficios(conn)
            programas = FA.cargar_programas(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t3_resumen WHERE clave = 'hash_datos'")
                hash_of = cur.fetchone()[0]
                cur.execute("SELECT valor FROM neural_mart.snapshot_t3_ext_resumen WHERE clave = 'hash_datos'")
                hash_ext = cur.fetchone()[0]
                cur.execute("SELECT valor FROM neural_mart.snapshot_t3_beneficios_resumen WHERE clave = 'hash_beneficios'")
                hash_ben = cur.fetchone()[0]
        device = None if args.sin_gpu_bootstrap or not torch.cuda.is_available() else "cuda"
        out = {"hash_snapshot": hash_of, "hash_snapshot_ext": hash_ext, "hash_beneficios": hash_ben, "version_codigo": S.version_codigo(),
               "tau": TAU, "umbrales": {"n_min_grupo": N_MIN_GRUPO, "eventos_min": EVENTOS_MIN, "supresion": N_SUPRESION},
               "por_k": {}, "ks": args.k, "reglas": args.reglas}
        for k in args.k:
            snap, sem = (snap_of, sem_of) if k in RT.K_OFICIALES else (snap_ext, sem_ext)
            t0 = time.perf_counter()
            out["por_k"][str(k)] = correr_k(snap, sem, ben, k, args.reglas, SEMILLAS[: args.seeds], args.boot, log,
                                            args.familias, args.bloques, device, programas)
            out["por_k"][str(k)]["segundos"] = time.perf_counter() - t0
            S.ARTEFACTOS.mkdir(exist_ok=True)
            (S.ARTEFACTOS / f"{args.salida}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        out["segundos_totales"] = time.perf_counter() - t_ini
        (S.ARTEFACTOS / f"{args.salida}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print(f"escrito artefactos/{args.salida}.json ({out['segundos_totales']:.0f} s)")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
