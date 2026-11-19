# DAI Neural — Benchmark T4 y T5: transición real de programa y eliminación

**Versión:** 0.5 · 18-11-2026 (§13.6: calibración de los candidatos de T5 sobre validación; empeora la calibración en prueba y se conservan las GRU, D120) · 0.4 · 18-11-2026 (§13: variables nuevas del estudio de viabilidad, regla D114; el desempate deja candidatos clásicos en T5 y no adopta T4) · 0.3 · 16-11-2026 (D114: el modelo conservado de T5 se elige con el IC pareado de validación y pasa a ser la GRU en `k` = 2 y 4) · 0.2 · 13-11-2026 (reconstrucción consolidada, etapa B: variables de admisión `mm_*` + prueba, momento del traslado P71, reintegro P88, T5 con tres evaluaciones) · 0.1 · 13-11-2026 · Fase 4, benchmark T4 y T5. Base: `PROMPT_MAESTRO.md` (secciones «Predicción experimental», «Evaluación» y «Fase 4»), `00_plan.md` (D23–D63 y D81–D88), `10_benchmark_t3.md` (población y atributos) y el mart de traslados (D48–D51). Versión del código: `4518dbc652eb4003d8a1a75888a68da0f38444daedcddac8d2ef2da4d0ef8d18`; huella de los datos del snapshot: `beea8a43a033d62b83e9cff75d6a79eaa30acb5b669606e144f9221f82310a4d`.
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, RUT ni predicción por persona figura en este documento ni en el repositorio; las predicciones viven en `artefactos/preds/` (ignorado por git). Los pronósticos por programa y facultad de §8 son **agregados** (tasa esperada de un grupo), no individuales, y se publican solo con n ≥ 100 y al menos 10 eventos.

## 1. Definición de las tareas

**T4, «transición real de programa».** Dada una trayectoria de pregrado que sigue matriculada al cierre del `k`-ésimo semestre regular, ¿pasa a otro programa de pregrado (cambio de carrera, traslado de sede u otro traslado) dentro de los dos semestres regulares siguientes? **T5, «eliminación».** ¿Recibe en esos dos semestres un estado de eliminación académica? Son dos objetivos binarios distintos, evaluados por separado, sobre **un mismo resultado mutuamente excluyente** en el horizonte (§3), de modo que los resultados competidores (egreso, otra salida, el otro evento) son explícitos y no se confunden con «continúa».

| Elemento | Definición |
|---|---|
| Unidad | Una **trayectoria de pregrado** de T3 (`id_nivel` 1; sin admisiones `IN`, `PE`, `IE`; cohortes 2015 o posteriores; sin los programas de Intercambio; Ingeniería Civil Plan Común unido a su especialidad: D47, `10_benchmark_t3.md` §2). Una persona puede tener más de una trayectoria; el bootstrap remuestrea personas. |
| Corte `k` | Fin del `k`-ésimo semestre regular desde el de admisión, `k` ∈ {2, 4}. Elegible: con estado de matrícula (matrícula, reingreso o cambio de ciclo) en el período del corte, sin estado de salida en ese período (D24, P52), sin egreso o titulación hasta el corte y con seguimiento posterior (las reglas de T3), y **sin una transición ya iniciada en el corte** (D53). |
| Horizonte | Los **dos semestres regulares siguientes** (slots `k + 1` y `k + 2`). Una fila solo se etiqueta si el período del slot `k + 2` está **cerrado** (`202610` es el último cerrado; el siguiente está en curso); si no, es `censurado` y queda fuera de los modelos. |
| Evento T4 | Un **traslado no ambiguo** de tipo *cambio de carrera*, *traslado de sede* u *otro traslado* (`neural_mart.programa_traslados`, D48–D50) cuyo **primer período del destino** cae en el horizonte. El origen puede ser la trayectoria o la especialidad ya unida a ella. **No son eventos:** la *elección de especialidad* desde el Plan Común (progresión esperada), el *cambio de ciclo* y la *continuación de estudios* tras el egreso. |
| Evento T5 | Un estado **`E` (Eliminado)** de la trayectoria dentro del horizonte. Los demás estados de salida (renuncias `B` y `F`, no continuidad `O`, retracto `R`, `3`, `9` y las sanciones disciplinarias `X`, `6`, `H`) no se consideran eliminación académica y quedan en «otra salida» (D57, P70). |
| Particiones | **Por cohorte de admisión:** train 2015–2019, valid 2020–2021 (docencia remota), test 2022–2023 y 2024 en adelante como control posterior (con `k` = 4 ninguna fila de 2024 tiene el horizonte cerrado). Son los límites de T1: con un horizonte de un año el seguimiento los permite (T3 usó cortes más tempranos por su horizonte de hasta 14 semestres). |
| Atributos | Los de T3, sin cambios (`10_benchmark_t3.md` §1): perfil de ingreso, programa vigente al corte, duración nominal, y agregados académicos robustos a P58 (créditos aprobados, tasas y promedios sobre los semestres con fallos registrados, avance de malla, semestres matriculados…); la GRU recibe además la secuencia de los semestres `1..k`. `sexo` solo se usa en la evaluación de equidad (`sexo_equidad`, M1); el año de admisión (`cohorte_anio`) **no** es variable de los modelos. |

### Decisiones conservadoras de la definición

1. **El primer evento gana (D54).** Si dentro del horizonte ocurren dos eventos, el resultado es el más temprano; en un empate rige el orden egreso, eliminación, transición, ambigua. Una persona con `E` y un traslado en el horizonte cuenta como eliminación o como transición según cuál ocurra primero; las banderas `hubo_transicion_en_horizonte` y `hubo_eliminacion_en_horizonte` conservan ambos hechos (§2).
2. **«Continúa» es matrícula en cualquier programa (D31, D54).** Quien no tiene evento y está matriculado en el período del horizonte en algún programa de la UCN continúa; así, un traslado que el mart no clasifica no se convierte en «otra salida».
3. **La elección de especialidad no es transición (D56).** La trayectoria del Plan Común sigue como «continúa» al pasar a su especialidad; lo que cuenta como T4 es el traslado de la especialidad ya unida, o el de un Plan Común sin continuación en Ingeniería Civil.
4. **Una transición ya iniciada al corte no es objetivo de predicción (D53).** Se conoce al corte, como una salida en el período del corte (D24).
5. **Momento del traslado (P71, aplicado en la etapa B).** El evento se fecha en la **salida del programa de origen**, es decir, en el último período del origen (`ultimo_periodo_origen`), y ya no en el primer período del destino. Un traslado cuyo origen termina en el período del corte no es evento de esa fila (se cuenta en la bandera `traslado_fechado_en_el_corte`); la exclusión de la «transición ya iniciada» sigue usando el inicio del destino (D53). Un traslado sin período de origen conocido se fecha en el destino. Los recuentos antes y después están en «Cambios de la reconstrucción consolidada».
6. **Transición ambigua y censura fuera de los modelos.** Una transición con más de un destino posible (D50) y una fila con el horizonte sin cerrar se conservan en el snapshot con su resultado, pero ningún modelo las usa.
7. **Períodos 201920 y 202010 (P58).** Heredado de T3: sus intentos cuentan para créditos, no para tasas; los modelos usan solo los agregados que P58 no altera.
8. **No hay recalibración.** Los modelos se ajustan con train y se evalúan con la deriva a la vista; se informan calibración y brecha del riesgo medio.

## Resumen de resultados

1. **Hay señal, y viene de los agregados académicos, no del perfil de ingreso.** Con el perfil de ingreso solo, ningún modelo supera de forma clara a la tasa histórica por programa en T4 (con `k` = 2, ΔAP de la logística frente a la tasa histórica: -0,004 [-0,012; 0,004]) y en T5 la mejora es modesta (AP 0,196 [0,170; 0,229] frente a 0,118 [0,106; 0,134]). Al sumar los agregados del rendimiento hasta el corte, el AP sube en T4 de 0,046 a 0,098 y en T5 de 0,178 a 0,554 (CatBoost, `k` = 2); las diferencias pareadas tienen el intervalo sobre 0 (§5–§6).
2. **T5 (eliminación) es predecible; T4 (transición real) lo es poco.** Con `k` = 2, T5 alcanza AP 0,554 [0,507; 0,602] y ROC-AUC 0,908 (tasa de base en test: 9,7 %); T4 llega a AP 0,094 [0,069; 0,139] con una tasa de base de 3,0 %: ordena razonablemente (ROC-AUC 0,732), pero acierta pocos casos en el extremo alto del riesgo. Con `k` = 4 las dos son más difíciles (T4: AP 0,059; T5: AP 0,309).
3. **Las redes no superan a los clásicos en ninguna tarea ni corte.** Con las variables de admisión corregidas, la GRU solo con la secuencia deja de superar a CatBoost en T5 con `k` = 2 (ΔAP 0,012 [-0,012; 0,037]: el intervalo incluye 0), de modo que la conclusión anterior (una red conservada por un margen estrecho) **cambia** y se conserva el clásico en las seis combinaciones de tarea y corte (§4). La logística entrena en un par de segundos y CatBoost en decenas; la GRU tarda de 3 a 6 segundos por tarea con tres semillas en GPU.
4. **Calibración y deriva.** En T5 con `k` = 2 el modelo conservado queda bien calibrado (ECE 0,0153). Con `k` = 4 el riesgo medio predicho supera a la tasa observada del test, porque la tasa de eliminación de las cohortes 2022–2023 cae respecto de la de entrenamiento. Parte de esa caída es un **subregistro del estado `E` desde 202420** (P75, §3): el número de estados `E` baja a una cuarta parte o menos de lo habitual mientras los traslados se mantienen. Con los períodos de registro completo (evaluación (c) de «Cambios de la reconstrucción consolidada»), T5 con `k` = 2 sube a AP 0,646 [0,586; 0,699] (§3); la eliminación efectiva (sin reintegro) tiene una tasa menor y un AP menor, y las conclusiones sobre qué modelo se conserva no cambian.
5. **Programas y facultades.** Solo una minoría de los grupos es reportable (n ≥ 100 y ≥ 10 eventos): con `k` = 2, 3 de 46 programas en T4 y 15 de 46 en T5. En T5 el modelo ordena los grupos (ρ de Spearman entre 0,7 y 0,8) y se equivoca menos que la tasa histórica; **en T4 el pronóstico agregado no mejora la tasa histórica y, con `k` = 2, está mal calibrado**: el modelo conservado (logística) sobreestima la tasa de transición en unos siete puntos (riesgo medio de 0,10 frente a una tasa observada de 0,03), de modo que su error agregado por programa y facultad es mucho mayor que el de la tasa histórica (§8). El conservado de T4 con `k` = 2 cambió de CatBoost a la logística por una diferencia de AP de 0,001 en valid entre dos clásicos que no se distinguen; la regla del benchmark es mecánica y se informa tal cual.
6. **Equidad.** La diferencia entre mujeres y hombres en la brecha de calibración es de a lo más 0,01 en las cuatro combinaciones de tarea y corte (descriptivo); el nivel absoluto de la brecha de T5 con `k` = 4 se debe a la deriva, no al sexo. Las diferencias de AP y de Recall@10 % descansan en pocos eventos y no son concluyentes (§9).
7. **Modelos conservados.** T4: logística con ingreso + agregados en `k` = 2 (antes CatBoost) y CatBoost con ingreso + agregados en `k` = 4. T5 (D114, 16-11-2026): **GRU** con ingreso + secuencia en `k` = 2 y **GRU** con agregados en `k` = 4, elegidas en validación con IC pareado sobre cero frente al mejor clásico (+0,038 y +0,031 de AP). En prueba, `k` = 2: AP 0,566 frente a 0,554 de CatBoost, con la misma discriminación y calibración; `k` = 4: AP 0,312 frente a 0,309, pero peor calibrada (Brier 0,058 frente a 0,049). Hasta el 16-11-2026 se conservaban CatBoost y la logística porque la regla exigía el IC sobre cero en prueba. **Ningún modelo está aprobado para uso individual** (Gate 4, §11).

## Cambios de la reconstrucción consolidada (13-11-2026)

Esta versión repite el benchmark con los datos corregidos de la etapa A y con cuatro cambios del lado del modelo.

1. **Variables de admisión (`mm_*` + prueba).** Los percentiles `pct_*` (rangos sobre valores en escalas mezcladas) se reemplazan por los puntajes normalizados `mm_*` (mínimo–máximo por prueba, año y campo) más la variable categórica `prueba_admision` (PSU hasta 2020, PDT 2021–2022, PAES desde 2023: P87). Vale para todas las tareas y los tres modelos.
2. **Momento del traslado (P71).** T4 fecha el evento en la salida del origen (último período del origen). Recuentos de eventos y de resultados por partición, antes y después:

| k | Partición | Transiciones (T4) antes | Transiciones (T4) después | Otra salida antes | Otra salida después | Continúa antes | Continúa después |
|---|---|---|---|---|---|---|---|
| 2 | train | 343 | 356 | 373 | 360 | 8.851 | 8.851 |
| 2 | valid | 128 | 134 | 152 | 148 | 3.359 | 3.357 |
| 2 | test | 137 | 141 | 194 | 190 | 3.895 | 3.895 |
| 4 | train | 153 | 159 | 195 | 189 | 7.188 | 7.188 |
| 4 | valid | 79 | 80 | 67 | 66 | 2.540 | 2.540 |
| 4 | test | 65 | 66 | 127 | 127 | 3.449 | 3.448 |

3. **Reintegro (P88).** El reintegro es solo el estado `I` (`Y` es una rectificación, no un reintegro). La eliminación con reintegro y la eliminación efectiva se recalcularon con esa regla y el snapshot se reconstruyó.
4. **T5 en tres evaluaciones.** Se mantiene la regla de selección (mejor clásico en valid; una red solo si gana en valid y el ΔAP pareado queda sobre 0): el modelo conservado es el de la etiqueta actual y las tres evaluaciones lo miden con (a) la etiqueta actual, (b) la eliminación efectiva (sin reintegro) y (c) la etiqueta actual sin las filas de horizonte dudoso (`horizonte_e_dudoso`, horizonte desde 202420: P75). Con `k` = 4 todas las filas de test tienen horizonte dudoso y (c) no es evaluable. En `k` = 4 el ΔAP pareado frente a la tasa histórica del modelo conservado (logística) no se guardó en el bootstrap y se muestra solo el punto; el AP del modelo y el de la tasa histórica llevan su intervalo.

| k | Evaluación | Modelo conservado | Filas | Eventos | Tasa observada | AP | ROC-AUC | Brier | ECE | AP tasa histórica | ΔAP pareado vs tasa histórica |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | (a) etiqueta actual: eliminación | CatBoost (ingreso + agregados) | 4.688 | 456 | 0,097 | 0,554 [0,507; 0,602] | 0,908 [0,895; 0,921] | 0,0602 [0,0553; 0,0653] | 0,0153 [0,0098; 0,0229] | 0,118 [0,106; 0,134] | 0,435 [0,391; 0,480] |
| 2 | (b) eliminación efectiva (sin reintegro) | CatBoost (ingreso + agregados) | 4.688 | 316 | 0,067 | 0,481 [0,423; 0,542] | 0,913 [0,897; 0,928] | 0,0457 [0,0417; 0,0500] | 0,0115 [0,0080; 0,0190] | 0,081 [0,071; 0,095] | 0,400 [0,341; 0,458] |
| 2 | (c) etiqueta actual sin horizontes dudosos | CatBoost (ingreso + agregados) | 2.123 | 278 | 0,131 | 0,646 [0,586; 0,699] | 0,919 [0,903; 0,934] | 0,0738 [0,0664; 0,0820] | 0,0402 [0,0296; 0,0525] | 0,169 [0,147; 0,197] | 0,477 [0,420; 0,528] |
| 4 | (a) etiqueta actual: eliminación | Logística (ingreso + agregados) | 3.885 | 201 | 0,052 | 0,309 [0,253; 0,379] | 0,879 [0,856; 0,900] | 0,0486 [0,0445; 0,0525] | 0,0782 [0,0714; 0,0851] | 0,072 [0,058; 0,090] | 0,237 |
| 4 | (b) eliminación efectiva (sin reintegro) | Logística (ingreso + agregados) | 3.885 | 130 | 0,033 | 0,280 [0,216; 0,364] | 0,898 [0,868; 0,922] | 0,0284 [0,0245; 0,0322] | 0,0282 [0,0227; 0,0333] | 0,042 [0,033; 0,059] | 0,238 |
| 4 | (c) etiqueta actual sin horizontes dudosos | — | 0 | 0 | no evaluable (menos de 100 filas o 10 eventos) | | | | | | |

   Lectura: la eliminación efectiva es menos frecuente y su AP absoluto es menor, pero el modelo mantiene una ventaja clara sobre la tasa histórica y el mismo modelo conservado; sin los horizontes dudosos (solo `k` = 2) el AP sube y la tasa observada también (el subregistro de `E` baja la tasa de las filas dudosas). **Las conclusiones de selección no cambian entre las tres evaluaciones.**

