"""Modelos ORM (SOLO LECTURA en la Torre) del feature Percepción.

Reflejan el esquema que ESCRIBE el worker externo (Sentiment_Analisys_University,
paquete `percepcion.db.models`). Los nombres de tabla y columnas DEBEN coincidir
con los del worker — el worker es el dueño del esquema. Se importan desde
app/routers/percepcion.py para registrarse en Base.metadata antes de create_all.

La tabla de HECHOS (`percepcion_hecho_diario`) es de grano fino: una fila por
(fecha, sede, facultad, departamento, tema) con las sumas crudas. La Torre calcula
índice/distribución/evolución/emociones al vuelo con cualquier filtro.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# Ingesta UCN vs. ingesta de cuentas ajenas (prensa, etc.). Todo lo anterior a la
# migración del worker es UCN por definición, por eso el default es "interno" y no
# NULL: un NULL obligaría a que CADA consulta del dashboard lo contemple.
ORIGEN_INTERNO = "interno"
ORIGEN_EXTERNO = "externo"


class PercepcionCuenta(Base):
    __tablename__ = "percepcion_cuenta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(120), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(40))
    campus: Mapped[str | None] = mapped_column(String(60))
    facultad: Mapped[str | None] = mapped_column(String(160))
    departamento: Mapped[str | None] = mapped_column(String(160))
    carrera: Mapped[str | None] = mapped_column(String(160))
    # --- Columnas que el worker agregó y a la Torre le faltaban (ver nota de módulo) ---
    unidad_cod: Mapped[str | None] = mapped_column(String(40))   # cod_unidad_organica
    activa: Mapped[bool | None] = mapped_column(Boolean)
    creada_en: Mapped[datetime | None] = mapped_column(DateTime)
    origen: Mapped[str | None] = mapped_column(String(20), index=True)


class PercepcionHechoDiario(Base):
    __tablename__ = "percepcion_hecho_diario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    campus: Mapped[str | None] = mapped_column(String(60), index=True)
    facultad: Mapped[str | None] = mapped_column(String(160), index=True)
    departamento: Mapped[str | None] = mapped_column(String(160), index=True)
    tema: Mapped[str | None] = mapped_column(String(40), index=True)

    n_comentarios: Mapped[int] = mapped_column(Integer, default=0)
    n_pos: Mapped[int] = mapped_column(Integer, default=0)
    n_neu: Mapped[int] = mapped_column(Integer, default=0)
    n_neg: Mapped[int] = mapped_column(Integer, default=0)

    # Sumas PONDERADAS por likes (likes ON) y SIN ponderar (likes OFF).
    suma_peso: Mapped[float] = mapped_column(Float, default=0.0)
    peso_pos: Mapped[float] = mapped_column(Float, default=0.0)
    peso_neg: Mapped[float] = mapped_column(Float, default=0.0)
    suma_pos: Mapped[float] = mapped_column(Float, default=0.0)
    suma_neg: Mapped[float] = mapped_column(Float, default=0.0)
    suma_ganadora: Mapped[float] = mapped_column(Float, default=0.0)

    emociones: Mapped[dict | None] = mapped_column(JSON)
    # Se hereda de la CUENTA. El worker agrupa por (fecha, origen, campus,
    # facultad, depto, tema) — la reagregación de la Torre tiene que espejarlo o
    # los hechos internos y externos se funden y ya no hay cómo separarlos.
    #
    # SIN `default=` a propósito. Con un default, SQLAlchemy incluye la columna en
    # TODO INSERT aunque no se le pase valor, y eso reventaba contra una base
    # anterior a la migración del worker ("table ... has no column named origen").
    # Los defaults los pone el worker, que es el dueño del esquema; este modelo es
    # un espejo y no debe inventar valores.
    origen: Mapped[str | None] = mapped_column(String(20), index=True)


class PercepcionPublicacion(Base):
    """Publicación (post/reel) de una cuenta. Read-only espejo del worker.

    Solo se leen las columnas que el dashboard usa (caption/fecha para el detalle
    de comentarios recientes). El worker es dueño del esquema completo.
    """

    __tablename__ = "percepcion_publicacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(Integer, index=True)
    external_id: Mapped[str] = mapped_column(String(80), index=True)
    fecha_publicacion: Mapped[datetime] = mapped_column(DateTime, index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    # deferred: es dato crudo. Una carga ORM de la entidad (`db.get`, `select(P)`) no lo
    # pide al servidor salvo que se acceda; el rol de la API no tiene SELECT sobre él.
    caption: Mapped[str | None] = mapped_column(Text, deferred=True)
    n_comentarios: Mapped[int] = mapped_column(Integer, default=0)
    n_likes: Mapped[int] = mapped_column(Integer, default=0)


class PercepcionComentario(Base):
    """Comentario SIN PII (autor solo como hash). Read-only espejo del worker.

    El texto se expone en el dashboard (dato público de cuentas públicas), pero
    NUNCA el autor: `autor_hash` es irreversible y no se devuelve al front.
    """

    __tablename__ = "percepcion_comentario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publicacion_id: Mapped[int] = mapped_column(Integer, index=True)
    external_id: Mapped[str] = mapped_column(String(80), index=True)
    autor_hash: Mapped[str] = mapped_column(String(64), index=True)
    # deferred: es dato crudo (ver `caption`). Se lee solo con el rol privilegiado.
    texto: Mapped[str] = mapped_column(Text, deferred=True)
    fecha_comentario: Mapped[datetime] = mapped_column(DateTime, index=True)
    idioma: Mapped[str] = mapped_column(String(8), default="es")
    n_likes: Mapped[int] = mapped_column(Integer, default=0)
    tema: Mapped[str | None] = mapped_column(String(40), index=True)
    tema_confianza: Mapped[float | None] = mapped_column(Float)
    # Por qué se retuvo un comentario de una cuenta EXTERNA (queda NULL en la
    # ingesta UCN, donde se guarda todo).
    motivo_relevancia: Mapped[str | None] = mapped_column(String(20), index=True)


class PercepcionScore(Base):
    """Resultado del scoring por comentario. Read-only espejo del worker."""

    __tablename__ = "percepcion_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comentario_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    modelo: Mapped[str] = mapped_column(String(120))
    sentimiento: Mapped[str] = mapped_column(String(8), index=True)
    prob_pos: Mapped[float] = mapped_column(Float, default=0.0)
    prob_neu: Mapped[float] = mapped_column(Float, default=0.0)
    prob_neg: Mapped[float] = mapped_column(Float, default=0.0)
    emocion: Mapped[str | None] = mapped_column(String(20))
    prob_emocion: Mapped[float | None] = mapped_column(Float)
    # NOT NULL en el worker, nullable acá y SIN default: la Torre nunca inserta
    # scores, solo los actualiza. Ver la nota de `origen` sobre por qué un default
    # en un modelo-espejo es peligroso.
    scored_en: Mapped[datetime | None] = mapped_column(DateTime)


class PercepcionTemaCustom(Base):
    """Tema creado a mano desde la Torre (curación). La Torre lo escribe; el worker
    lo lee para clasificar. Base compartida con el worker (percepcion_real.db)."""

    __tablename__ = "percepcion_tema_custom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    etiqueta: Mapped[str] = mapped_column(String(120))
    keywords: Mapped[list | None] = mapped_column(JSON)
    creado_en: Mapped[datetime | None] = mapped_column(DateTime)


# Quién revisó. Una anotación de persona y una de agente LLM NO valen lo mismo, y
# mezclarlas en un solo promedio esconde justo lo que hay que auditar: en la base
# real, 375 de 376 filas venían de dos pasadas de un agente (`auditoria-contextual-v4`,
# `auditoria-v9`) que movían el 90% y el 81% de sus fallos hacia POS.
AUTOR_HUMANO = "humano"
AUTOR_AGENTE = "agente"

# De qué cola salió el caso. Sin esto no se puede corregir el sesgo de selección:
# la cola por defecto ordena por DUDA del modelo, así que el acuerdo medido sobre
# ella es un piso pesimista y no el valor real.
MUESTRA_DUDA = "duda"
MUESTRA_RECIENTE = "reciente"
MUESTRA_ALEATORIA = "aleatorio"
# Cola dirigida a CANDIDATOS A ADVERSO. Existe por un cuello de botella medido: de
# las 150 anotaciones humanas de postura, solo **21 son adversos**, y con 21 casos
# no se puede calibrar ese lado de la regla — es la razón por la que ninguna de las
# variantes probadas movió el recall de adverso.
#
# Anotar al azar no lo resuelve: el adverso es el 8,5 % del corpus, así que de 100
# comentarios aleatorios salen ~8 adversos. Esta cola busca donde el adverso es
# probable Y la regla puede estar fallando.
#
# ⚠️ MISMO CUIDADO QUE `MUESTRA_DUDA`: al estar dirigida, NO sirve para estimar la
# calidad global del modelo. Sirve para CALIBRAR el lado adverso. El acuerdo medido
# sobre esta cola es un piso, no el valor real — por eso `origen_muestra` se guarda
# en cada corrección: sin él, mezclar las dos colas produce un número que no
# significa nada.
MUESTRA_ADVERSOS = "adversos"
# Cola ESTRATIFICADA — la salida al dilema entre las dos anteriores.
#
# `aleatorio` estima bien pero es caro (227 anotaciones para llegar a 50 adversos);
# `adversos` es barato (83) pero NO sirve para estimar nada. Esta parte el corpus en
# dos estratos por el puntaje de candidato adverso, sobremuestrea el estrato rico y
# RE-PESA cada estrato por su tamaño real al calcular cualquier métrica: la
# estimación sigue siendo insesgada y bastan ~105 anotaciones.
#
#     estrato   N corpus   % corpus   adversos
#     rico           711      8,7 %      35 %
#     pobre        7.463     91,3 %      10 %
#
# Validado contra los datos reales: re-pesando por estrato los 164 casos aleatorios
# ya anotados se obtiene 12,4 % de adversos, contra 12,8 % observado directamente.
#
# ⚠️ Una métrica calculada sobre esta cola SIN re-pesar está sesgada hacia arriba.
# Ver `curacion.repesar_por_estrato`, que no es opcional.
MUESTRA_ESTRATIFICADA = "estratificado"


class PercepcionCorreccion(Base):
    """Dataset de revisiones de sentimiento/emoción (auditoría + aprendizaje).

    Cada fila = una vez que alguien (persona o agente) revisó lo que dijo el modelo,
    con su justificación. Sirve para: auditar el modelo, generar reglas y un
    fine-tuning futuro. La Torre la escribe; base compartida con el worker.

    ⚠️ TABLA PROPIA DE LA TORRE (no es espejo del worker), por eso acá sí se pueden
    poner defaults y agregar columnas. Pero `create_all(checkfirst=True)` solo crea
    tablas AUSENTES, nunca columnas nuevas sobre una tabla que ya existe → las
    altas posteriores van por `db._asegurar_columnas()`.

    Tres cosas que esta tabla DEBE registrar y antes no registraba:

    1. `confirmado` — el acuerdo. Antes solo se escribía fila al CAMBIAR algo, así
       que las 376 filas de la base real son 376 desacuerdos y **no hay denominador**:
       el accuracy es literalmente incalculable. Un revisor que confirma "está bien"
       también es un dato, y es el más importante para medir.
    2. `*_orig` — la salida ORIGINAL del modelo. La corrección sobrescribe
       `percepcion_score.prob_*` con los sintéticos de `_PROBS_SENT` (0,90/0,05/0,05);
       en la base real eso destruyó 262 probabilidades, que son justo el insumo de
       cualquier recalibración. El snapshot va acá, ANTES de tocar el score.
    3. `autor_tipo` / `origen_muestra` — de quién y de qué cola viene la anotación.
    """

    __tablename__ = "percepcion_correccion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comentario_id: Mapped[int] = mapped_column(Integer, index=True)
    campo: Mapped[str] = mapped_column(String(20))  # sentimiento|emocion|tema|postura
    # 40 = el techo REAL de un valor corregible, no un número al azar: `curacion._slug`
    # corta las claves de tema en 40 (`t[:40]`) y `PercepcionTemaCustom.clave` es
    # String(40). Estaban en String(20) de cuando lo único corregible era
    # sentimiento/emoción; al sumarse la corrección de TEMA quedaron cortas y tres slugs
    # fijos no entran: logros_reconocimientos (22), organizacion_estudiantil (24) y
    # servicios_institucionales (25). SQLite NO valida el largo de un VARCHAR, así que
    # 2.996 filas se escribieron sin chistar en local y la migración a Postgres murió
    # con `value too long for type character varying(20)`.
    # OJO: `db._asegurar_columnas` solo hace ADD COLUMN, NUNCA ALTER TYPE — en una base
    # Postgres que ya tenga la tabla creada, ensancharla es un ALTER manual.
    valor_original: Mapped[str | None] = mapped_column(String(40))
    valor_nuevo: Mapped[str] = mapped_column(String(40))
    justificacion: Mapped[str | None] = mapped_column(Text)
    autor: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime | None] = mapped_column(DateTime)

    # --- El acuerdo (ver punto 1 del docstring) ---
    # True  = el revisor miró y dejó lo que había (confirmación).
    # False = lo cambió.
    # NULL  = fila anterior a esta columna; NO se puede asumir ninguna de las dos.
    confirmado: Mapped[bool | None] = mapped_column(Boolean, index=True)

    # --- Snapshot del modelo ANTES de la corrección (ver punto 2) ---
    modelo_orig: Mapped[str | None] = mapped_column(String(120))
    prob_pos_orig: Mapped[float | None] = mapped_column(Float)
    prob_neu_orig: Mapped[float | None] = mapped_column(Float)
    prob_neg_orig: Mapped[float | None] = mapped_column(Float)
    prob_emocion_orig: Mapped[float | None] = mapped_column(Float)
    # Confianza que tenía el CLASIFICADOR DE TEMAS antes de la curación. Sirve para
    # responder algo que hoy no se puede: ¿su confianza predice si acierta? Si sí, se
    # puede auto-aceptar lo confiable y revisar a mano solo lo dudoso. Importa porque
    # la mediana del corpus es 0,45 y el 89,5% está por debajo de 0,7.
    prob_tema_orig: Mapped[float | None] = mapped_column(Float)

    # --- Procedencia de la anotación (ver punto 3) ---
    autor_tipo: Mapped[str | None] = mapped_column(String(20), index=True)
    origen_muestra: Mapped[str | None] = mapped_column(String(20), index=True)


class PercepcionResumenSemanal(Base):
    """Resumen narrativo (LLM) de UNA semana para UN alcance. Caché, no fuente.

    ⚠️ TABLA PROPIA DE LA TORRE (no es espejo del worker) — valen defaults y altas
    de columnas por `db._asegurar_columnas()`.

    POR QUÉ EXISTE LA COLUMNA `huella`
    ----------------------------------
    El requisito es «que solo se corra al cargar los datos», y la Torre NO se entera
    de cuándo el worker ingesta: son procesos distintos, y la Torre lee su base en
    modo `query_only`. La única señal honesta de «hay datos nuevos» es la DATA MISMA.

    `huella` es el sha256 del paquete de insumos deterministas de esa semana. Si el
    worker no ingestó nada, el paquete es byte a byte idéntico, la huella coincide y
    se sirve el texto guardado **sin llamar al LLM**. Apenas entra un comentario, la
    huella cambia y se regenera. O sea: se gasta exactamente una vez por cada estado
    distinto de los datos, que es lo que se pidió, sin acoplar los dos repos.

    Sin la huella habría que elegir entre regenerar en cada request (caro y no
    determinista) o cachear por fecha (serviría un resumen viejo sobre datos nuevos,
    que es peor: miente sin avisar).

    `costo_usd` se guarda por fila —y no solo en `llm_usage`— porque la pregunta que
    hay que poder contestar es «cuánto cuesta ESTE feature por semana», y para eso el
    costo tiene que vivir al lado del período que lo generó.
    """

    __tablename__ = "percepcion_resumen_semanal"

    # ⚠️ La unicidad NO es una prolijidad de esquema: es lo que impide pagar dos veces.
    # Dos requests concurrentes (dos personas abriendo la pestaña, o dos instancias de
    # Cloud Run) buscan el caché, no encuentran nada, y ambas generan. Medido: pasó, y
    # dejó dos filas con la MISMA huella separadas por 54 ms.
    __table_args__ = (
        UniqueConstraint("semana_inicio", "nivel", "dimension",
                         name="uq_percepcion_resumen_semana_alcance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Lunes de la semana (mismo ancla que `repository._lunes`, que ya usa toda la
    # agregación semanal del módulo: dos anclas distintas darían dos verdades).
    semana_inicio: Mapped[date] = mapped_column(Date, index=True)
    nivel: Mapped[str] = mapped_column(String(20), index=True)      # campus|facultad|global
    # Nombre de la unidad; **cadena vacía = alcance global**, NUNCA NULL.
    #
    # Y esto es exactamente por lo que el UNIQUE de arriba funciona. En SQL `NULL` no
    # es igual a `NULL`, así que un UNIQUE sobre una columna nullable NO impide dos
    # filas globales — que es el caso principal de este feature. Guardar "" en vez de
    # NULL es lo que convierte la restricción en una garantía real.
    dimension: Mapped[str] = mapped_column(String(160), index=True, default="")

    huella: Mapped[str] = mapped_column(String(64), index=True)
    texto: Mapped[str] = mapped_column(Text)

    modelo: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    costo_usd: Mapped[float | None] = mapped_column(Float)
    generado_en: Mapped[datetime | None] = mapped_column(DateTime)


# Cuánto se puede confiar en las FECHAS de un evento. No es un adorno documental:
# es lo que impide que un modelo calibre contra una fecha inventada.
#
# El calendario entregado por la DAI marca explícitamente varios casos: "no está
# suficientemente documentada la duración efectiva del paro" (2022), "fechas exactas
# no verificadas, no deben tratarse todavía como definitivas" (2023), "fecha exacta de
# término todavía no confirmada" (paro Derecho 2025). Si esas fechas entran a la misma
# columna que las confirmadas, cualquier análisis de "cuánto cae el índice tras un
# paro" mezcla evidencia con suposición y no hay forma de separarlas después.
CONFIANZA_CONFIRMADA = "confirmado"    # fecha documentada
CONFIANZA_ESTIMADA = "estimado"        # ocurrió, pero las fechas son aproximadas
CONFIANZA_PLANIFICADA = "planificado"  # fecha de calendario que todavía puede moverse


class PercepcionEvento(Base):
    __tablename__ = "percepcion_evento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    fecha_inicio: Mapped[date] = mapped_column(Date, index=True)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    descripcion: Mapped[str | None] = mapped_column(Text)
    ambito: Mapped[str | None] = mapped_column(String(120))
    # Ver las constantes CONFIANZA_* de arriba. NULL = evento cargado a mano desde el
    # panel antes de que existiera esta columna; se trata como `estimado`, que es lo
    # conservador (no afirma que la fecha esté verificada).
    confianza: Mapped[str | None] = mapped_column(String(20), index=True)
    # De dónde salió la fila. `FUENTE_CALENDARIO` = vino del JSON versionado, así que
    # la carga puede sincronizarla (actualizar y hasta borrar lo que ya no existe en
    # el archivo). NULL = la cargó una persona desde el ABM del panel, y **nunca se
    # toca**: sin esta distinción, corregir el calendario borraría trabajo ajeno.
    fuente: Mapped[str | None] = mapped_column(String(40), index=True)


# --------------------------------------------------------------------------- #
# DERIVADOS DEL TEXTO CRUDO (Fase 3b).
# --------------------------------------------------------------------------- #
# La API normal corre con un rol de base de datos SIN permiso de lectura sobre
# `percepcion_comentario.texto` ni `percepcion_publicacion.caption`. Lo que necesita de
# ellos (nube de palabras, términos bajo vigilancia, impacto de palabras, rasgos de las
# captions) lo lee de estas tablas, que llena `scripts/precalcular_tokens_percepcion.py`
# con un rol privilegiado y con EXACTAMENTE la misma lógica (`derivados.py`).
#
# Son tablas de la Torre (no del worker) y se reconstruyen enteras: no hay que migrar
# nada al cambiar el tokenizador, basta volver a correr el script. Qué NO guardan: el
# orden de las palabras ni su repetición, así que el texto no se puede reconstruir.
class PercepcionComentarioToken(Base):
    """Palabras (normalizadas, sin stopwords ni PII conocida) de UN comentario, sin repetir."""

    __tablename__ = "percepcion_comentario_token"

    comentario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("percepcion_comentario.id", ondelete="CASCADE"), primary_key=True)
    token: Mapped[str] = mapped_column(String(200), primary_key=True)


class PercepcionComentarioFamilia(Base):
    """Familias del léxico de vigilancia (`lexico.FAMILIAS`) que menciona un comentario."""

    __tablename__ = "percepcion_comentario_familia"

    comentario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("percepcion_comentario.id", ondelete="CASCADE"), primary_key=True)
    familia: Mapped[str] = mapped_column(String(40), primary_key=True)


class PercepcionPublicacionRasgo(Base):
    """Rasgos binarios de la caption de una publicación (para `comunicacion.py`).

    Solo los que se calculan DE la caption; `es_reel` y `fin_de_semana` salen de la
    publicación misma y no se guardan acá.
    """

    __tablename__ = "percepcion_publicacion_rasgo"

    publicacion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("percepcion_publicacion.id", ondelete="CASCADE"), primary_key=True)
    emojis_3_o_mas: Mapped[bool] = mapped_column(Boolean, default=False)
    menciona_cuentas: Mapped[bool] = mapped_column(Boolean, default=False)
    hashtags_3_o_mas: Mapped[bool] = mapped_column(Boolean, default=False)
    hace_una_pregunta: Mapped[bool] = mapped_column(Boolean, default=False)
    texto_largo: Mapped[bool] = mapped_column(Boolean, default=False)
    sin_texto: Mapped[bool] = mapped_column(Boolean, default=False)
