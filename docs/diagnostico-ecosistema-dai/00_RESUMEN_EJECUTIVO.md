# 00 · Resumen ejecutivo — Bóveda DAI

> Diagnóstico del 2026-10-22 sobre el commit `6879a9e`. Etiquetas de evidencia en [README.md](README.md).

## Qué es

La **Bóveda DAI** es una aplicación web de acceso restringido de la Dirección de Análisis Institucional. Su función es **custodiar módulos con información sensible** y abrirlos solo a cuentas autorizadas una por una. Hoy contiene un único módulo, el **Termómetro Institucional** (identificador `percepcion`). Ese módulo mide la **percepción de la comunidad UCN en redes sociales** a partir de publicaciones y comentarios en cuentas públicas institucionales de Instagram. **Confirmado** (`README.md:3-7`, `backend/sql/001_boveda_access.sql:32-38`, `frontend/src/components/PercepcionPanel.tsx:1317-1318`).

El módulo nació dentro de la **Torre de Control**. Se separó en una aplicación propia **por la sensibilidad de los datos**: la base contiene comentarios reales de la comunidad. **Confirmado** (`README.md:3-7`).

## Para quién

| Actor | Papel | Estado |
|---|---|---|
| Alta dirección universitaria (rectoría, vicerrectorías, direcciones) | Destinataria de la lectura del índice y sus alertas | Confirmado por el responsable; coherente con la UI: "reservada a la dirección universitaria" (`frontend/src/app/layout.tsx:11`) |
| Equipo DAI | Opera el módulo: marca eventos de contexto, regenera resúmenes y, como administración, cura y anota el modelo | Confirmado (roles `equipo` y administrador en `backend/app/services/auth.py`, `README.md:25-29`) |
| Académicos en fase de prueba | Usuarios de prueba que dan retroalimentación | Documentado en `scripts/crear_form_retroalimentacion_termometro.gs:2-12` |

## Qué hace (capacidades)

- **Índice 0–100 de percepción** (50 = empate entre lo favorable y lo desfavorable). Se puede filtrar por sede, facultad, departamento, tema y período, y ponderar por *likes* y por recencia. **Confirmado** (`backend/app/services/percepcion/repository.py:371-379`).
- **Alertas tempranas**: términos de conflicto (paro, toma, petitorio, asamblea, movilización) y quincenas fuera de lo habitual (mediana + MAD). **Confirmado** (`services/percepcion/lexico.py:104`, `repository.py:545-792`).
- **Comparación** por área, tema y unidad, con la volatilidad descontada del ruido de muestreo. **Confirmado** (`services/percepcion/volatilidad.py:176`).
- **Conversación**: evolución diaria con franja de eventos del calendario, nube de palabras y publicaciones más comentadas, siempre **sin mostrar el texto de los comentarios**. **Confirmado** (`backend/tests/test_anonimizacion_api.py`).
- **Resumen semanal narrativo** generado por un modelo de lenguaje externo (Anthropic por defecto), con caché por huella de datos y verificación de cifras. **Confirmado** (`services/percepcion/resumen_llm.py:947-1021`).
- **Simulación** (solo equipo): ensayo de publicaciones, capacidad de anticipar el índice, respuesta a paros y efectos de la comunicación. **Confirmado** (`PercepcionPanel.tsx:1259-1267`).
- **Curación** (solo administración): medición de la calidad del modelo frente a anotación humana, colas de revisión, corrección de temas y subtemas. Cada lectura de texto crudo queda **auditada**. **Confirmado** (`routers/percepcion.py:81-96`, `backend/sql/002_boveda_admin_audit.sql:18-28`).

## Estado actual

**Prototipo local** (Confirmado por el responsable). El repositorio no tiene Dockerfile, CI ni URL de despliegue, y solo documenta el arranque local (`Boveda DAI.bat`, `.claude/launch.json`).

La historia del repositorio son 10 commits entre el 2026-10-20 y el 2026-10-22, de un único autor.

