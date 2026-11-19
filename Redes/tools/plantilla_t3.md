# DAI Neural — Benchmark T3: tiempo hasta titulación

**Versión:** 0.4 · 16-11-2026 (beneficios estudiantiles, §11: sin cambios en el modelo oficial) · 0.3 · 13-11-2026 (reconstrucción consolidada, etapa B: variables de admisión `mm_*` + prueba) · 0.2 · 12-11-2026 · Fase 4, benchmark T3, **con la población de D47** (Programa de Intercambio fuera; Ingeniería Civil Plan Común unido a su especialidad). Reemplaza a la v0.1 (D45), que usaba la población de D40; las cifras de D45 ya no rigen. Base: `PROMPT_MAESTRO.md` (Predicción experimental, Evaluación, Fase 4; no negociable 5), `03_reglas_academicas.md`, `05_modelo_datos.md`, `08_benchmark_t1.md` y `09_benchmark_t2.md` (misma estructura, estándar y herramientas).
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, RUT ni predicción por persona figura en este documento ni en el repositorio. Los grupos con menos de 10 episodios no se publican.

## Cambios de la reconstrucción consolidada (13-11-2026)

Cambio del lado del modelo: el perfil de ingreso usa los puntajes normalizados `mm_*` y la variable `prueba_admision` en lugar de los percentiles `pct_*` (P87). La población y el evento no cambian. Antes y después (test, IC 95 %):

{{tabla:cambios}}

**La conclusión sobre el modelo conservado de clase clásica no cambia** (CatBoost persona-período es el mejor clásico en valid en ambos cortes). **Cambia la lectura de la GRU en `k = 4`:** la ventaja de la GRU sobre el Cox con agregados en C(12) pasa de +0,003 [−0,001; +0,007] a +0,010 [+0,005; +0,014] y sobre CatBoost de +0,000 [−0,005; +0,005] a +0,006 [+0,001; +0,010], con peor IBS que CatBoost en ambas versiones; en `k = 2` la ventaja de la GRU se mantiene y aumenta algo (frente al Cox, +0,015 → +0,020; frente a CatBoost, +0,035 → +0,039).

## Resumen

1. **Tratar la salida como evento competitivo importa mucho.** A 12 semestres de la admisión la incidencia de egreso en test es {{pct:descriptivo.incidencia_comparada.test.F1.4}} con Aalen–Johansen y {{pct:descriptivo.incidencia_comparada.test.ingenua.4}} con 1 − Kaplan–Meier (que trata la salida como censura): el método ingenuo sobrestima en 25,9 puntos porcentuales (§2). Todo el benchmark usa causas competitivas.
2. **Al ingreso (k = 0) casi todo el valor está en el programa y el perfil, y las redes no aportan.** Aalen–Johansen por programa llega a C(12) = {{v:0.test.km_programa.c_12}} en test; Cox, logística, CatBoost y MLP quedan entre {{v:0.test.dt_cb_adm.c_12}} y {{v:0.test.nn_mlp_adm.c_12}}, con diferencias pareadas entre ellos cuyos intervalos incluyen el 0 (por ejemplo MLP − logística: {{d:0.test.nn_mlp_adm.dt_lr_adm.c_12}}). El MLP mejora algo el IBS ({{v:0.test.nn_mlp_adm.ibs}} frente a {{v:0.test.dt_lr_adm.ibs}} de la logística; diferencia {{d:0.test.nn_mlp_adm.dt_lr_adm.ibs}}, IC95 % excluye el 0), una ganancia pequeña de calibración y no de discriminación.
3. **Con los agregados académicos al corte (k = 2 y 4) la discriminación sube de {{v:2.test.cox_adm.c_12}} a {{v:2.test.cox_agg.c_12}}–{{v:4.test.dt_lr_agg.c_12}}**; es la ganancia dominante de todo el estudio (k = 2: {{d:2.test.cox_agg.cox_adm.c_12}} en el Cox; k = 4: de {{v:4.test.cox_adm.c_12}} a {{v:4.test.cox_agg.c_12}}). Ninguna arquitectura se acerca a ese salto.
4. **¿Las redes agregan señal?** Solo parcialmente y solo en `k = 2`. La **GRU** (3 semillas) tiene el mejor C(12) e IBS del corte ({{ic:2.test.nn_gru.c_12}}; {{ic:2.test.nn_gru.ibs}}) y supera en test al Cox de ingreso + agregados: ΔC(12) = {{d:2.test.nn_gru.cox_agg.c_12}} y ΔIBS = {{d:2.test.nn_gru.cox_agg.ibs}}; frente a CatBoost, {{d:2.test.nn_gru.dt_cb_agg.c_12}}. La logística con agregados supera al Cox por solo {{d:2.test.dt_lr_agg.cox_agg.c_12}} en C(12), de modo que la GRU gana alrededor de 0,016 a una logística (la comparación directa no está tabulada). En **k = 4 la ventaja es marginal** (cambia respecto de la versión 0.2, donde era nula): la GRU supera al Cox de ingreso + agregados en C(12) ({{d:4.test.nn_gru.cox_agg.c_12}}, el intervalo ya no incluye el 0) y apenas a CatBoost ({{d:4.test.nn_gru.dt_cb_agg.c_12}}, el intervalo apenas excluye el 0), pero con **peor IBS que CatBoost** ({{d:4.test.nn_gru.dt_cb_agg.ibs}}); su C(12) es {{v:4.test.nn_gru.c_12}} frente a {{v:4.test.dt_lr_agg.c_12}} de la logística. Una mejora de 0,005 en C(12) con peor calibración no justifica sustituir al clásico.
5. **Recomendación.** Para `k = 0` y `k = 4`, mantener el modelo clásico más simple (logística persona-período o Cox causa-específico; CatBoost si interesa la calibración en k = 4). Para `k = 2`, la GRU es la mejor opción técnica, con una ganancia modesta (≈ 0,016–0,020 en C(12) sobre la logística y el Cox) que justifica evaluarla pero no sustituye a un clásico sin revisión institucional. El control posterior (2021 en adelante) es inestable para CatBoost y MLP de solo ingreso (§7.4): no aprobar nada con ese comportamiento.
6. **Deriva entre cohortes.** La mediana del tiempo al egreso baja de 13 semestres (cohortes 2015–2017) a 11 (2018 en adelante), y la incidencia acumulada de egreso a 12 semestres desde la admisión sube de {{pct:descriptivo.incidencia_comparada.train.F1.4}} en train a {{pct:descriptivo.incidencia_comparada.valid.F1.4}} en valid y {{pct:descriptivo.incidencia_comparada.test.F1.4}} en test. Con la cohorte como variable (primera versión) los modelos fallaban fuera de tiempo; por eso el año de admisión **no** es variable de los modelos. Los modelos solo de ingreso subestiman el egreso en test (predicen {{pct:por_k.0.incidencia_media_test.12.cox_adm}}–{{pct:por_k.4.incidencia_media_test.12.dt_cb_adm}} a 12 semestres frente al {{pct:por_k.0.incidencia_media_test.12.observada}}–{{pct:por_k.4.incidencia_media_test.12.observada}} observado); los que usan agregados quedan mucho mejor calibrados (§7.3).
7. **Equidad.** Ninguna brecha de discriminación entre mujeres y hombres supera 0,029 de AUC en valor absoluto (con agregados el AUC es algo mayor en hombres: −0,02 a −0,03 en k = 2 y ≤ 0,01 en k = 4); las mujeres egresan más que los hombres ({{pct:por_k.2.subgrupos_test.nn_gru.sexo.0.incidencia_observada}} frente a {{pct:por_k.2.subgrupos_test.nn_gru.sexo.1.incidencia_observada}} a 12 semestres en k = 2) y los modelos solo de ingreso subestiman a ambos (§7.5).
8. **Costo.** Todo el benchmark corre en {{meta:segundos}} s (RAM pico {{meta:ram}} MB); las redes entrenan en 6–15 s por corte (las 3 semillas juntas) en una GPU con pico de 53 MB; CatBoost tarda entre 134 y 192 s (§7.6).
9. **Población (D47).** El Programa de Intercambio (que no puede egresar) quedó fuera y el Plan Común de Ingeniería Civil se unió a su especialidad ({{x:embudo.embudo_k0_plan_comun_unidos}} de {{x:embudo.embudo_k0_plan_comun_episodios}} trayectorias; §2). El cambio de población mueve poco las métricas globales (las diferencias con la versión anterior son de milésimas y están dentro de los intervalos; D47 en `00_plan.md` las lista) y no cambia las conclusiones. Siguen sin ser un problema del modelo la «salida por ausencia», que en al menos un 98 % es un cambio a otro programa sin estado de salida (§2, §8), y las trayectorias de Plan Común sin continuación, que por construcción nunca egresan.

