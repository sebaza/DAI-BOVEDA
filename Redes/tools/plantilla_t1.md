# DAI Neural — Benchmark T1: continuidad a un año

**Versión:** 0.4 · 16-11-2026 (beneficios estudiantiles de `banner.banner_beneficios`: ablación «+ beneficios», extensión a `k = 4`, diagnóstico de fuga y vista por facultad, §14; la configuración oficial no cambia) · 0.3 · 13-11-2026 (reconstrucción consolidada, etapa B: variables de admisión `mm_*` + prueba) · 0.2 · 12-11-2026 · Fase 4, benchmark T1 con la configuración oficial fijada por las respuestas de la DAI del 12-11-2026 (P49–P52, tercera ronda). Base: `PROMPT_MAESTRO.md` (Predicción experimental, Evaluación, Fase 4; no negociables 4 y 5), `03_reglas_academicas.md`, `05_modelo_datos.md`, `07_diseno_fase3.md`.
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, nota, RUT ni predicción por persona figura en este documento ni en el repositorio.

## Resumen

- **Tarea.** Para un episodio de pregrado vigente al cierre del semestre regular `k` (`k = 1, 2`), ¿sigue matriculado en la UCN dos períodos regulares después? El evento es la **no continuidad observada** (no «deserción»), definida por la DAI como «el estudiante ya no se encuentra matriculado» (P51). Elegibles: 44.116 (`k = 1`) y 28.871 (`k = 2`); con etiqueta observada: 40.572 y 23.310. **Configuración oficial (P49/P50):** train = cohortes 2015–2019 (12.012 y 11.247 filas), valid = 2020–2021, test = 2022–2023 (4.934 filas, 5,7 % de eventos, y 4.719, 10,6 %).
- **Etiqueta.** De los `no_continua` observados, 70,5 % (`k = 1`) y 90,9 % (`k = 2`) tienen un estado de salida explícito (`E`, `B`, `O`…); 25,1 % y 2,2 % son solo ausencia de estados. La ausencia pesa casi toda en las cohortes anteriores a 2014, que la configuración oficial deja fuera del entrenamiento (siguen en el snapshot con su estado).
- **Resultado principal (test, configuración oficial).** El perfil de ingreso solo discrimina poco (AP {{v:o.k1.test.cb_pre.ap}} en `k = 1`, {{v:o.k2.test.cb_pre.ap}}–{{v:o.k2.test.lr_pre.ap}} en `k = 2`; tasa histórica por programa: {{v:o.k1.test.baseline_tasa.ap}} y {{v:o.k2.test.baseline_tasa.ap}}). Al agregar el desempeño académico hasta el corte, el AP sube a {{v:o.k1.test.lr_acad.ap}}–{{v:o.k1.test.cb_acad.ap}} (`k = 1`) y {{v:o.k2.test.gru_seq.ap}}–{{v:o.k2.test.cb_acad.ap}} (`k = 2`), con ROC-AUC {{v:o.k1.test.cb_acad.roc_auc}} y {{v:o.k2.test.cb_acad.roc_auc}} (CatBoost); el 10 % de mayor riesgo contiene una fracción de {{v:o.k1.test.cb_acad.recall_10}} y {{v:o.k2.test.cb_acad.recall_10}} de los eventos (CatBoost, Recall@10 %).
- **La red neuronal no gana.** En test la GRU sobre la secuencia de semestres (AP {{v:o.k1.test.gru_seq.ap}} y {{v:o.k2.test.gru_seq.ap}}) no supera a CatBoost ({{v:o.k1.test.cb_acad.ap}} y {{v:o.k2.test.cb_acad.ap}}): GRU − CatBoost = {{ic:o.k1.test.delta_gru_cb.ap}} y {{ic:o.k2.test.delta_gru_cb.ap}}, **en ambos cortes el intervalo queda bajo cero, es decir, CatBoost supera a la GRU** (con las variables de admisión corregidas; en la versión 0.2 los intervalos incluían el cero). Frente a la logística ({{v:o.k1.test.lr_acad.ap}} y {{v:o.k2.test.lr_acad.ap}}) la GRU solo tiene ventaja en `k = 1` (§5.3). En valid de `k = 2` la GRU ya no supera a CatBoost en AP (§5.3); la comparación válida es la de test. Se conserva **CatBoost con ingreso + agregados**, con la logística como alternativa explicable.
- **Calibración y equidad.** Con el entrenamiento desde 2015 todos los modelos quedan razonablemente calibrados en test (ECE {{v:o.k1.test.cb_acad.ece}}–{{v:o.k1.test.gru_seq.ece}} en `k = 1`, {{v:o.k2.test.cb_acad.ece}}–{{v:o.k2.test.lr_acad.ece}} en `k = 2`); la tabla de equidad por sexo es descriptiva (en `k = 1` el AP de CatBoost es 0,423 en mujeres y 0,315 en hombres en valid y mejor en mujeres también en test; en `k = 2` es equivalente: 0,558 y 0,545).
- **Advertencias.** (i) La señal viene sobre todo del desempeño ya observado, incluidos quienes no tuvieron ramos evaluados en el semestre; no es un sistema de alerta temprana. (ii) Los datos anteriores a 2015 no son utilizables para segundos semestres (P49) y el registro de salidas cambió hacia 2014 (P50): la ventana de entrenamiento oficial es 2015–2019; la DAI buscará registros anteriores y, si los entrega, habrá que repetir el benchmark. (iii) Con 280 y 499 eventos en test, diferencias menores a ≈ 0,03 de AP no son separables.

- **Beneficios (16-11-2026, §14).** Agregar la situación de financiamiento (gratuidad, crédito, becas, mérito de ingreso, banda de decil, expiración de gratuidad, Capstone y, en `k = 4`, la pérdida de un beneficio) **no mejora de forma detectable** el modelo oficial: en `k = 2` el ΔAP pareado de CatBoost es {{b:ic:k2.valid.cb_ben__vs__cb_acad.ap}} en valid y {{b:ic:k2.test.cb_ben__vs__cb_acad.ap}} en test; en `k = 4` con pérdidas es {{b:ic:k4.valid.cb_ben_perd__vs__cb_acad.ap}} en valid. En `k = 1` sube el AP de test ({{b:ic:k1.test.cb_ben__vs__cb_acad.ap}}), pero el diagnóstico de fuga (§14.2) muestra que la vista final de la fuente no es la del cierre del primer semestre (hay filas que se cargan o se retiran después, sobre todo de quienes salen durante el año), por lo que **no se adopta**; sin esas personas la ganancia es {{b:ic:sin_salidas.k1.test.cb_ben__vs__cb_acad.ap}}. `benef_sem2` y `total` se excluyen siempre (se anulan después del cierre). El resultado oficial de `k = 1, 2` y el hash de datos no cambian.

## Cambios de la reconstrucción consolidada (13-11-2026)

La única modificación del lado del modelo en T1 es el perfil de ingreso: `mm_*` + `prueba_admision` reemplazan a los percentiles `pct_*` (P87). Los datos de la etapa A (nombre de facultad, bandas de nota, traslados y estados) no afectan a la etiqueta de T1. Comparación de las métricas de test antes y después (configuración oficial y sensibilidad):

{{cambios}}



Respuestas P49–P52 (`evidencia/respuestas_dai_2026-11-11.md`, «Tercera ronda»; consecuencias en `preguntas_abiertas.md` §J y `00_plan.md` D29–D32).