**Antes y después (modelo conservado, test).** Las diferencias de AP entre la versión anterior y esta están dentro de los intervalos; lo que sí cambia es el modelo conservado en T4 con `k` = 2 y en T5 con `k` = 2:

| Tarea y corte | Modelo conservado (antes → después) | AP de test antes | AP de test después | ROC-AUC antes | ROC-AUC después | Cambio de AP |
|---|---|---|---|---|---|---|
| T4 k = 2 | CatBoost (ingreso + agregados) → Logística (ingreso + agregados) | 0,100 [0,074; 0,142] | 0,094 [0,069; 0,139] | 0,766 [0,726; 0,803] | 0,732 [0,691; 0,773] | -0,005 |
| T4 k = 4 | CatBoost (ingreso + agregados) → CatBoost (ingreso + agregados) | 0,058 [0,040; 0,091] | 0,059 [0,041; 0,091] | 0,807 [0,759; 0,850] | 0,803 [0,753; 0,849] | +0,001 |
| T5 k = 2 | GRU (ingreso + secuencia) → CatBoost (ingreso + agregados) | 0,575 [0,530; 0,624] | 0,554 [0,507; 0,602] | 0,907 [0,893; 0,921] | 0,908 [0,895; 0,921] | -0,021 |
| T5 k = 4 | Logística (ingreso + agregados) → Logística (ingreso + agregados) | 0,319 [0,261; 0,389] | 0,309 [0,253; 0,379] | 0,886 [0,864; 0,907] | 0,879 [0,856; 0,900] | -0,010 |

## 2. Población y embudo

Un mismo snapshot (`neural_mart.snapshot_t45`, una fila por trayectoria y corte) sirve a las dos tareas. El embudo parte de la población de T3 y agrega un único filtro propio, la transición ya iniciada al corte (D53). Las cifras son recuentos de trayectorias (no de personas).

| Paso | k = 2 | k = 4 |
|---|---|---|
| Unidades de pregrado de las cohortes 2015 o posteriores (población T3: sin IN/PE/IE, sin Intercambio, Plan Común unido a su especialidad) | 30.967 | 30.967 |
| − sin estado de matrícula en el período del corte | 2.086 | 9.638 |
| − con estado de salida en el período del corte (D24, P52) | 970 | 811 |
| − egresado o titulado hasta el corte | 4 | 16 |
| − sin seguimiento después del corte (corte en el último período cerrado) | 2.701 | 2.180 |
| = Elegibles en T3 | 25.206 | 18.322 |
| − con una transición ya iniciada en el período del corte (se conoce al corte) | 214 | 170 |
| = **Filas de T4/T5** (una por trayectoria y corte) | 24.992 | 18.152 |
| … de ellas, con horizonte no cerrado (censuradas, fuera de los modelos) | 2.608 | 2.108 |
| … de ellas, transición ambigua (fuera de los modelos) | 17 | 3 |
| Memo: trayectorias de Plan Común elegibles en este corte | 521 | 294 |
| Memo: … de ellas, unidas a una especialidad (su elección no es una transición) | 352 | 273 |
| Memo: filas con eliminación y transición dentro del horizonte (solo se cuenta la primera, §3) | 119 | 124 |
| Memo: filas con eliminación y matriculadas en el período del horizonte (en cualquier programa) | 670 | 1.089 |
| Memo: filas observadas sin transición en el horizonte pero con una en los dos semestres siguientes | 554 | 280 |
| Memo: … de ellas, clasificadas «otra salida» (el destino empieza después del horizonte) | 26 | 6 |

Las filas con eliminación y transición en el horizonte son pocas: el resultado único evita contarlas dos veces y las banderas del snapshot conservan ambos hechos. Los traslados cuyo destino empieza después del horizonte (P71) no son eventos de esa fila; una parte mínima de ellos queda como «otra salida» y se informa en la última línea del embudo.

## 3. Resultados mutuamente excluyentes

| k | Partición | Filas | Continúa | Egreso | Transición (T4) | Eliminación (T5) | Otra salida | Transición ambigua (excluida) | Censurado (excluido) |
|---|---|---|---|---|---|---|---|---|---|
| 2 | train (2015–2019) | 11.094 | 8.851 (79,8 %) | < 10 | 356 (3,2 %) | 1.509 (13,6 %) | 360 (3,2 %) | 10 (0,1 %) | — |
| 2 | valid (2020–2021) | 4.043 | 3.357 (83,0 %) | < 10 | 134 (3,3 %) | 399 (9,9 %) | 148 (3,7 %) | < 10 | — |
| 2 | test (2022–2023) | 4.691 | 3.895 (83,0 %) | < 10 | 141 (3,0 %) | 456 (9,7 %) | 190 (4,1 %) | < 10 | — |
| 2 | control posterior (2024 en adelante) | 5.164 | 2.178 (42,2 %) | < 10 | 100 (1,9 %) | 135 (2,6 %) | 140 (2,7 %) | < 10 | 2.608 (50,5 %) |
| 4 | train (2015–2019) | 8.834 | 7.188 (81,4 %) | 70 (0,8 %) | 159 (1,8 %) | 1.226 (13,9 %) | 189 (2,1 %) | < 10 | — |
| 4 | valid (2020–2021) | 3.325 | 2.540 (76,4 %) | 50 (1,5 %) | 80 (2,4 %) | 588 (17,7 %) | 66 (2,0 %) | < 10 | — |
| 4 | test (2022–2023) | 3.885 | 3.448 (88,8 %) | 43 (1,1 %) | 66 (1,7 %) | 201 (5,2 %) | 127 (3,3 %) | — | — |
| 4 | control posterior (2024 en adelante) | 2.108 | — | — | — | — | — | — | 2.108 (100,0 %) |

Con `k` = 2 la tasa de eliminación en test es 9,7 % y la de transición 3,0 %. Los egresos dentro del horizonte son excepcionales con `k` = 2 y poco frecuentes con `k` = 4; no tienen un modelo propio y solo aparecen como clase en la vista multiclase (§7). Con `k` = 4 el control posterior (2024 en adelante) no tiene ninguna fila con el horizonte cerrado.

### Otra salida

«Otra salida» agrupa a quien no tiene un evento de T4 ni T5 y no está matriculado en el período del horizonte: un estado de salida distinto de `E` (renuncias, no continuidad, sanciones), una interrupción o una ausencia sin estado.

| k | Partición | estado de salida distinto de E | interrupción (sin matrícula en el horizonte) | ausencia sin estado |
|---|---|---|---|---|
| 2 | train | 268 | 79 | 13 |
| 2 | valid | 108 | 39 | < 10 |
| 2 | test | 153 | 37 | 0 |
| 4 | train | 124 | 55 | 10 |
| 4 | valid | 44 | 19 | < 10 |
| 4 | test | 103 | 22 | < 10 |

### Qué contiene el estado `E` (P70)

El diccionario no documenta los códigos de causal. La distribución del código en las filas de eliminación es muy concentrada, y los dos primeros códigos reúnen más del 80 %:

| Código de causal del estado E | Filas de eliminación (T5, train + valid + test) | Proporción |
|---|---|---|
| 0B | 1.880 | 42,9 % |
| 0D | 1.825 | 41,7 % |
| 0A | 278 | 6,3 % |
| 0C | 132 | 3,0 % |
| 0H | 116 | 2,6 % |
| 5I | 54 | 1,2 % |
| 2D | 26 | 0,6 % |
| 5B | 16 | 0,4 % |
| 2B | 16 | 0,4 % |
| 2C | 12 | 0,3 % |
| otros | 24 | 0,5 % |

Que `E` sea una eliminación académica se apoya en el comportamiento de los datos (los eliminados aprueban una fracción mucho menor de sus asignaturas que quienes continúan), no en una definición oficial. Hasta que se confirme, T5 se lee como «estado E registrado» (§11).

### Subregistro del estado `E` desde 202420 (P75)

Los estados `E` por período muestran una caída marcada desde 202420, mientras las matrículas y los traslados siguen su nivel. Los períodos 202010 y 202020 también son bajos (docencia remota); los de 202420 en adelante no tienen una explicación conocida.

| Período | Estados E | Estados de matrícula (M, N, J) | E por cada 1.000 matrículas |
|---|---|---|---|
| 201810 | 1.730 | 26.047 | 66,4 |
| 201820 | 1.426 | 11.661 | 122,3 |
| 201910 | 1.351 | 25.329 | 53,3 |
| 201920 | 1.536 | 12.139 | 126,5 |
| 202010 | 459 | 26.414 | 17,4 |
| 202020 | 541 | 12.232 | 44,2 |
| 202110 | 900 | 25.620 | 35,1 |
| 202120 | 1.113 | 12.214 | 91,1 |
| 202210 | 1.121 | 26.268 | 42,7 |
| 202220 | 1.187 | 11.978 | 99,1 |
| 202310 | 1.067 | 33.370 | 32,0 |
| 202320 | 1.304 | 12.681 | 102,8 |
| 202410 | 1.149 | 29.202 | 39,3 |
| 202420 | 290 | 12.264 | 23,6 |
| 202510 | 128 | 30.414 | 4,2 |
| 202520 | 532 | 12.414 | 42,9 |
| 202610 | 336 | 29.652 | 11,3 |

Consecuencia para el benchmark: la tasa de eliminación del test (cohortes 2022–2023) mezcla períodos de registro completo con períodos de subregistro. Con `k` = 4 el horizonte de todas las filas de test termina en 202420 o después. Como análisis de sensibilidad, se evalúa T5 en las filas de test cuyo horizonte termina en 202410 o antes (solo cohorte 2022 con `k` = 2; con `k` = 4 no queda ninguna fila). Las etiquetas no se modifican.

| k | Modelo conservado | Filas de test sin horizonte dudoso | Filas excluidas | Eventos | Tasa observada | Riesgo medio | AP (conservado) | AP (tasa histórica) | ΔAP pareado | ECE (conservado) |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | CatBoost (ingreso + agregados) | 2.123 de 4.688 | 2.565 | 278 | 0,131 | 0,098 | 0,646 [0,586; 0,699] | 0,169 [0,147; 0,197] | 0,477 [0,420; 0,528] | 0,0402 [0,0296; 0,0525] |
| 4 | — | 0 de 3.885 | 3.885 | 0 | no evaluable (menos de 100 filas o 10 eventos) | | | | | |

## 4. Modelos y protocolo

**Misma población, mismas particiones, mismos atributos.** Todas las comparaciones usan las mismas filas. La escalera de ablación es la de T3:

| Paso | Modelo | Entrada |
|---|---|---|
| 0 | Tasa histórica por programa | solo el programa vigente al corte (calculada en train) |
| 1 | Logística y CatBoost | perfil de ingreso (`adm`) |
| 2 | Logística y CatBoost | perfil + agregados académicos robustos a P58 (`adm+agg`) |
| 3 | GRU (3 semillas, GPU) | perfil + secuencia de los semestres `1..k` (`adm`), y con agregados (`adm+agg`) |

Los hiperparámetros se eligen con valid (regularización de la logística, iteraciones de CatBoost con parada temprana, época de la GRU); las semillas de la GRU se promedian. **Regla de conservación:** se conserva el mejor clásico por AP en valid; una red lo reemplaza solo si su AP en valid es mayor **y** el intervalo pareado de ΔAP en test queda sobre 0. Si las redes no ganan, se conserva el modelo clásico y se dice (§5–§6). La métrica principal es el AP (los eventos son raros); se informan además ROC-AUC, Brier y ECE, cada una con intervalo de confianza del 95 % por bootstrap agrupado por persona (`1000` remuestreos, los mismos para todos los modelos), y las diferencias entre pasos son **pareadas** sobre los mismos remuestreos.

**Selección de modelos (valid):**

| Tarea | k | Mejor clásico (valid) | Mejor red (valid) | Modelo conservado | AP valid del conservado |
|---|---|---|---|---|---|
| T4 | 2 | Logística (ingreso + agregados) | GRU (ingreso + agregados + secuencia) | **Logística (ingreso + agregados)** | 0,113 |
| T4 | 4 | CatBoost (ingreso + agregados) | GRU (ingreso + agregados + secuencia) | **CatBoost (ingreso + agregados)** | 0,134 |
| T5 | 2 | CatBoost (ingreso + agregados) | GRU (ingreso + secuencia) | **CatBoost (ingreso + agregados)** | 0,518 |
| T5 | 4 | Logística (ingreso + agregados) | GRU (ingreso + agregados + secuencia) | **Logística (ingreso + agregados)** | 0,631 |

**Sin fuga.** Los atributos usan solo información disponible al corte. Las pruebas de perturbación del repositorio alteran los datos posteriores al corte y verifican que ningún atributo cambia; la vinculación del Plan Común con su especialidad (D47) es propiedad de la unidad, no del atributo (§11).

## 5. T4: transición real de programa

### Corte `k` = 2

**Test (cohortes 2022–2023, intervalos al 95 %):**

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica por programa | 0,050 [0,039; 0,065] | 0,645 [0,600; 0,690] | 0,0290 [0,0245; 0,0334] | 0,0076 [0,0065; 0,0139] |
| Logística (perfil de ingreso) | 0,046 [0,037; 0,058] | 0,634 [0,589; 0,678] | 0,0392 [0,0353; 0,0432] | 0,0627 [0,0586; 0,0686] |
| Logística (ingreso + agregados) | 0,094 [0,069; 0,139] | 0,732 [0,691; 0,773] | 0,0430 [0,0392; 0,0467] | 0,0743 [0,0692; 0,0799] |
| CatBoost (perfil de ingreso) | 0,046 [0,035; 0,062] | 0,607 [0,558; 0,653] | 0,0291 [0,0245; 0,0336] | 0,0082 [0,0063; 0,0141] |
| CatBoost (ingreso + agregados) | 0,098 [0,073; 0,138] | 0,772 [0,733; 0,809] | 0,0283 [0,0239; 0,0327] | 0,0075 [0,0050; 0,0130] |
| GRU (ingreso + secuencia) | 0,113 [0,084; 0,161] | 0,760 [0,719; 0,802] | 0,0280 [0,0238; 0,0321] | 0,0060 [0,0045; 0,0122] |
| GRU (ingreso + agregados + secuencia) | 0,103 [0,079; 0,140] | 0,763 [0,723; 0,804] | 0,0283 [0,0239; 0,0325] | 0,0084 [0,0058; 0,0135] |

**Valid (sin intervalos):**

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica por programa | 0,056 | 0,657 | 0,0318 | 0,0096 |
| Logística (perfil de ingreso) | 0,066 | 0,673 | 0,0331 | 0,0231 |
| Logística (ingreso + agregados) | 0,113 | 0,714 | 0,0323 | 0,0210 |
| CatBoost (perfil de ingreso) | 0,060 | 0,649 | 0,0318 | 0,0058 |
| CatBoost (ingreso + agregados) | 0,112 | 0,758 | 0,0313 | 0,0148 |
| GRU (ingreso + secuencia) | 0,105 | 0,748 | 0,0311 | 0,0111 |
| GRU (ingreso + agregados + secuencia) | 0,126 | 0,751 | 0,0313 | 0,0158 |

