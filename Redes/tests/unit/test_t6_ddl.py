"""Static checks on migration 018 (no database)."""
import re
from pathlib import Path

from pipelines.migrate import validate_sql

DDL = Path(__file__).resolve().parents[2] / "sql" / "core" / "018_snapshot_t6.sql"
TIPOS = r"(?:text|integer|bigint|numeric|boolean|real|smallint)"


def test_migration_018_passes_the_schema_guard_and_only_creates():
    statements = validate_sql(DDL.read_text(encoding="utf-8"), DDL.name)
    assert statements and all(s.upper().startswith("CREATE") for s in statements)


def test_snapshot_t6_ddl_has_no_personal_columns_and_keeps_sex_for_fairness_only():
    text = DDL.read_text(encoding="utf-8")
    cols = set(re.findall(rf"^\s+(\w+)\s+{TIPOS}\b", text, re.M))
    assert "sexo_equidad" in cols and "sexo" not in cols
    for bad in ("rut", "nombre", "correo", "email", "telefono", "nacimiento", "periodo_postgrado", "cod_programa_postgrado"):
        assert bad not in cols
    assert {"episodio_id", "evento", "tiempo", "seguimiento", "split", "anio_egreso"} <= cols


def test_ddl_columns_equal_the_builder_columns_and_the_splits_are_the_rule_ones():
    from pipelines.snapshots import features_t6 as F6
    from pipelines.snapshots import rules_t6 as R6

    text = DDL.read_text(encoding="utf-8")
    tabla = text.split("snapshot_t6_resumen")[0]
    cols = set(re.findall(rf"^\s+(\w+)\s+{TIPOS}\b", tabla, re.M))
    from tests.unit.ddl_etapa_a import columnas_020

    cols |= columnas_020("snapshot_t6")                                                   # + 020 (P47, P77)
    assert cols == set(F6.SNAPSHOT_COLS_T6)
    check = re.search(r"split\s+text\s+NOT NULL CHECK \(split IN \(([^)]*)\)", text, re.S).group(1)
    assert set(re.findall(r"'(\w+)'", check)) == set(R6.SPLITS)
