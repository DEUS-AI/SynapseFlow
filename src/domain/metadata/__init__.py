"""
Metadata models for the knowledge graph.

This module contains all the metadata entity models and their relationships
that represent the data catalog structure.
"""

from .base import MetadataEntity
from .database import Database, Cluster
from .schema import Schema
from .table import Table, Column, ColumnStats
from .metadata_objects import Tag, Watermark, Description
from .workflow import AirflowDag, User
from .relationships import MetadataRelationship, RelationshipTypes

__all__ = [
    "MetadataEntity",
    "Database",
    "Cluster", 
    "Schema",
    "Table",
    "Column",
    "ColumnStats",
    "Tag",
    "Watermark",
    "Description",
    "AirflowDag",
    "User",
    "MetadataRelationship",
    "RelationshipTypes"
]
