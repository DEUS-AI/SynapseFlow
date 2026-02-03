from abc import ABC, abstractmethod
from typing import Optional

from domain.communication import CommunicationChannel, Message
from domain.command_bus import CommandBus


class Agent(ABC):
    """
    Abstract base class for all agents in the system.

    Each agent has a unique ID, a command bus to execute actions,
    a communication channel to interact with other agents, and a
    graph repository to interact with the knowledge graph.
    """

    def __init__(
        self,
        agent_id: str,
        command_bus: CommandBus,
        communication_channel: CommunicationChannel,
    ):
        self.agent_id = agent_id
        self.command_bus = command_bus
        self.communication_channel = communication_channel

    @abstractmethod
    async def process_messages(self) -> None:
        """
        The main loop for the agent to process incoming messages.
        """
        pass

    async def send_message(self, receiver_id: str, content: any) -> None:
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
