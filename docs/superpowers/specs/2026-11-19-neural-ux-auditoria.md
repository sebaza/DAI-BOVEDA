# Auditoría de experiencia de uso: módulo DAI Neural

Fecha: 2026-11-19. Alcance: todas las pestañas de `NeuralPanel.tsx` y sus piezas compartidas. Revisión de solo lectura sobre el código (no se levantó la aplicación ni se midió en pantalla real). Los anchos de 375 px son una estimación a partir de las clases y de los anchos mínimos declarados.

Audiencia: vicerrectores y directores de la UCN, lectores no técnicos y con poco tiempo, que necesitan conclusiones rápidas y confiables.

Restricción de diseño respetada en todas las recomendaciones: ninguna expone datos por estudiante, nombres ni rankings de docentes. Los bloques de ramos ya declaran que no hay cifras por sección ni por docente (`neuralLenguaSimple.ts:536`); cualquier cambio futuro en esos bloques debe conservar esa regla.

Convención de referencias: `archivo:línea`. Los archivos de componentes están en `frontend/src/components/` y los de lógica en `frontend/src/lib/`.

---

## 1. Resumen

El módulo tiene una base sólida: propósito y «Cómo leerla» al inicio de cada pestaña, preguntas como títulos, número clave por bloque, «Cómo usarlo», marca «pocos casos» casi universal, estados de carga, error y vacío en todas las pestañas, y un semáforo que nunca depende solo del color. Los problemas principales no son de contenido sino de estructura y consistencia:

1. La estructura de pestañas mezcla lo descriptivo (Histórico, Cohortes, Traslados) con lo técnico (Modelos, Por facultad) y deja la pestaña «Por facultad y programa» con un nombre que promete otra cosa que lo que muestra.
2. Elegir un programa se resuelve de cuatro maneras distintas y en ninguna hay búsqueda tolerante a tildes en el selector compartido.
3. La población elegida no queda a la vista dentro de los bloques, lo que arriesga que una cifra se cite con la facultad equivocada.
4. En móvil la conclusión llega después del gráfico y las siete pestañas se cortan sin señal de que hay más.
5. Los gráficos no tienen alternativa de datos y fallan en silencio si el CDN no carga.

Conteo de hallazgos: **Alta 8 · Media 21 · Baja 8 (total 37)**.

---

## 2. Arquitectura de información

### 2.1 Orden y agrupación actuales

`NeuralPanel.tsx:22-30`: Histórico, Proyecciones, Modelos, Por facultad y programa, Cohortes, Traslados, Calidad. El comentario del archivo (`:3-6`) lo describe como relato: pasado, futuro, calidad del modelo, facultad, contexto y confianza.

Lectura desde la audiencia: el relato se rompe en el medio. Después de las dos pestañas que sirven para decidir (Histórico, Proyecciones) vienen dos que responden «¿qué tan bien funciona el modelo?» (Modelos, Por facultad) y recién después dos descriptivas del pasado (Cohortes, Traslados), que conceptualmente son hermanas de Histórico. Un vicerrector que busca «cuántos se titulan por generación» debe saltar sobre la parte técnica.

### 2.2 Solapamientos

| Par | Qué se repite | Evidencia | Veredicto |
|---|---|---|---|
| «Por facultad y programa» vs. selector facultad → programa de Histórico/Proyecciones | El nombre promete «las cifras de mi facultad», pero la pestaña muestra, para T1 a T6, lo que ocurrió frente a lo que anticipó el modelo en cada grupo (`NeuralFacultades.tsx:174-251`); es validación del modelo por grupo, no historia por facultad. Además usa su propia selección (`NeuralPanel.tsx:50` no le pasa `seleccion`; estado propio en `NeuralFacultades.tsx:41-42`), de modo que elegir «Ingeniería» en Histórico no se refleja aquí. Tampoco ofrece «Toda la UCN». | Solapa en nombre y en tarea del usuario. |
| «Por facultad y programa» vs. «Modelos → Resultados por tarea → Por programa, facultad y otros grupos» | Mismas cifras (observada, esperada, brecha, IC) por programa y facultad. | `NeuralModelosGrupos.tsx:53-98` y `NeuralFacultades.tsx:217-251` | Tres lugares muestran «ocurrió frente a esperado» por facultad: Histórico bloque 2 (`NeuralLoQuePaso.tsx:160-199`), Modelos por tarea y esta pestaña. |
| «Cohortes» vs. «Histórico» | «Siguen tras el 1.er año» (`NeuralCohortes.tsx:93`) equivale a «¿Cuántos pasaron al año siguiente?» (`neuralLenguaSimple.ts:468-472`); «Titulados en la duración del plan, +1 año, +2 años» (`NeuralCohortes.tsx:94-95`) equivale a «¿Cuánto tardan en egresar?» (`NeuralLoQuePasoTemas.tsx:424-452`). Dicen casi lo mismo con otros nombres, otra población y otro selector. | Ver M1. |
| «Calidad» vs. «Modelos» | No se pisan en contenido (datos frente a modelos), pero el nombre «Calidad» es ambiguo y las advertencias sobre datos están también dentro de cada tarea (`NeuralModelosTarea.tsx:317-347`) y en Proyecciones (`neuralLenguaSimple.ts:617-621`). | Ver M2. |
| «Modelos → Fundamentos del modelo» en Histórico | El tema «Fundamentos del modelo» (`NeuralLoQuePaso.tsx:98-103`) explica señales y espera de un semestre, que es contenido de Modelos dentro de una pestaña histórica. | Aceptable como puente, pero refuerza que Histórico mezcla niveles. |

