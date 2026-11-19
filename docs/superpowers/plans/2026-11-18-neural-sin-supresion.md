# DAI Neural without the under-10 rule — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the n < 10 suppression rule from the whole DAI Neural module, gate the module behind a recorded acceptance checkbox, and show small groups (counts and model figures) with their n and a «pocos casos» mark instead of hiding them.

**Architecture:** The protection moves from hiding cells to an explicit, server-enforced acceptance stored in the access database (`boveda` schema).
- Redes stops suppressing when it builds marts and artefacts.
- Per-group model metrics are rebuilt for every group from the saved predictions and snapshots, with no retraining.
- The backend stops re-suppressing and blocks every `/neural/*` route until the current acceptance version is recorded.
- The frontend shows a gate panel first, then the data with n beside each percentage.

**Tech Stack:** Python 3 (Redes: pandas, scikit-learn, CatBoost, PyTorch; pytest), PostgreSQL (local dev), FastAPI + Pydantic (backend; pytest), Next.js + TypeScript + ECharts (frontend; `tsc --noEmit`).

**Spec:** `docs/superpowers/specs/2026-11-18-neural-sin-supresion-design.md`

## Global Constraints

**Privacy and Gate 4**
- No names, RUT, person identifiers, or per-student rows or lists in any artefact, mart table, API response or view.
- No teacher ranking. Never extract `nombre_estud`, `nombre_prof` or `nombre_banner`. Never expose `docente_key`, NRC or section.
- Aggregates of any size are allowed. This includes model figures for groups under 10: the user's decision of 18-11-2026 lifts Gate 4 for aggregate figures in this module.

**Model data**
- Never retrain. Kept models are only refit through `evaluation/modelos_conservados.py` `verificar` (tolerance max|Δp| ≤ 1e-4).
- `Redes/artefactos/preds/*` must stay byte-identical. Checksum baseline: `.superpowers/sdd/2026-11-18-lo-que-paso-temas-y-lo-que-viene/artefactos-before.sha256`.
- Keep the model-fitting thresholds (`models/baseline.py` MIN_N, `models/t3_supervivencia.py` and `models/t6_modelos.py` MIN_N_PROGRAMA, `models/data.py` and `models/t2_data.py` min_count, `models/t2_grafo.py` MIN_COOC, `pipelines/snapshots/rules_variables.py` MIN_PARES_RANKING, `pipelines/snapshots/rules_t6.py` viability). They change fitting, not display.
- `sexo` is used for fairness only. `cohorte_anio` is never a T3–T6 feature. Point-in-time cut 202610, as today.

**Migrations and environment**
- Redes migrations go in `Redes/sql/core/` and are applied with `python -m pipelines.migrate`. Never edit an applied one. Every new Redes migration is added to `EXTRA_DDL` in `backend/tests/test_neural_api.py`.
- `backend/sql/*.sql` are idempotent and applied in order to the local dev database (schema `boveda`).
- Credentials go inline per command only: `DEV_HOST=localhost DEV_PORT=5432 DEV_DB=postgres DEV_USER=postgres DEV_PASSWORD=1234`. Never read or write `.env`. Never print an HMAC key.

**Copy and UI**
- User-facing copy is neutral Spanish and centralized in `frontend/src/lib/neuralLenguaSimple.ts`.
- No internal codes (P58, D122…) reach readers. The exception is T1–T6 (spec item 7): codes may be shown to readers, always next to their Spanish name (Task 10).
- Dark theme. No horizontal page overflow at 375 px.

**Acceptance gate**
- Acceptance text (Spanish, served by the backend), version `"2026-11-18"`: «Declaro que soy una persona de confianza de la Dirección de Análisis Institucional (DAI), que conozco la Ley 19.628 sobre protección de la vida privada y la Ley 21.719 sobre protección de datos personales, y que usaré esta información solo para fines internos de la UCN, sin difundirla ni intentar identificar a personas.»
- Error contract: HTTP 403 with `{"detail": {"codigo": "aceptacion_requerida", "version": "<current>"}}`.
- Keep the badge «Solo lectura». Replace «Grupos con menos de 10 personas ocultos» and «Sin predicciones individuales» with «Sin nombres ni listas de estudiantes».
- «pocos casos» mark: any group with n < 10 (constant `POCOS_CASOS = 10` in one place per side). The value is shown with a lighter colour and the label «pocos casos».

