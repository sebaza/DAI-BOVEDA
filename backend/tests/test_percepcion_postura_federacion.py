"""Un NEUTRO en una cuenta de la federación es ADVERSO. La primera mejora demostrable.

QUÉ CAMBIA Y POR QUÉ
--------------------
La regla de postura acertaba el 82,4 % pero solo detectaba el **72 % de los
adversos**, y ese lado es el que el módulo existe para ver. Todas las variantes
probadas hasta ahora empataban dentro del intervalo de confianza. Esta no.

Medida sobre un holdout de **237 anotaciones humanas con 53 adversos** —cola
aleatoria + cola estratificada, re-pesadas por estrato— con bootstrap de 3.000
remuestreos DENTRO de cada estrato:

    regla (tono NEU +)            acuerdo  recall   IC95 recall     P    graves
    VIGENTE                        82,4%    72%          —          —      1
    tipo='federacion' (esta)       82,9%    83%    [+6,1,+18,8]   100%     1
    federación sin restringir tono 83,2%    84%          —          —    **3**
    org.estudiantil -> adverso     80,9%    92%          —          —   **11**

**El recall sube 11 puntos y el intervalo no incluye el cero.** El acuerdo global
sube poco (+0,5, no demostrable) pero no empeora.

POR QUÉ `Y TONO NEU`, Y NO LA CUENTA SOLA
------------------------------------------
La cuenta sola da un punto más de recall y **triplica los cruces graves**, que son
los que `postura.py` protege por encima de todo. Los dos que aparecen:

    regla=adverso  humano=favorable  '❤️❤️❤️'
    regla=adverso  humano=favorable  'Excelente comunicado! ❤️‍🔥💪🏻'

Gente FELICITANDO a la federación, marcada adversa solo por dónde comentó. La
restricción a NEU los deja afuera y tiene sentido fuera de los datos: un positivo
ahí puede ser apoyo genuino; un neutro —«¿Y cuál es el petitorio?», «Alguien que
me cuente por qué están en tomaaaaaa»— es participación en el conflicto.

EL CAMPO, NO EL NOMBRE
----------------------
`tipo='federacion'` son CUATRO cuentas (@feucn, @recreo.feucn, @feucn_c,
@seneudis); filtrar por nombre capturaba solo la primera. Se re-midió con el campo
antes de escribir esto y da lo mismo (recall 83 %, 1 cruce grave).

⚠️ SE DESCARTÓ `org.estudiantil -> adverso`, que parecía la regla obvia: 53 % de
adversos en la cola dirigida contra **20 % en el holdout limpio**. La cola dirigida
sobreestima porque selecciona los candidatos con señal.

MUEVE EL NÚMERO QUE VE EL DIRECTOR
-----------------------------------
Lo adverso pasa de 9,0 % a 10,9 % del corpus (124 comentarios). Por eso es
reversible por entorno, igual que el crédito atribuible: es una decisión
institucional y su vuelta atrás no puede depender de un release.
"""
from __future__ import annotations

import unittest

from app.services.percepcion import postura as P


