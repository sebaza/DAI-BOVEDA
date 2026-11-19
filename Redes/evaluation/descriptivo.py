"""Aggregate description of the T1 snapshot for docs/08_benchmark_t1.md (counts only, no individual rows).

``python -m evaluation.descriptivo`` writes ``artefactos/descriptivo_t1.json`` (gitignored) from the dev DB.
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List

from models.seguimiento import ARTEFACTOS

CONSULTAS: Dict[str, str] = {
    "embudo": "SELECT clave, valor FROM neural_mart.snapshot_t1_resumen ORDER BY clave",
    "filas": """SELECT k, split, estado_muestra,
                       count(*) AS n,
                       count(*) FILTER (WHERE continua IS FALSE) AS no_continua,
                       count(*) FILTER (WHERE continua IS FALSE AND no_continua_tipo = 'salida') AS nc_salida,
                       count(*) FILTER (WHERE continua IS FALSE AND no_continua_tipo = 'interrupcion') AS nc_interrupcion,
                       count(*) FILTER (WHERE continua IS FALSE AND no_continua_tipo = 'ausencia') AS nc_ausencia,
                       count(*) FILTER (WHERE continua IS TRUE AND NOT continua_mismo_programa) AS continua_otro_programa,
                       count(*) FILTER (WHERE continua_mismo_programa IS FALSE) AS no_mismo_programa
                FROM neural_mart.snapshot_t1 GROUP BY k, split, estado_muestra ORDER BY k, split, estado_muestra""",
    "cohortes": """SELECT k, cohorte_anio, count(*) AS n, count(*) FILTER (WHERE continua IS FALSE) AS no_continua,
                          count(*) FILTER (WHERE continua IS FALSE AND no_continua_tipo = 'salida') AS nc_salida
                   FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'observada'
                   GROUP BY k, cohorte_anio ORDER BY k, cohorte_anio""",
    "codigos_salida": """WITH nc AS (
                           SELECT episodio_id, k, periodo_corte, periodo_horizonte FROM neural_mart.snapshot_t1
                           WHERE continua IS FALSE AND no_continua_tipo = 'salida'),
                         primera AS (
                           SELECT DISTINCT ON (nc.episodio_id, nc.k) nc.k, e.cod_estado
                           FROM nc JOIN neural_core.evento_estado e ON e.episodio_id = nc.episodio_id
                           JOIN neural_meta.dic_estado d ON d.cod_estado = e.cod_estado
                           WHERE d.clase_estado = 'salida' AND e.periodo > nc.periodo_corte
                             AND e.periodo <= nc.periodo_horizonte AND NOT e.es_correccion_sistema
                           ORDER BY nc.episodio_id, nc.k, e.orden_canonico)
                         SELECT p.k, p.cod_estado, d.nombre_estado, count(*) AS n
                         FROM primera p JOIN neural_meta.dic_estado d USING (cod_estado)
                         GROUP BY p.k, p.cod_estado, d.nombre_estado ORDER BY p.k, n DESC""",
    "cobertura_estados": """SELECT periodo,
                                   count(DISTINCT persona_key) FILTER (WHERE d.clase_estado IN ('matricula', 'reingreso', 'cambio_ciclo')) AS personas_matriculadas
                            FROM neural_core.evento_estado e JOIN neural_meta.dic_estado d USING (cod_estado)
                            WHERE NOT e.es_correccion_sistema AND e.periodo ~ '^[0-9]{4}(10|20)$'
                            GROUP BY periodo ORDER BY periodo""",
    "faltantes": """SELECT k, count(*) AS n, avg((NOT con_postulacion)::int) AS sin_postulacion,
                           avg((pct_ponderado IS NULL)::int) AS sin_ponderado, avg((pct_leng IS NULL)::int) AS sin_leng,
                           avg((pct_ranking IS NULL)::int) AS sin_ranking, avg((preferencia IS NULL)::int) AS sin_preferencia,
                           avg((tasa_aprobacion IS NULL)::int) AS sin_intentos
                    FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'observada' GROUP BY k ORDER BY k""",
    "vias": """SELECT k, via_clase, count(*) AS n, avg((continua IS FALSE)::int) AS tasa_no_continua
               FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'observada' AND split IN ('train', 'valid', 'test')
               GROUP BY k, via_clase ORDER BY k, via_clase""",
}


def main() -> int:
    try:
        from pipelines.common.db import dev_connection

        out: Dict[str, List] = {}
        with dev_connection() as conn, conn.cursor() as cur:
            for nombre, sql in CONSULTAS.items():
                cur.execute(sql)
                cols = [d.name for d in cur.description]
                out[nombre] = [dict(zip(cols, [float(v) if hasattr(v, "as_tuple") else v for v in row]))
                               for row in cur.fetchall()]
        ARTEFACTOS.mkdir(exist_ok=True)
        (ARTEFACTOS / "descriptivo_t1.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        print("escrito artefactos/descriptivo_t1.json")
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