**Process**
- No commits (standing user rule). Preserve each file's line endings (most are CRLF).

## Review Focus

1. **A route that skips the gate.** Every `/neural/*` route — including `/calidad`, `/programas` and any route added later — must answer 403 `aceptacion_requerida` until the current version is accepted. An acceptance of an older version must not count. Owner: Task 1 test `test_every_neural_route_requires_current_acceptance` (iterates `app.routes`).
2. **The access database fails while recording or checking an acceptance.** The gate must fail closed (503 or 403), never grant. Owner: Task 1 test `test_gate_fails_closed_when_access_store_errors`.
3. **Groups with n = 1–9, zero events, or a single class.**
   - Metrics must be `None` ("no calculable"), never NaN in JSON and never a crash.
   - Percentages with n = 0 must not divide by zero.
   - Owners: Task 5 `test_metrics_are_none_without_events_or_single_class`; Task 4 `test_zero_n_group_has_null_pct`.
4. **A stale mart or artefact still carries the old suppressed shape** (null cells, «otros» rows). The API and UI must still render without crashing. Owner: Task 6 `test_old_suppressed_document_still_serves`.
5. **The «pocos casos» mark is missing in one place** (chart vs table, UCN vs faculty, 375 px). Owner: Task 7 browser check, item list in its brief.

---

### Task 1: Backend — acceptance storage, endpoints and gate

**Files:**
- Create:
  - `backend/sql/006_neural_aceptacion.sql`
  - `backend/app/services/neural/aceptacion.py`
- Modify:
  - `backend/app/services/accesos/puerto.py`, `postgres.py`, `memoria.py`
  - `backend/tests/contrato_accesos.py`
  - `backend/app/routers/neural.py`
  - `frontend/src/lib/neural.ts` (error mapping only)
- Test:
  - `backend/tests/test_neural_aceptacion.py`
  - the access contract (`test_accesos_memoria.py`, `test_accesos_postgres.py`)

**Interfaces:**
- Produces:
  - Table `boveda.aceptaciones_modulo(modulo_id text FK boveda.modulos, email text, version_texto text, aceptado_en timestamptz default now(), PRIMARY KEY (modulo_id, email, version_texto))`.
  - `AccessRepository.registrar_aceptacion(modulo_id: str, email: str, version: str) -> None` (idempotent).
  - `AccessRepository.acepto(modulo_id: str, email: str, version: str) -> bool` (fail closed: raises on store error).
  - `aceptacion.VERSION: str = "2026-11-18"`, `aceptacion.TEXTO: str` (exact Global Constraints text).
  - Dependency `require_aceptacion` → 403 `{"codigo": "aceptacion_requerida", "version": VERSION}`.
  - Routes:
    - `GET /neural/aceptacion` → `{"version": str, "texto": str, "aceptada": bool}`.
    - `POST /neural/aceptacion` with body `{"version": str}` → 204. Returns 409 if the version is not current.
    - Both require only `require_module("neural")`.
    - All other neural routes add `require_aceptacion` at router level (split into two routers).
  - `frontend/src/lib/neural.ts`:
    - `errorDeRespuesta` maps 403 with `codigo === "aceptacion_requerida"` to a typed error `AceptacionRequerida`.
    - `neuralApi.aceptacion(signal)` and `neuralApi.aceptar(version)`.

- [ ] **Step 1: Write the failing tests:**
  - `test_get_acceptance_returns_text_version_and_false_before_accepting`
  - `test_post_acceptance_records_and_unlocks_routes`
  - `test_post_with_old_version_returns_409_and_records_nothing`
  - `test_every_neural_route_requires_current_acceptance`: iterate the neural router's routes except `/neural/aceptacion`; each answers 403 with `detail.codigo == "aceptacion_requerida"`.
  - `test_older_version_acceptance_does_not_unlock`
  - `test_gate_fails_closed_when_access_store_errors`
  - Add contract cases `registrar_aceptacion` / `acepto` to `ContratoAccesos`, covering idempotency and per-version.
