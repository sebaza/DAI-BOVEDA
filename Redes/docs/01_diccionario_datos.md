# DAI Neural — Diccionario de datos (Fase 1, entregable 01)

**Versión:** 0.1 · 11-11-2026. Base: `evidencia/inventario_q1.txt` (INV), tipos `resultados_q1_q16.txt#Q01` y `resultados_v1_v14.txt#V01`, rondas Q/V/C/R y `respuestas_dai_2026-11-11.md` (resp).
**Alcance:** vistas vigentes del Warehouse (esquema `banner`, más `common.programa_d`). Estados e historia de notas filtran por `*_cargas.vigente`; las demás vistas usan `max(timestamp_carga)` (`sql/discovery/ronda3_fase1.sql`, cabecera; `resultados_r3.txt#R29`). Las tablas `*_full` no se documentan aquí.
**Reglas del documento:** "por confirmar" = sin evidencia de significado. **Columnas personales:** se listan solo para constatar que existen y están **excluidas** de DAI Neural (no se documentan sus valores ni significado). `rut` y `rut_*` se seudonimizan (HMAC → `persona_key`).

## 1. Columnas por fuente

### 1.1 `banner.ban_estados_academicos` (19 columnas)

| Columna | Tipo | Significado / uso | Evidencia |
|---|---|---|---|
| `rut` | text | Identificador de persona → `persona_key`. Sin NULL. | `c01_c10#C01` |
| `sorlcur` | numeric | Secuencia de estados por RUT; no se reinicia por programa; entero, sin NULL, 1–633; **no es contador denso** (48.804 de 49.582 personas con saltos). No es clave de episodio. | `r3#R06`, resp P01 |
| `periodo` | text | Período del estado, 6 dígitos (0 excepciones). Sufijos en §3. | `r3#R04`, `#R26` |
| `plan_estudios` | numeric | Plan de estudios: por confirmar. | `Q01` |
| `catalogo` | text | Versión de malla del programa; cambia con actualizaciones de malla (resp P07). 6.530 episodios con más de un catálogo. | `r3#R08` |
| `cod_admision`, `admision` | text | Vía de ingreso (código y nombre), §2.2. 12 filas con `cod_admision` NULL. | `r3#R03`, `#R07` |
| `periodo_admision` | text | Período de admisión; parte de la clave de episodio propuesta. | `r3#R07`, resp P06 |
| `cod_programa` | text | Programa; equivale a `programa_d.cod_banner` (90/90 códigos). | `r3#R14` |
| `nombre_banner`, `nombre_estandar` | text | Nombres del programa; diferencia entre ambos por confirmar. | `Q01` |
| `cod_estado`, `nombre_estado` | text | Estado y su nombre (§2.1). 5.211 filas sin ambos. | `r3#R01` |
| `fecha_estado` | timestamp | Fecha del estado. NULL en 159.885 (fecha no guardada o cambio interno, resp P02); 21 futuras (marcador, resp P03); no cronológica ni dentro de (`periodo`, `sorlcur`). | `r3#R05`, `#R12`, `c01_c10#C08` |
| `cod_causal`, `causal` | text | Causal; informada solo para `E` (5.703 `E` sin causal). | `Q03` |
| `nombre`, `sexo`, `nacionalidad` | text | **Personales — excluidas.** | INV |

### 1.2 `banner.ban_historia_notas` (16 columnas)

| Columna | Tipo | Significado / uso | Evidencia |
|---|---|---|---|
| `periodo` | text | Período del intento; 198020–202620. | `r3#R26` |
| `rut` | text | → `persona_key`. | INV |
| `cod_carrera`, `nom_carrera` | text | Programa (equivale a `cod_banner`, 85/85 códigos) y su nombre. | `r3#R14` |
| `catalogo`, `plan_estudio` | text, numeric | Versión de malla y plan del intento. | `Q01` |
| `materia`, `curso`, `titulo` | text | Código de asignatura = `materia`‖`curso` (patrón `AAAA99999`, sin guion) y nombre. | `r3#R20` |
| `nota` | text | Numérica o `DPA` (129.258, convalidación); 0 vacías. Formato decimal por verificar al parsear. | `v1_v14#V05`, `#V06` |
| `creditos` | numeric | Créditos de la asignatura; unidad (local o SCT) por confirmar. | `Q01` |
| `oportunidad` | text | Oportunidad del intento, valores 0–10; 1 = 2.351.185, 2 = 244.421, 0 = 19.531 (significado de 0 por confirmar, P40). | `r3#R18` |
| `nrc` | text | Sección (con `periodo`); 0 vacíos, incluso en DPA. | `v1_v14#V05` |
| `comentario` | text | Código de comentario; ver §4. | `r3#R17` |
| `cod_depto`, `nom_depto` | text | Departamento: por confirmar. | INV |

