"""Shared canonical key, list of published combinations and identity gate of the Neural publication (no database)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from _neural_publicacion import canonizar, combinaciones, revisar_identidad  # noqa: E402

_CASOS = json.loads((Path(__file__).parent / "fixtures" / "neural_canon_casos.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("caso", _CASOS, ids=[c["url"] for c in _CASOS])
def test_canonizar_casos_compartidos(caso):
    assert canonizar(caso["url"]) == (caso["ruta"], caso["consulta"])


def _tarea(t):
    return {"tarea": t, "orden": 1}


def _falso_get(vistas_por_tarea=None, hasta=2026):
    """A fake ``get`` serving only the listing responses ``combinaciones`` reads."""
    vistas_por_tarea = vistas_por_tarea or {"t1": [("base", 2)], "t6": [("base", 1), ("sin_pnd", 3)]}
    jerarquia = [{"facultad": "Toda la UCN", "programas": []},
                 {"facultad": "Escuela de Ingeniería", "programas": [{"codigo": "8616", "nombre": "A"}]}]
    respuestas = {
        "/neural/programas": [{"cod_programa": "8616"}, {"cod_programa": "8201"}],
        "/neural/modelos/tareas": {"tareas": [_tarea(t) for t in vistas_por_tarea]},
        "/neural/historico": {"jerarquia": jerarquia},
        "/neural/proyeccion": {"jerarquia": jerarquia},
        "/neural/traslados/resumen": {"anios_disponibles": {"desde": 2010, "hasta": hasta},
                                      "balance": [{"cod_programa": "8616"}, {"cod_programa": "9999"}]},
    }
    for t, vs in vistas_por_tarea.items():
        respuestas[f"/neural/modelos/tarea/{t}"] = {"vistas": [{"variante": v, "corte_k": k} for v, k in vs]}

    def get(url):
        return respuestas[url]

    return get


def test_combinaciones_traslados():
    urls = combinaciones(_falso_get())
    resumen = [u for u in urls if u.startswith("/neural/traslados/resumen")]
    assert len(resumen) == 42 and len(set(resumen)) == 42
    assert any("anio_desde=2017" in u for u in resumen)
    assert any("anio_desde=2022" in u for u in resumen)
    assert not any("anio_hasta" in u for u in urls)
    assert "/neural/traslados/resumen" in resumen
    programa = [u for u in urls if u.startswith("/neural/traslados/programa/")]
    assert len(programa) == 3 * 42 and len(set(programa)) == 3 * 42
    assert "/neural/traslados/programa/9999?anio_desde=2022&tipo=cambio_carrera&solo_abandono=true" in programa


def test_combinaciones_grupos_t6_incluye_nivel_postgrado():
    urls = combinaciones(_falso_get())
    grupos = [u for u in urls if "/grupos?" in u]
    assert "/neural/modelos/tarea/t6/grupos?nivel=nivel_postgrado&variante=sin_pnd&corte=3" in grupos
    assert not any(u.startswith("/neural/modelos/tarea/t1/grupos") and "nivel_postgrado" in u for u in grupos)
    assert "/neural/modelos/tarea/t1/grupos?nivel=tipo_colegio&variante=base&corte=2" in grupos
    assert len(grupos) == 5 * 1 + 6 * 2


def test_combinaciones_listados_y_filtros():
    urls = combinaciones(_falso_get())
    assert len(urls) == len(set(urls))
    for fijo in ("/neural/aceptacion", "/neural/programas", "/neural/calidad", "/neural/modelos/resumen",
                 "/neural/modelos/tareas", "/neural/historico", "/neural/proyeccion", "/neural/modelos/tarea/t1",
                 "/neural/programa/8201/cohortes", "/neural/modelos/malla-ejemplo?semestre_max=4",
                 "/neural/modelos/malla-ejemplo?semestre_max=4&cod_programa=8616"):
        assert fijo in urls
    # «Toda la UCN» is the unfiltered URL, never a ?facultad= one.
    assert "/neural/historico?facultad=Escuela%20de%20Ingenier%C3%ADa" in urls
    assert "/neural/proyeccion?programa=8616" in urls
    assert not any("Toda" in u for u in urls)


def test_revisar_identidad():
    assert revisar_identidad({"a": [{"rut": 1}]}) == ["a[0].rut"]
    assert revisar_identidad({"n_estudiantes": 5}) == []
    assert revisar_identidad({"lista_estudiantes": [1]}) == ["lista_estudiantes"]
    assert revisar_identidad({"lista_estudiantes": []}) == []
    assert revisar_identidad([{"x": {"pidm": 3, "nrc": 1}}]) == ["[0].x.pidm", "[0].x.nrc"]
    assert revisar_identidad({"ok": [1, {"n": 2}]}) == []


def test_revisar_identidad_respuesta_realista():
    """Names of programs, groups, models and courses are institutional: the gate must not flag them."""
    respuesta = {
        "jerarquia": [{"facultad": "Escuela de Ingeniería", "programas": [{"codigo": "8616", "nombre": "Ingeniería Civil"}]}],
        "grupos": [{"categoria": "programa", "grupo": "8616", "nombre": "Ingeniería Civil", "facultad": "X", "n": 12,
                    "pocos_casos": False}],
        "modelos": [{"variante": "base", "corte_k": 2, "modelo": "m1", "nombre": "Regresión logística", "familia": "lineal"}],
        "nodos": [{"codigo": "MAT101", "nombre": "Cálculo I", "semestre": 1, "creditos": 6.0}],
        "tareas": [{"tarea": "t1", "nombre": "Deserción temprana"}],
        "n_estudiantes": 40, "titulados_estudiantes": [],
    }
    assert revisar_identidad(respuesta) == []
    assert revisar_identidad({"x": {"paterno": "a", "materno": "b"}}) == ["x.paterno", "x.materno"]


@pytest.mark.parametrize("url", [
    "/neural/programa/%zz/cohortes", "/neural/programa/%4", "/neural/programa/%ff/cohortes",
    "/neural/historico?facultad=%zz", "/neural/historico?facultad=%4", "/neural/historico?facultad=%ff",
])
def test_canonizar_escape_invalido_falla(url):
    """Strict contract shared with the Node port (which answers 404): bad escapes and non-UTF-8 bytes raise ValueError."""
    with pytest.raises(ValueError):
        canonizar(url)


# --------------------------------------------------------------------------- #
# Writer (opt-in: needs the DEV_* variables of the localhost dev database)
# --------------------------------------------------------------------------- #
import os  # noqa: E402
from urllib.parse import quote  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402

_DEV = ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")
_necesita_dev = pytest.mark.skipif(not all(os.environ.get(k) for k in _DEV), reason="DEV_* environment variables not set")
ESQUEMA = "neural_pub_test"


def _url_dev() -> str:
    env = os.environ
    return (f"postgresql+psycopg://{quote(env['DEV_USER'], safe='')}:{quote(env['DEV_PASSWORD'], safe='')}"
            f"@{env['DEV_HOST']}:{env['DEV_PORT']}/{env['DEV_DB']}")


@pytest.fixture()
def destino():
    """Throwaway schema on the local dev database; always dropped, even if the test fails."""
    url = _url_dev()
    eng = create_engine(url, future=True)
    with eng.begin() as con:
        con.execute(text(f"DROP SCHEMA IF EXISTS {ESQUEMA} CASCADE"))
        con.execute(text(f"CREATE SCHEMA {ESQUEMA}"))
    try:
        yield url
    finally:
        with eng.begin() as con:
            con.execute(text(f"DROP SCHEMA IF EXISTS {ESQUEMA} CASCADE"))
        eng.dispose()


def _conteos(url: str) -> tuple[int, int]:
    eng = create_engine(url, future=True)
    try:
        with eng.connect() as con:
            r = con.execute(text(f"SELECT count(*) FROM {ESQUEMA}.neural_respuesta")).scalar_one()
            p = con.execute(text(f"SELECT count(*) FROM {ESQUEMA}.neural_publicacion")).scalar_one()
        return r, p
    finally:
        eng.dispose()


def _tres() -> list[tuple[str, str, bytes]]:
    return [("/neural/programas", "", b'[{"cod_programa":"8616"}]'),
            ("/neural/historico", "facultad=Escuela de Ingenier\u00eda", b'{"jerarquia":[]}'),
            ("/neural/calidad", "", b'{"n":1}')]


@_necesita_dev
def test_publicar_crea_tablas_y_filas(destino):
    from publicar_warehouse_neural import publicar

    assert publicar(destino, ESQUEMA, _tres(), dry_run=False) == 0
    assert _conteos(destino) == (3, 1)
    eng = create_engine(destino, future=True)
    try:
        with eng.connect() as con:
            fila = con.execute(text(f"SELECT respuestas, bytes, version_exportador FROM {ESQUEMA}.neural_publicacion")).one()
            acento = con.execute(text(f"SELECT contenido FROM {ESQUEMA}.neural_respuesta WHERE consulta LIKE 'facultad=%'")).scalar_one()
    finally:
        eng.dispose()
    assert tuple(fila) == (3, sum(len(b) for _, _, b in _tres()), "2026-11-19")
    assert acento == {"jerarquia": []}
    # a second run replaces, it does not accumulate
    assert publicar(destino, ESQUEMA, _tres()[:2], dry_run=False) == 0
    assert _conteos(destino) == (2, 1)


@_necesita_dev
def test_publicar_falla_identidad_no_toca_destino(destino):
    from publicar_warehouse_neural import publicar

    assert publicar(destino, ESQUEMA, _tres()[:1], dry_run=False) == 0
    malas = [*_tres(), ("/neural/x", "", b'{"a":[{"nombre_estud":"X"}]}')]
    assert publicar(destino, ESQUEMA, malas, dry_run=False) == 1
    assert _conteos(destino) == (1, 1)


@_necesita_dev
def test_dry_run_no_escribe(destino):
    from publicar_warehouse_neural import publicar

    assert publicar(destino, ESQUEMA, _tres(), dry_run=True) == 0
    eng = create_engine(destino, future=True)
    try:
        with eng.connect() as con:
            existe = con.execute(text("SELECT to_regclass(:t)"), {"t": f"{ESQUEMA}.neural_respuesta"}).scalar()
    finally:
        eng.dispose()
    assert existe is None
    # no destination at all is fine for a dry run
    assert publicar(None, ESQUEMA, _tres(), dry_run=True) == 0


def test_main_exige_destino_sin_dry_run(monkeypatch, capsys):
    from publicar_warehouse_neural import main

    monkeypatch.delenv("NEURAL_WH_DATABASE_URL", raising=False)
    assert main(["--origen", "postgresql+psycopg://u:p@localhost/x"]) == 2
    assert "p@" not in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Pre-write checks (no database: they fail before any connection is opened)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("esquema", ["percepcion\n", "Percepcion", "1a", "a-b", "", "a b"])
def test_publicar_rechaza_esquema_invalido(esquema):
    from publicar_warehouse_neural import publicar

    salida = []
    assert publicar(None, esquema, [], dry_run=True, salida=salida.append) == 1
    assert "Invalid schema name" in salida[0]


def test_main_rechaza_esquema_con_salto_de_linea(capsys):
    from publicar_warehouse_neural import main

    assert main(["--origen", "postgresql+psycopg://u:p@localhost/x", "--dry-run", "--esquema", "percepcion\n"]) == 2
    assert "Invalid schema name" in capsys.readouterr().err


def test_publicar_claves_duplicadas_aborta_antes_de_escribir():
    from publicar_warehouse_neural import publicar

    respuestas = _tres() + [("/neural/programas", "", b"[]"), ("/neural/calidad", "", b"{}")]
    salida = []
    # a real (non-dry) run with an unreachable destination: the duplicate check must answer first
    assert publicar("postgresql+psycopg://u:p@127.0.0.1:1/x", "percepcion", respuestas, dry_run=False,
                    salida=salida.append) == 1
    texto = "\n".join(salida)
    assert "Duplicate" in texto and ": 2;" in texto and "first ruta: /neural/programas" in texto
    assert "Write failed" not in texto and "Responses:" not in texto
    assert "u:p" not in texto and "127.0.0.1" not in texto


def test_publicar_sin_duplicados_sigue_normal():
    from publicar_warehouse_neural import publicar

    salida = []
    assert publicar(None, "percepcion", _tres(), dry_run=True, salida=salida.append) == 0
    assert not any("Duplicate" in s for s in salida)
