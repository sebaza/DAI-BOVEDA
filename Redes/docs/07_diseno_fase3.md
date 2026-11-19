# DAI Neural — Diseño de la Fase 3 (marts y API)

**Versión:** 0.1 · 11-11-2026 · Parte A de la Fase 3: capa gold (`neural_mart`) y backend. La interfaz (React/TS) queda para la parte B.
**Base:** `05_modelo_datos.md` (§5), `03_reglas_academicas.md` (RA12–RA22), `06_reconciliacion_gate2.md`.

## 1. Integración con la Bóveda

- Neural es el módulo `neural` de la Bóveda DAI, **solo en modo local**: no forma parte del modo GitHub Pages.
- **Acceso:** la lista de acceso existente (`require_module("neural")`, rol `lector` basta). No hay endpoints de escritura; el único `POST` (búsqueda por RUT) solo lee. Un módulo sin filas de acceso no deja entrar a nadie (falla cerrado).
- **Alta del módulo:** `backend/sql/005_neural_modulo.sql` inserta la fila en `boveda.modulos` (idempotente). Con la base de accesos configurada, el inicio de sesión de desarrollo (`/auth/dev-login`) también resuelve el acceso desde la base: sin esa fila, o sin una fila en `boveda.accesos_modulo` para el correo (o sin ser administrador global), el módulo no aparece y sus endpoints responden 403. Con `BOVEDA_DATABASE_URL` vacío no se concede nada. El SQL no se aplica solo: lo aplica el equipo.
- **Datos:** variable `NEURAL_DATABASE_URL` (URL `postgresql+psycopg://...` con `options=-c search_path=neural_mart,neural_core,neural_meta`). El motor se crea de forma perezosa (`services/neural/db.py`), en sesión de solo lectura y con tiempo máximo por consulta; no hay `create_all` ni DDL. Sin la variable, los endpoints responden 503 con un mensaje fijo y la aplicación arranca igual.
- **Búsqueda por RUT:** requiere `DAI_NEURAL_HMAC_KEY`. Sin ella, solo esa ruta responde 503.

## 2. Reglas transversales

