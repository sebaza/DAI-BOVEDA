-- DAI Neural — Ronda 5 (reconstrucción consolidada, etapa A). SOLO LECTURA, solo agregados.
-- Ejecutar con: Redes/tools/run_readonly_sql.py

-- R51 | P76: columnas de programa_d y de las vistas candidatas con nom_depto
SELECT table_schema, table_name, column_name FROM information_schema.columns
WHERE column_name IN ('nom_depto', 'nombre_estandar') ORDER BY 1, 2, 3;

-- R52 | P76: columnas de common.programa_d
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'common' AND table_name = 'programa_d' ORDER BY ordinal_position;

-- R53 | P77: columnas de banner.ban_estados_academicos_pos
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'banner' AND table_name = 'ban_estados_academicos_pos' ORDER BY ordinal_position;

-- R54 | P77: tablas hermanas de ban_estados_academicos_pos
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_name LIKE 'ban_estados_academicos%' ORDER BY 1, 2;

-- R55 | P77: cobertura de ban_estados_academicos_pos (filas, personas, períodos, programas)
SELECT COUNT(*) AS filas, COUNT(DISTINCT rut) AS personas, MIN(periodo) AS periodo_min, MAX(periodo) AS periodo_max,
       COUNT(DISTINCT cod_programa) AS programas, COUNT(DISTINCT nombre_estandar) AS nombres_estandar,
       COUNT(*) FILTER (WHERE nombre_estandar IS NULL OR BTRIM(nombre_estandar) = '') AS sin_nombre_estandar,
       COUNT(*) FILTER (WHERE nombre_banner IS NULL OR BTRIM(nombre_banner) = '') AS sin_nombre_banner
FROM banner.ban_estados_academicos_pos;

-- R56 | P77: estados de postgrado (código y nombre)
SELECT cod_estado, nombre_estado, COUNT(*) AS filas, COUNT(DISTINCT rut) AS personas
FROM banner.ban_estados_academicos_pos GROUP BY 1, 2 ORDER BY 3 DESC;

-- R57 | P80: personas con estado de matrícula por año (ban_estados_academicos_pos), todos los estados y solo cod_estado AS/MA
SELECT SUBSTRING(periodo, 1, 4) AS anio, COUNT(DISTINCT rut) AS personas, COUNT(*) AS filas,
       COUNT(DISTINCT cod_programa) AS programas
FROM banner.ban_estados_academicos_pos GROUP BY 1 ORDER BY 1;

-- R58 | P80: la misma serie en la fuente actual banner_estudiantes_postgrado (MATRICULADO)
SELECT SUBSTRING(periodo, 1, 4) AS anio, COUNT(DISTINCT rut) AS personas, COUNT(*) AS filas
FROM banner.banner_estudiantes_postgrado WHERE estado_matricula = 'MATRICULADO' GROUP BY 1 ORDER BY 1;

-- R59 | P77: programas de ban_estados_academicos_pos con su nombre estándar y nombre banner (códigos y nombres; sin personas)
SELECT cod_programa, nombre_estandar, nombre_banner, COUNT(*) AS filas, MIN(periodo) AS desde, MAX(periodo) AS hasta
FROM banner.ban_estados_academicos_pos GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

-- R60 | P77: solapamiento de programas entre ban_estados_academicos_pos y banner_estudiantes_postgrado
SELECT (SELECT COUNT(DISTINCT cod_programa) FROM banner.ban_estados_academicos_pos) AS prog_pos,
       (SELECT COUNT(DISTINCT cod_programa) FROM banner.banner_estudiantes_postgrado) AS prog_estudiantes,
       (SELECT COUNT(DISTINCT cod_programa) FROM banner.ban_estados_academicos_pos
          WHERE cod_programa IN (SELECT cod_programa FROM banner.banner_estudiantes_postgrado)) AS comunes;

-- R61 | P80: personas con estado Matriculado (M) por año en ban_estados_academicos_pos
SELECT SUBSTRING(periodo, 1, 4) AS anio, COUNT(DISTINCT rut) AS personas_m
FROM banner.ban_estados_academicos_pos WHERE cod_estado = 'M' GROUP BY 1 ORDER BY 1;

