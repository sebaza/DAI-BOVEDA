# 05 · Hallazgos, riesgos, madurez y preguntas — Bóveda DAI

> Diagnóstico del 2026-10-22 sobre el commit `6879a9e`. Estados: **Confirmado**, **Confirmado por el responsable**, **Inferido**, **Propuesto**, **No verificado**. Rutas relativas a la raíz del repositorio.

## 1. Hallazgos confirmados

| ID | Hallazgo | Evidencia |
|---|---|---|
| H-01 | La Bóveda es una aplicación independiente que aloja un único módulo, el Termómetro Institucional, separado de la Torre de Control por la sensibilidad de los datos | `README.md:3-7`; `backend/sql/001_boveda_access.sql:32-38` |
| H-02 | Es un prototipo local: no hay Dockerfile, CI ni URL de despliegue | Confirmado por el responsable; `Boveda DAI.bat`; `.claude/launch.json` |
| H-03 | El acceso falla cerrado: sin filas no entra nadie, una base caída deniega a todos, el rol se recalcula en cada petición y la aplicación no arranca en producción sin secretos | `backend/app/services/accesos/__init__.py:60-124`; `services/accesos/postgres.py:92-126`; `backend/app/config.py:101-117` |
| H-04 | La API no entrega texto de comentarios ni captions fuera de Curación, y una prueba recorre todos los GET para comprobarlo | `backend/tests/test_anonimizacion_api.py` |
| H-05 | En PostgreSQL, el rol de la aplicación no puede leer `texto` ni `caption` (permiso por columna); solo el rol de proceso puede | `backend/sql/003_percepcion_roles.sql:34-52,92-101` |
| H-06 | Toda lectura de texto crudo en Curación se audita, y si la auditoría falla no se entrega el texto | `backend/app/routers/percepcion.py:81-96`; `services/accesos/postgres.py:131-146` |
| H-07 | La metodología del índice está documentada en el código, con decisiones medidas: PCC, peso por tema con crédito y daño, postura, mediana + MAD quincenal | `services/percepcion/repository.py:109-380`; `ponderacion.py`; `postura.py` |
| H-08 | El backend tiene unas 715 funciones de prueba; el frontend, ninguna | `backend/tests/`; `frontend/package.json` |
| H-09 | La API tiene 53 handlers sin versionado; `/docs`, `/redoc` y `/openapi.json` son públicos | `backend/app/main.py:31`; `routers/*.py` |
| H-10 | El token de sesión y el objeto usuario se guardan en `localStorage`, y el frontend no tiene CSP | `frontend/src/lib/session.ts:76-77`; `frontend/next.config.ts` |
| H-11 | `GET /percepcion/resumen-semanal` abre sesiones de escritura y privilegiada. Si cambió la huella de los datos, un usuario `lector` dispara una llamada pagada al LLM y una escritura en caché; solo `forzar=true` exige `equipo` | `routers/percepcion.py:400-435` |
| H-12 | La Bóveda escribe en tablas que el README presenta como espejo del worker: actualiza `percepcion_comentario.tema` y `percepcion_score`, y reconstruye entera `percepcion_hecho_diario` en cada corrección | `services/percepcion/curacion.py:142-237`; `backend/sql/003_percepcion_roles.sql:39-52` |
| H-13 | Recargar PostgreSQL desde el SQLite del worker (`--reemplazar`) sobrescribe correcciones, eventos, temas personalizados y resúmenes | `README.md:139-143` |
| H-14 | El resumen semanal usa Anthropic y, si no hay clave, recurre a OpenAI. Ese *fallback* no está en el `README.md`. Al proveedor viajan agregados, hasta 6 captions de 320 caracteres y hasta 12 palabras agregadas de comentarios, sin filtro técnico de datos personales en las captions | `services/percepcion/resumen_llm.py:470-560,693-701`; `README.md:224` |
| H-15 | El script `_evaluar_jueces_percepcion.py` envía texto de comentarios y captions a OpenAI y Anthropic | `scripts/_evaluar_jueces_percepcion.py` |
| H-16 | El repositorio versionado contiene datos sensibles, por categoría: identificadores de cuentas personales de Instagram en comentarios de código y aserciones de pruebas, fragmentos de comentarios reales citados en documentos, correos de personas en un documento y en un docstring de script, e identificadores de cuentas de organizaciones estudiantiles en la regla de postura | `services/percepcion/derivados.py:87`; `repository.py:2211-2215`; `backend/tests/test_percepcion.py:955-975`; `docs/INFORME_PLAN_PERCEPCION_PAPERS.md:620-626`; `docs/notas/`; documento de coordinación del 2026-08-24 en `docs/` (líneas 22 y 36); `scripts/_rescatar_probs_percepcion.py:40`; `postura.py:195` |
| H-17 | La auditoría tiene huecos: no guarda IP ni parámetros; `/curacion/publicaciones` (captions) no se audita; eventos, asignación de temas y temas personalizados no guardan autor; la inmutabilidad es solo "por convención" | `backend/sql/002_boveda_admin_audit.sql:16-28`; `services/percepcion/models.py:365-383` |
| H-18 | `backend/.env.example` está desactualizado: documenta variables eliminadas, omite `BOVEDA_DATABASE_URL` y `PERCEPCION_PROCESO_DATABASE_URL`, y usa un driver distinto del fijado. **No verificado en la revisión final:** el permiso de lectura de `.env.example` estaba bloqueado; solo un análisis lo leyó | Informe del análisis de backend; `README.md:21-23` |
| H-19 | La interfaz muestra a todos los roles los controles de edición (✎ para corregir sentimiento o emoción, "Administrar marcas"); el backend los rechaza con 403 | `frontend/src/components/PercepcionPanel.tsx:1867,2107`; `routers/percepcion.py:66` |
| H-20 | El estado vacío del panel muestra al usuario comandos internos del worker (`python -m percepcion.cli …`) | `frontend/src/components/PercepcionPanel.tsx` |
| H-21 | El favicon (`frontend/src/app/icon.svg`) conserva la identidad de la Torre y no coincide con el emblema ni con la paleta | `frontend/src/app/icon.svg`; `BovedaEmblema.tsx` |
| H-22 | `POST /tasks/run/percepcion-resumen` responde 200 incluso ante un error y devuelve el mensaje de la excepción truncado | `backend/app/routers/tasks.py:55-56` |
| H-23 | Cuatro scripts tienen rutas absolutas del equipo del autor hacia el repositorio del worker | `scripts/_exportar_dataset_percepcion.py:46`; `_reparar_origen_percepcion.py:48`; `_rescatar_probs_percepcion.py:62`; `_verificar_anomalias_percepcion.py:37` |
| H-24 | Los documentos de `docs/` describen la etapa en la Torre (rutas, puertos, infraestructura y archivos que no existen aquí). El contrato con el worker tiene vocabularios de temas y tablas obsoletos | `README.md:266`; `docs/PERCEPCION_CONTRATO_WORKER.md:124-262` |
| H-25 | Los subtemas (script, tablas, endpoints y unas 51 pruebas) no aparecen en el `README.md` | `README.md`; `scripts/agrupar_subtemas_percepcion.py` |
| H-26 | Hay inconsistencias de rotulado: "Percepción de la comunidad" y "Termómetro Institucional"; "La vara" y "¿Se puede predecir?"; la guía habla de cuatro pestañas y hay seis | `PercepcionPanel.tsx`; `PercepcionBaselines.tsx` |
| H-27 | El índice que el código llama "canónico" (sin ponderar) no es el que muestra el tablero por defecto (ponderado por tema) | `services/percepcion/repository.py:1022-1024` |

