"""Point-in-time construction of the T1 snapshot with pandas (docs/08_benchmark_t1.md).

Inputs are plain DataFrames (loaded by ``t1.py``; tests pass synthetic ones). Nothing here touches a database.

Leakage guards, all covered by ``tests/unit/test_snapshot_features.py``:
* every feature is computed from rows whose period is ``<= periodo_corte`` (slot ``<= k``);
* the label only looks at periods strictly after the cutoff, up to the horizon;
* rows whose horizon is not observable are kept with ``estado_muestra`` = censurada / sin_cobertura and NULL labels.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from ..marts.rules import base_ordinal
from ..normalize.states import ESTADOS
from . import rules as R
from .features_beneficios import features_beneficios

CLASE_DE_ESTADO: Dict[str, str] = {cod: clase for cod, (_, clase) in ESTADOS.items()}
MATRICULA = ("matricula", "reingreso", "cambio_ciclo")           # an enrolled state
CONTINUIDAD = MATRICULA + ("egreso_titulacion",)                  # counts as continuity at the horizon
SCORE_COLS = {                                                    # snapshot column -> postulacion_via column
    "pct_leng": "puntaje_leng", "pct_mat": "puntaje_mat", "pct_ciencias": "puntaje_ciencias",
    "pct_historia": "puntaje_historia", "pct_nem": "puntaje_nem", "pct_ranking": "puntaje_ranking",
    "pct_notas_em": "notas_em", "pct_ponderado": "ponderado",
}
MM_COLS = {                                                       # P47: min-max per test and year (next to the pct_*)
    "mm_leng": "puntaje_leng", "mm_mat": "puntaje_mat", "mm_ciencias": "puntaje_ciencias",
    "mm_historia": "puntaje_historia", "mm_nem": "puntaje_nem", "mm_ranking": "puntaje_ranking",
    "mm_notas_em": "notas_em", "mm_ponderado": "ponderado",
}
PRUEBA_COL = "prueba_admision"
ADMISION_P47 = [PRUEBA_COL, *MM_COLS]                             # snapshot columns added by P47 (never in FEATURE_COLS_*)


# ---------------------------------------------------------------------------------------------
# vectorized period helpers (mirror rules.py; equality is tested on a grid)
# ---------------------------------------------------------------------------------------------
def base_ordinales(periodo_admision: pd.Series) -> pd.Series:
    return periodo_admision.map(lambda p: base_ordinal(p) if isinstance(p, str) else None).astype("float64")


def slot_vectorizado(periodo: pd.Series, base: pd.Series) -> pd.Series:
    """Vectorized ``rules.slot_de_periodo``; NaN where undefined."""
    text = periodo.astype("string")
    valid = text.str.fullmatch(r"\d{6}").fillna(False).to_numpy(bool)
    anio = pd.to_numeric(text.str.slice(0, 4), errors="coerce").to_numpy("float64")
    sufijo = text.str.slice(4, 6).fillna("00").to_numpy(str)
    ordinal = np.where(sufijo <= "10", anio * 2, np.where(sufijo <= "20", anio * 2 + 1, (anio + 1) * 2))
    j = ordinal - base.to_numpy("float64") + 1
    j = np.where(valid & (j >= 1), j, np.nan)
    return pd.Series(j, index=periodo.index)


def es_regular(periodo: pd.Series) -> pd.Series:
    return periodo.astype("string").str.slice(4, 6).isin(["10", "20"]).fillna(False).astype(bool)


def clase_estado(cod_estado: pd.Series) -> pd.Series:
    return cod_estado.map(CLASE_DE_ESTADO).fillna("otro")


# ---------------------------------------------------------------------------------------------
# population, cutoffs, eligibility and label
# ---------------------------------------------------------------------------------------------
def poblacion(episodios: pd.DataFrame) -> pd.DataFrame:
    """Undergraduate episodes outside exchange / special-plan admissions with a usable admission period."""
    ok = (episodios["id_nivel"] == R.NIVEL_PREGRADO) & ~episodios["cod_admision"].isin(R.ADMISIONES_EXCLUIDAS)
    ok &= base_ordinales(episodios["periodo_admision"]).notna()
    return episodios.loc[ok].copy()


def _estados_utiles(estados: pd.DataFrame) -> pd.DataFrame:
    e = estados.loc[~estados["es_correccion_sistema"]].copy()
    e["clase"] = clase_estado(e["cod_estado"])
    return e


def construir_cortes(
    episodios: pd.DataFrame,
    estados: pd.DataFrame,
    egreso_titulacion: pd.DataFrame,
    latest: str,
    ks: Sequence[int] = R.KS,
):
    """Eligible (episode, k) rows with sample status and labels, plus the elimination counts.

    ``egreso_titulacion``: columns ``persona_key``, ``episodio_id``, ``periodo`` (period of each titulacion date).
    Returns ``(cortes, resumen)``; ``resumen`` has one dict per k with the funnel counts.
    """
    pop = poblacion(episodios)
    est = _estados_utiles(estados)
    resumen = []
    out = []
    # states of the episode, reused below
    est_ep = est.loc[est["episodio_id"].notna()].copy()
    est_ep["episodio_id"] = est_ep["episodio_id"].astype("int64")
    # earliest egress/titulation period per episode and per person (states + titulacion table)
    eg_states = est.loc[est["clase"] == "egreso_titulacion"]
    eg_ep = pd.concat([
        eg_states.loc[eg_states["episodio_id"].notna(), ["episodio_id", "periodo"]].astype({"episodio_id": "int64"}),
        egreso_titulacion.loc[egreso_titulacion["episodio_id"].notna(), ["episodio_id", "periodo"]].astype(
            {"episodio_id": "int64"}),
    ]).groupby("episodio_id")["periodo"].min().rename("eg_ep")
    eg_pers = pd.concat([eg_states[["persona_key", "periodo"]], egreso_titulacion[["persona_key", "periodo"]]]
                        ).groupby("persona_key")["periodo"].min().rename("eg_pers")
    enrolled_pairs = est_ep.loc[est_ep["clase"].isin(MATRICULA), ["episodio_id", "periodo"]].drop_duplicates()
    enrolled_pairs["inscrito"] = True
    # an exit state recorded in the cutoff period itself is already known at the cutoff: not a prediction target
    salida_corte = est_ep.loc[est_ep["clase"] == "salida", ["episodio_id", "periodo"]].drop_duplicates()
    salida_corte["salida_en_corte"] = True
    cont = est.loc[est["clase"].isin(CONTINUIDAD), ["persona_key", "periodo", "cod_programa"]]
    cont_pers = cont[["persona_key", "periodo"]].drop_duplicates().assign(cont_h=True)
    cont_prog = cont.rename(columns={"cod_programa": "cod_programa_estado"}).drop_duplicates().assign(cont_prog=True)

    for k in ks:
        c = pop[["episodio_id", "persona_key", "cod_programa", "periodo_admision", "cod_admision"]].copy()
        c["k"] = k
        c["periodo_corte"] = c["periodo_admision"].map(lambda p: R.corte_periodo(p, k))
        c["periodo_horizonte"] = c["periodo_corte"].map(R.horizonte_periodo)
        n_pop = len(c)
        c = c.merge(enrolled_pairs, left_on=["episodio_id", "periodo_corte"], right_on=["episodio_id", "periodo"],
                    how="left")
        n_sin_matricula = int(c["inscrito"].isna().sum())
        c = c.loc[c["inscrito"].notna()].drop(columns=["periodo", "inscrito"])
        c = c.merge(salida_corte, left_on=["episodio_id", "periodo_corte"], right_on=["episodio_id", "periodo"],
                    how="left")
        ya_salio = c["salida_en_corte"].notna().to_numpy()
        n_salida_en_corte = int(ya_salio.sum())
        c = c.loc[~ya_salio].drop(columns=["periodo", "salida_en_corte"])
        c = c.merge(eg_ep, left_on="episodio_id", right_index=True, how="left")
        ya = c["eg_ep"].notna() & (c["eg_ep"] <= c["periodo_corte"])
        n_ya_egresado = int(ya.sum())
        c = c.loc[~ya].drop(columns=["eg_ep"])
        c["estado_muestra"] = [R.estado_muestra(a, b, latest) for a, b in zip(c["periodo_corte"],
                                                                                 c["periodo_horizonte"])]
        c["cohorte_anio"] = c["periodo_admision"].str.slice(0, 4).astype(int)
        c["split"] = c["cohorte_anio"].map(R.split_cohorte)
        c = _etiquetar(c, est_ep, eg_ep, eg_pers, cont_pers, cont_prog)
        out.append(c)
        resumen.append({"k": k, "poblacion": n_pop, "sin_matricula_en_k": n_sin_matricula,
                        "salida_en_corte": n_salida_en_corte,
                        "ya_egresado_o_titulado": n_ya_egresado, "elegibles": len(c)})
    return pd.concat(out, ignore_index=True), resumen


def _etiquetar(c, est_ep, eg_ep, eg_pers, cont_pers, cont_prog) -> pd.DataFrame:
    c = c.merge(cont_pers, left_on=["persona_key", "periodo_horizonte"], right_on=["persona_key", "periodo"],
                how="left").drop(columns=["periodo"])
    c = c.merge(eg_pers, left_on="persona_key", right_index=True, how="left")
    c = c.merge(eg_ep, left_on="episodio_id", right_index=True, how="left")
    c = c.merge(cont_prog, left_on=["persona_key", "periodo_horizonte", "cod_programa"],
                right_on=["persona_key", "periodo", "cod_programa_estado"], how="left"
                ).drop(columns=["periodo", "cod_programa_estado"])
    obs = (c["estado_muestra"] == "observada").to_numpy()
    egreso_antes = c["eg_pers"].notna() & (c["eg_pers"] <= c["periodo_horizonte"])
    egreso_ep = c["eg_ep"].notna() & (c["eg_ep"] <= c["periodo_horizonte"])
    continua = (c["cont_h"].notna() | egreso_antes).to_numpy()
    mismo = (c["cont_prog"].notna() | egreso_ep).to_numpy()
    # kind of non-continuity, from the states of the episode inside (cutoff, horizon]
    tramo = c[["episodio_id", "k", "periodo_corte", "periodo_horizonte"]].merge(
        est_ep[["episodio_id", "periodo", "clase"]], on="episodio_id")
    tramo = tramo.loc[(tramo["periodo"] > tramo["periodo_corte"]) & (tramo["periodo"] <= tramo["periodo_horizonte"])]
    salida = tramo.loc[tramo["clase"] == "salida", ["episodio_id", "k"]].drop_duplicates().assign(_salida=True)
    interr = tramo.loc[tramo["clase"] == "interrupcion", ["episodio_id", "k"]].drop_duplicates().assign(_interr=True)
    c = c.merge(salida, on=["episodio_id", "k"], how="left").merge(interr, on=["episodio_id", "k"], how="left")
    tipo = np.where(c["_salida"].notna().to_numpy(), "salida",
                    np.where(c["_interr"].notna().to_numpy(), "interrupcion", "ausencia"))
    c["continua"] = pd.array(np.where(obs, continua, None), dtype="boolean")
    c["continua_mismo_programa"] = pd.array(np.where(obs, mismo, None), dtype="boolean")
    c["no_continua_tipo"] = pd.Series(np.where(obs & ~continua, tipo, None), index=c.index, dtype="object")
    return c.drop(columns=["cont_h", "eg_pers", "eg_ep", "cont_prog", "_salida", "_interr"])


# ---------------------------------------------------------------------------------------------
# academic features by semester slot
# ---------------------------------------------------------------------------------------------
def tabla_semestres(
    pop: pd.DataFrame, intentos: pd.DataFrame, estados: pd.DataFrame, kmax: int = max(R.KS)
) -> pd.DataFrame:
    """One row per (episode, j <= kmax) with the facts of the slot ``j`` and the running credits."""
    base = pd.Series(base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    grid = pd.MultiIndex.from_product([pop["episodio_id"].to_numpy(), range(1, kmax + 1)],
                                      names=["episodio_id", "j"]).to_frame(index=False)

    a = intentos.loc[intentos["episodio_id"].isin(base.index)].copy()
    a["j"] = slot_vectorizado(a["periodo"], a["episodio_id"].map(base))
    a = a.loc[a["j"].notna() & (a["j"] <= kmax)].copy()
    a["j"] = a["j"].astype(int)
    ev = a["es_intento_evaluado"].astype(bool)
    nota_ok = ev & a["nota_numerica"].notna() & ~a["nota_es_heredada"].astype(bool)
    a["ie"] = ev.astype(int)
    a["ae"] = (ev & a["aprobado_curricular"].fillna(False).astype(bool)).astype(int)
    a["re"] = (ev & ~a["aprobado_curricular"].fillna(False).astype(bool)).astype(int)
    a["cv"] = (a["resultado_tipo"] == "convalidacion").astype(int)
    a["vi"] = (~es_regular(a["periodo"]) & (a["resultado_tipo"] != "renuncia")).astype(int)
    a["nn"] = nota_ok.astype(int)
    a["sn"] = a["nota_numerica"].where(nota_ok, 0.0).astype(float)
    # first approval of each course (convalidations included) is the only one that adds credits
    apr = a.loc[a["aprobado_curricular"].fillna(False).astype(bool)].sort_values(["periodo", "intento_id"])
    apr = apr.drop_duplicates(["episodio_id", "codigo_asignatura"])
    a["cred"] = 0.0
    cred = (apr["creditos"].fillna(apr["creditos_reconocidos"]).fillna(0.0)).astype(float)
    a.loc[apr.index, "cred"] = cred
    g = a.groupby(["episodio_id", "j"])[["ie", "ae", "re", "cv", "vi", "nn", "sn", "cred"]].sum().reset_index()

    e = _estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna() & e["episodio_id"].isin(base.index)].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    e["j"] = slot_vectorizado(e["periodo"], e["episodio_id"].map(base))
    e = e.loc[e["j"].notna() & (e["j"] <= kmax)].copy()
    e["j"] = e["j"].astype(int)
    e["mat"] = (e["clase"].isin(MATRICULA) & es_regular(e["periodo"])).astype(int)
    e["int"] = (e["clase"] == "interrupcion").astype(int)
    s = e.groupby(["episodio_id", "j"])[["mat", "int"]].max().reset_index()

    t = grid.merge(g, on=["episodio_id", "j"], how="left").merge(s, on=["episodio_id", "j"], how="left")
    cols = ["ie", "ae", "re", "cv", "vi", "nn", "sn", "cred", "mat", "int"]
    t[cols] = t[cols].fillna(0)
    t = t.sort_values(["episodio_id", "j"]).reset_index(drop=True)
    t["cred_ac"] = t.groupby("episodio_id")["cred"].cumsum()
    return t


def features_corte(cortes: pd.DataFrame, semestres: pd.DataFrame, estados: pd.DataFrame) -> pd.DataFrame:
    """Academic features of each (episode, k) from the slots ``j <= k`` and the episode states up to the cutoff."""
    sem = semestres.merge(cortes[["episodio_id", "k"]], on="episodio_id")
    sem = sem.loc[sem["j"] <= sem["k"]]
    agg = sem.groupby(["episodio_id", "k"]).agg(
        creditos_aprobados=("cred", "sum"), intentos_evaluados=("ie", "sum"), aprobados=("ae", "sum"),
        reprobados=("re", "sum"), convalidaciones=("cv", "sum"), cursos_verano_invierno=("vi", "sum"),
        n_notas_promedio=("nn", "sum"), _sn=("sn", "sum"), semestres_matriculados=("mat", "sum"),
    ).reset_index()
    ult = sem.loc[sem["j"] == sem["k"], ["episodio_id", "k", "ie", "ae", "nn", "sn"]].rename(
        columns={"ie": "intentos_ult_semestre", "ae": "_ae_ult", "nn": "_nn_ult", "sn": "_sn_ult"})
    f = agg.merge(ult, on=["episodio_id", "k"], how="left")
    f["tasa_aprobacion"] = f["aprobados"] / f["intentos_evaluados"].where(f["intentos_evaluados"] > 0)
    f["promedio_evaluado"] = f["_sn"] / f["n_notas_promedio"].where(f["n_notas_promedio"] > 0)
    f["tasa_ult_semestre"] = f["_ae_ult"] / f["intentos_ult_semestre"].where(f["intentos_ult_semestre"] > 0)
    f["promedio_ult_semestre"] = f["_sn_ult"] / f["_nn_ult"].where(f["_nn_ult"] > 0)
    f = f.drop(columns=["_sn", "_ae_ult", "_nn_ult", "_sn_ult"])

    e = _estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna()].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    e = cortes[["episodio_id", "k", "periodo_corte"]].merge(e[["episodio_id", "periodo", "clase", "catalogo"]],
                                                            on="episodio_id")
    e = e.loc[e["periodo"] <= e["periodo_corte"]]
    interr = e.loc[e["clase"] == "interrupcion"].groupby(["episodio_id", "k"]).size().rename("n_interrupcion")
    cat = e.loc[e["catalogo"].notna()].groupby(["episodio_id", "k"])["catalogo"].nunique().sub(1).clip(lower=0)
    cat = cat.rename("cambios_catalogo")
    out = cortes[["episodio_id", "k"]].merge(f, on=["episodio_id", "k"], how="left")
    out = out.merge(interr, left_on=["episodio_id", "k"], right_index=True, how="left")
    out = out.merge(cat, left_on=["episodio_id", "k"], right_index=True, how="left")
    for col in ("n_interrupcion", "cambios_catalogo", "creditos_aprobados", "intentos_evaluados", "aprobados",
                "reprobados", "convalidaciones", "cursos_verano_invierno", "n_notas_promedio",
                "semestres_matriculados", "intentos_ult_semestre"):
        out[col] = out[col].fillna(0)
    return out


# ---------------------------------------------------------------------------------------------
# admission features
# ---------------------------------------------------------------------------------------------
def rangos_percentiles(via: pd.DataFrame) -> pd.DataFrame:
    """Within-year percentile rank (0..1] of every score, among all applicant rows of the same year.

    PSU/PDT/PAES change scale over the years (P22/P47), so raw scores are never compared across years; a score
    <= 0 is a missing value. The rank uses only the applicants of the same admission year and no outcome, so it
    needs no fitting on the training split.
    """
    v = via.copy()
    v["anio"] = v["year_admision"].str.slice(0, 4)
    for out_col, src in SCORE_COLS.items():
        x = pd.to_numeric(v[src], errors="coerce")
        x = x.where(x > 0)
        if src == "ponderado":                                       # mixed decimal scales inside one year (measured)
            digitos = np.floor(np.log10(x.where(x >= 1000))).add(1).fillna(3).clip(lower=3)
            x = x / np.power(10.0, digitos - 3)
        v[out_col] = x.groupby(v["anio"]).rank(pct=True, method="average")
    return v


def normalizar_min_max(via: pd.DataFrame) -> pd.DataFrame:
    """P47: the admission test (``prueba_admision``) by process year and every score scaled to [0, 1] with the minimum and
    maximum of its (test, year, field): ``(x - min) / (max - min)``.

    A score <= 0 is missing; an order-of-magnitude outlier (> ``FACTOR_ESCALA`` times the median of its group) is a
    reading error and is left out of the scaling; a group with a single value (min = max) has no scale and gives NaN.
    Only applicants of the same test and year enter a group and no outcome is used, so nothing is fitted on a split.
    """
    v = via.copy()
    v["anio"] = v["year_admision"].astype("string").str.slice(0, 4)
    v[PRUEBA_COL] = v["anio"].map(R.prueba_admision).astype(object)
    claves = [v[PRUEBA_COL].fillna("sin_prueba"), v["anio"]]
    for out_col, src in MM_COLS.items():
        x = pd.to_numeric(v[src], errors="coerce")
        x = x.where(x > 0)
        if src == "ponderado":                                       # mixed decimal scales inside one year (measured)
            digitos = np.floor(np.log10(x.where(x >= 1000))).add(1).fillna(3).clip(lower=3)
            x = x / np.power(10.0, digitos - 3)
        mediana = x.groupby(claves).transform("median")
        x = x.where(x <= R.FACTOR_ESCALA * mediana)
        lo, hi = x.groupby(claves).transform("min"), x.groupby(claves).transform("max")
        v[out_col] = ((x - lo) / (hi - lo)).where(hi > lo)
    return v


def features_admision(pop: pd.DataFrame, via: pd.DataFrame) -> pd.DataFrame:
    """One row per episode with the pre-entry facts of its application route (NaN when no route is linked)."""
    v = rangos_percentiles(normalizar_min_max(via))
    v["preferencia_num"] = pd.to_numeric(v["preferencia"], errors="coerce")
    m = pop[["episodio_id", "persona_key", "cod_programa", "periodo_admision", "cod_admision"]].merge(
        v, left_on=["persona_key", "cod_programa", "periodo_admision"],
        right_on=["persona_key", "cod_carrera", "year_admision"], how="left", suffixes=("", "_via"))
    m["_misma_via"] = (m["cod_admision"] == m["cod_admision_via"]).astype(int)
    m["_mat"] = (m["matricula"] == "Y").astype(int)
    m = m.sort_values(["episodio_id", "_misma_via", "_mat", "postulacion_via_id"],
                      ascending=[True, False, False, True]).drop_duplicates("episodio_id")
    keep = ["episodio_id", "preferencia_num", "tipo_colegio", "depend_colegio", "region_colegio", *SCORE_COLS,
            *ADMISION_P47]
    out = m[keep].copy()
    out["con_postulacion"] = m["postulacion_via_id"].notna().to_numpy()
    out = out.rename(columns={"preferencia_num": "preferencia"})
    out["tipo_colegio"] = out["tipo_colegio"].map(R.codigo_colegio)
    out["depend_colegio"] = out["depend_colegio"].map(R.codigo_dependencia)
    out["region_colegio"] = out["region_colegio"].map(lambda s: (s or "").strip() or None if isinstance(s, str) else None)
    return out


def construir_snapshot(
    episodios: pd.DataFrame,
    estados: pd.DataFrame,
    intentos: pd.DataFrame,
    via: pd.DataFrame,
    egreso_titulacion: pd.DataFrame,
    latest: str,
    ks: Sequence[int] = R.KS,
    beneficios: Optional[pd.DataFrame] = None,
    malla: Optional[pd.DataFrame] = None,
):
    """Full snapshot: ``(snapshot_t1, snapshot_t1_semestre, resumen_embudo)``.

    ``beneficios`` (``banner_beneficios`` rows: ``periodo`` = year, ``persona_key``, ``cod_carrera``, ``codigo``, ``benef_sem1``)
    adds the benefit columns of ``features_beneficios`` (D90-D95); without it the snapshot has exactly the columns it had before.
    ``malla`` (``asignatura_malla`` rows) adds the new variables of ``features_t1_nuevas`` (P117-P127; needs ``oportunidad`` in
    ``intentos`` and ``catalogo_inicial`` in ``episodios``); without it the snapshot keeps the columns it had.
    """
    cortes, embudo = construir_cortes(episodios, estados, egreso_titulacion, latest, ks)
    pop = poblacion(episodios)
    sem = tabla_semestres(pop, intentos, estados, max(ks))
    acad = features_corte(cortes, sem, estados)
    adm = features_admision(pop, via)
    meta = pop[["episodio_id", "sede", "tipo_qualitas", "sexo"]].copy()
    meta["via_clase"] = meta["tipo_qualitas"].map(lambda q: R.via_clase(q if isinstance(q, str) else None))
    meta = meta.rename(columns={"sexo": "sexo_equidad"}).drop(columns=["tipo_qualitas"])
    snap = (cortes.merge(acad, on=["episodio_id", "k"], how="left")
            .merge(adm, on="episodio_id", how="left").merge(meta, on="episodio_id", how="left"))
    snap["con_postulacion"] = snap["con_postulacion"].fillna(False).astype(bool)
    if malla is not None:
        from .features_t1_nuevas import features_t1_nuevas

        snap = snap.merge(features_t1_nuevas(cortes, sem, intentos, estados, malla, pop), on=["episodio_id", "k"], how="left")
    if beneficios is not None:
        snap = snap.merge(features_beneficios(cortes, beneficios), on=["episodio_id", "k"], how="left")
    snap["sede"] = snap["sede"].map(lambda s: None if pd.isna(s) else str(int(s)) if not isinstance(s, str) else s)
    return snap, sem, embudo
