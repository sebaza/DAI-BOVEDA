"""T2 ablation of the new variables of 18-11-2026 (P117-P127) under the selection rule D114 (docs/09_benchmark_t2.md section 14).

``python -m evaluation.run_nuevas_t2`` trains CatBoost (3 seeds) and the logistic regression on the kept feature set ``c`` plus the new
variables (the student's average in the courses of the same department and the performance of the previous regular semester) and one
CatBoost per block (diagnostic). The kept model (``cb_c``) is NOT retrained: its saved predictions are read (and checked against the
rows of the snapshot), so the comparison is against the exact model that is published.

Decision (D114): chosen on VALID with AP; a candidate replaces ``cb_c`` only if the paired valid difference (cluster bootstrap by
student-period, the one of the T2 benchmark) has an interval that excludes 0 in its favour; ties keep the simpler model; test and
posterior only confirm. Writes AGGREGATES to ``artefactos/resultados_t2_nuevas.json`` and predictions to ``artefactos/preds/t2_nuevas_*.npz``
(gitignored). The files of the kept model are not touched.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from models import logistica, seguimiento as S, t2_data as TD
from pipelines.snapshots import features_t2 as F2
from . import metrics_t2 as M2
from .run_t2 import CB_PARAMS, SEMILLAS, SPLITS_EVAL, cb_ajustar, cb_predecir, ram_pico_mb

KEPT = "cb_c"
PRIMARIOS = ("lr_c_nuevas", "cb_c_nuevas")
SIMPLICIDAD = {"lr": 0, "cb": 1}
BLOQUES_T2 = {"depto": ["prom_depto", "n_depto", "dif_prom_depto"], "semprev": ["prom_sem_prev", "tasa_sem_prev"]}


def decision_d114(ev_valid: Dict, kept: str, candidatos: Sequence[str]) -> Dict:
    """D114 on valid (``metrics_t2.bootstrap`` output: paired differences are ``__delta__a__b``)."""
    filas = []
    for c in candidatos:
        d = ev_valid[f"__delta__{c}__{kept}"]["ap"]
        filas.append({"modelo": c, "ap_valid": ev_valid[c]["ap"]["punto"], "delta_ap": d["punto"], "lo": d["lo"], "hi": d["hi"],
                      "ic_excluye_cero_a_favor": bool(d["lo"] > 0)})
    elegibles = [f for f in filas if f["ic_excluye_cero_a_favor"]]
    if not elegibles:
        return {"kept": kept, "decision": "se_conserva", "modelo": kept, "candidatos": filas}
    mejor = sorted(elegibles, key=lambda f: (-round(f["ap_valid"], 6), SIMPLICIDAD[f["modelo"][:2]]))[0]
    return {"kept": kept, "decision": "reemplaza", "modelo": mejor["modelo"], "candidatos": filas}


def fusionar_resultados(prev: Dict, nuevo: Dict, modelos: Sequence[str], extras: Dict[str, Dict]) -> Dict:
    """Copy of ``resultados_t2.json`` (``prev``) with ``modelos`` added from ``resultados_t2_nuevas.json`` (``nuevo``): their metrics with
    intervals, the paired differences of the pairs of ``nuevo`` that involve them, calibration, subgroups, AP by period, info and times.

    The bootstrap of both runs uses the same seed, number of replicates and groups, and its draws do not depend on the set of models,
    so the kept model must reproduce its own entries exactly; if not, nothing is merged (``RuntimeError``).
    """
    import copy

    out = copy.deepcopy(prev)
    ev, evn = out["evaluacion"], nuevo["evaluacion"]
    for sp in SPLITS_EVAL:
        a, b = ev[sp][KEPT]["ap"], evn[sp][KEPT]["ap"]
        if any(abs(a[k] - b[k]) > 1e-9 for k in ("punto", "lo", "hi")):
            raise RuntimeError(f"the kept model does not reproduce its {sp} interval; the two runs are not comparable")
    pares = [tuple(p) for p in evn["pares"] if p[0] in modelos or p[1] in modelos]
    for sp in SPLITS_EVAL:
        for m in modelos:
            ev[sp][m] = evn[sp][m]
        for a_, b_ in pares:
            clave = f"__delta__{a_}__{b_}"
            if clave in evn[sp]:
                ev[sp][clave] = evn[sp][clave]
    ev["pares"] = [list(p) for p in dict.fromkeys([tuple(p) for p in ev.get("pares", [])] + pares)]
    for bloque, por_modelo in extras.items():
        ev.setdefault(bloque, {}).update(por_modelo)
    for m in modelos:
        out["info"][m] = nuevo["info"][m]
        if m in (nuevo.get("tiempos_s") or {}):
            out["tiempos_s"][m] = nuevo["tiempos_s"][m]
    out["adopcion_d114_nuevas"] = {"modelos": list(modelos), "decision": evn["d114"], "snapshot_hash": nuevo["snapshot_hash"]}
    return out


def adoptar(log) -> None:
    """Writes the adopted models where the benchmark readers look: ``artefactos/resultados_t2.json`` and ``artefactos/preds/t2_*.npz``.
    Originals are kept in ``artefactos/antes_nuevas/``; the kept models' arrays are copied unchanged."""
    import shutil
    from pipelines.common.db import dev_connection
    from . import run_t2 as R

    ev = json.loads((S.ARTEFACTOS / "resultados_t2_nuevas.json").read_text(encoding="utf-8"))
    if ev["evaluacion"]["d114"]["decision"] != "reemplaza":
        raise RuntimeError("D114 did not replace the kept model: nothing to adopt")
    modelos = tuple(m for m in PRIMARIOS)
    prev_json = S.ARTEFACTOS / "resultados_t2.json"
    prev = json.loads(prev_json.read_text(encoding="utf-8"))
    with dev_connection() as conn:
        parts = TD.particion(TD.cargar(conn))
    nuevas = {sp: np.load(S.ARTEFACTOS / "preds" / f"t2_nuevas_{sp}.npz") for sp in SPLITS_EVAL}
    previas = {sp: np.load(S.ARTEFACTOS / "preds" / f"t2_{sp}.npz") for sp in SPLITS_EVAL}
    for sp in SPLITS_EVAL:
        for z in (nuevas[sp], previas[sp]):
            if not np.array_equal(z["intento_id"], parts[sp]["intento_id"].to_numpy()):
                raise RuntimeError(f"the predictions of {sp} do not match the snapshot rows")
    yte = parts["test"]["y"].to_numpy()
    per = parts["test"]["periodo"].astype(str).to_numpy()
    from sklearn.metrics import average_precision_score
    extras = {"calibracion_test": {}, "subgrupos_test": {}, "ap_por_periodo_test": {}}
    for m in modelos:
        p = nuevas["test"][m].astype("float64")
        extras["calibracion_test"][m] = M2.tabla_confiabilidad(yte, p)
        extras["subgrupos_test"][m] = R.subgrupos(parts["test"], yte, p)
        extras["ap_por_periodo_test"][m] = {pp: float(average_precision_score(yte[per == pp], p[per == pp])) for pp in sorted(set(per))}
    fusion = fusionar_resultados(prev, ev, modelos, extras)
    for f_ in [prev_json] + [S.ARTEFACTOS / "preds" / f"t2_{sp}.npz" for sp in SPLITS_EVAL]:
        (S.ARTEFACTOS / "antes_nuevas").mkdir(exist_ok=True)
        copia = S.ARTEFACTOS / "antes_nuevas" / (f_.stem + ".antes_nuevas" + f_.suffix)
        if not copia.exists():
            shutil.copy2(f_, copia)
    for sp in SPLITS_EVAL:
        todo = {n: previas[sp][n] for n in previas[sp].files}
        for m in modelos:
            todo[m] = nuevas[sp][m]
        np.savez_compressed(S.ARTEFACTOS / "preds" / f"t2_{sp}.npz", **todo)
    prev_json.write_text(json.dumps(fusion, indent=1, default=float), encoding="utf-8")
    log(f"adoptados {modelos}: resultados_t2.json y preds/t2_*.npz actualizados (originales: artefactos/antes_nuevas/)")