La **metodología del módulo** es mucho más madura que la aplicación. Trae decisiones medidas y descartes documentados, y unas 715 funciones de prueba en el backend. Como contexto histórico, el módulo estuvo desplegado dentro de la Torre de Control (`docs/PERCEPCION_CONTRATO_WORKER.md:11`).

**Responsable funcional y técnico:** Sebastián Zapata (Confirmado por el responsable).

## Diferenciación

Ninguna otra pieza conocida del ecosistema combina tres rasgos (**Inferido**: las demás aplicaciones no se analizaron en este diagnóstico):

1. **Acceso por listas explícitas que falla cerrado.** Sin filas no entra nadie, y una caída de la base también deniega.
2. **Separación del texto crudo por privilegios de base de datos.** Un rol sin permiso por columna sobre el texto, otro rol privilegiado solo para Curación, y pruebas que impiden que el código normal use la credencial privilegiada.
3. **Honestidad metodológica explícita en la interfaz.** La guía advierte "Para qué no sirve", las vistas avisan "muestra insuficiente", y los casos se presentan como casos y no como promedios.

## Valor institucional

- Da a la dirección una **señal semanal y comparable** del clima de opinión pública en canales institucionales, con alertas que en las pruebas retrospectivas se anticiparon a episodios de conflicto (lead medido: atención 20 días, alerta 28 días; `repository.py:255-266`). **Confirmado** como medición documentada en el código. La validez externa sigue **No verificada**: la base son 8 episodios.
- Aporta a la DAI un **patrón reutilizable de custodia de datos sensibles**: listas por módulo, auditoría de acceso a texto y anonimización por privilegio. **Inferido**.

## Potencial de integración

Hoy la Bóveda **no expone ninguna API pensada para otras aplicaciones**. Todo endpoint exige una sesión de usuario, salvo el disparador post-ingesta protegido por token. **Confirmado**.

Tres oportunidades tienen fundamento (detalle en [04](04_INTEGRACION_ECOSISTEMA.md)):

1. **Identidad compartida con la Torre de Control.** Las dos aplicaciones heredan el mismo modelo de sesión e inicio con Google, y ya conviven en paralelo. **Confirmado** el linaje (`frontend/src/lib/session.ts:2`, `backend/app/services/auth.py:3`). La integración en sí es **Propuesta**.
2. **Publicar agregados anonimizados** (serie del índice, alertas y resumen semanal) mediante una API de lectura versionada o eventos, nunca el texto. **Propuesto**.
3. **El "Recibidor" como patrón de lanzador** del ecosistema, con el modelo de acceso por módulo como base de una autorización común. **Propuesto**.

Con Sonda, Sonda Intelligence y Plataforma CAPD **no hay evidencia alguna** en el repositorio. Cualquier relación con ellas es hipotética.

## Principales hallazgos

| # | Hallazgo | Tipo |
|---|---|---|
| 1 | Seguridad de acceso sólida para un prototipo: fail-closed, rol recalculado en cada petición, auditoría de texto crudo y permisos por columna | Fortaleza (Confirmado) |
| 2 | `GET /percepcion/resumen-semanal` puede gastar en el modelo de lenguaje y escribir en la base aunque lo pida un usuario `lector` | Riesgo (Confirmado) |
| 3 | El token de sesión vive en `localStorage` y no hay CSP; `/docs` y `/openapi.json` quedan públicos | Riesgo (Confirmado) |
| 4 | El repositorio versionado contiene datos sensibles por categoría: identificadores de cuentas personales en comentarios de código y pruebas, fragmentos de comentarios reales en documentos y correos de personas | Riesgo (Confirmado) |
| 5 | La Bóveda reescribe tablas que en teoría son "espejo" del worker, y la recarga desde SQLite con `--reemplazar` borra la curación | Deuda (Confirmado) |
| 6 | No hay CI, lint, pruebas de frontend ni despliegue | Deuda (Confirmado) |
| 7 | El nombre del producto convive en dos niveles ("Bóveda" contenedor y "Termómetro"/"Percepción" módulo) con rótulos inconsistentes, y algunos textos ("Señales bajo vigilancia") pueden asociarse con vigilancia de personas | Insumo para naming (Confirmado) |
