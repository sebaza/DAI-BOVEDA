# Plan de implementación — Percepción a partir de los papers

Fecha: 2026-08-11 · Estado: **A0 y A1 IMPLEMENTADOS** · el resto, propuesta para triaje

> **Implementado el 2026-08-11** (154 tests verdes, `tsc --noEmit` limpio):
> `A0` completo —corrección no destructiva, registro de confirmaciones, muestreo
> aleatorio con semilla fija, `replay_correcciones()`, y el rescate de las
> probabilidades destruidas— y `A1` completo —`services/percepcion/calidad.py`,
> `GET /percepcion/curacion/calidad`, `GET /percepcion/curacion/correcciones` y el
> bloque «Calidad del modelo» en la pestaña Curación—.
> Detalle al final, en **«Qué quedó implementado»**.
>
> `A2` sigue **bloqueada** a propósito: necesita `F′` (anotación humana), que es
> tiempo de personas, no de código.

Insumos: `paper5` (RollingLDA / conflictos socioambientales, Rieger et al. — con Keith-Norambuena
y Rojas-Córdova, UCN), `paper1` (Agenda-based Narrative Extraction, Keith-Norambuena et al., UCN),
[Narrative Maps](https://dl.acm.org/doi/10.1145/3432927) (Keith Norambuena & Mitra, CSCW),
Concordia (DeepMind) y AgentSociety (Tsinghua).

Cada iniciativa lleva una ficha fija para poder aceptarla o descartarla sola. La columna
**"qué se mueve"** está etiquetada por calidad de la estimación:

- **MEDIDO** — el número sale de los datos reales, ya está verificado.
- **ACOTADO** — se puede poner un techo o un piso, pero el valor exacto exige el experimento.
- **ESPECULATIVO** — no hay forma honesta de estimarlo sin construirlo.

---

## 0. Hechos medidos que condicionan todo el plan

Sobre `percepcion_real.db` (2.790 comentarios, 2022-04-12 → 2026-08-05):

| Hecho | Valor | Consecuencia |
|---|---|---|
| Largo de comentario | **mediana 3 palabras**, 56,3% ≤3, 84% ≤10 | LDA a nivel comentario es **inviable** |
| Vocabulario útil | 4.642 tipos, solo **211 con freq ≥ 10** | Techo duro para todo método bag-of-words |
| Comentarios por post | mediana 2 | Los pseudo-documentos por post tampoco alcanzan |
| Captions | 2.555, **mediana 60 palabras** | Único corpus con densidad para LDA clásico |
| Sesgo temporal | 2022:49 · 2023:41 · 2024:116 · 2025:613 · **2026:1.971** | Ventanas de RollingLDA en MESES, no años |
| Sentimiento | POS 45,8% · NEU **45,7%** · NEG 8,5% | El balde NEU es casi la mitad del corpus |
| Correcciones | 376 filas, **100% son desacuerdos**, autor = script en 375 | **No es un set de validación, es un log de defectos** |
| Ground truth de tema | **290** comentarios con `tema_confianza = 1.0` | Sí sirve para validar un clasificador nuevo |
| Modelo actual | `pysentimiento/robertuito-sentiment` (+ variantes `reglas_chile`, `emocion_ucn`) | RoBERTuito: español de Twitter, buena elección de base |

### 0.1 Qué son realmente las 376 correcciones (confirmado por el usuario, 2026-08-11)

`auditoria-contextual-v4` y `auditoria-v9` son **dos pasadas de un agente LLM** sobre los comentarios
de la primera percepción, aplicadas a través de la herramienta de corrección manual para agilizar.
Es decir: **LLM-as-judge**, no anotación humana. El paradigma es legítimo y `paper1` lo valida — pero
la implementación tiene tres problemas medidos, y los tres condicionan el plan.

**(1) La corrección es DESTRUCTIVA.** `curacion.corregir_sentimiento()` sobrescribe
`prob_pos/prob_neu/prob_neg` con los valores sintéticos de `_PROBS_SENT` (0,90/0,05/0,05).
Medido: **262 scores tienen ese patrón**. En los comentarios donde se conoce la respuesta correcta,
**la salida original del modelo ya no existe** — y es exactamente el insumo que necesita cualquier
recalibración. Consecuencia directa: `A2` pierde su mejor conjunto de entrenamiento.

*Recuperable*: `pysentimiento/robertuito-sentiment` es determinista. Re-puntuar esos 262 textos con
el modelo original devuelve las probabilidades exactas. Es barato y hay que hacerlo antes de que se
pierda el rastro.

**(2) v4 y v9 no son dos jueces independientes.** Son pasadas SECUENCIALES: v9 corrió después y vio
el estado ya corregido por v4. Solo se solapan en **4 comentarios**, y en esos **coinciden 0 de 4**
(v4=NEG → v9=NEU, las cuatro veces). Con n=4 no se puede concluir mucho, salvo lo importante: el
desacuerdo es **sistemático, no aleatorio**. `paper1` exige jueces de **familias distintas** y reporta
fiabilidad inter-juez (Pearson r=0,88 en alineación); acá no hay ni una cosa ni la otra.

**(3) Sesgo direccional medido en ambos auditores**:

| Auditor | Correcciones | Van hacia POS | Patrón dominante |
|---|---|---|---|
| `auditoria-contextual-v4` | 136 | **123 (90%)** | NEU→POS: 105 |
| `auditoria-v9` | 129 | **104 (81%)** | NEU→POS: 104 |

Un juez que mueve el 81-90% de sus fallos en una sola dirección admite dos lecturas —
**(a)** el modelo sub-detecta positivos de verdad, o **(b)** el agente LLM tiene sesgo de positividad
(conocido y documentado en LLMs sobre texto social ambiguo)— y **no se pueden distinguir sin una
referencia neutral**. Hoy esa referencia no existe. Esto es precisamente lo que `paper1` resuelve con
**controles negativos**.

**Lo que se hizo BIEN y hay que formalizar**: las justificaciones dicen *"caption de publicación"* —
cada comentario se juzgó **con el post al que responde**. Con mediana de 3 palabras, evaluar un
comentario aislado es imposible. Esto pasa a ser regla obligatoria para `F` y entra como decisión de
diseño en `B` (el embedding del comentario debería incorporar el contexto del caption).

**Lo que NO se puede reusar**: el campo `justificacion` trae el mismo texto de lote repetido en todas
las filas, no el razonamiento por caso. No hay explicación individual de la que aprender.

**La dirección de los desacuerdos** (261 comentarios con corrección de sentimiento):

| Modelo dijo | Humano/script dijo | Casos | % |
|---|---|---|---|
| NEU | **POS** | **209** | **80,1%** |
| NEG | NEU | 23 | 8,8% |
| NEG | POS | 17 | 6,5% |
| NEU | NEG | 11 | 4,2% |
| POS | NEG | 1 | 0,4% |

Cuatro de cada cinco desacuerdos son **el modelo marcando NEU algo que era POS**. Y en el corpus
completo hay **789 comentarios NEU cuya `prob_pos` supera a `prob_neg`**: neutrales que se inclinan
a positivo. Las dos señales apuntan al mismo lugar.

En emoción, 110 correcciones con dos patrones claros:
`sin_emocion → joy` (32) y `sin_emocion → anger` (24) = **56 casos donde el modelo no vio emoción y
la había**; `joy → empatia` (31) y `sadness → empatia` (16) = **47 casos que aterrizan en `empatia`**,
una clase que el modelo prácticamente no usa.

---

## Fase 0 — Habilitadores. Sin esto no se puede medir ninguna mejora

### A0 · Convertir el log de defectos en un conjunto de validación

**Qué**: registrar también las **confirmaciones** (el revisor dice "está bien" y queda la fila),
separar `autor_humano` de `autor_script`, y guardar de qué muestreo salió el caso
(`orden=duda` vs `reciente`).

**Por qué es lo primero**: `curacion.corregir_sentimiento()` guarda siempre, pero los scripts de
auditoría solo llamaron cuando querían cambiar algo. Resultado: 376 filas, 376 desacuerdos, cero
aciertos. Sin los aciertos no hay denominador y **el accuracy es literalmente incalculable**.

Y hay un segundo sesgo que hay que declarar sí o sí: la cola ordena por `orden="duda"` (menor margen
entre la clase ganadora y la segunda), o sea que dirige al revisor a donde el modelo es peor. Eso es
lo correcto para curar y lo peor posible para medir: cualquier accuracy calculado ahí es un
**piso pesimista**, no el número real. Si no sale escrito en pantalla, el número miente.

**Cuánto sesgo hay, medido** (posible recién tras el rescate de las probabilidades originales): el
margen mediano de lo corregido es **0,318** contra **0,488** del corpus completo, y el 36% cae bajo
0,2 contra el 15% del corpus. O sea que **sí hay** inclinación hacia lo dudoso, pero **es moderada**:
el 64% de las correcciones cayó sobre casos donde el modelo estaba razonablemente seguro, y hay 27 en
el tramo 0,7–1,0. La versión anterior de este informe decía que se habían atacado *solo* los casos
difíciles; eso era incorrecto. Buena noticia para usar los datos, peor noticia sobre el revisor: dar
vuelta una predicción de 0,916 de confianza es una decisión fuerte.

**Requisito nuevo y no negociable: la corrección deja de ser destructiva.** Hoy sobrescribe las
probabilidades del modelo (262 scores ya perdidos, ver §0.1). La corrección debe ser una **CAPA que
se aplica en lectura**, no una sobreescritura de `percepcion_score`.

Esto resuelve **dos** problemas de un saque:
1. Preserva la salida original del modelo, que es el insumo de toda calibración y de toda métrica de
   margen.
2. Mata el gotcha que el propio docstring de `curacion.py` advierte: *"si luego se re-clasifica TODO
   en el worker (reset tema=None), la curación manual se pierde"*. Con la corrección como capa, un
   re-scoring completo del worker **ya no destruye el trabajo de curación**.

**Tarea previa de rescate**: re-puntuar los 262 comentarios afectados con
`pysentimiento/robertuito-sentiment` (determinista ⇒ recuperación exacta) para restituir las
probabilidades originales antes de perder el rastro.

- **Dónde vive**: Torre. `services/percepcion/curacion.py`, `models.py` (columnas nuevas en
  `percepcion_correccion`), `routers/percepcion.py`, `PercepcionCuracion.tsx`.
- **Esfuerzo**: chico-medio (~250 líneas + tests + script de rescate).
- **Qué se mueve**: **MEDIDO** — de "accuracy incalculable" a "accuracy calculable". De 0 a 1.
  Y se recuperan 262 probabilidades hoy destruidas.
- **Riesgo**: bajo. `percepcion_correccion` **no** la toca `reagregar()`, así que no aplica el gotcha
  de la columna perdida. Ojo: pasar la corrección a capa **sí** toca `reagregar()`, que debe leer el
  valor corregido en vez del crudo.
- **Depende de**: nada. **Es el punto de partida del plan.**
- **Se verifica**: (a) test que corrige sin cambiar valor y comprueba que igual queda la fila con
  `confirmado=True`; (b) test que corrige y comprueba que `prob_*` del modelo **NO** cambió;
  (c) test que simula un re-scoring del worker y comprueba que la corrección sobrevive.

### A1 · Panel de calidad del modelo

**Qué**: endpoint `GET /percepcion/curacion/calidad` + bloque en la pestaña Curación con matriz de
confusión, kappa de Cohen, desglose por tema y por rango de margen, y el aviso de sesgo de muestreo.

**Lo que ya se puede mostrar hoy, sin esperar a A0**: la **matriz de desacuerdos**. Que el 80,1% de
los errores conocidos sean NEU→POS es información accionable por sí sola, y hoy no la ve nadie —
`curacion.correcciones_recientes()` existe en `curacion.py:403` y **no la llama ningún endpoint**.

- **Dónde vive**: Torre. `repository.py` o módulo nuevo `calidad.py`, router, componente nuevo.
- **Esfuerzo**: medio (~300 líneas + tests).
- **Qué se mueve**: **MEDIDO** — el módulo pasa de no tener ninguna métrica de calidad a tener la
  primera. Todo lo demás del plan se mide contra este baseline.
- **Riesgo**: bajo. El riesgo real es de lectura: publicar un accuracy sin el aviso de sesgo.
- **Depende de**: A0 para el accuracy honesto; la matriz de desacuerdos va sin dependencias.

---

## Fase 1 — Barato, sin romper nada de lo ya presentado

### F′ · Anclaje humano: 150 comentarios anotados al azar ⟵ **PRIORIDAD ALTA (era Fase 2)**

**Qué**: anotación **humana** de una muestra **aleatoria** de ~150 comentarios (con el caption de la
publicación a la vista, como se hizo en las auditorías), con dos anotadores y medición de acuerdo
entre ellos.

**Por qué subió de fase**: §0.1 dejó al descubierto que **todo el conocimiento actual sobre la
calidad del modelo proviene de un juez LLM con sesgo direccional de 81-90%**, sin referencia neutral
que permita distinguir "el modelo falla" de "el juez sesga". Sin ancla humana, `A2` y `F` miden
contra sí mismos. 150 casos es poco trabajo y es el cimiento de todo lo demás.

- **Dónde vive**: Torre (la cola de curación ya existe; solo hay que agregar `orden=aleatorio` y
  registro de confirmaciones vía `A0`).
- **Esfuerzo**: chico en código; el costo es **tiempo humano** (~2-3 horas de anotación).
- **Qué se mueve**: **MEDIDO** — de "no hay referencia neutral" a "hay referencia neutral". Habilita
  `A2` y convierte a `F` en algo calibrable.
- **Riesgo**: bajo. El único riesgo es no hacerlo y seguir construyendo sobre el juicio del juez.
- **Depende de**: A0 (muestreo aleatorio + registro de confirmaciones).

### A2 · Recalibrar el umbral NEU/POS del scorer ⟵ **BAJÓ de prioridad**

**Qué**: mover el punto de corte entre NEU y POS, o aplicar una capa de calibración
(Platt / temperature scaling) sobre las probabilidades de RoBERTuito.

**Evidencia**: 80,1% de los desacuerdos son NEU→POS, y hay 789 NEU con `prob_pos > prob_neg`.

**Por qué bajó** (revisión del 2026-08-11, tras §0.1): esa evidencia proviene **enteramente** de los
dos auditores LLM, que mueven el 81-90% de sus correcciones hacia POS. La señal es indistinguible de
un sesgo de positividad del propio juez. Y además **las 262 probabilidades originales que harían
falta para calibrar fueron sobrescritas**. Se mantiene en el plan porque la hipótesis sigue siendo
razonable, pero **ya no es la de mejor relación evidencia/esfuerzo**.

- **Dónde vive**: **WORKER** (el scoring no es de la Torre). La Torre solo lo ve reflejado.
- **Esfuerzo**: chico en código, medio en experimento.
- **Qué se mueve**: **ACOTADO**. Techo superior: hay 1.275 NEU (45,7%); si el corte se moviera hasta
  reclasificar los 789 que se inclinan a POS, el índice global subiría de forma grande. Piso: 121 NEU
  tienen `prob_neu < 0,5` (4,3% del corpus) y son los reclasificables sin discusión.
  **El valor real NO se puede estimar desde los 261 casos corregidos**: son muestra sesgada (elegidos
  por dudosos) *y* anotados por un juez con sesgo direccional medido.
- **Riesgo**: **ALTO en comparabilidad**. El índice se mueve para arriba y todo lo ya presentado a
  Alberto cambia de número. Hay que versionarlo y anunciarlo, no deslizarlo. Riesgo agravado: si el
  sesgo era del juez y no del modelo, se estaría "corrigiendo" hacia el error.
- **Depende de**: **A0 → rescate de las 262 probabilidades → F′ (ancla humana)**. Las tres, antes de
  tocar un umbral.

### D · Leave-one-out word impacts (paper5, §3.2)

**Qué**: `cos(t₁,t₂,k,V∖v) − cos(t₁,t₂,k,V)` sobre los vectores de conteo por tema entre dos
períodos. Responde **qué palabra específica movió un tema**, en vez de qué palabras hay.

Reemplaza el bloque "Las palabras que más pesan" del Resumen, que hoy usa una heurística inventada a
mano (ordenar por negativos absolutos) porque ya se descubrió que la frecuencia sola no sirve
(`felicitaciones`: 121 menciones, 0% negativo, sería la misma todos los meses). Buen instinto — esta
es la versión con fundamento publicado.

- **Dónde vive**: Torre, `repository.py`. **No necesita el modelo nuevo**: corre sobre los 8 temas
  actuales.
- **Esfuerzo**: chico (~60 líneas + tests).
- **Qué se mueve**: **ACOTADO** — el Resumen pasa de "qué se dice" a "por qué cambió". Con 211
  palabras de vocabulario útil el ranking puede ser inestable; hay que medir estabilidad entre
  períodos antes de publicarlo.
- **Riesgo**: medio-bajo. Vocabulario chico ⇒ posible ruido. Mitigación: exigir mínimo de
  apariciones en AMBOS períodos.
- **Depende de**: nada.

### E · Gini de prevalencia temática entre unidades (paper5, §3.3)

**Qué**: coeficiente de Gini de la distribución de un tema entre facultades/departamentos. Ellos lo
usan sobre regiones de Chile; acá aplica igual sobre sede/facultad/departamento.

Responde una pregunta que **el dashboard hoy no puede responder**: ¿este problema está concentrado
en una unidad o es transversal a la universidad? Para un director es la diferencia entre "es mío" y
"es de todos".

- **Dónde vive**: Torre, `repository.py` + `PercepcionComparar.tsx`.
- **Esfuerzo**: chico (~40 líneas + tests + UI).
- **Qué se mueve**: **ESPECULATIVO en magnitud, claro en naturaleza** — es una pregunta nueva, no un
  gráfico más. No mejora ningún número existente; agrega uno.
- **Riesgo**: bajo, con una condición: aplicar el resguardo de evidencia mínima
  (`N_MIN_EVIDENCIA = 30`) o una unidad con 4 comentarios devuelve un Gini sin sentido.
- **Depende de**: nada.

### C · Disciplina temporal: sin fuga de información del futuro (paper5, contribución central)

**Qué**: regla de que el modelo del período *t* se entrena **solo** con documentos ≤ *t* más una
ventana de memoria que se desvanece, y evaluación **walk-forward** en vez de aleatoria.

Hoy, si se reentrena el clasificador ve TODO el histórico —incluido 2026— y después se evalúa sobre
2025. Eso es fuga, e **infla cualquier métrica de calidad que se mida**. Es más regla metodológica
que código, y es lo más barato de adoptar de todo el paper.

- **Dónde vive**: **WORKER** (entrenamiento) + Torre (declararlo en `RotuloMetodo`).
- **Esfuerzo**: chico-medio.
- **Qué se mueve**: **MEDIDO en dirección, no en magnitud** — no cambia ni un pixel de la UI. Cambia
  si los números de calidad son creíbles. Con el 70% del corpus en 2026, las ventanas hay que
  pensarlas en MESES.
- **Riesgo**: bajo. El accuracy reportado va a **bajar** al eliminar la fuga. Eso es correcto, y hay
  que explicarlo o parece un retroceso.
- **Depende de**: A1 (si no hay panel de calidad, no se ve el efecto).

---

## Fase 2 — El cambio de fondo. Prueba de concepto ANTES de comprometerse

### B · Membresía blanda de temas por embeddings (Narrative Maps / paper1, §3.1)

**Qué**: reemplazar el clasificador de 8 cajas fijas por
**Sentence-BERT (multilingüe) → UMAP → HDBSCAN en modo soft clustering**, donde cada comentario
recibe una **distribución de probabilidad sobre temas** en vez de una etiqueta única.

Es el pipeline exacto de Narrative Trails, y es el que **sí tolera comentarios de 3 palabras**: los
embeddings no dependen de co-ocurrencia interna. Por eso esta es la maquinaria de `paper1`/Narrative
Maps y no el RollingLDA de `paper5`.

Dos consecuencias:
1. **Muere el balde "otros"** (385 comentarios, 13,8%). Un comentario deja de ser "otros" y pasa a
   ser 40% académico / 30% organización / 30% nada.
2. **`_indice()` ya trabaja con probabilidades, no con etiquetas.** La membresía blanda encaja con la
   matemática que ya está escrita.

**PoC obligatoria antes de comprometer nada** — y hay con qué medirla: los **290 comentarios con
`tema_confianza = 1.0`** son ground truth de tema. Criterio de éxito: los clusters emergentes deben
recuperar esas 290 asignaciones **mejor que los 8 temas actuales**. Si no lo logran, se descarta y
no se perdió más que la PoC.

- **Dónde vive**: **WORKER**. La Torre solo agrega una columna espejo (`tema_probs` JSON) en
  `models.py` y la contempla en `reagregar()`.
- **Esfuerzo**: **grande**. Es el proyecto de fondo del plan.
- **Qué se mueve**: **ACOTADO** — 385 comentarios (13,8%) dejan de estar en un balde sin significado.
  La calidad del resultado es **ESPECULATIVA** hasta la PoC.
- **Riesgos** (varios y reales):
  - Con 211 palabras útiles y textos de 3 palabras, los clusters pueden salir incoherentes.
  - **Rompe la comparabilidad histórica**: todo lo ya presentado cambia de número.
  - Los temas emergentes **no tienen nombre**; hay que etiquetarlos a mano o con LLM (`paper5` lo
    propone en su discusión).
  - HDBSCAN puede mandar una fracción grande a ruido — que es "otros" con otro nombre.
- **Depende de**: A1 (para saber contra qué se compara), y coordinación con el repo del worker.

### F · Evaluación multi-juez con controles negativos (paper1, §3.6) ⟵ **ya no es opcional**

**Qué**: dos jueces LLM **de familias distintas** (ellos usaron Claude Opus 4.5 + GPT 5.1) puntuando
una muestra de comentarios **con el caption de la publicación como contexto**, más **casos control**
cuya respuesta correcta se conoce. Ellos validaron el marco midiendo que las contra-agendas puntúan
bajo (2,24-2,49) frente a las reales (4,78-6,91): si el control negativo puntúa alto, el método está
fabricando.

**Esto NO es una técnica nueva a introducir: es la corrección metodológica del procedimiento que ya
se usó.** Las auditorías v4/v9 fueron LLM-as-judge —enfoque correcto— pero ejecutado como *un juez
dos veces en secuencia*, sin familias distintas, sin fiabilidad inter-juez y sin controles negativos.
`paper1` da la receta exacta para hacerlo bien, y lo ya construido (cola de revisión, herramienta de
corrección, contexto por caption) se reaprovecha casi entero.

Sirve además para **evaluar sobre muchos más comentarios de los que un humano alcanza a anotar**:
las 150 anotaciones humanas de `F′` calibran al juez, y el juez escala a miles.

- **Dónde vive**: Torre, **script offline** (`_evaluar_scorer_percepcion.py`), NO endpoint en
  caliente — el costo por request en Cloud Run no lo justifica.
- **Esfuerzo**: medio.
- **Qué se mueve**: **ESPECULATIVO** — amplía la cobertura de evaluación de ~300 casos anotados a
  miles. No mejora el modelo; mejora lo que sabés de él.
- **Riesgo**: costo de API; y si el juez comparte familia con el scorer, comparte sesgo. Por eso son
  dos modelos distintos, y por eso van los controles negativos.
- **Depende de**: A0/A1 (hace falta el ground truth humano para calibrar al juez antes de confiar en él).

### H · RollingLDA sobre los captions (opcional)

**Qué**: aplicar el modelo de `paper5` tal cual sobre los 2.555 captions (mediana 60 palabras), que
es el único corpus con densidad léxica suficiente. Librería `ttta`, `LDAPrototype` para
reproducibilidad (medoide de N corridas), K y α elegidos por expertos de dominio.

**Ojo con qué mide**: la **agenda institucional** (de qué habla la UCN), no la percepción de la
comunidad. Es otra pregunta. Ahora bien, **la brecha entre ambas es en sí misma un hallazgo**: si la
UCN publica sobre X y la comunidad responde sobre Y, eso es información de gestión.

- **Dónde vive**: worker o script aparte.
- **Esfuerzo**: medio.
- **Qué se mueve**: **ESPECULATIVO** — feature nueva, no mejora de las existentes.
- **Riesgo**: alcance. Puede terminar siendo una pestaña linda que no responde la pregunta del módulo.
- **Depende de**: nada, pero compite por tiempo con B.

---

## Lo que recomiendo DESCARTAR en esta ronda

### G · Extracción de narrativas (Narrative Maps / Trails / agenda-based) sobre el corpus

El algoritmo es excelente y es de la casa, pero opera sobre **documentos-evento**: noticias con
título y texto completo. Ellos evaluaron sobre 418 artículos de las protestas cubanas de 2021. Tu
unidad es un comentario de 3 palabras. Sobre los captions sería técnicamente posible, pero volvés a
medir la agenda institucional, y para eso `H` es más barato.

**Qué sí me llevaría de `paper1` igual**: el marco de evaluación (`F`), y el hallazgo de que
**el estilo de prompt le gana a cualquier hiperparámetro** (CoT: +25,7% de alineación, p=0,017, a
5× el tiempo; los hiperparámetros ni siquiera dieron significativos). Si algún día entra un LLM al
lazo de clasificación, ese dato ahorra semanas de tuneo inútil.

### Simulación (Concordia / AgentSociety) — fase 2 del proyecto, con una condición

De los dos, **AgentSociety le pega más al dominio**: valida contra 5 experimentos sociales reales,
dos de ellos son exactamente lo tuyo (**polarización** y **propagación de mensajes inflamatorios** —
la dinámica del paro). **Concordia** es el ladrillo práctico: librería, patrón Game Master, no exige
10k agentes ni MQTT ni cómputo distribuido.

**La condición**: el argumento central de AgentSociety es *"the alignment between AgentSociety's
outcomes and real-world experimental results"*. El ground truth de esa alineación sería el índice de
percepción. **Si el índice no está validado, la simulación se alinea contra ruido y no te enterás.**

Por eso la Fase 0 de este plan no es un desvío antes de la simulación: es su requisito.

---

## Orden propuesto (revisado 2026-08-11)

```
A0 (no destructiva + confirmaciones)
 │
 ├─► rescate: re-puntuar los 262 scores sobrescritos
 │
 ├─► A1 (panel de calidad)
 │    │
 │    ├─► F′  (150 anotaciones HUMANAS al azar)  ◄── el ancla que hoy no existe
 │    │        │
 │    │        ├─► F   (multi-juez calibrado + controles negativos)
 │    │        └─► A2  (recalibrar NEU/POS)
 │    │
 │    ├─► C   (disciplina temporal)
 │    └─► B   (soft topics, con PoC de por medio)
 │
D, E ── independientes, se pueden hacer en cualquier momento
```

**Si hubiera que elegir UNA sola cosa**: `A0`, y ahora con más razón que antes. No solo desbloquea la
medición: **detiene una pérdida de datos que está ocurriendo cada vez que alguien corrige algo.**

**Si hubiera que elegir la de mejor relación evidencia/esfuerzo**: `F′`. Dos o tres horas de
anotación humana sobre 150 comentarios al azar es el cimiento que le falta a TODO lo demás. Sin ella,
`A2` y `F` se miden contra el mismo juez que hay que auditar.

*(Nota: en la primera versión de este informe `A2` ocupaba este lugar. Bajó al descubrirse el sesgo
direccional de 81-90% de los auditores y la sobreescritura de las 262 probabilidades — ver §0.1.)*

---

## Pendientes transversales (no salen de los papers, pero condicionan todo)

1. ~~**¿Qué son `auditoria-contextual-v4` y `auditoria-v9`?**~~ **RESUELTO 2026-08-11**: dos pasadas
   de un agente LLM sobre los comentarios de la primera percepción, aplicadas vía la herramienta de
   corrección manual. Consecuencias completas en §0.1.
2. **La brecha de producción sigue abierta**: `PERCEPCION_DATABASE_URL` no está en
   `cloudrun.backend.env.yaml` ni en ningún `.bat`; `*.db` está en `.gitignore`. Toda mejora de este
   plan se ve en localhost y en ningún otro lado.
3. **El worker es otro repositorio.** `A2`, `C` y `B` viven allá. Cualquier columna nueva en la tabla
   de hechos hay que espejarla en `models.py` **y** en `reagregar()`, o se pierde en toda la tabla
   (ya pasó una vez con `origen`).

---

## Qué quedó implementado (2026-08-11)

### A0 — La revisión dejó de destruir datos

| Archivo | Cambio |
|---|---|
| `services/percepcion/models.py` | `PercepcionCorreccion` suma `confirmado`, `modelo_orig`, `prob_{pos,neu,neg,emocion}_orig`, `autor_tipo`, `origen_muestra`. Constantes `AUTOR_HUMANO/AGENTE` y `MUESTRA_DUDA/RECIENTE/ALEATORIA`. |
| `services/percepcion/db.py` | `_asegurar_columnas()`: ALTER TABLE idempotente para las tablas **propias de la Torre**. `create_all(checkfirst=True)` crea tablas ausentes, nunca columnas — sin esto las 376 filas existentes jamás verían el esquema nuevo. No toca las tablas espejo del worker. |
| `services/percepcion/curacion.py` | `corregir_*` congela la salida del modelo ANTES de pisar el score; registra confirmaciones (`confirmado=True`) y ya no reagrega cuando no cambió nada; acepta `autor_tipo`/`origen_muestra`. `_snapshot_modelo()` reusa el snapshot previo si el score ya venía pisado. `replay_correcciones()` re-aplica la curación tras un re-scoring del worker. `comentarios_para_scoring()` suma `orden=aleatorio` con semilla fija y devuelve el `caption` del post. |
| `_rescatar_probs_percepcion.py` | Recupera las probabilidades desde el respaldo pre-auditoría. Dry-run por defecto. |

**Bug encontrado por un test, no por lectura**: `db.add(Corr(...))` arma el INSERT
desde el MODELO e incluye TODAS las columnas mapeadas, así que contra una base sin
migrar moría con *"table percepcion_correccion has no column named confirmado"*. Es
**la misma trampa que ya había costado la columna `origen`**; la solución también es
la misma: INSERT por el Core (`_insertar_correccion()`), que manda solo las claves
presentes.

**Rescate verificado sobre copia de la base real: 376/376 = 100%.** (La estimación
previa de 261 contaba *scores*; las correcciones son 376 filas sobre 328 comentarios
y todas tenían su original en el respaldo del 05/08 13:57.)

### A1 — La primera métrica de calidad del módulo

`services/percepcion/calidad.py` + `GET /percepcion/curacion/calidad` +
`GET /percepcion/curacion/correcciones` + `PercepcionCalidad.tsx`.

Calcula matriz de confusión, acuerdo, **kappa de Cohen**, sesgo direccional del
revisor, y los cortes por autor, por tipo de muestra y por **margen ORIGINAL** del
modelo (posible gracias al rescate de A0).

**Regla de diseño**: los `avisos` los emite el SERVICIO, no la UI. Una métrica nueva
no puede publicarse por olvido sin su advertencia. Y cuando algo no se puede calcular
honestamente devuelve `None` con su motivo — nunca un `0.0` que se leería como
"el modelo nunca acierta" cuando lo que pasa es que los aciertos no se anotaron.

**Segundo bug propio, detectado al mirar la salida real**: el aviso de "falta
anotación humana" preguntaba *¿hay alguna?*, y con **1 fila humana entre 261** el
módulo declaraba que tenía referencia neutral. Corregido con `MIN_ANCLA = 30` (el
mismo umbral que `N_MIN_CONFIANZA` del resto del módulo) y cubierto con test.

### Lo que dice hoy sobre la base real

```
corpus 2790 · revisados 328 · cobertura 11,8%

[CRITICO]  El acuerdo no se puede calcular
[CRITICO]  No hay muestra aleatoria suficiente: falta el ancla
[CRITICO]  Sin anotación humana suficiente no hay referencia neutral
[ATENCION] Sesgo direccional en sentimiento

sentimiento  n=261  confirmaciones=0  acuerdo=None  kappa=None
  sesgo → Positivo: 226/261 = 87%
  Neutral→Positivo 209 · Negativo→Neutral 23 · Negativo→Positivo 17
  por margen:  0.0–0.2: 95 · 0.2–0.4: 107 · 0.4–0.7: 32 · 0.7–1.0: 27
  por autor:   agente 260 · humano 1

emocion      n=110  confirmaciones=0
  Sin emoción→Alegría 32 · Alegría→Empatía 31 · Sin emoción→Enojo 24
```

**Los 27 cambios en el bucket 0,7–1,0** son el dato nuevo que antes no se podía ver:
27 veces el revisor dio vuelta una predicción en la que el modelo estaba muy seguro.
Sin el rescate de A0 ese corte no existía.

### Verificación

```
backend\.venv\Scripts\python.exe -m unittest tests.test_percepcion   # 154 (126 + 28)
backend\.venv\Scripts\python.exe -m py_compile app/services/percepcion/*.py
cd frontend && npx tsc --noEmit
```

Contratos Pydantic validados contra la base real (`CalidadResponse`,
`CorreccionesResponse`, `ComentariosScoringResponse` en los tres órdenes) y muestra
aleatoria de 150 comprobada reproducible entre llamadas.

**Verificado en el navegador** (2026-08-11, backend 8011 + frontend 8001, `dev-login`):
`GET /percepcion/curacion/calidad → 200`, el bloque «Calidad del modelo» renderiza en
la pestaña Curación con los 4 avisos, la matriz y los cortes. Sin errores de consola
atribuibles al cambio (los que hay —`ChunkLoadError` de `animacion.ts`, CORS de
`/usuarios/me` y `/sorteo-personas/...`— son previos y de otros dominios).

**Muestra aleatoria probada en vivo contra la API** (`limite=150&orden=aleatorio`):

| | Valor | Lectura |
|---|---|---|
| Ítems | 150 | — |
| Reproducible entre llamadas | **sí** | dos revisores anotan el MISMO conjunto |
| Con caption | **150/150** | ningún comentario se juzga aislado |
| Margen mediano | **0,459** | ≈ el del corpus (0,488), **no** el de la cola por duda (0,318) |
| Bajo 0,2 | **26/150 = 17%** | ≈ el del corpus (15%), **no** el de la cola por duda (36%) |

Las dos últimas filas son la prueba de que la muestra **es realmente insesgada**: su
distribución de margen replica la del corpus y no la de la cola dirigida.

Ejemplo real devuelto: *«Q paso con los de geología»* (4 palabras, Neutral) con caption
*«Se convoca a pleno extraordinario para hoy lunes 8 de j…»*. Sin ese contexto el
comentario no es clasificable — que es exactamente por qué el caption viaja con él.

### Lo que falta para desbloquear A2

1. **Correr el rescate sobre la base real** (hoy solo se corrió sobre copia). Desde la
   raíz de la Torre, con el venv de la Torre; opera sobre el archivo del worker, que
   ya es la ruta por defecto del script:

   ```
   backend\.venv\Scripts\python.exe _rescatar_probs_percepcion.py            # dry-run
   backend\.venv\Scripts\python.exe _rescatar_probs_percepcion.py --aplicar
   ```

   El script **crea las columnas él mismo** si faltan (ALTER TABLE, no destructivo) y
   hace respaldo antes de escribir. Es idempotente: correrlo dos veces no rompe nada.
   No hace falta levantar el backend primero — esa dependencia de orden se eliminó
   porque era un paso invisible y fácil de olvidar. El backend igual las crea al
   arrancar (`db._asegurar_columnas()`); las dos vías son idempotentes y no se pisan.

2. **`F′`**: anotar ~150 comentarios con `orden=aleatorio`. Es tiempo humano.

**Dónde vive cada cosa** (fue una duda real, queda anotada):

| | Repo | Por qué |
|---|---|---|
| El script y el venv | **Torre** | El script es de la Torre y corre con `backend\.venv` |
| La base que modifica | **worker** (`Sentiment_Analisys_University/percepcion_real.db`) | El worker es el dueño de los datos |
| El respaldo del que lee | **worker** (`percepcion_real.db.bak-20260805-135722`) | Es el estado pre-auditoría |

La Torre local ya apunta a la base del worker: `config.py:11` hace
`load_dotenv(BASE_DIR / ".env")` sobre la RAÍZ del repo, y ahí está definida
`PERCEPCION_DATABASE_URL`. No es variable de entorno del sistema.

---

## Corrección posterior: `F′` no era usable (2026-08-11)

`A0` dejó el muestreo aleatorio en el backend y en el cliente TypeScript, pero
**inalcanzable desde la interfaz**. Detectado por el usuario al ir a usarlo.

Dos huecos, y el segundo es el grave:

1. **`percepcionApi.comentariosScoring()` no la llamaba nadie.** El endpoint
   `/percepcion/curacion/scoring` existía desde siempre y el frontend nunca lo usó:
   las correcciones se hacían inline en la lista de *Conversación*, que va por fecha
   y filtros globales. No había forma de pedir una muestra aleatoria.
2. **La UI IMPEDÍA confirmar.** `PercepcionPanel.tsx:390` rechazaba guardar si no
   cambiabas nada (*"No cambiaste nada"*). O sea que registrar «el modelo acertó» era
   literalmente imposible desde la aplicación — **esa es la causa de que las 376
   revisiones sean 376 desacuerdos** y de que el acuerdo no tenga denominador.

Es el mismo pecado que este informe le señalaba a `correcciones_recientes()`: código
escrito que nadie puede ejecutar. Una capacidad sin camino en la UI no existe.

**Solución**: `frontend/src/components/PercepcionRevision.tsx`, nuevo bloque «Cola de
revisión» en la pestaña Curación, entre Calidad y Curación de temas. El orden de los
tres bloques es deliberado: **MEDIR → ANOTAR → CURAR**.

- Selector de muestra (`Aleatorio` / `Donde el modelo dudó` / `Más recientes`) que
  **declara para qué sirve cada uno** — elegir mal invalida la medición sin que se note.
- **Botón «Está bien ✓»** cuando no hay cambios: manda el valor ACTUAL, el backend
  registra `confirmado=True`, no toca el score y no reagrega.
- El `caption` del post va ARRIBA del comentario, no al pie.
- `origen_muestra` viaja en cada anotación.
- Contador de progreso contra el objetivo (150) y el mínimo de ancla (30), que suma lo
  ya anotado antes — si no, cada recarga haría creer que se empieza de cero.

### Verificado en el navegador

25 fichas renderizadas, **25 botones «Está bien ✓»**, **25 con contexto del post**.
Payload capturado del botón de confirmación (interceptando `fetch` para **no escribir
en la base real**):

```
POST /percepcion/curacion/sentimiento/19  {"valor":"NEU","justificacion":"","origen_muestra":"aleatorio"}
POST /percepcion/curacion/emocion/19      {"valor":"sin_emocion","justificacion":"","origen_muestra":"aleatorio"}
```

Manda el valor actual (= confirmación) y etiqueta la muestra. Base real intacta tras
la prueba: 376 correcciones, 0 confirmaciones, `origen_muestra` NULL en las 376.

**Caso real que salió en la muestra** y que ilustra por qué esto hacía falta:

> *responde a:* «Les compartimos los acuerdos que se zanjaron el pasado viernes 3 de julio…»
> **«Gracias por nada feucn y atrasarnos un año más a los que esperábamos los cursos de invierno😮‍💨»**
> → el modelo dice **Neutral**

Sarcasmo negativo leído como neutro. Y notar que un enfoque por palabras clave vería
«Gracias» y lo daría por positivo: el error va en la dirección CONTRARIA al sesgo a POS
de los auditores LLM. Otra razón para no mover el umbral de `A2` sin ancla humana.

### Lo que NO se tocó

La edición inline de *Conversación* sigue como estaba (solo corrige, no confirma) y sus
anotaciones quedan con `origen_muestra` NULL — que es lo honesto: esa lista está
filtrada por los controles globales, no es ninguna de las tres muestras definidas.
