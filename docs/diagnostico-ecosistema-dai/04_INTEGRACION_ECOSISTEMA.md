# 04 · Integración con el ecosistema DAI — Bóveda DAI

> Diagnóstico del 2026-10-22 sobre el commit `6879a9e`. Estados: **Confirmado**, **Inferido**, **Propuesto**, **No verificado**. Las secciones 1 y 2 describen el estado actual; de la 3 en adelante todo es **Propuesto** salvo indicación.

## 0. Punto de partida

- **Hoy la Bóveda no se integra con ninguna otra aplicación DAI en tiempo de ejecución.** Sus únicas conexiones externas son Google Identity, el proveedor de modelo de lenguaje y el worker externo `Sentiment_Analisys_University`, que escribe en la base y llama al disparador. **Confirmado** (`README.md:245-266`; `backend/app/services/percepcion/resumen_llm.py:693-701`).
- **La Torre de Control es la aplicación de origen del módulo.**
  - La Bóveda conserva una ruta heredada, `/ai-tasks` (`backend/app/main.py:44`).
  - Su código de sesión y de login declara estar modelado sobre la Torre (`backend/app/services/auth.py:3`, `frontend/src/lib/session.ts:2`).
  - Ambas pueden correr en paralelo con puertos distintos (`README.md:14`).
  - **Confirmado**.
- **Sonda, Sonda Intelligence y Plataforma CAPD no se mencionan en ningún archivo del repositorio.** Sus funciones no se conocen desde este diagnóstico, así que toda hipótesis con ellas es **Propuesta con confianza baja** y se formula de forma condicional. **Confirmado** (búsqueda en todos los archivos versionados).

## 1. Capacidades expuestas hoy

| Capacidad | Interfaz | Consumidor posible | Limitación | Estado |
|---|---|---|---|---|
| Agregados del índice (resumen, evolución, por tema y unidad, emociones, postura) | REST `GET /percepcion/*` | Solo navegadores con sesión de usuario | No hay autenticación entre servicios, ni versionado, ni contrato publicado (`/openapi.json` existe pero no se gestiona) | Confirmado |
| Alertas y anomalías | `GET /percepcion/anomalias`, `/terminos`, `/conflicto` | Ídem | Ídem | Confirmado |
| Calendario de eventos institucionales | `GET /percepcion/eventos`, `/eventos/todos`, `/eventos/tipos` | Ídem | Ídem | Confirmado |
| Resumen semanal narrativo | `GET /percepcion/resumen-semanal` | Ídem | Efecto lateral: puede llamar al LLM y escribir caché | Confirmado |
| Identidad y módulos del usuario | `GET /auth/me` → `is_admin`, `modulos[]` | Ídem | Sesión propia, no interoperable | Confirmado |
| Disparador post-ingesta | `POST /tasks/run/percepcion-resumen` con `X-Tasks-Token` | El worker externo | Token compartido estático; responde siempre 200 | Confirmado |

## 2. Servicios reutilizables aún no expuestos

| Capacidad | Dónde vive | Por qué es reutilizable | Estado |
|---|---|---|---|
| Modelo de acceso por módulo (`modulos`, `accesos_modulo`, `administradores`) con fail-closed y rol recalculado por petición | `backend/sql/001`, `002`; `backend/app/services/accesos/` | Puerto hexagonal limpio y con contrato de pruebas; generalizable a autorización por aplicación o módulo en todo el ecosistema | Confirmado (código); reutilización Inferida |
| Patrón de auditoría de acceso a datos sensibles | `boveda.auditoria_texto`; `routers/percepcion.py:81-96` | "Si no se puede registrar, no se entrega": patrón institucional para cualquier dato sensible | Confirmado; reutilización Inferida |
| Anonimización por privilegio de base de datos | `backend/sql/003_percepcion_roles.sql`; `backend/tests/test_percepcion_privilegios.py` | Separa lo agregado de lo crudo a nivel de base, no solo de API | Confirmado; reutilización Inferida |
| Calendario académico normalizado 2022–2026 (109 eventos con tipo, ámbito y confianza) | `backend/app/data/percepcion_calendario_ucn.json` | Contexto temporal útil para cualquier serie institucional | Confirmado; reutilización Inferida |
| Detección de anomalías robusta (mediana + MAD quincenal) y validación contra episodios | `services/percepcion/repository.py:189-313` | Método genérico para series de indicadores | Confirmado; reutilización Inferida |
| Tokens de diseño y componentes (`--ucn-*`, `EChartsChart`, `SinEvidencia`, `BarraConfianza`) | `frontend/src/app/globals.css`; `frontend/src/components/` | Base de un sistema de diseño común | Confirmado; reutilización Inferida |
| Generación de narrativa con LLM verificada por cifras y con caché por huella | `services/percepcion/resumen_llm.py:595-1021` | Patrón para reportes automáticos con control de alucinación numérica | Confirmado; reutilización Inferida |

