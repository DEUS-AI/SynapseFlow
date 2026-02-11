"""
Modelos para el framework de evaluación de agentes.

Este módulo define los modelos Pydantic usados por el framework de evaluación
para representar snapshots de memoria, diffs, escenarios y resultados.
"""

from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
import unicodedata


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


class AssertionSeverity(str, Enum):
    """Severidad de una aserción."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ========================================
# Memory Entity Models
# ========================================

class MemoryEntity(BaseModel):
    """Entidad de memoria para comparación."""
    name: str
    entity_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    layer: Optional[MemoryLayer] = None
    dikw_layer: Optional[DIKWLayer] = None
    confidence: Optional[float] = None
    observation_count: Optional[int] = None
    first_observed: Optional[datetime] = None
    last_observed: Optional[datetime] = None

    def normalized_key(self) -> str:
        """Retorna una clave normalizada para comparación."""
        return f"{normalize_text(self.name)}:{self.entity_type.lower()}"

    def __hash__(self):
        return hash(self.normalized_key())

    def __eq__(self, other):
        if not isinstance(other, MemoryEntity):
            return False
        return self.normalized_key() == other.normalized_key()


class MemoryRelationship(BaseModel):
    """Relación de memoria para comparación."""
    from_name: str
    to_name: str
    relationship_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    layer: Optional[MemoryLayer] = None

    def normalized_key(self) -> str:
        """Retorna una clave normalizada para comparación."""
        return (
            f"{normalize_text(self.from_name)}"
            f"-[{self.relationship_type.upper()}]->"
            f"{normalize_text(self.to_name)}"
        )

    def __hash__(self):
        return hash(self.normalized_key())

    def __eq__(self, other):
        if not isinstance(other, MemoryRelationship):
            return False
        return self.normalized_key() == other.normalized_key()


class Mem0Memory(BaseModel):
    """Memoria de Mem0."""
    id: str
    text: str
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ========================================
# Layer Snapshots
# ========================================

class RedisLayerSnapshot(BaseModel):
    """Snapshot de la capa Redis."""
    session_data: Dict[str, Any] = Field(default_factory=dict)
    active_sessions: int = 0
    ttl_seconds: Optional[int] = None


class Mem0LayerSnapshot(BaseModel):
    """Snapshot de la capa Mem0."""
    memories: List[Mem0Memory] = Field(default_factory=list)
    memory_count: int = 0


class GraphitiLayerSnapshot(BaseModel):
    """Snapshot de la capa Graphiti/FalkorDB."""
    episodes: List[Dict[str, Any]] = Field(default_factory=list)
    entities: List[MemoryEntity] = Field(default_factory=list)
    edges: List[MemoryRelationship] = Field(default_factory=list)
    episode_count: int = 0


class Neo4jDIKWLayerSnapshot(BaseModel):
    """Snapshot de la capa Neo4j DIKW."""
    perception: List[MemoryEntity] = Field(default_factory=list)
    semantic: List[MemoryEntity] = Field(default_factory=list)
    reasoning: List[MemoryEntity] = Field(default_factory=list)
    application: List[MemoryEntity] = Field(default_factory=list)
    relationships: List[MemoryRelationship] = Field(default_factory=list)


# ========================================
# Complete Memory Snapshot
# ========================================

class MemorySnapshot(BaseModel):
    """Snapshot completo de memoria de un paciente."""
    patient_id: str
    timestamp: datetime
    redis: RedisLayerSnapshot = Field(default_factory=RedisLayerSnapshot)
    mem0: Mem0LayerSnapshot = Field(default_factory=Mem0LayerSnapshot)
    graphiti: GraphitiLayerSnapshot = Field(default_factory=GraphitiLayerSnapshot)
    neo4j_dikw: Neo4jDIKWLayerSnapshot = Field(default_factory=Neo4jDIKWLayerSnapshot)

    def all_entities(self) -> List[MemoryEntity]:
        """Retorna todas las entidades de todas las capas."""
        all_ents = []
        all_ents.extend(self.graphiti.entities)
        all_ents.extend(self.neo4j_dikw.perception)
        all_ents.extend(self.neo4j_dikw.semantic)
        all_ents.extend(self.neo4j_dikw.reasoning)
        all_ents.extend(self.neo4j_dikw.application)
        return all_ents

    def all_relationships(self) -> List[MemoryRelationship]:
        """Retorna todas las relaciones de todas las capas."""
        all_rels = []
        all_rels.extend(self.graphiti.edges)
        all_rels.extend(self.neo4j_dikw.relationships)
        return all_rels

    def get_entity_by_name(
        self,
        name: str,
        entity_type: Optional[str] = None
    ) -> Optional[MemoryEntity]:
        """Busca una entidad por nombre normalizado."""
        normalized_name = normalize_text(name)
        for entity in self.all_entities():
            if normalize_text(entity.name) == normalized_name:
                if entity_type is None or entity.entity_type.lower() == entity_type.lower():
                    return entity
        return None

    def has_entity(
        self,
        name: str,
        entity_type: Optional[str] = None
    ) -> bool:
        """Verifica si existe una entidad con el nombre dado."""
        return self.get_entity_by_name(name, entity_type) is not None


# ========================================
# Memory Diff
# ========================================

class EntityChange(BaseModel):
    """Cambio en una propiedad de entidad."""
    entity: MemoryEntity
    field: str
    old_value: Any
    new_value: Any


class MemoryDiff(BaseModel):
    """Diferencia entre dos snapshots de memoria."""
    entities_added: List[MemoryEntity] = Field(default_factory=list)
    entities_removed: List[MemoryEntity] = Field(default_factory=list)
    entities_modified: List[EntityChange] = Field(default_factory=list)
    relationships_added: List[MemoryRelationship] = Field(default_factory=list)
    relationships_removed: List[MemoryRelationship] = Field(default_factory=list)
    memories_added: List[Mem0Memory] = Field(default_factory=list)
    memories_removed: List[Mem0Memory] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Verifica si hay algún cambio."""
        return bool(
            self.entities_added or
            self.entities_removed or
            self.entities_modified or
            self.relationships_added or
            self.relationships_removed or
            self.memories_added or
            self.memories_removed
        )

    @property
    def entity_changes_count(self) -> int:
        """Número total de cambios de entidades."""
        return (
            len(self.entities_added) +
            len(self.entities_removed) +
            len(self.entities_modified)
        )

    @property
    def relationship_changes_count(self) -> int:
        """Número total de cambios de relaciones."""
        return len(self.relationships_added) + len(self.relationships_removed)

    def get_added_entity_names(self) -> List[str]:
        """Retorna los nombres de las entidades añadidas."""
        return [e.name for e in self.entities_added]

    def get_removed_entity_names(self) -> List[str]:
        """Retorna los nombres de las entidades eliminadas."""
        return [e.name for e in self.entities_removed]

    def has_entity_added(self, name: str, entity_type: Optional[str] = None) -> bool:
        """Verifica si se añadió una entidad con el nombre dado."""
        normalized = normalize_text(name)
        for entity in self.entities_added:
            if normalize_text(entity.name) == normalized:
                if entity_type is None or entity.entity_type.lower() == entity_type.lower():
                    return True
        return False

    def has_entity_removed(self, name: str, entity_type: Optional[str] = None) -> bool:
        """Verifica si se eliminó una entidad con el nombre dado."""
        normalized = normalize_text(name)
        for entity in self.entities_removed:
            if normalize_text(entity.name) == normalized:
                if entity_type is None or entity.entity_type.lower() == entity_type.lower():
                    return True
        return False


