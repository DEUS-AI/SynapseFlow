"""Dependency injection for FastAPI application."""

from functools import lru_cache
from typing import AsyncGenerator, Tuple
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
_chat_service_instance = None

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
    global _patient_memory_instance
    if _patient_memory_instance is None:
        _patient_memory_instance = await bootstrap_patient_memory()
    return _patient_memory_instance

async def get_chat_service():
    """Dependency to get Intelligent Chat Service."""
    global _chat_service_instance, _patient_memory_instance

    if _chat_service_instance is None:
        from application.services.intelligent_chat_service import IntelligentChatService

        # Ensure patient memory is initialized
        if _patient_memory_instance is None:
            _patient_memory_instance = await bootstrap_patient_memory()

        _chat_service_instance = IntelligentChatService(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            patient_memory_service=_patient_memory_instance
        )

    return _chat_service_instance
