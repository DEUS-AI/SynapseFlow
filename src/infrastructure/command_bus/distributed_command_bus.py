"""Distributed CommandBus implementation using RabbitMQ RPC.

Dispatches commands to remote agent processes by:
1. Serializing the command via CommandRegistry
2. Sending it as an RPC call to the target agent's queue (cmd_<role>)
3. Waiting for the response and deserializing the result
"""

import asyncio
import json
import logging
from typing import Any, Optional

import aio_pika
from aio_pika import connect_robust, Message as AMQPMessage, DeliveryMode
from aio_pika.patterns import RPC

from domain.command_bus import CommandBus as AbstractCommandBus
from domain.commands import Command
from application.commands.registry import (
    CommandRegistry,
    CommandDeserializationError,
    create_default_registry,
)

logger = logging.getLogger(__name__)


class CommandDispatchError(Exception):
    """Raised when a command cannot be dispatched to a remote agent."""

    def __init__(self, agent_role: str, command_type: str, reason: str = ""):
        self.agent_role = agent_role
        self.command_type = command_type
        super().__init__(
            f"Failed to dispatch {command_type} to agent '{agent_role}': {reason}"
        )


class DistributedCommandBus(AbstractCommandBus):
    """CommandBus that dispatches commands to remote agents via RabbitMQ RPC.

    Each agent registers an RPC handler on queue `cmd_<role>`.
    This bus serializes commands, sends them to the correct queue,
    and deserializes the response.
    """

    def __init__(
        self,
        connection_url: str = "amqp://guest:guest@localhost/",
        registry: Optional[CommandRegistry] = None,
        timeout: float = 30.0,
        queue_prefix: str = "cmd_",
    ):
        self._connection_url = connection_url
        self._registry = registry or create_default_registry()
        self._timeout = timeout
        self._queue_prefix = queue_prefix

        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._rpc: Optional[RPC] = None
        self._is_connected = False

        # Local handlers for fallback / hybrid mode
        self._local_handlers = {}

    async def connect(self) -> None:
        """Establish connection to RabbitMQ for RPC."""
        try:
            logger.info(f"DistributedCommandBus connecting to RabbitMQ at {self._connection_url}")
            self._connection = await connect_robust(self._connection_url)
            self._channel = await self._connection.channel()
            self._rpc = await RPC.create(self._channel)
            self._is_connected = True
            logger.info("DistributedCommandBus connected")
        except Exception as e:
            logger.error(f"DistributedCommandBus failed to connect: {e}")
            self._is_connected = False
            raise

    async def disconnect(self) -> None:
        """Close RabbitMQ connection."""
        if self._channel:
            await self._channel.close()
        if self._connection:
            await self._connection.close()
        self._is_connected = False

    def register(self, command_type: type, handler: Any) -> None:
        """Register a local handler (for fallback mode)."""
        self._local_handlers[command_type] = handler

    async def dispatch(self, command: Command) -> Any:
        """Dispatch a command to the appropriate remote agent.

        Falls back to local handler if not connected or no remote route.
        """
        # Determine target agent
        agent_role = self._registry.get_agent_role(command)

        if not agent_role:
            # No remote route — try local handler
            return await self._dispatch_local(command)

        if not self._is_connected:
            logger.warning(
                f"Not connected to RabbitMQ, falling back to local dispatch for {type(command).__name__}"
            )
            return await self._dispatch_local(command)

        # Serialize and send via RPC
        queue_name = f"{self._queue_prefix}{agent_role}"
        try:
            payload = self._registry.serialize(command)
            message_body = json.dumps(payload, default=str).encode()

            logger.info(f"Dispatching {type(command).__name__} to {queue_name}")
            response = await asyncio.wait_for(
                self._rpc.call(queue_name, message_body),
                timeout=self._timeout,
            )

            # Deserialize response
            result_str = response.decode() if isinstance(response, bytes) else response
            return self._registry.deserialize_result(result_str)

        except asyncio.TimeoutError:
            raise CommandDispatchError(
                agent_role,
                type(command).__name__,
                f"RPC call timed out after {self._timeout}s",
            )
        except Exception as e:
            raise CommandDispatchError(
                agent_role,
                type(command).__name__,
                str(e),
            )

    async def _dispatch_local(self, command: Command) -> Any:
        """Dispatch to a locally registered handler."""
        handler = self._local_handlers.get(type(command))
        if not handler:
            raise TypeError(
                f"No handler registered for command type {type(command).__name__}"
            )
        return await handler.handle(command)

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def register_rpc_handler(
        self,
        agent_role: str,
        local_command_bus,
    ) -> None:
        """Register this agent as an RPC handler for incoming commands.

        Called by agent_server.py on startup so this agent can receive
        commands dispatched by other processes.
        """
        if not self._is_connected:
            raise RuntimeError("Cannot register RPC handler: not connected")

        queue_name = f"{self._queue_prefix}{agent_role}"
        registry = self._registry

        async def rpc_handler(message_body: bytes) -> bytes:
            try:
                payload = json.loads(message_body.decode())
                command = registry.deserialize(payload)
                logger.info(f"RPC received {type(command).__name__} on {queue_name}")
                result = await local_command_bus.dispatch(command)
                return registry.serialize_result(result).encode()
            except CommandDeserializationError as e:
                logger.error(f"RPC deserialization error on {queue_name}: {e}")
                error_response = json.dumps({"error": str(e)})
                return error_response.encode()
            except Exception as e:
                logger.error(f"RPC handler error on {queue_name}: {e}")
                error_response = json.dumps({"error": str(e)})
                return error_response.encode()

        await self._rpc.register(queue_name, rpc_handler)
        logger.info(f"Registered RPC handler on queue '{queue_name}' for agent '{agent_role}'")
