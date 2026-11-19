# DAI Neural on GitHub Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish precomputed DAI Neural responses to the warehouse (`percepcion.neural_*`), serve them read-only from wh-api behind the Termómetro PIN token, and enable Neural in the frontend's GitHub Pages mode.

**Architecture:**
- A local exporter runs the real FastAPI Neural routes in process (`TestClient`, dependency overrides, the local Neural DB) for every published combination.
- It stores each JSON response under a canonical `(ruta, consulta)` key and replaces the warehouse rows in one transaction.
- wh-api canonicalizes the incoming request, looks up the key and returns the stored JSON.
- In Pages mode the frontend points `neural.ts` at wh-api with the PIN token.

**Tech Stack:**
- Python 3 with FastAPI, SQLAlchemy and psycopg 3; pytest (DAI-BOVEDA backend).
- Node/Express with pg and CASL; `node:test` (wh-api).
- Next.js/TypeScript (frontend, no test runner: `npm run typecheck` and `npm run build:pages`).

**Spec:** `docs/superpowers/specs/2026-11-19-neural-en-pages-design.md` (Decisions 1–9 and the 8 follow-up details). The spec places the exporter in `backend/scripts/`; this plan puts it in the repo-root `scripts/`, where the existing Percepción publication scripts live.

## Global Constraints
- **Warehouse writes:** only to `percepcion.neural_respuesta` and `percepcion.neural_publicacion`, and only from the exporter.
- **Credentials:**
  - Passed inline per command, never written to files, never printed.
  - Exporter URLs come from `--origen`/`--destino` or `NEURAL_DATABASE_URL`/`NEURAL_WH_DATABASE_URL`.
- **No per-student rows leave localhost.** Only the JSON responses of the public routes are stored.
- **Identity-key gate:** the exporter refuses to publish if any JSON key, at any depth, is in this closed list: `rut`, `dv`, `paterno`, `materno`, `nombre_estud`, `nombre_prof`, `nombre_banner`, `email`, `correo`, `telefono`, `fecha_nacimiento`, `docente_key`, `nrc`, `seccion`, `id_estudiante`, `pidm`. It also refuses any non-empty list under a key ending in `_estudiantes`.
- **Responses are unchanged:** stored responses are byte-for-byte what the local routes return. No model retraining, no pipeline or figure changes.
- **PIN token access:** it reads only `/percepcion/*` and `GET /neural/*`. Any non-GET under `/neural` returns 403. Ordinary wh-api JWT accounts get no Neural ability.
- **Errors:**
  - Unpublished combination: 404 `{"detail": "Esta combinación no está publicada en el sitio. Está disponible en la Bóveda local."}`.
  - No `neural_publicacion` row: 503.
- **Frontend:**
  - Pages-mode switches use the literal `process.env.NEXT_PUBLIC_MODO === "pages"` so webpack prunes dead branches.
  - The public-bundle grep in `.github/workflows/pages.yml` (`curacion|forzar|dev-login|accounts\.google\.com`) must still pass.
- **Copy and layout:** neutral Spanish copy; no horizontal overflow at 375 px; preserve each file's line endings.
- **Workflow:** no commits or pushes until the controller's final task gets the user's OK. Subagents run no servers, connect to no non-local database, and spawn no subagents.

## Review Focus
1. A faculty name with accents or spaces (`?facultad=Escuela%20de%20Ingenier%C3%ADa`) must find its row. Python and JS canonicalize it identically.
2. A program picked in another tab that has no transfers (e.g. any of the 90 programs not among the 69 with movement) must show its detail in Traslados, not «no publicada».
3. A PIN token trying `POST /neural/aceptacion` or `GET /empleado/...` must get 403.
4. A Pages user who reloads the tab must not be asked for the acceptance again in the same tab. A new tab, or a changed `VERSION`, asks again.
5. A response that would carry an identity key must abort the whole publication, and the warehouse must stay as before.

---

### Task 1: Shared canonical key, combination list and identity gate (Python, no DB)
**Files:**
- Create `scripts/_neural_publicacion.py`.
- Create `backend/tests/test_neural_publicacion.py`.
- Create `backend/tests/fixtures/neural_canon_casos.json`. The same file is copied verbatim into wh-api in Task 3.