## 1. Definición de la tarea

**T3, «tiempo hasta titulación».** Dado un episodio de pregrado que sigue en riesgo al cierre del `k`-ésimo semestre regular, ¿cuánto falta hasta su egreso/titulación y con qué probabilidad ocurre antes de un horizonte dado? Es un problema de **supervivencia con censura administrativa y un evento competitivo** (la salida definitiva del programa). La pregunta de investigación: (i) qué tan bien se puede anticipar el egreso con lo conocido al corte, (ii) cuánto cambia la estimación cuando se trata la salida como evento competitivo y no como censura, y (iii) si una red neuronal (MLP o GRU sobre la secuencia de semestres) mejora a los modelos clásicos de supervivencia.

| Elemento | Definición |
|---|---|
| Unidad | Una **trayectoria de pregrado** (`id_nivel` 1; sin admisiones `IN`, `PE`, `IE`, misma población que T1, D23) de una cohorte 2015 o posterior (P49/P50), con dos cambios de D47 (P62): (i) **sin los programas de Intercambio** (códigos 0003 y 0006: estudiantes de universidades extranjeras en estadías cortas, que no pueden egresar por naturaleza); (ii) un episodio de **Ingeniería Civil Plan Común** se une, como una sola trayectoria, con el primer episodio posterior de la misma persona en una especialidad de Ingeniería Civil que comience a lo más 2 períodos regulares después del último período del Plan Común; la unidad es la admisión al Plan Común y el episodio de la especialidad no se cuenta aparte (§2). |
| Corte `k` | Fin del `k`-ésimo semestre regular desde el de admisión, `k` ∈ {2, 4}; **`k = 0`** es «al ingreso» y solo usa información de admisión (variante «postulante», comparable con la ficha del postulante). Elegible: con estado de matrícula (matrícula, reingreso o cambio de ciclo) en el período del corte (para `k = 0`, en el semestre de admisión), sin estado de salida en el período del corte (D24/D32) y no egresado ni titulado hasta el corte. |
| Escala de tiempo | **Semestres regulares desde la admisión**: el *slot* `j` de `rules.slot_de_periodo` (1 = semestre de admisión). El tiempo desde el corte es `j − k`; los modelos trabajan en esa escala y los informes en la absoluta. |
| Evento de interés (causa 1) | **Primer egreso/titulación del episodio** (en una trayectoria unida, el de la especialidad): un estado de clase `egreso_titulacion` (`G` Egresado, `Z` Malla completa, `K` Expediente de título, `L` Licenciado, `U` Titulado) o una fila de `titulacion` vinculada al episodio, lo que ocurra primero. En la práctica casi siempre es `Z` (malla completa). La titulación propiamente tal (`U` o fila de `titulacion`) se guarda aparte como punto final de sensibilidad (`tiempo_titulacion`). |
| Evento competitivo (causa 2) | **Salida definitiva del episodio**: (a) *explícita*: un estado de clase `salida` que **no** es seguido por ningún estado de matrícula del episodio (una salida revertida por un reintegro no es salida), o (b) *por ausencia sostenida*: sin ningún estado de matrícula ni de interrupción en los dos últimos períodos regulares cerrados y sin egreso en ninguna fecha (el tiempo es el semestre siguiente a la última actividad). Las **interrupciones no son salidas**. Si el episodio egresa dentro del seguimiento, el egreso prevalece sobre una salida anterior (graduarse es un hecho verificado). |
| Censura | **Administrativa** (en una trayectoria unida, desde la especialidad): el seguimiento llega al último período regular **cerrado** (`{{meta:cierre}}`; `202620` está en curso y no se usa) y a lo sumo al semestre 20; un evento posterior se censura en ese límite. La censura depende solo del semestre de admisión, no del desenlace. |
| Particiones | **Por cohorte de admisión** (fuera de tiempo): train 2015-2017, valid 2018, test 2019-2020 y 2021 en adelante como control posterior (solo horizontes cortos). El seguimiento máximo es 23, 21, 19 semestres (train), 17 (valid), 15 y 13 (test): por eso las métricas se evalúan a horizontes fijos con el número de elegibles de cada uno (§2). |
| Horizontes | **10, 12 y 14 semestres desde la admisión** (5, 6 y 7 años): la duración nominal modal (10 semestres), +2 y +4. En test, 14 solo es observable para la cohorte 2019 (seguimiento 15); la cohorte 2020 (seguimiento 13) entra hasta 12. El control posterior usa 8 y 10. |

### Variables (resumen; lista completa en `pipelines/snapshots/features_t3.py` y `models/t3_data.py`)

| Bloque | Variables |
|---|---|
| Ingreso (todas las `k`) | percentiles de puntajes dentro del año (leng, mat, ciencias, historia, NEM, ranking, notas EM, ponderado) con indicadores de faltante; preferencia; vía de ingreso, código de admisión, sede, tipo y dependencia del colegio, región; cohorte; programa; **duración nominal del programa** (de `programa_catalogo`, o el semestre máximo de la malla del catálogo inicial) y créditos totales de la malla; **`trayectoria_plan_comun`** (ingresó a Plan Común; dato de admisión, no dice si habrá especialidad) |
| Programa vigente al corte (D47) | `cod_programa`, duración nominal, créditos totales de la malla, malla conocida y créditos esperados son los del **programa vigente al corte**: Plan Común hasta que se registra el primer estado de la especialidad (nunca en `k` = 0), la especialidad después, con sus semestres contados desde su propia admisión; **`especialidad_conocida_al_corte`** (hay un estado de la especialidad hasta el corte). La duración nominal de una trayectoria de Plan Común antes de conocer la especialidad es la duración del Plan Común más una constante aprendida **solo con las cohortes de train** (§4) |
| Agregados al corte (`k` = 2, 4) | créditos aprobados (primera aprobación de cada curso, convalidaciones incluidas), tasa de aprobación y promedio **sobre los semestres con fallos registrados**, convalidaciones, cursos de verano/invierno, interrupciones, cambios de catálogo, semestres matriculados, créditos esperados por la malla hasta `k`, avance respecto de lo esperado y fracción de la malla completada |
| Secuencia (GRU) | por semestre `1..k`: matrícula, interrupción, créditos aprobados y acumulados, convalidaciones, cursos de verano/invierno |
| Nunca variable | `sexo` (solo `sexo_equidad` para la evaluación de equidad, M1), el tiempo y la causa |

### Decisiones conservadoras de la definición

1. **Períodos 201920 y 202010 (P58).** No se registraron reprobaciones. Sus intentos cuentan para los créditos aprobados pero no como intentos evaluados. Una primera versión con todos los agregados colapsó en la cohorte 2019 (el último semestre del corte quedaba «sin intentos» y los modelos de árboles predecían un egreso 9 veces menor que el observado); por eso los modelos solo usan agregados que P58 no altera (§8): créditos, tasas y promedios calculados sobre los semestres con fallos registrados, matrícula y avance de malla. Los **conteos de intentos** y las tres variables del último semestre quedan en el snapshot pero fuera de los modelos, y la secuencia del GRU solo lleva canales intactos (matrícula, interrupción, créditos, convalidaciones).
2. **Egreso prevalece sobre salida anterior.** Ninguna salida definitiva precede a un egreso en las cohortes 2015 o posteriores (§3); la regla solo fija el comportamiento si ocurriera.
3. **Salida por ausencia.** Los episodios sin estado de salida que dejan de matricularse son, en su gran mayoría, personas que siguen matriculadas en **otro programa** de la UCN (§2): una transferencia sin estado de salida. Se tratan como salida del episodio porque el egreso **de este programa** ya no es posible; no se interpretan como deserción de la universidad.
4. **Censura al último período cerrado.** Un egreso registrado en `202620` (en curso) se censura en `202610`.
5. **Ventana de 20 semestres.** Los eventos posteriores se censuran en el semestre 20; ningún horizonte evaluado supera el 14.
6. **Estado del episodio.** Todas las variables y los eventos son del episodio (programa) o, en las trayectorias de Plan Común unidas, de las dos fases del mismo recorrido; la salida a otro programa no es un evento distinto.
7. **Población (D47, P62).** El Programa de Intercambio queda fuera por código de programa (no por duración). El Plan Común se une a su especialidad: la cohorte, el período de admisión, el perfil de ingreso y la partición son los del Plan Común; el tiempo se cuenta desde la admisión al Plan Común; el evento y la censura vienen de la especialidad (egreso o salida de la especialidad); la salida del propio Plan Común (cambio de programa) no es salida de la trayectoria. Un Plan Común sin continuación conserva el tratamiento anterior (una salida). Las variables académicas suman ambos episodios hasta el corte; las del programa son las del programa vigente al corte, de modo que la especialidad futura no llega a ningún corte anterior.

