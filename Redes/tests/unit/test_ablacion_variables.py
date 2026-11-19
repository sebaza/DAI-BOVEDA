"""Ablation of the new variables: D114 decision helpers and the loader merge. No database."""
import pytest

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from evaluation import ablacion_variables as AB      # noqa: E402
from models import vars_nuevas_data as VD            # noqa: E402
from pipelines.snapshots import features_variables as FV   # noqa: E402


def d(punto, lo, hi):
    return {"punto": punto, "lo": lo, "hi": hi}


def test_ap_candidate_wins_only_if_the_paired_interval_is_above_zero():
    assert AB.decidir_ap(d(0.02, 0.005, 0.04)) is True
    assert AB.decidir_ap(d(0.02, -0.001, 0.04)) is False          # a tie keeps the simpler (kept) model
    assert AB.decidir_ap(d(-0.02, -0.04, -0.01)) is False
    assert AB.decidir_ap(None) is False
    assert AB.decidir_ap(d(0.02, float("nan"), 0.04)) is False


def test_t3_candidate_needs_c12_above_zero_and_an_ibs_that_is_not_worse():
    assert AB.decidir_t3(d(0.01, 0.002, 0.02), d(-0.001, -0.002, 0.0005)) is True
    assert AB.decidir_t3(d(0.01, 0.002, 0.02), d(0.002, 0.001, 0.003)) is False      # IBS worse with an interval above zero
    assert AB.decidir_t3(d(0.01, -0.002, 0.02), d(-0.001, -0.002, 0.0)) is False    # C(12) not separated from zero


def test_the_best_valid_point_among_the_winners_is_chosen():
    cand = [{"nombre": "a", "gana": True, "valid_punto": 0.31}, {"nombre": "b", "gana": True, "valid_punto": 0.35},
            {"nombre": "c", "gana": False, "valid_punto": 0.50}]
    assert AB.elegir(cand)["nombre"] == "b"
    assert AB.elegir([{"nombre": "c", "gana": False, "valid_punto": 0.5}]) is None


def test_merge_keeps_rows_and_order_and_casts_booleans():
    snap = pd.DataFrame({"episodio_id": [2, 1, 1], "k": [2, 4, 2], "x": [1, 2, 3]})
    v = pd.DataFrame({"episodio_id": [1, 1, 2], "k": [2, 4, 2]})
    for c in FV.VARIABLES_NUEVAS:
        v[c] = 1.0
    for c in FV.VARS_BOOL:
        v[c] = True
    u = VD.unir(snap, v)
    assert list(u["episodio_id"]) == [2, 1, 1] and list(u["k"]) == [2, 4, 2]
    assert u["alc_pendiente_gt4"].dtype == "float64" and (u["alc_pendiente_gt4"] == 1.0).all()


def test_blocks_only_name_known_columns_and_never_a_forbidden_one():
    for b, cols in VD.BLOQUES.items():
        assert set(cols) <= set(FV.VARIABLES_NUEVAS), b
        VD.verificar_sin_fuga_nuevas(cols)
    with pytest.raises(ValueError):
        VD.verificar_sin_fuga_nuevas(["cohorte_anio"])


def test_columns_missing_in_train_are_dropped():
    tr = pd.DataFrame({"a": [1.0, np.nan], "b": [np.nan, np.nan]})
    assert VD.columnas_validas(tr, ["a", "b", "c"]) == ["a"]


def test_complexity_order_is_family_then_block():
    assert AB.complejidad("lr_agg+t4") < AB.complejidad("lr_agg+todo") < AB.complejidad("cb_agg+t4") < AB.complejidad("gru_adm+reg_alc")
    assert AB.complejidad("lr_agg+reg_alc") < AB.complejidad("lr_agg+todo")


def test_ties_keep_the_simpler_winner():
    ganadores = ["lr_agg+todo", "lr_agg+t4", "cb_agg+todo"]
    # nobody is separated from the best by the paired interval: the simplest winner stays
    sin_separar = lambda a, b: {"punto": 0.01, "lo": -0.01, "hi": 0.03}      # noqa: E731
    assert AB.refinar_por_simplicidad("lr_agg+todo", ganadores, sin_separar) == "lr_agg+t4"
    # the best is separated from the simpler ones: it stays
    separa = lambda a, b: {"punto": 0.05, "lo": 0.01, "hi": 0.09}            # noqa: E731
    assert AB.refinar_por_simplicidad("lr_agg+todo", ganadores, separa) == "lr_agg+todo"
