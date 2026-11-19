"""Leakage of the final view of the student benefits measured against the point-in-time view built from the load history
(16-11-2026, D96-D98; AGGREGATES only: no person, RUT or amount is written).

Questions answered, for the years that have load history (2024 onwards; ``rules_beneficios_cargas.anios_con_historial``):

1. ``filas_por_corte``: how many rows of the final view did not exist at the cut (late), how many rows visible at the cut were
   retired afterwards, and how many visible rows have a gap in their loads.
2. ``leakage``: presence of a benefit row, gratuity, credit and first-semester amount in the final view and in the point-in-time view,
   for the people who continue against those who do not (the same definitions as ``diagnostico_beneficios``), plus the admission-year
   students who leave during the year (k = 1).
3. ``p91``: why are rows retired? Each retired row is classified by what the same person has in the same program and year in the
   final view: a row of the same family that appeared AFTER the retirement (a replacement), a row of the same family that already
   coexisted, a row of another family, or nothing. The classes are crossed with what the person does (continues or not; stays or
   leaves during the admission year).

``python -m evaluation.diagnostico_beneficios_cargas`` reads the local dev DB only and writes
``artefactos/diagnostico_beneficios_cargas_t1.json`` (gitignored).
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from pipelines.snapshots import features_beneficios_cargas as FC
from pipelines.snapshots import rules_beneficios as RB
from pipelines.snapshots import rules_beneficios_cargas as RC

N_MIN = 30
ANIOS = (2024, 2025, 2026)
CREDITO = ("C_1_AC", "C_70_AC")                      # the same flags as ``diagnostico_beneficios.Q_DIAGNOSTICO``
COLUMNAS = ["tiene_fila", "grat", "cred", "s1_pos"]


# ---------------------------------------------------------------------------------------------------- row flags
def familia(codigo: Optional[str]) -> str:
    """Family key of a benefit code: the family of ``rules_beneficios`` or, outside the four families, the kind of benefit."""
    c = RB.clasificar(codigo)
    if c["familia"]:
        return c["familia"]
    for clave, etiqueta in (("merito", "merito"), ("merito_e1", "merito"), ("decil", "decil"), ("expiro", "expiracion"),
                            ("capstone", "capstone")):
        if c[clave]:
            return etiqueta
    return "otro:" + (codigo or "")[:5].upper()


def agregar_flags(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    cod = d["codigo"].fillna("").str.upper()
    d["grat"] = (cod.str.startswith("GG_94") | cod.str.startswith("GU_00")).astype(int)
    d["cred"] = cod.isin(CREDITO).astype(int)
    d["s1_pos"] = (pd.to_numeric(d["sem1_primera"], errors="coerce").fillna(0) > 0).astype(int)
    return d


def indicadores_por_corte(c: pd.DataFrame, filas: pd.DataFrame) -> pd.DataFrame:
    """Per cut row: does the person have a row (``tiene_fila``), gratuity, credit and a positive first-semester amount in ``filas``?"""
    f = agregar_flags(filas)
    g = f.groupby("_fila", as_index=False).agg(grat=("grat", "max"), cred=("cred", "max"), s1_pos=("s1_pos", "max"), n=("grat", "size"))
    out = c[["_fila"]].merge(g, on="_fila", how="left")
    out["tiene_fila"] = out["n"].notna().astype(int)
    for col in ("grat", "cred", "s1_pos"):
        out[col] = out[col].fillna(0).astype(int)
    return out[["_fila", *COLUMNAS]]


def _ultima(cargas_df: pd.DataFrame, c: pd.DataFrame) -> pd.DataFrame:
    """Final-view rows (present in the last load) joined to the cuts of the same person, program and year."""
    fin = cargas_df.loc[cargas_df["presente_ultima_carga"]]
    m = c[["_fila", "persona_key", "cod_programa", "_t"]].merge(
        fin.rename(columns={"cod_carrera": "cod_programa", "periodo": "_t"}), on=["persona_key", "cod_programa", "_t"], how="inner")
    return m


def _tasas(d: pd.DataFrame, cols: Sequence[str]) -> Dict:
    return {"n": int(len(d)), **{c: float(d[c].mean()) for c in cols}}


def tabla_resultado(df: pd.DataFrame, cols: Sequence[str], n_min: int = N_MIN) -> Dict:
    """Continue / do not continue rates of ``cols`` and the gap (continue - not) for one view."""
    r: Dict = {}
    for nombre, m in (("continua", df["continua"].astype(bool)), ("no_continua", ~df["continua"].astype(bool))):
        sub = df.loc[m]
        r[nombre] = _tasas(sub, cols) if len(sub) >= n_min else None
    r["brecha"] = {c: r["continua"][c] - r["no_continua"][c] for c in cols} if r["continua"] and r["no_continua"] else None
    return r


def tabla_salida_en_el_anio(df: pd.DataFrame, cols: Sequence[str], n_min: int = N_MIN) -> Dict:
    """Admission-year students enrolled in the first semester: those who stay enrolled in the second against those who leave."""
    r: Dict = {}
    for nombre, m in (("se_queda", df["matriculado_2"].astype(bool)), ("sale", ~df["matriculado_2"].astype(bool))):
        sub = df.loc[m]
        r[nombre] = _tasas(sub, cols) if len(sub) >= n_min else None
    r["brecha"] = {c: r["se_queda"][c] - r["sale"][c] for c in cols} if r["se_queda"] and r["sale"] else None
    return r


def leakage(snap: pd.DataFrame, cargas: pd.DataFrame, cal: Dict[int, np.ndarray]) -> Dict:
    """Final view against point-in-time view for the observed T1 rows whose cut year has load history."""
    c = FC.carga_de_corte(snap, cal)
    c = c.merge(snap[["episodio_id", "k", "continua", "periodo_admision", "matriculado_2"]], on=["episodio_id", "k"], how="left")
    c = c.loc[c["_con_historial"]].reset_index(drop=True)
    vis = FC.filas_visibles(c, cargas)
    pit = indicadores_por_corte(c, vis)
    fin = indicadores_por_corte(c, _ultima(cargas, c))
    base = c[["_fila", "k", "_t", "continua", "periodo_admision", "matriculado_2"]]
    d_pit, d_fin = base.merge(pit, on="_fila"), base.merge(fin, on="_fila")
    out: Dict = {"columnas": COLUMNAS, "n_filas": int(len(base)), "por_k": [], "por_k_y_anio": [], "salida_en_el_anio": {}}
    for k in sorted(base["k"].unique()):
        sel_f, sel_p = d_fin[d_fin["k"] == k], d_pit[d_pit["k"] == k]
        out["por_k"].append({"k": int(k), "vista_final": tabla_resultado(sel_f, COLUMNAS), "punto_en_el_tiempo": tabla_resultado(sel_p, COLUMNAS)})
        for t in sorted(sel_f["_t"].unique()):
            out["por_k_y_anio"].append({"k": int(k), "anio": int(t), "vista_final": tabla_resultado(sel_f[sel_f["_t"] == t], COLUMNAS),
                                        "punto_en_el_tiempo": tabla_resultado(sel_p[sel_p["_t"] == t], COLUMNAS)})
    adm1 = base["k"].eq(1) & base["periodo_admision"].str.slice(4, 6).eq("10") & base["matriculado_2"].notna()
    out["salida_en_el_anio"] = {"vista_final": tabla_salida_en_el_anio(d_fin[adm1.to_numpy()], COLUMNAS),
                                "punto_en_el_tiempo": tabla_salida_en_el_anio(d_pit[adm1.to_numpy()], COLUMNAS)}
    return out


# ---------------------------------------------------------------------------------------------------- rows at the cut
def filas_por_corte(cargas: pd.DataFrame, cal: Dict[int, np.ndarray], anios: Sequence[int] = ANIOS) -> List[Dict]:
    """For each (year, cut date): rows of the final view, rows visible at the cut, and how they differ (all rows of the history)."""
    ultimo_ts = max(int(v[-1]) for v in cal.values())
    historial = RC.anios_con_historial({a: int(v[0]) for a, v in cal.items() if len(v)})
    res = []
    for a in anios:
        if a not in cal or not historial.get(a, False):
            continue
        d = cargas.loc[cargas["periodo"] == a]
        cals = cal[a]
        for nombre, (mes, dia) in (("fin_primer_semestre", RC.CORTE_SEM1), ("fin_del_anio", RC.CORTE_CIERRE)):
            import datetime as dt
            corte_ts = RC.ts_fin_del_dia(dt.date(a, mes, dia))
            if corte_ts > ultimo_ts:
                res.append({"anio": a, "corte": nombre, "disponible": False})
                continue
            L = RC.ultima_carga_hasta(cals, corte_ts)
            if L is None:
                res.append({"anio": a, "corte": nombre, "disponible": False})
                continue
            first, last = d["first_ts"].to_numpy("int64"), d["last_ts"].to_numpy("int64")
            vis = (first <= L) & (L <= last)
            fin = d["presente_ultima_carga"].to_numpy(bool)
            esperado = np.searchsorted(cals, last, side="right") - np.searchsorted(cals, first, side="left")
            hueco = d["n_loads"].to_numpy("int64") < esperado
            s1 = pd.to_numeric(d["sem1_primera"], errors="coerce").fillna(0).to_numpy() != pd.to_numeric(d["sem1_ultima"], errors="coerce").fillna(0).to_numpy()
            res.append({"anio": a, "corte": nombre, "disponible": True, "fecha_carga_del_corte": str(RC.ts_a_fecha(L)),
                        "filas_vista_final": int(fin.sum()), "filas_visibles_al_corte": int(vis.sum()),
                        "visibles_que_siguen_en_la_final": int((vis & fin).sum()),
                        "finales_aun_no_cargadas": int((fin & ~vis).sum()),
                        "visibles_retiradas_despues": int((vis & ~fin).sum()),
                        "visibles_con_hueco_de_cargas": int((vis & hueco).sum()),
                        "visibles_con_monto_s1_distinto_al_final": int((vis & fin & s1).sum())})
    return res


# ---------------------------------------------------------------------------------------------------- P91
CLASES_P91 = ("reemplazo_misma_familia", "misma_familia_ya_existia", "otra_familia", "sin_filas")


def clasificar_retiradas(cargas: pd.DataFrame, anios: Sequence[int] = ANIOS) -> pd.DataFrame:
    """One row per retired benefit row (not in the last load) of the years with history, with its class and its person key.

    Classes (what the same person-program-year has in the final view): ``reemplazo_misma_familia`` (a row of the same family whose
    first load is later than the retired row's last load), ``misma_familia_ya_existia`` (the same family but it already existed),
    ``otra_familia`` (only rows of other families) and ``sin_filas`` (no row at all in the final view for that person, program, year).
    """
    d = cargas.loc[cargas["periodo"].isin(list(anios))].copy()
    codigos = {c: familia(c) for c in d["codigo"].dropna().unique()}
    d["familia"] = d["codigo"].map(lambda c: codigos.get(c, familia(c)))
    clave = ["persona_key", "cod_carrera", "periodo"]
    ret = d.loc[~d["presente_ultima_carga"], clave + ["familia", "first_ts", "last_ts", "codigo"]].reset_index(drop=True)
    fin = d.loc[d["presente_ultima_carga"], clave + ["familia", "first_ts", "codigo"]]
    n_fin = fin.groupby(clave).size().rename("n_final").reset_index()
    ret = ret.merge(n_fin, on=clave, how="left")
    ret["n_final"] = ret["n_final"].fillna(0).astype(int)
    m = ret[clave + ["familia", "last_ts"]].reset_index().merge(fin.rename(columns={"first_ts": "f_first"})[clave + ["familia", "f_first"]],
                                                                 on=clave + ["familia"], how="inner")
    m["despues"] = m["f_first"] > m["last_ts"]
    por = m.groupby("index").agg(hay_misma=("despues", "size"), hay_despues=("despues", "max"))
    ret = ret.join(por)
    ret["hay_misma"] = ret["hay_misma"].fillna(0).astype(int) > 0
    ret["hay_despues"] = ret["hay_despues"].eq(True)
    ret["clase"] = np.where(ret["hay_despues"], "reemplazo_misma_familia",
                            np.where(ret["hay_misma"], "misma_familia_ya_existia",
                                     np.where(ret["n_final"] > 0, "otra_familia", "sin_filas")))
    return ret


def p91(cargas: pd.DataFrame, snap: pd.DataFrame, anios: Sequence[int] = ANIOS) -> Dict:
    ret = clasificar_retiradas(cargas, anios)
    out: Dict = {"filas_retiradas": int(len(ret)),
                 "por_clase": {c: int((ret["clase"] == c).sum()) for c in CLASES_P91},
                 "por_anio": {str(a): {c: int(((ret["periodo"] == a) & (ret["clase"] == c)).sum()) for c in CLASES_P91} for a in anios},
                 "por_familia": {}}
    for fam, g in ret.groupby("familia"):
        if len(g) >= N_MIN:
            out["por_familia"][fam] = {"n": int(len(g)), **{c: int((g["clase"] == c).sum()) for c in CLASES_P91}}
    # persons: the strongest class of the person-program-year (replacement > coexisting > other family > nothing)
    orden = {c: i for i, c in enumerate(CLASES_P91)}
    ret["_o"] = ret["clase"].map(orden)
    pers = ret.groupby(["persona_key", "cod_carrera", "periodo"], as_index=False).agg(_o=("_o", "min"), n_retiradas=("_o", "size"))
    pers["clase"] = pers["_o"].map({v: k for k, v in orden.items()})
    s = snap.loc[snap["continua"].notna()].copy()
    s["_t"] = s["periodo_corte"].str.slice(0, 4).astype(int)
    s = s.loc[s["_t"].isin(list(anios))]
    m = s.merge(pers.rename(columns={"cod_carrera": "cod_programa", "periodo": "_t"}), on=["persona_key", "cod_programa", "_t"], how="left")
    m["con_retirada"] = m["clase"].notna()
    m["no_continua"] = ~m["continua"].astype(bool)
    out["resultado_por_clase"] = []
    for k, gk in m.groupby("k"):
        fila: Dict = {"k": int(k), "sin_fila_retirada": {"n": int((~gk["con_retirada"]).sum()),
                                                         "tasa_no_continuidad": float(gk.loc[~gk["con_retirada"], "no_continua"].mean())}}
        for c in CLASES_P91:
            sub = gk.loc[gk["clase"] == c]
            fila[c] = {"n": int(len(sub)), "tasa_no_continuidad": float(sub["no_continua"].mean()) if len(sub) >= N_MIN else None}
        out["resultado_por_clase"].append(fila)
    adm = m.loc[(m["k"] == 1) & m["periodo_admision"].str.slice(4, 6).eq("10") & m["matriculado_2"].notna()].copy()
    adm["sale_en_el_anio"] = ~adm["matriculado_2"].astype(bool)
    salida: Dict = {}
    for nombre, g in (("sale_en_el_anio", adm.loc[adm["sale_en_el_anio"]]), ("se_queda", adm.loc[~adm["sale_en_el_anio"]])):
        tot = len(g)
        salida[nombre] = {"n": int(tot), "con_fila_retirada": int(g["con_retirada"].sum()),
                          "proporcion_con_fila_retirada": float(g["con_retirada"].mean()) if tot >= N_MIN else None,
                          **{c: int((g["clase"] == c).sum()) for c in CLASES_P91}}
    out["salida_en_el_anio"] = salida
    return out


# ---------------------------------------------------------------------------------------------------- loading and main
Q_SNAP = """
SELECT s.episodio_id, s.k, s.persona_key, s.cod_programa, s.periodo_corte, s.periodo_admision, s.cohorte_anio, s.continua,
       s.estado_muestra, s.split, m.matriculado AS matriculado_2
FROM neural_mart.snapshot_t1 s
LEFT JOIN neural_mart.snapshot_t1_semestre m ON m.episodio_id = s.episodio_id AND m.j = 2
WHERE s.estado_muestra = 'observada' AND s.continua IS NOT NULL AND s.k IN (1, 2) AND CAST(left(s.periodo_corte, 4) AS int) >= 2024
"""


def cargar(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT periodo, persona_key, cod_carrera, codigo, cobertura, first_ts, last_ts, n_loads, presente_ultima_carga, "
                    "sem1_primera, sem2_primera, sem1_ultima, sem2_ultima FROM neural_stg.banner_beneficios_cargas")
        cargas = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        cur.execute("SELECT timestamp_carga, periodo, filas FROM neural_stg.banner_beneficios_cargas_cal")
        calendario = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        cur.execute(Q_SNAP)
        snap = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    for col in ("first_ts", "last_ts", "n_loads"):
        cargas[col] = cargas[col].astype("int64")
    calendario["timestamp_carga"] = calendario["timestamp_carga"].astype("int64")
    snap["continua"] = snap["continua"].astype(bool)
    return cargas, calendario, snap


def calendario_de_cargas(calendario: pd.DataFrame) -> List[Dict]:
    """Calendar of the loads: date, rows and years covered by each load (aggregates of the Warehouse load log)."""
    g = calendario.groupby("timestamp_carga").agg(filas=("filas", "sum"), anios=("periodo", lambda s: f"{s.min()}-{s.max()}"),
                                                  n_anios=("periodo", "nunique")).reset_index().sort_values("timestamp_carga")
    return [{"fecha": str(RC.ts_a_fecha(int(r.timestamp_carga))), "filas": int(r.filas), "anios": r.anios, "n_anios": int(r.n_anios)}
            for r in g.itertuples()]


def construir(conn) -> Dict:
    cargas, calendario, snap = cargar(conn)
    cal = FC.calendario_por_anio(calendario)
    cal_carga = calendario_de_cargas(calendario)
    primera = {a: int(v[0]) for a, v in cal.items()}
    return {"calendario_cargas": {"n_cargas": len(cal_carga), "primera": cal_carga[0]["fecha"], "ultima": cal_carga[-1]["fecha"],
                                  "cargas": cal_carga},
            "primera_carga_por_anio": {str(a): str(RC.ts_a_fecha(ts)) for a, ts in sorted(primera.items())},
            "anios_con_historial": [a for a, ok in sorted(RC.anios_con_historial(primera).items()) if ok],
            "filas_por_corte": filas_por_corte(cargas, cal),
            "leakage": leakage(snap, cargas, cal),
            "p91": p91(cargas, snap)}


def main() -> int:
    from pipelines.common.db import dev_connection
    from models import seguimiento as S

    try:
        with dev_connection() as conn:
            res = construir(conn)
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / "diagnostico_beneficios_cargas_t1.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
        print("escrito artefactos/diagnostico_beneficios_cargas_t1.json")
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
