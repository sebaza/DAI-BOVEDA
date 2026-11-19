"""Extraction specs: privacy guard, stg column parity and pseudonymization of rows."""
import re
from pathlib import Path

import pytest

from pipelines.common.pseudo import docente_key, persona_key
from pipelines.extract import sources as S

SECRET = "k" * 64
STG_SQL = (Path(__file__).resolve().parents[2] / "sql" / "core")


def _ddl_columns():
    """neural_stg table -> ordered column names, parsed from every sql/core file."""
    tables = {}
    for f in sorted(STG_SQL.glob("*.sql")):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"CREATE TABLE IF NOT EXISTS neural_stg\.(\w+) \((.*?)\n\);", text, re.S):
            cols = []
            for line in m.group(2).splitlines():
                line = line.strip()
                if not line or line.startswith("--") or line.startswith("PRIMARY") or line.startswith("CONSTRAINT"):
                    continue
                cols.append(line.split()[0])
            tables[m.group(1)] = cols
    return tables


def test_every_source_with_a_stg_table_matches_the_ddl():
    ddl = _ddl_columns()
    for src in S.SOURCES:
        if src.stg_table is None:
            continue
        assert src.stg_table in ddl, src.fuente
        cols = [c for c in ddl[src.stg_table] if c not in ("stg_id", "carga_id")]
        assert [c.stg for c in src.columns] == cols, src.fuente


def test_no_forbidden_column_is_selected():
    for src in S.SOURCES:
        for col in src.columns:
            assert not S.is_forbidden_column(col.wh), (src.fuente, col.wh)
        S.assert_safe_columns(src)  # must not raise


@pytest.mark.parametrize("name", [
    "nombre", "nombre1", "ap_paterno", "apellidos", "apellido_materno", "nombre_social", "correo_ucn",
    "telefono_celular", "fecha_nacimiento", "edad", "pasaporte", "colegio", "cod_colegio", "profesor",
    "etnia", "nacionalidad", "comuna", "ciudad", "provincia_colegio", "direccion_particular",
])
def test_forbidden_columns_are_refused(name):
    assert S.is_forbidden_column(name)


@pytest.mark.parametrize("name", [
    "rut", "sexo", "region_colegio", "comuna_colegio", "cod_comuna", "tipo_colegio", "depend_colegio",
    "nombre_estado", "nombre_programa", "nombre_asignatura", "rut_profesor", "tipo_profesor",
])
def test_allowed_columns_pass(name):
    assert not S.is_forbidden_column(name)


def test_assert_safe_columns_raises_for_a_personal_column():
    bad = S.Source("x", "banner.x", "t", (S.Col("nombre", "nombre"),), S.TS_NONE)
    with pytest.raises(ValueError):
        S.assert_safe_columns(bad)


def test_select_sql_lists_only_declared_columns():
    src = S.by_name("ban_estados_academicos")
    sql = src.select_sql
    assert sql.startswith("SELECT rut, sorlcur,")
    assert sql.endswith("FROM banner.ban_estados_academicos")
    assert "*" not in sql
    assert re.search(r"\bnombre\b", sql) is None


def test_transform_replaces_the_rut_with_the_key():
    src = S.by_name("ban_estados_academicos")
    tr = S.RowTransformer(src, SECRET)
    raw = ["98.765.432-1"] + [None] * (len(src.columns) - 1)
    out = tr(tuple(raw))
    assert out[0] == persona_key("98.765.432-1", SECRET)
    assert re.fullmatch(r"[0-9a-f]{64}", out[0])
    assert "98765432" not in "".join(str(v) for v in out if v is not None)


def test_transform_skips_rows_without_a_required_key():
    src = S.by_name("ban_estados_academicos")
    tr = S.RowTransformer(src, SECRET)
    assert tr(tuple([None] + [None] * (len(src.columns) - 1))) is None
    assert tr.skipped == 1


def test_teacher_key_uses_the_teacher_domain_and_may_be_null():
    src = S.by_name("ban_oferta_academica")
    tr = S.RowTransformer(src, SECRET)
    idx = [c.wh for c in src.columns].index("rut_profesor")
    raw = [None] * len(src.columns)
    raw[idx] = "9.999.999-9"
    out = tr(tuple(raw))
    assert out[idx] == docente_key("9.999.999-9", SECRET)
    assert out[idx] != persona_key("9.999.999-9", SECRET)
    raw[idx] = None
    assert tr(tuple(raw))[idx] is None


