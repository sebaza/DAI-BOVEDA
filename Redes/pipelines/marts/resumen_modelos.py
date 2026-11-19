"""Aggregate summary of the model benchmarks for the "Modelos" view (``neural_mart.resumen_modelos*``).

Pure transformation of the three gitignored result files (``artefactos/resultados_t{1,2,3}.json``). Only aggregate
metrics with their bootstrap intervals, paired differences, architecture sizes and headline sentences come out: never a
prediction, a person key or a subgroup. ``tools/exportar_resumen_modelos.py`` writes the rows into the database.

The ablation ladder (``escalon``) follows the benchmark documents (08, 09, 10); the verdict of a paired difference is
read from its 95 % interval: it excludes zero on the good side (``mejora``), on the bad side (``empeora``) or it does
not exclude zero (``sin_diferencia``). For error metrics (Brier, ECE, IBS) lower is better.
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Optional

CONJUNTO = "test"

# model key -> (display name, family, ladder rung, rung name)
T1_MODELOS = {
    "baseline_tasa": ("Tasa histórica del programa", "referencia", 0, "Tasa histórica del programa"),
    "lr_pre": ("Logística (solo perfil de ingreso)", "regresion", 1, "Solo perfil de ingreso"),
    "cb_pre": ("CatBoost (solo perfil de ingreso)", "arboles", 1, "Solo perfil de ingreso"),
    "lr_acad": ("Logística (ingreso + agregados)", "regresion", 2, "+ agregados académicos al corte"),
    "cb_acad": ("CatBoost (ingreso + agregados)", "arboles", 2, "+ agregados académicos al corte"),
    "gru_seq": ("GRU (ingreso + secuencia por semestre)", "red", 3, "+ secuencia por semestre (GRU)"),
}
T2_MODELOS = {
    "baseline": ("Tasa histórica del curso", "referencia", 0, "Tasa histórica del curso"),
    "lr_a": ("Logística (a) estudiante + carga", "regresion", 1, "a. Estudiante + carga"),
    "cb_a": ("CatBoost (a) estudiante + carga", "arboles", 1, "a. Estudiante + carga"),
    "lr_b": ("Logística (b) + estadística del curso", "regresion", 2, "b. + estadística del curso"),
    "cb_b": ("CatBoost (b) + estadística del curso", "arboles", 2, "b. + estadística del curso"),
    "lr_c": ("Logística (c) + prerrequisitos", "regresion", 3, "c. + prerrequisitos explícitos"),
    "cb_c": ("CatBoost (c) + prerrequisitos", "arboles", 3, "c. + prerrequisitos explícitos"),
    "lr_c_nuevas": ("Logística (c) + departamento y semestre anterior", "regresion", 3, "c. + departamento y semestre anterior (D118)"),
    "cb_c_nuevas": ("CatBoost (c) + departamento y semestre anterior", "arboles", 3, "c. + departamento y semestre anterior (D118)"),
    "lr_d": ("Logística (d) + historial de sección", "regresion", 4, "d. + historial de sección o docente"),
    "cb_d": ("CatBoost (d) + historial de sección", "arboles", 4, "d. + historial de sección o docente"),
    "cb_c_decay": ("CatBoost (c) + estadística con decaimiento exponencial", "arboles", 5, "Ablación de estadística reciente (P55)"),
    "cb_c_vent": ("CatBoost (c) + estadística de ventana reciente", "arboles", 5, "Ablación de estadística reciente (P55)"),
    "cb_c_id": ("CatBoost (c) + identidad del curso", "arboles", 5, "Grafo y representación del curso"),
    "cb_cemb": ("CatBoost (c) + embeddings GraphSAGE", "red_grafo", 5, "Grafo y representación del curso"),
    "nn_ninguno": ("Red sin representación del curso", "red", 5, "Grafo y representación del curso"),
    "nn_mlp": ("Red con atributos del curso, sin grafo", "red", 5, "Grafo y representación del curso"),
    "nn_gnn_prereq": ("Red GraphSAGE (solo prerrequisitos)", "red_grafo", 5, "Grafo y representación del curso"),
    "nn_gnn": ("Red GraphSAGE (prerrequisitos + coinscripción)", "red_grafo", 5, "Grafo y representación del curso"),
}
T3_MODELOS = {
    "km_global": ("Aalen-Johansen global", "referencia", 0, "Sin covariables"),
    "km_programa": ("Aalen-Johansen por programa", "referencia", 0, "Sin covariables"),
    "cox_adm": ("Cox causa-específico (ingreso)", "regresion", 1, "Solo perfil de ingreso"),
    "dt_lr_adm": ("Logística persona-período (ingreso)", "regresion", 1, "Solo perfil de ingreso"),
    "dt_cb_adm": ("CatBoost persona-período (ingreso)", "arboles", 1, "Solo perfil de ingreso"),
    "nn_mlp_adm": ("Red MLP de riesgos discretos (ingreso)", "red", 1, "Solo perfil de ingreso"),
    "cox_agg": ("Cox causa-específico (ingreso + agregados)", "regresion", 2, "+ agregados académicos al corte"),
    "dt_lr_agg": ("Logística persona-período (ingreso + agregados)", "regresion", 2, "+ agregados académicos al corte"),
    "dt_cb_agg": ("CatBoost persona-período (ingreso + agregados)", "arboles", 2, "+ agregados académicos al corte"),
    "nn_mlp_agg": ("Red MLP de riesgos discretos (ingreso + agregados)", "red", 2, "+ agregados académicos al corte"),
    "nn_gru": ("Red GRU de riesgos discretos (+ secuencia)", "red", 3, "+ secuencia por semestre (GRU)"),
}
MODELOS = {"t1": T1_MODELOS, "t2": T2_MODELOS, "t3": T3_MODELOS}
ETIQUETA_METRICA = {"ap": "AP", "roc_auc": "ROC-AUC", "brier": "Brier", "ece": "ECE", "c_12": "C(12)", "ibs": "IBS",
                    "recall_at_1": "Recall@1", "recall_10": "Recall@10 %"}
ESCALA_CODIGO = -1          # ``corte_k`` of the rows that come from constants in the model code, not from a run


def _num(x) -> Optional[float]:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x else None


def _es_metrica(v) -> bool:
    return isinstance(v, dict) and "punto" in v


def menor_es_mejor(metrica: str) -> bool:
    return metrica.startswith(("brier", "ece")) or metrica == "ibs"


def veredicto(metrica: str, lo: Optional[float], hi: Optional[float]) -> str:
    """Reading of a paired-difference interval (A - B) for the metric's direction."""
    if lo is None or hi is None:
        return "sin_diferencia"
    if lo > 0:
        return "empeora" if menor_es_mejor(metrica) else "mejora"
    if hi < 0:
        return "mejora" if menor_es_mejor(metrica) else "empeora"
    return "sin_diferencia"


