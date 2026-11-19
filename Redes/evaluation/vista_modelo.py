"""Blocks "Cómo decide el modelo" of the view "Lo que pasó" (plan 2026-11-18, Task 5). Aggregates only; "Toda la UCN" only.

* ``senales``           the five families of inputs that weigh the most in each kept model (T1 ``cb_acad`` at k = 1, T2 ``cb_c_nuevas``,
  T5 ``gru_adm`` at k = 2), by permutation importance on the model's test set: the drop in average precision when a family is
  shuffled across students (5 repetitions, fixed seed). ``peso_pct`` is the share of the positive drops. Associations of the model,
  not causes. A large test set may be subsampled with a fixed seed; the block states ``n_muestra``.
* ``esperar_semestre``  how many of every 10 students who leave the model reaches by supporting the 10 % of highest risk, one cut
  earlier versus one cut later (T1 k = 1 -> 2, T5 k = 2 -> 4). The populations differ (more time lived = fewer, more selected
  students), so the block carries ``nota_poblaciones``.

The models come from ``evaluation.modelos_conservados`` (refit and verified against the saved test predictions); nothing is retrained.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from evaluation import familias_variables as FV
from evaluation import vista_historica as VH
from evaluation.grupos_facultad import alinear

REPETICIONES = 5
SEMILLA = 0
TOP = 5
MAX_FILAS = 60000                     # permutation scores the model (families x repetitions) times: cap the rows, fixed seed
PREFIJO_SEQ = "seq:"
MODELOS_SENALES = (("t1", 1, "cb_acad"), ("t2", 0, "cb_c_nuevas"), ("t5", 2, "gru_adm"))
OBJETIVO = {"t1": "y", "t2": "y", "t5": "y5"}
PARES_ESPERAR = (
    {"tarea": "t1", "k_antes": 1, "k_despues": 2, "npz_antes": "t1_k1.npz", "col_antes": "test__cb_acad", "ids_antes": "episodio_test",
     "npz_despues": "t1_nuevas_k2.npz", "col_despues": "test__lr_acad", "ids_despues": "episodio_test"},
    {"tarea": "t5", "k_antes": 2, "k_despues": 4, "npz_antes": "t45_k2_test.npz", "col_antes": "T5__gru_adm", "ids_antes": "episodio_id",
     "npz_despues": "t45_k4_test.npz", "col_despues": "T5__gru_agg", "ids_despues": "episodio_id"},
)


# ------------------------------------------------------------------------------------------------ permutation importance
def _es_red(modelo) -> bool:
    return getattr(modelo, "tipo", None) == "t5_gru"


def importancia_permutacion(modelo, filas: pd.DataFrame, sem: Optional[pd.DataFrame], y, familias: Mapping[str, Sequence[str]],
                            repeticiones: int = REPETICIONES, semilla: int = SEMILLA) -> List[Dict[str, Any]]:
    """Drop in average precision when one family of inputs is shuffled across students, sorted from the largest drop.

    ``familias`` maps a family id to its columns of ``filas``; ``seq:<channel>`` names a sequence channel of the T5 network. Every
    repetition draws a new permutation (one per family, same rows each time); all the columns of a family move together, in the
    static and in the sequence inputs of the network. ``peso_pct`` is the share of the positive drops (0 for a family that does not help)."""
    from models import t3_data as TD3
    from models import t45_data as TD45

    filas = filas.reset_index(drop=True)
    y = np.asarray(y)
    n = len(filas)
    red = _es_red(modelo)
    base_seq = TD45.construir_secuencias_t45(filas, sem, modelo.k) if red else None

    def puntuar(f: pd.DataFrame, seq: Optional[np.ndarray]) -> float:
        p = modelo.predecir(f, sem, secuencias=seq) if red else modelo.predecir(f, sem)
        return float(average_precision_score(y, p))

    ap0 = puntuar(filas, base_seq)
    rng = np.random.default_rng(semilla)
    caidas: Dict[str, float] = {}
    for fam, cols in familias.items():
        est = [c for c in cols if not c.startswith(PREFIJO_SEQ)]
        canales = [TD3.SEQ_COLS_T3.index(c[len(PREFIJO_SEQ):]) for c in cols if c.startswith(PREFIJO_SEQ)] if red else []
        if not est and not canales:
            raise ValueError(f"family {fam!r} has no input column in this model")
        d = []
        for _ in range(repeticiones):
            perm = rng.permutation(n)
            f = filas.copy(deep=False)
            for c in est:
                f[c] = filas[c].iloc[perm].reset_index(drop=True)
            seq = base_seq
            if canales:
                seq = base_seq.copy()
                seq[:, :, canales] = base_seq[perm][:, :, canales]
            d.append(ap0 - puntuar(f, seq))
        caidas[fam] = float(np.mean(d))
    positivo = sum(v for v in caidas.values() if v > 0)
    out = [{"familia": fam, "etiqueta": FV.ETIQUETA_FAMILIA.get(fam, fam), "caida_ap": v,
            "peso_pct": 100.0 * v / positivo if v > 0 and positivo > 0 else 0.0} for fam, v in caidas.items()]
    return sorted(out, key=lambda r: (-r["caida_ap"], r["familia"]))


def columnas_de_entrada(modelo) -> List[str]:
    """Input columns of a kept model (static columns, plus the sequence channels of the T5 network)."""
    from models import t3_data as TD3

    prep = modelo.componentes["prep"]
    cols = list(prep.num_cols) + list(prep.cat_cols)
    return cols + [PREFIJO_SEQ + c for c in TD3.SEQ_COLS_T3] if _es_red(modelo) else cols


# ------------------------------------------------------------------------------------------------ blocks (pure)
def bloque_senales(entradas: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """``{tareas: [{tarea, k, modelo, n_muestra, senales: top 5}]}`` from ``[{tarea, k, modelo, importancia, n_muestra}]``."""
    tareas = []
    for e in entradas:
        top = [{"familia": s["familia"], "etiqueta": s["etiqueta"], "peso_pct": round(float(s["peso_pct"]), 1),
                "caida_ap": round(float(s["caida_ap"]), 4)} for s in e["importancia"][:TOP]]
        tareas.append({"tarea": e["tarea"], "k": int(e["k"]), "modelo": e["modelo"], "n_muestra": int(e["n_muestra"]), "senales": top})
    return {"tareas": tareas}


def bloque_esperar(pares: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """``{comparaciones: [{tarea, k_antes, k_despues, de_cada_10_antes, de_cada_10_despues}], nota_poblaciones: True}``.

    Each side is ``curva_alcance(y, p)["de_cada_10"]`` on its own saved test set (``None`` when the curve is not publishable)."""
    def de_cada_10(y, p) -> Optional[float]:
        c = VH.curva_alcance(np.asarray(y), np.asarray(p, dtype="float64"))
        return None if c is None else c["de_cada_10"]

    return {"comparaciones": [{"tarea": x["tarea"], "k_antes": int(x["k_antes"]), "k_despues": int(x["k_despues"]),
                               "de_cada_10_antes": de_cada_10(x["y_antes"], x["p_antes"]),
                               "de_cada_10_despues": de_cada_10(x["y_despues"], x["p_despues"])} for x in pares],
            "nota_poblaciones": True}


# ------------------------------------------------------------------------------------------------ database / artefacts
Q_T1_K = ("SELECT episodio_id, continua FROM neural_mart.snapshot_t1 "
          "WHERE k = %s AND split = 'test' AND estado_muestra = 'observada' AND continua IS NOT NULL")
Q_T5_K = "SELECT episodio_id, resultado FROM neural_mart.snapshot_t45 WHERE k = %s AND split = 'test'"


def _etiquetas(conn, tarea: str, k: int) -> pd.DataFrame:
    if tarea == "t1":
        d = VH._leer(conn, Q_T1_K, (k,))
        d["y"] = (~d["continua"].astype(bool)).astype("int8")
    else:
        d = VH._leer(conn, Q_T5_K, (k,))
        d = d.loc[d["resultado"].isin(VH.CLASES_T5)].reset_index(drop=True)
        d["y"] = (d["resultado"] == "eliminacion").astype("int8")
    return d


def _y_y_p(conn, artefactos: Path, tarea: str, k: int, npz: str, ids: str, col: str):
    z = np.load(artefactos / "preds" / npz)
    d = _etiquetas(conn, tarea, k)
    pos = alinear(z[ids], d)
    return d["y"].to_numpy()[pos], z[col].astype("float64")


def calcular_esperar(conn, artefactos: Path) -> Dict[str, Any]:
    pares = []
    for x in PARES_ESPERAR:
        y0, p0 = _y_y_p(conn, artefactos, x["tarea"], x["k_antes"], x["npz_antes"], x["ids_antes"], x["col_antes"])
        y1, p1 = _y_y_p(conn, artefactos, x["tarea"], x["k_despues"], x["npz_despues"], x["ids_despues"], x["col_despues"])
        pares.append({"tarea": x["tarea"], "k_antes": x["k_antes"], "k_despues": x["k_despues"],
                      "y_antes": y0, "p_antes": p0, "y_despues": y1, "p_despues": p1})
    return bloque_esperar(pares)


def calcular_senales(conn, artefactos: Path, max_filas: int = MAX_FILAS, repeticiones: int = REPETICIONES,
                     semilla: int = SEMILLA, log=None) -> Dict[str, Any]:
    """Permutation importance of the three kept models on their (verified) test rows."""
    from evaluation import modelos_conservados as MC

    entradas = []
    for tarea, k, nombre in MODELOS_SENALES:
        modelo = MC.cargar_o_ajustar(conn, tarea, k, nombre, artefactos)
        columnas = columnas_de_entrada(modelo)
        filas, sem = MC._filas_de_verificacion(modelo, conn)
        y = filas[OBJETIVO[tarea]].to_numpy()
        if len(filas) > max_filas:
            pos = np.sort(np.random.default_rng(semilla).choice(len(filas), size=max_filas, replace=False))
            filas, y = filas.iloc[pos].reset_index(drop=True), y[pos]
        familias = FV.agrupar(columnas)
        if log:
            log(f"{tarea} k={k} {nombre}: {len(filas)} filas, {len(familias)} familias")
        entradas.append({"tarea": tarea, "k": k, "modelo": nombre, "n_muestra": len(filas),
                         "importancia": importancia_permutacion(modelo, filas, sem, y, familias, repeticiones, semilla)})
        MC.limpiar_cache()
    return bloque_senales(entradas)
