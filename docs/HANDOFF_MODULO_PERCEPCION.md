# Handoff — Módulo "Percepción" / Termómetro Institucional

**Para**: agente Claude que va a integrar este módulo sobre `mejora-chatbot-genie`.
**Origen**: rama `Integracion-FormulariosYUsoAPI`.
**Estado**: 504 tests de percepción verdes, `tsc` limpio. Sin desplegar.

> ⚠️ Este documento se escribió **verificando contra `mejora-chatbot-genie`
> archivo por archivo**, no de memoria. Si algo no cuadra, **el código manda**.

> 🟢 **Es el módulo MÁS FÁCIL de integrar de los cinco**, y por una razón que no
> es obvia: **main ya dejó el andamiaje puesto a propósito**. Ver sección 3.

---

## 0. Las dos cosas que hay que leer antes de tocar nada

### 0.1 🔴 NADA DE VOSEO en los textos que ve el usuario

Regla de Alberto del 2026-08-07, y viene con nombre y apellido:

> *"hablame en español latino, no con acento argentino. Si incorporaste el
> lenguaje argentino en la Torre, modificalo."*
> **"El voseo NO era de la Torre: llegó con el módulo de Percepción de la rama de
> Sebastián Zapata."** — commit `70e20c9`

Main corrigió 5 textos y dejó escrita la instrucción para este momento:
*"Si entra código nuevo de esa rama, revisar los textos visibles antes de
integrarlos."*

**Registro correcto**: tuteo (`tocas`, `espera`, `prefieres`) o impersonal
(`No es necesario…`, `Si solo se llena uno…`). **Nunca** `tocá`, `esperá`,
`tenés`, `armá`, `mirá`.

En la rama de origen **ya se barrieron los textos visibles** (commit final): los
tres que quedaban con voseo se corrigieron. Los **comentarios de código** quedan
en voseo a propósito, para no inflar el diff — main tomó esa misma decisión.

**Barrido antes de dar por integrado:**
```bat
rg -n "\b(arm|mir|toc|fij|us|prob|avis|eleg|and|dec|revis|pon|compar)á\b|\b(ten|pod|quer|sab|sos)és?\b" frontend/src/components/Percepcion*.tsx
```
Ojo con el falso positivo: `negati-vos` matchea `\bvos\b` mal escrito. Usá el
patrón de arriba, que es de imperativos.

### 0.2 El módulo NO es dueño de sus datos

`percepcion_*` las escribe **el worker externo**
(`Sentiment_Analisys_University`, repo aparte). La Torre las lee con un engine
**dedicado y de solo lectura** (`services/percepcion/db.py`, `query_only=ON`).
La única excepción es la curación manual, que usa un engine de escritura aparte.

**Consecuencia**: los modelos en `services/percepcion/models.py` son un ESPEJO.
No inventan defaults, no migran, no crean columnas. Si el worker suma una
columna, hay que espejarla a mano. Está documentado en cada modelo.

---

## 1. Qué es

Pestaña **"Termómetro Institucional"** (id interno `percepcion`, grupo
`institucional` en main). Mide el sentimiento de la comunidad UCN en redes
sociales sobre ~8.200 comentarios de 80 cuentas públicas, 2022-2026.

Seis secciones: Resumen, Alertas, Comparar, Conversación, Curación y Simulación.

---

## 2. El alcance real: main tiene una versión MUY anterior

| | main | rama de origen |
|---|---|---|
| archivos `percepcion*` | **15** | **75** |
| endpoints del router | 24 | **42** |
| servicios en `services/percepcion/` | 6 | **19** |
| tests | 1 archivo | **17 archivos** |

**Integrar NO es aplicar un puñado de commits: es traer el módulo completo.**
Main quedó en la versión de agosto; la rama tiene ~5 meses de evolución encima.

---

## 3. 🟢 Compatibilidad — VERIFICADA, y main ya preparó el terreno

### 3.1 Las dependencias existen

| Dependencia | En main |
|---|---|
| `backend/app/services/auth.py` | ✅ |
| `backend/app/services/panel_access.py` (`_TEAM_DAI_ONLY`, `is_panel_visible`) | ✅ |
| `backend/app/database.py` | ✅ |
| `frontend/src/lib/api.ts` | ✅ |

### 3.2 ⚠️ EL PANEL YA ESTÁ REGISTRADO EN MAIN — **NO lo agregues de nuevo**