### 2.3 Recomendación de estructura

Mantener siete destinos, pero agruparlos en tres bloques con separación visual y cambiar nombres y orden:

1. Lo que pasó: **Histórico**, **Cohortes**, **Traslados**.
2. Lo que viene: **Proyecciones**.
3. Cuánto confiar: **Modelos**, **Modelo por facultad** (antes «Por facultad y programa»; alternativa: pasarla a subpestaña de Modelos, donde ya se enlaza desde `NeuralModelos.tsx:152-157`), **Calidad de los datos**.

Compromiso: unir Cohortes y Traslados dentro de Histórico como temas haría de Histórico una pestaña de 14 más 5 bloques, ya pesada. Dejarlas separadas pero adyacentes cuesta poco y evita ese crecimiento. Si se quiere minimizar el cambio, basta con mover Cohortes y Traslados a las posiciones 2 y 3.

### 2.4 Pestaña por defecto

Mantener **Histórico** (`NeuralPanel.tsx:34`): es lo verificable, no lleva el aviso de «orientativo» de Proyecciones y no exige elegir un programa (a diferencia de Cohortes). Pero dos ajustes:

- Abrirla con una franja «Lo esencial» de 3 a 4 cifras (continuidad al año siguiente, eliminados del último año completo, estudiantes en el umbral, estado de los datos) enlazadas a su bloque. Hoy no hay una vista de entrada con titulares; el primer contenido es el gráfico de «¿En qué semestre se pierden más estudiantes?» (`NeuralLoQuePaso.tsx:76`).
- Colocar primero en «Permanencia» el bloque de continuidad al año siguiente (`NeuralLoQuePaso.tsx:77`), que es la cifra más citada, antes de la distribución por semestre.

### 2.5 ¿Un filtro compartido en todas las pestañas?

No para todas. Tabla de situación actual:

| Pestaña | Filtro de población | Selector propio |
|---|---|---|
| Histórico | Compartido (`NeuralLoQuePaso.tsx:47`) | Tema (`Segmentado`, `:52`) y controles por bloque |
| Proyecciones | Compartido (`NeuralLoQueViene.tsx:52`) | Ninguno |
| Modelos | Ninguno (siempre Toda la UCN; aviso solo en la etiqueta del modelo, `NeuralModeloEtiqueta.tsx:49-51`) | Subpestaña, tarea, momento, nivel de grupo, malla de ejemplo |
| Por facultad y programa | Propio, desconectado | Nivel, facultad o programa, filtros de tabla (`NeuralFacultades.tsx:51-56, 87-96, 119-130, 274-287`) |
| Cohortes | Propio, solo programa | Filtro de texto más lista (`NeuralCohortes.tsx:21-49`), generación, indicador |
| Traslados | Ninguno por población; años, tipo y abandono | Filtros propios (`NeuralTraslados.tsx:96-140`) |
| Calidad | Ninguno | Ninguno |

Un filtro global confundiría: Modelos y Calidad no cambian con la población (se evalúan sobre conjuntos de prueba de toda la UCN) y Traslados es una relación origen-destino donde «filtrar por facultad» es ambiguo. Recomendación: un único componente de población (con búsqueda de programa) reutilizado en Histórico, Proyecciones, Cohortes y Modelo por facultad (como valor inicial), más un **indicador persistente** en la barra de pestañas con la población activa y, en las secciones donde no aplica, la frase «Esta sección no cambia con la población elegida» (el texto ya existe en `neuralLenguaSimple.ts:445`, pero solo se ve dentro del desplegable «Cómo se calculó»).

---

## 3. Hallazgos

Prioridad según el impacto sobre un vicerrector: **Alta** = puede llevar a citar mal una cifra, bloquea la lectura o rompe una promesa de la propia interfaz; **Media** = fricción o inconsistencia que cansa o resta confianza; **Baja** = pulido.

### Alta

**A1. «Por facultad y programa»: nombre engañoso, selección desconectada y contenido duplicado.**
Dónde: `NeuralPanel.tsx:26, 50`; `NeuralFacultades.tsx:35-47, 84-92`; `neuralLenguaSimple.ts:300-303`.
Por qué importa: el título sugiere «mis cifras por facultad»; el contenido es validación del modelo. Quien filtró por una facultad en Histórico llega aquí y vuelve a elegirla; no hay opción «Toda la UCN» para ver el total.
Recomendación: renombrar a «Modelo por facultad» (o integrarla en Modelos), pasarle `seleccion` como valor inicial, agregar «Toda la UCN» y dejar en el propósito (`:301`) la frase «Aquí se mide el modelo, no la historia; para la historia de una facultad use Histórico».

