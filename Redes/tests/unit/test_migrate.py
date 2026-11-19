import hashlib
import re
from pathlib import Path

import pytest

from pipelines.migrate import (
    ALLOWED_SCHEMAS,
    MigrationError,
    check_statement,
    discover_migrations,
    sha256_text,
    split_statements,
    validate_sql,
)
from pipelines.normalize.states import ESTADOS

SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "core"


def sql(name):
    return (SQL_DIR / name).read_text(encoding="utf-8")


def strip_comments(text):
    return re.sub(r"--[^\n]*", "", text)


# ---- splitter ---------------------------------------------------------------
def test_split_ignores_semicolons_in_strings_and_comments():
    text = "-- a; comment\nSELECT 'a;b';\n/* x; y */ SELECT 2;\n"
    assert [s.strip() for s in split_statements(text)] == ["SELECT 'a;b'", "SELECT 2"]


# ---- schema guard -----------------------------------------------------------
def test_allowed_schemas_are_exactly_the_neural_ones():
    assert set(ALLOWED_SCHEMAS) == {"neural_meta", "neural_stg", "neural_core", "neural_mart", "neural_test"}


@pytest.mark.parametrize(
    "stmt",
    [
        "CREATE TABLE neural_core.persona (persona_key text PRIMARY KEY)",
        "CREATE TABLE IF NOT EXISTS neural_meta.x (a int REFERENCES neural_meta.y (a))",
        "INSERT INTO neural_meta.dic_estado (cod_estado) VALUES ('M') ON CONFLICT DO NOTHING",
        "CREATE INDEX IF NOT EXISTS ix ON neural_stg.t (a)",
        "COMMENT ON TABLE neural_core.persona IS 'x'",
        "DROP SCHEMA IF EXISTS neural_test CASCADE",
        "INSERT INTO neural_meta.calendario_periodo (periodo) SELECT y::text FROM generate_series(1, 3) AS y",
    ],
)
def test_guard_accepts_neural_statements(stmt):
    assert check_statement(stmt) == []


@pytest.mark.parametrize(
    "stmt",
    [
        "CREATE TABLE boveda.x (a int)",
        "CREATE TABLE public.x (a int)",
        "CREATE TABLE x (a int)",
        "INSERT INTO percepcion.t VALUES (1)",
        "ALTER TABLE banner.ban_estados_academicos ADD COLUMN z int",
        "DROP SCHEMA neural_core CASCADE",
        "DROP SCHEMA boveda CASCADE",
        "CREATE SCHEMA other",
        "CREATE INDEX ix ON public.t (a)",
        "CREATE INDEX ix ON t (a)",
        "CREATE TABLE neural_core.x (a int REFERENCES boveda.modulos (id))",
        "UPDATE common.programa_d SET x = 1",
        "DELETE FROM banner.t",
        "TRUNCATE banner.t",
        "CREATE EXTENSION pgcrypto",
        "CREATE ROLE r",
        "GRANT ALL ON ALL TABLES IN SCHEMA public TO x",
        "DO $$ BEGIN PERFORM 1; END $$",
        "SET search_path TO public",
        "INSERT INTO neural_meta.t SELECT * FROM boveda.modulos",
    ],
)
def test_guard_rejects_everything_else(stmt):
    assert check_statement(stmt) != []


def test_validate_sql_raises_with_file_name():
    with pytest.raises(MigrationError) as exc:
        validate_sql("CREATE TABLE boveda.x (a int);", "099_bad.sql")
    assert "099_bad.sql" in str(exc.value)


# ---- discovery / hashing ----------------------------------------------------
def test_discover_orders_numbered_files_and_ignores_others(tmp_path):
    for name in ("002_b.sql", "001_a.sql", "010_c.sql", "notes.txt", "x_003.sql"):
        (tmp_path / name).write_text("SELECT 1;", encoding="utf-8")
    assert [p.name for p in discover_migrations(tmp_path)] == ["001_a.sql", "002_b.sql", "010_c.sql"]


def test_sha256_text_matches_hashlib():
    assert sha256_text("abc") == hashlib.sha256(b"abc").hexdigest()


# ---- the real migration files ----------------------------------------------
def test_real_migrations_exist_and_pass_the_guard():
    files = discover_migrations(SQL_DIR)
    assert [f.name for f in files][:4] == ["001_esquemas.sql", "002_meta.sql", "003_stg.sql", "004_core.sql"]
    for f in files:
        validate_sql(f.read_text(encoding="utf-8"), f.name)


def test_real_migrations_are_idempotent_by_construction():
    for f in discover_migrations(SQL_DIR):
        for stmt in split_statements(f.read_text(encoding="utf-8")):
            s = " ".join(stmt.split()).upper()
            if s.startswith("CREATE TABLE"):
                assert "IF NOT EXISTS" in s, stmt[:80]
            if s.startswith("CREATE SCHEMA"):
                assert "IF NOT EXISTS" in s, stmt[:80]
            if s.startswith("CREATE INDEX") or s.startswith("CREATE UNIQUE INDEX"):
                assert "IF NOT EXISTS" in s, stmt[:80]
            if s.startswith("INSERT INTO"):
                assert "ON CONFLICT" in s, stmt[:80]


def test_dic_estado_seed_matches_python_dictionary():
    text = sql("002_meta.sql")
    block = text[text.index("neural_meta.dic_estado") :]
    rows = re.findall(r"\('(.)',\s*'((?:[^']|'')*)',\s*'([a-z_]+)',\s*(true|false)", block)
    seeded = {c: (n.replace("''", "'"), clase, corr == "true") for c, n, clase, corr in rows}
    assert set(seeded) == set(ESTADOS)
    for code, (nombre, clase) in ESTADOS.items():
        assert seeded[code][:2] == (nombre, clase)
        assert seeded[code][2] == (clase == "correccion_sistema")


def test_dic_tipo_admision_seed_has_52_codes():
    text = sql("002_meta.sql")
    block = text[text.index("INSERT INTO neural_meta.dic_tipo_admision") :]
    block = block[: block.index("ON CONFLICT")]
    assert len(re.findall(r"^\s+\('[A-Z0-9]{2}',", block, flags=re.M)) == 52


# ---- (ad) no personal columns in stg / core / mart -------------------------
FORBIDDEN = {
    "rut", "rut_profesor", "rut_estud", "rut_prof", "nombre", "nombre1", "nombre2", "apellidos",
    "ap_paterno", "ap_materno", "apellido_paterno", "apellido_materno", "nombre_social", "profesor",
    "correo_ucn", "correo_personal", "telefono_fijo", "telefono_celular", "fecha_nacimiento", "edad",
    "pasaporte", "nacionalidad", "etnia", "colegio", "cod_colegio", "comuna", "ciudad", "cod_ciudad",
    "provincia_colegio", "nombre_estud", "nombre_prof",
}


@pytest.mark.parametrize("name", ["003_stg.sql", "004_core.sql"])
def test_ad_no_personal_columns(name):
    idents = set(re.findall(r"[a-z_][a-z0-9_]*", strip_comments(sql(name))))
    assert idents & FORBIDDEN == set()


def test_ad_allowed_context_columns_are_present():
    stg = strip_comments(sql("003_stg.sql"))
    for col in ("sexo", "region_colegio", "comuna_colegio", "cod_comuna", "persona_key", "docente_key", "carga_id"):
        assert re.search(rf"\b{col}\b", stg), col
