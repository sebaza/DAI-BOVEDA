"""VOLATILIDAD por unidad — ¿qué facultad se mueve de verdad y cuál solo parece?

Contesta «¿qué unidad es más volátil?», que es la pregunta D del plan de simulación
(`INFORME_PLAN_SIMULACION_PERCEPCION_20260824.md`). Y la contesta descontando el ruido,
que es lo único que la separa de un `sort()` sin sentido.

EL ERROR QUE ESTE MÓDULO EXISTE PARA EVITAR
-------------------------------------------
Ordenar unidades por la desviación estándar de su índice semanal **mide tamaño de
muestra disfrazado de volatilidad**. Una unidad con 5 comentarios por semana oscila
sola: dos comentarios negativos de más mueven su índice 20 puntos. Un ranking crudo
diría "las facultades chicas son inestables", que no es un hallazgo sobre la UCN sino
sobre la aritmética del promedio.

LA DESCOMPOSICIÓN
-----------------
    sd_observada² = sd_señal² + sd_muestreo²   =>   sd_señal = √(obs² − muestreo²)

`sd_muestreo` sale de la varianza del índice bajo muestreo aleatorio, semana por
semana, con el `n` real de esa semana. El índice es `50 + 50·(p_pos − p_neg)`, así que:

    Var(p_pos − p_neg) = [p(1−p) + q(1−q) + 2pq] / n        (p = pos, q = neg)

El término `2pq` no sobra: positivos y negativos están **negativamente correlacionados**
dentro de una multinomial (un comentario que cae en POS no cae en NEG), y omitirlo
subestima el ruido — que es justo el error que este módulo previene.

Lo que queda por encima de ese piso es volatilidad estructural: la que responde a algo
real que le pasó a esa unidad.

CUANDO NO SUPERA AL RUIDO SE DEVUELVE `None`, NO CERO
-----------------------------------------------------
Cero **afirma** estabilidad. `None` dice "no se puede saber con estos datos". Con
volúmenes chicos la mayoría de las unidades cae ahí, y presentarlas como estables sería
inventar un hallazgo donde solo hay falta de evidencia. Es el mismo criterio con el que
`calidad.py` devuelve `None` con motivo en vez de un 0 % que mentiría.

MEDIDO SOBRE EL CORPUS REAL (2026-08-24)
-----------------------------------------
Con el umbral estricto (n≥15/semana, 8+ semanas) calificaban **1 sede, 1 facultad y 0
departamentos** — un ranking de un elemento. Con el permisivo (n≥5, 6+ semanas) entran
10 unidades y **las 10 tienen volatilidad real distinguible del ruido**:

    Facultad de Ciencias Jurídicas   18,7      Escuela de Periodismo        9,8
    Escuela de Derecho Antofagasta   18,6      Depto. Ing. de Sistemas      9,5
    Antofagasta (sede)               13,0      Facultad de Humanidades      9,3
    Depto. Ingeniería Industrial     11,4      Facultad de Educación        7,5
    Fac. Ingeniería y Cs. Geológicas 10,2      Coquimbo (sede)              5,4

Ciencias Jurídicas es 3,5× Coquimbo. Y hay un control de calidad que salió solo:
Ciencias Jurídicas (18,7) y su Escuela de Derecho (18,6) coinciden — son la misma unidad
a dos niveles, y si fuera artefacto de muestreo no habrían caído juntas.

⚠️ Las posiciones VECINAS no son distinguibles entre sí (9,8 vs 9,5 vs 9,3 están dentro
del error). Lo que se sostiene es el contraste entre extremos. El módulo emite ese aviso
solo, para que la UI no pueda olvidarse de escribirlo.
"""
from __future__ import annotations

import math
import statistics as st
from datetime import date

from sqlalchemy import func, select

from app.services.percepcion import repository
from app.services.percepcion.models import PercepcionHechoDiario as H

# Umbrales por defecto: los PERMISIVOS, y a propósito. Con los estrictos del resto del
# módulo (30 comentarios) el ranking se queda sin unidades y no contesta nada. La
# contrapartida —que cada número tiene incertidumbre— se comunica con
# `evidencia_suficiente` por unidad y con los avisos, no bajando la vara en silencio.
N_MIN_SEMANA = 5
MIN_SEMANAS = 6

