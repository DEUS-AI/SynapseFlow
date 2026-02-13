"""Dependency injection for FastAPI application."""

from functools import lru_cache
from typing import AsyncGenerator, Tuple, Optional
import os

from fastapi import Depends
from graphiti_core import Graphiti
from domain.kg_backends import KnowledgeGraphBackend
from application.event_bus import EventBus
from composition_root import bootstrap_graphiti, bootstrap_knowledge_management, bootstrap_patient_memory

# Global instances to hold state
_graphiti_instance: Graphiti | None = None
_kg_backend_instance: KnowledgeGraphBackend | None = None
_event_bus_instance: EventBus | None = None
_patient_memory_instance = None
_mem0_instance = None  # NEW: Mem0 instance for conversational layer
_chat_service_instance = None
_conversation_graph_instance = None  # LangGraph conversation engine
_neurosymbolic_service_instance = None
_episodic_memory_instance = None  # Graphiti-based episodic memory

# Layer transition services
_layer_transition_service = None
_promotion_scanner_job = None

# Crystallization pipeline services
_crystallization_service = None
_promotion_gate = None
_entity_resolver = None

# Temporal scoring service
_temporal_scoring_service = None

# Hypergraph analytics
_hypergraph_analytics_instance = None

# DIKW Router
_dikw_router_instance = None

# Agent instances
_data_architect_agent = None

async def get_graphiti() -> AsyncGenerator[Graphiti, None]:
    """Dependency to get Graphiti instance."""
    global _graphiti_instance
    if _graphiti_instance is None:
        _graphiti_instance = await bootstrap_graphiti(agent_name="api_server")
    yield _graphiti_instance

async def get_knowledge_management() -> Tuple[KnowledgeGraphBackend, EventBus]:
    """Internal helper to get KM components."""
    global _kg_backend_instance, _event_bus_instance
    if _kg_backend_instance is None or _event_bus_instance is None:
        _kg_backend_instance, _event_bus_instance = await bootstrap_knowledge_management()
    return _kg_backend_instance, _event_bus_instance

async def get_kg_backend() -> KnowledgeGraphBackend:
    """Dependency to get Knowledge Graph Backend."""
    backend, _ = await get_knowledge_management()
    return backend

async def get_event_bus() -> EventBus:
    """Dependency to get Event Bus."""
    _, bus = await get_knowledge_management()
    return bus

async def get_patient_memory():
    """Dependency to get Patient Memory Service."""
    global _patient_memory_instance, _mem0_instance
    if _patient_memory_instance is None:
        _patient_memory_instance, _mem0_instance = await bootstrap_patient_memory()
    return _patient_memory_instance


async def get_episodic_memory():
    """
    Get the Graphiti-based EpisodicMemoryService instance.

    This service provides episodic memory for conversations using Graphiti
    with FalkorDB backend. It extracts entities, stores conversation turns,
    and emits events for the crystallization pipeline.

    CRITICAL: This must be initialized and passed to ConversationGraph
    for entity extraction to work!
    """
    global _episodic_memory_instance, _event_bus_instance

    # Check if episodic memory is enabled
    if not os.getenv("ENABLE_EPISODIC_MEMORY", "").lower() in ("true", "1", "yes"):
        return None

    if _episodic_memory_instance is None:
        from composition_root import bootstrap_episodic_memory

        # Ensure event bus is initialized (for crystallization events)
        if _event_bus_instance is None:
            _, _event_bus_instance = await get_knowledge_management()

        _episodic_memory_instance = await bootstrap_episodic_memory(
            event_bus=_event_bus_instance
        )

        if _episodic_memory_instance:
            print("✅ EpisodicMemoryService initialized (FalkorDB + Graphiti)")
        else:
            print("⚠️ EpisodicMemoryService not available (check ENABLE_EPISODIC_MEMORY)")

    return _episodic_memory_instance


