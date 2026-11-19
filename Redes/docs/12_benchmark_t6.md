# DAI Neural — Benchmark T6: matrícula en postgrado UCN después del egreso

**Versión:** 0.3 · 18-11-2026 (variables nuevas, §13: sin cambio en el modelo conservado) · 0.2 · 13-11-2026 (reconstrucción consolidada, etapa B: evento por la fuente de estados de postgrado P86, variables `mm_*`, viabilidad D68 revisada) · 0.1 · 13-11-2026 · Fase 4, benchmark T6. Base: `PROMPT_MAESTRO.md` (secciones «Predicción experimental», «Evaluación» y «Fase 4»), `00_plan.md` (D22, D40–D47, D53–D63, D64–D71 y D81–D88), `10_benchmark_t3.md` (población y atributos) y `11_benchmark_t4_t5.md` (evaluación por programa y facultad). Versión del código: `3e2ea71473257e19ef054e6a9544f157a4571dad3a9cc148fcfa8ccde442d1cf`; huella de los datos del snapshot: `972f3d91a2d07ef7a581718c78ddc55fd70ced3853f15d135cab0923197f6e45`.
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4). Solo agregados: ninguna fila individual, RUT ni predicción por persona figura en este documento ni en el repositorio; las predicciones viven en `artefactos/preds/` (ignorado por git). Solo se observa la **matrícula en postgrado de la UCN**: este informe no dice nada sobre estudios de postgrado en otras instituciones y no estima una probabilidad de postgrado fuera de la UCN.

## 1. Definición de la tarea

**T6, «matrícula en postgrado UCN».** Dada una trayectoria de pregrado que llegó al egreso, ¿cuánto tiempo pasa hasta que la misma persona se matricula por primera vez en un programa de postgrado de la UCN? Se estudia como **supervivencia con censura administrativa** (incidencia acumulada a 1, 2 y 4 años) y como **clasificación binaria en cada horizonte** donde el seguimiento está completo.

| Elemento | Definición |
|---|---|
| Unidad | Una **trayectoria de pregrado de T3** (`id_nivel` 1; sin admisiones `IN`, `PE`, `IE`; cohortes 2015 o posteriores; sin los programas de Intercambio; Ingeniería Civil Plan Común unido a su especialidad: D47) que **llegó al egreso** (estado de egreso o titulación, o fila de `titulacion` vinculada: el evento de T3, D46) en un período regular cerrado (D64). |
| Corte | El **semestre del egreso** (`k` = su posición desde la admisión). Todos los atributos son hechos de los semestres `≤ k`. |
| Evento | La **primera matrícula** de la misma persona en cualquier programa de postgrado de la UCN, medida con el estado **`M` (matriculado)** de la fuente de estados de postgrado (`neural_core.estado_postgrado`, de `ban_estados_academicos_pos`), en un semestre posterior al del egreso (D65, P86). Es la fuente de referencia de la DAI y reemplaza como evento principal al `estado_matricula = MATRICULADO` de `matricula_postgrado`, que queda como sensibilidad (§4). La fuente trae el nombre del programa, de donde se deriva el **nivel** (magíster, doctorado, otro: P77). |
| Tiempo | Semestres calendario después del egreso. `AAAA50` cae en el primer semestre del año (como `AAAA10`) y `AAAA60` en el segundo (como `AAAA20`) (D66). |
| Censura | Administrativa, en el último período regular cerrado (`202610`, equivalente a `202650` en postgrado). Una matrícula en un período todavía abierto (`202660`) no es evento. |
| Horizontes | 2, 4 y 8 semestres (1, 2 y 4 años). El horizonte de 1 año se agregó porque es el único con seguimiento completo en las tres particiones. |
| Exclusión | Las personas con una matrícula de postgrado UCN **antes del ingreso, durante el pregrado o en el semestre del egreso** (en cualquiera de las dos fuentes) no están en riesgo de una *primera* matrícula posterior: se excluyen y se cuentan (§2). Con el evento principal se excluyen además 57 unidades con matrícula previa en la fuente de estados (D65). |
| Partición | Por **año de egreso**, fuera de tiempo: train 2022 o antes, valid 2023, test 2024 o después (D67). |
| Variables | Perfil de ingreso (puntajes normalizados `mm_*` y la prueba de admisión `prueba_admision`), programa en vigor y su facultad, trayectoria académica robusta a P58 hasta el egreso, tiempo hasta el egreso frente a la duración nominal y si hay una titulación `U` conocida al corte. **Nunca** `sexo` (solo equidad), `cohorte_anio`, el año de egreso ni nada posterior al corte. |

## Resumen de resultados

1. **Población.** De 30.967 trayectorias de T3, 7.407 llegaron al egreso; tras excluir las que tienen matrícula de postgrado previa o simultánea y las que no tienen un semestre cerrado después del egreso, y las 57 con matrícula previa en la fuente de estados, quedan **7.091 unidades con 219 primeras matrículas** (estado `M`; §2).
2. **Es un evento raro.** La incidencia acumulada después del egreso es 1,9 % [1,6; 2,3] a 1 año, 2,7 % [2,3; 3,1] a 2 años y 3,9 % [3,4; 4,5] a 4 años (§4).
3. **¿Benchmark viable?** Solo en parte, y más que antes. Con el evento por estados se cumple el criterio fijado de antemano para los modelos clásicos (al menos 30 eventos en cada partición: 76, 51 y 92) y **el horizonte de 1 año es concluyente en test** (46 matriculados en 2.100 unidades; antes eran 28). A 2 años hay 12 matriculados en test (no concluyente) y a 4 años ningún seguimiento completo. CatBoost (mínimo 100 eventos de entrenamiento) y el MLP en GPU (mínimo 300) **siguen sin entrenarse**: hay 76 eventos de entrenamiento (§3, §5).
4. **Resultado.** A 1 año en test, el Cox con el perfil de ingreso supera a la incidencia histórica por programa: AP 0,046 [0,030; 0,077] frente a 0,029 [0,020; 0,042] (ΔAP 0,017 [0,005; 0,043]) y ROC-AUC 0,696 [0,625; 0,762] frente a 0,586 [0,513; 0,652]. La trayectoria académica **no agrega nada** (Cox con trayectoria menos Cox de perfil, ΔAP -0,010 [-0,028; -0,001]). El AP absoluto es bajo y el nivel de riesgo está subestimado (§5). El horizonte es concluyente, pero con 46 eventos el resultado sigue siendo exploratorio.
5. **Por programa y facultad.** La incidencia **observada** se puede reportar en 6 programas y 7 facultades, rotuladas con su **nombre** (§6). El **pronóstico agregado** del modelo no es reportable por programa en test y solo en una facultad; con valid + test hay 2 programas y 3 facultades, y en las tres facultades el modelo subestima la tasa (§7). Por nivel, la matrícula en postgrado UCN es sobre todo de magíster (§4).
6. **Fuente de referencia (P86, P80).** La DAI confirmó `ban_estados_academicos_pos` como fuente de postgrado. Su cobertura es completa desde 2015 (586–782 personas matriculadas por año), de modo que el salto de 2023 de `banner_estudiantes_postgrado` era un artefacto de cobertura y no oferta nueva. Con esta fuente la incidencia a 1 año sube de 1,1 % a 1,9 % y los eventos de 142 a 219; la tasa de train sigue siendo menor que la de valid y test (0,9 % frente a 1,9 % y 2,2 % a 1 año; §3 y §8).
7. **Modelo conservado.** Por la regla de D69 el Cox con el perfil de ingreso reemplaza a la línea base (el intervalo pareado de ΔAP a 1 año queda sobre cero), como antes; el resultado es exploratorio pero ahora se apoya en un horizonte concluyente. **Ningún modelo está aprobado para uso individual** (Gate 4, §11).

