# «Lo que pasó» por temas y pestaña «Lo que viene» (DAI Neural) — diseño

**Fecha:** 18-11-2026 · **Estado:** construido (decisión D121 en `Redes/docs/00_plan.md`). Desviaciones: el tema se elige en el frontend con una sola llamada `GET /neural/historico` (sin `?tema=`); egreso en la proyección por duración nominal y nominal + 2 semestres en vez de 2027 y 2028; regla de «otros» con absorción de la fila más pequeña; tolerancia de reproducción 1e-4 en vez de 1e-6; la distancia al umbral cuenta reprobaciones que faltan (en el umbral, a 1, a 2, lejos). Continúa `2026-11-18-vista-lo-que-paso-design.md` (parte A, ya construida y verificada).

## Intención
Vicerrectores y autoridades leen los resultados como cantidades de estudiantes. La parte A mostró cuatro preguntas históricas. Ahora el usuario pide: (1) la **parte B**, proyección para los estudiantes actuales, y (2) más preguntas que los modelos y los datos ya pueden responder: ramo más reprobado, ramos y departamentos que reprueban más de lo esperado, causales de eliminación por programa y las ocho preguntas aceptadas (abajo). El usuario rechazó explícitamente cualquier ranking de docentes («el peor profe») en favor de la versión por ramo y departamento.

## Objetivos / no objetivos / antiobjetivos
- **Objetivos:**
  - «Lo que pasó» se divide en cuatro temas con un selector segmentado: **Permanencia · Ramos · Egreso y causas · Cómo decide el modelo**.
  - Nueva pestaña **«Lo que viene»** (segunda, tras «Lo que pasó») con la proyección de los estudiantes actuales.
  - Cada bloque mantiene el formato aprobado: pregunta, gráfico, número clave, una frase y «Cómo usarlo»; filtro Toda la UCN / facultad.
- **No objetivos:** reentrenar o cambiar modelos conservados; listas o puntajes por estudiante; adaptar T5 al reglamento 2025 (se marca como orientativo).
- **Antiobjetivos:**
  - Cualquier identificación de docentes: nunca se expone `docente_key`, ni secciones individuales, ni rankings de profesores, ni siquiera seudonimizados.
  - Cifras por persona; celdas de menos de 10 estudiantes (se ocultan).
  - Mezclar lo ocurrido con lo proyectado en una misma cifra.
  - Presentar asociaciones como causas (pregunta 4).
  - Usar `sexo` fuera de equidad; usar `cohorte_anio` como variable.

## Organización (enfoque A, elegido por el usuario)

### «Lo que pasó» · Permanencia
- P-1 ¿En qué semestre se pierden más estudiantes? (bloque 1 actual).
- P-2 ¿Cuántos pasaron al año siguiente? (bloque 2 actual).
- P-3 Si se hubiera usado el modelo (bloque 4 actual).
- P-4 **¿Qué perfil de ingreso tiene más riesgo de no seguir?** Continuidad observada y esperada (T1 `k = 1`, prueba) por vía de admisión, tipo de colegio y quintil de puntaje ponderado. Texto fijo: «muestra asociación, no causa».
- P-5 **¿Cuánto pesa el primer semestre?** Continuidad al año siguiente según reprobaciones del primer semestre (0, 1, 2, 3 o más), cohortes con seguimiento.

### «Lo que pasó» · Ramos
- R-1 **¿Cuál es el ramo más reprobado?** Ranking de ramos por tasa de reprobación (intentos evaluados, sin los períodos P58), con nombre del ramo y número de intentos; solo ramos con ≥ 10 intentos por celda. Muestra también el número absoluto de reprobados (un ramo masivo con tasa media puede pesar más).
- R-2 **¿En qué ramos y departamentos se reprueba más de lo esperado?** Reprobados observados frente a esperados por el modelo T2 conservado (`cb_c_nuevas`, D118) en las particiones de prueba y posterior, agregados por ramo y por departamento. Se muestra la diferencia con su intervalo; solo grupos con ≥ 10 intentos. Ninguna salida contiene sección, NRC ni docente.
- R-3 **¿Qué ramos frenan el avance?** Cuellos de botella: reprobados del ramo × número de ramos que dependen de él en el grafo de prerrequisitos (descendientes). Top de ramos por impacto.
- R-4 **¿En qué semestre de la malla se reprueba más?** Tasa de reprobación por semestre curricular (`asignatura_malla.semestre`), por facultad.

