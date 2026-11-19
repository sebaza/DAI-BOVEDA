"""Stage B (13-11-2026): the admission-score features of T1-T6 are the scale-corrected ``mm_*`` columns plus the test
(``prueba_admision``); the rank-based ``pct_*`` never are (``ponderado`` mixes 557 / 5570 / 55700 scales, D74)."""
import pytest

pytest.importorskip("pandas")

from models import data as D                                  # noqa: E402
from models import t2_data as T2                              # noqa: E402
from models import t3_data as T3                              # noqa: E402
from models import t45_data as T45                            # noqa: E402
from models import t6_data as T6                              # noqa: E402
from pipelines.snapshots import features as F                 # noqa: E402
from pipelines.snapshots import features_t2 as F2             # noqa: E402
from pipelines.snapshots import features_t3 as F3             # noqa: E402
from pipelines.snapshots import features_t6 as F6             # noqa: E402
from pipelines.snapshots import t1 as S1                      # noqa: E402

MM = list(F.MM_COLS)
PCT = list(F.SCORE_COLS)


def _conjuntos():
    yield "T1", D.GRUPOS["pre_entry"]
    yield "T1+acad", D.GRUPOS["pre_entry+academico"]
    for n, g in T2.CONJUNTOS.items():
        yield f"T2 {n}", g
    for n, g in T3.GRUPOS.items():
        yield f"T3 {n}", g
    for n, g in T45.GRUPOS.items():
        yield f"T45 {n}", g
    for n, g in T6.GRUPOS.items():
        yield f"T6 {n}", g


@pytest.mark.parametrize("nombre,grupo", list(_conjuntos()))
def test_every_feature_set_uses_mm_and_the_test_not_the_percentiles(nombre, grupo):
    num, cat = grupo
    assert set(MM) <= set(num), nombre
    assert F.PRUEBA_COL in cat, nombre
    assert not set(PCT) & set(num + cat), nombre


def test_the_stage_b_columns_exist_in_every_snapshot():
    for cols in (S1.SNAPSHOT_COLS, F2.SNAPSHOT_COLS_T2, F3.SNAPSHOT_COLS_T3,
                 F6.SNAPSHOT_COLS_T6):
        assert set(MM) | {F.PRUEBA_COL} <= set(cols)


def test_the_test_column_is_read_as_text_by_every_loader():
    for textos in (T2.TEXT_COLS, T3.TEXT_COLS, T45.TEXT_COLS, T6.TEXT_COLS):
        assert F.PRUEBA_COL in textos


def test_the_percentile_columns_stay_in_the_snapshots_for_audit():
    assert set(PCT) <= set(F2.SNAPSHOT_COLS_T2) and set(PCT) <= set(F3.SNAPSHOT_COLS_T3)


def test_faculty_labels_are_names_never_bare_codes():
    from evaluation import facultades as FA
    import pandas as pd
    assert FA.nombre_facultad("4", "Facultad de  Ciencias ") == "Facultad de Ciencias"
    assert FA.nombre_facultad("99", None) == "Facultad sin nombre (código 99)"
    assert FA.nombre_facultad(None, None) == "Sin facultad"
    prog = pd.DataFrame({"facultad_nombre": ["Facultad de Ciencias"]}, index=["P1"])
    s = FA.facultad_de(pd.Series(["P1", "ZZ"]), prog)
    assert s.tolist() == ["Facultad de Ciencias", None]


def test_the_grade_band_is_read_as_text_and_is_never_a_feature():
    assert "banda_nota" in T2.TEXT_COLS
    with pytest.raises(ValueError):
        T2.verificar_sin_fuga(["banda_nota"], [])
    for num, cat in T2.CONJUNTOS.values():
        assert "banda_nota" not in set(num + cat)
