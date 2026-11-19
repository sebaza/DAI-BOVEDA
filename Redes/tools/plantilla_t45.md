# DAI Neural — Benchmark T4 y T5: transición real de programa y eliminación

**Versión:** 0.2 · 13-11-2026 (reconstrucción consolidada, etapa B: variables de admisión `mm_*` + prueba, momento del traslado P71, reintegro P88, T5 con tres evaluaciones) · 0.1 · 13-11-2026 · Fase 4, benchmark T4 y T5. Base: `PROMPT_MAESTRO.md` (secciones «Predicción experimental», «Evaluación» y «Fase 4»), `00_plan.md` (D23–D63 y D81–D88), `10_benchmark_t3.md` (población y atributos) y el mart de traslados (D48–D51). Versión del código: `{{meta:version_codigo}}`; huella de los datos del snapshot: `{{meta:snapshot_hash}}`.
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, RUT ni predicción por persona figura en este documento ni en el repositorio; las predicciones viven en `artefactos/preds/` (ignorado por git). Los pronósticos por programa y facultad de §8 son **agregados** (tasa esperada de un grupo), no individuales, y se publican solo con n ≥ 100 y al menos 10 eventos.

## 1. Definición de las tareas

**T4, «transición real de programa».** Dada una trayectoria de pregrado que sigue matriculada al cierre del `k`-ésimo semestre regular, ¿pasa a otro programa de pregrado (cambio de carrera, traslado de sede u otro traslado) dentro de los dos semestres regulares siguientes? **T5, «eliminación».** ¿Recibe en esos dos semestres un estado de eliminación académica? Son dos objetivos binarios distintos, evaluados por separado, sobre **un mismo resultado mutuamente excluyente** en el horizonte (§3), de modo que los resultados competidores (egreso, otra salida, el otro evento) son explícitos y no se confunden con «continúa».

| Elemento | Definición |
|---|---|
| Unidad | Una **trayectoria de pregrado** de T3 (`id_nivel` 1; sin admisiones `IN`, `PE`, `IE`; cohortes 2015 o posteriores; sin los programas de Intercambio; Ingeniería Civil Plan Común unido a su especialidad: D47, `10_benchmark_t3.md` §2). Una persona puede tener más de una trayectoria; el bootstrap remuestrea personas. |
| Corte `k` | Fin del `k`-ésimo semestre regular desde el de admisión, `k` ∈ {2, 4}. Elegible: con estado de matrícula (matrícula, reingreso o cambio de ciclo) en el período del corte, sin estado de salida en ese período (D24, P52), sin egreso o titulación hasta el corte y con seguimiento posterior (las reglas de T3), y **sin una transición ya iniciada en el corte** (D53). |
| Horizonte | Los **dos semestres regulares siguientes** (slots `k + 1` y `k + 2`). Una fila solo se etiqueta si el período del slot `k + 2` está **cerrado** (`{{meta:cierre}}` es el último cerrado; el siguiente está en curso); si no, es `censurado` y queda fuera de los modelos. |
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

