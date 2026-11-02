# Cómo actualizar el Termómetro (datos y código)

Guía operativa para publicar una versión nueva del Termómetro Institucional en
<https://sebaza.github.io/DAI-BOVEDA/>. Cubre dos casos que pueden darse por separado:

- **A. Datos nuevos**: el worker ingestó comentarios y hay que llevarlos hasta el sitio.
- **B. Código nuevo**: cambios en la Bóveda (frontend o backend) o en `wh-api`.

## Cómo fluyen los datos

```
worker (SQLite)  →  Bóveda local (Postgres, esquema percepcion)  →  almacén (esquema percepcion)
                    curación, cifrado, derivados, subtemas            copia seudonimizada
                                                                        ↓
                                     sitio en GitHub Pages  ←  wh-api (/percepcion/*, PIN)
```

- La **Bóveda local es la base principal**: ahí se ingesta, se cura y se calculan los derivados.
- El **almacén es una copia** que se reemplaza completa en cada publicación. Nada se edita en él.
- `wh-api` lee el almacén con `warehouse_user`, que es dueño del esquema `percepcion`.
- El sitio es estático: no guarda datos; los pide a `wh-api` con el token que entrega el PIN.

Reglas que valen siempre:

- Todos los comandos se corren en **PowerShell**, desde `C:\Users\<usuario>\Documents\GitHub\DAI-BOVEDA`,
  y las variables `$env:...` se definen **en la misma ventana** donde se corre el script.
- Ninguna URL, contraseña ni clave se escribe en archivos del repositorio (es **público**).
- `PERCEPCION_CLAVE_TEXTO` y `PERCEPCION_CLAVE_ID` viven solo en `backend/.env`. Si se pierde la
  primera, el texto cifrado es irrecuperable; si se cambia la segunda, los autores ya cargados dejan
  de coincidir con los nuevos.
- Los scripts imprimen solo conteos. Si alguno falla, revierte y no deja nada a medias.

---

## A. Publicar datos nuevos

### A1. Ingesta en el worker

El repositorio `Sentiment_Analisys_University` genera el SQLite `percepcion_real.db`. Ese proceso
está fuera de este repositorio; aquí solo se lee ese archivo (en modo solo lectura).
Si el archivo no está en la ruta por defecto, defina `PERCEPCION_WORKER_SQLITE` con su ruta.

### A2. Sincronizar el worker con la Bóveda local

```powershell
$env:PERCEPCION_ADMIN_DATABASE_URL = "postgresql+psycopg://<dueño_local>:<clave>@localhost:5432/<base_local>"
backend\.venv\Scripts\python.exe -I scripts\sincronizar_percepcion_worker.py --dry-run
backend\.venv\Scripts\python.exe -I scripts\sincronizar_percepcion_worker.py
```

Qué hace:

- Inserta solo lo nuevo (cuentas, publicaciones, comentarios, scores y eventos). No hace UPDATE,
  así que la curación existente queda intacta.
- **Cifra** el texto y los captions nuevos con las claves de `backend/.env`. Si al final aparece
  `ADVERTENCIA: ... SIN cifrar`, faltan las claves: no siga, revise `backend/.env` y corra
  `scripts/cifrar_textos_percepcion.py`.
- Reagrega los hechos diarios y reconstruye los derivados (tokens, familias, rasgos y etiquetas).
- Antes de escribir guarda un respaldo de la curación en `backend/respaldos/sync-<fecha>.json`
  (local, fuera de git).

Si el `--dry-run` informa conflictos de claves, **no corra la sincronización**: el worker cambió
datos ya cargados y hay que revisarlo antes.

### A3. Recalcular subtemas

```powershell
backend\.venv\Scripts\python.exe -I scripts\agrupar_subtemas_percepcion.py --dry-run
backend\.venv\Scripts\python.exe -I scripts\agrupar_subtemas_percepcion.py
```

Agrupa los comentarios de cada tema con un modelo de embeddings local (sin APIs externas). Los
nombres puestos a mano en Curación se conservan si el subtema nuevo se parece lo suficiente al
anterior. Necesita `backend/requirements-ml.txt` instalado.

### A4. Revisar en la Bóveda local (opcional, recomendado)

Levante la Bóveda local y revise:

- que la fecha "hasta" del rango llegue al último día ingestado;
- que la cola de Curación muestre lo nuevo;
- el **Resumen semanal**: al abrir una semana con datos nuevos se genera solo, y eso **cuesta**
  (centavos de dólar por semana). "Regenerar" fuerza otra llamada pagada aunque nada haya cambiado.
  El sitio público solo muestra los resúmenes ya generados; nunca los genera.

### A5. Publicar en el almacén

```powershell
$env:PERCEPCION_ADMIN_DATABASE_URL = "postgresql+psycopg://<dueño_local>:<clave>@localhost:5432/<base_local>"
$env:PERCEPCION_WH_DATABASE_URL    = "postgresql+psycopg://warehouse_user:<clave>@<host_almacén>:<puerto>/<base_almacén>"
backend\.venv\Scripts\python.exe -I scripts\publicar_warehouse_percepcion.py --dry-run
backend\.venv\Scripts\python.exe -I scripts\publicar_warehouse_percepcion.py --reemplazar
```

- `<base_almacén>` debe ser **la misma base** que usa `wh-api` (su `WH_DB`); si no, el sitio no verá
  los datos.
- Contraseñas con caracteres especiales van codificadas en la URL: `@`→`%40`, `:`→`%3A`,
  `/`→`%2F`, `#`→`%23`, `%`→`%25`, `?`→`%3F`.
