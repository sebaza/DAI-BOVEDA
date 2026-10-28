"""Exporta el corpus de Percepción a un .xlsx para compartir con un investigador externo.

NO es la planilla de anotación (`_exportar_percepcion_xlsx.py` del worker, que trae
columnas amarillas para corregir). Esto es un DATASET de investigación: una fila por
comentario, con la salida del modelo, sus probabilidades, y —cuando existe— la etiqueta
humana que sirve de patrón de oro.

DECISIONES DE PRIVACIDAD, y por qué
-----------------------------------
* **`autor_hash` NO se exporta.** Aunque es irreversible, es un identificador estable:
  quien tenga acceso a la base puede cruzarlo y reidentificar. En su lugar va `autor_id`,
  una renumeración 1..N generada acá y que no sirve fuera de este archivo. Conserva lo
  único que un investigador necesita —agrupar los comentarios de una misma persona— sin
  arrastrar la llave.
* **El texto del comentario SÍ va**, porque sin él no hay investigación posible y son
  datos públicos de cuentas públicas. Pero puede contener nombres de terceros; el script
  los cuenta y avisa para que la decisión de compartir sea informada, no automática.
* **`caption` va recortado** a `MAX_CAPTION`: es contexto, no el objeto de estudio.

LA POSTURA NO ESTÁ ALMACENADA: se deriva de (sentimiento, tema) con la regla de
`services/percepcion/postura.py`. Va calculada en la exportación para que el archivo sea
autocontenido, y la regla queda documentada en la hoja «Diccionario».
"""
from __future__ import annotations

import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.percepcion import cripto
from app.services.percepcion.postura import ETIQUETAS_POSTURA, postura_de
from app.services.percepcion.repository import (
    ETIQUETAS_EMOCION,
    ETIQUETAS_TEMA,
    _SENT_LABEL,
)

DB = Path(r"C:\Users\sezad\Documents\GitHub\Sentiment_Analisys_University\percepcion_real.db")
SALIDA = Path(__file__).resolve().parents[1] / "outputs" / "percepcion_dataset_20260824"
MAX_CAPTION = 400

FUENTE = "Arial"
AZUL = "1F4E79"
GRIS = "F2F2F2"


