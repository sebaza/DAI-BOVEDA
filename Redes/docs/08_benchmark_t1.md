# DAI Neural — Benchmark T1: continuidad a un año

**Versión:** 0.8 · 18-11-2026 (variables nuevas de la DAI P117–P127 en T1: 18 variables en el punto del tiempo y reevaluación con D114, §16; sin cambio de modelo) · 0.7 · 16-11-2026 (modelo conservado por la regla única de selección en validación, §12, D114) · 0.6 · 16-11-2026 (montos corregidos, validación 2024/2025 y adopción de CatBoost + beneficios en `k = 1` desde la cohorte 2024, §15.8-15.9, D110-D113) · 0.5 · 16-11-2026 (beneficios con historial de cargas: vista en el punto del tiempo, fuga medida y T1 reevaluado, §15, D96–D99) · 0.4 · 16-11-2026 (beneficios estudiantiles de `banner.banner_beneficios`: ablación «+ beneficios», extensión a `k = 4`, diagnóstico de fuga y vista por facultad, §14; la configuración oficial no cambia) · 0.3 · 13-11-2026 (reconstrucción consolidada, etapa B: variables de admisión `mm_*` + prueba) · 0.2 · 12-11-2026 · Fase 4, benchmark T1 con la configuración oficial fijada por las respuestas de la DAI del 12-11-2026 (P49–P52, tercera ronda). Base: `PROMPT_MAESTRO.md` (Predicción experimental, Evaluación, Fase 4; no negociables 4 y 5), `03_reglas_academicas.md`, `05_modelo_datos.md`, `07_diseno_fase3.md`.
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4: benchmark técnico completo, pendiente la revisión institucional y la aprobación de uso). Solo agregados: ninguna fila individual, nota, RUT ni predicción por persona figura en este documento ni en el repositorio.

## Resumen

- **Tarea.** Para un episodio de pregrado vigente al cierre del semestre regular `k` (`k = 1, 2`), ¿sigue matriculado en la UCN dos períodos regulares después? El evento es la **no continuidad observada** (no «deserción»), definida por la DAI como «el estudiante ya no se encuentra matriculado» (P51). Elegibles: 44.116 (`k = 1`) y 28.871 (`k = 2`); con etiqueta observada: 40.572 y 23.310. **Configuración oficial (P49/P50):** train = cohortes 2015–2019 (12.012 y 11.247 filas), valid = 2020–2021, test = 2022–2023 (4.934 filas, 5,7 % de eventos, y 4.719, 10,6 %).
- **Etiqueta.** De los `no_continua` observados, 70,5 % (`k = 1`) y 90,9 % (`k = 2`) tienen un estado de salida explícito (`E`, `B`, `O`…); 25,1 % y 2,2 % son solo ausencia de estados. La ausencia pesa casi toda en las cohortes anteriores a 2014, que la configuración oficial deja fuera del entrenamiento (siguen en el snapshot con su estado).
- **Resultado principal (test, configuración oficial).** El perfil de ingreso solo discrimina poco (AP 0,104 en `k = 1`, 0,163–0,175 en `k = 2`; tasa histórica por programa: 0,071 y 0,122). Al agregar el desempeño académico hasta el corte, el AP sube a 0,307–0,360 (`k = 1`) y 0,526–0,552 (`k = 2`), con ROC-AUC 0,857 y 0,890 (CatBoost); el 10 % de mayor riesgo contiene una fracción de 0,561 y 0,551 de los eventos (CatBoost, Recall@10 %).
- **La red neuronal no gana.** En test la GRU sobre la secuencia de semestres (AP 0,330 y 0,526) no supera a CatBoost (0,360 y 0,552): GRU − CatBoost = -0,030 [-0,052; -0,009] y -0,026 [-0,042; -0,007], **en ambos cortes el intervalo queda bajo cero, es decir, CatBoost supera a la GRU** (con las variables de admisión corregidas; en la versión 0.2 los intervalos incluían el cero). Frente a la logística (0,307 y 0,537) la GRU solo tiene ventaja en `k = 1` (§5.3). En valid de `k = 2` la GRU ya no supera a CatBoost en AP (§5.3); la comparación válida es la de test. Se conserva **CatBoost con ingreso + agregados**, con la logística como alternativa explicable.
- **Calibración y equidad.** Con el entrenamiento desde 2015 todos los modelos quedan razonablemente calibrados en test (ECE 0,007–0,018 en `k = 1`, 0,018–0,057 en `k = 2`); la tabla de equidad por sexo es descriptiva (en `k = 1` el AP de CatBoost es 0,423 en mujeres y 0,315 en hombres en valid y mejor en mujeres también en test; en `k = 2` es equivalente: 0,558 y 0,545).
- **Advertencias.** (i) La señal viene sobre todo del desempeño ya observado, incluidos quienes no tuvieron ramos evaluados en el semestre; no es un sistema de alerta temprana. (ii) Los datos anteriores a 2015 no son utilizables para segundos semestres (P49) y el registro de salidas cambió hacia 2014 (P50): la ventana de entrenamiento oficial es 2015–2019; la DAI buscará registros anteriores y, si los entrega, habrá que repetir el benchmark. (iii) Con 280 y 499 eventos en test, diferencias menores a ≈ 0,03 de AP no son separables.

- **Beneficios (16-11-2026, §14).** Agregar la situación de financiamiento (gratuidad, crédito, becas, mérito de ingreso, banda de decil, expiración de gratuidad, Capstone y, en `k = 4`, la pérdida de un beneficio) **no mejora de forma detectable** el modelo oficial: en `k = 2` el ΔAP pareado de CatBoost es +0,006 [-0,001; +0,012] en valid y -0,006 [-0,013; +0,000] en test; en `k = 4` con pérdidas es +0,005 [-0,010; +0,019] en valid. En `k = 1` sube el AP de test (+0,033 [+0,017; +0,051]), pero el diagnóstico de fuga (§14.2) muestra que la vista final de la fuente no es la del cierre del primer semestre (hay filas que se cargan o se retiran después, sobre todo de quienes salen durante el año), por lo que **no se adopta**; sin esas personas la ganancia es +0,014 [+0,001; +0,026]. `benef_sem2` y `total` se excluyen siempre (se anulan después del cierre). El resultado oficial de `k = 1, 2` y el hash de datos no cambian.
- **Beneficios con historial de cargas (16-11-2026, §15).** Con el historial de cargas de `banner_beneficios_full` (desde 2024) se construyó la vista de beneficios tal como existía al corte (31-jul y 30-nov). En `k = 1` la vista final sobrestima la presencia de beneficios (74,9 % frente a 66,2 % de quienes continúan; el crédito se carga tarde), pero **la salida durante el año de ingreso no se debe a filas retiradas**: esas personas no tenían fila al corte. Con la vista en el punto del tiempo (cohortes 2024-2025, entrenamiento aún con la vista final) los beneficios suman +0,036 [+0,015; +0,059] de AP a CatBoost en `k = 1`, casi igual que con la vista final (-0,005 [-0,017; +0,006]), pero la ganancia desaparece sin quienes salen durante el año (+0,006 [-0,013; +0,026]); en `k = 2` +0,010 [-0,001; +0,021]. **No se adoptan**; la línea de `k = 1` queda abierta a la respuesta de la DAI sobre la fecha de salida (P96) y a más años de historial.
- **Modelo oficial de `k = 1` desde la cohorte 2024 (16-11-2026, §15.8-15.9, D111-D113).** Con los montos corregidos (P97) y la vista de beneficios al corte, CatBoost + beneficios se eligió en 2024 (valid) y se confirmó en 2025 (test): AP 0,248 frente a 0,205 del modelo académico, ΔAP +0,043 [+0,011; +0,070], ROC-AUC +0,014 [+0,003; +0,027], sin empeorar la calibración. La DAI lo adoptó como modelo de `k = 1` para las cohortes desde 2024; las cifras históricas de este resumen siguen siendo solo académicas y no se comparan con estas. `k = 2` no cambia.

## Cambios de la reconstrucción consolidada (13-11-2026)

La única modificación del lado del modelo en T1 es el perfil de ingreso: `mm_*` + `prueba_admision` reemplazan a los percentiles `pct_*` (P87). Los datos de la etapa A (nombre de facultad, bandas de nota, traslados y estados) no afectan a la etiqueta de T1. Comparación de las métricas de test antes y después (configuración oficial y sensibilidad):

| Métrica | Antes | Después | Cambio |
|---|---|---|---|
| oficial (train desde 2015), k = 1: AP de test, Tasa histórica (programa, k) | 0,071 [0,061; 0,086] | 0,071 [0,061; 0,086] | +0,000 |
| oficial (train desde 2015), k = 1: AP de test, CatBoost, solo ingreso | 0,104 [0,085; 0,132] | 0,104 [0,085; 0,133] | +0,001 |
| oficial (train desde 2015), k = 1: AP de test, Logística, ingreso + agregados | 0,305 [0,250; 0,360] | 0,307 [0,251; 0,360] | +0,001 |
| oficial (train desde 2015), k = 1: AP de test, CatBoost, ingreso + agregados | 0,341 [0,280; 0,394] | 0,360 [0,303; 0,416] | +0,020 |
| oficial (train desde 2015), k = 1: AP de test, GRU, ingreso + secuencia | 0,325 [0,268; 0,380] | 0,330 [0,271; 0,384] | +0,005 |
| oficial (train desde 2015), k = 1: ROC-AUC de test, CatBoost, ingreso + agregados | 0,854 [0,828; 0,875] | 0,857 [0,832; 0,879] | +0,003 |
| oficial (train desde 2015), k = 1: GRU − CatBoost, ΔAP pareado | -0,015 [-0,036; 0,007] | -0,030 [-0,052; -0,009] | -0,015 |
| oficial (train desde 2015), k = 2: AP de test, Tasa histórica (programa, k) | 0,122 [0,109; 0,136] | 0,122 [0,109; 0,136] | +0,000 |
| oficial (train desde 2015), k = 2: AP de test, CatBoost, solo ingreso | 0,165 [0,145; 0,189] | 0,163 [0,143; 0,187] | -0,002 |
| oficial (train desde 2015), k = 2: AP de test, Logística, ingreso + agregados | 0,545 [0,500; 0,592] | 0,537 [0,492; 0,585] | -0,008 |
| oficial (train desde 2015), k = 2: AP de test, CatBoost, ingreso + agregados | 0,549 [0,503; 0,594] | 0,552 [0,506; 0,596] | +0,002 |
| oficial (train desde 2015), k = 2: AP de test, GRU, ingreso + secuencia | 0,539 [0,489; 0,586] | 0,526 [0,478; 0,575] | -0,013 |
| oficial (train desde 2015), k = 2: ROC-AUC de test, CatBoost, ingreso + agregados | 0,890 [0,874; 0,905] | 0,890 [0,874; 0,906] | +0,000 |
| oficial (train desde 2015), k = 2: GRU − CatBoost, ΔAP pareado | -0,011 [-0,029; 0,009] | -0,026 [-0,042; -0,007] | -0,015 |
| sensibilidad (todas las cohortes), k = 1: AP de test, Tasa histórica (programa, k) | 0,073 [0,062; 0,089] | 0,073 [0,062; 0,089] | +0,000 |
| sensibilidad (todas las cohortes), k = 1: AP de test, CatBoost, solo ingreso | 0,100 [0,083; 0,124] | 0,103 [0,086; 0,130] | +0,003 |
| sensibilidad (todas las cohortes), k = 1: AP de test, Logística, ingreso + agregados | 0,307 [0,253; 0,363] | 0,312 [0,260; 0,367] | +0,004 |
| sensibilidad (todas las cohortes), k = 1: AP de test, CatBoost, ingreso + agregados | 0,322 [0,267; 0,379] | 0,329 [0,272; 0,384] | +0,007 |
| sensibilidad (todas las cohortes), k = 1: AP de test, GRU, ingreso + secuencia | 0,318 [0,263; 0,369] | 0,306 [0,251; 0,362] | -0,011 |
| sensibilidad (todas las cohortes), k = 1: ROC-AUC de test, CatBoost, ingreso + agregados | 0,850 [0,825; 0,873] | 0,852 [0,826; 0,874] | +0,001 |
| sensibilidad (todas las cohortes), k = 1: GRU − CatBoost, ΔAP pareado | -0,005 [-0,027; 0,016] | -0,023 [-0,050; 0,006] | -0,018 |
| sensibilidad (todas las cohortes), k = 2: AP de test, Tasa histórica (programa, k) | 0,122 [0,109; 0,136] | 0,122 [0,109; 0,136] | +0,000 |
| sensibilidad (todas las cohortes), k = 2: AP de test, CatBoost, solo ingreso | 0,166 [0,147; 0,192] | 0,167 [0,147; 0,192] | +0,001 |
| sensibilidad (todas las cohortes), k = 2: AP de test, Logística, ingreso + agregados | 0,546 [0,500; 0,592] | 0,540 [0,494; 0,588] | -0,006 |
| sensibilidad (todas las cohortes), k = 2: AP de test, CatBoost, ingreso + agregados | 0,552 [0,507; 0,596] | 0,552 [0,507; 0,598] | -0,000 |
| sensibilidad (todas las cohortes), k = 2: AP de test, GRU, ingreso + secuencia | 0,538 [0,489; 0,586] | 0,534 [0,485; 0,583] | -0,005 |
| sensibilidad (todas las cohortes), k = 2: ROC-AUC de test, CatBoost, ingreso + agregados | 0,890 [0,874; 0,905] | 0,889 [0,873; 0,906] | -0,001 |
| sensibilidad (todas las cohortes), k = 2: GRU − CatBoost, ΔAP pareado | -0,014 [-0,032; 0,005] | -0,018 [-0,038; 0,003] | -0,004 |
| Pregunta | Respuesta de la DAI | Consecuencia en este informe |
|---|---|---|
| P49 | Los segundos semestres anteriores a 2015 probablemente nunca se registraron; no pueden usarse. | La regla de cobertura (corte u horizonte en un período `20` anterior a `201520` ⇒ sin cobertura, fuera de modelos) deja de ser provisional (§1, §2). |
| P50 | La forma de registrar las salidas debió de cambiar hacia 2014; la DAI buscará registros anteriores, por ahora se usan los datos tal como están. | **Configuración oficial: entrenar con las cohortes 2015–2019** (valid 2020–2021, test 2022–2023). La corrida con todas las cohortes ≤ 2019 se conserva como sensibilidad (§9). Las filas anteriores a 2015 siguen en el snapshot con su estado, para auditoría. |
| P51 | «No continuidad» = el estudiante ya no se encuentra matriculado. | **Verificado contra la implementación, sin cambios:** `continua` = estado de matrícula, reintegro o cambio de ciclo en el período del horizonte en cualquier programa de la UCN; egreso o titulación hasta el horizonte cuenta como término de ciclo, no como no continuidad. Ninguna etiqueta cambia (§1). |
| P52 | Se pueden excluir las filas que ya tienen un estado de salida en el período del corte. | La exclusión (1.982 filas en `k = 1`, 990 en `k = 2`) queda confirmada (§2). |



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

| Modelo | AP | ROC-AUC | Brier | ECE | Recall@10% | Precision@10% |
|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.071 [0.061; 0.086] | 0.574 [0.543; 0.610] | 0.0535 [0.0478; 0.0597] | 0.012 [0.008; 0.019] | 0.164 [0.122; 0.202] | 0.093 [0.067; 0.119] |
| Logística, solo ingreso | 0.102 [0.085; 0.127] | 0.657 [0.627; 0.691] | 0.0530 [0.0476; 0.0588] | 0.018 [0.013; 0.025] | 0.179 [0.138; 0.225] | 0.101 [0.075; 0.130] |
| Logística, ingreso + agregados | 0.307 [0.251; 0.360] | 0.844 [0.818; 0.867] | 0.0466 [0.0422; 0.0515] | 0.015 [0.011; 0.022] | 0.464 [0.407; 0.520] | 0.263 [0.221; 0.302] |
| CatBoost, solo ingreso | 0.104 [0.085; 0.133] | 0.649 [0.618; 0.681] | 0.0526 [0.0470; 0.0587] | 0.015 [0.011; 0.023] | 0.246 [0.198; 0.295] | 0.140 [0.109; 0.172] |
| CatBoost, ingreso + agregados | 0.360 [0.303; 0.416] | 0.857 [0.832; 0.879] | 0.0441 [0.0394; 0.0489] | 0.007 [0.005; 0.015] | 0.561 [0.502; 0.615] | 0.318 [0.273; 0.358] |
| GRU, ingreso + secuencia | 0.330 [0.271; 0.384] | 0.851 [0.825; 0.873] | 0.0459 [0.0411; 0.0511] | 0.018 [0.014; 0.025] | 0.550 [0.495; 0.609] | 0.312 [0.269; 0.352] |

**Diferencias pareadas en test** (mismos remuestreos para todos los modelos)

| Comparación (diferencia pareada) | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, solo ingreso − Tasa histórica (programa, k) | 0.031 [0.014; 0.055] | 0.083 [0.037; 0.127] | -0.0006 [-0.0012; 0.0001] |
| Logística, ingreso + agregados − Tasa histórica (programa, k) | 0.235 [0.182; 0.286] | 0.270 [0.230; 0.307] | -0.0070 [-0.0097; -0.0040] |
| CatBoost, solo ingreso − Tasa histórica (programa, k) | 0.033 [0.014; 0.058] | 0.074 [0.033; 0.115] | -0.0009 [-0.0013; -0.0004] |
| CatBoost, ingreso + agregados − Tasa histórica (programa, k) | 0.289 [0.236; 0.341] | 0.283 [0.243; 0.321] | -0.0094 [-0.0120; -0.0067] |
| GRU, ingreso + secuencia − Tasa histórica (programa, k) | 0.258 [0.205; 0.311] | 0.277 [0.237; 0.314] | -0.0076 [-0.0094; -0.0057] |
| GRU, ingreso + secuencia − CatBoost, ingreso + agregados | -0.030 [-0.052; -0.009] | -0.006 [-0.019; 0.006] | 0.0018 [0.0007; 0.0029] |

**Valid**

| Modelo | AP | ROC-AUC | Brier | ECE | Recall@10% | Precision@10% |
|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.053 [0.044; 0.066] | 0.548 [0.510; 0.587] | 0.0453 [0.0396; 0.0511] | 0.023 [0.018; 0.030] | 0.127 [0.080; 0.168] | 0.060 [0.036; 0.079] |
| Logística, solo ingreso | 0.089 [0.068; 0.118] | 0.655 [0.617; 0.692] | 0.0445 [0.0389; 0.0500] | 0.021 [0.015; 0.028] | 0.203 [0.151; 0.258] | 0.095 [0.069; 0.124] |
| Logística, ingreso + agregados | 0.299 [0.238; 0.370] | 0.831 [0.796; 0.865] | 0.0391 [0.0337; 0.0446] | 0.019 [0.013; 0.025] | 0.569 [0.503; 0.636] | 0.267 [0.221; 0.314] |
| CatBoost, solo ingreso | 0.081 [0.066; 0.102] | 0.666 [0.626; 0.702] | 0.0443 [0.0387; 0.0501] | 0.017 [0.011; 0.023] | 0.198 [0.139; 0.254] | 0.093 [0.062; 0.119] |
| CatBoost, ingreso + agregados | 0.318 [0.257; 0.384] | 0.856 [0.822; 0.885] | 0.0381 [0.0330; 0.0433] | 0.016 [0.012; 0.023] | 0.579 [0.509; 0.640] | 0.271 [0.221; 0.321] |
| GRU, ingreso + secuencia | 0.320 [0.258; 0.393] | 0.841 [0.807; 0.872] | 0.0391 [0.0338; 0.0445] | 0.023 [0.018; 0.029] | 0.579 [0.508; 0.639] | 0.271 [0.226; 0.317] |

**Variabilidad entre semillas (test)**

| Modelo (3 semillas) | AP | ROC-AUC | Brier | Recall@10% |
|---|---|---|---|---|
| CatBoost, solo ingreso | 0.104 ± 0.004 | 0.647 ± 0.004 | 0.0527 ± 0.0001 | 0.232 ± 0.009 |
| CatBoost, ingreso + agregados | 0.357 ± 0.001 | 0.855 ± 0.003 | 0.0443 ± 0.0000 | 0.550 ± 0.021 |
| GRU, ingreso + secuencia | 0.319 ± 0.005 | 0.847 ± 0.002 | 0.0464 ± 0.0007 | 0.546 ± 0.025 |

### 5.2 k = 2 (corte: segundo semestre regular; horizonte: cuarto período regular)

Tamaños — train (cohortes 2015–2019): n = 11.247, eventos = 1.480 (13,2 %); valid: n = 4.061, eventos = 464 (11,4 %); test: n = 4.719, eventos = 499 (10,6 %).

**Test**

| Modelo | AP | ROC-AUC | Brier | ECE | Recall@10% | Precision@10% |
|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.122 [0.109; 0.136] | 0.565 [0.539; 0.589] | 0.0951 [0.0887; 0.1012] | 0.026 [0.022; 0.036] | 0.104 [0.083; 0.134] | 0.110 [0.087; 0.144] |
| Logística, solo ingreso | 0.175 [0.154; 0.203] | 0.637 [0.611; 0.662] | 0.0948 [0.0883; 0.1006] | 0.033 [0.028; 0.043] | 0.210 [0.176; 0.243] | 0.222 [0.184; 0.258] |
| Logística, ingreso + agregados | 0.537 [0.492; 0.585] | 0.893 [0.877; 0.907] | 0.0717 [0.0667; 0.0766] | 0.057 [0.050; 0.064] | 0.525 [0.490; 0.566] | 0.555 [0.506; 0.602] |
| CatBoost, solo ingreso | 0.163 [0.143; 0.187] | 0.630 [0.605; 0.654] | 0.0928 [0.0860; 0.0987] | 0.017 [0.013; 0.027] | 0.172 [0.146; 0.205] | 0.182 [0.152; 0.216] |
| CatBoost, ingreso + agregados | 0.552 [0.506; 0.596] | 0.890 [0.874; 0.906] | 0.0637 [0.0590; 0.0684] | 0.018 [0.013; 0.025] | 0.551 [0.513; 0.593] | 0.583 [0.540; 0.627] |
| GRU, ingreso + secuencia | 0.526 [0.478; 0.575] | 0.887 [0.870; 0.904] | 0.0669 [0.0621; 0.0716] | 0.033 [0.027; 0.040] | 0.543 [0.502; 0.585] | 0.574 [0.527; 0.617] |

