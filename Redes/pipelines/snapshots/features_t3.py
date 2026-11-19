"""Point-in-time construction of the T3 snapshot ("tiempo hasta titulacion", docs/10_benchmark_t3.md) with pandas.

Inputs are plain DataFrames (loaded by ``t3.py``; tests pass synthetic ones). Nothing here touches a database.

Population (D47, P62): the exchange programs are out (by program code) and an Ingenieria Civil Plan Comun episode is
merged with the first later Ingenieria Civil specialty episode of the same person (``vincular_plan_comun``) into ONE
trajectory whose unit is the Plan Comun admission; the linked specialty episode is never a separate unit.

Leakage guards, all covered by ``tests/unit/test_snapshot_t3.py`` and ``tests/unit/test_snapshot_t3_plan_comun.py``:
* every feature is computed from facts of the slots ``<= k`` (the T1 helpers, plus static program data);
* the label (time, cause) only looks at slots after the cut and never feeds a feature;
* attempts of the periods without recorded failures (P58) feed credits but not pass-rate statistics;
* events past the administrative limit are censored, never dropped.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from ..marts.rules import base_ordinal
from . import features as F
from . import rules as R
from . import rules_t3 as R3

FEATURE_COLS_ADMISION = ["cohorte_anio", "preferencia", "con_postulacion", *F.SCORE_COLS,
                         "duracion_nominal", "creditos_malla_total", "malla_conocida",
                         "trayectoria_plan_comun", "especialidad_conocida_al_corte"]
FEATURE_COLS_CAT = ["cod_programa", "via_clase", "cod_admision", "sede", "tipo_colegio", "depend_colegio",
                    "region_colegio"]
FEATURE_COLS_ACADEMICO = [
    "creditos_aprobados", "intentos_evaluados", "aprobados", "reprobados", "tasa_aprobacion", "promedio_evaluado",
    "n_notas_promedio", "convalidaciones", "cursos_verano_invierno", "n_interrupcion", "cambios_catalogo",
    "semestres_matriculados", "intentos_ult_semestre", "tasa_ult_semestre", "promedio_ult_semestre",
    "creditos_esperados", "avance_malla", "fraccion_malla", "n_sem_sin_reprobacion",
]
SNAPSHOT_COLS_T3: List[str] = [
    "episodio_id", "k", "persona_key", "cod_programa", "periodo_admision", "cohorte_anio", "split",
    "seguimiento_max", "tiempo", "causa", "salida_tipo", "salida_a_otro_programa", "tiempo_titulacion",
    "episodio_especialidad_id", *FEATURE_COLS_CAT[1:], *[c for c in FEATURE_COLS_ADMISION if c != "cohorte_anio"], *FEATURE_COLS_ACADEMICO,
    "sexo_equidad", *F.ADMISION_P47,       # P47: admission test and min-max scores; never model inputs by default
]
# ``episodio_especialidad_id`` is the audit trail of the Plan Comun link: it is decided with the future, so it is never a feature.
LABEL_COLS = {"seguimiento_max", "tiempo", "causa", "salida_tipo", "salida_a_otro_programa", "tiempo_titulacion",
              "episodio_especialidad_id"}


# ---------------------------------------------------------------------------------------------
# population and per-episode facts
# ---------------------------------------------------------------------------------------------
def poblacion_t3(episodios: pd.DataFrame, cohorte_min: int = R3.COHORTE_MIN) -> Tuple[pd.DataFrame, int]:
    """T1 population restricted to the cohorts of the window and without the exchange programs (D47).

    Second value = episodes dropped for an earlier cohort (counted before the exchange exclusion, as in D40).
    ``cohorte_min`` only changes for the projection of the current students, which also covers the older cohorts.
    """
    pop = F.poblacion(episodios)
    anio = pop["periodo_admision"].str.slice(0, 4).astype(int)
    keep = anio >= cohorte_min
    kept = pop.loc[keep]
    return kept.loc[~kept["cod_programa"].isin(R3.PROGRAMAS_INTERCAMBIO)].copy(), int((~keep).sum())


def episodios_intercambio(episodios: pd.DataFrame) -> pd.DataFrame:
    """Episodes that the exchange exclusion removes: exchange programs inside the T1 population of the window."""
    pop = F.poblacion(episodios)
    keep = pop["periodo_admision"].str.slice(0, 4).astype(int) >= R3.COHORTE_MIN
    return pop.loc[keep & pop["cod_programa"].isin(R3.PROGRAMAS_INTERCAMBIO)].copy()


def _ordinal_slot(periodo: pd.Series) -> np.ndarray:
    """Vectorized ``rules_t3.ordinal_periodo`` (equality is tested on a grid); NaN where malformed."""
    text = periodo.astype("string")
    valido = text.str.fullmatch(r"\d{6}").fillna(False).to_numpy(bool)
    anio = pd.to_numeric(text.str.slice(0, 4), errors="coerce").to_numpy("float64")
    sufijo = text.str.slice(4, 6).fillna("00").to_numpy(str)
    ordinal = np.where(sufijo <= "10", anio * 2, np.where(sufijo <= "20", anio * 2 + 1, (anio + 1) * 2))
    return np.where(valido, ordinal, np.nan)


def _periodos_por_episodio(estados: pd.DataFrame) -> pd.DataFrame:
    """First and last period (any suffix) of the states of each episode, with their slot ordinals."""
    e = F._estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna() & e["periodo"].notna()]
    g = e.assign(episodio_id=e["episodio_id"].astype("int64")).groupby("episodio_id")["periodo"].agg(["min", "max"])
    g = g.rename(columns={"min": "primer_periodo", "max": "ultimo_periodo"})
    g["ord_primer"] = _ordinal_slot(g["primer_periodo"])
    g["ord_ultimo"] = _ordinal_slot(g["ultimo_periodo"])
    return g


COLS_VINCULO = ["episodio_id", "episodio_esp", "cod_programa_esp", "catalogo_esp", "periodo_admision_esp",
                "cod_admision_esp", "inicio_esp"]


def vincular_plan_comun(episodios: pd.DataFrame, estados: pd.DataFrame, pop: pd.DataFrame = None) -> pd.DataFrame:
    """Link each Ingenieria Civil Plan Comun episode of the population to its specialty episode (D47).

    The specialty is the FIRST later episode of the same person in an undergraduate Ingenieria Civil specialty program
    (``rules_t3.ESPECIALIDADES_ING_CIVIL``; later = its first state is after the first state of the Plan Comun episode)
    and must start (first state) at most ``VENTANA_VINCULO_PERIODOS`` regular periods after the last period of the Plan
    Comun episode. Neither the admission code (ES) nor the admission period is required. A specialty is linked to one
    Plan Comun episode only (the closest, i.e. latest, one). Returns one row per link (``COLS_VINCULO``); the
    candidates whose first later specialty falls outside the window are counted in ``.attrs['fuera_de_ventana']``.
    """
    if pop is None:
        pop, _ = poblacion_t3(episodios)
    vacio = pd.DataFrame({c: pd.Series(dtype="int64" if c in ("episodio_id", "episodio_esp") else "object")
                          for c in COLS_VINCULO})
    vacio.attrs["fuera_de_ventana"] = 0
    pc = pop.loc[pop["cod_programa"].isin(R3.PLAN_COMUN_ING_CIVIL), ["episodio_id", "persona_key"]]
    esp = episodios.loc[(episodios["id_nivel"] == R.NIVEL_PREGRADO)
                        & episodios["cod_programa"].isin(R3.ESPECIALIDADES_ING_CIVIL),
                        ["episodio_id", "persona_key", "cod_programa", "catalogo_inicial", "periodo_admision",
                         "cod_admision"]]
    if pc.empty or esp.empty:
        return vacio
    per = _periodos_por_episodio(estados)
    pc = pc.join(per, on="episodio_id", how="inner")
    esp = esp.join(per, on="episodio_id", how="inner")
    m = pc.merge(esp, on="persona_key", suffixes=("", "_e"))
    m = m.loc[(m["episodio_id_e"] != m["episodio_id"]) & (m["ord_primer_e"] > m["ord_primer"])]
    m = m.sort_values(["episodio_id", "ord_primer_e", "episodio_id_e"]).drop_duplicates("episodio_id")
    dentro = (m["ord_primer_e"] - m["ord_ultimo"]) <= R3.VENTANA_VINCULO_PERIODOS
    out = m.loc[dentro].copy()
    # a specialty belongs to one Plan Comun episode: the one that starts last
    out = out.sort_values(["episodio_id_e", "ord_primer", "episodio_id"]).drop_duplicates("episodio_id_e", keep="last")
    out = out.rename(columns={"episodio_id_e": "episodio_esp", "cod_programa": "cod_programa_esp",
                              "catalogo_inicial": "catalogo_esp", "periodo_admision": "periodo_admision_esp",
                              "cod_admision": "cod_admision_esp", "primer_periodo_e": "inicio_esp"})
    res = out[COLS_VINCULO].sort_values("episodio_id").reset_index(drop=True)
    res["episodio_id"] = res["episodio_id"].astype("int64")
    res["episodio_esp"] = res["episodio_esp"].astype("int64")
    res.attrs["fuera_de_ventana"] = int((~dentro).sum())
    return res


def _remapear(ids: pd.Series, mapa: Dict[int, int]) -> pd.Series:
    """Episode ids with the absorbed specialties replaced by their Plan Comun id (missing ids stay missing)."""
    nuevo = ids.astype("Int64").map(mapa).astype("Int64")
    return nuevo.where(nuevo.notna(), ids.astype("Int64"))


class Unidades:
    """The units of T3 and the facts re-keyed onto them (``unidades_t3``)."""

    def __init__(self, pop, estados, egreso, intentos, vinculos, n_previas, pop_sin_union):
        self.pop, self.estados, self.egreso, self.intentos = pop, estados, egreso, intentos
        self.vinculos, self.n_previas, self.pop_sin_union = vinculos, n_previas, pop_sin_union


def unidades_t3(episodios: pd.DataFrame, estados: pd.DataFrame, egreso_titulacion: pd.DataFrame,
                intentos: pd.DataFrame = None, cohorte_min: int = R3.COHORTE_MIN) -> Unidades:
    """Population of units after the exchange exclusion and the Plan Comun merge, with the facts re-keyed.

    * A linked specialty episode is NOT a unit: its states, attempts and titulacion rows are re-keyed onto the Plan
      Comun episode (``episodio_origen`` keeps the original episode of every state).
    * The exit and egress states (and titulacion rows) of a linked Plan Comun episode are dropped: its exit is the
      change of program, so the event and the censoring of the trajectory come from the specialty only.
    * A Plan Comun episode without a link is left exactly as it was (an exit, as before).
    """
    pop0, n_previas = poblacion_t3(episodios, cohorte_min)
    vinc = vincular_plan_comun(episodios, estados, pop0)
    mapa = dict(zip(vinc["episodio_esp"].astype(int), vinc["episodio_id"].astype(int)))
    pop = pop0.loc[~pop0["episodio_id"].isin(vinc["episodio_esp"])].copy()
    pop = pop.merge(vinc, on="episodio_id", how="left")
    pc_unidos = set(vinc["episodio_id"].astype(int))

    e = estados.copy()
    e["episodio_origen"] = e["episodio_id"].astype("Int64")
    e["episodio_id"] = _remapear(e["episodio_id"], mapa)
    clase = F.clase_estado(e["cod_estado"])
    descartar = e["episodio_origen"].isin(pc_unidos) & clase.isin(["salida", "egreso_titulacion"])
    e = e.loc[~descartar].reset_index(drop=True)

    t = egreso_titulacion.copy()
    t = t.loc[~t["episodio_id"].isin(pc_unidos)].copy()
    t["episodio_id"] = t["episodio_id"].map(mapa).where(t["episodio_id"].isin(list(mapa)), t["episodio_id"])
    it = None
    if intentos is not None:
        it = intentos.copy()
        it["episodio_id"] = it["episodio_id"].map(mapa).fillna(it["episodio_id"]).astype(intentos["episodio_id"].dtype)
    return Unidades(pop, e, t.reset_index(drop=True), it, vinc, n_previas, pop0)


def intentos_para_features(intentos: pd.DataFrame) -> pd.DataFrame:
    """P58: attempts of the periods without recorded failures stop being 'evaluated' (they keep their credits)."""
    out = intentos.copy()
    sin = out["periodo"].astype(str).isin(R3.PERIODOS_SIN_REPROBACION)
    out["es_intento_evaluado"] = out["es_intento_evaluado"].astype(bool) & ~sin
    return out


def _ordinal_regular(periodo: pd.Series) -> np.ndarray:
    text = periodo.astype("string")
    anio = pd.to_numeric(text.str.slice(0, 4), errors="coerce").to_numpy("float64")
    return anio * 2 + (text.str.slice(4, 6) == "20").fillna(False).to_numpy(float)


def hechos_episodio(pop: pd.DataFrame, estados: pd.DataFrame, egreso_titulacion: pd.DataFrame, latest: str) -> pd.DataFrame:
    """One row per episode: the slots of its egress, exit and activity facts (see ``rules_t3.resolver_evento``)."""
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    h = pd.DataFrame(index=base.index)
    h.index.name = "episodio_id"
    h["base"] = base
    h["t_max"] = [R3.slot_cierre(p, latest) for p in pop["periodo_admision"]]
    e = F._estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna()].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    e = e.loc[e["episodio_id"].isin(base.index)].copy()
    e["slot"] = F.slot_vectorizado(e["periodo"], e["episodio_id"].map(base))
    e = e.loc[e["slot"].notna()]
    reg = F.es_regular(e["periodo"])
    egreso = e.loc[e["clase"] == "egreso_titulacion"]
    t_tit = egreso.loc[egreso["cod_estado"] == "U"].groupby("episodio_id")["slot"].min()

    tit = egreso_titulacion.loc[egreso_titulacion["episodio_id"].notna()].copy()
    tit["episodio_id"] = tit["episodio_id"].astype("int64")
    tit = tit.loc[tit["episodio_id"].isin(base.index)].copy()
    tit["slot"] = F.slot_vectorizado(tit["periodo"], tit["episodio_id"].map(base))
    tit = tit.loc[tit["slot"].notna()]

    h["t_egreso_estado"] = egreso.groupby("episodio_id")["slot"].min()
    h["t_egreso_fila"] = tit.groupby("episodio_id")["slot"].min()
    h["t_titulado_estado"] = t_tit
    h["t_egreso"] = h[["t_egreso_estado", "t_egreso_fila"]].min(axis=1)
    h["t_titulacion"] = h[["t_titulado_estado", "t_egreso_fila"]].min(axis=1)
    mat = e.loc[e["clase"].isin(F.MATRICULA) & reg]
    h["ultima_matricula"] = mat.groupby("episodio_id")["slot"].max()
    act = e.loc[(e["clase"].isin(F.MATRICULA) & reg) | (e["clase"] == "interrupcion")]
    h["ultima_actividad"] = act.groupby("episodio_id")["slot"].max()
    sal = e.loc[e["clase"] == "salida", ["episodio_id", "slot"]].merge(
        h[["ultima_matricula"]], left_on="episodio_id", right_index=True, how="left")
    sal = sal.loc[sal["slot"] >= sal["ultima_matricula"].fillna(-np.inf)]
    h["t_salida_def"] = sal.groupby("episodio_id")["slot"].min()
    return h


def consistencia_fuentes(pop: pd.DataFrame, estados: pd.DataFrame, egreso_titulacion: pd.DataFrame, latest: str) -> Dict[str, int]:
    """Aggregate agreement between the egress/titulation STATES and the ``titulacion`` table (population episodes)."""
    h = hechos_episodio(pop, estados, egreso_titulacion, latest)
    est, fila, u = h["t_egreso_estado"].notna(), h["t_egreso_fila"].notna(), h["t_titulado_estado"].notna()
    both = est & fila
    d = (h["t_egreso_fila"] - h["t_egreso_estado"])[both]
    du = (h["t_egreso_fila"] - h["t_titulado_estado"])[fila & u]
    return {
        "episodios": int(len(h)), "con_estado_egreso_titulacion": int(est.sum()), "con_fila_titulacion": int(fila.sum()),
        "ambos": int(both.sum()), "solo_estado": int((est & ~fila).sum()), "solo_fila": int((fila & ~est).sum()),
        "con_estado_titulado": int(u.sum()), "estado_titulado_sin_fila": int((u & ~fila).sum()),
        "fila_sin_estado_titulado": int((fila & ~u).sum()),
        "fila_antes_que_primer_estado": int((d < 0).sum()), "fila_mismo_slot_que_primer_estado": int((d == 0).sum()),
        "fila_despues_del_primer_estado": int((d > 0).sum()),
        "fila_un_slot_antes_del_estado_titulado": int((du == -1).sum()), "fila_mismo_slot_del_estado_titulado": int((du == 0).sum()),
        "fila_otro_desfase_del_estado_titulado": int(((du != 0) & (du != -1)).sum()),
        "salida_definitiva_antes_del_egreso": int((h["t_salida_def"] < h["t_egreso"]).sum()),
        "egreso_posterior_al_cierre": int((h["t_egreso"] > h["t_max"]).sum()),
        "filas_titulacion_sin_episodio": int(egreso_titulacion["episodio_id"].isna().sum()),
    }


def resolver_eventos(h: pd.DataFrame, ventana: int = R3.VENTANA_SLOTS) -> pd.DataFrame:
    """Vectorized ``rules_t3.resolver_evento`` (equality is tested on a grid)."""
    t_eg, t_sal, t_act = (h[c].to_numpy("float64") for c in ("t_egreso", "t_salida_def", "ultima_actividad"))
    t_max = h["t_max"].to_numpy("float64")
    limite = np.minimum(t_max, ventana)
    eg_ok = ~np.isnan(t_eg) & (t_eg <= limite)
    sal_exp = ~np.isnan(t_sal)
    aus = ~sal_exp & np.isnan(t_eg) & ~np.isnan(t_act) & (t_act <= t_max - R3.AUSENCIA_PERIODOS)
    t_x = np.where(sal_exp, t_sal, np.where(aus, t_act + 1, np.nan))
    x_ok = ~eg_ok & ~np.isnan(t_x) & (t_x <= limite)
    out = pd.DataFrame(index=h.index)
    out["tiempo"] = np.where(eg_ok, t_eg, np.where(x_ok, t_x, limite)).astype("int64")
    out["causa"] = np.where(eg_ok, R3.EGRESO, np.where(x_ok, R3.SALIDA, R3.CENSURA)).astype("int64")
    tipo = np.where(x_ok & sal_exp, R3.SALIDA_EXPLICITA, np.where(x_ok & aus, R3.SALIDA_AUSENCIA, None))
    out["salida_tipo"] = pd.Series(tipo, index=h.index, dtype="object")
    t_tit = h["t_titulacion"].to_numpy("float64")
    out["tiempo_titulacion"] = pd.array(np.where(~np.isnan(t_tit) & (t_tit <= limite), t_tit, np.nan), dtype="Int64")
    out["seguimiento_max"] = h["t_max"].astype("int64")
    return out


def salida_a_otro_programa(pop: pd.DataFrame, estados: pd.DataFrame, eventos: pd.DataFrame) -> pd.Series:
    """For episodes that exit: does the same person have an enrolled state in ANOTHER episode at or after the exit?

    Descriptive only (a transfer between programs is an exit of the episode but not of the university).
    """
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    sal = eventos.loc[eventos["causa"] == R3.SALIDA].copy()
    sal["ord_salida"] = base.reindex(sal.index).to_numpy() + sal["tiempo"].to_numpy() - 1
    sal["persona_key"] = pop.set_index("episodio_id")["persona_key"].reindex(sal.index).to_numpy()
    e = F._estados_utiles(estados)
    e = e.loc[e["clase"].isin(F.MATRICULA) & F.es_regular(e["periodo"]) & e["episodio_id"].notna()].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    e["ord_estado"] = _ordinal_regular(e["periodo"])
    m = sal.reset_index()[["episodio_id", "persona_key", "ord_salida"]].merge(
        e[["persona_key", "episodio_id", "ord_estado"]], on="persona_key", suffixes=("", "_otro"))
    m = m.loc[(m["episodio_id"] != m["episodio_id_otro"]) & (m["ord_estado"] >= m["ord_salida"])]
    otro = pd.Series(sal.index.isin(m["episodio_id"].unique()), index=sal.index)
    return otro.reindex(eventos.index)


# ---------------------------------------------------------------------------------------------
# cuts, eligibility
# ---------------------------------------------------------------------------------------------
def construir_cortes_t3(
    pop: pd.DataFrame, h: pd.DataFrame, eventos: pd.DataFrame, estados: pd.DataFrame, ks: Sequence[int] = R3.KS
):
    """Eligible (episode, k) rows with their label, plus the funnel counts per k."""
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    e = F._estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna()].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    e = e.loc[e["episodio_id"].isin(base.index)].copy()
    e["slot"] = F.slot_vectorizado(e["periodo"], e["episodio_id"].map(base))
    reg = e.loc[F.es_regular(e["periodo"]) & e["slot"].notna()].copy()
    reg["slot"] = reg["slot"].astype("int64")
    enrolled = reg.loc[reg["clase"].isin(F.MATRICULA), ["episodio_id", "slot"]].drop_duplicates()
    enrolled["_inscrito"] = True
    salida = reg.loc[reg["clase"] == "salida", ["episodio_id", "slot"]].drop_duplicates()
    salida["_salida"] = True
    resumen: List[Dict[str, int]] = []
    out = []
    for k in ks:
        c = pop[["episodio_id", "persona_key", "cod_programa", "periodo_admision"]].copy()
        c["k"] = k
        c["slot_corte"] = max(k, 1)           # k = 0: enrolled in the admission semester, nothing else known
        n_pop = len(c)
        c = c.merge(enrolled, left_on=["episodio_id", "slot_corte"], right_on=["episodio_id", "slot"], how="left")
        n_sin_matricula = int(c["_inscrito"].isna().sum())
        c = c.loc[c["_inscrito"].notna()].drop(columns=["slot", "_inscrito"])
        if k >= 1:
            c = c.merge(salida, left_on=["episodio_id", "slot_corte"], right_on=["episodio_id", "slot"], how="left")
            ya_salio = c["_salida"].notna().to_numpy()
            c = c.loc[~ya_salio].drop(columns=["slot", "_salida"])
            n_salida = int(ya_salio.sum())
            t_eg = h["t_egreso"].reindex(c["episodio_id"]).to_numpy()
            ya = ~np.isnan(t_eg) & (t_eg <= k)
            c = c.loc[~ya]
            n_ya = int(ya.sum())
        else:
            n_salida = n_ya = 0
        t_max = h["t_max"].reindex(c["episodio_id"]).to_numpy()
        sin_seg = t_max < k + 1
        c = c.loc[~sin_seg].drop(columns=["slot_corte"])
        ev = eventos.reindex(c["episodio_id"])
        for col in ("seguimiento_max", "tiempo", "causa", "salida_tipo", "salida_a_otro_programa", "tiempo_titulacion"):
            c[col] = ev[col].to_numpy()
        c["cohorte_anio"] = c["periodo_admision"].str.slice(0, 4).astype(int)
        c["split"] = c["cohorte_anio"].map(R3.split_cohorte)
        out.append(c)
        resumen.append({"k": k, "poblacion": n_pop, "sin_matricula_en_corte": n_sin_matricula,
                        "salida_en_corte": n_salida, "ya_egresado_o_titulado": n_ya,
                        "sin_seguimiento": int(sin_seg.sum()), "elegibles": len(c)})
    return pd.concat(out, ignore_index=True), resumen


# ---------------------------------------------------------------------------------------------
# program features (static) and academic features by cut
# ---------------------------------------------------------------------------------------------
def features_programa(pop: pd.DataFrame, malla: pd.DataFrame, prog_cat: pd.DataFrame, ks: Sequence[int]) -> pd.DataFrame:
    """Nominal duration and credit expectations from the malla of the episode's initial catalog."""
    m = malla.loc[malla["semestre"].notna()].copy()
    m["creditos"] = pd.to_numeric(m["creditos"], errors="coerce").fillna(0.0)
    g = m.groupby(["cod_programa", "catalogo"])
    t = pd.DataFrame({"creditos_malla_total": g["creditos"].sum(), "dur_malla": g["semestre"].max()})
    for k in ks:
        if k >= 1:
            t[f"_ce{k}"] = m.loc[m["semestre"] <= k].groupby(["cod_programa", "catalogo"])["creditos"].sum()
    t = t.reset_index()
    t["malla_conocida"] = True
    pc = prog_cat[["cod_programa", "catalogo", "duracion"]].drop_duplicates(["cod_programa", "catalogo"])
    x = pop[["episodio_id", "cod_programa", "catalogo_inicial"]].merge(
        t, left_on=["cod_programa", "catalogo_inicial"], right_on=["cod_programa", "catalogo"], how="left").drop(
        columns="catalogo")
    x = x.merge(pc, left_on=["cod_programa", "catalogo_inicial"], right_on=["cod_programa", "catalogo"],
                how="left").drop(columns="catalogo")
    dur = pd.to_numeric(x["duracion"], errors="coerce")
    x["duracion_nominal"] = dur.where(dur.notna(), x["dur_malla"]).astype("float64")
    x["malla_conocida"] = x["malla_conocida"].eq(True)
    for k in ks:
        if k >= 1:
            x[f"_ce{k}"] = x[f"_ce{k}"].fillna(0.0).where(x["malla_conocida"])
    return x.drop(columns=["cod_programa", "catalogo_inicial", "duracion", "dur_malla"])


