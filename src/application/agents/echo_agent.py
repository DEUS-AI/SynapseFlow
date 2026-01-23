from domain.agent import Agent
from domain.communication import CommunicationChannel
from domain.command_bus import CommandBus
from typing import Optional


class EchoAgent(Agent):
    """
    A simple agent that echoes back any message it receives.
    """

    def __init__(
        self,
        agent_id: str,
        command_bus: CommandBus,
        communication_channel: CommunicationChannel,
        url: str,
    ):
        super().__init__(
            agent_id, command_bus, communication_channel
        )
        self.url = url

    async def process_messages(self) -> None:
        """
        Continuously checks for messages and echoes them back.
        """
        print(f"[{self.agent_id}] Waiting for messages...")
        message = await self.receive_message()
        if message:
            print(f"[{self.agent_id}] Received message: {message.content}")
            # Echo the content back to the sender
            await self.send_message(
                receiver_id=message.sender_id, content=f"Echo: {message.content}"
            )
            print(f"[{self.agent_id}] Echoed message back to {message.sender_id}") 