**Interfaces (Produces):**
- `canonizar(url: str) -> tuple[str, str]`:
  - Splits a path plus query and percent-decodes keys and values (UTF-8).
  - Drops empty values, sorts by key (then value) and joins `k=v` with `&` without re-encoding. No query gives `""`.
  - The path keeps its decoded form without a trailing slash.
- `combinaciones(get: Callable[[str], dict]) -> list[str]`: returns the exact URLs (path plus query, built the way `frontend/src/lib/neural.ts` builds them) to publish, using `get` to read listing responses:
  - `/neural/aceptacion`, `/neural/programas`, `/neural/calidad`, `/neural/modelos/resumen`, `/neural/modelos/tareas`.
  - `/neural/historico` and `/neural/proyeccion`: no query, `?facultad=<F>` for each faculty and `?programa=<P>` for each program in that route's own UCN response hierarchy (the list its selector shows).
  - `/neural/programa/<cod>/cohortes` for each `cod` in `/neural/programas`.
  - `/neural/modelos/tarea/<t>` for each task in `/neural/modelos/tareas`.
  - `/neural/modelos/tarea/<t>/grupos?nivel=<n>&variante=<v>&corte=<k>`:
    - for every vista `(variante, corte_k)` listed in that task's detail;
    - with `n` in `programa, facultad, sexo, via, tipo_colegio`, plus `nivel_postgrado` for `t6`.
  - `/neural/modelos/malla-ejemplo?semestre_max=4`, alone and with `&cod_programa=<cod>` for each program in `/neural/programas`.
  - `/neural/traslados/resumen`, with a query for every combination of:
    - `anio_desde` in {none, `max−9`, `max−4`}, where `max = anios_disponibles.hasta` of the unfiltered response;
    - `tipo` in {none} ∪ the 6 `rules.TIPOS_TRASLADO` keys;
    - `solo_abandono` in {absent, `true`}.

    That is 42 queries.
  - `/neural/traslados/programa/<cod>` with the same 42 queries, for every `cod` in the union of `/neural/programas` and the unfiltered resumen's `balance`.
- `revisar_identidad(obj: object) -> list[str]`: returns the JSON paths of every offending key per the Global Constraints list. Empty means clean.

- [ ] **Step 1: Write the canonicalization cases** to `neural_canon_casos.json` as `[{"url": ..., "ruta": ..., "consulta": ...}]`. Include at least:
  - `/neural/historico` → `["/neural/historico", ""]`
  - `/neural/historico?facultad=Escuela%20de%20Ingenier%C3%ADa` → `["/neural/historico", "facultad=Escuela de Ingeniería"]`
  - `/neural/traslados/resumen?tipo=cambio_carrera&anio_desde=2017&solo_abandono=true` → `["/neural/traslados/resumen", "anio_desde=2017&solo_abandono=true&tipo=cambio_carrera"]`
  - `/neural/traslados/resumen?anio_desde=` → `["/neural/traslados/resumen", ""]`
  - `/neural/programa/8616/cohortes/` → `["/neural/programa/8616/cohortes", ""]`
  - `/neural/modelos/tarea/t2/grupos?variante=base&nivel=sexo&corte=2` → `["/neural/modelos/tarea/t2/grupos", "corte=2&nivel=sexo&variante=base"]`
- [ ] **Step 2: Write the failing tests:**
  - `test_canonizar_casos_compartidos`: every case in the fixture.
  - `test_combinaciones_traslados`: a fake `get` with `anios_disponibles.hasta = 2026`, 2 programs and 1 extra balance program gives 42 resumen URLs. It contains `anio_desde=2017` and `anio_desde=2022` and no `anio_hasta`, and 3×42 program URLs.
  - `test_combinaciones_grupos_t6_incluye_nivel_postgrado`.
  - `test_revisar_identidad`: `{"a": [{"rut": 1}]}` → `["a[0].rut"]`; `{"n_estudiantes": 5}` is clean; `{"lista_estudiantes": [1]}` is flagged.
