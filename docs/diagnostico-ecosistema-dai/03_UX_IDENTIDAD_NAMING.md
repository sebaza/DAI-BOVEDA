# 03 · UX, identidad visual y análisis para naming — Bóveda DAI

> Diagnóstico del 2026-10-22 sobre el commit `6879a9e`. Estados: **Confirmado**, **Inferido**, **Propuesto**, **No verificado**. Rutas de frontend relativas a `frontend/`. Este documento **no propone nombres**; solo describe identidad, conceptos y criterios.

## 1. D.1 Estructura UX

### Navegación principal

| Ruta | Contenido | Acceso | Evidencia |
|---|---|---|---|
| `/` | Máquina de estados según la sesión: "Verificando sesión…" → `LoginScreen` → `Recibidor` | Público y luego sesión | `src/app/page.tsx` |
| `/percepcion` | `PaginaProtegida` → `BovedaShell` (cabecera + migas "Recibidor › Termómetro Institucional") → `PercepcionPanel` | Módulo `percepcion` asignado; si no, pantalla "Sin acceso" | `src/app/percepcion/page.tsx`, `src/components/BovedaShell.tsx` |

Todas las páginas son `"use client"`. **Confirmado**.

- **Cabecera** (`BovedaCabecera`): banda fija de 64 px con emblema, "Bóveda DAI" (enlace a `/`), nombre, correo y rol del usuario, y "Cerrar sesión".
- **Recibidor**: lobby con una tarjeta-baúl por módulo ("compartimento"). El catálogo visual está fijado en el código (`Recibidor.tsx`, `CATALOGO`) y solo contiene `percepcion`.

### Organización del Termómetro (pestañas)

| Pestaña | Sub-pestañas (texto visible) | Visible para |
|---|---|---|
| Resumen | "¿Cómo estamos?" · "¿Qué cambió?" | Todos |
| Alertas | "¿Se está hablando de paro?" · "¿Qué quincena se salió de lo normal?" | Todos |
| Comparar | "¿Cómo está cada área?" · "¿De qué se habla?" · "¿Qué unidad se mueve más?" | Todos |
| Conversación | "¿Cuándo pasó?" · "¿Con qué palabras?" · "¿Lo más hablado?" | Todos |
| Curación | "¿Cuánto le erra?" · "Revisar comentarios" · "Corregir temas" · "Subtemas" | Solo administración |
| Simulación | "¿Va a generar conversación?" · "¿Se puede predecir?" · "¿Qué pasa tras un paro?" · "¿Qué comunicación funciona?" | `equipo` y administración |

Evidencia: `PercepcionPanel.tsx:1259-1267`; `PercepcionUI.tsx` (`SubPestanas`). **Confirmado**.

La visibilidad por rol se resuelve en el cliente leyendo `localStorage`. La barrera real está en el backend.

### Inventario de patrones

| Patrón | Implementación | Estado |
|---|---|---|
| Dashboard inicial | Resumen: índice grande 0–100, barra apilada favorable/neutral/desfavorable, silueta mensual, postura, avisos de alertas activas, resumen semanal narrativo | Confirmado (`PercepcionResumen.tsx`, `PercepcionResumenSemanal.tsx`) |
| Filtros | Barra fija bajo la cabecera: Sede, Facultad, Departamento, Tema y Rango; "Último mes", "Restablecer" y "Ajustes ▾" con dos deslizadores ("Peso por likes", "Recencia (vida del comentario)"). En móvil quedan tras "Filtros ▾" | Confirmado (`PercepcionPanel.tsx`) |
| Gráficos | ECharts (líneas, barras) con carga diferida por `IntersectionObserver`, tema propio y redimensión | Confirmado (`EChartsChart.tsx`) |
| Visualizadores especiales | Franja de eventos alineada al eje temporal; nube de palabras en CSS puro (texto real, seleccionable) | Confirmado (`PercepcionFranjaEventos.tsx`, `PercepcionNube.tsx`) |
| Tablas | Deltas, anomalías, comparación por unidad, calidad del modelo (matriz de confusión) | Confirmado |
| Formularios | Ensayo de publicación, anotación en Curación, creación de temas, renombre de subtemas, ABM de eventos ("Administrar marcas") | Confirmado |
| Búsqueda | No hay búsqueda de texto libre; solo filtros y selección | Confirmado |
| Navegación contextual | Saltos entre pestañas con "migas de dónde vengo" (`RastroNavegacion`) | Confirmado |
| Ayuda | Guía "¿Qué es esto?" plegable, con "Para qué no sirve" y "Por dónde empezar"; explicaciones metodológicas en `title=` | Confirmado |
| Retroalimentación | Enlace "Dar retroalimentación ↗" a un formulario externo, solo si existe `NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL` | Confirmado (`PercepcionPanel.tsx:728`) |

