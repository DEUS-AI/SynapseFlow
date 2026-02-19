"""Knowledge manager service implementation.

This module provides a concrete implementation of the ``KnowledgeManager``
abstract base class defined in the domain.  The service uses a
``KnowledgeGraphBackend`` to persist events and enforces simple
role‑based access control (RBAC).  Additional reasoning, validation and
escalation logic can be layered on top of this service in the future.
"""


from domain.event import KnowledgeEvent
from domain.kg_backends import KnowledgeGraphBackend
from domain.knowledge_manager import KnowledgeManager
from domain.roles import Role


class KnowledgeManagerService(KnowledgeManager):
    """Concrete knowledge manager using a backend to apply events."""

    def __init__(self, backend: KnowledgeGraphBackend) -> None:
        self.backend = backend

    async def handle_event(self, event: KnowledgeEvent) -> None:
        """Handle a knowledge event with basic RBAC enforcement.

        Currently supports two actions:

        * ``create_entity`` – requires at least ``data_architect`` or ``data_engineer`` role.
        * ``create_relationship`` – requires ``knowledge_manager`` or ``system_admin`` role.

        Args:
            event: The event to process.

        Raises:
            PermissionError: If the caller role is not allowed to perform the action.
            ValueError: For unknown actions or missing required keys in the payload.
        """
        if event.action == "create_entity":
            if event.role not in {Role.DATA_ARCHITECT, Role.DATA_ENGINEER, Role.KNOWLEDGE_MANAGER, Role.SYSTEM_ADMIN}:
                raise PermissionError(f"Role {event.role} cannot create entities")
            entity_id = event.data.get("id")
            if entity_id is None:
                raise ValueError("'id' key required for create_entity")
            properties = event.data.get("properties", {})
            await self.backend.add_entity(entity_id, properties)
        elif event.action == "create_relationship":
            if event.role not in {Role.KNOWLEDGE_MANAGER, Role.SYSTEM_ADMIN}:
                raise PermissionError(f"Role {event.role} cannot create relationships")
            source = event.data.get("source")
            target = event.data.get("target")
            rel_type = event.data.get("type")
            if not (source and target and rel_type):
                raise ValueError("'source', 'target' and 'type' keys are required for create_relationship")
            properties = event.data.get("properties", {})
            await self.backend.add_relationship(source, rel_type, target, properties)
        else:
            raise ValueError(f"Unknown event action: {event.action}")