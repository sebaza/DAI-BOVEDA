---
name: percepcion-filtro-fecha-comentarios
description: Feature — filtrar los comentarios de Percepción por fecha (clic en gráfico + selector Desde/Hasta sincronizados)
metadata:
  type: project
---

Percepción: el directivo puede ver SOLO los comentarios de una fecha o rango ("qué se decía en ese hilo de tiempo"), sin tocar los gráficos (que siguen mostrando la tendencia global). Afecta solo la lista de comentarios.

**Backend**: `/percepcion/comentarios` acepta `fecha_desde` / `fecha_hasta` (date). Si vienen, `repository.comentarios_recientes` IGNORA la ventana `dias` y filtra `C.fecha_comentario >= fecha_desde` y `< fecha_hasta + 1 día` (fin inclusive).

**Frontend** (PercepcionPanel): estado en `comFiltro.fechaDesde/fechaHasta` (filtro LOCAL, recarga solo comentarios). Dos entradas sincronizadas: (a) inputs `type=date` Desde/Hasta, (b) clic en el gráfico de Evolución → setea ese día. Chip "Mostrando: X ✕" para limpiar. Banda + línea vertical cyan en el gráfico reflejan la selección (lineOption recibe `seleccion`). Al haber fecha activa y sin chip de sentimiento se pasa `incluir_neutrales=true` y límite 100 (ver TODO lo dicho ese día).

**Gotchas (críticos)**:
- ECharts 5.5: `chart.convertFromPixel({xAxisIndex:0}, px)` devuelve **null**. Hay que usar `{gridIndex:0}` → `[índiceX, valorY]` y tomar `[0]`. `containPixel({gridIndex:0})` sí anda.
- Para clic-por-pixel se extendió `EChartsChart` con prop `onReady?: (chart) => void` (aditiva) que entrega la instancia; el handler se registra con `chart.getZr().on('click', ...)` y lee la serie viva vía un `useRef` (no capturar estado viejo).
- Verificación local: tras editar, **esperar a que Next dev recompile** antes del hard reload; si recargás muy rápido, el bundle servido es viejo (onReady no cableado) y el clic "no hace nada". Ver [[percepcion-dev-login-local]] y [[percepcion-arquitectura]].
