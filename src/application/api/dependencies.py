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

# Layer transition services
_layer_transition_service = None
_promotion_scanner_job = None

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

async def get_chat_service():
    """Dependency to get Intelligent Chat Service."""
    global _chat_service_instance, _patient_memory_instance, _mem0_instance

    if _chat_service_instance is None:
        from application.services.intelligent_chat_service import IntelligentChatService

        # Ensure patient memory is initialized
        if _patient_memory_instance is None:
            _patient_memory_instance, _mem0_instance = await bootstrap_patient_memory()

        # Enable conversational layer if environment variable is set (default: True)
        enable_conversational = os.getenv("ENABLE_CONVERSATIONAL_LAYER", "true").lower() == "true"

        _chat_service_instance = IntelligentChatService(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            patient_memory_service=_patient_memory_instance,
            mem0=_mem0_instance,  # NEW: Pass mem0 for conversational layer
            enable_conversational_layer=enable_conversational  # NEW: Enable conversational layer
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