-- R62 | P80: personas MATRICULADO en banner_estudiantes_postgrado que también tienen estado M ese año en la fuente de estados
WITH a AS (SELECT DISTINCT rut, SUBSTRING(periodo, 1, 4) AS anio FROM banner.banner_estudiantes_postgrado WHERE estado_matricula = 'MATRICULADO'),
     b AS (SELECT DISTINCT rut, SUBSTRING(periodo, 1, 4) AS anio FROM banner.ban_estados_academicos_pos WHERE cod_estado = 'M')
SELECT a.anio, COUNT(*) AS personas_estudiantes, COUNT(b.rut) AS tambien_en_estados
FROM a LEFT JOIN b ON a.rut = b.rut AND a.anio = b.anio GROUP BY 1 ORDER BY 1;

-- R63 | P77: códigos de programa de postgrado en el diccionario de programas
SELECT id_nivel, COUNT(*) AS programas, COUNT(*) FILTER (WHERE cod_banner ~ '^[67][0-9]{3}$') AS con_codigo_6xxx_7xxx,
       MIN(cod_banner) AS cod_min, MAX(cod_banner) AS cod_max
FROM common.programa_d GROUP BY 1 ORDER BY 1;

-- R64 | P77: los programas de estados de postgrado frente al diccionario de programas
SELECT COUNT(DISTINCT e.cod_programa) AS programas_estados,
       COUNT(DISTINCT e.cod_programa) FILTER (WHERE d.id IS NOT NULL) AS en_programa_d
FROM banner.ban_estados_academicos_pos e LEFT JOIN common.programa_d d ON d.cod_banner = e.cod_programa;

-- R65 | P77: tipos de programa por palabra inicial del nombre estándar (filas y programas)
SELECT SPLIT_PART(COALESCE(nombre_estandar, '(sin nombre)'), ' ', 1) AS inicio, COUNT(DISTINCT cod_programa) AS programas, COUNT(*) AS filas
FROM banner.ban_estados_academicos_pos GROUP BY 1 ORDER BY 3 DESC;

-- R66 | P77: niveles de programa (diccionario)
SELECT * FROM common.nivel_programa_d ORDER BY 1;

-- R67 | P77: programas de estados de postgrado sin entrada en el diccionario o sin nombre estándar
SELECT e.cod_programa, MAX(e.nombre_banner) AS nombre_banner, MAX(e.nombre_estandar) AS nombre_estandar, d.id_nivel, COUNT(*) AS filas
FROM banner.ban_estados_academicos_pos e LEFT JOIN common.programa_d d ON d.cod_banner = e.cod_programa
GROUP BY 1, 4 HAVING d.id_nivel IS NULL OR MAX(e.nombre_estandar) IS NULL ORDER BY 1;

-- R68 | P77: nivel del diccionario frente a la palabra inicial del nombre estándar
SELECT d.id_nivel, SPLIT_PART(COALESCE(e.nombre_estandar,'(sin nombre)'), ' ', 1) AS inicio, COUNT(DISTINCT e.cod_programa) AS programas
FROM banner.ban_estados_academicos_pos e LEFT JOIN common.programa_d d ON d.cod_banner = e.cod_programa
GROUP BY 1, 2 ORDER BY 1, 2;

-- R69 | P78/P79: sufijos de período en estados de postgrado
SELECT SUBSTRING(periodo, 5, 2) AS sufijo, COUNT(*) AS filas, COUNT(DISTINCT rut) AS personas FROM banner.ban_estados_academicos_pos GROUP BY 1 ORDER BY 1;

-- R70 | tabla de cargas / marca de carga de la fuente de estados de postgrado
SELECT COUNT(*) AS filas, COUNT(DISTINCT timestamp_carga) AS cargas, MAX(timestamp_carga) AS ultima FROM banner.ban_estados_academicos_pos_full;
