# DAI Neural — Benchmark T2: aprobación por intento

**Versión:** 0.4 · 18-11-2026 (variables nuevas de la DAI P117–P127: promedio en el mismo departamento y rendimiento del semestre previo; `cb_c_nuevas` pasa a ser el modelo conservado por D114, §16) · 0.3 · 13-11-2026 (reconstrucción consolidada, etapa B: variables `mm_*` + prueba, bandas de nota P84, pronósticos agregados P74, ablación de estadística reciente P55) · anterior:  0.1 · 12-11-2026 · Fase 4, benchmark T2. Base: `PROMPT_MAESTRO.md` (Predicción experimental, Evaluación, Fase 4; no negociable 5), `03_reglas_academicas.md`, `05_modelo_datos.md`, `08_benchmark_t1.md` (misma estructura, estándar y herramientas).
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, nota, RUT ni predicción por persona figura en este documento ni en el repositorio.

## Cambios de la reconstrucción consolidada (13-11-2026)

1. **Variables de admisión.** `mm_*` (mínimo–máximo por prueba, año y campo) y `prueba_admision` reemplazan a los percentiles `pct_*` en los conjuntos (a)–(d) de CatBoost, la logística y las redes.
2. **Datos de la etapa A.** El snapshot se reconstruyó con las notas y los intentos corregidos (menos intentos de train y test, tasa de reprobación de test de 0,158 a 0,144).
3. **Banda de nota por intento (P84).** Se reemplazan los cortes anteriores por la escala institucional y se agrega un modelo multiclase (§12b).
4. **Ablación de estadística reciente (P55)** (§12c) y **pronósticos agregados por programa y facultad (P74)** (§12b).

Antes y después de la reconstrucción (test, IC 95 %):

| Métrica | Antes | Después | Cambio |
|---|---|---|---|
| Intentos de train | 522.645 | 515.891 | -6754 |
| Intentos de test | 233.001 | 228.752 | -4249 |
| Tasa de reprobación de train | 0,1741 | 0,1638 | -0,0103 |
| Tasa de reprobación de test | 0,1585 | 0,1437 | -0,0149 |
| AP de test, Tasa histórica del curso (expansiva) | 0,383 [0,377; 0,389] | 0,359 [0,353; 0,365] | -0,024 |
| AP de test, CatBoost (a) estudiante + carga | 0,433 [0,426; 0,440] | 0,432 [0,425; 0,440] | -0,001 |
| AP de test, CatBoost (b) + curso | 0,535 [0,528; 0,543] | 0,530 [0,523; 0,538] | -0,005 |
| AP de test, CatBoost (c) + prerrequisitos | 0,538 [0,531; 0,545] | 0,534 [0,527; 0,541] | -0,004 |
| AP de test, CatBoost (d) + docente | 0,560 [0,553; 0,567] | 0,562 [0,555; 0,569] | +0,002 |
| AP de test, Logística (c) + prerrequisitos | 0,501 [0,491; 0,510] | 0,499 [0,491; 0,507] | -0,002 |
| AP de test, Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0,527 [0,520; 0,535] | 0,516 [0,509; 0,524] | -0,011 |
| ROC-AUC de test, CatBoost (b) + curso | 0,850 [0,847; 0,853] | 0,855 [0,853; 0,858] | +0,006 |
| ROC-AUC de test, CatBoost (c) + prerrequisitos | 0,851 [0,849; 0,854] | 0,859 [0,856; 0,861] | +0,007 |
| ΔAP de test pareado, CatBoost (c) + prerrequisitos − CatBoost (b) + curso | 0,003 [0,002; 0,004] | 0,004 [0,003; 0,005] | +0,001 |
| ΔAP de test pareado, CatBoost (d') (c) + embeddings GraphSAGE − CatBoost (c) + prerrequisitos | 0,002 [0,001; 0,003] | -0,004 [-0,006; -0,003] | -0,006 |
| ΔAP de test pareado, Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) − Red extremo a extremo, atributos del curso sin grafo | 0,000 [-0,001; 0,002] | -0,008 [-0,009; -0,007] | -0,008 |

Mejor CatBoost en valid: CatBoost (d) + docente → CatBoost (d) + docente.

**Qué cambia en las conclusiones.** (i) La conclusión sobre el grafo se **refuerza**: con las variables corregidas los embeddings GraphSAGE empeoran el AP de CatBoost (c) en 0,004 y la red con grafo queda 0,008 por debajo de la misma red sin aristas (antes la diferencia era 0 ± 0,001), es decir, el grafo no solo no aporta sino que perjudica. (ii) Los prerrequisitos explícitos siguen aportando una milésima (0,004 [0,003; 0,005]). (iii) El historial de sección o docente sube de +0,022 a +0,028 de AP. (iv) El mejor CatBoost en valid sigue siendo (d). (v) La línea base baja (AP 0,383 a 0,359) porque la tasa de test baja, y los modelos de aprendizaje mantienen su nivel, de modo que su ventaja sobre la línea base aumenta.

## Resumen

- **Tarea.** Para cada intento evaluado de un estudiante de pregrado en un período regular 2015-2025, ¿reprobará el curso (nota < 4,0)? Momento de predicción: antes de que comience el período, con historia estrictamente anterior más lo conocido en la inscripción. Unidades: 515.891 intentos de train (2015-2020), 208.234 de valid (2021-2022), 228.752 de test (2023-2024, 14,4 % de reprobación) y 107.234 de 2025 como control posterior.
- **Hallazgo de datos que cambió el benchmark.** En los períodos **201920 y 202010** no hay reprobaciones registradas (0,000 de las notas < 4,0 frente a 14-19 % en los períodos vecinos). Incluirlos como unidades hacía que todos los modelos predijeran la mitad del riesgo real en test y dejaba a CatBoost al nivel de la línea base (corrida inicial descartada, §11b). Se excluyen como unidades y de las estadísticas de aprobación (los créditos y prerrequisitos aprobados sí cuentan). La DAI confirmó el motivo: en pandemia la reprobación no contaba como oportunidad y no se registró (P58, instancia única).
- **Resultado principal (test).** La tasa histórica expansiva del curso discrimina con AP 0,359 (ROC-AUC 0,755). El desempeño del estudiante y la carga solos aportan poco (CatBoost (a): AP 0,432); la estadística del curso es lo que más aporta: CatBoost (b) llega a AP 0,530 y ROC-AUC 0,855. Con el historial de sección/docente (ablación, 2016+) sube a 0,562.
- **¿Aporta el grafo curricular?** **Casi nada.** Los prerrequisitos explícitos (c − b) cambian el AP de test en 0,004 [0,003; 0,005] con CatBoost y en 0,004 [0,003; 0,005] con logística (en valid, con CatBoost, 0,001 [-0,001; 0,002]). Los embeddings GraphSAGE autosupervisados (d′ − c) cambian el AP en -0,004 [-0,006; -0,003]. La red extremo a extremo con GraphSAGE no supera a la misma red con los mismos atributos del curso sin aristas (-0,008 [-0,009; -0,007]) ni a la red sin representación del curso (0,001 [-0,001; 0,002]), y queda por debajo de CatBoost (c) (-0,018 [-0,021; -0,015]). Las diferencias son del orden de 0,005 de AP o menores, comparables a la variación entre semillas (0,002-0,009) y de signo cambiante entre particiones.
- **Ranking de cursos dentro de (estudiante, período).** El orden al azar da Recall@1 0,188; la línea base 0,342; CatBoost (c) 0,368 y con docente 0,395. Los modelos sin estadística del curso (a) ordenan casi como el azar (0,233), porque dentro de un mismo estudiante solo el curso distingue los riesgos.
- **Calibración y estabilidad.** Los modelos de árboles quedan razonablemente calibrados (ECE 0,031 en test) pero subestiman el riesgo en conjunto (riesgo medio ≈ 0,114 frente a 0,144 observado), porque se detienen con valid, cuyo nivel (13,4 %, docencia remota) es menor que el de test. La tasa de reprobación no es estacionaria (11,4 % en 202020 y 202110; de 12,3 % a 18,1 % desde 2023).
- **Equidad (descriptiva).** Las mujeres reprueban menos (13,4 % frente a 17,7 % en test) y los modelos las ubican con menor riesgo; el AP es algo menor en mujeres con todos los modelos; `sexo` nunca es variable del modelo.
- **Costo.** El benchmark completo (14 modelos, 3 semillas, bootstrap) tarda 3739 s; las redes se entrenan en 11-16 s en la RTX 4060 (pico de 317 MB de GPU); el pico de RAM del proceso es 4155 MB.
- **Estadística reciente (P55).** Calcular las estadísticas del curso con decaimiento exponencial (vida media de 2 años) o con una ventana de 3 años mejora el AP de test de CatBoost (c) en 0,011 [0,010; 0,013] y 0,011 [0,009; 0,013]; los dos intervalos **excluyen 0** y las dos variantes no se distinguen entre sí (-0,000 [-0,002; 0,001]). Por la regla fijada (cambiar el defecto solo si el intervalo excluye 0), la variante reciente **debe reemplazar** a la historia expansiva; el cambio del modelo por defecto queda pendiente de confirmación (§12c).
- **Bandas de nota (P84) y pronósticos agregados (P74).** Con la escala institucional (reprobado < 4,0; Aprobado por Unanimidad 4,0–5,3; con Distinción 5,4–6,3; con Máxima Distinción 6,4–7,0) un CatBoost multiclase reduce el log-loss de test de 1,346 (frecuencia de train) a 1,027 y el AP macro de 0,250 a 0,539 (§12b). Los porcentajes esperados por programa y facultad ordenan bien los grupos (ρ de Spearman de 0,84 a 0,93 en test) y se equivocan menos que la frecuencia global en reprobados, unanimidad y máxima distinción, pero **más en la banda de distinción**.
- **Recomendación.** Conservar **CatBoost con el conjunto (b) o (c)** como modelo técnico de T2 (el grafo explícito no justifica su costo de mantenimiento) y, por P55, calcular sus estadísticas de curso con decaimiento o ventana; no adoptar GraphSAGE para T2. El contexto docente es el escalón que más aporta pero exige revisión institucional antes de cualquier uso. Las predicciones individuales siguen sin estar aprobadas.


## 1. Definición de la tarea

**T2, «aprobación por intento».** Dado un estudiante de pregrado y un curso que cursa en el período regular `p`, ¿reprueba ese intento? El evento de interés de las métricas es la **reprobación** (nota < 4,0); se informa también la vista de **aprobación** (AP con el evento complementario). La pregunta de investigación es doble: (i) qué tan bien se puede anticipar la reprobación con lo conocido al inicio del período y (ii) si el **grafo curricular** (prerrequisitos) aporta señal, de forma explícita (variables de prerrequisitos) o aprendida (GraphSAGE).

| Elemento | Definición |
|---|---|
| Unidad | Un **intento evaluado**: fila de `intento_asignatura` con `es_intento_evaluado` verdadero (nota numérica; no convalidación, no nota heredada, no renuncia, no en curso; RA17) de un **período regular** (sufijo `10`/`20`) de un episodio de **pregrado** (`id_nivel` 1, sin admisiones `IN`, `PE`, `IE`; misma población que T1) con código de asignatura y en o después del semestre de admisión. Si la misma persona tiene dos filas del mismo curso y período, ambas son intentos (P54). |
| Ventana | Períodos 2015-10 a 2025-20. `202610` y `202620` están en curso y quedan fuera. Los estados anteriores a 2015 están incompletos (P49/P50): no hay filas de entrenamiento anteriores a 2015, pero la **historia de notas** anterior sí se usa como pasado (estadística del curso y atributos de nodo). |
| Evento | `y = 1` si nota < 4,0 (reprobación); `4,0` aprueba (RA12). |
| Momento de predicción | Justo antes de que comience `p`: la matrícula ya está hecha. Solo se usan hechos con período **estrictamente anterior** a `p` más lo conocido en la inscripción: el curso, su número de oportunidad, el conjunto de cursos que el estudiante toma en `p` (carga) y la sección. |
| Particiones | **Por período del intento**: train 2015-10 a 2020-20, valid 2021-10 a 2022-20, test 2023-10 a 2024-20, y 2025 como control «posterior». Una misma persona puede estar en varias particiones (validación temporal): es legítimo porque todas las variables son estrictamente pasadas; los intervalos remuestrean (persona, período) para no tratar como independientes los cursos de un mismo semestre. |
| Pandemia | Los períodos 2020-10, 2020-20 (train) y 2021-10, 2021-20 (valid) corresponden a la docencia remota; su tasa de reprobación difiere de la de otros años (§2). Valid se usa para detener el entrenamiento, de modo que su nivel no es comparable con test; la comparación válida es la de test. |

### Variables (resumen; lista completa en `pipelines/snapshots/features_t2.py`)

| Bloque | Variables |
|---|---|
| Estudiante (al cierre de `p−1`) | promedio evaluado acumulado y su `n`, créditos aprobados acumulados (primera aprobación de cada curso, convalidaciones incluidas), tasa de aprobación acumulada por intento, reprobaciones previas, intentos acumulados, semestre `k` (calendario regular desde la admisión), interrupciones, semestres matriculados, perfil de ingreso (percentiles por año, vía, colegio, sede; misma normalización que T1), historial de **este** curso (intentos previos, mejor nota previa, aprobado antes), `oportunidad` |
| Carga en `p` | número de cursos, créditos y número de cursos repetidos que toma en `p` |
| Curso | créditos, semestre en la malla, desfase `k − semestre de malla` («adelantado/atrasado»), formación y departamento, tasa de aprobación histórica del curso (expansiva, estrictamente pasada), `n` de esa historia, promedio histórico, tasa suavizada hacia la tasa global, tasa del curso en el programa, promedio de las tasas de la carga |
| Prerrequisitos (explícitos) | por (programa, catálogo) del estudiante: número de prerrequisitos, cuántos aprobó antes de `p`, cuántos por convalidación, cuántos reprobó y no ha aprobado, cuántos cursa en `p`, nota mínima y media de los prerrequisitos; banderas `en_malla`, `malla_conocida` e `info_prereq` (cobertura) |
| Docente (ablación) | tasa de aprobación histórica de la sección/docente y del docente en ese curso (expansiva, suavizada hacia la tasa del curso), solo donde la oferta cubre la sección (2016+). `docente_key` no se guarda en el snapshot ni se informa individualmente |
| Nunca variable | `sexo` (solo `sexo_equidad` para la evaluación de equidad, M1), la nota y la etiqueta |

### Decisiones conservadoras de la definición

1. **Períodos sin reprobaciones (201920, 202010).** No son unidades ni alimentan las estadísticas de aprobación (curso, estudiante, docente). Sí cuentan para créditos aprobados y prerrequisitos aprobados, porque el curso fue aprobado (P58). 202020 y 202110, con 11,4 % de reprobación, se conservan.
2. **Carga del período.** Se calcula con los intentos evaluados del período; las renuncias solo existen desde 202510 (RA19), de modo que antes de 2025 un ramo inscrito y luego renunciado no figura (P53).
3. **Historia del curso con toda la población.** La tasa histórica del curso usa todos los intentos evaluados anteriores al período (también de estudiantes de intercambio, planes especiales y períodos de verano/invierno), incluidos los anteriores a 2015 (≈ 70.000-85.000 intentos por año). No hay fuga: solo mira períodos anteriores.
4. **Suavizado.** Las tasas del curso, del curso por programa y del docente se suavizan hacia la tasa global (o del curso) con 10 pseudo-observaciones; se informan además la tasa cruda y su `n`.
5. **Intentos duplicados.** Hay 11.748 pares (persona, período, asignatura) con más de una fila (≈ 1 %); cada fila es una observación (P54).
6. **Estudiante = episodio.** Los acumulados del estudiante se calculan por episodio (programa); el historial de **un** curso (intentos previos, aprobado antes, prerrequisitos) se calcula por persona, para no perder lo aprobado en un episodio anterior.


## 2. Población, embudo y tasas base

### Embudo de intentos

| Paso | Intentos |
|---|---|
| intentos evaluados (nota numerica) | 2.515.519 |
| ... en periodo regular (10/20) | 2.503.731 |
| ... en 2015-2025 (periodos cerrados) | 1.153.246 |
| ... sin los periodos de reprobacion no registrada (201920, 202010) | 1.065.346 |
| ... de un episodio de pregrado (sin IN/PE/IE, con episodio) | 1.060.115 |
| ... en o despues del semestre de admision y con codigo de asignatura | 1.060.111 |

### Particiones y tasas base

| Partición | Períodos | Intentos | Reprobados | Tasa de reprobación | Personas | Cursos | Grupos (persona, período) |
|---|---|---|---|---|---|---|---|
| train | 2015-10 a 2020-20 | 515.891 | 84.495 | 16.4 % | 19.454 | 3.874 | 94.659 |
| valid | 2021-10 a 2022-20 | 208.234 | 27.968 | 13.4 % | 12.349 | 2.642 | 38.111 |
| test | 2023-10 a 2024-20 | 228.752 | 32.866 | 14.4 % | 12.779 | 2.514 | 39.051 |
| posterior | 2025-10 a 2025-20 | 107.234 | 18.441 | 17.2 % | 10.957 | 2.262 | 20.856 |

Tasa de reprobación por período (todas las particiones):

| Período | Intentos | Tasa de reprobación |
|---|---|---|
| 201510 | 42.886 | 18.2 % |
| 201520 | 41.146 | 17.2 % |
| 201610 | 52.374 | 18.6 % |
| 201620 | 42.961 | 19.3 % |
| 201710 | 81.472 | 12.7 % |
| 201720 | 43.766 | 20.9 % |
| 201810 | 64.331 | 13.1 % |
| 201820 | 45.980 | 18.5 % |
| 201910 | 51.994 | 18.4 % |
| 202020 | 48.981 | 11.4 % |
| 202110 | 53.863 | 11.4 % |
| 202120 | 46.739 | 14.2 % |
| 202210 | 65.374 | 13.5 % |
| 202220 | 42.258 | 15.2 % |
| 202310 | 74.412 | 12.3 % |
| 202320 | 52.346 | 13.7 % |
| 202410 | 55.603 | 15.9 % |
| 202420 | 46.391 | 16.6 % |
| 202510 | 58.159 | 16.4 % |
| 202520 | 49.075 | 18.1 % |

Por número de oportunidad (intentos y tasa de reprobación):

| Partición | Oportunidad 1 | Oportunidad 2 | Oportunidad 3+ |
|---|---|---|---|
| train | 459.910 (14.2 %) | 44.564 (33.5 %) | 11.417 (37.4 %) |
| valid | 190.848 (10.8 %) | 14.167 (40.9 %) | 3.219 (48.4 %) |
| test | 205.052 (11.8 %) | 17.641 (34.4 %) | 6.059 (42.5 %) |
| posterior | 95.368 (14.0 %) | 8.473 (38.4 %) | 3.393 (53.3 %) |

### Cobertura de las variables del grafo y del docente

