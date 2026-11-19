"""Point-in-time construction of the T4/T5 snapshot ("transicion real de programa" and "eliminacion",
docs/11_benchmark_t4_t5.md) with pandas.

The population, the cuts, the eligibility and every feature are the ones of T3 (``features_t3.construir_snapshot_t3`` with
``ks = (2, 4)``: D47, P58-aware aggregates, program facts in force at the cut), so a row has exactly the T3 features.
This module only adds the label side: the mutually exclusive outcome of the next two regular semesters.

Leakage guards, all covered by ``tests/unit/test_snapshot_t45.py``:
* the features are the T3 features (slots ``<= k``); labels and the transfers table never feed a feature;
* an event counts only inside the slots ``k + 1 .. k + 2`` (a transfer already started at the cut is known at the cut and
  makes the row ineligible, as D24 does for an exit state in the cut period);
* a row whose horizon period is not closed is kept as ``censurado`` and never used by a model.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from . import features as F
from . import features_t3 as F3
from . import rules as R
from . import rules_t3 as R3
from . import rules_t45 as R45

CLASE_DE_ESTADO = F.CLASE_DE_ESTADO
# P71 (stage B): the moment of a transfer is the EXIT from the origin program, its last period (``ultimo_periodo_origen``);
# the first period of the destination is only used to know whether the transfer had already started at the cut (D53).
COLS_TRASLADOS = ["origen_episodio_id", "destino_episodio_id", "tipo", "ambiguo", "primer_periodo_destino", "ultimo_periodo_origen"]
KEYS = ["episodio_id", "k", "persona_key", "cod_programa", "periodo_admision", "cohorte_anio", "split"]
LABELS = ["seguimiento_max", "resultado", "otra_salida_tipo", "hubo_transicion_en_horizonte",
          "hubo_eliminacion_en_horizonte",
          # P72 / P75: an E inside the horizon followed (or not) by I/Y inside it; the horizon touches periods >= 202420
          "eliminacion_con_reintegro", "eliminacion_efectiva", "horizonte_e_dudoso"]
AUDIT = ["episodio_especialidad_id"]       # the Plan Comun link is decided with the future: never a feature
LABEL_COLS_T45 = set(LABELS + AUDIT)
_NO_FEATURE = {*KEYS, *F3.LABEL_COLS}
FEATURE_COLS_T45: List[str] = [c for c in F3.SNAPSHOT_COLS_T3 if c not in _NO_FEATURE]
SNAPSHOT_COLS_T45: List[str] = KEYS + LABELS + AUDIT + FEATURE_COLS_T45


# ---------------------------------------------------------------------------------------------
# vectorized outcome (mirror of rules_t45.resolver_resultado; equality is tested on a grid)
# ---------------------------------------------------------------------------------------------
def resolver_resultados(d: pd.DataFrame) -> pd.Series:
    """Vectorized ``rules_t45.resolver_resultado``: columns ``k``, ``t_egreso``, ``t_eliminacion``, ``t_transicion``,
    ``t_ambigua``, ``matriculado_h``, ``t_max``."""
    k = d["k"].to_numpy("float64")
    h = k + R45.HORIZONTE_SEMESTRES
    t = np.column_stack([d[c].to_numpy("float64") for c in ("t_egreso", "t_eliminacion", "t_transicion", "t_ambigua")])
    with np.errstate(invalid="ignore"):
        dentro = (t > k[:, None]) & (t <= h[:, None])
    primero = np.where(dentro, t, np.inf).argmin(axis=1)          # first minimum: ties follow ORDEN_PRECEDENCIA
    nombres = np.array(R45.ORDEN_PRECEDENCIA, dtype=object)
    sin_evento = np.where(d["matriculado_h"].to_numpy(bool), "continua", "otra_salida").astype(object)
    out = np.where(dentro.any(axis=1), nombres[primero], sin_evento)
    out = np.where(d["t_max"].to_numpy("float64") < h, "censurado", out)
    return pd.Series(out, index=d.index, dtype="object")


# ---------------------------------------------------------------------------------------------
# transfers re-keyed onto the T3 units
# ---------------------------------------------------------------------------------------------
def traslados_por_unidad(traslados: pd.DataFrame, vinculos: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    """Transfers whose origin episode belongs to a unit (a linked specialty belongs to its Plan Comun unit).

    Returns ``unidad``, ``origen_episodio_id``, ``tipo``, ``ambiguo``, ``primer_periodo_destino``, ``ultimo_periodo_origen``
    (the exit from the origin; the first destination period when it is unknown) and ``clase`` (``transicion`` /
    ``transicion_ambigua`` for the types that leave the program, else NaN).
    """
    cols = ["unidad", "origen_episodio_id", "tipo", "ambiguo", "primer_periodo_destino", "ultimo_periodo_origen", "clase"]
    if traslados is None or traslados.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in cols}).astype({"unidad": "int64", "origen_episodio_id": "int64"})
    t = traslados[COLS_TRASLADOS].copy()
    t["ultimo_periodo_origen"] = t["ultimo_periodo_origen"].where(t["ultimo_periodo_origen"].notna(), t["primer_periodo_destino"])
    t["origen_episodio_id"] = t["origen_episodio_id"].astype("int64")
    mapa = dict(zip(vinculos["episodio_esp"].astype(int), vinculos["episodio_id"].astype(int)))
    t["unidad"] = t["origen_episodio_id"].map(mapa).fillna(t["origen_episodio_id"]).astype("int64")
    t = t.loc[t["unidad"].isin(pop["episodio_id"].to_numpy())].copy()
    t["ambiguo"] = t["ambiguo"].astype(bool)
    t["clase"] = [R45.clase_traslado(a, b) for a, b in zip(t["tipo"], t["ambiguo"])]
    return t[cols].reset_index(drop=True)


def _minimo_en_horizonte(filas: pd.DataFrame, hechos: pd.DataFrame, desde: int = 0, hasta: int = None) -> np.ndarray:
    """Smallest slot of ``hechos`` (columns ``episodio_id``, ``slot``) inside ``(k + desde, k + hasta]`` per row (NaN if none)."""
    hasta = R45.HORIZONTE_SEMESTRES if hasta is None else hasta
    if hechos.empty:
        return np.full(len(filas), np.nan)
    m = filas[["rid", "episodio_id", "k"]].merge(hechos[["episodio_id", "slot"]], on="episodio_id")
    m = m.loc[(m["slot"] > m["k"] + desde) & (m["slot"] <= m["k"] + hasta)]
    return m.groupby("rid")["slot"].min().reindex(filas["rid"]).to_numpy("float64")


def _estados_con_slot(est: pd.DataFrame, base: pd.Series) -> pd.DataFrame:
    e = F._estados_utiles(est)
    e = e.loc[e["episodio_id"].notna()].copy()
    e["episodio_id"] = e["episodio_id"].astype("int64")
    e = e.loc[e["episodio_id"].isin(base.index)].copy()
    e["slot"] = F.slot_vectorizado(e["periodo"], e["episodio_id"].map(base))
    return e.loc[e["slot"].notna()]


def _con_reintegro(filas: pd.DataFrame, elim: pd.DataFrame, reint: pd.DataFrame) -> np.ndarray:
    """P72: per row, is the FIRST ``E`` inside ``(k, k + h]`` followed by an I/Y inside ``(slot of the E, k + h]`` (same slot:
    recorded after the ``E``)? Rows without an ``E`` in the horizon give ``False``. Uses only slots up to ``k + h``."""
    h = R45.HORIZONTE_SEMESTRES
    if elim.empty:
        return np.zeros(len(filas), dtype=bool)
    m = filas[["rid", "episodio_id", "k"]].merge(elim[["episodio_id", "slot", "orden_canonico"]], on="episodio_id")
    m = m.loc[(m["slot"] > m["k"]) & (m["slot"] <= m["k"] + h)]
    primera = m.sort_values(["rid", "slot", "orden_canonico"]).drop_duplicates("rid")
    r = primera.merge(reint[["episodio_id", "slot", "orden_canonico"]].rename(
        columns={"slot": "r_slot", "orden_canonico": "r_orden"}), on="episodio_id")
    seguido = (r["r_slot"] <= r["k"] + h) & ((r["r_slot"] > r["slot"]) | (
        (r["r_slot"] == r["slot"]) & (r["r_orden"] > r["orden_canonico"])))
    return np.isin(filas["rid"].to_numpy(), r.loc[seguido, "rid"].to_numpy())


def etiquetar_t45(filas: pd.DataFrame, pop: pd.DataFrame, est: pd.DataFrame, h: pd.DataFrame, tr_u: pd.DataFrame) -> pd.DataFrame:
    """Label side of the eligible (unit, k) rows; ``filas`` needs ``episodio_id``, ``k``, ``persona_key``,
    ``periodo_admision`` and keeps its index in the result."""
    f = filas[["episodio_id", "k", "persona_key", "periodo_admision"]].copy()
    f["rid"] = np.arange(len(f))
    base = pd.Series(F.base_ordinales(pop["periodo_admision"]).to_numpy(), index=pop["episodio_id"].to_numpy())
    e = _estados_con_slot(est, base)
    elim = e.loc[e["cod_estado"].isin(R45.CODIGOS_ELIMINACION)]
    explicita = e.loc[(e["clase"] == "salida") & ~e["cod_estado"].isin(R45.CODIGOS_ELIMINACION)]
    interr = e.loc[e["clase"] == "interrupcion"]
    reint = e.loc[e["cod_estado"].isin(R45.CODIGOS_REINTEGRO)]

    # transfers: slot of the first period of the destination, on the scale of the unit
    t = tr_u.loc[tr_u["clase"].notna()].copy()
    t["episodio_id"] = t["unidad"].astype("int64")
    vacio = pd.Series(dtype="float64")
    # event date (P71): the exit from the origin program; destination start: only to know what the cut already shows (D53)
    t["slot"] = F.slot_vectorizado(t["ultimo_periodo_origen"], t["episodio_id"].map(base)) if len(t) else vacio
    t["slot_destino"] = F.slot_vectorizado(t["primer_periodo_destino"], t["episodio_id"].map(base)) if len(t) else vacio
    t = t.loc[t["slot"].notna() & t["slot_destino"].notna()]
    ciertas, ambiguas = t.loc[t["clase"] == "transicion"], t.loc[t["clase"] == "transicion_ambigua"]
    # a countable transfer whose destination started at or before the cut is already known at the cut
    ya = f[["rid", "episodio_id", "k"]].merge(t[["episodio_id", "slot_destino"]], on="episodio_id")
    iniciada = np.isin(f["rid"].to_numpy(), ya.loc[ya["slot_destino"] <= ya["k"], "rid"].to_numpy())
    # audit: a certain transfer whose exit is dated at (or before) the cut while its destination starts inside the horizon;
    # the former dating would have called it a transition, the exit dating does not (P71)
    en_corte = f[["rid", "episodio_id", "k"]].merge(ciertas[["episodio_id", "slot", "slot_destino"]], on="episodio_id")
    en_corte = en_corte.loc[(en_corte["slot"] <= en_corte["k"]) & (en_corte["slot_destino"] > en_corte["k"])
                            & (en_corte["slot_destino"] <= en_corte["k"] + R45.HORIZONTE_SEMESTRES)]
    fechado_en_corte = np.isin(f["rid"].to_numpy(), en_corte["rid"].to_numpy())

    out = pd.DataFrame(index=f.index)
    out["t_egreso"] = h["t_egreso"].reindex(f["episodio_id"]).to_numpy("float64")
    out["t_max"] = h["t_max"].reindex(f["episodio_id"]).to_numpy("float64")
    out["k"] = f["k"].to_numpy()
    out["t_eliminacion"] = _minimo_en_horizonte(f, elim)
    out["t_transicion"] = _minimo_en_horizonte(f, ciertas)
    out["t_ambigua"] = _minimo_en_horizonte(f, ambiguas)
    out["t_salida_explicita"] = _minimo_en_horizonte(f, explicita)
    out["t_interrupcion"] = _minimo_en_horizonte(f, interr)
    out["t_transicion_despues"] = _minimo_en_horizonte(f, ciertas, R45.HORIZONTE_SEMESTRES, R45.HORIZONTE_SEMESTRES + R3.VENTANA_VINCULO_PERIODOS)

    # enrolled at the horizon period in ANY program of the person (T1, D31)
    mat = F._estados_utiles(est)
    mat = mat.loc[mat["clase"].isin(F.MATRICULA) & F.es_regular(mat["periodo"]), ["persona_key", "periodo"]].drop_duplicates()
    mat["_m"] = True
    per_h = [R.ordinal_a_periodo(int(b) + int(k) + R45.HORIZONTE_SEMESTRES - 1)
             for b, k in zip(F.base_ordinales(f["periodo_admision"]).to_numpy(), f["k"].to_numpy())]
    q = pd.DataFrame({"persona_key": f["persona_key"].to_numpy(), "periodo": per_h})
    out["matriculado_h"] = q.merge(mat, on=["persona_key", "periodo"], how="left")["_m"].notna().to_numpy()

    out["resultado"] = resolver_resultados(out)
    observable = out["resultado"] != "censurado"
    out["hubo_transicion_en_horizonte"] = observable & out["t_transicion"].notna()
    out["hubo_eliminacion_en_horizonte"] = observable & out["t_eliminacion"].notna()
    con = _con_reintegro(f, elim, reint)
    out["eliminacion_con_reintegro"] = out["hubo_eliminacion_en_horizonte"].to_numpy() & con
    out["eliminacion_efectiva"] = out["hubo_eliminacion_en_horizonte"].to_numpy() & ~con
    out["horizonte_e_dudoso"] = observable.to_numpy() & np.array([R45.horizonte_e_dudoso(p) for p in per_h], dtype=bool)
    tipo = np.where(out["t_salida_explicita"].notna(), "salida_explicita",
                    np.where(out["t_interrupcion"].notna(), "interrupcion", "ausencia"))
    out["otra_salida_tipo"] = pd.Series(np.where(out["resultado"] == "otra_salida", tipo, None), index=out.index, dtype="object")
    out["seguimiento_max"] = out["t_max"].astype("int64")
    out["transicion_iniciada"] = iniciada
    out["traslado_fechado_en_el_corte"] = fechado_en_corte
    return out


def _embudo_k(k: int, r3: Dict, etq: pd.DataFrame) -> Dict:
    d = etq.loc[etq["k"] == k]
    row = {kk: v for kk, v in r3.items() if kk != "elegibles"}
    row["elegibles_t3"] = r3["elegibles"]
    row["transicion_iniciada_en_corte"] = int(d["transicion_iniciada"].sum())
    d = d.loc[~d["transicion_iniciada"]]
    row["traslado_fechado_en_el_corte"] = int(d["traslado_fechado_en_el_corte"].sum())
    row["elegibles"] = int(len(d))
    row["censurados"] = int((d["resultado"] == "censurado").sum())
    for c in R45.RESULTADOS:
        row[f"n_{c}"] = int((d["resultado"] == c).sum())
    obs = d["resultado"] != "censurado"
    row["eliminacion_y_transicion"] = int((d["hubo_transicion_en_horizonte"] & d["hubo_eliminacion_en_horizonte"]).sum())
    row["eliminacion_con_matricula_al_horizonte"] = int(((d["resultado"] == "eliminacion") & d["matriculado_h"]).sum())
    posterior = obs & (d["resultado"] != "transicion") & d["t_transicion_despues"].notna()
    row["transicion_en_los_dos_semestres_posteriores"] = int(posterior.sum())
    row["otra_salida_con_transicion_posterior"] = int((posterior & (d["resultado"] == "otra_salida")).sum())
    return row


def construir_snapshot_t45(
    episodios: pd.DataFrame,
    estados: pd.DataFrame,
    intentos: pd.DataFrame,
    via: pd.DataFrame,
    egreso_titulacion: pd.DataFrame,
    malla: pd.DataFrame,
    prog_cat: pd.DataFrame,
    traslados: pd.DataFrame,
    latest: str,
    ks: Sequence[int] = R45.KS,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict]]:
    """Full snapshot: ``(snapshot_t45, snapshot_t45_semestre, embudo)``.

    ``traslados`` has the columns ``COLS_TRASLADOS`` (``neural_mart.programa_traslados``).
    """
    snap3, sem, emb3 = F3.construir_snapshot_t3(episodios, estados, intentos, via, egreso_titulacion, malla, prog_cat,
                                                latest, ks)
    u = F3.unidades_t3(episodios, estados, egreso_titulacion)
    pop, est = u.pop, u.estados
    h = F3.hechos_episodio(pop, est, u.egreso, latest)
    tr_u = traslados_por_unidad(traslados, u.vinculos, pop)
    etq = etiquetar_t45(snap3, pop, est, h, tr_u)
    etq["k"] = snap3["k"].to_numpy()
    embudo = [_embudo_k(r["k"], r, etq) for r in emb3]
    snap = snap3.drop(columns=[c for c in F3.LABEL_COLS if c in snap3.columns and c != "episodio_especialidad_id"]).copy()
    snap = snap.drop(columns=["split"])
    for c in ("resultado", "otra_salida_tipo", "hubo_transicion_en_horizonte", "hubo_eliminacion_en_horizonte", "seguimiento_max",
              "eliminacion_con_reintegro", "eliminacion_efectiva", "horizonte_e_dudoso"):
        snap[c] = etq[c].to_numpy()
    snap["split"] = snap["cohorte_anio"].map(R45.split_cohorte)
    snap = snap.loc[~etq["transicion_iniciada"].to_numpy()].reset_index(drop=True)
    snap = snap[SNAPSHOT_COLS_T45].copy()
    sem = sem.loc[sem["episodio_id"].isin(snap["episodio_id"].unique())].copy()
    return snap, sem, embudo
