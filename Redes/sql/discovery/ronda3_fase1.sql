-- DAI Neural — Ronda 3 de descubrimiento (Fase 1). SOLO LECTURA, solo agregados.
-- Ejecutar con: Redes/tools/run_readonly_sql.py (sesión read-only + statement_timeout).
-- Ningún bloque retorna RUT, nombres, fechas de nacimiento ni notas individuales.
-- Fuente: vistas vigentes de banner.* (estados/notas usan la carga marcada vigente; el resto, max timestamp_carga).

-- R01 | Diccionario completo de estados (cod_estado + nombre_estado) con volumen
SELECT COALESCE(cod_estado,'[NULL]') AS cod_estado, COALESCE(nombre_estado,'[NULL]') AS nombre_estado,
       COUNT(*) AS registros, COUNT(DISTINCT rut) AS personas,
       MIN(periodo) AS periodo_min, MAX(periodo) AS periodo_max
FROM banner.ban_estados_academicos
GROUP BY 1,2 ORDER BY registros DESC;

-- R02 | Diccionario de tipos de admisión (vista ban_tipo_admision)
SELECT cod_admision, admision, tipo_qualitas, tipo_cna, ingreso_ordinario, ingreso_total
FROM banner.ban_tipo_admision ORDER BY cod_admision, admision;

-- R03 | Uso de cod_admision en estados (sin LIMIT)
SELECT COALESCE(cod_admision,'[NULL]') AS cod_admision, COALESCE(admision,'[NULL]') AS admision,
       COUNT(*) AS registros, COUNT(DISTINCT rut) AS personas, COUNT(DISTINCT cod_programa) AS programas
FROM banner.ban_estados_academicos GROUP BY 1,2 ORDER BY registros DESC;

-- R04 | Formato de periodo y orden (P01): periodo vs sorlcur vs fecha_estado dentro del RUT
WITH s AS (
  SELECT rut, sorlcur, periodo, fecha_estado,
         LAG(periodo) OVER w AS p_prev, LAG(fecha_estado) OVER w AS f_prev
  FROM banner.ban_estados_academicos
  WINDOW w AS (PARTITION BY rut ORDER BY sorlcur)
)
SELECT COUNT(*) AS filas,
       COUNT(*) FILTER (WHERE periodo !~ '^[0-9]{6}$' OR periodo IS NULL) AS periodo_no_6_digitos,
       COUNT(*) FILTER (WHERE p_prev IS NOT NULL) AS pasos,
       COUNT(*) FILTER (WHERE periodo < p_prev) AS periodo_desciende_al_subir_sorlcur,
       COUNT(*) FILTER (WHERE periodo = p_prev) AS mismo_periodo,
       COUNT(*) FILTER (WHERE fecha_estado < f_prev) AS fecha_desciende,
       COUNT(*) FILTER (WHERE fecha_estado < f_prev AND periodo < p_prev) AS fecha_y_periodo_descienden,
       COUNT(*) FILTER (WHERE fecha_estado < f_prev AND periodo = p_prev) AS fecha_desciende_mismo_periodo,
       COUNT(*) FILTER (WHERE fecha_estado < f_prev AND periodo > p_prev) AS fecha_desciende_periodo_sube
FROM s;

-- R05 | Orden alternativo (periodo, sorlcur): descensos de fecha restantes
WITH s AS (
  SELECT fecha_estado, LAG(fecha_estado) OVER (PARTITION BY rut ORDER BY periodo, sorlcur) AS f_prev
  FROM banner.ban_estados_academicos
)
SELECT COUNT(*) FILTER (WHERE f_prev IS NOT NULL AND fecha_estado IS NOT NULL) AS pasos_con_fecha,
       COUNT(*) FILTER (WHERE fecha_estado < f_prev) AS fecha_desciende
FROM s;

