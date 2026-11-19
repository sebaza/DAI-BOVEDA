"""Projection document of the tab "Lo que viene": what the kept models and the regulation say about the CURRENT students.

``python -m evaluation.vista_proyeccion`` writes ``artefactos/vista_proyeccion.json`` (gitignored, AGGREGATES ONLY: no row, key or
name of a person). The exporter ``tools/exportar_resumen_modelos.py`` loads it into ``neural_mart.vista_proyeccion`` (migration 032).

Only data up to the close of ``CORTE_ACTUAL`` (202610) is read; 202620 is in progress and is never read. No model is trained: the
kept models are rebuilt with the validated configuration and must reproduce their saved test predictions
(``modelos_conservados.cargar_o_ajustar``); a model that does not reproduce aborts the run and nothing is written.

Four blocks, each for "Toda la UCN", for every faculty and for every program (``vista_historica.por_filtro``; a program is keyed by its
program code and listed in ``programas`` with its name and faculty; ``filtros`` keeps "Toda la UCN" and the faculties):

* ``continuidad``  V-1, T1: expected number that continue, summed from the probability of continuing (``1 - p(no continua)``).
* ``eliminacion``  V-2, T5 (``orientativo``: the model did not see the 2025 regulation and the ``E`` states are under-recorded since
  202420, P75): expected eliminations in the two semesters after the cut (``k + 1``, ``k + 2``). Part of that horizon has already
  happened (202610): ``observados_hasta_hoy`` is reported APART and never added to ``esperados``.
* ``egreso``       V-3, T3: expected graduates, cumulative from each cohort's cut, at the end of the nominal duration of the program
  and two semesters later (``regla`` in the block), each with its range and the calendar period it corresponds to.
* ``umbral``       V-4, descriptive: current students at 0, 1 or 2 "reprobaciones" of the Art. 46 threshold in force since 202520.

Populations (``POBLACIONES``): the snapshot rows of the cohort and ``k`` of each model whose cut is closed (<= 202610) and whose
person is a current student at the close of 202610; never selected by the snapshot label (it may carry 202620 data). Each
entry of ``por_cohorte`` carries its ``corte`` and ``horizonte`` so the reader knows exactly what is projected. Inside one block
nobody is counted twice (checked). The same person may appear in two blocks: they answer different questions.

Ranges: ``rango`` is the normal interval of a sum of independent Bernoulli variables (the sum of the model probabilities
+- 1.96 sd), clipped to ``[0, n]``. It carries the model's calibration error, not only the sampling one.

Model behind each block (``evaluation.vista_modelo_visible``): every entry of ``por_cohorte`` carries ``modelo`` (task, kept model, k,
cut, ``tipo = "proyeccion"``); a block carries ``modelo = None`` and ``modelos`` (its distinct models); ``umbral`` only counts what was
observed and carries ``modelo = None``.

Publication rule: every block, ``por_cohorte`` entry and Art. 46 category is published for any group size (the user's decision
of 18-11-2026 lifts the under-10 rule for aggregates in this module), so the expected value of a group of one is that person's
probability, always with its range. A block is left out only when its group is empty. Observed eliminations appear only as a
block total. No row, key, id or name of a person is ever written.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from evaluation import facultades as FA
from evaluation import modelos_conservados as MC
from evaluation import vista_modelo_visible as MVIS
from evaluation.grupos_facultad import poner_facultad, sin_nan
from evaluation.vista_historica import UCN, codigos_presentes, construir_filtros, lista_programas, por_filtro
from pipelines.marts.rules import base_ordinal
from pipelines.snapshots import features as F
from pipelines.snapshots import features_t3 as F3
from pipelines.snapshots import features_variables as FV
from pipelines.snapshots import rules as R
from pipelines.snapshots import rules_variables as RV

RAIZ = Path(__file__).resolve().parents[1]
CORTE_ACTUAL = "202610"                 # last closed period; 202620 is in progress and is never read
COHORTE_PROYECTADA_DESDE = 2024
Z95 = 1.96
POBLACIONES: Tuple[Dict[str, Any], ...] = (
    {"bloque": "continuidad", "tarea": "t1", "k": 1, "modelo": "cb_ben_pit", "cohorte": 2026},
    {"bloque": "continuidad", "tarea": "t1", "k": 2, "modelo": "lr_acad", "cohorte": 2025},
    {"bloque": "eliminacion", "tarea": "t5", "k": 2, "modelo": "gru_adm", "cohorte": 2025},
    {"bloque": "eliminacion", "tarea": "t5", "k": 4, "modelo": "gru_agg", "cohorte": 2024},
    {"bloque": "egreso", "tarea": "t3", "k": 0, "modelo": "dt_lr_adm", "cohorte": 2026},
    {"bloque": "egreso", "tarea": "t3", "k": 2, "modelo": "nn_gru", "cohorte": 2025},
    {"bloque": "egreso", "tarea": "t3", "k": 4, "modelo": "nn_gru", "cohorte": 2024})
BLOQUES = ("continuidad", "eliminacion", "egreso", "umbral")
GRUPO = ["cohorte", "k", "modelo", "corte", "horizonte"]
CATEGORIAS_UMBRAL = ("en_umbral", "a_1", "a_2", "lejos")


# ------------------------------------------------------------------------------------------------------ range
def rango(p: np.ndarray) -> Tuple[float, float, float]:
    """``(sum p, sum p - 1.96 sd, sum p + 1.96 sd)`` with ``sd = sqrt(sum p (1 - p))``, clipped to ``[0, n]``."""
    p = np.asarray(p, dtype="float64")
    n = int(p.size)
    suma = float(p.sum())
    sd = float(np.sqrt((p * (1.0 - p)).sum()))
    return suma, float(np.clip(suma - Z95 * sd, 0.0, n)), float(np.clip(suma + Z95 * sd, 0.0, n))


def _estadistico(p: np.ndarray) -> Dict[str, Any]:
    s, lo, hi = rango(p)
    return {"esperados": round(s, 1), "lo": round(lo, 1), "hi": round(hi, 1)}


# ------------------------------------------------------------------------------------------------------ blocks
def _sin_repetidos(d: pd.DataFrame) -> None:
    if not d["episodio_id"].is_unique:
        raise ValueError("an episode would be counted twice in the same block")


def _grupos(d: pd.DataFrame) -> List[Tuple[Dict[str, Any], pd.DataFrame]]:
    """Sub-frames per (cohort, k, model, cut, horizon), newest cohort first. ``horizonte_desde`` rides along when present."""
    claves = GRUPO + (["horizonte_desde"] if "horizonte_desde" in d else [])
    out = []
    for valores, sub in d.groupby(claves, sort=False, dropna=False):
        out.append((dict(zip(claves, valores)), sub))
    return sorted(out, key=lambda g: (-int(g[0]["cohorte"]), int(g[0]["k"]), str(g[0]["corte"])))


def _modelo_de_cohorte(tarea: str, clave: Mapping[str, Any]) -> Dict[str, Any]:
    """The model object of one cohort entry: what scored these students and at which cut."""
    return MVIS.modelo_visible(tarea, int(clave["k"]), str(clave["modelo"]),
                               f"Estudiantes vigentes al cierre de {CORTE_ACTUAL}, cohorte {clave['cohorte']}", "proyeccion")


def _entradas(d: pd.DataFrame, resumir, tarea: str) -> List[Dict[str, Any]]:
    """``por_cohorte`` rows: one per (cohort, k, model, cut, horizon), whatever its size, each with the ``modelo`` object of its task."""
    out = []
    for clave, sub in _grupos(d):
        c = {k: _python(v) for k, v in clave.items()}
        c["modelo"] = _modelo_de_cohorte(tarea, c)
        out.append({**c, "n": int(len(sub)), **resumir(sub)})
    return out


def _modelos(entradas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """A block with cohorts has no single model: ``modelo = None`` and the distinct models of its cohorts in ``modelos``."""
    return {"modelo": None, "modelos": MVIS.distintos(e["modelo"] for e in entradas)}


def _python(v: Any) -> Any:
    return v.item() if isinstance(v, np.generic) else v


def _bloque_simple(d: pd.DataFrame, resumir, tarea: str) -> Optional[Dict[str, Any]]:
    resumir = resumir or (lambda sub: _estadistico(sub["p"].to_numpy()))
    _sin_repetidos(d)
    n = int(len(d))
    if n == 0:
        return None
    entradas = _entradas(d, resumir, tarea)
    return {"n": n, **_estadistico(d["p"].to_numpy()), "por_cohorte": entradas, **_modelos(entradas)}


def _resumen_continuidad(sub: pd.DataFrame) -> Dict[str, Any]:
    out = _estadistico(sub["p"].to_numpy())
    if "sin_hist" in sub and sub["sin_hist"].notna().any():          # only the benefit model has this input
        out["sin_historial_beneficios"] = int(sub["sin_hist"].fillna(0).sum())
    return out


def bloque_continuidad(d: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """V-1. ``d.p`` is the probability of CONTINUING (``1 - p(no continua)`` of T1); ``esperados`` is how many are expected to.
    ``d.sin_hist`` (benefit model only) marks the rows without load history at their cut: their count goes in each entry."""
    return _bloque_simple(d, _resumen_continuidad, "t1")


def bloque_eliminacion(d: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """V-2. ``d.p`` is the probability of elimination in the horizon; ``d.obs`` marks who was already eliminated in the part of the
    horizon that has happened (reported apart, once, for the whole block)."""
    b = _bloque_simple(d, None, "t5")
    if b is None:
        return None
    observados = int(d["obs"].astype(bool).sum()) if "obs" in d else 0
    b.update({"observados_hasta_hoy": observados, "periodo_observado": CORTE_ACTUAL, "orientativo": True})
    return b


HITOS_EGRESO = ("nominal", "nominal_mas_2")
REGLA_EGRESO = ("Egresados esperados acumulados desde el corte de cada cohorte hasta el final de la duración nominal del programa y "
                "hasta dos semestres después (incidencia acumulada del modelo T3 conservado de esa cohorte). Cada cifra indica el "
                "período calendario al que corresponde; la suma de todas las cohortes mezcla períodos distintos.")


def _por_hito(d: pd.DataFrame) -> Dict[str, Optional[Dict[str, Any]]]:
    """Per milestone: the expected over the rows whose milestone is still ahead (``p`` not NaN) and its calendar period, for any
    number of rows ahead (a single row gives its own probability with its range). ``None`` only when no row is ahead."""
    out: Dict[str, Optional[Dict[str, Any]]] = {}
    for h in HITOS_EGRESO:
        v = d.loc[d[f"p_{h}"].notna()]
        out[h] = ({**_estadistico(v[f"p_{h}"].to_numpy()), "desde": str(v[f"per_{h}"].min()), "hasta": str(v[f"per_{h}"].max())}
                  if len(v) else None)
    return out


def bloque_egreso(d: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """V-3. ``d.p_nominal`` / ``d.p_nominal_mas_2`` are the cumulative probabilities of graduating from the cut up to the end of the
    nominal duration of the program and two semesters later; ``d.per_*`` the calendar period (``AAAA10`` / ``AAAA20``) of each.
    A milestone that already happened (period up to the close, ``p`` NaN) is left out of its figure and counted apart
    (``ya_pasado_*``); ``d.trunc`` marks rows whose milestone went past the horizon of the model (``horizonte_truncado``)."""
    _sin_repetidos(d)
    n = int(len(d))
    if n == 0:
        return None
    aparte = {f"ya_pasado_{h}": int(d[f"p_{h}"].isna().sum()) for h in HITOS_EGRESO}
    truncados = int(d["trunc"].astype(bool).sum()) if "trunc" in d else 0
    entradas = _entradas(d, _por_hito, "t3")
    return {"n": n, "regla": REGLA_EGRESO, **_por_hito(d), **aparte, "horizonte_truncado": truncados,
            "por_cohorte": entradas, **_modelos(entradas)}


def hito_egreso(cif: np.ndarray, periodos_admision: Sequence[str], duracion: np.ndarray, k: int,
                extra: int) -> Tuple[np.ndarray, List[Optional[str]], np.ndarray]:
    """Cumulative incidence and calendar period at the end of slot ``duracion + extra`` (``u = slot - k`` semesters after the cut).

    A milestone that already happened (``u < 1`` or its period is not after ``CORTE_ACTUAL``) gets ``p = NaN`` and no period: it is
    not a projection. ``u`` above the horizon of the model is clipped to it and flagged in the third value."""
    U = cif.shape[1]
    slot = np.asarray(duracion, dtype="int64") + extra
    u = slot - int(k)
    periodos = [R.ordinal_a_periodo(base_ordinal(a) + int(x) - 1) for a, x in zip(periodos_admision, slot)]
    pasado = (u < 1) | np.array([per <= CORTE_ACTUAL for per in periodos], dtype=bool)
    p = np.clip(cif[np.arange(len(cif)), np.clip(u, 1, U) - 1], 0.0, 1.0)
    return np.where(pasado, np.nan, p), [None if x else per for per, x in zip(periodos, pasado)], (u > U) & ~pasado


# ------------------------------------------------------------------------------------------------------ threshold (V-4)
def umbral_actual(intentos: pd.DataFrame, actuales: pd.DataFrame) -> pd.DataFrame:
    """Art. 46 position of every current student, with the counting of ``features_variables`` (``reg_rep2_total``: distinct courses
    failed in the 2nd opportunity over the career; ``reg_rep3_cursos``: distinct courses failed in the 3rd or later) and the
    failures still needed to reach the threshold (``distancia_umbral``). Only attempts up to ``CORTE_ACTUAL`` count.
    The periods without recorded failures (P58) never produce one, so the counts are lower bounds."""
    return distancia_umbral(contar_umbral(intentos, actuales))


COLUMNAS_CUENTAS = ["reg_rep2_total", "reg_rep3_cursos", "pend_1ra", "pend_2da"]


def contar_umbral(intentos: pd.DataFrame, actuales: pd.DataFrame) -> pd.DataFrame:
    """Per current student (the heavy step, cacheable): ``reg_rep2_total`` and ``reg_rep3_cursos`` (Art. 46 counts of
    ``features_variables``), and the pending courses that decide how far the threshold is: ``pend_1ra`` (the last decided result
    of the course is a failed 1st opportunity: its next attempt is a 2nd) and ``pend_2da`` (a failed 2nd opportunity: the next one
    is a 3rd, the ``reg_cursos_riesgo_3ra`` logic). A course already failed in the 3rd opportunity is counted in ``reg_rep3_cursos``
    and is not a candidate any more. Only attempts up to ``CORTE_ACTUAL`` are read."""
    a = intentos.loc[intentos["periodo"].astype(str).le(CORTE_ACTUAL) & intentos["episodio_id"].isin(actuales["episodio_id"])].copy()
    a["periodo"] = a["periodo"].astype(str)
    FV.marcar_fallas(a)
    a["codigo"] = a["codigo_asignatura"]
    cuentas = FV.conteos_reglamento(a, "episodio_id")
    decidido = a.loc[a["aprob"] | a["fail"]].sort_values(["episodio_id", "codigo", "periodo", "opo"])
    ultimo = decidido.drop_duplicates(["episodio_id", "codigo"], keep="last")
    pend = ultimo.loc[ultimo["fail"]]
    cuentas["pend_1ra"] = pend.loc[pend["opo"] <= 1].groupby("episodio_id").size()
    cuentas["pend_2da"] = pend.loc[pend["opo"] == 2].groupby("episodio_id").size()
    out = actuales.drop(columns=[c for c in COLUMNAS_CUENTAS if c in actuales]).merge(
        cuentas[COLUMNAS_CUENTAS], left_on="episodio_id", right_index=True, how="left")
    for c in COLUMNAS_CUENTAS:
        out[c] = out[c].fillna(0).astype("int64")
    columnas = ["episodio_id", *[c for c in ("facultad", "cod_programa") if c in out], *COLUMNAS_CUENTAS]
    return out[columnas].reset_index(drop=True)


def distancia_umbral(c: pd.DataFrame) -> pd.DataFrame:
    """Failures still needed to reach the Art. 46 threshold, ``distancia = max(0, min(d2, d3))``:

    * ``d2``: the smallest sum of per-course needs that adds the missing failures in the 2nd opportunity
      (``UMBRAL_2DA_NUEVO - reg_rep2_total``): a pending course failed once needs 1, any other course needs 2.
    * ``d3``: the same for the missing courses failed in the 3rd opportunity (``UMBRAL_3RA_NUEVO - reg_rep3_cursos``): a pending
      course failed twice needs 1, one failed once needs 2, any other course needs 3.
    Enough other courses are assumed to exist."""
    f2 = np.maximum(0, RV.UMBRAL_2DA_NUEVO - c["reg_rep2_total"].to_numpy())
    a = np.minimum(f2, c["pend_1ra"].to_numpy())
    d2 = a + 2 * (f2 - a)
    f3 = np.maximum(0, RV.UMBRAL_3RA_NUEVO - c["reg_rep3_cursos"].to_numpy())
    x = np.minimum(f3, c["pend_2da"].to_numpy())
    y = np.minimum(f3 - x, c["pend_1ra"].to_numpy())
    d3 = x + 2 * y + 3 * (f3 - x - y)
    out = c.copy()
    out["distancia"] = np.maximum(0, np.minimum(d2, d3)).astype("int64")
    return out.reset_index(drop=True)


def bloque_umbral(u: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Exclusive categories by ``distancia`` (failures still needed): 0 en el umbral, 1, 2 and 3 or more (``lejos``). The four
    categories are always present with their exact count (0 when empty). ``None`` only when there is nobody."""
    n = int(len(u))
    if n == 0:
        return None
    d = u["distancia"].to_numpy()
    return {"n": n, "en_umbral": int((d <= 0).sum()), "a_1": int((d == 1).sum()), "a_2": int((d == 2).sum()), "lejos": int((d >= 3).sum()),
            "nota_p58": True, "modelo": None}