**Diferencias pareadas en test:**

| Diferencia pareada (test) | ΔAP | ΔROC-AUC | ΔBrier | Lectura (ΔAP) |
|---|---|---|---|---|
| Logística (perfil de ingreso) − Tasa histórica por programa | -0,004 [-0,012; 0,004] | -0,011 [-0,039; 0,015] | 0,0102 [0,0089; 0,0116] | sin diferencia (el intervalo incluye 0) |
| CatBoost (perfil de ingreso) − Tasa histórica por programa | -0,004 [-0,012; 0,006] | -0,039 [-0,081; -0,001] | 0,0001 [-0,0001; 0,0003] | sin diferencia (el intervalo incluye 0) |
| Logística (ingreso + agregados) − Logística (perfil de ingreso) | 0,049 [0,028; 0,087] | 0,098 [0,068; 0,131] | 0,0039 [0,0019; 0,0057] | mejora |
| CatBoost (ingreso + agregados) − CatBoost (perfil de ingreso) | 0,052 [0,029; 0,089] | 0,165 [0,122; 0,214] | -0,0008 [-0,0013; -0,0003] | mejora |
| CatBoost (perfil de ingreso) − Logística (perfil de ingreso) | -0,000 [-0,008; 0,010] | -0,028 [-0,065; 0,006] | -0,0101 [-0,0115; -0,0087] | sin diferencia (el intervalo incluye 0) |
| CatBoost (ingreso + agregados) − Logística (ingreso + agregados) | 0,004 [-0,034; 0,035] | 0,039 [0,011; 0,070] | -0,0147 [-0,0171; -0,0123] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + secuencia) − CatBoost (perfil de ingreso) | 0,067 [0,041; 0,108] | 0,154 [0,114; 0,200] | -0,0011 [-0,0018; -0,0004] | mejora |
| GRU (ingreso + agregados + secuencia) − CatBoost (ingreso + agregados) | 0,005 [-0,019; 0,024] | -0,009 [-0,033; 0,015] | -0,0000 [-0,0005; 0,0004] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + agregados + secuencia) − Logística (ingreso + agregados) | 0,009 [-0,032; 0,037] | 0,030 [0,002; 0,059] | -0,0148 [-0,0171; -0,0123] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + secuencia) − Logística (perfil de ingreso) | 0,067 [0,042; 0,109] | 0,126 [0,084; 0,168] | -0,0112 [-0,0125; -0,0099] | mejora |
| GRU (ingreso + agregados + secuencia) − GRU (ingreso + secuencia) | -0,010 [-0,046; 0,015] | 0,002 [-0,016; 0,022] | 0,0003 [-0,0002; 0,0008] | sin diferencia (el intervalo incluye 0) |
| CatBoost (ingreso + agregados) − Tasa histórica por programa | 0,048 [0,025; 0,086] | 0,126 [0,074; 0,179] | -0,0007 [-0,0012; -0,0001] | mejora |

Lectura. El perfil de ingreso solo no supera a la tasa histórica por programa; los agregados académicos suben el AP de 0,046 a 0,094 en la logística y de 0,046 a 0,098 en CatBoost. La GRU con agregados queda en 0,103 [0,079; 0,140], sin diferencia pareada con CatBoost (0,005 [-0,019; 0,024]): **la red no suma señal sobre los agregados**. La GRU solo con la secuencia (0,113) equipara a los clásicos con agregados, es decir, la secuencia reconstruye lo que los agregados resumen. Se conserva la logística con ingreso + agregados (el mejor clásico en valid; la red no la supera). **Advertencia de calibración:** esta logística sobreestima el riesgo (ECE de la tabla siguiente) y CatBoost con agregados, que en test tiene un AP equivalente (ΔAP pareado entre ambos 0,004 [-0,034; 0,035]), no se conserva solo porque su AP en valid fue 0,001 menor.

**Calibración del modelo conservado en test (deciles de riesgo):**

| Decil de riesgo | Logística (ingreso + agregados): riesgo medio | observado | n | Tasa histórica: riesgo medio | observado |
|---|---|---|---|---|---|
| 1 | 0,002 | 0,004 | 469 | 0,001 | 0,014 |
| 2 | 0,008 | 0,011 | 469 | 0,005 | 0,012 |
| 3 | 0,019 | 0,013 | 469 | 0,011 | 0,027 |
| 4 | 0,033 | 0,015 | 469 | 0,015 | 0,014 |
| 5 | 0,049 | 0,024 | 468 | 0,020 | 0,019 |
| 6 | 0,069 | 0,015 | 469 | 0,024 | 0,026 |
| 7 | 0,096 | 0,026 | 469 | 0,032 | 0,023 |
| 8 | 0,137 | 0,032 | 469 | 0,050 | 0,047 |
| 9 | 0,212 | 0,051 | 469 | 0,062 | 0,058 |
| 10 | 0,408 | 0,111 | 468 | 0,077 | 0,059 |

### Corte `k` = 4

**Test:**

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica por programa | 0,035 [0,022; 0,056] | 0,633 [0,551; 0,708] | 0,0167 [0,0130; 0,0206] | 0,0088 [0,0072; 0,0144] |
| Logística (perfil de ingreso) | 0,033 [0,021; 0,061] | 0,650 [0,586; 0,713] | 0,0167 [0,0130; 0,0207] | 0,0066 [0,0051; 0,0120] |
| Logística (ingreso + agregados) | 0,049 [0,033; 0,078] | 0,786 [0,739; 0,832] | 0,0176 [0,0141; 0,0214] | 0,0105 [0,0075; 0,0151] |
| CatBoost (perfil de ingreso) | 0,032 [0,021; 0,052] | 0,632 [0,563; 0,699] | 0,0166 [0,0128; 0,0206] | 0,0036 [0,0037; 0,0095] |
| CatBoost (ingreso + agregados) | 0,059 [0,041; 0,091] | 0,803 [0,753; 0,849] | 0,0165 [0,0127; 0,0204] | 0,0064 [0,0039; 0,0110] |
| GRU (ingreso + secuencia) | 0,049 [0,034; 0,075] | 0,760 [0,704; 0,812] | 0,0169 [0,0132; 0,0208] | 0,0064 [0,0042; 0,0110] |
| GRU (ingreso + agregados + secuencia) | 0,048 [0,033; 0,084] | 0,775 [0,727; 0,817] | 0,0169 [0,0132; 0,0207] | 0,0096 [0,0054; 0,0135] |

**Diferencias pareadas en test:**

| Diferencia pareada (test) | ΔAP | ΔROC-AUC | ΔBrier | Lectura (ΔAP) |
|---|---|---|---|---|
| Logística (perfil de ingreso) − Tasa histórica por programa | -0,003 [-0,012; 0,018] | 0,017 [-0,031; 0,073] | 0,0001 [-0,0001; 0,0003] | sin diferencia (el intervalo incluye 0) |
| CatBoost (perfil de ingreso) − Tasa histórica por programa | -0,003 [-0,010; 0,005] | -0,001 [-0,061; 0,068] | -0,0000 [-0,0003; 0,0002] | sin diferencia (el intervalo incluye 0) |
| Logística (ingreso + agregados) − Logística (perfil de ingreso) | 0,016 [0,002; 0,032] | 0,136 [0,078; 0,189] | 0,0008 [0,0003; 0,0014] | mejora |
| CatBoost (ingreso + agregados) − CatBoost (perfil de ingreso) | 0,027 [0,011; 0,049] | 0,171 [0,110; 0,231] | -0,0002 [-0,0004; 0,0000] | mejora |
| CatBoost (perfil de ingreso) − Logística (perfil de ingreso) | -0,001 [-0,021; 0,010] | -0,018 [-0,052; 0,017] | -0,0001 [-0,0002; 0,0001] | sin diferencia (el intervalo incluye 0) |
| CatBoost (ingreso + agregados) − Logística (ingreso + agregados) | 0,010 [-0,001; 0,022] | 0,017 [-0,014; 0,050] | -0,0011 [-0,0016; -0,0006] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + secuencia) − CatBoost (perfil de ingreso) | 0,017 [0,001; 0,036] | 0,128 [0,063; 0,192] | 0,0003 [-0,0001; 0,0006] | mejora |
| GRU (ingreso + agregados + secuencia) − CatBoost (ingreso + agregados) | -0,010 [-0,028; 0,011] | -0,028 [-0,065; 0,005] | 0,0004 [0,0002; 0,0007] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + agregados + secuencia) − Logística (ingreso + agregados) | -0,000 [-0,019; 0,025] | -0,011 [-0,044; 0,023] | -0,0007 [-0,0012; -0,0002] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + secuencia) − Logística (perfil de ingreso) | 0,017 [-0,007; 0,035] | 0,110 [0,053; 0,161] | 0,0002 [-0,0002; 0,0005] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + agregados + secuencia) − GRU (ingreso + secuencia) | -0,001 [-0,010; 0,019] | 0,015 [-0,011; 0,039] | -0,0000 [-0,0002; 0,0002] | sin diferencia (el intervalo incluye 0) |
| CatBoost (ingreso + agregados) − Tasa histórica por programa | 0,023 [0,009; 0,045] | 0,170 [0,102; 0,243] | -0,0002 [-0,0004; 0,0000] | mejora |

Lectura. Con menos eventos (66 en test) los intervalos son anchos. Los agregados mejoran al perfil de ingreso (CatBoost: 0,027 [0,011; 0,049]) y el conservado (CatBoost con agregados) mejora a la tasa histórica en 0,023 [0,009; 0,045]; el perfil solo y las redes no se distinguen de la tasa histórica ni del clásico. La GRU no mejora al clásico.

## 6. T5: eliminación

### Corte `k` = 2

**Test:**

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica por programa | 0,118 [0,106; 0,134] | 0,591 [0,566; 0,616] | 0,0890 [0,0827; 0,0955] | 0,0417 [0,0337; 0,0502] |
| Logística (perfil de ingreso) | 0,196 [0,170; 0,229] | 0,687 [0,663; 0,712] | 0,0860 [0,0797; 0,0922] | 0,0302 [0,0261; 0,0403] |
| Logística (ingreso + agregados) | 0,504 [0,461; 0,556] | 0,888 [0,872; 0,903] | 0,0668 [0,0620; 0,0719] | 0,0326 [0,0262; 0,0407] |
| CatBoost (perfil de ingreso) | 0,178 [0,153; 0,210] | 0,658 [0,632; 0,684] | 0,0853 [0,0786; 0,0917] | 0,0190 [0,0141; 0,0290] |
| CatBoost (ingreso + agregados) | 0,554 [0,507; 0,602] | 0,908 [0,895; 0,921] | 0,0602 [0,0553; 0,0653] | 0,0153 [0,0098; 0,0229] |
| GRU (ingreso + secuencia) | 0,566 [0,524; 0,613] | 0,908 [0,893; 0,922] | 0,0594 [0,0547; 0,0641] | 0,0109 [0,0078; 0,0198] |
| GRU (ingreso + agregados + secuencia) | 0,570 [0,526; 0,617] | 0,908 [0,895; 0,921] | 0,0605 [0,0561; 0,0651] | 0,0177 [0,0130; 0,0257] |

**Valid:**

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica por programa | 0,123 | 0,570 | 0,0904 | 0,0403 |
| Logística (perfil de ingreso) | 0,164 | 0,651 | 0,0904 | 0,0393 |
| Logística (ingreso + agregados) | 0,493 | 0,889 | 0,0648 | 0,0166 |
| CatBoost (perfil de ingreso) | 0,169 | 0,647 | 0,0874 | 0,0180 |
| CatBoost (ingreso + agregados) | 0,518 | 0,896 | 0,0627 | 0,0257 |
| GRU (ingreso + secuencia) | 0,556 | 0,901 | 0,0597 | 0,0222 |
| GRU (ingreso + agregados + secuencia) | 0,541 | 0,906 | 0,0601 | 0,0161 |

**Diferencias pareadas en test:**

| Diferencia pareada (test) | ΔAP | ΔROC-AUC | ΔBrier | Lectura (ΔAP) |
|---|---|---|---|---|
| Logística (perfil de ingreso) − Tasa histórica por programa | 0,078 [0,057; 0,105] | 0,096 [0,071; 0,122] | -0,0030 [-0,0050; -0,0010] | mejora |
| CatBoost (perfil de ingreso) − Tasa histórica por programa | 0,059 [0,037; 0,087] | 0,067 [0,043; 0,092] | -0,0038 [-0,0049; -0,0025] | mejora |
| Logística (ingreso + agregados) − Logística (perfil de ingreso) | 0,308 [0,266; 0,349] | 0,202 [0,177; 0,226] | -0,0192 [-0,0239; -0,0145] | mejora |
| CatBoost (ingreso + agregados) − CatBoost (perfil de ingreso) | 0,376 [0,330; 0,421] | 0,250 [0,225; 0,278] | -0,0251 [-0,0291; -0,0214] | mejora |
| CatBoost (perfil de ingreso) − Logística (perfil de ingreso) | -0,019 [-0,036; -0,001] | -0,028 [-0,044; -0,013] | -0,0008 [-0,0022; 0,0007] | empeora |
| CatBoost (ingreso + agregados) − Logística (ingreso + agregados) | 0,049 [0,025; 0,074] | 0,020 [0,012; 0,030] | -0,0066 [-0,0090; -0,0043] | mejora |
| GRU (ingreso + secuencia) − CatBoost (perfil de ingreso) | 0,388 [0,346; 0,429] | 0,249 [0,223; 0,277] | -0,0259 [-0,0300; -0,0225] | mejora |
| GRU (ingreso + agregados + secuencia) − CatBoost (ingreso + agregados) | 0,017 [-0,010; 0,043] | -0,000 [-0,008; 0,007] | 0,0003 [-0,0017; 0,0024] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + agregados + secuencia) − Logística (ingreso + agregados) | 0,066 [0,039; 0,093] | 0,020 [0,011; 0,031] | -0,0064 [-0,0083; -0,0044] | mejora |
| GRU (ingreso + secuencia) − Logística (perfil de ingreso) | 0,369 [0,327; 0,411] | 0,221 [0,195; 0,247] | -0,0267 [-0,0303; -0,0233] | mejora |
| GRU (ingreso + agregados + secuencia) − GRU (ingreso + secuencia) | 0,004 [-0,016; 0,024] | 0,001 [-0,003; 0,005] | 0,0011 [-0,0005; 0,0026] | sin diferencia (el intervalo incluye 0) |
| CatBoost (ingreso + agregados) − Tasa histórica por programa | 0,435 [0,391; 0,480] | 0,318 [0,291; 0,344] | -0,0288 [-0,0329; -0,0252] | mejora |
| GRU (ingreso + secuencia) − CatBoost (ingreso + agregados) | 0,012 [-0,012; 0,037] | -0,001 [-0,010; 0,008] | -0,0008 [-0,0024; 0,0009] | sin diferencia (el intervalo incluye 0) |

Lectura. La señal viene de los agregados académicos: el AP pasa de 0,196 (solo ingreso) a 0,504 con agregados en la logística y a 0,554 en CatBoost. **Ninguna red supera al clásico:** la GRU solo con la secuencia llega a AP 0,566, pero su ΔAP pareado frente a CatBoost con ingreso + agregados es 0,012 [-0,012; 0,037] (el intervalo incluye 0; antes excluía 0 por poco y se había conservado la red). Con la regla anterior (IC en prueba) se conservó CatBoost con ingreso + agregados. **Con D114 (16-11-2026) la elección se hace con el IC de validación, donde la GRU supera al clásico (+0,038 [+0,007; +0,065]); el modelo conservado pasa a ser la GRU.** Las tablas de calibración y de grupos de `artefactos/resultados_t45.json` ya corresponden a la GRU. La GRU con agregados no mejora a la GRU sin ellos.

**Calibración del modelo conservado en test:**