## 2. Inferencias

| ID | Inferencia | Base |
|---|---|---|
| I-01 | La ingesta es manual: no hay programador y el worker invoca el disparador cuando termina | `routers/tasks.py:42`; `README.md:139` |
| I-02 | El modelo de acceso por módulo y el Recibidor anticipan que la Bóveda aloje más módulos sensibles | Catálogo `boveda.modulos`; `Recibidor.tsx` |
| I-03 | La sesión de la Bóveda probablemente es compatible en formato con la de la Torre, por linaje común | `services/auth.py:3`; `frontend/src/lib/session.ts:2` |
| I-04 | Las reglas metodológicas con impacto institucional (peso por tema, NEU de federación como adverso) se fijaron sin una aprobación formal registrada en el repositorio | Docstrings de `ponderacion.py` y `postura.py` las llaman "decisión institucional" |
| I-05 | Dos correcciones de curación concurrentes podrían entrelazar la reconstrucción de `percepcion_hecho_diario`: no hay bloqueo ni restricción de unicidad | `curacion.py:142-237`; `models.py:58-91` |
| I-06 | La validez del índice como reflejo de la comunidad es limitada por diseño (canales institucionales, el 76,9 % de los autores comenta una sola vez), y la propia UI lo advierte | `docs/INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md:116-131`; `PercepcionPanel.tsx:1317-1318` |

## 3. Riesgos

