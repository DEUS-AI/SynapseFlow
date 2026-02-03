"""Tests for Schema, Table, Column and ColumnStats metadata models."""

import unittest
import os
import sys
from datetime import datetime

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "..", "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from domain.metadata.schema import Schema
from domain.metadata.table import Table, Column, ColumnStats


class TestSchema(unittest.TestCase):
    """Test cases for Schema model."""

    def setUp(self):
        """Set up test fixtures."""
        self.schema = Schema(
            name="test_schema",
            description="Test schema for testing",
            database_id="db-001",
            schema_name="test"
        )

    def test_schema_creation(self):
        """Test that schema is created with correct attributes."""
        self.assertEqual(self.schema.name, "test_schema")
        self.assertEqual(self.schema.description, "Test schema for testing")
        self.assertEqual(self.schema.database_id, "db-001")
        self.assertEqual(self.schema.schema_name, "test")
        self.assertEqual(self.schema.tables, [])
        self.assertEqual(self.schema.views, [])
        self.assertEqual(self.schema.functions, [])
        self.assertFalse(self.schema.is_default)
        self.assertEqual(self.schema.entity_type, "Schema")

    def test_schema_default_values(self):
        """Test schema default values."""
        minimal_schema = Schema(
            name="minimal_schema",
            database_id="db-001",
            schema_name="minimal"
        )
        self.assertEqual(minimal_schema.tables, [])
        self.assertEqual(minimal_schema.views, [])
        self.assertEqual(minimal_schema.functions, [])
        self.assertFalse(minimal_schema.is_default)
        self.assertEqual(minimal_schema.permissions, [])

    def test_add_table(self):
        """Test adding table to schema."""
        self.schema.add_table("table-001")
        self.assertIn("table-001", self.schema.tables)
        self.assertEqual(len(self.schema.tables), 1)

    def test_add_duplicate_table(self):
        """Test that duplicate tables are not added."""
        self.schema.add_table("table-001")
        self.schema.add_table("table-001")
        self.assertEqual(len(self.schema.tables), 1)

    def test_remove_table(self):
        """Test removing table from schema."""
        self.schema.add_table("table-001")
        self.schema.add_table("table-002")
        self.schema.remove_table("table-001")
        self.assertNotIn("table-001", self.schema.tables)
        self.assertIn("table-002", self.schema.tables)

    def test_add_view(self):
        """Test adding view to schema."""
        self.schema.add_view("view-001")
        self.assertIn("view-001", self.schema.views)
        self.assertEqual(len(self.schema.views), 1)

    def test_add_function(self):
        """Test adding function to schema."""
        self.schema.add_function("func-001")
        self.assertIn("func-001", self.schema.functions)
        self.assertEqual(len(self.schema.functions), 1)

    def test_add_permission(self):
        """Test adding permission to schema."""
        self.schema.add_permission("SELECT")
        self.schema.add_permission("INSERT")
        self.assertIn("SELECT", self.schema.permissions)
        self.assertIn("INSERT", self.schema.permissions)
        self.assertEqual(len(self.schema.permissions), 2)

    def test_get_object_count(self):
        """Test getting total object count."""
        self.schema.add_table("table-001")
        self.schema.add_view("view-001")
        self.schema.add_function("func-001")
        self.assertEqual(self.schema.get_object_count(), 3)