async def get_temporal_scoring_service():
    """
    Get the TemporalScoringService instance.

    This service provides entity-type specific temporal decay scoring,
    replacing the simple 7-day binary filter with exponential decay functions.
    """
    global _temporal_scoring_service

    if _temporal_scoring_service is None:
        from application.services.temporal_scoring import (
            TemporalScoringService,
            TemporalScoringConfig,
        )
        from domain.temporal_models import TemporalWindow

        # Configure temporal scoring from environment
        frequency_weight = float(os.getenv("TEMPORAL_SCORING_FREQUENCY_WEIGHT", "0.3"))
        min_threshold = float(os.getenv("TEMPORAL_SCORING_MIN_THRESHOLD", "0.05"))
        default_window = os.getenv("TEMPORAL_SCORING_DEFAULT_WINDOW", "short_term").lower()

        window_map = {
            "immediate": TemporalWindow.IMMEDIATE,
            "recent": TemporalWindow.RECENT,
            "short_term": TemporalWindow.SHORT_TERM,
            "medium_term": TemporalWindow.MEDIUM_TERM,
            "long_term": TemporalWindow.LONG_TERM,
            "historical": TemporalWindow.HISTORICAL,
        }

        config = TemporalScoringConfig(
            frequency_weight=frequency_weight,
            min_relevance_threshold=min_threshold,
            default_window=window_map.get(default_window, TemporalWindow.SHORT_TERM),
        )

        _temporal_scoring_service = TemporalScoringService(config=config)

        print(f"✅ TemporalScoringService initialized (frequency_weight={frequency_weight})")

    return _temporal_scoring_service


async def get_dikw_router():
    """
    Get the DIKWRouter instance.

    This router classifies query intent and routes to appropriate
    DIKW layers (FACTUAL→SEMANTIC, INFERENTIAL→REASONING, etc.).
    """
    global _dikw_router_instance

    if _dikw_router_instance is None:
        from application.services.dikw_router import DIKWRouter, DIKWRouterConfig

        # Configure router from environment
        enable_fallback = os.getenv("DIKW_ROUTER_ENABLE_FALLBACK", "true").lower() == "true"
        max_fallback_depth = int(os.getenv("DIKW_ROUTER_MAX_FALLBACK_DEPTH", "2"))

        config = DIKWRouterConfig(
            enable_fallback=enable_fallback,
            max_fallback_depth=max_fallback_depth,
        )

        _dikw_router_instance = DIKWRouter(config=config)

        print(f"✅ DIKWRouter initialized (fallback={enable_fallback})")

    return _dikw_router_instance


async def get_hypergraph_analytics():
    """
    Get the HypergraphAnalyticsService instance.

    This service provides hypergraph analytics (centrality, communities,
    connectivity) using HyperNetX over the Neo4j-persisted FactUnit graph.
    Returns None if HyperNetX is not installed.
    """
    global _hypergraph_analytics_instance

    if _hypergraph_analytics_instance is None:
        try:
            from infrastructure.hypernetx_adapter import HyperNetXAdapter, HNX_AVAILABLE
            from application.services.hypergraph_analytics_service import HypergraphAnalyticsService

            if not HNX_AVAILABLE:
                print("⚠️ HyperNetX not available — hypergraph analytics disabled")
                return None

            backend = await get_kg_backend()
            adapter = HyperNetXAdapter(neo4j_backend=backend)
            _hypergraph_analytics_instance = HypergraphAnalyticsService(adapter=adapter)

            print("✅ HypergraphAnalyticsService initialized")
        except ImportError:
            print("⚠️ HyperNetX not installed — hypergraph analytics disabled")
            return None

    return _hypergraph_analytics_instance


async def get_neurosymbolic_service():
    """Get the NeurosymbolicQueryService instance."""
    global _neurosymbolic_service_instance

    if _neurosymbolic_service_instance is None:
        from application.services.neurosymbolic_query_service import NeurosymbolicQueryService
        from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
        from domain.confidence_models import CrossLayerConfidencePropagation

        backend = await get_kg_backend()

        # Get hypergraph analytics for structural reasoning (optional)
        hypergraph_analytics = await get_hypergraph_analytics()

        reasoning_engine = ReasoningEngine(
            backend=backend,
            hypergraph_analytics=hypergraph_analytics,
        )
        confidence_propagator = CrossLayerConfidencePropagation()

        # Get temporal scoring service if enabled
        enable_temporal = os.getenv("ENABLE_TEMPORAL_SCORING", "true").lower() == "true"
        temporal_scoring = await get_temporal_scoring_service() if enable_temporal else None

        # Get DIKW router if enabled
        enable_intent_routing = os.getenv("ENABLE_INTENT_ROUTING", "true").lower() == "true"
        dikw_router = await get_dikw_router() if enable_intent_routing else None

        _neurosymbolic_service_instance = NeurosymbolicQueryService(
            backend=backend,
            reasoning_engine=reasoning_engine,
            confidence_propagator=confidence_propagator,
            temporal_scoring=temporal_scoring,
            dikw_router=dikw_router,
            enable_temporal_scoring=enable_temporal,
            enable_intent_routing=enable_intent_routing,
        )

        print(f"✅ NeurosymbolicQueryService initialized (temporal={enable_temporal}, intent_routing={enable_intent_routing})")

    return _neurosymbolic_service_instance


