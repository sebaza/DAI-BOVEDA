-- R1 | columnas de tablas clave
SELECT table_name, string_agg(column_name, ',' ORDER BY ordinal_position) cols FROM information_schema.columns WHERE table_schema='banner' AND table_name IN ('ban_malla_programa','banner_titulados','banner_programas','programas_posgrado_articulados_pregrado','programas_posgrado_articulados_pregrado2','ban_oferta_academica','estudiantes_por_nivel_vigentes_consolidados','mallas_curriculares_flexibles','programa_doble_titulo','estudiantes_posgrado_cotutela_tesis','oferta_profesor_f') GROUP BY 1
-- R2 | common.programa_d columnas
SELECT string_agg(column_name, ',' ORDER BY ordinal_position) cols FROM information_schema.columns WHERE table_schema='common' AND table_name='programa_d'
-- R3 | columnas con modalidad / jornada / regimen
SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema','vcm','sirh1','sigda','bench') AND table_name !~ '_full$' AND column_name ~* '(modalidad|jornada|regimen|b_learning|online|presencial)' ORDER BY 1,2
-- R4 | ses.casos motivos
SELECT motivo, nivel, count(*) n, min(fecha_ingreso) desde, max(fecha_ingreso) hasta FROM ses.casos GROUP BY 1,2 ORDER BY 3 DESC
-- R5 | ses.casos estado y resolucion
SELECT estado_caso, etapa, count(*) n FROM ses.casos GROUP BY 1,2 ORDER BY 3 DESC