## 3. Eventos de negocio que podrían publicarse

**Propuesto.** Hoy no existe ningún bus ni publicación de eventos.

| Evento | Disparador actual equivalente | Carga útil mínima (sin datos personales) |
|---|---|---|
| `percepcion.ingesta_completada` | Llamada del worker al disparador | Rango de fechas, número de comentarios nuevos, huella |
| `percepcion.resumen_semanal_generado` | Fin de `generar_tras_ingesta` | Semana, alcance, índice, modelo, URL de lectura |
| `percepcion.alerta_detectada` | `anomalias` con nivel atención o alerta | Quincena, nivel, severidad, familias del léxico, unidad agregada |
| `boveda.acceso_concedido` / `boveda.acceso_revocado` | `scripts/boveda_accesos.py` | Módulo, rol, quién ejecutó, cuándo (el correo solo hacia un sistema de identidad autorizado) |
| `boveda.texto_consultado` | Inserción en `auditoria_texto` | Para un registro de auditoría central: administrador, endpoint, cantidad de ids, hora |

## 4. Información compartible y no compartible

| Puede compartirse (agregada) | **No debe** compartirse directamente |
|---|---|
| Índice y series por sede, facultad, departamento y tema, con su confianza y n | Texto de comentarios (`percepcion_comentario.texto`) |
| Niveles de alerta y anomalías | Captions de publicaciones (`percepcion_publicacion.caption`) |
| Distribuciones de sentimiento, emoción y postura | Identificadores y nombres de cuentas de redes sociales, sobre todo de organizaciones estudiantiles |
| Calendario de eventos institucionales | `autor_hash` (aunque es seudónimo, permite seguir a un autor) |
| Resumen semanal (tras revisar que no nombre personas) | Justificaciones libres de curación y correos de revisores |
| Métricas de calidad del modelo | Filas de `boveda.auditoria_texto` y listas de acceso, salvo hacia un sistema de identidad o auditoría autorizado |

**Operaciones que requieren autorización institucional (Propuesto):** acceso a texto crudo; envío de cualquier contenido de comentarios o captions a un proveedor externo de IA; alta de nuevos consumidores de los agregados; cambio de las perillas metodológicas, que modifican el número que ve la dirección (`PERCEPCION_CREDITO_NO_ATRIBUIBLE`, `PERCEPCION_NEU_FEDERACION_ADVERSO`).

**Regla por defecto (Propuesto):** ninguna aplicación lee tablas internas de la Bóveda. El acceso se hace por un contrato de API de lectura de agregados o por eventos.

## 5. Matriz de integración

Confianza: alta, media o baja.

