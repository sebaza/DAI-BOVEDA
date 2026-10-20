"""POSTURA institucional: si un comentario favorece o perjudica a la UCN.

NO es el sentimiento. El sentimiento es el TONO del comentario; la postura es su
efecto para la institución. «¿Paro? 😍» tiene tono positivo y postura adversa, y
«qué lindo el perrito 🥹» tiene tono positivo y postura NEUTRAL — es cariño por un
animal, no una opinión sobre la universidad.

LA REGLA
--------
    NEG                       -> adverso
    NEU                       -> neutral
    POS + tema atribuible     -> favorable
    POS + tema no atribuible  -> neutral

«Atribuible» = el tema le asigna el mérito a la institución. Un logro, una clase,
un trámite bien resuelto o una prestación de bienestar hablan de la UCN. Un carrete,
una mascota o una asamblea estudiantil ocurren EN la UCN sin ser mérito suyo.

POR QUÉ ASÍ Y NO DE OTRA FORMA (medido sobre 150 comentarios de muestra aleatoria
anotados a mano, criterio vigente):

    clase mayoritaria                             44,7 %   ventaja  +0,0
    tono -> postura (la regla anterior)           66,7 %   ventaja +22,0
    ESTA REGLA                                    80,7 %   ventaja +36,0
    tabla completa (tono × tema, 19 celdas)       72,7 %   ventaja +28,0
    + «conflicto en el caption -> adverso»        79,3 %   ventaja +34,7

Los dos últimos se PROBARON Y SE DESCARTARON. La tabla de 19 celdas aprende cada
combinación por separado y sobreajusta: con 150 ejemplos hay celdas de n=1. La
regla de conflicto (paro/toma/petitorio en el caption) empeora y ni siquiera sube
la detección de adversos (76 % en los dos casos).

También se probaron embeddings semánticos (`paraphrase-multilingual-MiniLM`,
leave-one-out sin publicaciones hermanas): 63,3 % en el mejor caso, muy por debajo
de esta regla de cuatro líneas.

EL PERFIL DE ERROR ES LO MEJOR QUE TIENE. Matriz sobre los 150 (fila=regla,
columna=humano):

                favorable  neutral  adverso
    favorable          48       10        0
    neutral            14       55        5
    adverso             0        2       16

**Las dos esquinas opuestas están en cero**: nunca llama «favorable» a un comentario
adverso ni al revés. Toda la confusión vive entre favorable y neutral, que es el
error barato. Para un tablero institucional esa propiedad vale más que un par de
puntos de acuerdo, y hay que conservarla si alguna vez se cambia la regla.

⚠️ ESO ES LA REGLA SOLA. La cadena de producción también PREDICE el tono, y ahí los
errores se acumulan: con sentimiento predicho (88,7 %) y tema predicho (55,3 %) la
postura da **75,3 %, kappa 0,589, ventaja +30,7** — no 80,7 %. Y aparece 1 cruce
grave en 150 (el modelo dice adverso donde el humano puso favorable), que viene de
un error de TONO, no de esta regla:

                favorable  neutral  adverso
    favorable          46       10        0
    neutral            15       54        8
    adverso             1        3       13

O sea: la propiedad la garantiza la regla dadas entradas correctas, y el test que
la fija prueba exactamente eso. De punta a punta hay que decir 75,3 %, que es lo
que ve quien mira el tablero.

AUDITORÍA DE LA REGLA (19-08-2026). Se probó mover cada pieza y **ninguna
variante mejora**, así que esto es un óptimo local sobre los datos que hay:

    quitar academico       -9,3     agregar mascotas             -4,0
    quitar logros         -11,3     agregar vida_estudiantil    -10,0
    quitar servicios       -3,3     agregar organizacion_est.    +0,0
    quitar bienestar       -1,3     agregar otros                +0,0
    NEU + atribuible -> favorable   -7,3

LO QUE FALTA, Y POR QUÉ NO SE HIZO
----------------------------------
Detecta el 76 % de los adversos (16 de 21). Los 5 que se escapan son todos el
mismo patrón: **tono positivo o neutro apoyando movilización contra la
universidad**. «Me parece un excelente trabajo. Bien ahí.» sobre un *oficio a la
superintendencia de educación superior*; «Muy bien 👏» sobre una *asamblea*.

Se probó atacarlo con el vocabulario observado en esos 5 (pleno extraordinario,
superintendencia, oficio, asamblea, comunicado) y **se rechazó**:

* Daba 82,7 % con 100 % de recall de adversos… pero ese vocabulario salió de esos
  mismos 5 comentarios, así que el recall está garantizado por construcción. No es
  evidencia, es memorizar.
* Aplicado al corpus marcaría **96 comentarios (3,3 %) como adversos**, subiendo lo
  adverso de 7,7 % a 11,0 % — un 43 % más. Y las publicaciones que activa son en su
  mayoría convocatorias y comunicados normales: «Hacemos el llamado a seguir los
  procesos indicados en el protocolo», «Hoy sostuvimos una reunión con el
  Subsecretario de Educación Superior». Marcar eso como adverso es peor que no
  detectarlo.

Con 21 adversos en el patrón de oro no alcanza para aprender ese patrón sin
sobreajustar. Destrabarlo necesita ~50 adversos, o sea ~350 comentarios anotados.
Hasta entonces, la regla prefiere no detectar antes que inventar.
"""
from __future__ import annotations

