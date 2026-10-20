"""Linea base de los CUATRO campos anotados: tono, tema, emocion y postura.

Contra anotaciones humanas del muestreo ALEATORIO. Sin esta medicion, comparar
el pipeline actual contra cualquier alternativa no significa nada.

RESULTADO AL 22-09-2026

    emocion       96.6%   kappa 0.936   n=588
    sentimiento   91.5%   kappa 0.828   n=632
    tema          83.0%   kappa 0.783   n=171
    postura       61.7%   kappa 0.361   n=491   <- ENGANOSO, ver abajo

POSTURA NO SE CLASIFICA, SE DERIVA. `postura_de(sentimiento, tema, cuenta_tipo)`
la calcula con una regla, asi que su numero no se lee como los otros tres:

  - el valor GUARDADO da 70.6%, y esta stale: las anotaciones previas al
    19-08-2026 dan 97.6% y las posteriores 64.1%, porque ese dia cambio el
    criterio de tema y la postura derivada nunca se recalculo
  - la regla RECALCULADA sobre el modelo actual da 73.9%
  - la regla sobre sentimiento y tema HUMANOS da 74.9%

Ese 74.9% es el TECHO DE LA REGLA: aunque el tono y el tema fueran perfectos,
la postura no pasa de ahi. El error dominante es la regla diciendo `neutral`
donde el humano dice `favorable` (39 de 53 errores), y sale de que
`TEMAS_ATRIBUIBLES` deja fuera a `vida_estudiantil`, que es el tema MAS
FRECUENTE del corpus.

CONSECUENCIA: ningun clasificador mejor —ni un LLM, ni un scorer tipado— sube la
postura por encima de ~75% mientras la regla siga vigente. Para moverla hay que
(a) cambiar `TEMAS_ATRIBUIBLES`, que es decision de metodologia y no de
ingenieria, o (b) predecir postura directamente en vez de derivarla, que es un
camino que nunca se probo.

Reglas del dato aplicadas:
  - solo autor_tipo='humano' y origen_muestra='aleatorio' (las otras colas son dirigidas)
  - `tema`: solo anotaciones >= 2026-08-19 (CRITERIO_TEMA_DESDE). Mezclar los dos
    criterios baja el accuracy de 83.0% a 78.7% y la metrica deja de significar nada.

Correr con:
    backend\\.venv\\Scripts\\python.exe scripts/medir_linea_base_percepcion.py

Lee la base del worker en SOLO LECTURA. No escribe nada.
"""
import sqlite3
from collections import Counter

DB = "../Sentiment_Analisys_University/percepcion_real.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def kappa(pares):
    """Cohen entre modelo y humano."""
    n = len(pares)
    if not n:
        return None
    po = sum(1 for a, b in pares if a == b) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    return None if pe >= 1 else (po - pe) / (1 - pe)


def base(campo, extra=""):
    return f"""
        SELECT k.valor_original, k.valor_nuevo
        FROM percepcion_correccion k
        WHERE k.campo = '{campo}'
          AND k.autor_tipo = 'humano'
          AND k.origen_muestra = 'aleatorio'
          AND k.valor_original IS NOT NULL AND k.valor_nuevo IS NOT NULL
          {extra}
    """


print("LINEA BASE ACTUAL — modelo vs humano (muestreo aleatorio)")
print("=" * 72)
print(f"{'campo':12s} {'n':>5s} {'accuracy':>9s} {'kappa':>7s}  {'clases (humano)'}")
print("-" * 72)

resumen = {}
for campo, extra in (
    ("sentimiento", ""),
    ("tema", " AND k.creado_en >= '2026-08-19'"),
    ("emocion", ""),
    ("postura", ""),
):
    pares = con.execute(base(campo, extra)).fetchall()
    if not pares:
        print(f"{campo:12s} {'0':>5s}   (sin datos)")
        continue
    acc = sum(1 for a, b in pares if a == b) / len(pares)
    kp = kappa(pares)
    dist = Counter(b for _, b in pares)
    top = " ".join(f"{k}:{v}" for k, v in dist.most_common(5))
    resumen[campo] = (len(pares), acc, kp)
    print(f"{campo:12s} {len(pares):5d} {acc:9.4f} {kp if kp is None else round(kp,3):>7} "
          f" {len(dist)} clases · {top}")

print()
print("COMPARACION: tema con y sin el corte de criterio (19-08-2026)")
print("-" * 72)
for etiq, extra in (("solo criterio vigente", " AND k.creado_en >= '2026-08-19'"),
                    ("TODO (mezcla criterios)", "")):
    pares = con.execute(base("tema", extra)).fetchall()
    if pares:
        acc = sum(1 for a, b in pares if a == b) / len(pares)
        print(f"  {etiq:26s} n={len(pares):4d}  accuracy {acc:.4f}  kappa {round(kappa(pares),3)}")

print()
print("DONDE DUELE: matriz de confusion por campo (filas=modelo, cols=humano)")
print("-" * 72)
for campo, extra in (("sentimiento", ""), ("postura", "")):
    pares = con.execute(base(campo, extra)).fetchall()
    clases = sorted({v for p in pares for v in p})
    print(f"\n  {campo}  (n={len(pares)})")
    print("        " + "".join(f"{c[:9]:>10s}" for c in clases))
    for m in clases:
        fila = [sum(1 for a, b in pares if a == m and b == h) for h in clases]
        print(f"  {m[:6]:6s}" + "".join(f"{v:10d}" for v in fila))

print()
print("META DEL USUARIO: 90% por campo")
print("-" * 72)
for campo, (n, acc, kp) in resumen.items():
    estado = "YA CUMPLE" if acc >= 0.90 else f"FALTAN {(0.90-acc)*100:.1f} pts"
    print(f"  {campo:12s} accuracy {acc:.4f}  ->  {estado}")
