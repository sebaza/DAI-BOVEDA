"""Point-in-time construction of the T6 snapshot ("matricula en postgrado UCN despues del egreso",
docs/12_benchmark_t6.md) with pandas.

One row per T3 trajectory (D47: exchange out, Plan Comun merged with its specialty) that reached egreso in a closed
regular period; the cut is the egreso semester (``k`` = its slot). Every feature is a fact of the slots ``<= k`` (the T3
helpers: admission profile, academic record robust to P58, program facts in force at the cut) plus the time to egreso
against the nominal duration and whether a titulacion ``U`` is known by the cut. The label (time to the first enrolled
UCN postgrado semester, censored at the last closed period) comes from ``neural_core.matricula_postgrado`` and never feeds
a feature.

Leakage guards, all covered by ``tests/unit/test_snapshot_t6.py``:
* the features are T3 features at ``k`` (slots ``<= k``); the postgrado history is label side only;
* a person already enrolled in a postgrado program at or before the egreso semester is excluded and counted (D65);
* the year of egreso only defines the split and the subgroup tables; ``sexo`` is for fairness; neither is a feature.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from . import features as F
from . import features_t3 as F3
from . import rules as R
from . import rules_t3 as R3
from . import rules_t6 as R6
from ..normalize.postgrado import ordinal_estado_postgrado

KEYS = ["episodio_id", "persona_key", "cod_programa", "periodo_admision", "cohorte_anio", "anio_egreso", "split"]
LABELS = ["seguimiento", "tiempo", "evento", "tiempo_cualquier_fila", "evento_cualquier_fila",
          # P77: the same event read from the postgrado state source (complete since 2008) with the program level
          "previo_estados", "evento_estados", "tiempo_estados", "nivel_estados"]
AUDIT = ["episodio_especialidad_id"]       # the Plan Comun link is decided with the future: never a feature
NUEVAS = ["semestres_a_egreso", "exceso_duracion", "razon_duracion", "titulado_al_corte"]
FEATURE_COLS_T6: List[str] = [*F3.FEATURE_COLS_CAT[1:], *[c for c in F3.FEATURE_COLS_ADMISION if c != "cohorte_anio"],
                              *F3.FEATURE_COLS_ACADEMICO, *NUEVAS]
LABEL_COLS_T6 = set(LABELS + AUDIT)
SNAPSHOT_COLS_T6: List[str] = KEYS + LABELS + AUDIT + FEATURE_COLS_T6 + ["sexo_equidad", *F.ADMISION_P47]


# ---------------------------------------------------------------------------------------------
# vectorized state (mirror of rules_t6.resolver_evento; equality is tested on a grid)
# ---------------------------------------------------------------------------------------------
def resolver_estados(d: pd.DataFrame, ord_cierre: int) -> pd.DataFrame:
    """Vectorized ``rules_t6.resolver_evento``: columns ``ord_egreso`` and ``ord_primera`` (NaN = none)."""
    eg = d["ord_egreso"].to_numpy("float64")
    pr = d["ord_primera"].to_numpy("float64")
    hay = ~np.isnan(pr)
    seg = ord_cierre - eg
    delta = pr - eg
    antes = eg < R6.ORDINAL_INICIO_FUENTE
    previo = ~antes & hay & (pr <= eg)
    sin_seg = ~antes & ~previo & (seg < 1)
    evento = ~antes & ~previo & ~sin_seg & hay & (delta <= seg)
    estado = np.select([antes, previo, sin_seg, evento], ["antes_de_la_fuente", "previo", "sin_seguimiento", "evento"],
                       default="censurado")
    out = pd.DataFrame(index=d.index)
    out["estado"] = estado
    vivo = np.isin(estado, ["evento", "censurado"])
    out["tiempo"] = np.where(vivo, np.where(estado == "evento", delta, seg), np.nan)
    out["evento"] = np.where(vivo, (estado == "evento").astype(float), np.nan)
    return out


def primeras_matriculas(postgrado: pd.DataFrame) -> pd.DataFrame:
    """Per person: first enrolled postgrado semester (``ord_primera``) and the long form of the rows (``ord_fila``)."""
    p = postgrado.copy()
    p["ord_fila"] = p["periodo"].map(R6.ordinal_postgrado)
    p = p.loc[p["ord_fila"].notna()].copy()
    p["ord_fila"] = p["ord_fila"].astype("int64")
    mat = p.loc[p["estado_matricula"] == R6.ESTADO_MATRICULADO]
    primera = mat.groupby("persona_key")["ord_fila"].min().rename("ord_primera")
    return primera.to_frame(), p[["persona_key", "ord_fila"]]


def _primera_fila_posterior(u: pd.DataFrame, filas: pd.DataFrame) -> pd.Series:
    """First postgrado ROW (enrolled or not) strictly after the egreso semester of each unit (sensitivity only)."""
    m = u[["episodio_id", "persona_key", "ord_egreso"]].merge(filas, on="persona_key")
    m = m.loc[m["ord_fila"] > m["ord_egreso"]]
    return m.groupby("episodio_id")["ord_fila"].min().reindex(u["episodio_id"]).set_axis(u.index)


def eventos_estados(d: pd.DataFrame, estados_pos: pd.DataFrame, programas_pos: pd.DataFrame, ord_cierre: int) -> pd.DataFrame:
    """P77: ``previo_estados``, ``evento_estados``, ``tiempo_estados`` and ``nivel_estados`` of every unit of ``d`` (columns
    ``episodio_id``, ``persona_key``, ``ord_egreso``, ``seguimiento``), vectorized mirror of
    ``rules_t6.resolver_evento_estados``. ``estados_pos``: ``persona_key``, ``cod_programa``, ``periodo``, ``cod_estado``;
    ``programas_pos``: ``cod_programa``, ``nivel_derivado``. Only enrolled (``M``) semesters are used."""
    out = pd.DataFrame({"previo_estados": False, "evento_estados": 0, "tiempo_estados": d["seguimiento"].astype("int64"),
                        "nivel_estados": None}, index=d.index)
    out["nivel_estados"] = out["nivel_estados"].astype(object)
    if estados_pos is None or estados_pos.empty:
        return out
    pos = estados_pos.loc[estados_pos["cod_estado"] == R6.ESTADO_MATRICULADO_POS,
                          ["persona_key", "cod_programa", "periodo"]].copy()
    pos["ord_fila"] = pos["periodo"].map(ordinal_estado_postgrado)
    pos = pos.loc[pos["ord_fila"].notna()].copy()
    pos["ord_fila"] = pos["ord_fila"].astype("int64")
    nivel = dict(zip(programas_pos["cod_programa"], programas_pos["nivel_derivado"]))
    rango = {n: i for i, n in enumerate(R6.NIVELES_ESTADOS)}
    pos["nivel"] = pos["cod_programa"].map(nivel).fillna("sin_nombre").replace({"sin_nombre": "otro"})
    pos["rango"] = pos["nivel"].map(rango).astype("int64")
    m = d[["episodio_id", "persona_key", "ord_egreso", "seguimiento"]].merge(pos, on="persona_key")
    if m.empty:
        return out
    previo = m.loc[m["ord_fila"] <= m["ord_egreso"], "episodio_id"].unique()
    ahora = m.loc[(m["ord_fila"] > m["ord_egreso"]) & (m["ord_fila"] - m["ord_egreso"] <= m["seguimiento"])]
    primera = ahora.groupby("episodio_id")["ord_fila"].transform("min")
    primeras = ahora.loc[ahora["ord_fila"] == primera]
    mejor = primeras.groupby("episodio_id")["rango"].min()
    t = primeras.groupby("episodio_id")["ord_fila"].min()
    eg = d.set_index("episodio_id")
    ids = d["episodio_id"].to_numpy()
    out["previo_estados"] = np.isin(ids, previo)
    hay = np.isin(ids, mejor.index.to_numpy())
    out["evento_estados"] = hay.astype("int64")
    delta = t.reindex(ids).to_numpy("float64") - eg["ord_egreso"].reindex(ids).to_numpy("float64")
    out["tiempo_estados"] = np.where(hay, delta, d["seguimiento"].to_numpy("float64")).astype("int64")
    nombre = np.array(R6.NIVELES_ESTADOS, dtype=object)
    r = mejor.reindex(ids).to_numpy("float64")
    out["nivel_estados"] = pd.Series(np.where(hay, nombre[np.nan_to_num(r, nan=0).astype(int)], None), index=d.index,
                                     dtype="object")
    return out


def construir_snapshot_t6(
    episodios: pd.DataFrame,
    estados: pd.DataFrame,
    intentos: pd.DataFrame,
    via: pd.DataFrame,
    egreso_titulacion: pd.DataFrame,
    malla: pd.DataFrame,
    prog_cat: pd.DataFrame,
    postgrado: pd.DataFrame,
    latest: str,
    estados_pos: pd.DataFrame = None,
    programas_pos: pd.DataFrame = None,
) -> Tuple[pd.DataFrame, Dict]:
    """Full snapshot: ``(snapshot_t6, embudo)``.

    ``postgrado``: columns ``persona_key``, ``periodo`` and ``estado_matricula`` (``neural_core.matricula_postgrado``).
    ``estados_pos`` / ``programas_pos`` (optional, P77): ``neural_core.estado_postgrado`` (``persona_key``, ``cod_programa``,
    ``periodo``, ``cod_estado``) and ``neural_core.programa_postgrado`` (``cod_programa``, ``nivel_derivado``); they only add
    the ``*_estados`` columns and never change the legacy label columns nor the population.
    """
    ord_cierre = R6.ordinal_cierre(latest)
    u = F3.unidades_t3(episodios, estados, egreso_titulacion, intentos)
    pop, est, tit, it, vinc = u.pop, u.estados, u.egreso, u.intentos, u.vinculos
    pop["cohorte_anio_"] = pop["periodo_admision"].str.slice(0, 4).astype(int)
    h = F3.hechos_episodio(pop, est, tit, latest)
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    por_ep = pop.set_index("episodio_id")

    egresado = h["t_egreso"].notna() & (h["t_egreso"] <= h["t_max"])
    d = h.loc[egresado, ["t_egreso", "t_titulacion"]].copy()
    d["episodio_id"] = d.index.to_numpy()
    d.index.name = None
    d["k"] = d["t_egreso"].astype("int64")
    d["persona_key"] = por_ep["persona_key"].reindex(d.index).to_numpy()
    d["ord_base"] = base.reindex(d.index).to_numpy()
    d["ord_egreso"] = d["ord_base"] + d["k"] - 1
    primera, filas = primeras_matriculas(postgrado)
    d["ord_primera"] = d["persona_key"].map(primera["ord_primera"]).astype("float64")
    est6 = resolver_estados(d, ord_cierre)
    previo = est6["estado"] == "previo"
    antes_adm = previo & (d["ord_primera"] < d["ord_base"])
    embudo = {
        "poblacion": int(len(pop)), "sin_egreso": int((~egresado).sum()), "egresados": int(egresado.sum()),
        "egreso_antes_de_la_fuente": int((est6["estado"] == "antes_de_la_fuente").sum()),
        "postgrado_previo_antes": int(antes_adm.sum()), "postgrado_previo_durante": int((previo & ~antes_adm).sum()),
        "sin_seguimiento": int((est6["estado"] == "sin_seguimiento").sum()),
        "cohortes_anteriores_excluidas": int(u.n_previas),
    }
    ok = est6["estado"].isin(["evento", "censurado"])
    d = d.loc[ok].copy()
    est6 = est6.loc[ok]
    embudo["elegibles"] = int(len(d))
    embudo["eventos"] = int(est6["evento"].sum())
    if d.empty:
        return pd.DataFrame(columns=SNAPSHOT_COLS_T6), embudo

    d["seguimiento"] = (ord_cierre - d["ord_egreso"]).astype("int64")
    d["tiempo"] = est6["tiempo"].astype("int64")
    d["evento"] = est6["evento"].astype("int64")
    post = _primera_fila_posterior(d, filas)
    delta = post - d["ord_egreso"]
    ev_alt = (delta.notna() & (delta <= d["seguimiento"])).to_numpy()
    d["evento_cualquier_fila"] = ev_alt.astype("int64")
    d["tiempo_cualquier_fila"] = np.where(ev_alt, delta.fillna(0), d["seguimiento"]).astype("int64")
    ev6 = eventos_estados(d, estados_pos, programas_pos, ord_cierre)
    for c in ev6.columns:
        d[c] = ev6[c].to_numpy()
    embudo["previo_estados"] = int(d["previo_estados"].sum())
    embudo["eventos_estados"] = int(d["evento_estados"].sum())
    d["anio_egreso"] = (d["ord_egreso"] // 2).astype("int64")
    d["split"] = d["anio_egreso"].map(R6.split_egreso)

    # ---- features at the cut (T3 construction with a cut per row) ----
    pop_e = pop.loc[pop["episodio_id"].isin(d["episodio_id"])].copy()
    kmax = int(d["k"].max())
    cortes = pop_e[["episodio_id", "persona_key", "cod_programa", "periodo_admision"]].merge(
        d[["episodio_id", "k"]], on="episodio_id")
    acad, _ = F3.features_academicas(cortes, pop_e, it, est, (kmax,))
    adm = F.features_admision(pop_e, via)
    meta = pop_e[["episodio_id", "cod_admision", "sede", "tipo_qualitas", "sexo"]].copy()
    meta["via_clase"] = meta["tipo_qualitas"].map(lambda q: R.via_clase(q if isinstance(q, str) else None))
    meta = meta.rename(columns={"sexo": "sexo_equidad"}).drop(columns=["tipo_qualitas"])

    prog_pc = F3.features_programa(pop, malla, prog_cat, range(1, kmax + 1))
    vinculados = pop.loc[pop["episodio_esp"].notna()]
    esp_pop = vinculados[["episodio_id"]].assign(cod_programa=vinculados["cod_programa_esp"].to_numpy(),
                                                 catalogo_inicial=vinculados["catalogo_esp"].to_numpy())
    prog_esp = F3.features_programa(esp_pop, malla, prog_cat, range(1, kmax + 1)) if len(esp_pop) else None
    constante = F3.constante_duracion_plan_comun(pop, prog_pc, prog_esp)

    snap = cortes.merge(acad, on=["episodio_id", "k"], how="left").merge(adm, on="episodio_id", how="left").merge(
        meta, on="episodio_id", how="left")
    esp_id = por_ep["episodio_esp"].reindex(snap["episodio_id"]).to_numpy()
    inicio = por_ep["inicio_esp"].reindex(snap["episodio_id"]).to_numpy(object)
    corte = np.array([R.corte_periodo(p, int(k)) for p, k in zip(snap["periodo_admision"], snap["k"])], dtype=object)
    snap["trayectoria_plan_comun"] = snap["cod_programa"].isin(R3.PLAN_COMUN_ING_CIVIL).to_numpy()
    snap["especialidad_conocida_al_corte"] = np.array(
        [bool(pd.notna(e_) and c is not None and isinstance(i, str) and i <= c) for e_, c, i in zip(esp_id, corte, inicio)],
        dtype=bool)
    snap["episodio_especialidad_id"] = pd.array(esp_id, dtype="Int64")
    vig = F3.programa_vigente(snap, pop, prog_pc, prog_esp, constante)
    for col in vig.columns:
        snap[col] = vig[col].to_numpy()
    snap["avance_malla"] = snap["creditos_aprobados"] / snap["creditos_esperados"].where(snap["creditos_esperados"] > 0)
    snap["fraccion_malla"] = snap["creditos_aprobados"] / snap["creditos_malla_total"].where(snap["creditos_malla_total"] > 0)
    snap["con_postulacion"] = snap["con_postulacion"].fillna(False).astype(bool)
    snap["malla_conocida"] = snap["malla_conocida"].eq(True)
    snap["sede"] = snap["sede"].map(lambda s: None if pd.isna(s) else str(int(s)) if not isinstance(s, str) else s)

    # ---- features of the egreso itself ----
    dd = d.set_index("episodio_id")
    snap["semestres_a_egreso"] = snap["k"].astype("int64")
    snap["exceso_duracion"] = snap["k"] - snap["duracion_nominal"]
    snap["razon_duracion"] = snap["k"] / snap["duracion_nominal"].where(snap["duracion_nominal"] > 0)
    t_tit = dd["t_titulacion"].reindex(snap["episodio_id"]).to_numpy("float64")
    snap["titulado_al_corte"] = (~np.isnan(t_tit)) & (t_tit <= snap["k"].to_numpy("float64"))
    for c in ("seguimiento", "tiempo", "evento", "tiempo_cualquier_fila", "evento_cualquier_fila", "anio_egreso",
              "previo_estados", "evento_estados", "tiempo_estados", "nivel_estados"):
        snap[c] = dd[c].reindex(snap["episodio_id"]).to_numpy()
    snap["split"] = dd["split"].reindex(snap["episodio_id"]).to_numpy()
    snap["cohorte_anio"] = snap["periodo_admision"].str.slice(0, 4).astype(int)
    snap = snap.sort_values("episodio_id").reset_index(drop=True)
    return snap[SNAPSHOT_COLS_T6].copy(), embudo
