"""Main FastAPI application entry point."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import logging
from typing import Dict, Set, List, Any, Optional
import tempfile
import os

from pydantic import BaseModel, Field
from typing import Optional as OptionalType
from enum import Enum as PyEnum

from .kg_router import router as kg_router
from .document_router import router as document_router
from .dependencies import (
    get_chat_service,
    get_patient_memory,
    get_kg_backend,
    get_event_bus,
    initialize_layer_services,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Medical Knowledge Graph API",
    description="API for accessing and querying the Layered Knowledge Graph with Patient Memory",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(kg_router)
app.include_router(document_router)


# ========================================
# Startup Events
# ========================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("🚀 Starting Medical Knowledge Graph API...")

    # Initialize layer transition services (automatic promotion pipeline)
    try:
        await initialize_layer_services()
        logger.info("✅ Layer services initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize layer services: {e}")
        # Don't fail startup - allow API to run without auto-promotion


# ========================================
# WebSocket Connection Manager
# ========================================

class ConnectionManager:
    """Manage active WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket, client_id: str):
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def send_personal_message(self, message: dict, client_id: str):
        """Send message to specific client."""
        if client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message to {client_id}: {e}")


manager = ConnectionManager()


# ========================================
# WebSocket Endpoints
# ========================================

@app.websocket("/ws/chat/{patient_id}/{session_id}")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    patient_id: str,
    session_id: str
):
    """Real-time patient chat with streaming responses."""
    client_id = f"{patient_id}:{session_id}"
    logger.info(f"WebSocket connection attempt for {client_id}")

    # Accept connection first, then initialize dependencies
    await manager.connect(websocket, client_id)

    # Initialize dependencies after connection is established
    try:
        logger.info(f"Initializing dependencies for {client_id}")
        chat_service = await get_chat_service()
        patient_memory = await get_patient_memory()
        logger.info(f"Dependencies initialized for {client_id}")

        # Ensure patient exists in the system (creates if not found)
        await patient_memory.get_or_create_patient(patient_id)
        logger.info(f"Patient verified/created: {patient_id}")
    except Exception as e:
        logger.error(f"Failed to initialize dependencies for {client_id}: {e}", exc_info=True)
        await websocket.send_json({"type": "error", "message": f"Service initialization failed: {str(e)}"})
        await manager.disconnect(websocket, client_id)
        return

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_text = data.get("message")

            if not message_text:
                continue

            # Send "thinking" status
            await manager.send_personal_message(
                {"type": "status", "status": "thinking"},
                client_id
            )

            try:
                # Query chat service
                response = await chat_service.query(
                    question=message_text,
                    patient_id=patient_id,
                    session_id=session_id
                )

                # Send response back
                await manager.send_personal_message(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": response.answer,
                        "confidence": response.confidence,
                        "sources": [{"type": s.get("type", "KnowledgeGraph"), "name": s.get("name", "")} for s in response.sources],
                        "reasoning_trail": response.reasoning_trail,
                        "related_concepts": response.related_concepts,
                        "query_time": response.query_time_seconds
                    },
                    client_id
                )
            except Exception as e:
                logger.error(f"Error processing chat message: {e}", exc_info=True)
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": "Sorry, I encountered an error processing your message."
                    },
                    client_id
                )

    except WebSocketDisconnect:
        await manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}", exc_info=True)
        await manager.disconnect(websocket, client_id)


# ========================================
# REST API Endpoints
# ========================================

@app.get("/api/patients/{patient_id}/context")
async def get_patient_context(
    patient_id: str,
    patient_memory = Depends(get_patient_memory)
):
    """Get patient context for chat sidebar."""
    try:
        context = await patient_memory.get_patient_context(patient_id)
        return {
            "patient_id": context.patient_id,
            "diagnoses": context.diagnoses,
            "medications": context.medications,
            "allergies": context.allergies,
            "recent_symptoms": context.recent_symptoms,
            "conversation_summary": context.conversation_summary,
            "last_updated": context.last_updated.isoformat() if hasattr(context.last_updated, 'isoformat') else str(context.last_updated)
        }
    except Exception as e:
        logger.error(f"Error fetching patient context: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/data")
async def get_graph_data(
    limit: int = 100,
    layer: str = None,
    kg_backend = Depends(get_kg_backend)
):
    """Get knowledge graph data for visualization."""
    try:
        # Normalize layer to lowercase for consistent matching
        if layer:
            layer = layer.lower()

        # Build Cypher query based on filters
        if layer:
            query = f"""
            MATCH (n)
            WHERE toLower(n.layer) = $layer
            WITH n LIMIT $limit
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN
                collect(DISTINCT {{
                    id: elementId(n),
                    label: coalesce(n.name, elementId(n)),
                    type: head(labels(n)),
                    layer: n.layer,
                    properties: properties(n)
                }}) as nodes,
                collect(DISTINCT {{
                    id: elementId(r),
                    source: elementId(n),
                    target: elementId(m),
                    label: type(r),
                    type: type(r)
                }}) as edges
            """
            params = {"layer": layer, "limit": limit}
        else:
            query = f"""
            MATCH (n)
            WITH n LIMIT $limit
            OPTIONAL MATCH (n)-[r]->(m)
            WHERE m IS NOT NULL
            RETURN
                collect(DISTINCT {{
                    id: elementId(n),
                    label: coalesce(n.name, elementId(n)),
                    type: head(labels(n)),
                    layer: coalesce(n.layer, 'perception'),
                    properties: properties(n)
                }}) + collect(DISTINCT {{
                    id: elementId(m),
                    label: coalesce(m.name, elementId(m)),
                    type: head(labels(m)),
                    layer: coalesce(m.layer, 'perception'),
                    properties: properties(m)
                }}) as nodes,
                collect(DISTINCT {{
                    id: elementId(r),
                    source: elementId(n),
                    target: elementId(m),
                    label: type(r),
                    type: type(r)
                }}) as edges
            """
            params = {"limit": limit}

        result = await kg_backend.query_raw(query, params)

        if result and len(result) > 0:
            record = result[0]
            nodes = record.get("nodes", [])
            edges = record.get("edges", [])

            # Filter out None values
            nodes = [n for n in nodes if n is not None]
            edges = [e for e in edges if e is not None and e.get("source") and e.get("target")]

            return {
                "nodes": nodes,
                "edges": edges
            }

        return {"nodes": [], "edges": []}

    except Exception as e:
        logger.error(f"Error fetching graph data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/node/{node_id}")
