"""Tests for DistributedCommandBus — local fallback paths (no RabbitMQ required)."""

import pytest
from unittest.mock import AsyncMock

from application.commands.echo_command import EchoCommand, EchoCommandHandler
from infrastructure.command_bus.distributed_command_bus import DistributedCommandBus


@pytest.fixture
def bus():
    return DistributedCommandBus(connection_url="amqp://unused/")


# --- Local fallback ---


@pytest.mark.asyncio
async def test_disconnected_bus_falls_back_to_local(bus):
    """When not connected, dispatch should use the local handler."""
    handler = EchoCommandHandler()
    bus.register(EchoCommand, handler)

    result = await bus.dispatch(EchoCommand(text="local-echo"))
    assert result == "local-echo"


@pytest.mark.asyncio
async def test_no_agent_role_falls_back_to_local():
    """Command with no registered agent role uses local handler."""
    from pydantic import BaseModel
    from domain.commands import Command

    class UnroutedCommand(Command, BaseModel):
        val: int = 0

    bus = DistributedCommandBus()
    mock_handler = AsyncMock()
    mock_handler.handle = AsyncMock(return_value="handled")
    bus.register(UnroutedCommand, mock_handler)

    result = await bus.dispatch(UnroutedCommand(val=42))
    assert result == "handled"
    mock_handler.handle.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_local_handler_raises_type_error(bus):
    """Dispatch with no local handler raises TypeError."""
    with pytest.raises(TypeError, match="No handler registered"):
        await bus.dispatch(EchoCommand(text="orphan"))


@pytest.mark.asyncio
async def test_register_stores_handler_and_dispatch_calls_it(bus):
    handler = EchoCommandHandler()
    bus.register(EchoCommand, handler)

    assert EchoCommand in bus._local_handlers
    result = await bus.dispatch(EchoCommand(text="stored"))
    assert result == "stored"
