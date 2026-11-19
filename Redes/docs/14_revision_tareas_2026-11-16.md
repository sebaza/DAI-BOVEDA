# DAI Neural — Revisión de las seis tareas y qué falta para mejorarlas

**Versión:** 0.3 · 16-11-2026 (T5: GRU por D114) · 0.2 · 16-11-2026 (modelo conservado según la regla única D114; P106–P108) · 0.1 · 16-11-2026 · Revisión para la Vicerrectoría y la Dirección de Análisis Institucional (DAI). Base: `08` a `13` de `docs/`, `preguntas_abiertas.md`, `00_plan.md` (D1–D114), `evidencia/` del 13 y 16-11-2026 y la revisión de literatura «Modelos de deserción universitaria comparados» (`reports/` y `research_notes/`).
**Estado:** documento de síntesis. No se ejecutó ningún modelo ni consulta nueva. Solo agregados: no hay datos personales. **Ningún modelo está aprobado para decisiones sobre personas** (Gate 4 pendiente).

---

## Resumen ejecutivo

1. Hay seis modelos, uno por pregunta. Todos se evalúan «hacia el futuro»: se entrenan con cohortes antiguas y se prueban con las más recientes.
2. **Uno es usable ahora** (tiempo hasta el egreso, el resultado más sólido), **tres ordenan bien pero con reparos** (continuidad, reprobación de un ramo y eliminación) y **dos no sirven todavía** (cambio de programa y postgrado UCN).
3. La literatura revisada no encuentra modelos comparables que rindan más. La brecha de UCN **no es de método sino de información**: las redes neuronales y el grafo de mallas no aportaron.
4. Lo que más mejoraría los modelos son **datos**: notas parciales durante el semestre (hoy solo dos semestres), historia de beneficios con fechas, inscripciones y retiros de ramos, y aclarar el registro de la eliminación.
5. Esta semana ya se logró un avance: el modelo de continuidad al primer semestre incorpora los beneficios para las cohortes desde 2024 (D113). Los beneficios **no** ayudaron en el tiempo hasta el egreso.
6. Está pendiente de la semana: notas parciales, comparación con el modelo anterior, modelo unificado y la mejora de reprobación con datos recientes.
7. Tres respuestas de la DAI destrabarían más que cualquier ajuste técnico: la caída del registro de eliminaciones desde 2024-2 (P75), el diccionario de causales de eliminación (P107) y la carga de más semestres de notas parciales (P108).
8. Condición de uso: sin revisión institucional, las predicciones individuales no se muestran. Solo se publican agregados de 10 o más estudiantes.

| Tarea | Pregunta | Veredicto | Brecha principal | Próximo paso |
|---|---|---|---|---|
| T1 Continuidad | ¿Seguirá matriculado un año después? | Usable con reparos | Solo ve lo ya ocurrido; no alerta a mitad de semestre | Notas parciales y más años de beneficios |
| T2 Reprobación | ¿Reprobará este ramo? | Usable con reparos | Nivel de riesgo algo bajo; falta dato a mitad de semestre | Decidir el ajuste con datos recientes; notas parciales |
| T3 Egreso | ¿Cuándo egresará? | Usable ahora (el más sólido) | Definición de «egreso» y cambios de registro | Decidir egreso o titulación (P59) y recalibrar |
| T4 Cambio de programa | ¿Se cambiará de carrera? | Aún no útil | Pocos casos; sobreestima el riesgo | Recalibrar y probar preferencia de postulación |
| T5 Eliminación | ¿Será eliminado en los dos semestres siguientes? | Usable con reparos | El registro de eliminaciones cambió desde 2024-2 | Respuesta de Banner (P75) y diccionario de causales |
| T6 Postgrado UCN | ¿Se matriculará en un postgrado UCN? | Aún no útil | Evento raro; solo se ve la UCN | Esperar más casos; buscar fuente externa (P82) |

---

## 0. Cómo leer este documento

