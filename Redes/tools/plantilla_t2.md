# DAI Neural — Benchmark T2: aprobación por intento

**Versión:** 0.3 · 13-11-2026 (reconstrucción consolidada, etapa B: variables `mm_*` + prueba, bandas de nota P84, pronósticos agregados P74, ablación de estadística reciente P55) · anterior:  0.1 · 12-11-2026 · Fase 4, benchmark T2. Base: `PROMPT_MAESTRO.md` (Predicción experimental, Evaluación, Fase 4; no negociable 5), `03_reglas_academicas.md`, `05_modelo_datos.md`, `08_benchmark_t1.md` (misma estructura, estándar y herramientas).
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, nota, RUT ni predicción por persona figura en este documento ni en el repositorio.

## Cambios de la reconstrucción consolidada (13-11-2026)

1. **Variables de admisión.** `mm_*` (mínimo–máximo por prueba, año y campo) y `prueba_admision` reemplazan a los percentiles `pct_*` en los conjuntos (a)–(d) de CatBoost, la logística y las redes.
2. **Datos de la etapa A.** El snapshot se reconstruyó con las notas y los intentos corregidos (menos intentos de train y test, tasa de reprobación de test de 0,158 a 0,144).
3. **Banda de nota por intento (P84).** Se reemplazan los cortes anteriores por la escala institucional y se agrega un modelo multiclase (§12b).
4. **Ablación de estadística reciente (P55)** (§12c) y **pronósticos agregados por programa y facultad (P74)** (§12b).

Antes y después de la reconstrucción (test, IC 95 %):

{{tabla:cambios}}

**Qué cambia en las conclusiones.** (i) La conclusión sobre el grafo se **refuerza**: con las variables corregidas los embeddings GraphSAGE empeoran el AP de CatBoost (c) en 0,004 y la red con grafo queda 0,008 por debajo de la misma red sin aristas (antes la diferencia era 0 ± 0,001), es decir, el grafo no solo no aporta sino que perjudica. (ii) Los prerrequisitos explícitos siguen aportando una milésima (0,004 [0,003; 0,005]). (iii) El historial de sección o docente sube de +0,022 a +0,028 de AP. (iv) El mejor CatBoost en valid sigue siendo (d). (v) La línea base baja (AP 0,383 a 0,359) porque la tasa de test baja, y los modelos de aprendizaje mantienen su nivel, de modo que su ventaja sobre la línea base aumenta.

## Resumen

