# Bóveda DAI

App independiente de la Dirección de Análisis Institucional (DAI) de la UCN que aloja el
**Termómetro Institucional** (módulo *Percepción*), antes parte de la Torre de Control
DAI · UCN. Se separó por **sensibilidad de los datos**: la base contiene comentarios
reales de la comunidad en redes sociales, así que el acceso es **solo por listas en la base de datos** y
falla cerrado.

- **Backend**: FastAPI + SQLAlchemy 2 (`backend/`, puerto `8012`).
- **Frontend**: Next.js 16 / React 19 / Tailwind 3 (`frontend/`, puerto `3001`). ECharts por CDN.
- **Datos**: la base de Percepción (SQLite local o PostgreSQL). Las tablas espejo las
  escribe un worker externo; la Bóveda las lee.

Puertos distintos a los de la Torre (`8011`/`8001`), así que ambas corren a la vez.

## Acceso

Login con Google (token de identidad verificado en el servidor contra `GOOGLE_CLIENT_ID`)
y una sesión propia firmada con HMAC (`APP_SESSION_SECRET`, TTL `APP_SESSION_TTL_SECONDS`).

**Quién entra se decide en PostgreSQL** (esquema `boveda`, variable `BOVEDA_DATABASE_URL`), no en
variables de entorno. Las antiguas `BOVEDA_ALLOWED_EMAILS` y `BOVEDA_TEAM_EMAILS` **ya no existen** y no hay
fallback: si siguen en tu `.env`, se ignoran.

| Quién | Qué puede |
|---|---|
| `lector` (por módulo) | Leer ese módulo |
| `equipo` (por módulo) | Leer y **escribir** en ese módulo (en Percepción: eventos, regenerar el resumen) |
| Administrador (global) | Abrir **todos** los módulos activos con todos los permisos. Es el **único** rol que entra a la Curación (`/percepcion/curacion/*`), que devuelve texto crudo de comentarios |

- Tablas: `boveda.modulos` (catálogo; `activo=false` no da acceso a nadie, ni a administradores),
  `boveda.accesos_modulo` (correo + rol por módulo), `boveda.administradores` (lista global) y
  `boveda.auditoria_texto` (auditoría). Se crean con las migraciones de [`backend/sql/`](backend/sql/):
  `001_boveda_access.sql` y `002_boveda_admin_audit.sql` (idempotentes; aplícalas en ese orden con `psql -f`).
- **Sin filas = nadie entra.** Si la base no responde, también se niega (nunca se permite por error).
  Una cuenta puede iniciar sesión solo si es administradora o tiene acceso a al menos un módulo activo; si no, 403,
  aunque sea `*.ucn.cl`. Única excepción: `GET /auth/dev-login`, que existe solo con `APP_ENV=dev`.
- El rol se vuelve a calcular en cada request desde la base (no viaja en el token): quitar una fila revoca
  el acceso en la siguiente petición.
- Todo `POST/PUT/DELETE` bajo `/percepcion` exige rol equipo o administrador (esto cierra una brecha de la
  Torre, donde cualquier sesión `*.ucn.cl` podía escribir). `GET /percepcion/resumen-semanal?forzar=true`
  también, porque vuelve a pagar al modelo.
- **Auditoría:** cada vez que un administrador recibe texto crudo de comentarios (`/curacion/comentarios`,
  `/curacion/scoring`) se guarda quién, qué comentarios, qué endpoint y cuándo. Si no se puede registrar, la
  petición falla y no se entrega el texto.
- **Anonimización de la API:** el texto de los comentarios y los captions de las publicaciones se guardan tal cual, pero ninguna respuesta de `/percepcion` los entrega fuera de la Curación (solo administradores). Las demás vistas muestran fichas de etiquetas (tema, sentimiento, emoción, cuenta, fecha, likes) y pueden derivar agregados del texto (nube de palabras, términos, impacto de palabras) sin mostrarlo. `backend/tests/test_anonimizacion_api.py` recorre todos los GET del módulo y falla si alguno devuelve texto crudo.
- `GET /auth/me` (y la respuesta del login) devuelve `is_admin` y `modulos: [{id, nombre, rol}]`.
- Con `APP_ENV` distinto de `dev` la app **no arranca** si `APP_SESSION_SECRET` es el valor por defecto o está
  vacío, ni si `BOVEDA_DATABASE_URL` está vacía. En dev con la URL vacía todos son rechazados (el dev-login emite
  una sesión, pero sin módulos).
