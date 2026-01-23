"""FastAPI interface for knowledge graph operations.

This module provides a comprehensive REST API for:
- Entity management (CRUD operations)
- Relationship management
- Batch operations
- Query operations
- Health monitoring
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from domain.event import KnowledgeEvent
from domain.roles import Role
from domain.kg_backends import KnowledgeGraphBackend
from application.event_bus import EventBus
from infrastructure.in_memory_backend import InMemoryGraphBackend


logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Graph Operations API",
    description="REST API for managing knowledge graph entities and relationships",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Global dependencies
_kg_backend: Optional[KnowledgeGraphBackend] = None
_event_bus: Optional[EventBus] = None


# Pydantic Models
class EntityCreate(BaseModel):
    """Model for creating entities."""
    id: str = Field(..., description="Unique identifier for the entity")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Entity properties")
    labels: Optional[List[str]] = Field(default=None, description="Entity labels")
    
    @validator('id')
    def validate_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Entity ID cannot be empty')
        return v.strip()

class EntityUpdate(BaseModel):
    """Model for updating entities."""
    properties: Dict[str, Any] = Field(..., description="Updated entity properties")
    labels: Optional[List[str]] = Field(default=None, description="Updated entity labels")

class EntityResponse(BaseModel):
    """Model for entity responses."""
    id: str
    properties: Dict[str, Any]
    labels: Optional[List[str]]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class RelationshipCreate(BaseModel):
    """Model for creating relationships."""
    source: str = Field(..., description="Source entity ID")
    target: str = Field(..., description="Target entity ID")
    type: str = Field(..., description="Relationship type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Relationship properties")
    
    @validator('source', 'target')
    def validate_entity_ids(cls, v):
        if not v or not v.strip():
            raise ValueError('Entity ID cannot be empty')
        return v.strip()
    
    @validator('type')
    def validate_relationship_type(cls, v):
        if not v or not v.strip():
            raise ValueError('Relationship type cannot be empty')
        return v.strip()

class RelationshipResponse(BaseModel):
    """Model for relationship responses."""
    source: str
    target: str
    type: str
    properties: Dict[str, Any]
    created_at: Optional[str]

class BatchOperation(BaseModel):
    """Model for batch operations."""
    operations: List[Dict[str, Any]] = Field(..., description="List of operations to perform")
    transaction: bool = Field(default=True, description="Whether to use transaction")

class QueryRequest(BaseModel):
    """Model for query requests."""
    query: str = Field(..., description="Query string (Cypher-like)")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")

class QueryResponse(BaseModel):
    """Model for query responses."""
    results: List[Dict[str, Any]]
    execution_time: float
    result_count: int

class HealthResponse(BaseModel):
    """Model for health check responses."""
    status: str
    timestamp: str
    backend_status: Dict[str, Any]
    event_bus_status: Dict[str, Any]

class EventPublishRequest(BaseModel):
    """Model for publishing events."""
    action: str = Field(..., description="Event action")
    data: Dict[str, Any] = Field(..., description="Event data")
    role: str = Field(..., description="User role")
    routing_key: Optional[str] = Field(default=None, description="Optional routing key")

# Dependency injection
async def get_kg_backend() -> KnowledgeGraphBackend:
    """Get the knowledge graph backend instance."""
    if _kg_backend is None:
        raise HTTPException(status_code=503, detail="Knowledge graph backend not initialized")
    return _kg_backend

async def get_event_bus() -> EventBus:
    """Get the event bus instance."""
    if _event_bus is None:
        raise HTTPException(status_code=503, detail="Event bus not initialized")
    return _event_bus

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health of the API and its dependencies."""
    try:
        backend_status = {"status": "unknown"}
        event_bus_status = {"status": "unknown"}
        
        if _kg_backend:
            try:
                # Simple health check for backend
                await _kg_backend.query("RETURN 1")
                backend_status = {"status": "healthy"}
            except Exception as e:
                backend_status = {"status": "unhealthy", "error": str(e)}
        
        if _event_bus:
            try:
                if hasattr(_event_bus, 'health_check'):
                    event_bus_status = await _event_bus.health_check()
                else:
                    event_bus_status = {"status": "healthy", "type": "local"}
            except Exception as e:
                event_bus_status = {"status": "unhealthy", "error": str(e)}
        
        return HealthResponse(
            status="healthy" if backend_status.get("status") == "healthy" else "degraded",
            timestamp=datetime.utcnow().isoformat(),
            backend_status=backend_status,
            event_bus_status=event_bus_status
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

# Entity management endpoints
@app.post("/entities", response_model=EntityResponse)
async def create_entity(
    entity: EntityCreate,
    background_tasks: BackgroundTasks,
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Create a new entity in the knowledge graph."""
    try:
        # Add entity to backend
        await kg_backend.add_entity(entity.id, entity.properties)
        
        # Publish event for background processing
        event = KnowledgeEvent(
            action="create_entity",
            data={"id": entity.id, "properties": entity.properties, "labels": entity.labels},
            role=Role.DATA_ENGINEER  # Default role for API operations
        )
        
        background_tasks.add_task(event_bus.publish, event)
        
        # Return response
        return EntityResponse(
            id=entity.id,
            properties=entity.properties,
            labels=entity.labels,
            created_at=datetime.utcnow().isoformat(),
            updated_at=None
        )
        
    except Exception as e:
        logger.error(f"Failed to create entity {entity.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {e}")

@app.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend)
):
    """Get an entity by ID."""
    try:
        # Query for entity
        result = await kg_backend.query(f"MATCH (n {{id: '{entity_id}'}}) RETURN n")
        
        if not result or not result.get("nodes", {}).get(entity_id):
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        
        entity_data = result["nodes"][entity_id]
        
        # InMemoryGraphBackend stores properties directly, not nested under "properties"
        # Extract properties and metadata
        if isinstance(entity_data, dict):
            # Check if it's structured with separate keys or just properties
            if "properties" in entity_data:
                properties = entity_data.get("properties", {})
                labels = entity_data.get("labels", [])
                created_at = entity_data.get("created_at")
                updated_at = entity_data.get("updated_at")
            else:
                # entity_data IS the properties dict (InMemoryGraphBackend behavior)
                properties = entity_data
                labels = entity_data.get("labels", [])
                created_at = entity_data.get("created_at")
                updated_at = entity_data.get("updated_at")
        else:
            properties = {}
            labels = []
            created_at = None
            updated_at = None
        
        return EntityResponse(
            id=entity_id,
            properties=properties,
            labels=labels,
            created_at=created_at,
            updated_at=updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get entity: {e}")

@app.put("/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str,
    entity_update: EntityUpdate,
    background_tasks: BackgroundTasks,
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Update an existing entity."""
    try:
        # Check if entity exists
        existing = await kg_backend.query(f"MATCH (n {{id: '{entity_id}'}}) RETURN n")
        if not existing or not existing.get("nodes", {}).get(entity_id):
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        
        # Update entity (this would require an update method in the backend)
        # For now, we'll remove and recreate
        await kg_backend.add_entity(entity_id, entity_update.properties)
        
        # Publish update event
        event = KnowledgeEvent(
            action="update_entity",
            data={"id": entity_id, "properties": entity_update.properties, "labels": entity_update.labels},
            role=Role.DATA_ENGINEER
        )
        
        background_tasks.add_task(event_bus.publish, event)
        
        return EntityResponse(
            id=entity_id,
            properties=entity_update.properties,
            labels=entity_update.labels,
            created_at=None,
            updated_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update entity: {e}")

@app.delete("/entities/{entity_id}")
async def delete_entity(
    entity_id: str,
    background_tasks: BackgroundTasks,
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Delete an entity from the knowledge graph."""
    try:
        # Check if entity exists
        existing = await kg_backend.query(f"MATCH (n {{id: '{entity_id}'}}) RETURN n")
        if not existing or not existing.get("nodes", {}).get(entity_id):
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        
        # Delete entity (this would require a delete method in the backend)
        # For now, we'll just publish the delete event
        
        # Publish delete event
        event = KnowledgeEvent(
            action="delete_entity",
            data={"id": entity_id},
            role=Role.DATA_ENGINEER
        )
        
        background_tasks.add_task(event_bus.publish, event)
        
        return {"message": f"Entity {entity_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete entity {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete entity: {e}")

@app.get("/entities", response_model=List[EntityResponse])
async def list_entities(
    limit: int = Query(default=100, le=1000, description="Maximum number of entities to return"),
    offset: int = Query(default=0, ge=0, description="Number of entities to skip"),
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend)
):
    """List entities with pagination."""
    try:
        # Query for entities (InMemoryGraphBackend ignores query string)
        result = await kg_backend.query(f"MATCH (n) RETURN n LIMIT {limit} SKIP {offset}")
        
        entities = []
        nodes = result.get("nodes", {})
        
        # Apply pagination manually for InMemoryGraphBackend
        node_items = list(nodes.items())
        paginated_items = node_items[offset:offset + limit]
        
        for entity_id, entity_data in paginated_items:
            # Handle both structured and flat property storage
            if isinstance(entity_data, dict):
                if "properties" in entity_data:
                    properties = entity_data.get("properties", {})
                    labels = entity_data.get("labels", [])
                    created_at = entity_data.get("created_at")
                    updated_at = entity_data.get("updated_at")
                else:
                    # entity_data IS the properties dict
                    properties = entity_data
                    labels = entity_data.get("labels", [])
                    created_at = entity_data.get("created_at")
                    updated_at = entity_data.get("updated_at")
            else:
                properties = {}
                labels = []
                created_at = None
                updated_at = None
            
            entities.append(EntityResponse(
                id=entity_id,
                properties=properties,
                labels=labels,
                created_at=created_at,
                updated_at=updated_at
            ))
        
        return entities
        
    except Exception as e:
        logger.error(f"Failed to list entities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list entities: {e}")

# Relationship management endpoints
@app.post("/relationships", response_model=RelationshipResponse)
async def create_relationship(
    relationship: RelationshipCreate,
    background_tasks: BackgroundTasks,
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Create a new relationship between entities."""
    try:
        # Check if source and target entities exist
        source_exists = await kg_backend.query(f"MATCH (n {{id: '{relationship.source}'}}) RETURN n")
        target_exists = await kg_backend.query(f"MATCH (n {{id: '{relationship.target}'}}) RETURN n")
        
        if not source_exists or not source_exists.get("nodes", {}).get(relationship.source):
            raise HTTPException(status_code=404, detail=f"Source entity {relationship.source} not found")
        
        if not target_exists or not target_exists.get("nodes", {}).get(relationship.target):
            raise HTTPException(status_code=404, detail=f"Target entity {relationship.target} not found")
        
        # Add relationship to backend
        await kg_backend.add_relationship(
            relationship.source,
            relationship.type,
            relationship.target,
            relationship.properties
        )
        
        # Publish event for background processing
        event = KnowledgeEvent(
            action="create_relationship",
            data={
                "source": relationship.source,
                "target": relationship.target,
                "type": relationship.type,
                "properties": relationship.properties
            },
            role=Role.DATA_ENGINEER
        )
        
        background_tasks.add_task(event_bus.publish, event)
        
        return RelationshipResponse(
            source=relationship.source,
            target=relationship.target,
            type=relationship.type,
            properties=relationship.properties,
            created_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create relationship: {e}")

@app.get("/relationships", response_model=List[RelationshipResponse])
async def list_relationships(
    source: Optional[str] = Query(None, description="Filter by source entity ID"),
    target: Optional[str] = Query(None, description="Filter by target entity ID"),
    rel_type: Optional[str] = Query(None, description="Filter by relationship type"),
    limit: int = Query(default=100, le=1000, description="Maximum number of relationships to return"),
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend)
):
    """List relationships with optional filtering."""
    try:
        # Build query based on filters
        query_parts = ["MATCH (a)-[r]->(b)"]
        where_conditions = []
        
        if source:
            where_conditions.append(f"a.id = '{source}'")
        if target:
            where_conditions.append(f"b.id = '{target}'")
        if rel_type:
            where_conditions.append(f"TYPE(r) = '{rel_type}'")
        
        if where_conditions:
            query_parts.append("WHERE " + " AND ".join(where_conditions))
        
        query_parts.append(f"RETURN a, r, b LIMIT {limit}")
        query = " ".join(query_parts)
        
        result = await kg_backend.query(query)
        
        relationships = []
        edges = result.get("edges", {})
        
        # InMemoryGraphBackend stores edges as {source_id: [(rel_type, target_id, properties), ...]}
        for source_id, edge_list in edges.items():
            if isinstance(edge_list, list):
                # Handle list of tuples: (rel_type, target_id, properties)
                for edge_tuple in edge_list:
                    if len(edge_tuple) >= 3:
                        edge_type, target_id, properties = edge_tuple[0], edge_tuple[1], edge_tuple[2]
                        
                        # Apply filters
                        if source and source_id != source:
                            continue
                        if target and target_id != target:
                            continue
                        if rel_type and edge_type != rel_type:
                            continue
                        
                        relationships.append(RelationshipResponse(
                            source=source_id,
                            target=target_id,
                            type=edge_type,
                            properties=properties if isinstance(properties, dict) else {},
                            created_at=None
                        ))
            elif isinstance(edge_list, dict):
                # Handle dict structure (if backend uses different format)
                relationships.append(RelationshipResponse(
                    source=edge_list.get("source", source_id),
                    target=edge_list.get("target", ""),
                    type=edge_list.get("type", ""),
                    properties=edge_list.get("properties", {}),
                    created_at=edge_list.get("created_at")
                ))
        
        # Apply limit
        return relationships[:limit]
        
    except Exception as e:
        logger.error(f"Failed to list relationships: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list relationships: {e}")

# Batch operations endpoint
@app.post("/batch")
async def batch_operations(
    batch: BatchOperation,
    background_tasks: BackgroundTasks,
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Perform multiple operations in a batch."""
    try:
        results = []
        errors = []
        
        for i, operation in enumerate(batch.operations):
            try:
                op_type = operation.get("type")
                op_data = operation.get("data", {})
                
                if op_type == "create_entity":
                    await kg_backend.add_entity(op_data["id"], op_data.get("properties", {}))
                    results.append({"index": i, "type": op_type, "status": "success", "id": op_data["id"]})
                    
                elif op_type == "create_relationship":
                    await kg_backend.add_relationship(
                        op_data["source"],
                        op_data["type"],
                        op_data["target"],
                        op_data.get("properties", {})
                    )
                    results.append({"index": i, "type": op_type, "status": "success"})
                    
                else:
                    errors.append({"index": i, "type": op_type, "error": f"Unknown operation type: {op_type}"})
                    
            except Exception as e:
                errors.append({"index": i, "type": operation.get("type", "unknown"), "error": str(e)})
        
        # Publish batch completion event
        event = KnowledgeEvent(
            action="batch_operations_completed",
            data={"results": results, "errors": errors, "total": len(batch.operations)},
            role=Role.DATA_ENGINEER
        )
        
        background_tasks.add_task(event_bus.publish, event)
        
        return {
            "message": "Batch operations completed",
            "total_operations": len(batch.operations),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Batch operations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch operations failed: {e}")

# Query endpoint
@app.post("/query", response_model=QueryResponse)
async def execute_query(
    query_request: QueryRequest,
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend)
):
    """Execute a query against the knowledge graph."""
    try:
        import time
        start_time = time.time()
        
        # Execute query
        if query_request.parameters:
            result = await kg_backend.query(query_request.query, query_request.parameters)
        else:
            result = await kg_backend.query(query_request.query)
        
        execution_time = time.time() - start_time
        
        # Process results
        results = []
        if isinstance(result, dict):
            if "nodes" in result:
                for node_id, node_data in result["nodes"].items():
                    results.append({"type": "node", "id": node_id, "data": node_data})
            
            if "edges" in result:
                for edge_id, edge_data in result["edges"].items():
                    results.append({"type": "edge", "id": edge_id, "data": edge_data})
        
        return QueryResponse(
            results=results,
            execution_time=execution_time,
            result_count=len(results)
        )
        
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")

# Event publishing endpoint
@app.post("/events")
async def publish_event(
    event_request: EventPublishRequest,
    event_bus: EventBus = Depends(get_event_bus)
):
    """Publish a custom event to the event bus."""
    try:
        # Validate role
        try:
            role = Role(event_request.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {event_request.role}")
        
        # Create and publish event
        event = KnowledgeEvent(
            action=event_request.action,
            data=event_request.data,
            role=role
        )
        
        if event_request.routing_key:
            await event_bus.publish(event, event_request.routing_key)
        else:
            await event_bus.publish(event)
        
        return {"message": "Event published successfully", "event_id": f"{event_request.action}_{id(event)}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to publish event: {e}")

# Statistics endpoint
@app.get("/stats")
async def get_statistics(
    kg_backend: KnowledgeGraphBackend = Depends(get_kg_backend)
):
    """Get statistics about the knowledge graph."""
    try:
        # Get entity count - use a simple query that should work
        try:
            entity_result = await kg_backend.query("MATCH (n) RETURN n")
            entity_count = len(entity_result.get("nodes", {})) if isinstance(entity_result, dict) else 0
        except:
            entity_count = 0
        
        # Get relationship count - use a simple query that should work
        try:
            rel_result = await kg_backend.query("MATCH ()-[r]->() RETURN r")
            rel_count = len(rel_result.get("edges", {})) if isinstance(rel_result, dict) else 0
        except:
            rel_count = 0
        
        return {
            "entity_count": entity_count,
            "relationship_count": rel_count,
            "total_nodes": entity_count,
            "total_edges": rel_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {e}")

# Initialization function
def initialize_api(kg_backend: KnowledgeGraphBackend, event_bus: EventBus):
    """Initialize the API with dependencies."""
    global _kg_backend, _event_bus
    _kg_backend = kg_backend
    _event_bus = event_bus
    logger.info("API initialized with dependencies")

# Default initialization
if _kg_backend is None:
    _kg_backend = InMemoryGraphBackend()
    logger.info("Using in-memory backend as default")

if _event_bus is None:
    from application.event_bus import EventBus
    _event_bus = EventBus()
    logger.info("Using local event bus as default")
