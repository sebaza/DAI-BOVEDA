"""Selection gate, train-only preprocessing and sequences of the T1 models (no database)."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from models import data as D  # noqa: E402


def frame(n=60, seed=0):
    rng = np.random.default_rng(seed)
    split = np.array(["train"] * 30 + ["valid"] * 15 + ["test"] * 15)
    return pd.DataFrame({
        "episodio_id": np.arange(n), "k": 1,
        "split": split, "cohorte_anio": np.where(split == "train", 2016, np.where(split == "valid", 2020, 2022)),
        "estado_muestra": "observada", "continua": rng.random(n) > 0.2,
        "cod_programa": rng.choice(["A", "B", "C"], n), "via_clase": "regular", "cod_admision": "LS",
        "sede": "1", "tipo_colegio": "H1", "depend_colegio": "3", "region_colegio": "02",
        "preferencia": rng.integers(1, 5, n).astype(float), "con_postulacion": True,
        **{c: rng.random(n) for c in D.MM_COLS}, "prueba_admision": "PSU",
        **{c: rng.random(n) * 10 for c in D.ACAD_NUM},
        "sexo_equidad": rng.choice(["F", "M"], n),
    })


def test_selection_excludes_censored_uncovered_and_future_cohorts():
    df = frame()
    df.loc[0, "estado_muestra"] = "censurada"
    df.loc[1, "estado_muestra"] = "sin_cobertura"
    df.loc[2, "split"] = "posterior"
    df["continua"] = df["continua"].astype("boolean")
    df.loc[3, "continua"] = pd.NA
    out = D.seleccionar_modelado(df)
    assert not {0, 1, 2, 3} & set(out["episodio_id"])
    assert set(out["split"]) <= {"train", "valid", "test"}
    assert set(out["y"].unique()) <= {0, 1}


def test_event_is_no_continuidad():
    df = frame()
    df.loc[5, "continua"] = False
    df.loc[6, "continua"] = True
    out = D.seleccionar_modelado(df).set_index("episodio_id")
    assert out.loc[5, "y"] == 1 and out.loc[6, "y"] == 0


def test_sensitivity_filter_only_touches_train():
    df = frame()
    df.loc[:9, "cohorte_anio"] = 2010
    out = D.seleccionar_modelado(df, train_desde=2015)
    assert (out.loc[out["split"] == "train", "cohorte_anio"] >= 2015).all()
    assert (out["split"] == "valid").sum() == 15 and (out["split"] == "test").sum() == 15


def test_sex_and_labels_can_never_be_model_features():
    with pytest.raises(ValueError):
        D.Preprocesador(["sexo_equidad"], [])
    with pytest.raises(ValueError):
        D.assert_sin_fuga(["continua"])
    for nombre, (num, cat) in D.GRUPOS.items():
        D.assert_sin_fuga(num + cat)


def test_preprocessing_is_fitted_on_train_only():
    df = D.seleccionar_modelado(frame())
    tr, va = df[df["split"] == "train"], df[df["split"] == "valid"].copy()
    num, cat = D.GRUPOS["pre_entry+academico"]
    p1 = D.Preprocesador(num, cat, min_count=1).fit(tr)
    va2 = va.copy()
    va2[D.ACAD_NUM] = va2[D.ACAD_NUM] * 1000 + 5          # wildly different validation values
    va2["cod_programa"] = "ZZZ"
    p2 = D.Preprocesador(num, cat, min_count=1).fit(pd.concat([tr]))
    pd.testing.assert_series_equal(p1.medias, p2.medias)
    pd.testing.assert_series_equal(p1.desvios, p2.desvios)
    assert p1.vocab == p2.vocab
    # parameters equal the train statistics, not those of train+valid
    assert p1.medias["creditos_aprobados"] == pytest.approx(tr["creditos_aprobados"].mean())
    assert p1.medias["creditos_aprobados"] != pytest.approx(pd.concat([tr, va])["creditos_aprobados"].mean())
    assert "ZZZ" not in p1.vocab["cod_programa"]
    assert (p1.transform_cat_codes(va2)[:, 0] == 0).all()   # unseen category -> code 0


def test_missing_values_are_imputed_with_the_train_median_and_flagged():
    df = D.seleccionar_modelado(frame())
    df.loc[df.index[:5], "mm_ponderado"] = np.nan
    tr = df[df["split"] == "train"]
    p = D.Preprocesador(D.PRE_NUM, D.PRE_CAT, min_count=1).fit(tr)
    assert "mm_ponderado" in p.con_indicador
    x = p.transform_num(df)
    assert not np.isnan(x).any()
    na_col = p.nombres_num().index("mm_ponderado__na")
    assert x[:5, na_col].tolist() == [1.0] * 5 and x[5:, na_col].sum() == 0
    assert p.transform(df).shape[1] == len(p.nombres_num()) + sum(p.cardinalidades())


def test_rare_categories_go_to_the_unknown_code():
    df = D.seleccionar_modelado(frame())
    df.loc[df.index[0], "cod_programa"] = "RARE"
    tr = df[df["split"] == "train"]
    p = D.Preprocesador(D.PRE_NUM, D.PRE_CAT, min_count=5).fit(tr)
    assert "RARE" not in p.vocab["cod_programa"]
    assert p.transform_cat_codes(df.iloc[[0]])[0, 0] == 0


def test_sequences_use_only_slots_up_to_k():
    snap = pd.DataFrame({"episodio_id": [10, 11]})
    rows = []
    for e in (10, 11):
        for j in (1, 2, 3):
            rows.append({"episodio_id": e, "j": j, "matriculado": True, "interrupcion": False,
                         "intentos_evaluados": 5, "aprobados": 4, "reprobados": 1, "convalidaciones": 0,
                         "creditos_aprobados": 24.0, "cursos_verano_invierno": 0, "promedio": 5.0 + j,
                         "n_notas_promedio": 5, "creditos_acumulados": 24.0 * j})
    sem = pd.DataFrame(rows)
    seq1 = D.construir_secuencias(snap, sem, 1)
    seq2 = D.construir_secuencias(snap, sem, 2)
    assert seq1.shape == (2, 1, len(D.SEQ_COLS)) and seq2.shape == (2, 2, len(D.SEQ_COLS))
    np.testing.assert_array_equal(seq2[:, 0], seq1[:, 0])
    # the third slot (after k=2) never enters; changing it changes nothing
    sem2 = sem.copy()
    sem2.loc[sem2["j"] == 3, "promedio"] = 1.0
    np.testing.assert_array_equal(D.construir_secuencias(snap, sem2, 2), seq2)


def test_official_benchmark_trains_from_cohort_2015_and_all_years_is_sensitivity():
    from evaluation.run_benchmark import parsear
    from pipelines.snapshots.rules import TRAIN_DESDE_OFICIAL

    assert TRAIN_DESDE_OFICIAL == 2015
    oficial = parsear([])
    assert oficial.train_desde == 2015 and oficial.salida == "resultados_t1" and oficial.k == [1, 2]
    sens = parsear(["--todos-los-anios"])
    assert sens.train_desde is None and sens.salida == "resultados_t1_todos_anios"
    assert parsear(["--train-desde", "2016"]).train_desde == 2016


def test_prediction_artefact_suffix_marks_only_the_sensitivity_runs():
    from evaluation.run_benchmark import sufijo_preds

    assert sufijo_preds(2015) == "" and sufijo_preds(None) == "_todos_anios" and sufijo_preds(2016) == "_desde2016"


# ---- benefits (16-11-2026) -------------------------------------------------------------------------------------------------
def test_the_official_groups_do_not_contain_any_benefit_column():
    from pipelines.snapshots import features_beneficios as FB

    for num, cat in D.GRUPOS.values():
        assert not set(FB.COLS_BENEFICIOS) & set(num + cat)


def test_benefit_groups_extend_the_best_official_set_and_the_loss_only_exists_in_the_k4_set():
    from pipelines.snapshots import features_beneficios as FB

    base_num, base_cat = D.GRUPOS["pre_entry+academico"]
    num, cat = D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios"]
    assert num[:len(base_num)] == base_num and cat[:len(base_cat)] == base_cat
    assert set(num) - set(base_num) == set(D.BEN_NUM) and "banda_decil" in cat
    assert not set(FB.COLS_PERDIDA) & set(num)
    num4, _ = D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios+perdidas"]
    assert set(FB.COLS_PERDIDA) | {"perdida_sin_dato"} <= set(num4)


def test_second_semester_and_total_amounts_are_forbidden_as_features():
    for col in ("benef_sem2", "total", "monto_sem2", "monto_total"):
        with pytest.raises(ValueError):
            D.assert_sin_fuga([col])
    for num, cat in D.GRUPOS_BENEFICIOS.values():
        D.assert_sin_fuga(num + cat)


def test_the_benefit_set_imputes_unknown_years_on_train_only_and_adds_the_missing_indicator():
    df = frame()
    for c in D.BEN_NUM:
        df[c] = np.where(df["split"] == "train", np.nan, 1.0)
    df["banda_decil"] = np.where(df["split"] == "train", None, "<=6")
    num, cat = D.GRUPOS_BENEFICIOS["pre_entry+academico+beneficios"]
    train = df[df["split"] == "train"].assign(y=0)
    prep = D.Preprocesador(num, cat).fit(train)
    assert "tiene_gratuidad__na" in prep.nombres_num()
    x = prep.transform(df[df["split"] == "valid"])
    assert np.isfinite(x).all()
