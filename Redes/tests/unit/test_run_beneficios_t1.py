"""Selection rule and helpers of the T1 benefit ablation (no models are trained here)."""
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")

from evaluation import run_beneficios_t1 as RB   # noqa: E402


def d(lo, hi=None):
    return {"ap": {"punto": (lo + (hi if hi is not None else lo + 0.02)) / 2, "lo": lo, "hi": hi if hi is not None else lo + 0.02}}


AP = {"lr_acad": 0.30, "cb_acad": 0.36, "lr_ben": 0.33, "cb_ben": 0.40, "lr_ben_perd": 0.34, "cb_ben_perd": 0.43}


def test_a_benefit_model_is_eligible_only_if_its_paired_gain_on_valid_excludes_zero():
    ev = {"cb_ben__vs__cb_acad": d(0.01), "lr_ben__vs__lr_acad": d(-0.01, 0.03)}
    el = RB.elegibles(2, list(AP)[:4], ev)
    assert set(el) == {"lr_acad", "cb_acad", "cb_ben"}
    assert RB.elegir(AP, el) == "cb_ben"


def test_no_benefit_model_is_eligible_at_k1_because_the_cut_is_mid_year():
    ev = {"cb_ben__vs__cb_acad": d(0.05), "lr_ben__vs__lr_acad": d(0.05)}
    el = RB.elegibles(1, list(AP)[:4], ev)
    assert set(el) == {"lr_acad", "cb_acad"} and RB.elegir(AP, el) == "cb_acad"


def test_the_loss_set_needs_its_own_gain_over_the_benefit_set_and_the_benefit_set_itself():
    ev = {"cb_ben__vs__cb_acad": d(0.01), "lr_ben__vs__lr_acad": d(0.01),
          "cb_ben_perd__vs__cb_ben": d(0.005), "lr_ben_perd__vs__lr_ben": d(-0.02, 0.01)}
    el = RB.elegibles(4, list(AP), ev)
    assert "cb_ben_perd" in el and "lr_ben_perd" not in el and RB.elegir(AP, el) == "cb_ben_perd"
    ev["cb_ben__vs__cb_acad"] = d(-0.01, 0.02)
    el = RB.elegibles(4, list(AP), ev)
    assert "cb_ben" not in el and "cb_ben_perd" not in el


def test_leavers_of_the_admission_year_are_flagged_only_for_k1_and_a_first_semester_admission():
    snap = pd.DataFrame({"episodio_id": [1, 2, 3, 4], "k": [1, 1, 1, 2],
                         "periodo_admision": ["202010", "202010", "202020", "202010"]})
    sem = pd.DataFrame({"episodio_id": [1, 1, 2, 2, 3, 3, 4, 4], "j": [1, 2] * 4,
                        "matriculado": [True, True, True, False, True, False, True, False]})
    flag = RB.sale_en_el_anio(snap, sem)
    assert flag.tolist() == [False, True, False, False]


def test_importance_table_marks_benefit_variables_and_keeps_only_aggregates():
    t = RB.tabla_importancia(["a", "tiene_gratuidad", "b", "monto_sem1"], np.array([5.0, 3.0, 1.0, 1.0]),
                             np.array([0.1, 0.3, 0.05, 0.02]), top=3)
    assert [r["variable"] for r in t["top"]] == ["a", "tiene_gratuidad", "b"]
    assert {r["variable"] for r in t["beneficios"]} == {"tiene_gratuidad", "monto_sem1"}
    assert all(set(r) <= {"variable", "importancia", "importancia_pct", "shap_medio_abs", "rango"} for r in t["top"])
