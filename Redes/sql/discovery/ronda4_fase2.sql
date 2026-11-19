-- DAI Neural — Ronda 4 (preparación Fase 2). SOLO LECTURA, solo agregados.
-- Ejecutar con: Redes/tools/run_readonly_sql.py

-- R31 | M3: unicidad de claves candidatas en ban_inscripciones
SELECT COUNT(*) AS filas,
       COUNT(DISTINCT (periodo, rut, nrc)) AS k_periodo_rut_nrc,
       COUNT(DISTINCT (periodo, rut, materia_curso_inscrito)) AS k_periodo_rut_materia,
       COUNT(DISTINCT (periodo, rut, nrc, materia_curso_inscrito)) AS k_periodo_rut_nrc_materia,
       COUNT(DISTINCT (periodo, rut, nrc, materia_curso_inscrito, estado)) AS k_con_estado,
       COUNT(DISTINCT (periodo, rut, nrc, materia_curso_inscrito, estado, oportunidad)) AS k_con_estado_oport,
       COUNT(*) FILTER (WHERE nrc IS NULL OR BTRIM(nrc::text) = '') AS nrc_vacio,
       COUNT(*) FILTER (WHERE materia_curso_inscrito IS NULL) AS materia_null
FROM banner.ban_inscripciones;

