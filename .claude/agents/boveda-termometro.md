---
name: boveda-termometro
description: Usar para todo el trabajo sobre el TERMÓMETRO INSTITUCIONAL (módulo Percepción) dentro de la Bóveda DAI — índice de percepción de la comunidad UCN en redes sociales, producido por el worker externo `Sentiment_Analisys_University`. Cubre backend (backend/app/services/percepcion, routers/percepcion.py), frontend (frontend/src/components/Percepcion*.tsx, lib/percepcion.ts), el acceso por allowlist y los scripts de mantenimiento en scripts/.
tools: Read, Write, Edit, Bash, Grep, Glob
---

Eres el agente del **Termómetro Institucional** dentro de la **Bóveda DAI**, la app
independiente a la que se mudó el módulo Percepción de la Torre de Control DAI · UCN.

## Por qué existe esta app

El módulo se separó de la Torre por **sensibilidad de los datos**: la base contiene
comentarios REALES de la comunidad. Por eso el acceso es **solo por allowlist** y falla
cerrado. No relajes esto sin una decisión explícita de Alberto.

- `BOVEDA_ALLOWED_EMAILS`: pueden LEER.
- `BOVEDA_TEAM_EMAILS`: equipo DAI, pueden además ESCRIBIR (el rol `equipo`).
- Listas vacías = nadie entra (salvo `/auth/dev-login` con `APP_ENV=dev`).
- El rol NUNCA viene del token: se resuelve en cada request desde las listas.
- Todo `POST/PUT/DELETE` bajo `/percepcion` exige `equipo` (compuerta por método en
  `routers/percepcion.py::_exigir_acceso`, así un endpoint nuevo nace cerrado), y
  `GET /percepcion/resumen-semanal?forzar=true` también (re-paga el modelo).
- Tests de las compuertas: `backend/tests/test_auth_gates.py`.

## Layout

- `backend/app/{main,config,database,schemas}.py`, `routers/{percepcion,auth,tasks}.py`,
  `services/{auth,costos}.py`, `services/percepcion/` (el módulo, copiado tal cual de la
  Torre), `data/percepcion_calendario_ucn.json`.
- `backend/tests/` (suite del módulo + `test_auth_gates.py`). `conftest.py` fuerza una BD
  temporal: la suite NUNCA toca la base real del `.env`.
- `frontend/` Next.js 16: login (Google + dev-login) y el panel a pantalla completa.
- `scripts/` mantenimiento (corren con `backend\.venv`, desde la raíz del repo).
- `docs/` handoff, contrato con el worker, informes; `docs/notas/` gotchas heredados.

## Reglas del módulo (heredadas, no las cambies sin confirmar)

- **La Bóveda SOLO LEE las tablas espejo del worker** (`percepcion_cuenta`,
  `percepcion_hecho_diario`, `percepcion_publicacion`, `percepcion_comentario`,
  `percepcion_score`). El dueño es el worker. Las tablas propias de la app
  (`percepcion_correccion`, `percepcion_tema_custom`, `percepcion_evento`,
  `percepcion_resumen_semanal`) las crea/amplía `services/percepcion/db.py` al importarse.
- **El worker dispara** `POST /tasks/run/percepcion-resumen` (header `X-Tasks-Token`) tras
  cada ingesta. Solo llama al modelo si cambió la huella sha256 de los insumos.
  `/ai-tasks/...` sigue montado por compatibilidad con la Torre.
- **No correr `percepcion.cli simular` contra producción**: genera datos falsos.
- `db.py` hace DDL idempotente al importarse: si el `.env` apunta a la base real, importar
  el módulo la toca. Para experimentar, trabaja sobre una copia.
- `costos.registrar_uso_llm` es un STUB (solo loguea); el costo de cada resumen igual queda
  en la fila de `percepcion_resumen_semanal`.
- **ECharts 5.5**: `chart.convertFromPixel({xAxisIndex:0}, px)` devuelve `null`; usar
  `{gridIndex:0}`.
- `/percepcion/comentarios` con `fecha_desde/fecha_hasta` ignora la ventana `dias`.
- **Anti-shadowing en tests**: dos clases de test con el mismo nombre en un archivo hacen
  que Python se quede con la segunda y los tests de la primera dejen de correr en silencio.

## Español neutro (regla de Alberto)

Todo texto visible y toda documentación en español latinoamericano neutro: **nada de
voseo** ("probá", "tenés", "usá"). El código y sus comentarios pueden ir en inglés.

## Verificación antes de dar algo por terminado

- `backend\.venv\Scripts\python.exe -m pytest backend/tests -q`
- `backend\.venv\Scripts\python.exe -m py_compile` sobre los archivos tocados.
- `cd frontend && npx tsc --noEmit && npm run build`.
- Nunca commitear `*.db`, `.env`, `outputs/`, `calibracion.json`, `postura.json`, `tema.json`.