Main tiene esto en `panel_access.py`, con un comentario que habla de esta misma
integración:

```python
# Termómetro Institucional (Percepción): sentimiento de la comunidad en redes. El id
# interno se mantiene en "percepcion" —el que usa la rama Integracion-FormulariosYUsoAPI
# de Sebastián Zapata— para que su próximo merge no duplique la entrada; lo que cambia
# acá es el RÓTULO y el grupo del nav (institucional, no indicadores).
{"id": "percepcion", "label": "Termómetro Institucional",
 "subtitle": "Sentimiento de la comunidad (redes)", "default_roles": _ALL_PRIVILEGED},
```

Y en `App.tsx` ya están **el import, el tipo, la entrada de nav y 3 renders**.

> **RESPETÁ EL RÓTULO Y EL GRUPO DE MAIN.** La rama de origen usa
> `label: "Percepción"` y `group: "indicadores"`; main usa
> `"Termómetro Institucional"` y `group: "institucional"`. **Main gana**: fue un
> cambio deliberado. Si traés el `App.tsx` de la rama entero, lo pisás.
>
> Lo mismo con `default_roles`: main usa `_ALL_PRIVILEGED`, la rama de origen
> otra cosa. **No lo bajes sin preguntar.**

### 3.3 El único archivo que hay que BORRAR

`frontend/src/components/PercepcionSintesis.tsx` — existe en main y **lo
reemplaza `PercepcionComparar.tsx`**. Verificado: su único consumidor es
`PercepcionPanel.tsx`, que se reemplaza en esta integración. Al reemplazar el
panel queda huérfano.

> `docs/PERCEPCION_CONTRATO_WORKER.md` **NO se toca**: main lo agregó DESPUÉS de
> que la rama se separó, así que "no está en la rama" no significa "lo borramos".
> Es la trampa clásica de una rama 402 commits atrás.

---

## 4. Pasos de integración

### 4.1 Copiar tal cual (63 archivos nuevos, sin conflictos)

**Backend — servicios** (`backend/app/services/percepcion/`): `calendario.py`,
`calidad.py`, `comunicacion.py`, `conflicto.py`, `critica.py`, `lexico.py`,
`ponderacion.py`, `postura.py`, `prediccion.py`, `resumen_llm.py`, `shock.py`,
`volatilidad.py`.

**Backend — datos**: `backend/app/data/percepcion_calendario_ucn.json` (109
eventos del calendario académico).

**Backend — tests** (17 archivos `backend/tests/test_percepcion*.py`).

**Frontend — componentes** (`frontend/src/components/`): `PercepcionAlertas`,
`PercepcionBaselines`, `PercepcionCalendarioDatos`, `PercepcionCalidad`,
`PercepcionComparar`, `PercepcionComunicacion`, `PercepcionConflicto`,
`PercepcionDominantes`, `PercepcionEnsayo`, `PercepcionFranjaEventos`,
`PercepcionResumen`, `PercepcionResumenSemanal`, `PercepcionRevision`,
`PercepcionShock`, `PercepcionSimulacion`, `PercepcionUI`, `PercepcionVolatilidad`.

**Scripts de raíz** (opcionales pero útiles): `_cargar_calendario_percepcion.py`
(⚠️ necesario, ver 4.4), `_verificar_alerta_percepcion.py`,
`_verificar_anomalias_percepcion.py`, `_reparar_origen_percepcion.py`,
`_exportar_dataset_percepcion.py`, `_evaluar_jueces_percepcion.py`.

### 4.2 Reemplazar (6 archivos que main ya tiene, en versión vieja)

```
backend/app/routers/percepcion.py               24 -> 42 endpoints
backend/app/services/percepcion/curacion.py
backend/app/services/percepcion/models.py
backend/app/services/percepcion/repository.py
backend/app/services/percepcion/schemas.py
backend/app/services/percepcion/eventos.py
backend/app/services/percepcion/db.py
backend/tests/test_percepcion.py
frontend/src/components/PercepcionPanel.tsx
frontend/src/components/PercepcionNube.tsx
frontend/src/components/PercepcionCuracion.tsx
frontend/src/lib/percepcion.ts
```

### 4.3 Modificar (2 archivos, cambios chicos)