Clave natural de intento verificada: (`periodo`, `rut`, `cod_carrera`, `catalogo`, `materia`, `curso`, `oportunidad`, `nrc`), 0 repetidas (`v1_v14#V08`).

### 1.3 `banner.ban_inscripciones` (15 columnas)

| Columna | Tipo | Significado / uso | Evidencia |
|---|---|---|---|
| `rut` | text | → `persona_key`. | INV |
| `nivel`, `catalogo_malla` | text | Nivel y catálogo de malla: por confirmar. | `Q01` |
| `materia_curso_catalogo`, `titulo_catalogo`, `materia_curso_inscrito`, `titulo_inscrito` | text | Asignatura del catálogo y asignatura efectivamente inscrita; diferencia (equivalencias) por confirmar. | `Q01` |
| `nrc` | text | Sección. | INV |
| `nota` | text | Numérica o `DPA` (183 filas, todas CONV/INY APROBADA). | `c01_c10#C09` |
| `aprobacion` | text | APROBADA / REPROBADA / NULL; NULL con `INSCRITO` = en curso (resp P10). | `r3#R27` |
| `oportunidad` | numeric | Oportunidad (en historia es text). | `Q01` |
| `estado` | text | `INSCRITO`, `CONV/INY`, `CONV/INTERC`, `RENUNCIADA MANUAL`, `RENUNCIADA WF`, `RENUNCIADA WEB`. | `c01_c10#C04` |
| `periodo` | text | Solo 202510–202610. | `r3#R27` |
| `nombre`, `apellidos` | text | **Personales — excluidas.** | INV |

### 1.4 `banner.ban_oferta_academica` (28 columnas, todas text)

| Columnas | Significado / uso | Evidencia |
|---|---|---|
| `periodo`, `nrc`, `paralelo`, `carrera`, `nomcarrera`, `sede`, `departamento` | Sección = (`periodo`, `nrc`); 65.074 secciones; períodos 201610–202650. | `Q15`, `r3#R26` |
| `cod_asignatura`, `asignatura`, `tipo_clase`, `carga_horaria`, `cupo`, `utilizado`, `sala`, `hora_inicio`, `hora_fin`, `lunes`…`domingo`, `fechainicio`, `fechafin` | Atributos de la sección; significado fino por confirmar; fechas en texto. | `Q01` |
| `rut_profesor`, `tipo_profesor` | Docente (→ HMAC) y su rol (por confirmar, P14). 9.341 secciones con varios docentes. | `Q15` |
| `profesor` | **Personal — excluida.** | INV |

### 1.5 `banner.banner_admision` (49 columnas)

| Columna | Tipo | Significado / uso | Evidencia |
|---|---|---|---|
| `year_admision` | text | Período del proceso (6 dígitos: `YYYY10` 111.266 filas (derivado: N + Y), `YYYY20` 427, `YYYY01` 40), no solo año. | `r3#R25` |
| `cod_carrera`, `id_sede`, `cod_demre` | text, int, text | Programa (86/86 códigos en `programa_d`), sede, código DEMRE. | `r3#R14`, `#R23` |
| `pref_demre`, `preferencia` | text | Preferencias; `preferencia` varía en 262 de 4.209 grupos repetidos. | `r3#R23` |
| `cod_admision`, `desc_admision` | text | Vía de ingreso (§2.2). | INV |
| `matricula`, `fecha_matricula` | text | N = no se matriculó, Y = se matriculó (postulantes, resp P20). 111.733 filas: N 94.008, Y 17.725. | `Q11` |
| `cod_colegio`, `tipo_colegio`, `depend_colegio` | text | Contexto de origen; solo descriptivo. | spec |
| `puntaje_leng`, `puntaje_mat`, `puntaje_ciencias`, `puntaje_historia`, `puntaje_nem`, `puntaje_ranking`, `notas_em`, `promedio_lm`, `ponderado`, `ponderado_normalizado` | text | Puntajes textuales; parsing validado; `ponderado` informado desde ~2017 (`Q10`); prueba por proceso y normalización por confirmar (P47). | `Q10` |
| `colegio`, `region_colegio`, `provincia_colegio`, `comuna_colegio`, `comuna`, `cod_comuna`, `ciudad`, `cod_ciudad`, `year_egreso`, `lugar_lista` | text | Fuera de alcance de Fase 1. | INV |
| `pasaporte`, `nombre1`, `nombre2`, `ap_paterno`, `ap_materno`, `nombre_social`, `sexo`, `fecha_nacimiento`, `edad`, `nacionalidad`, `etnia`, `correo_ucn`, `correo_personal`, `telefono_fijo`, `telefono_celular` | text | **Personales — excluidas.** | INV |