## Cambios de la reconstrucción consolidada (13-11-2026)

1. **Evento principal por la fuente de estados (P86).** El evento pasa de `estado_matricula = MATRICULADO` de `matricula_postgrado` al estado `M` de `ban_estados_academicos_pos`; el evento anterior se conserva como sensibilidad completa (§4). Se excluyen las unidades con matrícula previa en la fuente de estados (D65).
2. **Variables de admisión.** `mm_*` (mínimo–máximo por prueba, año y campo) y `prueba_admision` reemplazan a los percentiles `pct_*`.
3. **Viabilidad (D68) con la fuente nueva.** Solo el escalón clásico es viable; CatBoost (76 eventos de entrenamiento frente a un mínimo de 100) y la red (mínimo 300) no lo son:

| Fuente del evento | Eventos train / valid / test | Escalón clásico (≥ 30 por partición) | CatBoost (≥ 100 de train) | Red (≥ 300 de train) |
|---|---|---|---|---|
| Estados de postgrado (principal) | 76 / 51 / 92 | sí | no | no |
| `matricula_postgrado` (sensibilidad) | 50 / 34 / 58 | sí | no | no |

4. **Antes y después** (modelo evaluado a 1 año en test; «antes» es la versión 0.1 con el evento anterior):

| Métrica | Antes | Después | Cambio |
|---|---|---|---|
| Eventos de train / valid / test | 50/34/58 | 76/51/92 | — |
| Unidades | 7.148 | 7.091 | -57 |
| Incidencia acumulada a 1 año (todas las unidades) | 0,0110 [0,0086; 0,0136] | 0,0193 [0,0163; 0,0228] | +0,0083 |
| Incidencia acumulada a 4 años (todas las unidades) | 0,0270 [0,0224; 0,0318] | 0,0394 [0,0339; 0,0454] | +0,0123 |
| Incidencia por programa, AP test a 1 año | 0,021 [0,013; 0,039] | 0,029 [0,020; 0,042] | +0,009 |
| Cox (perfil), AP test a 1 año | 0,048 [0,027; 0,103] | 0,046 [0,030; 0,077] | -0,002 |
| Cox (perfil), ROC-AUC test a 1 año | 0,775 [0,690; 0,850] | 0,696 [0,625; 0,762] | -0,079 |
| Cox (perfil) − incidencia por programa, ΔAP pareado | 0,027 [0,008; 0,074] | 0,017 [0,005; 0,043] | -0,010 |

Modelo conservado: Cox (perfil de ingreso) → Cox (perfil de ingreso). Programas con incidencia reportable: 5 → 6; facultades: 6 → 7.

La conclusión de selección no cambia (Cox con el perfil de ingreso), pero el ROC-AUC de test baja de 0,775 a 0,696 y el ΔAP pareado frente a la incidencia por programa de 0,027 a 0,017 (los intervalos se solapan). Con el evento principal la línea base mejora (AP 0,021 a 0,029), de modo que la ventaja del Cox es menor.

## 2. Población y embudo

El embudo parte de la población de T3 (D47) y se detiene en la unidad de T6. Los recuentos son de trayectorias (no de personas). Las cifras de 1 a 9 se muestran como «< 10».

| Paso | Trayectorias |
|---|---|
| Trayectorias de pregrado de las cohortes 2015 o posteriores (población T3: sin IN/PE/IE, sin Intercambio, Plan Común unido a su especialidad) | 30.967 |
| − sin egreso en un período cerrado (el egreso es el evento de T3) | 23.560 |
| = **Trayectorias egresadas** | 7.407 |
| − con egreso anterior al inicio de la fuente de postgrado (201650) | 0 |
| − con matrícula de postgrado UCN **antes** del ingreso a pregrado | 0 |
| − con matrícula de postgrado UCN **durante** el pregrado o en el semestre del egreso | 70 |
| − sin semestre cerrado después del egreso (egreso en el último período cerrado) | 189 |
| = Unidades con el evento anterior (`matricula_postgrado`, sensibilidad) | 7.148 |
| … de ellas, con matrícula posterior al egreso (evento anterior) | 142 |
| − con matrícula previa en la fuente de estados de postgrado (evento principal, D65) | 57 |
| = **Unidades de T6 con el evento principal (estado `M`, P86)** | 7.091 |
| … de ellas, con estado `M` posterior al egreso dentro del seguimiento (evento principal) | 219 |

Todas las exclusiones por matrícula previa corresponden a matrículas **durante el pregrado o en el semestre del egreso**; ninguna es anterior al ingreso (la fuente de postgrado empieza en 201650 y las cohortes son 2015 o posteriores). No hay egresos anteriores al inicio de la fuente. La decisión de excluir (y no de ignorar la matrícula previa) evita que una persona ya matriculada en postgrado cuente como «evento» en el semestre siguiente al egreso solo por continuar (D65, P81).

