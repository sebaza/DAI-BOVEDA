# DAI Neural — Benchmark T3: tiempo hasta titulación

**Versión:** 0.6 · 18-11-2026 (variables nuevas, §12: sin cambio en el modelo conservado; causa de los totales de créditos atípicos, P126) · 0.5 · 16-11-2026 (modelo conservado por la regla única de selección en validación, §9, D114) · 0.4 · 16-11-2026 (beneficios estudiantiles, §11: sin cambios en el modelo oficial) · 0.3 · 13-11-2026 (reconstrucción consolidada, etapa B: variables de admisión `mm_*` + prueba) · 0.2 · 12-11-2026 · Fase 4, benchmark T3, **con la población de D47** (Programa de Intercambio fuera; Ingeniería Civil Plan Común unido a su especialidad). Reemplaza a la v0.1 (D45), que usaba la población de D40; las cifras de D45 ya no rigen. Base: `PROMPT_MAESTRO.md` (Predicción experimental, Evaluación, Fase 4; no negociable 5), `03_reglas_academicas.md`, `05_modelo_datos.md`, `08_benchmark_t1.md` y `09_benchmark_t2.md` (misma estructura, estándar y herramientas).
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, RUT ni predicción por persona figura en este documento ni en el repositorio. Los grupos con menos de 10 episodios no se publican.

## Cambios de la reconstrucción consolidada (13-11-2026)

Cambio del lado del modelo: el perfil de ingreso usa los puntajes normalizados `mm_*` y la variable `prueba_admision` en lugar de los percentiles `pct_*` (P87). La población y el evento no cambian. Antes y después (test, IC 95 %):

| Métrica | Antes | Después | Cambio |
|---|---|---|---|
| k = 2: IBS de test, Aalen–Johansen por programa | 0,0606 [0,0578; 0,0636] | 0,0606 [0,0578; 0,0636] | +0,0000 |
| k = 2: IBS de test, Cox causa-específico (ingreso + agregados) | 0,0473 [0,0451; 0,0497] | 0,0472 [0,0450; 0,0496] | -0,0001 |
| k = 2: IBS de test, CatBoost persona-período (ingreso + agregados) | 0,0464 [0,0441; 0,0488] | 0,0463 [0,0440; 0,0487] | -0,0001 |
| k = 2: IBS de test, Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0,0425 [0,0406; 0,0447] | 0,0422 [0,0402; 0,0443] | -0,0004 |
| k = 2: C de test a 12 semestres, CatBoost persona-período (ingreso + agregados) | 0,800 [0,788; 0,811] | 0,800 [0,788; 0,811] | -0,000 |
| k = 2: C de test a 12 semestres, Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0,835 [0,825; 0,844] | 0,839 [0,829; 0,849] | +0,004 |
| k = 4: IBS de test, Aalen–Johansen por programa | 0,0808 [0,0768; 0,0846] | 0,0808 [0,0768; 0,0846] | +0,0000 |
| k = 4: IBS de test, Cox causa-específico (ingreso + agregados) | 0,0554 [0,0526; 0,0582] | 0,0564 [0,0535; 0,0592] | +0,0011 |
| k = 4: IBS de test, CatBoost persona-período (ingreso + agregados) | 0,0508 [0,0481; 0,0535] | 0,0507 [0,0480; 0,0534] | -0,0001 |
| k = 4: IBS de test, Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0,0533 [0,0504; 0,0562] | 0,0518 [0,0490; 0,0545] | -0,0015 |
| k = 4: C de test a 12 semestres, CatBoost persona-período (ingreso + agregados) | 0,853 [0,845; 0,863] | 0,854 [0,846; 0,863] | +0,001 |
| k = 4: C de test a 12 semestres, Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0,854 [0,845; 0,862] | 0,860 [0,851; 0,868] | +0,006 |

Mejor clásico en valid: k = 2: CatBoost persona-período (ingreso + agregados) → CatBoost persona-período (ingreso + agregados); k = 4: CatBoost persona-período (ingreso + agregados) → CatBoost persona-período (ingreso + agregados).

**La conclusión sobre el modelo conservado de clase clásica no cambia** (CatBoost persona-período es el mejor clásico en valid en ambos cortes). **Cambia la lectura de la GRU en `k = 4`:** la ventaja de la GRU sobre el Cox con agregados en C(12) pasa de +0,003 [−0,001; +0,007] a +0,010 [+0,005; +0,014] y sobre CatBoost de +0,000 [−0,005; +0,005] a +0,006 [+0,001; +0,010], con peor IBS que CatBoost en ambas versiones; en `k = 2` la ventaja de la GRU se mantiene y aumenta algo (frente al Cox, +0,015 → +0,020; frente a CatBoost, +0,035 → +0,039).

## Resumen

1. **Tratar la salida como evento competitivo importa mucho.** A 12 semestres de la admisión la incidencia de egreso en test es 35,0 % con Aalen–Johansen y 60,9 % con 1 − Kaplan–Meier (que trata la salida como censura): el método ingenuo sobrestima en 25,9 puntos porcentuales (§2). Todo el benchmark usa causas competitivas.
2. **Al ingreso (k = 0) casi todo el valor está en el programa y el perfil, y las redes no aportan.** Aalen–Johansen por programa llega a C(12) = 0,706 en test; Cox, logística, CatBoost y MLP quedan entre 0,739 y 0,738, con diferencias pareadas entre ellos cuyos intervalos incluyen el 0 (por ejemplo MLP − logística: -0,005 [-0,011; 0,001]). El MLP mejora algo el IBS (0,0451 frente a 0,0454 de la logística; diferencia -0,0003 [-0,0007; 0,0001], IC95 % excluye el 0), una ganancia pequeña de calibración y no de discriminación.
3. **Con los agregados académicos al corte (k = 2 y 4) la discriminación sube de 0,741 a 0,819–0,856**; es la ganancia dominante de todo el estudio (k = 2: 0,078 [0,067; 0,089] en el Cox; k = 4: de 0,743 a 0,850). Ninguna arquitectura se acerca a ese salto.
4. **¿Las redes agregan señal?** Solo parcialmente y solo en `k = 2`. La **GRU** (3 semillas) tiene el mejor C(12) e IBS del corte (0,839 [0,829; 0,849]; 0,0422 [0,0402; 0,0443]) y supera en test al Cox de ingreso + agregados: ΔC(12) = 0,020 [0,015; 0,025] y ΔIBS = -0,0050 [-0,0060; -0,0040]; frente a CatBoost, 0,039 [0,033; 0,046]. La logística con agregados supera al Cox por solo 0,004 [0,002; 0,006] en C(12), de modo que la GRU gana alrededor de 0,016 a una logística (la comparación directa no está tabulada). En **k = 4 la ventaja es marginal** (cambia respecto de la versión 0.2, donde era nula): la GRU supera al Cox de ingreso + agregados en C(12) (0,009 [0,005; 0,014], el intervalo ya no incluye el 0) y apenas a CatBoost (0,005 [0,001; 0,010], el intervalo apenas excluye el 0), pero con **peor IBS que CatBoost** (0,0011 [0,0001; 0,0022]); su C(12) es 0,860 frente a 0,856 de la logística. Una mejora de 0,005 en C(12) con peor calibración no justifica sustituir al clásico.
5. **Recomendación.** Para `k = 0` y `k = 4`, mantener el modelo clásico más simple (logística persona-período o Cox causa-específico; CatBoost si interesa la calibración en k = 4). Para `k = 2`, la GRU es la mejor opción técnica, con una ganancia modesta (≈ 0,016–0,020 en C(12) sobre la logística y el Cox) que justifica evaluarla pero no sustituye a un clásico sin revisión institucional. El control posterior (2021 en adelante) es inestable para CatBoost y MLP de solo ingreso (§7.4): no aprobar nada con ese comportamiento.
6. **Deriva entre cohortes.** La mediana del tiempo al egreso baja de 13 semestres (cohortes 2015–2017) a 11 (2018 en adelante), y la incidencia acumulada de egreso a 12 semestres desde la admisión sube de 21,1 % en train a 30,5 % en valid y 35,0 % en test. Con la cohorte como variable (primera versión) los modelos fallaban fuera de tiempo; por eso el año de admisión **no** es variable de los modelos. Los modelos solo de ingreso subestiman el egreso en test (predicen 23,1 %–33,8 % a 12 semestres frente al 35,0 %–44,6 % observado); los que usan agregados quedan mucho mejor calibrados (§7.3).
7. **Equidad.** Ninguna brecha de discriminación entre mujeres y hombres supera 0,029 de AUC en valor absoluto (con agregados el AUC es algo mayor en hombres: −0,02 a −0,03 en k = 2 y ≤ 0,01 en k = 4); las mujeres egresan más que los hombres (44,2 % frente a 33,1 % a 12 semestres en k = 2) y los modelos solo de ingreso subestiman a ambos (§7.5).
8. **Costo.** Todo el benchmark corre en 1176 s (RAM pico 2130 MB); las redes entrenan en 6–15 s por corte (las 3 semillas juntas) en una GPU con pico de 53 MB; CatBoost tarda entre 134 y 192 s (§7.6).
9. **Población (D47).** El Programa de Intercambio (que no puede egresar) quedó fuera y el Plan Común de Ingeniería Civil se unió a su especialidad (353 de 683 trayectorias; §2). El cambio de población mueve poco las métricas globales (las diferencias con la versión anterior son de milésimas y están dentro de los intervalos; D47 en `00_plan.md` las lista) y no cambia las conclusiones. Siguen sin ser un problema del modelo la «salida por ausencia», que en al menos un 98 % es un cambio a otro programa sin estado de salida (§2, §8), y las trayectorias de Plan Común sin continuación, que por construcción nunca egresan.

## 1. Definición de la tarea

**T3, «tiempo hasta titulación».** Dado un episodio de pregrado que sigue en riesgo al cierre del `k`-ésimo semestre regular, ¿cuánto falta hasta su egreso/titulación y con qué probabilidad ocurre antes de un horizonte dado? Es un problema de **supervivencia con censura administrativa y un evento competitivo** (la salida definitiva del programa). La pregunta de investigación: (i) qué tan bien se puede anticipar el egreso con lo conocido al corte, (ii) cuánto cambia la estimación cuando se trata la salida como evento competitivo y no como censura, y (iii) si una red neuronal (MLP o GRU sobre la secuencia de semestres) mejora a los modelos clásicos de supervivencia.

| Elemento | Definición |
|---|---|
| Unidad | Una **trayectoria de pregrado** (`id_nivel` 1; sin admisiones `IN`, `PE`, `IE`, misma población que T1, D23) de una cohorte 2015 o posterior (P49/P50), con dos cambios de D47 (P62): (i) **sin los programas de Intercambio** (códigos 0003 y 0006: estudiantes de universidades extranjeras en estadías cortas, que no pueden egresar por naturaleza); (ii) un episodio de **Ingeniería Civil Plan Común** se une, como una sola trayectoria, con el primer episodio posterior de la misma persona en una especialidad de Ingeniería Civil que comience a lo más 2 períodos regulares después del último período del Plan Común; la unidad es la admisión al Plan Común y el episodio de la especialidad no se cuenta aparte (§2). |
| Corte `k` | Fin del `k`-ésimo semestre regular desde el de admisión, `k` ∈ {2, 4}; **`k = 0`** es «al ingreso» y solo usa información de admisión (variante «postulante», comparable con la ficha del postulante). Elegible: con estado de matrícula (matrícula, reingreso o cambio de ciclo) en el período del corte (para `k = 0`, en el semestre de admisión), sin estado de salida en el período del corte (D24/D32) y no egresado ni titulado hasta el corte. |
| Escala de tiempo | **Semestres regulares desde la admisión**: el *slot* `j` de `rules.slot_de_periodo` (1 = semestre de admisión). El tiempo desde el corte es `j − k`; los modelos trabajan en esa escala y los informes en la absoluta. |
| Evento de interés (causa 1) | **Primer egreso/titulación del episodio** (en una trayectoria unida, el de la especialidad): un estado de clase `egreso_titulacion` (`G` Egresado, `Z` Malla completa, `K` Expediente de título, `L` Licenciado, `U` Titulado) o una fila de `titulacion` vinculada al episodio, lo que ocurra primero. En la práctica casi siempre es `Z` (malla completa). La titulación propiamente tal (`U` o fila de `titulacion`) se guarda aparte como punto final de sensibilidad (`tiempo_titulacion`). |
| Evento competitivo (causa 2) | **Salida definitiva del episodio**: (a) *explícita*: un estado de clase `salida` que **no** es seguido por ningún estado de matrícula del episodio (una salida revertida por un reintegro no es salida), o (b) *por ausencia sostenida*: sin ningún estado de matrícula ni de interrupción en los dos últimos períodos regulares cerrados y sin egreso en ninguna fecha (el tiempo es el semestre siguiente a la última actividad). Las **interrupciones no son salidas**. Si el episodio egresa dentro del seguimiento, el egreso prevalece sobre una salida anterior (graduarse es un hecho verificado). |
| Censura | **Administrativa** (en una trayectoria unida, desde la especialidad): el seguimiento llega al último período regular **cerrado** (`202610`; `202620` está en curso y no se usa) y a lo sumo al semestre 20; un evento posterior se censura en ese límite. La censura depende solo del semestre de admisión, no del desenlace. |
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

| Paso | k = 0 | k = 2 | k = 4 |
|---|---|---|---|
| Unidades de pregrado de las cohortes 2015 o posteriores (T1, sin IN/PE/IE, sin Programa de Intercambio, con Plan Común unido a su especialidad) | 30.967 | 30.967 | 30.967 |
| − sin estado de matrícula en el período del corte | 253 | 2.086 | 9.638 |
| − con estado de salida en el período del corte (D24, P52) | 0 | 970 | 811 |
| − egresado o titulado hasta el corte | 0 | 4 | 16 |
| − sin seguimiento después del corte (corte en el último período cerrado) | 63 | 2.701 | 2.180 |
| = **Elegibles** | 30.651 | 25.206 | 18.322 |
| Memo: episodios de cohortes anteriores a 2015, fuera de la ventana (P49/P50) | 24.700 | 24.700 | 24.700 |
| Memo: episodios del Programa de Intercambio excluidos (cohortes 2015 o posteriores) | 20 | 20 | 20 |
| Memo: … de ellos, elegibles en este corte si se hubieran mantenido | 19 | 1 | 1 |
| Memo: episodios de especialidad unidos a un Plan Común (no cuentan como unidad) | 353 | 353 | 353 |
| Memo: … de ellos, elegibles en este corte como unidad separada (doble conteo evitado) | 36 | 33 | 229 |
| Memo: trayectorias de Plan Común elegibles en este corte | 671 | 521 | 294 |
| Memo: … de ellas, unidas a una especialidad | 353 | 352 | 273 |

### Intercambio y Plan Común (D47, P62)

La DAI respondió (P62) que los programas de 1 a 3 semestres no son diplomados: el **Programa de Intercambio** reúne a estudiantes de universidades extranjeras con estadías cortas, que no pueden egresar por naturaleza, y **Ingeniería Civil Plan Común** es un programa tipo bachillerato de 2 semestres cuyo estudiante, al completar la malla, pide el cambio a una especialidad de Ingeniería Civil. Por eso la población de esta versión cambia de dos maneras:

1. **Intercambio fuera.** Se excluyen los programas 0003 y 0006 (`PROGRAMAS_INTERCAMBIO`, por código de programa y no por duración; una prueba de integración compara los códigos con los nombres de `neural_core.programa`). En total son 20 episodios de las cohortes 2015 o posteriores dentro de la población T1; de ellos, 19 habrían sido elegibles en `k` = 0, 1 en `k` = 2 y 1 en `k` = 4 (el resto no tiene matrícula en el semestre del corte o ya salió).
2. **Plan Común unido a su especialidad.** Un episodio de Plan Común (programas 8633 y 8643; solo el 8643 tiene episodios desde 2015) se vincula con el **primer episodio posterior de la misma persona en una especialidad de Ingeniería Civil** (nivel pregrado, lista fija `ESPECIALIDADES_ING_CIVIL` de 14 programas) si el primer estado de la especialidad cae a lo más **2 períodos regulares después del último período del Plan Común**. No se exige la vía ES ni el mismo período de admisión. La especialidad vinculada **no** se cuenta aparte, y una especialidad se asocia a un solo Plan Común.

| Plan Común y su continuación | Episodios |
|---|---|
| Episodios de Ingeniería Civil Plan Común (programas 8633 y 8643) de las cohortes 2015 o posteriores | 683 |
| … con una especialidad de Ingeniería Civil como primer episodio posterior dentro de 2 períodos regulares (**unidos**, regla aplicada) | 353 |
| … … de ellos, con vía de admisión ES (Elección Especialidad) en la especialidad | 198 |
| … … de ellos, con el mismo período de admisión que el Plan Común | 317 |
| … … de ellos, con ES y el mismo período de admisión (regla estricta alternativa) | 198 |
| … con primera especialidad posterior fuera de la ventana de 2 períodos (no se unen) | 7 |
| … sin continuación en Ingeniería Civil (conservan el tratamiento anterior: salida) | 323 |

*Por qué la regla inclusiva.* Exigir ES con el mismo período de admisión dejaría fuera a la mayor parte de las continuaciones reales: la regla estricta captura 198 de las 353 continuaciones de la ventana y exigir solo el mismo período captura 317. Las demás son ingresos a la especialidad por otra vía (por ejemplo, LS o RP en un período posterior) de personas que siguen en Ingeniería Civil sin interrupción mayor a 2 períodos, es decir, la progresión que describe la DAI. Se prefirió la regla inclusiva y se conserva la ventana de 2 períodos: ampliarla agrega muy pocos casos (7 Plan Común tienen su primera especialidad más tarde).

*Dos precisiones sobre el punto en el tiempo.* (i) La inclusión de una trayectoria en un corte se decide con la vinculación, que se conoce después del corte: la salida del propio Plan Común en el período del corte no cuenta como salida de la trayectoria cuando hay vínculo, lo que mantiene en el corte a un puñado de filas (su número exacto está en D47, `docs/00_plan.md`) que sin vínculo habrían salido de la población; es una propiedad de la definición de la unidad, igual que la etiqueta, y no de las variables. (ii) Las variables de cada corte usan solo hechos hasta el corte: los agregados académicos suman ambos episodios; el programa vigente es el Plan Común hasta que se registra el primer estado de la especialidad (nunca en `k` = 0), y solo después las variables de la especialidad. Las pruebas perturban o borran los datos de la especialidad posteriores al corte y comprueban que las variables no cambian (§4).

Resultados de las trayectorias de Plan Común por corte y partición (grupos de menos de 10 no se publican):

| k | Partición | Trayectorias de Plan Común | Egreso | Salida definitiva | Censura | Mediana del tiempo al egreso (semestres) |
|---|---|---|---|---|---|---|
| 0 | train | unidas a una especialidad: 164 | 43 (26,2 %) | 117 (71,3 %) | 4 (2,4 %) | 15 |
| 0 | train | sin continuación: 161 | 0 (0,0 %) | 161 (100,0 %) | 0 (0,0 %) | — |
| 0 | valid | unidas a una especialidad: 29 | 5 (17,2 %) | 15 (51,7 %) | 9 (31,0 %) | — |
| 0 | valid | sin continuación: 30 | 0 (0,0 %) | 30 (100,0 %) | 0 (0,0 %) | — |
| 0 | test | unidas a una especialidad: 45 | 13 (28,9 %) | 27 (60,0 %) | 5 (11,1 %) | 12 |
| 0 | test | sin continuación: 25 | 0 (0,0 %) | 25 (100,0 %) | 0 (0,0 %) | — |
| 0 | posterior | unidas a una especialidad: 115 | 2 (1,7 %) | 25 (21,7 %) | 88 (76,5 %) | — |
| 0 | posterior | sin continuación: 102 | 0 (0,0 %) | 44 (43,1 %) | 58 (56,9 %) | — |
| 2 | train | unidas a una especialidad: 164 | 43 (26,2 %) | 117 (71,3 %) | 4 (2,4 %) | 15 |
| 2 | train | sin continuación: 115 | 0 (0,0 %) | 115 (100,0 %) | 0 (0,0 %) | — |
| 2 | valid | unidas a una especialidad: 29 | 5 (17,2 %) | 15 (51,7 %) | 9 (31,0 %) | — |
| 2 | valid | sin continuación: 15 | 0 (0,0 %) | 15 (100,0 %) | 0 (0,0 %) | — |
| 2 | test | unidas a una especialidad: 45 | 13 (28,9 %) | 27 (60,0 %) | 5 (11,1 %) | 12 |
| 2 | test | sin continuación: 13 | 0 (0,0 %) | 13 (100,0 %) | 0 (0,0 %) | — |
| 2 | posterior | unidas a una especialidad: 114 | 2 (1,8 %) | 24 (21,1 %) | 88 (77,2 %) | — |
| 2 | posterior | sin continuación: 26 | 0 (0,0 %) | 20 (76,9 %) | 6 (23,1 %) | — |
| 4 | train | unidas a una especialidad: 137 | 43 (31,4 %) | 90 (65,7 %) | 4 (2,9 %) | 15 |
| 4 | train | sin continuación: 18 | 0 (0,0 %) | 18 (100,0 %) | 0 (0,0 %) | — |
| 4 | valid | unidas a una especialidad: 24 | 5 (20,8 %) | 10 (41,7 %) | 9 (37,5 %) | — |
| 4 | test | unidas a una especialidad: 40 | 13 (32,5 %) | 22 (55,0 %) | 5 (12,5 %) | 12 |
| 4 | posterior | unidas a una especialidad: 72 | 2 (2,8 %) | 15 (20,8 %) | 55 (76,4 %) | — |

### Particiones, desenlaces y seguimiento

| k | Partición (cohortes) | Episodios | Egreso/titulación | Salida definitiva | Censura administrativa | Seguimiento (semestres) | Mediana del tiempo al egreso |
|---|---|---|---|---|---|---|---|
| 0 | train (2015-2017) | 7.529 | 3.414 (45,3 %) | 4.006 (53,2 %) | 109 (1,4 %) | 18–23 | 13 |
| 0 | valid (2018) | 2.613 | 1.275 (48,8 %) | 1.233 (47,2 %) | 105 (4,0 %) | 16–17 | 11 |
| 0 | test (2019-2020) | 4.738 | 2.013 (42,5 %) | 2.121 (44,8 %) | 604 (12,7 %) | 12–15 | 11 |
| 0 | posterior (2021 en adelante) | 15.771 | 635 (4,0 %) | 3.811 (24,2 %) | 11.325 (71,8 %) | 1–11 | 10 |
| 2 | train (2015-2017) | 6.715 | 3.405 (50,7 %) | 3.201 (47,7 %) | 109 (1,6 %) | 18–23 | 13 |
| 2 | valid (2018) | 2.275 | 1.230 (54,1 %) | 940 (41,3 %) | 105 (4,6 %) | 16–17 | 11 |
| 2 | test (2019-2020) | 4.343 | 2.012 (46,3 %) | 1.728 (39,8 %) | 603 (13,9 %) | 12–15 | 11 |
| 2 | posterior (2021 en adelante) | 11.873 | 630 (5,3 %) | 2.680 (22,6 %) | 8.563 (72,1 %) | 3–11 | 10 |
| 4 | train (2015-2017) | 5.173 | 3.370 (65,1 %) | 1.696 (32,8 %) | 107 (2,1 %) | 18–23 | 13 |
| 4 | valid (2018) | 1.813 | 1.253 (69,1 %) | 462 (25,5 %) | 98 (5,4 %) | 16–17 | 11 |
| 4 | test (2019-2020) | 3.711 | 2.006 (54,1 %) | 1.110 (29,9 %) | 595 (16,0 %) | 12–15 | 11 |
| 4 | posterior (2021 en adelante) | 7.625 | 622 (8,2 %) | 985 (12,9 %) | 6.018 (78,9 %) | 5–11 | 10 |

Elegibles con seguimiento a cada horizonte (las métricas por horizonte solo usan los episodios cuya cohorte llega a ese horizonte, de modo que no hay incertidumbre de censura y el peso IPCW es exactamente 1):

| k | Partición | Episodios | Con seguimiento a 10 | a 12 | a 14 |
|---|---|---|---|---|---|
| 0 | valid | 2.613 | 2.613 | 2.613 | 2.613 |
| 0 | test | 4.738 | 4.738 | 4.738 | 2.511 |
| 0 | posterior (horizontes 8 y 10) | 15.771 | a 8: 4.394 | a 10: 2.078 | — |
| 2 | valid | 2.275 | 2.275 | 2.275 | 2.275 |
| 2 | test | 4.343 | 4.343 | 4.343 | 2.230 |
| 2 | posterior (horizontes 8 y 10) | 11.873 | a 8: 4.084 | a 10: 1.944 | — |
| 4 | valid | 1.813 | 1.813 | 1.813 | 1.813 |
| 4 | test | 3.711 | 3.711 | 3.711 | 1.925 |
| 4 | posterior (horizontes 8 y 10) | 7.625 | a 8: 3.264 | a 10: 1.575 | — |

### Desenlaces por cohorte (k = 2)

| Cohorte | Episodios (k = 2) | Egreso/titulación observado | Salida definitiva | Censurado | Seguimiento mediano (semestres) |
|---|---|---|---|---|---|
| 2015 | 2.206 | 48,4 % | 49,9 % | 1,7 % | 23 |
| 2016 | 2.256 | 51,7 % | 47,0 % | 1,3 % | 21 |
| 2017 | 2.253 | 52,0 % | 46,2 % | 1,8 % | 19 |
| 2018 | 2.275 | 54,1 % | 41,3 % | 4,6 % | 17 |
| 2019 | 2.230 | 51,9 % | 38,4 % | 9,7 % | 15 |
| 2020 | 2.113 | 40,5 % | 41,3 % | 18,3 % | 13 |
| 2021 | 1.944 | 26,3 % | 37,7 % | 36,0 % | 11 |
| 2022 | 2.140 | 3,6 % | 31,8 % | 64,6 % | 9 |
| 2023 | 2.579 | 1,4 % | 23,8 % | 74,8 % | 7 |
| 2024 | 2.576 | 0,2 % | 17,8 % | 82,0 % | 5 |
| 2025 | 2.634 | 0,0 % | 7,4 % | 92,6 % | 3 |