| Tema | Regla |
|---|---|
| Promedios | Solo sobre intentos con `es_intento_evaluado` y `nota_numerica` no nula y no heredada. DPA, CONVA y CONV/* no entran (RA13) |
| Tasa de aprobación | Por intento evaluado; excluye convalidaciones y renuncias. Se guarda el denominador junto a cada tasa |
| Avance curricular | Cuenta cada ramo aprobado una sola vez (primera aprobación), convalidaciones incluidas, con créditos `creditos` (o `creditos_reconocidos`) |
| Intentos sin episodio | `sin_episodio` o `episodio_ambiguo` no entran a ningún indicador de episodio (R36); se listan en la API con su bandera |
| Semestre regular | Período que termina en 10 o 20. `semestre_k` = número de períodos regulares desde el de admisión (k = 1 en el semestre de admisión). Verano, invierno y otros no tienen `semestre_k`. Admisión con sufijo no regular (01, 15, 25) se ubica en el semestre en que cae |
| Activo | Con un estado de clase matrícula, reintegro o cambio de ciclo en el semestre. Las reversas 1/2/5 nunca cuentan (RA06) |
| Supresión | **Suprimida por D122 (18-11-2026):** los marts publican grupos de todo tamaño, con `n` visible; la protección es la casilla de aceptación. Registro histórico: antes un estadístico sobre menos de 10 personas no se publicaba (valor NULL, bandera `suprimido`, umbral en `mart_construccion.n_min`) |
| Censura | Una ventana de `k` años desde el semestre de admisión se observa solo si su último semestre es **estrictamente anterior** al último período regular de los datos (ese período puede estar en curso). Si no, el valor es NULL con `censurado = true`; nunca cero |
| Duración | `programa_catalogo.duracion` viene en **semestres** (un plan de 10 semestres titula en promedio a los 6,3 años). `duracion_anios = ceil(duracion / 2)`; los horizontes son `duracion_anios`, `+1` y `+2` |
| Período de titulación | Período del primer estado `U`; si no hay, período de la fecha de titulación (enero y febrero cierran el segundo semestre del año anterior; marzo a julio, 10; agosto a diciembre, 20) |

Las definiciones puras están en `pipelines/marts/rules.py`; el SQL las implementa y `tests/integration/test_marts.py` verifica que coinciden.

## 3. Tablas de `neural_mart` (migración `009_mart.sql`)

Se reconstruyen completas con `python -m pipelines.marts` en **una transacción**: si algo falla, queda la versión anterior. Todas llevan solo `persona_key`, nunca RUT, nombre, sexo ni clave de docente.

| Tabla | Grano | Contenido |
|---|---|---|
| `indicador_periodo` | (`episodio_id`, `periodo`) | Períodos con estado o intento del episodio. Intentos evaluados, aprobados, reprobados, convalidaciones, créditos aprobados del período y acumulados, promedio del período y acumulado con su `n`, ramos aprobados acumulados, intentos y aprobados acumulados |
| `ficha_episodio` | `episodio_id` | Persona, programa, admisión, períodos, semestres regulares cursados, último estado y su clase, `titulado`, `egresado`, `periodo_titulacion`, créditos y promedio acumulados, tasa de aprobación con denominador, `retencion_1er_anio` |
| `avance_malla` | (`episodio_id`, `codigo_asignatura`) | **Dispersa:** solo ramos de la malla del catálogo final del episodio (o el inicial) con algún intento o en curso (1,46 millones de filas; la malla completa serían 12,7 millones). Los `no_cursada` los deriva la API desde `asignatura_malla`. Semestre, créditos, nombre, `es_hito`, `estado_ramo` (`aprobada`, `convalidada`, `reprobada_pendiente`, `en_curso`, `no_cursada`), intentos evaluados, mejor nota, último período |
| `cohorte_semestre` | (`cod_programa`, `cohorte`, `semestre_k`) | `n_episodios`, `n_activos`, `n_promedio` y percentiles 25/50/75 de créditos y de promedio acumulado |
| `programa_semestre` (auxiliar) | (`cod_programa`, `semestre_k`) | Lo mismo sobre todas las cohortes del programa |
| `cohorte_resultado` | (`cod_programa`, `cohorte`) | `n_ingreso`, duración, titulados a `d`, `d+1` y `d+2` años con su censura, retención al primer año con su denominador |
| `postulante_contexto` | (`cod_carrera`, `year_admision`, `banda_ponderado`) | Resultados históricos de postulantes pasados que se matricularon (retención y titulación a `d+1` años) |
| `mart_construccion` | `mart` | Filas, fecha de construcción, período máximo y umbral de cada tabla |

Detalles que conviene conocer:

- **`estado_ramo`.** Aprobada (nota evaluada ≥ 4,0) gana sobre convalidada; luego en curso (inscripción vigente sin resultado, solo en el último período de la fuente de inscripciones, 2025 en adelante); luego reprobada pendiente (hubo intentos evaluados y ninguno aprobó); si no, no cursada. Un ramo solo renunciado figura como no cursado.
- **Retención al primer año.** Verdadero si hay estado de matrícula en el semestre 3 o si el episodio llega a titulado o egresado. NULL si el semestre 3 aún no es observable.
- **Cohorte.** Es el `periodo_admision` del episodio. Se incluyen todas las vías de ingreso; una cohorte puede mezclar ingreso regular y cambios de carrera.
- **Percentiles de cohorte.** El último período regular de los datos no se usa (está en curso y sus notas son parciales).
- **Bandas del ponderado.** Quintil por `percent_rank` del mayor `ponderado` de cada postulante entre los postulantes de la misma carrera y período (los empates comparten banda; un grupo de uno cae en la banda 1). Solo hay ponderado informado desde 2017. Un postulante se vincula a un episodio por (`persona_key`, `cod_programa` = `cod_carrera`, `periodo_admision` = `year_admision`).

Tamaño con los datos reales (11-11-2026, período máximo 202620, umbral 10): `indicador_periodo` 447.369, `ficha_episodio` 57.561, `avance_malla` 1.461.978, `cohorte_semestre` 21.970 (13.961 suprimidas), `programa_semestre` 2.006 (790), `cohorte_resultado` 2.095 (1.024 suprimidas, 534 con la ventana a la duración censurada), `postulante_contexto` 2.229 (1.814 suprimidas). Reconstrucción completa: unos 190 s.

## 4. Punto en el tiempo (`corte`)

Los endpoints por persona y episodio aceptan `corte` (`AAAANN`) y devuelven solo hechos con `periodo <= corte`.

- Línea de tiempo, intentos, postulaciones y titulaciones se filtran por período.
- Los indicadores acumulados de `indicador_periodo` son causales (cada fila depende solo de filas anteriores), así que cortar filas es exacto.
- Ficha del episodio y avance de malla se **recalculan** desde el núcleo para el corte (la ficha completa sale del mart). Una prueba compara el cálculo con corte posterior a todo contra el mart.
- `titulado` con corte exige un período de titulación conocido y ≤ corte.
- Las comparaciones usan el `semestre_k` alcanzado al corte; los percentiles de comparación usan la historia completa observada (se avisa en la respuesta).
- La asignación de intentos a episodios (R36) usa el `ultimo_periodo` del episodio; es una fuga menor y conocida de la pertenencia, no de valores.

## 5. API (`/neural`)

| Ruta | Descripción |
|---|---|
| `POST /persona/buscar` | Cuerpo `{rut}` → `{persona_key, tiene_trayectoria, tiene_postulacion}` o 404. Misma seudonimización que el pipeline (copia de `normalize_rut` + HMAC, con prueba de paridad). El RUT viaja en el cuerpo (no en la URL), se lee a mano para que ningún error de validación lo repita, y no se registra ni se devuelve |
| `GET /persona/{key}/resumen?corte=` | Episodios (campos de `ficha_episodio`), postulaciones (vía elegida, número de vías, matrícula) y titulaciones |
| `GET /persona/{key}/linea-tiempo?corte=` | Estados en orden canónico (`periodo`, `sorlcur`), sin las correcciones del sistema (se informa cuántas se omitieron), con fecha original, mínima, máxima y banderas, episodio, tramo y clase |
| `GET /persona/{key}/intentos?corte=&episodio_id=` | Intentos con `resultado_tipo`, nota (solo si es evaluado o heredada con su bandera), aprobación curricular, oportunidad, créditos, más los indicadores por período con denominadores |
| `GET /episodio/{id}/malla?corte=` | Nodos (`avance_malla`) y aristas requisito → asignatura del catálogo; una arista con requisito fuera de la malla se marca (`requisito_en_malla = false`) |
| `GET /episodio/{id}/comparables?corte=` | Valores de la persona por semestre frente a percentiles de la cohorte y del programa, con `n`, `suprimido` y notas de cobertura |
| `GET /persona/{key}/postulante` | Solo datos previos al ingreso (puntajes, NEM, ranking, tipo y dependencia del colegio, vía) y el contexto histórico de la banda: únicamente postulantes de períodos **anteriores** de la misma carrera y banda, por año y agregado (el agregado omite los años suprimidos y se suprime si su propio `n` es menor al umbral) |
| `GET /programas`, `GET /programa/{cod}/cohortes` | Programas con episodios; resultados y series por cohorte |
| `GET /calidad` | Última carga por fuente, resumen de la auditoría (con los chequeos fallidos y su explicación), construcción de los marts y notas de cobertura |

**Privacidad.** Los modelos de respuesta (`services/neural/schemas.py`) son una lista de campos permitidos: lo que no esté declarado no sale. Ninguna respuesta incluye RUT, nombre, sexo ni `docente_key` (las vistas por docente están fuera del MVP). No hay listados masivos de personas: todo es por persona, por episodio o agregado. La ficha de postulante no incluye `matricula` ni sus resultados posteriores. Los datos del colegio se limitan a tipo y dependencia (no región ni comuna).

**Errores.** 401 sin sesión; 403 sin acceso al módulo; 404 persona, episodio o programa inexistente; 422 parámetro inválido; 503 configuración ausente, base no disponible o marts no construidos (mensajes fijos, sin valores ni SQL).

## 6. Pruebas

- Unitarias de funciones puras: `Redes/tests/unit/test_marts_rules.py`, `test_marts_ddl.py`; `backend/tests/test_neural_rules.py` (corte, supresión, agregación, seudonimización con paridad contra el pipeline).
- Integración (se omiten sin `DEV_*`): `Redes/tests/integration/test_marts.py` (marts sobre las historias sintéticas en `neural_test`) y `backend/tests/test_neural_api.py` (API sobre personas sintéticas: acceso y 403, 404, búsqueda por RUT sin eco, corte, DPA/CONVA fuera de promedios, supresión y censura, solo lectura).
- Datos de prueba solo sintéticos; el esquema `neural_test` se crea y se borra en cada módulo.

## 7. Dudas y límites abiertos

1. **Unidad de `duracion`.** Se interpretó en semestres (evidencia: titulados con duración 10 promedian 6,3 años entre ingreso y titulación; con duración 8, 5,9). Si la DAI la define en años, los horizontes de `cohorte_resultado` cambian.
2. **Definición de «activo».** Se usan las clases matrícula, reintegro y cambio de ciclo; contar cualquier estado incluiría a eliminados y renunciados.
3. **Cohorte mixta.** Una cohorte incluye todas las vías de ingreso (regular, cambio de carrera, intercambio). Podría separarse por clase de ingreso.
4. **Retención.** Un episodio que alguna vez llega a titulado o egresado cuenta como retenido aunque falte el estado del semestre 3.
5. **Sin ponderado antes de 2017** y, en general, bandas de grupos chicos: muchas filas quedan suprimidas.
6. **Auditoría de consultas.** Ninguna búsqueda queda registrada (por diseño no se guarda el RUT). Si se requiere trazabilidad de quién consultó a quién, hay que decidir qué se registra (por ejemplo, solo `persona_key` y correo del usuario).
7. **Enumeración de episodios.** `GET /episodio/{id}/...` usa el identificador numérico del episodio, que es secuencial; devuelve datos seudonimizados sin `persona_key`. Si preocupa la enumeración, se puede exigir pasar por `persona_key`.
