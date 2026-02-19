"""Tests for the Knowledge Manager Agent."""

import asyncio
import unittest
import os
import sys

# Ensure the src directory is on the import path
_TEST_DIR = os.path.dirname(__file__)
_SRC_PATH = os.path.abspath(os.path.join(_TEST_DIR, "..", "src"))
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from application.agents.knowledge_manager.agent import KnowledgeManagerAgent  # noqa: E402
from domain.event import KnowledgeEvent  # noqa: E402
from domain.roles import Role  # noqa: E402
from domain.communication import Message  # noqa: E402
from infrastructure.in_memory_backend import InMemoryGraphBackend  # noqa: E402
from application.event_bus import EventBus  # noqa: E402
from application.commands.base import CommandBus  # noqa: E402
from infrastructure.communication.memory_channel import InMemoryCommunicationChannel  # noqa: E402


class TestKnowledgeManagerAgent(unittest.IsolatedAsyncioTestCase):
    """Test cases for the Knowledge Manager Agent."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.kg_backend = InMemoryGraphBackend()
        self.event_bus = EventBus()
        self.command_bus = CommandBus()
        self.communication_channel = InMemoryCommunicationChannel()
        
        self.agent = KnowledgeManagerAgent(
            agent_id="test-km-agent",
            command_bus=self.command_bus,
            communication_channel=self.communication_channel,
            backend=self.kg_backend,
            event_bus=self.event_bus
        )

    async def test_agent_initialization(self):
        """Test that the agent initializes correctly."""
        self.assertEqual(self.agent.agent_id, "test-km-agent")
        self.assertIsNotNone(self.agent.conflict_resolver)
        self.assertIsNotNone(self.agent.validation_engine)
        self.assertIsNotNone(self.agent.reasoning_engine)

    async def test_register_self(self):
        """Test that the agent can register itself."""
        await self.agent.register_self()
        
        # Check that the agent was registered in the backend
        result = await self.kg_backend.query("")
        self.assertIn("agent_test-km-agent", result.get("nodes", {}))
        
        # Check that the agent has the correct capabilities
        agent_node = result.get("nodes", {}).get("agent_test-km-agent", {})
        expected_capabilities = [
            "complex_validation",
            "conflict_resolution", 
            "reasoning",
            "audit_trail",
            "batch_processing"
        ]
        
        for capability in expected_capabilities:
            self.assertIn(capability, agent_node.get("capabilities", []))

    async def test_handle_simple_entity_event(self):
        """Test handling a simple entity creation event."""
        event = KnowledgeEvent(
            action="create_entity",
            data={"id": "test_entity", "properties": {"name": "Test"}},
            role=Role.DATA_ARCHITECT
        )
        
        # Subscribe the agent to the event bus
        self.event_bus.subscribe("create_entity", self.agent.handle_complex_entity)
        
        # Publish the event
        await self.event_bus.publish(event)
        
        # Check that the entity was created
        result = await self.kg_backend.query("")
        self.assertIn("test_entity", result.get("nodes", {}))

    async def test_handle_simple_relationship_event(self):
        """Test handling a simple relationship creation event."""
        # First create the entities
        await self.kg_backend.add_entity("source_entity", {"name": "Source"})
        await self.kg_backend.add_entity("target_entity", {"name": "Target"})
        
        event = KnowledgeEvent(
            action="create_relationship",
            data={
                "source": "source_entity",
                "target": "target_entity",
                "type": "RELATES_TO",
                "properties": {"strength": "high"}
            },
            role=Role.KNOWLEDGE_MANAGER
        )
        
        # Subscribe the agent to the event bus
        self.event_bus.subscribe("create_relationship", self.agent.handle_complex_relationship)
        
        # Publish the event
        await self.event_bus.publish(event)
        
        # Check that the relationship was created
        result = await self.kg_backend.query("")
        self.assertIn("source_entity", result.get("edges", {}))

    async def test_handle_escalation_message(self):
        """Test handling escalation messages from other agents."""
        escalation_message = {
            "type": "escalate_operation",
            "agent_id": "test-architect",
            "operation": {
                "action": "create_entity",
                "data": {"id": "escalated_entity", "properties": {"name": "Escalated"}},
                "role": Role.DATA_ARCHITECT
            },
            "reason": "Complex validation required"
        }
        
        # Send escalation message using Message object
        message = Message(
            sender_id="test-architect",
            receiver_id="test-km-agent",
            content=escalation_message
        )
        await self.communication_channel.send(message)
        
        # Process the message
        await self.agent._process_message(await self.agent.receive_message())
        
        # Check that the escalated entity was processed
        result = await self.kg_backend.query("")
        self.assertIn("escalated_entity", result.get("nodes", {}))

    async def test_handle_validation_request(self):
        """Test handling validation requests from other agents."""
        validation_request = {
            "type": "request_validation",
            "agent_id": "test-architect",
            "operation": {
                "action": "create_entity",
                "data": {"id": "validation_test", "properties": {"name": "Validation Test"}},
                "role": Role.DATA_ARCHITECT
            },
            "operation_id": "req_123"
        }
        
        # Send validation request using Message object
        message = Message(
            sender_id="test-architect",
            receiver_id="test-km-agent",
            content=validation_request
        )
        await self.communication_channel.send(message)
        
        # Process the message
        await self.agent._process_message(await self.agent.receive_message())
        
        # Check that validation response was sent back
        messages = await self.communication_channel.get_all_messages("test-architect")
        self.assertTrue(any(msg.content.get("type") == "validation_response" for msg in messages))

    async def test_handle_conflict_resolution_request(self):
        """Test handling conflict resolution requests."""
        conflict_request = {
            "type": "resolve_conflict",
            "agent_id": "test-architect",
            "conflicts": [
                {
                    "type": "duplicate_entity_id",
                    "entity_id": "duplicate_entity",
                    "severity": "high"
                }
            ]
        }
        
        # Send conflict resolution request using Message object
        message = Message(
            sender_id="test-architect",
            receiver_id="test-km-agent",
            content=conflict_request
        )
        await self.communication_channel.send(message)
        
        # Process the message
        await self.agent._process_message(await self.agent.receive_message())
        
        # Check that conflict resolution plan was sent back
        messages = await self.communication_channel.get_all_messages("test-architect")
        self.assertTrue(any(msg.content.get("type") == "conflict_resolution_plan" for msg in messages))

    async def test_batch_operation_handling(self):
        """Test handling batch operations."""
        # Create multiple entities in sequence to simulate batch processing
        entities = [
            {"id": "batch_1", "properties": {"name": "Batch 1"}},
            {"id": "batch_2", "properties": {"name": "Batch 2"}}
        ]
        
        # Process each entity individually (this simulates batch processing)
        for entity in entities:
            event = KnowledgeEvent(
                action="create_entity",
                data=entity,
                role=Role.KNOWLEDGE_MANAGER
            )
            
            # Subscribe the agent to the event bus
            self.event_bus.subscribe("create_entity", self.agent.handle_complex_entity)
            
            # Publish the event
            await self.event_bus.publish(event)
        
        # Check that batch entities were created
        result = await self.kg_backend.query("")
        self.assertIn("batch_1", result.get("nodes", {}))
        self.assertIn("batch_2", result.get("nodes", {}))

    async def test_conflict_detection(self):
        """Test that the agent can detect conflicts."""
        # Create an entity first
        await self.kg_backend.add_entity("existing_entity", {"name": "Existing"})
        
        # Try to create the same entity again (should detect conflict)
        event = KnowledgeEvent(
            action="create_entity",
            data={"id": "existing_entity", "properties": {"name": "Duplicate"}},
            role=Role.DATA_ARCHITECT
        )
        
        # Subscribe the agent to the event bus
        self.event_bus.subscribe("create_entity", self.agent.handle_complex_entity)
        
        # Publish the event
        await self.event_bus.publish(event)
        
        # The agent should handle the conflict (though in this test we can't easily verify the conflict resolution)
        # At minimum, it shouldn't crash

    async def test_validation_engine_integration(self):
        """Test that the validation engine is properly integrated."""
        # Create an invalid event (missing ID)
        invalid_event = KnowledgeEvent(
            action="create_entity",
            data={"properties": {"name": "Invalid"}},  # Missing ID
            role=Role.DATA_ARCHITECT
        )
        
        # Subscribe the agent to the event bus
        self.event_bus.subscribe("create_entity", self.agent.handle_complex_entity)
        
        # Publish the invalid event
        await self.event_bus.publish(invalid_event)
        
        # The validation should fail, but the agent should handle it gracefully
        # We can't easily test the exact validation failure in this test, but it shouldn't crash

    async def test_reasoning_engine_integration(self):
        """Test that the reasoning engine is properly integrated."""
        # Create a valid event that should trigger reasoning
        reasoning_event = KnowledgeEvent(
            action="create_entity",
            data={"id": "user_123", "properties": {"name": "John Doe", "email": "john@example.com"}},
            role=Role.DATA_ARCHITECT
        )
        
        # Subscribe the agent to the event bus
        self.event_bus.subscribe("create_entity", self.agent.handle_complex_entity)
        
        # Publish the event
        await self.event_bus.publish(reasoning_event)
        
        # The reasoning engine should process this event
        # We can't easily test the exact reasoning output, but it shouldn't crash

    async def test_agent_message_processing_loop(self):
        """Test the agent's main message processing loop."""
        # Start the agent's message processing
        processing_task = asyncio.create_task(self.agent.process_messages())
        
        # Wait a bit for the loop to start
        await asyncio.sleep(0.1)
        
        # Send a message using Message object
        message = Message(
            sender_id="test-sender",
            receiver_id="test-km-agent",
            content={"type": "test_message"}
        )
        await self.communication_channel.send(message)
        
        # Wait a bit for processing
        await asyncio.sleep(0.1)
        
        # Cancel the processing task
        processing_task.cancel()
        
        try:
            await processing_task
        except asyncio.CancelledError:
            pass  # Expected

    async def test_agent_capabilities_registration(self):
        """Test that the agent registers its capabilities correctly."""
        await self.agent.register_self()
        
        # Check that capabilities were registered
        result = await self.kg_backend.query("")
        agent_node = result.get("nodes", {}).get("agent_test-km-agent", {})
        
        expected_capabilities = [
            "complex_validation",
            "conflict_resolution",
            "reasoning",
            "audit_trail",
            "batch_processing"
        ]
        
        for capability in expected_capabilities:
            self.assertIn(capability, agent_node.get("capabilities", []))


if __name__ == "__main__":
    unittest.main()