### Estados de interfaz

| Estado | Comportamiento | Evidencia |
|---|---|---|
| Carga | Texto centrado ("Cargando…", "Cargando alertas…"); atenuado con `aria-busy` en Resumen. El esqueleto de gráficos usa la clase `portal-skeleton`, **que no existe en el CSS** | `PercepcionResumen.tsx`; `EChartsChart.tsx` |
| Vacío | "No hay datos de percepción para este filtro.", "muestra insuficiente" (`SinEvidencia`), "Sin señal". El vacío principal **muestra comandos internos del worker** al usuario | `PercepcionPanel.tsx`; `PercepcionUI.tsx` |
| Error | Banner no bloqueante "… · reintentando…" que conserva los datos previos; error por bloque. Los mensajes de la API llegan crudos (JSON) salvo en Subtemas. Un fallo de carga de ECharts es silencioso | `lib/percepcion.ts`; `PercepcionSubtemas.tsx` (`mensajeDe`) |
| Sin acceso | "No tienes acceso a este módulo… Pide acceso a la DAI." con "Volver al recibidor"; cuenta sin módulos: "Aún no tienes compartimentos asignados…" | `PaginaProtegida.tsx`; `Recibidor.tsx` |
| Sesión vencida a mitad de uso | No desloguea; solo muestra el error del bloque | `lib/percepcion.ts` |

### Responsive y accesibilidad

**Responsive (Confirmado):**

- Usa los *breakpoints* por defecto de Tailwind (`sm`, `md`, `lg`).
- La barra de pestañas tiene desplazamiento horizontal.
- La cabecera compacta bajo `sm`.
- Las tarjetas del Recibidor pasan de 1 a 2 y a 3 columnas.
- Los gráficos se redimensionan con `ResizeObserver`.

**Fortalezas de accesibilidad (Confirmado):**

- `lang="es"`.
- Pestañas con `role="tablist"` y navegación con flechas.
- `aria-expanded` y `aria-pressed`.
- Migas con `aria-current`.
- Gráficos con `role="img"` y `aria-label`.
- Foco visible global.
- `prefers-reduced-motion` respetado, aunque solo en parte.

**Brechas (Confirmado salvo indicación):**

- `/percepcion` no tiene `<h1>`.
- Las explicaciones metodológicas solo están en `title=`, inaccesibles con teclado y en pantallas táctiles.
- Las filas de comentarios son `div` clicables sin rol ni teclado.
- Los banners de error no tienen `role="alert"` ni `aria-live`.
- Las sub-pestañas no tienen navegación con flechas.
- El color es el único canal en chips y franjas (**Inferido**).
- El botón primario está en el límite de contraste (≈ 4,5:1, **Inferido**).

## 2. D.2 Identidad visual actual

### Concepto

Es un tema único oscuro, una "bóveda de grafito" (`color-scheme: dark`) sin modo claro. La metáfora material es la de un **baúl de madera oscura con fajas de hierro, remaches y placa de latón**. Las tarjetas de datos usan una "placa grabada" más sobria, y el baúl completo se reserva para el Recibidor y el login. **Confirmado** (`src/app/globals.css`, clases `.boveda-baul`, `.boveda-faja`, `.boveda-esquina`, `.boveda-placa`, `.boveda-banda`, `.boveda-placa-card`).

### Tokens de color (`src/app/globals.css`, `:root`)

