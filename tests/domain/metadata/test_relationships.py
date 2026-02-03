"""Tests for metadata relationships."""

import unittest
from datetime import datetime, timezone
from domain.metadata.relationships import MetadataRelationship, RelationshipTypes


class TestRelationshipTypes(unittest.TestCase):
    """Test cases for RelationshipTypes constants."""
    
    def test_relationship_types_constants(self):
        """Test that all relationship type constants are defined."""
        # Test database relationships
        self.assertEqual(RelationshipTypes.HAS_CLUSTER, "has_cluster")
        self.assertEqual(RelationshipTypes.HAS_SCHEMA, "has_schema")
        self.assertEqual(RelationshipTypes.BELONGS_TO_SCHEMA, "belongs_to_schema")
        self.assertEqual(RelationshipTypes.HAS_COLUMN, "has_column")
        self.assertEqual(RelationshipTypes.BELONGS_TO_TABLE, "belongs_to_table")
        
        # Test metadata relationships
        self.assertEqual(RelationshipTypes.HAS_TAG, "has_tag")
        self.assertEqual(RelationshipTypes.TAGGED_BY, "tagged_by")
        self.assertEqual(RelationshipTypes.HAS_WATERMARK, "has_watermark")
        self.assertEqual(RelationshipTypes.WATERMARKED_BY, "watermarked_by")
        self.assertEqual(RelationshipTypes.HAS_DESCRIPTION, "has_description")
        self.assertEqual(RelationshipTypes.DESCRIBED_BY, "described_by")
        self.assertEqual(RelationshipTypes.HAS_STATS, "has_stats")
        self.assertEqual(RelationshipTypes.STATISTICS_FOR, "statistics_for")
        
        # Test workflow relationships
        self.assertEqual(RelationshipTypes.WRITE_TO_TABLE, "write_to_table")
        self.assertEqual(RelationshipTypes.WRITTEN_BY, "written_by")
        self.assertEqual(RelationshipTypes.READ_BY, "read_by")
        self.assertEqual(RelationshipTypes.READ_BY_USER, "read_by_user")
        self.assertEqual(RelationshipTypes.OWNED_BY, "owned_by")
        self.assertEqual(RelationshipTypes.OWNER_OF, "owner_of")
        
        # Test special relationships
        self.assertEqual(RelationshipTypes.REPLICATED_FROM, "replicated_from")
        self.assertEqual(RelationshipTypes.REPLICATED_TO, "replicated_to")
        self.assertEqual(RelationshipTypes.PREVIOUS, "previous")
        self.assertEqual(RelationshipTypes.NEXT, "next")
    
    def test_get_all_types(self):
        """Test getting all relationship types."""
        all_types = RelationshipTypes.get_all_types()
        self.assertIsInstance(all_types, list)
        self.assertIn("has_cluster", all_types)
        self.assertIn("has_schema", all_types)
        self.assertIn("has_tag", all_types)
        self.assertIn("write_to_table", all_types)
    
    def test_is_valid_type(self):
        """Test relationship type validation."""
        # Test valid types
        self.assertTrue(RelationshipTypes.is_valid_type("has_cluster"))
        self.assertTrue(RelationshipTypes.is_valid_type("has_schema"))
        self.assertTrue(RelationshipTypes.is_valid_type("has_tag"))
        self.assertTrue(RelationshipTypes.is_valid_type("write_to_table"))
        
        # Test invalid types
        self.assertFalse(RelationshipTypes.is_valid_type("invalid_type"))
        self.assertFalse(RelationshipTypes.is_valid_type("has_table"))  # Not in the list
        self.assertFalse(RelationshipTypes.is_valid_type(""))