**1. `backend/app/config.py`** — tres settings nuevos:
```python
percepcion_unidad_deteccion_semanas: int   # default 2 (quincena)
percepcion_credito_no_atribuible: float    # default 0.5
percepcion_neu_federacion_adverso: bool    # default True
```
Los tres están documentados en el archivo con sus mediciones. Son **reversibles
sin deploy**, a propósito: los tres mueven el número que ve el director.

**2. `backend/tests/test_metodologia.py`** — `"percepcion"` al set `expected` de
`PANEL_IDS`. Ver sección 6.

> **`main.py` NO se toca**: el router de percepción ya está registrado en main.

### 4.4 Cargar el calendario académico

El JSON versionado **no se aplica solo**: `calendario.cargar()` no la llama
ningún endpoint ni el arranque (a propósito — Cloud Run escala a cero y no
corresponde escribir en la base del worker en cada arranque en frío).

```bat
backend\.venv\Scripts\python.exe _cargar_calendario_percepcion.py            REM dry-run
backend\.venv\Scripts\python.exe _cargar_calendario_percepcion.py --aplicar
```
Esperado: 109 eventos, 13 disruptivos, 6 marcas de duelo.

> Esto ya causó un bug silencioso: el JSON declaraba 109 y la base tenía 102. Se
> descubrió mirando el panel, no los tests.

### 4.5 Configuración local

```
PERCEPCION_DATABASE_URL=sqlite:///RUTA/Sentiment_Analisys_University/percepcion_real.db
```
Si está vacío, cae a `OPERATIONAL_DATABASE_URL` (compat con la nube, donde el
worker escribe al mismo Postgres). **Ojo**: la operacional puede tener datos SEED
simulados; el módulo existe para NO mezclarlos.

---

## 5. Decisiones que hay que respetar (medidas, no opinadas)

| Decisión | Por qué |
|---|---|
| **El peso del tema va a los DOS numeradores y NUNCA al denominador** | Ponderar el denominador encoge la muestra: 78 → 61 semanas y sd 10,49 → 12,27. Sin ponderarlo, la serie es MENOS volátil (9,39) y no pierde una semana |
| **El crédito de un tema no atribuible vale la mitad; el daño no se descuenta** | Todo negativo es adverso. Un aplauso a la manada del campus no es mérito de la UCN, pero el reclamo sí es su problema |
| **NEU + cuenta `tipo='federacion'` → adverso** | Recall de adversos 72 % → 83 %, IC 95 % [+6,1, +18,8] sobre 237 anotaciones humanas re-pesadas. **Primera mejora demostrable del módulo** |
| **La regla NO usa la cuenta sola** | Sin restringir a NEU triplica los cruces graves: marca adversos a «❤️❤️❤️» y «Excelente comunicado!», anotados FAVORABLE por un humano |
| **La postura se lee del CORPUS, no de la tabla de hechos** | Necesita el tipo de cuenta y el grano de `percepcion_hecho_diario` no lo guarda. Agregarlo tocaría el esquema del worker |
| **La vara de predicción se mide sobre la serie del TABLERO** | Antes corría sobre el canónico mientras el tablero mostraba el ponderado: dos series distintas para la misma frase |
| **`_ruido_ponderado()` se reduce EXACTO al binomial con pesos 1** | Hay un test a 9 decimales. Es lo que permite cambiar de serie sin cambiar de instrumento |
| **La detección de anomalías corre sobre una serie CRUDA, no la dibujada** | Con `vida_media=30` los días están autocorrelacionados y un evento abrupto se reparte: el paro daba \|z\| máx 1,98 contra umbral 2,5 → CERO anomalías |
| **La serie se agrega por bloques anclados a una ÉPOCA FIJA** | Si dependieran del rango, cambiar el filtro reagruparía los días y la curva se movería sin que cambie un dato |
| **La franja de eventos usa el eje de la serie AGRUPADA** | Con la cruda, un paro quedaba corrido hasta 29 días con paso mensual |
| **`error_irreducible` NO es el techo de un pronóstico** | Mide ruido de muestreo (2,86); la cota real in-sample es 6,22. Confundirlos infla el margen aparente ~4× |
| **Las anotaciones de postura del AGENTE no sirven como ground truth** | 2.737 de 2.887 replican el TONO, no la postura. Filtrar `autor_tipo='humano'` **y** `origen_muestra='aleatorio'` |
| **La cola `estratificado` exige re-pesar** | Sin `repesar_por_estrato`, 50+50 anotaciones sobre un corpus 100/900 dan 30 % donde lo real es 14 % |

