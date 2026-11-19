# DAI Neural — núcleo (Fases 2–4)

Funciones puras de normalización, migraciones SQL, extracción desde el Warehouse (solo lectura, seudonimizada), construcción de `neural_core` y reconciliación del Gate 2.

## Variables de entorno (solo nombres; los valores los define el usuario fuera del repositorio)

| Variable | Uso |
|---|---|
| `DEV_HOST`, `DEV_PORT`, `DEV_DB`, `DEV_USER`, `DEV_PASSWORD` | PostgreSQL local de desarrollo (migraciones, carga, pruebas de integración) |
| `WH_HOST`, `WH_PORT`, `WH_DB`, `WH_USER`, `WH_PASSWORD` | Warehouse, solo lectura (extracción y recuentos de reconciliación) |
| `DAI_NEURAL_HMAC_KEY` | Secreto de la seudonimización (`persona_key`, `docente_key`); también lo usa el backend para la búsqueda por RUT |
| `NEURAL_DATABASE_URL` | Solo backend: URL SQLAlchemy `postgresql+psycopg://...` de lectura, con `options=-c search_path=neural_mart,neural_core,neural_meta`. Sin ella, `/neural/*` responde 503 |

Nunca se escriben credenciales en archivos del repositorio.

**Huella de la clave (guarda anti-desajuste).** La tabla `neural_meta.huella_clave` (migración 010) guarda una huella no reversible (`HMAC(clave, "dai-neural:huella-clave:v1")`) de la clave con que se cargaron los datos, nunca la clave. `pipelines.extract` la compara antes de leer cualquier fuente: si la tabla está vacía la registra; si difiere, aborta sin tocar nada (`--force-todo` recarga todo y adopta la clave actual; `--registrar-huella` solo la registra si no existe). El backend la compara en cada `POST /neural/persona/buscar`: si no coincide o no hay huella responde 503 («La clave de seudonimización del servidor no coincide con la usada para cargar los datos.») en vez de un 404 engañoso, y `GET /neural/calidad` expone `clave_coincide` (pestaña Calidad). `DAI_NEURAL_HMAC_KEY` debe venir de UN solo lugar: se recomienda la variable de entorno de usuario de Windows; si además aparece en `backend/.env` debe ser idéntica, de lo contrario las búsquedas responden 503.

## Pruebas

Desde esta carpeta, con el entorno de la Bóveda:

```
../backend/.venv/Scripts/python.exe -m pytest -q
```

Con el entorno de ML (`.venv-ml/Scripts/python.exe -m pytest -q`) corren además las pruebas de snapshots, modelos y métricas; con el entorno de la Bóveda esas pruebas se omiten (`importorskip` de pandas/sklearn/torch). Las pruebas unitarias no necesitan base de datos. Las de `tests/integration/` se omiten si faltan las variables `DEV_*`; `test_build_core.py` crea y borra el esquema `neural_test`.

## Migraciones

```
../backend/.venv/Scripts/python.exe -m pipelines.migrate            # aplica sql/core/NNN_*.sql
../backend/.venv/Scripts/python.exe -m pipelines.migrate --dry-run  # solo valida, sin conectarse
```

- Solo se pueden tocar los esquemas `neural_meta`, `neural_stg`, `neural_core`, `neural_mart` (y `neural_test` en pruebas). Antes de ejecutar nada, cada archivo pasa una revisión estática que rechaza cualquier otro esquema.
- Cada archivo aplicado queda registrado con su sha256 en `neural_meta.schema_migraciones`. Volver a ejecutar no hace nada; un archivo editado después de aplicado se rechaza (se agrega un archivo numerado nuevo).

## Pipeline de datos (orden de ejecución)

Requiere `DEV_*`, `WH_*` y `DAI_NEURAL_HMAC_KEY` definidas.

```
../backend/.venv/Scripts/python.exe -m pipelines.extract [--only fuente,...] [--force | --force-todo | --registrar-huella]
../backend/.venv/Scripts/python.exe -m pipelines.normalize.build_core [--only paso,...]
../backend/.venv/Scripts/python.exe -m pipelines.reconcile [--markdown ruta] [--no-warehouse]
```

