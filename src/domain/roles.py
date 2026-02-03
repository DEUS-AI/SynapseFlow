"""User roles for knowledge management.

Roles are represented as string enums to facilitate JSON serialisation and
deserialisation.  They are used to enforce simple RBAC policies when
applying knowledge events.  See `application.knowledge_management` for
specific rules.
"""

from enum import Enum


class Role(str, Enum):
    """Enumeration of roles supported by the knowledge management subsystem."""

    DATA_ARCHITECT = "data_architect"
    DATA_ENGINEER = "data_engineer"
    KNOWLEDGE_MANAGER = "knowledge_manager"
    MEDICAL_ASSISTANT = "medical_assistant"
    SYSTEM_ADMIN = "system_admin"
