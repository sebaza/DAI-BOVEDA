# DAI Neural — Modelo de datos (Fase 2)

**Versión:** 0.3 · 13-11-2026 (etapa A de la reconstrucción consolidada: §10) · 0.2 · 11-11-2026 · Resuelve M1–M4 y queda implementado en `sql/core/001`–`004` (aplicadas en localhost). Cambios respecto de v0.1: ver §8.
**Base:** reglas en `03_reglas_academicas.md`, joins en `02_mapa_joins.md`, auditoría en `04_auditoria_calidad.md`, respuestas DAI en `../evidencia/respuestas_dai_2026-11-11.md`.

## 1. Principios

1. **El Warehouse es la única fuente.** Se lee solo desde las vistas vigentes de `banner.*` y `common.*`, en sesión de solo lectura. Nunca se escribe en él.
2. **BD de desarrollo = PostgreSQL localhost** (autorizado, P33/P48). Todo vive en esquemas propios `neural_*`; no se tocan `boveda`, `percepcion` ni los demás esquemas internos.
3. **Seudonimización en la extracción.** El RUT (estudiante y docente) se reemplaza por `HMAC-SHA256(secreto, rut_normalizado)` *antes* de insertar. El RUT nunca llega a la BD de desarrollo. **Separación de dominios:** `persona_key = HMAC-SHA256(secreto, rut_normalizado)` y `docente_key = HMAC-SHA256(secreto, "docente:" + rut_normalizado)`, de modo que una clave de estudiante y una de docente nunca coinciden. `normalize_rut`: sin espacios, puntos ni guion, mayúsculas, sin ceros a la izquierda; vacío se rechaza (`NULL`). Implementado en `pipelines/common/pseudo.py`. **No se guarda tabla de correspondencia**: si hace falta reidentificar (caso privado autorizado), se recalcula desde el Warehouse con el mismo secreto.
4. **El secreto HMAC** se lee de la variable de entorno `DAI_NEURAL_HMAC_KEY`, definida por el usuario fuera del repositorio. La custodia definitiva queda en P34.
5. **Columnas mínimas.** No se extraen nombre, nacionalidad, correos, teléfonos, fecha de nacimiento, pasaporte, ciudad, comuna de residencia, ni colegio con nombre o código. Excepciones aprobadas (11-11-2026): `sexo` (solo para evaluación de equidad, nunca filtro ni variable de decisión; M1) y `region_colegio`, `comuna_colegio`, `cod_comuna` (contexto descriptivo; M2).
6. **Nada se borra ni se "corrige" en silencio.** Fechas imputadas, códigos imputados y correcciones del sistema se guardan como atributos con bandera; el valor original se conserva.
7. **Tiempo académico explícito.** Todo hecho tiene `periodo` (tiempo académico) y procedencia (`carga_id`). Los cortes point-in-time se hacen por `periodo`, no por timestamps de ETL.

## 2. Capas y esquemas (localhost)

| Esquema | Capa | Contenido | Escritura |
|---|---|---|---|
| `neural_meta` | control | Cargas de extracción, procedencia, diccionarios, versiones de clasificaciones, resultados de auditoría | Pipelines |
| `neural_stg` | bronze | Copia seudonimizada 1:1 de las columnas necesarias de cada vista vigente, sin transformar semántica | Extracción |
| `neural_core` | silver | Entidades normalizadas con reglas RA aplicadas | Normalización |
| `neural_mart` | gold | Fichas, línea de tiempo, comparables, snapshots de entrenamiento | Marts (después de Gate 2) |

Las migraciones siguen la convención de la Bóveda (`backend/sql/NNN_*.sql`): archivos SQL numerados e idempotentes en `Redes/sql/core/`.

## 3. Control y procedencia (`neural_meta`)

