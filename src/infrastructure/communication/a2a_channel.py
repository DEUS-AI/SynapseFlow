"""A2A (Agent-to-Agent) HTTP communication channel.

Implements bidirectional agent communication using HTTP POST.
- send(): POSTs messages to the target agent's /v1/tasks/send endpoint
- receive(): Returns messages from the inbound async queue (populated by the agent server)
- get_all_messages(): Drains the inbound queue
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import httpx

from domain.communication import CommunicationChannel, Message

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """Raised when a message targets an agent not in the configuration."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent '{agent_id}' not found in agent configuration")


class A2ACommunicationChannel(CommunicationChannel):
    """
    HTTP-based agent-to-agent communication channel.

    Resolves target agent URLs from the agent configuration (agents.yaml)
    and sends messages as JSON to each agent's /v1/tasks/send endpoint.

    The inbound queue is populated by the agent server's receive endpoint,
    making receive() return messages that arrived via HTTP.
    """

    def __init__(
        self,
        agent_urls: Optional[Dict[str, str]] = None,
        base_url: Optional[str] = None,
    ):
        """
        Args:
            agent_urls: Dict mapping agent role/id to base URL.
                        e.g. {"data_architect": "http://data_architect:8001"}
            base_url: Fallback base URL (legacy single-URL mode).
                      Used when agent_urls is not provided.
        """
        self._agent_urls: Dict[str, str] = agent_urls or {}
        self._base_url = base_url
        self._client = httpx.AsyncClient(timeout=30.0)
        self._inbound_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @classmethod
    def from_agent_config(cls, config) -> "A2ACommunicationChannel":
        """Create from an AgentInfraConfig instance.

        Builds the {role: url} lookup from the agents section of the config.
        """
        agent_urls = {}
        for name, agent_cfg in config.agents.items():
            if agent_cfg.enabled and agent_cfg.url:
                agent_urls[name] = agent_cfg.url
        base_url = config.communication_channel.a2a.base_url if hasattr(config, "communication_channel") else None
        return cls(agent_urls=agent_urls, base_url=base_url)

    def _resolve_url(self, agent_id: str) -> str:
        """Resolve the base URL for a target agent."""
        if agent_id in self._agent_urls:
            return self._agent_urls[agent_id]
        if self._base_url:
            return self._base_url
        raise AgentNotFoundError(agent_id)

    async def send(self, message: Message) -> None:
        """Send a message to another agent via HTTP POST.

        The wire format preserves all Message fields for faithful reconstruction.
        """
        target_url = self._resolve_url(message.receiver_id)
        endpoint = f"{target_url}/v1/tasks/send"

        # Serialize content — dicts stay as dicts, strings stay as strings
        content = message.content
        if isinstance(content, str):
            serialized_content = content
        else:
            serialized_content = content  # JSON-serializable dicts pass through

        payload = {
            "taskId": message.id,
            "message": {
                "id": message.id,
                "sender_id": message.sender_id,
                "receiver_id": message.receiver_id,
                "content": serialized_content,
                "metadata": message.metadata,
            },
        }

        try:
            response = await self._client.post(endpoint, json=payload)
            response.raise_for_status()
            logger.info(f"Message sent to {message.receiver_id} at {target_url} (status={response.status_code})")
        except httpx.HTTPStatusError as e:
            logger.error(f"Error sending message to {message.receiver_id}: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to agent {message.receiver_id} at {target_url}: {e}")
            raise

    async def receive(self, agent_id: str) -> Optional[Message]:
        """Return the next inbound message for the given agent, or None if empty.

        Messages are enqueued by the agent server's /v1/tasks/send endpoint.
        """
        queue = self._inbound_queues[agent_id]
        if not queue.empty():
            return await queue.get()
        return None

    async def get_all_messages(self, agent_id: str) -> List[Message]:
        """Drain all inbound messages for the given agent."""
        messages = []
        queue = self._inbound_queues[agent_id]
        while not queue.empty():
            messages.append(await queue.get())
        return messages

    async def enqueue_inbound(self, message: Message) -> None:
        """Enqueue a message received via the HTTP endpoint.

        Called by the agent server when it receives a POST /v1/tasks/send.
        """
        await self._inbound_queues[message.receiver_id].put(message)

    def queue_size(self, agent_id: str) -> int:
        """Return the current inbound queue size for an agent."""
        return self._inbound_queues[agent_id].qsize()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
