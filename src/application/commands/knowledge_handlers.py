"""Command handlers for knowledge management operations."""

from typing import Dict, Any, List
from domain.command_bus import CommandHandler
from application.commands.knowledge_commands import (
    EscalateKGUpdateCommand,
    KGQueryCommand,
    ValidateKGUpdateCommand,
    GetAuditLogCommand,
    KGUpdateResult,
    KGQueryResult,
    ValidationResult,
    AuditLogResult
)
from application.agents.knowledge_manager.agent import KnowledgeManagerAgent, KGUpdateRequest, KGUpdateType
from graphiti_core import Graphiti
import logging

logger = logging.getLogger(__name__)


class EscalateKGUpdateCommandHandler(CommandHandler):
    """Handler for escalating KG updates to the knowledge manager."""
    
    def __init__(self, knowledge_manager: KnowledgeManagerAgent):
        self.knowledge_manager = knowledge_manager
    
    async def handle(self, command: EscalateKGUpdateCommand) -> KGUpdateResult:
        """Handle the escalate KG update command."""
        try:
            # Convert command to KGUpdateRequest
            update_request = KGUpdateRequest(
                update_type=KGUpdateType(command.update_type),
                source_agent=command.source_agent,
                domain=command.domain,
                entities=command.entities,
                relationships=command.relationships,
                metadata=command.metadata,
                priority=command.priority
            )
            
            # Process the update
            result = await self.knowledge_manager.escalate_update(update_request)
            
            # Convert to KGUpdateResult
            return KGUpdateResult(
                success=result.success,
                request_id=result.request_id,
                nodes_created=result.nodes_created,
                edges_created=result.edges_created,
                conflicts_resolved=result.conflicts_resolved,
                validation_errors=result.validation_errors,
                reasoning_applied=result.reasoning_applied,
                rollback_performed=result.rollback_performed,
                error_message=result.error_message,
                timestamp=result.timestamp
            )
            
        except Exception as e:
            logger.error(f"Error in EscalateKGUpdateCommandHandler: {e}")
            return KGUpdateResult(
                success=False,
                request_id=f"error_{command.domain}_{command.timestamp.strftime('%Y%m%d_%H%M%S')}",
                error_message=str(e)
            )


class KGQueryCommandHandler(CommandHandler):
    """Handler for KG query commands."""
    
    def __init__(self, knowledge_manager: KnowledgeManagerAgent):
        self.knowledge_manager = knowledge_manager
    
    async def handle(self, command: KGQueryCommand) -> KGQueryResult:
        """Handle the KG query command."""
        try:
            # Create a message for the knowledge manager
            from domain.communication import Message
            
            message = Message(
                sender="command_handler",
                recipient=self.knowledge_manager.name,
                content={
                    "type": "kg_query",
                    "domain": command.domain,
                    "query_type": command.query_type,
                    "filters": command.filters
                }
            )
            
            # Process the query
            response = await self.knowledge_manager.process_message(message)
            
            # Parse the response
            if response.content.get("type") == "kg_query_response":
                return KGQueryResult(
                    success=True,
                    data=response.content.get("data", []),
                    total_count=len(response.content.get("data", [])),
                    query_type=command.query_type,
                    domain=command.domain
                )
            else:
                return KGQueryResult(
                    success=False,
                    data=[],
                    total_count=0,
                    query_type=command.query_type,
                    domain=command.domain,
                    error_message=response.content.get("error", "Unknown error")
                )
                
        except Exception as e:
            logger.error(f"Error in KGQueryCommandHandler: {e}")
            return KGQueryResult(
                success=False,
                data=[],
                total_count=0,
                query_type=command.query_type,
                domain=command.domain,
                error_message=str(e)
            )


class ValidateKGUpdateCommandHandler(CommandHandler):
    """Handler for KG validation commands."""
    
    def __init__(self, knowledge_manager: KnowledgeManagerAgent):
        self.knowledge_manager = knowledge_manager
    
    async def handle(self, command: ValidateKGUpdateCommand) -> ValidationResult:
        """Handle the KG validation command."""
        try:
            # Create a message for the knowledge manager
            from domain.communication import Message
            
            message = Message(
                sender="command_handler",
                recipient=self.knowledge_manager.name,
                content={
                    "type": "validation_request",
                    "domain": command.domain,
                    "entities": command.entities,
                    "relationships": command.relationships
                }
            )
            
            # Process the validation
            response = await self.knowledge_manager.process_message(message)
            
            # Parse the response
            if response.content.get("type") == "validation_response":
                return ValidationResult(
                    valid=response.content.get("valid", False),
                    errors=response.content.get("errors", []),
                    warnings=response.content.get("warnings", []),
                    suggestions=response.content.get("suggestions", [])
                )
            else:
                return ValidationResult(
                    valid=False,
                    errors=[response.content.get("error", "Unknown validation error")]
                )
                
        except Exception as e:
            logger.error(f"Error in ValidateKGUpdateCommandHandler: {e}")
            return ValidationResult(
                valid=False,
                errors=[str(e)]
            )


class GetAuditLogCommandHandler(CommandHandler):
    """Handler for getting audit log commands."""
    
    def __init__(self, knowledge_manager: KnowledgeManagerAgent):
        self.knowledge_manager = knowledge_manager
    
    async def handle(self, command: GetAuditLogCommand) -> AuditLogResult:
        """Handle the get audit log command."""
        try:
            # Get the audit log from the knowledge manager
            audit_log = self.knowledge_manager.get_audit_log()
            
            if not audit_log:
                return AuditLogResult(
                    operations=[],
                    total_operations=0,
                    success_rate=0.0
                )
            
            total_operations = len(audit_log)
            successful_operations = sum(1 for op in audit_log if op.get("success", False))
            success_rate = (successful_operations / total_operations) * 100 if total_operations > 0 else 0
            
            return AuditLogResult(
                operations=audit_log,
                total_operations=total_operations,
                success_rate=success_rate
            )
            
        except Exception as e:
            logger.error(f"Error in GetAuditLogCommandHandler: {e}")
            return AuditLogResult(
                operations=[],
                total_operations=0,
                success_rate=0.0
            )


def create_knowledge_command_handlers(knowledge_manager: KnowledgeManagerAgent) -> Dict[str, CommandHandler]:
    """Create all knowledge management command handlers."""
    return {
        EscalateKGUpdateCommand: EscalateKGUpdateCommandHandler(knowledge_manager),
        KGQueryCommand: KGQueryCommandHandler(knowledge_manager),
        ValidateKGUpdateCommand: ValidateKGUpdateCommandHandler(knowledge_manager),
        GetAuditLogCommand: GetAuditLogCommandHandler(knowledge_manager)
    } 