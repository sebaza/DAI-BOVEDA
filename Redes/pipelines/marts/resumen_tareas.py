"""Per-task summary (T1-T6) for the "Modelos" view of the Boveda (``neural_mart.resumen_tarea*``, migration 023).

Pure transformation of the five gitignored result files (``artefactos/resultados_t{1,2,3,45,6}.json``) plus a dictionary
of program names and faculties. Only aggregates come out: metrics with their bootstrap intervals, paired differences,
calibration deciles, expected-versus-observed rates by program, faculty, sex, admission route and school type (every group,
whatever its size, with its 95 % intervals: the rows come from ``artefactos/grupos_todos.json``, see
``evaluation/grupos_todos.py``; with that file given, a missing block or a block of another model than the kept one is an error,
never a fallback to the benchmark tables), the size of each split and short texts taken
from the benchmark reports (``docs/08`` to ``docs/12``) and ``docs/00_plan.md``. Never a prediction or a person key.
``tools/exportar_resumen_modelos.py`` writes the rows into the database.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import spearmanr

from evaluation.grupos_todos import BANDAS_T2, MODELO_BANDAS, POCOS_CASOS
from . import resumen_modelos as RM

# model key -> (display name, family, ladder rung, rung name)
T45_MODELOS = {
    "baseline_tasa": ("Tasa histórica del programa", "referencia", 0, "Solo el programa"),
    "lr_adm": ("Logística (solo perfil de ingreso)", "regresion", 1, "Solo perfil de ingreso"),
    "cb_adm": ("CatBoost (solo perfil de ingreso)", "arboles", 1, "Solo perfil de ingreso"),
    "lr_agg": ("Logística (ingreso + agregados)", "regresion", 2, "+ agregados académicos al corte"),
    "cb_agg": ("CatBoost (ingreso + agregados)", "arboles", 2, "+ agregados académicos al corte"),
    "gru_adm": ("GRU (ingreso + secuencia)", "red", 3, "+ secuencia por semestre (GRU)"),
    "gru_agg": ("GRU (ingreso + agregados + secuencia)", "red", 3, "+ secuencia por semestre (GRU)"),
}
T6_MODELOS = {
    "baseline_programa": ("Incidencia histórica por programa", "referencia", 0, "Solo el programa"),
    "cox_perfil": ("Cox (perfil de ingreso)", "regresion", 1, "Solo perfil de ingreso"),
    "cox_agg": ("Cox (ingreso + trayectoria académica)", "regresion", 2, "+ trayectoria académica hasta el egreso"),
}
# T1 with student benefits (16-11-2026, D90-D95): the same two model families with one more feature step each.
T1_BENEFICIOS_MODELOS = {
    "lr_ben": ("Logística (+ beneficios)", "regresion", 3, "+ beneficios estudiantiles"),
    "cb_ben": ("CatBoost (+ beneficios)", "arboles", 3, "+ beneficios estudiantiles"),
    "lr_ben_perd": ("Logística (+ beneficios y pérdidas)", "regresion", 4, "+ pérdida de beneficios (solo k = 4)"),
    "cb_ben_perd": ("CatBoost (+ beneficios y pérdidas)", "arboles", 4, "+ pérdida de beneficios (solo k = 4)"),
    # official k = 1 model from the 2024 cohort (D113): benefits as they stood at the cut, from the load history
    "cb_ben_pit": ("CatBoost oficial (+ beneficios al corte)", "arboles", 3, "+ beneficios estudiantiles al corte"),
}
MODELOS = {**RM.MODELOS, "t4": T45_MODELOS, "t5": T45_MODELOS, "t6": T6_MODELOS}
MODELOS["t1"] = {**RM.MODELOS["t1"], **T1_BENEFICIOS_MODELOS}

BANDAS = ("reprobado", "unanimidad", "distincion", "maxima_distincion")
ETIQUETA_BANDA = {"reprobado": "Reprobado", "unanimidad": "Aprobado por Unanimidad",
                  "distincion": "Aprobado con Distinción", "maxima_distincion": "Aprobado con Máxima Distinción"}
NIVEL_POSTGRADO = {"magister": "Magíster", "doctorado": "Doctorado", "otro": "Otro postgrado"}
# levels of the group tables (migration 034): the summaries (``grupo_resumen``) exist for the first two only
NIVELES_RESUMEN = ("programa", "facultad")
NIVELES_GRUPO = NIVELES_RESUMEN + ("sexo", "via", "tipo_colegio")

# ------------------------------------------------------------------------------------------------ fixed texts
# Every sentence below comes from the benchmark reports (docs/08 to docs/12) or the decision log (docs/00_plan.md).
FICHAS = {
    "t1": {
        "orden": 1, "nombre": "T1 · Continuidad", "estado": "completo", "estado_etiqueta": "Benchmark completo",
        "pregunta": ("¿La persona seguirá matriculada en la UCN dos períodos regulares después del corte? El evento es la "
                     "«no continuidad observada»: ya no se encuentra matriculada (no se llama deserción)."),
        "poblacion": ("Episodios de pregrado vigentes al cierre del primer o segundo semestre regular (k = 1 o 2). Se entrena con "
                      "las cohortes 2015 a 2019, se elige con 2020-2021 y se evalúa con 2022-2023."),
        "evento": "no continuidad observada",
        "veredicto_redes": ("Las redes no agregan señal: en validación la GRU sobre la secuencia de semestres no se separa del "
                            "mejor clásico (el intervalo de la diferencia pareada incluye el cero) y se conserva el modelo más "
                            "simple (D114). La información útil es el desempeño académico ya observado al corte."),
        "metrica_titular": "ap", "metrica_secundaria": "roc_auc",
    },
    "t2": {
        "orden": 2, "nombre": "T2 · Aprobación por ramo", "estado": "completo", "estado_etiqueta": "Benchmark completo",
        "pregunta": ("¿Reprobará el curso (nota menor que 4,0) cada intento evaluado de pregrado? Se estima antes de que "
                     "comience el período; por programa y facultad se pronostica además la banda de nota."),
        "poblacion": ("Intentos evaluados con nota numérica en períodos regulares 2015-2025. Se entrena con 2015-2020, se elige "
                      "con 2021-2022, se evalúa con 2023-2024 y 2025 queda como control posterior."),
        "evento": "reprobación del curso",
        "veredicto_redes": ("El grafo curricular y la red GraphSAGE no aportan: la diferencia es del orden de 0,005 de AP o "
                            "menos y la red queda bajo CatBoost. Lo que más aporta es la estadística del curso."),
        "metrica_titular": "ap", "metrica_secundaria": "roc_auc",
    },
    "t3": {
        "orden": 3, "nombre": "T3 · Tiempo hasta egreso", "estado": "completo", "estado_etiqueta": "Benchmark completo",
        "pregunta": ("¿Cuántos semestres pasan hasta el egreso, y con qué probabilidad ocurre antes de que la persona salga "
                     "del programa? Egreso y salida compiten entre sí."),
        "poblacion": ("Trayectorias de pregrado de las cohortes 2015 en adelante, sin el Programa de Intercambio y con el Plan "
                      "Común unido a su especialidad. Cortes al ingreso (k = 0) y tras 2 y 4 semestres; horizonte de hasta "
                      "14 semestres."),
        "evento": "egreso",
        "veredicto_redes": ("Las redes aportan en parte. Por la regla de selección en validación (D114), la GRU es el modelo "
                            "conservado en k = 2 y k = 4: su diferencia pareada con el mejor clásico excluye el cero en C(12) y en "
                            "IBS. En k = 4 la mejora en prueba es marginal y su IBS en prueba es levemente peor (+0,001). Al "
                            "ingreso (k = 0) las redes no aportan y se conserva el clásico. Los agregados académicos explican "
                            "casi toda la mejora."),
        "metrica_titular": "c_12", "metrica_secundaria": "ibs",
    },
    "t4": {
        "orden": 4, "nombre": "T4 · Cambio de programa", "estado": "completo", "estado_etiqueta": "Benchmark completo",
        "pregunta": ("¿La persona pasa a otro programa de pregrado (cambio de carrera, traslado de sede u otro traslado) dentro "
                     "de los dos semestres regulares siguientes al corte?"),
        "poblacion": ("Trayectorias de pregrado matriculadas al cierre del semestre k = 2 o 4, cohortes 2015 en adelante. Se "
                      "entrena con 2015-2019, se elige con 2020-2021 y se evalúa con 2022-2023. La elección de especialidad "
                      "desde el Plan Común no cuenta como cambio."),
        "evento": "traslado a otro programa",
        "veredicto_redes": ("Las redes no superan a los clásicos y se conserva el modelo clásico. T4 es poco predecible: con "
                            "el perfil de ingreso solo, ningún modelo supera de forma clara a la tasa histórica por programa."),
        "metrica_titular": "ap", "metrica_secundaria": "roc_auc",
    },
    "t5": {
        "orden": 5, "nombre": "T5 · Eliminación", "estado": "dato_en_revision", "estado_etiqueta": "Con dato en revisión",
        "pregunta": ("¿La persona recibe un estado de eliminación académica (E) dentro de los dos semestres regulares "
                     "siguientes al corte?"),
        "poblacion": ("La misma población y las mismas particiones que T4 (k = 2 o 4; prueba 2022-2023). Se evalúa de tres "
                      "maneras: con la etiqueta actual, con la eliminación efectiva (sin reintegro) y sin los años de registro "
                      "dudoso."),
        "evento": "eliminación académica",
        "veredicto_redes": ("La red supera a los clásicos: en validación la GRU mejora el AP del mejor clásico con un "
                            "intervalo que excluye el cero (D114), por lo que se conserva la GRU en k = 2 y k = 4 en las "
                            "tres evaluaciones. Las variables reglamentarias nuevas ordenan mejor el riesgo, pero calibran "
                            "peor en prueba y no se adoptan (D120)."),
        "metrica_titular": "ap", "metrica_secundaria": "roc_auc",
    },
    "t6": {
        "orden": 6, "nombre": "T6 · Postgrado UCN", "estado": "exploratorio", "estado_etiqueta": "Exploratorio",
        "pregunta": ("¿Cuánto tarda en matricularse por primera vez en un programa de postgrado de la UCN quien llegó al "
                     "egreso de pregrado? Se mira a 1, 2 y 4 años."),
        "poblacion": ("Trayectorias de pregrado que llegaron al egreso, cohortes 2015 en adelante, sin matrícula de postgrado "
                      "previa. Se entrena con egresos hasta 2022, se elige con 2023 y se evalúa con 2024 en adelante."),
        "evento": "primera matrícula en postgrado UCN",
        "veredicto_redes": ("Exploratorio: no se entrenaron CatBoost ni redes porque hay menos de 100 y de 300 eventos de "
                            "entrenamiento. A 1 año el Cox con el perfil de ingreso supera a la incidencia por programa; la "
                            "trayectoria académica no agrega nada."),
        "metrica_titular": "ap", "metrica_secundaria": "roc_auc",
    },
}

NOTAS = {
    "t1": [
        ("limite", "La etiqueta es «no continuidad observada», no deserción: incluye abandono sin registro, retiro no "
                   "formalizado, traslado a otra institución y errores de registro (P51)."),
        ("limite", "Con 280 y 499 eventos en prueba, diferencias menores que 0,03 de AP no son separables."),
        ("limite", "La señal sirve para ordenar a quienes ya cerraron el semestre; no es un sistema de alerta temprana."),
        ("dato", "Las salidas se registraban distinto antes de 2014 y los segundos semestres anteriores a 2015 no se "
                 "registraron (P49, P50): por eso se entrena desde las cohortes 2015."),
    ],
    "t2": [
        ("dato", "P58: en los períodos 201920 y 202010 (pandemia) no hay reprobaciones registradas. Se excluyen como unidades "
                 "y de las estadísticas de aprobación."),
        ("pendiente", "P55: calcular las estadísticas del curso con decaimiento exponencial mejora el AP en 0,011 con "
                      "intervalo que excluye el cero. Por la regla fijada debería ser el modelo por defecto, pero el cambio "
                      "está propuesto y no se aplicó en esta corrida."),
        ("limite", "La reprobación no es estacionaria (13,4 % en validación, 14,4 % en prueba, 17,2 % en 2025) y los modelos "
                   "subestiman el nivel en prueba. No se recalibró."),
        ("limite", "Por programa y facultad el pronóstico ordena bien los grupos y se equivoca menos que la frecuencia global, "
                   "salvo en la banda de distinción; subestima la reprobación de los programas de mayor reprobación."),
    ],
    "t3": [
        ("dato", "P58: los agregados académicos solo usan lo que la falta de reprobaciones de 201920 y 202010 no altera."),
        ("dato", "El evento es el egreso (malla completa), no la titulación (P59). La población excluye el Programa de "
                 "Intercambio y une el Plan Común a su especialidad."),
        ("limite", "La mediana de semestres hasta el egreso baja de 13 a 11 en las cohortes recientes (P60): los modelos solo "
                   "de ingreso subestiman el egreso en prueba. Conviene recalibrar antes de usar probabilidades absolutas."),
    ],
    "t4": [
        ("dato", "P58: los agregados académicos solo usan lo que la falta de reprobaciones de 201920 y 202010 no altera."),
        ("dato", "El traslado se fecha en la salida del programa de origen (P71). La elección de especialidad, el cambio de "
                 "ciclo y la continuación de estudios tras el egreso no son eventos."),
        ("limite", "El pronóstico agregado por programa y facultad no mejora la tasa histórica y no es confiable: con k = 2 el "
                   "modelo conservado sobreestima en unos siete puntos la tasa de traslado. Solo se muestra la tasa observada."),
    ],
    "t5": [
        ("dato", "P75: desde 202420 el estado E está subregistrado: baja a una cuarta parte o menos de lo habitual mientras los "
                 "traslados se mantienen. No se corrigió en las etiquetas."),
        ("dato", "Tres evaluaciones: la etiqueta actual, la eliminación efectiva (un E seguido de reintegro no cuenta) y sin las "
                 "filas de horizonte dudoso por P75. El modelo conservado no cambia entre ellas. Con k = 4 la tercera no se "
                 "puede evaluar (todas las filas de prueba son dudosas)."),
        ("dato", "P58: los agregados académicos solo usan lo que la falta de reprobaciones de 201920 y 202010 no altera."),
        ("limite", "Con k = 4 el riesgo medio predicho supera a la tasa observada en prueba, en parte por el subregistro de E."),
    ],
    "t6": [
        ("dato", "P80 y P86: la fuente antigua de postgrado era incompleta (su salto de 2023 era un artefacto de cobertura). El "
                 "evento sale de la fuente de estados de postgrado, completa desde 2015."),
        ("dato", "P58: la trayectoria académica usa solo lo que la falta de reprobaciones de 201920 y 202010 no altera."),
        ("limite", "Es un evento raro: a 1 año hay 46 matriculados en prueba (concluyente), a 2 años 12 y a 4 años ninguno con "
                   "seguimiento completo."),
        ("limite", "Solo se observa el postgrado de la UCN: una persona sin matrícula UCN puede haberse matriculado fuera (P82)."),
        ("limite", "El nivel (magíster, doctorado, otro) se deriva del nombre del programa (P77). Por programa y facultad "
                   "se listan todos los grupos, con su intervalo de 95 %; con tan pocos eventos las cifras por grupo son muy inciertas. "
                   "Los grupos reúnen la validación y la prueba."),
    ],
}

PRONOSTICO = {"t1": "descriptivo", "t2": "confiable", "t3": "descriptivo", "t4": "no_confiable", "t5": "confiable",
              "t6": "no_disponible"}
ETIQUETA_VARIANTE = {"base": "", "beneficios": "Con beneficios (16-11-2026)",
                     "beneficios_corte": "Modelo oficial desde la cohorte 2024 (beneficios al corte)", "extension_k4": "Extensión a 2 años (k = 4)",
                     "actual": "Etiqueta actual", "efectiva": "Eliminación efectiva (sin reintegro)",
                     "sin_dudosos": "Sin años de registro dudoso (P75)", "h2": "A 1 año", "h4": "A 2 años"}


# ----------------------------------------------------------------------------------------------------- helpers
def _num(x) -> Optional[float]:
    return RM._num(x)


def _m(v) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if isinstance(v, dict):
        return _num(v.get("punto")), _num(v.get("lo")), _num(v.get("hi"))
    n = _num(v)
    return n, None, None


def _entero(x) -> Optional[int]:
    v = _num(x)
    return None if v is None else int(round(v))


def _coma(x: float, dec: int = 3) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


def _fila_metrica(tarea, variante, k, modelo, metrica, v, n_eval, conservado) -> Dict[str, Any]:
    nombre, familia, escalon, escalon_nombre = MODELOS[tarea][modelo]
    return {"tarea": tarea, "variante": variante, "corte_k": k, "modelo": modelo, "modelo_nombre": nombre, "familia": familia,
            "escalon": escalon, "escalon_nombre": escalon_nombre, "metrica": metrica, "valor": _num(v.get("punto")),
            "ic_inf": _num(v.get("lo")), "ic_sup": _num(v.get("hi")), "n_evaluacion": n_eval,
            "conservado": modelo == conservado}


def _metricas(tarea, variante, k, test: Mapping, n_eval, conservado, solo: Optional[Iterable[str]] = None) -> List[Dict]:
    filas = []
    for modelo, metricas in test.items():
        if modelo not in MODELOS[tarea] or not isinstance(metricas, dict) or (solo is not None and modelo not in solo):
            continue
        for metrica, v in metricas.items():
            if RM._es_metrica(v):
                filas.append(_fila_metrica(tarea, variante, k, modelo, metrica, v, n_eval, conservado))
    return filas


def _fila_delta(tarea, variante, k, a, b, metrica, v) -> Dict[str, Any]:
    lo, hi = _num(v.get("lo")), _num(v.get("hi"))
    return {"tarea": tarea, "variante": variante, "corte_k": k, "modelo_a": a, "modelo_b": b, "metrica": metrica,
            "delta": _num(v.get("punto")), "ic_inf": lo, "ic_sup": hi, "veredicto": RM.veredicto(metrica, lo, hi)}


def _deltas_vs(tarea, variante, k, bloque: Mapping) -> List[Dict]:
    """Paired differences stored as ``'a__vs__b': {metric: {punto, lo, hi}}`` (T4, T5 and T6)."""
    filas = []
    for clave, metricas in bloque.items():
        if "__vs__" not in clave or not isinstance(metricas, dict):
            continue
        a, b = clave.split("__vs__")
        if a not in MODELOS[tarea] or b not in MODELOS[tarea]:
            continue
        filas += [_fila_delta(tarea, variante, k, a, b, met, v) for met, v in metricas.items() if RM._es_metrica(v)]
    return filas


def _deltas_rm(tarea, variante, k, test: Mapping) -> List[Dict]:
    return [_fila_delta(tarea, variante, k, d["modelo_a"], d["modelo_b"], d["metrica"],
                        {"punto": d["delta"], "lo": d["ic_inf"], "hi": d["ic_sup"]}) for d in RM._deltas(tarea, k, test)]


def _calibracion(tarea, variante, k, bloque: Mapping, indice="decil") -> List[Dict]:
    filas = []
    for modelo, deciles in bloque.items():
        if modelo not in MODELOS[tarea] or not isinstance(deciles, list):
            continue
        for d in deciles:
            n = _entero(d.get("n"))
            if n is None:
                continue
            filas.append({"tarea": tarea, "variante": variante, "corte_k": k, "modelo": modelo,
                          "decil": int(d.get(indice, d.get("grupo", 0))), "n": n, "riesgo_medio": _num(d.get("riesgo_medio")),
                          "tasa_observada": _num(d.get("tasa_observada"))})
    return filas


def _particiones(tarea, variante, k, partes: Mapping[str, Tuple[Any, Any]]) -> List[Dict]:
    filas = []
    for particion, (n, eventos) in partes.items():
        n, eventos = _entero(n), _entero(eventos)
        if n is None:
            continue
        filas.append({"tarea": tarea, "variante": variante, "corte_k": k, "particion": particion, "n": n, "eventos": eventos,
                      "tasa": (eventos / n) if eventos is not None and n > 0 else None, "tasa_inf": None, "tasa_sup": None})
    return filas


def _vista(tarea, variante, k, principal, conservado, referencia, concluyente=True, nota=None) -> Dict[str, Any]:
    ficha = FICHAS[tarea]
    etiqueta = ETIQUETA_VARIANTE.get(variante, "")
    return {"tarea": tarea, "variante": variante, "corte_k": k, "etiqueta": etiqueta, "principal": principal,
            "conservado_modelo": conservado, "referencia_modelo": referencia, "metrica_titular": ficha["metrica_titular"],
            "metrica_secundaria": ficha["metrica_secundaria"], "concluyente": concluyente,
            "pronostico_agregado": PRONOSTICO[tarea], "nota": nota}


# ----------------------------------------------------------------------------------------------- groups
def _nombre_programa(grupo: str, fila: Mapping, programas: Mapping) -> Tuple[str, Optional[str]]:
    nom, fac = programas.get(grupo, (None, None))
    return (fila.get("nombre") or nom or grupo), (fila.get("facultad") or fac)


def _fila_grupo(tarea, variante, k, nivel, categoria, fila, programas, observada, esperada, referencia, eventos, n=None,
                ap=None, roc_auc=None) -> Optional[Dict]:
    n = _entero(fila.get("n")) if n is None else n
    if n is None:
        return None
    obs, obs_inf, obs_sup = observada
    grupo = str(fila["grupo"])
    if nivel == "programa":
        nombre, facultad = _nombre_programa(grupo, fila, programas)
    elif nivel == "nivel_postgrado":
        nombre, facultad = NIVEL_POSTGRADO.get(grupo, grupo), None
    else:
        nombre, facultad = grupo, None
    esp, esp_inf, esp_sup = esperada
    # intervals of AP and ROC-AUC exist only on ``grupos_todos`` rows; the rate intervals are the observed / expected ones
    return {"tarea": tarea, "variante": variante, "corte_k": k, "nivel": nivel, "categoria": categoria, "grupo": grupo,
            "nombre": nombre, "facultad": facultad, "n": n, "eventos": eventos, "observada": obs, "obs_inf": obs_inf,
            "obs_sup": obs_sup, "esperada": esp, "esp_inf": esp_inf, "esp_sup": esp_sup,
            "referencia": _num(referencia), "ap": _num(ap), "roc_auc": _num(roc_auc),
            "ap_lo": _num(fila.get("ap_lo")), "ap_hi": _num(fila.get("ap_hi")), "auc_lo": _num(fila.get("auc_lo")),
            "auc_hi": _num(fila.get("auc_hi")), "tasa_lo": obs_inf, "tasa_hi": obs_sup, "esperado_lo": esp_inf,
            "esperado_hi": esp_sup, "pocos_casos": n < POCOS_CASOS}


def _resumen_grupo(tarea, variante, k, nivel, categoria, r: Mapping, mae_modelo=None, mae_base=None, spearman=None,
                   n_filas=0) -> Dict:
    """Group counts of a table (``grupos_reportables`` = rows listed) and its calibration summary."""
    total = _entero(r.get("grupos_total"))
    return {"tarea": tarea, "variante": variante, "corte_k": k, "nivel": nivel, "categoria": categoria,
            "grupos_total": n_filas if total is None else max(total, n_filas), "grupos_reportables": n_filas,
            "mae_modelo": _m(mae_modelo)[0], "mae_base": _m(mae_base)[0], "spearman": _m(spearman)[0]}


def _resumen_filas(tarea, variante, k, nivel, categoria, filas: Sequence[Mapping]) -> Dict:
    """Summary of the ``grupos_todos`` rows of a level: n-weighted mean absolute gap of the model and of the reference against the
    observed rate, and the Spearman correlation between expected and observed rates (None with fewer than 3 groups)."""
    ok = [f for f in filas if f.get("tasa") is not None and f.get("esperado") is not None and f.get("n")]
    mae = mae_base = rho = None
    if ok:
        peso = np.array([f["n"] for f in ok], dtype="float64")
        tasa = np.array([f["tasa"] for f in ok], dtype="float64")
        esp = np.array([f["esperado"] for f in ok], dtype="float64")
        mae = float(np.average(np.abs(esp - tasa), weights=peso))
        if all(f.get("referencia") is not None for f in ok):
            mae_base = float(np.average(np.abs(np.array([f["referencia"] for f in ok], dtype="float64") - tasa), weights=peso))
        if len(ok) >= 3 and np.ptp(tasa) > 0 and np.ptp(esp) > 0:
            rho = float(spearmanr(esp, tasa).correlation)
    return _resumen_grupo(tarea, variante, k, nivel, categoria, {}, mae, mae_base, rho, len(filas))


# ------------------------------------------------------------------------------------------------- tasks
# Kept model per task and cut under the single selection rule (D114): chosen on VALID with the headline metric; a network
# replaces the best classical model only if their paired difference on valid has a 95 % CI that excludes 0 (for T3 on
# C(12), with IBS not worse); on a tie the simpler model stays (logistic < CatBoost < network). Test only confirms.
CONSERVADO_T1 = {1: "cb_acad", 2: "lr_acad"}
CONSERVADO_RED_T3 = {2: "nn_gru", 4: "nn_gru"}
# k = 0 (D114): best classical on the headline metric C(12) on valid is the person-period logistic (0.754 vs 0.735 for
# CatBoost); the MLP (0.757) does not separate from it, so the simpler model stays
CONSERVADO_CLASICO_T3 = {0: "dt_lr_adm"}
CLASICO_COMPARACION_T3 = "dt_cb_agg"                 # best classical at k = 2 and 4 on valid
NOTA_T1 = {
    2: ("En validación la logística, CatBoost y la GRU no se separan (la diferencia pareada GRU − CatBoost incluye el cero); "
        "por la regla D114 se conserva la logística, el modelo más simple. En prueba CatBoost obtiene un AP algo mayor, pero la "
        "prueba solo confirma y no elige."),
}
NOTA_T3 = {
    2: "El modelo conservado es la GRU (D114): en validación mejora el C(12) y el IBS del mejor clásico con IC que excluye el cero.",
    4: ("El modelo conservado es la GRU (D114): en validación mejora el C(12) y el IBS del mejor clásico con IC que excluye el "
        "cero. En prueba la mejora de C(12) es marginal y su IBS es levemente peor (+0,001); se informa como salvedad."),
}


def _grupos_45(tarea, variante, k, grupos: Mapping, programas, out) -> None:
    """Group rows of the ``tabla_agregada`` blocks (``{"programa": ..., "facultad": ...}``) of a task / view."""
    for nivel in ("programa", "facultad"):
        bloque = grupos.get(nivel) or {}
        resumen = bloque.get("resumen") or {}
        listados = 0
        for f in bloque.get("filas", []):
            n, ev = _entero(f.get("n")), _entero(f.get("eventos"))
            g = _fila_grupo(tarea, variante, k, nivel, "", f, programas, _m(f.get("tasa_observada")), _m(f.get("riesgo_medio")),
                            _m(f.get("riesgo_medio_base"))[0], ev, n, f.get("ap"), f.get("roc_auc"))
            if g:
                out["grupo"].append(g)
                listados += 1
        out["grupo_resumen"].append(_resumen_grupo(tarea, variante, k, nivel, "", resumen, resumen.get("mae_modelo"),
                                                   resumen.get("mae_base"), resumen.get("spearman_modelo"), listados))


def _bloque_todos(gt: Optional[Mapping], tarea: str, variante: str, k: int, modelo: Optional[str]) -> Optional[Mapping]:
    """Block of ``artefactos/grupos_todos.json`` for this task, view and cut.

    ``gt`` None means no file was given (only tests and ad-hoc runs): the benchmark's own tables are used. With a file, the block must
    exist and hold the kept model's figures; otherwise this raises (no silent fallback to the benchmark's filtered tables).
    """
    if gt is None:
        return None
    blk = ((((gt.get("tareas") or {}).get(tarea)) or {}).get(variante) or {}).get(str(k)) or {}
    if not blk.get("dimensiones"):
        raise ValueError(f"grupos_todos.json has no block for {tarea}/{variante}/k={k}: regenerate it with "
                         "`python -m evaluation.grupos_todos`")
    if blk.get("modelo") != modelo:
        raise ValueError(f"grupos_todos.json holds {blk.get('modelo')!r} for {tarea}/{variante}/k={k} but the kept model is "
                         f"{modelo!r}: regenerate it with `python -m evaluation.grupos_todos`")
    return blk


def _grupos_todos(tarea, variante, k, bloque: Mapping, programas, out, categoria: str = "") -> None:
    """Rows of every dimension of a ``grupos_todos`` block (program, faculty, sex, route, school type): every group, with its
    intervals and model figures. Only program and faculty get a ``grupo_resumen`` row."""
    for nivel in NIVELES_GRUPO:
        filas = (bloque.get("dimensiones") or {}).get(nivel) or []
        for f in filas:
            g = _fila_grupo(tarea, variante, k, nivel, categoria, f, programas,
                            (_num(f.get("tasa")), _num(f.get("tasa_lo")), _num(f.get("tasa_hi"))),
                            (_num(f.get("esperado")), _num(f.get("esperado_lo")), _num(f.get("esperado_hi"))),
                            f.get("referencia"), _entero(f.get("eventos")), _entero(f.get("n")), f.get("ap"), f.get("auc"))
            if g:
                out["grupo"].append(g)
        if nivel in NIVELES_RESUMEN:
            out["grupo_resumen"].append(_resumen_filas(tarea, variante, k, nivel, categoria, filas))


def _tarea_t1(t1: Mapping, programas, out, gt: Optional[Mapping] = None) -> None:
    for r in (t1.get("resultados") or {}).values():
        k = int(r["k"])
        test = r.get("test") or {}
        n_split = r.get("n") or {}
        n_eval = _entero((n_split.get("test") or {}).get("n"))
        conservado = CONSERVADO_T1.get(k, "cb_acad")
        out["metrica"] += _metricas("t1", "base", k, test, n_eval, conservado)
        out["delta"] += _deltas_rm("t1", "base", k, test)
        out["calibracion"] += _calibracion("t1", "base", k, r.get("calibracion_test") or {})
        out["particion"] += _particiones("t1", "base", k, {p: (v.get("n"), v.get("eventos")) for p, v in n_split.items()})
        out["vista"].append(_vista("t1", "base", k, k == 1, conservado, "baseline_tasa", nota=NOTA_T1.get(k)))
        nuevos = _bloque_todos(gt, "t1", "base", k, conservado)
        if nuevos:
            _grupos_todos("t1", "base", k, nuevos, programas, out)
            continue
        listados = 0
        for f in ((r.get("subgrupos_test") or {}).get(conservado) or {}).get("programa", []):
            n = _entero(f.get("n"))
            obs = _num(f.get("tasa_observada"))
            ev = None if n is None or obs is None else int(round(n * obs))
            g = _fila_grupo("t1", "base", k, "programa", "", f, programas, (obs, None, None),
                            (_num(f.get("riesgo_medio")), None, None), None, ev, n, f.get("ap"), f.get("roc_auc"))
            if g:
                out["grupo"].append(g)
                listados += 1
        out["grupo_resumen"].append(_resumen_grupo("t1", "base", k, "programa", "", {}, n_filas=listados))


NOTA_BENEFICIOS = {
    1: ("Ablación con la vista final de los beneficios (§14): no es adoptable, porque el corte es a mitad de año y las filas de "
        "la vista final no son las que existían en ese momento (hay filas que aún no estaban y filas retiradas a quienes dejan "
        "los estudios). El modelo oficial de k = 1 desde la cohorte 2024 es la evaluación «Modelo oficial desde la cohorte 2024 "
        "(beneficios al corte)» (D113), que usa los beneficios vigentes al corte."),
    2: ("Corte al cierre del año: la vista final de los beneficios se parece a la del cierre. Se usa solo el monto del primer "
        "semestre; el del segundo se anula para parte de las personas al cerrar el año."),
    4: ("Extensión secundaria al cierre del segundo año: es el único corte donde existe la pérdida de beneficios entre el año 1 y "
        "el año 2. La configuración oficial (k = 1 y 2) no cambia."),
}


def _tarea_t1_beneficios(t1b: Mapping, programas, out, gt: Optional[Mapping] = None) -> None:
    """Views of the benefit ablation: k = 1 and 2 ("beneficios") and the k = 4 extension ("extension_k4"). The official view
    (variante "base") stays the principal one."""
    for blk in (t1b.get("resultados") or {}).values():
        k = int(blk["k"])
        variante = "extension_k4" if k == 4 else "beneficios"
        _objetivo_45("t1", variante, k, blk, programas, out, False, NOTA_BENEFICIOS.get(k), gt)


NOTA_BENEFICIOS_CORTE = (
    "Modelo oficial de k = 1 para las cohortes desde 2024 (D113): CatBoost con los beneficios vigentes al corte, reconstruidos "
    "desde el historial de cargas y con los montos corregidos. Se elige con la cohorte 2024 y se evalúa con la 2025. El pronóstico "
    "por programa y facultad y la calibración reúnen las cohortes 2024 y 2025. k = 2 no cambia (logística académica).")
MODELOS_BENEFICIOS_CORTE = ("baseline_tasa", "cb_acad", "cb_ben_pit")
PARES_BENEFICIOS_CORTE = ("cb_ben_pit__vs__cb_acad", "cb_acad__vs__baseline_tasa")


def _tarea_t1_beneficios_corte(t1c: Mapping, programas, out, gt: Optional[Mapping] = None) -> None:
    """Official k = 1 model from the 2024 cohort (D113, variante "beneficios_corte"): validation = cohort 2024, test = 2025.
    Only the academic and the adopted model are shown; groups and calibration come pooled over both cohorts."""
    blk = ((t1c.get("resultados") or {}).get("k1")) or {}
    anios = blk.get("por_anio") or {}
    valid, test = anios.get("2024"), anios.get("2025")
    if not valid or not test:
        return
    n = blk.get("n") or {}

    def parte(anio_blk):
        ev, tot = _entero(anio_blk.get("eventos")), _entero(anio_blk.get("n"))
        return {"n": tot, "eventos": ev, "tasa": (ev / tot) if ev is not None and tot else None}

    pares = {c: v for c, v in test.items() if c in PARES_BENEFICIOS_CORTE}
    modelos = {m: test[m] for m in MODELOS_BENEFICIOS_CORTE if m in test}
    normalizado = {
        "n": {"train": {"n": _entero(n.get("train")), "eventos": None}, "valid": parte(valid), "test": parte(test)},
        "test": {**modelos, **pares},
        "calibracion_test": {m: v for m, v in (blk.get("calibracion") or {}).items() if m in MODELOS_BENEFICIOS_CORTE},
        "grupos": blk.get("grupos") or {},
        "seleccion": {"conservado": "cb_ben_pit"},
    }
    _objetivo_45("t1", "beneficios_corte", 1, normalizado, programas, out, False, NOTA_BENEFICIOS_CORTE, gt)


def _tarea_t2(t2: Mapping, programas, out, gt: Optional[Mapping] = None) -> None:
    ev = t2.get("evaluacion") or {}
    test = ev.get("test") or {}
    split = (t2.get("descriptivo") or {}).get("split") or {}
    n_eval = _entero((split.get("test") or {}).get("n"))
    out["metrica"] += _metricas("t2", "base", 0, test, n_eval, "cb_c_nuevas")
    out["delta"] += _deltas_rm("t2", "base", 0, test)
    out["calibracion"] += _calibracion("t2", "base", 0, ev.get("calibracion_test") or {})
    out["particion"] += _particiones("t2", "base", 0, {p: (v.get("n"), v.get("reprobados")) for p, v in split.items()})
    out["vista"].append(_vista("t2", "base", 0, True, "cb_c_nuevas", "baseline"))
    grupos = ((ev.get("bandas") or {}).get("grupos") or {}).get("test") or {}
    # the band "reprobado" is the event of the task: its rows come from ``grupos_todos`` (every group, the kept model); the other
    # three bands come from the band model's block of the same file (``banda_<banda>``, programa and facultad)
    nuevos = _bloque_todos(gt, "t2", "base", 0, "cb_c_nuevas")
    if nuevos:
        _grupos_todos("t2", "base", 0, nuevos, programas, out, "reprobado")
        for banda in BANDAS_T2:
            _grupos_todos("t2", "base", 0, _bloque_todos(gt, "t2", f"banda_{banda}", 0, MODELO_BANDAS), programas, out, banda)
        return
    for nivel in ("programa", "facultad"):
        bloque = grupos.get(nivel) or {}
        resumen = bloque.get("resumen") or {}
        listados = {banda: 0 for banda in BANDAS}
        for fila in bloque.get("filas", []):
            n = _entero(fila.get("n"))
            for banda in BANDAS:
                b = (fila.get("bandas") or {}).get(banda)
                if not b:
                    continue
                g = _fila_grupo("t2", "base", 0, nivel, banda, fila, programas, _m(b.get("observada")), _m(b.get("predicha")),
                                _m(b.get("base"))[0], None, n, b.get("ap"))
                if g:
                    out["grupo"].append(g)
                    listados[banda] += 1
        for banda in BANDAS:
            out["grupo_resumen"].append(_resumen_grupo(
                "t2", "base", 0, nivel, banda, resumen, (resumen.get("mae_modelo") or {}).get(banda),
                (resumen.get("mae_base") or {}).get(banda), (resumen.get("spearman") or {}).get(banda), listados[banda]))


def _tarea_t3(t3: Mapping, programas, out, gt: Optional[Mapping] = None) -> None:
    desc = ((t3.get("descriptivo") or {}).get("por_k_split")) or {}
    for ks, bloque in (t3.get("por_k") or {}).items():
        k = int(ks)
        test = bloque.get("test") or {}
        clasico = CONSERVADO_CLASICO_T3.get(k) if CONSERVADO_CLASICO_T3.get(k) in test else bloque.get("mejor_clasico_valid")
        red = CONSERVADO_RED_T3.get(k)
        conservado = red if red in test else clasico
        n_split = bloque.get("n_split") or {}
        out["metrica"] += _metricas("t3", "base", k, test, _entero(n_split.get("test")), conservado)
        out["delta"] += _deltas_rm("t3", "base", k, test)
        out["calibracion"] += _calibracion("t3", "base", k, (bloque.get("calibracion_test") or {}).get("12") or {})
        partes = {p: (v.get("n"), v.get("egreso")) for p, v in (desc.get(ks) or {}).items() if p in ("train", "valid", "test")}
        out["particion"] += _particiones("t3", "base", k, partes)
        subgrupos = bloque.get("subgrupos_test") or {}
        # group data exist only for some models (the logistic of k = 0 has none): fall back to the benchmark's best classical
        con_grupos = [m for m in (conservado, clasico, bloque.get("mejor_clasico_valid"))
                      if (subgrupos.get(m) or {}).get("programa_n150")]
        modelo_grupos = con_grupos[0] if con_grupos else clasico
        nuevos = _bloque_todos(gt, "t3", "base", k, conservado)
        if nuevos:
            modelo_grupos = conservado
        nota = "Calibración y grupos a 12 semestres desde la admisión."
        if conservado == red:
            nota = f"{NOTA_T3[k]} {nota}"
        if modelo_grupos != conservado:
            nota += (f" Los grupos por programa vienen del mejor clásico ({MODELOS['t3'][modelo_grupos][0]}): el modelo "
                     "conservado no tiene datos por grupo.")
        out["vista"].append(_vista("t3", "base", k, k == 2, conservado, "km_programa", nota=nota))
        if nuevos:
            _grupos_todos("t3", "base", k, nuevos, programas, out)
            continue
        listados = 0
        for f in (subgrupos.get(modelo_grupos) or {}).get("programa_n150", []):
            obs = _num(f.get("incidencia_observada"))
            g = _fila_grupo("t3", "base", k, "programa", "", f, programas, (obs, None, None),
                            (_num(f.get("incidencia_predicha")), None, None), None, None, None, None, f.get("auc"))
            if g:
                out["grupo"].append(g)
                listados += 1
        out["grupo_resumen"].append(_resumen_grupo("t3", "base", k, "programa", "", {}, n_filas=listados))


def _sobreestimacion(cal: List[Dict], tasa_test: Optional[float]) -> Optional[str]:
    """Mean predicted risk of the kept model over the test deciles against the observed rate (only counts)."""
    n = sum(d["n"] for d in cal)
    if not n or tasa_test is None:
        return None
    pred = sum(d["n"] * (d["riesgo_medio"] or 0) for d in cal) / n
    return (f"El modelo conservado predice en promedio {_coma(100 * pred, 1)} % frente a una tasa observada de "
            f"{_coma(100 * tasa_test, 1)} % en prueba.")


def _objetivo_45(tarea, variante, k, blk: Mapping, programas, out, principal, nota_extra=None, gt: Optional[Mapping] = None) -> None:
    conservado = (blk.get("seleccion") or {}).get("conservado")
    n_split = blk.get("n") or {}
    test = blk.get("test") or {}
    n_eval = _entero((n_split.get("test") or {}).get("n"))
    out["metrica"] += _metricas(tarea, variante, k, test, n_eval, conservado)
    out["delta"] += _deltas_vs(tarea, variante, k, test)
    cal = _calibracion(tarea, variante, k, blk.get("calibracion_test") or {})
    out["calibracion"] += cal
    out["particion"] += _particiones(tarea, variante, k, {p: (v.get("n"), v.get("eventos")) for p, v in n_split.items()})
    nota = nota_extra
    if tarea == "t4":
        extra = _sobreestimacion([c for c in cal if c["modelo"] == conservado], (n_split.get("test") or {}).get("tasa"))
        nota = " ".join(x for x in (extra, "El pronóstico agregado por grupo no mejora la tasa histórica por programa y no se "
                                          "considera confiable.") if x)
    out["vista"].append(_vista(tarea, variante, k, principal, conservado, "baseline_tasa", nota=nota))
    nuevos = _bloque_todos(gt, tarea, variante, k, conservado)
    if nuevos:
        _grupos_todos(tarea, variante, k, nuevos, programas, out)
    else:
        _grupos_45(tarea, variante, k, blk.get("grupos") or {}, programas, out)


def _sin_dudosos(blk: Mapping, k: int, out) -> None:
    s = blk.get("sensibilidad_registro_e")
    if not s or not s.get("evaluado"):
        return
    conservado = (blk.get("seleccion") or {}).get("conservado")
    n = _entero(s.get("n"))
    for modelo, metricas in (s.get("modelos") or {}).items():
        if modelo not in T45_MODELOS:
            continue
        for metrica, v in metricas.items():
            if RM._es_metrica(v):
                out["metrica"].append(_fila_metrica("t5", "sin_dudosos", k, modelo, metrica, v, n, conservado))
    out["particion"] += _particiones("t5", "sin_dudosos", k, {"test": (n, s.get("eventos"))})
    out["vista"].append(_vista("t5", "sin_dudosos", k, False, conservado, "baseline_tasa", nota=(
        f"Solo filas de prueba con el horizonte anterior a {s.get('periodo_limite')}; se comparan el modelo conservado y la "
        "tasa histórica.")))


def _tarea_t45(t45: Mapping, programas, out, gt: Optional[Mapping] = None) -> None:
    for ks, bloque in (t45.get("por_k") or {}).items():
        k = int(ks)
        t = bloque.get("targets") or {}
        principal = k == min(int(x) for x in t45["por_k"])
        if "T4" in t:
            _objetivo_45("t4", "base", k, t["T4"], programas, out, principal, None, gt)
        if "T5" in t:
            _objetivo_45("t5", "actual", k, t["T5"], programas, out, principal, None, gt)
            _sin_dudosos(t["T5"], k, out)
        if "T5E" in t:
            _objetivo_45("t5", "efectiva", k, t["T5E"], programas, out, False, None, gt)


def _tarea_t6(t6: Mapping, programas, out, gt: Optional[Mapping] = None) -> None:
    modelos = t6.get("modelos") or {}
    conservado = (modelos.get("seleccion") or {}).get("conservado")
    principal = str((modelos.get("seleccion") or {}).get("tau") or t6.get("tau_principal") or 2)
    desc = t6.get("descriptivo") or {}
    por_h = desc.get("por_horizonte") or {}
    hor = (modelos.get("horizontes") or {}).get("test") or {}
    grupos = desc.get("grupos") or {}
    for tau, h in hor.items():
        if not h.get("modelos"):
            continue                                       # horizon without a test set (8 semesters)
        variante = f"h{tau}"
        n = _entero(h.get("n"))
        out["metrica"] += _metricas("t6", variante, 0, h["modelos"], n, conservado)
        out["delta"] += _deltas_vs("t6", variante, 0, h.get("pares") or {})
        if tau == principal:
            out["calibracion"] += _calibracion("t6", variante, 0, modelos.get("calibracion_test") or {}, "grupo")
        partes = {p: (v.get("n"), v.get("eventos")) for p, v in (por_h.get(tau) or {}).items() if p in ("train", "valid", "test")}
        out["particion"] += _particiones("t6", variante, 0, partes)
        out["vista"].append(_vista("t6", variante, 0, tau == principal, conservado, "baseline_programa",
                                   concluyente=bool(h.get("conclusivo")),
                                   nota=None if h.get("conclusivo") else "No concluyente: menos de 30 matriculados en prueba."))
        nuevos = _bloque_todos(gt, "t6", variante, 0, conservado)
        if nuevos:                                  # valid + test units followed up to the horizon, every group
            _grupos_todos("t6", variante, 0, nuevos, programas, out)
        for nivel in () if nuevos else ("programa", "facultad"):
            bloque = grupos.get(nivel) or {}
            listados = 0
            for f in bloque.get("filas", []):
                inc = (f.get("incidencia") or {}).get(tau)
                if not inc:
                    continue
                g = _fila_grupo("t6", variante, 0, nivel, "", f, programas, _m(inc), (None, None, None), None,
                                _entero(f.get("eventos")), _entero(f.get("n")))
                if g:
                    out["grupo"].append(g)
                    listados += 1
            r = bloque.get("resumen") or {}
            out["grupo_resumen"].append(_resumen_grupo("t6", variante, 0, nivel, "", r, n_filas=listados))
        for nivel_pg, d in (t6.get("incidencia_por_nivel") or {}).items():
            inc = (d.get("incidencia") or {}).get(tau)
            if not inc:
                continue
            ev = _entero(d.get("eventos"))
            g = _fila_grupo("t6", variante, 0, "nivel_postgrado", "", {"grupo": nivel_pg, "n": _entero(t6.get("n_unidades")) or 0},
                            programas, _m(inc), (None, None, None), None, ev, _entero(t6.get("n_unidades")))
            if g:
                out["grupo"].append(g)
    g = desc.get("global") or {}
    for tau, inc in (g.get("incidencia") or {}).items():
        variante = f"h{tau}"
        if any(v["tarea"] == "t6" and v["variante"] == variante for v in out["vista"]):
            p, lo, hi = _m(inc)
            out["particion"].append({"tarea": "t6", "variante": variante, "corte_k": 0, "particion": "todas",
                                     "n": _entero(g.get("n")), "eventos": _entero(g.get("eventos")), "tasa": p,
                                     "tasa_inf": lo, "tasa_sup": hi})


# ---------------------------------------------------------------------------------------- headline verdicts
def _veredicto_calculado(tarea: str, deltas: List[Dict], vistas: List[Dict]) -> str:
    """Appends, from the paired differences of the principal view, the nets-versus-kept-model reading."""
    principal = next((v for v in vistas if v["tarea"] == tarea and v["principal"]), None)
    if principal is None:
        return ""
    metrica = FICHAS[tarea]["metrica_titular"]
    en_vista = [d for d in deltas if d["tarea"] == tarea and d["variante"] == principal["variante"]
                and d["corte_k"] == principal["corte_k"] and d["metrica"] == metrica and d["delta"] is not None
                and d["ic_inf"] is not None and d["ic_sup"] is not None]
    if tarea == "t3" and principal["conservado_modelo"] == "nn_gru":
        pares = [("nn_gru", CLASICO_COMPARACION_T3)]                  # the kept network against the best classical
    else:
        pares = {"t2": [("nn_gnn", "nn_mlp")]}.get(tarea) or [
            (a, principal["conservado_modelo"]) for a in ("gru_seq", "nn_gru", "gru_adm", "gru_agg")]
    d = next((x for a, b in pares for x in en_vista if x["modelo_a"] == a and x["modelo_b"] == b), None)
    if d is None:
        return ""
    etiqueta = RM.ETIQUETA_METRICA.get(metrica, metrica)
    nombre = MODELOS[tarea]
    # the verdict is task-level and shown on every view, so it names the view its numbers come from
    return (f" Diferencia pareada en prueba de la vista principal (k = {principal['corte_k']}): "
            f"{nombre[d['modelo_a']][0]} frente a {nombre[d['modelo_b']][0]}, "
            f"Δ{etiqueta} {_coma(d['delta'])} [{_coma(d['ic_inf'])}; {_coma(d['ic_sup'])}].")


def construir(t1: Mapping, t2: Mapping, t3: Mapping, t45: Mapping, t6: Mapping,
              programas: Optional[Mapping[str, Tuple[Optional[str], Optional[str]]]] = None,
              t1_beneficios: Optional[Mapping] = None, t1_beneficios_cargas: Optional[Mapping] = None,
              grupos_todos: Optional[Mapping] = None) -> Dict[str, List[Dict]]:
    programas = programas or {}
    out: Dict[str, List[Dict]] = {k: [] for k in ("tarea", "nota", "vista", "particion", "metrica", "delta", "calibracion",
                                                  "grupo", "grupo_resumen")}
    _tarea_t1(t1, programas, out, grupos_todos)
    if t1_beneficios:
        _tarea_t1_beneficios(t1_beneficios, programas, out, grupos_todos)
    if t1_beneficios_cargas:
        _tarea_t1_beneficios_corte(t1_beneficios_cargas, programas, out, grupos_todos)
    _tarea_t2(t2, programas, out, grupos_todos)
    _tarea_t3(t3, programas, out, grupos_todos)
    _tarea_t45(t45, programas, out, grupos_todos)
    _tarea_t6(t6, programas, out, grupos_todos)
    for tarea, ficha in FICHAS.items():
        out["tarea"].append({"tarea": tarea, **{k: v for k, v in ficha.items()},
                             "veredicto_redes": ficha["veredicto_redes"] + _veredicto_calculado(tarea, out["delta"], out["vista"])})
        for orden, (tipo, texto) in enumerate(NOTAS[tarea], start=1):
            out["nota"].append({"tarea": tarea, "tipo": tipo, "orden": orden, "texto": texto})
    # a view needs at least a kept model to headline; drop views whose results are missing
    out["vista"] = [v for v in out["vista"] if any(m["tarea"] == v["tarea"] and m["variante"] == v["variante"]
                                                   and m["corte_k"] == v["corte_k"] for m in out["metrica"])]
    return out


# --------------------------------------------------------------------------------------------- database
TABLAS = {
    "resumen_tarea": ("tarea", "orden", "nombre", "pregunta", "poblacion", "evento", "estado", "estado_etiqueta",
                      "veredicto_redes", "metrica_titular", "metrica_secundaria"),
    "resumen_tarea_nota": ("tarea", "tipo", "orden", "texto"),
    "resumen_tarea_vista": ("tarea", "variante", "corte_k", "etiqueta", "principal", "conservado_modelo", "referencia_modelo",
                            "metrica_titular", "metrica_secundaria", "concluyente", "pronostico_agregado", "nota"),
    "resumen_tarea_particion": ("tarea", "variante", "corte_k", "particion", "n", "eventos", "tasa", "tasa_inf", "tasa_sup"),
    "resumen_tarea_metrica": ("tarea", "variante", "corte_k", "modelo", "modelo_nombre", "familia", "escalon",
                              "escalon_nombre", "metrica", "valor", "ic_inf", "ic_sup", "n_evaluacion", "conservado"),
    "resumen_tarea_delta": ("tarea", "variante", "corte_k", "modelo_a", "modelo_b", "metrica", "delta", "ic_inf", "ic_sup",
                            "veredicto"),
    "resumen_tarea_calibracion": ("tarea", "variante", "corte_k", "modelo", "decil", "n", "riesgo_medio", "tasa_observada"),
    "resumen_tarea_grupo": ("tarea", "variante", "corte_k", "nivel", "categoria", "grupo", "nombre", "facultad", "n", "eventos",
                            "observada", "obs_inf", "obs_sup", "esperada", "esp_inf", "esp_sup", "referencia", "ap", "roc_auc",
                            "ap_lo", "ap_hi", "auc_lo", "auc_hi", "tasa_lo", "tasa_hi", "esperado_lo", "esperado_hi",
                            "pocos_casos"),
    "resumen_tarea_grupo_resumen": ("tarea", "variante", "corte_k", "nivel", "categoria", "grupos_total",
                                    "grupos_reportables", "mae_modelo", "mae_base", "spearman"),
}
_ORIGEN = {"resumen_tarea": "tarea", "resumen_tarea_nota": "nota", "resumen_tarea_vista": "vista",
           "resumen_tarea_particion": "particion", "resumen_tarea_metrica": "metrica", "resumen_tarea_delta": "delta",
           "resumen_tarea_calibracion": "calibracion", "resumen_tarea_grupo": "grupo",
           "resumen_tarea_grupo_resumen": "grupo_resumen"}
# children first when deleting, parent first when inserting (the child tables reference ``resumen_tarea``)
ORDEN_BORRADO = tuple(reversed(list(TABLAS)))


def _limpio(v):
    return None if isinstance(v, float) and math.isnan(v) else v


def escribir(conn, resumen: Dict[str, List[Dict]], mart_schema: str = "neural_mart") -> Dict[str, int]:
    """Replace the content of the per-task tables in ONE transaction (a failure leaves the previous summary)."""
    from ..migrate import ALLOWED_SCHEMAS

    if mart_schema not in ALLOWED_SCHEMAS:
        raise ValueError(f"schema {mart_schema!r} is not one of {ALLOWED_SCHEMAS}")
    cuentas: Dict[str, int] = {}
    with conn.transaction():
        with conn.cursor() as cur:
            for tabla in ORDEN_BORRADO:
                cur.execute(f"DELETE FROM {mart_schema}.{tabla}")
            for tabla, columnas in TABLAS.items():
                filas = [tuple(_limpio(f.get(c)) for c in columnas) for f in resumen[_ORIGEN[tabla]]]
                if filas:
                    marcas = ", ".join(["%s"] * len(columnas))
                    cur.executemany(
                        f"INSERT INTO {mart_schema}.{tabla} ({', '.join(columnas)}) VALUES ({marcas})", filas)
                cuentas[tabla] = len(filas)
    return cuentas