**A2. La población elegida no aparece dentro de los bloques ni queda fija al desplazarse.**
Dónde: `NeuralLoQuePasoTemas.tsx:35` (la línea de población habla de cohortes, no de la facultad o programa); `NeuralSelectorPoblacion.tsx:69-108` (selector al inicio, no fijo); `NeuralModeloEtiqueta.tsx:34` (la población solo figura dentro del desplegable «Cómo se calculó»).
Por qué importa: en una pestaña de 5 bloques el lector pierde de vista qué facultad está viendo; una captura pegada en un informe no dice a qué población corresponde. Es el riesgo de atribución más serio del módulo.
Recomendación: chip en el encabezado de cada bloque («Facultad de Ingeniería · Ingeniería Civil») y selector pegajoso compacto en Histórico y Proyecciones; en pestañas sin filtro, chip «Toda la UCN».

**A3. Elegir un programa se hace de cuatro maneras y el selector compartido no tiene búsqueda.**
Dónde:
- Histórico y Proyecciones: dos listas en cascada, el programa solo se alcanza si se conoce la facultad (`NeuralSelectorPoblacion.tsx:73-94`).
- Cohortes: campo de filtro más lista, sensible a tildes, con otro formato de etiqueta (`NeuralCohortes.tsx:24-25, 39-41`).
- Por facultad: lista con grupos (`NeuralFacultades.tsx:119-130`) y, aparte, un buscador solo para la tabla (`:283-285`), también sensible a tildes (`:268-269`).
- Modelos / GraphSAGE: otra lista (`NeuralModelos.tsx:289-295`); Traslados: tabla de balance de cientos de filas sin búsqueda (`NeuralTraslados.tsx:319-371`).
Además, las opciones del selector compartido muestran solo el nombre (`NeuralSelectorPoblacion.tsx:91`), mientras el resto del módulo usa «nombre (código)» (`neuralFacultades.ts:118`); dos programas homónimos de distinta sede serían indistinguibles.
Recomendación (implementación sugerida para la búsqueda pedida):
- Un solo componente «Buscar programa» (combobox con lista, patrón ARIA 1.2) dentro de `NeuralSelectorPoblacion`, sobre la `jerarquia` que la pestaña ya tiene.
- Busca en todas las facultades a la vez, sin necesidad de elegir facultad antes; coincide por nombre o código, normalizando tildes y mayúsculas (`normalize("NFD")` y quitar marcas diacríticas); mínimo 2 caracteres.
- Cada resultado muestra «Nombre (código)» y la facultad en segunda línea; al elegirlo se fijan facultad y programa a la vez (`SeleccionPoblacion` ya admite ambas).
- Conservar la lista de facultad y «Toda la UCN» como camino sin teclado.
- Respetar `resolverFiltro` (`:37-52`): si el programa no está en la lista de la pestaña activa, mostrar la nota existente (`TX.sinDatosPrograma`) en lugar de ocultarlo.
- Reutilizar el componente en Cohortes, Por facultad y GraphSAGE, y el buscador tolerante a tildes en las tablas.
- Objetivos táctiles de al menos 44 px; resultado con `role="status"` («12 programas coinciden»).
Alternativa más simple: `<input list>` con `<datalist>`; menos código, pero el comportamiento en móvil y con lectores de pantalla es irregular y no permite mostrar la facultad como texto secundario.

**A4. Los textos prometen «se listan todos» y la pantalla muestra los 10 o 12 primeros.**
Dónde: promesa en `neuralLenguaSimple.ts:529` (ramos reprobados) y `:544` (cuellos de botella); recorte en `NeuralLoQuePasoTemas.tsx:197` (`slice(0, 10)`), `:282` (`slice(0, 10)`) y `:238` (`slice(0, 12)`, sin aviso). Los bloques de causales y de tiempo sí avisan o ofrecen tabla completa (`:343-345, 378-394, 444`).
Por qué importa: el módulo se apoya en el principio «se muestran todos los grupos de cualquier tamaño»; que aquí no ocurra, sin decirlo, resta confianza justo en los bloques que más se citan para decidir apoyos.
Recomendación: o bien una tabla «Ver los N ramos» (como en causales) o bien cambiar el texto a «se muestran los 10 mayores de N», con N calculado.

**A5. Móvil: siete pestañas que se cortan sin señal y sin llevar la pestaña activa a la vista.**
Dónde: `NeuralUI.tsx:161-165` (`overflow-x-auto`, barra oculta en `globals.css:319-324`, sin los degradados `pestanas-fade-*` que sí usa el módulo hermano en `PercepcionPanel.tsx:1669`); el ancho conjunto de las etiquetas (la de «Por facultad y programa» sola ocupa alrededor de la mitad de 375 px) deja fuera «Cohortes», «Traslados» y «Calidad». Los saltos internos (`NeuralPanel.tsx:49, 51`: «Ir a Por facultad y programa →») cambian de pestaña sin desplazar la barra.
Por qué importa: un usuario móvil puede no enterarse de que existen tres pestañas.
Recomendación: reutilizar el patrón de degradado y de «scrollIntoView» de Percepción; acortar «Por facultad y programa» (ver A1); en pantallas angostas considerar un selector de sección tipo lista.

