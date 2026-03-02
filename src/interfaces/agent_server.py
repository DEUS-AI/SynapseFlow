"""
Lightweight FastAPI server for running individual agents as isolated services.

Each agent container runs this server, which provides:
- GET /health: Health check endpoint with dependency status
- POST /v1/tasks/send: A2A receive endpoint for inbound messages
- RPC handler registration on startup (for distributed CommandBus)

Usage:
    python -m interfaces.agent_server --role data_architect --port 8001
"""

import argparse
import asyncio
import logging
import os
import sys
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from domain.communication import Message

logger = logging.getLogger(__name__)

# Valid agent roles (must match AGENT_REGISTRY in composition_root)
VALID_ROLES = {"data_architect", "data_engineer", "knowledge_manager", "medical_assistant", "echo"}

# Agent role to port mapping (defaults, can be overridden via --port)
DEFAULT_PORTS = {
    "data_architect": 8001,
    "data_engineer": 8002,
    "knowledge_manager": 8003,
    "medical_assistant": 8004,
    "echo": 8005,
}

# Required env vars per role
REQUIRED_ENV_VARS = {
    "__all__": ["NEO4J_URI", "NEO4J_PASSWORD", "OPENAI_API_KEY"],
    "medical_assistant": ["REDIS_HOST", "QDRANT_URL"],
}


class AgentServerState:
    """Holds the running state of the agent server."""

    def __init__(self, role: str):
        self.role = role
        self.agent = None
        self.event_bus = None
        self.kg_backend = None
        self.communication_channel = None
        self.command_bus = None
        self._message_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._healthy = False
        self._dependency_status: Dict[str, str] = {}

    @property
    def message_queues(self) -> Dict[str, asyncio.Queue]:
        return self._message_queues

    async def check_dependencies(self) -> Dict[str, str]:
        """Check connectivity to infrastructure dependencies."""
        status = {}

        # Check Neo4j
        try:
            if self.kg_backend and hasattr(self.kg_backend, "_get_driver"):
                driver = await self.kg_backend._get_driver()
                async with driver.session() as session:
                    await session.run("RETURN 1")
                status["neo4j"] = "connected"
            elif self.kg_backend:
                status["neo4j"] = "initialized_no_driver"
            else:
                status["neo4j"] = "not_initialized"
        except Exception as e:
            status["neo4j"] = f"disconnected: {e}"

        # Check RabbitMQ
        try:
            if self.event_bus and hasattr(self.event_bus, "is_connected"):
                status["rabbitmq"] = "connected" if self.event_bus.is_connected else "disconnected"
            elif self.event_bus:
                status["rabbitmq"] = "in_memory"
            else:
                status["rabbitmq"] = "not_initialized"
        except Exception as e:
            status["rabbitmq"] = f"error: {e}"

        self._dependency_status = status
        self._healthy = all(
            v in ("connected", "in_memory") for v in status.values()
        )
        return status


def validate_env_vars(role: str) -> None:
    """Validate required environment variables for the given role. Exits on failure."""
    missing = []

    for var in REQUIRED_ENV_VARS.get("__all__", []):
        if not os.environ.get(var):
            missing.append(var)

    for var in REQUIRED_ENV_VARS.get(role, []):
        if not os.environ.get(var):
            missing.append(var)

    if missing:
        print(
            f"FATAL: Agent '{role}' requires environment variables: {', '.join(missing)}\n"
            f"Set them in your environment or docker-compose configuration.",
            file=sys.stderr,
        )
        sys.exit(1)