La fuente de postgrado trae 1.968 filas con `MATRICULADO` de 1.417 personas en 57 programas, entre 201650 y 202660.

## 3. Eventos por partición y viabilidad

La partición por año de egreso deja pocas matrículas en cada tramo. Los criterios se fijaron **antes de entrenar o evaluar ningún modelo** (los recuentos de eventos por partición ya se conocían) (D68): al menos 30 eventos de supervivencia por partición para el escalón clásico (línea base y Cox), 100 eventos de entrenamiento para CatBoost y 300 para una red; un horizonte binario es concluyente solo con al menos 30 matriculados y 30 no matriculados entre las unidades con seguimiento completo.

| Familia de modelos | Mínimo de eventos por partición | train | valid | test | ¿Se entrena? |
|---|---|---|---|---|---|
| Línea base e incidencia por programa, Cox | 30 | 76 | 51 | 92 | sí |
| CatBoost | 100 | 76 | 51 | 92 | no |
| MLP en GPU (3 semillas) | 300 | 76 | 51 | 92 | no |

Eventos y unidades del problema binario (solo unidades con seguimiento hasta el horizonte):

| Horizonte | Partición | Unidades con seguimiento completo | Matriculados en el horizonte | Tasa |
|---|---|---|---|---|
| 1 año | train (egreso hasta 2022) | 2.598 | 23 | 0,9 % |
| 1 año | valid (egreso 2023) | 1.457 | 28 | 1,9 % |
| 1 año | test (egreso 2024 o después) | 2.100 | 46 | 2,2 % |
| 2 años | train (egreso hasta 2022) | 2.598 | 33 | 1,3 % |
| 2 años | valid (egreso 2023) | 1.457 | 45 | 3,1 % |
| 2 años | test (egreso 2024 o después) | 864 | 12 | 1,4 % |
| 4 años | train (egreso hasta 2022) | 2.276 | 51 | 2,2 % |
| 4 años | valid (egreso 2023) | 0 | — | — |
| 4 años | test (egreso 2024 o después) | 0 | — | — |

El seguimiento de test es de 1 a 4 semestres (mediana 3): a 2 años solo hay 864 unidades con seguimiento completo y a 4 años ninguna. El único horizonte con seguimiento completo en las tres particiones es el de 1 año: tiene 23 eventos en train, 28 en valid (no concluyente, menos de 30) y 46 en test (concluyente).

## 4. Análisis descriptivo: incidencia acumulada

La incidencia acumulada es `1 − Kaplan–Meier` del primer semestre con matrícula. Los intervalos son percentiles de 1000 remuestreos **agrupados por persona**. Una celda muestra «—» si a ese horizonte quedan menos de 100 unidades en seguimiento.

| Partición | Unidades | Matriculados después del egreso | Seguimiento (semestres: mín. · mediana · máx.) | 1 año | 2 años | 4 años |
|---|---|---|---|---|---|---|
| Todas las unidades | 7.091 | 219 | — | 1,9 % [1,6; 2,3] | 2,7 % [2,3; 3,1] | 3,9 % [3,4; 4,5] |
| train (egreso hasta 2022) | 2.598 | 76 | 7 · 9,0 · 20 | 0,9 % [0,5; 1,2] | 1,3 % [0,9; 1,7] | 2,6 % [2,0; 3,2] |
| valid (egreso 2023) | 1.457 | 51 | 5 · 6,0 · 6 | 1,9 % [1,3; 2,7] | 3,1 % [2,2; 4,0] | — |
| test (egreso 2024 o después) | 3.036 | 92 | 1 · 3,0 · 4 | 2,9 % [2,3; 3,5] | 3,9 % [3,0; 4,8] | — |

La incidencia de los egresos hasta 2022 es mucho menor que la de los posteriores: el seguimiento de los egresos recientes cae en el período con más matrículas registradas (§8). Por año de egreso (el 2026 y los años con menos de 100 unidades o 10 matriculados se suprimen):

| Grupo | Unidades | Matriculados | 1 año | 2 años |
|---|---|---|---|---|
| 2025 | 1.471 | 45 | 4,3 % [3,0; 5,8] | — |
| 2024 | 1.565 | 47 | 2,2 % [1,5; 3,0] | 3,2 % [2,3; 4,1] |
| 2023 | 1.457 | 51 | 1,9 % [1,2; 2,7] | 3,1 % [2,3; 4,0] |
| 2021 | 921 | 22 | 1,0 % [0,4; 1,7] | 1,5 % [0,8; 2,4] |
| 2022 | 1.148 | 30 | 0,9 % [0,4; 1,5] | 1,1 % [0,6; 1,8] |
| 2020 | 415 | 14 | 0,7 % [0,0; 1,7] | 1,2 % [0,3; 2,4] |

6 grupos reportados y 4 grupos suprimidos (menos de 100 unidades o menos de 10 matriculados); los reportados cubren 6.977 de 7.091 unidades.

Por sexo del registro (descriptivo; `sexo` no es variable del modelo):

| Grupo | Unidades | Matriculados | 1 año | 2 años |
|---|---|---|---|---|
| M | 3.410 | 122 | 2,6 % [2,0; 3,1] | 3,3 % [2,7; 3,9] |
| F | 3.681 | 97 | 1,3 % [1,0; 1,8] | 2,1 % [1,6; 2,6] |

2 grupos reportados y 0 grupos suprimidos (menos de 100 unidades o menos de 10 matriculados); los reportados cubren 7.091 de 7.091 unidades.

Por titulación `U` conocida al corte, por promedio de notas hasta el egreso (terciles de toda la muestra) y por duración respecto de la nominal:

| Grupo | Unidades | Matriculados | 1 año | 2 años |
|---|---|---|---|---|
| titulación U al corte | 5.946 | 197 | 2,2 % [1,8; 2,6] | 3,0 % [2,6; 3,5] |
| sin titulación al corte | 1.145 | 22 | 0,6 % [0,2; 1,1] | 0,9 % [0,4; 1,6] |

2 grupos reportados y 0 grupos suprimidos (menos de 100 unidades o menos de 10 matriculados); los reportados cubren 7.091 de 7.091 unidades.