1. **Hay señal, y viene de los agregados académicos, no del perfil de ingreso.** Con el perfil de ingreso solo, ningún modelo supera de forma clara a la tasa histórica por programa en T4 (con `k` = 2, ΔAP de la logística frente a la tasa histórica: {{d:2.T4.lr_adm.baseline_tasa.ap}}) y en T5 la mejora es modesta (AP {{ic:2.T5.lr_adm.ap}} frente a {{ic:2.T5.baseline_tasa.ap}}). Al sumar los agregados del rendimiento hasta el corte, el AP sube en T4 de {{v:2.T4.cb_adm.ap}} a {{v:2.T4.cb_agg.ap}} y en T5 de {{v:2.T5.cb_adm.ap}} a {{v:2.T5.cb_agg.ap}} (CatBoost, `k` = 2); las diferencias pareadas tienen el intervalo sobre 0 (§5–§6).
2. **T5 (eliminación) es predecible; T4 (transición real) lo es poco.** Con `k` = 2, T5 alcanza AP {{ic:2.T5.cb_agg.ap}} y ROC-AUC {{v:2.T5.cb_agg.roc_auc}} (tasa de base en test: {{tasa:2.test.eliminacion}}); T4 llega a AP {{ic:2.T4.lr_agg.ap}} con una tasa de base de {{tasa:2.test.transicion}}: ordena razonablemente (ROC-AUC {{v:2.T4.lr_agg.roc_auc}}), pero acierta pocos casos en el extremo alto del riesgo. Con `k` = 4 las dos son más difíciles (T4: AP {{v:4.T4.cb_agg.ap}}; T5: AP {{v:4.T5.lr_agg.ap}}).
3. **Las redes no superan a los clásicos en ninguna tarea ni corte.** Con las variables de admisión corregidas, la GRU solo con la secuencia deja de superar a CatBoost en T5 con `k` = 2 (ΔAP {{d:2.T5.gru_adm.cb_agg.ap}}: el intervalo incluye 0), de modo que la conclusión anterior (una red conservada por un margen estrecho) **cambia** y se conserva el clásico en las seis combinaciones de tarea y corte (§4). La logística entrena en un par de segundos y CatBoost en decenas; la GRU tarda de 3 a 6 segundos por tarea con tres semillas en GPU.
4. **Calibración y deriva.** En T5 con `k` = 2 el modelo conservado queda bien calibrado (ECE {{v:2.T5.cb_agg.ece}}). Con `k` = 4 el riesgo medio predicho supera a la tasa observada del test, porque la tasa de eliminación de las cohortes 2022–2023 cae respecto de la de entrenamiento. Parte de esa caída es un **subregistro del estado `E` desde 202420** (P75, §3): el número de estados `E` baja a una cuarta parte o menos de lo habitual mientras los traslados se mantienen. Con los períodos de registro completo (evaluación (c) de «Cambios de la reconstrucción consolidada»), T5 con `k` = 2 sube a AP {{sens:2.ap}} (§3); la eliminación efectiva (sin reintegro) tiene una tasa menor y un AP menor, y las conclusiones sobre qué modelo se conserva no cambian.
5. **Programas y facultades.** Solo una minoría de los grupos es reportable (n ≥ 100 y ≥ 10 eventos): con `k` = 2, {{x:por_k.2.targets.T4.grupos.programa.resumen.grupos_reportables}} de {{x:por_k.2.targets.T4.grupos.programa.resumen.grupos_total}} programas en T4 y {{x:por_k.2.targets.T5.grupos.programa.resumen.grupos_reportables}} de {{x:por_k.2.targets.T5.grupos.programa.resumen.grupos_total}} en T5. En T5 el modelo ordena los grupos (ρ de Spearman entre 0,7 y 0,8) y se equivoca menos que la tasa histórica; **en T4 el pronóstico agregado no mejora la tasa histórica y, con `k` = 2, está mal calibrado**: el modelo conservado (logística) sobreestima la tasa de transición en unos siete puntos (riesgo medio de 0,10 frente a una tasa observada de 0,03), de modo que su error agregado por programa y facultad es mucho mayor que el de la tasa histórica (§8). El conservado de T4 con `k` = 2 cambió de CatBoost a la logística por una diferencia de AP de 0,001 en valid entre dos clásicos que no se distinguen; la regla del benchmark es mecánica y se informa tal cual.
6. **Equidad.** La diferencia entre mujeres y hombres en la brecha de calibración es de a lo más 0,01 en las cuatro combinaciones de tarea y corte (descriptivo); el nivel absoluto de la brecha de T5 con `k` = 4 se debe a la deriva, no al sexo. Las diferencias de AP y de Recall@10 % descansan en pocos eventos y no son concluyentes (§9).
7. **Modelos conservados.** T4: logística con ingreso + agregados en `k` = 2 (antes CatBoost) y CatBoost con ingreso + agregados en `k` = 4. T5: CatBoost con ingreso + agregados en `k` = 2 (antes la GRU) y logística con ingreso + agregados en `k` = 4. **Ningún modelo está aprobado para uso individual** (Gate 4, §11).

## Cambios de la reconstrucción consolidada (13-11-2026)

Esta versión repite el benchmark con los datos corregidos de la etapa A y con cuatro cambios del lado del modelo.

