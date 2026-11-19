"""Aggregates of the executive view "Lo que pasó" (what already happened) from the saved test predictions. No model is retrained.

``python -m evaluation.vista_historica`` writes ``artefactos/vista_historica.json`` (gitignored, AGGREGATES ONLY: no row, key or
name of a person). The exporter ``tools/exportar_resumen_modelos.py`` loads it into ``neural_mart.vista_historica`` (migration 029).
Fourteen blocks, each for "Toda la UCN" and for every faculty (by name). The first four:

* ``semestres``  semester of permanence (1-12) in which the episodes of the cohorts with 12 closed semesters of follow-up
  (T3 snapshot, k = 0) leave: "deja la UCN" (definitive exit that is not an elimination) versus "eliminado" (the last state of
  the episode is ``E``). Descriptive: no model.
* ``siguieron``  T1 at k = 1 on the test cohorts with the kept model (``cb_acad``): who continued one year later, how many the
  model expected (``n - sum(p)``) and the same by faculty.
* ``eliminados`` total undergraduate eliminations per calendar year (distinct episodes with an ``E`` state, up to 202520), plus the
  model check, T5 at k = 2: elimination in the two semesters after the 2nd one, by year (cohort + 1 = year of the first
  semester of the window). Observed in every year with data, expected (kept model ``gru_adm``) only in the test years. Plus the
  causal of every elimination of undergraduate episodes since 2016, grouped as in P117.
* ``alcance``    T1 at k = 1 on test: capture curve (share of the students who did not continue that a given share of
  supported students, ordered by predicted risk, would have reached) and the figure for the 10 % of highest risk.

Eight more blocks (modules ``vista_permanencia``, ``vista_ramos``, ``vista_egreso``; same publication rule):

* ``perfil_ingreso``, ``primer_semestre``  who continued by entry profile (route, school type, admission score quintile) and by the
  failures of the first semester (T1 k = 1, associations, not causes).
* ``ramos_reprobados``, ``ramos_esperado``, ``cuellos_botella``, ``semestre_malla``  most failed courses of the last five complete
  years (202110-202520), courses and departments failing more than the kept T2 model expected (test and posterior windows),
  courses that hold back the most students through the prerequisite graph, and failure by curriculum semester. Aggregated
  attempts only: no section, NRC or teacher is ever read.
* ``causales_programa``, ``tiempo_egreso``  elimination causes by program (faculty under "Toda la UCN") and time to graduate.

* ``senales``, ``esperar_semestre``  "Cómo decide el modelo" (module ``vista_modelo``, "Toda la UCN" only): the five families of inputs
  that weigh the most in each kept model (permutation importance) and how many of every 10 who leave are reached one cut earlier
  versus one cut later. Associations of the model, not causes.

Program filter (plan 2026-11-18, Task 8): every block above is also computed for every program, keyed by its program code (the mart
row key is a free text, so no migration is needed); ``programas`` lists ``{codigo, nombre, facultad}`` and ``filtros`` keeps "Toda la
UCN" and the faculties only. The two blocks that describe the MODEL, not a population (``senales``, ``esperar_semestre``), keep
their "Toda la UCN" values and carry ``aplica_a_poblacion: false``. Every block carries ``modelo`` (see
``evaluation.vista_modelo_visible``): ``None`` for what was only observed, the model object for what a kept model produced.

Publication rule: every count and rate is published for any group size (the user's decision of 18-11-2026 lifts the under-10 rule
for aggregates in this module); a block is left out only when its group is empty, and a rate over an empty group is ``None``.
Every row that carries a percentage also carries its ``n``. No row, key or name of a person is ever written.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import numpy as np
import pandas as pd

from evaluation import facultades as FA
from evaluation import vista_modelo_visible as MVIS
from evaluation.grupos_facultad import alinear, poner_facultad, sin_nan

RAIZ = Path(__file__).resolve().parents[1]
UCN = "Toda la UCN"
SEM_MAX = 12                          # semesters of permanence shown; cohorts need 12 closed semesters of follow-up
MODELO_T1, MODELO_T5 = "cb_acad", "gru_adm"
MODELO_T2 = "cb_c_nuevas"
ANIO_REGLAMENTO = 2025                # new academic regulation from 202520 (P117 / P118)
PERIODO_TOTALES_HASTA = "202520"       # last closed period of the yearly totals (2025 is the last full year)
PERIODO_CAUSAL_DESDE = "201610"       # the causal text is informed in 97.9 % or more of the eliminations from 2016
PASOS_CURVA = 20                      # capture curve: one point every 5 % of supported students
FRACCION_APOYO = 0.10
CLASES_T5 = ("continua", "egreso", "transicion", "eliminacion", "otra_salida")

# P117 grouping of ``neural_core.evento_estado.cod_causal`` (checked against the causal text of ``ban_estados_academicos``):
# 0x = Art. 50, 2x = Art. 52, 5x = Art. 46 (from 202520), 84 / 5Z = Art. 77 / 51 "Egres.Elim.".
GRUPOS_CAUSAL = {
    "tercera": ("3.ª oportunidad", ("0B", "2B", "5B")),
    "segunda": ("2.ª oportunidad", ("0C", "2A", "5A")),
    "no_inscribe": ("No inscribe asignaturas", ("0D", "2D", "5I")),
    "avance": ("Avance o permanencia", ("0A", "2C")),
    "egresado": ("Egresado sin titularse", ("84", "5Z")),
    "otras": ("Otras causas", ()),
}
_CODIGO_A_GRUPO = {c: g for g, (_, codigos) in GRUPOS_CAUSAL.items() for c in codigos}


def grupo_causal(cod: Optional[str]) -> str:
    """Group of an elimination causal code; combined letters, "Otros/Migración", 46-C, Art. 29 and a missing code are ``otras``."""
    if cod is None or (isinstance(cod, float) and math.isnan(cod)):
        return "otras"
    return _CODIGO_A_GRUPO.get(str(cod).strip().upper(), "otras")


# ----------------------------------------------------------------------------------------------------- helpers
def _pct(a: float, b: float) -> Optional[float]:
    """Share ``a / b``; ``None`` when the group is empty (``b == 0``)."""
    return None if not b else float(a) / float(b)


# ------------------------------------------------------------------------------------------- block 1: semesters
def bloque_semestres(d: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """``d``: one row per episode with ``tiempo`` (semester of the event), ``causa`` (2 = definitive exit) and ``eliminado``.
    Every count is exact whatever the size of the group; ``None`` only when there is nobody."""
    n = int(len(d))
    if n == 0:
        return None
    sal = d.loc[(d["causa"] == 2) & d["tiempo"].between(1, SEM_MAX)]
    filas: List[Dict[str, Any]] = []
    for s in range(1, SEM_MAX + 1):
        en = sal.loc[sal["tiempo"] == s]
        elim = int(en["eliminado"].astype(bool).sum())
        dejan = int(len(en)) - elim
        filas.append({"semestre": s, "dejan": dejan, "eliminados": elim, "pct_dejan": _pct(dejan, n), "pct_eliminados": _pct(elim, n)})
    total = int(len(sal))
    primero = int((sal["tiempo"] <= 2).sum())
    return {"n": n, "bajas": total, "bajas_primer_anio": primero, "pct_bajas_primer_anio": _pct(primero, total),
            "pct_bajas": _pct(total, n), "filas": filas}


# ------------------------------------------------------------------------------------------ block 2: siguieron
def bloque_siguieron(y: np.ndarray, p: np.ndarray) -> Optional[Dict[str, Any]]:
    """``y`` = 1 when the student did not continue, ``p`` = predicted risk of not continuing."""
    n, eventos = int(len(y)), int(np.sum(y))
    if n == 0:
        return None
    siguieron = n - eventos
    esperados = float(n - np.sum(p))
    return {"n": n, "siguieron": siguieron, "esperados": round(esperados, 1), "pct_siguieron": siguieron / n,
            "pct_esperado": esperados / n, "diferencia": round(siguieron - esperados, 1)}


def puntos_facultad(d: pd.DataFrame, y: np.ndarray, p: np.ndarray) -> List[Dict[str, Any]]:
    """Occurred versus expected "continued" share per faculty (every faculty with students), largest first."""
    out = []
    for fac, idx in d.groupby("facultad", sort=True).indices.items():
        b = bloque_siguieron(y[idx], p[idx])
        if b is not None and fac != FA_SIN:
            out.append({"facultad": fac, "n": b["n"], "pct_siguieron": b["pct_siguieron"], "pct_esperado": b["pct_esperado"]})
    return sorted(out, key=lambda f: (-f["n"], f["facultad"]))


FA_SIN = "Sin facultad"


# ----------------------------------------------------------------------------------------- block 3: eliminated
def bloque_anios(d: pd.DataFrame) -> List[Dict[str, Any]]:
    """Per year (cohort + 1): observed elimination rate, expected rate (test years only) and whether the year is partial.

    ``d`` has ``cohorte_anio``, ``resultado`` (``censurado`` rows are kept to flag a partial year), ``p`` (NaN outside test)."""
    filas = []
    d = d.assign(anio=d["cohorte_anio"].astype(int) + 1)
    for anio, g in d.groupby("anio", sort=True):
        obs = g.loc[g["resultado"].isin(CLASES_T5)]
        n, elim = int(len(obs)), int((obs["resultado"] == "eliminacion").sum())
        if n == 0:
            continue
        fila: Dict[str, Any] = {"anio": int(anio), "n": n, "eliminados": elim, "tasa": elim / n,
                                "parcial": bool((g["resultado"] == "censurado").any()),
                                "esperados": None, "tasa_esperada": None}
        if obs["p"].notna().all():
            esp = float(obs["p"].sum())
            fila["esperados"], fila["tasa_esperada"] = round(esp, 1), esp / n
        filas.append(fila)
    return filas


def bloque_causales(cod_causal: pd.Series) -> Optional[Dict[str, Any]]:
    """Causes of the eliminations of one group: every cause of ``GRUPOS_CAUSAL`` with its exact count and share (``otras`` is a
    cause of the P117 list, not a size bucket). ``None`` when the group has no elimination."""
    total = int(len(cod_causal))
    if total == 0:
        return None
    grupos = cod_causal.map(grupo_causal).value_counts()
    filas = [{"grupo": g, "etiqueta": etiqueta, "n": int(grupos.get(g, 0)), "pct": _pct(int(grupos.get(g, 0)), total)}
             for g, (etiqueta, _) in GRUPOS_CAUSAL.items()]
    return {"total": total, "filas": filas}


def bloque_totales(causas: pd.DataFrame) -> List[Dict[str, Any]]:
    """Distinct undergraduate episodes with an ``E`` state per calendar year (all cohorts), every year with at least one."""
    if causas.empty or "episodio_id" not in causas:
        return []
    d = causas.loc[causas["periodo"] <= PERIODO_TOTALES_HASTA]
    cuenta = d.assign(anio=d["periodo"].str[:4].astype(int)).groupby("anio")["episodio_id"].nunique()
    return [{"anio": int(a), "eliminados": int(n)} for a, n in cuenta.items()]


def bloque_eliminados(anios: List[Dict[str, Any]], causales: Optional[Dict[str, Any]],
                      totales: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    totales = totales or []
    if not anios and causales is None and not totales:
        return None
    return {"totales": totales, "anios": anios, "anio_reglamento": ANIO_REGLAMENTO,
            "clave": dict(totales[-1]) if totales else None, "causales": causales}


# ------------------------------------------------------------------------------------------- block 4: reach
def curva_alcance(y: np.ndarray, p: np.ndarray, pasos: int = PASOS_CURVA, fraccion: float = FRACCION_APOYO) -> Optional[Dict[str, Any]]:
    """Capture curve of the risk ranking: share of the events reached when the ``q`` highest-risk students are supported."""
    n, eventos = int(len(y)), int(np.sum(y))
    if n == 0 or eventos == 0:
        return None
    orden = np.argsort(-np.asarray(p, dtype="float64"), kind="mergesort")
    acumulado = np.cumsum(np.asarray(y)[orden])

    def alcanzados(fr: float) -> int:
        m = int(math.ceil(fr * n - 1e-9))
        return 0 if m <= 0 else int(acumulado[min(m, n) - 1])

    m = int(math.ceil(fraccion * n - 1e-9))
    alc = alcanzados(fraccion)
    puntos = [{"apoyados": i / pasos, "alcanzados": alcanzados(i / pasos) / eventos} for i in range(pasos + 1)]
    return {"n": n, "eventos": eventos, "fraccion_apoyo": fraccion, "apoyados": m, "alcanzados": alc,
            "pct_alcanzado": alc / eventos, "de_cada_10": round(10.0 * alc / eventos, 1), "al_azar_de_cada_10": round(10.0 * fraccion, 1),
            "curva": puntos}


# --------------------------------------------------------------------------------------------------- assembly
def construir_filtros(nombres: List[str]) -> List[str]:
    return [UCN] + sorted(n for n in set(nombres) if n and n != FA_SIN)


def trozos(d: pd.DataFrame, codigos: Iterable[str] = ()) -> Dict[str, pd.DataFrame]:
    """``{filtro: sub-frame}`` for "Toda la UCN", every faculty and every program of ``codigos`` that has rows in ``d``. One group-by per
    level (never one mask per filter): the 55 programs cost one pass over the frame, not 55."""
    out = {UCN: d}
    if "facultad" in d:
        for fac, idx in d.groupby(d["facultad"].to_numpy(), sort=False).indices.items():
            if fac != FA_SIN:
                out[str(fac)] = d.iloc[idx]
    codigos = frozenset(codigos)
    if codigos and "cod_programa" in d:
        cod = d["cod_programa"].astype(str).to_numpy()
        for c, idx in d.groupby(np.where(d["cod_programa"].isna().to_numpy(), "", cod), sort=False).indices.items():
            if c in codigos:
                out[str(c)] = d.iloc[idx]
    return out


def codigos_presentes(*frames: Optional[pd.DataFrame]) -> set:
    """Program codes (as text) found in the frames that have a ``cod_programa`` column."""
    return {str(c) for d in frames if d is not None and "cod_programa" in d for c in d["cod_programa"].dropna().unique()}


def lista_programas(programas: Optional[pd.DataFrame], presentes: Iterable[str], facultades: Iterable[str]) -> List[Dict[str, str]]:
    """The program filters: ``{codigo, nombre, facultad}`` of every program of the dictionary (``programas``: index ``cod_programa``,
    ``nombre_programa``, ``facultad_nombre``) that has data and whose faculty is itself a filter. Ordered by faculty, then name."""
    if programas is None:
        return []
    facultades = set(facultades)
    por_codigo = {str(c): c for c in programas.index}
    out = []
    for cod in sorted(set(presentes)):
        if cod in por_codigo and programas.at[por_codigo[cod], "facultad_nombre"] in facultades:
            out.append({"codigo": cod, "nombre": str(programas.at[por_codigo[cod], "nombre_programa"]),
                        "facultad": str(programas.at[por_codigo[cod], "facultad_nombre"])})
    return sorted(out, key=lambda p: (p["facultad"], p["nombre"], p["codigo"]))


def por_filtro(d: pd.DataFrame, nombres: List[str], f, codigos: Iterable[str] = ()) -> Dict[str, Any]:
    """``{filtro: f(sub-frame)}`` for "Toda la UCN", every faculty and every program of ``codigos``; ``None`` results are dropped."""
    codigos = list(codigos)
    t = trozos(d, codigos)
    out = {}
    for filtro in construir_filtros(nombres) + codigos:
        if filtro not in t:
            continue
        r = f(t[filtro])
        if r is not None:
            out[filtro] = r
    return out


def construir_documento(t3: pd.DataFrame, t1: pd.DataFrame, y1: np.ndarray, p1: np.ndarray, t5: pd.DataFrame,
                        causas: pd.DataFrame, *, ramos: Optional[pd.DataFrame] = None, esperado: Optional[pd.DataFrame] = None,
                        prerreq: Optional[pd.DataFrame] = None, tiempo: Optional[pd.DataFrame] = None,
                        senales: Optional[Mapping[str, Any]] = None,
                        esperar_semestre: Optional[Mapping[str, Any]] = None,
                        programas: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """All blocks from the prepared frames (each with a ``facultad`` column).

    ``t1`` rows align with ``y1`` / ``p1``; ``t5`` has ``cohorte_anio``, ``resultado`` and ``p``; ``causas`` has ``cod_causal``.
    Optional inputs of the course / exit blocks (each with ``facultad``): ``ramos`` (aggregated attempts), ``esperado`` (failures
    versus expected by window), ``prerreq`` (prerequisite edges), ``tiempo`` (T3 k = 0 episodes with the nominal duration).
    ``senales`` and ``esperar_semestre`` are the finished blocks of ``vista_modelo``; they are stored under "Toda la UCN" only.
    ``programas`` (index ``cod_programa``, ``nombre_programa``, ``facultad_nombre``) turns on the program filters: every frame needs
    ``cod_programa`` for its program blocks."""
    from evaluation import vista_egreso as VE, vista_permanencia as VP, vista_ramos as VR

    extra = [x["facultad"] for x in (ramos, esperado, tiempo) if x is not None]
    nombres = list(pd.concat([t3["facultad"], t1["facultad"], t5["facultad"], causas["facultad"], *extra]).dropna().unique())
    t1 = t1.assign(y=y1, p=p1)
    t1q = VP.agregar_quintiles(t1)
    lista = lista_programas(programas, codigos_presentes(t3, t1, t5, causas, ramos, esperado, tiempo), construir_filtros(nombres))
    cods = [p["codigo"] for p in lista]
    todos = construir_filtros(nombres) + cods
    pf = lambda d, f: por_filtro(d, nombres, f, cods)                              # noqa: E731
    sin = lambda d, f: pf(d, f) if d is not None else {}                           # noqa: E731
    catalogo = prerreq if prerreq is not None else pd.DataFrame(columns=["codigo_requisito", "codigo_asignatura"])
    deps = VR.dependientes(catalogo)
    causas_ok = {"episodio_id", "periodo", "cod_programa"} <= set(causas.columns)
    base_causas = VE.una_por_episodio(causas) if causas_ok else causas            # same window and one per episode as causales_programa
    documento = {
        "version": 1, "modelo_t1": MODELO_T1, "modelo_t5": MODELO_T5,
        "filtros": construir_filtros(nombres), "programas": lista,
        "semestres": pf(t3, bloque_semestres),
        "siguieron": pf(t1, lambda d: bloque_siguieron(d["y"].to_numpy(), d["p"].to_numpy())),
        "por_facultad": puntos_facultad(t1.reset_index(drop=True), t1["y"].to_numpy(), t1["p"].to_numpy()),
        "eliminados": _eliminados(t5, base_causas, causas, todos, cods),
        "alcance": pf(t1, lambda d: curva_alcance(d["y"].to_numpy(), d["p"].to_numpy())),
        "cohortes": {
            "semestres": _rango(t3["cohorte_anio"]), "siguieron": _rango(t1["cohorte_anio"]),
            "eliminados": _anios_totales(causas), "alcance": _rango(t1["cohorte_anio"]),
            "test_t5": _rango(t5.loc[t5["p"].notna(), "cohorte_anio"] + 1)},
    }
    documento["cohortes"]["perfil_ingreso"] = documento["cohortes"]["primer_semestre"] = documento["cohortes"]["siguieron"]
    documento["cohortes"]["tiempo_egreso"] = _rango_tiempo(tiempo)
    documento.update({
        "perfil_ingreso": pf(t1q, VP.bloque_perfil) if "via_clase" in t1 else {},
        "primer_semestre": pf(t1, VP.bloque_primer_semestre) if "reprobados" in t1 else {},
        "ramos_reprobados": sin(ramos, VR.bloque_reprobados),
        "ramos_esperado": sin(esperado, VR.bloque_esperado),
        "cuellos_botella": sin(ramos, lambda d: VR.bloque_cuellos(d, catalogo, deps=deps)),
        "semestre_malla": sin(ramos, VR.bloque_semestre_malla),
        "causales_programa": _causales_programa(causas, todos, cods, VE) if causas_ok else {},
        "tiempo_egreso": sin(tiempo, VE.bloque_tiempo),
        "senales": {UCN: {**senales, "aplica_a_poblacion": False}} if senales else {},
        "esperar_semestre": {UCN: {**esperar_semestre, "aplica_a_poblacion": False}} if esperar_semestre else {},
    })
    _poner_modelos(documento)
    return documento


# ------------------------------------------------------------------------------------------ the model behind each block
BLOQUES_OBSERVADOS = ("semestres", "ramos_reprobados", "cuellos_botella", "semestre_malla", "causales_programa", "tiempo_egreso")
BLOQUES_T1 = ("siguieron", "alcance", "perfil_ingreso", "primer_semestre")


def _anios(r: Optional[List[int]]) -> str:
    return "" if not r else (str(r[0]) if r[0] == r[1] else f"{r[0]}-{r[1]}")


def _anios_ventanas() -> str:
    from evaluation import vista_ramos as VR

    def texto(v):
        a, b = v[0][:4], v[1][:4]
        return a if a == b else f"{a}-{b}"
    return "; ".join(f"{'Prueba' if n == 'prueba' else 'Posterior'}: {texto(v)}" for n, v in VR.VENTANAS_ESPERADO.items())


def _poner_modelos(doc: Dict[str, Any]) -> None:
    """Adds ``modelo`` to every block (``None`` = observed only) and ``modelos`` to the two that use several; ``doc["modelos"]`` maps
    each block to its model (``por_facultad`` is a list: it has no room for the field), so one reader of the meta finds them all."""
    from evaluation import vista_modelo as VM

    c = doc["cohortes"]
    t1 = MVIS.modelo_visible("t1", 1, MODELO_T1, f"Prueba: cohortes {_anios(c.get('siguieron'))}".strip(": "), "esperado")
    t5 = MVIS.modelo_visible("t5", 2, MODELO_T5, f"Prueba: años {_anios(c.get('test_t5'))}".strip(": "), "esperado")
    t2 = MVIS.modelo_visible("t2", 0, MODELO_T2, _anios_ventanas(), "esperado", corte=MVIS.CORTE_ANTES_DEL_PERIODO)
    unico = {**{b: t1 for b in BLOQUES_T1}, "eliminados": t5, "ramos_esperado": t2}
    for b in BLOQUES_OBSERVADOS:
        MVIS.etiquetar(doc[b])
    for b, m in unico.items():
        MVIS.etiquetar(doc[b], m)
    senales = [MVIS.modelo_visible(t["tarea"], t["k"], t["modelo"], f"Prueba: muestra de {t['n_muestra']} casos", "esperado")
               for t in ((doc["senales"].get(UCN) or {}).get("tareas") or [])]
    pares = {(p["tarea"], p["k_antes"], p["k_despues"]): p for p in VM.PARES_ESPERAR}
    esperar = []
    for x in ((doc["esperar_semestre"].get(UCN) or {}).get("comparaciones") or []):
        p = pares[(x["tarea"], x["k_antes"], x["k_despues"])]
        esperar += [MVIS.modelo_visible(x["tarea"], k, p[col].split("__")[-1], "Prueba: cohortes de prueba de cada corte", "esperado")
                    for k, col in ((x["k_antes"], "col_antes"), (x["k_despues"], "col_despues"))]
    MVIS.etiquetar(doc["senales"], None, MVIS.distintos(senales))
    MVIS.etiquetar(doc["esperar_semestre"], None, MVIS.distintos(esperar))
    doc["modelos"] = {**{b: None for b in BLOQUES_OBSERVADOS}, **unico, "por_facultad": t1,
                      "senales": MVIS.distintos(senales), "esperar_semestre": MVIS.distintos(esperar)}


def _eliminados(t5: pd.DataFrame, base_causas: pd.DataFrame, causas: pd.DataFrame, filtros: List[str], codigos: List[str]) -> Dict[str, Any]:
    """Block "eliminados" of every filter: the model check by year (T5), the causes and the yearly totals."""
    a, b, c = trozos(t5, codigos), trozos(base_causas, codigos), trozos(causas, codigos)
    out = {}
    for f in filtros:
        bloque = bloque_eliminados(bloque_anios(a[f]) if f in a else [],
                                   bloque_causales(b[f]["cod_causal"]) if f in b else None,
                                   bloque_totales(c[f]) if f in c else [])
        if bloque is not None:
            out[f] = bloque
    return out


def _causales_programa(causas: pd.DataFrame, filtros: List[str], codigos: List[str], VE) -> Dict[str, Any]:
    """Rows are faculties under "Toda la UCN", programs under a faculty and the program itself under a program."""
    if "programa" not in causas:
        causas = causas.assign(programa=causas["cod_programa"])
    t = trozos(causas, codigos)
    out = {}
    for filtro in filtros:
        if filtro not in t:
            continue
        b = VE.bloque_causales_programa(t[filtro], por="facultad") if filtro == UCN else VE.bloque_causales_programa(t[filtro])
        if b is not None:
            out[filtro] = b
    return out


def _anios_totales(causas: pd.DataFrame) -> Optional[List[int]]:
    a = [x["anio"] for x in bloque_totales(causas)]
    return [min(a), max(a)] if a else None


def _rango_tiempo(tiempo: Optional[pd.DataFrame]) -> Optional[List[int]]:
    """Cohort range of the episodes that enter the time-to-graduate block (the ones with follow-up of the nominal duration + 4)."""
    if tiempo is None or "cohorte_anio" not in tiempo:
        return None
    d = tiempo.loc[tiempo["seguimiento_max"] >= tiempo["duracion_nominal_sem"] + 4]
    return _rango(d["cohorte_anio"].dropna())


def _rango(s: pd.Series) -> Optional[List[int]]:
    return None if s.empty else [int(s.min()), int(s.max())]


# --------------------------------------------------------------------------------------------------- database
Q_T3 = """
WITH ult AS (SELECT DISTINCT ON (episodio_id) episodio_id, cod_estado FROM neural_core.evento_estado
             WHERE episodio_id IS NOT NULL AND NOT es_correccion_sistema ORDER BY episodio_id, orden_canonico DESC)
