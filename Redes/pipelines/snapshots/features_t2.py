"""Point-in-time construction of the T2 snapshot (one row per evaluated attempt) with pandas.

Inputs are plain DataFrames (loaded by ``t2.py``; tests pass synthetic ones). Nothing here touches a database.

Leakage guard (``tests/unit/test_snapshot_t2.py``): every history feature of an attempt in period ``p`` comes from a
cumulative table looked up with ``merge_asof(..., allow_exact_matches=False)``, i.e. only rows whose period is
STRICTLY earlier than ``p``. The only facts of ``p`` itself that enter are known at enrollment: the course, its
attempt number (``oportunidad``), the roster of the student's courses in ``p`` (load) and the section/teacher.
Changing or deleting any fact with ``periodo >= p`` leaves the features of ``p`` unchanged (tested).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import features as F
from . import rules_t2 as R2

APR = R2.UMBRAL_APROBACION
M = R2.SUAVIZADO_M

FEATURE_COLS_ESTUDIANTE = [
    "k", "prom_acum", "n_notas_acum", "creditos_aprob_acum", "tasa_aprob_acum", "n_reprob_acum",
    "n_intentos_acum", "n_interrupcion", "sem_matriculados", "oportunidad", "n_prev_curso", "mejor_nota_prev_curso",
    "aprobo_antes_curso", "cohorte_anio", "preferencia", "con_postulacion", *F.SCORE_COLS,
]
FEATURE_COLS_CAT_ESTUDIANTE = ["cod_programa", "via_clase", "cod_admision", "sede", "tipo_colegio",
                               "depend_colegio", "region_colegio"]
FEATURE_COLS_CARGA = ["n_cursos_carga", "creditos_carga", "n_repetidos_carga"]
FEATURE_COLS_CURSO = ["creditos", "sem_malla", "en_malla", "desfase", "tasa_hist_curso", "n_hist_curso",
                      "prom_hist_curso", "tasa_hist_curso_suav", "tasa_hist_curso_prog", "n_hist_curso_prog",
                      "tasa_hist_media_carga"]
FEATURE_COLS_CAT_CURSO = ["formacion", "depto"]
FEATURE_COLS_PRERREQ = ["malla_conocida", "info_prereq", "n_prereq", "n_prereq_aprob", "n_prereq_conva",
                        "n_prereq_pend_reprob", "n_prereq_en_carga", "min_nota_prereq", "mean_nota_prereq"]
FEATURE_COLS_DOCENTE = ["tiene_docente", "doc_tasa_suav", "doc_n", "doc_curso_tasa_suav", "doc_curso_n"]
# P117-P127 (18-11-2026): the student's record in the courses of the same department (``cod_depto`` of the grade history) and the
# performance of the previous regular semester with evaluated attempts. Strict past, like every history feature.
FEATURE_COLS_NUEVAS_T2 = ["prom_depto", "n_depto", "dif_prom_depto", "prom_sem_prev", "tasa_sem_prev"]


# ---------------------------------------------------------------------------------------------
# strict-past lookup
# ---------------------------------------------------------------------------------------------
def previo(izq: pd.DataFrame, der: pd.DataFrame, by, cols: List[str], on: str = "per") -> pd.DataFrame:
    """Values of ``cols`` of the latest ``der`` row with the same ``by`` and ``on`` STRICTLY smaller than ``izq``'s.

    ``izq`` must be sorted by ``on``; the result is positionally aligned with ``izq`` (NaN when there is no earlier
    row). ``der`` holds INCLUSIVE cumulative values at each of its (by, on) rows.
    """
    by = [by] if isinstance(by, str) else list(by)
    r = der[by + [on] + cols].sort_values(on, kind="stable")
    out = pd.merge_asof(izq[by + [on]], r, on=on, by=by, allow_exact_matches=False, direction="backward")
    return out[cols].reset_index(drop=True)


def acumulado(eventos: pd.DataFrame, by, sumas: List[str], maximos: Optional[List[str]] = None,
              on: str = "per") -> pd.DataFrame:
    """One row per (by, on): the period sums and the INCLUSIVE running sums / running maxima of the columns."""
    by = [by] if isinstance(by, str) else list(by)
    agg = {c: "sum" for c in sumas}
    agg.update({c: "max" for c in (maximos or [])})
    g = eventos.groupby(by + [on], sort=True).agg(agg).reset_index().sort_values(by + [on], kind="stable")
    gb = g.groupby(by, sort=False)
    for c in sumas:
        g[c] = gb[c].cumsum()
    for c in maximos or []:
        g[c] = gb[c].cummax()
    return g


def _clave(*cols: pd.Series) -> np.ndarray:
    """Combine integer code columns into one int64 key (so ``by`` is a single column)."""
    key = np.zeros(len(cols[0]), dtype="int64")
    for c in cols:
        key = key * np.int64(4_000_003) + c.to_numpy("int64")
    return key


def _suavizar(a: pd.Series, n: pd.Series, prior) -> pd.Series:
    return (a + M * prior) / (n + M)


# ---------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------
def preparar_intentos(intentos: pd.DataFrame, episodios: pd.DataFrame) -> pd.DataFrame:
    """Typed copy with integer period, codes for the large keys and the derived outcome columns."""
    a = intentos.copy()
    a["per"] = a["periodo"].astype(str).astype("int32")
    ev = a["es_intento_evaluado"].fillna(False).astype(bool) & a["nota_numerica"].notna()
    a["ev"] = ev
    a["nota"] = a["nota_numerica"].where(ev).astype("float32")
    a["aprob_ev"] = ev & (a["nota"] >= APR)
    a["repro_ev"] = ev & (a["nota"] < APR)
    apc = a["aprobado_curricular"].fillna(False).astype(bool)
    a["aprob_cur"] = apc
    a["conva"] = (a["resultado_tipo"].astype(str) == "convalidacion") & apc
    a["persona_c"] = pd.factorize(a["persona_key"])[0].astype("int64")
    a["periodo"] = a["periodo"].astype(str)
    a["sin_reprob"] = a["periodo"].isin(R2.PERIODOS_SIN_REPROBACION)
    a["ev_tasa"] = a["ev"] & ~a["sin_reprob"]            # evaluated attempts that feed pass-rate statistics
    a["nrc"] = a["nrc"].astype("object").where(a["nrc"].notna(), None)
    return a


def construir_snapshot_t2(
    episodios: pd.DataFrame,
    intentos: pd.DataFrame,
    estados: pd.DataFrame,
    via: pd.DataFrame,
    malla: pd.DataFrame,
    prereq: pd.DataFrame,
    docentes: pd.DataFrame,
    latest: str,
    deptos: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, List[Dict[str, object]]]:
    """Return ``(snapshot_t2, embudo)``; ``embudo`` lists (step, rows) of the population funnel.

    ``deptos`` (``codigo_asignatura``, ``cod_depto``) is the static department of each course; without it the department variables are NaN.
    """
    pop = F.poblacion(episodios)
    a = preparar_intentos(intentos, episodios)
    embudo: List[Dict[str, object]] = []

    def paso(nombre: str, n: int) -> None:
        embudo.append({"paso": nombre, "n": int(n)})

    # ------------------------------------------------------------------ codes
    codigos = pd.concat([a["codigo_asignatura"], prereq["codigo_requisito"], prereq["codigo_asignatura"],
                         malla["codigo_asignatura"]]).dropna()
    cod_idx = pd.Index(pd.unique(codigos))
    a["codigo_c"] = cod_idx.get_indexer(a["codigo_asignatura"]).astype("int64")
    epi = episodios[["episodio_id", "cod_programa"]].drop_duplicates("episodio_id")
    a = a.merge(epi.rename(columns={"cod_programa": "prog_ep"}), on="episodio_id", how="left")
    prog_idx = pd.Index(pd.unique(episodios["cod_programa"].dropna()))
    a["prog_c"] = prog_idx.get_indexer(a["prog_ep"]).astype("int64")

    # ------------------------------------------------------------------ attempts to predict
    paso("intentos evaluados (nota numerica)", a["ev"].sum())
    reg = a["ev"] & F.es_regular(a["periodo"])
    paso("... en periodo regular (10/20)", reg.sum())
    ven = reg & a["periodo"].map(lambda p: R2.en_ventana(p, latest))
    paso("... en 2015-2025 (periodos cerrados)", ven.sum())
    ven = ven & ~a["sin_reprob"]
    paso("... sin los periodos de reprobacion no registrada (201920, 202010)", ven.sum())
    con_ep = ven & a["episodio_id"].isin(pop["episodio_id"])
    paso("... de un episodio de pregrado (sin IN/PE/IE, con episodio)", con_ep.sum())
    T = a.loc[con_ep].copy()
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    T["k"] = F.slot_vectorizado(T["periodo"], T["episodio_id"].map(base))
    T = T.loc[T["k"].notna() & T["codigo_asignatura"].notna()].copy()
    T["episodio_id"] = T["episodio_id"].astype("int64")
    paso("... en o despues del semestre de admision y con codigo de asignatura", len(T))
    T = T.sort_values(["per", "intento_id"], kind="stable").reset_index(drop=True)
    T["row"] = np.arange(len(T))

    # ------------------------------------------------------------------ course history (expanding, strict past)
    E = a.loc[a["ev_tasa"], ["codigo_c", "prog_c", "per", "nota", "aprob_ev"]].copy()
    E["n"] = 1
    E["a"] = E["aprob_ev"].astype("int64")
    E["s"] = E["nota"].astype("float64")
    cc = acumulado(E, "codigo_c", ["n", "a", "s"])
    h = previo(T, cc, "codigo_c", ["n", "a", "s"]).fillna(0.0)
    glob = acumulado(E.assign(g=0), "g", ["n", "a"])
    gp = previo(T.assign(g=0), glob, "g", ["n", "a"])
    prior_g = (gp["a"] / gp["n"]).fillna(0.8)
    T["n_hist_curso"] = h["n"].to_numpy()
    T["tasa_hist_curso"] = (h["a"] / h["n"].where(h["n"] > 0)).to_numpy()
    T["prom_hist_curso"] = (h["s"] / h["n"].where(h["n"] > 0)).to_numpy()
    T["tasa_hist_curso_suav"] = _suavizar(h["a"], h["n"], prior_g).to_numpy()
    Ep = E.loc[E["prog_c"] >= 0]
    cp = acumulado(Ep.assign(k2=_clave(Ep["codigo_c"], Ep["prog_c"])), "k2", ["n", "a"])
    hp = previo(T.assign(k2=_clave(T["codigo_c"], T["prog_c"].clip(lower=0))), cp, "k2", ["n", "a"]).fillna(0.0)
    T["n_hist_curso_prog"] = hp["n"].to_numpy()
    T["tasa_hist_curso_prog"] = _suavizar(hp["a"], hp["n"], T["tasa_hist_curso_suav"].to_numpy()).to_numpy()

    # ------------------------------------------------------------------ student (episode) history
    S = a.loc[a["episodio_id"].notna()].copy()
    S["episodio_id"] = S["episodio_id"].astype("int64")
    S["ie"] = S["ev_tasa"].astype("int64")
    S["ae"] = (S["ev_tasa"] & S["aprob_cur"]).astype("int64")
    S["re"] = (S["ev_tasa"] & ~S["aprob_cur"]).astype("int64")
    S["nn"] = S["ev_tasa"].astype("int64")
    S["sn"] = S["nota"].where(S["ev_tasa"], 0.0).astype("float64")
    apr = S.loc[S["aprob_cur"]].sort_values(["per", "intento_id"], kind="stable").drop_duplicates(
        ["episodio_id", "codigo_asignatura"])
    S["cred"] = 0.0
    S.loc[apr.index, "cred"] = apr["creditos"].fillna(apr["creditos_reconocidos"]).fillna(0.0).astype("float64")
    st = _estados_acumulados(estados)
    sc = acumulado(S, "episodio_id", ["ie", "ae", "re", "nn", "sn", "cred"])
    hs = previo(T, sc, "episodio_id", ["ie", "ae", "re", "nn", "sn", "cred"]).fillna(0.0)
    T["n_intentos_acum"] = hs["ie"].to_numpy()
    T["n_notas_acum"] = hs["nn"].to_numpy()
    T["n_reprob_acum"] = hs["re"].to_numpy()
    T["creditos_aprob_acum"] = hs["cred"].to_numpy()
    T["prom_acum"] = (hs["sn"] / hs["nn"].where(hs["nn"] > 0)).to_numpy()
    T["tasa_aprob_acum"] = (hs["ae"] / hs["ie"].where(hs["ie"] > 0)).to_numpy()
    hst = previo(T, st, "episodio_id", ["n_int", "n_mat"]).fillna(0.0)
    T["n_interrupcion"] = hst["n_int"].to_numpy()
    T["sem_matriculados"] = hst["n_mat"].to_numpy()

    # ------------------------------------------------------------------ department record and previous regular semester (strict past)
    _nuevas_t2(T, S, deptos)

    # ------------------------------------------------------------------ student x course history (any episode)
    H = a.loc[a["codigo_asignatura"].notna()].copy()
    H["k3"] = _clave(H["persona_c"], H["codigo_c"].clip(lower=0))
    H["pe"] = H["ev"].astype("int64")
    H["pf"] = H["repro_ev"].astype("int64")
    H["pa"] = H["aprob_ev"].astype("int64")
    H["pc"] = H["conva"].astype("int64")
    H["nota_m"] = H["nota"].astype("float64")
    hc = acumulado(H, "k3", ["pe", "pf", "pa", "pc"], ["nota_m"])
    T["k3"] = _clave(T["persona_c"], T["codigo_c"])
    hh = previo(T, hc, "k3", ["pe", "pf", "pa", "pc", "nota_m"])
    T["n_prev_curso"] = hh["pe"].fillna(0.0).to_numpy()
    T["mejor_nota_prev_curso"] = hh["nota_m"].to_numpy()
    T["aprobo_antes_curso"] = ((hh["pa"].fillna(0) + hh["pc"].fillna(0)) > 0).to_numpy()

    # ------------------------------------------------------------------ load in p (known at enrollment)
    T["cred_curso"] = T["creditos"].astype("float64")
    grp = T.groupby(["episodio_id", "per"], sort=False)
    T["n_cursos_carga"] = grp["row"].transform("size").astype("float64")
    T["creditos_carga"] = grp["cred_curso"].transform("sum")
    T["_rep"] = (T["n_prev_curso"] > 0).astype("float64")
    T["n_repetidos_carga"] = T.groupby(["episodio_id", "per"], sort=False)["_rep"].transform("sum")
    T["tasa_hist_media_carga"] = T.groupby(["episodio_id", "per"], sort=False)["tasa_hist_curso_suav"].transform("mean")

    # ------------------------------------------------------------------ malla (static): semester, credits, area
    mm = malla.drop_duplicates(["cod_programa", "catalogo", "codigo_asignatura"])
    T = T.merge(mm[["cod_programa", "catalogo", "codigo_asignatura", "semestre", "creditos", "formacion", "depto"]]
                .rename(columns={"cod_programa": "prog_ep", "semestre": "sem_malla", "creditos": "cred_malla",
                                 "formacion": "formacion_m", "depto": "depto_m"}),
                on=["prog_ep", "catalogo", "codigo_asignatura"], how="left")
    T = T.sort_values("row", kind="stable").reset_index(drop=True)
    T["en_malla"] = T["sem_malla"].notna()
    claves_malla = set(zip(malla["cod_programa"], malla["catalogo"]))
    T["malla_conocida"] = [(p, c) in claves_malla for p, c in zip(T["prog_ep"], T["catalogo"])]
    moda = (malla.groupby("codigo_asignatura").agg(formacion_g=("formacion", _moda), depto_g=("depto", _moda))
            .reset_index())
    T = T.merge(moda, on="codigo_asignatura", how="left").sort_values("row", kind="stable").reset_index(drop=True)
    T["formacion"] = T["formacion_m"].fillna(T["formacion_g"])
    T["depto"] = T["depto_m"].fillna(T["depto_g"])
    T["creditos"] = T["cred_curso"].fillna(T["cred_malla"].astype("float64"))
    T["desfase"] = T["k"] - T["sem_malla"].astype("float64")

    # ------------------------------------------------------------------ explicit prerequisite graph
    _prerrequisitos(T, a, prereq, hc)

    # ------------------------------------------------------------------ teacher / section context (2016+)
    _docentes(T, a, docentes)

    # ------------------------------------------------------------------ pre-entry profile + labels
    adm = F.features_admision(pop, via)
    meta = pop[["episodio_id", "cod_admision", "periodo_admision", "sede", "tipo_qualitas", "sexo"]].copy()
    meta["via_clase"] = meta["tipo_qualitas"].map(lambda q: F.R.via_clase(q if isinstance(q, str) else None))
    meta["sede"] = meta["sede"].map(lambda s: None if pd.isna(s) else str(int(s)) if not isinstance(s, str) else s)
    meta["cohorte_anio"] = meta["periodo_admision"].str.slice(0, 4).astype(int)
    meta = meta.rename(columns={"sexo": "sexo_equidad"}).drop(columns=["tipo_qualitas", "periodo_admision"])
    T = T.merge(adm, on="episodio_id", how="left").merge(meta, on="episodio_id", how="left")
    T["con_postulacion"] = T["con_postulacion"].fillna(False).astype(bool)
    T["cod_programa"] = T["prog_ep"]
    T["split"] = T["periodo"].astype(str).map(R2.split_periodo)
    T["y"] = T["repro_ev"].astype("int8")
    T["banda_nota"] = pd.Series(np.select([T["nota"] < c for c in R2.CORTES_BANDA], list(R2.BANDAS[:-1]),
                                          default=R2.BANDAS[-1]), index=T.index, dtype="object")
    T["k"] = T["k"].astype("int64")
    T["oportunidad"] = pd.to_numeric(T["oportunidad"], errors="coerce").clip(lower=0, upper=6)
    T = T.sort_values("row", kind="stable").reset_index(drop=True)
    return T[SNAPSHOT_COLS_T2].copy(), embudo


def _nuevas_t2(T: pd.DataFrame, S: pd.DataFrame, deptos: Optional[pd.DataFrame]) -> None:
    """Fills ``FEATURE_COLS_NUEVAS_T2`` of ``T`` in place; ``S`` holds every attempt of the episodes with the ``ie/ae/nn/sn`` columns.

    Both lookups go through ``previo`` (strictly earlier periods), so nothing of the attempt's own period or later can enter. Only
    attempts that feed the pass-rate statistics (``ev_tasa``: evaluated and outside the periods without recorded failures) count.
    """
    ev = S.loc[S["ev_tasa"]]
    # previous regular semester: the last regular period before p in which the episode has evaluated attempts
    reg = ev.loc[F.es_regular(ev["periodo"])]
    por_sem = reg.groupby(["episodio_id", "per"], sort=True)[["ie", "ae", "nn", "sn"]].sum().reset_index()
    ps = previo(T, por_sem, "episodio_id", ["ie", "ae", "nn", "sn"])
    T["prom_sem_prev"] = (ps["sn"] / ps["nn"].where(ps["nn"] > 0)).to_numpy()
    T["tasa_sem_prev"] = (ps["ae"] / ps["ie"].where(ps["ie"] > 0)).to_numpy()
    # department record
    nan = np.full(len(T), np.nan)
    if deptos is None or deptos.empty:
        T["prom_depto"], T["n_depto"], T["dif_prom_depto"] = nan, nan, nan
        return
    mapa = deptos.drop_duplicates("codigo_asignatura").set_index("codigo_asignatura")["cod_depto"]
    codigos = pd.Index(pd.unique(mapa.dropna()))
    d_ev = codigos.get_indexer(ev["codigo_asignatura"].map(mapa)).astype("int64")
    d_t = codigos.get_indexer(T["codigo_asignatura"].map(mapa)).astype("int64")
    conocido = d_t >= 0
    E = ev.loc[d_ev >= 0, ["episodio_id", "per", "nota"]].copy()
    E["kd"] = _clave(E["episodio_id"], pd.Series(d_ev[d_ev >= 0], index=E.index))
    E["n"] = 1
    E["s"] = E["nota"].astype("float64")
    cd = acumulado(E, "kd", ["n", "s"])
    Tk = T[["per"]].copy()
    Tk["kd"] = _clave(T["episodio_id"], pd.Series(np.where(conocido, d_t, 0), index=T.index))
    h = previo(Tk, cd, "kd", ["n", "s"])
    n = h["n"].fillna(0.0).to_numpy()
    prom = (h["s"] / h["n"].where(h["n"] > 0)).to_numpy()
    T["n_depto"] = np.where(conocido, n, np.nan)
    T["prom_depto"] = np.where(conocido, prom, np.nan)
    T["dif_prom_depto"] = T["prom_depto"] - T["prom_acum"]


def _moda(s: pd.Series):
    s = s.dropna()
    return s.mode().iloc[0] if len(s) else None


def _estados_acumulados(estados: pd.DataFrame) -> pd.DataFrame:
    """Per (episode, period): running count of interruption states and of enrolled regular periods (inclusive)."""
    e = F._estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna()].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    e["per"] = e["periodo"].astype(str).astype("int32")
    e["n_int"] = (e["clase"] == "interrupcion").astype("int64")
    e["n_mat"] = (e["clase"].isin(F.MATRICULA) & F.es_regular(e["periodo"])).astype("int64")
    # one enrolled regular period counts once even if it has several enrolled states
    e = e.groupby(["episodio_id", "per"], sort=False).agg(n_int=("n_int", "max"), n_mat=("n_mat", "max")).reset_index()
    return acumulado(e, "episodio_id", ["n_int", "n_mat"])


def _prerrequisitos(T: pd.DataFrame, a: pd.DataFrame, prereq: pd.DataFrame, hc: pd.DataFrame) -> None:
    """Fills the explicit prerequisite columns of ``T`` in place (strict past, via the student x course table)."""
    cols = FEATURE_COLS_PRERREQ
    claves_pre = set(zip(prereq["cod_programa"], prereq["catalogo"]))
    T["info_prereq"] = [bool(m) and (p, c) in claves_pre for m, p, c in zip(T["en_malla"], T["prog_ep"], T["catalogo"])]
    pr = prereq[["cod_programa", "catalogo", "codigo_asignatura", "codigo_requisito"]].drop_duplicates()
    edges = T.loc[T["info_prereq"], ["row", "prog_ep", "catalogo", "codigo_asignatura", "persona_c", "per"]].merge(
        pr.rename(columns={"cod_programa": "prog_ep"}), on=["prog_ep", "catalogo", "codigo_asignatura"], how="inner")
    cod_idx = pd.Index(pd.unique(pd.concat([a["codigo_asignatura"], prereq["codigo_requisito"]]).dropna()))
    edges["req_c"] = cod_idx.get_indexer(edges["codigo_requisito"]).astype("int64")
    edges["k3"] = _clave(edges["persona_c"], edges["req_c"])
    edges = edges.sort_values("per", kind="stable").reset_index(drop=True)
    hh = previo(edges, hc, "k3", ["pe", "pf", "pa", "pc", "nota_m"])
    aprob = ((hh["pa"].fillna(0) + hh["pc"].fillna(0)) > 0)
    edges["aprob"] = aprob.to_numpy()
    edges["conva"] = (aprob & (hh["pa"].fillna(0) == 0)).to_numpy()
    edges["pend"] = ((hh["pf"].fillna(0) > 0) & ~aprob).to_numpy()
    edges["nota_req"] = hh["nota_m"].to_numpy()
    carga = _clave(T["persona_c"], T["codigo_c"]) * np.int64(1_000_003) + T["per"].to_numpy("int64")
    ek = _clave(edges["persona_c"], edges["req_c"]) * np.int64(1_000_003) + edges["per"].to_numpy("int64")
    edges["en_carga"] = np.isin(ek, carga)
    g = edges.groupby("row", sort=False).agg(
        n_prereq=("k3", "size"), n_prereq_aprob=("aprob", "sum"), n_prereq_conva=("conva", "sum"),
        n_prereq_pend_reprob=("pend", "sum"), n_prereq_en_carga=("en_carga", "sum"),
        min_nota_prereq=("nota_req", "min"), mean_nota_prereq=("nota_req", "mean"))
    out = pd.DataFrame(index=T["row"].to_numpy())
    for c in cols[2:]:
        out[c] = g[c].reindex(out.index)
    info = T["info_prereq"].to_numpy()
    for c in ("n_prereq", "n_prereq_aprob", "n_prereq_conva", "n_prereq_pend_reprob", "n_prereq_en_carga"):
        v = out[c].fillna(0).to_numpy("float64")           # a course of a known malla with no prerequisite row -> 0
        T[c] = np.where(info, v, np.nan)
    for c in ("min_nota_prereq", "mean_nota_prereq"):
        T[c] = np.where(info, out[c].to_numpy("float64"), np.nan)


def _docentes(T: pd.DataFrame, a: pd.DataFrame, docentes: pd.DataFrame) -> None:
    """Section / teacher historical pass rate (expanding, strict past), only where the offer table has the section."""
    d = docentes.drop_duplicates(["periodo", "nrc", "docente_key"]).copy()
    d["doc_c"] = pd.factorize(d["docente_key"])[0].astype("int64")
    ev = a.loc[a["ev_tasa"] & a["nrc"].notna(), ["periodo", "nrc", "per", "codigo_c", "aprob_ev"]]
    x = ev.merge(d[["periodo", "nrc", "doc_c"]], on=["periodo", "nrc"], how="inner")
    x["n"] = 1
    x["a"] = x["aprob_ev"].astype("int64")
    cd = acumulado(x, "doc_c", ["n", "a"])
    x["k4"] = _clave(x["doc_c"], x["codigo_c"].clip(lower=0))
    cdc = acumulado(x, "k4", ["n", "a"])
    t = T.loc[T["nrc"].notna(), ["row", "periodo", "nrc", "per", "codigo_c"]].merge(
        d[["periodo", "nrc", "doc_c"]], on=["periodo", "nrc"], how="inner")
    t["k4"] = _clave(t["doc_c"], t["codigo_c"])
    t = t.sort_values("per", kind="stable").reset_index(drop=True)
    p1 = previo(t, cd, "doc_c", ["n", "a"]).fillna(0.0)
    p2 = previo(t, cdc, "k4", ["n", "a"]).fillna(0.0)
    t["n1"], t["a1"], t["n2"], t["a2"] = p1["n"].to_numpy(), p1["a"].to_numpy(), p2["n"].to_numpy(), p2["a"].to_numpy()
    g = t.groupby("row", sort=False).agg(n1=("n1", "sum"), a1=("a1", "sum"), n2=("n2", "sum"), a2=("a2", "sum"),
                                        nd=("doc_c", "size"))
    g = g.reindex(T["row"].to_numpy())
    tiene = g["nd"].notna().to_numpy()
    prior = T["tasa_hist_curso_suav"].to_numpy()
    T["tiene_docente"] = tiene
    T["doc_n"] = np.where(tiene, g["n1"].to_numpy(), np.nan)
    T["doc_tasa_suav"] = np.where(tiene, ((g["a1"] + M * prior) / (g["n1"] + M)).to_numpy(), np.nan)
    T["doc_curso_n"] = np.where(tiene, g["n2"].to_numpy(), np.nan)
    T["doc_curso_tasa_suav"] = np.where(tiene, ((g["a2"] + M * prior) / (g["n2"] + M)).to_numpy(), np.nan)


SNAPSHOT_COLS_T2: List[str] = list(dict.fromkeys([
    "intento_id", "episodio_id", "persona_key", "periodo", "cod_programa", "catalogo", "codigo_asignatura", "split", "y",
    "banda_nota",       # P74: grade band of the attempt (label side, never a feature)
    *FEATURE_COLS_ESTUDIANTE, *FEATURE_COLS_CAT_ESTUDIANTE, *FEATURE_COLS_CARGA, *FEATURE_COLS_CURSO,
    *FEATURE_COLS_CAT_CURSO, *FEATURE_COLS_PRERREQ, *FEATURE_COLS_DOCENTE, "sexo_equidad", *F.ADMISION_P47,
    *FEATURE_COLS_NUEVAS_T2,
]))