| Token | Valor | Uso |
|---|---|---|
| `--ucn-azul` / `--ucn-azul-claro` | `#759cc0` / `#9dbad6` | Acento institucional sobre oscuro; serie "favorable" |
| `--ucn-tierra` / `--ucn-tierra-clara` | `#c06125` / `#e2b49a` | Acento cálido; botón primario `.boveda-cta`; alerta alta |
| `--ucn-azul-suave` / `--ucn-azul-borde` | `rgba(117,156,192,.14)` / `.32` | Fondos y bordes |
| `--ucn-tierra-suave` | `rgba(192,97,37,.16)` | Fondos de aviso |
| `--boveda-fondo` / `--boveda-fondo-2` | `#121314` / `#161719` | Fondo de página |
| `--boveda-madera` / `--boveda-madera-2` | `#1b1c1f` / `#232528` | Superficies |
| `--boveda-hierro` / `--boveda-hierro-2` | `#0c0d0e` / `#18191b` | Fajas |
| `--boveda-laton` / `--boveda-laton-oscuro` | `#c9a25e` / `#8e6e3a` | Adornos, kickers, bordes de tooltip |
| `--boveda-linea` / `--boveda-linea-fuerte` | `rgba(237,237,239,.08)` / `.14` | Divisores |
| `--portal-fg` / `--portal-muted` / `--portal-subtle` | `#ededef` / `#a8abb1` / `#888c93` | Texto |
| Datos: favorable / neutro / adverso / serie-3 / serie-4 | `#759cc0` / `#8c9097` / `#d27a45` / `#c9a25e` / `#a8abb1` | Gráficos |
| Alertas: baja / media / alta | `rgba(192,97,37,.14)` / `.32` / `#c06125` | Niveles |

El par azul–tierra se declara divergente y "seguro para daltonismo" (comentario del CSS). La paleta de gráficos está espejada en `src/lib/paleta.ts`.

**Fuera de marca:** siete colores de categorías de eventos heredados de la Torre, sin tokenizar y duplicados en dos archivos: `#f2777a`, `#fb923c`, `#4f9cf0`, `#51c28c`, `#e0aa4e`, `#a88bfa` y `#8496b0` (`PercepcionPanel.tsx`, `COLOR_EVENTO`; `PercepcionFranjaEventos.tsx:67-72`). **Confirmado**.

### Tipografía, forma, iconografía y movimiento

| Elemento | Valor | Evidencia |
|---|---|---|
| Cuerpo | Manrope 400–800, base 14 px, interlineado 1,55 | `globals.css:1` y `body` |
| Títulos | Space Grotesk 500/700 (`.portal-title`) | `globals.css` |
| Carga de fuentes | `@import` de Google Fonts con `display=swap` (sin `next/font`) | `globals.css:1` |
| Grises | Escala `slate` de Tailwind reemplazada por un grafito neutro (`#F7F7F8` … `#151618`) | `tailwind.config.ts` |
| Radios | sm 2 px, base 3 px, md/lg 4 px, xl/2xl 6 px, 3xl 8 px: formas de "placa metálica" | `tailwind.config.ts` |
| Espaciado | Escala por defecto de Tailwind (sin extensión) | `tailwind.config.ts` |
| Iconografía | Sin sistema de iconos: caracteres Unicode (▴ ▾ ▲ ▼ ✎ ✕ ↗ → ›) | Componentes |
| Animación | Elevación de 2 px y sombra en el baúl (0,2 s), `scroll-behavior: smooth`, foco con contorno azul de 2 px | `globals.css:202-205` |
| Design tokens | Variables CSS en `:root` de `src/app/globals.css`, espejo en `src/lib/paleta.ts`, extensiones en `tailwind.config.ts` | — |

### Logotipo y símbolo

- **Emblema** (`src/components/BovedaEmblema.tsx`, viewBox 54×42):
  - Placa rectangular de latón (`#c9a25e`, borde `#8e6e3a`) con marco interior y cuatro remaches.
  - Al centro, un **ojo de cerradura** en tierra UCN (`#c06125`).
  - El comentario del código lo declara abstracto: "not the official crest".
