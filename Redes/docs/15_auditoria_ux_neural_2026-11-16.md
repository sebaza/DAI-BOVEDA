# Auditoría UX/UI del módulo DAI Neural (2026-11-16)

Público: vicerrectoría y dirección de la DAI, sin formación en aprendizaje automático. Criterio por vista: ¿se entiende qué muestra, por qué importa y cómo leerlo en 10 segundos? No se cambió ninguna cifra ni la metodología. Los endpoints y pruebas del backend quedan intactos.

## Decisiones de estructura

- **Se quitan «Estudiante» y «Postulante».** Mostraban registros individuales (Gate 4 pendiente) y no aportan a lo que tratan los modelos. Se borraron 8 componentes y los tipos, funciones y rutas del cliente que solo ellos usaban. El backend sigue exponiendo esas rutas, pero el frontend ya no las llama.
- **Orden: Modelos, Por facultad, Cohortes, Traslados, Calidad.** Cuenta una historia: qué tan bien funcionan los modelos y si sirven (semáforo), cómo se ve eso en mi facultad, el contexto histórico que lo rodea, y al final cuánto confiar en los datos.
- **Pestaña inicial: Modelos.** Es la que responde la pregunta de fondo del módulo. «Por facultad» es un paso de detalle que se alcanza desde ella (enlace en el Resumen).
- **Pestaña nueva «Por facultad».** Solo agregados, con nombres de facultad (nunca códigos). Tarjetas T1 a T6 con semáforo, una línea de significado, «Lo que ocurrió» y «Lo que anticipó el modelo». Debajo, una tabla comparativa (filas = facultades, columnas = tareas; en el encabezado va el momento en palabras y el k).

## Hallazgos y cambios

| Vista | Problema | Severidad | Cambio aplicado |
|---|---|---|---|
| Todo el módulo | Sin una frase que diga para qué sirve cada pestaña | Alta | Propósito y «Cómo leerla» arriba de cada pestaña; una frase por subpestaña de Modelos. Textos centralizados en `neuralLenguaSimple.ts` |
| Encabezado | Texto de ingreso con tono de aviso legal; no decía qué responde el módulo | Media | Intro reescrita; se agrega el plegable «Palabras que se usan en este módulo» |
| Tareas (notas, avisos) | Códigos internos visibles (P49, P51, D113, D114, «regla D47») en texto abierto | Alta | `limpiarCodigos()` en notas, avisos y conclusiones; los códigos quedan solo en bloques plegados («Notas técnicas», «Detalle técnico») |
| Cohortes / Tareas | «Egreso» y «titulación» se mezclaban sin explicación | Alta | Se mantienen como conceptos distintos y se definen en el glosario. En Cohortes se habla siempre de «titulados», y en Modelos de «egreso» |
| Cohortes | «N de ingreso», «a d», «d+1», «d+2», «Cohorte», «episodios» | Alta | «Ingresaron», «Titulados en la duración del plan (N años)», «con 1 año más», «con 2 años más», «Generación», «ingresos» |
| Cohortes (gráfico) | Ejes y leyenda con «S1», «p25 a p75», «Semestre» | Media | Eje «Semestres desde el ingreso», leyenda «valor central (mediana)» y «rango central (25 % a 75 %)» |
| Cohortes / Traslados | Celdas «n<10» ininteligibles | Media | «Oculto» con la explicación visible en la propia vista, no solo en el `title` |
| Modelos | Aviso largo y repetido, con dos insignias que decían lo mismo | Baja | Aviso corto «Aquí no hay predicciones sobre personas» |
| Modelos (subpestañas) | Nombres técnicos (GRU, GraphSAGE, «Red de capas») sin contexto | Media | Prefijo «Cómo funciona:» y una línea que avisa que no hacen falta para leer los resultados |
| Modelos / Resumen | Viñeta con «escalón», «corte» | Baja | Reescrita con lenguaje llano; «Corte del benchmark» pasa a «Momento de la estimación (k)» |
| Calidad | Primero tablas de «marts», «seudonimización», «umbral de supresión» | Alta | Respuesta primero («¿Los datos están en orden?», con insignia y frase). Cargas, tablas y clave quedan en «Detalle técnico» plegado. «Marts» pasa a «Tablas de resultados» |
| Traslados / Facultad (móvil 375 px) | Desbordamiento horizontal de toda la página (889 px y 453 px): los `sr-only` de las tablas escapaban del contenedor con scroll | Alta | `relative` en `TablaScroll`. Ya no hay scroll horizontal de página |
| Contraste | `text-slate-500` bajo sobre fondo oscuro en etiquetas de métricas y celdas ocultas | Baja | Se usa `--portal-muted` y `--portal-subtle` |
| Código muerto | Helpers de malla, persona y postulante, `PanelPestana`, `periodoLegible`, `EsqueletoGrafico` | Baja | Eliminados |

## Lo que no se encontró

- **Tema claro.** El portal solo define tema oscuro (`color-scheme: dark`); no hay tema claro que auditar.
- **Foco de teclado.** Pestañas, segmentados y botones ya tenían `focus-visible`. Los controles nuevos (selector, botón de facultad en la tabla, plegables) lo traen.

## Qué queda pendiente

1. **T1 y T3 no tienen cifras por facultad en su vista principal.** La evaluación principal de T1 («histórica») y todas las de T3 no se calculan por facultad. En T1 se usa «Modelo oficial desde la cohorte 2024» (marcado con †). T3 queda con la columna vacía, avisada en la nota. Decidir si el exportador debe calcular facultades para esas vistas.
2. **Verificación visual parcial.** Se comprobó con el navegador del panel (ancho de escritorio y 375 px), sin capturas completas de cada vista. La revisión de contraste y de tipografía en pantalla real queda para la persona que valida.
3. **Jerga restante en notas que vienen del servidor.** Frases como «diferencias menores que 0,03 de AP» o «eventos en prueba» siguen apareciendo en «Qué conviene saber». Conviene reescribirlas en el exportador (`exportar_resumen_modelos.py`), no en el cliente.
4. **Subpestañas técnicas de Modelos** (GRU, GraphSAGE, red de capas, CatBoost): siguen densas. Hoy están rotuladas como explicación técnica; podrían ir plegadas bajo un solo «Cómo funcionan los modelos».
5. **Rutas del backend sin uso** (`/neural/persona/*`, `/episodio/*`): siguen publicadas. Valorar cerrarlas hasta que se apruebe el Gate 4.
6. **Pruebas automáticas de la interfaz:** no existen para este módulo; la única verificación es `tsc --noEmit` y la revisión manual.
