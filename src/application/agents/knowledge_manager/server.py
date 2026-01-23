"""HTTP server for the Knowledge Manager Agent."""

import asyncio
import json
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from domain.communication import Message
from .agent import KnowledgeManagerAgent, KGUpdateRequest, KGUpdateType, KGUpdateResult
from graphiti_core import Graphiti

logger = logging.getLogger(__name__)

# Pydantic models for API
class KGUpdateRequestModel(BaseModel):
    update_type: str
    source_agent: str
    domain: str
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any] = {}
    priority: int = 1

class KGQueryRequestModel(BaseModel):
    domain: str
    query_type: str  # "entities", "relationships", "full"
    filters: Dict[str, Any] = {}

class ValidationRequestModel(BaseModel):
    domain: str
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]

class AuditLogResponse(BaseModel):
    operations: List[Dict[str, Any]]
    total_operations: int
    success_rate: float

class KnowledgeManagerServer:
    """HTTP server for the Knowledge Manager Agent."""
    
    def __init__(self, agent: KnowledgeManagerAgent):
        self.agent = agent
        self.app = FastAPI(
            title="Knowledge Manager Agent API",
            description="API for escalated and complex KG operations",
            version="1.0.0"
        )
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.post("/kg/update")
        async def escalate_kg_update(request: KGUpdateRequestModel):
            """Escalate a KG update to the knowledge manager."""
            try:
                # Convert to internal request format
                update_request = KGUpdateRequest(
                    update_type=KGUpdateType(request.update_type),
                    source_agent=request.source_agent,
                    domain=request.domain,
                    entities=request.entities,
                    relationships=request.relationships,
                    metadata=request.metadata,
                    priority=request.priority
                )
                
                # Process the update
                result = await self.agent.escalate_update(update_request)
                
                return {
                    "success": result.success,
                    "request_id": result.request_id,
                    "nodes_created": result.nodes_created,
                    "edges_created": result.edges_created,
                    "conflicts_resolved": result.conflicts_resolved,
                    "validation_errors": result.validation_errors,
                    "reasoning_applied": result.reasoning_applied,
                    "rollback_performed": result.rollback_performed,
                    "error_message": result.error_message
                }
                
            except Exception as e:
                logger.error(f"Error in escalate_kg_update: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/kg/query")
        async def query_kg(request: KGQueryRequestModel):
            """Query the knowledge graph."""
            try:
                # Create a message for the agent
                message = Message(
                    sender="api",
                    recipient=self.agent.name,
                    content={
                        "type": "kg_query",
                        "domain": request.domain,
                        "query_type": request.query_type,
                        "filters": request.filters
                    }
                )
                
                # Process the query
                response = await self.agent.process_message(message)
                
                return response.content
                
            except Exception as e:
                logger.error(f"Error in query_kg: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/kg/validate")
        async def validate_kg_update(request: ValidationRequestModel):
            """Validate a KG update without performing it."""
            try:
                # Create a message for the agent
                message = Message(
                    sender="api",
                    recipient=self.agent.name,
                    content={
                        "type": "validation_request",
                        "domain": request.domain,
                        "entities": request.entities,
                        "relationships": request.relationships
                    }
                )
                
                # Process the validation
                response = await self.agent.process_message(message)
                
                return response.content
                
            except Exception as e:
                logger.error(f"Error in validate_kg_update: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/audit/log")
        async def get_audit_log():
            """Get the audit log of operations."""
            try:
                audit_log = self.agent.get_audit_log()
                
                if not audit_log:
                    return AuditLogResponse(
                        operations=[],
                        total_operations=0,
                        success_rate=0.0
                    )
                
                total_operations = len(audit_log)
                successful_operations = sum(1 for op in audit_log if op.get("success", False))
                success_rate = (successful_operations / total_operations) * 100 if total_operations > 0 else 0
                
                return AuditLogResponse(
                    operations=audit_log,
                    total_operations=total_operations,
                    success_rate=success_rate
                )
                
            except Exception as e:
                logger.error(f"Error in get_audit_log: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "agent": self.agent.name,
                "processing": self.agent._processing
            }
        
        @self.app.get("/")
        async def root():
            """Root endpoint with API information."""
            return {
                "service": "Knowledge Manager Agent API",
                "version": "1.0.0",
                "endpoints": {
                    "POST /kg/update": "Escalate KG update",
                    "POST /kg/query": "Query KG",
                    "POST /kg/validate": "Validate KG update",
                    "GET /audit/log": "Get audit log",
                    "GET /health": "Health check"
                }
            }
    
    async def start(self, host: str = "0.0.0.0", port: int = 8003):
        """Start the server."""
        import uvicorn
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI app instance."""
        return self.app


async def create_knowledge_manager_server(graph: Graphiti, llm: Graphiti) -> KnowledgeManagerServer:
    """Create a knowledge manager server instance."""
    agent = KnowledgeManagerAgent(graph, llm)
    await agent.start()
    return KnowledgeManagerServer(agent) 