# DAI Neural: buscador de programas y reorganización de pestañas (diseño corto)

**Fecha:** 19-11-2026 · **Estado:** construido (19-11-2026), aprobado por el usuario («Todo, con pestañas»). Falta solo la revisión visual de los gráficos y del aviso de carga fallida.
**Base:** auditoría `docs/superpowers/specs/2026-11-19-neural-ux-auditoria.md` (hallazgos A1–A8 y los cinco cambios de mayor valor).

## Intención
El usuario quiere elegir un programa directamente desde el selector donde aparece «Toda la UCN», sin tener que conocer antes su facultad. También pidió una auditoría de experiencia de uso de todas las pestañas y aprobó aplicar sus hallazgos de prioridad alta, incluida la reorganización de pestañas. La audiencia son vicerrectores y directores: leen rápido y citan cifras en informes.

## Objetivos / no objetivos / antiobjetivos
- **Objetivos:**
  - Un buscador de facultad o programa en el selector de población compartido.
  - Un solo componente de población, reutilizado en Histórico, Proyecciones, Cohortes y «Modelo por facultad».
  - Pestañas reagrupadas y renombradas, con una barra usable en el celular.
  - La población elegida visible en cada bloque.
  - Conclusiones primero, textos que no prometen más de lo que muestran, y gráficos que no fallan en silencio.
- **No objetivos:**
  - Los hallazgos de prioridad media y baja de la auditoría, salvo cuando caen dentro de un cambio de este diseño.
  - Cambios en Redes, en el backend o en los datos.
- **Antiobjetivos:**
  - Listas por estudiante, nombres, RUT o rankings de docentes.
  - Un filtro de población global que aparente cambiar Modelos, Calidad o Traslados.

## Restricciones
- Solo frontend (`frontend/src`); sin cambios en la API.
- Español neutro; sin desborde a 375 px; objetivos táctiles de al menos 44 px en los controles nuevos.
- Los códigos T1–T6 se muestran siempre junto a su nombre en español (spec 2026-11-18, ítem 7).
- Se mantienen la casilla de aceptación, la marca «pocos casos» con el umbral único `POCOS_CASOS` y la regla de `resolverFiltro` (nunca pedir un programa que la pestaña no lista).
- Se conservan los finales de línea de cada archivo.

## Enfoques considerados
- **A. Combobox accesible propio dentro de `NeuralSelectorPoblacion` (elegido).** Patrón ARIA 1.2 de combobox con lista. Muestra el nombre, el código y la facultad, ignora tildes y mayúsculas, y al elegir fija la facultad y el programa a la vez.
- **B. `<input list>` con `<datalist>`.** Menos código, pero se comporta de forma irregular en el celular y con lectores de pantalla, y no puede mostrar la facultad como texto secundario. Descartado.
- **C. Un filtro global en todas las pestañas.** Descartado: Modelos y Calidad se evalúan sobre toda la UCN, y Traslados es una relación de origen a destino.

## Decisiones (del usuario)
1. **Buscador:** desde 2 caracteres, sin distinguir tildes ni mayúsculas, por nombre o código, en todas las facultades a la vez.
   - Cada resultado muestra «Nombre (código)» con la facultad debajo.
   - Elegir un resultado fija la facultad y el programa.
   - Las listas de facultad y programa se mantienen como camino sin teclado.
2. **Selector único** en Histórico, Proyecciones, Cohortes y «Modelo por facultad».
   - Usa la lista propia de cada pestaña.
   - Respeta la nota existente cuando un programa o una facultad no existe en esa pestaña.
   - Agregado el 19-11-2026 a pedido del usuario: en Traslados, el programa elegido abre su detalle arriba del resumen, y «Ver detalle» cambia el programa de todas las pestañas. El resumen sigue siendo de toda la UCN, y con solo una facultad elegida una nota lo dice.
3. **Pestañas**, en tres grupos con separación visual:
   - «Lo que pasó»: Histórico, Cohortes, Traslados.
   - «Lo que viene»: Proyecciones.
   - «Cuánto confiar»: Modelos, «Modelo por facultad» (antes «Por facultad y programa»), «Calidad de los datos» (antes «Calidad»).
   - Histórico sigue siendo la pestaña inicial.
4. **«Modelo por facultad»** toma la selección compartida como valor inicial. Su propósito dice que ahí se mide el modelo, no la historia.
5. **Barra de pestañas en el celular:** degradado en los bordes y desplazamiento hasta la pestaña activa, con el mismo patrón que Percepción.
6. **Población visible:** una etiqueta con la población activa en el encabezado de cada bloque de Histórico y Proyecciones. Las pestañas que no cambian con la población lo dicen una vez arriba.
7. **Orden de lectura:**
   - En el celular, el número clave va antes del gráfico.
   - En Permanencia, el bloque de continuidad al año siguiente va primero.
   - Histórico abre con una franja «Lo esencial» de 3 cifras enlazadas a su bloque.
8. **Textos honestos:** donde se muestran los primeros N, el texto lo dice («se muestran los 10 mayores de N») y una tabla plegada ofrece todos.
9. **Confianza en los gráficos:**
   - Si el gráfico no carga, se dice.
   - `MarcoGrafico` ofrece «Ver los datos» en los gráficos sin tabla equivalente.
   - La curva de Cohortes usa `MarcoGrafico`.
   - «Pocos casos» no se comunica solo con transparencia: también con un texto en el tooltip o la leyenda.

## Lo que queda al constructor
- La forma visual exacta de los grupos de pestañas, de la etiqueta de población y de la franja «Lo esencial».
- Qué 3 cifras lleva «Lo esencial», siempre tomadas de la respuesta que Histórico ya recibe.
- El orden de las tareas.