### 1.6 Matrícula, titulación y postgrado

| Fuente | Columnas (tipo) | Significado / uso | Evidencia |
|---|---|---|---|
| `banner_matricula` (204.396 filas) | `year` int, `cod_carrera`, `nombre_carrera`, `catalogo`, `year_admision` int, `periodo_admision`, `rut`, `cod_admision`, `tipo_admision`, `fecha_estado` date, `sede`, `facultad` | Matrícula por programa y año; definición de matrícula efectiva por confirmar. `cod_carrera` 82/82 en `programa_d`. | `r3#R14`, `Q01` |
| `banner_titulados` (19.712 filas, 19.589 personas) | `rut`, `codigo_carrera`, `carrera`, `codigo_sies`, `catalogo`, `sede`, `year_ingreso` int, `semestre_ingreso` int, `duracion` int, `year_titulacion` int, `fecha_titulacion` date, `semestres_suspendidos` int, `semestres_suspendidos_old` int, `tipo_admision`, `id`, `timestamp_carga` bigint | Titulación observada; 122 personas con más de un registro (doble titulación, resp P29). `nombre1`, `nombre2`, `apellido_paterno`, `apellido_materno`, `sexo`: **personales — excluidas.** | `r3#R14`, `#R28` |
| `banner_estudiantes_postgrado` | `rut`, `cod_programa`, `periodo`, `cod_estado`, `estado`, `fecha_estado` date, `estado_matricula`, `periodo_admision`, `cod_admision`, `tipo_admision`, `catalogo`, `codigo_sies` | Solo postgrado UCN; matrícula y estado se tratan por separado; posterior al MVP. | `v1_v14#V14` |

### 1.7 Programas, mallas y catálogos

| Fuente | Columnas (tipo) | Significado / uso | Evidencia |
|---|---|---|---|
| `common.programa_d` (185 filas) | `id` bigint, `cod_banner` text, `programa_predecesor` bigint, `valid_program` boolean, `id_nivel` bigint (6 niveles), `nombre_programa`, `area_conocimiento`, `facultad` bigint, `sede` bigint, `cod_demre`, `unidad_analisis_ing_gast`, `seccion_analisis_ing_gast`, `cod_unidad_organica_seccion_analisis` (al menos 14 columnas inventariadas) | `id` ↔ `cod_banner` biyectivo; 170 válidos, 15 no válidos, 15 con predecesor. | `c01_c10#C06`, `r3#R15` |
| `malla_programa` (8.091 filas) | `cod_programa` bigint (= `programa_d.id`), `catalogo`, `codigo_asignatura`, `nombre_asignatura`, `creditos` int, `nivel` int | Malla antigua; incompleta; fuente oficial es `ban_malla_programa`. Código con guion (`AAAA-99999`). | `c01_c10#C07`, `r3#R19`, `#R20` |
| `malla_programa_prereq` (45.439 filas; 31.996 aristas) | `cod_programa`, `catalogo`, `codigo_asignatura`, `codigo_asignatura_repreq` | Aristas; dirección por confirmar (P46). 98 códigos con patrón `AAA9-99999`. | `v1_v14#V11`, `r3#R20` |
| `ban_malla_programa` (40.077 filas) | `malla_program_code` (= `cod_banner`), `malla_ctlg`, `malla_materiacurso`, `malla_semestre`, `malla_formacion`, `malla_creditaje`, `malla_asignatura`, `malla_area`, `malla_depto`, `malla_depto_desc`, `nombre_estandar`, fechas de actividad/sync | **Malla oficial** (resp P17); 152 programas, 284 programa-catálogo; semestre sin vacíos; `malla_formacion`: 704 valores, 6.976 NULL (P40). | `r3#R21`, `#R22` |
| `banner_catalogos`, `banner_programas` | `cod_carrera`, `catalogo`, `duracion` int; `tipo_programa`, `codigo_sies`, `area_conocimiento`, `sede`, `facultad` | Atributos de programa/catálogo; unidad de `duracion` por confirmar. | `Q01` |
| `ban_tipo_admision` | `cod_admision`, `admision`, `tipo_qualitas`, `tipo_cna`, `ingreso_ordinario`, `ingreso_total` | Diccionario de vías de ingreso (§2.2). | `r3#R02` |