- **Tarea.** Para cada intento evaluado de un estudiante de pregrado en un período regular 2015-2025, ¿reprobará el curso (nota < 4,0)? Momento de predicción: antes de que comience el período, con historia estrictamente anterior más lo conocido en la inscripción. Unidades: {{n:train.n}} intentos de train (2015-2020), {{n:valid.n}} de valid (2021-2022), {{n:test.n}} de test (2023-2024, {{n:test.tasa_reprobacion}} % de reprobación) y {{n:posterior.n}} de 2025 como control posterior.
- **Hallazgo de datos que cambió el benchmark.** En los períodos **201920 y 202010** no hay reprobaciones registradas (0,000 de las notas < 4,0 frente a 14-19 % en los períodos vecinos). Incluirlos como unidades hacía que todos los modelos predijeran la mitad del riesgo real en test y dejaba a CatBoost al nivel de la línea base (corrida inicial descartada, §11b). Se excluyen como unidades y de las estadísticas de aprobación (los créditos y prerrequisitos aprobados sí cuentan). La DAI confirmó el motivo: en pandemia la reprobación no contaba como oportunidad y no se registró (P58, instancia única).
- **Resultado principal (test).** La tasa histórica expansiva del curso discrimina con AP {{v:test.baseline.ap}} (ROC-AUC {{v:test.baseline.roc_auc}}). El desempeño del estudiante y la carga solos aportan poco (CatBoost (a): AP {{v:test.cb_a.ap}}); la estadística del curso es lo que más aporta: CatBoost (b) llega a AP {{v:test.cb_b.ap}} y ROC-AUC {{v:test.cb_b.roc_auc}}. Con el historial de sección/docente (ablación, 2016+) sube a {{v:test.cb_d.ap}}.
- **¿Aporta el grafo curricular?** **Casi nada.** Los prerrequisitos explícitos (c − b) cambian el AP de test en {{d:test.cb_c.cb_b.ap}} con CatBoost y en {{d:test.lr_c.lr_b.ap}} con logística (en valid, con CatBoost, {{d:valid.cb_c.cb_b.ap}}). Los embeddings GraphSAGE autosupervisados (d′ − c) cambian el AP en {{d:test.cb_cemb.cb_c.ap}}. La red extremo a extremo con GraphSAGE no supera a la misma red con los mismos atributos del curso sin aristas ({{d:test.nn_gnn.nn_mlp.ap}}) ni a la red sin representación del curso ({{d:test.nn_gnn.nn_ninguno.ap}}), y queda por debajo de CatBoost (c) ({{d:test.nn_gnn.cb_c.ap}}). Las diferencias son del orden de 0,005 de AP o menores, comparables a la variación entre semillas (0,002-0,009) y de signo cambiante entre particiones.
- **Ranking de cursos dentro de (estudiante, período).** El orden al azar da Recall@1 0,188; la línea base {{v:test.baseline.recall_at_1}}; CatBoost (c) {{v:test.cb_c.recall_at_1}} y con docente {{v:test.cb_d.recall_at_1}}. Los modelos sin estadística del curso (a) ordenan casi como el azar ({{v:test.cb_a.recall_at_1}}), porque dentro de un mismo estudiante solo el curso distingue los riesgos.
- **Calibración y estabilidad.** Los modelos de árboles quedan razonablemente calibrados (ECE {{v:test.cb_c.ece}} en test) pero subestiman el riesgo en conjunto (riesgo medio ≈ 0,114 frente a 0,144 observado), porque se detienen con valid, cuyo nivel (13,4 %, docencia remota) es menor que el de test. La tasa de reprobación no es estacionaria (11,4 % en 202020 y 202110; de 12,3 % a 18,1 % desde 2023).
- **Equidad (descriptiva).** Las mujeres reprueban menos (13,4 % frente a 17,7 % en test) y los modelos las ubican con menor riesgo; el AP es algo menor en mujeres con todos los modelos; `sexo` nunca es variable del modelo.
- **Costo.** El benchmark completo (14 modelos, 3 semillas, bootstrap) tarda {{meta:segundos}} s; las redes se entrenan en 11-16 s en la RTX 4060 (pico de 317 MB de GPU); el pico de RAM del proceso es {{meta:ram}} MB.
- **Estadística reciente (P55).** Calcular las estadísticas del curso con decaimiento exponencial (vida media de 2 años) o con una ventana de 3 años mejora el AP de test de CatBoost (c) en {{d:test.cb_c_decay.cb_c.ap}} y {{d:test.cb_c_vent.cb_c.ap}}; los dos intervalos **excluyen 0** y las dos variantes no se distinguen entre sí ({{d:test.cb_c_decay.cb_c_vent.ap}}). Por la regla fijada (cambiar el defecto solo si el intervalo excluye 0), la variante reciente **debe reemplazar** a la historia expansiva; el cambio del modelo por defecto queda pendiente de confirmación (§12c).
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

{{tabla:embudo}}

### Particiones y tasas base

{{tabla:split}}

Tasa de reprobación por período (todas las particiones):

{{tabla:periodos}}

Por número de oportunidad (intentos y tasa de reprobación):

{{tabla:oportunidad}}

### Cobertura de las variables del grafo y del docente

{{tabla:cobertura}}

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

{{tabla:modelos.test}}

Lectura: (i) la logística y CatBoost con la estadística del curso superan con claridad a la tasa histórica (CatBoost (b) − línea base: ΔAP {{d:test.cb_b.baseline.ap}}); (ii) CatBoost supera a la logística con el mismo conjunto ((c): ΔAP {{d:test.cb_c.lr_c.ap}}); (iii) la red extremo a extremo queda entre ambos ({{v:test.nn_gnn_prereq.ap}} con GraphSAGE de prerrequisitos). Sin las variables del curso, (a) casi no mejora a la línea base: lo que predice la reprobación es qué curso se cursa y cómo le ha ido al estudiante, no la carga ni el perfil de ingreso por sí solos.

### 5.2 Validación (2021-2022)

{{tabla:modelos.valid}}

