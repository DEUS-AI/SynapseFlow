"""Main FastAPI application entry point."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import logging
from typing import Dict, Set, List
import tempfile
import os

from .kg_router import router as kg_router
from .document_router import router as document_router
from .dependencies import get_chat_service, get_patient_memory, get_kg_backend

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
        # Build Cypher query based on filters
        if layer:
            query = f"""
            MATCH (n)
            WHERE n.layer = $layer
            WITH n LIMIT $limit
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN
                collect(DISTINCT {{
                    id: elementId(n),
                    label: coalesce(n.name, n.label, elementId(n)),
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
                    label: coalesce(n.name, n.label, elementId(n)),
                    type: head(labels(n)),
                    layer: coalesce(n.layer, 'perception'),
                    properties: properties(n)
                }}) + collect(DISTINCT {{
                    id: elementId(m),
                    label: coalesce(m.name, m.label, elementId(m)),
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
                target: coalesce(target.name, target.label, elementId(target)),
                targetId: elementId(target)
            }) as outgoing,
            collect(DISTINCT {
                type: type(r_in),
                source: coalesce(source.name, source.label, elementId(source)),
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
    kg_backend = Depends(get_kg_backend)
):
    """Upload and process DDA specification file."""
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
            # Process DDA using markdown parser
            from infrastructure.parsers.markdown_parser import MarkdownDDAParser
            parser = MarkdownDDAParser()

            result = await parser.parse(tmp_path)

            # Store parsed DDA in Neo4j
            # 1. Create or merge Catalog node from domain
            catalog_query = """
            MERGE (c:Catalog {name: $domain})
            SET c.data_owner = $data_owner,
                c.business_context = $business_context,
                c.updated_at = datetime()
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
            SET s.updated_at = datetime()
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
                    t.updated_at = datetime()
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
                        col.updated_at = datetime()
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
                    r.updated_at = datetime()
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
                "message": "DDA processed and stored successfully",
                "domain": result.domain,
                "data_owner": result.data_owner,
                "catalog_created": result.domain,
                "schema_created": schema_name,
                "tables_created": tables_created,
                "columns_created": columns_created,
                "relationships_created": relationships_created,
                "entities": entity_names,
                "relationships": relationship_info
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
            t.description as description,
            t.row_count as row_count,
            collect({
                id: elementId(col),
                name: col.name,
                data_type: col.data_type,
                nullable: col.nullable,
                description: col.description
            }) as columns
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
            catalog.description as description,
            null as data_type,
            [] as path

        UNION

        // Get schemas
        MATCH (catalog:Catalog)-[:CONTAINS_SCHEMA]->(schema:Schema)
        RETURN
            elementId(schema) as id,
            schema.name as name,
            'schema' as type,
            schema.description as description,
            null as data_type,
            [catalog.name] as path

        UNION

        // Get tables
        MATCH (catalog:Catalog)-[:CONTAINS_SCHEMA]->(schema:Schema)-[:CONTAINS_TABLE]->(table:Table)
        RETURN
            elementId(table) as id,
            table.name as name,
            'table' as type,
            table.description as description,
            null as data_type,
            [catalog.name, schema.name] as path

        UNION

        // Get columns
        MATCH (catalog:Catalog)-[:CONTAINS_SCHEMA]->(schema:Schema)-[:CONTAINS_TABLE]->(table:Table)-[:HAS_COLUMN]->(column:Column)
        RETURN
            elementId(column) as id,
            column.name as name,
            'column' as type,
            column.description as description,
            column.data_type as data_type,
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
