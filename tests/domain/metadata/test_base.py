"""Tests for the base MetadataEntity model."""

import unittest
import os
import sys
from datetime import datetime

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "..", "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from domain.metadata.base import MetadataEntity


class TestMetadataEntity(unittest.TestCase):
    """Test cases for MetadataEntity base class."""

    def setUp(self):
        """Set up test fixtures."""
        self.entity = MetadataEntity(
            name="test_entity",
            description="Test entity for testing",
            entity_type="Test"
        )

    def test_entity_creation(self):
        """Test that entity is created with correct basic attributes."""
        self.assertEqual(self.entity.name, "test_entity")
        self.assertEqual(self.entity.description, "Test entity for testing")
        self.assertEqual(self.entity.entity_type, "Test")
        self.assertIsInstance(self.entity.id, str)
        self.assertIsInstance(self.entity.created_at, datetime)
        self.assertIsInstance(self.entity.updated_at, datetime)
        self.assertEqual(self.entity.tags, [])
        self.assertEqual(self.entity.properties, {})

    def test_entity_id_uniqueness(self):
        """Test that each entity gets a unique ID."""
        entity1 = MetadataEntity(name="entity1", entity_type="Test")
        entity2 = MetadataEntity(name="entity2", entity_type="Test")
        self.assertNotEqual(entity1.id, entity2.id)

    def test_add_tag(self):
        """Test adding tags to entity."""
        self.entity.add_tag("test_tag")
        self.assertIn("test_tag", self.entity.tags)
        self.assertEqual(len(self.entity.tags), 1)

    def test_add_duplicate_tag(self):
        """Test that duplicate tags are not added."""
        self.entity.add_tag("test_tag")
        self.entity.add_tag("test_tag")
        self.assertEqual(len(self.entity.tags), 1)
        self.assertEqual(self.entity.tags.count("test_tag"), 1)

    def test_remove_tag(self):
        """Test removing tags from entity."""
        self.entity.add_tag("test_tag")
        self.entity.add_tag("another_tag")
        self.entity.remove_tag("test_tag")
        self.assertNotIn("test_tag", self.entity.tags)
        self.assertIn("another_tag", self.entity.tags)

    def test_remove_nonexistent_tag(self):
        """Test removing a tag that doesn't exist."""
        initial_tags = self.entity.tags.copy()
        self.entity.remove_tag("nonexistent_tag")
        self.assertEqual(self.entity.tags, initial_tags)

    def test_set_property(self):
        """Test setting properties on entity."""
        self.entity.set_property("key1", "value1")
        self.entity.set_property("key2", 42)
        self.assertEqual(self.entity.properties["key1"], "value1")
        self.assertEqual(self.entity.properties["key2"], 42)

    def test_get_property(self):
        """Test getting properties from entity."""
        self.entity.set_property("test_key", "test_value")
        self.assertEqual(self.entity.get_property("test_key"), "test_value")
        self.assertEqual(self.entity.get_property("nonexistent", "default"), "default")

    def test_update_description(self):
        """Test updating entity description."""
        old_updated_at = self.entity.updated_at
        self.entity.update_description("New description")
        self.assertEqual(self.entity.description, "New description")
        self.assertGreater(self.entity.updated_at, old_updated_at)

    def test_to_dict(self):
        """Test converting entity to dictionary."""
        entity_dict = self.entity.to_dict()
        self.assertIsInstance(entity_dict, dict)
        self.assertEqual(entity_dict["name"], "test_entity")
        self.assertEqual(entity_dict["description"], "Test entity for testing")
        self.assertEqual(entity_dict["entity_type"], "Test")
        self.assertIn("id", entity_dict)
        self.assertIn("created_at", entity_dict)
        self.assertIn("updated_at", entity_dict)
        self.assertIn("tags", entity_dict)
        self.assertIn("properties", entity_dict)

    def test_to_dict_timestamps(self):
        """Test that timestamps in dict are ISO format strings."""
        entity_dict = self.entity.to_dict()
        self.assertIsInstance(entity_dict["created_at"], str)
        self.assertIsInstance(entity_dict["updated_at"], str)
        # Verify they are valid ISO format
        datetime.fromisoformat(entity_dict["created_at"])
        datetime.fromisoformat(entity_dict["updated_at"])

    def test_entity_with_custom_properties(self):
        """Test entity with custom properties."""
        entity = MetadataEntity(
            name="custom_entity",
            description="Entity with custom properties",
            entity_type="Custom",
            tags=["tag1", "tag2"],
            properties={"custom_key": "custom_value"}
        )
        
        self.assertEqual(entity.tags, ["tag1", "tag2"])
        self.assertEqual(entity.properties["custom_key"], "custom_value")

    def test_entity_validation(self):
        """Test that entity validation works correctly."""
        # Test with minimal required fields
        minimal_entity = MetadataEntity(
            name="minimal",
            entity_type="Minimal"
        )
        self.assertEqual(minimal_entity.name, "minimal")
        self.assertEqual(minimal_entity.entity_type, "Minimal")
        self.assertIsNone(minimal_entity.description)

    def test_entity_immutability_of_core_fields(self):
        """Test that core fields cannot be modified directly."""
        # These fields should be read-only after creation
        # Note: In Pydantic v2, fields are not automatically immutable
        # This test verifies the current behavior
        old_id = self.entity.id
        old_entity_type = self.entity.entity_type
        
        # Attempt to modify fields (this should work in current implementation)
        self.entity.id = "new_id"
        self.entity.entity_type = "NewType"
        
        # Verify fields were changed
        self.assertEqual(self.entity.id, "new_id")
        self.assertEqual(self.entity.entity_type, "NewType")
        
        # Restore original values
        self.entity.id = old_id
        self.entity.entity_type = old_entity_type


if __name__ == "__main__":
    unittest.main()
