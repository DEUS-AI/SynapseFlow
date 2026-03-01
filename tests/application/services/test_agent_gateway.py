"""Tests for AgentGateway — local and distributed dispatch paths."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from application.services.agent_gateway import AgentGateway, AgentUnavailableError
from config.agent_config import AgentInfraConfig, DeploymentMode


@pytest.fixture
def local_config():
    config = AgentInfraConfig()
    config.deployment_mode = DeploymentMode.LOCAL
    return config


@pytest.fixture
def distributed_config():
    config = AgentInfraConfig()
    config.deployment_mode = DeploymentMode.DISTRIBUTED
    return config


# --- Local mode ---


@pytest.mark.asyncio
async def test_local_mode_dispatches_via_local_command_bus(local_config):
    gateway = AgentGateway(config=local_config)

    mock_bus = AsyncMock()
    mock_bus.dispatch = AsyncMock(return_value={"success": True})

    # bootstrap_command_bus is imported inside _invoke_local from composition_root
    with patch("composition_root.bootstrap_command_bus", return_value=mock_bus):
        from application.commands.echo_command import EchoCommand
        result = await gateway.invoke("echo", EchoCommand(text="test"))

    assert result == {"success": True}
    mock_bus.dispatch.assert_awaited_once()


# --- Distributed mode ---


@pytest.mark.asyncio
async def test_distributed_mode_wraps_dispatch_error(distributed_config):
    from infrastructure.command_bus.distributed_command_bus import CommandDispatchError

    gateway = AgentGateway(config=distributed_config)

    mock_bus = AsyncMock()
    mock_bus.connect = AsyncMock()
    mock_bus.dispatch = AsyncMock(
        side_effect=CommandDispatchError("da", "EchoCommand", "connection refused")
    )

    # DistributedCommandBus is imported inside initialize() from infrastructure module
    with patch(
        "infrastructure.command_bus.distributed_command_bus.DistributedCommandBus",
        return_value=mock_bus,
    ):
        gateway._initialized = False
        from application.commands.echo_command import EchoCommand
        with pytest.raises(AgentUnavailableError, match="da"):
            await gateway.invoke("data_architect", EchoCommand(text="fail"))


# --- Property ---


def test_deployment_mode_reflects_config(local_config, distributed_config):
    assert AgentGateway(config=local_config).deployment_mode == DeploymentMode.LOCAL
    assert AgentGateway(config=distributed_config).deployment_mode == DeploymentMode.DISTRIBUTED


# --- Idempotent initialize ---


@pytest.mark.asyncio
async def test_initialize_is_idempotent(local_config):
    gateway = AgentGateway(config=local_config)
    await gateway.initialize()
    assert gateway._initialized is True

    # Second call should be a no-op
    await gateway.initialize()
    assert gateway._initialized is True
