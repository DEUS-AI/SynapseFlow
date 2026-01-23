"""Pytest configuration for metadata tests."""

import pytest
import os
import sys

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "..", "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


@pytest.fixture
def sample_metadata_entities():
    """Provide sample metadata entities for testing."""
    from domain.metadata.base import MetadataEntity
    from domain.metadata.database import Cluster, Database
    from domain.metadata.schema import Schema
    from domain.metadata.table import Table, Column
    from domain.metadata.metadata_objects import Tag, Watermark, Description
    from domain.metadata.workflow import User

    # Create sample entities
    cluster = Cluster(
        name="Test Cluster",
        cluster_type="development",
        environment="dev"
    )

    database = Database(
        name="Test Database",
        database_type="postgresql",
        cluster_id=cluster.id
    )

    schema = Schema(
        name="Test Schema",
        database_id=database.id,
        schema_name="test"
    )

    table = Table(
        name="Test Table",
        schema_id=schema.id,
        table_name="test_table"
    )

    column = Column(
        name="Test Column",
        table_id=table.id,
        column_name="test_column",
        data_type="integer",
        position=1
    )

    tag = Tag(
        tag_name="Test Tag",
        tag_type="business"
    )

    watermark = Watermark(
        name="Test Watermark",
        watermark_type="timestamp",
        watermark_value="2024-01-01T00:00:00Z",
        watermark_format="iso_timestamp",
        entity_id=table.id
    )

    description = Description(
        name="Test Description",
        content="Test description content",
        entity_id=table.id,
        entity_type="Table"
    )

    user = User(
        name="Test User",
        username="testuser",
        role="data_engineer"
    )

    return {
        "cluster": cluster,
        "database": database,
        "schema": schema,
        "table": table,
        "column": column,
        "tag": tag,
        "watermark": watermark,
        "description": description,
        "user": user
    }


@pytest.fixture
def sample_relationships():
    """Provide sample relationships for testing."""
    from domain.metadata.relationships import MetadataRelationship, RelationshipTypes

    # Create sample relationships
    db_schema_rel = MetadataRelationship(
        name="Database Schema Relationship",
        source_entity_id="db-001",
        source_entity_type="Database",
        target_entity_id="schema-001",
        target_entity_type="Schema",
        relationship_type="has_schema"
    )

    schema_table_rel = MetadataRelationship(
        name="Schema Table Relationship",
        source_entity_id="schema-001",
        source_entity_type="Schema",
        target_entity_id="table-001",
        target_entity_type="Table",
        relationship_type="has_table"
    )

    table_column_rel = MetadataRelationship(
        name="Table Column Relationship",
        source_entity_id="table-001",
        source_entity_type="Table",
        target_entity_id="col-001",
        target_entity_type="Column",
        relationship_type="has_column"
    )

    return {
        "db_schema": db_schema_rel,
        "schema_table": schema_table_rel,
        "table_column": table_column_rel
    }


@pytest.fixture
def relationship_types():
    """Provide relationship types for testing."""
    from domain.metadata.relationships import RelationshipTypes
    return RelationshipTypes