**Diferencias pareadas en test**

| Comparación (diferencia pareada) | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, solo ingreso − Tasa histórica (programa, k) | 0.053 [0.034; 0.076] | 0.072 [0.046; 0.100] | -0.0004 [-0.0022; 0.0014] |
| Logística, ingreso + agregados − Tasa histórica (programa, k) | 0.415 [0.370; 0.461] | 0.328 [0.303; 0.357] | -0.0235 [-0.0291; -0.0173] |
| CatBoost, solo ingreso − Tasa histórica (programa, k) | 0.041 [0.024; 0.062] | 0.065 [0.040; 0.092] | -0.0024 [-0.0034; -0.0014] |
| CatBoost, ingreso + agregados − Tasa histórica (programa, k) | 0.430 [0.386; 0.474] | 0.326 [0.300; 0.356] | -0.0315 [-0.0358; -0.0267] |
| GRU, ingreso + secuencia − Tasa histórica (programa, k) | 0.404 [0.358; 0.451] | 0.323 [0.296; 0.353] | -0.0283 [-0.0335; -0.0226] |
| GRU, ingreso + secuencia − CatBoost, ingreso + agregados | -0.026 [-0.042; -0.007] | -0.003 [-0.010; 0.004] | 0.0032 [0.0017; 0.0048] |

**Valid**

| Modelo | AP | ROC-AUC | Brier | ECE | Recall@10% | Precision@10% |
|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.136 [0.121; 0.156] | 0.564 [0.537; 0.591] | 0.1014 [0.0940; 0.1081] | 0.025 [0.020; 0.037] | 0.125 [0.092; 0.151] | 0.143 [0.106; 0.174] |
| Logística, solo ingreso | 0.181 [0.159; 0.208] | 0.642 [0.614; 0.666] | 0.1005 [0.0937; 0.1070] | 0.027 [0.023; 0.039] | 0.190 [0.158; 0.224] | 0.216 [0.177; 0.260] |
| Logística, ingreso + agregados | 0.501 [0.450; 0.552] | 0.857 [0.836; 0.876] | 0.0742 [0.0682; 0.0807] | 0.019 [0.015; 0.030] | 0.491 [0.449; 0.531] | 0.560 [0.506; 0.607] |
| CatBoost, solo ingreso | 0.185 [0.161; 0.218] | 0.625 [0.599; 0.651] | 0.0990 [0.0919; 0.1060] | 0.019 [0.014; 0.031] | 0.179 [0.150; 0.214] | 0.204 [0.167; 0.246] |
| CatBoost, ingreso + agregados | 0.495 [0.447; 0.546] | 0.836 [0.813; 0.858] | 0.0748 [0.0689; 0.0810] | 0.025 [0.018; 0.034] | 0.494 [0.453; 0.532] | 0.563 [0.509; 0.609] |
| GRU, ingreso + secuencia | 0.510 [0.460; 0.558] | 0.856 [0.835; 0.875] | 0.0733 [0.0673; 0.0797] | 0.021 [0.015; 0.030] | 0.496 [0.455; 0.539] | 0.565 [0.511; 0.612] |

**Variabilidad entre semillas (test)**

| Modelo (3 semillas) | AP | ROC-AUC | Brier | Recall@10% |
|---|---|---|---|---|
| CatBoost, solo ingreso | 0.162 ± 0.002 | 0.628 ± 0.002 | 0.0929 ± 0.0001 | 0.177 ± 0.013 |
| CatBoost, ingreso + agregados | 0.549 ± 0.004 | 0.889 ± 0.002 | 0.0639 ± 0.0001 | 0.556 ± 0.009 |
| GRU, ingreso + secuencia | 0.522 ± 0.009 | 0.886 ± 0.003 | 0.0676 ± 0.0026 | 0.538 ± 0.015 |

### 5.3 Los tres modelos «ingreso + agregados/secuencia» entre sí

Diferencias pareadas (bootstrap de 1.000 remuestreos sobre las mismas filas), configuración oficial. `tools/pares_t1.py`.

**k = 1**

*test*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | +0.054 [+0.030; +0.075] | +0.013 [+0.001; +0.027] | -0.0025 [-0.0034; -0.0014] | -0.008 [-0.014; +0.002] |
| GRU − Logística | +0.023 [+0.007; +0.039] | +0.007 [-0.000; +0.013] | -0.0006 [-0.0018; +0.0006] | +0.003 [-0.006; +0.012] |
| GRU − CatBoost | -0.030 [-0.051; -0.008] | -0.006 [-0.020; +0.006] | +0.0018 [+0.0007; +0.0028] | +0.011 [+0.006; +0.013] |

*valid*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | +0.020 [-0.009; +0.048] | +0.025 [+0.001; +0.052] | -0.0010 [-0.0018; -0.0002] | -0.002 [-0.005; +0.001] |
| GRU − Logística | +0.022 [-0.001; +0.046] | +0.010 [-0.004; +0.027] | +0.0001 [-0.0006; +0.0008] | +0.004 [+0.002; +0.006] |
| GRU − CatBoost | +0.002 [-0.025; +0.032] | -0.015 [-0.037; +0.005] | +0.0011 [+0.0002; +0.0020] | +0.007 [+0.003; +0.010] |


**k = 2**

*test*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | +0.014 [-0.009; +0.036] | -0.003 [-0.008; +0.003] | -0.0080 [-0.0104; -0.0055] | -0.039 [-0.046; -0.027] |
| GRU − Logística | -0.011 [-0.029; +0.009] | -0.005 [-0.012; -0.000] | -0.0048 [-0.0061; -0.0034] | -0.024 [-0.027; -0.020] |
| GRU − CatBoost | -0.026 [-0.042; -0.007] | -0.003 [-0.010; +0.004] | +0.0032 [+0.0016; +0.0049] | +0.016 [+0.004; +0.023] |

*valid*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | -0.005 [-0.028; +0.018] | -0.021 [-0.031; -0.011] | +0.0006 [-0.0009; +0.0021] | +0.005 [-0.004; +0.010] |
| GRU − Logística | +0.009 [-0.005; +0.023] | -0.001 [-0.006; +0.003] | -0.0009 [-0.0018; +0.0001] | +0.001 [-0.005; +0.005] |
| GRU − CatBoost | +0.015 [-0.004; +0.032] | +0.020 [+0.011; +0.031] | -0.0015 [-0.0029; -0.0001] | -0.004 [-0.012; +0.006] |

**Lectura.** En test, en ningún `k` la GRU supera a CatBoost en AP, y ahora CatBoost la supera con el intervalo pareado bajo cero (−0,030 [−0,051; −0,008] en `k = 1`; −0,026 [−0,042; −0,007] en `k = 2`; en la versión 0.2 los intervalos incluían el cero). En `k = 1` CatBoost supera a la logística en test (+0,054 [+0,030; +0,075]) y la GRU también (+0,023 [+0,007; +0,039]); en `k = 2` los tres modelos no se distinguen en AP (CatBoost − logística +0,014 [−0,009; +0,036]; GRU − logística −0,011 [−0,029; +0,009]). **Valid de `k = 2`:** la GRU ya no supera a CatBoost en AP (+0,015 [−0,004; +0,032]; ΔROC-AUC +0,020 [+0,011; +0,031]) ni a la logística (+0,009 [−0,005; +0,023]); la excepción que mostraba la versión 0.2 desaparece. Valid es el período de pandemia y se usa para detener el entrenamiento, de modo que su ranking de modelos no se toma como evidencia; test es la comparación válida. Con 280 y 499 eventos en test los intervalos son anchos: las diferencias de unas pocas centésimas no se pueden separar.

## 6. Ablación (mismo horizonte y población en cada escalón)

Test, configuración oficial. El perfil de ingreso solo mejora poco a la tasa histórica por programa (AP 0,104 y 0,175 frente a 0,071 y 0,122); casi toda la ganancia aparece al agregar el desempeño académico hasta el corte; la secuencia por semestre no agrega a los agregados.

**k = 1**

| Escalón | Logística AP | CatBoost AP | GRU AP | Logística ROC-AUC | CatBoost ROC-AUC | GRU ROC-AUC |
|---|---|---|---|---|---|---|
| 1. Solo perfil de ingreso | 0.102 [0.085; 0.127] | 0.104 [0.085; 0.133] | — | 0.657 [0.627; 0.691] | 0.649 [0.618; 0.681] | — |
| 2. + agregados académicos al corte | 0.307 [0.251; 0.360] | 0.360 [0.303; 0.416] | — | 0.844 [0.818; 0.867] | 0.857 [0.832; 0.879] | — |
| 3. + secuencia por semestre (GRU) | — | — | 0.330 [0.271; 0.384] | — | — | 0.851 [0.825; 0.873] |

**k = 2**

| Escalón | Logística AP | CatBoost AP | GRU AP | Logística ROC-AUC | CatBoost ROC-AUC | GRU ROC-AUC |
|---|---|---|---|---|---|---|
| 1. Solo perfil de ingreso | 0.175 [0.154; 0.203] | 0.163 [0.143; 0.187] | — | 0.637 [0.611; 0.662] | 0.630 [0.605; 0.654] | — |
| 2. + agregados académicos al corte | 0.537 [0.492; 0.585] | 0.552 [0.506; 0.596] | — | 0.893 [0.877; 0.907] | 0.890 [0.874; 0.906] | — |
| 3. + secuencia por semestre (GRU) | — | — | 0.526 [0.478; 0.575] | — | — | 0.887 [0.870; 0.904] |

La tasa histórica (programa, `k`) es el escalón cero: AP 0,071 [0,061; 0,086] en `k = 1` y 0,122 [0,109; 0,136] en `k = 2`.

**Dónde está la señal.** El resumen académico identifica sobre todo a quienes **no tuvieron ningún ramo evaluado en el semestre `k`** (sin notas: ausentes de hecho pese a figurar vigentes). En test (CatBoost, `tools/subpoblacion_t1.py`):

| k | Subpoblación (test) | n | Eventos | Tasa | AP CatBoost | AP Logística | AP GRU |
|---|---|---|---|---|---|---|---|
| 1 | sin intentos evaluados en el semestre k | 226 | 76 | 0.336 | 0.384 | 0.294 | 0.318 |
| 1 | con al menos un intento evaluado en el semestre k | 4708 | 204 | 0.043 | 0.329 | 0.308 | 0.309 |
| 2 | sin intentos evaluados en el semestre k | 388 | 235 | 0.606 | 0.749 | 0.714 | 0.711 |
| 2 | con al menos un intento evaluado en el semestre k | 4331 | 264 | 0.061 | 0.333 | 0.334 | 0.339 |

Entre quienes sí tuvieron ramos evaluados el modelo sigue ordenando (AP 0,32 sobre una tasa de 4,3 % en `k = 1`; 0,34 sobre 6,1 % en `k = 2`), pero con una señal bastante más modesta que el agregado.

## 7. Calibración

Tabla de confiabilidad por deciles de riesgo en test (predicho medio / tasa observada, n por decil). ECE: 10 grupos de igual tamaño.

**k = 1**

| Decil de riesgo | Tasa histórica (programa, k): predicho / observado | Logística, ingreso + agregados: predicho / observado | CatBoost, ingreso + agregados: predicho / observado | GRU, ingreso + secuencia: predicho / observado |
|---|---|---|---|---|
| 1 | 0.020 / 0.027 (n=486) | 0.005 / 0.008 (n=494) | 0.008 / 0.002 (n=494) | 0.003 / 0.004 (n=494) |
| 2 | 0.035 / 0.040 (n=528) | 0.010 / 0.008 (n=493) | 0.010 / 0.010 (n=493) | 0.005 / 0.012 (n=493) |
| 3 | 0.042 / 0.049 (n=487) | 0.012 / 0.006 (n=494) | 0.012 / 0.010 (n=494) | 0.007 / 0.008 (n=494) |
| 4 | 0.046 / 0.058 (n=429) | 0.016 / 0.012 (n=493) | 0.013 / 0.010 (n=493) | 0.009 / 0.010 (n=493) |
| 5 | 0.051 / 0.063 (n=380) | 0.021 / 0.020 (n=493) | 0.015 / 0.012 (n=493) | 0.011 / 0.016 (n=493) |
| 6 | 0.063 / 0.058 (n=653) | 0.029 / 0.008 (n=494) | 0.018 / 0.024 (n=494) | 0.015 / 0.016 (n=494) |
| 7 | 0.071 / 0.061 (n=446) | 0.044 / 0.032 (n=493) | 0.027 / 0.026 (n=493) | 0.022 / 0.037 (n=493) |
| 8 | 0.079 / 0.052 (n=572) | 0.070 / 0.065 (n=494) | 0.043 / 0.055 (n=494) | 0.034 / 0.045 (n=494) |
| 9 | 0.087 / 0.071 (n=453) | 0.119 / 0.146 (n=493) | 0.079 / 0.099 (n=493) | 0.064 / 0.108 (n=493) |
| 10 | 0.108 / 0.092 (n=500) | 0.336 / 0.262 (n=493) | 0.297 / 0.318 (n=493) | 0.213 / 0.312 (n=493) |

**k = 2**

| Decil de riesgo | Tasa histórica (programa, k): predicho / observado | Logística, ingreso + agregados: predicho / observado | CatBoost, ingreso + agregados: predicho / observado | GRU, ingreso + secuencia: predicho / observado |
|---|---|---|---|---|
| 1 | 0.054 / 0.049 (n=429) | 0.010 / 0.002 (n=472) | 0.023 / 0.002 (n=472) | 0.007 / 0.015 (n=472) |
| 2 | 0.078 / 0.076 (n=551) | 0.015 / 0.006 (n=472) | 0.026 / 0.021 (n=472) | 0.012 / 0.004 (n=472) |
| 3 | 0.090 / 0.097 (n=382) | 0.020 / 0.008 (n=472) | 0.027 / 0.013 (n=472) | 0.015 / 0.023 (n=472) |
| 4 | 0.099 / 0.118 (n=501) | 0.027 / 0.030 (n=472) | 0.029 / 0.015 (n=472) | 0.019 / 0.017 (n=472) |
| 5 | 0.110 / 0.084 (n=359) | 0.037 / 0.019 (n=472) | 0.030 / 0.021 (n=472) | 0.025 / 0.008 (n=472) |
| 6 | 0.126 / 0.104 (n=741) | 0.059 / 0.023 (n=472) | 0.033 / 0.019 (n=472) | 0.036 / 0.032 (n=472) |
| 7 | 0.149 / 0.133 (n=353) | 0.098 / 0.047 (n=472) | 0.042 / 0.042 (n=472) | 0.059 / 0.038 (n=472) |
| 8 | 0.169 / 0.167 (n=402) | 0.190 / 0.093 (n=472) | 0.086 / 0.108 (n=472) | 0.124 / 0.093 (n=472) |
| 9 | 0.185 / 0.130 (n=446) | 0.424 / 0.273 (n=472) | 0.296 / 0.233 (n=472) | 0.374 / 0.252 (n=472) |
| 10 | 0.199 / 0.110 (n=555) | 0.739 / 0.556 (n=471) | 0.571 / 0.584 (n=471) | 0.686 / 0.575 (n=471) |

La tasa histórica (programa, `k`) es la referencia sin discriminación. Con la configuración oficial los cuatro modelos de `k = 1` quedan con ECE de 0,015 a 0,018 (tasa histórica 0,012); los tres modelos con agregados subestiman algo el decil 9 (predicho 0,07–0,10 frente a 0,10–0,14 observado) y quedan cerca en el decil de mayor riesgo (predicho 0,25–0,29 frente a 0,27–0,32). En `k = 2` el ECE va de 0,018 (CatBoost) a 0,057 (logística y GRU); CatBoost sobreestima los cinco deciles de menor riesgo (predicho 0,03–0,04 frente a 0,004–0,017 observado), con un efecto pequeño en términos absolutos. Con todas las cohortes ≤ 2019 la calibración de la tasa histórica, la logística y la GRU en `k = 1` era peor (ECE 0,070, 0,033 y 0,032; §9): el train incluía cohortes con 16–29 % de no continuidad y test tiene 5,7 %.

## 8. Subgrupos y equidad (test; descriptivo)

Las tablas por subgrupo usan el modelo conservado (CatBoost, ingreso + agregados). Grupos con n < 100 (programa) o n < 30 se omiten; con 100–300 filas por programa y pocos eventos, las cifras por programa son ruidosas y solo describen. `sexo` no es una característica del modelo: se usa únicamente para estas tablas.

### 8.1 Por sexo

Tasa observada, AP y brechas F − M para cada modelo. Las brechas de calibración son riesgo medio − tasa observada, restadas entre grupos.

**k = 1**

| Modelo | Tasa F | Tasa M | AP F | AP M | ΔAP (F−M) | Recall@10% F−M | Brecha calibración F−M | ECE F−M |
|---|---|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.059 | 0.055 | 0.067 | 0.076 | -0.010 | -0.015 | -0.002 | +0.008 |
| Logística, solo ingreso | 0.059 | 0.055 | 0.115 | 0.095 | +0.020 | +0.053 | +0.007 | +0.005 |
| Logística, ingreso + agregados | 0.059 | 0.055 | 0.357 | 0.274 | +0.083 | +0.084 | -0.011 | -0.014 |
| CatBoost, solo ingreso | 0.059 | 0.055 | 0.119 | 0.097 | +0.022 | +0.038 | +0.002 | -0.003 |
| CatBoost, ingreso + agregados | 0.059 | 0.055 | 0.423 | 0.315 | +0.108 | +0.084 | -0.010 | +0.000 |
| GRU, ingreso + secuencia | 0.059 | 0.055 | 0.393 | 0.283 | +0.111 | +0.106 | -0.009 | +0.009 |

**k = 2**

| Modelo | Tasa F | Tasa M | AP F | AP M | ΔAP (F−M) | Recall@10% F−M | Brecha calibración F−M | ECE F−M |
|---|---|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.097 | 0.113 | 0.104 | 0.134 | -0.030 | -0.036 | +0.004 | +0.002 |
| Logística, solo ingreso | 0.097 | 0.113 | 0.153 | 0.197 | -0.044 | -0.021 | +0.016 | +0.019 |
| Logística, ingreso + agregados | 0.097 | 0.113 | 0.532 | 0.546 | -0.014 | +0.102 | -0.026 | -0.023 |
| CatBoost, solo ingreso | 0.097 | 0.113 | 0.150 | 0.181 | -0.031 | +0.009 | +0.020 | -0.003 |
| CatBoost, ingreso + agregados | 0.097 | 0.113 | 0.558 | 0.545 | +0.013 | +0.090 | -0.012 | -0.004 |
| GRU, ingreso + secuencia | 0.097 | 0.113 | 0.519 | 0.537 | -0.018 | +0.100 | -0.023 | -0.015 |

**Lectura.** Las tasas observadas de F y M son parecidas en `k = 1` (5,9 % y 5,5 %) y algo distintas en `k = 2` (9,7 % y 11,3 %). En `k = 1` el modelo ordena mejor a las mujeres (AP 0,423 frente a 0,315 con CatBoost en valid; Recall@10 % +0,084), con una diferencia de brechas de calibración F − M pequeña (−0,010); en `k = 2` el AP es equivalente (0,558 frente a 0,545), el Recall@10 % de las mujeres es 0,09 mayor y la diferencia de brechas de calibración F − M es −0,012. Son diferencias descriptivas, sin intervalos y sin análisis causal; que `sexo` no entre al modelo no impide que otras variables (programa, colegio) lo representen parcialmente.

### 8.2 Por cohorte

**k = 1**

| Grupo | n | Tasa observada | Riesgo medio | Brecha calibración | AP | ROC-AUC | Recall@10% | ECE |
|---|---|---|---|---|---|---|---|---|
| 2022 | 2223 | 0.056 | 0.054 | -0.002 | 0.339 | 0.845 | 0.524 | 0.010 |
| 2023 | 2711 | 0.058 | 0.051 | -0.007 | 0.391 | 0.868 | 0.577 | 0.012 |

**k = 2**

| Grupo | n | Tasa observada | Riesgo medio | Brecha calibración | AP | ROC-AUC | Recall@10% | ECE |
|---|---|---|---|---|---|---|---|---|
| 2022 | 2139 | 0.115 | 0.119 | +0.005 | 0.607 | 0.922 | 0.535 | 0.020 |
| 2023 | 2580 | 0.098 | 0.114 | +0.015 | 0.504 | 0.859 | 0.567 | 0.017 |

### 8.3 Por vía de ingreso

**k = 1**

| Grupo | n | Tasa observada | Riesgo medio | Brecha calibración | AP | ROC-AUC | Recall@10% | ECE |
|---|---|---|---|---|---|---|---|---|
| especial | 438 | 0.080 | 0.067 | -0.013 | 0.341 | 0.795 | 0.429 | 0.030 |
| otros_cambio | 372 | 0.019 | 0.043 | +0.024 | 0.070 | 0.809 | 0.571 | 0.032 |
| regular | 4123 | 0.058 | 0.052 | -0.006 | 0.385 | 0.867 | 0.584 | 0.010 |

