# DAI Neural — Benchmark T6: matrícula en postgrado UCN después del egreso

**Versión:** 0.2 · 13-11-2026 (reconstrucción consolidada, etapa B: evento por la fuente de estados de postgrado P86, variables `mm_*`, viabilidad D68 revisada) · 0.1 · 13-11-2026 · Fase 4, benchmark T6. Base: `PROMPT_MAESTRO.md` (secciones «Predicción experimental», «Evaluación» y «Fase 4»), `00_plan.md` (D22, D40–D47, D53–D63, D64–D71 y D81–D88), `10_benchmark_t3.md` (población y atributos) y `11_benchmark_t4_t5.md` (evaluación por programa y facultad). Versión del código: `{{meta:version_codigo}}`; huella de los datos del snapshot: `{{meta:snapshot_hash}}`.
**Estado:** informe técnico completo; **el uso de predicciones individuales no está aprobado** (Gate 4). Solo agregados: ninguna fila individual, RUT ni predicción por persona figura en este documento ni en el repositorio; las predicciones viven en `artefactos/preds/` (ignorado por git). Solo se observa la **matrícula en postgrado de la UCN**: este informe no dice nada sobre estudios de postgrado en otras instituciones y no estima una probabilidad de postgrado fuera de la UCN.

## 1. Definición de la tarea

**T6, «matrícula en postgrado UCN».** Dada una trayectoria de pregrado que llegó al egreso, ¿cuánto tiempo pasa hasta que la misma persona se matricula por primera vez en un programa de postgrado de la UCN? Se estudia como **supervivencia con censura administrativa** (incidencia acumulada a 1, 2 y 4 años) y como **clasificación binaria en cada horizonte** donde el seguimiento está completo.

| Elemento | Definición |
|---|---|
| Unidad | Una **trayectoria de pregrado de T3** (`id_nivel` 1; sin admisiones `IN`, `PE`, `IE`; cohortes 2015 o posteriores; sin los programas de Intercambio; Ingeniería Civil Plan Común unido a su especialidad: D47) que **llegó al egreso** (estado de egreso o titulación, o fila de `titulacion` vinculada: el evento de T3, D46) en un período regular cerrado (D64). |
| Corte | El **semestre del egreso** (`k` = su posición desde la admisión). Todos los atributos son hechos de los semestres `≤ k`. |
| Evento | La **primera matrícula** de la misma persona en cualquier programa de postgrado de la UCN, medida con el estado **`M` (matriculado)** de la fuente de estados de postgrado (`neural_core.estado_postgrado`, de `ban_estados_academicos_pos`), en un semestre posterior al del egreso (D65, P86). Es la fuente de referencia de la DAI y reemplaza como evento principal al `estado_matricula = MATRICULADO` de `matricula_postgrado`, que queda como sensibilidad (§4). La fuente trae el nombre del programa, de donde se deriva el **nivel** (magíster, doctorado, otro: P77). |
| Tiempo | Semestres calendario después del egreso. `AAAA50` cae en el primer semestre del año (como `AAAA10`) y `AAAA60` en el segundo (como `AAAA20`) (D66). |
| Censura | Administrativa, en el último período regular cerrado (`{{meta:cierre}}`, equivalente a `202650` en postgrado). Una matrícula en un período todavía abierto (`202660`) no es evento. |
| Horizontes | 2, 4 y 8 semestres (1, 2 y 4 años). El horizonte de 1 año se agregó porque es el único con seguimiento completo en las tres particiones. |
| Exclusión | Las personas con una matrícula de postgrado UCN **antes del ingreso, durante el pregrado o en el semestre del egreso** (en cualquiera de las dos fuentes) no están en riesgo de una *primera* matrícula posterior: se excluyen y se cuentan (§2). Con el evento principal se excluyen además {{x:unidades_excluidas_previo_estados}} unidades con matrícula previa en la fuente de estados (D65). |
| Partición | Por **año de egreso**, fuera de tiempo: train 2022 o antes, valid 2023, test 2024 o después (D67). |
| Variables | Perfil de ingreso (puntajes normalizados `mm_*` y la prueba de admisión `prueba_admision`), programa en vigor y su facultad, trayectoria académica robusta a P58 hasta el egreso, tiempo hasta el egreso frente a la duración nominal y si hay una titulación `U` conocida al corte. **Nunca** `sexo` (solo equidad), `cohorte_anio`, el año de egreso ni nada posterior al corte. |