class TestReglaFederacion(unittest.TestCase):
    def setUp(self):
        self._previo = P.NEU_FEDERACION_ES_ADVERSO
        P.NEU_FEDERACION_ES_ADVERSO = True

    def tearDown(self):
        P.NEU_FEDERACION_ES_ADVERSO = self._previo

    def test_un_neutro_en_la_federacion_es_adverso(self):
        """«¿Y cuál es el petitorio?» no tiene tono, pero sí postura."""
        self.assertEqual(
            P.postura_de("NEU", "organizacion_estudiantil", cuenta_tipo="federacion"),
            P.POSTURA_ADVERSO)

    def test_vale_para_cualquier_tema_de_la_federacion(self):
        """La señal es la cuenta, no el tema: se descartó la regla por tema."""
        for tema in ("otros", "academico", "vida_estudiantil", None):
            with self.subTest(tema=tema):
                self.assertEqual(
                    P.postura_de("NEU", tema, cuenta_tipo="federacion"), P.POSTURA_ADVERSO)

    def test_un_POSITIVO_en_la_federacion_NO_se_vuelve_adverso(self):
        """LA PROPIEDAD QUE PROTEGE ESTE TEST.

        Sin la restricción a NEU, «Excelente comunicado! ❤️‍🔥» —anotado FAVORABLE
        por un humano— pasaba a adverso, y los cruces graves se triplicaban. Un
        positivo en la federación puede ser apoyo genuino.
        """
        self.assertEqual(
            P.postura_de("POS", "organizacion_estudiantil", cuenta_tipo="federacion"),
            P.POSTURA_NEUTRAL)
        self.assertEqual(
            P.postura_de("POS", "academico", cuenta_tipo="federacion"),
            P.POSTURA_FAVORABLE, "un tema atribuible sigue sumando aunque sea la federación")

    def test_un_negativo_sigue_siendo_adverso_venga_de_donde_venga(self):
        for tipo in ("federacion", "institucional", None):
            with self.subTest(tipo=tipo):
                self.assertEqual(P.postura_de("NEG", "academico", cuenta_tipo=tipo),
                                 P.POSTURA_ADVERSO)

    def test_un_neutro_fuera_de_la_federacion_sigue_neutral(self):
        for tipo in ("institucional", "centro_alumnos", "facultad", None):
            with self.subTest(tipo=tipo):
                self.assertEqual(
                    P.postura_de("NEU", "organizacion_estudiantil", cuenta_tipo=tipo),
                    P.POSTURA_NEUTRAL)

    def test_centro_de_alumnos_NO_entra(self):
        """Medido: sumarlos lleva lo adverso al 21 % del corpus. Se descartó."""
        self.assertEqual(
            P.postura_de("NEU", "organizacion_estudiantil", cuenta_tipo="centro_alumnos"),
            P.POSTURA_NEUTRAL)

    def test_sin_saber_la_cuenta_no_se_inventa(self):
        """Donde no hay dato de cuenta, la regla se comporta como antes.

        Es lo que permite que las vistas que aún no bajan al corpus sigan dando el
        número de siempre en vez de uno a medias.
        """
        self.assertEqual(P.postura_de("NEU", "organizacion_estudiantil"), P.POSTURA_NEUTRAL)


class TestReversibilidad(unittest.TestCase):
    def test_con_la_regla_apagada_vuelve_el_comportamiento_anterior(self):
        """Mueve el índice adverso del 9,0 % al 10,9 %: la vuelta atrás no puede
        depender de un release. Mismo criterio que el crédito atribuible."""
        previo = P.NEU_FEDERACION_ES_ADVERSO
        P.NEU_FEDERACION_ES_ADVERSO = False
        try:
            self.assertEqual(
                P.postura_de("NEU", "organizacion_estudiantil", cuenta_tipo="federacion"),
                P.POSTURA_NEUTRAL)
        finally:
            P.NEU_FEDERACION_ES_ADVERSO = previo


class TestContarPorPostura(unittest.TestCase):
    """El reparto agregado tiene que seguir a la regla, o las dos vistas se separan."""

    def setUp(self):
        self._previo = P.NEU_FEDERACION_ES_ADVERSO
        P.NEU_FEDERACION_ES_ADVERSO = True

    def tearDown(self):
        P.NEU_FEDERACION_ES_ADVERSO = self._previo

    def test_los_neutros_de_la_federacion_van_a_adverso(self):
        c = P.contar_por_postura("organizacion_estudiantil", 10, 20, 5,
                                 cuenta_tipo="federacion")

        self.assertEqual(c[P.POSTURA_ADVERSO], 25, "20 neutros + 5 negativos")
        self.assertEqual(c[P.POSTURA_NEUTRAL], 10, "los positivos no atribuibles")
        self.assertEqual(c[P.POSTURA_FAVORABLE], 0)

    def test_fuera_de_la_federacion_no_cambia_nada(self):
        c = P.contar_por_postura("organizacion_estudiantil", 10, 20, 5,
                                 cuenta_tipo="institucional")

        self.assertEqual(c, P.contar_por_postura("organizacion_estudiantil", 10, 20, 5))

    def test_el_reparto_siempre_conserva_el_total(self):
        """Si el reparto perdiera o inventara comentarios, los porcentajes mentirían."""
        for tipo in ("federacion", "institucional", None):
            for tema in ("academico", "mascotas", None):
                with self.subTest(tipo=tipo, tema=tema):
                    c = P.contar_por_postura(tema, 7, 11, 3, cuenta_tipo=tipo)
                    self.assertEqual(sum(c.values()), 21)
