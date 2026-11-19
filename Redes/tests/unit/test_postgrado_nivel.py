"""P77 (DAI, 13-11-2026): postgrado level derived from the standard program name."""
import pytest

from pipelines.normalize.postgrado import NIVELES, nivel_postgrado, ordinal_estado_postgrado


@pytest.mark.parametrize("estandar,banner,nivel", [
    ("MAGÍSTER EN DERECHO", "Magister en Derecho", "magister"),
    ("MAGISTER EN ENSEÑANZA DEL INGLÉS COMO LENGUA EXTRANJERA", None, "magister"),
    ("DOCTORADO EN ANTROPOLOGÍA", "Doc En Antropología", "doctorado"),
    ("DIPLOMADO EN GESTIÓN", None, "diplomado"),
    ("POST-TÍTULO DE ESPECIALISTA EN RADIOLOGÍA", "Post-Tit Espec. en Radiología", "otro"),
    ("POSTÍTULO DE ESPECIALISTA EN MEDICINA FAMILIAR", None, "otro"),
    ("FORMACIÓN DE ESPECIALISTA EN CIRUGÍA GENERAL", None, "otro"),
    ("ESPECIALIDAD EN NEUROCIRUGÍA", None, "otro"),
    (None, "Prog. Ficticio Post. Ant.", "sin_nombre"),
    ("", "", "sin_nombre"),
    ("   ", None, "sin_nombre"),
])
def test_level_is_derived_from_the_standard_name(estandar, banner, nivel):
    assert nivel_postgrado(estandar, banner) == nivel


def test_without_a_standard_name_the_banner_name_is_used_only_for_unambiguous_prefixes():
    assert nivel_postgrado(None, "Magister en Arquitectura") == "magister"
    assert nivel_postgrado(None, "Doctor Cs. Mención Matemática") == "doctorado"
    assert nivel_postgrado(None, "Diplomado en X") == "diplomado"
    assert nivel_postgrado(None, "Mg Gestión Integral Proyectos") == "sin_nombre"       # abbreviation: not derivable


def test_levels_are_the_declared_ones():
    assert set(NIVELES) == {"magister", "doctorado", "diplomado", "otro", "sin_nombre"}


@pytest.mark.parametrize("periodo,ordinal", [
    ("202650", 2026 * 2), ("202660", 2026 * 2 + 1), ("202610", 2026 * 2), ("202620", 2026 * 2 + 1),
    ("202615", None), ("202699", None), (None, None), ("2026", None),
])
def test_p79_postgrado_period_to_calendar_semester(periodo, ordinal):
    """50 / 60 = first / second semester of postgrado; 10 / 20 (also present in the source) the same semesters."""
    assert ordinal_estado_postgrado(periodo) == ordinal