# ------------------------------------------------------------------------------------------------------ current students
def seleccionar_actuales(pop: pd.DataFrame, estados: pd.DataFrame, intentos: pd.DataFrame, titulados: Any,
                         corte: str = CORTE_ACTUAL) -> pd.DataFrame:
    """Undergraduate units with enrolment (state of enrolment, re-entry or cycle change) or attempts in the period ``corte`` and no
    exit, graduation, degree or elimination at its close (``corte`` is ``CORTE_ACTUAL`` for the V-4 set, or the cut of a population).

    The last state up to the close (period, then canonical order) decides: any ``salida`` (an elimination or a voluntary exit) or
    ``egreso_titulacion`` ends the student, a later re-entry brings them back. States and attempts after ``corte`` are
    ignored, so the later periods neither enrol nor end anybody. ``titulados``: ids of the units with a degree, or a mapping
    ``id -> period of the degree`` (only those up to ``corte`` count)."""
    e = estados.loc[~estados["es_correccion_sistema"].astype(bool) & estados["periodo"].astype(str).le(corte)].copy()
    e["clase"] = F.clase_estado(e["cod_estado"])
    matriculados = set(e.loc[(e["periodo"].astype(str) == corte) & e["clase"].isin(F.MATRICULA), "episodio_id"].astype("int64"))
    con_intentos = set(intentos.loc[intentos["periodo"].astype(str) == corte, "episodio_id"].astype("int64"))
    ultimo = e.sort_values(["episodio_id", "periodo", "orden_canonico"]).drop_duplicates("episodio_id", keep="last")
    con_titulo = ({int(i) for i, per in titulados.items() if str(per) <= corte} if isinstance(titulados, Mapping)
                  else {int(x) for x in titulados})
    terminados = set(ultimo.loc[ultimo["clase"].isin(["salida", "egreso_titulacion"]), "episodio_id"].astype("int64")) | con_titulo
    vigentes = (matriculados | con_intentos) - terminados
    a = pop.loc[pop["episodio_id"].astype("int64").isin(vigentes), ["episodio_id", "persona_key", "cod_programa", "periodo_admision"]].copy()
    a["cohorte"] = a["periodo_admision"].str.slice(0, 4).astype(int)
    return a.drop(columns="periodo_admision").sort_values("episodio_id").reset_index(drop=True)


