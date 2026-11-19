"""Faculty (and program) group tables for T1 base and T3 from the saved test predictions (D115). No model is retrained.

``python -m evaluation.grupos_facultad`` reads the gitignored ``artefactos/preds/t1_k{1,2}.npz`` and
``t3_k{0,2,4}_test.npz``, takes the labels and the population from the localhost snapshots (``snapshot_t1``,
``snapshot_t3``), and writes AGGREGATES to ``artefactos/grupos_facultad.json`` (gitignored): per task, cut and level
(programa, facultad) the table of ``evaluation.grupos_t45.tabla_agregada`` (observed rate with a person-grouped bootstrap
interval, expected = mean predicted risk of the kept model, reference = historical rate of the baseline). Every group is listed,
whatever its size or number of events; AP / AUC of each group are in ``evaluation.grupos_todos``.

* T1 (cut k = 1, 2): event = no continua; kept model per D114; reference = ``baseline_tasa``.
* T3 (cut k = 0, 2, 4): event = egreso by 12 semesters among the episodes followed up to 12; expected = cumulative incidence
  of the kept model at 12; reference = ``km_programa``. Every group is listed and carries
  ``confianza = min(1, n / 150, eventos / 10)``.

The mart no longer reads this file (``pipelines.marts.resumen_tareas`` reads ``grupos_todos.json``). No row, key or name is written.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from evaluation import facultades as FA
from evaluation import grupos_t45 as GR
from evaluation import metrics_t3 as M3
from evaluation import metrics_t45 as M45

RAIZ = Path(__file__).resolve().parents[1]
N_BOOT = 1000
TAU_T3 = 12
N_RECOMENDADO_T3 = 150                # group size at which the confidence reaches 100 %
EVENTOS_RECOMENDADOS_T3 = 10
KS_T1 = (1, 2)
KS_T3 = (0, 2, 4)
# kept models (D114) and references; mirrored in ``pipelines.marts.resumen_tareas``
CONSERVADO_T1 = {1: "cb_acad", 2: "lr_acad"}
CONSERVADO_T3 = {0: "dt_lr_adm", 2: "nn_gru", 4: "nn_gru"}
REF_T1, REF_T3 = "baseline_tasa", "km_programa"
SIN_FACULTAD = "Sin facultad"


def alinear(ids_pred: np.ndarray, df: pd.DataFrame, col: str = "episodio_id") -> np.ndarray:
    """Positions of ``df`` rows in the order of ``ids_pred`` (each prediction row <-> exactly one snapshot row)."""
    ids = df[col].to_numpy()
    if len(set(ids_pred.tolist())) != len(ids_pred) or len(set(ids.tolist())) != len(ids):
        raise ValueError("duplicated episode ids")
    pos = pd.Series(np.arange(len(ids)), index=ids)
    faltan = ~pd.Index(ids_pred).isin(pos.index)
    if faltan.any():
        raise ValueError(f"{int(faltan.sum())} predicted episodes are not in the snapshot rows")
    return pos.loc[ids_pred].to_numpy()


def poner_facultad(df: pd.DataFrame, programas: pd.DataFrame) -> pd.DataFrame:
    fac = FA.facultad_de(df["cod_programa"], programas)
    return df.assign(facultad=fac.where(fac.notna(), SIN_FACULTAD))


def tablas_niveles(df: pd.DataFrame, y: np.ndarray, p: np.ndarray, p_base: np.ndarray, n_boot: int, seed: int = 7) -> Dict[str, Dict]:
    """``{"programa": tabla, "facultad": tabla}`` of ``grupos_t45.tabla_agregada`` over the rows of ``df``: every group is listed.

    The bootstrap resamples PERSONS (``persona_key``), as in T4 / T5, with the same indices for both levels.
    """
    idxs = M45.remuestreos(df["persona_key"].to_numpy(), n_boot, seed=seed)
    return {nivel: GR.tabla_agregada(df[col].to_numpy(), y, p, p_base, idxs, n_min=1, eventos_min=0)
            for nivel, col in (("programa", "cod_programa"), ("facultad", "facultad"))}


# ------------------------------------------------------------------------------------------------------ T1
def bloque_t1(snap: pd.DataFrame, preds: Mapping[str, np.ndarray], k: int, programas: pd.DataFrame, n_boot: int = N_BOOT) -> Dict:
    """Test rows of cut ``k`` aligned to the saved predictions; groups of the kept model against ``baseline_tasa``."""
    modelo = CONSERVADO_T1[k]
    d = snap.loc[(snap["k"] == k) & (snap["split"] == "test") & (snap["estado_muestra"] == "observada")
                 & snap["continua"].notna()]
    d = d.reset_index(drop=True)
    d = d.iloc[alinear(preds["episodio_test"], d)].reset_index(drop=True)
    d = poner_facultad(d, programas)
    y = (~d["continua"].astype(bool)).astype("int8").to_numpy()
    grupos = tablas_niveles(d, y, preds[f"test__{modelo}"], preds[f"test__{REF_T1}"], n_boot)
    return {"modelo": modelo, "referencia": REF_T1, "n_test": int(len(d)), "eventos_test": int(y.sum()), "grupos": grupos}


# ------------------------------------------------------------------------------------------------------ T3
def confianza_t3(n: int, eventos: int) -> float:
    """D116 confidence of a T3 group: closeness to the recommended size, ``min(1, n / 150, eventos / 10)``."""
    return float(min(1.0, n / N_RECOMENDADO_T3, eventos / EVENTOS_RECOMENDADOS_T3))


def _marcar_t3(grupos: Dict[str, Dict]) -> None:
    """Add ``confianza`` to every T3 row."""
    for tabla in grupos.values():
        for f in tabla["filas"]:
            f["confianza"] = confianza_t3(f["n"], f["eventos"])


def bloque_t3(snap: pd.DataFrame, preds: Mapping[str, np.ndarray], k: int, programas: pd.DataFrame, n_boot: int = N_BOOT,
              modelo: Optional[str] = None) -> Dict:
    """Test rows of cut ``k``: incidence of egreso at 12 semesters among the episodes followed up to 12 (``tabla_subgrupo``)."""
    modelo = modelo or CONSERVADO_T3[k]
    d = snap.loc[(snap["k"] == k) & (snap["split"] == "test")].reset_index(drop=True)
    d = d.iloc[alinear(preds["episodio_id"], d)].reset_index(drop=True)
    el, y = M3.resultado_horizonte(d["tiempo"], d["causa"], d["seguimiento_max"], TAU_T3)
    col = TAU_T3 - k - 1
    d = poner_facultad(d, programas).loc[el].reset_index(drop=True)
    y = y[el]
    grupos = tablas_niveles(d, y, preds[modelo][el, col].astype("float64"), preds[REF_T3][el, col].astype("float64"), n_boot)
    _marcar_t3(grupos)
    return {"modelo": modelo, "referencia": REF_T3, "horizonte": TAU_T3, "n_test": int(len(d)), "eventos_test": int(y.sum()),
            "grupos": grupos}


# ----------------------------------------------------------------------------------------------- sanity check
def comparar_filas(nuevas: Sequence[Mapping], previas: Sequence[Mapping], obs: str, esp: str, prev_obs: str, prev_esp: str) -> Dict:
    """Compare recomputed program rows with the benchmark's: n, observed and expected rate per common group."""
    a = {f["grupo"]: f for f in nuevas}
    b = {f["grupo"]: f for f in previas}
    comunes = sorted(set(a) & set(b))
    dif_n = sum(1 for g in comunes if int(a[g]["n"]) != int(b[g]["n"]))
    dif_obs = max((abs(a[g][obs]["punto"] - b[g][prev_obs]) for g in comunes), default=0.0)
    dif_esp = max((abs(a[g][esp]["punto"] - b[g][prev_esp]) for g in comunes), default=0.0)
    return {"comunes": len(comunes), "solo_nuevas": len(set(a) - set(b)), "solo_previas": len(set(b) - set(a)),
            "n_distinto": dif_n, "max_dif_observada": float(dif_obs), "max_dif_esperada": float(dif_esp)}


