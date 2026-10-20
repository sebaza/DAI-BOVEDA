# Termómetro Institucional — contrato de datos para el worker de Percepción

**Para:** Sebastián Zapata (worker `Sentiment_Analisys_University`)
**De:** DAI / Torre de Control
**Fecha:** 2026-08-07

---

## 1. Situación

El **Termómetro Institucional** ya está desplegado y funcionando en producción
(backend `torre-backend-00319-nb9`, frontend `torre-frontend-00224-dx4`). Es tu panel
de Percepción, integrado en la Torre bajo la sección **INSTITUCIONAL**.

**El panel se ve vacío porque las tablas `percepcion_*` existen y tienen cero filas.**
No es un error de conexión ni de permisos:

- Si las tablas **faltaran**, el repositorio lanzaría `OperationalError` y el panel
  mostraría un error. Está mostrando el *empty-state* limpio, que es el camino feliz
  con `count = 0`.
- Las 8 tablas las creó `Base.metadata.create_all` al arrancar el backend, porque tus
  modelos quedan registrados al importar `app/routers/percepcion.py`.

Falta, entonces, **que el worker escriba**. Este documento dice dónde y con qué forma.

---

## 2. Dónde escribir

| | |
|---|---|
| Instancia | Base operacional de la Torre — Cloud SQL, **PostgreSQL 17** |
| Proyecto y región | los del despliegue institucional (fuera de este repositorio) |
| DSN | en el gestor de secretos del despliegue (no se documenta aquí) |

La Torre resuelve la base de percepción así (`app/services/percepcion/db.py`):

```python
_url = settings.percepcion_database_url or settings.operational_database_url
```

**`PERCEPCION_DATABASE_URL` NO está seteada en Cloud Run** (lo verifiqué), así que hoy
la Torre lee de la operacional. Es decir: **el worker debe escribir los `percepcion_*`
en la base operacional.**

Si prefieres una base aparte, se puede: hay que setear `PERCEPCION_DATABASE_URL` en el
servicio `torre-backend` apuntando a ella. Avísanos y lo hacemos — pero entonces las
tablas hay que crearlas ahí (`create_all` solo las crea donde apunte la operacional).

Alberto gestiona el acceso al secreto / a la instancia; solicítaselo a él.

---

## 3. Lo mínimo para encender el panel

No es necesario poblar las 8 tablas. El reparto real, sacado de las funciones del
repositorio que sirven cada endpoint:

| Endpoint | Tablas que lee |
|---|---|
| `/percepcion/resumen` | `percepcion_hecho_diario` |
| `/percepcion/evolucion` | `percepcion_hecho_diario` |
| `/percepcion/por-tema` | `percepcion_hecho_diario` |
| `/percepcion/por-unidad` | `percepcion_hecho_diario` |
| `/percepcion/emociones` | `percepcion_hecho_diario` |
| `/percepcion/sintesis` | `percepcion_hecho_diario` |
| `/percepcion/anomalias` | `percepcion_hecho_diario` |
| `/percepcion/filtros` | `percepcion_hecho_diario` |
| `/percepcion/eventos` | `percepcion_hecho_diario` + `percepcion_evento` |
| `/percepcion/comentarios` | `percepcion_cuenta` → `percepcion_publicacion` → `percepcion_comentario` → `percepcion_score` |
| `/percepcion/nube` | idem anterior |

**`percepcion_hecho_diario` sola enciende 9 de los 11 endpoints** — todo el Tablero, la
Síntesis, la evolución, los filtros y las anomalías. La cadena
cuenta→publicación→comentario→score hace falta solo para la lista de comentarios y la
nube de palabras. `percepcion_evento` es la capa de hitos.

`percepcion_tema_custom` y `percepcion_correccion` **las escribe la Torre** (curación
manual); el worker las lee.

---

## 4. Grano y semántica de `percepcion_hecho_diario`

Una fila por **(fecha, campus, facultad, departamento, tema)** con las sumas crudas. La
Torre calcula índice, distribución, evolución y emociones al vuelo con cualquier filtro
— no guardes agregados ya filtrados.

**Índice** (`repository._indice`), en 0–100:

```
indice = clamp(0, 100,  50 + 50 * (num_pos - num_neg) / den)
```

donde `(num_pos, num_neg, den)` salen de interpolar por el slider "peso por likes"
α ∈ [0,1] (`repository._pick`):

```
num_pos = (1-α)*suma_pos      + α*peso_pos
num_neg = (1-α)*suma_neg      + α*peso_neg
den     = (1-α)*n_comentarios + α*suma_peso
```

Es decir, cada fila necesita **los dos juegos de sumas**:

- **sin ponderar** (cada comentario pesa 1): `suma_pos`, `suma_neg`, `n_comentarios`
- **ponderadas por likes**: `peso_pos`, `peso_neg`, `suma_peso`