### Incidencia acumulada: Aalen–Johansen frente a 1 − Kaplan–Meier

| Partición (k = 0) | Semestre desde la admisión | Incidencia acumulada de egreso (Aalen–Johansen) | 1 − Kaplan–Meier (salida como censura) | Diferencia | Incidencia acumulada de salida (AJ) |
|---|---|---|---|---|---|
| train (n = 7.529) | 8 | 0,9 % | 1,3 % | +0,5 pp | 46,1 % |
| train (n = 7.529) | 10 | 4,4 % | 8,0 % | +3,6 pp | 49,5 % |
| train (n = 7.529) | 12 | 21,1 % | 41,7 % | +20,5 pp | 51,1 % |
| train (n = 7.529) | 14 | 33,7 % | 68,3 % | +34,6 pp | 52,3 % |
| train (n = 7.529) | 16 | 40,8 % | 84,6 % | +43,8 pp | 52,8 % |
| train (n = 7.529) | 18 | 44,3 % | 93,1 % | +48,8 pp | 53,1 % |
| valid (n = 2.613) | 8 | 2,7 % | 4,0 % | +1,3 pp | 40,0 % |
| valid (n = 2.613) | 10 | 9,1 % | 14,9 % | +5,8 pp | 44,0 % |
| valid (n = 2.613) | 12 | 30,5 % | 54,1 % | +23,5 pp | 45,8 % |
| valid (n = 2.613) | 14 | 41,8 % | 76,2 % | +34,4 pp | 46,5 % |
| valid (n = 2.613) | 16 | 48,1 % | 89,2 % | +41,1 pp | 47,1 % |
| test (n = 4.738) | 8 | 2,3 % | 3,4 % | +1,1 pp | 39,5 % |
| test (n = 4.738) | 10 | 12,0 % | 19,9 % | +7,9 pp | 42,8 % |
| test (n = 4.738) | 12 | 35,0 % | 60,9 % | +25,9 pp | 43,9 % |
| test (n = 4.738) | 14 | 44,6 % | 78,8 % | +34,2 pp | 45,1 % |

### Tipo de salida y destino

| Partición (k = 2) | Salidas | Explícitas | Por ausencia sostenida | Explícitas con matrícula posterior en otro programa | Por ausencia con matrícula posterior en otro programa |
|---|---|---|---|---|---|
| train | 3.201 | 2.721 | 480 | 698 (25,7 %) | 472 (98,3 %) |
| valid | 940 | 829 | 111 | 165 (19,9 %) | 111 (100,0 %) |
| test | 1.728 | 1.488 | 240 | 279 (18,8 %) | 236 (98,3 %) |
| posterior | 2.680 | 2.278 | 402 | 280 (12,3 %) | 394 (98,0 %) |

### Duración nominal del programa

| Duración nominal (semestres) | Episodios (k = 2, 2015-2020) | Egreso/titulación observado | Salida definitiva |
|---|---|---|---|
| 6 | 53 | 49,1 % | 50,9 % |
| 8 | 1.450 | 53,4 % | 44,5 % |
| 9 | 176 | 27,8 % | 68,8 % |
| 10 | 9.822 | 51,5 % | 42,9 % |
| 11 | 111 | 15,3 % | 82,0 % |
| 12 | 1.341 | 35,3 % | 54,5 % |
| 14 | 379 | 64,9 % | 9,8 % |

## 3. Fuentes del evento: estados y tabla de titulación

| Concordancia entre fuentes | Episodios |
|---|---|
| Episodios de la población (cohortes ≥ 2015) | 30.967 |
| Con algún estado de clase egreso/titulación (G, Z, K, L, U) | 7.660 |
| Con fila vinculada en `titulacion` (banner_titulados) | 6.790 |
| … en ambas fuentes | 6.790 |
| … solo en estados (egresados sin fila de titulación) | 870 |
| … solo en la tabla de titulación (sin estado) | 0 |
| Con estado `U` (Titulado) | 6.891 |
| … `U` sin fila de titulación | 386 |
| Fila de titulación sin estado `U` | 285 |
| Ambas fuentes: fecha de titulación en el mismo semestre que el primer estado de egreso | 4.260 |
| … en un semestre anterior al primer estado | 1.757 |
| … en un semestre posterior al primer estado | 773 |
| Fila con estado `U`: misma fecha-semestre | 4.603 |
| … fecha-semestre un semestre antes que el estado `U` | 1.856 |
| … otro desfase | 46 |
| Salida definitiva registrada antes del egreso | 0 |
| Egreso registrado después del último período cerrado (censurado) | 253 |
| Filas de `titulacion` sin episodio vinculado (todas las cohortes; no se usan) | 1.260 |

## 4. Snapshot point-in-time (migraciones 013 y 014, `python -m pipelines.snapshots.t3`)

Una fila por (episodio, `k`) con las variables del corte y la etiqueta (`tiempo`, `causa`, `seguimiento_max`). Las variables usan solo hechos de los semestres `<= k` (la misma partición en *slots* de T1: `periodo <= corte ⇔ slot <= k`, los cursos de verano/invierno cuentan en el corte siguiente) más datos estáticos del programa; la etiqueta mira solo los semestres posteriores y nunca alimenta una variable. Pruebas: perturbación (reasignar notas, borrar la mitad de los estados y agregar salidas en los semestres posteriores al corte deja idénticas las variables), borrado de todos los períodos posteriores, comprobación por mutación (la prueba **falla** si se cambia un dato anterior al corte), reglas de evento y censura, equivalencia entre la resolución vectorizada y la escalar sobre una rejilla, y un recálculo SQL independiente del tiempo de egreso, del seguimiento, de los semestres matriculados y de los intentos (`tests/integration/test_snapshot_t3.py`).

**Plan Común (D47).** La migración 014 agrega a `snapshot_t3` las columnas `trayectoria_plan_comun` (dato de admisión), `especialidad_conocida_al_corte` y `episodio_especialidad_id` (huella de auditoría del vínculo, que se decide con el futuro y **nunca** es variable: está en `LABEL_COLS` y en las columnas prohibidas de los modelos). Las dos primeras **sí** son variables de los modelos porque se conocen en el corte (la primera es un dato de admisión; la segunda solo mira estados hasta el corte). La duración nominal de una trayectoria de Plan Común antes de conocer la especialidad es la duración del Plan Común más una constante de 8.0 semestres: la mediana, **solo en las cohortes de train**, de (desfase de admisión de la especialidad + su duración nominal − la duración del Plan Común); así vale lo mismo para quien después tendrá especialidad y para quien no, y no usa la especialidad de la propia trayectoria más que como parte de la mediana de train. Pruebas nuevas (`tests/unit/test_snapshot_t3_plan_comun.py`): regla de vínculo (ventana, primera especialidad posterior, una especialidad por Plan Común, sin exigir ES), exclusión del Intercambio, ausencia de doble conteo, evento y tiempo de las trayectorias unidas, variables del programa vigente en `k` = 0, 2 y 4, constante aprendida solo con train, y perturbación y borrado de los datos de la especialidad posteriores al corte (con la prueba por mutación que debe fallar); en integración, un recálculo SQL independiente de cada vínculo, de la especialidad conocida al corte, de los semestres matriculados y de los intentos de ambos episodios, y del egreso de la especialidad.

Hash de datos: `71bad59591e2fea0961400fe2863f4c99474d82c8469e2eae33ee52e4d60280b`. Versión del código: `b1259455b334aa220461c618d87aef762a13b7fb2757e1b1afd5a371a9590ff9`.

## 5. Protocolo de modelado

- **Escalera de ablación** (mismos episodios, horizontes y semillas en cada escalón): Aalen–Johansen global → Aalen–Johansen por programa → perfil de ingreso → + agregados al corte → + secuencia de semestres. Cada escalón se ajusta con cuatro familias: Cox causa-específico (`lifelines`, penalizado L2; una ecuación por causa y riesgos combinados en tiempo discreto), logística multinomial persona-período, CatBoost multiclase persona-período (3 semillas) y red neuronal de riesgos discretos.
- **Redes.** MLP y GRU con cabeza *softmax causa-específica* por semestre posterior al corte (supervive / egreso / salida): la verosimilitud exacta de tiempo discreto con censura, en una pasada por episodio. No es DeepHit (sin softmax conjunto en tiempo y causa ni pérdida de ranking). AdamW, parada anticipada con la log-verosimilitud negativa de valid, 3 semillas, GPU (NVIDIA GeForce RTX 4060 Laptop GPU); el resultado es el promedio de las incidencias acumuladas de las 3 semillas.
- **Ajuste y selección.** Todo (medianas, escalas, vocabularios, penalizadores, `C`, iteraciones, épocas) se ajusta o elige solo con train y valid. El modelo clásico ganador se elige por IBS en valid.
- **Métricas.** Para cada horizonte `t`: C de Uno truncado en `t` con evento competitivo (Wolbers: quien tuvo la salida nunca tiene el evento de interés), AUC(t) y Brier(t) de la incidencia acumulada predicha `F₁(t | x)` entre los episodios con seguimiento hasta `t`; IBS = promedio del Brier de los semestres `k+1..12` entre los episodios con seguimiento hasta 12. Las funciones de supervivencia (Aalen–Johansen, Kaplan–Meier de la censura, C de Uno con pesos IPCW, Brier IPCW, IBS) están escritas en `evaluation/metrics_t3.py` con pruebas contra casos calculados a mano y contra `lifelines`; no se usó `scikit-survival`.
- **Incertidumbre.** Bootstrap de 1.000 remuestreos de episodios (300 en el control posterior), con los **mismos** remuestreos para todos los modelos, de modo que las diferencias pareadas son válidas. Las particiones valid y test se reportan por separado.
- **Seguimiento.** MLflow local (experimento `t3_tiempo_hasta_titulacion`) con hash de los datos y versión del código.

## 6. Resultados por corte

Convención: intervalos del 95 % entre corchetes (bootstrap de episodios, mismos remuestreos para todos los modelos); las diferencias son **pareadas** (A − B). Para C y AUC, más es mejor; para Brier e IBS, menos es mejor. Horizonte principal: 12 semestres desde la admisión. Las tablas completas de valid y de test siguen; el control posterior está en §7.4.

### 6.1 Al ingreso (k = 0, «postulante»)

Test (cohortes 2019-2020):

| Modelo | C de Uno (t = 10) | C de Uno (t = 12) | C de Uno (t = 14) | AUC(t = 10) | AUC(t = 12) | AUC(t = 14) |
|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.653 [0.629; 0.676] | 0.706 [0.692; 0.718] | 0.702 [0.686; 0.719] | 0.655 [0.630; 0.680] | 0.732 [0.717; 0.747] | 0.716 [0.695; 0.736] |
| Cox causa-específico (ingreso) | 0.709 [0.687; 0.729] | 0.740 [0.727; 0.752] | 0.735 [0.721; 0.750] | 0.719 [0.697; 0.738] | 0.771 [0.755; 0.784] | 0.756 [0.736; 0.775] |
| Logística persona-período (ingreso) | 0.717 [0.697; 0.737] | 0.742 [0.729; 0.754] | 0.734 [0.719; 0.750] | 0.727 [0.706; 0.746] | 0.773 [0.758; 0.786] | 0.754 [0.735; 0.774] |
| CatBoost persona-período (ingreso) | 0.715 [0.695; 0.736] | 0.739 [0.727; 0.750] | 0.724 [0.711; 0.741] | 0.718 [0.697; 0.739] | 0.774 [0.760; 0.787] | 0.754 [0.737; 0.775] |
| Red MLP de riesgos discretos (ingreso) | 0.713 [0.688; 0.735] | 0.738 [0.726; 0.750] | 0.725 [0.711; 0.741] | 0.715 [0.690; 0.738] | 0.769 [0.756; 0.783] | 0.755 [0.736; 0.775] |

| Modelo | Brier(t = 10) | Brier(t = 12) | Brier(t = 14) | IBS |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.1113 [0.1034; 0.1202] | 0.2468 [0.2386; 0.2543] | 0.2592 [0.2527; 0.2658] | 0.0541 [0.0517; 0.0565] |
| Aalen–Johansen por programa | 0.1068 [0.0992; 0.1149] | 0.2113 [0.2038; 0.2189] | 0.2221 [0.2138; 0.2306] | 0.0480 [0.0459; 0.0503] |
| Cox causa-específico (ingreso) | 0.1050 [0.0975; 0.1130] | 0.2010 [0.1937; 0.2076] | 0.2037 [0.1957; 0.2110] | 0.0466 [0.0446; 0.0487] |
| Logística persona-período (ingreso) | 0.1026 [0.0953; 0.1104] | 0.1957 [0.1888; 0.2019] | 0.2024 [0.1951; 0.2094] | 0.0454 [0.0434; 0.0474] |
| CatBoost persona-período (ingreso) | 0.1056 [0.0979; 0.1139] | 0.1991 [0.1920; 0.2057] | 0.2041 [0.1969; 0.2107] | 0.0460 [0.0439; 0.0481] |
| Red MLP de riesgos discretos (ingreso) | 0.1052 [0.0978; 0.1133] | 0.1955 [0.1884; 0.2021] | 0.2023 [0.1939; 0.2097] | 0.0451 [0.0431; 0.0472] |

Diferencias pareadas en test:

| Comparación (A − B, diferencia pareada) | ΔC (t = 10) | ΔC (t = 12) | ΔAUC (t = 10) | ΔAUC (t = 12) | ΔBrier (t = 12) | ΔIBS |
|---|---|---|---|---|---|---|
| Aalen–Johansen por programa − Aalen–Johansen global (sin covariables) | 0.153 [0.129; 0.176] | 0.206 [0.192; 0.218] | 0.155 [0.130; 0.180] | 0.232 [0.217; 0.247] | -0.0354 [-0.0402; -0.0305] | -0.0061 [-0.0070; -0.0051] |
| Cox causa-específico (ingreso) − Aalen–Johansen por programa | 0.056 [0.029; 0.082] | 0.034 [0.027; 0.041] | 0.063 [0.035; 0.089] | 0.038 [0.031; 0.046] | -0.0104 [-0.0129; -0.0082] | -0.0014 [-0.0020; -0.0009] |
| Logística persona-período (ingreso) − Cox causa-específico (ingreso) | 0.008 [0.005; 0.012] | 0.002 [0.000; 0.004] | 0.008 [0.005; 0.011] | 0.002 [0.000; 0.004] | -0.0052 [-0.0060; -0.0044] | -0.0012 [-0.0014; -0.0009] |
| CatBoost persona-período (ingreso) − Logística persona-período (ingreso) | -0.002 [-0.020; 0.017] | -0.003 [-0.010; 0.004] | -0.009 [-0.027; 0.012] | 0.001 [-0.006; 0.008] | 0.0034 [0.0011; 0.0054] | 0.0006 [0.0001; 0.0010] |
| Red MLP de riesgos discretos (ingreso) − CatBoost persona-período (ingreso) | -0.003 [-0.020; 0.014] | -0.001 [-0.008; 0.005] | -0.003 [-0.020; 0.014] | -0.005 [-0.012; 0.003] | -0.0037 [-0.0062; -0.0010] | -0.0009 [-0.0013; -0.0004] |
| Red MLP de riesgos discretos (ingreso) − Logística persona-período (ingreso) | -0.005 [-0.028; 0.020] | -0.005 [-0.011; 0.001] | -0.012 [-0.036; 0.013] | -0.004 [-0.010; 0.003] | -0.0003 [-0.0025; 0.0018] | -0.0003 [-0.0007; 0.0001] |
| Red MLP de riesgos discretos (ingreso) − Cox causa-específico (ingreso) | 0.004 [-0.021; 0.028] | -0.002 [-0.008; 0.004] | -0.004 [-0.028; 0.022] | -0.002 [-0.008; 0.005] | -0.0055 [-0.0078; -0.0033] | -0.0015 [-0.0020; -0.0010] |
| Logística persona-período (ingreso) − Aalen–Johansen por programa | 0.064 [0.038; 0.089] | 0.036 [0.030; 0.044] | 0.071 [0.043; 0.097] | 0.040 [0.032; 0.049] | -0.0156 [-0.0183; -0.0132] | -0.0026 [-0.0031; -0.0021] |
| CatBoost persona-período (ingreso) − Aalen–Johansen por programa | 0.062 [0.036; 0.086] | 0.033 [0.023; 0.043] | 0.062 [0.035; 0.087] | 0.041 [0.031; 0.052] | -0.0122 [-0.0156; -0.0091] | -0.0020 [-0.0027; -0.0015] |
| Cox causa-específico (ingreso) − Aalen–Johansen global (sin covariables) | 0.209 [0.187; 0.229] | 0.240 [0.227; 0.252] | 0.219 [0.197; 0.238] | 0.271 [0.255; 0.284] | -0.0458 [-0.0502; -0.0414] | -0.0075 [-0.0082; -0.0068] |
| CatBoost persona-período (ingreso) − Aalen–Johansen global (sin covariables) | 0.215 [0.195; 0.236] | 0.239 [0.227; 0.250] | 0.218 [0.197; 0.239] | 0.274 [0.260; 0.287] | -0.0476 [-0.0517; -0.0432] | -0.0081 [-0.0088; -0.0073] |

Lectura. Pasar de Aalen–Johansen global a por programa añade 0,206 [0,192; 0,218] de C(12); agregar el perfil de ingreso (Cox) otros 0,034 [0,027; 0,041]; después de eso los cuatro modelos son equivalentes en discriminación (C(12) entre 0,739 y 0,738, diferencias con IC que incluyen el 0). Las redes y CatBoost no mejoran a la logística ni al Cox en ranking; el MLP tiene el mejor IBS en test (0,0451) y la diferencia con la logística (-0,0003 [-0,0007; 0,0001]) es significativa pero de magnitud pequeña. CatBoost y la logística difieren en C(10) con signos que dependen del horizonte (§7.2).

Valid (cohorte 2018):

| Modelo | C de Uno (t = 10) | C de Uno (t = 12) | C de Uno (t = 14) | AUC(t = 10) | AUC(t = 12) | AUC(t = 14) |
|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.777 [0.753; 0.800] | 0.720 [0.703; 0.737] | 0.687 [0.671; 0.701] | 0.790 [0.764; 0.814] | 0.754 [0.734; 0.772] | 0.713 [0.693; 0.731] |
| Cox causa-específico (ingreso) | 0.700 [0.672; 0.725] | 0.752 [0.735; 0.767] | 0.725 [0.710; 0.740] | 0.710 [0.682; 0.736] | 0.787 [0.768; 0.803] | 0.757 [0.737; 0.774] |
| Logística persona-período (ingreso) | 0.715 [0.689; 0.741] | 0.754 [0.737; 0.769] | 0.726 [0.710; 0.741] | 0.725 [0.698; 0.751] | 0.788 [0.769; 0.805] | 0.759 [0.739; 0.777] |
| CatBoost persona-período (ingreso) | 0.856 [0.836; 0.877] | 0.735 [0.718; 0.753] | 0.698 [0.681; 0.715] | 0.866 [0.845; 0.888] | 0.772 [0.753; 0.790] | 0.742 [0.722; 0.761] |
| Red MLP de riesgos discretos (ingreso) | 0.867 [0.844; 0.891] | 0.757 [0.742; 0.773] | 0.711 [0.696; 0.726] | 0.875 [0.850; 0.898] | 0.794 [0.777; 0.811] | 0.751 [0.733; 0.769] |

| Modelo | Brier(t = 10) | Brier(t = 12) | Brier(t = 14) | IBS |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.0847 [0.0745; 0.0945] | 0.2210 [0.2110; 0.2305] | 0.2499 [0.2439; 0.2558] | 0.0528 [0.0491; 0.0562] |
| Aalen–Johansen por programa | 0.0781 [0.0688; 0.0870] | 0.1857 [0.1770; 0.1942] | 0.2150 [0.2079; 0.2227] | 0.0464 [0.0429; 0.0496] |
| Cox causa-específico (ingreso) | 0.0808 [0.0710; 0.0902] | 0.1786 [0.1700; 0.1865] | 0.1999 [0.1928; 0.2072] | 0.0461 [0.0426; 0.0493] |
| Logística persona-período (ingreso) | 0.0790 [0.0693; 0.0880] | 0.1744 [0.1665; 0.1820] | 0.1971 [0.1904; 0.2042] | 0.0450 [0.0418; 0.0481] |
| CatBoost persona-período (ingreso) | 0.0722 [0.0632; 0.0804] | 0.1798 [0.1712; 0.1875] | 0.2046 [0.1976; 0.2119] | 0.0444 [0.0411; 0.0474] |
| Red MLP de riesgos discretos (ingreso) | 0.0676 [0.0596; 0.0751] | 0.1669 [0.1595; 0.1742] | 0.1990 [0.1922; 0.2060] | 0.0417 [0.0388; 0.0445] |

### 6.2 Después de 2 semestres (k = 2)

Test (cohortes 2019-2020):

| Modelo | C de Uno (t = 10) | C de Uno (t = 12) | C de Uno (t = 14) | AUC(t = 10) | AUC(t = 12) | AUC(t = 14) |
|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.656 [0.632; 0.682] | 0.708 [0.695; 0.721] | 0.709 [0.692; 0.726] | 0.659 [0.634; 0.686] | 0.738 [0.723; 0.752] | 0.727 [0.705; 0.748] |
| Cox causa-específico (ingreso) | 0.707 [0.686; 0.726] | 0.741 [0.728; 0.754] | 0.738 [0.722; 0.754] | 0.718 [0.696; 0.737] | 0.776 [0.761; 0.790] | 0.764 [0.744; 0.783] |
| Cox causa-específico (ingreso + agregados) | 0.798 [0.779; 0.815] | 0.819 [0.808; 0.829] | 0.794 [0.779; 0.809] | 0.807 [0.789; 0.824] | 0.858 [0.846; 0.868] | 0.837 [0.819; 0.853] |
| Logística persona-período (ingreso) | 0.712 [0.691; 0.732] | 0.739 [0.727; 0.751] | 0.734 [0.719; 0.750] | 0.722 [0.701; 0.741] | 0.773 [0.759; 0.787] | 0.763 [0.742; 0.782] |
| Logística persona-período (ingreso + agregados) | 0.813 [0.794; 0.829] | 0.823 [0.812; 0.833] | 0.796 [0.781; 0.811] | 0.820 [0.803; 0.837] | 0.858 [0.846; 0.868] | 0.841 [0.824; 0.857] |
| CatBoost persona-período (ingreso) | 0.719 [0.697; 0.742] | 0.739 [0.727; 0.752] | 0.722 [0.706; 0.739] | 0.723 [0.700; 0.746] | 0.778 [0.764; 0.792] | 0.761 [0.739; 0.781] |
| CatBoost persona-período (ingreso + agregados) | 0.805 [0.785; 0.823] | 0.800 [0.788; 0.811] | 0.747 [0.731; 0.763] | 0.808 [0.790; 0.827] | 0.841 [0.829; 0.853] | 0.798 [0.779; 0.816] |
| Red MLP de riesgos discretos (ingreso) | 0.689 [0.666; 0.713] | 0.734 [0.721; 0.746] | 0.721 [0.706; 0.737] | 0.690 [0.666; 0.715] | 0.770 [0.756; 0.784] | 0.758 [0.737; 0.777] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.810 [0.793; 0.828] | 0.816 [0.805; 0.825] | 0.770 [0.755; 0.785] | 0.813 [0.795; 0.831] | 0.860 [0.849; 0.872] | 0.824 [0.807; 0.841] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.835 [0.818; 0.852] | 0.839 [0.829; 0.849] | 0.808 [0.794; 0.821] | 0.836 [0.819; 0.853] | 0.880 [0.869; 0.889] | 0.860 [0.844; 0.875] |

| Modelo | Brier(t = 10) | Brier(t = 12) | Brier(t = 14) | IBS |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.1203 [0.1115; 0.1290] | 0.2571 [0.2495; 0.2649] | 0.2658 [0.2607; 0.2708] | 0.0687 [0.0656; 0.0718] |
| Aalen–Johansen por programa | 0.1149 [0.1061; 0.1236] | 0.2188 [0.2109; 0.2267] | 0.2251 [0.2161; 0.2335] | 0.0606 [0.0578; 0.0636] |
| Cox causa-específico (ingreso) | 0.1130 [0.1047; 0.1217] | 0.2076 [0.2003; 0.2144] | 0.2043 [0.1960; 0.2124] | 0.0588 [0.0560; 0.0617] |
| Cox causa-específico (ingreso + agregados) | 0.1006 [0.0934; 0.1082] | 0.1526 [0.1468; 0.1583] | 0.1662 [0.1567; 0.1763] | 0.0472 [0.0450; 0.0496] |
| Logística persona-período (ingreso) | 0.1107 [0.1025; 0.1192] | 0.2004 [0.1937; 0.2070] | 0.2009 [0.1928; 0.2091] | 0.0569 [0.0543; 0.0597] |
| Logística persona-período (ingreso + agregados) | 0.0935 [0.0869; 0.1008] | 0.1484 [0.1425; 0.1545] | 0.1634 [0.1536; 0.1737] | 0.0451 [0.0431; 0.0473] |
| CatBoost persona-período (ingreso) | 0.1128 [0.1043; 0.1213] | 0.2024 [0.1958; 0.2092] | 0.2042 [0.1967; 0.2115] | 0.0573 [0.0546; 0.0602] |
| CatBoost persona-período (ingreso + agregados) | 0.0990 [0.0909; 0.1072] | 0.1571 [0.1503; 0.1642] | 0.1914 [0.1798; 0.2027] | 0.0463 [0.0440; 0.0487] |
| Red MLP de riesgos discretos (ingreso) | 0.1127 [0.1044; 0.1214] | 0.1967 [0.1893; 0.2035] | 0.2014 [0.1932; 0.2097] | 0.0559 [0.0533; 0.0587] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.0985 [0.0910; 0.1064] | 0.1498 [0.1429; 0.1570] | 0.1790 [0.1679; 0.1901] | 0.0454 [0.0432; 0.0479] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.0936 [0.0858; 0.1012] | 0.1376 [0.1308; 0.1447] | 0.1546 [0.1444; 0.1647] | 0.0422 [0.0402; 0.0443] |