| ID | Riesgo | Impacto | Probabilidad | Evidencia |
|---|---|---|---|---|
| R-01 | Exposición de datos personales por el repositorio versionado (H-16) si se comparte, se hace público o se migra | Alto | Media | H-16 |
| R-02 | Robo de sesión por XSS: token en `localStorage` y sin CSP | Alto | Baja–media | H-10 |
| R-03 | Gasto de LLM y escrituras disparadas por lectores (H-11) | Medio | Media | H-11 |
| R-04 | Envío de contenido de la comunidad a proveedores externos de IA sin un contrato de datos documentado (H-14, H-15) | Alto | Media | H-14, H-15 |
| R-05 | Pérdida del trabajo de curación al recargar datos o cuando el worker reclasifica (H-12, H-13) | Alto | Alta mientras no haya un flujo de ingesta definido | H-12, H-13 |
| R-06 | Riesgo reputacional por percepción de "vigilancia" de la comunidad u organizaciones estudiantiles: monitoreo de comentarios, "Señales bajo vigilancia" y NEU de federación tratado como adverso | Alto | Media | `PercepcionAlertas.tsx:114`; `postura.py:198-203` |
| R-07 | Persona única: un solo responsable funcional y técnico, sin CI | Alto | Alta | Confirmado por el responsable; H-08 |
| R-08 | Superficie pública innecesaria (`/docs`, `/openapi.json`, `/health` con `APP_ENV`) | Bajo–medio | Media | H-09 |
| R-09 | Fallos silenciosos: el disparador siempre devuelve 200 y hay `except: pass` en el arranque | Medio | Media | H-22; `services/percepcion/db.py` |
| R-10 | Deriva entre la agregación del worker y `reagregar()` de la Bóveda | Medio | Media (ya ocurrió) | `docs/notas/percepcion-pestanas-y-deriva-worker.md` |
| R-11 | Base legal y política de tratamiento de los comentarios no documentadas en el repositorio | Alto | No verificado | — |

## 4. Fase G — Evaluación de madurez (1–5)

Escala: 1 = inicial, 2 = básica, 3 = definida, 4 = gestionada, 5 = optimizada. La falta de evidencia se marca como «No evaluable» y no cuenta como nota baja.

| Dimensión | Nivel | Justificación | Evidencia | Limitaciones |
|---|---|---|---|---|
| Madurez funcional | **3** | El núcleo (índice, alertas, comparación, conversación y curación) está completo y probado. Simulación es experimental, la administración de accesos no tiene UI y la volatilidad está limitada por datos | `01_FICHA_FUNCIONAL.md` §4; `PercepcionSimulacion.tsx` | Sin uso real por los destinatarios (prototipo local); el valor percibido por la dirección no es evaluable |
| Madurez técnica | **2** | Backend bien estructurado en accesos (hexagonal), con fuerte separación por privilegios y muchas pruebas. Pero no hay CI, lint ni contenedores; hay archivos monolíticos, DDL al importar y excepciones silenciadas | `02_ARQUITECTURA_TECNICA.md` §6 | Pruebas no ejecutadas en este análisis; sin cobertura medida |
| Capacidad de integración | **2** | El modelo de acceso por módulo y `/auth/me` son reutilizables, pero no hay API de servicio, versionado, eventos ni contratos publicados | `04_INTEGRACION_ECOSISTEMA.md` §1–2 | Las demás aplicaciones no se analizaron |
| Calidad de documentación | **3** | `README.md` es completo y honesto, incluso sobre los límites de la protección. Pero `docs/` es histórica, el contrato del worker está desactualizado, `.env.example` también, y faltan los subtemas | H-18, H-24, H-25 | — |
| Seguridad y gobernanza | **3** | Controles técnicos poco comunes en un prototipo: fail-closed, permisos por columna, auditoría, pruebas estructurales de privilegio. Restan: sesión en `localStorage` sin CSP, datos sensibles en el repositorio, huecos de auditoría y envío a IA externa sin política documentada | H-03 a H-06, H-10, H-14 a H-17 | La gobernanza institucional (base legal, aprobaciones, política de IA) es **No evaluable** desde el código |
| Consistencia de experiencia de usuario | **3** | Identidad visual propia y coherente (tokens, emblema, voz honesta, preguntas como títulos) y accesibilidad base razonable. Hay restos de la Torre (favicon, colores de eventos), rótulos inconsistentes, errores crudos, controles visibles sin permiso y brechas de accesibilidad | `03_UX_IDENTIDAD_NAMING.md` §1–3 | Sin ejecución ni pruebas con usuarios |

## 5. Fortalezas