-- R06 | Integridad de sorlcur por RUT: NULL, no enteros, saltos
WITH p AS (
  SELECT rut, COUNT(*) AS n, MIN(sorlcur) AS mn, MAX(sorlcur) AS mx,
         COUNT(*) FILTER (WHERE sorlcur IS NULL) AS nulos,
         COUNT(*) FILTER (WHERE sorlcur <> TRUNC(sorlcur)) AS no_enteros
  FROM banner.ban_estados_academicos GROUP BY rut
)
SELECT COUNT(*) AS personas, SUM(nulos) AS sorlcur_null, SUM(no_enteros) AS sorlcur_no_entero,
       MIN(mn) AS sorlcur_min_global, MAX(mx) AS sorlcur_max_global,
       COUNT(*) FILTER (WHERE mx - mn + 1 > n) AS personas_con_saltos,
       SUM(GREATEST(mx - mn + 1 - n, 0)) AS posiciones_faltantes,
       COUNT(*) FILTER (WHERE mn = 1) AS personas_que_parten_en_1
FROM p;

-- R07 | Episodio candidato (P06) = (rut, cod_programa, cod_admision, periodo_admision): tamaño y nulos
SELECT COUNT(*) AS filas,
       COUNT(*) FILTER (WHERE cod_programa IS NULL OR cod_admision IS NULL OR periodo_admision IS NULL) AS filas_con_componente_null,
       COUNT(*) FILTER (WHERE cod_programa IS NULL) AS cod_programa_null,
       COUNT(*) FILTER (WHERE cod_admision IS NULL) AS cod_admision_null,
       COUNT(*) FILTER (WHERE periodo_admision IS NULL) AS periodo_admision_null,
       COUNT(DISTINCT (rut, cod_programa, cod_admision, periodo_admision)) AS episodios,
       COUNT(DISTINCT rut) AS personas,
       COUNT(DISTINCT (rut, cod_programa)) AS pares_persona_programa
FROM banner.ban_estados_academicos;

-- R08 | Episodios por persona y contigüidad en la secuencia sorlcur
WITH s AS (
  SELECT rut, sorlcur, cod_programa, cod_admision, periodo_admision, catalogo,
         CASE WHEN (cod_programa, cod_admision, periodo_admision) IS NOT DISTINCT FROM
                   (LAG(cod_programa) OVER w, LAG(cod_admision) OVER w, LAG(periodo_admision) OVER w)
              THEN 0 ELSE 1 END AS inicia_tramo
  FROM banner.ban_estados_academicos
  WINDOW w AS (PARTITION BY rut ORDER BY sorlcur)
), e AS (
  SELECT rut, cod_programa, cod_admision, periodo_admision,
         SUM(inicia_tramo) AS tramos, COUNT(DISTINCT catalogo) AS catalogos, COUNT(*) AS estados
  FROM s GROUP BY 1,2,3,4
), pp AS (SELECT rut, COUNT(*) AS episodios FROM e GROUP BY rut)
SELECT 'episodios_no_contiguos' AS metrica, COUNT(*)::text AS valor FROM e WHERE tramos > 1
UNION ALL SELECT 'episodios_con_mas_de_un_catalogo', COUNT(*)::text FROM e WHERE catalogos > 1
UNION ALL SELECT 'episodios_un_solo_estado', COUNT(*)::text FROM e WHERE estados = 1
UNION ALL SELECT 'personas_1_episodio', COUNT(*)::text FROM pp WHERE episodios = 1
UNION ALL SELECT 'personas_2_episodios', COUNT(*)::text FROM pp WHERE episodios = 2
UNION ALL SELECT 'personas_3_episodios', COUNT(*)::text FROM pp WHERE episodios = 3
UNION ALL SELECT 'personas_4mas_episodios', COUNT(*)::text FROM pp WHERE episodios >= 4
UNION ALL SELECT 'max_episodios_por_persona', MAX(episodios)::text FROM pp;

