# DAI Neural sin la regla de menos de 10 — diseño

**Fecha:** 18-11-2026 · **Estado:** construido (D122, 18-11-2026).

## Intención
Las autoridades que usan DAI Neural son personas de confianza de la DAI y necesitan ver todas las cantidades, también las de grupos pequeños. Ocultar grupos de menos de 10 personas les quita información que necesitan para decidir. La protección pasa de ocultar cifras a un compromiso explícito y registrado de quien mira.

## Objetivos / no objetivos / antiobjetivos
- **Objetivos:**
  - Eliminar la regla de menos de 10 en todo el módulo DAI Neural, en todas las pestañas.
  - Agregar una casilla de aceptación al inicio de la sección, con registro en el servidor.
  - Mostrar los grupos pequeños con su n y con una marca de inestabilidad, no ocultarlos.
- **No objetivos:**
  - Reentrenar modelos o cambiar las predicciones guardadas.
  - El módulo Percepción, que tiene sus propias reglas.
- **Antiobjetivos:**
  - Nombres, RUT, listas o filas por estudiante.
  - Cualquier ranking de docentes.
  - Una casilla solo visual que se pueda saltar llamando a la API.

## Restricciones
- Solo lectura.
- `sexo` solo para equidad; `cohorte_anio` nunca es variable en T3–T6.
- Punto en el tiempo y corte 202610, como hoy.
- Las migraciones nuevas van con su runner y nunca se edita una ya aplicada. Toda migración nueva se agrega a `EXTRA_DDL` de `backend/tests/test_neural_api.py`.
- Las credenciales van solo en línea por comando.
- Texto en español neutro; sin desborde a 375 px.
- La ley vigente: Ley 19.628. La Ley 21.719 rige desde el 1-12-2026, salvo que se publique la postergación en trámite (Boletín 18.623-07).

## Enfoques considerados
- **A. Eliminar la supresión de punta a punta (elegido).** El productor (Redes) publica todos los datos, el servidor los sirve tras la aceptación y se borra la maquinaria de supresión. Es más simple y no deja código complejo que ya tuvo filtraciones.
- **B. Mantener la supresión con el umbral en 1.** Guarda la opción de una vista pública, pero deja código complejo (complemento entre facultades, «otros») que ya filtró dos veces. Descartado. Una copia de ese trabajo, nunca commiteado, queda en las instantáneas `.superpowers/sdd/2026-11-18-lo-que-paso-temas-y-lo-que-viene/snap-*`.

## Decisiones (del usuario)
1. **Casilla de aceptación** al inicio de la sección DAI Neural. El texto declara que la persona es de confianza de la DAI, que conoce la Ley 19.628 y la Ley 21.719 y que el uso es interno y confidencial.
   - El servidor registra quién aceptó, cuándo y qué versión del texto.
   - Toda ruta `/neural/*` responde «aceptación requerida» hasta que el usuario acepte la versión vigente.
   - Si el texto cambia, se vuelve a pedir.
2. **Sin la regla de menos de 10** en todo el módulo:
   - Redes deja de ocultar al construir artefactos y marts; se regeneran sin reentrenar.
   - El servidor deja de ocultar.
   - Se borran el complemento entre facultades, la agrupación en «otros» por tamaño y la eliminación de filas de rankings.
   - El frontend quita la insignia «Grupos con menos de 10 personas ocultos» y los avisos de ocultamiento.
3. **Mostrar los grupos pequeños con honestidad:**
   - Todo porcentaje lleva su n.
   - Los grupos de menos de 10 llevan la marca «pocos casos» y un color más tenue.
   - Las métricas de modelos por grupo se muestran para todo tamaño, con su intervalo de 95 %. Hoy se publican solo con n ≥ 100 y 10 eventos.
