---
name: percepcion-pestanas-y-deriva-worker
description: Percepción — las 4 pestañas por pregunta, el rótulo de método (mismo tema daba 58.7 y 64.3), y la deriva del modelo de la Torre vs el worker que borraba `origen`
metadata:
  type: project
---

## 1. Auditoría: por qué son 4 pestañas y no 3

Antes: **Tablero / Síntesis / Nube**, organizadas por TIPO DE GRÁFICO. Problemas medidos:

- **Duplicación con números distintos.** Cinco conceptos vivían en las dos primeras
  (índice global, distribución, por tema, por unidad, emociones) y **no coincidían**:
  el tema "Otros" daba **58.7 en Tablero y 64.3 en Síntesis**, y "Organización
  estudiantil" **cruzaba el neutro** (49.0 vs 50.3). Causa: el Tablero pondera la
  recencia (`vida_media`) y la Síntesis va sin decaimiento a propósito. Las dos
  decisiones son correctas; **faltaba decirlo en pantalla**.
- **Tablero = cajón de sastre**: 9 bloques + `PercepcionCuracion` completo al final.
- **Sliders de método siempre visibles**: un director no decide la "vida media de un
  comentario", y era justo la perilla que hacía diferir los números.
- Evolución y Comentarios estaban **separados por 5 bloques**, aunque el clic en el
  gráfico filtra esa lista (ver [[percepcion-filtro-fecha-comentarios]]).

Un primer intento dejó 4 pestañas con "Explorar" como cajón, y **no resolvió la
duplicación**: los cortes por tema y área seguían en DOS pestañas (tabla en Resumen,
gráfico en Explorar) con métodos distintos. Solo se los había rotulado. Segunda
auditoría → **5 pestañas, una pregunta cada una** (`PercepcionPanel.vista`):

| Pestaña | Pregunta | Componente | Método | Bloques |
|---|---|---|---|---|
| Resumen | ¿Cómo estamos? | `PercepcionResumen` | período | titular · alertas activas · qué cambió |
| Alertas | ¿Qué requiere atención? | `PercepcionAlertas` | período | señales bajo vigilancia · semanas anómalas |
| Comparar | ¿Dónde está el problema? | `PercepcionComparar` | período | cómo está cada área · de qué se habla |
| Conversación | ¿Qué se está diciendo? | inline en `PercepcionPanel` | **reciente** | evolución+eventos · comentarios · nube · emociones |
| Curación | Corregir el modelo | `PercepcionCuracion` | — | curación de temas |

**"Explorar" se partió en Comparar y Conversación** porque mezclaba dos preguntas:
rankear entidades y leer la conversación. Era el viejo Tablero con otro nombre.

**Se ELIMINARON por duplicados** (el Resumen ya los dice, y mejor): el gauge "Índice
general", los 4 StatTiles, el donut de Distribución, "Comparación por facultad" y
"Sentimiento por tema". Con ellos murieron `gaugeOption`, `donutOption`, `barOption`,
`temaOption`, `StatTile` y los fetch de `porTema`/`porUnidad` (~200 líneas). El Panel
bajó de ~1450 a ~1243 líneas.

En **Comparar**, gráfico y tabla salen de la MISMA llamada (`/percepcion/sintesis`
devuelve temas y áreas juntos). Mientras sean dos fuentes, tarde o temprano divergen.
El gráfico de áreas ordena **descendente** porque ECharts dibuja el primer elemento
ABAJO: así la peor unidad queda ARRIBA. Las filas sin evidencia van semitransparentes.

⚠️ **La NUBE se rompió** en el primer intento: quedó importada y nunca renderizada al
cambiar el ruteo de vistas. Vive en Conversación y su bloque ahora se titula "Nube de
palabras" (antes decía solo "Palabras más dichas", y embebida no se anunciaba).

### El Resumen sin caer en la repetición

Al sacarle los dos cortes, el Resumen quedó pobre. La salida NO fue devolverlos sino
darle **la conclusión de cada pestaña, no su contenido** (`GET /percepcion/destacados`,
una sola llamada):

