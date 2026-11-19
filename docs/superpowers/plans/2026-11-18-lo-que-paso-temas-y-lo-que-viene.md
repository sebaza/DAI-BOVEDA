# «Lo que pasó» por temas y «Lo que viene» Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split «Lo que pasó» into four topics with ten new aggregate blocks, and add a «Lo que viene» tab that projects current students with the kept models plus a descriptive "near the elimination threshold" count.

**Architecture:** Same pipeline as part A. Redes computes JSON documents (`artefactos/vista_historica.json`, extended; new `artefactos/vista_proyeccion.json`), the exporter loads them into `neural_mart` tables (one row per block and filter, `contenido` jsonb), FastAPI serves them read-only with server-side suppression (`rules.depurar_*`), and Next.js renders them. Kept models are rebuilt deterministically from their validated configuration and checked against the saved test predictions before any projection is published.

**Tech Stack:** Python 3 (pandas, numpy, CatBoost, scikit-learn, PyTorch), PostgreSQL dev DB, FastAPI + pydantic, Next.js + TypeScript + ECharts.

**Spec:** `docs/superpowers/specs/2026-11-18-lo-que-paso-temas-y-lo-que-viene-design.md`

**Deviation from the spec's builder notes (builder's call):** `GET /neural/historico` keeps one call and returns every block; the topic selector lives in the frontend. No `tema` parameter or column (payload is small, one fewer migration column, cache-friendly).

## Global Constraints

- Aggregates only; no cell with n < 10 (`N_MIN = 10`). In distributions with a known total, cells under 10 merge into «otros»; if «otros» is still under 10, the whole distribution of that group is hidden.
- No `docente_key`, NRC, section, `persona_key`, `episodio_id` or 64-hex string in any artefact, mart row or API response.
- Projection uses data up to the close of **202610** only; 202620 is never read.
- Every projection shows a range and its cut date; V-2 carries the 2025-regulation (Art. 46) and P75 warning.
- No retraining in the sense of new models: kept models are refit with the validated configuration, same training window and seeds, and must reproduce saved test predictions (max |Δp| ≤ 1e-4) or the run aborts.
- Kept models: T1 `cb_acad` (k=1, historical), `cb_ben_pit` (k=1, cohorts ≥ 2024), `lr_acad` (k=2); T2 `cb_c_nuevas`; T3 `dt_lr_adm` (k=0), `nn_gru` (k=2, 4); T5 `gru_adm` (k=2), `gru_agg` (k=4).
- Art. 46 thresholds (from 202520): `UMBRAL_2DA_NUEVO = 6` failures in 2nd opportunity over the career; `UMBRAL_3RA_NUEVO = 2` distinct courses failed in 3rd opportunity (`pipelines/snapshots/rules_variables.py`).
- `sexo` only for fairness; `cohorte_anio` never a feature.
- New migration only through `python -m pipelines.migrate`, next number **032**; never edit 001–031; add every new migration to `EXTRA_DDL` in `backend/tests/test_neural_api.py`.
- API stays read-only; route-count test becomes 12; no route contains «persona» or «episodio».
- UI copy in neutral Spanish for non-technical readers; dark theme; no horizontal overflow at 375 px.
- **No commits** (user rule). Every task ends with "no commit" instead of a commit step.
- DB credentials only inline per command: `DEV_HOST=localhost DEV_PORT=5432 DEV_DB=postgres DEV_USER=postgres DEV_PASSWORD=1234`. No warehouse access.

## Review Focus

1. **Refit that does not reproduce** — a rebuilt model whose test predictions differ from the saved ones must abort the projection run with a clear error, never publish (Task 2).
2. **Complementary disclosure** — one hidden cell recoverable by subtracting visible cells from a shown total must not happen (Task 3, Task 7).
3. **Future data leak** — rows or attempts with `periodo > '202610'` must not change any projection or threshold count (Task 5, Task 6).
4. **Teacher/section leak in R-2** — no key or value naming a section, NRC or teacher may reach artefacts or API (Task 4, Task 7).
5. **Fully suppressed block under a small faculty filter** — the UI shows the «oculto por tamaño» notice instead of an empty chart or a crash (Task 7, Task 8).

---

### Task 1: Migration 032 for the new blocks and the projection table

