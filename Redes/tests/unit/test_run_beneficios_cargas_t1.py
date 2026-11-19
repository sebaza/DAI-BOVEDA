"""Helpers of the T1 point-in-time benefits re-evaluation (no models are trained here)."""
import numpy as np
import pandas as pd
import pytest

from evaluation import diagnostico_beneficios_cargas as DC
from evaluation import run_beneficios_cargas_t1 as R
from pipelines.snapshots import features_beneficios as FB


def snap():
    return pd.DataFrame({
        "episodio_id": [1, 2, 3, 4, 5, 6], "k": [1, 1, 1, 1, 2, 2], "persona_key": list("abcdef"),
        "cod_programa": ["8213"] * 6,
        "periodo_corte": ["202310", "202410", "202510", "202610", "202410", "202420"],
        "estado_muestra": ["observada", "observada", "observada", "censurada", "observada", "observada"],
        "continua": [True, False, True, pd.NA, True, False]})


def test_evaluation_rows_are_the_observed_rows_with_history_at_the_cut():
    e = R.filas_de_evaluacion(snap(), 1)
    assert list(e["episodio_id"]) == [2, 3] and list(e["anio_corte"]) == [2024, 2025]
    assert list(e["y"]) == [1, 0]                                    # y = does not continue
    assert list(R.filas_de_evaluacion(snap(), 2)["episodio_id"]) == [5, 6]


def test_substituting_the_benefits_keeps_rows_and_every_other_column():
    e = R.filas_de_evaluacion(snap(), 1)
    for c in FB.COLS_BENEFICIOS:
        e[c] = 1.0 if c != "banda_decil" else "<=6"
    pit = pd.DataFrame({"episodio_id": [3, 2], "k": [1, 1], **{c: 0.0 for c in FB.COLS_BENEFICIOS}})
    pit["banda_decil"] = "desconocida"
    out = R.sustituir_beneficios(e, pit)
    assert list(out["episodio_id"]) == [2, 3] and list(out.columns) == list(e.columns)
    assert (out["tiene_gratuidad"] == 0).all() and (out["banda_decil"] == "desconocida").all()
    assert list(out["persona_key"]) == list(e["persona_key"])


def _ev(lo, punto):
    return {"ap": {"punto": punto, "lo": lo, "hi": punto + 0.03}}


def test_d93_needs_an_interval_above_zero_and_a_positive_point_in_every_year():
    ev = {"cb_ben_pit__vs__cb_acad": _ev(0.01, 0.03)}
    por = {"2024": {"cb_ben_pit__vs__cb_acad": _ev(-0.02, 0.02)}, "2025": {"cb_ben_pit__vs__cb_acad": _ev(-0.01, 0.04)}}
    d = R.decision_d93(ev, por, "cb")
    assert d["ic_sobre_cero"] and d["positivo_en_cada_anio"] and d["elegible"]
    por["2025"]["cb_ben_pit__vs__cb_acad"] = _ev(-0.05, -0.01)
    d = R.decision_d93(ev, por, "cb")
    assert d["ic_sobre_cero"] and not d["positivo_en_cada_anio"] and not d["elegible"]
    ev["cb_ben_pit__vs__cb_acad"] = _ev(-0.01, 0.03)
    assert not R.decision_d93(ev, {"2024": por["2024"]}, "cb")["elegible"]


def test_group_table_suppresses_small_groups_and_adds_the_official_ap():
    rng = np.random.default_rng(0)
    n = 400
    grupo = np.array(["A"] * 250 + ["B"] * 100 + ["C"] * 50)
    y = (rng.random(n) < 0.2).astype(int)
    p1, p2 = rng.random(n), rng.random(n)
    idx = [rng.integers(0, n, n) for _ in range(20)]
    t = R.agrupar_con_oficial(grupo, y, p1, p2, idx)
    listados = {f["grupo"] for f in t["filas"]}
    assert "C" not in listados and listados <= {"A", "B"} and "A" in listados
    assert all("ap_oficial" in f for f in t["filas"])
    assert t["resumen"]["grupos_suprimidos"] >= 1


# ---- diagnostic helpers
def test_family_keys_cover_the_four_families_and_the_other_kinds():
    assert DC.familia("GG_94AB") == "gratuidad" and DC.familia("GU_00AC") == "gratuidad"
    assert DC.familia("C_1_AC") == "credito" and DC.familia("BG_01") == "beca_estatal"
    assert DC.familia("PI_03") == "merito" and DC.familia("PC_01") == "capstone"
    assert DC.familia("ZZ_99X").startswith("otro:")


def _h(persona, codigo, first, last, final, anio=2024, carrera="8213"):
    return {"periodo": anio, "persona_key": persona, "cod_carrera": carrera, "codigo": codigo, "cobertura": "AC",
            "first_ts": first, "last_ts": last, "n_loads": 2, "presente_ultima_carga": final, "sem1_primera": 1.0,
            "sem2_primera": 0.0, "sem1_ultima": 1.0, "sem2_ultima": 0.0}


def test_retired_rows_are_classified_by_what_the_person_keeps():
    cargas = pd.DataFrame([
        _h("p1", "GG_94AB", 1, 5, False), _h("p1", "GG_94AC", 8, 20, True),          # replaced after the retirement
        _h("p2", "GG_94AB", 1, 5, False), _h("p2", "GG_94AC", 2, 20, True),          # the other already existed
        _h("p3", "GG_94AB", 1, 5, False), _h("p3", "C_1_AC", 1, 20, True),           # only another family left
        _h("p4", "GG_94AB", 1, 5, False),                                            # nothing left
        _h("p5", "GG_94AB", 1, 20, True)])                                           # never retired
    r = DC.clasificar_retiradas(cargas, anios=(2024,)).set_index("persona_key")["clase"].to_dict()
    assert r == {"p1": "reemplazo_misma_familia", "p2": "misma_familia_ya_existia", "p3": "otra_familia", "p4": "sin_filas"}


def test_rows_at_the_cut_count_late_and_retired_rows():
    import datetime as dt

    def ms(m, d):
        return int(dt.datetime(2024, m, d, 12, tzinfo=dt.timezone.utc).timestamp() * 1000)

    cal = {2024: np.array([ms(4, 4), ms(7, 1), ms(9, 1), ms(12, 9)])}
    cargas = pd.DataFrame([_h("a", "GG_94AB", ms(4, 4), ms(12, 9), True), _h("b", "GG_94AB", ms(9, 1), ms(12, 9), True),
                           _h("c", "GG_94AB", ms(4, 4), ms(7, 1), False)])
    r = {x["corte"]: x for x in DC.filas_por_corte(cargas, cal, anios=(2024,))}["fin_primer_semestre"]
    assert (r["filas_vista_final"], r["filas_visibles_al_corte"], r["finales_aun_no_cargadas"], r["visibles_retiradas_despues"]) == (2, 2, 1, 1)