- Requiere el driver `psycopg` (`psycopg[binary]`, ya fijado en `backend/requirements.txt`).

### Administrar las listas

No hay interfaz de administración: se usa [`scripts/boveda_accesos.py`](scripts/boveda_accesos.py), con el venv del backend.
Lee `BOVEDA_DATABASE_URL` del entorno o de `backend/.env` (y no la imprime).

```bat
backend\.venv\Scripts\python.exe scripts\boveda_accesos.py agregar-admin persona@ucn.cl
backend\.venv\Scripts\python.exe scripts\boveda_accesos.py quitar-admin persona@ucn.cl
backend\.venv\Scripts\python.exe scripts\boveda_accesos.py dar-acceso percepcion persona@ucn.cl lector
backend\.venv\Scripts\python.exe scripts\boveda_accesos.py dar-acceso percepcion persona@ucn.cl equipo
backend\.venv\Scripts\python.exe scripts\boveda_accesos.py quitar-acceso percepcion persona@ucn.cl
backend\.venv\Scripts\python.exe scripts\boveda_accesos.py listar [--modulo percepcion]
```

`dar-acceso` crea o cambia el rol (`lector` o `equipo`). `--por <nombre>` registra quién hizo el cambio
(por defecto, el usuario del sistema). Sale con código distinto de cero si el módulo no existe o el correo o el rol son inválidos.

## Correr en local

Requisitos: Python 3.11+ (probado con 3.11) y Node 22.

```bat
:: 1) backend
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
copy backend\.env.example backend\.env      :: editar: ver "Variables de entorno"

:: 2) frontend
cd frontend
npm install
copy .env.example .env.local
cd ..

:: 3) levantar todo (backend :8012 con --reload, frontend :3001)
"Boveda DAI.bat"
```

Abrir <http://127.0.0.1:3001>. Con `APP_ENV=dev` aparece el botón **Entrar en modo desarrollo**
(sin Google; el acceso de `dev@boveda.local` se lee de la base como el de cualquiera: dale acceso con el script de arriba). Sin `GOOGLE_CLIENT_ID` no hay botón de Google.

Datos reales en local: copia (no enlaces) la base del worker, `Sentiment_Analisys_University\percepcion_real.db`,
a `backend\percepcion_real.db` y apunta a ella en `backend\.env`:

```
PERCEPCION_DATABASE_URL=sqlite:///C:/ruta/absoluta/DAI-BOVEDA/backend/percepcion_real.db
```

Sin `PERCEPCION_DATABASE_URL` se usa `backend/percepcion.db`, que se crea vacía al arrancar
(el panel muestra su estado vacío).

> **Esa base tiene comentarios reales.** `*.db`, `.env`, `outputs/`, `calibracion.json`,
> `postura.json` y `tema.json` están en `.gitignore`; no los subas ni los muevas a otro repo.

## Datos en PostgreSQL

La base de Percepción puede vivir en PostgreSQL en vez de SQLite. Las tablas `percepcion_*`
van en un esquema propio, `percepcion`, de la misma base donde está el esquema `boveda`. El
esquema se elige por la URL de conexión (el `search_path` viaja en `options`), de modo que
los modelos siguen siendo un espejo de las tablas del worker y no conocen ningún esquema:

```
PERCEPCION_DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@HOST:5432/BASE?options=-csearch_path%3Dpercepcion
```

Con Postgres, el motor de lectura del dashboard abre cada conexión en modo **solo lectura**
(`SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`, el equivalente del `query_only` de
SQLite); solo la curación, los eventos y el caché de resúmenes escriben, por el motor de escritura.

### Migrar desde SQLite

