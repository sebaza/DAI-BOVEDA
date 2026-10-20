"""Carga del CALENDARIO ACADÉMICO UCN a `percepcion_evento` (Fase 0.1 del plan).

Por qué existe: sin causas registradas, ningún modelo puede explicar la percepción.
`percepcion_evento` tenía **una** fila; el corpus tiene cuatro años de historia con
matrículas, recesos, exámenes y ocho movilizaciones. El calendario es la variable
causal más obvia y era la única que faltaba.

QUÉ VALIDÓ ESTE CALENDARIO APENAS ENTRÓ
---------------------------------------
El análisis estacional del corpus había detectado dos picos sin explicación:

* **octubre, 11,2 % de negativos** — el segundo del año. El calendario lo resuelve:
  paralización en oct-2023, la gran toma de oct-2024 y el paro por Salud Mental de
  oct-2025. Tres años seguidos con conflicto en octubre.
* **junio-julio, la mayor concentración de léxico de conflicto** — el paro de Derecho
  Coquimbo (may-jul 2025) y la toma de Antofagasta (jun-jul 2026).

O sea: el corpus ya venía marcando estos eventos sin saber cómo se llamaban.

LA REGLA QUE GOBIERNA TODO ESTE ARCHIVO
---------------------------------------
    calendario_oficial != calendario_real

El paro de octubre 2024 extendió el semestre de Antofagasta **hasta enero de 2025**, y
el de junio 2026 corrió el cierre del primer semestre del 4 de julio al 1 de agosto.
Cuando hubo recalendarización se cargan **las dos** fechas —la programada y la
efectiva—, distinguidas por `confianza` y por el ámbito. Un modelo entrenado contra el
calendario oficial de esos años aprendería un semestre que no ocurrió.

EL CALENDARIO ESTÁ INCOMPLETO POR DEFECTO — Y EL CORPUS LO DELATA
-----------------------------------------------------------------
La auditoría de sept-2026 encontró **una paralización de tres semanas (20-04 a
08-05-2026) que no estaba cargada**: entre marzo y junio de ese año el calendario no
tenía ni un solo evento de conflicto, mientras las semanas del 27-04, 04-05 y 11-05
caían −10,6 / −12,7 / −15,2 contra el promedio de su año, con la negatividad más alta
de todo el corpus. La causa estaba a la vista en los captions —«votaciones de
revalidación de paralización de actividades», «17 carreras decidieron permanecer»— y
en los comentarios («primera semana después del paro de 2 semanas»).

**Método para encontrar los que faltan**, que conviene repetir cada tanto: cruzar las
semanas con índice anómalo contra los eventos cargados; donde hay caída y no hay
evento, leer los captions de esa semana. El corpus documenta los hechos aunque el
calendario oficial no los registre.

CONFIANZA: NO TODAS LAS FECHAS VALEN LO MISMO
---------------------------------------------
La fuente marca explícitamente varios casos sin verificar ("la duración efectiva del
paro no está documentada", "fechas exactas no verificadas", "término no confirmado").
Esas entran como `estimado`, y **cualquier análisis de duración tiene que excluirlas**
o va a medir una suposición. `confirmado` es fecha documentada; `planificado` es
calendario futuro que todavía puede moverse.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.config import BASE_DIR
from app.services.percepcion.models import PercepcionEvento

RUTA_CALENDARIO = Path(BASE_DIR) / "backend" / "app" / "data" / "percepcion_calendario_ucn.json"

# Tipos que representan una INTERRUPCIÓN de la actividad normal. Son los que sirven
# para medir respuesta a shock (pregunta C del plan); el resto es ritmo académico.
TIPOS_DISRUPTIVOS = frozenset({"paro", "toma", "emergencia"})

# DUELO: publicaciones de condolencia por una muerte en la comunidad —personas y
# también mascotas del campus, que en este corpus pesan igual o más—.
#
# NO es disruptivo (no interrumpe la actividad) y por eso va aparte, pero necesita
# marca propia porque **hunde el índice de su semana entre 6 y 9 puntos**: el scorer
# clasifica «QEPD» (prob_neg 0,71), «Descanse en paz profe 🕊️» (0,57) y «😢» (0,81)
# como NEGATIVOS. En el registro emocional acierta —son mensajes tristes—, pero lo
# que expresan es aprecio por la institución y su gente, o sea lo contrario de lo
# que el tablero va a reportar.
#
# Medido sobre `percepcion_real.db` (auditoría de sept-2026): 6 episodios, ~275
# comentarios, índice de los posts entre 27 y 47 contra 65,4 del corpus. La semana
# del 17-08-2026 pasa de 57,5 a 63,9 excluyéndolos; la del 13-04-2026, de 59,5 a 68,9.
#
# El de abril 2026 se solapa con la paralización: sin separarlos, las dos causas se
# confunden en la misma caída.
TIPOS_DUELO = frozenset({"duelo"})

# Tipos que EXPLICAN una caída del índice sin que haya descontento institucional.
# Hoy solo el duelo; si aparece otro (una catástrofe regional, por ejemplo) va acá.
TIPOS_NO_ADVERSOS = TIPOS_DUELO

# Marca de procedencia. Las filas con esta fuente vienen del JSON versionado, así que
# la carga puede sincronizarlas — incluso borrar las que ya no existen en el archivo.
# Las que cargó una persona desde el ABM llevan `fuente=NULL` y **nunca se tocan**:
# sin esa separación, corregir el calendario borraría trabajo ajeno en silencio.
FUENTE_CALENDARIO = "calendario_ucn"


def _ruta() -> Path:
    """La ruta del JSON, tolerante al aplanado del contenedor.

    En Cloud Run el Dockerfile aplana `backend/app` a `/app/app`, así que `BASE_DIR`
    resuelve a `/` y la ruta de desarrollo no existe. Mismo patrón que ya usan muestra
    y scripts vendorizados.
    """
    if RUTA_CALENDARIO.exists():
        return RUTA_CALENDARIO
    alterna = Path(BASE_DIR) / "app" / "data" / "percepcion_calendario_ucn.json"
    if alterna.exists():
        return alterna
    # Último recurso: relativo a este archivo. Sobrevive a cualquier reacomodo.
    return Path(__file__).resolve().parents[1] / "data" / "percepcion_calendario_ucn.json"


def leer_calendario(ruta: Path | None = None) -> list[dict]:
    """Los eventos del JSON, ya con `date` en vez de texto."""
    destino = ruta or _ruta()
    if not destino.exists():
        return []
    with destino.open("r", encoding="utf-8") as fh:
        crudo = json.load(fh)
    eventos = []
    for e in crudo.get("eventos") or []:
        fin = e.get("fecha_fin")
        eventos.append({
            "nombre": e["nombre"],
            "tipo": e.get("tipo") or "otro",
            "fecha_inicio": date.fromisoformat(e["fecha_inicio"]),
            "fecha_fin": date.fromisoformat(fin) if fin else None,
            "ambito": e.get("ambito") or "global",
            "confianza": e.get("confianza") or "estimado",
            "descripcion": e.get("descripcion"),
            "fuente": FUENTE_CALENDARIO,
        })
    return eventos


_CAMPOS_ACTUALIZABLES = ("tipo", "fecha_fin", "ambito", "confianza", "descripcion", "fuente")


def cargar(db, *, ruta: Path | None = None, dry_run: bool = False,
           sincronizar: bool = True) -> dict:
    """Carga el calendario. IDEMPOTENTE: la clave natural es (nombre, fecha_inicio).

    Deduplicar por nombre+fecha y no por nombre a secas es deliberado: "Semana Mechona"
    se repite todos los años y son eventos distintos. Y no por id, porque el JSON no
    tiene ids y la carga tiene que poder repetirse sin acumular basura.

    Un evento que ya existe se ACTUALIZA (fin, ámbito, confianza, descripción): si la
    fuente corrige la fecha de término de un paro estimado, la corrección tiene que
    llegar sin borrar y recargar todo.

    `sincronizar=True` además RETIRA las filas del calendario que ya no están en el
    archivo. Hizo falta al fusionar los hitos "inicio de clases" y "último día" en un
    único período lectivo: sin esto, los 20 hitos viejos quedaban huérfanos en la base
    conviviendo con los períodos nuevos, y la franja mostraba las dos versiones.

    ⚠️ El borrado se limita a `fuente == FUENTE_CALENDARIO`. Los eventos cargados a
    mano desde el panel tienen `fuente` NULL y quedan intactos — si el barrido no
    filtrara por fuente, recargar el calendario borraría trabajo de otra persona.
    """
    eventos = leer_calendario(ruta)
    existentes = {
        (e.nombre, e.fecha_inicio): e
        for e in db.execute(select(PercepcionEvento)).scalars().all()
    }

    nuevos, actualizados = 0, 0
    for ev in eventos:
        clave = (ev["nombre"], ev["fecha_inicio"])
        actual = existentes.get(clave)
        if actual is None:
            nuevos += 1
            if not dry_run:
                db.add(PercepcionEvento(**ev))
            continue
        cambios = any(
            getattr(actual, campo, None) != ev[campo] for campo in _CAMPOS_ACTUALIZABLES
        )
        if cambios:
            actualizados += 1
            if not dry_run:
                for campo in _CAMPOS_ACTUALIZABLES:
                    setattr(actual, campo, ev[campo])

    retirados = 0
    if sincronizar:
        del_archivo = {(ev["nombre"], ev["fecha_inicio"]) for ev in eventos}
        for clave, fila in existentes.items():
            if clave in del_archivo:
                continue
            if getattr(fila, "fuente", None) != FUENTE_CALENDARIO:
                continue   # cargado a mano: no es nuestro, no se toca
            retirados += 1
            if not dry_run:
                db.delete(fila)

    if not dry_run:
        db.commit()

    return {
        "dry_run": dry_run,
        "en_archivo": len(eventos),
        "nuevos": nuevos,
        "actualizados": actualizados,
        "retirados": retirados,
        "sin_cambios": len(eventos) - nuevos - actualizados,
        "disruptivos": sum(1 for e in eventos if e["tipo"] in TIPOS_DISRUPTIVOS),
        "por_confianza": {
            c: sum(1 for e in eventos if e["confianza"] == c)
            for c in ("confirmado", "estimado", "planificado")
        },
    }


def episodios_duelo(db) -> list[dict]:
    """Los episodios de duelo, para poder explicar (o descontar) su caída.

    Se lee igual que `episodios_disruptivos` pero son la otra cara: ahí el índice
    baja porque algo anda mal, acá baja porque la comunidad está despidiendo a
    alguien. Confundirlos es leer un homenaje como una crisis. Ver `TIPOS_DUELO`.
    """
    filas = db.execute(
        select(PercepcionEvento)
        .where(PercepcionEvento.tipo.in_(sorted(TIPOS_DUELO)))
        .order_by(PercepcionEvento.fecha_inicio)
    ).scalars().all()
    return [
        {
            "nombre": e.nombre,
            "desde": e.fecha_inicio,
            "hasta": e.fecha_fin,
            "ambito": e.ambito,
            "confianza": e.confianza or "estimado",
            "descripcion": e.descripcion,
        }
        for e in filas
    ]


def episodios_disruptivos(db, *, solo_confirmados: bool = False) -> list[dict]:
    """Los episodios contra los cuales se puede medir respuesta a shock (pregunta C).

    `solo_confirmados=True` deja fuera los de fechas estimadas. Es lo que hay que usar
    para medir DURACIÓN o velocidad de recuperación: con fechas aproximadas, esos dos
    números miden la suposición y no el hecho.
    """
    filas = db.execute(
        select(PercepcionEvento)
        .where(PercepcionEvento.tipo.in_(sorted(TIPOS_DISRUPTIVOS)))
        .order_by(PercepcionEvento.fecha_inicio)
    ).scalars().all()
    out = []
    for e in filas:
        if solo_confirmados and (e.confianza or "estimado") != "confirmado":
            continue
        out.append({
            "nombre": e.nombre,
            "tipo": e.tipo,
            "desde": e.fecha_inicio,
            "hasta": e.fecha_fin,
            "ambito": e.ambito,
            "confianza": e.confianza or "estimado",
            "dias": ((e.fecha_fin - e.fecha_inicio).days + 1) if e.fecha_fin else None,
        })
    return out