- [ ] **Step 3: Run** `cd backend && .venv/Scripts/python.exe -m pytest tests/test_neural_publicacion.py -q`. Expected: FAIL, import error.
- [ ] **Step 4: Implement the three functions** in `scripts/_neural_publicacion.py`. The test imports it via `sys.path`, following the `scripts/` convention.
- [ ] **Step 5: Run the same command.** Expected: PASS. Also run `.venv/Scripts/python.exe -m pytest -q` for the full suite with no new failures. The DB-gated tests stay skipped.

### Task 2: Exporter and warehouse DDL
**Files:**
- Create `backend/sql/008_neural_publicacion_warehouse.sql`.
- Create `scripts/publicar_warehouse_neural.py`.
- Extend `backend/tests/test_neural_publicacion.py`.

**Interfaces:**
- Consumes: Task 1's `canonizar`, `combinaciones` and `revisar_identidad`.
- Produces: the tables read by wh-api in Task 3.
  - `percepcion.neural_respuesta`: `ruta text`, `consulta text`, `contenido jsonb not null`, `generado_en timestamptz not null`; `primary key (ruta, consulta)`.
  - `percepcion.neural_publicacion`: `id smallint primary key check (id = 1)`, `publicado_en timestamptz not null`, `version_exportador text not null`, `respuestas int not null`, `bytes bigint not null`.
- DDL uses `CREATE TABLE IF NOT EXISTS`, with the schema as a psql-free placeholder that the script substitutes after validating `^[a-z_][a-z0-9_]*$`.
- Grants: the script copies the ACL of `<schema>.percepcion_hecho_diario` (`aclexplode` over `pg_class.relacl`) onto both tables. It grants only `SELECT` to roles that have `SELECT` there.

Script behaviour (`publicar_warehouse_neural.py`):
- **Arguments:** `--origen` (default `NEURAL_DATABASE_URL`), `--destino` (default `NEURAL_WH_DATABASE_URL`), `--esquema` (default `percepcion`) and `--dry-run`. Exit codes: 0 ok, 1 failure, 2 usage. URLs are never printed.
- **Collection:**
  - Builds `app.main.app` with `dependency_overrides` for `aceptacion.exigir_modulo` and `aceptacion.require_aceptacion`. Each returns a fixed `AuthUser` with no personal data: email `exportador@local`.
  - Points `get_neural_conn` at `--origen`, reusing `app.services.neural.db.crear_engine`, which keeps READ ONLY.
  - Collects `GET` for every URL from `combinaciones`. Any non-200 aborts with the URL and status. The stored `/neural/aceptacion` body always has `aceptada: false`; use an in-memory access repository, as `tests/test_neural_api.py` does, so no Bóveda access table is read.
- **Checks:** runs `revisar_identidad` on every body, and aborts with the offending paths only. It also refuses if origin and destination resolve to the same host, port and database.
- **Output:** prints only the response count, total bytes, the largest route by bytes, and timing.
- **Writing (non-dry-run):** in one transaction it applies the DDL, copies grants, `DELETE`s both tables, inserts all rows (batched `executemany`), and inserts the `neural_publicacion` row with `version_exportador = "2026-11-19"`. A failure rolls back everything.

- [ ] **Step 1: Write the failing tests**, opt-in via `DEV_*` env like `test_neural_api.py`, against a throwaway schema `neural_pub_test` on the local dev DB:
  - `test_publicar_crea_tablas_y_filas`: a run with a stub collector of 3 URLs leaves 3 rows and 1 `neural_publicacion` row.
  - `test_publicar_falla_identidad_no_toca_destino`: pre-seed 1 row; a body with `nombre_estud` exits 1 and the pre-seeded row is still there.
  - `test_dry_run_no_escribe`.

  Factor the writer as `publicar(destino_url: str, esquema: str, respuestas: list[tuple[str, str, bytes]], dry_run: bool) -> int` so tests pass a stub list.