def verificar(bloques: Mapping, resultados_t1: Optional[Mapping], resultados_t3: Optional[Mapping], snap_t3=None, preds_t3=None,
              programas=None) -> Dict:
    """Sanity check against the benchmark JSON (program rows of the same kept model)."""
    out: Dict[str, Dict] = {}
    if resultados_t1:
        for r in (resultados_t1.get("resultados") or {}).values():
            k = int(r["k"])
            blk = (bloques.get("t1") or {}).get(str(k))
            previas = ((r.get("subgrupos_test") or {}).get(CONSERVADO_T1.get(k, "")) or {}).get("programa")
            if blk and previas is not None:
                out[f"t1_k{k}"] = comparar_filas(blk["grupos"]["programa"]["filas"], previas, "tasa_observada", "riesgo_medio",
                                                 "tasa_observada", "riesgo_medio")
    if resultados_t3 and snap_t3 is not None:
        for ks, bloque in (resultados_t3.get("por_k") or {}).items():
            k = int(ks)
            sg = bloque.get("subgrupos_test") or {}
            # the benchmark has group rows for the networks and CatBoost, not for the logistic of k = 0: compare the same model
            modelo = CONSERVADO_T3[k] if "programa_n150" in (sg.get(CONSERVADO_T3[k]) or {}) else "dt_cb_adm"
            blk = bloque_t3(snap_t3, preds_t3[k], k, programas, n_boot=2, modelo=modelo)
            out[f"t3_k{k}_{modelo}"] = comparar_filas(blk["grupos"]["programa"]["filas"], sg[modelo]["programa_n150"],
                                                      "tasa_observada", "riesgo_medio", "incidencia_observada",
                                                      "incidencia_predicha")
    return out