-- R32 | M3: qué distingue las filas repetidas por (periodo, rut, nrc)
WITH g AS (
  SELECT periodo, rut, nrc, COUNT(*) AS n,
         COUNT(DISTINCT estado) AS v_estado, COUNT(DISTINCT materia_curso_inscrito) AS v_materia,
         COUNT(DISTINCT oportunidad) AS v_oport, COUNT(DISTINCT aprobacion) AS v_aprob,
         COUNT(DISTINCT materia_curso_catalogo) AS v_mat_cat
  FROM banner.ban_inscripciones GROUP BY 1,2,3 HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS grupos, MAX(n) AS max_filas,
       COUNT(*) FILTER (WHERE v_estado > 1) AS varia_estado,
       COUNT(*) FILTER (WHERE v_materia > 1) AS varia_materia_inscrito,
       COUNT(*) FILTER (WHERE v_mat_cat > 1) AS varia_materia_catalogo,
       COUNT(*) FILTER (WHERE v_oport > 1) AS varia_oportunidad,
       COUNT(*) FILTER (WHERE v_aprob > 1) AS varia_aprobacion
FROM g;

-- R33 | Formato de materia_curso_* en inscripciones (patrón)
SELECT campo, REGEXP_REPLACE(REGEXP_REPLACE(v, '[A-Za-z]', 'A', 'g'), '[0-9]', '9', 'g') AS patron, COUNT(*) AS filas
FROM (SELECT 'inscrito' AS campo, materia_curso_inscrito AS v FROM banner.ban_inscripciones
      UNION ALL SELECT 'catalogo', materia_curso_catalogo FROM banner.ban_inscripciones) x
GROUP BY 1,2 HAVING COUNT(*) >= 20 ORDER BY 1, filas DESC;

-- R34 | Reversas (1,2,5): ¿cambian programa/admisión respecto del estado anterior y siguiente?
WITH s AS (
  SELECT cod_estado, cod_programa, cod_admision, periodo_admision,
         LAG(cod_programa) OVER w AS ant_prog, LEAD(cod_programa) OVER w AS sig_prog,
         LAG(cod_admision) OVER w AS ant_adm, LAG(periodo_admision) OVER w AS ant_per_adm,
         LAG(cod_estado) OVER w AS ant_estado
  FROM banner.ban_estados_academicos
  WINDOW w AS (PARTITION BY rut ORDER BY periodo, sorlcur)
)
SELECT cod_estado, COALESCE(ant_estado,'[sin]') AS estado_anterior,
       COUNT(*) AS casos,
       COUNT(*) FILTER (WHERE ant_prog IS DISTINCT FROM cod_programa) AS cambia_programa_vs_anterior,
       COUNT(*) FILTER (WHERE ant_adm IS DISTINCT FROM cod_admision OR ant_per_adm IS DISTINCT FROM periodo_admision) AS cambia_admision_vs_anterior,
       COUNT(*) FILTER (WHERE sig_prog IS DISTINCT FROM cod_programa) AS cambia_programa_vs_siguiente
FROM s WHERE cod_estado IN ('1','2','5')
GROUP BY 1,2 ORDER BY 1, casos DESC;

-- R35 | Historia ↔ malla oficial: cobertura de materia||'-'||curso en ban_malla_programa (mismo programa y catálogo / mismo programa / cualquier)
WITH h AS (
  SELECT cod_carrera, catalogo, materia || '-' || curso AS cod, COUNT(*) AS filas
  FROM banner.ban_historia_notas GROUP BY 1,2,3
), m AS (SELECT DISTINCT malla_program_code AS prog, malla_ctlg AS cat, malla_materiacurso AS cod FROM banner.ban_malla_programa),
mp AS (SELECT DISTINCT malla_program_code AS prog, malla_materiacurso AS cod FROM banner.ban_malla_programa),
ma AS (SELECT DISTINCT malla_materiacurso AS cod FROM banner.ban_malla_programa)
SELECT SUM(h.filas) AS filas_notas,
       SUM(h.filas) FILTER (WHERE m.cod IS NOT NULL) AS en_malla_mismo_cat,
       SUM(h.filas) FILTER (WHERE m.cod IS NULL AND mp.cod IS NOT NULL) AS en_malla_otro_cat,
       SUM(h.filas) FILTER (WHERE mp.cod IS NULL AND ma.cod IS NOT NULL) AS en_malla_otro_programa,
       SUM(h.filas) FILTER (WHERE ma.cod IS NULL) AS fuera_de_toda_malla
FROM h
LEFT JOIN m ON m.prog = h.cod_carrera AND m.cat = h.catalogo AND m.cod = h.cod
LEFT JOIN mp ON mp.prog = h.cod_carrera AND mp.cod = h.cod
LEFT JOIN ma ON ma.cod = h.cod;

-- R36 | Episodio de cada intento: candidatos por (rut, programa) con periodo dentro del rango del episodio
WITH e AS (
  SELECT rut, cod_programa, cod_admision, periodo_admision, MIN(periodo) AS p_ini, MAX(periodo) AS p_fin
  FROM banner.ban_estados_academicos WHERE cod_estado IS NULL OR cod_estado NOT IN ('1','2','5')
  GROUP BY 1,2,3,4
), h AS (
  SELECT rut, cod_carrera, periodo, COUNT(*) AS filas FROM banner.ban_historia_notas GROUP BY 1,2,3
), c AS (
  SELECT h.rut, h.cod_carrera, h.periodo, h.filas, COUNT(e.rut) AS candidatos
  FROM h LEFT JOIN e ON e.rut = h.rut AND e.cod_programa = h.cod_carrera AND h.periodo BETWEEN e.p_ini AND e.p_fin
  GROUP BY 1,2,3,4
)
SELECT CASE WHEN candidatos >= 2 THEN '2+' ELSE candidatos::text END AS candidatos, SUM(filas) AS filas_notas, COUNT(*) AS persona_periodos
FROM c GROUP BY 1 ORDER BY 1;

-- R37 | Sexo, región y comuna: completitud (M1/M2), sin valores individuales
SELECT 'estados.sexo' AS campo, COUNT(*) AS filas, COUNT(*) FILTER (WHERE sexo IS NULL OR BTRIM(sexo)='') AS vacios, COUNT(DISTINCT sexo) AS valores
FROM banner.ban_estados_academicos
UNION ALL SELECT 'admision.sexo', COUNT(*), COUNT(*) FILTER (WHERE sexo IS NULL OR BTRIM(sexo)=''), COUNT(DISTINCT sexo) FROM banner.banner_admision
UNION ALL SELECT 'admision.region_colegio', COUNT(*), COUNT(*) FILTER (WHERE region_colegio IS NULL OR BTRIM(region_colegio)=''), COUNT(DISTINCT region_colegio) FROM banner.banner_admision
UNION ALL SELECT 'admision.comuna_colegio', COUNT(*), COUNT(*) FILTER (WHERE comuna_colegio IS NULL OR BTRIM(comuna_colegio)=''), COUNT(DISTINCT comuna_colegio) FROM banner.banner_admision
UNION ALL SELECT 'admision.cod_comuna', COUNT(*), COUNT(*) FILTER (WHERE cod_comuna IS NULL OR BTRIM(cod_comuna)=''), COUNT(DISTINCT cod_comuna) FROM banner.banner_admision;

-- R38 | Tipos de datos de las columnas a extraer (metadatos)
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'banner'
  AND table_name IN ('ban_inscripciones','ban_oferta_academica','banner_matricula','banner_catalogos','banner_estudiantes_postgrado')
ORDER BY table_name, ordinal_position;
