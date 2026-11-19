"""SQL of the ``neural_mart`` tables (one INSERT ... SELECT per table, built in dependency order).

Placeholders ``{core}``, ``{mart}``, ``{meta}`` are schema names (validated against the migration guard list);
values travel as bound parameters: ``latest`` (latest regular period in the
data, text) and ``latest_ord`` (its semester ordinal). Definitions mirror ``rules.py``.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from ..snapshots import rules_t3 as R3
from ..snapshots.rules import ADMISIONES_EXCLUIDAS
from . import rules_traslados as RT

ENROLLED = "('matricula', 'reingreso', 'cambio_ciclo')"


def ord_sem(col: str) -> str:
    """Semester ordinal of any period (``rules.base_ordinal``)."""
    return f"(substr({col}, 1, 4)::int * 2 + (substr({col}, 5, 2) >= '20')::int)"


def is_regular(col: str) -> str:
    return f"substr({col}, 5, 2) IN ('10', '20')"


def periodo_de_fecha(col: str) -> str:
    """Academic period of a date (``rules.periodo_de_fecha``)."""
    return (
        f"(CASE WHEN {col} IS NULL THEN NULL "
        f"WHEN extract(month FROM {col}) <= 2 THEN (extract(year FROM {col})::int - 1)::text || '20' "
        f"WHEN extract(month FROM {col}) <= 7 THEN extract(year FROM {col})::int::text || '10' "
        f"ELSE extract(year FROM {col})::int::text || '20' END)"
    )


MART_TABLES: Tuple[str, ...] = (
    "indicador_periodo", "ficha_episodio", "avance_malla", "cohorte_semestre", "programa_semestre",
    "cohorte_resultado", "postulante_contexto", "programa_traslados", "programa_traslados_nota",
)

INDICADOR_PERIODO = f"""
INSERT INTO {{mart}}.indicador_periodo (
    episodio_id, periodo, persona_key, cod_programa, semestre_k, periodo_regular,
    intentos_evaluados, aprobados_evaluados, reprobados, convalidaciones, creditos_aprobados_curriculares,
    promedio_periodo, n_notas_promedio, creditos_acumulados, promedio_acumulado, n_notas_acumulado,
    ramos_aprobados_acumulados, intentos_evaluados_acumulados, aprobados_evaluados_acumulados)
