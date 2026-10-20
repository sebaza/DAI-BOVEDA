"""Léxico institucional de TÉRMINOS BAJO VIGILANCIA (paro, toma, petitorio…).

Por qué existe: el clasificador temático reparte los comentarios en 8 cajas, y la
conversación de conflicto no tiene caja propia — se diluye entre "académico",
"organización estudiantil" y "otros". Medido sobre el corpus real: el 21/04/2026,
SEIS SEMANAS antes del paro del 03/06, hay en un solo día rumor de paro
("al final no caxe, hay paro o no"), rechazo ("No yapo no tiren paro"), petitorios
de seguridad pendientes y una convocatoria a asamblea general. El tablero no
mostraba nada de eso. Este módulo hace visible ese vocabulario, sin depender de
que el clasificador acierte.

Es un módulo HOJA a propósito: no importa nada del feature: `repository` lo importa
a él. Así el léxico se prueba solo y no arrastra el motor del índice.

    ⚠️  EL LÉXICO NO TOCA EL ÍNDICE. La fórmula canónica
    (50 + 50·(Σpos − Σneg)/den) queda intacta y comparable con lo ya reportado.
    Estas menciones alimentan el bloque "Señales bajo vigilancia" y la SEVERIDAD
    de las anomalías — nada más.

Reglas de construcción (aprendidas a los golpes contra el corpus real):

1. LISTA EXPLÍCITA DE FORMAS, NUNCA REGEX CÓMODA. El patrón `par[oa]s?` parece
   razonable y matchea 153 comentarios de 2.790… casi todos por "para", la
   preposición. Una familia mal escrita infla el indicador en silencio y nadie se
   entera nunca. Cada forma se escribe entera.

2. LAS PALABRAS AMBIGUAS SOLO CUENTAN EN FRASE. "tomar" en el corpus es
   mayoritariamente "tomar asignaturas" o "se tomaría un matcha"; "toma"/"tomas"
   (sustantivo) en cambio sí son señal. Por eso el verbo vive en `frases` y el
   sustantivo en `formas`.

3. LAS FRASES QUE SECUESTRAN UNA FORMA SE BORRAN ANTES DE MATCHEAR (`FRASES_AMBIGUAS`).
   "marcha blanca" y "poner en marcha" son habla institucional corriente y no
   tienen nada que ver con una movilización. Se quita la FRASE, no la palabra:
   quien hable de una marcha de verdad sigue contando. Mismo criterio que ya usa
   la nube con los artefactos del scraper.

4. SE INCLUYEN TÉRMINOS SIN EVIDENCIA TODAVÍA (huelga, plebiscito, protesta…).
   Esto es vigilancia: tiene que estar listo para lo que aún no pasó. No cuestan
   nada mientras no aparezcan.

Frecuencias medidas sobre percepcion_real.db (2.790 comentarios, 2022-2026):
    paro 16 · paros 2 · paralizacion 4 · paralizar 2   → familia `paro`   ~20
    toma 12 · tomas 1 · "vamos a tomar" 1              → familia `toma`   ~13
    movilizacion 3 · marcha 2 · marchas 2              → `movilizacion`   ~7
    petitorio 3 · petitorios 1                         → `petitorio`      ~4
    asamblea 2 · votacion 1                            → `asamblea`       ~3
    huelga, plebiscito, protesta, manifestacion, funa  → 0 (preventivos)
"""
from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------- #
# Ruido de ingesta: lo que el scraper de Instagram pega al comentario y NO
# escribió nadie. Vive acá (módulo hoja) y `repository` lo importa, para que la
# nube de palabras y el léxico compartan una sola definición.
# --------------------------------------------------------------------------- #
FRASES_SCRAPER = re.compile(
    r"comments?\s+from\s+facebook|see\s+translation|view\s+(all\s+)?\d*\s*repl(y|ies)",
    re.IGNORECASE,
)

# Frases donde una forma del léxico aparece con OTRO significado. Se borran del
# texto antes de matchear, así la palabra sigue viva para el resto de los usos.
# "marcha blanca" y "poner en marcha" son habla institucional de todos los días.
FRASES_AMBIGUAS = re.compile(
    r"marcha blanca|sobre la marcha|poner en marcha|puesta en marcha|en marcha blanca"
    r"|marcha atras"
    r"|toma nota|toma en cuenta|toma conciencia|toma asiento|toma once|toma agua",
)

# Solo vocales acentuadas: la Ñ se respeta. Colapsarla fusiona palabras distintas
# ("toño" con "tono"), y en español es una letra propia, no una "n" con adorno.
_SIN_TILDES = str.maketrans("áéíóúü", "aeiouu")

