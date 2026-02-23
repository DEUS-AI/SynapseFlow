"""Tests for startup configuration validation."""

import logging

import pytest
from infrastructure.config_validation import validate_config, REQUIRED_VARS, OPTIONAL_VARS


class TestValidateConfig:
    """Tests for validate_config()."""

    def test_all_required_vars_present_succeeds(self, monkeypatch):
        for var in REQUIRED_VARS:
            monkeypatch.setenv(var, "test-value")
        for var in OPTIONAL_VARS:
            monkeypatch.setenv(var, "test-value")
        # Should not raise or exit
        validate_config()

    def test_missing_required_var_exits(self, monkeypatch):
        # Set all except NEO4J_PASSWORD
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        with pytest.raises(SystemExit):
            validate_config()

    def test_missing_all_required_vars_exits(self, monkeypatch):
        for var in REQUIRED_VARS:
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(SystemExit):
            validate_config()

    def test_empty_required_var_exits(self, monkeypatch):
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("NEO4J_PASSWORD", "")
        with pytest.raises(SystemExit):
            validate_config()

    def test_missing_optional_var_warns(self, monkeypatch, caplog):
        for var in REQUIRED_VARS:
            monkeypatch.setenv(var, "test-value")
        for var in OPTIONAL_VARS:
            monkeypatch.delenv(var, raising=False)
        with caplog.at_level(logging.WARNING):
            validate_config()
        for var in OPTIONAL_VARS:
            assert var in caplog.text
