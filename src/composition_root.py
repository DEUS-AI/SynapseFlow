
# src/composition_root.py

from typing import Dict, Callable, Tuple, Optional
from application.agents.data_architect.agent import DataArchitectAgent
from application.agents.data_engineer.agent import DataEngineerAgent
from application.agents.knowledge_manager.agent import KnowledgeManagerAgent
from application.agents.medical_assistant.agent import MedicalAssistantAgent
from application.agents.data_engineer.handlers.build_kg import BuildKGCommandHandler
from application.agents.echo_agent import EchoAgent
from application.agents.knowledge_manager.agent import KnowledgeManagerAgent
from application.commands.base import CommandBus
from application.commands.collaboration_commands import BuildKGCommand
from application.commands.echo_command import EchoCommand, EchoCommandHandler
from application.commands.file_commands import (
    CreateFileCommand,
    CreateFileCommandHandler,
    ReadFileCommand,
    ReadFileCommandHandler,
)
from application.commands.shell_commands import (
    ExecuteShellCommand,
    ExecuteShellCommandHandler,
)
from application.commands.modeling_command import ModelingCommand
from application.commands.modeling_handler import ModelingCommandHandler
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_engineer.handlers.generate_metadata import GenerateMetadataCommandHandler
from application.agents.data_architect.modeling_workflow import ModelingWorkflow
from application.agents.data_architect.dda_parser import DDAParserFactory
from application.agents.data_architect.domain_modeler import DomainModeler
from application.agents.data_engineer.metadata_workflow import MetadataGenerationWorkflow
from application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from application.agents.data_engineer.type_inference import TypeInferenceService
from infrastructure.parsers.markdown_parser import MarkdownDDAParser
from domain.agent import Agent
from domain.communication import CommunicationChannel
from infrastructure.graphiti import get_graphiti
from graphiti_core import Graphiti
from infrastructure.in_memory_backend import InMemoryGraphBackend
from domain.kg_backends import KnowledgeGraphBackend
from application.event_bus import EventBus


# --- Agent Factory Functions ---

def create_echo_agent(
    agent_id: str,
    command_bus: CommandBus,
    communication_channel: CommunicationChannel,
    url: str,
) -> EchoAgent:
    """Creates an EchoAgent. agent_id is used for namespacing if needed."""
    return EchoAgent(
        agent_id=agent_id,
        command_bus=command_bus,
        communication_channel=communication_channel,
        url=url,
    )

def create_data_architect_agent(
    agent_id: str,
    command_bus: CommandBus,
    communication_channel: CommunicationChannel,
    graph: Graphiti,
    url: str,
    kg_backend: Optional[InMemoryGraphBackend] = None,
    event_bus: Optional[EventBus] = None,
) -> DataArchitectAgent:
    """Creates a DataArchitectAgent with a namespaced Graphiti graph and LLM."""
    return DataArchitectAgent(
        agent_id=agent_id,
        command_bus=command_bus,
        communication_channel=communication_channel,
        graph=graph,
        llm=graph,  # Use Graphiti for both graph and LLM
        url=url,
        kg_backend=kg_backend,
        event_bus=event_bus,
    )

def create_data_engineer_agent(
    agent_id: str,
    command_bus: CommandBus,
    communication_channel: CommunicationChannel,
    graph: Graphiti,
    url: str,
    kg_backend: Optional[InMemoryGraphBackend] = None,
    event_bus: Optional[EventBus] = None,
) -> DataEngineerAgent:
    """Creates a DataEngineerAgent with a namespaced Graphiti graph."""
    return DataEngineerAgent(
        agent_id=agent_id,
        command_bus=command_bus,
        communication_channel=communication_channel,
        graph=graph,
        url=url,
        kg_backend=kg_backend,
        event_bus=event_bus,
    )

def create_knowledge_manager_agent(
    agent_id: str,
    command_bus: CommandBus,
    communication_channel: CommunicationChannel,
    kg_backend: Optional[InMemoryGraphBackend] = None,
    event_bus: Optional[EventBus] = None,
    llm: Optional[Graphiti] = None,
) -> KnowledgeManagerAgent:
    """Creates a KnowledgeManagerAgent for complex knowledge graph operations."""
    # Use in-memory backend if none provided
    if kg_backend is None:
        kg_backend = InMemoryGraphBackend()

    # Use in-memory event bus if none provided
    if event_bus is None:
        event_bus = EventBus()

    return KnowledgeManagerAgent(
        agent_id=agent_id,
        command_bus=command_bus,
        communication_channel=communication_channel,
        backend=kg_backend,
        event_bus=event_bus,
        llm=llm,
    )