## Resumen de resultados

1. **Población.** De {{n:embudo.poblacion}} trayectorias de T3, {{n:embudo.egresados}} llegaron al egreso; tras excluir las que tienen matrícula de postgrado previa o simultánea y las que no tienen un semestre cerrado después del egreso, y las {{x:unidades_excluidas_previo_estados}} con matrícula previa en la fuente de estados, quedan **{{x:n_unidades}} unidades con {{x:eventos}} primeras matrículas** (estado `M`; §2).
2. **Es un evento raro.** La incidencia acumulada después del egreso es {{inc:descriptivo.global.incidencia.2}} a 1 año, {{inc:descriptivo.global.incidencia.4}} a 2 años y {{inc:descriptivo.global.incidencia.8}} a 4 años (§4).
3. **¿Benchmark viable?** Solo en parte, y más que antes. Con el evento por estados se cumple el criterio fijado de antemano para los modelos clásicos (al menos 30 eventos en cada partición: {{n:viabilidad.eventos.train}}, {{n:viabilidad.eventos.valid}} y {{n:viabilidad.eventos.test}}) y **el horizonte de 1 año es concluyente en test** (46 matriculados en 2.100 unidades; antes eran 28). A 2 años hay 12 matriculados en test (no concluyente) y a 4 años ningún seguimiento completo. CatBoost (mínimo 100 eventos de entrenamiento) y el MLP en GPU (mínimo 300) **siguen sin entrenarse**: hay {{n:viabilidad.eventos.train}} eventos de entrenamiento (§3, §5).
4. **Resultado.** A 1 año en test, el Cox con el perfil de ingreso supera a la incidencia histórica por programa: AP {{ic:test.2.cox_perfil.ap}} frente a {{ic:test.2.baseline_programa.ap}} (ΔAP {{d:test.2.cox_perfil.baseline_programa.ap}}) y ROC-AUC {{ic:test.2.cox_perfil.roc_auc}} frente a {{ic:test.2.baseline_programa.roc_auc}}. La trayectoria académica **no agrega nada** (Cox con trayectoria menos Cox de perfil, ΔAP {{d:test.2.cox_agg.cox_perfil.ap}}). El AP absoluto es bajo y el nivel de riesgo está subestimado (§5). El horizonte es concluyente, pero con 46 eventos el resultado sigue siendo exploratorio.
5. **Por programa y facultad.** La incidencia **observada** se puede reportar en {{x:descriptivo.grupos.programa.resumen.grupos_reportables}} programas y {{x:descriptivo.grupos.facultad.resumen.grupos_reportables}} facultades, rotuladas con su **nombre** (§6). El **pronóstico agregado** del modelo no es reportable por programa en test y solo en una facultad; con valid + test hay 2 programas y 3 facultades, y en las tres facultades el modelo subestima la tasa (§7). Por nivel, la matrícula en postgrado UCN es sobre todo de magíster (§4).
6. **Fuente de referencia (P86, P80).** La DAI confirmó `ban_estados_academicos_pos` como fuente de postgrado. Su cobertura es completa desde 2015 (586–782 personas matriculadas por año), de modo que el salto de 2023 de `banner_estudiantes_postgrado` era un artefacto de cobertura y no oferta nueva. Con esta fuente la incidencia a 1 año sube de 1,1 % a 1,9 % y los eventos de 142 a 219; la tasa de train sigue siendo menor que la de valid y test (0,9 % frente a 1,9 % y 2,2 % a 1 año; §3 y §8).
7. **Modelo conservado.** Por la regla de D69 el Cox con el perfil de ingreso reemplaza a la línea base (el intervalo pareado de ΔAP a 1 año queda sobre cero), como antes; el resultado es exploratorio pero ahora se apoya en un horizonte concluyente. **Ningún modelo está aprobado para uso individual** (Gate 4, §11).

## Cambios de la reconstrucción consolidada (13-11-2026)

