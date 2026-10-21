"""Conexión DEDICADA (solo lectura) a la base de PERCEPCIÓN del worker externo.

Por qué separada de `app.database.SessionLocal`:
  * El worker (`Sentiment_Analisys_University`) es el DUEÑO de las tablas
    `percepcion_*` y las escribe en SU base (`percepcion_real.db`), que contiene
    SOLO datos reales ingestados.
  * La base OPERACIONAL de la Torre puede tener datos SEED simulados (`*.sim`).
    Leer percepción desde ahí acopla lo real con lo simulado — justo lo que NO
    queremos. Este engine apunta a la base del worker y nunca la mezcla.

Config: `PERCEPCION_DATABASE_URL`. Si está vacío, cae a `OPERATIONAL_DATABASE_URL`
(compat / nube donde el worker escriba al mismo Postgres). La Torre NUNCA escribe
acá: no hay `create_all`, la sesión es de lectura.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()
# Base de percepción explícita, o la operacional como fallback.
_url = _settings.percepcion_database_url or _settings.operational_database_url
_is_sqlite = _url.startswith("sqlite")


def crear_engine(url: str, *, solo_lectura: bool) -> Engine:
    """Engine de la base de percepción, blindado según `solo_lectura`.

    * SQLite: WAL + busy_timeout (las lecturas del dashboard no se bloquean si el worker
      escribe la misma base) y, si es de lectura, `PRAGMA query_only=ON`.
    * PostgreSQL: el motor de lectura abre cada conexión con
      `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`, el equivalente de
      `query_only`: cualquier INSERT/UPDATE/DELETE/DDL por esa vía falla en el servidor.
      Se hace por evento y no por `options=-c default_transaction_read_only=on` porque
      la URL ya trae `options` (el `search_path` que elige el esquema `percepcion`) y un
      `options` de `connect_args` lo pisaría. A diferencia del PRAGMA, acá un fallo NO se
      traga: sin el blindaje la conexión no se entrega.
    """
    sqlite = url.startswith("sqlite")
    kwargs: dict = {
        "future": True,
        "pool_pre_ping": True,
        "connect_args": {"check_same_thread": False} if sqlite else {},
    }
    if not sqlite:
        kwargs["pool_recycle"] = 1800
    engine = create_engine(url, **kwargs)

    if sqlite:
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            try:
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA busy_timeout=8000")
                if solo_lectura:
                    cur.execute("PRAGMA temp_store=MEMORY")
                    cur.execute("PRAGMA query_only=ON")  # blindaje: esta conexión NO escribe
            except Exception:
                pass
            finally:
                cur.close()
    elif solo_lectura:
        @event.listens_for(engine, "connect")
        def _pg_solo_lectura(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            try:
                cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            finally:
                cur.close()
            dbapi_conn.commit()  # el SET de sesión sobrevive solo si la transacción cierra

    return engine


percepcion_engine = crear_engine(_url, solo_lectura=True)

PercepcionSessionLocal = sessionmaker(
    bind=percepcion_engine, autoflush=False, autocommit=False, future=True
)


# --------------------------------------------------------------------------- #
# Conexión de ESCRITURA — SOLO para la curación manual de temas.
# --------------------------------------------------------------------------- #
# El lector del dashboard es read-only (query_only=ON / READ ONLY en Postgres). La
# curación manual (asignar un tema a mano) es la ÚNICA operación de la Torre que escribe
# en la base del worker, así que va por un engine aparte SIN ese blindaje. Se usa con
# moderación y reconstruye los hechos tras cada cambio.
percepcion_write_engine = crear_engine(_url, solo_lectura=False)

PercepcionWriteSessionLocal = sessionmaker(
    bind=percepcion_write_engine, autoflush=False, autocommit=False, future=True
)

def _asegurar_columnas(tabla) -> list[str]:
    """Agrega por ALTER TABLE las columnas del modelo que falten en la base.

    `create_all(checkfirst=True)` crea TABLAS ausentes, **nunca columnas** sobre una
    tabla que ya existe. Sin esto, cualquier columna nueva de una tabla propia de la
    Torre (`percepcion_correccion`, `percepcion_tema_custom`, `percepcion_evento`)
    sería invisible en toda base que ya tuviera la tabla creada — que es el caso de
    la base real, con 376 filas de correcciones ya escritas.

    Solo se aplica a tablas que la Torre POSEE. Las tablas espejo del worker
    (`percepcion_score`, `percepcion_hecho_diario`, …) NO se tocan: su dueño es el
    worker y alterarlas desde acá es justo la clase de deriva que ya costó la
    columna `origen`.

    Es idempotente y no destructivo: solo ADD COLUMN de lo que falta. Devuelve las
    columnas agregadas (vacío si no había nada que hacer).
    """
    agregadas: list[str] = []
    try:
        insp = inspect(percepcion_write_engine)
        if not insp.has_table(tabla.name):
            return agregadas
        existentes = {c["name"] for c in insp.get_columns(tabla.name)}
        faltantes = [c for c in tabla.columns if c.name not in existentes]
        if not faltantes:
            return agregadas
        with percepcion_write_engine.begin() as con:
            for col in faltantes:
                # NOT NULL sin default no se puede agregar a una tabla con filas.
                # Todas las columnas nuevas de la Torre son nullable a propósito:
                # una fila vieja no sabe su `confirmado` ni su `autor_tipo`, y NULL
                # es la respuesta honesta (≠ False, que sería afirmar un desacuerdo).
                tipo = col.type.compile(percepcion_write_engine.dialect)
                con.execute(text(f'ALTER TABLE {tabla.name} ADD COLUMN "{col.name}" {tipo}'))
                agregadas.append(col.name)
    except Exception:
        # Base de solo lectura, permisos, o motor sin ALTER: la curación degrada
        # sola (`curacion._tiene_columna`), no se cae.
        pass
    return agregadas


def _asegurar_unicidad_resumen() -> bool:
    """Normaliza, deduplica y hace ÚNICA la clave del caché de resúmenes semanales.

    Hace falta porque `create_all(checkfirst=True)` crea tablas ausentes pero **nunca
    agrega constraints a una tabla que ya existe** — igual que con las columnas. Sin
    esto, toda base que haya creado la tabla antes de este cambio se queda sin la
    garantía, que es justo la que impide pagar dos veces por los mismos datos.

    Tres pasos, en este orden y por un motivo:

    1. `dimension` NULL -> ''. En SQL `NULL != NULL`, así que un índice único sobre una
       columna con NULLs NO impide dos filas globales. Sin normalizar primero, el paso 3
       crearía un índice que no protege el caso principal.
    2. Deduplicar dejando la fila de `id` más alto (la más reciente). Sin esto, el
       CREATE UNIQUE INDEX falla contra cualquier base que ya tenga duplicados.
    3. Recién ahí, el índice único.

    Idempotente y no destructivo salvo por los duplicados, que por definición sobran.
    Devuelve True si la unicidad quedó garantizada.
    """
    tabla = "percepcion_resumen_semanal"
    try:
        insp = inspect(percepcion_write_engine)
        if not insp.has_table(tabla):
            return False
        with percepcion_write_engine.begin() as con:
            con.execute(text(
                f"UPDATE {tabla} SET dimension = '' WHERE dimension IS NULL"
            ))
            # Se conserva el `id` MÁXIMO por clave: es el último generado, o sea el
            # que corresponde a los datos más recientes.
            con.execute(text(
                f"DELETE FROM {tabla} WHERE id NOT IN ("
                f"  SELECT MAX(id) FROM {tabla} GROUP BY semana_inicio, nivel, dimension"
                f")"
            ))
            con.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS uq_percepcion_resumen_semana_alcance "
                f"ON {tabla} (semana_inicio, nivel, dimension)"
            ))
        return True
    except Exception:
        # Base de solo lectura o motor sin DDL: el servicio ya degrada solo (relee la
        # fila ante un choque de unicidad). Peor caso, se regenera de más; nunca se
        # pierde un resumen.
        return False


# La tabla de temas CUSTOM la escribe la Torre (curación) y la lee el worker. El
# worker también la crea vía create_all, pero la aseguramos acá para que la primera
# creación de tema no falle si el worker aún no corrió una ingesta con el modelo nuevo.
try:
    from app.services.percepcion.models import (
        PercepcionCorreccion,
        PercepcionEvento,
        PercepcionResumenSemanal,
        PercepcionTemaCustom,
    )
    PercepcionTemaCustom.__table__.create(bind=percepcion_write_engine, checkfirst=True)
    PercepcionCorreccion.__table__.create(bind=percepcion_write_engine, checkfirst=True)
    # Marcas de contexto: las administra la Torre (ABM del panel), las lee el worker.
    PercepcionEvento.__table__.create(bind=percepcion_write_engine, checkfirst=True)
    # Caché del resumen semanal por LLM. La Torre la escribe y la lee; el worker no
    # la toca (no sabe de OpenAI). Ver el docstring del modelo.
    PercepcionResumenSemanal.__table__.create(bind=percepcion_write_engine, checkfirst=True)
    # ...y las columnas que se hayan sumado DESPUÉS de que la tabla ya existía.
    for _t in (PercepcionCorreccion.__table__, PercepcionTemaCustom.__table__,
               PercepcionEvento.__table__, PercepcionResumenSemanal.__table__):
        _asegurar_columnas(_t)
    _asegurar_unicidad_resumen()
except Exception:
    pass


def get_percepcion_db() -> Session:
    """Dependencia FastAPI: sesión de solo lectura sobre la base de percepción."""
    db = PercepcionSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_percepcion_write_db() -> Session:
    """Dependencia FastAPI: sesión de ESCRITURA (curación manual de temas)."""
    db = PercepcionWriteSessionLocal()
    try:
        yield db
    finally:
        db.close()
