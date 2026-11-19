"""Point-in-time construction of the new variables of T3-T6 (``rules_variables`` holds the rules and their sources).

``construir_variables(cortes, pop, intentos, malla, episodios, prog_cat)`` returns one row per cut ``(episodio_id, k)`` with the
columns of ``VARIABLES_NUEVAS``. Nothing here touches a database and nothing existing is changed: the result is stored in a
SIDE table and merged by the model loaders, so the kept models stay reproducible.

Leakage guards (``tests/unit/test_variables_nuevas.py``):
* every attempt feature reads only attempts whose slot is ``<= k``; ``k = 0`` only gets the static malla facts;
* the periods without recorded failures (P58: 201920 and 202010) never produce a failure: their attempts are treated as not
  evaluated (as ``features_t3.intentos_para_features`` does), so a failure count is a lower bound for the cohorts that
  cross them, and the sensitivity tables of the benchmark exclude those rows;
* the malla totals and flags are static facts of the program and catalogue of the attempts (P126 collapses the elective
  pools: a pool is one slot, not one slot per alternative);
* the graduation ranking of T6 uses only graduates of the same program up to the same graduation semester.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from . import features as F
from . import rules_t3 as R3
from . import rules_variables as RV

VARS_REGLAMENTO = [
    "reg_rep2_total", "reg_rep2_cb", "reg_rep2_cp", "reg_rep3_cursos", "reg_cursos_riesgo_3ra", "reg_pendientes_reprobados",
    "reg_ciclo_cb_actual", "reg_sem_en_cb", "reg_dist_2da_antiguo", "reg_dist_3ra_antiguo", "reg_dist_2da_nuevo",
    "reg_dist_3ra_nuevo", "reg_n_sem_avance_lt50", "reg_consec_avance_lt50", "reg_dist_avance_antiguo"]
VARS_ALCANCE = ["alc_sem_pendiente_antiguo", "alc_rezago", "alc_pendiente_gt4", "alc_n_bloqueados"]
VARS_T3 = ["creditos_malla_total_corr", "malla_creditos_confiable", "creditos_restantes", "velocidad_aprobacion",
           "velocidad_relativa", "cap_inscrito", "cap_aprobado", "prac_inscrita", "prac_aprobada", "malla_tiene_capstone",
           "malla_tiene_practica"]
VARS_T4 = ["n_propios_eval", "tasa_propios", "prom_propios", "n_generales_eval", "tasa_generales", "prom_generales",
           "brecha_propios_generales", "n_episodios_previos", "n_cc_previos"]
VARIABLES_NUEVAS: List[str] = [*VARS_REGLAMENTO, *VARS_ALCANCE, *VARS_T3, *VARS_T4]
VARS_BOOL = ["malla_creditos_confiable", "alc_pendiente_gt4", "malla_tiene_capstone", "malla_tiene_practica"]


# ---------------------------------------------------------------------------------------------
# malla: totals (P126) and per-course attributes
# ---------------------------------------------------------------------------------------------
def _malla_tipada(malla: pd.DataFrame) -> pd.DataFrame:
    m = malla.copy()
    m["creditos"] = pd.to_numeric(m["creditos"], errors="coerce")
    m["semestre"] = pd.to_numeric(m["semestre"], errors="coerce")
    clave = ["cod_programa", "catalogo", "formacion", "semestre"]
    tam = m.groupby(clave, dropna=True)["codigo_asignatura"].transform("size")
    m["n_pool"] = np.where(m["formacion"].notna() & m["semestre"].notna(), tam, 1).astype("int64")
    return m


def atributos_malla(malla: pd.DataFrame) -> pd.DataFrame:
    """Per (program, catalogue, course): semester, cycle (CB / CP), formation type, pool size and credits."""
    m = _malla_tipada(malla)
    m["ciclo"] = m["semestre_texto"].map(RV.ciclo_de_semestre_texto)
    m["ftipo"] = m["formacion"].map(RV.tipo_formacion)
    return m[["cod_programa", "catalogo", "codigo_asignatura", "semestre", "ciclo", "ftipo", "n_pool", "creditos"]]


def totales_malla(malla: pd.DataFrame, prog_cat: pd.DataFrame) -> pd.DataFrame:
    """Credit total of every (program, catalogue) with the elective pools collapsed (P126).

    The raw sum counts every alternative of an elective pool (several courses with the same formation code in the same
    semester are alternatives, not requirements): it inflated the totals up to 3,385. A pool counts once, with the median
    credits of its alternatives. ``malla_creditos_confiable`` marks the totals whose credits per nominal semester sit in
    ``rules_variables.CREDITOS_POR_SEMESTRE_MIN..MAX`` (the rest are partial plans or another unit).
    """
    m = _malla_tipada(malla)
    clave = ["cod_programa", "catalogo"]
    fijo = m.loc[m["n_pool"] == 1].groupby(clave)["creditos"].sum()
    pool = m.loc[m["n_pool"] > 1]
    pools = pool.groupby([*clave, "formacion", "semestre"])["creditos"].median()
    n_pools = pools.groupby(level=clave).size()
    t = pd.DataFrame({"creditos_malla_bruto": m.groupby(clave)["creditos"].sum(), "max_semestre": m.groupby(clave)["semestre"].max()})
    t["creditos_malla_total_corr"] = fijo.reindex(t.index).fillna(0.0) + pools.groupby(level=clave).sum().reindex(t.index).fillna(0.0)
    t["n_pools"] = n_pools.reindex(t.index).fillna(0).astype("int64")
    clase = m["nombre_asignatura"].map(RV.clasificar_titulo)
    t["malla_tiene_capstone"] = clase.isin(["capstone", "titulo"]).groupby([m["cod_programa"], m["catalogo"]]).any().reindex(t.index).fillna(False)
    t["malla_tiene_practica"] = (clase == "practica").groupby([m["cod_programa"], m["catalogo"]]).any().reindex(t.index).fillna(False)
    t = t.reset_index().merge(prog_cat[[*clave, "duracion"]].drop_duplicates(clave), on=clave, how="left")
    dur = pd.to_numeric(t["duracion"], errors="coerce")
    t["duracion_ref"] = dur.where(dur > 0, t["max_semestre"])
    por_sem = t["creditos_malla_total_corr"] / t["duracion_ref"].where(t["duracion_ref"] > 0)
    t["malla_creditos_confiable"] = ((por_sem >= RV.CREDITOS_POR_SEMESTRE_MIN) & (por_sem <= RV.CREDITOS_POR_SEMESTRE_MAX)).fillna(False)
    return t[[*clave, "creditos_malla_bruto", "creditos_malla_total_corr", "n_pools", "duracion_ref", "malla_creditos_confiable",
              "malla_tiene_capstone", "malla_tiene_practica"]]


# ---------------------------------------------------------------------------------------------
# attempts
# ---------------------------------------------------------------------------------------------
def marcar_fallas(a: pd.DataFrame) -> pd.DataFrame:
    """Adds, in place, ``ev_ok`` (evaluated attempt outside the P58 periods), ``aprob``, ``fail`` and ``opo`` (opportunity number)."""
    sin_rep = a["periodo"].isin(R3.PERIODOS_SIN_REPROBACION)
    a["ev_ok"] = a["es_intento_evaluado"].astype(bool) & ~sin_rep
    a["aprob"] = a["aprobado_curricular"].astype("boolean").fillna(False).astype(bool)
    a["fail"] = a["ev_ok"] & ~a["aprob"]
    a["opo"] = pd.to_numeric(a["oportunidad"], errors="coerce")
    return a


def preparar_intentos(intentos: pd.DataFrame, pop: pd.DataFrame, atributos: pd.DataFrame, kmax: int) -> pd.DataFrame:
    """Attempts of the units with their slot ``j <= kmax`` and the flags the features use."""
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    a = intentos.loc[intentos["episodio_id"].isin(base.index)].copy()
    a["episodio_id"] = a["episodio_id"].astype("int64")
    a["periodo"] = a["periodo"].astype(str)
    a["j"] = F.slot_vectorizado(a["periodo"], a["episodio_id"].map(base))
    a = a.loc[a["j"].notna() & (a["j"] <= kmax)].copy()
    a["j"] = a["j"].astype("int64")
    marcar_fallas(a)
    a["codigo"] = a["codigo_asignatura"]
    a["cred"] = pd.to_numeric(a["creditos"], errors="coerce").fillna(pd.to_numeric(a["creditos_reconocidos"], errors="coerce")).fillna(0.0)
    heredada = a["nota_es_heredada"].astype(bool)
    a["nota"] = pd.to_numeric(a["nota_numerica"], errors="coerce").where(a["ev_ok"] & ~heredada)
    a["clase_titulo"] = a["titulo"].map(RV.clasificar_titulo)
    attr = atributos.rename(columns={"cod_programa": "cod_carrera", "codigo_asignatura": "codigo"})[
        ["cod_carrera", "catalogo", "codigo", "semestre", "ciclo", "ftipo", "n_pool"]].rename(columns={"semestre": "sem"})
    a = a.merge(attr, on=["cod_carrera", "catalogo", "codigo"], how="left")
    return a[["episodio_id", "j", "codigo", "cod_carrera", "catalogo", "opo", "ev_ok", "aprob", "fail", "cred", "nota",
              "clase_titulo", "sem", "ciclo", "ftipo", "n_pool", "resultado_tipo"]]


def _distintos(m: pd.DataFrame, mascara, nombre: str, clave: str = "cid") -> pd.Series:
    return m.loc[mascara].drop_duplicates([clave, "codigo"]).groupby(clave).size().rename(nombre)


def mascara_rep2(m: pd.DataFrame):
    """Failures in the 2nd opportunity (Art. 46 counts the distinct courses over the career)."""
    return m["fail"] & (m["opo"] == 2)


def mascara_rep3(m: pd.DataFrame):
    """Failures in the 3rd opportunity or later."""
    return m["fail"] & (m["opo"] >= 3)


def conteos_reglamento(m: pd.DataFrame, clave: str = "cid") -> pd.DataFrame:
    """Per ``clave``: ``reg_rep2_total`` (distinct courses failed in the 2nd opportunity) and ``reg_rep3_cursos`` (distinct courses
    failed in the 3rd or later). ``m`` needs ``codigo`` and the columns of ``marcar_fallas``. Shared by the snapshot variables
    (``_features_k``) and by the threshold of the current students (``evaluation.vista_proyeccion``)."""
    return pd.DataFrame({"reg_rep2_total": _distintos(m, mascara_rep2(m), "reg_rep2_total", clave),
                         "reg_rep3_cursos": _distintos(m, mascara_rep3(m), "reg_rep3_cursos", clave)})


def _racha_avance(lt: pd.DataFrame, cut: pd.DataFrame, kmax: int) -> np.ndarray:
    """Consecutive slots, counted back from the cut slot, whose approved/enrolled credit share is under 50 %."""
    idx = pd.MultiIndex.from_frame(lt[["cid", "j"]])
    cid, k = cut["cid"].to_numpy(), cut["k"].to_numpy("int64")
    vivo = np.ones(len(cut), dtype=bool)
    racha = np.zeros(len(cut), dtype="int64")
    for s in range(kmax):
        vivo &= pd.MultiIndex.from_arrays([cid, k - s]).isin(idx)
        racha += vivo
    return racha


def _features_k(cut: pd.DataFrame, a: pd.DataFrame, totales_idx: pd.DataFrame, attr_no_pool: pd.DataFrame,
                fallback: pd.DataFrame) -> pd.DataFrame:
    """Features of the cuts of ONE ``k`` (``cut``: ``cid``, ``episodio_id``, ``k``, ``cod_programa``)."""
    m = cut[["cid", "episodio_id", "k"]].merge(a, on="episodio_id")
    m = m.loc[m["j"] <= m["k"]]
    out = pd.DataFrame(index=pd.Index(cut["cid"].to_numpy(), name="cid"))
    k = int(cut["k"].iloc[0])

    # ---- regulation (P117 / P118) ----
    rep2 = mascara_rep2(m)
    cuentas = conteos_reglamento(m)
    out["reg_rep2_total"] = cuentas["reg_rep2_total"]
    out["reg_rep2_cb"] = _distintos(m, rep2 & (m["ciclo"] == "CB"), "x")
    out["reg_rep2_cp"] = _distintos(m, rep2 & (m["ciclo"] == "CP"), "x")
    out["reg_rep3_cursos"] = cuentas["reg_rep3_cursos"]
    decidido = m.loc[m["aprob"] | m["fail"]].sort_values(["cid", "codigo", "j", "opo"])
    ultimo = decidido.drop_duplicates(["cid", "codigo"], keep="last")
    pend = ultimo.loc[ultimo["fail"]]
    out["reg_pendientes_reprobados"] = pend.groupby("cid").size()
    out["reg_cursos_riesgo_3ra"] = pend.loc[pend["opo"] == 2].groupby("cid").size()
    cols_conteo = ["reg_rep2_total", "reg_rep2_cb", "reg_rep2_cp", "reg_rep3_cursos", "reg_pendientes_reprobados",
                   "reg_cursos_riesgo_3ra"]
    out[cols_conteo] = out[cols_conteo].fillna(0.0)

    con_ciclo = m.loc[m["ciclo"].notna()]
    por_slot = con_ciclo.assign(_cb=(con_ciclo["ciclo"] == "CB").astype("float64")).groupby(["cid", "j"])["_cb"].mean()
    ultimo_slot = por_slot.reset_index().sort_values(["cid", "j"]).drop_duplicates("cid", keep="last").set_index("cid")["_cb"]
    out["reg_ciclo_cb_actual"] = (ultimo_slot > 0.5).astype("float64")
    out["reg_sem_en_cb"] = (por_slot > 0.5).groupby(level="cid").sum().astype("float64")
    out["reg_sem_en_cb"] = out["reg_sem_en_cb"].fillna(0.0)
    cb = out["reg_ciclo_cb_actual"]
    d2_cb = (RV.UMBRAL_2DA_CB_ANTIGUO - out["reg_rep2_cb"]).clip(lower=0)
    d2_cp = (RV.UMBRAL_2DA_CP_ANTIGUO - out["reg_rep2_cp"]).clip(lower=0)
    out["reg_dist_2da_antiguo"] = np.where(cb.isna(), np.nan, np.where(cb == 1, d2_cb, d2_cp))
    out["reg_dist_3ra_antiguo"] = (RV.UMBRAL_3RA_ANTIGUO - out["reg_rep3_cursos"]).clip(lower=0)
    out["reg_dist_2da_nuevo"] = (RV.UMBRAL_2DA_NUEVO - out["reg_rep2_total"]).clip(lower=0)
    out["reg_dist_3ra_nuevo"] = (RV.UMBRAL_3RA_NUEVO - out["reg_rep3_cursos"]).clip(lower=0)

    ev = m.loc[m["ev_ok"] & (m["cred"] > 0)]
    g = ev.assign(cred_apr=ev["cred"].where(ev["aprob"], 0.0)).groupby(["cid", "j"])[["cred", "cred_apr"]].sum()
    lt = g.loc[g["cred_apr"] / g["cred"] < RV.AVANCE_MINIMO].reset_index()[["cid", "j"]]
    out["reg_n_sem_avance_lt50"] = lt.groupby("cid").size()
    out["reg_n_sem_avance_lt50"] = out["reg_n_sem_avance_lt50"].fillna(0.0)
    racha = _racha_avance(lt, cut, k) if len(lt) else np.zeros(len(cut), dtype="int64")
    out["reg_consec_avance_lt50"] = pd.Series(racha, index=cut["cid"].to_numpy(), dtype="float64")
    out["reg_dist_avance_antiguo"] = (RV.PERIODOS_AVANCE_ANTIGUO - out["reg_consec_avance_lt50"]).clip(lower=0)

    # ---- reach (P121) ----
    out["alc_sem_pendiente_antiguo"] = pend.groupby("cid")["sem"].min()
    ult_j = m.groupby("cid")["j"].max()
    en_ultimo = m.loc[m["j"] == m["cid"].map(ult_j)]
    sem_actual = en_ultimo.groupby("cid")["sem"].max()
    out["alc_rezago"] = sem_actual.reindex(out.index) - out["alc_sem_pendiente_antiguo"]
    out["alc_pendiente_gt4"] = (out["alc_rezago"] > RV.ALCANCE_SEMESTRES).fillna(False)
    ult_attempt = m.sort_values(["cid", "j"]).drop_duplicates("cid", keep="last").set_index("cid")[["cod_carrera", "catalogo"]]
    bloq = ult_attempt.join(out["alc_sem_pendiente_antiguo"].dropna()).dropna(subset=["alc_sem_pendiente_antiguo"]).reset_index()
    bloq = bloq.merge(attr_no_pool, left_on=["cod_carrera", "catalogo"], right_on=["cod_programa", "catalogo"])
    bloq = bloq.loc[bloq["semestre"] > bloq["alc_sem_pendiente_antiguo"] + RV.ALCANCE_SEMESTRES]
    aprobados = m.loc[m["aprob"], ["cid", "codigo"]].drop_duplicates().assign(_ya=True)
    bloq = bloq.merge(aprobados, left_on=["cid", "codigo_asignatura"], right_on=["cid", "codigo"], how="left")
    out["alc_n_bloqueados"] = bloq.loc[bloq["_ya"].isna()].groupby("cid").size()
    out["alc_n_bloqueados"] = out["alc_n_bloqueados"].reindex(out.index).fillna(0.0)

    # ---- progress and malla totals (P126) ----
    primera = m.loc[m["aprob"]].sort_values(["cid", "codigo", "j"]).drop_duplicates(["cid", "codigo"])
    cred_aprob = primera.groupby("cid")["cred"].sum().reindex(out.index).fillna(0.0)
    n_slots = m.loc[m["resultado_tipo"] != "renuncia"].groupby("cid")["j"].nunique().reindex(out.index)
    out["velocidad_aprobacion"] = cred_aprob / n_slots.where(n_slots > 0)
    ult_clave = ult_attempt.reindex(out.index)
    claves = pd.DataFrame({"cod_programa": ult_clave["cod_carrera"], "catalogo": ult_clave["catalogo"]})
    en_malla = pd.MultiIndex.from_frame(claves.fillna("")).isin(totales_idx.index)
    fb = fallback.set_index("cid").reindex(out.index)
    for col in ("cod_programa", "catalogo"):
        claves[col] = np.where(en_malla, claves[col].to_numpy(object), fb[col].to_numpy(object))
    tot = totales_idx.reindex(pd.MultiIndex.from_frame(claves.fillna("")))
    for c in ("creditos_malla_total_corr", "malla_creditos_confiable", "malla_tiene_capstone", "malla_tiene_practica"):
        out[c] = tot[c].to_numpy()
    confiable = out["malla_creditos_confiable"].fillna(False).astype(bool)
    out["creditos_restantes"] = np.where(confiable, (out["creditos_malla_total_corr"] - cred_aprob).clip(lower=0), np.nan)
    por_sem = (tot["creditos_malla_total_corr"] / tot["duracion_ref"].where(tot["duracion_ref"] > 0)).to_numpy()
    out["velocidad_relativa"] = np.where(confiable, out["velocidad_aprobacion"] / por_sem, np.nan)

    # ---- Capstone / titulo / practice (P125) ----
    tit = m["clase_titulo"].isin(["capstone", "titulo"])
    pra = m["clase_titulo"] == "practica"
    out["cap_inscrito"] = m.loc[tit].groupby("cid").size().clip(upper=1)
    out["cap_aprobado"] = m.loc[tit & m["aprob"]].groupby("cid").size().clip(upper=1)
    out["prac_inscrita"] = m.loc[pra].groupby("cid").size().clip(upper=1)
    out["prac_aprobada"] = m.loc[pra & m["aprob"]].groupby("cid").size().clip(upper=1)
    for c in ("cap_inscrito", "cap_aprobado", "prac_inscrita", "prac_aprobada"):
        out[c] = out[c].fillna(0.0)

    # ---- own versus general formation ----
    e = m.loc[m["ev_ok"] & (m["resultado_tipo"] == "evaluado")]
    for tipo, suf in (("propia", "propios"), ("general", "generales")):
        x = e.loc[e["ftipo"] == tipo]
        gx = x.groupby("cid")
        out[f"n_{suf}_eval"] = gx.size()
        out[f"tasa_{suf}"] = gx["aprob"].mean()
        out[f"prom_{suf}"] = x.loc[x["nota"].notna()].groupby("cid")["nota"].mean()
        out[f"n_{suf}_eval"] = out[f"n_{suf}_eval"].fillna(0.0)
    out["brecha_propios_generales"] = out["prom_propios"] - out["prom_generales"]
    return out


def _estaticos(cut: pd.DataFrame, totales_idx: pd.DataFrame, fallback: pd.DataFrame) -> pd.DataFrame:
    """Rows without attempts (``k = 0``): only the static malla facts of the admission program and catalogue."""
    tot = totales_idx.reindex(pd.MultiIndex.from_frame(fallback.set_index("cid").reindex(cut["cid"])[["cod_programa", "catalogo"]].fillna("")))
    out = pd.DataFrame(index=pd.Index(cut["cid"].to_numpy(), name="cid"))
    for c in ("creditos_malla_total_corr", "malla_creditos_confiable", "malla_tiene_capstone", "malla_tiene_practica"):
        out[c] = tot[c].to_numpy()
    return out


def _previos(cortes: pd.DataFrame, pop: pd.DataFrame, episodios: pd.DataFrame) -> pd.DataFrame:
    """Earlier undergraduate episodes of the same person (admitted before this one) and how many were admitted by change of program."""
    u = pop[["episodio_id", "persona_key", "periodo_admision"]].rename(columns={"periodo_admision": "adm"})
    e = episodios.loc[episodios["id_nivel"] == 1, ["episodio_id", "persona_key", "periodo_admision", "cod_admision"]].rename(
        columns={"episodio_id": "ep_prev", "periodo_admision": "adm_prev"})
    m = u.merge(e, on="persona_key")
    m = m.loc[(m["ep_prev"] != m["episodio_id"]) & (m["adm_prev"] < m["adm"])]
    g = m.groupby("episodio_id").agg(n_episodios_previos=("ep_prev", "size"), n_cc_previos=("cod_admision", lambda s: int((s == "CC").sum())))
    r = cortes[["episodio_id"]].merge(g, left_on="episodio_id", right_index=True, how="left")
    return r[["n_episodios_previos", "n_cc_previos"]].astype("float64").fillna(0.0)


def construir_variables(cortes: pd.DataFrame, pop: pd.DataFrame, intentos: pd.DataFrame, malla: pd.DataFrame,
                        episodios: pd.DataFrame, prog_cat: pd.DataFrame, kmax: Optional[int] = None) -> pd.DataFrame:
    """The new variables of every cut. ``cortes``: ``episodio_id``, ``k``, ``periodo_admision``, ``cod_programa`` (the program
    in force at the cut); ``pop``: ``episodio_id``, ``persona_key``, ``periodo_admision``, ``cod_programa``,
    ``catalogo_inicial`` (the units of T3); ``intentos`` re-keyed onto the units; ``malla`` with ``semestre_texto``;
    ``episodios``: every episode of the people (``persona_key``, ``periodo_admision``, ``cod_admision``, ``id_nivel``)."""
    c = cortes[["episodio_id", "k", "periodo_admision", "cod_programa"]].reset_index(drop=True).copy()
    c["cid"] = np.arange(len(c))
    kmax = int(kmax if kmax is not None else c["k"].max())
    attrs = atributos_malla(malla)
    totales = totales_malla(malla, prog_cat)
    totales_idx = totales.set_index(["cod_programa", "catalogo"])
    attr_no_pool = attrs.loc[(attrs["n_pool"] == 1) & attrs["semestre"].notna()]
    a = preparar_intentos(intentos, pop, attrs, kmax)
    cat0 = pop.set_index("episodio_id")["catalogo_inicial"]
    fallback = c[["cid", "episodio_id", "cod_programa"]].assign(catalogo=c["episodio_id"].map(cat0).to_numpy())[["cid", "cod_programa", "catalogo"]]
    partes = []
    for k in sorted(c["k"].unique()):
        ck = c.loc[c["k"] == k]
        if k >= 1:
            partes.append(_features_k(ck, a, totales_idx, attr_no_pool, fallback))
        else:
            partes.append(_estaticos(ck, totales_idx, fallback))
    f = pd.concat(partes).reindex(c["cid"].to_numpy())
    for col in VARIABLES_NUEVAS:
        if col not in f.columns:
            f[col] = np.nan
    prev = _previos(c, pop, episodios)
    f["n_episodios_previos"] = prev["n_episodios_previos"].to_numpy()
    f["n_cc_previos"] = prev["n_cc_previos"].to_numpy()
    for col in VARS_BOOL:
        f[col] = f[col].astype("boolean").fillna(False).astype(bool)
    out = pd.concat([c[["episodio_id", "k"]].reset_index(drop=True), f[VARIABLES_NUEVAS].reset_index(drop=True)], axis=1)
    out["episodio_id"] = out["episodio_id"].astype("int64")
    out["k"] = out["k"].astype("int64")
    sin = c["k"].to_numpy() < 1
    for col in VARIABLES_NUEVAS:
        if col in VARS_BOOL or col in ("malla_creditos_confiable", "creditos_malla_total_corr", "n_episodios_previos", "n_cc_previos",
                                       "malla_tiene_capstone", "malla_tiene_practica"):
            continue
        out.loc[sin, col] = np.nan
    return out


# ---------------------------------------------------------------------------------------------
# T6: graduation ranking and the grade of the titulo activity
# ---------------------------------------------------------------------------------------------
def ranking_egreso(d: pd.DataFrame, n_min: int = RV.MIN_PARES_RANKING, ventana: int = 6) -> pd.DataFrame:
    """Share of the graduates of the same program, in the last ``ventana`` semesters up to the own graduation semester (the
    own one included), whose graduation grade is at most the own one. ``NaN`` with fewer than ``n_min`` peers. Graduates of
    later semesters are never read. ``d``: ``episodio_id``, ``cod_programa``, ``ord_egreso``, ``promedio_evaluado``."""
    x = d[["episodio_id", "cod_programa", "ord_egreso", "promedio_evaluado"]].copy()
    x["promedio_evaluado"] = pd.to_numeric(x["promedio_evaluado"], errors="coerce")
    pares = x.merge(x.rename(columns={"episodio_id": "par", "ord_egreso": "ord_par", "promedio_evaluado": "prom_par"}),
                    on="cod_programa")
    pares = pares.loc[(pares["ord_par"] <= pares["ord_egreso"]) & (pares["ord_par"] > pares["ord_egreso"] - ventana)
                      & pares["prom_par"].notna() & pares["promedio_evaluado"].notna()]
    g = pares.groupby("episodio_id").agg(n=("par", "size"), menor=("prom_par", "size"))
    g["menor"] = pares.loc[pares["prom_par"] <= pares["promedio_evaluado"]].groupby("episodio_id").size().reindex(g.index).fillna(0)
    g["ranking_prom_egreso"] = np.where(g["n"] >= n_min, g["menor"] / g["n"], np.nan)
    r = x[["episodio_id"]].merge(g[["ranking_prom_egreso"]], left_on="episodio_id", right_index=True, how="left")
    return r.reset_index(drop=True)


def nota_titulo(intentos: pd.DataFrame, cortes: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    """Grade of the Capstone / titulo activity and of the practice, up to the cut ``k`` of each unit (T6: the graduation
    semester). The LAST evaluated attempt of each kind is used; ``NaN`` when none exists (P125)."""
    atr = pd.DataFrame(columns=["cod_programa", "catalogo", "codigo_asignatura", "semestre", "ciclo", "ftipo", "n_pool"])
    a = preparar_intentos(intentos, pop, atr, int(cortes["k"].max()))
    m = cortes[["episodio_id", "k"]].merge(a, on="episodio_id")
    m = m.loc[(m["j"] <= m["k"]) & m["nota"].notna()].sort_values(["episodio_id", "j"])
    out = cortes[["episodio_id"]].copy()
    for nombre, mask in (("nota_titulo", m["clase_titulo"].isin(["capstone", "titulo"])), ("nota_practica", m["clase_titulo"] == "practica")):
        ult = m.loc[mask].drop_duplicates("episodio_id", keep="last").set_index("episodio_id")["nota"]
        out[nombre] = out["episodio_id"].map(ult).to_numpy()
    return out