| Decil de riesgo | CatBoost (ingreso + agregados): riesgo medio | observado | n | Tasa histórica: riesgo medio | observado |
|---|---|---|---|---|---|
| 1 | 0,008 | 0,004 | 469 | 0,046 | 0,028 |
| 2 | 0,010 | 0,006 | 469 | 0,074 | 0,063 |
| 3 | 0,012 | 0,006 | 469 | 0,084 | 0,090 |
| 4 | 0,015 | 0,011 | 469 | 0,093 | 0,069 |
| 5 | 0,018 | 0,002 | 468 | 0,111 | 0,136 |
| 6 | 0,023 | 0,015 | 469 | 0,135 | 0,084 |
| 7 | 0,034 | 0,041 | 469 | 0,160 | 0,095 |
| 8 | 0,083 | 0,111 | 469 | 0,186 | 0,199 |
| 9 | 0,213 | 0,275 | 469 | 0,194 | 0,101 |
| 10 | 0,518 | 0,502 | 468 | 0,225 | 0,116 |

### Corte `k` = 4

**Test:**

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica por programa | 0,072 [0,058; 0,090] | 0,586 [0,544; 0,627] | 0,0590 [0,0538; 0,0636] | 0,0853 [0,0782; 0,0925] |
| Logística (perfil de ingreso) | 0,101 [0,083; 0,130] | 0,689 [0,653; 0,726] | 0,0688 [0,0642; 0,0731] | 0,1136 [0,1059; 0,1211] |
| Logística (ingreso + agregados) | 0,309 [0,253; 0,379] | 0,879 [0,856; 0,900] | 0,0486 [0,0445; 0,0525] | 0,0782 [0,0714; 0,0851] |
| CatBoost (perfil de ingreso) | 0,079 [0,065; 0,101] | 0,635 [0,597; 0,672] | 0,0557 [0,0506; 0,0604] | 0,0758 [0,0685; 0,0830] |
| CatBoost (ingreso + agregados) | 0,314 [0,259; 0,386] | 0,882 [0,860; 0,903] | 0,0466 [0,0426; 0,0505] | 0,0571 [0,0504; 0,0637] |
| GRU (ingreso + secuencia) | 0,314 [0,256; 0,386] | 0,847 [0,812; 0,878] | 0,0628 [0,0584; 0,0670] | 0,1051 [0,0980; 0,1121] |
| GRU (ingreso + agregados + secuencia) | 0,312 [0,258; 0,381] | 0,877 [0,853; 0,901] | 0,0580 [0,0541; 0,0621] | 0,0912 [0,0844; 0,0985] |

**Diferencias pareadas en test:**

| Diferencia pareada (test) | ΔAP | ΔROC-AUC | ΔBrier | Lectura (ΔAP) |
|---|---|---|---|---|
| Logística (perfil de ingreso) − Tasa histórica por programa | 0,030 [0,015; 0,049] | 0,104 [0,072; 0,133] | 0,0098 [0,0077; 0,0121] | mejora |
| CatBoost (perfil de ingreso) − Tasa histórica por programa | 0,007 [-0,004; 0,022] | 0,050 [0,021; 0,075] | -0,0033 [-0,0038; -0,0026] | sin diferencia (el intervalo incluye 0) |
| Logística (ingreso + agregados) − Logística (perfil de ingreso) | 0,207 [0,153; 0,268] | 0,190 [0,155; 0,222] | -0,0202 [-0,0228; -0,0173] | mejora |
| CatBoost (ingreso + agregados) − CatBoost (perfil de ingreso) | 0,236 [0,182; 0,301] | 0,247 [0,213; 0,278] | -0,0091 [-0,0119; -0,0064] | mejora |
| CatBoost (perfil de ingreso) − Logística (perfil de ingreso) | -0,023 [-0,038; -0,010] | -0,054 [-0,078; -0,029] | -0,0131 [-0,0153; -0,0109] | empeora |
| CatBoost (ingreso + agregados) − Logística (ingreso + agregados) | 0,005 [-0,035; 0,053] | 0,003 [-0,006; 0,013] | -0,0019 [-0,0033; -0,0007] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + secuencia) − CatBoost (perfil de ingreso) | 0,235 [0,180; 0,304] | 0,212 [0,171; 0,251] | 0,0071 [0,0028; 0,0114] | mejora |
| GRU (ingreso + agregados + secuencia) − CatBoost (ingreso + agregados) | -0,002 [-0,046; 0,041] | -0,005 [-0,015; 0,007] | 0,0114 [0,0095; 0,0134] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + agregados + secuencia) − Logística (ingreso + agregados) | 0,004 [-0,035; 0,047] | -0,001 [-0,015; 0,013] | 0,0094 [0,0075; 0,0114] | sin diferencia (el intervalo incluye 0) |
| GRU (ingreso + secuencia) − Logística (perfil de ingreso) | 0,212 [0,159; 0,278] | 0,158 [0,114; 0,199] | -0,0060 [-0,0098; -0,0023] | mejora |
| GRU (ingreso + agregados + secuencia) − GRU (ingreso + secuencia) | -0,001 [-0,024; 0,021] | 0,030 [0,017; 0,046] | -0,0048 [-0,0060; -0,0037] | sin diferencia (el intervalo incluye 0) |
| CatBoost (ingreso + agregados) − Tasa histórica por programa | 0,243 [0,188; 0,309] | 0,296 [0,251; 0,335] | -0,0124 [-0,0152; -0,0095] | mejora |

Lectura. Los agregados siguen siendo la fuente de la señal (ΔAP de CatBoost con agregados frente al de solo ingreso: 0,236 [0,182; 0,301]). **Ninguna red supera al clásico**; se conserva la logística con ingreso + agregados. El ECE es alto en todos los modelos (de 0,06 a 0,08): el riesgo predicho es mayor que la tasa observada de test, consecuencia de la deriva y del subregistro de `E` (§3), no de un defecto del ordenamiento (el ROC-AUC de los modelos con agregados se mantiene en torno a 0,89).

**Calibración del modelo conservado en test:**

| Decil de riesgo | Logística (ingreso + agregados): riesgo medio | observado | n | Tasa histórica: riesgo medio | observado |
|---|---|---|---|---|---|
| 1 | 0,030 | 0,003 | 389 | 0,035 | 0,013 |
| 2 | 0,043 | 0,003 | 388 | 0,074 | 0,058 |
| 3 | 0,052 | 0,000 | 389 | 0,088 | 0,048 |
| 4 | 0,063 | 0,003 | 388 | 0,102 | 0,028 |
| 5 | 0,078 | 0,008 | 389 | 0,122 | 0,029 |
| 6 | 0,096 | 0,018 | 388 | 0,133 | 0,070 |
| 7 | 0,124 | 0,028 | 389 | 0,147 | 0,041 |
| 8 | 0,165 | 0,070 | 388 | 0,181 | 0,090 |
| 9 | 0,231 | 0,129 | 389 | 0,207 | 0,060 |
| 10 | 0,418 | 0,258 | 388 | 0,275 | 0,076 |

## 7. Vista multiclase

El mismo snapshot permite predecir el resultado completo (continúa, egreso, transición, eliminación, otra salida). Se comparan las frecuencias de resultado por programa (referencia), una logística multinomial y CatBoost multiclase, ambos con ingreso + agregados. El AP por clase se muestra solo para las clases con al menos 10 eventos en test. Es una vista complementaria: T4 y T5 se evalúan como binarias en §5–§6.

### Corte `k` = 2

| Modelo | Log-loss | Brier multiclase | AP macro | AP transición | AP eliminación | AP continúa | AP otra salida | AP egreso |
|---|---|---|---|---|---|---|---|---|
| Frecuencias de resultado por programa | 0,6239 [0,5920; 0,6569] | 0,2976 [0,2808; 0,3146] | 0,274 [0,220; 0,281] | 0,051 [0,039; 0,066] | 0,118 [0,106; 0,133] | 0,879 [0,867; 0,890] | 0,050 [0,041; 0,065] | — |
| Logística multinomial (ingreso + agregados) | 0,4789 [0,4521; 0,5069] | 0,2240 [0,2112; 0,2373] | 0,435 [0,354; 0,456] | 0,101 [0,071; 0,142] | 0,508 [0,464; 0,558] | 0,960 [0,952; 0,967] | 0,172 [0,134; 0,226] | — |
| CatBoost multiclase (ingreso + agregados) | 0,4485 [0,4225; 0,4754] | 0,2132 [0,2002; 0,2274] | 0,454 [0,371; 0,473] | 0,124 [0,089; 0,175] | 0,556 [0,511; 0,605] | 0,969 [0,963; 0,973] | 0,166 [0,130; 0,216] | — |

Eventos en test: transición 141, eliminación 456, continúa 3.895, otra salida 190, egreso < 10.

| Diferencia pareada (test) | Δ log-loss | Δ AP macro | Δ AP transición | Δ AP eliminación |
|---|---|---|---|---|
| Logística multinomial (ingreso + agregados) − Frecuencias de resultado por programa | -0,1450 [-0,1635; -0,1245] | 0,161 [0,132; 0,180] | 0,050 [0,024; 0,088] | 0,390 [0,350; 0,437] |
| CatBoost multiclase (ingreso + agregados) − Frecuencias de resultado por programa | -0,1754 [-0,1900; -0,1614] | 0,179 [0,149; 0,198] | 0,073 [0,042; 0,117] | 0,438 [0,396; 0,484] |
| CatBoost multiclase (ingreso + agregados) − Logística multinomial (ingreso + agregados) | -0,0304 [-0,0410; -0,0202] | 0,019 [0,004; 0,038] | 0,023 [-0,014; 0,065] | 0,048 [0,020; 0,074] |

### Corte `k` = 4

| Modelo | Log-loss | Brier multiclase | AP macro | AP transición | AP eliminación | AP continúa | AP otra salida | AP egreso |
|---|---|---|---|---|---|---|---|---|
| Frecuencias de resultado por programa | 0,5403 [0,5036; 0,5732] | 0,2222 [0,2074; 0,2355] | 0,216 [0,212; 0,222] | 0,035 [0,022; 0,056] | 0,066 [0,055; 0,082] | 0,922 [0,912; 0,932] | 0,041 [0,033; 0,052] | 0,016 [0,011; 0,024] |
| Logística multinomial (ingreso + agregados) | 0,4193 [0,3935; 0,4453] | 0,1972 [0,1839; 0,2095] | 0,399 [0,368; 0,439] | 0,056 [0,040; 0,085] | 0,300 [0,245; 0,367] | 0,966 [0,959; 0,974] | 0,249 [0,186; 0,324] | 0,425 [0,282; 0,584] |
| CatBoost multiclase (ingreso + agregados) | 0,3937 [0,3686; 0,4198] | 0,1835 [0,1705; 0,1958] | 0,401 [0,372; 0,444] | 0,060 [0,043; 0,089] | 0,306 [0,251; 0,378] | 0,977 [0,973; 0,982] | 0,235 [0,176; 0,316] | 0,426 [0,293; 0,598] |

Eventos en test: transición 66, eliminación 201, continúa 3.448, otra salida 127, egreso 43.

| Diferencia pareada (test) | Δ log-loss | Δ AP macro | Δ AP transición | Δ AP eliminación |
|---|---|---|---|---|
| Logística multinomial (ingreso + agregados) − Frecuencias de resultado por programa | -0,1210 [-0,1393; -0,1032] | 0,183 [0,152; 0,220] | 0,020 [0,005; 0,043] | 0,234 [0,183; 0,299] |
| CatBoost multiclase (ingreso + agregados) − Frecuencias de resultado por programa | -0,1466 [-0,1631; -0,1308] | 0,185 [0,156; 0,228] | 0,025 [0,006; 0,047] | 0,240 [0,186; 0,308] |
| CatBoost multiclase (ingreso + agregados) − Logística multinomial (ingreso + agregados) | -0,0256 [-0,0322; -0,0193] | 0,002 [-0,023; 0,029] | 0,004 [-0,013; 0,021] | 0,006 [-0,039; 0,055] |

Lectura. Los dos modelos reducen el log-loss respecto de la referencia con intervalos claramente bajo 0; CatBoost mejora algo a la logística. La clase que más gana es la eliminación; la transición mejora poco (0,124 [0,089; 0,175] en `k` = 2 frente a 0,051 [0,039; 0,066] de la referencia). Con `k` = 4 los egresos tempranos también se ordenan bien (0,426 [0,293; 0,598]).

## 8. Resultados por programa y facultad

Todo lo de esta sección son **agregados**. Un grupo se reporta solo con n ≥ 100 filas y al menos 10 eventos en test; los demás se suprimen. Para cada grupo se muestran la tasa observada, el riesgo medio predicho y su brecha, con intervalos del 95 % por bootstrap agrupado por persona, y la brecha de la tasa histórica por programa (la referencia que el modelo debe superar). Los resúmenes comparan el error absoluto medio ponderado por tamaño del grupo entre el modelo y la tasa histórica, y la correlación de Spearman entre el riesgo predicho y la tasa observada. Como T4 tiene pocos eventos, se agrega una tabla de **valid + test** con los mismos umbrales, que reporta más grupos.

### Cuántos grupos son reportables

**Solo test:**

| Tarea | k | Nivel | Grupos (total / reportables) | Filas en grupos reportables | Eventos en grupos reportables | Error absoluto medio ponderado del modelo | … de la tasa histórica | Diferencia | ρ de Spearman (pred. vs obs.) |
|---|---|---|---|---|---|---|---|---|---|
| T4 | 2 | programa | 46 / 3 | 635 de 4.688 (14 %) | 37 de 141 | 0,1316 [0,1109; 0,1532] | 0,0085 [0,0046; 0,0281] | 0,1231 [0,0924; 0,1332] | — |
| T4 | 2 | facultad | 13 / 5 | 3.014 de 4.688 (64 %) | 100 de 141 | 0,0690 [0,0626; 0,0766] | 0,0069 [0,0045; 0,0134] | 0,0622 [0,0527; 0,0680] | 0,70 [-0,60; 0,90] |
| T4 | 4 | programa | 47 / 1 | 149 de 3.885 (4 %) | 11 de 66 | 0,0163 [0,0009; 0,0618] | 0,0298 [0,0023; 0,0685] | -0,0135 [-0,0501; 0,0485] | — |
| T4 | 4 | facultad | 13 / 1 | 855 de 3.885 (22 %) | 27 de 66 | 0,0047 [0,0004; 0,0164] | 0,0099 [0,0006; 0,0209] | -0,0052 [-0,0160; 0,0147] | — |
| T5 | 2 | programa | 46 / 15 | 2.892 de 4.688 (62 %) | 318 de 456 | 0,0227 [0,0182; 0,0344] | 0,0362 [0,0334; 0,0513] | -0,0134 [-0,0257; -0,0059] | 0,69 [0,38; 0,84] |
| T5 | 2 | facultad | 13 / 11 | 4.378 de 4.688 (93 %) | 443 de 456 | 0,0130 [0,0104; 0,0221] | 0,0331 [0,0265; 0,0434] | -0,0201 [-0,0303; -0,0068] | 0,72 [0,46; 0,88] |
| T5 | 4 | programa | 47 / 6 | 1.222 de 3.885 (31 %) | 81 de 201 | 0,0776 [0,0651; 0,0909] | 0,0557 [0,0434; 0,0703] | 0,0219 [0,0128; 0,0277] | 0,83 [-0,03; 1,00] |
| T5 | 4 | facultad | 13 / 6 | 2.652 de 3.885 (68 %) | 168 de 201 | 0,0858 [0,0769; 0,0950] | 0,0871 [0,0772; 0,0969] | -0,0013 [-0,0066; 0,0036] | 0,77 [0,09; 0,94] |

**Valid + test:**