4. **Cifras del modelo en grupos pequeños (decisión del usuario del 18-11-2026).** Las cifras del modelo también se muestran en grupos de menos de 10. Esto incluye el esperado por programa o grupo y las proyecciones de «Lo que viene». Se advirtió que en un grupo de 1 eso equivale a la predicción de esa persona, así que el Gate 4 se levanta para cifras agregadas en este módulo.
5. **Se mantienen:**
   - Sin listas ni filas por estudiante en la API ni en la vista.
   - Sin nombres, RUT ni identificadores de persona.
   - Sin ranking de docentes.
   - La insignia «Sin predicciones individuales» deja de ser exacta y se reemplaza por «Sin nombres ni listas de estudiantes». Es una decisión del constructor.

## Agregado aprobado el 18-11-2026: filtro por programa, modelo visible y nombres
6. **Filtro por programa** en las dos pestañas (hoy «Lo que pasó» y «Lo que viene»).
   - Selector en cascada: Toda la UCN → Facultad → Programa. El selector de programa aparece al elegir una facultad.
   - Redes calcula cada bloque también por programa.
   - Los bloques que describen el modelo, no una población («Cómo decide el modelo», «Ganar un semestre»), muestran lo mismo con un programa elegido y lo dicen en una nota.
7. **Modelo visible en cada conclusión.**
   - Un bloque que usa un modelo lleva una etiqueta: código y nombre de la tarea, modelo conservado y corte. Por ejemplo: «T1 · No continuidad al año siguiente · CatBoost con beneficios · corte al 1.er semestre».
   - Un desplegable «Cómo se calculó» da el detalle: población, partición y si es esperado o proyección.
   - Un bloque solo descriptivo dice «Dato observado, sin modelo».
   - Si un bloque usa más de un modelo (por cohorte), la etiqueta va en cada cohorte del detalle.
   - Los códigos T1–T6 pasan a mostrarse al lector, siempre junto a su nombre en español. Esto reemplaza la regla anterior de ocultarlos.
8. **Nombres más formales.** El usuario eligió «Proyecciones» y pidió para la primera pestaña un nombre corto en la línea de «pasado»:
   - Pestañas: «Lo que pasó» → «Histórico»; «Lo que viene» → «Proyecciones».
   - Temas de «Histórico»:
     - «Permanencia» queda igual.
     - «Ramos» → «Rendimiento en asignaturas».
     - «Egreso y causas» → «Egreso y eliminación».
     - «Cómo decide el modelo» → «Fundamentos del modelo».
   - Los títulos de bloque siguen como preguntas.

## Decisiones del constructor
- **La tabla de aceptaciones** vive en el esquema `boveda` de la base de accesos (`backend/sql/006_neural_aceptacion.sql`). La conexión de Neural es de solo lectura y no puede guardarla.
- **El texto de aceptación y su versión** viven en el backend, que los sirve. Así el frontend siempre muestra la versión que el servidor exige.
- **Migración 033 de Redes:** quita los CHECK `n >= 10` y `eventos >= 10` (023, 028) y las columnas de supresión. No se editan migraciones aplicadas.
- **Las métricas por grupo** se reconstruyen desde las predicciones guardadas y los snapshots, sin reentrenar.
  - T1 con cargas no tiene predicciones guardadas; se regeneran con el modelo conservado `t1_k1_cb_ben_pit`, que pasa `verificar`.
  - Una métrica sin eventos, o con todos los casos en un solo valor, queda «no calculable». No se inventa.
- **Umbrales que se mantienen:** los que cambian el ajuste del modelo, como el mínimo de filas por programa en la línea base o las categorías raras. No deciden qué se muestra.
- **Documentos de benchmark 08–12:** son registro histórico y no se regeneran. D122 lo indica.

## Lo que queda al constructor
- El formato del código de error y la forma del panel.
- Cómo se marca «pocos casos» en cada gráfico.
- El orden de las tareas.
- Qué textos de las decisiones D89, D121 y otras de `Redes/docs/00_plan.md` se actualizan con una decisión nueva (D122).
