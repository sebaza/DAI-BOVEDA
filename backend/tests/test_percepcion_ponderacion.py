"""Indice ponderado por TEMA: cuanto habla de la institucion cada comentario.

La idea
-------
No todos los temas hablan igual de la institucion. Un aplauso a los perros del campus
no dice lo mismo sobre la UCN que un elogio a la docencia, y hoy pesan igual. La
postura ya reconoce eso, pero de forma binaria: un tema es atribuible o no lo es. Esto
lo hace continuo, y en las dos direcciones.

El denominador NO se pondera, y ahi esta la diferencia
-----------------------------------------------------
Se probaron las dos formas sobre los datos reales:

    denominador ponderado      78 -> 61 semanas - sd 10,49 -> 12,27 - indice 80,1
    denominador sin ponderar   78 semanas       - sd 10,49 ->  9,39 - indice 69,6

Ponderar la muestra la encoge: semanas enteras caen bajo el minimo de comentarios y la
serie se vuelve mas ruidosa. Sin ponderarla, el peso solo cambia cuanto dice cada
comentario sobre la institucion, y la serie queda MENOS volatil que la actual.

El peso vale para las dos caras, y lo enseno un caso real
---------------------------------------------------------
Durante la paralizacion de junio-julio, los 45 comentarios negativos de mayor peso del
indice eran condolencias por la muerte de Blanquita, una perra de la manada del campus.
El modelo los marca NEG y hace bien -son tristes-, pero contarlos como dano completo
convertia el duelo por una perra en el mayor golpe reputacional de un paro.

Si un aplauso a la manada no es merito de la UCN, una pena por la manada tampoco es su
culpa. El peso mide cuanto habla ese tema DE LA INSTITUCION, y eso no cambia con el
signo del comentario.

⚠️ ESO SIGUE VALIENDO, PERO YA NO ES TODO (09-2026)
---------------------------------------------------
El esquema «DAI x peso de tema» agrego un recorte ENCIMA del peso: el CREDITO de un
tema no atribuible se corta a la mitad y el DAÑO no. Asi que los numeros de este
archivo cambiaron en el lado positivo —mascotas POS pasa de 55,0 a 52,5— mientras el
lado negativo quedo intacto (mascotas NEG sigue en 45,0).

Este archivo sigue fijando el PESO DEL TEMA. La asimetria entre credito y daño la fija
`test_percepcion_credito_atribuible.py`, que es donde estan la medicion y el porque.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.percepcion import ponderacion


class _Fila:
    def __init__(self, tema: str | None, sentimiento: str, fecha: date = date(2026, 6, 20)):
        self.tema = tema
        self.sentimiento = sentimiento
        self.fecha = fecha


DIA = date(2026, 6, 20)


def test_el_aplauso_de_un_tema_liviano_suma_poco():
    """100 felicitaciones a los perros no ponen el índice en 100.

    El crédito es 0,1 (peso del tema) × 0,5 (no es atribuible) = 0,05 por comentario.
    """
    filas = [_Fila("mascotas", "POS")] * 100

    idx = ponderacion.indice_ponderado(filas, DIA, DIA)

    assert idx == pytest.approx(52.5, abs=0.5), (
        f"credito 0,1·0,5 sobre 100 comentarios deberia rondar 52,5, dio {idx}"
    )


def test_el_mismo_aplauso_en_un_tema_pesado_suma_entero():
    """La contraparte: elogiar los servicios sí es crédito para la institución."""
    filas = [_Fila("servicios_institucionales", "POS")] * 100

    assert ponderacion.indice_ponderado(filas, DIA, DIA) == pytest.approx(100.0)


def test_el_dano_de_un_tema_liviano_tambien_pesa_poco():
    """Un tema liviano lo es en las DOS direcciones. Lo enseñó un caso real.

    Durante la paralización de junio-julio, los 45 negativos de mayor peso del índice
    eran condolencias por la muerte de Blanquita, una perra de la manada del campus.
    El modelo los marca NEG y hace bien —son tristes—, pero contarlos como daño
    completo convertía el duelo por una perra en el mayor golpe reputacional de un
    paro universitario.

    Si un aplauso a la manada no es mérito de la UCN, una pena por la manada tampoco
    es su culpa.
    """
    filas = [_Fila("mascotas", "NEG")] * 100

    assert ponderacion.indice_ponderado(filas, DIA, DIA) == pytest.approx(45.0, abs=0.5)


def test_el_dano_de_un_tema_pesado_resta_entero():
    """La contraparte: una queja sobre servicios sí es daño institucional completo."""
    filas = [_Fila("servicios_institucionales", "NEG")] * 100

    assert ponderacion.indice_ponderado(filas, DIA, DIA) == pytest.approx(0.0)


def test_el_denominador_no_se_pondera():
    """Ponderar la muestra costaría cobertura: 17 semanas, medido.

    Con 10 comentarios livianos y 10 pesados, el denominador tiene que ser 20 — no
    10·0,1 + 10·1,0. Si el peso encogiera la muestra, semanas enteras caerían bajo el
    mínimo de comentarios y desaparecerían de la serie.
    """
    filas = [_Fila("mascotas", "POS")] * 10 + [_Fila("servicios_institucionales", "POS")] * 10

    idx = ponderacion.indice_ponderado(filas, DIA, DIA)

    # credito = 10*(0,1*0,5) + 10*1,0 = 10,5 ; denominador = 20 (los 20 comentarios).
    # `mascotas` lleva el recorte por no ser atribuible; `servicios` no.
    assert idx == pytest.approx(50 + 50 * 10.5 / 20, abs=0.1)


def test_un_tema_desconocido_usa_el_peso_por_defecto():
    """Aparece un tema nuevo y el índice no puede romperse ni asumir peso pleno.

    Cae al peso por defecto Y al lado no atribuible, que son las dos decisiones
    conservadoras: ni crédito pleno ni mérito supuesto.
    """
    filas = [_Fila("tema_que_no_existe_todavia", "POS")] * 100

    idx = ponderacion.indice_ponderado(filas, DIA, DIA)

    esperado = 50 + 50 * ponderacion.PESO_POR_DEFECTO * ponderacion.CREDITO_NO_ATRIBUIBLE
    assert idx == pytest.approx(esperado, abs=0.5)


def test_los_neutrales_no_suman_ni_restan_pero_diluyen():
    """Un neutral no es crédito ni daño, pero sí es parte de la conversación."""
    solo_pos = ponderacion.indice_ponderado(
        [_Fila("academico", "POS")] * 10, DIA, DIA)
    con_neutrales = ponderacion.indice_ponderado(
        [_Fila("academico", "POS")] * 10 + [_Fila("academico", "NEU")] * 10, DIA, DIA)

    assert solo_pos > con_neutrales > 50


def test_sin_datos_devuelve_none():
    assert ponderacion.indice_ponderado([], DIA, DIA) is None


def test_los_pesos_cubren_todos_los_temas_del_corpus():
    """Un tema sin peso explícito es una decisión no tomada, no un default.

    Los 8 temas de la taxonomía tienen que estar declarados: si uno queda afuera y
    cae al peso por defecto, nadie se entera de que su relevancia nunca se decidió.
    """
    del_corpus = {
        "vida_estudiantil", "logros_reconocimientos", "academico", "mascotas",
        "servicios_institucionales", "organizacion_estudiantil", "otros",
        "bienestar_salud",
    }

    faltan = del_corpus - set(ponderacion.PESOS_POR_TEMA)

    assert not faltan, f"temas sin peso declarado: {sorted(faltan)}"
