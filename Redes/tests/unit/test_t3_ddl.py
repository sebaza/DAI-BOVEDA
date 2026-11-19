"""Static checks on migration 013 (no database)."""
import re
from pathlib import Path

from pipelines.migrate import validate_sql

DDL = Path(__file__).resolve().parents[2] / "sql" / "core" / "013_snapshot_t3.sql"
TIPOS = r"(?:text|integer|bigint|numeric|boolean|real|smallint)"


def test_migration_013_passes_the_schema_guard_and_only_creates():
    statements = validate_sql(DDL.read_text(encoding="utf-8"), DDL.name)
    assert statements and all(s.upper().startswith("CREATE") for s in statements)


def test_snapshot_t3_ddl_has_no_personal_columns_and_keeps_sex_for_fairness_only():
    text = DDL.read_text(encoding="utf-8")
    cols = set(re.findall(rf"^\s+(\w+)\s+{TIPOS}\b", text, re.M))
    assert "sexo_equidad" in cols and "sexo" not in cols
    for bad in ("rut", "nombre", "correo", "email", "telefono", "nacimiento"):
        assert bad not in cols
    assert {"episodio_id", "k", "tiempo", "causa", "seguimiento_max", "split"} <= cols


def test_ddl_columns_cover_the_builder_columns():
    import pytest

    pytest.importorskip("pandas")
    from pipelines.snapshots import features_t3 as F3

    text = DDL.read_text(encoding="utf-8")
    tabla = text.split("snapshot_t3_semestre")[0]
    cols = set(re.findall(rf"^\s+(\w+)\s+{TIPOS}\b", tabla, re.M))
    cols |= set(re.findall(rf"add column if not exists (\w+) {TIPOS}\b", DDL_014.read_text(encoding="utf-8"), re.I))   # + 014
    from tests.unit.ddl_etapa_a import columnas_020

    cols |= columnas_020("snapshot_t3")                                                   # + 020 (P47)
    assert set(F3.SNAPSHOT_COLS_T3) <= cols
    assert cols <= set(F3.SNAPSHOT_COLS_T3)                      # nothing in the table that the builder does not fill


DDL_014 = Path(__file__).resolve().parents[2] / "sql" / "core" / "014_snapshot_t3_plan_comun.sql"


def test_migration_014_only_alters_the_snapshot_and_adds_the_plan_comun_columns():
    statements = validate_sql(DDL_014.read_text(encoding="utf-8"), DDL_014.name)
    assert statements and all(s.upper().startswith("ALTER TABLE NEURAL_MART.SNAPSHOT_T3") for s in statements)
    text = DDL_014.read_text(encoding="utf-8")
    assert {"trayectoria_plan_comun", "especialidad_conocida_al_corte", "episodio_especialidad_id"} <= set(
        re.findall(rf"add column if not exists (\w+) {TIPOS}\b", text, re.I))
    assert "sexo" not in text.lower().replace("sexo_equidad", "")