async def get_node_details(
    node_id: str,
    kg_backend = Depends(get_kg_backend)
):
    """Get detailed information about a specific node."""
    try:
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        OPTIONAL MATCH (n)-[r_out]->(target)
        OPTIONAL MATCH (source)-[r_in]->(n)
        RETURN
            n,
            collect(DISTINCT {
                type: type(r_out),
                target: coalesce(target.name, elementId(target)),
                targetId: elementId(target)
            }) as outgoing,
            collect(DISTINCT {
                type: type(r_in),
                source: coalesce(source.name, elementId(source)),
                sourceId: elementId(source)
            }) as incoming
        """

        result = await kg_backend.query_raw(query, {"node_id": node_id})

        if result and len(result) > 0:
            record = result[0]
            node = record.get("n", {})

            return {
                "id": node_id,
                "label": node.get("name") or node.get("label") or node_id,
                "type": node.get("labels", ["Unknown"])[0] if node.get("labels") else "Unknown",
                "properties": node,
                "outgoing": [r for r in record.get("outgoing", []) if r and r.get("type")],
                "incoming": [r for r in record.get("incoming", []) if r and r.get("type")]
            }

        raise HTTPException(status_code=404, detail="Node not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching node details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/metrics")
async def get_system_metrics(kg_backend = Depends(get_kg_backend)):
    """Get system-wide metrics for admin dashboard."""
    try:
        # Get Neo4j stats
        stats_query = """
        MATCH (n)
        WITH count(n) as node_count
        MATCH ()-[r]->()
        WITH node_count, count(r) as rel_count
        RETURN node_count, rel_count
        """
        stats_result = await kg_backend.query_raw(stats_query, {})

        node_count = 0
        rel_count = 0
        if stats_result and len(stats_result) > 0:
            node_count = stats_result[0].get("node_count", 0)
            rel_count = stats_result[0].get("rel_count", 0)

        # Get patient count
        patient_query = "MATCH (p:Patient) RETURN count(p) as patient_count"
        patient_result = await kg_backend.query_raw(patient_query, {})
        patient_count = 0
        if patient_result and len(patient_result) > 0:
            patient_count = patient_result[0].get("patient_count", 0)

        # Get active session count from connection manager
        active_sessions = len(manager.active_connections)

        return {
            "total_queries": 0,  # TODO: Implement query counter
            "avg_response_time": 1.5,  # TODO: Implement response time tracking
            "active_sessions": active_sessions,
            "total_patients": patient_count,
            "neo4j_nodes": node_count,
            "neo4j_relationships": rel_count,
            "redis_memory_usage": "N/A"  # TODO: Implement Redis stats
        }
    except Exception as e:
        logger.error(f"Error fetching system metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/agents")
async def get_agent_status():
    """Get status of all agents for admin dashboard."""
    # TODO: Implement actual agent health checking
    # For now, return mock data
    return [
        {
            "id": "data_architect",
            "name": "Data Architect",
            "status": "running",
            "port": 8001,
            "uptime": 86400,
            "tasks_completed": 123
        },
        {
            "id": "data_engineer",
            "name": "Data Engineer",
            "status": "running",
            "port": 8002,
            "uptime": 86400,
            "tasks_completed": 89
        },
        {
            "id": "knowledge_manager",
            "name": "Knowledge Manager",
            "status": "running",
            "port": 8003,
            "uptime": 86400,
            "tasks_completed": 234
        },
        {
            "id": "medical_assistant",
            "name": "Medical Assistant",
            "status": "running",
            "port": 8004,
            "uptime": 86400,
            "tasks_completed": 456
        }
    ]


@app.get("/api/admin/promotion-scanner")
async def get_promotion_scanner_status():
    """Get promotion scanner status and statistics."""
    try:
        from .dependencies import get_promotion_scanner
        scanner = await get_promotion_scanner()
        return {
            "status": "running" if scanner._running else "stopped",
            "statistics": scanner.get_statistics()
        }
    except Exception as e:
        logger.error(f"Error getting scanner status: {e}")
        return {
            "status": "not_initialized",
            "error": str(e),
            "hint": "Set ENABLE_PROMOTION_SCANNER=true in .env and restart"
        }


@app.post("/api/admin/promotion-scanner/scan")
async def trigger_promotion_scan():
    """Manually trigger a promotion scan."""
    try:
        from .dependencies import get_promotion_scanner
        scanner = await get_promotion_scanner()
        results = await scanner.run_once()
        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        logger.error(f"Error running promotion scan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/layer-stats")
async def get_layer_statistics(kg_backend = Depends(get_kg_backend)):
    """Get entity counts per layer for the 4-layer architecture."""
    try:
        query = """
        MATCH (n)
        WHERE n.layer IS NOT NULL
        RETURN n.layer as layer, count(n) as count
        ORDER BY
            CASE n.layer
                WHEN 'PERCEPTION' THEN 1
                WHEN 'SEMANTIC' THEN 2
                WHEN 'REASONING' THEN 3
                WHEN 'APPLICATION' THEN 4
                ELSE 5
            END
        """
        result = await kg_backend.query_raw(query, {})

        layer_counts = {
            "PERCEPTION": 0,
            "SEMANTIC": 0,
            "REASONING": 0,
            "APPLICATION": 0,
        }

        for record in result or []:
            layer = record.get("layer")
            count = record.get("count", 0)
            if layer in layer_counts:
                layer_counts[layer] = count

        # Also count nodes without layer property
        unassigned_query = """
        MATCH (n)
        WHERE n.layer IS NULL
        RETURN count(n) as count
        """
        unassigned_result = await kg_backend.query_raw(unassigned_query, {})
        unassigned_count = 0
        if unassigned_result:
            unassigned_count = unassigned_result[0].get("count", 0)

        return {
            "layers": layer_counts,
            "total": sum(layer_counts.values()),
            "unassigned": unassigned_count,
            "dikw_mapping": {
                "DATA": layer_counts["PERCEPTION"],
                "INFORMATION": layer_counts["SEMANTIC"],
                "KNOWLEDGE": layer_counts["REASONING"],
                "WISDOM": layer_counts["APPLICATION"]
            }
        }
    except Exception as e:
        logger.error(f"Error getting layer stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/patients")
async def list_patients(kg_backend = Depends(get_kg_backend)):
    """List all patients for admin dashboard."""
    try:
        query = """
        MATCH (p:Patient)
        OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(dx)
        OPTIONAL MATCH (p)-[:CURRENT_MEDICATION]->(med)
        OPTIONAL MATCH (p)-[:HAS_SESSION]->(session)
        RETURN
            p.id as patient_id,
            p.created_at as created_at,
            count(DISTINCT dx) as diagnoses_count,
            count(DISTINCT med) as medications_count,
            count(DISTINCT session) as sessions_count,
            p.consent_given as consent_given
        """
        result = await kg_backend.query_raw(query, {})

        patients = []
        for record in result or []:
            patients.append({
                "patient_id": record.get("patient_id", "unknown"),
                "created_at": record.get("created_at", "unknown"),
                "diagnoses_count": record.get("diagnoses_count", 0),
                "medications_count": record.get("medications_count", 0),
                "sessions_count": record.get("sessions_count", 0),
                "consent_given": record.get("consent_given", True)
            })

        return patients
    except Exception as e:
        logger.error(f"Error fetching patients: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/patients/{patient_id}")
async def delete_patient(
    patient_id: str,
    patient_memory = Depends(get_patient_memory)
):
    """Delete all patient data (GDPR right to be forgotten)."""
    try:
        success = await patient_memory.delete_patient_data(patient_id)
        if success:
            return {"message": "Patient data deleted successfully"}
        raise HTTPException(status_code=500, detail="Failed to delete patient data")
    except Exception as e:
        logger.error(f"Error deleting patient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/admin/monitor")
async def admin_monitor_websocket(websocket: WebSocket):
    """Real-time system monitoring for admin dashboard."""
    await manager.connect(websocket, "admin_monitor")

    try:
        while True:
            # Ping/pong to keep connection alive
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "admin_monitor")
    except Exception as e:
        logger.error(f"Admin monitor WebSocket error: {e}", exc_info=True)
        await manager.disconnect(websocket, "admin_monitor")


@app.post("/api/dda/upload")
async def upload_dda(
    file: UploadFile = File(...),
    kg_backend = Depends(get_kg_backend),
    use_agent: bool = True
):
    """
    Upload and process DDA specification file.

    When use_agent=True (default), the Data Architect Agent processes the DDA,
    which publishes events for downstream processing and layer promotion.
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.md', '.markdown')):
            raise HTTPException(status_code=400, detail="Only markdown files (.md, .markdown) are allowed")

        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp:
            tmp.write(content_str)
            tmp_path = tmp.name

        try:
            # Try to use Data Architect Agent if available and requested
            if use_agent:
                try:
                    from application.api.dependencies import get_data_architect_agent
                    agent = await get_data_architect_agent()
                    result = await agent.process_dda(tmp_path)

                    if result["success"]:
                        return {
                            "success": True,
                            "message": "DDA processed by Data Architect Agent in PERCEPTION layer",
                            "domain": result["domain"],
                            "entities_created": len(result["entities_created"]),
                            "relationships_created": len(result["relationships_created"]),
                            "events_published": result["events_published"],
                            "layer": "PERCEPTION",
                            "status": "pending_validation",
                            "agent": "data_architect",
                            "next_step": "Entities will be promoted to SEMANTIC layer after Knowledge Manager validation"
                        }
                    else:
                        logger.warning(f"Agent processing failed, falling back to direct: {result['errors']}")
                        # Fall through to direct processing
                except Exception as agent_error:
                    logger.warning(f"Agent unavailable, falling back to direct processing: {agent_error}")
                    # Fall through to direct processing

            # Direct processing (fallback or when use_agent=False)
            from infrastructure.parsers.markdown_parser import MarkdownDDAParser
            parser = MarkdownDDAParser()

            result = await parser.parse(tmp_path)

            # Store parsed DDA in Neo4j
            # All DDA entities start in PERCEPTION layer with pending_validation status
            # They will be promoted to SEMANTIC after Knowledge Manager validation

            # 1. Create or merge Catalog node from domain
            catalog_query = """
            MERGE (c:Catalog {name: $domain})
            SET c.data_owner = $data_owner,
                c.business_context = $business_context,
                c.layer = 'PERCEPTION',
                c.status = 'pending_validation',
                c.source_type = 'dda',
                c.updated_at = datetime(),
                c.created_at = COALESCE(c.created_at, datetime())
            RETURN elementId(c) as catalog_id
            """
            catalog_result = await kg_backend.query_raw(catalog_query, {
                "domain": result.domain,
                "data_owner": result.data_owner,
                "business_context": result.business_context
            })

            # 2. Create default Schema under Catalog
            schema_query = """
            MATCH (c:Catalog {name: $domain})
            MERGE (s:Schema {name: $schema_name})
            MERGE (c)-[:CONTAINS_SCHEMA]->(s)
            SET s.layer = 'PERCEPTION',
                s.status = 'pending_validation',
                s.source_type = 'dda',
                s.updated_at = datetime(),
                s.created_at = COALESCE(s.created_at, datetime())
            RETURN elementId(s) as schema_id
            """
            schema_name = f"{result.domain}_schema"
            await kg_backend.query_raw(schema_query, {
                "domain": result.domain,
                "schema_name": schema_name
            })

            # 3. Create Table nodes from entities with their columns
            tables_created = 0
            columns_created = 0
            for entity in result.entities:
                # Create Table node
                table_query = """
                MATCH (s:Schema {name: $schema_name})
                MERGE (t:Table {name: $table_name})
                MERGE (s)-[:CONTAINS_TABLE]->(t)
                SET t.description = $description,
                    t.primary_key = $primary_key,
                    t.business_rules = $business_rules,
                    t.layer = 'PERCEPTION',
                    t.status = 'pending_validation',
                    t.source_type = 'dda',
                    t.confidence = 0.7,
                    t.updated_at = datetime(),
                    t.created_at = COALESCE(t.created_at, datetime())
                RETURN elementId(t) as table_id
                """
                await kg_backend.query_raw(table_query, {
                    "schema_name": schema_name,
                    "table_name": entity.name,
                    "description": entity.description,
                    "primary_key": entity.primary_key,
                    "business_rules": entity.business_rules
                })
                tables_created += 1

                # Create Column nodes from attributes
                for attr in entity.attributes:
                    # Parse attribute (format might be "column_name (type)" or just "column_name")
                    attr_name = attr.split('(')[0].strip() if '(' in attr else attr.strip()
                    attr_type = "VARCHAR"  # Default type
                    if '(' in attr and ')' in attr:
                        type_part = attr.split('(')[1].split(')')[0].strip()
                        if type_part not in ['Primary Key', 'Foreign Key']:
                            attr_type = type_part

                    is_primary = 'Primary Key' in attr
                    is_foreign = 'Foreign Key' in attr

                    column_query = """
                    MATCH (t:Table {name: $table_name})
                    MERGE (col:Column {name: $column_name, table: $table_name})
                    MERGE (t)-[:HAS_COLUMN]->(col)
                    SET col.data_type = $data_type,
                        col.is_primary_key = $is_primary,
                        col.is_foreign_key = $is_foreign,
                        col.layer = 'PERCEPTION',
                        col.status = 'pending_validation',
                        col.source_type = 'dda',
                        col.confidence = 0.7,
                        col.updated_at = datetime(),
                        col.created_at = COALESCE(col.created_at, datetime())
                    """
                    await kg_backend.query_raw(column_query, {
                        "table_name": entity.name,
                        "column_name": attr_name,
                        "data_type": attr_type,
                        "is_primary": is_primary,
                        "is_foreign": is_foreign
                    })
                    columns_created += 1

            # 4. Create relationships between tables
            relationships_created = 0
            for rel in result.relationships:
                rel_query = """
                MATCH (source:Table {name: $source_name})
                MATCH (target:Table {name: $target_name})
                MERGE (source)-[r:RELATES_TO {type: $rel_type}]->(target)
                SET r.description = $description,
                    r.cardinality = $rel_type,
                    r.layer = 'PERCEPTION',
                    r.status = 'pending_validation',
                    r.source_type = 'dda',
                    r.confidence = 0.7,
                    r.updated_at = datetime(),
                    r.created_at = COALESCE(r.created_at, datetime())
                """
                await kg_backend.query_raw(rel_query, {
                    "source_name": rel.source_entity,
                    "target_name": rel.target_entity,
                    "rel_type": rel.relationship_type,
                    "description": rel.description
                })
                relationships_created += 1

            # Collect entity names for response
            entity_names = [entity.name for entity in result.entities]
            relationship_info = [
                f"{rel.source_entity} -> {rel.target_entity} ({rel.relationship_type})"
                for rel in result.relationships
            ]

            return {
                "success": True,
                "message": "DDA processed and stored in PERCEPTION layer (pending validation)",
                "domain": result.domain,
                "data_owner": result.data_owner,
                "catalog_created": result.domain,
                "schema_created": schema_name,
                "tables_created": tables_created,
                "columns_created": columns_created,
                "relationships_created": relationships_created,
                "entities": entity_names,
                "relationships": relationship_info,
                "layer": "PERCEPTION",
                "status": "pending_validation",
                "next_step": "Entities will be promoted to SEMANTIC layer after Knowledge Manager validation"
            }

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Error processing DDA: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process DDA: {str(e)}")


