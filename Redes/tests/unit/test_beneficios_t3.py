"""Student benefits as T3 features (16-11-2026): point-in-time rules ``previo`` / ``con_t`` and leakage perturbation tests."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features_beneficios_t3 as FT              # noqa: E402
from pipelines.snapshots import rules_beneficios_t3 as RT                  # noqa: E402

BEN_COLS = ["periodo", "persona_key", "cod_carrera", "codigo", "benef_sem1", "benef_sem2"]


def ben(*rows):
    """(anio, persona, carrera, codigo, sem1[, sem2])."""
    out = [dict(zip(BEN_COLS, [r[0], r[1], r[2], r[3], float(r[4]), float(r[5]) if len(r) > 5 else 0.0])) for r in rows]
    return pd.DataFrame(out, columns=BEN_COLS)


def cortes(*rows):
    """(episodio_id, k, persona, programa, programa_ingreso, periodo_admision)."""
    d = pd.DataFrame(rows, columns=["episodio_id", "k", "persona_key", "cod_programa", "cod_programa_ingreso", "periodo_admision"])
    d["periodo_corte"] = [RT.periodo_corte(p, k) for p, k in zip(d["periodo_admision"], d["k"])]
    return d


def fila(res, eid, k):
    return res.loc[(res["episodio_id"] == eid) & (res["k"] == k)].iloc[0]


# ---- rules ------------------------------------------------------------------------------------------------------------
def test_cut_period_and_years():
    assert RT.periodo_corte("201810", 2) == "201820"
    assert RT.periodo_corte("201820", 2) == "201910"
    assert RT.periodo_corte("201810", 0) is None
    assert RT.anio_admision("201820") == 2018 and RT.anio_admision("201825") == 2018
    assert RT.anio_inicio("201510") == RT.ANIO_MIN and RT.anio_inicio("201810") == 2018


@pytest.mark.parametrize("regla,corte,esperado", [
    ("previo", "201920", 2018), ("previo", "201910", 2018),
    ("con_t", "201920", 2019), ("con_t", "201910", 2018),        # only an end-of-year cut may read its own year
])
def test_latest_allowed_year(regla, corte, esperado):
    assert RT.anio_maximo(regla, corte) == esperado


def test_unknown_rule_is_rejected():
    with pytest.raises(ValueError):
        RT.anio_maximo("x", "201920")


# ---- features ---------------------------------------------------------------------------------------------------------
B = ben((2018, "p1", "A", "GG_94_AC", 100), (2019, "p1", "A", "GG_94_AC", 100), (2019, "p1", "A", "C_1_AC", 50),
        (2019, "p1", "A", "PC_01", 10), (2019, "p1", "A", "RE_G1_AC", 20))
C = cortes((1, 4, "p1", "A", "A", "201810"))          # cut 2019-20 (end of year): previo reads 2018, con_t reads 2018-2019


def test_previo_reads_only_years_before_the_cut_year():
    r = fila(FT.features_beneficios_t3(C, B, "previo"), 1, 4)
    assert r["anio_ben"] == 2018 and r["ben_sin_dato"] == 0
    assert r["tiene_gratuidad"] == 1 and r["tiene_credito"] == 0 and r["etapa_capstone"] == 0 and r["expiro_gratuidad"] == 0
    assert r["n_beneficios"] == 1 and r["anios_con_gratuidad"] == 1


def test_con_t_reads_the_cut_year_at_end_of_year_and_accumulates():
    r = fila(FT.features_beneficios_t3(C, B, "con_t"), 1, 4)
    assert r["anio_ben"] == 2019
    assert r["tiene_credito"] == 1 and r["etapa_capstone"] == 1 and r["expiro_gratuidad"] == 1
    assert r["n_beneficios"] == 4 and r["anios_con_gratuidad"] == 2 and r["capstone_alguna"] == 1 and r["expiro_alguna"] == 1
    assert r["perdida_sin_dato"] == 0 and r["perdio_gratuidad"] == 0 and r["perdio_cualquier_beneficio"] == 0


def test_mid_year_cut_behaves_like_previo_under_con_t():
    c = cortes((2, 3, "p1", "A", "A", "201810"))            # cut 2019-10 (mid-year)
    a, b = (fila(FT.features_beneficios_t3(c, B, r), 2, 3) for r in ("previo", "con_t"))
    assert a["anio_ben"] == b["anio_ben"] == 2018
    assert a["tiene_credito"] == b["tiene_credito"] == 0


def test_year_before_admission_is_unknown_not_zero():
    c = cortes((3, 2, "p1", "A", "A", "201810"))            # cut 2018-20; previo -> 2017 < admission year
    r = fila(FT.features_beneficios_t3(c, B, "previo"), 3, 2)
    assert r["ben_sin_dato"] == 1 and np.isnan(r["tiene_gratuidad"]) and np.isnan(r["n_beneficios"]) and r["banda_decil"] is None
    r2 = fila(FT.features_beneficios_t3(c, B, "con_t"), 3, 2)           # con_t reads 2018, the admission year
    assert r2["ben_sin_dato"] == 0 and r2["tiene_gratuidad"] == 1


def test_years_outside_the_loaded_range_are_unknown():
    c = cortes((4, 4, "p1", "A", "A", "202610"))             # cut 2027-20: allowed year beyond the loaded range
    assert fila(FT.features_beneficios_t3(c, B, "con_t"), 4, 4)["ben_sin_dato"] == 1
    c = cortes((5, 4, "p9", "A", "A", "201410"))             # window before the table starts
    assert fila(FT.features_beneficios_t3(c, B, "previo"), 5, 4)["ben_sin_dato"] == 1


def test_loss_between_the_two_latest_allowed_years():
    b = ben((2017, "p1", "A", "GG_94_AC", 100), (2017, "p1", "A", "C_1_AC", 10), (2018, "p1", "A", "C_1_AC", 10))
    c = cortes((6, 4, "p1", "A", "A", "201710"))             # cut 2018-20
    r = fila(FT.features_beneficios_t3(c, b, "con_t"), 6, 4)            # reads 2017 and 2018
    assert r["perdida_sin_dato"] == 0 and r["perdio_gratuidad"] == 1 and r["perdio_credito"] == 0 and r["obtuvo_gratuidad"] == 0
    r = fila(FT.features_beneficios_t3(c, b, "previo"), 6, 4)           # reads only 2017: no year before it inside the window
    assert r["perdida_sin_dato"] == 1 and np.isnan(r["perdio_gratuidad"])


def test_other_program_is_ignored_but_admission_program_counts():
    b = ben((2018, "p1", "Z", "GG_94_AC", 100), (2018, "p2", "A", "GG_94_AC", 100), (2018, "p2", "B", "C_1_AC", 100))
    c = cortes((7, 4, "p1", "A", "A", "201810"), (8, 4, "p2", "B", "A", "201810"))        # 8: moved from A to B (Plan Comun style)
    res = FT.features_beneficios_t3(c, b, "previo")
    assert fila(res, 7, 4)["tiene_gratuidad"] == 0 and fila(res, 7, 4)["n_beneficios"] == 0
    assert fila(res, 8, 4)["tiene_gratuidad"] == 1 and fila(res, 8, 4)["tiene_credito"] == 1 and fila(res, 8, 4)["n_beneficios"] == 2


def test_decil_band_is_reported_but_not_a_model_column():
    b = ben((2018, "p1", "A", "QI_07", 10), (2018, "p2", "A", "GG_94_AB", 10))
    c = cortes((9, 4, "p1", "A", "A", "201810"), (10, 4, "p2", "A", "A", "201810"))
    res = FT.features_beneficios_t3(c, b, "previo")
    assert fila(res, 9, 4)["banda_decil"] == "7" and fila(res, 10, 4)["banda_decil"] == "<=6"
    for bloque in ("fin", "expcap", "todo"):
        assert "banda_decil" not in FT.columnas_numericas(bloque)


def test_blocks_are_disjoint_and_complete():
    fin, ec, todo = (set(FT.columnas_numericas(b)) for b in ("fin", "expcap", "todo"))
    assert not ((fin - {"ben_sin_dato"}) & (ec - {"ben_sin_dato"}))
    assert todo == fin | ec


# ---- leakage: perturbing what the rule must not read leaves every feature unchanged ----------------------------------------
def _igual(a, b):
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


@pytest.mark.parametrize("regla,corte_anio", [("previo", 2019), ("con_t", 2020)])
def test_perturbing_years_after_the_allowed_one_changes_nothing(regla, corte_anio):
    c = cortes((1, 4, "p1", "A", "A", "201810"))
    base = FT.features_beneficios_t3(c, B, regla)
    extra = ben((corte_anio, "p1", "A", "GG_94_AB", 999), (corte_anio, "p1", "A", "PC_01", 999), (corte_anio + 1, "p1", "A", "RE_G2_AC", 5),
                (2026, "p1", "A", "C_70_AC", 7))
    quitado = B.loc[B["periodo"] < corte_anio]
    _igual(base, FT.features_beneficios_t3(c, pd.concat([B, extra], ignore_index=True), regla))
    _igual(FT.features_beneficios_t3(c, quitado, regla).drop(columns=[]), FT.features_beneficios_t3(c, B.loc[B["periodo"] < corte_anio], regla))


def test_previo_ignores_the_cut_year_even_at_end_of_year():
    c = cortes((1, 4, "p1", "A", "A", "201810"))
    sin_anio_t = B.loc[B["periodo"] < 2019]
    _igual(FT.features_beneficios_t3(c, B, "previo"), FT.features_beneficios_t3(c, sin_anio_t, "previo"))


def test_second_semester_amount_and_other_people_never_matter():
    c = cortes((1, 4, "p1", "A", "A", "201810"))
    b2 = B.copy()
    b2["benef_sem2"] = 12345.0
    otros = ben((2018, "p9", "A", "GG_94_AC", 1), (2019, "p9", "A", "PC_01", 1))
    for regla in RT.REGLAS:
        _igual(FT.features_beneficios_t3(c, B, regla), FT.features_beneficios_t3(c, b2, regla))
        _igual(FT.features_beneficios_t3(c, B, regla), FT.features_beneficios_t3(c, pd.concat([B, otros], ignore_index=True), regla))


def test_features_do_not_depend_on_the_order_or_the_other_cuts():
    c = cortes((1, 4, "p1", "A", "A", "201810"), (11, 2, "p1", "A", "A", "201810"), (12, 4, "p9", "A", "A", "201710"))
    todo = FT.features_beneficios_t3(c, B, "con_t")
    solo = FT.features_beneficios_t3(c.iloc[[0]], B, "con_t")
    _igual(todo.iloc[[0]].reset_index(drop=True), solo)


def test_year_count_is_unknown_when_the_window_starts_before_the_table():
    b = ben((2017, "p1", "A", "GG_94_AC", 1), (2018, "p1", "A", "GG_94_AC", 1))
    c = cortes((20, 4, "p1", "A", "A", "201610"))                # cut 2017-20, admitted 2016: 2016 is not in the table
    r = fila(FT.features_beneficios_t3(c, b, "con_t"), 20, 4)
    assert r["ben_sin_dato"] == 0 and r["tiene_gratuidad"] == 1 and np.isnan(r["anios_con_gratuidad"])