| Pregunta | Respuesta de la DAI | Consecuencia en este informe |
|---|---|---|
| P49 | Los segundos semestres anteriores a 2015 probablemente nunca se registraron; no pueden usarse. | La regla de cobertura (corte u horizonte en un período `20` anterior a `201520` ⇒ sin cobertura, fuera de modelos) deja de ser provisional (§1, §2). |
| P50 | La forma de registrar las salidas debió de cambiar hacia 2014; la DAI buscará registros anteriores, por ahora se usan los datos tal como están. | **Configuración oficial: entrenar con las cohortes 2015–2019** (valid 2020–2021, test 2022–2023). La corrida con todas las cohortes ≤ 2019 se conserva como sensibilidad (§9). Las filas anteriores a 2015 siguen en el snapshot con su estado, para auditoría. |
| P51 | «No continuidad» = el estudiante ya no se encuentra matriculado. | **Verificado contra la implementación, sin cambios:** `continua` = estado de matrícula, reintegro o cambio de ciclo en el período del horizonte en cualquier programa de la UCN; egreso o titulación hasta el horizonte cuenta como término de ciclo, no como no continuidad. Ninguna etiqueta cambia (§1). |
| P52 | Se pueden excluir las filas que ya tienen un estado de salida en el período del corte. | La exclusión (1.982 filas en `k = 1`, 990 en `k = 2`) queda confirmada (§2). |

## 1. Definición de la tarea

**T1, «continuidad a un año».** Para un episodio de programa de pregrado, ¿la persona sigue vinculada a la UCN un año después del cierre de su semestre `k`? El evento de interés de las métricas es la **no continuidad observada** (`no_continua`). El nombre es deliberado: la ausencia de un estado de matrícula no equivale a deserción definitiva (regla 4 de la especificación); la etiqueta no distingue abandono, pausa no registrada ni salida a otra institución.

| Elemento | Definición |
|---|---|
| Unidad | `episodio_programa` de pregrado. Filtro: `programa.id_nivel = 1` y `cod_admision` fuera de `IN` (intercambio), `PE` (planes especiales) e `IE` (alumno especial). Los planes especiales de titulación (`id_nivel = 8`) se excluyen por nivel. |
| Corte | Fin del `k`-ésimo período **regular** (sufijo `10` o `20`) contado desde el semestre de admisión (`semestre_k` de `neural_mart`, calendario, no «semestres matriculados»). `k = 1` y `k = 2`. Los períodos `15`/`25` (verano/invierno) no son semestres; sus asignaturas cuentan como característica del primer corte posterior (`periodo <= corte`). |
| Elegible | El episodio tiene, en el período del corte, un estado no-reversa de clase `matricula`, `reingreso` o `cambio_ciclo`; **no** está ya egresado/titulado (estado de clase `egreso_titulacion` o fecha de titulación con período `<=` corte); y **no tiene un estado de clase `salida` en el propio período del corte** (adición conservadora, ver §2). |
| Horizonte | El período regular dos períodos regulares después del corte (un año). Es estrictamente posterior al corte. |
| Etiqueta `continua` | La persona tiene, en el período del horizonte, un estado de clase `matricula`, `reingreso`, `cambio_ciclo` o `egreso_titulacion` en **cualquier** programa de la UCN (un cambio real de programa cuenta como continuidad), o alcanzó egreso/titulación hasta el horizonte (estados o tabla de titulaciones). En caso contrario `no_continua`. Verificada contra la definición de la DAI (P51, «ya no se encuentra matriculado»): un estudiante con retiro temporal, interrupción o salida registrada en el horizonte no tiene un estado de matrícula y por eso es `no_continua`; quien egresó o se tituló antes del horizonte terminó el ciclo y no se cuenta como no continuidad. |
| Censura | Si el horizonte es el último período con estados (`202620`, en curso) o posterior, la fila es **censurada**: se conserva en el snapshot con etiqueta NULL y no entra a entrenamiento ni evaluación. |
| Cobertura | Un corte o un horizonte en un período `20` anterior a `201520` queda **sin cobertura** (los estados de segundos semestres anteriores a 2015 están casi ausentes, ver §2): fila conservada con etiqueta NULL, fuera de entrenamiento y evaluación. |
| Etiqueta secundaria | `continua_mismo_programa`: estado de continuidad en el horizonte con el mismo `cod_programa` del episodio, o egreso/titulación del propio episodio. Se calcula y se informa; todavía no se modela. |

**Tipo de no continuidad (regla 4).** Entre los `no_continua`, la fila se rotula `salida` si el episodio tiene un estado de clase `salida` (`E`, `B`, `F`, `O`, `R`, `3`, `9`, `X`, `6`, `H`) entre el período siguiente al corte y el horizonte; `interrupcion` si tiene un estado de clase `interrupcion` (`P`, `Q`, `4`, `A`, `S`, `#`) en ese tramo sin ser `salida`; y `ausencia` si no hay ninguno de los dos (solo falta de estados).

## 2. Población, censura y cobertura (recuentos)

| Paso | k = 1 | k = 2 |
|---|---|---|
| Episodios en `neural_core` | 57.561 | 57.561 |
| − fuera de pregrado (`id_nivel` ≠ 1, planes especiales de titulación) | 235 | 235 |
| − admisión `IN` (1.224), `PE` (60), `IE` (2) | 1.286 | 1.286 |
| **Población T1** | **56.040** | **56.040** |
| − sin estado de matrícula/reintegro/cambio de ciclo en el período del corte | 9.937 | 26.167 |
| − con estado de clase `salida` en el propio período del corte | 1.982 | 990 |
| − ya egresado/titulado al corte | 5 | 12 |
| **Elegibles** | **44.116** | **28.871** |
| − sin cobertura (corte u horizonte en un `20` anterior a `201520`) | 716 | 226 |
| − censuradas (horizonte `>= 202620`) | 2.828 | 5.335 |
| **Observadas (con etiqueta)** | **40.572** | **23.310** |
| de ellas, cohortes 2024 y posteriores (fuera de la ventana de evaluación) | 5.397 | 2.577 |
| de ellas, cohortes ≤ 2014 (en el snapshot, fuera del entrenamiento oficial; P49/P50) | 14.037 | 706 |
| de ellas, usadas (configuración oficial: train desde la cohorte 2015) train / valid / test | 12.012 / 4.192 / 4.934 | 11.247 / 4.061 / 4.719 |

Notas:

- El filtro `IN`/`PE`/`IE` aplica a episodios de nivel 1; los 235 de nivel 8 se cuentan aparte (ver la fila anterior), por eso las dos filas suman menos que el total de exclusiones por admisión.
- **El período `periodo_admision` define la cohorte** (`year` del período; el `20` es la admisión de segundo semestre, 5 % de los episodios).
- **Exclusión «salida en el período del corte» (confirmada por la DAI, P52; no estaba en la especificación original).** Un estado `E`, `B`, `O`… registrado en el mismo período del corte ya es conocido al cierre del semestre; incluir esas filas haría que parte de los `no_continua` fuera trivial (en una primera construcción eran entre 19 % y 36 % de los eventos según la partición). Se excluyen y se cuentan. La pregunta que responde T1 es «¿quién que sigue vigente al cierre del semestre `k` no seguirá un año después?».
- **Cobertura de estados por período.** El número de personas con un estado de matrícula en períodos `10` es estable (8.500–13.900 entre 2008 y 2026), pero en períodos `20` anteriores a 2015 es de unos 740–1.500 (por ejemplo `201220`: 1.196; `201420`: 1.327) frente a 10.459 en `201520` y 11.065 en `201620`. Hasta 2014 el segundo semestre prácticamente no se registra en `ban_estados_academicos` (hallazgo propio; la DAI respondió que probablemente nunca se registraron y que no pueden usarse, P49). Por eso `k = 2` solo tiene datos de entrenamiento desde la cohorte 2015 (las cohortes 2007–2014 aportan 706 filas) y `k = 1` de cohortes de segundo semestre anteriores a 2015 quedan sin cobertura.
- **Cambio de medición alrededor de 2014.** Entre las cohortes 2008–2013 la no continuidad de `k = 1` es 16–29 % y en gran parte sin estado de salida (31–67 % solo ausencia); desde la cohorte 2014 es 4–7 % y 81–100 % con estado explícito. Puede ser un efecto real (hipótesis no verificada: cambios de política de financiamiento o de eliminación) o un cambio en cómo se registran las salidas; con estos datos no se puede separar. La DAI respondió que la forma de registrar las salidas debió de cambiar hacia 2014 y que buscará registros más antiguos (P50); mientras tanto la **configuración oficial entrena solo con cohortes 2015 y posteriores** y la corrida con todas las cohortes ≤ 2019 se informa como sensibilidad (§9).
- Una persona puede tener más de un episodio elegible (4.293 personas con más de una fila en `k = 1`, 2.132 en `k = 2`): el corte, la etiqueta y la división son por episodio, no por persona.

### Salida explícita frente a ausencia (no negociable 4)

Entre las filas observadas (train, valid, test y cohortes 2024+) con `no_continua`:

| | k = 1 | k = 2 |
|---|---|---|
| `no_continua` observados | 4.460 | 2.781 |
| con estado de **salida** explícito | 3.146 (70,5 %) | 2.527 (90,9 %) |
| con estado de **interrupción** (retiro temporal, etc.), sin salida | 193 (4,3 %) | 193 (6,9 %) |
| solo **ausencia** de estados | 1.121 (25,1 %) | 61 (2,2 %) |

Estado de salida que abre la no continuidad (primer estado de clase `salida` tras el corte): `k = 1`: `E` Eliminado 1.590, `O` No Continuidad 814, `B` Renuncia Alumno 741, `X` Expulsado 1; `k = 2`: `E` 1.858, `B` 656, `O` 10, `H` 2, `X` 1. En las cohortes 2016–2024 (`k = 1`) el 98–100 % tiene un estado de salida explícito (salvo 2021: 81 %); la ausencia sin estado se concentra en las cohortes 2008–2013. **Etiqueta secundaria:** de las filas observadas, 13,5 % (`k = 1`) y 16,3 % (`k = 2`) no continúan **en el mismo programa**; la diferencia con `no_continua` son personas que siguen en la UCN en otro programa.

## 3. Snapshot point-in-time (migración 011, `python -m pipelines.snapshots.t1`)

Tablas `neural_mart.snapshot_t1` (una fila por episodio y `k`, 72.987 filas), `snapshot_t1_semestre` (112.080 filas, la entrada del GRU) y `snapshot_t1_resumen` (embudo y hash). Se reconstruyen completas en una transacción.

**Regla de tiempo.** A cada hecho se le asigna un *slot* `j`: `regular(j−1) < periodo <= regular(j)`. Entonces `periodo <= corte(k)` equivale a `slot <= k`. Todas las características de una fila `k` salen de slots `<= k`; la etiqueta, de períodos estrictamente posteriores al corte. Las pruebas lo verifican (hechos añadidos después del corte no cambian ninguna característica; el período de la etiqueta es siempre posterior al corte; las filas censuradas y sin cobertura no tienen etiqueta ni llegan a los modelos).

**Perfil de ingreso** (solo información disponible antes de matricularse): programa, vía de ingreso (`cod_admision` y su clase por `tipo_qualitas`: regular / especial / otros-cambio / otra), sede del programa, año de cohorte, preferencia, tipo y dependencia del colegio, región del colegio, y los puntajes **normalizados** `mm_*` (mínimo–máximo por prueba, año de admisión y campo, de modo que las escalas mezcladas de PSU, PDT y PAES —el `ponderado` llega como 557, 5570 o 55700— queden en [0, 1]) para lenguaje, matemática, ciencias, historia, NEM, ranking, notas de enseñanza media y ponderado, más la variable categórica `prueba_admision` (PSU hasta 2020, PDT 2021–2022, PAES desde 2023: P87). Estos reemplazan a los percentiles `pct_*` de la versión 0.2 (rangos sobre valores en escalas mezcladas). Un puntaje `<= 0` es dato faltante; los faltantes se imputan en el modelo con la mediana de train más un indicador. El `ponderado` solo está informado desde 2017 (51 % faltante en `k = 1`). La normalización usa solo a los postulantes del mismo año y ningún resultado, por lo que no necesita ajustarse con train. La ruta de postulación se vincula al episodio por (persona, programa, período de admisión), prefiriendo la misma vía y la matriculada; 9,7 % de las filas no tiene ruta vinculada (indicador `con_postulacion`).

**Académico hasta el corte:** créditos aprobados acumulados (primera aprobación de cada asignatura, convalidaciones incluidas), intentos evaluados, aprobados, reprobados, tasa de aprobación por intento evaluado (excluye convalidaciones y renuncias), promedio de notas evaluadas con su denominador (excluye `DPA`/convalidaciones), convalidaciones, cursos de verano/invierno, estados de interrupción, cambios de catálogo, semestres matriculados, y los intentos, la tasa y el promedio del último semestre. **Secuencia:** un vector por semestre `1..k` (matriculado, interrupción, intentos, aprobados, reprobados, convalidaciones, créditos, verano/invierno, tasa, promedio, créditos acumulados), con escalas fijas por dominio (sin ajuste).

**Excluido como característica:** `sexo` (decisión M1: se guarda solo como `sexo_equidad` para las tablas de equidad; una prueba impide que entre al modelo); las renuncias de `ban_inscripciones` (solo existen desde 2025, sin cobertura histórica); cualquier estado de salida o de matrícula (el estado en el corte no es característica: la elegibilidad ya lo condiciona); programas y docentes como grafo (fases posteriores).

**Partición por cohorte (`periodo_admision`):** train = cohortes 2015–2019 (configuración oficial, P49/P50; las cohortes ≤ 2014 permanecen en el snapshot con `split = train` pero no se usan para entrenar; ver §9 para la sensibilidad con todas), valid 2020–2021, test 2022–2023, cohortes ≥ 2024 fuera de la evaluación. **Efecto de la pandemia:** valid (2020–2021) coincide con la pandemia y con la tasa de no continuidad más baja de la serie en `k = 1` (4,7 %); test (2022–2023) es el primer retorno presencial. La partición mide generalización a cohortes nuevas bajo un cambio de régimen, no estabilidad dentro de un régimen.

## 4. Protocolo de modelado

Todos los modelos se entrenan por separado para cada `k`. Todo ajuste (medianas, medias, desvíos, vocabularios de categorías, hiperparámetros, parada temprana) usa solo train y valid; test se toca una vez, al final.