| Grupo | Unidades | Matriculados | 1 año | 2 años |
|---|---|---|---|---|
| T3 (más alto) | 2.363 | 104 | 3,0 % [2,4; 3,8] | 4,0 % [3,2; 4,8] |
| T2 | 2.363 | 68 | 1,7 % [1,2; 2,2] | 2,4 % [1,8; 3,1] |
| T1 (más bajo) | 2.363 | 47 | 1,1 % [0,7; 1,6] | 1,6 % [1,1; 2,1] |

3 grupos reportados y 1 grupo suprimido (menos de 100 unidades o menos de 10 matriculados); los reportados cubren 7.089 de 7.091 unidades.

| Grupo | Unidades | Matriculados | 1 año | 2 años |
|---|---|---|---|---|
| en la duración nominal o antes | 1.452 | 76 | 3,9 % [3,0; 4,9] | 4,9 % [3,8; 6,0] |
| con atraso | 5.639 | 143 | 1,4 % [1,1; 1,7] | 2,1 % [1,7; 2,5] |

2 grupos reportados y 0 grupos suprimidos (menos de 100 unidades o menos de 10 matriculados); los reportados cubren 7.091 de 7.091 unidades.

Quien egresa dentro de la duración nominal, quien tiene mejor promedio y quien ya tiene titulación `U` al corte se matricula más a menudo en postgrado. Son asociaciones descriptivas, sin ajuste ni lectura causal.

### Sensibilidad a la definición del evento

El evento principal es el estado `M` de la fuente de estados de postgrado (P86). Las alternativas son el evento anterior (`estado_matricula = MATRICULADO` de `matricula_postgrado`) y cualquier fila de `matricula_postgrado` posterior al egreso (incluye «matrícula en trámite» y «post-graduado» sin matrícula, P78):

| Definición del evento | Unidades | train | valid | test | Total de eventos | Incidencia a 1 año | a 2 años | a 4 años |
|---|---|---|---|---|---|---|---|---|
| **Estado `M` de la fuente de estados de postgrado (principal, P86)** | 7.091 | 76 | 51 | 92 | 219 | 1,9 % [1,6; 2,3] | 2,7 % [2,3; 3,1] | 3,9 % [3,4; 4,5] |
| `estado_matricula = MATRICULADO` de `matricula_postgrado` (evento anterior, sensibilidad) | 7.148 | 50 | 34 | 58 | 142 | 1,1 % [0,9; 1,4] | 1,7 % [1,4; 2,0] | 2,7 % [2,2; 3,2] |
| Cualquier fila de postgrado UCN posterior al egreso (`matricula_postgrado`, sensibilidad) | 7.148 | 96 | 44 | 75 | 215 | 1,3 % [1,1; 1,6] | 2,3 % [2,0; 2,7] | 4,2 % [3,6; 4,8] |

**Modelos con el evento anterior (sensibilidad).** Los tres modelos reentrenados con el evento de `matricula_postgrado`:

2.108 unidades con seguimiento completo a 1 año y 28 matriculados en test (evento anterior).

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Incidencia histórica por programa | 0,021 [0,013; 0,039] | 0,631 [0,537; 0,728] | 0,0132 [0,0090; 0,0180] | 0,0122 [0,0081; 0,0170] |
| Cox (perfil de ingreso) | 0,032 [0,020; 0,057] | 0,733 [0,640; 0,811] | 0,0132 [0,0090; 0,0179] | 0,0116 [0,0079; 0,0169] |
| Cox (ingreso + trayectoria académica) | 0,033 [0,020; 0,063] | 0,736 [0,637; 0,816] | 0,0132 [0,0090; 0,0179] | 0,0122 [0,0080; 0,0171] |

Modelo conservado con el evento anterior: **Incidencia histórica por programa** (mejor Cox en valid: Cox (perfil de ingreso); ΔAP frente a la incidencia por programa: 0,011 [-0,004; 0,031]).

### Nivel del programa (magíster, doctorado, otro)

La fuente de estados trae el nombre del programa, de donde se deriva el nivel de la **primera matrícula** (P77): magíster, doctorado u otro (diplomado, postítulo o sin nombre estándar). La incidencia es específica de causa: la primera matrícula de otro nivel censura la unidad en ese momento.

| Nivel del programa | train | valid | test | Total | Incidencia a 1 año | a 2 años | a 4 años |
|---|---|---|---|---|---|---|---|
| Magíster | 63 | 33 | 62 | 158 | 1,3 % [1,0; 1,5] | 1,9 % [1,5; 2,2] | 3,0 % [2,5; 3,5] |
| Doctorado | < 10 | < 10 | 13 | 23 | 0,2 % [0,1; 0,4] | 0,3 % [0,2; 0,5] | 0,3 % [0,2; 0,5] |
| Otro (diplomado, postítulo, sin nombre) | < 10 | 14 | 17 | 38 | 0,4 % [0,3; 0,6] | 0,5 % [0,3; 0,7] | 0,6 % [0,4; 0,8] |

Incidencia específica de causa: la primera matrícula de otro nivel censura la unidad en ese momento. Un recuento de 1 a 9 no se imprime.

La matrícula en postgrado UCN después del egreso es sobre todo de magíster; el doctorado y los demás niveles tienen pocos eventos por partición y no se modelan por separado.


## 5. Modelos y resultados exploratorios

**Modelos entrenados** (misma población en todos): (1) *incidencia histórica por programa* (línea base): `1 − KM` por programa en train, con la incidencia global para los programas con menos de 50 unidades o no vistos; (2) *Cox con L2* sobre el perfil de ingreso + atributos del programa en vigor + facultad; (3) *Cox con L2* sobre el perfil + la trayectoria académica hasta el egreso. La penalización se elige en valid por la concordancia truncada a 2 años. Preprocesamiento ajustado solo con train. **No se entrenaron** CatBoost ni el MLP (§3).

### Test (egreso 2024 o después; IC 95 % del bootstrap agrupado por persona)

**1 año** · 2.100 unidades con seguimiento completo, 46 matriculados · concluyente

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Incidencia histórica por programa | 0,029 [0,020; 0,042] | 0,586 [0,513; 0,652] | 0,0217 [0,0156; 0,0278] | 0,0178 [0,0126; 0,0249] |
| Cox (perfil de ingreso) | 0,046 [0,030; 0,077] | 0,696 [0,625; 0,762] | 0,0215 [0,0155; 0,0276] | 0,0140 [0,0095; 0,0212] |
| Cox (ingreso + trayectoria académica) | 0,037 [0,026; 0,055] | 0,680 [0,611; 0,745] | 0,0216 [0,0155; 0,0276] | 0,0135 [0,0097; 0,0213] |

