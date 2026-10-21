"""Derivados del texto crudo: tokens, familias del léxico y rasgos de las captions.

POR QUÉ EXISTE (Fase 3b)
------------------------
La API corre con un rol de base de datos que NO puede leer `percepcion_comentario.texto`
ni `percepcion_publicacion.caption`. Todo lo que la nube de palabras, los términos bajo
vigilancia, el impacto de palabras, las palabras destacadas, las anomalías y el análisis
de comunicación necesitan del texto se calcula ACÁ, una vez, con un proceso privilegiado
(`scripts/precalcular_tokens_percepcion.py`), y se guarda en tablas derivadas
(`PercepcionComentarioToken`, `PercepcionComentarioFamilia`, `PercepcionPublicacionRasgo`).

Es un módulo HOJA: solo importa `lexico`. La regla es UNA función por derivado
(`tokenizar`, `familias_de`, `rasgos_caption`): el precálculo y cualquier otro camino
la comparten, así no pueden divergir.

Qué se guarda y qué no: por comentario, el CONJUNTO de palabras (sin repetición ni orden)
y las familias del léxico que menciona. Con eso las vistas reproducen exactamente los
conteos de antes (todas cuentan comentarios, no repeticiones); el texto no se puede
reconstruir. Los filtros que dependen del pedido (`excluir`, el mínimo de frecuencia anti-PII,
la agrupación de variantes) se siguen aplicando al consultar, sobre los tokens guardados.
"""
from __future__ import annotations

import re

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.services.percepcion import lexico

# --------------------------------------------------------------------------- #
# Tokenizador (movido tal cual desde `repository`; no cambiar sin re-precalcular).
# --------------------------------------------------------------------------- #
# Stopwords ES/EN mínimas. No se usa una librería a propósito: agregar una
# dependencia por una lista de palabras no se paga, y acá conviene poder sumar
# términos propios de la UCN sin pelear con el diccionario de nadie.
STOPWORDS = {
    # Español: artículos, preposiciones, pronombres, verbos vacíos.
    "a", "al", "algo", "algun", "alguna", "algunas", "alguno", "algunos", "ante",
    "antes", "aqui", "asi", "aun", "aunque", "bien", "cada", "casi", "como", "con",
    "contra", "cual", "cuales", "cuando", "cuanto", "de", "del", "desde", "donde",
    "dos", "el", "ella", "ellas", "ello", "ellos", "en", "entre", "era", "eran",
    "eres", "es", "esa", "esas", "ese", "eso", "esos", "esta", "estan", "estas",
    "este", "esto", "estos", "estoy", "fue", "fueron", "ha", "haber", "habia",
    "hace", "hacen", "hacer", "hasta", "hay", "la", "las", "le", "les", "lo",
    "los", "mas", "me", "mi", "mis", "mucho", "muy", "nada", "ni", "no", "nos",
    "nosotros", "o", "otra", "otras", "otro", "otros", "para", "pero", "poco",
    "por", "porque", "pue", "pues", "que", "se", "sea", "ser", "si", "sido",
    "sin", "sobre", "solo", "son", "su", "sus", "tambien", "tan", "tanto", "te",
    "tiene", "tienen", "toda", "todas", "todo", "todos", "tu", "tus", "un", "una",
    "unas", "uno", "unos", "ya", "yo", "él", "más", "sí", "está", "están", "qué",
    "cómo", "dónde", "así", "aún", "sólo", "les", "muchas", "muchos", "vez",
    "ahora", "siempre", "nunca", "puede", "pueden", "va", "van", "hacia", "eso",
    # Inglés: los comentarios mezclan idioma.
    "the", "and", "for", "you", "your", "with", "this", "that", "are", "was",
    "have", "has", "not", "but", "all", "can", "will", "from", "they", "there",
    "what", "when", "who", "how", "its", "it's", "our", "out", "get", "just",
    # ARTEFACTOS DE SCRAPING de Instagram. Sin esto encabezan la nube y tapan
    # todo: aparecen en casi cada comentario largo y NO los escribió nadie.
    # Visto en datos reales: "…fiestas lujosas si See translation View all 8 replies".
    "see", "translation", "view", "reply", "replies", "more", "ver", "traduccion",
    "traducción", "respuestas", "respuesta", "editado", "edited",
    # Saludos y muletillas sin señal: encabezan la nube y no dicen nada.
    "hola", "holi", "buenas", "jaja", "jajaja", "jsjs", "wena",
}
# OJO: acá NO van "cookie"/"facebook". Se filtraron en una primera versión por
# parecer chrome del scraper y fue un FALSO POSITIVO: "Cookie" es la mascota de
# la UCN y aparece en 7 comentarios reales ("Parece todo un caballero el Cookie").
# Los artefactos de scraping se atacan por FRASE (abajo), no por palabra suelta —
# borrar una palabra por sospecha se lleva puesto contenido legítimo.