**A6. En móvil, el número clave queda debajo del gráfico (la conclusión llega tarde).**
Dónde: `DISPOSICION` (`NeuralLoQuePasoTemas.tsx:66`) apila gráfico y `Clave` en una columna cuando no hay `lg`; el orden del DOM pone la `Clave` después del gráfico en `NeuralLoQuePaso.tsx:127-147`, `NeuralLoQuePasoTemas.tsx:160-175, 287-298` y `NeuralLoQueViene.tsx:123-138`. Con el tope de alto de gráficos del 70 % de la pantalla (`EChartsChart.tsx:131-157`) la cifra queda bajo el pliegue.
Por qué importa: el criterio de la audiencia es «concluir en segundos»; en el teléfono primero se ve un gráfico sin su conclusión.
Recomendación: `order-first lg:order-none` en la `Clave`; opcionalmente mostrar «Cómo usarlo» (hoy al final de cada bloque) como bajada del título.

**A7. Los gráficos no tienen alternativa de datos y fallan en silencio.**
Dónde: `EChartsChart.tsx:377` (solo `role="img"` más una etiqueta corta), `:309-311` y `:378` (si el CDN está bloqueado el `catch` no hace nada y queda el esqueleto indefinidamente). La mayoría de los gráficos de Histórico (semestres, perfil, primer semestre, esperado, tiempo, señales) no tienen tabla equivalente; sí la tienen Proyecciones (desplegable por cohorte), Grupos, Facultades y Traslados. La curva de Cohortes ni siquiera usa `MarcoGrafico` (`NeuralCohortes.tsx:171-173`).
Por qué importa: un lector de pantalla recibe una frase; en una red universitaria que bloquee `cdn.jsdelivr.net` el gráfico no aparece ni se explica.
Recomendación: (a) añadir a `MarcoGrafico` un desplegable «Ver los datos» generado desde las mismas filas; (b) en `EChartsChart`, tras un tiempo de espera o un error, mostrar «No se pudo cargar el gráfico; los datos están en la tabla»; (c) usar `MarcoGrafico` en la curva de Cohortes.

**A8. Orden de pestañas: lo descriptivo del pasado queda separado de Histórico por lo técnico.**
Dónde: `NeuralPanel.tsx:22-30`. Ver 2.1 a 2.3. Recomendación: agrupar y reordenar como en 2.3.

### Media

**M1. «Cohortes» duplica a Histórico con otros términos, otro selector y sin tomar la población compartida.**
`NeuralCohortes.tsx:21-49, 93-95` y `neuralLenguaSimple.ts:468-472, 563-571`. «Siguen tras el 1.er año» frente a «pasaron al año siguiente»; «titulados» frente a «egresan» (la distinción es correcta y está en `TERMINOS_MODULO`, `:337`, pero no se explica en la propia tabla). Recomendación: precargar el programa desde la población compartida si es un programa; usar «Siguen al año siguiente» y una nota «Titulación es posterior al egreso» bajo la tabla.

**M2. «Calidad» es ambiguo y su contenido de confianza está lejos de donde se necesita.**
`NeuralPanel.tsx:29`; `NeuralCalidad.tsx:23-64`. Renombrar «Calidad de los datos»; mostrar el estado («Sin diferencias: N de N chequeos aprobados») como chip en el encabezado del módulo con enlace a la pestaña. Los límites de cobertura (`:59-64`) se repiten parcialmente en cada pestaña; enlazarlos en vez de repetirlos.

**M3. «Modelos» destina 4 de 6 subpestañas a arquitecturas, con etiquetas de hasta 60 caracteres.**
`NeuralModelos.tsx:21-28`; las etiquetas con `whitespace-nowrap` (`NeuralUI.tsx:179`) obligan a desplazar la barra incluso en escritorio angosto. Las propias descripciones dicen «no hace falta para leer los resultados» (`neuralLenguaSimple.ts:322-325`). Recomendación: dejar «Resumen» y «Resultados por tarea» como únicas subpestañas y mover las cuatro explicaciones a un bloque «Cómo funcionan los modelos (técnico)» plegado o a una subpestaña única «Detalle técnico»; acortar las etiquetas («GRU», «GraphSAGE», «Red de capas», «CatBoost»).

**M4. Mensajes de vacío con instrucciones de consola dirigidas al equipo técnico.**
`NeuralModelos.tsx:48-50, 159-160` («ejecutar `python tools/exportar_resumen_modelos.py` en Redes»); `NeuralModelosTarea.tsx:34`; `NeuralModelosResultados.tsx:61` («Ejecuta el exportador…»). Un vicerrector no puede actuar sobre eso. Recomendación: «Estos resultados aún no están disponibles. Avise a la DAI.» y dejar el comando en un `<details>` «Para el equipo técnico».

**M5. La etiqueta de modelo se repite en cada bloque con jerga técnica.**
`NeuralLoQuePasoTemas.tsx:36`; `NeuralModeloEtiqueta.tsx:16-18, 29-38` («T1 · Continuidad · CatBoost (…) · corte al 1.er semestre» más «Partición» y «Cálculo»). Añade una línea de lectura bajo cada título y nombra algoritmos que el lector no necesita. Recomendación: en el título mostrar un icono o enlace «Modelo» que despliegue la etiqueta; conservar «Dato observado, sin modelo» como única indicación visible por defecto cuando aplique.