### «Lo que pasó» · Egreso y causas
- E-1 ¿Cuántos fueron eliminados cada año? (bloque 3 actual, con su inserto del modelo T5).
- E-2 **Causales de eliminación por programa.** Distribución por grupos de causal P117 (3.ª oportunidad, 2.ª oportunidad, no inscribe, avance, egresado sin titularse, otras) por programa; programas con < 10 eliminaciones en la ventana se agrupan en «otros programas de la facultad» o se ocultan. Nota fija: el motivo personal no existe en los datos (P123).
- E-3 **¿Cuánto tardan en egresar?** Por programa: % que egresa dentro de la duración nominal, con un año y con dos años de atraso, en cohortes con seguimiento suficiente (incidencia acumulada con riesgos competitivos, como T3).

### «Lo que pasó» · Cómo decide el modelo
- M-1 **¿Qué explica el riesgo?** Las cinco señales que más pesan en T1, T2 y T5 (modelos conservados), traducidas a lenguaje simple por familia de variable (p. ej. «notas del último semestre», «reprobaciones acumuladas»). Sin signos causales.
- M-2 **¿Cuánto se gana esperando un semestre?** Comparación de anticipación del modelo entre cortes (T1 `k = 1` frente a `k = 2`; T5 `k = 2` frente a `k = 4`) expresada como «de cada 10 que no continuaron, el 10 % de mayor riesgo alcanza a N».

### «Lo que viene» (parte B)
Base: estudiantes de pregrado vigentes al último período cerrado (**202610**). El 202620 está en curso y casi sin datos (321 episodios con intentos), por lo que no se usa. Cada modelo se aplica solo a la población y al corte con que fue entrenado; quien no cae en la población de ningún modelo se cuenta como «sin proyección» y se informa cuántos son.
- V-1 **¿Cuántos seguirán en 2027?** Esperados = suma de probabilidades del modelo T1 conservado para los estudiantes en su corte (cohorte 2026 con `k = 1`, modelo `cb_ben_pit` según D113; otras cohortes según la población de T1). Se muestra como rango.
- V-2 **¿Cuántos podrían ser eliminados?** T5 conservado (GRU, D120) en los cortes `k = 2` y `k = 4`. Marcado como **orientativo**: el modelo no vio el reglamento 2025 (Art. 46) y hay subregistro desde 202420 (P75).
- V-3 **¿Cuántos egresarían en 2027 y 2028?** Incidencia acumulada esperada del modelo T3 conservado para los estudiantes en sus cortes.
- V-4 **¿Cuántos están cerca del umbral de eliminación hoy?** Conteo de estudiantes actuales a 1 y a 2 reprobaciones (o cursos en 3.ª oportunidad) del umbral del **reglamento vigente** (Art. 46 desde 202520: 6 reprobaciones de 2.ª oportunidad o 2 cursos distintos de 3.ª), con las reglas ya codificadas en `rules_variables.py`. Es descriptivo, no un modelo, y es el bloque principal de la pestaña. «Cómo usarlo»: dónde poner tutorías este semestre.

## Restricciones
- Solo agregados; ninguna celda con n < 10. Nada de `docente_key`, NRC, sección o persona en ninguna tabla publicada, artefacto exportado ni respuesta de la API.
- Punto en el tiempo: la proyección usa solo datos hasta el cierre de 202610; las preguntas históricas usan las particiones ya definidas; no se reentrena nada.
- Toda proyección se muestra como rango y con su fecha de corte; V-2 lleva la advertencia de reglamento y P75.
- Texto en español neutro para no técnicos; tema oscuro; sin desborde horizontal a 375 px.
- Migraciones nuevas solo con el runner (`pipelines.migrate`, siguiente número 032), nunca editar una aplicada; toda migración nueva se agrega a `EXTRA_DDL` de `backend/tests/test_neural_api.py`.
- API de solo lectura y de agregados; la prueba de regresión que prohíbe rutas con «persona» o «episodio» sigue vigente.
- Sin commits hasta que el usuario lo indique.

## Enfoques considerados
- **A. «Lo que pasó» por temas + pestaña «Lo que viene» (elegido).** Cada tema se lee de una pasada y lo proyectado queda separado de lo ocurrido; cuesta un clic por tema.
- B. Una página larga con índice: ~15 bloques, se pierde la lectura rápida y se mezcla historia con proyección.
- C. Una pestaña por tema: el panel pasaría de 6 a ~10 pestañas y no cabe en el celular.