# Frases exactas que el scraper pega al comentario. Se quitan del texto ANTES de
# tokenizar, así "Seca! comments from Facebook" aporta "seca" y nada más, sin
# vetar "facebook" para quien lo mencione de verdad.
#
# La definición vive en `lexico` (módulo hoja) porque el conteo de términos
# críticos necesita exactamente la misma limpieza: una sola lista, no dos que se
# desincronizan en silencio.
FRASES_SCRAPER = lexico.FRASES_SCRAPER

# Los handles de Instagram que el scraper deja pegados al texto NO llevan "@"
# salvo el primero: al etiquetar a varias personas queda
# "Participando:B tote.mny_ cldliio_" — donde el comentario real es "Participando:B".
# En español no existen palabras con "_", dígitos ni punto interno, así que ese
# patrón identifica handles sin falsos positivos. Cubre smacaya_, tote.mny_,
# av_angamos, vixoo94_, _fab.iu_.
# NO cubre los handles que son letras puras (ignaciamilann, jmanuuu): para esos
# está HANDLES_CONOCIDOS y el clic-para-excluir del panel. El arreglo de fondo
# es que la ingesta separe las menciones del cuerpo del comentario.
PATRON_HANDLE = re.compile(r"[_\d]|\w\.\w")

# Nombres de usuario que el scraper dejó PEGADOS al texto sin "@" (el regex de
# menciones no los agarra). En datos reales aparecieron "smacaya" (n=9) y
# "cldliio" (n=6) entre las palabras más frecuentes: son cuentas de personas, o
# sea PII en pantalla.
#
# Deliberadamente NO se filtra con un diccionario español: borraría jerga real y
# valiosa como "seca" o "porfa", que SÍ son señal. Es una lista curada, y la
# solución de fondo es que el worker separe el handle del cuerpo al ingestar.
HANDLES_CONOCIDOS = {"smacaya", "cldliio"}


def tokenizar(texto: str, excluir: set[str] | None = None) -> list[str]:
    """Palabras normalizadas de un comentario, listas para contar.

    Descarta, en este orden: URLs, @menciones (son PII — identifican cuentas),
    emojis/puntuación, tokens de <3 letras, números sueltos y stopwords.
    Los #hashtags SÍ quedan (sin el #): suelen ser el tema real del comentario.
    Conserva tildes y ñ: "año" y "ano" no son la misma palabra, y la nube se lee
    en español.
    """
    if not texto:
        return []
    limpio = FRASES_SCRAPER.sub(" ", texto.lower())
    limpio = re.sub(r"https?://\S+|www\.\S+", " ", limpio)
    limpio = re.sub(r"@[\w.]+", " ", limpio)          # menciones = PII
    # Handles pegados SIN "@": se descartan mientras el token conserva "_"/dígitos
    # /punto, o sea ANTES de la limpieza de caracteres que borraría esa pista.
    limpio = " ".join(
        "" if PATRON_HANDLE.search(tok) else tok
        for tok in limpio.split()
    )
    limpio = limpio.replace("#", " ")
    limpio = re.sub(r"[^a-záéíóúüñ\s]", " ", limpio)  # deja solo letras ES
    vetadas = STOPWORDS | HANDLES_CONOCIDOS | (excluir or set())
    salida = []
    for palabra in limpio.split():
        if len(palabra) < 3 or palabra in vetadas:
            continue
        salida.append(palabra)
    return salida




