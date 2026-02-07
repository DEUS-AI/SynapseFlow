
# src/composition_root.py

from typing import Dict, Callable, Tuple, Optional, TYPE_CHECKING
from application.agents.data_architect.agent import DataArchitectAgent
from application.agents.data_engineer.agent import DataEngineerAgent
from application.agents.knowledge_manager.agent import KnowledgeManagerAgent
from application.agents.data_engineer.handlers.build_kg import BuildKGCommandHandler
from application.agents.echo_agent import EchoAgent

# Lazy import for MedicalAssistantAgent to avoid loading mem0 for agents that don't need it
if TYPE_CHECKING:
    from application.agents.medical_assistant.agent import MedicalAssistantAgent
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
from config.agent_config import get_agent_config, AgentInfraConfig
from infrastructure.agent_infrastructure_builder import AgentInfrastructureBuilder


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
):
    """Creates a MedicalAssistantAgent for patient memory operations.

    Note: Import is done lazily to avoid loading mem0 for agents that don't need it.
    """
    from application.agents.medical_assistant.agent import MedicalAssistantAgent
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
    """Initialize patient memory service components.

    Uses per-patient isolated Qdrant collections by default for HIPAA compliance.
    Set ENABLE_ISOLATED_PATIENT_MEMORY=false to use shared collection (NOT recommended).
    """
    import os
    from config.memory_config import create_memory_instance, create_isolated_memory_manager
    from infrastructure.redis_session_cache import RedisSessionCache
    from infrastructure.neo4j_backend import Neo4jBackend
    from application.services.patient_memory_service import PatientMemoryService

    print("🔄 Initializing Patient Memory Service...")

    # Use isolated memory by default for HIPAA compliance
    use_isolated_memory = os.getenv("ENABLE_ISOLATED_PATIENT_MEMORY", "true").lower() in ("true", "1", "yes")

    try:
        if use_isolated_memory:
            # RECOMMENDED: Per-patient Qdrant collections for true physical isolation
            mem0 = create_isolated_memory_manager(
                neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                neo4j_user=os.getenv("NEO4J_USERNAME", "neo4j"),
                neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
                qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
            print("  ✅ Mem0 initialized with ISOLATED per-patient collections (HIPAA compliant)")
        else:
            # Legacy: Shared collection with user_id filtering (NOT recommended for medical data)
            print("  ⚠️  WARNING: Using shared Mem0 collection. NOT recommended for medical data!")
            mem0 = create_memory_instance(
                neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                neo4j_user=os.getenv("NEO4J_USERNAME", "neo4j"),
                neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
                qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
            print("  ✅ Mem0 initialized (shared collection mode)")

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

        # Return both service and mem0 for conversational layer (Phase 6)
        return patient_memory_service, mem0

    except Exception as e:
        print(f"⚠️ Failed to initialize Patient Memory Service: {e}")
        raise


async def bootstrap_episodic_memory():
    """Initialize Graphiti-based episodic memory service with FalkorDB backend.

    This provides episodic memory for conversations, separate from the 3-layer
    memory architecture (Redis + Mem0 + Neo4j). The episodic memory uses:
    - FalkorDB: Episodic graph storage
    - Graphiti: Episode processing, entity extraction, edge inference

    Returns:
        EpisodicMemoryService or None if initialization fails
    """
    import os
    from application.services.feature_flag_service import is_flag_enabled

    # Check if episodic memory is enabled via feature flag
    # For now, we'll make it opt-in via environment variable since the feature flag might not exist yet
    if not os.getenv("ENABLE_EPISODIC_MEMORY", "").lower() in ("true", "1", "yes"):
        print("ℹ️  Episodic memory not enabled (set ENABLE_EPISODIC_MEMORY=true to enable)")
        return None

    print("🔄 Initializing Episodic Memory Service (Graphiti + FalkorDB)...")

    try:
        from application.services.episodic_memory_service import create_episodic_memory_service

        episodic_memory = await create_episodic_memory_service(
            falkordb_host=os.getenv("FALKORDB_HOST", "localhost"),
            falkordb_port=int(os.getenv("FALKORDB_PORT", "6379")),
            database_name=os.getenv("EPISODIC_MEMORY_DB", "episodic_memory"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

        print("✅ Episodic Memory Service initialized (FalkorDB + Graphiti)")
        return episodic_memory

    except ImportError as e:
        print(f"⚠️  Episodic memory dependencies not installed: {e}")
        print("   Install with: pip install graphiti-core[falkordb]")
        return None

    except Exception as e:
        print(f"⚠️  Failed to initialize Episodic Memory Service: {e}")
        print("   Continuing without episodic memory")
        return None


async def bootstrap_postgres_repositories():
    """Initialize PostgreSQL database and repositories.

    Returns:
        Tuple of (SessionRepository, MessageRepository, FeedbackRepository) or None values if disabled.
    """
    import os
    from application.services.feature_flag_service import is_flag_enabled

    # Only initialize if PostgreSQL features are enabled
    if not (is_flag_enabled("dual_write_sessions") or
            is_flag_enabled("use_postgres_sessions") or
            is_flag_enabled("dual_write_feedback") or
            is_flag_enabled("use_postgres_feedback")):
        print("ℹ️  PostgreSQL features not enabled, skipping initialization")
        return None, None, None

    print("🔄 Initializing PostgreSQL Database...")

    try:
        from infrastructure.database.session import init_database, db_session
        from infrastructure.database.repositories import (
            SessionRepository,
            MessageRepository,
            FeedbackRepository,
        )

        # Initialize database connection
        await init_database(create_tables=True)
        print("  ✅ PostgreSQL connection initialized")

        # Create repositories using a session context
        # Note: In production, you'd want to manage session lifecycle more carefully
        async with db_session() as session:
            session_repo = SessionRepository(session)
            message_repo = MessageRepository(session)
            feedback_repo = FeedbackRepository(session)

            print("✅ PostgreSQL repositories initialized")
            # Return factory functions that create repos with fresh sessions
            return session_repo, message_repo, feedback_repo

    except Exception as e:
        print(f"⚠️ Failed to initialize PostgreSQL: {e}")
        print("   Continuing with Neo4j-only mode")
        return None, None, None


def get_postgres_repository_factory():
    """Get a factory for creating PostgreSQL repositories.

    Returns a factory function that can create repository instances
    with proper session management.
    """
    from infrastructure.database.session import db_session
    from infrastructure.database.repositories import (
        SessionRepository,
        MessageRepository,
        FeedbackRepository,
    )

    class RepositoryFactory:
        """Factory for creating PostgreSQL repositories with managed sessions."""

        @staticmethod
        async def get_session_repo():
            """Get a SessionRepository with a new database session."""
            async with db_session() as session:
                return SessionRepository(session)

        @staticmethod
        async def get_message_repo():
            """Get a MessageRepository with a new database session."""
            async with db_session() as session:
                return MessageRepository(session)

        @staticmethod
        async def get_feedback_repo():
            """Get a FeedbackRepository with a new database session."""
            async with db_session() as session:
                return FeedbackRepository(session)

    return RepositoryFactory()


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


async def bootstrap_agent_infrastructure(
    config: Optional[AgentInfraConfig] = None,
    kg_backend: Optional[KnowledgeGraphBackend] = None,
) -> Tuple[EventBus, CommunicationChannel, Optional["AgentDiscoveryService"]]:
    """
    Bootstrap agent infrastructure using YAML configuration.

    This is the recommended way to initialize agent communication components.
    Uses config/agents.yaml by default, with environment variable overrides.

    Args:
        config: Optional custom configuration. If not provided, loads from
                config/agents.yaml with environment overrides.
        kg_backend: Optional KG backend for discovery service (required for
                    Neo4j-based discovery).

    Returns:
        Tuple of (EventBus, CommunicationChannel, AgentDiscoveryService or None)

    Usage:
        # Simple usage (loads config/agents.yaml)
        event_bus, channel, discovery = await bootstrap_agent_infrastructure()

        # With custom config
        config = AgentInfraConfig.from_yaml("custom/path.yaml")
        event_bus, channel, discovery = await bootstrap_agent_infrastructure(config)

        # With existing KG backend for discovery
        kg_backend, _ = await bootstrap_knowledge_management()
        event_bus, channel, discovery = await bootstrap_agent_infrastructure(
            kg_backend=kg_backend
        )
    """
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from application.services.agent_discovery import AgentDiscoveryService

    builder = AgentInfrastructureBuilder(config)

    print(f"🔄 Bootstrapping agent infrastructure...")
    print(f"   Deployment mode: {builder.config.deployment_mode.value}")
    print(f"   Event bus: {builder.config.event_bus.type.value}")
    print(f"   Channel: {builder.config.communication_channel.type.value}")
    print(f"   Discovery: {builder.config.discovery.type.value}")

    # Build components
    event_bus = await builder.build_event_bus()
    channel = builder.build_communication_channel()
    discovery = await builder.build_discovery_service(backend=kg_backend)

    print("✅ Agent infrastructure bootstrapped")

    return event_bus, channel, discovery


def get_infrastructure_builder(
    config: Optional[AgentInfraConfig] = None
) -> AgentInfrastructureBuilder:
    """
    Get an infrastructure builder for creating agent components.

    This is useful when you need more control over component creation,
    or want to create multiple channels with different configurations.

    Args:
        config: Optional custom configuration.

    Returns:
        AgentInfrastructureBuilder instance

    Usage:
        builder = get_infrastructure_builder()

        # Build components as needed
        event_bus = await builder.build_event_bus()
        channel = builder.build_communication_channel(agent_url="http://my-agent:8001")

        # Check if specific agents are enabled
        if builder.is_agent_enabled("knowledge_manager"):
            km_url = builder.get_agent_url("knowledge_manager")
    """
    return AgentInfrastructureBuilder(config)
