"""Leakage diagnostic of the student benefits for T1 (16-11-2026). AGGREGATES only; no person or amount is written.

Three questions, answered before any benefit variable is allowed into a model (``rules_beneficios`` records the outcome):

1. Is a benefit row (or a first / second semester amount) of the cut year more frequent among the people who continue than among
   those who do not? (``presencia_por_resultado``). A gap in the second-semester amount larger than the gap in the first-semester
   amount points at amounts that react to leaving.
2. Among the admission-year students who leave DURING that year (enrolled in the first semester, not in the second), are the rows
   deleted or zeroed? (``salida_en_el_anio``).
3. Does the load history of the Warehouse show rows added late in the year or second-semester amounts zeroed after it closes?
   (``historia_de_cargas``; the view only keeps the last load, ``banner_beneficios_full`` keeps all of them.)

``python -m evaluation.diagnostico_beneficios`` writes ``artefactos/diagnostico_beneficios_t1.json`` (gitignored); the
Warehouse part needs the ``WH_*`` variables (read only) and is skipped without them.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

N_MIN = 30

Q_DIAGNOSTICO = """
WITH b AS (
  SELECT persona_key, cod_carrera, periodo, count(*) AS n,
         bool_or(codigo LIKE 'GG_94%%' OR codigo LIKE 'GU_00%%') AS grat,
         bool_or(codigo IN ('C_1_AC', 'C_70_AC')) AS cred, sum(benef_sem1) AS s1, sum(benef_sem2) AS s2
  FROM neural_stg.banner_beneficios GROUP BY 1, 2, 3)
SELECT s.k, s.cohorte_anio, right(s.periodo_admision, 2) AS adm_suf, s.continua, s.estado_muestra, s.split,
       (b.persona_key IS NOT NULL)::int AS tiene_fila, COALESCE(b.grat, false)::int AS grat, COALESCE(b.cred, false)::int AS cred,
       (COALESCE(b.s1, 0) > 0)::int AS s1_pos, (COALESCE(b.s2, 0) > 0)::int AS s2_pos, sem2.matriculado AS matriculado_2
FROM neural_mart.snapshot_t1 s
LEFT JOIN b ON b.persona_key = s.persona_key AND b.cod_carrera = s.cod_programa
           AND b.periodo = CAST(left(s.periodo_corte, 4) AS int)