-- R09 | Transición tras estado D (cambio de ciclo): ¿qué viene en el siguiente sorlcur? (P05)
WITH s AS (
  SELECT cod_estado, cod_programa, cod_admision, periodo_admision,
         LEAD(cod_estado) OVER w AS sig_estado, LEAD(cod_programa) OVER w AS sig_programa,
         LEAD(cod_admision) OVER w AS sig_admision, LEAD(periodo_admision) OVER w AS sig_per_adm
  FROM banner.ban_estados_academicos
  WINDOW w AS (PARTITION BY rut ORDER BY sorlcur)
)
SELECT COALESCE(cod_admision,'[NULL]') AS admision_actual,
       CASE WHEN sig_estado IS NULL THEN 'sin_siguiente'
            WHEN sig_programa IS NOT DISTINCT FROM cod_programa THEN 'mismo_programa'
            ELSE 'otro_programa' END AS siguiente_programa,
       COALESCE(sig_admision,'[NULL]') AS admision_siguiente,
       COALESCE(sig_estado,'[NULL]') AS estado_siguiente,
       COUNT(*) AS casos
FROM s WHERE cod_estado = 'D'
GROUP BY 1,2,3,4 ORDER BY casos DESC LIMIT 40;

-- R10 | Inicio de un episodio CC (cambio de carrera): ¿cuál era el estado y admisión previos? (P05)
WITH s AS (
  SELECT cod_estado, cod_programa, cod_admision,
         LAG(cod_estado) OVER w AS ant_estado, LAG(cod_programa) OVER w AS ant_programa,
         LAG(cod_admision) OVER w AS ant_admision
  FROM banner.ban_estados_academicos
  WINDOW w AS (PARTITION BY rut ORDER BY sorlcur)
)
SELECT COALESCE(ant_estado,'[sin_anterior]') AS estado_anterior,
       COALESCE(ant_admision,'[sin_anterior]') AS admision_anterior,
       CASE WHEN ant_programa IS NULL THEN 'sin_anterior'
            WHEN ant_programa = cod_programa THEN 'mismo_programa' ELSE 'otro_programa' END AS programa_anterior,
       COUNT(*) AS casos
FROM s
WHERE cod_admision = 'CC' AND (ant_admision IS DISTINCT FROM 'CC' OR ant_programa IS DISTINCT FROM cod_programa)
GROUP BY 1,2,3 ORDER BY casos DESC LIMIT 30;

-- R11 | Cambios de programa en la secuencia: admisión del nuevo tramo y estado previo
WITH s AS (
  SELECT cod_estado, cod_programa, cod_admision,
         LAG(cod_estado) OVER w AS ant_estado, LAG(cod_programa) OVER w AS ant_programa
  FROM banner.ban_estados_academicos
  WINDOW w AS (PARTITION BY rut ORDER BY sorlcur)
)
SELECT COALESCE(cod_admision,'[NULL]') AS admision_nuevo_programa,
       COALESCE(ant_estado,'[NULL]') AS estado_previo,
       COUNT(*) AS cambios
FROM s WHERE ant_programa IS NOT NULL AND ant_programa IS DISTINCT FROM cod_programa
GROUP BY 1,2 ORDER BY cambios DESC LIMIT 30;

