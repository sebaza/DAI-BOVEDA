"""P55 ablation of T2 (stage B): course pass-rate statistics with exponential time decay or a recent window instead of the
expanding history. Point-in-time (strictly earlier periods only); equal to a brute-force definition. No database."""
import numpy as np
import pytest

pd = pytest.importorskip("pandas")

from models import t2_deriva as DV                     # noqa: E402

M = 10.0


def tabla():
    filas = [("X", "P1", "201510", 10, 8, 40.0), ("X", "P2", "201510", 6, 3, 24.0), ("X", "P1", "201710", 20, 10, 90.0),
             ("X", "P1", "201910", 30, 27, 150.0), ("X", None, "201910", 4, 4, 24.0), ("X", "P1", "202210", 40, 20, 180.0),
             ("Y", "P1", "201710", 12, 6, 50.0), ("X", "P1", "202115", 5, 5, 30.0)]
    return pd.DataFrame(filas, columns=["codigo_asignatura", "prog", "periodo", "n", "a", "s"])


def filas_T():
    return pd.DataFrame({"codigo_asignatura": ["X", "X", "X", "Y", "X", "Z"], "cod_programa": ["P1", "P2", "P1", "P1", None, "P1"],
                         "periodo": ["201710", "201710", "202220", "202210", "202220", "202210"],
                         "episodio_id": [1, 2, 1, 3, 4, 5]})


def fuerza_bruta(T, tab, modo, vida=2.0, ventana=3.0):
    out = []
    for r in T.itertuples():
        t_T = DV.tiempo(r.periodo)

        def w(p):
            d = (t_T - DV.tiempo(p)) / 4.0
            if DV.tiempo(p) >= t_T:
                return 0.0
            return 0.5 ** (d / vida) if modo == "decaimiento" else float(d < ventana)

        def suma(sel):
            ww = np.array([w(p) for p in sel["periodo"]])
            return [float((ww * sel[c]).sum()) for c in ("n", "a", "s")]

        curso = tab[tab["codigo_asignatura"] == r.codigo_asignatura]
        n, a, s = suma(curso)
        gn, ga, _ = suma(tab)
        prior = ga / gn if gn > 0 else 0.8
        pr = curso[curso["prog"] == r.cod_programa] if r.cod_programa is not None else curso.iloc[:0]
        pn, pa, _ = suma(pr)
        suav = (a + M * prior) / (n + M)
        out.append({"n_hist_curso": n, "tasa_hist_curso": a / n if n > 0 else np.nan, "prom_hist_curso": s / n if n > 0 else np.nan,
                    "tasa_hist_curso_suav": suav, "n_hist_curso_prog": pn, "tasa_hist_curso_prog": (pa + M * suav) / (pn + M)})
    return pd.DataFrame(out)


@pytest.mark.parametrize("modo", ["decaimiento", "ventana"])
def test_equals_the_brute_force_definition(modo):
    T, tab = filas_T(), tabla()
    got = DV.estadisticas_recientes(T, tab, modo, vida_media_anios=2.0, ventana_anios=3.0, m=M)
    esp = fuerza_bruta(T, tab, modo)
    for c in esp.columns:
        np.testing.assert_allclose(got[c].to_numpy("float64"), esp[c].to_numpy("float64"), rtol=1e-9, atol=1e-12,
                                   equal_nan=True, err_msg=c)


def test_only_strictly_earlier_periods_count():
    T, tab = filas_T(), tabla()
    base = DV.estadisticas_recientes(T, tab, "decaimiento")
    extra = pd.DataFrame([("X", "P1", "202220", 99, 0, 99.0), ("X", "P1", "202310", 50, 50, 300.0)], columns=tab.columns)
    otro = DV.estadisticas_recientes(T, pd.concat([tab, extra]), "decaimiento")
    pd.testing.assert_frame_equal(base, otro)


def test_a_period_two_years_older_weighs_half_with_a_two_year_half_life():
    tab = pd.DataFrame([("X", "P1", "201710", 10, 5, 40.0), ("X", "P1", "201910", 10, 5, 40.0)], columns=tabla().columns)
    T = pd.DataFrame({"codigo_asignatura": ["X"], "cod_programa": ["P1"], "periodo": ["202110"], "episodio_id": [1]})
    r = DV.estadisticas_recientes(T, tab, "decaimiento", vida_media_anios=2.0)
    assert r["n_hist_curso"].iloc[0] == pytest.approx(10 * 0.5 ** 1 + 10 * 0.5 ** 2)


def test_the_window_drops_what_is_older_than_it():
    tab = pd.DataFrame([("X", "P1", "201510", 10, 10, 70.0), ("X", "P1", "201910", 10, 0, 20.0)], columns=tabla().columns)
    T = pd.DataFrame({"codigo_asignatura": ["X", "X"], "cod_programa": ["P1", "P1"], "periodo": ["202010", "202210"],
                      "episodio_id": [1, 2]})
    r = DV.estadisticas_recientes(T, tab, "ventana", ventana_anios=3.0)
    assert r["n_hist_curso"].tolist() == [10.0, 0.0]               # 2019-10 is 1 y before 2020-10 (in) and exactly 3 y before 2022-10 (out)
    assert r["tasa_hist_curso"].iloc[0] == 0.0 and np.isnan(r["tasa_hist_curso"].iloc[1])
    r2 = DV.estadisticas_recientes(T.assign(periodo=["201810", "202110"]), tab, "ventana", ventana_anios=3.0)
    assert r2["n_hist_curso"].tolist() == [0.0, 10.0]               # 2015-10 is exactly 3 y before 2018-10 (out); 2019-10 is in at 2021-10


def test_a_course_without_history_has_no_rate_and_the_load_mean_uses_the_new_rate():
    T, tab = filas_T(), tabla()
    r = DV.estadisticas_recientes(T, tab, "decaimiento")
    assert np.isnan(r["tasa_hist_curso"].iloc[5]) and r["n_hist_curso"].iloc[5] == 0
    T2 = pd.DataFrame({"codigo_asignatura": ["X", "Y"], "cod_programa": ["P1", "P1"], "periodo": ["202210", "202210"],
                       "episodio_id": [7, 7]})
    r2 = DV.estadisticas_recientes(T2, tab, "decaimiento")
    assert r2["tasa_hist_media_carga"].iloc[0] == pytest.approx(r2["tasa_hist_curso_suav"].mean())
    assert r2["tasa_hist_media_carga"].iloc[0] == r2["tasa_hist_media_carga"].iloc[1]


def test_the_replaced_columns_are_the_course_statistics_of_the_snapshot():
    from pipelines.snapshots import features_t2 as F2
    assert set(DV.COLUMNAS) <= set(F2.FEATURE_COLS_CURSO)