from app.config import get_settings

POSTURA_FAVORABLE = "favorable"
POSTURA_NEUTRAL = "neutral"
POSTURA_ADVERSO = "adverso"

POSTURAS = (
    {"valor": POSTURA_FAVORABLE, "etiqueta": "Favorable a la UCN"},
    {"valor": POSTURA_NEUTRAL, "etiqueta": "Sin postura institucional"},
    {"valor": POSTURA_ADVERSO, "etiqueta": "Adverso a la UCN"},
)
ETIQUETAS_POSTURA = {p["valor"]: p["etiqueta"] for p in POSTURAS}
ORDEN_POSTURA = (POSTURA_FAVORABLE, POSTURA_NEUTRAL, POSTURA_ADVERSO)

# Temas cuyo tono positivo SÍ le suma a la institución.
#
# ⚠️ Sale de los datos, no de una intuición. Sobre los 150 anotados, el tono positivo
# se leyó como favorable en académico (18/22), logros (18/19), servicios (8/11) y
# bienestar (4/6); y como NEUTRAL en vida estudiantil (19/23), mascotas (6/6),
# organización estudiantil (6/13) y otros (4/10).
#
# Si se agrega un tema a la taxonomía hay que decidir de qué lado cae, y decidirlo
# CON ANOTACIÓN: por omisión queda como no atribuible, que es el lado conservador
# (nunca infla lo favorable).
# --------------------------------------------------------------------------- #
# ⚠️ LAS ANOTACIONES DEL AGENTE NO SIRVEN COMO GROUND TRUTH DE POSTURA
# --------------------------------------------------------------------------- #
# Medido el 02-09-2026 sobre `percepcion_correccion` (campo `postura`, última
# anotación por comentario): hay 2.887 comentarios anotados, pero **2.737 los anotó
# un AGENTE y replican el TONO, no la postura**.
#
# La prueba está en el caso donde las dos cosas se separan — POSITIVOS con tema NO
# atribuible, que la regla manda a `neutral`:
#
#                    favorable   neutral   adverso
#     humano (n=51)        11        38         2      75 % neutral  → postura
#     agente (n=799)      721        69         9      90 % favorable → TONO
#
# Y la coincidencia con el puro tono: humano 66,7 %, agente **90,4 %**.
#
# CONSECUENCIA PRÁCTICA: cualquier evaluación que mezcle las dos fuentes concluye
# que la mejor regla es «tono → postura», que es EXACTAMENTE la que se descartó por
# medición más arriba (66,7 % contra 80,7 %). Medido: contra las 2.887 mezcladas, el
# tono da 89,2 % y la regla vigente 67,5 %; contra las 150 humanas se invierte y la
# vigente da 84,7 %.
#
#     → Para evaluar o entrenar postura, FILTRAR `autor_tipo = 'humano'`.
#
# EL CUELLO DE BOTELLA NO ES LA REGLA, SON LOS DATOS. Se probaron cuatro variantes
# contra las 150 humanas —cuenta de federación a neutral, cuenta + léxico a adverso,
# favorable ampliado, y las dos combinadas— y **ninguna supera a la vigente**
# (84,7 %; las variantes dan 84,0 %, 84,0 %, 70,0 % y 69,3 %). El lado adverso solo
# tiene **21 ejemplos humanos**: no alcanza para calibrar nada ahí. Lo que hace falta
# es anotar más adversos a mano, no una regla más ingeniosa.
TEMAS_ATRIBUIBLES = frozenset({
    "academico",
    "logros_reconocimientos",
    "servicios_institucionales",
    "bienestar_salud",
})


