from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class KnowledgeLayer(str, Enum):
    """Layers of the Knowledge Graph."""
    PERCEPTION = "PERCEPTION"   # Raw data, tables, columns, files
    SEMANTIC = "SEMANTIC"       # Business concepts, entities, relationships
    REASONING = "REASONING"     # Inferred knowledge, rules, patterns
    APPLICATION = "APPLICATION" # Use cases, queries, views

class LayeredEntity(BaseModel):
    """An entity in the layered knowledge graph."""
    id: str
    name: str
    layer: KnowledgeLayer
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def full_id(self) -> str:
        """Get the fully qualified ID including layer."""
        return f"{self.layer}:{self.type}:{self.id}"

class LayeredRelationship(BaseModel):
    """A relationship in the layered knowledge graph."""
    source_id: str
    target_id: str
    type: str
    layer: KnowledgeLayer
    properties: Dict[str, Any] = Field(default_factory=dict)
