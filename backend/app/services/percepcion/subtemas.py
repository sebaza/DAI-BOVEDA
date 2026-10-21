"""Subtemas locales: agrupa los comentarios de cada `tema` con embeddings de un modelo LOCAL.

POR QUÉ
-------
Un `tema` ("matrícula y aranceles") sigue siendo muy grueso. Acá se agrupan sus comentarios
por parecido de significado (red neuronal multilingüe que corre en este equipo, sin APIs
externas) y cada grupo recibe una etiqueta ANONIMIZADA con sus palabras más características.

QUÉ ES PÚBLICO Y QUÉ NO
-----------------------
El texto crudo solo lo lee el proceso privilegiado (`scripts/agrupar_subtemas_percepcion.py`).
La API solo ve la etiqueta y los términos, y estos se calculan sobre los TOKENS ya
guardados (`percepcion_comentario_token`) con umbrales anti-PII (ver `etiquetar`).

Es un módulo sin motor de base de datos propio: recibe la sesión y el `embedder` (una función
`list[str] -> ndarray`). `torch`/`sentence_transformers` NO se importan acá (los importa el
script); `scikit-learn` se importa perezosamente dentro de `agrupar`.
"""
from __future__ import annotations

import math
import re
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from typing import Callable, Iterable

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.services.percepcion import derivados

OTROS = -1                       # cluster residual (los demasiado chicos)
ETIQUETA_OTROS = "Otros"

# Umbrales anti-PII de las etiquetas: un término sale en pantalla solo si lo dicen
# varias personas distintas, en varios comentarios, y no es lo que dice casi todo el tema.
MIN_COMENTARIOS_TERMINO = 5
MIN_AUTORES_TERMINO = 3
MIN_LETRAS_TERMINO = 4
MAX_LETRAS_TERMINO = 30      # más largo suele ser basura del scraper, no una palabra
LARGO_ETIQUETA = 120         # = percepcion_subtema.etiqueta String(120)
MAX_FRACCION_TEMA = 0.7          # más allá no distingue subtemas (y puede ser una plantilla)
MIN_EN_CLUSTER = 2
TOP_TERMINOS = 3
MUESTRA_SILUETA = 5000

_URL = re.compile(r"https?://\S+|www\.\S+")
_MENCION = re.compile(r"@[\w.]+")


def limpiar(texto: str | None) -> str:
    """Texto listo para embeber: sin frases del scraper, URLs, @menciones ni handles."""
    if not texto:
        return ""
    t = derivados.FRASES_SCRAPER.sub(" ", texto)
    t = _URL.sub(" ", t)
    t = _MENCION.sub(" ", t)
    return " ".join(p for p in t.split() if not derivados.PATRON_HANDLE.search(p))


_LETRAS = re.compile(r"[a-záéíóúüñ]+")


def usuarios_mencionados(textos: Iterable[str | None]) -> set[str]:
    """Handles que alguien escribió como @mención en el corpus, en las formas que el
    tokenizador podría dejar: completo, pegado sin signos y sus tramos de >= 4 letras.

    ANTI-PII: en las respuestas de Instagram el mismo usuario aparece también SIN la @
    ("jofloressc gracias"), y ahí el tokenizador lo deja pasar como palabra.
    """
    salida: set[str] = set()
    for texto in textos:
        for m in _MENCION.finditer(texto or ""):
            handle = m.group()[1:].lower().strip(".")
            if not handle:
                continue
            tramos = _LETRAS.findall(handle)
            salida.add(handle)
            salida.add("".join(tramos))
            salida.update(t for t in tramos if len(t) >= MIN_LETRAS_TERMINO)
    salida.discard("")
    return salida


_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|[.!?¡¿\n]")
MIN_MAYUSCULAS_PROPIO = 3
FRACCION_MAYUSCULAS_PROPIO = 0.3


def nombres_propios(textos: Iterable[str]) -> set[str]:
    """Palabras (en minúscula) que la gente escribe como nombre propio.

    ANTI-PII: los umbrales por frecuencia no frenan un nombre que muchos repiten ("Juan
    Morales"), así que se veta lo que aparece con mayúscula inicial A MITAD de frase en
    al menos 3 ocasiones y en >= 30 % de sus apariciones a mitad de frase. Se ignoran el
    inicio de frase y las palabras en MAYÚSCULAS sostenidas (énfasis, siglas). Veta
    también lugares, que es el lado seguro del error.
    """
    mayus: Counter = Counter()
    total: Counter = Counter()
    for texto in textos:
        inicio = True
        for m in _PALABRA.finditer(texto or ""):
            p = m.group()
            if p in ".!?¡¿\n":
                inicio = True
                continue
            if not inicio and not (p.isupper() and len(p) > 1):
                clave = p.lower()
                total[clave] += 1
                if p[0].isupper():
                    mayus[clave] += 1
            inicio = False
    return {p for p, n in mayus.items()
            if n >= MIN_MAYUSCULAS_PROPIO and n / total[p] >= FRACCION_MAYUSCULAS_PROPIO}


