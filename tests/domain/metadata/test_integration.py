"""Integration tests for the complete metadata system."""

import unittest
from datetime import datetime, timezone
from domain.metadata.base import MetadataEntity
from domain.metadata.database import Cluster, Database
from domain.metadata.schema import Schema
from domain.metadata.table import Table, Column, ColumnStats
from domain.metadata.metadata_objects import Tag, Watermark, Description
from domain.metadata.workflow import User, AirflowDag
from domain.metadata.relationships import MetadataRelationship, RelationshipTypes


class TestMetadataSystemIntegration(unittest.TestCase):
    """Test cases for complete metadata system integration."""
    
    def setUp(self):
        """Set up test fixtures for complete metadata system."""
        # Create users
        self.data_engineer = User(
            name="Data Engineer",
            username="data_eng",
            role="data_engineer",
            email="data_eng@company.com"
        )
        
        self.data_architect = User(
            name="Data Architect",
            username="data_arch",
            role="data_architect",
            email="data_arch@company.com"
        )
        
        # Create cluster
        self.production_cluster = Cluster(
            name="Production Cluster",
            description="Main production cluster",
            cluster_type="production",
            region="us-east-1",
            environment="prod"
        )
        
        # Create database
        self.analytics_db = Database(
            name="Analytics Database",
            description="Main analytics database",
            database_type="postgresql",
            version="15.0",
            cluster_id=self.production_cluster.id
        )
        
        # Create schema
        self.analytics_schema = Schema(
            name="Analytics Schema",
            description="Analytics data schema",
            database_id=self.analytics_db.id,
            schema_name="analytics"
        )
        
        # Create table
        self.customer_table = Table(
            name="Customer Table",
            description="Customer information table",
            schema_id=self.analytics_schema.id,
            table_name="customers"
        )
        
        # Create columns
        self.customer_id_column = Column(
            name="Customer ID Column",
            description="Unique customer identifier",
            table_id=self.customer_table.id,
            column_name="customer_id",
            data_type="integer",
            position=1
        )
        
        self.customer_name_column = Column(
            name="Customer Name Column",
            description="Customer full name",
            table_id=self.customer_table.id,
            column_name="customer_name",
            data_type="varchar",
            position=2
        )
        
        # Create column statistics
        self.customer_id_stats = ColumnStats(
            name="Customer ID Stats",
            description="Statistics for customer ID column",
            column_id=self.customer_id_column.id,
            row_count=10000,
            null_count=0,
            unique_count=10000,
            data_type="integer"
        )
        
        # Create metadata objects
        self.pii_tag = Tag(
            name="PII Tag",
            tag_name="PII Tag",
            description="Personally Identifiable Information",
            tag_type="security",
            color="#FF0000"
        )
        
        self.customer_watermark = Watermark(
            name="Customer Watermark",
            watermark_type="timestamp",
            watermark_value="2024-01-01T00:00:00Z",
            watermark_format="iso",
            entity_id=self.customer_table.id,
            entity_type="Table"
        )
        
        self.customer_description = Description(
            name="Customer Description",
            content="Customer information table containing personal data",
            entity_id=self.customer_table.id,
            entity_type="Table"
        )
        
        # Create workflow
        self.customer_etl_dag = AirflowDag(
            name="Customer ETL DAG",
            description="ETL pipeline for customer data",
            dag_id="customer_etl_pipeline",
            owner="data_engineering_team"
        )
        
        # Create relationships
        self.cluster_db_relationship = MetadataRelationship(
            name="Cluster Database Relationship",
            source_entity_id=self.production_cluster.id,
            source_entity_type="Cluster",
            target_entity_id=self.analytics_db.id,
            target_entity_type="Database",
            relationship_type="has_database"
        )
        
        self.db_schema_relationship = MetadataRelationship(
            name="Database Schema Relationship",
            source_entity_id=self.analytics_db.id,
            source_entity_type="Database",
            target_entity_id=self.analytics_schema.id,
            target_entity_type="Schema",
            relationship_type="has_schema"
        )
        
        self.schema_table_relationship = MetadataRelationship(
            name="Schema Table Relationship",
            source_entity_id=self.analytics_schema.id,
            source_entity_type="Schema",
            target_entity_id=self.customer_table.id,
            target_entity_type="Table",
            relationship_type="has_table"
        )
    
    def test_complete_metadata_hierarchy(self):
        """Test complete metadata hierarchy from cluster to column."""
        # Verify cluster -> database -> schema -> table -> column hierarchy
        self.assertEqual(self.production_cluster.name, "Production Cluster")
        self.assertEqual(self.analytics_db.name, "Analytics Database")
        self.assertEqual(self.analytics_schema.name, "Analytics Schema")
        self.assertEqual(self.customer_table.name, "Customer Table")
        self.assertEqual(self.customer_id_column.name, "Customer ID Column")
        
        # Verify relationships
        self.assertEqual(self.cluster_db_relationship.relationship_type, "has_database")
        self.assertEqual(self.db_schema_relationship.relationship_type, "has_schema")
        self.assertEqual(self.schema_table_relationship.relationship_type, "has_table")
    
    def test_metadata_tagging_system(self):
        """Test metadata tagging system."""
        # Add tag to table
        self.customer_table.add_tag(self.pii_tag.id)
        
        # Verify tag is added
        self.assertIn(self.pii_tag.id, self.customer_table.tags)
        
        # Verify tag properties
        self.assertEqual(self.pii_tag.tag_type, "security")
        self.assertEqual(self.pii_tag.color, "#FF0000")
    
    def test_metadata_watermark_system(self):
        """Test metadata watermark system."""
        # Verify watermark properties
        self.assertEqual(self.customer_watermark.watermark_type, "timestamp")
        self.assertEqual(self.customer_watermark.watermark_value, "2024-01-01T00:00:00Z")
        self.assertEqual(self.customer_watermark.entity_id, self.customer_table.id)
        
        # Note: activate_watermark is not implemented in the current model
        # We can only verify that the watermark is active by default
        self.assertTrue(self.customer_watermark.is_active)
    
    def test_metadata_description_system(self):
        """Test metadata description system."""
        # Verify description properties
        self.assertEqual(self.customer_description.content, "Customer information table containing personal data")
        self.assertEqual(self.customer_description.entity_id, self.customer_table.id)
        
        # Test description update
        self.customer_description.update_content("Updated customer table description", "test_user")
        self.assertEqual(self.customer_description.content, "Updated customer table description")
        self.assertEqual(self.customer_description.author, "test_user")
    
    def test_metadata_property_management(self):
        """Test metadata property management."""
        # Add custom properties to table
        self.customer_table.set_property("data_retention_days", 365)
        self.customer_table.set_property("data_classification", "confidential")
        
        # Verify properties
        self.assertEqual(self.customer_table.get_property("data_retention_days"), 365)
        self.assertEqual(self.customer_table.get_property("data_classification"), "confidential")
        
        # Note: remove_property is not implemented in the current model
        # We can only verify that properties can be set and retrieved
    
    def test_metadata_relationships_creation(self):
        """Test metadata relationships creation."""
        # Create table-column relationship
        table_column_relationship = MetadataRelationship(
            name="Table Column Relationship",
            source_entity_id=self.customer_table.id,
            source_entity_type="Table",
            target_entity_id=self.customer_id_column.id,
            target_entity_type="Column",
            relationship_type="has_column"
        )
        
        # Verify relationship
        self.assertEqual(table_column_relationship.relationship_type, "has_column")
        self.assertEqual(table_column_relationship.source_entity_type, "Table")
        self.assertEqual(table_column_relationship.target_entity_type, "Column")
        
        # Test reverse relationship
        reverse_type = table_column_relationship.get_reverse_relationship_type()
        self.assertEqual(reverse_type, "belongs_to_table")
    
    def test_workflow_integration(self):
        """Test workflow integration."""
        # Add tables to DAG
        self.customer_etl_dag.add_read_table(self.customer_table.id)
        self.customer_etl_dag.add_write_table(self.customer_table.id)
        
        # Verify DAG table associations
        self.assertTrue(self.customer_etl_dag.is_reading_table(self.customer_table.id))
        self.assertTrue(self.customer_etl_dag.is_writing_table(self.customer_table.id))
        
        # Verify DAG properties
        self.assertEqual(self.customer_etl_dag.owner, "data_engineering_team")
        self.assertTrue(self.customer_etl_dag.is_active)
    
    def test_user_permissions_and_access(self):
        """Test user permissions and access."""
        # Add permissions to users
        self.data_engineer.add_permission("read")
        self.data_engineer.add_permission("write")
        self.data_architect.add_permission("admin")
        
        # Verify permissions
        self.assertTrue(self.data_engineer.has_permission("read"))
        self.assertTrue(self.data_engineer.has_permission("write"))
        self.assertTrue(self.data_architect.has_permission("admin"))
        
        # Add entity access
        self.data_engineer.add_read_entity(self.customer_table.id)
        self.data_engineer.add_write_entity(self.customer_table.id)
        
        # Verify access
        self.assertTrue(self.data_engineer.can_read(self.customer_table.id))
        self.assertTrue(self.data_engineer.can_write(self.customer_table.id))
    
    def test_metadata_serialization(self):
        """Test metadata serialization."""
        # Test table serialization
        table_dict = self.customer_table.model_dump()
        self.assertIn("name", table_dict)
        self.assertIn("table_name", table_dict)
        self.assertIn("schema_id", table_dict)
        
        # Test column serialization
        column_dict = self.customer_id_column.model_dump()
        self.assertIn("name", column_dict)
        self.assertIn("column_name", column_dict)
        self.assertIn("data_type", column_dict)
        
        # Test tag serialization
        tag_dict = self.pii_tag.model_dump()
        self.assertIn("name", tag_dict)
        self.assertIn("tag_name", tag_dict)
        self.assertIn("tag_type", tag_dict)
    
    def test_metadata_validation_and_integrity(self):
        """Test metadata validation and integrity."""
        # Verify all entities have required fields
        entities = [
            self.production_cluster,
            self.analytics_db,
            self.analytics_schema,
            self.customer_table,
            self.customer_id_column,
            self.pii_tag,
            self.customer_watermark,
            self.customer_description
        ]
        
        for entity in entities:
            self.assertTrue(entity.name)
            self.assertTrue(entity.id)
            self.assertTrue(entity.entity_type)
        
        # Verify relationships have required fields
        relationships = [
            self.cluster_db_relationship,
            self.db_schema_relationship,
            self.schema_table_relationship
        ]
        
        for rel in relationships:
            self.assertTrue(rel.source_entity_id)
            self.assertTrue(rel.source_entity_type)
            self.assertTrue(rel.target_entity_id)
            self.assertTrue(rel.target_entity_type)
            self.assertTrue(rel.relationship_type)
    
    def test_metadata_system_performance(self):
        """Test metadata system performance."""
        # Test entity creation performance
        start_time = datetime.now()
        
        # Create multiple entities
        for i in range(100):
            tag = Tag(
                name=f"Test Tag {i}",
                tag_name=f"Test Tag {i}",
                tag_type="test"
            )
        
        end_time = datetime.now()
        creation_time = (end_time - start_time).total_seconds()
        
        # Verify reasonable performance (should be under 1 second for 100 entities)
        self.assertLess(creation_time, 1.0)
    
    def test_metadata_system_extensibility(self):
        """Test metadata system extensibility."""
        # Test custom properties on all entity types
        entities = [
            self.production_cluster,
            self.analytics_db,
            self.analytics_schema,
            self.customer_table,
            self.customer_id_column
        ]
        
        for entity in entities:
            entity.set_property("custom_property", "custom_value")
            self.assertEqual(entity.get_property("custom_property"), "custom_value")
        
        # Test custom properties on relationships
        self.cluster_db_relationship.add_property("custom_rel_property", "custom_rel_value")
        self.assertEqual(
            self.cluster_db_relationship.get_property("custom_rel_property"),
            "custom_rel_value"
        )


if __name__ == "__main__":
    unittest.main()
