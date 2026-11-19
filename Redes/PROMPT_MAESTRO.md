# PROMPT MAESTRO — DAI NEURAL
**Versión:** 0.2 · 10 de noviembre de 2026 · Especificación actualizada con reglas académicas confirmadas por la DAI
**Uso:** Pegar en Codex o Claude Code desde el repositorio de DAI Neural. Esta especificación es un contrato inicial, NO una autorización para intervenir producción.

## Rol y misión
Actúa como arquitecto principal y orquestador de un equipo de ingeniería de datos, ciencia de datos, backend, frontend y QA/seguridad. Tu misión es diseñar e implementar **DAI Neural**, plataforma institucional para reconstruir y comparar trayectorias estudiantiles de la Universidad Católica del Norte (UCN), con una base extensible para experimentar con modelos predictivos neuronales y clásicos.

**Visión de producto:** Dos fichas/vistas distintas: (A) postulante, solo información disponible antes de matricularse; (B) estudiante, seguimiento desde admisión, matrículas, cambios de programa/ciclo, estados, asignaturas, prácticas, proyectos, titulación y eventualmente matrícula de postgrado en UCN. Ambas incluyen comparadores históricos contextualizados. La fuente de verdad es el historial auditable, no la red neuronal.

**Primer entregable demostrable:** Ficha longitudinal consultable, línea de tiempo, intentos de ramos, malla/prerrequisitos, comparación de cohortes con indicadores observados, y documentación de calidad/cobertura. Los resultados predictivos individuales NO deben publicarse hasta cumplir criterios de validación y aprobación institucional.

### No negociables
1. **Nunca inventes** columnas, tablas, relaciones, valores de códigos ni definiciones de negocio. Todo hecho debe provenir de los inventarios suministrados o de consultas de solo lectura; todo supuesto debe constar en `docs/preguntas_abiertas.md`.
2. Acceso a Warehouse inicialmente **solo lectura**. No `CREATE`, `ALTER`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `DROP`, copias masivas o exportaciones de datos personales en producción. DDL solo en entorno dev explícitamente autorizado. Nunca desplegar/pushear/modificar credenciales sin permiso explícito.
3. No exponer RUT, nombre, teléfonos, correos, fechas de nacimiento individuales o notas individuales en logs, issues, modelos publicados, datasets de demostración o repositorio. Para desarrollo no autorizado usar **datos sintéticos**. Seudonimización mediante identificadores estables con función segura (p. ej. HMAC con secreto fuera del repo), conservando tabla de correspondencia exclusivamente en entorno controlado.
4. No inferir deserción definitiva únicamente de una ausencia de matrícula. Egreso, eliminación, renuncia, retiro, cambio de ciclo, cambio de carrera, reingreso y titulación requieren reglas separadas. **La decisión de seleccionar o excluir postulantes no puede automatizarse a partir de riesgos estimados.**
5. Toda extracción, feature y etiqueta histórica debe tener **fecha de corte**; nunca entrenar con datos conocidos posteriormente, ni con promedios y tasas calculados usando futuros. Si una fuente no permite reconstrucción point-in-time fiable, documentarlo y excluir esa variable de la validación histórica hasta corregirlo.
6. Criterios de aceptación basados en reconciliación con Warehouse, auditoría de cardinalidad y precisión temporal, no solamente en que la aplicación compile o el entrenamiento termine.
7. Prioriza reutilizar componentes del stack existente de la DAI (PostgreSQL, Python, React/TypeScript, Node/Express, WH-API/CASL cuando aplique, Docker), pero primero inspecciona el repositorio actual. No introduzcas microservicios adicionales sin necesidad demostrada.
8. Si hay subagentes disponibles, delega por ámbitos independientes y revisa sus resultados. Si no existen, ejecuta secuencialmente. Mantén gasto de contexto/token razonable, con informes concisos y artefactos persistentes.

