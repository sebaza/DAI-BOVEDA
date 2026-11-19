# Publicación en GitHub Pages (modo `pages`)

El Termómetro Institucional puede publicarse como sitio estático de **solo lectura**. En ese
modo no hay backend FastAPI, ni Google, ni herramientas de administración: los datos salen de
la API institucional **wh-api** (`GET /percepcion/*`) y el acceso es por clave (PIN).

El modo local (backend FastAPI + login de Google + Curación) no cambia.

## Variables de entorno (se leen al compilar)

| Variable | Valor | Para qué |
| --- | --- | --- |
| `NEXT_PUBLIC_MODO` | `pages` | Activa el modo Pages. `npm run build:pages` ya la fija; sin ella el build es el modo local. |
| `NEXT_PUBLIC_API_BASE_URL` | URL de wh-api, sin `/` final | Base de `/percepcion/acceso` y `/percepcion/*`. |
| `NEXT_PUBLIC_BASE_PATH` | `/nombre-del-repo` (o vacío) | Sub-ruta de Pages. Configura `basePath` y `assetPrefix`. Debe empezar con `/`. |

Variables solo del script `build:pages`:

| Variable | Para qué |
| --- | --- |
| `PAGES_PERMITIR_LOCAL=1` | Permite compilar con una API en `localhost` / `http` (solo pruebas). Sin esto el script **se niega** a compilar si la URL está vacía, no es https o apunta a localhost / 127.0.0.1 / ::1. |
| `PAGES_FEEDBACK_URL` | URL externa del formulario de retroalimentación. Si no se define, el script **fuerza vacío** `NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL`, para que nada de `frontend/.env.local` se filtre al sitio público. |

El script imprime solo el origen de la API efectiva.

Son `NEXT_PUBLIC_*`: quedan escritas en el JavaScript publicado. Nunca pongas secretos ahí.

## Compilar

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=https://api.ejemplo.cl NEXT_PUBLIC_BASE_PATH=/boveda npm run build:pages
```

En Git Bash de Windows, antepón `MSYS_NO_PATHCONV=1` (si no, `/boveda` se convierte en una ruta de disco).

El resultado es una **carpeta estática** `frontend/out/` (HTML, JS y CSS). Se sirve tal cual desde
cualquier hosting estático; no hay servidor Node. No hay workflow de GitHub Actions todavía
(el destino de hospedaje no está decidido).

## CORS en wh-api

El navegador llama a wh-api desde otro origen, así que el **origen de Pages** (por ejemplo
`https://usuario.github.io`, sin ruta) debe estar en `CORS_ORIGINS` de wh-api. Sin eso, todo
fallará como "error de red".

## Cabeceras de seguridad

Pages no permite cabeceras propias, así que el build agrega por `<meta>` un
`Content-Security-Policy` (`connect-src` = el origen de `NEXT_PUBLIC_API_BASE_URL`; scripts de
jsDelivr para ECharts; Google Fonts) y `referrer`. `script-src` y `style-src` llevan
`'unsafe-inline'` porque la exportación estática de Next incrusta scripts de arranque y los
componentes usan `style`. `frame-ancestors` **no** puede fijarse desde `<meta>` (el navegador lo
ignora): no hay protección contra incrustación (clickjacking) en Pages.

## Qué incluye y qué no

- Acceso: pantalla de clave -> `POST /percepcion/acceso`. El token (Bearer) vive en `sessionStorage`
  junto con su vencimiento; al vencer, o ante un 401/403 de cualquier consulta (en Neural, solo ante un 401), se borra y vuelve
  la pantalla de clave. "Salir" lo borra a mano. No se usan cookies.
- Rutas: `/` es el recibidor (un compartimento por módulo, de la lista `MODULOS_PAGES` en
  `PaginaPages.tsx`; la clave abre todos) y `/percepcion/` es el Termómetro. Ambas piden la clave.
- Pestañas visibles: Resumen, Alertas, Comparar y Conversación.
- Excluido (y fuera del bundle): Curación (calidad, revisión, temas, subtemas), Simulación,
  administración de marcas de contexto (crear/editar/borrar eventos), login de Google, dev-login y
  la regeneración del resumen semanal (`forzar`, que wh-api rechaza con 403).
