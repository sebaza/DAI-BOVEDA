-- R1 | causal: cobertura por estado y descripcion
SELECT cod_estado, count(*) filas, sum((cod_causal IS NOT NULL AND cod_causal<>'')::int) con_cod, sum((causal IS NOT NULL AND causal<>'')::int) con_texto, count(distinct cod_causal) n_cod, count(distinct causal) n_txt FROM banner.ban_estados_academicos GROUP BY 1 HAVING sum((cod_causal IS NOT NULL AND cod_causal<>'')::int)>0 ORDER BY 2 DESC
-- R2 | causal: codigo vs texto (valores distintos de codigos y textos, E)
SELECT cod_causal, left(causal,80) causal_txt, count(*) n, min(periodo) desde, max(periodo) hasta FROM banner.ban_estados_academicos WHERE cod_causal IS NOT NULL AND cod_causal<>'' GROUP BY 1,2 ORDER BY 3 DESC LIMIT 60
-- R3 | historia: nota no numerica y comentarios
SELECT CASE WHEN nota ~ '^[0-9]+([.,][0-9]+)?$' THEN 'numerica' ELSE nota END tipo_nota, count(*) n, min(periodo) desde, max(periodo) hasta FROM banner.ban_historia_notas GROUP BY 1 ORDER BY 2 DESC LIMIT 20
-- R4 | cobertura de cod_depto y creditos por anio en historia
SELECT left(periodo,4) anio, count(*) filas, round(100.0*sum((cod_depto IS NOT NULL AND cod_depto<>'')::int)/count(*),1) pct_depto, round(100.0*sum((creditos IS NOT NULL AND creditos>0)::int)/count(*),1) pct_cred, count(distinct cod_depto) n_depto FROM banner.ban_historia_notas WHERE periodo >= '201010' GROUP BY 1 ORDER BY 1
-- R5 | malla_formacion y malla_area distintos
SELECT left(malla_formacion,4) pref, count(*) filas, count(distinct malla_formacion) n_val, count(distinct malla_program_code) n_prog FROM banner.ban_malla_programa GROUP BY 1 ORDER BY 2 DESC LIMIT 25
-- R6 | malla_area valores
SELECT malla_area, count(*) filas, count(distinct malla_program_code) n_prog FROM banner.ban_malla_programa GROUP BY 1 ORDER BY 2 DESC LIMIT 25
-- R7 | oferta periodos recientes y tipo_clase
SELECT periodo, count(*) secciones, count(distinct cod_asignatura) asignaturas, sum((rut_profesor IS NOT NULL AND rut_profesor<>'')::int) con_prof FROM banner.ban_oferta_academica WHERE periodo >= '202410' AND periodo !~ '(50|60)$' GROUP BY 1 ORDER BY 1
-- R8 | oferta tipo_clase
SELECT tipo_clase, count(*) n FROM banner.ban_oferta_academica WHERE periodo !~ '(50|60)$' GROUP BY 1 ORDER BY 2 DESC LIMIT 25
