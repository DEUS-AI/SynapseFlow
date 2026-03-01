"""Tests for validate_env_vars() from agent_server.py."""

import pytest

from interfaces.agent_server import validate_env_vars


def test_all_vars_present_no_exit(monkeypatch):
    """When all required vars are set, validate_env_vars should not exit."""
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_PASSWORD", "pass")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    # Should not raise
    validate_env_vars("data_architect")


def test_missing_common_var_exits(monkeypatch):
    """Missing a common required var (NEO4J_URI) should sys.exit."""
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.setenv("NEO4J_PASSWORD", "pass")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with pytest.raises(SystemExit):
        validate_env_vars("data_architect")


def test_missing_role_specific_var_exits(monkeypatch):
    """Missing a role-specific var (REDIS_HOST for medical_assistant) should sys.exit."""
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_PASSWORD", "pass")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("QDRANT_URL", raising=False)

    with pytest.raises(SystemExit):
        validate_env_vars("medical_assistant")
