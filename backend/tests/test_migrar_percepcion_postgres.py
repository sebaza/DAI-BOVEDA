"""Migración SQLite -> PostgreSQL de Percepción (`scripts/migrar_percepcion_postgres.py`).

* `validar_largos` no necesita Postgres: corre siempre.
* La copia real contra Postgres es opt-in (``PERCEPCION_TEST_DATABASE_URL``) y trabaja en
  esquemas descartables; el esquema real ``percepcion`` no se toca.

Los datos de origen se escriben con ``sqlite3`` CRUDO y no por el ORM para reproducir la
base real: fechas como TEXTO, booleanos como 0/1 y JSON como cadena.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import String, create_engine, text

from app.database import Base
from app.services.percepcion import models  # noqa: F401
from pg_percepcion import URL, esquema_efimero, requiere_pg

RUTA_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrar_percepcion_postgres.py"
_spec = importlib.util.spec_from_file_location("migrar_percepcion_postgres", RUTA_SCRIPT)
migrar_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrar_mod)

SECRETO = "texto-que-no-debe-aparecer-en-ningun-mensaje"


def _crear_origen(ruta: Path, *, valor_nuevo: str = "organizacion_estudiantil") -> Path:
    """SQLite con el esquema de los modelos y unas filas escritas como las escribe el worker."""
    eng = create_engine(f"sqlite:///{ruta.as_posix()}", future=True)
    Base.metadata.create_all(eng)
    eng.dispose()
    con = sqlite3.connect(ruta)
    con.executescript(
        f"""
        INSERT INTO percepcion_cuenta (id, handle, nombre, tipo, campus, activa, creada_en, origen)
            VALUES (1, 'ucn', 'UCN', 'institucional', 'Antofagasta', 1, '2026-07-22 21:06:11.496281', 'interno'),
                   (7, 'fac', 'Facultad', 'facultad', 'Coquimbo', 0, '2026-07-23 10:00:00.000000', 'externo');
        INSERT INTO percepcion_publicacion (id, cuenta_id, external_id, fecha_publicacion, tipo, caption, n_comentarios, n_likes)
            VALUES (3, 1, 'p3', '2026-03-01 12:30:00.000000', 'post', '{SECRETO}', 2, 5);
        INSERT INTO percepcion_comentario (id, publicacion_id, external_id, autor_hash, texto, fecha_comentario, idioma, n_likes, tema)
            VALUES (10, 3, 'c10', 'h10', '{SECRETO}', '2026-03-02 08:00:00.000000', 'es', 1, 'otros'),
                   (11, 3, 'c11', 'h11', '{SECRETO}', '2026-03-03 09:00:00.000000', 'es', 0, NULL);
        INSERT INTO percepcion_score (id, comentario_id, modelo, sentimiento, prob_pos, prob_neu, prob_neg)
            VALUES (20, 10, 'm', 'POS', 0.9, 0.05, 0.05);
        INSERT INTO percepcion_hecho_diario (id, fecha, campus, tema, n_comentarios, n_pos, n_neu, n_neg,
                suma_peso, peso_pos, peso_neg, suma_pos, suma_neg, suma_ganadora, emociones, origen)
            VALUES (30, '2026-03-02', 'Antofagasta', 'otros', 2, 1, 1, 0, 2.0, 1.0, 0.0, 1.0, 0.0, 1.8,
                    '{{"alegria": 1, "enojo": 1}}', 'interno'),
                   (31, '2026-03-03', 'Antofagasta', 'otros', 1, 0, 1, 0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.9,
                    NULL, 'interno');
        INSERT INTO percepcion_tema_custom (id, clave, etiqueta, keywords, creado_en)
            VALUES (40, 'beca', 'Becas', '["beca", "gratuidad"]', '2026-03-04 00:00:00.000000');
        INSERT INTO percepcion_correccion (id, comentario_id, campo, valor_original, valor_nuevo, confirmado)
            VALUES (50, 10, 'tema', 'otros', '{valor_nuevo}', 0);
        INSERT INTO percepcion_evento (id, nombre, tipo, fecha_inicio, fecha_fin)
            VALUES (60, 'Paro', 'paro', '2026-03-05', NULL);
        """
    )
    con.commit()
    con.close()
    return ruta


# ---------------------------------------------------------------------------
# Validación de largos y bordes (sin Postgres)
# ---------------------------------------------------------------------------

def _largos_modelo() -> dict[str, dict[str, int]]:
    return {
        t.name: {c.name: c.type.length for c in t.columns
                 if isinstance(c.type, String) and c.type.length}
        for t in migrar_mod._tablas()
    }


def test_validar_largos_acepta_el_slug_mas_largo_que_el_modelo_permite(tmp_path):
    origen = _crear_origen(tmp_path / "o.db", valor_nuevo="servicios_institucionales")  # 25 < 40
    eng = migrar_mod.abrir_origen(origen)
    with eng.connect() as con:
        assert migrar_mod.validar_largos(con, _largos_modelo()) == []
    eng.dispose()


def test_validar_largos_nombra_la_columna_y_no_filtra_el_valor(tmp_path):
    origen = _crear_origen(tmp_path / "o.db", valor_nuevo="x" * 41)
    eng = migrar_mod.abrir_origen(origen)
    with eng.connect() as con:
        problemas = migrar_mod.validar_largos(con, _largos_modelo())
        angosto = _largos_modelo()
        angosto["percepcion_publicacion"]["tipo"] = 2  # 'post' (4) no entra en 2
        problemas_angosto = migrar_mod.validar_largos(con, angosto)
    eng.dispose()
    assert len(problemas) == 1
    assert problemas[0].startswith("percepcion_correccion.valor_nuevo")
    assert "xxxx" not in problemas[0]
    assert any(p.startswith("percepcion_publicacion.tipo") for p in problemas_angosto)


def test_el_origen_se_abre_solo_lectura(tmp_path):
    origen = _crear_origen(tmp_path / "o.db")
    eng = migrar_mod.abrir_origen(origen)
    with pytest.raises(Exception, match="readonly|read-only|read only"):
        with eng.begin() as con:
            con.execute(text("DELETE FROM percepcion_cuenta"))
    eng.dispose()


def test_origen_inexistente_falla_claro(tmp_path):
    with pytest.raises(migrar_mod.MigracionError, match="No existe"):
        migrar_mod.abrir_origen(tmp_path / "no_existe.db")


def test_destino_que_no_es_postgres_se_rechaza(tmp_path):
    origen = _crear_origen(tmp_path / "o.db")
    with pytest.raises(migrar_mod.MigracionError, match="PostgreSQL"):
        migrar_mod.migrar(origen, "sqlite:///otra.db", salida=lambda *_: None)


def test_sin_destino_el_script_sale_con_error(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("PERCEPCION_DATABASE_URL", raising=False)
    assert migrar_mod.main(["--origen", str(_crear_origen(tmp_path / "o.db"))]) == 2
    assert "destino" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Copia real contra Postgres
# ---------------------------------------------------------------------------

def _contar(url: str, tabla: str) -> int:
    eng = create_engine(url, future=True)
    try:
        with eng.connect() as con:
            return con.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()
    finally:
        eng.dispose()


@requiere_pg
class TestCopia:
    def _migrar(self, origen, esquema, **kw):
        return migrar_mod.migrar(origen, URL, esquema=esquema, salida=lambda *_: None, **kw)

    def test_copia_tipos_conteos_y_secuencias(self, tmp_path):
        origen = _crear_origen(tmp_path / "o.db")
        with esquema_efimero("percepcion_test_mig1", crear_tablas=False) as url:
            copiadas = self._migrar(origen, "percepcion_test_mig1")
            assert copiadas["percepcion_cuenta"] == 2
            assert copiadas["percepcion_comentario"] == 2
            assert copiadas["percepcion_evento"] == 1

            eng = create_engine(url, future=True)
            with eng.begin() as con:
                cuenta = con.execute(text(
                    "SELECT activa, creada_en, pg_typeof(activa)::text, pg_typeof(creada_en)::text "
                    "FROM percepcion_cuenta WHERE id = 7")).one()
                assert cuenta[0] is False and cuenta[2] == "boolean"
                assert cuenta[1].year == 2026 and cuenta[3] == "timestamp without time zone"
                hecho = con.execute(text(
                    "SELECT pg_typeof(fecha)::text, emociones FROM percepcion_hecho_diario WHERE id = 30")).one()
                assert hecho[0] == "date" and hecho[1] == {"alegria": 1, "enojo": 1}
                assert con.execute(text(
                    "SELECT emociones IS NULL FROM percepcion_hecho_diario WHERE id = 31")).scalar_one() is True
                assert con.execute(text(
                    "SELECT keywords FROM percepcion_tema_custom")).scalar_one() == ["beca", "gratuidad"]
                # la secuencia queda en max(id)+1: el siguiente INSERT sin id no choca
                nuevo = con.execute(text(
                    "INSERT INTO percepcion_cuenta (handle, nombre, tipo) VALUES ('n','n','n') RETURNING id"
                )).scalar_one()
                assert nuevo == 8
            eng.dispose()

    def test_se_niega_si_el_destino_tiene_datos(self, tmp_path):
        origen = _crear_origen(tmp_path / "o.db")
        with esquema_efimero("percepcion_test_mig2", crear_tablas=False) as url:
            self._migrar(origen, "percepcion_test_mig2")
            eng = create_engine(url, future=True)
            with eng.begin() as con:  # trabajo hecho en Postgres que NO debe perderse
                con.execute(text("UPDATE percepcion_cuenta SET nombre = 'EDITADO' WHERE id = 1"))
            eng.dispose()
            with pytest.raises(migrar_mod.MigracionError, match="--reemplazar"):
                self._migrar(origen, "percepcion_test_mig2")
            eng = create_engine(url, future=True)
            with eng.connect() as con:
                assert con.execute(text("SELECT nombre FROM percepcion_cuenta WHERE id = 1")).scalar_one() == "EDITADO"
            eng.dispose()

    def test_reemplazar_vacia_y_recarga(self, tmp_path):
        origen = _crear_origen(tmp_path / "o.db")
        with esquema_efimero("percepcion_test_mig3", crear_tablas=False) as url:
            self._migrar(origen, "percepcion_test_mig3")
            eng = create_engine(url, future=True)
            with eng.begin() as con:
                con.execute(text("UPDATE percepcion_cuenta SET nombre = 'EDITADO' WHERE id = 1"))
                con.execute(text("DELETE FROM percepcion_evento"))
            eng.dispose()
            self._migrar(origen, "percepcion_test_mig3", reemplazar=True)
            assert _contar(url, "percepcion_evento") == 1
            eng = create_engine(url, future=True)
            with eng.connect() as con:
                assert con.execute(text("SELECT nombre FROM percepcion_cuenta WHERE id = 1")).scalar_one() == "UCN"
            eng.dispose()

    def test_desborde_aborta_sin_dejar_nada_ni_filtrar_valores(self, tmp_path):
        origen = _crear_origen(tmp_path / "o.db", valor_nuevo="y" * 41)
        with esquema_efimero("percepcion_test_mig4", crear_tablas=False) as url:
            with pytest.raises(migrar_mod.MigracionError) as exc:
                self._migrar(origen, "percepcion_test_mig4")
            assert "percepcion_correccion.valor_nuevo" in str(exc.value)
            assert "yyyy" not in str(exc.value)
            # la transacción se revirtió: ni siquiera quedaron las tablas creadas
            eng = create_engine(url, future=True)
            with eng.connect() as con:
                assert con.execute(text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'percepcion_test_mig4'")).scalar_one() == 0
            eng.dispose()

    def test_main_no_imprime_la_url(self, tmp_path, capsys):
        origen = _crear_origen(tmp_path / "o.db")
        with esquema_efimero("percepcion_test_mig5", crear_tablas=False):
            codigo = migrar_mod.main(["--origen", str(origen), "--destino", URL,
                                      "--esquema", "percepcion_test_mig5"])
        salida = capsys.readouterr()
        assert codigo == 0
        assert "origen 2 -> destino 2" in salida.out
        assert URL not in salida.out + salida.err

    def test_avisa_de_tablas_del_origen_sin_modelo(self, tmp_path):
        origen = _crear_origen(tmp_path / "o.db")
        con = sqlite3.connect(origen)
        con.executescript("CREATE TABLE percepcion_contexto (id INTEGER PRIMARY KEY, valor FLOAT);"
                          "INSERT INTO percepcion_contexto (id, valor) VALUES (1, 2.5);")
        con.commit()
        con.close()
        lineas: list[str] = []
        with esquema_efimero("percepcion_test_mig6", crear_tablas=False):
            migrar_mod.migrar(origen, URL, esquema="percepcion_test_mig6", salida=lineas.append)
        assert any("percepcion_contexto" in l and "sin modelo" in l and "1 filas" in l for l in lineas)


# ---------------------------------------------------------------------------
# El almacén (marcado) no admite cargas crudas (sin Postgres: la función corre sobre cualquier conexión)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave,valor,esperado", [
    ("autor_seudonimizado", "true", True),
    ("ext_comentario_seudonimizado", "true", True),
    ("autor_seudonimizado", "false", False),
    ("otra_cosa", "true", False),
])
def test_destino_marcado_detecta_el_almacen(tmp_path, clave, valor, esperado):
    eng = create_engine(f"sqlite:///{(tmp_path / 'd.db').as_posix()}", future=True)
    Base.metadata.create_all(eng)
    with eng.begin() as con:
        assert migrar_mod.destino_marcado(con, None) is False
        con.execute(text("INSERT INTO percepcion_meta (clave, valor) VALUES (:c, :v)"),
                    {"c": clave, "v": valor})
        assert migrar_mod.destino_marcado(con, None) is esperado
    eng.dispose()


def test_destino_sin_tabla_meta_no_esta_marcado(tmp_path):
    eng = create_engine(f"sqlite:///{(tmp_path / 'd.db').as_posix()}", future=True)
    with eng.begin() as con:
        assert migrar_mod.destino_marcado(con, None) is False
    eng.dispose()


def test_migrar_se_niega_antes_de_copiar_si_el_destino_es_el_almacen():
    fuente = RUTA_SCRIPT.read_text(encoding="utf-8")
    # La guarda corre tras create_all y antes de la comprobación de --reemplazar.
    assert fuente.index("destino_marcado(dst, esquema)") < fuente.index("existentes = _con_filas")