- Piso de privacidad: wh-api oculta el detalle de celdas con pocos comentarios o menciones
  (`detalle_suprimido`); la interfaz lo muestra como "detalle oculto" en vez de números.

## DAI Neural en Pages

DAI Neural se publica en el sitio con el mismo acceso por clave (PIN), también de solo lectura.

### Qué se publica

- Respuestas **ya calculadas** de la Bóveda local, guardadas en el warehouse en las tablas
  `percepcion.neural_respuesta` (una fila por ruta y filtros) y `percepcion.neural_publicacion`
  (fecha y tamaño de la última publicación). Son equivalentes en JSON a las del modo local, no
  idénticas byte a byte (Postgres normaliza el orden de las claves).
- wh-api las lee con el mismo PIN (`GET /neural/*`, solo lectura). Solo se guardan las respuestas
  agregadas de las rutas públicas; además, el exportador revisa las claves (no los valores) de cada
  respuesta y aborta si encuentra alguna de identidad.
- Una combinación de filtros que no se exportó responde 404 y el sitio lo indica. Traslados se
  limita a rangos de años fijos (todo el período, últimos 10 y últimos 5 años).
- La declaración de confidencialidad se acepta solo en el navegador (`sessionStorage`); en Pages
  no queda registrada.

### Publicar los datos

El exportador es `scripts/publicar_warehouse_neural.py`. Los valores entre `<...>` son
marcadores: no escribas credenciales reales en la documentación ni en el historial.

```bash
cd backend
# 1) Prueba en seco: recolecta y revisa, no escribe nada
.venv/Scripts/python.exe ../scripts/publicar_warehouse_neural.py \
  --origen "postgresql+psycopg://<usuario>:<clave>@localhost:<puerto>/<base_neural>?options=-csearch_path%3Dneural_mart,neural_core,neural_meta" \
  --dry-run

# 2) Publicación real
.venv/Scripts/python.exe ../scripts/publicar_warehouse_neural.py \
  --origen "postgresql+psycopg://<usuario>:<clave>@localhost:<puerto>/<base_neural>?options=-csearch_path%3Dneural_mart,neural_core,neural_meta" \
  --destino "postgresql+psycopg://<usuario>:<clave>@<host_warehouse>:<puerto>/<base_warehouse>"
```

- `--origen`: URL de la base local de Neural, con `search_path` `neural_mart,neural_core,neural_meta`.
  También se puede dar con `NEURAL_DATABASE_URL`.
- `--destino`: URL del warehouse. También se puede dar con `NEURAL_WH_DATABASE_URL`.
- El script no imprime URLs ni credenciales. Rechaza origen y destino iguales.
- La escritura es una sola transacción: si algo falla, queda la publicación anterior.
- Al terminar imprime la cantidad de respuestas y de roles a los que copió permisos.
- Repite el comando después de cada corrida del pipeline de Neural.

Al compilar el frontend desde Git Bash de Windows, antepón `MSYS_NO_PATHCONV=1` a `npm run build:pages`
(ver «Compilar»).

### Orden de despliegue (obligatorio)

1. **Publicar los datos** (comando anterior).
2. **Desplegar wh-api** con la ruta `/neural`.
3. **Subir el frontend** (push a Pages).

Si el frontend queda en línea antes que wh-api, wh-api responde 403 a `/neural/*` y Neural no
carga. Datos antes que wh-api no causa problemas. Si wh-api corre sin datos o sin permiso de lectura
sobre las tablas, Neural muestra «Los datos de DAI Neural aún no están publicados.».

### Verificación posterior

- La salida del exportador muestra una cantidad de roles con permisos copiados distinta de cero.
- El rol que usa wh-api puede hacer `SELECT` sobre `percepcion.neural_respuesta` y
  `percepcion.neural_publicacion`.
- `GET /neural/publicacion` con un token del PIN (`Authorization: Bearer ...`) responde 200 con la
  fecha y la cantidad de respuestas.
- En el sitio, Neural carga y muestra «Datos publicados el …».
- Prueba una combinación no publicada a propósito: debe mostrar «Esta combinación no está
  publicada en el sitio».