def cargar_previas(parts: Dict[str, pd.DataFrame], modelos: Sequence[str]) -> Dict[str, Dict[str, np.ndarray]]:
    """Saved predictions of the kept models, checked row by row against the current snapshot."""
    out: Dict[str, Dict[str, np.ndarray]] = {s: {} for s in SPLITS_EVAL}
    for sp in SPLITS_EVAL:
        z = np.load(S.ARTEFACTOS / "preds" / f"t2_{sp}.npz")
        if not np.array_equal(z["intento_id"], parts[sp]["intento_id"].to_numpy()):
            raise RuntimeError(f"saved predictions of {sp} do not match the snapshot rows")
        for m in modelos:
            out[sp][m] = z[m]
    return out


def entrenar(parts: Dict[str, pd.DataFrame], semillas, log) -> Dict:
    tr, va = parts["train"], parts["valid"]
    ytr, yva = tr["y"].to_numpy(), va["y"].to_numpy()
    preds: Dict[str, Dict[str, np.ndarray]] = {s: {} for s in SPLITS_EVAL}
    info: Dict[str, Dict] = {}
    tiempos: Dict[str, float] = {}
    cat = TD.CONJUNTOS["c"][1]
    conjuntos = {"c_nuevas": TD.CONJUNTOS["c_nuevas"][0],
                 **{f"c_{b}": TD.CONJUNTOS["c"][0] + cols for b, cols in BLOQUES_T2.items()}}
    for nombre, num in conjuntos.items():
        prep = TD.PreprocesadorT2(num, cat).fit(tr)
        t0 = time.perf_counter()
        if nombre == "c_nuevas":                              # logistic regression of the primary candidate
            Xtr, Xva = prep.transform(tr), prep.transform(va)
            m, inf = logistica.ajustar(Xtr, ytr, Xva, yva, grid_c=(0.0003, 0.001, 0.003, 0.01, 0.03, 0.3), pesos=(None,))
            for sp in SPLITS_EVAL:
                preds[sp]["lr_c_nuevas"] = m.predict_proba(prep.transform(parts[sp]))[:, 1]
            tiempos["lr_c_nuevas"] = time.perf_counter() - t0
            info["lr_c_nuevas"] = {"C": inf["C"], "ap_valid": inf["ap_valid"], "n_variables": int(Xva.shape[1])}
            del Xtr, Xva
            log(f"lr_c_nuevas: C={inf['C']} AP valid={inf['ap_valid']:.4f} ({time.perf_counter() - t0:.0f} s)")
        t0 = time.perf_counter()
        Ctr, Cva = prep.transform_catboost(tr), prep.transform_catboost(va)
        cms = [cb_ajustar(Ctr, ytr, Cva, yva, cat, s) for s in semillas]
        for sp in SPLITS_EVAL:
            preds[sp][f"cb_{nombre}"] = np.mean([cb_predecir(c, prep.transform_catboost(parts[sp]), cat) for c in cms], axis=0)
        tiempos[f"cb_{nombre}"] = time.perf_counter() - t0
        info[f"cb_{nombre}"] = {"mejores_iteraciones": [int(c.get_best_iteration()) for c in cms], "n_variables": len(num) + len(cat),
                                "params": {k: str(v) for k, v in CB_PARAMS.items()}}
        imp = pd.Series(np.mean([c.get_feature_importance() for c in cms], axis=0), index=num + cat)
        info[f"cb_{nombre}"]["importancia_top15"] = {k: float(v) for k, v in imp.sort_values(ascending=False).head(15).items()}
        info[f"cb_{nombre}"]["importancia_nuevas"] = {k: float(imp[k]) for k in F2.FEATURE_COLS_NUEVAS_T2 if k in imp.index}
        log(f"cb_{nombre}: iteraciones={info[f'cb_{nombre}']['mejores_iteraciones']} ({time.perf_counter() - t0:.0f} s)")
        del Ctr, Cva, cms
    return {"preds": preds, "info": info, "tiempos": tiempos}


