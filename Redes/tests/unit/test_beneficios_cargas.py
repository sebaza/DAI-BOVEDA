"""Point-in-time benefits from the load history: rule, features, leakage (perturbation) tests, source spec and DDL."""
import datetime as dt
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipelines.extract import sources as S
from pipelines.migrate import validate_sql
from pipelines.snapshots import features_beneficios as FB
from pipelines.snapshots import features_beneficios_cargas as FC
from pipelines.snapshots import rules_beneficios_cargas as RC

SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "core"


def ms(y, m, d, h=12):
    return int(dt.datetime(y, m, d, h, tzinfo=dt.timezone.utc).timestamp() * 1000)


# loads of the benefit year 2024: Apr 4, Jun 20, Jul 1 (the last one on or before the Jul 31 cut), Aug 8, Nov 7, Dec 9
T_ABR, T_JUN, T_JUL, T_AGO, T_NOV, T_DIC = (ms(2024, 4, 4), ms(2024, 6, 20), ms(2024, 7, 1), ms(2024, 8, 8), ms(2024, 11, 7),
                                            ms(2024, 12, 9))
CAL = pd.DataFrame({"timestamp_carga": [T_ABR, T_JUN, T_JUL, T_AGO, T_NOV, T_DIC] + [ms(2024, 1, 8), ms(2024, 3, 4)],
                    "periodo": [2024] * 6 + [2023, 2023], "filas": 1})
# 2023 was loaded all at once on Jan 8 2024, so it has no history


def hist(persona, codigo, first, last, sem1=100.0, carrera="8213", anio=2024, **extra):
    return {"periodo": anio, "persona_key": persona, "cod_carrera": carrera, "codigo": codigo, "cobertura": "AC",
            "first_ts": first, "last_ts": last, "n_loads": 2, "presente_ultima_carga": last == T_DIC,
            "sem1_primera": sem1, "sem2_primera": 0.0, "sem1_ultima": sem1, "sem2_ultima": 0.0, **extra}


def corte(ep, persona, periodo_corte="202410", k=1, programa="8213"):
    return {"episodio_id": ep, "k": k, "persona_key": persona, "cod_programa": programa, "periodo_corte": periodo_corte}


# ---------------------------------------------------------------------------------------------------- rule
def test_cut_dates_follow_the_calendar_of_the_project():
    assert RC.fecha_corte("202410") == dt.date(2024, 7, 31)
    assert RC.fecha_corte("202520") == dt.date(2025, 11, 30)
    assert RC.ts_fin_del_dia(dt.date(2024, 7, 31)) == ms(2024, 8, 1, 0) - 1


def test_last_load_on_or_before_the_cut():
    cal = np.array([T_ABR, T_JUL, T_AGO])
    assert RC.ultima_carga_hasta(cal, RC.ts_fin_del_dia(dt.date(2024, 7, 31))) == T_JUL
    assert RC.ultima_carga_hasta(cal, RC.ts_fin_del_dia(dt.date(2024, 4, 4))) == T_ABR      # same day counts
    assert RC.ultima_carga_hasta(cal, RC.ts_fin_del_dia(dt.date(2024, 4, 3))) is None


def test_years_loaded_all_at_once_have_no_history():
    h = RC.anios_con_historial({2023: ms(2024, 1, 8), 2024: ms(2024, 4, 4), 2025: ms(2025, 3, 25)})
    assert h == {2023: False, 2024: True, 2025: True}


@pytest.mark.parametrize("first,last,esperado", [
    (T_ABR, T_DIC, True),       # in the load of the cut and kept
    (T_JUL, T_DIC, True),       # first appears exactly at the load of the cut
    (T_AGO, T_DIC, False),      # appears after the cut
    (T_ABR, T_JUN, False),      # retired before the load of the cut
    (T_ABR, T_JUL, True),       # retired right after the cut load (not visible before)
])
def test_visibility_rule(first, last, esperado):
    assert RC.visible(first, last, T_JUL) is esperado
    assert RC.visible(first, last, None) is False


# ---------------------------------------------------------------------------------------------------- features
def feats(cortes, cargas):
    return FC.features_beneficios_cargas(pd.DataFrame(cortes), pd.DataFrame(cargas), CAL)


def test_columns_match_the_final_view_features():
    f = feats([corte(1, "p1")], [hist("p1", "GG_94AB", T_ABR, T_DIC)])
    assert list(f.columns) == ["episodio_id", "k", *FB.COLS_BENEFICIOS]


def test_visible_rows_become_family_flags_and_late_or_retired_rows_do_not():
    cargas = [hist("p1", "GG_94AB", T_ABR, T_DIC, 50.0), hist("p1", "C_1_AC", T_AGO, T_DIC, 70.0),   # credit arrives after the cut
              hist("p2", "GG_94AB", T_ABR, T_JUN), hist("p2", "BG_01", T_ABR, T_DIC, 30.0)]          # gratuity retired before the cut
    f = feats([corte(1, "p1"), corte(2, "p2")], cargas).set_index("episodio_id")
    assert f.loc[1, "tiene_gratuidad"] == 1 and f.loc[1, "tiene_credito"] == 0 and f.loc[1, "n_beneficios"] == 1
    assert f.loc[1, "monto_sem1"] == 50.0 and f.loc[1, "banda_decil"] == "<=6"
    assert f.loc[2, "tiene_gratuidad"] == 0 and f.loc[2, "tiene_beca_estatal"] == 1 and f.loc[2, "banda_decil"] == "desconocida"
    assert (f["ben_sin_dato"] == 0).all()


