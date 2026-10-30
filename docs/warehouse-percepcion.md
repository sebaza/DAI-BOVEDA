# Percepción en el almacén institucional (fase A3)

El esquema `percepcion` del almacén (Postgres aparte, solo lo leen ingenieros DAI) pasa a ser la
base PRIMARIA de Percepción. Tiene las mismas tablas que hoy tiene la Bóveda. El esquema `boveda`
(módulos, listas de acceso, administradores, auditoría) **no se mueve**: sigue en
`BOVEDA_DATABASE_URL`.

Qué cambia en los datos al cargar:

- `texto` y `caption` se copian tal cual, **cifrados** (`enc:<versión>:...`). La carga se niega si
  alguna fila no es un cifrado auténtico (salvo `--permitir-claro`).
- `percepcion_comentario.autor_hash` se reemplaza por `HMAC-SHA256(PERCEPCION_CLAVE_ID, "autor" NUL valor)`.
  Es determinista: los conteos de autores distintos (umbrales anti-PII) no cambian.
- `percepcion_comentario.external_id` se reemplaza por `HMAC-SHA256(PERCEPCION_CLAVE_ID, "comentario_ext" NUL valor)`
  (64 caracteres hex, caben en `String(80)`): con el id original se llega al autor público del
  comentario. Ningún endpoint de lectura lo usa. El `external_id` de publicaciones y el `handle` de
  cuentas (datos institucionales públicos) no se tocan.
- Se escriben dos marcas en `percepcion_meta`: `autor_seudonimizado=true` y
  `ext_comentario_seudonimizado=true`. A partir de ahí `sincronizar_percepcion_worker.py` seudonimiza
  `autor_hash` y `external_id` de los comentarios **nuevos**, y compara la clave natural del worker
  ya seudonimizada contra la del almacén (así detecta lo ya cargado y los conflictos igual que antes;
  una re-ejecución inserta 0). Con solo una de las dos marcas, o con las marcas y sin
  `PERCEPCION_CLAVE_ID`, la sincronización se niega antes de escribir.
- `scripts/migrar_percepcion_postgres.py` se niega (con y sin `--reemplazar`) a cargar un destino
  marcado: copiaría identificadores crudos. Los únicos caminos que insertan comentarios son esa
  migración y la sincronización; el resto de los scripts solo actualiza filas existentes.

## Pasos (en este orden)

1. **Pedir al DBA** dos roles con `LOGIN` y contraseña propia, y un usuario dueño del esquema
   `percepcion` en el almacén:
   - *escritor*: procesos Python (sincronización, derivados, subtemas, resumen semanal) y la Curación local.
   - *lector*: la API Node (`wh-api`), solo lectura.
   - *dueño*: crea las tablas (la carga) y aplica los permisos. Los nombres aún no están definidos.
2. **Variables de entorno** (solo nombres; los valores no van en archivos del repositorio):
   - `PERCEPCION_ADMIN_DATABASE_URL`: URL del dueño de la base **actual** de la Bóveda (origen).
   - `PERCEPCION_WH_DATABASE_URL`: URL del dueño en el **almacén** (destino).
   - `PERCEPCION_WH_ADMIN_DATABASE_URL`: URL del dueño en el almacén para los permisos (puede ser la misma).
   - `PERCEPCION_CLAVE_TEXTO` y `PERCEPCION_CLAVE_ID`: **las mismas** que usa hoy la Bóveda. No se
     pierden ni se rotan a la ligera: sin `PERCEPCION_CLAVE_TEXTO` el texto es irrecuperable, y cambiar
     `PERCEPCION_CLAVE_ID` rompería la coherencia de los autores ya cargados.
3. **Referencia previa** (antes de tocar nada), para comparar después:
   ```
   backend\.venv\Scripts\python.exe -I scripts/verificar_paridad_percepcion.py --guardar-referencia ref.json --referencia-desde-postgres <URL de la Bóveda actual>
   ```
   `ref.json` trae lo que devuelven los endpoints de Curación (texto): es local, bórralo al terminar.
4. **Ensayo** (no escribe nada; verifica claves, cifrado y largos, y muestra qué se copiaría):
   ```
   backend\.venv\Scripts\python.exe -I scripts/publicar_warehouse_percepcion.py --dry-run
   ```
   Si informa texto sin cifrar, primero `scripts/cifrar_textos_percepcion.py` sobre el origen.