**M6. Carga de lectura de la cabecera y del propósito.**
`NeuralPanel.tsx:57-82, 109-118`; `neuralLenguaSimple.ts:287-316`. Cada pestaña abre con dos párrafos; el «Cómo leerla» de Proyecciones (`:292-299`) tiene unas 80 palabras. Por bloque hay hasta cinco desplegables o líneas de apoyo («Cómo se calculó», «Qué se está mirando», «Cómo usarlo», más «Cómo se calcularon estas cifras» al final). Recomendación: propósito en una frase; «Cómo leerla» en 1 o 2 frases breves y el resto en un desplegable; unificar los desplegables en dos («Cómo se calculó» y «Notas»).

**M7. «Pocos casos» no es uniforme.**
- Sin marca: denominadores de continuidad y titulación en Cohortes (`NeuralCohortes.tsx:105-112`; solo `n_ingreso` la lleva, `:102-104`); ganados, perdidos y neto en Traslados (`NeuralTraslados.tsx:344-346, 410-413`).
- Reglas distintas dentro de la misma pestaña: ramos usa inscripciones (`NeuralLoQuePasoTemas.tsx:197, 237`), cuellos usa reprobaciones (`:282`), y varios bloques usan la bandera del servidor.
- La regla es solo por tamaño del grupo: una tasa de eliminación o de postgrado con 3 casos sobre 800 personas no se marca (`NeuralFacultades.tsx:228-231` muestra los casos pero no los evalúa). Verificar en el servidor si conviene marcar también eventos < 10 en las tareas de evento raro (T4, T5, T6).
Recomendación: una función única que devuelva la marca y que acepte `n` y, cuando exista, `eventos`.

**M8. Jerga que no se define donde aparece.**
«Corte», «k», «umbral», «modelo conservado», «referencia», «intervalo de 95 %», «AP», «ROC-AUC», «Brier», «ECE», «C(12)», «IBS», «partición», «ablación», «censura», «semillas», «verosimilitud» (`NeuralModelos.tsx:24-27, 177, 257, 333`). `TERMINOS_MODULO` (`neuralLenguaSimple.ts:330-340`) cubre nueve términos y omite «corte», «umbral», «modelo conservado» e «intervalo de 95 %»; el glosario técnico (`:266-280`) solo existe dentro del «Detalle técnico» de cada tarea (`NeuralModelosTarea.tsx:103`). Los «k = 2» son visibles en la tabla de Facultades (`NeuralFacultades.tsx:302`). Recomendación: ampliar `TERMINOS_MODULO` con esos términos y vincular la primera aparición de cada uno de forma que el lector lo pueda consultar con un toque, sin depender de `title`.

**M9. El mismo concepto se nombra de formas distintas.**
- Lo anticipado: «El modelo esperaba» (`NeuralLoQuePaso.tsx:177`), «Lo que el modelo anticipa» (`:248`), «Lo que anticipó el modelo» (`NeuralFacultades.tsx:234`, `NeuralModelosGrupos.tsx:126`), «Esperado» y «central» (`neuralLenguaSimple.ts:612`, `NeuralLoQueViene.tsx:175`).
- Lo real: «Ocurrió», «Lo que ocurrió», «Observado hasta hoy».
- Quién: estudiantes, personas, casos, inscripciones, «ingresos» (`NeuralCohortes.tsx:40`), «Personas evaluadas».
- Salida: «No continúan», «deja la UCN», «bajas», «abandono» (en Traslados, con otro significado, `NeuralTraslados.tsx:130-133`).
- «Rango» sirve para el intervalo de incertidumbre (Histórico, Proyecciones) y para el rango central de 25 a 75 % (Cohortes, `:151`).
- Trato: segunda persona en `Elige…`, `¿Quieres ver…?` (`NeuralModelos.tsx:154`), `Inténtalo`, `Léela` (`neuralLenguaSimple.ts:686-689`); usted en `Úselo` (`:649`), `mire primero` (`:531`), `Compare` (`:570`).
Recomendación: una tabla de vocabulario único (esperado/anticipado → «Lo que anticipó el modelo»; real → «Lo que ocurrió»; grupo → «estudiantes» salvo que sea otra unidad) y un tratamiento uniforme, preferentemente impersonal («Elija», «Revise»).

**M10. Formatos numéricos e intervalos distintos.**
Tres notaciones de intervalo: «0,41 (0,22–0,63)» (`NeuralUI.tsx:220-230`), «Entre 8 % y 18 %» (`NeuralFacultades.tsx:229`), «[8 %; 18 %]» (`NeuralModelosTarea.tsx:179`) y, en Proyecciones, «entre X y Y». Decimales: continuidad en 0 decimales en Histórico (`NeuralLoQuePaso.tsx:135`), en 1 decimal en Facultades (`pct`, `NeuralFacultades.tsx:227`) y Cohortes (`NeuralCohortes.tsx:81, 107`). En Proyecciones de continuidad el número clave está en porcentaje y el rango debajo en estudiantes (`NeuralLoQueViene.tsx:235-236`), lo que se puede leer como un error. Recomendación: una sola notación («38 % (entre 31 % y 45 %)»), porcentajes sin decimales en las vistas ejecutivas y con 1 decimal solo en el detalle técnico; que el rango use la misma unidad que la cifra clave.

