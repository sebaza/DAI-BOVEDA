"""Calidad del modelo de scoring, medida contra las revisiones de `percepcion_correccion`.

Responde la pregunta que el módulo Percepción no podía responder: **¿los números que
muestra el tablero son buenos?** Hasta ahora no había ni una métrica; el índice se
presentaba sin ninguna medida de cuánto le erra el modelo que lo alimenta.

TRES ADVERTENCIAS QUE ESTE MÓDULO EMITE SOLO
--------------------------------------------
No son notas al pie: son la diferencia entre medir y aparentar que se mide. Por eso
viajan al front en `avisos` y no quedan libradas a que la UI se acuerde de escribirlas.

1. **Sin confirmaciones no hay accuracy.** Registrar solo los cambios deja un
   numerador sin denominador. En la base real las 376 filas son 376 desacuerdos, así
   que el acuerdo observado da 0% — y eso NO significa que el modelo falle siempre,
   significa que los aciertos nunca se anotaron. Cuando no hay confirmaciones,
   `acuerdo` y `kappa` vuelven en None con su motivo, en vez de un cero que mentiría.

2. **La cola `duda` está sesgada por construcción.** Ordena por menor margen del
   modelo, o sea que dirige al revisor justo a donde el modelo es peor. Medir ahí da
   un PISO pesimista, nunca la calidad real. Solo `origen_muestra='aleatorio'`
   habilita una estimación insesgada, y por eso el desglose por muestra es una
   sección propia y no un detalle.

3. **Un agente LLM no es un anotador humano.** En la base real, 375 de 376 revisiones
   vinieron de dos pasadas de un agente que movían el 90% y el 81% de sus fallos hacia
   POS. Un sesgo direccional de esa magnitud es indistinguible de un error real del
   modelo sin una referencia neutral. `sesgo_direccional` lo expone por autor para que
   nadie lo confunda con evidencia sobre el modelo.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.services.percepcion.curacion import ETIQUETAS_POSTURA
from app.services.percepcion.models import AUTOR_HUMANO
from app.services.percepcion.models import PercepcionComentario as C
from app.services.percepcion.models import PercepcionCorreccion as Corr
from app.services.percepcion.repository import (
    ETIQUETAS_EMOCION,
    ETIQUETAS_TEMA,
    _SENT_LABEL,
)

CAMPOS = ("sentimiento", "emocion", "tema", "postura")

# Un sesgo direccional por debajo de esto es ruido; por encima, hay que mirarlo. No
# sale de la literatura: con 3 clases, el azar reparte ~33% a cada una, así que
# concentrar 2 de cada 3 correcciones en una sola clase ya es una decisión, no una
# coincidencia.
UMBRAL_SESGO_DIRECCIONAL = 0.66

# Cortes del margen ORIGINAL del modelo (ganadora − segunda). El primero es "el
# modelo dudaba", el último "el modelo estaba seguro". Corregir mucho en el último
# bucket es la señal fuerte: o el modelo está mal calibrado, o el revisor se está
# pasando de largo.
CORTES_MARGEN = (0.0, 0.2, 0.4, 0.7, 1.01)

# Mínimo de anotaciones para que un ancla CUENTE como ancla.
#
# No alcanza con preguntar "¿hay alguna humana?": en la base real hay exactamente
# UNA entre 261, y con ese criterio el módulo declararía que tiene referencia
# neutral cuando no tiene nada. Se usa el mismo umbral que `N_MIN_CONFIANZA` (30)
# del resto del módulo: sería incoherente que la síntesis marque "muestra
# insuficiente" con menos de 30 y acá se diera por válida una referencia con 1.
MIN_ANCLA = 30


def _etiqueta(campo: str, valor: str | None) -> str:
    if valor is None:
        return "(sin valor)"
    if campo == "sentimiento":
        return _SENT_LABEL.get(valor, valor)
    if campo == "tema":
        return ETIQUETAS_TEMA.get(valor, valor)
    if campo == "postura":
        return ETIQUETAS_POSTURA.get(valor, valor)
    return ETIQUETAS_EMOCION.get(valor, valor)


def _ultimas_revisiones(db: Session, campo: str) -> list[Corr]:
    """Una fila por comentario: la PRIMERA revisión. Sí, la primera.

    ⚠️ BUG CORREGIDO — no cambiar a `max(id)` sin leer esto.

    Corregir ACTUALIZA la tabla base (`C.tema`, `S.sentimiento`). Si el mismo
    comentario se revisa una segunda vez, el `valor_original` que se guarda **ya es
    la respuesta humana de la primera pasada**, no la del modelo. Con `max(id)` se
    estaba midiendo "el humano coincidiendo consigo mismo".

    Medido sobre la base real, con 134 de 150 comentarios revisados dos veces:

    | campo       | max(id) — mal | min(id) — bien |
    |-------------|---------------|----------------|
    | sentimiento | 99,3 %        | **73,3 %**     |
    | tema        | 96,7 %        | **63,3 %**     |
    | emocion     | 100,0 %       | **97,3 %**     |

    Se toma la primera revisión ENTERA (su `valor_original` Y su `valor_nuevo`), no
    una mezcla: es el único par (modelo, humano) que corresponde a un mismo momento.
    Cruzar el modelo de la 1ª pasada con el veredicto de la 2ª compara a través de un
    cambio de modelo —entre medio se recalibró el umbral NEU/POS— y además arrastra
    los cambios de opinión del anotador (mezclando momentos daba 64,0 % y 60,7 %).

    Las revisiones posteriores no se pierden: sirven para medir la CONSISTENCIA del
    anotador consigo mismo, que es el techo de cualquier modelo. Sobre esta base:
    sentimiento 89,7 %, emoción 97,8 %, tema 97,0 %.
    """
    ids = db.execute(
        select(func.min(Corr.id)).where(Corr.campo == campo).group_by(Corr.comentario_id)
    ).scalars().all()
    if not ids:
        return []
    return list(db.execute(select(Corr).where(Corr.id.in_(ids)).order_by(Corr.id)).scalars())


def _kappa(pares: list[tuple[str, str]]) -> float | None:
    """Kappa de Cohen entre el modelo y el revisor.

    Mide el acuerdo DESCONTANDO el que ocurriría por azar, que es lo que hace falta
    cuando las clases están desbalanceadas: con 46% POS / 46% NEU / 8% NEG, dos
    jueces que tiran una moneda ya coinciden bastante.

    Devuelve None cuando no se puede calcular con sentido: sin pares, con una sola
    clase, o cuando el acuerdo esperado es 1 (todo cae en la misma celda) y la
    fórmula se indefine.
    """
    n = len(pares)
    if n == 0:
        return None
    clases = {c for par in pares for c in par}
    if len(clases) < 2:
        return None
    po = sum(1 for a, b in pares if a == b) / n
    marg_a: dict[str, int] = {}
    marg_b: dict[str, int] = {}
    for a, b in pares:
        marg_a[a] = marg_a.get(a, 0) + 1
        marg_b[b] = marg_b.get(b, 0) + 1
    pe = sum((marg_a.get(c, 0) / n) * (marg_b.get(c, 0) / n) for c in clases)
    if abs(1 - pe) < 1e-9:
        return None
    return round((po - pe) / (1 - pe), 3)


def _en_corte(valor: float) -> str | None:
    for i in range(len(CORTES_MARGEN) - 1):
        if CORTES_MARGEN[i] <= valor < CORTES_MARGEN[i + 1]:
            return f"{CORTES_MARGEN[i]:.1f}–{CORTES_MARGEN[i + 1]:.1f}"
    return None


def _bucket_margen(r, campo: str) -> str | None:
    """Cuán seguro estaba el modelo, en la escala que corresponda al campo.

    Para sentimiento/emoción es el MARGEN (ganadora − segunda), que es lo que mide
    la duda de un clasificador probabilístico. Para tema es la CONFIANZA cruda del
    matcher de keywords, que no devuelve una distribución: no hay segunda clase de
    la cual restar. Son escalas distintas y por eso no se mezclan en un solo número.
    """
    if campo == "tema":
        v = getattr(r, "prob_tema_orig", None)
        return None if v is None else _en_corte(float(v))
    vals = [v for v in (r.prob_pos_orig, r.prob_neu_orig, r.prob_neg_orig) if v is not None]
    if len(vals) < 2:
        return None
    orden = sorted((float(v) for v in vals), reverse=True)
    return _en_corte(orden[0] - orden[1])


def _resumen_pares(revisiones: list[Corr], campo: str) -> dict:
    """Matriz, acuerdo, kappa y sesgo direccional sobre un conjunto de revisiones."""
    # `confirmado is None` = fila anterior a la columna. NO se puede asumir que fue
    # un cambio: se compara valor a valor, que es el dato duro que sí está.
    pares = [
        (r.valor_original or "(sin valor)", r.valor_nuevo)
        for r in revisiones if r.valor_nuevo is not None
    ]
    n = len(pares)
    confirmaciones = sum(1 for a, b in pares if a == b)
    celdas: dict[tuple[str, str], int] = {}
    for par in pares:
        celdas[par] = celdas.get(par, 0) + 1

    # Sesgo direccional: hacia qué clase empuja el revisor cuando cambia algo.
    destinos: dict[str, int] = {}
    for a, b in pares:
        if a != b:
            destinos[b] = destinos.get(b, 0) + 1
    cambios = sum(destinos.values())
    top = max(destinos.items(), key=lambda kv: kv[1]) if destinos else None

    por_margen: dict[str, dict] = {}
    for r in revisiones:
        b = _bucket_margen(r, campo)
        if b is None:
            continue
        acc = por_margen.setdefault(b, {"bucket": b, "n": 0, "cambios": 0})
        acc["n"] += 1
        if (r.valor_original or "(sin valor)") != r.valor_nuevo:
            acc["cambios"] += 1

    return {
        "n": n,
        "confirmaciones": confirmaciones,
        "cambios": n - confirmaciones,
        # Sin una sola confirmación el acuerdo no es 0: es DESCONOCIDO. Devolver 0.0
        # invitaría a leer "el modelo nunca acierta", que es una conclusión falsa
        # sacada de un registro incompleto.
        "acuerdo": round(confirmaciones / n, 3) if n and confirmaciones else None,
        "acuerdo_motivo": (
            None if confirmaciones else
            "No hay confirmaciones registradas: solo se anotaron los cambios, así que "
            "falta el denominador. El acuerdo es desconocido, no cero."
        ),
        "kappa": _kappa(pares) if confirmaciones else None,
        "matriz": sorted(
            (
                {
                    "modelo": a, "modelo_label": _etiqueta(campo, a if a != "(sin valor)" else None),
                    "revisor": b, "revisor_label": _etiqueta(campo, b),
                    "n": k, "acuerdo": a == b,
                }
                for (a, b), k in celdas.items()
            ),
            key=lambda d: -d["n"],
        ),
        "sesgo_direccional": (
            {
                "clase": top[0],
                "clase_label": _etiqueta(campo, top[0]),
                "n": top[1],
                "de": cambios,
                "proporcion": round(top[1] / cambios, 3),
                "alerta": top[1] / cambios >= UMBRAL_SESGO_DIRECCIONAL,
            }
            if top and cambios else None
        ),
        "por_margen": sorted(por_margen.values(), key=lambda d: d["bucket"]),
    }


def _agrupar(revisiones: list[Corr], campo: str, atributo: str, defecto: str) -> list[dict]:
    grupos: dict[str, list[Corr]] = {}
    for r in revisiones:
        grupos.setdefault(getattr(r, atributo, None) or defecto, []).append(r)
    return [
        {"clave": clave, **_resumen_pares(rs, campo)}
        for clave, rs in sorted(grupos.items(), key=lambda kv: -len(kv[1]))
    ]


def calidad_modelo(db: Session) -> dict:
    """Informe de calidad del scoring contra el histórico de revisiones."""
    total_comentarios = db.execute(select(func.count(C.id))).scalar() or 0
    campos: dict[str, dict] = {}
    revisados_ids: set[int] = set()
    n_aleatoria = 0
    n_humano = 0

    for campo in CAMPOS:
        revisiones = _ultimas_revisiones(db, campo)
        revisados_ids.update(r.comentario_id for r in revisiones)
        n_aleatoria += sum(1 for r in revisiones if r.origen_muestra == "aleatorio")
        n_humano += sum(1 for r in revisiones if r.autor_tipo == AUTOR_HUMANO)
        # LA ÚNICA ESTIMACIÓN VÁLIDA: humano + muestra aleatoria. El resumen general
        # mezcla todo y con eso NO se puede leer nada — en la base real da 29,2%
        # porque promedia 250 filas de agente (todas desacuerdos, sin una sola
        # confirmación) con 151 humanas que están en 78%. Un número así, mostrado
        # como titular, hace entrar en pánico por un artefacto del registro.
        validas = [r for r in revisiones
                   if r.autor_tipo == AUTOR_HUMANO and r.origen_muestra == "aleatorio"]
        campos[campo] = {
            **_resumen_pares(revisiones, campo),
            "estimacion": {
                **_resumen_pares(validas, campo),
                "suficiente": len(validas) >= MIN_ANCLA,
            },
            "por_autor": _agrupar(revisiones, campo, "autor_tipo", "(sin registrar)"),
            "por_muestra": _agrupar(revisiones, campo, "origen_muestra", "(sin registrar)"),
            "con_snapshot": sum(
                1 for r in revisiones
                if (r.prob_tema_orig if campo == "tema" else r.prob_pos_orig) is not None
            ),
        }

    avisos: list[dict] = []
    if not any(campos[c]["confirmaciones"] for c in CAMPOS):
        avisos.append({
            "nivel": "critico",
            "titulo": "El acuerdo no se puede calcular",
            "detalle": (
                "Todas las revisiones registradas son cambios: nunca se anotó un "
                "\"el modelo acertó\". Sin confirmaciones falta el denominador y "
                "cualquier accuracy sería inventado. Revisa con la cola de curación "
                "para que las confirmaciones empiecen a quedar registradas."
            ),
        })
    if n_aleatoria < MIN_ANCLA:
        avisos.append({
            "nivel": "critico",
            "titulo": "No hay muestra aleatoria suficiente: falta el ancla",
            "detalle": (
                f"Solo {n_aleatoria} de las revisiones salen de una muestra al azar "
                f"(hacen falta al menos {MIN_ANCLA}). El resto viene de colas dirigidas, "
                "que sirven para corregir pero no para estimar la calidad real: la cola "
                "por duda apunta justo a donde el modelo es peor, así que lo medido ahí "
                "es un piso pesimista. Anota ~150 comentarios con el orden «aleatorio»."
            ),
        })
    if n_humano < MIN_ANCLA:
        avisos.append({
            "nivel": "critico",
            "titulo": "Sin anotación humana suficiente no hay referencia neutral",
            "detalle": (
                f"Solo {n_humano} de las revisiones las hizo una persona (hacen falta al "
                f"menos {MIN_ANCLA}); el resto proviene de agentes. Un agente con sesgo "
                "direccional produce exactamente el mismo patrón que un modelo que falla "
                "en esa dirección, y no hay forma de distinguirlos sin anotación humana "
                "con la que contrastar."
            ),
        })
    # Un campo SIN NINGUNA revisión no puede escudarse en que otro campo sí tiene
    # ancla: los avisos globales miran el total y lo taparían. Es el caso de `tema`,
    # que llegó a tener 2.887 comentarios clasificados y CERO verificados.
    for campo in CAMPOS:
        if campos[campo]["n"] == 0:
            avisos.append({
                "nivel": "critico",
                "titulo": f"«{campo}» no tiene ninguna revisión",
                "detalle": (
                    f"Nunca se verificó una sola asignación de {campo}, así que no hay "
                    "forma de saber si acierta. Revisa con el orden «aleatorio» de la "
                    "cola para tener la primera medición."
                ),
            })

    for campo in CAMPOS:
        sesgo = campos[campo].get("sesgo_direccional")
        if sesgo and sesgo["alerta"]:
            avisos.append({
                "nivel": "atencion",
                "titulo": f"Sesgo direccional en {campo}",
                "detalle": (
                    f"El {sesgo['proporcion'] * 100:.0f}% de los cambios "
                    f"({sesgo['n']} de {sesgo['de']}) apunta a «{sesgo['clase_label']}». "
                    "Puede ser un error real del modelo en esa dirección o un sesgo de "
                    "quien revisa; con lo registrado hoy no se pueden separar."
                ),
            })

    return {
        "total_comentarios": total_comentarios,
        "comentarios_revisados": len(revisados_ids),
        "cobertura": round(len(revisados_ids) / total_comentarios, 4) if total_comentarios else 0.0,
        "campos": campos,
        "avisos": avisos,
    }