- **Favicon** (`src/app/icon.svg`):
  - Cuadrado azul marino `#0a1626` con borde `#4f9cf0` y una retícula (anillo y punto dorado `#e0aa4e` con cuatro marcas en cruz).
  - **No coincide con el emblema ni con la paleta actual.** Es un resto de la identidad de la Torre.
- **Confirmado**.

### Voz y tono (textos propios de la interfaz)

- Login: "Acceso restringido" · "Bóveda DAI" · "Bóveda de la Dirección de Análisis Institucional, reservada a la dirección universitaria."
- Recibidor: "Elige un compartimento para entrar. Cada módulo guarda información reservada a la dirección universitaria." · Pie: "Dirección de Análisis Institucional · Universidad Católica del Norte".
- Panel: "Percepción de la comunidad" · "Indicador de redes sociales: no representa a toda la comunidad."
- Guía: "50 es el empate" · "Lo que importa es el cambio" · "Para qué no sirve".

El tono es español neutro, sobrio y honesto sobre los límites del dato, con los títulos formulados como preguntas de un directivo. **Confirmado** el texto; **Inferido** el tono.

## 3. Glosario de términos visibles

| Término | Significado en la interfaz |
|---|---|
| Bóveda DAI | Nombre del portal |
| Recibidor / Compartimento | Lobby / módulo |
| Termómetro Institucional | Nombre del módulo en las migas y en la pantalla sin acceso; el `h2` del panel dice "Percepción de la comunidad" |
| Índice (0–100) | Lecturas: Sin señal / Desfavorable (<40) / Bajo el neutro (<50) / Neutro (<60) / Favorable |
| Postura | "Postura hacia la UCN" (favorable, neutral, adverso), distinta del tono |
| Alerta / Atención | Niveles de anomalía; "Señales bajo vigilancia" para el léxico de conflicto |
| Conflicto | "Conflicto: cuántos, no cuánto" |
| Volatilidad | "Qué unidad se mueve de verdad" |
| Shock | "Qué pasa cuando hay un paro" |
| Baselines / "La vara" | "¿Se puede predecir?" en la UI; "La vara" en el código y los comentarios |
| Ensayo | "¿Esta publicación va a generar conversación?" |
| Curación | "¿Le puedo creer al modelo?" |
| Marcas / eventos | "Administrar marcas", "Calendario cargado" |

**Inconsistencias (Confirmado):**

- El mismo producto se llama "Percepción" y "Termómetro Institucional".
- El mismo bloque se llama "La vara" y "¿Se puede predecir?".
- La guía habla de "las cuatro pestañas", pero hay hasta seis.
- El texto de ayuda filtra vocabulario interno ("scoring", "corpus", "ABM").

## 4. D.3 Consistencia futura: elementos compartibles

| Elemento | Situación actual | Potencial de ecosistema |
|---|---|---|
| Header institucional | `BovedaCabecera`: emblema + nombre + usuario + cerrar sesión | Alto. Base para una cabecera común con espacio para la identidad de cada aplicación (**Propuesto**) |
| Navegador del ecosistema | El Recibidor ya funciona como lanzador de módulos según permisos (`/auth/me` → `modulos[]`) | Alto. Patrón natural para un lanzador DAI (**Propuesto**) |
| Perfil de usuario | Solo texto (nombre, correo, rol); `picture` existe en el tipo pero no se muestra | Medio |
| Autenticación visualmente unificada | `LoginScreen` con Google + modo desarrollo, heredado de la Torre | Alto si hay SSO (**Propuesto**) |
| Componentes | `PercepcionUI` (`CARD`, `SELECT`, `TituloBloque`, `SubPestanas`, `Delta`, `BarraConfianza`, `SinEvidencia`), `EChartsChart`, `useSolicitudVigente` | Medio–alto tras quitarles el prefijo de dominio |
| Sistema de diseño | Tokens CSS con nombres heredados (`--portal-*`) más propios (`--boveda-*`, `--ucn-*`); sin paquete compartido | Alto: los tokens `--ucn-*` son candidatos a la capa común, y `--boveda-*` a la capa de personalidad (**Propuesto**) |
| Terminología | Preguntas como títulos y avisos de evidencia | Patrón valioso para todo producto analítico DAI (**Propuesto**) |
| Estados y errores | `SinEvidencia`, `BarraConfianza`, banners no bloqueantes | Medio; antes falta normalizar los mensajes crudos de la API |
| Accesibilidad | Base razonable, con las brechas descritas | Requiere un estándar común (**Propuesto**) |