El orden de los modelos es el mismo que en test. Valid se usa para parar el entrenamiento y es el período de docencia remota (13,7 % de reprobación), de modo que su nivel no es comparable con el de test.

### 5.3 2025 (control posterior, nunca usado para decisiones)

{{tabla:modelos.posterior}}

El AP sube en 2025 (la tasa base sube a 17,2 %) y el orden de los modelos se mantiene. La calibración se degrada un poco (ECE de CatBoost (c): {{v:posterior.cb_c.ece}}). Bootstrap de 300 remuestreos.

### 5.4 Variación entre semillas de las redes

{{tabla:semillas}}

La desviación entre semillas (0,002-0,009 de AP) es del mismo orden que las diferencias entre variantes de la red; por eso las variantes no se distinguen entre sí con claridad (§7). Las épocas óptimas varían entre 0,3 y 3,1: con la evaluación en valid cada 40 pasos el modelo se detiene temprano, lo que refleja el cambio de nivel entre train y valid más que un sobreajuste clásico.

## 6. Ablación: estudiante, curso, prerrequisitos, docente

Test (los mismos intentos en cada escalón; en (d) las variables de docente están en NULL donde la oferta no cubre la sección):

{{tabla:ablacion.test}}

Diferencias pareadas de test (todas las comparaciones, con IC; el signo es A − B):

{{tabla:deltas.test}}

- **Curso (a a b)**: el salto grande (CatBoost, ΔAP {{d:test.cb_b.cb_a.ap}}; ΔROC-AUC {{d:test.cb_b.cb_a.roc_auc}}). Las variables de mayor importancia son la tasa histórica del curso en el programa, la tasa y el promedio acumulados del estudiante y el departamento (§12).
- **Prerrequisitos explícitos (b a c)**: ΔAP {{d:test.cb_c.cb_b.ap}} con CatBoost y {{d:test.lr_c.lr_b.ap}} con logística en test; {{d:valid.cb_c.cb_b.ap}} y {{d:valid.lr_c.lr_b.ap}} en valid; {{d:posterior.cb_c.cb_b.ap}} y {{d:posterior.lr_c.lr_b.ap}} en 2025. El efecto es del orden de 0,003 de AP o menor y de signo inconsistente entre particiones: **el grafo explícito no aporta señal utilizable** más allá de la estadística del curso y del desempeño del estudiante. Explicaciones posibles (hipótesis, no medidas): los prerrequisitos ya se reflejan en el promedio y las reprobaciones acumuladas del estudiante, y el 40 % de los intentos son de cursos sin prerrequisitos.
- **Docente (c a d)**: el escalón que más aporta después del curso (ΔAP {{d:test.cb_d.cb_c.ap}}; ΔRecall@1 {{d:test.cb_d.cb_c.recall_at_1}}). Es la asociación histórica de la sección o del docente con la aprobación (heterogeneidad entre secciones), no un juicio sobre personas; la llave del docente nunca se reporta ni se guarda en el snapshot. Solo existe oferta desde 2016; su cobertura en test es 83 %.

## 7. Grafo curricular: embeddings y red extremo a extremo

{{tabla:grafo.test}}

| Comparación (test) | Resultado |
|---|---|
| (d′) (c) + embeddings GraphSAGE frente a (c) | ΔAP {{d:test.cb_cemb.cb_c.ap}}; ΔROC-AUC {{d:test.cb_cemb.cb_c.roc_auc}} |
| (d′) frente a (c) + identidad del curso | ΔAP {{d:test.cb_cemb.cb_c_id.ap}} |
| (c) + identidad del curso frente a (c) | ΔAP {{d:test.cb_c_id.cb_c.ap}} |
| Red GraphSAGE (prerreq. + coinscripción) frente a la misma red sin aristas | ΔAP {{d:test.nn_gnn.nn_mlp.ap}} |
| Red GraphSAGE (prerreq. + coinscripción) frente a la red sin representación del curso | ΔAP {{d:test.nn_gnn.nn_ninguno.ap}} |
| Red GraphSAGE (prerreq. + coinscripción) frente a la de solo prerrequisitos | ΔAP {{d:test.nn_gnn.nn_gnn_prereq.ap}} |
| Red GraphSAGE frente a CatBoost (c) | ΔAP {{d:test.nn_gnn.cb_c.ap}} |
| Red GraphSAGE frente al mejor CatBoost de valid ((d), con docente) | ΔAP {{d:test.nn_gnn.cb_d.ap}} |

