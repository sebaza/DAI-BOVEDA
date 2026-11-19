-- DAI Neural: validaciones complementarias (solo lectura)
-- Ejecutar individualmente en DBeaver. Agregados solamente: no retorna RUT ni notas individuales.

-- C01 | SORLCUR: unicidad y repetición por persona (con categorías, sin identificar RUT)
WITH seq AS (
  SELECT rut, sorlcur, COUNT(*) AS n,
         COUNT(DISTINCT cod_programa) AS programas,
         COUNT(DISTINCT periodo) AS periodos
  FROM banner.ban_estados_academicos
  WHERE rut IS NOT NULL AND sorlcur IS NOT NULL
  GROUP BY rut, sorlcur
)
SELECT COUNT(*) AS pares_persona_sorlcur,
       COUNT(*) FILTER (WHERE n>1) AS pares_repetidos,
       MAX(n) AS max_filas_mismo_sorlcur,
       COUNT(*) FILTER (WHERE programas>1) AS pares_en_varios_programas,
       COUNT(*) FILTER (WHERE periodos>1) AS pares_en_varios_periodos
FROM seq;

-- C02 | SORLCUR: ¿el número ordena cronológicamente las fechas dentro del RUT?
WITH mov AS (
  SELECT rut, sorlcur, fecha_estado,
         LAG(fecha_estado) OVER (
            PARTITION BY rut ORDER BY sorlcur, fecha_estado
         ) AS fecha_anterior
  FROM banner.ban_estados_academicos
  WHERE rut IS NOT NULL AND sorlcur IS NOT NULL AND fecha_estado IS NOT NULL
)
SELECT COUNT(*) AS estados_con_fecha_y_orden,
       COUNT(*) FILTER (WHERE fecha_anterior IS NOT NULL AND fecha_estado<fecha_anterior)
         AS descensos_de_fecha_al_avanzar_sorlcur
FROM mov;
-- Descensos no prueban error: verificar carga retroactiva, rectificación o semántica del orden.

-- C03 | Cambio de ciclo/cambio de programa: distribución de cod_admision sin datos personales
SELECT cod_estado, COALESCE(cod_admision,'[NULL]') AS cod_admision,
       COUNT(*) AS registros,
       COUNT(DISTINCT rut) AS personas,
       COUNT(DISTINCT cod_programa) AS programas
FROM banner.ban_estados_academicos
WHERE cod_estado='D' OR cod_admision IS NOT NULL
GROUP BY cod_estado,cod_admision
ORDER BY registros DESC LIMIT 80;

-- C04 | Aprobación: notas 4,0 / DPA y estados de inscripción, solo agregado por nota+resultado
SELECT COALESCE(aprobacion,'[NULL]') AS aprobacion,
       COALESCE(estado,'[NULL]') AS estado,
       COUNT(*) AS inscripciones,
       COUNT(*) FILTER (WHERE REPLACE(BTRIM(COALESCE(nota,'')),',','.') ~ '^0*4(\.0+)?$') AS nota_4,
       COUNT(*) FILTER (WHERE UPPER(BTRIM(COALESCE(nota,'')))='DPA') AS nota_dpa
FROM banner.ban_inscripciones
GROUP BY aprobacion,estado
ORDER BY inscripciones DESC;

-- C05 | Cobertura por año del vínculo con oferta de profesores, sin join multiplicativo
WITH notas AS (
 SELECT LEFT(periodo,4) AS anio, periodo, nrc, COUNT(*) AS filas_notas
 FROM banner.ban_historia_notas
 WHERE nrc IS NOT NULL AND BTRIM(nrc)<>''
 GROUP BY LEFT(periodo,4), periodo, nrc
), oferta AS (
 SELECT DISTINCT periodo,nrc
 FROM banner.ban_oferta_academica
 WHERE nrc IS NOT NULL AND BTRIM(nrc)<>''
)
SELECT n.anio,
       SUM(n.filas_notas) AS notas_total,
       SUM(n.filas_notas) FILTER (WHERE o.nrc IS NOT NULL) AS notas_vinculadas,
       ROUND(100.0*SUM(n.filas_notas) FILTER (WHERE o.nrc IS NOT NULL)/NULLIF(SUM(n.filas_notas),0),2) AS pct_vinculadas
FROM notas n LEFT JOIN oferta o USING (periodo,nrc)
GROUP BY n.anio ORDER BY n.anio;

-- C06 | Tabla common.programa_d: ¿el mapping id↔cod_banner es unívoco?
SELECT COUNT(*) AS filas,
       COUNT(DISTINCT id) AS ids,
       COUNT(DISTINCT cod_banner) AS codigos_banner,
       COUNT(*) FILTER (WHERE cod_banner IS NULL OR BTRIM(cod_banner)='') AS cod_banner_vacio
FROM common.programa_d;

-- C07 | Mallas: cobertura de la FK esperada (malla.cod_programa a programa_d.id)
SELECT COUNT(*) AS filas_malla,
       COUNT(*) FILTER (WHERE p.id IS NULL) AS sin_programa_d,
       COUNT(DISTINCT (m.cod_programa,m.catalogo)) AS programas_catalogos,
       COUNT(DISTINCT (m.cod_programa,m.catalogo)) FILTER (WHERE p.id IS NULL) AS combinaciones_sin_mapping
FROM banner.malla_programa m
LEFT JOIN common.programa_d p ON p.id=m.cod_programa;

-- C08 | Estados `fecha_estado` nula/futura por tipo de estado
SELECT COALESCE(cod_estado,'[NULL]') AS cod_estado,
       COUNT(*) AS registros,
       COUNT(*) FILTER (WHERE fecha_estado IS NULL) AS sin_fecha,
       COUNT(*) FILTER (WHERE fecha_estado>CURRENT_TIMESTAMP) AS fecha_futura
FROM banner.ban_estados_academicos
GROUP BY cod_estado ORDER BY registros DESC;

-- C09 | DPA = convalidación; distribución por inscripción/resultado (solo agregados).
-- Ojo: DPA en nota de historia puede no estar en ban_inscripciones; no asumir equivalencia de cobertura.
SELECT COALESCE(estado, '[NULL]') AS estado,
       COALESCE(aprobacion, '[NULL]') AS aprobacion,
       COUNT(*) AS registros
FROM banner.ban_inscripciones
WHERE UPPER(BTRIM(COALESCE(nota, ''))) = 'DPA'
GROUP BY estado, aprobacion ORDER BY registros DESC;

-- C10 | sORLCUR sigue al RUT al pasar entre programas: cuántas transiciones
-- entre posiciones sucesivas de una persona están asociadas con cambio de programa.
WITH seq AS (
 SELECT rut, sorlcur, cod_programa,
        LAG(cod_programa) OVER (PARTITION BY rut ORDER BY sorlcur, periodo) AS programa_anterior,
        LAG(sorlcur) OVER (PARTITION BY rut ORDER BY sorlcur, periodo) AS posicion_anterior
 FROM banner.ban_estados_academicos
 WHERE rut IS NOT NULL AND sorlcur IS NOT NULL
)
SELECT COUNT(*) FILTER (WHERE programa_anterior IS NOT NULL) AS pasos_observables,
       COUNT(*) FILTER (WHERE programa_anterior IS DISTINCT FROM cod_programa
                        AND posicion_anterior IS NOT NULL) AS pasos_con_cambio_programa,
       COUNT(*) FILTER (WHERE programa_anterior IS DISTINCT FROM cod_programa
                        AND posicion_anterior IS NOT NULL
                        AND sorlcur > posicion_anterior) AS cambios_programa_orden_ascendente
FROM seq;
