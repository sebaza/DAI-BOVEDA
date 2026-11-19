"""Ablation of T3 with benefits: adoption criterion, suppression rules, feature sets and the migration 027."""
import re
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from evaluation import diagnostico_beneficios_t3 as DG                    # noqa: E402
from evaluation import run_beneficios_t3 as R                              # noqa: E402
from pipelines.migrate import validate_sql                                 # noqa: E402
from pipelines.snapshots import features_beneficios_t3 as FT               # noqa: E402
from pipelines.snapshots import rules_beneficios_t3 as RT                  # noqa: E402
from pipelines.snapshots import t3_beneficios as TB                        # noqa: E402

SQL = Path(__file__).resolve().parents[2] / "sql" / "core" / "027_snapshot_t3_beneficios.sql"


def d(punto, lo, hi):
    return {"punto": punto, "lo": lo, "hi": hi}


# ---- adoption criterion -----------------------------------------------------------------------------------------------------
def test_adopts_when_valid_interval_excludes_zero_and_test_is_not_worse():
    valid = {"c_12": d(0.01, 0.004, 0.016), "ibs": d(-0.0005, -0.0015, 0.0004)}
    test = {"c_12": d(0.006, -0.002, 0.014), "ibs": d(-0.0003, -0.001, 0.0005)}
    r = R.decidir(valid, test)
    assert r["adopta"] and r["metricas_que_califican_en_valid"] == ["c_12"]


def test_does_not_adopt_if_valid_interval_includes_zero():
    valid = {"c_12": d(0.01, -0.001, 0.02), "ibs": d(-0.001, -0.003, 0.001)}
    test = {"c_12": d(0.01, 0.0, 0.02), "ibs": d(-0.001, -0.003, 0.001)}
    assert not R.decidir(valid, test)["adopta"]


def test_ibs_gain_needs_an_interval_below_zero():
    valid = {"c_12": d(0.0, -0.01, 0.01), "ibs": d(-0.002, -0.003, -0.001)}
    test = {"c_12": d(0.0, -0.01, 0.01), "ibs": d(-0.001, -0.002, 0.0005)}
    assert R.decidir(valid, test)["adopta"]


@pytest.mark.parametrize("test", [
    {"c_12": d(-0.004, -0.009, 0.001), "ibs": d(0.0, -0.001, 0.001)},         # the metric that qualified moves the wrong way
    {"c_12": d(0.004, -0.002, 0.01), "ibs": d(0.002, 0.001, 0.003)},          # the other metric is significantly worse
])
def test_does_not_adopt_if_worse_on_test(test):
    valid = {"c_12": d(0.01, 0.004, 0.016), "ibs": d(-0.0005, -0.0015, 0.0004)}
    assert not R.decidir(valid, test)["adopta"]


# ---- feature sets -----------------------------------------------------------------------------------------------------------
def test_feature_sets_extend_the_official_one_and_exclude_fairness_columns():
    base_num, base_cat = R.conjunto_columnas("acad")
    for bloque in R.BLOQUES:
        num, cat = R.conjunto_columnas(bloque)
        assert set(base_num) < set(num) and cat == base_cat
        assert not ({"banda_decil", "banda_decil_eq", "sexo_equidad", "anio_ben"} & (set(num) | set(cat)))
        R.TD.verificar_sin_fuga(num, cat)


def test_model_names():
    assert R.nombre_modelo("gru", "previo", "acad") == "gru_acad"
    assert R.nombre_modelo("cb", "con_t", "expcap") == "cb_con_t_expcap"


# ---- suppression and group tables --------------------------------------------------------------------------------------------
def test_groups_below_the_thresholds_are_not_published_and_tiny_groups_are_only_counted():
    filas = [{"grupo": "a", "n": 500, "eventos": 100}, {"grupo": "b", "n": 150, "eventos": 3}, {"grupo": "c", "n": 40, "eventos": 20},
             {"grupo": "d", "n": 9, "eventos": 9}]
    vis, resumen = R.suprimir_grupos(filas)
    assert [f["grupo"] for f in vis] == ["a"]
    assert resumen == {"grupos": 4, "visibles": 1, "bajo_umbral": 2, "suprimidos_n_menor_10": 1}


