"""Static checks on migrations 019-021 (stage A, no database)."""
import re
from pathlib import Path

from pipelines.migrate import validate_sql

SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "core"


def test_migrations_019_to_022_pass_the_schema_guard():
    for name in ("019_etapa_a_core.sql", "020_etapa_a_snapshots.sql", "021_etapa_a_marts.sql", "022_banda_nota_p84.sql"):
        assert validate_sql((SQL_DIR / name).read_text(encoding="utf-8"), name)


def test_the_calendar_check_lists_the_p45_types_and_the_rows_are_remapped():
    from pipelines.normalize.periods import parse_periodo

    text = (SQL_DIR / "019_etapa_a_core.sql").read_text(encoding="utf-8")
    check = re.search(r"CHECK \(tipo_periodo IN \(([^)]*)\)", text, re.S).group(1)
    declared = set(re.findall(r"'(\w+)'", check))
    assert {"verano", "invierno", "excepcional"} <= declared and "verano_invierno" not in declared
    for sufijo, tipo in (("15", "invierno"), ("25", "verano"), ("21", "excepcional")):
        assert re.search(rf"SET tipo_periodo = '{tipo}' WHERE sufijo = '{sufijo}'", text)
        assert parse_periodo(f"2024{sufijo}").tipo_periodo == tipo


def test_the_postgrado_and_faculty_tables_have_no_personal_columns():
    text = (SQL_DIR / "019_etapa_a_core.sql").read_text(encoding="utf-8").lower()
    for bad in ("nombre_persona", "nacionalidad", "correo", "telefono", "nacimiento", " rut ", "sexo"):
        assert bad not in text


def test_the_migration_adds_the_p54_flag_with_a_default_so_existing_rows_stay_valid():
    text = (SQL_DIR / "019_etapa_a_core.sql").read_text(encoding="utf-8")
    assert "reemplazada_mismo_periodo boolean NOT NULL DEFAULT false" in text