- **"Las palabras que más pesan"** — NO las más dichas. Medido: las más frecuentes son
  `felicitaciones` (121, **0% negativo**), `gracias` (118) y `felicidades` (92); serían
  las mismas todos los meses. Se ordena por **negativos absolutos**, que pondera volumen
  y carga: `estudiantes` (37, 41% neg), `universidad` (34, 26%), `ucn` (50, 16%).
  Ordenar por % encumbraba palabras funcionales (`futuro` 70% con n=10).
- **"Cómo fue cambiando"** — silueta del índice MES a mes, escala relativa al rango
  (con 0-100 serían doce rectángulos iguales: el índice se mueve entre 55 y 70). No
  repite la evolución diaria de Conversación, que es trailing e interactiva.
- **"La emoción que más ganó terreno"** — dentro de "Qué cambió". Compara el **SHARE**,
  no el conteo: si el volumen se duplica, todas "crecen" y no se aprendió nada.

### ⚠️ REGLA ANTI-PII: el vocabulario se valida GLOBAL, nunca por área

El tokenizador no atrapa los handles de Instagram que son **letras puras**
(`ignaciamilann`, `jmanuuu`, `mish`): sin "_", dígitos ni punto interno parecen palabras.
Se midieron dos heurísticas estructurales sobre datos reales y **las DOS fallaron**:

| Heurística | `ignaciamilann` | `felicitaciones` | `paro` | ¿separa? |
|---|---|---|---|---|
| publicaciones distintas | 5 (ratio 1.6) | 74 (1.6) | 10 (1.6) | **NO** |
| autores distintos | 7 | 105 | 16 | **NO** |

En los posts de sorteo mucha gente distinta etiqueta a la misma persona, por eso ninguna
sirve. Lo único que separa es el **VOLUMEN GLOBAL**: los handles llegan a 8 apariciones
en todo el corpus y el vocabulario real pasa de 10. De ahí `MIN_GLOBAL_PALABRA = 10`
(122 palabras, **ningún handle**). El vocabulario se valida sobre TODO el período y
recién después se rankea por área — así un departamento con 4 comentarios no puede
publicar el nombre de una persona.

Y `MIN_LOCAL_PALABRA = 2`: el global protege de la PII, el local del ridículo. Sin él,
Ingeniería Industrial mostraba `amo (1) · año (1) · buena (1)`. Un área sin nada que
supere el mínimo devuelve lista vacía y la UI dice **"sin evidencia"**.

En Comparar, la columna "Qué se dice" existe a nivel facultad **y departamento**, con ese
resguardo. Verificado sobre datos reales: Derecho → `vida(3) · amor(2) · ucn(2)`;
Industrial → "sin evidencia". Cero nombres propios.

Decisiones que NO hay que deshacer sin pensarlo:

- **`RotuloMetodo`** (`PercepcionUI.tsx`): cada bloque declara con qué método lee. El
  usuario eligió **mantener los dos cálculos y explicarlos**, no unificarlos.
- **Los TRES controles son globales**: rango, peso por likes y recencia afectan a todas
  las pestañas por igual. Estuvieron un tiempo confinados a Conversación para evitar la
  divergencia; el problema real, sin embargo, era que la diferencia fuera **fija e
  invisible** (una vista con recencia SIEMPRE, otra NUNCA), no el control en sí. Con un
  control único que mueve todo a la vez las pestañas siguen coherentes, y el
  `RotuloMetodo` es DINÁMICO: dice "promedio del período" con recencia en 0 y
  "recencia N d" cuando está activa.
- **Excepción: ALERTAS ignora la recencia y lo declara** (`ignoraRecencia` →
  "sin recencia (detección)"). No es opcional: aplicándola, el evento se reparte y la
  detección se vuelve ciega — medido, el |z| máximo en el paro de 2026 cae a 1.98
  contra un umbral de 2.5, o sea CERO detecciones.
- **"Qué cambió" mide los DOS períodos llanos** aunque la recencia esté activa
  (`actuales_llano` en `sintesis`): comparar un período decaído contra uno sin decaer
  daría un delta sin significado. Hay test de regresión.
