"""Knowledge Manager Agent for complex knowledge graph operations.

This agent handles escalated operations, complex validation, reasoning,
and conflict resolution that are beyond the scope of simple agent updates.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
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


class KGUpdateType(str, Enum):
    """Types of KG updates that can be escalated."""
    COMPLEX_MERGE = "complex_merge"
    CONFLICT_RESOLUTION = "conflict_resolution"
    VALIDATION_FAILURE = "validation_failure"
    REASONING_REQUIRED = "reasoning_required"
    BATCH_UPDATE = "batch_update"
    ONTOLOGY_UPDATE = "ontology_update"


class KGUpdateResult:
    """Result of a KG update operation."""
    
    def __init__(
        self,
        success: bool,
        request_id: str,
        nodes_created: int = 0,
        edges_created: int = 0,
        conflicts_resolved: int = 0,
        validation_errors: List[str] = None,
        reasoning_applied: List[str] = None,
        rollback_performed: bool = False,
        error_message: str = None,
        timestamp: datetime = None
    ):
        self.success = success
        self.request_id = request_id
        self.nodes_created = nodes_created
        self.edges_created = edges_created
        self.conflicts_resolved = conflicts_resolved
        self.validation_errors = validation_errors or []
        self.reasoning_applied = reasoning_applied or []
        self.rollback_performed = rollback_performed
        self.error_message = error_message
        self.timestamp = timestamp or datetime.utcnow()


class KGUpdateRequest:
    """Request for escalating a KG update to the knowledge manager."""
    
    def __init__(
        self,
        update_type: KGUpdateType,
        source_agent: str,
        domain: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None,
        priority: int = 1
    ):
        self.update_type = update_type
        self.source_agent = source_agent
        self.domain = domain
        self.entities = entities
        self.relationships = relationships
        self.metadata = metadata or {}
        self.priority = priority
        self.request_id = f"{domain}_{update_type.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self.timestamp = datetime.utcnow()


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

    async def escalate_update(self, request: KGUpdateRequest) -> KGUpdateResult:
        """Handle escalated KG update requests."""
        try:
            # Log the request
            self._audit_log.append({
                "request_id": request.request_id,
                "source_agent": request.source_agent,
                "update_type": request.update_type.value,
                "timestamp": request.timestamp,
                "success": False,
                "nodes_created": 0,
                "edges_created": 0,
                "conflicts_resolved": 0,
                "validation_errors": [],
                "rollback_performed": False
            })
            
            # Validate the request
            validation_errors = []
            if not request.entities:
                validation_errors.append("No entities provided")
            if not request.domain:
                validation_errors.append("No domain specified")
            
            if validation_errors:
                self._audit_log[-1]["validation_errors"] = validation_errors
                return KGUpdateResult(
                    success=False,
                    request_id=request.request_id,
                    nodes_created=0,
                    edges_created=0,
                    conflicts_resolved=0,
                    validation_errors=validation_errors,
                    rollback_performed=False,
                    error_message="Validation failed"
                )
            
            # Process entities
            nodes_created = 0
            for entity in request.entities:
                try:
                    await self.backend.add_entity(
                        entity.get("id", f"entity_{nodes_created}"),
                        entity
                    )
                    nodes_created += 1
                except Exception as e:
                    # Rollback on failure
                    await self._rollback_entities(request.entities[:nodes_created])
                    self._audit_log[-1]["rollback_performed"] = True
                    return KGUpdateResult(
                        success=False,
                        request_id=request.request_id,
                        nodes_created=nodes_created,
                        edges_created=0,
                        conflicts_resolved=0,
                        validation_errors=[],
                        rollback_performed=True,
                        error_message=f"Failed to create entity: {str(e)}"
                    )
            
            # Process relationships
            edges_created = 0
            for relationship in request.relationships:
                try:
                    await self.backend.add_relationship(
                        relationship.get("id", f"rel_{edges_created}"),
                        relationship.get("source"),
                        relationship.get("target"),
                        relationship.get("type", "relates_to"),
                        relationship
                    )
                    edges_created += 1
                except Exception as e:
                    # Rollback on failure
                    await self._rollback_entities(request.entities)
                    await self._rollback_relationships(request.relationships[:edges_created])
                    self._audit_log[-1]["rollback_performed"] = True
                    return KGUpdateResult(
                        success=False,
                        request_id=request.request_id,
                        nodes_created=nodes_created,
                        edges_created=edges_created,
                        conflicts_resolved=0,
                        validation_errors=[],
                        rollback_performed=True,
                        error_message=f"Failed to create relationship: {str(e)}"
                    )
            
            # Update audit log
            self._audit_log[-1].update({
                "success": True,
                "nodes_created": nodes_created,
                "edges_created": edges_created,
                "conflicts_resolved": 0
            })
            
            return KGUpdateResult(
                success=True,
                request_id=request.request_id,
                nodes_created=nodes_created,
                edges_created=edges_created,
                conflicts_resolved=0,
                validation_errors=[],
                rollback_performed=False,
                error_message=None
            )
            
        except Exception as e:
            # Update audit log with error
            if self._audit_log:
                self._audit_log[-1].update({
                    "success": False,
                    "error_message": str(e)
                })
            
            return KGUpdateResult(
                success=False,
                request_id=request.request_id,
                nodes_created=0,
                edges_created=0,
                conflicts_resolved=0,
                validation_errors=[],
                rollback_performed=False,
                error_message=str(e)
            )
    
    async def _rollback_entities(self, entities: List[Dict[str, Any]]):
        """Rollback entity creation."""
        for entity in entities:
            try:
                entity_id = entity.get("id")
                if entity_id:
                    await self.backend.remove_entity(entity_id)
            except Exception:
                # Log rollback failure but continue
                pass
    
    async def _rollback_relationships(self, relationships: List[Dict[str, Any]]):
        """Rollback relationship creation."""
        for relationship in relationships:
            try:
                rel_id = relationship.get("id")
                if rel_id:
                    await self.backend.remove_relationship(rel_id)
            except Exception:
                # Log rollback failure but continue
                pass
    
    def get_audit_log(self):
        """Get the audit log of operations."""
        return self._audit_log

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