1. **Variables de admisión (`mm_*` + prueba).** Los percentiles `pct_*` (rangos sobre valores en escalas mezcladas) se reemplazan por los puntajes normalizados `mm_*` (mínimo–máximo por prueba, año y campo) más la variable categórica `prueba_admision` (PSU hasta 2020, PDT 2021–2022, PAES desde 2023: P87). Vale para todas las tareas y los tres modelos.
2. **Momento del traslado (P71).** T4 fecha el evento en la salida del origen (último período del origen). Recuentos de eventos y de resultados por partición, antes y después:

{{tabla:etiquetas_p71}}

3. **Reintegro (P88).** El reintegro es solo el estado `I` (`Y` es una rectificación, no un reintegro). La eliminación con reintegro y la eliminación efectiva se recalcularon con esa regla y el snapshot se reconstruyó.
4. **T5 en tres evaluaciones.** Se mantiene la regla de selección (mejor clásico en valid; una red solo si gana en valid y el ΔAP pareado queda sobre 0): el modelo conservado es el de la etiqueta actual y las tres evaluaciones lo miden con (a) la etiqueta actual, (b) la eliminación efectiva (sin reintegro) y (c) la etiqueta actual sin las filas de horizonte dudoso (`horizonte_e_dudoso`, horizonte desde 202420: P75). Con `k` = 4 todas las filas de test tienen horizonte dudoso y (c) no es evaluable. En `k` = 4 el ΔAP pareado frente a la tasa histórica del modelo conservado (logística) no se guardó en el bootstrap y se muestra solo el punto; el AP del modelo y el de la tasa histórica llevan su intervalo.

{{tabla:tres_evaluaciones}}

   Lectura: la eliminación efectiva es menos frecuente y su AP absoluto es menor, pero el modelo mantiene una ventaja clara sobre la tasa histórica y el mismo modelo conservado; sin los horizontes dudosos (solo `k` = 2) el AP sube y la tasa observada también (el subregistro de `E` baja la tasa de las filas dudosas). **Las conclusiones de selección no cambian entre las tres evaluaciones.**

**Antes y después (modelo conservado, test).** Las diferencias de AP entre la versión anterior y esta están dentro de los intervalos; lo que sí cambia es el modelo conservado en T4 con `k` = 2 y en T5 con `k` = 2:

{{tabla:cambios}}

## 2. Población y embudo

Un mismo snapshot (`neural_mart.snapshot_t45`, una fila por trayectoria y corte) sirve a las dos tareas. El embudo parte de la población de T3 y agrega un único filtro propio, la transición ya iniciada al corte (D53). Las cifras son recuentos de trayectorias (no de personas).

{{tabla:embudo}}

Las filas con eliminación y transición en el horizonte son pocas: el resultado único evita contarlas dos veces y las banderas del snapshot conservan ambos hechos. Los traslados cuyo destino empieza después del horizonte (P71) no son eventos de esa fila; una parte mínima de ellos queda como «otra salida» y se informa en la última línea del embudo.

## 3. Resultados mutuamente excluyentes

{{tabla:resultados}}

Con `k` = 2 la tasa de eliminación en test es {{tasa:2.test.eliminacion}} y la de transición {{tasa:2.test.transicion}}. Los egresos dentro del horizonte son excepcionales con `k` = 2 y poco frecuentes con `k` = 4; no tienen un modelo propio y solo aparecen como clase en la vista multiclase (§7). Con `k` = 4 el control posterior (2024 en adelante) no tiene ninguna fila con el horizonte cerrado.

### Otra salida

«Otra salida» agrupa a quien no tiene un evento de T4 ni T5 y no está matriculado en el período del horizonte: un estado de salida distinto de `E` (renuncias, no continuidad, sanciones), una interrupción o una ausencia sin estado.

{{tabla:otra_salida}}

### Qué contiene el estado `E` (P70)

El diccionario no documenta los códigos de causal. La distribución del código en las filas de eliminación es muy concentrada, y los dos primeros códigos reúnen más del 80 %:

{{tabla:causales}}

Que `E` sea una eliminación académica se apoya en el comportamiento de los datos (los eliminados aprueban una fracción mucho menor de sus asignaturas que quienes continúan), no en una definición oficial. Hasta que se confirme, T5 se lee como «estado E registrado» (§11).

### Subregistro del estado `E` desde 202420 (P75)