@app.get("/api/metadata/catalogs")
async def get_catalogs(kg_backend = Depends(get_kg_backend)):
    """Get all data catalogs."""
    try:
        query = "MATCH (c:Catalog) RETURN elementId(c) as id, c.name as name ORDER BY c.name"
        result = await kg_backend.query_raw(query, {})

        catalogs = []
        for record in result or []:
            catalogs.append({
                "id": record.get("id"),
                "name": record.get("name")
            })

        return catalogs
    except Exception as e:
        logger.error(f"Error fetching catalogs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metadata/catalogs/{catalog_id}/schemas")
async def get_schemas(catalog_id: str, kg_backend = Depends(get_kg_backend)):
    """Get all schemas in a catalog."""
    try:
        query = """
        MATCH (c:Catalog)-[:CONTAINS_SCHEMA]->(s:Schema)
        WHERE elementId(c) = $catalog_id
        RETURN elementId(s) as id, s.name as name
        ORDER BY s.name
        """
        result = await kg_backend.query_raw(query, {"catalog_id": catalog_id})

        schemas = []
        for record in result or []:
            schemas.append({
                "id": record.get("id"),
                "name": record.get("name")
            })

        return schemas
    except Exception as e:
        logger.error(f"Error fetching schemas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metadata/schemas/{schema_id}/tables")
