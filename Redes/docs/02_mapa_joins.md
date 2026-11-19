# DAI Neural — Mapa de joins (Fase 1, entregable 02)

**Versión:** 0.2 · 11-11-2026 (actualiza J11, §2.1 y dirección de prerrequisitos tras la segunda ronda de la DAI). Cada unión indica cardinalidad, cobertura medida y estado: **verificado** (medido con SQL de solo lectura), **parcial** (medido en parte o solo por inferencia de otras mediciones) o **no verificado** (sin medición). Evidencia `r3#Rxx` = `resultados_r3.txt`; `c01_c10`, `q1_q16`, `v1_v14` = `resultados_*.txt`; `resp#Pxx` = `respuestas_dai_2026-11-11.md`.
**Convención:** `A → B` = muchos de A a uno de B (N:1) salvo que se indique. Todas las uniones por `rut` se hacen sobre `persona_key` (HMAC), nunca sobre el RUT.

## 1. Programas (clave de unión: `common.programa_d`)

`programa_d`: 185 programas, `id` ↔ `cod_banner` biyectivo (185 ids, 185 códigos, 0 vacíos; `c01_c10#C06`). 170 válidos, 15 no válidos, 15 con `programa_predecesor`, 1 predecesor que no existe en la tabla (`r3#R15`). La DAI confirma que `cod_banner` es equivalente entre fuentes (`resp#P07`).

| ID | Unión | Cardinalidad | Cobertura medida | Estado | Evidencia |
|---|---|---|---|---|---|
| J01 | `ban_estados_academicos.cod_programa` → `programa_d.cod_banner` | N:1 | 90 de 90 códigos (89 válidos); 735.932 de 735.932 filas | **Verificado** | `r3#R14` |
| J02 | `ban_historia_notas.cod_carrera` → `programa_d.cod_banner` | N:1 | 85 de 85 códigos (83 válidos); 2.670.731 de 2.670.731 filas | **Verificado** | `r3#R14` |
| J03 | `banner_admision.cod_carrera` → `programa_d.cod_banner` | N:1 | 86 de 86 (83 válidos); 111.733 de 111.733 filas | **Verificado** | `r3#R14` |
| J04 | `banner_matricula.cod_carrera` → `programa_d.cod_banner` | N:1 | 82 de 82 (82 válidos); 204.396 de 204.396 filas | **Verificado** | `r3#R14` |
| J05 | `banner_titulados.codigo_carrera` → `programa_d.cod_banner` | N:1 | 65 de 65 (64 válidos); 19.712 de 19.712 filas | **Verificado** | `r3#R14` |
| J06 | `malla_programa.cod_programa` (bigint) → `programa_d.id` | N:1 | 8.091 filas, 0 sin programa; 173 combinaciones (programa, catálogo), 0 sin mapeo | **Verificado** | `c01_c10#C07` |
| J07 | `ban_malla_programa.malla_program_code` → `programa_d.cod_banner` | N:1 | 149 de 152 códigos; 40.056 de 40.077 filas (21 filas sin mapeo) | **Parcial** | `r3#R14` |
| J08 | `programa_d.programa_predecesor` → `programa_d.id` | N:1 (autorreferencia) | 15 con predecesor; 1 inexistente | **Parcial** (semántica del linaje por confirmar) | `r3#R15` |
| J09 | `malla_programa_prereq.cod_programa` → `programa_d.id` | N:1 | No medido directamente; R19 usa este enlace en la rama `ban_malla_programa` | **No verificado** | `r3#R19` (indirecto) |

Observación: en J01–J05 hay códigos en uso que corresponden a programas con `valid_program` falso (diferencia entre `codigos` y `codigos_validos`). Los catálogos cambian con actualizaciones de malla (`resp#P07`); `catalogo` es parte del identificador de malla.

## 2. Estados, episodios y personas

