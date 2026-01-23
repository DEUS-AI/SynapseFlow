"""End-to-end integration tests for metadata generation workflow."""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os
from datetime import datetime
from application.commands.modeling_command import ModelingCommand
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_architect.modeling_workflow import ModelingWorkflow
from application.agents.data_architect.dda_parser import DDAParserFactory
from application.agents.data_architect.domain_modeler import DomainModeler
from application.agents.data_engineer.metadata_workflow import MetadataGenerationWorkflow
from application.agents.data_engineer.metadata_graph_builder import MetadataGraphBuilder
from application.agents.data_engineer.type_inference import TypeInferenceService
from domain.dda_models import DDADocument, DataEntity
from infrastructure.in_memory_backend import InMemoryGraphBackend
from graphiti_core import Graphiti


class TestMetadataGenerationE2E(unittest.IsolatedAsyncioTestCase):
    """End-to-end tests for complete metadata generation workflow."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.kg_backend = InMemoryGraphBackend()
        self.mock_graph = Mock(spec=Graphiti)
        self.mock_llm = Mock(spec=Graphiti)
        
        # Setup type inference
        from domain.odin_models import DataTypeEntity, DataType
        self.type_inference = TypeInferenceService(self.mock_llm)
        self.type_inference.infer_data_type = AsyncMock(return_value=DataTypeEntity(
            name=DataType.VARCHAR.value,
            base_type="STRING"
        ))
        self.type_inference.infer_precision = AsyncMock(return_value=100)
        self.type_inference.infer_scale = AsyncMock(return_value=None)
        
        # Setup metadata builder
        self.metadata_builder = MetadataGraphBuilder(self.kg_backend, self.type_inference)
        
        # Setup parser factory with mock parser
        parser_factory = DDAParserFactory()
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(return_value=DDADocument(
            domain="Test Domain",
            stakeholders=["Team A", "Team B"],
            data_owner="Test Owner",
            effective_date=datetime(2024, 1, 15),
            business_context="Test business context",
            entities=[
                DataEntity(
                    name="Customer",
                    description="Test customer entity",
                    attributes=["Customer ID", "Email Address", "Name"],
                    business_rules=["Customer ID must be unique", "Email must be valid format"],
                    primary_key="Customer ID",
                    foreign_keys=[]
                )
            ],
            relationships=[]
        ))
        mock_parser.supports_format = Mock(return_value=True)
        parser_factory.get_parser = Mock(return_value=mock_parser)
        
        self.metadata_workflow = MetadataGenerationWorkflow(
            parser_factory=parser_factory,
            metadata_builder=self.metadata_builder,
            graph=self.mock_graph,
            kg_backend=self.kg_backend
        )
        
        # Setup modeling workflow
        domain_modeler = DomainModeler(self.mock_graph, self.mock_llm)
        self.modeling_workflow = ModelingWorkflow(parser_factory, domain_modeler)
        
        # Mock Graphiti responses
        self.mock_graph.add_episode = AsyncMock(return_value=Mock(
            episode=Mock(uuid="test-episode-uuid"),
            nodes=[],
            edges=[]
        ))
        self.mock_graph.search = AsyncMock(return_value=[])
    
    def _create_sample_dda_file(self) -> str:
        """Create a sample DDA file for testing."""
        content = """# Data Delivery Agreement - Test Domain

## Document Information
- **Domain**: Test Domain
- **Stakeholders**: Team A, Team B
- **Data Owner**: Test Owner
- **Effective Date**: 2024-01-15

## Business Context
Test business context for integration testing.

## Data Entities

### Customer
- **Description**: Test customer entity
- **Key Attributes**:
  - Customer ID (Primary Key)
  - Email Address
  - Name