1. **`pipelines.extract`**: lee las vistas vigentes del Warehouse (`banner.*`, `common.programa_d`) con un cursor de servidor en una sesión de solo lectura, seudonimiza el RUT en Python fila a fila y carga `neural_stg` con `COPY`. Solo selecciona las columnas declaradas en `pipelines/extract/sources.py`; las columnas personales se rechazan antes de construir la consulta. Cada ejecución queda en `neural_meta.carga_extraccion` (fuente, `timestamp_carga_wh`, filas de origen e insertadas, sha256 del SQL, tiempos, estado). Es idempotente: repetir una fuente con el mismo `timestamp_carga_wh` no hace nada, salvo `--force`, que la recarga. `ban_tipo_admision` no se copia: se verifica contra el diccionario sembrado.
2. **`pipelines.normalize.build_core`**: reconstruye `neural_core` completo desde `neural_stg` en **una transacción**, con las funciones puras de `pipelines/normalize/`. Pasos: `persona`, `catalogo`, `postulacion`, `episodio`, `intento`, `inscripcion`, `seccion`, `titulacion`, `postgrado`. `--only` reconstruye también lo que depende del paso elegido (p. ej. `episodio` arrastra `intento` y `titulacion`).
3. **`pipelines.reconcile`**: registra en `neural_meta.auditoria_resultado` los chequeos del Gate 2 (stg contra Warehouse, invariantes de privacidad, core contra la evidencia de descubrimiento) y los imprime en una tabla. Solo muestra recuentos.

Resultados y límites: `docs/06_reconciliacion_gate2.md`.

## Marts (Fase 3)

Requiere `DEV_*` y la migración `009_mart.sql` aplicada (`python -m pipelines.migrate`).

```
../backend/.venv/Scripts/python.exe -m pipelines.marts
```

Reconstruye `neural_mart` completo desde `neural_core` en **una transacción** (si falla, quedan los marts anteriores) y registra filas en `neural_mart.mart_construccion`. Hay que repetirlo después de cada `build_core`. Imprime solo recuentos, tiempos y cuántas filas quedaron censuradas. Diseño y reglas: `docs/07_diseno_fase3.md`.

## Snapshots y benchmark T1 (Fase 4)

Tarea T1, «continuidad a un año» (definición, resultados y límites: `docs/08_benchmark_t1.md`). Requiere el entorno de ML (`.venv-ml`, Python 3.11: torch con CUDA, catboost, scikit-learn, pandas, mlflow), `DEV_*` y la migración `011_snapshot_t1.sql`. Los modelos no se publican: las predicciones individuales no se escriben en la Bóveda ni en la API (bandera apagada por omisión).

```
.venv-ml/Scripts/python.exe -m pipelines.migrate                       # aplica 011_snapshot_t1.sql
.venv-ml/Scripts/python.exe -m pipelines.snapshots.t1                  # reconstruye neural_mart.snapshot_t1 (+ _semestre, _resumen) en una transacción
.venv-ml/Scripts/python.exe -m evaluation.run_benchmark                # configuración oficial: --k 1 2 --train-desde 2015; baselines, logística, CatBoost, GRU (3 semillas), IC bootstrap 1.000
.venv-ml/Scripts/python.exe -m evaluation.run_benchmark --todos-los-anios   # sensibilidad: train con todas las cohortes <= 2019 (resultados_t1_todos_anios)
.venv-ml/Scripts/python.exe -m evaluation.descriptivo                  # recuentos agregados del snapshot
.venv-ml/Scripts/python.exe tools/informe_t1.py --doc                      # regenera docs/08_benchmark_t1.md (tools/plantilla_t1.md + JSON agregados)
```

- Hay que repetir `pipelines.snapshots.t1` después de cada `build_core` y `pipelines.marts`.
- Cada corrida se registra en MLflow (almacén local `mlruns/`, ignorado por git) con parámetros, métricas, hash de los datos y versión del código (sha256 de los fuentes de `models/`, `evaluation/` y de las reglas del snapshot; no usa git). Los archivos de modelo, los JSON agregados y las predicciones (`artefactos/`) también están ignorados.
- Sin variables nuevas: solo `DEV_*`.

## Snapshots y benchmark T2 (Fase 4)

Tarea T2, «aprobación por intento» (evento: reprobación; definición, resultados y límites: `docs/09_benchmark_t2.md`), con prueba del grafo curricular explícito (prerrequisitos) y de un GraphSAGE escrito en torch (sin `torch_geometric`). Requiere el entorno de ML (`.venv-ml`), `DEV_*` y la migración `012_snapshot_t2.sql`. Sin variables nuevas.

```
.venv-ml/Scripts/python.exe -m pipelines.migrate                       # aplica 012_snapshot_t2.sql
.venv-ml/Scripts/python.exe -m pipelines.snapshots.t2                  # reconstruye neural_mart.snapshot_t2 (+ _resumen) en una transacción (~3 min)
.venv-ml/Scripts/python.exe -u -m evaluation.run_t2                    # baseline, logística y CatBoost (a-d), embeddings GraphSAGE, redes extremo a extremo (3 semillas), IC bootstrap por grupos (1.000)
.venv-ml/Scripts/python.exe tools/informe_t2.py --doc                  # regenera docs/09_benchmark_t2.md (tools/plantilla_t2.md + artefactos/resultados_t2.json)
```