-- R12 | fecha_estado NULL: ¿hay vecinos con fecha para aproximar un intervalo? (P02)
WITH s AS (
  SELECT fecha_estado,
         MAX(fecha_estado) OVER (PARTITION BY rut ORDER BY sorlcur ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS f_antes,
         MIN(fecha_estado) OVER (PARTITION BY rut ORDER BY sorlcur ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING) AS f_despues
  FROM banner.ban_estados_academicos
)
SELECT COUNT(*) AS fechas_null,
       COUNT(*) FILTER (WHERE f_antes IS NOT NULL AND f_despues IS NOT NULL) AS con_ambos_vecinos,
       COUNT(*) FILTER (WHERE f_antes IS NOT NULL AND f_despues IS NULL) AS solo_anterior,
       COUNT(*) FILTER (WHERE f_antes IS NULL AND f_despues IS NOT NULL) AS solo_posterior,
       COUNT(*) FILTER (WHERE f_antes IS NULL AND f_despues IS NULL) AS sin_vecinos,
       COUNT(*) FILTER (WHERE f_antes > f_despues) AS intervalo_invertido
FROM s WHERE fecha_estado IS NULL;

-- R13 | Cobertura notas↔oferta por año, separando DPA (reemplaza C05; P13)
WITH notas AS (
  SELECT LEFT(periodo,4) AS anio, periodo, nrc,
         COUNT(*) AS filas, COUNT(*) FILTER (WHERE UPPER(BTRIM(nota))='DPA') AS dpa
  FROM banner.ban_historia_notas
  WHERE nrc IS NOT NULL AND BTRIM(nrc) <> ''
  GROUP BY 1,2,3
), oferta AS (
  SELECT DISTINCT periodo, nrc FROM banner.ban_oferta_academica WHERE nrc IS NOT NULL AND BTRIM(nrc) <> ''
)
SELECT n.anio, SUM(n.filas) AS notas, SUM(n.dpa) AS dpa,
       SUM(n.filas - n.dpa) FILTER (WHERE o.nrc IS NOT NULL) AS evaluadas_vinculadas,
       ROUND(100.0 * SUM(n.filas - n.dpa) FILTER (WHERE o.nrc IS NOT NULL) / NULLIF(SUM(n.filas - n.dpa),0), 1) AS pct_evaluadas_vinculadas
FROM notas n LEFT JOIN oferta o USING (periodo, nrc)
GROUP BY n.anio ORDER BY n.anio;

-- R14 | Mapeo de códigos de programa contra common.programa_d (P07)
WITH pd AS (SELECT cod_banner, valid_program FROM common.programa_d),
src AS (
  SELECT 'estados.cod_programa' AS fuente, cod_programa AS cod, COUNT(*) AS filas FROM banner.ban_estados_academicos GROUP BY 2
  UNION ALL SELECT 'historia.cod_carrera', cod_carrera, COUNT(*) FROM banner.ban_historia_notas GROUP BY 2
  UNION ALL SELECT 'admision.cod_carrera', cod_carrera, COUNT(*) FROM banner.banner_admision GROUP BY 2
  UNION ALL SELECT 'titulados.codigo_carrera', codigo_carrera, COUNT(*) FROM banner.banner_titulados GROUP BY 2
  UNION ALL SELECT 'matricula.cod_carrera', cod_carrera, COUNT(*) FROM banner.banner_matricula GROUP BY 2
  UNION ALL SELECT 'ban_malla.malla_program_code', malla_program_code, COUNT(*) FROM banner.ban_malla_programa GROUP BY 2
)
SELECT s.fuente, COUNT(*) AS codigos, COUNT(pd.cod_banner) AS codigos_en_programa_d,
       COUNT(*) FILTER (WHERE pd.valid_program) AS codigos_validos,
       SUM(s.filas) AS filas, SUM(s.filas) FILTER (WHERE pd.cod_banner IS NOT NULL) AS filas_mapeadas
FROM src s LEFT JOIN pd ON pd.cod_banner = s.cod
GROUP BY s.fuente ORDER BY s.fuente;

-- R15 | programa_d: validez y predecesores (P07)
SELECT COUNT(*) AS programas,
       COUNT(*) FILTER (WHERE valid_program) AS validos,
       COUNT(*) FILTER (WHERE valid_program IS NOT TRUE) AS no_validos,
       COUNT(programa_predecesor) AS con_predecesor,
       COUNT(*) FILTER (WHERE programa_predecesor IS NOT NULL AND programa_predecesor NOT IN (SELECT id FROM common.programa_d)) AS predecesor_inexistente,
       COUNT(DISTINCT id_nivel) AS niveles
FROM common.programa_d;

-- R16 | Notas en inscripciones con estado de convalidación (P08)
SELECT estado, COALESCE(aprobacion,'[NULL]') AS aprobacion,
       CASE WHEN nota IS NULL OR BTRIM(nota)='' THEN 'vacia'
            WHEN UPPER(BTRIM(nota))='DPA' THEN 'DPA'
            WHEN REPLACE(BTRIM(nota),',','.') ~ '^[0-9]+(\.[0-9]+)?$' AND REPLACE(BTRIM(nota),',','.')::numeric >= 4 THEN 'numerica>=4'
            WHEN REPLACE(BTRIM(nota),',','.') ~ '^[0-9]+(\.[0-9]+)?$' THEN 'numerica<4'
            ELSE 'texto:' || UPPER(BTRIM(nota)) END AS clase_nota,
       COUNT(*) AS registros
FROM banner.ban_inscripciones
WHERE estado LIKE 'CONV%'
GROUP BY 1,2,3 ORDER BY registros DESC LIMIT 40;

-- R17 | Comentarios frecuentes en historia de notas (solo valores con >= 100 filas) (P08)
SELECT COALESCE(NULLIF(BTRIM(comentario),''),'[vacio]') AS comentario,
       COUNT(*) AS filas, COUNT(*) FILTER (WHERE UPPER(BTRIM(nota))='DPA') AS dpa
FROM banner.ban_historia_notas
GROUP BY 1 HAVING COUNT(*) >= 100 ORDER BY filas DESC LIMIT 40;

-- R18 | Valores de oportunidad en historia (P27: examen)
SELECT COALESCE(oportunidad,'[NULL]') AS oportunidad, COUNT(*) AS filas,
       COUNT(*) FILTER (WHERE UPPER(BTRIM(nota))='DPA') AS dpa
FROM banner.ban_historia_notas GROUP BY 1 ORDER BY filas DESC LIMIT 30;

-- R19 | Prerrequisitos vs mallas (P15): presencia de ambos extremos en malla_programa y en ban_malla_programa
WITH e AS (
  SELECT DISTINCT cod_programa, catalogo, codigo_asignatura AS asig, codigo_asignatura_repreq AS req
  FROM banner.malla_programa_prereq
), m AS (SELECT DISTINCT cod_programa, catalogo, codigo_asignatura AS asig FROM banner.malla_programa),
mp AS (SELECT DISTINCT cod_programa, codigo_asignatura AS asig FROM banner.malla_programa),
ma AS (SELECT DISTINCT codigo_asignatura AS asig FROM banner.malla_programa),
bm AS (SELECT DISTINCT pd.id AS cod_programa, b.malla_ctlg AS catalogo, b.malla_materiacurso AS asig
       FROM banner.ban_malla_programa b JOIN common.programa_d pd ON pd.cod_banner = b.malla_program_code)
SELECT COUNT(*) AS aristas,
       COUNT(*) FILTER (WHERE m1.asig IS NOT NULL) AS asig_en_misma_malla,
       COUNT(*) FILTER (WHERE m2.asig IS NOT NULL) AS req_en_misma_malla,
       COUNT(*) FILTER (WHERE m2.asig IS NULL AND p2.asig IS NOT NULL) AS req_en_otro_catalogo_mismo_programa,
       COUNT(*) FILTER (WHERE p2.asig IS NULL AND a2.asig IS NOT NULL) AS req_en_otro_programa,
       COUNT(*) FILTER (WHERE a2.asig IS NULL) AS req_en_ninguna_malla,
       COUNT(*) FILTER (WHERE b1.asig IS NOT NULL) AS asig_en_ban_malla_mismo_cat,
       COUNT(*) FILTER (WHERE b2.asig IS NOT NULL) AS req_en_ban_malla_mismo_cat
FROM e
LEFT JOIN m m1 ON m1.cod_programa=e.cod_programa AND m1.catalogo=e.catalogo AND m1.asig=e.asig
LEFT JOIN m m2 ON m2.cod_programa=e.cod_programa AND m2.catalogo=e.catalogo AND m2.asig=e.req
LEFT JOIN mp p2 ON p2.cod_programa=e.cod_programa AND p2.asig=e.req
LEFT JOIN ma a2 ON a2.asig=e.req
LEFT JOIN bm b1 ON b1.cod_programa=e.cod_programa AND b1.catalogo=e.catalogo AND b1.asig=e.asig
LEFT JOIN bm b2 ON b2.cod_programa=e.cod_programa AND b2.catalogo=e.catalogo AND b2.asig=e.req;

-- R20 | Formato de códigos de asignatura por fuente (patrón, no valores) (P15)
SELECT fuente, REGEXP_REPLACE(REGEXP_REPLACE(cod, '[A-Za-z]', 'A', 'g'), '[0-9]', '9', 'g') AS patron, COUNT(*) AS filas
FROM (
  SELECT 'malla_programa' AS fuente, codigo_asignatura AS cod FROM banner.malla_programa
  UNION ALL SELECT 'prereq.asig', codigo_asignatura FROM banner.malla_programa_prereq
  UNION ALL SELECT 'prereq.req', codigo_asignatura_repreq FROM banner.malla_programa_prereq
  UNION ALL SELECT 'ban_malla', malla_materiacurso FROM banner.ban_malla_programa
  UNION ALL SELECT 'historia', materia || curso FROM banner.ban_historia_notas
) x GROUP BY 1,2 HAVING COUNT(*) >= 50 ORDER BY 1, filas DESC;

-- R21 | ban_malla_programa: catálogos, semestres y formación (P16/P17)
SELECT COUNT(*) AS filas, COUNT(DISTINCT malla_program_code) AS programas,
       COUNT(DISTINCT (malla_program_code, malla_ctlg)) AS programa_catalogo,
       COUNT(*) FILTER (WHERE malla_ctlg = '000000') AS filas_catalogo_000000,
       COUNT(*) FILTER (WHERE malla_semestre IS NULL OR BTRIM(malla_semestre)='') AS sin_semestre,
       COUNT(DISTINCT malla_formacion) AS tipos_formacion,
       COUNT(DISTINCT (malla_program_code, malla_ctlg, malla_materiacurso)) AS asignaturas_distintas
FROM banner.ban_malla_programa;

-- R22 | ban_malla_programa: distribución de malla_formacion
SELECT COALESCE(malla_formacion,'[NULL]') AS malla_formacion, COUNT(*) AS filas
FROM banner.ban_malla_programa GROUP BY 1 ORDER BY filas DESC LIMIT 30;

-- R23 | Admisión: qué varía dentro de (year_admision, rut, cod_carrera) repetidos (P21)
WITH g AS (
  SELECT year_admision, rut, cod_carrera, COUNT(*) AS n,
         COUNT(DISTINCT pref_demre) AS v_pref_demre, COUNT(DISTINCT preferencia) AS v_preferencia,
         COUNT(DISTINCT cod_admision) AS v_cod_admision, COUNT(DISTINCT matricula) AS v_matricula,
         COUNT(DISTINCT id_sede) AS v_sede, COUNT(DISTINCT cod_demre) AS v_cod_demre,
         COUNT(DISTINCT ponderado) AS v_ponderado
  FROM banner.banner_admision GROUP BY 1,2,3 HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS grupos_repetidos,
       COUNT(*) FILTER (WHERE v_pref_demre > 1) AS varia_pref_demre,
       COUNT(*) FILTER (WHERE v_preferencia > 1) AS varia_preferencia,
       COUNT(*) FILTER (WHERE v_cod_admision > 1) AS varia_cod_admision,
       COUNT(*) FILTER (WHERE v_matricula > 1) AS varia_matricula,
       COUNT(*) FILTER (WHERE v_sede > 1) AS varia_sede,
       COUNT(*) FILTER (WHERE v_cod_demre > 1) AS varia_cod_demre,
       COUNT(*) FILTER (WHERE v_ponderado > 1) AS varia_ponderado,
       COUNT(*) FILTER (WHERE v_pref_demre=1 AND v_preferencia=1 AND v_cod_admision=1 AND v_matricula=1
                        AND v_sede=1 AND v_cod_demre=1 AND v_ponderado<=1) AS identicos_en_estos_campos
FROM g;

-- R24 | Admisión: postulaciones por persona y período (P21) y formato de year_admision
WITH p AS (SELECT year_admision, rut, COUNT(DISTINCT cod_carrera) AS carreras FROM banner.banner_admision GROUP BY 1,2)
SELECT CASE WHEN carreras >= 5 THEN '5+' ELSE carreras::text END AS carreras_postuladas, COUNT(*) AS personas_periodo
FROM p GROUP BY 1 ORDER BY 1;

-- R25 | Admisión: sufijo de year_admision y N/Y
SELECT CASE WHEN year_admision ~ '^[0-9]{6}$' THEN 'YYYY' || RIGHT(year_admision,2)
            WHEN year_admision ~ '^[0-9]{4}$' THEN 'YYYY' ELSE 'otro' END AS formato,
       COALESCE(matricula,'[NULL]') AS matricula, COUNT(*) AS filas
FROM banner.banner_admision GROUP BY 1,2 ORDER BY 1,2;

-- R26 | Sufijos de período por fuente (P23)
SELECT fuente, RIGHT(periodo,2) AS sufijo, COUNT(*) AS filas, MIN(periodo) AS desde, MAX(periodo) AS hasta
FROM (
  SELECT 'estados' AS fuente, periodo FROM banner.ban_estados_academicos
  UNION ALL SELECT 'historia', periodo FROM banner.ban_historia_notas
  UNION ALL SELECT 'inscripciones', periodo FROM banner.ban_inscripciones
  UNION ALL SELECT 'oferta', periodo FROM banner.ban_oferta_academica
) x GROUP BY 1,2 ORDER BY 1, filas DESC;

-- R27 | ban_inscripciones por período y estado (P10/P11/P12)
SELECT periodo, COUNT(*) AS filas,
       COUNT(*) FILTER (WHERE estado='INSCRITO' AND aprobacion IS NULL) AS inscrito_sin_resultado,
       COUNT(*) FILTER (WHERE estado LIKE 'RENUNCIADA%') AS renuncias,
       COUNT(*) FILTER (WHERE estado LIKE 'CONV%') AS convalidaciones
FROM banner.ban_inscripciones GROUP BY 1 ORDER BY 1;

-- R28 | Titulados: registros por persona y conciliación con estado U (P29)
WITH t AS (SELECT rut, COUNT(*) AS n, COUNT(DISTINCT codigo_carrera) AS carreras FROM banner.banner_titulados GROUP BY rut),
u AS (SELECT DISTINCT rut FROM banner.ban_estados_academicos WHERE cod_estado = 'U')
SELECT (SELECT COUNT(*) FROM t) AS personas_tituladas,
       (SELECT COUNT(*) FROM t WHERE n > 1) AS con_mas_de_un_registro,
       (SELECT COUNT(*) FROM t WHERE carreras > 1) AS con_mas_de_una_carrera,
       (SELECT COUNT(*) FROM t JOIN u USING (rut)) AS tituladas_con_estado_u,
       (SELECT COUNT(*) FROM u) AS personas_con_estado_u,
       (SELECT COUNT(*) FROM u WHERE rut NOT IN (SELECT rut FROM t)) AS estado_u_sin_titulados;

-- R29 | Cargas: metadatos de vigencia (P18)
SELECT 'estados' AS tabla, timestamp_carga, filas, ruts, periodo_min, periodo_max, medido_en, vigente, motivo
FROM banner.ban_estados_academicos_cargas
WHERE timestamp_carga >= (SELECT MAX(timestamp_carga) FROM banner.ban_estados_academicos_cargas) - 2592000000
UNION ALL
SELECT 'notas', timestamp_carga, filas, ruts, periodo_min, periodo_max, medido_en, vigente, motivo
FROM banner.ban_historia_notas_cargas
WHERE timestamp_carga >= (SELECT MAX(timestamp_carga) FROM banner.ban_historia_notas_cargas) - 2592000000
ORDER BY 1, 2 DESC;

-- R30 | Notas: personas con notas sin estados y viceversa (P25)
WITH n AS (SELECT DISTINCT rut FROM banner.ban_historia_notas),
e AS (SELECT DISTINCT rut FROM banner.ban_estados_academicos)
SELECT (SELECT COUNT(*) FROM n) AS personas_notas, (SELECT COUNT(*) FROM e) AS personas_estados,
       (SELECT COUNT(*) FROM n JOIN e USING (rut)) AS en_ambas,
       (SELECT COUNT(*) FROM n WHERE rut NOT IN (SELECT rut FROM e)) AS solo_notas,
       (SELECT COUNT(*) FROM e WHERE rut NOT IN (SELECT rut FROM n)) AS solo_estados;
