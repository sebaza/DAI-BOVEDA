"""New point-in-time variables of T1 requested by the DAI (P117-P127, ``evidencia/viabilidad_variables_2026-11-18.md``).

``features_t1_nuevas`` takes the cut rows, the per-semester table of ``features.tabla_semestres`` and the plain inputs of the T1
snapshot and returns one row per (episode, k). Leakage guards (``tests/unit/test_features_t1_nuevas.py``): every value is computed
from facts of the slots ``<= k`` and from episode states with ``periodo <= periodo_corte`` whose date, when known, is not after the
end of the cut period; changing or deleting any later fact leaves the row unchanged. The malla is static.

Definitions (``j`` = semester slot counted from admission, ``k`` = cut slot):
* ``creditos_aprob_ult_sem``: credits approved for the first time in slot ``k`` (convalidations included, as in ``creditos_aprobados``).
* ``delta_promedio_sem``: average of slot ``k`` minus the average of slot ``k - 1``; ``delta_promedio_acum``: average of slot ``k``
  minus the cumulative average of the slots ``< k``. Averages use evaluated, non-inherited grades. NaN when a term is undefined.
* ``repro_oport2`` / ``repro_oport3``: failed evaluated attempts with ``oportunidad >= 2`` / ``>= 3`` in the slots ``<= k``;
  ``ramos_repetidos``: distinct courses with an attempt of ``oportunidad >= 2`` in the slots ``<= k``.
* ``n_sem_sin_reprob``: slots ``<= k`` in a period without recorded failures (P58: 201920 and 202010); failures there are not
  observable, so the failure counts above undercount for those cuts, as ``reprobados`` already does.
* ``creditos_esperados`` / ``avance_malla`` / ``fraccion_malla``: as in T3 (credits of the malla of the initial catalog up to
  semester ``k``; approved credits over expected and over the whole malla).
* ``ramos_ins_ult`` / ``creditos_ins_ult``: attempts that are not convalidations (renounced ones included: they were enrolled) in slot
  ``k`` and their credits; ``delta_*``: change with respect to slot ``k - 1``.
* ``n_retiro_temporal`` / ``n_anulacion``: distinct periods up to the cut with a state ``P`` / ``A`` (episode states, no system
  corrections); ``sem_desde_ultimo_retiro``: ``k`` minus the slot of the latest ``P`` or ``A``; ``dias_desde_ultimo_retiro``: days from
  the date of that latest state to the end of the cut period (NaN when the date is missing or a future marker).
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from . import features as F
from . import malla_avance as MA
from . import rules as R
from . import rules_t2 as R2

BLOQUES: Dict[str, List[str]] = {
    "rendimiento": ["creditos_aprob_ult_sem", "delta_promedio_sem", "delta_promedio_acum"],
    "oportunidades": ["repro_oport2", "repro_oport3", "ramos_repetidos", "n_sem_sin_reprob"],
    "malla": ["creditos_esperados", "avance_malla", "fraccion_malla"],
    "carga": ["ramos_ins_ult", "delta_ramos_ins", "creditos_ins_ult", "delta_creditos_ins"],
    "retiros": ["n_retiro_temporal", "n_anulacion", "sem_desde_ultimo_retiro", "dias_desde_ultimo_retiro"],
}
COLS_NUEVAS_T1: List[str] = [c for cols in BLOQUES.values() for c in cols]
RETIRO, ANULACION = "P", "A"


def dia_siguiente_al_periodo(periodo: pd.Series) -> pd.Series:
    """First day AFTER the period: ``AAAA10`` ends on 31-07 and ``AAAA20`` on the last day of February of the next year
    (``marts.rules.periodo_de_fecha`` assigns January and February to the previous second semester)."""
    anio = pd.to_numeric(periodo.str.slice(0, 4), errors="coerce")
    es10 = periodo.str.slice(4, 6).le("10").to_numpy()
    texto = np.where(es10, anio.astype("Int64").astype(str).to_numpy() + "-08-01",
                     (anio + 1).astype("Int64").astype(str).to_numpy() + "-03-01")
    return pd.Series(pd.to_datetime(texto, errors="coerce"), index=periodo.index)


def _carga_por_slot(cortes: pd.DataFrame, intentos: pd.DataFrame) -> pd.DataFrame:
    """(episodio_id, j) -> enrolled courses and credits (attempts that are not convalidations)."""
    uni = cortes.drop_duplicates("episodio_id")
    base = pd.Series(F.base_ordinales(uni["periodo_admision"]).to_numpy(), index=uni["episodio_id"].to_numpy())
    a = intentos.loc[intentos["episodio_id"].isin(base.index), ["episodio_id", "periodo", "resultado_tipo", "creditos"]].copy()
    a["j"] = F.slot_vectorizado(a["periodo"], a["episodio_id"].map(base))
    a = a.loc[a["j"].notna() & (a["resultado_tipo"].astype(str) != "convalidacion")].copy()
    a["j"] = a["j"].astype(int)
    a["n"] = 1
    a["c"] = pd.to_numeric(a["creditos"], errors="coerce").fillna(0.0)
    return a.groupby(["episodio_id", "j"], as_index=False)[["n", "c"]].sum()


def _repetidos(cortes: pd.DataFrame, intentos: pd.DataFrame) -> pd.DataFrame:
    """Failures in the second / third opportunity and distinct repeated courses, per (episode, k), slots ``<= k`` only."""
    uni = cortes.drop_duplicates("episodio_id")
    base = pd.Series(F.base_ordinales(uni["periodo_admision"]).to_numpy(), index=uni["episodio_id"].to_numpy())
    a = intentos.loc[intentos["episodio_id"].isin(base.index)].copy()
    a["oportunidad"] = pd.to_numeric(a["oportunidad"], errors="coerce")
    a = a.loc[a["oportunidad"] >= 2, ["episodio_id", "periodo", "codigo_asignatura", "oportunidad", "es_intento_evaluado",
                                       "aprobado_curricular"]].copy()
    a["j"] = F.slot_vectorizado(a["periodo"], a["episodio_id"].map(base))
    a = a.loc[a["j"].notna()].copy()
    fallo = a["es_intento_evaluado"].astype(bool) & ~a["aprobado_curricular"].fillna(False).astype(bool)
    a["f2"] = fallo.astype(int)
    a["f3"] = (fallo & (a["oportunidad"] >= 3)).astype(int)
    m = a.merge(cortes[["episodio_id", "k"]], on="episodio_id")
    m = m.loc[m["j"] <= m["k"]]
    return m.groupby(["episodio_id", "k"]).agg(repro_oport2=("f2", "sum"), repro_oport3=("f3", "sum"),
                                               ramos_repetidos=("codigo_asignatura", "nunique")).reset_index()


def _retiros(cortes: pd.DataFrame, estados: pd.DataFrame) -> pd.DataFrame:
    """Temporary withdrawals (``P``) and annulments (``A``) known at the cut, per (episode, k)."""
    e = F._estados_utiles(estados)
    e = e.loc[e["episodio_id"].notna() & e["cod_estado"].isin([RETIRO, ANULACION])].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    fecha = pd.to_datetime(e["fecha_estado_original"], errors="coerce") if "fecha_estado_original" in e else pd.Series(
        pd.NaT, index=e.index)
    marcador = e["fecha_marcador"].fillna(False).astype(bool) if "fecha_marcador" in e else pd.Series(False, index=e.index)
    e["fecha"] = fecha.where(~marcador)
    m = cortes[["episodio_id", "k", "periodo_corte", "periodo_admision"]].merge(
        e[["episodio_id", "periodo", "cod_estado", "fecha"]], on="episodio_id")
    m = m.loc[m["periodo"] <= m["periodo_corte"]].copy()
    despues = dia_siguiente_al_periodo(m["periodo_corte"])
    m = m.loc[m["fecha"].isna() | (m["fecha"] < despues)].copy()                   # a date after the cut period is not known yet
    if m.empty:
        return pd.DataFrame(columns=["episodio_id", "k", "n_retiro_temporal", "n_anulacion", "sem_desde_ultimo_retiro",
                                     "dias_desde_ultimo_retiro"])
    m["j"] = F.slot_vectorizado(m["periodo"], F.base_ordinales(m["periodo_admision"]))
    m["ultimo_dia"] = dia_siguiente_al_periodo(m["periodo_corte"]) - pd.Timedelta(days=1)
    n = (m.drop_duplicates(["episodio_id", "k", "periodo", "cod_estado"])
         .groupby(["episodio_id", "k", "cod_estado"]).size().unstack(fill_value=0))
    out = pd.DataFrame({"n_retiro_temporal": n[RETIRO] if RETIRO in n else 0, "n_anulacion": n[ANULACION] if ANULACION in n else 0},
                       index=n.index)
    ult = (m.sort_values(["episodio_id", "k", "periodo", "fecha"], na_position="first")
           .groupby(["episodio_id", "k"]).tail(1).set_index(["episodio_id", "k"]).reindex(out.index))
    out["sem_desde_ultimo_retiro"] = (out.index.get_level_values("k").to_numpy() - ult["j"].to_numpy()).astype("float64")
    out["dias_desde_ultimo_retiro"] = (ult["ultimo_dia"] - ult["fecha"]).dt.days.astype("float64")
    return out.reset_index()


def _sem_sin_reprob(cortes: pd.DataFrame) -> np.ndarray:
    base = F.base_ordinales(cortes["periodo_admision"]).to_numpy("float64")
    kk = cortes["k"].to_numpy("int64")
    out = np.zeros(len(kk), dtype="float64")
    for j in range(1, int(kk.max(initial=0)) + 1):
        periodos = [R.ordinal_a_periodo(int(b) + j - 1) if b == b else None for b in base]
        out += np.array([(p in R2.PERIODOS_SIN_REPROBACION) and j <= kj for p, kj in zip(periodos, kk)], dtype="float64")
    return out


def features_t1_nuevas(
    cortes: pd.DataFrame, sem: pd.DataFrame, intentos: pd.DataFrame, estados: pd.DataFrame, malla: pd.DataFrame,
    episodios: pd.DataFrame,
) -> pd.DataFrame:
    """One row per (episode, k) with ``COLS_NUEVAS_T1``.

    ``cortes``: ``episodio_id``, ``k``, ``periodo_corte``, ``periodo_admision``. ``sem``: ``features.tabla_semestres``. ``intentos``
    must carry ``oportunidad`` and ``estados`` may carry ``fecha_estado_original`` / ``fecha_marcador``. ``episodios`` carries
    ``catalogo_inicial``.
    """
    c = cortes[["episodio_id", "k", "periodo_corte", "periodo_admision"]].reset_index(drop=True).copy()
    s = sem.copy()
    s["prom"] = s["sn"] / s["nn"].where(s["nn"] > 0)
    carga = _carga_por_slot(c, intentos)
    s = s.merge(carga.rename(columns={"n": "ins_n", "c": "ins_c"}), on=["episodio_id", "j"], how="left")
    s[["ins_n", "ins_c"]] = s[["ins_n", "ins_c"]].fillna(0.0)
    key = ["episodio_id", "j"]
    ult = c.merge(s[key + ["cred", "prom", "ins_n", "ins_c", "cred_ac"]], left_on=["episodio_id", "k"], right_on=key, how="left")
    pen = c.assign(jp=c["k"] - 1).merge(
        s[key + ["prom", "ins_n", "ins_c"]].rename(columns={"j": "jp", "prom": "prom_p", "ins_n": "n_p", "ins_c": "c_p"}),
        on=["episodio_id", "jp"], how="left")
    prev = s.merge(c[["episodio_id", "k"]], on="episodio_id")
    prev = prev.loc[prev["j"] < prev["k"]].groupby(["episodio_id", "k"]).agg(_sn=("sn", "sum"), _nn=("nn", "sum")).reset_index()
    out = c[["episodio_id", "k"]].copy()
    out["creditos_aprob_ult_sem"] = ult["cred"].to_numpy()
    out["delta_promedio_sem"] = (ult["prom"] - pen["prom_p"]).to_numpy()
    out = out.merge(prev, on=["episodio_id", "k"], how="left")
    prom_prev = out["_sn"] / out["_nn"].where(out["_nn"] > 0)
    out["delta_promedio_acum"] = ult["prom"].to_numpy() - prom_prev.to_numpy()
    out = out.drop(columns=["_sn", "_nn"])
    out["ramos_ins_ult"], out["creditos_ins_ult"] = ult["ins_n"].to_numpy(), ult["ins_c"].to_numpy()
    out["delta_ramos_ins"] = (ult["ins_n"] - pen["n_p"]).to_numpy()
    out["delta_creditos_ins"] = (ult["ins_c"] - pen["c_p"]).to_numpy()

    out = out.merge(_repetidos(c, intentos), on=["episodio_id", "k"], how="left")
    for col in ("repro_oport2", "repro_oport3", "ramos_repetidos"):
        out[col] = out[col].fillna(0.0)
    out["n_sem_sin_reprob"] = _sem_sin_reprob(c)

    out = out.merge(_retiros(c, estados), on=["episodio_id", "k"], how="left")
    for col in ("n_retiro_temporal", "n_anulacion"):
        out[col] = out[col].fillna(0.0)

    cat = episodios.drop_duplicates("episodio_id")[["episodio_id", "cod_programa", "catalogo_inicial"]]
    cmap = MA.creditos_malla(cat, malla, sorted(set(c["k"].tolist()))).set_index("episodio_id")
    esperados = np.full(len(out), np.nan)
    for kk in sorted(set(c["k"].tolist())):
        m = (out["k"] == kk).to_numpy()
        esperados[m] = cmap[f"_ce{kk}"].reindex(out.loc[m, "episodio_id"]).to_numpy("float64")
    out["creditos_esperados"] = esperados
    total = cmap["creditos_malla_total"].reindex(out["episodio_id"]).to_numpy("float64")
    aprob = ult["cred_ac"].to_numpy("float64")
    out["avance_malla"] = aprob / np.where(esperados > 0, esperados, np.nan)
    out["fraccion_malla"] = aprob / np.where(total > 0, total, np.nan)
    return out[["episodio_id", "k", *COLS_NUEVAS_T1]]