**Files:**
- Create: `Redes/sql/core/032_vista_temas_proyeccion.sql`
- Modify: `backend/tests/test_neural_api.py` (`EXTRA_DDL`, lines ~55-59)
- Test: `Redes/tests/unit/test_vista_temas_ddl.py`

**Interfaces:**
- Produces: `neural_mart.vista_historica.bloque` CHECK accepts the existing six values plus `perfil_ingreso, primer_semestre, ramos_reprobados, ramos_esperado, cuellos_botella, semestre_malla, causales_programa, tiempo_egreso, senales, esperar_semestre`. New table `neural_mart.vista_proyeccion(bloque text NOT NULL CHECK (bloque IN ('meta','continuidad','eliminacion','egreso','umbral')), facultad text NOT NULL, contenido jsonb NOT NULL, PRIMARY KEY (bloque, facultad))`.

- [ ] **Step 1: Write the failing test** `test_032_passes_the_schema_guard_and_lists_every_block`: `validate_sql(text, "032_vista_temas_proyeccion.sql")` does not raise; the text contains each of the 16 historical block names and the 5 projection block names; it contains no `persona_key` or `episodio_id`.
- [ ] **Step 2: Run** `cd Redes && .venv-ml/Scripts/python.exe -m pytest -q tests/unit/test_vista_temas_ddl.py` → FAIL (file missing).
- [ ] **Step 3: Write the migration**: `ALTER TABLE ... DROP CONSTRAINT IF EXISTS vista_historica_bloque_check`, re-add the widened CHECK, `CREATE TABLE IF NOT EXISTS neural_mart.vista_proyeccion (...)`. Only statements the schema guard allows (mirror 028 and 029).
- [ ] **Step 4: Run the test** → PASS. Apply: `DEV_*=... .venv-ml/Scripts/python.exe -m pipelines.migrate` → `applied 032_vista_temas_proyeccion.sql`, every other file `skipped`.
- [ ] **Step 5: Add** `REDES / "sql" / "core" / "032_vista_temas_proyeccion.sql"` to `EXTRA_DDL`; run `cd backend && DEV_*=... .venv/Scripts/python.exe -m pytest -q tests/test_neural_api.py` → all pass.
- [ ] **Step 6: No commit.**

### Task 2: Rebuild and persist the kept models

**Files:**
- Create: `Redes/evaluation/modelos_conservados.py`
- Test: `Redes/tests/unit/test_modelos_conservados.py`

**Interfaces:**
- Consumes: the existing fit paths — T1 `run_beneficios_cargas_t1.ajustar_y_predecir` (cb_ben_pit) and `run_nuevas_t1.evaluar_k` internals (cb_acad, lr_acad); T2 `run_nuevas_t2.entrenar` (`cb_c_nuevas`); T3 `run_t3.entrenar_k` internals (`DT.logistica_ajustar`, `NR.entrenar`); T5 `run_t45.entrenar_k` internals (`G.entrenar`). Seeds `(0, 1, 2)`; predictions are the seed mean, as today.
- Produces:
  - `CLAVES: tuple[tuple[str, int, str], ...]` = `(("t1",1,"cb_acad"), ("t1",1,"cb_ben_pit"), ("t1",2,"lr_acad"), ("t2",0,"cb_c_nuevas"), ("t3",0,"dt_lr_adm"), ("t3",2,"nn_gru"), ("t3",4,"nn_gru"), ("t5",2,"gru_adm"), ("t5",4,"gru_agg"))`.
  - `class ModeloConservado` with `tarea: str`, `k: int`, `nombre: str`, `predecir(filas: pd.DataFrame, sem: pd.DataFrame | None) -> np.ndarray` (T1/T2/T5: probability of the event; T3: cumulative incidence array `[n, U]` of egreso).
  - `ajustar(conn, tarea: str, k: int, nombre: str) -> ModeloConservado`.
  - `verificar(modelo: ModeloConservado, conn, artefactos: Path, tol: float = 1e-4) -> float` returns max |Δp| against the saved test predictions (npz paths and keys from the existing runners) and raises `ReproduccionFallida` above `tol`.
  - `cargar_o_ajustar(conn, tarea, k, nombre, artefactos: Path) -> ModeloConservado` persists to `artefactos/modelos/{tarea}_k{k}_{nombre}.joblib` (CatBoost/sklearn) or `.pt` (torch state dicts per seed plus preprocessor via joblib), reloads if present, and always calls `verificar` before returning.