async def get_conversation_graph():
    """
    Get the LangGraph-based ConversationGraph instance.

    This is the new conversation engine that replaces the intent-based
    routing with a state machine approach.

    CRITICAL: Now includes EpisodicMemoryService for entity extraction!
    Without this, store_turn_episode() is never called and entities
    are not extracted from conversations.
    """
    global _conversation_graph_instance, _patient_memory_instance, _mem0_instance

    if _conversation_graph_instance is None:
        from application.services.conversation_graph import build_conversation_graph

        # Ensure patient memory is initialized
        if _patient_memory_instance is None:
            _patient_memory_instance, _mem0_instance = await bootstrap_patient_memory()

        # Get neurosymbolic service for knowledge retrieval
        neurosymbolic_service = await get_neurosymbolic_service()

        # CRITICAL: Get episodic memory service for entity extraction
        # This enables store_turn_episode() in conversation_nodes.py
        episodic_memory_service = await get_episodic_memory()

        _conversation_graph_instance = build_conversation_graph(
            patient_memory_service=_patient_memory_instance,
            neurosymbolic_service=neurosymbolic_service,
            episodic_memory_service=episodic_memory_service,  # CRITICAL for entity extraction!
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("CHAT_MODEL", "gpt-4o"),
        )

        if episodic_memory_service:
            print("✅ ConversationGraph (LangGraph) initialized with episodic memory")
        else:
            print("✅ ConversationGraph (LangGraph) initialized (no episodic memory)")

    return _conversation_graph_instance


async def get_chat_service():
    """
    Dependency to get Chat Service.

    Uses LangGraph-based ConversationGraph when ENABLE_LANGGRAPH_CHAT=true,
    otherwise falls back to the legacy IntelligentChatService.
    """
    global _chat_service_instance, _patient_memory_instance, _mem0_instance

    if _chat_service_instance is None:
        # Check if LangGraph chat is enabled (default: false for backward compatibility)
        use_langgraph = os.getenv("ENABLE_LANGGRAPH_CHAT", "false").lower() == "true"

        # Ensure patient memory is initialized
        if _patient_memory_instance is None:
            _patient_memory_instance, _mem0_instance = await bootstrap_patient_memory()

        if use_langgraph:
            # Use new LangGraph-based conversation engine
            from application.services.langgraph_chat_service import LangGraphChatService

            conversation_graph = await get_conversation_graph()

            _chat_service_instance = LangGraphChatService(
                conversation_graph=conversation_graph,
                patient_memory_service=_patient_memory_instance,
            )

            print("✅ LangGraphChatService initialized (LangGraph conversation engine)")
        else:
            # Use legacy IntelligentChatService
            from application.services.intelligent_chat_service import IntelligentChatService

            # Enable conversational layer if environment variable is set (default: True)
            enable_conversational = os.getenv("ENABLE_CONVERSATIONAL_LAYER", "true").lower() == "true"

            _chat_service_instance = IntelligentChatService(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                patient_memory_service=_patient_memory_instance,
                mem0=_mem0_instance,
                enable_conversational_layer=enable_conversational
            )

            print(f"✅ IntelligentChatService initialized (conversational_layer={enable_conversational})")

    return _chat_service_instance


async def get_layer_transition_service():
    """
    Get the AutomaticLayerTransitionService instance.

    This service subscribes to events and automatically promotes entities
    between layers (PERCEPTION → SEMANTIC → REASONING → APPLICATION)
    when they meet promotion criteria.
    """
    global _layer_transition_service

    if _layer_transition_service is None:
        from application.services.automatic_layer_transition import AutomaticLayerTransitionService

        backend = await get_kg_backend()
        event_bus = await get_event_bus()

        enable_auto = os.getenv("ENABLE_AUTO_PROMOTION", "true").lower() == "true"

        _layer_transition_service = AutomaticLayerTransitionService(
            backend=backend,
            event_bus=event_bus,
            enable_auto_promotion=enable_auto,
        )

        print(f"✅ AutomaticLayerTransitionService initialized (auto_promotion={enable_auto})")

    return _layer_transition_service