| Tarea | k | Nivel | Grupos (total / reportables) | Filas en grupos reportables | Eventos en grupos reportables | Error absoluto medio ponderado del modelo | … de la tasa histórica | Diferencia | ρ de Spearman (pred. vs obs.) |
|---|---|---|---|---|---|---|---|---|---|
| T4 | 2 | programa | 50 / 9 | 3.256 de 8.728 (37 %) | 158 de 275 | 0,0603 [0,0529; 0,0685] | 0,0100 [0,0080; 0,0190] | 0,0503 [0,0372; 0,0556] | 0,83 [0,43; 0,92] |
| T4 | 2 | facultad | 14 / 10 | 7.782 de 8.728 (89 %) | 262 de 275 | 0,0429 [0,0389; 0,0477] | 0,0061 [0,0049; 0,0114] | 0,0368 [0,0292; 0,0402] | 0,94 [0,49; 0,93] |
| T4 | 4 | programa | 50 / 4 | 1.374 de 7.209 (19 %) | 60 de 146 | 0,0185 [0,0106; 0,0296] | 0,0123 [0,0072; 0,0229] | 0,0062 [-0,0103; 0,0195] | — |
| T4 | 4 | facultad | 14 / 6 | 4.593 de 7.209 (64 %) | 130 de 146 | 0,0118 [0,0075; 0,0165] | 0,0075 [0,0046; 0,0126] | 0,0043 [-0,0026; 0,0088] | 0,71 [0,03; 0,89] |
| T5 | 2 | programa | 50 / 23 | 6.718 de 8.728 (77 %) | 727 de 855 | 0,0257 [0,0215; 0,0332] | 0,0373 [0,0349; 0,0476] | -0,0115 [-0,0223; -0,0063] | 0,82 [0,64; 0,87] |
| T5 | 2 | facultad | 14 / 12 | 8.619 de 8.728 (99 %) | 846 de 855 | 0,0190 [0,0145; 0,0247] | 0,0336 [0,0282; 0,0408] | -0,0147 [-0,0248; -0,0048] | 0,69 [0,52; 0,90] |
| T5 | 4 | programa | 50 / 19 | 5.030 de 7.209 (70 %) | 664 de 789 | 0,0270 [0,0263; 0,0397] | 0,0524 [0,0469; 0,0637] | -0,0254 [-0,0303; -0,0130] | 0,81 [0,62; 0,87] |
| T5 | 4 | facultad | 14 / 12 | 7.113 de 7.209 (99 %) | 789 de 789 | 0,0259 [0,0220; 0,0332] | 0,0348 [0,0286; 0,0424] | -0,0089 [-0,0134; -0,0008] | 0,85 [0,66; 0,90] |

### T4, corte `k` = 2

Programas reportables en test:

| Programa | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 200 | 13 | 0,065 [0,033; 0,102] | 0,274 [0,245; 0,306] | 0,209 [0,163; 0,254] | 0,014 [-0,023; 0,046] | 0,095 | 0,509 |
| 8373 · DERECHO | 236 | 14 | 0,059 [0,032; 0,091] | 0,154 [0,140; 0,169] | 0,095 [0,066; 0,122] | 0,006 [-0,026; 0,033] | 0,373 | 0,843 |
| 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 199 | 10 | 0,050 [0,022; 0,083] | 0,148 [0,129; 0,167] | 0,098 [0,064; 0,128] | 0,007 [-0,026; 0,035] | 0,272 | 0,787 |

Facultades reportables en test:

| Facultad | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ingeniería y Ciencias Geológicas | 1.094 | 43 | 0,039 [0,029; 0,051] | 0,146 [0,136; 0,155] | 0,106 [0,091; 0,120] | 0,005 [-0,007; 0,016] | 0,079 | 0,674 |
| Facultad de Ciencias Jurídicas | 500 | 19 | 0,038 [0,022; 0,057] | 0,078 [0,069; 0,088] | 0,040 [0,023; 0,056] | -0,006 [-0,025; 0,009] | 0,289 | 0,785 |
| Escuela de Ingeniería | 569 | 16 | 0,028 [0,016; 0,042] | 0,098 [0,089; 0,107] | 0,070 [0,054; 0,084] | 0,005 [-0,008; 0,017] | 0,179 | 0,781 |
| Facultad de Economía y Administración | 451 | 12 | 0,027 [0,013; 0,042] | 0,097 [0,088; 0,104] | 0,070 [0,054; 0,086] | -0,002 [-0,017; 0,012] | 0,072 | 0,670 |
| Escuela de Ciencias Empresariales | 400 | 10 | 0,025 [0,012; 0,042] | 0,026 [0,024; 0,029] | 0,001 [-0,015; 0,014] | -0,020 [-0,037; -0,007] | 0,082 | 0,775 |

Con valid + test (más grupos):

| Programa | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| 8693 · INGENIERÍA CIVIL | 168 | 13 | 0,077 [0,039; 0,122] | 0,131 [0,108; 0,157] | 0,054 [0,006; 0,102] | -0,015 [-0,059; 0,024] | 0,089 | 0,519 |
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 365 | 27 | 0,074 [0,048; 0,102] | 0,199 [0,180; 0,218] | 0,125 [0,092; 0,157] | 0,005 [-0,023; 0,030] | 0,094 | 0,523 |
| 8213 · ARQUITECTURA | 293 | 20 | 0,068 [0,041; 0,097] | 0,150 [0,136; 0,164] | 0,082 [0,052; 0,112] | -0,017 [-0,046; 0,011] | 0,209 | 0,759 |
| 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 420 | 27 | 0,064 [0,044; 0,089] | 0,100 [0,090; 0,111] | 0,036 [0,012; 0,058] | -0,007 [-0,032; 0,013] | 0,184 | 0,703 |
| 8373 · DERECHO | 445 | 24 | 0,054 [0,032; 0,076] | 0,115 [0,105; 0,124] | 0,061 [0,040; 0,082] | 0,011 [-0,011; 0,032] | 0,268 | 0,751 |
| 8653 · INGENIERÍA CIVIL DE MINAS | 274 | 11 | 0,040 [0,018; 0,066] | 0,115 [0,101; 0,129] | 0,074 [0,048; 0,101] | 0,015 [-0,011; 0,037] | 0,103 | 0,703 |
| 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 313 | 10 | 0,032 [0,013; 0,052] | 0,021 [0,018; 0,024] | -0,011 [-0,031; 0,007] | -0,025 [-0,045; -0,006] | 0,094 | 0,718 |
| 8613 · INGENIERÍA CIVIL INDUSTRIAL | 471 | 13 | 0,028 [0,014; 0,044] | 0,076 [0,067; 0,085] | 0,048 [0,031; 0,062] | 0,004 [-0,012; 0,018] | 0,153 | 0,726 |
| 8323 · INGENIERÍA COMERCIAL | 507 | 13 | 0,026 [0,012; 0,040] | 0,083 [0,075; 0,090] | 0,057 [0,042; 0,071] | -0,003 [-0,018; 0,010] | 0,074 | 0,673 |

| Posición | Mayor tasa observada | Mayor riesgo predicho | Menor tasa observada | Menor riesgo predicho |
|---|---|---|---|---|
| 1 | 8693 · INGENIERÍA CIVIL | 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 8323 · INGENIERÍA COMERCIAL | 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN |
| 2 | 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 8213 · ARQUITECTURA | 8613 · INGENIERÍA CIVIL INDUSTRIAL | 8613 · INGENIERÍA CIVIL INDUSTRIAL |
| 3 | 8213 · ARQUITECTURA | 8693 · INGENIERÍA CIVIL | 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 8323 · INGENIERÍA COMERCIAL |
| 4 | 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 8373 · DERECHO | 8653 · INGENIERÍA CIVIL DE MINAS | 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA |

Coincidencia entre los 5 grupos de mayor tasa observada y los 5 de mayor riesgo predicho: 4.

| Facultad | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| Escuela de Arquitectura | 293 | 20 | 0,068 [0,041; 0,097] | 0,150 [0,136; 0,164] | 0,082 [0,052; 0,112] | -0,017 [-0,046; 0,011] | 0,209 | 0,759 |
| Facultad de Ciencias de Ingeniería y Construcción | 336 | 17 | 0,051 [0,028; 0,075] | 0,094 [0,080; 0,111] | 0,044 [0,017; 0,071] | -0,010 [-0,034; 0,012] | 0,088 | 0,629 |
| Facultad de Ingeniería y Ciencias Geológicas | 2.034 | 77 | 0,038 [0,030; 0,046] | 0,105 [0,099; 0,111] | 0,067 [0,059; 0,077] | 0,007 [-0,001; 0,015] | 0,084 | 0,685 |
| Facultad de Ciencias | 505 | 19 | 0,038 [0,022; 0,056] | 0,085 [0,075; 0,095] | 0,047 [0,029; 0,064] | -0,006 [-0,023; 0,010] | 0,126 | 0,727 |
| Facultad de Ciencias del Mar | 284 | 10 | 0,035 [0,015; 0,058] | 0,086 [0,071; 0,101] | 0,051 [0,025; 0,076] | -0,007 [-0,030; 0,013] | 0,166 | 0,614 |
| Escuela de Ingeniería | 1.097 | 37 | 0,034 [0,024; 0,045] | 0,071 [0,065; 0,076] | 0,037 [0,026; 0,047] | 0,001 [-0,010; 0,011] | 0,123 | 0,708 |
| Facultad de Ciencias Jurídicas | 921 | 30 | 0,033 [0,021; 0,044] | 0,059 [0,053; 0,065] | 0,027 [0,015; 0,038] | -0,000 [-0,011; 0,012] | 0,225 | 0,792 |
| Facultad de Economía y Administración | 806 | 22 | 0,027 [0,016; 0,039] | 0,075 [0,069; 0,080] | 0,047 [0,035; 0,058] | -0,002 [-0,014; 0,009] | 0,067 | 0,632 |
| Facultad de Medicina | 710 | 15 | 0,021 [0,012; 0,032] | 0,043 [0,038; 0,048] | 0,022 [0,012; 0,032] | -0,009 [-0,020; 0,001] | 0,093 | 0,740 |
| Escuela de Ciencias Empresariales | 796 | 15 | 0,019 [0,010; 0,028] | 0,018 [0,017; 0,019] | -0,001 [-0,010; 0,008] | -0,014 [-0,023; -0,005] | 0,073 | 0,768 |

Lectura. El modelo ordena los grupos (ρ de Spearman 0,8 en valid + test) pero **subestima sistemáticamente a los programas de mayor tasa** (las brechas pred. − obs. son negativas en todos los grupos con tasa alta) y su error ponderado es mayor que el de la tasa histórica por programa: el pronóstico agregado de T4 por programa **no mejora** al promedio histórico. A nivel de facultad la diferencia con la tasa histórica no es distinguible de 0.

### T4, corte `k` = 4

| Programa | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 149 | 11 | 0,074 [0,035; 0,119] | 0,058 [0,050; 0,066] | -0,016 [-0,062; 0,024] | 0,030 [-0,015; 0,069] | 0,092 | 0,534 |

| Facultad | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ingeniería y Ciencias Geológicas | 855 | 27 | 0,032 [0,021; 0,043] | 0,027 [0,025; 0,029] | -0,005 [-0,016; 0,006] | 0,010 [-0,002; 0,021] | 0,061 | 0,689 |

Solo un programa y una facultad cumplen los umbrales en test; con valid + test:

| Facultad | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ciencias de Ingeniería y Construcción | 273 | 11 | 0,040 [0,020; 0,065] | 0,017 [0,015; 0,019] | -0,023 [-0,047; -0,003] | -0,006 [-0,030; 0,015] | 0,106 | 0,671 |
| Facultad de Ingeniería y Ciencias Geológicas | 1.593 | 56 | 0,035 [0,026; 0,045] | 0,026 [0,025; 0,028] | -0,009 [-0,018; 0,000] | 0,006 [-0,003; 0,015] | 0,108 | 0,756 |
| Facultad de Ciencias | 417 | 12 | 0,029 [0,014; 0,046] | 0,014 [0,013; 0,015] | -0,015 [-0,032; -0,000] | -0,017 [-0,035; -0,003] | 0,079 | 0,782 |
| Escuela de Ingeniería | 895 | 24 | 0,027 [0,018; 0,038] | 0,009 [0,009; 0,010] | -0,018 [-0,029; -0,009] | -0,009 [-0,021; 0,000] | 0,210 | 0,848 |
| Facultad de Economía y Administración | 659 | 13 | 0,020 [0,010; 0,030] | 0,010 [0,009; 0,011] | -0,010 [-0,020; 0,000] | -0,010 [-0,021; -0,000] | 0,047 | 0,676 |
| Facultad de Ciencias Jurídicas | 756 | 14 | 0,019 [0,010; 0,029] | 0,011 [0,010; 0,012] | -0,007 [-0,018; 0,001] | 0,001 [-0,009; 0,010] | 0,115 | 0,820 |

### T5, corte `k` = 2

| Programa | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| 8653 · INGENIERÍA CIVIL DE MINAS | 150 | 29 | 0,193 [0,128; 0,260] | 0,144 [0,116; 0,173] | -0,049 [-0,104; 0,005] | -0,016 [-0,083; 0,050] | 0,631 | 0,860 |
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 200 | 35 | 0,175 [0,124; 0,227] | 0,136 [0,112; 0,160] | -0,039 [-0,084; 0,002] | 0,015 [-0,037; 0,066] | 0,619 | 0,872 |
| 8403 · GEOLOGÍA | 123 | 20 | 0,163 [0,098; 0,226] | 0,128 [0,094; 0,165] | -0,034 [-0,083; 0,014] | -0,047 [-0,110; 0,018] | 0,770 | 0,933 |
| 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 140 | 21 | 0,150 [0,092; 0,211] | 0,134 [0,103; 0,166] | -0,016 [-0,061; 0,022] | -0,004 [-0,064; 0,054] | 0,765 | 0,936 |
| 8266 · INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 110 | 16 | 0,145 [0,083; 0,213] | 0,092 [0,069; 0,119] | -0,053 [-0,110; -0,000] | -0,009 [-0,077; 0,053] | 0,587 | 0,854 |
| 8323 · INGENIERÍA COMERCIAL | 279 | 37 | 0,133 [0,094; 0,170] | 0,120 [0,098; 0,142] | -0,013 [-0,042; 0,017] | -0,020 [-0,058; 0,018] | 0,651 | 0,935 |
| 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 199 | 24 | 0,121 [0,076; 0,165] | 0,093 [0,072; 0,115] | -0,028 [-0,064; 0,006] | 0,075 [0,031; 0,120] | 0,710 | 0,946 |
| 8233 · INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 151 | 14 | 0,093 [0,049; 0,140] | 0,138 [0,110; 0,170] | 0,046 [0,006; 0,085] | 0,126 [0,079; 0,170] | 0,509 | 0,869 |
| 8376 · DERECHO | 264 | 24 | 0,091 [0,057; 0,127] | 0,079 [0,063; 0,096] | -0,012 [-0,040; 0,015] | -0,007 [-0,043; 0,027] | 0,661 | 0,940 |
| 8483 · QUÍMICA Y FARMACIA | 122 | 11 | 0,090 [0,040; 0,143] | 0,095 [0,067; 0,127] | 0,005 [-0,036; 0,044] | 0,008 [-0,045; 0,058] | 0,597 | 0,930 |
| 8326 · INGENIERÍA COMERCIAL | 260 | 23 | 0,088 [0,056; 0,125] | 0,064 [0,051; 0,080] | -0,024 [-0,057; 0,005] | -0,004 [-0,041; 0,028] | 0,433 | 0,820 |
| 8373 · DERECHO | 236 | 20 | 0,085 [0,051; 0,123] | 0,088 [0,070; 0,108] | 0,003 [-0,033; 0,035] | 0,108 [0,070; 0,142] | 0,475 | 0,893 |
| 8213 · ARQUITECTURA | 155 | 12 | 0,077 [0,039; 0,119] | 0,120 [0,091; 0,152] | 0,043 [0,008; 0,079] | 0,093 [0,051; 0,131] | 0,575 | 0,934 |
| 8613 · INGENIERÍA CIVIL INDUSTRIAL | 243 | 18 | 0,074 [0,045; 0,110] | 0,092 [0,076; 0,111] | 0,018 [-0,015; 0,048] | 0,018 [-0,018; 0,047] | 0,471 | 0,901 |
| 8616 · INGENIERÍA CIVIL INDUSTRIAL | 260 | 14 | 0,054 [0,028; 0,083] | 0,054 [0,041; 0,068] | 0,000 [-0,023; 0,020] | 0,016 [-0,013; 0,042] | 0,682 | 0,917 |