1. **Evento principal por la fuente de estados (P86).** El evento pasa de `estado_matricula = MATRICULADO` de `matricula_postgrado` al estado `M` de `ban_estados_academicos_pos`; el evento anterior se conserva como sensibilidad completa (§4). Se excluyen las unidades con matrícula previa en la fuente de estados (D65).
2. **Variables de admisión.** `mm_*` (mínimo–máximo por prueba, año y campo) y `prueba_admision` reemplazan a los percentiles `pct_*`.
3. **Viabilidad (D68) con la fuente nueva.** Solo el escalón clásico es viable; CatBoost (76 eventos de entrenamiento frente a un mínimo de 100) y la red (mínimo 300) no lo son:

{{tabla:viabilidad_fuentes}}

4. **Antes y después** (modelo evaluado a 1 año en test; «antes» es la versión 0.1 con el evento anterior):

{{tabla:cambios}}

La conclusión de selección no cambia (Cox con el perfil de ingreso), pero el ROC-AUC de test baja de 0,775 a 0,696 y el ΔAP pareado frente a la incidencia por programa de 0,027 a 0,017 (los intervalos se solapan). Con el evento principal la línea base mejora (AP 0,021 a 0,029), de modo que la ventaja del Cox es menor.

## 2. Población y embudo

El embudo parte de la población de T3 (D47) y se detiene en la unidad de T6. Los recuentos son de trayectorias (no de personas). Las cifras de 1 a 9 se muestran como «< 10».

{{tabla:embudo}}

Todas las exclusiones por matrícula previa corresponden a matrículas **durante el pregrado o en el semestre del egreso**; ninguna es anterior al ingreso (la fuente de postgrado empieza en 201650 y las cohortes son 2015 o posteriores). No hay egresos anteriores al inicio de la fuente. La decisión de excluir (y no de ignorar la matrícula previa) evita que una persona ya matriculada en postgrado cuente como «evento» en el semestre siguiente al egreso solo por continuar (D65, P81).

La fuente de postgrado trae {{x:fuente_postgrado.filas_matriculadas}} filas con `MATRICULADO` de {{x:fuente_postgrado.personas_matriculadas}} personas en {{x:fuente_postgrado.programas}} programas, entre {{x:fuente_postgrado.periodo_min}} y {{x:fuente_postgrado.periodo_max}}.

## 3. Eventos por partición y viabilidad

La partición por año de egreso deja pocas matrículas en cada tramo. Los criterios se fijaron **antes de entrenar o evaluar ningún modelo** (los recuentos de eventos por partición ya se conocían) (D68): al menos 30 eventos de supervivencia por partición para el escalón clásico (línea base y Cox), 100 eventos de entrenamiento para CatBoost y 300 para una red; un horizonte binario es concluyente solo con al menos 30 matriculados y 30 no matriculados entre las unidades con seguimiento completo.

{{tabla:viabilidad}}

Eventos y unidades del problema binario (solo unidades con seguimiento hasta el horizonte):

{{tabla:horizonte}}

El seguimiento de test es de 1 a 4 semestres (mediana 3): a 2 años solo hay {{n:descriptivo.por_horizonte.4.test.n}} unidades con seguimiento completo y a 4 años ninguna. El único horizonte con seguimiento completo en las tres particiones es el de 1 año: tiene {{x:descriptivo.por_horizonte.2.train.eventos}} eventos en train, {{x:descriptivo.por_horizonte.2.valid.eventos}} en valid (no concluyente, menos de 30) y {{x:descriptivo.por_horizonte.2.test.eventos}} en test (concluyente).

## 4. Análisis descriptivo: incidencia acumulada

La incidencia acumulada es `1 − Kaplan–Meier` del primer semestre con matrícula. Los intervalos son percentiles de {{meta:boot}} remuestreos **agrupados por persona**. Una celda muestra «—» si a ese horizonte quedan menos de 100 unidades en seguimiento.

{{tabla:particion}}

La incidencia de los egresos hasta 2022 es mucho menor que la de los posteriores: el seguimiento de los egresos recientes cae en el período con más matrículas registradas (§8). Por año de egreso (el 2026 y los años con menos de 100 unidades o 10 matriculados se suprimen):

{{tabla:estrato.anio_egreso}}

Por sexo del registro (descriptivo; `sexo` no es variable del modelo):

{{tabla:estrato.sexo}}

Por titulación `U` conocida al corte, por promedio de notas hasta el egreso (terciles de toda la muestra) y por duración respecto de la nominal:

{{tabla:estrato.titulado_al_corte}}

{{tabla:estrato.promedio}}

{{tabla:estrato.duracion}}