Diferencias pareadas en test (incluye cada escalón de la ablación y red frente a clásico):

| Comparación (A − B, diferencia pareada) | ΔC (t = 10) | ΔC (t = 12) | ΔAUC (t = 10) | ΔAUC (t = 12) | ΔBrier (t = 12) | ΔIBS |
|---|---|---|---|---|---|---|
| Aalen–Johansen por programa − Aalen–Johansen global (sin covariables) | 0.156 [0.132; 0.182] | 0.208 [0.195; 0.221] | 0.159 [0.134; 0.186] | 0.238 [0.223; 0.252] | -0.0383 [-0.0432; -0.0328] | -0.0081 [-0.0093; -0.0068] |
| Cox causa-específico (ingreso) − Aalen–Johansen por programa | 0.051 [0.025; 0.076] | 0.033 [0.026; 0.040] | 0.059 [0.031; 0.086] | 0.038 [0.029; 0.046] | -0.0112 [-0.0140; -0.0085] | -0.0018 [-0.0025; -0.0011] |
| Cox causa-específico (ingreso + agregados) − Cox causa-específico (ingreso) | 0.091 [0.074; 0.109] | 0.078 [0.067; 0.089] | 0.090 [0.072; 0.108] | 0.082 [0.069; 0.093] | -0.0550 [-0.0600; -0.0495] | -0.0116 [-0.0127; -0.0104] |
| Logística persona-período (ingreso) − Cox causa-específico (ingreso) | 0.005 [0.003; 0.008] | -0.002 [-0.003; -0.000] | 0.005 [0.003; 0.007] | -0.003 [-0.004; -0.001] | -0.0071 [-0.0084; -0.0059] | -0.0018 [-0.0021; -0.0015] |
| Logística persona-período (ingreso + agregados) − Cox causa-específico (ingreso + agregados) | 0.015 [0.011; 0.019] | 0.004 [0.002; 0.006] | 0.013 [0.009; 0.017] | 0.000 [-0.001; 0.002] | -0.0042 [-0.0062; -0.0021] | -0.0021 [-0.0026; -0.0015] |
| Logística persona-período (ingreso + agregados) − Logística persona-período (ingreso) | 0.100 [0.082; 0.119] | 0.084 [0.072; 0.094] | 0.098 [0.079; 0.117] | 0.085 [0.072; 0.097] | -0.0520 [-0.0581; -0.0459] | -0.0118 [-0.0133; -0.0103] |
| CatBoost persona-período (ingreso) − Logística persona-período (ingreso) | 0.007 [-0.012; 0.027] | 0.000 [-0.007; 0.007] | 0.000 [-0.018; 0.021] | 0.005 [-0.003; 0.013] | 0.0020 [-0.0005; 0.0046] | 0.0004 [-0.0002; 0.0009] |
| CatBoost persona-período (ingreso + agregados) − Logística persona-período (ingreso + agregados) | -0.008 [-0.021; 0.006] | -0.023 [-0.029; -0.016] | -0.012 [-0.025; 0.002] | -0.017 [-0.023; -0.010] | 0.0087 [0.0050; 0.0124] | 0.0012 [0.0002; 0.0020] |
| CatBoost persona-período (ingreso + agregados) − CatBoost persona-período (ingreso) | 0.085 [0.061; 0.107] | 0.061 [0.047; 0.073] | 0.086 [0.061; 0.108] | 0.063 [0.048; 0.076] | -0.0453 [-0.0520; -0.0379] | -0.0110 [-0.0126; -0.0093] |
| CatBoost persona-período (ingreso + agregados) − Cox causa-específico (ingreso + agregados) | 0.007 [-0.007; 0.021] | -0.019 [-0.025; -0.013] | 0.001 [-0.013; 0.016] | -0.016 [-0.022; -0.011] | 0.0045 [0.0008; 0.0082] | -0.0009 [-0.0019; -0.0000] |
| Red MLP de riesgos discretos (ingreso) − CatBoost persona-período (ingreso) | -0.030 [-0.049; -0.009] | -0.006 [-0.012; 0.000] | -0.033 [-0.053; -0.011] | -0.008 [-0.015; -0.001] | -0.0057 [-0.0084; -0.0032] | -0.0014 [-0.0019; -0.0008] |
| Red MLP de riesgos discretos (ingreso) − Logística persona-período (ingreso) | -0.023 [-0.049; 0.004] | -0.005 [-0.012; 0.001] | -0.032 [-0.059; -0.005] | -0.003 [-0.010; 0.004] | -0.0037 [-0.0062; -0.0013] | -0.0010 [-0.0016; -0.0004] |
| Red MLP de riesgos discretos (ingreso + agregados) − Red MLP de riesgos discretos (ingreso) | 0.121 [0.104; 0.138] | 0.082 [0.070; 0.093] | 0.123 [0.106; 0.139] | 0.090 [0.077; 0.102] | -0.0469 [-0.0531; -0.0402] | -0.0105 [-0.0118; -0.0091] |
| Red MLP de riesgos discretos (ingreso + agregados) − CatBoost persona-período (ingreso + agregados) | 0.006 [-0.011; 0.023] | 0.016 [0.011; 0.021] | 0.004 [-0.012; 0.021] | 0.019 [0.014; 0.024] | -0.0073 [-0.0104; -0.0042] | -0.0009 [-0.0017; -0.0000] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) − Red MLP de riesgos discretos (ingreso + agregados) | 0.025 [0.017; 0.033] | 0.024 [0.021; 0.027] | 0.023 [0.015; 0.031] | 0.019 [0.016; 0.022] | -0.0122 [-0.0142; -0.0102] | -0.0032 [-0.0038; -0.0027] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) − CatBoost persona-período (ingreso + agregados) | 0.030 [0.011; 0.049] | 0.039 [0.033; 0.046] | 0.027 [0.007; 0.047] | 0.039 [0.032; 0.045] | -0.0195 [-0.0234; -0.0153] | -0.0041 [-0.0051; -0.0031] |
| Red MLP de riesgos discretos (ingreso) − Cox causa-específico (ingreso) | -0.018 [-0.044; 0.010] | -0.007 [-0.013; -0.001] | -0.028 [-0.054; 0.001] | -0.006 [-0.012; 0.001] | -0.0109 [-0.0134; -0.0083] | -0.0029 [-0.0035; -0.0022] |
| Red MLP de riesgos discretos (ingreso + agregados) − Logística persona-período (ingreso + agregados) | -0.002 [-0.020; 0.015] | -0.007 [-0.012; -0.003] | -0.007 [-0.025; 0.011] | 0.003 [-0.002; 0.007] | 0.0014 [-0.0016; 0.0043] | 0.0003 [-0.0004; 0.0010] |
| Red MLP de riesgos discretos (ingreso + agregados) − Cox causa-específico (ingreso + agregados) | 0.012 [-0.006; 0.033] | -0.004 [-0.008; 0.001] | 0.005 [-0.013; 0.026] | 0.003 [-0.001; 0.007] | -0.0028 [-0.0058; 0.0005] | -0.0018 [-0.0026; -0.0010] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) − Cox causa-específico (ingreso + agregados) | 0.037 [0.016; 0.060] | 0.020 [0.015; 0.025] | 0.028 [0.008; 0.052] | 0.022 [0.017; 0.027] | -0.0150 [-0.0185; -0.0113] | -0.0050 [-0.0060; -0.0040] |
| Logística persona-período (ingreso) − Aalen–Johansen por programa | 0.056 [0.031; 0.081] | 0.031 [0.024; 0.038] | 0.063 [0.036; 0.089] | 0.035 [0.027; 0.044] | -0.0184 [-0.0214; -0.0154] | -0.0037 [-0.0043; -0.0030] |
| CatBoost persona-período (ingreso) − Aalen–Johansen por programa | 0.063 [0.041; 0.085] | 0.031 [0.022; 0.040] | 0.064 [0.041; 0.086] | 0.040 [0.030; 0.050] | -0.0164 [-0.0199; -0.0127] | -0.0033 [-0.0041; -0.0024] |
| Cox causa-específico (ingreso) − Aalen–Johansen global (sin covariables) | 0.207 [0.186; 0.226] | 0.241 [0.228; 0.254] | 0.218 [0.196; 0.237] | 0.276 [0.261; 0.290] | -0.0496 [-0.0539; -0.0448] | -0.0099 [-0.0107; -0.0089] |
| Red MLP de riesgos discretos (ingreso) − CatBoost persona-período (ingreso + agregados) | -0.115 [-0.143; -0.089] | -0.066 [-0.079; -0.053] | -0.118 [-0.146; -0.092] | -0.071 [-0.084; -0.055] | 0.0396 [0.0321; 0.0465] | 0.0096 [0.0080; 0.0113] |
| CatBoost persona-período (ingreso + agregados) − Aalen–Johansen global (sin covariables) | 0.305 [0.285; 0.323] | 0.300 [0.288; 0.311] | 0.308 [0.290; 0.327] | 0.341 [0.329; 0.353] | -0.1000 [-0.1085; -0.0908] | -0.0224 [-0.0244; -0.0202] |
| CatBoost persona-período (ingreso + agregados) − Aalen–Johansen por programa | 0.149 [0.120; 0.178] | 0.092 [0.079; 0.106] | 0.149 [0.120; 0.179] | 0.103 [0.088; 0.117] | -0.0617 [-0.0693; -0.0533] | -0.0143 [-0.0162; -0.0124] |

Lectura.

- **Agregados académicos.** Con el mismo modelo, agregarlos sube C(12) en 0,061 [0,047; 0,073] a 0,084 [0,072; 0,094] (Cox 0,078 [0,067; 0,089]; logística 0,084 [0,072; 0,094]; CatBoost 0,061 [0,047; 0,073]; MLP 0,082 [0,070; 0,093]) y baja el IBS entre 0,010 y 0,013. Es la mayor ganancia de la tarea.
- **Entre clásicos con agregados**, la logística y el Cox son equivalentes (C(12) 0,823 y 0,819; Δ = 0,004 [0,002; 0,006]); CatBoost es **peor** (0,800; -0,023 [-0,029; -0,016] frente a la logística).
- **Redes frente a clásicos con las mismas variables.** El MLP con agregados queda por debajo de la logística en C(12) (-0,007 [-0,012; -0,003]), empata con el Cox (-0,004 [-0,008; 0,001]) y mejora al Cox en IBS (-0,0018 [-0,0026; -0,0010]); la diferencia con la logística en IBS no es distinta de cero (0,0003 [-0,0004; 0,0010]). El MLP supera a CatBoost (0,016 [0,011; 0,021]).
- **La GRU sobre la secuencia de semestres** es el mejor modelo del corte: C(12) = 0,839 [0,829; 0,849] e IBS = 0,0422 [0,0402; 0,0443]. Gana al MLP con los mismos agregados (0,024 [0,021; 0,027] en C(12); -0,0032 [-0,0038; -0,0027] en IBS), al Cox con agregados (0,020 [0,015; 0,025]; -0,0050 [-0,0060; -0,0040]) y a CatBoost (0,039 [0,033; 0,046]). Frente a la logística con agregados la ventaja, por transitividad, es de aproximadamente 0,011 en C(12) (comparación directa no calculada).
- La variación entre semillas es pequeña (§7.2): sd de C(12) en test 0,005 para la GRU.

Valid (cohorte 2018):

| Modelo | C de Uno (t = 10) | C de Uno (t = 12) | C de Uno (t = 14) | AUC(t = 10) | AUC(t = 12) | AUC(t = 14) |
|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.800 [0.772; 0.831] | 0.737 [0.719; 0.755] | 0.703 [0.688; 0.720] | 0.809 [0.780; 0.840] | 0.766 [0.747; 0.786] | 0.726 [0.706; 0.745] |
| Cox causa-específico (ingreso) | 0.718 [0.685; 0.752] | 0.764 [0.746; 0.782] | 0.733 [0.718; 0.750] | 0.724 [0.691; 0.758] | 0.797 [0.778; 0.816] | 0.763 [0.744; 0.782] |
| Cox causa-específico (ingreso + agregados) | 0.842 [0.817; 0.869] | 0.861 [0.848; 0.873] | 0.838 [0.826; 0.851] | 0.850 [0.825; 0.877] | 0.889 [0.876; 0.903] | 0.873 [0.859; 0.887] |
| Logística persona-período (ingreso) | 0.745 [0.713; 0.777] | 0.767 [0.750; 0.784] | 0.734 [0.718; 0.751] | 0.751 [0.719; 0.785] | 0.798 [0.780; 0.817] | 0.764 [0.745; 0.784] |
| Logística persona-período (ingreso + agregados) | 0.876 [0.850; 0.899] | 0.868 [0.856; 0.881] | 0.838 [0.826; 0.850] | 0.883 [0.857; 0.906] | 0.892 [0.880; 0.906] | 0.876 [0.861; 0.890] |
| CatBoost persona-período (ingreso) | 0.850 [0.826; 0.878] | 0.759 [0.740; 0.777] | 0.720 [0.704; 0.736] | 0.857 [0.833; 0.885] | 0.788 [0.769; 0.808] | 0.759 [0.739; 0.778] |
| CatBoost persona-período (ingreso + agregados) | 0.925 [0.907; 0.942] | 0.863 [0.851; 0.876] | 0.831 [0.819; 0.844] | 0.931 [0.914; 0.947] | 0.891 [0.879; 0.905] | 0.873 [0.859; 0.888] |
| Red MLP de riesgos discretos (ingreso) | 0.840 [0.810; 0.871] | 0.763 [0.747; 0.782] | 0.718 [0.702; 0.733] | 0.846 [0.816; 0.877] | 0.797 [0.778; 0.817] | 0.755 [0.735; 0.774] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.934 [0.917; 0.949] | 0.866 [0.854; 0.879] | 0.832 [0.821; 0.844] | 0.940 [0.923; 0.955] | 0.898 [0.886; 0.911] | 0.878 [0.864; 0.892] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.948 [0.936; 0.960] | 0.880 [0.870; 0.892] | 0.843 [0.832; 0.854] | 0.954 [0.941; 0.966] | 0.909 [0.897; 0.920] | 0.888 [0.875; 0.901] |

| Modelo | Brier(t = 10) | Brier(t = 12) | Brier(t = 14) | IBS |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.0782 [0.0686; 0.0889] | 0.2305 [0.2205; 0.2404] | 0.2554 [0.2506; 0.2603] | 0.0596 [0.0562; 0.0632] |
| Aalen–Johansen por programa | 0.0694 [0.0609; 0.0787] | 0.1878 [0.1788; 0.1972] | 0.2152 [0.2076; 0.2235] | 0.0501 [0.0469; 0.0534] |
| Cox causa-específico (ingreso) | 0.0738 [0.0651; 0.0836] | 0.1809 [0.1720; 0.1898] | 0.2004 [0.1927; 0.2084] | 0.0501 [0.0469; 0.0534] |
| Cox causa-específico (ingreso + agregados) | 0.0666 [0.0584; 0.0752] | 0.1378 [0.1299; 0.1454] | 0.1451 [0.1366; 0.1533] | 0.0411 [0.0384; 0.0439] |
| Logística persona-período (ingreso) | 0.0712 [0.0627; 0.0805] | 0.1747 [0.1662; 0.1827] | 0.1973 [0.1895; 0.2050] | 0.0484 [0.0452; 0.0515] |
| Logística persona-período (ingreso + agregados) | 0.0602 [0.0529; 0.0677] | 0.1270 [0.1196; 0.1345] | 0.1409 [0.1322; 0.1492] | 0.0374 [0.0349; 0.0399] |
| CatBoost persona-período (ingreso) | 0.0651 [0.0573; 0.0738] | 0.1794 [0.1714; 0.1872] | 0.2004 [0.1934; 0.2072] | 0.0479 [0.0450; 0.0510] |
| CatBoost persona-período (ingreso + agregados) | 0.0493 [0.0421; 0.0561] | 0.1281 [0.1200; 0.1364] | 0.1434 [0.1347; 0.1519] | 0.0349 [0.0324; 0.0374] |
| Red MLP de riesgos discretos (ingreso) | 0.0633 [0.0561; 0.0713] | 0.1697 [0.1615; 0.1779] | 0.1994 [0.1922; 0.2071] | 0.0454 [0.0427; 0.0484] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.0476 [0.0413; 0.0538] | 0.1213 [0.1135; 0.1291] | 0.1411 [0.1320; 0.1502] | 0.0334 [0.0310; 0.0357] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.0440 [0.0379; 0.0499] | 0.1157 [0.1079; 0.1238] | 0.1350 [0.1260; 0.1436] | 0.0314 [0.0293; 0.0336] |

Ablación completa (valid):

| Escalón | Cox C(12) | Logística C(12) | CatBoost C(12) | Red C(12) | Cox IBS | Logística IBS | CatBoost IBS | Red IBS |
|---|---|---|---|---|---|---|---|---|
| 0. Aalen–Johansen global | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.0596 [0.0562; 0.0632] | 0.0596 [0.0562; 0.0632] | 0.0596 [0.0562; 0.0632] | 0.0596 [0.0562; 0.0632] |
| 1. Aalen–Johansen por programa | 0.737 [0.719; 0.755] | 0.737 [0.719; 0.755] | 0.737 [0.719; 0.755] | 0.737 [0.719; 0.755] | 0.0501 [0.0469; 0.0534] | 0.0501 [0.0469; 0.0534] | 0.0501 [0.0469; 0.0534] | 0.0501 [0.0469; 0.0534] |
| 2. Perfil de ingreso | 0.764 [0.746; 0.782] | 0.767 [0.750; 0.784] | 0.759 [0.740; 0.777] | 0.763 [0.747; 0.782] | 0.0501 [0.0469; 0.0534] | 0.0484 [0.0452; 0.0515] | 0.0479 [0.0450; 0.0510] | 0.0454 [0.0427; 0.0484] |
| 3. + agregados académicos al corte | 0.861 [0.848; 0.873] | 0.868 [0.856; 0.881] | 0.863 [0.851; 0.876] | 0.866 [0.854; 0.879] | 0.0411 [0.0384; 0.0439] | 0.0374 [0.0349; 0.0399] | 0.0349 [0.0324; 0.0374] | 0.0334 [0.0310; 0.0357] |
| 4. + secuencia de semestres (GRU) | — | — | — | 0.880 [0.870; 0.892] | — | — | — | 0.0314 [0.0293; 0.0336] |

Ablación completa (test):

| Escalón | Cox C(12) | Logística C(12) | CatBoost C(12) | Red C(12) | Cox IBS | Logística IBS | CatBoost IBS | Red IBS |
|---|---|---|---|---|---|---|---|---|
| 0. Aalen–Johansen global | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.0687 [0.0656; 0.0718] | 0.0687 [0.0656; 0.0718] | 0.0687 [0.0656; 0.0718] | 0.0687 [0.0656; 0.0718] |
| 1. Aalen–Johansen por programa | 0.708 [0.695; 0.721] | 0.708 [0.695; 0.721] | 0.708 [0.695; 0.721] | 0.708 [0.695; 0.721] | 0.0606 [0.0578; 0.0636] | 0.0606 [0.0578; 0.0636] | 0.0606 [0.0578; 0.0636] | 0.0606 [0.0578; 0.0636] |
| 2. Perfil de ingreso | 0.741 [0.728; 0.754] | 0.739 [0.727; 0.751] | 0.739 [0.727; 0.752] | 0.734 [0.721; 0.746] | 0.0588 [0.0560; 0.0617] | 0.0569 [0.0543; 0.0597] | 0.0573 [0.0546; 0.0602] | 0.0559 [0.0533; 0.0587] |
| 3. + agregados académicos al corte | 0.819 [0.808; 0.829] | 0.823 [0.812; 0.833] | 0.800 [0.788; 0.811] | 0.816 [0.805; 0.825] | 0.0472 [0.0450; 0.0496] | 0.0451 [0.0431; 0.0473] | 0.0463 [0.0440; 0.0487] | 0.0454 [0.0432; 0.0479] |
| 4. + secuencia de semestres (GRU) | — | — | — | 0.839 [0.829; 0.849] | — | — | — | 0.0422 [0.0402; 0.0443] |

### 6.3 Después de 4 semestres (k = 4)

Test (cohortes 2019-2020):

| Modelo | C de Uno (t = 10) | C de Uno (t = 12) | C de Uno (t = 14) | AUC(t = 10) | AUC(t = 12) | AUC(t = 14) |
|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.653 [0.629; 0.677] | 0.715 [0.702; 0.728] | 0.715 [0.698; 0.731] | 0.656 [0.630; 0.682] | 0.756 [0.741; 0.770] | 0.741 [0.719; 0.763] |
| Cox causa-específico (ingreso) | 0.700 [0.680; 0.720] | 0.743 [0.731; 0.755] | 0.739 [0.723; 0.754] | 0.712 [0.691; 0.732] | 0.789 [0.776; 0.803] | 0.773 [0.751; 0.793] |
| Cox causa-específico (ingreso + agregados) | 0.822 [0.805; 0.839] | 0.850 [0.841; 0.859] | 0.843 [0.831; 0.855] | 0.830 [0.813; 0.847] | 0.899 [0.888; 0.908] | 0.892 [0.878; 0.906] |
| Logística persona-período (ingreso) | 0.712 [0.691; 0.733] | 0.748 [0.736; 0.760] | 0.737 [0.722; 0.751] | 0.723 [0.701; 0.744] | 0.794 [0.781; 0.807] | 0.771 [0.749; 0.791] |
| Logística persona-período (ingreso + agregados) | 0.835 [0.818; 0.852] | 0.856 [0.847; 0.865] | 0.846 [0.833; 0.857] | 0.842 [0.826; 0.858] | 0.902 [0.891; 0.910] | 0.892 [0.878; 0.905] |
| CatBoost persona-período (ingreso) | 0.698 [0.676; 0.720] | 0.742 [0.731; 0.754] | 0.729 [0.713; 0.745] | 0.700 [0.678; 0.723] | 0.792 [0.778; 0.806] | 0.776 [0.755; 0.796] |
| CatBoost persona-período (ingreso + agregados) | 0.838 [0.822; 0.855] | 0.854 [0.846; 0.863] | 0.839 [0.828; 0.851] | 0.843 [0.826; 0.858] | 0.907 [0.897; 0.915] | 0.892 [0.878; 0.906] |
| Red MLP de riesgos discretos (ingreso) | 0.698 [0.675; 0.721] | 0.735 [0.723; 0.747] | 0.713 [0.697; 0.728] | 0.699 [0.675; 0.722] | 0.783 [0.768; 0.797] | 0.761 [0.739; 0.781] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.821 [0.803; 0.839] | 0.853 [0.844; 0.861] | 0.838 [0.826; 0.849] | 0.825 [0.806; 0.843] | 0.905 [0.895; 0.914] | 0.893 [0.879; 0.907] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.837 [0.819; 0.852] | 0.860 [0.851; 0.868] | 0.841 [0.829; 0.853] | 0.840 [0.822; 0.856] | 0.910 [0.900; 0.918] | 0.898 [0.885; 0.911] |

| Modelo | Brier(t = 10) | Brier(t = 12) | Brier(t = 14) | IBS |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.1370 [0.1266; 0.1472] | 0.2668 [0.2605; 0.2732] | 0.2526 [0.2520; 0.2532] | 0.0927 [0.0888; 0.0964] |
| Aalen–Johansen por programa | 0.1312 [0.1211; 0.1413] | 0.2213 [0.2141; 0.2293] | 0.2115 [0.2024; 0.2206] | 0.0808 [0.0768; 0.0846] |
| Cox causa-específico (ingreso) | 0.1289 [0.1195; 0.1384] | 0.2129 [0.2061; 0.2201] | 0.1959 [0.1879; 0.2043] | 0.0791 [0.0753; 0.0830] |
| Cox causa-específico (ingreso + agregados) | 0.1068 [0.0988; 0.1143] | 0.1328 [0.1269; 0.1395] | 0.1290 [0.1199; 0.1374] | 0.0564 [0.0535; 0.0592] |
| Logística persona-período (ingreso) | 0.1250 [0.1159; 0.1340] | 0.2064 [0.2004; 0.2128] | 0.1948 [0.1876; 0.2018] | 0.0767 [0.0732; 0.0803] |
| Logística persona-período (ingreso + agregados) | 0.0993 [0.0920; 0.1065] | 0.1256 [0.1200; 0.1322] | 0.1291 [0.1197; 0.1381] | 0.0530 [0.0505; 0.0556] |
| CatBoost persona-período (ingreso) | 0.1279 [0.1178; 0.1379] | 0.2008 [0.1948; 0.2069] | 0.1906 [0.1837; 0.1975] | 0.0753 [0.0717; 0.0789] |
| CatBoost persona-período (ingreso + agregados) | 0.1022 [0.0930; 0.1107] | 0.1225 [0.1162; 0.1293] | 0.1319 [0.1223; 0.1411] | 0.0507 [0.0480; 0.0534] |
| Red MLP de riesgos discretos (ingreso) | 0.1292 [0.1195; 0.1392] | 0.2131 [0.2055; 0.2205] | 0.1976 [0.1890; 0.2063] | 0.0777 [0.0739; 0.0815] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.1088 [0.0995; 0.1178] | 0.1238 [0.1170; 0.1316] | 0.1286 [0.1185; 0.1379] | 0.0538 [0.0509; 0.0568] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.1042 [0.0953; 0.1129] | 0.1201 [0.1130; 0.1282] | 0.1332 [0.1226; 0.1429] | 0.0518 [0.0490; 0.0545] |

