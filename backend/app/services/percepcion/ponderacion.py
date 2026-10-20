"""Índice ponderado por TEMA: cuánto habla de la institución cada comentario.

Por qué
-------
No todos los temas hablan igual de la institución. Un aplauso a los perros del campus
no dice lo mismo sobre la UCN que un elogio a la docencia, y hoy pesan igual. La
postura ya reconoce eso pero de forma binaria —un tema es atribuible o no—; esto lo
hace continuo.

El problema que resuelve: durante un paro el índice general sale tranquilo porque los
departamentos siguen publicando logros y ese aplauso entra al mismo promedio que la
protesta. Medido sobre las ventanas de conflicto:

    Paralización general junio-julio   71,8 -> 62,9
    Paro por gestión de la emergencia  70,2 -> 57,8
    Toma pabellón de Geología          95,7 -> 79,8

El denominador NO se pondera. Ahí está la diferencia
---------------------------------------------------
Es lo que decide si esto sirve. Con el denominador ponderado el peso encoge la
muestra, semanas enteras caen bajo el mínimo de comentarios y la serie se vuelve más
ruidosa. Sin ponderarlo, el peso solo cambia cuánto dice cada comentario sobre la
institución. Medido sobre los datos reales:

    denominador ponderado      78 -> 61 semanas · sd 10,49 -> 12,27 · índice 80,1
    denominador sin ponderar   78 semanas       · sd 10,49 ->  9,39 · índice 69,6

La segunda es MENOS volátil que el índice actual y no pierde una sola semana.

El peso del tema se aplica a los DOS lados, y por un caso concreto
------------------------------------------------------------------
Durante la paralización de junio-julio, los 45 comentarios negativos de mayor peso del
índice eran condolencias por la muerte de Blanquita, una perra de la manada del
campus: «mi viejita pesada :(», «descansa en paz», «mis más sinceras condolencias».

El modelo los marca NEG y hace bien —son tristes— pero no tienen ninguna adversidad
institucional. Contarlos como daño completo convertía el duelo por una perra en el
mayor golpe reputacional de un paro universitario.

Un tema liviano lo es en las dos direcciones: si un aplauso a la manada no es mérito
de la UCN, una pena por la manada tampoco es su culpa. El peso mide cuánto habla ese
tema DE LA INSTITUCIÓN, y eso no cambia con el signo del comentario.

...pero ENCIMA de eso, el crédito se recorta por atribuibilidad
---------------------------------------------------------------
Esquema «DAI × peso de tema», vigente desde 09-2026. Sobre el peso del tema —que sigue
valiendo para las dos caras— el CRÉDITO de un tema no atribuible se corta a la mitad,
y el DAÑO no se toca:

    crédito = peso_tema · CREDITO_NO_ATRIBUIBLE   (si el tema NO es atribuible)
    daño    = peso_tema                            (siempre)

Es la matriz tono × postura que pidió la DAI, resuelta sobre la postura que el sistema
sabe derivar hoy. Como `postura_de()` hace que el tema fije la postura de un positivo
—atribuible → favorable, no atribuible → neutral—, la matriz colapsa exactamente a
esta línea:

    POS + favorable  ×2 / 2 = 1,0 · peso_tema
    POS + neutral    ×1 / 2 = 0,5 · peso_tema     <- el único cambio real
    NEU              × 0                           (no mueve la barra)
    NEG + adverso    ×2 / 2 = 1,0 · peso_tema

MEDIDO sobre 4 años (8.174 comentarios, 80 semanas con n≥20, 8 paros + 4 tomas +
1 emergencia). AUC = P(semana de conflicto quede bajo una de calma); shock = caída en
la emergencia del 07-04-2025 en desvíos de la propia serie:

    esquema                AUC conflicto   AUC gestación   shock (σ)    sd
    canónico                   0,610           0,569         −1,85     10,51
    peso de tema (anterior)    0,640           0,620         −1,31      9,34
    matriz DAI cruda           0,636           0,558         −2,21     10,75
    ESTE                       0,643           0,618         −1,55      9,08

Se eligió sobre la matriz cruda porque esa aplana a 0,5 TODO positivo no atribuible
sin distinguir `organizacion_estudiantil` (peso 1,0, donde se gesta el conflicto) de
`mascotas` (0,1). Le cuesta 0,062 de AUC en gestación —la señal que el módulo existe
para dar— a cambio de reaccionar más al shock. Conservando el peso continuo dentro de
cada celda se queda con las dos cosas.

⚠️ NADA DE ESTO ES ESTADÍSTICAMENTE DISTINGUIBLE. Con 19 semanas de conflicto y 38 de
calma, los IC del 95 % por bootstrap se solapan por completo y todos incluyen 0,5. La
ventaja de 0,643 sobre 0,640 es ruido. Este cambio se adopta por su lectura
institucional —un aplauso que no es mérito de la UCN no es crédito pleno— y no porque
discrimine mejor: eso no se puede afirmar con los datos que hay. Si alguien vuelve a
tocar el esquema, la pregunta que decide NO es el AUC; es qué se quiere que el número
signifique.

LO QUE QUEDÓ AFUERA: la propuesta original también quería activar los neutros
(NEU+favorable → positivo, NEU+adverso → negativo). Esas dos celdas están VACÍAS —
`postura_de()` manda todo neutro a `neutral`—, así que son 1.922 comentarios (23,5 %
del corpus) que siguen aportando cero. Destrabarlo necesita una postura independiente
del tono, que es el proyecto de fondo. Ver `postura` para lo que hace falta.

Diferencia con `postura`: allá un negativo es adverso siempre (regla binaria validada
contra 150 anotaciones). Acá el peso del tema modula las dos caras y la atribuibilidad
recorta una. Son dos lecturas distintas y conviven; no se reemplazan.

De dónde salen estos pesos
--------------------------
Perfil «riesgo reputacional»: prioriza lo que puede escalar a un conflicto o a prensa.
Elegido explícitamente, con la excepción de `logros_reconocimientos`, que en ese perfil
iba a 0,2 y se subió a 0,5 para no castigar de forma permanente a la institución por
comunicar bien. Cambiar estos números es una decisión institucional, no técnica.
"""
from __future__ import annotations