def _conectar() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _cargar(con: sqlite3.Connection) -> tuple[list[dict], dict]:
    """Corpus completo, con la etiqueta humana pegada cuando existe."""
    # Anotaciones HUMANAS por (comentario, campo). Se toma la MÁS RECIENTE: si alguien
    # revisó dos veces el mismo comentario, la última es su criterio vigente.
    #
    # ⚠️ Y AL MISMO TIEMPO se recupera lo que había dicho EL MODELO (`valor_original`).
    # Sin esto el dataset miente. La curación SOBRESCRIBE `percepcion_score` con la
    # etiqueta humana, así que en un comentario revisado `percepcion_score` ya ES la
    # respuesta humana: compararlos daría 99 % de acuerdo contra el 88,7 % real. Es el
    # mismo anclaje que ya invalidó una medición completa (ver STATUS.md, «Trampas
    # encontradas»), y acá reaparece por el mismo motivo: leer el estado actual de un
    # registro que fue editado.
    humano: dict[tuple[int, str], str] = {}
    modelo_pre: dict[tuple[int, str], str] = {}
    for r in con.execute(
        "SELECT comentario_id, campo, valor_nuevo, valor_original, confirmado "
        "FROM percepcion_correccion WHERE autor_tipo = 'humano' ORDER BY id"
    ):
        clave = (r["comentario_id"], r["campo"])
        # `confirmado=1` significa que el revisor miró y dejó lo que había: la etiqueta
        # humana es entonces el valor ORIGINAL, no `valor_nuevo`. Sin esta distinción
        # las confirmaciones se leerían como correcciones y el oro quedaría mal.
        valor = r["valor_original"] if r["confirmado"] else r["valor_nuevo"]
        if valor:
            humano[clave] = valor
        # La salida del modelo ANTES de que la corrección la pisara. Es una foto del
        # momento de la revisión, no del modelo de hoy — se documenta como tal.
        if r["valor_original"]:
            modelo_pre.setdefault(clave, r["valor_original"])

    filas = []
    autores: dict[str, int] = {}
    for r in con.execute("""
        SELECT c.id, c.texto, c.fecha_comentario, c.n_likes, c.autor_hash,
               c.tema, c.tema_confianza, c.idioma,
               s.sentimiento, s.prob_pos, s.prob_neu, s.prob_neg,
               s.emocion, s.prob_emocion, s.modelo,
               p.caption, p.id AS pub_id, p.fecha_publicacion, p.tipo AS tipo_pub,
               cu.nombre AS cuenta, cu.campus, cu.facultad, cu.departamento
        FROM percepcion_comentario c
        JOIN percepcion_score s ON s.comentario_id = c.id
        JOIN percepcion_publicacion p ON p.id = c.publicacion_id
        JOIN percepcion_cuenta cu ON cu.id = p.cuenta_id
        ORDER BY c.fecha_comentario
    """):
        # Renumeración del autor: agrupa sin exportar la llave (ver docstring).
        if r["autor_hash"] not in autores:
            autores[r["autor_hash"]] = len(autores) + 1

        caption = (cripto.caption_de(r["pub_id"], r["caption"]) or "").strip().replace("\n", " ")
        if len(caption) > MAX_CAPTION:
            caption = caption[:MAX_CAPTION].rstrip() + "…"

        # Lo que dice el modelo HOY para este comentario. En los revisados esto ya fue
        # pisado por la corrección, así que la comparación honesta usa `modelo_pre`
        # (ver `_hoja_oro`); acá se deja el estado vigente, que es lo que alimenta el
        # tablero y por lo tanto lo que corresponde en la hoja de datos.
        sent, tema = r["sentimiento"], r["tema"]
        post = postura_de(sent, tema)
        h_sent = humano.get((r["id"], "sentimiento"))
        h_tema = humano.get((r["id"], "tema"))

        filas.append({
            "id": r["id"],
            "autor_id": autores[r["autor_hash"]],
            "fecha": (r["fecha_comentario"] or "")[:19],
            "comentario": cripto.texto_de(r["id"], r["texto"]),
            "contexto_publicacion": caption,
            "fecha_publicacion": (r["fecha_publicacion"] or "")[:10],
            "tipo_publicacion": r["tipo_pub"],
            "cuenta": r["cuenta"],
            "sede": r["campus"],
            "facultad": r["facultad"],
            "departamento": r["departamento"],
            "n_likes": r["n_likes"] or 0,
            "sentimiento": sent,
            "sentimiento_etiqueta": _SENT_LABEL.get(sent, sent),
            "prob_pos": round(r["prob_pos"] or 0, 4),
            "prob_neu": round(r["prob_neu"] or 0, 4),
            "prob_neg": round(r["prob_neg"] or 0, 4),
            "emocion": r["emocion"],
            "emocion_etiqueta": ETIQUETAS_EMOCION.get(r["emocion"], r["emocion"]),
            "prob_emocion": round(r["prob_emocion"] or 0, 4) if r["prob_emocion"] else None,
            "tema": tema,
            "tema_etiqueta": ETIQUETAS_TEMA.get(tema, tema),
            "tema_confianza": round(r["tema_confianza"] or 0, 4) if r["tema_confianza"] else None,
            "postura_ucn": post,
            "postura_etiqueta": ETIQUETAS_POSTURA.get(post, post),
            "modelo": r["modelo"],
            "revisado_por_humano": "sí" if any(
                (r["id"], k) in humano for k in ("sentimiento", "emocion", "tema", "postura")
            ) else "no",
            "humano_sentimiento": h_sent,
            "humano_emocion": humano.get((r["id"], "emocion")),
            "humano_tema": h_tema,
            "humano_postura": humano.get((r["id"], "postura")),
            # Salida del modelo ANTES de la corrección (solo en los revisados).
            "_pre_sentimiento": modelo_pre.get((r["id"], "sentimiento")),
            "_pre_emocion": modelo_pre.get((r["id"], "emocion")),
            "_pre_tema": modelo_pre.get((r["id"], "tema")),
            "_pre_postura": modelo_pre.get((r["id"], "postura")),
        })
    return filas, humano


# --------------------------------------------------------------------------- #
# Aviso de PII: nombres propios dentro de los textos
# --------------------------------------------------------------------------- #
# Heurística DELIBERADAMENTE simple: una palabra capitalizada que NO abre la frase.
# Sobre-detecta (marcas, "UCN", días de la semana) y por eso el número se reporta como
# un TECHO, no como un conteo. Sirve para decidir si hace falta una pasada manual, no
# para reemplazarla.
_CAPITALIZADA = re.compile(r"(?<![.!?¡¿]\s)(?<!^)\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\b")
_IGNORAR = {"UCN", "Universidad", "Catolica", "Católica", "Norte", "Antofagasta",
            "Coquimbo", "Chile", "Facultad", "Escuela", "Departamento", "Instituto",
            "Lunes", "Martes", "Miercoles", "Miércoles", "Jueves", "Viernes",
            "Sabado", "Sábado", "Domingo", "Enero", "Febrero", "Marzo", "Abril",
            "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
            "Noviembre", "Diciembre", "Felicidades", "Felicitaciones", "Gracias"}