Diferencias pareadas en test:

| Comparación (A − B, diferencia pareada) | ΔC (t = 10) | ΔC (t = 12) | ΔAUC (t = 10) | ΔAUC (t = 12) | ΔBrier (t = 12) | ΔIBS |
|---|---|---|---|---|---|---|
| Aalen–Johansen por programa − Aalen–Johansen global (sin covariables) | 0.153 [0.129; 0.177] | 0.215 [0.202; 0.228] | 0.156 [0.130; 0.182] | 0.256 [0.241; 0.270] | -0.0454 [-0.0514; -0.0390] | -0.0119 [-0.0136; -0.0102] |
| Cox causa-específico (ingreso) − Aalen–Johansen por programa | 0.047 [0.021; 0.074] | 0.028 [0.021; 0.034] | 0.056 [0.029; 0.085] | 0.033 [0.025; 0.041] | -0.0084 [-0.0115; -0.0056] | -0.0017 [-0.0026; -0.0008] |
| Cox causa-específico (ingreso + agregados) − Cox causa-específico (ingreso) | 0.122 [0.104; 0.140] | 0.108 [0.096; 0.119] | 0.119 [0.100; 0.137] | 0.110 [0.097; 0.122] | -0.0801 [-0.0864; -0.0739] | -0.0226 [-0.0247; -0.0206] |
| Logística persona-período (ingreso) − Cox causa-específico (ingreso) | 0.012 [0.006; 0.018] | 0.006 [0.002; 0.009] | 0.011 [0.005; 0.017] | 0.005 [0.001; 0.009] | -0.0065 [-0.0081; -0.0049] | -0.0024 [-0.0028; -0.0019] |
| Logística persona-período (ingreso + agregados) − Cox causa-específico (ingreso + agregados) | 0.013 [0.010; 0.017] | 0.006 [0.004; 0.008] | 0.012 [0.009; 0.015] | 0.002 [0.001; 0.004] | -0.0072 [-0.0093; -0.0053] | -0.0034 [-0.0041; -0.0027] |
| Logística persona-período (ingreso + agregados) − Logística persona-período (ingreso) | 0.123 [0.104; 0.140] | 0.108 [0.097; 0.119] | 0.120 [0.101; 0.137] | 0.107 [0.095; 0.119] | -0.0808 [-0.0876; -0.0741] | -0.0237 [-0.0259; -0.0213] |
| CatBoost persona-período (ingreso) − Logística persona-período (ingreso) | -0.014 [-0.034; 0.006] | -0.006 [-0.012; -0.001] | -0.022 [-0.043; -0.002] | -0.002 [-0.008; 0.004] | -0.0056 [-0.0078; -0.0035] | -0.0014 [-0.0021; -0.0007] |
| CatBoost persona-período (ingreso + agregados) − Logística persona-período (ingreso + agregados) | 0.004 [-0.007; 0.015] | -0.002 [-0.006; 0.002] | 0.000 [-0.010; 0.012] | 0.005 [0.001; 0.010] | -0.0031 [-0.0063; 0.0002] | -0.0023 [-0.0033; -0.0013] |
| CatBoost persona-período (ingreso + agregados) − CatBoost persona-período (ingreso) | 0.140 [0.121; 0.160] | 0.112 [0.101; 0.123] | 0.142 [0.123; 0.163] | 0.115 [0.101; 0.128] | -0.0783 [-0.0860; -0.0700] | -0.0246 [-0.0270; -0.0222] |
| CatBoost persona-período (ingreso + agregados) − Cox causa-específico (ingreso + agregados) | 0.017 [0.005; 0.029] | 0.004 [-0.001; 0.009] | 0.012 [0.000; 0.025] | 0.008 [0.003; 0.012] | -0.0103 [-0.0149; -0.0065] | -0.0058 [-0.0071; -0.0044] |
| Red MLP de riesgos discretos (ingreso) − CatBoost persona-período (ingreso) | -0.000 [-0.017; 0.017] | -0.007 [-0.014; -0.001] | -0.001 [-0.019; 0.017] | -0.009 [-0.016; -0.002] | 0.0123 [0.0092; 0.0155] | 0.0024 [0.0016; 0.0031] |
| Red MLP de riesgos discretos (ingreso) − Logística persona-período (ingreso) | -0.014 [-0.038; 0.012] | -0.013 [-0.019; -0.007] | -0.024 [-0.048; 0.004] | -0.012 [-0.018; -0.005] | 0.0067 [0.0038; 0.0096] | 0.0010 [0.0002; 0.0017] |
| Red MLP de riesgos discretos (ingreso + agregados) − Red MLP de riesgos discretos (ingreso) | 0.123 [0.106; 0.141] | 0.118 [0.107; 0.129] | 0.126 [0.109; 0.143] | 0.122 [0.109; 0.135] | -0.0893 [-0.0975; -0.0807] | -0.0238 [-0.0261; -0.0215] |
| Red MLP de riesgos discretos (ingreso + agregados) − CatBoost persona-período (ingreso + agregados) | -0.017 [-0.029; -0.004] | -0.002 [-0.005; 0.002] | -0.017 [-0.030; -0.004] | -0.002 [-0.006; 0.002] | 0.0013 [-0.0020; 0.0048] | 0.0031 [0.0021; 0.0042] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) − Red MLP de riesgos discretos (ingreso + agregados) | 0.015 [0.009; 0.022] | 0.007 [0.004; 0.010] | 0.015 [0.008; 0.021] | 0.005 [0.002; 0.008] | -0.0037 [-0.0066; -0.0009] | -0.0020 [-0.0028; -0.0012] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) − CatBoost persona-período (ingreso + agregados) | -0.002 [-0.015; 0.012] | 0.005 [0.001; 0.010] | -0.003 [-0.016; 0.011] | 0.003 [-0.002; 0.008] | -0.0024 [-0.0063; 0.0016] | 0.0011 [0.0001; 0.0022] |
| Red MLP de riesgos discretos (ingreso) − Cox causa-específico (ingreso) | -0.002 [-0.026; 0.024] | -0.008 [-0.015; -0.000] | -0.013 [-0.038; 0.015] | -0.007 [-0.014; 0.002] | 0.0002 [-0.0029; 0.0033] | -0.0014 [-0.0023; -0.0006] |
| Red MLP de riesgos discretos (ingreso + agregados) − Logística persona-período (ingreso + agregados) | -0.013 [-0.029; 0.002] | -0.004 [-0.007; -0.000] | -0.017 [-0.034; -0.001] | 0.003 [-0.000; 0.006] | -0.0018 [-0.0045; 0.0007] | 0.0008 [-0.0002; 0.0018] |
| Red MLP de riesgos discretos (ingreso + agregados) − Cox causa-específico (ingreso + agregados) | -0.000 [-0.016; 0.016] | 0.002 [-0.001; 0.006] | -0.005 [-0.022; 0.012] | 0.006 [0.002; 0.009] | -0.0090 [-0.0127; -0.0056] | -0.0026 [-0.0038; -0.0015] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) − Cox causa-específico (ingreso + agregados) | 0.015 [-0.002; 0.032] | 0.009 [0.005; 0.014] | 0.010 [-0.008; 0.027] | 0.011 [0.006; 0.015] | -0.0127 [-0.0175; -0.0080] | -0.0047 [-0.0061; -0.0032] |
| Logística persona-período (ingreso) − Aalen–Johansen por programa | 0.059 [0.032; 0.086] | 0.033 [0.026; 0.042] | 0.067 [0.039; 0.095] | 0.038 [0.029; 0.047] | -0.0149 [-0.0188; -0.0115] | -0.0041 [-0.0052; -0.0031] |
| CatBoost persona-período (ingreso) − Aalen–Johansen por programa | 0.045 [0.021; 0.068] | 0.027 [0.019; 0.036] | 0.044 [0.019; 0.069] | 0.036 [0.027; 0.045] | -0.0206 [-0.0246; -0.0166] | -0.0055 [-0.0066; -0.0044] |
| Cox causa-específico (ingreso) − Aalen–Johansen global (sin covariables) | 0.200 [0.180; 0.220] | 0.243 [0.231; 0.255] | 0.212 [0.191; 0.232] | 0.289 [0.276; 0.303] | -0.0539 [-0.0586; -0.0488] | -0.0136 [-0.0148; -0.0124] |
| Red MLP de riesgos discretos (ingreso) − CatBoost persona-período (ingreso + agregados) | -0.140 [-0.162; -0.118] | -0.120 [-0.131; -0.107] | -0.144 [-0.167; -0.121] | -0.124 [-0.138; -0.110] | 0.0906 [0.0813; 0.0993] | 0.0270 [0.0243; 0.0295] |
| CatBoost persona-período (ingreso + agregados) − Aalen–Johansen global (sin covariables) | 0.338 [0.322; 0.355] | 0.354 [0.346; 0.363] | 0.343 [0.326; 0.358] | 0.407 [0.397; 0.415] | -0.1443 [-0.1533; -0.1342] | -0.0420 [-0.0450; -0.0389] |
| CatBoost persona-período (ingreso + agregados) − Aalen–Johansen por programa | 0.185 [0.159; 0.211] | 0.139 [0.127; 0.152] | 0.187 [0.159; 0.213] | 0.151 [0.136; 0.166] | -0.0988 [-0.1080; -0.0899] | -0.0301 [-0.0331; -0.0273] |

Lectura.

- Los agregados vuelven a ser la ganancia dominante (C(12) de 0,743 a 0,850 en el Cox).
- **La ventaja neuronal es marginal.** Con agregados, la logística (0,856), CatBoost (0,854) y la GRU (0,860) quedan muy cerca en C(12). La GRU supera apenas a CatBoost (0,005 [0,001; 0,010]) y tiene **peor IBS** (0,0011 [0,0001; 0,0022]); CatBoost tiene el mejor IBS (0,0507 [0,0480; 0,0534]). La GRU gana al MLP con agregados por muy poco (0,007 [0,004; 0,010]) y supera al Cox con agregados en C(12) (0,009 [0,005; 0,014]) y en IBS (-0,0047 [-0,0061; -0,0032]).
- El MLP con agregados es **peor** que la logística (-0,004 [-0,007; -0,000]), aunque esa comparación es frágil por la variación entre semillas del MLP (§7.2).
- La secuencia añade poco al avanzar el corte: el resumen en agregados ya contiene casi toda la información del trayecto.

Valid (cohorte 2018):

| Modelo | C de Uno (t = 10) | C de Uno (t = 12) | C de Uno (t = 14) | AUC(t = 10) | AUC(t = 12) | AUC(t = 14) |
|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.798 [0.772; 0.822] | 0.713 [0.695; 0.730] | 0.687 [0.671; 0.703] | 0.818 [0.790; 0.843] | 0.764 [0.743; 0.786] | 0.729 [0.703; 0.752] |
| Cox causa-específico (ingreso) | 0.669 [0.640; 0.698] | 0.731 [0.713; 0.749] | 0.707 [0.691; 0.723] | 0.682 [0.651; 0.712] | 0.784 [0.763; 0.804] | 0.751 [0.726; 0.774] |
| Cox causa-específico (ingreso + agregados) | 0.876 [0.854; 0.900] | 0.883 [0.869; 0.897] | 0.861 [0.848; 0.874] | 0.883 [0.860; 0.906] | 0.916 [0.901; 0.929] | 0.900 [0.885; 0.913] |
| Logística persona-período (ingreso) | 0.687 [0.659; 0.714] | 0.731 [0.713; 0.748] | 0.704 [0.687; 0.720] | 0.699 [0.669; 0.728] | 0.784 [0.762; 0.804] | 0.755 [0.731; 0.778] |
| Logística persona-período (ingreso + agregados) | 0.895 [0.873; 0.917] | 0.888 [0.874; 0.901] | 0.860 [0.847; 0.873] | 0.900 [0.878; 0.923] | 0.916 [0.902; 0.930] | 0.900 [0.885; 0.913] |
| CatBoost persona-período (ingreso) | 0.853 [0.829; 0.874] | 0.732 [0.715; 0.750] | 0.690 [0.674; 0.707] | 0.865 [0.840; 0.888] | 0.780 [0.757; 0.800] | 0.750 [0.725; 0.771] |
| CatBoost persona-período (ingreso + agregados) | 0.929 [0.910; 0.945] | 0.876 [0.863; 0.889] | 0.842 [0.829; 0.854] | 0.934 [0.916; 0.951] | 0.913 [0.899; 0.926] | 0.891 [0.875; 0.905] |
| Red MLP de riesgos discretos (ingreso) | 0.859 [0.831; 0.885] | 0.738 [0.721; 0.754] | 0.688 [0.672; 0.703] | 0.867 [0.838; 0.894] | 0.792 [0.770; 0.813] | 0.754 [0.731; 0.777] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.929 [0.910; 0.947] | 0.884 [0.871; 0.897] | 0.846 [0.833; 0.859] | 0.935 [0.915; 0.952] | 0.921 [0.907; 0.933] | 0.897 [0.881; 0.911] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.949 [0.934; 0.962] | 0.900 [0.888; 0.911] | 0.864 [0.852; 0.875] | 0.955 [0.940; 0.967] | 0.934 [0.923; 0.945] | 0.918 [0.905; 0.930] |

| Modelo | Brier(t = 10) | Brier(t = 12) | Brier(t = 14) | IBS |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.1179 [0.1044; 0.1319] | 0.2640 [0.2556; 0.2728] | 0.2530 [0.2523; 0.2537] | 0.1015 [0.0953; 0.1084] |
| Aalen–Johansen por programa | 0.1070 [0.0950; 0.1189] | 0.2120 [0.2022; 0.2216] | 0.2127 [0.2040; 0.2218] | 0.0867 [0.0804; 0.0934] |
| Cox causa-específico (ingreso) | 0.1119 [0.0993; 0.1249] | 0.2078 [0.1991; 0.2164] | 0.2011 [0.1925; 0.2099] | 0.0878 [0.0818; 0.0944] |
| Cox causa-específico (ingreso + agregados) | 0.0767 [0.0676; 0.0867] | 0.1328 [0.1232; 0.1427] | 0.1263 [0.1174; 0.1354] | 0.0585 [0.0548; 0.0630] |
| Logística persona-período (ingreso) | 0.1085 [0.0968; 0.1209] | 0.2012 [0.1937; 0.2088] | 0.1948 [0.1871; 0.2028] | 0.0849 [0.0793; 0.0911] |
| Logística persona-período (ingreso + agregados) | 0.0693 [0.0612; 0.0782] | 0.1200 [0.1110; 0.1293] | 0.1211 [0.1120; 0.1306] | 0.0506 [0.0472; 0.0543] |
| CatBoost persona-período (ingreso) | 0.0911 [0.0811; 0.1013] | 0.1982 [0.1905; 0.2060] | 0.1960 [0.1886; 0.2036] | 0.0793 [0.0745; 0.0849] |
| CatBoost persona-período (ingreso + agregados) | 0.0578 [0.0496; 0.0665] | 0.1189 [0.1091; 0.1286] | 0.1295 [0.1200; 0.1391] | 0.0475 [0.0440; 0.0513] |
| Red MLP de riesgos discretos (ingreso) | 0.0859 [0.0769; 0.0956] | 0.1889 [0.1810; 0.1970] | 0.1926 [0.1844; 0.2011] | 0.0760 [0.0712; 0.0812] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.0578 [0.0502; 0.0660] | 0.1127 [0.1030; 0.1234] | 0.1242 [0.1142; 0.1342] | 0.0500 [0.0459; 0.0543] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.0505 [0.0433; 0.0583] | 0.1001 [0.0904; 0.1096] | 0.1101 [0.1001; 0.1200] | 0.0451 [0.0415; 0.0489] |

Ablación completa (test):

| Escalón | Cox C(12) | Logística C(12) | CatBoost C(12) | Red C(12) | Cox IBS | Logística IBS | CatBoost IBS | Red IBS |
|---|---|---|---|---|---|---|---|---|
| 0. Aalen–Johansen global | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.0927 [0.0888; 0.0964] | 0.0927 [0.0888; 0.0964] | 0.0927 [0.0888; 0.0964] | 0.0927 [0.0888; 0.0964] |
| 1. Aalen–Johansen por programa | 0.715 [0.702; 0.728] | 0.715 [0.702; 0.728] | 0.715 [0.702; 0.728] | 0.715 [0.702; 0.728] | 0.0808 [0.0768; 0.0846] | 0.0808 [0.0768; 0.0846] | 0.0808 [0.0768; 0.0846] | 0.0808 [0.0768; 0.0846] |
| 2. Perfil de ingreso | 0.743 [0.731; 0.755] | 0.748 [0.736; 0.760] | 0.742 [0.731; 0.754] | 0.735 [0.723; 0.747] | 0.0791 [0.0753; 0.0830] | 0.0767 [0.0732; 0.0803] | 0.0753 [0.0717; 0.0789] | 0.0777 [0.0739; 0.0815] |
| 3. + agregados académicos al corte | 0.850 [0.841; 0.859] | 0.856 [0.847; 0.865] | 0.854 [0.846; 0.863] | 0.853 [0.844; 0.861] | 0.0564 [0.0535; 0.0592] | 0.0530 [0.0505; 0.0556] | 0.0507 [0.0480; 0.0534] | 0.0538 [0.0509; 0.0568] |
| 4. + secuencia de semestres (GRU) | — | — | — | 0.860 [0.851; 0.868] | — | — | — | 0.0518 [0.0490; 0.0545] |

## 7. Análisis transversal

### 7.1 ¿Qué modelo, y es mejor la red?

Mejor clásico elegido por IBS en valid, y mejor red por IBS en valid:

| k | Mejor modelo clásico en valid (IBS) | IBS valid | Mejor red en valid (IBS) | IBS valid |
|---|---|---|---|---|
| 0 | CatBoost persona-período (ingreso) | 0.0444 | Red MLP de riesgos discretos (ingreso) | 0.0417 |
| 2 | CatBoost persona-período (ingreso + agregados) | 0.0349 | Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.0314 |
| 4 | CatBoost persona-período (ingreso + agregados) | 0.0475 | Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.0451 |

Resumen de la ablación, test (C(12) con IC; IBS con IC):

| Escalón | Cox C(12) | Logística C(12) | CatBoost C(12) | Red C(12) | Cox IBS | Logística IBS | CatBoost IBS | Red IBS |
|---|---|---|---|---|---|---|---|---|
| 0. Aalen–Johansen global | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.0541 [0.0517; 0.0565] | 0.0541 [0.0517; 0.0565] | 0.0541 [0.0517; 0.0565] | 0.0541 [0.0517; 0.0565] |
| 1. Aalen–Johansen por programa | 0.706 [0.692; 0.718] | 0.706 [0.692; 0.718] | 0.706 [0.692; 0.718] | 0.706 [0.692; 0.718] | 0.0480 [0.0459; 0.0503] | 0.0480 [0.0459; 0.0503] | 0.0480 [0.0459; 0.0503] | 0.0480 [0.0459; 0.0503] |
| 2. Perfil de ingreso | 0.740 [0.727; 0.752] | 0.742 [0.729; 0.754] | 0.739 [0.727; 0.750] | 0.738 [0.726; 0.750] | 0.0466 [0.0446; 0.0487] | 0.0454 [0.0434; 0.0474] | 0.0460 [0.0439; 0.0481] | 0.0451 [0.0431; 0.0472] |
| 3. + agregados académicos al corte | — | — | — | — | — | — | — | — |
| 4. + secuencia de semestres (GRU) | — | — | — | — | — | — | — | — |

Respuestas a las preguntas del encargo:

- *¿Algo vence a Kaplan–Meier / Aalen–Johansen por programa?* Sí, siempre: el perfil de ingreso suma 0,034 [0,027; 0,041] de C(12) en test; los agregados, 0,078 [0,067; 0,089] a 0,108 [0,096; 0,119] más.
- *¿Algo vence al Cox causa-específico?* La logística persona-período lo supera por poco y de manera consistente con agregados (0,004 [0,002; 0,006] y 0,006 [0,004; 0,008] de C(12); IBS -0,0021 [-0,0026; -0,0015] y -0,0034 [-0,0041; -0,0027]); con las mismas variables, la red añade un poco en IBS. Solo la GRU de k = 2 mejora de forma clara en discriminación (0,020 [0,015; 0,025]).
- *¿Las redes agregan señal?* Poca, y solo con la secuencia en k = 2. En k = 0 y k = 4 no hay mejora de discriminación frente al mejor clásico, y en k = 4 el mejor IBS es de CatBoost. Se conserva el modelo clásico donde las redes no superan: ver §9.

### 7.2 Estabilidad entre semillas y entre horizontes

Resultados de las redes por semilla (media ± sd de 3 semillas):

| k | Red (3 semillas) | C(12) valid (media ± sd) | C(12) test (media ± sd) | IBS test (media ± sd) |
|---|---|---|---|---|
| 0 | Red MLP de riesgos discretos (ingreso) | 0.752 ± 0.005 | 0.733 ± 0.002 | 0.0454 ± 0.0007 |
| 2 | Red MLP de riesgos discretos (ingreso) | 0.758 ± 0.003 | 0.728 ± 0.004 | 0.0566 ± 0.0007 |
| 2 | Red MLP de riesgos discretos (ingreso + agregados) | 0.864 ± 0.008 | 0.813 ± 0.006 | 0.0461 ± 0.0007 |
| 2 | Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.877 ± 0.005 | 0.836 ± 0.000 | 0.0429 ± 0.0004 |
| 4 | Red MLP de riesgos discretos (ingreso) | 0.734 ± 0.004 | 0.731 ± 0.008 | 0.0783 ± 0.0012 |
| 4 | Red MLP de riesgos discretos (ingreso + agregados) | 0.881 ± 0.002 | 0.850 ± 0.003 | 0.0547 ± 0.0006 |
| 4 | Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.897 ± 0.004 | 0.857 ± 0.001 | 0.0531 ± 0.0006 |

Las desviaciones entre semillas (≤ 0,014 en C, la mayor en el MLP de ingreso de k = 4; la GRU tiene 0,005 y 0,004) son menores que las diferencias entre modelos que se destacan arriba, salvo el MLP con agregados en k = 4 (sd 0,007), cuya comparación con la logística es por tanto frágil. CatBoost cambia de signo entre horizontes en valid (C(10) alto, C(12) y C(14) bajos): probablemente aprende un patrón de calendario por semestre (el egreso se registra en bloques, P60) y un solo horizonte engaña; por eso se reportan 10, 12 y 14 y el IBS.

### 7.3 Calibración y deriva entre cohortes

Incidencia acumulada a cada horizonte frente a la observada (test):

| Horizonte (semestres desde la admisión) | Episodios con seguimiento | Incidencia observada | Aalen–Johansen global (sin covariables) | Aalen–Johansen por programa | Cox causa-específico (ingreso) | CatBoost persona-período (ingreso) |
|---|---|---|---|---|---|---|
| 10 | 4.738 | 12,0 % | 4,4 % | 4,7 % | 5,1 % | 3,6 % |
| 12 | 4.738 | 35,0 % | 21,1 % | 22,1 % | 23,1 % | 23,2 % |
| 14 | 2.511 | 44,7 % | 33,7 % | 35,3 % | 38,8 % | 38,5 % |

| Horizonte (semestres desde la admisión) | Episodios con seguimiento | Incidencia observada | Aalen–Johansen global (sin covariables) | Aalen–Johansen por programa | Cox causa-específico (ingreso) | Cox causa-específico (ingreso + agregados) | CatBoost persona-período (ingreso + agregados) | CatBoost persona-período (ingreso) | Red MLP de riesgos discretos (ingreso + agregados) | Red GRU de riesgos discretos (ingreso + agregados + secuencia) |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 4.343 | 13,1 % | 4,8 % | 5,1 % | 5,4 % | 7,7 % | 5,9 % | 4,2 % | 5,4 % | 6,0 % |
| 12 | 4.343 | 38,2 % | 23,6 % | 24,2 % | 25,1 % | 33,1 % | 36,4 % | 26,1 % | 36,2 % | 37,3 % |
| 14 | 2.230 | 50,3 % | 37,7 % | 38,8 % | 42,4 % | 47,5 % | 47,6 % | 43,1 % | 50,5 % | 53,5 % |

| Horizonte (semestres desde la admisión) | Episodios con seguimiento | Incidencia observada | Aalen–Johansen global (sin covariables) | Aalen–Johansen por programa | Cox causa-específico (ingreso) | Cox causa-específico (ingreso + agregados) | CatBoost persona-período (ingreso + agregados) | CatBoost persona-período (ingreso) | Red MLP de riesgos discretos (ingreso + agregados) | Red GRU de riesgos discretos (ingreso + agregados + secuencia) |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 3.711 | 15,2 % | 6,2 % | 5,8 % | 6,6 % | 9,9 % | 7,6 % | 5,5 % | 6,2 % | 7,4 % |
| 12 | 3.711 | 44,6 % | 30,5 % | 29,6 % | 30,1 % | 39,0 % | 45,7 % | 33,8 % | 42,8 % | 46,5 % |
| 14 | 1.925 | 58,1 % | 48,5 % | 48,3 % | 49,8 % | 55,8 % | 60,5 % | 54,3 % | 60,5 % | 64,9 % |

Calibración por decil a 12 semestres (test):

