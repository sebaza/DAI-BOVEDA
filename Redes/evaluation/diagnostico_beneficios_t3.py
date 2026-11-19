"""Leakage diagnostic of the benefit variables for T3 (16-11-2026, decisions D100-D109; docs/10_benchmark_t3.md section 11).

``python -m evaluation.diagnostico_beneficios_t3`` reads the cuts of T3 (official ``k = 2, 4`` and late ``k = 8, 10``) with their
outcome and the benefit rows, and measures, for the CUT YEAR ``t`` and for the year before it, how the final-state table looks
by later outcome (egress / definitive exit / still enrolled-censored), separately for mid-year cuts (period ``AAAA10``) and
end-of-year cuts (``AAAA20``). If a flag of year ``t`` is a point-in-time fact, its prevalence by outcome has to look like the one
of year ``t - 1`` (same population, one year earlier); a gap that appears only in year ``t`` is information about the future.
It also measures whether the expiry and Capstone flags of year ``t`` are assigned early (first-semester amount > 0) or only in
the second semester (``benef_sem2`` is used HERE, for the diagnostic only: it is never a feature).

Writes AGGREGATES to ``artefactos/diagnostico_beneficios_t3.json`` (gitignored); groups with fewer than ``N_MIN`` cuts are dropped.
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from models import seguimiento as S
from pipelines.snapshots import rules_beneficios as RB
from pipelines.snapshots import rules_beneficios_t3 as RT

N_MIN = 30
CLASES = ("egreso_siguiente", "egreso_posterior", "salida", "censura")
INDICADORES = ("fila", "gratuidad", "expiro", "capstone")
Q_BEN = "SELECT periodo, persona_key, cod_carrera, codigo, benef_sem1, benef_sem2 FROM neural_stg.banner_beneficios"
Q_CORTES = ("SELECT episodio_id, k, persona_key, cod_programa, periodo_admision, tiempo, causa FROM neural_mart.{tabla} "
            "WHERE k = ANY(%s)")
Q_INGRESO = "SELECT episodio_id, cod_programa AS cod_programa_ingreso FROM neural_core.episodio_programa"


def clase_resultado(tiempo, causa, k) -> np.ndarray:
    """Outcome class after the cut: an egress in the very next semester, a later one, a definitive exit, or censoring."""
    u = np.asarray(tiempo) - np.asarray(k)
    causa = np.asarray(causa)
    return np.where(causa == 1, np.where(u <= 1, "egreso_siguiente", "egreso_posterior"),
                    np.where(causa == 2, "salida", "censura"))


def anual_diagnostico(ben: pd.DataFrame) -> pd.DataFrame:
    """One row per (person, program, year): presence, gratuity, expiry, Capstone, and whether the last two have a first-semester amount."""
    b = ben.copy()
    flags = {c: RB.clasificar(c) for c in b["codigo"].dropna().unique()}
    fam = b["codigo"].map(lambda c: flags.get(c, {}).get("familia"))
    exp = b["codigo"].map(lambda c: flags.get(c, {}).get("expiro", 0)).fillna(0).astype(int) > 0
    cap = b["codigo"].map(lambda c: bool(flags.get(c, {}).get("capstone", False)))
    s1, s2 = b["benef_sem1"].fillna(0) > 0, b["benef_sem2"].fillna(0) > 0
    d = pd.DataFrame({"persona_key": b["persona_key"], "cod_carrera": b["cod_carrera"], "periodo": b["periodo"].astype(int),
                      "fila": 1, "gratuidad": (fam == "gratuidad").astype(int), "expiro": exp.astype(int),
                      "capstone": cap.astype(int), "expiro_s1": (exp & s1).astype(int), "expiro_s2": (exp & s2).astype(int),
                      "capstone_s1": (cap & s1).astype(int), "capstone_s2": (cap & s2).astype(int)})
    return d.groupby(["persona_key", "cod_carrera", "periodo"], as_index=False).max()


def marcar(cortes: pd.DataFrame, anual: pd.DataFrame, columna_anio: str, sufijo: str) -> pd.DataFrame:
    """Flags of the year in ``columna_anio`` for each cut row (program in force at the cut or of admission), as ``<flag><sufijo>``."""
    c = cortes[["_row", "persona_key", "cod_programa", "cod_programa_ingreso", columna_anio]].rename(columns={columna_anio: "periodo"})
    pares = pd.concat([c[["_row", "persona_key", "cod_programa", "periodo"]].rename(columns={"cod_programa": "cod_carrera"}),
                       c[["_row", "persona_key", "cod_programa_ingreso", "periodo"]].rename(columns={"cod_programa_ingreso": "cod_carrera"})]
                      ).dropna(subset=["cod_carrera"]).drop_duplicates()
    m = pares.merge(anual, on=["persona_key", "cod_carrera", "periodo"], how="inner")
    cols = [x for x in anual.columns if x not in ("persona_key", "cod_carrera", "periodo")]
    g = m.groupby("_row")[cols].max()
    out = pd.DataFrame(index=cortes["_row"].to_numpy(), columns=cols, dtype="float64").fillna(0.0)
    out.loc[g.index, cols] = g[cols].to_numpy()
    return out.add_suffix(sufijo).reset_index(drop=True)


def tabla_prevalencias(d: pd.DataFrame, sufijo: str) -> Dict[str, Dict[str, float]]:
    """Per outcome class: n and the share with each indicator (columns ``<indicator><sufijo>``)."""
    out = {}
    for clase, x in d.groupby("clase"):
        if len(x) < N_MIN:
            continue
        r = {"n": int(len(x))}
        for ind in INDICADORES:
            r[ind] = float(x[f"{ind}{sufijo}"].mean())
        out[clase] = r
    return out


def adelanto_banderas(d: pd.DataFrame, sufijo: str) -> Dict[str, Dict[str, float]]:
    """Among the cuts with the expiry / Capstone flag, the share whose first-semester amount is positive (the flag applies from the start of the year)."""
    out = {}
    for flag in ("expiro", "capstone"):
        x = d.loc[d[f"{flag}{sufijo}"] > 0]
        if len(x) >= N_MIN:
            out[flag] = {"n": int(len(x)), "con_monto_sem1": float(x[f"{flag}_s1{sufijo}"].mean()),
                         "con_monto_sem2": float(x[f"{flag}_s2{sufijo}"].mean())}
    return out


def diagnosticar(cortes: pd.DataFrame, anual: pd.DataFrame) -> Dict:
    c = cortes.reset_index(drop=True).copy()
    c["_row"] = np.arange(len(c))
    c["periodo_corte"] = [RT.periodo_corte(p, int(k)) for p, k in zip(c["periodo_admision"], c["k"])]
    c["t"] = c["periodo_corte"].str.slice(0, 4).astype(int)
    c["tipo_corte"] = np.where(c["periodo_corte"].str.slice(4, 6) == "20", "fin_de_anio", "mitad_de_anio")
    c["clase"] = clase_resultado(c["tiempo"], c["causa"], c["k"])
    c["anio_adm"] = c["periodo_admision"].map(RT.anio_admision)
    anio_max = int(anual["periodo"].max())
    # comparable cuts: the year t and the year t - 1 are both inside the table and after the admission year
    ok = (c["t"] - 1 >= np.maximum(c["anio_adm"], RB.ANIO_MIN)) & (c["t"] <= anio_max)
    c = c.loc[ok].reset_index(drop=True)
    c["_row"] = np.arange(len(c))
    c["t_1"] = c["t"] - 1
    d = pd.concat([c, marcar(c, anual, "t", "_t"), marcar(c, anual, "t_1", "_t1")], axis=1)
    res: Dict = {"anio_beneficios_max": anio_max, "n_min": N_MIN, "por_corte": {}}
    for (k, tipo), x in d.groupby(["k", "tipo_corte"]):
        if len(x) < N_MIN:
            continue
        pt, p1 = tabla_prevalencias(x, "_t"), tabla_prevalencias(x, "_t1")
        brecha = {}
        for ind in INDICADORES:
            if "salida" in pt and "censura" in pt and "salida" in p1 and "censura" in p1:
                brecha[ind] = {"anio_t": pt["salida"][ind] - pt["censura"][ind], "anio_t_menos_1": p1["salida"][ind] - p1["censura"][ind]}
        res["por_corte"][f"k{k}_{tipo}"] = {"n": int(len(x)), "anio_t": pt, "anio_t_menos_1": p1, "brecha_salida_menos_censura": brecha,
                                           "bandera_con_monto_anio_t": adelanto_banderas(x, "_t")}
    return res


def distribucion_banderas(anual: pd.DataFrame, episodios: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Person-year rows with the expiry / Capstone flag by years since the admission year of the episode (same program)."""
    e = episodios.assign(anio_adm=episodios["periodo_admision"].map(RT.anio_admision))[["persona_key", "cod_programa", "anio_adm"]].drop_duplicates()
    m = anual.merge(e, left_on=["persona_key", "cod_carrera"], right_on=["persona_key", "cod_programa"])
    m["anios_desde_admision"] = (m["periodo"] - m["anio_adm"]).clip(lower=0, upper=9)
    out = {}
    for flag in ("expiro", "capstone"):
        g = m.loc[m[flag] > 0].groupby("anios_desde_admision").size()
        out[flag] = {str(int(k)): int(v) for k, v in g.items()}
    return out