1. Diseño de seguridad que falla cerrado, con defensa en profundidad (API, rol de base y pruebas estructurales).
2. Metodología medida y autocrítica, con descartes documentados y límites visibles en la interfaz.
3. Modelo de acceso por módulo con arquitectura hexagonal y contrato de pruebas, listo para generalizar.
4. Identidad visual propia y diferenciada, con un sistema de tokens ya organizado.
5. `README.md` vigente que explica operación, privilegios y límites con transparencia.

## 6. Deuda técnica que afecta a futuras integraciones

1. No hay API de servicio, versionado, contrato publicado ni autenticación entre servicios.
2. La sesión es propia (HMAC) y se guarda en `localStorage`, lo que no la hace apta para un SSO.
3. No hay despliegue, CI ni observabilidad.
4. La propiedad de los datos es ambigua entre worker y Bóveda: tablas espejo modificadas y recarga destructiva.
5. El contrato con el worker está obsoleto.
6. La auditoría es incompleta y no es inmutable técnicamente.
7. Los componentes monolíticos (`repository.py`, `PercepcionPanel.tsx`) dificultan extraer servicios reutilizables.

## 7. Oportunidades de reutilización

- Modelo de autorización `modulos` / `accesos_modulo` / `administradores` para el ecosistema.
- Patrón de auditoría "si no se registra, no se entrega".
- Patrón de anonimización por privilegio de base de datos.
- El Recibidor como lanzador por permisos.
- Calendario académico normalizado.
- Detección de anomalías robusta para otras series.
- Narrativa automática con verificación de cifras y caché por huella.
- Tokens `--ucn-*` y componentes de estado (`SinEvidencia`, `BarraConfianza`).

## 8. Decisiones institucionales pendientes

1. Base legal y política de tratamiento de comentarios de terceros, y si interviene la plataforma o comisión de protección de datos.
2. Qué cuentas de Instagram se monitorean, quién las autoriza y qué criterio aplica a las de organizaciones estudiantiles.
3. Aprobación formal de las reglas metodológicas que cambian el número que ve la dirección (peso por tema, crédito no atribuible, NEU de federación como adverso).
4. Política de uso de proveedores externos de IA: qué datos pueden salir, con qué contrato y con qué retención.
5. Dónde y cómo se despliega la Bóveda, y quién la opera.
6. Quién aprueba los accesos a la Bóveda (hoy solo se registra quién ejecutó el cambio).
7. Qué hacer con los datos sensibles presentes en el historial del repositorio.
8. Si la Bóveda alojará otros módulos sensibles de la DAI.
9. Nombres definitivos de la aplicación y del módulo (proceso de naming del ecosistema).

## 9. Quick wins

**Propuesto**, en orden de esfuerzo bajo e impacto claro.

| # | Acción | Archivo afectado |
|---|---|---|
| QW-1 | Exigir rol `equipo` para que `GET /resumen-semanal` pueda generar contenido (los lectores solo leen la caché) | `backend/app/routers/percepcion.py:400-435` |
| QW-2 | Ocultar `/docs`, `/redoc` y `/openapi.json` fuera de `dev` | `backend/app/main.py:31` |
| QW-3 | Actualizar `backend/.env.example` | `backend/.env.example` |
| QW-4 | Documentar en `README.md` el *fallback* a OpenAI y los subtemas | `README.md` |
| QW-5 | Ocultar en la UI los controles de edición a roles sin permiso | `frontend/src/components/PercepcionPanel.tsx` |
| QW-6 | Reemplazar en el estado vacío los comandos del worker por un mensaje para usuarios | `frontend/src/components/PercepcionPanel.tsx` |
| QW-7 | Alinear el favicon con el emblema | `frontend/src/app/icon.svg` |
| QW-8 | Unificar rótulos ("Termómetro Institucional" / "Percepción"; "La vara") | Componentes de frontend |
| QW-9 | Hacer que el disparador devuelva un código de error HTTP ante un fallo y no devuelva el mensaje de la excepción | `backend/app/routers/tasks.py:55-56` |
| QW-10 | Reemplazar en código, pruebas y documentos los identificadores personales y los fragmentos de comentarios por ejemplos sintéticos | Ver H-16 |
| QW-11 | Definir la clase `portal-skeleton` o quitar su uso | `frontend/src/app/globals.css`; `EChartsChart.tsx` |

## 10. Dependencias que podrían bloquear una integración

1. **Sin entorno desplegado.** Ninguna aplicación puede consumir una API local.
2. **Sin acuerdo de identidad común** con la Torre y las demás aplicaciones.
3. **Sin autorización institucional** para compartir agregados derivados de comentarios de terceros.
4. **Flujo de ingesta indefinido** (SQLite → PostgreSQL manual y destructivo).
5. **Desconocimiento de las funciones de Sonda, Sonda Intelligence y CAPD** desde este diagnóstico.