`scripts/migrar_percepcion_postgres.py` copia `backend/percepcion_real.db` al esquema
`percepcion` en **una sola transacción** (si algo falla no queda nada a medias). Crea el esquema
y las tablas desde los modelos, convierte fechas, booleanos y JSON con sus tipos, valida que cada
texto entre en su columna, reinicia las secuencias y compara el conteo de filas tabla por tabla
(código de salida distinto de 0 si algo no coincide). Abre el SQLite en solo lectura y nunca
imprime la URL.

```bat
set PERCEPCION_DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@HOST:5432/BASE?options=-csearch_path%3Dpercepcion
backend\.venv\Scripts\python.exe -I scripts\migrar_percepcion_postgres.py
```

Opciones: `--origen RUTA.db`, `--destino URL` (en vez de la variable), `--esquema NOMBRE`
(def. `percepcion`) y `--reemplazar`. Sin `--reemplazar`, si alguna tabla del destino ya tiene
filas el script se niega y no toca nada.

> **El worker externo sigue escribiendo SQLite.** Para refrescar Postgres con una ingesta nueva hay
> que volver a correr la migración con `--reemplazar`, que vacía las tablas y las recarga desde el
> SQLite. **Eso sobrescribe todo lo que la Bóveda haya escrito en Postgres desde la última copia**:
> correcciones de curación, eventos, temas personalizados y resúmenes semanales. Antes de recargar
> hay que decidir si ese trabajo se respalda (por ejemplo con `pg_dump -n percepcion`) o se pierde.

Para comprobar que la API responde lo mismo sobre las dos bases (compara los JSON de una batería
de endpoints, ignora el orden de las claves y usa tolerancia en los números; solo imprime nombres
de endpoint y rutas, nunca valores):

```bat
backend\.venv\Scripts\python.exe -I scripts\verificar_paridad_percepcion.py
```

Un endpoint puede salir como `ORDEN`: mismo contenido, pero distinto orden entre filas empatadas
(el SQL no garantiza ese orden en ningún motor). Es informativo; solo `DIFF` o `ERROR` fallan.

## Variables de entorno

Detalle comentado en [`backend/.env.example`](backend/.env.example) y [`frontend/.env.example`](frontend/.env.example).

| Backend | Para qué |
|---|---|
| `APP_ENV` | `dev` habilita dev-login. Cualquier otro valor, o vacía, = producción (fail closed). En local hay que fijar `APP_ENV=dev` |
| `APP_SESSION_SECRET` | Firma de sesiones. Obligatorio y no-default fuera de dev |
| `APP_SESSION_TTL_SECONDS` | Duración de la sesión (def. 28800) |
| `GOOGLE_CLIENT_ID` | Cliente OAuth del botón de Google y *audience* del token |
| `BOVEDA_DATABASE_URL` | URL de SQLAlchemy de la base con el esquema `boveda` (`postgresql+psycopg://usuario:clave@host:5432/base`). Obligatoria fuera de dev; vacía = nadie entra |
| `PERCEPCION_DATABASE_URL` | Base de Percepción (SQLite o `postgresql+psycopg://…?options=-csearch_path%3Dpercepcion`, ver «Datos en PostgreSQL»). Vacío → `OPERATIONAL_DATABASE_URL` → `backend/percepcion.db` |
| `TASKS_TRIGGER_TOKEN` | Secreto del disparador `POST /tasks/run/percepcion-resumen` (vacío = deshabilitado) |
| `ANTHROPIC_API_KEY` | Resumen semanal por LLM (sin clave degrada solo) |
| `BACKEND_CORS_ORIGINS` | Orígenes CORS (def. `localhost:3001`) |
| `PERCEPCION_RESUMEN_MODELO`, `PERCEPCION_UNIDAD_DETECCION_SEMANAS`, `PERCEPCION_CREDITO_NO_ATRIBUIBLE`, `PERCEPCION_NEU_FEDERACION_ADVERSO` | Perillas metodológicas del módulo (cambian el nivel del índice) |