SELECT s.cod_programa, s.cohorte_anio, s.tiempo, s.causa, COALESCE(u.cod_estado = 'E', false) AS eliminado
FROM neural_mart.snapshot_t3 s LEFT JOIN ult u USING (episodio_id)
WHERE s.k = 0 AND s.seguimiento_max >= 12
"""
Q_T1 = ("SELECT episodio_id, cod_programa, cohorte_anio, continua, via_clase, tipo_colegio, pct_ponderado, reprobados "
        "FROM neural_mart.snapshot_t1 "
        "WHERE k = 1 AND split = 'test' AND estado_muestra = 'observada' AND continua IS NOT NULL")
Q_T5 = "SELECT episodio_id, cod_programa, cohorte_anio, split, resultado FROM neural_mart.snapshot_t45 WHERE k = 2"
Q_CAUSAS = """
SELECT DISTINCT e.episodio_id, e.periodo, e.cod_programa, p.nombre_programa AS programa, e.cod_causal
FROM neural_core.evento_estado e
JOIN neural_core.episodio_programa ep ON ep.episodio_id = e.episodio_id
JOIN neural_core.programa p ON p.cod_programa = ep.cod_programa
WHERE e.cod_estado = 'E' AND NOT e.es_correccion_sistema AND e.periodo >= %s
  AND p.id_nivel = 1 AND ep.cod_admision NOT IN ('IN', 'PE', 'IE')
