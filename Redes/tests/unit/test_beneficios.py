"""Student benefits as T1 features (16-11-2026): code families, point-in-time rules and the k = 4 loss variables."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features_beneficios as FB          # noqa: E402
from pipelines.snapshots import rules_beneficios as RB              # noqa: E402

BEN_COLS = ["periodo", "persona_key", "cod_carrera", "codigo", "financiamiento", "benef_sem1", "benef_sem2"]


def ben(*rows):
    """(anio, persona, carrera, codigo, sem1[, sem2])."""
    out = []
    for r in rows:
        anio, persona, carrera, codigo, s1 = r[:5]
        s2 = r[5] if len(r) > 5 else 0.0
        fin = "Ayuda Gubernamental" if codigo.startswith(("GG", "C_1", "BG")) else (
            "Fondos externos" if codigo.startswith(("C_70", "BE")) else "Fondos centrales")
        out.append(dict(zip(BEN_COLS, [anio, persona, carrera, codigo, fin, float(s1), float(s2)])))
    return pd.DataFrame(out, columns=BEN_COLS)


def cortes(*rows):
    """(episodio_id, k, persona, programa, periodo_corte)."""
    return pd.DataFrame(rows, columns=["episodio_id", "k", "persona_key", "cod_programa", "periodo_corte"])


def fila(res, eid, k):
    return res.loc[(res["episodio_id"] == eid) & (res["k"] == k)].iloc[0]


# ---- code families ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("codigo,familia", [
    ("GG_94_AB", "gratuidad"), ("GG_94_AC", "gratuidad"), ("GU_00_AC", "gratuidad"), ("GU_00_AB", "gratuidad"),
    ("C_1_AC", "credito"), ("C_70_AC", "credito"), ("BG_2_AC", "beca_estatal"), ("BG_79_AB", "beca_estatal"),
    ("BI_69_AC", "beca_ucn"), ("BI_7_AB", "beca_ucn"), ("BI_9_AC", "beca_ucn"),
])
def test_each_code_belongs_to_one_family(codigo, familia):
    assert RB.clasificar(codigo)["familia"] == familia


def test_codes_outside_the_four_families_have_no_family():
    for codigo in ("BE_81_AC", "PI_0E_AC", "PC_85_AC", "RE_G1_AC", "QI_89_AC", "PI_03_AC"):
        assert RB.clasificar(codigo)["familia"] is None


@pytest.mark.parametrize("codigo,valor", [("PI_01_AC", 70), ("PI_02_AC", 75), ("PI_03_AC", 85), ("PI_04_AC", 85),
                                          ("PI_06_AC", 85)])
def test_positioning_benefit_percentages(codigo, valor):
    assert RB.clasificar(codigo)["merito"] == valor


def test_e1_is_a_category_not_a_percentage_and_debt_adjustments_are_not_merit():
    assert RB.clasificar("PE_01_AC")["merito_e1"] is True and RB.clasificar("PE_01_AC")["merito"] == 0
    assert RB.clasificar("PI_0E_AC")["merito"] == 0 and RB.clasificar("PI_07_AC")["merito"] == 0


@pytest.mark.parametrize("codigo,banda", [("QI_07_AC", "7"), ("DC_07_AC", "7"), ("QI_89_AC", "8-9"), ("DC_89_AC", "8-9")])
def test_decile_discount_gives_the_band(codigo, banda):
    assert RB.clasificar(codigo)["decil"] == banda


@pytest.mark.parametrize("codigo,n", [("RE_G1_AC", 1), ("RB_G1_AC", 1), ("RE_G1_AB", 1), ("RB_G2_AC", 2)])
def test_gratuity_expiration_years(codigo, n):
    assert RB.clasificar(codigo)["expiro"] == n


def test_capstone_adjustment_and_unknown_codes():
    assert RB.clasificar("PC_85_AC")["capstone"] is True and RB.clasificar("PC_70_AC")["capstone"] is True
    z = RB.clasificar("ZZ_99_AC")
    assert z["familia"] is None and z["merito"] == 0 and z["decil"] is None and z["expiro"] == 0 and not z["capstone"]


# ---- point in time ---------------------------------------------------------------------------------------------------------
def test_features_come_only_from_the_cut_year_and_the_episode_program():
    c = cortes((1, 1, "p", "C1", "202010"))
    base = ben((2020, "p", "C1", "GG_94_AC", 100), (2020, "p", "C1", "C_1_AC", 50))
    r = fila(FB.features_beneficios(c, base), 1, 1)
    assert r["tiene_gratuidad"] == 1 and r["tiene_credito"] == 1 and r["n_beneficios"] == 2 and r["monto_sem1"] == 150
    # a benefit of another program, of another person or of another year does not enter
    ruido = pd.concat([base, ben((2020, "p", "C2", "BG_2_AC", 80), (2020, "q", "C1", "BG_2_AC", 80),
                                 (2021, "p", "C1", "BG_2_AC", 80), (2019, "p", "C1", "BG_2_AC", 80))])
    r2 = fila(FB.features_beneficios(c, ruido), 1, 1)
    assert r2["tiene_beca_estatal"] == 0 and r2["n_beneficios"] == 2 and r2["monto_sem1"] == 150


def test_second_semester_amounts_never_enter_any_feature():
    c = cortes((1, 2, "p", "C1", "202020"))
    a = FB.features_beneficios(c, ben((2020, "p", "C1", "GG_94_AC", 100, 0)))
    b = FB.features_beneficios(c, ben((2020, "p", "C1", "GG_94_AC", 100, 99999)))
    pd.testing.assert_frame_equal(a, b)
    assert not any("sem2" in col or col == "monto_total" for col in a.columns)


def test_perturbing_later_years_does_not_change_the_features_of_a_cut():
    c = cortes((1, 1, "p", "C1", "202110"), (2, 4, "p", "C1", "202120"))
    base = ben((2020, "p", "C1", "GG_94_AC", 10), (2021, "p", "C1", "C_1_AC", 20))
    despues = pd.concat([base, ben((2022, "p", "C1", "GG_94_AC", 10), (2023, "p", "C1", "BG_2_AC", 5))])
    pd.testing.assert_frame_equal(FB.features_beneficios(c, base), FB.features_beneficios(c, despues))


def test_a_covered_year_without_rows_means_no_benefit_not_unknown():
    r = fila(FB.features_beneficios(cortes((1, 1, "p", "C1", "202010")), ben((2020, "q", "C1", "GG_94_AC", 1))), 1, 1)
    assert r["tiene_gratuidad"] == 0 and r["n_beneficios"] == 0 and r["monto_sem1"] == 0 and r["merito_ingreso"] == 0
    assert r["banda_decil"] == "desconocida" and r["ben_sin_dato"] == 0


def test_years_without_data_are_unknown_with_an_indicator():
    c = cortes((1, 1, "p", "C1", "201510"), (2, 2, "p", "C1", "201620"), (3, 1, "p", "C1", "201710"))
    res = FB.features_beneficios(c, ben((2017, "p", "C1", "GG_94_AC", 1)))
    for eid in (1, 2):
        r = fila(res, eid, 1 if eid == 1 else 2)
        assert r["ben_sin_dato"] == 1 and np.isnan(r["tiene_gratuidad"]) and np.isnan(r["n_beneficios"])
        assert pd.isna(r["banda_decil"])
    assert fila(res, 3, 1)["ben_sin_dato"] == 0 and fila(res, 3, 1)["tiene_gratuidad"] == 1


def test_a_year_after_the_last_loaded_year_is_unknown_too():
    res = FB.features_beneficios(cortes((1, 1, "p", "C1", "202810")), ben((2020, "p", "C1", "GG_94_AC", 1)))
    assert fila(res, 1, 1)["ben_sin_dato"] == 1


def test_decile_band_prefers_gratuity_and_then_the_decile_discount():
    c = cortes((1, 1, "a", "C1", "202010"), (2, 1, "b", "C1", "202010"), (3, 1, "c", "C1", "202010"),
               (4, 1, "d", "C1", "202010"))
    b = ben((2020, "a", "C1", "GG_94_AC", 1), (2020, "a", "C1", "QI_89_AC", 1), (2020, "b", "C1", "QI_07_AC", 1),
            (2020, "c", "C1", "QI_89_AC", 1), (2020, "d", "C1", "C_1_AC", 1))
    res = FB.features_beneficios(c, b)
    assert [fila(res, i, 1)["banda_decil"] for i in (1, 2, 3, 4)] == ["<=6", "7", "8-9", "desconocida"]


def test_merit_takes_the_highest_percentage_and_flags_e1_apart():
    c = cortes((1, 1, "a", "C1", "202010"), (2, 1, "b", "C1", "202010"))
    b = ben((2020, "a", "C1", "PI_01_AC", 1), (2020, "a", "C1", "PI_03_AC", 1), (2020, "b", "C1", "PE_01_AC", 1))
    res = FB.features_beneficios(c, b)
    assert fila(res, 1, 1)["merito_ingreso"] == 85 and fila(res, 1, 1)["merito_e1"] == 0
    assert fila(res, 2, 1)["merito_ingreso"] == 0 and fila(res, 2, 1)["merito_e1"] == 1


def test_expiration_and_capstone_flags():
    c = cortes((1, 1, "a", "C1", "202010"), (2, 1, "b", "C1", "202010"))
    b = ben((2020, "a", "C1", "RB_G2_AC", 1), (2020, "a", "C1", "RE_G1_AC", 1), (2020, "b", "C1", "PC_85_AC", 1))
    res = FB.features_beneficios(c, b)
    assert fila(res, 1, 1)["expiro_gratuidad"] == 2 and fila(res, 1, 1)["etapa_capstone"] == 0
    assert fila(res, 2, 1)["expiro_gratuidad"] == 0 and fila(res, 2, 1)["etapa_capstone"] == 1


# ---- loss variables (k = 4 only) -------------------------------------------------------------------------------------------
def test_loss_variables_exist_only_at_the_k_four_cut_and_stay_null_before():
    c = cortes((1, 1, "p", "C1", "202110"), (1, 2, "p", "C1", "202120"), (1, 4, "p", "C1", "202220"))
    b = ben((2021, "p", "C1", "GG_94_AC", 1), (2022, "p", "C1", "C_1_AC", 1))
    res = FB.features_beneficios(c, b)
    for k in (1, 2):
        r = fila(res, 1, k)
        assert all(np.isnan(r[v]) for v in FB.COLS_PERDIDA) and r["perdida_sin_dato"] == 1
    r = fila(res, 1, 4)
    assert r["perdio_gratuidad"] == 1 and r["perdio_credito"] == 0 and r["perdio_cualquier_beneficio"] == 0
    assert r["obtuvo_gratuidad"] == 0 and r["perdida_sin_dato"] == 0


def test_loss_compares_the_year_before_the_cut_year_and_the_cut_year():
    c = cortes((1, 4, "keeps", "C1", "202220"), (2, 4, "gets", "C1", "202220"), (3, 4, "none", "C1", "202220"),
               (4, 4, "all_lost", "C1", "202220"))
    b = ben((2021, "keeps", "C1", "GG_94_AC", 1), (2022, "keeps", "C1", "GG_94_AC", 1),
            (2022, "gets", "C1", "GG_94_AC", 1), (2021, "all_lost", "C1", "C_1_AC", 1))
    res = FB.features_beneficios(c, b)
    keeps, gets, none, lost = (fila(res, i, 4) for i in (1, 2, 3, 4))
    assert (keeps["perdio_gratuidad"], keeps["obtuvo_gratuidad"], keeps["tiene_gratuidad"]) == (0, 0, 1)
    assert (gets["perdio_gratuidad"], gets["obtuvo_gratuidad"]) == (0, 1)
    assert (none["perdio_gratuidad"], none["perdio_cualquier_beneficio"], none["obtuvo_gratuidad"]) == (0, 0, 0)
    assert (lost["perdio_credito"], lost["perdio_cualquier_beneficio"], lost["perdio_gratuidad"]) == (1, 1, 0)


def test_the_loss_of_the_next_year_is_never_read():
    """The year after the cut year (the outcome year) must not change a single column of the k = 4 row."""
    c = cortes((1, 4, "p", "C1", "202220"))
    base = ben((2021, "p", "C1", "GG_94_AC", 1), (2022, "p", "C1", "GG_94_AC", 1))
    con_2023 = pd.concat([base, ben((2023, "p", "C1", "C_1_AC", 9))])
    pd.testing.assert_frame_equal(FB.features_beneficios(c, base), FB.features_beneficios(c, con_2023))


def test_loss_is_unknown_when_the_previous_year_has_no_data():
    res = FB.features_beneficios(cortes((1, 4, "p", "C1", "201720")), ben((2017, "p", "C1", "GG_94_AC", 1)))
    r = fila(res, 1, 4)
    assert r["ben_sin_dato"] == 0 and r["perdida_sin_dato"] == 1 and np.isnan(r["perdio_gratuidad"])
    assert r["tiene_gratuidad"] == 1


def test_loss_uses_the_episode_program_in_both_years():
    c = cortes((1, 4, "p", "C1", "202220"))
    b = ben((2021, "p", "C2", "GG_94_AC", 1), (2022, "p", "C1", "BG_2_AC", 1))
    r = fila(FB.features_beneficios(c, b), 1, 4)
    assert r["perdio_gratuidad"] == 0 and r["perdio_cualquier_beneficio"] == 0


def test_the_output_has_one_row_per_cut_and_the_declared_columns():
    c = cortes((1, 1, "p", "C1", "202010"), (1, 4, "p", "C1", "202120"))
    res = FB.features_beneficios(c, ben((2020, "p", "C1", "GG_94_AC", 1)))
    assert len(res) == 2 and list(res.columns) == ["episodio_id", "k", *FB.COLS_BENEFICIOS]
    assert set(FB.COLS_PERDIDA) <= set(FB.COLS_BENEFICIOS)


# ---- wiring into the snapshot ---------------------------------------------------------------------------------------------
def _escenario():
    from tests.unit import test_snapshot_features as T

    e = T.episodios(T.ep(1, "p", "C1", "201710"))
    periodos = ["201710", "201720", "201810", "201820", "201910", "201920", "202010", "202020"]
    s = T.estados(*[("p", 1, per, "M") for per in periodos])
    a = T.intentos((1, "201710", 5.0, "A1"), (1, "201810", 3.0, "A2"))
    return T, e, s, a


def test_the_snapshot_without_benefits_is_unchanged_and_with_them_adds_columns_without_touching_the_official_rows():
    T, e, s, a = _escenario()
    from pipelines.snapshots import features as F

    sin, _, _ = F.construir_snapshot(e, s, a, T.NO_VIA, T.NO_EGRESO, T.LATEST, (1, 2, 4))
    assert not set(FB.COLS_BENEFICIOS) & set(sin.columns)
    b = ben((2017, "p", "C1", "GG_94_AC", 10), (2018, "p", "C1", "C_1_AC", 20))
    con, _, _ = F.construir_snapshot(e, s, a, T.NO_VIA, T.NO_EGRESO, T.LATEST, (1, 2, 4), beneficios=b)
    assert set(FB.COLS_BENEFICIOS) <= set(con.columns)
    pd.testing.assert_frame_equal(sin.reset_index(drop=True), con[sin.columns].reset_index(drop=True))
    r1, r4 = con.loc[con["k"] == 1].iloc[0], con.loc[con["k"] == 4].iloc[0]
    assert r1["tiene_gratuidad"] == 1 and np.isnan(r1["perdio_gratuidad"])
    assert r4["perdio_gratuidad"] == 1 and r4["tiene_credito"] == 1


def test_the_official_ks_stay_one_and_two_and_the_extension_is_four():
    from pipelines.snapshots import rules as R

    assert R.KS == (1, 2) and R.KS_EXTENSION == (4,) and R.KS_TODOS == (1, 2, 4)