def _fila_modelo(tarea: str, corte_k: int, modelo: str, metrica: str, v: Dict, n_eval: Optional[int]) -> Dict:
    nombre, familia, escalon, escalon_nombre = MODELOS[tarea][modelo]
    return {"tarea": tarea, "corte_k": corte_k, "conjunto": CONJUNTO, "modelo": modelo, "modelo_nombre": nombre,
            "familia": familia, "escalon": escalon, "escalon_nombre": escalon_nombre, "metrica": metrica,
            "valor": _num(v.get("punto")), "ic_inf": _num(v.get("lo")), "ic_sup": _num(v.get("hi")),
            "n_evaluacion": n_eval}


def _metricas(tarea: str, corte_k: int, test: Dict, n_eval: Optional[int]) -> List[Dict]:
    filas = []
    for modelo, metricas in test.items():
        if modelo.startswith("__") or modelo not in MODELOS[tarea] or not isinstance(metricas, dict):
            continue
        for metrica, v in metricas.items():
            if _es_metrica(v):
                filas.append(_fila_modelo(tarea, corte_k, modelo, metrica, v, n_eval))
    return filas


def _deltas(tarea: str, corte_k: int, test: Dict) -> List[Dict]:
    filas = []
    for clave, metricas in test.items():
        if not clave.startswith("__delta") or not isinstance(metricas, dict):
            continue
        if clave == "__delta_gru_vs_cb_acad":
            a, b = "gru_seq", "cb_acad"
        else:
            partes = [p for p in clave.split("__") if p and p != "delta"]
            if len(partes) == 1 and tarea == "t1":
                a, b = partes[0], "baseline_tasa"
            elif len(partes) == 2:
                a, b = partes
            else:
                continue
        if a not in MODELOS[tarea] or b not in MODELOS[tarea]:
            continue
        for metrica, v in metricas.items():
            if _es_metrica(v):
                lo, hi = _num(v.get("lo")), _num(v.get("hi"))
                filas.append({"tarea": tarea, "corte_k": corte_k, "conjunto": CONJUNTO, "modelo_a": a, "modelo_b": b,
                              "metrica": metrica, "delta": _num(v.get("punto")), "ic_inf": lo, "ic_sup": hi,
                              "veredicto": veredicto(metrica, lo, hi)})
    return filas


