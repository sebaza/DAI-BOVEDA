"""Static checks on migration 031 (side tables of the new variables of T3-T6)."""
import re
from pathlib import Path

from pipelines.migrate import validate_sql
from pipelines.snapshots import features_variables as FV

SQL = Path(__file__).resolve().parents[2] / "sql" / "core" / "031_variables_nuevas_t3_t6.sql"


def test_migration_031_passes_the_schema_guard_and_only_creates_tables():
    texto = SQL.read_text(encoding="utf-8")
    stmts = validate_sql(texto, SQL.name)
    assert stmts and all(s.lower().startswith("create table if not exists neural_mart.") for s in stmts)


def test_every_new_variable_has_exactly_one_column():
    texto = SQL.read_text(encoding="utf-8")
    bloque = texto.split("snapshot_variables_nuevas (")[1].split(");")[0]
    cols = re.findall(r"^\s{4}(\w+)\s+(?:bigint|smallint|double precision|boolean)", bloque, flags=re.M)
    assert set(cols) == {"episodio_id", "k", *FV.VARIABLES_NUEVAS}
    assert len(cols) == len(set(cols))


def test_no_person_identifier_in_the_side_tables():
    texto = SQL.read_text(encoding="utf-8").lower()
    assert "persona_key" not in texto.replace("no persona_key", "") and "rut" not in re.findall(r"\b\w+\b", texto)
