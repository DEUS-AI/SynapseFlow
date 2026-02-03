"""
Database and Cluster metadata models.

This module contains models for database infrastructure entities including
Database and Cluster.
"""

from pydantic import Field
from typing import List, Optional
from .base import MetadataEntity


class Cluster(MetadataEntity):
    """
    Cluster entity representing a computational cluster where databases reside.
    
    A cluster can contain multiple databases and provides computational resources
    for data processing and storage.
    """
    
    cluster_type: str = Field(..., description="Type of cluster (e.g., 'production', 'development', 'staging')")
    region: Optional[str] = Field(None, description="Geographic region where the cluster is located")
    environment: str = Field(..., description="Environment type (prod, dev, test)")
    capacity: Optional[str] = Field(None, description="Cluster capacity information")
    status: str = Field(default="active", description="Current status of the cluster")
    databases: List[str] = Field(default_factory=list, description="List of database IDs in this cluster")
    
    def __init__(self, **data):
        data['entity_type'] = "Cluster"
        super().__init__(**data)
    
    def add_database(self, database_id: str) -> None:
        """Add a database to this cluster."""
        if database_id not in self.databases:
            self.databases.append(database_id)
            self.updated_at = self.updated_at.now()
    
    def remove_database(self, database_id: str) -> None:
        """Remove a database from this cluster."""
        if database_id in self.databases:
            self.databases.remove(database_id)
            self.updated_at = self.updated_at.now()
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "cluster-001",
                "name": "Production Cluster East",
                "description": "Primary production cluster in East region",
                "cluster_type": "production",
                "region": "us-east-1",
                "environment": "prod",
                "capacity": "large",
                "status": "active",
                "databases": ["db-001", "db-002"]
            }
        }


class Database(MetadataEntity):
    """
    Database entity representing a database instance.
    
    A database contains schemas and is hosted on a specific cluster.
    """
    
    cluster_id: Optional[str] = Field(None, description="ID of the cluster hosting this database")
    database_type: str = Field(..., description="Type of database (e.g., 'postgresql', 'mysql', 'mongodb')")
    version: Optional[str] = Field(None, description="Database version")
    schemas: List[str] = Field(default_factory=list, description="List of schema IDs in this database")
    connection_string: Optional[str] = Field(None, description="Database connection string (encrypted)")
    owner: Optional[str] = Field(None, description="Database owner or administrator")
    backup_schedule: Optional[str] = Field(None, description="Backup schedule information")
    
    def __init__(self, **data):
        data['entity_type'] = "Database"
        super().__init__(**data)
    
    def add_schema(self, schema_id: str) -> None:
        """Add a schema to this database."""
        if schema_id not in self.schemas:
            self.schemas.append(schema_id)
            self.updated_at = self.updated_at.now()
    
    def remove_schema(self, schema_id: str) -> None:
        """Remove a schema from this database."""
        if schema_id in self.schemas:
            self.schemas.remove(schema_id)
            self.updated_at = self.updated_at.now()
    
    def set_cluster(self, cluster_id: str) -> None:
        """Set the cluster for this database."""
        self.cluster_id = cluster_id
        self.updated_at = self.updated_at.now()
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "db-001",
                "name": "customer_analytics_db",
                "description": "Customer analytics database",
                "cluster_id": "cluster-001",
                "database_type": "postgresql",
                "version": "14.0",
                "schemas": ["public", "analytics"],
                "owner": "data_team",
                "backup_schedule": "daily"
            }
        }