Los estados `E` por período muestran una caída marcada desde 202420, mientras las matrículas y los traslados siguen su nivel. Los períodos 202010 y 202020 también son bajos (docencia remota); los de 202420 en adelante no tienen una explicación conocida.

{{tabla:registro_e}}

Consecuencia para el benchmark: la tasa de eliminación del test (cohortes 2022–2023) mezcla períodos de registro completo con períodos de subregistro. Con `k` = 4 el horizonte de todas las filas de test termina en 202420 o después. Como análisis de sensibilidad, se evalúa T5 en las filas de test cuyo horizonte termina en 202410 o antes (solo cohorte 2022 con `k` = 2; con `k` = 4 no queda ninguna fila). Las etiquetas no se modifican.

{{tabla:sensibilidad_e}}

## 4. Modelos y protocolo

**Misma población, mismas particiones, mismos atributos.** Todas las comparaciones usan las mismas filas. La escalera de ablación es la de T3:

| Paso | Modelo | Entrada |
|---|---|---|
| 0 | Tasa histórica por programa | solo el programa vigente al corte (calculada en train) |
| 1 | Logística y CatBoost | perfil de ingreso (`adm`) |
| 2 | Logística y CatBoost | perfil + agregados académicos robustos a P58 (`adm+agg`) |
| 3 | GRU (3 semillas, GPU) | perfil + secuencia de los semestres `1..k` (`adm`), y con agregados (`adm+agg`) |

Los hiperparámetros se eligen con valid (regularización de la logística, iteraciones de CatBoost con parada temprana, época de la GRU); las semillas de la GRU se promedian. **Regla de conservación:** se conserva el mejor clásico por AP en valid; una red lo reemplaza solo si su AP en valid es mayor **y** el intervalo pareado de ΔAP en test queda sobre 0. Si las redes no ganan, se conserva el modelo clásico y se dice (§5–§6). La métrica principal es el AP (los eventos son raros); se informan además ROC-AUC, Brier y ECE, cada una con intervalo de confianza del 95 % por bootstrap agrupado por persona (`{{meta:boot}}` remuestreos, los mismos para todos los modelos), y las diferencias entre pasos son **pareadas** sobre los mismos remuestreos.

**Selección de modelos (valid):**

{{tabla:seleccion}}

**Sin fuga.** Los atributos usan solo información disponible al corte. Las pruebas de perturbación del repositorio alteran los datos posteriores al corte y verifican que ningún atributo cambia; la vinculación del Plan Común con su especialidad (D47) es propiedad de la unidad, no del atributo (§11).

## 5. T4: transición real de programa

### Corte `k` = 2

**Test (cohortes 2022–2023, intervalos al 95 %):**

{{tabla:test.T4.2}}

**Valid (sin intervalos):**

{{tabla:valid.T4.2}}

**Diferencias pareadas en test:**

{{tabla:deltas.T4.2}}

Lectura. El perfil de ingreso solo no supera a la tasa histórica por programa; los agregados académicos suben el AP de {{v:2.T4.lr_adm.ap}} a {{v:2.T4.lr_agg.ap}} en la logística y de {{v:2.T4.cb_adm.ap}} a {{v:2.T4.cb_agg.ap}} en CatBoost. La GRU con agregados queda en {{ic:2.T4.gru_agg.ap}}, sin diferencia pareada con CatBoost ({{d:2.T4.gru_agg.cb_agg.ap}}): **la red no suma señal sobre los agregados**. La GRU solo con la secuencia ({{v:2.T4.gru_adm.ap}}) equipara a los clásicos con agregados, es decir, la secuencia reconstruye lo que los agregados resumen. Se conserva la logística con ingreso + agregados (el mejor clásico en valid; la red no la supera). **Advertencia de calibración:** esta logística sobreestima el riesgo (ECE de la tabla siguiente) y CatBoost con agregados, que en test tiene un AP equivalente (ΔAP pareado entre ambos {{d:2.T4.cb_agg.lr_agg.ap}}), no se conserva solo porque su AP en valid fue 0,001 menor.

**Calibración del modelo conservado en test (deciles de riesgo):**

{{tabla:calibracion.T4.2}}

### Corte `k` = 4

**Test:**

{{tabla:test.T4.4}}

**Diferencias pareadas en test:**