**2 años** · 864 unidades con seguimiento completo, 12 matriculados · **no concluyente** (menos de 30 matriculados o de 30 no matriculados)

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Incidencia histórica por programa | 0,023 [0,011; 0,056] | 0,643 [0,482; 0,780] | 0,0137 [0,0069; 0,0215] | 0,0105 [0,0052; 0,0187] |
| Cox (perfil de ingreso) | 0,038 [0,013; 0,133] | 0,661 [0,493; 0,818] | 0,0137 [0,0069; 0,0216] | 0,0109 [0,0077; 0,0210] |
| Cox (ingreso + trayectoria académica) | 0,030 [0,011; 0,077] | 0,652 [0,471; 0,813] | 0,0137 [0,0069; 0,0215] | 0,0065 [0,0070; 0,0193] |


Diferencias pareadas en test (mismos remuestreos):

| Horizonte | Diferencia pareada | ΔAP | ΔROC-AUC | Lectura (ΔAP) |
|---|---|---|---|---|
| 1 año | Cox (perfil de ingreso) − Incidencia histórica por programa | 0,017 [0,005; 0,043] | 0,110 [0,037; 0,182] | mejora |
| 1 año | Cox (ingreso + trayectoria académica) − Incidencia histórica por programa | 0,007 [-0,002; 0,021] | 0,094 [0,027; 0,162] | sin diferencia (el intervalo incluye 0) |
| 1 año | Cox (ingreso + trayectoria académica) − Cox (perfil de ingreso) | -0,010 [-0,028; -0,001] | -0,016 [-0,049; 0,014] | empeora |
| 2 años | Cox (perfil de ingreso) − Incidencia histórica por programa | 0,015 [-0,022; 0,105] | 0,018 [-0,123; 0,145] | sin diferencia (el intervalo incluye 0) |
| 2 años | Cox (ingreso + trayectoria académica) − Incidencia histórica por programa | 0,007 [-0,025; 0,047] | 0,008 [-0,107; 0,113] | sin diferencia (el intervalo incluye 0) |
| 2 años | Cox (ingreso + trayectoria académica) − Cox (perfil de ingreso) | -0,008 [-0,087; 0,025] | -0,010 [-0,059; 0,043] | sin diferencia (el intervalo incluye 0) |

### Valid (egreso 2023)

**1 año** · 1.457 unidades con seguimiento completo, 28 matriculados · **no concluyente** (menos de 30 matriculados o de 30 no matriculados)

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Incidencia histórica por programa | 0,020 | 0,492 | 0,0191 | 0,0150 |
| Cox (perfil de ingreso) | 0,044 | 0,668 | 0,0189 | 0,0127 |
| Cox (ingreso + trayectoria académica) | 0,040 | 0,695 | 0,0189 | 0,0132 |

**2 años** · 1.457 unidades con seguimiento completo, 45 matriculados · concluyente

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Incidencia histórica por programa | 0,038 | 0,595 | 0,0304 | 0,0227 |
| Cox (perfil de ingreso) | 0,053 | 0,642 | 0,0302 | 0,0189 |
| Cox (ingreso + trayectoria académica) | 0,054 | 0,667 | 0,0302 | 0,0193 |


| Horizonte | Diferencia pareada | ΔAP | ΔROC-AUC | Lectura (ΔAP) |
|---|---|---|---|---|
| 1 año | Cox (perfil de ingreso) − Incidencia histórica por programa | 0,024 [0,000; 0,103] | 0,176 [0,070; 0,270] | sin diferencia (el intervalo incluye 0) |
| 1 año | Cox (ingreso + trayectoria académica) − Incidencia histórica por programa | 0,020 [0,000; 0,061] | 0,203 [0,092; 0,309] | mejora |
| 1 año | Cox (ingreso + trayectoria académica) − Cox (perfil de ingreso) | -0,004 [-0,067; 0,021] | 0,027 [-0,019; 0,069] | sin diferencia (el intervalo incluye 0) |
| 2 años | Cox (perfil de ingreso) − Incidencia histórica por programa | 0,015 [-0,004; 0,072] | 0,047 [-0,039; 0,139] | sin diferencia (el intervalo incluye 0) |
| 2 años | Cox (ingreso + trayectoria académica) − Incidencia histórica por programa | 0,015 [-0,002; 0,047] | 0,072 [-0,031; 0,181] | sin diferencia (el intervalo incluye 0) |
| 2 años | Cox (ingreso + trayectoria académica) − Cox (perfil de ingreso) | 0,001 [-0,040; 0,018] | 0,025 [-0,010; 0,060] | sin diferencia (el intervalo incluye 0) |

### Lectura

* **Orden, no nivel.** El Cox ordena mejor que la línea base: a 1 año el ROC-AUC de test es 0,696 [0,625; 0,762] frente a 0,586 [0,513; 0,652]; en valid la línea base queda por debajo de 0,5 a 1 año. El Brier y el ECE no mejoran, porque el nivel de riesgo no se recupera.
* **Subestimación del nivel.** El riesgo medio predicho a 1 año de cada grupo de riesgo (0,57–1,46 %) queda por debajo de la incidencia observada del grupo (0,95–5,71 %): el modelo aprende la tasa de base de train (egresos hasta 2022), menor que la de los períodos recientes (§8). Una recalibración con los datos de valid sería posible, pero con 28 eventos a 1 año no se intentó.
* **La trayectoria académica no agrega.** Cox con trayectoria menos Cox de perfil: ΔAP -0,010 [-0,028; -0,001] a 1 año; el intervalo incluye 0 en todos los horizontes.
* **A 2 años en test** hay 12 matriculados (no concluyente): los valores de la tabla (AP con intervalos muy anchos) no se interpretan.
* **Conservado (D69).** Cox con el perfil de ingreso. La regla se cumple a 1 año (el intervalo pareado de ΔAP queda sobre cero), con 46 eventos en test: el horizonte es concluyente, pero el resultado sigue siendo exploratorio.

### Calibración a 1 año en test

