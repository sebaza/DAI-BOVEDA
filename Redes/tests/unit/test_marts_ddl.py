"""Static checks on migration 009 and the mart SQL (no database)."""
import re
from pathlib import Path

from pipelines.marts import sql as S
from pipelines.migrate import validate_sql

SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "core"
DDL = SQL_DIR / "009_mart.sql"
DDL_TRASLADOS = SQL_DIR / "015_programa_traslados.sql"
DDL_NOTAS = SQL_DIR / "021_etapa_a_marts.sql"
DDL_MODELOS = SQL_DIR / "016_resumen_modelos.sql"


def test_migration_009_passes_the_schema_guard():
    statements = validate_sql(DDL.read_text(encoding="utf-8"), DDL.name)
    assert statements and all(s.upper().startswith("CREATE") for s in statements)


def test_every_mart_table_has_ddl_and_a_builder():
    text = DDL.read_text(encoding="utf-8") + DDL_TRASLADOS.read_text(encoding="utf-8") + DDL_NOTAS.read_text(encoding="utf-8")
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS neural_mart\.(\w+)", text))
    assert set(S.MART_TABLES) <= created
    assert created - set(S.MART_TABLES) == {"mart_construccion"}
    assert [t for t, _ in S.BUILD_ORDER] == list(S.MART_TABLES)


def test_builders_only_touch_their_own_table_and_use_schema_placeholders():
    for table, sql in S.BUILD_ORDER:
        assert re.match(rf"\s*INSERT INTO {{mart}}\.{table} \(", sql)
        assert not re.search(r"\bneural_\w+\.", sql), "schema names must come from the placeholders"
        rendered = S.render(sql, {"core": "neural_core", "mart": "neural_mart", "meta": "neural_meta"})
        assert "{core}" not in rendered and "{mart}" not in rendered and "{meta}" not in rendered


def test_no_personal_or_teacher_column_in_the_marts():
    text = DDL.read_text(encoding="utf-8").lower()
    for bad in ("docente", "rut ", "nombre_persona", "correo", "email", "telefono", "nacimiento", "sexo"):
        assert bad not in text


def test_period_sql_fragments_mirror_the_python_definitions():
    assert "substr(p, 5, 2) >= '20'" in S.ord_sem("p")
    assert S.is_regular("p") == "substr(p, 5, 2) IN ('10', '20')"
    assert "'20'" in S.periodo_de_fecha("d") and "<= 2" in S.periodo_de_fecha("d")


def test_migrations_015_and_016_pass_the_schema_guard_and_only_create():
    for path in (DDL_TRASLADOS, DDL_MODELOS):
        statements = validate_sql(path.read_text(encoding="utf-8"), path.name)
        assert statements and all(s.upper().startswith("CREATE") for s in statements)


def test_model_summary_tables_hold_aggregates_only():
    text = DDL_MODELOS.read_text(encoding="utf-8").lower()
    for bad in ("persona_key", "episodio_id", "rut ", "prediccion ", "nombre_persona"):
        assert bad not in text.replace("no person key", "").replace("no row-level prediction", "")
    assert "resumen_modelos_titular" in text and "resumen_modelos_delta" in text


def test_the_transfer_mart_is_not_filled_by_the_model_exporter():
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS neural_mart\.(\w+)", DDL_MODELOS.read_text(encoding="utf-8")))
    assert not created & set(S.MART_TABLES)       # the marts builder truncates MART_TABLES; the exporter owns its own


def test_migration_033_passes_the_schema_guard_and_drops_the_size_rule():
    path = SQL_DIR / "033_sin_supresion.sql"
    statements = validate_sql(path.read_text(encoding="utf-8"), path.name)
    assert statements and all(s.upper().startswith("ALTER") for s in statements)
    text = path.read_text(encoding="utf-8").lower()
    for item in ("resumen_tarea_calibracion_n_check", "resumen_tarea_grupo_n_check", "resumen_tarea_grupo_eventos_check",
                 "suprimido_promedio", "n_min", "grupos_suprimidos", "eventos_min"):
        assert item in text


def test_migration_034_adds_the_group_intervals_and_the_extra_levels():
    path = SQL_DIR / "034_grupo_intervalos.sql"
    statements = validate_sql(path.read_text(encoding="utf-8"), path.name)
    assert statements and all(s.upper().startswith("ALTER") for s in statements)
    text = path.read_text(encoding="utf-8").lower()
    for item in ("ap_lo", "ap_hi", "auc_lo", "auc_hi", "tasa_lo", "tasa_hi", "esperado_lo", "esperado_hi",
                 "pocos_casos boolean not null default false", "resumen_tarea_grupo_nivel_check", "'sexo'", "'via'",
                 "'tipo_colegio'"):
        assert item in text
    assert "persona_key" not in text and "create table" not in text
