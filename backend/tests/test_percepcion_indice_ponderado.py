"""El índice del tablero pondera por TEMA. Es un cambio al número canónico.

Qué cambia
----------
`repository` calculaba el índice sumando todos los temas por igual:

    índice = 50 + 50·(Σ num_pos − Σ num_neg) / Σ den

Ahora el numerador se pondera por tema —las dos caras— y el denominador NO:

    índice = 50 + 50·(Σ w_t·num_pos_t − Σ w_t·num_neg_t) / Σ den_t

Es exacto y no necesita migración: el grano de `percepcion_hecho_diario` ya incluye
`tema`, así que dentro de una fila el peso es único. El único cambio real es agrupar
por (fecha, tema) en vez de solo por fecha antes de sumar.

Por qué se toca el canónico
---------------------------
El docstring del módulo dice «NO cambiar sin acordar con la DAI». Se acordó: la DAI
pidió explícitamente que el ponderado predomine, porque el índice sin pesos contesta
«cómo se recibe lo que la UCN comunica» y durante un paro eso da un número tranquilo.

Se deja conmutable con `ponderar_tema=False` — el canónico sigue disponible para
contrastar y para cualquier serie histórica que dependa de él.

Medido sobre el corpus real (7.885 comentarios, 2022-2026):
    sin ponderar   78 semanas · índice medio 81,1 · sd 10,49
    ponderado      78 semanas · índice medio 69,6 · sd  9,39
No se pierde una sola semana y la serie queda MENOS volátil.

⚠️ ACTUALIZACIÓN 09-2026 — el peso ya no es el mismo en las dos caras
--------------------------------------------------------------------
Con el esquema «DAI × peso de tema», el numerador positivo lleva `peso_credito` (que
recorta a la mitad los temas no atribuibles) y el negativo lleva `peso_dano` (que no
recorta). La fórmula pasa a ser:

    índice = 50 + 50·(Σ wc_t·num_pos_t − Σ wd_t·num_neg_t) / Σ den_t

Los valores esperados del lado positivo de este archivo cambiaron por eso. La
asimetría en sí, con su medición, la fija `test_percepcion_credito_atribuible.py`.
"""
from __future__ import annotations

import pytest

from app.services.percepcion import ponderacion, repository


def _fila(tema, n=10, npos=0, nneu=0, nneg=0):
    """Una fila de hechos: (n, peso_pos, peso_neg, suma_peso, s_pos, s_neg, sgan, npos, nneu, nneg)."""
    return (tema, n, float(npos), float(nneg), float(n), float(npos), float(nneg),
            float(n), npos, nneu, nneg)


def test_el_aplauso_de_un_tema_liviano_pesa_poco_en_el_indice():
    """100 felicitaciones a los perros no ponen el índice del tablero en 100.

    Crédito 0,1 (peso del tema) × 0,5 (no atribuible) = 0,05 por comentario.
    """
    filas = [_fila("mascotas", n=100, npos=100)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True)

    assert idx == pytest.approx(52.5, abs=0.5)


def test_sin_ponderar_da_el_canonico():
    """El número de siempre sigue disponible para contrastar."""
    filas = [_fila("mascotas", n=100, npos=100)]

    assert repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=False) == pytest.approx(100.0)


def test_el_dano_de_un_tema_liviano_tambien_pesa_poco():
    """Las condolencias por un perro no son daño institucional (caso Blanquita)."""
    filas = [_fila("mascotas", n=100, nneg=100)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True)

    assert idx == pytest.approx(45.0, abs=0.5)


def test_los_temas_pesados_no_se_diluyen():
    """Una queja sobre servicios sigue restando entero."""
    filas = [_fila("servicios_institucionales", n=100, nneg=100)]

    assert repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True) == pytest.approx(0.0)


def test_el_denominador_junta_todos_los_temas_sin_pesar():
    """Lo que evita perder cobertura: la muestra no se encoge.

    50 aplausos a perros (0,1 · 0,5 = 0,05) y 50 a servicios (1,0, atribuible): el
    crédito es 2,5 + 50 = 52,5 sobre un denominador de 100 comentarios, no sobre la
    suma de los pesos.
    """
    filas = [_fila("mascotas", n=50, npos=50),
             _fila("servicios_institucionales", n=50, npos=50)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True)

    assert idx == pytest.approx(50 + 50 * 52.5 / 100, abs=0.2)


def test_un_tema_nuevo_no_rompe_el_indice():
    """Aparece un tema fuera de la taxonomía y el tablero no puede caerse.

    Peso por defecto y lado no atribuible: las dos decisiones conservadoras.
    """
    filas = [_fila("tema_inventado", n=100, npos=100)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True)

    esperado = 50 + 50 * ponderacion.PESO_POR_DEFECTO * ponderacion.CREDITO_NO_ATRIBUIBLE
    assert idx == pytest.approx(esperado, abs=0.5)


def test_sin_datos_no_inventa_un_numero():
    assert repository._indice_de_filas([], peso_likes=0.0, ponderar_tema=True) is None


def test_el_indice_queda_acotado_a_cero_cien():
    """Ningún peso puede sacar el índice del rango, ni con datos extremos."""
    filas = [_fila("servicios_institucionales", n=10, nneg=10)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True)

    assert 0.0 <= idx <= 100.0