**k = 2**

| Grupo | n | Tasa observada | Riesgo medio | Brecha calibración | AP | ROC-AUC | Recall@10% | ECE |
|---|---|---|---|---|---|---|---|---|
| especial | 414 | 0.150 | 0.153 | +0.003 | 0.621 | 0.884 | 0.468 | 0.026 |
| otros_cambio | 361 | 0.039 | 0.070 | +0.032 | 0.375 | 0.945 | 0.786 | 0.036 |
| regular | 3943 | 0.107 | 0.117 | +0.009 | 0.552 | 0.885 | 0.544 | 0.016 |

Las vías «otros_cambio» (cambio de carrera, traslado, etc.) tienen tasas de no continuidad muy bajas (1,9 % en `k = 1`), de modo que su AP es bajo aunque el ROC-AUC sea comparable.

### 8.4 Por programa (n ≥ 100 en test)

**k = 1**

| Grupo | n | Tasa observada | Riesgo medio | Brecha calibración | AP | ROC-AUC | Recall@10% | ECE |
|---|---|---|---|---|---|---|---|---|
| 8213 ARQUITECTURA | 173 | 0.116 | 0.067 | -0.048 | 0.465 | 0.857 | 0.350 | 0.055 |
| 8223 PEDAGOGÍA EN INGLÉS | 117 | 0.034 | 0.022 | -0.012 | 0.798 | 0.962 | 0.750 | 0.032 |
| 8233 INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 161 | 0.075 | 0.066 | -0.008 | 0.411 | 0.732 | 0.333 | 0.047 |
| 8266 INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 116 | 0.026 | 0.068 | +0.042 | 0.085 | 0.814 | 0.000 | 0.067 |
| 8323 INGENIERÍA COMERCIAL | 296 | 0.064 | 0.049 | -0.016 | 0.501 | 0.898 | 0.526 | 0.027 |
| 8326 INGENIERÍA COMERCIAL | 268 | 0.037 | 0.028 | -0.009 | 0.210 | 0.644 | 0.400 | 0.027 |
| 8373 DERECHO | 249 | 0.044 | 0.044 | +0.000 | 0.342 | 0.844 | 0.545 | 0.020 |
| 8376 DERECHO | 272 | 0.040 | 0.044 | +0.004 | 0.293 | 0.790 | 0.455 | 0.029 |
| 8383 PSICOLOGÍA | 147 | 0.020 | 0.020 | -0.001 | 0.358 | 0.907 | 0.667 | 0.013 |
| 8403 GEOLOGÍA | 130 | 0.077 | 0.070 | -0.007 | 0.475 | 0.897 | 0.500 | 0.048 |
| 8483 QUÍMICA Y FARMACIA | 131 | 0.092 | 0.069 | -0.022 | 0.584 | 0.919 | 0.583 | 0.044 |
| 8486 MEDICINA | 113 | 0.000 | 0.011 | +0.011 | — | — | — | 0.011 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 221 | 0.077 | 0.063 | -0.014 | 0.302 | 0.823 | 0.471 | 0.041 |
| 8606 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 212 | 0.075 | 0.074 | -0.002 | 0.362 | 0.803 | 0.500 | 0.042 |
| 8613 INGENIERÍA CIVIL INDUSTRIAL | 248 | 0.020 | 0.035 | +0.015 | 0.118 | 0.851 | 0.600 | 0.018 |
| 8616 INGENIERÍA CIVIL INDUSTRIAL | 266 | 0.026 | 0.041 | +0.015 | 0.210 | 0.890 | 0.571 | 0.018 |
| 8653 INGENIERÍA CIVIL DE MINAS | 156 | 0.064 | 0.054 | -0.010 | 0.489 | 0.847 | 0.500 | 0.031 |
| 8896 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 149 | 0.107 | 0.070 | -0.037 | 0.507 | 0.850 | 0.438 | 0.056 |

**k = 2**

| Grupo | n | Tasa observada | Riesgo medio | Brecha calibración | AP | ROC-AUC | Recall@10% | ECE |
|---|---|---|---|---|---|---|---|---|
| 8213 ARQUITECTURA | 156 | 0.103 | 0.121 | +0.019 | 0.614 | 0.848 | 0.625 | 0.045 |
| 8223 PEDAGOGÍA EN INGLÉS | 113 | 0.053 | 0.051 | -0.002 | 0.329 | 0.607 | 0.333 | 0.051 |
| 8233 INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 151 | 0.106 | 0.152 | +0.046 | 0.582 | 0.911 | 0.375 | 0.065 |
| 8266 INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 112 | 0.107 | 0.152 | +0.045 | 0.626 | 0.888 | 0.667 | 0.086 |
| 8323 INGENIERÍA COMERCIAL | 281 | 0.135 | 0.130 | -0.005 | 0.635 | 0.939 | 0.500 | 0.044 |
| 8326 INGENIERÍA COMERCIAL | 260 | 0.077 | 0.088 | +0.011 | 0.477 | 0.829 | 0.550 | 0.030 |
| 8373 DERECHO | 239 | 0.084 | 0.120 | +0.037 | 0.345 | 0.866 | 0.400 | 0.048 |
| 8376 DERECHO | 264 | 0.136 | 0.119 | -0.018 | 0.643 | 0.915 | 0.528 | 0.064 |
| 8383 PSICOLOGÍA | 144 | 0.028 | 0.051 | +0.023 | 0.646 | 0.991 | 1.000 | 0.026 |
| 8403 GEOLOGÍA | 124 | 0.137 | 0.140 | +0.003 | 0.551 | 0.870 | 0.412 | 0.045 |
| 8483 QUÍMICA Y FARMACIA | 122 | 0.139 | 0.107 | -0.032 | 0.749 | 0.947 | 0.588 | 0.065 |
| 8486 MEDICINA | 113 | 0.027 | 0.034 | +0.008 | 1.000 | 1.000 | 1.000 | 0.036 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 202 | 0.149 | 0.172 | +0.023 | 0.367 | 0.787 | 0.267 | 0.072 |
| 8606 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 201 | 0.129 | 0.125 | -0.004 | 0.675 | 0.924 | 0.538 | 0.039 |
| 8613 INGENIERÍA CIVIL INDUSTRIAL | 246 | 0.085 | 0.114 | +0.028 | 0.639 | 0.925 | 0.714 | 0.040 |
| 8616 INGENIERÍA CIVIL INDUSTRIAL | 260 | 0.050 | 0.073 | +0.023 | 0.569 | 0.904 | 0.769 | 0.027 |
| 8653 INGENIERÍA CIVIL DE MINAS | 153 | 0.176 | 0.171 | -0.006 | 0.584 | 0.822 | 0.407 | 0.079 |
| 8896 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 140 | 0.179 | 0.155 | -0.024 | 0.798 | 0.933 | 0.440 | 0.070 |

## 9. Sensibilidad: entrenar con todas las cohortes ≤ 2019 (sin la ventana de la DAI)

Antes de las respuestas P49/P50 la partición principal entrenaba con todas las cohortes ≤ 2019. Esa configuración se conserva como sensibilidad (`--todos-los-anios`), con el mismo valid y test. En `k = 2` casi no cambia (el train gana 706 filas); en `k = 1` el train pasa de 12.012 filas (754 eventos, 6,3 %) a 26.049 (3.760 eventos, 14,4 %), porque las cohortes 2008–2013 tienen 16–29 % de no continuidad con mucha ausencia de estados (§2).

**k = 1 (test)**

| Modelo | AP | ROC-AUC | Brier | ECE | Recall@10% | Precision@10% |
|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.073 [0.062; 0.089] | 0.565 [0.530; 0.602] | 0.0599 [0.0551; 0.0650] | 0.070 [0.063; 0.077] | 0.146 [0.105; 0.188] | 0.083 [0.059; 0.107] |
| Logística, solo ingreso | 0.103 [0.086; 0.130] | 0.662 [0.634; 0.693] | 0.0535 [0.0474; 0.0600] | 0.027 [0.021; 0.034] | 0.211 [0.171; 0.259] | 0.119 [0.093; 0.150] |
| Logística, ingreso + agregados | 0.312 [0.260; 0.367] | 0.849 [0.822; 0.873] | 0.0492 [0.0437; 0.0552] | 0.036 [0.030; 0.043] | 0.543 [0.489; 0.603] | 0.308 [0.265; 0.350] |
| CatBoost, solo ingreso | 0.103 [0.086; 0.130] | 0.660 [0.629; 0.692] | 0.0526 [0.0471; 0.0585] | 0.010 [0.009; 0.018] | 0.225 [0.174; 0.273] | 0.128 [0.097; 0.158] |
| CatBoost, ingreso + agregados | 0.329 [0.272; 0.384] | 0.852 [0.826; 0.874] | 0.0453 [0.0406; 0.0503] | 0.011 [0.008; 0.018] | 0.554 [0.491; 0.609] | 0.314 [0.269; 0.354] |
| GRU, ingreso + secuencia | 0.306 [0.251; 0.362] | 0.844 [0.817; 0.868] | 0.0465 [0.0417; 0.0517] | 0.017 [0.014; 0.024] | 0.521 [0.470; 0.579] | 0.296 [0.255; 0.340] |

| Comparación (diferencia pareada) | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, solo ingreso − Tasa histórica (programa, k) | 0.030 [0.013; 0.053] | 0.096 [0.053; 0.134] | -0.0064 [-0.0079; -0.0049] |
| Logística, ingreso + agregados − Tasa histórica (programa, k) | 0.238 [0.188; 0.291] | 0.284 [0.240; 0.325] | -0.0107 [-0.0123; -0.0090] |
| CatBoost, solo ingreso − Tasa histórica (programa, k) | 0.030 [0.013; 0.056] | 0.094 [0.050; 0.135] | -0.0073 [-0.0084; -0.0061] |
| CatBoost, ingreso + agregados − Tasa histórica (programa, k) | 0.256 [0.201; 0.308] | 0.286 [0.243; 0.328] | -0.0146 [-0.0167; -0.0122] |
| GRU, ingreso + secuencia − Tasa histórica (programa, k) | 0.233 [0.181; 0.288] | 0.279 [0.236; 0.320] | -0.0133 [-0.0148; -0.0119] |
| GRU, ingreso + secuencia − CatBoost, ingreso + agregados | -0.023 [-0.050; 0.006] | -0.007 [-0.021; 0.004] | 0.0013 [-0.0001; 0.0025] |

**k = 2 (test)**

| Modelo | AP | ROC-AUC | Brier | ECE | Recall@10% | Precision@10% |
|---|---|---|---|---|---|---|
| Tasa histórica (programa, k) | 0.122 [0.109; 0.136] | 0.565 [0.541; 0.589] | 0.0950 [0.0885; 0.1011] | 0.028 [0.024; 0.038] | 0.104 [0.083; 0.134] | 0.110 [0.087; 0.144] |
| Logística, solo ingreso | 0.176 [0.155; 0.205] | 0.638 [0.612; 0.663] | 0.0962 [0.0899; 0.1018] | 0.040 [0.035; 0.050] | 0.214 [0.180; 0.248] | 0.227 [0.186; 0.261] |
| Logística, ingreso + agregados | 0.540 [0.494; 0.588] | 0.893 [0.877; 0.908] | 0.0658 [0.0611; 0.0705] | 0.028 [0.021; 0.035] | 0.533 [0.494; 0.571] | 0.564 [0.511; 0.606] |
| CatBoost, solo ingreso | 0.167 [0.147; 0.192] | 0.630 [0.606; 0.655] | 0.0926 [0.0858; 0.0985] | 0.015 [0.011; 0.025] | 0.188 [0.158; 0.222] | 0.199 [0.165; 0.235] |
| CatBoost, ingreso + agregados | 0.552 [0.507; 0.598] | 0.889 [0.873; 0.906] | 0.0640 [0.0594; 0.0686] | 0.018 [0.013; 0.025] | 0.541 [0.501; 0.582] | 0.572 [0.525; 0.614] |
| GRU, ingreso + secuencia | 0.534 [0.485; 0.583] | 0.888 [0.871; 0.904] | 0.0655 [0.0608; 0.0703] | 0.024 [0.019; 0.033] | 0.535 [0.496; 0.575] | 0.566 [0.519; 0.606] |

Diferencias pareadas entre los tres modelos con train de todas las cohortes ≤ 2019:

**k = 1**

*test*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | +0.017 [-0.002; +0.032] | +0.002 [-0.009; +0.013] | -0.0039 [-0.0055; -0.0024] | -0.025 [-0.028; -0.019] |
| GRU − Logística | -0.006 [-0.037; +0.022] | -0.005 [-0.016; +0.006] | -0.0027 [-0.0036; -0.0017] | -0.019 [-0.022; -0.012] |
| GRU − CatBoost | -0.023 [-0.050; +0.003] | -0.007 [-0.020; +0.005] | +0.0013 [-0.0000; +0.0026] | +0.006 [+0.002; +0.010] |

*valid*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | -0.001 [-0.029; +0.025] | +0.037 [+0.014; +0.061] | -0.0022 [-0.0032; -0.0012] | -0.010 [-0.012; -0.007] |
| GRU − Logística | +0.010 [-0.028; +0.044] | +0.012 [-0.004; +0.028] | -0.0022 [-0.0030; -0.0013] | -0.010 [-0.013; -0.004] |
| GRU − CatBoost | +0.011 [-0.026; +0.050] | -0.025 [-0.048; -0.004] | +0.0000 [-0.0010; +0.0011] | +0.001 [-0.003; +0.005] |

**k = 2**

*test*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | +0.012 [-0.013; +0.034] | -0.004 [-0.010; +0.002] | -0.0018 [-0.0035; -0.0000] | -0.010 [-0.019; +0.002] |
| GRU − Logística | -0.007 [-0.024; +0.014] | -0.005 [-0.011; -0.000] | -0.0003 [-0.0013; +0.0008] | -0.003 [-0.006; +0.002] |
| GRU − CatBoost | -0.018 [-0.037; +0.003] | -0.001 [-0.009; +0.006] | +0.0015 [-0.0002; +0.0031] | +0.007 [-0.004; +0.017] |

*valid*

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier | ΔECE |
|---|---|---|---|---|
| CatBoost − Logística | -0.013 [-0.034; +0.010] | -0.019 [-0.029; -0.009] | +0.0006 [-0.0008; +0.0018] | -0.005 [-0.007; +0.002] |
| GRU − Logística | +0.009 [-0.006; +0.025] | +0.001 [-0.004; +0.006] | -0.0016 [-0.0026; -0.0005] | -0.010 [-0.011; -0.001] |
| GRU − CatBoost | +0.021 [+0.002; +0.038] | +0.020 [+0.011; +0.030] | -0.0022 [-0.0036; -0.0007] | -0.005 [-0.011; +0.003] |

**Lectura.** (i) La calibración en `k = 1` es peor con todas las cohortes (ECE tasa histórica 0,070, logística 0,036, GRU 0,017; con la ventana oficial 0,012, 0,015 y 0,018); en `k = 2` la diferencia es pequeña y mixta (logística 0,028 con todas frente a 0,057 con la ventana oficial; CatBoost 0,018 frente a 0,018). (ii) El AP de los modelos con agregados cambia poco: `k = 1`, logística 0,312 → 0,307, CatBoost 0,329 → 0,360, GRU 0,306 → 0,330; `k = 2`, 0,540 → 0,537, 0,552 → 0,552 y 0,534 → 0,526 (todas las cohortes → ventana oficial). (iii) El orden de los modelos es más claro con la ventana oficial en `k = 1` (CatBoost − logística +0,054 [+0,030; +0,075] frente a +0,017 [−0,002; +0,032] con todas las cohortes), y la GRU no supera a CatBoost en test en ninguna de las dos configuraciones (con la ventana oficial el intervalo queda bajo cero; con todas las cohortes incluye el cero). Las conclusiones de la recomendación (§12) no dependen de la ventana de entrenamiento; la calibración sí, por lo que la configuración oficial es la de la DAI.

## 10. Tiempo y memoria

Entrenamiento y evaluación en una máquina de 32 hilos, 16 GB de RAM y una RTX 4060 de 8 GB. Cada corrida completa (dos `k`, 3 semillas por modelo y 1.000 remuestreos de bootstrap) tarda unos 5–6 minutos; la oficial y la sensibilidad suman unos 12 minutos.

**k = 1 (configuración oficial)**

| Modelo | Tiempo de entrenamiento (s) | Notas |
|---|---|---|
| Tasa histórica (programa, k) | 0.0 |  |
| Logística, solo ingreso | 1.1 | C = 0.01, class_weight = none, 114 columnas |
| Logística, ingreso + agregados | 1.7 | C = 0.01, class_weight = none, 133 columnas |
| CatBoost, solo ingreso | 22.7 | 3 semillas; iteraciones óptimas [59, 44, 68] |
| CatBoost, ingreso + agregados | 48.5 | 3 semillas; iteraciones óptimas [172, 215, 323] |
| GRU, ingreso + secuencia | 2.9 | 16631 parámetros; cuda; pico de memoria GPU 47 MB; épocas óptimas [9, 3, 3] |

**k = 2 (configuración oficial)**

| Modelo | Tiempo de entrenamiento (s) | Notas |
|---|---|---|
| Tasa histórica (programa, k) | 0.0 |  |
| Logística, solo ingreso | 1.4 | C = 1.0, class_weight = none, 109 columnas |
| Logística, ingreso + agregados | 1.4 | C = 0.03, class_weight = none, 128 columnas |
| CatBoost, solo ingreso | 25.1 | 3 semillas; iteraciones óptimas [109, 91, 49] |
| CatBoost, ingreso + agregados | 23.1 | 3 semillas; iteraciones óptimas [44, 77, 48] |
| GRU, ingreso + secuencia | 3.9 | 16591 parámetros; cuda; pico de memoria GPU 61 MB; épocas óptimas [11, 12, 9] |

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

1. **Modelo conservado para T1, elegido en validación (regla única, D114).** `k` = 1: **CatBoost con perfil de ingreso + agregados académicos** (AP en validación: CatBoost 0,318, logística 0,299, GRU 0,320; GRU − CatBoost +0,002 [−0,024; +0,031], sin diferencia, y se conserva el más simple; desde la cohorte 2024, CatBoost + beneficios, D113). `k` = 2: **regresión logística** (AP en validación: logística 0,501, CatBoost 0,495, GRU 0,510; GRU − CatBoost +0,015 [−0,004; +0,032]: logística, CatBoost y GRU no son separables en validación y queda la más simple; en prueba la logística obtiene 0,537, CatBoost 0,552 y GRU 0,526, y la prueba solo confirma). *Nota:* la redacción anterior de este punto elegía CatBoost por el mayor AP puntual en **prueba**; la regla única la corrige (D114). La GRU no se separa de los modelos clásicos en validación en ningún `k` (con la ventana oficial CatBoost la supera en prueba: −0,030 y −0,026 de ΔAP con el intervalo bajo cero); su única ventaja es sobre la logística en `k` = 1 (+0,023). Se descarta para T1 por una complejidad mayor sin ganancia confirmada; los grafos y los embeddings de curso no se justifican con esta evidencia.
2. **Entrenar desde las cohortes 2015** (decisión de la DAI, P49/P50) y repetir el benchmark si la DAI entrega registros anteriores de salidas o de segundos semestres.
3. **No publicar predicciones individuales.** Quedan fuera de la API y de la Bóveda (bandera apagada por omisión); este informe no autoriza su uso en decisiones sobre personas. **Gate 4: el benchmark técnico está completo y la definición operativa de «no continuidad» ya está acordada con la DAI (P51); queda pendiente la revisión institucional y la aprobación del uso**, junto con un plan de monitoreo de deriva y equidad. Ningún riesgo estimado puede automatizar la selección ni la exclusión de postulantes.
4. **Próximos experimentos** (en este orden): supervivencia (tiempo hasta la salida) con censura; `k = 3, 4`; objetivo separado de salida explícita; solo después, características de curso y prerrequisitos bajo la misma ablación.

## 13. Reproducibilidad

- Datos: `neural_mart.snapshot_t1` (hash `28ac6287e979bd9b068c59d01e67a69ee7c585832338f35bc793fca58dacff75`, registrado en `snapshot_t1_resumen`). Código: sha256 de los fuentes de `models/`, `evaluation/` y de las reglas del snapshot, guardado como etiqueta de cada corrida de MLflow (`cb3f1bfa420e6a03ba48ae2e7195136169b474ec58310677ea4d3a99e6d6b878`).
- Cada modelo y cada `k` es una corrida de MLflow (almacén local `mlruns/`, experimento `t1_continuidad_1_anio`) con parámetros, métricas de valid y test con IC, tiempos, memoria GPU, hash de los datos y versión del código. Los JSON agregados y las predicciones están en `artefactos/` (ignorado por git).
- Comandos: ver `README.md` (sección «Snapshots y benchmark T1»). Configuración oficial: `python -m evaluation.run_benchmark` (por omisión `--k 1 2 --train-desde 2015`, artefacto `resultados_t1.json`); sensibilidad: `python -m evaluation.run_benchmark --todos-los-anios` (artefacto `resultados_t1_todos_anios.json`). Este documento se genera con `python tools/informe_t1.py --doc` a partir de `tools/plantilla_t1.md` y de los JSON agregados. Semillas: 0, 1, 2 para CatBoost y GRU; 7 para el bootstrap (11 en `tools/pares_t1.py`).
- Pruebas (en el entorno de ML): reglas de corte/horizonte/slot/cobertura/división, elegibilidad, etiqueta, censura, ausencia de fugas (hechos posteriores al corte no cambian las características), preprocesamiento ajustado solo en train, exclusión de `sexo`, métricas, calibración, bootstrap, subgrupos, GRU, y 7 invariantes del snapshot en la base.