# ------------------------------------------------------------------------------------------------------ document
def n_sin_proyeccion(actuales: pd.DataFrame, poblaciones: Mapping[str, pd.DataFrame]) -> Optional[int]:
    """Current students whose person is in no model population (in-memory person key; nothing of it is published)."""
    en_alguna: Set[Any] = set()
    for d in poblaciones.values():
        en_alguna |= set(d["persona_key"])
    return int((~actuales["persona_key"].isin(en_alguna)).sum())


def construir_documento(actuales: pd.DataFrame, intentos: Optional[pd.DataFrame], poblaciones: Mapping[str, pd.DataFrame],
                        cuentas: Optional[pd.DataFrame] = None, programas: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """The whole document. ``actuales`` (with ``facultad``, ``persona_key``) and ``intentos`` feed V-4; ``poblaciones`` maps
    ``continuidad`` / ``eliminacion`` / ``egreso`` to the scored rows (with ``facultad``, ``persona_key`` and the block's columns).
    ``programas`` (index ``cod_programa``, ``nombre_programa``, ``facultad_nombre``) turns on the program filters; every frame then
    needs ``cod_programa``."""
    nombres = list(pd.concat([actuales["facultad"], *[d["facultad"] for d in poblaciones.values()]]).dropna().unique())
    u = distancia_umbral(cuentas) if cuentas is not None else umbral_actual(intentos, actuales)
    lista = lista_programas(programas, codigos_presentes(actuales, u, *poblaciones.values()), construir_filtros(nombres))
    cods = [p["codigo"] for p in lista]
    documento = {
        "version": 1, "corte": CORTE_ACTUAL, "filtros": construir_filtros(nombres), "programas": lista,
        "poblaciones": [dict(p) for p in POBLACIONES],
        "sin_proyeccion": {"n": n_sin_proyeccion(actuales, poblaciones)},
        "continuidad": por_filtro(poblaciones["continuidad"], nombres, bloque_continuidad, cods),
        "eliminacion": por_filtro(poblaciones["eliminacion"], nombres, bloque_eliminacion, cods),
        "egreso": por_filtro(poblaciones["egreso"], nombres, bloque_egreso, cods),
        "umbral": por_filtro(u, nombres, bloque_umbral, cods)}
    documento["modelos"] = {**{b: (documento[b].get(UCN) or {}).get("modelos", []) for b in ("continuidad", "eliminacion", "egreso")},
                            "umbral": None}
    return documento


# ------------------------------------------------------------------------------------------------------ loading (database)
Q_EPISODIOS = """
SELECT e.episodio_id, e.persona_key, e.cod_programa, e.periodo_admision, e.cod_admision, e.catalogo_inicial, p.id_nivel
FROM neural_core.episodio_programa e
LEFT JOIN neural_core.programa p ON p.cod_programa = e.cod_programa
WHERE e.periodo_admision <= %s
"""
Q_ESTADOS = """
SELECT persona_key, episodio_id, periodo, orden_canonico, cod_estado, cod_programa, catalogo, es_correccion_sistema
FROM neural_core.evento_estado WHERE periodo <= %s
"""
Q_INTENTOS = """
SELECT episodio_id, periodo, codigo_asignatura, oportunidad, es_intento_evaluado, aprobado_curricular
FROM neural_core.intento_asignatura WHERE episodio_id IS NOT NULL AND periodo <= %s
"""
Q_TITULACION = "SELECT persona_key, episodio_id, fecha_titulacion FROM neural_core.titulacion"
Q_ELIMINADOS = """
SELECT episodio_id, periodo FROM neural_core.evento_estado
WHERE cod_estado = 'E' AND NOT es_correccion_sistema AND periodo > %s AND periodo <= %s AND episodio_id = ANY(%s)
"""


def _leer(conn, sql: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])