- **Corte.** Es el momento en que se hace la pregunta. Se escribe «k = n» en los informes técnicos y significa «al terminar el semestre n desde el ingreso».
- **Tasa general.** Es el porcentaje de estudiantes que tiene el evento. Un modelo útil marca un grupo de riesgo donde ese porcentaje es varias veces mayor.
- **Veredictos.**
  - *Usable ahora:* ordena bien y su error es conocido.
  - *Usable con reparos:* ordena bien, pero hay un problema de datos o de definición que debe resolverse o tenerse presente.
  - *Aún no útil:* acierta poco o hay muy pocos casos.
- **Esfuerzo.** Es una estimación del equipo, referencial: bajo (horas a un par de días), medio (varios días), alto (semanas o depende de terceros).
- **Cifras entre 0 y 1.** Más alto es mejor. Se comparan siempre con una referencia simple (la tasa general o la regla por programa o por ramo). Las definiciones exactas están en el anexo.
- **Qué ya se probó.** Cada tarea indica lo que no ayudó, para no repetirlo.

---

## 1. T1 Continuidad

**Pregunta.** ¿Seguirá matriculado en la UCN un año después? Se mide la «no continuidad», que no es lo mismo que deserción: incluye pausas no registradas y traslados a otra institución.

**Cuándo se pregunta.**
- *k = 1:* al terminar el primer semestre. Se mira si está matriculado dos semestres después, al comenzar su segundo año.
- *k = 2:* al terminar el segundo semestre. Se mira dos semestres después.

**Qué tan bueno es hoy.**
- Con el modelo de rendimiento académico (prueba en cohortes 2022–2023), en *k = 1* la tasa general es 5,7 % y en *k = 2* es 10,6 %. El 10 % de mayor riesgo incluye a **56 de cada 100** de los que no continúan en *k = 1* y a **53 de cada 100** en *k = 2*. El modelo conservado es CatBoost en *k = 1* y la logística en *k = 2* (elegidos en validación, D114).
- Con el modelo vigente de *k = 1* (con beneficios, cohorte 2025), el 10 % de mayor riesgo incluye a **45 de cada 100** de los que no continúan. El modelo mejora el orden del resto de la lista y la calibración, pero no cambia ese tramo alto. Las dos cifras no son comparables entre sí: son otras cohortes y otro conjunto de datos.
- Ordena claramente mejor que mirar solo el perfil de ingreso, que casi no distingue.

**Veredicto: usable con reparos.**
- Sirve para ordenar y para estimar riesgo por grupos.
- La señal viene sobre todo del rendimiento ya observado al cierre del semestre. **No es una alerta temprana.**

**Qué lo limita.**
- Los datos útiles parten en 2015. Los segundos semestres anteriores no se registraron (P49) y la forma de registrar salidas cambió hacia 2014 (P50).
- Hay pocos casos: unos 110 por año en la validación de beneficios. Diferencias menores a 0,03 no son separables.
- Los beneficios solo tienen historial de cargas desde 2024 (P93). El modelo se entrenó con la vista final de la tabla.
- Una parte de quienes «no continúan» sigue en otro programa UCN (13,5 % en *k = 1* deja el programa).

**Qué falta para mejorarlo.**

| Prioridad | Qué falta | Tipo | Impacto | Esfuerzo | Referencia |
|---|---|---|---|---|---|
| 1 | Notas parciales del semestre en curso, para una alerta a mitad de semestre | Dato y método | Alto (es el único salto medido en la literatura), pero hoy solo exploratorio | Medio | Plan 13; solo hay 202510 y 202610 |
| 2 | Más años de historial de beneficios con fecha; reentrenar con la vista del corte | Dato | Medio | Bajo, pero depende del tiempo | P93, D113; cohorte 2026 con resultado en octubre de 2027 |
| 3 | Inscripciones y retiros de ramos (créditos inscritos, renuncias) | Dato | Medio | Medio | P53; la tabla es reciente |
| 4 | Fuente de los diagnósticos institucionales de matemáticas e inglés (el modelo anterior los usaba) | Dato | Por medir | Bajo si existe | No se encontró en el almacén; P106 |
| 5 | Vigilar cambios de política de beneficios (se espera una reducción) | Decisión | Medio, por riesgo de desfase | Bajo | P93, P105 |
| 6 | Encuesta de ingreso (ENCE) | Dato nuevo | Medio, no medido | Alto | P31, abierta |