5. **Carga** (una sola transacción; el origen se lee en una instantánea REPEATABLE READ de solo
   lectura. Antes de empezar se niega si origen y destino son la misma base: normaliza host, puerto
   y loopback, y consulta al servidor. Después valida conteos por tabla, suma y máximo de `id`,
   no nulos de `texto`/`caption`, autores y `external_id` distintos, descifra TODAS las filas de
   `texto`/`caption` del destino y comprueba las dos marcas; si algo falla, revierte):
   ```
   backend\.venv\Scripts\python.exe -I scripts/publicar_warehouse_percepcion.py
   ```
   Si el destino ya tiene datos se niega; `--reemplazar` los vacía y recarga (sobrescribe lo escrito
   en el almacén desde la carga anterior). Códigos de salida: 0 ok, 1 falla, 2 configuración.
6. **Permisos** (solo `GRANT`; no crea roles ni contraseñas):
   ```
   backend\.venv\Scripts\python.exe -I scripts/otorgar_permisos_warehouse_percepcion.py --rol-escritor <ESCRITOR> --rol-lector <LECTOR>
   ```
   Se puede repetir sin riesgo. `--solo-imprimir` muestra el SQL (`backend/sql/004_percepcion_warehouse.sql`).
   Debe ejecutarlo el **dueño del esquema** (o un miembro de ese rol, o un superusuario): se niega en
   otro caso. Los permisos por defecto de tablas futuras se fijan `FOR ROLE <dueño del esquema>`, o
   sea valen para lo que cree ese rol, no para quien corra el script.
7. **Cambiar las URLs de la Bóveda** al almacén, con el rol *escritor*:
   `PERCEPCION_DATABASE_URL`, `PERCEPCION_PROCESO_DATABASE_URL` y `PERCEPCION_ADMIN_DATABASE_URL`.
   Reiniciar la Bóveda local. Las claves de cifrado siguen en la Bóveda, nunca en el almacén.
8. **Verificar** contra la referencia del paso 3:
   ```
   backend\.venv\Scripts\python.exe -I scripts/verificar_paridad_percepcion.py --contra-referencia ref.json --postgres <URL del almacén con el rol escritor>
   ```
   Debe terminar con "Todo coincide" (las diferencias de orden entre empates se informan aparte).
   Luego `scripts/sincronizar_percepcion_worker.py --dry-run` debe mostrar
   "destino marcado como almacén". Borrar `ref.json`.
9. **Avisar a quien construye `wh-api`** que lea con el rol *lector* (el esquema es `percepcion`).

## Reversa

Volver a poner las tres URLs de `PERCEPCION_*` de la Bóveda en la base anterior y reiniciar. La base
local no se toca nunca: es solo lectura en la carga. Todo lo que se haya escrito en el almacén
después del paso 7 (correcciones, subtemas renombrados, resúmenes) **no** vuelve a la base anterior.
Para repetir la carga desde cero basta `--reemplazar`.

## Columnas que NO son `autor_hash` y pueden identificar o delatar contenido

La carga no las modifica; imprime su conteo para que se decida. Quien lee el almacén las ve en claro:

| Columna | Qué es |
|---|---|
| `percepcion_correccion.autor` | correo del administrador que revisó (no es un comentarista) |
| `percepcion_correccion.justificacion` | texto libre de administradores; podría citar comentarios |
| `percepcion_subtema.renombrado_por` / `etiqueta_manual` | correo y nombre escritos por un administrador |
| `percepcion_subtema.terminos` | términos frecuentes del grupo (ya con umbral anti-PII) |
| `percepcion_comentario_token.token` | palabras de cada comentario, sin orden y **sin cifrar** |
| `percepcion_resumen_semanal.texto` | narrativa del LLM, agregada y en claro |
| `percepcion_publicacion.external_id`, `percepcion_cuenta.handle` | datos públicos de cuentas institucionales (se dejan tal cual) |

## Supuestos sobre el almacén

- Es PostgreSQL con driver `psycopg` y permite `CREATE SCHEMA`/`CREATE TABLE` al dueño.
- No corre ningún backend Python allí (ruta A): la Bóveda local y los scripts se conectan a él.
- El *escritor* es un solo rol para API, Curación y scripts. Se pierde la separación actual
  `boveda_app` (sin lectura de `texto`) frente a `boveda_proceso`; se compensa porque el texto está
  cifrado y la clave solo existe en la Bóveda.
- El *escritor* no tiene DDL: `db.py` intenta crear tablas/columnas al importarse y falla en silencio;
  las tablas o columnas nuevas las crea el dueño (la carga con `--reemplazar` o un `ALTER` del DBA).
- La sincronización reinicia secuencias con `setval`: por eso el escritor recibe `UPDATE` sobre secuencias.
- `percepcion_meta` es una tabla propia de la Bóveda; el worker no la conoce.