### 1.8 Otras fuentes y cargas

| Fuente | Contenido | Estado |
|---|---|---|
| `ban_encuesta` | Respuestas agregadas por `periodo`, `nrc`, `rut_profesor`, pregunta; `cantidad` numeric. Fuente ENCE: Excel por cargar. | `Q16`, resp P31 |
| `ban_parciales_notas` | Componentes y subcomponentes (`nota_comp`, `nota_sub`, `fecha_sub` en texto). Incluye `nombre_prof`, `nombre_estud` (**personales — excluidas**) y `rut_prof`, `rut_estud`. Posterior a Fase 1. | `Q01` |
| `ban_estados_academicos_cargas`, `ban_historia_notas_cargas` | `timestamp_carga` (epoch ms), `filas`, `ruts`, `periodo_min`, `periodo_max`, `medido_en`, `vigente`, `motivo` (+ `fecha_carga` en notas). | `r3#R29`, resp P19 |

## 2. Diccionarios de códigos

### 2.1 Estados (`cod_estado`) — R01

33 códigos más `NULL` (`resultados_r3.txt#R01`, vista vigente de `ban_estados_academicos`). Significado = `nombre_estado` (DAI P04). "Spec" = el código ya figuraba en la especificación. Clasificación de negocio (terminal, retiro, etc.): por confirmar.

| Código | Nombre | Registros | Personas | Período mín–máx | Origen / nota |
|---|---|---|---|---|---|
| M | Matriculado | 352.611 | 47.777 | 200810–202620 | Spec + R01 |
| J | Matrícula en Trámite | 178.304 | 35.984 | 200810–202620 | Spec + R01 |
| E | Eliminado | 38.704 | 17.892 | 200810–202620 | Spec + R01 |
| G | Egresado | 24.710 | 19.741 | 200810–202620 | Spec + R01 |
| D | Cambio de Ciclo | 23.455 | 23.119 | 200810–202620 | Spec + R01 |
| U | Titulado | 23.255 | 18.959 | 200810–202620 | Spec + R01 |
| I | Reintegro | 19.653 | 10.881 | 200810–202620 | Spec + R01 |
| Z | Malla Completa | 19.489 | 19.283 | 200810–202620 | Spec + R01 |
| K | Expediente Titulo | 14.373 | 10.082 | 200820–202620 | Spec + R01 |
| B | Renuncia Alumno | 9.357 | 6.728 | 200810–202620 | Spec + R01 |
| A | Anulación de Semestre | 7.780 | 5.972 | 200810–202620 | R01 (nombre) |
| N | Nuevo | 5.622 | 5.517 | 201210–202510 | R01 (nombre) |
| NULL | — | 5.211 | 5.116 | 201510–202610 | Sin código ni nombre; sin fecha (C08) |
| P | Retiro Temporal | 4.836 | 4.066 | 200810–202620 | Spec + R01 |
| L | Licenciado | 2.452 | 1.672 | 200810–202620 | R01 (nombre) |
| O | No Continuidad | 2.449 | 2.369 | 200810–202620 | Spec + R01 |
| Y | Reintegro por Rectificación | 1.966 | 1.768 | 201420–202620 | R01 (nombre) |
| S | Intercambio Saliente Total | 602 | 542 | 201510–202620 | R01 (nombre) |
| F | Renuncia Admisión | 427 | 386 | 201010–202610 | R01 (nombre) |
| R | Retracto | 222 | 206 | 201210–202610 | R01 (nombre) |
| Q | Retiro Temporal Excepción | 164 | 151 | 200810–202310 | R01 (nombre) |
| 3 | No Matricula Admision | 92 | 92 | 202120–202610 | R01 (nombre) |
| H | Sancionado | 92 | 89 | 200810–202620 | R01 (nombre) |
| Ñ | Matricula Fuera Periodo | 33 | 32 | 201520–202120 | R01 (nombre) |
| 9 | Matricula Anulada | 13 | 9 | 201110–202510 | R01 (nombre) |
| 4 | Suspensión Temporal | 13 | 13 | 201910–202620 | R01 (nombre) |
| X | Expulsado | 11 | 10 | 202120–202620 | R01 (nombre) |
| # | Intercambio Saliente Parcial | 10 | 10 | 202420–202420 | R01 (nombre) |
| 2 | Reversa G, K, Reciclaje, CPlan | 8 | 8 | 201510–202610 | R01; reversa: regla pendiente (P35) |
| 6 | Sancionado Eliminado | 6 | 6 | 202210–202210 | R01 (nombre) |
| 1 | Reversa Cambio Ciclo Prof | 5 | 5 | 201520–201720 | R01; reversa: regla pendiente (P35) |
| 5 | Reversa Malla Completa | 4 | 4 | 201910–202310 | R01; reversa: regla pendiente (P35) |
| T | Intercambio Entrante | 2 | 2 | 201510–201510 | R01 (nombre) |
| 0 | No Regular | 1 | 1 | 201610–201610 | R01 (nombre) |