| Modelo | Detalle |
|---|---|
| Tasa histórica | Tasa de `no_continua` por (programa, `k`) en train; global si el programa tiene menos de 20 filas. |
| Regresión logística | One-hot de categorías (≥ 30 casos en train; el resto, «otra») + estandarización; `C` ∈ {0,0003 … 10} elegido por AP en valid. `class_weight` balanceado se prueba y se registra, pero no se adopta (ver nota). |
| CatBoost | Categóricas nativas; hasta 1.500 árboles, profundidad 6, tasa 0,05, parada temprana en pérdida logarítmica de valid (ver nota), 3 semillas promediadas. |
| GRU | Secuencia de vectores por semestre → GRU (oculto 48) + embeddings de las categorías de ingreso y numéricas de ingreso (32) → cabeza de 64; AdamW, parada temprana por AP de valid (paciencia 8), 3 semillas promediadas, CUDA. |

*Notas de método (CatBoost y logística).* La primera corrida paró por PRAUC de valid; como valid pertenece a otro régimen, el mejor PRAUC variaba entre 12 y 79 árboles según la semilla y las paradas tempranas dejaban probabilidades mal calibradas (ECE hasta 0,11). Antes de fijar los resultados se cambió a pérdida logarítmica con `boost_from_average`; se amplió además la grilla de `C` de la logística cuyos óptimos caían en el borde, y se dejó de elegir `class_weight = balanced` por AP: en una primera corrida lo elegía en `k = 1` y distorsionaba las probabilidades (ECE hasta 0,27) a cambio de ganancias de AP dentro del ruido. Los resultados de este documento son los de la corrida final; las anteriores se descartaron por estos defectos de calibración visibles también en valid, no por el AP de test (que no cambió de forma material).

**Intervalos y comparaciones.** Cada métrica lleva un IC del 95 % por bootstrap percentil con 1.000 remuestreos de las filas; todos los modelos usan los **mismos** remuestreos, de modo que las diferencias pareadas son válidas. Las métricas de CatBoost y GRU usan el promedio de las 3 semillas (la variabilidad entre semillas se informa aparte). Recall@10 % y Precision@10 % consideran el 10 % de filas con mayor riesgo (empates por posición). ECE: 10 grupos de igual tamaño por rango de riesgo (los empates comparten grupo).

## 5. Resultados de la configuración oficial (train 2015–2019, valid 2020–2021, test 2022–2023)

Todas las cifras son agregados sobre cohortes completas; ninguna fila individual sale de la base de desarrollo. Evento = `no_continua`. Configuración oficial (P49/P50): entrenamiento con cohortes 2015–2019; la sensibilidad con todas las cohortes ≤ 2019 está en §9. «Ingreso + agregados» usa el perfil de ingreso y las características académicas al corte; «GRU» usa el perfil de ingreso y la secuencia de semestres (los agregados no entran a la GRU de forma separada; ver §4). Los intervalos son del 95 % por bootstrap (1.000 remuestreos).

### 5.1 k = 1 (corte: primer semestre regular; horizonte: tercer período regular)

Tamaños — train (cohortes 2015–2019): n = 12.012, eventos = 754 (6,3 %); valid: n = 4.192, eventos = 197 (4,7 %); test: n = 4.934, eventos = 280 (5,7 %).

**Test**

{{o.k1.test}}

**Diferencias pareadas en test** (mismos remuestreos para todos los modelos)

{{o.k1.delta_test}}

**Valid**

{{o.k1.valid}}

**Variabilidad entre semillas (test)**

{{o.k1.semillas}}

### 5.2 k = 2 (corte: segundo semestre regular; horizonte: cuarto período regular)

Tamaños — train (cohortes 2015–2019): n = 11.247, eventos = 1.480 (13,2 %); valid: n = 4.061, eventos = 464 (11,4 %); test: n = 4.719, eventos = 499 (10,6 %).

**Test**

{{o.k2.test}}

**Diferencias pareadas en test**

{{o.k2.delta_test}}

**Valid**

{{o.k2.valid}}

**Variabilidad entre semillas (test)**

{{o.k2.semillas}}

### 5.3 Los tres modelos «ingreso + agregados/secuencia» entre sí

Diferencias pareadas (bootstrap de 1.000 remuestreos sobre las mismas filas), configuración oficial. `tools/pares_t1.py`.

**k = 1**

*test*

{{pares.o.k1.test}}

*valid*

{{pares.o.k1.valid}}


**k = 2**

*test*

{{pares.o.k2.test}}

*valid*

{{pares.o.k2.valid}}

**Lectura.** En test, en ningún `k` la GRU supera a CatBoost en AP, y ahora CatBoost la supera con el intervalo pareado bajo cero (−0,030 [−0,051; −0,008] en `k = 1`; −0,026 [−0,042; −0,007] en `k = 2`; en la versión 0.2 los intervalos incluían el cero). En `k = 1` CatBoost supera a la logística en test (+0,054 [+0,030; +0,075]) y la GRU también (+0,023 [+0,007; +0,039]); en `k = 2` los tres modelos no se distinguen en AP (CatBoost − logística +0,014 [−0,009; +0,036]; GRU − logística −0,011 [−0,029; +0,009]). **Valid de `k = 2`:** la GRU ya no supera a CatBoost en AP (+0,015 [−0,004; +0,032]; ΔROC-AUC +0,020 [+0,011; +0,031]) ni a la logística (+0,009 [−0,005; +0,023]); la excepción que mostraba la versión 0.2 desaparece. Valid es el período de pandemia y se usa para detener el entrenamiento, de modo que su ranking de modelos no se toma como evidencia; test es la comparación válida. Con 280 y 499 eventos en test los intervalos son anchos: las diferencias de unas pocas centésimas no se pueden separar.

## 6. Ablación (mismo horizonte y población en cada escalón)

Test, configuración oficial. El perfil de ingreso solo mejora poco a la tasa histórica por programa (AP {{v:o.k1.test.cb_pre.ap}} y {{v:o.k2.test.lr_pre.ap}} frente a {{v:o.k1.test.baseline_tasa.ap}} y {{v:o.k2.test.baseline_tasa.ap}}); casi toda la ganancia aparece al agregar el desempeño académico hasta el corte; la secuencia por semestre no agrega a los agregados.

**k = 1**

{{o.k1.ablacion}}

**k = 2**

{{o.k2.ablacion}}

La tasa histórica (programa, `k`) es el escalón cero: AP {{ic:o.k1.test.baseline_tasa.ap}} en `k = 1` y {{ic:o.k2.test.baseline_tasa.ap}} en `k = 2`.

**Dónde está la señal.** El resumen académico identifica sobre todo a quienes **no tuvieron ningún ramo evaluado en el semestre `k`** (sin notas: ausentes de hecho pese a figurar vigentes). En test (CatBoost, `tools/subpoblacion_t1.py`):

{{subpoblacion}}

Entre quienes sí tuvieron ramos evaluados el modelo sigue ordenando (AP 0,32 sobre una tasa de 4,3 % en `k = 1`; 0,34 sobre 6,1 % en `k = 2`), pero con una señal bastante más modesta que el agregado.

## 7. Calibración

Tabla de confiabilidad por deciles de riesgo en test (predicho medio / tasa observada, n por decil). ECE: 10 grupos de igual tamaño.