## 14. Beneficios (16-11-2026)

**Qué se probó.** Se agregó a la tarea T1 la situación de financiamiento de cada estudiante (`banner.banner_beneficios`, una fila por año, persona, carrera, beneficio y cobertura; el campo `periodo` es el **año**), con la regla de la DAI del 16-11-2026: los beneficios se asignan por año; si una persona tiene un beneficio en el año *t* y no en *t* + 1, lo **perdió**. La configuración oficial de T1 (`k = 1, 2`, entrenamiento desde 2015, mismos modelos, semillas y particiones) **no cambia**: el hash de datos de las filas oficiales es el mismo de antes (`28ac6287e979bd9b068c59d01e67a69ee7c585832338f35bc793fca58dacff75`) y el reentrenamiento del modelo sin beneficios reproduce la corrida oficial (§14.3). Decisiones D90–D95 (`00_plan.md`).

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

| k | Grupo | n | Con fila de beneficio | Con gratuidad | Con crédito (CAE o FSCU) | Monto 1.er semestre > 0 | Monto 2.º semestre > 0 |
|---|---|---|---|---|---|---|---|
| 1 | Continúa | 20.575 | 73,5 % | 52,2 % | 11,8 % | 73,1 % | 71,3 % |
| 1 | No continúa | 1.128 | 54,7 % | 37,8 % | 6,4 % | 54,3 % | 44,5 % |
| 1 | **Brecha (continúa − no continúa)** | | +18,8 pp | +14,4 pp | +5,4 pp | +18,8 pp | +26,8 pp |
| 2 | Continúa | 16.124 | 74,1 % | 51,5 % | 12,6 % | 73,8 % | 73,1 % |
| 2 | No continúa | 2.093 | 68,8 % | 47,8 % | 9,8 % | 68,7 % | 60,0 % |
| 2 | **Brecha (continúa − no continúa)** | | +5,2 pp | +3,8 pp | +2,8 pp | +5,2 pp | +13,2 pp |
| 4 | Continúa | 13.416 | 74,9 % | 53,0 % | 12,9 % | 74,7 % | 73,9 % |
| 4 | No continúa | 1.160 | 71,6 % | 55,0 % | 8,7 % | 71,4 % | 62,3 % |
| 4 | **Brecha (continúa − no continúa)** | | +3,3 pp | -2,0 pp | +4,2 pp | +3,3 pp | +11,6 pp |

En el segundo semestre la brecha del monto es más del doble que la del primer semestre (`k = 2`: 13,2 frente a 5,2 puntos; `k = 4`: 11,6 frente a 3,3): el monto del segundo semestre reacciona a la salida.

**b) Quienes salen durante el año de ingreso** (ingresaron en el primer semestre y no están matriculados en el segundo; solo `k = 1`):

| Grupo (ingreso en el primer semestre, k = 1) | n | Con fila de beneficio | Con gratuidad | Con crédito (CAE o FSCU) | Monto 1.er semestre > 0 | Monto 2.º semestre > 0 |
|---|---|---|---|---|---|---|
| Sigue matriculado en el segundo semestre | 23.503 | 73,9 % | 52,8 % | 11,6 % | 73,5 % | 71,5 % |
| Sale durante el año de ingreso | 254 | 4,3 % | 2,8 % | 0,4 % | 3,9 % | 2,0 % |
| **Brecha** | | +69,5 pp | +50,0 pp | +11,2 pp | +69,6 pp | +69,5 pp |

Casi no tienen filas de beneficio en la vista final (4 % frente a 74 %), y son una de cada cinco no continuidades de `k = 1`.

**c) Historial de cargas del almacén** (`banner_beneficios_full`, solo conteos). El corte de `k = 1` es el fin del primer semestre (julio); el cierre del año es noviembre:

| Año | Filas en la última carga | Filas cargadas al corte (fin 1.er semestre) | Filas que aún no estaban al corte | Filas retiradas después del corte | Filas agregadas después del corte | Filas retiradas después del cierre (nov.) | Montos del 2.º semestre anulados después del cierre |
|---|---|---|---|---|---|---|---|
| 2024 | 22.160 | 19.737 (2024-07-01) | 10,9 % | 506 (2,6 %) | 2.929 | 271 (1,2 %) | 2,9 % |
| 2025 | 23.035 | 21.817 (2025-07-29) | 5,3 % | 536 (2,5 %) | 1.754 | 375 (1,6 %) | 2,8 % |

Las filas del año se siguen cargando después del fin del primer semestre y una parte se retira más tarde; **los montos del segundo semestre se anulan después del cierre para el 2,8 % de las filas**. ¿Las filas retiradas son de quienes luego no continúan?

| Año | k | Con alguna fila retirada después del corte: n | No continuidad | Resto: n | No continuidad |
|---|---|---|---|---|---|
| 2024 | 1 | 78 | 14,1 % | 2.609 | 3,8 % |
| 2024 | 2 | 67 | 26,9 % | 2.534 | 10,0 % |
| 2024 | 4 | 52 | 36,5 % | 2.158 | 6,1 % |
| 2025 | 1 | 69 | 5,8 % | 2.641 | 4,1 % |
| 2025 | 2 | 0 | — | 48 | 2,1 % |
| 2025 | 4 | 0 | — | 72 | 4,2 % |

**Conclusión del diagnóstico (D92).** (i) `benef_sem2` y `total` se **excluyen en todos los cortes** (también en `k = 2`): se anulan después del cierre y su brecha por resultado duplica la del primer semestre; el modelo los rechaza (`FORBIDDEN`). (ii) En `k = 1` la vista final **no es la del corte**: entre 5 % y 11 % de las filas no estaban cargadas en julio, una parte se retira después y quienes salen durante el año casi no tienen filas. Por eso en `k = 1` los modelos con beneficios **no son elegibles**; sus resultados se informan como sensibilidad (§14.3, §14.8). (iii) En `k = 2` y `k = 4` el corte es el cierre del año y la vista final difiere poco de la del cierre (cambio neto de filas de 0,3 % a 0,6 %, con una rotación bruta de 1 % a 2 %): se usan, con esa salvedad.

### 14.3 `k = 1` y `k = 2`: antes → después de agregar beneficios

Mismos modelos (CatBoost con 3 semillas y logística con C elegido en valid), mismas semillas, particiones y ventana de entrenamiento oficial (cohortes desde 2015); el IC de 95 % y las diferencias pareadas usan un bootstrap agrupado por persona con los **mismos** remuestreos para todos los modelos. El escalón nuevo es «+ beneficios» sobre el mejor conjunto (`pre_entry+academico`). Las cohortes 2015 y 2016 del entrenamiento no tienen datos de beneficios (la fuente empieza en 2017): 40 % de las filas de entrenamiento de `k = 1` y de `k = 2` tienen las variables desconocidas (NaN) con su indicador.

**Reproducción.** El reentrenamiento sin beneficios de esta corrida reproduce la corrida oficial (AP de test):

| Modelo (test) | AP corrida oficial | AP reentrenado en esta corrida | Diferencia |
|---|---|---|---|
| CatBoost, ingreso + agregados | 0,360 | 0,360 | +0,000 |
| Logística, ingreso + agregados | 0,307 | 0,307 | +0,000 |

| Modelo (test) | AP corrida oficial | AP reentrenado en esta corrida | Diferencia |
|---|---|---|---|
| CatBoost, ingreso + agregados | 0,552 | 0,552 | +0,000 |
| Logística, ingreso + agregados | 0,537 | 0,537 | +0,000 |

**`k = 1`** (train: n = 12.012, eventos = 754 (6,3 %); valid: n = 4.192, eventos = 197 (4,7 %); test: n = 4.934, eventos = 280 (5,7 %)).

| Modelo | Partición | AP sin beneficios | AP con beneficios | ΔAP pareado | ROC-AUC sin → con | Brier sin → con | ECE sin → con |
|---|---|---|---|---|---|---|---|
| CatBoost | valid | 0,318 [0,261; 0,394] | 0,331 [0,271; 0,403] | +0,012 [-0,012; +0,036] | 0,856 → 0,849 | 0,0381 → 0,0376 | 0,016 → 0,016 |
| CatBoost | test | 0,360 [0,309; 0,419] | 0,394 [0,338; 0,455] | +0,033 [+0,017; +0,051] | 0,857 → 0,864 | 0,0441 → 0,0425 | 0,007 → 0,010 |
| Logística | valid | 0,299 [0,238; 0,370] | 0,336 [0,274; 0,410] | +0,038 [+0,021; +0,056] | 0,831 → 0,827 | 0,0391 → 0,0378 | 0,019 → 0,016 |
| Logística | test | 0,307 [0,260; 0,364] | 0,360 [0,308; 0,417] | +0,053 [+0,033; +0,071] | 0,844 → 0,856 | 0,0466 → 0,0445 | 0,015 → 0,018 |

Diferencias pareadas, valid:

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, + beneficios − Logística, ingreso + agregados | +0,038 [+0,021; +0,056] | -0,003 [-0,016; +0,009] | -0,0013 [-0,0018; -0,0008] |
| CatBoost, + beneficios − CatBoost, ingreso + agregados | +0,012 [-0,012; +0,036] | -0,007 [-0,021; +0,006] | -0,0005 [-0,0012; +0,0002] |

Diferencias pareadas, test:

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, + beneficios − Logística, ingreso + agregados | +0,053 [+0,033; +0,071] | +0,012 [+0,005; +0,019] | -0,0020 [-0,0029; -0,0011] |
| CatBoost, + beneficios − CatBoost, ingreso + agregados | +0,033 [+0,017; +0,051] | +0,007 [+0,001; +0,012] | -0,0016 [-0,0023; -0,0009] |

- Modelos elegibles en valid: Logística, ingreso + agregados, CatBoost, ingreso + agregados.
- ¿Se pueden elegir modelos con beneficios?: no (el corte es a mitad de año; §14.2).
- **Modelo conservado (mayor AP en valid entre los elegibles): CatBoost, ingreso + agregados** (AP de valid 0,318).

**Lectura de `k = 1`.** En test los beneficios suben el AP de CatBoost de 0,360 a 0,394 (ΔAP +0,033 [+0,017; +0,051]) y el de la logística de 0,307 a 0,360 (ΔAP +0,053 [+0,033; +0,071]), pero **no se adopta**: en valid la diferencia de CatBoost incluye el cero (+0,012 [-0,012; +0,036]) y, sobre todo, el diagnóstico (§14.2) muestra que en este corte la vista final de los beneficios no es la que existía al cierre del primer semestre. Cuánto de la ganancia viene de quienes salen durante el año de ingreso se acota en §14.8.

**`k = 2`** (train: n = 11.247, eventos = 1.480 (13,2 %); valid: n = 4.061, eventos = 464 (11,4 %); test: n = 4.719, eventos = 499 (10,6 %)).

| Modelo | Partición | AP sin beneficios | AP con beneficios | ΔAP pareado | ROC-AUC sin → con | Brier sin → con | ECE sin → con |
|---|---|---|---|---|---|---|---|
| CatBoost | valid | 0,495 [0,445; 0,546] | 0,501 [0,450; 0,551] | +0,006 [-0,001; +0,012] | 0,836 → 0,837 | 0,0748 → 0,0748 | 0,025 → 0,026 |
| CatBoost | test | 0,552 [0,504; 0,599] | 0,545 [0,498; 0,593] | -0,006 [-0,013; +0,000] | 0,890 → 0,888 | 0,0637 → 0,0639 | 0,018 → 0,017 |
| Logística | valid | 0,501 [0,451; 0,551] | 0,509 [0,458; 0,560] | +0,009 [-0,001; +0,018] | 0,857 → 0,859 | 0,0742 → 0,0735 | 0,019 → 0,017 |
| Logística | test | 0,537 [0,493; 0,586] | 0,544 [0,500; 0,592] | +0,007 [-0,002; +0,016] | 0,893 → 0,895 | 0,0717 → 0,0735 | 0,057 → 0,065 |

Diferencias pareadas, valid:

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, + beneficios − Logística, ingreso + agregados | +0,009 [-0,001; +0,018] | +0,002 [-0,002; +0,006] | -0,0007 [-0,0013; +0,0000] |
| CatBoost, + beneficios − CatBoost, ingreso + agregados | +0,006 [-0,001; +0,012] | +0,001 [-0,006; +0,008] | +0,0001 [-0,0002; +0,0004] |

Diferencias pareadas, test:

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, + beneficios − Logística, ingreso + agregados | +0,007 [-0,002; +0,016] | +0,002 [-0,000; +0,004] | +0,0018 [+0,0012; +0,0024] |
| CatBoost, + beneficios − CatBoost, ingreso + agregados | -0,006 [-0,013; +0,000] | -0,002 [-0,006; +0,001] | +0,0003 [-0,0001; +0,0006] |

- Modelos elegibles en valid: Logística, ingreso + agregados, CatBoost, ingreso + agregados.
- ¿Se pueden elegir modelos con beneficios?: sí.
- **Modelo conservado (mayor AP en valid entre los elegibles): Logística, ingreso + agregados** (AP de valid 0,501).

**Lectura de `k = 2`.** Los beneficios **no mejoran** el desempeño de forma detectable: la diferencia pareada de valid incluye el cero en ambos modelos (CatBoost +0,006 [-0,001; +0,012]; logística +0,009 [-0,001; +0,018]) y en test la de CatBoost es -0,006 [-0,013; +0,000] y la de la logística +0,007 [-0,002; +0,016]. No se cumple el criterio del plan de mejora (ΔAP > 0 con IC que excluya 0 en valid), de modo que **ningún modelo con beneficios es elegible**. Entre los modelos sin beneficios, la regla «mayor AP de valid» queda con la logística (0,501 frente a 0,495 de CatBoost); la recomendación oficial (§12) los mantiene equivalentes en test.

### 14.4 Extensión secundaria a `k = 4` (fin del segundo año; D91)

Mismo evento (no continuidad en el período regular dos períodos después del corte), mismas particiones por cohorte y misma ventana de entrenamiento; el corte es el cuarto período regular desde el ingreso, igual que `k = 4` de T3 y de T4/T5. Es la única posición donde la pérdida de un beneficio entre el año 1 y el año 2 se puede probar sin usar el año del resultado. Elegibles: 23.614 episodios (1.039 con salida en el corte y 24 ya egresados quedan fuera); con etiqueta observada y partición: train: n = 8.927, eventos = 740 (8,3 %); valid: n = 3.363, eventos = 340 (10,1 %); test: n = 3.912, eventos = 244 (6,2 %). En el entrenamiento, 18 % de las filas no tienen beneficios del año del corte (cohorte 2015) y 38 % no tienen el año anterior (pérdida desconocida).

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica (programa, k) | 0,080 [0,067; 0,099] | 0,562 [0,526; 0,600] | 0,0591 [0,0529; 0,0653] | 0,027 [0,019; 0,034] |
| Logística, ingreso + agregados | 0,408 [0,352; 0,475] | 0,897 [0,875; 0,920] | 0,0609 [0,0555; 0,0660] | 0,075 [0,068; 0,083] |
| Logística, + beneficios | 0,404 [0,347; 0,469] | 0,894 [0,871; 0,917] | 0,0594 [0,0542; 0,0643] | 0,072 [0,065; 0,080] |
| Logística, + beneficios + pérdidas | 0,398 [0,345; 0,464] | 0,895 [0,873; 0,918] | 0,0599 [0,0547; 0,0649] | 0,071 [0,064; 0,079] |
| CatBoost, ingreso + agregados | 0,400 [0,343; 0,462] | 0,901 [0,879; 0,921] | 0,0442 [0,0394; 0,0488] | 0,016 [0,011; 0,023] |
| CatBoost, + beneficios | 0,397 [0,342; 0,455] | 0,900 [0,879; 0,921] | 0,0442 [0,0395; 0,0488] | 0,015 [0,010; 0,022] |
| CatBoost, + beneficios + pérdidas | 0,409 [0,352; 0,473] | 0,902 [0,882; 0,923] | 0,0437 [0,0391; 0,0483] | 0,017 [0,011; 0,023] |

Diferencias pareadas, valid:

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, + beneficios − Logística, ingreso + agregados | -0,006 [-0,017; +0,005] | +0,001 [-0,002; +0,003] | -0,0002 [-0,0008; +0,0004] |
| CatBoost, + beneficios − CatBoost, ingreso + agregados | -0,014 [-0,029; +0,003] | +0,003 [-0,000; +0,006] | +0,0003 [-0,0002; +0,0009] |
| Logística, + beneficios + pérdidas − Logística, + beneficios | +0,007 [-0,005; +0,016] | -0,001 [-0,003; +0,001] | +0,0004 [-0,0004; +0,0011] |
| CatBoost, + beneficios + pérdidas − CatBoost, + beneficios | +0,019 [+0,003; +0,033] | -0,000 [-0,003; +0,002] | -0,0008 [-0,0014; -0,0002] |
| Logística, + beneficios + pérdidas − Logística, ingreso + agregados | +0,001 [-0,011; +0,010] | -0,000 [-0,003; +0,002] | +0,0002 [-0,0005; +0,0009] |
| CatBoost, + beneficios + pérdidas − CatBoost, ingreso + agregados | +0,005 [-0,010; +0,019] | +0,003 [-0,001; +0,006] | -0,0005 [-0,0011; +0,0002] |

Diferencias pareadas, test:

| Diferencia pareada | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| Logística, + beneficios − Logística, ingreso + agregados | -0,004 [-0,019; +0,008] | -0,003 [-0,006; -0,000] | -0,0015 [-0,0022; -0,0007] |
| CatBoost, + beneficios − CatBoost, ingreso + agregados | -0,003 [-0,020; +0,012] | -0,001 [-0,004; +0,003] | +0,0001 [-0,0004; +0,0005] |
| Logística, + beneficios + pérdidas − Logística, + beneficios | -0,006 [-0,018; +0,006] | +0,001 [-0,001; +0,004] | +0,0005 [-0,0002; +0,0013] |
| CatBoost, + beneficios + pérdidas − CatBoost, + beneficios | +0,012 [-0,008; +0,033] | +0,002 [-0,000; +0,004] | -0,0005 [-0,0011; +0,0001] |
| Logística, + beneficios + pérdidas − Logística, ingreso + agregados | -0,010 [-0,023; +0,002] | -0,002 [-0,004; +0,000] | -0,0010 [-0,0017; -0,0001] |
| CatBoost, + beneficios + pérdidas − CatBoost, ingreso + agregados | +0,009 [-0,010; +0,028] | +0,001 [-0,003; +0,005] | -0,0004 [-0,0010; +0,0002] |

- Modelos elegibles en valid: Logística, ingreso + agregados, CatBoost, ingreso + agregados.
- ¿Se pueden elegir modelos con beneficios?: sí.
- **Modelo conservado (mayor AP en valid entre los elegibles): CatBoost, ingreso + agregados** (AP de valid 0,547).

**Lectura.** Con beneficios y sin pérdida el AP no mejora (CatBoost -0,014 [-0,029; +0,003] en valid y -0,003 [-0,020; +0,012] en test). Agregar la **pérdida de beneficios** sube el AP de CatBoost sobre el modelo con beneficios en valid (+0,019 [+0,003; +0,033]), pero frente al modelo sin ningún beneficio la diferencia es nula (+0,005 [-0,010; +0,019] en valid; +0,009 [-0,010; +0,028] en test). La asociación observada en el perfil general de 2018-2024 (73 % de continuidad entre quienes perdieron la gratuidad frente a 95 % entre quienes la mantienen) es real, pero **no agrega señal sobre las variables académicas** del cierre del segundo año: una explicación plausible es que quienes pierden la gratuidad por superar la duración formal ya muestran el atraso en sus créditos y notas (no se probó).

### 14.5 Importancia de las variables de beneficios (solo agregados)

`k = 1` (sensibilidad):

CatBoost, + beneficios: promedio de 3 semillas; SHAP sobre 4.000 filas de prueba (aleatorias, semilla fija).

| Rango | Variable | Importancia (%) | |SHAP| medio |
|---|---|---|---|
| 1 | `reprobados` | 13,3 | 0,237 |
| 2 | `creditos_aprobados` | 11,6 | 0,258 |
| 3 | `tasa_aprobacion` | 6,7 | 0,134 |
| 4 | `tasa_ult_semestre` | 6,2 | 0,122 |
| 5 | `promedio_evaluado` | 5,0 | 0,105 |
| 6 | `monto_sem1` (beneficio) | 4,2 | 0,064 |
| 7 | `promedio_ult_semestre` | 4,0 | 0,094 |
| 8 | `cod_programa` | 3,4 | 0,044 |
| 9 | `region_colegio` | 3,3 | 0,049 |
| 10 | `mm_mat` | 2,9 | 0,072 |
| 11 | `mm_nem` | 2,8 | 0,033 |
| 12 | `sede` | 2,8 | 0,026 |
| 13 | `mm_ranking` | 2,5 | 0,031 |
| 14 | `cohorte_anio` | 2,3 | 0,086 |
| 15 | `tipo_colegio` | 2,2 | 0,016 |

Variables de beneficios fuera de las primeras posiciones:

| Rango | Variable | Importancia (%) | |SHAP| medio |
|---|---|---|---|
| 21 | `banda_decil` | 1,77 | 0,021 |
| 22 | `n_beneficios` | 1,57 | 0,020 |
| 31 | `tiene_beca_estatal` | 0,81 | 0,004 |
| 32 | `tiene_beca_ucn` | 0,51 | 0,006 |
| 33 | `tiene_gratuidad` | 0,48 | 0,008 |
| 34 | `merito_ingreso` | 0,47 | 0,005 |
| 35 | `tiene_credito` | 0,43 | 0,005 |
| 37 | `expiro_gratuidad` | 0,30 | 0,005 |
| 38 | `ben_sin_dato` | 0,26 | 0,003 |
| 41 | `merito_e1` | 0,20 | 0,002 |
| 42 | `etapa_capstone` | 0,16 | 0,003 |