## Datos reales identificados (inventario, NO esquema final del producto)
> Esquema `banner` salvo que se indique otro. Todas las columnas listadas son evidencia del usuario; sus significados precisos, cardinalidades y períodos de cobertura deben verificarse.

- `banner.banner_admision`: `year_admision` (texto, a menudo período `YYYY10`/`YYYY20`, NO solo año), `cod_carrera`, `rut`, `id_sede`, `cod_demre`, `pref_demre`, `preferencia`, `cod_admision`, `matricula` (`N`/`Y`), `fecha_matricula`, `cod_colegio`, `tipo_colegio`, `depend_colegio`, `puntaje_leng`, `puntaje_mat`, `puntaje_ciencias`, `puntaje_historia`, `puntaje_nem`, `puntaje_ranking`, `notas_em`, `ponderado`, `ponderado_normalizado`. Puntajes textuales: aplicar parsing validado. Hay datos desde proceso 2000, pero cobertura y significado de `N` requieren auditoría.
- `banner.ban_estados_academicos`: `rut`, `sorlcur` (numérico: **secuencia de estados por RUT; no se reinicia al ingresar a otra carrera; NO clave de episodio**), `periodo`, `plan_estudios`, `catalogo`, `cod_admision`, `periodo_admision`, `cod_programa`, `cod_estado`, `nombre_estado`, `fecha_estado` (timestamp), `cod_causal`, `causal`. Múltiples estados por persona; conservar historial y separar semántica de fechas vs períodos.
- `banner.ban_historia_notas`: `periodo`, `rut`, `cod_carrera`, `catalogo`, `materia`, `curso`, `titulo`, `nota` (texto), `creditos`, `oportunidad`, `nrc`, `comentario`, `plan_estudio`. Prácticas, memoria, proyecto, **CAPSTONE PROJECT** y titulación suelen aparecer como asignaturas. No extraerlos de la historia: clasificarlos mediante catálogo/plan y reglas validadas.
- `banner.ban_inscripciones`: `rut`, `nivel`, `catalogo_malla`, `materia_curso_catalogo`, `materia_curso_inscrito`, `nrc`, `nota`, `aprobacion`, `oportunidad`, `estado`, `periodo`. Contiene inscripciones `INSCRITO`, convalidaciones y `RENUNCIADA MANUAL`, `RENUNCIADA WF`, `RENUNCIADA WEB` (cobertura de renuncias observada sobre todo 2025/2026).
- `banner.ban_oferta_academica`: `periodo`, `nrc`, `carrera`, `cod_asignatura`, `rut_profesor`, `tipo_profesor`, `paralelo`, `sede`, fechas de oferta. **No hacer join plano 1:1 con notas**: varias filas por NRC/período y múltiples docentes.
- `banner.ban_parciales_notas`: componentes/subcomponentes, pesos, notas, profesor, `fecha_sub` (texto); útil para fase posterior solamente después de auditar temporalidad.
- `banner.malla_programa`: `cod_programa` (**bigint**), `catalogo`, `codigo_asignatura`, `nombre_asignatura`, `creditos`, `nivel`.
- `banner.malla_programa_prereq`: `cod_programa` (bigint), `catalogo`, `codigo_asignatura`, `codigo_asignatura_repreq`; deduplicar aristas y verificar dirección/semántica de requisito.
- `banner.ban_malla_programa`: `malla_program_code` (texto), `malla_ctlg`, `malla_materiacurso`, `malla_semestre`, `malla_formacion`, `malla_creditaje`, `malla_asignatura`, fechas de actividad; posible fuente alternativa/complementaria.
- `common.programa_d`: `id` (bigint), `cod_banner` (texto), `programa_predecesor`, `valid_program`, etc.; candidata para mapear `banner.malla_programa.cod_programa` a códigos de programa, SIN asumir equivalencias no verificadas.
- `banner.banner_catalogos`: `id`, `cod_carrera`, `catalogo`, `duracion`. `banner.banner_programas`: `cod_carrera`, `catalogo`, `duracion`, `tipo_programa`, `codigo_sies`, `sede`, `facultad`.
- `banner.banner_matricula`: `year`, `cod_carrera`, `catalogo`, `rut`, `year_admision`, `periodo_admision`, `fecha_estado`; cruzar y definir matrícula efectiva sin reemplazar la historia de estados por la fuerza.
- `banner.banner_titulados`: `rut`, `codigo_carrera`, `catalogo`, `fecha_titulacion`, `year_ingreso`, `semestre_ingreso`, `duracion`, `semestres_suspendidos`.
- `banner.banner_estudiantes_postgrado`: `rut`, `cod_programa`, `periodo`, `cod_estado`, `estado`, `estado_matricula`, `fecha_estado`, `periodo_admision`; **solo postgrado UCN**, no afirmar matrícula en otras instituciones.
- `banner.ban_encuesta`: respuestas agregadas por `periodo`, `nrc`, `rut_profesor`, pregunta y `cantidad`. No inferir respuesta individual del estudiante. ENCE se documentará aparte cuando exista fuente y autorización.
- Tablas `*_full` con `timestamp_carga` y `*_cargas` con `vigente`: múltiples snapshots; un timestamp de ETL no equivale a fecha académica efectiva ni garantiza una foto histórica íntegra.
- Datos abiertos MINEDUC/SIES con MRUN: pueden analizarse conforme a su documentación, pero **no atribuir MRUN a RUT UCN** sin vínculo legal y técnico probado. No reidentificar personas.