Quien egresa dentro de la duración nominal, quien tiene mejor promedio y quien ya tiene titulación `U` al corte se matricula más a menudo en postgrado. Son asociaciones descriptivas, sin ajuste ni lectura causal.

### Sensibilidad a la definición del evento

El evento principal es el estado `M` de la fuente de estados de postgrado (P86). Las alternativas son el evento anterior (`estado_matricula = MATRICULADO` de `matricula_postgrado`) y cualquier fila de `matricula_postgrado` posterior al egreso (incluye «matrícula en trámite» y «post-graduado» sin matrícula, P78):

{{tabla:sensibilidad}}

**Modelos con el evento anterior (sensibilidad).** Los tres modelos reentrenados con el evento de `matricula_postgrado`:

{{tabla:modelos_sensibilidad}}

### Nivel del programa (magíster, doctorado, otro)

La fuente de estados trae el nombre del programa, de donde se deriva el nivel de la **primera matrícula** (P77): magíster, doctorado u otro (diplomado, postítulo o sin nombre estándar). La incidencia es específica de causa: la primera matrícula de otro nivel censura la unidad en ese momento.

{{tabla:niveles}}

La matrícula en postgrado UCN después del egreso es sobre todo de magíster; el doctorado y los demás niveles tienen pocos eventos por partición y no se modelan por separado.


## 5. Modelos y resultados exploratorios

**Modelos entrenados** (misma población en todos): (1) *incidencia histórica por programa* (línea base): `1 − KM` por programa en train, con la incidencia global para los programas con menos de 50 unidades o no vistos; (2) *Cox con L2* sobre el perfil de ingreso + atributos del programa en vigor + facultad; (3) *Cox con L2* sobre el perfil + la trayectoria académica hasta el egreso. La penalización se elige en valid por la concordancia truncada a 2 años. Preprocesamiento ajustado solo con train. **No se entrenaron** CatBoost ni el MLP (§3).

### Test (egreso 2024 o después; IC 95 % del bootstrap agrupado por persona)

{{tabla:metricas.test}}

Diferencias pareadas en test (mismos remuestreos):

{{tabla:deltas.test}}

### Valid (egreso 2023)

{{tabla:metricas.valid}}

{{tabla:deltas.valid}}

### Lectura

* **Orden, no nivel.** El Cox ordena mejor que la línea base: a 1 año el ROC-AUC de test es {{ic:test.2.cox_perfil.roc_auc}} frente a {{ic:test.2.baseline_programa.roc_auc}}; en valid la línea base queda por debajo de 0,5 a 1 año. El Brier y el ECE no mejoran, porque el nivel de riesgo no se recupera.
* **Subestimación del nivel.** El riesgo medio predicho a 1 año de cada grupo de riesgo (0,57–1,46 %) queda por debajo de la incidencia observada del grupo (0,95–5,71 %): el modelo aprende la tasa de base de train (egresos hasta 2022), menor que la de los períodos recientes (§8). Una recalibración con los datos de valid sería posible, pero con 28 eventos a 1 año no se intentó.
* **La trayectoria académica no agrega.** Cox con trayectoria menos Cox de perfil: ΔAP {{d:test.2.cox_agg.cox_perfil.ap}} a 1 año; el intervalo incluye 0 en todos los horizontes.
* **A 2 años en test** hay 12 matriculados (no concluyente): los valores de la tabla (AP con intervalos muy anchos) no se interpretan.
* **Conservado (D69).** Cox con el perfil de ingreso. La regla se cumple a 1 año (el intervalo pareado de ΔAP queda sobre cero), con 46 eventos en test: el horizonte es concluyente, pero el resultado sigue siendo exploratorio.

### Calibración a 1 año en test

Los grupos de riesgo se fusionan hasta tener al menos 10 matriculados cada uno (ningún grupo con 1 a 9 matriculados se imprime):

{{tabla:calibracion}}

El 10 % de mayor riesgo concentra una incidencia observada de 5,7 % frente a 1,8 % en el resto: una discriminación útil como orden, con niveles absolutos pequeños.

## 6. Resultados por programa y facultad: incidencia observada

Tablas de la incidencia acumulada observada en **toda la muestra** (train + valid + test), solo para programas (el vigente al egreso) y facultades con **al menos 100 unidades y 10 matriculados**; el resto se suprime y solo se cuenta. Es un resultado descriptivo, no un pronóstico.