| Tabla | Clave | Columnas principales | Propósito |
|---|---|---|---|
| `carga_extraccion` | `carga_id` (serial) | `fuente` (vista), `timestamp_carga_wh` (de `*_cargas.vigente` o max), `filas_origen`, `filas_insertadas`, `sql_sha256`, `iniciado_en`, `terminado_en`, `estado` | Procedencia e idempotencia: una fuente + `timestamp_carga_wh` se carga una sola vez |
| `dic_estado` | `cod_estado` | `nombre_estado`, `clase_estado`, `es_terminal`, `es_correccion_sistema`, `fuente_regla` | R01 + RA (reversas 1/2/5 ignoradas, P35) |
| `dic_tipo_admision` | `cod_admision` | `admision`, `tipo_qualitas`, `tipo_cna`, `ingreso_ordinario`, `ingreso_total`, `prioridad_via` | R02 + P39 |
| `dic_comentario_nota` | `comentario_codigo` | `significado`, `es_convalidacion`, `confirmado` | R17; solo CONVA confirmado (P36) |
| `calendario_periodo` | `periodo` | `anio`, `sufijo`, `tipo_periodo` (`regular_1`, `regular_2`, `verano`, `invierno`, `excepcional`, `postgrado`, `otro`; desde la migración `019`, P45), `periodo_atipico`, `orden_regular` | P23/R26. Sembrada 1980–2035 con los sufijos 10, 20, 15, 25, 50, 60, 11, 21, 01; un sufijo desconocido se conserva como `otro` |
| `schema_migraciones` | `nombre` | `sha256`, `aplicado_en` | Migraciones aplicadas; un archivo editado después de aplicado se rechaza |
| `auditoria_resultado` | (`carga_id`, `chequeo`) | `valor_esperado`, `valor_obtenido`, `ok` | Reconciliación (Gate 2) |

