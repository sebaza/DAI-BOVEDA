# Bóveda DAI

App independiente de la Dirección de Análisis Institucional (DAI) de la UCN que aloja el
**Termómetro Institucional** (módulo *Percepción*), antes parte de la Torre de Control
DAI · UCN. Se separó por **sensibilidad de los datos**: la base contiene comentarios
reales de la comunidad en redes sociales, así que el acceso es **solo por allowlist** y
falla cerrado.

- **Backend**: FastAPI + SQLAlchemy 2 (`backend/`, puerto `8012`).
- **Frontend**: Next.js 16 / React 19 / Tailwind 3 (`frontend/`, puerto `3001`). ECharts por CDN.
- **Datos**: la base de Percepción (SQLite local o PostgreSQL). Las tablas espejo las
  escribe un worker externo; la Bóveda las lee.

Puertos distintos a los de la Torre (`8011`/`8001`), así que ambas corren a la vez.

## Acceso

Login con Google (token de identidad verificado en el servidor contra `GOOGLE_CLIENT_ID`)
y una sesión propia firmada con HMAC (`APP_SESSION_SECRET`, TTL `APP_SESSION_TTL_SECONDS`).

| Variable | Permiso |
|---|---|
| `BOVEDA_ALLOWED_EMAILS` | Pueden **leer** `/percepcion` |
| `BOVEDA_TEAM_EMAILS` | Equipo DAI: pueden leer y **escribir** (eventos, curación, regenerar el resumen) |

- Cualquier cuenta que no esté en una de las dos listas recibe 403, aunque sea `*.ucn.cl`.
- **Listas vacías = nadie entra.** Única excepción: `GET /auth/dev-login`, que existe solo con `APP_ENV=dev`.
- El rol se vuelve a calcular en cada request desde las listas (no viaja en el token): sacar
  un correo de la lista revoca su acceso al reiniciar el servidor.
- Todo `POST/PUT/DELETE` bajo `/percepcion` exige rol equipo (esto cierra una brecha de la
  Torre, donde cualquier sesión `*.ucn.cl` podía escribir). `GET /percepcion/resumen-semanal?forzar=true`
  también, porque vuelve a pagar al modelo.
- Con `APP_ENV` distinto de `dev` la app **no arranca** si `APP_SESSION_SECRET` es el valor por defecto o está vacío.

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
(sesión de equipo, sin Google). Sin `GOOGLE_CLIENT_ID` no hay botón de Google.

Datos reales en local: copia (no enlaces) la base del worker, `Sentiment_Analisys_University\percepcion_real.db`,
a `backend\percepcion_real.db` y apunta a ella en `backend\.env`:

```
PERCEPCION_DATABASE_URL=sqlite:///C:/ruta/absoluta/DAI-BOVEDA/backend/percepcion_real.db
```

Sin `PERCEPCION_DATABASE_URL` se usa `backend/percepcion.db`, que se crea vacía al arrancar
(el panel muestra su estado vacío).

> **Esa base tiene comentarios reales.** `*.db`, `.env`, `outputs/`, `calibracion.json`,
> `postura.json` y `tema.json` están en `.gitignore`; no los subas ni los muevas a otro repo.

## Variables de entorno

Detalle comentado en [`backend/.env.example`](backend/.env.example) y [`frontend/.env.example`](frontend/.env.example).

| Backend | Para qué |
|---|---|
| `APP_ENV` | `dev` habilita dev-login. Cualquier otro valor = producción (fail closed) |
| `APP_SESSION_SECRET` | Firma de sesiones. Obligatorio y no-default fuera de dev |
| `APP_SESSION_TTL_SECONDS` | Duración de la sesión (def. 28800) |
| `GOOGLE_CLIENT_ID` | Cliente OAuth del botón de Google y *audience* del token |
| `BOVEDA_ALLOWED_EMAILS` / `BOVEDA_TEAM_EMAILS` | Allowlists (ver arriba) |
| `PERCEPCION_DATABASE_URL` | Base de Percepción (SQLite o `postgresql+psycopg2://…`). Vacío → `OPERATIONAL_DATABASE_URL` → `backend/percepcion.db` |
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
`test_auth_gates.py` cubre las compuertas de acceso.

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
  app/            main, config, database, schemas, routers/{percepcion,auth,tasks}, services/{auth,costos,percepcion/}, data/
  tests/          suite del módulo + test_auth_gates.py
  requirements.txt, requirements-dev.txt, pytest.ini, .env.example
frontend/
  src/app/        layout, page (sesión), globals.css (tokens --portal-*)
  src/components/ LoginScreen, BovedaShell, Percepcion*.tsx, EChartsChart
  src/lib/        session.ts (auth), percepcion.ts (cliente del módulo)
scripts/          mantenimiento del módulo (importar, exportar, evaluar, reparar…); corren con backend\.venv
docs/             handoff, contrato con el worker, informes, notas/
.claude/          launch.json (boveda-backend, boveda-frontend) y agents/boveda-termometro.md
Boveda DAI.bat    lanzador local (CRLF)
```

## Lo que NO se trajo de la Torre

- `costos.py` es una versión mínima: `registrar_uso_llm` solo registra en el log (no hay tabla `llm_usage`).
- `PercepcionSintesis.tsx` (huérfano en la Torre) y todo lo que no sea el módulo.
- El botón interno hacia *Formularios*: la prop `onIrAFormulario` es opcional y la Bóveda no la pasa.