- Hay que repetir `pipelines.snapshots.t2` después de cada `build_core`. Una fila por intento evaluado de período regular 2015-2025; todo lo histórico usa solo períodos estrictamente anteriores (`merge_asof` sin coincidencia exacta; prueba de perturbación en `tests/unit/test_snapshot_t2.py`).
- Particiones por período del intento: train 2015-2020, valid 2021-2022, test 2023-2024, 2025 como control posterior. Una misma persona puede aparecer en varias particiones.
- `python -m evaluation.run_t2 --muestra 8 --seeds 1 --boot 20 --solo lr_a cb_b nn_gnn --salida smoke_t2` es una corrida de humo (no registra en MLflow).
- Los archivos de modelo, los JSON agregados y las predicciones (`artefactos/`) están ignorados por git; experimento MLflow `t2_aprobacion_por_intento`.

## Snapshots y benchmark T3 (Fase 4)

Tarea T3, «tiempo hasta titulación» (análisis de supervivencia con censura administrativa y salida definitiva como evento competitivo; definición, resultados y límites: `docs/10_benchmark_t3.md`). Cortes `k` = 0 (al ingreso), 2 y 4 semestres regulares. Requiere el entorno de ML (`.venv-ml`, con `lifelines`), `DEV_*` y la migración `013_snapshot_t3.sql`. Sin variables nuevas.

```
.venv-ml/Scripts/python.exe -m pipelines.migrate                       # aplica 013_snapshot_t3.sql
.venv-ml/Scripts/python.exe -m pipelines.snapshots.t3                  # reconstruye neural_mart.snapshot_t3 (+ _semestre, _resumen) en una transacción (~40 s)
.venv-ml/Scripts/python.exe -u -m evaluation.run_t3                    # Aalen-Johansen, Cox, logística/CatBoost de riesgos discretos, redes MLP/GRU (3 semillas, GPU), IC bootstrap de 1.000 remuestreos de episodios
.venv-ml/Scripts/python.exe tools/informe_t3.py --doc                  # regenera docs/10_benchmark_t3.md (tools/plantilla_t3.md + artefactos/resultados_t3.json)
```

- Hay que repetir `pipelines.snapshots.t3` después de cada `build_core`. Una fila por (episodio, `k`): variables con hechos de los semestres `<= k` y etiqueta = (`tiempo` en semestres regulares desde la admisión, `causa`: 1 egreso/titulación, 2 salida definitiva, 0 censura al último período regular cerrado). Pruebas de perturbación y de borrado en `tests/unit/test_snapshot_t3.py`; recálculo SQL independiente en `tests/integration/test_snapshot_t3.py`.
- Particiones por cohorte de admisión: train 2015-2017, valid 2018, test 2019-2020, 2021 en adelante como control posterior. Horizontes 10, 12 y 14 semestres desde la admisión.
- Métricas de supervivencia (C de Uno truncado con evento competitivo, AUC(t), Brier con IPCW, IBS) escritas en `evaluation/metrics_t3.py`, sin `scikit-survival`; el bootstrap usa núcleos en torch (GPU) comprobados contra numpy.
- `python -m evaluation.run_t3 --k 2 --seeds 1 --boot 20 --solo km_programa cox_adm nn_gru --salida smoke_t3` es una corrida de humo (no registra en MLflow).
- Los archivos de modelo, los JSON agregados y las predicciones (`artefactos/`) están ignorados por git; experimento MLflow `t3_tiempo_hasta_titulacion`.

## Snapshots y benchmark T4 y T5 (Fase 4)

Tareas T4, «transición real de programa», y T5, «eliminación» (dos objetivos binarios separados sobre un mismo resultado mutuamente excluyente en el horizonte de los dos semestres regulares siguientes al corte; definición, resultados y límites: `docs/11_benchmark_t4_t5.md`). Cortes `k` = 2 y 4, población de T3 (D47). Requiere el entorno de ML (`.venv-ml`), `DEV_*`, el mart de traslados (`python -m pipelines.marts`, migración 015) y la migración `017_snapshot_t45.sql`. Sin variables nuevas: los atributos son los de T3.