Los grupos de riesgo se fusionan hasta tener al menos 10 matriculados cada uno (ningún grupo con 1 a 9 matriculados se imprime):

| Modelo | Grupo de riesgo (1 = más alto) | n | Riesgo medio predicho | Incidencia observada |
|---|---|---|---|---|
| Cox (perfil de ingreso) | 1 | 210 | 1,46 % | 5,71 % |
| Cox (perfil de ingreso) | 2 | 420 | 1,03 % | 3,33 % |
| Cox (perfil de ingreso) | 3 | 420 | 0,81 % | 2,38 % |
| Cox (perfil de ingreso) | 4 | 1.050 | 0,57 % | 0,95 % |
| Incidencia histórica por programa | 1 | 883 | 1,09 % | 3,40 % |
| Incidencia histórica por programa | 2 | 1.217 | 0,06 % | 1,31 % |

El 10 % de mayor riesgo concentra una incidencia observada de 5,7 % frente a 1,8 % en el resto: una discriminación útil como orden, con niveles absolutos pequeños.

## 6. Resultados por programa y facultad: incidencia observada

Tablas de la incidencia acumulada observada en **toda la muestra** (train + valid + test), solo para programas (el vigente al egreso) y facultades con **al menos 100 unidades y 10 matriculados**; el resto se suprime y solo se cuenta. Es un resultado descriptivo, no un pronóstico.

| Grupo | Unidades | Matriculados | 1 año | 2 años |
|---|---|---|---|---|
| 8486 · MEDICINA | 239 | 38 | 12,5 % [8,4; 16,9] | 14,6 % [10,1; 19,6] |
| 8403 · GEOLOGÍA | 179 | 14 | 6,0 % [2,5; 9,7] | 8,5 % [4,2; 13,1] |
| 8613 · INGENIERÍA CIVIL INDUSTRIAL | 387 | 13 | 3,2 % [1,5; 5,0] | 3,5 % [1,8; 5,4] |
| 8673 · INGENIERÍA EN CONSTRUCCIÓN | 209 | 16 | 2,1 % [0,5; 4,3] | 6,6 % [3,1; 10,6] |
| 8383 · PSICOLOGÍA | 411 | 16 | 1,6 % [0,5; 3,0] | 2,5 % [1,1; 4,3] |
| 8323 · INGENIERÍA COMERCIAL | 583 | 11 | 1,0 % [0,3; 1,9] | 1,5 % [0,5; 2,6] |

6 grupos reportados y 46 grupos suprimidos (menos de 100 unidades o menos de 10 matriculados); los reportados cubren 2.008 de 7.091 unidades.

| Grupo | Unidades | Matriculados | 1 año | 2 años |
|---|---|---|---|---|
| Facultad de Ciencias | 313 | 27 | 8,4 % [5,3; 12,0] | 9,4 % [6,1; 13,0] |
| Facultad de Medicina | 697 | 41 | 4,4 % [2,9; 6,0] | 5,1 % [3,5; 6,8] |
| Facultad de Ingeniería y Ciencias Geológicas | 1.303 | 55 | 3,0 % [2,1; 3,9] | 3,9 % [2,8; 5,0] |
| Facultad de Ciencias de Ingeniería y Construcción | 327 | 20 | 2,4 % [0,9; 4,3] | 5,8 % [3,2; 8,8] |
| Facultad de Humanidades | 629 | 20 | 1,5 % [0,6; 2,6] | 2,1 % [1,0; 3,3] |
| Facultad de Educación | 383 | 16 | 1,1 % [0,3; 2,4] | 3,1 % [1,2; 5,0] |
| Facultad de Economía y Administración | 930 | 15 | 0,8 % [0,3; 1,4] | 1,2 % [0,6; 2,0] |

7 grupos reportados y 7 grupos suprimidos (menos de 100 unidades o menos de 10 matriculados); los reportados cubren 4.582 de 7.091 unidades.

Las facultades se rotulan con su **nombre** (`neural_core.facultad`, de `common.facultad_d`; P76, P85) y los programas con su código y nombre. Las diferencias de nivel son grandes (Medicina y Ciencias frente a Economía y Administración), pero el número de matriculados por grupo es pequeño y las tasas dependen del año de egreso de cada programa (cohortes distintas).

## 7. Pronóstico agregado por programa y facultad

El mismo criterio de reportabilidad (n ≥ 100 y al menos 10 matriculados en el horizonte) se aplica al **pronóstico agregado del modelo conservado** frente a la línea base, a 1 año, entre las unidades con seguimiento completo.

| Evaluación | Nivel | Grupos | Reportables (n ≥ 100 y ≥ 10 matriculados) | Suprimidos | Unidades en reportables |
|---|---|---|---|---|---|
| test (1 año; 2.100 unidades) | programa | 46 | 0 | 46 | 0 de 2.100 |
| test (1 año; 2.100 unidades) | facultad | 14 | 1 | 13 | 392 de 2.100 |
| valid + test (1 año; 3.557 unidades) | programa | 48 | 2 | 46 | 349 de 3.557 |
| valid + test (1 año; 3.557 unidades) | facultad | 14 | 3 | 11 | 1.120 de 3.557 |

**Ningún programa y una sola facultad son reportables en test.** Con valid + test, que suma más eventos, lo son 2 programas y 3 facultades:

| Facultad | n | Matriculados | Tasa observada | Riesgo medio predicho | Brecha (pred. − obs.) | Brecha de la incidencia histórica |
|---|---|---|---|---|---|---|
| Facultad de Ciencias | 170 | 12 | 7,1 % [3,5; 11,1] | 1,5 % [1,5; 1,6] | -5,5 % [-9,6; -2,0] | -6,2 % [-10,2; -2,7] |
| Facultad de Medicina | 321 | 14 | 4,4 % [2,4; 6,8] | 1,0 % [1,0; 1,0] | -3,4 % [-5,8; -1,4] | -3,9 % [-6,3; -1,9] |
| Facultad de Ingeniería y Ciencias Geológicas | 629 | 25 | 4,0 % [2,6; 5,7] | 0,8 % [0,8; 0,9] | -3,1 % [-4,8; -1,8] | -3,4 % [-5,1; -2,0] |

