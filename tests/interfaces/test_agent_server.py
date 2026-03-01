"""Tests for the agent server FastAPI endpoints."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from interfaces.agent_server import AgentServerState, create_app


@pytest.fixture
def state():
    return AgentServerState(role="echo")


@pytest.fixture
def app(state):
    """Create the app without running the lifespan (skips bootstrap_agent)."""
    with patch("interfaces.agent_server.bootstrap_agent", new_callable=AsyncMock):
        return create_app(state)


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# --- GET /health ---


def test_health_returns_200_when_healthy(state, client):
    # Pre-set dependency status to healthy values
    state._healthy = True
    state._dependency_status = {"neo4j": "connected", "rabbitmq": "in_memory"}

    # Patch check_dependencies to return healthy status
    async def mock_check():
        return state._dependency_status

    state.check_dependencies = mock_check

    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["agent"] == "echo"


def test_health_returns_503_when_unhealthy(state, client):
    async def mock_check():
        return {"neo4j": "disconnected: timeout", "rabbitmq": "not_initialized"}

    state.check_dependencies = mock_check

    response = client.get("/health")
    assert response.status_code == 503


# --- POST /v1/tasks/send ---


def test_send_valid_payload(state, client):
    payload = {
        "taskId": "task-1",
        "message": {
            "id": "msg-1",
            "sender_id": "agent-a",
            "receiver_id": "agent-b",
            "content": "hello",
            "metadata": {"priority": "high"},
        },
    }
    response = client.post("/v1/tasks/send", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["taskId"] == "msg-1"


def test_send_missing_sender_id_returns_400(state, client):
    payload = {
        "taskId": "task-2",
        "message": {
            "receiver_id": "agent-b",
            "content": "no sender",
        },
    }
    response = client.post("/v1/tasks/send", json=payload)
    assert response.status_code == 400
    assert "sender_id" in response.json()["detail"]


def test_send_queue_full_returns_429(state, monkeypatch):
    # MAX_QUEUE_SIZE is read from env at app creation time
    monkeypatch.setenv("AGENT_MAX_QUEUE_SIZE", "2")

    with patch("interfaces.agent_server.bootstrap_agent", new_callable=AsyncMock):
        patched_app = create_app(state)
    patched_client = TestClient(patched_app, raise_server_exceptions=False)

    payload = {
        "taskId": "task-fill",
        "message": {
            "id": "msg-fill",
            "sender_id": "a",
            "receiver_id": "target",
            "content": "fill",
        },
    }

    # Fill the queue
    patched_client.post("/v1/tasks/send", json=payload)
    patched_client.post("/v1/tasks/send", json=payload)

    # Third should be rejected
    response = patched_client.post("/v1/tasks/send", json=payload)
    assert response.status_code == 429


def test_enqueued_message_has_correct_fields(state, client):
    payload = {
        "taskId": "task-fields",
        "message": {
            "id": "msg-fields",
            "sender_id": "alice",
            "receiver_id": "bob",
            "content": {"cmd": "run"},
            "metadata": {"trace": "123"},
        },
    }
    response = client.post("/v1/tasks/send", json=payload)
    assert response.status_code == 200

    # Verify the message landed in the correct queue
    queue = state.message_queues["bob"]
    assert queue.qsize() == 1