### 2.2 Tipos de admisión (`cod_admision`) — R02 y R03

Diccionario `ban_tipo_admision` (R02) y uso en estados (R03, sin LIMIT; `admision` trae el mismo nombre). **Clase** (de `tipo_qualitas`): 1 = Ingreso Regular o Centralizada; 2 = Ingreso Especial o Directo; 3 = Otros Ingresos o Cambio de Carrera; — = tipo propio (CN, ES, NN). **Ord.** = `ingreso_ordinario`; **Tot.** = `ingreso_total`. `HP` figura como clase 2 en `tipo_qualitas` y "3. Ingreso PAP" en `tipo_cna`; `CC`, `CS`, `IE`, `IN`, `OO`, `PE`, `UD` y NULL son clase 3. Registros, personas y programas son de estados.

| Código | Nombre | Clase | Ord. | Tot. | Registros | Personas | Programas |
|---|---|---|---|---|---|---|---|
| AR | IEP-Ingreso de Artista | 2 | N | S | 183 | 9 | 7 |
| BE | IEP-Ingreso Cupo Especial BEA | 2 | S | S | 5.752 | 374 | 20 |
| CC | Cambio de Carrera | 3 | N | S | 61.833 | 4.144 | 66 |
| CE | IEP-Ceduc | 2 | N | S | 99 | 14 | 8 |
| CN | Carrera Continuidad | — | N | S | 125 | 10 | 2 |
| CO | IEP-Ingreso Especial Teologico | 2 | N | S | 1.644 | 120 | 5 |
| CS | Cambio de Sede (Misma Carrera) | 3 | N | S | 1.415 | 89 | 14 |
| DE | IEP-Ingreso Deportista | 2 | N | S | 805 | 52 | 16 |
| EB | IEP-Lista Espera BEA | 2 | N | S | 7 | 2 | 1 |
| EC | IEP-Lista Espera Pace | 2 | N | S | 39 | 11 | 6 |
| EE | IEP-Enlace Escolar | 2 | N | S | 20 | 3 | 3 |
| EM | IEP-Lista Espera Mujeres cient | 2 | N | S | 26 | 8 | 6 |
| EP | IEP-Excepción Lista espera Rep | 2 | N | S | 2.316 | 231 | 32 |
| ES | Elección Especialidad | — | N | N | 2.995 | 241 | 11 |
| EX | IEP-Ingreso Extranjero | 2 | N | S | 1.398 | 101 | 30 |
| G9 | IEP-Convenio G9 | 2 | N | S | 34 | 17 | 1 |
| GE | IEP-Ingreso Equidad de Género | 2 | N | S | 169 | 24 | 16 |
| H3 | IEP-Habilitación Pedagogía 30% | 2 | N | S | 86 | 9 | 4 |
| H4 | IEP-Habilitación Pedagogía 33P | 2 | N | S | 6 | 1 | 1 |
| H5 | IEP-Habilitación Pedagogía 50P | 2 | N | S | 264 | 27 | 5 |
| HP | IEP-Habilitación Pedagogía PAP | 2 | N | S | 167 | 22 | 6 |
| ID | Ingreso Especial Discapacidad | 2 | N | S | 198 | 17 | 11 |
| IE | OI-Alumno Especial | 3 | N | N | 37 | 2 | 2 |
| IH | Ingreso Especial Historia | 2 | N | S | 214 | 10 | 4 |
| IN | OI-Ingreso por Intercambio | 3 | N | N | 3.204 | 1.184 | 2 |
| LE | IRP-Lista de espera | 1 | S | S | 11.862 | 726 | 41 |
| LS | IRP-Lista de selección | 1 | S | S | 602.995 | 43.304 | 70 |
| LV | IEP-Ingreso Esp. Licenciatura | 2 | N | S | 68 | 32 | 1 |
| MC | IEP-Mas Mujeres Científicas | 2 | N | S | 433 | 81 | 21 |
| NC | IEP-Inclusion | 2 | N | S | 83 | 12 | 7 |
| NN | Desconocido | — | N | N | 148 | 36 | 2 |
| OA | IRP-Oficio Verif. Excep. DEMRE | 1 | S | S | 185 | 10 | 7 |
| OO | OO-Otros Ingresos | 3 | N | S | 1.685 | 256 | 31 |
| OV | IRP-Oficio de Verificación | 1 | S | S | 554 | 42 | 23 |
| P1 | IEP-Prog. Esp. Acceso PEA | 2 | N | S | 221 | 47 | 20 |
| PA | IEP-Ingreso por Pastoral (OBS) | 2 | N | S | 38 | 9 | 7 |
| PC | IEP-Ingreso Cupo PACE | 2 | S | S | 8.874 | 739 | 46 |
| PD | Prosecución de Estudios | 2 | N | S | 307 | 57 | 2 |
| PE | OI-Planes Especiales | 3 | N | N | 2.559 | 279 | 12 |
| PL | IEP-Ley 20.903 | 2 | N | S | 547 | 33 | 4 |
| PO | IEP-Ingreso Pueblos Originario | 2 | N | S | 481 | 41 | 15 |
| PP | IEP-Propedéutico | 2 | N | S | 1.700 | 126 | 32 |
| PR | IEP-Ingreso Profesional | 2 | N | S | 3.909 | 331 | 39 |
| PS | IEP-Trayectoria Pastoral | 2 | N | S | 45 | 5 | 2 |
| PU | IEP-Ingreso Puntaje Ranking | 2 | N | S | 12 | 2 | 2 |
| RA | Repostulación PACE | 2 | N | S | 207 | 29 | 17 |
| RP | IRP-Repostulación | 1 | S | S | 4.334 | 371 | 40 |
| TP | IEP-Ingr. Tecnico Profesional | 2 | N | S | 1.386 | 110 | 21 |
| TR | IEP-Ingreso de Trabajador | 2 | N | S | 25 | 2 | 1 |
| TU | IEP-Ingreso Traslado de Univ | 2 | N | S | 9.763 | 666 | 55 |
| UD | OI-Ingreso UDM | 3 | N | S | 408 | 20 | 6 |
| VO | IEP-Definición Vocacional | 2 | N | S | 55 | 5 | 4 |
| NULL | — | 3 | N | N | 12 | 3 | 3 |