- **Autosupervisión.** Los embeddings se entrenan prediciendo las aristas de prerrequisito retenidas (10 %) contra pares al azar: AP 0,966-0,977 frente a 0,867-0,903 de una línea base por grado (producto de grados de entrada y salida con las aristas de entrenamiento). Mide que el codificador captura la estructura, pero los negativos al azar son fáciles; no demuestra utilidad para predecir reprobación.

{{tabla:enlaces}}

- **Embeddings en CatBoost (d′).** Cambian el AP en {{d:test.cb_cemb.cb_c.ap}} (valid {{d:valid.cb_cemb.cb_c.ap}}; 2025 {{d:posterior.cb_cemb.cb_c.ap}}): sin ganancia consistente. El control con la identidad del curso como categórica **empeora** a CatBoost ({{d:test.cb_c_id.cb_c.ap}}; sobreajuste a cursos con pocas filas); los embeddings son una forma de identidad del curso regularizada por la estructura (frente a la identidad: {{d:test.cb_cemb.cb_c_id.ap}}), pero esa ventaja sobre la identidad no se traduce en ventaja sobre el modelo que ya trae la estadística puntual del curso.
- **Red extremo a extremo.** El GraphSAGE entrenado con la reprobación no supera a la red con los mismos atributos de nodo sin aristas ni a la que no usa representación del curso. La coinscripción tampoco ayuda frente a usar solo prerrequisitos. La red queda ≈ 0,01 de AP por debajo de CatBoost (c) en test.
- **GAT.** No se implementó (opcional). Dado que ni el grafo explícito ni GraphSAGE aportan, no se espera que una variante con atención cambie la conclusión, pero no está probado.

## 8. Ranking de cursos por (estudiante, período)

Grupos elegibles: al menos 2 cursos y al menos 1 reprobación en el período (16.411 grupos en test). K = 1, 2; Recall@K = fracción de las reprobaciones del grupo que quedan entre los K cursos de mayor riesgo; Precision@K = fracción de esos K cursos que se reprobaron. Referencia: orden al azar (valor esperado exacto).

{{tabla:ranking.test}}

La tasa histórica del curso ya ordena mejor que el azar (Recall@1 {{v:test.baseline.recall_at_1}} frente a 0,188). Los modelos con estadística del curso la superan poco: CatBoost (c) {{d:test.cb_c.baseline.recall_at_1}} en Recall@1 y, con docente, {{d:test.cb_d.baseline.recall_at_1}}. Los modelos sin estadística del curso ((a)) ordenan los cursos de un mismo estudiante apenas mejor que el azar: aunque saben mucho del estudiante, ese conocimiento es idéntico para todos sus cursos del período.

## 9. Calibración (test)

{{tabla:calibracion}}

Los modelos de aprendizaje subestiman el riesgo de los deciles altos y en promedio (≈ 0,114 frente a 0,144 observado en CatBoost (c)); la línea base, que depende solo de la historia, queda mejor calibrada en nivel (ECE {{v:test.baseline.ece}}) pero discrimina menos. Causa probable (hipótesis): la parada temprana con valid, cuyo nivel (13,4 %) es menor que el de test; no se recalibró (no se ajustó nada con datos de test). Para usar probabilidades hay que recalibrar con un período reciente.

## 10. Subgrupos y equidad (test; descriptivo)

Modelos de las tablas: {{tabla:modelos_sub}}. «Riesgo / AP» = riesgo medio predicho y AP dentro del grupo; los grupos con menos de 500 (programa) o 100 intentos se omiten.

### 10.1 Por sexo (solo evaluación)

{{tabla:sub.sexo}}

Las mujeres reprueban menos y reciben menor riesgo; la brecha de calibración (riesgo medio menos observado) es negativa en ambos grupos (−0,02 a −0,05), algo mayor en hombres con la red; el AP es menor en mujeres con todos los modelos de aprendizaje. Es una descripción: no se aplicó ninguna corrección ni se evaluó causalidad.

### 10.2 Por oportunidad (primer intento frente a repetición)

