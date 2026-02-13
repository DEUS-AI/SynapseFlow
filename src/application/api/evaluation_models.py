"""
Modelos Pydantic para el Framework de Evaluación de Agentes.

Este módulo define los modelos de request/response para los endpoints
de evaluación que permiten la inspección de memoria, seeding de estado,
y control de pipelines para testing automatizado.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


# ========================================
# Enums
# ========================================

class DIKWLayer(str, Enum):
    """Capas del conocimiento DIKW."""
    PERCEPTION = "PERCEPTION"
    SEMANTIC = "SEMANTIC"
    REASONING = "REASONING"
    APPLICATION = "APPLICATION"


class MemoryLayer(str, Enum):
    """Capas de memoria del sistema."""
    REDIS = "redis"
    MEM0 = "mem0"
    GRAPHITI = "graphiti"
    NEO4J_DIKW = "neo4j_dikw"


# ========================================
# Memory Entity Models
# ========================================

class MemoryEntityModel(BaseModel):
    """Entidad de memoria capturada en snapshot."""
    name: str = Field(..., description="Nombre de la entidad")
    entity_type: str = Field(..., description="Tipo de entidad (Medication, Condition, etc.)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Propiedades adicionales")
    layer: Optional[MemoryLayer] = Field(None, description="Capa de memoria donde reside")
    dikw_layer: Optional[DIKWLayer] = Field(None, description="Capa DIKW (solo para Neo4j)")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Score de confianza")
    observation_count: Optional[int] = Field(None, ge=0, description="Número de observaciones")
    first_observed: Optional[datetime] = Field(None, description="Primera observación")
    last_observed: Optional[datetime] = Field(None, description="Última observación")


class MemoryRelationshipModel(BaseModel):
    """Relación de memoria capturada en snapshot."""
    from_name: str = Field(..., description="Nombre de la entidad origen")
    to_name: str = Field(..., description="Nombre de la entidad destino")
    relationship_type: str = Field(..., description="Tipo de relación")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Propiedades de la relación")
    layer: Optional[MemoryLayer] = Field(None, description="Capa de memoria donde reside")


class Mem0MemoryModel(BaseModel):
    """Memoria de Mem0 (texto con metadatos)."""
    id: str = Field(..., description="ID de la memoria")
    text: str = Field(..., description="Contenido de la memoria")
    created_at: Optional[datetime] = Field(None, description="Timestamp de creación")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")


# ========================================
# Layer Snapshots
# ========================================

class RedisLayerSnapshot(BaseModel):
    """Snapshot de la capa Redis."""
    session_data: Dict[str, Any] = Field(default_factory=dict, description="Datos de sesión")
    active_sessions: int = Field(0, description="Número de sesiones activas")
    ttl_seconds: Optional[int] = Field(None, description="TTL configurado")


class Mem0LayerSnapshot(BaseModel):
    """Snapshot de la capa Mem0."""
    memories: List[Mem0MemoryModel] = Field(default_factory=list, description="Memorias extraídas")
    memory_count: int = Field(0, description="Total de memorias")


class GraphitiLayerSnapshot(BaseModel):
    """Snapshot de la capa Graphiti/FalkorDB."""
    episodes: List[Dict[str, Any]] = Field(default_factory=list, description="Episodios recientes")
    entities: List[MemoryEntityModel] = Field(default_factory=list, description="Entidades extraídas")
    edges: List[MemoryRelationshipModel] = Field(default_factory=list, description="Relaciones")
    episode_count: int = Field(0, description="Total de episodios")


class Neo4jDIKWLayerSnapshot(BaseModel):
    """Snapshot de la capa Neo4j DIKW."""
    perception: List[MemoryEntityModel] = Field(default_factory=list, description="Nodos PERCEPTION")
    semantic: List[MemoryEntityModel] = Field(default_factory=list, description="Nodos SEMANTIC")
    reasoning: List[MemoryEntityModel] = Field(default_factory=list, description="Nodos REASONING")
    application: List[MemoryEntityModel] = Field(default_factory=list, description="Nodos APPLICATION")
    relationships: List[MemoryRelationshipModel] = Field(default_factory=list, description="Relaciones DIKW")


# ========================================
# Complete Memory Snapshot
# ========================================

class MemorySnapshot(BaseModel):
    """Snapshot completo de memoria de un paciente."""
    patient_id: str = Field(..., description="ID del paciente")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp del snapshot")
    redis: RedisLayerSnapshot = Field(default_factory=RedisLayerSnapshot)
    mem0: Mem0LayerSnapshot = Field(default_factory=Mem0LayerSnapshot)
    graphiti: GraphitiLayerSnapshot = Field(default_factory=GraphitiLayerSnapshot)
    neo4j_dikw: Neo4jDIKWLayerSnapshot = Field(default_factory=Neo4jDIKWLayerSnapshot)

    def all_entities(self) -> List[MemoryEntityModel]:
        """Retorna todas las entidades de todas las capas."""
        all_ents = []
        all_ents.extend(self.graphiti.entities)
        all_ents.extend(self.neo4j_dikw.perception)
        all_ents.extend(self.neo4j_dikw.semantic)
        all_ents.extend(self.neo4j_dikw.reasoning)
        all_ents.extend(self.neo4j_dikw.application)
        return all_ents

    def all_relationships(self) -> List[MemoryRelationshipModel]:
        """Retorna todas las relaciones de todas las capas."""
        all_rels = []
        all_rels.extend(self.graphiti.edges)
        all_rels.extend(self.neo4j_dikw.relationships)
        return all_rels


# ========================================
# Seed State Request
# ========================================

class SeedEntityRequest(BaseModel):
    """Entidad a seedear en memoria."""
    name: str = Field(..., description="Nombre de la entidad")
    entity_type: str = Field(..., description="Tipo de entidad")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Propiedades")
    dikw_layer: DIKWLayer = Field(DIKWLayer.PERCEPTION, description="Capa DIKW inicial")
    confidence: float = Field(0.75, ge=0, le=1, description="Confianza inicial")


class SeedRelationshipRequest(BaseModel):
    """Relación a seedear en memoria."""
    from_name: str = Field(..., description="Entidad origen")
    to_name: str = Field(..., description="Entidad destino")
    relationship_type: str = Field(..., description="Tipo de relación")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Propiedades")


class SeedStateRequest(BaseModel):
    """Request para seedear estado de memoria de un paciente."""
    patient_id: str = Field(..., description="ID del paciente")
    entities: List[SeedEntityRequest] = Field(default_factory=list, description="Entidades a crear")
    relationships: List[SeedRelationshipRequest] = Field(default_factory=list, description="Relaciones a crear")
    clear_existing: bool = Field(False, description="Limpiar memoria existente antes de seedear")


class SeedStateResponse(BaseModel):
    """Respuesta del seeding de estado."""
    success: bool
    patient_id: str
    entities_created: int
    relationships_created: int
    errors: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ========================================
# Pipeline Control
# ========================================

class FlushPipelinesResponse(BaseModel):
    """Respuesta del flush de pipelines."""
    flushed: bool
    events_processed: int = Field(0, description="Eventos procesados")
    entities_crystallized: int = Field(0, description="Entidades cristalizadas")
    promotions_executed: int = Field(0, description="Promociones ejecutadas")
    pending_after_flush: int = Field(0, description="Eventos pendientes después del flush")
    processing_time_ms: float = Field(0, description="Tiempo de procesamiento en ms")
    errors: List[str] = Field(default_factory=list)


class PipelineStatus(BaseModel):
    """Estado de quiescence de pipelines."""
    quiescent: bool = Field(..., description="True si todos los pipelines están estables")
    crystallization: Dict[str, Any] = Field(default_factory=dict, description="Estado de cristalización")
    pending_events: int = Field(0, description="Eventos pendientes en el bus")
    buffer_size: int = Field(0, description="Entidades en buffer de cristalización")
    tasks_in_flight: int = Field(0, description="Tareas async en ejecución")
    last_crystallization: Optional[datetime] = Field(None, description="Último batch de cristalización")


class BufferStatus(BaseModel):
    """Estado del buffer de cristalización."""
    buffer_size: int = Field(0, description="Entidades pendientes en buffer")
    last_flush: Optional[datetime] = Field(None, description="Último flush ejecutado")
    batch_in_progress: bool = Field(False, description="Si hay un batch en procesamiento")
    running: bool = Field(False, description="Si el servicio está activo")


# ========================================
# Reset Response
# ========================================

class ResetPatientResponse(BaseModel):
    """Respuesta del reset de paciente."""
    success: bool
    patient_id: str
    layers_cleared: List[str] = Field(default_factory=list, description="Capas limpiadas")
    entities_deleted: int = Field(0)
    relationships_deleted: int = Field(0)
    memories_deleted: int = Field(0)
    errors: List[str] = Field(default_factory=list)


# ========================================
# Test Chat Endpoint
# ========================================

class TestChatRequest(BaseModel):
    """Request para el endpoint REST de chat (para evaluación)."""
    patient_id: str = Field(..., description="ID del paciente")
    session_id: Optional[str] = Field(None, description="ID de sesión (se genera si no se provee)")
    message: str = Field(..., description="Mensaje del paciente")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Historial de conversación previo"
    )


class TestChatResponse(BaseModel):
    """Respuesta del endpoint REST de chat."""
    patient_id: str
    session_id: str
    response_id: str
    content: str = Field(..., description="Respuesta del agente")
    confidence: float = Field(0.0, description="Confianza de la respuesta")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Fuentes consultadas")
    reasoning_trail: List[str] = Field(default_factory=list, description="Traza de razonamiento")
    layer_accesses: List[str] = Field(default_factory=list, description="Capas DIKW accedidas")
    entities_extracted: List[Dict[str, Any]] = Field(default_factory=list, description="Entidades extraídas")
    medical_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="Alertas médicas")
    query_time_ms: float = Field(0.0, description="Tiempo de respuesta en ms")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ========================================
# Health Check
# ========================================

class EvaluationHealthResponse(BaseModel):
    """Health check del framework de evaluación."""
    status: str = Field("ok", description="Estado general")
    eval_mode_enabled: bool = Field(..., description="Si el modo evaluación está activo")
    services: Dict[str, bool] = Field(default_factory=dict, description="Estado de servicios")
    version: str = Field("1.0.0", description="Versión del framework")
