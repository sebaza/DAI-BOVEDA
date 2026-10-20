"""B · ¿Qué pasa si comunicamos de otra forma?

Cuarta pregunta del plan de simulación, y la que parecía más difícil de validar. Lo
que la volvió abordable fue cambiar la variable que se intenta predecir.

LA PREGUNTA QUE SÍ SE PUEDE CONTESTAR
--------------------------------------
La versión ambiciosa —«¿qué índice va a tener este post?»— no se puede: solo 186
publicaciones tienen 5 o más comentarios, y 3 llegan a 20. El índice de un post con
cinco comentarios trae ±15 puntos de ruido.

Pero hay otra variable, y es mejor: **¿esta publicación genera conversación o no?**
Ahí la muestra es excelente — 925 publicaciones con comentarios contra 1.769 sin
ellos— y encima está limpia: se verificó contra el contador de Instagram que solo 49
de los 1.818 «sin comentarios» son un problema de ingesta. El 65 % de lo que publica
la UCN genuinamente no genera conversación, y eso es un dato, no un agujero.

EL CONTROL POR CUENTA ES LO QUE HACE VÁLIDO EL RESULTADO
--------------------------------------------------------
Comparar publicaciones con y sin una característica, a secas, mide **quién publica**
tanto como **cómo publica**. Si los reels los hacen sobre todo las cuentas de
estudiantes —que ya generan más conversación— el formato se llevaría un crédito que
no le corresponde.

Por eso cada característica se mide DOS veces: el efecto crudo y el efecto
**dentro de cada cuenta**, comparando una cuenta consigo misma. El segundo es el que
vale, y es el que se reporta primero.

Medido: el formato reel sube la probabilidad de generar conversación **+22,6 puntos
en crudo** y **+15 puntos controlando por cuenta** — gana en 19 de 24 cuentas que
publican ambos formatos. Parte del efecto crudo era, efectivamente, de la cuenta.

LO QUE ESTO NO ES
-----------------
No es causal. Que los reels correlacionen con más conversación no prueba que
convertir un post en reel la genere: puede ser que el contenido que amerita un reel
sea distinto. Es una correlación robusta y controlada, que para decidir cómo
comunicar es útil, y no es lo mismo que un experimento.
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from sqlalchemy import select

from app.services.percepcion.models import PercepcionComentario as C
from app.services.percepcion.models import PercepcionCuenta as Cu
from app.services.percepcion.models import PercepcionPublicacion as P

# Mínimos del control intra-cuenta. Una cuenta necesita publicaciones de los DOS
# lados de la característica para poder compararse consigo misma.
MIN_POR_LADO = 6
# Publicaciones mínimas para que una característica se reporte.
MIN_POR_GRUPO = 30

_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def _caracteristicas(caption: str | None, tipo: str | None,
                     fecha: datetime | None) -> dict[str, bool]:
    """Rasgos de la publicación observables ANTES de publicarla.

    ⚠️ Nada que dependa de la reacción (likes, comentarios) puede entrar acá. Serían
    fuga de datos: predecirían la conversación porque YA son la conversación, y el
    resultado no serviría para decidir cómo comunicar.
    """
    cap = caption or ""
    return {
        "es_reel": (tipo or "") == "reel",
        "emojis_3_o_mas": len(_EMOJI.findall(cap)) >= 3,
        "menciona_cuentas": "@" in cap,
        "hashtags_3_o_mas": cap.count("#") >= 3,
        "hace_una_pregunta": "?" in cap,
        "texto_largo": len(cap) > 500,
        "sin_texto": len(cap.strip()) < 20,
        "fin_de_semana": bool(fecha) and fecha.weekday() >= 5,
    }


ETIQUETAS = {
    "es_reel": "Publicar como reel",
    "emojis_3_o_mas": "Usar 3 emojis o más",
    "menciona_cuentas": "Mencionar otras cuentas (@)",
    "hashtags_3_o_mas": "Usar 3 hashtags o más",
    "hace_una_pregunta": "Hacer una pregunta",
    "texto_largo": "Texto largo (500+ caracteres)",
    "sin_texto": "Publicar casi sin texto",
    "fin_de_semana": "Publicar en fin de semana",
}


def _publicaciones(db) -> list[dict]:
    """Cada publicación con sus rasgos y si generó conversación."""
    con_comentarios = {
        pid for (pid,) in db.execute(select(C.publicacion_id).distinct()).all()
    }
    filas = db.execute(
        select(P.id, P.caption, P.tipo, P.fecha_publicacion, Cu.nombre)
        .join(Cu, Cu.id == P.cuenta_id)
    ).all()
    return [
        {"id": pid, "cuenta": cuenta or "(sin cuenta)",
         "conversa": pid in con_comentarios,
         "rasgos": _caracteristicas(caption, tipo, fecha)}
        for pid, caption, tipo, fecha, cuenta in filas
    ]


def _efecto_crudo(pubs: list[dict], rasgo: str) -> dict | None:
    con = [p for p in pubs if p["rasgos"][rasgo]]
    sin = [p for p in pubs if not p["rasgos"][rasgo]]
    if len(con) < MIN_POR_GRUPO or len(sin) < MIN_POR_GRUPO:
        return None
    p_con = sum(p["conversa"] for p in con) / len(con)
    p_sin = sum(p["conversa"] for p in sin) / len(sin)
    se = math.sqrt(p_con * (1 - p_con) / len(con) + p_sin * (1 - p_sin) / len(sin))
    return {
        "n_con": len(con), "n_sin": len(sin),
        "tasa_con": round(100 * p_con, 1), "tasa_sin": round(100 * p_sin, 1),
        "efecto_crudo": round(100 * (p_con - p_sin), 1),
        "margen": round(100 * 1.96 * se, 1),
    }


def _efecto_intra_cuenta(pubs: list[dict], rasgo: str) -> dict:
    """El mismo efecto, pero comparando cada cuenta CONSIGO MISMA.

    Es la parte que separa «este formato funciona» de «las cuentas que usan este
    formato ya eran distintas».
    """
    por_cuenta: dict[str, list[list[int]]] = {}
    for p in pubs:
        acc = por_cuenta.setdefault(p["cuenta"], [[0, 0], [0, 0]])
        i = 1 if p["rasgos"][rasgo] else 0
        acc[i][0] += int(p["conversa"])
        acc[i][1] += 1

    difs, pesos, gana = [], [], 0
    for (sin, con) in por_cuenta.values():
        if sin[1] < MIN_POR_LADO or con[1] < MIN_POR_LADO:
            continue
        d = con[0] / con[1] - sin[0] / sin[1]
        difs.append(d)
        pesos.append(sin[1] + con[1])
        gana += int(d > 0)

    if not difs:
        return {"cuentas_comparables": 0, "efecto_intra": None,
                "cuentas_a_favor": 0, "p_signos": None}

    ponderado = sum(d * w for d, w in zip(difs, pesos)) / sum(pesos)
    return {
        "cuentas_comparables": len(difs),
        "efecto_intra": round(100 * ponderado, 1),
        "cuentas_a_favor": gana,
        # Test de signos: probabilidad de ver este reparto (o más extremo) si el
        # rasgo no hiciera nada. No asume nada sobre la forma del efecto.
        "p_signos": _p_signos(gana, len(difs)),
    }


def _p_signos(exitos: int, total: int) -> float | None:
    """P(X >= exitos) bajo una binomial(total, 0.5), a dos colas."""
    if total == 0:
        return None
    k = max(exitos, total - exitos)
    cola = sum(math.comb(total, i) for i in range(k, total + 1)) / (2 ** total)
    return round(min(1.0, 2 * cola), 4)


def efecto_de_caracteristicas(db) -> dict:
    """Qué rasgos de una publicación se asocian con generar conversación.

    Ordena por el efecto INTRA-CUENTA, no por el crudo: el crudo mide quién publica
    tanto como cómo publica.
    """
    pubs = _publicaciones(db)
    total = len(pubs)
    conversan = sum(p["conversa"] for p in pubs)

    filas = []
    for rasgo in ETIQUETAS:
        crudo = _efecto_crudo(pubs, rasgo)
        if crudo is None:
            continue
        intra = _efecto_intra_cuenta(pubs, rasgo)
        filas.append({
            "rasgo": rasgo, "etiqueta": ETIQUETAS[rasgo], **crudo, **intra,
            # Significativo = el efecto crudo supera su margen Y el test de signos
            # intra-cuenta descarta el azar. Exigir las dos cosas evita quedarse con
            # un efecto que solo existe porque ciertas cuentas publican distinto.
            "solido": (abs(crudo["efecto_crudo"]) > crudo["margen"]
                       and intra["p_signos"] is not None and intra["p_signos"] < 0.05),
        })
    filas.sort(key=lambda f: -(abs(f["efecto_intra"]) if f["efecto_intra"] is not None else 0))

    return {
        "publicaciones": total,
        "con_conversacion": conversan,
        "tasa_base": round(100 * conversan / total, 1) if total else 0.0,
        "min_por_lado": MIN_POR_LADO,
        "caracteristicas": filas,
        "avisos": _avisos(filas),
    }


# --------------------------------------------------------------------------- #
# EL ENSAYO — «¿esta publicación va a generar conversación?»
# --------------------------------------------------------------------------- #
# Es lo único de la simulación que quedó en pie. La pregunta A (anticipar el índice)
# se cerró con dos evidencias y sin camino de datos: esperar las semanas que faltan
# son 5,7 años, y ni sextuplicando el volumen se pasa de ~130 semanas evaluables.
#
# Acá la variable a predecir es otra y por eso sí se puede: 6.153 publicaciones, un
# tercio con conversación, y cada rasgo medido con control intra-cuenta.

# Publicaciones mínimas para que la tasa OBSERVADA de una combinación le gane a la
# estimación aditiva. Por debajo, esa tasa oscila más que el efecto que quiere medir.
#
# ⚠️ MEDIDO SOBRE EL CORPUS REAL, Y ES LA RAZÓN DE SER DE ESTE BLOQUE: los rasgos
# INTERACTÚAN, así que sumar sus efectos se equivoca feo.
#
#     combinación        aditivo   observado   n
#     sin rasgos            —        21,5 %   1039
#     reel                 34,9 %    41,7 %     96
#     3+ emojis            25,9 %    32,7 %    715
#     reel + 3 emojis      39,3 %    56,4 %    117   <- 17 puntos de diferencia
#     reel + 3 hashtags    34,9 %    31,8 %     66   <- rinde MENOS que reel solo
#
# Un reel con emojis no rinde la suma de las dos cosas: rinde bastante más. Y los
# hashtags, que por su cuenta no hacen daño, le restan a un reel. Con 6.153
# publicaciones las combinaciones frecuentes tienen muestra de sobra, así que no hay
# ninguna razón para suponer lo que se puede contar.
MIN_COMBINACION = 30
# A partir de acá la suma de efectos deja de ser creíble y hay que decirlo.
MAX_RASGOS_SIN_AVISO = 1


def estimar_conversacion(tasa_base: float, efectos: list[dict], rasgos: set[str],
                         *, observado: dict | None) -> dict:
    """Probabilidad de que una publicación con esos rasgos genere conversación.

    DOS VÍAS, Y NO VALEN LO MISMO — por eso la respuesta declara cuál usó:

    * `observado`: la tasa real de las publicaciones que tienen EXACTAMENTE esa
      combinación. Es un dato contado, no un modelo, y por eso gana siempre que haya
      muestra. Con 6.153 publicaciones no hace falta asumir que los rasgos no
      interactúan: se cuenta.
    * `estimado`: la tasa base más los efectos intra-cuenta de los rasgos SÓLIDOS.
      Asume aditividad, que es una suposición y no un hecho — de ahí el aviso.

    Los rasgos NO sólidos no suman nada y se devuelven en `ignorados`. Un efecto que
    no superó su margen ni el test de signos no es un efecto chico: es uno que no se
    pudo distinguir del azar, y sumarlo sería inventar.
    """
    por_rasgo = {e["rasgo"]: e for e in efectos}
    aplicados, ignorados = [], []
    for r in sorted(rasgos):
        e = por_rasgo.get(r)
        if e is None:
            continue
        if e.get("solido") and e.get("efecto_intra") is not None:
            aplicados.append({"rasgo": r, "etiqueta": e["etiqueta"],
                              "efecto": e["efecto_intra"]})
        else:
            ignorados.append({"rasgo": r, "etiqueta": e["etiqueta"],
                              "motivo": "el efecto no se distingue del azar"})

    if observado and observado.get("n", 0) >= MIN_COMBINACION:
        n, k = observado["n"], observado["conversan"]
        p = 100.0 * k / n
        return {
            "probabilidad": round(p, 1), "fuente": "observado", "n_observado": n,
            # Error estándar binomial de la propia tasa: es lo que oscila al contar.
            "margen": round(100.0 * math.sqrt(max(p/100*(1-p/100), 1e-9) / n) * 1.96, 1),
            "aplicados": aplicados, "ignorados": ignorados, "tasa_base": tasa_base,
            "avisos": ["Este número está CONTADO, no estimado: es la tasa real de las "
                       f"{n} publicaciones del corpus con esta misma combinación."],
        }

    p = tasa_base + sum(a["efecto"] for a in aplicados)
    # Los márgenes se combinan en cuadratura, no se suman: sumarlos exageraría la
    # incertidumbre de una combinación.
    margen = math.sqrt(sum((por_rasgo[a["rasgo"]].get("margen") or 0) ** 2
                           for a in aplicados))
    avisos = []
    if len(aplicados) > MAX_RASGOS_SIN_AVISO:
        avisos.append("Se sumaron los efectos de varios rasgos, y eso supone que no "
                      "interactúan entre sí. No hay muestra de esta combinación exacta "
                      "para verificarlo, así que el número es más frágil que uno contado.")
    if ignorados:
        avisos.append("Hay rasgos elegidos que no mueven el número: su efecto no se "
                      "pudo distinguir del azar, y sumarlo sería inventar.")
    return {
        "probabilidad": round(max(0.0, min(100.0, p)), 1),
        "fuente": "estimado" if aplicados else "base",
        "n_observado": (observado or {}).get("n", 0),
        "margen": round(margen, 1),
        "aplicados": aplicados, "ignorados": ignorados, "tasa_base": tasa_base,
        "avisos": avisos,
    }


def ensayar(db, rasgos: set[str]) -> dict:
    """El ensayo completo: mide los efectos, busca la combinación y estima.

    Devuelve además el catálogo de rasgos con cuáles son sólidos, porque elegir sin
    saber eso lleva a apilar características que no hacen nada.
    """
    base = efecto_de_caracteristicas(db)
    pubs = _publicaciones(db)
    if not pubs:
        return {"probabilidad": None, "fuente": "sin_datos", "margen": 0.0,
                "aplicados": [], "ignorados": [], "tasa_base": 0.0, "n_observado": 0,
                "rasgos": [], "publicaciones": 0,
                "avisos": ["No hay publicaciones ingestadas para este ensayo."]}

    # La combinación EXACTA: mismos rasgos activos, mismos rasgos apagados.
    iguales = [p for p in pubs
               if {r for r, v in p["rasgos"].items() if v} == set(rasgos) & set(ETIQUETAS)]
    observado = ({"n": len(iguales), "conversan": sum(1 for p in iguales if p["conversa"])}
                 if iguales else None)

    r = estimar_conversacion(base["tasa_base"], base["caracteristicas"], rasgos,
                             observado=observado)
    r["rasgos"] = [{"rasgo": c["rasgo"], "etiqueta": c["etiqueta"],
                    "solido": c["solido"], "efecto_intra": c.get("efecto_intra")}
                   for c in base["caracteristicas"]]
    r["publicaciones"] = base["publicaciones"]
    r["avisos"] = r["avisos"] + [
        "Predice si va a haber CONVERSACIÓN, no de qué color: no dice nada sobre el "
        "índice ni sobre si los comentarios serán favorables.",
        "Es correlación, no causa. Que los reels generen más conversación no prueba "
        "que convertir un post en reel la produzca.",
    ]
    return r


def _avisos(filas: list[dict]) -> list[str]:
    avisos = [
        "Esto es correlación, no causa. Que los reels generen más conversación no "
        "prueba que convertir un post en reel la produzca: puede ser que el contenido "
        "que amerita un reel sea distinto de entrada."
    ]
    solidos = [f for f in filas if f["solido"]]
    if solidos:
        avisos.append(
            f"{len(solidos)} de {len(filas)} características superan las dos pruebas: "
            "el efecto crudo supera su margen de error Y se sostiene comparando cada "
            "cuenta consigo misma."
        )
    debiles = [f for f in filas
               if not f["solido"] and abs(f["efecto_crudo"]) > f["margen"]]
    if debiles:
        avisos.append(
            f"{len(debiles)} característica(s) parecen tener efecto en crudo pero NO "
            "se sostienen dentro de cada cuenta: ahí lo que se estaba midiendo era "
            "quién publica, no cómo."
        )
    return avisos