{{tabla:deltas.T4.4}}

Lectura. Con menos eventos ({{n:descriptivo.cuentas.4.test.transicion}} en test) los intervalos son anchos. Los agregados mejoran al perfil de ingreso (CatBoost: {{d:4.T4.cb_agg.cb_adm.ap}}) y el conservado (CatBoost con agregados) mejora a la tasa histórica en {{d:4.T4.cb_agg.baseline_tasa.ap}}; el perfil solo y las redes no se distinguen de la tasa histórica ni del clásico. La GRU no mejora al clásico.

## 6. T5: eliminación

### Corte `k` = 2

**Test:**

{{tabla:test.T5.2}}

**Valid:**

{{tabla:valid.T5.2}}

**Diferencias pareadas en test:**

{{tabla:deltas.T5.2}}

Lectura. La señal viene de los agregados académicos: el AP pasa de {{v:2.T5.lr_adm.ap}} (solo ingreso) a {{v:2.T5.lr_agg.ap}} con agregados en la logística y a {{v:2.T5.cb_agg.ap}} en CatBoost. **Ninguna red supera al clásico:** la GRU solo con la secuencia llega a AP {{v:2.T5.gru_adm.ap}}, pero su ΔAP pareado frente a CatBoost con ingreso + agregados es {{d:2.T5.gru_adm.cb_agg.ap}} (el intervalo incluye 0; antes excluía 0 por poco y se había conservado la red). Se conserva CatBoost con ingreso + agregados. La GRU con agregados no mejora a la GRU sin ellos.

**Calibración del modelo conservado en test:**

{{tabla:calibracion.T5.2}}

### Corte `k` = 4

**Test:**

{{tabla:test.T5.4}}

**Diferencias pareadas en test:**

{{tabla:deltas.T5.4}}

Lectura. Los agregados siguen siendo la fuente de la señal (ΔAP de CatBoost con agregados frente al de solo ingreso: {{d:4.T5.cb_agg.cb_adm.ap}}). **Ninguna red supera al clásico**; se conserva la logística con ingreso + agregados. El ECE es alto en todos los modelos (de 0,06 a 0,08): el riesgo predicho es mayor que la tasa observada de test, consecuencia de la deriva y del subregistro de `E` (§3), no de un defecto del ordenamiento (el ROC-AUC de los modelos con agregados se mantiene en torno a 0,89).

**Calibración del modelo conservado en test:**

{{tabla:calibracion.T5.4}}

## 7. Vista multiclase

El mismo snapshot permite predecir el resultado completo (continúa, egreso, transición, eliminación, otra salida). Se comparan las frecuencias de resultado por programa (referencia), una logística multinomial y CatBoost multiclase, ambos con ingreso + agregados. El AP por clase se muestra solo para las clases con al menos 10 eventos en test. Es una vista complementaria: T4 y T5 se evalúan como binarias en §5–§6.

### Corte `k` = 2

{{tabla:multiclase.2}}

{{tabla:multiclase_deltas.2}}

### Corte `k` = 4

{{tabla:multiclase.4}}

{{tabla:multiclase_deltas.4}}

Lectura. Los dos modelos reducen el log-loss respecto de la referencia con intervalos claramente bajo 0; CatBoost mejora algo a la logística. La clase que más gana es la eliminación; la transición mejora poco ({{mc:2.mc_cb_agg.ap_transicion}} en `k` = 2 frente a {{mc:2.mc_base.ap_transicion}} de la referencia). Con `k` = 4 los egresos tempranos también se ordenan bien ({{mc:4.mc_cb_agg.ap_egreso}}).

## 8. Resultados por programa y facultad

Todo lo de esta sección son **agregados**. Un grupo se reporta solo con n ≥ 100 filas y al menos 10 eventos en test; los demás se suprimen. Para cada grupo se muestran la tasa observada, el riesgo medio predicho y su brecha, con intervalos del 95 % por bootstrap agrupado por persona, y la brecha de la tasa histórica por programa (la referencia que el modelo debe superar). Los resúmenes comparan el error absoluto medio ponderado por tamaño del grupo entre el modelo y la tasa histórica, y la correlación de Spearman entre el riesgo predicho y la tasa observada. Como T4 tiene pocos eventos, se agrega una tabla de **valid + test** con los mismos umbrales, que reporta más grupos.

