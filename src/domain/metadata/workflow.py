"""
Workflow and User metadata models.

This module contains models for workflow entities including Airflow DAGs
and users who interact with the metadata system.
"""

from pydantic import Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .base import MetadataEntity


class User(MetadataEntity):
    """
    User entity representing a person or system that interacts with metadata.
    
    Users can read, write, and manage metadata entities based on their
    roles and permissions.
    """
    
    username: str = Field(..., description="Unique username for the user")
    email: Optional[str] = Field(None, description="User's email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    role: str = Field(..., description="User's role in the system")
    department: Optional[str] = Field(None, description="User's department or team")
    is_active: bool = Field(default=True, description="Whether the user account is active")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    permissions: List[str] = Field(default_factory=list, description="List of user permissions")
    read_entities: List[str] = Field(default_factory=list, description="List of entity IDs the user can read")
    write_entities: List[str] = Field(default_factory=list, description="List of entity IDs the user can write")
    owned_entities: List[str] = Field(default_factory=list, description="List of entity IDs owned by the user")
    
    def __init__(self, **data):
        data['entity_type'] = "User"
        super().__init__(**data)
    
    def add_permission(self, permission: str) -> None:
        """Add a permission to the user."""
        if permission not in self.permissions:
            self.permissions.append(permission)
            self.updated_at = datetime.now()
    
    def remove_permission(self, permission: str) -> None:
        """Remove a permission from the user."""
        if permission in self.permissions:
            self.permissions.remove(permission)
            self.updated_at = datetime.now()
    
    def add_read_entity(self, entity_id: str) -> None:
        """Add read access to an entity."""
        if entity_id not in self.read_entities:
            self.read_entities.append(entity_id)
            self.updated_at = datetime.now()
    
    def remove_read_entity(self, entity_id: str) -> None:
        """Remove read access to an entity."""
        if entity_id in self.read_entities:
            self.read_entities.remove(entity_id)
            self.updated_at = datetime.now()
    
    def add_write_entity(self, entity_id: str) -> None:
        """Add write access to an entity."""
        if entity_id not in self.write_entities:
            self.write_entities.append(entity_id)
            self.updated_at = datetime.now()
    
    def remove_write_entity(self, entity_id: str) -> None:
        """Remove write access to an entity."""
        if entity_id in self.write_entities:
            self.write_entities.remove(entity_id)
            self.updated_at = datetime.now()
    
    def add_owned_entity(self, entity_id: str) -> None:
        """Add an entity to the user's ownership."""
        if entity_id not in self.owned_entities:
            self.owned_entities.append(entity_id)
            self.updated_at = datetime.now()
    
    def remove_owned_entity(self, entity_id: str) -> None:
        """Remove an entity from the user's ownership."""
        if entity_id in self.owned_entities:
            self.owned_entities.remove(entity_id)
            self.updated_at = datetime.now()
    
    def update_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login = datetime.now()
        self.updated_at = datetime.now()
    
    def deactivate(self) -> None:
        """Deactivate the user account."""
        self.is_active = False
        self.updated_at = datetime.now()
    
    def activate(self) -> None:
        """Activate the user account."""
        self.is_active = True
        self.updated_at = datetime.now()
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions
    
    def can_read(self, entity_id: str) -> bool:
        """Check if user can read a specific entity."""
        return entity_id in self.read_entities
    
    def can_write(self, entity_id: str) -> bool:
        """Check if user can write to a specific entity."""
        return entity_id in self.write_entities
    
    def owns(self, entity_id: str) -> bool:
        """Check if user owns a specific entity."""
        return entity_id in self.owned_entities
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "user-001",
                "name": "john_doe",
                "description": "Data Analyst",
                "username": "john_doe",
                "email": "john.doe@company.com",
                "full_name": "John Doe",
                "role": "Data Analyst",
                "department": "Data Team",
                "is_active": True,
                "permissions": ["read", "write"],
                "read_entities": ["table-001", "table-002"],
                "write_entities": ["table-001"],
                "owned_entities": ["table-001"]
            }
        }


