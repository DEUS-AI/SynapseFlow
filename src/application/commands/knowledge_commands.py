"""Commands for knowledge management operations."""

from typing import Dict, Any, List, Optional
from domain.commands import Command
from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class KGUpdateType(str, Enum):
    """Types of KG updates that can be escalated."""
    COMPLEX_MERGE = "complex_merge"
    CONFLICT_RESOLUTION = "conflict_resolution"
    VALIDATION_FAILURE = "validation_failure"
    REASONING_REQUIRED = "reasoning_required"
    BATCH_UPDATE = "batch_update"
    ONTOLOGY_UPDATE = "ontology_update"


class EscalateKGUpdateCommand(Command):
    """Command to escalate a KG update to the knowledge manager."""
    
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
        self.timestamp = datetime.utcnow()


class KGQueryCommand(Command):
    """Command to query the knowledge graph."""
    
    def __init__(
        self,
        domain: str,
        query_type: str,  # "entities", "relationships", "full"
        filters: Dict[str, Any] = None
    ):
        self.domain = domain
        self.query_type = query_type
        self.filters = filters or {}


class ValidateKGUpdateCommand(Command):
    """Command to validate a KG update without performing it."""
    
    def __init__(
        self,
        domain: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ):
        self.domain = domain
        self.entities = entities
        self.relationships = relationships


class GetAuditLogCommand(Command):
    """Command to get the audit log of knowledge manager operations."""
    
    def __init__(self):
        pass


class KGUpdateResult(BaseModel):
    """Result of a KG update operation."""
    success: bool
    request_id: str
    nodes_created: int = 0
    edges_created: int = 0
    conflicts_resolved: int = 0
    validation_errors: List[str] = None
    reasoning_applied: List[str] = None
    rollback_performed: bool = False
    error_message: str = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.validation_errors is None:
            self.validation_errors = []
        if self.reasoning_applied is None:
            self.reasoning_applied = []


class KGQueryResult(BaseModel):
    """Result of a KG query operation."""
    success: bool
    data: List[Dict[str, Any]]
    total_count: int
    query_type: str
    domain: str
    error_message: str = None


class ValidationResult(BaseModel):
    """Result of a KG validation operation."""
    valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.suggestions is None:
            self.suggestions = []


class AuditLogResult(BaseModel):
    """Result of an audit log query."""
    operations: List[Dict[str, Any]]
    total_operations: int
    success_rate: float
    time_range: Dict[str, datetime] = None 