class TestTable(unittest.TestCase):
    """Test cases for Table model."""

    def setUp(self):
        """Set up test fixtures."""
        self.table = Table(
            name="test_table",
            description="Test table for testing",
            schema_id="schema-001",
            table_name="test_table"
        )

    def test_table_creation(self):
        """Test that table is created with correct attributes."""
        self.assertEqual(self.table.name, "test_table")
        self.assertEqual(self.table.description, "Test table for testing")
        self.assertEqual(self.table.schema_id, "schema-001")
        self.assertEqual(self.table.table_name, "test_table")
        self.assertEqual(self.table.columns, [])
        self.assertEqual(self.table.primary_keys, [])
        self.assertEqual(self.table.foreign_keys, [])
        self.assertEqual(self.table.indexes, [])
        self.assertEqual(self.table.entity_type, "Table")

    def test_table_default_values(self):
        """Test table default values."""
        minimal_table = Table(
            name="minimal_table",
            schema_id="schema-001",
            table_name="minimal_table"
        )
        self.assertEqual(minimal_table.columns, [])
        self.assertEqual(minimal_table.primary_keys, [])
        self.assertEqual(minimal_table.foreign_keys, [])
        self.assertEqual(minimal_table.indexes, [])
        self.assertIsNone(minimal_table.row_count)
        self.assertIsNone(minimal_table.size_bytes)
        self.assertIsNone(minimal_table.watermark_id)
        self.assertIsNone(minimal_table.replicated_from)

    def test_add_column(self):
        """Test adding column to table."""
        self.table.add_column("col-001")
        self.assertIn("col-001", self.table.columns)
        self.assertEqual(len(self.table.columns), 1)

    def test_add_duplicate_column(self):
        """Test that duplicate columns are not added."""
        self.table.add_column("col-001")
        self.table.add_column("col-001")
        self.assertEqual(len(self.table.columns), 1)

    def test_remove_column(self):
        """Test removing column from table."""
        self.table.add_column("col-001")
        self.table.add_column("col-002")
        self.table.remove_column("col-001")
        self.assertNotIn("col-001", self.table.columns)
        self.assertIn("col-002", self.table.columns)

    def test_add_primary_key(self):
        """Test adding primary key to table."""
        self.table.add_primary_key("col-001")
        self.assertIn("col-001", self.table.primary_keys)
        self.assertEqual(len(self.table.primary_keys), 1)

    def test_add_foreign_key(self):
        """Test adding foreign key to table."""
        self.table.add_foreign_key("col-002")
        self.assertIn("col-002", self.table.foreign_keys)
        self.assertEqual(len(self.table.foreign_keys), 1)

    def test_add_index(self):
        """Test adding index to table."""
        self.table.add_index("idx-001")
        self.assertIn("idx-001", self.table.indexes)
        self.assertEqual(len(self.table.indexes), 1)

    def test_set_watermark(self):
        """Test setting watermark for table."""
        self.table.set_watermark("watermark-001")
        self.assertEqual(self.table.watermark_id, "watermark-001")

    def test_get_column_count(self):
        """Test getting column count."""
        self.assertEqual(self.table.get_column_count(), 0)
        self.table.add_column("col-001")
        self.table.add_column("col-002")
        self.assertEqual(self.table.get_column_count(), 2)


class TestColumn(unittest.TestCase):
    """Test cases for Column model."""

    def setUp(self):
        """Set up test fixtures."""
        self.column = Column(
            name="test_column",
            description="Test column for testing",
            table_id="table-001",
            column_name="test_column",
            data_type="varchar",
            position=1
        )

    def test_column_creation(self):
        """Test that column is created with correct attributes."""
        self.assertEqual(self.column.name, "test_column")
        self.assertEqual(self.column.description, "Test column for testing")
        self.assertEqual(self.column.table_id, "table-001")
        self.assertEqual(self.column.column_name, "test_column")
        self.assertEqual(self.column.data_type, "varchar")
        self.assertTrue(self.column.nullable)
        self.assertFalse(self.column.primary_key)
        self.assertFalse(self.column.foreign_key)
        self.assertEqual(self.column.position, 1)
        self.assertEqual(self.column.entity_type, "Column")

    def test_column_default_values(self):
        """Test column default values."""
        minimal_column = Column(
            name="minimal_column",
            table_id="table-001",
            column_name="minimal_column",
            data_type="integer",
            position=1
        )
        self.assertTrue(minimal_column.nullable)
        self.assertFalse(minimal_column.primary_key)
        self.assertFalse(minimal_column.foreign_key)
        self.assertEqual(minimal_column.constraints, [])
        self.assertIsNone(minimal_column.stats_id)

    def test_set_stats(self):
        """Test setting statistics for column."""
        self.column.set_stats("stats-001")
        self.assertEqual(self.column.stats_id, "stats-001")

    def test_add_constraint(self):
        """Test adding constraint to column."""
        self.column.add_constraint("NOT NULL")
        self.column.add_constraint("UNIQUE")
        self.assertIn("NOT NULL", self.column.constraints)
        self.assertIn("UNIQUE", self.column.constraints)
        self.assertEqual(len(self.column.constraints), 2)

    def test_remove_constraint(self):
        """Test removing constraint from column."""
        self.column.add_constraint("NOT NULL")
        self.column.add_constraint("UNIQUE")
        self.column.remove_constraint("NOT NULL")
        self.assertNotIn("NOT NULL", self.column.constraints)
        self.assertIn("UNIQUE", self.column.constraints)

    def test_set_foreign_key_reference(self):
        """Test setting foreign key reference."""
        self.column.set_foreign_key_reference("ref_table", "ref_column")
        self.assertTrue(self.column.foreign_key)
        self.assertEqual(self.column.referenced_table, "ref_table")
        self.assertEqual(self.column.referenced_column, "ref_column")


