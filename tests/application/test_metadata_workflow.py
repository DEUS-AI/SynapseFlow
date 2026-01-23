"""Tests for MetadataGenerationWorkflow."""

import unittest
from unittest.mock import Mock, AsyncMock
import tempfile
import os
from datetime import datetime
from application.agents.data_engineer.metadata_workflow import MetadataGenerationWorkflow
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_architect.dda_parser import DDAParserFactory
from application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from application.agents.data_engineer.type_inference import TypeInferenceService
from domain.dda_models import DDADocument, DataEntity
from infrastructure.in_memory_backend import InMemoryGraphBackend
from graphiti_core import Graphiti


class TestMetadataGenerationWorkflow(unittest.IsolatedAsyncioTestCase):
    """Test cases for MetadataGenerationWorkflow."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.parser_factory = Mock(spec=DDAParserFactory)
        self.kg_backend = InMemoryGraphBackend()
        self.mock_llm = Mock(spec=Graphiti)
        self.type_inference = TypeInferenceService(self.mock_llm)
        self.metadata_builder = MetadataGraphBuilder(self.kg_backend, self.type_inference)
        self.mock_graph = Mock(spec=Graphiti)
        
        self.workflow = MetadataGenerationWorkflow(
            parser_factory=self.parser_factory,
            metadata_builder=self.metadata_builder,
            graph=self.mock_graph,
            kg_backend=self.kg_backend
        )
        
        # Mock type inference - need to return DataTypeEntity
        from domain.odin_models import DataTypeEntity, DataType
        self.type_inference.infer_data_type = AsyncMock(return_value=DataTypeEntity(
            name=DataType.VARCHAR.value,
            base_type="STRING"
        ))
        self.type_inference.infer_precision = AsyncMock(return_value=100)
        self.type_inference.infer_scale = AsyncMock(return_value=None)
    
    def _create_sample_dda(self) -> DDADocument:
        """Create a sample DDA document for testing."""
        return DDADocument(
            domain="Customer Analytics",
            stakeholders=["Marketing Team"],
            data_owner="VP of Customer Experience",
            effective_date=datetime(2024, 1, 15),
            business_context="Customer behavior analysis",
            entities=[
                DataEntity(
                    name="Customer",
                    description="Core customer information",
                    attributes=["Customer ID", "Email Address"],
                    business_rules=["Customer ID must be unique"],
                    primary_key="Customer ID",
                    foreign_keys=[]
                )
            ],
            relationships=[]
        )
    
    async def test_execute_full_workflow_success(self):
        """Test successful execution of complete workflow."""
        dda = self._create_sample_dda()
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(return_value=dda)
        self.parser_factory.get_parser = Mock(return_value=mock_parser)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Customer Analytics"
            )
            
            result = await self.workflow.execute(command)
            
            self.assertTrue(result["success"])
            self.assertEqual(result["domain"], "Customer Analytics")
            self.assertIn("metadata_graph", result)
            self.assertIn("tables_created", result["metadata_graph"])
            self.assertGreater(result["metadata_graph"]["tables_created"], 0)
        finally:
            os.unlink(temp_path)
    
    async def test_execute_with_architecture_graph_ref(self):
        """Test workflow execution with architecture graph reference."""
        dda = self._create_sample_dda()
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(return_value=dda)
        self.parser_factory.get_parser = Mock(return_value=mock_parser)
        
        # Mock architecture graph reading
        mock_search_result = Mock()
        mock_search_result.uuid = "test-uuid"
        mock_search_result.name = "Entity Customer"
        mock_search_result.attributes = {}
        self.mock_graph.search = AsyncMock(return_value=[mock_search_result])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Customer Analytics",
                architecture_graph_ref="dda_customer_analytics"
            )
            
            result = await self.workflow.execute(command)
            
            self.assertTrue(result["success"])
            # Verify architecture graph was read
            self.mock_graph.search.assert_called_once()
        finally:
            os.unlink(temp_path)
    
    async def test_execute_validation_failure(self):
        """Test workflow execution with validation failure."""
        dda = self._create_sample_dda()
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(return_value=dda)
        self.parser_factory.get_parser = Mock(return_value=mock_parser)
        
        # Mock architecture graph with validation issues
        mock_search_result = Mock()
        mock_search_result.uuid = "test-uuid"
        mock_search_result.name = "Different Entity"
        mock_search_result.attributes = {}
        self.mock_graph.search = AsyncMock(return_value=[mock_search_result])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Customer Analytics",
                architecture_graph_ref="dda_customer_analytics",
                validate_against_architecture=True
            )
            
            result = await self.workflow.execute(command)
            
            # Validation should pass (warnings only, not errors)
            # Since our validation is lenient, it should still succeed
            self.assertTrue(result["success"])
        finally:
            os.unlink(temp_path)
    
    async def test_execute_parser_error(self):
        """Test workflow execution with parser error."""
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(side_effect=Exception("Parse error"))
        self.parser_factory.get_parser = Mock(return_value=mock_parser)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Customer Analytics"
            )
            
            result = await self.workflow.execute(command)
            
            self.assertFalse(result["success"])
            self.assertIn("errors", result)
            self.assertGreater(len(result["errors"]), 0)
        finally:
            os.unlink(temp_path)
    
    async def test_read_architecture_graph(self):
        """Test reading architecture graph from Graphiti."""
        mock_search_result = Mock()
        mock_search_result.uuid = "test-uuid-1"
        mock_search_result.name = "Entity Customer"
        mock_search_result.attributes = {"type": "DataEntity"}
        
        mock_search_result2 = Mock()
        mock_search_result2.uuid = "test-uuid-2"
        mock_search_result2.name = "Entity Order"
        mock_search_result2.attributes = {"type": "DataEntity"}
        
        self.mock_graph.search = AsyncMock(return_value=[mock_search_result, mock_search_result2])
        
        result = await self.workflow._read_architecture_graph("dda_customer_analytics")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["group_id"], "dda_customer_analytics")
        self.assertEqual(result["node_count"], 2)
        self.assertEqual(len(result["nodes"]), 2)
        self.mock_graph.search.assert_called_once()
    
    async def test_read_architecture_graph_not_found(self):
        """Test reading architecture graph when not found."""
        self.mock_graph.search = AsyncMock(return_value=[])
        
        result = await self.workflow._read_architecture_graph("nonexistent_ref")
        
        self.assertIsNone(result)
    
    async def test_read_architecture_graph_error(self):
        """Test reading architecture graph with error."""
        self.mock_graph.search = AsyncMock(side_effect=Exception("Graphiti error"))
        
        result = await self.workflow._read_architecture_graph("test_ref")
        
        self.assertIsNone(result)
    
    async def test_validate_against_architecture(self):
        """Test validation against architecture graph."""
        dda = self._create_sample_dda()
        
        architecture_graph = {
            "group_id": "dda_customer_analytics",
            "nodes": [
                {
                    "uuid": "test-uuid",
                    "name": "Entity Customer",
                    "attributes": {"type": "DataEntity"}
                }
            ],
            "node_count": 1
        }
        
        result = await self.workflow._validate_against_architecture(dda, architecture_graph)
        
        self.assertTrue(result["is_valid"])
        self.assertEqual(len(result["errors"]), 0)
        # May have warnings
        self.assertIsInstance(result["warnings"], list)
    
    async def test_validate_against_architecture_empty(self):
        """Test validation with empty architecture graph."""
        dda = self._create_sample_dda()
        
        architecture_graph = {
            "group_id": "dda_customer_analytics",
            "nodes": [],
            "node_count": 0
        }
        
        result = await self.workflow._validate_against_architecture(dda, architecture_graph)
        
        self.assertTrue(result["is_valid"])
        self.assertEqual(len(result["errors"]), 0)
    
    async def test_validate_against_architecture_none(self):
        """Test validation with None architecture graph."""
        dda = self._create_sample_dda()
        
        result = await self.workflow._validate_against_architecture(dda, None)
        
        self.assertTrue(result["is_valid"])
        self.assertEqual(len(result["errors"]), 0)

