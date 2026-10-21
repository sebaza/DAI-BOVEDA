"""`scripts/crear_roles_percepcion.py` — la parte que no necesita Postgres."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[2] / "scripts" / "crear_roles_percepcion.py"
_spec = importlib.util.spec_from_file_location("crear_roles_percepcion", RUTA)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_se_niega_si_falta_una_contrasena():
    with pytest.raises(mod.FaltanContrasenas) as exc:
        mod.contrasenas_del_entorno({})
    # Nombra las variables que faltan.
    assert mod.VAR_APP in str(exc.value) and mod.VAR_PROCESO in str(exc.value)
    with pytest.raises(mod.FaltanContrasenas):
        mod.contrasenas_del_entorno({mod.VAR_APP: "a"})
    with pytest.raises(mod.FaltanContrasenas):
        mod.contrasenas_del_entorno({mod.VAR_APP: "a", mod.VAR_PROCESO: "  "})


def test_exige_contrasenas_distintas():
    with pytest.raises(mod.FaltanContrasenas):
        mod.contrasenas_del_entorno({mod.VAR_APP: "x", mod.VAR_PROCESO: "x"})
    assert mod.contrasenas_del_entorno({mod.VAR_APP: "a", mod.VAR_PROCESO: "b"}) == ("a", "b")


def test_main_sale_con_codigo_2_sin_contrasenas(monkeypatch, capsys):
    monkeypatch.delenv(mod.VAR_APP, raising=False)
    monkeypatch.delenv(mod.VAR_PROCESO, raising=False)
    assert mod.main(["--admin-url", "postgresql+psycopg://x:y@localhost/db"]) == 2
    assert "Falta definir" in capsys.readouterr().err


def test_el_sql_no_contiene_contrasenas_ni_las_pide():
    codigo = [l.lower() for l in mod.RUTA_SQL.read_text(encoding="utf-8").splitlines()
              if not l.strip().startswith("--")]
    assert not any("password" in l for l in codigo)


def test_sustitucion_de_nombres_solo_toca_los_parametros():
    original = mod.sql_roles()
    for valor in ("percepcion", "boveda", "boveda_app", "boveda_proceso"):
        assert f"'{valor}'" in original
    cambiado = mod.sql_roles(rol_app="x_app", esq_percepcion="p_test")
    assert "rol_app        text := 'x_app'" in cambiado
    assert "esq_percepcion text := 'p_test'" in cambiado
    # El resto del SQL queda idéntico.
    assert cambiado.replace("x_app", "boveda_app").replace("p_test", "percepcion") == original
    with pytest.raises(ValueError):
        mod.sql_roles(rol_app="x; DROP ROLE y")
    with pytest.raises(ValueError):
        mod.sql_roles(inexistente="x")
