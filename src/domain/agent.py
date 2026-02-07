from abc import ABC, abstractmethod
from typing import Any, List, Optional, TYPE_CHECKING

from domain.communication import CommunicationChannel, Message
from domain.command_bus import CommandBus

if TYPE_CHECKING:
    from application.services.agent_discovery import AgentDiscoveryService, AgentServiceInfo


class Agent(ABC):
    """
    Abstract base class for all agents in the system.

    Each agent has a unique ID, a command bus to execute actions,
    a communication channel to interact with other agents, and a
    graph repository to interact with the knowledge graph.

    Optional discovery service integration enables:
    - Agent registration in the KG
    - Capability-based agent discovery
    - Health status management
    """

    def __init__(
        self,
        agent_id: str,
        command_bus: CommandBus,
        communication_channel: CommunicationChannel,
        discovery_service: Optional["AgentDiscoveryService"] = None,
    ):
        self.agent_id = agent_id
        self.command_bus = command_bus
        self.communication_channel = communication_channel
        self._discovery_service = discovery_service

    @abstractmethod
    async def process_messages(self) -> None:
        """
        The main loop for the agent to process incoming messages.
        """
        pass

    # ========================================
    # Discovery Service Integration
    # ========================================

    def get_agent_info(self) -> Optional["AgentServiceInfo"]:
        """
        Get this agent's service information for registration.

        Override in subclasses to provide agent-specific metadata.
        Returns None by default (no registration).
        """
        return None

    async def register_self(self) -> bool:
        """
        Register this agent with the discovery service.

        Uses get_agent_info() to get the agent's metadata.
        Returns True if registration succeeded.
        """
        if not self._discovery_service:
            return False

        agent_info = self.get_agent_info()
        if not agent_info:
            return False

        return await self._discovery_service.register_agent(agent_info)

    async def discover_agent(self, capability: str) -> Optional[str]:
        """
        Discover an agent by capability.

        Queries the KG for an active agent that provides the
        requested capability.

        Args:
            capability: The capability to search for

        Returns:
            Agent URL if found, None otherwise
        """
        if not self._discovery_service:
            return None

        return await self._discovery_service.discover_agent(capability)

    async def discover_agents(
        self,
        capability: str,
        limit: int = 10,
    ) -> List["AgentServiceInfo"]:
        """
        Discover multiple agents by capability.

        Args:
            capability: The capability to search for
            limit: Maximum number of agents to return

        Returns:
            List of matching agents
        """
        if not self._discovery_service:
            return []

        result = await self._discovery_service.discover_by_capability(
            capability=capability,
            limit=limit,
        )
        return result.agents

    async def send_heartbeat(self) -> bool:
        """
        Send a heartbeat to indicate this agent is alive.

        Should be called periodically by long-running agents.
        """
        if not self._discovery_service:
            return False

        return await self._discovery_service.update_heartbeat(self.agent_id)

    async def deregister_self(self) -> bool:
        """
        Mark this agent as inactive during shutdown.
        """
        if not self._discovery_service:
            return False

        return await self._discovery_service.mark_inactive(self.agent_id)

    # ========================================
    # Communication Helpers
    # ========================================

    async def send_message(self, receiver_id: str, content: Any) -> None:
        """Helper method to send a message to another agent."""
        message = Message(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            content=content,
        )
        await self.communication_channel.send(message)

    async def receive_message(self) -> Optional[Message]:
        """Helper method to receive a message from the channel."""
        return await self.communication_channel.receive(self.agent_id)
