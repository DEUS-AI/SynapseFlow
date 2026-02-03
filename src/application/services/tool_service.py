import inspect
from typing import Type
from pydantic import BaseModel

from domain.commands import Command
from domain.tool_definition import ToolDefinition


def command_to_tool_definition(command_cls: Type[Command]) -> ToolDefinition:
    """
    Introspects a Command Pydantic model and converts it into a ToolDefinition.
    """
    if not issubclass(command_cls, BaseModel):
        raise TypeError("Command must be a Pydantic model.")

    description = inspect.getdoc(command_cls) or ""
    
    properties = {}
    required = []

    for name, field in command_cls.model_fields.items():
        # A very basic type mapping. In a real scenario, this would be more robust.
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        
        properties[name] = {"type": type_mapping.get(field.annotation, "string")}
        if field.is_required():
            required.append(name)

    parameters_schema = {
        "type": "object",
        "properties": properties,
        "required": required,
    }

    return ToolDefinition(
        name=command_cls.__name__,
        description=description,
        parameters=parameters_schema,
    ) 