# Diferencia mínima entre dos volatilidades para considerarlas distintas. Sale de la
# magnitud del propio ruido de muestreo del corpus (~4-6 puntos): por debajo de eso,
# dos unidades vecinas del ranking están empatadas aunque el número diga otra cosa.
DELTA_DISTINGUIBLE = 2.0

_DIMENSIONES = {"campus": H.campus, "facultad": H.facultad,
                "departamento": H.departamento}


def _series_por_unidad(db, col, n_min_semana: int) -> dict[str, list[tuple[int, float, dict]]]:
    """{unidad: [(n, indice, reparto) por semana]}, en UNA consulta.

    Se agrupa por semana en Python y no en SQL porque `strftime`/`date_trunc` difieren
    entre SQLite y Postgres —y en el número de semana ISO en los bordes de año—, y este
    módulo corre contra los dos. Son ~940 filas de hechos.
    """
    filas = db.execute(
        select(col, H.fecha, func.sum(H.n_pos), func.sum(H.n_neu), func.sum(H.n_neg))
        .where(col.is_not(None), col != "")
        .group_by(col, H.fecha)
    ).all()

    acumulado: dict[str, dict[date, list[int]]] = {}
    for nombre, fecha, npos, nneu, nneg in filas:
        f = repository._a_fecha(fecha)
        if f is None:
            continue
        semanas = acumulado.setdefault(nombre, {})
        acc = semanas.setdefault(repository._lunes(f), [0, 0, 0])
        acc[0] += int(npos or 0)
        acc[1] += int(nneu or 0)
        acc[2] += int(nneg or 0)

    out: dict[str, list[tuple[int, float, dict]]] = {}
    for nombre, semanas in acumulado.items():
        serie = []
        for _lunes, (npos, nneu, nneg) in sorted(semanas.items()):
            n = npos + nneu + nneg
            if n < n_min_semana:
                continue
            # Índice SIN ponderar por likes ni por recencia: este bloque afirma algo
            # sobre una unidad, y lo afirmado tiene que poder verificarse contando.
            indice = 50.0 + 50.0 * (npos - nneg) / n
            serie.append((n, indice, {"pos": npos, "neu": nneu, "neg": nneg}))
        if serie:
            out[nombre] = serie
    return out


def _ruido_de_muestreo(serie) -> float:
    """Cuánto oscilaría el índice de esta unidad SOLO por azar, dado su volumen.

    ⚠️ LAS PROPORCIONES VAN SUAVIZADAS (Laplace, +1 por categoría), y no es cosmética:
    sin eso el módulo falla justo en el caso que existe para atajar.

    Estimar la varianza con `p̂ = x/n` da CERO cuando una semana cae entera en una
    categoría. Una unidad con 4 comentarios, los 4 positivos, tendría ruido 0 — como
    si su índice de 100 fuera una certeza. Pero con n=4, observar 4 de 4 es
    perfectamente compatible con una proporción real de 0,7. Y si esa unidad alterna
    semanas de 100 y de 0, `sd_observada` es enorme, `sd_ruido` es 0, y **toda la
    oscilación se cuenta como señal**: exactamente el artefacto que hay que evitar,
    en su forma más extrema.

    Con el suavizado, esa misma unidad de n=4 da un ruido de ~18 puntos, y una de
    n=100 con el mismo patrón da ~1. Que es la diferencia real entre las dos.
    """
    ruidos = []
    for _n, _idx, d in serie:
        tot = d["pos"] + d["neu"] + d["neg"]
        if tot < 1:
            continue
        # +1 por cada una de las 3 categorías => denominador tot+3.
        den = tot + 3
        p, q = (d["pos"] + 1) / den, (d["neg"] + 1) / den
        # El divisor sigue siendo el n REAL: el suavizado corrige la ESTIMACIÓN de la
        # proporción, no la cantidad de observaciones que se tienen.
        var = (p * (1 - p) + q * (1 - q) + 2 * p * q) / tot
        ruidos.append(50.0 * math.sqrt(max(var, 0.0)))
    return st.mean(ruidos) if ruidos else 0.0