Suma de la importancia de las variables de beneficios: 11,2 %.

`k = 2`:

CatBoost, + beneficios: promedio de 3 semillas; SHAP sobre 4.000 filas de prueba (aleatorias, semilla fija).

| Rango | Variable | Importancia (%) | |SHAP| medio |
|---|---|---|---|
| 1 | `reprobados` | 17,2 | 0,253 |
| 2 | `promedio_ult_semestre` | 15,7 | 0,248 |
| 3 | `creditos_aprobados` | 11,8 | 0,177 |
| 4 | `tasa_ult_semestre` | 11,3 | 0,176 |
| 5 | `intentos_ult_semestre` | 8,1 | 0,129 |
| 6 | `tasa_aprobacion` | 4,5 | 0,080 |
| 7 | `promedio_evaluado` | 4,2 | 0,086 |
| 8 | `n_notas_promedio` | 2,7 | 0,012 |
| 9 | `intentos_evaluados` | 2,4 | 0,012 |
| 10 | `mm_mat` | 2,4 | 0,033 |
| 11 | `mm_historia` | 1,3 | 0,016 |
| 12 | `mm_leng` | 1,2 | 0,013 |
| 13 | `mm_ciencias` | 1,1 | 0,013 |
| 14 | `prueba_admision` | 1,1 | 0,007 |
| 15 | `monto_sem1` (beneficio) | 1,1 | 0,025 |

Variables de beneficios fuera de las primeras posiciones:

| Rango | Variable | Importancia (%) | |SHAP| medio |
|---|---|---|---|
| 28 | `n_beneficios` | 0,50 | 0,014 |
| 30 | `tiene_gratuidad` | 0,42 | 0,007 |
| 31 | `tiene_credito` | 0,37 | 0,004 |
| 33 | `tiene_beca_ucn` | 0,31 | 0,003 |
| 35 | `banda_decil` | 0,23 | 0,005 |
| 36 | `merito_e1` | 0,23 | 0,003 |
| 37 | `expiro_gratuidad` | 0,20 | 0,003 |
| 38 | `tiene_beca_estatal` | 0,16 | 0,003 |
| 40 | `merito_ingreso` | 0,14 | 0,001 |
| 42 | `ben_sin_dato` | 0,09 | 0,001 |
| 46 | `etapa_capstone` | 0,01 | 0,000 |

Suma de la importancia de las variables de beneficios: 3,7 %.

`k = 4`, con pérdidas:

CatBoost, + beneficios + pérdidas: promedio de 3 semillas; SHAP sobre 3.912 filas de prueba (aleatorias, semilla fija).

| Rango | Variable | Importancia (%) | |SHAP| medio |
|---|---|---|---|
| 1 | `tasa_ult_semestre` | 17,6 | 0,355 |
| 2 | `promedio_ult_semestre` | 13,1 | 0,332 |
| 3 | `reprobados` | 10,2 | 0,271 |
| 4 | `tasa_aprobacion` | 4,7 | 0,120 |
| 5 | `creditos_aprobados` | 4,7 | 0,106 |
| 6 | `promedio_evaluado` | 3,6 | 0,071 |
| 7 | `intentos_ult_semestre` | 3,6 | 0,073 |
| 8 | `region_colegio` | 2,2 | 0,026 |
| 9 | `n_interrupcion` | 2,0 | 0,069 |
| 10 | `intentos_evaluados` | 1,9 | 0,028 |
| 11 | `cursos_verano_invierno` | 1,9 | 0,037 |
| 12 | `mm_ciencias` | 1,8 | 0,013 |
| 13 | `tipo_colegio` | 1,8 | 0,016 |
| 14 | `mm_nem` | 1,8 | 0,029 |
| 15 | `depend_colegio` | 1,8 | 0,029 |

Variables de beneficios fuera de las primeras posiciones:

| Rango | Variable | Importancia (%) | |SHAP| medio |
|---|---|---|---|
| 17 | `banda_decil` | 1,59 | 0,010 |
| 19 | `monto_sem1` | 1,51 | 0,049 |
| 26 | `tiene_gratuidad` | 1,16 | 0,035 |
| 28 | `n_beneficios` | 1,12 | 0,029 |
| 32 | `perdio_cualquier_beneficio` | 0,71 | 0,009 |
| 35 | `perdio_gratuidad` | 0,60 | 0,007 |
| 36 | `tiene_credito` | 0,58 | 0,007 |
| 38 | `perdio_credito` | 0,51 | 0,008 |
| 39 | `obtuvo_gratuidad` | 0,35 | 0,009 |
| 41 | `perdida_sin_dato` | 0,31 | 0,004 |
| 42 | `expiro_gratuidad` | 0,25 | 0,002 |
| 43 | `tiene_beca_ucn` | 0,22 | 0,002 |
| 44 | `tiene_beca_estatal` | 0,20 | 0,002 |
| 45 | `ben_sin_dato` | 0,15 | 0,002 |
| 46 | `merito_ingreso` | 0,15 | 0,001 |
| 48 | `merito_e1` | 0,13 | 0,001 |
| 49 | `etapa_capstone` | 0,13 | 0,003 |

Suma de la importancia de las variables de beneficios: 9,7 %.

Las variables académicas del último semestre dominan en todos los cortes; los beneficios aportan una fracción pequeña de la importancia total.

### 14.6 Resultados por programa y por facultad (modelo conservado; prueba)

T1 no tenía vista por facultad; se agrega con el mismo método de T4 y T5 (pronóstico agregado: tasa observada y riesgo medio del grupo con IC del bootstrap agrupado por persona; solo grupos con n ≥ 100 y al menos 10 eventos). Los nombres de facultad salen de `common.facultad_d` (D82).

**`k = 1`, por facultad**

Modelo conservado: CatBoost, ingreso + agregados; prueba. Se listan 10 de 13 grupos (n ≥ 100 y ≥ 10 eventos); los demás se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio | Brecha (predicho − observado) | AP |
|---|---|---|---|---|---|---|
| Escuela de Arquitectura | 173 | 20 | 11,6 % | 6,7 % | -0,048 [-0,094; -0,005] | 0,465 |
| Escuela de Ciencias Empresariales | 417 | 26 | 6,2 % | 4,3 % | -0,019 [-0,040; -0,000] | 0,363 |
| Escuela de Ingeniería | 594 | 26 | 4,4 % | 5,8 % | +0,014 [-0,002; +0,030] | 0,234 |
| Facultad de Ciencias | 263 | 20 | 7,6 % | 6,4 % | -0,012 [-0,040; +0,015] | 0,468 |
| Facultad de Ciencias Jurídicas | 521 | 22 | 4,2 % | 4,4 % | +0,002 [-0,016; +0,018] | 0,249 |
| Facultad de Ciencias de Ingeniería y Construcción | 183 | 17 | 9,3 % | 8,0 % | -0,013 [-0,055; +0,025] | 0,359 |
| Facultad de Ciencias del Mar | 185 | 13 | 7,0 % | 9,2 % | +0,022 [-0,012; +0,053] | 0,535 |
| Facultad de Economía y Administración | 476 | 28 | 5,9 % | 5,1 % | -0,008 [-0,027; +0,009] | 0,595 |
| Facultad de Educación | 270 | 12 | 4,4 % | 3,1 % | -0,014 [-0,037; +0,007] | 0,466 |
| Facultad de Ingeniería y Ciencias Geológicas | 1.166 | 75 | 6,4 % | 5,8 % | -0,007 [-0,020; +0,007] | 0,353 |

Error absoluto medio ponderado de la tasa del grupo: modelo 0,012 [0,009; 0,019], tasa histórica 0,015 [0,011; 0,023]; correlación de Spearman entre riesgo medio y tasa observada: 0,709 [0,127; 0,891].

**`k = 1`, por programa**

Modelo conservado: CatBoost, ingreso + agregados; prueba. Se listan 12 de 47 grupos (n ≥ 100 y ≥ 10 eventos); los demás se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio | Brecha (predicho − observado) | AP |
|---|---|---|---|---|---|---|
| 8213 ARQUITECTURA | 173 | 20 | 11,6 % | 6,7 % | -0,048 [-0,094; -0,005] | 0,465 |
| 8233 INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 161 | 12 | 7,5 % | 6,6 % | -0,008 [-0,047; +0,030] | 0,411 |
| 8323 INGENIERÍA COMERCIAL | 296 | 19 | 6,4 % | 4,9 % | -0,016 [-0,039; +0,008] | 0,501 |
| 8326 INGENIERÍA COMERCIAL | 268 | 10 | 3,7 % | 2,8 % | -0,009 [-0,031; +0,010] | 0,210 |
| 8373 DERECHO | 249 | 11 | 4,4 % | 4,4 % | +0,000 [-0,027; +0,022] | 0,342 |
| 8376 DERECHO | 272 | 11 | 4,0 % | 4,4 % | +0,004 [-0,020; +0,025] | 0,293 |
| 8403 GEOLOGÍA | 130 | 10 | 7,7 % | 7,0 % | -0,007 [-0,049; +0,028] | 0,475 |
| 8483 QUÍMICA Y FARMACIA | 131 | 12 | 9,2 % | 6,9 % | -0,022 [-0,063; +0,015] | 0,584 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 221 | 17 | 7,7 % | 6,3 % | -0,014 [-0,050; +0,018] | 0,302 |
| 8606 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 212 | 16 | 7,5 % | 7,4 % | -0,002 [-0,035; +0,030] | 0,362 |
| 8653 INGENIERÍA CIVIL DE MINAS | 156 | 10 | 6,4 % | 5,4 % | -0,010 [-0,043; +0,024] | 0,489 |
| 8896 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 149 | 16 | 10,7 % | 7,0 % | -0,037 [-0,088; +0,004] | 0,507 |

Error absoluto medio ponderado de la tasa del grupo: modelo 0,013 [0,011; 0,026], tasa histórica 0,021 [0,017; 0,034]; correlación de Spearman entre riesgo medio y tasa observada: 0,806 [0,403; 0,902].

**`k = 2`, por facultad**

Modelo conservado: Logística, ingreso + agregados; prueba. Se listan 12 de 13 grupos (n ≥ 100 y ≥ 10 eventos); los demás se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio | Brecha (predicho − observado) | AP |
|---|---|---|---|---|---|---|
| Escuela de Arquitectura | 156 | 16 | 10,3 % | 17,2 % | +0,069 [+0,028; +0,109] | 0,628 |
| Escuela de Ciencias Empresariales | 400 | 45 | 11,2 % | 16,0 % | +0,048 [+0,023; +0,073] | 0,601 |
| Escuela de Educación Coquimbo | 103 | 10 | 9,7 % | 10,3 % | +0,006 [-0,034; +0,041] | 0,793 |
| Escuela de Ingeniería | 573 | 51 | 8,9 % | 15,5 % | +0,066 [+0,047; +0,084] | 0,625 |
| Facultad de Ciencias | 249 | 27 | 10,8 % | 16,1 % | +0,053 [+0,016; +0,087] | 0,467 |
| Facultad de Ciencias Jurídicas | 503 | 56 | 11,1 % | 17,0 % | +0,059 [+0,034; +0,082] | 0,490 |
| Facultad de Ciencias de Ingeniería y Construcción | 173 | 23 | 13,3 % | 20,5 % | +0,072 [+0,030; +0,115] | 0,572 |
| Facultad de Ciencias del Mar | 177 | 25 | 14,1 % | 21,6 % | +0,075 [+0,032; +0,113] | 0,699 |
| Facultad de Economía y Administración | 455 | 49 | 10,8 % | 16,5 % | +0,057 [+0,037; +0,078] | 0,635 |
| Facultad de Educación | 255 | 14 | 5,5 % | 6,7 % | +0,012 [-0,013; +0,035] | 0,337 |
| Facultad de Ingeniería y Ciencias Geológicas | 1.109 | 141 | 12,7 % | 21,7 % | +0,090 [+0,071; +0,108] | 0,461 |
| Facultad de Medicina | 358 | 36 | 10,1 % | 8,4 % | -0,016 [-0,036; +0,005] | 0,715 |

Error absoluto medio ponderado de la tasa del grupo: modelo 0,060 [0,053; 0,068], tasa histórica 0,024 [0,019; 0,034]; correlación de Spearman entre riesgo medio y tasa observada: 0,832 [0,357; 0,930].

**`k = 2`, por programa**

Modelo conservado: Logística, ingreso + agregados; prueba. Se listan 15 de 46 grupos (n ≥ 100 y ≥ 10 eventos); los demás se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio | Brecha (predicho − observado) | AP |
|---|---|---|---|---|---|---|
| 8213 ARQUITECTURA | 156 | 16 | 10,3 % | 17,2 % | +0,069 [+0,028; +0,109] | 0,628 |
| 8233 INGENIERÍA EN COMPUTACIÓN E INFORMÁTICA | 151 | 16 | 10,6 % | 21,3 % | +0,107 [+0,064; +0,154] | 0,438 |
| 8266 INGENIERÍA EN TECNOLOGÍAS DE INFORMACIÓN | 112 | 12 | 10,7 % | 22,6 % | +0,118 [+0,069; +0,168] | 0,644 |
| 8323 INGENIERÍA COMERCIAL | 281 | 38 | 13,5 % | 20,0 % | +0,064 [+0,034; +0,095] | 0,627 |
| 8326 INGENIERÍA COMERCIAL | 260 | 20 | 7,7 % | 13,6 % | +0,059 [+0,030; +0,091] | 0,392 |
| 8373 DERECHO | 239 | 20 | 8,4 % | 17,1 % | +0,088 [+0,049; +0,122] | 0,337 |
| 8376 DERECHO | 264 | 36 | 13,6 % | 16,9 % | +0,033 [-0,001; +0,067] | 0,661 |
| 8403 GEOLOGÍA | 124 | 17 | 13,7 % | 18,5 % | +0,048 [-0,004; +0,103] | 0,435 |
| 8483 QUÍMICA Y FARMACIA | 122 | 17 | 13,9 % | 13,9 % | +0,000 [-0,050; +0,046] | 0,731 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 202 | 30 | 14,9 % | 29,8 % | +0,149 [+0,096; +0,202] | 0,419 |
| 8606 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 201 | 26 | 12,9 % | 19,3 % | +0,064 [+0,030; +0,097] | 0,691 |
| 8613 INGENIERÍA CIVIL INDUSTRIAL | 246 | 21 | 8,5 % | 15,0 % | +0,065 [+0,035; +0,094] | 0,670 |
| 8616 INGENIERÍA CIVIL INDUSTRIAL | 260 | 13 | 5,0 % | 9,6 % | +0,046 [+0,023; +0,068] | 0,547 |
| 8653 INGENIERÍA CIVIL DE MINAS | 153 | 27 | 17,6 % | 21,1 % | +0,035 [-0,016; +0,083] | 0,643 |
| 8896 INGENIERÍA EN INFORMACIÓN Y CONTROL DE GESTIÓN | 140 | 25 | 17,9 % | 20,5 % | +0,026 [-0,019; +0,067] | 0,806 |

Error absoluto medio ponderado de la tasa del grupo: modelo 0,065 [0,057; 0,076], tasa histórica 0,036 [0,030; 0,049]; correlación de Spearman entre riesgo medio y tasa observada: 0,550 [0,253; 0,818].

**`k = 4`, por facultad**

Modelo conservado: CatBoost, ingreso + agregados; prueba. Se listan 10 de 13 grupos (n ≥ 100 y ≥ 10 eventos); los demás se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio | Brecha (predicho − observado) | AP |
|---|---|---|---|---|---|---|
| Escuela de Arquitectura | 125 | 11 | 8,8 % | 9,1 % | +0,003 [-0,041; +0,040] | 0,514 |
| Escuela de Ciencias Empresariales | 336 | 15 | 4,5 % | 5,9 % | +0,014 [-0,008; +0,036] | 0,291 |
| Escuela de Ingeniería | 483 | 21 | 4,3 % | 7,4 % | +0,031 [+0,013; +0,048] | 0,417 |
| Facultad de Ciencias | 211 | 20 | 9,5 % | 10,9 % | +0,014 [-0,020; +0,046] | 0,429 |
| Facultad de Ciencias Jurídicas | 406 | 46 | 11,3 % | 9,1 % | -0,023 [-0,049; +0,005] | 0,434 |
| Facultad de Ciencias de Ingeniería y Construcción | 138 | 11 | 8,0 % | 11,3 % | +0,033 [-0,008; +0,071] | 0,442 |
| Facultad de Economía y Administración | 373 | 19 | 5,1 % | 6,4 % | +0,013 [-0,007; +0,031] | 0,482 |
| Facultad de Educación | 236 | 11 | 4,7 % | 4,3 % | -0,004 [-0,030; +0,021] | 0,307 |
| Facultad de Ingeniería y Ciencias Geológicas | 864 | 56 | 6,5 % | 10,6 % | +0,041 [+0,027; +0,054] | 0,439 |
| Facultad de Medicina | 312 | 17 | 5,4 % | 4,6 % | -0,008 [-0,030; +0,010] | 0,446 |

Error absoluto medio ponderado de la tasa del grupo: modelo 0,023 [0,019; 0,031], tasa histórica 0,028 [0,022; 0,037]; correlación de Spearman entre riesgo medio y tasa observada: 0,636 [0,285; 0,867].

**`k = 4`, por programa**

Modelo conservado: CatBoost, ingreso + agregados; prueba. Se listan 6 de 47 grupos (n ≥ 100 y ≥ 10 eventos); los demás se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio | Brecha (predicho − observado) | AP |
|---|---|---|---|---|---|---|
| 8213 ARQUITECTURA | 125 | 11 | 8,8 % | 9,1 % | +0,003 [-0,041; +0,040] | 0,514 |
| 8323 INGENIERÍA COMERCIAL | 224 | 11 | 4,9 % | 6,8 % | +0,018 [-0,005; +0,041] | 0,508 |
| 8373 DERECHO | 190 | 16 | 8,4 % | 8,2 % | -0,003 [-0,038; +0,032] | 0,354 |
| 8376 DERECHO | 216 | 30 | 13,9 % | 9,9 % | -0,040 [-0,083; -0,000] | 0,489 |
| 8483 QUÍMICA Y FARMACIA | 104 | 10 | 9,6 % | 8,3 % | -0,013 [-0,058; +0,031] | 0,566 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 153 | 16 | 10,5 % | 12,9 % | +0,024 [-0,018; +0,068] | 0,642 |

Error absoluto medio ponderado de la tasa del grupo: modelo 0,019 [0,012; 0,036], tasa histórica 0,018 [0,014; 0,041]; correlación de Spearman entre riesgo medio y tasa observada: 0,886 [-0,086; 0,943].

### 14.7 Equidad por banda de decil y por sexo (modelo conservado frente a CatBoost sin beneficios; prueba)

`banda_decil` es una variable socioeconómica del hogar (gratuidad ⇒ decil 6 o menos; «Rebaja por decil» ⇒ 7 u 8-9; el resto, desconocida). Se puede usar como variable porque no es un atributo protegido de la especificación, y **se informa su equidad de forma descriptiva** (sin IC ni ajuste; solo grupos de 30 filas o más). `sexo` se usa solo aquí, nunca como variable.

**`k = 1`**

| Grupo | Modelo | n | Tasa observada | Riesgo medio | Brecha de calibración | AP | Recall@10% |
|---|---|---|---|---|---|---|---|
| 7 | CatBoost, ingreso + agregados | 65 | 4,6 % | 2,9 % | -0,018 | 0,113 | 0,333 |
| 8-9 | CatBoost, ingreso + agregados | 153 | 2,0 % | 3,4 % | +0,015 | 0,600 | 1,000 |
| <=6 | CatBoost, ingreso + agregados | 2.638 | 3,6 % | 5,4 % | +0,017 | 0,249 | 0,521 |
| desconocida | CatBoost, ingreso + agregados | 2.078 | 8,6 % | 5,2 % | -0,033 | 0,518 | 0,562 |

| Grupo | Modelo | n | Tasa observada | Riesgo medio | Brecha de calibración | AP | Recall@10% |
|---|---|---|---|---|---|---|---|
| F | CatBoost, ingreso + agregados | 2.238 | 5,9 % | 4,8 % | -0,010 | 0,423 | 0,588 |
| M | CatBoost, ingreso + agregados | 2.695 | 5,5 % | 5,5 % | +0,000 | 0,315 | 0,503 |

**`k = 2`**

| Grupo | Modelo | n | Tasa observada | Riesgo medio | Brecha de calibración | AP | Recall@10% |
|---|---|---|---|---|---|---|---|
| 7 | Logística, ingreso + agregados | 65 | 10,8 % | 12,0 % | +0,013 | 0,708 | 0,571 |
| 8-9 | Logística, ingreso + agregados | 151 | 7,9 % | 11,1 % | +0,031 | 0,626 | 0,750 |
| <=6 | Logística, ingreso + agregados | 2.580 | 10,3 % | 17,3 % | +0,070 | 0,559 | 0,541 |
| desconocida | Logística, ingreso + agregados | 1.923 | 11,1 % | 15,2 % | +0,041 | 0,514 | 0,481 |
| 7 | CatBoost, ingreso + agregados | 65 | 10,8 % | 9,1 % | -0,017 | 0,672 | 0,571 |
| 8-9 | CatBoost, ingreso + agregados | 151 | 7,9 % | 8,5 % | +0,005 | 0,651 | 0,750 |
| <=6 | CatBoost, ingreso + agregados | 2.580 | 10,3 % | 12,3 % | +0,020 | 0,559 | 0,564 |
| desconocida | CatBoost, ingreso + agregados | 1.923 | 11,1 % | 11,1 % | -0,001 | 0,545 | 0,528 |