- [ ] **Step 1: Write the failing tests**:
  - `test_verificar_raises_when_predictions_differ`: a stub model whose `predecir` returns saved predictions + 0.01 → `ReproduccionFallida`.
  - `test_verificar_passes_on_identical_predictions`: stub returning the saved array → returns `0.0`.
  - `test_claves_match_the_kept_models_of_the_plan`: `CLAVES` equals the tuple above.
  - `test_persisted_model_round_trips`: on a tiny synthetic logistic fit, save then `cargar_o_ajustar` reloads without refitting (monkeypatch `ajustar` to raise if called).
- [ ] **Step 2: Run** `pytest -q tests/unit/test_modelos_conservados.py` → FAIL (module missing).
- [ ] **Step 3: Implement** the module. Refactor only by extracting the existing fit code into callable functions where it is inline; default behaviour of every runner must stay identical (their tests must keep passing).
- [ ] **Step 4: Run the unit tests** → PASS.
- [ ] **Step 5: Real reproduction check** (long; run in background): `DEV_*=... .venv-ml/Scripts/python.exe -m evaluation.modelos_conservados --verificar-todo` prints one line per key `tarea k nombre max|Δp|=…` and exits 0. Every value ≤ 1e-4.
- [ ] **Step 6: No commit.**

### Task 3: Shared suppression helper with the «otros» rule

**Files:**
- Create: `Redes/evaluation/suprimir.py`
- Test: `Redes/tests/unit/test_suprimir.py`

**Interfaces:**
- Produces: `agrupar_otros(filas: list[dict], clave_n: str = "n", n_min: int = 10, etiqueta: str = "otros") -> list[dict] | None` — rows with `n < n_min` merge into one «otros» row (summing every numeric count field, recomputing `pct` fields from the merged counts); returns `None` if «otros» stays under `n_min`. Used by every distribution block in Tasks 4–6.

- [ ] **Step 1: Write the failing tests**:
  - `test_small_cells_merge_into_otros`: `[{"g":"a","n":50},{"g":"b","n":4},{"g":"c","n":7}]` → `[{"g":"a","n":50},{"g":"otros","n":11}]`.
  - `test_single_small_cell_hides_the_whole_distribution`: `[{"g":"a","n":50},{"g":"b","n":4}]` → `None`.
  - `test_no_small_cells_is_identity`.
  - `test_pct_is_recomputed_on_the_merged_row`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: No commit.**

### Task 4: Historical blocks — Permanencia, Ramos, Egreso y causas

**Files:**
- Create: `Redes/evaluation/vista_permanencia.py`, `Redes/evaluation/vista_ramos.py`, `Redes/evaluation/vista_egreso.py`
- Modify: `Redes/evaluation/vista_historica.py` (`construir`, `construir_documento`, `resumen`; docstring), `Redes/pipelines/marts/vista_historica.py` (`BLOQUES`)
- Test: `Redes/tests/unit/test_vista_permanencia.py`, `test_vista_ramos.py`, `test_vista_egreso.py`, and extend `test_vista_historica.py`