| Posición | Mayor tasa observada | Mayor riesgo predicho | Menor tasa observada | Menor riesgo predicho |
|---|---|---|---|---|
| 1 | 8653 · INGENIERÍA CIVIL DE MINAS | 8653 · INGENIERÍA CIVIL DE MINAS | 8616 · INGENIERÍA CIVIL INDUSTRIAL | 8616 · INGENIERÍA CIVIL INDUSTRIAL |
| 2 | 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 8233 · INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 8613 · INGENIERÍA CIVIL INDUSTRIAL | 8326 · INGENIERÍA COMERCIAL |
| 3 | 8403 · GEOLOGÍA | 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 8213 · ARQUITECTURA | 8376 · DERECHO |
| 4 | 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 8373 · DERECHO | 8373 · DERECHO |
| 5 | 8266 · INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 8403 · GEOLOGÍA | 8326 · INGENIERÍA COMERCIAL | 8266 · INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN |
| 6 | 8323 · INGENIERÍA COMERCIAL | 8213 · ARQUITECTURA | 8483 · QUÍMICA Y FARMACIA | 8613 · INGENIERÍA CIVIL INDUSTRIAL |
| 7 | 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 8323 · INGENIERÍA COMERCIAL | 8376 · DERECHO | 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA |

Coincidencia entre los 5 grupos de mayor tasa observada y los 5 de mayor riesgo predicho: 4.

| Facultad | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ciencias de Ingeniería y Construcción | 171 | 28 | 0,164 [0,111; 0,219] | 0,148 [0,117; 0,180] | -0,016 [-0,061; 0,031] | 0,032 [-0,023; 0,085] | 0,546 | 0,864 |
| Facultad de Ingeniería y Ciencias Geológicas | 1.094 | 149 | 0,136 [0,116; 0,155] | 0,128 [0,119; 0,138] | -0,008 [-0,026; 0,009] | 0,034 [0,014; 0,053] | 0,564 | 0,878 |
| Escuela de Ciencias Empresariales | 400 | 44 | 0,110 [0,077; 0,141] | 0,088 [0,074; 0,105] | -0,022 [-0,048; 0,004] | -0,004 [-0,035; 0,028] | 0,604 | 0,874 |
| Facultad de Ciencias del Mar | 176 | 19 | 0,108 [0,063; 0,156] | 0,122 [0,097; 0,152] | 0,015 [-0,024; 0,048] | 0,062 [0,014; 0,106] | 0,637 | 0,862 |
| Facultad de Economía y Administración | 451 | 48 | 0,106 [0,080; 0,134] | 0,102 [0,086; 0,119] | -0,004 [-0,025; 0,016] | 0,010 [-0,017; 0,037] | 0,700 | 0,955 |
| Escuela de Ingeniería | 569 | 54 | 0,095 [0,071; 0,120] | 0,075 [0,063; 0,086] | -0,020 [-0,041; -0,001] | 0,032 [0,007; 0,057] | 0,657 | 0,921 |
| Facultad de Ciencias Jurídicas | 500 | 44 | 0,088 [0,064; 0,113] | 0,083 [0,072; 0,096] | -0,005 [-0,028; 0,016] | 0,047 [0,021; 0,071] | 0,551 | 0,920 |
| Escuela de Arquitectura | 155 | 12 | 0,077 [0,039; 0,119] | 0,120 [0,091; 0,152] | 0,043 [0,008; 0,079] | 0,093 [0,051; 0,131] | 0,575 | 0,934 |
| Facultad de Ciencias | 249 | 19 | 0,076 [0,045; 0,111] | 0,116 [0,092; 0,142] | 0,039 [0,009; 0,069] | 0,044 [0,009; 0,075] | 0,358 | 0,842 |
| Facultad de Medicina | 358 | 16 | 0,045 [0,024; 0,067] | 0,040 [0,031; 0,051] | -0,004 [-0,024; 0,014] | 0,004 [-0,019; 0,024] | 0,328 | 0,938 |
| Facultad de Educación | 255 | 10 | 0,039 [0,019; 0,064] | 0,041 [0,031; 0,053] | 0,001 [-0,019; 0,020] | 0,065 [0,040; 0,086] | 0,532 | 0,941 |

| Posición | Mayor tasa observada | Mayor riesgo predicho | Menor tasa observada | Menor riesgo predicho |
|---|---|---|---|---|
| 1 | Facultad de Ciencias de Ingeniería y Construcción | Facultad de Ciencias de Ingeniería y Construcción | Facultad de Educación | Facultad de Medicina |
| 2 | Facultad de Ingeniería y Ciencias Geológicas | Facultad de Ingeniería y Ciencias Geológicas | Facultad de Medicina | Facultad de Educación |
| 3 | Escuela de Ciencias Empresariales | Facultad de Ciencias del Mar | Facultad de Ciencias | Escuela de Ingeniería |
| 4 | Facultad de Ciencias del Mar | Escuela de Arquitectura | Escuela de Arquitectura | Facultad de Ciencias Jurídicas |
| 5 | Facultad de Economía y Administración | Facultad de Ciencias | Facultad de Ciencias Jurídicas | Escuela de Ciencias Empresariales |

Coincidencia entre los 5 grupos de mayor tasa observada y los 5 de mayor riesgo predicho: 3.

Lectura. Aquí el pronóstico agregado sí agrega valor: con 15 programas y 11 facultades reportables, el error ponderado del modelo es menor que el de la tasa histórica y el orden predicho acompaña al observado (ρ ≈ 0,7). La coincidencia entre los grupos de mayor tasa observada y los de mayor riesgo es parcial.

### T5, corte `k` = 4

| Programa | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 149 | 18 | 0,121 [0,071; 0,172] | 0,223 [0,194; 0,252] | 0,102 [0,058; 0,145] | 0,055 [0,003; 0,105] | 0,540 | 0,836 |
| 8373 · DERECHO | 190 | 12 | 0,063 [0,032; 0,102] | 0,144 [0,131; 0,159] | 0,081 [0,047; 0,110] | 0,155 [0,116; 0,186] | 0,350 | 0,865 |
| 8376 · DERECHO | 216 | 13 | 0,060 [0,031; 0,092] | 0,134 [0,122; 0,148] | 0,074 [0,044; 0,102] | 0,073 [0,041; 0,103] | 0,339 | 0,881 |
| 8613 · INGENIERÍA CIVIL INDUSTRIAL | 217 | 13 | 0,060 [0,030; 0,095] | 0,149 [0,136; 0,163] | 0,089 [0,058; 0,119] | 0,031 [-0,004; 0,061] | 0,195 | 0,847 |
| 8323 · INGENIERÍA COMERCIAL | 220 | 13 | 0,059 [0,030; 0,092] | 0,126 [0,113; 0,140] | 0,067 [0,040; 0,093] | 0,025 [-0,008; 0,054] | 0,453 | 0,896 |
| 8326 · INGENIERÍA COMERCIAL | 230 | 12 | 0,052 [0,025; 0,082] | 0,114 [0,103; 0,126] | 0,062 [0,036; 0,088] | 0,011 [-0,018; 0,038] | 0,321 | 0,911 |

| Facultad | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ciencias | 210 | 18 | 0,086 [0,050; 0,125] | 0,174 [0,152; 0,194] | 0,088 [0,052; 0,123] | 0,082 [0,043; 0,118] | 0,343 | 0,896 |
| Facultad de Ingeniería y Ciencias Geológicas | 855 | 65 | 0,076 [0,059; 0,094] | 0,187 [0,177; 0,197] | 0,111 [0,094; 0,127] | 0,114 [0,095; 0,133] | 0,358 | 0,857 |
| Facultad de Ciencias Jurídicas | 406 | 25 | 0,062 [0,039; 0,085] | 0,139 [0,130; 0,149] | 0,077 [0,056; 0,100] | 0,111 [0,088; 0,134] | 0,339 | 0,873 |
| Facultad de Economía y Administración | 369 | 21 | 0,057 [0,034; 0,080] | 0,123 [0,112; 0,134] | 0,066 [0,046; 0,084] | 0,044 [0,022; 0,066] | 0,577 | 0,939 |
| Escuela de Ciencias Empresariales | 334 | 17 | 0,051 [0,029; 0,076] | 0,113 [0,104; 0,122] | 0,062 [0,039; 0,082] | 0,020 [-0,007; 0,042] | 0,313 | 0,911 |
| Escuela de Ingeniería | 478 | 22 | 0,046 [0,029; 0,066] | 0,126 [0,117; 0,134] | 0,080 [0,059; 0,098] | 0,101 [0,081; 0,118] | 0,172 | 0,793 |

Con valid + test:

| Programa | n | Eventos | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la tasa histórica | AP | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| 8606 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 317 | 83 | 0,262 [0,212; 0,310] | 0,156 [0,145; 0,168] | -0,106 [-0,152; -0,062] | -0,078 [-0,126; -0,028] | 0,558 | 0,813 |
| 8266 · INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 147 | 37 | 0,252 [0,183; 0,321] | 0,150 [0,130; 0,173] | -0,101 [-0,168; -0,036] | -0,113 [-0,182; -0,045] | 0,425 | 0,719 |
| 8603 · INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 268 | 58 | 0,216 [0,166; 0,267] | 0,213 [0,194; 0,233] | -0,003 [-0,047; 0,043] | -0,041 [-0,092; 0,010] | 0,564 | 0,817 |
| 8683 · INGENIERÍA CIVIL METALÚRGICA | 121 | 23 | 0,190 [0,126; 0,261] | 0,205 [0,178; 0,238] | 0,015 [-0,051; 0,077] | -0,005 [-0,077; 0,059] | 0,390 | 0,775 |
| 8653 · INGENIERÍA CIVIL DE MINAS | 208 | 37 | 0,178 [0,128; 0,230] | 0,177 [0,159; 0,197] | -0,001 [-0,050; 0,050] | 0,016 [-0,036; 0,066] | 0,393 | 0,717 |
| 8693 · INGENIERÍA CIVIL | 129 | 22 | 0,171 [0,108; 0,241] | 0,158 [0,136; 0,183] | -0,013 [-0,076; 0,041] | 0,023 [-0,047; 0,085] | 0,502 | 0,777 |
| 8403 · GEOLOGÍA | 217 | 34 | 0,157 [0,110; 0,205] | 0,132 [0,117; 0,147] | -0,025 [-0,069; 0,019] | 0,162 [0,113; 0,208] | 0,432 | 0,758 |
| 8373 · DERECHO | 367 | 54 | 0,147 [0,111; 0,184] | 0,136 [0,124; 0,146] | -0,011 [-0,045; 0,022] | 0,071 [0,034; 0,107] | 0,462 | 0,835 |
| 8376 · DERECHO | 389 | 53 | 0,136 [0,103; 0,171] | 0,129 [0,120; 0,138] | -0,007 [-0,042; 0,024] | -0,003 [-0,038; 0,030] | 0,264 | 0,739 |
| 8613 · INGENIERÍA CIVIL INDUSTRIAL | 422 | 56 | 0,133 [0,101; 0,166] | 0,134 [0,124; 0,143] | 0,001 [-0,030; 0,029] | -0,042 [-0,075; -0,010] | 0,418 | 0,826 |
| 8213 · ARQUITECTURA | 222 | 28 | 0,126 [0,084; 0,173] | 0,130 [0,113; 0,148] | 0,004 [-0,037; 0,037] | -0,025 [-0,071; 0,017] | 0,571 | 0,859 |
| 8233 · INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 186 | 21 | 0,113 [0,069; 0,156] | 0,185 [0,163; 0,207] | 0,072 [0,034; 0,112] | 0,174 [0,131; 0,218] | 0,458 | 0,826 |
| 8673 · INGENIERÍA EN CONSTRUCCIÓN | 112 | 11 | 0,098 [0,047; 0,155] | 0,140 [0,117; 0,167] | 0,042 [-0,011; 0,089] | 0,167 [0,110; 0,218] | 0,403 | 0,851 |
| 8326 · INGENIERÍA COMERCIAL | 432 | 40 | 0,093 [0,065; 0,121] | 0,100 [0,092; 0,109] | 0,007 [-0,019; 0,034] | -0,029 [-0,058; -0,001] | 0,454 | 0,889 |
| 8616 · INGENIERÍA CIVIL INDUSTRIAL | 431 | 39 | 0,090 [0,064; 0,117] | 0,104 [0,096; 0,112] | 0,014 [-0,011; 0,038] | 0,035 [0,009; 0,062] | 0,395 | 0,856 |
| 8483 · QUÍMICA Y FARMACIA | 207 | 15 | 0,072 [0,037; 0,111] | 0,121 [0,107; 0,136] | 0,048 [0,016; 0,077] | 0,090 [0,051; 0,125] | 0,491 | 0,908 |
| 8323 · INGENIERÍA COMERCIAL | 401 | 29 | 0,072 [0,049; 0,099] | 0,112 [0,102; 0,122] | 0,039 [0,017; 0,059] | 0,011 [-0,015; 0,035] | 0,556 | 0,928 |
| 8223 · PEDAGOGÍA EN INGLÉS | 193 | 11 | 0,057 [0,026; 0,093] | 0,092 [0,077; 0,110] | 0,035 [0,009; 0,058] | 0,038 [0,002; 0,069] | 0,730 | 0,929 |
| 8896 · INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 261 | 13 | 0,050 [0,023; 0,078] | 0,087 [0,077; 0,098] | 0,037 [0,011; 0,058] | 0,036 [0,008; 0,063] | 0,534 | 0,944 |

Lectura. Las brechas son positivas en casi todos los grupos: el modelo sobrestima la eliminación de las cohortes 2022–2023 (deriva y subregistro de `E`, §3). En test el error ponderado por programa es mayor que el de la tasa histórica; en valid + test es menor. Es un resultado que depende de qué cohortes se miren, no una propiedad estable del modelo.

## 9. Equidad por sexo (descriptivo)

`sexo` no es variable de ningún modelo; se usa solo para comparar el desempeño. No se aplica ninguna corrección y no se interpretan causas. Los grupos pequeños se muestran con su `n`.

### T4

`k` = 2:

| Sexo | n | Tasa observada | Riesgo medio | Brecha (pred. − obs.) | AP | ROC-AUC | Recall@10 % | ECE |
|---|---|---|---|---|---|---|---|---|
| F | 2.128 | 0,031 | 0,099 | +0,068 | 0,162 | 0,752 | 0,462 | 0,0699 |
| M | 2.559 | 0,030 | 0,107 | +0,078 | 0,067 | 0,714 | 0,263 | 0,0781 |

Brechas F − M: tasa observada +0,001, riesgo medio -0,009, AP +0,095, Recall@10 % +0,198, brecha de calibración -0,010.

`k` = 4:

| Sexo | n | Tasa observada | Riesgo medio | Brecha (pred. − obs.) | AP | ROC-AUC | Recall@10 % | ECE |
|---|---|---|---|---|---|---|---|---|
| F | 1.801 | 0,013 | 0,011 | -0,003 | 0,056 | 0,795 | 0,458 | 0,0056 |
| M | 2.083 | 0,020 | 0,015 | -0,005 | 0,063 | 0,799 | 0,381 | 0,0076 |

Brechas F − M: tasa observada -0,007, riesgo medio -0,005, AP -0,008, Recall@10 % +0,077, brecha de calibración +0,002.

### T5

`k` = 2:

| Sexo | n | Tasa observada | Riesgo medio | Brecha (pred. − obs.) | AP | ROC-AUC | Recall@10 % | ECE |
|---|---|---|---|---|---|---|---|---|
| F | 2.128 | 0,083 | 0,081 | -0,002 | 0,587 | 0,925 | 0,597 | 0,0133 |
| M | 2.559 | 0,109 | 0,104 | -0,006 | 0,534 | 0,894 | 0,468 | 0,0161 |

Brechas F − M: tasa observada -0,027, riesgo medio -0,023, AP +0,053, Recall@10 % +0,129, brecha de calibración +0,004.

`k` = 4:

| Sexo | n | Tasa observada | Riesgo medio | Brecha (pred. − obs.) | AP | ROC-AUC | Recall@10 % | ECE |
|---|---|---|---|---|---|---|---|---|
| F | 1.801 | 0,039 | 0,114 | +0,074 | 0,258 | 0,894 | 0,592 | 0,0745 |
| M | 2.083 | 0,062 | 0,144 | +0,081 | 0,346 | 0,865 | 0,454 | 0,0814 |

Brechas F − M: tasa observada -0,023, riesgo medio -0,030, AP -0,088, Recall@10 % +0,138, brecha de calibración -0,007.

Lectura. Las tasas observadas difieren entre mujeres y hombres (en T5 la de las mujeres es menor) y el riesgo predicho acompaña esa diferencia: la brecha de calibración difiere entre sexos en no más de 0,01. El AP y el Recall@10 % varían entre sexos, pero se calculan sobre pocos eventos en T4 y sin intervalo, de modo que no se interpretan como diferencia de desempeño.

### Deriva por cohorte y Plan Común

| Grupo | n | Tasa observada | Riesgo medio | Brecha | AP | ROC-AUC |
|---|---|---|---|---|---|---|
| 2022 | 2.123 | 0,131 | 0,098 | -0,033 | 0,646 | 0,919 |
| 2023 | 2.565 | 0,069 | 0,089 | +0,020 | 0,467 | 0,898 |

La tasa observada de eliminación cae de la cohorte 2022 a la 2023 mientras el riesgo medio predicho se mantiene: es la señal de la deriva descrita en §3. En T4 la diferencia entre cohortes es menos marcada:

| Grupo | n | Tasa observada | Riesgo medio | Brecha | AP | ROC-AUC |
|---|---|---|---|---|---|---|
| 2022 | 2.123 | 0,037 | 0,085 | +0,048 | 0,155 | 0,793 |
| 2023 | 2.565 | 0,025 | 0,119 | +0,094 | 0,072 | 0,676 |

## 10. Costo computacional

Ejecución completa (snapshot ya construido): 14 minutos, RAM máxima 1585 MB, GPU NVIDIA GeForce RTX 4060 Laptop GPU (memoria máxima de la GRU menor a 0,1 GB). Segundos por modelo (tres semillas de GRU, tres particiones de CatBoost):

| k | Tarea | Logística (perfil de ingreso) | Logística (ingreso + agregados) | CatBoost (perfil de ingreso) | CatBoost (ingreso + agregados) | GRU (ingreso + secuencia) | GRU (ingreso + agregados + secuencia) |
|---|---|---|---|---|---|---|---|
| 2 | T4 | 1 s | 1 s | 35 s | 51 s | 6 s | 8 s |
| 2 | T5 | 1 s | 1 s | 28 s | 37 s | 4 s | 5 s |
| 2 | multiclase | logística 2 s · CatBoost 69 s | | | | | |
| 4 | T4 | 1 s | 1 s | 25 s | 40 s | 5 s | 6 s |
| 4 | T5 | 1 s | 1 s | 33 s | 30 s | 3 s | 3 s |
| 4 | multiclase | logística 1 s · CatBoost 67 s | | | | | |

Los modelos clásicos son baratos y los resultados de la GRU no justifican un costo adicional de mantenimiento, salvo el margen estrecho de T5 con `k` = 2.

## 11. Límites y alcance

1. **El uso no está aprobado.** Este informe es técnico. Las predicciones individuales no se publican ni se exponen en la Bóveda; los agregados por programa y facultad de §8 tampoco tienen endpoint ni vista (P74).
2. **T5 mide el estado `E`, no «reprobación grave».** Que `E` sea siempre una eliminación académica no está confirmado (P70), y una parte de las eliminaciones figura matriculada en el período del horizonte (P72): T5 se lee como «eliminación registrada en los dos semestres siguientes al corte».
3. **T4 depende del mart de traslados (D48–D51).** Sus reglas conservadoras siguen pendientes de validar (P64–P69); el momento del traslado es el primer período del destino (P71) y los traslados ambiguos quedan fuera de los modelos.
4. **Pocos eventos de T4 por programa.** Con 2–3 % de transiciones, la mayoría de los programas no llega a 10 eventos en test: §8 informa cuántos grupos son reportables y complementa con valid + test; los demás se suprimen.
5. **Deriva y subregistro de `E` (P75).** La tasa de eliminación cambia entre train, valid y test (docencia remota en 2020–2021) y, desde 202420, el estado `E` aparece subregistrado (§3). La métrica de T5 en test depende de qué períodos se incluyan: la sensibilidad de §3 muestra la diferencia. No se recalibró ni se corrigieron las etiquetas; antes de cualquier uso de T5 hay que aclarar con la fuente si la caída de `E` es real o un rezago de carga.
6. **La vinculación del Plan Común se decide con el futuro (D47).** Es una propiedad de la unidad, no de los atributos; las pruebas de perturbación garantizan que ningún dato posterior al corte entra en los atributos.
7. **Equidad solo descriptiva.** No se aplicó ninguna corrección ni se evaluó causalidad; `sexo` no es variable, pero otras variables pueden representarlo parcialmente.
8. **Facultades solo con código** (P76).

## 12. Reproducción

```
.venv-ml/Scripts/python.exe -m pipelines.migrate                  # 017_snapshot_t45.sql
.venv-ml/Scripts/python.exe -m pipelines.snapshots.t45            # reconstruye neural_mart.snapshot_t45 (+ _semestre, _resumen)
.venv-ml/Scripts/python.exe -u -m evaluation.run_t45              # artefactos/resultados_t45.json (agregados), MLflow t45_transicion_eliminacion
.venv-ml/Scripts/python.exe tools/informe_t45.py --doc            # regenera este documento
```

Entorno: `.venv-ml` (Python 3.11; torch con CUDA, CatBoost, scikit-learn, pandas, MLflow). Credenciales solo por las variables `DEV_*` del entorno. Pruebas: `tests/unit/test_snapshot_t45.py` (reglas, exclusividad mutua, horizonte y censura, Plan Común, perturbación y borrado), `tests/unit/test_metrics_t45.py` (bootstrap agrupado, supresión de grupos), `tests/integration/test_snapshot_t45.py` (recálculo SQL independiente).


## 13. Variables nuevas (18-11-2026)

**Pregunta.** Las respuestas de la DAI del 18-11-2026 (P117, P118, P121, P122, P125 y P126) permiten construir, sin datos nuevos, el riesgo reglamentario de T5 y el rendimiento propio frente a general de T4. ¿Mejoran los modelos conservados bajo la regla única D114 (elegir en validación con el AP; la prueba solo confirma; el empate se resuelve a favor del modelo más simple)? Solo agregados; ninguna predicción por persona figura aquí.

**Resultado en una línea.** Las variables reglamentarias **mejoran a T5 en validación en `k` = 2 y 4 con IC que excluye el cero** y la prueba no las contradice; por la regla de simplicidad de D114 el candidato que queda es un modelo clásico con las variables nuevas (`cb_agg+reg_alc` en `k` = 2 y `lr_agg+reg_alc` en `k` = 4), y la GRU con las mismas variables es el mejor punto en validación pero no se separa de ellos. En T4 los candidatos pasan la regla en validación (`k` = 2: `lr_agg+t4`; `k` = 4: `lr_agg+todo`) **pero la prueba no lo confirma** (ΔAP +0,001 [−0,017; +0,020] y −0,011 [−0,031; +0,023]) y en `k` = 4 el ROC-AUC de prueba baja de 0,803 a 0,694: se informan como candidatos, con la recomendación de no adoptar T4 hasta confirmarlos. Las predicciones de los candidatos que cumplen D114 quedan guardadas junto a las del modelo conservado (claves nuevas en `artefactos/preds/t45_k{2,4}_{valid,test}.npz`); los arreglos que ya estaban no cambian (verificado bit a bit).

### 13.1 Variables y construcción

Tabla lateral `neural_mart.snapshot_variables_nuevas` (migración 031; clave `episodio_id, k`; los snapshots oficiales no cambian y las filas de T4 y T5 son un subconjunto de las de T3: mismas unidades y mismos cortes). Construcción en `pipelines/snapshots/features_variables.py` y `rules_variables.py`; se reconstruye con `python -m pipelines.snapshots.variables_nuevas`. Todas leen intentos con semestre `<= k`.

| Bloque | Variables (definición) |
|---|---|
| `reg` (T5; P117, P118, P122) | `reg_rep2_total`, `reg_rep2_cb`, `reg_rep2_cp`: asignaturas distintas reprobadas en **2.ª oportunidad** (total y por ciclo de la asignatura: `CB` / `CP` del texto del semestre de la malla). `reg_rep3_cursos`: asignaturas distintas reprobadas en 3.ª oportunidad o más. `reg_cursos_riesgo_3ra`: asignaturas cuyo último intento fue una reprobación en 2.ª oportunidad (el próximo es la 3.ª). `reg_pendientes_reprobados`: asignaturas cuyo último intento es una reprobación. `reg_ciclo_cb_actual` y `reg_sem_en_cb`: ciclo del último semestre cursado y semestres cursados en Ciclo Básico. **Distancias al umbral de eliminación** (cero = ya se cumple), calculadas **siempre con los dos reglamentos**: `reg_dist_2da_antiguo` (5 en Ciclo Básico, 3 en Profesional; Art. 50-C y 52-A), `reg_dist_3ra_antiguo` (1; 50-B y 52-B), `reg_dist_2da_nuevo` (6; 46-A) y `reg_dist_3ra_nuevo` (2 asignaturas distintas; 46-B). `reg_n_sem_avance_lt50`, `reg_consec_avance_lt50` y `reg_dist_avance_antiguo` (2 menos los semestres consecutivos hasta el corte; 52-C): el avance de un semestre es créditos aprobados sobre créditos evaluados de ese semestre |
| `alc` (T3 y T5; P121) | `alc_sem_pendiente_antiguo`, `alc_rezago`, `alc_pendiente_gt4` y `alc_n_bloqueados` (definidas en `10_benchmark_t3.md` §12.2) |
| `reg_alc` | los dos bloques anteriores (19 columnas): el candidato previsto de T5 |
| `t4` (P40, P125) | `n_propios_eval`, `tasa_propios`, `prom_propios`, `n_generales_eval`, `tasa_generales`, `prom_generales` y `brecha_propios_generales` (rendimiento en asignaturas propias frente a formación general), y `n_episodios_previos` y `n_cc_previos` (episodios de pregrado de la misma persona con admisión anterior a la de este y cuántos entraron por cambio de carrera) |
| `todo` | todas las variables nuevas (también los créditos y el Capstone de T3) |

- **Reglamento vigente.** Se calculan las distancias del reglamento antiguo (Art. 50 y 52, hasta `202510`) y del nuevo (Art. 46, desde `202520`) en **todos** los cortes y no se agrega una bandera del reglamento vigente: todos los cortes de entrenamiento, validación y prueba son anteriores a `202520`, así que la bandera sería constante. P118 advierte que un modelo entrenado con el reglamento anterior sobreestimará la eliminación con el nuevo; esta evaluación **no puede** medir ese efecto porque ninguna etiqueta de entrenamiento o prueba se generó bajo el reglamento nuevo.
- **Formación propia y general.** P40 aclara que los prefijos de `malla_formacion` son nombres de departamento. Se leen así (lectura del estudio, abierta con la DAI): general = `UNFG`, `UNFV` y `UNFE` (formación general, valórica y electiva); propia = `UNFP` (formación profesional) o sin código (el núcleo disciplinar del programa); `UNFI`, `UNFC`, `UNES` y `UNFB` no entran. Cobertura de la tasa de aprobación propia: 96,7 % en `k` = 2 y 99,7 % en `k` = 4; de la general: 69,9 % y 81,2 %.
- **P58.** Los semestres `201920` y `202010` no tienen reprobaciones registradas: las filas de esos períodos se tratan como no evaluadas, de modo que los conteos de reprobación son cotas inferiores para las cohortes 2019 y 2020 (el promedio de `reg_rep2_total` en `k` = 2 es 0,26 a 0,39 en las cohortes 2015 a 2018, 0,01 en 2019 y 0,003 en 2020). Como estas cohortes están en validación (2020 y 2021 en T4 y T5), cada candidato se evalúa también **sin** las filas con algún semestre sin reprobaciones registradas: la columna «sin P58». La ganancia no depende de esas filas (en `k` = 2 de T5 es incluso mayor: +0,105 [+0,065; +0,142]).

### 13.2 Ablación (valid decide; test confirma)

El comparador es la predicción **guardada** del conservado (T4: `lr_agg` en `k` = 2 y `cb_agg` en `k` = 4; T5: `gru_adm` y `gru_agg`); reentrenado la reproduce con diferencia máxima de 3·10⁻⁸. Los candidatos son la misma familia con las mismas entradas más el bloque, y, para ver si la ganancia depende de la familia, también `lr_agg` y `cb_agg` (con y sin bloque). Bloques previstos: `t4` y `todo` en T4; `reg_alc` y `todo` en T5. Remuestreo de personas (1.000, los mismos para todos los modelos). La fila «(referencia)» es la familia sin variables nuevas.

### 13.3 Resultados

ΔAP es la diferencia pareada con el conservado (IC de 95 %, remuestreo por persona); «sin P58» repite la validación sin las filas con semestres sin reprobaciones registradas. La columna ¿D114? marca los candidatos cuyo IC de validación excluye el cero a favor, antes del desempate por simplicidad.
**T4 `k` = 2** (conservado: `lr_agg`; valid 4040 filas y 134 eventos, test 4688 y 141; diferencia máxima al reentrenar el conservado: 2.9e-08).

| Candidato | Bloque | AP valid | ΔAP valid (IC 95 %) | ΔAP test (IC 95 %) | ΔAP valid sin P58 | ¿D114? |
|---|---|---|---|---|---|---|
| `lr_agg` (conservado) | - | 0,113 [0,081; 0,170] | - | - | - | - |
| `lr_agg+t4` | t4 | 0,166 [0,120; 0,234] | +0,053 [+0,015; +0,093] | +0,001 [-0,017; +0,020] | +0,094 [+0,029; +0,162] | **sí** |
| `lr_agg+todo` | todo | 0,168 [0,119; 0,236] | +0,055 [+0,014; +0,093] | +0,005 [-0,013; +0,021] | +0,100 [+0,034; +0,166] | **sí** |
| `cb_agg` | - | 0,112 [0,082; 0,162] | -0,001 [-0,045; +0,037] | +0,004 [-0,034; +0,035] | -0,013 [-0,072; +0,035] | (referencia) |
| `cb_agg+t4` | t4 | 0,109 [0,080; 0,158] | -0,004 [-0,053; +0,039] | +0,029 [-0,008; +0,074] | +0,038 [-0,033; +0,109] | no |
| `cb_agg+todo` | todo | 0,124 [0,092; 0,180] | +0,011 [-0,036; +0,055] | +0,031 [-0,005; +0,070] | +0,090 [+0,014; +0,169] | no |

Decisión D114: **lr_agg+todo**.

**T4 `k` = 4** (conservado: `cb_agg`; valid 3324 filas y 80 eventos, test 3885 y 66; diferencia máxima al reentrenar el conservado: 7.1e-09).

| Candidato | Bloque | AP valid | ΔAP valid (IC 95 %) | ΔAP test (IC 95 %) | ΔAP valid sin P58 | ¿D114? |
|---|---|---|---|---|---|---|
| `cb_agg` (conservado) | - | 0,134 [0,086; 0,206] | - | - | - | - |
| `cb_agg+t4` | t4 | 0,186 [0,123; 0,294] | +0,052 [-0,001; +0,124] | +0,018 [-0,005; +0,060] | +0,102 [+0,003; +0,237] | no |
| `cb_agg+todo` | todo | 0,205 [0,138; 0,319] | +0,071 [+0,012; +0,150] | +0,005 [-0,014; +0,047] | +0,133 [+0,020; +0,268] | **sí** |
| `lr_agg` | - | 0,120 [0,084; 0,190] | -0,014 [-0,058; +0,027] | -0,010 [-0,022; +0,001] | -0,025 [-0,088; +0,038] | (referencia) |
| `lr_agg+t4` | t4 | 0,199 [0,137; 0,303] | +0,065 [+0,010; +0,140] | -0,013 [-0,030; +0,007] | +0,059 [-0,029; +0,160] | **sí** |
| `lr_agg+todo` | todo | 0,251 [0,168; 0,374] | +0,117 [+0,047; +0,219] | -0,011 [-0,031; +0,023] | +0,114 [+0,005; +0,251] | **sí** |