async def get_promotion_scanner():
    """
    Get the PromotionScannerJob instance.

    This background job periodically scans for entities that meet
    promotion criteria and promotes them.
    """
    global _promotion_scanner_job, _layer_transition_service

    if _promotion_scanner_job is None:
        from application.jobs.promotion_scanner import PromotionScannerJob

        # Ensure transition service is initialized
        transition_service = await get_layer_transition_service()

        scan_interval = int(os.getenv("PROMOTION_SCAN_INTERVAL", "300"))

        _promotion_scanner_job = PromotionScannerJob(
            transition_service=transition_service,
            scan_interval_seconds=scan_interval,
        )

        print(f"✅ PromotionScannerJob initialized (interval={scan_interval}s)")

    return _promotion_scanner_job


async def initialize_layer_services():
    """
    Initialize all layer management services on startup.

    Call this from the FastAPI startup event to ensure
    the automatic promotion pipeline is active.
    """
    # Initialize the transition service (which subscribes to events)
    await get_layer_transition_service()

    # Optionally start the background scanner
    if os.getenv("ENABLE_PROMOTION_SCANNER", "false").lower() == "true":
        scanner = await get_promotion_scanner()
        await scanner.start()
        print("🔄 Background promotion scanner started")


async def get_data_architect_agent():
    """
    Get the Data Architect Agent instance.

    This agent handles DDA processing and creates entities in the PERCEPTION layer.
    It publishes events for downstream processing by Knowledge Manager.
    """
    global _data_architect_agent

    if _data_architect_agent is None:
        from application.agents.data_architect.agent import DataArchitectAgent
        from domain.command_bus import CommandBus
        from domain.communication import InMemoryCommunicationChannel

        # Get dependencies
        backend = await get_kg_backend()
        event_bus = await get_event_bus()

        # Create minimal dependencies for the agent
        # Note: Some features (graph, llm) are optional for DDA processing
        command_bus = CommandBus()
        communication_channel = InMemoryCommunicationChannel()

        _data_architect_agent = DataArchitectAgent(
            agent_id="data_architect_api",
            command_bus=command_bus,
            communication_channel=communication_channel,
            graph=None,  # Not needed for DDA processing
            llm=None,    # Not needed for DDA processing
            url="http://localhost:8001",
            kg_backend=backend,
            event_bus=event_bus,
        )

        print("✅ DataArchitectAgent initialized")

    return _data_architect_agent


# ========================================
# Crystallization Pipeline Dependencies
# ========================================

async def get_crystallization_service():
    """
    Get the CrystallizationService instance.

    This service handles the transfer of entities from Graphiti/FalkorDB
    (episodic memory) to Neo4j (DIKW knowledge graph).
    """
    global _crystallization_service, _promotion_gate, _entity_resolver

    # Check if crystallization is enabled
    if not os.getenv("ENABLE_CRYSTALLIZATION", "").lower() in ("true", "1", "yes"):
        return None

    if _crystallization_service is None:
        from composition_root import bootstrap_crystallization_pipeline

        backend = await get_kg_backend()
        event_bus = await get_event_bus()

        _crystallization_service, _promotion_gate, _entity_resolver = (
            await bootstrap_crystallization_pipeline(
                neo4j_backend=backend,
                event_bus=event_bus,
            )
        )

        # Wire hypergraph adapter for cache invalidation on crystallization
        hypergraph_analytics = await get_hypergraph_analytics()
        if hypergraph_analytics and _crystallization_service:
            _crystallization_service._hypergraph_adapter = hypergraph_analytics.adapter

    return _crystallization_service


async def get_promotion_gate():
    """
    Get the PromotionGate instance.

    This service validates entity promotions between DIKW layers
    with medical-domain specific criteria.
    """
    global _promotion_gate

    # Ensure crystallization services are initialized
    if _promotion_gate is None:
        await get_crystallization_service()

    return _promotion_gate


async def get_entity_resolver():
    """
    Get the EntityResolver instance.

    This service handles cross-database entity deduplication
    between FalkorDB and Neo4j.
    """
    global _entity_resolver

    # Ensure crystallization services are initialized
    if _entity_resolver is None:
        await get_crystallization_service()

    return _entity_resolver


async def initialize_crystallization_pipeline():
    """
    Initialize the crystallization pipeline on startup.

    Call this from the FastAPI startup event to ensure
    the crystallization service is active.
    """
    if os.getenv("ENABLE_CRYSTALLIZATION", "").lower() in ("true", "1", "yes"):
        crystallization = await get_crystallization_service()
        if crystallization:
            print("✅ Crystallization pipeline initialized")
        else:
            print("⚠️ Crystallization pipeline failed to initialize")