| Decil de riesgo | Aalen–Johansen por programa: predicho / observado | Cox causa-específico (ingreso): predicho / observado | CatBoost persona-período (ingreso): predicho / observado |
|---|---|---|---|
| 1 | 0.008 / 0.137 | 0.034 / 0.046 | 0.026 / 0.023 |
| 2 | 0.033 / 0.091 | 0.069 / 0.093 | 0.057 / 0.097 |
| 3 | 0.060 / 0.113 | 0.103 / 0.169 | 0.094 / 0.177 |
| 4 | 0.100 / 0.242 | 0.138 / 0.213 | 0.139 / 0.228 |
| 5 | 0.167 / 0.298 | 0.174 / 0.268 | 0.189 / 0.302 |
| 6 | 0.223 / 0.341 | 0.225 / 0.382 | 0.243 / 0.380 |
| 7 | 0.273 / 0.594 | 0.283 / 0.487 | 0.294 / 0.430 |
| 8 | 0.374 / 0.505 | 0.344 / 0.538 | 0.345 / 0.525 |
| 9 | 0.440 / 0.593 | 0.415 / 0.631 | 0.414 / 0.641 |
| 10 | 0.547 / 0.562 | 0.530 / 0.674 | 0.517 / 0.698 |

| Decil de riesgo | Aalen–Johansen por programa: predicho / observado | Cox causa-específico (ingreso + agregados): predicho / observado | CatBoost persona-período (ingreso + agregados): predicho / observado | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicho / observado |
|---|---|---|---|---|
| 1 | 0.009 / 0.152 | 0.005 / 0.014 | 0.005 / 0.044 | 0.002 / 0.014 |
| 2 | 0.035 / 0.097 | 0.035 / 0.044 | 0.016 / 0.099 | 0.011 / 0.021 |
| 3 | 0.067 / 0.150 | 0.090 / 0.106 | 0.038 / 0.081 | 0.036 / 0.046 |
| 4 | 0.113 / 0.271 | 0.165 / 0.170 | 0.100 / 0.156 | 0.088 / 0.136 |
| 5 | 0.181 / 0.324 | 0.240 / 0.272 | 0.215 / 0.286 | 0.200 / 0.288 |
| 6 | 0.238 / 0.385 | 0.324 / 0.373 | 0.383 / 0.385 | 0.371 / 0.417 |
| 7 | 0.292 / 0.582 | 0.429 / 0.545 | 0.536 / 0.515 | 0.556 / 0.520 |
| 8 | 0.434 / 0.573 | 0.545 / 0.645 | 0.677 / 0.611 | 0.728 / 0.705 |
| 9 | 0.479 / 0.655 | 0.667 / 0.781 | 0.787 / 0.767 | 0.831 / 0.809 |
| 10 | 0.587 / 0.605 | 0.809 / 0.866 | 0.881 / 0.873 | 0.908 / 0.862 |

| Decil de riesgo | Aalen–Johansen por programa: predicho / observado | Cox causa-específico (ingreso + agregados): predicho / observado | CatBoost persona-período (ingreso + agregados): predicho / observado | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicho / observado |
|---|---|---|---|---|
| 1 | 0.008 / 0.114 | 0.004 / 0.013 | 0.005 / 0.024 | 0.001 / 0.005 |
| 2 | 0.048 / 0.163 | 0.035 / 0.051 | 0.026 / 0.019 | 0.007 / 0.046 |
| 3 | 0.108 / 0.188 | 0.094 / 0.078 | 0.066 / 0.057 | 0.036 / 0.062 |
| 4 | 0.169 / 0.345 | 0.176 / 0.173 | 0.168 / 0.191 | 0.118 / 0.143 |
| 5 | 0.211 / 0.373 | 0.262 / 0.294 | 0.337 / 0.340 | 0.323 / 0.321 |
| 6 | 0.302 / 0.516 | 0.389 / 0.526 | 0.547 / 0.472 | 0.593 / 0.488 |
| 7 | 0.375 / 0.721 | 0.529 / 0.712 | 0.738 / 0.709 | 0.791 / 0.720 |
| 8 | 0.536 / 0.686 | 0.666 / 0.784 | 0.829 / 0.792 | 0.883 / 0.852 |
| 9 | 0.570 / 0.644 | 0.814 / 0.881 | 0.902 / 0.889 | 0.931 / 0.895 |
| 10 | 0.650 / 0.753 | 0.927 / 0.946 | 0.958 / 0.965 | 0.966 / 0.927 |

Lectura.

- Los modelos de **solo ingreso** subestiman sistemáticamente el egreso en test (predicen 23,1 %–33,8 % a 12 semestres frente al 35,0 %–44,6 % observado, según el corte). La causa no es el modelo sino la **deriva de cohorte**: la incidencia acumulada de egreso a 12 semestres es 21,1 % en train y 35,0 % en test (la mediana pasó de 13 a 11 semestres). Ninguna variable de ingreso explica ese cambio.
- Los modelos con **agregados** absorben la mayor parte de la deriva porque observan el avance real: en k = 2 el Cox con agregados predice 33,1 % (observado 38,2 %), CatBoost 36,4 %, la GRU 37,3 % y el MLP 36,2 %; en k = 4, 39,0 %, 45,7 %, 46,5 % y 42,8 % frente al 44,6 % observado. Los árboles y las redes tienden a sobrestimar un poco en k = 4 (+4,0 pp la GRU); el Cox, a subestimar.
- Los deciles extremos están bien ordenados; en los deciles bajos de k = 0, la tasa observada es mayor que la predicha (el riesgo mínimo está subestimado).

Calibración por cohorte (k = 2):

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicha / AUC |
|---|---|---|---|---|---|---|
| 2019 | 2.230 | 0.381 | 0.236 / 0.500 | 0.245 / 0.760 | 0.261 / 0.801 | 0.344 / 0.887 |
| 2020 | 2.113 | 0.382 | 0.236 / 0.500 | 0.238 / 0.714 | 0.240 / 0.749 | 0.403 / 0.876 |

### 7.4 Control posterior (cohortes 2021 en adelante, horizontes 8 y 10)

Es solo un control de estabilidad: pocos episodios (§2) y casi todo censurado. No se usa para elegir.

| Modelo | C de Uno (t = 8) | C de Uno (t = 10) | AUC(t = 8) | AUC(t = 10) |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.501 [0.460; 0.542] | 0.611 [0.582; 0.637] | 0.497 [0.456; 0.540] | 0.607 [0.577; 0.636] |
| Cox causa-específico (ingreso) | 0.623 [0.587; 0.665] | 0.766 [0.744; 0.791] | 0.629 [0.591; 0.671] | 0.792 [0.770; 0.814] |
| Cox causa-específico (ingreso + agregados) | 0.864 [0.833; 0.895] | 0.855 [0.836; 0.874] | 0.869 [0.837; 0.899] | 0.871 [0.854; 0.890] |
| Logística persona-período (ingreso) | 0.614 [0.576; 0.658] | 0.763 [0.740; 0.787] | 0.620 [0.581; 0.664] | 0.788 [0.767; 0.811] |
| Logística persona-período (ingreso + agregados) | 0.855 [0.825; 0.888] | 0.852 [0.833; 0.871] | 0.860 [0.830; 0.894] | 0.868 [0.852; 0.886] |
| CatBoost persona-período (ingreso) | 0.922 [0.894; 0.947] | 0.771 [0.750; 0.793] | 0.920 [0.893; 0.945] | 0.760 [0.738; 0.781] |
| CatBoost persona-período (ingreso + agregados) | 0.978 [0.972; 0.983] | 0.859 [0.842; 0.875] | 0.978 [0.972; 0.983] | 0.852 [0.834; 0.869] |
| Red MLP de riesgos discretos (ingreso) | 0.783 [0.753; 0.817] | 0.596 [0.567; 0.629] | 0.784 [0.753; 0.819] | 0.575 [0.545; 0.607] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.892 [0.870; 0.913] | 0.725 [0.700; 0.750] | 0.895 [0.870; 0.917] | 0.710 [0.685; 0.736] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.962 [0.950; 0.972] | 0.775 [0.752; 0.797] | 0.963 [0.950; 0.973] | 0.761 [0.736; 0.784] |

| Modelo | C de Uno (t = 8) | C de Uno (t = 10) | AUC(t = 8) | AUC(t = 10) |
|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] | 0.500 [0.500; 0.500] |
| Aalen–Johansen por programa | 0.512 [0.469; 0.553] | 0.622 [0.593; 0.651] | 0.508 [0.464; 0.550] | 0.613 [0.583; 0.643] |
| Cox causa-específico (ingreso) | 0.641 [0.600; 0.680] | 0.765 [0.738; 0.786] | 0.648 [0.606; 0.686] | 0.796 [0.770; 0.817] |
| Cox causa-específico (ingreso + agregados) | 0.955 [0.936; 0.971] | 0.907 [0.893; 0.920] | 0.958 [0.938; 0.974] | 0.910 [0.897; 0.923] |
| Logística persona-período (ingreso) | 0.758 [0.724; 0.788] | 0.809 [0.785; 0.827] | 0.763 [0.727; 0.793] | 0.828 [0.804; 0.848] |
| Logística persona-período (ingreso + agregados) | 0.969 [0.949; 0.983] | 0.912 [0.899; 0.924] | 0.970 [0.950; 0.984] | 0.914 [0.901; 0.926] |
| CatBoost persona-período (ingreso) | 0.923 [0.897; 0.947] | 0.761 [0.739; 0.787] | 0.921 [0.894; 0.945] | 0.746 [0.723; 0.772] |
| CatBoost persona-período (ingreso + agregados) | 0.975 [0.958; 0.987] | 0.899 [0.883; 0.913] | 0.974 [0.957; 0.986] | 0.890 [0.875; 0.905] |
| Red MLP de riesgos discretos (ingreso) | 0.807 [0.774; 0.835] | 0.622 [0.590; 0.655] | 0.811 [0.776; 0.840] | 0.596 [0.561; 0.630] |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.930 [0.912; 0.946] | 0.793 [0.768; 0.816] | 0.937 [0.918; 0.953] | 0.775 [0.748; 0.799] |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.947 [0.931; 0.959] | 0.851 [0.834; 0.870] | 0.953 [0.937; 0.965] | 0.837 [0.817; 0.856] |

Lectura. Los modelos de solo ingreso con árboles o red (CatBoost y MLP) son **erráticos**: el C de CatBoost pasa de 0,922 (t = 8) a 0,771 (t = 10) en k = 2 y de 0,923 a 0,761 en k = 4, y el del MLP queda en 0,622–0,596 en t = 10, una inversión sin explicación sustantiva que no se ve en Cox ni en logística; probablemente por el mismo patrón de calendario (§7.2). Con agregados, la logística es la más estable (C(10) = 0,852 en k = 2 y 0,912 en k = 4); el MLP y la GRU caen a 0,725–0,851 en t = 10 y CatBoost conserva 0,859 en k = 2 y 0,899 en k = 4. Es otra razón para no preferir los modelos de mayor capacidad sin revisión.

### 7.5 Subgrupos y equidad

**Sexo** (solo para evaluación de equidad, nunca como variable): las mujeres egresan más (k = 2: 44,2 % frente a 33,1 % a 12 semestres en test). Brecha de AUC (F − M) en test:

| Modelo | Incidencia F | Incidencia M | Predicha F | Predicha M | AUC F | AUC M | ΔAUC (F−M) | Brecha de calibración F | Brecha de calibración M |
|---|---|---|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.404 | 0.305 | 0.211 | 0.211 | 0.500 | 0.500 | +0.000 | -0.192 | -0.093 |
| Aalen–Johansen por programa | 0.404 | 0.305 | 0.258 | 0.190 | 0.726 | 0.724 | +0.002 | -0.146 | -0.115 |
| Cox causa-específico (ingreso) | 0.404 | 0.305 | 0.267 | 0.202 | 0.764 | 0.765 | -0.001 | -0.137 | -0.103 |
| CatBoost persona-período (ingreso) | 0.404 | 0.305 | 0.258 | 0.210 | 0.770 | 0.768 | +0.002 | -0.146 | -0.095 |

| Modelo | Incidencia F | Incidencia M | Predicha F | Predicha M | AUC F | AUC M | ΔAUC (F−M) | Brecha de calibración F | Brecha de calibración M |
|---|---|---|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.442 | 0.331 | 0.236 | 0.236 | 0.500 | 0.500 | +0.000 | -0.206 | -0.095 |
| Aalen–Johansen por programa | 0.442 | 0.331 | 0.282 | 0.208 | 0.734 | 0.725 | +0.009 | -0.160 | -0.123 |
| Cox causa-específico (ingreso) | 0.442 | 0.331 | 0.291 | 0.217 | 0.770 | 0.769 | +0.001 | -0.151 | -0.113 |
| Cox causa-específico (ingreso + agregados) | 0.442 | 0.331 | 0.386 | 0.284 | 0.843 | 0.867 | -0.024 | -0.056 | -0.046 |
| CatBoost persona-período (ingreso + agregados) | 0.442 | 0.331 | 0.422 | 0.315 | 0.824 | 0.852 | -0.028 | -0.020 | -0.015 |
| CatBoost persona-período (ingreso) | 0.442 | 0.331 | 0.294 | 0.234 | 0.776 | 0.771 | +0.004 | -0.148 | -0.097 |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.442 | 0.331 | 0.417 | 0.317 | 0.846 | 0.869 | -0.023 | -0.026 | -0.014 |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.442 | 0.331 | 0.426 | 0.328 | 0.867 | 0.887 | -0.021 | -0.016 | -0.002 |

| Modelo | Incidencia F | Incidencia M | Predicha F | Predicha M | AUC F | AUC M | ΔAUC (F−M) | Brecha de calibración F | Brecha de calibración M |
|---|---|---|---|---|---|---|---|---|---|
| Aalen–Johansen global (sin covariables) | 0.512 | 0.389 | 0.305 | 0.305 | 0.500 | 0.500 | +0.000 | -0.207 | -0.084 |
| Aalen–Johansen por programa | 0.512 | 0.389 | 0.343 | 0.256 | 0.757 | 0.739 | +0.018 | -0.169 | -0.134 |
| Cox causa-específico (ingreso) | 0.512 | 0.389 | 0.344 | 0.265 | 0.790 | 0.776 | +0.014 | -0.168 | -0.125 |
| Cox causa-específico (ingreso + agregados) | 0.512 | 0.389 | 0.457 | 0.332 | 0.896 | 0.899 | -0.003 | -0.055 | -0.057 |
| CatBoost persona-período (ingreso + agregados) | 0.512 | 0.389 | 0.524 | 0.401 | 0.899 | 0.909 | -0.010 | +0.012 | +0.011 |
| CatBoost persona-período (ingreso) | 0.512 | 0.389 | 0.371 | 0.309 | 0.799 | 0.776 | +0.023 | -0.141 | -0.080 |
| Red MLP de riesgos discretos (ingreso + agregados) | 0.512 | 0.389 | 0.496 | 0.371 | 0.901 | 0.904 | -0.004 | -0.016 | -0.019 |
| Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 0.512 | 0.389 | 0.532 | 0.408 | 0.907 | 0.908 | -0.000 | +0.020 | +0.018 |

- La discriminación es equivalente por sexo en los modelos de ingreso (|ΔAUC| ≤ 0,02). Con agregados el AUC es algo mayor en hombres (−0,02 a −0,03 en k = 2; ≤ 0,01 en k = 4).
- La calibración difiere de otra manera: los modelos de solo ingreso subestiman a las mujeres más que a los hombres (brecha −0,16 frente a −0,11 en k = 2); con agregados la brecha se reduce a entre −0,06 y +0,05 en ambos sexos y es casi simétrica (GRU: +0,008 y +0,009 en k = 2).

**Vía de ingreso** (test, k = 2 y k = 4; `otros_cambio` = ingresos por cambio de carrera o similares):

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicha / AUC |
|---|---|---|---|---|---|---|
| especial | 329 | 0.319 | 0.236 / 0.500 | 0.306 / 0.697 | 0.282 / 0.772 | 0.328 / 0.886 |
| otros_cambio | 234 | 0.564 | 0.236 / 0.500 | 0.308 / 0.706 | 0.347 / 0.705 | 0.536 / 0.860 |
| regular | 3.778 | 0.375 | 0.236 / 0.500 | 0.232 / 0.744 | 0.242 / 0.779 | 0.367 / 0.879 |

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicha / AUC |
|---|---|---|---|---|---|---|
| especial | 272 | 0.386 | 0.305 / 0.500 | 0.361 / 0.727 | 0.349 / 0.789 | 0.443 / 0.915 |
| otros_cambio | 223 | 0.605 | 0.305 / 0.500 | 0.374 / 0.699 | 0.405 / 0.704 | 0.668 / 0.902 |
| regular | 3.214 | 0.439 | 0.305 / 0.500 | 0.285 / 0.763 | 0.290 / 0.796 | 0.453 / 0.912 |

- La discriminación de la GRU es alta y similar en todas las vías (AUC 0,85–0,91), pero en `otros_cambio` (n pequeño) el egreso observado es mayor (0,56–0,61) y los modelos de ingreso lo subestiman; con agregados la brecha se reduce.

**Duración nominal y programas** (k = 2, test; grupos de al menos 150 episodios):

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicha / AUC |
|---|---|---|---|---|---|---|
| 10 | 3.561 | 0.403 | 0.236 / 0.500 | 0.250 / 0.710 | 0.257 / 0.762 | 0.388 / 0.871 |
| <=8 | 430 | 0.477 | 0.236 / 0.500 | 0.349 / 0.635 | 0.320 / 0.701 | 0.501 / 0.839 |
| >=12 | 352 | 0.045 | 0.236 / 0.500 | 0.029 / 0.771 | 0.107 / 0.658 | 0.066 / 0.962 |

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicha / AUC |
|---|---|---|---|---|---|---|
| 8213 ARQUITECTURA | 157 | 0.019 | 0.236 / 0.500 | 0.000 / 0.500 | 0.055 / 0.284 | 0.028 / 0.978 |
| 8323 INGENIERÍA COMERCIAL | 247 | 0.595 | 0.236 / 0.500 | 0.457 / 0.500 | 0.410 / 0.684 | 0.562 / 0.850 |
| 8326 INGENIERÍA COMERCIAL | 233 | 0.730 | 0.236 / 0.500 | 0.475 / 0.500 | 0.431 / 0.654 | 0.724 / 0.886 |
| 8373 DERECHO | 203 | 0.256 | 0.236 / 0.500 | 0.101 / 0.500 | 0.160 / 0.623 | 0.249 / 0.830 |
| 8376 DERECHO | 201 | 0.129 | 0.236 / 0.500 | 0.189 / 0.500 | 0.203 / 0.730 | 0.372 / 0.847 |
| 8606 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 230 | 0.170 | 0.236 / 0.500 | 0.042 / 0.500 | 0.103 / 0.650 | 0.144 / 0.885 |
| 8613 INGENIERÍA CIVIL INDUSTRIAL | 206 | 0.515 | 0.236 / 0.500 | 0.174 / 0.500 | 0.210 / 0.639 | 0.366 / 0.790 |
| 8616 INGENIERÍA CIVIL INDUSTRIAL | 220 | 0.605 | 0.236 / 0.500 | 0.270 / 0.500 | 0.289 / 0.687 | 0.510 / 0.851 |
| 8896 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 191 | 0.681 | 0.236 / 0.500 | 0.312 / 0.500 | 0.360 / 0.650 | 0.644 / 0.820 |

- Los programas con duración nominal de 12 semestres o más tienen muy poco egreso observable a 12 semestres (4–5 %) y el AUC es menos estable.
- Ningún programa alcanza 500 episodios con seguimiento a 12 semestres (el mayor es de ≈ 250), así que la tabla pedida para n ≥ 500 queda vacía; se reportan los grupos de al menos 150.

**Trayectorias de Plan Común (D47)** frente al resto (test, n ≥ 10; incidencia observada y predicha a 12 semestres desde la admisión entre los episodios con seguimiento hasta ahí; son pocos episodios (40 a 70), así que los intervalos son amplios):

k = 0:

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | CatBoost persona-período (ingreso): predicha / AUC |
|---|---|---|---|---|---|---|
| otras_trayectorias | 4.668 | 0.354 | 0.211 / 0.500 | 0.224 / 0.731 | 0.234 / 0.768 | 0.235 / 0.771 |
| plan_comun | 70 | 0.114 | 0.211 / 0.500 | 0.015 / 0.500 | 0.055 / 0.929 | 0.049 / 0.915 |

k = 2:

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicha / AUC |
|---|---|---|---|---|---|---|
| otras_trayectorias | 4.285 | 0.385 | 0.236 / 0.500 | 0.245 / 0.737 | 0.253 / 0.774 | 0.376 / 0.879 |
| plan_comun | 58 | 0.138 | 0.236 / 0.500 | 0.019 / 0.490 | 0.062 / 0.912 | 0.114 / 0.925 |

k = 4:

| Grupo | n (con seguimiento a 12) | Incidencia observada a 12 | Aalen–Johansen global (sin covariables): predicha / AUC | Aalen–Johansen por programa: predicha / AUC | Cox causa-específico (ingreso): predicha / AUC | Red GRU de riesgos discretos (ingreso + agregados + secuencia): predicha / AUC |
|---|---|---|---|---|---|---|
| otras_trayectorias | 3.671 | 0.448 | 0.305 / 0.500 | 0.298 / 0.755 | 0.303 / 0.788 | 0.468 / 0.909 |
| plan_comun | 40 | 0.200 | 0.305 / 0.500 | 0.129 / 0.740 | 0.137 / 0.918 | 0.158 / 0.953 |

- Las trayectorias de Plan Común tienen mucho menos egreso a 12 semestres que el resto, porque el tiempo cuenta desde el ingreso al Plan Común, a ese horizonte aún les quedan semestres de la especialidad y las que no tienen continuación nunca egresan (§2). Los modelos de solo ingreso subestiman su egreso (en k = 0, mucho más que el resto en términos relativos); con agregados y secuencia (k = 2 y 4) la GRU predice algo menos que lo observado (brecha de −0,03 en ambos cortes) y las ordena bien (AUC alto). Con 40 a 70 episodios por grupo estas diferencias no se han acompañado de intervalos y no deben leerse como un sesgo establecido.

Los grupos de menos de 10 episodios no se publican.

### 7.6 Costo y reproducibilidad de la ejecución

| k | Modelo | Tiempo de entrenamiento (s) | Notas |
|---|---|---|---|
| 0 | Aalen–Johansen global (sin covariables) | 0 |  |
| 0 | Aalen–Johansen por programa | 0 |  |
| 0 | Cox causa-específico (ingreso) | 16 | penalizador 0.01; 104 columnas activas |
| 0 | Logística persona-período (ingreso) | 16 | C = 0.3; 128 columnas; 66.633 filas persona-período |
| 0 | CatBoost persona-período (ingreso) | 117 | 3 semillas; iteraciones óptimas [322, 408, 363] |
| 0 | Red MLP de riesgos discretos (ingreso) | 7 | 19951 parámetros; pico de GPU 22 MB; épocas óptimas [17, 17, 17] |
| 2 | Aalen–Johansen global (sin covariables) | 0 |  |
| 2 | Aalen–Johansen por programa | 0 |  |
| 2 | Cox causa-específico (ingreso) | 19 | penalizador 0.01; 102 columnas activas |
| 2 | Cox causa-específico (ingreso + agregados) | 19 | penalizador 0.01; 115 columnas activas |
| 2 | Logística persona-período (ingreso) | 15 | C = 1.0; 123 columnas; 51.820 filas persona-período |
| 2 | Logística persona-período (ingreso + agregados) | 14 | C = 10.0; 136 columnas; 51.820 filas persona-período |
| 2 | CatBoost persona-período (ingreso) | 129 | 3 semillas; iteraciones óptimas [337, 486, 519] |
| 2 | CatBoost persona-período (ingreso + agregados) | 149 | 3 semillas; iteraciones óptimas [628, 515, 554] |
| 2 | Red MLP de riesgos discretos (ingreso) | 7 | 19537 parámetros; pico de GPU 22 MB; épocas óptimas [17, 18, 22] |
| 2 | Red MLP de riesgos discretos (ingreso + agregados) | 7 | 21201 parámetros; pico de GPU 22 MB; épocas óptimas [23, 18, 17] |
| 2 | Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 11 | 32337 parámetros; pico de GPU 47 MB; épocas óptimas [23, 29, 25] |
| 4 | Aalen–Johansen global (sin covariables) | 0 |  |
| 4 | Aalen–Johansen por programa | 0 |  |
| 4 | Cox causa-específico (ingreso) | 3 | penalizador 0.0003; 95 columnas activas |
| 4 | Cox causa-específico (ingreso + agregados) | 3 | penalizador 0.0003; 108 columnas activas |
| 4 | Logística persona-período (ingreso) | 10 | C = 0.1; 115 columnas; 38.129 filas persona-período |
| 4 | Logística persona-período (ingreso + agregados) | 9 | C = 0.3; 128 columnas; 38.129 filas persona-período |
| 4 | CatBoost persona-período (ingreso) | 89 | 3 semillas; iteraciones óptimas [381, 317, 264] |
| 4 | CatBoost persona-período (ingreso + agregados) | 97 | 3 semillas; iteraciones óptimas [360, 386, 351] |
| 4 | Red MLP de riesgos discretos (ingreso) | 5 | 18972 parámetros; pico de GPU 21 MB; épocas óptimas [14, 23, 22] |
| 4 | Red MLP de riesgos discretos (ingreso + agregados) | 5 | 20636 parámetros; pico de GPU 21 MB; épocas óptimas [14, 22, 20] |
| 4 | Red GRU de riesgos discretos (ingreso + agregados + secuencia) | 9 | 31772 parámetros; pico de GPU 53 MB; épocas óptimas [31, 26, 31] |

Tiempo total del benchmark: 20 minutos; RAM pico 2130 MB. Importancia de variables de CatBoost (media de 3 semillas, % de la importancia total):