| Cobertura (fracción de intentos) | train | valid | test | posterior |
|---|---|---|---|---|
| Curso en la malla oficial del estudiante (programa + catálogo) | 98,5 % | 98,9 % | 98,6 % | 98,9 % |
| Programa + catálogo presente en la malla | 100,0 % | 100,0 % | 100,0 % | 100,0 % |
| Con información de prerrequisitos (curso en malla y catálogo con aristas) | 98,5 % | 98,9 % | 98,6 % | 98,9 % |
| Curso con al menos un prerrequisito (sobre todas las filas) | 60,1 % | 62,1 % | 57,5 % | 59,6 % |
| Curso con al menos un prerrequisito (sobre filas con información) | 61,0 % | 62,8 % | 58,3 % | 60,3 % |
| Sección con docente en la oferta (2016+) | 71,3 % | 90,7 % | 84,5 % | 97,6 % |
| Curso con historia previa (n_hist_curso > 0) | 83,0 % | 89,6 % | 88,4 % | 97,0 % |
| Intento repetido (el estudiante ya cursó el curso) | 10,0 % | 8,4 % | 9,6 % | 11,5 % |
| Oportunidad > 1 (campo de la fuente) | 10,9 % | 8,3 % | 10,4 % | 11,1 % |

La malla oficial (programa + catálogo) contiene el 98,6 % de los intentos de test; el 1,4 % restante no tiene semestre de malla ni prerrequisitos (variables en NULL con bandera). Esta cobertura es mayor que la de ≈ 77 % de R35 porque aquí la población se restringe a períodos regulares desde 2015 y a pregrado, y se une por el programa del episodio y el catálogo de la propia fila (P57). Entre el 58 % y el 62 % de los intentos son de cursos con al menos un prerrequisito: el grafo explícito solo puede informar sobre esa parte. La cobertura de docente crece con los años (70 % en train porque 2015 no tiene oferta; 98 % en 2025).

## 3. Snapshot point-in-time (migración 012, `python -m pipelines.snapshots.t2`)

- **Una fila por intento** (`neural_mart.snapshot_t2`, ~1,16 millones de filas, tipos compactos `real`/`smallint`; no se particiona: un solo `COPY` en una transacción, ~3 min). Claves seudónimas (`persona_key`, `episodio_id`, `intento_id`); sin RUT ni nombres.
- **Mecanismo anti-fuga.** Toda variable histórica sale de una tabla acumulada inclusiva por (clave, período) consultada con `merge_asof(..., allow_exact_matches=False)`: devuelve el último acumulado de un período **estrictamente anterior** al del intento. Vale igual para la estadística del curso, del curso por programa, del estudiante (episodio), del par estudiante-curso (intentos previos y prerrequisitos) y del docente.
- **Pruebas** (`tests/unit/test_snapshot_t2.py`, 17 casos): (i) lo que ocurre en el mismo período no es historia; (ii) la historia del curso incluye intentos de personas fuera de la población (intercambio, verano/invierno); (iii) estado de los prerrequisitos antes de `p`, aprobación por convalidación y prerrequisito cursado en el mismo período; (iv) banderas de cobertura; (v) historia del docente estrictamente pasada; (vi) **perturbación**: se reasignan al azar todas las notas de los períodos `>= P` y se comprueba que **todas** las variables de las filas con período `<= P` quedan idénticas (para tres valores de `P`); (vii) **borrado**: eliminar los períodos posteriores a `P` no cambia las variables de las filas anteriores. Verificado también que las pruebas fallan si se permite la coincidencia exacta de período (mutación).
- **Verificación independiente en la base** (`tests/integration/test_snapshot_t2.py`): períodos regulares dentro de la ventana, partición coherente con el período, etiqueta igual a «nota < 4,0» de un intento evaluado, `k` coherente con la admisión, y recálculo SQL de `n_hist_curso`, `tasa_hist_curso`, `n_intentos_acum`, `n_reprob_acum` y `n_prereq` sobre una muestra.
- **Normalizadores ajustados solo con train** (`models/t2_data.py::PreprocesadorT2`): medianas, medias, desvíos y vocabularios; indicadores de faltante. Pruebas de que no se ajustan con valid/test y de que `sexo_equidad`, la etiqueta o la llave de persona no pueden entrar como variables.

## 4. Protocolo de modelado

| Elemento | Detalle |
|---|---|
| Línea base | `1 − tasa histórica suavizada del curso` (expansiva, estrictamente pasada; suavizada hacia la tasa global con 10 pseudo-observaciones). |
| Conjuntos | (a) estudiante + carga; (b) + estadística del curso; (c) + prerrequisitos explícitos; (d) + historial de sección/docente (ablación). Anidados: cada uno añade un bloque. |
| Logística | Regularizada (L2), `C` en {0,0003; 0,001; 0,003; 0,01; 0,03; 0,3} elegido por AP en valid, sin `class_weight` (T1: pesos balanceados descalibran). |
| CatBoost | Categóricas nativas, parada temprana por pérdida logarítmica en valid, 3 semillas promediadas (profundidad 6, tasa 0,08, L2 = 5, hasta 2.000 iteraciones). Controles adicionales: (c) + identidad del curso como categórica (`cb_c_id`) y (d′) (c) + embeddings del grafo (`cb_cemb`). |
| Grafo de cursos | Nodos = códigos de asignatura (globales, de las filas, la malla y los prerrequisitos). Relaciones: *previo* (media de los prerrequisitos), *posterior* (media de los cursos que lo requieren) y *coinscripción* (cursos tomados juntos por ≥ 30 pares estudiante-período **solo de train**). Atributos de nodo sin resultados del periodo modelado: créditos, estadística del semestre en la malla, grados, departamento y formación, y **tasa de aprobación del curso anterior a 2015** (ningún período de train puede filtrarse en ella). Se descartó usar la tasa de aprobación de los períodos de train como atributo de nodo porque cada fila de train contribuiría a su propio atributo (fuga de la etiqueta); la tasa histórica por período ya entra como variable puntual. |
| GraphSAGE | Escrito en torch (agregador de media, un peso por relación, 2 capas, 64 → 32 dimensiones); sin `torch_geometric`. **Autosupervisado:** predicción de enlaces sobre las aristas de prerrequisito (10 % retenido, negativos al azar), embeddings con paso de mensajes sobre todas las aristas → entran a CatBoost (d′). **Supervisado:** `RedT2` entrena el codificador de grafo extremo a extremo junto con el MLP del estudiante (variables del conjunto (c) + embeddings de categorías) y la cabeza de reprobación. |
| Red extremo a extremo | Entrada = conjunto (c) estandarizado + embeddings de categorías + representación del curso: `nn_gnn` (GraphSAGE con prerrequisitos y coinscripción), `nn_gnn_prereq` (solo prerrequisitos), `nn_mlp` (los mismos atributos de nodo **sin** aristas) y `nn_ninguno` (sin representación del curso). Adam, lote 4.096, pérdida logística sin re-ponderar, parada temprana por AP en valid (paciencia 4), 3 semillas promediadas, GPU. |
| GAT | No se implementó (opcional en el encargo): ver §13. |
| Métricas | AP (evento reprobación y evento aprobación), ROC-AUC, Brier, ECE (deciles de igual tamaño), y por grupo (estudiante, período): Recall@K y Precision@K con K = 1, 2 sobre los grupos con ≥ 2 cursos y ≥ 1 reprobación (los empates se rompen con una clave aleatoria con semilla). |
| IC y diferencias pareadas | Bootstrap **por grupos (estudiante, período)**, 1.000 remuestreos (300 en 2025), los mismos remuestreos para todos los modelos; AP y ROC-AUC ponderados exactamente (coinciden con `sklearn` con `sample_weight`, probado). |

## 5. Resultados

Intervalos del 95 % por bootstrap de (estudiante, período) con 1.000 remuestreos compartidos entre modelos. El ajuste, la elección de `C` y la parada temprana usan solo train y valid; test no interviene en ninguna decisión.

### 5.1 Test (2023-2024), configuración oficial

