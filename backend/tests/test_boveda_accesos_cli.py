"""CLI that manages the Boveda access lists (``scripts/boveda_accesos.py``)."""
from __future__ import annotations

import getpass
import importlib.util
import sys
from pathlib import Path

import pytest

from app.services.accesos import InMemoryAccessRepository

RUTA = Path(__file__).resolve().parents[2] / "scripts" / "boveda_accesos.py"


@pytest.fixture(scope="module")
def cli():
    spec = importlib.util.spec_from_file_location("boveda_accesos_cli", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def repo():
    r = InMemoryAccessRepository()
    r.add_module("percepcion", "Termómetro Institucional")
    r.add_module("otro", "Otro módulo")
    return r


def run(cli, repo, *args) -> int:
    return cli.main(list(args), repo=repo)


def test_agregar_y_quitar_admin(cli, repo, capsys):
    assert run(cli, repo, "agregar-admin", "  Jefe@UCN.cl ", "--por", "yo") == 0
    assert repo.is_admin("jefe@ucn.cl")
    assert "jefe@ucn.cl" in capsys.readouterr().out
    assert run(cli, repo, "quitar-admin", "jefe@ucn.cl") == 0
    assert not repo.is_admin("jefe@ucn.cl")


def test_quitar_admin_inexistente_avisa_pero_no_falla(cli, repo, capsys):
    assert run(cli, repo, "quitar-admin", "nadie@ucn.cl") == 0
    assert "no era administrador" in capsys.readouterr().out


def test_dar_acceso_es_un_upsert_del_rol(cli, repo):
    assert run(cli, repo, "dar-acceso", "percepcion", "a@ucn.cl", "lector", "--por", "yo") == 0
    assert str(repo.role_for("a@ucn.cl", "percepcion").value) == "lector"
    assert run(cli, repo, "dar-acceso", "percepcion", "a@ucn.cl", "equipo") == 0
    assert str(repo.role_for("a@ucn.cl", "percepcion").value) == "equipo"


def test_creado_por_usa_el_usuario_del_sistema_por_defecto(cli, repo):
    run(cli, repo, "dar-acceso", "percepcion", "a@ucn.cl", "lector")
    assert repo.list_all("percepcion").accesos[0].creado_por == getpass.getuser()
    run(cli, repo, "dar-acceso", "otro", "b@ucn.cl", "lector", "--por", "setup-local")
    assert repo.list_all("otro").accesos[0].creado_por == "setup-local"


def test_quitar_acceso(cli, repo, capsys):
    run(cli, repo, "dar-acceso", "percepcion", "a@ucn.cl", "lector")
    assert run(cli, repo, "quitar-acceso", "percepcion", "a@ucn.cl") == 0
    assert repo.role_for("a@ucn.cl", "percepcion") is None
    assert run(cli, repo, "quitar-acceso", "percepcion", "a@ucn.cl") == 0
    assert "no tenía acceso" in capsys.readouterr().out


@pytest.mark.parametrize(
    "args, fragmento",
    [
        (("dar-acceso", "no_existe", "a@ucn.cl", "lector"), "no existe"),
        (("dar-acceso", "percepcion", "a@ucn.cl", "superjefe"), "rol"),
        (("dar-acceso", "percepcion", "a@ucn.cl", "admin"), "rol"),
        (("dar-acceso", "percepcion", "sin-arroba", "lector"), "correo"),
        (("agregar-admin", "sin-arroba"), "correo"),
        (("quitar-acceso", "no_existe", "a@ucn.cl"), "no existe"),
        (("listar", "--modulo", "no_existe"), "no existe"),
    ],
)
def test_errores_salen_con_codigo_distinto_de_cero_y_mensaje_claro(cli, repo, capsys, args, fragmento):
    assert run(cli, repo, *args) == 1
    err = capsys.readouterr().err
    assert fragmento in err.lower()
    assert repo.list_all().accesos == [] and repo.list_all().administradores == []


def test_listar(cli, repo, capsys):
    run(cli, repo, "agregar-admin", "jefe@ucn.cl")
    run(cli, repo, "dar-acceso", "percepcion", "a@ucn.cl", "lector", "--por", "yo")
    run(cli, repo, "dar-acceso", "otro", "b@ucn.cl", "equipo")
    capsys.readouterr()

    assert run(cli, repo, "listar") == 0
    todo = capsys.readouterr().out
    assert "jefe@ucn.cl" in todo and "a@ucn.cl" in todo and "b@ucn.cl" in todo

    assert run(cli, repo, "listar", "--modulo", "percepcion") == 0
    solo = capsys.readouterr().out
    assert "a@ucn.cl" in solo and "b@ucn.cl" not in solo
    assert "jefe@ucn.cl" in solo  # admins are global: they open every module


def test_listar_vacio_lo_dice(cli, repo, capsys):
    assert run(cli, repo, "listar") == 0
    assert "nadie" in capsys.readouterr().out.lower()


def test_sin_url_de_base_de_datos_falla_sin_imprimir_nada_sensible(cli, monkeypatch, capsys):
    monkeypatch.delenv("BOVEDA_DATABASE_URL", raising=False)
    monkeypatch.setattr(cli, "cargar_entorno", lambda: None)  # do not read backend/.env
    assert cli.main(["listar"]) == 1
    assert "BOVEDA_DATABASE_URL" in capsys.readouterr().err


def test_no_imprime_la_url(cli, monkeypatch, capsys):
    monkeypatch.setenv("BOVEDA_DATABASE_URL", "postgresql+psycopg://u:clave-secreta@127.0.0.1:1/x")
    monkeypatch.setattr(cli, "cargar_entorno", lambda: None)
    assert cli.main(["listar"]) == 1  # nothing listens on :1
    salida = capsys.readouterr()
    assert "clave-secreta" not in salida.out + salida.err
