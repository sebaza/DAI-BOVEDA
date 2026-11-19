"""Static checks on migration 017 (no database)."""
import re
from pathlib import Path

from pipelines.migrate import validate_sql

DDL = Path(__file__).resolve().parents[2] / "sql" / "core" / "017_snapshot_t45.sql"
TIPOS = r"(?:text|integer|bigint|numeric|boolean|real|smallint)"


def test_migration_017_passes_the_schema_guard_and_only_creates():
    statements = validate_sql(DDL.read_text(encoding="utf-8"), DDL.name)
    assert statements and all(s.upper().startswith("CREATE") for s in statements)


def test_snapshot_t45_ddl_has_no_personal_columns_and_keeps_sex_for_fairness_only():
    text = DDL.read_text(encoding="utf-8")
    cols = set(re.findall(rf"^\s+(\w+)\s+{TIPOS}\b", text, re.M))
    assert "sexo_equidad" in cols and "sexo" not in cols
    for bad in ("rut", "nombre", "correo", "email", "telefono", "nacimiento"):
        assert bad not in cols
    assert {"episodio_id", "k", "resultado", "seguimiento_max", "split"} <= cols


def test_ddl_columns_equal_the_builder_columns_and_the_outcomes_are_the_rule_ones():
    from pipelines.snapshots import features_t45 as F45
    from pipelines.snapshots import rules_t45 as R45

    text = DDL.read_text(encoding="utf-8")
    tabla = text.split("snapshot_t45_semestre")[0]
    cols = set(re.findall(rf"^\s+(\w+)\s+{TIPOS}\b", tabla, re.M))
    from tests.unit.ddl_etapa_a import columnas_020

    cols |= columnas_020("snapshot_t45")                                                  # + 020 (P47, P72, P75)
    assert cols == set(F45.SNAPSHOT_COLS_T45)
    check = re.search(r"resultado\s+text\s+NOT NULL CHECK \(resultado IN \(([^)]*)\)", text, re.S).group(1)
    assert set(re.findall(r"'(\w+)'", check)) == set(R45.RESULTADOS)