| Frontend | Para qué |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | URL del backend (def. `http://127.0.0.1:8012`; se hornea en el build) |
| `NEXT_PUBLIC_PERCEPCION_FEEDBACK_URL` | URL del Google Form de retroalimentación. Si está vacía, el botón no se muestra (la Bóveda no tiene módulo de Formularios) |

## Verificación

```bat
backend\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend && npx tsc --noEmit && npm run build
```

`backend/tests/conftest.py` fuerza una base temporal: la suite no toca la base del `.env`.
`test_auth_gates.py` cubre las compuertas de acceso con un repositorio en memoria. `test_accesos_postgres.py` prueba el
adaptador contra una PostgreSQL real y se **omite** salvo que definas `BOVEDA_TEST_DATABASE_URL` (con las migraciones 001 y 002
aplicadas); corre dentro de una transacción que se revierte, así que no deja nada en el esquema `boveda`. Las pruebas contra PostgreSQL del módulo (`test_percepcion_postgres.py`, `test_migrar_percepcion_postgres.py`) también se **omiten** salvo que definas `PERCEPCION_TEST_DATABASE_URL`; trabajan en esquemas descartables (`percepcion_test*`) que crean y eliminan ellas mismas, y nunca tocan el esquema real `percepcion`.

## Contrato con el worker externo

El worker (repo `Sentiment_Analisys_University`) **es el dueño** de las tablas espejo
`percepcion_cuenta`, `percepcion_hecho_diario`, `percepcion_publicacion`,
`percepcion_comentario` y `percepcion_score`: las escribe en la misma base que lee la Bóveda
(`PERCEPCION_DATABASE_URL`). La Bóveda nunca altera su esquema; solo crea las tablas propias
(`percepcion_correccion`, `percepcion_tema_custom`, `percepcion_evento`,
`percepcion_resumen_semanal`) y, en una base local nueva, las espejo que falten.
Forma de las filas y reglas de escritura: [`docs/PERCEPCION_CONTRATO_WORKER.md`](docs/PERCEPCION_CONTRATO_WORKER.md).

**Cambio para el worker:** al terminar una ingesta debe llamar al disparador de la **Bóveda**,
no al de la Torre:

```
POST  <URL de la Bóveda>/tasks/run/percepcion-resumen?semanas=1
Header  X-Tasks-Token: <TASKS_TRIGGER_TOKEN de la Bóveda>
```

Genera el resumen semanal solo si cambió la huella de los datos (llamarlo dos veces seguidas no
cuesta nada). Responde siempre 200 con `{"status": "ok" | "skipped" | "error", …}`. La ruta
antigua `/ai-tasks/run/percepcion-resumen` sigue montada, así que basta cambiar el host y el token.
Los documentos de `docs/` mencionan todavía a la Torre y sus rutas: léelos como historia del módulo.

## Estructura

```
backend/
  app/            main, config, database, schemas, routers/{percepcion,auth,tasks}, services/{auth,costos,accesos/,percepcion/}, data/
  sql/            migraciones del esquema `boveda` (accesos, administradores, auditoría)
  tests/          suite del módulo + test_auth_gates.py
  requirements.txt, requirements-dev.txt, pytest.ini, .env.example
frontend/
  src/app/        layout, page (sesión), globals.css (tokens --portal-*)
  src/components/ LoginScreen, BovedaShell, Percepcion*.tsx, EChartsChart
  src/lib/        session.ts (auth), percepcion.ts (cliente del módulo)
scripts/          mantenimiento del módulo (importar, exportar, evaluar, reparar…) y boveda_accesos.py (listas de acceso); corren con backend\.venv
docs/             handoff, contrato con el worker, informes, notas/
.claude/          launch.json (boveda-backend, boveda-frontend) y agents/boveda-termometro.md
Boveda DAI.bat    lanzador local (CRLF)
```

## Lo que NO se trajo de la Torre

- `costos.py` es una versión mínima: `registrar_uso_llm` solo registra en el log (no hay tabla `llm_usage`).
- `PercepcionSintesis.tsx` (huérfano en la Torre) y todo lo que no sea el módulo.
- El botón interno hacia *Formularios*: la prop `onIrAFormulario` es opcional y la Bóveda no la pasa.
