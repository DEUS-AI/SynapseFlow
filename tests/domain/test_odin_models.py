"""Tests for ODIN domain models."""

import unittest
from pydantic import ValidationError
from domain.odin_models import (
    Catalog,
    Schema,
    Table,
    Column,
    DataTypeEntity,
    TypeAssignment,
    Constraint,
    DataType,
    ConstraintType,
)


class TestCatalog(unittest.TestCase):
    """Test cases for Catalog model."""

    def test_catalog_creation_with_required_fields(self):
        """Test creating a catalog with only required fields."""
        catalog = Catalog(name="test_catalog")
        self.assertEqual(catalog.name, "test_catalog")
        self.assertIsNone(catalog.description)
        self.assertEqual(catalog.properties, {})

    def test_catalog_creation_with_all_fields(self):
        """Test creating a catalog with all fields."""
        catalog = Catalog(
            name="test_catalog",
            description="Test catalog description",
            properties={"domain": "Customer Analytics", "version": "1.0"}
        )
        self.assertEqual(catalog.name, "test_catalog")
        self.assertEqual(catalog.description, "Test catalog description")
        self.assertEqual(catalog.properties["domain"], "Customer Analytics")

    def test_catalog_missing_required_field(self):
        """Test that catalog creation fails without required name field."""
        with self.assertRaises(ValidationError):
            Catalog()


class TestSchema(unittest.TestCase):
    """Test cases for Schema model."""

    def test_schema_creation_with_required_fields(self):
        """Test creating a schema with only required fields."""
        schema = Schema(name="test_schema", catalog_name="test_catalog")
        self.assertEqual(schema.name, "test_schema")
        self.assertEqual(schema.catalog_name, "test_catalog")
        self.assertIsNone(schema.description)
        self.assertEqual(schema.properties, {})

    def test_schema_creation_with_all_fields(self):
        """Test creating a schema with all fields."""
        schema = Schema(
            name="test_schema",
            catalog_name="test_catalog",
            description="Test schema description",
            properties={"stakeholders": ["Team A", "Team B"]}
        )
        self.assertEqual(schema.name, "test_schema")
        self.assertEqual(schema.catalog_name, "test_catalog")
        self.assertEqual(schema.description, "Test schema description")
        self.assertEqual(len(schema.properties["stakeholders"]), 2)

    def test_schema_missing_required_fields(self):
        """Test that schema creation fails without required fields."""
        with self.assertRaises(ValidationError):
            Schema(name="test_schema")
        with self.assertRaises(ValidationError):
            Schema(catalog_name="test_catalog")


class TestTable(unittest.TestCase):
    """Test cases for Table model."""

    def test_table_creation_with_required_fields(self):
        """Test creating a table with only required fields."""
        table = Table(name="test_table", schema_name="test_schema")
        self.assertEqual(table.name, "test_table")
        self.assertEqual(table.schema_name, "test_schema")
        self.assertIsNone(table.description)
        self.assertIsNone(table.origin)
        self.assertEqual(table.properties, {})

    def test_table_creation_with_all_fields(self):
        """Test creating a table with all fields."""
        table = Table(
            name="test_table",
            schema_name="test_schema",
            description="Test table description",
            origin="source_system",
            properties={"entity_name": "Customer", "business_rules": ["Rule 1"]}
        )
        self.assertEqual(table.name, "test_table")
        self.assertEqual(table.schema_name, "test_schema")
        self.assertEqual(table.description, "Test table description")
        self.assertEqual(table.origin, "source_system")
        self.assertEqual(table.properties["entity_name"], "Customer")

    def test_table_missing_required_fields(self):
        """Test that table creation fails without required fields."""
        with self.assertRaises(ValidationError):
            Table(name="test_table")
        with self.assertRaises(ValidationError):
            Table(schema_name="test_schema")