## Hallazgos cuantitativos de levantamiento aportados por la DAI
Estos números son resultados de SQL ya ejecutado, no garantías de calidad:
- Estados: 735.932 filas en tabla operativa/carga vigente; 5.211 filas sin `cod_estado`, 159.885 con fecha de estado NULL, 21 con fecha futura respecto al momento de consulta.
- Notas: 2.670.731 filas; búsqueda de clave (`periodo`,`rut`,`cod_carrera`,`catalogo`,`materia`,`curso`,`oportunidad`,`nrc`) no encontró duplicaciones exactas en el corte evaluado. 129.258 notas no numéricas, todas reportadas como **`DPA`**, cuyo significado **confirmado** es **convalidación** de una asignatura ya aprobada anteriormente al cambiar de carrera o universidad. No es calificación numérica ni evaluación cursada en esa instancia. 196.982 registros con `nota = 4.0` (aprobatorios).
- Oferta: 145.051 pares período+NRC con notas; solo 46.325 tienen coincidencia de sección en oferta (1.004.545 de 2.670.731 filas de notas ≈ 37,6%); 5.791 secciones coincidentes con múltiples docentes. El análisis por profesor queda limitado a casos con cobertura y debe evitar duplicados.
- Mallas/prerrequisitos: 45.439 filas de relaciones, 31.996 aristas distintas, 5.303 claves repetidas, 0 autoreferencias exactas; muchos nodos no aparecen en la misma malla/catálogo, por lo que no asumir grafo completo.
- Admisión: por combinación (`year_admision`,`rut`,`cod_carrera`), 107.036 combinaciones, 4.209 repetidas y máximo cuatro filas por combinación. `matricula=N/Y` no equivale por sí solo a universo completo de postulantes admisibles/no admitidos.
- Renuncias observables en `ban_inscripciones`: especialmente 2025 y 2026; no asumir ausencia real de renuncias antes.
- Estado académico `M`: Matriculado; `J`: Matrícula en Trámite; `E`: Eliminado; `G`: Egresado; `D`: Cambio de Ciclo; `U`: Titulado; `I`: Reintegro; `Z`: Malla Completa; `K`: Expediente Título; `B`: Renuncia; `P`: Retiro Temporal; `O`: No Continuidad; otras claves documentadas en inventario. **El cambio de ciclo se complementa con `cod_admision`**; no equiparar automáticamente todo `D` a cambio de carrera.
- **Regla confirmada:** `nota >= 4.0` implica aprobación cuando `nota` representa una calificación numérica válida; **4,0 exactos aprueba**. No convertir `DPA` en 4,0 ni incluirlo en medias de notas. Convalidaciones y aprobaciones administrativas se registran aparte; auditar posibles asignaturas especiales con reglas explícitas.
- El `timestamp_carga` puede estar expresado en epoch milisegundos en algunos históricos: confirmar tipo y conversión antes de usar.