| Grupo | Modelo | n | Tasa observada | Riesgo medio | Brecha de calibración | AP | Recall@10% |
|---|---|---|---|---|---|---|---|
| F | Logística, ingreso + agregados | 2.138 | 9,7 % | 13,9 % | +0,042 | 0,532 | 0,599 |
| M | Logística, ingreso + agregados | 2.580 | 11,3 % | 18,1 % | +0,068 | 0,546 | 0,497 |
| F | CatBoost, ingreso + agregados | 2.138 | 9,7 % | 10,1 % | +0,004 | 0,558 | 0,604 |
| M | CatBoost, ingreso + agregados | 2.580 | 11,3 % | 12,9 % | +0,016 | 0,545 | 0,514 |

**`k = 4`**

| Grupo | Modelo | n | Tasa observada | Riesgo medio | Brecha de calibración | AP | Recall@10% |
|---|---|---|---|---|---|---|---|
| 8-9 | CatBoost, ingreso + agregados | 38 | 0,0 % | 2,2 % | +0,022 | — | — |
| <=6 | CatBoost, ingreso + agregados | 2.383 | 7,1 % | 8,2 % | +0,010 | 0,427 | 0,659 |
| desconocida | CatBoost, ingreso + agregados | 1.482 | 4,9 % | 7,1 % | +0,023 | 0,343 | 0,722 |

| Grupo | Modelo | n | Tasa observada | Riesgo medio | Brecha de calibración | AP | Recall@10% |
|---|---|---|---|---|---|---|---|
| F | CatBoost, ingreso + agregados | 1.811 | 6,6 % | 6,8 % | +0,002 | 0,432 | 0,714 |
| M | CatBoost, ingreso + agregados | 2.100 | 6,0 % | 8,5 % | +0,025 | 0,386 | 0,640 |

### 14.8 Sensibilidades

**Sin las personas que salen durante el año de ingreso** (`k = 1`; se excluyen de entrenamiento, valid y test quienes no están matriculados en el segundo semestre; así el sesgo de §14.2 b no actúa):

| k | Entrenamiento | n train / valid / test | AP CatBoost sin → con beneficios (test) | ΔAP pareado CatBoost (valid) | ΔAP pareado CatBoost (test) | ΔAP pareado logística (test) |
|---|---|---|---|---|---|---|
| 1 | sin las salidas durante el año de ingreso | 11.736 / 4.149 / 4.864 | 0,311 → 0,325 | +0,015 [+0,000; +0,028] | +0,014 [+0,001; +0,026] | +0,031 [+0,016; +0,043] |

Con la configuración oficial completa, la ganancia de CatBoost en test es +0,033 [+0,017; +0,051]; sin esas personas baja a +0,014 [+0,001; +0,026], es decir, más de la mitad de la ganancia aparente de `k = 1` desaparece cuando se quita un efecto que no sería observable al cierre del semestre.

**Entrenar solo con cohortes desde 2017** (todas con datos de beneficios; entrenamiento más pequeño):

| k | Entrenamiento | n train / valid / test | AP CatBoost sin → con beneficios (test) | ΔAP pareado CatBoost (valid) | ΔAP pareado CatBoost (test) | ΔAP pareado logística (test) |
|---|---|---|---|---|---|---|
| 1 | cohortes desde 2017 | 7.180 / 4.192 / 4.934 | 0,344 → 0,398 | +0,034 [+0,008; +0,060] | +0,054 [+0,034; +0,074] | +0,068 [+0,043; +0,089] |
| 2 | cohortes desde 2017 | 6.775 / 4.061 / 4.719 | 0,551 → 0,553 | +0,002 [-0,006; +0,012] | +0,002 [-0,006; +0,012] | +0,005 [-0,004; +0,015] |
| 4 | cohortes desde 2017 | 5.468 / 3.363 / 3.912 | 0,396 → 0,381 | +0,001 [-0,012; +0,015] | -0,015 [-0,031; +0,003] | -0,014 [-0,032; +0,003] |

### 14.9 Conclusión y límites

1. **Configuración oficial de T1 (`k = 1` y `k = 2`): sin cambios.** Los beneficios no cumplen el criterio de adopción en ningún corte: en `k = 1` el corte es a mitad de año y la vista final de la fuente no es la del corte (no elegibles), y en `k = 2` y `k = 4` la diferencia pareada de valid incluye el cero. T1 sigue con ingreso + agregados académicos (CatBoost, con la logística como alternativa).
2. **Dónde está el valor de los beneficios.** Para ordenar a quienes ya cerraron el semestre, el desempeño académico explica casi todo. Los beneficios describen **con quién** se está hablando (gratuidad, decil, crédito) y sirven como descripción y equidad (§14.7), no como señal adicional de continuidad.
3. **Lo que falta para volver a probarlos.** La fecha en que la fuente registra la asignación o el retiro de un beneficio (P90), por qué se retiran filas durante el año (P91) y un historial de cargas anterior a 2024 (P93). Con la vista de cada corte tal como existía, `k = 1` se podría evaluar de forma limpia y también un corte a mitad de semestre.
4. **Límites.** Los años anteriores a 2017 no tienen datos (las cohortes 2015-2016 quedan con beneficios desconocidos); las variables dependen de la clasificación por código y 12 códigos (aportes externos y ajustes de deuda) solo cuentan en `n_beneficios`; un beneficio de otro programa en el mismo año se ignora; la pérdida de beneficios solo existe en `k = 4`; con 244 eventos en la prueba de `k = 4` diferencias menores que 0,03 de AP no son separables.

## 15. Beneficios con historial de cargas (16-11-2026)

**Qué se hizo.** El §14 dejó los beneficios fuera de la configuración oficial de T1 porque, en `k = 1`, la vista final de la fuente (`banner.banner_beneficios`, la última carga de `banner_beneficios_full`) no es la que existía al cierre del primer semestre. La DAI respondió el 16-11-2026 tres preguntas que permiten volver a probarlo: **P90** no existe una fecha de asignación; lo más cercano es la marca de tiempo (`timestamp_carga`) de la **primera carga** de `banner_beneficios_full` en que aparece la fila; **P91** el retiro de filas «significa que ya tendría el beneficio» (respuesta ambigua; se contrasta con datos en §15.4); **P93** no hay historial de cargas anterior a 2024 y los beneficios han crecido (riesgo de deriva si se reducen). Con esa información se construyó una **vista de beneficios en el punto del tiempo** a partir del historial de cargas y se usó para (1) medir cuánto filtra la vista final en `k = 1` y `k = 2` y (2) reevaluar T1 en los años con historial. La configuración oficial no cambia. Decisiones D96–D99 (`00_plan.md`).

### 15.1 Calendario de cargas y años con historial

`banner_beneficios_full` tiene **68 cargas** (marcas de tiempo distintas; fechas en UTC): la primera es del **2024-01-08** y la última del 2026-11-12 (10.144.160 filas en total). La primera carga solo traía el año 2017 (12.767 filas) y dos minutos después se cargaron los años 2017-2023 completos (111.340 filas): **los años 2017-2023 llegaron todos de una vez el 8-1-2024**, de modo que su «primera carga» no dice nada sobre cuándo se asignó cada fila. Los años 2024, 2025 y 2026 sí se cargaron a medida que avanzaba cada año.

| Año calendario | Cargas | Filas por carga (mín.–máx.) | Cadencia |
|---|---|---|---|
| 2024 | 16 | 12.767–133.581 | sin cargas entre el 4-abr y el 1-jul; luego cada 1-8 semanas |
| 2025 | 23 | 133.525–156.614 | cada 1-4 semanas; sin cargas entre el 17-jun y el 29-jul |
| 2026 (hasta el 12-nov) | 29 | 20.015–180.493 | cada 1-3 semanas desde abril |

| Año del beneficio | Primera carga que lo contiene | ¿Tiene historial? | Filas en la última carga |
|---|---|---|---|
| 2017 | 2024-01-08 | no (llegó completo en la primera carga de 2024) | 12.767 |
| 2018 | 2024-01-08 | no (llegó completo en la primera carga de 2024) | 13.274 |
| 2019 | 2024-01-08 | no (llegó completo en la primera carga de 2024) | 14.947 |
| 2020 | 2024-01-08 | no (llegó completo en la primera carga de 2024) | 16.008 |
| 2021 | 2024-01-08 | no (llegó completo en la primera carga de 2024) | 17.102 |
| 2022 | 2024-01-08 | no (llegó completo en la primera carga de 2024) | 16.353 |
| 2023 | 2024-01-08 | no (llegó completo en la primera carga de 2024) | 20.864 |
| 2024 | 2024-04-04 | sí | 22.160 |
| 2025 | 2025-03-25 | sí | 23.035 |
| 2026 | 2026-04-14 | sí | 23.983 |

Solo **2024, 2025 y 2026** tienen historial. Para T1 esto significa que los cortes con año de corte 2024 o posterior se pueden reconstruir; las cohortes de entrenamiento (2015-2019), de valid (2020-2021) y la ventana oficial de test (2022-2023) **no**: quedan como «desconocido» (NaN + indicador), coherente con D90. Los cortes del año 2026 (en curso) no tienen etiqueta observada.

### 15.2 Regla del punto en el tiempo (D96)

Historial comprimido en `neural_stg.banner_beneficios_cargas` (migración `026_beneficios_cargas.sql`; una fila por año, persona, programa, código y cobertura: primera y última carga en que aparece, cantidad de cargas, presencia en la última carga y montos del 1.er y 2.º semestre en la primera y la última carga; 182.695 filas, 0 omitidas; el RUT pasa a `persona_key` con el HMAC vigente y la huella se verificó sin `--force-todo`) y calendario de cargas por año en `neural_stg.banner_beneficios_cargas_cal` (587 filas). La agregación se hizo en el `SELECT` del almacén (solo lectura, `GROUP BY`, sin subconsultas correlacionadas; 20 s).

Para un corte con fecha *c* y un año de beneficio *t*:

1. Fechas de corte (el mismo calendario del diagnóstico del §14.2c): fin del primer semestre (período `AAAA10`) = **31 de julio**; fin del año (`AAAA20`) = **30 de noviembre** del año del corte.
2. *L* = última carga del año *t* con fecha ≤ *c*. Si *t* no tiene historial o no hay carga ≤ *c*, el año es **desconocido** (NaN + `ben_sin_dato`), nunca 0.
3. Una fila del año *t* es **visible** en *c* si `primera_carga ≤ L ≤ última_carga`: ya estaba cargada en *L* y no se había retirado antes. Una fila que desaparece y reaparece se trata como presente (33-168 filas por año y corte, ≤ 0,8 % de las visibles; tabla siguiente).
4. El monto del primer semestre es el de la **primera carga** de la fila: es el único monto del historial comprimido que es anterior a *c* pase lo que pase después (el monto cambia después de la primera carga en 2-26 % de las filas; se informa como límite). `benef_sem2` y `total` no son variables (D92). Solo cuentan las filas del programa del episodio, como en D91.
5. Nada posterior a *L* (última carga, cantidad de cargas, presencia en la última carga, montos de la última carga, cargas posteriores del calendario) altera la visibilidad ni las variables: las pruebas de perturbación lo verifican (`tests/unit/test_beneficios_cargas.py`).

Las variables tienen las mismas columnas que las de la vista final (`COLS_BENEFICIOS`), de modo que los modelos entrenados con la vista final se aplican sin cambios. Las variables de pérdida (solo `k = 4`) no se definen: `k = 4` no tiene cortes con historial y etiqueta observada.

Filas de la vista final frente a las visibles en el corte (todas las filas del historial de cada año):

| Año | Corte | Carga *L* | Filas en la vista final | Visibles en el corte | Finales aún no cargadas en el corte | Visibles retiradas después | Visibles con hueco de cargas | Visibles con monto 1.er sem. distinto al final |
|---|---|---|---|---|---|---|---|---|
| 2024 | fin del 1.er semestre (31-jul) | 2024-07-01 | 22.160 | 19.765 | 2.901 (13,1 %) | 506 (2,6 %) | 33 | 1.074 |
| 2024 | fin del año (30-nov) | 2024-11-07 | 22.160 | 22.115 | 316 (1,4 %) | 271 (1,2 %) | 37 | 1.288 |
| 2025 | fin del 1.er semestre (31-jul) | 2025-07-29 | 23.035 | 21.829 | 1.746 (7,6 %) | 540 (2,5 %) | 162 | 5.609 |
| 2025 | fin del año (30-nov) | 2025-11-10 | 23.035 | 22.907 | 503 (2,2 %) | 375 (1,6 %) | 168 | 5.686 |
| 2026 | fin del 1.er semestre (31-jul) | 2026-07-28 | 23.983 | 22.976 | 1.208 (5,0 %) | 201 (0,9 %) | 47 | 461 |
| 2026 | fin del año (30-nov) | aún no ocurre | — | — | — | — | — | — |

Las filas visibles coinciden con las de la carga *L* del §14.2c (19.737 en 2024 y 21.817 en 2025, frente a 19.765 y 21.829 visibles: la diferencia, 28 y 12 filas, son filas con hueco de cargas). El 31 de julio de 2024 la última carga era del 1-jul-2024 (30 días antes) y el 13 % de las filas de la vista final todavía no existía; al 30 de noviembre la vista final difiere de la del corte en 1-2 %. Los montos del primer semestre de 2025 cambian después de la primera carga en 26 % de las filas (5.609 de 21.829 visibles en julio), de modo que `monto_sem1` del punto en el tiempo es una aproximación conservadora.

### 15.3 Cuánto filtra la vista final (D97)

Filas T1 observadas con año de corte 2024 o posterior (8.046 filas: `k = 1`, cohortes 2024 y 2025; `k = 2`, admisiones de segundo semestre de 2023 y de 2024). Mismas definiciones que el §14.2 (gratuidad = códigos `GG_94*` y `GU_00*`; crédito = `C_1_AC` o `C_70_AC`; monto > 0 del primer semestre). Brecha = continúa − no continúa, en puntos porcentuales.

| k | Vista | Grupo | n | Con fila | Con gratuidad | Con crédito | Monto 1.er sem. > 0 |
|---|---|---|---|---|---|---|---|
| 1 | final | Continúa | 5.174 | 74,9 % | 59,7 % | 9,4 % | 74,4 % |
| 1 | final | No continúa | 223 | 53,8 % | 45,7 % | 4,5 % | 53,8 % |
| 1 | final | **Brecha** | | +21,1 pp | +13,9 pp | +4,9 pp | +20,5 pp |
| 1 | punto en el tiempo | Continúa | 5.174 | 66,2 % | 57,4 % | 2,4 % | 66,2 % |
| 1 | punto en el tiempo | No continúa | 223 | 49,3 % | 44,4 % | 1,3 % | 49,3 % |
| 1 | punto en el tiempo | **Brecha** | | +16,9 pp | +13,0 pp | +1,0 pp | +16,9 pp |
| 2 | final | Continúa | 2.376 | 75,3 % | 59,9 % | 10,0 % | 75,3 % |
| 2 | final | No continúa | 273 | 67,4 % | 54,9 % | 5,5 % | 67,4 % |
| 2 | final | **Brecha** | | +7,9 pp | +4,9 pp | +4,5 pp | +7,9 pp |
| 2 | punto en el tiempo | Continúa | 2.376 | 74,7 % | 59,8 % | 9,3 % | 74,6 % |
| 2 | punto en el tiempo | No continúa | 273 | 67,4 % | 54,9 % | 5,5 % | 67,4 % |
| 2 | punto en el tiempo | **Brecha** | | +7,3 pp | +4,9 pp | +3,8 pp | +7,2 pp |

**Lectura.** (i) En `k = 1` la vista final sobrestima la presencia de beneficios en el corte: **74,9 % frente a 66,2 %** de las personas que continúan tienen una fila; el crédito (CAE/FSCU) casi no existe en julio (2,4 % frente a 9,4 %) porque esas filas se cargan más tarde, y la brecha de presencia entre quienes continúan y quienes no baja de 21,1 a 16,9 puntos (la del crédito, de 4,9 a 1,0; la de gratuidad casi no cambia: 13,9 a 13,0). Por año de corte la brecha de presencia pasa de 30,9 a 23,7 puntos en 2024 y de 11,3 a 10,1 en 2025. (ii) En `k = 2` el corte es el cierre del año y las dos vistas casi coinciden (brecha de presencia 7,9 y 7,3 puntos). (iii) **La salida durante el año de ingreso no se explica por filas retiradas:** quienes salen durante el año de ingreso (46 filas de `k = 1` con ingreso en el primer semestre y sin matrícula en el segundo) tienen una fila de beneficios en 2,2 % de los casos **tanto en la vista final como en la del 31 de julio**, frente a 74,7 % y 66,0 % de quienes siguen: no es que la fila se borre después, es que **nunca estuvo en el corte** (el §14.2b atribuía esa diferencia a un efecto retroactivo; el historial de cargas no lo respalda).

### 15.4 P91: ¿por qué se retiran filas? (D97)

Entre 2024 y 2026 (2026 en curso) **2.104 filas** estuvieron en alguna carga y no están en la última. Cada una se clasifica por lo que la misma persona tiene en el mismo programa y año en la vista final:

| Qué tiene la persona después | Filas retiradas | % |
|---|---|---|
| Una fila de la **misma familia** que aparece después del retiro (reemplazo: p. ej. un código preliminar reemplazado por otro) | 668 | 31,7 % |
| Una fila de la misma familia que **ya existía** (coexistía) | 224 | 10,6 % |
| Solo filas de **otras familias** | 561 | 26,7 % |
| **Ninguna fila** en ese año y programa | 651 | 30,9 % |

Por familia, el reemplazo es casi exclusivo de la gratuidad: de 1.173 filas de gratuidad retiradas, 618 (53 %) se reemplazan por otra fila de gratuidad y 89 ya coexistían; en el crédito, las becas y el mérito el reemplazo es raro (1-8 %) y predominan «otras familias» o «ninguna fila». Cruzado con lo que hace la persona (T1, cortes 2024-2025):

| k | Persona | n | No continuidad |
|---|---|---|---|
| 1 | Sin fila retirada | 5.111 | 4,0 % |
| 1 | Retirada y reemplazada por la misma familia | 150 | 8,0 % |
| 1 | Retirada, la misma familia ya existía | 10 | suprimido (n < 30) |
| 1 | Retirada, solo otra familia | 89 | 3,4 % |
| 1 | Retirada y sin filas | 37 | 13,5 % |
| 2 | Sin fila retirada | 2.488 | 10,0 % |
| 2 | Retirada y reemplazada por la misma familia | 97 | 18,6 % |
| 2 | Retirada, la misma familia ya existía | 6 | suprimido (n < 30) |
| 2 | Retirada, solo otra familia | 40 | 5,0 % |
| 2 | Retirada y sin filas | 18 | suprimido (n < 30) |

Entre quienes ingresan en el primer semestre: **1 de 46** de los que salen durante el año tienen una fila retirada (2,2 %), frente a 285 de 5.301 de los que se quedan (5,4 %).

**Hallazgo.** La respuesta de la DAI («ya tendría el beneficio») se cumple para una parte: **42 % de las filas retiradas** (892 de 2.104) tienen otra fila de la misma familia en la vista final (668 la reciben después y 224 ya la tenían), casi toda gratuidad (un código que se reemplaza). El otro **58 %** no tiene sustituto de su familia (561 conservan solo otras familias y 651 quedan sin ninguna fila en el año). El retiro **no es el mecanismo por el cual quienes salen pierden sus filas** (1 de 46). Las personas con una fila retirada y reemplazada muestran más no continuidad que el resto (8,0 % frente a 4,0 % en k = 1 y 18,6 % frente a 10,0 % en k = 2, con 150 y 97 casos), no así quienes solo cambian de familia (3,4 %). «Sin filas» tiene 37 casos en k = 1 (13,5 %) y 18 en k = 2 (suprimido): con tan pocos casos no permite concluir. Es **asociación, no causalidad**, y no responde por qué se anulan los montos del segundo semestre (§14.2c); queda como P96.

### 15.5 T1 con la vista en el punto del tiempo (D98)

**Diseño.** Los modelos son los mismos de la ablación del §14.3 (CatBoost con 3 semillas y logística con C elegido en valid; conjuntos «ingreso + agregados académicos» y «+ beneficios»), **entrenados como allí con la vista final** (cohortes 2015-2019; las cohortes 2015-2016 sin datos de beneficios): no existe historial anterior a 2024, de modo que el **entrenamiento sigue sesgado hacia la vista final** y solo la evaluación usa el punto en el tiempo. El reentrenamiento reproduce los AP de valid del §14.3 (`k = 1`: CatBoost 0,318 sin y 0,331 con beneficios, logística 0,299 y 0,336; `k = 2`: 0,495 y 0,501, 0,501 y 0,509; diferencias < 0,001). Se evalúan las filas observadas con año de corte 2024 o posterior: **5.397 filas, 223 eventos (4,1 %) en `k = 1`** (cohortes 2024: 2.687 y 2025: 2.710) y **2.649 filas, 273 eventos (10,3 %) en `k = 2`** (casi todas con año de corte 2024: 2.601; las de 2025 son 48 porque el resto está censurado). Estas filas quedan **fuera de la ventana oficial de test** (cohortes 2022-2023), de modo que no hay un valid separado: la regla D93 (ΔAP pareado frente al mismo modelo sin beneficios con intervalo sobre 0) se aplica a este mismo conjunto y el veredicto es provisorio. El AP del modelo oficial en estas cohortes (CatBoost 0,227 en `k = 1`; logística 0,534 en `k = 2`) no es comparable con el de la ventana de test (0,360 y 0,537): cambian la cohorte y la tasa de eventos; todas las comparaciones son pareadas dentro del mismo conjunto, con el mismo bootstrap agrupado por persona (1.000 remuestreos) para todos los modelos.