class TestColumn(unittest.TestCase):
    """Test cases for Column model."""

    def test_column_creation_with_required_fields(self):
        """Test creating a column with only required fields."""
        column = Column(name="test_column", table_name="test_table")
        self.assertEqual(column.name, "test_column")
        self.assertEqual(column.table_name, "test_table")
        self.assertIsNone(column.description)
        self.assertEqual(column.properties, {})

    def test_column_creation_with_all_fields(self):
        """Test creating a column with all fields."""
        column = Column(
            name="test_column",
            table_name="test_table",
            description="Test column description",
            properties={"original_attribute": "Customer ID", "entity_name": "Customer"}
        )
        self.assertEqual(column.name, "test_column")
        self.assertEqual(column.table_name, "test_table")
        self.assertEqual(column.description, "Test column description")
        self.assertEqual(column.properties["original_attribute"], "Customer ID")

    def test_column_missing_required_fields(self):
        """Test that column creation fails without required fields."""
        with self.assertRaises(ValidationError):
            Column(name="test_column")
        with self.assertRaises(ValidationError):
            Column(table_name="test_table")


class TestDataTypeEntity(unittest.TestCase):
    """Test cases for DataTypeEntity model."""

    def test_data_type_creation_with_required_fields(self):
        """Test creating a data type with only required fields."""
        data_type = DataTypeEntity(name="VARCHAR", base_type="STRING")
        self.assertEqual(data_type.name, "VARCHAR")
        self.assertEqual(data_type.base_type, "STRING")
        self.assertEqual(data_type.properties, {})

    def test_data_type_creation_with_all_fields(self):
        """Test creating a data type with all fields."""
        data_type = DataTypeEntity(
            name="DECIMAL",
            base_type="NUMERIC",
            properties={"max_precision": 38, "max_scale": 10}
        )
        self.assertEqual(data_type.name, "DECIMAL")
        self.assertEqual(data_type.base_type, "NUMERIC")
        self.assertEqual(data_type.properties["max_precision"], 38)

    def test_data_type_missing_required_fields(self):
        """Test that data type creation fails without required fields."""
        with self.assertRaises(ValidationError):
            DataTypeEntity(name="VARCHAR")
        with self.assertRaises(ValidationError):
            DataTypeEntity(base_type="STRING")


class TestTypeAssignment(unittest.TestCase):
    """Test cases for TypeAssignment model."""

    def test_type_assignment_creation_with_required_fields(self):
        """Test creating a type assignment with only required fields."""
        assignment = TypeAssignment(column_name="test_column", data_type_name="VARCHAR")
        self.assertEqual(assignment.column_name, "test_column")
        self.assertEqual(assignment.data_type_name, "VARCHAR")
        self.assertIsNone(assignment.precision)
        self.assertIsNone(assignment.scale)
        self.assertEqual(assignment.properties, {})

    def test_type_assignment_creation_with_all_fields(self):
        """Test creating a type assignment with all fields."""
        assignment = TypeAssignment(
            column_name="test_column",
            data_type_name="DECIMAL",
            precision=10,
            scale=2,
            properties={"inferred": True}
        )
        self.assertEqual(assignment.column_name, "test_column")
        self.assertEqual(assignment.data_type_name, "DECIMAL")
        self.assertEqual(assignment.precision, 10)
        self.assertEqual(assignment.scale, 2)
        self.assertTrue(assignment.properties["inferred"])

    def test_type_assignment_missing_required_fields(self):
        """Test that type assignment creation fails without required fields."""
        with self.assertRaises(ValidationError):
            TypeAssignment(column_name="test_column")
        with self.assertRaises(ValidationError):
            TypeAssignment(data_type_name="VARCHAR")