Si solo se llena uno, el slider deja de tener sentido en un extremo.

`suma_ganadora` alimenta la **confianza** junto con `n_comentarios`:

```
confianza = min(1, n/N_MIN_CONFIANZA) * (suma_ganadora / n)
```

`emociones` es un **JSON `{emocion: conteo}`** dentro de la propia fila de hecho (no se
recalcula desde los comentarios).

### Vocabularios cerrados

`tema` — claves canónicas (`ETIQUETAS_TEMA`):
`academico`, `matricula_aranceles`, `infraestructura`, `bienestar_salud`,
`organizacion_estudiantil`, `eventos`, `tramites`, `otros`.

`emocion` — claves de `ETIQUETAS_EMOCION`:
`joy`, `sadness`, `anger`, `fear`, `surprise`, `humor_ironia`, `empatia`,
`sin_emocion`. (`disgust` y `others` se siguen aceptando por compatibilidad histórica,
rotulados como "histórico".)

`percepcion_score.sentimiento` — `pos` / `neu` / `neg`.

---

## 5. Esquema exacto que existe HOY en producción

**Ojo con esto:** `create_all` **solo crea tablas que faltan; nunca hace ALTER**. Si tu
worker espera una columna que este espejo no tiene, tu escritura va a fallar contra la
tabla ya creada. Compara antes de correr.

```sql
CREATE TABLE percepcion_hecho_diario (
	id SERIAL NOT NULL,
	fecha DATE NOT NULL,
	campus VARCHAR(60),
	facultad VARCHAR(160),
	departamento VARCHAR(160),
	tema VARCHAR(40),
	n_comentarios INTEGER NOT NULL,
	n_pos INTEGER NOT NULL,
	n_neu INTEGER NOT NULL,
	n_neg INTEGER NOT NULL,
	suma_peso FLOAT NOT NULL,
	peso_pos FLOAT NOT NULL,
	peso_neg FLOAT NOT NULL,
	suma_pos FLOAT NOT NULL,
	suma_neg FLOAT NOT NULL,
	suma_ganadora FLOAT NOT NULL,
	emociones JSON,
	PRIMARY KEY (id)
);
CREATE INDEX ix_percepcion_hecho_diario_campus ON percepcion_hecho_diario (campus);
CREATE INDEX ix_percepcion_hecho_diario_departamento ON percepcion_hecho_diario (departamento);
CREATE INDEX ix_percepcion_hecho_diario_facultad ON percepcion_hecho_diario (facultad);
CREATE INDEX ix_percepcion_hecho_diario_fecha ON percepcion_hecho_diario (fecha);
CREATE INDEX ix_percepcion_hecho_diario_tema ON percepcion_hecho_diario (tema);

CREATE TABLE percepcion_cuenta (
	id SERIAL NOT NULL,
	handle VARCHAR(120) NOT NULL,
	nombre VARCHAR(200) NOT NULL,
	tipo VARCHAR(40) NOT NULL,
	campus VARCHAR(60),
	facultad VARCHAR(160),
	departamento VARCHAR(160),
	carrera VARCHAR(160),
	PRIMARY KEY (id)
);
CREATE INDEX ix_percepcion_cuenta_handle ON percepcion_cuenta (handle);

CREATE TABLE percepcion_publicacion (
	id SERIAL NOT NULL,
	cuenta_id INTEGER NOT NULL,
	external_id VARCHAR(80) NOT NULL,
	fecha_publicacion TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	tipo VARCHAR(20) NOT NULL,
	caption TEXT,
	n_comentarios INTEGER NOT NULL,
	n_likes INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX ix_percepcion_publicacion_cuenta_id ON percepcion_publicacion (cuenta_id);
CREATE INDEX ix_percepcion_publicacion_external_id ON percepcion_publicacion (external_id);
CREATE INDEX ix_percepcion_publicacion_fecha_publicacion ON percepcion_publicacion (fecha_publicacion);

CREATE TABLE percepcion_comentario (
	id SERIAL NOT NULL,
	publicacion_id INTEGER NOT NULL,
	external_id VARCHAR(80) NOT NULL,
	autor_hash VARCHAR(64) NOT NULL,
	texto TEXT NOT NULL,
	fecha_comentario TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	idioma VARCHAR(8) NOT NULL,
	n_likes INTEGER NOT NULL,
	tema VARCHAR(40),
	tema_confianza FLOAT,
	PRIMARY KEY (id)
);
CREATE INDEX ix_percepcion_comentario_autor_hash ON percepcion_comentario (autor_hash);
CREATE INDEX ix_percepcion_comentario_external_id ON percepcion_comentario (external_id);
CREATE INDEX ix_percepcion_comentario_fecha_comentario ON percepcion_comentario (fecha_comentario);
CREATE INDEX ix_percepcion_comentario_publicacion_id ON percepcion_comentario (publicacion_id);
CREATE INDEX ix_percepcion_comentario_tema ON percepcion_comentario (tema);

CREATE TABLE percepcion_score (
	id SERIAL NOT NULL,
	comentario_id INTEGER NOT NULL,
	modelo VARCHAR(120) NOT NULL,
	sentimiento VARCHAR(8) NOT NULL,
	prob_pos FLOAT NOT NULL,
	prob_neu FLOAT NOT NULL,
	prob_neg FLOAT NOT NULL,
	emocion VARCHAR(20),
	prob_emocion FLOAT,
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_percepcion_score_comentario_id ON percepcion_score (comentario_id);
CREATE INDEX ix_percepcion_score_sentimiento ON percepcion_score (sentimiento);

CREATE TABLE percepcion_evento (
	id SERIAL NOT NULL,
	nombre VARCHAR(200) NOT NULL,
	tipo VARCHAR(40) NOT NULL,
	fecha_inicio DATE NOT NULL,
	fecha_fin DATE,
	descripcion TEXT,
	ambito VARCHAR(120),
	PRIMARY KEY (id)
);
CREATE INDEX ix_percepcion_evento_fecha_inicio ON percepcion_evento (fecha_inicio);
CREATE INDEX ix_percepcion_evento_tipo ON percepcion_evento (tipo);

-- Escritas por la TORRE (curación manual), leídas por el worker:

CREATE TABLE percepcion_tema_custom (
	id SERIAL NOT NULL,
	clave VARCHAR(40) NOT NULL,
	etiqueta VARCHAR(120) NOT NULL,
	keywords JSON,
	creado_en TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_percepcion_tema_custom_clave ON percepcion_tema_custom (clave);

CREATE TABLE percepcion_correccion (
	id SERIAL NOT NULL,
	comentario_id INTEGER NOT NULL,
	campo VARCHAR(20) NOT NULL,          -- "sentimiento" | "emocion"
	valor_original VARCHAR(20),
	valor_nuevo VARCHAR(20) NOT NULL,
	justificacion TEXT,
	autor VARCHAR(160),
	creado_en TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id)
);
CREATE INDEX ix_percepcion_correccion_comentario_id ON percepcion_correccion (comentario_id);
```

