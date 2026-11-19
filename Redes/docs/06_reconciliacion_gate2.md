# DAI Neural — Reconciliación del Gate 2

**Versión:** 0.1 · 11-11-2026 · Resultado de ejecutar `pipelines.extract`, `pipelines.normalize.build_core` y `pipelines.reconcile` contra el Warehouse (solo lectura) y la BD de desarrollo localhost.
**Estado del Gate 2: cerrado con observaciones.** Los conteos de las 13 fuentes coinciden con el Warehouse, no hay RUT en ninguna columna y el núcleo reproduce todas las cifras de la evidencia salvo cuatro, que difieren por el orden y el método de vecinos de `r3#R12` (no por los datos; ver §3). Las observaciones abiertas están en §6.

## 1. Qué se ejecutó y cuánto tardó

| Paso | Comando | Resultado | Tiempo |
|---|---|---|---|
| Migraciones | `pipelines.migrate` | `006` (tabla `neural_stg.malla_programa`), `007` (3 columnas en `asignatura_malla`), `008` (`explicacion` en `auditoria_resultado`) | segundos |
| Extracción | `pipelines.extract` | 13 fuentes cargadas + verificación de `ban_tipo_admision` | ≈ 5,7 min (estados 61 s; historia 226 s; inscripciones 18 s; oferta 14 s; matrícula 11 s; admisión 6 s; titulados 1 s; resto < 1 s) |
| Núcleo | `pipelines.normalize.build_core` | 17 tablas, una sola transacción | ≈ 11,9 min (persona 4 s; catálogos 3 s; postulación 13 s; episodios y estados 133 s; intentos 505 s; inscripciones 34 s; secciones 18 s; titulación 3 s; postgrado < 1 s) |
| Reconciliación | `pipelines.reconcile` | 92 chequeos | ≈ 1,8 min (privacidad 86 s; núcleo 19 s; fuentes 1 s) |
| Pruebas | `pytest -q` | 351 pasan | 1,4 s |

La repetición de `pipelines.extract` sin cambios en el Warehouse no carga nada (idempotente); `--force` recarga la fuente indicada reutilizando su fila de procedencia.

### Filas por tabla

| Capa | Tabla | Filas |
|---|---|---|
| stg | `ban_estados_academicos` / `ban_historia_notas` / `ban_inscripciones` / `ban_oferta_academica` | 735.932 / 2.670.731 / 213.170 / 272.706 |
| stg | `banner_admision` / `banner_matricula` / `banner_titulados` / `banner_estudiantes_postgrado` | 111.733 / 204.396 / 19.712 / 4.466 |
| stg | `ban_malla_programa` / `malla_programa_prereq` / `malla_programa` / `banner_catalogos` / `programa_d` | 40.077 / 45.439 / 8.091 / 211 / 185 |
| core | `persona` / `programa` / `programa_catalogo` / `asignatura_malla` / `prerrequisito` / `hito_formativo` | 69.971 / 185 / 353 / 29.614 / 31.996 / 837 |
| core | `postulacion_via` / `postulacion` | 111.733 / 107.036 |
| core | `episodio_programa` / `evento_estado` | 57.561 / 735.932 |
| core | `intento_asignatura` | 2.670.731 |
| core | `inscripcion_asignatura` / `inscripcion_equivalencia` | 194.080 / 212.642 |
| core | `seccion` / `seccion_docente` | 65.074 / 80.921 |
| core | `titulacion` / `matricula_postgrado` | 19.709 / 4.413 |

## 2. Tabla de reconciliación

Esperado = cifra de la evidencia (`resultados_*.txt`) o, en los chequeos `stg:*`, el recuento en vivo de la vista. Los chequeos "sin pérdida" comparan el núcleo con el stg. Los "informativo" no tienen cifra de referencia. Cada fila queda en `neural_meta.auditoria_resultado` (con `explicacion`).