# 3+ repeticiones del mismo carácter → 1. Resuelve el alargamiento expresivo de
# redes ("tomaaaaaa", "marchaaa" están literalmente en el corpus). El umbral es 3
# y no 2 a propósito: con 2 se romperían "carro", "llave", "arroz", "innovacion".
_ALARGAMIENTO = re.compile(r"(.)\1{2,}")


def normalizar(texto: str | None) -> str:
    """Texto listo para matchear: minúsculas, sin tildes, sin ruido, sin alargues.

    Es IDEMPOTENTE sobre las formas del léxico (los tests lo verifican): si una
    forma se escribiera con tilde o mayúscula nunca matchearía y el fallo sería mudo.
    """
    if not texto:
        return ""
    t = unicodedata.normalize("NFC", texto).lower().translate(_SIN_TILDES)
    t = FRASES_SCRAPER.sub(" ", t)
    t = _ALARGAMIENTO.sub(r"\1", t)
    t = FRASES_AMBIGUAS.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------- #
# Las familias. `formas` = palabras que cuentan SOLAS (inequívocas en contexto
# universitario). `frases` = secuencias que habilitan palabras que solas serían
# ruido. Todo en minúscula y sin tildes: se compara contra texto ya normalizado.
# --------------------------------------------------------------------------- #
FAMILIAS: list[dict] = [
    {
        "clave": "paro",
        "etiqueta": "Paro / paralización",
        "formas": [
            "paro", "paros", "paralizacion", "paralizaciones", "paralizar",
            "paralizado", "paralizados", "paralizada", "paralizadas", "paralizando",
        ],
        "frases": ["hay paro", "en paro", "tiren paro", "tirar paro",
                   "se va a paro", "vamos a paro"],
    },
    {
        "clave": "toma",
        "etiqueta": "Toma / ocupación",
        # "toma"/"tomas" (sustantivo) son señal; "tomar" (verbo) NO — en el corpus
        # es casi siempre "tomar asignaturas" o "tomarse un café". El verbo solo
        # cuenta dentro de una frase que lo desambigüe.
        "formas": ["toma", "tomas"],
        "frases": ["vamos a tomar", "tomar la universidad", "tomar la u",
                   "tomarse la", "se tomaron la", "se toma la", "tomar el campus"],
    },
    {
        "clave": "movilizacion",
        "etiqueta": "Movilización",
        "formas": [
            "movilizacion", "movilizaciones", "movilizar", "movilizados",
            "movilizadas", "marcha", "marchas", "marchar",
            "huelga", "huelgas", "protesta", "protestas",
            "manifestacion", "manifestaciones", "funa", "funas",
        ],
        "frases": ["salir a la calle", "corte de calle"],
    },
    {
        "clave": "petitorio",
        "etiqueta": "Petitorio / demandas",
        "formas": ["petitorio", "petitorios", "pliego", "pliegos"],
        "frases": ["pliego de demandas", "mesa de negociacion"],
    },
    {
        "clave": "asamblea",
        "etiqueta": "Asamblea / votación",
        "formas": [
            "asamblea", "asambleas", "plebiscito", "plebiscitos",
            "votacion", "votaciones",
        ],
        "frases": ["asamblea general", "consulta estudiantil"],
    },
]

ETIQUETAS_FAMILIA: dict[str, str] = {f["clave"]: f["etiqueta"] for f in FAMILIAS}

# Una regex por familia con todas sus formas y \b a los costados. Se compila una
# sola vez: `detectar` corre sobre cada comentario del período.
_PATRONES: dict[str, re.Pattern] = {
    f["clave"]: re.compile(r"\b(?:" + "|".join(sorted(f["formas"], key=len, reverse=True)) + r")\b")
    for f in FAMILIAS
    if f["formas"]
}


def claves() -> list[str]:
    """Claves de familia, en el orden de declaración."""
    return [f["clave"] for f in FAMILIAS]


def detectar(texto: str | None) -> set[str]:
    """Familias del léxico presentes en el comentario.

    Devuelve CLAVES, no ocurrencias: un comentario que repite "paro" cinco veces
    aporta una sola mención, igual que la nube cuenta comentarios y no palabras.
    Lo que se mide es cuánta gente lo dice.
    """
    t = normalizar(texto)
    if not t:
        return set()
    encontradas = set()
    for f in FAMILIAS:
        clave = f["clave"]
        patron = _PATRONES.get(clave)
        if patron is not None and patron.search(t):
            encontradas.add(clave)
            continue
        if any(frase in t for frase in f["frases"]):
            encontradas.add(clave)
    return encontradas