def _posible_pii(filas: list[dict]) -> tuple[int, list[str]]:
    con_nombre, muestras = 0, Counter()
    for f in filas:
        hits = [w for w in _CAPITALIZADA.findall(f["comentario"] or "")
                if w not in _IGNORAR]
        if hits:
            con_nombre += 1
            muestras.update(hits)
    return con_nombre, [w for w, _ in muestras.most_common(12)]


# --------------------------------------------------------------------------- #
# Escritura
# --------------------------------------------------------------------------- #
def _encabezado(ws, columnas: list[str]) -> None:
    ws.append(columnas)
    for i, _ in enumerate(columnas, start=1):
        c = ws.cell(row=1, column=i)
        c.font = Font(name=FUENTE, bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columnas))}1"


def _anchos(ws, anchos: dict[str, int]) -> None:
    for col, ancho in anchos.items():
        ws.column_dimensions[col].width = ancho


def _hoja_datos(wb: Workbook, filas: list[dict]) -> None:
    # Las `_pre_*` son insumo interno de la hoja de oro; en la de datos serían ruido.
    columnas = [c for c in filas[0] if not c.startswith("_pre_")]
    ws = wb.create_sheet("Comentarios")
    _encabezado(ws, columnas)
    for f in filas:
        ws.append([f[c] for c in columnas])
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.font = Font(name=FUENTE, size=10)
            c.alignment = Alignment(vertical="top", wrap_text=False)
    _anchos(ws, {"A": 7, "B": 8, "C": 18, "D": 52, "E": 60, "F": 12, "G": 10,
                 "H": 26, "I": 13, "J": 30, "K": 30, "L": 8})
    ws.row_dimensions[1].height = 30


def _hoja_oro(wb: Workbook, filas: list[dict]) -> tuple[int, dict]:
    """Los comentarios con etiqueta humana, contra lo que el modelo dijo ANTES.

    ⚠️ La columna `modelo_*` sale de `percepcion_correccion.valor_original`, NO de
    `percepcion_score`. Ese score fue sobrescrito por la corrección, así que en un
    comentario revisado ya contiene la respuesta humana: compararlos daba 99,0 % de
    acuerdo en sentimiento contra el 88,7 % real. Comparar un registro editado consigo
    mismo no mide nada, y produce un número alto que parece un resultado.
    """
    cols = ["id", "fecha", "comentario", "contexto_publicacion",
            "modelo_sentimiento", "humano_sentimiento", "coincide_sentimiento",
            "modelo_emocion", "humano_emocion", "coincide_emocion",
            "modelo_tema", "humano_tema", "coincide_tema",
            "modelo_postura", "humano_postura", "coincide_postura"]
    ws = wb.create_sheet("Patron de oro (humano)")
    _encabezado(ws, cols)

    def _cmp(a, b):
        if not a or not b:
            return ""
        return "sí" if a == b else "NO"

    n = 0
    acuerdo: dict[str, list[int]] = {c: [0, 0] for c in
                                     ("sentimiento", "emocion", "tema", "postura")}
    for f in filas:
        if f["revisado_por_humano"] != "sí":
            continue
        n += 1
        celdas = [f["id"], f["fecha"], f["comentario"], f["contexto_publicacion"]]
        for campo, vigente in (("sentimiento", f["sentimiento"]),
                               ("emocion", f["emocion"]),
                               ("tema", f["tema"]),
                               ("postura", f["postura_ucn"])):
            # Si no hay foto previa, el comentario no fue corregido en ese campo y el
            # valor vigente SÍ es el del modelo.
            del_modelo = f[f"_pre_{campo}"] or vigente
            del_humano = f[f"humano_{campo}"]
            marca = _cmp(del_modelo, del_humano)
            if marca:
                acuerdo[campo][1] += 1
                acuerdo[campo][0] += int(marca == "sí")
            celdas += [del_modelo, del_humano, marca]
        ws.append(celdas)

    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.font = Font(name=FUENTE, size=10)
    _anchos(ws, {"A": 7, "B": 18, "C": 50, "D": 55})
    ws.row_dimensions[1].height = 30
    return n, acuerdo


