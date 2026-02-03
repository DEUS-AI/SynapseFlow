"""Tests for MetadataGraphBuilder."""

import unittest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from application.agents.data_engineer.type_inference import TypeInferenceService
from domain.dda_models import DDADocument, DataEntity, Relationship
from domain.odin_models import DataType, DataTypeEntity, ConstraintType
from infrastructure.in_memory_backend import InMemoryGraphBackend


class TestMetadataGraphBuilder(unittest.IsolatedAsyncioTestCase):
    """Test cases for MetadataGraphBuilder."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.kg_backend = InMemoryGraphBackend()
        self.mock_llm = Mock()
        self.type_inference = TypeInferenceService(self.mock_llm)
        self.builder = MetadataGraphBuilder(self.kg_backend, self.type_inference)
        
        # Mock type inference to return predictable results
        self.type_inference.infer_data_type = AsyncMock(return_value=DataTypeEntity(
            name=DataType.VARCHAR,
            base_type="STRING"
        ))
        self.type_inference.infer_precision = AsyncMock(return_value=100)
        self.type_inference.infer_scale = AsyncMock(return_value=None)
    
    def _create_sample_dda(self) -> DDADocument:
        """Create a sample DDA document for testing."""
        return DDADocument(
            domain="Customer Analytics",
            stakeholders=["Marketing Team", "Sales Team"],
            data_owner="VP of Customer Experience",
            effective_date=datetime(2024, 1, 15),
            business_context="Customer behavior analysis",
            entities=[
                DataEntity(
                    name="Customer",
                    description="Core customer information",
                    attributes=["Customer ID", "Email Address", "Name"],
                    business_rules=["Customer ID must be unique", "Email must be valid format"],
                    primary_key="Customer ID",
                    foreign_keys=[]
                ),
                DataEntity(
                    name="Order",
                    description="Customer orders",
                    attributes=["Order ID", "Customer ID", "Order Date", "Total Amount"],
                    business_rules=["Order ID must be unique", "Must reference valid Customer ID"],
                    primary_key="Order ID",
                    foreign_keys=["Customer ID"]
                )
            ],
            relationships=[
                Relationship(
                    source_entity="Order",
                    target_entity="Customer",
                    relationship_type="N:1",
                    description="Order belongs to Customer",
                    constraints=["Order must reference valid Customer ID"]
                )
            ]
        )
    
    async def test_build_metadata_graph_complete(self):
        """Test building a complete metadata graph from DDA."""
        dda = self._create_sample_dda()
        
        result = await self.builder.build_metadata_graph(dda)
        
        # Verify counts
        self.assertEqual(result["catalogs_created"], 1)
        self.assertEqual(result["schemas_created"], 1)
        self.assertEqual(result["tables_created"], 2)  # Customer and Order
        self.assertGreater(result["columns_created"], 0)
        self.assertGreater(result["constraints_created"], 0)
        self.assertGreater(result["relationships_created"], 0)
    
    async def test_create_catalog(self):
        """Test catalog creation."""
        dda = self._create_sample_dda()
        
        catalog = await self.builder._create_catalog(dda)
        
        self.assertEqual(catalog.name, "customer_analytics_catalog")
        self.assertIn("Customer Analytics", catalog.description)
        
        # Verify catalog was added to backend
        graph_state = await self.kg_backend.query("")
        self.assertIn("catalog:customer_analytics_catalog", graph_state["nodes"])
    
    async def test_create_schema(self):
        """Test schema creation with belongs_to relationship."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        
        schema = await self.builder._create_schema(dda, catalog.name)
        
        self.assertEqual(schema.name, "customer_analytics_schema")
        self.assertEqual(schema.catalog_name, catalog.name)
        
        # Verify schema was added to backend
        graph_state = await self.kg_backend.query("")
        self.assertIn("schema:customer_analytics_schema", graph_state["nodes"])
        
        # Verify belongs_to relationship
        self.assertIn("schema:customer_analytics_schema", graph_state["edges"])
        relationships = graph_state["edges"]["schema:customer_analytics_schema"]
        belongs_to = [r for r in relationships if r[0] == "belongs_to"]
        self.assertEqual(len(belongs_to), 1)
    
    async def test_create_table(self):
        """Test table creation from entity."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        entity = dda.entities[0]
        
        table = await self.builder._create_table(dda, entity, schema.name)
        
        self.assertEqual(table.name, "customer")
        self.assertEqual(table.schema_name, schema.name)
        self.assertEqual(table.description, entity.description)
        
        # Verify table was added to backend
        graph_state = await self.kg_backend.query("")
        table_id = f"table:{schema.name}.{table.name}"
        self.assertIn(table_id, graph_state["nodes"])
        
        # Verify belongs_to relationship
        self.assertIn(table_id, graph_state["edges"])
        relationships = graph_state["edges"][table_id]
        belongs_to = [r for r in relationships if r[0] == "belongs_to"]
        self.assertEqual(len(belongs_to), 1)
    
    async def test_create_column(self):
        """Test column creation from attribute."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        entity = dda.entities[0]
        table = await self.builder._create_table(dda, entity, schema.name)
        table_id = f"table:{schema.name}.{table.name}"
        
        column = await self.builder._create_column(entity, "Customer ID", table.name, table_id)
        
        self.assertEqual(column.name, "customer_id")
        self.assertEqual(column.table_name, table.name)
        
        # Verify column was added to backend
        graph_state = await self.kg_backend.query("")
        column_id = f"column:{table.name}.{column.name}"
        self.assertIn(column_id, graph_state["nodes"])
        
        # Verify has_column relationship
        self.assertIn(table_id, graph_state["edges"])
        relationships = graph_state["edges"][table_id]
        has_column = [r for r in relationships if r[0] == "has_column" and r[1] == column_id]
        self.assertEqual(len(has_column), 1)
    
    async def test_create_type_assignment(self):
        """Test type assignment creation."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        entity = dda.entities[0]
        table = await self.builder._create_table(dda, entity, schema.name)
        table_id = f"table:{schema.name}.{table.name}"
        column = await self.builder._create_column(entity, "Email Address", table.name, table_id)
        
        assignment = await self.builder._create_type_assignment(column, "Email Address", entity, table_id)
        
        self.assertEqual(assignment.column_name, column.name)
        self.assertEqual(assignment.data_type_name, DataType.VARCHAR.value)
        self.assertIsNotNone(assignment.precision)
        
        # Verify type assignment was added to backend
        graph_state = await self.kg_backend.query("")
        assignment_id = f"type_assignment:{table.name}.{column.name}"
        self.assertIn(assignment_id, graph_state["nodes"])
        
        # Verify relationships
        column_id = f"column:{table.name}.{column.name}"
        self.assertIn(column_id, graph_state["edges"])
        relationships = graph_state["edges"][column_id]
        has_type = [r for r in relationships if r[0] == "has_type_assignment"]
        self.assertEqual(len(has_type), 1)
    
    async def test_create_constraints_primary_key(self):
        """Test constraint creation for primary key."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        entity = dda.entities[0]
        table = await self.builder._create_table(dda, entity, schema.name)
        table_id = f"table:{schema.name}.{table.name}"
        column = await self.builder._create_column(entity, "Customer ID", table.name, table_id)
        
        constraints = await self.builder._create_constraints(
            entity, "Customer ID", column, table.name, table_id, dda
        )
        
        # Should have primary key constraint
        pk_constraints = [c for c in constraints if c.constraint_type == ConstraintType.PRIMARY_KEY]
        self.assertEqual(len(pk_constraints), 1)
        self.assertEqual(pk_constraints[0].name, f"pk_{table.name}_{column.name}")
        
        # Verify constraint was added to backend
        graph_state = await self.kg_backend.query("")
        constraint_id = f"constraint:{pk_constraints[0].name}"
        self.assertIn(constraint_id, graph_state["nodes"])
        
        # Verify constrained_by relationship
        column_id = f"column:{table.name}.{column.name}"
        self.assertIn(column_id, graph_state["edges"])
        relationships = graph_state["edges"][column_id]
        constrained_by = [r for r in relationships if r[0] == "constrained_by"]
        self.assertGreater(len(constrained_by), 0)
    
    async def test_create_constraints_foreign_key(self):
        """Test constraint creation for foreign key."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        entity = dda.entities[1]  # Order entity
        table = await self.builder._create_table(dda, entity, schema.name)
        table_id = f"table:{schema.name}.{table.name}"
        column = await self.builder._create_column(entity, "Customer ID", table.name, table_id)
        
        constraints = await self.builder._create_constraints(
            entity, "Customer ID", column, table.name, table_id, dda
        )
        
        # Should have foreign key constraint
        fk_constraints = [c for c in constraints if c.constraint_type == ConstraintType.FOREIGN_KEY]
        self.assertGreater(len(fk_constraints), 0)
        fk = fk_constraints[0]
        self.assertEqual(fk.referenced_table, "customer")
    
    async def test_create_constraints_business_rules(self):
        """Test constraint creation from business rules."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        entity = dda.entities[0]
        table = await self.builder._create_table(dda, entity, schema.name)
        table_id = f"table:{schema.name}.{table.name}"
        column = await self.builder._create_column(entity, "Customer ID", table.name, table_id)
        
        constraints = await self.builder._create_constraints(
            entity, "Customer ID", column, table.name, table_id, dda
        )
        
        # Should have unique constraint from business rule
        unique_constraints = [c for c in constraints if c.constraint_type == ConstraintType.UNIQUE]
        self.assertGreater(len(unique_constraints), 0)
    
    async def test_create_relationships_owned_by(self):
        """Test owned_by relationship creation."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        
        relationships = await self.builder._create_relationships(dda, catalog, schema)
        
        # Should have owned_by relationships
        owned_by = [r for r in relationships if r["type"] == "owned_by"]
        self.assertGreater(len(owned_by), 0)
        
        # Verify in backend
        graph_state = await self.kg_backend.query("")
        for entity in dda.entities:
            table_id = f"table:{schema.name}.{entity.name.lower().replace(' ', '_')}"
            if table_id in graph_state["edges"]:
                rels = graph_state["edges"][table_id]
                owned = [r for r in rels if r[0] == "owned_by"]
                self.assertGreater(len(owned), 0)
    
    async def test_create_relationships_read_by(self):
        """Test read_by relationship creation."""
        dda = self._create_sample_dda()
        catalog = await self.builder._create_catalog(dda)
        schema = await self.builder._create_schema(dda, catalog.name)
        
        relationships = await self.builder._create_relationships(dda, catalog, schema)
        
        # Should have read_by relationships for stakeholders
        read_by = [r for r in relationships if r["type"] == "read_by"]
        self.assertGreater(len(read_by), 0)
    
    async def test_parse_attribute_name(self):
        """Test attribute name parsing."""
        result = self.builder._parse_attribute_name("Customer ID (Primary Key)")
        self.assertEqual(result, "customer_id")
        
        result = self.builder._parse_attribute_name("Email Address")
        self.assertEqual(result, "email_address")
        
        result = self.builder._parse_attribute_name("First Name")
        self.assertEqual(result, "first_name")
    
    async def test_matches_attribute(self):
        """Test attribute matching logic."""
        self.assertTrue(self.builder._matches_attribute("Customer ID", "Customer ID"))
        self.assertTrue(self.builder._matches_attribute("Customer ID (Primary Key)", "Customer ID"))
        self.assertTrue(self.builder._matches_attribute("customer_id", "Customer ID"))
        self.assertFalse(self.builder._matches_attribute("Email Address", "Customer ID"))
    
    async def test_find_referenced_table(self):
        """Test finding referenced table from foreign key."""
        dda = self._create_sample_dda()
        
        # Should find Customer table from Customer ID FK
        referenced = self.builder._find_referenced_table("Customer ID", dda)
        self.assertEqual(referenced, "customer")
        
        # Should return None for non-existent FK
        referenced = self.builder._find_referenced_table("NonExistent ID", dda)
        self.assertIsNone(referenced)
    
    async def test_infer_referenced_column(self):
        """Test inferring referenced column name."""
        result = self.builder._infer_referenced_column("Customer ID")
        self.assertEqual(result, "customer_id")
        
        result = self.builder._infer_referenced_column("Order ID")
        self.assertEqual(result, "order_id")
    
    async def test_parse_business_rule_to_constraint(self):
        """Test parsing business rules to constraints."""
        # Unique constraint
        constraint = self.builder._parse_business_rule_to_constraint(
            "Customer ID must be unique",
            "customer_id",
            "customer"
        )
        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.constraint_type, ConstraintType.UNIQUE)
        
        # NOT NULL constraint
        constraint = self.builder._parse_business_rule_to_constraint(
            "Email cannot be null",
            "email",
            "customer"
        )
        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.constraint_type, ConstraintType.NOT_NULL)
        
        # CHECK constraint
        constraint = self.builder._parse_business_rule_to_constraint(
            "Email must be valid format",
            "email",
            "customer"
        )
        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.constraint_type, ConstraintType.CHECK)
        
        # No constraint
        constraint = self.builder._parse_business_rule_to_constraint(
            "Some other rule",
            "field",
            "table"
        )
        self.assertIsNone(constraint)
    
    async def test_ensure_data_type(self):
        """Test ensuring data type exists."""
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        
        await self.builder._ensure_data_type(data_type)
        
        # Verify data type was added
        graph_state = await self.kg_backend.query("")
        self.assertIn("datatype:VARCHAR", graph_state["nodes"])
    
    async def test_ensure_user(self):
        """Test ensuring user exists."""
        await self.builder._ensure_user("Test User", "data_owner", "Test Domain")
        
        # Verify user was added
        graph_state = await self.kg_backend.query("")
        self.assertIn("user:Test User", graph_state["nodes"])
        
        # Should not duplicate if called again
        await self.builder._ensure_user("Test User", "data_owner", "Test Domain")
        # Count should still be 1 (though we can't easily verify this with current backend)

