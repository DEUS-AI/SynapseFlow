"""
Metadata relationships model.

This module contains the MetadataRelationship model that represents
relationships between different metadata entities in the knowledge graph.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4


class MetadataRelationship(BaseModel):
    """
    Relationship between metadata entities in the knowledge graph.
    
    This model represents the edges in the metadata graph, connecting
    different entities with specific relationship types and properties.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the relationship")
    source_entity_id: str = Field(..., description="ID of the source entity")
    source_entity_type: str = Field(..., description="Type of the source entity")
    target_entity_id: str = Field(..., description="ID of the target entity")
    target_entity_type: str = Field(..., description="Type of the target entity")
    relationship_type: str = Field(..., description="Type of relationship")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties for the relationship")
    created_at: datetime = Field(default_factory=datetime.now, description="When the relationship was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="When the relationship was last updated")
    is_active: bool = Field(default=True, description="Whether the relationship is currently active")
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "rel-001",
                "source_entity_id": "db-001",
                "source_entity_type": "Database",
                "target_entity_id": "cluster-001",
                "target_entity_type": "Cluster",
                "relationship_type": "has_cluster",
                "properties": {"created_by": "system", "priority": "high"},
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00",
                "is_active": True
            }
        }
    
    def add_property(self, key: str, value: Any) -> None:
        """Add a property to the relationship."""
        self.properties[key] = value
        self.updated_at = datetime.now()
    
    def remove_property(self, key: str) -> None:
        """Remove a property from the relationship."""
        if key in self.properties:
            del self.properties[key]
            self.updated_at = datetime.now()
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a property value from the relationship."""
        return self.properties.get(key, default)
    
    def deactivate(self) -> None:
        """Deactivate the relationship."""
        self.is_active = False
        self.updated_at = datetime.now()
    
    def activate(self) -> None:
        """Activate the relationship."""
        self.is_active = True
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary representation."""
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "source_entity_type": self.source_entity_type,
            "target_entity_id": self.target_entity_id,
            "target_entity_type": self.target_entity_type,
            "relationship_type": self.relationship_type,
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active
        }
    
    def get_relationship_key(self) -> str:
        """Get a unique key for the relationship based on entities and type."""
        return f"{self.source_entity_id}:{self.relationship_type}:{self.target_entity_id}"
    
    def is_bidirectional(self) -> bool:
        """Check if this relationship type is bidirectional."""
        bidirectional_types = {
            "replicated_from",  # Table can be replicated from another table
            "previous"          # Stats can have previous versions
        }
        return self.relationship_type in bidirectional_types
    
    def get_reverse_relationship_type(self) -> Optional[str]:
        """Get the reverse relationship type if applicable."""
        reverse_mapping = {
            "has_cluster": "belongs_to_cluster",
            "has_schema": "belongs_to_schema",
            "has_column": "belongs_to_table",
            "has_tag": "tagged_by",
            "has_watermark": "watermarked_by",
            "has_description": "described_by",
            "has_stats": "statistics_for",
            "write_to_table": "written_by",
            "read_by": "read_by_user",
            "owned_by": "owner_of",
            "replicated_from": "replicated_to",
            "previous": "next"
        }
        return reverse_mapping.get(self.relationship_type)
    
    def create_reverse_relationship(self) -> Optional['MetadataRelationship']:
        """Create a reverse relationship if applicable."""
        reverse_type = self.get_reverse_relationship_type()
        if reverse_type:
            return MetadataRelationship(
                source_entity_id=self.target_entity_id,
                source_entity_type=self.target_entity_type,
                target_entity_id=self.source_entity_id,
                target_entity_type=self.source_entity_type,
                relationship_type=reverse_type,
                properties=self.properties.copy(),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        return None


# Predefined relationship types for consistency
class RelationshipTypes:
    """Constants for common relationship types."""
    
    # Database hierarchy relationships
    HAS_CLUSTER = "has_cluster"
    BELONGS_TO_CLUSTER = "belongs_to_cluster"
    HAS_SCHEMA = "has_schema"
    BELONGS_TO_SCHEMA = "belongs_to_schema"
    HAS_COLUMN = "has_column"
    BELONGS_TO_TABLE = "belongs_to_table"
    
    # Metadata relationships
    HAS_TAG = "has_tag"
    TAGGED_BY = "tagged_by"
    HAS_WATERMARK = "has_watermark"
    WATERMARKED_BY = "watermarked_by"
    HAS_DESCRIPTION = "has_description"
    DESCRIBED_BY = "described_by"
    HAS_STATS = "has_stats"
    STATISTICS_FOR = "statistics_for"
    
    # Workflow relationships
    WRITE_TO_TABLE = "write_to_table"
    WRITTEN_BY = "written_by"
    READ_BY = "read_by"
    READ_BY_USER = "read_by_user"
    OWNED_BY = "owned_by"
    OWNER_OF = "owner_of"
    
    # Special relationships
    REPLICATED_FROM = "replicated_from"
    REPLICATED_TO = "replicated_to"
    PREVIOUS = "previous"
    NEXT = "next"
    
    @classmethod
    def get_all_types(cls) -> list:
        """Get all available relationship types."""
        return [
            cls.HAS_CLUSTER, cls.BELONGS_TO_CLUSTER,
            cls.HAS_SCHEMA, cls.BELONGS_TO_SCHEMA,
            cls.HAS_COLUMN, cls.BELONGS_TO_TABLE,
            cls.HAS_TAG, cls.TAGGED_BY,
            cls.HAS_WATERMARK, cls.WATERMARKED_BY,
            cls.HAS_DESCRIPTION, cls.DESCRIBED_BY,
            cls.HAS_STATS, cls.STATISTICS_FOR,
            cls.WRITE_TO_TABLE, cls.WRITTEN_BY,
            cls.READ_BY, cls.READ_BY_USER,
            cls.OWNED_BY, cls.OWNER_OF,
            cls.REPLICATED_FROM, cls.REPLICATED_TO,
            cls.PREVIOUS, cls.NEXT
        ]
    
    @classmethod
    def is_valid_type(cls, relationship_type: str) -> bool:
        """Check if a relationship type is valid."""
        return relationship_type in cls.get_all_types()