**Interfaces:**
- Consumes: `vista_historica.por_filtro`, `conteo`, `GRUPOS_CAUSAL`, `grupo_causal`, `UCN`, `N_MIN`; `grupos_facultad.alinear`; `suprimir.agrupar_otros`; snapshots `snapshot_t1` (k=1 test, `via_clase`, `tipo_colegio`, `pct_ponderado`), T1 preds `t1_k1.npz` (`test__cb_acad`), `neural_core.intento_asignatura` (`es_intento_evaluado`, `aprobado_curricular`, P58 periods 201920 and 202010 excluded), `neural_core.asignatura_malla` (`semestre`, `nombre_asignatura`, `depto`, `depto_desc`), `neural_core.prerrequisito`, `snapshot_t2` + `t2_nuevas_{test}.npz` / posterior preds of `cb_c_nuevas` joined by `intento_id`, T3 snapshot (k=0, `seguimiento_max >= 12`).
- Produces (each block is `{filtro: contenido}` through `por_filtro`, filters = UCN + faculties):
  - `vista_permanencia.bloque_perfil(d: pd.DataFrame) -> dict | None` → `{n, dimensiones: [{dimension: "via"|"colegio"|"puntaje", filas: [{grupo, etiqueta, n, pct_siguieron, pct_esperado}]}]}`; `puntaje` = quintiles of `pct_ponderado` computed on the UCN test population. Text key `nota_asociacion: true`.
  - `vista_permanencia.bloque_primer_semestre(d) -> dict | None` → `{n, filas: [{reprobaciones: "0"|"1"|"2"|"3+", n, pct_siguieron}]}` (T1 k=1 population with follow-up, reprobaciones of slot 1).
  - `vista_ramos.bloque_reprobados(a: pd.DataFrame, top: int = 15) -> dict | None` → `{desde, hasta, por_tasa: [...], por_volumen: [...]}`, row `{codigo, nombre, depto, intentos, reprobados, tasa}`; a course is listed only if `intentos >= 10` and `reprobados >= 10`. Window: the last five complete years ending 202520.
  - `vista_ramos.bloque_esperado(a: pd.DataFrame) -> dict | None` → `{ventanas: {"prueba": {desde:"202310", hasta:"202420", ramos:[...], deptos:[...]}, "posterior": {desde:"202510", hasta:"202520", ...}}}`, row `{codigo|depto, nombre|depto_desc, intentos, observados, esperados, diferencia, lo, hi}`; `lo/hi` = `diferencia ± 1.96·sqrt(Σ p(1−p))`; top 10 by `diferencia` with `intentos >= 10`. The input frame never carries `nrc` or docente columns (drop them at query time).
  - `vista_ramos.bloque_cuellos(a, prerreq: pd.DataFrame, top: int = 15) -> dict | None` → `{filas: [{codigo, nombre, reprobados, dependientes, impacto}]}`; `dependientes` = number of descendants in the prerequisite graph of the student's catalog (union over catalogs, counted once per course), `impacto = reprobados × dependientes`.
  - `vista_ramos.bloque_semestre_malla(a) -> dict | None` → `{filas: [{semestre, intentos, reprobados, tasa}]}` for `semestre` 1–12 of `asignatura_malla`.
  - `vista_egreso.bloque_causales_programa(causas: pd.DataFrame) -> dict | None` → `{filas: [{cod_programa, programa, total, causales: [{grupo, etiqueta, n, pct}]}]}`; programs with `total < 10` merge into «otros programas» via `agrupar_otros`; under the UCN filter rows are faculties instead of programs. Window from `PERIODO_CAUSAL_DESDE` to `PERIODO_TOTALES_HASTA`.
  - `vista_egreso.bloque_tiempo(t3: pd.DataFrame) -> dict | None` → `{filas: [{cod_programa, programa, n, duracion_nominal_sem, pct_a_tiempo, pct_mas_1, pct_mas_2}]}`; `duracion_nominal_sem` = max `semestre` in `asignatura_malla` for the program's catalog (documented in the block as `regla_duracion`); cumulative egreso by semester among cohorts with ≥ duration + 4 semesters of follow-up; programs with `n < 10` hidden.
  - `construir_documento(...)` gains keyword arguments for the new inputs and adds the keys `perfil_ingreso, primer_semestre, ramos_reprobados, ramos_esperado, cuellos_botella, semestre_malla, causales_programa, tiempo_egreso`; `BLOQUES` in the mart module lists them.

- [ ] **Step 1: Write the failing tests** (synthetic frames, `np.random.default_rng(seed)`, no DB, as in `test_vista_historica.py`):
  - `test_perfil_has_three_dimensions_and_quintiles_sum_to_n`.
  - `test_primer_semestre_buckets_are_0_1_2_3plus`.
  - `test_reprobados_requires_ten_attempts_and_ten_failures`.
  - `test_esperado_interval_brackets_the_difference_and_has_no_section_keys`: `json.dumps(block)` contains none of `nrc`, `docente`, `seccion`.
  - `test_cuellos_counts_descendants_once` on a 4-course chain A→B→C, A→D: `dependientes(A) == 3`.
  - `test_causales_programa_merges_small_programs_into_otros`.
  - `test_tiempo_hides_programs_under_ten`.
  - Extend `test_document_has_no_person_level_keys` to the new keys.
