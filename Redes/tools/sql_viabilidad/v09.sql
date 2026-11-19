-- R1 | formatos de rut (solo patron)
SELECT 'banner_estados' fuente, regexp_replace(regexp_replace(rut,'[0-9]','9','g'),'[Kk]','K','g') patron, count(*) n FROM (SELECT rut FROM banner.ban_estados_academicos LIMIT 200000) x GROUP BY 1,2 ORDER BY 3 DESC LIMIT 4
-- R2 | formato rut vridt estudiantes
SELECT 'vridt_estud' fuente, regexp_replace(regexp_replace(rut,'[0-9]','9','g'),'[Kk]','K','g') patron, count(*) n FROM vridt.estudiantes_f GROUP BY 1,2 ORDER BY 3 DESC LIMIT 4
-- R3 | traslape de ruts de estudiantes autores con estados pregrado (sin guion/puntos)
WITH a AS (SELECT DISTINCT regexp_replace(upper(rut),'[^0-9K]','','g') r FROM vridt.estudiantes_f WHERE nivel='Pregrado'), b AS (SELECT DISTINCT regexp_replace(upper(rut),'[^0-9K]','','g') r FROM banner.ban_estados_academicos) SELECT (SELECT count(*) FROM a) autores_pregrado, count(*) en_estados FROM a JOIN b ON a.r=b.r
-- R4 | publicaciones con estudiante: anios
SELECT p.ano_publicacion anio, count(distinct e.id_publicacion) pubs_con_estudiante, count(distinct e.rut) estudiantes FROM vridt.estudiantes_f e JOIN vridt.publicacion_f p ON p.id_publicacion=e.id_publicacion GROUP BY 1 ORDER BY 1 DESC LIMIT 12
-- R5 | intercambio saliente por periodo
SELECT left(periodo,4) anio, count(*) filas, count(distinct rut) ruts FROM pde.intercambio_saliente_xls GROUP BY 1 ORDER BY 1
-- R6 | estudiantes inclusion por periodo
SELECT left(periodo,6) per, count(*) filas, count(distinct rut) ruts FROM pde.estudiantes_inclusion_xls GROUP BY 1 ORDER BY 1
-- R7 | VCM participantes: columnas
SELECT string_agg(column_name, ',' ORDER BY ordinal_position) cols FROM information_schema.columns WHERE table_schema='vcm' AND table_name='sivcm_participante'
-- R8 | sirh1.dgd_becario columnas
SELECT string_agg(column_name, ',' ORDER BY ordinal_position) cols FROM information_schema.columns WHERE table_schema='sirh1' AND table_name='dgd_becario'
-- R9 | articulados columnas y conteo
SELECT articulado, count(*) n, count(distinct cod_programa) progs FROM banner.programas_posgrado_articulados_pregrado GROUP BY 1 ORDER BY 2 DESC LIMIT 6
-- R10 | niveles de programa y area_conocimiento en programa_d
SELECT id_nivel, count(*) progs, sum((area_conocimiento IS NOT NULL AND area_conocimiento<>'')::int) con_area, sum(valid_program::int) validos FROM common.programa_d GROUP BY 1 ORDER BY 1
-- R11 | modalidad en programa_catalogos_d
SELECT modalidad, jornada, count(*) n, count(distinct cod_banner) progs FROM common.programa_catalogos_d GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12