**k = 1**

{{o.k1.calibracion}}

**k = 2**

{{o.k2.calibracion}}

La tasa histórica (programa, `k`) es la referencia sin discriminación. Con la configuración oficial los cuatro modelos de `k = 1` quedan con ECE de {{v:o.k1.test.lr_acad.ece}} a {{v:o.k1.test.gru_seq.ece}} (tasa histórica {{v:o.k1.test.baseline_tasa.ece}}); los tres modelos con agregados subestiman algo el decil 9 (predicho 0,07–0,10 frente a 0,10–0,14 observado) y quedan cerca en el decil de mayor riesgo (predicho 0,25–0,29 frente a 0,27–0,32). En `k = 2` el ECE va de {{v:o.k2.test.cb_acad.ece}} (CatBoost) a {{v:o.k2.test.lr_acad.ece}} (logística y GRU); CatBoost sobreestima los cinco deciles de menor riesgo (predicho 0,03–0,04 frente a 0,004–0,017 observado), con un efecto pequeño en términos absolutos. Con todas las cohortes ≤ 2019 la calibración de la tasa histórica, la logística y la GRU en `k = 1` era peor (ECE 0,070, 0,033 y 0,032; §9): el train incluía cohortes con 16–29 % de no continuidad y test tiene 5,7 %.

## 8. Subgrupos y equidad (test; descriptivo)

Las tablas por subgrupo usan el modelo conservado (CatBoost, ingreso + agregados). Grupos con n < 100 (programa) o n < 30 se omiten; con 100–300 filas por programa y pocos eventos, las cifras por programa son ruidosas y solo describen. `sexo` no es una característica del modelo: se usa únicamente para estas tablas.

### 8.1 Por sexo

Tasa observada, AP y brechas F − M para cada modelo. Las brechas de calibración son riesgo medio − tasa observada, restadas entre grupos.

**k = 1**

{{o.k1.sexo}}

**k = 2**

{{o.k2.sexo}}

**Lectura.** Las tasas observadas de F y M son parecidas en `k = 1` (5,9 % y 5,5 %) y algo distintas en `k = 2` (9,7 % y 11,3 %). En `k = 1` el modelo ordena mejor a las mujeres (AP 0,423 frente a 0,315 con CatBoost en valid; Recall@10 % +0,084), con una diferencia de brechas de calibración F − M pequeña (−0,010); en `k = 2` el AP es equivalente (0,558 frente a 0,545), el Recall@10 % de las mujeres es 0,09 mayor y la diferencia de brechas de calibración F − M es −0,012. Son diferencias descriptivas, sin intervalos y sin análisis causal; que `sexo` no entre al modelo no impide que otras variables (programa, colegio) lo representen parcialmente.

### 8.2 Por cohorte

**k = 1**

{{o.k1.cohorte}}

**k = 2**

{{o.k2.cohorte}}

### 8.3 Por vía de ingreso

**k = 1**

{{o.k1.via}}

**k = 2**

{{o.k2.via}}

Las vías «otros_cambio» (cambio de carrera, traslado, etc.) tienen tasas de no continuidad muy bajas (1,9 % en `k = 1`), de modo que su AP es bajo aunque el ROC-AUC sea comparable.

### 8.4 Por programa (n ≥ 100 en test)

**k = 1**

{{o.k1.programa}}

**k = 2**

{{o.k2.programa}}

## 9. Sensibilidad: entrenar con todas las cohortes ≤ 2019 (sin la ventana de la DAI)

Antes de las respuestas P49/P50 la partición principal entrenaba con todas las cohortes ≤ 2019. Esa configuración se conserva como sensibilidad (`--todos-los-anios`), con el mismo valid y test. En `k = 2` casi no cambia (el train gana 706 filas); en `k = 1` el train pasa de 12.012 filas (754 eventos, 6,3 %) a 26.049 (3.760 eventos, 14,4 %), porque las cohortes 2008–2013 tienen 16–29 % de no continuidad con mucha ausencia de estados (§2).

**k = 1 (test)**

{{s.k1.test}}

{{s.k1.delta_test}}

**k = 2 (test)**

{{s.k2.test}}

Diferencias pareadas entre los tres modelos con train de todas las cohortes ≤ 2019:

**k = 1**

*test*

{{pares.s.k1.test}}

*valid*

{{pares.s.k1.valid}}

**k = 2**

*test*

{{pares.s.k2.test}}

*valid*

{{pares.s.k2.valid}}

**Lectura.** (i) La calibración en `k = 1` es peor con todas las cohortes (ECE tasa histórica {{v:s.k1.test.baseline_tasa.ece}}, logística {{v:s.k1.test.lr_acad.ece}}, GRU {{v:s.k1.test.gru_seq.ece}}; con la ventana oficial {{v:o.k1.test.baseline_tasa.ece}}, {{v:o.k1.test.lr_acad.ece}} y {{v:o.k1.test.gru_seq.ece}}); en `k = 2` la diferencia es pequeña y mixta (logística {{v:s.k2.test.lr_acad.ece}} con todas frente a {{v:o.k2.test.lr_acad.ece}} con la ventana oficial; CatBoost {{v:s.k2.test.cb_acad.ece}} frente a {{v:o.k2.test.cb_acad.ece}}). (ii) El AP de los modelos con agregados cambia poco: `k = 1`, logística {{v:s.k1.test.lr_acad.ap}} → {{v:o.k1.test.lr_acad.ap}}, CatBoost {{v:s.k1.test.cb_acad.ap}} → {{v:o.k1.test.cb_acad.ap}}, GRU {{v:s.k1.test.gru_seq.ap}} → {{v:o.k1.test.gru_seq.ap}}; `k = 2`, {{v:s.k2.test.lr_acad.ap}} → {{v:o.k2.test.lr_acad.ap}}, {{v:s.k2.test.cb_acad.ap}} → {{v:o.k2.test.cb_acad.ap}} y {{v:s.k2.test.gru_seq.ap}} → {{v:o.k2.test.gru_seq.ap}} (todas las cohortes → ventana oficial). (iii) El orden de los modelos es más claro con la ventana oficial en `k = 1` (CatBoost − logística +0,054 [+0,030; +0,075] frente a +0,017 [−0,002; +0,032] con todas las cohortes), y la GRU no supera a CatBoost en test en ninguna de las dos configuraciones (con la ventana oficial el intervalo queda bajo cero; con todas las cohortes incluye el cero). Las conclusiones de la recomendación (§12) no dependen de la ventana de entrenamiento; la calibración sí, por lo que la configuración oficial es la de la DAI.

## 10. Tiempo y memoria

Entrenamiento y evaluación en una máquina de 32 hilos, 16 GB de RAM y una RTX 4060 de 8 GB. Cada corrida completa (dos `k`, 3 semillas por modelo y 1.000 remuestreos de bootstrap) tarda unos 5–6 minutos; la oficial y la sensibilidad suman unos 12 minutos.

**k = 1 (configuración oficial)**

{{o.k1.tiempos}}

**k = 2 (configuración oficial)**

{{o.k2.tiempos}}

La GRU (16.500–16.600 parámetros) entrena en pocos segundos por semilla y usa 47–61 MB de memoria GPU como máximo: el costo computacional no es el motivo para descartarla. CatBoost corre en CPU (16 hilos). Los tiempos de la logística incluyen la búsqueda en la grilla (10 valores de `C` × 2 pesos).

