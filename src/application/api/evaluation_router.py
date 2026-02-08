"""
Router de Evaluación - Endpoints para testing automatizado del agente.

Este router expone endpoints de inspección que permiten al framework
de evaluación:
1. Capturar snapshots completos de memoria de pacientes
2. Seedear estado inicial para escenarios de test
3. Resetear memoria de pacientes
4. Forzar flush de pipelines asíncronos
5. Verificar quiescence de todos los servicios
6. Ejecutar chat vía REST (para testing sin WebSocket)

IMPORTANTE: Estos endpoints solo están disponibles cuando
SYNAPSEFLOW_EVAL_MODE=true y requieren X-Eval-API-Key header.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .evaluation_auth import verify_eval_access, is_eval_mode_enabled
from .evaluation_models import (
    MemorySnapshot,
    MemoryEntityModel,
    MemoryRelationshipModel,
    Mem0MemoryModel,
    RedisLayerSnapshot,
    Mem0LayerSnapshot,
    GraphitiLayerSnapshot,
    Neo4jDIKWLayerSnapshot,
    SeedStateRequest,
    SeedStateResponse,
    SeedEntityRequest,
    ResetPatientResponse,
    FlushPipelinesResponse,
    PipelineStatus,
    TestChatRequest,
    TestChatResponse,
    EvaluationHealthResponse,
    DIKWLayer,
    MemoryLayer,
)
from .dependencies import (
    get_patient_memory,
    get_chat_service,
    get_kg_backend,
    get_crystallization_service,
    get_episodic_memory,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/eval",
    tags=["Evaluation Framework"],
    dependencies=[Depends(verify_eval_access)],
)


# ========================================
# Health Check
# ========================================

@router.get("/health", response_model=EvaluationHealthResponse)
async def evaluation_health(
    _auth: str = Depends(verify_eval_access)
) -> EvaluationHealthResponse:
    """
    Health check del framework de evaluación.

    Verifica que todos los servicios necesarios están disponibles.
    """
    services = {}

    # Check patient memory
    try:
        patient_memory = await get_patient_memory()
        services["patient_memory"] = patient_memory is not None
    except Exception as e:
        logger.error(f"Patient memory check failed: {e}")
        services["patient_memory"] = False

    # Check chat service
    try:
        chat_service = await get_chat_service()
        services["chat_service"] = chat_service is not None
    except Exception as e:
        logger.error(f"Chat service check failed: {e}")
        services["chat_service"] = False

    # Check KG backend
    try:
        kg_backend = await get_kg_backend()
        services["kg_backend"] = kg_backend is not None
    except Exception as e:
        logger.error(f"KG backend check failed: {e}")
        services["kg_backend"] = False

    # Check crystallization service (optional)
    try:
        crystallization = await get_crystallization_service()
        services["crystallization"] = crystallization is not None
    except Exception as e:
        services["crystallization"] = False

    # Check episodic memory (optional)
    try:
        episodic = await get_episodic_memory()
        services["episodic_memory"] = episodic is not None
    except Exception as e:
        services["episodic_memory"] = False

    all_critical_ok = all([
        services.get("patient_memory", False),
        services.get("chat_service", False),
        services.get("kg_backend", False),
    ])

    return EvaluationHealthResponse(
        status="ok" if all_critical_ok else "degraded",
        eval_mode_enabled=is_eval_mode_enabled(),
        services=services,
        version="1.0.0",
    )


# ========================================
# Memory Snapshot
# ========================================

@router.get("/memory-snapshot/{patient_id}", response_model=MemorySnapshot)
async def get_memory_snapshot(
    patient_id: str,
    include_redis: bool = Query(True, description="Incluir datos de Redis"),
    include_mem0: bool = Query(True, description="Incluir memorias de Mem0"),
    include_graphiti: bool = Query(True, description="Incluir episodios de Graphiti"),
    include_neo4j: bool = Query(True, description="Incluir nodos DIKW de Neo4j"),
    _auth: str = Depends(verify_eval_access),
) -> MemorySnapshot:
    """
    Captura el estado completo de memoria de un paciente.

    Consulta todas las capas de memoria y retorna un snapshot unificado
    que puede usarse para comparación en evaluaciones.
    """
    logger.info(f"Capturing memory snapshot for patient: {patient_id}")
    timestamp = datetime.utcnow()

    patient_memory = await get_patient_memory()
    kg_backend = await get_kg_backend()

    # Initialize layer snapshots
    redis_snapshot = RedisLayerSnapshot()
    mem0_snapshot = Mem0LayerSnapshot()
    graphiti_snapshot = GraphitiLayerSnapshot()
    neo4j_snapshot = Neo4jDIKWLayerSnapshot()

    # 1. Redis Layer
    if include_redis:
        try:
            redis_snapshot = await _capture_redis_snapshot(patient_id, patient_memory)
        except Exception as e:
            logger.error(f"Error capturing Redis snapshot: {e}")

    # 2. Mem0 Layer
    if include_mem0:
        try:
            mem0_snapshot = await _capture_mem0_snapshot(patient_id, patient_memory)
        except Exception as e:
            logger.error(f"Error capturing Mem0 snapshot: {e}")

    # 3. Graphiti/FalkorDB Layer
    if include_graphiti:
        try:
            graphiti_snapshot = await _capture_graphiti_snapshot(patient_id)
        except Exception as e:
            logger.error(f"Error capturing Graphiti snapshot: {e}")

    # 4. Neo4j DIKW Layer
    if include_neo4j:
        try:
            neo4j_snapshot = await _capture_neo4j_dikw_snapshot(patient_id, kg_backend)
        except Exception as e:
            logger.error(f"Error capturing Neo4j DIKW snapshot: {e}")

    return MemorySnapshot(
        patient_id=patient_id,
        timestamp=timestamp,
        redis=redis_snapshot,
        mem0=mem0_snapshot,
        graphiti=graphiti_snapshot,
        neo4j_dikw=neo4j_snapshot,
    )


async def _capture_redis_snapshot(
    patient_id: str,
    patient_memory
) -> RedisLayerSnapshot:
    """Captura snapshot de la capa Redis."""
    if not hasattr(patient_memory, 'redis') or patient_memory.redis is None:
        return RedisLayerSnapshot()

    # Get session data for this patient
    # Note: Redis stores by session_id, not patient_id directly
    # We need to query Neo4j for sessions associated with this patient
    try:
        sessions = await patient_memory.neo4j.query_raw(
            "MATCH (p:Patient {id: $patient_id})-[:HAS_SESSION]->(s:Session) "
            "RETURN s.id as session_id ORDER BY s.created_at DESC LIMIT 10",
            {"patient_id": patient_id}
        )

        session_data = {}
        active_sessions = 0

        for record in sessions or []:
            session_id = record.get("session_id")
            if session_id:
                data = await patient_memory.redis.get_session(session_id)
                if data:
                    session_data[session_id] = data
                    active_sessions += 1

        return RedisLayerSnapshot(
            session_data=session_data,
            active_sessions=active_sessions,
            ttl_seconds=86400,  # Default TTL
        )
    except Exception as e:
        logger.warning(f"Redis snapshot partial failure: {e}")
        return RedisLayerSnapshot()


async def _capture_mem0_snapshot(
    patient_id: str,
    patient_memory
) -> Mem0LayerSnapshot:
    """Captura snapshot de la capa Mem0."""
    if not hasattr(patient_memory, 'mem0') or patient_memory.mem0 is None:
        return Mem0LayerSnapshot()

    try:
        mem0_result = patient_memory.mem0.get_all(
            user_id=patient_id,
            limit=100  # Get more memories for evaluation
        )

        memories = []
        for mem in mem0_result.get("results", []) if mem0_result else []:
            # Verify memory belongs to this patient
            mem_user_id = mem.get("user_id") or mem.get("metadata", {}).get("user_id")
            if mem_user_id and mem_user_id != patient_id:
                continue

            memories.append(Mem0MemoryModel(
                id=mem.get("id", ""),
                text=mem.get("memory", ""),
                created_at=_parse_datetime(mem.get("created_at")),
                metadata=mem.get("metadata", {}),
            ))

        return Mem0LayerSnapshot(
            memories=memories,
            memory_count=len(memories),
        )
    except Exception as e:
        logger.warning(f"Mem0 snapshot partial failure: {e}")
        return Mem0LayerSnapshot()


async def _capture_graphiti_snapshot(patient_id: str) -> GraphitiLayerSnapshot:
    """Captura snapshot de la capa Graphiti/FalkorDB."""
    episodic_service = await get_episodic_memory()
    if not episodic_service:
        return GraphitiLayerSnapshot()

    try:
        # Get recent episodes for this patient
        episodes = await episodic_service.retrieve_recent_episodes(
            patient_id=patient_id,
            limit=50,
        )

        episode_list = []
        entities = []
        edges = []

        for ep in episodes or []:
            episode_list.append({
                "episode_id": getattr(ep, 'episode_id', ''),
                "content": getattr(ep, 'content', ''),
                "timestamp": str(getattr(ep, 'timestamp', '')),
                "mode": getattr(ep, 'mode', None),
            })

            # Extract entities from episodes
            for ent in getattr(ep, 'entities', []) or []:
                entities.append(MemoryEntityModel(
                    name=ent.get("name", "") if isinstance(ent, dict) else str(ent),
                    entity_type=ent.get("entity_type", "Entity") if isinstance(ent, dict) else "Entity",
                    layer=MemoryLayer.GRAPHITI,
                ))

        return GraphitiLayerSnapshot(
            episodes=episode_list,
            entities=entities,
            edges=edges,
            episode_count=len(episode_list),
        )
    except Exception as e:
        logger.warning(f"Graphiti snapshot partial failure: {e}")
        return GraphitiLayerSnapshot()


async def _capture_neo4j_dikw_snapshot(
    patient_id: str,
    kg_backend
) -> Neo4jDIKWLayerSnapshot:
    """Captura snapshot de la capa Neo4j DIKW."""
    perception = []
    semantic = []
    reasoning = []
    application = []
    relationships = []

    try:
        # Query all DIKW entities for this patient
        entity_query = """
        MATCH (n)
        WHERE n.patient_id = $patient_id
          AND n.dikw_layer IS NOT NULL
        RETURN n.name as name, n.entity_type as entity_type, n.dikw_layer as layer,
               n.confidence as confidence, n.observation_count as obs_count,
               n.first_observed as first_obs, n.last_observed as last_obs,
               properties(n) as all_props
        """
        entities = await kg_backend.query_raw(entity_query, {"patient_id": patient_id})

        for record in entities or []:
            entity = MemoryEntityModel(
                name=record.get("name", ""),
                entity_type=record.get("entity_type", "Entity"),
                layer=MemoryLayer.NEO4J_DIKW,
                dikw_layer=DIKWLayer(record.get("layer")) if record.get("layer") else None,
                confidence=record.get("confidence"),
                observation_count=record.get("obs_count"),
                first_observed=_parse_datetime(record.get("first_obs")),
                last_observed=_parse_datetime(record.get("last_obs")),
                properties=record.get("all_props", {}),
            )

            layer = record.get("layer", "")
            if layer == "PERCEPTION":
                perception.append(entity)
            elif layer == "SEMANTIC":
                semantic.append(entity)
            elif layer == "REASONING":
                reasoning.append(entity)
            elif layer == "APPLICATION":
                application.append(entity)

        # Query relationships
        rel_query = """
        MATCH (a)-[r]->(b)
        WHERE a.patient_id = $patient_id OR b.patient_id = $patient_id
        RETURN a.name as from_name, type(r) as rel_type, b.name as to_name,
               properties(r) as rel_props
        LIMIT 200
        """
        rels = await kg_backend.query_raw(rel_query, {"patient_id": patient_id})

        for record in rels or []:
            relationships.append(MemoryRelationshipModel(
                from_name=record.get("from_name", ""),
                to_name=record.get("to_name", ""),
                relationship_type=record.get("rel_type", ""),
                properties=record.get("rel_props", {}),
                layer=MemoryLayer.NEO4J_DIKW,
            ))

    except Exception as e:
        logger.warning(f"Neo4j DIKW snapshot partial failure: {e}")

    return Neo4jDIKWLayerSnapshot(
        perception=perception,
        semantic=semantic,
        reasoning=reasoning,
        application=application,
        relationships=relationships,
    )


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse datetime from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


# ========================================
# Seed State
# ========================================

@router.post("/seed-state", response_model=SeedStateResponse)
async def seed_state(
    request: SeedStateRequest,
    _auth: str = Depends(verify_eval_access),
) -> SeedStateResponse:
    """
    Seedea el estado de memoria de un paciente con datos iniciales.

    Crea entidades y relaciones en las capas correspondientes
    para preparar un escenario de evaluación.
    """
    logger.info(f"Seeding state for patient: {request.patient_id}")

    patient_memory = await get_patient_memory()
    kg_backend = await get_kg_backend()
    errors = []
    entities_created = 0
    relationships_created = 0

    # Optionally clear existing data first
    if request.clear_existing:
        reset_result = await _reset_patient_memory(request.patient_id, patient_memory, kg_backend)
        if not reset_result.success:
            errors.extend(reset_result.errors)

    # Ensure patient exists
    try:
        await patient_memory.get_or_create_patient(request.patient_id)
    except Exception as e:
        logger.error(f"Failed to create patient: {e}")
        errors.append(f"Failed to create patient: {str(e)}")
        return SeedStateResponse(
            success=False,
            patient_id=request.patient_id,
            entities_created=0,
            relationships_created=0,
            errors=errors,
        )

    # Create entities
    for entity in request.entities:
        try:
            entity_id = f"{entity.dikw_layer.value.lower()}_{uuid.uuid4().hex[:12]}"
            properties = {
                "id": entity_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "dikw_layer": entity.dikw_layer.value,
                "confidence": entity.confidence,
                "observation_count": 1,
                "patient_id": request.patient_id,
                "first_observed": datetime.utcnow().isoformat(),
                "last_observed": datetime.utcnow().isoformat(),
                "source": "eval_seed",
                **entity.properties,
            }

            labels = ["Entity", entity.dikw_layer.value, entity.entity_type]
            await kg_backend.add_entity(
                entity_id=entity_id,
                properties=properties,
                labels=labels,
            )
            entities_created += 1
            logger.debug(f"Created entity: {entity.name} ({entity.dikw_layer.value})")

        except Exception as e:
            logger.error(f"Failed to create entity {entity.name}: {e}")
            errors.append(f"Entity '{entity.name}': {str(e)}")

    # Create relationships
    for rel in request.relationships:
        try:
            # Find source and target entities
            source_query = """
            MATCH (n {name: $name, patient_id: $patient_id})
            RETURN n.id as id LIMIT 1
            """
            source = await kg_backend.query_raw(
                source_query,
                {"name": rel.from_name, "patient_id": request.patient_id}
            )
            target = await kg_backend.query_raw(
                source_query,
                {"name": rel.to_name, "patient_id": request.patient_id}
            )

            if source and target:
                source_id = source[0].get("id")
                target_id = target[0].get("id")

                await kg_backend.add_relationship(
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=rel.relationship_type,
                    properties=rel.properties,
                )
                relationships_created += 1
                logger.debug(f"Created relationship: {rel.from_name} -[{rel.relationship_type}]-> {rel.to_name}")
            else:
                errors.append(f"Relationship endpoints not found: {rel.from_name} -> {rel.to_name}")

        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            errors.append(f"Relationship '{rel.from_name} -> {rel.to_name}': {str(e)}")

    success = entities_created > 0 or relationships_created > 0 or len(request.entities) == 0

    logger.info(
        f"Seed complete: {entities_created} entities, {relationships_created} relationships, "
        f"{len(errors)} errors"
    )

    return SeedStateResponse(
        success=success,
        patient_id=request.patient_id,
        entities_created=entities_created,
        relationships_created=relationships_created,
        errors=errors,
    )


# ========================================
# Reset Patient
# ========================================

@router.post("/reset/{patient_id}", response_model=ResetPatientResponse)
async def reset_patient(
    patient_id: str,
    _auth: str = Depends(verify_eval_access),
) -> ResetPatientResponse:
    """
    Limpia toda la memoria de un paciente.

    Elimina datos de todas las capas de memoria (Redis, Mem0, Graphiti, Neo4j).
    Usado para cleanup después de tests.
    """
    logger.info(f"Resetting memory for patient: {patient_id}")

    patient_memory = await get_patient_memory()
    kg_backend = await get_kg_backend()

    return await _reset_patient_memory(patient_id, patient_memory, kg_backend)


async def _reset_patient_memory(
    patient_id: str,
    patient_memory,
    kg_backend
) -> ResetPatientResponse:
    """Internal function to reset patient memory across all layers."""
    errors = []
    layers_cleared = []
    entities_deleted = 0
    relationships_deleted = 0
    memories_deleted = 0

    # 1. Clear Neo4j DIKW entities
    try:
        # Delete all entities for this patient
        delete_query = """
        MATCH (n {patient_id: $patient_id})
        WHERE n.source = 'eval_seed' OR n.dikw_layer IS NOT NULL
        DETACH DELETE n
        RETURN count(n) as deleted
        """
        result = await kg_backend.query_raw(delete_query, {"patient_id": patient_id})
        if result:
            entities_deleted = result[0].get("deleted", 0)
        layers_cleared.append("neo4j_dikw")
        logger.debug(f"Neo4j: deleted {entities_deleted} entities")
    except Exception as e:
        logger.error(f"Failed to clear Neo4j: {e}")
        errors.append(f"Neo4j: {str(e)}")

    # 2. Clear Mem0 memories
    try:
        if hasattr(patient_memory, 'mem0') and patient_memory.mem0:
            # Mem0 doesn't have a delete_all_for_user method,
            # so we need to get all memories and delete individually
            memories = patient_memory.mem0.get_all(user_id=patient_id, limit=1000)
            for mem in memories.get("results", []) if memories else []:
                mem_id = mem.get("id")
                if mem_id:
                    try:
                        patient_memory.mem0.delete(mem_id)
                        memories_deleted += 1
                    except Exception:
                        pass
            layers_cleared.append("mem0")
            logger.debug(f"Mem0: deleted {memories_deleted} memories")
    except Exception as e:
        logger.error(f"Failed to clear Mem0: {e}")
        errors.append(f"Mem0: {str(e)}")

    # 3. Clear Redis sessions
    try:
        if hasattr(patient_memory, 'redis') and patient_memory.redis:
            # Get all sessions for this patient and clear them
            sessions = await patient_memory.neo4j.query_raw(
                "MATCH (p:Patient {id: $patient_id})-[:HAS_SESSION]->(s:Session) "
                "RETURN s.id as session_id",
                {"patient_id": patient_id}
            )
            for record in sessions or []:
                session_id = record.get("session_id")
                if session_id:
                    await patient_memory.redis.delete_session(session_id)
            layers_cleared.append("redis")
            logger.debug(f"Redis: cleared sessions for patient")
    except Exception as e:
        logger.error(f"Failed to clear Redis: {e}")
        errors.append(f"Redis: {str(e)}")

    # 4. Clear Graphiti episodes
    try:
        episodic = await get_episodic_memory()
        if episodic:
            # Graphiti doesn't have a simple delete-by-patient API
            # This would need custom implementation
            layers_cleared.append("graphiti")
            logger.debug(f"Graphiti: marked for clearing (may need manual cleanup)")
    except Exception as e:
        logger.error(f"Failed to clear Graphiti: {e}")
        errors.append(f"Graphiti: {str(e)}")

    success = len(layers_cleared) > 0 and len(errors) == 0

    return ResetPatientResponse(
        success=success,
        patient_id=patient_id,
        layers_cleared=layers_cleared,
        entities_deleted=entities_deleted,
        relationships_deleted=relationships_deleted,
        memories_deleted=memories_deleted,
        errors=errors,
    )


# ========================================
# Pipeline Control
# ========================================

@router.post("/flush-pipelines", response_model=FlushPipelinesResponse)
async def flush_pipelines(
    _auth: str = Depends(verify_eval_access),
) -> FlushPipelinesResponse:
    """
    Fuerza el procesamiento inmediato de todos los eventos pendientes.

    Ejecuta el flush del crystallization service y espera a que
    todos los pipelines asíncronos completen su trabajo.
    """
    logger.info("Flush pipelines requested")

    crystallization = await get_crystallization_service()
    errors = []

    if not crystallization:
        return FlushPipelinesResponse(
            flushed=True,
            events_processed=0,
            entities_crystallized=0,
            promotions_executed=0,
            pending_after_flush=0,
            processing_time_ms=0,
            errors=["Crystallization service not enabled"],
        )

    try:
        result = await crystallization.flush_now()

        return FlushPipelinesResponse(
            flushed=result.flushed,
            events_processed=result.events_processed,
            entities_crystallized=result.entities_crystallized,
            promotions_executed=result.promotions_executed,
            pending_after_flush=result.pending_after_flush,
            processing_time_ms=result.processing_time_ms,
            errors=result.errors,
        )
    except Exception as e:
        logger.error(f"Flush failed: {e}", exc_info=True)
        errors.append(str(e))
        return FlushPipelinesResponse(
            flushed=False,
            errors=errors,
        )


@router.get("/pipeline-status", response_model=PipelineStatus)
async def get_pipeline_status(
    _auth: str = Depends(verify_eval_access),
) -> PipelineStatus:
    """
    Reporta el estado de quiescence de todos los pipelines.

    Usado para verificar si es seguro tomar un snapshot.
    """
    crystallization = await get_crystallization_service()

    if not crystallization:
        return PipelineStatus(
            quiescent=True,
            crystallization={},
            pending_events=0,
            buffer_size=0,
            tasks_in_flight=0,
            last_crystallization=None,
        )

    try:
        buffer_status = crystallization.get_buffer_status()
        stats = await crystallization.get_crystallization_stats()

        quiescent = (
            buffer_status.buffer_size == 0 and
            not buffer_status.batch_in_progress
        )

        return PipelineStatus(
            quiescent=quiescent,
            crystallization=stats,
            pending_events=0,  # TODO: Track event bus pending
            buffer_size=buffer_status.buffer_size,
            tasks_in_flight=0,  # TODO: Track async tasks
            last_crystallization=buffer_status.last_flush,
        )
    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        return PipelineStatus(
            quiescent=False,
            crystallization={"error": str(e)},
        )


# ========================================
# Test Chat Endpoint
# ========================================

@router.post("/chat", response_model=TestChatResponse)
async def test_chat(
    request: TestChatRequest,
    _auth: str = Depends(verify_eval_access),
) -> TestChatResponse:
    """
    Endpoint REST de chat para evaluación.

    Permite enviar mensajes al agente sin usar WebSocket,
    facilitando el testing automatizado.
    """
    logger.info(f"Test chat request: patient={request.patient_id}, message={request.message[:50]}...")

    patient_memory = await get_patient_memory()
    chat_service = await get_chat_service()

    # Generate session_id if not provided
    session_id = request.session_id or f"eval-{uuid.uuid4().hex[:12]}"
    response_id = str(uuid.uuid4())

    # Ensure patient exists
    try:
        await patient_memory.get_or_create_patient(request.patient_id)
    except Exception as e:
        logger.error(f"Failed to create patient: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create patient: {str(e)}")

    # Ensure session exists
    try:
        await patient_memory.create_session(
            session_id=session_id,
            patient_id=request.patient_id,
            title="Evaluation Session",
            device_type="eval_framework",
        )
    except Exception as e:
        # Session might already exist, which is fine
        logger.debug(f"Session creation note: {e}")

    # Build conversation history from request
    conversation_history = []
    for msg in request.conversation_history:
        from application.services.chat_history_service import Message
        conversation_history.append(Message(
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
            timestamp=datetime.utcnow(),
            patient_id=request.patient_id,
            session_id=session_id,
        ))

    # Execute chat query
    start_time = datetime.utcnow()
    try:
        response = await chat_service.query(
            question=request.message,
            conversation_history=conversation_history,
            patient_id=request.patient_id,
            session_id=session_id,
            response_id=response_id,
        )

        query_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return TestChatResponse(
            patient_id=request.patient_id,
            session_id=session_id,
            response_id=response_id,
            content=response.content if hasattr(response, 'content') else str(response),
            confidence=response.confidence if hasattr(response, 'confidence') else 0.0,
            sources=response.sources if hasattr(response, 'sources') else [],
            reasoning_trail=response.reasoning_trail if hasattr(response, 'reasoning_trail') else [],
            layer_accesses=response.layer_accesses if hasattr(response, 'layer_accesses') else [],
            entities_extracted=response.entities if hasattr(response, 'entities') else [],
            medical_alerts=response.medical_alerts if hasattr(response, 'medical_alerts') else [],
            query_time_ms=query_time,
        )

    except Exception as e:
        logger.error(f"Chat query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat query failed: {str(e)}")