**Ya se probó y no ayudó.**
- Redes neuronales: en validación la GRU no se separa de los modelos clásicos (la diferencia pareada con CatBoost incluye el cero) y se conserva el modelo más simple (D114).
- Beneficios en *k = 2* (+0,011, sin ganancia detectable) y la pérdida de beneficios en *k = 4*.
- Entrenar con todas las cohortes antiguas.

**Plan de la semana.**
- *Hecho:* extracción de beneficios y de su historial de cargas. Evaluación y adopción en *k = 1* desde la cohorte 2024 (D113).
- *Pendiente:* notas parciales, comparación con el modelo anterior, modelo unificado y reprobaciones esperadas desde T2.
- *Descartado:* beneficios en *k = 2*.

---

## 2. T2 Reprobación de un ramo

**Pregunta.** Para cada ramo que un estudiante cursa, ¿lo reprobará (nota menor a 4,0)?

**Cuándo se pregunta.** Antes de que comience el semestre, con la inscripción hecha y la historia anterior. No tiene cortes «k». El corte a mitad de semestre, con notas parciales, está planificado y aún no existe.

**Qué tan bueno es hoy** (prueba 2023–2024, tasa general 14,4 %).
- Mirar solo la dificultad histórica de cada ramo da un resultado de 0,359. El modelo actual llega a 0,534. Los modelos con solo datos del estudiante quedan en 0,43.
- Es decir, el modelo identifica bien a quienes están en riesgo, sobre todo por el ramo que cursan.
- El nivel absoluto es algo bajo: predice 11,4 % de reprobación media frente a 14,4 % real.
- Agregado por programa y facultad, ordena bien los grupos y se equivoca menos que la frecuencia global.

**Veredicto: usable con reparos.** Sirve para ordenar los ramos por riesgo y para pronósticos por grupo, pero subestima el nivel de reprobación. Antes de mostrar porcentajes absolutos hay que recalibrar con datos recientes.

**Qué lo limita.**
- Los semestres 2019-2 y 2020-1 no tienen reprobaciones registradas (P58): en pandemia no contaban como oportunidad. No se puede recuperar.
- La dificultad de los ramos cambia con el tiempo: hoy son más fáciles que hace diez años (P55, D80).
- La carga real inscrita solo se conoce desde 2025, porque la tabla de inscripciones es reciente (P53).

**Qué falta para mejorarlo.**

| Prioridad | Qué falta | Tipo | Impacto | Esfuerzo | Referencia |
|---|---|---|---|---|---|
| 1 | Notas parciales: un corte con la mitad de las notas del semestre | Dato y método | Alto | Medio; solo dos semestres | Plan 13 (jueves) |
| 2 | Adoptar el cálculo con datos recientes de la dificultad del ramo (decaimiento temporal) | Decisión | Bajo a medio (+0,011, seguro) | Bajo | P55, D88; propuesto y no aplicado |
| 3 | Decidir si se usa el contexto docente | Decisión | Medio (+0,028) | Bajo | D88; exige revisión institucional |
| 4 | Recalibrar con un semestre reciente | Método | Medio, para porcentajes absolutos | Bajo | §14 del informe 09 |
| 5 | Inscripciones anteriores a 2025 | Dato | Bajo a medio | Alto: no existen | P53 |
| 6 | Beneficios como variable | Método | Bajo a medio, por probar | Bajo | Plan 13 (martes) |

**Ya se probó y no ayudó.**
- El grafo curricular. Los prerrequisitos explícitos aportan una milésima (+0,004) y los embeddings de grafo empeoran el resultado (−0,004).
- Redes neuronales.
- Identificar el ramo por su código.

**Plan de la semana.**
- *Pendiente:* adopción del decaimiento (propuesto desde el 13-11), regeneración de predicciones, notas parciales y beneficios.

---

## 3. T3 Tiempo hasta el egreso