## 11. Limitaciones

1. **La etiqueta es «no continuidad observada», no deserción (la DAI la define como «ya no se encuentra matriculado», P51).** Incluye abandono sin registro, retiro no formalizado, traslado a otra institución y errores de registro; la etiqueta secundaria (mismo programa) muestra que 13,5 % (`k = 1`) y 16,3 % (`k = 2`) de las filas observadas dejan el programa, y una parte de ellas sigue en la UCN.
2. **Cambio de régimen y de medición.** Valid (2020–2021) coincide con la pandemia; el período anterior a 2014 tiene tasas de no continuidad 3–4 veces mayores y, en buena parte, sin estado de salida explícito (la DAI cree que la forma de registrar las salidas cambió hacia 2014, P50); los segundos semestres anteriores a 2015 probablemente nunca se registraron (P49). La configuración oficial entrena desde 2015, pero eso deja solo 5 cohortes de entrenamiento y los modelos se evalúan bajo un cambio de régimen, no dentro de uno estable. Si la DAI entrega registros más antiguos hay que repetir el benchmark.
3. **Tamaños.** `k = 1` tiene 197 eventos en valid y 280 en test (754 en train); los intervalos son anchos y la parada temprana sobre valid es ruidosa (la GRU de `k = 1` para en la época 4 a 12 según la semilla). No hay evidencia suficiente para ordenar modelos que difieren en menos de ≈ 0,03 de AP.
4. **Personas con varios episodios.** La unidad es el episodio; el bootstrap y las particiones son por fila/cohorte, no por persona. Hay personas con filas en más de una partición (por ejemplo un reingreso en otra carrera), lo que puede dar un optimismo pequeño.
5. **Asignación de ramos a episodios.** Las características usan solo ramos con período `<=` corte, pero la asignación de cada ramo a su episodio (`intento_asignatura.episodio_id`) se calcula en `neural_core` con la historia completa, no reconstruida punto en el tiempo; el 30,3 % de los intentos del núcleo no tiene episodio (801.181 sin episodio y 8.997 ambiguos) y no entra a las características.
6. **Datos de ingreso incompletos.** `ponderado` falta en 51 % de las filas de `k = 1` (solo informado desde 2017) y en 9,7 % no hay ruta de postulación vinculada. Se imputan con la mediana de train más un indicador; la normalización `mm_*` usa a todos los postulantes del año.
7. **La señal es mayormente un resumen del desempeño ya observado** (§6): sirve para ordenar a quienes ya cerraron el semestre, no para anticiparse. Un uso preventivo requeriría un corte anterior (a mitad del semestre) que estos datos no permiten.
8. **Selección de modelos con valid y parada temprana sobre valid:** las métricas de valid son optimistas; la comparación válida es la de test.
9. **No evaluado todavía:** modelos de supervivencia y tiempo hasta el evento, `k ≥ 3`, embeddings de curso, prerrequisitos y GNN, contexto docente, encuestas, ensamble, eliminación/egreso como objetivos separados. La etiqueta secundaria (mismo programa) solo se calcula.
10. **Equidad solo descriptiva:** las tablas por sexo y por programa no tienen intervalos ni ajuste; no justifican por sí mismas ninguna decisión.

## 12. Recomendación

1. **Modelo conservado para T1: CatBoost con perfil de ingreso + agregados académicos** (mayor AP puntual en test en `k = 1` y en `k = 2`, con calibración igual o mejor; §5 y §9), **con la regresión logística como alternativa explicable**: en `k = 2` las diferencias entre ambos no son separables y en `k = 1` CatBoost supera a la logística por +0,054 de AP. **La GRU no supera a CatBoost en test en ningún `k` ni en ninguna configuración de entrenamiento** (con la ventana oficial CatBoost la supera: −0,030 y −0,026 de ΔAP con el intervalo bajo cero); su única ventaja es sobre la logística en `k = 1` (+0,023). Se descarta para T1 por una complejidad mayor sin ganancia confirmada; los grafos y los embeddings de curso no se justifican con esta evidencia.
2. **Entrenar desde las cohortes 2015** (decisión de la DAI, P49/P50) y repetir el benchmark si la DAI entrega registros anteriores de salidas o de segundos semestres.
3. **No publicar predicciones individuales.** Quedan fuera de la API y de la Bóveda (bandera apagada por omisión); este informe no autoriza su uso en decisiones sobre personas. **Gate 4: el benchmark técnico está completo y la definición operativa de «no continuidad» ya está acordada con la DAI (P51); queda pendiente la revisión institucional y la aprobación del uso**, junto con un plan de monitoreo de deriva y equidad. Ningún riesgo estimado puede automatizar la selección ni la exclusión de postulantes.
4. **Próximos experimentos** (en este orden): supervivencia (tiempo hasta la salida) con censura; `k = 3, 4`; objetivo separado de salida explícita; solo después, características de curso y prerrequisitos bajo la misma ablación.

## 13. Reproducibilidad

- Datos: `neural_mart.snapshot_t1` (hash `{{meta:snapshot_hash}}`, registrado en `snapshot_t1_resumen`). Código: sha256 de los fuentes de `models/`, `evaluation/` y de las reglas del snapshot, guardado como etiqueta de cada corrida de MLflow (`{{meta:version_codigo}}`).
- Cada modelo y cada `k` es una corrida de MLflow (almacén local `mlruns/`, experimento `t1_continuidad_1_anio`) con parámetros, métricas de valid y test con IC, tiempos, memoria GPU, hash de los datos y versión del código. Los JSON agregados y las predicciones están en `artefactos/` (ignorado por git).
- Comandos: ver `README.md` (sección «Snapshots y benchmark T1»). Configuración oficial: `python -m evaluation.run_benchmark` (por omisión `--k 1 2 --train-desde 2015`, artefacto `resultados_t1.json`); sensibilidad: `python -m evaluation.run_benchmark --todos-los-anios` (artefacto `resultados_t1_todos_anios.json`). Este documento se genera con `python tools/informe_t1.py --doc` a partir de `tools/plantilla_t1.md` y de los JSON agregados. Semillas: 0, 1, 2 para CatBoost y GRU; 7 para el bootstrap (11 en `tools/pares_t1.py`).
- Pruebas (en el entorno de ML): reglas de corte/horizonte/slot/cobertura/división, elegibilidad, etiqueta, censura, ausencia de fugas (hechos posteriores al corte no cambian las características), preprocesamiento ajustado solo en train, exclusión de `sexo`, métricas, calibración, bootstrap, subgrupos, GRU, y 7 invariantes del snapshot en la base.

## 14. Beneficios (16-11-2026)

**Qué se probó.** Se agregó a la tarea T1 la situación de financiamiento de cada estudiante (`banner.banner_beneficios`, una fila por año, persona, carrera, beneficio y cobertura; el campo `periodo` es el **año**), con la regla de la DAI del 16-11-2026: los beneficios se asignan por año; si una persona tiene un beneficio en el año *t* y no en *t* + 1, lo **perdió**. La configuración oficial de T1 (`k = 1, 2`, entrenamiento desde 2015, mismos modelos, semillas y particiones) **no cambia**: el hash de datos de las filas oficiales es el mismo de antes (`{{meta:snapshot_hash}}`) y el reentrenamiento del modelo sin beneficios reproduce la corrida oficial (§14.3). Decisiones D90–D95 (`00_plan.md`).