async def get_tables(schema_id: str, kg_backend = Depends(get_kg_backend)):
    """Get all tables in a schema."""
    try:
        query = """
        MATCH (s:Schema)-[:CONTAINS_TABLE]->(t:Table)
        WHERE elementId(s) = $schema_id
        OPTIONAL MATCH (t)-[:HAS_COLUMN]->(col:Column)
        RETURN
            elementId(t) as id,
            t.name as name,
            coalesce(t.description, '') as description,
            coalesce(t.row_count, 0) as row_count,
            collect(CASE WHEN col IS NOT NULL THEN {
                id: elementId(col),
                name: col.name,
                data_type: coalesce(col.data_type, 'unknown'),
                nullable: coalesce(col.nullable, true),
                description: coalesce(col.description, '')
            } END) as columns
        ORDER BY t.name
        """
        result = await kg_backend.query_raw(query, {"schema_id": schema_id})

        tables = []
        for record in result or []:
            columns = [c for c in record.get("columns", []) if c and c.get("name")]
            tables.append({
                "id": record.get("id"),
                "name": record.get("name"),
                "description": record.get("description"),
                "row_count": record.get("row_count"),
                "columns": columns
            })

        return tables
    except Exception as e:
        logger.error(f"Error fetching tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metadata/catalog/all")