- [ ] **Step 2: Run** `pytest -q tests/unit/test_vista_permanencia.py tests/unit/test_vista_ramos.py tests/unit/test_vista_egreso.py tests/unit/test_vista_historica.py` → FAIL.
- [ ] **Step 3: Implement** the three modules and wire them into `construir` (new SQL queries live next to `Q_T1`/`Q_CAUSAS`).
- [ ] **Step 4: Run the tests** → PASS. Then `DEV_*=... .venv-ml/Scripts/python.exe -m evaluation.vista_historica` → `resumen` prints one line per new block with its UCN headline.
- [ ] **Step 5: No commit.**

### Task 5: «Cómo decide el modelo» blocks

**Files:**
- Create: `Redes/evaluation/familias_variables.py`, `Redes/evaluation/vista_modelo.py`
- Modify: `Redes/evaluation/vista_historica.py` (`construir_documento` adds `senales`, `esperar_semestre`; both UCN only)
- Test: `Redes/tests/unit/test_vista_modelo.py`

**Interfaces:**
- Consumes: `modelos_conservados.cargar_o_ajustar` (Task 2) for T1 `cb_acad` k=1, T2 `cb_c_nuevas`, T5 `gru_adm` k=2; saved test preds `t1_k1.npz`, `t1_k2*` (lr_acad), `t45_k2_test.npz`, `t45_k4_test.npz`.
- Produces:
  - `familias_variables.FAMILIA: dict[str, str]` (every input column of the three models → family id) and `ETIQUETA_FAMILIA: dict[str, str]` (family id → plain Spanish label, e.g. `"notas_ultimo_semestre": "Notas del último semestre"`). A test asserts every model input column has a family.
  - `vista_modelo.importancia_permutacion(modelo, filas, sem, y, familias: dict[str, list[str]], repeticiones: int = 5, semilla: int = 0) -> list[dict]` → `[{familia, etiqueta, caida_ap, peso_pct}]` sorted desc; `peso_pct` = share of the positive drops. For the GRU, permuting a family shuffles those columns across persons in both the static and sequence inputs.
  - `vista_modelo.bloque_senales(...) -> dict` → `{tareas: [{tarea, k, modelo, senales: top 5}]}`.
  - `vista_modelo.bloque_esperar(...) -> dict` → `{comparaciones: [{tarea:"t1", k_antes:1, k_despues:2, de_cada_10_antes, de_cada_10_despues}, {tarea:"t5", k_antes:2, k_despues:4, ...}]}` using `curva_alcance(y, p)["de_cada_10"]` on each saved test set (populations differ; the block carries `nota_poblaciones: true`).