**M11. Navegación secundaria y títulos con patrones distintos.**
Histórico usa `Segmentado` para los temas (`NeuralLoQuePaso.tsx:52`); Modelos usa pestañas (`NeuralModelos.tsx:65`); Por facultad usa `Segmentado` para el nivel (`NeuralFacultades.tsx:54`). Títulos: preguntas en Histórico, Proyecciones y Calidad; sustantivos en Cohortes («Resultados por generación…», «Evolución por semestre»), Traslados («Balance por programa») y Facultades. «Cómo usarlo» solo existe en Histórico y Proyecciones (`NeuralLoQuePasoTemas.tsx:58-64`); en Modelos hay «Cómo leer los resultados» (`NeuralModelos.tsx:175`) y en Traslados «Cómo se cuenta cada tipo». Recomendación: elegir un patrón de navegación secundaria (pestañas para destinos, control segmentado solo para modos), títulos en forma de pregunta, y «Cómo usarlo» en todas las pestañas que llevan a una acción.

**M12. Orden de encabezados.**
La página tiene un `h1` (`NeuralPanel.tsx:59`); Histórico y Proyecciones usan `h2` por bloque (`NeuralLoQuePasoTemas.tsx:32`) pero Modelos, Facultades, Cohortes, Traslados y Calidad usan `Titulo`, que genera `h3` (`NeuralUI.tsx:288`) sin `h2` previo; el propósito de cada pestaña es un `<p>` (`NeuralPanel.tsx:113-115`). Recomendación: que `Titulo` acepte el nivel (por defecto `h2` dentro de un panel) y añadir un `h2` visible o solo para lector de pantalla con el nombre de la pestaña.

**M13. Control segmentado sin teclado propio de grupo de radio.**
`NeuralUI.tsx:332-361`: `role="radio"` con todos los botones en el orden de tabulación y sin flechas. Para 6 o 7 opciones (tareas) son muchas paradas de tabulador, y la altura es de 36 px (`h-9`). Recomendación: tabindex móvil con flechas, o convertirlo en botones con `aria-pressed`; altura mínima de 44 px en móvil.

**M14. Indicador de foco débil en listas y campos.**
`NeuralUI.tsx:11-13` y `SELECT` (`PercepcionUI.tsx:23-26`): `outline-none` más cambio de color de borde de 1 px. Varios `summary` sin estilo de foco (`NeuralUI.tsx:277`, `NeuralModelosTarea.tsx:92`, `NeuralCalidad.tsx:67` sí lo tiene). Recomendación: contorno visible de 2 px en todos los controles.

**M15. Interacciones que no devuelven la vista al lugar del cambio.**
En Por facultad, «Toca un nombre para ver su detalle arriba» (`NeuralFacultades.tsx:155`) cambia el estado pero no desplaza la pantalla; en móvil el detalle queda muy por encima. En Traslados, «Ver detalle» abre el panel al final de la sección Balance, después de la tabla (`NeuralTraslados.tsx:83-88, 347-355`), y puede quedar fuera de pantalla. Recomendación: mover el foco y el scroll al detalle y devolverlo al botón al cerrar.

**M16. Traslados: la guía no coincide con el orden y usa «abandono» con un sentido propio.**
El propósito dice «Mira primero el balance por programa» (`neuralLenguaSimple.ts:308-311`), pero el balance es la quinta sección (`NeuralTraslados.tsx:79-83`, después de indicadores, tipos, flujos y por año). «Cuentan como abandono» (`:149`) es una convención del módulo que choca con «no continuidad no equivale a deserción» (`neuralLenguaSimple.ts:335`). No hay filtro por facultad. Recomendación: mover el balance al inicio o cambiar el propósito; rotular «Dejan el programa de origen» en lugar de «abandono»; permitir filtrar por facultad de origen o destino con el selector común.

**M17. Tablas anchas en móvil sin columna fija.**
Grupos (hasta 9 columnas, encabezados largos en mayúsculas y sin ajuste de línea, `NeuralModelosGrupos.tsx:120-130, 159`) y Cohortes (6 columnas, p. ej. «Titulados en la duración del plan (5 años)», `NeuralCohortes.tsx:93-95`) obligan a desplazarse en horizontal perdiendo la primera columna; Facultades sí fija la primera columna (`NeuralFacultades.tsx:294, 315`). Recomendación: columna fija en todas las tablas de más de tres columnas y encabezados con ajuste de línea.

**M18. En los gráficos, «pocos casos» se señala solo con opacidad y el tamaño del grupo solo con el cursor.**
`neuralGraficos.ts:12` (opacidad 0,4); `neuralGraficosTareas.ts:179-187`; `neuralGraficosHistorico.ts:106`. La leyenda lo explica en texto, pero marca por marca solo hay diferencia tonal; el número de personas aparece únicamente en el tooltip (`NeuralModelosTarea.tsx:312` dice «Al pasar el cursor…», que no existe en táctil ni con teclado). Una barra al 40 % de opacidad sobre fondo oscuro es casi invisible, lo que contradice el criterio de mostrar todos los tamaños. Recomendación: contorno discontinuo o trama además de la opacidad (0,6 como mínimo) y la cantidad de personas en la etiqueta del eje («Programa X (n = 7)»).

