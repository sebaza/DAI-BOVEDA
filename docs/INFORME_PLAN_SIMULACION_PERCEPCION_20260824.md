# Simulación de percepción — plan de trabajo

**Fecha:** 2026-08-24 · **Estado:** fases 0 y 1 completas · **fase 2 medida y CERRADA** (08-09-2026)
**Antecedente:** `INFORME_PLAN_PERCEPCION_PAPERS.md` §"Simulación (Concordia / AgentSociety)"

---

## 0. Resultado, para quien lee esto después *(agregado 2026-09-08)*

El plan se ejecutó hasta la fase 2. **El modelo poblacional se midió y no se integra**, que
es uno de los desenlaces que el propio plan declaraba aceptable (§4, fase 1: *"es
enteramente posible que la fase 1 cierre el proyecto, y eso sería un éxito"*).

| fase | estado | resultado |
|---|---|---|
| 0.1 calendario | ✅ | 109 eventos cargados (el plan se escribió con **1**) |
| 0.2 banco de episodios | ✅ | 11 episodios, 7 medibles |
| 0.3 métrica + barra de error | ✅ | `error_irreducible` + `indistinguible_del_techo` |
| 0.4 corte temporal | ✅ | walk-forward, no corte único |
| **1 · baselines** | ✅ | vara **MAE 6,82** sobre la serie del tablero |
| **2 · modelo poblacional** | ❌ **no se integra** | no supera la vara: 7,50–7,71 contra 6,82 |
| 3 · Concordia | no corresponde | la fase 2 no dejó una brecha identificable que justifique agentes |

**Tres cosas que el plan suponía y NO están en los datos:**

1. **No hay contagio.** La regresión de ΔI sobre I(t) da −0,594; descontado el sesgo por
   error de medición (−0,113) queda **−0,481 → φ = 0,52**. Es reversión a la media con
   vida media de ~1,1 semanas, no autorefuerzo. El término β·A·(1−A) de un modelo tipo
   SIR no tiene nada que ajustar.
2. **Los eventos no aportan sobre el estado previo.** Residuo de las semanas disruptivas
   tras descontar la reversión: **−2,22 ± 2,03**. El signo va donde se esperaba y el
   error estándar es del mismo tamaño.
3. **La composición aporta in-sample y no sobrevive.** Sumar adverso+favorable sube el R²
   de 0,16 a 0,26 con los datos a la vista; walk-forward el modelo **empeora**.

**Walk-forward honesto, 74 semanas evaluadas, misma serie y mismo protocolo:**

```
suavizado exponencial (1 parámetro)     6,82   <- la vara nueva
media_movil (la vara anterior)          7,31
regresión · índice                      7,48
POBLACIONAL + evento                    7,50
POBLACIONAL · índice+adverso+favorable  7,54
regresión · índice+adverso              7,71
```

**El resultado sale al revés de lo que el plan esperaba: lo que mejora el pronóstico es
MENOS modelo, no más.** Un suavizado exponencial de un solo parámetro, calibrado sobre el
pasado, le gana a todo lo demás — y es coherente con la reversión medida, porque pesar las
semanas por antigüedad es la forma correcta de promediar una serie con φ≈0,52.

### El techo real no es el error irreducible

`error_irreducible` (2,86) mide solo el ruido de **muestreo**. No es el techo de un
pronóstico: casi toda la variación del índice es señal real e impredecible desde el pasado.
La cota medida —el mejor modelo lineal con **seis** parámetros ajustado in-sample, o sea con
ventaja injusta— es **MAE 6,22**, con R² 0,30.

```
vara honesta (suavizado)                        6,82
cota superior in-sample, ventaja injusta        6,22
margen máximo que queda                         0,60
mínimo detectable con 74 semanas (2 ee)         0,58
```

**El margen restante es prácticamente igual a lo mínimo demostrable.** Un modelo que
alcanzara la cota teórica sería indistinguible del ruido con la cantidad de semanas que hay.
Esa es la razón de fondo por la que la fase 3 no corresponde: no es que los agentes
generativos no sirvan, es que **no habría cómo probar que sirven**.

### Qué destrabaría la fase 2, si alguna vez se retoma

No un modelo más sofisticado. Cualquiera de estos tres:

* **Más semanas evaluables** — el mínimo detectable baja con √n. Para demostrar 0,3 puntos
  harían falta ~280 semanas evaluables (hoy 74).
* **Más comentarios por semana**, que bajaría el ruido de muestreo y ensancharía la franja.
* **Postura independiente del tono** — hoy `postura_de()` la deriva del tono, así que la
  composición favorable/adverso lleva menos información de la que parece. Ver
  `services/percepcion/postura.py`.

Detalle técnico y tests: `backend/tests/test_percepcion_suavizado.py` y
`test_percepcion_serie_validacion.py`.

---

## 1. La condición que puso el plan original, y cómo está hoy

El informe de papers dejó la simulación en fase 2 **con una condición explícita**:

> "El argumento central de AgentSociety es *the alignment between AgentSociety's outcomes
> and real-world experimental results*. El ground truth de esa alineación sería el índice
> de percepción. **Si el índice no está validado, la simulación se alinea contra ruido y
> no te enteras.**"

Esa condición **se cumplió, pero solo en parte**:

| dimensión | acierto | techo humano | ¿sirve como ground truth? |
|---|---|---|---|
| sentimiento (alimenta el índice) | **88,7 %** | 86,3 % | **Sí** — está por encima del techo del anotador |
| emoción | 84,0 % | 98,8 % | Con reservas |
| postura | 75,3 % | – | Con reservas |
| tema | **55,3 %** | 92,5 % | **No** — alinear contra temas es alinear contra ruido |

**Consecuencia para el plan:** una simulación puede validarse contra **el índice**. No
contra la composición temática. Cualquier diseño que dependa de "qué temas emergen" está
apoyado en un clasificador que acierta la mitad de las veces.

---

## 2. Lo que dicen los datos, medido hoy

Cinco mediciones sobre `percepcion_real.db` (3.008 comentarios, 2022-04 → 2026-08). No
son estimaciones: son consultas, reproducibles.

### 2.1 No hay trayectorias individuales

```
autores únicos                    1.916
comentaron UNA sola vez           1.474  (76,9 %)
comentaron 2 veces                  274
el más activo                        50 comentarios
```

**Esto es lo más determinante del informe.** Concordia y AgentSociety modelan
*individuos* con memoria, personalidad y evolución de opinión. Para validar eso hace
falta observar a la misma persona a lo largo del tiempo. En este corpus, **3 de cada 4
personas aparecen una vez y no vuelven**.

No es un problema de volumen que se arregle ingestando más: es la naturaleza del dato.
Un comentario de Instagram es una reacción anónima, no una biografía.

### 2.2 Hay señal real, pero el ruido es de la mitad de su tamaño

```
semanas con n≥20                     33
índice: media 64,8 · sd observada  6,99  (rango 40,6 – 76,8)
sd esperada solo por muestreo      3,99
ratio observada/muestreo           1,75
```

Descomponiendo (`sd_señal = √(6,99² − 3,99²)`): de los ~7 puntos de variación semanal,
**~5,7 son señal real y ~4,0 son ruido de muestreo**.

**Consecuencia:** hay algo que simular. Pero cualquier validación semana a semana lleva
una barra de error de **±4 puntos de índice**. Una simulación que acierte dentro de esos
±4 no se distingue de la suerte, y hay que decirlo antes de construirla, no después.

### 2.3 Casi no hay episodios contra los cuales validar

```
anomalías detectadas en TODO el corpus     8   (todas entre 03 y 07/2026)
comentarios con léxico de conflicto       47   de 3.008  (1,6 %)
eventos institucionales cargados           1
```

Los dos experimentos de AgentSociety que "le pegan al dominio" son **polarización** y
**propagación de mensajes inflamatorios**. Para calibrar cualquiera de los dos hacen
falta episodios observados. Hay 8, y 47 comentarios de conflicto en cuatro años.

**Con 8 episodios y ±4 puntos de error no se valida una dinámica de propagación.** Se
puede contar una anécdota, que es otra cosa.

### 2.4 Las semanas útiles son 33, no 127

El bloque de resumen navega 127 semanas, pero solo 33 llegan a n≥20. El resto tiene
volumen demasiado bajo para calcular un índice estable.

### 2.5 La palanca más barata está sin usar

`percepcion_evento` tiene **1 fila**. El calendario académico de la UCN (matrícula,
exámenes, receso, titulación, admisión, paros conocidos) es información que ya existe,
es gratis de cargar, y es **la variable causal más obvia** de la percepción semanal.

Hoy la simulación no tendría contra qué contrastar sus causas, porque las causas reales
no están registradas.

---

## 3. Lo que NO recomiendo hacer, y por qué

**No empezar por AgentSociety.** Su propuesta de valor es la validación contra
experimentos sociales reales. Sin trayectorias individuales (§2.1) y con 8 episodios
(§2.3), esa validación no se puede reproducir acá. Quedaría el andamiaje sin el
argumento — 10k agentes, MQTT y cómputo distribuido para producir un número que nadie
puede contrastar.

**No empezar por agentes con memoria individual.** Mismo motivo: el 77 % de la población
no tiene historia observable. Se estaría simulando una estructura que los datos no
registran, y "se ve razonable" no es un criterio de aceptación.

**No alinear contra composición temática.** El clasificador de temas acierta 55,3 %.

Nada de esto dice "la simulación no sirve". Dice **en qué orden hay que construirla para
que en algún momento se pueda saber si sirve.**

---

## 4. El plan, en cuatro fases

El principio es el mismo que ya funcionó en este módulo: **primero el patrón de medida,
después el modelo.** El panel de calidad se construyó antes de tocar el scoring, y por
eso hoy se puede afirmar 88,7 % en vez de "anda bien".

### Fase 0 — El gimnasio de validación *(sin esto, todo lo demás es opinión)*

Construir el banco de pruebas **antes** de simular nada.

| # | Tarea | Entregable |
|---|---|---|
| 0.1 | Cargar el calendario académico real en `percepcion_evento` | ~40–60 eventos con fecha, tipo y ámbito |
| 0.2 | Extraer los episodios observados (anomalías + picos de léxico) con su ventana antes/después | dataset de episodios, hoy 8 |
| 0.3 | Definir la métrica de acierto y su barra de error | función de scoring versionada |
| 0.4 | Partir la serie en train/test **por tiempo**, nunca al azar | corte fijo y documentado |

**0.1 es la de mejor relación evidencia/esfuerzo de todo el plan.** Sin causas
registradas, ningún modelo puede explicar nada; con ellas, hasta una regresión simple
empieza a decir algo.

⚠️ El corte train/test **tiene que ser temporal**. Partir al azar deja semanas futuras en
el entrenamiento y produce un acierto que no existe fuera del experimento.

### Fase 1 — Los baselines tontos *(la vara que la simulación debe superar)*

Antes de un solo agente, cuatro modelos triviales sobre el índice semanal:

1. **Persistencia** — "la semana que viene será igual a esta".
2. **Media móvil** de k semanas.
3. **Estacionalidad académica** — el mismo período del año anterior.
4. **Regresión sobre eventos** — usando el calendario de 0.1.

**Criterio de aceptación de todo el proyecto:** una simulación que no le gane a estos
cuatro, con la barra de error de ±4 puntos incluida, **no se integra**. Es la misma
disciplina que ya descartó embeddings (50,7 % vs 55,3 % de keywords) y al juez LLM
(52,3 % vs 90,0 % de una regla de cuatro líneas). Los dos resultados negativos ahorraron
semanas.

**Es enteramente posible que la fase 1 cierre el proyecto**, y eso sería un éxito: costó
días en vez de meses.

### Fase 2 — Simulación POBLACIONAL, no individual

Si la fase 1 deja margen: modelar **segmentos**, no personas. Los datos soportan
segmentos (unidad, tema, postura) y no soportan individuos.

Forma concreta: un modelo de compartimentos sobre la población que comenta —
proporciones favorable / neutral / adverso que se mueven según eventos y contagio,
calibrado contra las 33 semanas y los episodios de 0.2.

Es menos vistoso que 1.900 agentes LLM, y es lo que los datos permiten **falsar**.

### Fase 3 — Agentes generativos (Concordia), acotado

Solo si la fase 2 muestra que la heterogeneidad importa y que el modelo poblacional se
queda corto en algo identificable.

**Concordia sobre AgentSociety**, por lo que ya decía el informe original: es una
librería con patrón Game Master, no exige 10k agentes ni infraestructura distribuida. Y
acá el aporte sería **generar el texto plausible de la reacción**, no predecir el índice
— para eso ya estaría la fase 2.

Uso realista: **contrafactuales cualitativos**. "Si se comunica de esta manera en vez de
aquella, ¿qué tipo de comentarios aparecen?" Eso es un ensayo de comunicación, no un
pronóstico, y hay que presentarlo como tal.

---

## 5. Riesgos, nombrados

| Riesgo | Mitigación |
|---|---|
| **Validar contra ruido** — el error de ±4 puntos se ignora y todo "acierta" | La métrica de 0.3 incluye la barra de error; el criterio de la fase 1 es explícito |
| **Sobreajuste a 33 semanas** | Corte temporal (0.4). Con 33 puntos, cualquier modelo con muchos parámetros memoriza |
| **Alinear contra temas** (55,3 %) | El ground truth es el índice, que sí está validado |
| **La simulación se vuelve la pestaña linda** que no responde nada | La pregunta de gestión se fija ANTES (§6), y la fase 1 puede cerrar el proyecto |
| **Costo LLM sin techo** en la fase 3 | Aplicar lo del resumen semanal: huella + caché + costo por corrida registrado en `llm_usage` |

---

## 6. La decisión que falta

Todo lo anterior es ejecutable salvo por una cosa que no es técnica: **qué pregunta de
gestión debe responder la simulación.** El diseño de la fase 2 cambia por completo según
la respuesta:

- **A · Anticipar** — "¿cómo va a estar la percepción las próximas semanas?"
  → Serie temporal. Se valida con backtesting. La más medible, la menos ambiciosa.
- **B · Contrafactual de comunicación** — "¿qué pasa si comunicamos X de esta forma?"
  → Necesita el vínculo caption→reacción. Es lo más útil para la DAI y lo más difícil de validar.
- **C · Respuesta a shock** — "si hay un paro, ¿cuánto cae y cuánto tarda en recuperarse?"
  → Necesita los episodios de 0.2. Con 8 casos, sería un rango, no un número.
- **D · Sensibilidad por unidad** — "¿qué facultad es más volátil?"
  → El más barato: es casi descriptivo sobre lo que ya hay.

**Sin elegir una, la fase 0 se hace igual** — el calendario y el banco de episodios sirven
para las cuatro. Por eso el plan puede arrancar antes de que la decisión esté tomada.

---

## 7. Resumen

| | |
|---|---|
| **Condición del plan original** | cumplida para el índice (88,7 %), no para temas (55,3 %) |
| **Obstáculo estructural** | 76,9 % de autores aparecen una sola vez → sin trayectorias individuales |
| **Señal disponible** | real, ratio 1,75 sobre el ruido, con ±4 puntos de error |
| **Muestra de validación** | 33 semanas · 8 episodios · 1 evento cargado |
| **Primer paso recomendado** | Fase 0.1 — cargar el calendario académico |
| **Vara de éxito** | ganarle a persistencia, media móvil, estacionalidad y regresión sobre eventos |
| **Resultado aceptable** | que la fase 1 cierre el proyecto en días |