**Pregunta.** ¿Cuánto falta para que el estudiante egrese y con qué probabilidad lo hace antes de 10, 12 o 14 semestres? «Egreso» es el primer estado de malla completa, no la titulación (P59). La salida del programa se trata como evento competidor.

**Cuándo se pregunta.**
- *k = 0:* al ingreso, solo con datos de admisión.
- *k = 2:* al terminar el segundo semestre.
- *k = 4:* al terminar el cuarto semestre.

**Qué tan bueno es hoy** (prueba, cohortes 2019–2020).
- Con *k = 2* y *k = 4*, el modelo ordena correctamente a unos **84 a 86 de cada 100** pares de estudiantes en cuál egresa antes. Al ingreso esa cifra baja a unos 74.
- La ganancia grande viene de los créditos aprobados y el avance de malla al corte (de 74 a 82-86). Ninguna arquitectura se acerca a ese salto.
- Tratar bien la salida importa: el método ingenuo estima 61 % de egreso a 12 semestres; el correcto, 35 %.
- Los modelos solo con ingreso subestiman el egreso reciente. Los que usan rendimiento quedan mejor calibrados.

**Veredicto: usable ahora; es el resultado más sólido de las seis tareas.** Ordena bien desde el segundo semestre. Antes de mostrar probabilidades hay que recalibrar y aclarar la definición del evento.

**Qué lo limita.**
- Egreso y titulación no coinciden en las fuentes (P59). Hay estados de titulado sin registro y registros sin episodio.
- La mediana al egreso bajó de 13 a 11 semestres. Parte puede ser de registro (P60).
- Quienes «salen» del programa son en su mayoría traslados dentro de la UCN (P61).
- Las cohortes recientes no tienen todavía seguimiento completo.

**Qué falta para mejorarlo.**

| Prioridad | Qué falta | Tipo | Impacto | Esfuerzo | Referencia |
|---|---|---|---|---|---|
| 1 | Decidir si el evento es egreso o titulación | Decisión | Medio, aclara la definición | Bajo | P59 |
| 2 | Recalibrar con las cohortes más recientes | Método | Medio | Bajo | §7.3 del informe 10 |
| 3 | Decidir si se opera en cortes tardíos (8 a 10 semestres) | Decisión | Alto en utilidad: con el estudiante cerca del egreso la discriminación es muy alta (valid 0,93 a 0,97) | Medio | P104, D103 |
| 4 | Separar «cambió de programa» de «abandonó» dentro de la salida | Método | Medio, en interpretación | Medio | P61 |
| 5 | Fecha de asignación de Capstone y de expiración de gratuidad; beneficios anteriores a 2017 | Dato | Bajo: el rendimiento ya contiene esa señal | Alto | P98, P99, P100, P102 |

**Ya se probó y no ayudó.**
- Beneficios. No mejoran en ningún corte oficial y empeoran en los tardíos (D104 a D109).
- Redes neuronales. La GRU es el modelo conservado en *k = 2* y *k = 4* (D114): en validación mejora el C(12) del mejor clásico en +0,017 y +0,024. En *k = 4* la mejora en prueba es marginal (+0,006) y su IBS en prueba es levemente peor (+0,001). Al ingreso (*k = 0*) las redes no aportan.
- Usar el año de ingreso como variable.

**Plan de la semana.**
- *Hecho y descartado:* beneficios en T3 (D100 a D109). El modelo oficial no cambia.
- *Hecho y descartado:* Capstone y expiración de gratuidad como señales de egreso cercano. No mejoran a la GRU, porque los créditos y el avance de malla ya sitúan al estudiante (D105).
- *Pendiente:* modelo unificado.

---

## 4. T4 Cambio de programa

**Pregunta.** ¿Se pasará a otro programa de pregrado (cambio de carrera, de sede u otro traslado) en los dos semestres siguientes? La elección de especialidad desde el Plan Común no cuenta.

**Cuándo se pregunta.**
- *k = 2:* al terminar el segundo semestre.
- *k = 4:* al terminar el cuarto semestre.
- En ambos casos se mira en los dos semestres siguientes.

