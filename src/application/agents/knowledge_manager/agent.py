"""Knowledge Manager Agent for complex knowledge graph operations.

This agent handles escalated operations, complex validation, reasoning,
and conflict resolution that are beyond the scope of simple agent updates.
"""

from typing import Dict, Any, List, Optional
from domain.agent import Agent
from domain.communication import CommunicationChannel, Message
from domain.command_bus import CommandBus
from domain.event import KnowledgeEvent
from domain.roles import Role
from domain.kg_backends import KnowledgeGraphBackend
from application.knowledge_management import KnowledgeManagerService
from application.event_bus import EventBus
from .conflict_resolver import ConflictResolver
from .validation_engine import ValidationEngine
from .reasoning_engine import ReasoningEngine


class KnowledgeManagerAgent(Agent):
    """
    Dedicated agent for complex knowledge graph operations.
    
    This agent handles:
    - Escalated operations from other agents
    - Complex validation and reasoning
    - Conflict detection and resolution
    - Audit trail management
    - Advanced RBAC enforcement
    """

    def __init__(
        self,
        agent_id: str,
        command_bus: CommandBus,
        communication_channel: CommunicationChannel,
        backend: KnowledgeGraphBackend,
        event_bus: EventBus,
        llm: Optional['Graphiti'] = None,
    ):
        super().__init__(agent_id, command_bus, communication_channel)
        self.backend = backend
        self.event_bus = event_bus
        self.llm = llm
        self.knowledge_service = KnowledgeManagerService(backend)
        self.conflict_resolver = ConflictResolver(backend)
        self.validation_engine = ValidationEngine(backend)
        self.reasoning_engine = ReasoningEngine(backend, llm=llm)
        
        # Subscribe to complex operations
        self.event_bus.subscribe("complex_entity_operation", self.handle_complex_entity)
        self.event_bus.subscribe("complex_relationship_operation", self.handle_complex_relationship)
        self.event_bus.subscribe("batch_operation", self.handle_batch_operation)
        self.event_bus.subscribe("conflict_resolution", self.handle_conflict_resolution)

    async def register_self(self):
        """Register the agent as a knowledge management service."""
        # Register capabilities in the knowledge graph
        await self.backend.add_entity(
            f"agent_{self.agent_id}",
            {
                "type": "KnowledgeManagerAgent",
                "capabilities": [
                    "complex_validation",
                    "conflict_resolution", 
                    "reasoning",
                    "audit_trail",
                    "batch_processing"
                ],
                "status": "active"
            }
        )

    async def process_messages(self) -> None:
        """Main message processing loop for the knowledge manager agent."""
        print(f"[{self.agent_id}] Knowledge Manager Agent started. Waiting for messages...")
        
        while True:
            try:
                message = await self.receive_message()
                if message:
                    await self._process_message(message)
                else:
                    # Small delay to prevent busy waiting
                    import asyncio
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[{self.agent_id}] Error processing message: {e}")
                # Continue processing other messages

    async def _process_message(self, message: Message) -> None:
        """Process a single message."""
        print(f"[{self.agent_id}] Processing message from {message.sender_id}")
        
        if isinstance(message.content, KnowledgeEvent):
            await self._handle_knowledge_event(message.content)
        elif isinstance(message.content, dict):
            await self._handle_dict_message(message.content)
        else:
            print(f"[{self.agent_id}] Unhandled message type: {type(message.content)}")

    async def _handle_knowledge_event(self, event: KnowledgeEvent) -> None:
        """Handle a knowledge event with advanced processing."""
        try:
            # Advanced validation
            validation_result = await self.validation_engine.validate_event(event)
            if not validation_result["is_valid"]:
                await self._send_validation_feedback(event, validation_result)
                return

            # Check for conflicts
            conflicts = await self.conflict_resolver.detect_conflicts(event)
            if conflicts:
                await self._handle_conflicts(event, conflicts)
                # After resolving conflicts, continue with the operation if it's still valid
                # Check if the operation can proceed after conflict resolution
                if await self._can_proceed_after_conflicts(event, conflicts):
                    print(f"[{self.agent_id}] Proceeding with operation after conflict resolution")
                else:
                    print(f"[{self.agent_id}] Operation cannot proceed after conflict resolution")
                    return

            # Apply reasoning
            reasoning_result = await self.reasoning_engine.apply_reasoning(event)
            
            # Execute the operation
            await self.knowledge_service.handle_event(event)
            
            # Send success feedback
            await self._send_success_feedback(event, reasoning_result)
            
        except Exception as e:
            await self._send_error_feedback(event, str(e))

    async def _can_proceed_after_conflicts(self, event: KnowledgeEvent, conflicts: List[Dict[str, Any]]) -> bool:
        """Check if the operation can proceed after conflict resolution."""
        # For now, allow all operations to proceed after conflict resolution
        # In a more sophisticated implementation, this could check if the conflicts
        # were resolved in a way that allows the operation to continue
        return True

    async def _handle_dict_message(self, content: Dict[str, Any]) -> None:
        """Handle dictionary-based messages."""
        message_type = content.get("type")
        
        if message_type == "escalate_operation":
            await self._handle_escalation(content)
        elif message_type == "request_validation":
            await self._handle_validation_request(content)
        elif message_type == "resolve_conflict":
            await self._handle_conflict_resolution_request(content)
        else:
            print(f"[{self.agent_id}] Unknown message type: {message_type}")

    async def _handle_escalation(self, content: Dict[str, Any]) -> None:
        """Handle escalated operations from other agents."""
        operation = content.get("operation")
        agent_id = content.get("agent_id")
        reason = content.get("reason")
        
        print(f"[{self.agent_id}] Handling escalation from {agent_id}: {reason}")
        
        # Process the escalated operation with enhanced validation
        if operation:
            event = KnowledgeEvent(
                action=operation.get("action"),
                data=operation.get("data"),
                role=operation.get("role", Role.KNOWLEDGE_MANAGER)
            )
            await self._handle_knowledge_event(event)

    async def _handle_validation_request(self, content: Dict[str, Any]) -> None:
        """Handle validation requests from other agents."""
        operation = content.get("operation")
        agent_id = content.get("agent_id")
        
        if operation:
            event = KnowledgeEvent(
                action=operation.get("action"),
                data=operation.get("data"),
                role=operation.get("role", Role.DATA_ARCHITECT)
            )
            
            validation_result = await self.validation_engine.validate_event(event)
            await self.send_message(agent_id, {
                "type": "validation_response",
                "operation_id": content.get("operation_id"),
                "is_valid": validation_result["is_valid"],
                "warnings": validation_result.get("warnings", []),
                "errors": validation_result.get("errors", [])
            })

    async def _handle_conflict_resolution_request(self, content: Dict[str, Any]) -> None:
        """Handle conflict resolution requests."""
        conflicts = content.get("conflicts", [])
        agent_id = content.get("agent_id")
        
        resolution_plan = await self.conflict_resolver.create_resolution_plan(conflicts)
        await self.send_message(agent_id, {
            "type": "conflict_resolution_plan",
            "conflicts": conflicts,
            "resolution_plan": resolution_plan
        })

    async def _handle_conflicts(self, event: KnowledgeEvent, conflicts: List[Dict[str, Any]]) -> None:
        """Handle detected conflicts."""
        print(f"[{self.agent_id}] Resolving {len(conflicts)} conflicts")
        
        # Create resolution plan
        resolution_plan = await self.conflict_resolver.create_resolution_plan(conflicts)
        
        # Apply automatic resolutions if possible
        auto_resolved = await self.conflict_resolver.apply_automatic_resolutions(conflicts)
        
        # Send feedback about conflicts
        await self._send_conflict_feedback(event, conflicts, resolution_plan, auto_resolved)

    async def _send_validation_feedback(self, event: KnowledgeEvent, validation_result: Dict[str, Any]) -> None:
        """Send validation feedback to the requesting agent."""
        # This would typically be sent back to the original agent
        print(f"[{self.agent_id}] Validation failed: {validation_result.get('errors')}")

    async def _send_success_feedback(self, event: KnowledgeEvent, reasoning_result: Dict[str, Any]) -> None:
        """Send success feedback with reasoning results."""
        print(f"[{self.agent_id}] Operation successful: {reasoning_result}")

    async def _send_error_feedback(self, event: KnowledgeEvent, error: str) -> None:
        """Send error feedback."""
        print(f"[{self.agent_id}] Operation failed: {error}")

    async def _send_conflict_feedback(self, event: KnowledgeEvent, conflicts: List[Dict[str, Any]], 
                                    resolution_plan: Dict[str, Any], auto_resolved: List[str]) -> None:
        """Send conflict feedback with resolution plan."""
        print(f"[{self.agent_id}] Conflicts detected: {len(conflicts)}")
        print(f"[{self.agent_id}] Auto-resolved: {len(auto_resolved)}")
        print(f"[{self.agent_id}] Resolution plan: {resolution_plan}")

    # Event handlers for complex operations
    async def handle_complex_entity(self, event: KnowledgeEvent) -> None:
        """Handle complex entity operations."""
        await self._handle_knowledge_event(event)

    async def handle_complex_relationship(self, event: KnowledgeEvent) -> None:
        """Handle complex relationship operations."""
        await self._handle_knowledge_event(event)

    async def handle_batch_operation(self, event: KnowledgeEvent) -> None:
        """Handle batch operations."""
        await self._handle_knowledge_event(event)

    async def handle_conflict_resolution(self, event: KnowledgeEvent) -> None:
        """Handle conflict resolution operations."""
        await self._handle_knowledge_event(event)