## 2. Población, embudo y tasas base

### Embudo de elegibilidad

{{tabla:embudo}}

### Intercambio y Plan Común (D47, P62)

La DAI respondió (P62) que los programas de 1 a 3 semestres no son diplomados: el **Programa de Intercambio** reúne a estudiantes de universidades extranjeras con estadías cortas, que no pueden egresar por naturaleza, y **Ingeniería Civil Plan Común** es un programa tipo bachillerato de 2 semestres cuyo estudiante, al completar la malla, pide el cambio a una especialidad de Ingeniería Civil. Por eso la población de esta versión cambia de dos maneras:

1. **Intercambio fuera.** Se excluyen los programas 0003 y 0006 (`PROGRAMAS_INTERCAMBIO`, por código de programa y no por duración; una prueba de integración compara los códigos con los nombres de `neural_core.programa`). En total son {{x:embudo.embudo_k0_intercambio_excluidos}} episodios de las cohortes 2015 o posteriores dentro de la población T1; de ellos, {{x:embudo.embudo_k0_intercambio_elegibles_excluidos}} habrían sido elegibles en `k` = 0, {{x:embudo.embudo_k2_intercambio_elegibles_excluidos}} en `k` = 2 y {{x:embudo.embudo_k4_intercambio_elegibles_excluidos}} en `k` = 4 (el resto no tiene matrícula en el semestre del corte o ya salió).
2. **Plan Común unido a su especialidad.** Un episodio de Plan Común (programas 8633 y 8643; solo el 8643 tiene episodios desde 2015) se vincula con el **primer episodio posterior de la misma persona en una especialidad de Ingeniería Civil** (nivel pregrado, lista fija `ESPECIALIDADES_ING_CIVIL` de 14 programas) si el primer estado de la especialidad cae a lo más **2 períodos regulares después del último período del Plan Común**. No se exige la vía ES ni el mismo período de admisión. La especialidad vinculada **no** se cuenta aparte, y una especialidad se asocia a un solo Plan Común.

{{tabla:union}}

*Por qué la regla inclusiva.* Exigir ES con el mismo período de admisión dejaría fuera a la mayor parte de las continuaciones reales: la regla estricta captura {{x:embudo.embudo_k0_unidos_es_mismo_periodo}} de las {{x:embudo.embudo_k0_plan_comun_unidos}} continuaciones de la ventana y exigir solo el mismo período captura {{x:embudo.embudo_k0_unidos_mismo_periodo}}. Las demás son ingresos a la especialidad por otra vía (por ejemplo, LS o RP en un período posterior) de personas que siguen en Ingeniería Civil sin interrupción mayor a 2 períodos, es decir, la progresión que describe la DAI. Se prefirió la regla inclusiva y se conserva la ventana de 2 períodos: ampliarla agrega muy pocos casos ({{x:embudo.embudo_k0_plan_comun_fuera_de_ventana}} Plan Común tienen su primera especialidad más tarde).

*Dos precisiones sobre el punto en el tiempo.* (i) La inclusión de una trayectoria en un corte se decide con la vinculación, que se conoce después del corte: la salida del propio Plan Común en el período del corte no cuenta como salida de la trayectoria cuando hay vínculo, lo que mantiene en el corte a un puñado de filas (su número exacto está en D47, `docs/00_plan.md`) que sin vínculo habrían salido de la población; es una propiedad de la definición de la unidad, igual que la etiqueta, y no de las variables. (ii) Las variables de cada corte usan solo hechos hasta el corte: los agregados académicos suman ambos episodios; el programa vigente es el Plan Común hasta que se registra el primer estado de la especialidad (nunca en `k` = 0), y solo después las variables de la especialidad. Las pruebas perturban o borran los datos de la especialidad posteriores al corte y comprueban que las variables no cambian (§4).

Resultados de las trayectorias de Plan Común por corte y partición (grupos de menos de 10 no se publican):

{{tabla:plan_comun}}

### Particiones, desenlaces y seguimiento

{{tabla:split}}

Elegibles con seguimiento a cada horizonte (las métricas por horizonte solo usan los episodios cuya cohorte llega a ese horizonte, de modo que no hay incertidumbre de censura y el peso IPCW es exactamente 1):

{{tabla:elegibles}}

### Desenlaces por cohorte (k = 2)

{{tabla:cohorte}}

### Incidencia acumulada: Aalen–Johansen frente a 1 − Kaplan–Meier

{{tabla:incidencia}}

### Tipo de salida y destino

{{tabla:salida}}

### Duración nominal del programa

{{tabla:duracion}}

## 3. Fuentes del evento: estados y tabla de titulación

{{tabla:consistencia}}

## 4. Snapshot point-in-time (migraciones 013 y 014, `python -m pipelines.snapshots.t3`)

Una fila por (episodio, `k`) con las variables del corte y la etiqueta (`tiempo`, `causa`, `seguimiento_max`). Las variables usan solo hechos de los semestres `<= k` (la misma partición en *slots* de T1: `periodo <= corte ⇔ slot <= k`, los cursos de verano/invierno cuentan en el corte siguiente) más datos estáticos del programa; la etiqueta mira solo los semestres posteriores y nunca alimenta una variable. Pruebas: perturbación (reasignar notas, borrar la mitad de los estados y agregar salidas en los semestres posteriores al corte deja idénticas las variables), borrado de todos los períodos posteriores, comprobación por mutación (la prueba **falla** si se cambia un dato anterior al corte), reglas de evento y censura, equivalencia entre la resolución vectorizada y la escalar sobre una rejilla, y un recálculo SQL independiente del tiempo de egreso, del seguimiento, de los semestres matriculados y de los intentos (`tests/integration/test_snapshot_t3.py`).

**Plan Común (D47).** La migración 014 agrega a `snapshot_t3` las columnas `trayectoria_plan_comun` (dato de admisión), `especialidad_conocida_al_corte` y `episodio_especialidad_id` (huella de auditoría del vínculo, que se decide con el futuro y **nunca** es variable: está en `LABEL_COLS` y en las columnas prohibidas de los modelos). Las dos primeras **sí** son variables de los modelos porque se conocen en el corte (la primera es un dato de admisión; la segunda solo mira estados hasta el corte). La duración nominal de una trayectoria de Plan Común antes de conocer la especialidad es la duración del Plan Común más una constante de {{x:embudo.embudo_k0_constante_duracion_plan_comun}} semestres: la mediana, **solo en las cohortes de train**, de (desfase de admisión de la especialidad + su duración nominal − la duración del Plan Común); así vale lo mismo para quien después tendrá especialidad y para quien no, y no usa la especialidad de la propia trayectoria más que como parte de la mediana de train. Pruebas nuevas (`tests/unit/test_snapshot_t3_plan_comun.py`): regla de vínculo (ventana, primera especialidad posterior, una especialidad por Plan Común, sin exigir ES), exclusión del Intercambio, ausencia de doble conteo, evento y tiempo de las trayectorias unidas, variables del programa vigente en `k` = 0, 2 y 4, constante aprendida solo con train, y perturbación y borrado de los datos de la especialidad posteriores al corte (con la prueba por mutación que debe fallar); en integración, un recálculo SQL independiente de cada vínculo, de la especialidad conocida al corte, de los semestres matriculados y de los intentos de ambos episodios, y del egreso de la especialidad.