CORTES_POBLACION = ("202410", "202420", "202510", "202520", CORTE_ACTUAL)      # cut periods a population can have


def _cargar_unidades(conn) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Set[Any]]]:
    """``(actuales, intentos, personas_por_corte)``: the current students at ``CORTE_ACTUAL`` and their attempts, both on the units of T3 (a linked specialty is merged
    with its Plan Comun episode, as in the snapshots) and read only up to ``CORTE_ACTUAL``. ``actuales``: ``episodio_id``,
    ``persona_key``, ``cod_programa``, ``cohorte`` (the faculty is attached by ``construir``). ``personas_por_corte``: for every
    cut period of ``CORTES_POBLACION``, the persons current at the close of that period (same rule, states up to it only)."""
    from pipelines.marts.rules import periodo_de_fecha

    ep = _leer(conn, Q_EPISODIOS, (CORTE_ACTUAL,))
    ep["id_nivel"] = pd.to_numeric(ep["id_nivel"]).astype("Int64")
    es = _leer(conn, Q_ESTADOS, (CORTE_ACTUAL,))
    es["episodio_id"] = es["episodio_id"].astype("Int64")
    it = _leer(conn, Q_INTENTOS, (CORTE_ACTUAL,))
    it["oportunidad"] = pd.to_numeric(it["oportunidad"]).astype("float64")
    tit = _leer(conn, Q_TITULACION)
    tit["periodo"] = tit["fecha_titulacion"].map(periodo_de_fecha)
    tit = tit.loc[tit["periodo"].notna() & (tit["periodo"] <= CORTE_ACTUAL), ["persona_key", "episodio_id", "periodo"]]
    u = F3.unidades_t3(ep, es, tit, it, cohorte_min=0)
    eg = u.egreso.dropna(subset=["episodio_id"])
    titulados = eg.groupby(eg["episodio_id"].astype("int64"))["periodo"].min().to_dict()
    actuales = seleccionar_actuales(u.pop, u.estados, u.intentos, titulados)
    por_corte = {c: set(seleccionar_actuales(u.pop, u.estados, u.intentos, titulados, c)["persona_key"]) for c in CORTES_POBLACION}
    intentos = u.intentos.loc[u.intentos["episodio_id"].isin(actuales["episodio_id"])]
    return actuales, intentos.reset_index(drop=True), por_corte