async def bootstrap_agent(state: AgentServerState) -> None:
    """Bootstrap only the required agent and its dependencies."""
    from dotenv import load_dotenv
    load_dotenv()

    role = state.role
    logger.info(f"Bootstrapping agent: {role}")

    # Initialize knowledge management (Neo4j + EventBus)
    from composition_root import bootstrap_knowledge_management, bootstrap_command_bus

    state.kg_backend, state.event_bus = await bootstrap_knowledge_management()
    state.command_bus = bootstrap_command_bus()

    # Create communication channel (in-memory for now, A2A will be added in Phase 2)
    from infrastructure.communication.memory_channel import InMemoryCommunicationChannel
    state.communication_channel = InMemoryCommunicationChannel()

    # Create the specific agent
    from composition_root import AGENT_REGISTRY

    factory = AGENT_REGISTRY.get(role)
    if not factory:
        raise ValueError(f"Unknown agent role: {role}. Valid roles: {', '.join(AGENT_REGISTRY.keys())}")

    # Build agent-specific kwargs
    if role == "data_architect":
        from composition_root import bootstrap_graphiti
        graph = await bootstrap_graphiti(agent_name=role)
        state.agent = factory(
            agent_id=f"{role}_container",
            command_bus=state.command_bus,
            communication_channel=state.communication_channel,
            graph=graph,
            url=f"http://localhost:{DEFAULT_PORTS.get(role, 8001)}",
            kg_backend=state.kg_backend,
            event_bus=state.event_bus,
        )
    elif role == "data_engineer":
        from composition_root import bootstrap_graphiti
        graph = await bootstrap_graphiti(agent_name=role)
        state.agent = factory(
            agent_id=f"{role}_container",
            command_bus=state.command_bus,
            communication_channel=state.communication_channel,
            graph=graph,
            url=f"http://localhost:{DEFAULT_PORTS.get(role, 8002)}",
            kg_backend=state.kg_backend,
            event_bus=state.event_bus,
        )
    elif role == "knowledge_manager":
        state.agent = factory(
            agent_id=f"{role}_container",
            command_bus=state.command_bus,
            communication_channel=state.communication_channel,
            kg_backend=state.kg_backend,
            event_bus=state.event_bus,
        )
    elif role == "medical_assistant":
        from composition_root import bootstrap_patient_memory
        patient_memory_service, _ = await bootstrap_patient_memory()
        state.agent = factory(
            agent_id=f"{role}_container",
            command_bus=state.command_bus,
            communication_channel=state.communication_channel,
            patient_memory_service=patient_memory_service,
            url=f"http://localhost:{DEFAULT_PORTS.get(role, 8004)}",
        )
    elif role == "echo":
        state.agent = factory(
            agent_id=f"{role}_container",
            command_bus=state.command_bus,
            communication_channel=state.communication_channel,
            url=f"http://localhost:{DEFAULT_PORTS.get(role, 8005)}",
        )
    else:
        raise ValueError(f"No bootstrap logic for role: {role}")

    # Register RPC handler if using distributed mode (RabbitMQ available)
    if state.event_bus and hasattr(state.event_bus, "is_connected") and state.event_bus.is_connected:
        try:
            from infrastructure.command_bus.distributed_command_bus import DistributedCommandBus
            rabbitmq_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost/")
            distributed_bus = DistributedCommandBus(connection_url=rabbitmq_url)
            await distributed_bus.connect()
            await distributed_bus.register_rpc_handler(role, state.command_bus)
            logger.info(f"RPC handler registered on cmd_{role} queue")
        except Exception as e:
            logger.warning(f"Could not register RPC handler for {role}: {e}")

    logger.info(f"Agent '{role}' bootstrapped successfully")


def create_app(state: AgentServerState) -> FastAPI:
    """Create the FastAPI app for the agent server."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        logger.info(f"Starting agent server for role: {state.role}")
        try:
            await bootstrap_agent(state)
            await state.check_dependencies()
            logger.info(f"Agent '{state.role}' ready")
        except Exception as e:
            logger.error(f"Failed to bootstrap agent '{state.role}': {e}")
            raise
        yield
        # Shutdown
        logger.info(f"Shutting down agent '{state.role}'")

    app = FastAPI(
        title=f"SynapseFlow Agent: {state.role}",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        dep_status = await state.check_dependencies()
        is_healthy = all(
            v in ("connected", "in_memory") for v in dep_status.values()
        )
        status_code = 200 if is_healthy else 503
        body = {
            "status": "healthy" if is_healthy else "unhealthy",
            "agent": state.role,
            "dependencies": dep_status,
        }
        if not is_healthy:
            raise HTTPException(status_code=status_code, detail=body)
        return body

    # --- A2A Receive Endpoint ---

    class A2AMessagePayload(BaseModel):
        taskId: str
        message: Dict[str, Any]

    MAX_QUEUE_SIZE = int(os.environ.get("AGENT_MAX_QUEUE_SIZE", "1000"))

    @app.post("/v1/tasks/send")
    async def a2a_receive(payload: A2AMessagePayload):
        """Receive an inbound A2A message and enqueue it for the agent."""
        msg_data = payload.message

        # Validate required fields in message
        required_fields = ["sender_id", "receiver_id", "content"]
        missing = [f for f in required_fields if f not in msg_data]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required message fields: {', '.join(missing)}",
            )

        # Check queue capacity
        agent_id = msg_data["receiver_id"]
        queue = state.message_queues[agent_id]
        if queue.qsize() >= MAX_QUEUE_SIZE:
            raise HTTPException(
                status_code=429,
                detail={"error": "queue_full", "retry_after": 5},
            )

        # Reconstruct domain Message
        message = Message(
            id=msg_data.get("id", payload.taskId),
            sender_id=msg_data["sender_id"],
            receiver_id=msg_data["receiver_id"],
            content=msg_data["content"],
            metadata=msg_data.get("metadata", {}),
        )

        await queue.put(message)
        logger.info(f"A2A message received from {message.sender_id} for {message.receiver_id}")

        return {"status": "accepted", "taskId": message.id}

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SynapseFlow Agent Server")
    parser.add_argument(
        "--role",
        required=True,
        choices=sorted(VALID_ROLES),
        help="Agent role to run",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to listen on (defaults to role-specific port)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    role = args.role
    port = args.port or DEFAULT_PORTS.get(role, 8001)

    # Validate environment before starting
    validate_env_vars(role)

    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{role}] %(levelname)s %(name)s: %(message)s",
    )

    state = AgentServerState(role=role)
    app = create_app(state)

    logger.info(f"Starting {role} agent server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