async def get_all_catalog_items(kg_backend = Depends(get_kg_backend)):
    """Get all catalog items for search/browse."""
    try:
        query = """
        // Get catalogs
        MATCH (catalog:Catalog)
        RETURN
            elementId(catalog) as id,
            catalog.name as name,
            'catalog' as type,
            coalesce(catalog.description, '') as description,
            null as data_type,
            [] as path

        UNION

        // Get schemas
        MATCH (catalog:Catalog)-[:CONTAINS_SCHEMA]->(schema:Schema)
        RETURN
            elementId(schema) as id,
            schema.name as name,
            'schema' as type,
            coalesce(schema.description, '') as description,
            null as data_type,
            [catalog.name] as path

        UNION

        // Get tables
        MATCH (catalog:Catalog)-[:CONTAINS_SCHEMA]->(schema:Schema)-[:CONTAINS_TABLE]->(table:Table)
        RETURN
            elementId(table) as id,
            table.name as name,
            'table' as type,
            coalesce(table.description, '') as description,
            null as data_type,
            [catalog.name, schema.name] as path

        UNION

        // Get columns
        MATCH (catalog:Catalog)-[:CONTAINS_SCHEMA]->(schema:Schema)-[:CONTAINS_TABLE]->(table:Table)-[:HAS_COLUMN]->(column:Column)
        RETURN
            elementId(column) as id,
            column.name as name,
            'column' as type,
            coalesce(column.description, '') as description,
            coalesce(column.data_type, 'unknown') as data_type,
            [catalog.name, schema.name, table.name] as path

        ORDER BY type, name
        """
        result = await kg_backend.query_raw(query, {})

        items = []
        for record in result or []:
            items.append({
                "id": record.get("id"),
                "name": record.get("name"),
                "type": record.get("type"),
                "description": record.get("description"),
                "data_type": record.get("data_type"),
                "path": record.get("path", [])
            })

        return items
    except Exception as e:
        logger.error(f"Error fetching catalog items: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint - serve frontend or API info."""
    # Check if frontend build exists
    frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {"message": "Medical Knowledge Graph API. Visit /docs for API documentation."}


# ========================================
# Feedback Collection Endpoints (RLHF)
# ========================================

# Response tracker for simple thumbs feedback
# Stores response metadata so thumbs up/down can look up entities
_response_tracker: Dict[str, Dict[str, Any]] = {}


def track_response(
    response_id: str,
    query_text: str,
    response_text: str,
    entities_involved: List[str],
    layers_traversed: List[str],
    patient_id: str = "anonymous",
    session_id: str = "default",
    confidence: float = 0.0,
) -> None:
    """
    Track a response for later feedback attribution.

    Call this when generating a response to enable simple thumbs feedback.
    """
    from datetime import datetime

    _response_tracker[response_id] = {
        "response_id": response_id,
        "query_text": query_text,
        "response_text": response_text,
        "entities_involved": entities_involved,
        "layers_traversed": layers_traversed,
        "patient_id": patient_id,
        "session_id": session_id,
        "confidence": confidence,
        "created_at": datetime.now().isoformat(),
    }

    # Keep only last 1000 responses to prevent memory bloat
    if len(_response_tracker) > 1000:
        oldest_keys = sorted(
            _response_tracker.keys(),
            key=lambda k: _response_tracker[k].get("created_at", "")
        )[:100]
        for key in oldest_keys:
            del _response_tracker[key]


def get_tracked_response(response_id: str) -> Optional[Dict[str, Any]]:
    """Get tracked response data for feedback submission."""
    return _response_tracker.get(response_id)


# Pydantic models for simple thumbs feedback
class ThumbsFeedbackRequest(BaseModel):
    """Simple thumbs up/down feedback request."""
    response_id: str = Field(..., description="ID of the response being rated")
    thumbs_up: bool = Field(..., description="True for thumbs up, False for thumbs down")
    correction_text: Optional[str] = Field(None, description="Optional correction if thumbs down")


# Pydantic models for feedback
class FeedbackTypeEnum(str, PyEnum):
    """Types of user feedback."""
    HELPFUL = "helpful"
    UNHELPFUL = "unhelpful"
    INCORRECT = "incorrect"
    PARTIALLY_CORRECT = "partially_correct"
    MISSING_INFO = "missing_info"


class FeedbackSeverityEnum(str, PyEnum):
    """Severity of feedback issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""
    response_id: str = Field(..., description="ID of the response being rated")
    patient_id: str = Field(..., description="Patient identifier")
    session_id: str = Field(..., description="Session identifier")
    query_text: str = Field(..., description="Original query text")
    response_text: str = Field(..., description="Response that was given")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5")
    feedback_type: FeedbackTypeEnum = Field(..., description="Type of feedback")
    severity: OptionalType[FeedbackSeverityEnum] = Field(None, description="Severity level")
    correction_text: OptionalType[str] = Field(None, description="User's correction")
    entities_involved: OptionalType[List[str]] = Field(default=[], description="Entity IDs involved")
    layers_traversed: OptionalType[List[str]] = Field(default=[], description="Layers traversed")


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    feedback_id: str
    message: str
    confidence_adjusted: bool = False


# Global feedback service instance
_feedback_service_instance = None


async def get_feedback_service():
    """Get or create feedback service instance."""
    global _feedback_service_instance
    if _feedback_service_instance is None:
        from application.services.feedback_tracer import FeedbackTracerService
        backend = await get_kg_backend()
        event_bus = await get_event_bus()
        _feedback_service_instance = FeedbackTracerService(
            backend=backend,
            event_bus=event_bus
        )
    return _feedback_service_instance


@app.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback for a response.

    This endpoint collects feedback for RLHF training data:
    - Rating (1-5)
    - Feedback type (helpful, incorrect, etc.)
    - Optional user correction
    - Entity and layer attribution

    Feedback is propagated to entity confidence scores.
    """
    try:
        from application.services.feedback_tracer import FeedbackType, FeedbackSeverity

        feedback_service = await get_feedback_service()

        # Convert enums
        feedback_type = FeedbackType(request.feedback_type.value)
        severity = FeedbackSeverity(request.severity.value) if request.severity else None

        feedback = await feedback_service.submit_feedback(
            response_id=request.response_id,
            patient_id=request.patient_id,
            session_id=request.session_id,
            query_text=request.query_text,
            response_text=request.response_text,
            rating=request.rating,
            feedback_type=feedback_type,
            severity=severity,
            correction_text=request.correction_text,
            entities_involved=request.entities_involved or [],
            layers_traversed=request.layers_traversed or [],
        )

        return FeedbackResponse(
            feedback_id=feedback.feedback_id,
            message="Feedback submitted successfully",
            confidence_adjusted=len(request.entities_involved or []) > 0
        )

    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feedback/thumbs", response_model=FeedbackResponse)
async def submit_thumbs_feedback(request: ThumbsFeedbackRequest):
    """
    Submit simple thumbs up/down feedback.

    This is the simplified feedback endpoint for low-confidence responses.
    It uses the tracked response metadata to attribute feedback to entities.

    - Thumbs up (rating 5): Boosts entity confidence
    - Thumbs down (rating 1): Decreases entity confidence, may trigger demotion
    """
    try:
        from application.services.feedback_tracer import FeedbackType

        # Look up tracked response
        response_data = get_tracked_response(request.response_id)

        if not response_data:
            raise HTTPException(
                status_code=404,
                detail=f"Response {request.response_id} not found. "
                "Ensure the response was tracked during generation."
            )

        feedback_service = await get_feedback_service()

        # Map thumbs to rating and feedback type
        rating = 5 if request.thumbs_up else 1
        feedback_type = FeedbackType.HELPFUL if request.thumbs_up else FeedbackType.UNHELPFUL

        feedback = await feedback_service.submit_feedback(
            response_id=request.response_id,
            patient_id=response_data.get("patient_id", "anonymous"),
            session_id=response_data.get("session_id", "default"),
            query_text=response_data.get("query_text", ""),
            response_text=response_data.get("response_text", ""),
            rating=rating,
            feedback_type=feedback_type,
            correction_text=request.correction_text,
            entities_involved=response_data.get("entities_involved", []),
            layers_traversed=response_data.get("layers_traversed", []),
            metadata={
                "original_confidence": response_data.get("confidence", 0),
                "feedback_method": "thumbs",
            }
        )

        # Check for demotion on negative feedback
        entities_demoted = []
        if not request.thumbs_up and response_data.get("entities_involved"):
            entities_demoted = await feedback_service.check_demotion(
                response_data.get("entities_involved", [])
            )

        return FeedbackResponse(
            feedback_id=feedback.feedback_id,
            message=f"{'Thumbs up' if request.thumbs_up else 'Thumbs down'} recorded. "
                   f"{len(entities_demoted)} entities demoted." if entities_demoted else "",
            confidence_adjusted=len(response_data.get("entities_involved", [])) > 0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting thumbs feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/stats")
async def get_feedback_statistics():
    """
    Get aggregated feedback statistics.

    Returns:
    - Total feedbacks
    - Average rating
    - Rating distribution
    - Feedback type distribution
    - Layer performance metrics
    """
    try:
        feedback_service = await get_feedback_service()
        stats = await feedback_service.get_feedback_statistics()

        return {
            "total_feedbacks": stats.total_feedbacks,
            "average_rating": stats.average_rating,
            "rating_distribution": stats.rating_distribution,
            "feedback_type_distribution": stats.feedback_type_distribution,
            "layer_performance": stats.layer_performance,
            "recent_trends": stats.recent_trends,
        }

    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/preference-pairs")
async def get_preference_pairs(
    min_rating_gap: int = 2,
    limit: int = 100
):
    """
    Get preference pairs for RLHF training.

    Preference pairs are created when users provide corrections.
    The original response is 'rejected' and the correction is 'chosen'.

    Args:
        min_rating_gap: Minimum rating gap between chosen/rejected (default 2)
        limit: Maximum pairs to return (default 100)

    Returns:
        List of preference pairs in DPO format
    """
    try:
        feedback_service = await get_feedback_service()
        pairs = await feedback_service.get_preference_pairs(
            min_rating_gap=min_rating_gap,
            limit=limit
        )

        return {
            "pairs": pairs,
            "total_count": len(pairs),
            "format": "dpo_preference_pairs"
        }

    except Exception as e:
        logger.error(f"Error getting preference pairs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/corrections")
async def get_correction_examples(
    feedback_type: OptionalType[str] = None,
    limit: int = 100
):
    """
    Get user correction examples for supervised fine-tuning.

    Args:
        feedback_type: Optional filter by feedback type
        limit: Maximum examples to return

    Returns:
        List of correction examples
    """
    try:
        from application.services.feedback_tracer import FeedbackType

        feedback_service = await get_feedback_service()

        ft = FeedbackType(feedback_type) if feedback_type else None
        corrections = await feedback_service.get_correction_examples(
            feedback_type=ft,
            limit=limit
        )

        return {
            "corrections": corrections,
            "total_count": len(corrections),
            "format": "supervised_fine_tuning"
        }

    except Exception as e:
        logger.error(f"Error getting corrections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ExportFormatEnum(str, PyEnum):
    """Supported export formats for RLHF training data."""
    DPO = "dpo"
    SFT = "sft"
    ALPACA = "alpaca"
    SHAREGPT = "sharegpt"
    OPENAI = "openai"
    RAW = "raw"


@app.get("/api/feedback/export")
async def export_training_data(
    format: ExportFormatEnum = ExportFormatEnum.RAW,
    layer: Optional[str] = None,
    min_rating_gap: float = 2.0,
    min_rating_for_sft: float = 4.0,
    include_metadata: bool = False,
    split_dataset: bool = False,
):
    """
    Export training data for RLHF in various formats.

    Args:
        format: Output format (dpo, sft, alpaca, sharegpt, openai, raw)
        layer: Filter by knowledge graph layer (PERCEPTION, SEMANTIC, REASONING, APPLICATION)
        min_rating_gap: Minimum rating gap for preference pairs (default 2.0)
        min_rating_for_sft: Minimum rating for SFT examples (default 4.0)
        include_metadata: Include source metadata in output
        split_dataset: Split into train/validation/test sets

    Returns:
        Formatted training data based on the selected format:
        - dpo: Direct Preference Optimization format
        - sft: Supervised Fine-Tuning format
        - alpaca: Alpaca instruction tuning format
        - sharegpt: ShareGPT conversation format
        - openai: OpenAI fine-tuning format
        - raw: Raw extracted data with both preference pairs and SFT examples
    """
    try:
        # Validate layer if provided
        valid_layers = ["PERCEPTION", "SEMANTIC", "REASONING", "APPLICATION"]
        if layer and layer.upper() not in valid_layers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid layer. Must be one of: {', '.join(valid_layers)}"
            )

        # Use raw format for backward compatibility
        if format == ExportFormatEnum.RAW:
            feedback_service = await get_feedback_service()
            export_data = await feedback_service.export_training_data()
            return export_data

        # Use RLHFDataExtractor for formatted output
        from application.services.rlhf_data_extractor import RLHFDataExtractor
        from application.formatters.training_data_formatter import (
            TrainingDataFormatter,
            FormatterConfig,
            OutputFormat,
        )

        backend = await get_kg_backend()
        extractor = RLHFDataExtractor(
            backend=backend,
            min_rating_gap=min_rating_gap,
            min_rating_for_sft=min_rating_for_sft,
        )

        # Extract data
        result = await extractor.extract_all(
            layer_filter=layer.upper() if layer else None,
        )

        # Configure formatter
        config = FormatterConfig(
            include_metadata=include_metadata,
        )
        formatter = TrainingDataFormatter(config)

        # Format based on requested type
        output = {}

        if format == ExportFormatEnum.DPO:
            formatted_pairs = formatter.format_dpo([
                {
                    "prompt": p.prompt,
                    "chosen": p.chosen,
                    "rejected": p.rejected,
                    "rating_gap": p.rating_gap,
                    "source": p.source,
                    "layers_involved": p.layers_involved,
                }
                for p in result.preference_pairs
            ])
            output = {
                "format": "dpo",
                "data": formatted_pairs,
                "count": len(formatted_pairs),
            }

        elif format == ExportFormatEnum.SFT:
            formatted_sft = formatter.format_sft([
                {
                    "instruction": e.instruction,
                    "input": e.input,
                    "output": e.output,
                    "rating": e.rating,
                    "source": e.source,
                }
                for e in result.sft_examples
            ])
            output = {
                "format": "sft",
                "data": formatted_sft,
                "count": len(formatted_sft),
            }

        elif format == ExportFormatEnum.ALPACA:
            formatted_alpaca = formatter.format_alpaca([
                {
                    "instruction": e.instruction,
                    "input": e.input,
                    "output": e.output,
                    "rating": e.rating,
                    "source": e.source,
                }
                for e in result.sft_examples
            ])
            output = {
                "format": "alpaca",
                "data": formatted_alpaca,
                "count": len(formatted_alpaca),
            }

        elif format == ExportFormatEnum.SHAREGPT:
            formatted_sharegpt = formatter.format_sharegpt([
                {
                    "instruction": e.instruction,
                    "input": e.input,
                    "output": e.output,
                    "rating": e.rating,
                    "source": e.source,
                }
                for e in result.sft_examples
            ])
            output = {
                "format": "sharegpt",
                "data": formatted_sharegpt,
                "count": len(formatted_sharegpt),
            }

        elif format == ExportFormatEnum.OPENAI:
            # OpenAI format for both SFT and DPO
            formatted_sft = formatter.format_openai([
                {
                    "instruction": e.instruction,
                    "input": e.input,
                    "output": e.output,
                }
                for e in result.sft_examples
            ])
            formatted_dpo = formatter.format_dpo_openai([
                {
                    "prompt": p.prompt,
                    "chosen": p.chosen,
                    "rejected": p.rejected,
                }
                for p in result.preference_pairs
            ])
            output = {
                "format": "openai",
                "sft_data": formatted_sft,
                "dpo_data": formatted_dpo,
                "sft_count": len(formatted_sft),
                "dpo_count": len(formatted_dpo),
            }

        # Split dataset if requested
        if split_dataset and output.get("data"):
            splits = formatter.split_dataset(output["data"])
            output["splits"] = {
                "train": len(splits["train"]),
                "validation": len(splits["validation"]),
                "test": len(splits["test"]),
            }
            output["data"] = splits

        # Add extraction metadata
        output["extraction_metadata"] = {
            "total_preference_pairs": len(result.preference_pairs),
            "total_sft_examples": len(result.sft_examples),
            "layer_filter": layer,
            "min_rating_gap": min_rating_gap,
            "min_rating_for_sft": min_rating_for_sft,
        }

        # Add layer analysis if available
        if result.layer_analysis:
            output["layer_analysis"] = {
                layer_name: {
                    "total_queries": la.total_queries,
                    "average_rating": la.average_rating,
                    "negative_rate": la.negative_rate,
                }
                for layer_name, la in result.layer_analysis.items()
            }

        return output

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting training data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Chat Session Management Endpoints
# ========================================

# Global chat history service instance
_chat_history_service_instance = None


async def get_chat_history_service():
    """Get or create chat history service instance."""
    global _chat_history_service_instance

    if _chat_history_service_instance is None:
        from application.services.chat_history_service import ChatHistoryService
        from application.services.conversational_intent_service import ConversationalIntentService

        # Get dependencies
        patient_memory = await get_patient_memory()
        intent_service = ConversationalIntentService(
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        _chat_history_service_instance = ChatHistoryService(
            patient_memory_service=patient_memory,
            intent_service=intent_service,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        logger.info("ChatHistoryService initialized")

    return _chat_history_service_instance


class SessionListRequest(BaseModel):
    """Request model for listing sessions."""
    patient_id: str
    limit: int = 20
    offset: int = 0
    status: Optional[str] = None  # "active", "ended", "archived"


class CreateSessionRequest(BaseModel):
    """Request model for creating a session."""
    patient_id: str
    title: Optional[str] = None
    device: str = "web"


@app.get("/api/chat/sessions")
async def list_sessions(
    patient_id: str,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    List all chat sessions for a patient.

    Returns sessions grouped by time periods (today, yesterday, this week, etc.)
    with metadata including message count, last activity, and topics.
    """
    try:
        history_service = await get_chat_history_service()

        session_list = await history_service.list_sessions(
            patient_id=patient_id,
            limit=limit,
            offset=offset,
            status=status
        )

        return session_list.to_dict()

    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions/latest")
async def get_latest_session(patient_id: str):
    """
    Get most recent active session for a patient.

    Used for auto-resume functionality.
    """
    try:
        history_service = await get_chat_history_service()

        session = await history_service.get_latest_session(patient_id)

        if not session:
            raise HTTPException(status_code=404, detail="No active sessions found")

        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions/{session_id}")
async def get_session_metadata(session_id: str):
    """Get metadata for a specific session."""
    try:
        history_service = await get_chat_history_service()

        session = await history_service.get_session_metadata(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 100,
    offset: int = 0
):
    """
    Get messages for a session with pagination.

    Returns messages ordered by timestamp (oldest first for display).
    """
    try:
        history_service = await get_chat_history_service()

        messages = await history_service.get_session_messages(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

        return {
            "session_id": session_id,
            "messages": [msg.to_dict() for msg in messages],
            "count": len(messages),
            "has_more": len(messages) == limit
        }

    except Exception as e:
        logger.error(f"Error getting session messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/sessions/start")
async def start_session(request: CreateSessionRequest):
    """
    Create a new chat session.

    Title will be auto-generated after 2-3 messages if not provided.
    """
    try:
        history_service = await get_chat_history_service()

        session_id = await history_service.create_session(
            patient_id=request.patient_id,
            title=request.title,
            device=request.device
        )

        return {
            "session_id": session_id,
            "patient_id": request.patient_id,
            "title": request.title or "New Conversation",
            "status": "active"
        }

    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/chat/sessions/{session_id}/end")
async def end_session(session_id: str):
    """Mark a session as ended."""
    try:
        history_service = await get_chat_history_service()

        success = await history_service.end_session(session_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to end session")

        return {"session_id": session_id, "status": "ended"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session and all messages (GDPR compliance).

    Permanently removes session data. Cannot be undone.
    """
    try:
        history_service = await get_chat_history_service()

        success = await history_service.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete session")

        return {"session_id": session_id, "status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions/{session_id}/summary")
async def get_session_summary(session_id: str):
    """
    Get AI-generated summary of a session.

    Includes key topics, main symptoms, recommendations, and sentiment.
    """
    try:
        history_service = await get_chat_history_service()

        summary = await history_service.get_session_summary(session_id)

        if not summary:
            raise HTTPException(status_code=404, detail="Could not generate summary")

        return summary.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating session summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/sessions/{session_id}/auto-title")
async def auto_generate_session_title(session_id: str):
    """
    Auto-generate session title from first 2-3 messages.

    Uses Phase 6 intent classification for fast, consistent titles.
    Called automatically after 3 messages in a session.
    """
    try:
        history_service = await get_chat_history_service()

        title = await history_service.auto_generate_title(session_id)

        if not title:
            raise HTTPException(status_code=404, detail="Could not generate title")

        return {
            "session_id": session_id,
            "title": title,
            "status": "generated"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-generating title: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions/search")
async def search_sessions(
    patient_id: str,
    query: str,
    limit: int = 20
):
    """
    Search sessions by content or title.

    Uses full-text search on message content.
    """
    try:
        history_service = await get_chat_history_service()

        sessions = await history_service.search_sessions(
            patient_id=patient_id,
            query=query,
            limit=limit
        )

        return {
            "query": query,
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions)
        }

    except Exception as e:
        logger.error(f"Error searching sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Layer Statistics Endpoint
# ========================================

@app.get("/api/graph/layer-stats")
async def get_layer_statistics(kg_backend = Depends(get_kg_backend)):
    """
    Get knowledge graph layer statistics.

    Returns counts and metrics for each layer:
    - PERCEPTION: Raw extracted data
    - SEMANTIC: Validated concepts
    - REASONING: Inferred knowledge
    - APPLICATION: Query patterns
    """
    try:
        query = """
        MATCH (n)
        WHERE n.layer IS NOT NULL
        RETURN n.layer as layer, count(n) as count
        ORDER BY layer
        """
        result = await kg_backend.query_raw(query, {})

        layer_counts = {
            "PERCEPTION": 0,
            "SEMANTIC": 0,
            "REASONING": 0,
            "APPLICATION": 0,
        }

        for record in result or []:
            layer = record.get("layer")
            if layer in layer_counts:
                layer_counts[layer] = record.get("count", 0)

        # Get total nodes without layer property
        unassigned_query = """
        MATCH (n) WHERE n.layer IS NULL
        RETURN count(n) as count
        """
        unassigned_result = await kg_backend.query_raw(unassigned_query, {})
        unassigned_count = 0
        if unassigned_result:
            unassigned_count = unassigned_result[0].get("count", 0)

        total = sum(layer_counts.values()) + unassigned_count

        return {
            "layers": layer_counts,
            "unassigned": unassigned_count,
            "total_nodes": total,
            "layer_percentages": {
                layer: (count / total * 100) if total > 0 else 0
                for layer, count in layer_counts.items()
            }
        }

    except Exception as e:
        logger.error(f"Error getting layer stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Promotion Management Endpoints
# ========================================

@app.get("/api/promotion/status")
async def get_promotion_status():
    """
    Get the status of the automatic promotion service.

    Returns statistics about promotions attempted, completed, and rejected,
    as well as the current configuration.
    """
    from .dependencies import get_layer_transition_service

    try:
        service = await get_layer_transition_service()
        return {
            "status": "active" if service.enable_auto_promotion else "disabled",
            "statistics": service.get_statistics(),
        }
    except Exception as e:
        logger.error(f"Error getting promotion status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/promotion/scan")
async def trigger_promotion_scan():
    """
    Manually trigger a promotion scan.

    Scans PERCEPTION and SEMANTIC layers for entities that meet
    promotion criteria and promotes them.
    """
    from .dependencies import get_layer_transition_service

    try:
        service = await get_layer_transition_service()
        result = await service.run_promotion_scan()

        return {
            "success": True,
            "scan_results": result,
        }
    except Exception as e:
        logger.error(f"Error running promotion scan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/promotion/candidates/{layer}")
async def get_promotion_candidates(layer: str):
    """
    Get entities that are candidates for promotion from a specific layer.

    Args:
        layer: The source layer (PERCEPTION or SEMANTIC)
    """
    from .dependencies import get_layer_transition_service

    layer_upper = layer.upper()
    if layer_upper not in ["PERCEPTION", "SEMANTIC"]:
        raise HTTPException(
            status_code=400,
            detail="Layer must be PERCEPTION or SEMANTIC"
        )

    try:
        service = await get_layer_transition_service()
        candidates = await service.scan_for_promotion_candidates(layer_upper)

        return {
            "layer": layer_upper,
            "candidate_count": len(candidates),
            "candidate_ids": candidates[:100],  # Limit response size
        }
    except Exception as e:
        logger.error(f"Error getting promotion candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Neurosymbolic Query Endpoints
# ========================================

class QueryRequest(BaseModel):
    """Request model for neurosymbolic queries."""
    question: str = Field(..., description="Natural language question")
    patient_id: Optional[str] = Field(None, description="Patient ID for context")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    trace_layers: bool = Field(False, description="Include layer trace in response")
    force_strategy: Optional[str] = Field(None, description="Override strategy")


# Global neurosymbolic query service instance
_neurosymbolic_service_instance = None


async def get_neurosymbolic_service():
    """Get or create neurosymbolic query service instance."""
    global _neurosymbolic_service_instance

    if _neurosymbolic_service_instance is None:
        from application.services.neurosymbolic_query_service import NeurosymbolicQueryService

        backend = await get_kg_backend()

        _neurosymbolic_service_instance = NeurosymbolicQueryService(
            backend=backend,
            enable_caching=True,
        )
        logger.info("NeurosymbolicQueryService initialized")

    return _neurosymbolic_service_instance


@app.post("/api/query")
async def execute_neurosymbolic_query(request: QueryRequest):
    """
    Execute a neurosymbolic query across knowledge graph layers.

    This endpoint:
    1. Detects query type (drug interaction, symptoms, etc.)
    2. Selects appropriate strategy (symbolic-only, neural-first, etc.)
    3. Traverses layers: APPLICATION → REASONING → SEMANTIC → PERCEPTION
    4. Tracks response for feedback attribution

    Returns a response_id that can be used for thumbs up/down feedback.
    """
    import uuid

    try:
        service = await get_neurosymbolic_service()

        # Parse optional strategy override
        force_strategy = None
        if request.force_strategy:
            from application.services.neurosymbolic_query_service import QueryStrategy
            try:
                force_strategy = QueryStrategy(request.force_strategy)
            except ValueError:
                pass

        # Execute query
        result, trace = await service.execute_query(
            query_text=request.question,
            patient_context={"patient_id": request.patient_id} if request.patient_id else None,
            force_strategy=force_strategy,
            trace_execution=request.trace_layers,
        )

        # Generate response ID for feedback tracking
        response_id = str(uuid.uuid4())

        # Build response text from result
        response_text = _build_response_text(result)

        # Track response for feedback attribution
        track_response(
            response_id=response_id,
            query_text=request.question,
            response_text=response_text,
            entities_involved=result.get("entity_ids", []),
            layers_traversed=result.get("layers_traversed", []),
            patient_id=request.patient_id or "anonymous",
            session_id=request.session_id or "default",
            confidence=result.get("confidence", 0.0),
        )

        # Build API response
        response = {
            "response_id": response_id,
            "query_id": result.get("query_id"),
            "answer": response_text,
            "confidence": result.get("confidence", 0.0),
            "strategy": result.get("strategy"),
            "layers_traversed": result.get("layers_traversed", []),
            "entity_count": len(result.get("entities", [])),
            "execution_time_ms": result.get("execution_time_ms", 0),
        }

        # Include detailed trace if requested
        if request.trace_layers and trace:
            response["trace"] = {
                "layer_results": [
                    {
                        "layer": lr.layer.value,
                        "entity_count": len(lr.entities),
                        "confidence": lr.confidence.score,
                        "query_time_ms": lr.query_time_ms,
                    }
                    for lr in trace.layer_results
                ],
                "conflicts_detected": trace.conflicts_detected,
            }

        # Include entities if present
        if result.get("entities"):
            response["entities"] = result["entities"][:20]  # Limit for response size

        # Include warnings/inferences
        if result.get("warnings"):
            response["warnings"] = result["warnings"]
        if result.get("inferences"):
            response["inferences"] = result["inferences"]

        # Flag low confidence for UI to show feedback prompt
        response["request_feedback"] = result.get("confidence", 0) < 0.7

        return response

    except Exception as e:
        logger.error(f"Error executing neurosymbolic query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _build_response_text(result: Dict[str, Any]) -> str:
    """Build human-readable response text from query result."""
    parts = []

    # Add main answer based on entities
    entities = result.get("entities", [])
    if entities:
        entity_names = [e.get("name", "Unknown") for e in entities[:5]]
        parts.append(f"Found: {', '.join(entity_names)}")

    # Add warnings
    for warning in result.get("warnings", []):
        parts.append(f"Warning: {warning}")

    # Add inferences
    for inference in result.get("inferences", []):
        if isinstance(inference, dict):
            parts.append(f"Inference: {inference.get('description', str(inference))}")
        else:
            parts.append(f"Inference: {inference}")

    # Add disclaimer if present
    if result.get("disclaimer"):
        parts.append(result["disclaimer"])

    return "\n".join(parts) if parts else "No results found."


@app.get("/api/query/stats")
async def get_query_statistics():
    """Get neurosymbolic query statistics."""
    try:
        service = await get_neurosymbolic_service()
        return service.stats
    except Exception as e:
        logger.error(f"Error getting query stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Agent Discovery Endpoints
# ========================================

# Global discovery service instance
_discovery_service_instance = None


async def get_discovery_service():
    """Get or create agent discovery service instance."""
    global _discovery_service_instance

    if _discovery_service_instance is None:
        from application.services.agent_discovery import AgentDiscoveryService

        backend = await get_kg_backend()
        _discovery_service_instance = AgentDiscoveryService(backend=backend)
        await _discovery_service_instance.initialize()
        logger.info("AgentDiscoveryService initialized")

    return _discovery_service_instance


class AgentRegistrationRequest(BaseModel):
    """Request model for agent registration."""
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(default="1.0.0", description="Agent version")
    url: str = Field(..., description="Agent HTTP endpoint URL")
    capabilities: List[str] = Field(..., description="List of capabilities")
    tier: Optional[str] = Field(default="optional", description="Service tier (core/optional)")
    health_check_url: Optional[str] = Field(None, description="Health check endpoint")


@app.get("/api/agents")
async def list_agents(
    status: Optional[str] = None,
    tier: Optional[str] = None,
):
    """
    List all registered agents.

    Args:
        status: Filter by status (active, inactive, degraded)
        tier: Filter by tier (core, optional)

    Returns:
        List of registered agents with their metadata
    """
    try:
        from application.services.agent_discovery import AgentStatus, AgentTier

        discovery = await get_discovery_service()

        status_filter = AgentStatus(status) if status else None
        tier_filter = AgentTier(tier) if tier else None

        agents = await discovery.list_all_agents(
            status_filter=status_filter,
            tier_filter=tier_filter,
        )

        return {
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "description": a.description,
                    "version": a.version,
                    "url": a.url,
                    "capabilities": a.capabilities,
                    "status": a.status.value,
                    "tier": a.tier.value,
                    "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                }
                for a in agents
            ],
            "total_count": len(agents),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/discover/{capability}")
async def discover_agent_by_capability(
    capability: str,
    limit: int = 10,
    include_inactive: bool = False,
):
    """
    Discover agents by capability.

    Searches the Knowledge Graph for agents that provide the specified capability.

    Args:
        capability: The capability to search for
        limit: Maximum number of agents to return
        include_inactive: Whether to include inactive agents

    Returns:
        List of matching agents sorted by last heartbeat
    """
    try:
        from application.services.agent_discovery import AgentStatus

        discovery = await get_discovery_service()

        status_filter = None if include_inactive else AgentStatus.ACTIVE

        result = await discovery.discover_by_capability(
            capability=capability,
            status_filter=status_filter,
            limit=limit,
        )

        return {
            "capability": capability,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "url": a.url,
                    "capabilities": a.capabilities,
                    "status": a.status.value,
                    "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                }
                for a in result.agents
            ],
            "total_found": result.total_found,
            "active_count": result.active_count,
        }

    except Exception as e:
        logger.error(f"Error discovering agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_id}")
async def get_agent_details(agent_id: str):
    """
    Get detailed information about a specific agent.

    Args:
        agent_id: The agent's unique identifier

    Returns:
        Full agent metadata
    """
    try:
        discovery = await get_discovery_service()
        agent = await discovery.get_agent_by_id(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "description": agent.description,
            "version": agent.version,
            "url": agent.url,
            "capabilities": agent.capabilities,
            "status": agent.status.value,
            "tier": agent.tier.value,
            "health_check_url": agent.health_check_url,
            "heartbeat_interval_seconds": agent.heartbeat_interval_seconds,
            "registered_at": agent.registered_at.isoformat() if agent.registered_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
            "metadata": agent.metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/register")
async def register_agent(request: AgentRegistrationRequest):
    """
    Register an agent in the Knowledge Graph.

    Creates or updates an AgentService node with the agent's metadata.
    Agents should call this endpoint on startup.

    Returns:
        Registration confirmation
    """
    try:
        from application.services.agent_discovery import (
            AgentServiceInfo,
            AgentStatus,
            AgentTier,
        )

        discovery = await get_discovery_service()

        agent_info = AgentServiceInfo(
            agent_id=request.agent_id,
            name=request.name,
            description=request.description,
            version=request.version,
            url=request.url,
            capabilities=request.capabilities,
            status=AgentStatus.ACTIVE,
            tier=AgentTier(request.tier) if request.tier else AgentTier.OPTIONAL,
            health_check_url=request.health_check_url,
        )

        success = await discovery.register_agent(agent_info)

        if success:
            return {
                "success": True,
                "message": f"Agent {request.agent_id} registered successfully",
                "agent_id": request.agent_id,
                "capabilities": request.capabilities,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to register agent")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str):
    """
    Update agent heartbeat.

    Agents should call this periodically to indicate they are alive.

    Args:
        agent_id: The agent's unique identifier

    Returns:
        Heartbeat confirmation
    """
    try:
        discovery = await get_discovery_service()
        success = await discovery.update_heartbeat(agent_id)

        if success:
            return {
                "success": True,
                "agent_id": agent_id,
                "message": "Heartbeat recorded",
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating heartbeat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/agents/{agent_id}")
async def deregister_agent(agent_id: str):
    """
    Deregister an agent from the Knowledge Graph.

    Removes the AgentService node. Use with caution.

    Args:
        agent_id: The agent's unique identifier

    Returns:
        Deregistration confirmation
    """
    try:
        discovery = await get_discovery_service()
        success = await discovery.deregister_agent(agent_id)

        if success:
            return {
                "success": True,
                "message": f"Agent {agent_id} deregistered",
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deregistering agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/capabilities/summary")
async def get_capabilities_summary():
    """
    Get a summary of all capabilities and which agents provide them.

    Returns:
        Map of capability -> list of agent IDs
    """
    try:
        discovery = await get_discovery_service()
        summary = await discovery.get_capabilities_summary()

        return {
            "capabilities": summary,
            "total_capabilities": len(summary),
        }

    except Exception as e:
        logger.error(f"Error getting capabilities summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/scan-stale")
async def scan_stale_agents():
    """
    Scan for stale agents and mark them as degraded.

    Agents without a recent heartbeat will be marked as degraded.

    Returns:
        List of agent IDs that were marked as degraded
    """
    try:
        discovery = await get_discovery_service()
        stale_ids = await discovery.scan_stale_agents()

        return {
            "success": True,
            "stale_agents": stale_ids,
            "count": len(stale_ids),
        }

    except Exception as e:
        logger.error(f"Error scanning stale agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