{{tabla:grupos.programa}}

{{tabla:grupos.facultad}}

Las facultades se rotulan con su **nombre** (`neural_core.facultad`, de `common.facultad_d`; P76, P85) y los programas con su código y nombre. Las diferencias de nivel son grandes (Medicina y Ciencias frente a Economía y Administración), pero el número de matriculados por grupo es pequeño y las tasas dependen del año de egreso de cada programa (cohortes distintas).

## 7. Pronóstico agregado por programa y facultad

El mismo criterio de reportabilidad (n ≥ 100 y al menos 10 matriculados en el horizonte) se aplica al **pronóstico agregado del modelo conservado** frente a la línea base, a 1 año, entre las unidades con seguimiento completo.

{{tabla:grupos_resumen}}

**Ningún programa y una sola facultad son reportables en test.** Con valid + test, que suma más eventos, lo son 2 programas y 3 facultades:

{{tabla:gm.valid_test.facultad}}

En las tres, el modelo y la línea base **subestiman** la incidencia observada en 3 a 6 puntos porcentuales: el pronóstico agregado por programa y facultad **no es utilizable** con estos datos. Lo útil a este nivel es la incidencia observada de §6.

## 8. Cobertura de la fuente de postgrado (P80, P86)

La fuente anterior (`banner_estudiantes_postgrado`, filas `MATRICULADO`) registraba 62, 25, 52, 65, 24, 51 y 38 personas matriculadas en 2016–2022 frente a 293, 253 y 264 en 2023–2025. La fuente de estados (`ban_estados_academicos_pos`) registra 586–782 personas con estado `M` por año desde 2015, y las de la fuente anterior están contenidas en ella (D79). Es decir, el salto de 2023 era un artefacto de **cobertura** de la fuente anterior y no oferta nueva. Con el evento principal por estados:

* la tasa de base de train (egresos hasta 2022) sigue siendo menor que la de valid y test (0,9 % frente a 1,9 % y 2,2 % a 1 año), pero ya no por un registro incompleto: parte es el período del seguimiento (los egresos recientes se observan en años con más matrícula) y parte la cohorte;
* con el evento anterior la línea base aprendida en train no transfería (ROC-AUC de 0,44 a 0,63); con el evento principal se mantiene entre 0,49 y 0,64 en valid y test, es decir, la incidencia por programa sigue siendo una referencia débil;
* un modelo de supervivencia con escala de tiempo calendario o con una covariable de período (no se usó) podría separar ambos efectos con más datos.

## 9. Equidad por sexo (descriptivo)

`sexo` es un dato del registro y nunca una variable. Descriptivamente, la incidencia observada a 2 años es mayor en los hombres ({{inc:descriptivo.estratos.sexo.filas.1.incidencia.4}}) que en las mujeres ({{inc:descriptivo.estratos.sexo.filas.0.incidencia.4}}). Para el modelo conservado, a 1 año en valid + test:

{{tabla:sexo}}

El riesgo medio predicho es el mismo en ambos sexos (el modelo no usa `sexo` y sus variables no reproducen la brecha), de modo que **la brecha observada no se refleja en el modelo**. Con menos de 10 matriculadas en valid + test a 1 año en el grupo de mujeres, sus tasas observadas, AP y ROC-AUC se suprimen. No se aplicó ninguna corrección; el análisis es descriptivo, sin lectura causal.

## 10. Costo computacional

El benchmark completo (descriptivo con bootstrap de {{meta:boot}} remuestreos, dos Cox, evaluación en tres horizontes, tablas por grupo y MLflow) tarda {{meta:segundos}} s en CPU, con un pico de RAM de {{meta:ram}} MB (límite fijado: 6 GB). No se usó la GPU: el MLP no se entrenó.

{{tabla:tiempos}}

## 11. Límites y alcance

1. **El uso no está aprobado.** Informe técnico; las predicciones individuales no se publican ni se exponen en la Bóveda, y los agregados no tienen endpoint ni vista.
2. **Pocos eventos.** {{x:eventos}} matrículas posteriores al egreso en {{x:n_unidades}} unidades; a 1 año hay 46 matriculados en test (concluyente), a 2 años 12 y a 4 años ningún seguimiento completo. CatBoost y la red no son viables (D68). Las diferencias del §5 son exploratorias.
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