"""
Q_TIEMPO = """
SELECT s.cod_programa, s.cohorte_anio, p.nombre_programa AS programa, s.tiempo, s.causa, s.seguimiento_max, s.duracion_nominal AS duracion_nominal_sem
FROM neural_mart.snapshot_t3 s JOIN neural_core.programa p ON p.cod_programa = s.cod_programa
WHERE s.k = 0 AND s.duracion_nominal IS NOT NULL
"""
# aggregated evaluated attempts of the last five complete years by student program x course x curriculum semester of the
# student's own catalog; no NRC, section or teacher column is selected (P58 periods are not a failure count)
Q_RAMOS = """
SELECT i.cod_carrera AS cod_programa, i.codigo_asignatura AS codigo, m.semestre, count(*) AS intentos,
       count(*) FILTER (WHERE NOT i.aprobado_curricular) AS reprobados
FROM neural_core.intento_asignatura i
LEFT JOIN neural_core.asignatura_malla m ON m.cod_programa = i.cod_carrera AND m.catalogo = i.catalogo
     AND m.codigo_asignatura = i.codigo_asignatura
WHERE i.es_intento_evaluado AND i.periodo BETWEEN %s AND %s AND i.periodo NOT IN ('201920', '202010')
GROUP BY 1, 2, 3
"""
Q_NOMBRES = """
SELECT DISTINCT ON (codigo_asignatura) codigo_asignatura AS codigo, nombre_asignatura AS nombre, depto, depto_desc
FROM neural_core.asignatura_malla ORDER BY codigo_asignatura, catalogo DESC
"""
Q_PRERREQ = ("SELECT cod_programa, catalogo, codigo_requisito, codigo_asignatura FROM neural_core.prerrequisito "
             "WHERE codigo_requisito IS NOT NULL")
Q_T2 = ("SELECT intento_id, cod_programa, codigo_asignatura, periodo, y FROM neural_mart.snapshot_t2 "
        "WHERE split IN ('test', 'posterior') AND periodo BETWEEN %s AND %s")


def _leer(conn, sql: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        d = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    if "cod_programa" in d:
        d["cod_programa"] = d["cod_programa"].astype(object)
    return d


def preparar_t1(snap: pd.DataFrame, preds: Mapping[str, np.ndarray], programas: pd.DataFrame):
    d = snap.reset_index(drop=True)
    d = d.iloc[alinear(preds["episodio_test"], d)].reset_index(drop=True)
    d = poner_facultad(d, programas)
    y = (~d["continua"].astype(bool)).astype("int8").to_numpy()
    return d, y, preds[f"test__{MODELO_T1}"].astype("float64")


def preparar_t5(snap: pd.DataFrame, preds: Mapping[str, np.ndarray], programas: pd.DataFrame) -> pd.DataFrame:
    d = poner_facultad(snap.reset_index(drop=True), programas)
    d["p"] = np.nan
    test = d.index[(d["split"] == "test") & d["resultado"].isin(CLASES_T5)].to_numpy()
    sub = d.loc[test].reset_index(drop=True)
    pos = alinear(preds["episodio_id"], sub)
    d.loc[test[pos], "p"] = preds[f"T5__{MODELO_T5}"].astype("float64")
    return d


def construir(conn, artefactos: Path) -> Dict[str, Any]:
    programas = FA.cargar_programas(conn)
    t3 = poner_facultad(_leer(conn, Q_T3), programas)
    t3["eliminado"] = t3["eliminado"].astype(bool)
    z1 = np.load(artefactos / "preds" / "t1_k1.npz")
    t1, y1, p1 = preparar_t1(_leer(conn, Q_T1), {n: z1[n] for n in z1.files}, programas)
    z5 = np.load(artefactos / "preds" / "t45_k2_test.npz")
    t5 = preparar_t5(_leer(conn, Q_T5), {n: z5[n] for n in z5.files}, programas)
    causas = poner_facultad(_leer(conn, Q_CAUSAS, (PERIODO_CAUSAL_DESDE,)), programas)
    from evaluation import vista_modelo as VM

    doc = construir_documento(t3, t1, y1, p1, t5, causas, **_entradas_nuevas(conn, artefactos, programas), programas=programas,
                              senales=VM.calcular_senales(conn, artefactos, log=lambda m: print(m, flush=True)),
                              esperar_semestre=VM.calcular_esperar(conn, artefactos))
    doc["periodo_causales_desde"] = PERIODO_CAUSAL_DESDE
    return doc


def _entradas_nuevas(conn, artefactos: Path, programas: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Frames of the course and exit blocks: aggregated attempts, failures versus expected, prerequisites and T3 durations."""
    from evaluation import vista_ramos as VR

    nombres = _leer(conn, Q_NOMBRES)
    ramos = _leer(conn, Q_RAMOS, (VR.VENTANA_DESDE, VR.VENTANA_HASTA)).merge(nombres, on="codigo", how="left")
    ramos["nombre"] = ramos["nombre"].fillna(ramos["codigo"])
    preds = {}
    for ventana, archivo in (("prueba", "t2_test.npz"), ("posterior", "t2_posterior.npz")):
        z = np.load(artefactos / "preds" / archivo)
        preds[ventana] = {"intento_id": z["intento_id"], MODELO_T2: z[MODELO_T2]}
    desde = min(v[0] for v in VR.VENTANAS_ESPERADO.values())
    hasta = max(v[1] for v in VR.VENTANAS_ESPERADO.values())
    esperado = VR.preparar_esperado(_leer(conn, Q_T2, (desde, hasta)), preds, MODELO_T2, nombres)
    return {"ramos": poner_facultad(ramos, programas), "esperado": poner_facultad(esperado, programas),
            "prerreq": _leer(conn, Q_PRERREQ), "tiempo": poner_facultad(_leer(conn, Q_TIEMPO), programas)}


