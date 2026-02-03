"""
Metadata objects models.

This module contains models for descriptive metadata objects including
tags, watermarks, and descriptions.
"""

from pydantic import Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .base import MetadataEntity


class Tag(MetadataEntity):
    """
    Tag entity representing a label or category for metadata entities.
    
    Tags are used to categorize and organize metadata entities for easier
    discovery and management.
    """
    
    tag_name: str = Field(..., description="Name of the tag")
    tag_value: Optional[str] = Field(None, description="Value associated with the tag")
    tag_type: str = Field(default="custom", description="Type of tag (e.g., 'custom', 'system', 'governance')")
    color: Optional[str] = Field(None, description="Color code for the tag (hex format)")
    category: Optional[str] = Field(None, description="Category this tag belongs to")
    entities: List[str] = Field(default_factory=list, description="List of entity IDs using this tag")
    is_system: bool = Field(default=False, description="Whether this is a system-generated tag")
    
    def __init__(self, **data):
        data['entity_type'] = "Tag"
        super().__init__(**data)
    
    def add_entity(self, entity_id: str) -> None:
        """Add an entity to this tag."""
        if entity_id not in self.entities:
            self.entities.append(entity_id)
            self.updated_at = datetime.now()
    
    def remove_entity(self, entity_id: str) -> None:
        """Remove an entity from this tag."""
        if entity_id in self.entities:
            self.entities.remove(entity_id)
            self.updated_at = datetime.now()
    
    def get_entity_count(self) -> int:
        """Get the number of entities using this tag."""
        return len(self.entities)
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "tag-001",
                "name": "PII",
                "description": "Personally Identifiable Information",
                "tag_name": "PII",
                "tag_value": "true",
                "tag_type": "governance",
                "color": "#FF0000",
                "category": "data_privacy",
                "entities": ["col-001", "col-002"],
                "is_system": False
            }
        }


class Watermark(MetadataEntity):
    """
    Watermark entity representing data freshness information.
    
    Watermarks track when data was last updated and provide information
    about data currency and reliability.
    """
    
    watermark_type: str = Field(..., description="Type of watermark (e.g., 'last_updated', 'data_freshness')")
    watermark_value: Any = Field(..., description="Value of the watermark (timestamp, version, etc.)")
    watermark_format: str = Field(..., description="Format of the watermark value")
    entity_id: str = Field(..., description="ID of the entity this watermark belongs to")
    entity_type: str = Field(..., description="Type of entity (Table, Column, etc.)")
    is_active: bool = Field(default=True, description="Whether this watermark is currently active")
    previous_watermark_id: Optional[str] = Field(None, description="ID of the previous watermark")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional watermark metadata")
    
    def __init__(self, **data):
        data['entity_type'] = "Watermark"
        super().__init__(**data)
    
    def deactivate(self) -> None:
        """Deactivate this watermark."""
        self.is_active = False
        self.updated_at = datetime.now()
    
    def activate(self) -> None:
        """Activate this watermark."""
        self.is_active = True
        self.updated_at = datetime.now()
    
    def set_previous_watermark(self, watermark_id: str) -> None:
        """Set the previous watermark reference."""
        self.previous_watermark_id = watermark_id
        self.updated_at = datetime.now()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the watermark."""
        self.metadata[key] = value
        self.updated_at = datetime.now()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from the watermark."""
        return self.metadata.get(key, default)
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "watermark-001",
                "name": "customer_table_watermark",
                "description": "Last update watermark for customer table",
                "watermark_type": "last_updated",
                "watermark_value": "2024-01-15T10:30:00",
                "watermark_format": "iso_timestamp",
                "entity_id": "table-001",
                "entity_type": "Table",
                "is_active": True,
                "metadata": {"source": "ETL_pipeline", "frequency": "hourly"}
            }
        }


class Description(MetadataEntity):
    """
    Description entity representing detailed information about metadata entities.
    
    Descriptions provide rich, contextual information about metadata entities
    including business context, usage guidelines, and technical details.
    """
    
    content: str = Field(..., description="The description content")
    content_type: str = Field(default="text", description="Type of content (text, markdown, html)")
    language: str = Field(default="en", description="Language of the description")
    entity_id: str = Field(..., description="ID of the entity this description belongs to")
    entity_type: str = Field(..., description="Type of entity being described")
    author: Optional[str] = Field(None, description="Author of the description")
    version: str = Field(default="1.0", description="Version of the description")
    is_approved: bool = Field(default=False, description="Whether this description is approved")
    approval_date: Optional[datetime] = Field(None, description="Date when description was approved")
    approver: Optional[str] = Field(None, description="Person who approved the description")
    previous_version_id: Optional[str] = Field(None, description="ID of the previous version")
    
    def __init__(self, **data):
        data['entity_type'] = "Description"
        super().__init__(**data)
    
    def approve(self, approver: str) -> None:
        """Approve this description."""
        self.is_approved = True
        self.approval_date = datetime.now()
        self.approver = approver
        self.updated_at = datetime.now()
    
    def unapprove(self) -> None:
        """Unapprove this description."""
        self.is_approved = False
        self.approval_date = None
        self.approver = None
        self.updated_at = datetime.now()
    
    def set_previous_version(self, version_id: str) -> None:
        """Set the previous version reference."""
        self.previous_version_id = version_id
        self.updated_at = datetime.now()
    
    def update_content(self, new_content: str, author: str) -> None:
        """Update the description content."""
        self.content = new_content
        self.author = author
        self.updated_at = datetime.now()
        # Reset approval status when content changes
        self.is_approved = False
        self.approval_date = None
        self.approver = None
    
    def get_word_count(self) -> int:
        """Get the word count of the description content."""
        return len(self.content.split())
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "desc-001",
                "name": "customer_table_description",
                "description": "Description for customer table",
                "content": "This table contains customer information including personal details, contact information, and account status.",
                "content_type": "text",
                "language": "en",
                "entity_id": "table-001",
                "entity_type": "Table",
                "author": "data_analyst_001",
                "version": "1.0",
                "is_approved": True,
                "approval_date": "2024-01-15T10:30:00",
                "approver": "data_governance_team"
            }
        }