**M19. Gráficos con texto de 10 y 11 px y desplazamiento interno en móvil.**
Tamaños en `neuralGraficosHistorico.ts:95, 129, 216`; `neuralGraficosProyeccion.ts:39, 79`; `neuralGraficosTraslados.ts:92, 137`. El tope de alto del 70 % de la pantalla crea una caja con scroll propio dentro de la página (`EChartsChart.tsx:120-157`), que en táctil compite con el desplazamiento de la página. El diagrama de flujos con 60 flujos en 375 px (`NeuralTraslados.tsx:192-197`) es denso. Recomendación: 12 px como mínimo, ofrecer la tabla en lugar del diagrama por defecto en pantallas angostas y limitar el máximo de flujos a 15 en móvil.

**M20. Estados de error y carga demasiado técnicos o repetitivos.**
`NeuralUI.tsx:94`: «Módulo sin configurar o sin datos» (503) es lenguaje de operador. Cada esqueleto tiene `role="status"` y `aria-live` (`:83`), de modo que con varios bloques el lector de pantalla anuncia «Cargando» varias veces. Al cambiar de filtro, el contenido completo se sustituye por el esqueleto (`NeuralLoQuePaso.tsx:53`), con salto de maquetación; Traslados lo resuelve conservando el resultado previo (`NeuralTraslados.tsx:59-64, 75`) y es el modelo a seguir. Recomendación: «Los datos no están disponibles por ahora. Avise a la DAI», un único anuncio de carga por pestaña y conservar el resultado anterior con opacidad reducida.

**M21. Sin enlace profundo ni estado en la URL.**
La pestaña, el tema y la población viven en `useState` (`NeuralPanel.tsx:34-37`; `NeuralLoQuePaso.tsx:39`). Recargar la página o compartir el enlace vuelve a Histórico/Toda la UCN. Para quien necesita enviar «lo de Ingeniería Civil» a un colega es una fricción real. Recomendación: reflejar pestaña, tema y programa en el hash o la consulta.

### Baja

**B1. Códigos de período en bruto.** «1.er semestre 2021 (202110)» (`NeuralLoQueViene.tsx:33`), «reglamento 2025 (desde 202520)» dentro del gráfico (`neuralGraficosHistorico.ts:134`), «Último período» en Calidad (`NeuralCalidad.tsx:112`). Mostrar solo el texto legible.

**B2. Años fijos en el texto.** «cohortes 2024 y 2025», «2024, 2025 y 2026» (`neuralLenguaSimple.ts:648, 662`) y el valor por defecto «2016» (`NeuralLoQuePaso.tsx:222`) quedarán desactualizados; derivarlos de los datos.

**B3. Leyenda improvisada con guiones.** «`- -` el modelo esperaba» (`NeuralLoQuePaso.tsx:251`) para representar una línea punteada; usar un trazo dibujado como en el resto de las leyendas (`Cuadro`).

**B4. `aria-label` sobre `div` sin rol.** `NeuralPanel.tsx:65`, `NeuralModelosTarea.tsx:60, 256`, `NeuralModelosGrupos.tsx:145`; los lectores lo ignoran. Agregar `role="group"` o convertirlo en texto.

**B5. `aria-controls` hacia paneles inexistentes.** Las pestañas no visitadas apuntan a un panel que aún no se monta (`NeuralPanel.tsx:88-102`) y en Modelos solo existe el panel de la subpestaña activa (`NeuralModelos.tsx:67`). Montar el contenedor vacío o quitar el atributo.

**B6. Puerta de aceptación.** El texto de la casilla «Confirmo lo anterior» (`neuralLenguaSimple.ts:683`) depende de que el lector recuerde qué es «lo anterior»; mejor «Confirmo que leí esta declaración y la acepto». Tras aceptar, la tarjeta desaparece y el foco se pierde (`NeuralAceptacion.tsx:35-37, 96-102`); mover el foco al encabezado del módulo o a la primera pestaña.

**B7. Explicaciones solo en `title`.** El significado de cada semáforo y de «pocos casos» está en atributos `title` (`NeuralModelosSemaforo.tsx:10`; `NeuralUI.tsx:249`), inaccesibles con toque y teclado. La explicación existe en texto en `PROPOSITO_PESTANA.modelos` y en las leyendas, por lo que el riesgo es bajo; considerar un enlace «¿Qué significa?».

**B8. Calidad muestra identificadores internos.** Nombre del chequeo y «marts» (`NeuralCalidad.tsx:46, 98`) dentro del detalle técnico; traducir o agregar una línea de explicación.

---

## 4. Revisión por pestaña

Criterios: lidera con la conclusión (C), jerga explicada (J), carga de lectura (L), interacciones (I), estados vacío/carga/error (E), «pocos casos» (P), móvil 375 px (M).