def create_medical_assistant_agent(
    agent_id: str,
    command_bus: CommandBus,
    communication_channel: CommunicationChannel,
    patient_memory_service,  # PatientMemoryService
    url: Optional[str] = None,
) -> MedicalAssistantAgent:
    """Creates a MedicalAssistantAgent for patient memory operations."""
    return MedicalAssistantAgent(
        agent_id=agent_id,
        command_bus=command_bus,
        communication_channel=communication_channel,
        patient_memory_service=patient_memory_service,
        url=url,
    )

def create_modeling_command_handler(neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> ModelingCommandHandler:
    """Creates a ModelingCommandHandler with all necessary dependencies."""
    # Create parser factory and register parsers
    parser_factory = DDAParserFactory()
    markdown_parser = MarkdownDDAParser()
    parser_factory.register_parser(markdown_parser)
    
    # Create modeling workflow with Neo4j credentials
    modeling_workflow = ModelingWorkflow(
        parser_factory,
        neo4j_uri,
        neo4j_user,
        neo4j_password
    )
    
    return ModelingCommandHandler(modeling_workflow)


def create_generate_metadata_command_handler(
    graph: Graphiti,
    kg_backend: InMemoryGraphBackend
) -> GenerateMetadataCommandHandler:
    """Creates a GenerateMetadataCommandHandler with all necessary dependencies."""
    # Create parser factory and register parsers
    parser_factory = DDAParserFactory()
    markdown_parser = MarkdownDDAParser()
    parser_factory.register_parser(markdown_parser)
    
    # Create type inference service (use Graphiti as LLM)
    type_inference = TypeInferenceService(graph)
    
    # Create metadata graph builder
    metadata_builder = MetadataGraphBuilder(kg_backend, type_inference)
    
    # Create metadata generation workflow
    metadata_workflow = MetadataGenerationWorkflow(
        parser_factory=parser_factory,
        metadata_builder=metadata_builder,
        graph=graph,
        kg_backend=kg_backend
    )
    
    return GenerateMetadataCommandHandler(metadata_workflow)


# Agent Registry
# Maps a role name to an agent factory function.
AGENT_REGISTRY: Dict[str, Callable[..., Agent]] = {
    "data_architect": create_data_architect_agent,
    "data_engineer": create_data_engineer_agent,
    "knowledge_manager": create_knowledge_manager_agent,
    "medical_assistant": create_medical_assistant_agent,
    "echo": create_echo_agent,
    "knowledge_manager": create_knowledge_manager_agent,
}


async def bootstrap_graphiti(agent_name: str | None = None) -> Graphiti:
    """Initializes the Graphiti instance from environment variables, namespaced by agent if agent_name is provided."""
    from dotenv import load_dotenv
    import os

    load_dotenv()

    graph_config = {
        "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j")),
        "password": os.environ.get("NEO4J_PASSWORD", "password"),
    }
    if agent_name:
        graph_config["name"] = agent_name
    return await get_graphiti(graph_config)


def bootstrap_command_bus() -> CommandBus:
    """Initializes and registers all command handlers."""
    command_bus = CommandBus()

    # Register handlers
    command_bus.register(EchoCommand, EchoCommandHandler())
    command_bus.register(CreateFileCommand, CreateFileCommandHandler())
    command_bus.register(ReadFileCommand, ReadFileCommandHandler())
    command_bus.register(
        ExecuteShellCommand,
        ExecuteShellCommandHandler(),
    )
    # Note: BuildKGCommand and ModelingCommand handlers require Graphiti instances
    # and are registered dynamically when needed in the CLI or agent creation
    
    # Note: RunAgentHandler is registered dynamically in the CLI
    # because it depends on a runtime agent instance.

    return command_bus



