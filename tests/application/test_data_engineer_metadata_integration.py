"""Integration tests for Data Engineer metadata command registration."""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os
from application.commands.base import CommandBus
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_engineer.handlers.generate_metadata import GenerateMetadataCommandHandler
from composition_root import create_generate_metadata_command_handler, bootstrap_knowledge_management
from infrastructure.in_memory_backend import InMemoryGraphBackend
from graphiti_core import Graphiti


class TestDataEngineerMetadataIntegration(unittest.IsolatedAsyncioTestCase):
    """Test cases for Data Engineer metadata command integration."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.command_bus = CommandBus()
        self.kg_backend, _ = bootstrap_knowledge_management()
        self.mock_graph = Mock(spec=Graphiti)
    
    async def test_command_registration(self):
        """Test that GenerateMetadataCommand is registered in command bus."""
        handler = create_generate_metadata_command_handler(self.mock_graph, self.kg_backend)
        self.command_bus.register(GenerateMetadataCommand, handler)
        
        # Verify command is registered
        self.assertIn(GenerateMetadataCommand, self.command_bus.handlers)
        self.assertEqual(self.command_bus.handlers[GenerateMetadataCommand], handler)
    
    async def test_command_dispatch(self):
        """Test that command can be dispatched through command bus."""
        handler = create_generate_metadata_command_handler(self.mock_graph, self.kg_backend)
        self.command_bus.register(GenerateMetadataCommand, handler)
        
        # Mock the workflow to return success
        handler.workflow.execute = AsyncMock(return_value={
            "success": True,
            "metadata_graph": {"tables_created": 1},
            "domain": "Test Domain"
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA\n## Domain: Test Domain")
            temp_path = f.name
        
        try:
            command = GenerateMetadataCommand(
                dda_path=temp_path,
                domain="Test Domain"
            )
            
            result = await self.command_bus.dispatch(command)
            
            self.assertTrue(result["success"])
            self.assertEqual(result["domain"], "Test Domain")
            handler.workflow.execute.assert_called_once_with(command)
        finally:
            os.unlink(temp_path)
    
    async def test_a2a_endpoint_receives_command(self):
        """Test that A2A endpoint can receive and process the command."""
        from fastapi.testclient import TestClient
        from application.agents.data_engineer.server import create_app
        
        handler = create_generate_metadata_command_handler(self.mock_graph, self.kg_backend)
        self.command_bus.register(GenerateMetadataCommand, handler)
        
        # Mock the workflow
        handler.workflow.execute = AsyncMock(return_value={
            "success": True,
            "metadata_graph": {},
            "domain": "Test Domain"
        })
        
        app = create_app(self.command_bus)
        client = TestClient(app)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test DDA")
            temp_path = f.name
        
        try:
            # Test A2A endpoint
            response = client.post(
                "/v1/tasks/send",
                json={
                    "tool_name": "GenerateMetadataCommand",
                    "parameters": {
                        "dda_path": temp_path,
                        "domain": "Test Domain"
                    }
                }
            )
            
            # Should succeed (200 or 201)
            self.assertIn(response.status_code, [200, 201])
            self.assertIn("status", response.json())
        finally:
            os.unlink(temp_path)
    
    async def test_agent_json_includes_command(self):
        """Test that agent.json includes GenerateMetadataCommand as a tool."""
        from fastapi.testclient import TestClient
        from application.agents.data_engineer.server import create_app
        
        handler = create_generate_metadata_command_handler(self.mock_graph, self.kg_backend)
        self.command_bus.register(GenerateMetadataCommand, handler)
        
        app = create_app(self.command_bus)
        client = TestClient(app)
        
        response = client.get("/.well-known/agent.json")
        
        self.assertEqual(response.status_code, 200)
        agent_def = response.json()
        
        # Check that GenerateMetadataCommand is in tools
        tool_names = [tool["name"] for tool in agent_def.get("tools", [])]
        self.assertIn("GenerateMetadataCommand", tool_names)
    
    async def test_handler_factory_creates_valid_handler(self):
        """Test that handler factory creates a valid handler."""
        handler = create_generate_metadata_command_handler(self.mock_graph, self.kg_backend)
        
        self.assertIsInstance(handler, GenerateMetadataCommandHandler)
        self.assertIsNotNone(handler.workflow)
    
    async def test_command_bus_integration(self):
        """Test full integration: command bus -> handler -> workflow."""
        handler = create_generate_metadata_command_handler(self.mock_graph, self.kg_backend)
        self.command_bus.register(GenerateMetadataCommand, handler)
        
        # Verify the handler is properly set up
        self.assertIsNotNone(handler.workflow.metadata_builder)
        self.assertIsNotNone(handler.workflow.parser_factory)
        self.assertEqual(handler.workflow.graph, self.mock_graph)
        self.assertEqual(handler.workflow.kg_backend, self.kg_backend)