LEFT JOIN neural_mart.snapshot_t1_semestre sem2 ON sem2.episodio_id = s.episodio_id AND sem2.j = 2
WHERE CAST(left(s.periodo_corte, 4) AS int) >= 2017
"""


def _tasas(d: pd.DataFrame, columnas: Sequence[str]) -> Dict:
    return {"n": int(len(d)), **{c: float(d[c].mean()) for c in columnas}}


def presencia_por_resultado(df: pd.DataFrame, columnas: Sequence[str], n_min: int = N_MIN) -> List[Dict]:
    """Per k: rates of ``columnas`` among those who continue and those who do not, and the gap (continue - not)."""
    out = []
    for k, g in df.groupby("k"):
        fila: Dict = {"k": int(k)}
        for nombre, mask in (("continua", g["continua"].astype(bool)), ("no_continua", ~g["continua"].astype(bool))):
            sub = g.loc[mask]
            fila[nombre] = _tasas(sub, columnas) if len(sub) >= n_min else None
        fila["brecha"] = ({c: fila["continua"][c] - fila["no_continua"][c] for c in columnas}
                          if fila["continua"] and fila["no_continua"] else None)
        out.append(fila)
    return out


def salida_en_el_anio(df: pd.DataFrame, columnas: Sequence[str], n_min: int = N_MIN) -> Dict:
    """Admission-year students enrolled in the first semester: those who stay enrolled in the second against those who leave."""
    se_queda, sale = df.loc[df["matriculado_2"].astype(bool)], df.loc[~df["matriculado_2"].astype(bool)]
    r: Dict = {"se_queda": _tasas(se_queda, columnas) if len(se_queda) >= n_min else None,
               "sale": _tasas(sale, columnas) if len(sale) >= n_min else None}
    r["brecha"] = ({c: r["se_queda"][c] - r["sale"][c] for c in columnas} if r["se_queda"] and r["sale"] else None)
    return r


def historia_de_cargas(historia: Sequence[Tuple[str, int, int]], corte: str, cierre: str) -> Dict:
    """``historia``: (date of the load, rows of the year, rows of the year with second-semester amount > 0), in date order.

    ``filas_tardias_despues_del_corte``: share of the final rows that were not yet loaded at the last load on or before ``corte``
    (the end of the first semester). ``sem2_anulado_despues_del_cierre``: share of the second-semester amounts present at the last
    load on or before ``cierre`` (the end of the second semester) that are zero or missing in the final view.
    """
    h = sorted(historia)
    final_filas, final_sem2 = h[-1][1], h[-1][2]

    def ultimo(fecha: str):
        previos = [x for x in h if x[0] <= fecha]
        return previos[-1] if previos else None

    a, b = ultimo(corte), ultimo(cierre)
    return {"filas_final": int(final_filas), "sem2_final": int(final_sem2), "fecha_corte": a[0] if a else None,
            "filas_en_el_corte": a[1] if a else None,
            "filas_tardias_despues_del_corte": (1 - a[1] / final_filas) if a else None,
            "fecha_cierre": b[0] if b else None, "sem2_en_el_cierre": b[2] if b else None,
            "filas_en_el_cierre": b[1] if b else None,
            "filas_netas_despues_del_cierre": (1 - b[1] / final_filas) if b else None,
            "sem2_anulado_despues_del_cierre": (1 - final_sem2 / b[2]) if b and b[2] else None}


def _fecha(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")


def cargar_historia(wh_conn, anios: Sequence[int]) -> Dict[int, List[Tuple[str, int, int]]]:
    """Aggregated history of the loads of the Warehouse (``banner_beneficios_full``): rows per year and load."""
    out: Dict[int, List[Tuple[str, int, int]]] = {}
    with wh_conn.cursor() as cur:
        cur.execute("SELECT timestamp_carga, periodo, count(*), sum((benef_sem2 > 0)::int) FROM banner.banner_beneficios_full "
                    "WHERE periodo = ANY(%s) GROUP BY 1, 2 ORDER BY 2, 1", (list(anios),))
        rows = cur.fetchall()
    for ts, periodo, n, s2 in rows:
        out.setdefault(int(periodo), []).append((_fecha(int(ts)), int(n), int(s2 or 0)))
    # the same date can hold two loads: keep the one with the most rows of the day
    return {a: sorted({f: (f, n, s) for f, n, s in v}.values()) for a, v in out.items()}


Q_CAMBIOS = """
WITH a AS (SELECT rut, cod_carrera, codigo, cobertura FROM banner.banner_beneficios_full WHERE periodo = %(y)s AND timestamp_carga =
             (SELECT max(timestamp_carga) FROM banner.banner_beneficios_full
              WHERE to_char(to_timestamp(timestamp_carga / 1000) AT TIME ZONE 'UTC', 'YYYY-MM-DD') = %(fa)s)),
     b AS (SELECT rut, cod_carrera, codigo, cobertura FROM banner.banner_beneficios_full WHERE periodo = %(y)s AND timestamp_carga =
             (SELECT max(timestamp_carga) FROM banner.banner_beneficios_full
              WHERE to_char(to_timestamp(timestamp_carga / 1000) AT TIME ZONE 'UTC', 'YYYY-MM-DD') = %(fb)s))
SELECT (SELECT count(*) FROM a), (SELECT count(*) FROM b),
       (SELECT count(*) FROM (SELECT * FROM a EXCEPT SELECT * FROM b) x),
       (SELECT count(*) FROM (SELECT * FROM b EXCEPT SELECT * FROM a) y)
