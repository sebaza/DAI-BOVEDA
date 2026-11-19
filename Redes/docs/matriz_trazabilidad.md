# DAI Neural — Matriz de trazabilidad

**Versión:** 0.2 · 11-11-2026 (incorpora ronda 3 `r3#R01`–`R30` y respuestas DAI `resp#Pxx`). Fuente → campo → transformación **prevista** → entidad silver → uso → estado de verificación → evidencia.
Las transformaciones son diseño propuesto, no implementado. Esquema `banner` salvo que se indique. Tipos de columna: `q1_q16#Q01` (`Q01`) o `v1_v14#V01`.
**Estados:** *Confirmado DAI* (regla cerrada) · *Verificado* (evidencia) · *Parcial* · *No verificado*.
**Evidencia:** `c01_c10`, `q1_q16`, `v1_v14`, `r3` = `resultados_*.txt`; `resp#Pxx` = `respuestas_dai_2026-11-11.md`; `INV` = `inventario_q1.txt`. Las transformaciones detalladas están en `03_reglas_academicas.md` (RA##).
**Seudonimización:** todo `rut` pasa a `persona_key` con HMAC (secreto fuera del repo); ningún RUT, nombre ni nota individual sale a documentos, logs ni demos.

## Admisión — `banner_admision`

| Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|
| `rut` (text) | HMAC → `persona_key` | `persona_key` | Ficha postulante/estudiante | Parcial: tipo verificado, sin pruebas de formato | `q1_q16#Q01` |
| `year_admision` (text) | Parsear período `YYYYPP`; no tratar como año | `postulacion.periodo_proceso`; `calendario_periodo` | Cohortes; ficha postulante | Verificado: 6 dígitos (`10`, `20`, 202601) | `q1_q16#Q10`, `v1_v14#V03` |
| `cod_carrera` (text) | Mapear vía `programa_d.cod_banner` | `programa_catalogo` | Cohortes; ficha | Verificado: 86/86 códigos en `programa_d` (111.733 filas) | `r3#R14` |
| `cod_admision`, `desc_admision` | Normalizar con diccionario de admisión | `postulacion.via_admision` | Ficha; cohortes | Verificado: diccionario `ban_tipo_admision` (52 códigos + NULL) | `r3#R02`, `r3#R03` |
| `matricula` (N/Y) | Conservar marca sin interpretar | `postulacion.marca_matricula` | Ficha postulante | Verificado el dominio (N 94.008, Y 17.725). DAI: N = no se matriculó, Y = se matriculó (P20) | `q1_q16#Q11`, `r3#R25`, `resp#P20` |
| `fecha_matricula` (text) | Parsing explícito a fecha; NULL si inválida | `postulacion.fecha_matricula` | Ficha | No verificado | `q1_q16#Q01` |
| `puntaje_leng`, `puntaje_mat`, `puntaje_ciencias`, `puntaje_historia`, `puntaje_nem`, `puntaje_ranking`, `notas_em` (text) | Parsing numérico validado; nullable | `postulacion.puntajes` | Contexto del postulante | Parcial: NEM y mat. informados en casi todas las filas con datos | `q1_q16#Q10` |
| `ponderado`, `ponderado_normalizado` (text) | Parsing validado; marcar cobertura | `postulacion.ponderado` | Contexto; comparación | Parcial: `ponderado` informado desde ~2017 (P22); normalizado sin medir | `q1_q16#Q10` |
| `pref_demre`, `preferencia` | Conservar | `postulacion.preferencia` | Ficha | No verificado | `v1_v14#V04` (granularidad repetida) |
| (`year_admision`, `rut`, `cod_carrera`) | Clave natural candidata, no única | `postulacion` | Unicidad | Verificado: 4.209 de 107.036 repetidas, máx. 4; 4.202 varían `cod_admision` (RA30; P39) | `v1_v14#V04`, `r3#R23` |
| `cod_colegio`, `tipo_colegio`, `depend_colegio` | Solo contexto descriptivo; no filtro de exclusión | `postulacion.contexto_origen` | Ficha postulante | No verificado | `INV` |

## Estados — `ban_estados_academicos`

| Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|
| `rut` (text) | HMAC → `persona_key` | `persona_key`, `evento_estado` | Ficha; línea de tiempo | Verificado: sin NULL (derivado de pares = filas) | `c01_c10#C01`, `v1_v14#V02` |
| `sorlcur` (numeric) | Ordenar por `(rut, sorlcur)`; nunca reiniciar por programa; no es clave de episodio | `evento_estado.secuencia_rut` | Línea de tiempo | Confirmado DAI; unicidad verificada (0 repetidos); entero, 1–633, con saltos (no es contador, RA02) | `c01_c10#C01`, `r3#R06` |
| `fecha_estado` (timestamp) | Conservar con NULL; no imputar ni reordenar por fecha | `evento_estado.fecha_estado` | Línea de tiempo; cortes | Parcial: 159.885 NULL (110.733 imputables por intervalo); 44.990 descensos aun con orden (`periodo`, `sorlcur`); 21 futuras (RA03, RA04; P01–P03, P44) | `c01_c10#C08`, `r3#R05`, `r3#R12`, `resp#P01`–`#P03` |
| `periodo` (text) | Parsear período; separar de fechas | `evento_estado.periodo` | Línea de tiempo | Verificado: 0 vacíos | `v1_v14#V02`, `q1_q16#Q04` |
| `cod_estado` (text) | Diccionario de estados versionado | `evento_estado.cod_estado` | Línea de tiempo; clasificación | Verificado: 33 códigos con nombre (significado = nombre, DAI P04); 5.211 NULL; reversas `1`/`2`/`5` pendientes (P35) | `r3#R01`, `resp#P04` |
| `nombre_estado` | Etiqueta de diccionario | `evento_estado` (referencia) | Presentación | Verificado | `q1_q16#Q02` |
| `cod_causal`, `causal` | Conservar; solo `E` informa causal | `evento_estado.causal` | Línea de tiempo (eliminación) | Verificado en agregado | `q1_q16#Q03` |
| `cod_programa` (text) | Mapear a `programa_d.cod_banner`; no reiniciar secuencia | `episodio_programa.programa` | Ficha; cambios de programa | Verificado: 90/90 códigos en `programa_d` (735.932 filas) | `r3#R14`, `c01_c10#C10` |
| `catalogo` (text), `plan_estudios` (numeric) | Versión de malla del episodio | `episodio_programa.catalogo` | Malla vigente | No verificado | `q1_q16#Q01` |
| `cod_admision`, `admision`, `periodo_admision` | Atributo de ingreso del episodio; no es evento | `episodio_programa.via_ingreso`, `periodo_ingreso` | Cambio de ciclo vs carrera | Verificado: `D` no cambia de programa ni de `cod_admision` (R09); constancia general sin medir | `r3#R03`, `r3#R09`, `resp#P05` |
| Regla de episodio | Derivar del estado y cruces con `cod_admision`, `cod_programa`, `catalogo` | `episodio_programa` | Ficha longitudinal | **Propuesta:** (`rut`, `cod_programa`, `cod_admision`, `periodo_admision`): 57.561 episodios; 1.660 no contiguos; 6.530 multi-catálogo (RA09; P38) | `r3#R07`, `r3#R08`, `resp#P06` |

## Notas — `ban_historia_notas`

| Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|
| (`periodo`, `rut`, `cod_carrera`, `catalogo`, `materia`, `curso`, `oportunidad`, `nrc`) | Clave natural del intento (acceso controlado) | `intento_asignatura` | Intentos; unicidad | Verificado: 0 repetidos sobre 2.670.731 | `v1_v14#V08` |
| `nota` (text) | Parsing explícito: numérica válida o `DPA`; sin fallo silencioso | `intento_asignatura.nota_numerica`, `resultado_tipo` | Intentos; promedios | Verificado: 129.258 no numéricas, todas `DPA`; 0 vacías | `v1_v14#V05`, `v1_v14#V06` |
| `nota` numérica `>= 4,0` | `aprobado_curricular = true`, `es_intento_evaluado = true`; 3,9 reprueba | `intento_asignatura` | Tasa de aprobación | Confirmado DAI; 196.982 con 4,0 | `v1_v14#V05` |
| `nota = 'DPA'` | `resultado_tipo='convalidacion'`, `nota_numerica` NULL, `aprobado_curricular = true`, `es_intento_evaluado = false` | `intento_asignatura` / hecho de reconocimiento | Avance curricular; excluido de promedio y tasa docente | Confirmado DAI; 129.258 filas | `v1_v14#V06` |
| `oportunidad` (text) | Parsear a entero; conciliar con `ban_inscripciones.oportunidad` (numeric) | `intento_asignatura.oportunidad` | Intentos | Parcial: sin vacíos; valores 0–10 (0: 19.531, significado pendiente, P40); tipos distintos entre fuentes | `v1_v14#V05`, `q1_q16#Q01`, `r3#R18` |
| `nrc` (text) | Enlazar con sección (periodo, nrc) | `seccion` | Tasa por docente | Verificado: cobertura de oferta por año 69,7 %–96,9 % (2016–2026); sin oferta antes de 2016 | `r3#R13` |
| `materia`, `curso`, `titulo` | Código y nombre de asignatura; clasificar hitos con catálogo | `asignatura_conceptual`, `hito_formativo_clasificado` | Prácticas, memoria, CAPSTONE | Parcial: búsqueda exploratoria con falsos positivos (P26) | `v1_v14#V12` |
| `creditos` (numeric) | Créditos reconocidos según plan/catálogo, evitando doble conteo | `intento_asignatura.creditos_reconocidos` | Avance curricular | Regla DAI: aprobado = reconocido (P28); doble conteo sin medir | `q1_q16#Q01`, `resp#P28` |
| `cod_carrera`, `catalogo`, `plan_estudio` | Programa y versión de malla del intento | `programa_catalogo` | Ficha; malla | Verificado: 85/85 códigos en `programa_d` (2.670.731 filas) | `r3#R14` |
| `comentario`, `cod_depto`, `nom_depto` | Conservar | `intento_asignatura` | Auditoría | Parcial: 14 valores de `comentario` con ≥ 100 filas; significados pendientes (P36) | `r3#R17` |

## Inscripciones — `ban_inscripciones`

| Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|
| `estado` | Clasificar `INSCRITO`, `CONV/*`, `RENUNCIADA *` en `resultado_tipo` | `inscripcion_asignatura` | Convalidaciones; renuncias | Parcial: 6 valores de `estado`; CONV/* con nota numérica en 17.116 filas (derivado: 15.367 + 1.713 + 36), propuesta RA15 (P37) | `c01_c10#C04`, `r3#R16` |
| `aprobacion` | Fuente de contraste con la regla de nota; NULL = sin resultado | `inscripcion_asignatura.aprobado_fuente` | Reconciliación | Verificado: NULL + `INSCRITO` = en curso (73.499 en 202610); 1.713 REPROBADA + CONV/INY explicadas por vigencia (DAI P09, P10) | `r3#R27`, `r3#R16`, `resp#P09`, `resp#P10` |
| `nota` (text) | Mismo parsing que historia | `inscripcion_asignatura` | Reconciliación | Parcial: 183 `DPA`; 1.120 con 4,0 en CONV/INY APROBADA | `c01_c10#C04`, `c01_c10#C09` |
| `oportunidad` (numeric), `periodo`, `nrc`, `nivel`, `catalogo_malla`, `materia_curso_catalogo`, `materia_curso_inscrito` | Normalizar; conservar catálogo y curso inscrito | `inscripcion_asignatura` | Intentos; equivalencias | Parcial: períodos 202510–202610; clave de reconciliación con historia sin medir | `q1_q16#Q01`, `r3#R26`, `r3#R27` |

## Oferta y docentes — `ban_oferta_academica`

| Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|
| (`periodo`, `nrc`) | Deduplicar a sección; no join plano con notas | `seccion` | Tasa por docente | Verificado: 65.074 secciones, 47.252 con varias filas; oferta 201610–202650 | `q1_q16#Q15`, `r3#R26` |
| `rut_profesor` | HMAC; tabla puente | `seccion_docente` (muchos-a-muchos) | Tasa por docente | Verificado: 9.341 secciones con varios docentes | `q1_q16#Q15`, `v1_v14#V09` |
| `tipo_profesor` | Rol del docente en la sección | `seccion_docente.rol` | Atribución | No verificado (P14) | `q1_q16#Q01` |
| `fechainicio`, `fechafin` (text) | Parsing a fecha | `seccion` | Calendario | No verificado | `q1_q16#Q01` |

## Mallas y programas

| Fuente | Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|---|
| `malla_programa` | `cod_programa` (bigint) | Unir con `programa_d.id` | `programa_catalogo`, `asignatura_malla` | Malla | Verificado: 8.091 filas, 0 sin mapeo; malla incompleta (R19) | `c01_c10#C07`, `r3#R19` |
| `malla_programa` | `catalogo`, `codigo_asignatura`, `nombre_asignatura`, `creditos`, `nivel` | Versión de malla por (programa, catálogo) | `asignatura_malla` | Malla; avance | Parcial: 173 combinaciones; catálogo `000000` = histórico o antecesor (DAI P16) | `c01_c10#C07`, `q1_q16#Q07`, `resp#P16` |
| `malla_programa_prereq` | (`cod_programa`, `catalogo`, `codigo_asignatura`, `codigo_asignatura_repreq`) | Deduplicar aristas; conservar nodos ausentes con marca | `prerrequisito` | Prerrequisitos | Verificado: 31.996 aristas; requisito en misma malla 12.255, otro catálogo 986, otro programa 17.448, ninguna 1.307; dirección sin confirmar (P46) | `v1_v14#V11`, `r3#R19`, `resp#P15` |
| `ban_malla_programa` | `malla_program_code`, `malla_ctlg`, `malla_materiacurso`, `malla_semestre`, `malla_creditaje` (text) | Posible fuente alternativa | `asignatura_malla` | Malla | **Malla oficial** (DAI P17): 40.077 filas, 152 programas, 284 programa-catálogo; 149/152 códigos en `programa_d` | `r3#R21`, `r3#R14`, `resp#P17` |
| `common.programa_d` | `id`, `cod_banner` | Tabla de equivalencia de programas | `programa_catalogo` | Todos | Verificado: biyectivo, 185 filas; `cod_banner` cubre estados, historia, admisión, matrícula y titulados | `c01_c10#C06`, `r3#R14` |
| `common.programa_d` | `programa_predecesor`, `valid_program` | Linaje de programas | `programa_catalogo` | Cohortes | Verificado: 170 válidos, 15 con predecesor, 1 predecesor inexistente (RA10) | `r3#R15`, `resp#P07` |
| `banner_catalogos`, `banner_programas` | `cod_carrera`, `catalogo`, `duracion`, `tipo_programa`, `codigo_sies`, `sede`, `facultad` | Atributos de programa/catálogo | `programa_catalogo` | Cohortes; ficha | No verificado | `q1_q16#Q01` |

## Matrícula, titulación, postgrado y encuesta

| Fuente | Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|---|
| `banner_matricula` | `year`, `cod_carrera`, `catalogo`, `rut`, `year_admision`, `periodo_admision`, `fecha_estado` | Matrícula por programa; sin sustituir estados | `episodio_programa` (matrícula) | Matrícula efectiva | No verificado | `q1_q16#Q01` |
| `banner_titulados` | `rut`, `codigo_carrera`, `catalogo`, `fecha_titulacion` (date), `year_ingreso`, `semestre_ingreso`, `duracion`, `semestres_suspendidos` | Titulación observada | `titulacion` | Tiempo a titulación; cohortes | Verificado: 19.712 registros, 19.589 personas; 122 con más de un registro (doble titulación); 825 `U` sin registro (P42) | `q1_q16#Q12`, `r3#R28`, `resp#P29` |
| `banner_estudiantes_postgrado` | `rut`, `cod_programa`, `periodo`, `cod_estado`, `estado`, `estado_matricula` | Separar matrícula y estado | `matricula_postgrado` | Postgrado UCN (posterior al MVP) | Parcial: coexisten MATRICULADO y estados J/W/P/E/B | `q1_q16#Q13`, `v1_v14#V14` |
| `ban_encuesta` | `periodo`, `nrc`, `rut_profesor`, `cod_pregunta`, `cantidad` | Agregado; sin inferir respuesta individual | `instrumento_encuesta` | Contexto docente (posterior) | Parcial: 18 tipos de encuesta | `q1_q16#Q16` |
| `ban_parciales_notas` | `fecha_sub` (text), `nota_comp`, `nota_sub` | Fase posterior, tras auditar temporalidad | — | Posterior | No verificado | `q1_q16#Q01` |

## Procedencia y calendario

| Fuente | Campo | Transformación prevista | Entidad silver | Uso | Estado | Evidencia |
|---|---|---|---|---|---|---|
| `*_cargas` | `timestamp_carga`, `vigente`, `filas`, `ruts`, `periodo_min`, `periodo_max`, `medido_en` | Usar la carga con `vigente=true`; registrar como procedencia | `dato_procedencia` | Auditoría; reproducibilidad | Verificado: 1 vigente por fuente; vigencia automática (≥ 97 % de RUT); notas del 04-11-2026 no vigentes (P41) | `v1_v14#V13`, `r3#R29` |
| `*_cargas`, `*_full` | `timestamp_carga` | Convertir de epoch ms | `dato_procedencia.carga_ts` | Procedencia | Verificado en estados y notas (epoch ms, DAI P19); otras tablas sin medir | `q1_q16#Q14`, `r3#R29`, `resp#P19` |
| Varias | `periodo`/`year_admision` | Catálogo de períodos con sufijos observados `10`, `20`, `15`, `25`, `11`, `21`, `01`; postgrado `50`/`60` | `calendario_periodo` | Todos | Parcial: sufijos 10/20, 15/25, 11/21/01, 50/60 con significado DAI; `21` y fechas pendientes (P45) | `r3#R26`, `resp#P23` |
| `bench.min_*`, `bench.sies_*` | `mrun` y agregados | No unir a RUT UCN sin vínculo legal y técnico | — | Benchmark externo | No verificado | `INV` |

## Hallazgos de ronda 3 sin fila propia (v0.2)

| Fuente | Hallazgo | Estado | Evidencia |
|---|---|---|---|
| `banner_matricula` | `cod_carrera` 82/82 códigos en `programa_d` (204.396 filas) | Verificado | `r3#R14` |
| `banner_titulados` | `codigo_carrera` 65/65 códigos en `programa_d` (19.712 filas) | Verificado | `r3#R14` |
| `ban_malla_programa` | 3 de 152 códigos sin `programa_d` (21 de 40.077 filas) | Verificado | `r3#R14` |
| Estados ↔ notas | Personas en ambas 47.574; solo notas 18.551; solo estados 2.008 | Verificado (persona) | `r3#R30` |
| Historia ↔ mallas | Formato `AAAA99999` vs `AAAA-99999`: unir por `materia‖'-'‖curso` (RA28); cobertura sin medir | Parcial | `r3#R20` |
| Transformaciones previstas | Reglas RA01–RA34 y pruebas (a)–(af) | Propuesta | `03_reglas_academicas.md` |