| Modelo | AP reprobación | AP aprobación | ROC-AUC | Brier | ECE |
|---|---|---|---|---|---|
| Tasa histórica del curso (expansiva) | 0.359 [0.353; 0.365] | 0.942 [0.941; 0.944] | 0.755 [0.751; 0.758] | 0.1078 [0.1065; 0.1092] | 0.027 [0.026; 0.029] |
| Logística (a) estudiante + carga | 0.412 [0.404; 0.420] | 0.956 [0.954; 0.957] | 0.796 [0.793; 0.800] | 0.1046 [0.1032; 0.1061] | 0.027 [0.025; 0.029] |
| Logística (b) + curso | 0.495 [0.487; 0.503] | 0.968 [0.967; 0.969] | 0.846 [0.843; 0.849] | 0.1000 [0.0986; 0.1016] | 0.052 [0.050; 0.053] |
| Logística (c) + prerrequisitos | 0.499 [0.491; 0.507] | 0.968 [0.967; 0.969] | 0.848 [0.845; 0.851] | 0.0984 [0.0970; 0.0999] | 0.045 [0.043; 0.047] |
| Logística (d) + docente | 0.530 [0.523; 0.538] | 0.971 [0.970; 0.972] | 0.861 [0.858; 0.864] | 0.0999 [0.0985; 0.1014] | 0.064 [0.062; 0.066] |
| CatBoost (a) estudiante + carga | 0.432 [0.425; 0.440] | 0.959 [0.958; 0.960] | 0.808 [0.805; 0.812] | 0.1015 [0.1001; 0.1030] | 0.015 [0.013; 0.017] |
| CatBoost (b) + curso | 0.530 [0.523; 0.538] | 0.970 [0.969; 0.971] | 0.855 [0.853; 0.858] | 0.0936 [0.0922; 0.0950] | 0.034 [0.033; 0.036] |
| CatBoost (c) + prerrequisitos | 0.534 [0.527; 0.541] | 0.971 [0.970; 0.972] | 0.859 [0.856; 0.861] | 0.0924 [0.0910; 0.0938] | 0.031 [0.029; 0.032] |
| CatBoost (d) + docente | 0.562 [0.555; 0.569] | 0.974 [0.973; 0.975] | 0.873 [0.871; 0.876] | 0.0895 [0.0882; 0.0909] | 0.032 [0.030; 0.033] |
| CatBoost (c) + identidad del curso | 0.487 [0.480; 0.494] | 0.966 [0.965; 0.967] | 0.839 [0.836; 0.842] | 0.0979 [0.0964; 0.0993] | 0.037 [0.036; 0.039] |
| CatBoost (d') (c) + embeddings GraphSAGE | 0.529 [0.522; 0.537] | 0.971 [0.970; 0.972] | 0.858 [0.856; 0.861] | 0.0929 [0.0916; 0.0943] | 0.032 [0.030; 0.033] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0.516 [0.509; 0.524] | 0.970 [0.969; 0.971] | 0.854 [0.852; 0.857] | 0.1005 [0.0990; 0.1020] | 0.066 [0.064; 0.068] |
| Red extremo a extremo, GraphSAGE (solo prerreq.) | 0.530 [0.522; 0.537] | 0.971 [0.970; 0.972] | 0.860 [0.857; 0.862] | 0.0972 [0.0957; 0.0987] | 0.057 [0.055; 0.058] |
| Red extremo a extremo, atributos del curso sin grafo | 0.524 [0.517; 0.532] | 0.971 [0.970; 0.972] | 0.858 [0.855; 0.861] | 0.0970 [0.0955; 0.0985] | 0.055 [0.053; 0.057] |
| Red extremo a extremo, sin representación del curso | 0.515 [0.508; 0.523] | 0.969 [0.968; 0.970] | 0.852 [0.849; 0.855] | 0.0975 [0.0960; 0.0990] | 0.052 [0.051; 0.054] |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 0.545 [0.538; 0.552] | 0.972 [0.971; 0.973] | 0.863 [0.861; 0.866] | 0.0910 [0.0896; 0.0923] | 0.028 [0.026; 0.030] |
| CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0.545 [0.538; 0.553] | 0.972 [0.971; 0.973] | 0.865 [0.863; 0.868] | 0.0910 [0.0896; 0.0923] | 0.029 [0.027; 0.031] |

Lectura: (i) la logística y CatBoost con la estadística del curso superan con claridad a la tasa histórica (CatBoost (b) − línea base: ΔAP 0,171 [0,165; 0,177]); (ii) CatBoost supera a la logística con el mismo conjunto ((c): ΔAP 0,035 [0,031; 0,039]); (iii) la red extremo a extremo queda entre ambos (0,530 con GraphSAGE de prerrequisitos). Sin las variables del curso, (a) casi no mejora a la línea base: lo que predice la reprobación es qué curso se cursa y cómo le ha ido al estudiante, no la carga ni el perfil de ingreso por sí solos.

### 5.2 Validación (2021-2022)

| Modelo | AP reprobación | AP aprobación | ROC-AUC | Brier | ECE |
|---|---|---|---|---|---|
| Tasa histórica del curso (expansiva) | 0.352 [0.345; 0.359] | 0.948 [0.946; 0.949] | 0.760 [0.756; 0.764] | 0.1026 [0.1013; 0.1041] | 0.025 [0.023; 0.027] |
| Logística (a) estudiante + carga | 0.410 [0.401; 0.420] | 0.959 [0.957; 0.960] | 0.794 [0.790; 0.798] | 0.0975 [0.0960; 0.0991] | 0.009 [0.007; 0.011] |
| Logística (b) + curso | 0.474 [0.464; 0.484] | 0.969 [0.968; 0.970] | 0.840 [0.836; 0.843] | 0.0914 [0.0900; 0.0930] | 0.021 [0.019; 0.023] |
| Logística (c) + prerrequisitos | 0.474 [0.465; 0.484] | 0.969 [0.968; 0.970] | 0.840 [0.837; 0.843] | 0.0912 [0.0898; 0.0928] | 0.019 [0.017; 0.021] |
| Logística (d) + docente | 0.482 [0.473; 0.491] | 0.970 [0.969; 0.971] | 0.844 [0.841; 0.847] | 0.0920 [0.0905; 0.0936] | 0.034 [0.032; 0.036] |
| CatBoost (a) estudiante + carga | 0.424 [0.415; 0.433] | 0.960 [0.959; 0.962] | 0.805 [0.801; 0.808] | 0.0959 [0.0944; 0.0974] | 0.006 [0.005; 0.008] |
| CatBoost (b) + curso | 0.493 [0.485; 0.502] | 0.970 [0.969; 0.971] | 0.847 [0.844; 0.850] | 0.0891 [0.0877; 0.0906] | 0.015 [0.014; 0.017] |
| CatBoost (c) + prerrequisitos | 0.493 [0.485; 0.502] | 0.971 [0.970; 0.972] | 0.849 [0.846; 0.852] | 0.0889 [0.0875; 0.0904] | 0.013 [0.012; 0.015] |
| CatBoost (d) + docente | 0.510 [0.502; 0.519] | 0.973 [0.972; 0.974] | 0.857 [0.854; 0.860] | 0.0874 [0.0861; 0.0889] | 0.017 [0.015; 0.019] |
| CatBoost (c) + identidad del curso | 0.487 [0.479; 0.496] | 0.969 [0.968; 0.970] | 0.846 [0.842; 0.849] | 0.0895 [0.0881; 0.0910] | 0.016 [0.014; 0.018] |
| CatBoost (d') (c) + embeddings GraphSAGE | 0.499 [0.491; 0.507] | 0.971 [0.970; 0.972] | 0.851 [0.848; 0.854] | 0.0883 [0.0869; 0.0898] | 0.014 [0.012; 0.015] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0.492 [0.484; 0.502] | 0.971 [0.970; 0.972] | 0.850 [0.847; 0.854] | 0.0905 [0.0890; 0.0921] | 0.036 [0.034; 0.038] |
| Red extremo a extremo, GraphSAGE (solo prerreq.) | 0.492 [0.484; 0.501] | 0.971 [0.970; 0.972] | 0.851 [0.848; 0.854] | 0.0897 [0.0883; 0.0913] | 0.029 [0.028; 0.031] |
| Red extremo a extremo, atributos del curso sin grafo | 0.493 [0.484; 0.502] | 0.971 [0.970; 0.972] | 0.851 [0.847; 0.854] | 0.0894 [0.0880; 0.0910] | 0.027 [0.025; 0.029] |
| Red extremo a extremo, sin representación del curso | 0.497 [0.488; 0.506] | 0.971 [0.970; 0.972] | 0.851 [0.847; 0.854] | 0.0892 [0.0878; 0.0907] | 0.027 [0.025; 0.028] |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 0.502 [0.494; 0.512] | 0.971 [0.970; 0.972] | 0.851 [0.848; 0.854] | 0.0883 [0.0869; 0.0898] | 0.018 [0.016; 0.020] |
| CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0.492 [0.484; 0.501] | 0.970 [0.969; 0.971] | 0.846 [0.843; 0.849] | 0.0897 [0.0883; 0.0912] | 0.023 [0.022; 0.025] |

El orden de los modelos es el mismo que en test. Valid se usa para parar el entrenamiento y es el período de docencia remota (13,7 % de reprobación), de modo que su nivel no es comparable con el de test.

### 5.3 2025 (control posterior, nunca usado para decisiones)

| Modelo | AP reprobación | AP aprobación | ROC-AUC | Brier | ECE |
|---|---|---|---|---|---|
| Tasa histórica del curso (expansiva) | 0.424 [0.416; 0.433] | 0.944 [0.942; 0.946] | 0.794 [0.790; 0.799] | 0.1194 [0.1175; 0.1214] | 0.028 [0.025; 0.031] |
| Logística (a) estudiante + carga | 0.464 [0.452; 0.476] | 0.945 [0.943; 0.947] | 0.792 [0.788; 0.797] | 0.1207 [0.1184; 0.1231] | 0.048 [0.045; 0.050] |
| Logística (b) + curso | 0.560 [0.547; 0.573] | 0.964 [0.962; 0.965] | 0.856 [0.853; 0.860] | 0.1160 [0.1137; 0.1183] | 0.077 [0.074; 0.080] |
| Logística (c) + prerrequisitos | 0.561 [0.549; 0.574] | 0.964 [0.963; 0.965] | 0.858 [0.855; 0.861] | 0.1132 [0.1110; 0.1154] | 0.069 [0.066; 0.072] |
| Logística (d) + docente | 0.581 [0.571; 0.592] | 0.966 [0.964; 0.967] | 0.864 [0.861; 0.868] | 0.1178 [0.1156; 0.1202] | 0.090 [0.087; 0.093] |
| CatBoost (a) estudiante + carga | 0.490 [0.479; 0.501] | 0.951 [0.950; 0.953] | 0.813 [0.809; 0.817] | 0.1148 [0.1126; 0.1169] | 0.028 [0.025; 0.031] |
| CatBoost (b) + curso | 0.589 [0.579; 0.599] | 0.966 [0.965; 0.967] | 0.864 [0.861; 0.868] | 0.1055 [0.1035; 0.1075] | 0.050 [0.047; 0.052] |
| CatBoost (c) + prerrequisitos | 0.593 [0.583; 0.603] | 0.967 [0.966; 0.968] | 0.867 [0.864; 0.871] | 0.1037 [0.1018; 0.1057] | 0.044 [0.042; 0.047] |
| CatBoost (d) + docente | 0.615 [0.605; 0.625] | 0.969 [0.968; 0.970] | 0.876 [0.873; 0.879] | 0.1012 [0.0993; 0.1032] | 0.043 [0.041; 0.046] |
| CatBoost (c) + identidad del curso | 0.536 [0.526; 0.546] | 0.961 [0.959; 0.962] | 0.843 [0.839; 0.847] | 0.1124 [0.1103; 0.1146] | 0.055 [0.053; 0.058] |
| CatBoost (d') (c) + embeddings GraphSAGE | 0.584 [0.574; 0.593] | 0.967 [0.966; 0.968] | 0.866 [0.863; 0.870] | 0.1051 [0.1031; 0.1070] | 0.046 [0.044; 0.049] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0.559 [0.548; 0.569] | 0.964 [0.963; 0.966] | 0.855 [0.852; 0.859] | 0.1214 [0.1189; 0.1238] | 0.097 [0.095; 0.100] |
| Red extremo a extremo, GraphSAGE (solo prerreq.) | 0.572 [0.561; 0.583] | 0.966 [0.965; 0.967] | 0.861 [0.858; 0.865] | 0.1164 [0.1141; 0.1187] | 0.087 [0.084; 0.089] |
| Red extremo a extremo, atributos del curso sin grafo | 0.566 [0.555; 0.576] | 0.966 [0.965; 0.967] | 0.860 [0.857; 0.864] | 0.1168 [0.1144; 0.1191] | 0.087 [0.084; 0.090] |
| Red extremo a extremo, sin representación del curso | 0.564 [0.554; 0.575] | 0.965 [0.963; 0.966] | 0.857 [0.853; 0.861] | 0.1155 [0.1131; 0.1177] | 0.082 [0.079; 0.085] |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 0.601 [0.592; 0.611] | 0.968 [0.967; 0.969] | 0.871 [0.868; 0.874] | 0.1020 [0.1001; 0.1039] | 0.041 [0.038; 0.043] |
| CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0.602 [0.592; 0.612] | 0.968 [0.967; 0.969] | 0.872 [0.869; 0.875] | 0.1014 [0.0996; 0.1033] | 0.038 [0.036; 0.041] |

El AP sube en 2025 (la tasa base sube a 17,2 %) y el orden de los modelos se mantiene. La calibración se degrada un poco (ECE de CatBoost (c): 0,044). Bootstrap de 300 remuestreos.

### 5.4 Variación entre semillas de las redes

| Red (3 semillas) | AP valid (media ± sd) | AP test (media ± sd) | Épocas óptimas | Tiempo total (s) |
|---|---|---|---|---|
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0.488 ± 0.004 | 0.511 ± 0.008 | [1.9047619047619047, 1.5873015873015872, 1.5873015873015872] | 20 |
| Red extremo a extremo, GraphSAGE (solo prerreq.) | 0.488 ± 0.003 | 0.523 ± 0.005 | [1.9047619047619047, 1.5873015873015872, 1.5873015873015872] | 18 |
| Red extremo a extremo, atributos del curso sin grafo | 0.488 ± 0.006 | 0.518 ± 0.001 | [1.9047619047619047, 1.9047619047619047, 1.5873015873015872] | 15 |
| Red extremo a extremo, sin representación del curso | 0.492 ± 0.003 | 0.509 ± 0.005 | [1.9047619047619047, 1.9047619047619047, 1.5873015873015872] | 11 |

La desviación entre semillas (0,002-0,009 de AP) es del mismo orden que las diferencias entre variantes de la red; por eso las variantes no se distinguen entre sí con claridad (§7). Las épocas óptimas varían entre 0,3 y 3,1: con la evaluación en valid cada 40 pasos el modelo se detiene temprano, lo que refleja el cambio de nivel entre train y valid más que un sobreajuste clásico.

## 6. Ablación: estudiante, curso, prerrequisitos, docente

Test (los mismos intentos en cada escalón; en (d) las variables de docente están en NULL donde la oferta no cubre la sección):

| Escalón | Logística AP | CatBoost AP | Logística ROC-AUC | CatBoost ROC-AUC | CatBoost Recall@1 |
|---|---|---|---|---|---|
| 0. Tasa histórica del curso | 0.359 [0.353; 0.365] | 0.359 [0.353; 0.365] | 0.755 [0.751; 0.758] | 0.755 [0.751; 0.758] | 0.342 [0.336; 0.348] |
| a. Estudiante + carga | 0.412 [0.404; 0.420] | 0.432 [0.425; 0.440] | 0.796 [0.793; 0.800] | 0.808 [0.805; 0.812] | 0.233 [0.228; 0.238] |
| b. + estadística del curso | 0.495 [0.487; 0.503] | 0.530 [0.523; 0.538] | 0.846 [0.843; 0.849] | 0.855 [0.853; 0.858] | 0.365 [0.359; 0.370] |
| c. + prerrequisitos explícitos | 0.499 [0.491; 0.507] | 0.534 [0.527; 0.541] | 0.848 [0.845; 0.851] | 0.859 [0.856; 0.861] | 0.368 [0.362; 0.373] |
| d. + historial de sección/docente (2016+) | 0.530 [0.523; 0.538] | 0.562 [0.555; 0.569] | 0.861 [0.858; 0.864] | 0.873 [0.871; 0.876] | 0.395 [0.389; 0.400] |

Diferencias pareadas de test (todas las comparaciones, con IC; el signo es A − B):

| Comparación (A − B, diferencia pareada) | ΔAP reprobación | ΔAP aprobación | ΔROC-AUC | ΔBrier | ΔRecall@1 |
|---|---|---|---|---|---|
| Logística (a) estudiante + carga − Tasa histórica del curso (expansiva) | 0.053 [0.045; 0.061] | 0.013 [0.012; 0.014] | 0.042 [0.037; 0.046] | -0.0032 [-0.0038; -0.0025] | -0.119 [-0.126; -0.112] |
| Logística (b) + curso − Logística (a) estudiante + carga | 0.083 [0.078; 0.088] | 0.012 [0.012; 0.013] | 0.050 [0.048; 0.052] | -0.0046 [-0.0049; -0.0042] | 0.151 [0.144; 0.158] |
| Logística (c) + prerrequisitos − Logística (b) + curso | 0.004 [0.003; 0.005] | 0.000 [0.000; 0.001] | 0.002 [0.001; 0.002] | -0.0017 [-0.0018; -0.0016] | -0.005 [-0.008; -0.001] |
| Logística (d) + docente − Logística (c) + prerrequisitos | 0.031 [0.029; 0.033] | 0.003 [0.003; 0.003] | 0.013 [0.012; 0.014] | 0.0015 [0.0013; 0.0017] | 0.020 [0.016; 0.024] |
| CatBoost (a) estudiante + carga − Tasa histórica del curso (expansiva) | 0.074 [0.065; 0.081] | 0.016 [0.015; 0.018] | 0.054 [0.049; 0.058] | -0.0063 [-0.0070; -0.0056] | -0.108 [-0.116; -0.101] |
| CatBoost (b) + curso − CatBoost (a) estudiante + carga | 0.098 [0.094; 0.102] | 0.011 [0.011; 0.012] | 0.047 [0.045; 0.049] | -0.0079 [-0.0083; -0.0076] | 0.131 [0.125; 0.138] |
| CatBoost (c) + prerrequisitos − CatBoost (b) + curso | 0.004 [0.003; 0.005] | 0.001 [0.001; 0.001] | 0.003 [0.003; 0.004] | -0.0012 [-0.0013; -0.0011] | 0.003 [-0.000; 0.006] |
| CatBoost (d) + docente − CatBoost (c) + prerrequisitos | 0.028 [0.026; 0.030] | 0.003 [0.003; 0.004] | 0.015 [0.014; 0.016] | -0.0028 [-0.0030; -0.0027] | 0.027 [0.022; 0.031] |
| CatBoost (d') (c) + embeddings GraphSAGE − CatBoost (c) + prerrequisitos | -0.004 [-0.006; -0.003] | -0.000 [-0.000; 0.000] | -0.000 [-0.001; 0.000] | 0.0005 [0.0004; 0.0007] | 0.002 [-0.001; 0.005] |
| CatBoost (c) + identidad del curso − CatBoost (c) + prerrequisitos | -0.047 [-0.049; -0.044] | -0.005 [-0.005; -0.004] | -0.020 [-0.020; -0.019] | 0.0055 [0.0053; 0.0057] | -0.032 [-0.037; -0.028] |
| CatBoost (d') (c) + embeddings GraphSAGE − CatBoost (c) + identidad del curso | 0.042 [0.040; 0.045] | 0.004 [0.004; 0.005] | 0.019 [0.018; 0.020] | -0.0050 [-0.0052; -0.0048] | 0.035 [0.030; 0.039] |
| CatBoost (b) + curso − Tasa histórica del curso (expansiva) | 0.171 [0.165; 0.177] | 0.028 [0.027; 0.029] | 0.101 [0.098; 0.104] | -0.0142 [-0.0147; -0.0137] | 0.023 [0.018; 0.028] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) − Red extremo a extremo, atributos del curso sin grafo | -0.008 [-0.009; -0.007] | -0.001 [-0.001; -0.001] | -0.004 [-0.004; -0.003] | 0.0035 [0.0034; 0.0036] | 0.004 [0.000; 0.007] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) − Red extremo a extremo, sin representación del curso | 0.001 [-0.001; 0.002] | 0.001 [0.001; 0.001] | 0.003 [0.002; 0.003] | 0.0030 [0.0029; 0.0031] | 0.000 [-0.003; 0.004] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) − Red extremo a extremo, GraphSAGE (solo prerreq.) | -0.014 [-0.015; -0.012] | -0.001 [-0.001; -0.001] | -0.005 [-0.005; -0.005] | 0.0033 [0.0032; 0.0035] | -0.005 [-0.008; -0.003] |
| Red extremo a extremo, atributos del curso sin grafo − Red extremo a extremo, sin representación del curso | 0.009 [0.008; 0.010] | 0.002 [0.001; 0.002] | 0.006 [0.006; 0.007] | -0.0005 [-0.0006; -0.0004] | -0.003 [-0.006; -0.000] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) − CatBoost (c) + prerrequisitos | -0.018 [-0.021; -0.015] | -0.001 [-0.001; -0.000] | -0.004 [-0.005; -0.003] | 0.0081 [0.0078; 0.0084] | 0.002 [-0.002; 0.006] |
| CatBoost (c) + prerrequisitos − Logística (c) + prerrequisitos | 0.035 [0.031; 0.039] | 0.003 [0.002; 0.003] | 0.011 [0.010; 0.012] | -0.0060 [-0.0063; -0.0057] | -0.001 [-0.005; 0.003] |
| CatBoost (c) + prerrequisitos − Tasa histórica del curso (expansiva) | 0.175 [0.168; 0.181] | 0.028 [0.027; 0.030] | 0.104 [0.101; 0.107] | -0.0154 [-0.0159; -0.0149] | 0.026 [0.021; 0.032] |
| Logística (b) + curso − Tasa histórica del curso (expansiva) | 0.136 [0.129; 0.143] | 0.025 [0.024; 0.027] | 0.091 [0.088; 0.094] | -0.0078 [-0.0082; -0.0073] | 0.032 [0.028; 0.037] |
| CatBoost (d) + docente − CatBoost (b) + curso | 0.032 [0.030; 0.034] | 0.004 [0.004; 0.005] | 0.018 [0.017; 0.019] | -0.0040 [-0.0042; -0.0039] | 0.030 [0.025; 0.035] |
| CatBoost (d') (c) + embeddings GraphSAGE − CatBoost (b) + curso | -0.001 [-0.002; 0.001] | 0.001 [0.001; 0.001] | 0.003 [0.002; 0.004] | -0.0007 [-0.0008; -0.0005] | 0.005 [0.002; 0.009] |
| Red extremo a extremo, GraphSAGE (solo prerreq.) − CatBoost (c) + prerrequisitos | -0.004 [-0.007; -0.001] | 0.001 [0.000; 0.001] | 0.001 [-0.000; 0.002] | 0.0048 [0.0045; 0.0051] | 0.007 [0.003; 0.012] |
| Red extremo a extremo, sin representación del curso − CatBoost (c) + prerrequisitos | -0.019 [-0.021; -0.016] | -0.001 [-0.002; -0.001] | -0.007 [-0.008; -0.005] | 0.0051 [0.0048; 0.0054] | 0.001 [-0.003; 0.006] |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) − CatBoost (c) + prerrequisitos | 0.011 [0.010; 0.013] | 0.001 [0.001; 0.001] | 0.005 [0.004; 0.005] | -0.0014 [-0.0015; -0.0013] | 0.015 [0.011; 0.018] |
| CatBoost (c) con estadísticas del curso en ventana reciente (P55) − CatBoost (c) + prerrequisitos | 0.011 [0.009; 0.013] | 0.001 [0.001; 0.002] | 0.007 [0.006; 0.007] | -0.0014 [-0.0016; -0.0012] | 0.016 [0.012; 0.020] |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) − CatBoost (c) con estadísticas del curso en ventana reciente (P55) | -0.000 [-0.002; 0.001] | -0.001 [-0.001; -0.000] | -0.002 [-0.002; -0.001] | 0.0000 [-0.0001; 0.0001] | -0.001 [-0.004; 0.002] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) − CatBoost (d) + docente | -0.046 [-0.049; -0.043] | -0.004 [-0.004; -0.004] | -0.019 [-0.020; -0.018] | 0.0110 [0.0106; 0.0113] | -0.025 [-0.030; -0.020] |
| CatBoost (d) + docente − Tasa histórica del curso (expansiva) | 0.203 [0.197; 0.209] | 0.032 [0.031; 0.033] | 0.119 [0.116; 0.122] | -0.0183 [-0.0188; -0.0178] | 0.053 [0.047; 0.059] |
| CatBoost (d) + docente − Logística (c) + prerrequisitos | 0.063 [0.059; 0.068] | 0.006 [0.006; 0.006] | 0.026 [0.024; 0.027] | -0.0088 [-0.0092; -0.0085] | 0.026 [0.021; 0.030] |

- **Curso (a a b)**: el salto grande (CatBoost, ΔAP 0,098 [0,094; 0,102]; ΔROC-AUC 0,047 [0,045; 0,049]). Las variables de mayor importancia son la tasa histórica del curso en el programa, la tasa y el promedio acumulados del estudiante y el departamento (§12).
- **Prerrequisitos explícitos (b a c)**: ΔAP 0,004 [0,003; 0,005] con CatBoost y 0,004 [0,003; 0,005] con logística en test; 0,001 [-0,001; 0,002] y 0,000 [-0,001; 0,001] en valid; 0,004 [0,003; 0,006] y 0,002 [-0,000; 0,004] en 2025. El efecto es del orden de 0,003 de AP o menor y de signo inconsistente entre particiones: **el grafo explícito no aporta señal utilizable** más allá de la estadística del curso y del desempeño del estudiante. Explicaciones posibles (hipótesis, no medidas): los prerrequisitos ya se reflejan en el promedio y las reprobaciones acumuladas del estudiante, y el 40 % de los intentos son de cursos sin prerrequisitos.
- **Docente (c a d)**: el escalón que más aporta después del curso (ΔAP 0,028 [0,026; 0,030]; ΔRecall@1 0,027 [0,022; 0,031]). Es la asociación histórica de la sección o del docente con la aprobación (heterogeneidad entre secciones), no un juicio sobre personas; la llave del docente nunca se reporta ni se guarda en el snapshot. Solo existe oferta desde 2016; su cobertura en test es 83 %.

## 7. Grafo curricular: embeddings y red extremo a extremo