| Pestaña | C | J | L | I | E | P | M |
|---|---|---|---|---|---|---|---|
| Histórico | Parcial: clave presente, pero tras el gráfico en móvil (A6); primer bloque no es la cifra más citada | Parcial: definiciones plegadas; etiqueta de modelo técnica (M5) | Alta: 14 bloques en 4 temas y 5 líneas de apoyo por bloque (M6) | Buenas; selector sin búsqueda (A3) | Completos (`:53-55`) | Casi total; reglas distintas (M7) | Gráficos 10 px, clave debajo (A6, M19) |
| Proyecciones | Sí: umbral primero («dónde poner tutorías»); el aviso de «orientativa» precede a la cifra de eliminación (`NeuralLoQueViene.tsx:272`), lo que es honesto pero demora la cifra | Parcial: «umbral», «corte» con código en bruto (B1, M8) | Media-alta: «Cómo leerla» muy largo (M6) | Tabla por cohorte plegable | Completos | Sí | Tabla con `min-w-[34rem]` y scroll propio (adecuado) |
| Modelos | Parcial: semáforo y «resultado en palabras» lideran en la ficha; en el resumen son tarjetas | Débil: siglas y arquitecturas (M3, M8) | Alta: 6 subpestañas más 6 tareas más opciones | Muchos controles en cadena (`NeuralModelosTarea.tsx:59-70`) | Completos, pero con comandos de consola (M4) | Marca en grupos y calibración | Etiquetas largas, tabla de 9 columnas (M3, M17) |
| Por facultad y programa | Parcial: tarjetas por tarea con cifra grande; la conclusión («¿el modelo describe bien a la facultad?») debe inferirla el lector comparando dos cifras | Parcial: «T1…T6», «k =» (M8) | Media: 6 tarjetas más tabla comparativa | Fila clicable sin desplazamiento (M15); sin «Toda la UCN» (A1) | Completos y con mensajes distintos para «no calculado» y «sin cifra» (bien resuelto) | Sí, incluida la tabla | Mejor tabla móvil del módulo (columna fija) |
| Cohortes | Débil: el primer estado es vacío («Elige un programa») | Parcial: «en curso» sí se explica | Baja | Selector propio (A3) | Carga y vacío; falta marca en denominadores (M7) | Parcial (M7) | Tabla de 6 columnas sin columna fija (M17) |
| Traslados | Parcial: la guía dice balance primero, que va quinto (M16) | Parcial: «abandono», «ambiguos» | Alta: seis secciones largas | Filtros claros; el resultado previo se conserva (bien resuelto) | Completos | Parcial: falta en balance (M7) | Diagrama de flujos denso (M19) |
| Calidad | Sí: responde «¿los datos están en orden?» al inicio | Parcial (B8) | Baja | Pocas | Completos | No aplica | Tablas planas, adecuado |

---

## 5. Accesibilidad básica

- **Significado solo por color.** El semáforo es punto más texto (bien). Neto positivo y negativo lleva signo (bien). «Pocos casos» en gráficos depende de opacidad (M18). Diagramas de flujos y barras apiladas usan color por tipo pero repiten la etiqueta en la tabla (aceptable). Conviene comprobar la paleta de «deja la UCN» frente a «eliminado» con un simulador de daltonismo.
- **Alternativas textuales de gráficos.** Etiqueta corta más `figcaption` solo para lectores de pantalla (`NeuralUI.tsx:367-374`), sin los datos (A7).
- **Teclado y foco.** Pestañas con flechas, Inicio y Fin (bien, `NeuralUI.tsx:149-159`); tablas ordenables con botones y `aria-sort` (bien); regiones de tabla enfocables (bien). Debilidades: M13 y M14.
- **Orden de encabezados.** M12.
- **Mensajes dinámicos.** Cobertura y recuento de filtros con `aria-live` (bien); los cambios de resultado no se anuncian (M20).

---

## 6. Los cinco cambios de mayor valor

1. **Reestructurar las pestañas en tres bloques** (Lo que pasó: Histórico, Cohortes, Traslados · Lo que viene: Proyecciones · Cuánto confiar: Modelos, Modelo por facultad, Calidad de los datos) y renombrar «Por facultad y programa» (A1, A8, M1, M2).
2. **Un único selector de población con búsqueda de programa** (tolerante a tildes, «nombre (código)», facultad como contexto), reutilizado en Histórico, Proyecciones, Cohortes y Modelo por facultad, más un chip persistente con la población en cada bloque (A2, A3).
3. **Conclusión primero**: número clave antes del gráfico en móvil, franja «Lo esencial» al abrir Histórico y bloque de continuidad como primero (A6, 2.4).
4. **Móvil**: barra de pestañas con degradado y desplazamiento a la pestaña activa, columna fija en tablas anchas y etiquetas cortas en Modelos (A5, M3, M17, M19).
5. **Confiabilidad de los gráficos**: desplegable «Ver los datos» en cada gráfico, aviso cuando el CDN no carga y marca «pocos casos» con trama y tamaño en la etiqueta (A7, M18). En paralelo, un vocabulario y un formato numérico únicos (M9, M10), que es el cambio de menor costo con mayor efecto sobre la sensación de rigor.