**`k = 1`** (evaluación: n = 5.397, eventos = 223; modelo oficial: CatBoost, ingreso + agregados sin beneficios).

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica (programa, k) | 0,059 [0,047; 0,074] | 0,577 [0,533; 0,616] | 0,0401 [0,0355; 0,0443] | 0,023 [0,019; 0,029] |
| Logística, ingreso + agregados | 0,200 [0,158; 0,255] | 0,836 [0,809; 0,860] | 0,0421 [0,0383; 0,0459] | 0,039 [0,034; 0,045] |
| CatBoost, ingreso + agregados | 0,227 [0,183; 0,287] | 0,848 [0,819; 0,872] | 0,0365 [0,0324; 0,0404] | 0,014 [0,010; 0,020] |
| Logística, + beneficios (vista final) | 0,230 [0,184; 0,289] | 0,850 [0,822; 0,875] | 0,0424 [0,0388; 0,0461] | 0,047 [0,042; 0,052] |
| CatBoost, + beneficios (vista final) | 0,268 [0,214; 0,333] | 0,859 [0,833; 0,882] | 0,0345 [0,0307; 0,0384] | 0,011 [0,008; 0,017] |
| Logística, + beneficios (punto en el tiempo) | 0,225 [0,182; 0,283] | 0,845 [0,816; 0,871] | 0,0428 [0,0391; 0,0465] | 0,048 [0,043; 0,054] |
| CatBoost, + beneficios (punto en el tiempo) | 0,263 [0,212; 0,332] | 0,857 [0,831; 0,882] | 0,0347 [0,0308; 0,0386] | 0,009 [0,007; 0,015] |

Diferencias pareadas:

| Diferencia | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| CatBoost: beneficios en el punto en el tiempo − sin beneficios | +0,036 [+0,015; +0,059] | +0,010 [+0,003; +0,017] | -0,0018 [-0,0027; -0,0008] |
| Logística: beneficios en el punto en el tiempo − sin beneficios | +0,025 [+0,009; +0,044] | +0,009 [-0,002; +0,019] | +0,0007 [-0,0003; +0,0017] |
| CatBoost: beneficios con la vista final − sin beneficios | +0,042 [+0,021; +0,063] | +0,011 [+0,005; +0,018] | -0,0019 [-0,0027; -0,0011] |
| Logística: beneficios con la vista final − sin beneficios | +0,029 [+0,014; +0,047] | +0,013 [+0,005; +0,023] | +0,0003 [-0,0006; +0,0012] |
| CatBoost: punto en el tiempo − vista final | -0,005 [-0,017; +0,006] | -0,001 [-0,003; +0,001] | +0,0001 [-0,0004; +0,0006] |
| Logística: punto en el tiempo − vista final | -0,004 [-0,013; +0,004] | -0,005 [-0,009; -0,000] | +0,0004 [-0,0002; +0,0009] |
| CatBoost, + beneficios (punto en el tiempo) − modelo oficial (CatBoost, ingreso + agregados) | +0,036 [+0,015; +0,059] | +0,010 [+0,003; +0,017] | -0,0018 [-0,0027; -0,0008] |
| Logística, + beneficios (punto en el tiempo) − modelo oficial (CatBoost, ingreso + agregados) | -0,001 [-0,028; +0,025] | -0,003 [-0,018; +0,013] | +0,0063 [+0,0048; +0,0079] |

ΔAP pareado por año de corte (punto en el tiempo − sin beneficios):

| Año de corte | n | Eventos | CatBoost | Logística | CatBoost: punto en el tiempo − vista final |
|---|---|---|---|---|---|
| 2024 | 2.687 | 111 | +0,050 [+0,019; +0,080] | +0,038 [+0,015; +0,064] | -0,006 [-0,023; +0,008] |
| 2025 | 2.710 | 112 | +0,021 [-0,016; +0,052] | +0,009 [-0,023; +0,036] | -0,002 [-0,018; +0,015] |

**Sensibilidad: sin las personas que salen durante el año de ingreso** (se excluyen 46 filas, 37 de ellas con el evento; quedan n = 5.351 y 186 eventos; los modelos son los mismos, solo cambia el conjunto evaluado):

| Diferencia pareada | ΔAP |
|---|---|
| CatBoost: beneficios en el punto en el tiempo − sin beneficios | +0,006 [-0,013; +0,026] |
| Logística: beneficios en el punto en el tiempo − sin beneficios | +0,010 [-0,008; +0,031] |
| CatBoost: beneficios con la vista final − sin beneficios | +0,015 [-0,003; +0,035] |
| Logística: beneficios con la vista final − sin beneficios | +0,015 [-0,002; +0,034] |

**Regla D93 en este conjunto** (ΔAP pareado con intervalo sobre 0 en el conjunto completo y positivo en cada año de corte): CatBoost +0,036 [+0,015; +0,059] → elegible; logística +0,025 [+0,009; +0,044] → elegible.

**`k = 2`** (evaluación: n = 2.649, eventos = 273; modelo oficial: Logística, ingreso + agregados sin beneficios).

| Modelo | AP | ROC-AUC | Brier | ECE |
|---|---|---|---|---|
| Tasa histórica (programa, k) | 0,113 [0,099; 0,132] | 0,550 [0,516; 0,584] | 0,0936 [0,0857; 0,1019] | 0,037 [0,028; 0,048] |
| Logística, ingreso + agregados | 0,534 [0,472; 0,605] | 0,885 [0,858; 0,911] | 0,0761 [0,0690; 0,0829] | 0,080 [0,071; 0,090] |
| CatBoost, ingreso + agregados | 0,529 [0,474; 0,594] | 0,885 [0,859; 0,910] | 0,0638 [0,0573; 0,0699] | 0,022 [0,015; 0,031] |
| Logística, + beneficios (vista final) | 0,547 [0,483; 0,617] | 0,889 [0,863; 0,912] | 0,0790 [0,0720; 0,0859] | 0,090 [0,081; 0,101] |
| CatBoost, + beneficios (vista final) | 0,540 [0,484; 0,605] | 0,887 [0,862; 0,910] | 0,0633 [0,0568; 0,0694] | 0,018 [0,014; 0,029] |
| Logística, + beneficios (punto en el tiempo) | 0,546 [0,480; 0,616] | 0,888 [0,863; 0,912] | 0,0791 [0,0720; 0,0860] | 0,090 [0,081; 0,101] |
| CatBoost, + beneficios (punto en el tiempo) | 0,539 [0,483; 0,604] | 0,887 [0,862; 0,910] | 0,0633 [0,0568; 0,0694] | 0,018 [0,014; 0,029] |

Diferencias pareadas:

| Diferencia | ΔAP | ΔROC-AUC | ΔBrier |
|---|---|---|---|
| CatBoost: beneficios en el punto en el tiempo − sin beneficios | +0,010 [-0,001; +0,021] | +0,002 [-0,001; +0,006] | -0,0005 [-0,0010; -0,0001] |
| Logística: beneficios en el punto en el tiempo − sin beneficios | +0,011 [-0,001; +0,021] | +0,003 [+0,001; +0,006] | +0,0030 [+0,0021; +0,0039] |
| CatBoost: beneficios con la vista final − sin beneficios | +0,011 [-0,000; +0,022] | +0,002 [-0,001; +0,006] | -0,0006 [-0,0010; -0,0001] |
| Logística: beneficios con la vista final − sin beneficios | +0,012 [+0,000; +0,023] | +0,003 [+0,001; +0,006] | +0,0029 [+0,0020; +0,0037] |
| CatBoost: punto en el tiempo − vista final | -0,001 [-0,002; +0,001] | -0,000 [-0,000; +0,000] | +0,0000 [-0,0000; +0,0001] |
| Logística: punto en el tiempo − vista final | -0,001 [-0,003; +0,000] | -0,000 [-0,001; -0,000] | +0,0001 [-0,0000; +0,0004] |
| CatBoost, + beneficios (punto en el tiempo) − modelo oficial (Logística, ingreso + agregados) | +0,005 [-0,026; +0,033] | +0,002 [-0,005; +0,009] | -0,0128 [-0,0163; -0,0093] |
| Logística, + beneficios (punto en el tiempo) − modelo oficial (Logística, ingreso + agregados) | +0,011 [-0,001; +0,021] | +0,003 [+0,001; +0,006] | +0,0030 [+0,0021; +0,0039] |

ΔAP pareado por año de corte (punto en el tiempo − sin beneficios):

| Año de corte | n | Eventos | CatBoost | Logística | CatBoost: punto en el tiempo − vista final |
|---|---|---|---|---|---|
| 2024 | 2.601 | 272 | +0,011 [-0,000; +0,021] | +0,011 [-0,001; +0,022] | -0,001 [-0,002; +0,001] |
| 2025 | 48 | 1 | suprimido (menos de 10 eventos) | suprimido | suprimido |

**Regla D93 en este conjunto** (ΔAP pareado con intervalo sobre 0 en el conjunto completo y positivo en cada año de corte): CatBoost +0,010 [-0,001; +0,021] → no elegible; logística +0,011 [-0,001; +0,021] → no elegible.

**Lectura.**

- **`k = 1`.** Con el punto en el tiempo los beneficios siguen sumando: CatBoost +0,036 [+0,015; +0,059] y logística +0,025 [+0,009; +0,044] sobre el mismo modelo sin beneficios, frente a +0,042 [+0,021; +0,063] y +0,029 [+0,014; +0,047] con la vista final. **Pasar de la vista final a la del corte casi no cambia el desempeño** (CatBoost -0,005 [-0,017; +0,006]; logística -0,004 [-0,013; +0,004]): la hipótesis de que la ganancia del §14.3 era una fuga por filas retiradas retroactivamente **no se sostiene** (§15.3 y §15.4); lo observable al 31 de julio se mantiene.
- **Pero la ganancia está en quienes salen durante el año de ingreso.** Al excluir esas 46 filas (37 eventos, 17 % de los eventos) el ΔAP baja a +0,006 [-0,013; +0,026] (CatBoost) y +0,010 [-0,008; +0,031] (logística), con intervalos que incluyen el cero; con la vista final también (+0,015 [-0,003; +0,035] y +0,015 [-0,002; +0,034]). En esas personas la ausencia de beneficios en julio es una señal fuerte, pero no sabemos si al 31 de julio la salida ya era conocida por la institución (P96); si lo era, la «predicción» describe a alguien que ya se fue.
- Por año, la ganancia de CatBoost es +0,050 [+0,019; +0,080] (2024) y +0,021 [-0,016; +0,052] (2025): no es estable.
- La logística con beneficios no supera al modelo oficial (CatBoost sin beneficios): diferencia -0,001 [-0,028; +0,025].
- **`k = 2`.** El punto en el tiempo y la vista final son equivalentes (diferencia de AP entre -0,001 y 0,000, como se espera al cierre del año) y la ganancia sobre el modelo sin beneficios es pequeña y su intervalo incluye el cero (CatBoost +0,010 [-0,001; +0,021]; logística +0,011 [-0,001; +0,021]): **ningún modelo con beneficios es elegible**, igual que en el §14.3. Las filas con año de corte 2025 son 48 (1 evento) y no aportan.
- Calibración: el CatBoost con beneficios queda tan calibrado como el oficial en ambos cortes (ECE 0,009-0,018); la logística de `k = 2` queda peor calibrada que CatBoost, como el modelo oficial (ECE 0,090 con beneficios y 0,080 sin ellos).

### 15.6 Por programa y por facultad (punto en el tiempo; D98)

Modelo con beneficios en el punto en el tiempo y mayor AP de cada corte (CatBoost en `k = 1`; logística en `k = 2`) frente al modelo oficial sin beneficios. Mismas reglas de supresión que T4 y T5 (D89): solo se listan los grupos con **n ≥ 100 y al menos 10 eventos**; los demás se cuentan y no se muestran (lo que deja fuera también todo grupo con n < 10).

**`k = 1`, por facultad.** Se listan 10 de 13 grupos (4.877 de 5.397 filas); 3 se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio con beneficios | Riesgo medio oficial | Brecha con beneficios (predicho − observado) | AP con beneficios | AP oficial |
|---|---|---|---|---|---|---|---|---|
| Escuela de Arquitectura | 165 | 15 | 9,1 % | 6,6 % | 7,0 % | -0,025 [-0,068; +0,012] | 0,373 | 0,371 |
| Escuela de Ciencias Empresariales | 406 | 14 | 3,4 % | 4,7 % | 4,9 % | +0,012 [-0,004; +0,027] | 0,486 | 0,370 |
| Escuela de Ingeniería | 644 | 21 | 3,3 % | 4,1 % | 4,2 % | +0,008 [-0,005; +0,020] | 0,380 | 0,253 |
| Facultad de Ciencias | 293 | 12 | 4,1 % | 5,0 % | 5,9 % | +0,009 [-0,012; +0,028] | 0,402 | 0,406 |
| Facultad de Ciencias Jurídicas | 503 | 26 | 5,2 % | 4,3 % | 4,6 % | -0,008 [-0,027; +0,008] | 0,341 | 0,244 |
| Facultad de Ciencias del Mar | 208 | 17 | 8,2 % | 8,8 % | 11,0 % | +0,006 [-0,030; +0,041] | 0,314 | 0,302 |
| Facultad de Economía y Administración | 479 | 14 | 2,9 % | 4,7 % | 5,0 % | +0,018 [+0,003; +0,032] | 0,165 | 0,134 |
| Facultad de Educación | 401 | 11 | 2,7 % | 2,9 % | 3,1 % | +0,002 [-0,014; +0,016] | 0,155 | 0,149 |
| Facultad de Ingeniería y Ciencias Geológicas | 1.422 | 66 | 4,6 % | 5,4 % | 5,6 % | +0,008 [-0,003; +0,017] | 0,214 | 0,192 |
| Facultad de Medicina | 356 | 11 | 3,1 % | 3,0 % | 4,1 % | -0,001 [-0,018; +0,014] | 0,421 | 0,302 |

Error absoluto medio ponderado de la tasa del grupo: con beneficios 0,009 [0,007; 0,015], oficial 0,012 [0,008; 0,018], diferencia -0,003 [-0,004; -0,000].

**`k = 1`, por programa.** Se listan 4 de 51 grupos (764 de 5.397 filas); 47 se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio con beneficios | Riesgo medio oficial | Brecha con beneficios (predicho − observado) | AP con beneficios | AP oficial |
|---|---|---|---|---|---|---|---|---|
| 8213 ARQUITECTURA | 165 | 15 | 9,1 % | 6,6 % | 7,0 % | -0,025 [-0,068; +0,012] | 0,373 | 0,371 |
| 8376 DERECHO | 264 | 17 | 6,4 % | 3,6 % | 4,1 % | -0,028 [-0,055; -0,003] | 0,416 | 0,243 |
| 8456 BIOLOGÍA MARINA | 112 | 12 | 10,7 % | 8,8 % | 10,8 % | -0,019 [-0,074; +0,031] | 0,437 | 0,457 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 223 | 15 | 6,7 % | 6,1 % | 6,1 % | -0,006 [-0,036; +0,024] | 0,368 | 0,336 |

Error absoluto medio ponderado de la tasa del grupo: con beneficios 0,020 [0,010; 0,038], oficial 0,015 [0,008; 0,034], diferencia +0,005 [-0,003; +0,008].

**`k = 2`, por facultad.** Se listan 8 de 13 grupos (2.199 de 2.649 filas); 5 se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio con beneficios | Riesgo medio oficial | Brecha con beneficios (predicho − observado) | AP con beneficios | AP oficial |
|---|---|---|---|---|---|---|---|---|
| Escuela de Ciencias Empresariales | 201 | 15 | 7,5 % | 17,1 % | 16,1 % | +0,096 [+0,066; +0,127] | 0,518 | 0,541 |
| Escuela de Ingeniería | 323 | 20 | 6,2 % | 15,6 % | 14,8 % | +0,094 [+0,071; +0,117] | 0,586 | 0,541 |
| Facultad de Ciencias | 147 | 16 | 10,9 % | 21,4 % | 20,1 % | +0,105 [+0,066; +0,144] | 0,699 | 0,719 |
| Facultad de Ciencias Jurídicas | 246 | 30 | 12,2 % | 22,0 % | 20,8 % | +0,098 [+0,060; +0,134] | 0,502 | 0,488 |
| Facultad de Economía y Administración | 249 | 30 | 12,0 % | 18,6 % | 17,6 % | +0,066 [+0,029; +0,102] | 0,505 | 0,470 |
| Facultad de Educación | 174 | 17 | 9,8 % | 9,8 % | 9,1 % | +0,001 [-0,032; +0,035] | 0,571 | 0,535 |
| Facultad de Ingeniería y Ciencias Geológicas | 671 | 83 | 12,4 % | 24,8 % | 23,3 % | +0,124 [+0,101; +0,148] | 0,519 | 0,501 |
| Facultad de Medicina | 188 | 10 | 5,3 % | 9,0 % | 8,5 % | +0,037 [+0,018; +0,055] | 0,892 | 0,856 |

Error absoluto medio ponderado de la tasa del grupo: con beneficios 0,089 [0,079; 0,101], oficial 0,079 [0,069; 0,090], diferencia +0,010 [+0,009; +0,012].

**`k = 2`, por programa.** Se listan 5 de 48 grupos (614 de 2.649 filas); 43 se suprimen.

| Grupo | n | Eventos | Tasa observada | Riesgo medio con beneficios | Riesgo medio oficial | Brecha con beneficios (predicho − observado) | AP con beneficios | AP oficial |
|---|---|---|---|---|---|---|---|---|
| 8323 INGENIERÍA COMERCIAL | 140 | 15 | 10,7 % | 17,0 % | 15,9 % | +0,063 [+0,013; +0,112] | 0,467 | 0,403 |
| 8326 INGENIERÍA COMERCIAL | 117 | 10 | 8,5 % | 16,7 % | 15,7 % | +0,081 [+0,036; +0,122] | 0,458 | 0,505 |
| 8376 DERECHO | 128 | 22 | 17,2 % | 20,3 % | 19,2 % | +0,031 [-0,027; +0,083] | 0,631 | 0,614 |
| 8603 INGENIERÍA CIVIL EN COMPUTACIÓN E INFORMÁTICA | 107 | 17 | 15,9 % | 34,9 % | 33,2 % | +0,191 [+0,116; +0,261] | 0,428 | 0,422 |
| 8613 INGENIERÍA CIVIL INDUSTRIAL | 122 | 10 | 8,2 % | 11,2 % | 10,2 % | +0,030 [-0,013; +0,067] | 0,687 | 0,677 |

Error absoluto medio ponderado de la tasa del grupo: con beneficios 0,076 [0,056; 0,098], oficial 0,064 [0,047; 0,087], diferencia +0,012 [+0,005; +0,013].

Por facultad los modelos con y sin beneficios predicen casi lo mismo (riesgo medio dentro de 2,2 puntos) y el error absoluto ponderado mejora apenas en `k = 1` (-0,003 [-0,004; -0,000]) y empeora en `k = 2` (+0,010 [+0,009; +0,012]: la logística sobrestima el riesgo en casi todas las facultades, como el modelo oficial). Con 4-5 programas listables y 10-22 eventos por grupo, las diferencias de AP entre grupos no son interpretables; se informan por completitud.

### 15.7 Conclusión y límites (D99)

1. **Configuración oficial de T1 (`k = 1, 2`): sin cambios**; el hash de datos de las filas oficiales no cambia (no se tocó el snapshot).
2. **Fuga de la vista final.** En `k = 1` la vista final sobrestima la presencia de beneficios al corte (74,9 % frente a 66,2 % de las personas que continúan), sobre todo por el crédito, que se carga tarde; la brecha de presencia entre quienes continúan y quienes no baja de 21,1 a 16,9 puntos. En `k = 2` las dos vistas coinciden (7,9 y 7,3 puntos). La explicación del §14.2b (filas retiradas retroactivamente para quienes salen) **no se confirma**: quienes salen durante el año no tenían fila en el corte (1 de 46 con fila retirada).
3. **¿Se pueden reconsiderar los beneficios en `k = 1`?** Sí como línea de trabajo, no todavía como cambio oficial. Con el punto en el tiempo los beneficios agregan +0,036 [+0,015; +0,059] de AP a CatBoost (cohortes 2024-2025) y la regla D93 se cumple formalmente en el conjunto completo; no se adoptan porque (a) la ganancia desaparece al excluir a quienes salen durante el año de ingreso (+0,006 [-0,013; +0,026]), cuya salida podría ser conocida al corte (P96); (b) en 2025 por sí sola el intervalo incluye el cero (+0,021 [-0,016; +0,052]); (c) el entrenamiento sigue en la vista final (sin historial anterior a 2024, P93) y la evaluación está fuera de la ventana oficial y sin valid propio; (d) las cohortes 2024-2025 tienen un nivel de AP distinto del de test y la fuente depende de una política de beneficios que podría cambiar (P93). **En `k = 2` no se adoptan** (ΔAP +0,010 [-0,001; +0,021]).
4. **Qué falta para decidir.** (i) La respuesta de la DAI sobre la fecha en que queda registrada la salida de quienes dejan el año de ingreso (P96); (ii) reentrenar con el punto en el tiempo cuando haya más años de historial (2026 completo; la cohorte 2026 de `k = 1` tendrá etiqueta en octubre de 2027); (iii) un hold-out prospectivo y no la reutilización de las cohortes 2024-2025; (iv) confirmar con la DAI por qué los montos del primer semestre cambian después de la primera carga (P97), porque limitan `monto_sem1` en el punto en el tiempo.
5. **Límites.** El historial empieza en 2024 (2017-2023 llegaron de una vez); `monto_sem1` usa el monto de la primera carga (26 % de las filas de 2025 lo cambian después); las filas con hueco de cargas (33-168 por año y corte) se tratan como presentes; el corte del 31 de julio usa la última carga anterior (30 días antes en 2024); solo hay 46 personas que salen durante el año de ingreso, 37 de ellas con el evento, por lo que su efecto se estima con poca precisión; las cohortes 2024-2025 no son la ventana de test del resto de T1.