Hash de datos: `{{meta:snapshot_hash}}`. Versión del código: `{{meta:version_codigo}}`.

## 5. Protocolo de modelado

- **Escalera de ablación** (mismos episodios, horizontes y semillas en cada escalón): Aalen–Johansen global → Aalen–Johansen por programa → perfil de ingreso → + agregados al corte → + secuencia de semestres. Cada escalón se ajusta con cuatro familias: Cox causa-específico (`lifelines`, penalizado L2; una ecuación por causa y riesgos combinados en tiempo discreto), logística multinomial persona-período, CatBoost multiclase persona-período (3 semillas) y red neuronal de riesgos discretos.
- **Redes.** MLP y GRU con cabeza *softmax causa-específica* por semestre posterior al corte (supervive / egreso / salida): la verosimilitud exacta de tiempo discreto con censura, en una pasada por episodio. No es DeepHit (sin softmax conjunto en tiempo y causa ni pérdida de ranking). AdamW, parada anticipada con la log-verosimilitud negativa de valid, 3 semillas, GPU ({{meta:gpu}}); el resultado es el promedio de las incidencias acumuladas de las 3 semillas.
- **Ajuste y selección.** Todo (medianas, escalas, vocabularios, penalizadores, `C`, iteraciones, épocas) se ajusta o elige solo con train y valid. El modelo clásico ganador se elige por IBS en valid.
- **Métricas.** Para cada horizonte `t`: C de Uno truncado en `t` con evento competitivo (Wolbers: quien tuvo la salida nunca tiene el evento de interés), AUC(t) y Brier(t) de la incidencia acumulada predicha `F₁(t | x)` entre los episodios con seguimiento hasta `t`; IBS = promedio del Brier de los semestres `k+1..12` entre los episodios con seguimiento hasta 12. Las funciones de supervivencia (Aalen–Johansen, Kaplan–Meier de la censura, C de Uno con pesos IPCW, Brier IPCW, IBS) están escritas en `evaluation/metrics_t3.py` con pruebas contra casos calculados a mano y contra `lifelines`; no se usó `scikit-survival`.
- **Incertidumbre.** Bootstrap de 1.000 remuestreos de episodios (300 en el control posterior), con los **mismos** remuestreos para todos los modelos, de modo que las diferencias pareadas son válidas. Las particiones valid y test se reportan por separado.
- **Seguimiento.** MLflow local (experimento `t3_tiempo_hasta_titulacion`) con hash de los datos y versión del código.

## 6. Resultados por corte

Convención: intervalos del 95 % entre corchetes (bootstrap de episodios, mismos remuestreos para todos los modelos); las diferencias son **pareadas** (A − B). Para C y AUC, más es mejor; para Brier e IBS, menos es mejor. Horizonte principal: 12 semestres desde la admisión. Las tablas completas de valid y de test siguen; el control posterior está en §7.4.

### 6.1 Al ingreso (k = 0, «postulante»)

Test (cohortes 2019-2020):

{{tabla:rank.0.test}}

{{tabla:brier.0.test}}

Diferencias pareadas en test:

{{tabla:deltas.0.test}}

Lectura. Pasar de Aalen–Johansen global a por programa añade {{d:0.test.km_programa.km_global.c_12}} de C(12); agregar el perfil de ingreso (Cox) otros {{d:0.test.cox_adm.km_programa.c_12}}; después de eso los cuatro modelos son equivalentes en discriminación (C(12) entre {{v:0.test.dt_cb_adm.c_12}} y {{v:0.test.nn_mlp_adm.c_12}}, diferencias con IC que incluyen el 0). Las redes y CatBoost no mejoran a la logística ni al Cox en ranking; el MLP tiene el mejor IBS en test ({{v:0.test.nn_mlp_adm.ibs}}) y la diferencia con la logística ({{d:0.test.nn_mlp_adm.dt_lr_adm.ibs}}) es significativa pero de magnitud pequeña. CatBoost y la logística difieren en C(10) con signos que dependen del horizonte (§7.2).

Valid (cohorte 2018):

{{tabla:rank.0.valid}}

{{tabla:brier.0.valid}}

### 6.2 Después de 2 semestres (k = 2)

Test (cohortes 2019-2020):

{{tabla:rank.2.test}}

{{tabla:brier.2.test}}

Diferencias pareadas en test (incluye cada escalón de la ablación y red frente a clásico):

{{tabla:deltas.2.test}}

Lectura.

- **Agregados académicos.** Con el mismo modelo, agregarlos sube C(12) en {{d:2.test.dt_cb_agg.dt_cb_adm.c_12}} a {{d:2.test.dt_lr_agg.dt_lr_adm.c_12}} (Cox {{d:2.test.cox_agg.cox_adm.c_12}}; logística {{d:2.test.dt_lr_agg.dt_lr_adm.c_12}}; CatBoost {{d:2.test.dt_cb_agg.dt_cb_adm.c_12}}; MLP {{d:2.test.nn_mlp_agg.nn_mlp_adm.c_12}}) y baja el IBS entre 0,010 y 0,013. Es la mayor ganancia de la tarea.
- **Entre clásicos con agregados**, la logística y el Cox son equivalentes (C(12) {{v:2.test.dt_lr_agg.c_12}} y {{v:2.test.cox_agg.c_12}}; Δ = {{d:2.test.dt_lr_agg.cox_agg.c_12}}); CatBoost es **peor** ({{v:2.test.dt_cb_agg.c_12}}; {{d:2.test.dt_cb_agg.dt_lr_agg.c_12}} frente a la logística).
- **Redes frente a clásicos con las mismas variables.** El MLP con agregados queda por debajo de la logística en C(12) ({{d:2.test.nn_mlp_agg.dt_lr_agg.c_12}}), empata con el Cox ({{d:2.test.nn_mlp_agg.cox_agg.c_12}}) y mejora al Cox en IBS ({{d:2.test.nn_mlp_agg.cox_agg.ibs}}); la diferencia con la logística en IBS no es distinta de cero ({{d:2.test.nn_mlp_agg.dt_lr_agg.ibs}}). El MLP supera a CatBoost ({{d:2.test.nn_mlp_agg.dt_cb_agg.c_12}}).
- **La GRU sobre la secuencia de semestres** es el mejor modelo del corte: C(12) = {{ic:2.test.nn_gru.c_12}} e IBS = {{ic:2.test.nn_gru.ibs}}. Gana al MLP con los mismos agregados ({{d:2.test.nn_gru.nn_mlp_agg.c_12}} en C(12); {{d:2.test.nn_gru.nn_mlp_agg.ibs}} en IBS), al Cox con agregados ({{d:2.test.nn_gru.cox_agg.c_12}}; {{d:2.test.nn_gru.cox_agg.ibs}}) y a CatBoost ({{d:2.test.nn_gru.dt_cb_agg.c_12}}). Frente a la logística con agregados la ventaja, por transitividad, es de aproximadamente 0,011 en C(12) (comparación directa no calculada).
- La variación entre semillas es pequeña (§7.2): sd de C(12) en test 0,005 para la GRU.

Valid (cohorte 2018):

{{tabla:rank.2.valid}}

{{tabla:brier.2.valid}}

Ablación completa (valid):

{{tabla:ablacion.2.valid}}

Ablación completa (test):

{{tabla:ablacion.2.test}}

### 6.3 Después de 4 semestres (k = 4)

Test (cohortes 2019-2020):

{{tabla:rank.4.test}}

{{tabla:brier.4.test}}

Diferencias pareadas en test:

{{tabla:deltas.4.test}}

Lectura.

- Los agregados vuelven a ser la ganancia dominante (C(12) de {{v:4.test.cox_adm.c_12}} a {{v:4.test.cox_agg.c_12}} en el Cox).
- **La ventaja neuronal es marginal.** Con agregados, la logística ({{v:4.test.dt_lr_agg.c_12}}), CatBoost ({{v:4.test.dt_cb_agg.c_12}}) y la GRU ({{v:4.test.nn_gru.c_12}}) quedan muy cerca en C(12). La GRU supera apenas a CatBoost ({{d:4.test.nn_gru.dt_cb_agg.c_12}}) y tiene **peor IBS** ({{d:4.test.nn_gru.dt_cb_agg.ibs}}); CatBoost tiene el mejor IBS ({{ic:4.test.dt_cb_agg.ibs}}). La GRU gana al MLP con agregados por muy poco ({{d:4.test.nn_gru.nn_mlp_agg.c_12}}) y supera al Cox con agregados en C(12) ({{d:4.test.nn_gru.cox_agg.c_12}}) y en IBS ({{d:4.test.nn_gru.cox_agg.ibs}}).
- El MLP con agregados es **peor** que la logística ({{d:4.test.nn_mlp_agg.dt_lr_agg.c_12}}), aunque esa comparación es frágil por la variación entre semillas del MLP (§7.2).
- La secuencia añade poco al avanzar el corte: el resumen en agregados ya contiene casi toda la información del trayecto.

