"""
Base metadata entity model.

This module contains the base class for all metadata entities in the knowledge graph.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4


class MetadataEntity(BaseModel):
    """
    Base class for all metadata entities in the knowledge graph.
    
    This class provides common fields and functionality for all metadata entities
    including Database, Cluster, Schema, Table, Column, etc.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the entity")
    name: str = Field(..., description="Human-readable name of the entity")
    description: Optional[str] = Field(None, description="Description of the entity")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    tags: List[str] = Field(default_factory=list, description="List of tags associated with the entity")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties for the entity")
    entity_type: str = Field(..., description="Type of the metadata entity")
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "customer_table",
                "description": "Customer information table",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00",
                "tags": ["customer", "core", "production"],
                "properties": {"owner": "data_team", "sensitivity": "medium"},
                "entity_type": "Table"
            }
        }
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the entity."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the entity."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()
    
    def set_property(self, key: str, value: Any) -> None:
        """Set a property value."""
        self.properties[key] = value
        self.updated_at = datetime.now()
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a property value."""
        return self.properties.get(key, default)
    
    def update_description(self, description: str) -> None:
        """Update the entity description."""
        self.description = description
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "properties": self.properties,
            "entity_type": self.entity_type
        }