**Qué tan bueno es hoy** (prueba, cohortes 2022–2023, *k = 2*).
- La tasa general es 3,0 %.
- Con los datos de rendimiento el modelo duplica la regla simple por programa (0,094 frente a 0,050), pero acierta pocos casos en el extremo alto.
- Ordena de forma razonable (0,73 en la escala de orden, donde 0,5 es azar). Con *k = 4* es más difícil: la precisión baja a 0,059.
- **Sobreestima el riesgo en unos 7 puntos** (predice 10 % frente a 3 % real). Por eso su pronóstico agregado por programa es peor que la tasa histórica.

**Veredicto: aún no útil.** Solo sirve la tasa histórica por programa.

**Qué lo limita.**
- Pocos eventos: la mayoría de los programas no llega a 10 casos.
- El perfil de ingreso casi no distingue.
- Depende de la regla del archivo de traslados (D48 a D51), cuyas reglas conservadoras siguen en validación.

**Qué falta para mejorarlo.**

| Prioridad | Qué falta | Tipo | Impacto | Esfuerzo | Referencia |
|---|---|---|---|---|---|
| 1 | Recalibrar el riesgo | Método | Alto para el pronóstico por programa, no para el orden | Bajo | D86; plan 13 |
| 2 | Preferencia de postulación y notas en ramos propios de la carrera frente a ramos generales | Dato y método | Medio, por probar | Medio | Plan 13; sin pregunta asignada |
| 3 | Ramos inscritos fuera de la malla, como señal de que se quiere cambiar | Dato | Medio a alto según la literatura, no medido en UCN | Medio | P53; literatura |
| 4 | Validar la regla de traslados (casos especiales del Plan Común) | Decisión | Medio | Bajo | P73, P64 a P69 |
| 5 | Decidir si se usará solo por programa | Decisión | Define el alcance | Bajo | Plan 13 |

**Ya se probó y no ayudó.**
- El perfil de ingreso solo no supera la tasa histórica.
- Redes neuronales.

**Plan de la semana.**
- *Pendiente:* preferencia de postulación, recalibración y modelo unificado.

---

## 5. T5 Eliminación académica

**Pregunta.** ¿Recibirá un estado de eliminación (`E`) en los dos semestres siguientes?

**Cuándo se pregunta.**
- *k = 2:* al terminar el segundo semestre.
- *k = 4:* al terminar el cuarto semestre.

**Qué tan bueno es hoy** (prueba 2022–2023, *k = 2*).
- La tasa general es 9,7 %. En la lista de mayor riesgo, la proporción de eliminados es del orden de **5 a 6 veces** esa tasa.
- Ordena muy bien (0,91 en la escala de orden, donde 0,5 es azar) y queda bien calibrado.
- Con los años de registro completo mejora (0,634). Con la eliminación efectiva (sin reintegro) baja (0,460).
- Con *k = 4* es más difícil (0,309).

**Veredicto: usable con reparos.** Ordena muy bien, pero lo que mide depende de cómo se registre `E`.

**Qué lo limita.**
- **Desde 2024-2 el registro de eliminaciones y reintegros cae a la vez** (P75). La matrícula cuadra y no hay estudiantes perdidos: parece un cambio de registro. Un modelo entrenado así aprende menos eliminación de la real.
- Solo un tercio (29,8 %) de las eliminaciones sigue la regla de la tercera oportunidad. Otro tercio (34,0 %) no cursó ramos: parece abandono.
- No hay diccionario de causales (P70, P107).
- `E` mide una eliminación registrada, no una «reprobación grave».

**Qué falta para mejorarlo.**

| Prioridad | Qué falta | Tipo | Impacto | Esfuerzo | Referencia |
|---|---|---|---|---|---|
| 1 | Respuesta de Banner sobre la caída de `E` e `I` desde 2024-2 | Dato | Alto: define cuánto confiar en la evaluación | Bajo para la DAI | P75 |
| 2 | Diccionario de causales de eliminación (0A, 0B, 0D, 2D, 84) | Dato | Alto: separa las vías reglamentaria, abandono y sumario | Bajo | P70, P107 |
| 3 | Riesgo reglamentario: ramos con segunda oportunidad reprobada y riesgo de reprobar la tercera, desde T2 | Método | Medio a alto | Medio | Plan 13 (martes) |
| 4 | Notas parciales | Dato y método | Medio a alto, exploratorio | Medio | Plan 13 (jueves) |
| 5 | Beneficios (vía de abandono) | Método | Bajo a medio | Bajo | Plan 13 |