from datetime import date

from app.config import get_settings
from app.services.percepcion.postura import TEMAS_ATRIBUIBLES

# Cuánto habla DE LA INSTITUCIÓN un comentario de cada tema. Se aplica igual al
# crédito de un positivo que al daño de un negativo: si el aplauso a la manada no es
# mérito de la UCN, la pena por la manada tampoco es su culpa.
#
#   1.0  habla directamente de cómo funciona la institución
#   0.5  la involucra, pero es comunicación propia o contexto
#   0.1  ocurre EN la UCN sin ser mérito suyo
PESOS_POR_TEMA: dict[str, float] = {
    "organizacion_estudiantil": 1.0,   # lo que puede escalar; el más negativo (20 %)
    "servicios_institucionales": 1.0,  # trámites, infraestructura: gestión pura
    "academico": 0.9,                  # docencia y ramos: el corazón del servicio
    "bienestar_salud": 0.8,            # prestaciones reales a estudiantes
    "logros_reconocimientos": 0.5,     # es mérito, pero también es la UCN comunicándose
    "otros": 0.5,                      # sin clasificar: ni se premia ni se castiga
    "vida_estudiantil": 0.3,           # pasa en la UCN; el aplauso no es a la gestión
    "mascotas": 0.1,                   # la manada del campus: cariño, no evaluación
}

# Un tema que no esté en la tabla es una decisión que nadie tomó. Se le da peso medio
# —ni crédito pleno ni cero— y hay un test que exige declarar los de la taxonomía.
PESO_POR_DEFECTO = 0.5

# Cuánto del peso conserva el CRÉDITO de un tema NO atribuible. Ver el docstring del
# módulo para la medición. Configurable por `PERCEPCION_CREDITO_NO_ATRIBUIBLE`: con 1,0
# se vuelve al esquema simétrico anterior sin tocar código, que es la vuelta atrás de
# una decisión que mueve el nivel del índice y rompe comparabilidad histórica.
CREDITO_NO_ATRIBUIBLE = get_settings().percepcion_credito_no_atribuible


