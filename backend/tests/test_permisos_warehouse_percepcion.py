"""`scripts/otorgar_permisos_warehouse_percepcion.py` + `backend/sql/004_percepcion_warehouse.sql`.

La parte textual corre siempre; la prueba contra Postgres es opt-in (PERCEPCION_TEST_DATABASE_URL)
y usa roles y esquema descartables.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from pg_percepcion import URL, esquema_efimero, requiere_pg

RUTA = Path(__file__).resolve().parents[2] / "scripts" / "otorgar_permisos_warehouse_percepcion.py"
_spec = importlib.util.spec_from_file_location("otorgar_permisos_warehouse_percepcion", RUTA)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _codigo() -> list[str]:
    return [l for l in mod.RUTA_SQL.read_text(encoding="utf-8").splitlines()
            if not l.strip().startswith("--")]


def test_el_sql_no_crea_roles_ni_pone_contrasenas():
    codigo = "\n".join(_codigo()).lower()
    assert "create role" not in codigo and "alter role" not in codigo and "password" not in codigo


def test_sustituye_solo_los_parametros():
    sql = mod.sql_permisos(rol_escritor="wh_escribe", rol_lector="wh_lee")
    assert "rol_escritor   text := 'wh_escribe';" in sql
    assert "rol_lector     text := 'wh_lee';" in sql
    assert "esq_percepcion text := 'percepcion';" in sql
    original = mod.RUTA_SQL.read_text(encoding="utf-8")
    assert sql.replace("wh_escribe", "").replace("wh_lee", "") == original


def test_exige_los_dos_roles_distintos_y_validos():
    with pytest.raises(ValueError, match="obligatorio"):
        mod.sql_permisos(rol_escritor="a")
    with pytest.raises(ValueError, match="distintos"):
        mod.sql_permisos(rol_escritor="a", rol_lector="a")
    with pytest.raises(ValueError, match="no válido"):
        mod.sql_permisos(rol_escritor="x; DROP ROLE y", rol_lector="b")
    with pytest.raises(ValueError, match="desconocidos"):
        mod.sql_permisos(rol_escritor="a", rol_lector="b", otro="c")


def test_otorga_lo_pedido_y_nada_mas():
    codigo = "\n".join(_codigo())
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES" in codigo   # escritor
    assert "GRANT SELECT ON ALL TABLES" in codigo                           # lector
    assert "TRUNCATE" not in codigo and "WITH GRANT OPTION" not in codigo
    assert "ALTER DEFAULT PRIVILEGES" in codigo


def test_main_exit_2_sin_url_o_con_parametros_malos(monkeypatch, capsys):
    monkeypatch.delenv(mod.VAR_ADMIN_URL, raising=False)
    assert mod.main(["--rol-escritor", "a", "--rol-lector", "b"]) == 2
    assert mod.VAR_ADMIN_URL in capsys.readouterr().err
    assert mod.main(["--rol-escritor", "a", "--rol-lector", "a"]) == 2
    assert "distintos" in capsys.readouterr().err


def test_solo_imprimir_no_necesita_conexion(capsys):
    assert mod.main(["--rol-escritor", "a", "--rol-lector", "b", "--solo-imprimir"]) == 0
    assert "text := 'a';" in capsys.readouterr().out


@requiere_pg
def test_permisos_reales_con_roles_descartables():
    esq, escritor, lector = "percepcion_test_wh_perm", "wh_test_escritor", "wh_test_lector"
    admin = create_engine(URL, future=True)

    def _borrar_roles():
        with admin.begin() as con:
            for r in (escritor, lector):
                if con.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": r}).first():
                    con.execute(text(f'DROP OWNED BY "{r}"'))   # incluye permisos por defecto
                    con.execute(text(f'DROP ROLE "{r}"'))

    _borrar_roles()
    try:
        with esquema_efimero(esq):
            with admin.begin() as con:
                for r in (escritor, lector):
                    con.execute(text(f'CREATE ROLE "{r}" NOLOGIN'))
            mod.aplicar(URL, esq_percepcion=esq, rol_escritor=escritor, rol_lector=lector)
            mod.aplicar(URL, esq_percepcion=esq, rol_escritor=escritor, rol_lector=lector)  # idempotente

            def _como(rol, sql):
                with admin.connect() as con:
                    con.execute(text(f'SET ROLE "{rol}"'))
                    try:
                        return con.execute(text(sql)).rowcount
                    finally:
                        con.rollback()

            ruta = f'"{esq}".percepcion_cuenta'
            alta = f"INSERT INTO {ruta} (handle, nombre, tipo) VALUES ('h','n','t')"
            assert _como(escritor, alta) == 1
            assert _como(escritor, f"UPDATE {ruta} SET nombre = 'x'") == 0
            assert _como(escritor, f"DELETE FROM {ruta}") == 0
            assert _como(lector, f"SELECT 1 FROM {ruta}") == 0
            for sql in (alta, f"UPDATE {ruta} SET nombre = 'x'", f"DELETE FROM {ruta}"):
                with pytest.raises(DBAPIError):
                    _como(lector, sql)
            with pytest.raises(DBAPIError):
                _como(escritor, f"TRUNCATE {ruta}")
    finally:
        _borrar_roles()
        admin.dispose()


def test_permisos_por_defecto_son_del_dueno_del_esquema():
    codigo = "\n".join(_codigo())
    assert codigo.count("ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I") == 5
    assert "ALTER DEFAULT PRIVILEGES IN SCHEMA" not in codigo
    assert "n.nspowner" in codigo and "rolsuper" in codigo
    # La comprobación del llamante ocurre antes de tocar cualquier permiso.
    assert codigo.index("rolsuper") < codigo.index("REVOKE ALL ON SCHEMA")