class AirflowDag(MetadataEntity):
    """
    Airflow DAG entity representing an automated data pipeline.
    
    Airflow DAGs are used to orchestrate data workflows and can read from
    and write to various metadata entities.
    """
    
    dag_id: str = Field(..., description="Unique identifier for the DAG")
    schedule_interval: Optional[str] = Field(None, description="DAG schedule interval (cron expression)")
    owner: str = Field(..., description="Owner of the DAG")
    is_active: bool = Field(default=True, description="Whether the DAG is currently active")
    last_run: Optional[datetime] = Field(None, description="Last successful run timestamp")
    next_run: Optional[datetime] = Field(None, description="Next scheduled run timestamp")
    read_tables: List[str] = Field(default_factory=list, description="List of table IDs the DAG reads from")
    write_tables: List[str] = Field(default_factory=list, description="List of table IDs the DAG writes to")
    owned_tables: List[str] = Field(default_factory=list, description="List of table IDs owned by the DAG")
    tags: List[str] = Field(default_factory=list, description="DAG tags for categorization")
    retries: int = Field(default=3, description="Number of retries on failure")
    timeout: Optional[int] = Field(None, description="DAG timeout in seconds")
    description: Optional[str] = Field(None, description="DAG description")
    
    def __init__(self, **data):
        data['entity_type'] = "AirflowDag"
        super().__init__(**data)
    
    def add_read_table(self, table_id: str) -> None:
        """Add a table to the read tables list."""
        if table_id not in self.read_tables:
            self.read_tables.append(table_id)
            self.updated_at = datetime.now()
    
    def remove_read_table(self, table_id: str) -> None:
        """Remove a table from the read tables list."""
        if table_id in self.read_tables:
            self.read_tables.remove(table_id)
            self.updated_at = datetime.now()
    
    def add_write_table(self, table_id: str) -> None:
        """Add a table to the write tables list."""
        if table_id not in self.write_tables:
            self.write_tables.append(table_id)
            self.updated_at = datetime.now()
    
    def remove_write_table(self, table_id: str) -> None:
        """Remove a table from the write tables list."""
        if table_id in self.write_tables:
            self.write_tables.remove(table_id)
            self.updated_at = datetime.now()
    
    def add_owned_table(self, table_id: str) -> None:
        """Add a table to the owned tables list."""
        if table_id not in self.owned_tables:
            self.owned_tables.append(table_id)
            self.updated_at = datetime.now()
    
    def remove_owned_table(self, table_id: str) -> None:
        """Remove a table from the owned tables list."""
        if table_id in self.owned_tables:
            self.owned_tables.remove(table_id)
            self.updated_at = datetime.now()
    
    def update_last_run(self) -> None:
        """Update the last run timestamp."""
        self.last_run = datetime.now()
        self.updated_at = datetime.now()
    
    def set_next_run(self, next_run: datetime) -> None:
        """Set the next run timestamp."""
        self.next_run = next_run
        self.updated_at = datetime.now()
    
    def activate(self) -> None:
        """Activate the DAG."""
        self.is_active = True
        self.updated_at = datetime.now()
    
    def deactivate(self) -> None:
        """Deactivate the DAG."""
        self.is_active = False
        self.updated_at = datetime.now()
    
    def get_table_count(self) -> int:
        """Get the total number of tables associated with this DAG."""
        return len(set(self.read_tables + self.write_tables + self.owned_tables))
    
    def is_reading_table(self, table_id: str) -> bool:
        """Check if DAG reads from a specific table."""
        return table_id in self.read_tables
    
    def is_writing_table(self, table_id: str) -> bool:
        """Check if DAG writes to a specific table."""
        return table_id in self.write_tables
    
    def owns_table(self, table_id: str) -> bool:
        """Check if DAG owns a specific table."""
        return table_id in self.owned_tables
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "dag-001",
                "name": "customer_etl_pipeline",
                "description": "ETL pipeline for customer data",
                "dag_id": "customer_etl_pipeline",
                "schedule_interval": "0 2 * * *",
                "owner": "data_engineering_team",
                "is_active": True,
                "read_tables": ["table-001"],
                "write_tables": ["table-002"],
                "owned_tables": ["table-002"],
                "tags": ["etl", "customer", "daily"],
                "retries": 3,
                "timeout": 3600
            }
        }