{{tabla:sub.oportunidad}}

En repeticiones la reprobación es de 37-44 % y los modelos subestiman el nivel (riesgo medio 0,29-0,33).

### 10.3 Por semestre de la malla

{{tabla:sub.sem_malla}}

### 10.4 Curso dentro o fuera de la malla del estudiante

{{tabla:sub.en_malla}}

Los cursos fuera de la malla (1,4 %) tienen menos señal (AP 0,36 frente a 0,54 en CatBoost (c)) y no tienen variables de prerrequisitos (`info_prereq` es idéntico a «en la malla»).

### 10.5 Por programa (n ≥ 500 en test)

{{tabla:sub.programa}}

## 11. Estabilidad por período (test)

AP por período de test:

{{tabla:ap_periodo}}

Los modelos mantienen el orden en los cuatro períodos; el AP sube con la tasa base. Tasas por período: §2.

## 11b. Sensibilidad: qué ocurre si se incluyen 201920 y 202010

En la corrida inicial (no conservada; mismos modelos y misma definición, con esos dos períodos como unidades) el AP de test fue 0,39 para CatBoost (b) (0,385 la línea base), 0,50 para la logística (b) y 0,51 para la red GraphSAGE; el riesgo medio predicho fue de 0,04-0,09 frente a 0,159 observado y la parada temprana de CatBoost se producía en unas 30 iteraciones. Con ellos excluidos, CatBoost (b) alcanza {{v:test.cb_b.ap}}. La diferencia se debe a que en esos períodos los estudiantes que habrían reprobado figuran sin reprobación registrada, lo que enseña al modelo que ciertos semestres no tienen riesgo. Las cifras de esa corrida se citan solo como orden de magnitud: sus artefactos no se conservaron.


## 12. Importancia de variables, tiempo y memoria

Importancia (CatBoost (c), media de 3 semillas):

{{tabla:importancia}}

### Tiempo y memoria

{{tabla:tiempos}}

Pico de memoria RAM del proceso de entrenamiento y evaluación: {{meta:ram}} MB (conjunto completo en memoria, 16 GB disponibles). Tiempo total de la corrida: {{meta:segundos}} s. GPU: RTX 4060 de 8 GB; ninguna red superó el pico indicado en la tabla (memoria asignada por PyTorch).

## 12b. Banda de nota por intento (P84) y pronósticos agregados (P74)

**Escala institucional (P84).** Reprobado < 4,0; «Aprobado por Unanimidad» [4,0; 5,4); «Aprobado con Distinción» [5,4; 6,4); «Aprobado con Máxima Distinción» [6,4; 7,0]. La banda es una etiqueta (como `y`), nunca una variable. **La nota final de titulación** (70 % el promedio de cursos y 30 % el examen de titulación) **no se modela**: no hay en la base una fuente de la nota del examen (P89), y la banda de T2 es solo la nota del intento de un curso.

{{tabla:bandas.distribucion}}

**Modelo.** CatBoost multiclase con el mismo conjunto de variables que los binarios (se usó el conjunto elegido por el AP de valid de los modelos binarios, conjunto {{bx:conjunto}}), 3 semillas del conjunto de entrenamiento y parada temprana en valid, sin docente. Se evalúa con log-loss y AP por clase frente a la frecuencia de las bandas en train, con intervalos del bootstrap agrupado por persona y diferencias pareadas.

**Test (2023-2024):**

{{tabla:bandas.metricas.test}}

**Valid (2021-2022):**

{{tabla:bandas.metricas.valid}}

**2025 (control posterior):**

{{tabla:bandas.metricas.posterior}}

El modelo reduce el log-loss de test de {{b:test.frecuencias.logloss}} a {{b:test.cb_bandas.logloss}} y mejora el AP de cada banda con intervalos claramente sobre 0 (diferencias pareadas en la fila final).

### Pronósticos agregados por programa y facultad (P74)

**Solo agregados.** Ninguna fila de esta sección corresponde a una persona. Se aplican los umbrales de publicación (D70 y la respuesta de la DAI): un grupo con menos de 10 intentos no deja rastro; un grupo se lista con n ≥ 100 y una banda solo se evalúa con al menos 10 eventos en ella; los demás se cuentan y no se listan. Los porcentajes son del **modelo** (esperado) frente a lo **observado** en test, con intervalos del 95 %; la «brecha de la frecuencia global» es la referencia que el modelo debe superar.