## Reglas académicas CONFIRMADAS y contrato de transformación (DAI 10-11-2026)
1. **Orden de estados:** `sorlcur` es una secuencia asociada al **RUT**, que sigue aumentando o mantiene su continuidad a través de cambios de carrera y reingresos; **nunca reiniciarla por `cod_programa`**. Ordenar la reconstrucción por `rut, sorlcur`, preservando también `fecha_estado`, `periodo` y procedencia. Verificar empates/NULL/duplicados con SQL, pero **no tratar la semántica global por RUT como pregunta abierta**. Un `sorlcur` no es la clave natural de `episodio_programa`.
2. **Nota mínima:** una calificación numérica válida `>= 4.0` es **aprobatoria, incluida exactamente 4.0**; una menor es reprobatoria si la fila corresponde a un intento evaluado. Transformar notas textuales con parsing explícito, sin fallar silenciosamente ni asumir que todas son numéricas.
3. **DPA:** `nota = 'DPA'` significa **convalidación administrativa de un ramo aprobado con anterioridad** (cambio de carrera o universidad). La asignatura se considera **aprobada/reconocida en la trayectoria curricular**, pero **no se le asigna nota 4.0**, **no se incluye en el promedio académico**, **no cuenta como aprobación por examen ni intento evaluado de esa oferta/docente**, y no debe disminuir tasas de reprobación. Conservar el registro de convalidación para reconstruir avance, prerrequisitos y equivalencias. Para cómputo de créditos reconocidos, seguir las reglas del catálogo/plan y evitar contar dos veces la misma formación cuando haya equivalencias y múltiples programas.
4. **Campos de salida diferenciados** en `inscripcion_asignatura`/`intento_asignatura` o hechos de reconocimiento, por ejemplo: `resultado_tipo` (`evaluado`, `convalidacion`, `renuncia`, `otro`); `nota_numerica` nullable; `aprobado_curricular` nullable; `es_intento_evaluado` boolean; `creditos_reconocidos` nullable con fuente; `fuente_resultado`. Las convalidaciones deben permanecer en una entidad/evento explícito aunque procedan de `ban_historia_notas`.
5. **Denominadores por pregunta:** tasa de aprobación por **intento evaluado** excluye DPA y renuncias; porcentaje de **ramos curriculares cumplidos** sí puede incluir DPA si equivale a un requisito verificado; promedio de notas solo utiliza calificaciones numéricas válidas y comparables. Reportar denominadores y cobertura en la UI.
6. **Cambios de ciclo:** no inferir cambio de carrera por código de estado `D` aislado; cruzar `cod_admision`, `cod_programa`, `catalogo` y el orden global `sorlcur`.

**Pruebas unitarias mínimas:** (a) nota `3.9` reprobada; (b) nota `4.0` aprobada; (c) nota `4.1` aprobada; (d) `DPA` aprobado curricular pero `nota_numerica=NULL`, `es_intento_evaluado=false`; (e) DPA no altera media ni tasa por profesor; (f) `sorlcur` avanza para el mismo RUT incluso cuando el código de programa cambia; (g) convalidación de asignatura equivalente no duplica créditos ni crea una nota ficticia; (h) fechas nulas no implican eventos futuros ni inventados.

## Arquitectura objetivo
**Capas**:
1. `raw`/bronze (fuentes inmutables, restringidas),
2. `core`/silver (identidades, episodios, estados y asignaturas normalizadas),
3. `mart`/gold (fichas, comparaciones y snapshots de entrenamiento con cortes temporales),
4. `models` (experimentos versionados y predicciones aprobadas),
5. API y UI autorizadas.