def test_a_person_without_rows_in_a_year_with_history_has_zeros_not_unknown():
    f = feats([corte(1, "p9")], [hist("p1", "GG_94AB", T_ABR, T_DIC)])
    assert f.loc[0, "ben_sin_dato"] == 0 and f.loc[0, "n_beneficios"] == 0 and f.loc[0, "tiene_gratuidad"] == 0


def test_years_without_history_or_without_a_load_by_the_cut_are_unknown():
    f = feats([corte(1, "p1", "202310"), corte(2, "p1", "202610"), corte(3, "p1", "202410")],
              [hist("p1", "GG_94AB", T_ABR, T_DIC, anio=2023)] + [hist("p1", "GG_94AB", T_ABR, T_DIC)]).set_index("episodio_id")
    assert f.loc[1, "ben_sin_dato"] == 1 and np.isnan(f.loc[1, "tiene_gratuidad"]) and f.loc[1, "banda_decil"] is None
    assert f.loc[2, "ben_sin_dato"] == 1                                        # 2026 is not in the calendar
    assert f.loc[3, "ben_sin_dato"] == 0
    assert (f["perdida_sin_dato"] == 1).all() and f[FB.COLS_PERDIDA].isna().all().all()


def test_only_the_program_of_the_episode_counts():
    f = feats([corte(1, "p1")], [hist("p1", "GG_94AB", T_ABR, T_DIC, carrera="9999")])
    assert f.loc[0, "n_beneficios"] == 0


def test_two_cuts_of_one_person_use_their_own_cut_date():
    cargas = [hist("p1", "C_1_AC", T_AGO, T_DIC)]                                # credit appears on Aug 8
    f = feats([corte(1, "p1", "202410", k=1), corte(2, "p1", "202420", k=2)], cargas).set_index("episodio_id")
    assert f.loc[1, "tiene_credito"] == 0 and f.loc[2, "tiene_credito"] == 1      # July cut vs November cut


# ---------------------------------------------------------------------------------------------------- leakage
def baseline_hist():
    return [hist("p1", "GG_94AB", T_ABR, T_DIC, 50.0), hist("p1", "FSCU", T_JUN, T_NOV, 20.0),
            hist("p2", "BG_01", T_JUL, T_DIC, 30.0), hist("p3", "GG_94AB", T_ABR, T_AGO, 10.0)]


CORTES = [corte(1, "p1"), corte(2, "p2"), corte(3, "p3"), corte(4, "p4")]


def test_perturbing_what_happens_after_the_cut_does_not_change_the_features():
    base = feats(CORTES, baseline_hist())
    h = baseline_hist()
    # (a) the later life of rows visible at the cut: when they are retired, how many loads contain them, amounts at the last load
    for row in h:
        row.update(last_ts=T_DIC if row["last_ts"] > T_JUL else row["last_ts"])
    #     (the first-semester amount of the last load is deliberately used: it is the corrected amount, P97 / D111, tested apart)
    h[0].update(last_ts=T_NOV, n_loads=99, presente_ultima_carga=False, sem2_ultima=9e6, sem2_primera=9e6)
    h[2].update(n_loads=1, presente_ultima_carga=False)
    # (b) rows that only appear after the cut: added, and their codes / amounts changed
    h += [hist("p4", "GG_94AB", T_AGO, T_DIC, 80.0), hist("p2", "C_1_AC", T_NOV, T_DIC, 60.0), hist("p1", "PI_03", T_DIC, T_DIC)]
    # (c) a row that was retired AFTER being visible keeps counting; retiring it later or earlier than the cut load is the only
    #     thing that matters, so changing the end of a row that ends after the cut is invisible
    h[3].update(last_ts=T_DIC)
    after = feats(CORTES, h)
    cols = [c for c in base.columns if c != "episodio_id"]
    pd.testing.assert_frame_equal(base[cols], after[cols])
    # the people of the changed rows only differ where the row was retired before the cut (p3 stays visible at the cut)
    assert base.set_index("episodio_id").loc[3, "n_beneficios"] == 1


def test_loads_after_the_cut_in_the_calendar_do_not_change_the_features():
    base = feats(CORTES, baseline_hist())
    cal2 = pd.concat([CAL, pd.DataFrame({"timestamp_carga": [ms(2024, 9, 30), ms(2025, 1, 5)], "periodo": [2024, 2024], "filas": 1})])
    after = FC.features_beneficios_cargas(pd.DataFrame(CORTES), pd.DataFrame(baseline_hist()), cal2)
    pd.testing.assert_frame_equal(base, after)


