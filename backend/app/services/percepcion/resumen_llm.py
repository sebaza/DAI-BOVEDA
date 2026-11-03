"""RESUMEN SEMANAL narrativo del módulo Percepción, redactado por LLM.

Qué contesta: «¿qué pasó esta semana en esta sede?» en cuatro o cinco frases —
de qué se habló, qué publicación se llevó la conversación, si hubo un evento grande,
y cómo se movió respecto de la semana anterior.

TRES DECISIONES QUE VALE LA PENA ENTENDER ANTES DE TOCAR ESTE ARCHIVO
=====================================================================

1) EL LLM INTERPRETA, NO CUENTA
-------------------------------
Al modelo se le entrega un paquete de insumos YA AGREGADOS (`insumos_semana`) y se le
prohíbe explícitamente inventar o recalcular cifras. Los conteos salen de
`percepcion_hecho_diario`, que es exacto; un LLM contando 100 textos se equivoca y
nadie lo nota, porque el error viene redactado con la misma prosa segura que el acierto.
Es la misma regla que ya usa `informe_llm._redactar` para los informes de arancel.

2) NO VIAJA NI UN COMENTARIO AL LLM
-----------------------------------
Sí viajan las CAPTIONS de las publicaciones; no viajan los textos de los comentarios.
La diferencia no es de tamaño, es de propiedad: la caption la publicó la UCN por su
propia cuenta institucional, el comentario lo escribió una persona. Todo el módulo se
sostiene sobre no exportar lo que escribió la gente (`autor_hash` irreversible, umbral
anti-PII en la nube de palabras), y mandarlos a un tercero rompería justamente eso.

Y encima no hace falta. Medido sobre el corpus real: **el comentario promedio mide 43
caracteres** ("💚", "felicitaciones", "grande"). El comentario es la REACCIÓN; el hecho
está en la caption, que promedia 496. Para saber qué pasó hay que mirar la publicación.

3) SE COBRA UNA VEZ POR ESTADO DE LOS DATOS — LA HUELLA
--------------------------------------------------------
El requisito es «que solo se corra al cargar los datos». La Torre NO se entera de la
ingesta: el worker es otro proceso, en otro repo, y la Torre abre su base en modo
`query_only`. La única señal honesta de "hay datos nuevos" es la data misma.

Por eso `huella()` es el sha256 del paquete de insumos. Si el worker no ingestó nada,
el paquete es idéntico byte a byte, la huella coincide y se devuelve el texto guardado
**sin llamar a OpenAI**. Apenas entra un comentario, la huella cambia y se regenera.

Las dos alternativas son peores: regenerar en cada request es caro y no determinista;
cachear por fecha serviría un resumen viejo sobre datos nuevos, o sea mentir sin avisar.

COSTO MEDIDO CONTRA LA API REAL (semana 17–23/08/2026, n=41)
------------------------------------------------------------
~3.200–4.000 tokens de entrada + 360–580 de salida. Con `claude-haiku-4-5`
(1,0 USD/M entrada · 5,0 USD/M salida): **0,005–0,007 USD por resumen → 0,26–0,36 USD
al año.** Con Opus 5 serían 1,71 USD/año (ver la nota de `MODELO_ANTHROPIC`).

⚠️ Una estimación previa de este mismo archivo decía 0,0013 USD, y estaba MAL por dos
motivos que conviene no repetir: (1) la regla de ~3,7 caracteres por token subestima
casi a la mitad un prompt que es JSON en español — hay que medir con la API, no con
una división; (2) cambiar de proveedor cambia la escala de precio aunque el código se
vea igual (Opus 5 es 20× la entrada de `gpt-5.4-mini`).

El costo no es la restricción de este feature. La cobertura de datos sí (ver `NIVELES`).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import false, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.services.costos import costo_estimado_usd, registrar_uso_llm
from app.services.percepcion import cripto, repository
from app.services.percepcion.models import PercepcionComentario as C
from app.services.percepcion.models import PercepcionCuenta as Cu
from app.services.percepcion.models import PercepcionEvento as Evento
from app.services.percepcion.models import PercepcionHechoDiario as H
from app.services.percepcion.models import PercepcionPublicacion as P
from app.services.percepcion.models import PercepcionResumenSemanal
from app.services.percepcion.postura import ORDEN_POSTURA, contar_por_postura

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

# --------------------------------------------------------------------------- #
# Proveedor del redactor
# --------------------------------------------------------------------------- #
# Este es el ÚNICO punto de la Torre que redacta con Claude; el resto (chatbox,
# intake, informes) va por la Responses API de OpenAI. La elección no es un capricho:
# `openai_api_key` está vacía en el entorno local y `anthropic_api_key` no, así que
# sin esto el feature no se puede ni probar fuera de la nube.
#
# Se elige por DATO, no por config: gana Anthropic si hay clave de Anthropic, y si no
# se cae a OpenAI. Así el mismo código corre local (Claude) y en la nube (lo que haya
# en Secret Manager) sin una variable más que mantener sincronizada entre los dos.
PROVEEDOR_ANTHROPIC = "anthropic"
PROVEEDOR_OPENAI = "openai"

# ELEGIDO MIDIENDO, no por default. Se corrieron los tres sobre los MISMOS insumos
# (semana 17–23/08/2026, n=41) y se evaluaron las cuatro reglas que hacen publicable
# el bloque. Empataron en las cuatro — y en la lectura fina el más barato ganó:
#
#   modelo             cifras inventadas  unidades  prudencia  USD/año  latencia
#   claude-opus-5              0            4/4        sí        1,71     10,5 s
#   claude-sonnet-5            0            4/4        sí        1,07     13,9 s
#   claude-haiku-4-5           0            4/4        sí        0,36      8,7 s
#
# El desempate NO fue el precio. La emoción dominante de esa semana era `sin_emocion`
# (20) sobre `joy` (18), y **Opus 5 fue el único que dijo "predominio de alegría"** —
# reportó la segunda como dominante. Sonnet y Haiku la leyeron bien y además citaron
# el `n` de cada unidad destacada ("9 y 8 comentarios"), que es lo que le permite al
# lector juzgar la solidez. Haiku fue también el más rápido.
#
# Para esta tarea eso tiene sentido: los datos vienen CALCULADOS y ordenados por el
# servicio; no hay nada que razonar, hay que redactar. La capacidad extra de un modelo
# grande no tiene dónde aplicarse, y su libertad interpretativa solo agrega riesgo.
#
# Si el prompt crece hasta pedir juicio (priorizar, inferir causas, recomendar), hay
# que volver a correr esta comparación — el empate vale para ESTA tarea, no en general.
MODELO_ANTHROPIC = "claude-haiku-4-5"

# Solo aplica si el modelo configurado lo soporta (Haiku 4.5, el default, NO lo hace).
# Queda para el caso de volver a un modelo de la familia Opus/Sonnet: redactar sobre
# datos ya calculados no necesita razonamiento profundo, y `low` recorta ese gasto.
EFFORT_ANTHROPIC = "low"

# ⚠️ `output_config.effort` NO existe en toda la familia. Haiku 4.5 y Sonnet 4.5 lo
# RECHAZAN con un 400, así que mandarlo siempre rompería el feature apenas alguien
# ponga un modelo más barato en `PERCEPCION_RESUMEN_MODELO` — que es justamente el
# motivo por el que ese setting existe. Se enumera por prefijo: los IDs no llevan
# sufijo de fecha, y las familias nuevas se agregan acá a mano y a propósito.
_PREFIJOS_CON_EFFORT = ("claude-opus-5", "claude-opus-4-6", "claude-opus-4-7",
                        "claude-opus-4-8", "claude-sonnet-5", "claude-sonnet-4-6",
                        "claude-fable-5", "claude-mythos-5")


def soporta_effort(modelo: str) -> bool:
    return any(modelo.startswith(p) for p in _PREFIJOS_CON_EFFORT)

# Alcances soportados. **El default y el uso previsto es `global`**: UN resumen de
# toda la universidad por semana, que menciona adentro las unidades que se movieron.
#
# Por qué no uno por unidad, que fue el primer diseño: sobre el corpus real hay
# 40–165 comentarios POR SEMANA en toda la UCN. Repartidos en 9 facultades dan ~5
# cada una, contra el `N_MIN_EVIDENCIA = 30` que el propio módulo exige para afirmar
# algo de una unidad — y encima **el 54 % de los comentarios no tiene facultad**
# (1.614 de 3.006). Un resumen por unidad diría "evidencia insuficiente" casi
# siempre; uno global con las desviaciones adentro dice lo mismo que se sabe, pero
# sin fingir que se sabe más.
#
# `campus`/`facultad` quedan soportados para acotar el alcance a mano (y para el día
# que el volumen dé), pero no son el camino principal.
NIVELES = ("global", "campus", "facultad")

# Mínimo para que una unidad se MENCIONE en el resumen global. No es evidencia
# suficiente —eso son 30— es el piso para que la mención no sea ruido: por debajo de
# 5 comentarios, un solo comentario mueve el índice entero. Cada unidad viaja con su
# `evidencia_suficiente` para que el redactor sepa cuál puede afirmar y cuál no.
N_MIN_UNIDAD = 5
# Cuánto se tiene que mover el índice para que valga nombrarlo. Con den chico el
# índice oscila solo; por debajo de esto es ruido de muestreo, no una señal.
DELTA_INDICE_NOTABLE = 8.0
# Adversos que ameritan mención aunque nada se haya movido.
ADVERSOS_NOTABLES = 3
# Tope de unidades en el prompt: es un resumen, no un ranking.
MAX_UNIDADES_DESTACADAS = 6

# Cuántas publicaciones se le muestran al redactor. Son la evidencia de QUÉ pasó, así
# que son lo caro del prompt (~140 tokens de caption cada una): 6 alcanzan para el
# evento dominante y sus dos o tres seguidores sin inflar el gasto.
N_PUBLICACIONES = 6
# La caption institucional media son 496 caracteres, pero la cola suele ser hashtags
# y menciones que no aportan al resumen y sí a la factura.
MAX_CAPTION = 320
N_TEMAS = 6
N_PALABRAS = 12

# Techo de SEGURIDAD, no control de longitud. El largo del texto lo fija la regla 3
# de las instrucciones (5–7 frases); `max_tokens` solo evita una salida desbocada.
# Es holgado a propósito: con thinking adaptivo, un techo justo corta el texto a la
# mitad de una frase en vez de producir uno más corto.
MAX_OUTPUT_TOKENS = 4000
TIMEOUT_SEGUNDOS = 120.0

FEATURE_COSTO = "percepcion_resumen_semanal"


class ResumenNoDisponible(RuntimeError):
    """No se pudo redactar (falta la key, OpenAI caído, respuesta vacía).

    Es una degradación esperada, NO un error del tablero: el panel sigue mostrando
    todos sus bloques deterministas y este queda con su aviso.
    """


# --------------------------------------------------------------------------- #
# Anclaje temporal
# --------------------------------------------------------------------------- #
def ultima_semana(db) -> date | None:
    """Lunes de la última semana CON DATOS.

    Anclado a los datos y no al reloj, igual que el resto del módulo
    (`repository._rango`): si el worker se atrasa un día, anclar a `hoy` devolvería
    una semana vacía y el tablero diría "no pasó nada" cuando lo que pasó es que no
    corrió la ingesta. Son dos cosas muy distintas.
    """
    fmax = db.execute(select(func.max(H.fecha))).scalar_one_or_none()
    return repository._lunes(fmax) if fmax else None


def semanas_disponibles(db, *, limite: int = 52, nivel: str = "global",
                        dimension: str | None = None) -> list[dict]:
    """Catálogo de semanas navegables, de la más nueva a la más vieja.

    El front no puede adivinar a dónde puede ir: con un selector de fechas libre, la
    mayoría de los saltos caerían en semanas sin un solo comentario y el usuario vería
    el empty-state sin entender por qué. Acá salen solo las que tienen datos.

    `tiene_resumen` distingue **navegar de generar**: ir a una semana ya escrita es
    instantáneo y gratis; ir a una sin escribir dispara una llamada al modelo. Son
    ~0,005 USD, pero la UI tiene que poder decirlo antes de que el usuario haga clic.

    La agrupación por semana se hace en Python y no en SQL a propósito: `strftime`,
    `date_trunc` y `EXTRACT(week)` difieren entre SQLite y Postgres —y en el número de
    semana ISO en los bordes de año—, y este módulo corre contra los dos. Son ~940
    filas de hechos: agrupar en memoria es exacto y sobra de rápido.
    """
    alc = _filtro_alcance(nivel, dimension)
    filas = db.execute(
        select(H.fecha, func.sum(H.n_comentarios))
        .where(*repository._condiciones(alc["campus"], alc["facultad"], None, None))
        .group_by(H.fecha)
    ).all()

    por_semana: dict[date, int] = {}
    for fecha, n in filas:
        f = repository._a_fecha(fecha)
        if f is None:
            continue
        por_semana[repository._lunes(f)] = por_semana.get(repository._lunes(f), 0) + int(n or 0)

    # Qué semanas YA tienen texto escrito. Va en su propio try porque la tabla puede
    # no existir todavía (base donde la Torre nunca arrancó, o motor sin DDL). Que
    # falte el caché significa "ninguna está escrita", NO que no haya semanas: sin
    # este guardia, un detalle del caché tiraba abajo la navegación entera.
    escritas: set = set()
    try:
        escritas = {
            # La columna es Date, pero una base creada por otro motor puede dar str.
            date.fromisoformat(s) if isinstance(s, str) else repository._a_fecha(s)
            for (s,) in db.execute(
                select(PercepcionResumenSemanal.semana_inicio).where(
                    PercepcionResumenSemanal.nivel == nivel,
                    PercepcionResumenSemanal.dimension == _clave_dimension(dimension),
                )
            ).all()
        }
    except Exception:
        try:
            db.rollback()   # la sesión queda abortada tras el error; hay que limpiarla
        except Exception:
            pass

    ordenadas = sorted((s for s, n in por_semana.items() if n > 0), reverse=True)
    return [
        {"semana": s, "n_comentarios": por_semana[s], "tiene_resumen": s in escritas}
        for s in ordenadas[:max(1, int(limite))]
    ]


def _filtro_alcance(nivel: str, dimension: str | None) -> dict[str, Any]:
    if nivel == "campus":
        return {"campus": dimension, "facultad": None}
    if nivel == "facultad":
        return {"campus": None, "facultad": dimension}
    return {"campus": None, "facultad": None}


def _etiqueta_alcance(nivel: str, dimension: str | None) -> str:
    if nivel == "global" or not dimension:
        return "toda la universidad"
    return f"{'la sede' if nivel == 'campus' else 'la unidad'} {dimension}"


# --------------------------------------------------------------------------- #
# Insumos — el paquete determinista
# --------------------------------------------------------------------------- #
def insumos_semana(db, *, semana_inicio: date, nivel: str = "global",
                   dimension: str | None = None, db_texto=None) -> dict | None:
    """Todo lo que el redactor necesita saber de una semana, ya calculado.

    `db_texto` es la sesión con el rol que puede leer las CAPTIONS (las que se envían,
    truncadas, al modelo). Es lo único de todo el paquete que necesita texto crudo; el
    resto sale de la sesión normal `db`. Si no se pasa, se usa `db` (bases de prueba con
    una sola conexión).

    Devuelve None si esa semana no tuvo un solo comentario en ese alcance: sin datos
    no hay nada que redactar y, sobre todo, nada que pagar.

    `peso_likes=0` y `vida_media=0` A PROPÓSITO. Este bloque NARRA lo que pasó, y lo
    que se narra tiene que poder verificarse contando: un índice ponderado por likes
    y por recencia da un número correcto que nadie puede reproducir a mano. Es el
    mismo criterio con el que `postura_institucional` usa `kwargs()` y no
    `kwargs_peso()`.
    """
    desde = repository._lunes(semana_inicio)
    hasta = desde + timedelta(days=6)
    alc = _filtro_alcance(nivel, dimension)
    fecha = {"fecha_desde": desde, "fecha_hasta": hasta}
    plano = dict(dias=7, departamento=None, tema=None, **alc, **fecha)

    g_temas = repository._agrupado(db, 7, H.tema, alc["campus"], alc["facultad"],
                                   None, None, 0.0, 0, desde, hasta)
    n_total = sum(g["n"] for g in g_temas)
    if not n_total:
        return None

    etq = repository.etiquetas_tema(db)
    num_pos = sum(g["num_pos"] for g in g_temas)
    num_neg = sum(g["num_neg"] for g in g_temas)
    den = sum(g["den"] for g in g_temas)

    temas = sorted(
        (
            {
                "tema": g["dim"],
                "etiqueta": etq.get(g["dim"], g["dim"]),
                "n_comentarios": g["n"],
                "share_pct": round(100.0 * g["n"] / n_total, 1),
                "indice": repository._indice(g["num_pos"], g["num_neg"], g["den"]),
                "n_pos": g["npos"], "n_neu": g["nneu"], "n_neg": g["nneg"],
            }
            for g in g_temas
        ),
        key=lambda t: (-t["n_comentarios"], t["tema"] or ""),
    )[:N_TEMAS]

    # La postura NO sale de `g_temas` (que viene de la tabla de hechos) sino del
    # CORPUS: desde 09-2026 mira también el tipo de cuenta —un neutro en la
    # federación es adverso— y el grano de hechos no lo guarda. Si este bloque
    # siguiera con los hechos, el resumen semanal contaría los adversos distinto
    # que el tablero, que es la clase de discrepancia que este módulo persigue.
    postura = dict.fromkeys(ORDEN_POSTURA, 0)
    for t, ctipo, npos, nneu, nneg in repository._conteos_postura(
            db, desde, hasta, alc["campus"], alc["facultad"], None, None):
        for k, v in contar_por_postura(t, npos, nneu, nneg, cuenta_tipo=ctipo).items():
            postura[k] += v

    return {
        "alcance": {"nivel": nivel, "dimension": dimension,
                    "etiqueta": _etiqueta_alcance(nivel, dimension)},
        "periodo": {"desde": desde, "hasta": hasta},
        "n_comentarios": n_total,
        "indice": repository._indice(num_pos, num_neg, den),
        "distribucion": {
            "positivo": sum(g["npos"] for g in g_temas),
            "neutral": sum(g["nneu"] for g in g_temas),
            "negativo": sum(g["nneg"] for g in g_temas),
        },
        "postura": dict(postura),
        "temas": temas,
        "emociones": _emociones(db, desde, hasta, alc),
        "publicaciones": _publicaciones(db_texto if db_texto is not None else db,
                                        desde, hasta, alc),
        "palabras": _palabras(db, plano),
        "eventos_institucionales": _eventos(db, desde, hasta),
        "semana_anterior": _semana_anterior(db, desde, alc),
        "unidades_destacadas": _unidades_destacadas(db, desde, alc),
    }


# --------------------------------------------------------------------------- #
# Desviaciones por unidad — lo que hace que un resumen global no sea un promedio
# --------------------------------------------------------------------------- #
# El riesgo de resumir toda la universidad en un número es justamente ese: el
# promedio tapa. Si una sede se desplomó y otra subió, el índice global no se mueve
# y el resumen dice "semana estable", que es falso.
#
# Por eso el paquete global lleva las unidades que SE MOVIERON, en los tres niveles,
# ya filtradas y con el motivo calculado en Python. El LLM no decide qué es notable
# —eso es un umbral, no una opinión—; decide cómo contarlo.
_DIMENSIONES = (("campus", H.campus), ("facultad", H.facultad),
                ("departamento", H.departamento))


def _unidades_destacadas(db, desde: date, alc: dict) -> list[dict]:
    """Unidades cuya semana se salió de lo suyo, en los tres niveles.

    Solo tiene sentido en el alcance global: con la sede ya fijada, comparar sedes
    es comparar una sola cosa consigo misma.
    """
    if alc["campus"] or alc["facultad"]:
        return []
    hasta = desde + timedelta(days=6)
    prev_desde, prev_hasta = desde - timedelta(days=7), desde - timedelta(days=1)

    destacadas: list[dict] = []
    for nivel, col in _DIMENSIONES:
        actual = {g["dim"]: g for g in repository._agrupado(
            db, 7, col, None, None, None, None, 0.0, 0, desde, hasta)}
        previa = {g["dim"]: g for g in repository._agrupado(
            db, 7, col, None, None, None, None, 0.0, 0, prev_desde, prev_hasta)}

        for nombre, g in actual.items():
            if g["n"] < N_MIN_UNIDAD:
                continue
            indice = repository._indice(g["num_pos"], g["num_neg"], g["den"])
            ant = previa.get(nombre)
            indice_ant = (repository._indice(ant["num_pos"], ant["num_neg"], ant["den"])
                          if ant else None)
            delta = (round(indice - indice_ant, 1)
                     if indice is not None and indice_ant is not None else None)
            motivo = _motivo(g, delta, ant)
            if motivo is None:
                continue
            destacadas.append({
                "nivel": nivel,
                "nombre": nombre,
                "n_comentarios": g["n"],
                "indice": indice,
                "n_semana_anterior": ant["n"] if ant else 0,
                "indice_semana_anterior": indice_ant,
                "delta_indice": delta,
                "n_negativos": g["nneg"],
                # Debajo de 30 el módulo entero se niega a afirmar nada de una
                # unidad. Viaja al prompt para que el texto module el verbo.
                "evidencia_suficiente": g["n"] >= repository.N_MIN_EVIDENCIA,
                "motivo": motivo,
            })

    # Primero lo que más se movió; a igual movimiento, lo que más volumen tiene.
    destacadas.sort(key=lambda u: (-abs(u["delta_indice"] or 0), -u["n_comentarios"]))
    return destacadas[:MAX_UNIDADES_DESTACADAS]


def _motivo(g: dict, delta: float | None, ant: dict | None) -> str | None:
    """Por qué esta unidad merece una mención. None = no la merece.

    Se calcula acá y no en el prompt para que el criterio sea auditable y estable:
    un umbral en el código se puede discutir y testear; "lo que al modelo le pareció
    relevante" cambia entre corridas y no se puede defender ante nadie.
    """
    if delta is not None and abs(delta) >= DELTA_INDICE_NOTABLE:
        return ("el índice subió %.1f puntos" if delta > 0
                else "el índice bajó %.1f puntos") % abs(delta)
    if g["nneg"] >= ADVERSOS_NOTABLES:
        return f"concentra {g['nneg']} comentarios negativos"
    if ant is None:
        return "aparece esta semana, sin actividad la semana anterior"
    if ant["n"] and g["n"] >= 2 * ant["n"]:
        return f"el volumen se multiplicó por {g['n'] / ant['n']:.1f}"
    if ant["n"] >= N_MIN_UNIDAD and g["n"] * 2 <= ant["n"]:
        return f"el volumen cayó de {ant['n']} a {g['n']} comentarios"
    return None


def _emociones(db, desde: date, hasta: date, alc: dict) -> list[dict]:
    """Top emociones de la semana. Reusa el agregado del módulo, no recalcula."""
    conteo = repository._emociones_por_dim(
        db, desde, hasta, H.campus if alc["campus"] else H.tema,
        alc["campus"], alc["facultad"], None, None,
    )
    total: dict[str, int] = {}
    for por_dim in conteo.values():
        for emo, n in por_dim.items():
            total[emo] = total.get(emo, 0) + int(n or 0)
    return [
        {"emocion": e, "etiqueta": repository.ETIQUETAS_EMOCION.get(e, e), "n": n}
        for e, n in sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
    ]


def _publicaciones(db, desde: date, hasta: date, alc: dict) -> list[dict]:
    """Las publicaciones que se llevaron la conversación DE ESTA SEMANA.

    ⚠️ EL CONTEO SE CALCULA, NO SE LEE DE `percepcion_publicacion.n_comentarios`.
    Esa columna es el contador HISTÓRICO del post en Instagram: incluye comentarios
    de otras semanas y comentarios que la ingesta nunca trajo. Usarla producía cifras
    de otra escala dentro de un resumen semanal — medido sobre la semana del 20/07:
    total semanal 151, y las publicaciones que se le pasaban al modelo sumaban 337,
    una sola con 252. El modelo, obedientemente, escribió "reunió 252 comentarios" en
    un texto que decía 151. Nadie inventó nada: el dato de entrada era incoherente.

    Y no es un detalle estético. Un directivo que suma dos cifras del mismo párrafo y
    no le cierran deja de creerle al tablero entero, con razón.

    Ahora se cuentan los comentarios de la VENTANA, desde `percepcion_comentario` —
    la misma fuente que alimenta el total semanal—, así las cifras cierran entre sí.

    También cambia el criterio de inclusión: entran las publicaciones que RECIBIERON
    comentarios en la ventana, sin importar cuándo se publicaron. Un post del domingo
    anterior que explota el lunes es parte de la conversación de esta semana; filtrar
    por fecha de publicación lo dejaba afuera.

    Ordena por comentarios, no por likes: el like es aprobación pasiva, el comentario
    es la conversación que este módulo mide.
    """
    cond = [C.fecha_comentario >= datetime.combine(desde, datetime.min.time()),
            C.fecha_comentario < datetime.combine(hasta + timedelta(days=1),
                                                  datetime.min.time())]
    if alc["campus"]:
        cond.append(Cu.campus == alc["campus"])
    if alc["facultad"]:
        cond.append(Cu.facultad == alc["facultad"])

    n_semana = func.count(C.id).label("n_semana")
    filas = db.execute(
        select(P.caption, P.fecha_publicacion, n_semana, P.n_likes, P.tipo, Cu.nombre, P.id)
        .select_from(C)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
        .where(*cond)
        # GROUP BY P.id, Cu.id — las DOS entidades. Agrupar por la clave primaria de una
        # tabla determina funcionalmente el resto de SUS columnas, pero `Cu.nombre` es de
        # OTRA tabla: PostgreSQL la exige en el GROUP BY y falla con GroupingError.
        # SQLite la tolera (permite columnas "desnudas"), asi que la suite pasaba en verde
        # y el resumen reventaba recien contra la base real. Verificado en produccion el
        # 2026-08-24: "column percepcion_cuenta.nombre must appear in the GROUP BY clause".
        .group_by(P.id, Cu.id)
        .order_by(n_semana.desc(), P.fecha_publicacion.desc())
        .limit(N_PUBLICACIONES)
    )
    out = []
    for caption, fecha_pub, n_com, n_likes, tipo, cuenta, pid in filas:
        # Descifra en memoria: el caption viaja en claro al proveedor del modelo (como antes).
        texto = (cripto.caption_de(pid, caption) or "").strip()
        if len(texto) > MAX_CAPTION:
            texto = texto[:MAX_CAPTION].rstrip() + "…"
        out.append({
            "caption": texto,
            "fecha": repository._a_fecha(fecha_pub),
            # Nombre explícito: `n_comentarios` a secas se confunde con el total del
            # post, que es exactamente el error que este cambio corrige.
            "n_comentarios_en_la_semana": int(n_com or 0),
            "n_likes": int(n_likes or 0),
            "tipo": tipo,
            "cuenta": cuenta,
        })
    return out


def _palabras(db, plano: dict) -> list[dict]:
    """Vocabulario crudo de la semana.

    Complementa a los TEMAS, que son 8 cajas de un clasificador cuyo acierto medido es
    55,3 % — el eslabón más flojo de la cadena. Las palabras no dependen de él.

    Sale de `nube_palabras`, que ya trae el umbral anti-PII del módulo
    (`min_frecuencia=2`: una palabra dicha una sola vez puede volver identificable el
    comentario del que salió).
    """
    try:
        nube = repository.nube_palabras(db, limite=N_PALABRAS, **plano)
    except Exception:
        # El vocabulario es un extra: si falla, el resumen se redacta igual con los
        # agregados y las publicaciones, que son el núcleo.
        return []
    # Se recorta a lo que el redactor necesita: la palabra, cuánto se dijo y con qué
    # signo. El resto de la fila (variantes agrupadas, emoción dominante, etiquetas)
    # es para pintar la nube y acá solo sería prompt pagado sin uso.
    return [
        {"texto": p["texto"], "n": p["n"], "pos": p.get("pos", 0), "neg": p.get("neg", 0)}
        for p in (nube.get("palabras") or [])[:N_PALABRAS]
    ]


def _eventos(db, desde: date, hasta: date) -> list[dict]:
    """Marcas del calendario institucional que cruzan la semana (las carga la Torre)."""
    filas = db.execute(
        select(Evento.nombre, Evento.tipo, Evento.fecha_inicio, Evento.fecha_fin)
        .where(Evento.fecha_inicio <= hasta,
               func.coalesce(Evento.fecha_fin, Evento.fecha_inicio) >= desde)
        .order_by(Evento.fecha_inicio)
    )
    return [{"nombre": n, "tipo": t, "desde": fi, "hasta": ff}
            for n, t, fi, ff in filas]


def _semana_anterior(db, desde: date, alc: dict) -> dict | None:
    """Volumen e índice de la semana previa. Sin esto no se puede decir "subió"."""
    prev_desde = desde - timedelta(days=7)
    prev_hasta = desde - timedelta(days=1)
    g = repository._agrupado(db, 7, H.tema, alc["campus"], alc["facultad"],
                             None, None, 0.0, 0, prev_desde, prev_hasta)
    n = sum(x["n"] for x in g)
    if not n:
        return None
    return {
        "desde": prev_desde, "hasta": prev_hasta, "n_comentarios": n,
        "indice": repository._indice(sum(x["num_pos"] for x in g),
                                     sum(x["num_neg"] for x in g),
                                     sum(x["den"] for x in g)),
    }


# --------------------------------------------------------------------------- #
# Huella
# --------------------------------------------------------------------------- #
def huella(insumos: dict | None, modelo: str | None = None) -> str:
    """sha256 de TODO lo que determina el texto. Es LA señal de "hay que regenerar".

    Entran tres cosas, y las tres por el mismo motivo — cambiar cualquiera cambia el
    texto que corresponde mostrar:

    * **los insumos** — la señal de "hay datos nuevos", que es el caso frecuente;
    * **el modelo** — sin esto, bajar de Opus a Haiku dejaba en pantalla el texto que
      había escrito Opus, con su firma de modelo vieja y su lectura equivocada de la
      emoción dominante. Observado, no hipotético;
    * **el prompt** — cuando se corrige una regla (p.ej. "la emoción dominante es la
      primera de la lista"), los textos anteriores no la cumplen. Si el prompt no
      entrara acá, esa corrección no se aplicaría hasta la próxima ingesta.

    `sort_keys=True` no es cosmética: sin orden estable, dos corridas sobre los mismos
    datos darían huellas distintas y el caché no serviría para nada — se pagaría en
    cada request, que es exactamente lo que este mecanismo evita.
    """
    if not insumos:
        return ""
    crudo = json.dumps(
        {
            "insumos": insumos,
            "modelo": modelo or _modelo_configurado(),
            # Solo el hash: el prompt entero infla la huella sin agregar información.
            "prompt": hashlib.sha256(INSTRUCCIONES.encode("utf-8")).hexdigest()[:16],
        },
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


def _modelo_configurado() -> str:
    """El modelo que se USARÍA ahora, sin llamar a nadie."""
    settings = get_settings()
    if getattr(settings, "anthropic_api_key", ""):
        return getattr(settings, "percepcion_resumen_modelo", "") or MODELO_ANTHROPIC
    return getattr(settings, "openai_chat_model", "gpt-5.4-mini")


# --------------------------------------------------------------------------- #
# Redacción
# --------------------------------------------------------------------------- #
INSTRUCCIONES = (
    "Eres analista de la Dirección de Análisis Institucional (DAI) de la Universidad "
    "Católica del Norte. Escribes el RESUMEN SEMANAL de la conversación de la comunidad "
    "en redes sociales, a partir de datos YA AGREGADOS que se te entregan en JSON.\n"
    "REGLAS ESTRICTAS:\n"
    "1) USA EXCLUSIVAMENTE los números del JSON, TAL COMO VIENEN. No calcules, no "
    "estimes, no inventes cifras. En particular: NO sumes, restes, combines ni "
    "promedies cifras entre sí — nada de 'X e Y generaron N comentarios combinados'. "
    "Si quieres hablar de dos publicaciones, cita el número de cada una por separado. "
    "Si un dato no está en el JSON, no lo afirmes.\n"
    "2) Los datos son AGREGADOS. Nunca menciones ni inventes personas, autores, cuentas "
    "individuales ni comentarios textuales.\n"
    # 200 palabras era la regla original y los TRES modelos la pasaron (205/224/230).
    # Una regla que se incumple siempre no disciplina nada: se ajusta al largo que la
    # tarea realmente necesita, que sigue siendo un párrafo y no un informe.
    "3) EXTENSIÓN: entre 5 y 8 frases, máximo 240 palabras. Es un resumen ejecutivo para "
    "leer de un vistazo, NO un informe. Prosa corrida en español, sin viñetas, sin "
    "títulos, sin markdown.\n"
    "4) PRIORIDAD del contenido, en este orden: (a) qué actividad o publicación concentró "
    "la conversación —usa las captions de 'publicaciones' para nombrarla—; (b) de qué se "
    "habló, con el número de comentarios; (c) cómo se sintió (tono/emoción/postura); "
    "(d) cómo se compara con 'semana_anterior' si viene.\n"
    "4b) Las cifras del texto tienen que CERRAR entre sí. El único conteo de una "
    "publicación es 'n_comentarios_en_la_semana', y ninguna cifra parcial puede superar "
    "el 'n_comentarios' total de la semana. Si una suma no te cuadra, no la escribas.\n"
    "5) 'unidades_destacadas' son las sedes, facultades o departamentos que se salieron "
    "de lo suyo esta semana. Si la lista trae algo, DEDÍCALE al menos una frase y nombra "
    "la unidad con su 'motivo'. Es lo que un promedio institucional tapa, y es la razón "
    "de ser de este resumen: si una sede se desploma y otra sube, el número global no se "
    "mueve y decir 'semana estable' sería falso. Si la lista viene vacía, di que ninguna "
    "unidad se apartó de su comportamiento habitual.\n"
    "6) Si una unidad trae 'evidencia_suficiente': false, menciónala igual pero con verbo "
    "prudente ('se observa', 'aparece') y di que el volumen es bajo. Nunca afirmes una "
    "tendencia sobre menos de 30 comentarios.\n"
    "7) Si 'eventos_institucionales' trae algo, nómbralo: es contexto del calendario.\n"
    "8) Cuando 'n_comentarios' sea menor a 30, di explícitamente que el volumen de la "
    "semana es bajo y que la lectura es indicativa. No adornes una muestra chica.\n"
    "9) 'emociones' y 'temas' vienen ORDENADOS de mayor a menor. La emoción o el tema "
    "dominante es SIEMPRE el primero de la lista, aunque el segundo te parezca más "
    "interesante de contar. No lo reordenes.\n"
    "10) Tono institucional, sobrio y concreto. Nada de superlativos ni de lenguaje de "
    "marketing."
)


def _prompt(insumos: dict) -> str:
    return (
        "Redacta el resumen semanal de percepción para "
        f"{insumos['alcance']['etiqueta']}.\n"
        "Datos agregados de la semana:\n"
        f"{json.dumps(insumos, ensure_ascii=False, default=str, sort_keys=True)}\n\n"
        "Devuelve EXCLUSIVAMENTE el texto del resumen, sin encabezado ni saludo."
    )


def _proveedor() -> str:
    settings = get_settings()
    if getattr(settings, "anthropic_api_key", ""):
        return PROVEEDOR_ANTHROPIC
    if getattr(settings, "openai_api_key", ""):
        return PROVEEDOR_OPENAI
    raise ResumenNoDisponible(
        "resumen semanal no disponible: no hay ANTHROPIC_API_KEY ni OPENAI_API_KEY."
    )


def _redactar(insumos: dict) -> dict:
    """Despacha al proveedor disponible y devuelve texto + consumo.

    Aislada en su propia función a propósito: es el único punto que gasta plata, así
    que los tests la parchan y cuentan las llamadas. Si se inlinea en
    `resumen_semanal`, se pierde el test que garantiza el gasto cero.
    """
    if _proveedor() == PROVEEDOR_ANTHROPIC:
        return _redactar_anthropic(insumos)
    return _redactar_openai(insumos)


# --------------------------------------------------------------------------- #
# Guardarraíl de cifras — la regla 1 del prompt, verificada y no solo pedida
# --------------------------------------------------------------------------- #
# El prompt prohíbe inventar números. Medido sobre 10 corridas por modelo, igual pasa:
# 3 veces con Sonnet 5, 1 con Haiku 4.5. Son pocas, pero una cifra falsa firmada por
# la DAI en un tablero institucional no es un defecto de estilo — y detectarla es
# barato, porque los números válidos están todos en los insumos.
#
# La verificación es SINTÁCTICA a propósito: no le pregunta a otro modelo si el texto
# está bien (eso sería tapar un problema de confiabilidad con más de lo mismo), sino
# que compara contra el dato. Lo que no está en los insumos, no se pudo derivar.
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def _norm(valor) -> set[str]:
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return set()
    # El texto puede redondear ("58,7" -> "59") y puede citar un delta en positivo
    # aunque el dato sea negativo ("bajó 9,6" a partir de -9,6).
    return {f"{f:.1f}", f"{round(f):.1f}", f"{abs(f):.1f}", f"{round(abs(f)):.1f}"}


def _cifras_del_texto(texto: str) -> set[str]:
    out: set[str] = set()
    for bruto in _NUMERO.findall(texto):
        out |= {f"{float(bruto.replace(',', '.')):.1f}"} if bruto else set()
    return out


def cifras_justificables(insumos: dict) -> set[str]:
    """Todo número que el texto PUEDE citar sin inventar nada.

    Incluye los valores de los insumos (recursivo, y también los que aparecen dentro
    de las captions), las fechas del período y los deltas contra la semana anterior,
    que las propias instrucciones piden calcular.
    """
    ok: set[str] = set()

    def caminar(x) -> None:
        if isinstance(x, dict):
            for v in x.values():
                caminar(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                caminar(v)
        elif isinstance(x, bool):
            return
        elif isinstance(x, (int, float)):
            ok.update(_norm(x))
        elif isinstance(x, str):
            ok.update(_cifras_del_texto(x))

    caminar(insumos)
    fechas = [insumos["periodo"]["desde"], insumos["periodo"]["hasta"]]
    prev = insumos.get("semana_anterior")
    if prev:
        fechas += [prev["desde"], prev["hasta"]]
        if prev.get("indice") is not None and insumos.get("indice") is not None:
            ok.update(_norm(insumos["indice"] - prev["indice"]))
    for f in fechas:
        for parte in (f.day, f.month, f.year):
            ok.update(_norm(parte))
    ok.update(_norm(repository.N_MIN_EVIDENCIA))  # el prompt lo nombra
    return ok


def cifras_no_justificadas(texto: str, insumos: dict) -> list[str]:
    """Números del texto que NO salen de los insumos. Vacío = el texto es auditable.

    ⚠️ LÍMITE CONOCIDO, y conviene saberlo antes de confiar de más. Esto detecta
    números AUSENTES de los datos, no operaciones mal hechas. Si el modelo suma dos
    publicaciones (14 + 12) y el resultado —26— aparece por casualidad en cualquier
    otro lugar de los insumos, pasa el filtro. Observado en la semana del 10/08.

    Cubrirlo del todo pediría analizar la frase, no los números, y ahí ya no habría
    una verdad contra la cual comparar. Por eso la defensa principal está en el
    prompt (regla 1: prohibido combinar cifras) y esto es la red debajo: agarra el
    caso peligroso —una cifra que no existe en ninguna parte— y deja pasar una
    aritmética correcta, que es el error barato.
    """
    return sorted(_cifras_del_texto(texto) - cifras_justificables(insumos), key=float)


def _generar_verificado(insumos: dict) -> dict:
    """Redacta y verifica las cifras. Un reintento, y después se avisa.

    Reintentar una vez sale ~0,005 USD y arregla el caso frecuente (una alucinación
    puntual). Reintentar en bucle no: si el modelo insiste, el problema no es la
    tirada — y un tablero que se cuelga esperando un texto perfecto es peor que uno
    que muestra el texto con una advertencia honesta.
    """
    generado = _redactar(insumos)
    dudosas = cifras_no_justificadas(generado["texto"], insumos)
    if dudosas:
        reintento = _redactar(insumos)
        dudosas_2 = cifras_no_justificadas(reintento["texto"], insumos)
        # Se acumula el costo de las DOS llamadas: se pagaron las dos, y el número
        # que se guarda tiene que ser lo que salió del bolsillo.
        costo = (generado["costo_usd"] or 0) + (reintento["costo_usd"] or 0)
        generado = {
            **reintento,
            "costo_usd": costo,
            "input_tokens": generado["input_tokens"] + reintento["input_tokens"],
            "output_tokens": generado["output_tokens"] + reintento["output_tokens"],
        }
        dudosas = dudosas_2
    generado["cifras_dudosas"] = dudosas
    return generado


def _redactar_anthropic(insumos: dict) -> dict:
    """Redacta con Claude vía el SDK oficial de Anthropic.

    Notas de la API que NO son obvias y ya costaron una vez:
      * `max_tokens` es un techo de seguridad; el largo lo fija la instrucción.
      * En Opus 5 el pensamiento está ON por defecto y se paga como salida. Para una
        tarea de redacción sobre datos ya calculados alcanza `effort: low`.
      * `response.content` es una LISTA de bloques y puede traer bloques `thinking`
        antes del texto. Hay que filtrar por `type == "text"`, no tomar `content[0]`.
    """
    import anthropic  # import tardío: el resto del backend no depende del SDK

    settings = get_settings()
    key = settings.anthropic_api_key
    if not key:
        raise ResumenNoDisponible("resumen semanal no disponible: falta ANTHROPIC_API_KEY.")
    modelo = getattr(settings, "percepcion_resumen_modelo", "") or MODELO_ANTHROPIC

    cliente = anthropic.Anthropic(api_key=key, timeout=TIMEOUT_SEGUNDOS)
    extra = ({"output_config": {"effort": EFFORT_ANTHROPIC}}
             if soporta_effort(modelo) else {})
    try:
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=INSTRUCCIONES,
            messages=[{"role": "user", "content": _prompt(insumos)}],
            **extra,
        )
    except anthropic.APIStatusError as exc:
        raise ResumenNoDisponible(f"Anthropic respondió {exc.status_code}: {exc}") from exc
    except anthropic.APIConnectionError as exc:
        raise ResumenNoDisponible(f"no se pudo conectar con Anthropic: {exc}") from exc

    # Una negativa por política llega como HTTP 200 con `stop_reason='refusal'`, no
    # como excepción: hay que mirarlo ANTES de leer el contenido.
    if respuesta.stop_reason == "refusal":
        raise ResumenNoDisponible("el modelo declinó redactar este resumen.")

    texto = "\n".join(
        b.text.strip() for b in respuesta.content
        if getattr(b, "type", None) == "text" and getattr(b, "text", "").strip()
    ).strip()
    if not texto:
        raise ResumenNoDisponible("el modelo no devolvió texto.")

    entrada = int(respuesta.usage.input_tokens or 0)
    salida = int(respuesta.usage.output_tokens or 0)
    uso = {"input_tokens": entrada, "output_tokens": salida}
    registrar_uso_llm(modelo, FEATURE_COSTO, uso)
    return {
        "texto": texto,
        "modelo": modelo,
        "input_tokens": entrada,
        "output_tokens": salida,
        "costo_usd": costo_estimado_usd(modelo, entrada, salida),
    }


def _redactar_openai(insumos: dict) -> dict:
    """Redacta con la Responses API de OpenAI (el resto de la Torre usa esta vía)."""
    settings = get_settings()
    key = getattr(settings, "openai_api_key", "")
    if not key:
        raise ResumenNoDisponible("resumen semanal no disponible: falta OPENAI_API_KEY.")
    modelo = getattr(settings, "openai_chat_model", "gpt-5.4-mini")

    try:
        respuesta = httpx.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "instructions": INSTRUCCIONES,
                "input": _prompt(insumos),
                "max_output_tokens": MAX_OUTPUT_TOKENS,
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
        payload = respuesta.json()
    except httpx.HTTPError as exc:
        raise ResumenNoDisponible(f"OpenAI no respondió: {exc}") from exc

    texto = _texto_de(payload)
    if not texto:
        raise ResumenNoDisponible("el modelo no devolvió texto.")

    uso = payload.get("usage") or {}
    entrada = int(uso.get("input_tokens") or uso.get("prompt_tokens") or 0)
    salida = int(uso.get("output_tokens") or uso.get("completion_tokens") or 0)
    # Best-effort y compartido con el resto de la Torre: así este feature aparece en
    # el panel de costos junto a chatbox, intake e informes, y no en una planilla aparte.
    registrar_uso_llm(modelo, FEATURE_COSTO, uso)
    return {
        "texto": texto,
        "modelo": modelo,
        "input_tokens": entrada,
        "output_tokens": salida,
        "costo_usd": costo_estimado_usd(modelo, entrada, salida),
    }


def _texto_de(payload: dict) -> str:
    """Extrae la salida de la Responses API (mismo criterio que `informe_llm`)."""
    directo = payload.get("output_text")
    if isinstance(directo, str) and directo.strip():
        return directo.strip()
    trozos: list[str] = []
    for item in payload.get("output") or []:
        for contenido in item.get("content") or []:
            if contenido.get("type") in {"output_text", "text"} and contenido.get("text"):
                trozos.append(str(contenido["text"]))
    return "\n".join(t.strip() for t in trozos if t.strip()).strip()


# --------------------------------------------------------------------------- #
# Entrada pública — el caché
# --------------------------------------------------------------------------- #
def resumen_semanal(db, write_db, *, semana_inicio: date | None = None,
                    nivel: str = "global", dimension: str | None = None,
                    forzar: bool = False, db_texto=None) -> dict:
    """Resumen de la semana para un alcance, generándolo SOLO si los datos cambiaron.

    `db` es la sesión de lectura del dashboard; `write_db` la de escritura (la curación
    ya usa ese mismo par). Son dos porque la de lectura abre con `PRAGMA query_only=ON`
    y no puede guardar el caché. `db_texto` (opcional) es la sesión del rol que puede leer
    captions; ver `insumos_semana`.
    """
    if nivel not in NIVELES:
        nivel = "global"
    if nivel == "global":
        dimension = None  # un alcance global con dimensión sería una contradicción
    semana = repository._lunes(semana_inicio) if semana_inicio else ultima_semana(db)
    base = {"hay_datos": False, "texto": None, "periodo": None,
            "alcance": {"nivel": nivel, "dimension": dimension,
                        "etiqueta": _etiqueta_alcance(nivel, dimension)},
            "desde_cache": False, "desactualizado": False, "aviso": None,
            "cifras_dudosas": [],
            "modelo": None, "costo_usd": None, "generado_en": None,
            "n_comentarios": 0, "indice": None}
    if semana is None:
        base["aviso"] = "todavía no hay datos de percepción."
        return base

    insumos = insumos_semana(db, semana_inicio=semana, nivel=nivel, dimension=dimension,
                             db_texto=db_texto)
    periodo = {"desde": semana, "hasta": semana + timedelta(days=6)}
    base["periodo"] = periodo
    if insumos is None:
        # Semana sin un solo comentario en este alcance. Se corta ACÁ, antes de
        # cualquier llamada: una semana vacía no cuesta un token.
        base["aviso"] = "no hubo comentarios en este alcance durante la semana."
        return base

    base.update({"hay_datos": True, "n_comentarios": insumos["n_comentarios"],
                 "indice": insumos["indice"]})
    hue = huella(insumos)
    fila = _fila(write_db, semana, nivel, dimension)

    if fila is not None and fila.huella == hue and not forzar:
        # El camino feliz y el más frecuente: los datos no se movieron, no se paga.
        base.update({"texto": fila.texto, "desde_cache": True, "modelo": fila.modelo,
                     "costo_usd": fila.costo_usd, "generado_en": fila.generado_en})
        return base

    try:
        generado = _generar_verificado(insumos)
    except ResumenNoDisponible as exc:
        # Degradar mostrando lo último bueno vale más que una pantalla en blanco,
        # pero hay que decir que no refleja los datos de ahora.
        if fila is not None:
            base.update({"texto": fila.texto, "desde_cache": True,
                         "desactualizado": True, "modelo": fila.modelo,
                         "costo_usd": fila.costo_usd, "generado_en": fila.generado_en,
                         "aviso": str(exc)})
        else:
            base["aviso"] = str(exc)
        return base

    fila = _guardar(write_db, fila, semana, nivel, dimension, hue, generado)
    base.update({"texto": generado["texto"], "modelo": generado["modelo"],
                 "costo_usd": generado["costo_usd"],
                 "generado_en": fila.generado_en if fila is not None else None})
    dudosas = generado.get("cifras_dudosas") or []
    if dudosas:
        # Sobrevivió al reintento. Se muestra igual —el texto es útil— pero con la
        # advertencia a la vista: quien lo lea tiene que saber qué revisar.
        base["cifras_dudosas"] = dudosas
        base["aviso"] = (
            "el texto menciona cifras que no están en los datos de la semana "
            f"({', '.join(dudosas[:5])}). Verifica antes de citarlo."
        )
    return base


def generar_tras_ingesta(*, semanas: int = 1, forzar: bool = False,
                         solo_completas: bool = False, hoy: date | None = None) -> dict:
    """Entry point para disparar la generación DESPUÉS de una ingesta.

    Es lo que llama `POST /ai-tasks/run/percepcion-resumen`, que a su vez es lo que
    dispara la última celda de `migraciones/correr_migracion.py` del worker.

    POR QUÉ EL WORKER NO ESCRIBE ESTA TABLA DIRECTO
    -----------------------------------------------
    Podría, pero traería dos problemas que este camino evita:

    * **Permisos.** El GRANT del usuario IAM del worker enumera tabla por tabla
      (ver `migraciones/PARA_ALBERTO.md`), y `percepcion_resumen_semanal` no está en
      esa lista. Escribirla desde el worker obligaría a pedirle a Alberto un GRANT
      nuevo cada vez que la Torre agregue una tabla propia.
    * **El secreto.** La API key de OpenAI vive en Secret Manager y la usa la Torre.
      Generar desde el worker la bajaría a una máquina de escritorio.

    Disparando por HTTP, la Torre crea su tabla (ya lo hace al arrancar) y escribe
    con su propia cuenta de servicio. Cero intervención de terceros.

    `semanas` regenera hacia atrás desde la última con datos: 1 = solo la última.
    Útil cuando una ingesta trae comentarios viejos y mueve semanas ya resumidas.

    `solo_completas` omite la semana en curso (la que aún no termina el domingo según
    `hoy`, por defecto la fecha local): una ingesta del lunes trae los comentarios de esa
    misma mañana y, sin esto, se resumiría una semana de pocas horas que el lunes
    siguiente habría que pagar de nuevo.
    """
    from app.services.percepcion.db import (
        PercepcionProcesoSessionLocal,
        PercepcionSessionLocal,
        PercepcionWriteSessionLocal,
    )

    db = PercepcionSessionLocal()
    wdb = PercepcionWriteSessionLocal()
    tdb = PercepcionProcesoSessionLocal()   # captions: la única lectura de texto crudo
    try:
        ultima = ultima_semana(db)
        if ultima is None:
            return {"status": "skipped", "fuente": "percepcion-resumen",
                    "reason": "no hay datos de percepción todavía.", "generados": 0}
        if solo_completas:
            # Una semana está completa cuando ya pasó su domingo: lunes + 7 <= hoy.
            hoy = hoy or date.today()
            while ultima + timedelta(days=7) > hoy:
                ultima -= timedelta(days=7)
        resultados = []
        for i in range(max(1, int(semanas))):
            semana = ultima - timedelta(days=7 * i)
            r = resumen_semanal(db, wdb, semana_inicio=semana, nivel="global",
                                forzar=forzar, db_texto=tdb)
            resultados.append({
                "semana": str(semana),
                "hay_datos": r["hay_datos"],
                # `desde_cache=True` significa que NO se pagó: los datos de esa
                # semana no cambiaron desde la última corrida.
                "regenerado": bool(r["texto"]) and not r["desde_cache"],
                "n_comentarios": r["n_comentarios"],
                "costo_usd": r["costo_usd"],
                "aviso": r["aviso"],
            })
        nuevos = [r for r in resultados if r["regenerado"]]
        return {
            "status": "ok",
            "fuente": "percepcion-resumen",
            "generados": len(nuevos),
            "costo_usd_total": round(sum(r["costo_usd"] or 0 for r in nuevos), 6),
            "semanas": resultados,
        }
    finally:
        db.close()
        wdb.close()
        tdb.close()


def _clave_dimension(dimension: str | None) -> str:
    """'' para el alcance global. Ver la nota de unicidad en el modelo: guardar NULL
    haría que el índice único no impida dos filas globales."""
    return dimension or ""


def _fila(db, semana: date, nivel: str, dimension: str | None):
    """La fila del caché para ese alcance. Determinista incluso con duplicados.

    El `ORDER BY id DESC` no sobra aunque exista el índice único: una base creada
    antes de `db._asegurar_unicidad_resumen()` puede tener duplicados heredados, y sin
    orden explícito el caché devolvería cualquiera de ellos — o sea, a veces un texto
    viejo. Con el orden, siempre gana el más reciente.
    """
    clave = _clave_dimension(dimension)
    return db.execute(
        select(PercepcionResumenSemanal)
        .where(
            PercepcionResumenSemanal.semana_inicio == semana,
            PercepcionResumenSemanal.nivel == nivel,
            # `or_` cubre las filas heredadas que todavía tengan NULL en una base
            # donde la normalización no pudo correr (motor sin DDL, permisos).
            or_(PercepcionResumenSemanal.dimension == clave,
                PercepcionResumenSemanal.dimension.is_(None) if clave == "" else false()),
        )
        .order_by(PercepcionResumenSemanal.id.desc())
    ).scalars().first()


def _guardar(db, fila, semana: date, nivel: str, dimension: str | None,
             hue: str, generado: dict):
    """UPSERT: una fila por (semana, alcance).

    Se actualiza en vez de acumular versiones porque lo que interesa es el resumen
    VIGENTE de esa semana; el histórico de gasto ya queda en `llm_usage`, que es su
    lugar y no obliga a esta tabla a crecer sin techo.
    """
    try:
        if fila is None:
            fila = PercepcionResumenSemanal(
                semana_inicio=semana, nivel=nivel,
                dimension=_clave_dimension(dimension))
            db.add(fila)
        fila.huella = hue
        fila.texto = generado["texto"]
        fila.modelo = generado["modelo"]
        fila.input_tokens = generado["input_tokens"]
        fila.output_tokens = generado["output_tokens"]
        fila.costo_usd = generado["costo_usd"]
        fila.generado_en = datetime.utcnow()
        db.commit()
        return fila
    except IntegrityError:
        # Otra request ganó la carrera y ya insertó la fila. No es un error: los dos
        # textos describen los mismos datos. Se pisa la fila existente con este —
        # ya se pagó por él— en vez de descartarlo o duplicar.
        try:
            db.rollback()
            existente = _fila(db, semana, nivel, dimension)
            if existente is not None:
                existente.huella = hue
                existente.texto = generado["texto"]
                existente.modelo = generado["modelo"]
                existente.input_tokens = generado["input_tokens"]
                existente.output_tokens = generado["output_tokens"]
                existente.costo_usd = generado["costo_usd"]
                existente.generado_en = datetime.utcnow()
                db.commit()
                return existente
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return None
    except Exception:
        # No poder cachear degrada a "se regenera la próxima" (más caro), nunca a
        # perder el resumen que ya se pagó y se está por devolver.
        try:
            db.rollback()
        except Exception:
            pass
        return None
