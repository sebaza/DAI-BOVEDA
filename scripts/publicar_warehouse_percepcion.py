"""Carga la base de Percepción de la Bóveda (Postgres) al almacén institucional (fase A3).

QUÉ HACE
--------
Copia TODAS las tablas `percepcion_*` de los modelos (curación y estado incluidos) desde el
Postgres actual de la Bóveda (`--origen`) al esquema `percepcion` del almacén (`--destino`),
que pasa a ser la base PRIMARIA de Percepción. Todo en UNA transacción: si algo falla no queda
nada a medias. Reutiliza los ayudantes de `migrar_percepcion_postgres.py` (tablas en orden de
claves foráneas, columnas comunes, validación de largos, INSERT tipado, secuencias).

TRANSFORMACIONES (las únicas)
-----------------------------
* `percepcion_comentario.autor_hash` -> `cripto.seudonimo_autor(...)` = HMAC-SHA256 con
  `PERCEPCION_CLAVE_ID`, dominio "autor". Determinista: los conteos de autores distintos (umbrales
  anti-PII de subtemas, concentración) no cambian. El `external_id` NO se toca (clave natural de
  la sincronización con el worker).
* `percepcion_comentario.texto` y `percepcion_publicacion.caption` NO se transforman: deben llegar
  como cifrado AUTÉNTICO (descifra con su AAD y la clave). Si alguna fila no lo es, la carga se
  NIEGA (solo conteos) salvo `--permitir-claro`.
* `percepcion_comentario.external_id` -> `cripto.seudonimo_ext_comentario(...)` (dominio
  "comentario_ext"): con el id original se llega al autor público del comentario. El de
  publicaciones y el `handle` de cuentas (datos institucionales públicos) no se tocan.
* Se escriben las marcas `autor_seudonimizado=true` y `ext_comentario_seudonimizado=true` en
  `percepcion_meta`: `sincronizacion.py` las lee y seudonimiza también los comentarios nuevos (un
  solo criterio, sin doble aplicación; con una sola marca se niega). Esa tabla nunca se copia
  desde el origen; si el ORIGEN ya trae alguna marca, se niega (aplicaría el seudónimo dos veces).

SEGURIDAD
---------
* Exige `PERCEPCION_CLAVE_TEXTO` y `PERCEPCION_CLAVE_ID` (también en `--dry-run`).
* El origen se lee en UNA instantánea (REPEATABLE READ, solo lectura): cifrado, copia y validación
  ven los mismos datos. Antes de empezar se comprueba que origen y destino no sean la misma
  instancia/base (normalizando host y puerto, y consultando al servidor).
* Las URLs vienen de `--origen`/`--destino` o de `PERCEPCION_ADMIN_DATABASE_URL` /
  `PERCEPCION_WH_DATABASE_URL`, y NUNCA se imprimen. El origen se lee en transacción de solo lectura.
* Imprime solo nombres de tabla/columna y conteos; jamás valores. Un error inesperado muestra
  solo la clase de la excepción.
* Si alguna tabla del destino ya tiene filas se NIEGA, salvo `--reemplazar` (las vacía y recarga:
  sobrescribe lo escrito en el almacén).

Código de salida: 0 ok; 1 falla (cifrado, conteos, destino con datos, error); 2 uso/configuración
(faltan URLs o claves).

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts/publicar_warehouse_percepcion.py --dry-run
    backend\\.venv\\Scripts\\python.exe -I scripts/publicar_warehouse_percepcion.py
    backend\\.venv\\Scripts\\python.exe -I scripts/publicar_warehouse_percepcion.py --reemplazar
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
# `python -I` no agrega el directorio del script ni el cwd al sys.path.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import String, bindparam, create_engine, inspect, text  # noqa: E402
from sqlalchemy.engine import Connection, Engine, make_url  # noqa: E402

from app.services.percepcion import cripto  # noqa: E402
from app.services.percepcion.models import (  # noqa: E402
    MARCAS_ALMACEN,
    META_AUTOR_SEUDONIMIZADO,
    META_EXT_COMENTARIO_SEUDONIMIZADO,
    PercepcionMeta,
)
from app.services.percepcion.pg import ESQUEMA_PERCEPCION, url_con_esquema  # noqa: E402


def _cargar_migrar():
    """El script de migración SQLite->Postgres como módulo (`scripts/` no es un paquete)."""
    ruta = Path(__file__).resolve().parent / "migrar_percepcion_postgres.py"
    spec = importlib.util.spec_from_file_location("migrar_percepcion_postgres", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mig = _cargar_migrar()

VAR_ORIGEN = "PERCEPCION_ADMIN_DATABASE_URL"
VAR_DESTINO = "PERCEPCION_WH_DATABASE_URL"
LOTE_POR_DEFECTO = 1000
TABLA_META = PercepcionMeta.__tablename__
_NOMBRE_ESQUEMA = re.compile(r"^[a-z_][a-z0-9_]*$")

# tabla -> (columna cifrada, función que arma el AAD con el id de la fila)
COLUMNAS_CIFRADAS = {
    "percepcion_comentario": ("texto", cripto.contexto_comentario),
    "percepcion_publicacion": ("caption", cripto.contexto_publicacion),
}

# Columnas que NO son autor_hash pero podrían identificar o delatar contenido. Se informan con
# su conteo de filas no nulas para que la persona responsable decida; la carga NO las modifica.
COLUMNAS_A_REVISAR = {
    "percepcion_correccion.autor": "correo del administrador que revisó (no es de un comentarista)",
    "percepcion_correccion.justificacion": "texto libre de administradores; puede citar comentarios",
    "percepcion_subtema.renombrado_por": "correo del administrador que renombró",
    "percepcion_subtema.etiqueta_manual": "nombre escrito por un administrador",
    "percepcion_subtema.terminos": "términos frecuentes del grupo (con umbral anti-PII), en claro",
    "percepcion_comentario_token.token": "palabras de cada comentario, sin orden y SIN cifrar",
    "percepcion_publicacion.external_id": "id de la publicación en la plataforma (público)",
    "percepcion_resumen_semanal.texto": "narrativa generada por el LLM, agregada y en claro",
    "percepcion_evento.descripcion": "texto libre de administradores",
}


class PublicacionError(mig.MigracionError):
    """Falla esperable de la carga; el mensaje es apto para mostrar (sin valores)."""


class ConfiguracionError(PublicacionError):
    """Falta o es inválida una clave/URL: la carga ni siquiera empieza (código de salida 2)."""


# ---------------------------------------------------------------------------
# Verificaciones previas (solo lectura)
# ---------------------------------------------------------------------------

def exigir_claves() -> None:
    """Falla (nombrando la variable, jamás su valor) si faltan las claves de texto o de ID."""
    try:
        if not cripto.hay_clave():
            raise ConfiguracionError(f"Falta {cripto.VAR_CLAVE_TEXTO}: sin ella no se puede verificar "
                                     "que el texto esté cifrado.")
        cripto.seudonimo_autor("verificacion")
    except cripto.ErrorCripto as exc:   # sus mensajes nombran la variable, nunca el valor
        raise ConfiguracionError(str(exc)) from None


def _origen_marcado(src: Connection) -> bool:
    """¿El origen ya trae alguna de las marcas del almacén? (entonces ya está seudonimizado)"""
    if not inspect(src).has_table(TABLA_META):
        return False
    n = src.execute(
        text(f"SELECT COUNT(*) FROM \"{TABLA_META}\" WHERE clave IN :c AND valor = 'true'")
        .bindparams(bindparam("c", expanding=True)), {"c": list(MARCAS_ALMACEN)}).scalar_one()
    return n > 0


def revisar_cifrado(src: Connection) -> dict[str, dict[str, int]]:
    """{tabla.columna: {"con_valor": n, "no_genuinos": m}} sobre el origen.

    "No genuino" = no descifra de verdad con su AAD (texto en claro, o algo que solo imita la
    forma `enc:...`). Vacío y NULL no cuentan: no hay nada que proteger.
    """
    resultado: dict[str, dict[str, int]] = {}
    insp = inspect(src)
    for tabla, (columna, contexto_de) in COLUMNAS_CIFRADAS.items():
        if not insp.has_table(tabla) or columna not in {c["name"] for c in insp.get_columns(tabla)}:
            continue
        con_valor = no_genuinos = 0
        lectura = src.execution_options(stream_results=True).execute(
            text(f'SELECT id, "{columna}" FROM "{tabla}"'))
        for lote in lectura.partitions(2000):
            for id_, valor in lote:
                if not valor:
                    continue
                con_valor += 1
                try:
                    genuino = cripto.es_genuino(valor, contexto_de(id_))
                except cripto.ClaveNoConfigurada as exc:
                    raise ConfiguracionError(
                        f"{exc} (en {tabla}.{columna}: una versión de clave sin configurar)") from None
                if not genuino:
                    no_genuinos += 1
        resultado[f"{tabla}.{columna}"] = {"con_valor": con_valor, "no_genuinos": no_genuinos}
    return resultado


def _conteo(con: Connection, tabla: str, esquema: str | None) -> int:
    if not inspect(con).has_table(tabla, schema=esquema):
        return 0
    return con.execute(text(f"SELECT COUNT(*) FROM {_q(tabla, esquema)}")).scalar_one()


def _q(tabla: str, esquema: str | None) -> str:
    return f'"{esquema}"."{tabla}"' if esquema else f'"{tabla}"'


def _largos_del_modelo() -> dict[str, dict[str, int]]:
    return {
        t.name: {c.name: c.type.length for c in t.columns
                 if isinstance(c.type, String) and c.type.length}
        for t in mig._tablas()
    }


def _reporte_a_revisar(src: Connection, salida) -> None:
    """Conteos (no valores) de las columnas que podrían identificar algo; ver COLUMNAS_A_REVISAR."""
    insp = inspect(src)
    salida("  Columnas a revisar (no se modifican; solo conteo de filas con valor):")
    for clave, motivo in COLUMNAS_A_REVISAR.items():
        tabla, columna = clave.split(".")
        if not insp.has_table(tabla) or columna not in {c["name"] for c in insp.get_columns(tabla)}:
            continue
        n = src.execute(text(f'SELECT COUNT("{columna}") FROM "{tabla}"')).scalar_one()
        salida(f"    {clave}: {n} filas  -- {motivo}")


# ---------------------------------------------------------------------------
# Copia
# ---------------------------------------------------------------------------

def _copiar_tabla(src: Connection, dst: Connection, tabla, columnas: list[str], lote: int,
                  cache_autor: dict) -> int:
    from sqlalchemy import select

    lectura = src.execution_options(stream_results=True).execute(
        select(*[tabla.c[n] for n in columnas]))
    insert = mig._insert(tabla, columnas)
    es_comentario = tabla.name == "percepcion_comentario"
    copiadas = 0
    for filas in lectura.partitions(lote):
        lote_filas = [dict(f._mapping) for f in filas]
        if es_comentario:
            for fila in lote_filas:
                if "autor_hash" in fila:
                    k = ("autor", fila["autor_hash"])
                    if k not in cache_autor:
                        cache_autor[k] = cripto.seudonimo_autor(fila["autor_hash"])
                    fila["autor_hash"] = cache_autor[k]
                if "external_id" in fila:
                    k = ("ext", fila["external_id"])
                    if k not in cache_autor:
                        cache_autor[k] = cripto.seudonimo_ext_comentario(fila["external_id"])
                    fila["external_id"] = cache_autor[k]
        dst.execute(insert, lote_filas)
        copiadas += len(filas)
    return copiadas


def _vaciar(dst: Connection, esquema: str | None, pg: bool) -> None:
    tablas = mig._tablas()
    if pg:
        nombres = ", ".join(_q(t.name, esquema) for t in tablas)
        dst.execute(text(f"TRUNCATE TABLE {nombres} RESTART IDENTITY CASCADE"))
    else:   # SQLite (solo pruebas): hijos primero
        for t in reversed(tablas):
            dst.execute(text(f'DELETE FROM "{t.name}"'))


def _con_filas(dst: Connection, esquema: str | None) -> list[str]:
    return [
        t.name for t in mig._tablas()
        if dst.execute(text(f"SELECT EXISTS (SELECT 1 FROM {_q(t.name, esquema)})")).scalar()
    ]


def _cmp(salida, etiqueta: str, n_o, n_d, problemas: list[str], problema: str | None = None) -> None:
    salida(f"  {etiqueta}: origen {n_o} -> destino {n_d}  {'OK' if n_o == n_d else 'DIFERENTE'}")
    if n_o != n_d:
        problemas.append(problema or etiqueta)


def _validar(src: Connection, dst: Connection, esquema: str | None, cifrado_origen: dict,
             salida) -> list[str]:
    """Compara origen y destino. Devuelve las discrepancias (vacío = todo coincide)."""
    problemas: list[str] = []
    insp_src = inspect(src)
    for tabla in mig._tablas():
        if tabla.name == TABLA_META:
            continue
        n_o, n_d = _conteo(src, tabla.name, None), _conteo(dst, tabla.name, esquema)
        _cmp(salida, tabla.name, n_o, n_d, problemas, f"conteo de {tabla.name}")
        if "id" in tabla.c and n_o:
            # Mismas filas y no solo la misma cantidad: suma y máximo de los id.
            q = "SELECT COALESCE(SUM(id), 0), COALESCE(MAX(id), 0) FROM %s"
            o = tuple(src.execute(text(q % _q(tabla.name, None))).one())
            d = tuple(dst.execute(text(q % _q(tabla.name, esquema))).one())
            if o != d:
                salida(f"  {tabla.name}: suma/máximo de id DIFERENTE")
                problemas.append(f"ids de {tabla.name}")
    for tabla, (columna, _ctx) in COLUMNAS_CIFRADAS.items():
        if not insp_src.has_table(tabla):
            continue
        sql = f'SELECT COUNT("{columna}") FROM %s'
        n_o = src.execute(text(sql % _q(tabla, None))).scalar_one()
        n_d = dst.execute(text(sql % _q(tabla, esquema))).scalar_one()
        _cmp(salida, f"{tabla}.{columna} no nulos", n_o, n_d, problemas)
    if insp_src.has_table("percepcion_comentario"):
        for col, etiqueta in (("autor_hash", "autores distintos"), ("external_id", "external_id distintos")):
            sql = f"SELECT COUNT(DISTINCT {col}) FROM %s"
            n_o = src.execute(text(sql % _q("percepcion_comentario", None))).scalar_one()
            n_d = dst.execute(text(sql % _q("percepcion_comentario", esquema))).scalar_one()
            _cmp(salida, etiqueta, n_o, n_d, problemas)
    # Cada texto/caption del destino, dentro de la transacción abierta: lo que descifra en el
    # origen tiene que descifrar igual en el destino (y la cuenta de "no genuinos" debe coincidir).
    cifrado_destino = revisar_cifrado(dst)
    if cifrado_destino != cifrado_origen:
        salida("  cifrado del destino: DIFERENTE respecto del origen")
        problemas.append("verificación de cifrado del destino")
    else:
        salida("  cifrado del destino (todas las filas): OK")
    for clave in MARCAS_ALMACEN:
        marca = dst.execute(text(f"SELECT valor FROM {_q(TABLA_META, esquema)} WHERE clave = :c"),
                            {"c": clave}).scalar()
        salida(f"  marca {clave}: {'presente' if marca == 'true' else 'AUSENTE'}")
        if marca != "true":
            problemas.append(f"marca {clave}")
    return problemas


# ---------------------------------------------------------------------------
# Origen y destino no pueden ser la misma base
# ---------------------------------------------------------------------------
_LOCALES = {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _extremo(url: str) -> tuple[str, int, str]:
    """(host, puerto, base) normalizados: minúsculas, loopback unificado, puerto 5432 por defecto,
    y `?host=` (como lo entiende libpq) por encima del host de la URL."""
    u = make_url(url)
    host = u.query.get("host") or u.host or ""
    if isinstance(host, (tuple, list)):
        host = host[0] if host else ""
    host = str(host).strip().strip("[]").lower()
    if host in _LOCALES:
        host = "localhost"
    puerto = u.query.get("port") or u.port or 5432
    return host, int(puerto), u.database or ""


def _misma_base(a: str, b: str, esq_a: str, esq_b: str) -> bool:
    return _extremo(a) == _extremo(b) and esq_a == esq_b


def _identidad(eng: Engine) -> dict:
    """Quién es el servidor al otro lado: base, dirección/puerto y, si el rol puede, el
    identificador del clúster. Lo que no se pueda leer queda en None (se degrada con gracia)."""
    with eng.connect() as con:
        base, addr, puerto = con.execute(text(
            "SELECT current_database(), inet_server_addr()::text, inet_server_port()")).one()
        try:
            with con.begin_nested():
                sysid = con.execute(text("SELECT system_identifier FROM pg_control_system()")).scalar()
        except Exception:   # noqa: BLE001 - sin permiso: se usa lo demás
            sysid = None
    return {"base": base, "addr": addr, "puerto": puerto, "sysid": sysid}


def _misma_instancia(eng_o: Engine, eng_d: Engine) -> bool:
    """True si los dos motores llegan a la misma base del mismo servidor (consulta al servidor)."""
    o, d = _identidad(eng_o), _identidad(eng_d)
    if o["base"] != d["base"]:
        return False
    if o["sysid"] is not None and d["sysid"] is not None:
        return o["sysid"] == d["sysid"]
    if o["addr"] is not None and d["addr"] is not None:
        return (o["addr"], o["puerto"]) == (d["addr"], d["puerto"])
    return False   # sin datos para afirmarlo (p. ej. socket Unix): decide la comparación de URLs


def publicar(
    eng_origen: Engine,
    eng_destino: Engine | None,
    *,
    esquema: str = ESQUEMA_PERCEPCION,
    esquema_origen: str | None = None,
    reemplazar: bool = False,
    permitir_claro: bool = False,
    dry_run: bool = False,
    lote: int = LOTE_POR_DEFECTO,
    salida=print,
) -> dict[str, int]:
    """Copia origen -> destino en una transacción. Devuelve {tabla: filas copiadas}.

    Con `eng_destino=None` y `dry_run=True` solo revisa el origen. Lanza `PublicacionError`
    (o `ConfiguracionError`) ante cualquier problema; el destino queda intacto.
    Los motores llegan ya apuntando al esquema (ver `publicar_urls`).
    """
    if not _NOMBRE_ESQUEMA.match(esquema):
        raise PublicacionError("El nombre del esquema solo admite minúsculas, dígitos y guion bajo.")
    exigir_claves()
    if eng_destino is None and not dry_run:
        raise PublicacionError("Falta el destino: solo --dry-run puede correr sin él.")
    pg = eng_destino is not None and eng_destino.dialect.name == "postgresql"
    esq = esquema if pg else None
    copiadas: dict[str, int] = {}

    if (pg and eng_origen.dialect.name == "postgresql" and esquema_origen == esquema
            and _misma_instancia(eng_origen, eng_destino)):
        raise PublicacionError(
            "El servidor confirma que origen y destino son la misma base y esquema: se niega "
            "(--reemplazar habría vaciado el origen).")

    with eng_origen.connect() as src:
        if src.dialect.name == "postgresql":
            # UNA instantánea: cifrado, copia y validación ven exactamente los mismos datos.
            src.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        if _origen_marcado(src):
            raise PublicacionError(
                f"El origen ya está marcado como seudonimizado ({META_AUTOR_SEUDONIMIZADO}): "
                "aplicar el seudónimo otra vez rompería la identidad de los autores.")

        cifrado = revisar_cifrado(src)
        no_genuinos = {k: v["no_genuinos"] for k, v in cifrado.items() if v["no_genuinos"]}
        for clave, v in cifrado.items():
            salida(f"  {clave}: {v['con_valor']} con valor, {v['no_genuinos']} sin cifrar de verdad")
        if no_genuinos and not permitir_claro:
            raise PublicacionError(
                "Hay texto que no es un cifrado auténtico (" + ", ".join(
                    f"{k}={n}" for k, n in no_genuinos.items()) + "). No se copia nada. Cifra el origen "
                "(scripts/cifrar_textos_percepcion.py) o usa --permitir-claro si de verdad lo quieres en claro.")
        if no_genuinos:
            salida("  ADVERTENCIA: --permitir-claro: se copia texto SIN cifrar al almacén ("
                   + ", ".join(f"{k}={n}" for k, n in no_genuinos.items()) + ").")

        modeladas = {t.name for t in mig._tablas()}
        for nombre in sorted(inspect(src).get_table_names()):
            if nombre.startswith("percepcion_") and nombre not in modeladas:
                salida(f"  {nombre}: sin modelo, NO se copia")

        if dry_run:
            problemas = mig.validar_largos(src, _largos_del_modelo())
            if problemas:
                raise PublicacionError("Estas columnas tienen texto más largo que el límite del "
                                       "modelo: " + "; ".join(problemas))
            for tabla in mig._tablas():
                if tabla.name == TABLA_META:
                    continue
                n = _conteo(src, tabla.name, None)
                copiadas[tabla.name] = n
                salida(f"  {tabla.name}: {n} filas se copiarían")
            if eng_destino is not None:
                with eng_destino.connect() as dst:
                    insp = inspect(dst)
                    con_datos = [t.name for t in mig._tablas()
                                 if insp.has_table(t.name, schema=esq)
                                 and dst.execute(text(f"SELECT EXISTS (SELECT 1 FROM "
                                                      f"{_q(t.name, esq)})")).scalar()]
                    salida("  destino con datos en: " + (", ".join(con_datos) or "(ninguna tabla)")
                           + ("  -> haría falta --reemplazar" if con_datos and not reemplazar else ""))
            _reporte_a_revisar(src, salida)
            salida("  DRY-RUN: no se escribió nada.")
            return copiadas

        with eng_destino.begin() as dst:
            if pg:
                dst.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"'))
            tablas = mig._tablas()
            tablas[0].metadata.create_all(dst, tables=tablas)   # solo las de Percepción, checkfirst

            existentes = _con_filas(dst, esq)
            if existentes and not reemplazar:
                raise PublicacionError(
                    "El destino ya tiene datos en: " + ", ".join(existentes) + ". No se toca nada. "
                    "Usa --reemplazar para vaciarlas y recargar (sobrescribe lo escrito en el almacén).")

            problemas = mig.validar_largos(src, mig.largos_destino(dst, esq))
            if problemas:
                raise PublicacionError(
                    "Estas columnas tienen texto más largo que el límite del destino; ensancha el "
                    "modelo y la columna antes de cargar: " + "; ".join(problemas))

            if existentes:
                _vaciar(dst, esq, pg)

            cache_autor: dict[str, str] = {}
            for tabla in tablas:
                if tabla.name == TABLA_META:
                    continue   # la marca es del destino: nunca se copia del origen
                columnas = mig._columnas_comunes(src, tabla)
                if columnas is None:
                    salida(f"  {tabla.name}: no existe en el origen, se omite")
                    copiadas[tabla.name] = 0
                    continue
                copiadas[tabla.name] = _copiar_tabla(src, dst, tabla, columnas, lote, cache_autor)

            ahora = datetime.now(timezone.utc).replace(tzinfo=None)
            for clave in MARCAS_ALMACEN:
                dst.execute(PercepcionMeta.__table__.insert().values(
                    clave=clave, valor="true", actualizado_en=ahora))
            if pg:
                mig._reiniciar_secuencias(dst, esquema)

            problemas = _validar(src, dst, esq, cifrado, salida)
            if problemas:
                raise PublicacionError("No coinciden: " + ", ".join(problemas) + ". Se revierte todo.")
            _reporte_a_revisar(src, salida)
            salida("  Siguiente paso: scripts/otorgar_permisos_warehouse_percepcion.py (permisos) y "
                   "luego cambiar las URLs de la Bóveda (docs/warehouse-percepcion.md).")
    return copiadas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def publicar_urls(origen: str, destino: str | None, *, esquema_origen: str = ESQUEMA_PERCEPCION,
                  esquema: str = ESQUEMA_PERCEPCION, **kw) -> dict[str, int]:
    """Valida las URLs (ambas PostgreSQL, distintas) y llama a `publicar`. Jamás las imprime."""
    if not origen.startswith("postgresql"):
        raise ConfiguracionError("El origen debe ser una URL de PostgreSQL (postgresql+psycopg://...).")
    if destino is not None and not destino.startswith("postgresql"):
        raise ConfiguracionError("El destino debe ser una URL de PostgreSQL (postgresql+psycopg://...).")
    if destino is not None and _misma_base(origen, destino, esquema_origen, esquema):
        raise ConfiguracionError("Origen y destino apuntan a la misma base y esquema: se niega.")
    for e in (esquema_origen, esquema):
        if not _NOMBRE_ESQUEMA.match(e):
            raise ConfiguracionError("El nombre del esquema solo admite minúsculas, dígitos y guion bajo.")
    eng_o = create_engine(url_con_esquema(origen, esquema_origen), future=True)
    eng_d = create_engine(url_con_esquema(destino, esquema), future=True) if destino else None
    try:
        return publicar(eng_o, eng_d, esquema=esquema, esquema_origen=esquema_origen, **kw)
    finally:
        eng_o.dispose()
        if eng_d is not None:
            eng_d.dispose()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carga Percepción al almacén institucional (cifrado + autores seudonimizados).")
    ap.add_argument("--origen", default=None, help=f"URL del Postgres actual de la Bóveda (o {VAR_ORIGEN}); no se imprime")
    ap.add_argument("--destino", default=None, help=f"URL del almacén (o {VAR_DESTINO}); no se imprime")
    ap.add_argument("--esquema-origen", default=ESQUEMA_PERCEPCION)
    ap.add_argument("--esquema", default=ESQUEMA_PERCEPCION, help="esquema destino (por defecto percepcion)")
    ap.add_argument("--reemplazar", action="store_true",
                    help="vaciar las tablas del destino que ya tengan filas y recargarlas")
    ap.add_argument("--permitir-claro", action="store_true",
                    help="copia aunque haya texto/caption sin cifrar (NO recomendado)")
    ap.add_argument("--dry-run", action="store_true",
                    help="cuenta y verifica el cifrado; no escribe nada")
    ap.add_argument("--lote", type=int, default=LOTE_POR_DEFECTO, help="filas por INSERT")
    args = ap.parse_args(argv)

    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass

    origen = (args.origen or os.environ.get(VAR_ORIGEN, "")).strip()
    destino = (args.destino or os.environ.get(VAR_DESTINO, "")).strip()
    if not origen:
        print(f"Falta el origen: pasa --origen o define {VAR_ORIGEN}.", file=sys.stderr)
        return 2
    if not destino and not args.dry_run:
        print(f"Falta el destino: pasa --destino o define {VAR_DESTINO}.", file=sys.stderr)
        return 2

    print(f"Origen: esquema {args.esquema_origen}  ->  almacén: esquema {args.esquema}"
          f"{'  (reemplazando)' if args.reemplazar else ''}{'  [dry-run]' if args.dry_run else ''}")
    try:
        copiadas = publicar_urls(
            origen, destino or None, esquema_origen=args.esquema_origen, esquema=args.esquema,
            reemplazar=args.reemplazar, permitir_claro=args.permitir_claro,
            dry_run=args.dry_run, lote=args.lote)
    except ConfiguracionError as exc:
        print(f"CONFIGURACIÓN: {exc}", file=sys.stderr)
        return 2
    except mig.MigracionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - el mensaje del driver puede traer URL o filas
        print(f"ERROR inesperado ({type(exc).__name__}). No se escribió nada.", file=sys.stderr)
        return 1
    print(f"{'Simulación' if args.dry_run else 'Carga'} completa: {sum(copiadas.values())} filas "
          f"en {len(copiadas)} tablas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