def _descomponer(serie) -> dict:
    indices = [x[1] for x in serie]
    sd_obs = st.pstdev(indices)
    sd_ruido = _ruido_de_muestreo(serie)
    resto = sd_obs ** 2 - sd_ruido ** 2
    ns = [x[0] for x in serie]
    return {
        "semanas": len(serie),
        "n_mediana": int(st.median(ns)),
        "indice_medio": st.mean(indices),
        "sd_observada": round(sd_obs, 2),
        "sd_ruido": round(sd_ruido, 2),
        # None (y no 0.0) cuando la variación no supera al ruido: ver el docstring.
        "volatilidad_real": round(math.sqrt(resto), 2) if resto > 0 else None,
        "ratio": round(sd_obs / sd_ruido, 2) if sd_ruido else None,
        "evidencia_suficiente": st.median(ns) >= repository.N_MIN_EVIDENCIA,
    }


def volatilidad_por_unidad(db, *, nivel: str = "facultad",
                           n_min_semana: int = N_MIN_SEMANA,
                           min_semanas: int = MIN_SEMANAS) -> dict:
    """Ranking de unidades por volatilidad ESTRUCTURAL de su índice semanal.

    `sin_evidencia` lista las unidades que no llegan al mínimo. No es un detalle: si
    solo se mostraran las que califican, el tablero daría a entender que el ranking
    cubre a toda la universidad cuando cubre una fracción.
    """
    col = _DIMENSIONES.get(nivel)
    if col is None:
        nivel, col = "facultad", H.facultad

    series = _series_por_unidad(db, col, n_min_semana)
    unidades, sin_evidencia = [], []
    for nombre, serie in series.items():
        if len(serie) < min_semanas:
            sin_evidencia.append(nombre)
            continue
        unidades.append({"nombre": nombre, **_descomponer(serie)})

    # Por volatilidad REAL. Las que no la tienen van al final: no son estables, son
    # indeterminadas, y mezclarlas con las de volatilidad baja las confundiría.
    unidades.sort(key=lambda u: (u["volatilidad_real"] is None,
                                 -(u["volatilidad_real"] or 0)))
    return {
        "nivel": nivel,
        "n_min_semana": n_min_semana,
        "min_semanas": min_semanas,
        "unidades": unidades,
        "sin_evidencia": sorted(sin_evidencia),
        "avisos": _avisos(unidades, sin_evidencia),
    }


def _avisos(unidades: list[dict], sin_evidencia: list[str]) -> list[str]:
    """Advertencias que el módulo emite SOLO.

    Viajan con el dato y no quedan libradas a que la UI se acuerde de escribirlas —
    mismo criterio que `calidad.py`. Son la diferencia entre un ranking que se lee bien
    y uno que se lee como si fuera un orden exacto.
    """
    avisos: list[str] = []
    if len(unidades) < 3:
        avisos.append(
            f"Solo {len(unidades)} unidad(es) tienen semanas suficientes para medir "
            "volatilidad. Con tan pocas no hay con qué comparar: el orden no es un "
            "ranking, es una lista."
        )
    con_valor = [u for u in unidades if u["volatilidad_real"] is not None]
    if len(con_valor) >= 2:
        vecinas = sum(
            1 for a, b in zip(con_valor, con_valor[1:])
            if abs(a["volatilidad_real"] - b["volatilidad_real"]) < DELTA_DISTINGUIBLE
        )
        if vecinas:
            avisos.append(
                f"{vecinas} par(es) de posiciones vecinas difieren en menos de "
                f"{DELTA_DISTINGUIBLE} puntos: están empatadas dentro del error. "
                "Lo que sí se sostiene es el contraste entre los extremos."
            )
    flacas = [u["nombre"] for u in unidades if not u["evidencia_suficiente"]]
    if flacas:
        avisos.append(
            f"{len(flacas)} unidad(es) miden con menos de {repository.N_MIN_EVIDENCIA} "
            "comentarios por semana. El ruido ya está descontado, pero su cifra tiene "
            "más incertidumbre que el resto."
        )
    if sin_evidencia:
        avisos.append(
            f"{len(sin_evidencia)} unidad(es) quedaron fuera por no tener semanas "
            "suficientes. El ranking NO cubre a toda la universidad."
        )
    return avisos