def resumen(doc: Mapping[str, Any]) -> str:
    lineas = [f"{b}: {len(doc[b])} filtros" for b in ("semestres", "siguieron", "eliminados", "alcance")]
    return ", ".join(lineas) + "".join("\n" + linea for linea in _titulares(doc))


def _titulares(doc: Mapping[str, Any]) -> List[str]:
    """One line per new block with its "Toda la UCN" headline (the first figure a reader meets)."""
    def uno(bloque: str):
        return (doc.get(bloque) or {}).get(UCN)

    out: List[str] = []
    b = uno("perfil_ingreso")
    out.append("perfil_ingreso: " + (f"n={b['n']}, " + "; ".join(f"{x['dimension']}: {len(x['filas'])} grupos" for x in b["dimensiones"]) if b else "sin datos"))
    b = uno("primer_semestre")
    out.append("primer_semestre: " + ("; ".join(f"{f['reprobaciones']} reprob.: {f['pct_siguieron']:.0%} siguieron" if f["pct_siguieron"] is not None
                                              else f"{f['reprobaciones']} reprob.: n={f['n']}" for f in b["filas"]) if b else "sin datos"))
    b = uno("ramos_reprobados")
    out.append("ramos_reprobados: " + (f"{b['desde']}-{b['hasta']}, mayor tasa {b['por_tasa'][0]['nombre']} ({b['por_tasa'][0]['tasa']:.0%}), "
                                       f"mayor volumen {b['por_volumen'][0]['nombre']} ({b['por_volumen'][0]['reprobados']})" if b else "sin datos"))
    b = uno("ramos_esperado")
    out.append("ramos_esperado: " + ("; ".join(f"{v}: {w['ramos'][0]['nombre']} {w['ramos'][0]['diferencia']:+.0f} ({w['ramos'][0]['lo']:.0f} a {w['ramos'][0]['hi']:.0f})"
                                              for v, w in b["ventanas"].items() if w["ramos"]) if b else "sin datos"))
    b = uno("cuellos_botella")
    out.append("cuellos_botella: " + (f"{b['filas'][0]['nombre']} impacto {b['filas'][0]['impacto']} ({b['filas'][0]['reprobados']} x {b['filas'][0]['dependientes']})" if b else "sin datos"))
    b = uno("semestre_malla")
    out.append("semestre_malla: " + (", ".join(f"S{f['semestre']} {f['tasa']:.0%}" if f["tasa"] is not None else f"S{f['semestre']} sin tasa" for f in b["filas"]) if b else "sin datos"))
    b = uno("causales_programa")
    out.append("causales_programa: " + (f"{len(b['filas'])} facultades, total {sum(f['total'] for f in b['filas'])}" if b else "sin datos"))
    b = uno("tiempo_egreso")
    out.append("tiempo_egreso: " + (f"{len(b['filas'])} programas, primer programa {b['filas'][0]['programa']} a tiempo {b['filas'][0]['pct_a_tiempo']}" if b else "sin datos"))
    return out + _titulares_modelo(doc)


def _titulares_modelo(doc: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    b = (doc.get("senales") or {}).get(UCN)
    for t in (b["tareas"] if b else []):
        out.append(f"senales {t['tarea']} k={t['k']} {t['modelo']} (n={t['n_muestra']}): "
                   + "; ".join(f"{s['etiqueta']} {s['peso_pct']:.0f}%" for s in t["senales"]))
    b = (doc.get("esperar_semestre") or {}).get(UCN)
    if b:
        out.append("esperar_semestre: " + "; ".join(f"{c['tarea']} k{c['k_antes']}->k{c['k_despues']}: {c['de_cada_10_antes']} -> {c['de_cada_10_despues']} de cada 10"
                                                   for c in b["comparaciones"]))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artefactos", type=Path, default=RAIZ / "artefactos")
    args = parser.parse_args(argv)
    try:
        from pipelines.common.db import dev_connection

        with dev_connection() as conn:
            doc = construir(conn, args.artefactos)
        (args.artefactos / "vista_historica.json").write_text(
            json.dumps(sin_nan(doc), ensure_ascii=False, allow_nan=False, indent=1, default=int), encoding="utf-8")
        print(resumen(doc))
    except Exception as exc:  # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