class TestColumnStats(unittest.TestCase):
    """Test cases for ColumnStats model."""

    def setUp(self):
        """Set up test fixtures."""
        self.stats = ColumnStats(
            name="test_stats",
            description="Test statistics for testing",
            column_id="col-001",
            row_count=1000,
            null_count=50,
            unique_count=950,
            data_type="varchar"
        )

    def test_stats_creation(self):
        """Test that stats are created with correct attributes."""
        self.assertEqual(self.stats.name, "test_stats")
        self.assertEqual(self.stats.description, "Test statistics for testing")
        self.assertEqual(self.stats.column_id, "col-001")
        self.assertEqual(self.stats.row_count, 1000)
        self.assertEqual(self.stats.null_count, 50)
        self.assertEqual(self.stats.unique_count, 950)
        self.assertEqual(self.stats.data_type, "varchar")
        self.assertEqual(self.stats.entity_type, "ColumnStats")

    def test_stats_default_values(self):
        """Test stats default values."""
        minimal_stats = ColumnStats(
            name="minimal_stats",
            column_id="col-001",
            data_type="integer"
        )
        self.assertEqual(minimal_stats.row_count, 0)
        self.assertEqual(minimal_stats.null_count, 0)
        self.assertEqual(minimal_stats.unique_count, 0)
        self.assertEqual(minimal_stats.distinct_values, [])
        self.assertIsInstance(minimal_stats.last_analyzed, datetime)

    def test_update_stats(self):
        """Test updating statistics."""
        old_updated_at = self.stats.updated_at
        new_stats = {
            "row_count": 2000,
            "null_count": 100,
            "unique_count": 1900
        }
        self.stats.update_stats(new_stats)
        self.assertEqual(self.stats.row_count, 2000)
        self.assertEqual(self.stats.null_count, 100)
        self.assertEqual(self.stats.unique_count, 1900)
        self.assertGreater(self.stats.updated_at, old_updated_at)

    def test_get_null_percentage(self):
        """Test calculating null percentage."""
        self.assertEqual(self.stats.get_null_percentage(), 5.0)  # 50/1000 * 100

    def test_get_null_percentage_zero_rows(self):
        """Test null percentage with zero rows."""
        zero_stats = ColumnStats(
            name="zero_stats",
            column_id="col-001",
            row_count=0,
            data_type="integer"
        )
        self.assertEqual(zero_stats.get_null_percentage(), 0.0)

    def test_get_uniqueness_ratio(self):
        """Test calculating uniqueness ratio."""
        self.assertEqual(self.stats.get_uniqueness_ratio(), 95.0)  # 950/1000 * 100

    def test_get_uniqueness_ratio_zero_rows(self):
        """Test uniqueness ratio with zero rows."""
        zero_stats = ColumnStats(
            name="zero_stats",
            column_id="col-001",
            row_count=0,
            data_type="integer"
        )
        self.assertEqual(zero_stats.get_uniqueness_ratio(), 0.0)


class TestSchemaTableIntegration(unittest.TestCase):
    """Test cases for Schema and Table integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.schema = Schema(
            name="test_schema",
            database_id="db-001",
            schema_name="test"
        )
        self.table = Table(
            name="test_table",
            schema_id=self.schema.id,
            table_name="test_table"
        )

    def test_schema_table_relationship(self):
        """Test that schema and table are properly linked."""
        self.schema.add_table(self.table.id)
        self.assertIn(self.table.id, self.schema.tables)
        self.assertEqual(self.table.schema_id, self.schema.id)

    def test_table_column_management(self):
        """Test that table can manage columns."""
        self.table.add_column("col-001")
        self.table.add_column("col-002")
        self.assertEqual(len(self.table.columns), 2)

    def test_table_primary_key_management(self):
        """Test that table can manage primary keys."""
        self.table.add_column("col-001")
        self.table.add_primary_key("col-001")
        self.assertIn("col-001", self.table.primary_keys)

    def test_table_foreign_key_management(self):
        """Test that table can manage foreign keys."""
        self.table.add_column("col-002")
        self.table.add_foreign_key("col-002")
        self.assertIn("col-002", self.table.foreign_keys)

    def test_column_stats_integration(self):
        """Test integration between column and stats."""
        column = Column(
            name="test_column",
            table_id=self.table.id,
            column_name="test_column",
            data_type="integer",
            position=1
        )
        
        stats = ColumnStats(
            name="test_stats",
            column_id=column.id,
            row_count=1000,
            data_type="integer"
        )
        
        column.set_stats(stats.id)
        self.assertEqual(column.stats_id, stats.id)
        self.assertEqual(stats.column_id, column.id)


if __name__ == "__main__":
    unittest.main()