Valid (cohorte 2018):

{{tabla:rank.4.valid}}

{{tabla:brier.4.valid}}

Ablación completa (test):

{{tabla:ablacion.4.test}}

## 7. Análisis transversal

### 7.1 ¿Qué modelo, y es mejor la red?

Mejor clásico elegido por IBS en valid, y mejor red por IBS en valid:

{{tabla:mejor}}

Resumen de la ablación, test (C(12) con IC; IBS con IC):

{{tabla:ablacion.0.test}}

Respuestas a las preguntas del encargo:

- *¿Algo vence a Kaplan–Meier / Aalen–Johansen por programa?* Sí, siempre: el perfil de ingreso suma {{d:0.test.cox_adm.km_programa.c_12}} de C(12) en test; los agregados, {{d:2.test.cox_agg.cox_adm.c_12}} a {{d:4.test.cox_agg.cox_adm.c_12}} más.
- *¿Algo vence al Cox causa-específico?* La logística persona-período lo supera por poco y de manera consistente con agregados ({{d:2.test.dt_lr_agg.cox_agg.c_12}} y {{d:4.test.dt_lr_agg.cox_agg.c_12}} de C(12); IBS {{d:2.test.dt_lr_agg.cox_agg.ibs}} y {{d:4.test.dt_lr_agg.cox_agg.ibs}}); con las mismas variables, la red añade un poco en IBS. Solo la GRU de k = 2 mejora de forma clara en discriminación ({{d:2.test.nn_gru.cox_agg.c_12}}).
- *¿Las redes agregan señal?* Poca, y solo con la secuencia en k = 2. En k = 0 y k = 4 no hay mejora de discriminación frente al mejor clásico, y en k = 4 el mejor IBS es de CatBoost. Se conserva el modelo clásico donde las redes no superan: ver §9.

### 7.2 Estabilidad entre semillas y entre horizontes

Resultados de las redes por semilla (media ± sd de 3 semillas):

{{tabla:semillas}}

Las desviaciones entre semillas (≤ 0,014 en C, la mayor en el MLP de ingreso de k = 4; la GRU tiene 0,005 y 0,004) son menores que las diferencias entre modelos que se destacan arriba, salvo el MLP con agregados en k = 4 (sd 0,007), cuya comparación con la logística es por tanto frágil. CatBoost cambia de signo entre horizontes en valid (C(10) alto, C(12) y C(14) bajos): probablemente aprende un patrón de calendario por semestre (el egreso se registra en bloques, P60) y un solo horizonte engaña; por eso se reportan 10, 12 y 14 y el IBS.

### 7.3 Calibración y deriva entre cohortes

Incidencia acumulada a cada horizonte frente a la observada (test):

{{tabla:incidencia_media.0}}

{{tabla:incidencia_media.2}}

{{tabla:incidencia_media.4}}

Calibración por decil a 12 semestres (test):

{{tabla:calibracion.0.12}}

{{tabla:calibracion.2.12}}

{{tabla:calibracion.4.12}}

Lectura.

- Los modelos de **solo ingreso** subestiman sistemáticamente el egreso en test (predicen {{pct:por_k.0.incidencia_media_test.12.cox_adm}}–{{pct:por_k.4.incidencia_media_test.12.dt_cb_adm}} a 12 semestres frente al {{pct:por_k.0.incidencia_media_test.12.observada}}–{{pct:por_k.4.incidencia_media_test.12.observada}} observado, según el corte). La causa no es el modelo sino la **deriva de cohorte**: la incidencia acumulada de egreso a 12 semestres es {{pct:descriptivo.incidencia_comparada.train.F1.4}} en train y {{pct:descriptivo.incidencia_comparada.test.F1.4}} en test (la mediana pasó de 13 a 11 semestres). Ninguna variable de ingreso explica ese cambio.
- Los modelos con **agregados** absorben la mayor parte de la deriva porque observan el avance real: en k = 2 el Cox con agregados predice {{pct:por_k.2.incidencia_media_test.12.cox_agg}} (observado {{pct:por_k.2.incidencia_media_test.12.observada}}), CatBoost {{pct:por_k.2.incidencia_media_test.12.dt_cb_agg}}, la GRU {{pct:por_k.2.incidencia_media_test.12.nn_gru}} y el MLP {{pct:por_k.2.incidencia_media_test.12.nn_mlp_agg}}; en k = 4, {{pct:por_k.4.incidencia_media_test.12.cox_agg}}, {{pct:por_k.4.incidencia_media_test.12.dt_cb_agg}}, {{pct:por_k.4.incidencia_media_test.12.nn_gru}} y {{pct:por_k.4.incidencia_media_test.12.nn_mlp_agg}} frente al {{pct:por_k.4.incidencia_media_test.12.observada}} observado. Los árboles y las redes tienden a sobrestimar un poco en k = 4 (+4,0 pp la GRU); el Cox, a subestimar.
- Los deciles extremos están bien ordenados; en los deciles bajos de k = 0, la tasa observada es mayor que la predicha (el riesgo mínimo está subestimado).

Calibración por cohorte (k = 2):

{{tabla:sub.2.cohorte}}

### 7.4 Control posterior (cohortes 2021 en adelante, horizontes 8 y 10)

Es solo un control de estabilidad: pocos episodios (§2) y casi todo censurado. No se usa para elegir.

{{tabla:rank.2.posterior}}

{{tabla:rank.4.posterior}}

Lectura. Los modelos de solo ingreso con árboles o red (CatBoost y MLP) son **erráticos**: el C de CatBoost pasa de {{v:2.posterior.dt_cb_adm.c_8}} (t = 8) a {{v:2.posterior.dt_cb_adm.c_10}} (t = 10) en k = 2 y de {{v:4.posterior.dt_cb_adm.c_8}} a {{v:4.posterior.dt_cb_adm.c_10}} en k = 4, y el del MLP queda en {{v:4.posterior.nn_mlp_adm.c_10}}–{{v:2.posterior.nn_mlp_adm.c_10}} en t = 10, una inversión sin explicación sustantiva que no se ve en Cox ni en logística; probablemente por el mismo patrón de calendario (§7.2). Con agregados, la logística es la más estable (C(10) = {{v:2.posterior.dt_lr_agg.c_10}} en k = 2 y {{v:4.posterior.dt_lr_agg.c_10}} en k = 4); el MLP y la GRU caen a {{v:2.posterior.nn_mlp_agg.c_10}}–{{v:4.posterior.nn_gru.c_10}} en t = 10 y CatBoost conserva {{v:2.posterior.dt_cb_agg.c_10}} en k = 2 y {{v:4.posterior.dt_cb_agg.c_10}} en k = 4. Es otra razón para no preferir los modelos de mayor capacidad sin revisión.

### 7.5 Subgrupos y equidad

**Sexo** (solo para evaluación de equidad, nunca como variable): las mujeres egresan más (k = 2: {{pct:por_k.2.subgrupos_test.nn_gru.sexo.0.incidencia_observada}} frente a {{pct:por_k.2.subgrupos_test.nn_gru.sexo.1.incidencia_observada}} a 12 semestres en test). Brecha de AUC (F − M) en test:

{{tabla:sexo.0}}

{{tabla:sexo.2}}

{{tabla:sexo.4}}

- La discriminación es equivalente por sexo en los modelos de ingreso (|ΔAUC| ≤ 0,02). Con agregados el AUC es algo mayor en hombres (−0,02 a −0,03 en k = 2; ≤ 0,01 en k = 4).
- La calibración difiere de otra manera: los modelos de solo ingreso subestiman a las mujeres más que a los hombres (brecha −0,16 frente a −0,11 en k = 2); con agregados la brecha se reduce a entre −0,06 y +0,05 en ambos sexos y es casi simétrica (GRU: +0,008 y +0,009 en k = 2).

