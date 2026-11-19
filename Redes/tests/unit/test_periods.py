import pytest

from pipelines.normalize.periods import parse_periodo, tipo_periodo


@pytest.mark.parametrize(
    "periodo,tipo",
    [
        ("202410", "regular_1"),
        ("202420", "regular_2"),
        ("202415", "invierno"),     # P45: suffix 15 = winter session
        ("202425", "verano"),       # P45: suffix 25 = summer session
        ("202421", "excepcional"),  # P45: suffix 21 = exceptional cases
        ("202450", "postgrado"),
        ("202460", "postgrado"),
        ("202411", "otro"),
        ("202401", "otro"),
        ("202499", "otro"),
    ],
)
def test_s_suffix_to_type(periodo, tipo):
    assert tipo_periodo(periodo) == tipo
    assert parse_periodo(periodo).tipo_periodo == tipo


def test_s_unknown_suffix_is_kept_not_dropped():
    p = parse_periodo("202499")
    assert (p.anio, p.sufijo, p.periodo) == (2024, "99", "202499")
    assert p.periodo_atipico is True


@pytest.mark.parametrize("periodo", ["202411", "202401", "202421"])  # 21 is exceptional, still atypical
def test_known_odd_suffixes_flagged_atypical(periodo):
    assert parse_periodo(periodo).periodo_atipico is True


@pytest.mark.parametrize("periodo", ["202410", "202420", "202415", "202425", "202450"])
def test_regular_and_known_special_not_atypical(periodo):
    assert parse_periodo(periodo).periodo_atipico is False


def test_regular_order_is_monotone_and_special_has_none():
    a, b, c = (parse_periodo(p).orden_regular for p in ("202420", "202510", "202520"))
    assert a < b < c
    assert parse_periodo("202415").orden_regular is None


@pytest.mark.parametrize("bad", [None, "", "2024", "20241", "2024100", "abcdef", "20241a"])
def test_malformed_period_returns_none_explicitly(bad):
    assert parse_periodo(bad) is None
    assert tipo_periodo(bad) is None


def test_p45_verano_and_invierno_are_distinct_labels():
    assert tipo_periodo("202425") == "verano" and tipo_periodo("202415") == "invierno"
    assert "verano_invierno" not in {tipo_periodo(f"2024{s}") for s in ("10", "20", "15", "25", "21", "50", "60")}