En las tres, el modelo y la línea base **subestiman** la incidencia observada en 3 a 6 puntos porcentuales: el pronóstico agregado por programa y facultad **no es utilizable** con estos datos. Lo útil a este nivel es la incidencia observada de §6.

## 8. Cobertura de la fuente de postgrado (P80, P86)

La fuente anterior (`banner_estudiantes_postgrado`, filas `MATRICULADO`) registraba 62, 25, 52, 65, 24, 51 y 38 personas matriculadas en 2016–2022 frente a 293, 253 y 264 en 2023–2025. La fuente de estados (`ban_estados_academicos_pos`) registra 586–782 personas con estado `M` por año desde 2015, y las de la fuente anterior están contenidas en ella (D79). Es decir, el salto de 2023 era un artefacto de **cobertura** de la fuente anterior y no oferta nueva. Con el evento principal por estados:

* la tasa de base de train (egresos hasta 2022) sigue siendo menor que la de valid y test (0,9 % frente a 1,9 % y 2,2 % a 1 año), pero ya no por un registro incompleto: parte es el período del seguimiento (los egresos recientes se observan en años con más matrícula) y parte la cohorte;
* con el evento anterior la línea base aprendida en train no transfería (ROC-AUC de 0,44 a 0,63); con el evento principal se mantiene entre 0,49 y 0,64 en valid y test, es decir, la incidencia por programa sigue siendo una referencia débil;
* un modelo de supervivencia con escala de tiempo calendario o con una covariable de período (no se usó) podría separar ambos efectos con más datos.

## 9. Equidad por sexo (descriptivo)

`sexo` es un dato del registro y nunca una variable. Descriptivamente, la incidencia observada a 2 años es mayor en los hombres (3,3 % [2,7; 3,9]) que en las mujeres (2,1 % [1,6; 2,6]). Para el modelo conservado, a 1 año en valid + test:

| Sexo (registro) | Unidades | Matriculados | Tasa observada | Riesgo medio predicho | AP | ROC-AUC |
|---|---|---|---|---|---|---|
| F | 1.808 | 21 | 1,16 % | 0,81 % | 0,021 | 0,653 |
| M | 1.749 | 53 | 3,03 % | 0,83 % | 0,062 | 0,695 |

El riesgo medio predicho es el mismo en ambos sexos (el modelo no usa `sexo` y sus variables no reproducen la brecha), de modo que **la brecha observada no se refleja en el modelo**. Con menos de 10 matriculadas en valid + test a 1 año en el grupo de mujeres, sus tasas observadas, AP y ROC-AUC se suprimen. No se aplicó ninguna corrección; el análisis es descriptivo, sin lectura causal.

## 10. Costo computacional

El benchmark completo (descriptivo con bootstrap de 1000 remuestreos, dos Cox, evaluación en tres horizontes, tablas por grupo y MLflow) tarda 60 s en CPU, con un pico de RAM de 817 MB (límite fijado: 6 GB). No se usó la GPU: el MLP no se entrenó.

| Modelo | Segundos de entrenamiento | Columnas de entrada | Penalización elegida (valid) |
|---|---|---|---|
| Incidencia histórica por programa | 0,0 | — | — |
| Cox (perfil de ingreso) | 0,8 | 48 | 0,1 |
| Cox (ingreso + trayectoria académica) | 0,8 | 68 | 0,3 |

## 11. Límites y alcance

1. **El uso no está aprobado.** Informe técnico; las predicciones individuales no se publican ni se exponen en la Bóveda, y los agregados no tienen endpoint ni vista.
2. **Pocos eventos.** 219 matrículas posteriores al egreso en 7.091 unidades; a 1 año hay 46 matriculados en test (concluyente), a 2 años 12 y a 4 años ningún seguimiento completo. CatBoost y la red no son viables (D68). Las diferencias del §5 son exploratorias.
3. **Solo la UCN.** El evento es la matrícula en un programa de postgrado de la UCN. No se observa el postgrado en otras instituciones y no se inventa una probabilidad de postgrado externo; una persona sin matrícula UCN puede haberse matriculado fuera (P82).
4. **Nivel del programa derivado del nombre (P77).** La fuente de estados trae el nombre del programa y el nivel (magíster, doctorado, otro) se deriva de su nombre estándar; la mayoría de los diplomados no lo tiene y cae en «otro». El significado de los estados (`W` «Post-Graduado» con y sin matrícula, `J` «en trámite») se tomó de la respuesta de la DAI (P78).
5. **Deriva entre particiones.** La tasa de base de train es menor que la de valid y test; los niveles de riesgo no son transferibles entre particiones (§8).
6. **Matrícula previa excluida (P81).** 70 trayectorias con matrícula de postgrado durante el pregrado o en el semestre del egreso quedan fuera: son un caso de articulación que merece su propia definición.
7. **Facultades por nombre (P76, P85).** El nombre viene de `common.facultad_d`; una unidad sin nombre queda con su código.
8. **Equidad solo descriptiva.** `sexo` no es variable, pero otras variables pueden representarlo parcialmente.
9. **Egresos con titulación.** El evento de T3 es el egreso (`Z`); la titulación `U` se usa como variable (si ya existe al corte) y no como punto final (D46).

## 12. Reproducción

```
.venv-ml/Scripts/python.exe -m pipelines.migrate                  # 018_snapshot_t6.sql
.venv-ml/Scripts/python.exe -m pipelines.snapshots.t6             # reconstruye neural_mart.snapshot_t6 (+ _resumen)
.venv-ml/Scripts/python.exe -u -m evaluation.run_t6               # artefactos/resultados_t6.json (agregados), MLflow t6_postgrado_ucn
.venv-ml/Scripts/python.exe tools/informe_t6.py --doc             # regenera este documento
```

Entorno: `.venv-ml` (Python 3.11; lifelines, scikit-learn, pandas, MLflow). Credenciales solo por las variables `DEV_*` del entorno. Pruebas: `tests/unit/test_snapshot_t6.py` (reglas de etiqueta y censura, exclusión de matrícula previa, embudo, perturbación y borrado de hechos posteriores al corte), `tests/unit/test_metrics_t6.py` (incidencia acumulada contra valores calculados a mano, supresión de grupos, métricas por horizonte, calibración), `tests/unit/test_models_t6.py`, `tests/unit/test_run_t6.py` (viabilidad), `tests/unit/test_informe_t6.py`, `tests/unit/test_t6_ddl.py` y `tests/integration/test_snapshot_t6.py` (recálculo independiente en SQL del tiempo, evento y seguimiento y de los semestres matriculados e intentos hasta el corte).