**Vía de ingreso** (test, k = 2 y k = 4; `otros_cambio` = ingresos por cambio de carrera o similares):

{{tabla:sub.2.via}}

{{tabla:sub.4.via}}

- La discriminación de la GRU es alta y similar en todas las vías (AUC 0,85–0,91), pero en `otros_cambio` (n pequeño) el egreso observado es mayor (0,56–0,61) y los modelos de ingreso lo subestiman; con agregados la brecha se reduce.

**Duración nominal y programas** (k = 2, test; grupos de al menos 150 episodios):

{{tabla:sub.2.duracion_nominal}}

{{tabla:sub.2.programa_n150}}

- Los programas con duración nominal de 12 semestres o más tienen muy poco egreso observable a 12 semestres (4–5 %) y el AUC es menos estable.
- Ningún programa alcanza 500 episodios con seguimiento a 12 semestres (el mayor es de ≈ 250), así que la tabla pedida para n ≥ 500 queda vacía; se reportan los grupos de al menos 150.

**Trayectorias de Plan Común (D47)** frente al resto (test, n ≥ 10; incidencia observada y predicha a 12 semestres desde la admisión entre los episodios con seguimiento hasta ahí; son pocos episodios (40 a 70), así que los intervalos son amplios):

k = 0:

{{tabla:sub.0.plan_comun}}

k = 2:

{{tabla:sub.2.plan_comun}}

k = 4:

{{tabla:sub.4.plan_comun}}

- Las trayectorias de Plan Común tienen mucho menos egreso a 12 semestres que el resto, porque el tiempo cuenta desde el ingreso al Plan Común, a ese horizonte aún les quedan semestres de la especialidad y las que no tienen continuación nunca egresan (§2). Los modelos de solo ingreso subestiman su egreso (en k = 0, mucho más que el resto en términos relativos); con agregados y secuencia (k = 2 y 4) la GRU predice algo menos que lo observado (brecha de −0,03 en ambos cortes) y las ordena bien (AUC alto). Con 40 a 70 episodios por grupo estas diferencias no se han acompañado de intervalos y no deben leerse como un sesgo establecido.

Los grupos de menos de 10 episodios no se publican.

### 7.6 Costo y reproducibilidad de la ejecución

{{tabla:tiempos}}

Tiempo total del benchmark: {{meta:minutos}} minutos; RAM pico {{meta:ram}} MB. Importancia de variables de CatBoost (media de 3 semillas, % de la importancia total):

{{tabla:importancia.2}}

El tiempo (`slot`, `slot_rel_nominal`) y el avance de créditos dominan; el programa y los puntajes de ingreso pesan menos.

## 8. Limitaciones y preguntas abiertas

1. **Deriva de cohorte (P60).** La incidencia acumulada de egreso a 12 semestres pasa de {{pct:descriptivo.incidencia_comparada.train.F1.4}} (2015-2017) a {{pct:descriptivo.incidencia_comparada.valid.F1.4}} (2018) y {{pct:descriptivo.incidencia_comparada.test.F1.4}} (2019-2020); la mediana del tiempo al egreso, de 13 a 11. Es posible que parte del cambio sea de **registro** (lotes de estados «Z» en períodos «10») y no de comportamiento.
2. **Etiquetas de train observadas hasta 2026.** Las cohortes de train se observan hasta períodos que son posteriores al corte de las de test; es inherente al corte por cohorte y puede favorecer a los modelos de calendario.
3. **Egreso frente a titulación (P59).** El evento es el primer estado de egreso (casi siempre `Z`), no la titulación (`U`/fila de `titulacion`): 1.757 episodios tienen una fila de titulación anterior al primer estado y 386 tienen `U` sin fila; hay 1.260 filas de titulación sin episodio. La titulación se guarda como punto final de sensibilidad (`tiempo_titulacion`) y no se modela.
4. **La «salida» es, en gran parte, una transferencia (P61).** El 97 % de las salidas por ausencia (y 12–26 % de las explícitas) están matriculados después en otro programa de la UCN. La salida del episodio no equivale a deserción de la universidad.
5. **Intercambio y Plan Común (P62, D47).** El Programa de Intercambio se excluyó y el Plan Común se unió a su especialidad; el Plan Común sin continuación en Ingeniería Civil sigue contando como salida (es un cambio a otro programa o un abandono, y el sistema no los distingue). La vinculación usa estados y no un registro formal de cambio de especialidad; la regla (primer episodio posterior de Ingeniería Civil dentro de 2 períodos) es una aproximación que la DAI puede refinar. Las trayectorias de Plan Común son pocas frente al total (§2), y sus tablas de calibración tienen intervalos amplios.
6. **Períodos 201920 y 202010 (P58).** No tienen reprobaciones registradas: se excluyeron los conteos de intentos de las variables de los modelos; los agregados restantes (créditos, tasas, promedios sobre semestres con fallos) son robustos pero no inmunes.
7. **Completitud del último período (P63).** 202610 es el último período regular cerrado; 202620 (en curso) se excluye y 253 egresos registrados allí se censuran. No se ha verificado si 202610 es completo para egreso/titulación.
8. **Estabilidad de los modelos de mayor capacidad.** CatBoost y el MLP de solo ingreso son erráticos en el control posterior (§7.4) y CatBoost cambia de signo entre horizontes (§7.2). Hace falta más cohortes para decidir.
9. **Sin DeepHit ni redes de tiempo continuo.** Las redes son de riesgos discretos con cabeza softmax por semestre; no se probaron otras formulaciones.
10. **Año de admisión.** No es variable de los modelos (§1, §6): una primera versión con el año como número hacía fallar a las redes en las cohortes 2021-2022. La cohorte queda como columna del snapshot, de los cortes y de las tablas por subgrupo.

## 9. Recomendación

- **k = 0 (postulante).** Usar la logística persona-período (o el Cox) con perfil de ingreso y programa; la red no aporta discriminación (|Δ| ≤ 0,01) y solo mejora el IBS en 0,001–0,003. No reportar probabilidades absolutas sin recalibrar con la cohorte más reciente (§7.3).
- **k = 2.** La GRU con secuencia es el mejor modelo técnico (+0,016 a +0,020 de C(12) sobre la logística y el Cox, +0,039 sobre CatBoost; IBS −0,004 a −0,005), pero la mejora es modesta y hay que repetir la estimación con nuevas cohortes y una recalibración antes de cualquier uso.
- **k = 4.** Conservar la logística o CatBoost: la GRU mejora el C(12) en 0,005 a 0,010 pero empeora el IBS frente a CatBoost.
- En todos los cortes los agregados académicos explican casi toda la mejora; antes de invertir en arquitecturas más complejas conviene mejorar la calidad de esos datos (P58) y aclarar el evento (P59).
- **Beneficios estudiantiles (16-11-2026, §11).** No se adoptan: ningún modelo con beneficios mejora al oficial en `k = 4` con la regla de años anteriores al del corte, y en `k = 2` la ablación no es aplicable. Se reevaluará con una fecha de asignación de los beneficios (P90, P98).
- **El uso de predicciones individuales no está aprobado** (Gate 4). Todo el contenido es agregado.

## 10. Reproducibilidad

- Migraciones: `python -m pipelines.migrate` (013 y 014). Snapshot: `python -m pipelines.snapshots.t3`. Benchmark: `python -m evaluation.run_t3` (`--k`, `--seeds`, `--boot`, `--solo`). Informe: `python tools/informe_t3.py --doc`.
- Resultados agregados: `artefactos/resultados_t3.json` (ignorado por git); predicciones por episodio: `artefactos/preds/` (nunca fuera del equipo).
- Hash de datos `{{meta:snapshot_hash}}`; versión del código `{{meta:version_codigo}}`; MLflow `t3_tiempo_hasta_titulacion`.
- Todos los números de este documento se generan desde el JSON con `tools/plantilla_t3.md`; no se editan a mano en `docs/10_benchmark_t3.md`.

## 11. Beneficios (16-11-2026)

