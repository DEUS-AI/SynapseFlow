"""Command Registry for serialization, deserialization, and agent routing.

Enables distributed command dispatch by:
1. Serializing Command objects to JSON-compatible dicts with type discriminators
2. Deserializing dicts back to typed Command objects
3. Routing commands to the correct agent role
"""

import json
import logging
from typing import Any, Dict, Optional, Type

from domain.commands import Command

logger = logging.getLogger(__name__)


class CommandDeserializationError(Exception):
    """Raised when a command cannot be deserialized."""

    def __init__(self, type_name: str, reason: str = ""):
        self.type_name = type_name
        super().__init__(f"Cannot deserialize command type '{type_name}': {reason}")


# Type discriminator field name in serialized payloads
COMMAND_TYPE_FIELD = "__command_type__"


class CommandRegistry:
    """Registry mapping command type names to classes and agent roles.

    Usage:
        registry = CommandRegistry()
        registry.register(ModelingCommand, "data_architect")

        # Serialize
        data = registry.serialize(ModelingCommand(dda_path="..."))
        # -> {"__command_type__": "ModelingCommand", "dda_path": "..."}

        # Deserialize
        cmd = registry.deserialize(data)
        # -> ModelingCommand(dda_path="...")

        # Route
        role = registry.get_agent_role(ModelingCommand)
        # -> "data_architect"
    """

    def __init__(self):
        self._type_to_class: Dict[str, Type[Command]] = {}
        self._type_to_role: Dict[str, str] = {}

    def register(self, command_class: Type[Command], agent_role: str) -> None:
        """Register a command class with its target agent role."""
        type_name = command_class.__name__
        self._type_to_class[type_name] = command_class
        self._type_to_role[type_name] = agent_role

    def serialize(self, command: Command) -> Dict[str, Any]:
        """Serialize a Command to a JSON-compatible dict with type discriminator.

        Supports both Pydantic BaseModel and dataclass commands.
        """
        type_name = type(command).__name__

        if type_name not in self._type_to_class:
            raise CommandDeserializationError(type_name, "not registered in registry")

        # Pydantic models use model_dump()
        if hasattr(command, "model_dump"):
            data = command.model_dump()
        # Fallback for dataclass-style commands
        elif hasattr(command, "__dict__"):
            data = {k: v for k, v in command.__dict__.items() if not k.startswith("_")}
        else:
            raise CommandDeserializationError(type_name, "unsupported command type")

        data[COMMAND_TYPE_FIELD] = type_name
        return data

    def deserialize(self, data: Dict[str, Any]) -> Command:
        """Deserialize a dict back to a typed Command object."""
        type_name = data.get(COMMAND_TYPE_FIELD)
        if not type_name:
            raise CommandDeserializationError("<missing>", f"no '{COMMAND_TYPE_FIELD}' field in payload")

        command_class = self._type_to_class.get(type_name)
        if not command_class:
            raise CommandDeserializationError(type_name, "not registered in registry")

        # Remove the type discriminator before constructing
        fields = {k: v for k, v in data.items() if k != COMMAND_TYPE_FIELD}

        # Pydantic models use model_validate()
        if hasattr(command_class, "model_validate"):
            return command_class.model_validate(fields)
        # Fallback for plain dataclass commands
        return command_class(**fields)

    def get_agent_role(self, command_or_type) -> Optional[str]:
        """Get the target agent role for a command class or instance."""
        if isinstance(command_or_type, Command):
            type_name = type(command_or_type).__name__
        elif isinstance(command_or_type, type):
            type_name = command_or_type.__name__
        else:
            type_name = str(command_or_type)
        return self._type_to_role.get(type_name)

    def serialize_result(self, result: Any) -> str:
        """Serialize a command result to JSON string."""
        if result is None:
            return json.dumps(None)
        if isinstance(result, (str, int, float, bool)):
            return json.dumps(result)
        if isinstance(result, dict):
            return json.dumps(result, default=str)
        if isinstance(result, list):
            return json.dumps(result, default=str)
        if hasattr(result, "model_dump"):
            return json.dumps(result.model_dump(), default=str)
        if hasattr(result, "__dict__"):
            return json.dumps(result.__dict__, default=str)
        return json.dumps(str(result))

    def deserialize_result(self, data: str) -> Any:
        """Deserialize a JSON string result."""
        return json.loads(data)


def create_default_registry() -> CommandRegistry:
    """Create a CommandRegistry with all known commands pre-registered."""
    registry = CommandRegistry()

    # Import commands lazily to avoid circular imports
    from application.commands.echo_command import EchoCommand
    from application.commands.modeling_command import ModelingCommand
    from application.commands.metadata_command import GenerateMetadataCommand

    # Register commands with their target agent roles
    registry.register(EchoCommand, "echo")
    registry.register(ModelingCommand, "data_architect")
    registry.register(GenerateMetadataCommand, "data_engineer")

    return registry
