"""Importa a la base las anotaciones hechas en `percepcion_comentarios.xlsx`.

Contraparte de `_exportar_percepcion_xlsx.py` (repo del worker). Anotar en planilla
es mucho más rápido que la cola web; esto es lo que hace que ese trabajo sirva.

⚠️ NO REIMPLEMENTA LA CURACIÓN. Llama a `curacion.corregir_*`, que son las mismas
funciones que usa la Torre. Duplicar esa lógica es exactamente cómo se perdió la
columna `origen` de los 894 hechos en agosto: dos caminos de escritura que se creen
equivalentes y no lo son.

CELDA VACÍA = «EL MODELO ACERTÓ»
--------------------------------
Vacío no es "sin revisar": es una CONFIRMACIÓN, y confirmar es dato (sin las
confirmaciones no se puede calcular el acuerdo, sólo los errores). Como una fila no
revisada también está vacía, hace falta saber hasta dónde se revisó: es lo que hace
`--hasta N` sobre `orden_muestra`. Sin el argumento se INFIERE como el mayor
`orden_muestra` con alguna celda escrita, que subestima (si las últimas revisadas
estaban todas bien, quedan afuera) pero nunca inventa.

MUESTRA INSESGADA
-----------------
`origen_muestra='aleatorio'` sólo se marca dentro del PREFIJO CONTIGUO anotado de la
permutación. Lo de más abajo entra como 'planilla' y NO se usa para medir: una
muestra elegida por conveniencia no estima nada, por muchas filas que tenga.

Uso:
    backend\\.venv\\Scripts\\python.exe scripts/_importar_percepcion_xlsx.py <ruta.xlsx> [--hasta N] [--aplicar]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# La consola de Windows es cp1252 y revienta con «⚠» o con cualquier tilde. Sin
# esto el script se cae JUSTO cuando tiene un aviso que mostrar, que es cuando más
# falta hace verlo.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # flujo redirigido o ya envuelto
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.services.percepcion import curacion  # noqa: E402
from app.services.percepcion.db import PercepcionWriteSessionLocal  # noqa: E402
from app.services.percepcion.models import AUTOR_AGENTE, AUTOR_HUMANO  # noqa: E402
from app.services.percepcion.models import MUESTRA_ALEATORIA  # noqa: E402
from app.services.percepcion.models import PercepcionComentario as C  # noqa: E402
from app.services.percepcion.models import PercepcionScore as S  # noqa: E402
from app.services.percepcion.repository import ETIQUETAS_EMOCION, ETIQUETAS_TEMA  # noqa: E402

MUESTRA_PLANILLA = "planilla"

# etiqueta visible -> clave interna. Se invierten los diccionarios que ya existen
# en vez de escribirlos de nuevo: así un cambio de etiqueta no deja el importador
# aceptando valores que la Torre ya no conoce.
A_SENT = {"Positivo": "POS", "Neutral": "NEU", "Negativo": "NEG"}
A_EMO = {v: k for k, v in ETIQUETAS_EMOCION.items()}
A_TEMA = {v: k for k, v in ETIQUETAS_TEMA.items()}
A_POSTURA = {
    "Favorable a la UCN": "favorable",
    "Sin postura institucional": "neutral",
    "Adverso a la UCN": "adverso",
}
CAMPOS = (
    ("sentimiento_ok", "sentimiento", A_SENT, curacion.corregir_sentimiento),
    ("emocion_ok", "emocion", A_EMO, curacion.corregir_emocion),
    ("tema_ok", "tema", A_TEMA, curacion.corregir_tema),
    ("postura_ok", "postura", A_POSTURA, curacion.corregir_postura),
)


def _leer(ruta: Path) -> tuple[list[dict], list[str]]:
    wb = load_workbook(ruta, data_only=True, read_only=True)
    if "Comentarios" not in wb.sheetnames:
        raise SystemExit(f"{ruta.name} no tiene la hoja 'Comentarios'.")
    ws = wb["Comentarios"]
    it = ws.iter_rows(values_only=True)
    enc = [str(v or "").strip() for v in next(it)]
    idx = {n: i for i, n in enumerate(enc)}
    faltan = [n for n, _, _, _ in CAMPOS if n not in idx]
    faltan += [n for n in ("orden_muestra", "id") if n not in idx]
    if faltan:
        raise SystemExit(f"Faltan columnas en la planilla: {', '.join(faltan)}")

    filas, avisos = [], []
    for n, fila in enumerate(it, start=2):
        if fila[idx["id"]] is None:
            continue
        r = {"fila": n, "id": int(fila[idx["id"]]),
             "orden": int(fila[idx["orden_muestra"]] or 0)}
        for col, campo, mapa, _fn in CAMPOS:
            bruto = fila[idx[col]]
            txt = str(bruto).strip() if bruto is not None else ""
            if not txt:
                r[campo] = None
                continue
            if txt not in mapa:
                avisos.append(f"fila {n}: «{txt}» no es un valor válido de {col} — se ignora")
                r[campo] = None
            else:
                r[campo] = mapa[txt]
        filas.append(r)
    wb.close()
    return filas, avisos


def _prefijo_contiguo(ordenes: set[int]) -> int:
    """Mayor K tal que 1..K estén TODOS anotados. Sólo eso es muestra insesgada."""
    k = 0
    while k + 1 in ordenes:
        k += 1
    return k


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx", type=Path)
    ap.add_argument("--hasta", type=int, default=None,
                    help="hasta qué orden_muestra se revisó (vacío = confirmación)")
    ap.add_argument("--autor", default="planilla@ucn.cl")
    ap.add_argument("--como-agente", action="store_true", dest="agente",
                    help="marca lo importado como autor_tipo='agente' en vez de 'humano'. "
                         "Un anotador que NO fue validado a ciegas entra SIEMPRE así: "
                         "`calidad.py` mide sólo sobre 'humano', de modo que sus etiquetas "
                         "sirven de candidato/prellenado pero no se cuelan al patrón de oro.")
    ap.add_argument("--aplicar", action="store_true", help="sin esto no escribe nada")
    a = ap.parse_args()

    filas, avisos = _leer(a.xlsx)
    for w in avisos[:20]:
        print(f"  ⚠ {w}")
    if len(avisos) > 20:
        print(f"  ⚠ ...y {len(avisos) - 20} avisos más")

    con_algo = {r["orden"] for r in filas if any(r[c] for _, c, _, _ in CAMPOS)}
    hasta = a.hasta if a.hasta is not None else (max(con_algo) if con_algo else 0)
    inferido = a.hasta is None
    revisadas = [r for r in filas if 0 < r["orden"] <= hasta]
    prefijo = _prefijo_contiguo({r["orden"] for r in revisadas})

    print(f"\nPlanilla : {a.xlsx.name}  ({len(filas)} filas)")
    print(f"Revisado hasta orden_muestra {hasta}"
          + (" (INFERIDO — pasá --hasta N si revisaste más)" if inferido else ""))
    print(f"  filas dentro del tramo revisado : {len(revisadas)}")
    print(f"  prefijo contiguo (sirve p/medir): {prefijo}")
    if prefijo < hasta:
        print(f"  ⚠ hay huecos: {hasta - prefijo} filas quedan como '{MUESTRA_PLANILLA}'")

    cambios = sum(1 for r in revisadas for _, c, _, _ in CAMPOS if r[c])
    print(f"  correcciones explícitas         : {cambios}")
    print(f"  confirmaciones (celda vacía)    : {len(revisadas) * len(CAMPOS) - cambios}")

    if not a.aplicar:
        print("\n[DRY-RUN] No se escribió nada. Volvé a correr con --aplicar.")
        return 0

    db = PercepcionWriteSessionLocal()
    try:
        # El estado ACTUAL de cada comentario. Hace falta porque una celda vacía se
        # escribe igual, con el valor que el modelo dice HOY: eso queda como
        # `confirmado=True` y es lo que permite calcular ACUERDO. Si sólo se
        # guardaran las correcciones, la base tendría los errores y ningún acierto,
        # y el acuerdo medido daría 0 %.
        vivos = {
            cid: {"tema": tema, "sentimiento": sent, "emocion": emo}
            for cid, tema, sent, emo in db.execute(
                select(C.id, C.tema, S.sentimiento, S.emocion)
                .join(S, S.comentario_id == C.id)
                .where(C.id.in_([r["id"] for r in revisadas]))
            )
        } if revisadas else {}

        # UN AGENTE NO PISA A UN HUMANO. `corregir_*` escribe la tabla base además
        # de la de correcciones, así que sin esto el tablero mostraría la etiqueta
        # del agente encima de una curada a mano. El oro sobreviviría igual (vive en
        # `percepcion_correccion`), pero lo que se ve en pantalla sería del agente.
        # Con `--como-agente` se saltean los comentarios ya terminados por un humano
        # bajo el criterio vigente.
        protegidos = curacion.comentarios_completos(db) if a.agente else set()

        escritas, saltadas, sin_base, pisadas = 0, 0, 0, 0
        for r in revisadas:
            actual = vivos.get(r["id"])
            if actual is None:
                sin_base += 1
                continue
            if r["id"] in protegidos:
                pisadas += 1
                continue
            muestra = MUESTRA_ALEATORIA if r["orden"] <= prefijo else MUESTRA_PLANILLA
            for _col, campo, _mapa, fn in CAMPOS:
                valor = r[campo]
                if valor is None:
                    # Vacío = confirmación de lo vigente. La postura no la produce
                    # ningún modelo: lo vigente es la suposición desde el tono.
                    valor = (curacion.POSTURA_DESDE_SENTIMIENTO.get(actual["sentimiento"])
                             if campo == "postura" else actual[campo])
                    if not valor or (campo == "tema" and valor in curacion.TEMAS_RETIRADOS):
                        saltadas += 1
                        continue
                try:
                    fn(db, r["id"], valor, "planilla", a.autor,
                       autor_tipo=AUTOR_AGENTE if a.agente else AUTOR_HUMANO,
                       origen_muestra=muestra)
                    escritas += 1
                except ValueError as e:
                    print(f"  ⚠ fila {r['fila']} ({campo}): {e}")
        db.commit()
        print(f"\nEscritas {escritas} anotaciones · {saltadas} filas sin comentario en la base")
        print(f"Hechos reconstruidos: {curacion.reagregar(db)}")
        db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
