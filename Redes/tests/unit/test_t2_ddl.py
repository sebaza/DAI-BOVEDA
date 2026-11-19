"""Static checks on migration 012 (no database)."""
import re
from pathlib import Path

from pipelines.migrate import validate_sql

DDL = Path(__file__).resolve().parents[2] / "sql" / "core" / "012_snapshot_t2.sql"


def test_migration_012_passes_the_schema_guard_and_only_creates():
    statements = validate_sql(DDL.read_text(encoding="utf-8"), DDL.name)
    assert statements and all(s.upper().startswith("CREATE") for s in statements)


def test_snapshot_t2_ddl_has_no_personal_or_teacher_identifying_columns():
    text = DDL.read_text(encoding="utf-8")
    cols = set(re.findall(r"^\s+(\w+)\s+(?:text|integer|bigint|numeric|boolean|real|smallint)\b", text, re.M))
    assert "sexo_equidad" in cols and "sexo" not in cols
    for bad in ("rut", "nombre", "correo", "email", "telefono", "nacimiento", "docente_key", "nrc"):
        assert bad not in cols
    assert {"intento_id", "split", "y", "n_hist_curso", "n_prereq"} <= cols


def test_ddl_columns_cover_the_builder_columns():
    import pytest

    pytest.importorskip("pandas")
    from pipelines.snapshots import features_t2 as F2

    text = DDL.read_text(encoding="utf-8")
    cols = set(re.findall(r"^\s+(\w+)\s+(?:text|integer|bigint|numeric|boolean|real|smallint)\b", text, re.M))
    from tests.unit.ddl_etapa_a import columnas_020

    cols |= columnas_020("snapshot_t2")                                                   # + 020 (P47, P74)
    m030 = (DDL.parent / "030_variables_nuevas_t1_t2.sql").read_text(encoding="utf-8")
    cols |= set(re.findall(r"ALTER TABLE neural_mart\.snapshot_t2 ADD COLUMN IF NOT EXISTS (\w+)", m030))   # + 030 (P117-P127)
    assert set(F2.SNAPSHOT_COLS_T2) <= cols