def cargar(conn) -> Dict[str, pd.DataFrame]:
    def leer(sql, params=None):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])

    of = leer(Q_CORTES.format(tabla="snapshot_t3"), (list(RT.K_OFICIALES),))
    ext = leer(Q_CORTES.format(tabla="snapshot_t3_ext"), (list(RT.K_EXTENSION),))
    ingreso = leer(Q_INGRESO)
    cortes = pd.concat([of, ext], ignore_index=True).merge(ingreso, on="episodio_id", how="left")
    ben = leer(Q_BEN)
    for col in ("benef_sem1", "benef_sem2"):
        ben[col] = pd.to_numeric(ben[col]).astype("float64")
    episodios = leer("SELECT e.persona_key, e.cod_programa, e.periodo_admision FROM neural_core.episodio_programa e "
                     "JOIN neural_core.programa p ON p.cod_programa = e.cod_programa WHERE p.id_nivel::text = '1'")
    return {"cortes": cortes, "ben": ben, "episodios": episodios}


def main(argv: Optional[List[str]] = None) -> int:
    try:
        from pipelines.common.db import dev_connection

        with dev_connection() as conn:
            datos = cargar(conn)
        anual = anual_diagnostico(datos["ben"])
        res = diagnosticar(datos["cortes"], anual)
        res["banderas_por_anios_desde_admision"] = distribucion_banderas(anual, datos["episodios"])
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / "diagnostico_beneficios_t3.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
        print("escrito artefactos/diagnostico_beneficios_t3.json")
        for corte, v in res["por_corte"].items():
            print(corte, v["n"])
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
