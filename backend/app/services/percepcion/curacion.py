"""Curación manual de temas: asignar a mano el tema de los comentarios/posts que
el clasificador dejó en "otros".

Es la ÚNICA parte de la Torre que ESCRIBE en la base del worker (vía el engine de
escritura). Tras cada asignación reconstruye la tabla de hechos para que el cambio
se refleje en TODO el dashboard (lista de comentarios Y gráficos por tema), no solo
en la lista.

⚠️ La reagregación replica la lógica del worker (aggregation/pipeline.agregar). Si
el worker cambia esa fórmula, hay que espejarla acá. La escritura es directa sobre
`tema`; si luego se re-clasifica TODO en el worker (reset tema=None), la curación
manual se pierde — correr la curación DESPUÉS de la clasificación automática.
"""
from __future__ import annotations

import math
import random
import re
import unicodedata
from datetime import datetime

from sqlalchemy import case, delete, func, inspect, select, update
from sqlalchemy.orm import Session

from app.services.percepcion import lexico
from app.services.percepcion.models import (
    AUTOR_HUMANO,
    MUESTRA_ADVERSOS,
    MUESTRA_ALEATORIA,
    MUESTRA_DUDA,
    MUESTRA_ESTRATIFICADA,
    ORIGEN_INTERNO,
)
from app.services.percepcion.models import PercepcionComentario as C
from app.services.percepcion.models import PercepcionCorreccion as Corr
from app.services.percepcion.models import PercepcionCuenta as Cu
from app.services.percepcion.models import PercepcionHechoDiario as H
from app.services.percepcion.models import PercepcionPublicacion as P
from app.services.percepcion.models import PercepcionScore as S
from app.services.percepcion.models import PercepcionTemaCustom as TC
from app.services.percepcion.postura import (  # noqa: F401  (re-export)
    ETIQUETAS_POSTURA,
    POSTURAS,
    postura_de,
    postura_valida,
)
from app.services.percepcion.repository import ETIQUETAS_EMOCION, ETIQUETAS_TEMA, _SENT_LABEL

TEMA_OTROS = "otros"


def _cap(caption: str | None, n: int = 160) -> str:
    """Recorte del caption para mostrar en la UI (ya viene limpio del worker)."""
    c = (caption or "").strip()
    return c[:n] + ("…" if len(c) > n else "")
# Temas FIJOS asignables (los 8 de la taxonomía, menos "otros").
# Temas RETIRADOS: siguen teniendo etiqueta para que los datos históricos aún sin
# re-clasificar no muestren la clave cruda, pero NO se ofrecen para asignar a mano.
TEMAS_RETIRADOS = {
    "eventos",
    # Fusionados el 2026-08-18: en comentarios de redes casi nadie habla de estos
    # temas (juntos eran 9 de 85 en la muestra anotada) y separados solo ensuciaban
    # la medición de los que sí tienen datos. Medido: acuerdo 51,8 % -> 55,3 %,
    # ventaja sobre la clase mayoritaria +29,4 -> +32,9 puntos.
    "charlas_seminarios", "infraestructura", "tramites",
    "matricula_aranceles", "difusion_admision",
}

_TEMAS_FIJOS = [
    {"tema": t, "etiqueta": e} for t, e in ETIQUETAS_TEMA.items()
    if t != TEMA_OTROS and t not in TEMAS_RETIRADOS
]


