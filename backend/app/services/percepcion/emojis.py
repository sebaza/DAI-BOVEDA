"""Emojis -> palabras en español, SOLO para el texto que se embebe en los subtemas.

POR QUÉ
-------
El modelo de embeddings tokeniza los emojis pero los ve casi iguales entre sí (~0,81 de
coseno): 👏, 😡 y 😭 pesan lo mismo y el TONO del comentario se pierde. Traducidos a una
palabra ("aplausos", "enojo", "tristeza") el modelo sí los distingue.

QUÉ NO TOCA
-----------
No cambia los tokens guardados (`derivados.tokenizar`: etiquetas y umbrales anti-PII se
calculan sobre ellos) ni el puntaje de sentimiento. Se usa únicamente en `subtemas.limpiar`.

El diccionario es a mano y corto (los emojis que más aparecen en los comentarios reales,
más algunos de tono claro que casi no salen). Un emoji que no está acá se deja tal cual.
Para sumar uno basta agregar una línea en `_GRUPOS`.
"""
from __future__ import annotations

# palabra -> emojis que la dicen. Se escribe por palabra para que se pueda revisar el tono.
_GRUPOS: dict[str, str] = {
    "aplausos": "👏",
    "celebración": "🙌🥳🎉🎊",
    "amor": "❤♥💕💖💗💓❣🩷🧡💛💚💙🩵💜🤍",
    "luto": "🖤🕯",
    "paz": "🕊",
    "cariño": "🫶🫰",
    "abrazo": "🫂🤗",
    "gracias": "🙏",
    "me encanta": "😍🥰😘",
    "beso": "💋",
    "genial": "🔥",
    "increíble": "🤩",
    "brillo": "✨🌟💫",
    "fuerza": "💪",
    "tristeza": "😢😭😔😞",
    "pena": "🥺",
    "emoción": "🥹",
    "corazón roto": "💔",
    "risa": "😂🤣",
    "sonrisa": "😁😊🙂☺",
    "buena onda": "😎",
    "rico": "😋",
    "sorpresa": "😮",
    "susto": "😱",
    "enojo": "😡🤬😠😤",
    "fastidio": "🙄",
    "burla": "🤡",
    "rechazo": "👎",
    "aprobación": "👍",
    "atención": "👀",
    "llamado": "🗣",
    "mascota": "🐾🐶",
    "fumar": "🚬",
    "flores": "🌹💐",
    "enfermo": "🤧",
    "coqueteo": "🫦",
}

EMOJI_PALABRAS: dict[str, str] = {e: palabra for palabra, emojis in _GRUPOS.items() for e in emojis}

# Se descartan siempre: tonos de piel, selectores de variación, signos de género (vienen
# pegados con ZWJ a otro emoji) e indicadores regionales (las dos mitades de una bandera).
_DESCARTADOS = (
    {chr(c) for c in range(0x1F3FB, 0x1F400)}
    | {"️", "︎", "♀", "♂"}
    | {chr(c) for c in range(0x1F1E6, 0x1F200)}
)
_ZWJ = "‍"


def emojis_a_palabras(texto: str | None) -> str:
    """Reemplaza los emojis conocidos por su palabra; deja los demás como están.

    Un emoji unido con ZWJ a otro (❤️‍🩹) cuenta como el primero: la pieza que se le pega se
    descarta. Las repeticiones seguidas de la misma palabra ("👏👏👏", "❤💕") se juntan en
    una. Devuelve el texto con los espacios normalizados.
    """
    if not texto:
        return ""
    partes: list[str] = []           # trozos de texto y palabras, en orden
    es_palabra: list[bool] = []
    unir = False                     # el último emoji era conocido y venía un ZWJ
    ultimo_mapeado = False
    for ch in texto:
        if ch in _DESCARTADOS:
            continue
        if ch == _ZWJ:
            unir = ultimo_mapeado
            continue
        if unir:                     # pieza pegada con ZWJ a un emoji conocido
            unir = False
            continue
        palabra = EMOJI_PALABRAS.get(ch)
        ultimo_mapeado = palabra is not None
        if palabra is None:
            partes.append(ch)
            es_palabra.append(False)
            continue
        # Repetición: la palabra anterior (saltando espacios) es la misma.
        j = len(partes) - 1
        while j >= 0 and not es_palabra[j] and partes[j].isspace():
            j -= 1
        if j >= 0 and es_palabra[j] and partes[j] == palabra:
            continue
        partes.append(palabra)
        es_palabra.append(True)
    return " ".join("".join(f" {p} " if w else p for p, w in zip(partes, es_palabra)).split())