# ========================================
# Evaluation Results
# ========================================

class AssertionResult(BaseModel):
    """Resultado de una aserción individual."""
    assertion_type: str
    passed: bool
    reason: str = ""
    details: str = ""
    score: Optional[float] = None
    judge_reasoning: Optional[str] = None
    severity: AssertionSeverity = AssertionSeverity.MEDIUM


class TurnResult(BaseModel):
    """Resultado de evaluar un turno de conversación."""
    turn_number: int
    patient_message: str
    agent_response: str
    response_assertions: List[AssertionResult] = Field(default_factory=list)
    state_assertions: List[AssertionResult] = Field(default_factory=list)
    memory_diff: MemoryDiff = Field(default_factory=MemoryDiff)
    response_time_ms: float = 0.0
    passed: bool = True

    @property
    def all_assertions(self) -> List[AssertionResult]:
        """Retorna todas las aserciones."""
        return self.response_assertions + self.state_assertions

    @property
    def failed_assertions(self) -> List[AssertionResult]:
        """Retorna las aserciones que fallaron."""
        return [a for a in self.all_assertions if not a.passed]


class EvalResult(BaseModel):
    """Resultado completo de evaluar un escenario."""
    scenario_id: str
    scenario_name: str
    category: str
    severity: str
    passed: bool
    turns: List[TurnResult] = Field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: Optional[str] = None

    @property
    def total_assertions(self) -> int:
        """Total de aserciones ejecutadas."""
        return sum(len(t.all_assertions) for t in self.turns)

    @property
    def failed_assertions_count(self) -> int:
        """Total de aserciones fallidas."""
        return sum(len(t.failed_assertions) for t in self.turns)

    @property
    def pass_rate(self) -> float:
        """Tasa de aserciones pasadas."""
        total = self.total_assertions
        if total == 0:
            return 1.0
        return (total - self.failed_assertions_count) / total


# ========================================
# Utility Functions
# ========================================

def normalize_text(text: str) -> str:
    """
    Normaliza texto para comparación consistente.

    - Convierte a minúsculas
    - Elimina espacios extra
    - Elimina acentos/diacríticos
    """
    if not text:
        return ""

    # Lowercase
    text = text.lower().strip()

    # Remove accents/diacritics (important for Spanish)
    # NFD decomposes characters, then we filter out combining marks
    normalized = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

    # Collapse multiple spaces
    text = ' '.join(text.split())

    return text


def entities_match(
    entity1: MemoryEntity,
    entity2: MemoryEntity,
    match_type: bool = True
) -> bool:
    """
    Verifica si dos entidades son equivalentes.

    Args:
        entity1: Primera entidad
        entity2: Segunda entidad
        match_type: Si también comparar entity_type

    Returns:
        True si las entidades matchean
    """
    name_match = normalize_text(entity1.name) == normalize_text(entity2.name)

    if not match_type:
        return name_match

    type_match = entity1.entity_type.lower() == entity2.entity_type.lower()
    return name_match and type_match


def relationships_match(
    rel1: MemoryRelationship,
    rel2: MemoryRelationship
) -> bool:
    """
    Verifica si dos relaciones son equivalentes.
    """
    return (
        normalize_text(rel1.from_name) == normalize_text(rel2.from_name) and
        normalize_text(rel1.to_name) == normalize_text(rel2.to_name) and
        rel1.relationship_type.upper() == rel2.relationship_type.upper()
    )
