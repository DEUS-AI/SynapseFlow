"""Tests for DDA upload route integration with AgentGateway."""

import io
import pytest
from unittest.mock import AsyncMock, patch

from application.services.agent_gateway import AgentUnavailableError


@pytest.fixture
def mock_kg_backend():
    backend = AsyncMock()
    backend.query_raw = AsyncMock(return_value=[{"catalog_id": "1"}])
    return backend


@pytest.fixture
def client(mock_kg_backend):
    """Create a test client with mocked dependencies."""
    from fastapi.testclient import TestClient
    from application.api.main import app

    return TestClient(app, raise_server_exceptions=False)


# --- Gateway invocation ---


def test_upload_with_agent_calls_gateway(client, mock_kg_backend):
    mock_gateway = AsyncMock()
    mock_gateway.invoke = AsyncMock(return_value={
        "success": True,
        "domain": "TestDomain",
        "entities_created": ["e1"],
        "relationships_created": ["r1"],
        "events_published": 2,
    })

    with patch("application.api.dependencies.get_agent_gateway", return_value=mock_gateway), \
         patch("application.api.dependencies.get_kg_backend", return_value=mock_kg_backend):
        response = client.post(
            "/api/dda/upload",
            files={"file": ("test.md", io.BytesIO(b"# Test DDA\n## Data Entities\n### Customer\n"), "text/markdown")},
            data={"use_agent": "true"},
        )

    # The gateway should have been called
    mock_gateway.invoke.assert_awaited_once()
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["agent"] == "data_architect"


# --- AgentUnavailableError → 503 ---


def test_gateway_unavailable_returns_503(client, mock_kg_backend):
    mock_gateway = AsyncMock()
    mock_gateway.invoke = AsyncMock(
        side_effect=AgentUnavailableError("data_architect", reason="connection refused")
    )

    with patch("application.api.dependencies.get_agent_gateway", return_value=mock_gateway), \
         patch("application.api.dependencies.get_kg_backend", return_value=mock_kg_backend):
        response = client.post(
            "/api/dda/upload",
            files={"file": ("test.md", io.BytesIO(b"# Test DDA\n"), "text/markdown")},
            data={"use_agent": "true"},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "agent_unavailable"
    assert body["agent"] == "data_architect"