WITH per AS (
    SELECT episodio_id, periodo FROM {{core}}.evento_estado
    WHERE episodio_id IS NOT NULL AND NOT es_correccion_sistema
    UNION
    SELECT episodio_id, periodo FROM {{core}}.intento_asignatura WHERE episodio_id IS NOT NULL
), att AS (
    SELECT episodio_id, periodo,
           count(*) FILTER (WHERE es_intento_evaluado) AS ie,
           count(*) FILTER (WHERE es_intento_evaluado AND aprobado_curricular) AS ae,
           count(*) FILTER (WHERE es_intento_evaluado AND NOT aprobado_curricular) AS re,
           count(*) FILTER (WHERE resultado_tipo = 'convalidacion') AS cv,
           sum(nota_numerica) FILTER (WHERE es_intento_evaluado AND nota_numerica IS NOT NULL
                                      AND NOT nota_es_heredada) AS sn,
           count(*) FILTER (WHERE es_intento_evaluado AND nota_numerica IS NOT NULL
                            AND NOT nota_es_heredada) AS nn
    FROM {{core}}.intento_asignatura WHERE episodio_id IS NOT NULL GROUP BY episodio_id, periodo
), first_ap AS (
    SELECT episodio_id, periodo, count(*) AS ramos, sum(cred) AS cred
    FROM (SELECT episodio_id, periodo, coalesce(creditos, creditos_reconocidos, 0) AS cred,
                 row_number() OVER (PARTITION BY episodio_id, codigo_asignatura
                                    ORDER BY periodo, intento_id) AS rn
          FROM {{core}}.intento_asignatura
          WHERE episodio_id IS NOT NULL AND aprobado_curricular) t
    WHERE rn = 1 GROUP BY episodio_id, periodo
), j AS (
    SELECT per.episodio_id, per.periodo, e.persona_key, e.cod_programa,
           CASE WHEN {is_regular('per.periodo')}
                 AND {ord_sem('per.periodo')} - {ord_sem('e.periodo_admision')} + 1 >= 1
                THEN {ord_sem('per.periodo')} - {ord_sem('e.periodo_admision')} + 1 END AS semestre_k,
           {is_regular('per.periodo')} AS regular,
           coalesce(att.ie, 0) AS ie, coalesce(att.ae, 0) AS ae, coalesce(att.re, 0) AS re,
           coalesce(att.cv, 0) AS cv, att.sn, coalesce(att.nn, 0) AS nn,
           coalesce(first_ap.ramos, 0) AS ramos, coalesce(first_ap.cred, 0) AS cred
    FROM per
    JOIN {{core}}.episodio_programa e ON e.episodio_id = per.episodio_id
    LEFT JOIN att ON att.episodio_id = per.episodio_id AND att.periodo = per.periodo
    LEFT JOIN first_ap ON first_ap.episodio_id = per.episodio_id AND first_ap.periodo = per.periodo
), w AS (
    SELECT j.*,
           sum(cred) OVER win AS cred_ac, sum(ramos) OVER win AS ramos_ac,
           sum(coalesce(sn, 0)) OVER win AS sn_ac, sum(nn) OVER win AS nn_ac,
           sum(ie) OVER win AS ie_ac, sum(ae) OVER win AS ae_ac
    FROM j
    WINDOW win AS (PARTITION BY episodio_id ORDER BY periodo
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT episodio_id, periodo, persona_key, cod_programa, semestre_k, regular,
       ie, ae, re, cv, cred,
       CASE WHEN nn > 0 THEN round(sn / nn, 3) END, nn,
       cred_ac, CASE WHEN nn_ac > 0 THEN round(sn_ac / nn_ac, 3) END, nn_ac::int,
       ramos_ac::int, ie_ac::int, ae_ac::int
FROM w
"""

FICHA_EPISODIO = f"""
INSERT INTO {{mart}}.ficha_episodio (
    episodio_id, persona_key, cod_programa, nombre_programa, cod_admision, admision, periodo_admision,
    primer_periodo, ultimo_periodo, semestres_regulares_cursados, ultimo_cod_estado, ultimo_estado_clase,
    titulado, egresado, periodo_titulacion, creditos_acumulados, promedio_acumulado, n_notas_acumulado,
    tasa_aprobacion_intento, intentos_evaluados, aprobados_evaluados, retencion_1er_anio)
WITH st AS (
    SELECT s.episodio_id, s.periodo, s.orden_canonico, s.cod_estado, coalesce(d.clase_estado, 'otro') AS clase
    FROM {{core}}.evento_estado s
    LEFT JOIN {{meta}}.dic_estado d ON d.cod_estado = s.cod_estado
    WHERE s.episodio_id IS NOT NULL AND NOT s.es_correccion_sistema
), ult AS (
    SELECT DISTINCT ON (episodio_id) episodio_id, cod_estado, clase
    FROM st ORDER BY episodio_id, orden_canonico DESC
), fl AS (
    SELECT st.episodio_id,
           count(DISTINCT st.periodo) FILTER (WHERE {is_regular('st.periodo')} AND st.clase IN {ENROLLED}) AS sem,
           bool_or(st.cod_estado = 'U') AS u,
           bool_or(st.cod_estado IN ('G', 'Z')) AS eg,
           min(st.periodo) FILTER (WHERE st.cod_estado = 'U') AS per_u,
           bool_or({is_regular('st.periodo')} AND st.clase IN {ENROLLED}
                   AND {ord_sem('st.periodo')} = {ord_sem('e.periodo_admision')} + 2) AS act3
    FROM st JOIN {{core}}.episodio_programa e ON e.episodio_id = st.episodio_id
    GROUP BY st.episodio_id
), tit AS (
    SELECT episodio_id, min({periodo_de_fecha('fecha_titulacion')}) AS per_f
    FROM {{core}}.titulacion WHERE episodio_id IS NOT NULL GROUP BY episodio_id
), tit_any AS (
    SELECT DISTINCT episodio_id FROM {{core}}.titulacion WHERE episodio_id IS NOT NULL
), last_ind AS (
    SELECT DISTINCT ON (episodio_id) episodio_id, creditos_acumulados, promedio_acumulado, n_notas_acumulado
    FROM {{mart}}.indicador_periodo ORDER BY episodio_id, periodo DESC
), tot AS (
    SELECT episodio_id, sum(intentos_evaluados)::int AS ie, sum(aprobados_evaluados)::int AS ae
    FROM {{mart}}.indicador_periodo GROUP BY episodio_id
)
SELECT e.episodio_id, e.persona_key, e.cod_programa, p.nombre_programa, e.cod_admision, a.admision,
       e.periodo_admision, e.primer_periodo, e.ultimo_periodo,
       coalesce(fl.sem, 0)::int, ult.cod_estado, ult.clase,
       (coalesce(fl.u, false) OR ta.episodio_id IS NOT NULL),
       coalesce(fl.eg, false),
       coalesce(fl.per_u, tit.per_f),
       coalesce(li.creditos_acumulados, 0), li.promedio_acumulado, coalesce(li.n_notas_acumulado, 0),
       CASE WHEN coalesce(tot.ie, 0) > 0 THEN round(tot.ae::numeric / tot.ie, 4) END,
       coalesce(tot.ie, 0), coalesce(tot.ae, 0),
       CASE WHEN e.periodo_admision IS NOT NULL
                 AND {ord_sem('e.periodo_admision')} + 2 < %(latest_ord)s::int
            THEN (coalesce(fl.act3, false) OR coalesce(fl.u, false) OR ta.episodio_id IS NOT NULL
                  OR coalesce(fl.eg, false)) END
FROM {{core}}.episodio_programa e
LEFT JOIN {{core}}.programa p ON p.cod_programa = e.cod_programa
LEFT JOIN {{meta}}.dic_tipo_admision a ON a.cod_admision = e.cod_admision
LEFT JOIN ult ON ult.episodio_id = e.episodio_id
LEFT JOIN fl ON fl.episodio_id = e.episodio_id
LEFT JOIN tit ON tit.episodio_id = e.episodio_id
LEFT JOIN tit_any ta ON ta.episodio_id = e.episodio_id
LEFT JOIN last_ind li ON li.episodio_id = e.episodio_id
LEFT JOIN tot ON tot.episodio_id = e.episodio_id
"""

# Sparse: only courses with an attempt or in progress. `no_cursada` rows (12.7M for the whole malla) are
# derived by the API from asignatura_malla instead of being stored.
AVANCE_MALLA = """
INSERT INTO {mart}.avance_malla (
    episodio_id, codigo_asignatura, cod_programa, catalogo, semestre, creditos, nombre_asignatura,
    es_hito, tipo_hito, estado_ramo, n_intentos_evaluados, mejor_nota, ultimo_periodo)
WITH ep AS (
    SELECT episodio_id, persona_key, cod_programa, primer_periodo, ultimo_periodo,
           coalesce(catalogo_final, catalogo_inicial) AS catalogo
    FROM {core}.episodio_programa
), agg AS (
    SELECT episodio_id, codigo_asignatura,
           count(*) FILTER (WHERE es_intento_evaluado) AS n_eval,
           bool_or(aprobado_curricular AND resultado_tipo = 'evaluado') AS ap_eval,
           bool_or(aprobado_curricular AND resultado_tipo = 'convalidacion') AS ap_conv,
           max(nota_numerica) FILTER (WHERE es_intento_evaluado) AS mejor,
           max(periodo) AS ultimo
    FROM {core}.intento_asignatura WHERE episodio_id IS NOT NULL GROUP BY episodio_id, codigo_asignatura
), curso AS (
    SELECT DISTINCT ep.episodio_id, q.materia_curso_catalogo AS codigo_asignatura
    FROM {core}.inscripcion_asignatura i
    JOIN {core}.inscripcion_equivalencia q ON q.inscripcion_id = i.inscripcion_id
    JOIN ep ON ep.persona_key = i.persona_key AND i.periodo BETWEEN ep.primer_periodo AND ep.ultimo_periodo
    WHERE i.en_curso AND i.periodo = (SELECT max(periodo) FROM {core}.inscripcion_asignatura)
), cand AS (
    SELECT episodio_id, codigo_asignatura FROM agg
    UNION
    SELECT episodio_id, codigo_asignatura FROM curso
), j AS (
    SELECT ep.episodio_id, m.codigo_asignatura, ep.cod_programa, ep.catalogo, m.semestre, m.creditos,
           m.nombre_asignatura, (h.tipo_hito IS NOT NULL) AS es_hito, h.tipo_hito,
           CASE WHEN coalesce(agg.ap_eval, false) THEN 'aprobada'
                WHEN coalesce(agg.ap_conv, false) THEN 'convalidada'
                WHEN curso.episodio_id IS NOT NULL THEN 'en_curso'
                WHEN coalesce(agg.n_eval, 0) > 0 THEN 'reprobada_pendiente'
                ELSE 'no_cursada' END AS estado,
           coalesce(agg.n_eval, 0) AS n_eval, agg.mejor, agg.ultimo
    FROM cand
    JOIN ep ON ep.episodio_id = cand.episodio_id
    JOIN {core}.asignatura_malla m ON m.cod_programa = ep.cod_programa AND m.catalogo = ep.catalogo
                                  AND m.codigo_asignatura = cand.codigo_asignatura
    LEFT JOIN {core}.hito_formativo h ON h.cod_programa = m.cod_programa AND h.catalogo = m.catalogo
                                      AND h.codigo_asignatura = m.codigo_asignatura
    LEFT JOIN agg ON agg.episodio_id = cand.episodio_id AND agg.codigo_asignatura = cand.codigo_asignatura
    LEFT JOIN curso ON curso.episodio_id = cand.episodio_id AND curso.codigo_asignatura = cand.codigo_asignatura
)
SELECT episodio_id, codigo_asignatura, cod_programa, catalogo, semestre, creditos, nombre_asignatura, es_hito,
       tipo_hito, estado, n_eval, mejor, ultimo
FROM j WHERE estado <> 'no_cursada'
"""

# Active = an enrolled-class state in the semester; period strictly before the latest (still running) one.
_ACTIVOS = f"""
act AS (
    SELECT DISTINCT f.cod_programa, f.periodo_admision AS cohorte, i.semestre_k, i.episodio_id,
           i.creditos_acumulados, i.promedio_acumulado, i.n_notas_acumulado
    FROM {{core}}.evento_estado s
    JOIN {{meta}}.dic_estado d ON d.cod_estado = s.cod_estado AND d.clase_estado IN {ENROLLED}
    JOIN {{mart}}.indicador_periodo i ON i.episodio_id = s.episodio_id AND i.periodo = s.periodo
                                     AND i.semestre_k IS NOT NULL
    JOIN {{mart}}.ficha_episodio f ON f.episodio_id = s.episodio_id
    WHERE s.episodio_id IS NOT NULL AND NOT s.es_correccion_sistema AND s.periodo < %(latest)s::text
)"""

_STATS = """
count(*)::int AS n_activos,
count(*) FILTER (WHERE n_notas_acumulado > 0)::int AS n_prom,
percentile_cont(0.25) WITHIN GROUP (ORDER BY creditos_acumulados) AS c25,
percentile_cont(0.50) WITHIN GROUP (ORDER BY creditos_acumulados) AS c50,
percentile_cont(0.75) WITHIN GROUP (ORDER BY creditos_acumulados) AS c75,
percentile_cont(0.25) WITHIN GROUP (ORDER BY promedio_acumulado) FILTER (WHERE n_notas_acumulado > 0) AS p25,
percentile_cont(0.50) WITHIN GROUP (ORDER BY promedio_acumulado) FILTER (WHERE n_notas_acumulado > 0) AS p50,
percentile_cont(0.75) WITHIN GROUP (ORDER BY promedio_acumulado) FILTER (WHERE n_notas_acumulado > 0) AS p75
"""

COHORTE_SEMESTRE = (
    """
INSERT INTO {mart}.cohorte_semestre (
    cod_programa, cohorte, semestre_k, n_episodios, n_activos, n_promedio,
    creditos_p25, creditos_p50, creditos_p75, promedio_p25, promedio_p50, promedio_p75)
WITH coh AS (
    SELECT cod_programa, periodo_admision AS cohorte, count(*)::int AS n
    FROM {core}.episodio_programa WHERE periodo_admision IS NOT NULL GROUP BY cod_programa, periodo_admision
), """
    + _ACTIVOS
    + """, s AS (
    SELECT cod_programa, cohorte, semestre_k, """
    + _STATS
    + """
    FROM act GROUP BY cod_programa, cohorte, semestre_k
)
SELECT s.cod_programa, s.cohorte, s.semestre_k, coh.n, s.n_activos, s.n_prom,
       round(c25::numeric, 3), round(c50::numeric, 3), round(c75::numeric, 3), round(p25::numeric, 3), round(p50::numeric, 3), round(p75::numeric, 3)
FROM s JOIN coh ON coh.cod_programa = s.cod_programa AND coh.cohorte = s.cohorte
"""
)

PROGRAMA_SEMESTRE = (
    """
INSERT INTO {mart}.programa_semestre (
    cod_programa, semestre_k, n_episodios, n_activos, n_promedio,
    creditos_p25, creditos_p50, creditos_p75, promedio_p25, promedio_p50, promedio_p75)
WITH coh AS (
    SELECT cod_programa, """
    + ord_sem("periodo_admision")
    + """ AS base, count(*)::int AS n
    FROM {core}.episodio_programa WHERE periodo_admision IS NOT NULL GROUP BY cod_programa, periodo_admision
), cohk AS (
    SELECT coh.cod_programa, k.k AS semestre_k, sum(coh.n)::int AS n
    FROM coh CROSS JOIN generate_series(1, 60) AS k(k)
    WHERE coh.base + k.k - 1 < %(latest_ord)s::int
    GROUP BY coh.cod_programa, k.k
), """
    + _ACTIVOS
    + """, s AS (
    SELECT cod_programa, semestre_k, """
    + _STATS
    + """
    FROM act GROUP BY cod_programa, semestre_k
)
SELECT s.cod_programa, s.semestre_k, cohk.n, s.n_activos, s.n_prom,
       round(c25::numeric, 3), round(c50::numeric, 3), round(c75::numeric, 3), round(p25::numeric, 3), round(p50::numeric, 3), round(p75::numeric, 3)
FROM s JOIN cohk ON cohk.cod_programa = s.cod_programa AND cohk.semestre_k = s.semestre_k
"""
)

COHORTE_RESULTADO = f"""
INSERT INTO {{mart}}.cohorte_resultado (
    cod_programa, cohorte, n_ingreso, duracion, duracion_anios,
    censurado_d, censurado_d1, censurado_d2, titulados_d, titulados_d1, titulados_d2,
    censurado_retencion, n_retencion_obs, n_retenidos)
WITH e AS (
    SELECT f.cod_programa, f.periodo_admision AS cohorte, {ord_sem('f.periodo_admision')} AS base,
           {ord_sem('f.periodo_titulacion')} AS pt, f.retencion_1er_anio AS ret, pc.duracion
    FROM {{mart}}.ficha_episodio f
    JOIN {{core}}.episodio_programa ep ON ep.episodio_id = f.episodio_id
    LEFT JOIN {{core}}.programa_catalogo pc ON pc.cod_programa = ep.cod_programa AND pc.catalogo = ep.catalogo_inicial
    WHERE f.periodo_admision IS NOT NULL
), pm AS (
    SELECT cod_programa, max(duracion) AS dmax FROM {{core}}.programa_catalogo GROUP BY cod_programa
), c AS (
    SELECT e.cod_programa, e.cohorte, min(e.base) AS base, count(*)::int AS n,
           coalesce(mode() WITHIN GROUP (ORDER BY e.duracion), pm.dmax) AS dur
    FROM e LEFT JOIN pm ON pm.cod_programa = e.cod_programa
    GROUP BY e.cod_programa, e.cohorte, pm.dmax
), c2 AS (
    SELECT c.*, CASE WHEN dur > 0 THEN ceil(dur / 2.0)::int END AS da FROM c
), r AS (
    SELECT c2.cod_programa, c2.cohorte, c2.base, c2.n, c2.dur, c2.da,
           count(*) FILTER (WHERE e.pt <= c2.base + 2 * c2.da - 1) AS t0,
           count(*) FILTER (WHERE e.pt <= c2.base + 2 * (c2.da + 1) - 1) AS t1,
           count(*) FILTER (WHERE e.pt <= c2.base + 2 * (c2.da + 2) - 1) AS t2,
           count(*) FILTER (WHERE e.ret IS NOT NULL) AS ro,
           count(*) FILTER (WHERE e.ret) AS rr
    FROM c2 JOIN e ON e.cod_programa = c2.cod_programa AND e.cohorte = c2.cohorte
    GROUP BY c2.cod_programa, c2.cohorte, c2.base, c2.n, c2.dur, c2.da
)
SELECT cod_programa, cohorte, n, dur, da,
       (da IS NULL OR base + 2 * da - 1 >= %(latest_ord)s::int),
       (da IS NULL OR base + 2 * (da + 1) - 1 >= %(latest_ord)s::int),
       (da IS NULL OR base + 2 * (da + 2) - 1 >= %(latest_ord)s::int),
       CASE WHEN da IS NOT NULL AND base + 2 * da - 1 < %(latest_ord)s::int THEN t0::int END,
       CASE WHEN da IS NOT NULL AND base + 2 * (da + 1) - 1 < %(latest_ord)s::int THEN t1::int END,
       CASE WHEN da IS NOT NULL AND base + 2 * (da + 2) - 1 < %(latest_ord)s::int THEN t2::int END,
       NOT (base + 2 < %(latest_ord)s::int),
       CASE WHEN base + 2 < %(latest_ord)s::int THEN ro::int END,
       CASE WHEN base + 2 < %(latest_ord)s::int THEN rr::int END
FROM r
"""

POSTULANTE_CONTEXTO = f"""
INSERT INTO {{mart}}.postulante_contexto (
    cod_carrera, year_admision, banda_ponderado, n_postulantes, n_matriculados, n_vinculados,
    n_retencion_obs, n_retenidos, censurado_titulacion, duracion_anios, n_titulacion_obs, n_titulados)
WITH app AS (
    SELECT year_admision, cod_carrera, persona_key, max(ponderado) AS ponderado, bool_or(matricula = 'Y') AS mat
    FROM {{core}}.postulacion_via WHERE ponderado IS NOT NULL
    GROUP BY year_admision, cod_carrera, persona_key
), banded AS (
    SELECT app.*, least(5, floor(percent_rank() OVER (PARTITION BY year_admision, cod_carrera
                                                       ORDER BY ponderado) * 5)::int + 1) AS banda
    FROM app
), lk AS (
    SELECT persona_key, cod_programa, periodo_admision,
           bool_or(retencion_1er_anio) AS ret, min({ord_sem('periodo_titulacion')}) AS pt, count(*) AS n
    FROM {{mart}}.ficha_episodio WHERE periodo_admision IS NOT NULL
    GROUP BY persona_key, cod_programa, periodo_admision
), j AS (
    SELECT b.cod_carrera, b.year_admision, b.banda, b.mat, lk.n IS NOT NULL AS vinc, lk.ret, lk.pt,
           cr.duracion_anios AS da, cr.censurado_d1 AS cens, {ord_sem('b.year_admision')} AS base
    FROM banded b
    LEFT JOIN lk ON lk.persona_key = b.persona_key AND lk.cod_programa = b.cod_carrera
                AND lk.periodo_admision = b.year_admision
    LEFT JOIN {{mart}}.cohorte_resultado cr ON cr.cod_programa = b.cod_carrera AND cr.cohorte = b.year_admision
), g AS (
    SELECT cod_carrera, year_admision, banda,
           count(*)::int AS n_post, count(*) FILTER (WHERE mat)::int AS n_mat,
           count(*) FILTER (WHERE mat AND vinc)::int AS n_vinc,
           count(*) FILTER (WHERE mat AND vinc AND ret IS NOT NULL)::int AS n_ro,
           count(*) FILTER (WHERE mat AND vinc AND ret)::int AS n_rr,
           max(da) AS da, bool_and(coalesce(cens, true)) AS cens,
           count(*) FILTER (WHERE mat AND vinc AND da IS NOT NULL)::int AS n_to,
           count(*) FILTER (WHERE mat AND vinc AND da IS NOT NULL
                            AND pt <= base + 2 * (da + 1) - 1)::int AS n_tt
    FROM j GROUP BY cod_carrera, year_admision, banda
)
SELECT cod_carrera, year_admision, banda, n_post, n_mat, n_vinc, n_ro, n_rr, cens, da,
       CASE WHEN NOT cens THEN n_to END, CASE WHEN NOT cens THEN n_tt END
FROM g
"""

def _lista(valores: Iterable[str]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in sorted(valores)) + ")"


def slot(col: str) -> str:
    """Regular slot of any period (``rules_t3.ordinal_periodo``: 15 and 20 -> odd, 25 -> next 10)."""
    return (f"(CASE WHEN substr({col}, 5, 2) <= '10' THEN substr({col}, 1, 4)::int * 2 "
            f"WHEN substr({col}, 5, 2) <= '20' THEN substr({col}, 1, 4)::int * 2 + 1 "
            f"ELSE (substr({col}, 1, 4)::int + 1) * 2 END)")


# Transfers between programs (rules_traslados.py). The D47 link picks, for an Ingenieria Civil Plan Comun origin, the
# first later specialty; any other origin goes to the NEXT undergraduate episode of the person.
# Transfers between programs (rules_traslados.py). The D47 link picks, for an Ingenieria Civil Plan Comun origin, the
# first later specialty; any other origin goes to the NEXT undergraduate episode of the person. ``t0`` also labels the
# pairs that are NOT a transfer (``rel``: P64 double program / baja in an overlap, P69 continuation after graduating).
_TRASLADOS_CTE = f"""
WITH ep AS (
    SELECT e.episodio_id, e.persona_key, e.cod_programa, e.cod_admision, e.periodo_admision, e.primer_periodo,
           e.ultimo_periodo, e.ultimo_estado_clase, {slot('e.primer_periodo')} AS s_primer,
           {slot('e.ultimo_periodo')} AS s_ultimo
    FROM {{core}}.episodio_programa e JOIN {{core}}.programa p ON p.cod_programa = e.cod_programa
    WHERE p.id_nivel = 1 AND e.cod_programa NOT IN {_lista(RT.PROGRAMAS_EXCLUIDOS)}
      AND e.cod_admision NOT IN {_lista(ADMISIONES_EXCLUIDAS)}
), seq AS (
    SELECT ep.*, row_number() OVER (PARTITION BY persona_key ORDER BY s_primer, episodio_id) AS rn FROM ep
), pc AS (
    SELECT DISTINCT ON (a.episodio_id) a.episodio_id AS a_id, b.episodio_id AS b_id, a.s_primer AS a_primer
    FROM seq a JOIN seq b ON b.persona_key = a.persona_key AND b.episodio_id <> a.episodio_id AND b.s_primer > a.s_primer
    WHERE a.cod_programa IN {_lista(R3.PLAN_COMUN_ING_CIVIL)} AND b.cod_programa IN {_lista(R3.ESPECIALIDADES_ING_CIVIL)}
      AND b.s_primer - a.s_ultimo <= {R3.VENTANA_VINCULO_PERIODOS}
    ORDER BY a.episodio_id, b.s_primer, b.episodio_id
), pc1 AS (
    SELECT DISTINCT ON (b_id) a_id, b_id FROM pc ORDER BY b_id, a_primer DESC, a_id DESC
), nxt AS (
    SELECT a.episodio_id AS a_id, b.episodio_id AS b_id
    FROM seq a JOIN seq b ON b.persona_key = a.persona_key AND b.rn = a.rn + 1 AND b.cod_programa <> a.cod_programa
), par AS (
    SELECT coalesce(pc1.a_id, nxt.a_id) AS a_id, coalesce(pc1.b_id, nxt.b_id) AS b_id
    FROM nxt FULL JOIN pc1 ON pc1.a_id = nxt.a_id
), j AS (
    SELECT o.*, d.episodio_id AS d_id, d.cod_programa AS d_prog, d.cod_admision AS d_adm, d.primer_periodo AS d_primer,
           d.s_primer AS d_s, d.s_primer - o.s_ultimo AS brecha,
           (o.cod_programa IN {_lista(R3.PLAN_COMUN_ING_CIVIL)} AND d.cod_programa IN {_lista(R3.ESPECIALIDADES_ING_CIVIL)}
            AND d.s_primer > o.s_primer AND d.s_primer - o.s_ultimo <= {R3.VENTANA_VINCULO_PERIODOS}) AS d47
    FROM par JOIN seq o ON o.episodio_id = par.a_id JOIN seq d ON d.episodio_id = par.b_id
), t0 AS (
    SELECT j.*, CASE
        WHEN d47 THEN 'eleccion_especialidad'
        WHEN brecha NOT BETWEEN {RT.VENTANA_MIN} AND {RT.VENTANA_MAX} THEN NULL
        WHEN d_adm = '{RT.ADMISION_ELECCION}' THEN 'eleccion_especialidad'
        WHEN ultimo_estado_clase = '{RT.CLASE_EGRESO}' THEN NULL            -- P69: not a transfer (noted in rel)
        WHEN ultimo_estado_clase = '{RT.CLASE_CICLO}' THEN 'cambio_ciclo'
        WHEN d_adm = '{RT.ADMISION_CAMBIO_CARRERA}' THEN 'cambio_carrera'
        WHEN d_adm = '{RT.ADMISION_CAMBIO_SEDE}' THEN 'traslado_sede'
        ELSE 'traslado_otro' END AS tipo,
        CASE WHEN d47 THEN NULL
        WHEN brecha < {RT.VENTANA_MIN} THEN CASE WHEN ultimo_estado_clase = '{RT.CLASE_BAJA}'
            THEN 'superposicion_con_baja' ELSE 'doble_programa' END     -- P64: overlap, never a transfer
        WHEN brecha <= {RT.VENTANA_MAX} AND d_adm <> '{RT.ADMISION_ELECCION}' AND ultimo_estado_clase = '{RT.CLASE_EGRESO}'
            THEN 'continuacion_estudios' END AS rel
    FROM j

"""

PROGRAMA_TRASLADOS = f"""
INSERT INTO {{mart}}.programa_traslados (
    origen_episodio_id, destino_episodio_id, persona_key, cod_programa_origen, cod_programa_destino,
    periodo_admision_origen, anio_cohorte_origen, ultimo_periodo_origen, primer_periodo_destino, anio_traslado,
    cod_admision_destino, ultimo_estado_clase_origen, brecha_periodos, tipo, regla, cuenta_abandono, ambiguo)
{_TRASLADOS_CTE}
), t AS (
    SELECT * FROM t0 WHERE tipo IS NOT NULL
), amb AS (
    SELECT DISTINCT t.episodio_id FROM t JOIN seq c ON c.persona_key = t.persona_key
        AND c.episodio_id NOT IN (t.episodio_id, t.d_id) AND c.cod_programa NOT IN (t.cod_programa, t.d_prog)
        AND c.s_primer - t.s_ultimo BETWEEN {RT.VENTANA_MIN} AND {RT.VENTANA_MAX}
)
SELECT t.episodio_id, t.d_id, t.persona_key, t.cod_programa, t.d_prog, t.periodo_admision,
       CASE WHEN t.periodo_admision ~ '^[0-9]{{4}}' THEN substr(t.periodo_admision, 1, 4)::int END,
       t.ultimo_periodo, t.d_primer, substr(t.d_primer, 1, 4)::int, t.d_adm, t.ultimo_estado_clase, t.brecha, t.tipo,
       CASE WHEN t.d47 THEN 'd47' WHEN t.d_adm = '{RT.ADMISION_ELECCION}' THEN 'via_es' ELSE 'ventana' END,
       t.tipo IN ('cambio_carrera', 'traslado_sede', 'traslado_otro'),
       t.episodio_id IN (SELECT episodio_id FROM amb)
FROM t
"""


# Notes on the pairs of episodes that are not transfers (P64, P69), one row per relation.
PROGRAMA_TRASLADOS_NOTA = f"""
INSERT INTO {{mart}}.programa_traslados_nota (clave, valor, nota)
{_TRASLADOS_CTE}
)
SELECT r.clave, count(t0.rel), r.nota
FROM (VALUES
    ('continuacion_estudios', 'P69: estudios posteriores a un egreso o titulacion; no es traslado'),
    ('doble_programa', 'P64: episodios superpuestos sin baja (doble programa); no es traslado ni se excluye de las poblaciones'),
    ('superposicion_con_baja', 'P64: episodios superpuestos cuyo origen termina en baja; es una salida de ese programa, no un traslado')
) AS r (clave, nota) LEFT JOIN t0 ON t0.rel = r.clave
GROUP BY r.clave, r.nota
"""

# (mart table, SQL) in build order.
BUILD_ORDER: List[Tuple[str, str]] = [
    ("indicador_periodo", INDICADOR_PERIODO),
    ("ficha_episodio", FICHA_EPISODIO),
    ("avance_malla", AVANCE_MALLA),
    ("cohorte_semestre", COHORTE_SEMESTRE),
    ("programa_semestre", PROGRAMA_SEMESTRE),
    ("cohorte_resultado", COHORTE_RESULTADO),
    ("postulante_contexto", POSTULANTE_CONTEXTO),
    ("programa_traslados", PROGRAMA_TRASLADOS),
    ("programa_traslados_nota", PROGRAMA_TRASLADOS_NOTA),
]

LATEST_PERIODO = """
SELECT max(periodo) FROM {core}.evento_estado
WHERE NOT es_correccion_sistema AND periodo ~ '^[0-9]{4}(10|20)$'
"""


def render(sql: str, schemas: Dict[str, str]) -> str:
    return sql.replace("{core}", schemas["core"]).replace("{mart}", schemas["mart"]).replace("{meta}", schemas["meta"])