async def bootstrap_patient_memory():
    """Initialize patient memory service components."""
    import os
    from config.memory_config import create_memory_instance
    from infrastructure.redis_session_cache import RedisSessionCache
    from infrastructure.neo4j_backend import Neo4jBackend
    from application.services.patient_memory_service import PatientMemoryService

    print("🔄 Initializing Patient Memory Service...")

    try:
        # Initialize Mem0
        mem0 = create_memory_instance(
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USERNAME", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        print("  ✅ Mem0 initialized")

        # Initialize Neo4j backend
        neo4j = Neo4jBackend(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )
        print("  ✅ Neo4j backend initialized")

        # Initialize Redis cache
        redis = RedisSessionCache(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),  # Fixed: correct Redis default port
            db=int(os.getenv("REDIS_DB", "0")),
            ttl_seconds=int(os.getenv("REDIS_SESSION_TTL", "86400"))
        )
        print("  ✅ Redis session cache initialized")

        # Create patient memory service
        patient_memory_service = PatientMemoryService(mem0, neo4j, redis)
        print("✅ Patient Memory Service initialized")

        return patient_memory_service

    except Exception as e:
        print(f"⚠️ Failed to initialize Patient Memory Service: {e}")
        raise


async def bootstrap_knowledge_management() -> Tuple[KnowledgeGraphBackend, EventBus]:
    """Initialize knowledge management components."""
    import os
    from infrastructure.neo4j_backend import create_neo4j_backend
    from infrastructure.falkor_backend import FalkorBackend
    from infrastructure.graphiti_backend import GraphitiBackend
    from infrastructure.graphiti import get_graphiti
    
    backend_type = os.environ.get("KG_BACKEND", "neo4j").lower()
    kg_backend: KnowledgeGraphBackend
    
    print(f"🔄 Initializing Knowledge Graph Backend: {backend_type}")
    
    try:
        if backend_type == "falkordb":
            host = os.environ.get("FALKORDB_HOST", "localhost")
            port = int(os.environ.get("FALKORDB_PORT", 6379))
            kg_backend = FalkorBackend(host=host, port=port)
            print(f"✅ Using FalkorDB backend at {host}:{port}")
            
        elif backend_type == "graphiti":
            # Graphiti requires a Neo4j connection under the hood usually
            graphiti_client = await get_graphiti({
                "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                "user": os.environ.get("NEO4J_USERNAME", "neo4j"),
                "password": os.environ.get("NEO4J_PASSWORD", "password"),
            })
            kg_backend = GraphitiBackend(graphiti_client)
            print(f"✅ Using Graphiti backend")
            
        elif backend_type == "neo4j":
            kg_backend = await create_neo4j_backend()
            print(f"✅ Using Neo4j backend at {os.environ.get('NEO4J_URI', 'bolt://localhost:7687')}")
            
        else:
            kg_backend = InMemoryGraphBackend()
            print("✅ Using In-Memory backend")
            
    except Exception as e:
        print(f"⚠️ Failed to initialize {backend_type} backend: {e}. Falling back to in-memory.")
        kg_backend = InMemoryGraphBackend()
        
    # Initialize Event Bus
    event_bus_type = os.environ.get("EVENT_BUS_TYPE", "in_memory").lower()
    event_bus: EventBus
    
    print(f"🔄 Initializing Event Bus: {event_bus_type}")
    
    if event_bus_type == "rabbitmq":
        from infrastructure.event_bus.rabbitmq_event_bus import RabbitMQEventBus
        rabbitmq_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost/")
        event_bus = RabbitMQEventBus(connection_url=rabbitmq_url)
        # We need to connect, but this is async. 
        # Ideally we should await event_bus.connect() here, but we need to handle potential failures.
        try:
            # We can't await here easily if we want to keep the function signature simple?
            # Wait, this function IS async.
            await event_bus.connect()
            print(f"✅ Connected to RabbitMQ at {rabbitmq_url}")
        except Exception as e:
            print(f"⚠️ Failed to connect to RabbitMQ: {e}. Falling back to in-memory mode (local handlers only).")
            # RabbitMQEventBus falls back to local handlers automatically if not connected,
            # but we might want to explicitly fallback to simple EventBus if connection fails completely?
            # The RabbitMQEventBus implementation seems to handle disconnected state by using local handlers.
            # So we can keep using it, or switch to simple EventBus.
            # Let's keep using it but maybe log a warning.
            pass
    else:
        event_bus = EventBus()
        print("✅ Using In-Memory Event Bus")
    
    return kg_backend, event_bus