**Pregunta.** La hipótesis del plan semanal es que la gratuidad se pierde al superar la duración formal del programa (la UCN otorga entonces rebajas «Expiración Gratuidad N+1» y «Brecha … N+1 / N+2») y que el «Ajuste Deuda Capstone Project» marca la etapa final. Ambas señales deberían anticipar el egreso. Se prueba con la tabla `banner.banner_beneficios` ya extraída y seudonimizada (decisiones D90–D95) y con una regla estricta de punto en el tiempo. Solo agregados; ningún RUT, monto individual ni predicción por persona figura aquí.

**Resultado en una línea.** **El modelo oficial de T3 no cambia.** En los cortes oficiales `k = 2` y `k = 4`, ningún modelo con beneficios cumple el criterio de adopción bajo la regla por defecto (años anteriores al del corte): en `k = 2` casi nadie tiene datos de beneficios previos al corte y la ablación no es aplicable; en `k = 4` la GRU con todos los beneficios cambia el C(12) de valid en {{bd:4.valid.gru_previo_todo.gru_acad.c_12}} y el IBS de valid en {{bd:4.valid.gru_previo_todo.gru_acad.ibs}} (el intervalo incluye el 0 en ambas). La única mejora en valid con intervalo que excluye el 0 (GRU con el bloque de financiamiento, ΔIBS {{bd:4.valid.gru_previo_fin.gru_acad.ibs}}) no se confirma en test ({{bd:4.test.gru_previo_fin.gru_acad.ibs}}). En cortes tardíos (`k = 8` y `k = 10`, donde las banderas de expiración y Capstone sí existen) la GRU con beneficios empeora (en `k = 10`, ΔC(12) de test {{bd:10.test.gru_previo_todo.gru_acad.c_12}}) y la única mejora estadística aparece en la logística bajo la regla con fuga (§11.6). Las banderas de Capstone del año del corte no son un hecho conocido al corte (§11.3).

### 11.1 Variables, regla de punto en el tiempo y cortes

| Bloque | Variables (todas del año calendario leído; solo el monto del primer semestre) |
|---|---|
| `fin` (financiamiento) | `tiene_gratuidad`, `tiene_credito`, `tiene_beca_estatal`, `tiene_beca_ucn`, `merito_ingreso`, `merito_e1`, `n_beneficios`, `monto_sem1`, `anios_con_gratuidad` (años de la ventana del estudiante con gratuidad; desconocido si la ventana empieza antes de 2017) y las pérdidas entre el último año permitido y el anterior (`perdio_gratuidad`, `perdio_credito`, `perdio_cualquier_beneficio`, `obtuvo_gratuidad`) con su indicador de dato faltante |
| `expcap` (la hipótesis) | `expiro_gratuidad` (0 / 1 = N+1 / 2 = N+2), `etapa_capstone`, `expiro_alguna` y `capstone_alguna` (alguna vez en la ventana del estudiante) |
| `todo` | los dos bloques anteriores |
| Solo equidad (nunca variable) | `banda_decil` (≤ 6 con gratuidad; 7 y 8-9 por «Rebaja Arancel Decil»; desconocida) y `sexo`. Se descartó `banda_decil` como variable: es una función de la gratuidad y la rebaja ya incluidas y llevaría el nivel socioeconómico a la decisión sin ganancia que lo justifique |

**Regla de punto en el tiempo** (`rules_beneficios_t3.py`; D100). La tabla es anual, guarda el **estado final** de cada año (quien se retira pierde la fila o se anula el monto del segundo semestre, D92) y no tiene fecha de asignación (P90, P93). Un corte de T3 termina en el período `AAAA10` (mitad de año) o `AAAA20` (fin de año).

- **`previo` (por defecto; la regla del criterio de adopción):** solo años calendario **estrictamente anteriores** al del corte.
- **`con_t` (sensibilidad):** en un corte de fin de año (`AAAA20`) se lee además el año del corte; en uno de mitad de año se comporta como `previo`.
- En ambas, solo se leen los años de la **ventana propia** del estudiante (desde `max(2017, año de admisión)`): un año anterior a la admisión es «aún no es estudiante», no «sin beneficios», y queda desconocido (NaN + indicador), igual que los años anteriores a 2017 o posteriores al último cargado. Solo cuentan las filas del programa vigente al corte o del programa de admisión (Plan Común y su especialidad); `benef_sem2` y `total` nunca son variables.
- `k = 0` («al ingreso») no tiene beneficios previos por construcción y no se evalúa.

**Cortes.** Los oficiales `k = 2, 4` y, como **extensión**, los tardíos `k = 8, 10` (migración 027: `snapshot_t3_ext*`, misma construcción, columnas y particiones que el snapshot oficial, hash `{{bmeta:hash_ext}}`). Se agregaron porque las banderas de la hipótesis aparecen mucho después de los cortes oficiales:

{{ben:diag.distribucion}}

(Filas persona-año de pregrado con la bandera, por años desde el año de admisión del mismo programa.) Con cortes a 2 y 4 semestres casi ninguna fila tiene la bandera; con la regla `previo` en `k = 4` solo se lee el año de admisión. Por eso el criterio de adopción se juzga en los cortes oficiales y la extensión muestra si la señal existe cuando sí puede observarse.

### 11.2 Cobertura de los datos por corte y regla

{{ben:cobertura}}

Un corte es «no aplicable» si menos del 5 % de sus filas de train o de test tiene datos bajo la regla (`k = 2` con `previo`: solo los admitidos en el segundo semestre tienen un año anterior al corte dentro de su ventana). Las cohortes 2015 y 2016 de train no tienen datos de beneficios en `k ≤ 4` (la tabla empieza en 2017; P93): el entrenamiento ve beneficios en una fracción de las filas y el modelo los imputa con la mediana de train más un indicador; valid y test sí los tienen en todas las filas.

### 11.3 Diagnóstico de fuga: ¿el año `t` es un hecho del corte? (justificación de la regla)

Para cada corte se compara, por desenlace posterior, qué tan frecuente es tener fila de beneficio o gratuidad en el año `t` del corte y en el año `t − 1` (misma población, un año antes). Si el año `t` fuera un hecho conocido al corte, la brecha entre quienes luego salen y quienes siguen se parecería a la del año `t − 1`. La tabla da la brecha «salida definitiva menos sigue matriculado o censurado» en puntos porcentuales.

{{ben:diag.brechas}}

- **Cortes de mitad de año:** la brecha del año `t` es varias veces la del año `t − 1` (en `k = 4`, la presencia de fila difiere en −21,9 puntos contra −4,3 y la gratuidad en −15,4 contra −0,1): quien se retira durante el año pierde la fila o la gratuidad antes del corte siguiente (consistente con D92). Esos cortes **no** leen el año `t` en ninguna regla.
- **Cortes de fin de año:** la brecha del año `t` sigue siendo mayor que la del año `t − 1` (entre 2 y 5 puntos en presencia de fila y en gratuidad): la fila del año `t` refleja parte del desenlace posterior. Es una fuga pequeña pero sistemática, y sin fecha de asignación no se puede acotar.
- **`k = 2` de fin de año** (la mayoría de los cortes de `k = 2`) no tiene un año `t − 1` dentro de la ventana de un recién admitido, de modo que no es comparable; es el caso más expuesto a la fuga (D92: entre quienes salen en el año de ingreso solo el 4,3 % conserva alguna fila, frente al 73,9 % del resto).
- **Regla elegida (D100):** `previo` por defecto; `con_t` solo como sensibilidad, porque su ganancia o pérdida no se puede atribuir a información disponible al corte.

**¿Las banderas de expiración y Capstone del año `t` se asignan temprano?** Entre los cortes de fin de año que tienen la bandera en el año `t`, se mide qué fracción tiene monto en el primer semestre (la bandera rige desde el inicio del año) y cuál lo tiene en el segundo (`benef_sem2` solo se usa aquí, en el diagnóstico):

{{ben:diag.banderas}}

