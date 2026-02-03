import pytest
from unittest.mock import Mock, AsyncMock, patch
from application.commands.modeling_command import ModelingCommand
from application.commands.modeling_handler import ModelingCommandHandler
from application.agents.data_architect.modeling_workflow import ModelingWorkflow, ModelingResult
from application.agents.data_architect.dda_parser import DDAParserFactory
from application.agents.data_architect.domain_modeler import DomainModeler
from domain.dda_models import DDADocument, DataEntity, Relationship
from datetime import datetime
import tempfile
import os


class TestModelingCommand:
    """Test cases for ModelingCommand."""
    
    def test_valid_command_creation(self):
        """Test creating a valid modeling command."""
        command = ModelingCommand(
            dda_path="examples/sample_dda.md",
            domain="Customer Analytics",
            update_existing=False,
            validate_only=False,
            output_path=None
        )
        
        assert command.dda_path == "examples/sample_dda.md"
        assert command.domain == "Customer Analytics"
        assert command.update_existing is False
        assert command.validate_only is False
    
    def test_command_with_nonexistent_file(self):
        """Test that command validation fails for nonexistent files."""
        with pytest.raises(ValueError, match="DDA file not found"):
            ModelingCommand(
                dda_path="nonexistent_file.md",
                domain="Test Domain",
                update_existing=False,
                validate_only=False,
                output_path=None
            )
    
    def test_command_with_directory_path(self):
        """Test that command validation fails for directory paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Path is not a file"):
                            ModelingCommand(
                dda_path=temp_dir,
                domain="Test Domain",
                update_existing=False,
                validate_only=False,
                output_path=None
            )
    
    def test_output_path_creation(self):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "new_dir", "output.json")
            command = ModelingCommand(
                dda_path="examples/sample_dda.md",
                domain="Test Domain",
                output_path=output_path
            )
            
            assert command.output_path == output_path
            assert os.path.exists(os.path.dirname(output_path))


class TestModelingCommandHandler:
    """Test cases for ModelingCommandHandler."""
    
    @pytest.fixture
    def mock_workflow(self):
        """Create a mock modeling workflow."""
        workflow = Mock(spec=ModelingWorkflow)
        workflow.execute = AsyncMock()
        return workflow
    
    @pytest.fixture
    def handler(self, mock_workflow):
        """Create a modeling command handler with mock workflow."""
        return ModelingCommandHandler(mock_workflow)
    
    @pytest.fixture
    def valid_command(self):
        """Create a valid modeling command."""
        return ModelingCommand(
            dda_path="examples/sample_dda.md",
            domain="Customer Analytics",
            update_existing=False,
            validate_only=False,
            output_path=None
        )
    
    @pytest.mark.asyncio
    async def test_successful_handling(self, handler, mock_workflow, valid_command):
        """Test successful command handling."""
        # Setup mock result
        expected_result = ModelingResult(
            success=True,
            graph_document={"nodes": [], "relationships": []},
            artifacts={"summary": "test"}
        )
        mock_workflow.execute.return_value = expected_result
        
        # Execute handler
        result = await handler.handle(valid_command)
        
        # Verify results
        assert result.success is True
        assert result.graph_document == {"nodes": [], "relationships": []}
        assert result.artifacts == {"summary": "test"}
        mock_workflow.execute.assert_called_once_with(valid_command)
    
    @pytest.mark.asyncio
    async def test_failed_handling(self, handler, mock_workflow, valid_command):
        """Test command handling when workflow fails."""
        # Setup mock to raise exception
        mock_workflow.execute.side_effect = Exception("Test error")
        
        # Execute handler
        result = await handler.handle(valid_command)
        
        # Verify results
        assert result.success is False
        assert "Test error" in result.errors[0]
        mock_workflow.execute.assert_called_once_with(valid_command)


class TestModelingWorkflow:
    """Test cases for ModelingWorkflow."""
    
    @pytest.fixture
    def mock_parser_factory(self):
        """Create a mock parser factory."""
        factory = Mock(spec=DDAParserFactory)
        return factory
    
    @pytest.fixture
    def mock_domain_modeler(self):
        """Create a mock domain modeler."""
        modeler = Mock(spec=DomainModeler)
        modeler.create_domain_graph = AsyncMock()
        modeler.update_domain_graph = AsyncMock()
        return modeler
    
    @pytest.fixture
    def workflow(self, mock_parser_factory, mock_domain_modeler):
        """Create a modeling workflow with mocks."""
        return ModelingWorkflow(mock_parser_factory, mock_domain_modeler)
    
    @pytest.fixture
    def sample_dda_document(self):
        """Create a sample DDA document for testing."""
        return DDADocument(
            domain="Test Domain",
            stakeholders=["Team A", "Team B"],
            data_owner="Test Owner",
            effective_date=datetime.now(),
            business_context="Test business context",
            entities=[
                DataEntity(
                    name="TestEntity",
                    description="Test entity description",
                    attributes=["attr1", "attr2"],
                    business_rules=["rule1"],
                    primary_key=None,
                    foreign_keys=[]
                )
            ],
            relationships=[
                Relationship(
                    source_entity="TestEntity",
                    target_entity="TestEntity",
                    relationship_type="1:N",
                    description="Test relationship"
                )
            ]
        )
    
    @pytest.mark.asyncio
    async def test_successful_workflow_execution(self, workflow, mock_parser_factory, mock_domain_modeler, sample_dda_document):
        """Test successful workflow execution."""
        # Setup mocks
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(return_value=sample_dda_document)
        mock_parser_factory.get_parser.return_value = mock_parser
        
        mock_domain_modeler.create_domain_graph.return_value = {
            "nodes": [],
            "relationships": [],
            "domain": "Test Domain",
            "group_id": "test_group"  # Add group_id for handoff
        }
        
        # Create command with a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_file.write("# Test DDA\n")
            temp_file_path = temp_file.name
        
        try:
            command = ModelingCommand(
                dda_path=temp_file_path,
                domain="Test Domain",
                update_existing=False,
                validate_only=False,
                output_path=None
            )
            
            # Mock httpx for handoff (httpx is imported inside the method)
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_response = Mock()
                mock_response.json.return_value = {"status": "success"}
                mock_response.raise_for_status = Mock()
                mock_client_instance = AsyncMock()
                mock_client_instance.__aenter__.return_value = mock_client_instance
                mock_client_instance.__aexit__.return_value = None
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client_instance
                
                # Execute workflow
                result = await workflow.execute(command)
            
            # Debug: print result if it failed
            if not result.get("success"):
                print(f"Workflow failed: {result}")
            
            # Verify results
            assert result["success"] is True
            assert result["graph_document"] is not None
            assert result["artifacts"] is not None
            assert len(result.get("errors", [])) == 0
            
            # Verify mocks were called
            mock_parser_factory.get_parser.assert_called_once_with(temp_file_path)
            mock_parser.parse.assert_called_once_with(temp_file_path)
            mock_domain_modeler.create_domain_graph.assert_called_once_with(sample_dda_document)
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_workflow_with_validation_errors(self, workflow, mock_parser_factory, sample_dda_document):
        """Test workflow execution with validation errors."""
        # Create invalid DDA document (no domain)
        invalid_dda = sample_dda_document.model_copy()
        invalid_dda.domain = ""
        
        # Setup mocks
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(return_value=invalid_dda)
        mock_parser_factory.get_parser.return_value = mock_parser
        
        # Create command with a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_file.write("# Test DDA\n")
            temp_file_path = temp_file.name
        
        try:
            command = ModelingCommand(
                dda_path=temp_file_path,
                domain="Test Domain",
                update_existing=False,
                validate_only=False,
                output_path=None
            )
            
            # Execute workflow
            result = await workflow.execute(command)
            
            # Verify results
            assert result["success"] is False
            assert len(result.get("errors", [])) > 0
            assert "Domain is required" in result.get("errors", [])
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_workflow_with_parser_exception(self, workflow, mock_parser_factory):
        """Test workflow execution when parser fails."""
        # Setup mock to raise exception
        mock_parser = Mock()
        mock_parser.parse = AsyncMock(side_effect=Exception("Parser error"))
        mock_parser_factory.get_parser.return_value = mock_parser
        
        # Create command with a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
            temp_file.write("# Test DDA\n")
            temp_file_path = temp_file.name
        
        try:
            command = ModelingCommand(
                dda_path=temp_file_path,
                domain="Test Domain",
                update_existing=False,
                validate_only=False,
                output_path=None
            )
            
            # Execute workflow
            result = await workflow.execute(command)
            
            # Verify results
            assert result["success"] is False
            assert len(result.get("errors", [])) > 0
            assert "Parser error" in result.get("errors", [])[0]
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path) 