- Con recencia activa, una unidad sin comentarios recientes queda **sin índice** pero
  con su `n` intacto (medido: rango 90 d, vida 30 → 2 de 8 facultades; vida 7 → 4 de 8).
  No es un error, es "no habló últimamente": la UI lo escribe con
  `SinActividadReciente` y el gráfico usa `value: null` (con 0 la barra encabezaría el
  ranking de lo peor, justo lo contrario de lo que significa).
- **Conversación tiene SUBSECCIONES** (`subConv`): "Línea de tiempo" (evolución +
  eventos + comentarios) y "Nube de palabras" (nube + emociones). Apiladas, la línea de
  tiempo eclipsaba a la nube. El corte no es arbitrario: los comentarios van con el
  gráfico porque el clic en un día los filtra, y las emociones con la nube porque las
  dos describen el CONTENIDO, no la distribución temporal.
- **Comentarios va pegado a Evolución** en Conversación: el clic en un día filtra esa lista.
- Anomalías y términos críticos viven **juntos en Alertas**: responden la misma
  pregunta y nacen del mismo motor (el léxico alimenta la severidad).
- `PercepcionResumen` trae un bloque **"Alertas activas"** con contador y botón que
  salta a la pestaña Alertas (`onVerAlertas`).
- `PercepcionUI.tsx` centraliza colores, `colorIndice`, `fmt`, `labelEmocion` y las
  barras. Estaban **triplicados** en Panel/Síntesis/Nube.
- `PercepcionSintesis.tsx` **ya no existe**: es `PercepcionResumen.tsx`.

## 2. Deriva del modelo de la Torre vs el worker (GOTCHA GRAVE)

`backend/app/services/percepcion/models.py` es un espejo READ-ONLY del esquema que
**escribe el worker** (`Sentiment_Analisys_University`, `src/percepcion/db/models.py`).
Había quedado atrás y eso causó **pérdida de datos real**:

Columnas que faltaban: `percepcion_hecho_diario.origen`, `percepcion_cuenta.{unidad_cod,
activa, creada_en, origen}`, `percepcion_comentario.motivo_relevancia`,
`percepcion_score.scored_en`.

`origen` distingue ingesta UCN (`'interno'`) de cuentas ajenas (`'externo'`), y el
worker agrupa los hechos por **(fecha, ORIGEN, campus, facultad, depto, tema)**.

**El daño**: `curacion.reagregar()` hace `delete(H)` + reinsert y **no pasaba `origen`**.
Como TODA corrección manual llama a esa función, las 894 filas quedaron en NULL —
comprobado contra `percepcion_cuenta.origen`, que conservaba `'interno'` en sus 73 filas
porque la Torre no reagrega cuentas. Las 376 correcciones del 05-07/08/2026 lo dispararon.

**Arreglado**: modelos alineados, `reagregar()` deriva `origen` de la cuenta (con fallback
a `'interno'` para bases pre-migración) y agrupa por él. 4 tests de regresión en
`TestReagregarPreservaOrigen`. Reparación aplicada con
`_reparar_origen_percepcion.py --aplicar` → 894/894 en `'interno'`, respaldo en
`backups/percepcion_real_pre_reparar_origen_*.db`. El trabajo humano nunca estuvo en
riesgo (376 correcciones + 329 scores marcados siguen intactos).

⚠️ **REGLA**: `reagregar()` reconstruye la tabla ENTERA. Cualquier columna que el worker
agregue a `percepcion_hecho_diario` y no se espeje ahí **se pierde en toda la tabla, no
solo en la fila corregida**. Ante un cambio del worker, revisar `models.py` Y `reagregar()`.

## Verificación

```
backend\.venv\Scripts\python.exe -m unittest tests.test_percepcion   # 110 tests
backend\.venv\Scripts\python.exe _reparar_origen_percepcion.py       # dry-run
cd frontend && npx tsc --noEmit
```

Para la UI local hay que entrar por **`127.0.0.1:8001`, no `localhost:8001`** (CORS).
Ver [[percepcion-dev-login-local]] y [[percepcion-terminos-y-anomalias]].