```
.venv-ml/Scripts/python.exe -m pipelines.migrate                       # aplica 017_snapshot_t45.sql
.venv-ml/Scripts/python.exe -m pipelines.snapshots.t45                 # reconstruye neural_mart.snapshot_t45 (+ _semestre, _resumen) en una transacción (~50 s)
.venv-ml/Scripts/python.exe -u -m evaluation.run_t45                   # escalera de ablación (tasa histórica, logística, CatBoost, GRU: 3 semillas, GPU), vista multiclase, IC bootstrap agrupado por persona (1.000), agregados por programa y facultad
.venv-ml/Scripts/python.exe tools/informe_t45.py --doc                 # regenera docs/11_benchmark_t4_t5.md (tools/plantilla_t45.md + artefactos/resultados_t45.json)
```

- Hay que repetir `pipelines.snapshots.t45` después de cada `build_core` y de cada reconstrucción de `programa_traslados`. Una fila por (trayectoria, `k`): atributos de los semestres `<= k` y resultado = continúa, egreso, transición (T4), eliminación (T5), otra salida, transición ambigua o censurado. T4 son los traslados que dejan el programa (cambio de carrera, traslado de sede, otro traslado); la elección de especialidad del Plan Común, el cambio de ciclo y la continuación tras el egreso no son eventos. T5 es el estado `E` (los demás estados de salida no son eliminación académica: P70).
- Particiones por cohorte: train 2015-2019, valid 2020-2021, test 2022-2023, 2024 en adelante como control posterior (solo filas con el horizonte cerrado).
- Pruebas: reglas y exclusividad mutua, horizonte y censura, Plan Común, perturbación y borrado de hechos posteriores al corte (`tests/unit/test_snapshot_t45.py`), métricas de grupos de todo tamaño (`tests/unit/test_metrics_t45.py`), recálculo SQL independiente (`tests/integration/test_snapshot_t45.py`).
- Los agregados por programa y facultad se informan para todo tamaño de grupo, con su n, su intervalo de 95 % y la marca «pocos casos» bajo 10 (D122).
- `python -m evaluation.run_t45 --k 2 --seeds 1 --boot 20 --solo lr_agg cb_agg gru_agg --salida smoke_t45` es una corrida de humo (no registra en MLflow). Experimento MLflow `t45_transicion_eliminacion`; los JSON agregados y las predicciones (`artefactos/`) están ignorados por git.

## Snapshots y benchmark T6 (Fase 4)

Tarea T6, «matrícula en postgrado UCN» después del egreso (supervivencia con censura administrativa; definición, resultados y límites: `docs/12_benchmark_t6.md`). Unidad = la trayectoria de T3 que llegó al egreso, corte = el semestre del egreso, evento = la primera matrícula (`estado_matricula = MATRICULADO`) de la misma persona en un programa de postgrado de la UCN. **Solo se observa el postgrado UCN**: no se estima ninguna probabilidad de postgrado en otras instituciones. Requiere el entorno de ML (`.venv-ml`), `DEV_*` y la migración `018_snapshot_t6.sql`.

```
.venv-ml/Scripts/python.exe -m pipelines.migrate                       # aplica 018_snapshot_t6.sql
.venv-ml/Scripts/python.exe -m pipelines.snapshots.t6                  # reconstruye neural_mart.snapshot_t6 (+ _resumen) en una transacción (~35 s)
.venv-ml/Scripts/python.exe -u -m evaluation.run_t6                    # viabilidad, análisis descriptivo, línea base por programa y Cox, IC bootstrap agrupado por persona (1.000), tablas por programa y facultad (~30 s)
.venv-ml/Scripts/python.exe tools/informe_t6.py --doc                  # regenera docs/12_benchmark_t6.md (tools/plantilla_t6.md + artefactos/resultados_t6.json)
```

- Hay que repetir `pipelines.snapshots.t6` después de cada `build_core`. Una fila por trayectoria egresada: atributos de los semestres `<= k` (`k` = semestre del egreso) y tiempo / evento en semestres calendario (`AAAA50` ≡ primer semestre, `AAAA60` ≡ segundo). Se excluyen (y se cuentan) las personas ya matriculadas en postgrado antes o durante el pregrado o en el semestre del egreso. `sexo`, `cohorte_anio` y el año de egreso nunca son variables.
- Partición por año de egreso: train 2022 o antes, valid 2023, test 2024 o después. **Criterio de viabilidad** fijado antes de entrenar: al menos 30 eventos por partición para la línea base y el Cox, 100 de entrenamiento para CatBoost y 300 para una red; con 50 / 34 / 58 eventos solo se entrena el escalón clásico y ningún horizonte binario es concluyente en test.
- Los agregados por programa y facultad se informan para todo tamaño de grupo, con su n, su intervalo de 95 % y la marca «pocos casos» bajo 10 (D122).
- Pruebas: reglas de etiqueta y censura, exclusión de matrícula previa, perturbación y borrado de hechos posteriores al corte (`tests/unit/test_snapshot_t6.py`), incidencia acumulada contra valores a mano y métricas de grupos de todo tamaño (`tests/unit/test_metrics_t6.py`), modelos y viabilidad (`tests/unit/test_models_t6.py`, `tests/unit/test_run_t6.py`), recálculo SQL independiente (`tests/integration/test_snapshot_t6.py`). Experimento MLflow `t6_postgrado_ucn`; los JSON agregados y las predicciones (`artefactos/`) están ignorados por git.

