"""
Schema metadata model.

This module contains the Schema model that represents a database schema
containing tables and other database objects.
"""

from pydantic import Field
from typing import List, Optional
from .base import MetadataEntity


class Schema(MetadataEntity):
    """
    Schema entity representing a database schema.
    
    A schema is a logical container for database objects like tables, views,
    and functions. It belongs to a specific database.
    """
    
    database_id: str = Field(..., description="ID of the database containing this schema")
    schema_name: str = Field(..., description="Name of the schema in the database")
    owner: Optional[str] = Field(None, description="Schema owner")
    tables: List[str] = Field(default_factory=list, description="List of table IDs in this schema")
    views: List[str] = Field(default_factory=list, description="List of view IDs in this schema")
    functions: List[str] = Field(default_factory=list, description="List of function IDs in this schema")
    is_default: bool = Field(default=False, description="Whether this is the default schema")
    permissions: List[str] = Field(default_factory=list, description="List of permissions for this schema")
    
    def __init__(self, **data):
        data['entity_type'] = "Schema"
        super().__init__(**data)
    
    def add_table(self, table_id: str) -> None:
        """Add a table to this schema."""
        if table_id not in self.tables:
            self.tables.append(table_id)
            self.updated_at = self.updated_at.now()
    
    def remove_table(self, table_id: str) -> None:
        """Remove a table from this schema."""
        if table_id in self.tables:
            self.tables.remove(table_id)
            self.updated_at = self.updated_at.now()
    
    def add_view(self, view_id: str) -> None:
        """Add a view to this schema."""
        if view_id not in self.views:
            self.views.append(view_id)
            self.updated_at = self.updated_at.now()
    
    def remove_view(self, view_id: str) -> None:
        """Remove a view from this schema."""
        if view_id in self.views:
            self.views.remove(view_id)
            self.updated_at = self.updated_at.now()
    
    def add_function(self, function_id: str) -> None:
        """Add a function to this schema."""
        if function_id not in self.functions:
            self.functions.append(function_id)
            self.updated_at = self.updated_at.now()
    
    def remove_function(self, function_id: str) -> None:
        """Remove a function from this schema."""
        if function_id in self.functions:
            self.functions.remove(function_id)
            self.updated_at = self.updated_at.now()
    
    def add_permission(self, permission: str) -> None:
        """Add a permission to this schema."""
        if permission not in self.permissions:
            self.permissions.append(permission)
            self.updated_at = self.updated_at.now()
    
    def remove_permission(self, permission: str) -> None:
        """Remove a permission from this schema."""
        if permission in self.permissions:
            self.permissions.remove(permission)
            self.updated_at = self.updated_at.now()
    
    def get_object_count(self) -> int:
        """Get total count of objects in this schema."""
        return len(self.tables) + len(self.views) + len(self.functions)
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "schema-001",
                "name": "analytics_schema",
                "description": "Analytics schema for customer data",
                "database_id": "db-001",
                "schema_name": "analytics",
                "owner": "analytics_team",
                "tables": ["table-001", "table-002"],
                "views": ["view-001"],
                "functions": ["func-001"],
                "is_default": False,
                "permissions": ["SELECT", "INSERT", "UPDATE"]
            }
        }