Códigos del diccionario: 52 más NULL; usados en estados: 52 más NULL. Códigos usados y ausentes del diccionario (comparación R03 vs R02): ninguno. Códigos del diccionario sin uso en estados: ninguno. La fila NULL cubre 12 registros / 3 personas.

### 2.3 Códigos de `comentario` en `ban_historia_notas` — R17

Solo valores con ≥ 100 filas (`resultados_r3.txt#R17`). **Significados por confirmar** (P36): ningún código está explicado por la DAI. La columna DPA muestra cuántas filas del código tienen `nota = 'DPA'` (dato observado, no definición).

| Código | Filas | De ellas DPA | % DPA | Significado |
|---|---|---|---|---|
| (vacío) | 2.488.829 | 91.080 | 3,7 | Sin comentario |
| CCAT | 132.721 | 14.098 | 10,6 | Por confirmar |
| CONVA | 21.740 | 15.840 | 72,9 | Por confirmar |
| CCAR | 9.507 | 3.993 | 42,0 | Por confirmar |
| RCONV | 7.982 | 340 | 4,3 | Por confirmar |
| RCRED | 4.997 | 610 | 12,2 | Por confirmar |
| TRSLD | 1.767 | 1.406 | 79,6 | Por confirmar |
| PESP | 1.218 | 1.206 | 99,0 | Por confirmar |
| INPRO | 724 | 677 | 93,5 | Por confirmar |
| CDEP | 358 | 0 | 0,0 | Por confirmar |
| CSEDE | 327 | 8 | 2,4 | Por confirmar |
| REXTC | 181 | 0 | 0,0 | Por confirmar |
| CRVE | 120 | 0 | 0,0 | Por confirmar |
| ENLC | 100 | 0 | 0,0 | Por confirmar |

