"""Agent Gateway — unified interface for invoking agent operations.

Routes agent invocations to either:
- Local in-process agents (local mode) via composition_root factories
- Remote agent containers (distributed mode) via DistributedCommandBus

The API layer uses this gateway instead of creating agents directly.
"""

import logging
from typing import Any, Optional

from config.agent_config import AgentInfraConfig, DeploymentMode, get_agent_config
from domain.commands import Command

logger = logging.getLogger(__name__)


class AgentUnavailableError(Exception):
    """Raised when a remote agent service is unreachable."""

    def __init__(self, agent_role: str, retry_after_seconds: int = 30, reason: str = ""):
        self.agent_role = agent_role
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Agent '{agent_role}' is unavailable: {reason}"
        )


class AgentGateway:
    """Routes agent operations to local or remote agents based on deployment mode.

    Usage:
        gateway = AgentGateway(config)
        await gateway.initialize()

        result = await gateway.invoke("data_architect", ModelingCommand(...))
    """

    def __init__(self, config: Optional[AgentInfraConfig] = None):
        self._config = config or get_agent_config()
        self._distributed_bus = None
        self._local_agents = {}
        self._initialized = False

    @property
    def deployment_mode(self) -> DeploymentMode:
        return self._config.deployment_mode

    async def initialize(self) -> None:
        """Initialize the gateway based on deployment mode."""
        if self._initialized:
            return

        if self._config.deployment_mode == DeploymentMode.DISTRIBUTED:
            import os
            from infrastructure.command_bus.distributed_command_bus import DistributedCommandBus
            rabbitmq_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost/")
            self._distributed_bus = DistributedCommandBus(connection_url=rabbitmq_url)
            await self._distributed_bus.connect()
            logger.info("AgentGateway initialized in distributed mode")
        else:
            logger.info("AgentGateway initialized in local mode")

        self._initialized = True

    async def invoke(self, role: str, command: Command) -> Any:
        """Invoke an agent operation.

        In local mode: creates the agent in-process and dispatches the command.
        In distributed mode: dispatches via DistributedCommandBus to the remote agent.
        """
        if not self._initialized:
            await self.initialize()

        if self._config.deployment_mode == DeploymentMode.DISTRIBUTED:
            return await self._invoke_remote(role, command)
        else:
            return await self._invoke_local(role, command)

    async def _invoke_remote(self, role: str, command: Command) -> Any:
        """Dispatch command to a remote agent via RabbitMQ RPC."""
        from infrastructure.command_bus.distributed_command_bus import CommandDispatchError

        try:
            return await self._distributed_bus.dispatch(command)
        except CommandDispatchError as e:
            raise AgentUnavailableError(
                agent_role=role,
                retry_after_seconds=30,
                reason=str(e),
            )

    async def _invoke_local(self, role: str, command: Command) -> Any:
        """Create agent in-process and dispatch command locally."""
        from composition_root import (
            bootstrap_command_bus,
            bootstrap_knowledge_management,
            bootstrap_graphiti,
            AGENT_REGISTRY,
        )

        # Get or create local command bus with handlers
        if not hasattr(self, "_local_command_bus"):
            self._local_command_bus = bootstrap_command_bus("local")

        return await self._local_command_bus.dispatch(command)

    async def close(self) -> None:
        """Clean up resources."""
        if self._distributed_bus and hasattr(self._distributed_bus, "disconnect"):
            await self._distributed_bus.disconnect()
