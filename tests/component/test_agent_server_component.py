"""Component-level tests for agent_server using async HTTPX + ASGITransport."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch

from interfaces.agent_server import AgentServerState, create_app


@pytest.fixture
def state():
    return AgentServerState(role="echo")


@pytest.fixture
def app(state):
    with patch("interfaces.agent_server.bootstrap_agent", new_callable=AsyncMock):
        return create_app(state)


def _payload(sender="a", receiver="b", content="hi", task_id="t1"):
    return {
        "taskId": task_id,
        "message": {
            "id": f"msg-{task_id}",
            "sender_id": sender,
            "receiver_id": receiver,
            "content": content,
        },
    }


# --- Round-trip: POST then read from state queue ---


@pytest.mark.asyncio
async def test_post_message_then_read_from_queue(state, app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/v1/tasks/send", json=_payload(sender="alice", receiver="bob", content="hello"))

    assert resp.status_code == 200

    queue = state.message_queues["bob"]
    assert queue.qsize() == 1
    msg = await queue.get()
    assert msg.sender_id == "alice"
    assert msg.content == "hello"


# --- Health reflects changing dependency states ---


@pytest.mark.asyncio
async def test_health_reflects_dependency_changes(state, app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Healthy state
        state.check_dependencies = AsyncMock(
            return_value={"neo4j": "connected", "rabbitmq": "in_memory"}
        )
        resp = await ac.get("/health")
        assert resp.status_code == 200

        # Switch to unhealthy
        state.check_dependencies = AsyncMock(
            return_value={"neo4j": "disconnected: timeout"}
        )
        resp = await ac.get("/health")
        assert resp.status_code == 503


# --- Queue isolation between receivers ---


@pytest.mark.asyncio
async def test_messages_to_different_receivers_are_isolated(state, app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/v1/tasks/send", json=_payload(receiver="agent_x", content="for-x"))
        await ac.post("/v1/tasks/send", json=_payload(receiver="agent_y", content="for-y"))

    assert state.message_queues["agent_x"].qsize() == 1
    assert state.message_queues["agent_y"].qsize() == 1

    msg_x = await state.message_queues["agent_x"].get()
    msg_y = await state.message_queues["agent_y"].get()
    assert msg_x.content == "for-x"
    assert msg_y.content == "for-y"