## 13. Variables nuevas (18-11-2026)

**Pregunta.** Con las respuestas de la DAI (P125 y el estudio de viabilidad del 18-11-2026): ¿mejoran el modelo conservado de T6 (`cox_perfil`) el ranking de egreso dentro del programa, el área de conocimiento y la nota de la actividad de título o práctica, bajo la regla única D114 (elegir en validación con el AP a un año; la prueba solo confirma; el empate se resuelve a favor del modelo más simple)? Solo agregados.

**Resultado en una línea.** **El modelo conservado de T6 no cambia.** Ningún candidato separa de cero la diferencia pareada de AP en validación, que solo tiene 20 eventos a un año (50 en entrenamiento). La prueba (28 eventos) sí muestra una mejora clara con el **área de conocimiento** (ΔAP +0,074 [+0,023; +0,180]), pero D114 no permite que la prueba elija: queda como hipótesis a confirmar con más cohortes.

### 13.1 Variables

Tabla lateral `neural_mart.snapshot_variables_nuevas_t6` (migración 031; una fila por egresado de `snapshot_t6`; el snapshot oficial no cambia). Construcción en `pipelines/snapshots/features_variables.py` (`ranking_egreso`, `nota_titulo`); se reconstruye con `python -m pipelines.snapshots.variables_nuevas`.

| Variable | Definición | Cobertura |
|---|---|---|
| `ranking_prom_egreso` | proporción de los egresados del **mismo programa**, en los 6 semestres hasta el semestre de egreso propio (inclusive), cuyo promedio final es menor o igual al propio; solo se leen egresados de ese semestre o anteriores (nunca posteriores), con al menos 10 pares | 96,5 % |
| `nota_titulo` | nota del último intento evaluado de Capstone o actividad de título (por nombre del ramo, P125) hasta el egreso | 50,0 % |
| `nota_practica` | ídem para práctica profesional o internado | 57,4 % |
| `area_conocimiento` (categórica) | área del programa vigente al egreso (`neural_core.programa`) | 100 % |

Bloques de la ablación: `area`; `ranking`; `titulo` (las dos notas); `todo`. Los candidatos son el modelo conservado más el bloque (`cox_perfil+…`) y, como referencia, `cox_agg+todo`. **No se construyó** la bandera del programa de articulación pregrado-postgrado (`banner.programas_posgrado_articulados_pregrado`): la tabla no está extraída ni en `neural_stg` y se dejó fuera (79 filas, 11 programas; extraerla es una tarea aparte).

### 13.2 Ablación (valid decide; test confirma)

El comparador es el conservado **reentrenado sobre el `snapshot_t6` actual**: las predicciones guardadas de T6 (13-11-2026) vienen de una construcción anterior del snapshot con 7 filas menos en validación y 8 en prueba, y el reentrenado difiere de ellas como máximo 0,021 en las filas comunes. Horizonte principal (un año), AP entre quienes tienen seguimiento completo.

Horizonte 2 semestres; valid 1464 filas y 20 eventos, test 2108 y 28; eventos de entrenamiento 50.

| Candidato | Bloque | AP valid | ΔAP valid (IC 95 %) | AP test | ΔAP test (IC 95 %) | ¿D114? |
|---|---|---|---|---|---|---|
| `cox_perfil` (conservado) | - | 0,036 [0,017; 0,078] | - | 0,032 [0,020; 0,057] | - | - |
| `cox_perfil+area` | area | 0,050 [0,021; 0,124] | +0,014 [-0,008; +0,066] | 0,106 [0,047; 0,227] | +0,074 [+0,023; +0,180] | no |
| `cox_perfil+ranking` | ranking | 0,045 [0,020; 0,101] | +0,009 [-0,005; +0,035] | 0,037 [0,022; 0,072] | +0,005 [-0,001; +0,019] | no |
| `cox_perfil+titulo` | titulo | 0,040 [0,019; 0,083] | +0,004 [-0,009; +0,020] | 0,043 [0,024; 0,090] | +0,012 [+0,003; +0,034] | no |
| `cox_perfil+todo` | todo | 0,045 [0,020; 0,117] | +0,009 [-0,011; +0,053] | 0,110 [0,049; 0,240] | +0,079 [+0,026; +0,192] | no |
| `cox_agg+todo` | todo | 0,039 [0,017; 0,103] | +0,003 [-0,023; +0,048] | 0,119 [0,051; 0,261] | +0,088 [+0,029; +0,210] | no |

Decisión D114: **sin cambio (se conserva cox_perfil)**.

### 13.3 Lectura y límites

- **La validación no tiene poder.** Con 20 eventos a un año, un AP de 0,036 y un IC de la diferencia pareada que incluye el cero en todos los candidatos, D114 conserva `cox_perfil` (el empate favorece al más simple).
- **Señal en prueba, sin adopción.** `area` y `todo` suben el AP de prueba de 0,032 a 0,106 y 0,110, con diferencias pareadas que excluyen el cero. Es una pista sobre programas con más postgrado propio, no una evidencia de selección; se podrá evaluar cuando haya más egresados (el entrenamiento tiene 50 eventos y no alcanza el mínimo para CatBoost ni redes, `rules_t6`). `ranking` y `titulo` no aportan en validación y apenas en prueba.
- **El ranking** se calcula con los egresados del `snapshot_t6` (población elegible), no con todos los egresados del programa; no usa nunca egresados posteriores al propio.
- **Variables no incluidas.** Investigación, ayudantías y publicaciones (P120: no existe registro de ayudantes; las publicaciones con estudiante son una señal débil y sensible); modalidad y jornada de los postgrados (P124 sigue abierta).

### 13.4 Reproducción

`python -m evaluation.ablacion_variables --tarea t6` (escribe `artefactos/ablacion_variables_t6.json` y `artefactos/preds/abl_t6_*.npz`, ignorados por git; no toca `t6_*.npz`). Tabla: `python tools/informe_variables_nuevas.py t6`. Hash de las variables nuevas `02fac354897ddc13512322a73adb9b4462a8e0e19d994df03d54c75a76a62ea0`.