| Aplicación relacionada | Caso de uso potencial | Datos/capacidad | Tecnología candidata | Valor | Estado de evidencia |
|---|---|---|---|---|---|
| Torre de Control | Identidad común: una sola cuenta y un lanzador que muestre la Bóveda solo a quien tiene acceso | `GET /auth/me` → `modulos[]`; sesión con el mismo linaje | OIDC institucional o emisor de sesión común; el lanzador consulta "mis aplicaciones" | Alto: elimina logins duplicados y da coherencia | Linaje **Confirmado**; integración **Propuesta**; confianza **media** |
| Torre de Control | Mostrar en la Torre un indicador resumido (índice y nivel de alerta) con enlace a la Bóveda, sin datos sensibles | Índice y alerta agregados a nivel universidad | API REST de lectura versionada (`/v1/indicadores/percepcion`) con token de servicio y alcance limitado; o evento `alerta_detectada` | Medio–alto: visibilidad para la dirección sin abrir la Bóveda | **Propuesto**; confianza **media**. Riesgo: reintroducir en la Torre la sensibilidad por la que el módulo salió de ella |
| Torre de Control | Retirar la ruta heredada `/ai-tasks` y redirigir el worker a la Bóveda | Disparador post-ingesta | Configuración del worker | Bajo (higiene) | Ruta heredada **Confirmada**; el cambio en el worker está **No verificado** |
| Sonda | Si Sonda resultara recoger datos de opinión o encuestas, contrastar el índice de redes con datos declarados | Serie del índice por unidad y período | API de lectura de agregados o evento periódico | Potencialmente alto: valida el índice con otra fuente | **Propuesto**; confianza **baja**. La función de Sonda no consta en este repositorio |
| Sonda Intelligence | Si resultara ser una capa analítica o de IA, consumir agregados y el resumen semanal como insumo | Agregados, anomalías, resumen semanal | API de lectura versionada; eventos `resumen_semanal_generado` | Medio | **Propuesto**; confianza **baja**. Función no verificada |
| Sonda Intelligence | Si ofreciera servicios de IA gobernados, centralizar ahí la llamada al LLM del resumen (contrato de datos y costos únicos) | Insumos agregados y captions | API interna de inferencia con política de datos | Medio | **Propuesto**; confianza **baja** |
| Plataforma CAPD | Gobernanza y protección de datos: revisar y autorizar el tratamiento de comentarios, el envío a proveedores de IA y la lista de cuentas monitoreadas | Inventario de tratamientos, registros de auditoría, perillas metodológicas | Flujo de aprobación con registro; exportación de auditoría | Alto: da base institucional a un tratamiento sensible hoy sin respaldo documentado en el repositorio | **Propuesto**; confianza **baja** en la integración técnica y **alta** en la necesidad de gobernanza. Las funciones de CAPD no constan en este repositorio |
| Plataforma CAPD | Registro central de accesos a datos sensibles | Eventos `texto_consultado`, `acceso_concedido` y `acceso_revocado` | Evento asíncrono hacia un registro de auditoría | Alto | **Propuesto**; confianza **baja** |

## 6. Capacidades compartidas del ecosistema

| Capacidad | Situación en la Bóveda | Recomendación | Estado |
|---|---|---|---|
| Autenticación y SSO | Google ID token + sesión HMAC propia en `localStorage`; sin restricción de dominio | Un proveedor OIDC común (la cuenta Google institucional puede seguir siendo el factor). Sesión por cookie `HttpOnly` o BFF. Cada aplicación conserva su autorización | Propuesto |
| Autorización por usuario, rol y contexto | Roles por módulo + administrador global en la base; control por método HTTP | Generalizar el modelo `modulos`/`accesos_modulo` a "aplicación·módulo·rol" como servicio o esquema común de autorización. Añadir contexto (por ejemplo, restringir por unidad) solo si se necesita | Propuesto |
| Registro de auditoría | Tabla local con huecos (sin IP, sin parámetros, captions no auditadas, sin autor en eventos) | Esquema común de auditoría (quién, qué, cuándo, desde dónde, resultado) con inmutabilidad técnica (REVOKE o trigger) y envío a un registro central | Propuesto |
| Catálogo de API | Ninguno; OpenAPI autogenerado y público | Catálogo DAI con contratos publicados por aplicación; ocultar `/docs` en producción | Propuesto |
| Contratos y versionado | Sin versionado; contrato con el worker desactualizado (`docs/PERCEPCION_CONTRATO_WORKER.md`) | Versión en la ruta (`/v1`) para las API de agregados; contrato del worker vigente y versionado | Propuesto |
| Eventos institucionales | Ninguno | Empezar con un mecanismo simple (webhook firmado o tabla *outbox*) antes de adoptar un bus | Propuesto |
| Observabilidad | Logging sin configuración central; `/health` estático | Logs estructurados con id de correlación, `/health` que compruebe dependencias, métricas mínimas, error tracking común | Propuesto |
| Gestión de identidades | Altas y bajas por CLI con credencial de base | Altas y bajas desde un punto común (o al menos una UI auditada) | Propuesto |
| Design system | Tokens propios con capa UCN (`--ucn-*`) y capa de personalidad (`--boveda-*`) | Paquete común de tokens UCN + cabecera + estados + accesibilidad; cada aplicación conserva su personalidad | Propuesto |
| Portal o lanzador | **El Recibidor ya es un lanzador por permisos** dentro de la Bóveda | Evaluarlo como base del lanzador del ecosistema (lista de aplicaciones según `/auth/me`) | Confirmado el patrón; uso como lanzador **Propuesto** |