| Modelo | AP reprobación | ROC-AUC | Brier | Recall@1 |
|---|---|---|---|---|
| Tasa histórica del curso (expansiva) | 0.359 [0.353; 0.365] | 0.755 [0.751; 0.758] | 0.1078 [0.1065; 0.1092] | 0.342 [0.336; 0.348] |
| CatBoost (b) + curso | 0.530 [0.523; 0.538] | 0.855 [0.853; 0.858] | 0.0936 [0.0922; 0.0950] | 0.365 [0.359; 0.370] |
| CatBoost (c) + prerrequisitos | 0.534 [0.527; 0.541] | 0.859 [0.856; 0.861] | 0.0924 [0.0910; 0.0938] | 0.368 [0.362; 0.373] |
| CatBoost (c) + identidad del curso | 0.487 [0.480; 0.494] | 0.839 [0.836; 0.842] | 0.0979 [0.0964; 0.0993] | 0.335 [0.330; 0.341] |
| CatBoost (d') (c) + embeddings GraphSAGE | 0.529 [0.522; 0.537] | 0.858 [0.856; 0.861] | 0.0929 [0.0916; 0.0943] | 0.370 [0.364; 0.376] |
| Red extremo a extremo, sin representación del curso | 0.515 [0.508; 0.523] | 0.852 [0.849; 0.855] | 0.0975 [0.0960; 0.0990] | 0.369 [0.363; 0.375] |
| Red extremo a extremo, atributos del curso sin grafo | 0.524 [0.517; 0.532] | 0.858 [0.855; 0.861] | 0.0970 [0.0955; 0.0985] | 0.366 [0.361; 0.372] |
| Red extremo a extremo, GraphSAGE (solo prerreq.) | 0.530 [0.522; 0.537] | 0.860 [0.857; 0.862] | 0.0972 [0.0957; 0.0987] | 0.375 [0.369; 0.381] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0.516 [0.509; 0.524] | 0.854 [0.852; 0.857] | 0.1005 [0.0990; 0.1020] | 0.370 [0.364; 0.375] |

| Comparación (test) | Resultado |
|---|---|
| (d′) (c) + embeddings GraphSAGE frente a (c) | ΔAP -0,004 [-0,006; -0,003]; ΔROC-AUC -0,000 [-0,001; 0,000] |
| (d′) frente a (c) + identidad del curso | ΔAP 0,042 [0,040; 0,045] |
| (c) + identidad del curso frente a (c) | ΔAP -0,047 [-0,049; -0,044] |
| Red GraphSAGE (prerreq. + coinscripción) frente a la misma red sin aristas | ΔAP -0,008 [-0,009; -0,007] |
| Red GraphSAGE (prerreq. + coinscripción) frente a la red sin representación del curso | ΔAP 0,001 [-0,001; 0,002] |
| Red GraphSAGE (prerreq. + coinscripción) frente a la de solo prerrequisitos | ΔAP -0,014 [-0,015; -0,012] |
| Red GraphSAGE frente a CatBoost (c) | ΔAP -0,018 [-0,021; -0,015] |
| Red GraphSAGE frente al mejor CatBoost de valid ((d), con docente) | ΔAP -0,046 [-0,049; -0,043] |

- **Autosupervisión.** Los embeddings se entrenan prediciendo las aristas de prerrequisito retenidas (10 %) contra pares al azar: AP 0,966-0,977 frente a 0,867-0,903 de una línea base por grado (producto de grados de entrada y salida con las aristas de entrenamiento). Mide que el codificador captura la estructura, pero los negativos al azar son fáciles; no demuestra utilidad para predecir reprobación.

| Semilla | AP enlaces retenidos | ROC-AUC enlaces retenidos | AP línea base por grado | ROC-AUC línea base por grado |
|---|---|---|---|---|
| 0 | 0.967 | 0.967 | 0.869 | 0.861 |
| 1 | 0.972 | 0.967 | 0.892 | 0.879 |
| 2 | 0.977 | 0.972 | 0.903 | 0.892 |

- **Embeddings en CatBoost (d′).** Cambian el AP en -0,004 [-0,006; -0,003] (valid 0,005 [0,004; 0,007]; 2025 -0,009 [-0,011; -0,007]): sin ganancia consistente. El control con la identidad del curso como categórica **empeora** a CatBoost (-0,047 [-0,049; -0,044]; sobreajuste a cursos con pocas filas); los embeddings son una forma de identidad del curso regularizada por la estructura (frente a la identidad: 0,042 [0,040; 0,045]), pero esa ventaja sobre la identidad no se traduce en ventaja sobre el modelo que ya trae la estadística puntual del curso.
- **Red extremo a extremo.** El GraphSAGE entrenado con la reprobación no supera a la red con los mismos atributos de nodo sin aristas ni a la que no usa representación del curso. La coinscripción tampoco ayuda frente a usar solo prerrequisitos. La red queda ≈ 0,01 de AP por debajo de CatBoost (c) en test.
- **GAT.** No se implementó (opcional). Dado que ni el grafo explícito ni GraphSAGE aportan, no se espera que una variante con atención cambie la conclusión, pero no está probado.

## 8. Ranking de cursos por (estudiante, período)

Grupos elegibles: al menos 2 cursos y al menos 1 reprobación en el período (16.411 grupos en test). K = 1, 2; Recall@K = fracción de las reprobaciones del grupo que quedan entre los K cursos de mayor riesgo; Precision@K = fracción de esos K cursos que se reprobaron. Referencia: orden al azar (valor esperado exacto).

| Modelo | Recall@1 | Precision@1 | Recall@2 | Precision@2 |
|---|---|---|---|---|
| Orden al azar (esperado, forma cerrada) | 0.193 | 0.381 | 0.386 | 0.381 |
| Tasa histórica del curso (expansiva) | 0.342 [0.336; 0.348] | 0.610 [0.603; 0.618] | 0.596 [0.590; 0.602] | 0.558 [0.553; 0.563] |
| Logística (a) estudiante + carga | 0.223 [0.218; 0.228] | 0.433 [0.426; 0.440] | 0.417 [0.410; 0.424] | 0.409 [0.403; 0.415] |
| Logística (b) + curso | 0.374 [0.369; 0.379] | 0.655 [0.648; 0.662] | 0.619 [0.613; 0.625] | 0.576 [0.571; 0.581] |
| Logística (c) + prerrequisitos | 0.369 [0.364; 0.375] | 0.651 [0.644; 0.658] | 0.617 [0.612; 0.623] | 0.576 [0.571; 0.581] |
| Logística (d) + docente | 0.389 [0.384; 0.395] | 0.680 [0.673; 0.687] | 0.649 [0.644; 0.655] | 0.602 [0.597; 0.607] |
| CatBoost (a) estudiante + carga | 0.233 [0.228; 0.238] | 0.447 [0.439; 0.454] | 0.428 [0.421; 0.434] | 0.417 [0.411; 0.423] |
| CatBoost (b) + curso | 0.365 [0.359; 0.370] | 0.642 [0.634; 0.649] | 0.628 [0.622; 0.634] | 0.583 [0.577; 0.588] |
| CatBoost (c) + prerrequisitos | 0.368 [0.362; 0.373] | 0.646 [0.638; 0.653] | 0.627 [0.622; 0.633] | 0.581 [0.576; 0.586] |
| CatBoost (d) + docente | 0.395 [0.389; 0.400] | 0.688 [0.680; 0.694] | 0.665 [0.660; 0.671] | 0.613 [0.608; 0.618] |
| CatBoost (c) + identidad del curso | 0.335 [0.330; 0.341] | 0.600 [0.592; 0.607] | 0.582 [0.576; 0.588] | 0.546 [0.541; 0.552] |
| CatBoost (d') (c) + embeddings GraphSAGE | 0.370 [0.364; 0.376] | 0.651 [0.643; 0.658] | 0.624 [0.618; 0.630] | 0.580 [0.575; 0.586] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0.370 [0.364; 0.375] | 0.649 [0.641; 0.655] | 0.623 [0.617; 0.629] | 0.578 [0.572; 0.583] |
| Red extremo a extremo, GraphSAGE (solo prerreq.) | 0.375 [0.369; 0.381] | 0.657 [0.650; 0.664] | 0.624 [0.618; 0.630] | 0.580 [0.575; 0.585] |
| Red extremo a extremo, atributos del curso sin grafo | 0.366 [0.361; 0.372] | 0.644 [0.637; 0.651] | 0.623 [0.618; 0.629] | 0.579 [0.573; 0.583] |
| Red extremo a extremo, sin representación del curso | 0.369 [0.363; 0.375] | 0.648 [0.640; 0.655] | 0.625 [0.619; 0.630] | 0.580 [0.574; 0.585] |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 0.382 [0.377; 0.388] | 0.668 [0.660; 0.675] | 0.644 [0.638; 0.649] | 0.595 [0.590; 0.600] |
| CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0.384 [0.378; 0.389] | 0.668 [0.661; 0.675] | 0.644 [0.638; 0.650] | 0.594 [0.589; 0.599] |

La tasa histórica del curso ya ordena mejor que el azar (Recall@1 0,342 frente a 0,188). Los modelos con estadística del curso la superan poco: CatBoost (c) 0,026 [0,021; 0,032] en Recall@1 y, con docente, 0,053 [0,047; 0,059]. Los modelos sin estadística del curso ((a)) ordenan los cursos de un mismo estudiante apenas mejor que el azar: aunque saben mucho del estudiante, ese conocimiento es idéntico para todos sus cursos del período.

## 9. Calibración (test)

| Decil de riesgo | Tasa histórica del curso (expansiva): predicho / observado | CatBoost (c) + prerrequisitos: predicho / observado | Red extremo a extremo, GraphSAGE (prerreq. + coinscripción): predicho / observado |
|---|---|---|---|
| 1 | 0.012 / 0.021 | 0.006 / 0.003 | 0.001 / 0.003 |
| 2 | 0.028 / 0.040 | 0.011 / 0.010 | 0.003 / 0.009 |
| 3 | 0.047 / 0.055 | 0.019 / 0.022 | 0.006 / 0.019 |
| 4 | 0.066 / 0.073 | 0.030 / 0.034 | 0.012 / 0.031 |
| 5 | 0.089 / 0.112 | 0.045 / 0.053 | 0.021 / 0.052 |
| 6 | 0.122 / 0.124 | 0.065 / 0.074 | 0.035 / 0.086 |
| 7 | 0.176 / 0.172 | 0.096 / 0.124 | 0.058 / 0.137 |
| 8 | 0.191 / 0.076 | 0.150 / 0.201 | 0.097 / 0.207 |
| 9 | 0.258 / 0.325 | 0.246 / 0.331 | 0.169 / 0.329 |
| 10 | 0.426 / 0.445 | 0.473 / 0.586 | 0.374 / 0.565 |

Los modelos de aprendizaje subestiman el riesgo de los deciles altos y en promedio (≈ 0,114 frente a 0,144 observado en CatBoost (c)); la línea base, que depende solo de la historia, queda mejor calibrada en nivel (ECE 0,027) pero discrimina menos. Causa probable (hipótesis): la parada temprana con valid, cuyo nivel (13,4 %) es menor que el de test; no se recalibró (no se ajustó nada con datos de test). Para usar probabilidades hay que recalibrar con un período reciente.

## 10. Subgrupos y equidad (test; descriptivo)

Modelos de las tablas: `baseline`, `cb_b`, `cb_c`, `cb_d`, `nn_gnn`. «Riesgo / AP» = riesgo medio predicho y AP dentro del grupo; los grupos con menos de 500 (programa) o 100 intentos se omiten.

### 10.1 Por sexo (solo evaluación)

| Modelo | Tasa F | Tasa M | Riesgo medio F | Riesgo medio M | AP F | AP M | ΔAP (F−M) | Brecha calibración F | Brecha calibración M |
|---|---|---|---|---|---|---|---|---|---|
| Tasa histórica del curso (expansiva) | 0.127 | 0.157 | 0.130 | 0.151 | 0.351 | 0.364 | -0.013 | +0.004 | -0.007 |
| CatBoost (b) + curso | 0.127 | 0.157 | 0.097 | 0.121 | 0.508 | 0.544 | -0.036 | -0.030 | -0.036 |
| CatBoost (c) + prerrequisitos | 0.127 | 0.157 | 0.100 | 0.125 | 0.511 | 0.548 | -0.037 | -0.026 | -0.032 |
| CatBoost (d) + docente | 0.127 | 0.157 | 0.100 | 0.125 | 0.544 | 0.573 | -0.029 | -0.027 | -0.032 |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 0.127 | 0.157 | 0.067 | 0.086 | 0.500 | 0.526 | -0.027 | -0.060 | -0.071 |

Las mujeres reprueban menos y reciben menor riesgo; la brecha de calibración (riesgo medio menos observado) es negativa en ambos grupos (−0,02 a −0,05), algo mayor en hombres con la red; el AP es menor en mujeres con todos los modelos de aprendizaje. Es una descripción: no se aplicó ninguna corrección ni se evaluó causalidad.

### 10.2 Por oportunidad (primer intento frente a repetición)

| Grupo | n | Tasa reprobación observada | baseline: riesgo / AP | cb_b: riesgo / AP | cb_c: riesgo / AP | cb_d: riesgo / AP | nn_gnn: riesgo / AP |
|---|---|---|---|---|---|---|---|
| 1 | 205.052 | 0.118 | 0.128 / 0.328 | 0.091 / 0.486 | 0.095 / 0.491 | 0.094 / 0.526 | 0.059 / 0.467 |
| 2 | 17.641 | 0.344 | 0.244 / 0.439 | 0.262 / 0.622 | 0.269 / 0.623 | 0.272 / 0.640 | 0.234 / 0.624 |
| 3+ | 6.059 | 0.425 | 0.292 / 0.480 | 0.318 / 0.664 | 0.323 / 0.663 | 0.330 / 0.673 | 0.262 / 0.676 |

En repeticiones la reprobación es de 37-44 % y los modelos subestiman el nivel (riesgo medio 0,29-0,33).

### 10.3 Por semestre de la malla

| Grupo | n | Tasa reprobación observada | baseline: riesgo / AP | cb_b: riesgo / AP | cb_c: riesgo / AP | cb_d: riesgo / AP | nn_gnn: riesgo / AP |
|---|---|---|---|---|---|---|---|
| 01 | 42.779 | 0.209 | 0.181 / 0.441 | 0.181 / 0.614 | 0.187 / 0.617 | 0.181 / 0.633 | 0.112 / 0.590 |
| 02 | 38.757 | 0.185 | 0.152 / 0.348 | 0.127 / 0.578 | 0.136 / 0.582 | 0.135 / 0.615 | 0.092 / 0.558 |
| 03 | 29.165 | 0.194 | 0.183 / 0.390 | 0.132 / 0.559 | 0.137 / 0.559 | 0.141 / 0.585 | 0.103 / 0.545 |
| 04 | 24.710 | 0.162 | 0.154 / 0.335 | 0.108 / 0.508 | 0.111 / 0.506 | 0.116 / 0.548 | 0.084 / 0.509 |
| 05 | 19.728 | 0.110 | 0.129 / 0.259 | 0.084 / 0.386 | 0.087 / 0.390 | 0.089 / 0.421 | 0.064 / 0.393 |
| 06 | 18.957 | 0.092 | 0.112 / 0.250 | 0.072 / 0.366 | 0.073 / 0.367 | 0.074 / 0.404 | 0.052 / 0.353 |
| 07 | 18.141 | 0.078 | 0.099 / 0.288 | 0.063 / 0.368 | 0.064 / 0.374 | 0.065 / 0.409 | 0.045 / 0.351 |
| 08 | 14.667 | 0.047 | 0.071 / 0.167 | 0.045 / 0.304 | 0.045 / 0.308 | 0.044 / 0.343 | 0.027 / 0.292 |
| 09 | 12.328 | 0.022 | 0.085 / 0.060 | 0.036 / 0.146 | 0.036 / 0.156 | 0.031 / 0.174 | 0.018 / 0.150 |
| 10 | 6.213 | 0.091 | 0.110 / 0.365 | 0.081 / 0.405 | 0.083 / 0.405 | 0.082 / 0.401 | 0.065 / 0.420 |
| fuera_de_malla | 3.307 | 0.065 | 0.111 / 0.194 | 0.064 / 0.331 | 0.066 / 0.337 | 0.068 / 0.343 | 0.052 / 0.322 |

### 10.4 Curso dentro o fuera de la malla del estudiante

| Grupo | n | Tasa reprobación observada | baseline: riesgo / AP | cb_b: riesgo / AP | cb_c: riesgo / AP | cb_d: riesgo / AP | nn_gnn: riesgo / AP |
|---|---|---|---|---|---|---|---|
| en_malla | 225.445 | 0.145 | 0.142 / 0.360 | 0.111 / 0.531 | 0.115 / 0.535 | 0.115 / 0.563 | 0.078 / 0.517 |
| fuera_de_malla | 3.307 | 0.065 | 0.111 / 0.194 | 0.064 / 0.331 | 0.066 / 0.337 | 0.068 / 0.343 | 0.052 / 0.322 |

Los cursos fuera de la malla (1,4 %) tienen menos señal (AP 0,36 frente a 0,54 en CatBoost (c)) y no tienen variables de prerrequisitos (`info_prereq` es idéntico a «en la malla»).

### 10.5 Por programa (n ≥ 500 en test)

| Grupo | n | Tasa reprobación observada | baseline: riesgo / AP | cb_b: riesgo / AP | cb_c: riesgo / AP | cb_d: riesgo / AP | nn_gnn: riesgo / AP |
|---|---|---|---|---|---|---|---|
| 8103 LICENCIATURA EN FÍSICA CON MENCIÓN EN ASTRONOMÍA | 1.583 | 0.330 | 0.291 / 0.455 | 0.270 / 0.661 | 0.289 / 0.659 | 0.294 / 0.669 | 0.219 / 0.643 |
| 8163 PEDAGOGÍA EN EDUCACIÓN PARVULARIA CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 1.432 | 0.045 | 0.100 / 0.048 | 0.041 / 0.136 | 0.040 / 0.150 | 0.039 / 0.153 | 0.020 / 0.162 |
| 8173 PEDAGOGÍA EN EDUCACIÓN DIFERENCIAL CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 1.187 | 0.044 | 0.144 / 0.041 | 0.058 / 0.132 | 0.055 / 0.131 | 0.054 / 0.134 | 0.024 / 0.147 |
| 8176 PEDAGOGÍA EN EDUCACIÓN DIFERENCIAL CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 2.410 | 0.045 | 0.108 / 0.061 | 0.053 / 0.148 | 0.052 / 0.154 | 0.046 / 0.154 | 0.029 / 0.173 |
| 8213 ARQUITECTURA | 6.922 | 0.152 | 0.196 / 0.396 | 0.166 / 0.472 | 0.174 / 0.480 | 0.171 / 0.492 | 0.115 / 0.458 |
| 8223 PEDAGOGÍA EN INGLÉS | 5.155 | 0.060 | 0.081 / 0.106 | 0.048 / 0.300 | 0.051 / 0.322 | 0.049 / 0.323 | 0.032 / 0.338 |
| 8233 INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 5.564 | 0.155 | 0.185 / 0.339 | 0.143 / 0.530 | 0.146 / 0.537 | 0.149 / 0.555 | 0.098 / 0.508 |
| 8243 INGENIERÍA EN METALURGIA | 1.631 | 0.182 | 0.200 / 0.340 | 0.159 / 0.480 | 0.161 / 0.491 | 0.164 / 0.535 | 0.105 / 0.447 |
| 8266 INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 4.966 | 0.206 | 0.185 / 0.389 | 0.129 / 0.613 | 0.133 / 0.623 | 0.128 / 0.620 | 0.102 / 0.598 |
| 8293 QUÍMICA INDUSTRIAL | 633 | 0.229 | 0.235 / 0.341 | 0.206 / 0.524 | 0.218 / 0.532 | 0.236 / 0.539 | 0.145 / 0.506 |
| 8313 CONTADOR AUDITOR - CONTADOR PÚBLICO VESPERTINO | 803 | 0.122 | 0.128 / 0.225 | 0.118 / 0.456 | 0.124 / 0.464 | 0.126 / 0.496 | 0.078 / 0.459 |
| 8323 INGENIERÍA COMERCIAL | 11.167 | 0.137 | 0.137 / 0.343 | 0.106 / 0.506 | 0.115 / 0.506 | 0.111 / 0.538 | 0.063 / 0.479 |
| 8326 INGENIERÍA COMERCIAL | 11.769 | 0.135 | 0.125 / 0.271 | 0.090 / 0.436 | 0.097 / 0.444 | 0.092 / 0.472 | 0.053 / 0.446 |
| 8333 CONTADOR AUDITOR - CONTADOR PÚBLICO | 2.874 | 0.135 | 0.133 / 0.347 | 0.106 / 0.545 | 0.111 / 0.535 | 0.111 / 0.554 | 0.072 / 0.503 |
| 8353 PERIODISMO | 3.213 | 0.046 | 0.055 / 0.102 | 0.032 / 0.311 | 0.033 / 0.329 | 0.031 / 0.338 | 0.022 / 0.318 |
| 8373 DERECHO | 10.545 | 0.200 | 0.156 / 0.390 | 0.141 / 0.502 | 0.148 / 0.502 | 0.146 / 0.570 | 0.115 / 0.500 |
| 8376 DERECHO | 11.211 | 0.189 | 0.142 / 0.417 | 0.132 / 0.564 | 0.137 / 0.578 | 0.135 / 0.616 | 0.116 / 0.544 |
| 8383 PSICOLOGÍA | 7.429 | 0.023 | 0.062 / 0.034 | 0.028 / 0.204 | 0.028 / 0.204 | 0.027 / 0.202 | 0.012 / 0.257 |
| 8403 GEOLOGÍA | 6.375 | 0.207 | 0.166 / 0.460 | 0.162 / 0.553 | 0.169 / 0.545 | 0.171 / 0.578 | 0.133 / 0.523 |
| 8453 ANALISTA QUÍMICO | 527 | 0.268 | 0.246 / 0.527 | 0.241 / 0.654 | 0.258 / 0.659 | 0.266 / 0.676 | 0.173 / 0.671 |
| 8456 BIOLOGÍA MARINA | 3.848 | 0.138 | 0.133 / 0.308 | 0.091 / 0.496 | 0.092 / 0.493 | 0.093 / 0.505 | 0.063 / 0.480 |
| 8466 INGENIERÍA EN ACUICULTURA | 918 | 0.219 | 0.154 / 0.352 | 0.150 / 0.530 | 0.160 / 0.539 | 0.147 / 0.567 | 0.114 / 0.473 |
| 8483 QUÍMICA Y FARMACIA | 5.717 | 0.164 | 0.167 / 0.356 | 0.121 / 0.582 | 0.126 / 0.589 | 0.121 / 0.581 | 0.078 / 0.554 |
| 8486 MEDICINA | 7.009 | 0.018 | 0.026 / 0.084 | 0.013 / 0.082 | 0.012 / 0.072 | 0.012 / 0.058 | 0.008 / 0.223 |
| 8506 INGENIERÍA EN PREVENCION DE RIESGOS Y MEDIOAMBIENTE | 2.208 | 0.202 | 0.195 / 0.326 | 0.208 / 0.510 | 0.218 / 0.512 | 0.214 / 0.544 | 0.145 / 0.458 |
| 8516 ENFERMERÍA | 3.602 | 0.042 | 0.057 / 0.087 | 0.032 / 0.136 | 0.031 / 0.146 | 0.033 / 0.142 | 0.021 / 0.186 |
| 8526 NUTRICIÓN Y DIETÉTICA | 2.443 | 0.063 | 0.048 / 0.204 | 0.049 / 0.358 | 0.046 / 0.347 | 0.045 / 0.378 | 0.029 / 0.409 |
| 8553 INGENIERÍA CIVIL EN QUÍMICA | 2.900 | 0.171 | 0.184 / 0.351 | 0.134 / 0.587 | 0.138 / 0.585 | 0.148 / 0.624 | 0.107 / 0.584 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 9.952 | 0.201 | 0.154 / 0.491 | 0.136 / 0.688 | 0.139 / 0.696 | 0.143 / 0.716 | 0.102 / 0.673 |
| 8606 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 11.706 | 0.143 | 0.134 / 0.303 | 0.115 / 0.487 | 0.118 / 0.482 | 0.115 / 0.519 | 0.074 / 0.457 |
| 8613 INGENIERÍA CIVIL INDUSTRIAL | 17.097 | 0.136 | 0.167 / 0.288 | 0.102 / 0.492 | 0.104 / 0.501 | 0.107 / 0.546 | 0.068 / 0.486 |
| 8616 INGENIERÍA CIVIL INDUSTRIAL | 18.529 | 0.119 | 0.160 / 0.308 | 0.092 / 0.479 | 0.094 / 0.464 | 0.090 / 0.522 | 0.065 / 0.465 |
| 8623 INGENIERÍA CIVIL AMBIENTAL | 2.414 | 0.123 | 0.157 / 0.381 | 0.102 / 0.556 | 0.105 / 0.567 | 0.110 / 0.608 | 0.083 / 0.564 |
| 8643 INGENIERÍA CIVIL PLAN COMÚN | 841 | 0.344 | 0.205 / 0.506 | 0.302 / 0.676 | 0.311 / 0.678 | 0.301 / 0.688 | 0.198 / 0.641 |
| 8653 INGENIERÍA CIVIL DE MINAS | 9.006 | 0.200 | 0.206 / 0.415 | 0.174 / 0.599 | 0.178 / 0.603 | 0.175 / 0.641 | 0.125 / 0.584 |
| 8673 INGENIERÍA EN CONSTRUCCIÓN | 3.029 | 0.151 | 0.182 / 0.323 | 0.146 / 0.505 | 0.147 / 0.517 | 0.151 / 0.522 | 0.105 / 0.479 |
| 8683 INGENIERÍA CIVIL METALÚRGICA | 4.963 | 0.211 | 0.181 / 0.402 | 0.164 / 0.658 | 0.168 / 0.662 | 0.172 / 0.682 | 0.115 / 0.623 |
| 8693 INGENIERÍA CIVIL | 3.383 | 0.324 | 0.274 / 0.560 | 0.264 / 0.736 | 0.271 / 0.741 | 0.277 / 0.738 | 0.182 / 0.719 |
| 8716 PEDAGOGÍA EN FILOSOFÍA Y RELIGIÓN | 549 | 0.155 | 0.084 / 0.127 | 0.064 / 0.376 | 0.065 / 0.361 | 0.062 / 0.382 | 0.050 / 0.300 |
| 8783 PEDAGOGÍA EN EDUCACIÓN BÁSICA CON ESPECIALIZACIÓN | 2.817 | 0.047 | 0.068 / 0.088 | 0.037 / 0.295 | 0.036 / 0.291 | 0.037 / 0.288 | 0.019 / 0.278 |
| 8843 PEDAGOGÍA EN MATEMÁTICA EN EDUCACIÓN MEDIA | 1.679 | 0.167 | 0.144 / 0.376 | 0.111 / 0.548 | 0.117 / 0.553 | 0.126 / 0.579 | 0.075 / 0.525 |
| 8893 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 3.651 | 0.091 | 0.063 / 0.185 | 0.048 / 0.397 | 0.050 / 0.404 | 0.057 / 0.431 | 0.025 / 0.398 |
| 8896 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 6.960 | 0.144 | 0.065 / 0.209 | 0.058 / 0.423 | 0.063 / 0.429 | 0.073 / 0.453 | 0.034 / 0.435 |
| 8906 KINESIOLOGÍA | 3.744 | 0.047 | 0.044 / 0.093 | 0.034 / 0.220 | 0.033 / 0.225 | 0.033 / 0.229 | 0.016 / 0.228 |
| 8953 INGENIERÍA CIVIL ELECTRÓNICA | 549 | 0.346 | 0.205 / 0.594 | 0.238 / 0.733 | 0.242 / 0.746 | 0.258 / 0.762 | 0.143 / 0.730 |
| 8973 INGENIERÍA CIVIL EN GESTIÓN DE LA CONSTRUCCION | 1.032 | 0.199 | 0.212 / 0.427 | 0.176 / 0.663 | 0.176 / 0.657 | 0.181 / 0.659 | 0.127 / 0.660 |

## 11. Estabilidad por período (test)

AP por período de test:

| Período (test) | Tasa histórica del curso (expansiva) | CatBoost (b) + curso | CatBoost (c) + prerrequisitos | CatBoost (d') (c) + embeddings GraphSAGE | CatBoost (d) + docente | Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) |
|---|---|---|---|---|---|---|
| 202310 | 0.341 | 0.501 | 0.507 | 0.505 | 0.541 | 0.492 |
| 202320 | 0.338 | 0.526 | 0.530 | 0.521 | 0.557 | 0.511 |
| 202410 | 0.387 | 0.542 | 0.545 | 0.541 | 0.567 | 0.526 |
| 202420 | 0.392 | 0.558 | 0.560 | 0.556 | 0.588 | 0.548 |

Los modelos mantienen el orden en los cuatro períodos; el AP sube con la tasa base. Tasas por período: §2.

## 11b. Sensibilidad: qué ocurre si se incluyen 201920 y 202010

En la corrida inicial (no conservada; mismos modelos y misma definición, con esos dos períodos como unidades) el AP de test fue 0,39 para CatBoost (b) (0,385 la línea base), 0,50 para la logística (b) y 0,51 para la red GraphSAGE; el riesgo medio predicho fue de 0,04-0,09 frente a 0,159 observado y la parada temprana de CatBoost se producía en unas 30 iteraciones. Con ellos excluidos, CatBoost (b) alcanza 0,530. La diferencia se debe a que en esos períodos los estudiantes que habrían reprobado figuran sin reprobación registrada, lo que enseña al modelo que ciertos semestres no tienen riesgo. Las cifras de esa corrida se citan solo como orden de magnitud: sus artefactos no se conservaron.


## 12. Importancia de variables, tiempo y memoria

Importancia (CatBoost (c), media de 3 semillas):

| Variable | Importancia (media de 3 semillas, % del total) |
|---|---|
| `tasa_hist_curso_prog` | 11.8 |
| `prom_acum` | 11.0 |
| `creditos_carga` | 8.9 |
| `tasa_aprob_acum` | 7.3 |
| `prom_hist_curso` | 6.3 |
| `n_cursos_carga` | 5.1 |
| `depto` | 4.5 |
| `tasa_hist_curso_suav` | 4.0 |
| `n_repetidos_carga` | 4.0 |
| `n_reprob_acum` | 3.0 |
| `mean_nota_prereq` | 2.8 |
| `tasa_hist_curso` | 2.7 |
| `cod_programa` | 2.7 |
| `creditos_aprob_acum` | 2.4 |
| `mejor_nota_prev_curso` | 2.4 |

### Tiempo y memoria

| Modelo | Tiempo de entrenamiento (s) | Notas |
|---|---|---|
| Tasa histórica del curso (expansiva) | 0 |  |
| Logística (a) estudiante + carga | 56 | C = 0.003; 167 columnas |
| Logística (b) + curso | 173 | C = 0.0003; 420 columnas |
| Logística (c) + prerrequisitos | 182 | C = 0.0003; 436 columnas |
| Logística (d) + docente | 189 | C = 0.0003; 445 columnas |
| CatBoost (a) estudiante + carga | 187 | 3 semillas; iteraciones óptimas [211, 140, 206] |
| CatBoost (b) + curso | 233 | 3 semillas; iteraciones óptimas [142, 156, 195] |
| CatBoost (c) + prerrequisitos | 221 | 3 semillas; iteraciones óptimas [145, 215, 183] |
| CatBoost (d) + docente | 223 | 3 semillas; iteraciones óptimas [147, 175, 178] |
| CatBoost (c) + identidad del curso | 223 | 3 semillas; iteraciones óptimas [199, 103, 155] |
| CatBoost (d') (c) + embeddings GraphSAGE | 225 | 3 semillas; iteraciones óptimas [136, 173, 181] |
| Red extremo a extremo, GraphSAGE (prerreq. + coinscripción) | 20 | 109473 parámetros; pico de memoria GPU 319 MB; épocas óptimas [1.9047619047619047, 1.5873015873015872, 1.5873015873015872] |
| Red extremo a extremo, GraphSAGE (solo prerreq.) | 18 | 103329 parámetros; pico de memoria GPU 319 MB; épocas óptimas [1.9047619047619047, 1.5873015873015872, 1.5873015873015872] |
| Red extremo a extremo, atributos del curso sin grafo | 15 | 91041 parámetros; pico de memoria GPU 317 MB; épocas óptimas [1.9047619047619047, 1.9047619047619047, 1.5873015873015872] |
| Red extremo a extremo, sin representación del curso | 11 | 68609 parámetros; pico de memoria GPU 306 MB; épocas óptimas [1.9047619047619047, 1.9047619047619047, 1.5873015873015872] |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 234 | 3 semillas; iteraciones óptimas [192, 159, 226] |
| CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 257 | 3 semillas; iteraciones óptimas [163, 261, 189] |

Pico de memoria RAM del proceso de entrenamiento y evaluación: 4155 MB (conjunto completo en memoria, 16 GB disponibles). Tiempo total de la corrida: 3739 s. GPU: RTX 4060 de 8 GB; ninguna red superó el pico indicado en la tabla (memoria asignada por PyTorch).

## 12b. Banda de nota por intento (P84) y pronósticos agregados (P74)

**Escala institucional (P84).** Reprobado < 4,0; «Aprobado por Unanimidad» [4,0; 5,4); «Aprobado con Distinción» [5,4; 6,4); «Aprobado con Máxima Distinción» [6,4; 7,0]. La banda es una etiqueta (como `y`), nunca una variable. **La nota final de titulación** (70 % el promedio de cursos y 30 % el examen de titulación) **no se modela**: no hay en la base una fuente de la nota del examen (P89), y la banda de T2 es solo la nota del intento de un curso.

| Partición | Intentos | Reprobado (< 4,0) | Aprobado por Unanimidad (4,0–5,3) | Aprobado con Distinción (5,4–6,3) | Aprobado con Máxima Distinción (6,4–7,0) |
|---|---|---|---|---|---|
| valid | 208.234 | 13,4 % | 35,5 % | 31,9 % | 19,1 % |
| test | 228.752 | 14,4 % | 38,2 % | 29,5 % | 17,9 % |
| posterior | 107.234 | 17,2 % | 35,1 % | 28,5 % | 19,2 % |

**Modelo.** CatBoost multiclase con el mismo conjunto de variables que los binarios (se usó el conjunto elegido por el AP de valid de los modelos binarios, conjunto c), 3 semillas del conjunto de entrenamiento y parada temprana en valid, sin docente. Se evalúa con log-loss y AP por clase frente a la frecuencia de las bandas en train, con intervalos del bootstrap agrupado por persona y diferencias pareadas.

**Test (2023-2024):**

| Modelo | Log-loss | Brier multiclase | AP reprobado | AP unanimidad | AP distinción | AP máx, distinción | AP macro |
|---|---|---|---|---|---|---|---|
| CatBoost multiclase (conjunto c) | 1,0272 [1,0238; 1,0313] | 0,5864 [0,5847; 0,5885] | 0,521 [0,512; 0,530] | 0,615 [0,611; 0,620] | 0,468 [0,464; 0,473] | 0,550 [0,542; 0,558] | 0,539 [0,535; 0,542] |
| Frecuencia de las bandas en train | 1,3464 [1,3427; 1,3508] | 0,7266 [0,7247; 0,7289] | 0,144 [0,141; 0,147] | 0,382 [0,379; 0,386] | 0,295 [0,293; 0,298] | 0,179 [0,176; 0,182] | 0,250 [0,250; 0,250] |
| **Diferencia pareada (CatBoost − frecuencia)** | -0,3192 [-0,3250; -0,3134] | -0,1402 [-0,1429; -0,1373] | 0,377 [0,370; 0,385] | 0,233 [0,230; 0,237] | 0,173 [0,170; 0,177] | 0,371 [0,364; 0,378] | 0,289 [0,285; 0,292] |

**Valid (2021-2022):**

| Modelo | Log-loss | Brier multiclase | AP reprobado | AP unanimidad | AP distinción | AP máx, distinción | AP macro |
|---|---|---|---|---|---|---|---|
| CatBoost multiclase (conjunto c) | 1,0715 [1,0679; 1,0753] | 0,6084 [0,6064; 0,6107] | 0,489 [0,479; 0,499] | 0,550 [0,544; 0,556] | 0,473 [0,469; 0,477] | 0,525 [0,518; 0,531] | 0,509 [0,506; 0,512] |
| Frecuencia de las bandas en train | 1,3674 [1,3629; 1,3719] | 0,7387 [0,7366; 0,7408] | 0,134 [0,131; 0,138] | 0,355 [0,352; 0,359] | 0,319 [0,316; 0,323] | 0,191 [0,188; 0,194] | 0,250 [0,250; 0,250] |
| **Diferencia pareada (CatBoost − frecuencia)** | -0,2959 [-0,3009; -0,2908] | -0,1302 [-0,1330; -0,1275] | 0,354 [0,346; 0,362] | 0,195 [0,190; 0,199] | 0,154 [0,151; 0,157] | 0,333 [0,328; 0,340] | 0,259 [0,256; 0,262] |

**2025 (control posterior):**

| Modelo | Log-loss | Brier multiclase | AP reprobado | AP unanimidad | AP distinción | AP máx, distinción | AP macro |
|---|---|---|---|---|---|---|---|
| CatBoost multiclase (conjunto c) | 1,0281 [1,0227; 1,0337] | 0,5888 [0,5863; 0,5917] | 0,584 [0,571; 0,594] | 0,561 [0,555; 0,567] | 0,476 [0,470; 0,483] | 0,585 [0,578; 0,593] | 0,552 [0,547; 0,555] |
| Frecuencia de las bandas en train | 1,3901 [1,3850; 1,3949] | 0,7490 [0,7466; 0,7515] | 0,172 [0,168; 0,176] | 0,351 [0,346; 0,355] | 0,285 [0,282; 0,289] | 0,192 [0,189; 0,196] | 0,250 [0,250; 0,250] |
| **Diferencia pareada (CatBoost − frecuencia)** | -0,3620 [-0,3689; -0,3544] | -0,1602 [-0,1635; -0,1565] | 0,412 [0,402; 0,420] | 0,211 [0,206; 0,215] | 0,191 [0,186; 0,197] | 0,393 [0,387; 0,400] | 0,302 [0,297; 0,305] |

El modelo reduce el log-loss de test de 1,3464 [1,3427; 1,3508] a 1,0272 [1,0238; 1,0313] y mejora el AP de cada banda con intervalos claramente sobre 0 (diferencias pareadas en la fila final).

### Pronósticos agregados por programa y facultad (P74)

**Solo agregados.** Ninguna fila de esta sección corresponde a una persona. Se aplican los umbrales de publicación (D70 y la respuesta de la DAI): un grupo con menos de 10 intentos no deja rastro; un grupo se lista con n ≥ 100 y una banda solo se evalúa con al menos 10 eventos en ella; los demás se cuentan y no se listan. Los porcentajes son del **modelo** (esperado) frente a lo **observado** en test, con intervalos del 95 %; la «brecha de la frecuencia global» es la referencia que el modelo debe superar.

| Evaluación | Nivel | Grupos | ≥ 100 intentos (listados) | 10 a 99 (solo contados) | < 10 (suprimidos) | Intentos en listados | MAE reprobado: modelo / frecuencia | MAE unanimidad: modelo / frecuencia | MAE distinción: modelo / frecuencia | MAE máx, distinción: modelo / frecuencia | ρ reprobado | ρ unanimidad | ρ distinción | ρ máx, distinción |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| test | programa | 55 | 49 | 4 | 2 | 228.667 de 228.752 | 3,82 / 5,09 pp | 3,93 / 7,96 pp | 5,16 / 4,62 pp | 3,65 / 7,78 pp | 0,91 | 0,86 | 0,88 | 0,91 |
| test | facultad | 14 | 13 | 1 | 0 | 228.723 de 228.752 | 3,81 / 4,23 pp | 3,46 / 7,63 pp | 5,00 / 3,64 pp | 3,39 / 7,65 pp | 0,93 | 0,85 | 0,84 | 0,90 |
| valid + test | programa | 58 | 52 | 5 | 1 | 436.796 de 436.986 | 2,96 / 5,76 pp | 2,90 / 8,96 pp | 3,71 / 4,91 pp | 2,74 / 8,41 pp | 0,95 | 0,85 | 0,88 | 0,94 |
| valid + test | facultad | 15 | 14 | 1 | 0 | 436.969 de 436.986 | 2,90 / 4,79 pp | 1,79 / 8,92 pp | 3,52 / 3,94 pp | 2,32 / 8,28 pp | 0,98 | 0,91 | 0,91 | 0,89 |

**Lectura.** El modelo ordena bien los grupos (ρ de Spearman de 0,84 a 0,93 en test por programa y facultad) y su error absoluto medio en puntos porcentuales es menor que el de la frecuencia global en la banda de reprobados (3,8 frente a 5,1 por programa), en Unanimidad (3,9 frente a 8,0) y en Máxima Distinción (3,7 frente a 7,8), pero **peor en Distinción** (5,2 frente a 4,6 por programa; 5,0 frente a 3,6 por facultad): esa banda es la central y la frecuencia global ya la predice bien. El modelo **subestima la reprobación de los programas con más reprobación** (hasta 12 puntos en Ingeniería Civil en Energía y Electrónica): es la misma subestimación de nivel de §9, concentrada en los grupos de mayor riesgo.

**Programas reportables.** Con n ≥ 100 intentos en test se listan 49 de 55 programas y 13 de 14 facultades. Los programas, ordenados por el % observado de reprobados (observado / predicho y brecha en puntos porcentuales; los intervalos por programa están en `artefactos/resultados_t2.json`, ignorado por git):

| Programa | Intentos | Reprobado: obs. / pred. (brecha, pp) | Unanimidad: obs. / pred. (brecha, pp) | Distinción: obs. / pred. (brecha, pp) | Máx. distinción: obs. / pred. (brecha, pp) |
|---|---|---|---|---|---|
| 8953 · INGENIERÍA CIVIL ELECTRÓNICA | 549 | 34,6 / 23,5 (-11,1) | 30,4 / 32,5 (+2,1) | 20,6 / 28,4 (+7,9) | 14,4 / 15,5 (+1,1) |
| 8643 · INGENIERÍA CIVIL PLAN COMÚN | 841 | 34,4 / 27,7 (-6,7) | 31,6 / 33,9 (+2,3) | 21,0 / 25,5 (+4,5) | 13,0 / 12,9 (-0,1) |
| 8963 · INGENIERÍA CIVIL EN ENERGÍA | 245 | 33,1 / 21,2 (-11,9) | 25,7 / 31,5 (+5,8) | 24,5 / 30,0 (+5,5) | 16,7 / 17,3 (+0,5) |
| 8103 · LICENCIATURA EN FÍSICA CON MENCIÓN EN ASTRONOMÍA | 1.583 | 33,0 / 28,2 (-4,8) | 34,8 / 42,7 (+7,9) | 18,1 / 19,4 (+1,3) | 14,2 / 9,7 (-4,4) |
| 8693 · INGENIERÍA CIVIL | 3.383 | 32,4 / 25,5 (-6,9) | 37,5 / 40,1 (+2,6) | 21,2 / 24,6 (+3,4) | 8,9 / 9,8 (+0,9) |
| 8453 · ANALISTA QUÍMICO | 527 | 26,8 / 24,6 (-2,2) | 39,5 / 39,6 (+0,2) | 23,9 / 26,4 (+2,5) | 9,9 / 9,4 (-0,5) |
| 8293 · QUÍMICA INDUSTRIAL | 633 | 22,9 / 21,4 (-1,5) | 39,7 / 38,0 (-1,6) | 21,3 / 27,4 (+6,1) | 16,1 / 13,1 (-3,0) |
| 8466 · INGENIERÍA EN ACUICULTURA | 918 | 21,9 / 14,4 (-7,5) | 42,0 / 40,3 (-1,8) | 24,5 / 31,4 (+6,9) | 11,5 / 13,9 (+2,3) |
| 8253 · INGENIERÍA EN PROCESOS QUÍMICOS | 288 | 21,9 / 18,6 (-3,3) | 39,2 / 40,4 (+1,1) | 22,9 / 28,1 (+5,2) | 16,0 / 12,9 (-3,1) |
| 8683 · INGENIERÍA CIVIL METALÚRGICA | 4.963 | 21,1 / 15,8 (-5,3) | 45,2 / 44,3 (-0,9) | 23,6 / 28,0 (+4,4) | 10,2 / 11,9 (+1,8) |
| 8403 · GEOLOGÍA | 6.375 | 20,7 / 14,8 (-5,9) | 41,5 / 38,1 (-3,4) | 23,3 / 31,1 (+7,8) | 14,4 / 16,0 (+1,5) |
| 8266 · INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 4.966 | 20,6 / 12,8 (-7,9) | 41,9 / 44,6 (+2,7) | 26,0 / 29,5 (+3,5) | 11,5 / 13,2 (+1,7) |
| 8506 · INGENIERÍA EN PREVENCION DE RIESGOS Y MEDIOAMBIENTE | 2.208 | 20,2 / 20,1 (-0,1) | 44,5 / 42,2 (-2,3) | 25,7 / 25,8 (+0,1) | 9,6 / 11,8 (+2,2) |
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 9.952 | 20,1 / 13,1 (-7,0) | 37,5 / 36,8 (-0,7) | 27,5 / 33,5 (+6,0) | 14,9 / 16,6 (+1,7) |
| 8653 · INGENIERÍA CIVIL DE MINAS | 9.006 | 20,0 / 16,2 (-3,9) | 48,5 / 49,5 (+1,0) | 21,9 / 24,4 (+2,5) | 9,5 / 9,9 (+0,3) |
| 8373 · DERECHO | 10.545 | 20,0 / 13,8 (-6,2) | 41,0 / 39,4 (-1,6) | 24,0 / 32,1 (+8,0) | 15,0 / 14,8 (-0,2) |
| 8973 · INGENIERÍA CIVIL EN GESTIÓN DE LA CONSTRUCCION | 1.032 | 19,9 / 17,3 (-2,6) | 40,1 / 38,6 (-1,6) | 28,9 / 31,2 (+2,3) | 11,1 / 13,0 (+1,9) |
| 8376 · DERECHO | 11.211 | 18,9 / 13,0 (-5,9) | 42,9 / 42,6 (-0,2) | 22,6 / 28,8 (+6,2) | 15,6 / 15,6 (+0,0) |
| 8243 · INGENIERÍA EN METALURGIA | 1.631 | 18,2 / 16,6 (-1,6) | 49,5 / 46,8 (-2,7) | 24,2 / 27,0 (+2,9) | 8,1 / 9,5 (+1,4) |
| 8553 · INGENIERÍA CIVIL EN QUÍMICA | 2.900 | 17,1 / 13,5 (-3,6) | 45,3 / 45,1 (-0,2) | 25,0 / 28,7 (+3,7) | 12,6 / 12,7 (+0,1) |
| 8843 · PEDAGOGÍA EN MATEMÁTICA EN EDUCACIÓN MEDIA | 1.679 | 16,7 / 11,9 (-4,8) | 26,7 / 27,5 (+0,8) | 27,8 / 31,2 (+3,5) | 28,8 / 29,4 (+0,6) |
| 8483 · QUÍMICA Y FARMACIA | 5.717 | 16,4 / 11,6 (-4,8) | 41,2 / 35,1 (-6,2) | 27,0 / 35,3 (+8,4) | 15,4 / 18,0 (+2,6) |
| 8233 · INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 5.564 | 15,5 / 14,7 (-0,8) | 41,2 / 40,2 (-0,9) | 29,5 / 31,8 (+2,3) | 13,8 / 13,3 (-0,5) |
| 8716 · PEDAGOGÍA EN FILOSOFÍA Y RELIGIÓN | 549 | 15,5 / 7,0 (-8,5) | 25,3 / 19,8 (-5,5) | 32,1 / 38,9 (+6,8) | 27,1 / 34,2 (+7,1) |
| 8213 · ARQUITECTURA | 6.922 | 15,2 / 17,1 (+1,9) | 43,7 / 40,8 (-2,9) | 29,3 / 31,0 (+1,7) | 11,8 / 11,1 (-0,7) |
| 8673 · INGENIERÍA EN CONSTRUCCIÓN | 3.029 | 15,1 / 15,2 (+0,1) | 48,3 / 41,9 (-6,4) | 26,0 / 30,6 (+4,6) | 10,6 / 12,3 (+1,7) |
| 8853 · LICENCIATURA EN MATEMÁTICA | 192 | 14,6 / 17,2 (+2,7) | 38,5 / 37,7 (-0,9) | 23,4 / 26,8 (+3,4) | 23,4 / 18,2 (-5,2) |
| 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 6.960 | 14,4 / 5,4 (-8,9) | 42,9 / 34,2 (-8,6) | 28,5 / 38,9 (+10,4) | 14,3 / 21,4 (+7,2) |
| 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 11.706 | 14,3 / 10,7 (-3,5) | 43,5 / 40,8 (-2,7) | 27,5 / 32,3 (+4,8) | 14,8 / 16,1 (+1,3) |
| 8456 · BIOLOGÍA MARINA | 3.848 | 13,8 / 8,8 (-5,1) | 36,1 / 30,9 (-5,2) | 33,6 / 37,2 (+3,6) | 16,5 / 23,2 (+6,7) |
| 8323 · INGENIERÍA COMERCIAL | 11.167 | 13,7 / 10,6 (-3,1) | 39,7 / 33,8 (-5,9) | 26,7 / 33,7 (+7,0) | 19,9 / 22,0 (+2,0) |
| 8613 · INGENIERÍA CIVIL INDUSTRIAL | 17.097 | 13,6 / 9,6 (-4,0) | 41,8 / 39,0 (-2,7) | 31,1 / 34,6 (+3,5) | 13,5 / 16,8 (+3,3) |
| 8333 · CONTADOR AUDITOR - CONTADOR PÚBLICO | 2.874 | 13,5 / 11,0 (-2,6) | 41,9 / 35,2 (-6,7) | 27,6 / 35,1 (+7,6) | 17,0 / 18,7 (+1,7) |
| 8326 · INGENIERÍA COMERCIAL | 11.769 | 13,5 / 9,2 (-4,3) | 43,0 / 36,9 (-6,1) | 26,3 / 32,7 (+6,4) | 17,2 / 21,2 (+4,0) |
| 8623 · INGENIERÍA CIVIL AMBIENTAL | 2.414 | 12,3 / 9,7 (-2,7) | 42,8 / 43,0 (+0,2) | 29,7 / 32,8 (+3,0) | 15,1 / 14,5 (-0,6) |
| 8313 · CONTADOR AUDITOR - CONTADOR PÚBLICO VESPERTINO | 803 | 12,2 / 11,6 (-0,6) | 41,1 / 39,1 (-2,0) | 29,8 / 33,0 (+3,2) | 16,9 / 16,3 (-0,6) |
| 8616 · INGENIERÍA CIVIL INDUSTRIAL | 18.529 | 11,9 / 8,9 (-3,1) | 45,9 / 39,8 (-6,1) | 29,3 / 33,8 (+4,5) | 12,9 / 17,6 (+4,7) |
| 8893 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 3.651 | 9,1 / 4,8 (-4,3) | 31,7 / 28,0 (-3,7) | 34,5 / 44,0 (+9,5) | 24,7 / 23,2 (-1,5) |
| 8526 · NUTRICIÓN Y DIETÉTICA | 2.443 | 6,3 / 4,0 (-2,2) | 27,3 / 20,5 (-6,8) | 43,0 / 39,8 (-3,2) | 23,5 / 35,6 (+12,2) |
| 8223 · PEDAGOGÍA EN INGLÉS | 5.155 | 6,0 / 4,6 (-1,4) | 27,1 / 19,5 (-7,6) | 34,2 / 39,0 (+4,8) | 32,7 / 36,9 (+4,2) |
| 8906 · KINESIOLOGÍA | 3.744 | 4,7 / 3,0 (-1,7) | 33,7 / 19,9 (-13,7) | 43,6 / 43,2 (-0,4) | 18,0 / 33,9 (+15,9) |
| 8783 · PEDAGOGÍA EN EDUCACIÓN BÁSICA CON ESPECIALIZACIÓN | 2.817 | 4,7 / 3,7 (-1,0) | 15,8 / 12,1 (-3,7) | 34,6 / 33,4 (-1,2) | 44,8 / 50,8 (+5,9) |
| 8353 · PERIODISMO | 3.213 | 4,6 / 2,8 (-1,8) | 18,4 / 14,6 (-3,9) | 40,1 / 44,7 (+4,5) | 36,8 / 38,0 (+1,2) |
| 8176 · PEDAGOGÍA EN EDUCACIÓN DIFERENCIAL CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 2.410 | 4,5 / 4,1 (-0,4) | 14,6 / 18,2 (+3,6) | 38,0 / 43,1 (+5,0) | 42,9 / 34,7 (-8,3) |
| 8163 · PEDAGOGÍA EN EDUCACIÓN PARVULARIA CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 1.432 | 4,5 / 3,4 (-1,1) | 21,9 / 13,0 (-8,9) | 43,8 / 46,1 (+2,3) | 29,9 / 37,6 (+7,7) |
| 8173 · PEDAGOGÍA EN EDUCACIÓN DIFERENCIAL CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 1.187 | 4,4 / 3,9 (-0,5) | 13,1 / 12,8 (-0,3) | 37,7 / 41,7 (+4,0) | 44,8 / 41,6 (-3,2) |
| 8516 · ENFERMERÍA | 3.602 | 4,2 / 3,1 (-1,1) | 25,5 / 17,1 (-8,5) | 45,9 / 39,4 (-6,5) | 24,4 / 40,5 (+16,0) |
| 8383 · PSICOLOGÍA | 7.429 | 2,3 / 2,3 (-0,1) | 20,6 / 12,6 (-8,0) | 44,7 / 41,5 (-3,2) | 32,4 / 43,7 (+11,3) |
| 8486 · MEDICINA | 7.009 | 1,8 / 0,8 (-0,9) | 9,4 / 7,5 (-2,0) | 44,8 / 33,2 (-11,6) | 44,0 / 58,5 (+14,5) |

**Facultades, por banda** (nombre de la facultad; % observado, % esperado y brecha con intervalos):

**Reprobado (< 4,0)**

| Facultad | Intentos | % observado | % esperado (modelo) | Brecha (pp, pred. − obs.) | Brecha de la frecuencia global (pp) |
|---|---|---|---|---|---|
| Facultad de Ciencias de Ingeniería y Construcción | 7.464 | 23,5 % [21,4; 25,8] | 20,1 % [18,9; 21,3] | -3,4 [-4,7; -2,1] | -7,1 [-9,4; -5,0] |
| Facultad de Ciencias | 10.331 | 19,9 % [18,4; 21,6] | 15,6 % [14,6; 16,5] | -4,3 [-5,3; -3,5] | -3,5 [-5,2; -2,1] |
| Facultad de Ciencias Jurídicas | 21.756 | 19,4 % [18,3; 20,5] | 13,4 % [12,9; 13,8] | -6,1 [-6,8; -5,3] | -3,1 [-4,1; -1,9] |
| Facultad de Ingeniería y Ciencias Geológicas | 61.861 | 17,9 % [17,2; 18,6] | 13,4 % [13,1; 13,8] | -4,5 [-4,8; -4,0] | -1,5 [-2,2; -0,8] |
| Facultad de Ciencias del Mar | 6.974 | 16,9 % [15,0; 18,9] | 13,1 % [12,1; 14,1] | -3,8 [-5,2; -2,5] | -0,5 [-2,5; +1,3] |
| Escuela de Arquitectura | 6.922 | 15,2 % [13,7; 16,7] | 17,1 % [16,0; 18,1] | +1,9 [+0,8; +2,9] | +1,2 [-0,3; +2,7] |
| Escuela de Ingeniería | 35.201 | 13,9 % [13,2; 14,8] | 10,0 % [9,7; 10,5] | -3,9 [-4,4; -3,4] | +2,4 [+1,6; +3,2] |
| Escuela de Ciencias Empresariales | 18.729 | 13,8 % [12,8; 14,8] | 7,8 % [7,4; 8,2] | -6,0 [-6,7; -5,3] | +2,6 [+1,6; +3,5] |
| Facultad de Economía y Administración | 18.495 | 12,7 % [11,8; 13,8] | 9,6 % [9,1; 10,1] | -3,1 [-3,9; -2,4] | +3,7 [+2,5; +4,6] |
| Escuela de Educación Coquimbo | 2.959 | 6,5 % [4,8; 8,6] | 4,6 % [3,9; 5,5] | -1,9 [-3,7; -0,4] | +9,9 [+7,8; +11,6] |
| Facultad de Educación | 10.591 | 5,3 % [4,5; 6,3] | 4,1 % [3,8; 4,5] | -1,1 [-1,9; -0,5] | +11,1 [+10,1; +11,9] |
| Facultad de Medicina | 16.798 | 3,6 % [3,1; 4,0] | 2,3 % [2,1; 2,4] | -1,3 [-1,7; -1,0] | +12,8 [+12,4; +13,2] |
| Facultad de Humanidades | 10.642 | 3,0 % [2,3; 3,7] | 2,4 % [2,2; 2,7] | -0,6 [-1,2; -0,1] | +13,4 [+12,7; +14,0] |

**Aprobado por Unanimidad (4,0–5,3)**

| Facultad | Intentos | % observado | % esperado (modelo) | Brecha (pp, pred. − obs.) | Brecha de la frecuencia global (pp) |
|---|---|---|---|---|---|
| Escuela de Ingeniería | 35.201 | 44,5 % [43,8; 45,3] | 40,8 % [40,2; 41,4] | -3,7 [-4,4; -3,1] | +1,3 [+0,6; +2,0] |
| Escuela de Arquitectura | 6.922 | 43,7 % [41,9; 45,4] | 40,8 % [39,9; 41,7] | -2,9 [-4,1; -1,5] | +2,2 [+0,4; +4,0] |
| Escuela de Ciencias Empresariales | 18.729 | 43,0 % [41,8; 44,1] | 35,9 % [35,1; 36,9] | -7,0 [-7,9; -6,2] | +2,9 [+1,8; +4,0] |
| Facultad de Ingeniería y Ciencias Geológicas | 61.861 | 42,4 % [41,8; 43,0] | 41,1 % [40,7; 41,6] | -1,2 [-1,7; -0,8] | +3,5 [+2,8; +4,1] |
| Facultad de Ciencias de Ingeniería y Construcción | 7.464 | 42,2 % [40,8; 43,9] | 40,6 % [39,8; 41,4] | -1,6 [-3,0; -0,4] | +3,6 [+2,0; +5,1] |
| Facultad de Ciencias Jurídicas | 21.756 | 41,9 % [41,1; 42,8] | 41,1 % [40,5; 41,6] | -0,9 [-1,6; -0,1] | +3,9 [+3,0; +4,8] |
| Facultad de Ciencias del Mar | 6.974 | 39,5 % [37,7; 41,5] | 35,7 % [34,5; 37,0] | -3,8 [-5,2; -2,5] | +6,3 [+4,3; +8,2] |
| Facultad de Economía y Administración | 18.495 | 38,5 % [37,4; 39,7] | 33,1 % [32,3; 33,9] | -5,4 [-6,2; -4,6] | +7,3 [+6,2; +8,5] |
| Facultad de Ciencias | 10.331 | 37,7 % [36,3; 39,1] | 35,5 % [34,7; 36,2] | -2,2 [-3,4; -0,8] | +8,2 [+6,8; +9,5] |
| Facultad de Educación | 10.591 | 21,8 % [20,6; 23,1] | 15,9 % [15,2; 16,6] | -5,9 [-6,9; -4,9] | +24,0 [+22,7; +25,3] |
| Facultad de Medicina | 16.798 | 20,9 % [19,8; 22,0] | 14,2 % [13,6; 14,8] | -6,7 [-7,4; -6,0] | +25,0 [+23,9; +26,1] |
| Facultad de Humanidades | 10.642 | 19,9 % [18,6; 21,3] | 13,2 % [12,6; 13,7] | -6,8 [-7,8; -5,7] | +25,9 [+24,6; +27,2] |
| Escuela de Educación Coquimbo | 2.959 | 16,6 % [14,4; 18,5] | 18,5 % [17,4; 19,6] | +1,9 [+0,4; +3,4] | +29,3 [+27,3; +31,4] |

**Aprobado con Distinción (5,4–6,3)**

| Facultad | Intentos | % observado | % esperado (modelo) | Brecha (pp, pred. − obs.) | Brecha de la frecuencia global (pp) |
|---|---|---|---|---|---|
| Facultad de Medicina | 16.798 | 44,5 % [43,4; 45,5] | 37,7 % [37,2; 38,2] | -6,8 [-7,9; -5,7] | -17,0 [-18,0; -16,0] |
| Facultad de Humanidades | 10.642 | 43,3 % [42,1; 44,6] | 42,4 % [41,7; 43,1] | -0,9 [-2,1; +0,2] | -15,9 [-17,1; -14,6] |
| Escuela de Educación Coquimbo | 2.959 | 36,9 % [34,8; 39,0] | 42,3 % [41,6; 42,8] | +5,4 [+3,5; +7,3] | -9,4 [-11,5; -7,3] |
| Facultad de Educación | 10.591 | 36,0 % [34,8; 37,2] | 38,8 % [38,2; 39,3] | +2,8 [+1,7; +3,9] | -8,5 [-9,7; -7,3] |
| Facultad de Ciencias del Mar | 6.974 | 29,9 % [28,3; 31,5] | 32,8 % [31,9; 33,8] | +2,9 [+1,6; +4,3] | -2,4 [-4,0; -0,8] |
| Escuela de Arquitectura | 6.922 | 29,3 % [27,7; 31,0] | 31,0 % [30,0; 32,1] | +1,7 [+0,6; +2,7] | -1,9 [-3,5; -0,2] |
| Facultad de Economía y Administración | 18.495 | 28,5 % [27,6; 29,3] | 35,9 % [35,4; 36,5] | +7,4 [+6,7; +8,1] | -1,0 [-1,8; -0,1] |
| Escuela de Ingeniería | 35.201 | 28,2 % [27,6; 28,9] | 32,7 % [32,3; 33,1] | +4,4 [+3,9; +4,9] | -0,7 [-1,4; -0,1] |
| Escuela de Ciencias Empresariales | 18.729 | 27,1 % [26,1; 28,1] | 35,0 % [34,5; 35,5] | +7,9 [+7,1; +8,7] | +0,4 [-0,6; +1,4] |
| Facultad de Ingeniería y Ciencias Geológicas | 61.861 | 26,8 % [26,3; 27,4] | 31,0 % [30,6; 31,4] | +4,2 [+3,8; +4,5] | +0,7 [+0,1; +1,2] |
| Facultad de Ciencias | 10.331 | 25,2 % [24,0; 26,4] | 31,1 % [30,3; 32,0] | +6,0 [+4,9; +7,0] | +2,3 [+1,1; +3,5] |
| Facultad de Ciencias de Ingeniería y Construcción | 7.464 | 24,3 % [22,8; 25,7] | 28,0 % [27,1; 28,9] | +3,7 [+2,6; +4,7] | +3,2 [+1,8; +4,7] |
| Facultad de Ciencias Jurídicas | 21.756 | 23,3 % [22,5; 24,1] | 30,4 % [29,9; 30,9] | +7,1 [+6,5; +7,7] | +4,2 [+3,4; +5,0] |

**Aprobado con Máxima Distinción (6,4–7,0)**

| Facultad | Intentos | % observado | % esperado (modelo) | Brecha (pp, pred. − obs.) | Brecha de la frecuencia global (pp) |
|---|---|---|---|---|---|
| Escuela de Educación Coquimbo | 2.959 | 40,0 % [36,9; 43,1] | 34,6 % [32,9; 36,2] | -5,4 [-7,7; -3,2] | -29,7 [-32,9; -26,6] |
| Facultad de Educación | 10.591 | 36,9 % [35,2; 38,5] | 41,2 % [39,9; 42,5] | +4,3 [+3,1; +5,5] | -26,6 [-28,3; -24,9] |
| Facultad de Humanidades | 10.642 | 33,7 % [32,1; 35,5] | 42,0 % [40,7; 43,4] | +8,2 [+7,1; +9,5] | -23,4 [-25,2; -21,8] |
| Facultad de Medicina | 16.798 | 31,0 % [29,8; 32,3] | 45,8 % [44,7; 46,9] | +14,8 [+13,9; +15,7] | -20,7 [-22,0; -19,5] |
| Facultad de Economía y Administración | 18.495 | 20,3 % [19,2; 21,4] | 21,4 % [20,6; 22,3] | +1,2 [+0,5; +1,7] | -10,0 [-11,1; -8,9] |
| Facultad de Ciencias | 10.331 | 17,3 % [16,1; 18,5] | 17,9 % [17,0; 18,7] | +0,6 [-0,2; +1,3] | -7,0 [-8,2; -5,9] |
| Escuela de Ciencias Empresariales | 18.729 | 16,1 % [15,2; 17,0] | 21,3 % [20,4; 22,0] | +5,1 [+4,6; +5,7] | -5,8 [-6,7; -4,9] |
| Facultad de Ciencias Jurídicas | 21.756 | 15,3 % [14,7; 16,1] | 15,2 % [14,8; 15,7] | -0,1 [-0,6; +0,3] | -5,0 [-5,8; -4,4] |
| Facultad de Ciencias del Mar | 6.974 | 13,7 % [12,3; 15,1] | 18,4 % [17,1; 19,6] | +4,7 [+3,9; +5,5] | -3,4 [-4,8; -2,0] |
| Escuela de Ingeniería | 35.201 | 13,3 % [12,8; 13,9] | 16,5 % [16,0; 17,0] | +3,2 [+2,8; +3,5] | -3,0 [-3,6; -2,5] |
| Facultad de Ingeniería y Ciencias Geológicas | 61.861 | 12,9 % [12,5; 13,4] | 14,4 % [14,1; 14,8] | +1,5 [+1,2; +1,8] | -2,6 [-3,1; -2,2] |
| Escuela de Arquitectura | 6.922 | 11,8 % [10,8; 12,9] | 11,1 % [10,4; 11,8] | -0,7 [-1,4; +0,0] | -1,5 [-2,7; -0,5] |
| Facultad de Ciencias de Ingeniería y Construcción | 7.464 | 9,9 % [9,1; 10,8] | 11,3 % [10,8; 11,9] | +1,4 [+0,6; +2,1] | +0,3 [-0,5; +1,2] |

**Mayores y menores.** Posiciones por % observado de reprobados y por % esperado (programas y facultades):

| Posición | Mayor % de reprobados observado | Mayor % esperado | Menor % observado | Menor % esperado |
|---|---|---|---|---|
| 1 | 8953 · INGENIERÍA CIVIL ELECTRÓNICA | 8103 · LICENCIATURA EN FÍSICA CON MENCIÓN EN ASTRONOMÍA | 8486 · MEDICINA | 8486 · MEDICINA |
| 2 | 8643 · INGENIERÍA CIVIL PLAN COMÚN | 8643 · INGENIERÍA CIVIL PLAN COMÚN | 8383 · PSICOLOGÍA | 8383 · PSICOLOGÍA |
| 3 | 8963 · INGENIERÍA CIVIL EN ENERGÍA | 8693 · INGENIERÍA CIVIL | 8516 · ENFERMERÍA | 8353 · PERIODISMO |
| 4 | 8103 · LICENCIATURA EN FÍSICA CON MENCIÓN EN ASTRONOMÍA | 8453 · ANALISTA QUÍMICO | 8173 · PEDAGOGÍA EN EDUCACIÓN DIFERENCIAL CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 8906 · KINESIOLOGÍA |
| 5 | 8693 · INGENIERÍA CIVIL | 8953 · INGENIERÍA CIVIL ELECTRÓNICA | 8163 · PEDAGOGÍA EN EDUCACIÓN PARVULARIA CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 8516 · ENFERMERÍA |

| Posición | Mayor % de reprobados observado | Mayor % esperado | Menor % observado | Menor % esperado |
|---|---|---|---|---|
| 1 | Facultad de Ciencias de Ingeniería y Construcción | Facultad de Ciencias de Ingeniería y Construcción | Facultad de Humanidades | Facultad de Medicina |
| 2 | Facultad de Ciencias | Escuela de Arquitectura | Facultad de Medicina | Facultad de Humanidades |
| 3 | Facultad de Ciencias Jurídicas | Facultad de Ciencias | Facultad de Educación | Facultad de Educación |
| 4 | Facultad de Ingeniería y Ciencias Geológicas | Facultad de Ingeniería y Ciencias Geológicas | Escuela de Educación Coquimbo | Escuela de Educación Coquimbo |
| 5 | Facultad de Ciencias del Mar | Facultad de Ciencias Jurídicas | Facultad de Economía y Administración | Escuela de Ciencias Empresariales |

**Pronóstico agregado con eliminación y cambio de programa.** Para cada grupo, el % esperado por banda (entre paréntesis lo observado), el % que sería **eliminado** (T5, k = 2; con la etiqueta actual y la efectiva sin reintegro) y el % con **cambio de programa** (T4, k = 2), tomados de `11_benchmark_t4_t5.md` solo donde ese informe reporta el grupo (n ≥ 100 y ≥ 10 eventos); «—» es un grupo no reportable allí. **Advertencia sobre T4:** el modelo conservado de T4 con `k` = 2 (logística) sobreestima la tasa de transición en unos siete puntos (11_benchmark_t4_t5.md §5), de modo que el % esperado de cambio de programa **no es utilizable** como pronóstico (compárese el valor esperado con el observado entre paréntesis).

Por programa:

| Programa | Intentos (T2) | % reprobado | % unanimidad | % distinción | % máx. distinción | % eliminado (T5, k = 2) | % elimin. efectiva (T5, sin reintegro) | % con cambio de programa (T4, k = 2) |
|---|---|---|---|---|---|---|---|---|
| 8103 · LICENCIATURA EN FÍSICA CON MENCIÓN EN ASTRONOMÍA | 1.583 | 28,2 (33,0) | 42,7 (34,8) | 19,4 (18,1) | 9,7 (14,2) | — | — | — |
| 8643 · INGENIERÍA CIVIL PLAN COMÚN | 841 | 27,7 (34,4) | 33,9 (31,6) | 25,5 (21,0) | 12,9 (13,0) | — | — | — |
| 8693 · INGENIERÍA CIVIL | 3.383 | 25,5 (32,4) | 40,1 (37,5) | 24,6 (21,2) | 9,8 (8,9) | — | — | — |
| 8453 · ANALISTA QUÍMICO | 527 | 24,6 (26,8) | 39,6 (39,5) | 26,4 (23,9) | 9,4 (9,9) | — | — | — |
| 8953 · INGENIERÍA CIVIL ELECTRÓNICA | 549 | 23,5 (34,6) | 32,5 (30,4) | 28,4 (20,6) | 15,5 (14,4) | — | — | — |
| 8293 · QUÍMICA INDUSTRIAL | 633 | 21,4 (22,9) | 38,0 (39,7) | 27,4 (21,3) | 13,1 (16,1) | — | — | — |
| 8963 · INGENIERÍA CIVIL EN ENERGÍA | 245 | 21,2 (33,1) | 31,5 (25,7) | 30,0 (24,5) | 17,3 (16,7) | — | — | — |
| 8506 · INGENIERÍA EN PREVENCION DE RIESGOS Y MEDIOAMBIENTE | 2.208 | 20,1 (20,2) | 42,2 (44,5) | 25,8 (25,7) | 11,8 (9,6) | — | — | — |
| 8253 · INGENIERÍA EN PROCESOS QUÍMICOS | 288 | 18,6 (21,9) | 40,4 (39,2) | 28,1 (22,9) | 12,9 (16,0) | — | — | — |
| 8973 · INGENIERÍA CIVIL EN GESTIÓN DE LA CONSTRUCCION | 1.032 | 17,3 (19,9) | 38,6 (40,1) | 31,2 (28,9) | 13,0 (11,1) | — | — | — |
| 8853 · LICENCIATURA EN MATEMÁTICA | 192 | 17,2 (14,6) | 37,7 (38,5) | 26,8 (23,4) | 18,2 (23,4) | — | — | — |
| 8213 · ARQUITECTURA | 6.922 | 17,1 (15,2) | 40,8 (43,7) | 31,0 (29,3) | 11,1 (11,8) | 12,0 (7,7) | — | — |
| 8243 · INGENIERÍA EN METALURGIA | 1.631 | 16,6 (18,2) | 46,8 (49,5) | 27,0 (24,2) | 9,5 (8,1) | — | — | — |
| 8653 · INGENIERÍA CIVIL DE MINAS | 9.006 | 16,2 (20,0) | 49,5 (48,5) | 24,4 (21,9) | 9,9 (9,5) | 14,4 (19,3) | 10,9 (12,0) | — |
| 8683 · INGENIERÍA CIVIL METALÚRGICA | 4.963 | 15,8 (21,1) | 44,3 (45,2) | 28,0 (23,6) | 11,9 (10,2) | — | — | — |
| 8673 · INGENIERÍA EN CONSTRUCCIÓN | 3.029 | 15,2 (15,1) | 41,9 (48,3) | 30,6 (26,0) | 12,3 (10,6) | — | — | — |
| 8403 · GEOLOGÍA | 6.375 | 14,8 (20,7) | 38,1 (41,5) | 31,1 (23,3) | 16,0 (14,4) | 12,8 (16,3) | 10,6 (12,2) | — |
| 8233 · INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 5.564 | 14,7 (15,5) | 40,2 (41,2) | 31,8 (29,5) | 13,3 (13,8) | 13,8 (9,3) | 10,7 (6,6) | — |
| 8466 · INGENIERÍA EN ACUICULTURA | 918 | 14,4 (21,9) | 40,3 (42,0) | 31,4 (24,5) | 13,9 (11,5) | — | — | — |
| 8373 · DERECHO | 10.545 | 13,8 (20,0) | 39,4 (41,0) | 32,1 (24,0) | 14,8 (15,0) | 8,8 (8,5) | 7,7 (4,2) | 15,4 (5,9) |
| 8553 · INGENIERÍA CIVIL EN QUÍMICA | 2.900 | 13,5 (17,1) | 45,1 (45,3) | 28,7 (25,0) | 12,7 (12,6) | — | — | — |
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 9.952 | 13,1 (20,1) | 36,8 (37,5) | 33,5 (27,5) | 16,6 (14,9) | 13,6 (17,5) | 11,1 (10,0) | 27,4 (6,5) |
| 8376 · DERECHO | 11.211 | 13,0 (18,9) | 42,6 (42,9) | 28,8 (22,6) | 15,6 (15,6) | 7,9 (9,1) | 7,5 (7,6) | — |
| 8266 · INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 4.966 | 12,8 (20,6) | 44,6 (41,9) | 29,5 (26,0) | 13,2 (11,5) | 9,2 (14,5) | — | — |
| 8843 · PEDAGOGÍA EN MATEMÁTICA EN EDUCACIÓN MEDIA | 1.679 | 11,9 (16,7) | 27,5 (26,7) | 31,2 (27,8) | 29,4 (28,8) | — | — | — |
| 8313 · CONTADOR AUDITOR - CONTADOR PÚBLICO VESPERTINO | 803 | 11,6 (12,2) | 39,1 (41,1) | 33,0 (29,8) | 16,3 (16,9) | — | — | — |
| 8483 · QUÍMICA Y FARMACIA | 5.717 | 11,6 (16,4) | 35,1 (41,2) | 35,3 (27,0) | 18,0 (15,4) | 9,5 (9,0) | 7,8 (8,2) | — |
| 8333 · CONTADOR AUDITOR - CONTADOR PÚBLICO | 2.874 | 11,0 (13,5) | 35,2 (41,9) | 35,1 (27,6) | 18,7 (17,0) | — | — | — |
| 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 11.706 | 10,7 (14,3) | 40,8 (43,5) | 32,3 (27,5) | 16,1 (14,8) | 9,3 (12,1) | 7,2 (9,5) | 14,8 (5,0) |
| 8323 · INGENIERÍA COMERCIAL | 11.167 | 10,6 (13,7) | 33,8 (39,7) | 33,7 (26,7) | 22,0 (19,9) | 12,0 (13,3) | 9,7 (7,9) | — |
| 8623 · INGENIERÍA CIVIL AMBIENTAL | 2.414 | 9,7 (12,3) | 43,0 (42,8) | 32,8 (29,7) | 14,5 (15,1) | — | — | — |
| 8613 · INGENIERÍA CIVIL INDUSTRIAL | 17.097 | 9,6 (13,6) | 39,0 (41,8) | 34,6 (31,1) | 16,8 (13,5) | 9,2 (7,4) | 7,3 (5,3) | — |
| 8326 · INGENIERÍA COMERCIAL | 11.769 | 9,2 (13,5) | 36,9 (43,0) | 32,7 (26,3) | 21,2 (17,2) | 6,4 (8,8) | 5,3 (5,0) | — |
| 8616 · INGENIERÍA CIVIL INDUSTRIAL | 18.529 | 8,9 (11,9) | 39,8 (45,9) | 33,8 (29,3) | 17,6 (12,9) | 5,4 (5,4) | — | — |
| 8456 · BIOLOGÍA MARINA | 3.848 | 8,8 (13,8) | 30,9 (36,1) | 37,2 (33,6) | 23,2 (16,5) | — | — | — |
| 8716 · PEDAGOGÍA EN FILOSOFÍA Y RELIGIÓN | 549 | 7,0 (15,5) | 19,8 (25,3) | 38,9 (32,1) | 34,2 (27,1) | — | — | — |
| 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 6.960 | 5,4 (14,4) | 34,2 (42,9) | 38,9 (28,5) | 21,4 (14,3) | 13,4 (15,0) | 11,2 (12,9) | — |
| 8893 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 3.651 | 4,8 (9,1) | 28,0 (31,7) | 44,0 (34,5) | 23,2 (24,7) | — | — | — |
| 8223 · PEDAGOGÍA EN INGLÉS | 5.155 | 4,6 (6,0) | 19,5 (27,1) | 39,0 (34,2) | 36,9 (32,7) | — | — | — |
| 8176 · PEDAGOGÍA EN EDUCACIÓN DIFERENCIAL CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 2.410 | 4,1 (4,5) | 18,2 (14,6) | 43,1 (38,0) | 34,7 (42,9) | — | — | — |
| 8526 · NUTRICIÓN Y DIETÉTICA | 2.443 | 4,0 (6,3) | 20,5 (27,3) | 39,8 (43,0) | 35,6 (23,5) | — | — | — |
| 8173 · PEDAGOGÍA EN EDUCACIÓN DIFERENCIAL CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 1.187 | 3,9 (4,4) | 12,8 (13,1) | 41,7 (37,7) | 41,6 (44,8) | — | — | — |
| 8783 · PEDAGOGÍA EN EDUCACIÓN BÁSICA CON ESPECIALIZACIÓN | 2.817 | 3,7 (4,7) | 12,1 (15,8) | 33,4 (34,6) | 50,8 (44,8) | — | — | — |
| 8163 · PEDAGOGÍA EN EDUCACIÓN PARVULARIA CON MENCIÓN EN DESARROLLO EMOCIONAL Y COGNITIVO | 1.432 | 3,4 (4,5) | 13,0 (21,9) | 46,1 (43,8) | 37,6 (29,9) | — | — | — |
| 8516 · ENFERMERÍA | 3.602 | 3,1 (4,2) | 17,1 (25,5) | 39,4 (45,9) | 40,5 (24,4) | — | — | — |
| 8906 · KINESIOLOGÍA | 3.744 | 3,0 (4,7) | 19,9 (33,7) | 43,2 (43,6) | 33,9 (18,0) | — | — | — |
| 8353 · PERIODISMO | 3.213 | 2,8 (4,6) | 14,6 (18,4) | 44,7 (40,1) | 38,0 (36,8) | — | — | — |
| 8383 · PSICOLOGÍA | 7.429 | 2,3 (2,3) | 12,6 (20,6) | 41,5 (44,7) | 43,7 (32,4) | — | — | — |
| 8486 · MEDICINA | 7.009 | 0,8 (1,8) | 7,5 (9,4) | 33,2 (44,8) | 58,5 (44,0) | — | — | — |

Por facultad:

| Facultad | Intentos (T2) | % reprobado | % unanimidad | % distinción | % máx. distinción | % eliminado (T5, k = 2) | % elimin. efectiva (T5, sin reintegro) | % con cambio de programa (T4, k = 2) |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ciencias de Ingeniería y Construcción | 7.464 | 20,1 (23,5) | 40,6 (42,2) | 28,0 (24,3) | 11,3 (9,9) | 14,8 (16,4) | 11,9 (11,1) | — |
| Escuela de Arquitectura | 6.922 | 17,1 (15,2) | 40,8 (43,7) | 31,0 (29,3) | 11,1 (11,8) | 12,0 (7,7) | — | — |
| Facultad de Ciencias | 10.331 | 15,6 (19,9) | 35,5 (37,7) | 31,1 (25,2) | 17,9 (17,3) | 11,6 (7,6) | 9,4 (5,6) | — |
| Facultad de Ingeniería y Ciencias Geológicas | 61.861 | 13,4 (17,9) | 41,1 (42,4) | 31,0 (26,8) | 14,4 (12,9) | 12,8 (13,6) | 10,0 (9,0) | 14,6 (3,9) |
| Facultad de Ciencias Jurídicas | 21.756 | 13,4 (19,4) | 41,1 (41,9) | 30,4 (23,3) | 15,2 (15,3) | 8,3 (8,8) | 7,6 (6,0) | 7,8 (3,8) |
| Facultad de Ciencias del Mar | 6.974 | 13,1 (16,9) | 35,7 (39,5) | 32,8 (29,9) | 18,4 (13,7) | 12,2 (10,8) | 10,0 (9,7) | — |
| Escuela de Ingeniería | 35.201 | 10,0 (13,9) | 40,8 (44,5) | 32,7 (28,2) | 16,5 (13,3) | 7,5 (9,5) | 6,1 (6,3) | 9,8 (2,8) |
| Facultad de Economía y Administración | 18.495 | 9,6 (12,7) | 33,1 (38,5) | 35,9 (28,5) | 21,4 (20,3) | 10,2 (10,6) | 8,4 (6,9) | 9,7 (2,7) |
| Escuela de Ciencias Empresariales | 18.729 | 7,8 (13,8) | 35,9 (43,0) | 35,0 (27,1) | 21,3 (16,1) | 8,8 (11,0) | 7,4 (7,8) | 2,6 (2,5) |
| Escuela de Educación Coquimbo | 2.959 | 4,6 (6,5) | 18,5 (16,6) | 42,3 (36,9) | 34,6 (40,0) | — | — | — |
| Facultad de Educación | 10.591 | 4,1 (5,3) | 15,9 (21,8) | 38,8 (36,0) | 41,2 (36,9) | 4,1 (3,9) | — | — |
| Facultad de Humanidades | 10.642 | 2,4 (3,0) | 13,2 (19,9) | 42,4 (43,3) | 42,0 (33,7) | — | — | — |
| Facultad de Medicina | 16.798 | 2,3 (3,6) | 14,2 (20,9) | 37,7 (44,5) | 45,8 (31,0) | 4,0 (4,5) | 3,8 (4,5) | — |

## 12c. Ablación de estadística reciente (P55)

La tasa de aprobación de los cursos no es estacionaria (§2, D80). Se comparan tres formas de calcular las siete estadísticas del curso del conjunto (c), siempre con períodos estrictamente anteriores al de la fila y con el mismo modelo, semillas y particiones: (1) la **historia expansiva** (defecto actual), (2) **decaimiento exponencial** con vida media de 2 años y (3) una **ventana** de los últimos 3 años. Las estadísticas se recalculan desde los agregados por (curso, programa, período) y la prueba de que no usan el futuro compara contra un cálculo directo.

| Partición | Modelo | AP reprobación | ROC-AUC | Brier | ECE |
|---|---|---|---|---|---|
| valid | CatBoost (c) + prerrequisitos | 0,493 [0,485; 0,502] | 0,849 [0,846; 0,852] | 0,0889 [0,0875; 0,0904] | 0,013 [0,012; 0,015] |
| valid | CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 0,502 [0,494; 0,512] | 0,851 [0,848; 0,854] | 0,0883 [0,0869; 0,0898] | 0,018 [0,016; 0,020] |
| valid | CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0,492 [0,484; 0,501] | 0,846 [0,843; 0,849] | 0,0897 [0,0883; 0,0912] | 0,023 [0,022; 0,025] |
| test | CatBoost (c) + prerrequisitos | 0,534 [0,527; 0,541] | 0,859 [0,856; 0,861] | 0,0924 [0,0910; 0,0938] | 0,031 [0,029; 0,032] |
| test | CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 0,545 [0,538; 0,552] | 0,863 [0,861; 0,866] | 0,0910 [0,0896; 0,0923] | 0,028 [0,026; 0,030] |
| test | CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0,545 [0,538; 0,553] | 0,865 [0,863; 0,868] | 0,0910 [0,0896; 0,0923] | 0,029 [0,027; 0,031] |
| posterior | CatBoost (c) + prerrequisitos | 0,593 [0,583; 0,603] | 0,867 [0,864; 0,871] | 0,1037 [0,1018; 0,1057] | 0,044 [0,042; 0,047] |
| posterior | CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) | 0,601 [0,592; 0,611] | 0,871 [0,868; 0,874] | 0,1020 [0,1001; 0,1039] | 0,041 [0,038; 0,043] |
| posterior | CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0,602 [0,592; 0,612] | 0,872 [0,869; 0,875] | 0,1014 [0,0996; 0,1033] | 0,038 [0,036; 0,041] |

| Diferencia pareada de AP (A − B) | valid | test | posterior | ¿El intervalo de test excluye 0? |
|---|---|---|---|---|
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) − CatBoost (c) + prerrequisitos | 0,009 [0,008; 0,010] | 0,011 [0,010; 0,013] | 0,009 [0,007; 0,011] | sí |
| CatBoost (c) con estadísticas del curso en ventana reciente (P55) − CatBoost (c) + prerrequisitos | -0,002 [-0,004; 0,000] | 0,011 [0,009; 0,013] | 0,010 [0,007; 0,012] | sí |
| CatBoost (c) con estadísticas del curso con decaimiento exponencial (P55) − CatBoost (c) con estadísticas del curso en ventana reciente (P55) | 0,010 [0,009; 0,012] | -0,000 [-0,002; 0,001] | -0,001 [-0,003; 0,001] | no |

**Lectura.** Las dos variantes recientes mejoran el AP de test en 0,011 con intervalos que excluyen 0 (sin la banda del cero), mejoran también el ROC-AUC, el Brier y el ECE y la mejoría se repite en 2025. En valid (docencia remota) el decaimiento mejora (+0,009) y la ventana no (−0,002 [−0,004; 0,000]), de modo que la ventana depende más del período evaluado. Decaimiento y ventana no se distinguen en test. **Por la regla fijada de antemano (mantener el defecto salvo que el intervalo excluya 0), el defecto debe cambiar a las estadísticas con decaimiento exponencial** (la más estable entre particiones). En esta corrida el modelo por defecto del código y las bandas de §12b siguen usando la historia expansiva; el cambio requiere repetir T2 completo y queda propuesto, no aplicado, a la espera de confirmación.

## 13. Limitaciones

1. **Cambio de nivel y de régimen.** La reprobación pasa de 17,4 % (train) a 13,7 % (valid, docencia remota) y vuelve a 15,9-17,2 %. Los modelos paran con valid, lo que subestima el riesgo en test; la comparación entre modelos es válida (mismos datos), el nivel absoluto de las probabilidades no (§9). 202020 y 202110 tienen 11,4 % y se conservan en train y valid.
2. **Períodos 201920 y 202010.** Excluidos como unidades (P58, respondida): en pandemia la reprobación no contaba como oportunidad y no se registró. Consecuencia: los conteos de reprobaciones previas del estudiante omiten esos dos semestres; no es recuperable con los datos disponibles.
3. **Carga del período aproximada** (P53) y **duplicados de intento** (P54): ver §1.
4. **Mallas y catálogo.** El 1,4 % de los intentos no tiene el curso en la malla; las equivalencias entre catálogos no se mapean (P57). El grafo de prerrequisitos es por programa + catálogo; el GraphSAGE usa su unión global, lo que mezcla programas.
5. **Independencia.** La misma persona aparece en varias particiones (válido por ser temporal) y en varios cursos de un semestre; por eso los IC remuestrean (estudiante, período). No se corrige la dependencia entre períodos de una misma persona dentro de test.
6. **Ajuste acotado.** Un solo diseño de cada modelo (CatBoost de profundidad 6; red de dos capas ocultas); el `C` de la logística quedó en el borde inferior de la rejilla en (b) y (d) (0,0003; AP casi plano entre 0,0003 y 0,003) y la logística podría mejorar poco con más regularización; la comparación logística/árboles/red depende de esos diseños. Tres semillas por modelo.
7. **GAT no implementado.** Ver §7.
8. **Atributos de nodo.** La tasa de aprobación del nodo se calcula solo con períodos anteriores a 2015 (sin fuga); los cursos nuevos tienen NULL con indicador. El grafo de coinscripción se calcula con train. El GraphSAGE es transductivo sobre un grafo estático.
9. **Contexto docente.** Es una ablación que mide la asociación sección/docente con la reprobación; no debe usarse para evaluar a personas. Cobertura desde 2016.
10. **Equidad.** Solo descriptiva y por sexo; no hay evaluación por vía de ingreso, edad ni otras condiciones.
11. **Evento.** «Reprobación» no distingue abandono del ramo, inasistencia o evaluación final; las renuncias (desde 2025) no son intentos.
12. **Uso.** Resultado de un benchmark técnico; no hay predicciones individuales en la API ni en la Bóveda.

## 14. Recomendación

1. **Modelo técnico de T2:** CatBoost con el conjunto (c) (estudiante + carga + curso + prerrequisitos), o (b) si se prefiere un modelo más simple: la diferencia entre ambos no justifica el costo de mantener las variables de prerrequisitos. Línea base de comparación: tasa histórica expansiva del curso.
2. **No adoptar GraphSAGE/GNN para T2:** no supera a las variables puntuales; el costo (grafo, transductivo, mantenimiento) no se compensa.
3. **Contexto docente:** aporta más que el grafo, pero requiere una revisión institucional previa (riesgo de uso para evaluar personas) antes de entrar a cualquier salida.
4. **Calibración:** recalibrar con un período reciente antes de usar probabilidades absolutas.
5. **Pendientes de la DAI:** P53 (inscripciones previas a 2025), P54, P56, P57.
6. **Gate 4:** benchmark técnico completo; aprobación de uso pendiente.


## 15. Reproducibilidad

- Hash del snapshot (`snapshot_t2_resumen.hash_datos`): `bb65853bfc4502a16a225e34d037d7bf69e7b1295c22670aea8d6882f18f4923`. Versión del código (sha256 de `models/`, `evaluation/` y las reglas/variables del snapshot): `cb3f1bfa420e6a03ba48ae2e7195136169b474ec58310677ea4d3a99e6d6b878`.
- Comandos y entorno: `README.md` («Snapshots y benchmark T2»). MLflow: experimento `t2_aprobacion_por_intento` en `mlruns/` (ignorado por git), un run por modelo con parámetros, métricas con IC, hash de los datos y versión del código.
- Las predicciones individuales solo existen en `artefactos/preds/t2_*.npz` (ignorado por git); no hay API ni pantalla para ellas.


## 16. Variables nuevas pedidas por la DAI (18-11-2026)

La DAI pidió agregar a T2 variables que el estudio de viabilidad (`evidencia/viabilidad_variables_2026-11-18.md`, P117–P127) encontró factibles. Se evalúan con la regla única de selección (D114): el modelo conservado se elige en **validación** con AP; un candidato lo reemplaza solo si la diferencia pareada en validación (bootstrap por estudiante-período, el de este informe) tiene un IC de 95 % que excluye 0 a su favor; ante empate gana el más simple; prueba y posterior solo confirman. El conservado era `cb_c` (CatBoost, conjunto c). **Resultado: el candidato `cb_c_nuevas` cumple la regla y pasa a ser el modelo conservado de T2**, con una ganancia pequeña (ver 16.3).

### 16.1 Variables (5 columnas nuevas de `snapshot_t2`, migración 030)

Se calculan con `features_t2._nuevas_t2`, solo con intentos de períodos **estrictamente anteriores** al del intento (la misma búsqueda `previo` que el resto de las variables de historia) y solo con intentos que alimentan las estadísticas de aprobación (evaluados y fuera de 201920 y 202010, P58).

| Variable | Definición |
|---|---|
| `prom_depto` | Promedio de notas del episodio en los ramos del mismo departamento (`cod_depto`) rendidos antes del período. Vacío si no hay historial en el departamento o el departamento del curso no se conoce. |
| `n_depto` | Número de esos intentos previos (0 si el departamento se conoce y no hay historial; vacío si no se conoce). |
| `dif_prom_depto` | `prom_depto` menos el promedio acumulado del episodio (`prom_acum`). |
| `prom_sem_prev` | Promedio de notas del último semestre regular (sufijo 10 o 20) anterior al período en el que el episodio tuvo intentos evaluados. |
| `tasa_sem_prev` | Tasa de aprobación de ese mismo semestre. |

El departamento de un curso es el `cod_depto` que más veces informa `ban_historia_notas` para su código (`materia-curso`); es estático y ningún curso tiene dos códigos (10.048 cursos con departamento; 70 departamentos). Es distinto del `depto` de la malla (códigos de otro sistema) que ya usa el conjunto b. Cobertura en el snapshot reconstruido: `prom_depto` 77,1 % de las filas (el departamento se conoce en 99,9 %; el resto no tiene aún historial en él), `prom_sem_prev` 84,1 %.

**Pruebas** (`tests/unit/test_snapshot_t2_nuevas.py`): el promedio del departamento solo usa intentos anteriores del mismo departamento y del mismo episodio; el semestre previo salta períodos sin intentos y el verano; 201920 y 202010 no alimentan las variables; cambiar o borrar cualquier hecho del período del intento o posterior (incluida la nota del propio intento) deja las 5 columnas iguales. El hash de datos de `snapshot_t2` no cambia (`bb65853b…f4923`): las columnas existentes se reproducen igual al reconstruir.

### 16.2 Resultados (D114)

Misma partición por período que el resto del informe (train hasta 202020, valid 202110–202220, test 202310–202420, posterior desde 202510), mismos hiperparámetros y 3 semillas. El conservado `cb_c` no se reentrenó: se leyeron sus predicciones guardadas (y su IC se reproduce exacto). La columna ΔAP es siempre frente a `cb_c`.

| Modelo | AP valid | ΔAP valid frente a `cb_c` | AP test | ΔAP test | ROC-AUC test | Brier test | AP posterior | ΔAP posterior |
|---|---|---|---|---|---|---|---|---|
| CatBoost conjunto c (conservado) | 0,493 [0,485; 0,502] | — | 0,534 [0,527; 0,541] | — | 0,859 | 0,0924 | 0,593 [0,583; 0,603] | — |
| CatBoost c + variables nuevas | 0,500 [0,492; 0,509] | +0,007 [+0,005; +0,008] | 0,538 [0,531; 0,545] | +0,004 [+0,003; +0,005] | 0,861 | 0,0922 | 0,599 [0,589; 0,609] | +0,006 [+0,005; +0,008] |
| Logística c | 0,474 [0,465; 0,484] | — | 0,499 [0,491; 0,507] | — | 0,848 | 0,0984 | 0,561 [0,549; 0,574] | — |
| Logística c + variables nuevas | 0,480 [0,472; 0,490] | −0,013 [−0,017; −0,009] | 0,506 [0,498; 0,514] | −0,028 [−0,032; −0,024] | 0,850 | 0,0985 | 0,568 [0,558; 0,580] | −0,024 [−0,030; −0,020] |
| CatBoost c + departamento | 0,496 [0,488; 0,505] | +0,002 [+0,001; +0,003] | 0,538 [0,531; 0,545] | +0,004 [+0,003; +0,005] | 0,860 | 0,0921 | 0,594 [0,585; 0,605] | +0,002 [+0,001; +0,003] |
| CatBoost c + semestre previo | 0,501 [0,493; 0,510] | +0,007 [+0,006; +0,008] | 0,536 [0,529; 0,543] | +0,002 [+0,001; +0,003] | 0,860 | 0,0920 | 0,599 [0,589; 0,609] | +0,006 [+0,005; +0,008] |

La logística con variables nuevas gana +0,006 [+0,004; +0,008] de AP sobre la logística (c) en validación (+0,007 en prueba y +0,007 en posterior), pero sigue por debajo de `cb_c`.

**D114.** `cb_c_nuevas` +0,007 [+0,005; +0,008] de AP en validación frente a `cb_c` (el IC excluye 0 a su favor) → **reemplaza**; `lr_c_nuevas` −0,013 [−0,017; −0,009] → no. La prueba y el posterior lo confirman (+0,004 [+0,003; +0,005] y +0,006 [+0,005; +0,008]). Por bloque (diagnóstico, no decide): solo el semestre previo +0,007 [+0,006; +0,008]; solo el departamento +0,002 [+0,001; +0,003].

### 16.3 Qué cambia y qué no

| Métrica | Valid | Prueba | Posterior |
|---|---|---|---|
| ΔAP (`cb_c_nuevas` − `cb_c`) | +0,0066 [+0,0051; +0,0080] | +0,0039 [+0,0027; +0,0052] | +0,0065 [+0,0048; +0,0084] |
| ΔROC-AUC | +0,0029 [+0,0024; +0,0033] | +0,0024 [+0,0019; +0,0028] | +0,0029 [+0,0024; +0,0034] |
| ΔBrier | −0,0005 [−0,0006; −0,0004] | −0,0002 [−0,0003; −0,0001] | −0,0001 [−0,0003; +0,0000] |
| ΔECE | +0,0036 [+0,0034; +0,0038] | +0,0011 [+0,0008; +0,0016] | +0,0031 [+0,0028; +0,0035] |
| ΔRecall@1 por estudiante-período | +0,0026 [−0,0001; +0,0054] | +0,0030 [+0,0004; +0,0058] | +0,0009 [−0,0030; +0,0043] |

- **La ganancia es real pero pequeña** (unos 0,4 a 0,7 puntos de AP sobre 0,49 a 0,59), consistente en los cuatro períodos de prueba (AP por período 0,507 → 0,509, 0,531 → 0,534, 0,545 → 0,549 y 0,560 → 0,568). El intervalo es angosto porque la comparación es pareada sobre 200 mil intentos; no implica una mejora grande para quien use el ranking.
- **La calibración empeora un poco** (ECE +0,001 a +0,004, ya mayor en el posterior: 0,044 → 0,047),, y vale la recomendación 4 del §14: recalibrar con un período reciente antes de usar probabilidades absolutas.
- **Importancia** (media de 3 semillas, CatBoost, % de importancia): `prom_sem_prev` 7,3 (tercera variable del modelo), `prom_depto` 3,1, `n_depto` 0,4, `tasa_sem_prev` 0,4 y `dif_prom_depto` 0,2. El rendimiento reciente es lo que aporta; el departamento aporta poco.
- **Equidad (prueba).** Sin cambio relevante: AP mujeres 0,511 → 0,516 y hombres 0,548 → 0,551; la brecha de calibración por sexo pasa de −0,027 y −0,032 a −0,027 y −0,033.
- **Alcance.** La banda de nota por intento y sus pronósticos por programa y facultad (§12b) usan el modelo de bandas entrenado con el conjunto c y no se reentrenaron; el modelo de bandas no cambia. `cb_d` (con docente o sección) sigue sin ser modelo oficial (revisión institucional).

### 16.4 Conclusión y límites

1. **Cambio de modelo conservado:** `cb_c` → `cb_c_nuevas` (D114). Las predicciones y métricas de los dos candidatos quedan en `artefactos/preds/t2_{valid,test,posterior}.npz` y `artefactos/resultados_t2.json`, junto con los modelos anteriores; las copias previas están en `artefactos/antes_nuevas/`.
2. **Límites.** (i) El departamento es el que informa la historia de notas por curso; si un curso cambió de departamento, se usa el más frecuente. (ii) `prom_depto` solo existe para quien ya cursó otro ramo del departamento (77 % de las filas). (iii) El semestre previo es el último con intentos evaluados, no necesariamente el inmediato (un semestre sin matrícula no cuenta como nota). (iv) La calibración debe revisarse antes de citar probabilidades absolutas.
3. **Reproducción.** `python -m pipelines.migrate` (030), `python -m pipelines.snapshots.t2`, `python -m evaluation.run_nuevas_t2` (agregados en `artefactos/resultados_t2_nuevas.json`) y `python -m evaluation.run_nuevas_t2 --adoptar` (fusiona los candidatos en `resultados_t2.json` y `preds/t2_*.npz`). Pruebas: `tests/unit/test_snapshot_t2_nuevas.py`, `tests/unit/test_run_nuevas_t1.py`.