# --------------------------------------------------------------------------------------------------- database
Q_T1 = ("SELECT episodio_id, persona_key, cod_programa, k, split, estado_muestra, continua FROM neural_mart.snapshot_t1 "
        "WHERE split = 'test'")
Q_T3 = ("SELECT episodio_id, persona_key, cod_programa, k, split, tiempo, causa, seguimiento_max FROM neural_mart.snapshot_t3 "
        "WHERE split = 'test'")


def _leer(conn, sql: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql)
        d = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    d["cod_programa"] = d["cod_programa"].astype(object)
    return d


def construir(conn, artefactos: Path, n_boot: int = N_BOOT, log=print):
    programas = FA.cargar_programas(conn)
    t1 = _leer(conn, Q_T1)
    t1["continua"] = t1["continua"].astype("boolean")
    t3 = _leer(conn, Q_T3)
    preds_dir = artefactos / "preds"
    out: Dict = {"version": 1, "n_boot": n_boot, "tau_t3": TAU_T3, "t1": {}, "t3": {}}
    for k in KS_T1:
        z = np.load(preds_dir / f"t1_k{k}.npz")
        out["t1"][str(k)] = bloque_t1(t1, {n: z[n] for n in z.files}, k, programas, n_boot)
        log(f"T1 k={k}: {_cuenta(out['t1'][str(k)])}")
    preds_t3 = {}
    for k in KS_T3:
        z = np.load(preds_dir / f"t3_k{k}_test.npz")
        preds_t3[k] = {n: z[n] for n in z.files}
        out["t3"][str(k)] = bloque_t3(t3, preds_t3[k], k, programas, n_boot)
        log(f"T3 k={k}: {_cuenta(out['t3'][str(k)])}")
    return out, t3, preds_t3, programas


def sin_nan(v):
    """JSON-safe copy: NaN / inf become ``None`` (a group without AP / AUC, an empty interval)."""
    if isinstance(v, dict):
        return {k: sin_nan(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [sin_nan(x) for x in v]
    if isinstance(v, (float, np.floating)):
        return float(v) if np.isfinite(v) else None
    return v


def _cuenta(b: Mapping) -> str:
    g = b["grupos"]
    return (f"{b['modelo']}, n={b['n_test']:,}, programas {len(g['programa']['filas'])}/{g['programa']['resumen']['grupos_total']}, "
            f"facultades {len(g['facultad']['filas'])}/{g['facultad']['resumen']['grupos_total']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artefactos", type=Path, default=RAIZ / "artefactos")
    parser.add_argument("--boot", type=int, default=N_BOOT)
    args = parser.parse_args(argv)
    try:
        from pipelines.common.db import dev_connection

        with dev_connection() as conn:
            out, t3, preds_t3, programas = construir(conn, args.artefactos, args.boot)
        r1 = json.loads((args.artefactos / "resultados_t1.json").read_text(encoding="utf-8"))
        r3 = json.loads((args.artefactos / "resultados_t3.json").read_text(encoding="utf-8"))
        out["verificacion"] = verificar(out, r1, r3, t3, preds_t3, programas)
        for nombre, v in out["verificacion"].items():
            print(f"verificación {nombre}: {v}")
        (args.artefactos / "grupos_facultad.json").write_text(json.dumps(sin_nan(out), ensure_ascii=False, allow_nan=False,
                                                                         indent=1, default=int), encoding="utf-8")
    except Exception as exc:  # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
