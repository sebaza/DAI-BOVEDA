-- R1 | causal E por anio: cobertura del texto
SELECT left(periodo,4) anio, count(*) e_filas, round(100.0*sum((cod_causal IS NOT NULL AND cod_causal<>'')::int)/count(*),1) pct_con_causal FROM banner.ban_estados_academicos WHERE cod_estado='E' AND periodo>='201010' GROUP BY 1 ORDER BY 1
-- R2 | titulos tipo practica/titulo en malla (por patron de nombre)
SELECT CASE WHEN malla_asignatura ~* 'pr[aá]ctica' THEN 'practica' WHEN malla_asignatura ~* 'capstone' THEN 'capstone' WHEN malla_asignatura ~* '(proyecto|trabajo|seminario|memoria|tesis|examen).{0,12}(t[ií]tulo|grado|titulaci)' THEN 'titulo_grado' WHEN malla_asignatura ~* '(t[ií]tulo|titulaci|grado)' THEN 'otro_titulo' WHEN malla_asignatura ~* 'internado' THEN 'internado' ELSE 'resto' END tipo, count(*) filas_malla, count(distinct malla_program_code) n_prog, count(distinct malla_materiacurso) n_codigos FROM banner.ban_malla_programa GROUP BY 1 ORDER BY 2 DESC
-- R3 | practica/titulo en historia de notas por anio (intentos)
SELECT CASE WHEN titulo ~* 'pr[aá]ctica' THEN 'practica' WHEN titulo ~* 'capstone' THEN 'capstone' WHEN titulo ~* '(proyecto|trabajo|seminario|memoria|tesis|examen).{0,12}(t[ií]tulo|grado|titulaci)' THEN 'titulo_grado' WHEN titulo ~* 'internado' THEN 'internado' ELSE NULL END tipo, count(*) intentos, count(distinct rut) personas, min(periodo) desde, max(periodo) hasta FROM banner.ban_historia_notas WHERE periodo>='201510' GROUP BY 1 ORDER BY 2 DESC
-- R4 | nombres de asignatura de capstone/practica mas frecuentes (por titulo)
SELECT left(titulo,60) titulo, count(*) intentos, count(distinct cod_carrera) n_prog FROM banner.ban_historia_notas WHERE periodo>='201510' AND (titulo ~* 'capstone' OR titulo ~* 'pr[aá]ctica profesional' OR titulo ~* '(proyecto|trabajo|seminario|memoria|tesis).{0,12}(t[ií]tulo|grado|titulaci)') GROUP BY 1 ORDER BY 2 DESC LIMIT 25
-- R5 | DPA por anio y comentario CONVA
SELECT left(periodo,4) anio, sum((nota='DPA')::int) dpa, sum((comentario='CONVA')::int) conva, sum((comentario IN ('CCAT','CCAR'))::int) cambio_carrera_cat, count(*) filas FROM banner.ban_historia_notas WHERE periodo>='201010' GROUP BY 1 ORDER BY 1
-- R6 | inscripciones: equivalencias (catalogo distinto de inscrito)
SELECT periodo, count(*) filas, sum((materia_curso_catalogo IS DISTINCT FROM materia_curso_inscrito)::int) distinto, sum((estado LIKE 'RENUNCIADA%')::int) renuncias FROM banner.ban_inscripciones GROUP BY 1 ORDER BY 1
-- R7 | AYU: secciones y rut_profesor que son estudiantes matriculados (aprox: rut presente en estados M del mismo periodo)
SELECT o.periodo, count(*) secciones_ayu, count(distinct o.rut_profesor) ruts_ayu, count(distinct CASE WHEN e.rut IS NOT NULL THEN o.rut_profesor END) ruts_que_son_estudiantes FROM banner.ban_oferta_academica o LEFT JOIN banner.ban_estados_academicos e ON e.rut=o.rut_profesor AND e.periodo=o.periodo AND e.cod_estado='M' WHERE o.tipo_clase='AYU' AND o.periodo>='202010' AND o.periodo !~ '(50|60)$' GROUP BY 1 ORDER BY 1
-- R8 | tipo_profesor valores en AYU
SELECT tipo_profesor, tipo_clase, count(*) n FROM banner.ban_oferta_academica WHERE tipo_clase IN ('AYU','CAT') AND periodo>='201610' GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15
