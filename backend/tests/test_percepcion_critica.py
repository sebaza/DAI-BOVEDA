"""Conversación CRÍTICA y volumen ADVERSO: dos lecturas que el índice no da.

El problema
-----------
El índice general contesta «cómo se recibe lo que la UCN comunica». Durante un paro
esa pregunta se responde con un número tranquilo, porque los departamentos siguen
publicando logros y esos posts reciben aplauso. Medido sobre 6 ventanas de conflicto:

    índice general de la ventana                74,5
    solo cuentas que alguna vez reciben crítica 66,6
    solo feucn (la federación)                  28,4

Y hay un dato que lo explica: 19 cuentas con 25+ comentarios NUNCA recibieron un solo
negativo en cuatro años. `fisicaucn` tiene 167 comentarios y ninguna crítica. Son el
16 % del corpus, pero el 29 % dentro de las ventanas de conflicto — su peso casi se
duplica justo cuando hay conflicto.

Lo que se agrega
----------------
Dos indicadores SEPARADOS. No se toca el índice: está bien calculado, simplemente no
es el instrumento para esta pregunta. Un multiplicador sobre los negativos —la
alternativa que se evaluó— sube la volatilidad de la serie (sd 10,5 -> 13,5 al ×2) y
rompe la interpretación de cuota neta.

    índice crítico    el mismo cálculo, sobre los canales donde la crítica EXISTE.
    volumen adverso   cuántos negativos hubo y qué proporción, sin promediar con nada.

Sobre la circularidad
---------------------
Elegir canales por ser negativos y después medir su negatividad no probaría nada. Por
eso el criterio es ESTRUCTURAL y se evalúa sobre TODA la historia, no sobre la ventana
que se está midiendo: un canal queda fuera solo si en cuatro años nunca recibió una
crítica. Y hace falta un mínimo de comentarios para afirmarlo: con la tasa base de
8,5 %, no ver ningún negativo entre 10 comentarios es lo esperable por azar.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.percepcion import critica


class _Fila:
    def __init__(self, handle: str, fecha: date, sentimiento: str, tema: str | None = None):
        self.handle = handle
        self.fecha = fecha
        self.sentimiento = sentimiento
        self.tema = tema


DIA = date(2026, 6, 20)


def _corpus() -> list[_Fila]:
    filas = []
    # Canal de puro aplauso: 40 comentarios, ni una critica en toda su historia.
    filas += [_Fila("fisicaucn", DIA, "POS")] * 35
    filas += [_Fila("fisicaucn", DIA, "NEU")] * 5
    # Canal con voz critica.
    filas += [_Fila("feucn", DIA, "POS")] * 10
    filas += [_Fila("feucn", DIA, "NEU")] * 20
    filas += [_Fila("feucn", DIA, "NEG")] * 30
    # Canal chico: cero negativos, pero con 6 comentarios no se puede afirmar nada.
    filas += [_Fila("ceicucn", DIA, "POS")] * 6
    return filas


def test_identifica_los_canales_sin_critica():
    """Solo los que tienen volumen suficiente para afirmarlo."""
    sin = critica.canales_sin_critica(_corpus())

    assert "fisicaucn" in sin, "40 comentarios sin un negativo es silencio critico real"
    assert "feucn" not in sin
    assert "ceicucn" not in sin, (
        "con 6 comentarios no ver negativos es lo esperable por azar: no se afirma"
    )


def test_indice_critico_excluye_el_aplauso_estructural():
    """El número que contesta «qué dice quien sí critica»."""
    filas = _corpus()

    general = critica.indice(filas, DIA, DIA)
    critico = critica.indice_critico(filas, DIA, DIA)

    assert critico < general - 15, (
        f"el indice critico ({critico:.1f}) no se despega del general ({general:.1f})"
    )


def test_el_criterio_se_evalua_sobre_toda_la_historia():
    """Un canal que criticó ALGUNA vez sigue contando aunque esa semana aplauda.

    Si el criterio se evaluara dentro de la ventana, bastaría una semana tranquila
    para que un canal crítico saliera de la lista — y el indicador mediría su propia
    selección en vez de la conversación.
    """
    otro_dia = date(2026, 1, 15)
    filas = [_Fila("feucn", otro_dia, "NEG")] * 30      # critico en enero
    filas += [_Fila("feucn", DIA, "POS")] * 30          # aplaude en junio
    filas += [_Fila("fisicaucn", DIA, "POS")] * 40      # nunca critica

    sin = critica.canales_sin_critica(filas)

    assert "feucn" not in sin
    assert critica.indice_critico(filas, DIA, DIA) == pytest.approx(100.0)


def test_volumen_adverso_no_promedia_con_nada():
    """El conteo crudo: es lo que un promedio esconde."""
    v = critica.volumen_adverso(_corpus(), DIA, DIA)

    assert v["n_adversos"] == 30
    assert v["n_total"] == 106
    assert v["proporcion"] == pytest.approx(30 / 106 * 100, abs=0.1)


def test_volumen_adverso_distingue_pocos_de_ninguno():
    """Cero adversos y «no hubo datos» no son lo mismo."""
    vacio = critica.volumen_adverso([], DIA, DIA)
    sin_adversos = critica.volumen_adverso([_Fila("x", DIA, "POS")] * 10, DIA, DIA)

    assert vacio["n_total"] == 0 and vacio["proporcion"] is None
    assert sin_adversos["n_total"] == 10 and sin_adversos["proporcion"] == 0.0


def test_sin_canales_criticos_devuelve_none():
    """Si TODOS los canales son de aplauso, no hay indice critico que dar.

    Devolver el indice general disfrazado seria peor que no responder: el tablero
    mostraria un numero que dice representar la critica sin tener ninguna detras.
    """
    filas = [_Fila("fisicaucn", DIA, "POS")] * 40

    assert critica.indice_critico(filas, DIA, DIA) is None