- [ ] **Step 2: Run** `cd backend && DEV_HOST=localhost DEV_PORT=5432 DEV_DB=postgres DEV_USER=postgres DEV_PASSWORD=1234 .venv/Scripts/python.exe -m pytest tests/test_neural_publicacion.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the SQL file and the script.
- [ ] **Step 4: Run Step 2's command.** Expected: PASS, with the throwaway schema dropped at teardown.
- [ ] **Step 5: Local dry run of the full collection:** `.venv/Scripts/python.exe -I ../scripts/publicar_warehouse_neural.py --dry-run --origen "<local neural URL from NEURAL_DATABASE_URL>"`. Expected: exit 0, about 4,500 responses, with count and bytes reported in the task report. Without `--destino` the dry run must still collect and check, then stop before writing.

### Task 3: wh-api read routes behind the PIN token
**Files (repo `C:/Users/sezad/Documents/GitHub/wh-api`):**
- Modify `auth/autenticar.js` (around lines 18 and 44–48) and `ability.js` (lines 18–22).
- Create `neural/canon.js`, `neural/lectura.js` and `queries/neural.js`.
- Create `test/neural.canon.test.js`, `test/neural.router.test.js` and `test/neural_canon_casos.json` (verbatim copy of Task 1's fixture).
- Modify the `package.json` `scripts.test` list and `test/percepcion.acceso.test.js` (cases at lines 185–191).

**Interfaces:**
- `canonizar(urlOriginal: string) -> {ruta: string, consulta: string}`: same rules as Task 1.
- `crearLectura(consulta, esquema)`, where `consulta(sql, values) -> rows`, as `percepcion/db.js` `crearConsulta`, returns:
  - `respuesta(ruta, consulta) -> object | null`;
  - `publicacion() -> object | null`.

  The schema comes from `esquemaDe()` (reuse `percepcion/db.js`); the tables are `neural_respuesta` and `neural_publicacion`.
- `queries/neural.js` exports `crearRouter(autorizacion)`, `router` and `path = "/neural"`, following `queries/percepcion.js`:
  - `router.use(autorizacion)`, then a CASL check `can('read', 'Neural')`, otherwise 403.
  - `GET /publicacion` returns the row as `{publicado_en, respuestas}`, or 503 `{"detail": "Los datos de DAI Neural aún no están publicados."}`.
  - `GET *`:
    - if there is no publication row, 503 (same detail);
    - otherwise it looks up `canonizar` of `req.originalUrl` cut from its `/neural` segment onward, so any proxy prefix such as `/wh-api/v0` is ignored and the key matches the stored `ruta`, which keeps the `/neural` prefix;
    - a hit sends `contenido` as JSON with `Cache-Control: no-store`;
    - a miss returns 404 with the Global Constraints detail.
  - Any other method returns 403.
- Auth:
  - Allow `decoded.tipo === 'percepcion'` on `GET`/`HEAD` paths equal to `/neural` or starting with `/neural/`, in addition to `/percepcion`.
  - Set `req.accesoPercepcion = true` there too.
  - `defineAbilityPercepcion()` adds `can('read', 'Neural')`.
  - Ordinary JWT abilities are untouched.

- [ ] **Step 1: Write the failing tests:**
  - `neural.canon.test.js`: every fixture case.
  - `neural.router.test.js`, with a fake pool in the style of `test/percepcion.router.test.js`:
    - a hit returns 200 and the stored JSON;
    - a miss returns 404 and the exact detail;
    - no publication row returns 503;
    - `nadaPermitido` returns 403;
    - `POST /neural/aceptacion` returns 403;
    - an accented faculty query hits the row stored under `facultad=Escuela de Ingeniería`.
  - `percepcion.acceso.test.js`, for a PIN token:
    - `GET /neural/historico` passes;
    - `POST /neural/aceptacion` returns 403;
    - `GET /empleado/1` still returns 403.
- [ ] **Step 2: Run** `cd C:/Users/sezad/Documents/GitHub/wh-api && npm test`. Expected: the new tests FAIL and the existing ones pass.
- [ ] **Step 3: Implement.** Add a short `@swagger` block like `queries/percepcion.js`.
- [ ] **Step 4: Run** `npm test`. Expected: all PASS.

### Task 4: Frontend Pages mode for Neural
**Files:**
- Modify `frontend/src/lib/neural.ts`, `frontend/src/components/PaginaPages.tsx`, `frontend/src/app/neural/page.tsx`, `frontend/src/components/NeuralAceptacion.tsx`, `frontend/src/components/NeuralTraslados.tsx` and `frontend/src/components/NeuralPanel.tsx`.
- Modify `frontend/src/components/Recibidor.tsx` (its comment only).

**Interfaces:**
- Consumes: Task 3's routes, including `GET /neural/publicacion` and `{publicado_en, respuestas}`.
- `neural.ts` in Pages mode, following `percepcion.ts` lines 9–35:
  - base `API_PAGES_URL`, the token from `obtenerToken()`, `credentials: "omit"`;
  - `limpiarToken()` on 401 and 403;
  - a 404 or 503 with a string `detail` shows that detail.
  - New `neuralApi.publicacion(signal)`.
  - `aceptar()` is never called in Pages.
- `PaginaPages({ modulo?: "percepcion" | "neural" })`:
  - `MODULOS_PAGES` adds `{ id: "neural", nombre: "DAI Neural", rol: "lector" }`.
  - `modulo="neural"` renders `BovedaCabecera` plus the breadcrumb plus `NeuralPanel`, mirroring the local `PaginaNeural` layout.
- `app/neural/page.tsx`: the Pages branch returns `<PaginaPages modulo="neural" />`, and `NoDisponible` is removed.
- `NeuralAceptacion` in Pages:
  - reads `GET /neural/aceptacion`;
  - «Aceptar» stores `sessionStorage["neural-aceptacion"] = <version>`, wrapped in try/catch, and calls `onAceptada`;
  - a stored value equal to the current version skips the gate;
  - it adds the line «En el sitio publicado esta aceptación no queda registrada.»
- `NeuralTraslados` in Pages:
  - The two year selects become a `Segmentado` «Período» with «Todos los años» (no `anio_desde`), «Últimos 10» (`anio_desde = hasta − 9`) and «Últimos 5» (`hasta − 4`).
  - `hasta` comes from `d.anios_disponibles.hasta`.
  - `anio_hasta` is never sent.
  - The range caption names the years shown.
- `NeuralPanel` in Pages: under the header, «Datos publicados el <dd-mm-aaaa>.» from `neuralApi.publicacion`. If that fails, the line is omitted and nothing else is blocked.

- [ ] **Step 1: Implement** the changes above. Local mode must behave exactly as before.
- [ ] **Step 2: Typecheck:** `cd frontend && npm run typecheck`. Expected: clean.
- [ ] **Step 3: Pages build and bundle check:** `cd frontend && NEXT_PUBLIC_API_BASE_URL=https://bi.ucn.cl/wh-api/v0 NEXT_PUBLIC_BASE_PATH=/DAI-BOVEDA npm run build:pages`, then `grep -rlE 'curacion|forzar|dev-login|accounts\.google\.com' out --include='*.js' --include='*.html'`. Expected: the build succeeds, the grep prints nothing, and `out/neural/index.html` (or `out/neural.html`) exists.
- [ ] **Step 4: Local build sanity:** `npm run build`. Expected: success.