---

## 6. Regla dura: nada de datos simulados en producción

El *empty-state* del panel sugiere `python -m percepcion.cli simular --dias 90`. **Eso
no se corre contra producción.** Este tablero lo miran el Director y el Vicerrector, y
números simulados ahí son indistinguibles de percepción real de la comunidad. El
`simular` es para tu entorno de desarrollo.

---

## 7. Cómo verificar que quedó

1. `select count(*) from percepcion_hecho_diario;` en la base operacional → > 0.
2. Entrar a la Torre → **INSTITUCIONAL → Termómetro Institucional**. El panel debería
   mostrar índice y confianza en vez del *empty-state*, y los selectores de Sede /
   Facultad / Departamento / Tema deberían poblarse solos (salen de `/percepcion/filtros`,
   que lee los distintos de `percepcion_hecho_diario`).
3. La ventana **no** es un problema: `_rango` ancla el `hasta` a la fecha MÁXIMA de
   `percepcion_hecho_diario` y retrocede `dias`, así que aunque cargues datos viejos el
   panel los encuentra igual.

   Si hay filas y el índice igual sale vacío, el sospechoso es **`den <= 0`**: con
   `n_comentarios`, `suma_peso` y las sumas en cero, `_indice` devuelve `None` por
   división nula. Es el modo de falla típico de escribir la fila del hecho con las
   dimensiones pobladas pero los agregados sin llenar.

---

## 8. Nota sobre la integración

La Torre integró **solo Percepción** de tu rama `Integracion-FormulariosYUsoAPI`.
Formularios y Uso de API quedan fuera por decisión de Alberto (2026-08-07).

El código de Percepción está copiado **tal cual** de `e87e5ea`. La **única** divergencia
deliberada es el rótulo del encabezado del panel ("Termómetro Institucional", para que
coincida con el nombre de la pestaña). El **id interno se mantiene en `percepcion`** —el
tuyo— justamente para que tu próximo merge no duplique la entrada; lo que cambió es el
rótulo y el grupo del nav (`institucional` en vez de `indicadores`).

Hay una segunda divergencia, chica: **cinco textos visibles pasaron de voseo a español
neutro** (`Probá`→`Prueba`, `Escribí`→`Escribe`, `usá`→`usa`, `Elegí`→`Elige`,
`podés`→`puedes`). Es una regla de Alberto para toda la Torre — es una herramienta
institucional de la UCN y el registro tiene que ser neutro. **Tus comentarios de código
quedaron intactos a propósito**, para no inflar el diff de tu próximo merge.

Tu rama sigue siendo tuya: desde la Torre no la modificamos. Si ves algo mal en el
código integrado, avísanos y lo corregimos en tu rama, no río abajo.