def evaluar(parts: Dict[str, pd.DataFrame], preds: Dict[str, Dict[str, np.ndarray]], n_boot: int, log) -> Dict:
    nuevos = list(dict.fromkeys(m for m in preds["valid"] if m not in (KEPT, "lr_c", "baseline")))
    pares = [(c, KEPT) for c in nuevos] + [("lr_c_nuevas", "lr_c"), ("cb_c_nuevas", "lr_c_nuevas"), (KEPT, "baseline")]
    out: Dict = {"kept": KEPT, "pares": [list(p) for p in dict.fromkeys(pares)]}
    for sp in SPLITS_EVAL:
        d = parts[sp]
        y = d["y"].to_numpy()
        g = M2.reconstruir_grupos(d["persona_key"], d["periodo"])
        nb = n_boot if sp != "posterior" else min(n_boot, 300)
        t0 = time.perf_counter()
        out[sp] = M2.bootstrap(y, preds[sp], g, n_boot=nb, seed=7, pares=list(dict.fromkeys(pares)))
        out[sp]["__n_boot"] = nb
        log(f"bootstrap {sp}: {nb} remuestreos, {time.perf_counter() - t0:.0f} s")
    out["d114"] = decision_d114(out["valid"], KEPT, PRIMARIOS)
    out["d114_bloques_diagnostico"] = decision_d114(out["valid"], KEPT, [n for n in nuevos if n not in PRIMARIOS])
    yte = parts["test"]["y"].to_numpy()
    out["calibracion_test"] = {n: M2.tabla_confiabilidad(yte, p) for n, p in preds["test"].items() if n in (KEPT, "cb_c_nuevas")}
    return out


