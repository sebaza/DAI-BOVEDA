"""El CRÉDITO se descuenta por atribuibilidad; el DAÑO no. Esquema «DAI × peso de tema».

Qué cambia
----------
Hasta acá el peso del tema se aplicaba IGUAL a las dos caras: si un aplauso a la manada
valía 0,1, una pena por la manada restaba 0,1. Ahora el crédito de un tema NO ATRIBUIBLE
se corta a la mitad y el daño se mantiene entero:

    crédito = peso_tema · (1,0 si el tema es atribuible, si no 0,5)
    daño    = peso_tema

De dónde sale
-------------
Es la matriz tono × postura que pidió la DAI, resuelta sobre la postura que el sistema
sabe derivar hoy. Con `postura_de()` el tema fija la postura de un positivo —atribuible
→ favorable, no atribuible → neutral— así que la matriz colapsa exactamente a esto:

    POS + favorable  ×2 / 2 = 1,0 · peso_tema     -> crédito entero
    POS + neutral    ×1 / 2 = 0,5 · peso_tema     -> medio crédito
    NEU              × 0                          -> no mueve la barra
    NEG + adverso    ×2 / 2 = 1,0 · peso_tema     -> daño entero

Es exacto a nivel de fila de hechos y no necesita migración: el grano de
`percepcion_hecho_diario` ya incluye `tema`, y dentro de una fila el tema es único, así
que la atribuibilidad también lo es.

POR QUÉ ESTA VARIANTE Y NO LA MATRIZ CRUDA
------------------------------------------
Medido sobre los 4 años reales (8.174 comentarios, 80 semanas con n≥20, 8 paros +
4 tomas + 1 emergencia). AUC = P(una semana de conflicto quede por debajo de una de
calma); «shock» = caída en la emergencia del 07-04-2025, en desvíos de la propia serie:

    esquema                AUC conflicto   AUC gestación   shock (σ)    sd
    canónico                   0,610           0,569         −1,85     10,51
    peso de tema (anterior)    0,640           0,620         −1,31      9,34
    matriz DAI cruda           0,636           0,558         −2,21     10,75
    ESTE (DAI × peso tema)     0,643           0,618         −1,55      9,08

La matriz cruda aplana a 0,5 TODO positivo no atribuible sin distinguir
`organizacion_estudiantil` (peso 1,0 — donde se gesta el conflicto) de `mascotas`
(peso 0,1). Eso le cuesta 0,062 de AUC en gestación, que es la señal que el módulo
existe para dar. Conservando el peso continuo dentro de cada celda, el aviso previo se
mantiene (0,618 contra 0,620) y se gana reacción al shock (−1,55 contra −1,31).

⚠️ LO QUE ESTE TEST NO PUEDE AFIRMAR. Con 19 semanas de conflicto y 38 de calma, los
IC del 95 % por bootstrap se solapan por completo —conflicto [0,49–0,79] contra
[0,49–0,78]— y todos incluyen 0,5. Ninguna diferencia de AUC entre esquemas es
estadísticamente distinguible. Lo único que sobrevive al bootstrap es el shock, porque
mide un evento concreto y no compara grupos de semanas. Este cambio se adopta por su
lectura institucional (un aplauso que no es mérito de la UCN no es crédito pleno), no
porque discrimine mejor: eso no se puede afirmar con los datos que hay.

REVERSIBLE. `PERCEPCION_CREDITO_NO_ATRIBUIBLE=1.0` devuelve exactamente el esquema
simétrico anterior, sin tocar código.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.percepcion import ponderacion, postura, repository


class _Fila:
    def __init__(self, tema: str | None, sentimiento: str, fecha: date = date(2026, 6, 20)):
        self.tema = tema
        self.sentimiento = sentimiento
        self.fecha = fecha


DIA = date(2026, 6, 20)


def _fila_hecho(tema, n=10, npos=0, nneu=0, nneg=0):
    """Una fila de `percepcion_hecho_diario` como la consume `_indice_de_filas`."""
    return (tema, n, float(npos), float(nneg), float(n), float(npos), float(nneg),
            float(n), npos, nneu, nneg)


# --------------------------------------------------------------------------- #
# La regla, en las dos caras
# --------------------------------------------------------------------------- #
def test_el_aplauso_de_un_tema_no_atribuible_vale_la_mitad():
    """Un aplauso a la manada no es mérito de la UCN: medio crédito, no crédito pleno.

    Es el corazón del cambio. `mascotas` pesa 0,1 y no es atribuible, así que 100
    felicitaciones aportan 100·0,1·0,5 = 5 sobre un denominador de 100.
    """
    filas = [_Fila("mascotas", "POS")] * 100

    idx = ponderacion.indice_ponderado(filas, DIA, DIA)

    assert idx == pytest.approx(52.5, abs=0.1), (
        f"credito 0,1·0,5 sobre 100 comentarios deberia dar 52,5; dio {idx}"
    )


def test_el_aplauso_de_un_tema_atribuible_vale_entero():
    """La contraparte: elogiar los servicios SÍ es mérito de la institución."""
    filas = [_Fila("servicios_institucionales", "POS")] * 100

    assert ponderacion.indice_ponderado(filas, DIA, DIA) == pytest.approx(100.0)


def test_el_dano_no_se_descuenta_por_atribuibilidad():
    """El daño NO cambia: todo negativo es adverso, atribuible o no.

    Es la asimetría deliberada del esquema. El caso Blanquita sigue cubierto —las
    condolencias por la perra del campus pesan 0,1 y no hunden el índice— pero por el
    peso del TEMA, no por la atribuibilidad. Un negativo de mascotas resta lo mismo
    que antes del cambio.
    """
    filas = [_Fila("mascotas", "NEG")] * 100

    assert ponderacion.indice_ponderado(filas, DIA, DIA) == pytest.approx(45.0, abs=0.1)


def test_la_asimetria_solo_toca_el_credito():
    """Mismo tema, mismo peso, distinto signo: el crédito es la mitad del daño.

    Sin este test nada impide que una refactorización aplique el descuento a las dos
    caras y devuelva el esquema simétrico sin que se note.
    """
    credito = ponderacion.indice_ponderado([_Fila("vida_estudiantil", "POS")] * 100,
                                           DIA, DIA) - 50.0
    dano = 50.0 - ponderacion.indice_ponderado([_Fila("vida_estudiantil", "NEG")] * 100,
                                               DIA, DIA)

    assert credito == pytest.approx(dano * 0.5, abs=0.1), (
        f"credito {credito:.2f} deberia ser la mitad del dano {dano:.2f}"
    )


def test_un_tema_atribuible_es_simetrico():
    """Donde el tema SÍ habla de la institución, las dos caras siguen pesando igual."""
    credito = ponderacion.indice_ponderado([_Fila("academico", "POS")] * 100,
                                           DIA, DIA) - 50.0
    dano = 50.0 - ponderacion.indice_ponderado([_Fila("academico", "NEG")] * 100,
                                               DIA, DIA)

    assert credito == pytest.approx(dano, abs=0.1)


def test_los_neutrales_siguen_sin_mover_la_barra():
    """El esquema manda NEU+neutral a cero, que es lo que el índice ya hacía.

    La propuesta original quería activar los neutros (NEU+favorable a positivo,
    NEU+adverso a negativo), pero esas dos celdas no existen: `postura_de()` manda
    todo neutro a `neutral`. Activarlos necesita una postura independiente del tono.
    """
    solo_pos = ponderacion.indice_ponderado([_Fila("academico", "POS")] * 10, DIA, DIA)
    con_neu = ponderacion.indice_ponderado(
        [_Fila("academico", "POS")] * 10 + [_Fila("academico", "NEU")] * 10, DIA, DIA)

    assert solo_pos > con_neu > 50


# --------------------------------------------------------------------------- #
# Lo que NO cambia
# --------------------------------------------------------------------------- #
def test_el_denominador_sigue_sin_ponderarse():
    """La muestra no se encoge: es lo que evita perder 17 semanas de cobertura.

    50 aplausos a perros (0,1 · 0,5 = 0,05) y 50 a servicios (1,0): el crédito es
    2,5 + 50 = 52,5 sobre un denominador de 100 comentarios, no sobre la suma de pesos.
    """
    filas = ([_Fila("mascotas", "POS")] * 50
             + [_Fila("servicios_institucionales", "POS")] * 50)

    idx = ponderacion.indice_ponderado(filas, DIA, DIA)

    assert idx == pytest.approx(50 + 50 * 52.5 / 100, abs=0.1)


def test_un_tema_desconocido_no_rompe_ni_asume_atribuibilidad():
    """Un tema fuera de la taxonomía cae al peso por defecto Y al lado conservador.

    Por omisión un tema nuevo NO es atribuible, que es el lado que nunca infla lo
    favorable. Misma decisión que toma `postura.TEMAS_ATRIBUIBLES`.
    """
    filas = [_Fila("tema_que_no_existe_todavia", "POS")] * 100

    idx = ponderacion.indice_ponderado(filas, DIA, DIA)

    esperado = 50 + 50 * ponderacion.PESO_POR_DEFECTO * ponderacion.CREDITO_NO_ATRIBUIBLE
    assert idx == pytest.approx(esperado, abs=0.1)


def test_sin_datos_devuelve_none():
    assert ponderacion.indice_ponderado([], DIA, DIA) is None


# --------------------------------------------------------------------------- #
# Coherencia con la regla de postura y reversibilidad
# --------------------------------------------------------------------------- #
def test_la_atribuibilidad_la_define_postura_y_no_una_copia():
    """Un solo dueño de la lista. Si `postura` cambia, el índice la sigue.

    Duplicar `TEMAS_ATRIBUIBLES` acá haría que la postura mostrada en pantalla y el
    peso usado en el cálculo se separaran en silencio.
    """
    for tema in postura.TEMAS_ATRIBUIBLES:
        assert ponderacion.peso_credito(tema) == pytest.approx(ponderacion.peso_de(tema))
    assert ponderacion.peso_credito("mascotas") < ponderacion.peso_de("mascotas")


def test_todo_tema_atribuible_tiene_peso_declarado():
    """Un tema atribuible sin peso propio caería al default sin que nadie se entere."""
    faltan = postura.TEMAS_ATRIBUIBLES - set(ponderacion.PESOS_POR_TEMA)

    assert not faltan, f"temas atribuibles sin peso declarado: {sorted(faltan)}"


def test_se_puede_volver_al_esquema_simetrico_sin_tocar_codigo(monkeypatch):
    """`PERCEPCION_CREDITO_NO_ATRIBUIBLE=1.0` devuelve el comportamiento anterior.

    El cambio mueve el nivel del índice y rompe comparabilidad con lo ya reportado,
    así que tiene que haber una vuelta atrás que no dependa de un deploy.
    """
    monkeypatch.setattr(ponderacion, "CREDITO_NO_ATRIBUIBLE", 1.0)

    filas = [_Fila("mascotas", "POS")] * 100

    assert ponderacion.indice_ponderado(filas, DIA, DIA) == pytest.approx(55.0, abs=0.1)


# --------------------------------------------------------------------------- #
# El índice del TABLERO usa la misma regla
# --------------------------------------------------------------------------- #
def test_el_indice_del_tablero_aplica_el_credito_recortado():
    """`repository._indice_de_filas` es el que alimenta el medidor y la serie."""
    filas = [_fila_hecho("mascotas", n=100, npos=100)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True)

    assert idx == pytest.approx(52.5, abs=0.1)


def test_el_indice_del_tablero_no_recorta_el_dano():
    filas = [_fila_hecho("mascotas", n=100, nneg=100)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=True)

    assert idx == pytest.approx(45.0, abs=0.1)


def test_el_canonico_sigue_disponible_para_contrastar():
    """`ponderar_tema=False` no aplica ni peso de tema ni recorte de crédito."""
    filas = [_fila_hecho("mascotas", n=100, npos=100)]

    idx = repository._indice_de_filas(filas, peso_likes=0.0, ponderar_tema=False)

    assert idx == pytest.approx(100.0)