**Criterio (Propuesto):** separar una capa común (tokens UCN, cabecera, autenticación, estados, accesibilidad) de una capa de personalidad por aplicación. En la Bóveda, esa personalidad es la materialidad de baúl, latón y hierro. El objetivo no es que todas las aplicaciones se vean idénticas.

## 5. D.4 Capturas

**No se tomaron capturas**, por tres razones:

1. La aplicación es un prototipo local cuya base contiene comentarios reales.
2. El acceso depende de listas en una base PostgreSQL que no se configuró para este análisis.
3. No había autorización para ejecutar la aplicación contra datos reales.

No se generan capturas ficticias.

### Guía de capturas manuales

**Preparación recomendada:**

- `APP_ENV=dev` y botón "Entrar en modo desarrollo", con una cuenta de prueba a la que se le da acceso con `scripts/boveda_accesos.py`.
- Una base de Percepción **vacía o sintética**, nunca la base real.
- Si hay que usar datos reales, difuminar lo indicado en la tabla.

| # | Pantalla | Ruta o lugar | Estado recomendado | Qué evidencia | Qué ocultar o anonimizar |
|---|---|---|---|---|---|
| 1 | Login | `/` sin sesión | Con el botón de Google visible | Acceso restringido, voz de marca, banda de hierro | Mensajes de configuración de desarrollo |
| 2 | Sin acceso | `/percepcion` con una cuenta sin el módulo | Por defecto | Fail-closed visible | Correo en la cabecera |
| 3 | Recibidor | `/` con sesión | Con al menos un compartimento | Metáfora de baúl, lanzador de módulos | Nombre y correo del usuario |
| 4 | Resumen | `/percepcion`, pestaña Resumen, sub-pestaña "¿Cómo estamos?" | Rango de un mes o más | Índice 0–100, postura, resumen semanal | El resumen semanal puede nombrar episodios reales: difuminar si los datos son reales |
| 5 | Alertas | Pestaña Alertas | Con al menos una quincena marcada | Alerta temprana y léxico de conflicto | Fechas de episodios si se consideran sensibles |
| 6 | Comparar | Pestaña Comparar | Nivel facultad | Comparación entre unidades, volatilidad | Nombres de unidades con índices bajos si se difunde fuera de la dirección |
| 7 | Conversación — "¿Cuándo pasó?" | Pestaña Conversación | Con la franja de eventos visible | Serie temporal, eventos, fichas sin texto | **Identificadores de cuentas** en "Comentarios recientes" |
| 8 | Conversación — "¿Con qué palabras?" | Pestaña Conversación | Mínimo de frecuencia alto | Nube anonimizada | Palabras que puedan ser nombres de personas (el propio código reconoce que el *scraper* deja nombres de usuario pegados) |
| 9 | Simulación — Ensayo | Pestaña Simulación (rol `equipo`) | Un ensayo ejecutado | Capacidad analítica interna | Nombres de cuentas |
| 10 | Curación — "¿Cuánto le erra?" | Pestaña Curación (administración) | Con la matriz de confusión | Rigor metodológico | Ningún dato personal esperado |
| 11 | Curación — "Revisar comentarios" | Pestaña Curación | **No capturar con datos reales** | Auditoría de texto crudo | Todo el texto de comentarios, captions e identificadores. Solo con base sintética |
| 12 | Vista móvil | Cualquier pantalla a 375 px | Filtros plegados | Responsive | Lo mismo que en la pantalla original |

## 6. Fase E — Análisis semántico para naming

### E.1 Esencia del producto

La aplicación tiene **dos niveles semánticos distintos**, y conviene no confundirlos al nombrar:

| Nivel | Qué es | Acción que representa | Qué protege, transforma u observa | Valor |
|---|---|---|---|---|
| **Contenedor** ("Bóveda") | Un espacio de acceso restringido con un recibidor y compartimentos para módulos sensibles | **Custodiar y conceder acceso** | Información sensible de la comunidad; protege a las personas de la exposición y a la institución del uso indebido | Confianza: solo entra quien debe, y queda registro |
| **Módulo** ("Termómetro Institucional" / "Percepción") | Un instrumento de medición del clima de opinión pública en canales institucionales | **Medir, interpretar y advertir** | Transforma miles de reacciones anónimas en una señal agregada, comparable y con límites explícitos | Anticipación y lectura honesta del clima, no una encuesta |

- **Papel en la inteligencia institucional:** aporta la **dimensión perceptiva y externa** (cómo se percibe la institución en lo público), con un nivel de sensibilidad que exige custodia. **Inferido**.
- **Metáfora principal:** del contenedor, *la cámara acorazada con compartimentos*; del módulo, *un instrumento que mide la temperatura del clima de opinión*. **Inferido**, consistente con los nombres y el emblema actuales.

### E.2 Territorio conceptual

| Concepto | Pertinencia | Nivel |
|---|---|---|
| Custodia | Núcleo del contenedor: acceso por listas, fail-closed, auditoría | Contenedor |
| Resguardo / acceso restringido | La razón de existir de la aplicación es la sensibilidad del dato | Contenedor |
| Medición | Índice 0–100, confianza, umbrales de evidencia | Módulo |
| Escucha / percepción | Atiende lo que la comunidad expresa en lo público, de forma agregada | Módulo |
| Evidencia | "Muestra insuficiente", casos en vez de promedios, calidad del modelo frente a humanos | Ambos |
| Anticipación / alerta temprana | Alertas quincenales con *lead* medido | Módulo |
| Interpretación | Resumen semanal, postura frente a tono, palabras que más pesan | Módulo |
| Rigor y honestidad del dato | "Para qué no sirve"; decisiones "medidas, no opinadas" | Ambos |
| Memoria / histórico | Serie 2022–2026, calendario institucional | Módulo (secundario) |

Conceptos de la lista sugerida que **no se recomiendan** como eje: **observación** y **vigilancia**, por el riesgo de que se lean como monitoreo de personas, y **coordinación** y **navegación**, que no se alinean con la función. **Inferido**.

### E.3 Personalidad (cinco atributos)

1. **Reservada.** Protege por defecto y solo se abre a quien está autorizado. En la duda, niega.
2. **Rigurosa.** Mide antes de afirmar y declara su error y sus umbrales de evidencia.
3. **Honesta.** Dice "para qué no sirve" y distingue señal de ruido sin exagerar.
4. **Serena.** Tono sobrio, sin alarmismo: las alertas son graduadas (atención o alerta) y explicadas.
5. **Anticipatoria.** Busca dar aviso antes de que un conflicto escale, sin pretender predecir lo que no puede.

**Inferido** a partir de la voz de la interfaz, las reglas de acceso y los docstrings metodológicos.

### E.4 Metáforas y símbolos

| Metáfora | Qué representa | Ajuste | Riesgo |
|---|---|---|---|
| Bóveda / cámara acorazada con compartimentos | Custodia, acceso graduado, memoria protegida | Alto para el contenedor (ya en uso) | Puede sonar a secreto u opacidad hacia la comunidad |
| Cerradura / placa de latón con remaches | Acceso y autenticidad, oficio | Alto (ya es el emblema) | Bajo |
| Termómetro | Medición de temperatura o clima, lectura simple | Alto para el módulo | Sugiere una sola dimensión, cuando el módulo ofrece también alertas, comparación y simulación |
| Barómetro | Presión atmosférica y anticipación del tiempo | Alto para la componente de alerta temprana | Menos conocido para públicos no técnicos |
| Sismógrafo | Detección de sacudidas (paros, crisis) | Medio, fuerte para Alertas | Connotación de catástrofe |
| Prisma | Una señal descompuesta en tono, emoción, postura y tema | Medio | Más abstracto |
| Pulso / caja de resonancia | La comunidad "resuena" en lo público | Medio | "Pulso" puede leerse como algo individual |