def _slug(texto: str) -> str:
    """Clave estable desde una etiqueta: minúsculas, sin tildes, guiones_bajos."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t[:40] or "tema"


def _norm_kw(k: str) -> str:
    t = unicodedata.normalize("NFKD", (k or "").lower().strip())
    return "".join(c for c in t if not unicodedata.combining(c))


def temas_asignables(db: Session) -> list[dict]:
    """Temas fijos + los CUSTOM creados a mano. Es lo que ofrece la UI de curación."""
    custom = [{"tema": c.clave, "etiqueta": c.etiqueta} for c in db.query(TC).order_by(TC.etiqueta).all()]
    return _TEMAS_FIJOS + custom


def tema_valido(db: Session, tema: str) -> bool:
    return any(t["tema"] == tema for t in temas_asignables(db))


def crear_tema_custom(db: Session, etiqueta: str, keywords: list[str]) -> dict:
    """Crea (o actualiza) un tema custom con sus keywords. El worker lo usará para
    clasificar en las próximas ingestas; acá ya queda asignable a mano."""
    etiqueta = (etiqueta or "").strip()
    if not etiqueta:
        raise ValueError("La etiqueta no puede estar vacía.")
    clave = _slug(etiqueta)
    if clave in ETIQUETAS_TEMA:
        raise ValueError(f"Ya existe un tema fijo con esa clave ({clave}).")
    kws = sorted({_norm_kw(k) for k in (keywords or []) if k and k.strip()})

    existente = db.query(TC).filter(TC.clave == clave).one_or_none()
    if existente is not None:
        existente.etiqueta = etiqueta
        existente.keywords = kws
    else:
        db.add(TC(clave=clave, etiqueta=etiqueta, keywords=kws, creado_en=datetime.utcnow()))
    db.commit()
    return {"tema": clave, "etiqueta": etiqueta, "keywords": kws}


def _peso_likes(n_likes: int) -> float:
    return 1.0 + math.log1p(max(0, int(n_likes or 0)))


def _tiene_columna(db: Session, tabla: str, columna: str) -> bool:
    """¿La BASE tiene esa columna? Se le pregunta al motor, no al modelo.

    La Torre es un espejo READ-ONLY del esquema del worker y puede estar corriendo
    contra una base anterior a una migración suya: `Base.metadata.create_all` crea
    TABLAS que faltan, nunca COLUMNAS. Comprobado sobre la operacional real
    (`backend/torre_control_ai.db`, sin `origen`): todas las lecturas del tablero
    siguen funcionando —ninguna pide la columna nueva— pero `reagregar()` moría
    con "no such column", y esa función la dispara CADA corrección manual.

    Ante la duda devuelve False: es preferible reagregar sin `origen` (el
    comportamiento anterior) que tumbar la curación entera.
    """
    try:
        return columna in {c["name"] for c in inspect(db.get_bind()).get_columns(tabla)}
    except Exception:
        return False


def reagregar(db: Session, *, confirmar: bool = True) -> int:
    """Reconstruye percepcion_hecho_diario desde comentario⋈score⋈cuenta. Idempotente.

    Espeja aggregation/pipeline.agregar del worker. Devuelve el nº de hechos.

    `confirmar=False` deja la transacción abierta (la sincronización con el worker la
    comparte con sus INSERT y confirma todo junto).

    ⚠️ EL GRANO INCLUYE `origen`. El worker agrupa por (fecha, ORIGEN, campus,
    facultad, depto, tema) y lo hereda de la cuenta (interno = ingesta UCN,
    externo = cuentas ajenas). Esta función hace `delete(H)` + reinsert, así que
    cualquier columna que NO se pase acá se pierde en TODA la tabla —y como cada
    corrección manual la llama, se pierde seguido.

    Ya pasó: las 894 filas de la base real quedaron con `origen` en NULL después
    de las 376 correcciones del 05-07/08/2026, mientras `percepcion_cuenta.origen`
    seguía en 'interno' (la Torre no reagrega cuentas). Se recompone derivándolo
    de la cuenta, que es de donde sale. Ver `_reparar_origen_percepcion.py`.

    Si el worker suma otra columna a la tabla de hechos, hay que espejarla ACÁ.
    """
    # Base anterior a la migración del worker: se reagrega SIN `origen`, igual que
    # antes, en vez de reventar. Ver `_tiene_columna`.
    con_origen = (_tiene_columna(db, "percepcion_cuenta", "origen")
                  and _tiene_columna(db, H.__tablename__, "origen"))

    db.execute(delete(H))
    columnas = [C.fecha_comentario]
    if con_origen:
        columnas.append(Cu.origen)
    columnas += [
        Cu.campus, Cu.facultad, Cu.departamento, C.tema, C.n_likes,
        S.sentimiento, S.prob_pos, S.prob_neu, S.prob_neg, S.emocion,
    ]
    stmt = (
        select(*columnas)
        .join(S, S.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
    )
    buckets: dict = {}
    for fila in db.execute(stmt):
        if con_origen:
            (fecha_dt, origen, campus, facultad, depto, tema, likes,
             sent, ppos, pneu, pneg, emo) = fila
        else:
            (fecha_dt, campus, facultad, depto, tema, likes,
             sent, ppos, pneu, pneg, emo) = fila
            origen = None
        # Cuenta anterior a la migración del worker: todo lo que ya estaba es
        # ingesta UCN por definición.
        origen = origen or ORIGEN_INTERNO
        clave = (fecha_dt.date(), origen, campus, facultad, depto, tema)
        acc = buckets.setdefault(clave, {
            "n": 0, "n_pos": 0, "n_neu": 0, "n_neg": 0, "suma_peso": 0.0,
            "peso_pos": 0.0, "peso_neg": 0.0, "suma_pos": 0.0, "suma_neg": 0.0,
            "suma_ganadora": 0.0, "emociones": {},
        })
        peso = _peso_likes(likes)
        ppos, pneu, pneg = float(ppos or 0), float(pneu or 0), float(pneg or 0)
        acc["n"] += 1
        acc["suma_peso"] += peso
        acc["peso_pos"] += peso * ppos
        acc["peso_neg"] += peso * pneg
        acc["suma_pos"] += ppos
        acc["suma_neg"] += pneg
        acc["suma_ganadora"] += max(ppos, pneu, pneg)
        if sent == "POS":
            acc["n_pos"] += 1
        elif sent == "NEG":
            acc["n_neg"] += 1
        else:
            acc["n_neu"] += 1
        if emo:
            acc["emociones"][emo] = acc["emociones"].get(emo, 0) + 1

    # INSERT por el CORE y no por el ORM: con `add_all(H(...))` SQLAlchemy arma el
    # INSERT desde el MODELO y mete `origen` con su default aunque no se lo pase,
    # así que en una base sin esa columna fallaba igual. Con el Core se insertan
    # solo las claves que están en el dict. De paso es un bulk insert, más rápido
    # que instanciar un objeto por fila.
    hechos = [
        {
            **({"origen": origen} if con_origen else {}),
            "fecha": fecha, "campus": campus, "facultad": facultad,
            "departamento": depto, "tema": tema,
            "n_comentarios": a["n"], "n_pos": a["n_pos"],
            "n_neu": a["n_neu"], "n_neg": a["n_neg"],
            "suma_peso": a["suma_peso"], "peso_pos": a["peso_pos"],
            "peso_neg": a["peso_neg"], "suma_pos": a["suma_pos"],
            "suma_neg": a["suma_neg"], "suma_ganadora": a["suma_ganadora"],
            "emociones": dict(a["emociones"]) or None,
        }
        for (fecha, origen, campus, facultad, depto, tema), a in buckets.items()
    ]
    if hechos:
        db.execute(H.__table__.insert(), hechos)
    if confirmar:
        db.commit()
    return len(hechos)


def publicaciones_a_curar(db: Session, *, solo_con_otros: bool = True, limite: int = 100) -> dict:
    """Posts con conteo de comentarios y cuántos siguen en 'otros' (para curar en masa)."""
    n_otros = func.sum(case((C.tema == TEMA_OTROS, 1), else_=0))
    stmt = (
        select(P.id, P.caption, Cu.nombre, func.count(C.id), n_otros)
        .join(Cu, Cu.id == P.cuenta_id)
        .join(C, C.publicacion_id == P.id)
        # PG exige agrupar por TODA columna no agregada que no dependa de la clave: `Cu.nombre`
        # depende de `Cu.id`, no de `P.id`. SQLite lo toleraba (columna "desnuda").
        .group_by(P.id, Cu.id)
    )
    items = []
    for pid, caption, cuenta, n_com, n_ot in db.execute(stmt):
        n_ot = int(n_ot or 0)
        if solo_con_otros and n_ot == 0:
            continue
        items.append({
            "id": pid,
            "caption": _cap(caption),
            "cuenta": cuenta,
            "n_comentarios": int(n_com or 0),
            "n_otros": n_ot,
        })
    # Desempate por `id`: sin él, qué filas empatadas entran al `limite` lo decide el motor
    # (SQLite y Postgres elegían distinto) y la cola de curación cambiaba de una base a otra.
    items.sort(key=lambda x: (-x["n_otros"], x["id"]))
    return {"items": items[:limite]}


def comentarios_a_curar(db: Session, *, limite: int = 100) -> dict:
    """Comentarios que siguen en 'otros' (para asignar tema uno por uno)."""
    stmt = (
        select(C.id, C.texto, C.fecha_comentario, S.sentimiento, P.caption, Cu.nombre)
        .join(S, S.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
        .where(C.tema == TEMA_OTROS)
        .order_by(C.fecha_comentario.desc())
        .limit(limite)
    )
    items = [
        {
            "id": cid, "texto": texto, "fecha": fecha.date(),
            "sentimiento": sent, "caption": _cap(caption),
            "cuenta": cuenta,
        }
        for cid, texto, fecha, sent, caption, cuenta in db.execute(stmt)
    ]
    return {"items": items}


def asignar_tema_publicacion(db: Session, pub_id: int, tema: str) -> dict:
    """Asigna `tema` a los comentarios 'otros' de un post (heredan) y reagrega."""
    res = db.execute(
        update(C).where(C.publicacion_id == pub_id, C.tema == TEMA_OTROS)
        .values(tema=tema, tema_confianza=1.0)  # 1.0 = curado a mano (certeza humana)
    )
    db.commit()
    n_hechos = reagregar(db)
    return {"comentarios_actualizados": res.rowcount, "hechos": n_hechos}


def asignar_tema_comentario(db: Session, com_id: int, tema: str) -> dict:
    """Asigna `tema` a un comentario puntual y reagrega."""
    res = db.execute(
        update(C).where(C.id == com_id).values(tema=tema, tema_confianza=1.0)
    )
    db.commit()
    n_hechos = reagregar(db)
    return {"comentarios_actualizados": res.rowcount, "hechos": n_hechos}


# --------------------------------------------------------------------------- #
# Corrección de SENTIMIENTO / EMOCIÓN (dataset de aprendizaje humano).
# --------------------------------------------------------------------------- #
# Al corregir a mano, el score toma la certeza humana (prob ~0.9) y se guarda la
# corrección + justificación en percepcion_correccion (dataset para reglas/fine-tuning).
_PROBS_SENT = {"POS": (0.90, 0.05, 0.05), "NEU": (0.05, 0.90, 0.05), "NEG": (0.05, 0.05, 0.90)}
SENTIMIENTOS = [{"valor": v, "etiqueta": _SENT_LABEL[v]} for v in ("POS", "NEU", "NEG")]
EMOCIONES = [{"valor": k, "etiqueta": e} for k, e in ETIQUETAS_EMOCION.items()]


def sentimiento_valido(s: str) -> bool:
    return s in _PROBS_SENT


def emocion_valida(e: str) -> bool:
    return e in ETIQUETAS_EMOCION


# Semilla fija: dos personas que pidan la muestra aleatoria tienen que recibir LOS
# MISMOS comentarios, o no están anotando el mismo conjunto y el acuerdo entre
# anotadores no significa nada.
SEMILLA_MUESTRA = 20260811

# Los cuatro campos que se anotan a mano en la cola de revision.
CAMPOS_REVISION = ("sentimiento", "emocion", "tema", "postura")

# CRITERIO DE TEMA VIGENTE. Las anotaciones de `tema` anteriores a esta fecha se
# hicieron con OTRO criterio y no cuentan como revisadas: hay que rehacerlas.
#
# El 19-08-2026 el dueño del dominio fijó que **un post que DESTACA A UNA PERSONA
# es `logros_reconocimientos`, aunque la persona sea académica**. Antes de eso el
# tema salía de qué trataba el contenido, así que "Conversamos con Pamela Meneses,
# periodista egresada" se anotaba `academico` y ahora se anota `logros`.
#
# ⚠️ NO es un detalle administrativo: medido sobre los 135 comentarios anotados más
# de una vez, 42 cambiaron de etiqueta y 31 de esos 42 migraron a `logros`. Mezclar
# los dos criterios hace que la métrica de tema no signifique nada — se comprobó que
# mover el vocabulario hacia el criterio nuevo sube el acuerdo de lo nuevo (+6,2) y
# lo baja en lo viejo (−6,4) en la misma proporción. Son incompatibles.
#
# Si el criterio vuelve a cambiar, mover esta fecha; no borrar las anotaciones
# viejas, que son la evidencia de que el criterio cambió.
CRITERIO_TEMA_DESDE = datetime(2026, 8, 19)


def comentarios_completos(db: Session) -> set[int]:
    """IDs cuya revision manual YA ESTA TERMINADA: tienen anotacion humana vigente
    en los cuatro campos y su tema sigue existiendo en la taxonomia.

    Un comentario cuyo ultimo tema humano quedo en un tema RETIRADO (`eventos`,
    `infraestructura`, ...) NO cuenta como completo: hay que volver a preguntarle
    al revisor, porque la etiqueta que puso ya no significa nada. Lo mismo con las
    anotaciones anteriores a `CRITERIO_TEMA_DESDE`, hechas con otro criterio.
    """
    return {cid for cid, motivo in estado_revision(db).items() if motivo is None}


def estado_revision(db: Session) -> dict[int, str | None]:
    """Por cada comentario ya tocado a mano: POR QUÉ sigue pendiente (None = listo).

    Existe para poder decirlo en pantalla. Sin el motivo a la vista, una cola que
    devuelve comentarios ya anotados se lee como "está rota" — y de hecho eso pasó:
    los primeros ~96 lugares de la permutación son justo los que se anotaron el
    14-08 con el criterio anterior, así que la cola arrancaba con una pantalla
    entera de caras conocidas y sin ninguna explicación.
    """
    ultimos: dict[int, dict[str, tuple[str, datetime | None]]] = {}
    sub = (
        select(func.max(Corr.id))
        .where(Corr.autor_tipo == AUTOR_HUMANO, Corr.campo.in_(CAMPOS_REVISION))
        .group_by(Corr.comentario_id, Corr.campo)
    )
    for cid, campo, valor, cuando in db.execute(
        select(Corr.comentario_id, Corr.campo, Corr.valor_nuevo, Corr.creado_en)
        .where(Corr.id.in_(sub))
    ):
        ultimos.setdefault(cid, {})[campo] = (valor, cuando)

    def _motivo(campos: dict[str, tuple[str, datetime | None]]) -> str | None:
        faltan = [c for c in CAMPOS_REVISION if c not in campos]
        if faltan:
            return "falta anotar " + ", ".join(faltan)
        tema, cuando = campos["tema"]
        if tema in TEMAS_RETIRADOS:
            return f"el tema «{tema}» se retiró de la taxonomía"
        if cuando is None or cuando < CRITERIO_TEMA_DESDE:
            return "el tema se anotó con el criterio anterior"
        return None

    return {cid: _motivo(campos) for cid, campos in ultimos.items()}


# Puntaje de "candidato a adverso". No es una predicción: es una PRIORIDAD de
# revisión. Cada rasgo suma por un motivo medido y distinto:
#
#   +3  el comentario NOMBRA el conflicto (paro, toma, asamblea…). Es la señal más
#       precisa del módulo — 86 % cuando dispara— y si además el tono es POSITIVO,
#       estamos ante el caso «¿Paro? 😍»: tono positivo, postura adversa. Ese es
#       exactamente el caso que hoy no se puede detectar y que hay que anotar.
#   +2  la PUBLICACIÓN es de conflicto. Hay 264 comentarios así, muchos más que los
#       9 que nombran el conflicto en su propio texto. Pesa menos porque incluye a
#       los de apoyo (por eso "conflicto en el caption → adverso" se descartó como
#       regla), pero como cola de revisión es justo donde hay que mirar.
#   +2  el tono es POSITIVO o NEUTRAL. Los NEG ya son adversos por regla y anotarlos
#       confirma lo obvio; lo que falta calibrar es el otro lado.
#   +1  cuenta de FEDERACIÓN. Medido: índice 32,4 y 37 % de negativos, contra 71,8
#       de las cuentas de facultad. Es donde el conflicto se conversa.
#
# El orden es descendente por puntaje y, a igualdad, por fecha reciente.
_PUNTOS_LEXICO_COMENTARIO = 3
_PUNTOS_LEXICO_CAPTION = 2
_PUNTOS_NO_NEGATIVO = 2
_PUNTOS_CUENTA_FEDERACION = 1
CUENTA_CONFLICTO = "federacion"


def _puntaje_adverso(sentimiento, texto, caption, tipo_cuenta) -> int:
    p = 0
    if lexico.detectar(texto):
        p += _PUNTOS_LEXICO_COMENTARIO
    if lexico.detectar(caption):
        p += _PUNTOS_LEXICO_CAPTION
    if (sentimiento or "").upper() != "NEG":
        p += _PUNTOS_NO_NEGATIVO
    if tipo_cuenta == CUENTA_CONFLICTO:
        p += _PUNTOS_CUENTA_FEDERACION
    return p


ESTRATO_RICO = "rico"
ESTRATO_POBRE = "pobre"
# Puntaje a partir del cual un comentario entra al estrato RICO en adversos. Es el
# mismo corte que usa `_cola_adversos` (`> _PUNTOS_NO_NEGATIVO`), a propósito: si los
# dos criterios se separan, el estrato deja de describir a la cola que lo produjo.
CORTE_ESTRATO = _PUNTOS_NO_NEGATIVO + 1
# Qué fracción de la muestra sale del estrato rico. Con 0,7 hacen falta ~105
# anotaciones para llegar a 50 adversos, contra 227 al azar. No se sube más porque el
# estrato pobre es el 91 % del corpus y necesita muestra propia: sin ella su tasa no
# se puede estimar y el re-pesado se queda sin uno de sus dos términos.
FRACCION_ESTRATO_RICO = 0.7


def _estrato_de(sentimiento, texto, caption, tipo_cuenta) -> str:
    """A qué estrato pertenece un comentario, según su puntaje de candidato adverso."""
    p = _puntaje_adverso(sentimiento, texto, caption, tipo_cuenta)
    return ESTRATO_RICO if p >= CORTE_ESTRATO else ESTRATO_POBRE


def repesar_por_estrato(muestra: dict[str, tuple[int, int]],
                        tamanos: dict[str, int]) -> float | None:
    """Estimación INSESGADA de una proporción a partir de una muestra estratificada.

    `muestra` es {estrato: (anotados, casos_que_cumplen)} y `tamanos` {estrato: N en
    el corpus}. Devuelve `Σ_e (N_e/N) · p̂_e`.

    Por qué no alcanza el promedio simple: la cola estratificada sobremuestrea el
    estrato rico A PROPÓSITO, así que contar todo junto sobreestima. Con un corpus de
    100 ricos al 50 % y 900 pobres al 10 % —tasa real 14 %—, anotar 50 de cada uno y
    promediar da 30 %. Re-pesando da 14 %. Hay un test con exactamente ese caso.

    Devuelve None si algún estrato quedó SIN ANOTAR: sin su p̂ no hay forma honesta de
    completar la suma, y rellenarlo con el promedio de los otros sería inventar el
    número que justamente se quería estimar.
    """
    if not muestra:
        return None
    total = sum(tamanos.get(e, 0) for e in muestra)
    if total <= 0:
        # Todos los estratos con tamaño 0 declarado: se cae al promedio simple, que
        # es lo correcto cuando no hay información de tamaños con la cual pesar.
        n = sum(a for a, _ in muestra.values())
        return (sum(k for _, k in muestra.values()) / n) if n else None
    acc = 0.0
    for estrato, (anotados, aciertos) in muestra.items():
        peso = tamanos.get(estrato, 0)
        if peso <= 0:
            continue
        if anotados <= 0:
            return None            # estrato sin muestra: la estimación no se puede afirmar
        acc += (peso / total) * (aciertos / anotados)
    return acc


def _cola_estratificada(db, stmt, cond, completos, limite, semilla):
    """Muestra aleatoria DENTRO de cada estrato, con el rico sobrerrepresentado.

    Es aleatoria dentro del estrato —no ordenada por puntaje como `_cola_adversos`—
    y eso es lo que la hace estimable: dentro de un estrato cada comentario tiene la
    misma probabilidad de salir, así que su tasa observada estima la del estrato.
    """
    candidatos = db.execute(
        select(C.id, S.sentimiento, C.texto, P.caption, Cu.tipo)
        .join(S, S.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
        .where(*cond)
    ).all()
    por_estrato: dict[str, list[int]] = {ESTRATO_RICO: [], ESTRATO_POBRE: []}
    for cid, sent, texto, caption, tipo in candidatos:
        if cid in completos:
            continue
        por_estrato[_estrato_de(sent, texto, caption, tipo)].append(cid)

    rnd = random.Random(semilla)
    elegidos: set[int] = set()
    cupo = {ESTRATO_RICO: round(limite * FRACCION_ESTRATO_RICO)}
    cupo[ESTRATO_POBRE] = limite - cupo[ESTRATO_RICO]
    # El rico primero: si no llena su cupo, lo que sobra va al pobre y no se
    # desperdicia el pedido. Al revés no sirve — el pobre siempre tiene de sobra y
    # se comería la muestra entera.
    for estrato in (ESTRATO_RICO, ESTRATO_POBRE):
        ids = sorted(por_estrato[estrato])
        rnd.shuffle(ids)
        faltan = limite - len(elegidos)
        elegidos.update(ids[:min(cupo[estrato] + max(0, faltan - sum(
            len(por_estrato[e]) for e in por_estrato if e != estrato)), faltan)])
    return list(db.execute(stmt.where(C.id.in_(elegidos)))) if elegidos else []


def _cola_adversos(db, stmt, cond, completos, limite):
    """Comentarios con más chance de ser ADVERSOS y de que la regla los erre.

    Por qué hace falta: el lado adverso de la regla de postura tiene solo 21
    ejemplos humanos, y anotar al azar no lo arregla —el adverso es el 8,5 % del
    corpus, así que 100 comentarios aleatorios dan ~8—. Esta cola concentra el
    trabajo donde rinde.

    ⚠️ Al estar dirigida, lo anotado acá NO sirve para estimar la calidad global.
    Ver `MUESTRA_ADVERSOS` en `models.py`.
    """
    candidatos = db.execute(
        select(C.id, S.sentimiento, C.texto, P.caption, Cu.tipo, C.fecha_comentario)
        .join(S, S.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
        .where(*cond)
    ).all()
    puntuados = []
    for cid, sent, texto, caption, tipo, fecha in candidatos:
        if cid in completos:
            continue
        p = _puntaje_adverso(sent, texto, caption, tipo)
        # Sin ninguna señal no es candidato: servirlo sería una cola aleatoria con
        # otro nombre, y la persona que anota perdería el tiempo.
        if p <= _PUNTOS_NO_NEGATIVO:
            continue
        puntuados.append((p, fecha, cid))
    # Descendente por puntaje; a igualdad, lo más reciente primero.
    puntuados.sort(key=lambda t: (t[0], t[1] or datetime.min), reverse=True)
    elegidos = {cid for _, _, cid in puntuados[:limite]}
    return list(db.execute(stmt.where(C.id.in_(elegidos)))) if elegidos else []


def comentarios_para_scoring(
    db: Session, *, limite: int = 50, sentimiento: str | None = None,
    emocion: str | None = None, orden: str = MUESTRA_DUDA,
    semilla: int = SEMILLA_MUESTRA, solo_pendientes: bool = True,
) -> dict:
    """Comentarios con su sentimiento/emoción actual, para revisar y corregir a mano.

    Tres órdenes, y la diferencia entre ellos NO es cosmética — determina para qué
    sirve lo que se anote:

    * `duda` (default): por INCERTIDUMBRE del modelo, primero donde la clase
      ganadora le sacó poca ventaja a la segunda. Es donde el trabajo de revisión
      RINDE más... y por eso mismo **no sirve para medir**: la muestra está elegida
      justo donde el modelo es peor, así que el acuerdo medido ahí es un piso.
    * `reciente`: por fecha, el comportamiento original.
    * `aleatorio`: muestra SIN SESGO sobre todo el corpus, con semilla fija para que
      sea reproducible entre revisores. **Es el único orden con el que se puede
      estimar la calidad real del modelo.**

    `solo_pendientes` (default True) SALTEA lo que ya está revisado del todo (los
    cuatro campos anotados y el tema todavía vigente, ver `comentarios_completos`).

    ⚠️ SIN ESTO LA COLA NO AVANZA NUNCA. La semilla es fija y el corte era
    `ids[:limite]`, o sea el mismo prefijo de la misma permutación en cada request:
    se anotaba, se guardaba, se recargaba y volvían LOS MISMOS comentarios. Medido
    el 19-08-2026: de 109 comentarios revisados ese día, **0 eran nuevos**, y había
    comentarios anotados hasta 8 veces. La semilla fija se mantiene —es lo que hace
    comparable la muestra entre revisores—; lo que se corrige es CONSUMIR la
    permutación en vez de mirarle siempre la cabeza. La muestra sigue siendo
    insesgada: un prefijo de una permutación fija lo es, se corte donde se corte.

    El `caption` de la publicación viaja con cada comentario. No es decoración: la
    mediana del corpus es de 3 palabras y el 56% tiene 3 o menos. "no yapo" no se
    puede clasificar sin ver a qué está respondiendo — las auditorías v4/v9 ya
    habían llegado a esa conclusión por su cuenta y lo dejaron escrito en sus
    justificaciones ("caption de publicacion").
    """
    cond = []
    if sentimiento:
        cond.append(S.sentimiento == sentimiento)
    if emocion:
        cond.append(S.emocion == emocion)

    stmt = (
        select(
            C.id, C.texto, C.fecha_comentario, C.tema, C.tema_confianza,
            S.sentimiento, S.emocion, Cu.nombre,
            S.prob_pos, S.prob_neu, S.prob_neg, P.caption,
        )
        .join(S, S.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(Cu, Cu.id == P.cuenta_id)
        .where(*cond)
    )

    # Lo ya terminado no se vuelve a servir. Ver `solo_pendientes` en el docstring:
    # sin esto la cola aleatoria devuelve SIEMPRE el mismo prefijo de la permutación.
    motivos = estado_revision(db)
    completos = {c for c, m in motivos.items() if m is None} if solo_pendientes else set()
    total_corpus = db.execute(
        select(func.count()).select_from(C).join(S, S.comentario_id == C.id)
    ).scalar_one()

    if orden == MUESTRA_ADVERSOS:
        filas = _cola_adversos(db, stmt, cond, completos, limite)
    elif orden == MUESTRA_ESTRATIFICADA:
        filas = _cola_estratificada(db, stmt, cond, completos, limite, semilla)
    elif orden == MUESTRA_ALEATORIA:
        # Se sortean los IDS y recién después se traen las filas: barajar en Python
        # el corpus entero traería 2.790 registros para descartar 2.640.
        ids = [r[0] for r in db.execute(
            select(C.id).join(S, S.comentario_id == C.id).where(*cond).order_by(C.id)
        )]
        random.Random(semilla).shuffle(ids)
        ids = [i for i in ids if i not in completos]
        elegidos = set(ids[:limite])
        filas = list(db.execute(stmt.where(C.id.in_(elegidos)))) if elegidos else []
    else:
        # El margen se calcula en Python (no en SQL): son tres columnas y hay que
        # ordenar dos de ellas por fila, algo que en SQLite se vuelve ilegible. Para
        # no traer la tabla entera se toma una ventana amplia de los más recientes y
        # se prioriza dentro de ella.
        ventana = max(limite * 20, 500) if orden == MUESTRA_DUDA else limite
        if completos:
            ventana += len(completos)  # se descartan después: hay que traer de más
        filas = [f for f in db.execute(stmt.order_by(C.fecha_comentario.desc()).limit(ventana))
                 if f[0] not in completos]

    items = []
    for cid, texto, fecha, tema, tema_conf, sent, emo, cuenta, ppos, pneu, pneg, caption in filas:
        probs = sorted(
            (float(ppos or 0), float(pneu or 0), float(pneg or 0)), reverse=True
        )
        margen = round(probs[0] - probs[1], 3)
        items.append({
            "id": cid, "texto": texto, "fecha": fecha.date(),
            "sentimiento": sent, "sentimiento_label": _SENT_LABEL.get(sent, sent),
            "emocion": emo, "emocion_label": ETIQUETAS_EMOCION.get(emo, emo) if emo else None,
            "tema": tema, "cuenta": cuenta,
            # Confianza del matcher de keywords. Mediana del corpus: 0,45.
            "tema_confianza": round(float(tema_conf or 0), 3),
            "caption": _cap(caption),
            # Por qué sigue en la cola. None = nunca se tocó.
            "motivo_pendiente": motivos.get(cid),
            "margen": margen,
            "prob_pos": round(float(ppos or 0), 3),
            "prob_neu": round(float(pneu or 0), 3),
            "prob_neg": round(float(pneg or 0), 3),
        })

    if orden == MUESTRA_DUDA:
        items.sort(key=lambda i: i["margen"])
    elif orden == MUESTRA_ALEATORIA:
        # `in_()` no garantiza orden; se reordena por id para que la muestra sea
        # estable entre llamadas y dos revisores vean lo mismo en la misma posición.
        items.sort(key=lambda i: i["id"])
    # `pendientes` es lo que hacía falta para NOTAR que la cola no avanzaba: sin un
    # contador en pantalla, revisar los mismos comentarios una y otra vez se ve
    # exactamente igual que revisar comentarios nuevos.
    return {
        "items": items[:limite],
        "orden": orden,
        "revisados": len(completos),
        "pendientes": max(0, total_corpus - len(completos)),
    }


def _marcar_manual(sc) -> None:
    if sc.modelo and "correccion_manual" not in sc.modelo:
        sc.modelo = f"{sc.modelo}+correccion_manual"


MARCA_MANUAL = "correccion_manual"


def _ya_corregido(sc) -> bool:
    """¿Este score ya fue pisado por una corrección anterior?

    Importa porque sus `prob_*` ya NO son las del modelo: son los sintéticos de
    `_PROBS_SENT`. Snapshotearlas otra vez guardaría 0,90/0,05/0,05 como si fuera
    la salida original, que es exactamente la manera de perder el dato dos veces.
    """
    return MARCA_MANUAL in (sc.modelo or "")


def _snapshot_modelo(db: Session, com_id: int, sc) -> dict:
    """Salida ORIGINAL del modelo para este comentario, para congelarla en la corrección.

    Tres casos:
      * score limpio  -> se toma del score, que todavía tiene lo que dijo el modelo.
      * score ya pisado -> se REUSA el snapshot de la primera corrección de ese
        comentario. Sin esto, la segunda corrección sobre el mismo comentario
        guardaría los sintéticos y borraría la única copia buena.
      * score pisado y sin snapshot previo -> no hay de dónde sacarlo (son las 262
        filas de la base real anteriores a este cambio). Se devuelve vacío y lo
        rellena `_rescatar_probs_percepcion.py` desde el respaldo pre-auditoría.
    """
    if not _ya_corregido(sc):
        return {
            "modelo_orig": sc.modelo,
            "prob_pos_orig": sc.prob_pos,
            "prob_neu_orig": sc.prob_neu,
            "prob_neg_orig": sc.prob_neg,
            "prob_emocion_orig": sc.prob_emocion,
        }
    previo = db.execute(
        select(Corr).where(Corr.comentario_id == com_id, Corr.modelo_orig.isnot(None))
        .order_by(Corr.id).limit(1)
    ).scalars().first()
    if previo is None:
        return {}
    return {
        "modelo_orig": previo.modelo_orig,
        "prob_pos_orig": previo.prob_pos_orig,
        "prob_neu_orig": previo.prob_neu_orig,
        "prob_neg_orig": previo.prob_neg_orig,
        "prob_emocion_orig": previo.prob_emocion_orig,
    }


def _extras_correccion(db: Session, com_id: int, sc, *, cambiado: bool,
                       autor_tipo: str | None, origen_muestra: str | None) -> dict:
    """Campos nuevos de la corrección, omitidos si la base es anterior a la migración.

    `db._asegurar_columnas()` los agrega al arrancar, pero una base de solo lectura
    o sin permisos de ALTER puede no tenerlos. Igual que con `origen`, se degrada al
    comportamiento anterior en vez de tumbar la curación entera.
    """
    if not _tiene_columna(db, Corr.__tablename__, "confirmado"):
        return {}
    return {
        "confirmado": not cambiado,
        "autor_tipo": autor_tipo or AUTOR_HUMANO,
        "origen_muestra": origen_muestra,
        **_snapshot_modelo(db, com_id, sc),
    }


def _insertar_correccion(db: Session, fila: dict) -> None:
    """INSERT por el CORE, no por el ORM.

    Misma razón que en `reagregar()`: con `db.add(Corr(...))` SQLAlchemy arma el
    INSERT desde el MODELO e incluye TODAS las columnas mapeadas —aunque no se les
    haya pasado valor—, así que contra una base sin migrar reventaba con
    "table percepcion_correccion has no column named confirmado". Con el Core se
    insertan solo las claves del dict, que es lo que `_extras_correccion` decide.
    """
    db.execute(Corr.__table__.insert(), [fila])


def corregir_sentimiento(
    db: Session, com_id: int, sentimiento: str, justificacion: str, autor: str | None,
    *, autor_tipo: str | None = None, origen_muestra: str | None = None,
) -> dict:
    """Revisa el sentimiento de un comentario, deja constancia y reagrega.

    Registra SIEMPRE, cambie o no. Confirmar que el modelo acertó es un dato tan
    necesario como corregirlo: sin las confirmaciones no hay denominador y el
    accuracy no se puede calcular (en la base real, 266 de 266 filas eran cambios).

    La salida original del modelo se congela en la corrección ANTES de pisar el
    score, que es lo que permite recalibrar después.
    """
    sc = db.query(S).filter(S.comentario_id == com_id).one_or_none()
    if sc is None:
        raise ValueError("El comentario no tiene score.")
    original = sc.sentimiento
    cambiado = original != sentimiento
    extras = _extras_correccion(db, com_id, sc, cambiado=cambiado,
                                autor_tipo=autor_tipo, origen_muestra=origen_muestra)
    if cambiado:
        sc.prob_pos, sc.prob_neu, sc.prob_neg = _PROBS_SENT[sentimiento]
        sc.sentimiento = sentimiento
        _marcar_manual(sc)
    _insertar_correccion(db, {
        "comentario_id": com_id, "campo": "sentimiento", "valor_original": original,
        "valor_nuevo": sentimiento,
        "justificacion": (justificacion or "").strip() or None,
        "autor": autor, "creado_en": datetime.utcnow(), **extras,
    })
    db.commit()
    # Confirmar no cambia ningún hecho: no hay por qué reconstruir 894 filas.
    return {"cambiado": cambiado, "hechos": reagregar(db) if cambiado else 0}


def corregir_emocion(
    db: Session, com_id: int, emocion: str, justificacion: str, autor: str | None,
    *, autor_tipo: str | None = None, origen_muestra: str | None = None,
) -> dict:
    """Revisa la emoción de un comentario, deja constancia y reagrega. Ver `corregir_sentimiento`."""
    sc = db.query(S).filter(S.comentario_id == com_id).one_or_none()
    if sc is None:
        raise ValueError("El comentario no tiene score.")
    original = sc.emocion
    cambiado = original != emocion
    extras = _extras_correccion(db, com_id, sc, cambiado=cambiado,
                                autor_tipo=autor_tipo, origen_muestra=origen_muestra)
    if cambiado:
        sc.emocion = emocion
        sc.prob_emocion = 1.0
        _marcar_manual(sc)
    _insertar_correccion(db, {
        "comentario_id": com_id, "campo": "emocion", "valor_original": original,
        "valor_nuevo": emocion,
        "justificacion": (justificacion or "").strip() or None,
        "autor": autor, "creado_en": datetime.utcnow(), **extras,
    })
    db.commit()
    return {"cambiado": cambiado, "hechos": reagregar(db) if cambiado else 0}


# --------------------------------------------------------------------------- #
# POSTURA — sentimiento y postura NO son lo mismo.
# --------------------------------------------------------------------------- #
# El scorer mide el TONO del comentario y lo mide bien: «Paro?😍» ES positivo en
# tono. Pero el tablero se llama "percepción de la comunidad" y se lee como «¿cómo
# está la UCN?», que es una pregunta de POSTURA — y en eso «Paro?😍» es adverso.
#
# Medido sobre la base real: de 141 comentarios en publicaciones de CONFLICTO,
# **33 (23%) están marcados POSITIVO**. El léxico de términos críticos captura solo
# 4 de esos casos: sub-captura el fenómeno por ocho veces.
#
# Ya se había topado antes sin nombrarlo: durante el paro de 2026 el índice SUBIÓ
# (51,9 → 67) porque las cuentas de federación reciben comentarios de apoyo.
#
# DECISIÓN: postura va como dimensión SEPARADA y anotable. NO se toca el índice de
# sentimiento — meterla adentro perdería comparabilidad con todo lo presentado y
# volvería a fusionar dos constructos, solo que al revés.
# La regla y sus etiquetas viven en `postura.py`, con la medición que las justifica.
# Se re-exportan acá porque el router y la UI ya las importaban desde este módulo.

# ⚠️ `POSTURA_DESDE_SENTIMIENTO` (el mapeo ingenuo tono→postura) fue la regla hasta
# el 19-08-2026 y se conserva SOLO como referencia histórica: es el `valor_original`
# de las correcciones anteriores a esa fecha, y sin él esas filas no se pueden
# interpretar. La regla vigente es `postura.postura_de`, que además mira el tema y
# acierta 80,7 % contra 66,7 % de esta.
POSTURA_DESDE_SENTIMIENTO = {"POS": "favorable", "NEU": "neutral", "NEG": "adverso"}


def corregir_postura(
    db: Session, com_id: int, postura: str, justificacion: str, autor: str | None,
    *, autor_tipo: str | None = None, origen_muestra: str | None = None,
) -> dict:
    """Anota la POSTURA de un comentario hacia la institución.

    El `valor_original` es lo que dice la REGLA VIGENTE (`postura.postura_de`), así
    lo que se mide es cuánto le erra esa regla — igual que con el sentimiento.

    ⚠️ Cambió el 19-08-2026. Antes el `valor_original` era el mapeo ingenuo
    tono→postura; ahora la regla también mira el tema. Las correcciones anteriores
    a esa fecha miden la regla VIEJA, así que no se pueden promediar con las nuevas
    para estimar el error de la regla actual.

    NO toca `percepcion_score` ni reagrega: la postura se DERIVA de tono + tema, así
    que los agregados salen de la tabla de hechos sin guardar nada (ver
    `postura.contar_por_postura`). No hay estado que mantener sincronizado.
    """
    sc = db.query(S).filter(S.comentario_id == com_id).one_or_none()
    if sc is None:
        raise ValueError("El comentario no tiene score.")
    tema = db.execute(select(C.tema).where(C.id == com_id)).scalar_one_or_none()
    ingenua = postura_de(sc.sentimiento, tema)
    cambiado = ingenua != postura

    extras: dict = {}
    if _tiene_columna(db, Corr.__tablename__, "confirmado"):
        extras = {
            "confirmado": not cambiado,
            "autor_tipo": autor_tipo or AUTOR_HUMANO,
            "origen_muestra": origen_muestra,
            # El tono del que salió la suposición, para poder cruzarlo después.
            "modelo_orig": sc.modelo,
            "prob_pos_orig": sc.prob_pos,
            "prob_neu_orig": sc.prob_neu,
            "prob_neg_orig": sc.prob_neg,
        }
    _insertar_correccion(db, {
        "comentario_id": com_id, "campo": "postura", "valor_original": ingenua,
        "valor_nuevo": postura, "justificacion": (justificacion or "").strip() or None,
        "autor": autor, "creado_en": datetime.utcnow(), **extras,
    })
    db.commit()
    return {"cambiado": cambiado, "hechos": 0}


def corregir_tema(
    db: Session, com_id: int, tema: str, justificacion: str, autor: str | None,
    *, autor_tipo: str | None = None, origen_muestra: str | None = None,
) -> dict:
    """Revisa el TEMA de un comentario y deja constancia. Ver `corregir_sentimiento`.

    Por qué existe además de `asignar_tema_comentario`: aquella PISA `C.tema` y no
    deja rastro de qué había antes ni de quién lo cambió — exactamente el problema
    que tenía el sentimiento antes de registrar las revisiones. Consecuencia medida:
    `percepcion_correccion` tiene CERO filas con `campo='tema'`, así que el
    clasificador de temas nunca se pudo evaluar.

    Y hace falta evaluarlo: es un matcher de palabras clave (`keyword-taxonomy-v1`)
    corriendo sobre comentarios de mediana 3 palabras. Su confianza tiene mediana
    **0,45** y el **89,5%** de las asignaciones está por debajo de 0,7.
    """
    com = db.get(C, com_id)
    if com is None:
        raise ValueError("El comentario no existe.")
    original = com.tema
    cambiado = original != tema

    extras: dict = {}
    if _tiene_columna(db, Corr.__tablename__, "confirmado"):
        extras = {
            "confirmado": not cambiado,
            "autor_tipo": autor_tipo or AUTOR_HUMANO,
            "origen_muestra": origen_muestra,
        }
        if _tiene_columna(db, Corr.__tablename__, "prob_tema_orig"):
            # `tema_confianza == 1.0` = ya curado a mano; esa no es la confianza del
            # clasificador sino la certeza de una persona. Guardarla como "original"
            # sería perder el dato, igual que pasaba con las probabilidades del scorer.
            ya_curado = com.tema_confianza is not None and com.tema_confianza >= 1.0
            if not ya_curado:
                extras["prob_tema_orig"] = com.tema_confianza
            else:
                previo = db.execute(
                    select(Corr).where(Corr.comentario_id == com_id, Corr.campo == "tema",
                                       Corr.prob_tema_orig.isnot(None))
                    .order_by(Corr.id).limit(1)
                ).scalars().first()
                if previo is not None:
                    extras["prob_tema_orig"] = previo.prob_tema_orig

    if cambiado:
        com.tema = tema
        com.tema_confianza = 1.0        # 1.0 = curado a mano (certeza humana)
    _insertar_correccion(db, {
        "comentario_id": com_id, "campo": "tema", "valor_original": original,
        "valor_nuevo": tema, "justificacion": (justificacion or "").strip() or None,
        "autor": autor, "creado_en": datetime.utcnow(), **extras,
    })
    db.commit()
    return {"cambiado": cambiado, "hechos": reagregar(db) if cambiado else 0}


def replay_correcciones(db: Session) -> dict:
    """Re-aplica sobre `percepcion_score` la ÚLTIMA revisión de cada comentario.

    Para qué: el docstring del módulo advierte que si el worker re-clasifica todo
    (reset de temas / re-scoring), la curación manual se pierde. Con el historial
    completo en `percepcion_correccion` eso deja de ser irreversible — se corre
    esto después del re-scoring y el trabajo de revisión vuelve a su lugar.

    Las CONFIRMACIONES se saltean: no cambian nada por definición, y re-aplicarlas
    marcaría como `correccion_manual` un score que nadie tocó.
    """
    aplicadas = {"sentimiento": 0, "emocion": 0}
    for campo in ("sentimiento", "emocion"):
        # Última revisión por comentario: el máximo id gana.
        ultimas = db.execute(
            select(Corr.comentario_id, func.max(Corr.id))
            .where(Corr.campo == campo).group_by(Corr.comentario_id)
        ).all()
        for com_id, corr_id in ultimas:
            c = db.get(Corr, corr_id)
            if c is None or c.confirmado:
                continue
            sc = db.query(S).filter(S.comentario_id == com_id).one_or_none()
            if sc is None:
                continue
            if campo == "sentimiento":
                if sc.sentimiento == c.valor_nuevo:
                    continue
                sc.prob_pos, sc.prob_neu, sc.prob_neg = _PROBS_SENT[c.valor_nuevo]
                sc.sentimiento = c.valor_nuevo
            else:
                if sc.emocion == c.valor_nuevo:
                    continue
                sc.emocion = c.valor_nuevo
                sc.prob_emocion = 1.0
            _marcar_manual(sc)
            aplicadas[campo] += 1
    db.commit()
    total = aplicadas["sentimiento"] + aplicadas["emocion"]
    return {**aplicadas, "hechos": reagregar(db) if total else 0}


def correcciones_recientes(db: Session, *, limite: int = 100) -> dict:
    """Historial de revisiones, lo más reciente primero.

    Viaja con `autor_tipo` y `origen_muestra`: sin ellos, una anotación humana al
    azar y una pasada de agente sobre la cola de dudosos se leen igual, y no lo son.
    """
    stmt = select(Corr).order_by(Corr.id.desc()).limit(limite)
    items = [
        {
            "comentario_id": r.comentario_id, "campo": r.campo,
            "valor_original": r.valor_original, "valor_nuevo": r.valor_nuevo,
            "justificacion": r.justificacion, "autor": r.autor,
            "autor_tipo": r.autor_tipo, "origen_muestra": r.origen_muestra,
            "confirmado": r.confirmado,
        }
        for r in db.execute(stmt).scalars().all()
    ]
    return {"items": items}


# --------------------------------------------------------------------------- #
# Renombrar subtemas (nombre manual sobre la etiqueta automática).
# --------------------------------------------------------------------------- #
LARGO_MAX_SUBTEMA = 80
_ENLACE = re.compile(r"(https?:|www\.)|\S\.[a-zA-Z]{2,}", re.IGNORECASE)
# Letras "en blanco" (categoría Lo/So, no Cf): dejarían un nombre que se ve vacío.
_RELLENOS_INVISIBLES = frozenset("ᅟᅠㅤﾠ⠀")


class SubtemaDesactualizado(Exception):
    """La pantalla tenía otra versión del subtema (los ids cambian al reconstruir)."""


def normalizar_nombre_subtema(valor: str | None) -> str | None:
    """Nombre limpio, o None para volver al automático. ValueError con mensaje en español.

    Sin `@` ni enlaces: un nombre puesto a mano sale en pantalla para todo el equipo y no debe
    poder colar un usuario ni una dirección.
    """
    t = (valor or "").strip()
    if not t:
        return None
    # NFKC pliega variantes que se ven igual: ＠ -> @, ． -> . (si no, colarían usuarios y enlaces).
    t = unicodedata.normalize("NFKC", t)
    if any(ch in _RELLENOS_INVISIBLES for ch in t):
        raise ValueError("El nombre no puede tener caracteres invisibles.")
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in t):
        raise ValueError("El nombre no puede tener saltos de línea, tabulaciones ni caracteres de control.")
    t = " ".join(t.split())
    if len(t) > LARGO_MAX_SUBTEMA:
        raise ValueError(f"El nombre puede tener hasta {LARGO_MAX_SUBTEMA} caracteres.")
    if "@" in t:
        raise ValueError("El nombre no puede incluir @ ni usuarios.")
    if _ENLACE.search(t):
        raise ValueError("El nombre no puede incluir enlaces ni direcciones web.")
    return t


def renombrar_subtema(db: Session, subtema_id: int, valor: str | None, autor: str | None,
                      etiqueta_auto: str | None = None) -> dict:
    """Pone (o quita, con None/blanco) el nombre manual de un subtema. Devuelve el ítem público.

    Solo escribe `etiqueta_manual`, `renombrado_por` y `renombrado_en` (UPDATE por columna del
    rol de la app). LookupError si el subtema no existe. Con `etiqueta_auto` (la que vio la
    pantalla) el UPDATE exige que siga igual: si una reconstrucción la cambió entretanto, lanza
    SubtemaDesactualizado en vez de renombrar otra cosa.
    """
    from app.services.percepcion import repository
    from app.services.percepcion.models import PercepcionSubtema as Sub

    nombre = normalizar_nombre_subtema(valor)
    if not repository._hay_subtemas(db) or not repository._hay_nombre_manual(db):
        raise LookupError("Todavía no hay subtemas que renombrar.")
    existe = db.execute(select(Sub.id).where(Sub.id == subtema_id)).first()
    if existe is None:
        raise LookupError("El subtema no existe.")
    filtro = Sub.id == subtema_id
    if etiqueta_auto is not None:
        filtro = filtro & (Sub.etiqueta == etiqueta_auto)
    hechas = db.execute(update(Sub).where(filtro).values(
        etiqueta_manual=nombre,
        renombrado_por=(autor or None) if nombre else None,
        renombrado_en=datetime.utcnow() if nombre else None)).rowcount
    if not hechas:
        # Otra versión (o borrado por una reconstrucción entre el chequeo y el UPDATE).
        db.rollback()
        raise SubtemaDesactualizado("Los subtemas cambiaron mientras editabas. Recarga la lista.")
    db.commit()
    f = db.execute(select(Sub.id, Sub.etiqueta, Sub.terminos, Sub.n_comentarios, Sub.etiqueta_manual)
                   .where(Sub.id == subtema_id)).first()
    if f is None:
        raise SubtemaDesactualizado("Los subtemas cambiaron mientras editabas. Recarga la lista.")
    return repository._item_subtema(f, f.etiqueta_manual)