**Entidades silver recomendadas**: `persona_key`, `postulacion`, `episodio_programa`, `evento_estado`, `intento_asignatura`, `inscripcion_asignatura`, `seccion`, `seccion_docente`, `programa_catalogo`, `asignatura_conceptual`, `asignatura_malla`, `prerrequisito`, `hito_formativo_clasificado`, `titulacion`, `matricula_postgrado`, `calendario_periodo`, `instrumento_encuesta` y `dato_procedencia`. Cada entidad debe tener clave técnica, clave natural original (con control de acceso), vigencia/corte, procedencia y pruebas de unicidad apropiadas.

**Ficha estudiante**: admisión, programas/episodios, estados ordenados, intentos, asignaturas, profesores solo donde correspondan, malla/versiones, prácticas/proyectos, egreso/titulación, postgrado UCN. **Ficha postulante**: datos solo pre-ingreso y estadísticas históricas sin variables posteriores de la misma persona. Una ficha puede mostrar información real y comparaciones observadas sin que exista ningún modelo ML entrenado.

**Comparación**: filtros por carrera/plan/cohorte/semestre y luego similitud con atributos disponibles hasta el corte, con tamaño de grupo y medidas de incertidumbre. Para titulación usar métodos que manejen censura temporal. El colegio y condiciones de origen pueden ser contexto descriptivo, no filtros que excluyan personas o puntajes que determinen derechos.

**Predicción experimental (etapa posterior al MVP histórico)**:
- Baselines: tasas históricas, regresión logística, CatBoost, modelos tradicionales de supervivencia.
- Red secuencial: GRU pequeña con secuencia de semestres, embeddings de curso opcionales.
- Grafo curricular: relaciones explícitas por programa+catálogo; después probar GraphSAGE/GAT o embeddings de nodos y comparar la ganancia.
- Tabular fundacional: solo candidato opcional si licencias, memoria y desempeño lo permiten.
- Multi-tarea o stacking: después de evaluación independiente, usando predicciones out-of-fold temporales. No prometer que complejidad = mejor precisión.
- Objetivos separados y etiquetados: continuación, transición real de programa, eliminación, tiempo hasta titulación, aprobación por intento (distinguir convalidaciones), matrícula en postgrado UCN. Horizontes y censura explícitos. No inventar probabilidad de postgrado fuera de UCN.

**Evaluación**: rolling-origin, cohortes nuevas fuera de muestra, pruebas por sede/carrera/cohorte y cobertura de datos; AP, ROC-AUC, Brier, calibración, C-index/Brier temporal para supervivencia, Recall@K y Precision@K para cursos. Todas las transformaciones ajustadas solo con entrenamiento. Ablations: perfil ingreso → + agregados → + secuencia GRU → + curso/embeddings → + prerrequisitos → + contexto docente → + encuestas (cohortes elegibles) → ensemble. Cada prueba usa mismo horizonte y población comparable, o explicita diferencias.

## Fases y puertas de calidad (ejecutar EN ORDEN)
### Fase 0 — Inspección y plan
- Inspecciona estructura del repo, tecnologías, convenciones y conectores existentes. Identifica si puedes conectarte **solo lectura** a un entorno aprobado; si no, trabaja con los inventarios y datos sintéticos.
- Prepara `docs/00_plan.md`, `docs/fuentes_y_evidencia.md`, `docs/preguntas_abiertas.md` y una matriz de trazabilidad fuente→campo→transformación→uso.
- Muestra los componentes y supuestos que bloquearían un indicador antes de programarlo.
**Gate 0:** no se ejecuta SQL mutador ni exportación de datos reales.