def _corte(periodo_admision: str, k: int) -> Optional[str]:
    """Period of the cut: the end of the ``k``-th semester since admission (``k = 0``: the admission semester)."""
    return periodo_admision if k < 1 else R.corte_periodo(periodo_admision, k)


def _filas_de_poblacion(conn, pob: Mapping[str, Any], personas: Optional[Mapping[str, Set[Any]]] = None) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Rows of one population and the semester rows the networks need. Selected by cohort, ``k`` and cut (``<= CORTE_ACTUAL``) and,
    when ``personas`` (``cut -> persons current at the close of that cut``) is given, by being a current student at the close of
    the row's OWN cut: what the model predicts happens after the cut, so who leaves later is exactly what it must still count.
    NEVER by the label of the snapshot (censored / event): labels resolved with later data must not decide who is projected."""
    k, cohorte = int(pob["k"]), int(pob["cohorte"])
    sem = None
    if pob["tarea"] == "t1":
        snap = MC.snapshot_t1(conn)
        cortes = snap["periodo_corte"]
        m = (snap["k"] == k) & (snap["cohorte_anio"] == cohorte) & (cortes <= CORTE_ACTUAL)
    else:
        snap, sem = MC.snapshot_t3(conn) if pob["tarea"] == "t3" else MC.snapshot_t5(conn)
        cortes = pd.Series([_corte(a, k) for a in snap["periodo_admision"]], index=snap.index)
        m = (snap["k"] == k) & (snap["cohorte_anio"] == cohorte) & cortes.notna() & (cortes <= CORTE_ACTUAL)
    if personas is not None:
        vigente = pd.Series(False, index=snap.index)
        for c in cortes[m].dropna().unique():
            vigente |= (cortes == c) & snap["persona_key"].isin(personas.get(c, set()))
        m &= vigente
    return snap.loc[m].reset_index(drop=True), sem


def _eliminados_observados(conn, filas: pd.DataFrame, cortes: pd.Series) -> np.ndarray:
    """True for the units with an ``E`` state in the part of the T5 horizon that has happened (after the cut, up to the close)."""
    ids = set(filas["episodio_id"].astype("int64"))
    if "episodio_especialidad_id" in filas:
        ids |= set(filas["episodio_especialidad_id"].dropna().astype("int64"))
    e = _leer(conn, Q_ELIMINADOS, (str(cortes.min()), CORTE_ACTUAL, sorted(ids)))
    por_id: Dict[int, List[str]] = {}
    for i, per in zip(e["episodio_id"], e["periodo"]):
        por_id.setdefault(int(i), []).append(per)
    obs = []
    for i, esp, corte in zip(filas["episodio_id"], filas.get("episodio_especialidad_id", pd.Series([None] * len(filas))), cortes):
        periodos = por_id.get(int(i), []) + (por_id.get(int(esp), []) if pd.notna(esp) else [])
        obs.append(any(p > corte for p in periodos))
    return np.array(obs, dtype=bool)


VERSION_CACHE = 3


def _hash_frame(d: Optional[pd.DataFrame]) -> str:
    """Content hash of a frame (column names and every value, in order)."""
    import hashlib

    if d is None:
        return "sin_datos"
    h = hashlib.sha256()
    h.update("|".join(map(str, d.columns)).encode())
    h.update(pd.util.hash_pandas_object(d, index=False).to_numpy().tobytes())
    return h.hexdigest()


def _hash_archivo(ruta: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest() if Path(ruta).exists() else "sin_archivo"


def _prediccion_en_cache(modelo, pob: Mapping[str, Any], entrada: pd.DataFrame, sem: Optional[pd.DataFrame], artefactos: Path) -> np.ndarray:
    """Output of the (already verified) model on the exact rows to score, cached under ``artefactos/proyeccion_cache`` (per-episode
    outputs never leave ``artefactos``, which is gitignored). The key is the content hash of the scored feature frame (benefit columns
    included), of the semester rows the network consumes, of the model file and of the saved-prediction file it was verified against,
    plus ``VERSION_CACHE``: any change of an input is a miss. The caller always runs the reproduction check before this."""
    import hashlib

    k = int(pob["k"])
    if sem is not None:
        sem = sem.loc[sem["episodio_id"].isin(entrada["episodio_id"])].sort_values(["episodio_id", "j"])
    clave = hashlib.sha256("|".join([
        str(VERSION_CACHE), CORTE_ACTUAL, str(sorted(pob.items())), _hash_frame(entrada), _hash_frame(sem),
        _hash_archivo(MC.ruta_modelo(artefactos, pob["tarea"], k, pob["modelo"])),
        _hash_archivo(MC.archivo_predicciones(pob["tarea"], k, pob["modelo"], artefactos))]).encode()).hexdigest()[:24]
    carpeta = Path(artefactos) / "proyeccion_cache"
    ruta = carpeta / f"{pob['tarea']}_k{k}_{pob['modelo']}_{pob['cohorte']}_{clave}.npy"
    if ruta.exists():
        return np.load(ruta)
    salida = np.asarray(modelo.predecir(entrada) if pob["tarea"] == "t1" else modelo.predecir(entrada, sem), dtype="float64")
    carpeta.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp.npy")
    np.save(tmp, salida)
    os.replace(tmp, ruta)
    return salida


def _salida_modelo(conn, pob: Mapping[str, Any], artefactos: Path, personas: Optional[Mapping[str, Set[Any]]] = None) -> Dict[str, Any]:
    """Base columns of one population and what its kept model returned. The reproduction check runs EVERY time (also when the
    prediction comes from the cache): if the model does not reproduce its saved test predictions, ``ReproduccionFallida`` aborts."""
    k = int(pob["k"])
    filas, sem = _filas_de_poblacion(conn, pob, personas)
    modelo = MC.cargar_o_ajustar(conn, pob["tarea"], k, pob["modelo"], artefactos)
    entrada = filas
    if pob["tarea"] == "t1" and pob["modelo"] == "cb_ben_pit":
        entrada = MC._t1_pit(conn, MC.snapshot_t1(conn), k, filas=filas)
    cols = [c for c in ("episodio_id", "persona_key", "cod_programa", "periodo_admision", "duracion_nominal", "periodo_corte",
                        "periodo_horizonte") if c in filas]
    base = filas[cols].reset_index(drop=True)
    if "ben_sin_dato" in entrada and pob["modelo"] == "cb_ben_pit":
        base["ben_sin_dato"] = entrada["ben_sin_dato"].to_numpy()
    out: Dict[str, Any] = {"base": base, "salida": _prediccion_en_cache(modelo, pob, entrada, sem, artefactos)}
    if pob["tarea"] == "t5":
        cortes = pd.Series([_corte(a, k) for a in filas["periodo_admision"]])
        out["obs"] = _eliminados_observados(conn, filas, cortes)
    return out


def _a_filas(pob: Mapping[str, Any], s: Mapping[str, Any]) -> pd.DataFrame:
    """Rows of one population with the columns of its block (see ``construir_documento``) from the model output."""
    k, b = int(pob["k"]), s["base"]
    if pob["tarea"] == "t1":
        meta = {"corte": b["periodo_corte"].to_numpy(), "horizonte": b["periodo_horizonte"].to_numpy()}
        extra: Dict[str, Any] = {"p": 1.0 - s["salida"],                        # probability of CONTINUING
                                 "sin_hist": b["ben_sin_dato"].to_numpy(dtype="float64") if "ben_sin_dato" in b else np.nan}
    elif pob["tarea"] == "t5":
        cortes = pd.Series([_corte(a, k) for a in b["periodo_admision"]])
        meta = {"corte": cortes.to_numpy(), "horizonte": [R.horizonte_periodo(c, 2) for c in cortes],
                "horizonte_desde": [R.horizonte_periodo(c, 1) for c in cortes]}
        extra = {"p": s["salida"], "obs": s["obs"]}
    else:
        extra, meta = {}, {"corte": [_corte(a, k) for a in b["periodo_admision"]], "horizonte": "nominal_mas_2"}
        for h, mas in zip(HITOS_EGRESO, (0, 2)):
            p, per, trunc = hito_egreso(s["salida"], b["periodo_admision"], b["duracion_nominal"].to_numpy(), k, mas)
            extra[f"p_{h}"], extra[f"per_{h}"] = p, per
            extra["trunc"] = trunc | extra.get("trunc", False)
    return pd.DataFrame({"episodio_id": b["episodio_id"].astype("int64").to_numpy(), "persona_key": b["persona_key"].to_numpy(),
                         "cod_programa": b["cod_programa"].to_numpy(), "cohorte": int(pob["cohorte"]), "k": k,
                         "modelo": pob["modelo"], **meta, **extra})


def _puntuar(conn, pob: Mapping[str, Any], artefactos: Path, personas: Optional[Mapping[str, Set[Any]]] = None) -> pd.DataFrame:
    return _a_filas(pob, _salida_modelo(conn, pob, artefactos, personas))


Q_HUELLA_UNIDADES = """
SELECT
 (SELECT coalesce(sum(hashtextextended(concat_ws('|', intento_id, episodio_id, periodo, codigo_asignatura, oportunidad,
          es_intento_evaluado, aprobado_curricular), 0)::numeric), 0)
  FROM neural_core.intento_asignatura WHERE episodio_id IS NOT NULL AND periodo <= %(c)s),
 (SELECT coalesce(sum(hashtextextended(concat_ws('|', persona_key, episodio_id, periodo, orden_canonico, cod_estado,
          es_correccion_sistema), 0)::numeric), 0)
  FROM neural_core.evento_estado WHERE periodo <= %(c)s),
 (SELECT coalesce(sum(hashtextextended(concat_ws('|', e.episodio_id, e.persona_key, e.cod_programa, e.periodo_admision,
          e.cod_admision, e.catalogo_inicial, p.id_nivel), 0)::numeric), 0)
  FROM neural_core.episodio_programa e LEFT JOIN neural_core.programa p ON p.cod_programa = e.cod_programa
  WHERE e.periodo_admision <= %(c)s),
 (SELECT coalesce(sum(hashtextextended(concat_ws('|', persona_key, episodio_id, fecha_titulacion), 0)::numeric), 0)
  FROM neural_core.titulacion)