| Chequeo | Esperado | Obtenido | OK | Explicación |
|---|---|---|---|---|
| `stg:ban_estados_academicos` | 735.932 | 735.932 | sí | recuento en vivo de la vista |
| `stg:ban_historia_notas` | 2.670.731 | 2.670.731 | sí | recuento en vivo de la vista |
| `stg:ban_inscripciones` | 213.170 | 213.170 | sí | recuento en vivo de la vista |
| `stg:ban_oferta_academica` | 272.706 | 272.706 | sí | recuento en vivo de la vista |
| `stg:banner_admision` | 111.733 | 111.733 | sí | recuento en vivo de la vista |
| `stg:banner_matricula` | 204.396 | 204.396 | sí | recuento en vivo de la vista |
| `stg:banner_titulados` | 19.712 | 19.712 | sí | recuento en vivo de la vista |
| `stg:banner_estudiantes_postgrado` | 4.466 | 4.466 | sí | recuento en vivo de la vista |
| `stg:ban_malla_programa` | 40.077 | 40.077 | sí | recuento en vivo de la vista |
| `stg:malla_programa_prereq` | 45.439 | 45.439 | sí | recuento en vivo de la vista |
| `stg:malla_programa` | 8.091 | 8.091 | sí | recuento en vivo de la vista |
| `stg:banner_catalogos` | 211 | 211 | sí | recuento en vivo de la vista |
| `stg:programa_d` | 185 | 185 | sí | recuento en vivo de la vista |
| `llaves_no_hex64` | 0 | 0 | sí | 18 columnas persona_key/docente_key revisadas |
| `rut_like_en_columnas_texto` | 0 | 0 | sí | 232 columnas de texto en 30 tablas |
| `core:evento_estado` | 735.932 | 735.932 | sí | coincide |
| `core:evento_estado = stg` | 735.932 | 735.932 | sí | coincide |
| `core:episodio_programa` | 57.561 | 57.561 | sí | coincide |
| `core:persona con estados` | 49.582 | 49.582 | sí | coincide |
| `core:personas con estados = stg` | 49.582 | 49.582 | sí | coincide |
| `core:persona total` | informativo | 69.971 | sí | unión de estados, historia, inscripciones, titulados y postgrado |
| `core:intento_asignatura` | 2.670.731 | 2.670.731 | sí | coincide |
| `core:intentos DPA` | 129.258 | 129.258 | sí | coincide |
| `core:intentos nota 4,0` | 196.982 | 196.982 | sí | coincide |
| `core:intento con 1 episodio candidato` | 1.860.553 | 1.860.553 | sí | coincide |
| `core:intento con 0 candidatos` | 801.181 | 801.181 | sí | coincide |
| `core:intento con 2+ candidatos` | 8.997 | 8.997 | sí | coincide |
| `core:intento sin pérdida ni multiplicación` | 2.670.731 | 2.670.731 | sí | coincide |
| `core:estados con cod_admision NULL` | 12 | 12 | sí | coincide |
| `core:fecha_estado NULL` | 159.885 | 159.885 | sí | coincide |
| `core:fecha_estado futura (marcador)` | 21 | 21 | sí | coincide |
| `core:NULL con fecha a ambos lados (incluye invertidos)` | 110.733 | 111.090 | **no** | r3#R12 se midió en orden sorlcur; el orden canónico (periodo, sorlcur) y el vecino más cercano cambian la clasificación (ver chequeos 'R12 paridad' y 'R12 ventana ilimitada, orden canónico') |
| `core:NULL solo con fecha anterior` | 8.967 | 11.985 | **no** | r3#R12 se midió en orden sorlcur; el orden canónico (periodo, sorlcur) y el vecino más cercano cambian la clasificación (ver chequeos 'R12 paridad' y 'R12 ventana ilimitada, orden canónico') |
| `core:NULL solo con fecha posterior` | 38.927 | 35.552 | **no** | r3#R12 se midió en orden sorlcur; el orden canónico (periodo, sorlcur) y el vecino más cercano cambian la clasificación (ver chequeos 'R12 paridad' y 'R12 ventana ilimitada, orden canónico') |
| `core:NULL sin vecinos` | 1.258 | 1.258 | sí | coincide |
| `core:NULL con intervalo invertido` | 5.068 | 638 | **no** | R12 compara el máximo anterior con el mínimo posterior en orden sorlcur; aquí vecino más cercano en orden canónico (los descensos de fecha bajan al ordenar por período, r3#R05) |
| `core:R12 paridad (orden sorlcur) ambos lados` | 110.733 | 110.733 | sí | coincide |
| `core:R12 paridad (orden sorlcur) solo anterior` | 8.967 | 8.967 | sí | coincide |
| `core:R12 paridad (orden sorlcur) solo posterior` | 38.927 | 38.927 | sí | coincide |
| `core:R12 paridad (orden sorlcur) sin vecinos` | 1.258 | 1.258 | sí | coincide |
| `core:R12 paridad (orden sorlcur) invertido` | 5.068 | 5.068 | sí | coincide |
| `core:R12 ventana ilimitada, orden canónico: ambos lados` | informativo | 111.090 | sí | mismo método de R12 aplicado al orden (periodo, sorlcur) |
| `core:R12 ventana ilimitada, orden canónico: solo anterior` | informativo | 11.985 | sí | mismo método de R12 aplicado al orden (periodo, sorlcur) |
| `core:R12 ventana ilimitada, orden canónico: solo posterior` | informativo | 35.552 | sí | mismo método de R12 aplicado al orden (periodo, sorlcur) |
| `core:R12 ventana ilimitada, orden canónico: sin vecinos` | informativo | 1.258 | sí | mismo método de R12 aplicado al orden (periodo, sorlcur) |
| `core:R12 ventana ilimitada, orden canónico: invertido` | informativo | 1.061 | sí | mismo método de R12 aplicado al orden (periodo, sorlcur) |
| `core:postulacion_via` | 111.733 | 111.733 | sí | coincide |
| `core:postulacion` | 107.036 | 107.036 | sí | coincide |
| `core:R37 region_colegio vacío` | 7.352 | 7.352 | sí | coincide |
| `core:R37 comuna_colegio vacío` | 7.352 | 7.352 | sí | coincide |
| `core:R37 cod_comuna vacío` | 9.060 | 9.060 | sí | coincide |
| `core:postulacion_via con puntaje no parseable` | informativo | 0 | sí | textos de puntaje que no son número; el valor queda NULL con bandera |
| `core:inscripcion (filas con estado)` | 194.080 | 194.080 | sí | coincide |
| `core:inscripcion grano sin estado` | 194.072 | 194.072 | sí | coincide |
| `core:inscripcion_equivalencia suma filas_origen = stg` | 213.170 | 213.170 | sí | coincide |
| `core:inscripcion con estado_conflicto (grupos)` | 8 | 8 | sí | coincide |
| `core:personas tituladas` | 19.589 | 19.589 | sí | coincide |
| `core:titulacion filas = stg menos repetidas en clave` | 19.709 | 19.709 | sí | coincide |
| `core:estado U sin registro de titulado (P42)` | 825 | 825 | sí | coincide |
| `core:personas con estado U` | 18.959 | 18.959 | sí | coincide |
| `core:seccion (periodo, nrc)` | 65.074 | 65.074 | sí | coincide |
| `core:secciones con más de un docente` | 9.341 | 9.341 | sí | coincide |
| `core:programa` | 185 | 185 | sí | coincide |
| `core:programa válidos` | 170 | 170 | sí | coincide |
| `core:programa con predecesor` | 15 | 15 | sí | coincide |
| `core:predecesor inexistente` | 1 | 1 | sí | coincide |
| `core:asignatura_malla (programa, catálogo, asignatura)` | 29.614 | 29.614 | sí | coincide |
| `core:asignatura_malla sin pérdida (suma filas_origen = stg)` | 40.077 | 40.077 | sí | coincide |
| `core:programa-catálogo de la malla oficial` | 284 | 284 | sí | coincide |
| `core:prerrequisito aristas distintas` | 31.996 | 31.996 | sí | coincide |
| `core:prerrequisito suma filas_origen = stg` | 45.439 | 45.439 | sí | coincide |
| `core:prerrequisito asignatura en malla oficial (J24)` | 28.859 | 28.859 | sí | coincide |
| `core:prerrequisito requisito en malla oficial (J25)` | 12.175 | 12.175 | sí | coincide |
| `stg:R19 requisito misma malla (legacy)` | 12.255 | 12.255 | sí | coincide |
| `stg:R19 requisito otro catálogo (legacy)` | 986 | 986 | sí | coincide |
| `stg:R19 requisito otro programa (legacy)` | 17.448 | 17.448 | sí | coincide |
| `stg:R19 requisito en ninguna malla (legacy)` | 1.307 | 1.307 | sí | coincide |
| `core:R35 historia en malla (mismo programa y catálogo)` | 2.065.392 | 2.065.392 | sí | coincide |
| `core:R35 historia en malla (otro catálogo del programa)` | 55.227 | 55.227 | sí | coincide |
| `core:R35 historia en malla (otro programa)` | 125.823 | 125.823 | sí | coincide |
| `core:R35 historia en malla (ninguna malla)` | 424.289 | 424.289 | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2016` | 89591 (90.4%) | 89591 (90.4%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2017` | 91630 (69.7%) | 91630 (69.7%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2018` | 92196 (82.3%) | 92196 (82.3%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2019` | 89649 (95.7%) | 89649 (95.7%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2020` | 93575 (96.9%) | 93575 (96.9%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2021` | 98451 (96.4%) | 98451 (96.4%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2022` | 90948 (81.9%) | 90948 (81.9%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2023` | 95710 (71.3%) | 95710 (71.3%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2024` | 98553 (93.6%) | 98553 (93.6%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2025` | 105166 (95.5%) | 105166 (95.5%) | sí | coincide |
| `core:R13 evaluadas vinculadas a oferta 2026` | 59074 (77.9%) | 59074 (77.9%) | sí | coincide |

## 3. Diferencias y su explicación

Cuatro chequeos no coinciden; los cuatro son la imputación de fechas NULL (`r3#R12`) y no se forzaron:

- **Los datos son los mismos.** Aplicando el método de R12 (orden `sorlcur`, máximo anterior y mínimo posterior con ventana ilimitada) sobre `core.evento_estado`, se reproduce R12 exacto: 110.733 / 8.967 / 38.927 / 1.258 / 5.068 (chequeos "R12 paridad").
- **Cambia la regla, no el dato.** `03_reglas_academicas.md` (RA01, RA03) fija el orden canónico (`periodo`, `sorlcur`) y el vecino más cercano con fecha; R12 midió en orden `sorlcur`. Con el orden canónico y la ventana de R12 se obtienen 111.090 / 11.985 / 35.552 / 1.258 / 1.061 (chequeos "ventana ilimitada, orden canónico"), que coinciden con lo que produce el núcleo en las tres categorías de vecinos. Los intervalos invertidos bajan de 5.068 a 638 porque el orden canónico elimina la mayoría de los descensos de fecha (`r3#R05`) y porque el núcleo usa el vecino más cercano y no el máximo/mínimo de toda la ventana.
- "Ambos lados" se compara incluyendo los invertidos (R12 los contaba dentro de ese grupo).

Resto de cifras de evidencia, todas exactas: estados, episodios, personas con estados, intentos, DPA, nota 4,0, candidatos de episodio (1.860.553 / 801.181 / 8.997), fechas NULL (159.885) y futuras (21), vías y postulaciones, grano de inscripciones (194.072 y 194.080, 8 grupos con conflicto de estado), titulados (19.589), personas con estado `U` sin registro de titulado (825), secciones (65.074), cobertura de la malla (R35), aristas de prerrequisito (J24/J25), programas (R14/R15), completitud de región/comuna (R37) y cobertura de oferta por año (R13, 2016–2026).

## 4. Límites de cobertura (de la evidencia, no de la carga)

- **Oferta académica:** solo desde 201610; la cobertura de notas evaluadas con sección va de 69,7 % (2017) a 96,9 % (2020) y 77,9 % en 2026 (año en curso). Antes de 2016 no hay secciones: `seccion` y `seccion_docente` no sirven para tasas por docente históricas.
- **Docentes:** 7.920 filas de oferta sin `rut_profesor`; 2.907 secciones sin docente en el puente. Sin regla de atribución del resultado entre docentes (P14).
- **Inscripciones:** solo 202510–202610; la historia sigue siendo la fuente principal de intentos.
- **Episodios:** 801.181 filas de historia no caen en ningún episodio (programa sin estados) y 8.997 caen en dos o más; no se elige entre candidatos (R36). Solo 18.449 de 19.709 titulaciones se enlazan a un episodio (430 son ambiguas, el resto no tiene episodio del mismo programa).
- **Malla oficial:** 424.289 filas de historia no están en ninguna malla (R35); no hay llave foránea de intento a malla.
- **Prerrequisitos:** clasificados contra la malla oficial (`ban_malla_programa`): 12.175 misma malla, 2.365 otro catálogo, 17.223 otro programa, 233 sin malla. La clasificación de R19 (12.255 / 986 / 17.448 / 1.307) se hizo contra la malla antigua `malla_programa`; se reproduce exacta en stg (chequeos "R19 legacy") y no es comparable con la del núcleo.
- **Postgrado:** 4.413 de 4.466 filas en el núcleo (ver §5, ambigüedad 9). Diferido después del MVP.
- **Edades de los datos:** el Warehouse carga cada vista en fechas distintas (según `timestamp_carga`, UTC: estados, oferta, inscripciones y malla 02-11-2026; historia, titulados y postgrado 26-10-2026; admisión 01-06-2026; `malla_programa` y prerrequisitos 12-03-2025). Los cortes entre fuentes no son simultáneos.

## 5. Ambigüedades de reglas y cómo se resolvieron

Se eligió siempre la opción conservadora y se dejó bandera o conteo.

1. **Corte de extracción (RA04).** Se usa la fecha del `timestamp_carga` de la carga vigente de estados (02-11-2026, UTC). Las 21 fechas futuras (todas `B`) lo superan igual con cualquier corte entre el 02 y el 11-11-2026.
2. **Vocabulario de `sexo`.** Estados usa `MASCULINO`/`FEMENINO` y admisión `M`/`F` (más `N` en 6 filas). Se normaliza a `M`/`F`; cualquier otra etiqueta se conserva tal cual y, si discrepa, la persona queda con `sexo_conflicto` y `sexo` NULL. Resultado: 4 conflictos; 16.085 personas sin dato (solo aparecen en historia, inscripciones, titulados o postgrado). Solo para equidad (M1).
3. **Idempotencia sin marca de carga.** `programa_d` y `banner_matricula` no tienen tabla `_full` ni `*_cargas`; su `timestamp_carga_wh` queda NULL y "sin cambios" se decide por igualdad del recuento de filas (aproximación débil: un cambio con el mismo recuento no se detecta; `--force` lo resuelve).
4. **`timestamp_carga_wh`.** Estados e historia: la carga marcada `vigente` (exactamente una, `pick_vigente`). Resto: `max(timestamp_carga)` de la tabla `_full` (único valor leído de ellas).
5. **Malla oficial repetida.** 5.233 de 29.614 grupos (programa, catálogo, asignatura) tienen varias filas y 5.199 difieren en algún atributo (4.088 en el semestre). Se conserva una fila por grupo (la de menor semestre, desempate determinista) con `filas_origen` y `atributos_conflicto` (migración `007`); la suma de `filas_origen` es 40.077.
6. **Semestre.** `'Semestre 09 CP'` → 9. `'Año 01 CP'` y `'Area 02 CP'` no son semestres: `semestre` NULL y la etiqueta original en `semestre_texto`.
7. **Secciones.** 18.785 secciones tienen filas con atributos distintos (p. ej. horarios); `seccion` toma una fila completa por orden lexicográfico de sus atributos, no una mezcla. Sin NRC vacío en la oferta.
8. **Titulación.** 3 grupos con la clave natural repetida y filas idénticas: se conserva 1 de cada uno. El episodio se enlaza solo si hay exactamente un episodio del mismo programa.
9. **Postgrado.** La clave (persona, programa, período) no es única en la fuente (34 grupos; 33 con estados distintos) y 20 filas no tienen programa o período. Se conserva la de fecha de estado más reciente; las 53 filas restantes quedan solo en stg.
10. **Persona.** Unión de estados, historia, inscripciones, titulados y postgrado. Los postulantes que no aparecen en otra fuente no se crean como persona (la admisión no tiene llave foránea a `persona`); solo aportan `sexo` si la persona ya existe.
11. **Inscripciones.** El resultado del grupo se clasifica con la primera fila (por orden de carga); 0 grupos tienen filas con resultado distinto. 396 renuncias repetidas, 234 inscripciones con `oportunidad` distinta entre equivalencias, 0 con discrepancia entre nota y etiqueta.
12. **Estados sin código.** 5.211 estados con `cod_estado` NULL se conservan con `sin_codigo` y `estado_conocido` falsos; 17 reversas se conservan con bandera y fuera de episodios.
13. **Episodios no contiguos.** 1.582 en orden canónico (R08 midió 1.660 sobre la secuencia `sorlcur`); no se comparó porque la definición difiere.
14. **`ban_tipo_admision`.** El diccionario sembrado (52 códigos) coincide con la vista salvo una coma final en el nombre de `LE` y `LS` y una fila del Warehouse sin código (clase "otros ingresos"); se verifica, no se copia.
15. **Transacción única.** `build_core` reconstruye todas las entidades seleccionadas en una transacción (más estricto que "una por entidad"): si falla, no cambia nada.
16. **Hitos formativos.** 837 candidatos por nombre (`regex_nombre_v1`), todos `validado = false` (P26).

## 6. Problemas pendientes

- **Gate 2 cerrado con observaciones:** la única diferencia con la evidencia es el método de R12 (§3); conviene que el equipo confirme que el orden canónico y el vecino más cercano (RA03) siguen siendo la regla.
- Idempotencia débil en `programa_d` y `banner_matricula` (ambigüedad 3).
- `banner_matricula` está en stg pero no tiene tabla en `neural_core` (el modelo no la define).
- `sexo` y `dic_comentario_nota` (resto de P36) siguen como en el plan; la sensibilidad por `comentario` no se midió.
- `neural_mart` no se construye hasta cerrar el Gate 2.
- El secreto HMAC sigue sin custodia definitiva (P34); la tabla de correspondencia no existe, así que un cambio de secreto obliga a recargar todo.
