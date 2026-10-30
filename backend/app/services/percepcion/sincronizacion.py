"""Sincronización INCREMENTAL del SQLite del worker hacia la Bóveda (lógica pura, sin CLI).

Contrato
--------
* SOLO INSERTA filas cuyo `id` no existe en el destino. Nunca hace UPDATE: así no se pisa
  el `tema`/`tema_confianza` curado ni nada editado en la Bóveda.
* Tablas, en orden de claves foráneas: cuenta, publicación, comentario, score, evento.
  NO toca correcciones, resúmenes, temas custom, hechos (salvo la reagregación de abajo),
  contexto ni derivadas (salvo `derivados.reconstruir`).
* Guardas de consistencia (aborta TODO antes de escribir; solo se informan conteos):
  - mismo `id` en ambos lados con distinta clave natural;
  - fila nueva cuya clave natural ya existe en el destino bajo otro `id`;
  - fila nueva que apunta a un padre que no existe ni en el destino ni entre las nuevas.
* Después de insertar, reagrega `percepcion_hecho_diario` con `curacion.reagregar`
  (respeta la curación porque lee `comentario.tema`) y reconstruye tokens/familias/rasgos,
  todo en la MISMA transacción. Quien llama confirma o revierte; este módulo no hace commit.
* Cifrado: con claves configuradas (`cripto.hay_clave()`), `texto` y `caption` de las filas
  NUEVAS se insertan cifrados (el contexto usa el `id`, que se copia del worker). Sin claves se
  insertan en claro y `Resultado.sin_cifrar` cuenta cuántos valores quedaron así (solo el conteo).
  Las guardas de clave natural nunca leen ni comparan texto.
* Almacén institucional (fase A3): si el destino tiene las marcas `autor_seudonimizado=true` y
  `ext_comentario_seudonimizado=true` en `percepcion_meta` (las escribe
  `scripts/publicar_warehouse_percepcion.py`), el `autor_hash` y el `external_id` de los comentarios
  NUEVOS pasan por `cripto.seudonimo_autor` / `cripto.seudonimo_ext_comentario` antes de
  insertarse, igual que en la carga inicial. La clave natural (publicacion_id, external_id) del
  origen se compara YA seudonimizada contra la del destino, así la detección de duplicados y de
  conflictos sigue funcionando. Sin marcas, se copia tal cual (base local). Una sola marca
  presente = base inconsistente: se NIEGA (`MarcasInconsistentes`). Con marcas y sin
  `PERCEPCION_CLAVE_ID` se NIEGA (`ClaveNoConfigurada`) antes de escribir: mezclaría dos criterios
  en la misma columna. Nunca se aplica dos veces: solo se transforman filas que vienen del worker
  (SQLite), y las que ya están en el destino no se tocan.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.services.percepcion import cripto, curacion, derivados
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionCuenta,
    META_AUTOR_SEUDONIMIZADO,
    META_EXT_COMENTARIO_SEUDONIMIZADO,
    PercepcionEvento,
    PercepcionMeta,
    PercepcionPublicacion,
    PercepcionScore,
)

LOTE = 1000

# tabla -> (columna con texto crudo, función que la cifra con el id de la fila)
_CIFRABLES = {
    "percepcion_comentario": ("texto", cripto.cifrar_texto),
    "percepcion_publicacion": ("caption", cripto.cifrar_caption),
}

# (modelo, columnas de la clave natural, padres [(columna, tabla padre)])
_TABLAS = [
    (PercepcionCuenta, ("handle",), []),
    (PercepcionPublicacion, ("cuenta_id", "external_id"), [("cuenta_id", "percepcion_cuenta")]),
    (PercepcionComentario, ("publicacion_id", "external_id"),
     [("publicacion_id", "percepcion_publicacion")]),
    (PercepcionScore, ("comentario_id",), [("comentario_id", "percepcion_comentario")]),
    (PercepcionEvento, ("nombre", "fecha_inicio"), []),
]


class ConflictoSincronizacion(Exception):
    """Inconsistencia entre origen y destino. Solo lleva conteos por tabla (nunca datos)."""

    def __init__(self, conflictos: dict[str, int]):
        self.conflictos = conflictos
        super().__init__("Conflictos de consistencia: " + ", ".join(
            f"{t}={n}" for t, n in conflictos.items()))


@dataclass
class Resultado:
    insertados: dict[str, int] = field(default_factory=dict)
    conflictos: dict[str, int] = field(default_factory=dict)
    hechos: int | None = None
    derivados: dict[str, int] | None = None
    sin_cifrar: int = 0   # valores de texto/caption insertados en claro por falta de claves
    autor_seudonimizado: bool = False   # el destino lleva la marca: autor_hash nuevo seudonimizado
    autores_seudonimizados: int = 0     # filas nuevas cuyo autor_hash se seudonimizó


class MarcasInconsistentes(Exception):
    """El destino tiene solo una de las dos marcas del almacén. No lleva datos."""


def destino_seudonimizado(destino: Session) -> bool:
    """¿El destino es el almacén (marcas `autor_seudonimizado` y `ext_comentario_seudonimizado`)?

    Una base sin la tabla (la local, anterior a la fase A3) o sin ninguna fila no está marcada.
    Con SOLO una de las dos marcas lanza `MarcasInconsistentes`: ni copiar tal cual ni
    seudonimizar es seguro.
    """
    if not inspect(destino.connection()).has_table(PercepcionMeta.__tablename__):
        return False
    valores = {c: v for c, v in destino.execute(select(PercepcionMeta.clave, PercepcionMeta.valor).where(
        PercepcionMeta.clave.in_([META_AUTOR_SEUDONIMIZADO, META_EXT_COMENTARIO_SEUDONIMIZADO])))}
    activas = [(valores.get(k) or "").strip().lower() == "true"
               for k in (META_AUTOR_SEUDONIMIZADO, META_EXT_COMENTARIO_SEUDONIMIZADO)]
    if any(activas) and not all(activas):
        raise MarcasInconsistentes(
            "El destino tiene solo una de las marcas de seudonimización "
            f"({META_AUTOR_SEUDONIMIZADO}, {META_EXT_COMENTARIO_SEUDONIMIZADO}): se niega la "
            "sincronización. Recarga el almacén con scripts/publicar_warehouse_percepcion.py --reemplazar.")
    return all(activas)


def _columnas(modelo, origen: Session, destino: Session) -> list[str]:
    """Columnas del modelo presentes en AMBAS bases (una base vieja puede carecer de alguna)."""
    def _de(s: Session) -> set[str]:
        return {c["name"] for c in inspect(s.connection()).get_columns(modelo.__tablename__)}
    comunes = _de(origen) & _de(destino)
    return [c.name for c in modelo.__table__.columns if c.name in comunes]


def _claves(s: Session, modelo, nat: tuple[str, ...], transformar: dict | None = None) -> dict[int, tuple]:
    """{id: clave natural} leyendo SOLO id y la clave (jamás texto).

    `transformar` = {columna: función} se aplica a esa parte de la clave (la usa el origen cuando
    el destino guarda el `external_id` de comentarios seudonimizado).
    """
    t = modelo.__table__
    cols = [t.c.id] + [t.c[n] for n in nat]
    fns = [(transformar or {}).get(n) for n in nat]
    if not any(fns):
        return {f[0]: tuple(f[1:]) for f in s.execute(select(*cols))}
    cache: dict = {}

    def _t(fn, v):
        if fn is None:
            return v
        k = (fn, v)
        if k not in cache:
            cache[k] = fn(v)
        return cache[k]
    return {f[0]: tuple(_t(fn, v) for fn, v in zip(fns, f[1:])) for f in s.execute(select(*cols))}


def _planificar(origen: Session, destino: Session, seudonimizar: bool = False):
    """Devuelve (ids nuevos por tabla, conflictos por tabla)."""
    nuevos: dict[str, list[int]] = {}
    conflictos: dict[str, int] = {}
    ids_destino: dict[str, set[int]] = {}
    ids_origen: dict[str, dict[int, tuple]] = {}
    for modelo, nat, padres in _TABLAS:
        nombre = modelo.__tablename__
        transf = ({"external_id": cripto.seudonimo_ext_comentario}
                  if seudonimizar and modelo is PercepcionComentario else None)
        src = _claves(origen, modelo, nat, transf)
        dst = _claves(destino, modelo, nat)
        ids_origen[nombre] = src
        ids_destino[nombre] = set(dst)
        por_clave = {k: i for i, k in dst.items()} if nat else {}
        n_conf = 0
        ids_nuevos: list[int] = []
        for id_, clave in src.items():
            if id_ in dst:
                if nat and dst[id_] != clave:
                    n_conf += 1
            else:
                if nat and clave in por_clave:
                    n_conf += 1
                else:
                    ids_nuevos.append(id_)
        nuevos[nombre] = sorted(ids_nuevos)
        if n_conf:
            conflictos[nombre] = n_conf

    # Huérfanos: el padre de una fila nueva debe existir en el destino o entre las nuevas.
    for modelo, _nat, padres in _TABLAS:
        nombre = modelo.__tablename__
        for columna, padre in padres:
            validos = ids_destino[padre] | set(nuevos[padre])
            t = modelo.__table__
            huerfanos = 0
            if nuevos[nombre]:
                nuevos_set = set(nuevos[nombre])
                for id_, fk in origen.execute(select(t.c.id, t.c[columna])):
                    if id_ in nuevos_set and fk not in validos:
                        huerfanos += 1
            if huerfanos:
                conflictos[nombre] = conflictos.get(nombre, 0) + huerfanos
    return nuevos, conflictos


def _reiniciar_secuencias(destino: Session, tablas: list[str]) -> None:
    """Deja cada secuencia de `id` en max(id)+1 (solo Postgres)."""
    if destino.get_bind().dialect.name != "postgresql":
        return
    for nombre in tablas:
        destino.execute(
            text("SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                 f'COALESCE((SELECT MAX(id) FROM "{nombre}"), 0) + 1, false) '
                 "WHERE pg_get_serial_sequence(:t, 'id') IS NOT NULL"),
            {"t": nombre},
        )


def _destino_tiene_cifrados(destino: Session, nuevos: dict[str, list[int]]) -> bool:
    """Sonda barata: ¿alguna fila del destino ya tiene la forma `enc:...`? (solo si hay filas nuevas)"""
    for modelo, _nat, _p in _TABLAS:
        cifrable = _CIFRABLES.get(modelo.__tablename__)
        if not cifrable or not nuevos[modelo.__tablename__]:
            continue
        col = modelo.__table__.c[cifrable[0]]
        if destino.execute(select(modelo.__table__.c.id).where(col.like("enc:%")).limit(1)).first():
            return True
    return False


def sincronizar(origen: Session, destino: Session, *, simular: bool = False,
                con_derivados: bool = True, permitir_claro: bool = False) -> Resultado:
    """Inserta en `destino` lo que `origen` tiene de más. NO hace commit.

    `simular=True` calcula y devuelve los conteos (y los conflictos, sin lanzar) sin escribir
    ni leer texto del destino. Fuera de simulación, un conflicto lanza `ConflictoSincronizacion`
    antes de insertar nada.

    Sin clave configurada y con filas YA cifradas en el destino se NIEGA (`ClaveNoConfigurada`):
    insertaría en claro y dejaría la base en un estado mixto. `permitir_claro=True` lo permite.
    """
    seudonimizar = destino_seudonimizado(destino)
    if seudonimizar:
        # Falla ANTES de planificar o escribir: sin la clave no hay criterio coherente posible.
        cripto.seudonimo_autor("verificacion")
    nuevos, conflictos = _planificar(origen, destino, seudonimizar)
    res = Resultado(insertados={m.__tablename__: len(nuevos[m.__tablename__]) for m, _, _ in _TABLAS},
                    conflictos=conflictos, autor_seudonimizado=seudonimizar)
    if simular:
        return res
    if conflictos:
        raise ConflictoSincronizacion(conflictos)
    if not permitir_claro and not cripto.hay_clave() and _destino_tiene_cifrados(destino, nuevos):
        raise cripto.ClaveNoConfigurada(
            f"{cripto.VAR_CLAVE_TEXTO} no está configurada pero el destino ya tiene texto cifrado: "
            "insertar en claro dejaría la base mezclada (usa permitir_claro / --permitir-claro "
            "solo si es lo que quieres).")

    for modelo, _nat, _padres in _TABLAS:
        ids = nuevos[modelo.__tablename__]
        if not ids:
            continue
        t = modelo.__table__
        columnas = _columnas(modelo, origen, destino)
        for i in range(0, len(ids), LOTE):
            lote = ids[i:i + LOTE]
            filas = [dict(f._mapping) for f in origen.execute(
                select(*[t.c[c] for c in columnas]).where(t.c.id.in_(lote)).order_by(t.c.id))]
            if seudonimizar and modelo is PercepcionComentario:
                for fila in filas:
                    if "autor_hash" in fila:
                        fila["autor_hash"] = cripto.seudonimo_autor(fila["autor_hash"])
                    if "external_id" in fila:
                        fila["external_id"] = cripto.seudonimo_ext_comentario(fila["external_id"])
                    res.autores_seudonimizados += 1
            cifrable = _CIFRABLES.get(modelo.__tablename__)
            if cifrable and cifrable[0] in columnas:
                col, cifrar_valor = cifrable
                contexto_de = (cripto.contexto_comentario if col == "texto"
                               else cripto.contexto_publicacion)
                con_clave = cripto.hay_clave()
                for fila in filas:
                    valor = fila[col]
                    # Ya cifrado de verdad (descifra con su AAD): no se cifra dos veces. Algo con la
                    # forma `enc:...` que no descifra es texto en claro y se cifra.
                    if not valor or (con_clave and cripto.es_genuino(valor, contexto_de(fila["id"]))):
                        continue
                    if con_clave:
                        fila[col] = cifrar_valor(fila["id"], valor)
                    else:
                        res.sin_cifrar += 1
            destino.execute(t.insert(), filas)
    destino.flush()
    _reiniciar_secuencias(destino, [m.__tablename__ for m, _, _ in _TABLAS])

    if con_derivados:
        res.hechos = curacion.reagregar(destino, confirmar=False)
        # La tabla de etiquetas es nueva: una base anterior todavía no la tiene.
        from app.services.percepcion.models import PercepcionComentarioEtiqueta
        PercepcionComentarioEtiqueta.__table__.create(bind=destino.connection(), checkfirst=True)
        res.derivados = derivados.reconstruir(destino)
    return res


def _json(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return str(valor)


def respaldar(destino: Session, carpeta: Path, *, ahora: datetime | None = None) -> Path:
    """Exporta lo curado en la Bóveda (correcciones y nombres manuales de subtemas) a JSON.

    Sirve para recuperarse si algo sale mal. NUNCA incluye texto de comentarios. Las
    correcciones traen `justificacion` y `autor`, texto escrito por administradores: el
    archivo es local y está en .gitignore (`backend/respaldos/`).
    """
    ahora = ahora or datetime.now(timezone.utc)
    insp = inspect(destino.connection())
    pedidas = {
        "percepcion_correccion": None,  # todas sus columnas (no tiene texto de comentarios)
        "percepcion_subtema": ["id", "tema", "etiqueta", "etiqueta_manual",
                               "renombrado_por", "renombrado_en"],
    }
    datos: dict = {"generado_en": ahora.isoformat(), "conteos": {}}
    for tabla, cols in pedidas.items():
        if not insp.has_table(tabla):
            datos[tabla], datos["conteos"][tabla] = [], 0
            continue
        existentes = [c["name"] for c in insp.get_columns(tabla)]
        usar = existentes if cols is None else [c for c in cols if c in existentes]
        filas = [dict(f._mapping) for f in destino.execute(
            text("SELECT " + ", ".join(f'"{c}"' for c in usar) + f' FROM "{tabla}"'))]
        datos[tabla] = filas
        datos["conteos"][tabla] = len(filas)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"sync-{ahora.strftime('%Y%m%dT%H%M%SZ')}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1, default=_json), encoding="utf-8")
    return ruta
