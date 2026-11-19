"""Report helpers of T4/T5 (``tools/informe_t45.py``): small counts are never printed, decimals follow the Spanish
convention and the group tables only print what the evaluation reported. No database, no JSON artefact."""
import importlib.util
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / "tools" / "informe_t45.py"
spec = importlib.util.spec_from_file_location("informe_t45", RUTA)
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)


def test_counts_between_one_and_nine_are_never_printed():
    assert I.n_pub(1) == "< 10" and I.n_pub(9) == "< 10"
    assert I.n_pub(0) == "0" and I.n_pub(10) == "10" and I.n_pub(56789) == "56.789"


def test_numbers_use_the_spanish_decimal_comma_and_missing_values_are_dashes():
    assert I.fmt(0.1567) == "0,157" and I.fmt(0.05, 2, True) == "+0,05" and I.fmt(float("nan")) == "—"
    assert I.pct(0.1567) == "15,7 %"
    assert I.con_ic({"punto": 0.5, "lo": 0.4, "hi": 0.6}) == "0.500 [0.400; 0.600]"


def _grupo(g, n=150, ev=15):
    ic = {"punto": 0.1, "lo": 0.05, "hi": 0.15}
    return {"grupo": g, "n": n, "eventos": ev, "ap": 0.3, "roc_auc": 0.7, "tasa_observada": ic, "riesgo_medio": ic,
            "brecha": ic, "brecha_base": ic, "riesgo_medio_base": ic, "nombre": "Programa de ejemplo"}


def test_group_table_prints_only_the_reported_groups_and_labels_the_level():
    g = {"programa": {"filas": [_grupo("P1"), _grupo("P2")], "resumen": {}}, "facultad": {"filas": [_grupo("Facultad de Ciencias")], "resumen": {}}}
    texto = "\n".join(I.tabla_grupos(g, "programa"))
    assert "P1 · Programa de ejemplo" in texto and "P2" in texto and "P3" not in texto
    texto_f = "\n".join(I.tabla_grupos(g, "facultad"))
    assert "| Facultad de Ciencias |" in texto_f and "Facultad 8" not in texto_f      # a faculty is labelled by its NAME (stage B)
    vacio = {"programa": {"filas": [], "resumen": {}}}
    assert "No hay grupos" in "\n".join(I.tabla_grupos(vacio, "programa"))