---

## 6. ⚠️ Rompe 1 test de `test_metodologia.py`

De los 6 que fallan en la rama de origen, **uno nombra `'percepcion'`**: el set
`expected` de `PANEL_IDS` en `test_catalogo_coincide_con_director_top_tab`.

**No es un bug**: los cuatro paneles «faltantes» (`percepcion`, `formularios`,
`manejo-wh`, `wh-consultas`) **SÍ están** en `DirectorTopTab` y en
`LEADERSHIP_NAV` de `App.tsx`. El desactualizado es el set literal del test.

> ⚠️ En main ese set tiene además `equipos`, `reqext`, `lakehouse`, `ingenieria`
> que la rama no tiene. **No los toques**: solo sumá el tuyo.

---

## 7. Verificación

```bat
REM ⚠️ desde backend/, NO desde la raíz: con otro rootdir pytest da 24 errores de colección
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q -k percepcion
.venv\Scripts\python.exe -m pytest tests/ -q

cd ..\frontend && npx tsc --noEmit && npm run build
```

Esperado: **504 tests de percepción en verde**.

Contra la base real, sin levantar el frontend:
```bat
backend\.venv\Scripts\python.exe -c "import os; os.environ.setdefault('PERCEPCION_DATABASE_URL','sqlite:///RUTA/percepcion_real.db'); from app.services.percepcion import repository; from app.services.percepcion.db import PercepcionSessionLocal; db=PercepcionSessionLocal(); r=repository.postura_institucional(db, dias=36500); print(r['n_comentarios'], [(d['postura'], d['pct']) for d in r['distribucion']])"
```
Esperado (corrida 2026-09-10): **8.174 comentarios · favorable 38,8 % · neutral
50,3 % · adverso 10,9 %**, y el tema adverso #1 es `organizacion_estudiantil`.

### Ver el panel sin VPN

El gate de perfiles llama `usuarios/me` → warehouse, que sin VPN devuelve 500 y
deja el perfil en `ucn_user`. Para inspeccionar visualmente:

1. Crear `frontend/src/app/preview-percepcion/page.tsx` que monte
   `<PercepcionPanel />` sin gate. **Sin guion bajo**: Next trata `_xxx` como
   privado y da 404.
2. `fetch('http://127.0.0.1:8011/auth/dev-login?email=TU_EMAIL@ucn.cl')` y
   guardar `session_token` + `user` en `localStorage`.
3. **Borrar la ruta al terminar.**

> Un **401** (no 404) en un endpoint nuevo = token vencido, no que el backend no
> tomó el cambio.

---

## 8. Pendientes conocidos

1. **Anotar postura con la cola `estratificado`**: ~105 anotaciones para llegar a
   50 adversos evaluables. Hoy hay 21 en la muestra sin sesgo, y con eso el IC del
   recall es [55-89 %]. Es lo único que destraba seguir calibrando la regla.
2. **La simulación está CERRADA para la pregunta A** (anticipar el índice), con
   dos evidencias y sin camino de datos (5,7 años esperando; mediana real de 9
   comentarios/semana). Lo vivo es el ensayo de comunicación. Ver
   `INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md` §0.
3. **Pregunta D (volatilidad por unidad) bloqueada por datos**: ninguna unidad
   llega a evidencia suficiente (medianas de 7-15 comentarios/semana contra 30).
4. **Descartado CON MEDICIÓN — no re-litigar sin datos nuevos**: activar los
   neutros adversos en el índice (trade-off, no mejora); `org.estudiantil →
   adverso` (53 % en cola dirigida contra 20 % en holdout); `centro_alumnos` en
   la regla de federación (lleva lo adverso al 21 % del corpus); el modelo
   poblacional de la fase 2.
5. **El worker es un repo aparte** (`Sentiment_Analisys_University`). Si su
   esquema cambia, hay que espejarlo en `models.py` y en `curacion.reagregar()`.

---

## 9. Relacionados

- `INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md` — el plan y su §0 con el
  veredicto de las cuatro preguntas.
- `STATUS.md`, entrada del 2026-09-10 — estado vivo con los números.
- `HANDOFF_MODULO_CALIDAD_DATOS.md` — el otro módulo prioritario.
- `HANDOFF_INTEGRACION.md` — **la guía maestra: leela primero.**