### 14.1 Variables y punto en el tiempo

| Variable | Definición |
|---|---|
| `tiene_gratuidad`, `tiene_credito`, `tiene_beca_estatal`, `tiene_beca_ucn` | Existe una fila de la familia en el **año del corte** y en el **programa del episodio**. Gratuidad: Gratuidad Confirmada (AB y AC) y Gratuidad UCN; crédito: FSCU y CAE; beca estatal: códigos `BG_*`; beca UCN: códigos `BI_*` (incluye el aporte UCN). |
| `merito_ingreso`, `merito_e1` | 0, 70, 75 u 85 según «Beneficio por Posicionamiento» (el mayor del año); «E1» se marca aparte porque es una categoría y no un porcentaje. |
| `banda_decil` | `<=6` si tiene gratuidad; `7` u `8-9` si tiene «Rebaja Arancel Decil»; `desconocida` en otro caso. Es una variable socioeconómica del hogar: se usa como variable y se informa la equidad por banda (§14.7). |
| `expiro_gratuidad` | 0, 1 o 2: «Expiración de gratuidad N+1 / N+2» (superó la duración formal). |
| `etapa_capstone` | «Ajuste de deuda Capstone». |
| `n_beneficios`, `monto_sem1` | Cantidad de filas del año y suma de `benef_sem1` (primer semestre). |
| `ben_sin_dato`, `perdida_sin_dato` | Indicadores de dato desconocido: los años anteriores a 2017 no existen en la fuente, de modo que las variables quedan **desconocidas (NaN), no 0**; en la logística se imputan con la mediana de train más un indicador. |
| `perdio_gratuidad`, `perdio_credito`, `perdio_cualquier_beneficio`, `obtuvo_gratuidad` | Cambio entre el año *t* − 1 y el año del corte *t*. **Solo existen en `k = 4`**; en `k = 1, 2` no se definen (el corte cae en el año de ingreso, donde no hay «año anterior»). |

Reglas de punto en el tiempo: (1) las variables de un corte usan únicamente el **año calendario del período de corte**, nunca el siguiente: la ausencia de un beneficio en *t* + 1 está ligada mecánicamente a no matricularse en *t* + 1 y filtraría la etiqueta; (2) un beneficio de **otro programa** distinto del episodio no cuenta (0,7 % de las filas: 148 de 21.703 en `k = 1`); (3) **`benef_sem2` y `total` no son variables** (§14.2): la prueba de perturbación de las pruebas unitarias confirma que cambiar el segundo semestre, los años posteriores o los beneficios de otras personas y programas no altera ninguna variable del corte.

### 14.2 Diagnóstico de fuga

**a) Presencia del beneficio según el resultado** (año del corte, mismo programa; solo las filas con etiqueta observada de las cohortes con dato):

{{ben.diag_presencia}}

En el segundo semestre la brecha del monto es más del doble que la del primer semestre (`k = 2`: 13,2 frente a 5,2 puntos; `k = 4`: 11,6 frente a 3,3): el monto del segundo semestre reacciona a la salida.

**b) Quienes salen durante el año de ingreso** (ingresaron en el primer semestre y no están matriculados en el segundo; solo `k = 1`):

{{ben.diag_salida_anio}}

Casi no tienen filas de beneficio en la vista final (4 % frente a 74 %), y son una de cada cinco no continuidades de `k = 1`.

**c) Historial de cargas del almacén** (`banner_beneficios_full`, solo conteos). El corte de `k = 1` es el fin del primer semestre (julio); el cierre del año es noviembre:

{{ben.diag_historia}}

Las filas del año se siguen cargando después del fin del primer semestre y una parte se retira más tarde; **los montos del segundo semestre se anulan después del cierre para el 2,8 % de las filas**. ¿Las filas retiradas son de quienes luego no continúan?

{{ben.diag_retiradas}}

**Conclusión del diagnóstico (D92).** (i) `benef_sem2` y `total` se **excluyen en todos los cortes** (también en `k = 2`): se anulan después del cierre y su brecha por resultado duplica la del primer semestre; el modelo los rechaza (`FORBIDDEN`). (ii) En `k = 1` la vista final **no es la del corte**: entre 5 % y 11 % de las filas no estaban cargadas en julio, una parte se retira después y quienes salen durante el año casi no tienen filas. Por eso en `k = 1` los modelos con beneficios **no son elegibles**; sus resultados se informan como sensibilidad (§14.3, §14.8). (iii) En `k = 2` y `k = 4` el corte es el cierre del año y la vista final difiere poco de la del cierre (cambio neto de filas de 0,3 % a 0,6 %, con una rotación bruta de 1 % a 2 %): se usan, con esa salvedad.

### 14.3 `k = 1` y `k = 2`: antes → después de agregar beneficios

Mismos modelos (CatBoost con 3 semillas y logística con C elegido en valid), mismas semillas, particiones y ventana de entrenamiento oficial (cohortes desde 2015); el IC de 95 % y las diferencias pareadas usan un bootstrap agrupado por persona con los **mismos** remuestreos para todos los modelos. El escalón nuevo es «+ beneficios» sobre el mejor conjunto (`pre_entry+academico`). Las cohortes 2015 y 2016 del entrenamiento no tienen datos de beneficios (la fuente empieza en 2017): 40 % de las filas de entrenamiento de `k = 1` y de `k = 2` tienen las variables desconocidas (NaN) con su indicador.

**Reproducción.** El reentrenamiento sin beneficios de esta corrida reproduce la corrida oficial (AP de test):

{{ben.k1.reproduccion}}

{{ben.k2.reproduccion}}

**`k = 1`** ({{ben.k1.n}}).

{{ben.k1.antes_despues}}

Diferencias pareadas, valid:

{{ben.k1.delta_valid}}

Diferencias pareadas, test:

{{ben.k1.delta_test}}

{{ben.k1.seleccion}}

**Lectura de `k = 1`.** En test los beneficios suben el AP de CatBoost de {{b:v:k1.test.cb_acad.ap}} a {{b:v:k1.test.cb_ben.ap}} (ΔAP {{b:ic:k1.test.cb_ben__vs__cb_acad.ap}}) y el de la logística de {{b:v:k1.test.lr_acad.ap}} a {{b:v:k1.test.lr_ben.ap}} (ΔAP {{b:ic:k1.test.lr_ben__vs__lr_acad.ap}}), pero **no se adopta**: en valid la diferencia de CatBoost incluye el cero ({{b:ic:k1.valid.cb_ben__vs__cb_acad.ap}}) y, sobre todo, el diagnóstico (§14.2) muestra que en este corte la vista final de los beneficios no es la que existía al cierre del primer semestre. Cuánto de la ganancia viene de quienes salen durante el año de ingreso se acota en §14.8.

**`k = 2`** ({{ben.k2.n}}).

{{ben.k2.antes_despues}}

Diferencias pareadas, valid:

{{ben.k2.delta_valid}}

Diferencias pareadas, test:

{{ben.k2.delta_test}}

{{ben.k2.seleccion}}