### Task 5: Publish, verify, deliver (controller, with user gates)
- [ ] **Step 1:** Run the exporter dry run against local data and report the count and bytes.
- [ ] **Step 2 — USER GATE:**
  - Ask the user before the real publication: it writes to the shared warehouse.
  - Then run it with `NEURAL_WH_DATABASE_URL` built inline from the `WH_*` values the user gave.
  - Verify with a read-only query: row counts, the `neural_publicacion` row, and `SELECT` privilege for the wh-api role.
- [ ] **Step 3: Parity spot check:**
  - Compare 5 stored rows (UCN historico, one faculty proyeccion, one traslados combination, one grupos, calidad) byte-for-byte against the local backend responses.
  - Run wh-api locally against the warehouse (`npm test`, plus one `GET` with a PIN token, if the user has `PERCEPCION_PIN_HASH` configured locally).
- [ ] **Step 4 — USER GATE:** deploying wh-api to `bi.ucn.cl` is the user's or the infrastructure owner's step. Report what changed in wh-api.
- [ ] **Step 5 — USER GATE:**
  - Propose the commits as work units: DAI-BOVEDA Neural module plus this plan; wh-api routes.
  - Get the user's OK, and push only after wh-api is live.
  - Then check that the Pages workflow passes, and that `/DAI-BOVEDA/neural` loads with the PIN.
- [ ] **Step 6:** Set the spec state to «construido», and add the exporter command to the README next to the Percepción publication command.