def _hoja_diccionario(wb: Workbook, filas: list[dict], n_oro: int,
                      acuerdo: dict, pii_n: int, pii_ej: list[str]) -> None:
    ws = wb.create_sheet("Diccionario y metodologia", 0)
    _anchos(ws, {"A": 30, "B": 96})
    fila = 1

    def linea(titulo: str, texto: str = "", bold=False, salto=False):
        nonlocal fila
        if salto:
            fila += 1
        ws.cell(row=fila, column=1, value=titulo).font = Font(
            name=FUENTE, bold=True, size=11 if bold else 10,
            color=AZUL if bold else "000000")
        if texto:
            c = ws.cell(row=fila, column=2, value=texto)
            c.font = Font(name=FUENTE, size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        fila += 1

    linea("PERCEPCIÓN UCN — DATASET", "", bold=True)
    linea("Generado", datetime.now().strftime("%Y-%m-%d %H:%M"))
    linea("Fuente", "percepcion_real.db · comentarios públicos de cuentas públicas de Instagram de la UCN")
    linea("Filas", f"{len(filas)} comentarios · {filas[-1]['fecha'][:10]} es el más reciente")
    linea("Con etiqueta humana", f"{n_oro} comentarios (hoja «Patron de oro»)")

    linea("CUÁNTO CREERLE A CADA COLUMNA", "", bold=True, salto=True)
    linea("", "Medido sobre 150 comentarios de muestra ALEATORIA anotados a mano. "
              "«Clase mayoritaria» es lo que se acertaría diciendo siempre la etiqueta "
              "más frecuente; la diferencia con el acierto es lo que aporta el modelo. "
              "«Techo» es la auto-consistencia del anotador al revisar dos veces el "
              "mismo comentario: nadie puede superarlo.")
    fila += 1
    ws.append(["dimensión", "acierto · kappa · clase mayoritaria · techo"])
    for c in ws[fila]:
        c.font = Font(name=FUENTE, bold=True, size=10)
    fila += 1
    for dim, txt in (
        ("sentimiento", "88,7 % · κ 0,745 · 73,3 % · techo 86,3 % → POR ENCIMA del techo humano"),
        ("emoción", "84,0 % · κ 0,672 · 71,3 % · techo 98,8 %"),
        ("postura", "75,3 % · κ 0,589 · 44,7 % · (regla sola, con entradas correctas: 80,7 %)"),
        ("tema", "55,3 % · κ 0,470 · 32,0 % · techo 92,5 % → el eslabón más débil"),
    ):
        ws.cell(row=fila, column=1, value=dim).font = Font(name=FUENTE, size=10)
        ws.cell(row=fila, column=2, value=txt).font = Font(name=FUENTE, size=10)
        fila += 1

    linea("LA HOJA «PATRON DE ORO» — LEER ANTES DE USARLA", "", bold=True, salto=True)
    linea("", "La columna `modelo_*` de esa hoja NO sale del score vigente, sino de la "
              "foto que se tomó ANTES de corregirlo. Es imprescindible: la curación "
              "SOBRESCRIBE el score con la etiqueta humana, así que en un comentario "
              "revisado el score vigente YA ES la respuesta humana. Compararlos daría "
              "99,0 % de acuerdo en sentimiento — comparar un registro editado consigo "
              "mismo. Es el mismo anclaje que ya invalidó una auditoría completa de este "
              "corpus.")
    fila += 1
    linea("", "Acuerdo modelo–humano recalculado sobre la foto previa, en ESTE archivo:")
    for campo in ("sentimiento", "emocion", "tema", "postura"):
        si, tot = acuerdo.get(campo, [0, 0])
        if tot:
            linea(f"   {campo}", f"{100*si/tot:.1f} %  ({si} de {tot})")
    linea("", "⚠️ Aun así, estos porcentajes NO reemplazan a los oficiales de arriba. "
              "`valor_original` es la foto del modelo en el MOMENTO de cada corrección, "
              "y el modelo cambió después (recalibración NEU→POS de 08-2026). Medir el "
              "modelo de hoy exige RE-PUNTUAR el corpus, que es como se obtuvo el 88,7 %.")

    linea("CÓMO SE PRODUJO CADA COLUMNA", "", bold=True, salto=True)
    for k, v in (
        ("sentimiento", "pysentimiento/RoBERTuito + calibración NEU→POS (umbral 0,18) + reglas de modismos chilenos. POS/NEU/NEG."),
        ("prob_pos/neu/neg", "Probabilidades del modelo. OJO: en los comentarios revisados a mano, la corrección sobrescribió estas probabilidades con sintéticas (0,90/0,05/0,05)."),
        ("emocion", "pysentimiento (RoBERTuito) + reglas. joy, sadness, anger, fear, surprise, humor_ironia, empatia, sin_emocion."),
        ("tema", "Clasificador por palabras clave, taxonomía de 8 clases. NO es un modelo entrenado."),
        ("tema_confianza", "Confianza del matcher. Mediana del corpus 0,45; el 89,5 % está por debajo de 0,7."),
        ("postura_ucn", "DERIVADA, no observada. Regla: NEG→adverso; POS + tema atribuible→favorable; resto→neutral. Temas atribuibles: academico, logros_reconocimientos, servicios_institucionales, bienestar_salud."),
        ("autor_id", "Renumeración 1..N generada en esta exportación. NO es el identificador de la base y no permite cruzarla."),
        ("humano_*", "Etiqueta de un anotador humano. Vacío = no se revisó. Es el patrón de oro."),
        ("revisado_por_humano", "«sí» si al menos una de las cuatro dimensiones tiene etiqueta humana."),
    ):
        linea(k, v)

    linea("ADVERTENCIAS METODOLÓGICAS", "", bold=True, salto=True)
    for t in (
        "El comentario mediano tiene 3 palabras y el 84 % tiene 10 o menos. Métodos bag-of-words (LDA, TF-IDF) son inviables a nivel comentario: solo 211 tipos de palabra superan las 10 apariciones.",
        "El 76,9 % de los autores aparece UNA sola vez (1.474 de 1.916). No hay trayectorias individuales.",
        "Las etiquetas humanas se anotaron sobre muestra aleatoria con semilla fija. Hay además ~2.800 comentarios etiquetados por un agente LLM que NO se incluyen acá: rindieron peor que las humanas (42,7 % vs 49,3 %) y contaminarían el patrón de oro.",
        "«tema» cambió de taxonomía en 08-2026 (de 11 clases a 8). Las etiquetas retiradas aparecen marcadas «(retirado)» o «(fusionado…)».",
        "La postura se deriva del sentimiento y del tema. Como el tema acierta 55,3 %, el error del tema se propaga a la postura.",
    ):
        linea("•", t)

    linea("PRIVACIDAD", "", bold=True, salto=True)
    linea("Autor", "No se exporta ningún identificador de la base. `autor_id` es una renumeración local.")
    linea("Nombres en el texto",
          f"Hasta {pii_n} de {len(filas)} comentarios contienen alguna palabra capitalizada "
          f"que podría ser un nombre propio (heurística que SOBRE-detecta; es un techo, no un conteo). "
          f"Ejemplos frecuentes: {', '.join(pii_ej[:8])}. "
          "Revisar antes de publicar el dataset o de incluirlo en un anexo.")
    linea("Uso", "Datos públicos de cuentas públicas institucionales. Compartir para investigación; "
                 "no re-publicar los textos crudos sin revisar la línea anterior.")


def main() -> None:
    con = _conectar()
    filas, _humano = _cargar(con)
    con.close()
    if not filas:
        print("Sin datos.")
        return

    pii_n, pii_ej = _posible_pii(filas)

    wb = Workbook()
    wb.remove(wb.active)
    _hoja_datos(wb, filas)
    n_oro, acuerdo = _hoja_oro(wb, filas)
    _hoja_diccionario(wb, filas, n_oro, acuerdo, pii_n, pii_ej)
    wb.active = 0

    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / "percepcion_dataset_ucn.xlsx"
    wb.save(destino)

    print(f"OK -> {destino}")
    print(f"   comentarios          : {len(filas)}")
    print(f"   con etiqueta humana  : {n_oro}")
    print("   acuerdo modelo-humano (contra la foto PREVIA a la correccion):")
    for campo in ("sentimiento", "emocion", "tema", "postura"):
        si, tot = acuerdo.get(campo, [0, 0])
        if tot:
            print(f"      {campo:<12} {100*si/tot:5.1f} %  ({si}/{tot})")
    print(f"   posible PII en texto : hasta {pii_n} filas ({100*pii_n/len(filas):.1f} %)")
    print(f"   ejemplos detectados  : {', '.join(pii_ej[:10])}")


if __name__ == "__main__":
    main()