- **Expiración:** la mayoría (77 % a 91 %) ya tiene monto en el primer semestre y su frecuencia por desenlace es estable entre `t` y `t − 1` (por ejemplo, en `k = 10` de fin de año: {{bdiag:k10_fin_de_anio.anio_t.salida.expiro}} de quienes salen y {{bdiag:k10_fin_de_anio.anio_t.censura.expiro}} de quienes siguen en el año `t`, frente a {{bdiag:k10_fin_de_anio.anio_t_menos_1.salida.expiro}} y {{bdiag:k10_fin_de_anio.anio_t_menos_1.censura.expiro}} en el año anterior). Parece asignada al inicio del año, pero la prueba es indirecta.
- **Capstone:** solo el 4 % de las filas con la bandera en `k = 10` tiene monto en el primer semestre y el 99 % lo tiene en el segundo: **se asigna en el segundo semestre**, es decir, al cursar la etapa final. En `k = 10` de fin de año la bandera aparece en {{bdiag:k10_fin_de_anio.anio_t.egreso_siguiente.capstone}} de quienes egresan en el semestre siguiente y en {{bdiag:k10_fin_de_anio.anio_t.censura.capstone}} de quienes siguen (año anterior: {{bdiag:k10_fin_de_anio.anio_t_menos_1.egreso_siguiente.capstone}}). Es la señal de cercanía al egreso que planteaba la hipótesis, pero se genera en el semestre que termina en el corte y sin fecha de asignación no se puede asegurar que exista antes de él; tampoco se puede descartar que el egreso mismo la cree. **No se usa como hecho del corte** (solo en la sensibilidad `con_t`).

Prevalencia de las banderas por desenlace posterior (año `t` frente a `t − 1`):

{{ben:diag.prevalencias}}

### 11.4 Reproducción del modelo oficial

El modelo «ingreso + agregados» se reentrenó con los mismos datos, semillas y particiones (código nuevo, sin tocar el oficial). Debe coincidir con `resultados_t3.json`:

{{ben:reproduccion}}

### 11.5 Ablación en los cortes oficiales (`k = 2` y `k = 4`)

Modelos y evaluación como en §6 (regresión logística y CatBoost persona-período, GRU de riesgos discretos con 3 semillas; selección en valid; bootstrap por episodio de 1000 remuestreos con las **mismas** remuestras para todos los modelos y diferencias pareadas; C de Uno a 12 semestres desde la admisión e IBS hasta el semestre 12).

**Criterio de adopción (D100).** Un modelo con beneficios reemplaza al modelo oficial sin beneficios solo si, **con la regla `previo`**, su ΔC(12) pareado en valid tiene intervalo sobre 0 o su ΔIBS pareado en valid tiene intervalo bajo 0, y en test la métrica que califica no empeora en su estimación puntual y ninguna de las dos empeora significativamente. La sensibilidad `con_t` y los cortes tardíos no se adoptan nunca. Es una comparación de varias familias, bloques y reglas: un intervalo que excluye el 0 por poco se interpreta con cautela.

**`k = 2`, regla `previo`:** {{ben:ablacion.2.previo}}

**`k = 2`, regla `con_t` (sensibilidad):**

{{ben:ablacion.2.con_t}}

{{ben:deltas.2.con_t}}

**`k = 4`, regla `previo` (por defecto):**

{{ben:ablacion.4.previo}}

{{ben:deltas.4.previo}}

**`k = 4`, regla `con_t` (sensibilidad):**

{{ben:ablacion.4.con_t}}

{{ben:deltas.4.con_t}}

**Decisión sobre los cortes oficiales (regla por defecto):**

{{ben:decision}}

### 11.6 Extensión: cortes tardíos (`k = 8` y `k = 10`)

Aquí las banderas de expiración y Capstone sí existen (§11.1). No son cortes oficiales: no se adoptan, se informan para saber si la señal está.

**`k = 8`, regla `previo`:**

{{ben:ablacion.8.previo}}

{{ben:deltas.8.previo}}

**`k = 8`, regla `con_t` (sensibilidad):**

{{ben:deltas.8.con_t}}

**`k = 10`, regla `previo`:**

{{ben:ablacion.10.previo}}

{{ben:deltas.10.previo}}

**`k = 10`, regla `con_t` (sensibilidad):**

{{ben:deltas.10.con_t}}

**Lectura.** (1) Con la regla `previo` la GRU empeora con beneficios en ambos cortes tardíos, con intervalos que excluyen el 0 (`k = 10`, bloque `todo`: ΔC(12) de valid {{bd:10.valid.gru_previo_todo.gru_acad.c_12}}; de test {{bd:10.test.gru_previo_todo.gru_acad.c_12}}; `k = 8`: test {{bd:8.test.gru_previo_todo.gru_acad.c_12}}). CatBoost y la logística quedan en diferencias de milésimas. (2) La única mejora estadística en estos cortes es la de la logística con `con_t` en `k = 10` (ΔIBS de test, bloque `todo`: {{bd:10.test.lr_con_t_todo.lr_acad.ibs}}), y no se reproduce en la GRU. Es coherente con la fuga del año `t`: la presencia de alguna fila de beneficio es {{bdiag:k10_fin_de_anio.anio_t.egreso_siguiente.fila}} entre quienes egresan en el semestre siguiente frente a {{bdiag:k10_fin_de_anio.anio_t_menos_1.egreso_siguiente.fila}} en el año anterior (§11.3). Sin una fecha de asignación no se puede separar la señal real de la fuga. (3) Ni siquiera en estos cortes las banderas de expiración y Capstone mejoran a la GRU sin beneficios: los créditos aprobados y el avance de malla ya sitúan al estudiante cerca del egreso.

### 11.7 Resultados por programa y por facultad (test; GRU con todos los beneficios frente a la GRU oficial; regla `previo`)

Solo grupos con n ≥ 100 y al menos 10 egresos dentro de 12 semestres; los grupos con menos de 10 episodios no se publican. La facultad se nombra con `neural_core.facultad`. El C(12) por grupo es una estimación puntual sin intervalo (grupos pequeños) y se lee como descriptivo.

**`k = 4` por facultad:**

{{ben:grupos.4.previo.facultad}}

**`k = 4` por programa:**

{{ben:grupos.4.previo.programa}}

**`k = 8` (extensión) por facultad:**

{{ben:grupos.8.previo.facultad}}

### 11.8 Equidad (test; mismo par de modelos; regla `previo`)

La banda de decil de estos cuadros es la del año del corte (solo agrupación descriptiva, nunca variable). `sexo` solo se usa aquí.

**`k = 4`, por banda de decil:**

{{ben:grupos.4.previo.banda_decil}}

**`k = 4`, por sexo:**

{{ben:grupos.4.previo.sexo}}

**`k = 8` (extensión), por banda de decil:**

{{ben:grupos.8.previo.banda_decil}}

### 11.9 Conclusión y límites

1. **No se adopta ningún modelo con beneficios en T3.** En `k = 4` (el único corte oficial con datos previos al corte) ningún bloque cumple el criterio de adopción (la única mejora en valid con intervalo favorable, GRU + financiamiento en IBS, desaparece en test); en `k = 2` la ablación no es aplicable con la regla por defecto. Los agregados académicos (créditos aprobados, avance de malla, matrícula) ya contienen la cercanía al egreso que se esperaba leer en las banderas.
2. **La señal de Capstone existe, pero no es previa al corte.** Se asigna en el semestre final y, bajo `con_t`, aparece más entre quienes egresan pronto; con fuga detectable en el año `t` no se puede usar como variable.
3. **Datos de entrenamiento.** Las cohortes 2015-2016 no tienen beneficios en `k ≤ 4` (P93): el modelo con beneficios aprende de una fracción del train y la tabla refleja el estado final del año. Con los datos actuales no se puede mejorar sin una fecha de asignación (P90) ni historial anterior a 2024.
4. **Reevaluar** cuando exista una fecha de asignación o cargas por semestre: la regla `con_t` sería entonces verificable y los cortes tardíos podrían adoptarse como cortes operativos de T3 (P98–P105).
5. **Reproducibilidad.** Migración 027 (`python -m pipelines.migrate`), `python -m pipelines.snapshots.t3_beneficios` (tabla lateral `snapshot_t3_beneficios` y cortes tardíos; se repite tras cada reconstrucción de `snapshot_t3`), `python -m evaluation.diagnostico_beneficios_t3`, `python -m evaluation.run_beneficios_t3` ({{bmeta:minutos}} min) y `python tools/informe_t3_beneficios.py --doc`. Resultados: `artefactos/resultados_t3_beneficios.json` y `diagnostico_beneficios_t3.json` (ignorados por git); hash de la tabla de beneficios `{{bmeta:hash_beneficios}}`.