**Lectura de `k = 2`.** Los beneficios **no mejoran** el desempeño de forma detectable: la diferencia pareada de valid incluye el cero en ambos modelos (CatBoost {{b:ic:k2.valid.cb_ben__vs__cb_acad.ap}}; logística {{b:ic:k2.valid.lr_ben__vs__lr_acad.ap}}) y en test la de CatBoost es {{b:ic:k2.test.cb_ben__vs__cb_acad.ap}} y la de la logística {{b:ic:k2.test.lr_ben__vs__lr_acad.ap}}. No se cumple el criterio del plan de mejora (ΔAP > 0 con IC que excluya 0 en valid), de modo que **ningún modelo con beneficios es elegible**. Entre los modelos sin beneficios, la regla «mayor AP de valid» queda con la logística ({{b:v:k2.valid.lr_acad.ap}} frente a {{b:v:k2.valid.cb_acad.ap}} de CatBoost); la recomendación oficial (§12) los mantiene equivalentes en test.

### 14.4 Extensión secundaria a `k = 4` (fin del segundo año; D91)

Mismo evento (no continuidad en el período regular dos períodos después del corte), mismas particiones por cohorte y misma ventana de entrenamiento; el corte es el cuarto período regular desde el ingreso, igual que `k = 4` de T3 y de T4/T5. Es la única posición donde la pérdida de un beneficio entre el año 1 y el año 2 se puede probar sin usar el año del resultado. Elegibles: 23.614 episodios (1.039 con salida en el corte y 24 ya egresados quedan fuera); con etiqueta observada y partición: {{ben.k4.n}}. En el entrenamiento, 18 % de las filas no tienen beneficios del año del corte (cohorte 2015) y 38 % no tienen el año anterior (pérdida desconocida).

{{ben.k4.test}}

Diferencias pareadas, valid:

{{ben.k4.delta_valid}}

Diferencias pareadas, test:

{{ben.k4.delta_test}}

{{ben.k4.seleccion}}

**Lectura.** Con beneficios y sin pérdida el AP no mejora (CatBoost {{b:ic:k4.valid.cb_ben__vs__cb_acad.ap}} en valid y {{b:ic:k4.test.cb_ben__vs__cb_acad.ap}} en test). Agregar la **pérdida de beneficios** sube el AP de CatBoost sobre el modelo con beneficios en valid ({{b:ic:k4.valid.cb_ben_perd__vs__cb_ben.ap}}), pero frente al modelo sin ningún beneficio la diferencia es nula ({{b:ic:k4.valid.cb_ben_perd__vs__cb_acad.ap}} en valid; {{b:ic:k4.test.cb_ben_perd__vs__cb_acad.ap}} en test). La asociación observada en el perfil general de 2018-2024 (73 % de continuidad entre quienes perdieron la gratuidad frente a 95 % entre quienes la mantienen) es real, pero **no agrega señal sobre las variables académicas** del cierre del segundo año: una explicación plausible es que quienes pierden la gratuidad por superar la duración formal ya muestran el atraso en sus créditos y notas (no se probó).

### 14.5 Importancia de las variables de beneficios (solo agregados)

`k = 1` (sensibilidad):

{{ben.k1.importancia.cb_ben}}

`k = 2`:

{{ben.k2.importancia.cb_ben}}

`k = 4`, con pérdidas:

{{ben.k4.importancia.cb_ben_perd}}

Las variables académicas del último semestre dominan en todos los cortes; los beneficios aportan una fracción pequeña de la importancia total.

### 14.6 Resultados por programa y por facultad (modelo conservado; prueba)

T1 no tenía vista por facultad; se agrega con el mismo método de T4 y T5 (pronóstico agregado: tasa observada y riesgo medio del grupo con IC del bootstrap agrupado por persona; solo grupos con n ≥ 100 y al menos 10 eventos). Los nombres de facultad salen de `common.facultad_d` (D82).

**`k = 1`, por facultad**

{{ben.k1.facultad}}

**`k = 1`, por programa**

{{ben.k1.programa}}

**`k = 2`, por facultad**

{{ben.k2.facultad}}

**`k = 2`, por programa**

{{ben.k2.programa}}

**`k = 4`, por facultad**

{{ben.k4.facultad}}

**`k = 4`, por programa**

{{ben.k4.programa}}

### 14.7 Equidad por banda de decil y por sexo (modelo conservado frente a CatBoost sin beneficios; prueba)

`banda_decil` es una variable socioeconómica del hogar (gratuidad ⇒ decil 6 o menos; «Rebaja por decil» ⇒ 7 u 8-9; el resto, desconocida). Se puede usar como variable porque no es un atributo protegido de la especificación, y **se informa su equidad de forma descriptiva** (sin IC ni ajuste; solo grupos de 30 filas o más). `sexo` se usa solo aquí, nunca como variable.

**`k = 1`**

{{ben.k1.equidad_banda}}

{{ben.k1.equidad_sexo}}

**`k = 2`**

{{ben.k2.equidad_banda}}

{{ben.k2.equidad_sexo}}

**`k = 4`**

{{ben.k4.equidad_banda}}

{{ben.k4.equidad_sexo}}

### 14.8 Sensibilidades

**Sin las personas que salen durante el año de ingreso** (`k = 1`; se excluyen de entrenamiento, valid y test quienes no están matriculados en el segundo semestre; así el sesgo de §14.2 b no actúa):

{{ben.sens_sin_salidas}}

Con la configuración oficial completa, la ganancia de CatBoost en test es {{b:ic:k1.test.cb_ben__vs__cb_acad.ap}}; sin esas personas baja a {{b:ic:sin_salidas.k1.test.cb_ben__vs__cb_acad.ap}}, es decir, más de la mitad de la ganancia aparente de `k = 1` desaparece cuando se quita un efecto que no sería observable al cierre del semestre.

**Entrenar solo con cohortes desde 2017** (todas con datos de beneficios; entrenamiento más pequeño):

{{ben.sens_2017}}

### 14.9 Conclusión y límites

1. **Configuración oficial de T1 (`k = 1` y `k = 2`): sin cambios.** Los beneficios no cumplen el criterio de adopción en ningún corte: en `k = 1` el corte es a mitad de año y la vista final de la fuente no es la del corte (no elegibles), y en `k = 2` y `k = 4` la diferencia pareada de valid incluye el cero. T1 sigue con ingreso + agregados académicos (CatBoost, con la logística como alternativa).
2. **Dónde está el valor de los beneficios.** Para ordenar a quienes ya cerraron el semestre, el desempeño académico explica casi todo. Los beneficios describen **con quién** se está hablando (gratuidad, decil, crédito) y sirven como descripción y equidad (§14.7), no como señal adicional de continuidad.
3. **Lo que falta para volver a probarlos.** La fecha en que la fuente registra la asignación o el retiro de un beneficio (P90), por qué se retiran filas durante el año (P91) y un historial de cargas anterior a 2024 (P93). Con la vista de cada corte tal como existía, `k = 1` se podría evaluar de forma limpia y también un corte a mitad de semestre.
4. **Límites.** Los años anteriores a 2017 no tienen datos (las cohortes 2015-2016 quedan con beneficios desconocidos); las variables dependen de la clasificación por código y 12 códigos (aportes externos y ajustes de deuda) solo cuentan en `n_beneficios`; un beneficio de otro programa en el mismo año se ignora; la pérdida de beneficios solo existe en `k = 4`; con 244 eventos en la prueba de `k = 4` diferencias menores que 0,03 de AP no son separables.
