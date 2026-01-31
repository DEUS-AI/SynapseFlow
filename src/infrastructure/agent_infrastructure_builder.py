"""
Agent Infrastructure Builder

Factory for creating agent communication infrastructure components
based on configuration.
"""

import logging
from typing import Optional, TYPE_CHECKING

from config.agent_config import (
    AgentInfraConfig,
    EventBusType,
    ChannelType,
    DiscoveryType,
    get_agent_config,
)
from domain.communication import CommunicationChannel
from application.event_bus import EventBus

if TYPE_CHECKING:
    from application.services.agent_discovery import AgentDiscoveryService

logger = logging.getLogger(__name__)


class AgentInfrastructureBuilder:
    """
    Builder for agent infrastructure components.

    Creates EventBus, CommunicationChannel, and DiscoveryService
    instances based on configuration.

    Usage:
        builder = AgentInfrastructureBuilder()
        event_bus = await builder.build_event_bus()
        channel = builder.build_communication_channel()
        discovery = await builder.build_discovery_service()

    Or with custom config:
        config = AgentInfraConfig.from_yaml("custom/path.yaml")
        builder = AgentInfrastructureBuilder(config)
    """

    def __init__(self, config: Optional[AgentInfraConfig] = None):
        """
        Initialize the builder.

        Args:
            config: Optional configuration. If not provided, loads from
                    environment/YAML using get_agent_config().
        """
        self.config = config or get_agent_config()
        self._event_bus: Optional[EventBus] = None
        self._channel: Optional[CommunicationChannel] = None
        self._discovery: Optional["AgentDiscoveryService"] = None

    async def build_event_bus(self) -> EventBus:
        """
        Build the event bus based on configuration.

        Returns:
            EventBus instance (InMemoryEventBus or RabbitMQEventBus)
        """
        if self._event_bus is not None:
            return self._event_bus

        eb_config = self.config.event_bus

        if eb_config.type == EventBusType.MEMORY:
            logger.info("Creating in-memory EventBus")
            # EventBus from application.event_bus is already in-memory
            self._event_bus = EventBus()

        elif eb_config.type == EventBusType.RABBITMQ:
            logger.info(f"Creating RabbitMQEventBus with URL: {eb_config.rabbitmq.url}")
            from infrastructure.event_bus.rabbitmq_event_bus import RabbitMQEventBus

            self._event_bus = RabbitMQEventBus(
                connection_url=eb_config.rabbitmq.url,
                exchange_name=eb_config.rabbitmq.exchange_name,
                queue_prefix=eb_config.rabbitmq.queue_prefix,
                max_retries=eb_config.rabbitmq.max_retries,
                retry_delay=eb_config.rabbitmq.retry_delay,
            )
            # Connect to RabbitMQ
            await self._event_bus.connect()

        else:
            raise ValueError(f"Unknown event bus type: {eb_config.type}")

        return self._event_bus

    def build_communication_channel(
        self,
        agent_url: Optional[str] = None
    ) -> CommunicationChannel:
        """
        Build the communication channel based on configuration.

        Args:
            agent_url: Optional override for the agent's URL (for A2A channel).
                       If not provided, uses config value.

        Returns:
            CommunicationChannel instance
        """
        if self._channel is not None:
            return self._channel

        ch_config = self.config.communication_channel

        if ch_config.type == ChannelType.MEMORY:
            logger.info("Creating InMemoryCommunicationChannel")
            from infrastructure.communication.memory_channel import InMemoryCommunicationChannel
            self._channel = InMemoryCommunicationChannel()

        elif ch_config.type == ChannelType.A2A:
            base_url = agent_url or ch_config.a2a.base_url
            logger.info(f"Creating A2ACommunicationChannel with base URL: {base_url}")
            from infrastructure.communication.a2a_channel import A2ACommunicationChannel
            self._channel = A2ACommunicationChannel(base_url=base_url)

        elif ch_config.type == ChannelType.RABBITMQ:
            logger.info(f"Creating RabbitMQCommunicationChannel with URL: {ch_config.rabbitmq.url}")
            # This would need a RabbitMQ-based channel implementation
            # For now, fall back to memory channel
            logger.warning("RabbitMQ channel not fully implemented, using memory channel")
            from infrastructure.communication.memory_channel import InMemoryCommunicationChannel
            self._channel = InMemoryCommunicationChannel()

        else:
            raise ValueError(f"Unknown channel type: {ch_config.type}")

        return self._channel

    async def build_discovery_service(
        self,
        backend=None
    ) -> Optional["AgentDiscoveryService"]:
        """
        Build the agent discovery service based on configuration.

        Args:
            backend: Optional Neo4j backend. Required for Neo4j discovery.

        Returns:
            AgentDiscoveryService instance or None for local discovery
        """
        if self._discovery is not None:
            return self._discovery

        disc_config = self.config.discovery

        if disc_config.type == DiscoveryType.LOCAL:
            logger.info("Using local (in-memory) agent discovery")
            # Local discovery doesn't need a service - agents are in-process
            return None

        elif disc_config.type == DiscoveryType.NEO4J:
            logger.info("Creating Neo4j-backed AgentDiscoveryService")
            from application.services.agent_discovery import AgentDiscoveryService

            if backend is None:
                # Create a backend if not provided
                from infrastructure.neo4j_backend import Neo4jBackend
                backend = Neo4jBackend(
                    uri=disc_config.neo4j.uri,
                    username=disc_config.neo4j.username,
                    password=disc_config.neo4j.password,
                )
                await backend.connect()

            self._discovery = AgentDiscoveryService(
                backend=backend,
                stale_threshold_seconds=disc_config.stale_threshold_seconds,
            )
            return self._discovery

        else:
            raise ValueError(f"Unknown discovery type: {disc_config.type}")

    def get_agent_config(self, agent_name: str):
        """
        Get configuration for a specific agent.

        Args:
            agent_name: Agent name (e.g., "knowledge_manager")

        Returns:
            AgentConfig or None if not found
        """
        return self.config.agents.get(agent_name)

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if a specific agent is enabled."""
        agent_config = self.get_agent_config(agent_name)
        return agent_config.enabled if agent_config else False

    def get_agent_url(self, agent_name: str) -> Optional[str]:
        """Get the URL for a specific agent (for A2A communication)."""
        agent_config = self.get_agent_config(agent_name)
        return agent_config.url if agent_config else None

    async def close(self):
        """Clean up resources."""
        if self._event_bus is not None:
            if hasattr(self._event_bus, 'disconnect'):
                await self._event_bus.disconnect()

        if self._channel is not None:
            if hasattr(self._channel, 'close'):
                await self._channel.close()


# Convenience function
async def create_infrastructure(
    config: Optional[AgentInfraConfig] = None
) -> AgentInfrastructureBuilder:
    """
    Create and initialize infrastructure builder.

    Usage:
        infra = await create_infrastructure()
        event_bus = await infra.build_event_bus()
        channel = infra.build_communication_channel()
    """
    builder = AgentInfrastructureBuilder(config)
    return builder
