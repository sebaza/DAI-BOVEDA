"""F · ¿Sirve un LLM como anotador de percepción? Calibración contra el ancla humana.

PARA QUÉ
--------
Anotar a mano no escala: 150 comentarios costaron unas horas y el corpus tiene 2.887.
Un juez LLM sí escala — **si primero se demuestra que coincide con la persona**. Este
script es esa demostración, y no da por buena ninguna respuesta sin medirla.

QUÉ HACE DISTINTO DE LAS AUDITORÍAS v4/v9
------------------------------------------
Las dos pasadas de agente que ya existían (`auditoria-contextual-v4`, `auditoria-v9`)
movieron el **90 %** y el **81 %** de sus correcciones hacia POS. Un sesgo direccional
de esa magnitud es indistinguible de un modelo que falla en esa dirección, y quedó sin
resolver hasta que hubo anotación humana. Tres cambios para no repetirlo:

1. **JUICIO CIEGO.** Al juez NO se le muestra lo que dijo el modelo. Es la defensa
   principal contra el anclaje: no se puede arrastrar hacia una etiqueta que no se ve.
2. **DOS FAMILIAS DISTINTAS** (OpenAI + Anthropic), no dos pasadas del mismo. `paper1`
   reporta fiabilidad inter-juez (Pearson r=0,88) justamente porque los jueces eran
   independientes; v4 y v9 eran secuenciales y en los 4 comentarios que compartían
   coincidieron 0 de 4.
3. **CONTROL NEGATIVO DE ANCLAJE.** A un subconjunto se le vuelve a preguntar, pero
   inventándole una etiqueta de modelo. Si el veredicto CAMBIA según lo que se le
   dice, el juez está obedeciendo en vez de juzgando y sus anotaciones no valen nada.
   Es la adaptación del control de `paper1`: allá una contra-agenda contradicha por
   los datos debía puntuar BAJO; acá un ancla inventada NO debe mover el veredicto.

QUÉ MIDE
--------
* **juez vs humano** — la pregunta real: ¿puede sustituir a la persona?
* **juez vs juez** — fiabilidad inter-anotador entre familias distintas.
* **juez vs modelo** — de paso, una segunda opinión sobre el scorer.
* **tasa de anclaje** — el control. Alta ⇒ el resto de los números no significan nada.

Todas con kappa de Cohen además del acuerdo simple: con clases desbalanceadas
(POS 70 % / NEU 21 % / NEG 8,5 %) dos jueces que tiran una moneda ya coinciden bastante.

DATOS QUE SALEN DE LA MÁQUINA
-----------------------------
Se envía a las APIs el TEXTO del comentario y el CAPTION de su publicación. Son datos
públicos de cuentas públicas. **Nunca se envía `autor_hash`** ni ningún identificador:
el corpus no tiene PII expuesta y este script no la introduce.

NO ESCRIBE EN LA BASE. Es solo lectura + reporte: mezclar veredictos de máquina con el
ancla humana antes de saber si el juez sirve arruinaría justamente el patrón de medida.

Uso:
    backend\\.venv\\Scripts\\python.exe scripts/_evaluar_jueces_percepcion.py --limite 40
    backend\\.venv\\Scripts\\python.exe scripts/_evaluar_jueces_percepcion.py --cot --json salida.json

Claves (ninguna se imprime): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` en el `.env` de la
raíz del repo. Sin al menos una, el script no corre.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.percepcion import cripto  # noqa: E402
from app.services.percepcion.calidad import _kappa  # noqa: E402
from app.services.percepcion.db import PercepcionSessionLocal  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):          # Windows: la consola es cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SEMILLA = 20260813

# --------------------------------------------------------------------------- #
# POSTURA — la dimensión que el tono NO captura.
# --------------------------------------------------------------------------- #
# Las reglas de abajo NO son del sentido común del modelo: son la definición
# OPERATIVA que fijó la DAI al anotar 150 comentarios, y sin ellas el juez usaría
# su propio criterio y mediría otra cosa. Las dos que más pesan salieron de la
# anotación real:
#   * un carrete o una junta de CEAL es positivo en tono pero NO afecta a la UCN
#     como institución -> neutral. Es el error dominante del mapeo ingenuo
#     (favorable -> neutral, 7 de 15 casos).
#   * una entrevista, una charla o un logro institucional SÍ suma -> favorable.
SISTEMA_POSTURA = (
    "Sos analista institucional de la Universidad Católica del Norte (UCN). "
    "Para cada comentario decidís su POSTURA HACIA LA INSTITUCIÓN, que NO es su tono.\n\n"
    "REGLA PRINCIPAL: el entusiasmo con la vida universitaria SUMA a la UCN. Si el "
    "comentario celebra, agradece, felicita o se entusiasma con algo de la comunidad "
    "—una bienvenida, un logro, un centro de estudiantes, una actividad— es "
    "**favorable**. Ante la duda entre favorable y neutral, elegí favorable.\n\n"
    "favorable — celebra, agradece, felicita o apoya algo de la UCN o su comunidad.\n"
    "neutral — RESERVADO para comentarios sin ninguna carga institucional: consultas "
    "logísticas («¿a qué hora?»), datos sueltos, o charla entre compañeros que no "
    "dice nada sobre la universidad. Es la clase MENOS frecuente después de adverso.\n"
    "adverso — critica a la UCN o su gestión, o apoya acciones EN CONTRA (paro, toma, "
    "movilización, petitorio), aunque lo haga con entusiasmo: «Paro?😍» es adverso.\n\n"
    "Los comentarios son muy cortos (mediana 3 palabras): usá el contexto de la "
    "publicación para interpretarlos."
)
# ⚠️ Esta es la SEGUNDA versión. La primera enumeraba los casos donde el tono
# engaña («carretes, quinchazos, juntas de CEAL son neutrales») y el juez convirtió
# esa excepción en la regla: dijo "neutral" 93 veces contra las 26 del humano y el
# acuerdo cayó a 52,3%, muy por debajo del 90,0% del mapeo ingenuo tono→postura.
# Por eso ahora la regla PRINCIPAL empuja a favorable y "neutral" está acotado.
# NO volver a listar excepciones sin re-medir.

SISTEMA_TEMA = (
    "Sos analista de percepción de la Universidad Católica del Norte. Clasificás el "
    "TEMA del que habla un comentario de redes sociales.\n"
    "Los comentarios son muy cortos (mediana 3 palabras), así que casi siempre el "
    "tema hay que deducirlo del CONTEXTO de la publicación a la que responden.\n"
    "Elegí el tema por LO QUE LA PUBLICACIÓN ES, no por las palabras sueltas que "
    "aparezcan en ella: un anuncio puede nombrar cosas académicas (tesis, semestre, "
    "departamento) y ser la convocatoria a una fiesta."
)
# ⚠️ LECCIÓN CARA, NO BORRAR: la primera versión de este prompt enumeraba ejemplos
# de la excepción («el carrete de fin de semestre es un evento», «bingo para
# tesistas es un evento»). En POSTURA se hizo exactamente eso —listar los casos
# donde la regla obvia falla— y el juez convirtió la EXCEPCIÓN en la REGLA: usó
# "neutral" 93 veces cuando el humano la usó 26, y el acuerdo se desplomó a 52,3%
# contra el 90,0% del mapeo ingenuo.
#
# Un prompt que enumera excepciones le enseña al juez a buscarlas en todos lados.
# Por eso acá va como CRITERIO ("mirá qué es la publicación") y no como catálogo de
# casos. Si se vuelve a tocar, medir antes y después: el efecto es enorme.

SISTEMA = (
    "Sos analista de percepción de una universidad chilena (Universidad Católica del "
    "Norte). Clasificás el SENTIMIENTO de comentarios de redes sociales HACIA LA "
    "UNIVERSIDAD.\n"
    "Reglas:\n"
    "- POS: elogio, agradecimiento, celebración, apoyo.\n"
    "- NEU: consulta informativa, dato, comentario sin carga hacia la institución.\n"
    "- NEG: queja, reclamo, ironía o sarcasmo crítico, decepción.\n"
    "- El sarcasmo cuenta por su INTENCIÓN, no por sus palabras: «gracias por nada» es NEG.\n"
    "- Los comentarios son muy cortos (mediana 3 palabras). Usá el contexto de la "
    "publicación para interpretarlos."
)

_PEDIDO_SECO = "Respondé SOLO con una palabra: POS, NEU o NEG."
# `paper1` midió que el estilo de prompt le gana a cualquier hiperparámetro (CoT:
# +25,7 % de alineación, p=0,017, a 5x el tiempo). Por eso es una opción medible acá.
_PEDIDO_COT = (
    "Pensá en una frase corta qué intención tiene el comentario y recién después "
    "decidí. Terminá tu respuesta con una línea que diga exactamente:\n"
    "VEREDICTO: <POS|NEU|NEG>"
)


# Registro de dimensiones evaluables. `clases` se resuelve tarde para `tema`,
# porque depende de la taxonomía (fija + los temas custom de la Torre).
DIMENSIONES = {
    "sentimiento": {"sistema": SISTEMA, "clases": ("POS", "NEU", "NEG")},
    "postura": {"sistema": SISTEMA_POSTURA,
                "clases": ("favorable", "neutral", "adverso")},
    "tema": {"sistema": SISTEMA_TEMA, "clases": None},
}


def _prompt(texto: str, caption: str, cot: bool, ancla: str | None,
            clases: tuple[str, ...] = ("POS", "NEU", "NEG")) -> str:
    partes = [
        f"PUBLICACIÓN A LA QUE RESPONDE:\n{(caption or '(sin texto)')[:600]}",
        f"COMENTARIO:\n{texto}",
    ]
    if ancla:
        # SOLO para el control negativo. En el juicio normal esto NO va: mostrarle al
        # juez lo que dijo el modelo es exactamente cómo se contamina una anotación.
        partes.append(f"Un modelo automático clasificó este comentario como: {ancla}")
    opciones = " | ".join(clases)
    partes.append(
        f"Responde SOLO con una de estas opciones: {opciones}" if not cot else
        "Pensá en una frase corta qué intención tiene el comentario y recién después "
        "decidí. Terminá tu respuesta con una línea que diga exactamente:\n"
        f"VEREDICTO: <{opciones}>"
    )
    return "\n\n".join(partes)


def _extraer(texto: str, clases: tuple[str, ...] = ("POS", "NEU", "NEG")) -> str | None:
    """Saca la clase de la respuesta. Tolera CoT, minúsculas y puntuación."""
    t = (texto or "").upper()
    if "VEREDICTO:" in t:
        t = t.rsplit("VEREDICTO:", 1)[1]
    hallados = [c for c in clases if c.upper() in t]
    # Si menciona varias (típico en CoT que enumera opciones), gana la última.
    return max(hallados, key=lambda c: t.rfind(c.upper())) if hallados else None


def _openai(prompt: str, modelo: str, key: str, sistema: str = SISTEMA) -> str:
    r = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": modelo, "instructions": sistema, "input": prompt,
              "max_output_tokens": 300},
        timeout=60.0,
    )
    r.raise_for_status()
    d = r.json()
    partes = []
    for bloque in d.get("output", []):
        for c in bloque.get("content", []) or []:
            if c.get("text"):
                partes.append(c["text"])
    return "\n".join(partes) or d.get("output_text", "")


def _anthropic(prompt: str, modelo: str, key: str, sistema: str = SISTEMA) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": modelo, "system": sistema, "max_tokens": 300,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=60.0,
    )
    r.raise_for_status()
    return "\n".join(b.get("text", "") for b in r.json().get("content", []))


def _jueces_disponibles(s) -> list[dict]:
    jueces = []
    if s.openai_api_key:
        jueces.append({"nombre": "openai", "modelo": s.openai_chat_model,
                       "fn": _openai, "key": s.openai_api_key})
    if s.anthropic_api_key:
        jueces.append({"nombre": "anthropic",
                       "modelo": os.getenv("ANTHROPIC_JUDGE_MODEL", "claude-sonnet-5"),
                       "fn": _anthropic, "key": s.anthropic_api_key})
    return jueces


MIN_CALIBRACION = 30   # mismo umbral que `calidad.MIN_ANCLA`


def _corte_fecha(db, dias: int | None):
    """Fecha desde la cual filtrar, anclada al comentario MÁS RECIENTE, no a hoy.

    Si el worker no ingesta hace una semana, "los últimos 7 días" contra la fecha de
    hoy devolverían cero. El corpus manda.
    """
    if not dias:
        return None
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.services.percepcion.models import PercepcionComentario as C

    fmax = db.execute(select(func.max(C.fecha_comentario))).scalar()
    return None if fmax is None else fmax - timedelta(days=dias)


def _muestra(db, limite: int, dias: int | None = None,
             campo: str = "sentimiento") -> list[dict]:
    """Los comentarios que anotó una PERSONA sobre muestra aleatoria, con su caption.

    Es el único patrón de medida válido que hay: muestra insesgada y anotador humano.
    `dias` acota la ventana, pero ojo — ver la advertencia de `main`: la anotación
    humana está repartida en TODO el período, así que recortarla deja muy pocos casos
    y la calibración pierde sentido.
    """
    from sqlalchemy import func, select

    from app.services.percepcion.models import PercepcionComentario as C
    from app.services.percepcion.models import PercepcionCorreccion as Corr
    from app.services.percepcion.models import PercepcionPublicacion as P
    from app.services.percepcion.models import PercepcionScore as S

    ultimos = select(func.max(Corr.id)).where(
        Corr.campo == campo, Corr.autor_tipo == "humano",
        Corr.origen_muestra == "aleatorio",
    ).group_by(Corr.comentario_id)

    # ⚠️ La PRIMERA revisión, no la última. Corregir actualiza la tabla base, así que
    # en una segunda pasada el `valor_original` ya es la respuesta humana anterior:
    # tomar la última medía "el humano coincidiendo consigo mismo" y daba 96,7% en
    # tema cuando el número real es 63,3%. Ver `calidad._ultimas_revisiones`.

    primeras = select(func.min(Corr.id)).where(
        Corr.campo == campo, Corr.autor_tipo == "humano",
        Corr.origen_muestra == "aleatorio",
    ).group_by(Corr.comentario_id)

    cond = [Corr.id.in_(primeras)]
    corte = _corte_fecha(db, dias)
    if corte is not None:
        cond.append(C.fecha_comentario >= corte)

    filas = db.execute(
        select(C.id, C.texto, P.caption, Corr.valor_nuevo, Corr.valor_original, P.id)
        .join(Corr, Corr.comentario_id == C.id)
        .join(P, P.id == C.publicacion_id)
        .join(S, S.comentario_id == C.id)
        .where(*cond)
        .order_by(C.id)
    ).all()

    datos = [
        {"id": cid, "texto": cripto.texto_de(cid, txt),
         "caption": cripto.caption_de(pid, cap) or "",
         "humano": humano, "modelo": modelo}
        for cid, txt, cap, humano, modelo, pid in filas
    ]
    if limite and len(datos) > limite:
        random.Random(SEMILLA).shuffle(datos)
        datos = sorted(datos[:limite], key=lambda d: d["id"])
    return datos


def _sin_anotar(db, limite: int, dias: int | None) -> list[dict]:
    """Comentarios que NADIE revisó todavía — el objetivo real de escalar con un juez.

    Acá el recorte por fecha SÍ es lo correcto: se juzga lo que entró nuevo, no se
    re-procesa el histórico entero en cada corrida.
    """
    from sqlalchemy import select

    from app.services.percepcion.models import PercepcionComentario as C
    from app.services.percepcion.models import PercepcionCorreccion as Corr
    from app.services.percepcion.models import PercepcionPublicacion as P
    from app.services.percepcion.models import PercepcionScore as S

    cond = [C.id.notin_(select(Corr.comentario_id))]
    corte = _corte_fecha(db, dias)
    if corte is not None:
        cond.append(C.fecha_comentario >= corte)

    filas = db.execute(
        select(C.id, C.texto, P.caption, S.sentimiento, P.id)
        .join(P, P.id == C.publicacion_id)
        .join(S, S.comentario_id == C.id)
        .where(*cond)
        .order_by(C.fecha_comentario.desc())
        .limit(limite or 10_000)
    ).all()
    return [{"id": cid, "texto": cripto.texto_de(cid, txt),
             "caption": cripto.caption_de(pid, cap) or "",
             "humano": None, "modelo": sent} for cid, txt, cap, sent, pid in filas]


def _comparar(pares: list[tuple[str, str]], etiqueta: str) -> dict:
    if not pares:
        return {"etiqueta": etiqueta, "n": 0}
    ok = sum(1 for a, b in pares if a == b)
    return {"etiqueta": etiqueta, "n": len(pares), "acuerdo": round(ok / len(pares), 3),
            "kappa": _kappa(pares)}


def _linea(m: dict) -> str:
    if not m.get("n"):
        return f"  {m['etiqueta']:24s} sin datos"
    k = m["kappa"]
    return (f"  {m['etiqueta']:24s} n={m['n']:3d}  acuerdo={m['acuerdo'] * 100:5.1f}%"
            f"  kappa={'—' if k is None else f'{k:.3f}'}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--limite", type=int, default=40,
                   help="comentarios a juzgar (default 40; 0 = todos)")
    p.add_argument("--cot", action="store_true",
                   help="pide razonar antes de decidir (paper1: +25,7%% de alineacion, 5x tiempo)")
    p.add_argument("--anclaje", type=int, default=15,
                   help="cuantos comentarios usar para el control negativo de anclaje")
    p.add_argument("--dias", type=int, default=None,
                   help="acota a los ultimos N dias (desde el comentario mas reciente, no desde hoy)")
    p.add_argument("--nuevos", action="store_true",
                   help="MODO APLICAR: juzga comentarios SIN revisar en vez de calibrar. "
                        "Solo tiene sentido DESPUES de que la calibracion haya dado bien.")
    p.add_argument("--dimension", choices=tuple(DIMENSIONES), default="sentimiento",
                   help="que se juzga: sentimiento (tono), postura (hacia la UCN) o tema")
    p.add_argument("--json", default=None, help="guarda el detalle en un archivo")
    p.add_argument("--rehacer", action="store_true",
                   help="ignora el checkpoint y vuelve a juzgar todo desde cero")
    args = p.parse_args()

    dim = DIMENSIONES[args.dimension]
    sistema = dim["sistema"]
    clases = dim["clases"]

    s = get_settings()
    jueces = _jueces_disponibles(s)
    if not jueces:
        print("[X] No hay ninguna clave de juez configurada.")
        print("    Definí OPENAI_API_KEY y/o ANTHROPIC_API_KEY en el .env de la raiz.")
        print("    Estan en Secret Manager (TORRE_OPENAI_API_KEY).")
        return 2
    if len(jueces) == 1:
        print(f"[!] Solo hay un juez ({jueces[0]['nombre']}). Se puede medir contra el")
        print("    humano, pero NO la fiabilidad inter-juez, que es lo que le faltaba")
        print("    a las auditorias v4/v9. Configura la otra familia para eso.\n")

    db = PercepcionSessionLocal()
    if clases is None:
        # `tema` depende de la taxonomía viva (fija + custom de la Torre), así que
        # se resuelve acá y no en la constante.
        from app.services.percepcion.curacion import temas_asignables
        clases = tuple(t["tema"] for t in temas_asignables(db))

    if args.nuevos:
        datos = _sin_anotar(db, args.limite, args.dias)
        if not datos:
            print("[X] No quedan comentarios sin revisar en esa ventana.")
            return 2
        print(f"MODO APLICAR: {len(datos)} comentarios SIN revisar"
              f"{f' (ultimos {args.dias} dias)' if args.dias else ''}")
        print("  No hay veredicto humano contra el cual medir: esto ANOTA, no calibra.")
        print("  Corre primero sin --nuevos y confirma que el juez da >= 85%.")
    else:
        datos = _muestra(db, args.limite, args.dias, campo=args.dimension)
        if not datos:
            print("[X] No hay anotaciones humanas sobre muestra aleatoria en esa ventana.")
            print("    Anota desde Percepcion -> Curacion -> Cola de revision, o saca --dias.")
            return 2
        # La anotación humana está repartida en TODO el período. Recortarla por fecha
        # deja muy pocos casos y el acuerdo medido deja de significar algo — con 7
        # comentarios, un juez que acierta 5 "saca 71%" y eso no es una medición.
        if args.dias and len(datos) < MIN_CALIBRACION:
            print(f"[!] Con --dias {args.dias} quedan solo {len(datos)} comentarios anotados,")
            print(f"    menos del minimo de {MIN_CALIBRACION} para que el acuerdo signifique algo.")
            print("    Para CALIBRAR sacá --dias (son ~150 casos y cuesta centavos).")
            print("    Para ANOTAR datos nuevos de esa ventana, usá --nuevos.\n")

    print(f"muestra: {len(datos)} comentarios"
          f"{'' if args.nuevos else ' anotados por una persona (muestra aleatoria)'}")
    print(f"jueces : {', '.join(j['nombre'] + '/' + j['modelo'] for j in jueces)}")
    print(f"modo   : {'CoT (razona y decide)' if args.cot else 'directo'}")
    print("-" * 70)

    # CHECKPOINT: cada llamada cuesta plata y segundos. Si el proceso se corta a
    # mitad —Ctrl+C, red, rate limit— sin esto se pierde TODO lo ya pagado. Con el
    # checkpoint, volver a correr el mismo comando retoma donde quedó.
    ruta_ck = Path(args.json) if args.json else Path(f"_jueces_{args.dimension}.parcial.json")
    veredictos: dict[str, dict[int, str]] = {j["nombre"]: {} for j in jueces}
    if ruta_ck.exists() and not args.rehacer:
        try:
            previo = json.loads(ruta_ck.read_text(encoding="utf-8")).get("veredictos", {})
            for nombre, d_ in previo.items():
                if nombre in veredictos:
                    veredictos[nombre] = {int(k): v for k, v in d_.items()}
            ya = sum(len(v) for v in veredictos.values())
            if ya:
                print(f"  reanudando: {ya} veredictos ya guardados en {ruta_ck.name}")
        except Exception:
            pass

    def _guardar_checkpoint():
        try:
            ruta_ck.write_text(json.dumps(
                {"muestra": datos, "veredictos": veredictos, "dimension": args.dimension,
                 "cot": args.cot, "parcial": True}, ensure_ascii=False, indent=1,
            ), encoding="utf-8")
        except Exception:
            pass

    fallos = 0
    t0 = time.monotonic()
    interrumpido = False
    try:
        for i, d in enumerate(datos, 1):
            for j in jueces:
                if d["id"] in veredictos[j["nombre"]]:
                    continue                      # ya juzgado en una corrida previa
                try:
                    cruda = j["fn"](
                        _prompt(d["texto"], d["caption"], args.cot, None, clases),
                        j["modelo"], j["key"], sistema)
                    clase = _extraer(cruda, clases)
                    if clase:
                        veredictos[j["nombre"]][d["id"]] = clase
                    else:
                        fallos += 1
                except Exception as exc:
                    fallos += 1
                    if fallos <= 3:
                        print(f"  fallo en {j['nombre']} (com {d['id']}): "
                              f"{exc.__class__.__name__}")
            # Señal de vida en CADA ítem y con flush. Sin esto son minutos de
            # pantalla muerta y uno cree que se colgó — que es justo lo que pasó.
            hechas = i
            transcurrido = time.monotonic() - t0
            ritmo = transcurrido / max(hechas, 1)
            faltan = int(ritmo * (len(datos) - hechas))
            print(f"\r  {i}/{len(datos)}  ({transcurrido:.0f}s, faltan ~{faltan}s)   ",
                  end="", flush=True)
            if i % 10 == 0:
                _guardar_checkpoint()
    except KeyboardInterrupt:
        interrumpido = True
        print("\n  [interrumpido] se guarda lo hecho hasta acá.")
    finally:
        print()
        _guardar_checkpoint()

    juzgados = sum(len(v) for v in veredictos.values())
    if not juzgados:
        print("  no se pudo juzgar ningun comentario.")
        return 1
    if interrumpido:
        print(f"  {juzgados} veredictos guardados en {ruta_ck.name}.")
        print("  Volve a correr el MISMO comando para retomar donde quedo.")

    print()
    print("=== ACUERDO ===")
    humano = {d["id"]: d["humano"] for d in datos if d["humano"]}
    modelo = {d["id"]: d["modelo"] for d in datos}
    resultados = []
    for j in jueces:
        v = veredictos[j["nombre"]]
        if humano:
            resultados.append(
                _comparar([(v[i], humano[i]) for i in v if i in humano],
                          f"{j['nombre']} vs HUMANO"))
        resultados.append(_comparar([(v[i], modelo[i]) for i in v], f"{j['nombre']} vs modelo"))
    if len(jueces) == 2:
        a, b = (veredictos[j["nombre"]] for j in jueces)
        comunes = set(a) & set(b)
        # Fiabilidad INTER-JUEZ. Es lo único de acá que no necesita veredicto humano,
        # y es justo lo que las auditorias v4/v9 nunca pudieron medir (eran pasadas
        # secuenciales del mismo juez, no dos familias independientes).
        resultados.append(_comparar([(a[i], b[i]) for i in comunes], "juez vs juez"))
    if humano:
        # El modelo contra el humano: la referencia que ya conocíamos (78 %).
        resultados.append(_comparar([(modelo[i], humano[i]) for i in humano], "MODELO vs humano"))
    for m in resultados:
        print(_linea(m))
    if not humano:
        print()
        print("  (sin veredicto humano en esta muestra: se puede medir si los jueces")
        print("   COINCIDEN, no si ACIERTAN. Para lo segundo corré sin --nuevos.)")

    # ---------------------------------------------------------------- control
    anclaje = []
    if args.anclaje and not interrumpido:
        print()
        print("=== CONTROL NEGATIVO: ¿el juez se deja anclar? ===")
        print("  Se le repregunta inventandole una etiqueta de modelo. Si el veredicto")
        print("  CAMBIA, esta obedeciendo en vez de juzgando y el resto no vale.")
        sub = datos[: args.anclaje]
        for j in jueces:
            v = veredictos[j["nombre"]]
            cambios = comparados = 0
            for d in sub:
                base = v.get(d["id"])
                if base is None:
                    continue
                # Ancla FALSA: la clase que el juez NO eligió.
                falsa = next(c for c in clases if c != base)
                try:
                    otra = _extraer(j["fn"](
                        _prompt(d["texto"], d["caption"], args.cot, falsa, clases),
                        j["modelo"], j["key"], sistema), clases)
                except Exception:
                    continue
                if otra is None:
                    continue
                comparados += 1
                cambios += int(otra != base)
            tasa = cambios / comparados if comparados else None
            anclaje.append({"juez": j["nombre"], "n": comparados, "cambios": cambios,
                            "tasa": None if tasa is None else round(tasa, 3)})
            estado = "—" if tasa is None else (
                "OK (resiste)" if tasa <= 0.10 else
                "SOSPECHOSO" if tasa <= 0.25 else "SE ANCLA: no usar")
            print(f"  {j['nombre']:24s} n={comparados:3d}  cambio de veredicto="
                  f"{'—' if tasa is None else f'{tasa * 100:5.1f}%'}  {estado}")

    if fallos:
        print(f"\n  respuestas no interpretables o fallidas: {fallos}")

    print()
    print("=== LECTURA ===")
    jh = [m for m in resultados if "vs HUMANO" in m["etiqueta"] and m.get("n")]
    mejor = max(jh, key=lambda m: m["acuerdo"]) if jh else None
    mh = next((m for m in resultados if m["etiqueta"] == "MODELO vs humano"), None)
    if mejor and mh and mh.get("acuerdo"):
        if mejor["acuerdo"] >= 0.85:
            print(f"  {mejor['etiqueta']} = {mejor['acuerdo'] * 100:.1f}%: el juez esta a la altura")
            print("  del anotador humano. Se puede escalar la anotacion con el.")
        elif mejor["acuerdo"] > mh["acuerdo"]:
            print(f"  El juez ({mejor['acuerdo'] * 100:.1f}%) le gana al modelo "
                  f"({mh['acuerdo'] * 100:.1f}%) pero no llega a 85%:")
            print("  sirve para PRIORIZAR que revisar a mano, no para reemplazar la revision.")
        else:
            print(f"  El juez ({mejor['acuerdo'] * 100:.1f}%) NO le gana al modelo "
                  f"({mh['acuerdo'] * 100:.1f}%). No lo uses como anotador.")
    jj = next((m for m in resultados if m["etiqueta"] == "juez vs juez" and m.get("n")), None)
    if jj:
        k = jj["kappa"]
        print(f"  Fiabilidad INTER-JUEZ: acuerdo {jj['acuerdo'] * 100:.1f}%"
              f"{'' if k is None else f', kappa {k:.3f}'}.")
        if jj["acuerdo"] >= 0.80:
            print("  Dos familias distintas coinciden: el criterio es estable, no es")
            print("  la manía de un modelo puntual.")
        else:
            print("  Coinciden poco. Si dos jueces independientes no se ponen de acuerdo,")
            print("  la tarea esta mal definida o los comentarios son demasiado ambiguos:")
            print("  revisá el prompt antes de confiar en cualquiera de los dos.")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"muestra": datos, "veredictos": veredictos, "metricas": resultados,
             "anclaje": anclaje, "cot": args.cot}, ensure_ascii=False, indent=1,
        ), encoding="utf-8")
        print(f"\n  detalle en {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
