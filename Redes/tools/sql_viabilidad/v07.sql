-- R1 | oferta: cargas por timestamp
SELECT to_timestamp(timestamp_carga/1000.0)::date fecha_carga, count(*) filas, min(periodo) pmin, max(periodo) pmax, count(distinct periodo) np FROM banner.ban_oferta_academica_full GROUP BY timestamp_carga ORDER BY timestamp_carga DESC LIMIT 15
-- R2 | oferta: fechainicio/fechafin formato y primer valor por periodo reciente
SELECT periodo, min(fechainicio) fi_min, max(fechainicio) fi_max, min(fechafin) ff_min, max(fechafin) ff_max FROM banner.ban_oferta_academica WHERE periodo IN ('202410','202420','202510','202520','202610') GROUP BY 1 ORDER BY 1
-- R3 | prerequisitos: cobertura de cursos de la malla con alguna arista (codigos normalizados)
WITH m AS (SELECT DISTINCT malla_program_code cod, malla_ctlg ctlg, malla_materiacurso mc FROM banner.ban_malla_programa), p AS (SELECT DISTINCT pd.cod_banner cod, r.catalogo ctlg, replace(r.codigo_asignatura,'-','') mc FROM banner.malla_programa_prereq r JOIN common.programa_d pd ON pd.id=r.cod_programa) SELECT count(*) cursos_malla, sum((p.mc IS NOT NULL)::int) con_prereq, round(100.0*sum((p.mc IS NOT NULL)::int)/count(*),1) pct FROM m LEFT JOIN p ON p.cod=m.cod AND p.ctlg=m.ctlg AND p.mc=m.mc
-- R4 | prerequisitos: cobertura por semestre de malla (los de semestre 1 no deberian tener)
WITH m AS (SELECT DISTINCT malla_program_code cod, malla_ctlg ctlg, malla_materiacurso mc, malla_semestre sem FROM banner.ban_malla_programa), p AS (SELECT DISTINCT pd.cod_banner cod, r.catalogo ctlg, replace(r.codigo_asignatura,'-','') mc FROM banner.malla_programa_prereq r JOIN common.programa_d pd ON pd.id=r.cod_programa) SELECT m.sem, count(*) cursos, round(100.0*sum((p.mc IS NOT NULL)::int)/count(*),1) pct_con_prereq FROM m LEFT JOIN p ON p.cod=m.cod AND p.ctlg=m.ctlg AND p.mc=m.mc GROUP BY 1 ORDER BY 1 LIMIT 16
-- R5 | vridt.estudiantes_f: tipo, rol, nivel
SELECT tipo, rol, nivel, count(*) n, count(distinct rut) ruts FROM vridt.estudiantes_f GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 15
-- R6 | vridt.cargo_en_proyecto_f cargos
SELECT cargo, count(*) n, count(distinct rut) ruts, min(fecha_hora)::date desde, max(fecha_hora)::date hasta FROM vridt.cargo_en_proyecto_f GROUP BY 1 ORDER BY 2 DESC LIMIT 15
-- R7 | vridt publicacion anios
SELECT column_name FROM information_schema.columns WHERE table_schema='vridt' AND table_name IN ('publicacion_f') ORDER BY ordinal_position
-- R8 | postgrado: programa_catalogos_d y oferta_sies_d columnas
SELECT table_name, string_agg(column_name, ',' ORDER BY ordinal_position) cols FROM information_schema.columns WHERE table_schema='common' AND table_name IN ('programa_catalogos_d','oferta_sies_d') GROUP BY 1