# --------------------------------------------------------------------------------------------- architecture info
def _texto_capas(h) -> str:
    return "-".join(str(int(x)) for x in h)


def _info_modelo(tarea: str, corte_k: int, modelo: str, info: Dict) -> List[Dict]:
    filas: List[Dict] = []

    def num(clave, valor):
        v = _num(valor)
        if v is not None:
            filas.append({"tarea": tarea, "corte_k": corte_k, "modelo": modelo, "clave": clave, "valor_num": v,
                          "valor_texto": None})

    def texto(clave, valor):
        filas.append({"tarea": tarea, "corte_k": corte_k, "modelo": modelo, "clave": clave, "valor_num": None,
                      "valor_texto": valor})

    pars = [s["n_parametros"] for s in info.get("semillas", []) if isinstance(s, dict) and "n_parametros" in s]
    if pars:
        num("n_parametros", statistics.median(pars))
    h = info.get("hidden")
    if isinstance(h, (list, tuple)):
        texto("hidden", _texto_capas(h))
    else:
        num("hidden", h)
    for clave in ("gru_hidden", "static_dim", "d_secuencia", "n_variables_estaticas", "n_variables", "batch", "lr",
                  "weight_decay", "gpu_pico_mb", "n_nodos", "n_aristas_prerrequisito", "n_pares_coinscripcion",
                  "nodos_con_malla"):
        num(clave, info.get(clave))
    if info.get("mejores_iteraciones"):
        num("iteraciones", statistics.median(info["mejores_iteraciones"]))
    params = info.get("params") or {}
    for clave, destino in (("depth", "profundidad"), ("learning_rate", "tasa_aprendizaje"),
                           ("iterations", "iteraciones_max")):
        try:
            num(destino, float(params[clave]))
        except (KeyError, TypeError, ValueError):
            pass
    return filas


def _info(tarea: str, corte_k: int, info: Dict) -> List[Dict]:
    return [f for modelo, d in info.items() if isinstance(d, dict) for f in _info_modelo(tarea, corte_k, modelo, d)]


def arquitectura_desde_codigo() -> List[Dict]:
    """Layer sizes read from the model code itself (instantiating small models), marked with ``corte_k = -1``."""
    import inspect

    from models import catboost_modelo, gru, t2_grafo, t3_redes

    filas: List[Dict] = []

    def add(tarea, modelo, clave, valor):
        if isinstance(valor, str):
            filas.append({"tarea": tarea, "corte_k": ESCALA_CODIGO, "modelo": modelo, "clave": clave,
                          "valor_num": None, "valor_texto": valor})
        else:
            filas.append({"tarea": tarea, "corte_k": ESCALA_CODIGO, "modelo": modelo, "clave": clave,
                          "valor_num": float(valor), "valor_texto": None})

    red = gru.RedGRU(d_seq=13, n_num=20, cardinalidades=[5, 3])
    add("t1", "gru_t1", "hidden", gru.HIDDEN)
    add("t1", "gru_t1", "static_dim", gru.STATIC_DIM)
    add("t1", "gru_t1", "emb_max", gru.EMB_MAX)
    add("t1", "gru_t1", "cabeza_oculta", red.cabeza[0].out_features)
    add("t1", "catboost", "profundidad", catboost_modelo.PARAMS["depth"])
    add("t1", "catboost", "iteraciones_max", catboost_modelo.PARAMS["iterations"])
    add("t1", "catboost", "tasa_aprendizaje", catboost_modelo.PARAMS["learning_rate"])

    riesgos = t3_redes.RedRiesgos(n_num=10, cardinalidades=[4], U=8, d_seq=13)
    add("t3", "nn_gru", "capas", _texto_capas(t3_redes.HIDDEN))
    add("t3", "nn_gru", "gru_hidden", t3_redes.GRU_HIDDEN)
    add("t3", "nn_gru", "cabeza_oculta", riesgos.cabeza[0].out_features)
    add("t3", "nn_gru", "salida_por_semestre", 3)
    add("t3", "nn_mlp_agg", "capas", _texto_capas(t3_redes.HIDDEN))
    add("t3", "nn_mlp_agg", "salida_por_semestre", 3)

    enc = inspect.signature(t2_grafo.CodificadorGrafo.__init__).parameters
    add("t2", "nn_gnn", "sage_d_hid", enc["d_hid"].default)
    add("t2", "nn_gnn", "sage_d_out", enc["d_out"].default)
    add("t2", "nn_gnn", "capas_sage", sum(1 for n in ("c1", "c2")
                                          if isinstance(getattr(t2_grafo.CodificadorGrafo(5, [3], 2), n), t2_grafo.CapaSage)))
    add("t2", "nn_gnn", "relaciones", 3)            # previo, posterior, co (coinscripcion)
    add("t2", "nn_gnn", "capas", _texto_capas(t2_grafo.HIDDEN))
    add("t2", "nn_mlp", "capas", _texto_capas(t2_grafo.HIDDEN))
    return filas


