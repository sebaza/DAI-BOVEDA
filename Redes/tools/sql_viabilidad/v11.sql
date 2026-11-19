-- R1 | familias de causal por periodo (E) desde 2023
SELECT periodo, count(*) e_total, sum((cod_causal ~ '^0')::int) fam0_art50, sum((cod_causal ~ '^2')::int) fam2_art52, sum((cod_causal ~ '^5')::int) fam5_art46_51, sum((cod_causal='84')::int) c84, sum((cod_causal='29')::int) c29med, sum((cod_causal IS NULL OR cod_causal='')::int) sin_causal FROM banner.ban_estados_academicos WHERE cod_estado='E' AND periodo>='202310' AND periodo ~ '[12]0$' GROUP BY 1 ORDER BY 1
-- R2 | malla_semestre patrones
SELECT regexp_replace(malla_semestre,'[0-9]+','NN','g') patron, count(*) filas, count(distinct malla_program_code) progs FROM banner.ban_malla_programa GROUP BY 1 ORDER BY 2 DESC LIMIT 10
-- R3 | creditaje cobertura y total por programa-catalogo
WITH t AS (SELECT malla_program_code, malla_ctlg, sum(malla_creditaje) cred, count(*) n, sum((malla_creditaje IS NULL)::int) nulos FROM banner.ban_malla_programa GROUP BY 1,2) SELECT count(*) prog_cat, sum((nulos>0)::int) con_nulos, percentile_cont(0.5) WITHIN GROUP (ORDER BY cred) mediana_cred, min(cred) cmin, max(cred) cmax FROM t
-- R4 | creditos en historia: unidad (distribucion de valores)
SELECT creditos, count(*) n FROM banner.ban_historia_notas WHERE periodo>='202010' GROUP BY 1 ORDER BY 2 DESC LIMIT 10
-- R5 | historia: oportunidad >=2 por anio y reprobaciones consecutivas derivables (n intentos con oportunidad>=2)
SELECT left(periodo,4) anio, sum((oportunidad::int>=2)::int) op2mas, sum((oportunidad::int>=3)::int) op3mas, sum((oportunidad::int=0)::int) op0, count(*) filas FROM banner.ban_historia_notas WHERE periodo>='201510' GROUP BY 1 ORDER BY 1
-- R6 | titulados: semestres_suspendidos y fecha cobertura por anio
SELECT year_titulacion, count(*) titulados, round(100.0*sum((fecha_titulacion IS NOT NULL)::int)/count(*),1) pct_fecha, sum((semestres_suspendidos>0)::int) con_susp FROM banner.banner_titulados WHERE year_titulacion>=2015 GROUP BY 1 ORDER BY 1
-- R7 | postgrado matricula por nivel (id_nivel) y programa, años 2023-2026 (oferta)
SELECT pd.id_nivel, count(distinct e.cod_programa) progs_con_estados, count(distinct e.rut) personas FROM banner.ban_estados_academicos_pos e JOIN common.programa_d pd ON pd.cod_banner=e.cod_programa WHERE e.periodo>='202310' GROUP BY 1 ORDER BY 1