def test_group_table_never_lists_a_group_of_fewer_than_ten():
    rng = np.random.default_rng(0)
    n = 400
    dfr = pd.DataFrame({"tiempo": rng.integers(5, 14, n), "causa": rng.integers(0, 3, n), "seguimiento_max": np.full(n, 15)})
    F = np.sort(rng.random((n, 18)), axis=1)
    g = pd.Series(["grande"] * 390 + ["chico"] * 6 + ["medio"] * 4, index=dfr.index)
    t = R.tabla_grupos(dfr, F, F, 2, g)
    assert [f["grupo"] for f in t["filas"]] == ["grande"]
    assert t["resumen"]["suprimidos_n_menor_10"] == 2 and "chico" not in str(t) and "medio" not in str(t)


# ---- migration 027 and the builder ------------------------------------------------------------------------------------------
def test_migration_027_passes_the_schema_guard_and_matches_the_builder_columns():
    text = SQL.read_text(encoding="utf-8")
    assert validate_sql(text, SQL.name)
    body = re.search(r"snapshot_t3_beneficios \((.*?)PRIMARY KEY", text, re.S).group(1)
    cols = re.findall(r"^\s+(\w+)\s+(?:bigint|smallint|real|double|text)", body, re.M)
    assert cols == TB.COLS_TABLA
    assert "persona_key" not in cols and "benef_sem2" not in text.split("CREATE TABLE")[1] and "total" not in cols


def test_builder_outputs_both_rules_and_the_fairness_band_of_the_cut_year():
    ben = pd.DataFrame([dict(periodo=2018, persona_key="p1", cod_carrera="A", codigo="GG_94_AC", benef_sem1=1.0),
                        dict(periodo=2019, persona_key="p1", cod_carrera="A", codigo="QI_07", benef_sem1=1.0)])
    cortes = pd.DataFrame({"episodio_id": [1], "k": [4], "persona_key": ["p1"], "cod_programa": ["A"], "cod_programa_ingreso": ["A"],
                           "periodo_admision": ["201810"]})
    cortes["periodo_corte"] = [RT.periodo_corte("201810", 4)]
    f = TB.construir_filas(cortes, ben)
    assert sorted(f["regla"]) == ["con_t", "previo"] and list(f.columns) == TB.COLS_TABLA
    por = f.set_index("regla")
    assert por.loc["previo", "banda_decil"] == "<=6" and por.loc["con_t", "banda_decil"] == "7"
    assert (f["banda_decil_eq"] == "7").all()         # descriptive grouping from the cut year, identical for both rules


# ---- diagnostic -------------------------------------------------------------------------------------------------------------
def test_outcome_classes():
    c = DG.clase_resultado([5, 7, 9, 12], [1, 1, 2, 0], [4, 4, 4, 4])
    assert list(c) == ["egreso_siguiente", "egreso_posterior", "salida", "censura"]


def test_diagnostic_compares_year_t_with_the_year_before_and_drops_small_groups():
    rows, anual = [], []
    for i in range(200):
        pk = f"p{i}"
        causa = 2 if i % 4 == 0 else 0
        rows.append(dict(episodio_id=i, k=4, persona_key=pk, cod_programa="A", cod_programa_ingreso="A", periodo_admision="201810",
                         tiempo=6, causa=causa))
        anual.append(dict(persona_key=pk, cod_carrera="A", periodo=2018, fila=1, gratuidad=1, expiro=0, capstone=0, expiro_s1=0,
                          expiro_s2=0, capstone_s1=0, capstone_s2=0))
        if causa == 0:                     # only the stayers have a row in the cut year 2019 (a leak by construction)
            anual.append({**anual[-1], "periodo": 2019})
    res = DG.diagnosticar(pd.DataFrame(rows), pd.DataFrame(anual))
    x = res["por_corte"]["k4_fin_de_anio"]
    assert x["brecha_salida_menos_censura"]["fila"]["anio_t"] == pytest.approx(-1.0)
    assert x["brecha_salida_menos_censura"]["fila"]["anio_t_menos_1"] == pytest.approx(0.0)


def test_flag_distribution_counts_person_year_rows_by_years_since_admission():
    anual = pd.DataFrame([dict(persona_key="p1", cod_carrera="A", periodo=2022, expiro=1, capstone=0),
                          dict(persona_key="p1", cod_carrera="A", periodo=2023, expiro=1, capstone=1),
                          dict(persona_key="p2", cod_carrera="A", periodo=2018, expiro=0, capstone=0)])
    epis = pd.DataFrame([dict(persona_key="p1", cod_programa="A", periodo_admision="201810"),
                         dict(persona_key="p2", cod_programa="A", periodo_admision="201810")])
    d = DG.distribucion_banderas(anual, epis)
    assert d == {"expiro": {"4": 1, "5": 1}, "capstone": {"5": 1}}