## 7. Seguridad de la integración

**Propuesto.**

1. **Mínimo privilegio para consumidores.** Credenciales de servicio con alcance "solo agregados" y sin acceso al rol `boveda_proceso`.
2. **Umbral de anonimato en las API públicas internas.** No devolver cortes con n < 30, coherente con `N_MIN_CONFIANZA`.
3. **Auditoría de consumo.** Registrar qué aplicación consultó qué agregado.
4. **Política de datos con proveedores de IA.** Hoy salen hacia fuera hasta 6 captions de 320 caracteres y 12 palabras agregadas por resumen. Los scripts de evaluación envían texto de comentarios a proveedores externos. Esto requiere decisión institucional antes de compartir capacidades.
5. **No reintroducir sensibilidad en la Torre.** Cualquier indicador que viaje a la Torre debe ser agregado y no permitir reconstruir comentarios.

## 8. Oportunidades y riesgos

| Oportunidades | Riesgos |
|---|---|
| Modelo de acceso y auditoría listo para generalizar | Duplicar datos de percepción en otras aplicaciones y perder el control de privilegios |
| Recibidor como semilla del lanzador DAI | Acoplar la Bóveda a la Torre otra vez y perder la razón de la separación |
| Agregados con metodología documentada, útiles para la dirección | Exponer API sin versionado ni autenticación de servicio |
| Calendario institucional normalizado | Integrar antes de tener despliegue, CI y observabilidad: la aplicación es aún un prototipo local |

## 9. Recomendaciones incrementales

**Propuesto**, en orden. Cada fase es independiente y reversible.

| Fase | Objetivo | Acciones | Prerrequisito |
|---|---|---|---|
| 0 · Base | Hacer la Bóveda desplegable y operable | Despliegue en un entorno gestionado, CI con pruebas y lint, ocultar `/docs`, CSP, `/health` con dependencias, logs estructurados | Decisión de alojamiento |
| 1 · Identidad | Un solo inicio de sesión | Acordar un proveedor OIDC común con la Torre; mover la sesión a cookie `HttpOnly`; mantener la autorización local | Fase 0 y acuerdo con la Torre |
| 2 · Lanzador | Navegación del ecosistema | Exponer "mis aplicaciones y módulos" en un formato común; Recibidor o cabecera con enlaces entre aplicaciones según permisos | Fase 1 |
| 3 · Contrato de agregados | Compartir valor sin datos sensibles | API `/v1` de solo agregados (índice, alertas, calendario) con token de servicio, umbral de n y auditoría de consumo | Fase 0 y autorización institucional |
| 4 · Eventos | Reacción sin acoplamiento | Webhook firmado u *outbox* para `alerta_detectada` y `resumen_semanal_generado` | Fase 3 |
| 5 · Gobernanza común | Auditoría y autorización compartidas | Esquema común de auditoría y de autorización por aplicación·módulo·rol; integración con la plataforma de protección de datos, si corresponde | Decisión institucional |