Observación: `CONVA` tiene ≈5.900 filas (21.740 − 15.840) sin DPA, posibles convalidaciones con nota numérica (hipótesis; P36).

### 2.4 Otros dominios observados

| Dominio | Valores | Evidencia |
|---|---|---|
| `ban_inscripciones.estado` × `aprobacion` | INSCRITO/APROBADA 88.453; INSCRITO/NULL 73.697; INSCRITO/REPROBADA 19.822; CONV/INY APROBADA 15.550; RENUNCIADA MANUAL 10.104; RENUNCIADA WF 2.964; CONV/INY REPROBADA 1.713; RENUNCIADA WEB 830; CONV/INTERC APROBADA 36; RENUNCIADA WF REPROBADA 1 | `c01_c10#C04` |
| `ban_inscripciones.nota` en `CONV/*` | CONV/INY APROBADA: numérica ≥ 4 15.367, DPA 183; CONV/INY REPROBADA: numérica < 4 1.713; CONV/INTERC APROBADA: numérica ≥ 4 36 | `r3#R16` |
| `ban_historia_notas.oportunidad` | 1: 2.351.185 · 2: 244.421 · 3: 46.450 · 0: 19.531 · 4: 7.873 · 5: 994 · 6: 234 · 7: 26 · 8: 13 · 9: 3 · 10: 1 | `r3#R18` |
| `banner_admision.matricula` | N, Y (sin NULL) | `Q11`, `r3#R25` |

## 3. Sufijos de período

Los 6 dígitos son `AAAA` + sufijo. Significados de la DAI (`respuestas#P23`); conteos de filas por fuente (`resultados_r3.txt#R26`), con rango de períodos.

| Sufijo | Significado (DAI) | Estados | Historia | Inscripciones | Oferta |
|---|---|---|---|---|---|
| `10` | Primer semestre pregrado | 513.676 (200810–202610) | 1.554.145 (198110–202610) | 157.150 (202510–202610) | 142.448 (201610–202610) |
| `20` | Segundo semestre pregrado | 222.189 (200820–202620) | 1.104.788 (198020–202620) | 53.642 (202520) | 119.129 (201620–202520) |
| `15` | Cursos de verano o invierno (cuál, por confirmar) | — | 6.310 (201515–202615) | 1.309 (202515) | — |
| `25` | Cursos de verano o invierno (cuál, por confirmar) | — | 4.841 (201525–202525) | 889 (202525) | — |
| `11` | Poco útil; quizá primera versión | — | 251 (201811–202611) | 6 (202511) | — |
| `21` | **No indicado por la DAI** | 3 (202021) | 231 (201821–202521) | 19 (202521) | — |
| `01` | Poco útil | 64 (202601) | 165 (202601) | 155 (202601) | 5 (202601) |
| `50` | Postgrado | — | — | — | 6.357 (201650–202650) |
| `60` | Postgrado | — | — | — | 4.767 (201660–202560) |

`banner_admision.year_admision` usa `10` (111.266), `20` (427) y `01` (40) (`r3#R25`). No se reconstruyó el calendario con fechas (P45); no se asume que todo período es un semestre regular.
