"""View "Lo que pasó": entry profile and first-semester failures versus continuing (T1, k = 1)."""
import numpy as np
import pandas as pd
import pytest

from evaluation import vista_permanencia as VP


def _t1(n=600, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "via_clase": rng.choice(["regular", "especial", "otros_cambio"], size=n, p=[0.7, 0.2, 0.1]),
        "tipo_colegio": rng.choice(["H1", "T1", "T2", None], size=n, p=[0.6, 0.2, 0.1, 0.1]),
        "pct_ponderado": np.where(rng.random(n) < 0.1, np.nan, rng.uniform(300, 900, size=n)),
        "reprobados": rng.integers(0, 6, size=n),
        "y": rng.binomial(1, 0.25, size=n), "p": rng.uniform(0.05, 0.5, size=n)})


def _dim(b, nombre):
    return next((x for x in b["dimensiones"] if x["dimension"] == nombre), None)


def test_perfil_has_three_dimensions_and_quintiles_sum_to_n():
    d = VP.agregar_quintiles(_t1())
    b = VP.bloque_perfil(d)
    assert b["nota_asociacion"] is True and b["n"] == len(d)
    assert [x["dimension"] for x in b["dimensiones"]] == ["via", "colegio", "puntaje"]
    for dim in b["dimensiones"]:
        assert sum(f["n"] for f in dim["filas"]) == len(d)
        assert all(0 <= f["pct_siguieron"] <= 1 and 0 <= f["pct_esperado"] <= 1 for f in dim["filas"])
    q = [f for f in _dim(b, "puntaje")["filas"] if f["grupo"].startswith("q")]
    assert [f["grupo"] for f in q] == ["q1", "q2", "q3", "q4", "q5"]


def test_perfil_publishes_small_groups_as_their_own_rows_with_exact_counts():
    d = _t1(300)
    d.loc[d.index[:4], "via_clase"] = "rara1"                  # 4 students
    d.loc[d.index[4:9], "via_clase"] = "otra2"                 # 5 more
    via = _dim(VP.bloque_perfil(d), "via")
    por = {f["grupo"]: f for f in via["filas"]}
    assert por["rara1"]["n"] == 4 and por["otra2"]["n"] == 5 and sum(f["n"] for f in via["filas"]) == 300
    assert "otros" not in por                                  # no size-based merge; "otros_cambio" is a class of entry route


def test_no_size_based_otros_row_anywhere():
    d = _t1(60)
    d.loc[d.index[:2], "via_clase"] = "rara"
    b = VP.bloque_perfil(VP.agregar_quintiles(d))
    for dim in b["dimensiones"]:
        assert all(f["grupo"] != "otros" for f in dim["filas"])
    assert {f["grupo"] for f in _dim(b, "via")["filas"]} >= {"regular", "especial", "otros_cambio", "rara"}


def test_perfil_keeps_a_group_with_few_continuers_and_its_pct_carries_n():
    d = _t1(400)
    g = d.index[d["via_clase"] == "regular"]
    d.loc[g, "y"] = 1
    d.loc[g[:3], "y"] = 0                                        # 3 continued among many
    via = _dim(VP.bloque_perfil(d), "via")
    regular = next(f for f in via["filas"] if f["grupo"] == "regular")
    assert regular["n"] == len(g) and regular["pct_siguieron"] == pytest.approx(3 / len(g))


def test_perfil_with_a_single_group_is_published():
    d = _t1(40)
    d["via_clase"] = "regular"
    via = _dim(VP.bloque_perfil(d), "via")
    assert [f["grupo"] for f in via["filas"]] == ["regular"] and via["filas"][0]["n"] == 40


def test_primer_semestre_buckets_are_0_1_2_3plus():
    b = VP.bloque_primer_semestre(_t1())
    assert [f["reprobaciones"] for f in b["filas"]] == ["0", "1", "2", "3+"]
    assert sum(f["n"] for f in b["filas"]) == b["n"]


def test_small_population_is_published_and_empty_is_not():
    assert VP.bloque_perfil(_t1(9))["n"] == 9 and VP.bloque_primer_semestre(_t1(9))["n"] == 9
    assert VP.bloque_perfil(_t1(0)) is None and VP.bloque_primer_semestre(_t1(0)) is None