- `--reemplazar` vacía las tablas del almacén y las vuelve a cargar en una sola transacción. Copia el
  texto cifrado tal cual y seudonimiza `autor_hash` y `external_id` de los comentarios con
  `PERCEPCION_CLAVE_ID`. Al final valida conteos, sumas, que todo el texto se descifre y las marcas
  de seudonimización; si algo no cuadra, revierte.
- No hace falta reiniciar `wh-api` ni otorgar permisos: `warehouse_user` es dueño del esquema.

### A6. Verificar en el sitio

Abra <https://sebaza.github.io/DAI-BOVEDA/> (con `Ctrl+F5`), entre con el PIN y compruebe que:

- la fecha "hasta" y el total de comentarios coinciden con la Bóveda local;
- las cuatro pestañas (Resumen, Alertas, Comparar y Conversación) cargan sin errores.

---

## B. Publicar código nuevo

### B1. Bóveda (este repositorio)

1. Trabaje en una rama, verifique localmente y lleve el cambio a `main`.
2. `git push origin main`.
3. Si el cambio toca `frontend/`, se ejecuta solo el workflow **"Publicar en GitHub Pages"**
   (`.github/workflows/pages.yml`). Siga su avance en la pestaña *Actions* del repositorio. El
   workflow:
   - corre `npm ci`, el chequeo de tipos y `npm run build:pages` con base `/DAI-BOVEDA`;
   - falla si el bundle público contiene funciones de administración (Curación, `forzar`,
     login de desarrollo, Google);
   - publica `frontend/out`.
4. Si cambió el backend de la Bóveda, reinicie la Bóveda local. El backend no se publica: solo lo
   usa la Bóveda local.

Para probar el modo público en local (sin publicar):

```powershell
$env:MSYS_NO_PATHCONV = "1"   # solo si se usa Git Bash
$env:PAGES_PERMITIR_LOCAL = "1"
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:3999"
$env:NEXT_PUBLIC_BASE_PATH = "/boveda"
npm --prefix frontend run build:pages
```

Detalles del modo público en `docs/github-pages.md`.

Variables del repositorio (*Settings → Secrets and variables → Actions → Variables*), opcionales:

| Variable | Uso |
|---|---|
| `PAGES_API_BASE_URL` | URL pública de `wh-api`. Por defecto `https://bi.ucn.cl/wh-api/v0`. |
| `PAGES_FEEDBACK_URL` | Enlace de comentarios que muestra el sitio. Sin ella no se muestra. |

### B2. `wh-api` (repositorio `cin-dai/wh-api`, privado)

1. Rama nueva, `npm test` en verde, pull request a `main` y merge.
2. Jenkins construye la imagen Docker desde `main`. Si no se dispara solo, ejecute **Build Now**
   en el job de `wh-api`.
3. Compruebe que el sitio sigue entrando con el PIN y cargando datos.

La configuración de `wh-api` está en su `.env` (versionado en ese repositorio privado). Variables
de Percepción:

| Variable | Qué es |
|---|---|
| `JWT_SECRET` | 32 caracteres o más. **Sin ella el API no arranca** (se cae todo `wh-api`). |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma. Debe incluir `https://sebaza.github.io`. |
| `PERCEPCION_PIN_HASH` | Hash del PIN del equipo. Sin él, el ingreso responde "acceso no disponible". |
| `TRUST_PROXY` | Número de proxies delante del API (hoy `1`). |
| `PERCEPCION_TOKEN_EXPIRA` | Duración del token (por defecto `8h`, máximo `24h`). |
| `PERCEPCION_TERMINOS_MIN_MENCIONES`, `PERCEPCION_SINTESIS_MIN_COMENTARIOS` | Pisos de privacidad (por defecto 5). |

### B3. Cambiar el PIN

```powershell
cd C:\Users\<usuario>\Documents\GitHub\wh-api
node scripts\hash_pin_percepcion.js
```

Hágalo en PowerShell (en Git Bash el PIN se ve al escribirlo). Pegue la línea que imprime en
`PERCEPCION_PIN_HASH='...'` del `.env` de `wh-api`, súbalo a `main` y vuelva a construir en Jenkins.
Los tokens ya entregados siguen valiendo hasta que expiran. Se recomienda una frase de 10 o más
caracteres en vez de un número corto.

---

## Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Todo da error 500 tras entrar | El almacén no tiene las tablas, o `wh-api` lee otra base | Repetir A5 y confirmar que `<base_almacén>` es el `WH_DB` de `wh-api` |
| "PIN incorrecto" con el PIN correcto | El hash no corresponde al PIN o se copió incompleto | Generar el hash de nuevo (B3) |
| "Acceso no disponible" | Falta `PERCEPCION_PIN_HASH` en `wh-api` | Agregarlo y reconstruir |
| "Demasiados intentos" | 5 fallos en 15 minutos | Esperar; revisar que `TRUST_PROXY` esté definido |
| La página no carga datos y la consola muestra CORS | El origen no está en `CORS_ORIGINS` | Agregar `https://sebaza.github.io` y reconstruir |
| El sitio muestra datos viejos | No se corrió A5 tras sincronizar | Correr A5 |
| El workflow de Pages falla en `build:pages` | URL de la API vacía, local o sin https | Revisar `PAGES_API_BASE_URL` |
| El workflow falla en "Verificar que no se publica nada de administración" | Algún componente de administración quedó fuera del pliegue `MODO_PAGES` | Revisar el cambio en `frontend/` |

## Lo que no hay que hacer

- No editar el almacén a mano: A5 lo reemplaza completo y se perdería lo editado.
- No subir `backend/.env`, `frontend/.env*` ni respaldos (`backend/respaldos/`) al repositorio.
- No rotar `PERCEPCION_CLAVE_ID` sin recargar el almacén completo.