## Decisiones del constructor (mías)
- Mismo patrón que la parte A: cálculo en Redes (`evaluation/vista_historica.py` ampliado o módulos hermanos por tema → `artefactos/*.json`) → exportador → `neural_mart` (una fila por bloque, tema y filtro, `contenido` jsonb; la tabla de la migración 029 puede ampliarse con una columna `tema` mediante migración nueva) → endpoints de solo lectura: `GET /neural/historico?tema=&facultad=` y nuevo `GET /neural/proyeccion?facultad=` → componentes en `NeuralPanel`.
- La proyección necesita filas de los estudiantes actuales en los cortes de cada modelo: se reutilizan los constructores de snapshot en un modo «solo puntuación» (sin etiqueta), sin alterar los snapshots oficiales ni sus hashes.
- Rango de las proyecciones: intervalo de la suma de Bernoulli independientes (o bootstrap por persona), a elección del constructor; se documenta.
- Importancias (M-1): importancia por permutación en prueba agrupada por familia de variables, para que sea comparable entre CatBoost, logística y GRU.
- Orden de los temas y el bloque por defecto de cada uno: el de la lista anterior.

## Reglas de la proyección (decisiones mías tras la revisión del constructor)
- **Modelos:** no hay modelos guardados en disco, solo predicciones. Para puntuar a los estudiantes actuales se reajusta **exactamente la configuración validada sobre su misma ventana de entrenamiento y con la misma semilla**, y se verifica que reproduce las predicciones guardadas de prueba (tolerancia 1e-6; en T6 no aplica). No es un modelo nuevo ni usa datos más recientes. Los modelos ajustados se guardan en `artefactos/modelos/` para no repetir el ajuste.
- **Quién entra en cada proyección:** cada par (tarea, `k`) se aplica a la cohorte cuyo corte (`corte_periodo(admisión, k)`) es el más reciente ya cerrado (≤ 202610) y cuyo horizonte sigue abierto. Con los datos de hoy:

  | Bloque | Tarea y `k` | Cohorte | Corte |
  |---|---|---|---|
  | V-1 | T1 `k = 1` (`cb_ben_pit`, D113) | 2026 | 202610 |
  | V-1 | T1 `k = 2` (`lr_acad`) | 2025 | 202520 |
  | V-2 | T5 `k = 2` (`gru_adm`) | 2025 | 202520 |
  | V-2 | T5 `k = 4` (`gru_agg`) | 2024 | 202520 |
  | V-3 | T3 `k = 0`, `2` y `4` (modelos conservados) | 2026, 2025 y 2024 | 202610, 202520 y 202520 |

  Un mismo estudiante puede aparecer en V-1 y en V-2 porque responden preguntas distintas; dentro de una misma pregunta nadie se cuenta dos veces. Las cohortes anteriores a 2024 quedan «sin proyección» en V-1 a V-3 y se informa cuántas son; V-4 cubre a todos.
- **Cada cifra se expresa con la definición de su etiqueta:** V-1 usa la definición de continuidad de T1. V-2 se refiere a la eliminación en los dos semestres siguientes al corte (`k + 1`, `k + 2`; para las cohortes de la tabla, 202610 y 202620). V-3 traduce el horizonte en semestres de T3 a años calendario a partir del corte. Cuando parte del horizonte ya ocurrió (202610 en V-2), se muestra al lado lo observado hasta hoy, sin mezclarlo con lo esperado.
- **Estudiantes actuales:** pregrado con matrícula o intentos en 202610 y sin egreso, titulación ni eliminación registrados al cierre de 202610.
- **V-4:** aplica a todos los estudiantes actuales el reglamento vigente desde 202520 (Art. 46): 6 reprobaciones de 2.ª oportunidad en la carrera, o 2 cursos distintos reprobados en 3.ª oportunidad, con las funciones de `pipelines/snapshots/rules_variables.py`. Las categorías son excluyentes: «en el umbral», «a 1» y «a 2», definidas por la menor de las dos distancias. Por P58 los conteos son cotas inferiores, y el bloque lo dice.
- **R-2:** se usan la prueba (202310–202420) y la posterior (202510–202520) como ventanas separadas, cada una rotulada con sus años, sin mezclarlas. Agrega por `codigo_asignatura` y `depto` del snapshot T2.
- **Celdas pequeñas:** en toda distribución con total conocido (E-2, P-4, P-5, R-4), las celdas con n < 10 se agrupan en «otros». Si «otros» también queda bajo 10, se oculta la distribución completa del grupo. Es una regla única del exportador.

## Lo que queda al constructor
- Gráfico concreto de cada bloque nuevo, con las primitivas de `NeuralUI.tsx` y el patrón de `lib/neuralGraficos*.ts`.
- Ventanas exactas de años para R-1, R-4, E-2 y E-3, mientras queden indicadas en el bloque.
- Duración nominal de cada programa: derivarla de la malla (semestre máximo de `asignatura_malla`) si no hay un campo explícito, documentando la regla.
- Cómo se divide el trabajo entre módulos de Redes, siempre que se respeten las restricciones.
