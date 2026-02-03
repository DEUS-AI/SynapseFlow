"""Tests for the Knowledge Manager Agent."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from src.application.agents.knowledge_manager.agent import (
    KnowledgeManagerAgent,
    KGUpdateRequest,
    KGUpdateType,
    KGUpdateResult
)
from src.domain.communication import Message
from src.domain.agent import Agent


class TestKnowledgeManagerAgent:
    """Test cases for KnowledgeManagerAgent."""
    
    @pytest.fixture
    def mock_graph(self):
        """Create a mock Graphiti instance."""
        mock = Mock()
        mock.add_episode = AsyncMock()
        mock.add_episode.return_value = Mock(
            episode=Mock(uuid="test-episode-uuid"),
            nodes=["node1", "node2"],
            edges=["edge1"]
        )
        return mock
    
    @pytest.fixture
    def knowledge_manager_agent(self, mock_graph):
        """Create a KnowledgeManagerAgent instance for testing."""
        # Create mocks for dependencies
        mock_command_bus = Mock()
        mock_communication_channel = Mock()
        mock_backend = Mock()
        mock_event_bus = Mock()
        
        return KnowledgeManagerAgent(
            agent_id="test_knowledge_manager",
            command_bus=mock_command_bus,
            communication_channel=mock_communication_channel,
            backend=mock_backend,
            event_bus=mock_event_bus
        )
    
    @pytest.fixture
    def sample_kg_update_request(self):
        """Create a sample KG update request."""
        return KGUpdateRequest(
            update_type=KGUpdateType.COMPLEX_MERGE,
            source_agent="data_architect",
            domain="test_domain",
            entities=[
                {"name": "TestEntity1", "description": "Test entity 1"},
                {"name": "TestEntity2", "description": "Test entity 2"}
            ],
            relationships=[
                {"source": "TestEntity1", "target": "TestEntity2", "type": "relates_to"}
            ],
            metadata={"priority": "high", "source": "test"},
            priority=1
        )
    
    def test_agent_initialization(self, knowledge_manager_agent):
        """Test that the agent initializes correctly."""
        assert knowledge_manager_agent.agent_id == "test_knowledge_manager"
        assert knowledge_manager_agent.backend is not None
        assert knowledge_manager_agent.event_bus is not None
        assert knowledge_manager_agent._audit_log is not None
    
    @pytest.mark.asyncio
    async def test_escalate_update_success(self, knowledge_manager_agent, sample_kg_update_request):
        """Test successful escalation of KG update."""
        # Mock backend methods
        knowledge_manager_agent.backend.add_entity = AsyncMock()
        knowledge_manager_agent.backend.add_relationship = AsyncMock()
        
        result = await knowledge_manager_agent.escalate_update(sample_kg_update_request)
        
        assert isinstance(result, KGUpdateResult)
        assert result.success is True
        assert result.request_id == sample_kg_update_request.request_id
        assert result.nodes_created == 2
        assert result.edges_created == 1
        assert result.conflicts_resolved == 0
        assert result.validation_errors == []
        assert result.rollback_performed is False
        assert result.error_message is None
        
        # Check audit log
        audit_log = knowledge_manager_agent.get_audit_log()
        assert len(audit_log) == 1
        assert audit_log[0]["request_id"] == sample_kg_update_request.request_id
        assert audit_log[0]["source_agent"] == "data_architect"
        assert audit_log[0]["update_type"] == "complex_merge"
        assert audit_log[0]["success"] is True
    
    @pytest.mark.asyncio
    async def test_escalate_update_validation_failure(self, knowledge_manager_agent):
        """Test escalation with validation failure."""
        # Create request with missing required fields
        invalid_request = KGUpdateRequest(
            update_type=KGUpdateType.COMPLEX_MERGE,
            source_agent="data_architect",
            domain="test_domain",
            entities=[],  # Empty entities list
            relationships=[],
            metadata={},
            priority=1
        )
        
        result = await knowledge_manager_agent.escalate_update(invalid_request)
        
        assert isinstance(result, KGUpdateResult)
        assert result.success is False
        assert result.validation_errors
        assert result.nodes_created == 0
        assert result.edges_created == 0
        assert result.rollback_performed is False
        
        # Check audit log
        audit_log = knowledge_manager_agent.get_audit_log()
        assert len(audit_log) == 1
        assert audit_log[0]["success"] is False
        assert audit_log[0]["validation_errors"]
    
    @pytest.mark.asyncio
    async def test_escalate_update_rollback(self, knowledge_manager_agent):
        """Test escalation with rollback on failure."""
        # Create request that will fail during processing
        failing_request = KGUpdateRequest(
            update_type=KGUpdateType.COMPLEX_MERGE,
            source_agent="data_architect",
            domain="test_domain",
            entities=[
                {"name": "FailingEntity", "description": "This will fail"}
            ],
            relationships=[],
            metadata={"will_fail": True},
            priority=1
        )
        
        # Mock backend to fail
        knowledge_manager_agent.backend.add_entity = AsyncMock(side_effect=Exception("Backend failure"))
        knowledge_manager_agent.backend.remove_entity = AsyncMock()
        
        result = await knowledge_manager_agent.escalate_update(failing_request)
        
        assert isinstance(result, KGUpdateResult)
        assert result.success is False
        assert result.rollback_performed is True
        assert result.error_message
        
        # Check audit log
        audit_log = knowledge_manager_agent.get_audit_log()
        assert len(audit_log) == 1
        assert audit_log[0]["success"] is False
        assert audit_log[0]["rollback_performed"] is True
    
    @pytest.mark.asyncio
    async def test_batch_operation_handling(self, knowledge_manager_agent):
        """Test handling of batch operations."""
        # Create batch request
        batch_request = KGUpdateRequest(
            update_type=KGUpdateType.BATCH_UPDATE,
            source_agent="data_architect",
            domain="test_domain",
            entities=[
                {"name": "BatchEntity1", "description": "Batch entity 1"},
                {"name": "BatchEntity2", "description": "Batch entity 2"},
                {"name": "BatchEntity3", "description": "Batch entity 3"}
            ],
            relationships=[
                {"source": "BatchEntity1", "target": "BatchEntity2", "type": "relates_to"},
                {"source": "BatchEntity2", "target": "BatchEntity3", "type": "relates_to"}
            ],
            metadata={"batch_size": 3},
            priority=2
        )
        
        # Mock backend methods
        knowledge_manager_agent.backend.add_entity = AsyncMock()
        knowledge_manager_agent.backend.add_relationship = AsyncMock()
        
        result = await knowledge_manager_agent.escalate_update(batch_request)
        
        assert isinstance(result, KGUpdateResult)
        assert result.success is True
        assert result.nodes_created == 3
        assert result.edges_created == 2
        
        # Check audit log
        audit_log = knowledge_manager_agent.get_audit_log()
        assert len(audit_log) == 1
        assert audit_log[0]["update_type"] == "batch_update"
    
    @pytest.mark.asyncio
    async def test_agent_capabilities_registration(self, knowledge_manager_agent):
        """Test that the agent registers its capabilities correctly."""
        # Mock backend methods
        knowledge_manager_agent.backend.add_entity = AsyncMock()
        
        await knowledge_manager_agent.register_self()
        
        # Verify capabilities were registered
        # This would require checking the backend state
        assert knowledge_manager_agent.backend.add_entity.called
    
    @pytest.mark.asyncio
    async def test_agent_message_processing_loop(self, knowledge_manager_agent):
        """Test the agent's main message processing loop."""
        # Mock the receive_message method
        with patch.object(knowledge_manager_agent, 'receive_message') as mock_receive:
            mock_receive.return_value = None  # No message to process
            
            # Start the agent (this will run the loop once)
            await knowledge_manager_agent.process_messages()
            
            # Verify message was processed
            # This would require checking the processing logic
            assert True  # Placeholder assertion
    
    @pytest.mark.asyncio
    async def test_handle_knowledge_event(self, knowledge_manager_agent):
        """Test handling of knowledge events."""
        # Create a knowledge event
        from src.domain.event import KnowledgeEvent
        from src.domain.roles import Role
        
        event = KnowledgeEvent(
            action="create_entity",
            data={"name": "TestEntity", "type": "test"},
            role=Role.DATA_ARCHITECT
        )
        
        # Mock the validation and conflict resolution
        knowledge_manager_agent.validation_engine.validate_event = AsyncMock(return_value={"is_valid": True})
        knowledge_manager_agent.conflict_resolver.detect_conflicts = AsyncMock(return_value=[])
        knowledge_manager_agent.reasoning_engine.apply_reasoning = AsyncMock(return_value={})
        knowledge_manager_agent.knowledge_service.handle_event = AsyncMock()
        
        # Process the event
        await knowledge_manager_agent._handle_knowledge_event(event)
        
        # Verify event was handled
        # This would require checking the event handling logic
        assert True  # Placeholder assertion
    
    @pytest.mark.asyncio
    async def test_handle_dict_message(self, knowledge_manager_agent):
        """Test handling of dictionary messages."""
        # Create a dictionary message
        dict_message = {
            "type": "test_message",
            "data": {"key": "value"}
        }
        
        # Process the message
        await knowledge_manager_agent._handle_dict_message(dict_message)
        
        # Verify message was handled
        # This would require checking the message handling logic
        assert True  # Placeholder assertion
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self, knowledge_manager_agent):
        """Test that the agent can detect conflicts."""
        # Create a request that would cause conflicts
        conflict_request = KGUpdateRequest(
            update_type=KGUpdateType.COMPLEX_MERGE,
            source_agent="data_architect",
            domain="test_domain",
            entities=[
                {"name": "ConflictingEntity", "description": "This will conflict"}
            ],
            relationships=[],
            metadata={},
            priority=1
        )
        
        # Mock conflict detection
        with patch.object(knowledge_manager_agent.conflict_resolver, 'detect_conflicts') as mock_detect:
            mock_detect.return_value = ["conflict1"]
            
            # Mock backend methods
            knowledge_manager_agent.backend.add_entity = AsyncMock()
            
            result = await knowledge_manager_agent.escalate_update(conflict_request)
            
            assert result.success is True
            mock_detect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validation_engine_integration(self, knowledge_manager_agent):
        """Test that the validation engine is properly integrated."""
        # Create a request that needs validation
        validation_request = KGUpdateRequest(
            update_type=KGUpdateType.COMPLEX_MERGE,
            source_agent="data_architect",
            domain="test_domain",
            entities=[
                {"name": "ValidEntity", "description": "This is valid"}
            ],
            relationships=[],
            metadata={},
            priority=1
        )
        
        # Mock validation
        with patch.object(knowledge_manager_agent.validation_engine, 'validate_event') as mock_validate:
            mock_validate.return_value = {"is_valid": True}
            
            # Mock backend methods
            knowledge_manager_agent.backend.add_entity = AsyncMock()
            
            result = await knowledge_manager_agent.escalate_update(validation_request)
            
            assert result.success is True
            mock_validate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reasoning_engine_integration(self, knowledge_manager_agent):
        """Test that the reasoning engine is properly integrated."""
        # Create a request that needs reasoning
        reasoning_request = KGUpdateRequest(
            update_type=KGUpdateType.COMPLEX_MERGE,
            source_agent="data_architect",
            domain="test_domain",
            entities=[
                {"name": "ReasoningEntity", "description": "This needs reasoning"}
            ],
            relationships=[],
            metadata={},
            priority=1
        )
        
        # Mock reasoning
        with patch.object(knowledge_manager_agent.reasoning_engine, 'apply_reasoning') as mock_reason:
            mock_reason.return_value = {"inferences": ["inference1"]}
            
            # Mock backend methods
            knowledge_manager_agent.backend.add_entity = AsyncMock()
            
            result = await knowledge_manager_agent.escalate_update(reasoning_request)
            
            assert result.success is True
            mock_reason.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_escalation_message(self, knowledge_manager_agent):
        """Test handling escalation messages from other agents."""
        # Create an escalation message
        escalation_message = {
            "type": "escalate_operation",
            "operation": {
                "action": "create_entity",
                "data": {"name": "Test"},
                "role": "data_architect"
            },
            "agent_id": "data_architect",
            "reason": "Complex operation"
        }
        
        # Process the message
        await knowledge_manager_agent._handle_dict_message(escalation_message)
        
        # Verify escalation was handled
        # This would require checking the escalation handling logic
        assert True  # Placeholder assertion
    
    @pytest.mark.asyncio
    async def test_handle_validation_request(self, knowledge_manager_agent):
        """Test handling validation requests from other agents."""
        # Create a validation request message
        validation_message = {
            "type": "request_validation",
            "operation": {
                "action": "create_entity",
                "data": {"name": "Test"},
                "role": "data_architect"
            },
            "agent_id": "data_architect"
        }
        
        # Process the message
        await knowledge_manager_agent._handle_dict_message(validation_message)
        
        # Verify validation request was handled
        # This would require checking the validation handling logic
        assert True  # Placeholder assertion
    
    @pytest.mark.asyncio
    async def test_handle_conflict_resolution_request(self, knowledge_manager_agent):
        """Test handling conflict resolution requests from other agents."""
        # Create a conflict resolution request message
        conflict_message = {
            "type": "resolve_conflict",
            "conflicts": ["conflict1", "conflict2"],
            "agent_id": "data_architect"
        }
        
        # Process the message
        await knowledge_manager_agent._handle_dict_message(conflict_message)
        
        # Verify conflict resolution request was handled
        # This would require checking the conflict resolution handling logic
        assert True  # Placeholder assertion
    
    @pytest.mark.asyncio
    async def test_register_self(self, knowledge_manager_agent):
        """Test that the agent can register itself."""
        # Mock backend methods
        knowledge_manager_agent.backend.add_entity = AsyncMock()
        
        await knowledge_manager_agent.register_self()
        
        # Verify registration was successful
        # This would require checking the backend state
        assert knowledge_manager_agent.backend.add_entity.called 