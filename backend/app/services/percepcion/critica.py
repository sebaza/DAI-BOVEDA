"""Conversación CRÍTICA y volumen ADVERSO: lo que el índice general no puede mostrar.

Por qué hace falta
------------------
El índice general contesta «cómo se recibe lo que la UCN comunica». Es una pregunta
legítima y está bien calculada, pero no es la que se hace cuando hay un paro. Durante
un conflicto ese número sale tranquilo, y no por un error de cálculo: los
departamentos siguen publicando logros y esos posts reciben aplauso, que entra al
mismo promedio que la protesta.

Medido sobre las 6 ventanas de conflicto del calendario:

    índice general de la ventana                      74,5
    solo canales que alguna vez reciben crítica        66,6
    solo feucn (la federación estudiantil)             28,4

Y el dato que lo explica: **19 cuentas con 25+ comentarios nunca recibieron un solo
negativo en cuatro años**. `fisicaucn` tiene 167 comentarios y ninguna crítica. Son el
16 % del corpus, pero el 29 % dentro de las ventanas de conflicto: su peso casi se
duplica justo cuando hay conflicto, porque el aplauso institucional no se detiene.

Qué NO se hizo, y por qué
-------------------------
La alternativa evaluada era ponderar los negativos (multiplicarlos). Se midió sobre la
serie semanal completa:

    ×1,0   índice 81,1   sd 10,49
    ×1,5          78,4      12,11
    ×2,0          76,0      13,52
    ×3,0          72,0      15,68

Multiplicar la clase más rara y más variable AGREGA varianza: la línea queda más
nerviosa, que es lo contrario de lo que se buscaba. Y rompe la interpretación — hoy el
índice es `50 + 50·(cuota_pos − cuota_neg)`, legible como cuota neta; con multiplicador
deja de ser cuota de nada. Por eso acá se agregan indicadores SEPARADOS y no se toca
la serie.

La circularidad, que es el riesgo real
--------------------------------------
Elegir canales por ser negativos y después medir su negatividad no probaría nada. El
criterio es ESTRUCTURAL y se evalúa sobre TODA la historia, nunca sobre la ventana que
se está midiendo: un canal queda afuera solo si en cuatro años no recibió una sola
crítica. Y se exige un mínimo de comentarios para poder afirmarlo — con la tasa base
de negativos del corpus (8,5 %), no ver ninguno entre 10 comentarios es lo esperable
por azar, no evidencia de nada.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import select

from app.services.percepcion import repository

# Comentarios mínimos para afirmar que un canal NUNCA recibe críticas. Con la tasa
# base de 8,5 %, la probabilidad de no ver ningún negativo por azar es ~11 % con 25
# comentarios y ~44 % con 10: por debajo de este umbral el silencio no es evidencia.
N_MIN_JUICIO = 25


def filas_de_comentarios(db) -> list:
    """Un registro por comentario scoreado: cuenta, fecha, tono y tema.

    Baja al nivel de comentario porque `percepcion_hecho_diario` no guarda la cuenta,
    y la cuenta es justo la unidad que define si un canal admite crítica o no.
    """
    from app.services.percepcion.models import (
        PercepcionComentario as _M,
        PercepcionCuenta as _C,
        PercepcionPublicacion as _P,
        PercepcionScore as _S,
    )

    filas = db.execute(
        select(_C.handle, _M.fecha_comentario, _S.sentimiento, _M.tema)
        .join(_P, _P.cuenta_id == _C.id)
        .join(_M, _M.publicacion_id == _P.id)
        .join(_S, _S.comentario_id == _M.id)
    ).all()
    return [
        SimpleNamespace(
            handle=handle,
            fecha=fc.date() if hasattr(fc, "date") else repository._a_fecha(fc),
            sentimiento=sent,
            tema=tema,
        )
        for handle, fc, sent, tema in filas
    ]


def canales_sin_critica(filas, *, n_min: int = N_MIN_JUICIO) -> set[str]:
    """Canales donde la crítica no ocurre: cero negativos en toda la historia.

    Se evalúa sobre TODAS las filas a propósito, no sobre una ventana. Si el criterio
    se aplicara dentro de la ventana medida, una semana tranquila bastaría para sacar
    a un canal crítico de la lista y el indicador terminaría midiendo su propia
    selección.
    """
    total: dict[str, int] = {}
    negativos: dict[str, int] = {}
    for f in filas:
        total[f.handle] = total.get(f.handle, 0) + 1
        if f.sentimiento == "NEG":
            negativos[f.handle] = negativos.get(f.handle, 0) + 1
    return {
        h for h, n in total.items()
        if n >= n_min and negativos.get(h, 0) == 0
    }


def _en_ventana(filas, desde: date, hasta: date, excluir: set[str] | None = None):
    return [
        f for f in filas
        if f.fecha is not None and desde <= f.fecha <= hasta
        and (not excluir or f.handle not in excluir)
    ]


def _indice(sub) -> float | None:
    n = len(sub)
    if not n:
        return None
    pos = sum(1 for f in sub if f.sentimiento == "POS")
    neg = sum(1 for f in sub if f.sentimiento == "NEG")
    return 50.0 + 50.0 * (pos - neg) / n


def indice(filas, desde: date, hasta: date) -> float | None:
    """El índice general de la ventana, con todos los canales. Sirve de referencia."""
    return _indice(_en_ventana(filas, desde, hasta))


def indice_critico(filas, desde: date, hasta: date,
                   *, n_min: int = N_MIN_JUICIO) -> float | None:
    """El mismo cálculo, sobre los canales donde la crítica EXISTE.

    Devuelve None si no queda ningún canal crítico en la ventana. Es deliberado:
    entregar el índice general disfrazado sería peor que no responder, porque el
    tablero mostraría un número que dice representar la crítica sin tener ninguna
    detrás.
    """
    sin = canales_sin_critica(filas, n_min=n_min)
    sub = _en_ventana(filas, desde, hasta, excluir=sin)
    return _indice(sub)


def volumen_adverso(filas, desde: date, hasta: date) -> dict:
    """Cuántos negativos hubo, sin promediarlos con nada.

    Es el complemento del índice: un promedio esconde el volumen, y para gestión
    «hubo 54 comentarios negativos» es información distinta de «el índice bajó 4
    puntos». Se informa aparte justo para no tener que tocar la serie.
    """
    sub = _en_ventana(filas, desde, hasta)
    n = len(sub)
    adversos = sum(1 for f in sub if f.sentimiento == "NEG")
    return {
        "n_total": n,
        "n_adversos": adversos,
        # None y 0.0 no son lo mismo: sin datos no se puede afirmar que no hubo nada.
        "proporcion": (round(100.0 * adversos / n, 1) if n else None),
    }
