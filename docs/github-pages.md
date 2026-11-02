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
  junto con su vencimiento; al vencer, o ante un 401/403 de cualquier consulta, se borra y vuelve
  la pantalla de clave. "Salir" lo borra a mano. No se usan cookies.
- Pestañas visibles: Resumen, Alertas, Comparar y Conversación.
- Excluido (y fuera del bundle): Curación (calidad, revisión, temas, subtemas), Simulación,
  administración de marcas de contexto (crear/editar/borrar eventos), login de Google, dev-login y
  la regeneración del resumen semanal (`forzar`, que wh-api rechaza con 403).
- Piso de privacidad: wh-api oculta el detalle de celdas con pocos comentarios o menciones
  (`detalle_suprimido`); la interfaz lo muestra como "detalle oculto" en vez de números.