# --------------------------------------------------------------------------- #
# Agrupación.
# --------------------------------------------------------------------------- #
def k_minimo(n: int, *, k_max: int = 8, min_tamano: int = 8) -> int:
    """Piso de k para un tema de `n` comentarios: ~sqrt(n / 40), entre 2 y k_max.

    La silueta casi siempre prefiere k=2 en texto sin estructura fuerte, y dos mitades no
    son subtemas útiles; el piso crece con el tema. Nunca exige más clusters de los que
    caben con `min_tamano` comentarios cada uno.
    """
    piso = max(2, round((n / 40) ** 0.5))
    return max(2, min(piso, k_max, n // max(1, min_tamano)))


def agrupar(embeddings: np.ndarray, *, k_max: int = 8, min_tamano: int = 8,
            semilla: int = 0) -> list[int]:
    """Etiqueta de cluster por fila. Elige k (k_minimo..k_max) por mejor silueta coseno.

    Un tema con menos de `2 * min_tamano` comentarios no se parte (todo cluster 0). Los
    clusters de menos de `min_tamano` se funden en `OTROS` (-1); los demás se numeran
    0..m-1 del más grande al más chico. Determinista para una misma `semilla`.
    """
    X = np.asarray(embeddings, dtype=float)
    n = len(X)
    if n == 0:
        return []
    if n < 2 * min_tamano:
        return [0] * n

    from sklearn.cluster import KMeans            # perezoso: la API no lo necesita
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.metrics import silhouette_score

    norma = np.linalg.norm(X, axis=1, keepdims=True)
    X = X / np.where(norma == 0, 1.0, norma)

    mejor, mejor_s = None, -2.0
    desde = k_minimo(n, k_max=k_max, min_tamano=min_tamano)
    for k in range(desde, min(k_max, n - 1) + 1):
        with warnings.catch_warnings():      # puntos duplicados: k efectivo menor, no es un error
            warnings.simplefilter("ignore", ConvergenceWarning)
            etiquetas = KMeans(n_clusters=k, n_init=10, random_state=semilla).fit_predict(X)
        if len(set(etiquetas)) < 2:
            continue
        s = float(silhouette_score(
            X, etiquetas, metric="cosine", random_state=semilla,
            sample_size=MUESTRA_SILUETA if n > MUESTRA_SILUETA else None))
        if s > mejor_s + 1e-9:
            mejor, mejor_s = etiquetas, s
    if mejor is None:
        return [0] * n

    tamanos = Counter(int(c) for c in mejor)
    grandes = sorted((c for c, t in tamanos.items() if t >= min_tamano),
                     key=lambda c: (-tamanos[c], c))
    if not grandes:
        return [0] * n
    nuevo = {c: i for i, c in enumerate(grandes)}
    return [nuevo.get(int(c), OTROS) for c in mejor]


# --------------------------------------------------------------------------- #
# Etiquetas anonimizadas.
# --------------------------------------------------------------------------- #
def etiquetar(tokens_por_comentario: dict[int, set[str]],
              autores_por_comentario: dict[int, str],
              asignacion: dict[int, int],
              excluir: set[str] | frozenset[str] = frozenset(),
              es_palabra: Callable[[str], bool] | None = None) -> dict[int, tuple[str, list[str]]]:
    """Etiqueta y términos de cada cluster de UN tema, con TF-IDF por clase.

    ANTI-PII: un término califica solo si aparece en >= 5 comentarios Y de >= 3 autores
    distintos en todo el tema, tiene >= 4 letras, no es stopword y no lo dice más del 70 %
    del tema. Etiqueta = hasta 3 términos unidos por " · "; si ninguno califica, "Subtema N".
    """
    n_tema = len(asignacion)
    comentarios_de: dict[str, int] = Counter()
    autores_de: dict[str, set] = defaultdict(set)
    for cid in asignacion:
        for t in tokens_por_comentario.get(cid, ()):
            comentarios_de[t] += 1
            autor = autores_por_comentario.get(cid)
            if autor is not None:            # sin autor no suma como "otra persona"
                autores_de[t].add(autor)

    vetadas = derivados.STOPWORDS | derivados.HANDLES_CONOCIDOS | set(excluir)
    califican = {
        t for t, n in comentarios_de.items()
        if n >= MIN_COMENTARIOS_TERMINO
        and len(autores_de[t]) >= MIN_AUTORES_TERMINO
        and MIN_LETRAS_TERMINO <= len(t) <= MAX_LETRAS_TERMINO
        and t not in vetadas
        and n / n_tema <= MAX_FRACCION_TEMA
        and (es_palabra is None or es_palabra(t))   # p. ej. un handle escrito sin @
    }

    clusters = sorted({c for c in asignacion.values()})
    miembros: dict[int, list[int]] = defaultdict(list)
    for cid, c in asignacion.items():
        miembros[c].append(cid)

    salida: dict[int, tuple[str, list[str]]] = {}
    usadas: Counter = Counter()
    for c in clusters:
        if c == OTROS:
            salida[c] = (ETIQUETA_OTROS, [])
            continue
        en_cluster = Counter(t for cid in miembros[c]
                             for t in tokens_por_comentario.get(cid, ()) if t in califican)
        puntajes = {
            t: (n / len(miembros[c])) * math.log(1 + n_tema / comentarios_de[t])
            for t, n in en_cluster.items() if n >= MIN_EN_CLUSTER
        }
        top = [t for t, _ in sorted(puntajes.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_TERMINOS]]
        etiqueta = " · ".join(top)
        etiqueta = etiqueta[0].upper() + etiqueta[1:] if etiqueta else f"Subtema {c + 1}"
        usadas[etiqueta] += 1
        if usadas[etiqueta] > 1:
            etiqueta = f"{etiqueta} {usadas[etiqueta]}"
        etiqueta = etiqueta[:LARGO_ETIQUETA]   # un INSERT largo abortaría toda la reconstrucción
        salida[c] = (etiqueta, top)
    return salida


# --------------------------------------------------------------------------- #
# Reconstrucción completa.
# --------------------------------------------------------------------------- #
LOTE_EMBEDDING = 256


def _embeber(embedder: Callable[[list[str]], np.ndarray], textos: list[str]) -> np.ndarray:
    partes = [np.asarray(embedder(textos[i:i + LOTE_EMBEDDING]), dtype=float)
              for i in range(0, len(textos), LOTE_EMBEDDING)]
    return np.vstack(partes) if partes else np.zeros((0, 0))


def reconstruir_subtemas(db: Session, embedder: Callable[[list[str]], np.ndarray], *,
                         modelo: str, ahora: datetime, k_max: int = 8, min_tamano: int = 8,
                         semilla: int = 0, escribir: bool = True,
                         vetar: Iterable[str] = (),
                         es_palabra: Callable[[str], bool] | None = None) -> dict:
    """Vacía y vuelve a llenar `percepcion_subtema` y `percepcion_comentario_subtema`.

    Lee `texto` (sesión del rol privilegiado). No hace commit: lo hace quien llama. Con
    `escribir=False` calcula todo y no toca las tablas. Devuelve SOLO conteos.
    """
    from app.services.percepcion.models import (
        PercepcionComentario as C,
        PercepcionComentarioSubtema as CS,
        PercepcionComentarioToken as T,
        PercepcionSubtema as S,
    )

    if escribir:
        db.execute(delete(CS))
        db.execute(delete(S))

    por_tema: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    crudos: list[str | None] = []                # solo para juntar @menciones; no sale de acá
    for cid, tema, autor, texto in db.execute(
            select(C.id, C.tema, C.autor_hash, C.texto).where(C.tema.is_not(None)).order_by(C.id)):
        por_tema[tema].append((cid, autor, limpiar(texto)))
        crudos.append(texto)

    tokens: dict[int, set[str]] = defaultdict(set)
    for cid, tok in db.execute(select(T.comentario_id, T.token)):
        tokens[cid].add(tok)

    # Sobre TODO el corpus: un nombre se reconoce mejor con más apariciones.
    propios = nombres_propios(t for filas in por_tema.values() for _, _, t in filas)
    propios |= usuarios_mencionados(crudos)
    propios |= {v.strip().lower() for v in vetar if v.strip()}   # vetos a mano (apodos)
    del crudos

    resumen = {"temas": 0, "subtemas": 0, "asignados": 0, "por_tema": {}}
    for tema in sorted(por_tema):
        filas = por_tema[tema]
        emb = _embeber(embedder, [t for _, _, t in filas])
        etiquetas = agrupar(emb, k_max=k_max, min_tamano=min_tamano, semilla=semilla)
        asignacion = {cid: c for (cid, _, _), c in zip(filas, etiquetas)}
        nombres = etiquetar({cid: tokens.get(cid, set()) for cid, _, _ in filas},
                            {cid: a for cid, a, _ in filas}, asignacion, excluir=propios,
                            es_palabra=es_palabra)
        tamanos = Counter(etiquetas)
        orden = sorted(tamanos, key=lambda c: (c == OTROS, c))
        resumen["temas"] += 1
        resumen["subtemas"] += len(orden)
        resumen["asignados"] += len(filas)
        resumen["por_tema"][tema] = len(orden)
        if not escribir:
            continue
        ids: dict[int, int] = {}
        for pos, c in enumerate(orden):
            etiqueta, terminos = nombres[c]
            fila = S(tema=tema, orden=pos, etiqueta=etiqueta, terminos=terminos,
                     n_comentarios=tamanos[c], modelo=modelo, generado_en=ahora)
            db.add(fila)
            db.flush()
            ids[c] = fila.id
        derivados._insertar(db, CS, [{"comentario_id": cid, "subtema_id": ids[c]}
                                     for cid, c in asignacion.items()])
    return resumen
