import numpy as np
import pandas as pd

from evaluation import seleccion_valid_t45 as SV


def test_network_kept_only_when_valid_interval_is_above_zero():
    assert SV.decidir_d114("gru_agg", "cb_agg", {"punto": 0.03, "lo": 0.001, "hi": 0.06}) == "gru_agg"
    assert SV.decidir_d114("gru_agg", "cb_agg", {"punto": 0.03, "lo": -0.001, "hi": 0.06}) == "cb_agg"
    assert SV.decidir_d114(None, "lr_agg", None) == "lr_agg"


def test_evaluar_selects_on_valid_with_a_paired_grouped_bootstrap():
    rng = np.random.default_rng(0)
    n = 600
    y = rng.random(n) < 0.15
    valid = pd.DataFrame({"persona_key": [f"p{i // 2}" for i in range(n)], "y4": y, "y5": y, "y5e": y})
    ruido = rng.random(n)
    fuerte = y + 0.2 * ruido                       # near-perfect ranking
    debil = y * 0.2 + ruido                         # weak ranking
    base = np.full(n, 0.15)
    preds = {t: {"lr_adm": debil, "lr_agg": debil, "cb_adm": debil, "cb_agg": debil, "gru_adm": fuerte,
                 "gru_agg": debil, "baseline_tasa": base} for t in ("T4", "T5", "T5E")}
    r = SV.evaluar(valid, preds, n_boot=200)
    assert r["T5"]["red"] == "gru_adm" and r["T5"]["conservado_d114"] == "gru_adm"
    assert r["T5"]["delta_red_vs_clasico_valid"]["lo"] > 0
    preds_empate = {t: {**p, "gru_adm": debil} for t, p in preds.items()}
    assert SV.evaluar(valid, preds_empate, n_boot=200)["T4"]["conservado_d114"] in ("lr_adm", "lr_agg", "cb_adm", "cb_agg")