{{tabla:bandas.resumen}}

**Lectura.** El modelo ordena bien los grupos (ρ de Spearman de 0,84 a 0,93 en test por programa y facultad) y su error absoluto medio en puntos porcentuales es menor que el de la frecuencia global en la banda de reprobados (3,8 frente a 5,1 por programa), en Unanimidad (3,9 frente a 8,0) y en Máxima Distinción (3,7 frente a 7,8), pero **peor en Distinción** (5,2 frente a 4,6 por programa; 5,0 frente a 3,6 por facultad): esa banda es la central y la frecuencia global ya la predice bien. El modelo **subestima la reprobación de los programas con más reprobación** (hasta 12 puntos en Ingeniería Civil en Energía y Electrónica): es la misma subestimación de nivel de §9, concentrada en los grupos de mayor riesgo.

**Programas reportables.** Con n ≥ 100 intentos en test se listan {{bx:grupos.test.programa.resumen.grupos_100_o_mas}} de {{bx:grupos.test.programa.resumen.grupos_total}} programas y {{bx:grupos.test.facultad.resumen.grupos_100_o_mas}} de {{bx:grupos.test.facultad.resumen.grupos_total}} facultades. Los programas, ordenados por el % observado de reprobados (observado / predicho y brecha en puntos porcentuales; los intervalos por programa están en `artefactos/resultados_t2.json`, ignorado por git):

{{tabla:bandas.programas}}

**Facultades, por banda** (nombre de la facultad; % observado, % esperado y brecha con intervalos):

{{tabla:bandas.facultad.reprobado}}

{{tabla:bandas.facultad.unanimidad}}

{{tabla:bandas.facultad.distincion}}

{{tabla:bandas.facultad.maxima_distincion}}

**Mayores y menores.** Posiciones por % observado de reprobados y por % esperado (programas y facultades):

{{tabla:bandas.ranking.programa}}

{{tabla:bandas.ranking.facultad}}

**Pronóstico agregado con eliminación y cambio de programa.** Para cada grupo, el % esperado por banda (entre paréntesis lo observado), el % que sería **eliminado** (T5, k = 2; con la etiqueta actual y la efectiva sin reintegro) y el % con **cambio de programa** (T4, k = 2), tomados de `11_benchmark_t4_t5.md` solo donde ese informe reporta el grupo (n ≥ 100 y ≥ 10 eventos); «—» es un grupo no reportable allí. **Advertencia sobre T4:** el modelo conservado de T4 con `k` = 2 (logística) sobreestima la tasa de transición en unos siete puntos (11_benchmark_t4_t5.md §5), de modo que el % esperado de cambio de programa **no es utilizable** como pronóstico (compárese el valor esperado con el observado entre paréntesis).

Por programa:

{{tabla:pronostico.programa}}

Por facultad:

{{tabla:pronostico.facultad}}

## 12c. Ablación de estadística reciente (P55)

La tasa de aprobación de los cursos no es estacionaria (§2, D80). Se comparan tres formas de calcular las siete estadísticas del curso del conjunto (c), siempre con períodos estrictamente anteriores al de la fila y con el mismo modelo, semillas y particiones: (1) la **historia expansiva** (defecto actual), (2) **decaimiento exponencial** con vida media de 2 años y (3) una **ventana** de los últimos 3 años. Las estadísticas se recalculan desde los agregados por (curso, programa, período) y la prueba de que no usan el futuro compara contra un cálculo directo.

{{tabla:deriva}}

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

- Hash del snapshot (`snapshot_t2_resumen.hash_datos`): `{{meta:snapshot_hash}}`. Versión del código (sha256 de `models/`, `evaluation/` y las reglas/variables del snapshot): `{{meta:version_codigo}}`.
- Comandos y entorno: `README.md` («Snapshots y benchmark T2»). MLflow: experimento `t2_aprobacion_por_intento` en `mlruns/` (ignorado por git), un run por modelo con parámetros, métricas con IC, hash de los datos y versión del código.
- Las predicciones individuales solo existen en `artefactos/preds/t2_*.npz` (ignorado por git); no hay API ni pantalla para ellas.
