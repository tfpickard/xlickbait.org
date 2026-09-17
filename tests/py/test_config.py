"""Configuration loading: the guards that stop a bad env var doing damage."""

from __future__ import annotations

import pytest

from generator import config as config_module
from generator.config import ARXIV_MIN_INTERVAL_SECONDS


@pytest.fixture(autouse=True)
def base_env(monkeypatch):
    """A minimally valid environment; individual tests override one key."""
    monkeypatch.setenv("XLICKBAIT_DB_URL", "postgresql://user:pw@localhost/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    for name in (
        "XLICKBAIT_ARXIV_INTERVAL",
        "XLICKBAIT_ID_BATCH",
        "XLICKBAIT_CATEGORIES",
        "XLICKBAIT_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


class TestRateLimitIsNotNegotiable:
    """arXiv's three seconds is a condition of use, not a default."""

    @pytest.mark.parametrize("value", ["0", "0.5", "-5", "2.999"])
    def test_an_override_can_never_go_below_the_documented_minimum(self, monkeypatch, value):
        # Regression: this was passed straight through to the RateLimiter, so an
        # ordinary environment setting could put the client in breach -- and a
        # negative value removed the gate entirely.
        monkeypatch.setenv("XLICKBAIT_ARXIV_INTERVAL", value)
        assert config_module.load().request_interval == ARXIV_MIN_INTERVAL_SECONDS

    def test_an_override_may_still_slow_the_client_down(self, monkeypatch):
        # Clamping must be one-directional: being politer than required is fine.
        monkeypatch.setenv("XLICKBAIT_ARXIV_INTERVAL", "10")
        assert config_module.load().request_interval == 10.0

    def test_the_default_is_the_minimum(self):
        assert config_module.load().request_interval == ARXIV_MIN_INTERVAL_SECONDS


class TestBatchSizeIsValidated:
    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_a_non_positive_batch_is_rejected_at_load(self, monkeypatch, value):
        # It would otherwise make the vintage sampler draw nothing forever.
        monkeypatch.setenv("XLICKBAIT_ID_BATCH", value)
        with pytest.raises(SystemExit, match="XLICKBAIT_ID_BATCH"):
            config_module.load()

    def test_a_positive_batch_is_accepted(self, monkeypatch):
        monkeypatch.setenv("XLICKBAIT_ID_BATCH", "25")
        assert config_module.load().id_batch_size == 25


class TestTheKillSwitchDoesNotNeedTheModel:
    def test_run_still_requires_an_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
            config_module.load()

    def test_hide_loads_without_an_api_key(self, monkeypatch):
        # `hide` never calls Anthropic, and the moment you most need to take a
        # headline down is exactly when the key may be missing or mid-rotation.
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg = config_module.load_for_hide()
        assert cfg.database_url.startswith("postgresql://")
        assert cfg.anthropic_api_key == ""

    def test_the_database_url_is_still_required_either_way(self, monkeypatch):
        monkeypatch.delenv("XLICKBAIT_DB_URL", raising=False)
        with pytest.raises(SystemExit, match="XLICKBAIT_DB_URL"):
            config_module.load_for_hide()


class TestTheKillSwitchIgnoresRunSettings:
    """`hide` calls neither Anthropic nor arXiv, so no generation setting may be
    able to stop a takedown. The moment you need it is the moment something else
    is already wrong."""

    def test_a_bad_id_batch_does_not_block_hide(self, monkeypatch):
        monkeypatch.setenv("XLICKBAIT_ID_BATCH", "0")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert config_module.load_for_hide().database_url.startswith("postgresql://")

    def test_a_malformed_interval_does_not_block_hide(self, monkeypatch):
        monkeypatch.setenv("XLICKBAIT_ARXIV_INTERVAL", "not-a-number")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert config_module.load_for_hide().database_url.startswith("postgresql://")

    def test_but_a_run_still_rejects_those_values(self, monkeypatch):
        monkeypatch.setenv("XLICKBAIT_ID_BATCH", "0")
        with pytest.raises(SystemExit):
            config_module.load()

    def test_hide_still_needs_a_database(self, monkeypatch):
        monkeypatch.delenv("XLICKBAIT_DB_URL", raising=False)
        with pytest.raises(SystemExit, match="XLICKBAIT_DB_URL"):
            config_module.load_for_hide()

    def test_hide_picks_up_purge_credentials_when_present(self, monkeypatch):
        monkeypatch.setenv("NETLIFY_PURGE_TOKEN", "t")
        monkeypatch.setenv("NETLIFY_SITE_ID", "s")
        assert config_module.load_for_hide().can_purge is True


class TestVintageCount:
    @pytest.mark.parametrize("value", ["-1", "-10"])
    def test_a_negative_vintage_count_is_rejected(self, monkeypatch, value):
        # It used to be honoured: pick_vintage returned nothing, the shortage
        # check passed, and the run was recorded a success having published fewer
        # headlines than asked for, with nothing to say why.
        monkeypatch.setenv("XLICKBAIT_VINTAGE", value)
        with pytest.raises(SystemExit, match="XLICKBAIT_VINTAGE"):
            config_module.load()

    def test_zero_still_means_disabled(self, monkeypatch):
        monkeypatch.setenv("XLICKBAIT_VINTAGE", "0")
        assert config_module.load().vintage_count == 0