`clase_estado` (**aprobada**, M4; sembrada en `neural_meta.dic_estado` con los 33 códigos de R01; una prueba verifica la paridad con `pipelines/normalize/states.py`): `matricula` (M, J, N, Ñ), `interrupcion` (P, Q, 4, A, S, #), `salida` (E, B, F, O, R, 3, 9, X, 6, H), `reingreso` (I, Y), `cambio_ciclo` (D), `egreso_titulacion` (G, Z, K, L, U), `correccion_sistema` (1, 2, 5), `otro` (T, 0, NULL).

## 4. Entidades silver (`neural_core`)

### 4.1 Identidad y catálogo académico

| Entidad | Clave técnica | Clave natural | Fuente | Notas |
|---|---|---|---|---|
| `persona` | `persona_key` (HMAC, text) | — | unión de fuentes | Sin atributos personales, salvo `sexo` (M1, solo equidad) con `sexo_conflicto` si las fuentes discrepan. `primer_periodo_*` por fuente |
| `programa` | `cod_programa` (= `cod_banner`) | `programa_d.id` | `common.programa_d` | `valid_program`, `programa_predecesor`, nivel, facultad (su nombre está en `facultad`, P76), sede. Mapeo verificado 100 % (R14) |
| `programa_catalogo` | (`cod_programa`, `catalogo`) | — | `ban_malla_programa` + `banner_catalogos` | `duracion`, vigencia por fechas de actividad |
| `asignatura_malla` | (`cod_programa`, `catalogo`, `codigo_asignatura`) | — | `ban_malla_programa` (oficial, P17) | `semestre`, `creditos`, `formacion`, `nombre`, `depto`. Código formato `AAAA-99999` |
| `prerrequisito` | (`cod_programa`, `catalogo`, `codigo_requisito`, `codigo_asignatura`) | — | `malla_programa_prereq` deduplicado | Arista requisito → asignatura (P46). Banderas `asig_en_malla`, `req_en_malla`, `req_en_otro_programa`; `filas_origen` para no perder repetidas |
| `hito_formativo` | (`cod_programa`, `catalogo`, `codigo_asignatura`) | — | `asignatura_malla.nombre` | `tipo_hito` (práctica, memoria, proyecto, seminario, capstone, titulación), `metodo` (`regex_nombre_v1`), `validado` (bool), `version` (P26) |

### 4.2 Admisión

| Entidad | Clave natural | Columnas | Regla |
|---|---|---|---|
| `postulacion_via` | (`year_admision`, `persona_key`, `cod_carrera`, `cod_admision`) — **sin restricción única**: la unicidad completa no está verificada (R23); clave técnica `postulacion_via_id` | `id_sede`, `pref_demre`, `preferencia`, `matricula` (Y/N), `fecha_matricula` (parseada), puntajes parseados (`numeric`, NULL si no parsea, con `puntaje_parse_ok`), `puntaje_nem`, `puntaje_ranking`, `notas_em`, `ponderado`, `tipo_colegio`, `depend_colegio`, `region_colegio`, `comuna_colegio`, `cod_comuna` (M2) | Todas las filas se conservan (R23) |
| `postulacion` | (`year_admision`, `persona_key`, `cod_carrera`) | `cod_admision_elegida`, `matricula_elegida`, `alguna_via_matriculo`, `n_vias` | Vía elegida por prioridad P39 (decisión del equipo, a validar con casos; ver `neural_meta.dic_tipo_admision.prioridad_via` y `pipelines/normalize/admission.py`): (1) `tipo_qualitas` = '2. Ingreso Especial o Directo' (p. ej. PC, BE, TU, PR); (2) regular de selección LS, RP, OV, OA; (3) listas de espera LE, EB, EC, EM, EP (estas cuatro son clase 2 en `r3#R02`, pero la DAI confirmó el 11-11-2026 que se tratan como lista de espera; migración `005`); (4) resto (clase 3, NN). Empate → `matricula='Y'`. Clases según `r3#R02` |

La normalización de puntajes entre PSU/PDT/PAES (P22/P47) se calcula en `neural_mart`, nunca en silver.

### 4.3 Trayectoria

| Entidad | Clave técnica | Clave natural | Columnas | Reglas |
|---|---|---|---|---|
| `episodio_programa` | `episodio_id` (bigserial) | (`persona_key`, `cod_programa`, `cod_admision`, `periodo_admision`) | `cod_admision_imputado`, `primer_periodo`, `ultimo_periodo`, `n_tramos`, `catalogo_inicial`, `catalogo_final`, `ultimo_estado_clase` | Decisión del equipo P38. 57.561 episodios esperados (R07) |
| `evento_estado` | (`persona_key`, `sorlcur`) | idem (único, C01) | `episodio_id`, `periodo`, `orden_canonico` (rank por `periodo, sorlcur`), `tramo_n`, `catalogo`, `plan_estudios`, `cod_estado`, `cod_causal`, `fecha_estado_original`, `fecha_min`, `fecha_max`, `fecha_aproximada`, `sin_intervalo`, `intervalo_invertido`, `fecha_marcador`, `es_correccion_sistema`, `carga_id` (la bandera de fecha futura se llama `fecha_marcador`, como en RA04; reemplaza a `fecha_placeholder`) | Orden (P43). Fecha NULL → intervalo de vecinos (P02/R12). Fecha futura → `fecha_marcador` (P03, RA04): conserva su valor pero no es vecino ni ancla de tiempo. Reversas → bandera, sin borrar (P35) |

### 4.4 Asignaturas

| Entidad | Clave natural | Columnas | Reglas |
|---|---|---|---|
| `intento_asignatura` | (`periodo`, `persona_key`, `cod_carrera`, `catalogo`, `materia`, `curso`, `oportunidad`, `nrc`) — única (V08) | `episodio_id` (nullable), `codigo_asignatura` (`materia-curso`), `titulo`, `nota_texto`, `nota_numerica`, `nota_es_heredada`, `resultado_tipo` (`evaluado`, `convalidacion`, `otro`), `aprobado_curricular`, `es_intento_evaluado`, `creditos`, `creditos_reconocidos`, `comentario_codigo`, `fuente_resultado`, `episodio_ambiguo`, `reemplazada_mismo_periodo` | Fuente principal = historia (P11). DPA o CONVA → convalidación (P36). Nota ≥ 4,0 aprueba. `reemplazada_mismo_periodo` = fila anterior de la misma (persona, período, asignatura) superada por la de mayor `oportunidad` (P54, RA35): sale de los intentos evaluados |
| `inscripcion_asignatura` | (`periodo`, `persona_key`, `nrc`, `materia_curso_inscrito`, `estado`); **M3 resuelto** | `titulo_inscrito`, `aprobacion`, `oportunidad`, resultado (`resultado_tipo`, `nota_numerica`, `nota_es_heredada`, `aprobado_curricular`, `es_intento_evaluado`), `es_renuncia`, `tipo_renuncia`, `renuncia_repetida`, `es_convalidacion`, `en_curso`, `estado_conflicto`, `n_equivalencias` | Solo 202510–202610 (R27). CONV/* APROBADA = aprobado; REPROBADA = no reconocido (P37). NULL = en curso (P10). Grano = una inscripción de un curso; cuando una inscripción tiene más de un `estado` (8 grupos, R31: 194.080 contra 194.072) se conservan todas las filas con `estado_conflicto = true`, sin elegir. `neural_stg.ban_inscripciones` conserva las 213.170 filas de origen |
| `inscripcion_equivalencia` | (`inscripcion_id`, `materia_curso_catalogo`, `catalogo_malla`, `oportunidad`) | `titulo_catalogo`, `nivel`, `filas_origen` | Hija de la anterior. Una inscripción corresponde a varios cursos equivalentes del catálogo (4.794 de 7.057 grupos repetidos varían `materia_curso_catalogo`, R32). Ambos códigos tienen formato `AAAA-99999` (R33). `oportunidad` varía dentro de algunas inscripciones (R31: 194.315 contra 194.080), por eso también vive en la hija y en la madre queda NULL con `oportunidad_conflicto` |
| `seccion` | (`periodo`, `nrc`) | `sede`, `paralelo`, `cod_asignatura`, `carrera` | Oferta desde 201610 (R13) |
| `seccion_docente` | (`periodo`, `nrc`, `docente_key`) | `tipo_profesor` | Puente muchos-a-muchos; `docente_key` = HMAC del `rut_profesor` |

**Asignación de intento a episodio (R36).** El intento se asigna por (`persona_key`, `cod_carrera` = `cod_programa`) con `periodo` entre `primer_periodo` y `ultimo_periodo` del episodio (reversas excluidas). Un candidato: se asigna (1.860.553 filas). Cero candidatos: `episodio_id` NULL, `episodio_ambiguo = false`, `sin_episodio = true` (801.181 filas). Dos o más: `episodio_id` NULL y `episodio_ambiguo = true` (8.997 filas). Nunca se elige entre candidatos. Implementado en `pipelines/normalize/assignment.py`.

**Cobertura de la malla (R35).** De 2.670.731 filas de historia, 2.065.392 están en la malla oficial con el mismo programa y catálogo, 55.227 en otro catálogo del mismo programa, 125.823 en otro programa y 424.289 en ninguna malla. Por eso `intento_asignatura` no tiene FK a `asignatura_malla`; el vínculo es una unión opcional que reporta cobertura.

### 4.5 Resultados

| Entidad | Clave natural | Columnas | Reglas |
|---|---|---|---|
| `titulacion` | (`persona_key`, `codigo_carrera`, `catalogo`, `fecha_titulacion`) | `episodio_id`, `year_ingreso`, `semestre_ingreso`, `duracion`, `semestres_suspendidos`, `tipo_admision` | Doble titulación permitida (P29). Sin registro en titulados pero con estado U → se marca en auditoría, sin inventar el registro (P42) |
| `matricula_postgrado` | (`persona_key`, `cod_programa`, `periodo`) | `cod_estado`, `estado`, `estado_matricula`, `periodo_admision` | Solo postgrado UCN. Diferido después del MVP |
| `estado_postgrado` | (`estado_postgrado_id`) | `persona_key`, `sorlcur`, `periodo`, `cod_programa`, `cod_estado`, `nombre_estado`, `fecha_estado`, `cod_admision`, `periodo_admision`, `catalogo` | Desde `banner.ban_estados_academicos_pos` (migración `019`, P77). Una fila por fila de la fuente; sin clave foránea a `persona` (la mayoría de las personas de postgrado no tiene trayectoria de pregrado) |
| `programa_postgrado` | `cod_programa` | `nombre_banner`, `nombre_estandar`, `nivel_derivado` (`magister`, `doctorado`, `diplomado`, `otro`, `sin_nombre`), `id_nivel_diccionario`, `primer_periodo`, `ultimo_periodo`, `filas` | Nivel derivado del nombre estándar (`pipelines/normalize/postgrado.py`); la mayoría de los diplomados no tiene nombre estándar (Banner lo está normalizando) |
| `facultad` | `facultad_id` (= `programa.facultad`) | `cod_unidad_organica`, `nombre_facultad`, `nombre_vigente`, `nivel_jerarquico`, `cod_sede` | `common.facultad_d` (migración `019`, paso propio `facultad` de `build_core`, P76, D78); se une a `programa` por `programa.facultad` |

## 5. Gold (`neural_mart`) — después de Gate 2

- **Ficha y línea de tiempo:** `v_ficha_estudiante` y `v_linea_tiempo`, sobre episodios, eventos, intentos e hitos, con denominadores explícitos.
- **Indicadores por persona y período:** `indicador_periodo`, con créditos aprobados, intentos evaluados, promedio de notas solo evaluadas y avance curricular (incluye convalidaciones).
- **Comparables:** `comparable_cohorte`, por carrera, catálogo, cohorte y semestre, con N y cobertura.
- **Snapshots de entrenamiento:** `snapshot_entrenamiento` con `periodo_corte`, que solo usa hechos con `periodo <= corte` y etiquetas con horizonte y censura explícitos.

## 6. Pipeline de Fase 2

1. `sql/core/001_esquemas.sql`: crea los esquemas `neural_*`.
2. `002_meta.sql`: crea las tablas de control y los diccionarios.
3. `003_stg.sql` y `004_core.sql`: crean las tablas, con PK y restricciones de unicidad que verifican las claves naturales.
4. `pipelines/extract/`: lee las vistas vigentes en sesión de solo lectura, en streaming. Aplica HMAC en Python y carga en `neural_stg` con `COPY`, registrando `carga_extraccion`.
5. `pipelines/normalize/`: aplica funciones puras de Python (parseo de nota, clasificación de resultado, orden, imputación de fechas, prioridad de vía) más SQL de construcción de `neural_core`.
6. **Pruebas:**
   - Pruebas unitarias con `pytest` para las funciones puras, que cubren los casos (a)–(h) de la especificación y los de `03_reglas_academicas.md`.
   - Tres historias sintéticas de control en `tests/fixtures`.
7. **Reconciliación (Gate 2):** conteos stg = Warehouse por fuente; core respecto de stg (sin pérdida ni multiplicación); valores esperados conocidos:
   - 735.932 estados;
   - 2.670.731 intentos;
   - 57.561 episodios;
   - 129.258 DPA.

## 7. Decisiones del modelo (M1–M4, resueltas el 11-11-2026)

| ID | Tema | Resolución |
|---|---|---|
| M1 | `sexo` para auditoría de equidad | Se extrae (`stg.ban_estados_academicos.sexo`, `stg.banner_admision.sexo`) y se guarda en `core.persona.sexo`. Solo evaluación de equidad (Fase 4); nunca filtro ni variable de decisión. Prioridad baja |
| M2 | `region_colegio`, `comuna_colegio`, `cod_comuna` | Se extraen como contexto descriptivo de la ficha postulante (`postulacion_via`). Vacíos en R37: 7.352 / 7.352 / 9.060 de 111.733 |
| M3 | Clave de `inscripcion_asignatura` | Sin clave natural limpia (R31–R33). `stg` conserva todas las filas; `core` tiene grano (`periodo`, `persona_key`, `nrc`, `materia_curso_inscrito`, `estado`) con la hija `inscripcion_equivalencia` y `estado_conflicto` (ver §4.4) |
| M4 | `clase_estado` de §3 | **Aprobada** |

## 8. Cambios de v0.1 a v0.2

- M1–M4 resueltas (§7); principio 5 y §4.1–4.4 actualizados.
- Separación de dominios en el HMAC (principio 3).
- Regla de asignación de intentos a episodios (R36) y cobertura de la malla (R35) en §4.4.
- R34: las reversas 1/2/5 nunca cambian programa ni admisión respecto del estado anterior, así que excluirlas no afecta la derivación de episodios.
- Convalidación `CONVA` con nota heredada menor que 4,0: `aprobado_curricular = false` (valor por defecto; el usuario puede revisarlo).
- `fecha_placeholder` pasa a llamarse `fecha_marcador` (RA04); `alguna_via_matriculo` en `postulacion`.
- Implementación: `Redes/pipelines/` (funciones puras y `migrate.py`) y `Redes/sql/core/001`–`004`. Las claves únicas sobre claves naturales usan `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15 o superior; local 16.3) para que un NULL en la clave no permita duplicados.
- `postulacion_via` no tiene restricción única: la unicidad de (`year_admision`, `rut`, `cod_carrera`, `cod_admision`) no está verificada (7 de 4.209 grupos repetidos conservan el mismo `cod_admision`, R23).

## 9. Cambios del Gate 2 (11-11-2026)

- `neural_stg.malla_programa` (migración `006`): `malla_programa` antigua, solo para auditar `r3#R19`.
- `neural_core.asignatura_malla` (migración `007`): `semestre_texto`, `filas_origen`, `atributos_conflicto`. Una fila por (programa, catálogo, asignatura); las filas repetidas de la malla oficial se resumen ahí.
- `neural_meta.auditoria_resultado` (migración `008`): `explicacion`.
- `persona` se construye como unión de estados, historia, inscripciones, titulados y postgrado; la admisión solo aporta `sexo`. Detalle y resultados: `06_reconciliacion_gate2.md`.

## 10. Cambios de la etapa A (13-11-2026)

Migraciones `019`–`021` (idempotentes):

- `019_etapa_a_core.sql`: `intento_asignatura.reemplazada_mismo_periodo` (P54); tipos de `calendario_periodo` `verano`, `invierno`, `excepcional` (P45) con la restricción renovada; `neural_stg.facultad_d` y `neural_core.facultad` (P76); `neural_stg.ban_estados_academicos_pos`, `neural_core.programa_postgrado` y `neural_core.estado_postgrado` (P77).
- `020_etapa_a_snapshots.sql`: columnas nuevas de los snapshots. Todos: `prueba_admision` y `mm_leng`, `mm_mat`, `mm_ciencias`, `mm_historia`, `mm_nem`, `mm_ranking`, `mm_notas_em`, `mm_ponderado` (P47; puntaje mín–máx por prueba y año, NULL si no hay rango). T2: `banda_nota` (P74). T4/T5: `eliminacion_con_reintegro`, `eliminacion_efectiva`, `horizonte_e_dudoso` (P72, P75). T6: `previo_estados`, `evento_estados`, `tiempo_estados`, `nivel_estados` (P77). Las etiquetas nuevas no entran a `FEATURE_COLS_*`.
- `021_etapa_a_marts.sql`: `neural_mart.programa_traslados_nota(clave, valor, nota)`, con una fila por relación que no es traslado (`continuacion_estudios`, `doble_programa`, `superposicion_con_baja`; P64, P69).

Las columnas `pct_*` previas de admisión (percentiles por rango) se conservan; `mm_*` se agregan al lado y se documentan en `03_reglas_academicas.md` RA31.
