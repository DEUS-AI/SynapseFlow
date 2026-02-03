"""Tests for GenerateMetadataCommand and handler."""

import unittest
from unittest.mock import Mock, AsyncMock
import tempfile
import os
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_engineer.handlers.generate_metadata import GenerateMetadataCommandHandler
from application.agents.data_engineer.metadata_workflow import MetadataGenerationWorkflow


class TestGenerateMetadataCommand(unittest.TestCase):
    """Test cases for GenerateMetadataCommand."""
    
    def test_valid_command_creation(self):
        """Test creating a valid metadata command."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA\n## Domain: Test Domain")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Test Domain",
                architecture_graph_ref="test_ref",
                validate_against_architecture=True
            )
            
            self.assertEqual(command.dda_path, temp_path)
            self.assertEqual(command.domain, "Test Domain")
            self.assertEqual(command.architecture_graph_ref, "test_ref")
            self.assertTrue(command.validate_against_architecture)
        finally:
            os.unlink(temp_path)
    
    def test_command_with_nonexistent_file(self):
        """Test that command validation fails for nonexistent files."""
        with self.assertRaises(ValueError) as context:
            GenerateMetadataCommand(
                dda_path="nonexistent_file.md",
                domain="Test Domain"
            )
        self.assertIn("DDA file not found", str(context.exception))
    
    def test_command_with_directory_path(self):
        """Test that command validation fails for directory paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as context:
                GenerateMetadataCommand(
                    dda_path=temp_dir,
                    domain="Test Domain"
                )
            self.assertIn("Path is not a file", str(context.exception))
    
    def test_command_with_optional_fields(self):
        """Test command creation with optional fields."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Test Domain"
            )
            
            self.assertIsNone(command.architecture_graph_ref)
            self.assertTrue(command.validate_against_architecture)  # Default value
        finally:
            os.unlink(temp_path)
    
    def test_command_without_architecture_ref(self):
        """Test command creation without architecture graph reference."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Test Domain",
                validate_against_architecture=False
            )
            
            self.assertIsNone(command.architecture_graph_ref)
            self.assertFalse(command.validate_against_architecture)
        finally:
            os.unlink(temp_path)


class TestGenerateMetadataCommandHandler(unittest.IsolatedAsyncioTestCase):
    """Test cases for GenerateMetadataCommandHandler."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.mock_workflow = Mock(spec=MetadataGenerationWorkflow)
        self.handler = GenerateMetadataCommandHandler(self.mock_workflow)
    
    async def test_handler_execution_success(self):
        """Test successful handler execution."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Test Domain"
            )
            
            expected_result = {
                "success": True,
                "metadata_graph": {
                    "tables_created": 2,
                    "columns_created": 5
                },
                "domain": "Test Domain"
            }
            
            self.mock_workflow.execute = AsyncMock(return_value=expected_result)
            
            result = await self.handler.handle(command)
            
            self.assertTrue(result["success"])
            self.assertEqual(result["domain"], "Test Domain")
            self.mock_workflow.execute.assert_called_once_with(command)
        finally:
            os.unlink(temp_path)
    
    async def test_handler_execution_failure(self):
        """Test handler execution with workflow failure."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Test Domain"
            )
            
            self.mock_workflow.execute = AsyncMock(side_effect=Exception("Workflow error"))
            
            result = await self.handler.handle(command)
            
            self.assertFalse(result["success"])
            self.assertIn("errors", result)
            self.assertGreater(len(result["errors"]), 0)
            self.assertIn("Workflow error", result["errors"][0])
        finally:
            os.unlink(temp_path)
    
    async def test_handler_with_architecture_ref(self):
        """Test handler execution with architecture graph reference."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Test Domain",
                architecture_graph_ref="dda_test_domain"
            )
            
            expected_result = {
                "success": True,
                "metadata_graph": {},
                "domain": "Test Domain"
            }
            
            self.mock_workflow.execute = AsyncMock(return_value=expected_result)
            
            result = await self.handler.handle(command)
            
            self.assertTrue(result["success"])
            # Verify command was passed with architecture_ref
            call_args = self.mock_workflow.execute.call_args[0][0]
            self.assertEqual(call_args.architecture_graph_ref, "dda_test_domain")
        finally:
            os.unlink(temp_path)

