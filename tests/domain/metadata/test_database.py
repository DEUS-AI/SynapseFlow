"""Tests for Database and Cluster metadata models."""

import unittest
import os
import sys
from datetime import datetime

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "..", "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from domain.metadata.database import Cluster, Database


class TestCluster(unittest.TestCase):
    """Test cases for Cluster model."""

    def setUp(self):
        """Set up test fixtures."""
        self.cluster = Cluster(
            name="Test Cluster",
            description="Test cluster for testing",
            cluster_type="development",
            region="us-west-1",
            environment="dev"
        )

    def test_cluster_creation(self):
        """Test that cluster is created with correct attributes."""
        self.assertEqual(self.cluster.name, "Test Cluster")
        self.assertEqual(self.cluster.description, "Test cluster for testing")
        self.assertEqual(self.cluster.cluster_type, "development")
        self.assertEqual(self.cluster.region, "us-west-1")
        self.assertEqual(self.cluster.environment, "dev")
        self.assertEqual(self.cluster.status, "active")
        self.assertEqual(self.cluster.databases, [])
        self.assertEqual(self.cluster.entity_type, "Cluster")

    def test_cluster_default_values(self):
        """Test cluster default values."""
        minimal_cluster = Cluster(
            name="Minimal Cluster",
            cluster_type="production",
            environment="prod"
        )
        self.assertEqual(minimal_cluster.status, "active")
        self.assertEqual(minimal_cluster.databases, [])
        self.assertIsNone(minimal_cluster.region)
        self.assertIsNone(minimal_cluster.capacity)

    def test_add_database(self):
        """Test adding database to cluster."""
        self.cluster.add_database("db-001")
        self.assertIn("db-001", self.cluster.databases)
        self.assertEqual(len(self.cluster.databases), 1)

    def test_add_duplicate_database(self):
        """Test that duplicate databases are not added."""
        self.cluster.add_database("db-001")
        self.cluster.add_database("db-001")
        self.assertEqual(len(self.cluster.databases), 1)

    def test_remove_database(self):
        """Test removing database from cluster."""
        self.cluster.add_database("db-001")
        self.cluster.add_database("db-002")
        self.cluster.remove_database("db-001")
        self.assertNotIn("db-001", self.cluster.databases)
        self.assertIn("db-002", self.cluster.databases)

    def test_remove_nonexistent_database(self):
        """Test removing database that doesn't exist."""
        initial_databases = self.cluster.databases.copy()
        self.cluster.remove_database("nonexistent")
        self.assertEqual(self.cluster.databases, initial_databases)

    def test_cluster_with_custom_properties(self):
        """Test cluster with custom properties."""
        self.cluster.set_property("owner", "data_team")
        self.cluster.set_property("cost_center", "CC001")
        self.assertEqual(self.cluster.get_property("owner"), "data_team")
        self.assertEqual(self.cluster.get_property("cost_center"), "CC001")


class TestDatabase(unittest.TestCase):
    """Test cases for Database model."""

    def setUp(self):
        """Set up test fixtures."""
        self.database = Database(
            name="test_database",
            description="Test database for testing",
            database_type="postgresql",
            version="14.0"
        )

    def test_database_creation(self):
        """Test that database is created with correct attributes."""
        self.assertEqual(self.database.name, "test_database")
        self.assertEqual(self.database.description, "Test database for testing")
        self.assertEqual(self.database.database_type, "postgresql")
        self.assertEqual(self.database.version, "14.0")
        self.assertEqual(self.database.schemas, [])
        self.assertEqual(self.database.entity_type, "Database")

    def test_database_default_values(self):
        """Test database default values."""
        minimal_database = Database(
            name="minimal_db",
            database_type="mysql"
        )
        self.assertEqual(minimal_database.schemas, [])
        self.assertIsNone(minimal_database.cluster_id)
        self.assertIsNone(minimal_database.version)
        self.assertIsNone(minimal_database.connection_string)
        self.assertIsNone(minimal_database.owner)
        self.assertIsNone(minimal_database.backup_schedule)

    def test_add_schema(self):
        """Test adding schema to database."""
        self.database.add_schema("schema-001")
        self.assertIn("schema-001", self.database.schemas)
        self.assertEqual(len(self.database.schemas), 1)

    def test_add_duplicate_schema(self):
        """Test that duplicate schemas are not added."""
        self.database.add_schema("schema-001")
        self.database.add_schema("schema-001")
        self.assertEqual(len(self.database.schemas), 1)

    def test_remove_schema(self):
        """Test removing schema from database."""
        self.database.add_schema("schema-001")
        self.database.add_schema("schema-002")
        self.database.remove_schema("schema-001")
        self.assertNotIn("schema-001", self.database.schemas)
        self.assertIn("schema-002", self.database.schemas)

    def test_remove_nonexistent_schema(self):
        """Test removing schema that doesn't exist."""
        initial_schemas = self.database.schemas.copy()
        self.database.remove_schema("nonexistent")
        self.assertEqual(self.database.schemas, initial_schemas)

    def test_set_cluster(self):
        """Test setting cluster for database."""
        self.database.set_cluster("cluster-001")
        self.assertEqual(self.database.cluster_id, "cluster-001")

    def test_database_with_custom_properties(self):
        """Test database with custom properties."""
        self.database.set_property("maintenance_window", "Sunday 2-4 AM")
        self.database.set_property("backup_retention_days", 30)
        self.assertEqual(self.database.get_property("maintenance_window"), "Sunday 2-4 AM")
        self.assertEqual(self.database.get_property("backup_retention_days"), 30)


class TestDatabaseClusterIntegration(unittest.TestCase):
    """Test cases for Database and Cluster integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.cluster = Cluster(
            name="Test Cluster",
            cluster_type="production",
            environment="prod"
        )
        self.database = Database(
            name="Test Database",
            database_type="postgresql",
            cluster_id=self.cluster.id
        )

    def test_database_cluster_relationship(self):
        """Test that database and cluster are properly linked."""
        # Add database to cluster
        self.cluster.add_database(self.database.id)
        
        # Verify relationship
        self.assertIn(self.database.id, self.cluster.databases)
        self.assertEqual(self.database.cluster_id, self.cluster.id)

    def test_cluster_database_count(self):
        """Test that cluster tracks database count correctly."""
        self.assertEqual(len(self.cluster.databases), 0)
        
        self.cluster.add_database("db-001")
        self.cluster.add_database("db-002")
        
        self.assertEqual(len(self.cluster.databases), 2)

    def test_database_schema_management(self):
        """Test that database can manage schemas independently."""
        self.database.add_schema("public")
        self.database.add_schema("analytics")
        
        self.assertEqual(len(self.database.schemas), 2)
        self.assertIn("public", self.database.schemas)
        self.assertIn("analytics", self.database.schemas)

    def test_cluster_database_removal(self):
        """Test removing database from cluster."""
        self.cluster.add_database(self.database.id)
        self.assertIn(self.database.id, self.cluster.databases)
        
        self.cluster.remove_database(self.database.id)
        self.assertNotIn(self.database.id, self.cluster.databases)

    def test_database_cluster_change(self):
        """Test changing database cluster."""
        new_cluster = Cluster(
            name="New Cluster",
            cluster_type="staging",
            environment="staging"
        )
        
        self.database.set_cluster(new_cluster.id)
        self.assertEqual(self.database.cluster_id, new_cluster.id)


if __name__ == "__main__":
    unittest.main()
