"""Model figures for EVERY group, whatever its size (plan 2026-11-18, Task 5). No model is retrained.

``python -m evaluation.grupos_todos`` rebuilds, from the gitignored saved predictions (``artefactos/preds/*.npz``) and the
labels / group columns of the localhost snapshots (``neural_mart.snapshot_t1|t2|t3|t45|t6``), one table per task, cut and kept
model, and writes AGGREGATES to ``artefactos/grupos_todos.json`` (gitignored). Dimensions are the ones of the benchmark group
tables: programa, facultad, sexo, via (admission route) and tipo_colegio (school type). There is no size or event floor:

* one row per group with ``n``, ``eventos``, ``tasa``, ``esperado`` (mean predicted risk of the kept model) and ``referencia``
  (mean of the reference model), each rate with a 95 % interval;
* ``ap`` / ``auc`` with their interval, ``None`` when the group has no events or no non-events (never NaN);
* ``pocos_casos`` = ``n < 10`` (a mark, not a filter).

Intervals come from a bootstrap that resamples PERSONS (``persona_key``): 1000 resamples, seed 0, all dimensions and metrics on the
same draws. It is vectorised: a draw is a weight per row, applied to the order of each dimension sorted once by (group, score),
so AP and ROC-AUC (ties count one half, as scikit-learn) of every group come out of cumulative sums, without re-sorting.

The kept model of T1 with course load (``cb_ben_pit``) has no saved predictions for its test rows: it is loaded (or refitted)
through ``evaluation.modelos_conservados.cargar_o_ajustar`` -- which checks max|dp| <= 1e-4 against the saved ones -- and scored in
memory; nothing is written under ``preds/``. No row, key or name is written.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from evaluation import facultades as FA
from evaluation import metrics_t3 as M3
from evaluation.grupos_facultad import (CONSERVADO_T1, CONSERVADO_T3, REF_T1, REF_T3, TAU_T3, alinear, poner_facultad, sin_nan,
                                        _leer)
from pipelines.snapshots import rules_t2 as R2

RAIZ = Path(__file__).resolve().parents[1]
N_BOOT = 1000
SEMILLA = 0
POCOS_CASOS = 10                      # mark ``pocos_casos`` for n below this; it never hides a group
# (name published, snapshot column): the dimensions of the benchmark group tables
DIMENSIONES: Tuple[Tuple[str, str], ...] = (("programa", "cod_programa"), ("facultad", "facultad"), ("sexo", "sexo_equidad"),
                                            ("via", "via_clase"), ("tipo_colegio", "tipo_colegio"))
SIN_DATO = "sin_dato"
REF_T2, MODELO_T2 = "baseline", "cb_c_nuevas"
MODELO_BANDAS, REF_BANDAS = "cb_bandas", "frecuencias"
# the event of T2 (reprobado) is the kept model's; the other three grade bands come from the band model
BANDAS_T2 = tuple(b for b in R2.BANDAS if b != "reprobado")
DIMENSIONES_BANDAS = ("programa", "facultad")                 # the dimensions of the benchmark's band tables
VARIANTE_T1_BENEFICIOS = {1: "beneficios", 2: "beneficios", 4: "extension_k4"}   # as resumen_tareas names the views
REF_T45, REF_T6 = "baseline_tasa", "baseline_programa"
COLS_DIM = ("sexo_equidad", "via_clase", "tipo_colegio")


# --------------------------------------------------------------------------------------------------- vectorised metrics
class Dimension:
    """One grouping of the rows: AP and ROC-AUC of every group under any non-negative row weights.

    The order (group, score descending) and the ends of the tie blocks are computed once; a weight vector (the number of times
    each row is drawn) then gives the metrics of the resampled data with cumulative sums only.
    """

    def __init__(self, codigos: np.ndarray, y: np.ndarray, p: np.ndarray):
        self.codigos = np.asarray(codigos, dtype="int64")
        self.G = int(self.codigos.max()) + 1 if len(self.codigos) else 0
        self.y = np.asarray(y, dtype="float64")
        p = np.asarray(p, dtype="float64")
        self.orden = np.lexsort((-p, self.codigos))
        cs, ps = self.codigos[self.orden], p[self.orden]
        fin = np.ones(len(cs), dtype=bool)
        fin[:-1] = (cs[1:] != cs[:-1]) | (ps[1:] != ps[:-1])           # last row of each tie block within a group
        self.fin = np.flatnonzero(fin)
        self.gb = cs[self.fin]
        self.inicio = np.searchsorted(cs, np.arange(self.G))
        self.primero = np.ones(len(self.fin), dtype=bool)
        self.primero[1:] = self.gb[1:] != self.gb[:-1]
        self.ys = self.y[self.orden]

    def metricas(self, w: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """``(ap, auc)`` per group for the row weights ``w``; NaN where a group has no weighted event or no weighted non-event."""
        ws = np.asarray(w, dtype="float64")[self.orden]
        tp, fp = np.cumsum(ws * self.ys), np.cumsum(ws * (1.0 - self.ys))
        tp0 = np.concatenate(([0.0], tp))[self.inicio][self.gb]
        fp0 = np.concatenate(([0.0], fp))[self.inicio][self.gb]
        tpe, fpe = tp[self.fin] - tp0, fp[self.fin] - fp0
        tpp, fpp = np.empty_like(tpe), np.empty_like(fpe)
        if len(tpe):
            tpp[0] = fpp[0] = 0.0
            tpp[1:], fpp[1:] = tpe[:-1], fpe[:-1]
            tpp[self.primero] = fpp[self.primero] = 0.0
        dtp, dfp = tpe - tpp, fpe - fpp
        den = tpe + fpe
        precision = np.divide(tpe, den, out=np.zeros_like(tpe), where=den > 0)
        pos = np.bincount(self.codigos, weights=np.asarray(w, dtype="float64") * self.y, minlength=self.G)
        neg = np.bincount(self.codigos, weights=np.asarray(w, dtype="float64") * (1.0 - self.y), minlength=self.G)
        ok = (pos > 0) & (neg > 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            ap = np.bincount(self.gb, weights=dtp * precision, minlength=self.G) / pos
            auc = np.bincount(self.gb, weights=dtp * (neg[self.gb] - fpe + 0.5 * dfp), minlength=self.G) / (pos * neg)
        return np.where(ok, ap, np.nan), np.where(ok, auc, np.nan)


def _etiquetas(valores) -> np.ndarray:
    s = pd.Series(np.asarray(valores, dtype=object))
    return s.where(s.notna(), SIN_DATO).astype(str).to_numpy()


def _valor(x) -> Optional[float]:
    x = float(x)
    return x if np.isfinite(x) else None


def _intervalo(sorteos: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """95 % percentile interval per column over the valid (non-NaN) draws; NaN where there is none."""
    lo = np.full(sorteos.shape[1], np.nan)
    hi = np.full(sorteos.shape[1], np.nan)
    con = (~np.isnan(sorteos)).any(axis=0)
    if con.any():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            q = np.nanpercentile(sorteos[:, con], [2.5, 97.5], axis=0)
        lo[con], hi[con] = q[0], q[1]
    return lo, hi


def tablas_dimensiones(dims: Mapping[str, np.ndarray], y: np.ndarray, p: np.ndarray, p_base: np.ndarray, personas: Sequence,
                       n_boot: int = N_BOOT, seed: int = SEMILLA) -> Dict[str, List[Dict]]:
    """``{dimension: rows}``: one row per group of every dimension, with the person-grouped bootstrap of all of them on the same draws."""
    y = np.asarray(y, dtype="float64")
    p = np.asarray(p, dtype="float64")
    p_base = np.asarray(p_base, dtype="float64")
    pcod, pnom = pd.factorize(np.asarray(personas))
    n_p = len(pnom)
    prep = {}
    for nombre, valores in dims.items():
        codigos, nombres = pd.factorize(_etiquetas(valores), sort=True)
        prep[nombre] = (codigos, np.asarray(nombres), Dimension(codigos, y, p))
    uno = np.ones(len(y))
    puntos, sorteos = {}, {}
    for nombre, (codigos, nombres, dim) in prep.items():
        G = len(nombres)
        n = np.bincount(codigos, minlength=G).astype("float64")
        ap, auc = dim.metricas(uno)
        puntos[nombre] = {"n": n, "ev": np.bincount(codigos, weights=y, minlength=G), "esp": np.bincount(codigos, weights=p, minlength=G) / n,
                          "ref": np.bincount(codigos, weights=p_base, minlength=G) / n, "ap": ap, "auc": auc}
        puntos[nombre]["tasa"] = puntos[nombre]["ev"] / n
        sorteos[nombre] = {m: np.full((n_boot, G), np.nan) for m in ("tasa", "esp", "ap", "auc")}
    rng = np.random.default_rng(seed)
    for b in range(n_boot):
        w = np.bincount(rng.integers(0, n_p, n_p), minlength=n_p)[pcod].astype("float64")
        for nombre, (codigos, nombres, dim) in prep.items():
            G = len(nombres)
            nb = np.bincount(codigos, weights=w, minlength=G)
            with np.errstate(invalid="ignore", divide="ignore"):
                s = sorteos[nombre]
                s["tasa"][b] = np.bincount(codigos, weights=w * y, minlength=G) / nb
                s["esp"][b] = np.bincount(codigos, weights=w * p, minlength=G) / nb
            s["ap"][b], s["auc"][b] = dim.metricas(w)
    salida: Dict[str, List[Dict]] = {}
    for nombre, (codigos, nombres, dim) in prep.items():
        pt = puntos[nombre]
        ic = {m: _intervalo(sorteos[nombre][m]) for m in ("tasa", "esp", "ap", "auc")}
        filas = []
        for g, etiqueta in enumerate(nombres):
            fila = {"grupo": str(etiqueta), "n": int(pt["n"][g]), "eventos": int(pt["ev"][g]),
                    "tasa": _valor(pt["tasa"][g]), "tasa_lo": _valor(ic["tasa"][0][g]), "tasa_hi": _valor(ic["tasa"][1][g]),
                    "esperado": _valor(pt["esp"][g]), "esperado_lo": _valor(ic["esp"][0][g]), "esperado_hi": _valor(ic["esp"][1][g]),
                    "referencia": _valor(pt["ref"][g])}
            for m, campo in (("ap", "ap"), ("auc", "auc")):
                punto = _valor(pt[m][g])
                lo, hi = (_valor(ic[m][0][g]), _valor(ic[m][1][g])) if punto is not None else (None, None)
                fila.update({campo: punto, f"{campo}_lo": lo, f"{campo}_hi": hi})
            fila["pocos_casos"] = bool(fila["n"] < POCOS_CASOS)
            filas.append(fila)
        salida[nombre] = filas
    return salida


def tabla_grupos(grupo: Sequence, y: np.ndarray, p: np.ndarray, p_base: np.ndarray, personas: Sequence, n_boot: int = N_BOOT,
                 seed: int = SEMILLA) -> List[Dict]:
    """Rows of ONE grouping (see ``tablas_dimensiones``)."""
    return tablas_dimensiones({"grupo": grupo}, y, p, p_base, personas, n_boot, seed)["grupo"]


def bloque(df: pd.DataFrame, y: np.ndarray, p: np.ndarray, p_base: np.ndarray, modelo: str, referencia: str,
           n_boot: int = N_BOOT, seed: int = SEMILLA, dimensiones: Optional[Sequence[str]] = None, **extra) -> Dict:
    """Block of one task / cut: every dimension of ``DIMENSIONES`` present in ``df`` (or only ``dimensiones``); needs ``persona_key``."""
    dims = {nombre: df[col].to_numpy() for nombre, col in DIMENSIONES
            if col in df.columns and (dimensiones is None or nombre in dimensiones)}
    y = np.asarray(y)
    return {"modelo": modelo, "referencia": referencia, "n": int(len(y)), "eventos": int(y.sum()), **extra,
            "dimensiones": tablas_dimensiones(dims, y, p, p_base, df["persona_key"].to_numpy(), n_boot, seed)}


# ------------------------------------------------------------------------------------------------------ blocks per task
def bloque_t1(snap: pd.DataFrame, preds: Mapping[str, np.ndarray], k: int, programas: pd.DataFrame, n_boot: int = N_BOOT,
              modelo: Optional[str] = None) -> Dict:
    """Test rows of cut ``k`` aligned to ``t1_k{k}.npz`` (or to the benefit ablation's file, with its own kept ``modelo``): kept
    model against ``baseline_tasa``; event = no continua."""
    modelo = modelo or CONSERVADO_T1[k]
    d = snap.loc[(snap["k"] == k) & (snap["split"] == "test") & (snap["estado_muestra"] == "observada") & snap["continua"].notna()]
    d = d.reset_index(drop=True)
    d = d.iloc[alinear(preds["episodio_test"], d)].reset_index(drop=True)
    d = poner_facultad(d, programas)
    y = (~d["continua"].astype(bool)).astype("int8").to_numpy()
    return bloque(d, y, preds[f"test__{modelo}"], preds[f"test__{REF_T1}"], modelo, REF_T1, n_boot)


def bloque_t1_corte(ev: pd.DataFrame, p: np.ndarray, p_base: np.ndarray, programas: pd.DataFrame, n_boot: int = N_BOOT,
                    modelo: str = "cb_ben_pit") -> Dict:
    """T1 with course load (k = 1, cohorts 2024 and 2025 pooled): ``ev`` are the evaluation rows with their label ``y``."""
    d = poner_facultad(ev.reset_index(drop=True), programas)
    return bloque(d, d["y"].to_numpy(), p, p_base, modelo, REF_T1, n_boot)


def bloque_t2(snap: pd.DataFrame, ids: np.ndarray, p: np.ndarray, p_base: np.ndarray, programas: pd.DataFrame,
              n_boot: int = N_BOOT) -> Dict:
    """Test attempts aligned to the saved predictions by ``intento_id``; event = reprobacion (``y``)."""
    d = snap.reset_index(drop=True)
    pos = alinear(ids, d, "intento_id")
    d = poner_facultad(d.iloc[pos].reset_index(drop=True), programas)
    return bloque(d, d["y"].to_numpy(), np.asarray(p), np.asarray(p_base), MODELO_T2, REF_T2, n_boot)


def bloques_t2_bandas(snap: pd.DataFrame, ids: np.ndarray, P: np.ndarray, F: np.ndarray, programas: pd.DataFrame,
                      n_boot: int = N_BOOT) -> Dict[str, Dict]:
    """``{"banda_<banda>": block}`` of the three grade bands that are not the task's event: attempt in the band against the band
    model's probability of it (``t2_bandas_test.npz``: columns in ``rules_t2.BANDAS`` order); reference = the frequency baseline."""
    d = snap.reset_index(drop=True)
    d = poner_facultad(d.iloc[alinear(ids, d, "intento_id")].reset_index(drop=True), programas)
    # the benchmark renormalises rows that already sum to one (CatBoost softmax in float64): the saved float32 rows are used as they
    # are, because renormalising them would add a new perturbation of their order
    P, F = np.asarray(P, dtype="float64"), np.asarray(F, dtype="float64")
    indice = {b: j for j, b in enumerate(R2.BANDAS)}
    banda = d["banda_nota"].map(indice)
    if banda.isna().any():
        raise ValueError("an attempt has no grade band")
    banda = banda.to_numpy()
    return {f"banda_{b}": bloque(d, (banda == indice[b]).astype("int8"), P[:, indice[b]], F[:, indice[b]], MODELO_BANDAS, REF_BANDAS,
                                 n_boot, dimensiones=DIMENSIONES_BANDAS, banda=b) for b in BANDAS_T2}


def bloque_t3(snap: pd.DataFrame, preds: Mapping[str, np.ndarray], k: int, programas: pd.DataFrame, n_boot: int = N_BOOT,
              modelo: Optional[str] = None) -> Dict:
    """Test episodes of cut ``k`` followed up to 12 semesters: incidence of egreso at 12 against ``km_programa``."""
    modelo = modelo or CONSERVADO_T3[k]
    d = snap.loc[(snap["k"] == k) & (snap["split"] == "test")].reset_index(drop=True)
    d = d.iloc[alinear(preds["episodio_id"], d)].reset_index(drop=True)
    el, y = M3.resultado_horizonte(d["tiempo"], d["causa"], d["seguimiento_max"], TAU_T3)
    col = TAU_T3 - k - 1
    d = poner_facultad(d, programas).loc[el].reset_index(drop=True)
    return bloque(d, y[el], preds[modelo][el, col].astype("float64"), preds[REF_T3][el, col].astype("float64"), modelo, REF_T3,
                  n_boot, horizonte=TAU_T3)


def etiqueta_t45(d: pd.DataFrame, objetivo: str) -> np.ndarray:
    """T4 = transicion, T5 = eliminacion, T5E = eliminacion efectiva (the rule of ``models.t45_data.seleccionar``)."""
    if objetivo == "T4":
        return (d["resultado"] == "transicion").astype("int8").to_numpy()
    eliminada = d["resultado"] == "eliminacion"
    if objetivo == "T5":
        return eliminada.astype("int8").to_numpy()
    return (eliminada & d["eliminacion_efectiva"].astype(bool)).astype("int8").to_numpy()


def bloque_t45(snap: pd.DataFrame, preds: Mapping[str, np.ndarray], k: int, objetivo: str, modelo: str, programas: pd.DataFrame,
               n_boot: int = N_BOOT) -> Dict:
    """Test rows of cut ``k`` with an observed outcome, aligned to ``t45_k{k}_test.npz``; kept model against ``baseline_tasa``."""
    d = snap.loc[(snap["k"] == k) & (snap["split"] == "test")].reset_index(drop=True)
    d = d.iloc[alinear(preds["episodio_id"], d)].reset_index(drop=True)
    d = poner_facultad(d, programas)
    return bloque(d, etiqueta_t45(d, objetivo), preds[f"{objetivo}__{modelo}"], preds[f"{objetivo}__{REF_T45}"], modelo, REF_T45, n_boot)


def bloque_t6(snap: pd.DataFrame, preds: Mapping[str, Mapping[str, np.ndarray]], tau: int, modelo: str, programas: pd.DataFrame,
              n_boot: int = N_BOOT) -> Dict:
    """Valid and test units followed up to ``tau`` semesters, pooled (the benchmark's ``valid_test`` group tables): first
    enrolment in a UCN postgraduate programme by ``tau``. ``preds`` is ``{split: arrays of t6_<split>.npz}``."""
    from pipelines.snapshots import rules_t6 as R6

    partes, ys, ps, bs = [], [], [], []
    for split, pr in preds.items():
        d = snap.loc[snap["split"] == split].reset_index(drop=True)
        d = d.iloc[alinear(pr["episodio_id"], d)].reset_index(drop=True)
        el, y = R6.resultado_horizonte(d["tiempo"], d["evento"], d["seguimiento"], tau)
        partes.append(poner_facultad(d, programas).loc[el])
        ys.append(y[el])
        ps.append(pr[f"{modelo}__tau{tau}"][el].astype("float64"))
        bs.append(pr[f"{REF_T6}__tau{tau}"][el].astype("float64"))
    d = pd.concat(partes, ignore_index=True)
    return bloque(d, np.concatenate(ys), np.concatenate(ps), np.concatenate(bs), modelo, REF_T6, n_boot, horizonte=int(tau),
                  particiones=list(preds))


# ------------------------------------------------------------------------------------------------------------ database
_COLS = "persona_key, cod_programa, split, sexo_equidad, via_clase, tipo_colegio"
Q_T1 = f"SELECT episodio_id, k, estado_muestra, continua, {_COLS} FROM neural_mart.snapshot_t1 WHERE split = 'test'"
Q_T2 = f"SELECT intento_id, y, banda_nota, {_COLS} FROM neural_mart.snapshot_t2 WHERE split = 'test'"
Q_T3 = f"SELECT episodio_id, k, tiempo, causa, seguimiento_max, {_COLS} FROM neural_mart.snapshot_t3 WHERE split = 'test'"
Q_T45 = (f"SELECT episodio_id, k, resultado, eliminacion_efectiva, {_COLS} FROM neural_mart.snapshot_t45 WHERE split = 'test' "
         "AND resultado IN ('continua', 'egreso', 'transicion', 'eliminacion', 'otra_salida')")
# the benchmark of T6 (run_t6) takes the event and time from the postgraduate-status source (P80, P86)
Q_T6 = (f"SELECT episodio_id, tiempo_estados AS tiempo, evento_estados AS evento, seguimiento, {_COLS} "
        "FROM neural_mart.snapshot_t6 WHERE split IN ('valid', 'test')")


def _cargar_json(ruta: Path) -> Optional[Dict]:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def conservados(artefactos: Path) -> Dict[str, Dict]:
    """Kept model per objective and cut from the benchmark files (``seleccion.conservado``): ``{"t45": {(obj, k): m}, "t6": m, "t1_ben": {k: (m, train_desde)}}``."""
    t45 = _cargar_json(artefactos / "resultados_t45.json") or {}
    t6 = _cargar_json(artefactos / "resultados_t6.json") or {}
    ben = _cargar_json(artefactos / "resultados_t1_beneficios.json") or {}
    return {"t1_ben": {int(r["k"]): (r["seleccion"]["conservado"], int(r["train_desde"]))
                       for r in (ben.get("resultados") or {}).values()},
            "t45": {(obj, int(k)): b["seleccion"]["conservado"] for k, bk in (t45.get("por_k") or {}).items()
                    for obj, b in (bk.get("targets") or {}).items()},
            "t6": ((t6.get("modelos") or {}).get("seleccion") or {}).get("conservado")}


def _npz(ruta: Path) -> Dict[str, np.ndarray]:
    z = np.load(ruta)
    return {n: z[n] for n in z.files}


def _bloque_corte(conn, artefactos: Path, programas: pd.DataFrame, n_boot: int) -> Dict:
    """T1 with course load: the kept model is loaded (or refitted) and verified, then scored in memory on its evaluation rows."""
    from evaluation import modelos_conservados as MC

    modelo = MC.cargar_o_ajustar(conn, "t1", 1, "cb_ben_pit", artefactos)
    ev, _ = MC._filas_de_verificacion(modelo, conn)
    p = np.asarray(modelo.predecir(ev), dtype="float64")
    z = np.load(MC.archivo_predicciones("t1", 1, "cb_ben_pit", artefactos))
    base = z["pit__baseline_tasa"][alinear(ev["episodio_id"].to_numpy(), pd.DataFrame({"episodio_id": z["episodio"]}))]
    return bloque_t1_corte(ev, p, base, programas, n_boot)


def construir(conn, artefactos: Path, n_boot: int = N_BOOT, log=print) -> Dict:
    programas = FA.cargar_programas(conn)
    kept = conservados(artefactos)
    pr = artefactos / "preds"
    tareas: Dict[str, Dict[str, Dict[str, Dict]]] = {}

    def listo(nombre, t0, b):
        log(f"{nombre}: {b['modelo']}, n={b['n']:,}, eventos={b['eventos']:,}, "
            + ", ".join(f"{d} {len(f)}" for d, f in b["dimensiones"].items()) + f" ({time.perf_counter() - t0:.0f} s)")

    t1 = _leer(conn, Q_T1)
    t1["continua"] = t1["continua"].astype("boolean")
    for k in (1, 2):
        t0 = time.perf_counter()
        b = tareas.setdefault("t1", {}).setdefault("base", {})[str(k)] = bloque_t1(t1, _npz(pr / f"t1_k{k}.npz"), k, programas, n_boot)
        listo(f"T1 k={k}", t0, b)
    for k, (modelo, desde) in sorted(kept["t1_ben"].items()):          # benefit ablation: its own kept model, its own file
        t0 = time.perf_counter()
        b = tareas["t1"].setdefault(VARIANTE_T1_BENEFICIOS[k], {})[str(k)] = bloque_t1(
            t1, _npz(pr / f"t1_beneficios_k{k}_desde{desde}.npz"), k, programas, n_boot, modelo)
        listo(f"T1 beneficios k={k}", t0, b)
    t0 = time.perf_counter()
    b = tareas["t1"].setdefault("beneficios_corte", {})["1"] = _bloque_corte(conn, artefactos, programas, n_boot)
    listo("T1 con cargas k=1", t0, b)
    del t1
    t0 = time.perf_counter()
    t2 = _leer(conn, Q_T2)
    nuevas, viejas = _npz(pr / "t2_nuevas_test.npz"), _npz(pr / "t2_test.npz")
    orden = pd.Index(viejas["intento_id"]).get_indexer(nuevas["intento_id"])
    if (orden < 0).any():
        raise ValueError("t2_nuevas_test.npz and t2_test.npz do not list the same attempts")
    b = tareas.setdefault("t2", {}).setdefault("base", {})["0"] = bloque_t2(
        t2, nuevas["intento_id"], nuevas[MODELO_T2].astype("float64"), viejas[REF_T2][orden].astype("float64"), programas, n_boot)
    listo("T2", t0, b)
    z = _npz(pr / "t2_bandas_test.npz")
    t0 = time.perf_counter()
    for variante, b in bloques_t2_bandas(t2, z["intento_id"], z[MODELO_BANDAS], z[REF_BANDAS], programas, n_boot).items():
        tareas["t2"].setdefault(variante, {})["0"] = b
        listo(f"T2 {variante}", t0, b)
    del t2
    t3 = _leer(conn, Q_T3)
    for k in (0, 2, 4):
        t0 = time.perf_counter()
        b = tareas.setdefault("t3", {}).setdefault("base", {})[str(k)] = bloque_t3(t3, _npz(pr / f"t3_k{k}_test.npz"), k, programas, n_boot)
        listo(f"T3 k={k}", t0, b)
    t45 = _leer(conn, Q_T45)
    t45["eliminacion_efectiva"] = t45["eliminacion_efectiva"].astype("boolean").fillna(False)
    for objetivo, tarea, variante in (("T4", "t4", "base"), ("T5", "t5", "actual"), ("T5E", "t5", "efectiva")):
        for k in (2, 4):
            modelo = kept["t45"].get((objetivo, k))
            if modelo is None:
                continue
            t0 = time.perf_counter()
            b = tareas.setdefault(tarea, {}).setdefault(variante, {})[str(k)] = bloque_t45(
                t45, _npz(pr / f"t45_k{k}_test.npz"), k, objetivo, modelo, programas, n_boot)
            listo(f"{objetivo} k={k}", t0, b)
    t6 = _leer(conn, Q_T6)
    if kept["t6"]:
        z6 = {s: _npz(pr / f"t6_{s}.npz") for s in ("valid", "test")}
        for tau in (2, 4):
            if all(f"{kept['t6']}__tau{tau}" in z for z in z6.values()):
                t0 = time.perf_counter()
                b = tareas.setdefault("t6", {}).setdefault(f"h{tau}", {})["0"] = bloque_t6(t6, z6, tau, kept["t6"], programas, n_boot)
                listo(f"T6 tau={tau}", t0, b)
    return {"version": 1, "n_boot": n_boot, "semilla": SEMILLA, "pocos_casos": POCOS_CASOS, "tareas": tareas}


# ---------------------------------------------------------------------------------------------- parity with the benchmark
TOL_PARIDAD = 1e-6
# the band model's predictions are stored as float32 (``preds/t2_bandas_*.npz``) while the benchmark ranked the float64 ones: the
# rounding creates a few ties and moves a group's AP by up to ~1e-6 (measured 1.07e-6)
TOL_PARIDAD_BANDAS = 2e-6


def tolerancia(clave: str) -> float:
    return TOL_PARIDAD_BANDAS if clave.startswith("t2_banda_") else TOL_PARIDAD


def _comparar(nuevas: Sequence[Mapping], previas: Sequence[Mapping], ap: Optional[str], auc: Optional[str]) -> Dict:
    """Common groups of our rows and the benchmark's: sizes, AP and ROC-AUC (only where the benchmark has a finite value)."""
    a = {f["grupo"]: f for f in nuevas}
    dif = {"comparados": 0, "faltan": 0, "n_distinto": 0, "max_dif_ap": 0.0, "max_dif_auc": 0.0, "max_dif_tasa": 0.0}
    for f in previas:
        g = str(f["grupo"])
        if g not in a:
            dif["faltan"] += 1                      # a benchmark group that our table does not list: reported, never skipped
            continue
        dif["comparados"] += 1
        dif["n_distinto"] += int(int(f["n"]) != a[g]["n"])
        if f.get("tasa") is not None and np.isfinite(f["tasa"]):          # observed rate (= events / n) where the benchmark lists it
            dif["max_dif_tasa"] = max(dif["max_dif_tasa"], float("inf") if a[g]["tasa"] is None else abs(a[g]["tasa"] - float(f["tasa"])))
        for campo_prev, campo, clave in ((ap, "ap", "max_dif_ap"), (auc, "auc", "max_dif_auc")):
            previo = f.get(campo_prev) if campo_prev else None
            if previo is None or not np.isfinite(previo):
                continue
            nuevo = a[g][campo]
            dif[clave] = max(dif[clave], float("inf") if nuevo is None else abs(nuevo - float(previo)))
    return dif


def verificar(doc: Mapping, artefactos: Path) -> Dict[str, Dict]:
    """Compare every group that today's ``resultados_t*.json`` tables already list (AP and ROC-AUC of the same kept model)."""
    out: Dict[str, Dict] = {}
    tareas = doc["tareas"]

    def poner(clave, bloque_, previas, ap, auc, dimension):
        if bloque_ and previas:
            out[clave] = _comparar(bloque_["dimensiones"][dimension], previas, ap, auc)

    r1 = _cargar_json(artefactos / "resultados_t1.json")
    for r in ((r1 or {}).get("resultados") or {}).values():
        k = int(r["k"])
        blk = ((tareas.get("t1") or {}).get("base") or {}).get(str(k))
        sg = (r.get("subgrupos_test") or {}).get(CONSERVADO_T1.get(k, "")) or {}
        for dim, tabla in (("programa", "programa"), ("via", "via"), ("sexo", "sexo")):
            poner(f"t1_k{k}_{dim}", blk, sg.get(tabla), "ap", "roc_auc", dim)
    r2 = _cargar_json(artefactos / "resultados_t2.json")
    sg2 = (((r2 or {}).get("evaluacion") or {}).get("subgrupos_test") or {}).get(MODELO_T2) or {}
    for dim in ("programa", "sexo"):
        poner(f"t2_{dim}", ((tareas.get("t2") or {}).get("base") or {}).get("0"), sg2.get(dim), "ap", "roc_auc", dim)
    r3 = _cargar_json(artefactos / "resultados_t3.json")
    for ks, b3 in ((r3 or {}).get("por_k") or {}).items():
        blk = ((tareas.get("t3") or {}).get("base") or {}).get(ks)
        if not blk:
            continue
        sg = (b3.get("subgrupos_test") or {}).get(blk["modelo"]) or {}
        for dim, tabla in (("programa", "programa_n150"), ("via", "via"), ("sexo", "sexo")):
            poner(f"t3_k{ks}_{dim}", blk, sg.get(tabla), None, "auc", dim)
    r45 = _cargar_json(artefactos / "resultados_t45.json")
    destino = {"T4": ("t4", "base"), "T5": ("t5", "actual"), "T5E": ("t5", "efectiva")}
    for ks, bk in ((r45 or {}).get("por_k") or {}).items():
        for objetivo, b in (bk.get("targets") or {}).items():
            tarea, variante = destino[objetivo]
            blk = ((tareas.get(tarea) or {}).get(variante) or {}).get(ks)
            if not blk or blk["modelo"] != b["seleccion"]["conservado"]:
                continue
            for dim in ("programa", "facultad"):
                poner(f"{objetivo.lower()}_k{ks}_{dim}", blk, (b.get("grupos") or {}).get(dim, {}).get("filas"), "ap", "roc_auc", dim)
    r6 = _cargar_json(artefactos / "resultados_t6.json") or {}
    por_h = (r6.get("descriptivo") or {}).get("por_horizonte") or {}
    tau_principal = str(((r6.get("modelos") or {}).get("seleccion") or {}).get("tau") or r6.get("tau_principal") or 2)
    for tau, h in ((((r6 or {}).get("modelos") or {}).get("horizontes") or {}).get("test") or {}).items():
        blk = ((tareas.get("t6") or {}).get(f"h{tau}") or {}).get("0")
        if not blk or not h.get("modelos"):
            continue
        # pooled valid + test units followed up to the horizon: size and events of both splits of the benchmark
        n = sum(int((por_h.get(tau, {}).get(s) or {}).get("n", 0)) for s in blk["particiones"])
        ev = sum(int((por_h.get(tau, {}).get(s) or {}).get("eventos", 0)) for s in blk["particiones"])
        out[f"t6_h{tau}_n"] = {"comparados": 1, "faltan": 0, "n_distinto": int(blk["n"] != n or blk["eventos"] != ev),
                               "max_dif_ap": 0.0, "max_dif_auc": 0.0}
        if tau == tau_principal:                  # the benchmark's group tables (valid + test) exist for the main horizon only
            gv = (((r6.get("modelos") or {}).get("grupos") or {}).get("valid_test")) or {}
            for dim in ("programa", "facultad"):
                poner(f"t6_h{tau}_{dim}", blk, (gv.get(dim) or {}).get("filas"), "ap", "roc_auc", dim)
    r1b = _cargar_json(artefactos / "resultados_t1_beneficios.json")
    for r in ((r1b or {}).get("resultados") or {}).values():
        k = int(r["k"])
        variante = VARIANTE_T1_BENEFICIOS[k]
        blk = ((tareas.get("t1") or {}).get(variante) or {}).get(str(k))
        if blk is None or blk["modelo"] != r["seleccion"]["conservado"]:
            continue
        clave = "extension_k4" if variante == "extension_k4" else f"beneficios_k{k}"
        for dim in ("programa", "facultad"):
            poner(f"t1_{clave}_{dim}", blk, ((r.get("grupos") or {}).get(dim) or {}).get("filas"), "ap", "roc_auc", dim)
    bandas = ((((r2 or {}).get("evaluacion") or {}).get("bandas") or {}).get("grupos") or {}).get("test") or {}
    for banda in BANDAS_T2:
        blk = ((tareas.get("t2") or {}).get(f"banda_{banda}") or {}).get("0")
        for dim in ("programa", "facultad"):
            previas = [{"grupo": f["grupo"], "n": f["n"], "ap": ((f.get("bandas") or {}).get(banda) or {}).get("ap"),
                        "tasa": (((f.get("bandas") or {}).get(banda) or {}).get("observada") or {}).get("punto")}
                       for f in (bandas.get(dim) or {}).get("filas", [])]
            poner(f"t2_banda_{banda}_{dim}", blk, previas, "ap", None, dim)
    rc = _cargar_json(artefactos / "resultados_t1_beneficios_cargas.json")
    blk = ((tareas.get("t1") or {}).get("beneficios_corte") or {}).get("1")
    k1 = (((rc or {}).get("resultados") or {}).get("k1") or {}).get("grupos") or {}
    for dim in ("programa", "facultad"):
        poner(f"t1_corte_k1_{dim}", blk, (k1.get(dim) or {}).get("filas"), "ap", "roc_auc", dim)
    return out


# ------------------------------------------------------------------------------------------------------------------ main
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artefactos", type=Path, default=RAIZ / "artefactos")
    parser.add_argument("--boot", type=int, default=N_BOOT)
    args = parser.parse_args(argv)
    try:
        from pipelines.common.db import dev_connection

        t0 = time.perf_counter()
        with dev_connection() as conn:
            doc = construir(conn, args.artefactos, args.boot, log=lambda m: print(m, flush=True))
        doc["verificacion"] = verificar(doc, args.artefactos)
        for nombre, v in doc["verificacion"].items():
            print(f"verificación {nombre}: {v}")
        (args.artefactos / "grupos_todos.json").write_text(
            json.dumps(sin_nan(doc), ensure_ascii=False, allow_nan=False, indent=1, default=int), encoding="utf-8")
        print(f"listo en {time.perf_counter() - t0:.0f} s")
    except Exception as exc:  # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