## API de la Bóveda (Fase 3)

El módulo `neural` vive en `backend/` (`app/routers/neural.py`, `app/services/neural/`). Solo lectura, solo modo local, acceso por la lista de la Bóveda. Registro del módulo: `backend/sql/005_neural_modulo.sql` (lo aplica el equipo; no se aplica solo). Variables del backend: `NEURAL_DATABASE_URL`, `DAI_NEURAL_HMAC_KEY` (más las propias de la Bóveda). Pruebas de integración del backend: `cd ../backend && .venv/Scripts/python.exe -m pytest tests/test_neural_api.py` con `DEV_*` definidas (crean y borran el esquema `neural_test`).

## Estructura

- `pipelines/common/`: configuración por variables de entorno, conexiones, seudonimización.
- `pipelines/extract/`: especificaciones por fuente (`sources.py`), ejecución en streaming (`runner.py`).
- `pipelines/normalize/`: reglas académicas como funciones puras (notas, estados, fechas, episodios, admisión, mallas, secciones) y `build_core.py`.
- `pipelines/marts/`: reglas puras (`rules.py`), SQL de los marts (`sql.py`) y reconstrucción transaccional (`build.py`).
- `pipelines/snapshots/`: reglas puras de T1 (`rules.py`), construcción con pandas (`features.py`) y carga transaccional (`t1.py`); T2: `rules_t2.py`, `features_t2.py`, `t2.py`; T3: `rules_t3.py`, `features_t3.py`, `t3.py`; T4/T5: `rules_t45.py`, `features_t45.py`, `t45.py`; T6: `rules_t6.py`, `features_t6.py`, `t6.py`.
- `models/`: preprocesamiento ajustado solo en train (`data.py`), baseline, logística, CatBoost, GRU y seguimiento MLflow.
- `evaluation/`: métricas con IC bootstrap, subgrupos/equidad, corrida del benchmark y recuentos descriptivos; T2: `metrics_t2.py` (bootstrap por grupos persona-período, Recall@K) y `run_t2.py`; T3: `metrics_t3.py` (supervivencia con riesgos competitivos, bootstrap pareado) y `run_t3.py`; T4/T5: `metrics_t45.py` (bootstrap agrupado por persona, vista multiclase), `grupos_t45.py` (agregados por programa y facultad con supresión) y `run_t45.py`; T6: `metrics_t6.py` (incidencia acumulada con IC por persona, métricas por horizonte, tablas de incidencia por grupo con supresión) y `run_t6.py`.
- `models/` (T2): `t2_data.py` (conjuntos de variables a-d y preprocesamiento solo con train), `t2_grafo.py` (grafo de cursos, GraphSAGE, enlaces autosupervisados, red extremo a extremo).
- `models/` (T3): `t3_data.py` (conjuntos de variables, expansión persona-período, secuencias), `t3_supervivencia.py` (Aalen-Johansen por programa, Cox causa-específico), `t3_discreto.py` (logística y CatBoost de riesgos discretos), `t3_redes.py` (MLP y GRU con cabeza softmax causa-específica).
- `models/` (T4/T5): `t45_data.py` (resultado, objetivos `y4`/`y5`, conjuntos de variables de T3), `t45_multiclase.py` (frecuencias por programa, logística multinomial, CatBoost multiclase).
- `models/` (T6): `t6_data.py` (conjuntos de variables, facultad del programa), `t6_modelos.py` (incidencia histórica por programa, Cox con L2).
- `pipelines/reconcile.py`: reconciliación del Gate 2.
- `pipelines/migrate.py`: aplicador de migraciones.
- `sql/core/`: esquemas, control y diccionarios, staging, silver.
- `tests/fixtures/synthetic_histories.py`: las tres historias sintéticas de control.

Modelo y reglas: `docs/05_modelo_datos.md` y `docs/03_reglas_academicas.md`; diseño de la Fase 3: `docs/07_diseno_fase3.md`.