**Ya se probó y no ayudó.**
- Redes neuronales: la GRU ya no supera a CatBoost (D87).
- El perfil de ingreso solo.

**Plan de la semana.**
- *Pendiente:* riesgo reglamentario, beneficios, notas parciales y separación por vía.

---

## 6. T6 Postgrado UCN

**Pregunta.** Entre quienes egresan de pregrado, ¿quién se matriculará después en un postgrado de la UCN?

**Cuándo se pregunta.** Al egresar, con horizontes de 1, 2 y 4 años. Solo el de 1 año es concluyente.

**Qué tan bueno es hoy** (prueba, egresados desde 2024, 1 año).
- Es un evento raro: 2,2 % de los egresados se matricula en el primer año.
- El modelo, basado en el perfil de ingreso, mejora la tasa por programa (0,046 frente a 0,029) y ordena de forma moderada (0,70).
- El 10 % de mayor riesgo tiene 5,7 % de matrícula, frente a 1,8 % en el resto. Pero **subestima** el nivel: predice 1,5 % en ese grupo.
- La trayectoria académica no agrega nada.

**Veredicto: aún no útil.** Es exploratorio, con 46 matriculados en la prueba. No se puede reportar por programa.

**Qué lo limita.**
- Pocos eventos: 76 en entrenamiento, frente a un mínimo de 100 para el modelo de árboles.
- Solo se observa el postgrado UCN. No matricularse aquí no significa no estudiar postgrado (P82).
- La matrícula en postgrado era un registro incompleto antes de 2023; ahora se usa la fuente de estados (P86, D83).

**Qué falta para mejorarlo.**

| Prioridad | Qué falta | Tipo | Impacto | Esfuerzo | Referencia |
|---|---|---|---|---|---|
| 1 | Más eventos: esperar cohortes y volver a evaluar la viabilidad | Dato | Medio | Bajo, depende del tiempo | D68, D83 |
| 2 | Fuente de postgrado en otras instituciones | Dato | Alto, cambia la pregunta | Alto | P82, abierta |
| 3 | Decidir cómo tratar la articulación pregrado-postgrado (70 casos excluidos) | Decisión | Bajo a medio | Bajo | P81 |
| 4 | Nota de titulación con el Capstone (examen 30 %) | Dato | Bajo a medio | Medio | P89, D81 |
| 5 | Señales de investigación, becas y participación | Dato nuevo | Bajo a medio, evidencia débil | Alto | Literatura |
| 6 | Beneficios | Método | Bajo | Bajo | Plan 13 (jueves) |

**Ya se probó y no ayudó.**
- La trayectoria académica como variable (ΔAP −0,010).
- Los modelos de árboles y de redes no se pueden entrenar con tan pocos eventos.

**Plan de la semana.**
- *Pendiente:* beneficios y Capstone.

---

## 7. Mejoras que sirven a varias tareas

