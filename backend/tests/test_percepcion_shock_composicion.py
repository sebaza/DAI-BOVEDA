"""La caída durante un conflicto se confunde con un cambio de QUIÉN comenta.

El problema medido
------------------
El índice de una ventana mezcla todas las cuentas. Y entre la ventana previa y la del
conflicto la mezcla cambia muchísimo — medido sobre «Paralización general junio-julio»:

    centros de alumnos (índice ~72)   n=114  ->  n=4
    feucn              (índice ~28)   n=26   ->  n=102

feucn no se pone más negativa durante el paro: está en 28-32 antes, durante y después.
Lo que cambia es su PESO. Cuando el canal negativo cuadruplica su participación y los
positivos desaparecen, el índice agregado baja aunque nadie haya cambiado de opinión.

Medido sobre los 6 episodios: la caída del episodio grande pasa de −15,6 a −4,7 al
mantener la mezcla fija. Dos tercios eran composición.

Por qué por TIPO de cuenta y no por tema
----------------------------------------
Se probaron los dos. Estandarizar por `tema` deja la caída casi igual (−15,6 -> −13,7);
por tipo de cuenta la corrige de verdad (-> −4,7). Lo que se mueve entre ventanas es
QUIÉN comenta, no de qué se habla.

Eso obliga a bajar al nivel de comentario: `percepcion_hecho_diario` tiene fecha,
origen, campus, facultad, departamento y tema — pero no el tipo de cuenta. Con ~8.000
comentarios el costo es despreciable y evita tocar el esquema que escribe el worker.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.percepcion import shock


class _FilaFalsa:
    """Un comentario ya scoreado, con el tipo de su cuenta."""

    def __init__(self, tipo: str, fecha: date, sentimiento: str) -> None:
        self.tipo = tipo
        self.fecha = fecha
        self.sentimiento = sentimiento


def _corpus() -> list[_FilaFalsa]:
    """Dos canales de nivel MUY distinto, ninguno cambia de opinión.

    La única diferencia entre las dos ventanas es cuánto habla cada uno. Un índice
    crudo tiene que caer; uno estandarizado no.
    """
    previa, durante = date(2026, 5, 18), date(2026, 6, 15)
    filas = []
    # Ventana previa: dominan los centros de alumnos (positivos).
    filas += [_FilaFalsa("centro_alumnos", previa, "POS")] * 90
    filas += [_FilaFalsa("centro_alumnos", previa, "NEG")] * 10
    filas += [_FilaFalsa("federacion", previa, "POS")] * 3
    filas += [_FilaFalsa("federacion", previa, "NEG")] * 7
    # Ventana del conflicto: MISMAS proporciones internas, pesos invertidos.
    filas += [_FilaFalsa("centro_alumnos", durante, "POS")] * 9
    filas += [_FilaFalsa("centro_alumnos", durante, "NEG")] * 1
    filas += [_FilaFalsa("federacion", durante, "POS")] * 30
    filas += [_FilaFalsa("federacion", durante, "NEG")] * 70
    return filas


def test_el_indice_crudo_cae_por_puro_cambio_de_mezcla():
    """Control: sin corregir, el número baja aunque nadie cambió de opinión."""
    filas = _corpus()
    prev = shock.indice_crudo(filas, date(2026, 5, 18), date(2026, 5, 18))
    dur = shock.indice_crudo(filas, date(2026, 6, 15), date(2026, 6, 15))

    assert prev - dur > 30, (
        f"el falso no reproduce el problema: {prev:.1f} -> {dur:.1f}"
    )


def test_estandarizado_no_se_mueve_si_nadie_cambio_de_opinion():
    """Lo que se busca: con la mezcla fija, la caída desaparece."""
    filas = _corpus()
    pesos = shock.pesos_por_tipo(filas)

    prev = shock.indice_estandarizado(filas, date(2026, 5, 18), date(2026, 5, 18), pesos)
    dur = shock.indice_estandarizado(filas, date(2026, 6, 15), date(2026, 6, 15), pesos)

    assert abs(prev - dur) < 1.0, (
        f"quedo una caida de {prev - dur:.1f} puntos que es solo composicion"
    )


def test_estandarizado_si_detecta_un_cambio_real_de_opinion():
    """Contraprueba: si un canal EMPEORA de verdad, tiene que verse.

    Sin esto, un indicador que siempre devuelve «no pasó nada» pasaría el test de
    arriba y no serviría para nada.
    """
    previa, durante = date(2026, 5, 18), date(2026, 6, 15)
    filas = []
    filas += [_FilaFalsa("centro_alumnos", previa, "POS")] * 50
    filas += [_FilaFalsa("federacion", previa, "POS")] * 50
    filas += [_FilaFalsa("centro_alumnos", durante, "POS")] * 50
    filas += [_FilaFalsa("federacion", durante, "NEG")] * 50  # este empeoro de verdad
    pesos = shock.pesos_por_tipo(filas)

    prev = shock.indice_estandarizado(filas, previa, previa, pesos)
    dur = shock.indice_estandarizado(filas, durante, durante, pesos)

    assert prev - dur > 40, f"no detecto el cambio real: {prev:.1f} -> {dur:.1f}"


def test_un_estrato_con_pocos_datos_no_arrastra_el_promedio():
    """Un tipo con 2 comentarios no puede pesar como uno con 200.

    Se excluye por debajo del mínimo y los pesos se renormalizan entre los que
    quedan: si no, un estrato de n=1 al 0 % o al 100 % mueve el índice varios puntos
    sin ninguna evidencia detrás.
    """
    dia = date(2026, 6, 15)
    filas = [_FilaFalsa("centro_alumnos", dia, "POS")] * 200
    filas += [_FilaFalsa("federacion", dia, "NEG")] * 2
    pesos = shock.pesos_por_tipo(filas)

    idx = shock.indice_estandarizado(filas, dia, dia, pesos, n_min=5)

    assert idx == pytest.approx(100.0), (
        f"el estrato de n=2 arrastro el indice a {idx:.1f}"
    )


def test_sin_datos_devuelve_none():
    """Una ventana vacía no vale 50 ni 0: no se puede afirmar nada."""
    assert shock.indice_estandarizado([], date(2026, 1, 1), date(2026, 1, 2), {}) is None
    assert shock.indice_crudo([], date(2026, 1, 1), date(2026, 1, 2)) is None
