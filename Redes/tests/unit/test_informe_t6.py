"""Report helpers of T6 (``tools/informe_t6.py``): small counts are never printed, a group table prints only what the
evaluation reported, an incidence without enough units at risk is a dash. No database, no JSON artefact."""
import importlib.util
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / "tools" / "informe_t6.py"
spec = importlib.util.spec_from_file_location("informe_t6", RUTA)
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)


def ic(p, lo, hi):
    return {"punto": p, "lo": lo, "hi": hi}


def test_counts_between_one_and_nine_are_never_printed():
    assert I.n_pub(1) == "< 10" and I.n_pub(9) == "< 10"
    assert I.n_pub(0) == "0" and I.n_pub(10) == "10" and I.n_pub(56789) == "56.789"


def test_numbers_use_the_spanish_decimal_comma_and_missing_values_are_dashes():
    assert I.fmt(0.1567) == "0,157" and I.fmt(float("nan")) == "—"
    assert I.pct(0.0157) == "1,6 %"
    assert I.pct_ic(ic(0.02, 0.01, 0.03)) == "2,0 % [1,0; 3,0]"


def test_an_incidence_with_fewer_than_100_units_at_risk_is_a_dash():
    inc = {"2": ic(0.02, 0.01, 0.03), "4": ic(0.03, 0.02, 0.05)}
    assert I.celda_incidencia(inc, {"2": 500, "4": 99}, "2") == "2,0 % [1,0; 3,0]"
    assert I.celda_incidencia(inc, {"2": 500, "4": 99}, "4") == "—"
    assert I.celda_incidencia(inc, None, "4") == "3,0 % [2,0; 5,0]"


def _t(grupos):
    filas = [{"grupo": g, "n": 150, "eventos": 12, "incidencia": {"2": ic(0.05, 0.02, 0.08), "4": ic(0.07, 0.03, 0.1)},
              "en_riesgo": {"2": 150, "4": 120}, "nombre": "Programa de ejemplo"} for g in grupos]
    return {"filas": filas, "resumen": {"grupos_total": 9, "grupos_reportables": len(filas), "grupos_suprimidos": 9 - len(filas),
                                        "filas_total": 1000, "filas_en_reportables": 150 * len(filas), "eventos_total": 60,
                                        "eventos_en_reportables": 12 * len(filas), "n_min": 100, "eventos_min": 10}}


def test_group_table_prints_only_the_reported_groups_and_counts_the_suppressed_ones():
    texto = "\n".join(I.tabla_incidencia({"programa": _t(["P1", "P2"])}["programa"], "programa"))
    assert "P1 · Programa de ejemplo" in texto and "P2" in texto and "P3" not in texto
    assert "7 grupos suprimidos" in texto
    vacio = "\n".join(I.tabla_incidencia(_t([]), "programa"))
    assert "No hay grupos" in vacio
    texto_f = "\n".join(I.tabla_incidencia(_t(["Facultad de Ciencias"]), "facultad"))
    assert "| Facultad de Ciencias |" in texto_f      # the NAME, never a code (stage B)


def test_the_funnel_table_keeps_its_identity():
    e = {"poblacion": 100, "sin_egreso": 60, "egresados": 40, "egreso_antes_de_la_fuente": 0, "postgrado_previo_antes": 0,
         "postgrado_previo_durante": 4, "sin_seguimiento": 6, "elegibles": 30, "eventos": 3, "cohortes_anteriores_excluidas": 10}
    texto = "\n".join(I.tabla_embudo(e))
    assert "30" in texto and "< 10" in texto                 # 4 prior enrollments are < 10 and never printed exactly
    assert "4" not in texto.replace("40", "").replace("< 10", "")


def test_a_rate_that_would_reveal_a_count_under_ten_is_a_dash():
    assert I.tasa_pub(0, 500) == "0,0 %" and I.tasa_pub(9, 500) == "—" and I.tasa_pub(10, 500) == "2,0 %"
    assert I.tasa_pub(20, 0) == "—"


def test_calibration_table_never_prints_a_bin_with_one_to_nine_events():
    ev = {"seleccion": {"conservado": "cox_perfil"},
          "calibracion_test": {"cox_perfil": [{"grupo": 1, "n": 100, "riesgo_medio": 0.02, "tasa_observada": 0.12},
                                              {"grupo": 2, "n": 900, "riesgo_medio": 0.003, "tasa_observada": 0.004}],
                               "baseline_programa": [{"grupo": 1, "n": 1000, "riesgo_medio": 0.01, "tasa_observada": 0.016}]}}
    texto = "\n".join(I.tabla_calibracion(ev))
    assert "12,00 %" in texto and "1,60 %" in texto             # 12 and 16 events: shown
    assert texto.count("—") == 1                                # 900 * 0.004 = 3.6 -> 4 events: a dash


def test_no_negative_zero_in_the_intervals():
    assert I.con_ic({"punto": -0.0001, "lo": -0.02, "hi": 0.01}) == "0.000 [-0.020; 0.010]"
