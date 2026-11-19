# DAI Neural en GitHub Pages (diseño)

**Fecha:** 19-11-2026 · **Estado:** construido y publicado en el warehouse (19-11-2026). Faltan el despliegue de wh-api y el push del frontend.
**Repositorios:** `DAI-BOVEDA` (exportación y frontend) y `wh-api` (rutas de lectura).

## Intención
El usuario quiere que DAI Neural se vea en el sitio publicado (https://sebaza.github.io/DAI-BOVEDA/), igual que el Termómetro, sin instalar la Bóveda local. Hoy el modo Pages lo excluye a propósito: `frontend/src/app/neural/page.tsx` muestra «no disponible», y sus datos solo existen en el Postgres local.

**Cambio de regla:** hasta ahora, las tablas de Neural se creaban solo en localhost. El 19-11-2026 el usuario decidió llevar los datos de Neural al warehouse, al esquema `percepcion`, para que wh-api los entregue.

## Objetivos / no objetivos / antiobjetivos
- **Objetivos:**
  - Todas las pestañas de Neural funcionan en Pages, con el mismo PIN del Termómetro.
  - Las cifras son idénticas a las de la Bóveda local en las combinaciones publicadas.
  - Un comando local vuelve a publicar los datos después de cada corrida del pipeline.
- **No objetivos:**
  - Filtros de años libres en Traslados dentro de Pages (ver Decisión 5).
  - Registrar la casilla de aceptación por persona en Pages.
  - Cambios en los modelos, en el pipeline de Redes o en las cifras.
  - Sacar las credenciales y los datos personales del README de wh-api: es un problema real, pero es otra tarea.
- **Antiobjetivos:**
  - Cualquier fila por estudiante en el warehouse, aunque esté seudonimizada. Esto incluye `ficha_episodio` y `programa_traslados`.
  - Nombres, RUT, listas de estudiantes o rankings de docentes.
  - Cifras de Neural sin PIN (por ejemplo, JSON estático dentro del sitio).
  - Un token de Percepción que pueda escribir algo, o que lea otra ruta además de `/percepcion/*` y `GET /neural/*`.

## Restricciones
- En el warehouse solo se escribe en las tablas `percepcion.neural_*`, con la cuenta `warehouse_user`. Esa cuenta es dueña del esquema `percepcion`, verificado el 19-11-2026.
- Las credenciales se pasan en línea en cada comando. Nunca se guardan en archivos ni en el repositorio.
- Se conservan las marcas «pocos casos» (`POCOS_CASOS`), los avisos y las notas de cada respuesta, tal como las produce el backend.
- Los modelos no se reentrenan y las predicciones no se tocan.
- La revisión del bundle público en `.github/workflows/pages.yml` debe seguir pasando: nada de `curacion`, `forzar`, `dev-login` ni `accounts.google.com`.
- Español neutro en los textos nuevos, sin desborde a 375 px y con los finales de línea de cada archivo.

## Enfoques considerados
1. **Tablas agregadas en el warehouse y rutas reescritas en JavaScript dentro de wh-api.**
   - El frontend tendría todos los filtros.
   - Contra: hay que portar a JS la lógica de 12 rutas en Python y mantener las dos versiones iguales.
2. **Respuestas ya calculadas en el warehouse (elegido por el usuario).**
   - Un comando local llama al backend real de Neural para cada combinación publicada y guarda cada respuesta JSON.
   - wh-api solo busca la respuesta y la devuelve.
   - La paridad queda asegurada por construcción, y casi no hay lógica que portar.
   - Contra: los filtros que se combinan mucho (los años de Traslados) se limitan en Pages.
3. **JSON estático dentro del sitio de Pages.** Descartado: las cifras quedarían abiertas sin PIN.

## Decisiones (del usuario salvo donde se indica)
1. **Dónde se guardan:** en el esquema `percepcion` del warehouse, en tablas con el prefijo `neural_`. El prefijo es decisión del constructor.
2. **Acceso:** el mismo PIN del Termómetro. wh-api acepta el token de Percepción también en `GET /neural/*`, y en ninguna otra ruta nueva.
3. **Formato** (decisión del constructor; el usuario la puede corregir):
   - Una tabla `percepcion.neural_respuesta` con:
     - `ruta` (text), por ejemplo `/neural/traslados/resumen`;
     - `consulta` (text), la consulta canónica: claves ordenadas, sin valores por defecto, `""` si no hay ninguna;
     - `contenido` (jsonb), la respuesta tal cual;
     - `generado_en` (timestamptz).
   - Clave primaria: `(ruta, consulta)`.
   - Una tabla `percepcion.neural_publicacion` con una sola fila: fecha, versión del exportador, número de respuestas y bytes totales.
4. **Comando de publicación** (decisión del constructor):
   - Es un script en `backend/scripts/` que llama en proceso a las rutas reales de FastAPI (cliente de prueba de FastAPI, contra la base local) para cada combinación.
   - Reemplaza las filas en el warehouse dentro de una sola transacción, con borrado e inserción. Una corrida que falla no deja una publicación a medias.
   - Imprime solo conteos y tamaños, nunca contenido.
   - Rechaza la publicación si alguna respuesta trae claves de identidad, como `rut`, `nombre_estud`, `nombre_prof`, `docente_key` o `nrc`.
5. **Traslados en Pages:**
   - El filtro de años se reemplaza por tres rangos fijos: «Todos los años», «Últimos 10» y «Últimos 5», contados desde el último año disponible.
   - El tipo de traslado (6 más «todos») y «Solo los que cuentan como abandono» se mantienen.
   - Son 42 combinaciones en el resumen y 42 por cada programa en el detalle (69 programas). En total, unas 2.900 respuestas.
   - La Bóveda local mantiene el rango libre.
6. **Combinaciones publicadas en las demás rutas** (las enumera el constructor desde los datos):
   - `/neural/historico` y `/neural/proyeccion`: Toda la UCN, cada facultad y cada programa que lista su `meta`.
   - `/neural/programa/{cod}/cohortes`: cada programa de `/neural/programas`.
   - `/neural/modelos/*`: cada tarea, y en `grupos` cada nivel, variante y corte que existe.
   - `/neural/modelos/malla-ejemplo`: los valores de `cod_programa` y `semestre_max` que pide el frontend.
   - Una sola respuesta para `/neural/programas`, `/neural/modelos/resumen`, `/neural/modelos/tareas` y `/neural/calidad`.
7. **Combinación no publicada:** wh-api responde 404 con `{"detail": "Esta combinación no está publicada en el sitio. Está disponible en la Bóveda local."}`. Si la ruta existe pero no hay ninguna publicación, responde 503.
8. **Casilla de aceptación en Pages** (decisión del constructor):
   - Se muestra el mismo texto de aceptación una vez por pestaña del navegador (`sessionStorage`) y no se registra.
   - `GET` y `POST /neural/aceptacion` no se publican.
   - El texto dice que en el sitio publicado la aceptación no queda registrada.
9. **Frontend en modo Pages:**
   - `page.tsx` deja de mostrar «no disponible» y entra por `PaginaPages`.
   - `MODULOS_PAGES` incluye Neural.
   - `neural.ts` usa `API_PAGES_URL` con el token del PIN, como `percepcion.ts`.
   - Cohortes, Histórico y los demás no cambian; Traslados cambia el control de años (Decisión 5).
   - El texto de `NoDisponible`, que habla de información reservada, se retira o se ajusta.

## Detalles resueltos tras la revisión del constructor (decisiones de Claude; el usuario las puede corregir)
1. **Rangos fijos de años:**
   - «Últimos 10» son los 10 años calendario que terminan en el último año disponible: `anio_desde = max − 9`, sin `anio_hasta`. «Últimos 5» usa `max − 4`. «Todos los años» no manda `anio_desde`.
   - El último año entra tal como está en la base local, aunque esté incompleto, igual que en la Bóveda.
   - El exportador fija esos valores con el `max` de los datos. El frontend los calcula con `anios_disponibles` de la primera respuesta, que es el resumen sin filtros.
2. **Consulta canónica:**
   - Son los parámetros que el frontend realmente manda, decodificados (UTF-8, sin codificar porcentajes), con claves ordenadas, unidos como `k=v&k2=v2`, y sin parámetros vacíos.
   - No se quitan valores «por defecto»: el exportador genera exactamente las consultas que arma `neural.ts`. Por ejemplo, en `grupos` siempre van `variante` y `corte`.
   - wh-api canoniza y hace una búsqueda exacta. Un parámetro de más o un valor desconocido da 404.
   - La canonización tiene una prueba compartida con los mismos casos en Python y en JS, incluido un nombre de facultad con tildes.
3. **Quién lee `GET /neural/*`:**
   - Solo el token del PIN, a través de la misma regla que hoy lo limita a `/percepcion`, ampliada a `GET /neural`.
   - Las cuentas JWT normales de wh-api no lo leen.
   - Cualquier método que no sea GET bajo `/neural` responde 403 con ese token.
4. **Tablas y permisos:**
   - El DDL va en `backend/sql/008_neural_publicacion_warehouse.sql` (DAI-BOVEDA), con `CREATE TABLE IF NOT EXISTS`. El exportador lo aplica antes de publicar.
   - Los permisos de lectura copian los de una tabla existente de Percepción (`percepcion.percepcion_hecho_diario`). Así `poolWH` lee las nuevas igual que lee las de Percepción, sin adivinar su rol.
   - Orden de despliegue: primero la publicación, después wh-api y al final el push del frontend.
5. **Texto de confidencialidad:**
   - Se exporta como una fila de `GET /neural/aceptacion` con el texto y la versión. Se publica solo el GET y nunca el POST.
   - En Pages, la marca de «aceptado» va en `sessionStorage`, ligada a esa versión.
6. **Mensajes 404 y 503:** en modo Pages, `neural.ts` muestra el `detail` de la respuesta también en 404, para que se lea el mensaje de la Decisión 7. En modo local no cambia.
7. **Calidad de los datos:**
   - Se publica completa: son conteos, chequeos y fechas, sin datos de personas, y es la misma pestaña que ve el equipo localmente.
   - La revisión de identidad del exportador recorre todas las claves de cada JSON. Rechaza cualquier clave de una lista cerrada: `rut`, `dv`, `paterno`, `materno`, `nombre_estud`, `nombre_prof`, `nombre_banner`, `email`, `correo`, `telefono`, `fecha_nacimiento`, `docente_key`, `nrc`, `seccion`, `id_estudiante` y `pidm`.
   - También rechaza cualquier lista con más de 0 elementos bajo claves que terminen en `_estudiantes`.
8. **«Sin publicación»:**
   - wh-api responde 503 cuando `neural_publicacion` no tiene su fila. Si la tiene pero falta la combinación pedida, responde 404.
   - En Pages, Neural muestra arriba la línea «Datos publicados el <fecha>», tomada de `neural_publicacion`, que se expone en `GET /neural/publicacion`.

## Lo que queda al constructor
- La canonización exacta de la consulta, que debe ser la misma en el exportador y en wh-api.
- Dónde montar las rutas en wh-api: un `queries/neural.js` siguiendo el patrón de `percepcion/`, por ejemplo.
- Cómo validar la paridad: una prueba que compare algunas respuestas del warehouse con la Bóveda local.
- La forma visual de los tres rangos fijos.
- Si hace falta comprimir `contenido`. Primero se mide el tamaño total.
