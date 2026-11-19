"""New T1 variables of 18-11-2026 (P117-P127): last-semester performance, repeated failures, curricular lag, load evolution and
temporary withdrawal / annulment. Synthetic frames, no database. Every feature must use only facts known at the cut."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from pipelines.snapshots import features as F                        # noqa: E402
from pipelines.snapshots import features_t1_nuevas as N              # noqa: E402
from pipelines.snapshots import features_t3 as F3                    # noqa: E402
from pipelines.snapshots import malla_avance as MA                   # noqa: E402
from tests.unit.test_snapshot_features import NO_EGRESO, NO_VIA, LATEST, episodios   # noqa: E402

KS = (1, 2, 3)
MALLA = pd.DataFrame([
    ("C1", "2019", "M-1", 1, 6.0), ("C1", "2019", "M-2", 1, 6.0), ("C1", "2019", "M-3", 2, 6.0),
    ("C1", "2019", "M-4", 2, 4.0), ("C1", "2019", "M-5", 3, 8.0),
], columns=["cod_programa", "catalogo", "codigo_asignatura", "semestre", "creditos"])


def ep(eid=1, persona="p", adm="201910", catalogo="2019", prog="C1"):
    row = (eid, persona, prog, adm, "LS", 1, 1, "1. Ingreso Regular o Centralizada", "F")
    return row, catalogo


def eps(*items):
    df = episodios(*[r for r, _ in items])
    df["catalogo_inicial"] = [c for _, c in items]
    return df


def est(*rows):
    """(persona, episodio_id, periodo, cod_estado[, fecha]) -> states with the date columns of the loader."""
    out = []
    for i, r in enumerate(rows):
        persona, eid, periodo, cod = r[:4]
        fecha = pd.Timestamp(r[4]) if len(r) > 4 and r[4] is not None else pd.NaT
        marcador = bool(r[5]) if len(r) > 5 else False
        out.append({"persona_key": persona, "episodio_id": eid, "periodo": periodo, "cod_estado": cod,
                    "cod_programa": "C1", "catalogo": "2019", "es_correccion_sistema": False, "orden_canonico": i + 1,
                    "fecha_estado_original": fecha, "fecha_marcador": marcador})
    df = pd.DataFrame(out)
    df["episodio_id"] = df["episodio_id"].astype("Int64")
    return df


def its(*rows):
    """(episodio_id, periodo, nota, codigo[, oportunidad[, creditos[, tipo]]])."""
    out = []
    for i, (eid, periodo, nota, codigo, *rest) in enumerate(rows):
        oport = rest[0] if len(rest) > 0 else 1
        cred = rest[1] if len(rest) > 1 else 6.0
        tipo = rest[2] if len(rest) > 2 else "evaluado"
        evaluado = tipo == "evaluado"
        out.append({
            "intento_id": i + 1, "episodio_id": eid, "periodo": periodo, "codigo_asignatura": codigo,
            "es_intento_evaluado": evaluado, "nota_numerica": float(nota) if evaluado else np.nan,
            "nota_es_heredada": False, "resultado_tipo": tipo, "oportunidad": oport,
            "aprobado_curricular": (float(nota) >= 4.0) if evaluado else (True if tipo == "convalidacion" else None),
            "creditos": cred, "creditos_reconocidos": cred if tipo == "convalidacion" else np.nan,
        })
    return pd.DataFrame(out)


MATRICULADO = [("p", 1, "201910", "M"), ("p", 1, "201920", "M"), ("p", 1, "202010", "M"), ("p", 1, "202020", "M")]


def snapshot(ep_df, est_df, it_df, malla=MALLA, ks=KS):
    snap, _, _ = F.construir_snapshot(ep_df, est_df, it_df, NO_VIA, NO_EGRESO, LATEST, ks, malla=malla)
    return snap.set_index(["episodio_id", "k"])


def test_new_columns_are_added_only_when_the_malla_is_given():
    e, s = eps(ep()), est(*MATRICULADO)
    it = its((1, "201910", 5.0, "M-1"))
    sin, _, _ = F.construir_snapshot(e, s, it, NO_VIA, NO_EGRESO, LATEST, KS)
    con, _, _ = F.construir_snapshot(e, s, it, NO_VIA, NO_EGRESO, LATEST, KS, malla=MALLA)
    assert not set(N.COLS_NUEVAS_T1) & set(sin.columns)
    assert set(N.COLS_NUEVAS_T1) <= set(con.columns)
    assert list(con.columns[: len(sin.columns)]) == list(sin.columns)          # the old columns are untouched


def test_last_semester_credits_and_average_changes():
    e, s = eps(ep()), est(*MATRICULADO)
    it = its(
        (1, "201910", 6.0, "M-1"), (1, "201910", 4.0, "M-2"),                  # slot 1: average 5.0, 12 credits
        (1, "201920", 7.0, "M-3"), (1, "201920", 5.0, "M-4", 1, 4.0),         # slot 2: average 6.0, 10 credits
        (1, "202010", 3.0, "M-5"),                                             # slot 3: average 3.0, fails
    )
    f = snapshot(e, s, it)
    assert f.loc[(1, 1), "creditos_aprob_ult_sem"] == 12.0
    assert np.isnan(f.loc[(1, 1), "delta_promedio_sem"]) and np.isnan(f.loc[(1, 1), "delta_promedio_acum"])
    assert f.loc[(1, 2), "creditos_aprob_ult_sem"] == 10.0
    assert f.loc[(1, 2), "delta_promedio_sem"] == pytest.approx(1.0)           # 6.0 - 5.0
    assert f.loc[(1, 2), "delta_promedio_acum"] == pytest.approx(1.0)          # previous cumulative average = 5.0
    assert f.loc[(1, 3), "creditos_aprob_ult_sem"] == 0.0
    assert f.loc[(1, 3), "delta_promedio_sem"] == pytest.approx(-3.0)          # 3.0 - 6.0
    assert f.loc[(1, 3), "delta_promedio_acum"] == pytest.approx(3.0 - 5.5)    # previous cumulative = (6+4+7+5)/4


def test_cumulative_reference_is_the_average_of_the_previous_semesters_only():
    e, s = eps(ep()), est(*MATRICULADO)
    it = its((1, "201910", 5.0, "M-1"), (1, "201910", 5.0, "M-2"), (1, "201920", 7.0, "M-3"), (1, "202010", 4.0, "M-5"))
    f = snapshot(e, s, it)
    assert f.loc[(1, 3), "delta_promedio_acum"] == pytest.approx(4.0 - (5.0 + 5.0 + 7.0) / 3)


def test_failures_in_second_and_third_opportunity_and_distinct_repeated_courses():
    e, s = eps(ep()), est(*MATRICULADO)
    it = its(
        (1, "201910", 3.0, "M-1", 1), (1, "201910", 3.0, "M-2", 1),            # first opportunity failures: not counted
        (1, "201920", 3.0, "M-1", 2), (1, "201920", 5.0, "M-2", 2),            # 2nd opp.: one fail, one pass
        (1, "202010", 2.0, "M-1", 3), (1, "202010", 6.0, "M-3", 1),            # 3rd opp.: fail
    )
    f = snapshot(e, s, it)
    assert (f.loc[(1, 1), "repro_oport2"], f.loc[(1, 1), "repro_oport3"], f.loc[(1, 1), "ramos_repetidos"]) == (0, 0, 0)
    assert (f.loc[(1, 2), "repro_oport2"], f.loc[(1, 2), "repro_oport3"], f.loc[(1, 2), "ramos_repetidos"]) == (1, 0, 2)
    assert (f.loc[(1, 3), "repro_oport2"], f.loc[(1, 3), "repro_oport3"], f.loc[(1, 3), "ramos_repetidos"]) == (2, 1, 2)


def test_load_evolution_counts_attempts_that_are_not_convalidations():
    e, s = eps(ep()), est(*MATRICULADO)
    it = its(
        (1, "201910", 5.0, "M-1", 1, 6.0), (1, "201910", 5.0, "M-2", 1, 6.0), (1, "201910", None, "X-1", 1, 6.0, "convalidacion"),
        (1, "201920", 5.0, "M-3", 1, 6.0), (1, "201920", None, "M-4", 1, 4.0, "renuncia"),
        (1, "202010", 5.0, "M-5", 1, 8.0), (1, "202010", 5.0, "X-2", 1, 3.0), (1, "202010", 5.0, "X-3", 1, 3.0),
    )
    f = snapshot(e, s, it)
    assert (f.loc[(1, 1), "ramos_ins_ult"], f.loc[(1, 1), "creditos_ins_ult"]) == (2, 12.0)   # the convalidation is no load
    assert np.isnan(f.loc[(1, 1), "delta_ramos_ins"]) and np.isnan(f.loc[(1, 1), "delta_creditos_ins"])
    assert (f.loc[(1, 2), "ramos_ins_ult"], f.loc[(1, 2), "delta_ramos_ins"]) == (2, 0)       # a withdrawn course was enrolled
    assert f.loc[(1, 2), "delta_creditos_ins"] == pytest.approx(10.0 - 12.0)
    assert (f.loc[(1, 3), "ramos_ins_ult"], f.loc[(1, 3), "delta_ramos_ins"]) == (3, 1)
    assert f.loc[(1, 3), "delta_creditos_ins"] == pytest.approx(14.0 - 10.0)


def test_curricular_lag_uses_the_malla_of_the_initial_catalog_like_t3():
    e, s = eps(ep()), est(*MATRICULADO)
    it = its((1, "201910", 5.0, "M-1"), (1, "201920", 5.0, "M-3"))
    f = snapshot(e, s, it)
    assert f.loc[(1, 1), "creditos_esperados"] == 12.0 and f.loc[(1, 2), "creditos_esperados"] == 22.0
    assert f.loc[(1, 3), "creditos_esperados"] == 30.0
    assert f.loc[(1, 2), "avance_malla"] == pytest.approx(12.0 / 22.0)
    assert f.loc[(1, 2), "fraccion_malla"] == pytest.approx(12.0 / 30.0)          # the malla totals 30 credits


def test_curricular_lag_is_unknown_without_a_malla_for_the_catalog():
    e = eps(ep(catalogo="2099"))
    f = snapshot(e, est(*MATRICULADO), its((1, "201910", 5.0, "M-1")))
    assert f[["creditos_esperados", "avance_malla", "fraccion_malla"]].isna().all().all()


def test_the_shared_malla_helper_equals_the_t3_computation_without_editing_t3():
    pop = pd.DataFrame({"episodio_id": [1, 2], "cod_programa": ["C1", "C1"], "catalogo_inicial": ["2019", "2099"]})
    prog_cat = pd.DataFrame({"cod_programa": ["C1"], "catalogo": ["2019"], "duracion": [8]})
    t3 = F3.features_programa(pop, MALLA, prog_cat, [1, 2, 3]).set_index("episodio_id")
    mine = MA.creditos_malla(pop, MALLA, [1, 2, 3]).set_index("episodio_id")
    for k in (1, 2, 3):
        pd.testing.assert_series_equal(mine[f"_ce{k}"], t3[f"_ce{k}"], check_names=False)
    pd.testing.assert_series_equal(mine["creditos_malla_total"], t3["creditos_malla_total"], check_names=False)


def test_temporary_withdrawal_and_annulment_before_the_cut_with_dates():
    e = eps(ep())
    s = est(("p", 1, "201910", "M"), ("p", 1, "201920", "M"), ("p", 1, "202010", "M"),
            ("p", 1, "201920", "P", "2019-09-01"),                           # withdrawal dated inside slot 2
            ("p", 1, "202010", "A", "2020-04-01"))                           # annulment dated inside slot 3
    f = snapshot(e, s, its((1, "201910", 5.0, "M-1")))
    assert (f.loc[(1, 1), "n_retiro_temporal"], f.loc[(1, 1), "n_anulacion"]) == (0, 0)
    assert np.isnan(f.loc[(1, 1), "sem_desde_ultimo_retiro"]) and np.isnan(f.loc[(1, 1), "dias_desde_ultimo_retiro"])
    assert (f.loc[(1, 2), "n_retiro_temporal"], f.loc[(1, 2), "n_anulacion"]) == (1, 0)
    assert f.loc[(1, 2), "sem_desde_ultimo_retiro"] == 0
    assert f.loc[(1, 2), "dias_desde_ultimo_retiro"] == (pd.Timestamp("2020-02-29") - pd.Timestamp("2019-09-01")).days
    assert (f.loc[(1, 3), "n_retiro_temporal"], f.loc[(1, 3), "n_anulacion"]) == (1, 1)
    assert f.loc[(1, 3), "sem_desde_ultimo_retiro"] == 0
    assert f.loc[(1, 3), "dias_desde_ultimo_retiro"] == (pd.Timestamp("2020-07-31") - pd.Timestamp("2020-04-01")).days


def test_withdrawal_without_a_date_counts_by_period_and_a_future_marker_date_is_ignored_for_days():
    e = eps(ep())
    s = est(("p", 1, "201910", "M"), ("p", 1, "201920", "M"), ("p", 1, "201910", "P"),
            ("p", 1, "201920", "A", "2031-01-01", True))
    f = snapshot(e, s, its((1, "201910", 5.0, "M-1")), ks=(1, 2))
    assert (f.loc[(1, 1), "n_retiro_temporal"], f.loc[(1, 1), "sem_desde_ultimo_retiro"]) == (1, 0)
    assert np.isnan(f.loc[(1, 1), "dias_desde_ultimo_retiro"])
    assert f.loc[(1, 2), "n_anulacion"] == 1 and f.loc[(1, 2), "sem_desde_ultimo_retiro"] == 0
    assert np.isnan(f.loc[(1, 2), "dias_desde_ultimo_retiro"])


def test_a_withdrawal_dated_after_the_end_of_the_cut_period_is_not_known_at_the_cut():
    e = eps(ep())
    s = est(("p", 1, "201910", "M"), ("p", 1, "201920", "M"),
            ("p", 1, "201910", "P", "2019-09-15"))                           # recorded in 201910 but dated after July
    f = snapshot(e, s, its((1, "201910", 5.0, "M-1")), ks=(1, 2))
    assert f.loc[(1, 1), "n_retiro_temporal"] == 0
    assert f.loc[(1, 2), "n_retiro_temporal"] == 1


def test_states_after_the_cut_and_correction_states_never_count():
    e = eps(ep())
    base = [("p", 1, "201910", "M"), ("p", 1, "201920", "M")]
    s = est(*base, ("p", 1, "202010", "P", "2020-04-01"), ("p", 1, "202020", "A", "2020-10-01"))
    f = snapshot(e, s, its((1, "201910", 5.0, "M-1")), ks=(1, 2))
    assert (f[["n_retiro_temporal", "n_anulacion"]] == 0).all().all()
    corr = est(*base, ("p", 1, "201910", "P", "2019-04-01"))
    corr.loc[corr["cod_estado"] == "P", "es_correccion_sistema"] = True
    g = snapshot(e, corr, its((1, "201910", 5.0, "M-1")), ks=(1, 2))
    assert (g["n_retiro_temporal"] == 0).all()


def test_semesters_without_recorded_failures_are_counted_p58():
    e = eps(ep(adm="201920"))
    s = est(("p", 1, "201920", "M"), ("p", 1, "202010", "M"), ("p", 1, "202020", "M"))
    f = snapshot(e, s, its((1, "201920", 5.0, "M-1")), ks=(1, 2, 3))
    assert f["n_sem_sin_reprob"].tolist() == [1, 2, 2]


@pytest.mark.parametrize("k", [1, 2, 3])
def test_leakage_changing_or_deleting_facts_after_the_cut_never_changes_the_features(k):
    e = eps(ep())
    s = est(("p", 1, "201910", "M"), ("p", 1, "201920", "M"), ("p", 1, "202010", "M"), ("p", 1, "202020", "M"),
            ("p", 1, "201920", "P", "2019-10-01"))
    it = its((1, "201910", 5.0, "M-1"), (1, "201920", 3.0, "M-1", 2), (1, "202010", 6.0, "M-3"), (1, "202020", 2.0, "M-4", 3))
    base = snapshot(e, s, it).loc[(1, k)][N.COLS_NUEVAS_T1]
    cut = {1: "201910", 2: "201920", 3: "202010"}[k]
    # change every attempt after the cut and add withdrawals / annulments after it
    it2 = it.copy()
    later = it2["periodo"] > cut
    it2.loc[later, ["nota_numerica", "oportunidad", "creditos"]] = [7.0, 3, 9.0]
    it2.loc[later, "aprobado_curricular"] = True
    s2 = pd.concat([s, est(("p", 1, "202020", "P", "2020-09-01"), ("p", 1, "202020", "A", "2020-09-02"))], ignore_index=True)
    changed = snapshot(e, s2, it2).loc[(1, k)][N.COLS_NUEVAS_T1]
    pd.testing.assert_series_equal(base, changed)
    # delete every attempt after the cut
    borrado = snapshot(e, s, it.loc[it["periodo"] <= cut]).loc[(1, k)][N.COLS_NUEVAS_T1]
    pd.testing.assert_series_equal(base, borrado)


def test_feature_blocks_cover_the_new_columns_exactly():
    todas = [c for cols in N.BLOQUES.values() for c in cols]
    assert sorted(todas) == sorted(N.COLS_NUEVAS_T1) and len(todas) == len(set(todas))


def test_model_groups_match_the_feature_blocks_and_carry_no_forbidden_column():
    from models import data as D

    assert D.NUEVAS_BLOQUES_T1 == N.BLOQUES and D.NUEVAS_NUM == N.COLS_NUEVAS_T1
    for num, cat in D.GRUPOS_NUEVAS.values():
        D.assert_sin_fuga(num + cat)
        assert set(D.GRUPOS["pre_entry+academico"][0]) <= set(num)
    assert set(D.GRUPOS_NUEVAS) == {"pre_entry+academico+nuevas", *[f"pre_entry+academico+{b}" for b in N.BLOQUES]}


def test_migration_030_passes_the_guard_and_covers_every_new_column_of_both_snapshots():
    import re
    from pathlib import Path

    from pipelines.migrate import validate_sql
    from pipelines.snapshots import features_t2 as F2
    from pipelines.snapshots import t1 as T1

    sql = (Path(__file__).resolve().parents[2] / "sql" / "core" / "030_variables_nuevas_t1_t2.sql").read_text(encoding="utf-8")
    assert validate_sql(sql, "030_variables_nuevas_t1_t2.sql")
    t1 = set(re.findall(r"ALTER TABLE neural_mart\.snapshot_t1 ADD COLUMN IF NOT EXISTS (\w+)", sql))
    t2 = set(re.findall(r"ALTER TABLE neural_mart\.snapshot_t2 ADD COLUMN IF NOT EXISTS (\w+)", sql))
    assert t1 == set(N.COLS_NUEVAS_T1) and t2 == set(F2.FEATURE_COLS_NUEVAS_T2)
    assert set(N.COLS_NUEVAS_T1) <= set(T1.SNAPSHOT_COLS)
    assert not re.search(r"\b(drop|delete|truncate|update)\b", sql, re.I)
