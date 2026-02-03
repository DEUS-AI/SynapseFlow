from pydantic import BaseModel
from typing import List
from domain.tool_definition import ToolDefinition


class AgentDefinition(BaseModel):
    """
    Represents the public definition of an agent, typically served
    at /.well-known/agent.json
    """
    name: str
    description: str
    version: str
    tools: List[ToolDefinition] 