| Variable | Importancia (media de 3 semillas, % del total) |
|---|---|
| `slot_rel_nominal` | 26.4 |
| `slot` | 19.3 |
| `tasa_aprobacion` | 6.5 |
| `creditos_aprobados` | 6.2 |
| `promedio_evaluado` | 5.8 |
| `avance_malla` | 4.5 |
| `cod_programa` | 4.0 |
| `fraccion_malla` | 3.2 |
| `creditos_malla_total` | 2.9 |
| `creditos_esperados` | 2.5 |
| `mm_ranking` | 1.6 |
| `mm_notas_em` | 1.5 |
| `mm_leng` | 1.5 |
| `mm_ciencias` | 1.5 |
| `mm_mat` | 1.4 |

El tiempo (`slot`, `slot_rel_nominal`) y el avance de créditos dominan; el programa y los puntajes de ingreso pesan menos.

## 8. Limitaciones y preguntas abiertas

1. **Deriva de cohorte (P60).** La incidencia acumulada de egreso a 12 semestres pasa de 21,1 % (2015-2017) a 30,5 % (2018) y 35,0 % (2019-2020); la mediana del tiempo al egreso, de 13 a 11. Es posible que parte del cambio sea de **registro** (lotes de estados «Z» en períodos «10») y no de comportamiento.
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
- **k = 2.** **Modelo conservado: GRU** (regla única de selección en validación, D114: frente al mejor clásico `dt_cb_agg`, ΔC(12) +0,0167 [+0,0107; +0,0226] y ΔIBS −0,0035 [−0,0046; −0,0025]; la prueba lo confirma con C(12) 0,839 frente a 0,800, ΔC +0,039 [+0,033; +0,046] y ΔIBS −0,0041). La GRU con secuencia es el mejor modelo técnico (+0,016 a +0,020 de C(12) sobre la logística y el Cox, +0,039 sobre CatBoost; IBS −0,004 a −0,005), pero la mejora es modesta y hay que repetir la estimación con nuevas cohortes y una recalibración antes de cualquier uso.
- **k = 4.** **Modelo conservado: GRU** (D114: en validación ΔC(12) +0,024 [+0,018; +0,030] y ΔIBS −0,0024 [−0,0044; −0,0004] frente al mejor clásico). *Salvedad:* en prueba la mejora de C(12) es marginal (0,860 frente a 0,854; ΔC +0,0055 [+0,0007; +0,0097]) y el IBS es levemente peor (ΔIBS +0,0011 [+0,0001; +0,0022]); conviene revisar la calibración antes de citar probabilidades absolutas. *La redacción anterior recomendaba conservar la logística o CatBoost con los resultados de prueba; la regla única la corrige.*
- En todos los cortes los agregados académicos explican casi toda la mejora; antes de invertir en arquitecturas más complejas conviene mejorar la calidad de esos datos (P58) y aclarar el evento (P59).
- **Beneficios estudiantiles (16-11-2026, §11).** No se adoptan: ningún modelo con beneficios mejora al oficial en `k = 4` con la regla de años anteriores al del corte, y en `k = 2` la ablación no es aplicable. Se reevaluará con una fecha de asignación de los beneficios (P90, P98).
- **El uso de predicciones individuales no está aprobado** (Gate 4). Todo el contenido es agregado.

## 10. Reproducibilidad

- Migraciones: `python -m pipelines.migrate` (013 y 014). Snapshot: `python -m pipelines.snapshots.t3`. Benchmark: `python -m evaluation.run_t3` (`--k`, `--seeds`, `--boot`, `--solo`). Informe: `python tools/informe_t3.py --doc`.
- Resultados agregados: `artefactos/resultados_t3.json` (ignorado por git); predicciones por episodio: `artefactos/preds/` (nunca fuera del equipo).
- Hash de datos `71bad59591e2fea0961400fe2863f4c99474d82c8469e2eae33ee52e4d60280b`; versión del código `b1259455b334aa220461c618d87aef762a13b7fb2757e1b1afd5a371a9590ff9`; MLflow `t3_tiempo_hasta_titulacion`.
- Todos los números de este documento se generan desde el JSON con `tools/plantilla_t3.md`; no se editan a mano en `docs/10_benchmark_t3.md`.

## 11. Beneficios (16-11-2026)

**Pregunta.** La hipótesis del plan semanal es que la gratuidad se pierde al superar la duración formal del programa (la UCN otorga entonces rebajas «Expiración Gratuidad N+1» y «Brecha … N+1 / N+2») y que el «Ajuste Deuda Capstone Project» marca la etapa final. Ambas señales deberían anticipar el egreso. Se prueba con la tabla `banner.banner_beneficios` ya extraída y seudonimizada (decisiones D90–D95) y con una regla estricta de punto en el tiempo. Solo agregados; ningún RUT, monto individual ni predicción por persona figura aquí.

**Resultado en una línea.** **El modelo oficial de T3 no cambia.** En los cortes oficiales `k = 2` y `k = 4`, ningún modelo con beneficios cumple el criterio de adopción bajo la regla por defecto (años anteriores al del corte): en `k = 2` casi nadie tiene datos de beneficios previos al corte y la ablación no es aplicable; en `k = 4` la GRU con todos los beneficios cambia el C(12) de valid en +0,000 [-0,004; +0,004] y el IBS de valid en -0,0001 [-0,0011; +0,0009] (el intervalo incluye el 0 en ambas). La única mejora en valid con intervalo que excluye el 0 (GRU con el bloque de financiamiento, ΔIBS -0,0013 [-0,0023; -0,0004]) no se confirma en test (+0,0001 [-0,0006; +0,0007]). En cortes tardíos (`k = 8` y `k = 10`, donde las banderas de expiración y Capstone sí existen) la GRU con beneficios empeora (en `k = 10`, ΔC(12) de test -0,010 [-0,013; -0,007]) y la única mejora estadística aparece en la logística bajo la regla con fuga (§11.6). Las banderas de Capstone del año del corte no son un hecho conocido al corte (§11.3).

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

**Cortes.** Los oficiales `k = 2, 4` y, como **extensión**, los tardíos `k = 8, 10` (migración 027: `snapshot_t3_ext*`, misma construcción, columnas y particiones que el snapshot oficial, hash `e8990d569f906d9a0b3584bf21220e66ec515606605bfac4d1e9a76a2785cece`). Se agregaron porque las banderas de la hipótesis aparecen mucho después de los cortes oficiales:

| Años desde el año de admisión | Filas con expiración de gratuidad | Filas con Capstone |
|---|---|---|
| 0 | 115 | 2 |
| 1 | 176 | 0 |
| 2 | 315 | 0 |
| 3 | 434 | 8 |
| 4 | 816 | 127 |
| 5 | 2.424 | 690 |
| 6 | 1.519 | 487 |
| 7 | 825 | 250 |
| 8 | 404 | 116 |
| 9 o más | 307 | 107 |

(Filas persona-año de pregrado con la bandera, por años desde el año de admisión del mismo programa.) Con cortes a 2 y 4 semestres casi ninguna fila tiene la bandera; con la regla `previo` en `k = 4` solo se lee el año de admisión. Por eso el criterio de adopción se juzga en los cortes oficiales y la extensión muestra si la señal existe cuando sí puede observarse.

### 11.2 Cobertura de los datos por corte y regla

| Corte | Regla | n train | n valid | n test | Con dato (train) | Con dato (valid) | Con dato (test) | Estado |
|---|---|---|---|---|---|---|---|---|
| k = 2 | previo | 6.715 | 2.275 | 4.343 | 1,6 % | 4,4 % | 2,5 % | no aplicable |
| k = 2 | con_t | 6.715 | 2.275 | 4.343 | 33,6 % | 100,0 % | 100,0 % | evaluada |
| k = 4 | previo | 5.173 | 1.813 | 3.711 | 34,6 % | 100,0 % | 100,0 % | evaluada |
| k = 4 | con_t | 5.173 | 1.813 | 3.711 | 67,1 % | 100,0 % | 100,0 % | evaluada |
| k = 8 (extensión) | previo | 3.543 | 1.339 | 2.472 | 100,0 % | 100,0 % | 100,0 % | evaluada |
| k = 8 (extensión) | con_t | 3.543 | 1.339 | 2.472 | 100,0 % | 100,0 % | 100,0 % | evaluada |
| k = 10 (extensión) | previo | 3.325 | 1.150 | 2.066 | 100,0 % | 100,0 % | 100,0 % | evaluada |
| k = 10 (extensión) | con_t | 3.325 | 1.150 | 2.066 | 100,0 % | 100,0 % | 100,0 % | evaluada |

Un corte es «no aplicable» si menos del 5 % de sus filas de train o de test tiene datos bajo la regla (`k = 2` con `previo`: solo los admitidos en el segundo semestre tienen un año anterior al corte dentro de su ventana). Las cohortes 2015 y 2016 de train no tienen datos de beneficios en `k ≤ 4` (la tabla empieza en 2017; P93): el entrenamiento ve beneficios en una fracción de las filas y el modelo los imputa con la mediana de train más un indicador; valid y test sí los tienen en todas las filas.

### 11.3 Diagnóstico de fuga: ¿el año `t` es un hecho del corte? (justificación de la regla)

Para cada corte se compara, por desenlace posterior, qué tan frecuente es tener fila de beneficio o gratuidad en el año `t` del corte y en el año `t − 1` (misma población, un año antes). Si el año `t` fuera un hecho conocido al corte, la brecha entre quienes luego salen y quienes siguen se parecería a la del año `t − 1`. La tabla da la brecha «salida definitiva menos sigue matriculado o censurado» en puntos porcentuales.

| Corte | Tipo de corte | Cortes comparables | Fila de beneficio: brecha año t | Fila: brecha año t − 1 | Gratuidad: brecha año t | Gratuidad: brecha año t − 1 |
|---|---|---|---|---|---|---|
| k = 2 | mitad de año (AAAA10) | 546 | -14,9 pp | -6,6 pp | -5,8 pp | -6,0 pp |
| k = 4 | fin de año (AAAA20) | 14.370 | -3,1 pp | +1,5 pp | -4,9 pp | -0,3 pp |
| k = 4 | mitad de año (AAAA10) | 570 | -21,9 pp | -4,3 pp | -15,4 pp | -0,1 pp |
| k = 8 (extensión) | fin de año (AAAA20) | 9.579 | -5,8 pp | -0,9 pp | -8,2 pp | -5,6 pp |
| k = 10 (extensión) | fin de año (AAAA20) | 7.104 | -7,5 pp | -4,3 pp | -6,0 pp | -3,7 pp |

- **Cortes de mitad de año:** la brecha del año `t` es varias veces la del año `t − 1` (en `k = 4`, la presencia de fila difiere en −21,9 puntos contra −4,3 y la gratuidad en −15,4 contra −0,1): quien se retira durante el año pierde la fila o la gratuidad antes del corte siguiente (consistente con D92). Esos cortes **no** leen el año `t` en ninguna regla.
- **Cortes de fin de año:** la brecha del año `t` sigue siendo mayor que la del año `t − 1` (entre 2 y 5 puntos en presencia de fila y en gratuidad): la fila del año `t` refleja parte del desenlace posterior. Es una fuga pequeña pero sistemática, y sin fecha de asignación no se puede acotar.
- **`k = 2` de fin de año** (la mayoría de los cortes de `k = 2`) no tiene un año `t − 1` dentro de la ventana de un recién admitido, de modo que no es comparable; es el caso más expuesto a la fuga (D92: entre quienes salen en el año de ingreso solo el 4,3 % conserva alguna fila, frente al 73,9 % del resto).
- **Regla elegida (D100):** `previo` por defecto; `con_t` solo como sensibilidad, porque su ganancia o pérdida no se puede atribuir a información disponible al corte.

**¿Las banderas de expiración y Capstone del año `t` se asignan temprano?** Entre los cortes de fin de año que tienen la bandera en el año `t`, se mide qué fracción tiene monto en el primer semestre (la bandera rige desde el inicio del año) y cuál lo tiene en el segundo (`benef_sem2` solo se usa aquí, en el diagnóstico):

| Corte | Tipo | Bandera del año t | Cortes con la bandera | Con monto en el 1.er semestre | Con monto en el 2.º semestre |
|---|---|---|---|---|---|
| k = 4 | fin de año (AAAA20) | Expiración de gratuidad | 139 | 77,0 % | 98,6 % |
| k = 8 (extensión) | fin de año (AAAA20) | Expiración de gratuidad | 256 | 90,6 % | 98,0 % |
| k = 8 (extensión) | mitad de año (AAAA10) | Expiración de gratuidad | 74 | 93,2 % | 95,9 % |
| k = 10 (extensión) | fin de año (AAAA20) | Expiración de gratuidad | 481 | 85,4 % | 98,5 % |
| k = 10 (extensión) | fin de año (AAAA20) | Capstone | 78 | 3,8 % | 98,7 % |
| k = 10 (extensión) | mitad de año (AAAA10) | Expiración de gratuidad | 66 | 86,4 % | 95,5 % |
| k = 10 (extensión) | mitad de año (AAAA10) | Capstone | 30 | 26,7 % | 86,7 % |

- **Expiración:** la mayoría (77 % a 91 %) ya tiene monto en el primer semestre y su frecuencia por desenlace es estable entre `t` y `t − 1` (por ejemplo, en `k = 10` de fin de año: 7,6 % de quienes salen y 6,5 % de quienes siguen en el año `t`, frente a 2,8 % y 2,0 % en el año anterior). Parece asignada al inicio del año, pero la prueba es indirecta.
- **Capstone:** solo el 4 % de las filas con la bandera en `k = 10` tiene monto en el primer semestre y el 99 % lo tiene en el segundo: **se asigna en el segundo semestre**, es decir, al cursar la etapa final. En `k = 10` de fin de año la bandera aparece en 2,8 % de quienes egresan en el semestre siguiente y en 0,4 % de quienes siguen (año anterior: 0,0 %). Es la señal de cercanía al egreso que planteaba la hipótesis, pero se genera en el semestre que termina en el corte y sin fecha de asignación no se puede asegurar que exista antes de él; tampoco se puede descartar que el egreso mismo la cree. **No se usa como hecho del corte** (solo en la sensibilidad `con_t`).

Prevalencia de las banderas por desenlace posterior (año `t` frente a `t − 1`):

| Corte | Tipo | Desenlace posterior | n | Expiración, año t | Expiración, año t − 1 | Capstone, año t | Capstone, año t − 1 |
|---|---|---|---|---|---|---|---|
| k = 8 (extensión) | fin de año (AAAA20) | egreso en el semestre siguiente | 327 | 12,8 % | 8,0 % | 2,1 % | 0,0 % |
| k = 8 (extensión) | fin de año (AAAA20) | egreso posterior | 5.906 | 2,3 % | 1,0 % | 0,0 % | 0,0 % |
| k = 8 (extensión) | fin de año (AAAA20) | salida definitiva | 719 | 3,1 % | 1,3 % | 0,0 % | 0,0 % |
| k = 8 (extensión) | fin de año (AAAA20) | sigue matriculado / censurado | 2.627 | 2,2 % | 1,3 % | 0,0 % | 0,0 % |
| k = 10 (extensión) | fin de año (AAAA20) | egreso en el semestre siguiente | 2.204 | 7,7 % | 2,6 % | 2,8 % | 0,0 % |
| k = 10 (extensión) | fin de año (AAAA20) | egreso posterior | 3.139 | 6,1 % | 1,7 % | 0,4 % | 0,0 % |
| k = 10 (extensión) | fin de año (AAAA20) | salida definitiva | 353 | 7,6 % | 2,8 % | 0,0 % | 0,0 % |
| k = 10 (extensión) | fin de año (AAAA20) | sigue matriculado / censurado | 1.408 | 6,5 % | 2,0 % | 0,4 % | 0,0 % |
| k = 10 (extensión) | mitad de año (AAAA10) | egreso posterior | 140 | 35,0 % | 19,3 % | 14,3 % | 0,7 % |
| k = 8 (extensión) | mitad de año (AAAA10) | egreso en el semestre siguiente | 48 | 31,2 % | 18,8 % | 8,3 % | 0,0 % |
| k = 8 (extensión) | mitad de año (AAAA10) | egreso posterior | 235 | 19,6 % | 10,2 % | 4,3 % | 0,0 % |
| k = 8 (extensión) | mitad de año (AAAA10) | sigue matriculado / censurado | 31 | 41,9 % | 6,5 % | 0,0 % | 0,0 % |

### 11.4 Reproducción del modelo oficial

El modelo «ingreso + agregados» se reentrenó con los mismos datos, semillas y particiones (código nuevo, sin tocar el oficial). Debe coincidir con `resultados_t3.json`:

| Corte | Modelo | C(12) test oficial | C(12) test reentrenado | IBS test oficial | IBS test reentrenado |
|---|---|---|---|---|---|
| k = 2 | Logística persona-período | 0,823 | 0,823 | 0,0451 | 0,0451 |
| k = 2 | CatBoost persona-período | 0,800 | 0,800 | 0,0463 | 0,0463 |
| k = 2 | Red GRU de riesgos discretos | 0,839 | 0,839 | 0,0422 | 0,0422 |
| k = 4 | Logística persona-período | 0,856 | 0,856 | 0,0530 | 0,0530 |
| k = 4 | CatBoost persona-período | 0,854 | 0,854 | 0,0507 | 0,0507 |
| k = 4 | Red GRU de riesgos discretos | 0,860 | 0,860 | 0,0518 | 0,0518 |

### 11.5 Ablación en los cortes oficiales (`k = 2` y `k = 4`)

Modelos y evaluación como en §6 (regresión logística y CatBoost persona-período, GRU de riesgos discretos con 3 semillas; selección en valid; bootstrap por episodio de 1000 remuestreos con las **mismas** remuestras para todos los modelos y diferencias pareadas; C de Uno a 12 semestres desde la admisión e IBS hasta el semestre 12).

**Criterio de adopción (D100).** Un modelo con beneficios reemplaza al modelo oficial sin beneficios solo si, **con la regla `previo`**, su ΔC(12) pareado en valid tiene intervalo sobre 0 o su ΔIBS pareado en valid tiene intervalo bajo 0, y en test la métrica que califica no empeora en su estimación puntual y ninguna de las dos empeora significativamente. La sensibilidad `con_t` y los cortes tardíos no se adoptan nunca. Es una comparación de varias familias, bloques y reglas: un intervalo que excluye el 0 por poco se interpreta con cautela.

**`k = 2`, regla `previo`:** _No aplicable: casi ninguna fila del corte tiene datos de beneficios bajo esta regla._

**`k = 2`, regla `con_t` (sensibilidad):**

| Modelo | C(12) valid | C(12) test | IBS valid | IBS test |
|---|---|---|---|---|
| Logística persona-período: ingreso + agregados (oficial) | 0,868 [0,856; 0,881] | 0,823 [0,812; 0,833] | 0,0374 [0,0349; 0,0399] | 0,0451 [0,0431; 0,0473] |
| Logística persona-período: + financiamiento (con año t) | 0,867 [0,854; 0,881] | 0,821 [0,811; 0,831] | 0,0375 [0,0350; 0,0399] | 0,0457 [0,0436; 0,0479] |
| Logística persona-período: + expiración y Capstone (con año t) | 0,869 [0,857; 0,882] | 0,823 [0,813; 0,833] | 0,0372 [0,0346; 0,0396] | 0,0450 [0,0430; 0,0472] |
| Logística persona-período: + beneficios (todo) (con año t) | 0,868 [0,855; 0,881] | 0,822 [0,812; 0,832] | 0,0374 [0,0349; 0,0398] | 0,0456 [0,0436; 0,0478] |
| CatBoost persona-período: ingreso + agregados (oficial) | 0,863 [0,851; 0,876] | 0,800 [0,788; 0,811] | 0,0349 [0,0324; 0,0374] | 0,0463 [0,0440; 0,0487] |
| CatBoost persona-período: + financiamiento (con año t) | 0,865 [0,854; 0,878] | 0,804 [0,792; 0,814] | 0,0344 [0,0320; 0,0369] | 0,0460 [0,0438; 0,0484] |
| CatBoost persona-período: + expiración y Capstone (con año t) | 0,863 [0,851; 0,876] | 0,801 [0,789; 0,812] | 0,0347 [0,0322; 0,0371] | 0,0464 [0,0442; 0,0488] |
| CatBoost persona-período: + beneficios (todo) (con año t) | 0,865 [0,853; 0,877] | 0,803 [0,792; 0,814] | 0,0345 [0,0320; 0,0369] | 0,0461 [0,0438; 0,0484] |
| Red GRU de riesgos discretos: ingreso + agregados (oficial) | 0,880 [0,870; 0,892] | 0,839 [0,829; 0,849] | 0,0314 [0,0293; 0,0336] | 0,0422 [0,0402; 0,0443] |
| Red GRU de riesgos discretos: + financiamiento (con año t) | 0,872 [0,861; 0,884] | 0,833 [0,824; 0,843] | 0,0326 [0,0303; 0,0348] | 0,0432 [0,0412; 0,0455] |
| Red GRU de riesgos discretos: + expiración y Capstone (con año t) | 0,879 [0,869; 0,890] | 0,838 [0,829; 0,847] | 0,0318 [0,0296; 0,0340] | 0,0422 [0,0402; 0,0444] |
| Red GRU de riesgos discretos: + beneficios (todo) (con año t) | 0,873 [0,862; 0,885] | 0,834 [0,825; 0,844] | 0,0329 [0,0306; 0,0352] | 0,0433 [0,0412; 0,0456] |

| Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | ΔIBS test | Cumple el criterio estadístico |
|---|---|---|---|---|---|---|
| Logística persona-período | + financiamiento | -0,001 [-0,003; +0,001] | +0,0001 [-0,0002; +0,0004] | -0,001 [-0,004; +0,001] | +0,0005 [-0,0001; +0,0013] | no |
| Logística persona-período | + expiración y Capstone | +0,001 [+0,000; +0,002] | -0,0002 [-0,0004; -0,0001] | +0,000 [-0,000; +0,001] | -0,0001 [-0,0002; -0,0000] | sí (solo sensibilidad; no adoptable) |
| Logística persona-período | + beneficios (todo) | -0,000 [-0,002; +0,002] | -0,0000 [-0,0003; +0,0003] | -0,001 [-0,003; +0,002] | +0,0005 [-0,0002; +0,0012] | no |
| CatBoost persona-período | + financiamiento | +0,002 [+0,000; +0,004] | -0,0005 [-0,0009; -0,0002] | +0,004 [+0,002; +0,005] | -0,0003 [-0,0004; -0,0001] | sí (solo sensibilidad; no adoptable) |
| CatBoost persona-período | + expiración y Capstone | -0,000 [-0,001; +0,001] | -0,0002 [-0,0004; -0,0000] | +0,001 [+0,000; +0,002] | +0,0001 [-0,0000; +0,0002] | no |
| CatBoost persona-período | + beneficios (todo) | +0,002 [+0,000; +0,003] | -0,0004 [-0,0007; -0,0001] | +0,003 [+0,002; +0,004] | -0,0002 [-0,0004; -0,0001] | sí (solo sensibilidad; no adoptable) |
| Red GRU de riesgos discretos | + financiamiento | -0,008 [-0,012; -0,005] | +0,0012 [+0,0003; +0,0019] | -0,006 [-0,009; -0,003] | +0,0010 [+0,0005; +0,0016] | no |
| Red GRU de riesgos discretos | + expiración y Capstone | -0,001 [-0,003; +0,001] | +0,0003 [-0,0000; +0,0007] | -0,001 [-0,003; +0,000] | +0,0000 [-0,0002; +0,0003] | no |
| Red GRU de riesgos discretos | + beneficios (todo) | -0,007 [-0,011; -0,003] | +0,0014 [+0,0006; +0,0022] | -0,005 [-0,008; -0,002] | +0,0011 [+0,0005; +0,0017] | no |

**`k = 4`, regla `previo` (por defecto):**

| Modelo | C(12) valid | C(12) test | IBS valid | IBS test |
|---|---|---|---|---|
| Logística persona-período: ingreso + agregados (oficial) | 0,888 [0,874; 0,901] | 0,856 [0,847; 0,865] | 0,0506 [0,0472; 0,0543] | 0,0530 [0,0505; 0,0556] |
| Logística persona-período: + financiamiento (previo) | 0,886 [0,872; 0,900] | 0,854 [0,845; 0,863] | 0,0506 [0,0473; 0,0543] | 0,0534 [0,0508; 0,0559] |
| Logística persona-período: + expiración y Capstone (previo) | 0,887 [0,874; 0,901] | 0,856 [0,847; 0,865] | 0,0507 [0,0473; 0,0544] | 0,0530 [0,0505; 0,0556] |
| Logística persona-período: + beneficios (todo) (previo) | 0,886 [0,872; 0,900] | 0,854 [0,845; 0,863] | 0,0506 [0,0473; 0,0543] | 0,0533 [0,0508; 0,0559] |
| CatBoost persona-período: ingreso + agregados (oficial) | 0,876 [0,863; 0,889] | 0,854 [0,846; 0,863] | 0,0475 [0,0440; 0,0513] | 0,0507 [0,0480; 0,0534] |
| CatBoost persona-período: + financiamiento (previo) | 0,877 [0,863; 0,890] | 0,855 [0,847; 0,864] | 0,0474 [0,0438; 0,0510] | 0,0506 [0,0480; 0,0533] |
| CatBoost persona-período: + expiración y Capstone (previo) | 0,876 [0,863; 0,889] | 0,853 [0,845; 0,862] | 0,0481 [0,0446; 0,0519] | 0,0509 [0,0481; 0,0535] |
| CatBoost persona-período: + beneficios (todo) (previo) | 0,876 [0,863; 0,889] | 0,854 [0,846; 0,863] | 0,0481 [0,0445; 0,0517] | 0,0506 [0,0480; 0,0533] |
| Red GRU de riesgos discretos: ingreso + agregados (oficial) | 0,900 [0,888; 0,911] | 0,860 [0,851; 0,868] | 0,0451 [0,0415; 0,0489] | 0,0518 [0,0490; 0,0545] |
| Red GRU de riesgos discretos: + financiamiento (previo) | 0,900 [0,889; 0,911] | 0,860 [0,851; 0,868] | 0,0438 [0,0403; 0,0475] | 0,0518 [0,0489; 0,0548] |
| Red GRU de riesgos discretos: + expiración y Capstone (previo) | 0,902 [0,891; 0,914] | 0,860 [0,851; 0,868] | 0,0454 [0,0416; 0,0493] | 0,0520 [0,0491; 0,0549] |
| Red GRU de riesgos discretos: + beneficios (todo) (previo) | 0,900 [0,889; 0,911] | 0,861 [0,852; 0,869] | 0,0450 [0,0413; 0,0488] | 0,0510 [0,0481; 0,0539] |

| Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | ΔIBS test | Cumple el criterio estadístico |
|---|---|---|---|---|---|---|
| Logística persona-período | + financiamiento | -0,002 [-0,003; +0,000] | +0,0000 [-0,0003; +0,0004] | -0,002 [-0,005; +0,000] | +0,0004 [-0,0001; +0,0009] | no |
| Logística persona-período | + expiración y Capstone | -0,000 [-0,000; -0,000] | +0,0001 [+0,0001; +0,0001] | -0,000 [-0,000; +0,000] | +0,0000 [-0,0000; +0,0000] | no |
| Logística persona-período | + beneficios (todo) | -0,002 [-0,003; +0,000] | -0,0000 [-0,0004; +0,0004] | -0,002 [-0,004; +0,000] | +0,0003 [-0,0001; +0,0008] | no |
| CatBoost persona-período | + financiamiento | +0,001 [-0,000; +0,002] | -0,0002 [-0,0005; +0,0001] | +0,001 [-0,000; +0,002] | -0,0001 [-0,0003; +0,0001] | no |
| CatBoost persona-período | + expiración y Capstone | +0,000 [-0,001; +0,001] | +0,0006 [+0,0003; +0,0010] | -0,001 [-0,002; -0,001] | +0,0002 [-0,0000; +0,0003] | no |
| CatBoost persona-período | + beneficios (todo) | +0,000 [-0,001; +0,001] | +0,0005 [+0,0002; +0,0009] | -0,000 [-0,001; +0,001] | -0,0001 [-0,0003; +0,0001] | no |
| Red GRU de riesgos discretos | + financiamiento | +0,000 [-0,003; +0,004] | -0,0013 [-0,0023; -0,0004] | +0,000 [-0,003; +0,003] | +0,0001 [-0,0006; +0,0007] | no |
| Red GRU de riesgos discretos | + expiración y Capstone | +0,003 [-0,000; +0,006] | +0,0002 [-0,0005; +0,0010] | -0,000 [-0,002; +0,002] | +0,0002 [-0,0003; +0,0008] | no |
| Red GRU de riesgos discretos | + beneficios (todo) | +0,000 [-0,004; +0,004] | -0,0001 [-0,0011; +0,0009] | +0,001 [-0,002; +0,004] | -0,0008 [-0,0015; +0,0000] | no |

**`k = 4`, regla `con_t` (sensibilidad):**

| Modelo | C(12) valid | C(12) test | IBS valid | IBS test |
|---|---|---|---|---|
| Logística persona-período: ingreso + agregados (oficial) | 0,888 [0,874; 0,901] | 0,856 [0,847; 0,865] | 0,0506 [0,0472; 0,0543] | 0,0530 [0,0505; 0,0556] |
| Logística persona-período: + financiamiento (con año t) | 0,886 [0,872; 0,899] | 0,852 [0,842; 0,861] | 0,0512 [0,0478; 0,0549] | 0,0533 [0,0507; 0,0559] |
| Logística persona-período: + expiración y Capstone (con año t) | 0,888 [0,874; 0,901] | 0,857 [0,847; 0,865] | 0,0505 [0,0471; 0,0542] | 0,0530 [0,0504; 0,0556] |
| Logística persona-período: + beneficios (todo) (con año t) | 0,886 [0,872; 0,899] | 0,852 [0,843; 0,861] | 0,0512 [0,0479; 0,0550] | 0,0533 [0,0508; 0,0559] |
| CatBoost persona-período: ingreso + agregados (oficial) | 0,876 [0,863; 0,889] | 0,854 [0,846; 0,863] | 0,0475 [0,0440; 0,0513] | 0,0507 [0,0480; 0,0534] |
| CatBoost persona-período: + financiamiento (con año t) | 0,877 [0,864; 0,889] | 0,853 [0,845; 0,862] | 0,0473 [0,0439; 0,0509] | 0,0503 [0,0476; 0,0530] |
| CatBoost persona-período: + expiración y Capstone (con año t) | 0,876 [0,863; 0,889] | 0,854 [0,845; 0,862] | 0,0478 [0,0442; 0,0515] | 0,0505 [0,0478; 0,0531] |
| CatBoost persona-período: + beneficios (todo) (con año t) | 0,878 [0,865; 0,890] | 0,853 [0,845; 0,863] | 0,0473 [0,0438; 0,0510] | 0,0506 [0,0479; 0,0532] |
| Red GRU de riesgos discretos: ingreso + agregados (oficial) | 0,900 [0,888; 0,911] | 0,860 [0,851; 0,868] | 0,0451 [0,0415; 0,0489] | 0,0518 [0,0490; 0,0545] |
| Red GRU de riesgos discretos: + financiamiento (con año t) | 0,895 [0,883; 0,907] | 0,851 [0,842; 0,860] | 0,0460 [0,0422; 0,0500] | 0,0526 [0,0496; 0,0556] |
| Red GRU de riesgos discretos: + expiración y Capstone (con año t) | 0,906 [0,894; 0,917] | 0,859 [0,850; 0,867] | 0,0447 [0,0410; 0,0486] | 0,0520 [0,0493; 0,0548] |
| Red GRU de riesgos discretos: + beneficios (todo) (con año t) | 0,900 [0,888; 0,911] | 0,853 [0,843; 0,862] | 0,0451 [0,0413; 0,0490] | 0,0524 [0,0494; 0,0553] |

| Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | ΔIBS test | Cumple el criterio estadístico |
|---|---|---|---|---|---|---|
| Logística persona-período | + financiamiento | -0,002 [-0,004; +0,000] | +0,0006 [+0,0002; +0,0009] | -0,004 [-0,007; -0,002] | +0,0003 [-0,0001; +0,0007] | no |
| Logística persona-período | + expiración y Capstone | +0,000 [+0,000; +0,001] | -0,0001 [-0,0001; -0,0001] | +0,000 [+0,000; +0,000] | -0,0000 [-0,0001; -0,0000] | sí (solo sensibilidad; no adoptable) |
| Logística persona-período | + beneficios (todo) | -0,002 [-0,004; +0,000] | +0,0006 [+0,0003; +0,0010] | -0,004 [-0,007; -0,002] | +0,0003 [-0,0001; +0,0007] | no |
| CatBoost persona-período | + financiamiento | +0,001 [-0,000; +0,002] | -0,0002 [-0,0005; +0,0001] | -0,001 [-0,002; -0,000] | -0,0004 [-0,0006; -0,0002] | no |
| CatBoost persona-período | + expiración y Capstone | +0,000 [-0,001; +0,001] | +0,0002 [-0,0001; +0,0005] | -0,001 [-0,002; +0,000] | -0,0002 [-0,0004; -0,0001] | no |
| CatBoost persona-período | + beneficios (todo) | +0,002 [+0,001; +0,003] | -0,0003 [-0,0006; -0,0000] | -0,001 [-0,002; +0,000] | -0,0001 [-0,0003; +0,0001] | no |
| Red GRU de riesgos discretos | + financiamiento | -0,005 [-0,009; -0,001] | +0,0008 [-0,0001; +0,0018] | -0,009 [-0,012; -0,005] | +0,0009 [+0,0000; +0,0017] | no |
| Red GRU de riesgos discretos | + expiración y Capstone | +0,006 [+0,004; +0,008] | -0,0005 [-0,0011; +0,0002] | -0,001 [-0,003; +0,000] | +0,0003 [-0,0002; +0,0007] | no |
| Red GRU de riesgos discretos | + beneficios (todo) | -0,000 [-0,004; +0,004] | +0,0000 [-0,0009; +0,0008] | -0,007 [-0,011; -0,003] | +0,0006 [-0,0001; +0,0015] | no |

**Decisión sobre los cortes oficiales (regla por defecto):**

| Corte | Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | Decisión |
|---|---|---|---|---|---|---|
| k = 2 | — | — | — | — | — | no aplicable (sin datos de beneficios previos al corte) |
| k = 4 | Logística persona-período | + beneficios (todo) | -0,002 [-0,003; +0,000] | -0,0000 [-0,0004; +0,0004] | -0,002 [-0,004; +0,000] | no adopta |
| k = 4 | Logística persona-período | + expiración y Capstone | -0,000 [-0,000; -0,000] | +0,0001 [+0,0001; +0,0001] | -0,000 [-0,000; +0,000] | no adopta |
| k = 4 | CatBoost persona-período | + beneficios (todo) | +0,000 [-0,001; +0,001] | +0,0005 [+0,0002; +0,0009] | -0,000 [-0,001; +0,001] | no adopta |
| k = 4 | CatBoost persona-período | + expiración y Capstone | +0,000 [-0,001; +0,001] | +0,0006 [+0,0003; +0,0010] | -0,001 [-0,002; -0,001] | no adopta |
| k = 4 | Red GRU de riesgos discretos | + beneficios (todo) | +0,000 [-0,004; +0,004] | -0,0001 [-0,0011; +0,0009] | +0,001 [-0,002; +0,004] | no adopta |
| k = 4 | Red GRU de riesgos discretos | + expiración y Capstone | +0,003 [-0,000; +0,006] | +0,0002 [-0,0005; +0,0010] | -0,000 [-0,002; +0,002] | no adopta |

### 11.6 Extensión: cortes tardíos (`k = 8` y `k = 10`)

Aquí las banderas de expiración y Capstone sí existen (§11.1). No son cortes oficiales: no se adoptan, se informan para saber si la señal está.

**`k = 8`, regla `previo`:**

| Modelo | C(12) valid | C(12) test | IBS valid | IBS test |
|---|---|---|---|---|
| Logística persona-período: ingreso + agregados (oficial) | 0,900 [0,886; 0,912] | 0,848 [0,838; 0,859] | 0,0786 [0,0736; 0,0835] | 0,1055 [0,1009; 0,1099] |
| Logística persona-período: + financiamiento (previo) | 0,900 [0,887; 0,913] | 0,848 [0,837; 0,858] | 0,0784 [0,0734; 0,0834] | 0,1052 [0,1006; 0,1099] |
| Logística persona-período: + expiración y Capstone (previo) | 0,900 [0,887; 0,913] | 0,850 [0,839; 0,860] | 0,0781 [0,0730; 0,0832] | 0,1051 [0,1008; 0,1098] |
| Logística persona-período: + beneficios (todo) (previo) | 0,901 [0,888; 0,913] | 0,849 [0,839; 0,860] | 0,0781 [0,0730; 0,0831] | 0,1049 [0,1004; 0,1095] |
| CatBoost persona-período: ingreso + agregados (oficial) | 0,918 [0,907; 0,928] | 0,862 [0,852; 0,872] | 0,0516 [0,0467; 0,0562] | 0,0829 [0,0783; 0,0873] |
| CatBoost persona-período: + financiamiento (previo) | 0,918 [0,907; 0,928] | 0,859 [0,849; 0,869] | 0,0521 [0,0473; 0,0568] | 0,0836 [0,0789; 0,0880] |
| CatBoost persona-período: + expiración y Capstone (previo) | 0,916 [0,905; 0,926] | 0,859 [0,849; 0,869] | 0,0523 [0,0475; 0,0570] | 0,0832 [0,0787; 0,0876] |
| CatBoost persona-período: + beneficios (todo) (previo) | 0,917 [0,905; 0,927] | 0,861 [0,851; 0,871] | 0,0526 [0,0478; 0,0573] | 0,0836 [0,0790; 0,0880] |
| Red GRU de riesgos discretos: ingreso + agregados (oficial) | 0,931 [0,921; 0,942] | 0,877 [0,867; 0,886] | 0,0509 [0,0460; 0,0559] | 0,0825 [0,0778; 0,0868] |
| Red GRU de riesgos discretos: + financiamiento (previo) | 0,922 [0,911; 0,932] | 0,872 [0,863; 0,882] | 0,0541 [0,0491; 0,0590] | 0,0825 [0,0779; 0,0869] |
| Red GRU de riesgos discretos: + expiración y Capstone (previo) | 0,926 [0,916; 0,936] | 0,874 [0,864; 0,883] | 0,0514 [0,0467; 0,0563] | 0,0814 [0,0771; 0,0859] |
| Red GRU de riesgos discretos: + beneficios (todo) (previo) | 0,922 [0,911; 0,933] | 0,869 [0,859; 0,879] | 0,0544 [0,0494; 0,0592] | 0,0844 [0,0797; 0,0887] |

| Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | ΔIBS test | Cumple el criterio estadístico |
|---|---|---|---|---|---|---|
| Logística persona-período | + financiamiento | +0,000 [-0,001; +0,001] | -0,0002 [-0,0006; +0,0003] | -0,001 [-0,002; +0,000] | -0,0003 [-0,0008; +0,0002] | no |
| Logística persona-período | + expiración y Capstone | +0,001 [-0,001; +0,002] | -0,0005 [-0,0010; -0,0001] | +0,001 [-0,000; +0,002] | -0,0003 [-0,0008; +0,0002] | sí (solo sensibilidad; no adoptable) |
| Logística persona-período | + beneficios (todo) | +0,001 [-0,001; +0,003] | -0,0005 [-0,0012; +0,0002] | +0,000 [-0,001; +0,002] | -0,0006 [-0,0014; +0,0003] | no |
| CatBoost persona-período | + financiamiento | +0,000 [-0,001; +0,001] | +0,0006 [+0,0000; +0,0011] | -0,003 [-0,005; -0,002] | +0,0006 [+0,0002; +0,0011] | no |
| CatBoost persona-período | + expiración y Capstone | -0,001 [-0,003; +0,000] | +0,0007 [+0,0002; +0,0012] | -0,003 [-0,004; -0,002] | +0,0003 [-0,0002; +0,0008] | no |
| CatBoost persona-período | + beneficios (todo) | -0,001 [-0,002; +0,000] | +0,0010 [+0,0005; +0,0016] | -0,001 [-0,003; -0,000] | +0,0006 [+0,0002; +0,0011] | no |
| Red GRU de riesgos discretos | + financiamiento | -0,010 [-0,013; -0,006] | +0,0032 [+0,0018; +0,0045] | -0,004 [-0,007; -0,002] | +0,0000 [-0,0011; +0,0012] | no |
| Red GRU de riesgos discretos | + expiración y Capstone | -0,005 [-0,008; -0,002] | +0,0005 [-0,0008; +0,0018] | -0,003 [-0,005; -0,001] | -0,0010 [-0,0021; +0,0000] | no |
| Red GRU de riesgos discretos | + beneficios (todo) | -0,009 [-0,013; -0,005] | +0,0035 [+0,0018; +0,0052] | -0,008 [-0,011; -0,005] | +0,0019 [+0,0004; +0,0036] | no |

**`k = 8`, regla `con_t` (sensibilidad):**

| Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | ΔIBS test | Cumple el criterio estadístico |
|---|---|---|---|---|---|---|
| Logística persona-período | + financiamiento | +0,001 [-0,001; +0,004] | -0,0015 [-0,0027; -0,0004] | +0,001 [-0,001; +0,002] | +0,0003 [-0,0004; +0,0009] | no |
| Logística persona-período | + expiración y Capstone | +0,001 [-0,001; +0,004] | -0,0012 [-0,0023; -0,0003] | +0,001 [-0,001; +0,003] | +0,0006 [-0,0003; +0,0014] | no |
| Logística persona-período | + beneficios (todo) | +0,002 [-0,001; +0,005] | -0,0024 [-0,0038; -0,0011] | +0,001 [-0,001; +0,004] | +0,0003 [-0,0007; +0,0012] | no |
| CatBoost persona-período | + financiamiento | +0,000 [-0,001; +0,002] | -0,0006 [-0,0015; +0,0002] | -0,000 [-0,001; +0,001] | -0,0004 [-0,0011; +0,0003] | no |
| CatBoost persona-período | + expiración y Capstone | -0,000 [-0,002; +0,001] | +0,0008 [+0,0003; +0,0013] | -0,001 [-0,002; +0,000] | -0,0008 [-0,0012; -0,0004] | no |
| CatBoost persona-período | + beneficios (todo) | -0,000 [-0,002; +0,002] | -0,0001 [-0,0011; +0,0006] | -0,001 [-0,002; +0,000] | -0,0003 [-0,0010; +0,0003] | no |
| Red GRU de riesgos discretos | + financiamiento | -0,004 [-0,007; -0,000] | +0,0002 [-0,0017; +0,0020] | -0,001 [-0,004; +0,001] | +0,0002 [-0,0012; +0,0015] | no |
| Red GRU de riesgos discretos | + expiración y Capstone | -0,001 [-0,003; +0,001] | +0,0006 [-0,0006; +0,0019] | -0,004 [-0,007; -0,002] | -0,0006 [-0,0019; +0,0007] | no |
| Red GRU de riesgos discretos | + beneficios (todo) | -0,008 [-0,011; -0,004] | +0,0001 [-0,0019; +0,0020] | -0,003 [-0,006; -0,001] | -0,0003 [-0,0017; +0,0012] | no |

**`k = 10`, regla `previo`:**

| Modelo | C(12) valid | C(12) test | IBS valid | IBS test |
|---|---|---|---|---|
| Logística persona-período: ingreso + agregados (oficial) | 0,939 [0,926; 0,951] | 0,921 [0,912; 0,930] | 0,0980 [0,0910; 0,1057] | 0,1108 [0,1050; 0,1169] |
| Logística persona-período: + financiamiento (previo) | 0,938 [0,925; 0,950] | 0,921 [0,912; 0,930] | 0,0982 [0,0914; 0,1059] | 0,1106 [0,1046; 0,1166] |
| Logística persona-período: + expiración y Capstone (previo) | 0,940 [0,926; 0,951] | 0,921 [0,912; 0,930] | 0,0980 [0,0911; 0,1057] | 0,1118 [0,1060; 0,1178] |
| Logística persona-período: + beneficios (todo) (previo) | 0,939 [0,926; 0,951] | 0,921 [0,912; 0,930] | 0,0979 [0,0911; 0,1056] | 0,1110 [0,1053; 0,1170] |
| CatBoost persona-período: ingreso + agregados (oficial) | 0,965 [0,956; 0,973] | 0,941 [0,933; 0,949] | 0,0559 [0,0482; 0,0641] | 0,0819 [0,0757; 0,0882] |
| CatBoost persona-período: + financiamiento (previo) | 0,965 [0,956; 0,973] | 0,941 [0,933; 0,948] | 0,0556 [0,0479; 0,0635] | 0,0829 [0,0765; 0,0892] |
| CatBoost persona-período: + expiración y Capstone (previo) | 0,966 [0,956; 0,974] | 0,941 [0,932; 0,949] | 0,0550 [0,0474; 0,0629] | 0,0817 [0,0756; 0,0880] |
| CatBoost persona-período: + beneficios (todo) (previo) | 0,966 [0,956; 0,974] | 0,939 [0,931; 0,947] | 0,0550 [0,0471; 0,0630] | 0,0848 [0,0783; 0,0913] |
| Red GRU de riesgos discretos: ingreso + agregados (oficial) | 0,966 [0,958; 0,974] | 0,935 [0,926; 0,942] | 0,0524 [0,0449; 0,0608] | 0,0839 [0,0769; 0,0910] |
| Red GRU de riesgos discretos: + financiamiento (previo) | 0,951 [0,939; 0,962] | 0,924 [0,915; 0,933] | 0,0657 [0,0573; 0,0750] | 0,0933 [0,0860; 0,1006] |
| Red GRU de riesgos discretos: + expiración y Capstone (previo) | 0,959 [0,948; 0,968] | 0,929 [0,920; 0,937] | 0,0589 [0,0508; 0,0681] | 0,0899 [0,0827; 0,0974] |
| Red GRU de riesgos discretos: + beneficios (todo) (previo) | 0,952 [0,940; 0,962] | 0,924 [0,916; 0,933] | 0,0653 [0,0567; 0,0746] | 0,0940 [0,0867; 0,1015] |

| Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | ΔIBS test | Cumple el criterio estadístico |
|---|---|---|---|---|---|---|
| Logística persona-período | + financiamiento | -0,001 [-0,002; +0,000] | +0,0003 [-0,0003; +0,0008] | -0,000 [-0,001; +0,001] | -0,0002 [-0,0006; +0,0002] | no |
| Logística persona-período | + expiración y Capstone | +0,000 [-0,001; +0,002] | +0,0000 [-0,0007; +0,0007] | -0,000 [-0,002; +0,001] | +0,0010 [+0,0001; +0,0020] | no |
| Logística persona-período | + beneficios (todo) | +0,000 [-0,001; +0,002] | -0,0001 [-0,0009; +0,0008] | -0,000 [-0,002; +0,001] | +0,0002 [-0,0006; +0,0011] | no |
| CatBoost persona-período | + financiamiento | -0,000 [-0,001; +0,001] | -0,0003 [-0,0010; +0,0003] | -0,000 [-0,001; +0,001] | +0,0011 [+0,0005; +0,0017] | no |
| CatBoost persona-período | + expiración y Capstone | +0,001 [-0,000; +0,001] | -0,0009 [-0,0016; -0,0002] | -0,000 [-0,001; +0,001] | -0,0001 [-0,0007; +0,0004] | sí (solo sensibilidad; no adoptable) |
| CatBoost persona-período | + beneficios (todo) | +0,000 [-0,000; +0,001] | -0,0009 [-0,0018; -0,0001] | -0,002 [-0,003; -0,001] | +0,0030 [+0,0022; +0,0037] | no |
| Red GRU de riesgos discretos | + financiamiento | -0,016 [-0,021; -0,011] | +0,0132 [+0,0106; +0,0161] | -0,010 [-0,014; -0,007] | +0,0093 [+0,0066; +0,0121] | no |
| Red GRU de riesgos discretos | + expiración y Capstone | -0,008 [-0,012; -0,004] | +0,0064 [+0,0044; +0,0087] | -0,006 [-0,008; -0,003] | +0,0059 [+0,0038; +0,0081] | no |
| Red GRU de riesgos discretos | + beneficios (todo) | -0,014 [-0,020; -0,010] | +0,0129 [+0,0099; +0,0162] | -0,010 [-0,013; -0,007] | +0,0101 [+0,0071; +0,0130] | no |

**`k = 10`, regla `con_t` (sensibilidad):**

| Modelo | Bloque | ΔC(12) valid | ΔIBS valid | ΔC(12) test | ΔIBS test | Cumple el criterio estadístico |
|---|---|---|---|---|---|---|
| Logística persona-período | + financiamiento | +0,004 [+0,000; +0,007] | -0,0042 [-0,0064; -0,0020] | +0,004 [+0,001; +0,008] | -0,0050 [-0,0067; -0,0033] | sí (solo sensibilidad; no adoptable) |
| Logística persona-período | + expiración y Capstone | +0,002 [-0,002; +0,006] | -0,0027 [-0,0051; -0,0002] | +0,000 [-0,003; +0,004] | +0,0009 [-0,0009; +0,0026] | no |
| Logística persona-período | + beneficios (todo) | +0,007 [+0,003; +0,012] | -0,0079 [-0,0109; -0,0050] | +0,005 [+0,000; +0,010] | -0,0054 [-0,0078; -0,0031] | sí (solo sensibilidad; no adoptable) |
| CatBoost persona-período | + financiamiento | -0,000 [-0,001; +0,001] | -0,0007 [-0,0020; +0,0005] | -0,000 [-0,002; +0,002] | +0,0013 [-0,0000; +0,0024] | no |
| CatBoost persona-período | + expiración y Capstone | +0,000 [-0,001; +0,002] | -0,0015 [-0,0025; -0,0006] | +0,000 [-0,001; +0,001] | +0,0005 [-0,0004; +0,0014] | no |
| CatBoost persona-período | + beneficios (todo) | +0,000 [-0,001; +0,001] | -0,0006 [-0,0020; +0,0007] | -0,000 [-0,002; +0,002] | +0,0019 [+0,0005; +0,0033] | no |
| Red GRU de riesgos discretos | + financiamiento | -0,009 [-0,013; -0,005] | +0,0072 [+0,0047; +0,0098] | -0,000 [-0,003; +0,003] | +0,0062 [+0,0032; +0,0090] | no |
| Red GRU de riesgos discretos | + expiración y Capstone | -0,004 [-0,009; -0,000] | +0,0014 [-0,0016; +0,0043] | -0,001 [-0,005; +0,003] | +0,0015 [-0,0013; +0,0041] | no |
| Red GRU de riesgos discretos | + beneficios (todo) | -0,008 [-0,013; -0,003] | +0,0084 [+0,0047; +0,0121] | -0,003 [-0,008; +0,002] | +0,0073 [+0,0034; +0,0112] | no |