## 11. Limitaciones del análisis

- No se ejecutó la aplicación, las pruebas ni los scripts; no se abrió ninguna base de datos.
- No se tomaron capturas (ver la guía en `03_UX_IDENTIDAD_NAMING.md` §5).
- El repositorio del worker externo no está disponible: el scoring se describe por contrato y documentación.
- Uno de los análisis no pudo abrir los `.env.example` por permisos. Los nombres de variables salen de `backend/app/config.py`, `README.md` y los usos en el código. Otro análisis sí leyó `backend/.env.example` (H-18).
- Los conteos de pruebas y endpoints son estáticos.
- Las cifras de corpus y calidad del modelo provienen de documentos y docstrings con fechas anteriores; no se verificaron contra la base actual.
- Las demás aplicaciones del ecosistema no se analizaron.

## 12. Preguntas abiertas

El responsable funcional y el técnico son la misma persona (Confirmado por el responsable). Las preguntas se separan por tema.

### Para el responsable funcional

1. ¿Qué decisiones concretas toma o tomará la alta dirección con el índice y las alertas? ¿Con qué frecuencia lo consultaría?
2. ¿Qué rectoría, vicerrectorías y direcciones tendrán acceso, y quién aprueba cada alta?
3. ¿Qué cuentas de Instagram componen el universo "cuentas públicas UCN autorizadas" y quién las autorizó? ¿Se incluirán otras redes?
4. ¿Existe evaluación de privacidad o base legal para tratar comentarios de terceros? ¿Debe intervenir la Plataforma CAPD?
5. ¿Quién valida las reglas metodológicas con impacto institucional (peso por tema, NEU de federación como adverso)?
6. ¿Se mantendrá el nombre "Termómetro Institucional" en las comunicaciones actuales mientras se define el naming del ecosistema?
7. ¿La Bóveda alojará otros módulos sensibles de la DAI? ¿Cuáles?
8. ¿Está vigente la fase de prueba con académicos documentada en el formulario de retroalimentación?

### Para el responsable técnico

1. ¿Dónde se desplegará la Bóveda (por ejemplo, en la misma infraestructura en la nube que la Torre) y con qué pipeline?
2. ¿Cuál será el flujo de ingesta: el worker escribe directo en PostgreSQL, o se mantiene la migración desde SQLite? ¿Cómo se preserva la curación?
3. ¿Qué rol de base de datos usa `BOVEDA_DATABASE_URL`? ¿Puede alterar o borrar `boveda.auditoria_texto`?
4. ¿Se planea un proveedor OIDC común con la Torre? ¿Comparten hoy el formato de sesión?
5. ¿Qué política se aplicará a los scripts que envían texto de comentarios a proveedores externos de IA?
6. ¿Se limpiará el historial del repositorio de los datos sensibles (H-16) antes de compartirlo o migrarlo?
7. ¿Se actualizará `docs/PERCEPCION_CONTRATO_WORKER.md` como contrato vigente Bóveda ↔ worker?
8. ¿Hay planes de CI, lint y pruebas de frontend?

## 13. Recomendaciones priorizadas

**Propuesto.**

| Prioridad | Recomendación | Riesgos que aborda |
|---|---|---|
| P1 | Sanear los datos sensibles del repositorio y decidir sobre su historial | R-01 |
| P1 | Formalizar la base legal, la política de cuentas monitoreadas y la política de IA externa | R-04, R-06, R-11 |
| P1 | Cerrar la generación de LLM a lectores (QW-1) y ocultar `/docs` (QW-2) | R-03, R-08 |
| P2 | Definir el flujo de ingesta y la propiedad de los datos (worker frente a Bóveda) sin recarga destructiva | R-05, R-10 |
| P2 | Preparar el despliegue: contenedor, CI con pruebas y lint, CSP, sesión en cookie `HttpOnly`, observabilidad mínima | R-02, R-07, R-09 |
| P2 | Completar la auditoría (autor en todas las escrituras, captions, inmutabilidad técnica) | Auditoría |
| P3 | Acordar la identidad común con la Torre y exponer "mis aplicaciones" (fases 1–2 de `04`) | Integración |
| P3 | Revisar textos con connotación de vigilancia y unificar rótulos dentro del proceso de naming | R-06, UX |
| P3 | Dividir `repository.py` y `PercepcionPanel.tsx`; añadir puertos al dominio de Percepción | Mantenibilidad |