| Mejora | Tareas | Tipo | Impacto | Esfuerzo | Estado |
|---|---|---|---|---|---|
| **Notas parciales: más semestres.** Hoy solo hay 202510 y 202610. Se puede entrenar con uno y evaluar con otro, pero con una sola validación. | T1, T2, T5 | Dato | Alto | Medio | Pendiente; pedir más semestres a la DAI (P108) |
| **Comparación cara a cara con el modelo anterior.** Su puntaje está congelado desde 09-2024 y solo cubre a los mismos 13.145 estudiantes; no hay cohortes 2025-2026. | T1, T5 | Evaluación | Alto en confianza institucional; no mejora el modelo | Medio | Pendiente (lunes) |
| **Evaluación prospectiva.** Guardar las predicciones de cada semestre y compararlas con lo ocurrido, con vigilancia de cambios y de equidad. | Todas | Método | Alto en credibilidad | Medio | Sin iniciar |
| **Revisión institucional (Gate 4).** Aprobar usos, límites y quién ve qué. | Todas | Decisión | No mejora los modelos, pero **es lo que habilita su uso** | Medio | Pendiente |
| **Aclarar los registros** (P75, P59, P60, causales: P107). | T1, T3, T5 | Dato | Alto | Bajo para la DAI | Pendiente |
| **Modelo unificado de trayectoria.** Un solo modelo para el siguiente semestre (sigue, egresa, eliminado, cambia, abandona), con T2 como insumo. | T1, T4, T5 | Método | Medio en coherencia y mantenimiento; **bajo en precisión**: la literatura y los resultados indican que la arquitectura no es la brecha | Alto | Pendiente (miércoles) |
| **Inscripciones, retiros y diagnósticos** (matemáticas, inglés). | T1, T2, T4, T5 | Dato | Medio | Medio a alto | Parcial; P53, P106 |
| **Beneficios con historial y fecha.** Cada año de carga agrega historia. | T1, T3, T5 | Dato | Medio, creciente | Bajo, depende del tiempo | En curso (P90, P93, P105) |
| **Recalibración periódica** con el semestre más reciente. | T2, T3, T4 | Método | Medio | Bajo | Pendiente |

**Lectura de la literatura.**
- Los puntajes más altos publicados vienen de cortes tardíos, de particiones aleatorias o de tasas base mayores. Ninguno combina corte temprano, validación fuera de tiempo y tasa base baja.
- Para T1 y T2 UCN queda por sobre lo comparable. Para T3 a T6 no hay benchmark publicado.
- El orden de prioridad que respalda la evidencia es: notas parciales, ayuda financiera y su pérdida, inscripción y retiros y, por último, encuestas.
- Las ganancias de los puntos 2 a 7 de la literatura son hipótesis razonadas, no efectos medidos.
- Con dos semestres de notas parciales, cualquier resultado muy alto debe auditarse contra la fuga de información.

**Pendientes de la DAI que condicionan todo el plan** (plan 13, §4):
- P75: caída de `E` y de reintegros desde 2024-2.
- Diccionario de causales de `E` (P107).
- Fecha de asignación de beneficios: no existe (P90); se usa la primera carga.
- Fuente de los diagnósticos institucionales (P106).
- Más semestres de notas parciales (P108).

---

## Anexo técnico (para analistas)

### A. Definiciones en una línea

- **AP (precisión promedio):** resume cuántos de los casos marcados como riesgo son reales al recorrer la lista de mayor a menor riesgo. La referencia al azar es la tasa general.
- **ROC-AUC:** probabilidad de que un caso real tenga más riesgo que uno que no lo es. 0,5 es azar; 1 es perfecto.
- **C(12) o C-index:** igual que el AUC, para tiempo hasta el evento. Se evalúa a 12 semestres desde el ingreso.
- **IBS:** error de probabilidades en el tiempo; menor es mejor.
- **Brier y ECE:** error de las probabilidades y desvío entre lo predicho y lo observado; menor es mejor.
- **Recall@10 %:** fracción de los eventos que cae en el 10 % de mayor riesgo.
- **IC 95 %:** intervalo del bootstrap; si la diferencia pareada lo excluye del 0, se considera real.
- **Lift (derivado):** AP dividido por la tasa general. Es una aproximación de cuántas veces concentra el riesgo el tramo alto.
- **Gate 4:** revisión institucional previa al uso de predicciones individuales.

### B. Métricas citadas (prueba, IC en los informes)