- **Business Rules**:
  - Customer ID must be unique
  - Email must be valid format
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            return f.name
    
    async def test_complete_workflow_dda_to_metadata(self):
        """Test complete workflow: DDA → Architecture Graph → Metadata Graph."""
        dda_path = self._create_sample_dda_file()
        
        try:
            # Step 1: Data Architect processes DDA → creates architecture graph
            modeling_command = ModelingCommand(
                dda_path=dda_path,
                domain="Test Domain",
                update_existing=False,
                validate_only=False
            )
            
            # Mock domain modeler to return a graph document with group_id
            self.modeling_workflow.domain_modeler.create_domain_graph = AsyncMock(return_value={
                "episode_uuid": "test-episode-uuid",
                "group_id": "dda_test_domain",
                "domain": "Test Domain",
                "entities_count": 1,
                "nodes_created": 5,
                "edges_created": 3
            })
            
            # Mock httpx for handoff
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_response = Mock()
                mock_response.json.return_value = {"status": "success"}
                mock_response.raise_for_status = Mock()
                mock_client_instance = AsyncMock()
                mock_client_instance.__aenter__.return_value = mock_client_instance
                mock_client_instance.__aexit__.return_value = None
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client_instance
                
                modeling_result = await self.modeling_workflow.execute(modeling_command)
            
            # Verify architecture graph was created
            self.assertTrue(modeling_result["success"])
            self.assertIn("group_id", modeling_result["graph_document"])
            architecture_graph_ref = modeling_result["graph_document"]["group_id"]
            
            # Step 2: Data Engineer generates metadata graph
            metadata_command = GenerateMetadataCommand(
                dda_path=dda_path,
                domain="Test Domain",
                architecture_graph_ref=architecture_graph_ref,
                validate_against_architecture=True
            )
            
            metadata_result = await self.metadata_workflow.execute(metadata_command)
            
            # Debug: print result if it failed
            if not metadata_result.get("success"):
                print(f"Metadata workflow failed: {metadata_result}")
            
            # Verify metadata graph was created
            self.assertTrue(metadata_result["success"], f"Metadata workflow failed: {metadata_result}")
            self.assertIn("metadata_graph", metadata_result)
            self.assertGreater(metadata_result["metadata_graph"]["tables_created"], 0)
            self.assertGreater(metadata_result["metadata_graph"]["columns_created"], 0)
            
            # Step 3: Verify metadata graph entities in backend
            graph_state = await self.kg_backend.query("")
            self.assertIn("nodes", graph_state)
            
            # Should have catalog, schema, table, columns
            node_ids = list(graph_state["nodes"].keys())
            catalog_nodes = [n for n in node_ids if n.startswith("catalog:")]
            schema_nodes = [n for n in node_ids if n.startswith("schema:")]
            table_nodes = [n for n in node_ids if n.startswith("table:")]
            column_nodes = [n for n in node_ids if n.startswith("column:")]
            
            self.assertGreater(len(catalog_nodes), 0)
            self.assertGreater(len(schema_nodes), 0)
            self.assertGreater(len(table_nodes), 0)
            self.assertGreater(len(column_nodes), 0)
            
        finally:
            os.unlink(dda_path)
    
    async def test_handoff_workflow(self):
        """Test that Data Architect hands off to Data Engineer via A2A."""
        dda_path = self._create_sample_dda_file()
        
        try:
            modeling_command = ModelingCommand(
                dda_path=dda_path,
                domain="Test Domain",
                update_existing=False
            )
            
            # Mock domain modeler
            self.modeling_workflow.domain_modeler.create_domain_graph = AsyncMock(return_value={
                "group_id": "dda_test_domain",
                "domain": "Test Domain"
            })
            
            # Mock httpx for A2A handoff
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_response = Mock()
                mock_response.json.return_value = {"status": "success", "message": "GenerateMetadataCommand dispatched."}
                mock_response.raise_for_status = Mock()
                mock_client_instance = AsyncMock()
                mock_client_instance.__aenter__.return_value = mock_client_instance
                mock_client_instance.__aexit__.return_value = None
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client_instance
                
                result = await self.modeling_workflow.execute(modeling_command)
            
            # Verify handoff was attempted
            self.assertTrue(result["success"])
            self.assertIn("handoff", result["workflow_state"])
            handoff_result = result["workflow_state"]["handoff"]
            
            # Handoff may succeed or fail (depending on Data Engineer availability)
            # But it should be attempted
            self.assertIn("success", handoff_result)
            self.assertIn("data_engineer_url", handoff_result)
            
            # Verify HTTP call was made
            if handoff_result.get("success"):
                mock_client_instance.post.assert_called_once()
                call_args = mock_client_instance.post.call_args
                self.assertIn("/v1/tasks/send", call_args[0][0])
                self.assertEqual(call_args[1]["json"]["tool_name"], "GenerateMetadataCommand")
            
        finally:
            os.unlink(dda_path)

