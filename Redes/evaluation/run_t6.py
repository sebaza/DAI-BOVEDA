"""Benchmark runner for T6 ("matricula en postgrado UCN despues del egreso"), docs/12_benchmark_t6.md.

``python -m evaluation.run_t6`` reads ``neural_mart.snapshot_t6`` and:
1. counts events by partition and by horizon and applies the viability gate (``rules_t6.viable``);
2. always writes the DESCRIPTIVE analysis: cumulative incidence (Kaplan-Meier) overall, by partition, by year of egreso, by sex,
   by academic strata, by programa and by facultad, with a bootstrap grouped by person; groups under 100 units or 10 events
   are suppressed;
3. only if the gate allows it, fits the historical incidence by program (baseline) and a penalized Cox model (profile /
   profile + academic record), evaluates them at 1, 2 and 4 years with grouped bootstrap and paired differences, and builds the
   aggregate forecasts by programa and facultad. CatBoost and the MLP are not trained below their own event thresholds.
Writes AGGREGATES to ``artefactos/resultados_t6.json`` (gitignored); individual predictions only as gitignored npz.
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
from evaluation import metrics_t6 as M6
from evaluation import subgrupos as SG
from evaluation.run_t2 import ram_pico_mb
from models import seguimiento as S
from models import t6_data as TD
from models import t6_modelos as MD
from models.data import Preprocesador
from pipelines.snapshots import rules_t6 as R6

EXPERIMENTO_T6 = "t6_postgrado_ucn"
TAUS = R6.HORIZONTES
TAU_PRINCIPAL = 2                # one year: the only horizon with complete follow-up in the three partitions
TAUS_GRUPOS = (2, 4)
BASE = "baseline_programa"
MODELOS = (BASE, "cox_perfil", "cox_agg")
PARES = [("cox_perfil", BASE), ("cox_agg", BASE), ("cox_agg", "cox_perfil")]


def version_codigo_t6() -> str:
    from pathlib import Path

    raiz = Path(S.RAIZ)
    h = hashlib.sha256(S.version_codigo().encode())
    for p in sorted([raiz / "pipelines" / "snapshots" / n for n in ("rules_t3.py", "features_t3.py", "rules_t6.py", "features_t6.py", "t6.py")]
                    + [raiz / "models" / n for n in ("t3_data.py", "t6_data.py", "t6_modelos.py")]
                    + [raiz / "evaluation" / n for n in ("metrics_t6.py", "run_t6.py")]):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------------------------
FUENTE_PRINCIPAL = "estados"          # P86 (DAI, 13-11-2026): ``ban_estados_academicos_pos`` is the postgrado reference source
NIVELES = ("magister", "doctorado", "otro")
CELDA_MIN = 10                        # a cell of 1 to 9 units is never shown


def con_evento(snap: pd.DataFrame, fuente: str) -> pd.DataFrame:
    """The snapshot read with the event of ``fuente``. ``estados`` (primary): first enrolled semester (state ``M``) of the
    postgrado state source, excluding the units already enrolled at or before the egreso semester (not at risk of a FIRST
    enrollment, D65). ``matricula`` (sensitivity run): the previous event from ``matricula_postgrado``, untouched."""
    if fuente == "matricula":
        return snap
    if fuente != "estados":
        raise ValueError(fuente)
    d = snap.loc[~snap["previo_estados"].astype(bool)].copy()
    d["evento"] = d["evento_estados"].astype("int64")
    d["tiempo"] = d["tiempo_estados"].astype("int64")
    return d.reset_index(drop=True)


def eventos_por_nivel(snap: pd.DataFrame) -> Dict:
    """Events by program level (magister, doctorado, otro) overall and by partition; cells of 1 to 9 are omitted."""
    e = snap.loc[snap["evento"] == 1]
    nivel = e["nivel_estados"].astype(object).where(e["nivel_estados"].notna(), "otro")
    total = {n: int((nivel == n).sum()) for n in NIVELES}
    por = {s: {n: int(((nivel == n) & (e["split"] == s)).sum()) for n in NIVELES} for s in R6.SPLITS}
    ocultar = lambda v: {k: x for k, x in v.items() if x >= CELDA_MIN or x == 0}      # noqa: E731
    return {"total": ocultar(total), "por_particion": {s: ocultar(v) for s, v in por.items()},
            "celdas_ocultas": int(sum(0 < x < CELDA_MIN for v in [total, *por.values()] for x in v.values()))}


def incidencia_por_nivel(snap: pd.DataFrame, n_boot: int) -> Dict:
    """Cause-specific cumulative incidence of the first enrollment of each level (an enrollment of another level censors the
    unit at its time) with a bootstrap grouped by person; a level with fewer than ``CELDA_MIN`` events is not estimated."""
    idxs = M45.remuestreos(snap["persona_key"].to_numpy(), n_boot, seed=17)
    nivel = snap["nivel_estados"].astype(object).where(snap["nivel_estados"].notna(), "otro")
    out: Dict = {}
    for n in NIVELES:
        ev = ((snap["evento"] == 1) & (nivel == n)).astype(int)
        if ev.sum() < CELDA_MIN:
            out[n] = {"eventos": None, "incidencia": None}
            continue
        out[n] = {"eventos": int(ev.sum()), "incidencia": M6.incidencia_con_ic(snap["tiempo"].to_numpy(), ev.to_numpy(), TAUS, idxs)}
    return out


def eventos_por_particion(snap: pd.DataFrame) -> Dict[str, int]:
    return {s: int(snap.loc[snap["split"] == s, "evento"].sum()) for s in R6.SPLITS}


def eventos_por_horizonte(snap: pd.DataFrame, taus=TAUS) -> Dict[int, Dict[str, Dict[str, int]]]:
    """Units followed up to each horizon and their events within it, by partition (the binary-at-horizon sample)."""
    out: Dict[int, Dict[str, Dict[str, int]]] = {}
    for tau in taus:
        out[int(tau)] = {}
        for s in R6.SPLITS:
            d = snap.loc[snap["split"] == s]
            el, y = R6.resultado_horizonte(d["tiempo"], d["evento"], d["seguimiento"], tau)
            out[int(tau)][s] = {"n": int(el.sum()), "eventos": int(y[el].sum())}
    return out


def viabilidad(eventos: Dict[str, int]) -> Dict:
    return {"eventos": dict(eventos), "clasico": R6.viable(eventos, R6.MIN_EVENTOS_CLASICO),
            "catboost": R6.viable(eventos, R6.MIN_EVENTOS_CATBOOST), "red": R6.viable(eventos, R6.MIN_EVENTOS_RED),
            "umbrales": {"clasico": R6.MIN_EVENTOS_CLASICO, "catboost": R6.MIN_EVENTOS_CATBOOST, "red": R6.MIN_EVENTOS_RED}}


def estratos(snap: pd.DataFrame) -> Dict[str, pd.Series]:
    """Labels of the strata of the descriptive tables (sex, year of egreso, titulacion, academic average, delay)."""
    prom = snap["promedio_evaluado"]
    rango = prom.rank(method="first")
    terciles = pd.qcut(rango, 3, labels=["T1 (más bajo)", "T2", "T3 (más alto)"]).astype(object)
    terciles = terciles.where(prom.notna(), "sin dato")
    exceso = snap["exceso_duracion"]
    dur = pd.Series(np.where(exceso <= 0, "en la duración nominal o antes", "con atraso"), index=snap.index, dtype=object)
    dur = dur.where(exceso.notna(), "sin dato")
    return {
        "sexo": snap["sexo_equidad"].astype(object).where(snap["sexo_equidad"].notna(), "sin dato"),
        "anio_egreso": snap["anio_egreso"].astype(str),
        "titulado_al_corte": pd.Series(np.where(snap["titulado_al_corte"].astype(bool), "titulación U al corte", "sin titulación al corte"),
                                       index=snap.index, dtype=object),
        "promedio": terciles, "duracion": dur,
    }


def decidir_conservado(mejor: Optional[str], delta_ap: Optional[Dict[str, float]]) -> str:
    """The Cox model replaces the historical baseline only if its paired AP difference has an interval above zero."""
    if mejor is None or delta_ap is None:
        return BASE
    lo = delta_ap.get("lo")
    return mejor if lo is not None and lo == lo and lo > 0 else BASE


# ---------------------------------------------------------------------------------------------
# descriptive analysis
# ---------------------------------------------------------------------------------------------
def _incidencia_global(d: pd.DataFrame, idxs, columna_t="tiempo", columna_e="evento") -> Dict:
    r = M6.incidencia_con_ic(d[columna_t].to_numpy(), d[columna_e].to_numpy(), TAUS, idxs)
    return {"n": int(len(d)), "eventos": int(d[columna_e].sum()),
            "en_riesgo": {int(t): int((d["seguimiento"] >= t).sum()) for t in TAUS}, "incidencia": r}


def descriptivo(snap: pd.DataFrame, programas: pd.DataFrame, n_boot: int, log) -> Dict:
    idxs = M45.remuestreos(snap["persona_key"].to_numpy(), n_boot, seed=3)
    out: Dict = {"global": _incidencia_global(snap, idxs), "particion": {}, "estratos": {}, "grupos": {}}
    for s in R6.SPLITS:
        d = snap.loc[snap["split"] == s]
        out["particion"][s] = _incidencia_global(d, M45.remuestreos(d["persona_key"].to_numpy(), n_boot, seed=5))
        out["particion"][s]["seguimiento"] = {"min": int(d["seguimiento"].min()), "mediana": float(d["seguimiento"].median()),
                                              "max": int(d["seguimiento"].max())}
    out["sensibilidad_cualquier_fila"] = {
        "global": _incidencia_global(snap, idxs, "tiempo_cualquier_fila", "evento_cualquier_fila"),
        "eventos_por_particion": {s: int(snap.loc[snap["split"] == s, "evento_cualquier_fila"].sum()) for s in R6.SPLITS}}
    for nombre, serie in estratos(snap).items():
        out["estratos"][nombre] = M6.tabla_incidencia_grupos(serie.to_numpy(), snap["tiempo"], snap["evento"], TAUS_GRUPOS, idxs,
                                                             seguimiento=snap["seguimiento"])
    fac = snap["facultad_nombre"]                      # faculty NAMES in every table (stage B)
    for nombre, col in (("programa", snap["cod_programa"]), ("facultad", fac)):
        t = M6.tabla_incidencia_grupos(col.to_numpy(), snap["tiempo"], snap["evento"], TAUS_GRUPOS, idxs, seguimiento=snap["seguimiento"])
        if nombre == "programa":
            for f in t["filas"]:
                if f["grupo"] in programas.index:
                    f["nombre"] = str(programas.loc[f["grupo"], "nombre_programa"])
        out["grupos"][nombre] = t
    out["por_horizonte"] = eventos_por_horizonte(snap)
    log(f"descriptivo: {len(snap)} unidades, {int(snap['evento'].sum())} eventos, programas reportables "
        f"{out['grupos']['programa']['resumen']['grupos_reportables']} de {out['grupos']['programa']['resumen']['grupos_total']}")
    return out


# ---------------------------------------------------------------------------------------------
# models (only when the gate allows them)
# ---------------------------------------------------------------------------------------------
def entrenar(parts: Dict[str, pd.DataFrame], log) -> Dict:
    tr, va, te = parts["train"], parts["valid"], parts["test"]
    preds: Dict[str, Dict[str, np.ndarray]] = {m: {} for m in MODELOS}
    info: Dict[str, Dict] = {}
    tiempos: Dict[str, float] = {}
    t0 = time.perf_counter()
    base = MD.BaselinePrograma(TAUS).fit(tr)
    for s, d in (("valid", va), ("test", te)):
        preds[BASE][s] = base.predict(d)
    tiempos[BASE] = time.perf_counter() - t0
    info[BASE] = {"programas_con_curva_propia": len(base.tabla), "min_n": base.min_n}
    for nombre, grupo in (("cox_perfil", "perfil"), ("cox_agg", "perfil+academico")):
        t0 = time.perf_counter()
        num, cat = TD.GRUPOS[grupo]
        TD.verificar_sin_fuga(num, cat)
        prep = Preprocesador(num, cat).fit(tr)
        X = {s: prep.transform(d).astype("float64") for s, d in (("train", tr), ("valid", va), ("test", te))}
        modelo, i = MD.ajustar_cox(TAUS, X["train"], tr["tiempo"].to_numpy(), tr["evento"].to_numpy(),
                                   X["valid"], va["tiempo"].to_numpy(), va["evento"].to_numpy(), tau=4)
        for s, d in (("valid", va), ("test", te)):
            preds[nombre][s] = modelo.predict(X[s])
        tiempos[nombre] = time.perf_counter() - t0
        info[nombre] = {"grupo": grupo, "columnas_entrada": int(X["train"].shape[1]), **{k: v for k, v in i.items() if k != "busqueda"},
                        "busqueda": i["busqueda"]}
        log(f"{nombre}: penalizador {i['penalizador']} (C valid {i['c_valid']:.3f}), {X['train'].shape[1]} columnas, {tiempos[nombre]:.1f} s")
    return {"preds": preds, "info": info, "tiempos": tiempos}


def evaluar_modelos(parts: Dict[str, pd.DataFrame], res: Dict, n_boot: int, programas: pd.DataFrame, log) -> Dict:
    va, te = parts["valid"], parts["test"]
    out: Dict = {"horizontes": {}}
    for s, d in (("valid", va), ("test", te)):
        out["horizontes"][s] = {}
        for j, tau in enumerate(TAUS):
            scores = {m: res["preds"][m][s][:, j] for m in MODELOS}
            out["horizontes"][s][str(tau)] = M6.evaluar_horizonte(d["tiempo"], d["evento"], d["seguimiento"], scores, tau,
                                                                  d["persona_key"].to_numpy(), n_boot, PARES)
    # the model that would replace the baseline is chosen on valid at the main horizon (AP)
    j0 = TAUS.index(TAU_PRINCIPAL)
    el_v, y_v = R6.resultado_horizonte(va["tiempo"], va["evento"], va["seguimiento"], TAU_PRINCIPAL)
    ap_valid = {m: M.metricas(y_v[el_v], res["preds"][m]["valid"][el_v, j0])["ap"] for m in ("cox_perfil", "cox_agg")}
    mejor = max(ap_valid, key=lambda m: (ap_valid[m] if ap_valid[m] == ap_valid[m] else -1.0))
    delta = out["horizontes"]["test"][str(TAU_PRINCIPAL)]["pares"].get(f"{mejor}__vs__{BASE}", {}).get("ap")
    conservado = decidir_conservado(mejor, delta)
    out["seleccion"] = {"tau": TAU_PRINCIPAL, "ap_valid": ap_valid, "mejor_cox": mejor, "delta_ap_vs_baseline": delta,
                        "conservado": conservado}
    log(f"conservado: {conservado} (mejor Cox en valid: {mejor}, AP valid {ap_valid})")
    # calibration, groups and fairness at the main horizon
    el_t, y_t = R6.resultado_horizonte(te["tiempo"], te["evento"], te["seguimiento"], TAU_PRINCIPAL)
    out["calibracion_test"] = {m: M6.agrupar_calibracion(M6.calibracion_horizonte(
        te["tiempo"], te["evento"], te["seguimiento"], res["preds"][m]["test"][:, j0], TAU_PRINCIPAL)) for m in {conservado, BASE}}
    vt = pd.concat([va.assign(_s="valid"), te.assign(_s="test")], ignore_index=True)
    p_c = np.vstack([res["preds"][conservado]["valid"], res["preds"][conservado]["test"]])[:, j0]
    p_b = np.vstack([res["preds"][BASE]["valid"], res["preds"][BASE]["test"]])[:, j0]
    out["grupos"] = {}
    for etiqueta, d, pc, pb in (("test", te, res["preds"][conservado]["test"][:, j0], res["preds"][BASE]["test"][:, j0]),
                                ("valid_test", vt, p_c, p_b)):
        el, y = R6.resultado_horizonte(d["tiempo"], d["evento"], d["seguimiento"], TAU_PRINCIPAL)
        dd, yy, pc_, pb_ = d.loc[el].reset_index(drop=True), y[el].astype(int), pc[el], pb[el]
        idxs = M45.remuestreos(dd["persona_key"].to_numpy(), n_boot, seed=11)
        t_ = {"programa": GR.tabla_agregada(dd["cod_programa"].to_numpy(), yy, pc_, pb_, idxs),
              "facultad": GR.tabla_agregada(dd["facultad_nombre"].to_numpy(), yy, pc_, pb_, idxs),
              "n": int(len(dd)), "eventos": int(yy.sum())}
        for fila in t_["programa"]["filas"]:
            if fila["grupo"] in programas.index:
                fila["nombre"] = str(programas.loc[fila["grupo"], "nombre_programa"])
        out["grupos"][etiqueta] = t_
        if etiqueta == "valid_test":
            sub = SG.tabla_grupo(dd, yy, pc_, "sexo_equidad", SG.N_MIN_GRUPO)
            for fila in sub:
                fila["eventos"] = int(round(fila["tasa_observada"] * fila["n"]))
            out["sexo"] = {"tabla": sub, "brecha_fm": SG.brechas_sexo(sub), "n": int(len(dd)), "eventos": int(yy.sum()), "tau": TAU_PRINCIPAL}
    log("evaluado: horizontes, grupos y sexo")
    return out


def guardar_preds(parts, res) -> None:
    (S.ARTEFACTOS / "preds").mkdir(parents=True, exist_ok=True)
    for sp in ("valid", "test"):
        datos = {f"{m}__tau{t}": res["preds"][m][sp][:, j].astype("float32") for m in MODELOS for j, t in enumerate(TAUS)}
        np.savez_compressed(S.ARTEFACTOS / "preds" / f"t6_{sp}.npz", episodio_id=parts[sp]["episodio_id"].to_numpy(), **datos)


def registrar_mlflow(res: Dict, ev: Dict, snapshot_hash: str, etiqueta: str, n: Dict[str, int]) -> None:
    mlflow = S.iniciar_mlflow()
    mlflow.set_experiment(EXPERIMENTO_T6)
    codigo = version_codigo_t6()
    for nombre in MODELOS:
        met = {"segundos_entrenamiento": res["tiempos"].get(nombre, 0.0)}
        for s in ("valid", "test"):
            for tau, r in ev["horizontes"][s].items():
                m = r["modelos"].get(nombre)
                if not m:
                    continue
                for k, v in m.items():
                    met[f"{s}_tau{tau}_{k}"] = v["punto"]
                    if s == "test":
                        met[f"{s}_tau{tau}_{k}_lo"], met[f"{s}_tau{tau}_{k}_hi"] = v["lo"], v["hi"]
        params = {"modelo": nombre, "n_train": n["train"], "n_valid": n["valid"], "n_test": n["test"],
                  **{k: json.dumps(v)[:240] for k, v in res["info"][nombre].items() if k != "busqueda"}}
        S.registrar(mlflow, f"{etiqueta}_{nombre}", params, met,
                    {"hash_snapshot": snapshot_hash, "version_codigo": codigo, "tarea": "T6", "evento": "matricula_postgrado_ucn"})


def analizar(snap: pd.DataFrame, programas: pd.DataFrame, n_boot: int, log, snapshot_hash: str, salida: str, guardar: bool) -> Dict:
    """Gate, descriptive analysis and (if viable) models of one event source; ``guardar`` writes predictions and MLflow runs."""
    viab = viabilidad(eventos_por_particion(snap))
    log(f"viabilidad: {viab}")
    out: Dict = {"viabilidad": viab, "n_unidades": int(len(snap)), "eventos": int(snap["evento"].sum())}
    out["descriptivo"] = descriptivo(snap, programas, n_boot, log)
    parts = TD.particion(snap)
    out["n_particion"] = {s: int(len(d)) for s, d in parts.items()}
    if viab["clasico"]:
        res = entrenar(parts, log)
        out["info"], out["tiempos_s"] = res["info"], res["tiempos"]
        out["modelos"] = evaluar_modelos(parts, res, n_boot, programas, log)
        if guardar:
            guardar_preds(parts, res)
            registrar_mlflow(res, out["modelos"], snapshot_hash, salida, {s: len(d) for s, d in parts.items()})
    else:
        out["modelos"] = None
        log("benchmark no viable: solo análisis descriptivo")
    return out


def parsear(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Descriptive analysis and (if viable) benchmark of T6.")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--salida", default="resultados_t6")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear(argv)
    try:
        from pipelines.common.db import dev_connection

        t_ini = time.perf_counter()
        log = lambda m: print(m, flush=True)             # noqa: E731
        with dev_connection() as conn:
            snap = TD.cargar(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT clave, valor FROM neural_mart.snapshot_t6_resumen")
                resumen = dict(cur.fetchall())
                cur.execute("SELECT count(*), count(DISTINCT persona_key), count(DISTINCT cod_programa) "
                            "FROM neural_core.matricula_postgrado WHERE estado_matricula = 'MATRICULADO'")
                fuente = dict(zip(("filas_matriculadas", "personas_matriculadas", "programas"), cur.fetchone()))
                cur.execute("SELECT min(periodo), max(periodo) FROM neural_core.matricula_postgrado")
                fuente["periodo_min"], fuente["periodo_max"] = cur.fetchone()
            programas = FA.cargar_programas(conn)
        snap["facultad_nombre"] = FA.facultad_de(snap["cod_programa"], programas)
        print(f"snapshot cargado: {len(snap):,} filas, RAM pico {ram_pico_mb()} MB", flush=True)
        snapshot_hash = resumen["hash_datos"]
        embudo = {k.replace("embudo_", ""): int(v) for k, v in resumen.items() if k.startswith("embudo_")}
        out = {"snapshot_hash": snapshot_hash, "version_codigo": version_codigo_t6(), "periodo_cierre": resumen["periodo_cierre"],
               "embudo": embudo, "fuente_postgrado": fuente, "n_boot": args.boot, "taus": list(TAUS), "tau_principal": TAU_PRINCIPAL,
               "fuente_evento": FUENTE_PRINCIPAL}
        principal = con_evento(snap, FUENTE_PRINCIPAL)
        out["unidades_excluidas_previo_estados"] = int(len(snap) - len(principal))
        out.update(analizar(principal, programas, args.boot, log, snapshot_hash, args.salida, guardar=True))
        out["eventos_por_nivel"] = eventos_por_nivel(principal)
        out["incidencia_por_nivel"] = incidencia_por_nivel(principal, args.boot)
        # sensitivity: the previous event (enrollment status of ``matricula_postgrado``), same code and thresholds
        log("--- sensibilidad: evento de matricula_postgrado ---")
        out["sensibilidad_matricula"] = analizar(con_evento(snap, "matricula"), programas, args.boot, log, snapshot_hash, args.salida,
                                                 guardar=False)
        out["ram_pico_mb"] = ram_pico_mb()
        out["gpu_usada"] = False
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