class TestMetadataRelationship(unittest.TestCase):
    """Test cases for MetadataRelationship model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.relationship = MetadataRelationship(
            name="test_relationship",
            source_entity_id="source-001",
            source_entity_type="Database",
            target_entity_id="target-001",
            target_entity_type="Schema",
            relationship_type="has_schema"
        )
    
    def test_relationship_creation(self):
        """Test that relationship is created with correct attributes."""
        self.assertEqual(self.relationship.source_entity_id, "source-001")
        self.assertEqual(self.relationship.source_entity_type, "Database")
        self.assertEqual(self.relationship.target_entity_id, "target-001")
        self.assertEqual(self.relationship.target_entity_type, "Schema")
        self.assertEqual(self.relationship.relationship_type, "has_schema")
        self.assertTrue(self.relationship.is_active)
        self.assertEqual(self.relationship.properties, {})
    
    def test_relationship_default_values(self):
        """Test relationship default values."""
        minimal_relationship = MetadataRelationship(
            name="minimal_relationship",
            source_entity_id="source-001",
            source_entity_type="Database",
            target_entity_id="target-001",
            target_entity_type="Schema",
            relationship_type="has_schema"
        )
        self.assertTrue(minimal_relationship.is_active)
        self.assertEqual(minimal_relationship.properties, {})
        self.assertIsInstance(minimal_relationship.created_at, datetime)
        self.assertIsInstance(minimal_relationship.updated_at, datetime)
    
    def test_relationship_with_custom_properties(self):
        """Test relationship with custom properties."""
        relationship = MetadataRelationship(
            name="custom_relationship",
            source_entity_id="source-001",
            source_entity_type="Database",
            target_entity_id="target-001",
            target_entity_type="Schema",
            relationship_type="has_schema",
            properties={"strength": "strong", "priority": "high"}
        )
        self.assertEqual(relationship.properties["strength"], "strong")
        self.assertEqual(relationship.properties["priority"], "high")
    
    def test_add_property(self):
        """Test adding property to relationship."""
        self.relationship.add_property("strength", "strong")
        self.relationship.add_property("priority", "high")
        
        self.assertEqual(self.relationship.get_property("strength"), "strong")
        self.assertEqual(self.relationship.get_property("priority"), "high")
    
    def test_remove_property(self):
        """Test removing property from relationship."""
        self.relationship.add_property("strength", "strong")
        self.relationship.add_property("priority", "high")
        
        self.relationship.remove_property("strength")
        self.assertIsNone(self.relationship.get_property("strength"))
        self.assertEqual(self.relationship.get_property("priority"), "high")
    
    def test_get_property(self):
        """Test getting property from relationship."""
        self.relationship.add_property("strength", "strong")
        
        self.assertEqual(self.relationship.get_property("strength"), "strong")
        self.assertEqual(self.relationship.get_property("nonexistent", "default"), "default")
        self.assertIsNone(self.relationship.get_property("nonexistent"))
    
    def test_activate_deactivate(self):
        """Test activating and deactivating relationship."""
        self.relationship.deactivate()
        self.assertFalse(self.relationship.is_active)
        
        self.relationship.activate()
        self.assertTrue(self.relationship.is_active)
    
    def test_to_dict(self):
        """Test converting relationship to dictionary."""
        relationship_dict = self.relationship.to_dict()
        
        self.assertIn("id", relationship_dict)
        self.assertIn("source_entity_id", relationship_dict)
        self.assertIn("source_entity_type", relationship_dict)
        self.assertIn("target_entity_id", relationship_dict)
        self.assertIn("target_entity_type", relationship_dict)
        self.assertIn("relationship_type", relationship_dict)
        self.assertIn("properties", relationship_dict)
        self.assertIn("created_at", relationship_dict)
        self.assertIn("updated_at", relationship_dict)
        self.assertIn("is_active", relationship_dict)
    
    def test_get_relationship_key(self):
        """Test getting relationship key."""
        key = self.relationship.get_relationship_key()
        expected_key = "source-001:has_schema:target-001"
        self.assertEqual(key, expected_key)
    
    def test_is_bidirectional(self):
        """Test checking if relationship is bidirectional."""
        # Test bidirectional types
        bidirectional_rel = MetadataRelationship(
            name="bidirectional_relationship",
            source_entity_id="source-001",
            source_entity_type="Table",
            target_entity_id="target-001",
            target_entity_type="Table",
            relationship_type="replicated_from"
        )
        self.assertTrue(bidirectional_rel.is_bidirectional())
        
        # Test non-bidirectional types
        self.assertFalse(self.relationship.is_bidirectional())
    
    def test_get_reverse_relationship_type(self):
        """Test getting reverse relationship type."""
        # Test relationships with reverse types
        reverse_type = self.relationship.get_reverse_relationship_type()
        self.assertEqual(reverse_type, "belongs_to_schema")
        
        # Test relationships without reverse types
        no_reverse_rel = MetadataRelationship(
            name="no_reverse_relationship",
            source_entity_id="source-001",
            source_entity_type="Database",
            target_entity_id="target-001",
            target_entity_type="Cluster",
            relationship_type="has_cluster"
        )
        reverse_type = no_reverse_rel.get_reverse_relationship_type()
        self.assertEqual(reverse_type, "belongs_to_cluster")
    
    def test_create_reverse_relationship(self):
        """Test creating reverse relationship."""
        reverse_rel = self.relationship.create_reverse_relationship()
        
        self.assertIsNotNone(reverse_rel)
        self.assertEqual(reverse_rel.source_entity_id, "target-001")
        self.assertEqual(reverse_rel.source_entity_type, "Schema")
        self.assertEqual(reverse_rel.target_entity_id, "source-001")
        self.assertEqual(reverse_rel.target_entity_type, "Database")
        self.assertEqual(reverse_rel.relationship_type, "belongs_to_schema")
    
    def test_relationship_validation(self):
        """Test relationship validation."""
        # All required fields should be present
        self.assertTrue(self.relationship.source_entity_id)
        self.assertTrue(self.relationship.source_entity_type)
        self.assertTrue(self.relationship.target_entity_id)
        self.assertTrue(self.relationship.target_entity_type)
        self.assertTrue(self.relationship.relationship_type)
    
    def test_relationship_serialization(self):
        """Test relationship serialization."""
        # Test to_dict method
        relationship_dict = self.relationship.to_dict()
        
        # Verify all fields are present
        self.assertIn("source_entity_id", relationship_dict)
        self.assertIn("source_entity_type", relationship_dict)
        self.assertIn("target_entity_id", relationship_dict)
        self.assertIn("target_entity_type", relationship_dict)
        self.assertIn("relationship_type", relationship_dict)
        
        # Verify data types
        self.assertIsInstance(relationship_dict["source_entity_id"], str)
        self.assertIsInstance(relationship_dict["source_entity_type"], str)
        self.assertIsInstance(relationship_dict["target_entity_id"], str)
        self.assertIsInstance(relationship_dict["target_entity_type"], str)
        self.assertIsInstance(relationship_dict["relationship_type"], str)


class TestRelationshipIntegration(unittest.TestCase):
    """Test cases for relationship integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.database_relationship = MetadataRelationship(
            name="database_schema_relationship",
            source_entity_id="db-001",
            source_entity_type="Database",
            target_entity_id="schema-001",
            target_entity_type="Schema",
            relationship_type="has_schema"
        )
        
        self.schema_table_relationship = MetadataRelationship(
            name="schema_table_relationship",
            source_entity_id="schema-001",
            source_entity_type="Schema",
            target_entity_id="table-001",
            target_entity_type="Table",
            relationship_type="has_table"
        )
        
        self.table_column_relationship = MetadataRelationship(
            name="table_column_relationship",
            source_entity_id="table-001",
            source_entity_type="Table",
            target_entity_id="col-001",
            target_entity_type="Column",
            relationship_type="has_column"
        )
    
    def test_database_hierarchy_relationships(self):
        """Test database hierarchy relationships."""
        # Database -> Schema
        self.assertEqual(self.database_relationship.relationship_type, "has_schema")
        self.assertEqual(self.database_relationship.source_entity_type, "Database")
        self.assertEqual(self.database_relationship.target_entity_type, "Schema")
        
        # Schema -> Table
        self.assertEqual(self.schema_table_relationship.relationship_type, "has_table")
        self.assertEqual(self.schema_table_relationship.source_entity_type, "Schema")
        self.assertEqual(self.schema_table_relationship.target_entity_type, "Table")
        
        # Table -> Column
        self.assertEqual(self.table_column_relationship.relationship_type, "has_column")
        self.assertEqual(self.table_column_relationship.source_entity_type, "Table")
        self.assertEqual(self.table_column_relationship.target_entity_type, "Column")
    
    def test_relationship_metadata_objects(self):
        """Test relationships with metadata objects."""
        # Test tag relationship
        tag_relationship = MetadataRelationship(
            name="tag_relationship",
            source_entity_id="table-001",
            source_entity_type="Table",
            target_entity_id="tag-001",
            target_entity_type="Tag",
            relationship_type="has_tag"
        )
        
        self.assertEqual(tag_relationship.relationship_type, "has_tag")
        self.assertEqual(tag_relationship.source_entity_type, "Table")
        self.assertEqual(tag_relationship.target_entity_type, "Tag")
    
    def test_workflow_relationships(self):
        """Test workflow relationships."""
        # Test write relationship
        write_relationship = MetadataRelationship(
            name="write_relationship",
            source_entity_id="dag-001",
            source_entity_type="AirflowDag",
            target_entity_id="table-001",
            target_entity_type="Table",
            relationship_type="write_to_table"
        )
        
        self.assertEqual(write_relationship.relationship_type, "write_to_table")
        self.assertEqual(write_relationship.source_entity_type, "AirflowDag")
        self.assertEqual(write_relationship.target_entity_type, "Table")
    
    def test_relationship_property_management(self):
        """Test relationship property management."""
        # Add properties to relationships
        self.database_relationship.add_property("created_by", "system")
        self.database_relationship.add_property("priority", "high")
        
        # Verify properties
        self.assertEqual(self.database_relationship.get_property("created_by"), "system")
        self.assertEqual(self.database_relationship.get_property("priority"), "high")
        
        # Remove property
        self.database_relationship.remove_property("priority")
        self.assertIsNone(self.database_relationship.get_property("priority"))
    
    def test_relationship_serialization_integration(self):
        """Test relationship serialization integration."""
        # Serialize all relationships
        db_dict = self.database_relationship.to_dict()
        schema_dict = self.schema_table_relationship.to_dict()
        table_dict = self.table_column_relationship.to_dict()
        
        # Verify all have required fields
        for rel_dict in [db_dict, schema_dict, table_dict]:
            self.assertIn("source_entity_id", rel_dict)
            self.assertIn("source_entity_type", rel_dict)
            self.assertIn("target_entity_id", rel_dict)
            self.assertIn("target_entity_type", rel_dict)
            self.assertIn("relationship_type", rel_dict)
    
    def test_relationship_strength_and_direction(self):
        """Test relationship strength and direction."""
        # Test bidirectional relationships
        replicated_rel = MetadataRelationship(
            name="replicated_relationship",
            source_entity_id="table-001",
            source_entity_type="Table",
            target_entity_id="table-002",
            target_entity_type="Table",
            relationship_type="replicated_from"
        )
        
        self.assertTrue(replicated_rel.is_bidirectional())
        reverse_type = replicated_rel.get_reverse_relationship_type()
        self.assertEqual(reverse_type, "replicated_to")
    
    def test_relationship_validation_integration(self):
        """Test relationship validation integration."""
        # All relationships should be valid
        relationships = [
            self.database_relationship,
            self.schema_table_relationship,
            self.table_column_relationship
        ]
        
        for rel in relationships:
            self.assertTrue(rel.source_entity_id)
            self.assertTrue(rel.source_entity_type)
            self.assertTrue(rel.target_entity_id)
            self.assertTrue(rel.target_entity_type)
            self.assertTrue(rel.relationship_type)
            self.assertTrue(rel.is_active)


if __name__ == "__main__":
    unittest.main()
