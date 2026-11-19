"""Static checks on migrations 024 (staging) and 025 (snapshot columns) of the benefits."""
import re
from pathlib import Path

from pipelines.migrate import validate_sql
from pipelines.snapshots import features_beneficios as FB
from pipelines.snapshots import t1 as T1

SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "core"


def test_migrations_024_and_025_pass_the_schema_guard():
    for name in ("024_beneficios.sql", "025_snapshot_t1_beneficios.sql"):
        assert validate_sql((SQL_DIR / name).read_text(encoding="utf-8"), name)


def test_the_staging_table_has_no_rut_and_no_program_name():
    text = (SQL_DIR / "024_beneficios.sql").read_text(encoding="utf-8").lower()
    for bad in ("rut", "carrera ", "nombre_persona"):
        assert bad not in text.replace("cod_carrera", "")
    assert "persona_key" in text and "banner_beneficios" in text


def test_every_benefit_feature_of_the_snapshot_has_a_column_in_025():
    text = (SQL_DIR / "025_snapshot_t1_beneficios.sql").read_text(encoding="utf-8")
    cols = set(re.findall(r"ADD COLUMN IF NOT EXISTS (\w+) ", text))
    assert cols == set(FB.COLS_BENEFICIOS)
    assert set(FB.COLS_BENEFICIOS) <= set(T1.SNAPSHOT_COLS)


def test_no_second_semester_or_total_column_exists_anywhere():
    text = (SQL_DIR / "025_snapshot_t1_beneficios.sql").read_text(encoding="utf-8").lower()
    assert "sem2" not in text and "monto_total" not in text