def tokens_de(texto: str | None) -> set[str]:
    """Palabras ÚNICAS de un comentario: lo que se guarda por comentario.

    `set()` porque todas las vistas miden cuánta GENTE dice una palabra, no cuántas veces
    la repite. El `excluir` del pedido no entra acá: se aplica al consultar.
    """
    return set(tokenizar(texto or ""))


def familias_de(texto: str | None) -> set[str]:
    """Familias del léxico de vigilancia que menciona el comentario (`lexico.detectar`)."""
    return lexico.detectar(texto)


# --------------------------------------------------------------------------- #
# Rasgos de la caption (los usa `comunicacion`; antes los calculaba al vuelo).
# --------------------------------------------------------------------------- #
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")

RASGOS_CAPTION = ("emojis_3_o_mas", "menciona_cuentas", "hashtags_3_o_mas",
                  "hace_una_pregunta", "texto_largo", "sin_texto")


def rasgos_caption(caption: str | None) -> dict[str, bool]:
    """Rasgos observables de una caption. `None` equivale a caption vacía."""
    cap = caption or ""
    return {
        "emojis_3_o_mas": len(EMOJI.findall(cap)) >= 3,
        "menciona_cuentas": "@" in cap,
        "hashtags_3_o_mas": cap.count("#") >= 3,
        "hace_una_pregunta": "?" in cap,
        "texto_largo": len(cap) > 500,
        "sin_texto": len(cap.strip()) < 20,
    }


# --------------------------------------------------------------------------- #
# Reconstrucción completa.
# --------------------------------------------------------------------------- #
LOTE = 5000


def _insertar(db: Session, modelo, filas: list[dict]) -> None:
    for i in range(0, len(filas), LOTE):
        db.execute(insert(modelo), filas[i:i + LOTE])


def reconstruir(db: Session) -> dict[str, int]:
    """Vacía y vuelve a llenar las tablas derivadas, en UNA transacción.

    Necesita LEER `texto` y `caption`: se llama con una sesión del rol privilegiado. No
    hace commit: lo hace quien llama (el script), así un fallo a medias —o un
    `rollback()`— deja intactas las tablas anteriores. Idempotente: dos corridas seguidas
    dejan exactamente lo mismo.

    Devuelve los conteos: comentarios y publicaciones recorridos, y filas escritas.
    """
    from app.services.percepcion.models import (
        PercepcionComentario as C,
        PercepcionComentarioFamilia as F,
        PercepcionComentarioToken as T,
        PercepcionPublicacion as P,
        PercepcionPublicacionRasgo as R,
    )

    # Hijos primero (hay FK hacia comentario/publicación en bases que las imponen).
    for modelo in (T, F, R):
        db.execute(delete(modelo))

    n_com = n_tok = n_fam = 0
    tokens: list[dict] = []
    familias: list[dict] = []
    for cid, texto in db.execute(select(C.id, C.texto).order_by(C.id)).yield_per(2000):
        n_com += 1
        tokens += [{"comentario_id": cid, "token": t} for t in sorted(tokens_de(texto))]
        familias += [{"comentario_id": cid, "familia": f} for f in sorted(familias_de(texto))]
        if len(tokens) >= LOTE:
            n_tok += len(tokens)
            _insertar(db, T, tokens)
            tokens = []
        if len(familias) >= LOTE:
            n_fam += len(familias)
            _insertar(db, F, familias)
            familias = []
    n_tok += len(tokens)
    n_fam += len(familias)
    _insertar(db, T, tokens)
    _insertar(db, F, familias)

    rasgos = [{"publicacion_id": pid, **rasgos_caption(caption)}
              for pid, caption in db.execute(select(P.id, P.caption).order_by(P.id))]
    _insertar(db, R, rasgos)
    return {"comentarios": n_com, "tokens": n_tok, "familias": n_fam, "rasgos": len(rasgos)}
