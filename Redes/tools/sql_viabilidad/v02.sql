-- R1 | reportes_deudas columnas
SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='banner' AND table_name IN ('reportes_deudas') ORDER BY ordinal_position
-- R2 | resumen_reporte_deudas columnas
SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='banner' AND table_name IN ('resumen_reporte_deudas') ORDER BY ordinal_position
-- R3 | tablas con columnas rut/rut_estudiante fuera de banner
SELECT c.table_schema, c.table_name, string_agg(c.column_name, ',') cols FROM information_schema.columns c JOIN information_schema.tables t ON t.table_schema=c.table_schema AND t.table_name=c.table_name AND t.table_type='BASE TABLE'
WHERE c.table_schema NOT IN ('pg_catalog','information_schema','bench','banner','percepcion','rag_tables') AND c.table_name !~ '_full$' AND c.column_name ~* '(^rut|rut_|estud|alumno|matricula)'
GROUP BY 1,2 ORDER BY 1,2
-- R4 | tablas ayudant / tutor / pasantia / practica en columnas de texto del catalogo (nombres de columna)
SELECT table_schema, table_name, column_name FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog','information_schema','bench','vcm','sirh1') AND table_name !~ '_full$' AND (column_name ~* '(ayudant|tutor|pasant|practic|titulaci|memoria|tesis|egresad|seguimiento|empleab)' OR table_name ~* '(ayudant|tutor|pasant|practic|tesis|memoria|egresad|seguimiento|empleab|encuesta)')
ORDER BY 1,2,3
-- R5 | vcm tablas ayudantia/estudiante
SELECT table_name FROM information_schema.tables WHERE table_schema='vcm' AND table_name !~ '_full$' AND table_name ~* '(estud|alumn|particip|ayud|tutor|servicio)' ORDER BY 1
-- R6 | sigda tablas con estudiantes
SELECT table_name FROM information_schema.tables WHERE table_schema='sigda' AND table_name !~ '_full$' ORDER BY 1