**Lectura.** (1) Con la regla `previo` la GRU empeora con beneficios en ambos cortes tardíos, con intervalos que excluyen el 0 (`k = 10`, bloque `todo`: ΔC(12) de valid -0,014 [-0,020; -0,010]; de test -0,010 [-0,013; -0,007]; `k = 8`: test -0,008 [-0,011; -0,005]). CatBoost y la logística quedan en diferencias de milésimas. (2) La única mejora estadística en estos cortes es la de la logística con `con_t` en `k = 10` (ΔIBS de test, bloque `todo`: -0,0054 [-0,0078; -0,0031]), y no se reproduce en la GRU. Es coherente con la fuga del año `t`: la presencia de alguna fila de beneficio es 92,8 % entre quienes egresan en el semestre siguiente frente a 77,7 % en el año anterior (§11.3). Sin una fecha de asignación no se puede separar la señal real de la fuga. (3) Ni siquiera en estos cortes las banderas de expiración y Capstone mejoran a la GRU sin beneficios: los créditos aprobados y el avance de malla ya sitúan al estudiante cerca del egreso.

### 11.7 Resultados por programa y por facultad (test; GRU con todos los beneficios frente a la GRU oficial; regla `previo`)

Solo grupos con n ≥ 100 y al menos 10 egresos dentro de 12 semestres; los grupos con menos de 10 episodios no se publican. La facultad se nombra con `neural_core.facultad`. El C(12) por grupo es una estimación puntual sin intervalo (grupos pequeños) y se lee como descriptivo.

**`k = 4` por facultad:**

| Grupo | n | Egresos ≤ 12 | Observada | Predicha sin beneficios | Predicha con beneficios | C(12) sin | C(12) con | ΔC(12) |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ingeniería y Ciencias Geológicas | 849 | 287 | 33,8 % | 34,5 % | 29,8 % | 0,862 | 0,858 | -0,004 |
| Escuela de Ingeniería | 420 | 182 | 43,3 % | 41,5 % | 37,0 % | 0,890 | 0,895 | +0,004 |
| Escuela de Ciencias Empresariales | 395 | 303 | 76,7 % | 80,0 % | 79,8 % | 0,821 | 0,839 | +0,018 |
| Facultad de Economía y Administración | 360 | 241 | 66,9 % | 64,5 % | 65,4 % | 0,816 | 0,820 | +0,004 |
| Facultad de Ciencias Jurídicas | 331 | 77 | 23,3 % | 35,9 % | 33,6 % | 0,865 | 0,868 | +0,003 |
| Facultad de Medicina | 310 | 118 | 38,1 % | 49,2 % | 46,0 % | 0,880 | 0,870 | -0,011 |
| Facultad de Ciencias | 227 | 82 | 36,1 % | 26,4 % | 24,4 % | 0,809 | 0,823 | +0,013 |
| Facultad de Ciencias de Ingeniería y Construcción | 212 | 55 | 25,9 % | 34,7 % | 31,9 % | 0,852 | 0,846 | -0,006 |
| Facultad de Humanidades | 191 | 155 | 81,2 % | 75,5 % | 76,2 % | 0,722 | 0,737 | +0,015 |
| Facultad de Educación | 170 | 98 | 57,6 % | 57,5 % | 50,8 % | 0,923 | 0,925 | +0,002 |
| Facultad de Ciencias del Mar | 106 | 44 | 41,5 % | 44,9 % | 40,6 % | 0,885 | 0,876 | -0,010 |

Grupos: 14; publicados (n ≥ 100 y al menos 10 egresos): 11; bajo el umbral, no publicados: 1; con menos de 10 episodios, suprimidos: 2.

**`k = 4` por programa:**

| Grupo | n | Egresos ≤ 12 | Observada | Predicha sin beneficios | Predicha con beneficios | C(12) sin | C(12) con | ΔC(12) |
|---|---|---|---|---|---|---|---|---|
| 8326 INGENIERÍA COMERCIAL | 225 | 173 | 76,9 % | 80,7 % | 80,0 % | 0,853 | 0,872 | +0,019 |
| 8323 INGENIERÍA COMERCIAL | 206 | 146 | 70,9 % | 69,9 % | 69,2 % | 0,789 | 0,812 | +0,023 |
| 8613 INGENIERÍA CIVIL INDUSTRIAL | 197 | 110 | 55,8 % | 50,8 % | 43,4 % | 0,783 | 0,782 | -0,000 |
| 8616 INGENIERÍA CIVIL INDUSTRIAL | 197 | 133 | 67,5 % | 63,0 % | 57,2 % | 0,824 | 0,841 | +0,017 |
| 8606 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 185 | 39 | 21,1 % | 16,9 % | 14,1 % | 0,922 | 0,921 | -0,000 |
| 8896 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 170 | 130 | 76,5 % | 79,1 % | 79,5 % | 0,790 | 0,799 | +0,008 |
| 8376 DERECHO | 168 | 26 | 15,5 % | 25,3 % | 24,3 % | 0,894 | 0,889 | -0,005 |
| 8373 DERECHO | 163 | 51 | 31,3 % | 46,8 % | 43,2 % | 0,820 | 0,826 | +0,006 |
| 8383 PSICOLOGÍA | 122 | 103 | 84,4 % | 74,3 % | 77,5 % | 0,789 | 0,782 | -0,007 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 122 | 32 | 26,2 % | 18,3 % | 16,5 % | 0,928 | 0,921 | -0,007 |
| 8403 GEOLOGÍA | 111 | 21 | 18,9 % | 20,9 % | 16,7 % | 0,831 | 0,814 | -0,016 |
| 8483 QUÍMICA Y FARMACIA | 103 | 36 | 35,0 % | 13,5 % | 12,7 % | 0,814 | 0,810 | -0,004 |
| 8223 PEDAGOGÍA EN INGLÉS | 101 | 37 | 36,6 % | 38,0 % | 27,9 % | 0,928 | 0,926 | -0,002 |

Grupos: 48; publicados (n ≥ 100 y al menos 10 egresos): 13; bajo el umbral, no publicados: 27; con menos de 10 episodios, suprimidos: 8.

**`k = 8` (extensión) por facultad:**

| Grupo | n | Egresos ≤ 12 | Observada | Predicha sin beneficios | Predicha con beneficios | C(12) sin | C(12) con | ΔC(12) |
|---|---|---|---|---|---|---|---|---|
| Facultad de Ingeniería y Ciencias Geológicas | 474 | 244 | 51,5 % | 45,0 % | 47,6 % | 0,873 | 0,869 | -0,003 |
| Escuela de Ciencias Empresariales | 348 | 300 | 86,2 % | 89,0 % | 89,3 % | 0,768 | 0,730 | -0,038 |
| Facultad de Economía y Administración | 283 | 238 | 84,1 % | 79,1 % | 79,6 % | 0,777 | 0,744 | -0,033 |
| Facultad de Medicina | 273 | 118 | 43,2 % | 39,3 % | 40,9 % | 0,965 | 0,969 | +0,004 |
| Facultad de Ciencias Jurídicas | 218 | 73 | 33,5 % | 29,2 % | 29,0 % | 0,961 | 0,964 | +0,004 |
| Escuela de Ingeniería | 216 | 173 | 80,1 % | 68,4 % | 69,7 % | 0,868 | 0,872 | +0,004 |
| Facultad de Humanidades | 170 | 152 | 89,4 % | 79,3 % | 79,2 % | 0,779 | 0,784 | +0,005 |
| Facultad de Ciencias | 122 | 69 | 56,6 % | 34,7 % | 35,6 % | 0,870 | 0,885 | +0,014 |
| Facultad de Educación | 103 | 73 | 70,9 % | 69,4 % | 69,5 % | 0,957 | 0,938 | -0,018 |

Grupos: 13; publicados (n ≥ 100 y al menos 10 egresos): 9; bajo el umbral, no publicados: 3; con menos de 10 episodios, suprimidos: 1.

### 11.8 Equidad (test; mismo par de modelos; regla `previo`)

La banda de decil de estos cuadros es la del año del corte (solo agrupación descriptiva, nunca variable). `sexo` solo se usa aquí.

**`k = 4`, por banda de decil:**

| Grupo | n | Egresos ≤ 12 | Observada | Predicha sin beneficios | Predicha con beneficios | C(12) sin | C(12) con | ΔC(12) |
|---|---|---|---|---|---|---|---|---|
| <=6 | 1.993 | 896 | 45,0 % | 47,0 % | 44,8 % | 0,866 | 0,866 | +0,000 |
| desconocida | 1.070 | 480 | 44,9 % | 46,0 % | 41,7 % | 0,837 | 0,843 | +0,006 |
| 8-9 | 580 | 250 | 43,1 % | 46,0 % | 44,8 % | 0,883 | 0,884 | +0,002 |

Grupos: 4; publicados (n ≥ 100 y al menos 10 egresos): 3; bajo el umbral, no publicados: 1; con menos de 10 episodios, suprimidos: 0.

**`k = 4`, por sexo:**

| Grupo | n | Egresos ≤ 12 | Observada | Predicha sin beneficios | Predicha con beneficios | C(12) sin | C(12) con | ΔC(12) |
|---|---|---|---|---|---|---|---|---|
| M | 2.006 | 781 | 38,9 % | 40,8 % | 38,1 % | 0,870 | 0,870 | -0,000 |
| F | 1.705 | 873 | 51,2 % | 53,2 % | 50,6 % | 0,841 | 0,844 | +0,003 |

Grupos: 2; publicados (n ≥ 100 y al menos 10 egresos): 2; bajo el umbral, no publicados: 0; con menos de 10 episodios, suprimidos: 0.

**`k = 8` (extensión), por banda de decil:**

| Grupo | n | Egresos ≤ 12 | Observada | Predicha sin beneficios | Predicha con beneficios | C(12) sin | C(12) con | ΔC(12) |
|---|---|---|---|---|---|---|---|---|
| <=6 | 1.319 | 844 | 64,0 % | 58,7 % | 59,4 % | 0,875 | 0,868 | -0,007 |
| desconocida | 1.029 | 612 | 59,5 % | 53,5 % | 55,1 % | 0,874 | 0,867 | -0,008 |

Grupos: 4; publicados (n ≥ 100 y al menos 10 egresos): 2; bajo el umbral, no publicados: 2; con menos de 10 episodios, suprimidos: 0.

### 11.9 Conclusión y límites

1. **No se adopta ningún modelo con beneficios en T3.** En `k = 4` (el único corte oficial con datos previos al corte) ningún bloque cumple el criterio de adopción (la única mejora en valid con intervalo favorable, GRU + financiamiento en IBS, desaparece en test); en `k = 2` la ablación no es aplicable con la regla por defecto. Los agregados académicos (créditos aprobados, avance de malla, matrícula) ya contienen la cercanía al egreso que se esperaba leer en las banderas.
2. **La señal de Capstone existe, pero no es previa al corte.** Se asigna en el semestre final y, bajo `con_t`, aparece más entre quienes egresan pronto; con fuga detectable en el año `t` no se puede usar como variable.
3. **Datos de entrenamiento.** Las cohortes 2015-2016 no tienen beneficios en `k ≤ 4` (P93): el modelo con beneficios aprende de una fracción del train y la tabla refleja el estado final del año. Con los datos actuales no se puede mejorar sin una fecha de asignación (P90) ni historial anterior a 2024.
4. **Reevaluar** cuando exista una fecha de asignación o cargas por semestre: la regla `con_t` sería entonces verificable y los cortes tardíos podrían adoptarse como cortes operativos de T3 (P98–P105).
5. **Reproducibilidad.** Migración 027 (`python -m pipelines.migrate`), `python -m pipelines.snapshots.t3_beneficios` (tabla lateral `snapshot_t3_beneficios` y cortes tardíos; se repite tras cada reconstrucción de `snapshot_t3`), `python -m evaluation.diagnostico_beneficios_t3`, `python -m evaluation.run_beneficios_t3` (70 min) y `python tools/informe_t3_beneficios.py --doc`. Resultados: `artefactos/resultados_t3_beneficios.json` y `diagnostico_beneficios_t3.json` (ignorados por git); hash de la tabla de beneficios `1c606f4fdf606c14366ad8c6ed3590673d32b3b79b7ab01a3569bc6260eb8f9b`.

## 12. Variables nuevas (18-11-2026)

**Pregunta.** La DAI respondió P117 a P127 el 18-11-2026 y el estudio `evidencia/viabilidad_variables_2026-11-18.md` dejó cuatro variables de T3 construibles sin datos nuevos: créditos restantes, velocidad de aprobación, alcance (cuello de botella) y Capstone / práctica. ¿Alguna mejora el modelo conservado de T3 bajo la regla única D114 (elegir en validación con C(12) y un IBS que no empeore; la prueba solo confirma; el empate se resuelve a favor del modelo más simple)? Solo agregados; ningún RUT, nota ni predicción por persona figura aquí.

**Resultado en una línea.** **El modelo conservado de T3 no cambia en ningún corte** (`dt_lr_adm` en `k` = 0; GRU en `k` = 2 y 4). En `k` = 2 y 4 ninguna variable nueva mejora el C(12) de la GRU en validación con un IC que excluye el cero. En `k` = 0 el bloque de créditos corregidos pasa el criterio en validación (ΔC(12) +0,006 [+0,003; +0,008], ΔIBS −0,0005 [−0,0006; −0,0003]) pero **la prueba lo contradice** (ΔC(12) −0,005 [−0,007; −0,002]): no se adopta. Hallazgo colateral de P126: **los totales de créditos de la malla estaban inflados por las asignaturas electivas** (§12.1); el modelo oficial usa todavía el total sin corregir como entrada (`creditos_malla_total`).

### 12.1 P126: por qué los totales de créditos de la malla eran atípicos

La DAI indicó que no debería haber totales atípicos. **La causa es el cálculo, no los datos.** La malla oficial (`neural_core.asignatura_malla`, una fila por programa, catálogo y asignatura) lista, para cada ramo electivo o de formación general, **todas las asignaturas alternativas** entre las que el estudiante elige una: varias filas con el **mismo código de formación** (`malla_formacion`) **en el mismo semestre**. Sumar las filas cuenta cada alternativa como si fuera obligatoria.

| Medida (284 programa-catálogo) | Suma de todas las filas (la anterior) | Un cupo por grupo de alternativas (corregida) |
|---|---|---|
| Mediana de créditos totales | 256 | 187 |
| Percentil 95 | 1.354 | 318 |
| Máximo | 2.119 | 495 |
| Totales sobre 500 | 108 | 0 |
| Créditos por semestre nominal: mediana (cuartiles 25 y 75) | 43,9 (24,4; 77,8) | 27,9 (19,4; 30,0) |

- El 75,6 % de las filas de la malla pertenece a un grupo de alternativas y el 86,6 % de los programa-catálogo tiene al menos uno. El caso extremo es un programa de 10 semestres que sumaba 2.119 créditos con 387 asignaturas; un solo grupo de alternativas llegaba a 100 asignaturas en un semestre.
- La mediana de 317 del estudio de viabilidad suma además las filas duplicadas de la fuente (40.077 filas en el almacén frente a 29.614 asignaturas únicas en `neural_core`); la mediana de 256 de la tabla es sobre las filas únicas.
- Corregido el cálculo (un cupo por grupo, con la mediana de los créditos de las alternativas), el 75 % de los programa-catálogo queda en 30,0 créditos por semestre nominal o menos y el percentil 95 en 31,5: una escala de 30 créditos por semestre, coherente con SCT-Chile. **252 de 284 son confiables** (entre 15 y 40 créditos por semestre nominal); los otros 32 son planes parciales (por ejemplo, 7 créditos en 2 asignaturas) y `creditos_restantes` queda sin valor ahí.
- La unidad (SCT-Chile o créditos propios) sigue sin confirmarse: lo que se corrige es la **suma**, no la unidad. Queda abierto con la DAI (primera parte de P126).
- Los modelos conservados de T3, T4 y T5 usan `creditos_malla_total` (la suma sin corregir) como entrada. La corrección **no cambia los valores existentes**: queda como columna nueva `creditos_malla_total_corr` en la tabla lateral `snapshot_variables_nuevas`.

### 12.2 Variables y construcción

Tabla lateral `neural_mart.snapshot_variables_nuevas` (migración 031; clave `episodio_id, k`; los snapshots oficiales no cambian). Construcción en `pipelines/snapshots/features_variables.py` y `rules_variables.py`; se reconstruye con `python -m pipelines.snapshots.variables_nuevas` después de cada reconstrucción de `snapshot_t3`. Todas leen intentos con semestre `<= k`; en `k` = 0 solo existen los hechos estáticos de la malla.

| Bloque | Variables (definición) |
|---|---|
| `cred` (P126) | `creditos_malla_total_corr`, `malla_creditos_confiable`, `creditos_restantes` (total corregido menos créditos aprobados; sin valor si el total no es confiable), `velocidad_aprobacion` (créditos aprobados por semestre con inscripciones) y `velocidad_relativa` (frente al ritmo nominal del programa) |
| `alc` (P121, P122) | `alc_sem_pendiente_antiguo` (semestre de malla del ramo reprobado y no aprobado después más antiguo), `alc_rezago` (semestre más alto del último semestre cursado menos el anterior), `alc_pendiente_gt4` (rezago mayor que 4: la banda elástica de P121) y `alc_n_bloqueados` (ramos de la malla sin aprobar a más de 4 semestres del pendiente) |
| `tit` (P125) | `cap_inscrito` y `cap_aprobado` (Capstone o actividad de título), `prac_inscrita` y `prac_aprobada` (práctica o internado), identificados por el nombre del ramo; `malla_tiene_capstone` y `malla_tiene_practica` (estáticas) |
| `t3` | los tres bloques anteriores (15 columnas en `k` = 2 y 4) |

**Punto en el tiempo y P58.** Un ramo reprobado en `201920` o `202010` no tiene fila de reprobación (P58). Esas filas se tratan como no evaluadas (igual que las agregadas robustas de `ACAD_ROBUSTAS`, que tampoco usan conteos de intentos): los conteos de reprobación son **cotas inferiores** para quien cruza esos períodos. El bloque `alc` depende de las reprobaciones; `cred` y `tit` no. Cada candidato se evalúa además **sin** las filas con algún semestre sin reprobaciones registradas (columna «sin P58»; en `k` = 4 de validación no queda ninguna fila limpia).

### 12.3 Ablación (valid decide; test confirma)

Cada candidato es el modelo conservado de su `k` con las mismas entradas más el bloque; el comparador es la predicción **guardada** del conservado (reentrenado, la reproduce con diferencia máxima de 3·10⁻⁸). Remuestreo de 1.000 episodios, los mismos para todos los modelos. ΔC(12) y ΔIBS de validación frente al conservado (el IBS más bajo es mejor).


**`k` = 0** (conservado: `dt_lr_adm`; filas valid 2613, test 4738; reproducción del conservado: diferencia máxima 3.0e-08).

| Candidato | Columnas nuevas | C(12) valid | ΔC(12) valid (IC 95 %) | ΔIBS valid | C(12) test | ΔC(12) test | ΔC(12) valid sin P58 | ¿D114? |
|---|---|---|---|---|---|---|---|---|
| `dt_lr_adm` (conservado) | - | 0,754 [0,737; 0,769] | - | - | 0,742 [0,729; 0,754] | - | - | - |
| `dt_lr_adm+t3` | 5 | 0,754 [0,737; 0,770] | +0,000 [-0,003; +0,003] | +0,0000 [-0,0001; +0,0001] | 0,750 [0,738; 0,762] | +0,008 [+0,006; +0,010] | +0,000 [-0,003; +0,003] | no |
| `dt_lr_adm+cred` | 2 | 0,759 [0,743; 0,774] | +0,006 [+0,003; +0,008] | -0,0005 [-0,0006; -0,0003] | 0,738 [0,725; 0,750] | -0,005 [-0,007; -0,002] | +0,006 [+0,003; +0,008] | **sí** |
| `dt_lr_adm+alc` | 1 | 0,754 [0,737; 0,769] | +0,000 [+0,000; +0,000] | -0,0000 [-0,0000; -0,0000] | 0,742 [0,729; 0,754] | +0,000 [+0,000; +0,000] | +0,000 [+0,000; +0,000] | no |
| `dt_lr_adm+tit` | 2 | 0,755 [0,738; 0,771] | +0,001 [-0,001; +0,003] | -0,0001 [-0,0002; +0,0000] | 0,747 [0,734; 0,759] | +0,005 [+0,003; +0,006] | +0,001 [-0,001; +0,003] | no |

Decisión D114: **dt_lr_adm+cred**.

**`k` = 2** (conservado: `nn_gru`; filas valid 2275, test 4343; reproducción del conservado: diferencia máxima 3.0e-08).

| Candidato | Columnas nuevas | C(12) valid | ΔC(12) valid (IC 95 %) | ΔIBS valid | C(12) test | ΔC(12) test | ΔC(12) valid sin P58 | ¿D114? |
|---|---|---|---|---|---|---|---|---|
| `nn_gru` (conservado) | - | 0,880 [0,870; 0,892] | - | - | 0,839 [0,829; 0,849] | - | - | - |
| `nn_gru+t3` | 15 | 0,880 [0,870; 0,891] | +0,000 [-0,004; +0,005] | +0,0004 [-0,0003; +0,0011] | 0,841 [0,831; 0,850] | +0,002 [-0,001; +0,005] | +0,000 [-0,004; +0,005] | no |
| `nn_gru+cred` | 5 | 0,878 [0,868; 0,890] | -0,002 [-0,005; +0,001] | -0,0000 [-0,0005; +0,0004] | 0,838 [0,829; 0,847] | -0,001 [-0,003; +0,001] | -0,002 [-0,005; +0,001] | no |
| `nn_gru+alc` | 4 | 0,876 [0,866; 0,887] | -0,004 [-0,008; -0,000] | +0,0007 [+0,0001; +0,0013] | 0,834 [0,825; 0,843] | -0,005 [-0,007; -0,003] | -0,004 [-0,008; -0,000] | no |
| `nn_gru+tit` | 6 | 0,877 [0,867; 0,889] | -0,003 [-0,005; -0,001] | +0,0004 [-0,0000; +0,0008] | 0,839 [0,829; 0,848] | -0,000 [-0,002; +0,002] | -0,003 [-0,005; -0,001] | no |

Decisión D114: **sin cambio (se conserva nn_gru)**.

**`k` = 4** (conservado: `nn_gru`; filas valid 1813, test 3711; reproducción del conservado: diferencia máxima 3.0e-08).

| Candidato | Columnas nuevas | C(12) valid | ΔC(12) valid (IC 95 %) | ΔIBS valid | C(12) test | ΔC(12) test | ΔC(12) valid sin P58 | ¿D114? |
|---|---|---|---|---|---|---|---|---|
| `nn_gru` (conservado) | - | 0,900 [0,888; 0,911] | - | - | 0,860 [0,851; 0,868] | - | - | - |
| `nn_gru+t3` | 15 | 0,903 [0,892; 0,914] | +0,004 [-0,001; +0,008] | -0,0019 [-0,0031; -0,0007] | 0,858 [0,850; 0,866] | -0,002 [-0,005; +0,002] | - | no |
| `nn_gru+cred` | 5 | 0,902 [0,891; 0,913] | +0,002 [-0,001; +0,006] | -0,0015 [-0,0022; -0,0008] | 0,857 [0,849; 0,865] | -0,003 [-0,006; -0,000] | - | no |
| `nn_gru+alc` | 4 | 0,898 [0,887; 0,909] | -0,002 [-0,006; +0,001] | +0,0008 [+0,0000; +0,0017] | 0,859 [0,851; 0,867] | -0,001 [-0,004; +0,002] | - | no |
| `nn_gru+tit` | 6 | 0,902 [0,891; 0,913] | +0,002 [-0,000; +0,005] | -0,0004 [-0,0014; +0,0004] | 0,863 [0,854; 0,872] | +0,003 [+0,001; +0,006] | - | no |

Decisión D114: **sin cambio (se conserva nn_gru)**.

### 12.4 Lectura y límites

- **`k` = 2 y 4: sin ganancia.** La GRU ya recoge en su secuencia (créditos aprobados, matrícula, interrupciones) casi todo lo que aportan los créditos restantes y la velocidad; el bloque `alc` incluso empeora el C(12) de validación en `k` = 2 (−0,004 [−0,008; −0,000]). En `k` = 4, `t3` mejora el IBS de validación (−0,0019 [−0,0031; −0,0007]) pero no el C(12) (+0,004 [−0,001; +0,008]), que es la métrica titular, y la prueba no lo confirma.
- **`k` = 0: el único candidato que pasa en validación no se confirma en prueba.** `dt_lr_adm+cred` agrega solo dos columnas estáticas: el total corregido y su bandera de confiabilidad. Gana en validación (cohorte 2018) y pierde en prueba (cohortes 2019 y 2020), con IC que excluye el cero en ambos sentidos. D114 elige en validación pero exige que la prueba confirme; una contradicción significativa en la métrica titular no es una salvedad como el IBS de `k` = 4 de D114: se conserva `dt_lr_adm`. El bloque `tit` mejora la prueba (+0,005 [+0,003; +0,006]) sin pasar en validación (+0,001 [−0,001; +0,003]).
- **Colinealidad del total.** Los candidatos conservan la suma inflada y agregan la corregida; no se probó reemplazarla. Si la DAI valida la unidad (P126), conviene repetir esta prueba con el reemplazo.
- **No hecho.** Oferta histórica de asignaturas (el almacén no guarda la fecha de publicación, P111). El máximo de permanencia en Ciclo Básico (causal 50-A) no se deriva de los datos.

### 12.5 Reproducción

`python -m pipelines.migrate` (031; solo crea tablas laterales), `python -m pipelines.snapshots.variables_nuevas`, `python -m evaluation.ablacion_variables --tarea t3` (escribe `artefactos/ablacion_variables_t3.json` y `artefactos/preds/abl_t3_*.npz`, ignorados por git; no toca las predicciones guardadas `t3_k*_*.npz`). Tablas: `python tools/informe_variables_nuevas.py t3`. Pruebas: `tests/unit/test_variables_nuevas.py`, `test_variables_nuevas_ddl.py` y `test_ablacion_variables.py`. Hash de las variables nuevas `02fac354897ddc13512322a73adb9b4462a8e0e19d994df03d54c75a76a62ea0`.
