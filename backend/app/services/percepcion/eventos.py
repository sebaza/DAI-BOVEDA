"""Marcas de contexto del gráfico de percepción: ABM de eventos institucionales.

Un EVENTO es un periodo con nombre que se dibuja como banda en la evolución diaria
(paro, vacaciones/receso, periodo de pruebas, fiestas patrias…). Sirve para LEER el
índice en contexto: una caída durante exámenes no se interpreta igual que una caída
en una semana normal.

⚠️ COINCIDENCIA, NO CAUSALIDAD: la banda muestra que el periodo se solapa con el
tramo, no que lo haya causado. El aviso del panel lo dice explícitamente.

Escribe en la base del WORKER (igual que `curacion`), vía el engine de escritura
(`get_percepcion_write_db`). El lector del dashboard es read-only (query_only=ON).
A diferencia de la curación, esto NO toca la tabla de hechos: los eventos son una
capa de anotación sobre el gráfico, no entran en el cálculo del índice.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.percepcion.models import PercepcionEvento as E

# Tipos con color propio en el gráfico (espejo de COLOR_EVENTO/COLOR_EVENTO_LINEA
# del front). `otro` es el comodín gris para lo que no calce en la taxonomía.
TIPOS_EVENTO: list[dict[str, str]] = [
    # Un semestre es un PERÍODO, no dos hitos sueltos. Antes el calendario cargaba
    # "inicio de clases" y "último día" como eventos de un día cada uno, y en la
    # franja aparecían como dos puntos separados por meses de nada — cuando lo que
    # informa es justamente el tramo que hay entre medio.
    {"tipo": "semestre", "etiqueta": "Período lectivo"},
    {"tipo": "paro", "etiqueta": "Paro / movilización"},
    {"tipo": "toma", "etiqueta": "Toma"},
    {"tipo": "emergencia", "etiqueta": "Emergencia"},
    {"tipo": "examenes", "etiqueta": "Periodo de pruebas"},
    {"tipo": "receso", "etiqueta": "Vacaciones / receso"},
    {"tipo": "fiestas_patrias", "etiqueta": "Fiestas patrias"},
    {"tipo": "cambio_calendario", "etiqueta": "Cambio de calendario"},
    {"tipo": "resolucion", "etiqueta": "Resolución / anuncio"},
    # El duelo hunde el índice de su semana entre 6 y 9 puntos SIN que haya
    # descontento: son condolencias, que el scorer marca negativas con razón (son
    # tristes) pero que expresan aprecio. Necesita etiqueta propia justamente para
    # que la caída se lea como lo que es. Ver `calendario.TIPOS_DUELO`.
    {"tipo": "duelo", "etiqueta": "Duelo"},
    {"tipo": "otro", "etiqueta": "Otro"},
]
_TIPOS_VALIDOS = {t["tipo"] for t in TIPOS_EVENTO}
ETIQUETAS_TIPO = {t["tipo"]: t["etiqueta"] for t in TIPOS_EVENTO}

MAX_NOMBRE = 200
MAX_AMBITO = 120


def _slug_tipo(texto: str) -> str:
    """Normaliza un tipo escrito a mano: minúsculas, sin tildes, guiones_bajos."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:40]


def tipos_disponibles() -> list[dict[str, str]]:
    return list(TIPOS_EVENTO)


def _serializar(e: E) -> dict:
    fin = e.fecha_fin or e.fecha_inicio
    return {
        "id": e.id,
        "nombre": e.nombre,
        "tipo": e.tipo,
        "tipo_label": ETIQUETAS_TIPO.get(e.tipo, e.tipo),
        "fecha_inicio": e.fecha_inicio,
        "fecha_fin": fin,
        "descripcion": e.descripcion,
        "ambito": e.ambito,
        # `getattr` porque una base anterior a la migración de esta columna devuelve
        # el modelo sin ella, y el ABM no debe caerse por eso.
        "confianza": getattr(e, "confianza", None),
    }


def listar(db: Session) -> dict:
    """TODOS los eventos (sin filtrar por ventana): es la vista de administración."""
    filas = db.execute(select(E).order_by(E.fecha_inicio.desc())).scalars().all()
    return {"items": [_serializar(e) for e in filas]}


def _validar(
    nombre: str, tipo: str, fecha_inicio: date, fecha_fin: date | None
) -> tuple[str, str, date, date]:
    """Reglas duras del ABM. Devuelve los campos ya normalizados."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacío.")
    if len(nombre) > MAX_NOMBRE:
        raise ValueError(f"El nombre no puede superar {MAX_NOMBRE} caracteres.")
    tipo = _slug_tipo(tipo) or "otro"
    if tipo not in _TIPOS_VALIDOS:
        raise ValueError(f"Tipo inválido: {tipo}. Válidos: {', '.join(sorted(_TIPOS_VALIDOS))}.")
    if fecha_inicio is None:
        raise ValueError("La fecha de inicio es obligatoria.")
    # Un evento de un solo día se guarda con fin = inicio (el gráfico igual lo dibuja).
    fin = fecha_fin or fecha_inicio
    if fin < fecha_inicio:
        raise ValueError("La fecha de fin no puede ser anterior a la de inicio.")
    return nombre, tipo, fecha_inicio, fin


def crear(
    db: Session, *, nombre: str, tipo: str, fecha_inicio: date,
    fecha_fin: date | None = None, descripcion: str | None = None,
    ambito: str | None = None,
) -> dict:
    nombre, tipo, ini, fin = _validar(nombre, tipo, fecha_inicio, fecha_fin)
    evento = E(
        nombre=nombre, tipo=tipo, fecha_inicio=ini, fecha_fin=fin,
        descripcion=(descripcion or "").strip() or None,
        ambito=(ambito or "").strip()[:MAX_AMBITO] or None,
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return _serializar(evento)


def actualizar(
    db: Session, evento_id: int, *, nombre: str, tipo: str, fecha_inicio: date,
    fecha_fin: date | None = None, descripcion: str | None = None,
    ambito: str | None = None,
) -> dict:
    evento = db.get(E, evento_id)
    if evento is None:
        raise LookupError(f"No existe el evento {evento_id}.")
    nombre, tipo, ini, fin = _validar(nombre, tipo, fecha_inicio, fecha_fin)
    evento.nombre = nombre
    evento.tipo = tipo
    evento.fecha_inicio = ini
    evento.fecha_fin = fin
    evento.descripcion = (descripcion or "").strip() or None
    evento.ambito = (ambito or "").strip()[:MAX_AMBITO] or None
    db.commit()
    db.refresh(evento)
    return _serializar(evento)


def eliminar(db: Session, evento_id: int) -> dict:
    evento = db.get(E, evento_id)
    if evento is None:
        raise LookupError(f"No existe el evento {evento_id}.")
    db.delete(evento)
    db.commit()
    return {"eliminado": True, "id": evento_id}