- [ ] **Step 2: Run** `cd backend && DEV_HOST=localhost DEV_PORT=5432 DEV_DB=postgres DEV_USER=postgres DEV_PASSWORD=1234 .venv/Scripts/python.exe -m pytest -q tests/test_neural_aceptacion.py tests/test_accesos_memoria.py`. Expected: FAIL (missing module/routes).
- [ ] **Step 3: Implement** the migration, repository methods (memoria + postgres), `aceptacion.py`, the router split and the frontend error mapping. Apply `006` to the local dev database (inline `DEV_*`, via `psql -f` or a short psycopg call) and confirm `boveda.aceptaciones_modulo` exists.
- [ ] **Step 4: Run** the Step 2 command, then the full backend suite `.venv/Scripts/python.exe -m pytest -q`. Expected: all pass. Existing neural API tests must accept the gate via a fixture that records the acceptance, not by disabling it. Then `cd frontend && npx tsc --noEmit`, which must be clean.

### Task 2: Frontend — acceptance panel

**Files:**
- Create: `frontend/src/components/NeuralAceptacion.tsx`
- Modify:
  - `frontend/src/components/NeuralPanel.tsx`
  - `frontend/src/lib/neuralLenguaSimple.ts` (`ACEPTACION_TEXTOS`)

**Interfaces:**
- Consumes:
  - `neuralApi.aceptacion`, `neuralApi.aceptar`, `AceptacionRequerida` (Task 1).
- Produces:
  - `NeuralPanel` renders `NeuralAceptacion` at the top of the section.
  - No tab content mounts or fetches until `aceptada === true`.
  - If any later call raises `AceptacionRequerida` (version changed), the panel returns to the gate.

- [ ] **Step 1: Implement the gate panel:**
  - Title «Antes de ver los datos».
  - The server's `texto` shown verbatim.
  - A checkbox with label «Confirmo lo anterior».
  - A button «Aceptar y continuar», disabled until checked.
  - On success, tabs mount.
  - Show a load error with a retry.
  - The badges follow the Global Constraints.
- [ ] **Step 2: Run** `cd frontend && npx tsc --noEmit` → clean.
- [ ] **Step 3: Browser check** (controller):
  - The gate shows on first visit.
  - No `/neural/*` data request is sent before accepting (network panel).
  - Accept → tabs load; reload → no gate.
  - 375 px: no overflow.
  - Console clean.

### Task 3: Redes — marts without suppression (migration 033)

**Files:**
- Create: `Redes/sql/core/033_sin_supresion.sql`
- Modify:
  - `Redes/pipelines/marts/sql.py`, `build.py`, `rules.py`, `__main__.py`
  - `backend/tests/test_neural_api.py` (`EXTRA_DDL` += 033)
- Test:
  - `Redes/tests/unit/test_marts_rules.py`
  - `Redes/tests/integration/test_marts.py`
  - `Redes/tests/unit/test_marts_ddl.py`

**Interfaces:**
- Produces:
  - 033 drops these CHECKs:
    - `n >= 10` on `neural_mart.resumen_tarea_calibracion`.
    - `n >= 10` and the events CHECK (023 and its 028 replacement) on `neural_mart.resumen_tarea_grupo`.
  - 033 drops these columns:
    - `suprimido` and `suprimido_promedio` on `cohorte_semestre`, `programa_semestre`, `cohorte_resultado` and `postulante_contexto`.
    - `n_min` on `mart_construccion`.
    - `grupos_suprimidos`, `n_min` and `eventos_min` on `resumen_tarea_grupo_resumen`.
  - Look up the real constraint names with `\d` before dropping (use `DROP CONSTRAINT IF EXISTS`).
  - Mart statistics are computed for every group size. `--n-min` is removed.

- [ ] **Step 1: Write failing tests:**
  - Replace `test_suppression_threshold_is_ten` with `test_marts_have_no_size_threshold` (no `N_MIN` attribute, no `nmin` SQL param).
  - Replace `test_suppression_below_ten_hides_statistics_but_keeps_counts` with `test_groups_below_ten_publish_statistics` (a 3-person cohort gets its promedio and percentiles).
  - Add `test_migration_033_drops_size_checks` (insert a `resumen_tarea_grupo` row with n = 3, eventos = 1 succeeds).