def peso_de(tema: str | None) -> float:
    """Cuánto habla DE LA INSTITUCIÓN un comentario de este tema, sin mirar el signo."""
    return PESOS_POR_TEMA.get(tema or "", PESO_POR_DEFECTO)


def peso_credito(tema: str | None) -> float:
    """Cuánto CRÉDITO le da a la institución un positivo de este tema.

    `TEMAS_ATRIBUIBLES` se lee de `postura` y no se copia acá a propósito: si las dos
    listas se separaran, la postura que el panel muestra y el peso que el índice usa
    dirían cosas distintas del mismo comentario y nadie se enteraría. Un tema que no
    esté declarado cae del lado no atribuible, que es el conservador —nunca infla lo
    favorable—, igual que en `postura`.
    """
    w = peso_de(tema)
    return w if tema in TEMAS_ATRIBUIBLES else w * CREDITO_NO_ATRIBUIBLE


def peso_dano(tema: str | None) -> float:
    """Cuánto DAÑO le hace un negativo de este tema. No se descuenta por atribuibilidad.

    Todo negativo es adverso (`postura_de`), así que acá solo pesa el tema. La
    asimetría con `peso_credito` es deliberada: un aplauso que no es mérito de la UCN
    no es crédito pleno, pero una queja sobre algo que pasa en la UCN sigue siendo
    algo que pasó en la UCN.
    """
    return peso_de(tema)


def indice_ponderado(filas, desde: date, hasta: date) -> float | None:
    """Índice de la ventana, ponderado por tema en sus dos caras.

    `filas` son registros con `.tema`, `.sentimiento` y `.fecha` — los que devuelve
    `critica.filas_de_comentarios`.

    Devuelve None sin datos: una ventana vacía no vale 50 ni 0.
    """
    credito = dano = 0.0
    n = 0
    for f in filas:
        if f.fecha is None or not (desde <= f.fecha <= hasta):
            continue
        # El denominador cuenta TODOS los comentarios sin ponderar: ponderarlo encoge
        # la muestra y cuesta 17 semanas de cobertura.
        n += 1
        if f.sentimiento == "POS":
            credito += peso_credito(f.tema)
        elif f.sentimiento == "NEG":
            dano += peso_dano(f.tema)
    if not n:
        return None
    return 50.0 + 50.0 * (credito - dano) / n


def aporte_por_tema(filas, desde: date, hasta: date) -> list[dict]:
    """Cuánto pone cada tema en la ventana: volumen, crédito y daño.

    Sirve para que el número sea auditable. Un índice ponderado que no se puede abrir
    por tema es una caja negra, y acá los pesos son una decisión discutible que
    conviene poder revisar contra los datos que la sostienen.
    """
    acc: dict[str, list[float]] = {}
    for f in filas:
        if f.fecha is None or not (desde <= f.fecha <= hasta):
            continue
        celda = acc.setdefault(f.tema or "(sin tema)", [0.0, 0.0, 0.0])
        celda[0] += 1
        if f.sentimiento == "POS":
            celda[1] += peso_credito(f.tema)
        elif f.sentimiento == "NEG":
            celda[2] += peso_dano(f.tema)
    return sorted(
        (
            {
                "tema": tema,
                "n": int(n),
                "peso": peso_de(clave),
                # Los dos pesos van por separado porque desde el esquema «DAI × peso de
                # tema» ya no son el mismo número, y un desglose que mostrara solo uno
                # no permitiría reconstruir el crédito ni el daño de la fila.
                "peso_credito": round(peso_credito(clave), 3),
                "peso_dano": round(peso_dano(clave), 3),
                "atribuible": clave in TEMAS_ATRIBUIBLES,
                "credito": round(credito, 1),
                "dano": round(dano, 1),
                "aporte_neto": round(credito - dano, 1),
            }
            for tema, (n, credito, dano) in acc.items()
            for clave in (None if tema == "(sin tema)" else tema,)
        ),
        key=lambda d: d["aporte_neto"],
    )