class TestConstraint(unittest.TestCase):
    """Test cases for Constraint model."""

    def test_constraint_creation_with_required_fields(self):
        """Test creating a constraint with only required fields."""
        constraint = Constraint(
            name="pk_test",
            constraint_type=ConstraintType.PRIMARY_KEY,
            column_name="test_column",
            table_name="test_table"
        )
        self.assertEqual(constraint.name, "pk_test")
        self.assertEqual(constraint.constraint_type, ConstraintType.PRIMARY_KEY)
        self.assertEqual(constraint.column_name, "test_column")
        self.assertEqual(constraint.table_name, "test_table")
        self.assertIsNone(constraint.referenced_table)
        self.assertIsNone(constraint.referenced_column)
        self.assertIsNone(constraint.expression)
        self.assertEqual(constraint.properties, {})

    def test_constraint_creation_foreign_key(self):
        """Test creating a foreign key constraint."""
        constraint = Constraint(
            name="fk_test",
            constraint_type=ConstraintType.FOREIGN_KEY,
            column_name="customer_id",
            table_name="orders",
            referenced_table="customers",
            referenced_column="id",
            properties={"source": "business_rule"}
        )
        self.assertEqual(constraint.constraint_type, ConstraintType.FOREIGN_KEY)
        self.assertEqual(constraint.referenced_table, "customers")
        self.assertEqual(constraint.referenced_column, "id")

    def test_constraint_creation_check(self):
        """Test creating a check constraint."""
        constraint = Constraint(
            name="chk_test",
            constraint_type=ConstraintType.CHECK,
            column_name="age",
            table_name="users",
            expression="age >= 0 AND age <= 150",
            properties={"source": "business_rule"}
        )
        self.assertEqual(constraint.constraint_type, ConstraintType.CHECK)
        self.assertEqual(constraint.expression, "age >= 0 AND age <= 150")

    def test_constraint_missing_required_fields(self):
        """Test that constraint creation fails without required fields."""
        with self.assertRaises(ValidationError):
            Constraint(
                name="pk_test",
                constraint_type=ConstraintType.PRIMARY_KEY,
                column_name="test_column"
            )
        with self.assertRaises(ValidationError):
            Constraint(
                name="pk_test",
                constraint_type=ConstraintType.PRIMARY_KEY,
                table_name="test_table"
            )


class TestDataTypeEnum(unittest.TestCase):
    """Test cases for DataType enum."""

    def test_data_type_enum_values(self):
        """Test that all DataType enum values are accessible."""
        self.assertEqual(DataType.VARCHAR, "VARCHAR")
        self.assertEqual(DataType.INTEGER, "INTEGER")
        self.assertEqual(DataType.BIGINT, "BIGINT")
        self.assertEqual(DataType.DECIMAL, "DECIMAL")
        self.assertEqual(DataType.DATE, "DATE")
        self.assertEqual(DataType.TIMESTAMP, "TIMESTAMP")
        self.assertEqual(DataType.BOOLEAN, "BOOLEAN")
        self.assertEqual(DataType.JSON, "JSON")
        self.assertEqual(DataType.ARRAY, "ARRAY")

    def test_data_type_enum_usage(self):
        """Test using DataType enum in a model."""
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        self.assertEqual(data_type.name, "VARCHAR")


class TestConstraintTypeEnum(unittest.TestCase):
    """Test cases for ConstraintType enum."""

    def test_constraint_type_enum_values(self):
        """Test that all ConstraintType enum values are accessible."""
        self.assertEqual(ConstraintType.PRIMARY_KEY, "PRIMARY_KEY")
        self.assertEqual(ConstraintType.FOREIGN_KEY, "FOREIGN_KEY")
        self.assertEqual(ConstraintType.UNIQUE, "UNIQUE")
        self.assertEqual(ConstraintType.NOT_NULL, "NOT_NULL")
        self.assertEqual(ConstraintType.CHECK, "CHECK")
        self.assertEqual(ConstraintType.DEFAULT, "DEFAULT")

    def test_constraint_type_enum_usage(self):
        """Test using ConstraintType enum in a model."""
        constraint = Constraint(
            name="pk_test",
            constraint_type=ConstraintType.PRIMARY_KEY,
            column_name="id",
            table_name="test_table"
        )
        self.assertEqual(constraint.constraint_type, ConstraintType.PRIMARY_KEY)


class TestModelDefaults(unittest.TestCase):
    """Test cases for model default values."""

    def test_default_properties_empty_dict(self):
        """Test that properties default to empty dict."""
        catalog = Catalog(name="test")
        self.assertEqual(catalog.properties, {})
        
        schema = Schema(name="test", catalog_name="catalog")
        self.assertEqual(schema.properties, {})
        
        table = Table(name="test", schema_name="schema")
        self.assertEqual(table.properties, {})
        
        column = Column(name="test", table_name="table")
        self.assertEqual(column.properties, {})

    def test_default_optional_fields_none(self):
        """Test that optional fields default to None."""
        catalog = Catalog(name="test")
        self.assertIsNone(catalog.description)
        
        table = Table(name="test", schema_name="schema")
        self.assertIsNone(table.description)
        self.assertIsNone(table.origin)
        
        column = Column(name="test", table_name="table")
        self.assertIsNone(column.description)
        
        assignment = TypeAssignment(column_name="col", data_type_name="VARCHAR")
        self.assertIsNone(assignment.precision)
        self.assertIsNone(assignment.scale)

