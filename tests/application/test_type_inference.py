"""Tests for TypeInferenceService."""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from application.agents.data_engineer.type_inference import TypeInferenceService
from domain.odin_models import DataType, DataTypeEntity
from graphiti_core import Graphiti


class MockGraphDocument:
    """Mock Graphiti graph document for testing."""
    
    def __init__(self, nodes=None, relationships=None):
        self.nodes = nodes or []
        self.relationships = relationships or []


class MockNode:
    """Mock graph node for testing."""
    
    def __init__(self, name=None, properties=None):
        self.name = name
        self.properties = properties or {}


class MockRelationship:
    """Mock graph relationship for testing."""
    
    def __init__(self, properties=None):
        self.properties = properties or {}


class TestTypeInferenceService(unittest.IsolatedAsyncioTestCase):
    """Test cases for TypeInferenceService."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.mock_llm = Mock(spec=Graphiti)
        self.service = TypeInferenceService(self.mock_llm)
    
    async def test_infer_data_type_with_graphiti_response(self):
        """Test type inference using Graphiti response."""
        # Mock Graphiti response with type information
        mock_node = MockNode(name="VARCHAR", properties={"type": "VARCHAR"})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        result = await self.service.infer_data_type("Customer Email", {})
        
        self.assertIsInstance(result, DataTypeEntity)
        self.assertEqual(result.name, DataType.VARCHAR)
        self.assertEqual(result.base_type, "STRING")
        self.mock_llm.process.assert_called_once()
    
    async def test_infer_data_type_heuristic_fallback(self):
        """Test type inference falls back to heuristic when Graphiti fails."""
        # Mock Graphiti to raise exception
        self.mock_llm.process = Mock(side_effect=Exception("Graphiti error"))
        
        result = await self.service.infer_data_type("Customer ID", {})
        
        self.assertIsInstance(result, DataTypeEntity)
        # Should use heuristic - ID should be BIGINT
        self.assertEqual(result.name, DataType.BIGINT)
        self.assertEqual(result.base_type, "NUMERIC")
    
    async def test_infer_data_type_heuristic_id_pattern(self):
        """Test heuristic inference for ID patterns."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        result = await self.service.infer_data_type("customer_id", {})
        self.assertEqual(result.name, DataType.BIGINT)
        
        result = await self.service.infer_data_type("Order ID", {})
        self.assertEqual(result.name, DataType.BIGINT)
    
    async def test_infer_data_type_heuristic_date_pattern(self):
        """Test heuristic inference for date patterns."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        result = await self.service.infer_data_type("created_date", {})
        self.assertEqual(result.name, DataType.DATE)
        
        result = await self.service.infer_data_type("updated_timestamp", {})
        self.assertEqual(result.name, DataType.TIMESTAMP)
    
    async def test_infer_data_type_heuristic_email_pattern(self):
        """Test heuristic inference for email patterns."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        result = await self.service.infer_data_type("email_address", {})
        self.assertEqual(result.name, DataType.VARCHAR)
    
    async def test_infer_data_type_heuristic_amount_pattern(self):
        """Test heuristic inference for amount patterns."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        result = await self.service.infer_data_type("total_amount", {})
        self.assertEqual(result.name, DataType.DECIMAL)
        
        result = await self.service.infer_data_type("price", {})
        self.assertEqual(result.name, DataType.DECIMAL)
    
    async def test_infer_data_type_heuristic_boolean_pattern(self):
        """Test heuristic inference for boolean patterns."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        result = await self.service.infer_data_type("is_active", {})
        self.assertEqual(result.name, DataType.BOOLEAN)
        
        result = await self.service.infer_data_type("has_permission", {})
        self.assertEqual(result.name, DataType.BOOLEAN)
    
    async def test_infer_data_type_heuristic_default(self):
        """Test heuristic inference defaults to VARCHAR."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        result = await self.service.infer_data_type("unknown_field", {})
        self.assertEqual(result.name, DataType.VARCHAR)
    
    async def test_infer_data_type_with_context(self):
        """Test type inference uses context information."""
        mock_node = MockNode(properties={"type": "INTEGER"})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        context = {
            "entity_name": "Customer",
            "description": "Customer identifier",
            "business_rules": ["Must be unique"]
        }
        
        result = await self.service.infer_data_type("Customer ID", context)
        
        self.assertIsInstance(result, DataTypeEntity)
        # Verify context was included in prompt
        call_args = self.mock_llm.process.call_args[0][0]
        self.assertIn("Customer", call_args)
        self.assertIn("Must be unique", call_args)
    
    async def test_infer_precision_varchar(self):
        """Test precision inference for VARCHAR types."""
        mock_node = MockNode(name="VARCHAR_255", properties={"precision": 255})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("email_address", data_type)
        
        self.assertEqual(result, 255)
    
    async def test_infer_precision_heuristic_fallback(self):
        """Test precision inference falls back to heuristic."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("email_address", data_type)
        
        # Email should default to 255
        self.assertEqual(result, 255)
    
    async def test_infer_precision_heuristic_id(self):
        """Test precision heuristic for ID fields."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("customer_id", data_type)
        
        # ID fields should default to 50
        self.assertEqual(result, 50)
    
    async def test_infer_precision_heuristic_name(self):
        """Test precision heuristic for name fields."""
        self.mock_llm.process = Mock(side_effect=Exception("Error"))
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("customer_name", data_type)
        
        # Name fields should default to 100
        self.assertEqual(result, 100)
    
    async def test_infer_precision_decimal(self):
        """Test precision inference for DECIMAL types."""
        mock_node = MockNode(properties={"precision": 10})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        data_type = DataTypeEntity(name=DataType.DECIMAL, base_type="NUMERIC")
        result = await self.service.infer_precision("total_amount", data_type)
        
        self.assertEqual(result, 10)
    
    async def test_infer_precision_non_applicable(self):
        """Test precision inference returns None for non-applicable types."""
        data_type = DataTypeEntity(name=DataType.INTEGER, base_type="NUMERIC")
        result = await self.service.infer_precision("count", data_type)
        
        self.assertIsNone(result)
    
    async def test_infer_scale_decimal(self):
        """Test scale inference for DECIMAL types."""
        data_type = DataTypeEntity(name=DataType.DECIMAL, base_type="NUMERIC")
        
        result = await self.service.infer_scale("total_amount", data_type)
        self.assertEqual(result, 2)  # Amount fields default to scale 2
        
        result = await self.service.infer_scale("price", data_type)
        self.assertEqual(result, 2)
    
    async def test_infer_scale_percentage(self):
        """Test scale inference for percentage fields."""
        data_type = DataTypeEntity(name=DataType.DECIMAL, base_type="NUMERIC")
        
        result = await self.service.infer_scale("discount_rate", data_type)
        self.assertEqual(result, 4)  # Rate fields default to scale 4
    
    async def test_infer_scale_non_decimal(self):
        """Test scale inference returns None for non-DECIMAL types."""
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_scale("name", data_type)
        
        self.assertIsNone(result)
    
    async def test_type_cache(self):
        """Test that type inference results are cached."""
        mock_node = MockNode(properties={"type": "VARCHAR"})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        # First call
        result1 = await self.service.infer_data_type("email", {})
        
        # Second call should use cache
        result2 = await self.service.infer_data_type("email", {})
        
        # Should only call Graphiti once
        self.assertEqual(self.mock_llm.process.call_count, 1)
        self.assertEqual(result1.name, result2.name)
    
    async def test_clear_cache(self):
        """Test that cache can be cleared."""
        mock_node = MockNode(properties={"type": "VARCHAR"})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        # First call
        await self.service.infer_data_type("email", {})
        
        # Clear cache
        self.service.clear_cache()
        
        # Second call should call Graphiti again
        await self.service.infer_data_type("email", {})
        
        # Should call Graphiti twice
        self.assertEqual(self.mock_llm.process.call_count, 2)
    
    async def test_extract_type_from_node_properties(self):
        """Test extracting type from node properties."""
        mock_node = MockNode(properties={"type": "INTEGER", "data_type": "BIGINT"})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        result = await self.service.infer_data_type("test_field", {})
        
        # Should extract INTEGER from properties
        self.assertEqual(result.name, DataType.INTEGER)
    
    async def test_extract_type_from_node_name(self):
        """Test extracting type from node name."""
        mock_node = MockNode(name="VARCHAR_TYPE")
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        result = await self.service.infer_data_type("test_field", {})
        
        # Should extract VARCHAR from node name
        self.assertEqual(result.name, DataType.VARCHAR)
    
    async def test_extract_precision_from_properties(self):
        """Test extracting precision from node properties."""
        mock_node = MockNode(properties={"precision": 50, "length": 100})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("test_field", data_type)
        
        # Should extract precision from properties
        self.assertEqual(result, 50)
    
    async def test_extract_precision_from_node_name(self):
        """Test extracting precision from node name."""
        mock_node = MockNode(name="VARCHAR_255")
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("test_field", data_type)
        
        # Should extract 255 from node name
        self.assertEqual(result, 255)
    
    def test_get_base_type(self):
        """Test base type mapping."""
        self.assertEqual(self.service._get_base_type(DataType.VARCHAR), "STRING")
        self.assertEqual(self.service._get_base_type(DataType.INTEGER), "NUMERIC")
        self.assertEqual(self.service._get_base_type(DataType.BIGINT), "NUMERIC")
        self.assertEqual(self.service._get_base_type(DataType.DECIMAL), "NUMERIC")
        self.assertEqual(self.service._get_base_type(DataType.DATE), "TEMPORAL")
        self.assertEqual(self.service._get_base_type(DataType.TIMESTAMP), "TEMPORAL")
        self.assertEqual(self.service._get_base_type(DataType.BOOLEAN), "BOOLEAN")
        self.assertEqual(self.service._get_base_type(DataType.JSON), "JSON")
        self.assertEqual(self.service._get_base_type(DataType.ARRAY), "ARRAY")
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        key1 = self.service._generate_cache_key("email", None)
        key2 = self.service._generate_cache_key("email", {})
        key3 = self.service._generate_cache_key("email", {"entity_name": "Customer"})
        
        self.assertEqual(key1, "email_")
        self.assertEqual(key2, "email_")
        self.assertNotEqual(key1, key3)
        self.assertIn("customer", key3.lower())
    
    async def test_extract_type_from_empty_graph_document(self):
        """Test extracting type from empty graph document."""
        mock_doc = MockGraphDocument(nodes=[], relationships=[])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        result = await self.service.infer_data_type("test_field", {})
        
        # Should fall back to heuristic
        self.assertIsInstance(result, DataTypeEntity)
        self.assertEqual(result.name, DataType.VARCHAR)
    
    async def test_extract_type_from_invalid_properties(self):
        """Test extracting type when properties are not dict."""
        mock_node = MockNode(properties="invalid")
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        result = await self.service.infer_data_type("test_field", {})
        
        # Should fall back to heuristic
        self.assertIsInstance(result, DataTypeEntity)
    
    async def test_extract_precision_from_empty_graph_document(self):
        """Test extracting precision from empty graph document."""
        mock_doc = MockGraphDocument(nodes=[], relationships=[])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("test_field", data_type)
        
        # Should fall back to heuristic
        self.assertIsNotNone(result)
    
    async def test_extract_precision_invalid_value(self):
        """Test extracting precision with invalid value."""
        mock_node = MockNode(properties={"precision": "invalid"})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        data_type = DataTypeEntity(name=DataType.VARCHAR, base_type="STRING")
        result = await self.service.infer_precision("test_field", data_type)
        
        # Should fall back to heuristic
        self.assertIsNotNone(result)
    
    async def test_infer_data_type_with_context_description(self):
        """Test type inference with description in context."""
        mock_node = MockNode(properties={"type": "INTEGER"})
        mock_doc = MockGraphDocument(nodes=[mock_node])
        self.mock_llm.process = Mock(return_value=mock_doc)
        
        context = {"description": "A long description that might contain useful information"}
        result = await self.service.infer_data_type("test_field", context)
        
        # Verify description was included in prompt
        call_args = self.mock_llm.process.call_args[0][0]
        self.assertIn("description", call_args.lower())