def test_a_row_of_the_wrong_side_of_the_cut_changes_the_features():
    """Control of the perturbation test: perturbing what IS before the cut does change them."""
    base = feats(CORTES, baseline_hist())
    h = baseline_hist()
    h[0].update(first_ts=T_AGO)                                                  # p1's gratuity now appears after the cut
    assert feats(CORTES, h).set_index("episodio_id").loc[1, "tiene_gratuidad"] == 0
    assert base.set_index("episodio_id").loc[1, "tiene_gratuidad"] == 1


def test_amounts_use_the_corrected_amount_of_the_last_load():
    """P97 / D111: upload failures are corrected later and the current amounts are the right ones."""
    h = [hist("p1", "GG_94AB", T_ABR, T_DIC, 100.0, sem1_ultima=80.5)]
    assert feats([corte(1, "p1")], h).loc[0, "monto_sem1"] == 80.5


def test_an_amount_that_varies_90_percent_or_more_is_not_used():
    h = [hist("p1", "GG_94AB", T_ABR, T_DIC, 100.0, sem1_ultima=0.0), hist("p1", "C_1_AC", T_ABR, T_DIC, 40.0)]
    f = feats([corte(1, "p1")], h)
    assert np.isnan(f.loc[0, "monto_sem1"])
    assert f.loc[0, "n_beneficios"] == 2 and f.loc[0, "tiene_gratuidad"] == 1   # presence is unaffected


def test_monto_rule():
    assert RC.monto_corregido(100.0, 80.5) == 80.5
    assert RC.monto_corregido(100.0, 10.1) == 10.1                                # 89.9 % variation: kept
    assert np.isnan(RC.monto_corregido(100.0, 10.0))                              # exactly 90 %: dropped
    assert np.isnan(RC.monto_corregido(0.0, 50.0)) and np.isnan(RC.monto_corregido(50.0, 0.0))
    assert RC.monto_corregido(0.0, 0.0) == 0.0
    assert RC.monto_corregido(float("nan"), 30.0) == 30.0 and RC.monto_corregido(30.0, float("nan")) == 30.0
    assert np.isnan(RC.monto_corregido(float("nan"), float("nan")))


def test_no_second_semester_column_reaches_the_features():
    f = feats([corte(1, "p1")], [hist("p1", "GG_94AB", T_ABR, T_DIC)])
    assert not [c for c in f.columns if "sem2" in c or c == "total"]


# ---------------------------------------------------------------------------------------------------- source and migration
def test_history_sources_are_registered_and_key_the_rut():
    src = S.by_name("banner_beneficios_cargas")
    assert src.stg_table == "banner_beneficios_cargas" and src.ts.kind == "full"
    assert src.select_sql == src.sql and "GROUP BY" in src.sql and "FROM banner.banner_beneficios_full" in src.sql
    keyed = [c for c in src.columns if c.key]
    assert len(keyed) == 1 and keyed[0].wh == "rut" and keyed[0].stg == "persona_key"
    S.assert_safe_columns(src)
    assert re.search(r"\bcarrera\b", src.select_sql) is None and "persona_key" not in src.select_sql
    # every output column of the SELECT is declared (and nothing else)
    declared = {c.wh for c in src.columns}
    for col in declared:
        assert re.search(rf"\b{col}\b", src.select_sql), col
    cal = S.by_name("banner_beneficios_cargas_cal")
    assert all(c.key is None for c in cal.columns) and "rut" not in cal.select_sql
    assert {"banner_beneficios_cargas", "banner_beneficios_cargas_cal"} <= set(S.all_fuentes())


def test_the_history_select_is_read_only_and_has_no_correlated_subquery():
    sql = S.by_name("banner_beneficios_cargas").select_sql
    assert sql.lstrip().upper().startswith("SELECT")
    assert not re.search(r"\b(insert|update|delete|drop|alter|create|truncate)\b", sql, re.I)
    assert sql.count("SELECT") == 2                      # the outer one and the uncorrelated max(timestamp_carga)


def test_the_history_row_transformer_keys_the_rut_and_never_keeps_it():
    from pipelines.common.pseudo import persona_key

    src = S.by_name("banner_beneficios_cargas")
    tr = S.RowTransformer(src, "k" * 32)
    raw = tuple("12.345.678-5" if c.wh == "rut" else None for c in src.columns)
    out = tr(raw)
    assert persona_key("12.345.678-5", "k" * 32) in out and "12.345.678-5" not in out


def test_migration_026_passes_the_guard_and_has_no_rut():
    text = (SQL_DIR / "026_beneficios_cargas.sql").read_text(encoding="utf-8")
    assert validate_sql(text, "026_beneficios_cargas.sql")
    low = text.lower()
    assert "persona_key" in low and not re.search(r"^\s+rut\b", low, re.M) and "neural_stg.banner_beneficios_cargas" in low
    cols = set(re.findall(r"^\s+(\w+)\s+(?:bigint|integer|text|boolean|numeric)\b", text, re.M))
    assert {c.stg for c in S.by_name("banner_beneficios_cargas").columns} <= cols
    assert {c.stg for c in S.by_name("banner_beneficios_cargas_cal").columns} <= cols
