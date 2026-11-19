import pytest

from pipelines.common.config import ConfigError, hmac_secret, load_db_config
from pipelines.common.db import WAREHOUSE_STATEMENT_TIMEOUT_MS, warehouse_options

FULL = {
    "DEV_HOST": "h", "DEV_PORT": "5432", "DEV_DB": "d", "DEV_USER": "u", "DEV_PASSWORD": "pw-test",
}


def test_load_db_config_reads_all_variables():
    cfg = load_db_config("DEV", FULL)
    assert (cfg.host, cfg.port, cfg.dbname, cfg.user, cfg.password) == ("h", 5432, "d", "u", "pw-test")


def test_missing_variables_are_listed_without_defaults():
    with pytest.raises(ConfigError) as exc:
        load_db_config("WH", {"WH_HOST": "x"})
    msg = str(exc.value)
    for name in ("WH_PORT", "WH_DB", "WH_USER", "WH_PASSWORD"):
        assert name in msg
    assert "WH_HOST" not in msg


def test_blank_value_counts_as_missing():
    with pytest.raises(ConfigError):
        load_db_config("DEV", {**FULL, "DEV_PASSWORD": "  "})


def test_bad_port_is_a_config_error():
    with pytest.raises(ConfigError):
        load_db_config("DEV", {**FULL, "DEV_PORT": "abc"})


def test_repr_hides_password():
    cfg = load_db_config("DEV", FULL)
    assert "pw-test" not in repr(cfg)


def test_hmac_secret_required():
    with pytest.raises(ConfigError):
        hmac_secret({})
    assert hmac_secret({"DAI_NEURAL_HMAC_KEY": "abc"}) == "abc"


def test_warehouse_options_force_read_only_and_timeout():
    opts = warehouse_options()
    assert "default_transaction_read_only=on" in opts
    assert f"statement_timeout={WAREHOUSE_STATEMENT_TIMEOUT_MS}" in opts


def test_warehouse_options_custom_timeout_and_validation():
    assert "statement_timeout=5000" in warehouse_options(5000)
    with pytest.raises(ValueError):
        warehouse_options(0)