| ID | Unión | Cardinalidad | Cobertura medida | Estado | Evidencia |
|---|---|---|---|---|---|
| J10 | `ban_estados_academicos`: (`rut`, `sorlcur`) → estado | 1:1 | 0 pares repetidos sobre 735.932; `sorlcur` sin NULL ni decimales | **Verificado** | `c01_c10#C01`, `r3#R06` |
| J11 | Estados → `episodio_programa` por (`rut`, `cod_programa`, `cod_admision`, `periodo_admision`) | N:1 | 57.561 episodios; 49.582 personas; 56.172 pares persona-programa; 12 filas con `cod_admision` NULL | **Parcial** (clave fijada por decisión del equipo, P38; N:1 medido en R07–R08) | `r3#R07`, `#R08` |
| J12 | `ban_estados_academicos.cod_admision` → `ban_tipo_admision.cod_admision` | N:1 | 52 códigos usados, todos presentes en el diccionario; 12 filas NULL (derivado de comparar R02 y R03) | **Parcial** (no es SQL de unión) | `r3#R02`, `#R03` |
| J13 | Personas en `ban_historia_notas` ↔ `ban_estados_academicos` por `rut` | N:M por persona | Notas 66.125 RUT; estados 49.582; en ambas 47.574; solo notas 18.551; solo estados 2.008 | **Verificado** (nivel persona) | `r3#R30` |
| J14 | Estados `U` ↔ `banner_titulados` por `rut` | 1:N (titulados) | 19.589 personas tituladas; 18.134 con estado `U`; 18.959 personas con `U`; 825 sin registro | **Verificado** (nivel persona) | `r3#R28` |
| J15 | Estados ↔ `banner_admision` / `banner_matricula` (`rut`, programa, período de admisión) | Por definir | No medido | **No verificado** | — |
| J16 | Estados ↔ historia por (`rut`, programa, `catalogo`) | Por definir | No medido (solo nivel persona, J13) | **No verificado** | — |

### 2.1 Clave de episodio (decisión del equipo)

- **Definición (decisión del equipo por delegación de la DAI, `resp#P38`):** episodio = (`persona_key`, `cod_programa`, `cod_admision`, `periodo_admision`) (RA09). La DAI dijo "`cod_admision` + `periodo` + `periodo_admision`, por persona y programa" (`resp#P06`); `periodo` varía en cada estado, por lo que no se puede usar como clave. Los episodios no contiguos se unifican con `tramo_n` por estado; el `catalogo` se registra por estado; `cod_admision` NULL → `NN` con marca.
- **Tamaño:** 57.561 episodios en 49.582 personas. Personas con 1/2/3/4+ episodios: 42.824/5.734/863/161; máximo 7 (`r3#R07`, `#R08`).
- **Casos límite:** 1.660 episodios no contiguos en la secuencia (intercalados); 6.530 con más de un catálogo (actualización de malla dentro del episodio, coherente con `resp#P07`); 1.483 de un solo estado; 12 filas con `cod_admision` NULL.
- **No es cambio de episodio:** un estado `D` (cambio de ciclo): el siguiente estado queda casi siempre en el mismo programa y con el mismo `cod_admision` (LS→M 11.981; LS→J 6.660; CC→M 1.576) (`r3#R09`).
- **Es cambio de episodio:** cambio de `cod_programa` entre estados consecutivos. Entra con `CC` (tras M 1.295, J 867, O 777, N 423) o con admisión regular nueva `LS` (tras M 1.524, B 776, E 554) (`r3#R10`, `#R11`; listas de 30 filas).
- **Orden dentro de la persona:** (`periodo`, `sorlcur`) (`resp#P01`; `r3#R04`, `#R05`). `sorlcur` no se reinicia por programa y no sirve para contar eventos (`r3#R06`).

## 3. Notas, inscripciones, oferta y docentes

| ID | Unión | Cardinalidad | Cobertura medida | Estado | Evidencia |
|---|---|---|---|---|---|
| J17 | Intento de historia: (`periodo`, `rut`, `cod_carrera`, `catalogo`, `materia`, `curso`, `oportunidad`, `nrc`) | 1:1 | 0 claves repetidas sobre 2.670.731 | **Verificado** | `v1_v14#V08` |
| J18 | Historia → sección de oferta por (`periodo`, `nrc`), con NRC no vacío | N:1 a sección; sección 1:N docentes | Filas evaluadas (sin DPA) vinculadas: 2016 90,4 %; 2017 69,7 %; 2018 82,3 %; 2019 95,7 %; 2020 96,9 %; 2021 96,4 %; 2022 81,9 %; 2023 71,3 %; 2024 93,6 %; 2025 95,5 %; 2026 77,9 % (en curso). Antes de 2016: sin oferta | **Verificado** (cobertura por año) | `r3#R13` |
| J19 | Sección → docentes: `ban_oferta_academica` (`periodo`, `nrc`) → `rut_profesor` | 1:N | 65.074 secciones; 47.252 con varias filas; 9.341 con varios docentes; máx. 451 filas por sección; 5.791 secciones con notas y varios docentes | **Verificado** | `q1_q16#Q15`, `v1_v14#V09` |
| J20 | Historia ↔ inscripciones por clave de intento | Por definir | `ban_inscripciones` cubre 202510–202610; clave no medida | **No verificado** | `r3#R26`, `#R27` |
| J21 | Historia ↔ malla: `materia`‖`'-'`‖`curso` ↔ `ban_malla_programa.malla_materiacurso` / `malla_programa.codigo_asignatura` | N:1 | Formato: historia `AAAA99999` (2.670.717 filas con ese patrón); mallas y prerrequisitos `AAAA-99999`; cobertura del emparejamiento no medida | **Parcial** (formato verificado) | `r3#R20` |