- [ ] **Step 2: Run** `cd Redes && DEV_...=... .venv-ml/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/unit/test_marts_rules.py tests/unit/test_marts_ddl.py tests/integration/test_marts.py` → FAIL.
- [ ] **Step 3: Implement**, then run `python -m pipelines.migrate` and `python -m pipelines.marts` (inline `DEV_*`).
- [ ] **Step 4: Run** the Step 2 command → PASS. Then run the full Redes suite and record pre-existing failures caused by later tasks' code (expected: tests of suppression in vistas/resumen still assert the old rule — list them; they are owned by Tasks 4–5).

### Task 4: Redes — «Lo que pasó» / «Lo que viene» artefacts without suppression

**Files:**
- Delete:
  - `Redes/evaluation/complemento.py`
  - `Redes/tests/unit/test_complemento.py`
  - `Redes/tests/fixtures/suprimir_vector.json`
- Modify:
  - `Redes/evaluation/suprimir.py`: delete it if no caller remains; otherwise keep only non-size helpers.
  - `vista_historica.py`, `vista_proyeccion.py`, `vista_permanencia.py`, `vista_egreso.py`, `vista_ramos.py`
  - `Redes/pipelines/marts/vista_historica.py`, `vista_proyeccion.py` (META without `n_min`)
- Test:
  - `test_vista_historica.py`, `test_vista_proyeccion.py`, `test_vista_permanencia.py`, `test_vista_egreso.py`, `test_vista_ramos.py`, `test_suprimir.py`

**Interfaces:**
- Produces:
  - Every block and row is published for every filter with its exact counts.
  - Size-based «otros» rows and «otros programas» are removed; class-based groupings such as `otros_cambio` stay.
  - Every row that carries a percentage also carries its `n`.
  - Projection blocks keep `lo`/`hi` and are computed for every group size (`_por_hito` with no `N_MIN`).
  - Umbral categories are always all present.
  - Rankings (`_listable`) list every course or department with ≥ 1 attempt, ordered as today, capped only by the existing top-N length.

