---
name: percepcion-terminos-y-anomalias
description: Termómetro — léxico de términos críticos (paro/toma) y detección de anomalías semanal; por qué la versión anterior no veía el paro
metadata:
  type: project
---

Dos features del Termómetro UCN, ambas calibradas contra `percepcion_real.db`
(2.790 comentarios, 2022-04-12 → 2026-08-05) usando el evento cargado
**"Paro estudiantil 2026-06-03 → 2026-07-03"** como ground truth.

## 1. Términos bajo vigilancia (`services/percepcion/lexico.py`)

5 familias: paro, toma, movilización, petitorio, asamblea. `GET /percepcion/terminos`
→ bloque "Señales bajo vigilancia" en Síntesis (va PRIMERO, antes de "Qué cambió").

**Por qué**: el clasificador tiene 8 temas y el conflicto no tiene caja propia. El
**21/04/2026, seis semanas antes del paro**, hay en un solo día rumor de paro
("al final no caxe, hay paro o no"), rechazo ("No yapo no tiren paro" [NEG]),
petitorios de seguridad y convocatoria a asamblea. No se veía en ningún lado.

**Reglas del léxico (todas aprendidas contra el corpus, no inventadas)**:
- **Lista explícita de formas, nunca regex laxa.** `par[oa]s?` da 153 matches y casi
  todos son **"para"** (preposición). Este es EL error a no repetir.
- **Palabra ambigua → solo en frase.** "tomar" es casi siempre "tomar asignaturas";
  el sustantivo "toma"/"tomas" sí cuenta solo.
- **Colapsar repeticiones de 3+** antes de matchear: "tomaaaaaa" y "marchaaa" están
  literalmente en el corpus. Umbral 3, no 2 (rompería "carro", "llave", "arroz").
- **Frases que secuestran una forma se borran del texto** (`FRASES_AMBIGUAS`):
  "marcha blanca", "poner en marcha", "toma nota".
- `FRASES_SCRAPER` vive en `lexico.py` y `repository` la importa: una sola lista.

**No toca el índice** (decisión del usuario): la fórmula canónica queda comparable
con lo ya presentado. El humor (`humor_ironia`) se separa pero se muestra.

**Hallazgo**: el índice de las familias críticas es **21-28** cuando el global es
**65-67**. La señal está en la CARGA, no en el volumen (45 de 2.790 = 1.6%).

## 2. Anomalías semanales (`repository._deteccion_semanal`)

**El problema medido**: la versión anterior daba **cero anomalías en toda la ventana
del paro** (|z| máx 1.98 vs umbral 2.5), y las 3 que marcaba en 4 años caían fuera
de todo evento. Causa: detectaba sobre la MISMA serie trailing que se grafica — con
`vida_media=30` cada punto ya promedia 30 días, los días están autocorrelacionados y
un evento abrupto se reparte. El `PISO_SD_ANOMALIA` frenaba falsos positivos Y
verdaderos: mismo síntoma, misma causa.

**Ahora**: se dibuja suave y se **detecta crudo**, por SEMANA (mediana 5 comentarios/día
hace inútil el z diario), con baseline **mediana + MAD** y tres señales con severidad
graduada 0..1 + `motivos`. `es_anomalia` se conserva por compatibilidad.

**Hipótesis que los datos DESCARTARON** (no reintentarlas):
- **Volumen**: durante el paro BAJA (28.5 → 22.9 → 22.5 com/día); el pico de 107 del
  09/06 es menor que el de 120 del 14/04, sin relación con el paro.
- **Menciones críticas en bruto**: 5.1% / 5.7% / 5.4%. Plano.
- **El índice SUBE durante el paro** (51.9 → 67): las cuentas de federación reciben
  comentarios de apoyo. Un índice de sentimiento solo jamás lo iba a detectar.

**Jerarquía honesta**: `terminos` es el disparador real (crit_neg mediana 0 en 125
semanas, ≥2 en solo 5). `negatividad` es APOYO — el 19.4% del 29/06 da z robusto
**1.51** contra su baseline, no discrimina sola. El `indice` es **asimétrico**: solo
la caída dispara (tratando ambos sentidos por igual saltaban 3 semanas en las que la
percepción MEJORÓ). La persistencia **agrava pero no es requisito**: el 20/04 fue una
semana suelta y era la antesala.

`MIN_N_SEMANA = N_MIN_CONFIANZA` (30): sería incoherente que la síntesis marque
"muestra insuficiente" y la detección alarme con esa misma semana.

**Resultado**: paro detectado (22/06 sev 0.65, 29/06 sev 0.90; 4 de 5 semanas con
severidad > 0), antesala **20/04 con severidad 1.00**, ruido **6/125 semanas (4.8%)**.

## Verificación

```
backend\.venv\Scripts\python.exe -m unittest tests.test_percepcion   # 106 tests
backend\.venv\Scripts\python.exe _verificar_anomalias_percepcion.py  # calibración
```

El script de calibración es **solo lectura** (`mode=ro`) y contrasta contra los eventos
de `percepcion_evento`. Ojo con el criterio de ruido: medirlo sobre el AÑO del evento
cuenta las señales verdaderas como ruido — el denominador es el histórico completo.

Base del worker: `C:\Users\sezad\Documents\GitHub\Sentiment_Analisys_University\percepcion_real.db`.
Para verlo en la UI local hay que entrar por **`127.0.0.1:8001`, no `localhost:8001`**
(CORS del backend). Ver [[percepcion-dev-login-local]] y [[percepcion-filtro-fecha-comentarios]].

**Deuda detectada, NO arreglada**: `curacion.reagregar()` borra la columna `origen`
de `percepcion_hecho_diario` (existe en la base real, falta en `models.py`), y las 376
correcciones humanas de `percepcion_correccion` no las lee ningún endpoint.