"""


def cambios_entre_cargas(wh_conn, anio: int, fecha_a: str, fecha_b: str) -> Dict:
    """Rows of the year present in the load of ``fecha_a`` and gone in ``fecha_b`` (``retiradas``), and the reverse
    (``agregadas``). Counts only: it answers whether rows are deleted retroactively."""
    with wh_conn.cursor() as cur:
        cur.execute(Q_CAMBIOS, {"y": anio, "fa": fecha_a, "fb": fecha_b})
        n_a, n_b, retiradas, agregadas = cur.fetchone()
    return {"fecha_a": fecha_a, "fecha_b": fecha_b, "filas_a": int(n_a), "filas_b": int(n_b),
            "retiradas": int(retiradas), "agregadas": int(agregadas)}


Q_RETIRADAS = Q_CAMBIOS.replace(
    """SELECT (SELECT count(*) FROM a), (SELECT count(*) FROM b),
       (SELECT count(*) FROM (SELECT * FROM a EXCEPT SELECT * FROM b) x),
       (SELECT count(*) FROM (SELECT * FROM b EXCEPT SELECT * FROM a) y)""",
    "SELECT DISTINCT rut, cod_carrera FROM (SELECT * FROM a EXCEPT SELECT * FROM b) x")


def retiradas_y_continuidad(wh_conn, conn, anio: int, fecha_a: str, fecha_b: str, secreto: str) -> Dict:
    """Do the rows removed after the first-semester cut belong to people who then do not continue?

    The persons with at least one removed row are pseudonymized in memory (never written) and looked up in the snapshot; only the
    counts and rates of the two groups come out."""
    from pipelines.common.pseudo import persona_key

    with wh_conn.cursor() as cur:
        cur.execute(Q_RETIRADAS, {"y": anio, "fa": fecha_a, "fb": fecha_b})
        pares = {(persona_key(str(r[0]), secreto), r[1]) for r in cur.fetchall()}
    with conn.cursor() as cur:
        cur.execute("SELECT persona_key, cod_programa, k, continua FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'observada' "
                    "AND continua IS NOT NULL AND CAST(left(periodo_corte, 4) AS int) = %s", (anio,))
        d = pd.DataFrame(cur.fetchall(), columns=["persona_key", "cod_programa", "k", "continua"])
    d["retirada"] = [(p, c) in pares for p, c in zip(d["persona_key"], d["cod_programa"])]
    out: Dict = {"anio": anio, "personas_programa_con_fila_retirada": len(pares)}
    for k, g in d.groupby("k"):
        con, sin = g.loc[g["retirada"]], g.loc[~g["retirada"]]
        out[f"k{int(k)}"] = {"con_fila_retirada": {"n": int(len(con)), "tasa_no_continuidad": float((~con["continua"].astype(bool)).mean())
                                                    if len(con) >= N_MIN else None},
                              "resto": {"n": int(len(sin)), "tasa_no_continuidad": float((~sin["continua"].astype(bool)).mean())}}
    return out


def construir(conn, wh_conn=None, anios_historia: Sequence[int] = (2024, 2025)) -> Dict:
    with conn.cursor() as cur:
        cur.execute(Q_DIAGNOSTICO)
        d = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    obs = d.loc[(d["estado_muestra"] == "observada") & d["continua"].notna()]
    columnas = ["tiene_fila", "grat", "cred", "s1_pos", "s2_pos"]
    res: Dict = {"columnas": columnas, "n_filas": int(len(obs))}
    res["presencia_por_resultado"] = presencia_por_resultado(obs, columnas)
    adm1 = d.loc[(d["k"] == 1) & (d["adm_suf"] == "10") & d["matriculado_2"].notna()]
    res["salida_en_el_anio"] = salida_en_el_anio(adm1, columnas)
    if wh_conn is not None:
        hist = cargar_historia(wh_conn, anios_historia)
        res["historia_cargas"] = {str(a): historia_de_cargas(h, f"{a}-07-31", f"{a}-11-30") for a, h in hist.items()}
        for a, r in res["historia_cargas"].items():
            ultima = max(x[0] for x in hist[int(a)])
            r["cambios_desde_el_corte"] = cambios_entre_cargas(wh_conn, int(a), r["fecha_corte"], ultima)
            r["cambios_desde_el_cierre"] = cambios_entre_cargas(wh_conn, int(a), r["fecha_cierre"], ultima)
            from pipelines.common.config import hmac_secret

            r["retiradas_y_continuidad"] = retiradas_y_continuidad(wh_conn, conn, int(a), r["fecha_corte"], ultima, hmac_secret())
    return res


def main() -> int:
    from pipelines.common.db import dev_connection, warehouse_connection
    from models import seguimiento as S

    try:
        with dev_connection() as conn:
            if all(os.environ.get(v) for v in ("WH_HOST", "WH_PORT", "WH_DB", "WH_USER", "WH_PASSWORD")):
                with warehouse_connection() as wh:
                    res = construir(conn, wh)
            else:
                res = construir(conn, None)
        S.ARTEFACTOS.mkdir(exist_ok=True)
        (S.ARTEFACTOS / "diagnostico_beneficios_t1.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
        print("escrito artefactos/diagnostico_beneficios_t1.json")
        return 0
    except Exception as exc:                      # no secrets in these messages
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