- [ ] **Step 1: Write failing tests:**
  - `test_small_faculty_block_is_published_with_exact_counts`: a 3-person faculty shows its counts.
  - `test_no_size_based_otros_row_anywhere`
  - `test_zero_n_group_has_null_pct`
  - `test_projection_published_for_group_of_one` (`esperados` = the person's probability, `lo`/`hi` present).
  - `test_umbral_has_all_four_categories_for_small_faculty`
  - Update or delete each old test that asserts suppression (list in the report which and why).
- [ ] **Step 2: Run** the five `test_vista_*` files → FAIL.
- [ ] **Step 3: Implement.** Then regenerate (inline `DEV_*`, from `Redes`) with `python -m evaluation.vista_historica`, `python -m evaluation.vista_proyeccion` (cache keeps it fast) and `python tools/exportar_resumen_modelos.py`.
- [ ] **Step 4: Run** the five test files → PASS. Then grep `Redes/artefactos/vista_historica.json` and `vista_proyeccion.json` for `"otros"`: 0 size-based rows. Then `sha256sum -c` on preds: unchanged.

### Task 5: Redes — model metrics for every group, rebuilt from saved predictions

**Files:**
- Create:
  - `Redes/evaluation/grupos_todos.py` → `Redes/artefactos/grupos_todos.json`
  - `Redes/tests/unit/test_grupos_todos.py`
- Modify:
  - `Redes/pipelines/marts/resumen_tareas.py` (drop `_publicable`, `N_MIN`, `N_MODELO`, `grupos_suprimidos`; calibration keeps every decile; group rows come from `grupos_todos.json`)
  - `Redes/evaluation/grupos_facultad.py` (drop `N_MIN_T3`, `N_METRICAS_GRUPO`, `EVENTOS_MIN`)
  - `Redes/tools/exportar_resumen_modelos.py` (read `grupos_todos.json`)
  - `Redes/tests/unit/test_resumen_tareas.py`, `test_grupos_facultad.py`

**Interfaces:**
- Consumes:
  - `artefactos/preds/*.npz` (read-only)
  - snapshots `neural_mart.snapshot_t1|t2|t3|t45|t6` for labels, group columns and `persona_key`
  - `evaluation/modelos_conservados.py` (`cargar_o_ajustar`, `verificar`)
- Produces:
  - `grupos_todos.json` with, per task, cut and kept model, one row per group (program, faculty, sex, admission route, school type — the same dimensions the current `resultados_t*.json` group tables use), each holding:
    - `n`, `eventos`, `tasa`, `esperado`
    - `ap`, `ap_lo`, `ap_hi`, `auc`, `auc_lo`, `auc_hi`: bootstrap by `persona_key`, 1000 resamples, seed 0. These are `None` when the group has 0 events or 0 non-events.
    - `pocos_casos: bool` (n < 10).
  - T1-with-course-load: predictions are regenerated in memory from `t1_k1_cb_ben_pit` via `cargar_o_ajustar` + `verificar`; nothing is written under `preds/`.

- [ ] **Step 1: Write failing tests:**
  - `test_every_group_is_listed_including_n_below_ten`
  - `test_metrics_are_none_without_events_or_single_class`
  - `test_bootstrap_ci_contains_point_estimate_and_is_seeded`
  - `test_group_metrics_match_existing_tables_for_reportable_groups`: for groups present in today's `resultados_t*.json`, `ap`/`auc` agree within 1e-6.
  - `test_resumen_tareas_publishes_groups_of_any_size` (replaces `test_no_group_row_below_ten_people_or_ten_events_exists_anywhere`).
  - `test_calibration_keeps_small_deciles`
- [ ] **Step 2: Run** `test_grupos_todos.py`, `test_resumen_tareas.py` and `test_grupos_facultad.py` → FAIL.
- [ ] **Step 3: Implement.** Then run `python -m evaluation.grupos_todos`, `python -m evaluation.grupos_facultad` and `python tools/exportar_resumen_modelos.py`.
- [ ] **Step 4: Run** the Step 2 tests → PASS. Then run the full Redes suite → all pass. Confirm `sha256sum -c` on preds is unchanged.

### Task 6: Backend — remove the suppression layer

**Files:**
- Delete:
  - `backend/app/services/neural/complemento.py`
  - `backend/tests/test_neural_complemento.py`
- Modify:
  - `backend/app/services/neural/rules.py`: delete size rules; keep pure reshaping such as `depurar_senales`/`depurar_esperar` field whitelists.
  - `repository.py`: no `n_min`, no `n >= 10` SQL filters.
  - `schemas.py`: drop `suprimido*`, `n_min`, `grupos_suprimidos`, `FlujosOtros`, `ProyUmbralOtros`, `confianza` T3 if it encodes publishability. Add `pocos_casos: bool` wherever a group row is returned.
  - `routers/neural.py`: docstrings and notes without «n >= 10».
- Test:
  - `backend/tests/test_neural_rules.py`
  - `backend/tests/test_neural_api.py`

**Interfaces:**
- Consumes: Task 3 and Task 5 mart shapes.
- Produces:
  - Every neural route serves the mart data as stored.
  - Group rows carry `pocos_casos`.
  - The `/calidad` response has no `n_min`.

- [ ] **Step 1: Write failing tests:**
  - `test_small_groups_are_served_with_pocos_casos_true`
  - `test_no_route_returns_size_suppressed_nulls` (seed a 3-person faculty, call each neural route after acceptance, assert counts present)
  - `test_old_suppressed_document_still_serves` (a mart document with null cells and an «otros» row → 200)
  - Delete or rewrite every test asserting suppression; list them.
- [ ] **Step 2: Run** `cd backend && DEV_...=... .venv/Scripts/python.exe -m pytest -q tests/test_neural_rules.py tests/test_neural_api.py` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full backend suite → all pass. The controller restarts the `neural-backend` preview.

### Task 7: Frontend — show everything, with n and «pocos casos»

**Files:**
- Modify:
  - `frontend/src/components/NeuralUI.tsx`: delete `AVISO_SUPRIMIDO`; add `PocosCasos` (badge) and `POCOS_CASOS = 10`.
  - `NeuralPanel.tsx` (badges)
  - `NeuralLoQuePaso.tsx`, `NeuralLoQuePasoTemas.tsx`, `NeuralLoQueViene.tsx`, `NeuralModelosGrupos.tsx`, `NeuralModelosTarea.tsx`, `NeuralFacultades.tsx`, `NeuralCohortes.tsx`, `NeuralTraslados.tsx`, `NeuralCalidad.tsx`
  - `frontend/src/lib/neural.ts` (types per Task 6), `neuralFacultades.ts`, `neuralGraficos.ts`, `neuralGraficosHistorico.ts`, `neuralGraficosProyeccion.ts`, `neuralGraficosTraslados.ts`
  - `neuralLenguaSimple.ts`: remove every «menos de 10… se oculta / no se publican / reúnen en una sola fila / Oculto» string.

**Interfaces:**
- Consumes: Task 6 API types.
- Produces:
  - Every percentage is rendered with its n: «38 % de 13».
  - Groups with n < 10 show `PocosCasos` («pocos casos») and a lighter series/cell colour.
  - Group metrics show «AP 0,41 (0,22–0,63)» or «no calculable» when `None`.
  - No hidden-group notices remain.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Run** `cd frontend && npx tsc --noEmit` → clean. Then run `grep -rniE "menos de 10|no se publican|Oculto|suprimid|n_min" frontend/src` → only hits that are not about size suppression (list them).
- [ ] **Step 3: Browser check** (controller):
  - Every tab for Toda la UCN, a large faculty and the Instituto de Ciencias Religiosas y Filosofía (smallest).
  - The «pocos casos» mark appears in tables and charts.
  - No «oculto» text remains.
  - n beside every percentage.
  - 375 px: no overflow.
  - Console clean.

### Task 8: Redes — program filter and the model behind each block

**Files:**
- Modify:
  - `Redes/evaluation/vista_historica.py`, `vista_proyeccion.py`, `vista_permanencia.py`, `vista_egreso.py`, `vista_ramos.py`, `vista_modelo.py`
  - `Redes/pipelines/marts/vista_historica.py`, `vista_proyeccion.py`
  - a new migration `Redes/sql/core/034_vista_programa.sql`, only if the mart key needs a program column (check 029/032 first; add it to `EXTRA_DDL`)
- Test: the `test_vista_*` files and `test_vista_temas_ddl.py`.

**Interfaces:**
- Produces:
  - Filters are UCN, each faculty and each program. Each program filter is keyed by its program code, with its name and its faculty.
  - Every block is computed for every program, except the model-description blocks (`senales`, `esperar_semestre`): they keep UCN values and carry `aplica_a_poblacion: false`.
  - Every block and every `por_cohorte` entry carries `modelo`. It is either `null`, for an observed-data block, or `{"tarea": "T1", "tarea_nombre": str, "modelo": str, "modelo_nombre": str, "k": int, "corte": str, "particion": str, "tipo": "esperado" | "proyeccion"}`, using the kept-model registry (`evaluation/modelos_conservados.py` `CLAVES`) and Spanish names from `pipelines/marts/resumen_tareas.py`.

- [ ] **Step 1: Write failing tests:**
  - `test_every_block_is_published_per_program`
  - `test_program_filter_carries_faculty_and_name`
  - `test_model_blocks_declare_their_model_and_observed_blocks_null`
  - `test_projection_cohorts_each_declare_task_model_and_cut`: continuidad 2026 → T1 k1 `cb_ben_pit`; 2025 → T1 k2 `lr_acad`.
  - `test_model_description_blocks_do_not_vary_by_population`
- [ ] **Step 2: Run** those tests → FAIL.
- [ ] **Step 3: Implement.** Then regenerate both artefacts and export (commands as in Task 4).
- [ ] **Step 4: Run** the Redes suite → all pass. Check that the preds are unchanged.

### Task 9: Backend — program filter and model fields

**Files:**
- Modify: `backend/app/routers/neural.py` (`/historico`, `/proyeccion`), `repository.py`, `schemas.py`.
- Test: `backend/tests/test_neural_api.py`.

**Interfaces:**
- Produces:
  - `GET /neural/historico` and `GET /neural/proyeccion` accept `facultad` or `programa`. Sending both returns 422. An unknown program returns 404.
  - The responses list the available filters as a hierarchy: faculties, each with its programs.
  - Blocks and cohorts expose `modelo` and `aplica_a_poblacion` as in Task 8.

- [ ] **Step 1: Write failing tests:**
  - `test_historico_and_proyeccion_filter_by_program`
  - `test_faculty_and_program_together_is_422`
  - `test_unknown_program_is_404`
  - `test_filters_list_programs_under_their_faculty`
  - `test_blocks_expose_model_metadata`
- [ ] **Step 2: Run** `test_neural_api.py` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full backend suite → all pass. The controller restarts the preview.

### Task 10: Frontend — cascading selector, model labels and new names

**Files:**
- Modify:
  - `frontend/src/components/NeuralLoQuePaso.tsx`, `NeuralLoQuePasoTemas.tsx`, `NeuralLoQueViene.tsx`, `NeuralPanel.tsx`
  - a new `frontend/src/components/NeuralModeloEtiqueta.tsx`
  - `frontend/src/lib/neural.ts`, `neuralLenguaSimple.ts`

**Interfaces:**
- Consumes: Task 9 API.
- Produces:
  - A cascading selector «Toda la UCN» → faculty → program. The program selector shows after a faculty is chosen and resets when the faculty changes. Both tabs share the selection.
  - `NeuralModeloEtiqueta` renders, on every model-based block (and per cohort in the detail), a label such as «T1 · No continuidad al año siguiente · CatBoost con beneficios · corte al 1.er semestre». It also has a «Cómo se calculó» toggle (population, partition, esperado or proyección).
  - Observed-data blocks show «Dato observado, sin modelo». `aplica_a_poblacion: false` blocks show a note that they describe the model and do not change with the selected population.
  - Tab and topic names follow spec item 8: «Histórico», «Proyecciones», «Permanencia», «Rendimiento en asignaturas», «Egreso y eliminación», «Fundamentos del modelo».
  - The T1–T6 codes may be shown to readers, always next to their Spanish name (spec item 7).

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Run** `cd frontend && npx tsc --noEmit` → clean.
- [ ] **Step 3: Browser check** (controller):
  - Selectors: UCN → a faculty → a large program → a 1-student program.
  - Every model block shows its label, and observed blocks show «Dato observado».
  - Tab and topic names are updated.
  - 375 px: no overflow.
  - Console clean.

### Task 11: Decision record and full verification

**Files:**
- Modify:
  - `Redes/docs/00_plan.md`: version 0.28; new row D122; mark D89, D116 and D121 «(suprimida la regla de menos de 10 por D122)»
  - `Redes/README.md` (remove `--n-min 10`, «n ≥ 100 y al menos 10 eventos»)
  - `Redes/docs/07_diseno_fase3.md` (suppression paragraph → pointer to D122)
  - spec state → «construido»

- [ ] **Step 1: Write D122** in Spanish, same style as D118–D121. It covers:
  - The user's decision (18-11-2026): remove the rule in the whole module.
  - The acceptance gate: text, version, storage and the 403 contract.
  - Model figures in small groups: the Gate 4 lift for aggregates, with the n = 1 caveat.
  - What stays: no names or lists, no teacher ranking.
  - Migration 033.
  - Group metrics rebuilt from saved predictions (bootstrap by person).
  - Model-fitting thresholds kept.
  - Benchmark docs 08–12 left as a historical record.
  - The program filter, the visible model behind each conclusion (T codes now shown to readers) and the new tab and topic names.
- [ ] **Step 2: Run everything:**
  - Full Redes suite.
  - Full backend suite (with inline `DEV_*`).
  - `npx tsc --noEmit`.
  - Hygiene: `grep -rniE "<prefijo-clave-warehouse>|DEV_PASSWORD=|nombre_estud|nombre_prof|nombre_banner|docente_key" Redes/evaluation Redes/pipelines/marts backend/app frontend/src` → only pre-existing exclusion lists and docstrings.
  - `sha256sum -c` of preds → unchanged.
- [ ] **Step 3: No commit.**