### 15.8 Actualización: salidas registradas al corte (P96) y montos corregidos (P97; D110, D111)

**P96.** La DAI confirma que los estados académicos se registran en el momento y quedan en el `sorlcur`. En `snapshot_t1` (filas observadas) solo 2 de las 223 no continuidades de `k = 1` con corte desde 2024 tienen un estado de salida en un período ≤ el del corte (test: 0 de 280). La salida de quienes dejan la universidad durante el año de ingreso es una no matrícula posterior y **no era conocida al corte**: la ausencia de beneficios al 31 de julio es una señal disponible en ese momento (D110). La objeción (a) del §15.7 se levanta.

**P97.** La DAI indica que los montos cambian después de la primera carga porque se corrigen subidas fallidas, y que los montos actuales son los correctos. Variación del monto del 1.er semestre entre la primera y la última carga:

| Año | Sin cambio | ≤ 10 % | 10-50 % | 50-90 % | ≥ 90 % (casi todo de o hacia cero) |
|---|---|---|---|---|---|
| 2024 | 21.617 | 354 | 563 | 256 | 210 |
| 2025 | 18.043 | 895 | 4.574 | 215 | 127 |
| 2026 | 23.917 | 62 | 296 | 112 | 41 |

En 2025, 5.177 filas bajaron con una razón mediana de 0,805 (p10 0,750; p90 0,958), y el 97 % había entrado en una misma carga: es la subida fallida corregida después. Un umbral del 90 % por sí solo no la detecta. **Regla aplicada (D111):** `monto_sem1` usa el monto de la **última carga** (corregido); si el monto varía un 90 % o más entre la primera y la última carga (normalmente de o hacia cero, que puede ser una pérdida u obtención real), el corte queda sin monto (NaN, imputado por la mediana en la logística). La presencia de beneficios no cambia. Es una excepción deliberada a la prueba de perturbación: una corrección arregla el mismo hecho y no informa sobre lo que ocurre después del corte.

**Resultados con la regla D111** (mismo conjunto del §15.5; bootstrap pareado por persona, 1.000 remuestreos). Las cifras del §15.5 y las tablas del §15.6 corresponden a los montos de la primera carga; las vigentes están en `artefactos/resultados_t1_beneficios_cargas.json`.

| ΔAP pareado frente al mismo modelo sin beneficios | Con montos de la primera carga (§15.5) | Con montos corregidos (D111) |
|---|---|---|
| `k = 1` CatBoost, conjunto completo | +0,036 [+0,015; +0,059] | **+0,043 [+0,024; +0,064]** |
| `k = 1` CatBoost, 2024 | +0,050 [+0,019; +0,080] | +0,047 [+0,018; +0,075] |
| `k = 1` CatBoost, 2025 | +0,021 [-0,016; +0,052] | **+0,043 [+0,011; +0,070]** |
| `k = 1` logística, conjunto completo | +0,025 [+0,009; +0,044] | +0,027 [+0,011; +0,044] |
| `k = 1` CatBoost, sin quienes salen durante el año de ingreso | +0,006 [-0,013; +0,026] | +0,016 [-0,001; +0,035] |
| `k = 2` CatBoost | +0,010 [-0,001; +0,021] | +0,011 [-0,001; +0,022] |
| `k = 2` logística | +0,011 [-0,001; +0,021] | +0,011 [-0,001; +0,022] |

**Lectura.** Con los montos corregidos la ganancia de `k = 1` es mayor y positiva con intervalo sobre cero **en cada año**, incluido 2025, donde estaba la subida fallida. La objeción (b) del §15.7 se levanta. La ganancia sigue concentrada en parte en quienes salen durante el año de ingreso, pero esa señal es legítima (P96). En `k = 2` no hay ganancia.

**Estado.** Los beneficios quedan como **candidatos** en `k = 1` (D110, D111). Siguen pendientes las objeciones (c) y (d) del §15.7: el entrenamiento usa la vista final (sin historial anterior a 2024) y el conjunto de evaluación es el mismo en que se aplica D93, sin valid propio. La configuración oficial de T1 no cambia hasta que se decida su adopción.

### 15.9 Validación propia: 2024 como valid, 2025 como test (D112)

Para aplicar D93 con un conjunto de selección distinto del de confirmación, se separan las filas del §15.8 por año de corte: **2024 = valid** (2.687 filas, 111 eventos) y **2025 = test** (2.710 filas, 112 eventos). Los modelos son los mismos (entrenados en la ventana oficial con la vista final; montos corregidos, D111); no se reentrena nada. Bootstrap pareado por persona, 1.000 remuestreos.

**Selección en valid (2024).**

| Modelo | AP | ROC-AUC | Brier | ECE | ΔAP frente al mismo modelo sin beneficios | ¿Elegible (D93)? |
|---|---|---|---|---|---|---|
| CatBoost académico (oficial) | 0,259 [0,200; 0,338] | 0,902 | 0,036 | 0,017 | — | — |
| **CatBoost + beneficios** | **0,306 [0,242; 0,399]** | 0,912 | 0,033 | 0,015 | +0,047 [+0,018; +0,075] | Sí |
| Logística académica | 0,200 [0,157; 0,264] | 0,882 | 0,043 | 0,045 | — | — |
| Logística + beneficios | 0,236 [0,184; 0,308] | 0,892 | 0,043 | 0,055 | +0,036 [+0,013; +0,060] | Sí |

Ambos modelos con beneficios son elegibles; se conserva el de mayor AP en valid: **CatBoost + beneficios**.

**Confirmación en test (2025)**, frente al oficial (CatBoost académico):

| Métrica | CatBoost académico | CatBoost + beneficios | Diferencia pareada |
|---|---|---|---|
| AP | 0,205 [0,144; 0,289] | 0,248 [0,177; 0,335] | **+0,043 [+0,011; +0,070]** |
| ROC-AUC | 0,793 | 0,807 | +0,014 [+0,003; +0,027] |
| Brier | 0,037 | 0,036 | −0,002 [−0,003; −0,001] |
| ECE | 0,017 | 0,014 | −0,003 [−0,007; +0,001] |
| Recall en el 10 % de mayor riesgo | 0,446 | 0,446 | 0,000 [−0,040; +0,044] |

**Lectura.** El modelo elegido en 2024 se confirma en 2025: mejora el AP, el AUC y el Brier con intervalos que excluyen el cero, sin empeorar la calibración. La ganancia no cambia cuántos casos captura el 10 % de mayor riesgo; mejora el orden fuera de ese tramo y la calibración.

**Límites.** (1) El entrenamiento sigue en la vista final (sin historial anterior a 2024, P93), aunque se evalúa con la vista del corte. (2) Cada año tiene unos 110 eventos, por lo que los intervalos son anchos. (3) Las variables con punto en el tiempo solo existen desde 2024: el benchmark histórico de T1 (test 2022-2023, AP 0,360) sigue siendo solo académico y no es comparable con estas cifras. (4) En `k = 2` el conjunto es casi solo 2024 (2.601 de 2.649 filas), así que no se puede separar valid y test; ahí no se adoptan.

**Decisión de la DAI (16-11-2026, D113): adoptado.** CatBoost + beneficios (vista en el punto del tiempo D96, montos corregidos D111) es el modelo oficial de `k = 1` para las cohortes desde 2024. El benchmark histórico (test 2022-2023, solo académico) se mantiene como referencia. `k = 2` sigue con la logística académica.

Reproducción: `python -m pipelines.migrate`; `python -m pipelines.extract --only banner_beneficios_cargas,banner_beneficios_cargas_cal`; `python -m evaluation.diagnostico_beneficios_cargas`; `python -m evaluation.run_beneficios_cargas_t1` (salidas agregadas en `artefactos/diagnostico_beneficios_cargas_t1.json` y `artefactos/resultados_t1_beneficios_cargas.json`, fuera del repositorio). Pruebas: `tests/unit/test_beneficios_cargas.py`, `tests/unit/test_run_beneficios_cargas_t1.py`. Evidencia: `evidencia/beneficios_cargas_2026-11-16.md`.


## 16. Variables nuevas pedidas por la DAI (18-11-2026)

La DAI pidió agregar a T1 variables que el estudio de viabilidad (`evidencia/viabilidad_variables_2026-11-18.md`, P117–P127) encontró factibles con las fuentes ya extraídas. Se construyen en el punto del tiempo del corte `k`, se reevalúan con la regla única de selección (D114: se elige en **validación** con AP; un candidato reemplaza al modelo conservado solo si la diferencia pareada en validación, con bootstrap agrupado por persona, tiene un IC de 95 % que excluye 0 a su favor; ante empate gana el más simple; la prueba solo confirma) y **ninguna cambia el modelo conservado**. La configuración oficial, las predicciones guardadas y los hashes de los modelos conservados no cambian.

### 16.1 Variables (18 columnas nuevas de `snapshot_t1`, migración 030)

`j` es el semestre contado desde el ingreso; el corte es `k`. Código: `pipelines/snapshots/features_t1_nuevas.py`; el atraso curricular usa `pipelines/snapshots/malla_avance.py`, que copia la lógica mínima de `features_t3.features_programa` (sin editarla) y tiene una prueba que exige valores idénticos.

| Bloque | Variable | Definición |
|---|---|---|
| Rendimiento | `creditos_aprob_ult_sem` | Créditos aprobados por primera vez en el semestre `k` (no el acumulado). |
| | `delta_promedio_sem` | Promedio del semestre `k` menos el del semestre `k − 1` (vacío en `k` = 1). |
| | `delta_promedio_acum` | Promedio del semestre `k` menos el promedio acumulado de los semestres `< k`. |
| Oportunidades | `repro_oport2`, `repro_oport3` | Intentos evaluados reprobados con `oportunidad` ≥ 2 y ≥ 3 en los semestres `≤ k`. |
| | `ramos_repetidos` | Ramos distintos con algún intento de `oportunidad` ≥ 2 en los semestres `≤ k`. |
| | `n_sem_sin_reprob` | Semestres `≤ k` sin reprobaciones registradas (201920 y 202010; P58). |
| Malla | `creditos_esperados`, `avance_malla`, `fraccion_malla` | Como en T3: créditos de la malla del catálogo inicial hasta el semestre `k`; aprobados sobre esperados y sobre el total de la malla. |
| Carga | `ramos_ins_ult`, `creditos_ins_ult` | Intentos del semestre `k` que no son convalidaciones (los retirados cuentan: estaban inscritos) y sus créditos. |
| | `delta_ramos_ins`, `delta_creditos_ins` | Cambio frente al semestre `k − 1`. |
| Retiros | `n_retiro_temporal`, `n_anulacion` | Períodos distintos hasta el corte con estado `P` (retiro temporal) o `A` (anulación). |
| | `sem_desde_ultimo_retiro` | `k` menos el semestre del último `P` o `A` (vacío si no hay). |
| | `dias_desde_ultimo_retiro` | Días entre la fecha del último `P` o `A` (`fecha_estado`) y el fin del período de corte (vacío sin fecha o con fecha marcador futura). |

**Punto en el tiempo.** Cada valor sale de hechos de los semestres `≤ k` y de estados del episodio con `periodo ≤ periodo_corte` cuya fecha, si existe, no es posterior al fin de ese período (31 de julio para `AAAA10`; último día de febrero siguiente para `AAAA20`, como `periodo_de_fecha`). Un retiro registrado en el período pero fechado después del fin del período no se conoce al corte y no cuenta. Pruebas (`tests/unit/test_features_t1_nuevas.py`): cambiar o borrar cualquier intento o estado posterior al corte deja las 18 columnas iguales, para `k` = 1, 2 y 3; los estados de corrección del sistema no cuentan; los semestres sin reprobaciones registradas (P58) se cuentan en `n_sem_sin_reprob` y, como `reprobados`, subestiman las reprobaciones en esos cortes (6,3 % de las filas observadas de `k` = 1 y 20,8 % de `k` = 2 tienen al menos uno). La malla es estática.

**Cobertura (filas observadas de train, valid y test).** `k` = 1: 0,3 % con alguna reprobación en 2.ª oportunidad, 0,6 % con algún ramo repetido, 0,18 % con un retiro temporal y 1,47 % con una anulación antes del corte, malla conocida en 97,4 %; los deltas de promedio no existen (no hay semestre previo). `k` = 2: 14,2 %, 33,1 %, 0,14 % y 4,73 %, malla conocida en 99,9 %, deltas de promedio en 88,3 %. En `k` = 1 casi todas las variables nuevas coinciden con las que ya existen (el último semestre es el acumulado) o valen cero.

### 16.2 Resultados (D114)

Misma ventana de entrenamiento oficial (cohortes desde 2015), mismos modelos y semillas que el §5. El conservado se reentrena en esta corrida y reproduce el §12 (AP en valid 0,318 en `k` = 1 y 0,501 en `k` = 2; en test 0,360 y 0,537).

**`k` = 1** (valid 4.192 filas y 197 eventos; test 4.934 filas y 280 eventos; entrenamiento 12.012 filas).

| Modelo | AP valid | ΔAP valid frente al conservado | ROC-AUC valid | Brier valid | AP test | ΔAP test | ROC-AUC test | Brier test |
|---|---|---|---|---|---|---|---|---|
| CatBoost académico (conservado) | 0,318 [0,261; 0,388] | — | 0,856 | 0,0381 | 0,360 [0,303; 0,418] | — | 0,857 | 0,0441 |
| CatBoost + variables nuevas | 0,322 [0,268; 0,392] | +0,004 [−0,012; +0,020] | 0,852 | 0,0377 | 0,348 [0,290; 0,404] | −0,013 [−0,025; −0,001] | 0,855 | 0,0447 |
| Logística + variables nuevas | 0,313 [0,254; 0,381] | −0,005 [−0,039; +0,027] | 0,809 | 0,0389 | 0,287 [0,237; 0,348] | −0,074 [−0,102; −0,040] | 0,837 | 0,0466 |

D114 (valid, AP, IC pareado agrupado por persona): se conserva → **cb_acad**. lr_nuevas −0,005 [−0,039; +0,027]; cb_nuevas +0,004 [−0,012; +0,020].

**`k` = 2** (valid 4.061 filas y 464 eventos; test 4.719 filas y 499 eventos; entrenamiento 11.247 filas).

| Modelo | AP valid | ΔAP valid frente al conservado | ROC-AUC valid | Brier valid | AP test | ΔAP test | ROC-AUC test | Brier test |
|---|---|---|---|---|---|---|---|---|
| Logística académica (conservado) | 0,501 [0,454; 0,552] | — | 0,857 | 0,0742 | 0,537 [0,494; 0,584] | — | 0,893 | 0,0717 |
| Logística + variables nuevas | 0,505 [0,458; 0,556] | +0,004 [−0,012; +0,019] | 0,860 | 0,0740 | 0,492 [0,446; 0,540] | −0,045 [−0,069; −0,023] | 0,887 | 0,0697 |
| CatBoost + variables nuevas | 0,502 [0,456; 0,556] | +0,002 [−0,019; +0,025] | 0,852 | 0,0755 | 0,541 [0,495; 0,587] | +0,003 [−0,024; +0,031] | 0,888 | 0,0639 |

D114 (valid, AP, IC pareado agrupado por persona): se conserva → **lr_acad**. lr_nuevas +0,004 [−0,012; +0,019]; cb_nuevas +0,002 [−0,019; +0,025].

**Lectura.** Ningún candidato tiene un IC pareado en validación que excluya 0 a su favor, ni en `k` = 1 ni en `k` = 2: se conservan CatBoost académico (`k` = 1) y la logística académica (`k` = 2). La prueba no contradice la decisión y en `k` = 1 la empeora (CatBoost con variables nuevas −0,013 de AP, IC que excluye 0; la logística −0,074). En `k` = 2 la logística pierde 0,045 de AP en prueba al agregar las variables (ROC-AUC −0,006), señal de sobreajuste a validación con variables ruidosas o poco frecuentes.

### 16.3 Bloques (diagnóstico)

Cada bloque se agrega por separado al conjunto académico. Es solo diagnóstico: con 10 candidatos por `k` el mejor de ellos sobreestima su ganancia (efecto de elegir el máximo), por eso la decisión usa solo el conjunto completo.

AP en valid y ΔAP pareado frente al conservado.

| Bloque | `k` = 1 CatBoost | `k` = 1 logística | `k` = 2 CatBoost | `k` = 2 logística |
|---|---|---|---|---|
| rendimiento | 0,315 (−0,003 [−0,014; +0,007]) | 0,300 (−0,018 [−0,047; +0,009]) | 0,498 (−0,003 [−0,027; +0,022]) | 0,508 (+0,007 [−0,003; +0,018]) |
| oportunidades | 0,328 (+0,010 [−0,002; +0,022]) | 0,307 (−0,011 [−0,043; +0,019]) | 0,499 (−0,001 [−0,022; +0,020]) | 0,499 (−0,002 [−0,016; +0,012]) |
| malla | 0,331 (+0,013 [−0,001; +0,025]) | 0,303 (−0,016 [−0,045; +0,010]) | 0,497 (−0,004 [−0,025; +0,018]) | 0,501 (+0,001 [−0,003; +0,004]) |
| carga | 0,317 (−0,001 [−0,012; +0,011]) | 0,301 (−0,018 [−0,046; +0,011]) | 0,489 (−0,011 [−0,030; +0,011]) | 0,493 (−0,008 [−0,013; −0,002]) |
| retiros | 0,315 (−0,003 [−0,016; +0,011]) | 0,301 (−0,018 [−0,047; +0,010]) | 0,490 (−0,010 [−0,034; +0,014]) | 0,504 (+0,004 [−0,001; +0,008]) |

El mayor aporte puntual es la malla y las oportunidades en CatBoost de `k` = 1 (+0,013 y +0,010 de AP), con IC que incluyen 0; en prueba ninguno supera al conservado (malla −0,001 [−0,010; +0,007]).

### 16.4 Cohortes desde 2024 (CatBoost + beneficios, D113)

Se repite D112 con las variables nuevas añadidas al modelo de beneficios en el punto del tiempo (valid = corte 2024, test = corte 2025).

(valid = corte 2024: 2.687 filas y 111 eventos; test = corte 2025: 2.710 filas y 112 eventos).

| Modelo | AP valid | ΔAP valid frente a CatBoost + beneficios | AP test | ΔAP test | ROC-AUC test | Brier test |
|---|---|---|---|---|---|---|
| CatBoost + beneficios (conservado, D113) | 0,306 [0,242; 0,397] | — | 0,248 [0,177; 0,330] | — | 0,807 | 0,0357 |
| CatBoost + beneficios + variables nuevas | 0,290 [0,229; 0,378] | −0,017 [−0,036; −0,000] | 0,245 [0,174; 0,327] | −0,003 [−0,018; +0,013] | 0,798 | 0,0360 |
| Logística + beneficios + variables nuevas | 0,213 [0,168; 0,276] | −0,093 [−0,142; −0,054] | 0,236 [0,167; 0,315] | −0,012 [−0,040; +0,019] | 0,809 | 0,0368 |

CatBoost + beneficios + variables nuevas queda por debajo del conservado en validación (−0,017 [−0,036; −0,000]) y sin diferencia en prueba: se conserva CatBoost + beneficios (D113).

### 16.5 Conclusión y límites

1. **Sin cambio de modelo en T1.** Las variables nuevas no mejoran el AP de validación con IC que excluya 0 en ninguna configuración (`k` = 1, `k` = 2, cohortes desde 2024). Se publican como columnas del snapshot para futuras reevaluaciones, pero no entran a ningún modelo oficial.
2. **Por qué es esperable.** En `k` = 1 solo hay un semestre: el semestre previo, los deltas y buena parte de la carga no existen o repiten el acumulado. En `k` = 2 el conjunto académico ya incluye la tasa y el promedio del último semestre. Las reprobaciones en 2.ª y 3.ª oportunidad (14 % y 0,3 % de las filas de `k` = 2) y los retiros `P`/`A` son poco frecuentes antes del corte `k` ≤ 2; podrían pesar más en `k` = 4 (29 % con reprobación en 2.ª oportunidad, 5,5 % en la 3.ª), que no es la configuración oficial.
3. **Límites.** (i) La unidad de los créditos sigue sin confirmar (P126), por lo que `creditos_esperados` y `avance_malla` comparten esa incertidumbre. (ii) Las fechas de `P`/`A` ausentes se imputan en el núcleo (P44); aquí se tratan como desconocidas para los días, no para los conteos. (iii) Los retiros de ramos (`RENUNCIADA`) solo existen desde 2025 (P12, P53); antes, la carga solo ve intentos evaluados o con resultado. (iv) `oportunidad` = 0 (4 filas desde 2015) se trata como primera oportunidad. (v) El snapshot no es bit a bit determinista en `promedio_evaluado` y `promedio_ult_semestre` (el orden de lectura de la base cambia el último decimal de la suma); no afecta a ninguna decisión.
4. **Reproducción.** `python -m pipelines.migrate` (030), `python -m pipelines.snapshots.t1` (el hash de datos de los `k` oficiales no cambia: `28ac6287…cff75`), `python -m evaluation.run_nuevas_t1` (salidas agregadas en `artefactos/resultados_t1_nuevas.json` y predicciones en `artefactos/preds/t1_nuevas_*.npz`, fuera del repositorio). Pruebas: `tests/unit/test_features_t1_nuevas.py`, `tests/unit/test_run_nuevas_t1.py`.