### E.5 Restricciones

| Restricción | Detalle | Estado |
|---|---|---|
| Nombre ya sembrado en la base | `boveda.modulos` siembra `percepcion` / "Termómetro Institucional" (`backend/sql/001_boveda_access.sql:32-38`). El id `percepcion` vive en rutas (`/percepcion`), tablas (`percepcion_*`) y roles de base | Confirmado. Renombrar el **rótulo** es barato; renombrar el **identificador técnico** es costoso |
| Adopción del nombre "Bóveda" | La aplicación tiene dos días de historia y es un prototipo local | No verificado; probablemente baja adopción, lo que facilita un cambio |
| Adopción de "Termómetro Institucional" | Nombre heredado de su etapa en la Torre, usado en el formulario de retroalimentación y en documentos | Confirmado su uso; nivel de adopción en la dirección No verificado |
| Conflicto conceptual interno | "Percepción de la comunidad" frente a "Termómetro Institucional" en la misma pantalla | Confirmado |
| Riesgo de vigilancia | El módulo analiza comentarios de personas en redes. Textos como "Señales bajo vigilancia" y "Términos bajo vigilancia", más la metáfora de bóveda (secreto), pueden asociarse con **vigilancia de personas o de la organización estudiantil**. La postura trata como adversos los neutros de cuentas de federación | Confirmado: textos en `src/components/PercepcionAlertas.tsx:114` y `src/components/PercepcionResumen.tsx:281`, regla en `backend/app/services/percepcion/postura.py:198-203`. El riesgo reputacional es **Inferido** |
| Claridad para no técnicos | Los destinatarios son la alta dirección. Hay que evitar jerga ("scoring", "baseline", "MAD") y nombres que exijan explicación | Confirmado por el responsable (usuarios) |
| Siglas institucionales | No hay siglas obligatorias en este repositorio; "DAI" y "UCN" aparecen como firma institucional | Confirmado |
| Relación con la Torre de Control | Origen del módulo; comparten linaje técnico y algunos nombres internos (`--portal-*`, tema `"torre"`) | Confirmado |

### E.6 Ficha de identidad futura

Son criterios y posibilidades, **no nombres**. La selección se hará con los cinco diagnósticos. **Propuesto**.

| Campo | Nivel contenedor (hoy "Bóveda DAI") | Nivel módulo (hoy "Termómetro Institucional") |
|---|---|---|
| Nombre: criterios | Evocar resguardo **legítimo y transparente** (custodia responsable, no secreto); admitir varios módulos futuros; pronunciable en español; no confundirse con almacenamiento de documentos | Evocar medición del **clima colectivo y agregado**, nunca de individuos; entenderse sin explicación por la alta dirección; abarcar alerta y comparación, no solo un número |
| Logotipo | Conservar el lenguaje de placa y cerradura (ya consistente) y alinear el favicon | Instrumento de medición estilizado (escala, aguja, curva) que conviva con la placa |
| Símbolo | Cerradura o compartimento | Escala graduada o curva con umbral |
| Color distintivo | Latón `#c9a25e` sobre grafito `#121314` como personalidad; `--ucn-*` como capa común | Par divergente azul `#759cc0` / tierra `#c06125` (favorable/adverso), ya validado para daltonismo |
| Metáfora | Cámara acorazada con compartimentos | Termómetro o barómetro del clima de opinión |
| Mensaje principal | "Información sensible, en manos autorizadas y con registro" | "Cómo se percibe la UCN en lo público, con sus límites a la vista" |
| Papel en la familia DAI | La custodia: el lugar de lo sensible dentro del ecosistema y modelo de acceso por módulo reutilizable | La percepción: la lectura externa del clima institucional, complementaria a los datos internos de gestión que puedan tener otras aplicaciones (**No verificado**: las demás aplicaciones no se analizaron aquí) |
| Direcciones de naming preferibles | Custodia, resguardo, archivo protegido, compartimento | Clima, temperatura, presión, resonancia, lectura pública |
| Direcciones a evitar | Secreto, encierro, ocultamiento | Vigilancia, monitoreo, radar, espionaje, rastreo |
