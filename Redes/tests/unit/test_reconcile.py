"""Reconciliation bookkeeping: a mismatch is recorded with its explanation, never forced to pass."""
from pipelines import reconcile as R


def rec():
    return R.Reconciler(dev=None)


def test_equal_values_pass():
    c = rec().add("x", 10, 10)
    assert c.ok and c.explicacion == "coincide"


def test_mismatch_is_recorded_as_failure_with_a_default_explanation():
    r = rec()
    c = r.add("x", 10, 11)
    assert not c.ok and c.explicacion == "sin explicación registrada"
    assert r.checks == [c]


def test_mismatch_uses_the_explanation_given_by_the_caller():
    assert rec().add("x", 10, 11, why="orden distinto").explicacion == "orden distinto"


def test_informational_check_can_be_forced_ok_explicitly():
    c = rec().add("x", "informativo", 5, ok=True, why="solo informativo")
    assert c.ok and c.explicacion == "solo informativo"


def test_numbers_are_formatted_with_dot_thousands():
    c = rec().add("x", 735932, 735932)
    assert c.esperado == c.obtenido == "735.932"


def test_render_lists_every_check_and_marks_failures():
    r = rec()
    r.add("a", 1, 1)
    r.add("b", 1, 2, why="causa")
    text = R.render(r.checks)
    assert "a" in text and "NO" in text and "causa" in text
    md = R.render_markdown(r.checks)
    assert md.count("\n") == 3 and "**no**" in md


def test_rut_like_pattern_matches_ruts_and_not_hex_keys():
    import re

    pat = re.compile(R.RUT_LIKE)
    assert pat.match("98765432-1") and pat.match("987654321") and pat.match("9876543K")
    assert not pat.match("202510") and not pat.match("a" * 64)
    assert re.compile(R.HEX64).match("a" * 64) and not re.compile(R.HEX64).match("A" * 64)