Decisión D114: **lr_agg+todo**.

**T5 `k` = 2** (conservado: `gru_adm`; valid 4040 filas y 399 eventos, test 4688 y 456; diferencia máxima al reentrenar el conservado: 3.0e-08).

| Candidato | Bloque | AP valid | ΔAP valid (IC 95 %) | ΔAP test (IC 95 %) | ΔAP valid sin P58 | ¿D114? |
|---|---|---|---|---|---|---|
| `gru_adm` (conservado) | - | 0,556 [0,506; 0,611] | - | - | - | - |
| `gru_adm+reg_alc` | reg_alc | 0,624 [0,577; 0,671] | +0,068 [+0,032; +0,102] | +0,038 [+0,005; +0,069] | +0,105 [+0,065; +0,142] | **sí** |
| `gru_adm+todo` | todo | 0,596 [0,548; 0,646] | +0,040 [+0,003; +0,076] | +0,027 [-0,007; +0,060] | +0,098 [+0,059; +0,136] | **sí** |
| `lr_agg` | - | 0,493 [0,444; 0,547] | -0,063 [-0,092; -0,031] | -0,062 [-0,087; -0,036] | +0,014 [-0,018; +0,048] | (referencia) |
| `lr_agg+reg_alc` | reg_alc | 0,556 [0,504; 0,607] | -0,000 [-0,038; +0,039] | -0,047 [-0,086; -0,011] | +0,085 [+0,037; +0,128] | no |
| `lr_agg+todo` | todo | 0,547 [0,496; 0,597] | -0,009 [-0,046; +0,027] | -0,046 [-0,080; -0,011] | +0,069 [+0,022; +0,112] | no |
| `cb_agg` | - | 0,518 [0,470; 0,576] | -0,038 [-0,065; -0,007] | -0,012 [-0,037; +0,012] | +0,050 [+0,012; +0,087] | (referencia) |
| `cb_agg+reg_alc` | reg_alc | 0,607 [0,558; 0,655] | +0,051 [+0,014; +0,088] | +0,016 [-0,014; +0,045] | +0,119 [+0,077; +0,160] | **sí** |
| `cb_agg+todo` | todo | 0,601 [0,552; 0,649] | +0,045 [+0,009; +0,081] | +0,019 [-0,008; +0,050] | +0,120 [+0,078; +0,158] | **sí** |

Decisión D114: **gru_adm+reg_alc**.

**T5 `k` = 4** (conservado: `gru_agg`; valid 3324 filas y 588 eventos, test 3885 y 201; diferencia máxima al reentrenar el conservado: 3.0e-08).

| Candidato | Bloque | AP valid | ΔAP valid (IC 95 %) | ΔAP test (IC 95 %) | ΔAP valid sin P58 | ¿D114? |
|---|---|---|---|---|---|---|
| `gru_agg` (conservado) | - | 0,663 [0,626; 0,699] | - | - | - | - |
| `gru_agg+reg_alc` | reg_alc | 0,792 [0,764; 0,817] | +0,129 [+0,104; +0,156] | +0,045 [-0,014; +0,097] | +0,167 [+0,129; +0,207] | **sí** |
| `gru_agg+todo` | todo | 0,788 [0,760; 0,813] | +0,125 [+0,101; +0,152] | +0,028 [-0,027; +0,083] | +0,163 [+0,124; +0,205] | **sí** |
| `lr_agg` | - | 0,631 [0,588; 0,675] | -0,031 [-0,053; -0,006] | -0,004 [-0,047; +0,035] | -0,005 [-0,040; +0,034] | (referencia) |
| `lr_agg+reg_alc` | reg_alc | 0,780 [0,750; 0,806] | +0,117 [+0,095; +0,142] | +0,031 [-0,014; +0,078] | +0,161 [+0,121; +0,200] | **sí** |
| `lr_agg+todo` | todo | 0,781 [0,752; 0,807] | +0,118 [+0,097; +0,143] | +0,032 [-0,014; +0,080] | +0,163 [+0,124; +0,202] | **sí** |
| `cb_agg` | - | 0,585 [0,542; 0,626] | -0,078 [-0,098; -0,054] | +0,002 [-0,041; +0,046] | -0,059 [-0,090; -0,024] | (referencia) |
| `cb_agg+reg_alc` | reg_alc | 0,770 [0,741; 0,798] | +0,108 [+0,084; +0,133] | +0,019 [-0,035; +0,075] | +0,140 [+0,100; +0,180] | **sí** |
| `cb_agg+todo` | todo | 0,782 [0,752; 0,807] | +0,119 [+0,096; +0,144] | +0,031 [-0,027; +0,089] | +0,157 [+0,117; +0,197] | **sí** |

Decisión D114: **gru_agg+reg_alc**.

### 13.4 Lectura y límites

- **Regla D114 aplicada, con su desempate.** La tabla marca «sí» a todo candidato cuyo ΔAP pareado de validación excluye el cero a favor. Entre los que pasan, D114 conserva el más simple (regresión logística < CatBoost < GRU, y luego el bloque más chico) salvo que otro lo supere con IC que excluye el cero (`evaluation/ablacion_variables.py`, `refinar_por_simplicidad`, y `--tarea t45-final`). Resultado: T4 `k` = 2 `lr_agg+t4`; T4 `k` = 4 `lr_agg+todo` (supera a `lr_agg+t4` por +0,052 [+0,018; +0,098]); T5 `k` = 2 `cb_agg+reg_alc`; T5 `k` = 4 `lr_agg+reg_alc`. La tabla anterior, calculada sin el desempate, muestra como mejor en validación a `gru_adm+reg_alc` y `gru_agg+reg_alc`.
- **T5: la mejora viene de las variables, no de la familia.** Con las mismas variables, la GRU no se distingue de la clasificación clásica: `gru_adm+reg_alc` frente a `cb_agg+reg_alc` en `k` = 2, +0,017 [−0,007; +0,042]; `gru_agg+reg_alc` frente a `lr_agg+reg_alc` en `k` = 4, +0,012 [−0,002; +0,027]. Por eso D114 deja el modelo simple. Sin las variables nuevas, los modelos clásicos están por debajo de la GRU conservada (−0,063 y −0,031 en validación para `lr_agg`), es decir, **la distancia al umbral de eliminación aporta justo lo que la secuencia ya aportaba a la GRU**.
- **T5 `k` = 4: la prueba no contradice pero tampoco separa del cero** (ΔAP test +0,031 [−0,014; +0,078] para `lr_agg+reg_alc`). La razón es el tamaño: 201 eventos en prueba frente a 588 en validación.
- **Calibración de los candidatos (prueba; AP / ROC-AUC / Brier / ECE).**

  | Tarea y `k` | Modelo | AP | ROC-AUC | Brier | ECE |
  |---|---|---|---|---|---|
  | T4 2 | `lr_agg` (conservado) | 0,094 | 0,732 | 0,043 | 0,074 |
  | T4 2 | `lr_agg+t4` | 0,096 | 0,739 | 0,036 | 0,039 |
  | T4 4 | `cb_agg` (conservado) | 0,059 | 0,803 | 0,017 | 0,006 |
  | T4 4 | `lr_agg+todo` | 0,047 | 0,694 | 0,019 | 0,015 |
  | T5 2 | `gru_adm` (conservado) | 0,566 | 0,908 | 0,059 | 0,011 |
  | T5 2 | `cb_agg+reg_alc` | 0,582 | 0,910 | 0,062 | 0,032 |
  | T5 2 | `gru_adm+reg_alc` | 0,604 | 0,906 | 0,065 | 0,048 |
  | T5 4 | `gru_agg` (conservado) | 0,312 | 0,877 | 0,058 | 0,091 |
  | T5 4 | `lr_agg+reg_alc` | 0,344 | 0,913 | 0,077 | 0,132 |
  | T5 4 | `gru_agg+reg_alc` | 0,357 | 0,914 | 0,100 | 0,148 |

  Los candidatos de T5 ordenan mejor (AP y ROC-AUC) pero **calibran peor** que el conservado, sobre todo en `k` = 4 (Brier de 0,058 a 0,077 y ECE de 0,091 a 0,132): el entrenamiento y la validación tienen más eliminaciones que la prueba (el reglamento nuevo y la ventana de censura reducen la tasa observada), y las distancias al umbral empujan la probabilidad hacia arriba. **Si el panel muestra probabilidades y no solo órdenes de riesgo, conviene calibrar (Platt o isotónica sobre validación) antes de publicar un candidato de T5.** En T4 `k` = 4 el candidato `lr_agg+todo` tiene menos AP y ROC-AUC en prueba que el conservado (−0,011 y −0,109): D114 lo elige en validación (80 eventos) pero la prueba no lo confirma.
- **T4 no se adopta.** Los dos candidatos pasan D114 en validación, pero la prueba no los confirma (IC que incluye el cero) y en `k` = 4 el ROC-AUC de prueba cae. La ganancia de validación es mayor sin las filas afectadas por P58 (+0,094 y +0,114), pero 134 y 80 eventos son pocos para que la regla elija con seguridad; se recomienda esperar a una cohorte más antes de cambiar el modelo conservado de T4.
- **Reglamento nuevo no observado.** Ningún evento de entrenamiento, validación o prueba ocurre bajo el Art. 46 (desde `202520`). Las distancias del reglamento nuevo se calculan pero no se pueden validar contra etiquetas; la distancia del reglamento antiguo es la que el modelo aprende. P118 advierte que la mejora puede no trasladarse a las cohortes con el reglamento nuevo.
- **Variables no incluidas.** Morosidad (P119: no se puede usar sin definir el tratamiento); el máximo de permanencia en Ciclo Básico (50-A) y la oferta histórica de asignaturas (P111) no se derivan de los datos.

### 13.5 Predicciones guardadas y reproducción

Las predicciones de los candidatos que cumplen D114 se agregan, **sin tocar los arreglos que ya existían** (la función `_publicar_t45` verifica la igualdad bit a bit y falla si difiere), a `artefactos/preds/t45_k{2,4}_{valid,test}.npz` con las claves (según `k`) `T4__lr_agg_t4`, `T4__lr_agg_todo`, `T5__cb_agg_reg_alc`, `T5__gru_adm_reg_alc` (`k` = 2) y `T4__lr_agg_todo`, `T5__lr_agg_reg_alc`, `T5__gru_agg_reg_alc` (`k` = 4) (mismo formato y mismo orden de filas que las claves del conservado). `evaluation/grupos_facultad.py`, `evaluation/vista_historica.py` (`MODELO_T5`) y el exportador leen esa ubicación, pero **ninguno cambia de modelo por sí solo**: adoptar un candidato de T5 exige cambiar `MODELO_T5` y registrar la decisión en `00_plan.md`. `resultados_t45.json` y `seleccion_valid_t45.json` no se modificaron.

```
python -m pipelines.migrate                                        # 031 (tablas laterales)
python -m pipelines.snapshots.variables_nuevas                     # hash 02fac354897ddc13512322a73adb9b4462a8e0e19d994df03d54c75a76a62ea0
python -m evaluation.ablacion_variables --tarea t45                # artefactos/ablacion_variables_t45.json
python -m evaluation.ablacion_variables --tarea t45-final          # desempate D114 y publicación (artefactos/ablacion_variables_t45_final.json)
python tools/informe_variables_nuevas.py t45                       # tablas de 13.3
```

Pruebas: `tests/unit/test_variables_nuevas.py`, `test_variables_nuevas_ddl.py` y `test_ablacion_variables.py`. Regenerar este documento con `tools/informe_t45.py --doc` **borraría** esta sección: agregarla a la plantilla antes de regenerar.

### 13.6 Calibración de los candidatos de T5 sobre validación (D120)

Antes de publicar `cb_agg+reg_alc` (`k` = 2) y `lr_agg+reg_alc` (`k` = 4) se ajustaron calibradores **solo con validación** (`evaluation/calibrar_t5_nuevas.py`; pruebas en `tests/unit/test_calibrar_t5_nuevas.py`). Se compararon Platt (logística sobre el logit del puntaje) e isotónica con un ajuste cruzado de 5 grupos por persona dentro de validación; se elige el menor Brier cruzado (el empate va a Platt) y el calibrador elegido se reajusta con toda la validación y se aplica a la prueba, que nunca interviene en el ajuste ni en la elección. Las predicciones calibradas se agregan como `T5__cb_agg_reg_alc_cal` y `T5__lr_agg_reg_alc_cal` en `artefactos/preds/t45_k{2,4}_{valid,test}.npz` (en validación, las del ajuste cruzado; los arreglos que ya existían no cambian: verificado bit a bit). Parámetros y comparación: `artefactos/calibracion_t5_nuevas.json`.

| `k` | Método elegido | Brier cruzado Platt / isotónica |
|---|---|---|
| 2 | Platt (a = 1,084; b = 0,680) | 0,0558 / 0,0566 |
| 4 | Isotónica | 0,0774 / 0,0765 |

Métricas (AP / ROC-AUC / Brier / ECE). Validación: ajuste cruzado; el conservado y el candidato sin calibrar no se ajustan sobre validación.

| `k` | Modelo | Validación | Prueba |
|---|---|---|---|
| 2 | `gru_adm` (conservado) | 0,556 / 0,901 / 0,060 / 0,022 | 0,566 / 0,908 / 0,059 / 0,011 |
| 2 | `cb_agg+reg_alc` sin calibrar | 0,607 / 0,914 / 0,058 / 0,032 | 0,582 / 0,910 / 0,062 / 0,032 |
| 2 | `cb_agg+reg_alc` calibrado | 0,603 / 0,914 / 0,056 / 0,014 | 0,582 / 0,910 / 0,074 / 0,074 |
| 4 | `gru_agg` (conservado) | 0,663 / 0,899 / 0,101 / 0,064 | 0,312 / 0,877 / 0,058 / 0,091 |
| 4 | `lr_agg+reg_alc` sin calibrar | 0,780 / 0,928 / 0,084 / 0,071 | 0,344 / 0,913 / 0,077 / 0,132 |
| 4 | `lr_agg+reg_alc` calibrado | 0,764 / 0,923 / 0,077 / 0,013 | 0,306 / 0,911 / 0,118 / 0,182 |

**Lectura.** La calibración funciona dentro de validación (el ECE baja de 0,032 a 0,014 y de 0,071 a 0,013; el Brier mejora), y el orden se conserva (en Platt el AP y el ROC-AUC no cambian; la isotónica de `k` = 4 los reduce por los empates: AP de prueba 0,344 a 0,306). **Pero en prueba la calibración empeora**: Brier 0,062 a 0,074 (`k` = 2) y 0,077 a 0,118 (`k` = 4), y el ECE 0,032 a 0,074 y 0,132 a 0,182; el modelo calibrado queda claramente peor calibrado que el conservado (ECE 0,011 y 0,091). La causa es el cambio entre validación y prueba, no el calibrador: en `k` = 2 el candidato subpredice en validación (riesgo medio 0,072 frente a 0,099 observado) y sobrepredice en prueba (0,128 frente a 0,097), de modo que el ajuste que corrige lo primero agrava lo segundo; en `k` = 4 la tasa observada cae de 0,177 (validación) a 0,052 (prueba), en parte por el subregistro de `E` desde 202420 (P75). Una calibración elegida solo con validación no puede corregir ese cambio. **Decisión (D120, 18-11-2026):** se conservan las GRU (`gru_adm` en `k` = 2 y `gru_agg` en `k` = 4). La Bóveda publica conteos agregados, que dependen de la calibración, y la ventaja de orden de los candidatos solo serviría para listas por estudiante, que esperan el Gate 4. Se reevalúa con etiquetas del reglamento 2025 y con P75 resuelta.