# --------------------------------------------------------------------------- #
# LA CUARTA LÍNEA DE LA REGLA (10-09-2026): NEU + federación -> adverso
# --------------------------------------------------------------------------- #
# Es la PRIMERA variante que supera a la regla base con evidencia. Todas las
# anteriores empataban dentro del intervalo de confianza — ver la lista de arriba.
#
# Medido sobre un holdout de 237 anotaciones humanas con 53 adversos (cola
# aleatoria + cola estratificada, RE-PESADAS por estrato), bootstrap de 3.000
# remuestreos dentro de cada estrato:
#
#     regla (tono NEU +)            acuerdo  recall   IC95 recall     P    graves
#     base (las tres líneas)         82,4%    72%          —          —      1
#     + tipo='federacion' (ESTA)     82,9%    83%    [+6,1,+18,8]   100%     1
#     + federación sin mirar tono    83,2%    84%          —          —    **3**
#     + org.estudiantil -> adverso   80,9%    92%          —          —   **11**
#
# El recall sube 11 puntos y el intervalo NO incluye el cero. El acuerdo global
# sube poco (+0,5, no demostrable) pero tampoco empeora.
#
# ⚠️ POR QUÉ «Y TONO NEU» Y NO LA CUENTA SOLA. Sin restringir el tono se gana un
# punto más de recall y se TRIPLICAN los cruces graves, que son lo que esta regla
# protege por encima de todo. Los dos que aparecen son «❤️❤️❤️» y «Excelente
# comunicado! ❤️‍🔥💪🏻», los dos anotados FAVORABLE por un humano: gente felicitando
# a la federación, marcada adversa solo por dónde comentó. La restricción los deja
# afuera y se sostiene fuera de los datos — un positivo ahí puede ser apoyo
# genuino; un neutro («¿Y cuál es el petitorio?», «Alguien que me cuente por qué
# están en tomaaaaaa») es participación en el conflicto.
#
# ⚠️ SE DESCARTÓ `org.estudiantil -> adverso`, que parecía lo obvio: 53 % de
# adversos en la cola DIRIGIDA contra 20 % en el holdout limpio. La cola dirigida
# sobreestima porque selecciona los candidatos con señal; descubrir un patrón ahí y
# medirlo ahí mismo confirma cualquier cosa.
#
# Se usa el CAMPO `percepcion_cuenta.tipo`, no el nombre: son cuatro cuentas
# (@feucn, @recreo.feucn, @feucn_c, @seneudis) y filtrar por nombre capturaba una.
# `centro_alumnos` se probó y se descartó: lleva lo adverso al 21 % del corpus.
CUENTA_FEDERACION = "federacion"
# Mueve lo adverso del 9,0 % al 10,9 % del corpus (124 comentarios), así que rompe
# la comparabilidad con lo reportado antes. Es una decisión institucional y su
# vuelta atrás no puede depender de un release. Mismo criterio que
# `ponderacion.CREDITO_NO_ATRIBUIBLE`.
NEU_FEDERACION_ES_ADVERSO = get_settings().percepcion_neu_federacion_adverso


def postura_de(sentimiento: str | None, tema: str | None,
               cuenta_tipo: str | None = None) -> str:
    """Postura institucional de un comentario a partir de su tono, tema y cuenta.

    `cuenta_tipo` es OPCIONAL y por omisión la regla se comporta como antes. No es
    un descuido: la tabla de hechos no guarda la cuenta, así que las vistas que aún
    no bajan al corpus tienen que seguir dando el número de siempre en vez de uno a
    medias. Ver `repository._conteos_postura`.
    """
    if sentimiento == "NEG":
        return POSTURA_ADVERSO
    if (NEU_FEDERACION_ES_ADVERSO and sentimiento == "NEU"
            and cuenta_tipo == CUENTA_FEDERACION):
        return POSTURA_ADVERSO
    if sentimiento == "POS" and tema in TEMAS_ATRIBUIBLES:
        return POSTURA_FAVORABLE
    return POSTURA_NEUTRAL


def postura_valida(valor: str) -> bool:
    return valor in ETIQUETAS_POSTURA


def contar_por_postura(tema: str | None, n_pos: int, n_neu: int, n_neg: int,
                       cuenta_tipo: str | None = None) -> dict[str, int]:
    """Reparte los conteos de tono de UNA fila de hechos entre las tres posturas.

    Se puede hacer exactamente —sin aproximar y sin re-agregar— porque el grano de
    `percepcion_hecho_diario` YA incluye `tema`: dentro de una fila el tema es fijo,
    así que el tono determina la postura sin ambigüedad. Por eso la postura no
    necesitó ninguna columna nueva ni ninguna migración.
    """
    atribuible = tema in TEMAS_ATRIBUIBLES
    # Los neutros de una cuenta de la federación se van con los adversos. Dentro de
    # una fila la cuenta es fija —igual que el tema—, así que el reparto sigue
    # siendo exacto y no necesita bajar al comentario.
    neu_adverso = (NEU_FEDERACION_ES_ADVERSO and cuenta_tipo == CUENTA_FEDERACION)
    return {
        POSTURA_FAVORABLE: n_pos if atribuible else 0,
        POSTURA_NEUTRAL: (0 if neu_adverso else n_neu) + (0 if atribuible else n_pos),
        POSTURA_ADVERSO: n_neg + (n_neu if neu_adverso else 0),
    }