- [ ] **Step 1: Write the failing tests**:
  - `test_every_model_input_has_a_family` (columns from the three models' feature lists).
  - `test_permutation_ranks_the_informative_family_first`: synthetic logistic data where only family `x` drives `y` → first entry is `x`, `peso_pct` sums to 100 over positive drops.
  - `test_esperar_uses_de_cada_10_of_curva_alcance`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; rerun `python -m evaluation.vista_historica` and check `senales` lists 5 families per task.
- [ ] **Step 5: No commit.**

### Task 6: Projection document «Lo que viene»

**Files:**
- Create: `Redes/evaluation/vista_proyeccion.py`, `Redes/pipelines/marts/vista_proyeccion.py`
- Modify: `Redes/tools/exportar_resumen_modelos.py` (load `vista_proyeccion.json` when present, like lines 67-69)
- Test: `Redes/tests/unit/test_vista_proyeccion.py`

**Interfaces:**
- Consumes: `modelos_conservados.cargar_o_ajustar`; snapshot rows with `estado_muestra = 'censurada'` at the cut (they keep features with NULL labels): `snapshot_t1`, `snapshot_t3` (+ `_semestre`), `snapshot_t45` (+ `_semestre`); `rules.corte_periodo`; `features_variables.preparar_intentos` and the counting logic of `_features_k` (`reg_rep2_total`, `reg_rep3_cursos`); `rules_variables.UMBRAL_2DA_NUEVO`, `UMBRAL_3RA_NUEVO`; `suprimir.agrupar_otros`; `vista_historica.por_filtro`, `UCN`.
- Produces:
  - `CORTE_ACTUAL = "202610"`.
  - `POBLACIONES: tuple[dict, ...]` — exactly the spec's table: `{"bloque":"continuidad","tarea":"t1","k":1,"modelo":"cb_ben_pit","cohorte":2026}`, `{... "t1",2,"lr_acad",2025}`, `{"bloque":"eliminacion","tarea":"t5","k":2,"modelo":"gru_adm","cohorte":2025}`, `{... "t5",4,"gru_agg",2024}`, `{"bloque":"egreso","tarea":"t3","k":0,"modelo":"dt_lr_adm","cohorte":2026}`, `{... "t3",2,"nn_gru",2025}`, `{... "t3",4,"nn_gru",2024}`.
  - `estudiantes_actuales(conn) -> pd.DataFrame` — pregrado episodes with enrolment or attempts in 202610 and no egreso, titulación or elimination at the close of 202610; columns `episodio_id, cod_programa, facultad, cohorte`. Queries filter `periodo <= '202610'`.
  - `rango(p: np.ndarray) -> tuple[float, float, float]` → `(Σp, Σp − 1.96·sqrt(Σp(1−p)), Σp + 1.96·sqrt(Σp(1−p)))`, clipped to `[0, n]`.
  - `bloque_continuidad(...)`, `bloque_eliminacion(...)`, `bloque_egreso(...)` → `{n, esperados, lo, hi, por_cohorte: [{cohorte, k, modelo, n, esperados, lo, hi}]}`; eliminación adds `{observados_hasta_hoy, periodo_observado: "202610", orientativo: true}`; egreso is `{anios: [{anio: 2027|2028, esperados, lo, hi}], por_cohorte: [...]}` from the CIF horizons translated to calendar years from each cut.
  - `umbral_actual(intentos: pd.DataFrame, actuales: pd.DataFrame) -> pd.DataFrame` → per episode `reg_rep2_total, reg_rep3_cursos, distancia = min(UMBRAL_2DA_NUEVO − rep2, UMBRAL_3RA_NUEVO − rep3) clipped at 0`.
  - `bloque_umbral(u) -> dict | None` → `{n, en_umbral, a_1, a_2, lejos}` (exclusive categories by `distancia` 0, 1, 2, ≥3; `nota_p58: true`).
  - `construir(conn, artefactos) -> dict` → `{version: 1, corte: "202610", n_min, filtros, sin_proyeccion: {n}, continuidad, eliminacion, egreso, umbral}` (blocks via `por_filtro`); writes `artefactos/vista_proyeccion.json`; CLI `python -m evaluation.vista_proyeccion`.
  - Mart: `pipelines.marts.vista_proyeccion.filas(doc)` and `escribir(conn, doc, mart_schema="neural_mart")`, same shape as `pipelines.marts.vista_historica`.

- [ ] **Step 1: Write the failing tests**:
  - `test_poblaciones_match_the_spec_table`.
  - `test_rango_is_sum_and_normal_interval` on `p = [0.5]*100` → `(50, 50 − 9.8, 50 + 9.8)`.
  - `test_umbral_categories_are_exclusive_and_use_art46`: episode with 5 rep2 and 0 rep3 → `a_1`; 6 rep2 → `en_umbral`; 1 rep3 and 0 rep2 → `a_1`; counts sum to `n`.
  - `test_future_attempts_do_not_change_the_threshold`: adding attempts with `periodo = "202620"` leaves `umbral_actual` unchanged.
  - `test_nobody_is_counted_twice_within_a_block`: synthetic populations for cohorts 2025 (k=2) and 2024 (k=4) → `por_cohorte` n's sum to block `n` and episode ids are disjoint.
  - `test_projection_aborts_when_a_model_does_not_reproduce`: monkeypatch `cargar_o_ajustar` to raise `ReproduccionFallida` → `construir` raises and writes no JSON.
  - `test_document_has_no_person_level_keys` (no `episodio`, `persona`, 64-hex).
- [ ] **Step 2: Run** `pytest -q tests/unit/test_vista_proyeccion.py` → FAIL.
- [ ] **Step 3: Implement** both modules and the exporter hook.
- [ ] **Step 4: Run the tests** → PASS. Then `DEV_*=... .venv-ml/Scripts/python.exe -m evaluation.vista_proyeccion` (background) prints the UCN headline of each block and `sin_proyeccion`; then `tools/exportar_resumen_modelos.py` prints `vista_proyeccion  N filas`.
- [ ] **Step 5: No commit.**

### Task 7: Backend — new historical blocks and `GET /neural/proyeccion`

**Files:**
- Modify: `backend/app/services/neural/schemas.py` (after line ~583), `backend/app/services/neural/rules.py` (after line ~188), `backend/app/services/neural/repository.py` (after line ~357), `backend/app/routers/neural.py` (after `/historico`, line ~423)
- Test: `backend/tests/test_neural_api.py`, `backend/tests/test_neural_rules.py`

**Interfaces:**
- Consumes: mart rows from Tasks 4–6.
- Produces:
  - Pydantic models mirroring each new block (names `HistPerfil`, `HistPrimerSemestre`, `HistRamos`, `HistEsperado`, `HistCuellos`, `HistSemestreMalla`, `HistCausalesPrograma`, `HistTiempo`, `HistSenales`, `HistEsperar`) added as optional fields of `HistoricoVista` with the same names as the document keys; `ProyeccionVista {disponible, filtro, filtros, corte, sin_proyeccion, continuidad, eliminacion, egreso, umbral, aviso, notas}`.
  - `rules.depurar_<bloque>(b, n_min)` for each new block: re-applies the n ≥ 10 and «otros» rules server-side (never trust the artefact); `depurar_esperado` also drops any key outside the schema.
  - `repo.proyeccion(conn) -> dict[(bloque, facultad), contenido]`.
  - Route `GET /neural/proyeccion?facultad=` with the same 404 / 503 / `disponible: False` behaviour as `/historico`.

- [ ] **Step 1: Write the failing tests** (seed rows in `_cargar_historico` and a new `_cargar_proyeccion`, including a «Facultad Chica» whose blocks must vanish):
  - `test_historico_serves_the_new_blocks`.
  - `test_new_blocks_hide_cells_under_ten_and_merge_otros` (one distribution with a single small cell → whole distribution hidden).
  - `test_esperado_has_no_section_or_teacher_fields` (seed a row with an extra `nrc` key → absent in the response).
  - `test_proyeccion_serves_four_blocks_with_ranges_and_cut`.
  - `test_proyeccion_filters_by_faculty_and_suppresses_small_groups`.
  - `test_proyeccion_unknown_faculty_is_404_and_missing_table_is_503`.
  - Update the route count to `12`; the «persona»/«episodio» assertion stays.
  - Rules tests for each `depurar_*` in `test_neural_rules.py`.
- [ ] **Step 2: Run** `cd backend && DEV_*=... .venv/Scripts/python.exe -m pytest -q tests/test_neural_api.py tests/test_neural_rules.py` → FAIL.
- [ ] **Step 3: Implement.** **Step 4: Run** → PASS; run the whole backend suite with `DEV_*` → `931 + new passed, 56 skipped`.
- [ ] **Step 5: Restart** the `neural-backend` preview (no hot reload).
- [ ] **Step 6: No commit.**

### Task 8: Frontend — «Lo que pasó» by topic

**Files:**
- Modify: `frontend/src/components/NeuralLoQuePaso.tsx`, `frontend/src/lib/neural.ts` (types after line ~321), `frontend/src/lib/neuralGraficosHistorico.ts`, `frontend/src/lib/neuralLenguaSimple.ts` (`HISTORICO_TEXTOS`, lines ~399-434)
- Create (if `NeuralLoQuePaso.tsx` would pass ~500 lines): `frontend/src/components/NeuralLoQuePasoTemas.tsx` holding the new block components

**Interfaces:**
- Consumes: `neuralApi.historico` (now typed with the new optional fields); `Segmentado`, `Aviso`, `MarcoGrafico`, `Carga`, `Vacio`, `Notas`, `useAncho`, `pct`, `entero` from `NeuralUI`; `EChartsChart`.
- Produces:
  - `type TemaHistorico = "permanencia" | "ramos" | "egreso" | "modelo"`; topic order and contents exactly as the spec (Permanencia: semestres, siguieron, alcance, perfil_ingreso, primer_semestre; Ramos: ramos_reprobados, ramos_esperado, cuellos_botella, semestre_malla; Egreso y causas: eliminados, causales_programa, tiempo_egreso; Cómo decide el modelo: senales, esperar_semestre). Default topic `permanencia`; the faculty filter persists across topics.
  - New chart builders returning `{option, alto}`: `opcionPerfil`, `opcionPrimerSemestre`, `opcionRamos`, `opcionEsperado`, `opcionCuellos`, `opcionSemestreMalla`, `opcionCausalesPrograma`, `opcionTiempo`, `opcionSenales`.
  - `HISTORICO_TEXTOS` gains `temas` labels and, per new block, `{titulo, definicion, comoUsar}`; `perfil_ingreso.definicion` includes «Muestra asociación, no causa.»; `causales_programa` includes «El motivo personal no existe en los datos.»; `umbral`-related copy is in Task 9.
  - A `null` block renders `Aviso` with the existing «oculto por tamaño» text, never an empty chart.

- [ ] **Step 1: Implement** types, chart builders, texts and the topic selector.
- [ ] **Step 2: Run** `cd frontend && npx tsc --noEmit` → no errors.
- [ ] **Step 3: Browser check** (preview `boveda-frontend` + `neural-backend`, dev login): each topic renders its blocks with real data for «Toda la UCN» and one faculty; a small faculty shows the hidden notice; at 375 px `document.documentElement.scrollWidth <= 375`; no console errors. Screenshot each topic.
- [ ] **Step 4: No commit.**

### Task 9: Frontend — «Lo que viene» tab

**Files:**
- Create: `frontend/src/components/NeuralLoQueViene.tsx`, `frontend/src/lib/neuralGraficosProyeccion.ts`
- Modify: `frontend/src/components/NeuralPanel.tsx` (`Vista`, `PESTANAS` lines ~19-26, `contenido` lines ~36-43), `frontend/src/lib/neural.ts` (`neuralApi.proyeccion(facultad: string | null, signal?)`, `ProyeccionVista` types), `frontend/src/lib/neuralLenguaSimple.ts` (`PROPOSITO_PESTANA.proyeccion`, `PROYECCION_TEXTOS`)

**Interfaces:**
- Consumes: `GET /neural/proyeccion` (Task 7).
- Produces: `Vista` gains `"proyeccion"`; tab `{id: "proyeccion", label: "Lo que viene"}` placed second. Block order: umbral (main, first), continuidad, eliminacion, egreso. Every number shows its range («entre lo y hi») and «Corte: 202610». `eliminacion` shows the `Aviso tono="tierra"` with the Art. 46 + P75 warning and the «observado hasta hoy» figure beside the expected one, never summed. `sin_proyeccion.n` is stated under the first model block. `umbral.comoUsar`: «Dónde poner tutorías este semestre.»

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Run** `npx tsc --noEmit` → no errors.
- [ ] **Step 3: Browser check** as in Task 8 for the new tab (UCN, one faculty, small faculty, 375 px, console). Screenshot.
- [ ] **Step 4: No commit.**

### Task 10: Docs, decision record and full verification

**Files:**
- Modify: `Redes/docs/00_plan.md` (new row D121 after D120; version 0.27), `docs/superpowers/specs/2026-11-18-lo-que-paso-temas-y-lo-que-viene-design.md` (state → «construido», note the `tema` deviation)

- [ ] **Step 1: Write D121** in Spanish, same style as D118–D120: the four topics and ten blocks, the projection populations table, the refit-and-verify rule (max |Δp| per key from Task 2), the Art. 46 threshold block, the «otros» suppression rule, and the explicit exclusion of any teacher ranking.
- [ ] **Step 2: Run everything**:
  - `cd Redes && DEV_*=... .venv-ml/Scripts/python.exe -m pytest -q -p no:cacheprovider` → all pass (baseline 1330 + new).
  - `cd backend && DEV_*=... .venv/Scripts/python.exe -m pytest -q` → all pass, 56 skipped.
  - `cd frontend && npx tsc --noEmit` → clean.
  - Hygiene: `grep -rniE "<prefijo-clave-warehouse>|DEV_PASSWORD=|nombre_estud|nombre_prof|nombre_banner|docente_key" Redes/evaluation Redes/pipelines/marts backend/app frontend/src` → only pre-existing exclusion lists, nothing in the new files; `grep -c '"nrc"\|docente' Redes/artefactos/vista_historica.json Redes/artefactos/vista_proyeccion.json` → 0.
  - `sha256sum` of `artefactos/preds/t1_* t2_* t3_* t45_* t6_*` unchanged against a copy taken before Task 2.
- [ ] **Step 3: No commit.** Report per block the UCN headline numbers to the user.