### 3.1 Tabla puente `seccion_docente`

- **Nunca** unir notas a oferta con un join plano (multiplicaría intentos): primero `seccion` = `DISTINCT (periodo, nrc)`, luego `seccion_docente` (`periodo`, `nrc`, `persona_key` docente, `rol` = `tipo_profesor`).
- Sin regla de atribución del resultado entre docentes (P14): la tasa por docente se calcula sobre secciones con oferta (desde 2016) y se reporta cobertura. Un intento pertenece a **una** sección; la sección tiene 0..N docentes.
- La DAI indica que el foco son las notas de los estudiantes y que menos vínculos docentes que notas es normal (`resp#P14`).

## 4. Mallas y prerrequisitos

| ID | Unión | Cardinalidad | Cobertura medida | Estado | Evidencia |
|---|---|---|---|---|---|
| J22 | Prerrequisito (31.996 aristas distintas de 45.439 filas): asignatura presente en la misma malla (`malla_programa`, programa-catálogo) | N:1 | 8.981 de 31.996 | **Verificado** (baja cobertura) | `r3#R19`, `v1_v14#V11` |
| J23 | Prerrequisito: requisito en la misma malla | N:1 | 12.255; en otro catálogo del mismo programa 986; en otro programa 17.448; en ninguna malla 1.307 (suman 31.996) | **Verificado** | `r3#R19` |
| J24 | Prerrequisito vs `ban_malla_programa` (vía `programa_d`, mismo programa y catálogo): asignatura | N:1 | 28.859 de 31.996 | **Verificado** | `r3#R19` |
| J25 | Prerrequisito vs `ban_malla_programa`: requisito | N:1 | 12.175 de 31.996 | **Verificado** | `r3#R19` |
| J26 | `ban_malla_programa` (programa, catálogo) ↔ `catalogo` de estados/historia | Por definir | `ban_malla_programa` tiene 284 programa-catálogo; emparejamiento no medido | **No verificado** | `r3#R21` |

- La malla oficial es `ban_malla_programa` (`resp#P17`; 40.077 filas, 152 programas, 0 sin semestre, 0 con catálogo `000000`; `r3#R21`). `malla_programa` (8.091 filas) es incompleta.
- Los requisitos en otro programa (17.448) son coherentes con ramos del ciclo básico fuera de la especialidad (`resp#P15`); **no se descartan aristas**: se clasifican (misma malla / otro catálogo / otro programa / sin malla).
- Códigos con patrón `AAA9-99999`: 98 filas en `prereq.asig` (`r3#R20`); requieren normalización antes de unir.
- Dirección confirmada (`resp#P46`): arista `codigo_asignatura_repreq` → `codigo_asignatura` (requisito → curso). Sin verificar con datos (ciclos pendientes en ronda 4).

## 5. Procedencia y vigencia

| ID | Unión | Detalle | Estado | Evidencia |
|---|---|---|---|---|
| J27 | Vista vigente ↔ `*_cargas` | Estados y notas filtran por `vigente`; la vigencia es automática: "la más nueva con ruts ≥ 97 % del máximo histórico". Estados: vigente = la más nueva (04-11-2026, 735.932 filas, 49.582 RUT). Notas: vigente = carga del 28-10-2026 (2.670.731 filas, 66.125 RUT); las dos del 04-11-2026 (2.443.729 filas, 64.006 RUT) no lo son | **Verificado** | `r3#R29` |
| J28 | `timestamp_carga` | Epoch en milisegundos (`resp#P19`); consistente con `medido_en` en estados y notas | **Parcial** (otras tablas sin medir) | `r3#R29` |

## 6. Uniones pendientes de medir (ronda 4 propuesta)

J09, J15, J16, J20, J21 (cobertura), J26, y el cruce nota 4,0 × `oportunidad`. Ver `00_plan.md` §7.