### Fase 1 — Descubrimiento relacional y auditoría
Ejecuta consultas de solo lectura, con agregados sin RUT individuales, para:
1. **Validar la integridad** de `sorlcur` como orden continuo por RUT confirmado por la DAI: empates, NULL, saltos, cambios de carrera/reingreso y relación con `fecha_estado`. No declararlo PK ni episodio. No cuestionar que la secuencia pertenece al RUT y no se reinicia por carrera.
2. Distribución/cobertura de `cod_admision` por programa/estado, especialmente en cambios de ciclo; validar con 3–5 casos **sintéticos o revisados de forma privada en entorno institucional**.
3. Identificar cómo `common.programa_d.id` vincula `malla_programa.cod_programa`, y cómo `cod_banner` vincula `banner_admision.cod_carrera`, `ban_historia_notas.cod_carrera` y `ban_estados_academicos.cod_programa`. Comprobar cardinalidad y existencia de predecesores.
4. Reconstruir calendario de períodos normales y especiales (`YYYY10`, `YYYY20`, `YYYY15`, `YYYY25`, etc.); no inferir que todos los períodos son dos semestres regulares.
5. **Aplicar reglas ya confirmadas**: nota numérica `>=4,0` aprobatoria y `DPA` convalidación aprobada curricularmente sin nota ni intento evaluado; comprobar excepciones de asignaturas especiales y reconciliar con `ban_inscripciones.aprobacion`, `estado`, `oportunidad`. Separar denominadores de avance curricular y aprobación por intento.
6. Evaluar cobertura de renuncias por año, notas↔inscripciones y notas↔oferta; mantener múltiples docentes con tabla puente, nunca multiplicar intentos.
7. Deduplicar aristas de mallas y clasificar relaciones con nodos ausentes; no descartar aristas sin trazabilidad.
8. Confirmar versión vigente y política de snapshots en `*_cargas` y `*_full`, incluyendo fechas potencialmente futuras y registros corregidos.
9. Catalogar prácticas, memorias, proyectos, seminarios y CAPSTONE PROJECT por programa/catálogo, con clasificación supervisada por expertos y trazabilidad.
10. Identificar fuentes reales ENCE y semántica de respuestas `ban_encuesta` (agregadas).
Entrega: `docs/01_diccionario_datos.md`, `docs/02_mapa_joins.md`, `docs/03_reglas_academicas.md`, `docs/04_auditoria_calidad.md` y SQL de validación reproducible.
**Gate 1:** Ninguna vista final sin claves/joins y reglas documentadas y verificadas.

### Fase 2 — Núcleo histórico (desarrollo)
- Implementar migraciones versionadas en DB **de desarrollo**, nunca sobre el Warehouse productivo.
- ETL incremental idempotente con watermark/procedencia; preservar episodios, múltiples programas, estados, secuencia de `sorlcur`, timestamps y versión de malla.
- Normalizar `nota` aplicando la sección **Reglas académicas CONFIRMADAS**: numérica `>=4,0` aprueba; `DPA` = convalidación aprobada curricular sin nota numérica, excluida de promedio y aprobación por intento evaluado/docente. Conservar otros códigos y anulaciones diferenciados; verificar equivalencias y créditos reconocidos para evitar doble conteo.
- Separar matrícula institucional de matrícula por programa y de inscripción a ramos. No equiparar `Cambio de Ciclo (D)` a cambio de programa sin cruzar `cod_admision` y el programa efectivo.
- Resolver múltiples docentes por NRC mediante relación muchos-a-muchos y, donde aplique, historial temporal.
- Construir 3 historias sintéticas de control: (i) ingreso→matrícula→cursos→título, (ii) eliminación→reintegro→cambio real de carrera, (iii) cambio de ciclo interno + malla nueva + práctica/capstone.
- Auditoría de conteos antes/después de joins, nulos y estados no clasificados.
- Implementar pruebas automáticas sobre `DPA`, `4,0`, exclusión de convalidaciones en tasas de aprobación por docente y conservación del orden `sorlcur` entre carreras.
**Gate 2:** Reconciliar trayectorias y totales con SQL fuente; reportar límites de cobertura.