| Tarea | Configuración | Tasa general | AP | AUC o C | Otros | Fuente |
|---|---|---|---|---|---|---|
| T1 *k* = 1, académico | CatBoost, test 2022–2023 | 5,7 % | 0,360 | 0,857 | Recall@10 % 0,561 | 08 §Resumen |
| T1 *k* = 2, académico | Logística, test 2022–2023 | 10,6 % | 0,537 | 0,893 | Recall@10 % 0,525; CatBoost AP 0,552 (no separable en validación) | 08 §12, D114 |
| T1 *k* = 1, con beneficios | CatBoost, test 2025 (112 eventos) | no informada | 0,248 (académico 0,205) | 0,807 | ΔAP +0,043 [+0,011; +0,070]; Recall@10 % 0,446 | 08 §15.9, D112, D113 |
| T2 | CatBoost (c), test 2023–2024 | 14,4 % | 0,534; con decaimiento 0,545; con docente 0,562 | 0,859 | Tasa histórica del curso 0,359; riesgo medio 0,114 | 09 §5.1, §12c, D88 |
| T3 *k* = 2 | GRU, test 2019–2020 | egreso a 12 sem. 35,0 % | n/a | C(12) 0,839 | IBS 0,0422 | 10 Resumen, D104 |
| T3 *k* = 4 | GRU, test 2019–2020 | idem | n/a | C(12) 0,860 | IBS 0,0518 | 10 Resumen, D104 |
| T3 *k* = 0 | clásico, test | idem | n/a | C(12) 0,738–0,739 | AJ por programa 0,706 | 10 Resumen |
| T4 *k* = 2 | logística, test 2022–2023 | 3,0 % | 0,094 | 0,732 | Tasa histórica AP 0,050; sobreestima ≈ 7 pts | 11 Resumen, D86 |
| T4 *k* = 4 | CatBoost | no informada | 0,059 | no informado | — | 11 Resumen |
| T5 *k* = 2 | GRU (D114), test 2022–2023 | 9,7 % | 0,566 | 0,908 | ECE 0,011; antes CatBoost 0,554; sin años dudosos 0,634; eliminación efectiva 0,460 | 11, D114 |
| T5 *k* = 4 | GRU (D114) | no informada | 0,312 | 0,877 | peor calibrada que la logística (Brier 0,058 frente a 0,049) | 11, D114 |
| T6 1 año | Cox con perfil, test 2024+ | 2,2 % (46/2.100) | 0,046 (línea base 0,029) | 0,696 | Eventos 76/51/92; ΔAP +0,017 [+0,005; +0,043] | 12 Resumen, D83 |

### C. Decisiones y preguntas citadas

- **Decisiones:** D47 (población T3), D48 a D51 (traslados), D68 y D83 (viabilidad y fuente de T6), D80 y D88 (deriva y decaimiento en T2), D86 y D87 (T4 y T5), D90 a D99 (beneficios en T1), D100 a D109 (beneficios en T3), D110 a D113 (señal al corte, montos corregidos, validación 2024/2025 y adopción en T1 *k* = 1), D114 (regla única de selección del modelo conservado).
- **Preguntas abiertas o parciales:** P31, P53, P56, P59, P75, P82, P92, P94, P95, P98 a P100, P102 a P108.
- **Respondidas con efecto en este documento:** P49, P50, P58, P60, P61, P70, P81, P89, P90, P93, P96, P97.
- **Preguntas nuevas con número (16-11-2026):** P106 (fuente de los diagnósticos institucionales), P107 (diccionario de causales de eliminación) y P108 (plan y fecha de más semestres de notas parciales).

### D. Evidencia externa y de apoyo

- Modelo anterior (`analitics_results`): 13.145 estudiantes, puntaje congelado desde 09-2024, explicaciones inestables (`evidencia/modelo_anterior_analitics_2026-11-13.md`).
- Eliminación frente a reprobación: 29,8 % reprobó en tercera oportunidad o más; 24,4 % reprobó sin llegar a ella; 11,7 % aprobó todo; 34,0 % no cursó ramos (`evidencia/eliminacion_vs_reprobacion_2026-11-13.md`).
- Beneficios: perder la gratuidad se asocia con 73,0 % de continuidad frente a 95,2 % de quienes la mantienen; es asociación, no causalidad (`evidencia/beneficios_2026-11-16.md`).
- Flujo de matrícula: el saldo cuadra y no hay estudiantes perdidos; E y reintegro caen a la vez desde 202420 (`evidencia/flujo_matricula_2026-11-13.md`).