def parsear(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="T2 ablation of the new variables under D114.")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--salida", default="resultados_t2_nuevas")
    ap.add_argument("--adoptar", action="store_true",
                    help="no training: merge the candidates into resultados_t2.json and preds/t2_*.npz (only if D114 replaced the kept model)")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    log = lambda m: print(m, flush=True)   # noqa: E731
    if args.adoptar:
        try:
            adoptar(log)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        return 0
    try:
        from pipelines.common.db import dev_connection

        t_ini = time.perf_counter()
        with dev_connection() as conn:
            df = TD.cargar(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT valor FROM neural_mart.snapshot_t2_resumen WHERE clave = 'hash_datos'")
                snapshot_hash = cur.fetchone()[0]
        log(f"snapshot cargado: {len(df):,} filas, RAM pico {ram_pico_mb()} MB")
        parts = TD.particion(df)
        res = entrenar(parts, SEMILLAS[: args.seeds], log)
        previas = cargar_previas(parts, (KEPT, "lr_c", "baseline"))
        preds = {sp: {**previas[sp], **res["preds"][sp]} for sp in SPLITS_EVAL}
        ev = evaluar(parts, preds, args.boot, log)
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / "preds").mkdir(exist_ok=True)
        for sp in SPLITS_EVAL:
            np.savez_compressed(S.ARTEFACTOS / "preds" / f"t2_nuevas_{sp}.npz", intento_id=parts[sp]["intento_id"].to_numpy(),
                                **{n: p.astype("float32") for n, p in res["preds"][sp].items()})
        n = {sp: {"n": int(len(parts[sp])), "eventos": int(parts[sp]["y"].sum())} for sp in ("train", *SPLITS_EVAL)}
        out = {"snapshot_hash": snapshot_hash, "version_codigo": S.version_codigo(), "n": n, "evaluacion": ev, "info": res["info"],
               "tiempos_s": res["tiempos"],
               "ram_pico_mb": ram_pico_mb(), "segundos_totales": time.perf_counter() - t_ini}
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