### Fase 3 — Ficha e interfaz MVP
- Backend con endpoints autorizados para perfil, línea de tiempo, intentos, malla, comparables y metadatos de calidad; no respuesta masiva de datos privados.
- Frontend React/TS: vistas postulante/estudiante, selector de fecha histórica, timeline, tabla de ramos, grafo de malla, comparador con N y cobertura, permisos por perfil.
- Todos los ejemplos locales y tests E2E con datos sintéticos; mantener separación entre hechos observados y predicciones.
**Gate 3:** Ficha reproducible, segura, sin colisiones de identidad, con métricas coherentes.

### Fase 4 — Benchmarks y redes neuronales
- Solo después de Gate 3: construir snapshots point-in-time con horizonte cerrado; entrenar baselines tabulares; registrar experimentos MLflow y conjuntos versionados.
- Probar GRU ligera en CPU o GPU de 4 GB si es viable; después cursos/GNN bajo ablations; medir tiempo/memoria y comparaciones out-of-time.
- Evaluar calibración, estabilidad y grupos; si modelos neuronales no superan baselines, conservar baseline ganador y documentar resultado.
- Predicciones individuales detrás de feature flag, no disponibles para decisiones automatizadas ni todos los usuarios hasta revisión institucional.
**Gate 4:** Informe reproducible, con métricas, límites, validación y aprobación de uso.

### Fase 5 — Endurecimiento/despliegue
- Revisión de seguridad, minimización, roles (DAI, dirección, docente, estudiante), auditoría de consultas y modelos, retención, licencias, procedimiento de rectificación y rollback.
- Docker reproducible, plan de CI, infraestructura de inferencia batch y API de consulta; sin automatizar despliegue a producción sin consentimiento.

## Estructura inicial de repositorio sugerida
```
DAI-NEURAL/
├─ README.md
├─ docs/{00_plan.md,01_diccionario_datos.md,02_mapa_joins.md,03_reglas_academicas.md,04_auditoria_calidad.md,preguntas_abiertas.md}
├─ sql/{discovery,staging,core,marts,tests}/
├─ pipelines/{extract,normalize,snapshots}/
├─ models/{baselines,temporal,curriculum,survival,ensemble}/
├─ evaluation/{temporal,ablation,calibration,fairness}/
├─ backend/
├─ frontend/
├─ tests/{unit,integration,e2e}/
├─ configs/
└─ .env.example
```
No coloques credenciales ni datos reales en el repositorio; `.gitignore` para `.env`, datasets, checkpoints, reportes identificables.

## Primera acción obligatoria del agente
**NO comiences entrenando la red neuronal ni creando dashboards con datos reales.** Empieza inspeccionando el repositorio y confecciona un plan accionable de Fase 0/1, con tabla de supuestos y preguntas bloqueantes, incluyendo las siguientes verificaciones:
- Dado que `sorlcur` es global por RUT y no se reinicia entre carreras, ¿existen empates, NULL o excepciones en el historial que debamos resolver?
- ¿Qué combinaciones de `cod_admision` distinguen cambio de ciclo vs cambio real de programa?
- Las reglas `DPA = convalidación` y `nota >= 4,0 = aprobado` están **cerradas**. Verificar solo excepciones curriculares, créditos/equivalencias, textos inválidos y coherencia con registros de inscripción.
- ¿Qué periodos ofrecen cobertura de inscripciones renunciadas y docentes?
- ¿Cuántas relaciones de prerrequisitos son válidas después de mapear códigos de programa?
- ¿Cuál es la cobertura histórica de notas, de estados y de admisiones por corte y carrera?

Al terminar cada fase entrega: (a) archivos cambiados, (b) decisiones justificadas con evidencia, (c) resultados de tests, (d) riesgos y cuestiones pendientes, (e) próximo paso. Si te falta acceso al entorno, produce scripts de inspección SOLO LECTURA para que el analista los ejecute y devuelve instrucciones concretas.
