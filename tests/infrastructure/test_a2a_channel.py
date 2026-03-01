"""Tests for A2ACommunicationChannel — HTTP send + inbound queue."""

import json
from dataclasses import dataclass, field

import httpx
import pytest
from pytest_httpx import HTTPXMock

from domain.communication import Message
from infrastructure.communication.a2a_channel import (
    A2ACommunicationChannel,
    AgentNotFoundError,
)


ARCHITECT_URL = "http://data_architect:8001"
ENGINEER_URL = "http://data_engineer:8002"
FALLBACK_URL = "http://fallback:9000"


@pytest.fixture
def channel():
    return A2ACommunicationChannel(
        agent_urls={"data_architect": ARCHITECT_URL, "data_engineer": ENGINEER_URL},
        base_url=FALLBACK_URL,
    )


def _make_message(receiver="data_architect", content="hi", **kw):
    return Message(sender_id="sender", receiver_id=receiver, content=content, **kw)


# --- send() URL resolution ---


@pytest.mark.asyncio
async def test_send_resolves_url_from_agent_urls(httpx_mock: HTTPXMock, channel):
    httpx_mock.add_response(url=f"{ARCHITECT_URL}/v1/tasks/send", status_code=200)
    await channel.send(_make_message(receiver="data_architect"))

    req = httpx_mock.get_request()
    assert str(req.url) == f"{ARCHITECT_URL}/v1/tasks/send"


@pytest.mark.asyncio
async def test_send_falls_back_to_base_url(httpx_mock: HTTPXMock, channel):
    httpx_mock.add_response(url=f"{FALLBACK_URL}/v1/tasks/send", status_code=200)
    await channel.send(_make_message(receiver="unknown_agent"))

    req = httpx_mock.get_request()
    assert str(req.url) == f"{FALLBACK_URL}/v1/tasks/send"


@pytest.mark.asyncio
async def test_send_unknown_agent_no_base_url_raises():
    channel = A2ACommunicationChannel(agent_urls={}, base_url=None)
    with pytest.raises(AgentNotFoundError, match="ghost_agent"):
        await channel.send(_make_message(receiver="ghost_agent"))


# --- send() wire format ---


@pytest.mark.asyncio
async def test_send_wire_format(httpx_mock: HTTPXMock, channel):
    httpx_mock.add_response(url=f"{ARCHITECT_URL}/v1/tasks/send", status_code=200)
    msg = _make_message(receiver="data_architect", content="payload", metadata={"k": "v"})
    await channel.send(msg)

    body = json.loads(httpx_mock.get_request().content)
    assert body["taskId"] == msg.id
    assert body["message"]["id"] == msg.id
    assert body["message"]["sender_id"] == "sender"
    assert body["message"]["receiver_id"] == "data_architect"
    assert body["message"]["content"] == "payload"
    assert body["message"]["metadata"] == {"k": "v"}


@pytest.mark.asyncio
async def test_send_dict_content_preserved(httpx_mock: HTTPXMock, channel):
    httpx_mock.add_response(url=f"{ARCHITECT_URL}/v1/tasks/send", status_code=200)
    dict_content = {"command": "model", "params": [1, 2]}
    await channel.send(_make_message(receiver="data_architect", content=dict_content))

    body = json.loads(httpx_mock.get_request().content)
    assert body["message"]["content"] == dict_content


# --- send() error handling ---


@pytest.mark.asyncio
async def test_send_http_500_raises(httpx_mock: HTTPXMock, channel):
    httpx_mock.add_response(url=f"{ARCHITECT_URL}/v1/tasks/send", status_code=500)
    with pytest.raises(httpx.HTTPStatusError):
        await channel.send(_make_message(receiver="data_architect"))


# --- receive() / enqueue_inbound() ---


@pytest.mark.asyncio
async def test_receive_empty_queue_returns_none(channel):
    result = await channel.receive("data_architect")
    assert result is None


@pytest.mark.asyncio
async def test_enqueue_then_receive(channel):
    msg = _make_message(receiver="data_architect", content="queued")
    await channel.enqueue_inbound(msg)

    received = await channel.receive("data_architect")
    assert received is not None
    assert received.content == "queued"
    assert received.sender_id == "sender"
    assert received.receiver_id == "data_architect"


@pytest.mark.asyncio
async def test_fifo_ordering(channel):
    for i in range(3):
        await channel.enqueue_inbound(_make_message(receiver="da", content=f"msg-{i}"))

    for i in range(3):
        received = await channel.receive("da")
        assert received.content == f"msg-{i}"


# --- get_all_messages() ---


@pytest.mark.asyncio
async def test_get_all_messages_drains_queue(channel):
    for i in range(3):
        await channel.enqueue_inbound(_make_message(receiver="da", content=f"m-{i}"))

    all_msgs = await channel.get_all_messages("da")
    assert len(all_msgs) == 3
    assert [m.content for m in all_msgs] == ["m-0", "m-1", "m-2"]

    # Second call returns empty
    assert await channel.get_all_messages("da") == []


# --- queue_size() ---


@pytest.mark.asyncio
async def test_queue_size(channel):
    assert channel.queue_size("da") == 0

    await channel.enqueue_inbound(_make_message(receiver="da", content="a"))
    await channel.enqueue_inbound(_make_message(receiver="da", content="b"))
    assert channel.queue_size("da") == 2

    await channel.receive("da")
    assert channel.queue_size("da") == 1


# --- from_agent_config() ---


def test_from_agent_config_builds_agent_urls():
    @dataclass
    class FakeAgent:
        enabled: bool = True
        url: str = ""

    @dataclass
    class FakeA2A:
        base_url: str = "http://base:8000"

    @dataclass
    class FakeChannel:
        a2a: FakeA2A = field(default_factory=FakeA2A)

    @dataclass
    class FakeConfig:
        agents: dict = field(default_factory=dict)
        communication_channel: FakeChannel = field(default_factory=FakeChannel)

    config = FakeConfig(
        agents={
            "da": FakeAgent(enabled=True, url="http://da:8001"),
            "de": FakeAgent(enabled=True, url="http://de:8002"),
            "disabled": FakeAgent(enabled=False, url="http://disabled:9999"),
        }
    )

    ch = A2ACommunicationChannel.from_agent_config(config)
    assert ch._agent_urls == {"da": "http://da:8001", "de": "http://de:8002"}
