"""T1 snapshot construction on tiny synthetic frames: eligibility, label, censoring and point-in-time features."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features as F          # noqa: E402
from pipelines.snapshots import rules as R              # noqa: E402

LATEST = "202620"


def episodios(*rows):
    cols = ["episodio_id", "persona_key", "cod_programa", "periodo_admision", "cod_admision", "id_nivel",
            "sede", "tipo_qualitas", "sexo"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows], columns=cols)


def ep(eid, persona="p", prog="C1", adm="201910", cod="LS", nivel=1):
    return (eid, persona, prog, adm, cod, nivel, 1, "1. Ingreso Regular o Centralizada", "F")


def estados(*rows):
    """(persona, episodio_id|None, periodo, cod_estado[, programa[, catalogo[, correccion]]])."""
    out = []
    for i, r in enumerate(rows):
        persona, eid, periodo, cod = r[:4]
        out.append({"persona_key": persona, "episodio_id": eid, "periodo": periodo, "cod_estado": cod,
                    "cod_programa": r[4] if len(r) > 4 else "C1", "catalogo": r[5] if len(r) > 5 else "2019",
                    "es_correccion_sistema": bool(r[6]) if len(r) > 6 else False, "orden_canonico": i + 1})
    df = pd.DataFrame(out)
    df["episodio_id"] = df["episodio_id"].astype("Int64")
    return df


def intentos(*rows):
    """(episodio_id, periodo, nota|'DPA'|None, aprobado, creditos, codigo, resultado_tipo)."""
    out = []
    for i, (eid, periodo, nota, codigo, *rest) in enumerate(rows):
        tipo = rest[0] if rest else ("convalidacion" if nota == "DPA" else "evaluado")
        evaluado = tipo == "evaluado"
        out.append({
            "intento_id": i + 1, "episodio_id": eid, "periodo": periodo, "codigo_asignatura": codigo,
            "es_intento_evaluado": evaluado, "nota_numerica": float(nota) if evaluado else np.nan,
            "nota_es_heredada": False, "resultado_tipo": tipo,
            "aprobado_curricular": (float(nota) >= 4.0) if evaluado else (True if tipo == "convalidacion" else None),
            "creditos": 6.0, "creditos_reconocidos": 6.0 if tipo == "convalidacion" else np.nan,
        })
    return pd.DataFrame(out)


NO_EGRESO = pd.DataFrame({"persona_key": [], "episodio_id": [], "periodo": []})
NO_VIA = pd.DataFrame(columns=[
    "postulacion_via_id", "year_admision", "persona_key", "cod_carrera", "cod_admision", "id_sede", "preferencia",
    "matricula", "puntaje_leng", "puntaje_mat", "puntaje_ciencias", "puntaje_historia", "puntaje_nem",
    "puntaje_ranking", "notas_em", "ponderado", "tipo_colegio", "depend_colegio", "region_colegio"])


def cortes_de(ep_df, est_df, egreso=NO_EGRESO, latest=LATEST, ks=(1, 2)):
    c, resumen = F.construir_cortes(ep_df, est_df, egreso, latest, ks)
    return c.set_index(["episodio_id", "k"]), resumen


# ---------------------------------------------------------------------------------------------
# population and eligibility
# ---------------------------------------------------------------------------------------------
def test_population_filters_level_and_admission_route():
    df = episodios(ep(1), ep(2, cod="IN"), ep(3, cod="PE"), ep(4, cod="IE"), ep(5, nivel=8), ep(6, adm=None))
    assert list(F.poblacion(df)["episodio_id"]) == [1]


def test_eligibility_needs_an_enrolled_state_in_the_kth_regular_period():
    e = episodios(ep(1, "a"), ep(2, "b"), ep(3, "c"))
    s = estados(
        ("a", 1, "201910", "M"), ("a", 1, "201920", "M"),              # enrolled in k=1 and k=2
        ("b", 2, "201910", "M"), ("b", 2, "201920", "P"),              # interruption in k=2: not eligible there
        ("c", 3, "201910", "E"),                                       # exited in k=1: not an enrolled state
    )
    c, resumen = cortes_de(e, s)
    assert set(c.index) == {(1, 1), (1, 2), (2, 1)}
    r1 = resumen[0]
    assert (r1["poblacion"], r1["sin_matricula_en_k"], r1["elegibles"]) == (3, 1, 2)


def test_correction_states_never_make_a_person_eligible():
    e = episodios(ep(1))
    s = estados(("p", 1, "201910", "M", "C1", "2019", True))
    c, _ = cortes_de(e, s)
    assert c.empty


def test_already_graduated_episode_is_not_eligible():
    e = episodios(ep(1))
    s = estados(("p", 1, "201910", "M"), ("p", 1, "201910", "G"))
    c, resumen = cortes_de(e, s)
    assert c.empty and resumen[0]["ya_egresado_o_titulado"] == 1


# ---------------------------------------------------------------------------------------------
# label
# ---------------------------------------------------------------------------------------------
def test_continuity_is_an_enrolled_state_two_regular_periods_later_in_any_program():
    e = episodios(ep(1, "a"), ep(2, "b"))
    s = estados(
        ("a", 1, "201910", "M"), ("a", 1, "202010", "M"),              # same program, horizon 202010
        ("b", 2, "201910", "M"), ("b", 9, "202010", "I", "C2"),        # other program (reintegro), horizon 202010
    )
    c, _ = cortes_de(e, s)
    assert bool(c.loc[(1, 1), "continua"]) and bool(c.loc[(1, 1), "continua_mismo_programa"])
    assert bool(c.loc[(2, 1), "continua"]) and not bool(c.loc[(2, 1), "continua_mismo_programa"])


def test_a_state_in_the_intermediate_period_is_not_continuity():
    e = episodios(ep(1))
    s = estados(("p", 1, "201910", "M"), ("p", 1, "201920", "M"))     # enrolled next semester, absent at horizon
    c, _ = cortes_de(e, s)
    assert not bool(c.loc[(1, 1), "continua"])
    assert c.loc[(1, 1), "no_continua_tipo"] == "ausencia"


def test_exit_state_is_distinguished_from_absence_and_interruption():
    e = episodios(ep(1, "a"), ep(2, "b"), ep(3, "c"))
    s = estados(
        ("a", 1, "201910", "M"), ("a", 1, "201920", "E"),              # explicit exit after the cutoff
        ("b", 2, "201910", "M"),                                       # nothing afterwards
        ("c", 3, "201910", "M"), ("c", 3, "201920", "P"),              # temporary withdrawal, not back at horizon
    )
    c, _ = cortes_de(e, s)
    assert c.loc[(1, 1), "no_continua_tipo"] == "salida"
    assert c.loc[(2, 1), "no_continua_tipo"] == "ausencia"
    assert c.loc[(3, 1), "no_continua_tipo"] == "interrupcion"
    assert not c["continua"].astype(bool).any()


def test_an_exit_recorded_in_the_cutoff_period_is_known_at_the_cutoff_and_not_eligible():
    e = episodios(ep(1, "d"), ep(2, "f"))
    s = estados(("d", 1, "201910", "M"), ("d", 1, "201910", "B"),     # renuncia in the cutoff period itself
                ("f", 2, "201910", "M"), ("f", 2, "201920", "B"))     # exit one period later: still a target
    c, resumen = cortes_de(e, s)
    assert (1, 1) not in c.index and (2, 1) in c.index
    assert resumen[0]["salida_en_corte"] == 1
    assert c.loc[(2, 1), "no_continua_tipo"] == "salida"


def test_graduating_before_the_horizon_counts_as_continuity():
    e = episodios(ep(1, "a"), ep(2, "b"))
    s = estados(("a", 1, "201910", "M"), ("a", 1, "201920", "G"),     # egreso state, then nothing
                ("b", 2, "201910", "M"))
    egreso = pd.DataFrame({"persona_key": ["b"], "episodio_id": [2], "periodo": ["201920"]})   # titulacion table
    c, _ = cortes_de(e, s, egreso)
    assert bool(c.loc[(1, 1), "continua"]) and bool(c.loc[(2, 1), "continua"])
    assert pd.isna(c.loc[(1, 1), "no_continua_tipo"])


def test_censored_and_uncovered_rows_have_no_label_and_stay_out_of_observed():
    e = episodios(ep(1, "a", adm="202510"), ep(2, "b", adm="201320"), ep(3, "c", adm="201310"))
    s = estados(("a", 1, "202510", "M"), ("a", 1, "202520", "M"),     # k=2 horizon 202620 = latest: censored
                ("b", 2, "201320", "M"),                              # 20 period before 2015: no coverage
                ("c", 3, "201310", "M"))
    c, _ = cortes_de(e, s)
    assert c.loc[(1, 1), "estado_muestra"] == "observada"            # horizon 202610 < latest
    assert c.loc[(1, 2), "estado_muestra"] == "censurada"
    assert pd.isna(c.loc[(1, 2), "continua"]) and pd.isna(c.loc[(1, 2), "no_continua_tipo"])
    assert c.loc[(2, 1), "estado_muestra"] == "sin_cobertura" and pd.isna(c.loc[(2, 1), "continua"])
    assert c.loc[(3, 1), "estado_muestra"] == "observada"


def test_label_period_is_always_after_the_cutoff_and_split_follows_the_cohort():
    e = episodios(ep(1, "a", adm="201910"), ep(2, "b", adm="202110"), ep(3, "c", adm="202210"), ep(4, "d", adm="202410"))
    s = estados(*[(p, i, a, "M") for i, (p, a) in enumerate([("a", "201910"), ("b", "202110"), ("c", "202210"),
                                                             ("d", "202410")], start=1)])
    c, _ = cortes_de(e, s)
    assert (c["periodo_horizonte"] > c["periodo_corte"]).all()
    assert c.loc[(1, 1), "split"] == "train" and c.loc[(2, 1), "split"] == "valid"
    assert c.loc[(3, 1), "split"] == "test" and c.loc[(4, 1), "split"] == "posterior"


# ---------------------------------------------------------------------------------------------
# point-in-time academic features
# ---------------------------------------------------------------------------------------------
def test_slot_vectorizado_matches_the_scalar_rule():
    periodos = ["201910", "201915", "201920", "201925", "202010", "201901", "201810", "bad", "202020"]
    s = pd.Series(periodos)
    base = pd.Series([F.base_ordinal("201910")] * len(periodos), dtype="float64")
    got = F.slot_vectorizado(s, base)
    want = [R.slot_de_periodo(p, "201910") for p in periodos]
    assert [None if np.isnan(g) else int(g) for g in got] == want


def _basic_world(extra_intentos=(), extra_estados=()):
    e = episodios(ep(1))
    s = estados(("p", 1, "201910", "M"), ("p", 1, "201920", "M"), *extra_estados)
    a = intentos(
        (1, "201910", "5.0", "MAT-1"), (1, "201910", "3.0", "MAT-2"),       # k=1: one pass, one fail
        (1, "201915", "6.0", "MAT-3"),                                      # winter, belongs to slot 2
        (1, "201920", "4.0", "MAT-4"), (1, "201920", "DPA", "MAT-5"),
        *extra_intentos,
    )
    return e, s, a


def _features(e, s, a):
    c, _ = F.construir_cortes(e, s, NO_EGRESO, LATEST, (1, 2))
    sem = F.tabla_semestres(F.poblacion(e), a, s, 2)
    return F.features_corte(c, sem, s).set_index(["episodio_id", "k"]), sem


def test_features_at_k1_use_only_the_first_regular_period():
    f, _ = _features(*_basic_world())
    r = f.loc[(1, 1)]
    assert (r["intentos_evaluados"], r["aprobados"], r["reprobados"]) == (2, 1, 1)
    assert r["creditos_aprobados"] == 6.0                       # only MAT-1 (the failed course adds nothing)
    assert r["tasa_aprobacion"] == 0.5 and r["promedio_evaluado"] == 4.0 and r["n_notas_promedio"] == 2
    assert r["cursos_verano_invierno"] == 0 and r["convalidaciones"] == 0 and r["semestres_matriculados"] == 1


def test_features_at_k2_add_the_winter_course_and_the_dpa_without_a_grade():
    f, _ = _features(*_basic_world())
    r = f.loc[(1, 2)]
    assert (r["intentos_evaluados"], r["aprobados"], r["reprobados"]) == (4, 3, 1)
    assert r["convalidaciones"] == 1 and r["cursos_verano_invierno"] == 1
    assert r["n_notas_promedio"] == 4 and r["promedio_evaluado"] == pytest.approx((5 + 3 + 6 + 4) / 4)   # DPA excluded
    assert r["creditos_aprobados"] == 6.0 * 4                                                            # MAT-1,3,4,5
    assert r["semestres_matriculados"] == 2 and r["intentos_ult_semestre"] == 2                          # 6.0 (winter) and 4.0


def test_dpa_does_not_enter_the_last_semester_attempts_or_rate():
    f, _ = _features(*_basic_world())
    r = f.loc[(1, 2)]
    assert r["intentos_ult_semestre"] == 2
    assert r["tasa_ult_semestre"] == 1.0                         # 6.0 and 4.0 approved, DPA not an attempt


def test_facts_after_the_cutoff_never_change_the_features():
    base, _ = _features(*_basic_world())
    # attempts in the horizon period and later, a state in a later period, another winter course after k=2
    e, s, a = _basic_world(
        extra_intentos=[(1, "202010", "1.0", "MAT-9"), (1, "202015", "7.0", "MAT-8"), (1, "202020", "2.0", "MAT-7"),
                        (1, "201925", "7.0", "MAT-6")],
        extra_estados=[("p", 1, "202010", "P"), ("p", 1, "202020", "P")],
    )
    f, _ = _features(e, s, a)
    cols = [c for c in base.columns if c not in ("n_interrupcion", "cambios_catalogo")]
    pd.testing.assert_frame_equal(base[cols], f.loc[base.index, cols])
    assert f.loc[(1, 2), "n_interrupcion"] == 0                  # the withdrawals are after the cutoff 201920
    assert f.loc[(1, 1), "intentos_evaluados"] == 2


def test_summer_course_after_k1_is_invisible_at_k1_but_visible_at_k2():
    e, s, a = _basic_world()
    f, sem = _features(e, s, a)
    assert f.loc[(1, 1), "cursos_verano_invierno"] == 0
    assert f.loc[(1, 2), "cursos_verano_invierno"] == 1
    sem1 = sem[(sem["episodio_id"] == 1) & (sem["j"] == 1)].iloc[0]
    assert sem1["vi"] == 0 and sem1["ie"] == 2


def test_attempts_without_an_episode_are_ignored():
    e, s, a = _basic_world()
    a = pd.concat([a, intentos((np.nan, "201910", "7.0", "X-1")).assign(intento_id=99)], ignore_index=True)
    f, _ = _features(e, s, a)
    assert f.loc[(1, 1), "intentos_evaluados"] == 2


def test_catalog_changes_and_interruptions_are_counted_up_to_the_cutoff_only():
    e = episodios(ep(1))
    s = estados(("p", 1, "201910", "M", "C1", "2019"), ("p", 1, "201915", "P", "C1", "2019"),
                ("p", 1, "201920", "M", "C1", "2019"), ("p", 1, "202010", "M", "C1", "2021"))              # catalog change after k=2: invisible
    a = intentos((1, "201910", "5.0", "MAT-1"))
    f, _ = _features(e, s, a)
    assert f.loc[(1, 2), "n_interrupcion"] == 1 and f.loc[(1, 2), "cambios_catalogo"] == 0


# ---------------------------------------------------------------------------------------------
# admission features
# ---------------------------------------------------------------------------------------------
def via_row(i, persona, year, cod, ponderado, mat="Y", prog="C1", leng=600):
    return {"postulacion_via_id": i, "year_admision": year, "persona_key": persona, "cod_carrera": prog,
            "cod_admision": cod, "id_sede": 1, "preferencia": "1", "matricula": mat, "puntaje_leng": leng,
            "puntaje_mat": 0, "puntaje_ciencias": None, "puntaje_historia": None, "puntaje_nem": 600,
            "puntaje_ranking": 600, "notas_em": 6.0, "ponderado": ponderado,
            "tipo_colegio": "H1-Humanista Científico Diurno", "depend_colegio": "4-Particular NO subvencionado",
            "region_colegio": "02"}


def test_scores_are_ranked_within_the_admission_year_only():
    via = pd.DataFrame([
        via_row(1, "a", "201910", "LS", 500), via_row(2, "b", "201910", "LS", 700),
        via_row(3, "c", "202010", "LS", 450), via_row(4, "d", "202010", "LS", 460),
    ])
    r = F.rangos_percentiles(via).set_index("postulacion_via_id")["pct_ponderado"]
    assert r[1] == 0.5 and r[2] == 1.0 and r[3] == 0.5 and r[4] == 1.0   # 2020 scores are not mixed with 2019
    assert F.rangos_percentiles(via)["pct_mat"].isna().all()             # a score of 0 is missing, not a rank


def test_admission_route_is_matched_to_the_episode_and_missing_routes_are_flagged():
    pop = F.poblacion(episodios(ep(1, "a", cod="LS"), ep(2, "z", cod="LS")))
    via = pd.DataFrame([
        via_row(1, "a", "201910", "LE", 500, mat="N"), via_row(2, "a", "201910", "LS", 600, mat="Y"),
        via_row(3, "a", "201910", "LS", 800, mat="Y", prog="OTHER"),
    ])
    out = F.features_admision(pop, via).set_index("episodio_id")
    assert bool(out.loc[1, "con_postulacion"]) and not bool(out.loc[2, "con_postulacion"])
    assert out.loc[1, "tipo_colegio"] == "H1" and out.loc[1, "depend_colegio"] == "4"
    assert pd.isna(out.loc[2, "pct_ponderado"])


def test_full_snapshot_has_sex_only_for_fairness_and_no_label_columns_in_features():
    e, s, a = _basic_world()
    snap, sem, embudo = F.construir_snapshot(e, s, a, NO_VIA, NO_EGRESO, LATEST)
    assert "sexo_equidad" in snap.columns and "sexo" not in snap.columns
    assert len(snap) == 2 and set(snap["k"]) == {1, 2}
    assert len(sem) == 2 and embudo[0]["elegibles"] == 1


def test_p51_not_enrolled_at_the_horizon_is_no_continuidad_even_with_an_interruption_state_there():
    """DAI P51: no continuidad = ya no se encuentra matriculado (a temporary-withdrawal state is not enrolled)."""
    e = episodios(ep(1))
    s = estados(("p", 1, "201910", "M"), ("p", 1, "202010", "P"))     # horizon 202010: withdrawal, not enrolled
    c, _ = cortes_de(e, s)
    assert not bool(c.loc[(1, 1), "continua"])
    assert c.loc[(1, 1), "no_continua_tipo"] == "interrupcion"


# ---------------------------------------------------------------------------------------------
# P47 (DAI, 13-11-2026): admission test by process year and min-max normalisation per test and year
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("anio,prueba", [(2005, "PSU"), (2015, "PSU"), (2020, "PSU"), (2021, "PDT"), (2022, "PDT"),
                                         (2023, "PAES"), (2026, "PAES")])
def test_p47_the_admission_test_follows_the_process_year(anio, prueba):
    assert R.prueba_admision(anio) == prueba


def test_p47_unknown_or_malformed_process_year_has_no_test():
    assert R.prueba_admision(None) is None and R.prueba_admision("abc") is None


def test_p47_scores_are_min_max_scaled_within_test_and_year():
    via = pd.DataFrame([
        via_row(1, "a", "202010", "LS", 500), via_row(2, "b", "202010", "LS", 700), via_row(3, "c", "202010", "LS", 600),
        via_row(4, "d", "202110", "LS", 5000), via_row(5, "e", "202110", "LS", 9000),
    ])
    out = F.normalizar_min_max(via).set_index("postulacion_via_id")
    assert list(out.loc[[1, 2, 3], "mm_ponderado"]) == [0.0, 1.0, 0.5]
    assert list(out.loc[[4, 5], "mm_ponderado"]) == [0.0, 1.0]            # a different scale in another year
    assert out.loc[1, "prueba_admision"] == "PSU" and out.loc[4, "prueba_admision"] == "PDT"
    assert out["mm_mat"].isna().all()                                      # a score of 0 is missing


def test_p47_a_year_with_a_single_value_has_no_scale_and_an_order_of_magnitude_outlier_is_ignored():
    via = pd.DataFrame([via_row(1, "a", "201910", "LS", 500)] + [
        via_row(i, f"p{i}", "202010", "LS", 400 + 10 * i, leng=500 + 10 * i) for i in range(2, 8)] + [
        via_row(8, "z", "202010", "LS", 450, leng=55700)])               # 557,00 read as 55700
    out = F.normalizar_min_max(via).set_index("postulacion_via_id")
    assert pd.isna(out.loc[1, "mm_ponderado"])                              # min == max: undefined, not 0
    assert pd.isna(out.loc[8, "mm_leng"])                                    # the outlier is not a score
    assert out.loc[7, "mm_leng"] == 1.0 and out.loc[2, "mm_leng"] == 0.0     # and it does not squash the others


def test_p47_features_admision_carries_the_test_and_the_scaled_scores_next_to_the_percentiles():
    pop = F.poblacion(episodios(ep(1, "a", cod="LS")))
    via = pd.DataFrame([via_row(1, "a", "201910", "LS", 500), via_row(2, "b", "201910", "LS", 700)])
    out = F.features_admision(pop, via).set_index("episodio_id")
    assert out.loc[1, "prueba_admision"] == "PSU" and out.loc[1, "mm_ponderado"] == 0.0
    assert out.loc[1, "pct_ponderado"] == 0.5                               # the percentile is kept
    assert set(F.MM_COLS) <= set(out.columns)


def test_p47_the_weighted_score_comes_in_mixed_decimal_scales_and_is_brought_to_one_scale_first():
    """Measured on the source: `ponderado` is stored as 700.00 (x1), 7000 (x10) and 70000 (x100) inside one process year, in
    roughly equal parts in 2025-2026; the median guard alone cannot tell them apart."""
    via = pd.DataFrame([
        via_row(1, "a", "202510", "LS", 500), via_row(2, "b", "202510", "LS", 7000), via_row(3, "c", "202510", "LS", 80000),
        via_row(4, "d", "202510", "LS", 650.5), via_row(5, "e", "202510", "LS", 6505), via_row(6, "f", "202510", "LS", 650500),
    ])
    out = F.normalizar_min_max(via).set_index("postulacion_via_id")
    assert out.loc[1, "mm_ponderado"] == 0.0 and out.loc[3, "mm_ponderado"] == 1.0
    assert out.loc[2, "mm_ponderado"] == pytest.approx(200 / 300)
    assert out.loc[4, "mm_ponderado"] == out.loc[5, "mm_ponderado"] == out.loc[6, "mm_ponderado"]


def test_p47_reescala_decimal_leaves_scores_below_one_hundred_and_non_positive_values_alone():
    assert R.reescala_decimal(557.0) == 557.0 and R.reescala_decimal(5570.0) == 557.0 and R.reescala_decimal(55700.0) == 557.0
    assert R.reescala_decimal(55.0) == 55.0 and R.reescala_decimal(0.0) == 0.0 and R.reescala_decimal(-3.0) == -3.0