### Cuántos grupos son reportables

**Solo test:**

{{tabla:grupos_resumen}}

**Valid + test:**

{{tabla:grupos_resumen_vt}}

### T4, corte `k` = 2

Programas reportables en test:

{{tabla:g.T4.2.programa}}

Facultades reportables en test:

{{tabla:g.T4.2.facultad}}

Con valid + test (más grupos):

{{tabla:gvt.T4.2.programa}}

{{tabla:ranking.gvt.T4.2.programa}}

{{tabla:gvt.T4.2.facultad}}

Lectura. El modelo ordena los grupos (ρ de Spearman 0,8 en valid + test) pero **subestima sistemáticamente a los programas de mayor tasa** (las brechas pred. − obs. son negativas en todos los grupos con tasa alta) y su error ponderado es mayor que el de la tasa histórica por programa: el pronóstico agregado de T4 por programa **no mejora** al promedio histórico. A nivel de facultad la diferencia con la tasa histórica no es distinguible de 0.

### T4, corte `k` = 4

{{tabla:g.T4.4.programa}}

{{tabla:g.T4.4.facultad}}

Solo un programa y una facultad cumplen los umbrales en test; con valid + test:

{{tabla:gvt.T4.4.facultad}}

### T5, corte `k` = 2

{{tabla:g.T5.2.programa}}

{{tabla:ranking.g.T5.2.programa}}

{{tabla:g.T5.2.facultad}}

{{tabla:ranking.g.T5.2.facultad}}

Lectura. Aquí el pronóstico agregado sí agrega valor: con {{x:por_k.2.targets.T5.grupos.programa.resumen.grupos_reportables}} programas y {{x:por_k.2.targets.T5.grupos.facultad.resumen.grupos_reportables}} facultades reportables, el error ponderado del modelo es menor que el de la tasa histórica y el orden predicho acompaña al observado (ρ ≈ 0,7). La coincidencia entre los grupos de mayor tasa observada y los de mayor riesgo es parcial.

### T5, corte `k` = 4

{{tabla:g.T5.4.programa}}

{{tabla:g.T5.4.facultad}}

Con valid + test:

{{tabla:gvt.T5.4.programa}}

Lectura. Las brechas son positivas en casi todos los grupos: el modelo sobrestima la eliminación de las cohortes 2022–2023 (deriva y subregistro de `E`, §3). En test el error ponderado por programa es mayor que el de la tasa histórica; en valid + test es menor. Es un resultado que depende de qué cohortes se miren, no una propiedad estable del modelo.

## 9. Equidad por sexo (descriptivo)

`sexo` no es variable de ningún modelo; se usa solo para comparar el desempeño. No se aplica ninguna corrección y no se interpretan causas. Los grupos pequeños se muestran con su `n`.

### T4

`k` = 2:

{{tabla:sexo.T4.2}}

`k` = 4:

{{tabla:sexo.T4.4}}

### T5

`k` = 2:

{{tabla:sexo.T5.2}}

`k` = 4:

{{tabla:sexo.T5.4}}

Lectura. Las tasas observadas difieren entre mujeres y hombres (en T5 la de las mujeres es menor) y el riesgo predicho acompaña esa diferencia: la brecha de calibración difiere entre sexos en no más de 0,01. El AP y el Recall@10 % varían entre sexos, pero se calculan sobre pocos eventos en T4 y sin intervalo, de modo que no se interpretan como diferencia de desempeño.

### Deriva por cohorte y Plan Común

{{tabla:cohorte.T5.2}}

La tasa observada de eliminación cae de la cohorte 2022 a la 2023 mientras el riesgo medio predicho se mantiene: es la señal de la deriva descrita en §3. En T4 la diferencia entre cohortes es menos marcada:

{{tabla:cohorte.T4.2}}

## 10. Costo computacional

Ejecución completa (snapshot ya construido): {{meta:minutos}} minutos, RAM máxima {{meta:ram}} MB, GPU {{meta:gpu}} (memoria máxima de la GRU menor a 0,1 GB). Segundos por modelo (tres semillas de GRU, tres particiones de CatBoost):

{{tabla:tiempos}}

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