"""


def _cuentas_actuales(conn, artefactos: Path) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Set[Any]]]:
    """``(actuales, cuentas, personas_por_corte)`` of the current students, cached under ``artefactos/proyeccion_cache``. The key is a content hash of
    the source rows (attempts, states, episodes with their level, degrees; order-independent sums of row hashes) up to the close
    and ``VERSION_CACHE``. ``cuentas`` is the output of ``contar_umbral``; the faculty is attached afterwards."""
    import hashlib

    with conn.cursor() as cur:
        cur.execute(Q_HUELLA_UNIDADES, {"c": CORTE_ACTUAL})
        huella = "|".join(str(x) for x in cur.fetchone())
    clave = hashlib.sha256(f"{VERSION_CACHE}|{CORTE_ACTUAL}|{huella}".encode()).hexdigest()[:24]
    ruta = Path(artefactos) / "proyeccion_cache" / f"actuales_{clave}.pkl"
    if ruta.exists():
        return pd.read_pickle(ruta)
    actuales, intentos, por_corte = _cargar_unidades(conn)
    res = (actuales, contar_umbral(intentos, actuales), por_corte)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    pd.to_pickle(res, tmp)
    os.replace(tmp, ruta)
    return res


def construir(conn, artefactos: Path) -> Dict[str, Any]:
    """Current students first, then every population (selected by cohort, ``k`` and cut among them) scored by its kept model
    (aborting if one does not reproduce); writes the document only when all of it was built."""
    artefactos = Path(artefactos)
    programas = FA.cargar_programas(conn)
    actuales, cuentas, personas = _cuentas_actuales(conn, artefactos)
    actuales = poner_facultad(actuales.drop(columns="facultad", errors="ignore"), programas)
    cuentas = cuentas.drop(columns=["facultad", "cod_programa"], errors="ignore").merge(
        actuales[["episodio_id", "facultad", "cod_programa"]], on="episodio_id", how="left")
    por_bloque: Dict[str, List[pd.DataFrame]] = {b: [] for b in ("continuidad", "eliminacion", "egreso")}
    previa = None
    for pob in POBLACIONES:
        if previa is not None and pob["tarea"] != previa:
            MC.limpiar_cache()                                  # one task's snapshot at a time
        previa = pob["tarea"]
        por_bloque[pob["bloque"]].append(poner_facultad(_puntuar(conn, pob, artefactos, personas), programas))
    poblaciones = {b: pd.concat(v, ignore_index=True) for b, v in por_bloque.items()}
    doc = construir_documento(actuales, None, poblaciones, cuentas, programas)
    destino = artefactos / "vista_proyeccion.json"
    tmp = destino.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sin_nan(doc), ensure_ascii=False, allow_nan=False, indent=1, default=int), encoding="utf-8")
    os.replace(tmp, destino)                                    # nothing is written unless the whole document was built
    return doc


# ------------------------------------------------------------------------------------------------------ command line
def resumen(doc: Mapping[str, Any]) -> str:
    """The "Toda la UCN" headline of every block (the first figures a reader meets)."""
    def uno(bloque: str):
        return (doc.get(bloque) or {}).get(UCN)

    def rng(b):
        return f"{b['esperados']:.0f} ({b['lo']:.0f} a {b['hi']:.0f})"

    lineas = [f"corte {doc['corte']}; sin_proyeccion n={doc['sin_proyeccion']['n']}"]
    b = uno("continuidad")
    lineas.append("continuidad: " + (f"n={b['n']}, seguirían {rng(b)}; por cohorte: "
                                     + "; ".join(f"{c['cohorte']} k={c['k']} {c['modelo']} n={c['n']} corte {c['corte']} horizonte {c['horizonte']}"
                                                 for c in b["por_cohorte"]) if b else "sin datos"))
    b = uno("eliminacion")
    lineas.append("eliminacion: " + (f"n={b['n']}, esperados {rng(b)}, observados_hasta_hoy={b['observados_hasta_hoy']} ({b['periodo_observado']}); por cohorte: "
                                     + "; ".join(f"{c['cohorte']} k={c['k']} n={c['n']} {c['esperados']}" for c in b["por_cohorte"]) if b else "sin datos"))
    b = uno("egreso")
    lineas.append("egreso: " + (f"n={b['n']}; " + "; ".join(f"{h} {rng(b[h])} {b[h]['desde']}-{b[h]['hasta']}" for h in HITOS_EGRESO if b[h]) if b else "sin datos"))
    b = uno("umbral")
    lineas.append("umbral: " + (f"n={b['n']}, en_umbral={b['en_umbral']}, a_1={b['a_1']}, a_2={b['a_2']}, lejos={b['lejos']}"
                                if b else "sin datos"))
    return "\n".join(lineas)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artefactos", type=Path, default=RAIZ / "artefactos")
    args = parser.parse_args(argv)
    try:
        from pipelines.common.db import dev_connection

        with dev_connection() as conn:
            doc = construir(conn, args.artefactos)
        print(resumen(doc))
    except Exception as exc:  # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
