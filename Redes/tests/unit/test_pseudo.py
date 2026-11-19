import pytest

from pipelines.common.pseudo import docente_key, normalize_rut, persona_key

KEY = "unit-test-secret-not-real"


@pytest.mark.parametrize(
    "raw",
    ["11111111-1", "11.111.111-1", " 11111111-1 ", "011111111-1", "0011.111.111-1", "111111111"],
)
def test_normalize_rut_variants_map_to_same_value(raw):
    assert normalize_rut(raw) == "111111111"


def test_normalize_rut_uppercases_check_digit():
    assert normalize_rut("22.222.222-k") == "22222222K"


@pytest.mark.parametrize("raw", [None, "", "   ", "-", "0", "000-0", ".-."])
def test_normalize_rut_rejects_empty(raw):
    assert normalize_rut(raw) is None


def test_persona_key_is_deterministic_hex_sha256():
    a = persona_key("11111111-1", KEY)
    assert a == persona_key("11111111-1", KEY)
    assert len(a) == 64 and int(a, 16) >= 0


def test_persona_key_same_for_normalization_variants():
    assert persona_key("11.111.111-1", KEY) == persona_key("011111111-1", KEY)


def test_persona_key_depends_on_secret():
    assert persona_key("11111111-1", KEY) != persona_key("11111111-1", KEY + "x")


def test_persona_key_differs_per_person():
    assert persona_key("11111111-1", KEY) != persona_key("22222222-2", KEY)


def test_student_and_teacher_domains_never_collide():
    assert persona_key("11111111-1", KEY) != docente_key("11111111-1", KEY)


def test_docente_key_deterministic_and_normalized():
    assert docente_key("11.111.111-1", KEY) == docente_key("11111111-1", KEY)


def test_invalid_rut_gives_none_key():
    assert persona_key("", KEY) is None
    assert docente_key(None, KEY) is None


def test_key_is_required():
    with pytest.raises(ValueError):
        persona_key("11111111-1", "")


def test_key_never_contains_the_rut():
    assert "111111111" not in persona_key("11111111-1", KEY)


def test_key_fingerprint_is_hmac_over_fixed_message():
    import hashlib
    import hmac

    from pipelines.common.pseudo import key_fingerprint

    expected = hmac.new(KEY.encode(), b"dai-neural:huella-clave:v1", hashlib.sha256).hexdigest()
    assert key_fingerprint(KEY) == expected
    assert key_fingerprint(KEY) != key_fingerprint(KEY + "x")
    with pytest.raises(ValueError):
        key_fingerprint("")