def n_sem_sin_reprobacion(periodo_admision: pd.Series, k: pd.Series) -> np.ndarray:
    """Number of slots ``1..k`` that are periods without recorded failures (P58)."""
    base = periodo_admision.map(lambda p: base_ordinal(p) if isinstance(p, str) else None).to_numpy("float64")
    kk = k.to_numpy("int64")
    out = np.zeros(len(kk), dtype="int64")
    for j in range(1, int(kk.max(initial=0)) + 1):
        periodo = [R.ordinal_a_periodo(int(b) + j - 1) if b == b else None for b in base]
        out += np.array([(p in R3.PERIODOS_SIN_REPROBACION) and j <= kj for p, kj in zip(periodo, kk)], dtype="int64")
    return out


def features_academicas(
    cortes: pd.DataFrame, pop: pd.DataFrame, intentos: pd.DataFrame, estados: pd.DataFrame, ks: Sequence[int]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Academic aggregates at each cut (T1 construction, P58-aware) and the per-semester table for the GRU."""
    sem = F.tabla_semestres(pop, intentos_para_features(intentos), estados, max(ks))
    c = cortes[["episodio_id", "k", "periodo_admision"]].copy()
    c["periodo_corte"] = [R.corte_periodo(p, k) if k >= 1 else "000000" for p, k in zip(c["periodo_admision"], c["k"])]
    acad = F.features_corte(c, sem, estados)
    if "episodio_origen" in estados.columns:
        acad = acad.drop(columns="cambios_catalogo").merge(_cambios_catalogo(c, estados), on=["episodio_id", "k"], how="left")
        acad["cambios_catalogo"] = acad["cambios_catalogo"].fillna(0)
    acad["n_sem_sin_reprobacion"] = n_sem_sin_reprobacion(c["periodo_admision"], c["k"])
    return acad, sem


def _cambios_catalogo(cortes: pd.DataFrame, estados: pd.DataFrame) -> pd.DataFrame:
    """Catalog changes up to the cut counted WITHIN each original episode: moving from Plan Comun to its specialty is a
    change of program, not a change of catalog."""
    e = F._estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna() & e["catalogo"].notna(), ["episodio_id", "episodio_origen", "periodo", "catalogo"]]
    e = cortes[["episodio_id", "k", "periodo_corte"]].merge(e.assign(episodio_id=e["episodio_id"].astype("int64")),
                                                            on="episodio_id")
    e = e.loc[e["periodo"] <= e["periodo_corte"]]
    n = e.groupby(["episodio_id", "k", "episodio_origen"])["catalogo"].nunique().sub(1).clip(lower=0)
    return n.groupby(level=["episodio_id", "k"]).sum().rename("cambios_catalogo").reset_index()


def _elegibles_por_k(pop_x: pd.DataFrame, estados: pd.DataFrame, egreso: pd.DataFrame, latest: str,
                     ks: Sequence[int]) -> Dict[int, int]:
    """Eligible rows per cut of a set of episodes treated as separate units (memo counts of the funnel)."""
    if pop_x.empty:
        return {int(k): 0 for k in ks}
    h = hechos_episodio(pop_x, estados, egreso, latest)
    ev = resolver_eventos(h)
    ev["salida_a_otro_programa"] = np.nan
    _, emb = construir_cortes_t3(pop_x, h, ev, estados, ks)
    return {int(r["k"]): int(r["elegibles"]) for r in emb}


def offset_especialidad(pop: pd.DataFrame) -> np.ndarray:
    """Regular semesters between the Plan Comun admission and the specialty admission (0 when equal or unknown)."""
    a = F.base_ordinales(pop["periodo_admision"]).to_numpy("float64")
    b = F.base_ordinales(pop["periodo_admision_esp"]).to_numpy("float64")
    return np.nan_to_num(np.maximum(b - a, 0.0), nan=0.0)


def constante_duracion_plan_comun(pop: pd.DataFrame, prog_pc: pd.DataFrame, prog_esp: pd.DataFrame) -> float:
    """Constant added to the Plan Comun nominal duration while the specialty is unknown (leakage-free).

    Median, over the TRAIN-cohort linked trajectories only, of (specialty offset + specialty nominal duration) minus the
    Plan Comun nominal duration; i.e. ``duracion_nominal`` of a Plan Comun trajectory before the specialty is known is
    the typical total nominal duration of the trajectories of the training cohorts.
    """
    if prog_esp is None or prog_esp.empty:
        return 0.0
    d = pd.Series(offset_especialidad(pop), index=pop["episodio_id"].to_numpy())
    train = pop.loc[pop["episodio_esp"].notna() & (pop["cohorte_anio_"] <= R3.TRAIN_HASTA), "episodio_id"].to_numpy()
    dur_esp = prog_esp.set_index("episodio_id")["duracion_nominal"].reindex(train)
    dur_pc = prog_pc.set_index("episodio_id")["duracion_nominal"].reindex(train)
    valor = (d.reindex(train) + dur_esp - dur_pc).dropna()
    return float(valor.median()) if len(valor) else 0.0


def programa_vigente(snap: pd.DataFrame, pop: pd.DataFrame, prog_pc: pd.DataFrame, prog_esp: pd.DataFrame,
                     constante: float) -> pd.DataFrame:
    """Program facts of each (unit, k) for the program IN FORCE at the cut.

    Plan Comun until the first state of the specialty is recorded (``periodo <= corte``; never at ``k = 0``), the
    specialty afterwards, with its semesters counted from its own admission (offset ``d``). Nothing about a specialty
    that starts after the cut is used.
    """
    eid = snap["episodio_id"].to_numpy()
    k = snap["k"].to_numpy("int64")
    pu = pop.set_index("episodio_id")
    pc = prog_pc.set_index("episodio_id")
    conocida = snap["especialidad_conocida_al_corte"].to_numpy(bool)
    d = pd.Series(offset_especialidad(pop), index=pop["episodio_id"].to_numpy()).reindex(eid).to_numpy("float64")
    es_pc = snap["trayectoria_plan_comun"].to_numpy(bool)
    out = pd.DataFrame(index=snap.index)
    dur_pc = pc["duracion_nominal"].reindex(eid).to_numpy("float64")
    tot_pc = pc["creditos_malla_total"].reindex(eid).to_numpy("float64")
    mc_pc = pc["malla_conocida"].reindex(eid).eq(True).to_numpy(bool)
    if prog_esp is not None and not prog_esp.empty:
        pe = prog_esp.set_index("episodio_id")
        dur_esp = pe["duracion_nominal"].reindex(eid).to_numpy("float64")
        tot_esp = pe["creditos_malla_total"].reindex(eid).to_numpy("float64")
        mc_esp = pe["malla_conocida"].reindex(eid).eq(True).to_numpy(bool)
    else:
        pe = None
        dur_esp = tot_esp = np.full(len(snap), np.nan)
        mc_esp = np.zeros(len(snap), bool)
    out["duracion_nominal"] = np.where(conocida, d + dur_esp, np.where(es_pc, dur_pc + constante, dur_pc))
    out["creditos_malla_total"] = np.where(conocida, tot_esp, tot_pc)
    out["malla_conocida"] = np.where(conocida, mc_esp, mc_pc)
    ce = np.full(len(snap), np.nan)
    for kk in sorted(set(k.tolist())):
        if kk < 1:
            continue
        m = (k == kk) & ~conocida
        if m.any():
            ce[m] = pc[f"_ce{kk}"].reindex(eid[m]).to_numpy("float64")
    if pe is not None:
        sem_esp = (k - d).astype("int64")
        for s in sorted(set(sem_esp[conocida].tolist())):
            m = conocida & (sem_esp == s)
            ce[m] = pe[f"_ce{s}"].reindex(eid[m]).to_numpy("float64") if f"_ce{s}" in pe.columns else np.nan
    out["creditos_esperados"] = ce
    cod_esp = pu["cod_programa_esp"].reindex(eid).to_numpy(object)
    out["cod_programa"] = np.where(conocida, cod_esp, snap["cod_programa"].to_numpy(object))
    return out


def construir_snapshot_t3(
    episodios: pd.DataFrame,
    estados: pd.DataFrame,
    intentos: pd.DataFrame,
    via: pd.DataFrame,
    egreso_titulacion: pd.DataFrame,
    malla: pd.DataFrame,
    prog_cat: pd.DataFrame,
    latest: str,
    ks: Sequence[int] = R3.KS,
):
    """Full snapshot: ``(snapshot_t3, snapshot_t3_semestre, embudo)``."""
    u = unidades_t3(episodios, estados, egreso_titulacion, intentos)
    pop, est, tit, it, vinc = u.pop, u.estados, u.egreso, u.intentos, u.vinculos
    pop["cohorte_anio_"] = pop["periodo_admision"].str.slice(0, 4).astype(int)
    h = hechos_episodio(pop, est, tit, latest)
    ev = resolver_eventos(h)
    ev["salida_a_otro_programa"] = salida_a_otro_programa(pop, est, ev)
    cortes, embudo = construir_cortes_t3(pop, h, ev, est, ks)
    acad, sem = features_academicas(cortes, pop, it, est, ks)
    adm = F.features_admision(pop, via)
    meta = pop[["episodio_id", "cod_admision", "sede", "tipo_qualitas", "sexo"]].copy()
    meta["via_clase"] = meta["tipo_qualitas"].map(lambda q: R.via_clase(q if isinstance(q, str) else None))
    meta = meta.rename(columns={"sexo": "sexo_equidad"}).drop(columns=["tipo_qualitas"])

    # program features: Plan Comun / ordinary unit (static) and, for linked trajectories, the specialty
    kmax = max(ks)
    prog_pc = features_programa(pop, malla, prog_cat, ks)
    vinculados = pop.loc[pop["episodio_esp"].notna()]
    esp_pop = vinculados[["episodio_id"]].assign(cod_programa=vinculados["cod_programa_esp"].to_numpy(),
                                                 catalogo_inicial=vinculados["catalogo_esp"].to_numpy())
    prog_esp = features_programa(esp_pop, malla, prog_cat, range(1, kmax + 1)) if len(esp_pop) else None
    constante = constante_duracion_plan_comun(pop, prog_pc, prog_esp)

    snap = (cortes.merge(acad, on=["episodio_id", "k"], how="left")
            .merge(adm, on="episodio_id", how="left").merge(meta, on="episodio_id", how="left"))
    unid = pop.set_index("episodio_id")
    esp_id = unid["episodio_esp"].reindex(snap["episodio_id"]).to_numpy()
    inicio = unid["inicio_esp"].reindex(snap["episodio_id"]).to_numpy(object)
    corte = np.array([R.corte_periodo(p, int(k)) if k >= 1 else None
                      for p, k in zip(snap["periodo_admision"], snap["k"])], dtype=object)
    conocida = np.array([bool(pd.notna(e) and c is not None and isinstance(i, str) and i <= c)
                         for e, c, i in zip(esp_id, corte, inicio)], dtype=bool)
    snap["trayectoria_plan_comun"] = snap["cod_programa"].isin(R3.PLAN_COMUN_ING_CIVIL).to_numpy()
    snap["especialidad_conocida_al_corte"] = conocida
    snap["episodio_especialidad_id"] = pd.array(esp_id, dtype="Int64")
    vig = programa_vigente(snap, pop, prog_pc, prog_esp, constante)
    for col in vig.columns:
        snap[col] = vig[col].to_numpy()
    snap["avance_malla"] = snap["creditos_aprobados"] / snap["creditos_esperados"].where(snap["creditos_esperados"] > 0)
    snap["fraccion_malla"] = snap["creditos_aprobados"] / snap["creditos_malla_total"].where(
        snap["creditos_malla_total"] > 0)
    snap["con_postulacion"] = snap["con_postulacion"].fillna(False).astype(bool)
    snap["malla_conocida"] = snap["malla_conocida"].eq(True)
    snap["sede"] = snap["sede"].map(lambda s: None if pd.isna(s) else str(int(s)) if not isinstance(s, str) else s)

    # funnel memo counts of the population change (D47)
    interc = episodios_intercambio(episodios)
    absorbidas = u.pop_sin_union.loc[u.pop_sin_union["episodio_id"].isin(vinc["episodio_esp"])]
    n_interc_k = _elegibles_por_k(interc, estados, egreso_titulacion, latest, ks)
    n_abs_k = _elegibles_por_k(absorbidas, estados, egreso_titulacion, latest, ks)
    es_pc = pop["cod_programa"].isin(R3.PLAN_COMUN_ING_CIVIL)
    mismo_per = vinc["periodo_admision_esp"].to_numpy() == pop.set_index("episodio_id")["periodo_admision"].reindex(
        vinc["episodio_id"]).to_numpy()
    es_ = (vinc["cod_admision_esp"] == "ES").to_numpy()
    glob = {
        "intercambio_excluidos": int(len(interc)), "plan_comun_episodios": int(es_pc.sum()),
        "plan_comun_unidos": int(len(vinc)), "plan_comun_sin_continuacion": int(es_pc.sum()) - int(len(vinc)),
        "plan_comun_fuera_de_ventana": int(vinc.attrs.get("fuera_de_ventana", 0)),
        "especialidades_absorbidas": int(len(vinc)), "especialidades_absorbidas_en_poblacion": int(len(absorbidas)),
        "unidos_es": int(es_.sum()), "unidos_mismo_periodo": int(mismo_per.sum()),
        "unidos_es_mismo_periodo": int((es_ & mismo_per).sum()),
        "constante_duracion_plan_comun": float(constante),
    }
    for r in embudo:
        r["cohortes_anteriores_excluidas"] = u.n_previas
        k = r["k"]
        r.update(glob)
        r["intercambio_elegibles_excluidos"] = n_interc_k[k]
        r["especialidades_absorbidas_elegibles"] = n_abs_k[k]
        d = snap.loc[snap["k"] == k]
        r["plan_comun_elegibles"] = int(d["trayectoria_plan_comun"].sum())
        r["plan_comun_unidos_elegibles"] = int(d["episodio_especialidad_id"].notna().sum())
    sem = sem.loc[sem["episodio_id"].isin(snap["episodio_id"].unique())].copy()
    return snap[SNAPSHOT_COLS_T3].copy(), sem, embudo
