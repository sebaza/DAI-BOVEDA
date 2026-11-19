-- R1 | intercambio saliente por periodo
SELECT left(periodo::text,4) anio, count(*) filas, count(distinct rut) ruts FROM pde.intercambio_saliente_xls GROUP BY 1 ORDER BY 1
-- R2 | inclusion por periodo
SELECT left(periodo::text,4) anio, count(*) filas, count(distinct rut) ruts FROM pde.estudiantes_inclusion_xls GROUP BY 1 ORDER BY 1
-- R3 | deudas vs matricula pregrado por anio (cobertura de ruts)
WITH d AS (SELECT DISTINCT year, regexp_replace(upper(rut),'[^0-9K]','','g') r FROM banner.reportes_deudas), m AS (SELECT DISTINCT year, regexp_replace(upper(rut),'[^0-9K]','','g') r FROM banner.banner_matricula) SELECT m.year, count(*) matriculados, sum((d.r IS NOT NULL)::int) con_fila_deuda, round(100.0*sum((d.r IS NOT NULL)::int)/count(*),1) pct FROM m LEFT JOIN d ON d.year=m.year AND d.r=m.r WHERE m.year>=2017 GROUP BY 1 ORDER BY 1
-- R4 | deudas: distribucion saldo>0 por tramos y relacion con total deuda (aranceles)
SELECT year, round(100.0*sum((saldo_por_pagar>0)::int)/count(*),1) pct_saldo_pos, round(100.0*sum((saldo_por_pagar>0 AND saldo_por_pagar>=0.5*NULLIF(total_deuda_aranceles,0))::int)/count(*),1) pct_saldo_mayor_mitad FROM banner.reportes_deudas GROUP BY 1 ORDER BY 1
-- R5 | ban_estados 'A' anulacion semestre y 'P' retiro temporal por anio con fecha_estado
SELECT left(periodo,4) anio, cod_estado, count(*) filas, round(100.0*sum((fecha_estado IS NOT NULL)::int)/count(*),1) pct_fecha FROM banner.ban_estados_academicos WHERE cod_estado IN ('B','P','A','H','O','4','X') AND periodo>='201510' GROUP BY 1,2 ORDER BY 2,1
-- R6 | tutoria/AYU en historia de notas: titulo ayudantia como asignatura
SELECT count(*) intentos, count(distinct rut) personas, min(periodo) desde FROM banner.ban_historia_notas WHERE titulo ~* '(ayudant|tutor)'
-- R7 | cursos de formacion general: materia prefijo UNF? en historia (malla_formacion) - cobertura: asignaturas de historia presentes en alguna malla del programa del intento
WITH h AS (SELECT DISTINCT cod_carrera, catalogo, materia||'-'||curso mc FROM banner.ban_historia_notas WHERE periodo>='202010' AND nota<>'DPA'), m AS (SELECT DISTINCT malla_program_code cod, malla_ctlg ctlg, malla_materiacurso mc FROM banner.ban_malla_programa) SELECT count(*) combos, sum((m.mc IS NOT NULL)::int) en_malla FROM h LEFT JOIN m ON m.cod=h.cod_carrera AND m.ctlg=h.catalogo AND m.mc=h.mc