def test_admission_keeps_rows_without_rut():
    src = S.by_name("banner_admision")
    tr = S.RowTransformer(src, SECRET)
    out = tr(tuple([None] * len(src.columns)))
    assert out is not None and out[0] is None


def test_row_transformer_caches_keys():
    src = S.by_name("ban_estados_academicos")
    tr = S.RowTransformer(src, SECRET)
    raw = tuple(["1-9"] + [None] * (len(src.columns) - 1))
    assert tr(raw)[0] == tr(raw)[0]
    assert tr.cache_size == 1


def test_idempotency_decision():
    assert S.should_skip(existing_ok=True, force=False) is True
    assert S.should_skip(existing_ok=True, force=True) is False
    assert S.should_skip(existing_ok=False, force=False) is False


def test_sha256_of_the_statement_is_stable():
    src = S.by_name("banner_titulados")
    assert src.sql_sha256 == src.sql_sha256 and len(src.sql_sha256) == 64


# ---- stage A (P76, P77): faculty dictionary and postgrado states -------------------------------------------------------
def test_stage_a_sources_are_registered_with_their_views():
    assert S.by_name("facultad_d").view == "common.facultad_d"
    pos = S.by_name("ban_estados_academicos_pos")
    assert pos.view == "banner.ban_estados_academicos_pos"
    assert pos.stg_table == "ban_estados_academicos_pos"
    assert {"facultad_d", "ban_estados_academicos_pos"} <= set(S.all_fuentes())


def test_postgrado_states_never_select_the_person_name_nationality_or_sex():
    pos = S.by_name("ban_estados_academicos_pos")
    wh = [c.wh for c in pos.columns]
    for bad in ("nombre", "nacionalidad", "sexo"):
        assert bad not in wh
    assert re.search(r"\bnombre\b", pos.select_sql) is None
    assert {"nombre_banner", "nombre_estandar", "cod_estado", "cod_programa", "periodo"} <= set(wh)


def test_postgrado_states_pseudonymize_the_rut():
    pos = S.by_name("ban_estados_academicos_pos")
    tr = S.RowTransformer(pos, SECRET)
    out = tr(tuple(["12.345.678-5"] + [None] * (len(pos.columns) - 1)))
    assert out[0] == persona_key("12.345.678-5", SECRET)
    assert tr(tuple([None] * len(pos.columns))) is None


def test_the_faculty_dictionary_has_no_person_and_no_key_column():
    fac = S.by_name("facultad_d")
    assert all(c.key is None for c in fac.columns)
    assert [c.wh for c in fac.columns][0] == "id"


# ---- benefits (16-11-2026): banner.banner_beneficios -------------------------------------------------------------------
def test_beneficios_source_is_registered_with_the_full_table_of_loads():
    src = S.by_name("banner_beneficios")
    assert src.view == "banner.banner_beneficios" and src.stg_table == "banner_beneficios"
    assert src.ts.kind == "full" and src.ts.table == "banner.banner_beneficios_full"
    assert "banner_beneficios" in S.all_fuentes()


def test_beneficios_skips_the_career_name_and_keys_the_rut():
    src = S.by_name("banner_beneficios")
    wh = [c.wh for c in src.columns]
    assert "carrera" not in wh
    assert re.search(r"\bcarrera\b", src.select_sql) is None
    assert {"periodo", "rut", "id_sede", "cod_carrera", "financiamiento", "cobertura", "codigo", "beneficio",
            "benef_sem1", "benef_sem2", "total"} == set(wh)
    keyed = [c for c in src.columns if c.key]
    assert len(keyed) == 1 and keyed[0].wh == "rut" and keyed[0].stg == "persona_key" and keyed[0].required
    S.assert_safe_columns(src)
    tr = S.RowTransformer(src, SECRET)
    raw = tuple("12.345.678-5" if c.wh == "rut" else None for c in src.columns)
    out = tr(raw)
    assert persona_key("12.345.678-5", SECRET) in out and "12.345.678-5" not in out
