"""Lectura y cálculo del dashboard de percepción desde la tabla de HECHOS.

Todo (índice, distribución, evolución, por-tema, por-unidad, emociones, anomalías)
se deriva al vuelo de `percepcion_hecho_diario` aplicando un FILTRO común
(rango × sede × facultad × departamento × tema) + un CONTROL DE PESO:
  * peso_likes: si True, el índice pondera por likes (peso = 1 + ln(1+likes));
    si False, cada comentario pesa 1.
  * vida_media (días): decaimiento temporal LINEAL — el peso baja parejo día a día y a
    los `vida_media` días un comentario deja de contar (peso 0). vida_media ES, de hecho,
    la ventana efectiva hacia atrás. 0/None => sin decaimiento (cada punto = su día aislado).

La ventana se ancla a la fecha MÁS RECIENTE presente (no a hoy).

El GRÁFICO y el medidor son 'as-of-fecha': cada punto = índice de ESE día y hacia atrás
(trailing decaído sobre sus `vida_media` días previos), no el día aislado. Así un
comentario suelto no dibuja un pico; se diluye en su ventana y sube la confianza.

Índice (canónico; NO cambiar sin acordar con la DAI):
    índice   = 50 + 50·(Σ num_pos − Σ num_neg)/Σ den
    confianza = min(1, Σn/30) · (Σ suma_ganadora/Σn)   [siempre por volumen, sin pesos]
    * indice_actual  = decaído (recencia), anclado al día más reciente/seleccionado.
    * indice_promedio = llano sobre la ventana (sin ponderar recencia), como contraste.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.percepcion import lexico, ponderacion
from app.services.percepcion.models import PercepcionComentario as C
from app.services.percepcion.models import PercepcionCuenta as Cu
from app.services.percepcion.models import PercepcionEvento as Evento
from app.services.percepcion.models import PercepcionHechoDiario as H
from app.services.percepcion.postura import (
    ETIQUETAS_POSTURA,
    ORDEN_POSTURA,
    POSTURA_ADVERSO,
    contar_por_postura,
)
from app.services.percepcion.models import PercepcionPublicacion as P
from app.services.percepcion.models import PercepcionScore as S

# Espejo de `percepcion.topics.taxonomy.ETIQUETAS` del worker (él es el dueño).
#
# REVISIÓN 2026-08-14 — se partió «eventos». Medido sobre 150 comentarios de muestra
# aleatoria anotados a mano, ese solo tema se llevaba el **56,0 %** del corpus, con lo
# cual un clasificador que dijera siempre «eventos» acertaba 56,0 % y el matcher real
# apenas llegaba a 63,1 %: +7,1 puntos sobre no hacer nada. Adentro convivían al menos
# siete cosas distintas; la mayor, la agrupación de rescate animal `@Ellos También Son
# UCN`, que sola es el 10,7 % del corpus y no tenía tema propio.
#
# Tras la partición: clase mayoritaria **22,7 %** y la ventaja del clasificador sobre
# la clase mayoritaria pasa de +7,1 a **+42,0 puntos**.
ETIQUETAS_TEMA = {
    "academico": "Académico",
    "vida_estudiantil": "Vida estudiantil",
    "mascotas": "Mascotas y adopción",
    "logros_reconocimientos": "Logros y reconocimientos",
    "organizacion_estudiantil": "Organización estudiantil",
    "bienestar_salud": "Bienestar y salud",
    "servicios_institucionales": "Servicios y trámites",
    "otros": "Otros",
    # RETIRADOS. Se conserva su etiqueta para que los datos históricos que todavía
    # no se re-clasificaron no muestren la clave cruda en pantalla; no se ofrecen
    # para asignar a mano (ver `curacion.TEMAS_RETIRADOS`).
    "eventos": "Eventos (retirado)",
    "charlas_seminarios": "Charlas y seminarios (fusionado en Académico)",
    "infraestructura": "Infraestructura (fusionado en Servicios)",
    "tramites": "Trámites (fusionado en Servicios)",
    "matricula_aranceles": "Matrícula y aranceles (fusionado en Servicios)",
    "difusion_admision": "Difusión y admisión (fusionado en Servicios)",
}
ETIQUETAS_EMOCION = {
    "joy": "Alegría",
    "sadness": "Tristeza",
    "anger": "Enojo",
    "fear": "Miedo",
    "surprise": "Sorpresa",
    "humor_ironia": "Humor e ironía",
    "empatia": "Empatía",
    "sin_emocion": "Sin emoción",
    # Compatibilidad histórica con datos anteriores del worker.
    "disgust": "Asco (histórico)",
    "others": "Otra emoción (histórico)",
}


def etiquetas_tema(db) -> dict[str, str]:
    """ETIQUETAS_TEMA fijas + etiquetas de los temas CUSTOM (creados en la Torre)."""
    from app.services.percepcion.models import PercepcionTemaCustom as TC
    combinado = dict(ETIQUETAS_TEMA)
    try:
        for clave, etiqueta in db.execute(select(TC.clave, TC.etiqueta)):
            combinado[clave] = etiqueta
    except Exception:
        pass
    return combinado

N_MIN_CONFIANZA = 30
VIDA_MEDIA_DIAS = 30.0  # decaimiento por defecto

# --------------------------------------------------------------------------- #
# DETECCIÓN DE ANOMALÍAS — semanal, robusta y SEPARADA de la serie que se dibuja.
# --------------------------------------------------------------------------- #
# Por qué se rehízo (medido sobre percepcion_real.db, con el evento
# "Paro estudiantil 03/06/2026 – 03/07/2026" cargado como referencia):
#
#   La versión anterior detectaba sobre la MISMA serie trailing que se grafica.
#   Con vida_media=30 cada punto ya promedia sus 30 días previos, así que los
#   días consecutivos están fuertemente autocorrelacionados y un evento abrupto
#   se reparte en vez de saltar. Resultado medido: en TODA la ventana del paro el
#   |z| máximo fue 1.98 contra un umbral de 2.5 → CERO anomalías, mientras las 3
#   que sí marcaba en 4 años caían fuera de cualquier evento conocido. El piso de
#   dispersión que se había agregado para frenar falsos positivos terminaba
#   apagando también los verdaderos: los dos síntomas son la misma causa.
#
# Tres cambios:
#   1. GRANULARIDAD SEMANAL. El corpus tiene mediana de 5 comentarios/día y MAD 4
#      (209 días con datos en 4 años): un z diario sobre eso es ruido.
#   2. BASELINE ROBUSTA (mediana + MAD, no media + sd). Con series ralas la media
#      se arrastra por el propio evento y la sd colapsa; el MAD no se inmuta.
#   3. TRES SEÑALES, no una. El índice solo no alcanza: durante el paro SUBE
#      (de 51.9 a 67), porque las cuentas de federación reciben comentarios de
#      apoyo. Lo que delata el conflicto son las MENCIONES CRÍTICAS negativas.
#
# Jerarquía de las señales, y esto es honesto sobre lo que cada una puede:
#   * `terminos`   — disparador PRINCIPAL. Medido: mediana 0 en 125 semanas y >=2
#                    en solo 5 (4%), de las cuales dos caen dentro del paro y una
#                    es su antesala (20/04). Es el que de verdad discrimina.
#   * `indice`     — dispara solo si la caída es fuerte (|z| >= 2.5).
#   * `negatividad`— APOYO. El %NEG semanal es demasiado variable para disparar
#                    con poco: el 19.4% del 29/06 da z robusto 1.51 contra su
#                    propia baseline. Suma severidad; sola y débil no alarma.
# UNIDAD DE DETECCIÓN: la QUINCENA, no la semana.
#
# La detección corre sobre bloques de 2 semanas. Medido sobre los 8 episodios del
# calendario, con la misma memoria de medio año en las tres configuraciones:
#
#     unidad        detecta   lead    falsas/año   precisión
#     semanal        4 de 5   34 d       0,9          75 %
#     QUINCENAL      5 de 5   28 d       0,5          83 %
#     mensual        5 de 5   39 d       0,2          88 %
#
# La quincena toma el paro de Salud Mental (oct-2025), que la semana no veía por
# falta de volumen, y sube DOS episodios de ATENCIÓN a ALERTA: al juntar dos
# semanas el conteo de léxico suma y pasa el umbral. El mes sale mejor en el papel
# pero su latencia operativa es mala — un conflicto que arranca el día 2 no se ve
# hasta que cierra el mes.
#
# ⚠️ NO usar ventana DESLIZANTE (2 semanas móviles evaluadas cada semana), que
# parece la mejor de las dos ideas y no lo es: medido, baja a 3 de 5 con 79 % de
# precisión. Los bloques solapados comparten una semana, la serie queda
# autocorrelacionada, el MAD subestima la dispersión real y el z se infla; además
# el evento se reparte entre puntos vecinos y el pico se diluye. Es el mismo
# problema por el que la detección no corre sobre la serie con decaimiento.
#
# CONFIGURABLE por `PERCEPCION_UNIDAD_DETECCION_SEMANAS`. Con 1 el sistema sigue
# funcionando —los dos niveles existen igual— pero se paga en precisión, y el
# desglose POR NIVEL muestra dónde:
#
#     unidad   ATENCIÓN (la bajada)      ALERTA (hablan de paro)   conjunta
#       1      4 de 5 · 56 % precisión   2 de 5 · 100 %             4 de 5
#       2      3 de 5 · 67 % precisión   3 de 5 · 100 %             5 de 5
#
# Con la semana, casi la MITAD de las alarmas de ATENCIÓN son falsas —es el nivel
# que más se mira en el día a día— y ALERTA cubre un episodio menos. La quincena
# mejora los dos a la vez, porque juntar dos semanas apaga las alarmas de semanas
# flacas (las de n=29 y n=21 desaparecen solas) y suma el léxico entre semanas.
#
# ⚠️ Cambiar esto cambia lo que el tablero muestra, así que el panel DECLARA la
# unidad activa (`/percepcion/anomalias` devuelve `unidad_semanas`). Sin eso, dos
# personas con distinta configuración ven números distintos y ninguna sabe por qué.
UNIDAD_DETECCION_SEMANAS = get_settings().percepcion_unidad_deteccion_semanas

# Ancla de los bloques. Las quincenas se cuentan desde una fecha FIJA y no desde el
# inicio del rango consultado: si dependieran del filtro, cambiar "últimos 90 días"
# por "últimos 180" reagruparía las semanas de a pares distintos y las alarmas
# bailarían sin que cambie un solo dato. Es lunes, anterior a todo el corpus.
EPOCA_BLOQUES = date(2022, 1, 3)

# MEDIO AÑO de memoria. Era 8 semanas; se midió el barrido completo (2/4/6/8/12/16/
# 26/39) contra los 8 episodios del calendario. El %negativos detecta 4 de 5 con
# CUALQUIERA — la señal es robusta al parámetro—, pero acortar tiene dos costos que
# solo se ven mirando de cerca:
#
#   * ENMASCARAMIENTO. La escalada de abr-may 2026 subió tres semanas seguidas
#     (%neg 26 → 38 → 33). Con memoria de 4 semanas el baseline la SIGUE y solo ve
#     1 de las 3 (z +3,8 / +8,5 / +1,2); con 26 ve las 3 (z +2,2 / +3,2 / +2,4).
#     Ver un pico suelto no es lo mismo que ver una escalada.
#   * MUDEZ. Con memoria de 4 semanas el 35 % de las semanas con muestra no llega
#     a calcular z y no puede alarmar nunca; con 26, el 6 %. Una "precisión
#     perfecta" obtenida callando no es precisión.
#
# Y 26 semanas NO significa que el sistema tarde medio año en arrancar:
# `MIN_SEMANAS_BASELINE` son 3. La ventana es un TECHO de cuánto mira hacia atrás.
VENTANA_BASELINE_SEMANAS = 26
MIN_SEMANAS_BASELINE = 3
Z_UMBRAL_SEMANAL = 2.5        # z para que una señal de proporción dispare sola
Z_APORTE_SEVERIDAD = 1.5      # z desde el cual una señal ya suma severidad
MIN_TERMINOS_ALARMA = 2       # menciones críticas NEGATIVAS en la semana
# Bajo este volumen la semana no se evalúa POR PROPORCIÓN: 3 comentarios con 33%
# negativo es ruido, no señal (pasa de verdad — semana del 12/01/2026). El conteo
# de términos es absoluto y no pasa por este filtro.
#
# ERA `N_MIN_CONFIANZA` (30), por coherencia con la síntesis: sería raro que el
# tablero diga "muestra insuficiente" y la detección alarme con esa misma semana.
# El argumento valía cuando el ÍNDICE podía disparar la alarma. Ya no puede —los
# niveles se encienden con el %neg y con el conteo de léxico, no con el índice—,
# así que el umbral pasó a medirse por lo que de verdad hace: cuántos episodios
# quedan evaluables. Barrido sobre los 8 episodios del calendario:
#
#     MIN_N   evaluables   detecta   lead    falsas/año   precisión
#       15         5         3 de 5   32 d       0,7          80 %
#       20         5         4 de 5   34 d       0,9          75 %
#       25         4         4 de 4   32 d       0,5          83 %
#       30         3         2 de 3   32 d       0,5          82 %
#
# Con 30 solo TRES de los ocho episodios tienen ventana evaluable: el umbral
# apagaba la detección en la mayor parte del corpus.
#
# ⚠️ Se elige 20 y NO 25, que sale mejor en todas las columnas salvo cobertura.
# Un umbral que da "4 de 4" es exactamente el que hay que mirar con desconfianza:
# elegir el valor que maximiza el resultado sobre 8 casos es sobreajustar. 20 es
# el más exigente que conserva los 5 episodios evaluables, y el resultado se mueve
# entre 3 y 4 de 5 según dónde se ponga — el sistema anticipa "tres o cuatro de
# cinco", y no hay que prometer más que eso.
MIN_N_SEMANA = 20
# Pisos de escala: si el MAD da 0 (serie constante) el z sería infinito y marcaría
# todo. El piso los traduce a "cuánto tiene que moverse para que nos importe".
PISO_MAD_INDICE = 1.0         # puntos de índice
PISO_MAD_PCT_NEG = 2.0        # puntos porcentuales de negatividad
# Aportes a la severidad. Una señal fuerte alcanza sola; dos débiles concurrentes
# también. Una débil sola queda visible pero no alarma.
APORTE_FUERTE = 0.5
APORTE_DEBIL = 0.25
APORTE_PERSISTENCIA = 0.15
UMBRAL_SEVERIDAD_ANOMALIA = 0.5
# 1/0.6745: convierte el MAD en una escala comparable con la sd de una normal.
_MAD_A_SD = 1.4826

# --------------------------------------------------------------------------- #
# DOS NIVELES DE ALERTA — cubrir y acertar son objetivos distintos.
# --------------------------------------------------------------------------- #
# La severidad graduada dice CUÁNTO, no QUÉ HACER. Medido sobre los 8 episodios
# disruptivos del calendario (5 con muestra suficiente en su ventana previa de 6
# semanas; los de 2022-2023 caen en años de 66 y 151 comentarios y no se pueden
# evaluar), con baseline móvil de 26 semanas:
#
#   señal                    detecta   lead mediano   falsas/año   precisión
#   % negativos (z>=2,0)      4 de 5      34 días         1,1          71 %
#   léxico + negativo (>=2)   2 de 5      25 días         0,2          86 %
#   índice (caída)            0 de 5         —            0,7           0 %
#
# Ninguna sirve para las dos cosas, y unirlas por OR no mejora (misma cobertura que
# el %neg solo, una falsa alarma más). De ahí los dos niveles:
#
#   ATENCIÓN  cubre. Es para MIRAR: abrir la semana y leer de qué se habla. Una
#             falsa alarma cuesta diez minutos. Cubre 4 de 5 episodios.
#   ALERTA    acierta. Es para AVISAR: alguien está diciendo en voz alta que hay
#             paro, toma o asamblea, y en el corpus casi siempre lo hubo.
#
# ⚠️ EL ÍNDICE NO PARTICIPA de ninguno de los dos niveles, y esto es lo más
# contraintuitivo del módulo: es la métrica que el tablero muestra en grande y es
# la PEOR para anticipar. Durante un conflicto recibe apoyo y reclamo en las mismas
# publicaciones —las cuentas de federación concentran ambas cargas— y el promedio
# las cancela. Sigue sumando severidad (describe el clima, que es otra pregunta),
# pero no enciende un nivel por sí solo.
#
# ⚠️ Las falsas alarmas del nivel ATENCIÓN NO son ruido: las 5 del corpus tienen
# causa identificable (la inscripción de asignaturas de enero 2026, un comunicado
# de la FEUCN sobre denuncias). El nivel 1 no detecta paros: detecta SEMANAS EN QUE
# ALGO ANDA MAL. A veces es la antesala de un paro y a veces es un sistema de
# matrícula que no funciona — las dos cosas hay que verlas.
NIVEL_ALERTA = "alerta"
NIVEL_ATENCION = "atencion"

# El z del %neg que enciende ATENCIÓN. Es más bajo que `Z_UMBRAL_SEMANAL` (2,5) a
# propósito: con 2,5 se pierde un episodio y solo se evita una falsa alarma. 2,0 es
# el umbral MÁS EXIGENTE que conserva la cobertura máxima de 4 de 5.
Z_ATENCION_PCT_NEG = 2.0

# Lead MEDIDO de cada nivel, para poder decirlo en pantalla. "Esto suele avisar con
# un mes" es la información que decide si alguien actúa; una alarma sin horizonte
# no se puede accionar. Son medianas sobre los episodios detectados, no promesas.
#
# Los números salen de `_verificar_alerta_percepcion.py`, que corre ESTA función
# sobre los 4 años de historia real. Volver a correrlo cuando cambie el corpus o
# cualquier umbral de acá: si estas constantes quedan desfasadas, el tablero
# promete un horizonte que ya no es el suyo.
#
# ⚠️ El rango de ATENCIÓN empieza en 0 y no es un error. La suspensión por amenaza
# de tiroteo (07-04-2025) se detectó la MISMA semana, no antes: un shock externo y
# súbito no se gesta en los comentarios. El sistema anticipa el conflicto que se
# incuba —una paralización que se vota, una toma que se anuncia—, no lo que pasa
# de un día para el otro.
LEAD_ESPERADO_DIAS = {NIVEL_ATENCION: 20, NIVEL_ALERTA: 28}
LEAD_RANGO_DIAS = {NIVEL_ATENCION: (0, 39), NIVEL_ALERTA: (0, 49)}
# Cuántos de los episodios evaluables toma cada nivel. Va junto al lead: un nivel
# que avisa con 28 días pero toma 3 de 5 no se lee igual que uno que toma 5.
# Entre los dos toman los 5 evaluables — pero OJO con leer "5 de 5" como "cinco
# anticipados": tres avisan con 28, 39 y 49 días y DOS se encienden el mismo día
# del episodio (lead 0). Detectar no es anticipar, y el rango lo dice.
COBERTURA_MEDIDA = {NIVEL_ATENCION: (2, 5), NIVEL_ALERTA: (3, 5)}


def _decaimiento(fecha: date, fecha_ref: date, vida_media: float | None) -> float:
    """Peso temporal LINEAL: baja parejo cada día y a los `vida_media` días llega a 0
    (el comentario deja de contar). Proporcional al día, no por mitades. vida_media=0
    => sin decaimiento (peso 1)."""
    if not vida_media or vida_media <= 0:
        return 1.0
    dias = (fecha_ref - fecha).days
    if dias <= 0:
        return 1.0
    return max(0.0, 1.0 - dias / vida_media)


def _pick(peso_likes: float, ppos, pneg, speso, spos, sneg, n):
    """(num_pos, num_neg, den) INTERPOLADOS por la intensidad de ponderación α∈[0,1].

    α=0 → cada comentario pesa 1 (ignora likes): (Σprob_pos, Σprob_neg, n).
    α=1 → ponderación completa por likes:        (Σpeso·pos, Σpeso·neg, Σpeso).
    Valores intermedios interpolan linealmente entre ambos extremos, así el slider
    de "peso por likes" del dashboard es un control continuo, no un on/off.
    """
    a = max(0.0, min(1.0, float(peso_likes)))
    spos, sneg, n = float(spos or 0), float(sneg or 0), float(n or 0)
    ppos, pneg, speso = float(ppos or 0), float(pneg or 0), float(speso or 0)
    num_pos = (1.0 - a) * spos + a * ppos
    num_neg = (1.0 - a) * sneg + a * pneg
    den = (1.0 - a) * n + a * speso
    return num_pos, num_neg, den


def _indice_de_filas(filas, *, peso_likes: float, ponderar_tema: bool = True) -> float | None:
    """Índice a partir de filas POR TEMA: (tema, n, ppos, pneg, speso, spos, sneg, sgan, npos, nneu, nneg).

    El peso del tema se aplica a los DOS numeradores y NUNCA al denominador. Esa
    asimetría es lo que hace que el cambio no cueste cobertura: la muestra sigue
    siendo todos los comentarios, y lo único que cambia es cuánto dice cada uno sobre
    la institución. Ver `ponderacion` para los pesos y el caso que los justifica.

    Los pesos del crédito y del daño son DISTINTOS desde el esquema «DAI × peso de
    tema»: el crédito de un tema no atribuible se corta a la mitad y el daño no. Se
    puede resolver acá, sin migración, porque el grano de `percepcion_hecho_diario` ya
    incluye `tema` y dentro de una fila la atribuibilidad es única.

    Con `ponderar_tema=False` devuelve el índice canónico, para contrastar.
    """
    num_pos = num_neg = den = 0.0
    for tema, n, ppos, pneg, speso, spos, sneg, _sgan, _np, _nu, _ng in filas:
        p, g, d = _pick(peso_likes, ppos, pneg, speso, spos, sneg, n)
        w_cred = ponderacion.peso_credito(tema) if ponderar_tema else 1.0
        w_dano = ponderacion.peso_dano(tema) if ponderar_tema else 1.0
        num_pos += w_cred * p
        num_neg += w_dano * g
        den += d
    return _indice(num_pos, num_neg, den)


def _indice(num_pos: float, num_neg: float, den: float) -> float | None:
    if den <= 0:
        return None
    return max(0.0, min(100.0, 50.0 + 50.0 * (num_pos - num_neg) / den))


def _confianza(n: int, suma_ganadora: float) -> float:
    if n <= 0:
        return 0.0
    return min(1.0, n / N_MIN_CONFIANZA) * (suma_ganadora / n)


def _condiciones(campus, facultad, departamento, tema) -> list:
    cond = []
    if campus:
        cond.append(H.campus == campus)
    if facultad:
        cond.append(H.facultad == facultad)
    if departamento:
        cond.append(H.departamento == departamento)
    if tema:
        cond.append(H.tema == tema)
    return cond


def _fecha_maxima(db: Session) -> date | None:
    return db.execute(select(func.max(H.fecha))).scalar_one_or_none()


def _rango(
    db: Session, dias: int, fecha_desde: date | None = None, fecha_hasta: date | None = None
) -> tuple[date, date] | None:
    """Ventana efectiva (desde, hasta). Si viene fecha_desde/fecha_hasta (la REGLA),
    manda ese intervalo e ignora la ventana `dias`; si no, últimos `dias` desde fmax.

    Caso especial: seleccionar UN día (fecha_desde == fecha_hasta) se interpreta como
    ANCLA → 'ese día y hacia atrás' (trailing `dias`), NO un único día. La lista de
    comentarios no usa esta función (filtra por fecha directa), así que sigue mostrando
    solo ese día; el ÍNDICE, en cambio, mira hacia atrás como pidió la DAI."""
    fmax = _fecha_maxima(db)
    if fmax is None:
        return None
    if fecha_desde and fecha_hasta and fecha_desde == fecha_hasta:
        return (fecha_hasta - timedelta(days=dias), fecha_hasta)
    hasta = fecha_hasta or fmax
    desde = fecha_desde or (hasta - timedelta(days=dias))
    return (desde, hasta)


_COLS = (
    func.sum(H.n_comentarios), func.sum(H.peso_pos), func.sum(H.peso_neg),
    func.sum(H.suma_peso), func.sum(H.suma_pos), func.sum(H.suma_neg),
    func.sum(H.suma_ganadora),
    func.sum(H.n_pos), func.sum(H.n_neu), func.sum(H.n_neg),
)


def _dias_crudos(db, desde, hasta, campus, facultad, departamento, tema, peso_likes,
                 ponderar_tema: bool = True) -> list[dict]:
    """Filas diarias CRUDAS (sin decaimiento) en [desde, hasta], con el control de peso
    por likes ya aplicado (num_pos, num_neg, den). Base común de todos los cálculos."""
    # Se agrupa por (fecha, TEMA) y no solo por fecha: el peso del tema tiene que
    # aplicarse ANTES de sumar. Es exacto y no necesita migración porque el grano de
    # `percepcion_hecho_diario` ya incluye `tema`, así que dentro de una fila el peso
    # es único.
    stmt = (
        select(H.fecha, H.tema, *_COLS)
        .where(H.fecha >= desde, H.fecha <= hasta, *_condiciones(campus, facultad, departamento, tema))
        .group_by(H.fecha, H.tema).order_by(H.fecha)
    )
    por_dia: dict = {}
    for fecha, tema_fila, n, ppos, pneg, speso, spos, sneg, sgan, npos, nneu, nneg in db.execute(stmt):
        n = int(n or 0)
        num_pos, num_neg, den = _pick(peso_likes, ppos, pneg, speso, spos, sneg, n)
        # Crédito y daño llevan pesos DISTINTOS: el crédito de un tema no atribuible se
        # corta a la mitad, el daño no. Ver `ponderacion.peso_credito`.
        w_cred = ponderacion.peso_credito(tema_fila) if ponderar_tema else 1.0
        w_dano = ponderacion.peso_dano(tema_fila) if ponderar_tema else 1.0
        acc = por_dia.get(fecha)
        if acc is None:
            acc = por_dia[fecha] = {
                "fecha": fecha, "n": 0, "num_pos": 0.0, "num_neg": 0.0,
                "den": 0.0, "sgan": 0.0, "n_pos": 0, "n_neu": 0, "n_neg": 0,
            }
        acc["n"] += n
        acc["num_pos"] += w_cred * num_pos   # el peso va a los numeradores...
        acc["num_neg"] += w_dano * num_neg
        acc["den"] += den                    # ...y NUNCA al denominador
        acc["sgan"] += float(sgan or 0)
        acc["n_pos"] += int(npos or 0)
        acc["n_neu"] += int(nneu or 0)
        acc["n_neg"] += int(nneg or 0)
    return [por_dia[k] for k in sorted(por_dia)]


def _trailing_sums(crudos: list[dict], fecha_ref: date, vida_media: float | None):
    """Sumas decaídas (lineal) sobre la ventana [fecha_ref − vida_media, fecha_ref].

    Devuelve (num_pos, num_neg, den, n_ventana, sgan_ventana). Con vida_media=0 la
    ventana se reduce al propio día `fecha_ref` (sin trailing). Los CONTEOS (n, sgan)
    NO se decaen: la confianza refleja el volumen REAL acumulado en la ventana → por eso
    'ese día y hacia atrás' usa más comentarios y sube la confianza."""
    vm = int(vida_media or 0)
    limite_inf = fecha_ref - timedelta(days=vm) if vm > 0 else fecha_ref
    num_pos = num_neg = den = sgan = 0.0
    n = 0
    for c in crudos:
        f = c["fecha"]
        if f < limite_inf or f > fecha_ref:
            continue
        w = _decaimiento(f, fecha_ref, vida_media)
        if w <= 0:
            continue
        num_pos += w * c["num_pos"]
        num_neg += w * c["num_neg"]
        den += w * c["den"]
        n += c["n"]
        sgan += c["sgan"]
    return num_pos, num_neg, den, n, sgan


def _serie_trailing(db, dias, campus, facultad, departamento, tema, peso_likes, vida_media,
                    fecha_desde=None, fecha_hasta=None) -> list[dict]:
    """Serie donde CADA punto = índice 'ese día y hacia atrás' (trailing decaído sobre
    sus `vida_media` días previos, incluido ese día). Lee un buffer de calentamiento de
    `vida_media` días antes del borde izquierdo para que el primer punto visible también
    tenga su ventana completa. Marca anomalías sobre esta misma serie suavizada (un
    chispazo de 1 comentario ya no es anomalía; sí lo es un giro sostenido)."""
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return []
    desde, hasta = r
    vm = int(vida_media or 0)
    warmup = desde - timedelta(days=vm) if vm > 0 else desde
    crudos = _dias_crudos(db, warmup, hasta, campus, facultad, departamento, tema, peso_likes)
    if not crudos:
        return []
    serie = []
    for c in crudos:
        d = c["fecha"]
        if d < desde:   # solo calentamiento: alimenta el trailing, no se dibuja
            continue
        num_pos, num_neg, den, n_v, sgan_v = _trailing_sums(crudos, d, vida_media)
        serie.append({
            "fecha": d, "n": c["n"], "n_ventana": n_v,
            "indice": _indice(num_pos, num_neg, den),
            "confianza": _confianza(n_v, sgan_v),
            # La marca la pone la detección SEMANAL (ver `_deteccion_semanal`),
            # que no corre sobre esta serie. Acá quedan inicializadas para que el
            # contrato del punto sea siempre el mismo.
            "es_anomalia": False, "z_score": None, "severidad": 0.0, "motivos": [],
        })
    return serie


def _z_robusto(valor: float | None, previos: list[float], *, piso: float) -> float | None:
    """z contra la MEDIANA de `previos`, escalado por su MAD (no por la sd).

    La media y la desviación estándar se dejan arrastrar por el propio evento: un
    solo pico previo infla la sd y el evento siguiente deja de destacar. La
    mediana y el MAD lo ignoran. `piso` evita dividir por cero cuando la serie
    previa es constante (MAD = 0) y define, de hecho, cuánto tiene que moverse el
    valor para que nos importe.
    """
    if valor is None or len(previos) < MIN_SEMANAS_BASELINE:
        return None
    m = median(previos)
    mad = median([abs(x - m) for x in previos])
    escala = max(_MAD_A_SD * mad, piso)
    if escala <= 0:
        return None
    return (valor - m) / escala


def _detectar_anomalias_semanales(serie: list[dict]) -> None:
    """Marca in-place `z_indice`, `z_pct_neg`, `motivos`, `severidad`, `es_anomalia`.

    Función PURA sobre la serie semanal (no toca la BD): así la política de
    detección se prueba sola, sin sembrar hechos ni comentarios.

    La severidad es aditiva y explicable: cada señal aporta según su fuerza, la
    persistencia agrava, y el total se corta en 1. Se eligió una severidad
    graduada en vez de un booleano porque una mención crítica aislada no es un
    paro pero tampoco es nada — tiene que verse en el tablero sin gritar.

    ⚠️ La persistencia AGRAVA pero no es requisito. El 20/04/2026 fue UNA semana
    suelta (3 menciones críticas negativas) y resultó ser la antesala del paro del
    03/06. Exigir semanas consecutivas habría descartado justo la señal temprana.

    RESULTADO SOBRE LOS 4 AÑOS REALES (`_verificar_alerta_percepcion.py`)
    --------------------------------------------------------------------
    De los 8 episodios disruptivos del calendario, 5 tienen ventana evaluable y los
    **5** encienden un nivel, con 0,5 falsas alarmas por año (precisión 83 %).

    ⚠️ "5 de 5" NO es "cinco anticipados", y la diferencia importa:

        Toma pabellón de Geología      alerta     49 días antes
        Paro Derecho Coquimbo          atención   39 días antes
        Paralización abril-mayo 2026   alerta     28 días antes
        Paro Salud Mental              alerta      0 días  (se enciende, no anticipa)
        Suspensión por amenaza         atención    0 días  (íd.)

    TRES anticipan de verdad; DOS se encienden el mismo día. El de la amenaza de
    tiroteo no podía ser de otra forma —un shock externo y súbito no se gesta en
    los comentarios—; el de Salud Mental simplemente no se anunció.

    Y las falsas alarmas del nivel ATENCIÓN no son ruido: las dos tienen causa —la
    inscripción de asignaturas de enero 2026 y un comunicado de la FEUCN sobre
    denuncias—. El nivel 1 no detecta paros: detecta semanas en que algo anda mal,
    que a veces es la antesala de un paro y a veces es un sistema de matrícula que
    no funciona. Las dos cosas hay que verlas.
    """
    # La memoria está declarada en SEMANAS pero la serie viene en unidades de
    # detección (quincenas). Sin esta conversión, "26" pasaría a significar un año
    # en silencio el día que se toca `UNIDAD_DETECCION_SEMANAS`.
    memoria = max(MIN_SEMANAS_BASELINE,
                  VENTANA_BASELINE_SEMANAS // max(1, UNIDAD_DETECCION_SEMANAS))
    for i, p in enumerate(serie):
        previos = serie[max(0, i - memoria):i]
        # La baseline se arma SOLO con semanas de volumen suficiente: las flacas
        # tienen proporciones erráticas y ensucian la referencia.
        solidas = [q for q in previos if (q.get("n") or 0) >= MIN_N_SEMANA]
        evaluable = (p.get("n") or 0) >= MIN_N_SEMANA

        z_idx = z_neg = None
        if evaluable:
            z_idx = _z_robusto(
                p.get("indice"),
                [q["indice"] for q in solidas if q.get("indice") is not None],
                piso=PISO_MAD_INDICE,
            )
            z_neg = _z_robusto(
                p.get("pct_neg"),
                [q["pct_neg"] for q in solidas if q.get("pct_neg") is not None],
                piso=PISO_MAD_PCT_NEG,
            )

        motivos: list[str] = []
        severidad = 0.0

        # 1) TÉRMINOS — conteo absoluto, sin gate de volumen: dos menciones de
        #    paro en una semana chica importan igual (o más).
        n_term_neg = int(p.get("n_terminos_neg") or 0)
        if n_term_neg >= MIN_TERMINOS_ALARMA:
            motivos.append("terminos")
            severidad += APORTE_FUERTE
        elif n_term_neg >= 1:
            motivos.append("terminos")
            severidad += APORTE_DEBIL

        # 2) ÍNDICE — ASIMÉTRICO. Solo la CAÍDA dispara sola: que la percepción
        #    mejore de golpe es un cambio, no una alarma, y este es un tablero de
        #    alerta temprana. La subida se registra igual (queda el motivo y el
        #    signo en `z_indice`) pero aporta poco.
        #    Calibrado: tratando ambos sentidos por igual, las semanas del
        #    06/04 (z +3.39), 25/05 (z +3.78) y 24/11 (z +4.05) se marcaban como
        #    alarma. Ninguna es un problema: en las tres la percepción mejoró.
        if z_idx is not None and z_idx <= -Z_UMBRAL_SEMANAL:
            motivos.append("indice")
            severidad += APORTE_FUERTE
        elif z_idx is not None and abs(z_idx) >= Z_APORTE_SEVERIDAD:
            motivos.append("indice")
            severidad += APORTE_DEBIL

        # 3) NEGATIVIDAD — solo al alza: que BAJE la negatividad no es una alarma.
        if z_neg is not None and z_neg >= Z_UMBRAL_SEMANAL:
            motivos.append("negatividad")
            severidad += APORTE_FUERTE
        elif z_neg is not None and z_neg >= Z_APORTE_SEVERIDAD:
            motivos.append("negatividad")
            severidad += APORTE_DEBIL

        if motivos and i > 0 and serie[i - 1].get("motivos"):
            severidad += APORTE_PERSISTENCIA

        # ------------------------------------------------------------------ #
        # NIVEL. Se decide con las DOS señales que se midieron útiles, cada una
        # con su umbral propio, y NO con la severidad combinada: la severidad
        # dice cuánto, el nivel dice qué hacer. Ver el bloque de constantes.
        # ------------------------------------------------------------------ #
        nivel = None
        if n_term_neg >= MIN_TERMINOS_ALARMA:
            # Alguien está diciendo en voz alta que hay paro/toma/asamblea.
            nivel = NIVEL_ALERTA
        elif z_neg is not None and z_neg >= Z_ATENCION_PCT_NEG:
            nivel = NIVEL_ATENCION

        p["z_indice"] = z_idx
        p["z_pct_neg"] = z_neg
        p["z_score"] = z_idx          # compatibilidad con el contrato anterior
        p["motivos"] = motivos
        p["severidad"] = round(min(1.0, severidad), 3)
        p["es_anomalia"] = p["severidad"] >= UMBRAL_SEVERIDAD_ANOMALIA
        # `nivel_alerta` y no `nivel`: en el item de `anomalias()` la clave `nivel`
        # ya significa otra cosa (el alcance de la dimensión: global o filtrado).
        p["nivel_alerta"] = nivel
        # El horizonte viaja con la alarma: sin él, "hay una alerta" no se puede
        # accionar. Son los valores MEDIDOS sobre el histórico, no una predicción
        # para esta semana en particular.
        p["lead_esperado_dias"] = LEAD_ESPERADO_DIAS.get(nivel)
        p["lead_rango_dias"] = list(LEAD_RANGO_DIAS[nivel]) if nivel else None
        p["cobertura_medida"] = list(COBERTURA_MEDIDA[nivel]) if nivel else None


def _serie_semanal(db, desde, hasta, campus, facultad, departamento, tema, peso_likes) -> list[dict]:
    """Serie SEMANAL desde los hechos: índice, volumen y % negativo por lunes.

    Sin decaimiento a propósito: la semana ya es la unidad de suavizado. Decaer
    encima volvería a aplanar justo lo que se quiere detectar.
    """
    acc: dict = {}
    for c in _dias_crudos(db, desde, hasta, campus, facultad, departamento, tema, peso_likes):
        a = acc.setdefault(_lunes(c["fecha"]), {
            "n": 0, "num_pos": 0.0, "num_neg": 0.0, "den": 0.0, "sgan": 0.0, "n_neg": 0,
        })
        a["n"] += c["n"]
        a["num_pos"] += c["num_pos"]
        a["num_neg"] += c["num_neg"]
        a["den"] += c["den"]
        a["sgan"] += c["sgan"]
        a["n_neg"] += c["n_neg"]
    return [
        {
            "semana": s, "n": a["n"], "n_neg": a["n_neg"],
            "pct_neg": round(100.0 * a["n_neg"] / a["n"], 2) if a["n"] else None,
            "indice": _indice(a["num_pos"], a["num_neg"], a["den"]),
            "confianza": _confianza(a["n"], a["sgan"]),
        }
        for s, a in sorted(acc.items())
    ]


def _terminos_por_semana(db, desde, hasta, *, campus, facultad, departamento, tema) -> dict:
    """{lunes: {"n": serias, "n_neg": serias negativas}} desde el CORPUS de textos.

    El humor queda fuera: un "jajaja paro" no es una alarma. Se reporta aparte en
    `terminos_vigilancia`, pero no dispara.

    Tolera que las tablas del corpus no existan: hay bases (y tests) que solo
    tienen la tabla de HECHOS. En ese caso no hay señal de términos y las otras
    dos siguen funcionando, en vez de tumbar toda la detección.
    """
    try:
        fmax = _fmax_comentario(db)
        if fmax is None:
            return {}
        filas = db.execute(
            _select_corpus(C.fecha_comentario, C.texto, S.sentimiento, S.emocion)
            .where(*_cond_corpus(
                fmax, dias=0, campus=campus, facultad=facultad,
                departamento=departamento, tema=tema,
                fecha_desde=desde, fecha_hasta=hasta,
            ))
        )
        acc: dict = {}
        for fecha_dt, texto, sent, emo in filas:
            if emo == EMOCION_HUMOR or not lexico.detectar(texto):
                continue
            a = acc.setdefault(_lunes(_a_fecha(fecha_dt)), {"n": 0, "n_neg": 0})
            a["n"] += 1
            if sent == "NEG":
                a["n_neg"] += 1
        return acc
    except Exception:
        return {}


def _bloque_de(lunes_semana: date) -> date:
    """Lunes de la QUINCENA a la que pertenece esa semana, anclado a `EPOCA_BLOQUES`.

    Anclar a una época fija —y no al primer lunes del rango consultado— es lo que
    hace que la quincena de una fecha sea SIEMPRE la misma. Ver `EPOCA_BLOQUES`.
    """
    semanas = (lunes_semana - EPOCA_BLOQUES).days // 7
    bloque = semanas // UNIDAD_DETECCION_SEMANAS
    return EPOCA_BLOQUES + timedelta(weeks=bloque * UNIDAD_DETECCION_SEMANAS)


def _agrupar_en_bloques(serie: list[dict]) -> list[dict]:
    """Junta la serie semanal en unidades de detección (quincenas por defecto).

    El índice y el %neg se PONDERAN POR VOLUMEN. Promediarlos sin ponderar le daría
    el mismo peso a una semana de 5 comentarios que a una de 200 — y en un corpus
    donde el volumen semanal va de 0 a 385, eso no es un detalle.

    Los conteos de léxico se SUMAN, que es justo lo que hace ganar a la quincena:
    dos semanas con una mención negativa cada una llegan juntas al umbral de dos y
    encienden ALERTA, el nivel preciso.
    """
    if UNIDAD_DETECCION_SEMANAS <= 1:
        return serie
    acc: dict[date, list[dict]] = {}
    for p in serie:
        acc.setdefault(_bloque_de(p["semana"]), []).append(p)

    salida = []
    for inicio, bloque in sorted(acc.items()):
        n = sum(p.get("n") or 0 for p in bloque)
        def _pond(campo):
            partes = [(p[campo], p["n"]) for p in bloque
                      if p.get(campo) is not None and p.get("n")]
            return (sum(v * w for v, w in partes) / sum(w for _, w in partes)
                    if partes else None)
        salida.append({
            "semana": inicio,
            # Fin del bloque, para que la UI pueda decir "del X al Y" en vez de
            # mostrar un lunes suelto que en realidad representa dos semanas.
            "semana_fin": inicio + timedelta(weeks=UNIDAD_DETECCION_SEMANAS, days=-1),
            "n": n,
            "n_neg": sum(p.get("n_neg") or 0 for p in bloque),
            "indice": _pond("indice"),
            "pct_neg": _pond("pct_neg"),
            "confianza": max((p.get("confianza") or 0.0) for p in bloque),
            "n_terminos": sum(p.get("n_terminos") or 0 for p in bloque),
            "n_terminos_neg": sum(p.get("n_terminos_neg") or 0 for p in bloque),
            "semanas": [p["semana"] for p in bloque],
        })
    return salida


def _deteccion_semanal(db, dias, campus, facultad, departamento, tema, peso_likes,
                       fecha_desde=None, fecha_hasta=None) -> list[dict]:
    """Serie de detección con las tres señales cruzadas y las anomalías marcadas.

    La unidad es la QUINCENA (`UNIDAD_DETECCION_SEMANAS`), no la semana: medido
    sobre los 8 episodios del calendario, detecta 5 de 5 contra 4 de 5, con la
    mitad de falsas alarmas. El nombre de la función se conserva porque es el que
    usa medio módulo; lo que cambió es el tamaño del bloque, no el contrato.
    """
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return []
    desde, hasta = r
    serie = _serie_semanal(db, desde, hasta, campus, facultad, departamento, tema, peso_likes)
    if not serie:
        return []
    terminos = _terminos_por_semana(
        db, desde, hasta, campus=campus, facultad=facultad,
        departamento=departamento, tema=tema,
    )
    for p in serie:
        t = terminos.get(p["semana"], {})
        p["n_terminos"] = t.get("n", 0)
        p["n_terminos_neg"] = t.get("n_neg", 0)
    # Los términos se cruzan ANTES de agrupar: vienen indexados por semana, y
    # agrupar primero obligaría a repartirlos a mano por bloque.
    serie = _agrupar_en_bloques(serie)
    _detectar_anomalias_semanales(serie)
    return serie


# Mínimo de comentarios para que una unidad entre al cálculo del Gini. Sin esto, una
# unidad con 4 comentarios de los cuales 2 son de un tema aporta un 50 % de
# prevalencia que es puro ruido y desplaza el índice entero.
N_MIN_EVIDENCIA = 30


# Cortes del Gini traducidos a palabras. Son convención, no ley: se eligieron para
# que las tres bandas describan ACCIONES distintas —hablar con una unidad, mirar
# cuáles, tratarlo como institucional— y no para partir el rango en tercios.
UMBRAL_CONCENTRADO = 0.60
UMBRAL_DESPAREJO = 0.42


def _reparto(gini: float) -> str:
    if gini >= UMBRAL_CONCENTRADO:
        return "Concentrado en una unidad"
    if gini >= UMBRAL_DESPAREJO:
        return "Desparejo entre unidades"
    return "Transversal a la universidad"


def _gini(valores: list[float]) -> float | None:
    """Desigualdad de una distribución. 0 = todos iguales, 1 = todo en uno solo."""
    v = sorted(valores)
    n, s = len(v), sum(v)
    if n == 0 or s == 0:
        return None
    return (2 * sum((i + 1) * x for i, x in enumerate(v)) / (n * s)) - (n + 1) / n


def concentracion_temas(
    db, *, nivel="facultad", dias=30, campus=None, facultad=None, departamento=None,
    tema=None, fecha_desde=None, fecha_hasta=None,
) -> dict:
    """¿Cada tema está concentrado en una unidad o es transversal a la universidad?

    Para un director es la diferencia entre «es mío» y «es de todos», y el tablero no
    podía contestarlo: mostraba el volumen por unidad, que confunde «este tema pesa
    acá» con «esta unidad comenta mucho de todo».

    Se mide con el Gini de la PREVALENCIA (comentarios del tema ÷ comentarios de la
    unidad), no del volumen. Esa división es la que separa las dos cosas: una unidad
    con mucho volumen no infla su prevalencia.

    ⚠️ COBERTURA PARCIAL, Y VA A LA RESPUESTA. Solo el 35 % de los comentarios tiene
    facultad y el 27 % departamento: las cuentas de más volumen son agrupaciones
    (rescate animal, centros de estudiantes), no unidades académicas. El resultado
    describe la conversación DE LAS UNIDADES, no la del corpus. Se devuelve
    `cobertura_pct` y `unidades` para que se pueda decir en pantalla en vez de
    presentar un número que parece del total.
    """
    col = {"facultad": H.facultad, "departamento": H.departamento,
           "campus": H.campus}.get(nivel)
    if col is None:
        raise ValueError(f"nivel inválido: {nivel}")
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return {"hay_datos": False}
    desde, hasta = r
    cond = [H.fecha >= desde, H.fecha <= hasta,
            *_condiciones(campus, facultad, departamento, tema)]

    total_ventana = db.execute(
        select(func.sum(H.n_comentarios)).where(*cond)
    ).scalar() or 0
    filas = list(db.execute(
        select(col, H.tema, func.sum(H.n_comentarios))
        .where(*cond, col.is_not(None), col != "")
        .group_by(col, H.tema)
    ))
    if not filas:
        return {"hay_datos": False}

    por_unidad: dict[str, int] = {}
    por_tema: dict[str, dict[str, int]] = {}
    for unidad, t, n in filas:
        n = int(n or 0)
        por_unidad[unidad] = por_unidad.get(unidad, 0) + n
        por_tema.setdefault(t or "otros", {})[unidad] = n

    elegibles = [u for u, n in por_unidad.items() if n >= N_MIN_EVIDENCIA]
    if len(elegibles) < 3:
        # Con menos de tres unidades el Gini no significa nada: es un cociente.
        return {"hay_datos": False, "motivo":
                f"Se necesitan al menos 3 unidades con {N_MIN_EVIDENCIA}+ comentarios; "
                f"hay {len(elegibles)}."}

    items = []
    for t, d in por_tema.items():
        n = sum(d.get(u, 0) for u in elegibles)
        if n < N_MIN_EVIDENCIA:
            continue
        prev = [d.get(u, 0) / por_unidad[u] for u in elegibles]
        g = _gini(prev)
        if g is None:
            continue
        top = max(elegibles, key=lambda u: d.get(u, 0) / por_unidad[u])
        prev_top = d.get(top, 0) / por_unidad[top] * 100
        prev_media = sum(prev) / len(prev) * 100
        items.append({
            "tema": t, "etiqueta": ETIQUETAS_TEMA.get(t, t), "n": n,
            # El Gini viaja para quien quiera auditarlo, pero NO se muestra: a un
            # administrativo «0,70» no le dice nada. La lectura va en `reparto` y en
            # la comparación prevalencia_top vs prevalencia_media, que sí se leen.
            "gini": round(g, 3),
            "reparto": _reparto(g),
            "concentrado": g >= UMBRAL_CONCENTRADO,
            "unidad_top": top,
            "prevalencia_top": round(prev_top, 1),
            "prevalencia_media": round(prev_media, 1),
            # Cuántas veces más presente está en la unidad que más lo trata que en
            # una unidad promedio. Es la frase que un director entiende sin glosario.
            "veces_sobre_promedio": round(prev_top / prev_media, 1) if prev_media else None,
            "unidades_con_presencia": sum(1 for x in prev if x > 0),
        })
    if not items:
        return {"hay_datos": False}

    cubiertos = sum(por_unidad[u] for u in elegibles)
    return {
        "hay_datos": True,
        "nivel": nivel,
        "items": sorted(items, key=lambda x: -x["gini"]),
        "unidades": len(elegibles),
        "n_comentarios": cubiertos,
        "cobertura_pct": round(cubiertos / total_ventana * 100, 1) if total_ventana else 0.0,
        "minimo_por_unidad": N_MIN_EVIDENCIA,
        "fecha_desde": desde,
        "fecha_hasta": hasta,
    }


def postura_institucional(
    db, *, dias=30, campus=None, facultad=None, departamento=None, tema=None,
    fecha_desde=None, fecha_hasta=None,
) -> dict:
    """Reparto favorable / sin postura / adverso sobre la ventana pedida.

    NO ES EL SENTIMIENTO. El sentimiento es el TONO; la postura es el efecto para la
    institución. Se muestran juntos a propósito: la diferencia entre los dos es
    justamente lo que el tablero no podía decir antes.

    Sale de `percepcion_hecho_diario` SIN columnas nuevas ni migración: el grano de
    los hechos ya incluye `tema`, así que dentro de cada fila el tono determina la
    postura sin ambigüedad (ver `postura.contar_por_postura`). Consecuencia práctica:
    si cambia la regla, el histórico entero se recalcula solo — no hay nada guardado
    que quede viejo.

    ⚠️ SIN DECAIMIENTO, a diferencia del índice. Acá se cuentan comentarios, no se
    mide temperatura: «cuántos adversos hubo este mes» es una pregunta de conteo y
    ponderar por recencia daría un número que nadie puede verificar contando.
    """
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return {"hay_datos": False}
    desde, hasta = r
    total = dict.fromkeys(ORDEN_POSTURA, 0)
    por_tema: dict[str, dict] = {}
    # Del CORPUS y no de los hechos: la postura mira el tipo de cuenta y el grano de
    # hechos no lo guarda. Ver `_conteos_postura`.
    for t, ctipo, npos, nneu, nneg in _conteos_postura(
            db, desde, hasta, campus, facultad, departamento, tema):
        cuenta = contar_por_postura(t, npos, nneu, nneg, cuenta_tipo=ctipo)
        n = sum(cuenta.values())
        if n == 0:
            continue
        for k, v in cuenta.items():
            total[k] += v
        # Un mismo tema llega ahora en varias filas (una por tipo de cuenta), así
        # que se ACUMULA en vez de asignarse: con `=` se perdían todas menos la última.
        acc = por_tema.setdefault(t or "otros", {"n": 0, **dict.fromkeys(ORDEN_POSTURA, 0)})
        acc["n"] += n
        for k, v in cuenta.items():
            acc[k] += v
    n_total = sum(total.values())
    if n_total == 0:
        return {"hay_datos": False}

    return {
        "hay_datos": True,
        "n_comentarios": n_total,
        "distribucion": [
            {"postura": p, "etiqueta": ETIQUETAS_POSTURA[p], "n": total[p],
             "pct": round(total[p] / n_total * 100, 1)}
            for p in ORDEN_POSTURA
        ],
        # De dónde sale lo adverso. Es la pregunta que sigue siempre al titular, y sin
        # esto habría que abrir la lista de comentarios para contestarla.
        "temas_adversos": [
            {"tema": t, "etiqueta": ETIQUETAS_TEMA.get(t, t), "n": d[POSTURA_ADVERSO],
             "pct": round(d[POSTURA_ADVERSO] / d["n"] * 100, 1)}
            for t, d in sorted(por_tema.items(), key=lambda x: -x[1][POSTURA_ADVERSO])
            if d[POSTURA_ADVERSO] > 0
        ][:6],
        "fecha_desde": desde,
        "fecha_hasta": hasta,
    }


def resumen(db, *, dias=30, campus=None, facultad=None, departamento=None, tema=None,
            peso_likes=1.0, vida_media=VIDA_MEDIA_DIAS, fecha_desde=None, fecha_hasta=None,
            ponderar_tema: bool = True) -> dict:
    """`ponderar_tema=False` devuelve el índice CANÓNICO, sin pesos por tema.

    Se deja conmutable a propósito: el ponderado es el que manda en el tablero, pero
    el canónico sigue siendo el número con el que se leyó la serie histórica y sirve
    de contraste. Ver `ponderacion` para los pesos y el caso que los justifica.
    """
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return {"hay_datos": False}
    desde, hasta = r
    crudos = _dias_crudos(db, desde, hasta, campus, facultad, departamento, tema, peso_likes,
                          ponderar_tema)
    if not crudos:
        return {"hay_datos": False}
    n_total = sum(c["n"] for c in crudos)
    if n_total == 0:
        return {"hay_datos": False}

    # Índice ACTUAL = decaído (recencia): 'a esa fecha y hacia atrás'. Lo nuevo pesa más
    # y a los `vida_media` días un comentario deja de contar (decaimiento LINEAL). Anclado
    # al día más reciente con datos: un comentario suelto ya no puede dispararlo solo.
    ref = crudos[-1]["fecha"]
    num_pos = sum(_decaimiento(c["fecha"], ref, vida_media) * c["num_pos"] for c in crudos)
    num_neg = sum(_decaimiento(c["fecha"], ref, vida_media) * c["num_neg"] for c in crudos)
    den = sum(_decaimiento(c["fecha"], ref, vida_media) * c["den"] for c in crudos)

    # Índice PROMEDIO = llano sobre la ventana (sin ponderar recencia), como contraste.
    indice_promedio = _indice(
        sum(c["num_pos"] for c in crudos),
        sum(c["num_neg"] for c in crudos),
        sum(c["den"] for c in crudos),
    )

    dias_idx = [x for x in (_indice(c["num_pos"], c["num_neg"], c["den"]) for c in crudos) if x is not None]
    tendencia = None
    if len(dias_idx) >= 4:
        ult, prev = dias_idx[-7:], (dias_idx[-14:-7] or dias_idx[:-7])
        if ult and prev:
            tendencia = (sum(ult) / len(ult)) - (sum(prev) / len(prev))

    return {
        "hay_datos": True,
        "indice_actual": _indice(num_pos, num_neg, den),
        "indice_promedio": indice_promedio,
        "tendencia": tendencia,
        "n_comentarios": n_total,
        "confianza_promedio": _confianza(n_total, sum(c["sgan"] for c in crudos)),
        "distribucion": {
            "positivo": sum(c["n_pos"] for c in crudos),
            "neutral": sum(c["n_neu"] for c in crudos),
            "negativo": sum(c["n_neg"] for c in crudos),
        },
        "fecha_desde": crudos[0]["fecha"],
        "fecha_hasta": crudos[-1]["fecha"],
    }


def evolucion(db, *, dias=90, campus=None, facultad=None, departamento=None, tema=None,
              peso_likes=1.0, vida_media=VIDA_MEDIA_DIAS, fecha_desde=None, fecha_hasta=None) -> dict:
    # La evolución es la LÍNEA DE TIEMPO completa; fecha_desde/fecha_hasta (la selección)
    # NO la recortan. Cada punto = índice 'ese día y hacia atrás' (trailing decaído), no
    # el día aislado: un comentario suelto se diluye en su ventana en vez de dibujar un pico.
    serie = _serie_trailing(db, dias, campus, facultad, departamento, tema, peso_likes, vida_media)
    # La marca de anomalía viene de la detección SEMANAL, que corre sobre otra
    # serie (ver `_deteccion_semanal`): se dibuja suave y se detecta crudo. Cada
    # día hereda el veredicto de SU semana, así el tramo anómalo se ve como tramo
    # y no como un punto suelto que nadie sabe interpretar.
    semanas = {p["semana"]: p for p in _deteccion_semanal(
        db, dias, campus, facultad, departamento, tema, peso_likes)}
    return {
        "nivel": "filtrado",
        "dimension": facultad or departamento or campus,
        "puntos": [
            {
                "fecha": p["fecha"], "indice": p["indice"], "confianza": p["confianza"],
                "n_comentarios": p["n_ventana"],
                "es_anomalia": bool(semanas.get(_lunes(p["fecha"]), {}).get("es_anomalia")),
                "severidad": semanas.get(_lunes(p["fecha"]), {}).get("severidad", 0.0),
                "motivos": semanas.get(_lunes(p["fecha"]), {}).get("motivos", []),
            }
            for p in serie
        ],
    }


def _tramos_postura(cuenta: dict[str, int] | None) -> list[dict] | None:
    """Formatea el reparto de una unidad. None cuando no hay ningún comentario:
    devolver ceros haría dibujar una barra vacía que parece un dato."""
    if not cuenta:
        return None
    n = sum(cuenta.values())
    if n == 0:
        return None
    return [
        {"postura": p, "etiqueta": ETIQUETAS_POSTURA[p], "n": cuenta[p],
         "pct": round(cuenta[p] / n * 100, 1)}
        for p in ORDEN_POSTURA
    ]


def _postura_por_dim(db, desde, hasta, dim_nivel, campus, facultad, departamento,
                     tema) -> dict[str, dict[str, int]]:
    """Reparto de postura por unidad. Agrupa por (unidad, TEMA) y recién ahí decide.

    ⚠️ NO se puede sacar de `_agrupado`, que agrupa sólo por unidad y pierde el
    tema: la postura de un positivo depende de si el tema es atribuible, así que
    sin el tema el reparto sería una adivinanza. Es una consulta aparte a propósito.
    """
    out: dict[str, dict[str, int]] = {}
    # Del CORPUS: hace falta el tipo de cuenta, que la tabla de hechos no tiene.
    for dim, t, ctipo, npos, nneu, nneg in _conteos_postura(
            db, desde, hasta, campus, facultad, departamento, tema, dim_nivel=dim_nivel):
        cuenta = contar_por_postura(t, npos, nneu, nneg, cuenta_tipo=ctipo)
        acc = out.setdefault(dim, dict.fromkeys(ORDEN_POSTURA, 0))
        for k, v in cuenta.items():
            acc[k] += v
    return out


def _agrupado(db, dias, dim_col, campus, facultad, departamento, tema,
              peso_likes, vida_media, fecha_desde=None, fecha_hasta=None) -> list[dict]:
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return []
    desde, hasta = r
    stmt = (
        select(dim_col, H.fecha, *_COLS)
        .where(H.fecha >= desde, H.fecha <= hasta, dim_col.is_not(None),
               *_condiciones(campus, facultad, departamento, tema))
        .group_by(dim_col, H.fecha)
    )
    filas = list(db.execute(stmt))
    if not filas:
        return []
    ref = max(f[1] for f in filas)

    acc: dict = {}
    for dim, fecha, n, ppos, pneg, speso, spos, sneg, sgan, npos, nneu, nneg in filas:
        num_pos, num_neg, den = _pick(peso_likes, ppos, pneg, speso, spos, sneg, n)
        d = _decaimiento(fecha, ref, vida_media)
        a = acc.setdefault(dim, {"n": 0, "num_pos": 0.0, "num_neg": 0.0, "den": 0.0,
                                 "sgan": 0.0, "npos": 0, "nneu": 0, "nneg": 0})
        a["n"] += int(n or 0)
        a["num_pos"] += d * num_pos
        a["num_neg"] += d * num_neg
        a["den"] += d * den
        a["sgan"] += float(sgan or 0)
        a["npos"] += int(npos or 0); a["nneu"] += int(nneu or 0); a["nneg"] += int(nneg or 0)
    return [{"dim": dim, **v} for dim, v in acc.items()]


def por_tema(db, *, dias=30, campus=None, facultad=None, departamento=None,
             peso_likes=1.0, vida_media=VIDA_MEDIA_DIAS, fecha_desde=None, fecha_hasta=None) -> dict:
    etq = etiquetas_tema(db)
    temas = []
    for g in _agrupado(db, dias, H.tema, campus, facultad, departamento, None,
                       peso_likes, vida_media, fecha_desde, fecha_hasta):
        temas.append({
            "tema": g["dim"], "etiqueta": etq.get(g["dim"], g["dim"]),
            "indice_promedio": _indice(g["num_pos"], g["num_neg"], g["den"]),
            "confianza_promedio": _confianza(g["n"], g["sgan"]),
            "n_comentarios": g["n"],
            "n_pos": g["npos"], "n_neu": g["nneu"], "n_neg": g["nneg"],
        })
    temas.sort(key=lambda t: t["n_comentarios"], reverse=True)
    return {"temas": temas}


def por_unidad(db, *, nivel="facultad", dias=30, campus=None, departamento=None, tema=None,
               peso_likes=1.0, vida_media=VIDA_MEDIA_DIAS, fecha_desde=None, fecha_hasta=None) -> dict:
    dim = {"facultad": H.facultad, "campus": H.campus, "departamento": H.departamento}.get(nivel, H.facultad)
    unidades = []
    for g in _agrupado(
        db, dias, dim, campus if nivel != "campus" else None,
        None, departamento if nivel != "departamento" else None, tema,
        peso_likes, vida_media, fecha_desde, fecha_hasta,
    ):
        unidades.append({
            "nombre": g["dim"],
            "indice_promedio": _indice(g["num_pos"], g["num_neg"], g["den"]),
            "confianza_promedio": _confianza(g["n"], g["sgan"]),
            "n_comentarios": g["n"],
        })
    unidades.sort(key=lambda u: (u["indice_promedio"] is None, -(u["indice_promedio"] or 0)))
    return {"nivel": nivel, "unidades": unidades}


def emociones(db, *, dias=30, campus=None, facultad=None, departamento=None, tema=None,
              fecha_desde=None, fecha_hasta=None) -> dict:
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return {"items": []}
    desde, hasta = r
    filas = db.execute(
        select(H.emociones).where(
            H.fecha >= desde, H.fecha <= hasta, H.emociones.is_not(None),
            *_condiciones(campus, facultad, departamento, tema),
        )
    ).scalars().all()
    total: dict[str, int] = {}
    for conteo in filas:
        for emo, k in (conteo or {}).items():
            total[emo] = total.get(emo, 0) + int(k)
    items = [
        {"emocion": e, "etiqueta": ETIQUETAS_EMOCION.get(e, e), "n": k}
        for e, k in total.items()
    ]
    items.sort(key=lambda x: x["n"], reverse=True)
    return {"items": items}


# --------------------------------------------------------------------------- #
# SÍNTESIS — "de qué hablan, con qué emoción y en qué área" (capa 1).
# --------------------------------------------------------------------------- #
# Es la capa DETERMINISTA del resumen: puro SQL sobre la tabla de hechos, mismo
# input => mismo número siempre. La capa 2 (narración en lenguaje natural, que
# corre en la ingesta semanal del worker) consume ESTA salida — nunca los
# comentarios crudos — para que las CIFRAS del tablero jamás dependan de un LLM.
#
# Dos decisiones de cálculo, ambas por legibilidad directiva:
#
# 1. SIN DECAIMIENTO (vida_media=0). El resto del dashboard es 'as-of-fecha' y
#    decae por recencia; eso hace que una unidad cuyos comentarios son todos más
#    viejos que la vida media quede con den=0 => índice None, pero con su `n`
#    intacto (se acumula sin decaer, ver _agrupado). En pantalla eso es
#    "39 comentarios, índice —", que no se entiende. La síntesis responde "en
#    ESTE período, de qué se habló", así que cada comentario del período pesa
#    igual y el índice queda siempre definido.
#
# 2. EVIDENCIA EXPLÍCITA. Ordenar por índice crudo pone arriba a unidades con 7
#    comentarios y confianza 0.14, por encima de una con 88 y confianza 0.64: el
#    ranking miente. Cada fila trae `evidencia_suficiente` (n >= N_MIN_CONFIANZA)
#    y el orden primario es por VOLUMEN, no por índice. El ranking por índice se
#    ofrece solo dentro del grupo con evidencia, vía `focos`.
N_MIN_EVIDENCIA = N_MIN_CONFIANZA  # 30 comentarios; mismo umbral que la confianza


def _emociones_por_dim(db, desde, hasta, dim_col, campus, facultad, departamento, tema) -> dict:
    """{valor_dimension: {emocion: n}} sumando el JSON `emociones` de los hechos.

    El worker ya guarda el conteo de emociones DENTRO de la fila de hecho, que es
    de grano (fecha, campus, facultad, departamento, tema). Por eso el cruce
    tema × emoción × área no necesita tocar los comentarios: se agrega acá.
    """
    stmt = select(dim_col, H.emociones).where(
        H.fecha >= desde, H.fecha <= hasta,
        dim_col.is_not(None), H.emociones.is_not(None),
        *_condiciones(campus, facultad, departamento, tema),
    )
    acc: dict[str, dict[str, int]] = {}
    for dim, conteo in db.execute(stmt):
        destino = acc.setdefault(dim, {})
        for emo, k in (conteo or {}).items():
            destino[emo] = destino.get(emo, 0) + int(k or 0)
    return acc


def _top_emocion(conteo: dict[str, int]) -> dict | None:
    """Emoción dominante {emocion, etiqueta, n, pct} o None si no hay conteo."""
    if not conteo:
        return None
    total = sum(conteo.values())
    if total <= 0:
        return None
    emo, n = max(conteo.items(), key=lambda kv: kv[1])
    return {
        "emocion": emo,
        "etiqueta": ETIQUETAS_EMOCION.get(emo, emo),
        "n": int(n),
        "pct": round(100.0 * n / total, 1),
    }


def _cruce_volumen(db, desde, hasta, col_a, col_b, campus, facultad, departamento, tema) -> dict:
    """{valor_a: [(valor_b, n_comentarios), ...]} ordenado por volumen desc."""
    stmt = (
        select(col_a, col_b, func.sum(H.n_comentarios))
        .where(H.fecha >= desde, H.fecha <= hasta,
               col_a.is_not(None), col_b.is_not(None),
               *_condiciones(campus, facultad, departamento, tema))
        .group_by(col_a, col_b)
    )
    acc: dict[str, list] = {}
    for a, b, n in db.execute(stmt):
        acc.setdefault(a, []).append((b, int(n or 0)))
    for a in acc:
        acc[a].sort(key=lambda x: x[1], reverse=True)
    return acc


def _clave_orden(fila: dict, orden: str):
    """Clave de ordenamiento de temas/áreas.

    `orden="peor"` (default) pone PRIMERO lo peor hablado, que es la lectura que
    pidió la DAI. Pero ordenar por índice a secas dejaría arriba filas de n=1
    (una unidad con 2 comentarios e índice 37.5 encabezaría el listado y se leería
    como "la peor facultad"). Por eso la evidencia manda SIEMPRE en el primer
    término de la tupla: las muestras chicas caen al fondo en cualquier orden, y
    ahí sí se compara por índice.
    """
    sin_evidencia = not fila["evidencia_suficiente"]
    idx = fila["indice"]
    if orden == "volumen":
        return (sin_evidencia, -fila["n_comentarios"])
    # None (sin polaridad) al final de su grupo: no es "lo peor", es "sin señal".
    return (sin_evidencia, idx is None, idx if idx is not None else 0.0)


def sintesis(db, *, dias=30, campus=None, facultad=None, departamento=None, tema=None,
             nivel="facultad", orden="peor", peso_likes=1.0,
             fecha_desde=None, fecha_hasta=None, vida_media=0,
             min_global_palabras=None) -> dict:
    """Resumen ejecutivo del período: de qué se habla, con qué emoción, en qué área.

    Devuelve los DOS cortes que pidió la DAI en una sola llamada (para que el
    front no tenga que cruzar N endpoints a mano):
      * `temas`: qué se habla, cómo se siente y dónde se concentra cada tema.
      * `areas`: cómo está cada unidad y de qué se habla ahí.
    Más `focos`, que es lo único que un directivo necesita mirar primero.

    El filtro `tema` aplica a `areas` y `focos` (responde "en este tema, qué
    unidades están peor") pero NO al desglose `temas`, que mostraría una sola
    fila y dejaría de ser un desglose.
    """
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return {"hay_datos": False, "periodo": None, "global": None,
                "temas": [], "areas": [], "cambios": [], "periodo_anterior": None}
    desde, hasta = r
    # "Todo" llega como dias=36500, así que `desde` cae ~100 años atrás y el
    # tablero mostraría "período: 21/08/1926 – 27/07/2026". Se acota al primer
    # día CON datos: no cambia ningún cálculo (el WHERE filtra igual), solo hace
    # que el período informado sea el real.
    fmin = db.execute(select(func.min(H.fecha))).scalar_one_or_none()
    if fmin and desde < fmin:
        desde = fmin
    dim_area = {"facultad": H.facultad, "campus": H.campus,
                "departamento": H.departamento}.get(nivel, H.facultad)

    # `vida_media` llega desde el control global del tablero y por defecto es 0
    # (sin decaimiento), que es la lectura "promedio del período" con la que se
    # diseñó esta vista. Cuando el usuario SÍ pide recencia, hay una consecuencia
    # que la UI tiene que nombrar: una unidad cuyos comentarios son todos más
    # viejos que la vida configurada queda con den=0 => índice None, pero con su
    # `n` intacto. Medido sobre datos reales con rango de 90 días: con vida 30
    # quedan 2 de 8 facultades sin índice; con vida 7, 4 de 8. No es un error —
    # significa "esta unidad no habló últimamente"— pero mostrado como un guion
    # mudo no se entiende, así que el front lo escribe con todas las letras.
    g_temas = _agrupado(db, dias, H.tema, campus, facultad, departamento, None,
                        peso_likes, vida_media, fecha_desde, fecha_hasta)
    # Las ÁREAS sí respetan el filtro de tema: "en Infraestructura, ¿qué unidades
    # están peor?" es una pregunta legítima del tablero.
    g_areas = _agrupado(db, dias, dim_area,
                        campus if nivel != "campus" else None,
                        facultad if nivel != "facultad" else None,
                        departamento if nivel != "departamento" else None,
                        tema, peso_likes, vida_media, fecha_desde, fecha_hasta)

    emo_tema = _emociones_por_dim(db, desde, hasta, H.tema, campus, facultad, departamento, None)
    emo_area = _emociones_por_dim(db, desde, hasta, dim_area, campus, facultad, departamento, tema)
    # `nivel`, no `dim_area`: la postura se lee del CORPUS y `dim_area` es una
    # columna de la tabla de hechos. Mezclarlas produce un producto cartesiano.
    post_area = _postura_por_dim(db, desde, hasta, nivel, campus, facultad, departamento, tema)
    areas_de_tema = _cruce_volumen(db, desde, hasta, H.tema, dim_area,
                                   campus, facultad, departamento, None)
    temas_de_area = _cruce_volumen(db, desde, hasta, dim_area, H.tema,
                                   campus, facultad, departamento, tema)

    etq = etiquetas_tema(db)
    total_n = sum(g["n"] for g in g_temas) or 0

    # Qué se DICE literalmente en cada área y en cada tema. Una pasada del corpus
    # con el vocabulario validado global (ver la regla anti-PII de este módulo).
    palabras_area, palabras_tema = _palabras_por_dimension(
        db, dias=dias, campus=campus, facultad=facultad, departamento=departamento,
        tema=tema, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, nivel=nivel,
        min_global=(MIN_GLOBAL_PALABRA if min_global_palabras is None else min_global_palabras),
    )

    temas = []
    for g in g_temas:
        clave = g["dim"]
        temas.append({
            "tema": clave,
            "etiqueta": etq.get(clave, clave),
            "n_comentarios": g["n"],
            "share_pct": round(100.0 * g["n"] / total_n, 1) if total_n else 0.0,
            "indice": _indice(g["num_pos"], g["num_neg"], g["den"]),
            "confianza": _confianza(g["n"], g["sgan"]),
            "evidencia_suficiente": g["n"] >= N_MIN_EVIDENCIA,
            "n_pos": g["npos"], "n_neu": g["nneu"], "n_neg": g["nneg"],
            "emocion_dominante": _top_emocion(emo_tema.get(clave, {})),
            "areas_top": [
                {"nombre": nombre, "n_comentarios": n}
                for nombre, n in areas_de_tema.get(clave, [])[:3]
            ],
            "palabras_top": palabras_tema.get(clave, []),
        })
    temas.sort(key=lambda t: _clave_orden(t, orden))

    areas = []
    for g in g_areas:
        nombre = g["dim"]
        top_tema = (temas_de_area.get(nombre) or [(None, 0)])[0]
        areas.append({
            "nombre": nombre,
            "n_comentarios": g["n"],
            "share_pct": round(100.0 * g["n"] / total_n, 1) if total_n else 0.0,
            "indice": _indice(g["num_pos"], g["num_neg"], g["den"]),
            "confianza": _confianza(g["n"], g["sgan"]),
            "evidencia_suficiente": g["n"] >= N_MIN_EVIDENCIA,
            "n_pos": g["npos"], "n_neu": g["nneu"], "n_neg": g["nneg"],
            "tema_dominante": (
                {"tema": top_tema[0], "etiqueta": etq.get(top_tema[0], top_tema[0]),
                 "n_comentarios": top_tema[1]}
                if top_tema[0] else None
            ),
            "emocion_dominante": _top_emocion(emo_area.get(nombre, {})),
            # Postura del área. Va acá y no en un bloque aparte porque la pregunta
            # («¿qué unidad concentra lo adverso?») es de comparación, y comparar
            # es exactamente lo que hace esta tabla.
            "postura": _tramos_postura(post_area.get(nombre)),
            "palabras_top": palabras_area.get(nombre, []),
        })
    areas.sort(key=lambda a: _clave_orden(a, orden))

    # QUÉ CAMBIÓ — reemplaza a los "focos por umbral fijo".
    #
    # El criterio anterior (índice < 50) dejó de informar apenas se corrigió la
    # clasificación: ningún tema quedó bajo el neutro y el bloque quedó VACÍO.
    # Y ordenar por "lo peor" tampoco sirve — sería siempre la misma lista.
    # Tampoco alcanza "lo más hablado": Académico y Eventos concentran el volumen
    # todas las semanas, así que no dice nada nuevo.
    #
    # Lo que sí cambia de un período a otro es el MOVIMIENTO. Se compara la
    # ventana actual contra la ventana INMEDIATAMENTE anterior del mismo largo y
    # se ordena por cuánto se movió cada tema. Responde "¿qué pasó este período
    # que no pasaba antes?", que es la pregunta de un directivo.
    largo = max((hasta - desde).days, 1)
    prev_hasta = desde - timedelta(days=1)
    prev_desde = prev_hasta - timedelta(days=largo)
    # Con el rango en "Todo", la ventana previa cae ENTERA antes del primer dato
    # y cada tema se reportaría como "nuevo este período", que es falso: no es
    # que aparecieron, es que no hay con qué comparar. En ese caso no hay
    # comparación posible y se devuelve vacío.
    hay_comparacion = bool(fmin and prev_hasta >= fmin)
    # La ventana previa va SIN decaimiento aunque el usuario haya pedido recencia:
    # decaída, se mediría contra el borde derecho del período anterior y casi todo
    # daría cero. La comparación tiene que ser entre dos períodos medidos igual.
    previos = (
        {
            g["dim"]: g
            for g in _agrupado(db, largo, H.tema, campus, facultad, departamento, None,
                               peso_likes, 0, prev_desde, prev_hasta)
        }
        if hay_comparacion
        else {}
    )

    # El índice ACTUAL para la comparación se recalcula LLANO cuando el usuario
    # pidió recencia: comparar un período decaído contra uno sin decaer daría un
    # delta que no significa nada. Dentro de "Qué cambió", los dos lados se miden
    # igual — la recencia sí manda en el resto de la vista.
    actuales_llano = (
        {g["dim"]: g for g in _agrupado(db, dias, H.tema, campus, facultad, departamento,
                                        None, peso_likes, 0, fecha_desde, fecha_hasta)}
        if vida_media else {g["dim"]: g for g in g_temas}
    )

    cambios = []
    for t in temas:
        antes = previos.get(t["tema"])
        n_antes = antes["n"] if antes else 0
        idx_antes = _indice(antes["num_pos"], antes["num_neg"], antes["den"]) if antes else None
        ahora = actuales_llano.get(t["tema"])
        idx_ahora = _indice(ahora["num_pos"], ahora["num_neg"], ahora["den"]) if ahora else None
        delta_idx = (
            round(idx_ahora - idx_antes, 1)
            if (idx_ahora is not None and idx_antes is not None)
            else None
        )
        # Variación de volumen en PUNTOS PORCENTUALES sobre el período previo.
        # Sin base previa se marca como "nuevo" en vez de dividir por cero.
        if n_antes > 0:
            delta_vol_pct = round(100.0 * (t["n_comentarios"] - n_antes) / n_antes, 1)
        else:
            delta_vol_pct = None
        cambios.append({
            "tema": t["tema"],
            "etiqueta": t["etiqueta"],
            "n_comentarios": t["n_comentarios"],
            "n_anterior": n_antes,
            "delta_volumen_pct": delta_vol_pct,
            # El índice que se muestra en "Qué cambió" es el LLANO, el mismo con
            # el que se calculó el delta. Mostrar el decaído al lado de un delta
            # llano sería incoherente.
            "indice": idx_ahora,
            "indice_anterior": idx_antes,
            "delta_indice": delta_idx,
            "evidencia_suficiente": t["evidencia_suficiente"],
            "emocion_dominante": t["emocion_dominante"],
            "es_nuevo": n_antes == 0 and t["n_comentarios"] > 0,
        })

    def _magnitud(c: dict) -> float:
        """Cuánto se movió. Un tema nuevo siempre encabeza: aparecer de la nada
        es el cambio más fuerte que puede haber."""
        if c["es_nuevo"]:
            return 1e6 + c["n_comentarios"]
        vol = abs(c["delta_volumen_pct"] or 0)
        idx = abs(c["delta_indice"] or 0) * 10  # 1 punto de índice ≈ 10% de volumen
        return vol + idx

    # Sin evidencia no hay cambio que reportar: el ruido de 3 comentarios daría
    # variaciones del 300% y taparía lo que de verdad se movió.
    cambios = [c for c in cambios if c["evidencia_suficiente"]] if hay_comparacion else []
    cambios.sort(key=_magnitud, reverse=True)

    num_pos = sum(g["num_pos"] for g in g_temas)
    num_neg = sum(g["num_neg"] for g in g_temas)
    den = sum(g["den"] for g in g_temas)
    emo_global: dict[str, int] = {}
    for conteo in emo_tema.values():
        for emo, k in conteo.items():
            emo_global[emo] = emo_global.get(emo, 0) + int(k)

    return {
        "hay_datos": total_n > 0,
        "periodo": {"desde": desde, "hasta": hasta, "dias": (hasta - desde).days},
        "global": {
            "n_comentarios": total_n,
            "indice": _indice(num_pos, num_neg, den),
            "confianza": _confianza(total_n, sum(g["sgan"] for g in g_temas)),
            "distribucion": {
                "positivo": sum(g["npos"] for g in g_temas),
                "neutral": sum(g["nneu"] for g in g_temas),
                "negativo": sum(g["nneg"] for g in g_temas),
            },
            "emocion_dominante": _top_emocion(emo_global),
        },
        "nivel_area": nivel,
        "orden": orden,
        "tema_filtrado": tema,
        # COBERTURA del corte por área: no todo hecho trae la dimensión (el
        # agrupado descarta los NULL), así que las áreas suman MENOS que el total.
        # Con los datos reales eso es ~219 de 555 por facultad: si el tablero no lo
        # dice, se lee el corte por área como si cubriera toda la conversación.
        "cobertura_area": {
            "n_con_area": sum(g["n"] for g in g_areas),
            "n_total": total_n,
            "pct": round(100.0 * sum(g["n"] for g in g_areas) / total_n, 1) if total_n else 0.0,
        },
        "temas": temas,
        "areas": areas,
        "cambios": cambios,
        "periodo_anterior": (
            {"desde": prev_desde, "hasta": prev_hasta} if hay_comparacion else None
        ),
        "n_min_evidencia": N_MIN_EVIDENCIA,
    }


# --------------------------------------------------------------------------- #
# CORPUS DE COMENTARIOS — la query común de todo lo que lee TEXTOS.
# --------------------------------------------------------------------------- #
# La tabla de HECHOS no sirve para esto: es agregada y no guarda el texto. La
# nube de palabras y el conteo de términos críticos leen los comentarios crudos,
# con el MISMO join y el MISMO filtro. Estaba escrito dentro de `nube_palabras`;
# se extrajo para que las dos vistas no se desincronicen al tocar una sola.


def _fmax_comentario(db):
    """Fecha del comentario más reciente. La ventana se ancla acá, no a hoy."""
    return db.execute(select(func.max(C.fecha_comentario))).scalar_one_or_none()


def _conteos_postura(db, desde, hasta, campus, facultad, departamento, tema,
                     *, dim_nivel: str | None = None) -> list[tuple]:
    """(dim?, tema, cuenta_tipo) → (n_pos, n_neu, n_neg), leído del CORPUS.

    ⚠️ POR QUÉ NO SALE DE LA TABLA DE HECHOS, como todo lo demás del módulo.
    Desde 09-2026 la postura mira también el TIPO DE CUENTA —un neutro en la
    federación es adverso, ver `postura.NEU_FEDERACION_ES_ADVERSO`— y el grano de
    `percepcion_hecho_diario` es (fecha, origen, campus, facultad, depto, tema): no
    guarda la cuenta. Agregarla ahí significaría tocar un esquema del que el worker
    es dueño, y sus inserts dejarían la columna en NULL hasta que él se actualice.

    Bajar al corpus es exacto y no toca nada compartido. El costo es real pero
    acotado —el join recorre el corpus completo (~8.200 filas hoy) en vez de ~2.100
    hechos— y es el mismo camino que `critica.filas_de_comentarios` ya hace en
    producción. Se agrupa en SQL, así que lo que vuelve son decenas de filas.
    """
    # ⚠️ `dim_nivel` es el NOMBRE del nivel, no una columna. Recibir la columna era
    # un error caro: quien llama tiene a mano `H.facultad` —la de la tabla de
    # hechos— y meterla en una consulta del corpus arrastra `percepcion_hecho_diario`
    # al FROM sin ninguna condición de join. El resultado es un PRODUCTO CARTESIANO
    # que infla los conteos en silencio; lo delató un SAWarning, no un test.
    dim_col = {"facultad": Cu.facultad, "campus": Cu.campus,
               "departamento": Cu.departamento}.get(dim_nivel or "")
    cols = [C.tema, Cu.tipo, S.sentimiento, func.count()]
    if dim_col is not None:
        cols.insert(0, dim_col)
    cond = [C.fecha_comentario >= desde, C.fecha_comentario < hasta + timedelta(days=1)]
    if campus:
        cond.append(Cu.campus == campus)
    if facultad:
        cond.append(Cu.facultad == facultad)
    if departamento:
        cond.append(Cu.departamento == departamento)
    if tema:
        cond.append(C.tema == tema)
    if dim_col is not None:
        cond += [dim_col.is_not(None), dim_col != ""]
    grupos = [C.tema, Cu.tipo, S.sentimiento]
    if dim_col is not None:
        grupos.insert(0, dim_col)

    # (clave) -> [n_pos, n_neu, n_neg]. El tono se pivotea acá y no en SQL para no
    # escribir tres CASE que sqlite y postgres tratan distinto.
    acc: dict[tuple, list[int]] = {}
    for fila in db.execute(_select_corpus(*cols).where(*cond).group_by(*grupos)):
        *clave, sent, n = fila
        celda = acc.setdefault(tuple(clave), [0, 0, 0])
        celda[{"POS": 0, "NEU": 1}.get((sent or "").upper(), 2)] += int(n or 0)
    return [(*clave, *conteos) for clave, conteos in acc.items()]


def _cond_corpus(fmax, *, dias, campus, facultad, departamento, tema,
                 fecha_desde, fecha_hasta) -> list:
    """WHERE del corpus de textos.

    Si viene `fecha_desde`/`fecha_hasta` manda ese intervalo (fin INCLUSIVE, por
    eso el `< día siguiente`) e ignora la ventana `dias`; si no, los últimos
    `dias` anclados al comentario más reciente.
    """
    cond: list = []
    if fecha_desde or fecha_hasta:
        if fecha_desde:
            cond.append(C.fecha_comentario >= fecha_desde)
        if fecha_hasta:
            cond.append(C.fecha_comentario < fecha_hasta + timedelta(days=1))
    else:
        cond.append(C.fecha_comentario >= fmax - timedelta(days=dias))
    if campus:
        cond.append(Cu.campus == campus)
    if facultad:
        cond.append(Cu.facultad == facultad)
    if departamento:
        cond.append(Cu.departamento == departamento)
    if tema:
        cond.append(C.tema == tema)
    return cond


def _select_corpus(*columnas):
    """SELECT con los joins canónicos comentario ⋈ score ⋈ publicación ⋈ cuenta.

    La cuenta entra porque campus/facultad/departamento cuelgan de ELLA, no del
    comentario: el área es dónde se comentó, no de dónde es quien comenta.
    """
    return (
        select(*columnas)
        .join(S, S.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
    )


def _lunes(d: date) -> date:
    """Lunes de la semana de `d`. Ancla de toda agregación semanal del módulo."""
    return d - timedelta(days=d.weekday())


def _a_fecha(v):
    return v.date() if isinstance(v, datetime) else v


# --------------------------------------------------------------------------- #
# NUBE DE PALABRAS — qué se dice, literalmente.
# --------------------------------------------------------------------------- #
# Complementa la síntesis: los TEMAS son categorías del clasificador (8 cajas),
# la nube muestra el vocabulario CRUDO. Sirve para detectar de qué se habla antes
# de que exista una categoría para eso.
#
# Tokeniza los comentarios del filtro y cuenta frecuencias, arrastrando el
# sentimiento/emoción/tema de cada comentario a cada palabra suya. Así el front
# puede colorear por la dimensión que elija sin volver a pedir nada.

# Tope de seguridad: hoy son ~555 comentarios y tokenizar es instantáneo, pero
# esto crece sin techo. Con el tope, la nube degrada a "los N más recientes" en
# vez de tumbar el request.
MAX_COMENTARIOS_NUBE = 20000

# Stopwords ES/EN mínimas. No se usa una librería a propósito: agregar una
# dependencia por una lista de palabras no se paga, y acá conviene poder sumar
# términos propios de la UCN sin pelear con el diccionario de nadie.
_STOPWORDS = {
    # Español: artículos, preposiciones, pronombres, verbos vacíos.
    "a", "al", "algo", "algun", "alguna", "algunas", "alguno", "algunos", "ante",
    "antes", "aqui", "asi", "aun", "aunque", "bien", "cada", "casi", "como", "con",
    "contra", "cual", "cuales", "cuando", "cuanto", "de", "del", "desde", "donde",
    "dos", "el", "ella", "ellas", "ello", "ellos", "en", "entre", "era", "eran",
    "eres", "es", "esa", "esas", "ese", "eso", "esos", "esta", "estan", "estas",
    "este", "esto", "estos", "estoy", "fue", "fueron", "ha", "haber", "habia",
    "hace", "hacen", "hacer", "hasta", "hay", "la", "las", "le", "les", "lo",
    "los", "mas", "me", "mi", "mis", "mucho", "muy", "nada", "ni", "no", "nos",
    "nosotros", "o", "otra", "otras", "otro", "otros", "para", "pero", "poco",
    "por", "porque", "pue", "pues", "que", "se", "sea", "ser", "si", "sido",
    "sin", "sobre", "solo", "son", "su", "sus", "tambien", "tan", "tanto", "te",
    "tiene", "tienen", "toda", "todas", "todo", "todos", "tu", "tus", "un", "una",
    "unas", "uno", "unos", "ya", "yo", "él", "más", "sí", "está", "están", "qué",
    "cómo", "dónde", "así", "aún", "sólo", "les", "muchas", "muchos", "vez",
    "ahora", "siempre", "nunca", "puede", "pueden", "va", "van", "hacia", "eso",
    # Inglés: los comentarios mezclan idioma.
    "the", "and", "for", "you", "your", "with", "this", "that", "are", "was",
    "have", "has", "not", "but", "all", "can", "will", "from", "they", "there",
    "what", "when", "who", "how", "its", "it's", "our", "out", "get", "just",
    # ARTEFACTOS DE SCRAPING de Instagram. Sin esto encabezan la nube y tapan
    # todo: aparecen en casi cada comentario largo y NO los escribió nadie.
    # Visto en datos reales: "…fiestas lujosas si See translation View all 8 replies".
    "see", "translation", "view", "reply", "replies", "more", "ver", "traduccion",
    "traducción", "respuestas", "respuesta", "editado", "edited",
    # Saludos y muletillas sin señal: encabezan la nube y no dicen nada.
    "hola", "holi", "buenas", "jaja", "jajaja", "jsjs", "wena",
}
# OJO: acá NO van "cookie"/"facebook". Se filtraron en una primera versión por
# parecer chrome del scraper y fue un FALSO POSITIVO: "Cookie" es la mascota de
# la UCN y aparece en 7 comentarios reales ("Parece todo un caballero el Cookie").
# Los artefactos de scraping se atacan por FRASE (abajo), no por palabra suelta —
# borrar una palabra por sospecha se lleva puesto contenido legítimo.

# Frases exactas que el scraper pega al comentario. Se quitan del texto ANTES de
# tokenizar, así "Seca! comments from Facebook" aporta "seca" y nada más, sin
# vetar "facebook" para quien lo mencione de verdad.
#
# La definición vive en `lexico` (módulo hoja) porque el conteo de términos
# críticos necesita exactamente la misma limpieza: una sola lista, no dos que se
# desincronizan en silencio.
_FRASES_SCRAPER = lexico.FRASES_SCRAPER

# Los handles de Instagram que el scraper deja pegados al texto NO llevan "@"
# salvo el primero: al etiquetar a varias personas queda
# "Participando:B tote.mny_ cldliio_" — donde el comentario real es "Participando:B".
# En español no existen palabras con "_", dígitos ni punto interno, así que ese
# patrón identifica handles sin falsos positivos. Cubre smacaya_, tote.mny_,
# av_angamos, vixoo94_, _fab.iu_.
# NO cubre los handles que son letras puras (ignaciamilann, jmanuuu): para esos
# está _HANDLES_CONOCIDOS y el clic-para-excluir del panel. El arreglo de fondo
# es que la ingesta separe las menciones del cuerpo del comentario.
_PATRON_HANDLE = re.compile(r"[_\d]|\w\.\w")

# Nombres de usuario que el scraper dejó PEGADOS al texto sin "@" (el regex de
# menciones no los agarra). En datos reales aparecieron "smacaya" (n=9) y
# "cldliio" (n=6) entre las palabras más frecuentes: son cuentas de personas, o
# sea PII en pantalla.
#
# Deliberadamente NO se filtra con un diccionario español: borraría jerga real y
# valiosa como "seca" o "porfa", que SÍ son señal. Es una lista curada, y la
# solución de fondo es que el worker separe el handle del cuerpo al ingestar.
_HANDLES_CONOCIDOS = {"smacaya", "cldliio"}


def _tokenizar(texto: str, excluir: set[str] | None = None) -> list[str]:
    """Palabras normalizadas de un comentario, listas para contar.

    Descarta, en este orden: URLs, @menciones (son PII — identifican cuentas),
    emojis/puntuación, tokens de <3 letras, números sueltos y stopwords.
    Los #hashtags SÍ quedan (sin el #): suelen ser el tema real del comentario.
    Conserva tildes y ñ: "año" y "ano" no son la misma palabra, y la nube se lee
    en español.
    """
    if not texto:
        return []
    limpio = _FRASES_SCRAPER.sub(" ", texto.lower())
    limpio = re.sub(r"https?://\S+|www\.\S+", " ", limpio)
    limpio = re.sub(r"@[\w.]+", " ", limpio)          # menciones = PII
    # Handles pegados SIN "@": se descartan mientras el token conserva "_"/dígitos
    # /punto, o sea ANTES de la limpieza de caracteres que borraría esa pista.
    limpio = " ".join(
        "" if _PATRON_HANDLE.search(tok) else tok
        for tok in limpio.split()
    )
    limpio = limpio.replace("#", " ")
    limpio = re.sub(r"[^a-záéíóúüñ\s]", " ", limpio)  # deja solo letras ES
    vetadas = _STOPWORDS | _HANDLES_CONOCIDOS | (excluir or set())
    salida = []
    for palabra in limpio.split():
        if len(palabra) < 3 or palabra in vetadas:
            continue
        salida.append(palabra)
    return salida


# Tildes vocálicas fuera para comparar raíces, pero la Ñ SE RESPETA. Colapsarla
# fusionó "toño" (apodo) con "tono" en una prueba con datos reales: en español la
# ñ es una letra distinta, no una "n" decorada.
_SIN_TILDES = str.maketrans("áéíóúü", "aeiouu")


def _raiz_agrupacion(palabra: str) -> str:
    """Raíz para juntar variantes de la MISMA palabra (singular/plural).

    Deliberadamente conservador: solo quita los plurales regulares "-s"/"-es" y
    exige que quede un tronco de 4+ letras. No es un lematizador — no toca
    conjugaciones ni derivaciones, porque un stemmer agresivo en español une
    cosas que no van juntas y la nube perdería sentido en silencio.
    """
    s = palabra.translate(_SIN_TILDES)
    for sufijo in ("es", "s"):
        if s.endswith(sufijo) and len(s) - len(sufijo) >= 4:
            return s[: -len(sufijo)]
    return s


def publicaciones_dominantes(db, *, dias=30, campus=None, facultad=None,
                             departamento=None, tema=None, limite=10,
                             fecha_desde=None, fecha_hasta=None) -> dict:
    """De qué se habló: las publicaciones que concentran la conversación del período.

    POR QUÉ EXISTE. La auditoría de septiembre 2026 revisó seis caídas del índice y
    en las seis la explicación salió del mismo lugar: **mirar qué publicación
    concentraba los comentarios**. Sin eso, la etiqueta del calendario lleva a la
    conclusión equivocada — y llevó, dos veces:

      * El −8,1 de Fiestas Patrias no era ánimo: **128 de 161 comentarios (79,5 %)
        venían de dos publicaciones del mismo sorteo**, donde la gente etiqueta
        amigos. Índice 50,5 y 50,6, el neutro exacto.
      * La semana del 17-08-2026 no era descontento: era un post de condolencias por
        un profesor fallecido. 63,9 → 57,5 por sí solo.

    Un promedio sobre una muestra que concentra el 80 % en un solo post no describe
    a una comunidad: describe a ese post.

    QUÉ MUESTRA, Y POR QUÉ ASÍ
    --------------------------
    Ordena por VOLUMEN de comentarios, no por índice. Lo que hay que ver primero es
    **cuánto pesa cada publicación en la muestra**, que es lo que decide si el
    período es representativo. El índice de cada una va al lado para poder leer si
    empuja hacia arriba o hacia abajo.

    `concentracion` es la proporción del período que junta la publicación más
    grande: es el número que dice de una si el período se puede leer como un
    promedio o si hay que mirar caso por caso.
    """
    fmax = _fmax_comentario(db)
    if fmax is None:
        return {"items": [], "n_comentarios": 0, "concentracion": None}
    cond = _cond_corpus(fmax, dias=dias, campus=campus, facultad=facultad,
                        departamento=departamento, tema=tema,
                        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    filas = db.execute(
        _select_corpus(P.id, P.caption, Cu.handle, Cu.nombre, Cu.tipo,
                       S.sentimiento, S.prob_pos, S.prob_neg, C.fecha_comentario)
        .where(*cond)
    ).all()

    acc: dict = {}
    for pid, caption, handle, nombre, ctipo, sent, ppos, pneg, fecha in filas:
        a = acc.setdefault(pid, {
            "caption": caption, "handle": handle, "cuenta": nombre, "cuenta_tipo": ctipo,
            "n": 0, "n_neg": 0, "spos": 0.0, "sneg": 0.0, "desde": fecha, "hasta": fecha,
        })
        a["n"] += 1
        a["spos"] += float(ppos or 0)
        a["sneg"] += float(pneg or 0)
        if (sent or "").upper() == "NEG":
            a["n_neg"] += 1
        if fecha and (a["desde"] is None or fecha < a["desde"]):
            a["desde"] = fecha
        if fecha and (a["hasta"] is None or fecha > a["hasta"]):
            a["hasta"] = fecha

    total = sum(a["n"] for a in acc.values())
    orden = sorted(acc.items(), key=lambda kv: kv[1]["n"], reverse=True)
    items = [
        {
            "publicacion_id": pid,
            "caption": _cap_corto(a["caption"]),
            "cuenta": a["cuenta"] or a["handle"],
            "cuenta_tipo": a["cuenta_tipo"],
            "n_comentarios": a["n"],
            # Cuánto de la muestra del período es ESTA publicación. Es el dato que
            # decide si el promedio del período significa algo.
            "pct_del_periodo": round(100.0 * a["n"] / total, 1) if total else 0.0,
            "indice": _indice(a["spos"], a["sneg"], a["n"]),
            "pct_neg": round(100.0 * a["n_neg"] / a["n"], 1) if a["n"] else None,
            "desde": a["desde"].date() if a["desde"] else None,
            "hasta": a["hasta"].date() if a["hasta"] else None,
        }
        for pid, a in orden[:limite]
    ]
    return {
        "items": items,
        "n_comentarios": total,
        "n_publicaciones": len(acc),
        # Concentración de la MAYOR. Sobre 40 % conviene leer publicación por
        # publicación en vez del promedio: fue el caso del sorteo del 18.
        "concentracion": round(100.0 * orden[0][1]["n"] / total, 1) if orden and total else None,
    }


def _cap_corto(caption: str | None, n: int = 140) -> str:
    c = " ".join((caption or "").split())
    return c[:n] + ("…" if len(c) > n else "")


def nube_palabras(db, *, dias=30, campus=None, facultad=None, departamento=None,
                  tema=None, limite=120, min_frecuencia=2, excluir=None,
                  agrupar_variantes=True, fecha_desde=None, fecha_hasta=None) -> dict:
    """Frecuencia de palabras del período, con su sentimiento/tema/emoción.

    Cada palabra arrastra el desglose de los comentarios donde aparece, así el
    front puede colorearla por sentimiento, por tema o dejarla monocroma sin
    pedir nada más. `min_frecuencia=2` por defecto: una palabra dicha UNA vez no
    es un patrón, es ruido — y además, al ser única, puede volver identificable
    el comentario del que salió.
    """
    fmax = _fmax_comentario(db)
    if fmax is None:
        return {"hay_datos": False, "palabras": [], "n_comentarios": 0,
                "n_palabras_unicas": 0, "periodo": None, "truncado": False}

    cond = _cond_corpus(
        fmax, dias=dias, campus=campus, facultad=facultad, departamento=departamento,
        tema=tema, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
    )
    stmt = (
        _select_corpus(C.texto, C.tema, S.sentimiento, S.emocion)
        .where(*cond)
        .order_by(C.fecha_comentario.desc())
        .limit(MAX_COMENTARIOS_NUBE + 1)
    )
    filas = list(db.execute(stmt))
    truncado = len(filas) > MAX_COMENTARIOS_NUBE
    filas = filas[:MAX_COMENTARIOS_NUBE]

    veto = {p.strip().lower() for p in (excluir or []) if p and p.strip()}

    # set(): una palabra repetida DENTRO de un comentario cuenta una sola vez. Si
    # no, un comentario que repite "plata" cinco veces la infla como si cinco
    # personas la hubieran dicho. La nube mide CUÁNTA GENTE lo dice.
    tokenizados = [(set(_tokenizar(texto, veto)), tm, sent, emo)
                   for texto, tm, sent, emo in filas]

    # Agrupar variantes va en DOS PASADAS, y el orden importa:
    #   1ª) contar en crudo para saber cuál variante es la más frecuente — esa se
    #       usa como forma visible ("cursos" y no "curso", porque es la que la
    #       gente escribió más).
    #   2ª) reemplazar cada token por su forma canónica ANTES del set() por
    #       comentario. Si se sumaran los conteos ya calculados, un comentario que
    #       dice "el curso y los cursos" contaría DOS veces esa palabra.
    canonica: dict[str, str] = {}
    if agrupar_variantes:
        crudo: dict[str, int] = {}
        for tokens, _tm, _s, _e in tokenizados:
            for palabra in tokens:
                crudo[palabra] = crudo.get(palabra, 0) + 1
        por_raiz: dict[str, list[str]] = {}
        for palabra in crudo:
            por_raiz.setdefault(_raiz_agrupacion(palabra), []).append(palabra)
        for variantes in por_raiz.values():
            jefe = max(variantes, key=lambda w: (crudo[w], -len(w), w))
            for w in variantes:
                canonica[w] = jefe

    variantes_de: dict[str, set[str]] = {}
    acc: dict[str, dict] = {}
    for tokens, tm, sent, emo in tokenizados:
        vistos = {canonica.get(p, p) for p in tokens}
        for p in tokens:
            destino = canonica.get(p, p)
            if destino != p:
                variantes_de.setdefault(destino, set()).add(p)
        for palabra in vistos:
            a = acc.setdefault(palabra, {
                "n": 0, "pos": 0, "neu": 0, "neg": 0,
                "temas": {}, "emociones": {},
            })
            a["n"] += 1
            if sent == "POS":
                a["pos"] += 1
            elif sent == "NEG":
                a["neg"] += 1
            else:
                a["neu"] += 1
            if tm:
                a["temas"][tm] = a["temas"].get(tm, 0) + 1
            if emo:
                a["emociones"][emo] = a["emociones"].get(emo, 0) + 1

    etq = etiquetas_tema(db)
    palabras = []
    for texto, a in acc.items():
        if a["n"] < min_frecuencia:
            continue
        # Sentimiento dominante de la palabra: gana el que más aparece, pero los
        # NEUTRALES no "ganan" por mayoría — si hubiera polaridad clara quedaría
        # tapada por el 60% de neutrales del corpus. Solo es neutral si NINGUNA
        # polaridad se impone.
        if a["pos"] > a["neg"]:
            sent_dom = "POS"
        elif a["neg"] > a["pos"]:
            sent_dom = "NEG"
        else:
            sent_dom = "NEU"
        tema_dom = max(a["temas"].items(), key=lambda kv: kv[1])[0] if a["temas"] else None
        emo_dom = max(a["emociones"].items(), key=lambda kv: kv[1])[0] if a["emociones"] else None
        palabras.append({
            "texto": texto,
            "n": a["n"],
            "pos": a["pos"], "neu": a["neu"], "neg": a["neg"],
            "sentimiento_dominante": sent_dom,
            "tema_dominante": tema_dom,
            "tema_etiqueta": etq.get(tema_dom, tema_dom) if tema_dom else None,
            "emocion_dominante": emo_dom,
            "emocion_etiqueta": ETIQUETAS_EMOCION.get(emo_dom, emo_dom) if emo_dom else None,
            # Qué otras formas se fundieron acá. Se expone para que la agrupación
            # sea auditable desde la UI y no un número que aparece sin explicación.
            "variantes": sorted(variantes_de.get(texto, set())),
        })
    palabras.sort(key=lambda p: (-p["n"], p["texto"]))
    total_unicas = len(palabras)

    return {
        "hay_datos": bool(palabras),
        "palabras": palabras[:limite],
        "n_comentarios": len(filas),
        "n_palabras_unicas": total_unicas,
        "min_frecuencia": min_frecuencia,
        "agrupar_variantes": agrupar_variantes,
        "n_variantes_agrupadas": sum(len(v) for v in variantes_de.values()),
        "truncado": truncado,
        "periodo": {
            "desde": (fecha_desde or (fmax - timedelta(days=dias)).date()
                      if isinstance(fmax, datetime) else fecha_desde),
            "hasta": fecha_hasta or (fmax.date() if isinstance(fmax, datetime) else fmax),
        },
    }


# --------------------------------------------------------------------------- #
# TÉRMINOS BAJO VIGILANCIA — la conversación de conflicto, contada aparte.
# --------------------------------------------------------------------------- #
# Complementa a los TEMAS (8 cajas del clasificador) y a la NUBE (vocabulario
# crudo): acá se cuenta un léxico institucional FIJO y auditable — paro, toma,
# petitorio, asamblea, movilización — que hoy queda repartido entre "académico",
# "organización estudiantil" y "otros", y por eso no se ve.
#
# ⚠️  NO TOCA EL ÍNDICE. La fórmula canónica queda intacta y comparable con lo ya
# reportado a la DAI. Estas menciones alimentan el bloque de vigilancia y la
# SEVERIDAD de las anomalías, nada más.
#
# El HUMOR se separa, no se descarta: `humor_ironia` sale del cálculo del índice
# de la familia pero se muestra igual. RoBERTuito detecta ironía mal y un
# "jajaja paro" puede ser sarcasmo amargo — esconderlo sería decidir por el lector.
EMOCION_HUMOR = "humor_ironia"
MAX_COMENTARIOS_TERMINOS = 50000   # tope de seguridad, mismo criterio que la nube
N_EJEMPLOS_TERMINO = 3
MAX_CANDIDATOS_EJEMPLO = 100       # de dónde se eligen los ejemplos, por familia


def _menciones_por_familia(db, cond) -> dict[str, int]:
    """{familia: nº de COMENTARIOS que la mencionan} en una ventana ya filtrada.

    Solo el conteo: se usa para la ventana ANTERIOR, donde no hace falta el
    desglose completo y traer todo sería caro al pedo.
    """
    conteo: dict[str, int] = {}
    for (texto,) in db.execute(_select_corpus(C.texto).where(*cond)):
        for clave in lexico.detectar(texto):
            conteo[clave] = conteo.get(clave, 0) + 1
    return conteo


def terminos_vigilancia(db, *, dias=30, campus=None, facultad=None, departamento=None,
                        tema=None, fecha_desde=None, fecha_hasta=None,
                        n_ejemplos=N_EJEMPLOS_TERMINO) -> dict:
    """Menciones del léxico crítico en el período: cuántas, con qué carga, dónde.

    Por familia devuelve el conteo separando SERIO de HUMOR, el desglose de
    sentimiento y el índice de los serios, los TEMAS donde aparece, la evolución
    semanal, la variación contra el período anterior y unos EJEMPLOS textuales.

    Los ejemplos no son decoración: un contador que no se puede auditar no lo
    cree nadie, y con razón. Van anónimos (el `autor_hash` jamás sale de la BD).
    """
    fmax = _fmax_comentario(db)
    if fmax is None:
        return {"hay_datos": False, "periodo": None, "global": None,
                "familias": [], "periodo_anterior": None}

    hasta = fecha_hasta or _a_fecha(fmax)
    desde = fecha_desde or (hasta - timedelta(days=dias))
    filtro = {"campus": campus, "facultad": facultad,
              "departamento": departamento, "tema": tema}

    filas = list(db.execute(
        _select_corpus(C.texto, C.fecha_comentario, C.tema,
                       S.sentimiento, S.prob_pos, S.prob_neg, S.emocion)
        .where(*_cond_corpus(fmax, dias=dias, fecha_desde=fecha_desde,
                             fecha_hasta=fecha_hasta, **filtro))
        .order_by(C.fecha_comentario.desc())
        .limit(MAX_COMENTARIOS_TERMINOS)
    ))

    acc: dict[str, dict] = {}
    n_con_termino = 0
    n_humor_global = 0
    for i, (texto, fecha_dt, tm, sent, ppos, pneg, emo) in enumerate(filas):
        familias_del_comentario = lexico.detectar(texto)
        if not familias_del_comentario:
            continue
        n_con_termino += 1
        es_humor = emo == EMOCION_HUMOR
        if es_humor:
            n_humor_global += 1
        f = _a_fecha(fecha_dt)
        for clave in familias_del_comentario:
            a = acc.setdefault(clave, {
                "n": 0, "serio": 0, "humor": 0, "pos": 0, "neu": 0, "neg": 0,
                "num_pos": 0.0, "num_neg": 0.0, "temas": {}, "semanas": {},
                "primera": f, "ultima": f, "cand": [],
            })
            a["n"] += 1
            a["primera"] = min(a["primera"], f)
            a["ultima"] = max(a["ultima"], f)
            if tm:
                a["temas"][tm] = a["temas"].get(tm, 0) + 1
            sem = a["semanas"].setdefault(_lunes(f), {"n": 0, "n_neg": 0})
            sem["n"] += 1
            if es_humor:
                a["humor"] += 1
            else:
                a["serio"] += 1
                a["num_pos"] += float(ppos or 0)
                a["num_neg"] += float(pneg or 0)
                if sent == "POS":
                    a["pos"] += 1
                elif sent == "NEG":
                    a["neg"] += 1
                    sem["n_neg"] += 1
                else:
                    a["neu"] += 1
            if len(a["cand"]) < MAX_CANDIDATOS_EJEMPLO:
                a["cand"].append((es_humor, sent != "NEG", i, texto, f, sent, emo, tm))

    # Ventana INMEDIATAMENTE anterior del mismo largo, para el delta. Sin base
    # previa (o con el rango en "Todo") no hay comparación posible y se informa
    # como tal en vez de inventar un "nuevo este período" que sería falso.
    largo = max((hasta - desde).days, 1)
    prev_hasta = desde - timedelta(days=1)
    prev_desde = prev_hasta - timedelta(days=largo)
    fmin = db.execute(select(func.min(C.fecha_comentario))).scalar_one_or_none()
    hay_comparacion = bool(fmin and _a_fecha(fmin) <= prev_hasta)
    previos = (
        _menciones_por_familia(db, _cond_corpus(
            fmax, dias=largo, fecha_desde=prev_desde, fecha_hasta=prev_hasta, **filtro))
        if hay_comparacion else {}
    )

    etq = etiquetas_tema(db)
    total = len(filas)
    familias = []
    for clave, a in acc.items():
        n_antes = previos.get(clave, 0)
        cand = sorted(a["cand"])[:n_ejemplos]
        familias.append({
            "clave": clave,
            "etiqueta": lexico.ETIQUETAS_FAMILIA.get(clave, clave),
            "n_menciones": a["n"],
            "n_serio": a["serio"],
            "n_humor": a["humor"],
            "n_pos": a["pos"], "n_neu": a["neu"], "n_neg": a["neg"],
            # Índice SOLO de los serios: mide con qué ánimo se habla del tema.
            "indice": _indice(a["num_pos"], a["num_neg"], float(a["serio"])),
            "share_pct": round(100.0 * a["n"] / total, 1) if total else 0.0,
            "temas": [
                {"tema": t, "etiqueta": etq.get(t, t), "n": k}
                for t, k in sorted(a["temas"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
            ],
            "primera_mencion": a["primera"],
            "ultima_mencion": a["ultima"],
            "n_anterior": n_antes,
            "delta_menciones_pct": (
                round(100.0 * (a["n"] - n_antes) / n_antes, 1) if n_antes else None
            ),
            "es_nuevo": hay_comparacion and n_antes == 0,
            "serie_semanal": [
                {"semana": s, "n": v["n"], "n_neg": v["n_neg"]}
                for s, v in sorted(a["semanas"].items())
            ],
            # Primero los serios negativos, después el resto, y a igualdad los más
            # recientes: es el orden en que un directivo quiere leerlos.
            "ejemplos": [
                {
                    "texto": texto, "fecha": f,
                    "sentimiento": sent,
                    "sentimiento_label": _SENT_LABEL.get(sent, sent),
                    "emocion": emo,
                    "emocion_label": ETIQUETAS_EMOCION.get(emo, emo) if emo else None,
                    "tema": tm, "tema_label": etq.get(tm, tm) if tm else None,
                }
                for _h, _neg, _i, texto, f, sent, emo, tm in cand
            ],
        })
    familias.sort(key=lambda f: (-f["n_menciones"], f["clave"]))

    return {
        "hay_datos": bool(familias),
        "periodo": {"desde": desde, "hasta": hasta},
        "global": {
            "n_comentarios": total,
            "n_con_termino": n_con_termino,
            "pct": round(100.0 * n_con_termino / total, 1) if total else 0.0,
            "n_humor": n_humor_global,
        },
        "familias": familias,
        "periodo_anterior": (
            {"desde": prev_desde, "hasta": prev_hasta} if hay_comparacion else None
        ),
    }


# --------------------------------------------------------------------------- #
# PALABRAS DESTACADAS — el vocabulario que PESA, no el que más se repite.
# --------------------------------------------------------------------------- #
# "La palabra más dicha" no informa: medido sobre el corpus real es
# `felicitaciones` (121 apariciones, 0% negativo), seguida de `gracias` (118) y
# `felicidades` (92). Son felicitaciones a publicaciones institucionales y van a
# encabezar el ranking todos los meses.
#
# Lo que informa es la palabra CARGADA: `estudiantes` (n=37, 41% negativo),
# `universidad` (n=34, 26%), `ucn` (n=50, 16%). Cuando alguien dice "los
# estudiantes" o "la universidad", cuatro de cada diez veces es para quejarse.
#
# Se ordena por NEGATIVOS ABSOLUTOS y no por porcentaje: ordenando por % quedaban
# arriba `futuro` (n=10, 70%) y `familias` (n=12, 67%), palabras funcionales que
# aparecen en comentarios negativos sin significar nada. El conteo absoluto
# pondera volumen y carga a la vez.
#
# ⚠️ REGLA ANTI-PII — POR QUÉ EL MÍNIMO ES GLOBAL Y NO POR ÁREA.
# El tokenizador no atrapa los handles de Instagram que son letras puras
# (`ignaciamilann`, `jmanuuu`, `mish`): sin "_", dígitos ni punto interno parecen
# palabras. Se probaron dos heurísticas estructurales sobre datos reales y las DOS
# fallaron:
#   * publicaciones distintas — `ignaciamilann` aparece en 5 pubs (ratio 1.6),
#     idéntico a `felicitaciones` (1.6) y `paro` (1.6);
#   * autores distintos — lo escriben 7 personas, igual que `toma` (7). En los
#     posts de sorteo mucha gente distinta etiqueta a la misma persona.
# Lo único que separa es el VOLUMEN GLOBAL: los handles llegan a 8 apariciones en
# todo el corpus, el vocabulario real pasa de 10. Por eso el vocabulario se valida
# sobre TODO el período y recién después se rankea por área: así una facultad con
# 4 comentarios no puede publicar el nombre de una persona. Con umbral 10 el
# vocabulario queda en 122 palabras y NINGÚN handle conocido lo atraviesa.
MIN_GLOBAL_PALABRA = 10      # apariciones en el período para entrar al vocabulario
LIMITE_PALABRAS_RESUMEN = 5
LIMITE_PALABRAS_AREA = 3
# Mínimo LOCAL: además de pertenecer al vocabulario, la palabra tiene que decirse
# al menos esto en ESA área. El global protege de la PII; este protege del
# ridículo. Sin él, el Departamento de Ingeniería Industrial mostraba
# "amo (1) · año (1) · buena (1)" — palabras del vocabulario común que ahí se
# dijeron UNA vez. Un área sin nada que supere el mínimo devuelve lista vacía, y
# la UI dice "sin evidencia suficiente" en vez de inventar un titular.
MIN_LOCAL_PALABRA = 2


def _acumular_palabras(filas) -> dict:
    """{palabra: {n, n_pos, n_neu, n_neg}} sobre (texto, sentimiento) del corpus.

    `set()` por comentario: quien repite una palabra cinco veces cuenta una sola.
    Se mide cuánta GENTE lo dice, igual que la nube.
    """
    acc: dict[str, dict] = {}
    for texto, sent in filas:
        for palabra in set(_tokenizar(texto)):
            a = acc.setdefault(palabra, {"n": 0, "n_pos": 0, "n_neu": 0, "n_neg": 0})
            a["n"] += 1
            a["n_pos" if sent == "POS" else "n_neg" if sent == "NEG" else "n_neu"] += 1
    return acc


def _vocabulario(acc: dict, minimo: int) -> set[str]:
    """Palabras con volumen suficiente en TODO el período. Ver la regla anti-PII."""
    return {p for p, v in acc.items() if v["n"] >= minimo}


def _fila_palabra(texto: str, v: dict) -> dict:
    return {
        "texto": texto,
        "n": v["n"], "n_pos": v["n_pos"], "n_neu": v["n_neu"], "n_neg": v["n_neg"],
        "pct_neg": round(100.0 * v["n_neg"] / v["n"], 1) if v["n"] else 0.0,
    }


# --------------------------------------------------------------------------- #
# D · Leave-one-out word impacts — QUÉ palabra movió la conversación.
# --------------------------------------------------------------------------- #
# Método de Rieger et al. (Text2Story'26, §3.2), el paper de RollingLDA sobre
# conflictos socioambientales en Chile:
#
#     impacto(v) = cos(t₁, t₂, V∖v) − cos(t₁, t₂, V)
#
# Se comparan dos períodos por su vector de conteos de palabras. Si al SACAR la
# palabra `v` los dos períodos se parecen MÁS, entonces `v` era la que los
# diferenciaba: es la palabra que movió la conversación.
#
# Por qué hacía falta. El bloque "Las palabras que más pesan" del Resumen ordenaba
# por negativos absolutos — una heurística inventada acá porque ya se había medido
# que la frecuencia sola no sirve (`felicitaciones`: 121 menciones, 0 % negativo,
# sería la misma todos los meses). Buen instinto, pero responde "qué se dice", no
# "qué CAMBIÓ". Esto responde lo segundo, que es lo que un tablero de percepción
# tiene que contestar.
#
# ⚠️ TECHO CONOCIDO: el vocabulario útil del corpus es chico (211 palabras con 10+
# apariciones, por la regla anti-PII). Con pocas palabras el ranking se vuelve
# inestable, y por eso `MIN_POR_VENTANA` exige presencia en AMBOS períodos: una
# palabra que aparece en uno solo produce un impacto enorme y sin sentido.
MIN_POR_VENTANA = 3        # apariciones mínimas en CADA una de las dos ventanas
LIMITE_IMPACTO = 8


def _coseno(a: dict[str, int], b: dict[str, int], vocab) -> float:
    """Coseno entre dos vectores de conteo sobre el vocabulario dado."""
    num = sum(a.get(p, 0) * b.get(p, 0) for p in vocab)
    na = math.sqrt(sum(a.get(p, 0) ** 2 for p in vocab))
    nb = math.sqrt(sum(b.get(p, 0) ** 2 for p in vocab))
    return num / (na * nb) if na and nb else 0.0


def _conteos(db, desde, hasta, campus, facultad, departamento, tema) -> dict[str, int]:
    filas = db.execute(
        _select_corpus(C.texto).where(*_cond_corpus(
            _fmax_comentario(db), dias=None, campus=campus, facultad=facultad,
            departamento=departamento, tema=tema,
            fecha_desde=desde, fecha_hasta=hasta,
        )).limit(MAX_COMENTARIOS_NUBE)
    ).all()
    acc: dict[str, int] = {}
    for (texto,) in filas:
        for palabra in set(_tokenizar(texto)):     # una vez por comentario, como la nube
            acc[palabra] = acc.get(palabra, 0) + 1
    return acc


def impacto_palabras(db, *, dias=30, campus=None, facultad=None, departamento=None,
                     tema=None, limite=LIMITE_IMPACTO) -> dict:
    """Palabras que más movieron la conversación entre el período actual y el previo.

    Devuelve, por palabra, cuánto se parecerían los dos períodos SIN ella. Cuanto
    más alto el impacto, más responsable es esa palabra de que hayan cambiado.
    """
    # Ancla en el CORPUS (`_fmax_comentario`), no en la tabla de hechos
    # (`_fecha_maxima`): esto lee textos, y los hechos pueden estar desfasados si el
    # worker ingestó y todavía no reagregó. Mezclar las dos anclas dejaba la ventana
    # apuntando a un rango sin comentarios.
    fmax = _fmax_comentario(db)
    if fmax is None:
        return {"hay_datos": False, "palabras": [], "similitud": None,
                "periodo_actual": None, "periodo_previo": None}
    fmax = _a_fecha(fmax)      # la columna es DATETIME; las ventanas van por día

    fin_act = fmax
    ini_act = fmax - timedelta(days=dias)
    fin_pre = ini_act - timedelta(days=1)
    ini_pre = fin_pre - timedelta(days=dias)

    act = _conteos(db, ini_act, fin_act, campus, facultad, departamento, tema)
    pre = _conteos(db, ini_pre, fin_pre, campus, facultad, departamento, tema)

    # Vocabulario: presente EN LOS DOS períodos con volumen mínimo. Sin esta
    # exigencia, una palabra nueva del período actual da impacto máximo por el
    # solo hecho de no existir antes, que es información pero no de esta métrica.
    vocab = {p for p in set(act) & set(pre)
             if act[p] >= MIN_POR_VENTANA and pre[p] >= MIN_POR_VENTANA}
    if len(vocab) < 2:
        return {"hay_datos": False, "palabras": [], "similitud": None,
                "periodo_actual": [ini_act, fin_act], "periodo_previo": [ini_pre, fin_pre],
                "motivo": "Vocabulario compartido insuficiente entre los dos períodos."}

    base = _coseno(act, pre, vocab)
    filas = []
    for v in vocab:
        sin_v = vocab - {v}
        impacto = _coseno(act, pre, sin_v) - base
        filas.append({
            "texto": v,
            "impacto": round(impacto, 5),
            "n_actual": act[v],
            "n_previo": pre[v],
            # Dirección: la palabra creció o se retrajo. El impacto dice CUÁNTO
            # movió; esto dice HACIA DÓNDE, que es lo que se lee en pantalla.
            "delta": act[v] - pre[v],
        })
    filas.sort(key=lambda f: -f["impacto"])
    return {
        "hay_datos": True,
        "similitud": round(base, 4),
        "vocabulario": len(vocab),
        "periodo_actual": [ini_act, fin_act],
        "periodo_previo": [ini_pre, fin_pre],
        "palabras": filas[:limite],
    }


def _serie_mensual(db, desde, hasta, campus, facultad, departamento, tema, peso_likes) -> list[dict]:
    """Índice mes a mes, SIN decaimiento: la silueta del período de un vistazo.

    No repite la evolución de Conversación —esa es diaria, trailing, interactiva y
    con bandas de eventos—; esta responde "¿veníamos subiendo o bajando?".
    """
    acc: dict = {}
    for c in _dias_crudos(db, desde, hasta, campus, facultad, departamento, tema, peso_likes):
        mes = c["fecha"].replace(day=1)
        a = acc.setdefault(mes, {"n": 0, "num_pos": 0.0, "num_neg": 0.0, "den": 0.0})
        a["n"] += c["n"]
        a["num_pos"] += c["num_pos"]
        a["num_neg"] += c["num_neg"]
        a["den"] += c["den"]
    return [
        {"mes": m, "indice": _indice(a["num_pos"], a["num_neg"], a["den"]),
         "n_comentarios": a["n"]}
        for m, a in sorted(acc.items())
    ]


def _emociones_ventana(db, desde, hasta, campus, facultad, departamento, tema) -> dict:
    """{emocion: n} sumando el JSON de los hechos de la ventana."""
    total: dict[str, int] = {}
    filas = db.execute(
        select(H.emociones).where(
            H.fecha >= desde, H.fecha <= hasta, H.emociones.is_not(None),
            *_condiciones(campus, facultad, departamento, tema),
        )
    ).scalars().all()
    for conteo in filas:
        for emo, k in (conteo or {}).items():
            total[emo] = total.get(emo, 0) + int(k or 0)
    return total


def _emocion_que_mas_crecio(actual: dict, previa: dict) -> dict | None:
    """La emoción que más subió su PARTICIPACIÓN respecto del período anterior.

    Se compara el SHARE y no el conteo bruto: si el volumen total se duplica,
    todas las emociones "crecen" y no se aprendió nada. Lo informativo es que una
    pase a ocupar más lugar en la conversación.
    """
    tot_a, tot_p = sum(actual.values()), sum(previa.values())
    if tot_a <= 0 or tot_p <= 0:
        return None
    mejor = None
    for emo, n in actual.items():
        share_a = 100.0 * n / tot_a
        share_p = 100.0 * previa.get(emo, 0) / tot_p
        delta = share_a - share_p
        if delta <= 0:
            continue
        if mejor is None or delta > mejor["delta_pp"]:
            mejor = {
                "emocion": emo,
                "etiqueta": ETIQUETAS_EMOCION.get(emo, emo),
                "n": int(n),
                "pct": round(share_a, 1),
                "pct_anterior": round(share_p, 1),
                "delta_pp": round(delta, 1),
                "es_nueva": previa.get(emo, 0) == 0,
            }
    return mejor


def _palabras_por_dimension(db, *, dias, campus, facultad, departamento, tema,
                            fecha_desde, fecha_hasta, nivel,
                            min_global=MIN_GLOBAL_PALABRA, min_local=MIN_LOCAL_PALABRA,
                            limite=LIMITE_PALABRAS_AREA):
    """({área: [palabras]}, {tema: [palabras]}) en UNA sola pasada del corpus.

    El vocabulario se valida GLOBALMENTE (ver la regla anti-PII arriba) y recién
    después se rankea dentro de cada área y cada tema. Una palabra que no llega al
    mínimo en todo el período no aparece en ningún corte, por más que en una
    facultad chica sea "la más dicha" — que es exactamente el caso de los handles
    de personas.

    Devuelve `({}, {})` si las tablas del corpus no existen (bases que solo tienen
    hechos, como las de los tests del índice).
    """
    try:
        fmax = _fmax_comentario(db)
        if fmax is None:
            return {}, {}
        col_area = {"facultad": Cu.facultad, "campus": Cu.campus,
                    "departamento": Cu.departamento}.get(nivel, Cu.facultad)
        filas = list(db.execute(
            _select_corpus(C.texto, S.sentimiento, col_area, C.tema).where(*_cond_corpus(
                fmax, dias=dias, campus=campus, facultad=facultad,
                departamento=departamento, tema=tema,
                fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
            )).limit(MAX_COMENTARIOS_TERMINOS)
        ))
    except Exception:
        return {}, {}

    glob: dict[str, dict] = {}
    por_area: dict[str, dict] = {}
    por_tema: dict[str, dict] = {}

    def _sumar(destino: dict, palabra: str, sent: str) -> None:
        a = destino.setdefault(palabra, {"n": 0, "n_pos": 0, "n_neu": 0, "n_neg": 0})
        a["n"] += 1
        a["n_pos" if sent == "POS" else "n_neg" if sent == "NEG" else "n_neu"] += 1

    for texto, sent, area, tm in filas:
        tokens = set(_tokenizar(texto))
        for palabra in tokens:
            _sumar(glob, palabra, sent)
            if area:
                _sumar(por_area.setdefault(area, {}), palabra, sent)
            if tm:
                _sumar(por_tema.setdefault(tm, {}), palabra, sent)

    voc = _vocabulario(glob, min_global)

    def _top(acc: dict) -> list[dict]:
        return sorted(
            (_fila_palabra(p, v) for p, v in acc.items()
             if p in voc and v["n"] >= min_local),
            key=lambda x: (-x["n"], -x["n_neg"], x["texto"]),
        )[:limite]

    return ({d: _top(a) for d, a in por_area.items()},
            {t: _top(a) for t, a in por_tema.items()})


def destacados(db, *, dias=30, campus=None, facultad=None, departamento=None, tema=None,
               peso_likes=1.0, fecha_desde=None, fecha_hasta=None,
               min_global=MIN_GLOBAL_PALABRA, limite=LIMITE_PALABRAS_RESUMEN) -> dict:
    """Lo que el RESUMEN muestra de un vistazo, en una sola llamada.

    Tres cosas que NO están en ninguna otra pestaña, para no repetir:
      * `palabras`: el vocabulario que más pesa (ordenado por negativos absolutos).
      * `serie_mensual`: la silueta del índice mes a mes.
      * `emocion_cambio`: qué emoción ganó terreno contra el período anterior.
    """
    # Las PALABRAS salen del corpus de textos y la serie/emoción de la tabla de
    # HECHOS. Se calculan por separado a propósito: una base puede tener una y no
    # la otra (los tests del índice solo siembran hechos; los del corpus, solo
    # comentarios) y un bloque no tiene por qué anular al otro.
    palabras: list[dict] = []
    try:
        fmax = _fmax_comentario(db)
        if fmax is not None:
            filas = db.execute(
                _select_corpus(C.texto, S.sentimiento).where(*_cond_corpus(
                    fmax, dias=dias, campus=campus, facultad=facultad,
                    departamento=departamento, tema=tema,
                    fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
                )).limit(MAX_COMENTARIOS_TERMINOS)
            )
            acc = _acumular_palabras(filas)
            palabras = sorted(
                (_fila_palabra(p, acc[p]) for p in _vocabulario(acc, min_global)),
                key=lambda x: (-x["n_neg"], -x["n"], x["texto"]),
            )[:limite]
    except Exception:
        palabras = []

    base = {"palabras": palabras, "serie_mensual": [], "emocion_cambio": None,
            "vocabulario_min": min_global, "periodo_anterior": None}
    r = _rango(db, dias, fecha_desde, fecha_hasta)
    if r is None:
        return base
    desde, hasta = r
    fmin = db.execute(select(func.min(H.fecha))).scalar_one_or_none()
    if fmin and desde < fmin:
        desde = fmin

    base["serie_mensual"] = _serie_mensual(
        db, desde, hasta, campus, facultad, departamento, tema, peso_likes)

    # Emoción que más creció contra la ventana INMEDIATAMENTE anterior del mismo
    # largo. Sin base previa no hay comparación posible y se informa como tal, en
    # vez de reportar todo como "nuevo este período", que sería falso.
    largo = max((hasta - desde).days, 1)
    prev_hasta = desde - timedelta(days=1)
    prev_desde = prev_hasta - timedelta(days=largo)
    if fmin and prev_hasta >= fmin:
        base["emocion_cambio"] = _emocion_que_mas_crecio(
            _emociones_ventana(db, desde, hasta, campus, facultad, departamento, tema),
            _emociones_ventana(db, prev_desde, prev_hasta, campus, facultad, departamento, tema),
        )
        base["periodo_anterior"] = {"desde": prev_desde, "hasta": prev_hasta}
    return base


def anomalias(db, *, dias=90, campus=None, facultad=None, departamento=None, tema=None,
              peso_likes=1.0, vida_media=VIDA_MEDIA_DIAS, limite=50,
              fecha_desde=None, fecha_hasta=None) -> dict:
    """Semanas que se apartan de su historia reciente, con el POR QUÉ.

    `fecha` es el LUNES de la semana marcada: la unidad de detección es la
    semana, no el día (el corpus tiene mediana de 5 comentarios diarios).
    `vida_media` se acepta por compatibilidad de la API pero no interviene: la
    detección corre sin decaimiento, justamente para no aplanar el evento.
    """
    serie = _deteccion_semanal(db, dias, campus, facultad, departamento, tema,
                               peso_likes, fecha_desde, fecha_hasta)
    dim = facultad or departamento or campus or "Global"
    items = [
        {
            "fecha": p["semana"],
            # Fin del bloque: la unidad es la quincena, así que un lunes suelto no
            # alcanza para saber qué período se está mirando.
            "fecha_fin": p.get("semana_fin"),
            "nivel": "filtrado", "dimension": dim,
            "indice": p["indice"], "z_score": p["z_score"],
            "z_indice": p["z_indice"], "z_pct_neg": p["z_pct_neg"],
            "pct_neg": p["pct_neg"], "n_comentarios": p["n"],
            "n_terminos": p["n_terminos"], "n_terminos_neg": p["n_terminos_neg"],
            "motivos": p["motivos"], "severidad": p["severidad"],
            # Los dos niveles y su horizonte medido. Ver el bloque de constantes:
            # `severidad` dice cuánto se apartó la semana, `nivel_alerta` dice qué
            # hacer con eso, y el lead dice con cuánta anticipación suele avisar.
            "nivel_alerta": p.get("nivel_alerta"),
            "lead_esperado_dias": p.get("lead_esperado_dias"),
            "lead_rango_dias": p.get("lead_rango_dias"),
            "cobertura_medida": p.get("cobertura_medida"),
        }
        # Una semana entra si es anomalía por severidad O si encendió un nivel: son
        # dos criterios distintos y el nivel puede prender sin llegar al umbral de
        # severidad (el %neg con z 2,0 aporta APORTE_DEBIL y solo no alcanza 0,5).
        # Sin este OR, el nivel ATENCIÓN —el que cubre 4 de 5 episodios— nunca se
        # vería en la pestaña Alertas.
        for p in serie if p["es_anomalia"] or p.get("nivel_alerta")
    ]
    # Primero ALERTA, después ATENCIÓN, después el resto; dentro de cada grupo por
    # severidad y fecha. Ordenar solo por severidad enterraba las alertas de léxico,
    # que son las más precisas pero no siempre las de severidad más alta.
    _ORDEN_NIVEL = {NIVEL_ALERTA: 2, NIVEL_ATENCION: 1}
    items.sort(key=lambda x: (_ORDEN_NIVEL.get(x["nivel_alerta"], 0),
                              x["severidad"], x["fecha"]), reverse=True)
    # La configuración viaja con los datos. `UNIDAD_DETECCION_SEMANAS` es ajustable
    # por entorno y cambia lo que se ve: sin declararla, dos personas con distinta
    # configuración leen números distintos y ninguna sabe por qué. Lo mismo con la
    # memoria y el umbral de muestra — son las tres perillas que mueven el resultado.
    return {
        "items": items[:limite],
        "config": {
            "unidad_semanas": UNIDAD_DETECCION_SEMANAS,
            "baseline_semanas": VENTANA_BASELINE_SEMANAS,
            "min_comentarios": MIN_N_SEMANA,
            # Lo que se midió con ESTA configuración, para que el panel no prometa
            # el rendimiento de otra. Solo hay medición para 1 y 2 semanas.
            "medicion": _MEDICION_POR_UNIDAD.get(UNIDAD_DETECCION_SEMANAS),
        },
    }


# Rendimiento MEDIDO por unidad, sobre los 8 episodios disruptivos del calendario
# (5 con ventana evaluable). Se guarda por unidad y no como un número suelto porque
# cambiar la perilla cambia el resultado: mostrar "5 de 5" cuando el tablero corre
# en modo semanal sería reportar el rendimiento de una configuración que no es la
# que el lector está mirando.
#
# Re-medir con `_verificar_alerta_percepcion.py` cuando crezca el corpus.
_MEDICION_POR_UNIDAD = {
    1: {"detecta": 4, "evaluables": 5, "falsas_anio": 0.9, "precision": 0.75,
        "lead_mediano": 34},
    2: {"detecta": 5, "evaluables": 5, "falsas_anio": 0.5, "precision": 0.83,
        "lead_mediano": 28},
}


def eventos(db, *, dias=120) -> dict:
    r = _rango(db, dias)
    if r is None:
        return {"items": []}
    desde, hasta = r
    filas = db.execute(
        select(Evento)
        .where(
            Evento.fecha_inicio <= hasta,
            func.coalesce(Evento.fecha_fin, Evento.fecha_inicio) >= desde,
        )
        .order_by(Evento.fecha_inicio)
    ).scalars().all()
    # `tipo_label` para que la UI muestre el nombre legible del tipo ("Vacaciones /
    # receso") en los toggles del gráfico, no la clave cruda ("receso"). Import local
    # para no acoplar el módulo de lectura con el de ABM en tiempo de carga.
    from app.services.percepcion.eventos import ETIQUETAS_TIPO

    return {
        "items": [
            {
                "id": e.id, "nombre": e.nombre, "tipo": e.tipo,
                "tipo_label": ETIQUETAS_TIPO.get(e.tipo, e.tipo),
                "fecha_inicio": e.fecha_inicio, "fecha_fin": e.fecha_fin or e.fecha_inicio,
                "descripcion": e.descripcion, "ambito": e.ambito,
                # `getattr` porque una base que todavía no corrió la migración de la
                # columna devuelve el modelo sin ella; el tablero no debe caerse por eso.
                "confianza": getattr(e, "confianza", None),
            }
            for e in filas
        ]
    }


_SENT_LABEL = {"POS": "Positivo", "NEU": "Neutral", "NEG": "Negativo"}


def _peso_likes(n_likes: int) -> float:
    """Mismo peso que la agregación: 1 + ln(1+likes). Rendimientos decrecientes."""
    return 1.0 + math.log1p(max(0, int(n_likes or 0)))


def comentarios_recientes(
    db, *, dias=30, campus=None, facultad=None, departamento=None, tema=None,
    limite=20, incluir_neutrales=False, sentimiento=None, emocion=None,
    fecha_desde=None, fecha_hasta=None,
) -> dict:
    """Comentarios reales que MÁS afectan la percepción reciente.

    Une comentario⋈score⋈publicación⋈cuenta, aplica el filtro global y ancla a la
    fecha más reciente presente. Se puede acotar por `sentimiento` (POS/NEU/NEG) y
    por `emocion` (joy/anger/…). Sin `sentimiento` explícito, excluye los NEUTRALES
    salvo `incluir_neutrales`. Ordena por impacto reciente; NUNCA devuelve el autor.

    Si se pasa `fecha_desde` y/o `fecha_hasta` (día puntual o rango), la ventana `dias`
    se IGNORA y se acota a ese intervalo de fechas — así el directivo lee "qué se decía
    en la comunidad" en ese hilo de tiempo (clic en el gráfico o selector Desde/Hasta).
    """
    fmax = db.execute(select(func.max(C.fecha_comentario))).scalar_one_or_none()
    if fmax is None:
        return {"items": []}

    cond: list = []
    if fecha_desde or fecha_hasta:
        # Rango EXPLÍCITO por fecha del comentario (fecha_hasta inclusive: < día siguiente).
        if fecha_desde:
            cond.append(C.fecha_comentario >= fecha_desde)
        if fecha_hasta:
            cond.append(C.fecha_comentario < fecha_hasta + timedelta(days=1))
    else:
        cond.append(C.fecha_comentario >= fmax - timedelta(days=dias))
    if campus:
        cond.append(Cu.campus == campus)
    if facultad:
        cond.append(Cu.facultad == facultad)
    if departamento:
        cond.append(Cu.departamento == departamento)
    if tema:
        cond.append(C.tema == tema)
    if sentimiento:
        cond.append(S.sentimiento == sentimiento)   # filtro explícito manda
    elif not incluir_neutrales:
        cond.append(S.sentimiento != "NEU")
    if emocion:
        cond.append(S.emocion == emocion)

    stmt = (
        select(
            C.id, C.texto, C.fecha_comentario, C.n_likes, C.tema,
            S.sentimiento, S.prob_pos, S.prob_neg, S.emocion,
            Cu.nombre, Cu.campus, Cu.facultad, Cu.departamento,
        )
        .join(S, S.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
        .where(*cond)
        # Orden en BD por recencia; el recorte fino se hace tras calcular impacto.
        .order_by(C.fecha_comentario.desc())
        .limit(max(limite * 5, 100))  # candidatos recientes; luego priorizamos impacto
    )

    etq = etiquetas_tema(db)
    items = []
    for cid, texto, fecha, likes, tm, sent, ppos, pneg, emo, nombre, camp, fac, depto in db.execute(stmt):
        neto = float(ppos or 0) - float(pneg or 0)
        items.append({
            "id": cid,
            "texto": texto,
            "fecha": fecha.date() if isinstance(fecha, datetime) else fecha,
            "sentimiento": sent,
            "sentimiento_label": _SENT_LABEL.get(sent, sent),
            "neto": round(neto, 3),
            "n_likes": int(likes or 0),
            "tema": tm,
            "tema_label": etq.get(tm, tm) if tm else None,
            "emocion": emo,
            "emocion_label": ETIQUETAS_EMOCION.get(emo, emo) if emo else None,
            "unidad": fac or depto or camp,
            "cuenta": nombre,
            "impacto": round(abs(neto) * _peso_likes(likes), 3),
        })
    # De los recientes, mostramos primero los que más afectan (impacto), y a igual
    # impacto los más nuevos. Así "recientes que están afectando".
    items.sort(key=lambda x: (x["impacto"], x["fecha"]), reverse=True)
    return {"items": items[:limite]}


def filtros(db) -> dict:
    etq = etiquetas_tema(db)

    def distintos(col):
        return sorted(v for (v,) in db.execute(select(col).distinct()) if v)

    # Span temporal REAL de los datos: del comentario más antiguo al más reciente.
    # El front usa `dias_span` como MÁXIMO del slider de rango (crece solo cuando
    # entran más datos); en ese máximo la ventana cubre todo el histórico.
    fmin, fmax = db.execute(select(func.min(H.fecha), func.max(H.fecha))).one()
    dias_span = (fmax - fmin).days if (fmin and fmax) else 0

    return {
        "sedes": distintos(H.campus),
        "facultades": distintos(H.facultad),
        "departamentos": distintos(H.departamento),
        "temas": [
            {"tema": t, "etiqueta": etq.get(t, t)} for t in distintos(H.tema)
        ],
        "fecha_min": fmin,
        "fecha_max": fmax,
        "dias_span": dias_span,
    }