# ------------------------------------------------------------------------------------------------- headlines
VERBO = {"mejora": "supera a", "sin_diferencia": "no se distingue de", "empeora": "queda por debajo de"}


def _coma(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def _titular(deltas: Dict, tarea: str, corte_k: int, a: str, b: str, metrica: str, tema: str) -> Optional[str]:
    d = deltas.get((tarea, corte_k, a, b, metrica))
    if d is None or d["delta"] is None or d["ic_inf"] is None or d["ic_sup"] is None:
        return None
    etiqueta = ETIQUETA_METRICA.get(metrica, metrica)
    nombre = MODELOS[tarea]
    return (f"{tema}: {nombre[a][0]} {VERBO[d['veredicto']]} {nombre[b][0]} "
            f"(Δ{etiqueta} {_coma(d['delta'])} [{_coma(d['ic_inf'])}; {_coma(d['ic_sup'])}], conjunto de prueba).")


# (tarea, corte_k, clave, A, B, métrica, tema)
def _plan_titulares() -> Iterable[tuple]:
    for k in (1, 2):
        yield ("t1", k, f"t1_agregados_k{k}", "cb_acad", "baseline_tasa", "ap",
               f"Desempeño académico al corte (k = {k})")
        yield ("t1", k, f"t1_gru_vs_arboles_k{k}", "gru_seq", "cb_acad", "ap", f"Secuencia por semestre (k = {k})")
    yield ("t2", 0, "t2_prerrequisitos", "cb_c", "cb_b", "ap", "Prerrequisitos explícitos")
    yield ("t2", 0, "t2_variables_nuevas", "cb_c_nuevas", "cb_c", "ap", "Promedio en el departamento y semestre anterior (D118)")
    yield ("t2", 0, "t2_grafo", "nn_gnn", "nn_mlp", "ap", "Grafo curricular (GraphSAGE frente a la misma red sin aristas)")
    yield ("t2", 0, "t2_embeddings", "cb_cemb", "cb_c", "ap", "Embeddings del grafo en CatBoost")
    yield ("t2", 0, "t2_deriva_decay", "cb_c_decay", "cb_c", "ap", "Estadística del curso con decaimiento (P55)")
    yield ("t2", 0, "t2_deriva_ventana", "cb_c_vent", "cb_c", "ap", "Estadística del curso con ventana reciente (P55)")
    yield ("t2", 0, "t2_docente", "cb_d", "cb_c", "ap", "Historial de sección o docente")
    yield ("t3", 0, "t3_mlp_ingreso_k0", "nn_mlp_adm", "cox_adm", "c_12", "Red al ingreso (k = 0)")
    for k in (2, 4):
        yield ("t3", k, f"t3_gru_vs_cox_k{k}", "nn_gru", "cox_agg", "c_12", f"Secuencia por semestre (k = {k})")


def _titulares(deltas: List[Dict]) -> List[Dict]:
    idx = {(d["tarea"], d["corte_k"], d["modelo_a"], d["modelo_b"], d["metrica"]): d for d in deltas}
    contador: Dict[str, int] = {}
    salida = []
    for tarea, k, clave, a, b, metrica, tema in _plan_titulares():
        texto = _titular(idx, tarea, k, a, b, metrica, tema)
        if texto:
            contador[tarea] = contador.get(tarea, 0) + 1
            salida.append({"tarea": tarea, "orden": contador[tarea], "clave": clave, "texto": texto})
    return salida


# ------------------------------------------------------------------------------------------------------ build
def construir(t1: Dict, t2: Dict, t3: Dict) -> Dict[str, List[Dict]]:
    metricas: List[Dict] = []
    deltas: List[Dict] = []
    info: List[Dict] = []
    for r in (t1.get("resultados") or {}).values():
        k = int(r["k"])
        test = r.get("test") or {}
        n_eval = ((r.get("n") or {}).get(CONJUNTO) or {}).get("n")
        metricas += _metricas("t1", k, test, n_eval)
        deltas += _deltas("t1", k, test)
        info += _info("t1", k, r.get("info") or {})
    ev = (t2.get("evaluacion") or {}).get(CONJUNTO) or {}
    n2 = (((t2.get("descriptivo") or {}).get("split") or {}).get(CONJUNTO) or {}).get("n")
    metricas += _metricas("t2", 0, ev, n2)
    deltas += _deltas("t2", 0, ev)
    info += _info("t2", 0, t2.get("info") or {})
    for ks, bloque in (t3.get("por_k") or {}).items():
        test = bloque.get(CONJUNTO) or {}
        n3 = (bloque.get("n_split") or {}).get(CONJUNTO)
        metricas += _metricas("t3", int(ks), test, n3)
        deltas += _deltas("t3", int(ks), test)
    for ks, d in (t3.get("info") or {}).items():
        info += _info("t3", int(ks), d)
    return {"metricas": metricas, "deltas": deltas, "info": info, "titulares": _titulares(deltas)}


# ------------------------------------------------------------------------------------------------- database
TABLAS = {
    "resumen_modelos": ("tarea", "corte_k", "conjunto", "modelo", "modelo_nombre", "familia", "escalon",
                        "escalon_nombre", "metrica", "valor", "ic_inf", "ic_sup", "n_evaluacion"),
    "resumen_modelos_delta": ("tarea", "corte_k", "conjunto", "modelo_a", "modelo_b", "metrica", "delta", "ic_inf",
                              "ic_sup", "veredicto"),
    "resumen_modelos_info": ("tarea", "corte_k", "modelo", "clave", "valor_num", "valor_texto"),
    "resumen_modelos_titular": ("tarea", "orden", "clave", "texto"),
}
_ORIGEN = {"resumen_modelos": "metricas", "resumen_modelos_delta": "deltas", "resumen_modelos_info": "info",
           "resumen_modelos_titular": "titulares"}


def escribir(conn, resumen: Dict[str, List[Dict]], mart_schema: str = "neural_mart") -> Dict[str, int]:
    """Replace the content of the summary tables in ONE transaction (a failure leaves the previous summary)."""
    from ..migrate import ALLOWED_SCHEMAS

    if mart_schema not in ALLOWED_SCHEMAS:
        raise ValueError(f"schema {mart_schema!r} is not one of {ALLOWED_SCHEMAS}")
    cuentas: Dict[str, int] = {}
    with conn.transaction():
        with conn.cursor() as cur:
            for tabla, columnas in TABLAS.items():
                cur.execute(f"DELETE FROM {mart_schema}.{tabla}")
                filas = [tuple(f.get(c) for c in columnas) for f in resumen[_ORIGEN[tabla]]]
                if filas:
                    marcas = ", ".join(["%s"] * len(columnas))
                    cur.executemany(
                        f"INSERT INTO {mart_schema}.{tabla} ({', '.join(columnas)}) VALUES ({marcas})", filas)
                cuentas[tabla] = len(filas)
            cur.execute(f"DELETE FROM {mart_schema}.resumen_modelos_construccion")
            cur.execute(f"INSERT INTO {mart_schema}.resumen_modelos_construccion (id, filas) VALUES (1, %s)",
                        (sum(cuentas.values()),))
    return cuentas
