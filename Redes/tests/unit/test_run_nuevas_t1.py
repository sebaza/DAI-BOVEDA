"""D114 decision helper of the T1 ablation of the new variables (no models are trained here)."""
import pytest

from evaluation import run_nuevas_t1 as R


def ev(ap, deltas):
    """``ap``: valid AP per model; ``deltas``: {candidate: (punto, lo, hi)} against the kept model ``cb_acad``."""
    out = {m: {"ap": {"punto": v, "lo": v - 0.03, "hi": v + 0.03}} for m, v in ap.items()}
    for c, (p, lo, hi) in deltas.items():
        out[f"{c}__vs__cb_acad"] = {"ap": {"punto": p, "lo": lo, "hi": hi}}
    return out


def test_model_names():
    assert R.nombre_modelo("cb", R.GRUPO_ACAD) == "cb_acad" and R.nombre_modelo("lr", R.GRUPO_NUEVAS) == "lr_nuevas"
    assert R.nombre_modelo("cb", "pre_entry+academico+malla") == "cb_nuevas_malla"


def test_the_kept_model_stays_unless_the_paired_interval_excludes_zero_in_favour_of_the_candidate():
    e = ev({"cb_acad": 0.30, "cb_nuevas": 0.33, "lr_nuevas": 0.31}, {"cb_nuevas": (0.03, -0.001, 0.06), "lr_nuevas": (0.01, -0.02, 0.04)})
    d = R.decision_d114(e, "cb_acad", R.PRIMARIOS)
    assert d["decision"] == "se_conserva" and d["modelo"] == "cb_acad"
    e = ev({"cb_acad": 0.30, "cb_nuevas": 0.33, "lr_nuevas": 0.31}, {"cb_nuevas": (0.03, 0.005, 0.06), "lr_nuevas": (0.01, -0.02, 0.04)})
    d = R.decision_d114(e, "cb_acad", R.PRIMARIOS)
    assert d["decision"] == "reemplaza" and d["modelo"] == "cb_nuevas"


def test_an_interval_below_zero_never_replaces_and_an_ap_tie_goes_to_the_simpler_family():
    e = ev({"cb_acad": 0.30, "cb_nuevas": 0.28, "lr_nuevas": 0.28}, {"cb_nuevas": (-0.02, -0.05, 0.0), "lr_nuevas": (-0.02, -0.04, 0.0)})
    assert R.decision_d114(e, "cb_acad", R.PRIMARIOS)["decision"] == "se_conserva"
    e = ev({"cb_acad": 0.30, "cb_nuevas": 0.35, "lr_nuevas": 0.35}, {"cb_nuevas": (0.05, 0.01, 0.09), "lr_nuevas": (0.05, 0.01, 0.09)})
    assert R.decision_d114(e, "cb_acad", R.PRIMARIOS)["modelo"] == "lr_nuevas"


def test_t2_decision_uses_the_paired_delta_of_the_cluster_bootstrap():
    from evaluation import run_nuevas_t2 as R2

    def e(ap, delta):
        return {"cb_c": {"ap": {"punto": 0.49, "lo": 0.48, "hi": 0.5}}, "cb_c_nuevas": {"ap": {"punto": ap, "lo": 0, "hi": 1}},
                "lr_c_nuevas": {"ap": {"punto": 0.45, "lo": 0, "hi": 1}},
                "__delta__cb_c_nuevas__cb_c": {"ap": {"punto": delta[0], "lo": delta[1], "hi": delta[2]}},
                "__delta__lr_c_nuevas__cb_c": {"ap": {"punto": -0.04, "lo": -0.05, "hi": -0.03}}}
    assert R2.decision_d114(e(0.50, (0.01, -0.002, 0.02)), "cb_c", R2.PRIMARIOS)["decision"] == "se_conserva"
    d = R2.decision_d114(e(0.51, (0.02, 0.01, 0.03)), "cb_c", R2.PRIMARIOS)
    assert d["decision"] == "reemplaza" and d["modelo"] == "cb_c_nuevas"


def test_t2_merge_adds_the_candidates_and_refuses_when_the_kept_model_does_not_reproduce():
    from evaluation import run_nuevas_t2 as R2

    def m(ap):
        return {"ap": {"punto": ap, "lo": ap - 0.01, "hi": ap + 0.01}}

    def bloque(extra):
        d = {"cb_c": m(0.5), "lr_c": m(0.47), **extra}
        return d
    prev = {"evaluacion": {"pares": [["cb_c", "lr_c"]], **{sp: bloque({}) for sp in R2.SPLITS_EVAL}, "calibracion_test": {"cb_c": [1]}},
            "info": {"cb_c": {}}, "tiempos_s": {"cb_c": 1.0}}
    nuevo = {"evaluacion": {"pares": [["cb_c_nuevas", "cb_c"], ["lr_c_nuevas", "lr_c"], ["cb_c", "lr_c"]],
                            **{sp: bloque({"cb_c_nuevas": m(0.51), "lr_c_nuevas": m(0.48), "__delta__cb_c_nuevas__cb_c": m(0.01),
                                           "__delta__lr_c_nuevas__lr_c": m(0.01), "__delta__cb_c__lr_c": m(0.03)})
                               for sp in R2.SPLITS_EVAL}, "d114": {"decision": "reemplaza"}},
             "info": {"cb_c_nuevas": {"x": 1}, "lr_c_nuevas": {"x": 2}}, "tiempos_s": {"cb_c_nuevas": 5.0}, "snapshot_hash": "h"}
    out = R2.fusionar_resultados(prev, nuevo, ("cb_c_nuevas", "lr_c_nuevas"), {"calibracion_test": {"cb_c_nuevas": [2]}})
    assert out["evaluacion"]["valid"]["cb_c_nuevas"]["ap"]["punto"] == 0.51
    assert "__delta__cb_c_nuevas__cb_c" in out["evaluacion"]["test"] and "__delta__cb_c__lr_c" not in out["evaluacion"]["test"]
    assert out["evaluacion"]["calibracion_test"] == {"cb_c": [1], "cb_c_nuevas": [2]}
    assert out["info"]["lr_c_nuevas"] == {"x": 2} and out["tiempos_s"]["cb_c_nuevas"] == 5.0 and "cb_c_nuevas" not in prev["evaluacion"]["valid"]
    nuevo["evaluacion"]["valid"]["cb_c"] = m(0.49)
    with pytest.raises(RuntimeError):
        R2.fusionar_resultados(prev, nuevo, ("cb_c_nuevas",), {})
