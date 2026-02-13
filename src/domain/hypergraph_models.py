"""Domain models for Hypergraph-based Neurosymbolic Bridge.

Implements hypergraph structures that bridge the Document Graph (neural/dense)
with the Knowledge Graph (symbolic/sparse) using FactUnits as hyperedges.

Key Concepts:
- FactUnit: A hyperedge connecting multiple entities from the same context
- ConfidencePropagation: Neural confidence → symbolic certainty
- CoOccurrenceContext: Shared context between entities in a chunk

References:
- Hypergraph Neural Networks (Feng et al., 2019)
- Neurosymbolic AI (Garcez et al., 2022)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib


class FactType(str, Enum):
    """Types of facts that can be extracted from chunks."""
    RELATIONSHIP = "relationship"      # Entity1 relates to Entity2
    ATTRIBUTE = "attribute"            # Entity has property
    CAUSATION = "causation"            # Entity1 causes Entity2
    TREATMENT = "treatment"            # Drug treats Disease
    ASSOCIATION = "association"        # General co-occurrence
    TEMPORAL = "temporal"              # Time-based relationship
    HIERARCHICAL = "hierarchical"      # IS_A, PART_OF relationships


class ConfidenceSource(str, Enum):
    """Sources of confidence scores."""
    EMBEDDING_SIMILARITY = "embedding_similarity"
    EXTRACTION_MODEL = "extraction_model"
    CO_OCCURRENCE = "co_occurrence"
    ONTOLOGY_MATCH = "ontology_match"
    USER_VALIDATION = "user_validation"
    RULE_INFERENCE = "rule_inference"


@dataclass
class EntityMention:
    """An entity mention within a specific context (chunk)."""
    entity_id: str
    entity_name: str
    entity_type: str
    chunk_id: str
    position_start: Optional[int] = None
    position_end: Optional[int] = None
    extraction_confidence: float = 0.7
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "chunk_id": self.chunk_id,
            "position_start": self.position_start,
            "position_end": self.position_end,
            "extraction_confidence": self.extraction_confidence,
        }


@dataclass
class ConfidenceScore:
    """Multi-source confidence score with provenance."""
    value: float
    source: ConfidenceSource
    evidence: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": round(self.value, 4),
            "source": self.source.value,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class FactUnit:
    """A hyperedge representing a factual unit extracted from text.

    Unlike traditional edges (2 nodes), a FactUnit can connect N entities
    that participate in the same factual context. This models the reality
    that facts often involve multiple participants.

    Example:
        "Metformin is used to treat Type 2 Diabetes in patients with obesity"
        → FactUnit connecting: [Metformin, Type2Diabetes, Obesity, Patient]
        → With roles: [TREATMENT, CONDITION, COMORBIDITY, SUBJECT]
    """
    id: str = ""
    fact_type: FactType = FactType.ASSOCIATION
    source_chunk_id: str = ""
    source_document_id: str = ""

    # Participating entities with their roles
    participants: List[EntityMention] = field(default_factory=list)
    participant_roles: Dict[str, str] = field(default_factory=dict)  # entity_id -> role

    # The extracted fact as text
    fact_text: str = ""

    # Multi-source confidence
    confidence_scores: List[ConfidenceScore] = field(default_factory=list)
    aggregate_confidence: float = 0.0

    # Embedding for neural operations
    embedding: Optional[List[float]] = None

    # Provenance
    extraction_method: str = "co_occurrence"
    created_at: datetime = field(default_factory=datetime.now)
    validated: bool = False
    validation_count: int = 0

    # Links to symbolic layer
    inferred_relationships: List[str] = field(default_factory=list)  # Relationship IDs
    ontology_mappings: Dict[str, str] = field(default_factory=dict)  # entity_id -> ontology_class

    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.id:
            # Generate deterministic ID from participants
            participant_ids = sorted([p.entity_id for p in self.participants])
            content = f"{self.source_chunk_id}:{':'.join(participant_ids)}"
            self.id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def add_participant(self, mention: EntityMention, role: str = "participant") -> None:
        """Add an entity participant to this fact."""
        self.participants.append(mention)
        self.participant_roles[mention.entity_id] = role

    def add_confidence(self, score: ConfidenceScore) -> None:
        """Add a confidence score and recompute aggregate."""
        self.confidence_scores.append(score)
        self._compute_aggregate_confidence()

    def _compute_aggregate_confidence(self) -> None:
        """Compute weighted aggregate confidence from multiple sources."""
        if not self.confidence_scores:
            self.aggregate_confidence = 0.0
            return

        # Weight by source reliability
        weights = {
            ConfidenceSource.USER_VALIDATION: 1.0,
            ConfidenceSource.ONTOLOGY_MATCH: 0.9,
            ConfidenceSource.RULE_INFERENCE: 0.85,
            ConfidenceSource.EXTRACTION_MODEL: 0.8,
            ConfidenceSource.EMBEDDING_SIMILARITY: 0.7,
            ConfidenceSource.CO_OCCURRENCE: 0.6,
        }

        weighted_sum = sum(
            score.value * weights.get(score.source, 0.5)
            for score in self.confidence_scores
        )
        total_weight = sum(
            weights.get(score.source, 0.5)
            for score in self.confidence_scores
        )

        self.aggregate_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0

    def get_entity_pairs(self) -> List[Tuple[EntityMention, EntityMention]]:
        """Get all entity pairs for relationship extraction."""
        pairs = []
        for i, e1 in enumerate(self.participants):
            for e2 in self.participants[i + 1:]:
                pairs.append((e1, e2))
        return pairs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "fact_type": self.fact_type.value,
            "source_chunk_id": self.source_chunk_id,
            "source_document_id": self.source_document_id,
            "participants": [p.to_dict() for p in self.participants],
            "participant_roles": self.participant_roles,
            "fact_text": self.fact_text,
            "confidence_scores": [c.to_dict() for c in self.confidence_scores],
            "aggregate_confidence": round(self.aggregate_confidence, 4),
            "extraction_method": self.extraction_method,
            "created_at": self.created_at.isoformat(),
            "validated": self.validated,
            "inferred_relationships": self.inferred_relationships,
            "ontology_mappings": self.ontology_mappings,
        }

    def to_neo4j_properties(self) -> Dict[str, Any]:
        """Convert to Neo4j node properties."""
        return {
            "id": self.id,
            "fact_type": self.fact_type.value,
            "source_chunk_id": self.source_chunk_id,
            "source_document_id": self.source_document_id,
            "fact_text": self.fact_text[:500],  # Truncate for storage
            "aggregate_confidence": self.aggregate_confidence,
            "extraction_method": self.extraction_method,
            "participant_count": len(self.participants),
            "validated": self.validated,
            "validation_count": self.validation_count,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HyperEdge:
    """A generalized hyperedge connecting a FactUnit to its participants.

    This represents the N-ary relationship in Neo4j using an intermediate node pattern:

    (e1:Entity)──┐
    (e2:Entity)──┼──[:PARTICIPATES_IN]──>(f:FactUnit)
    (e3:Entity)──┘

    The FactUnit node acts as the hyperedge, and PARTICIPATES_IN edges
    connect entities to their shared context.
    """
    fact_unit_id: str
    entity_id: str
    role: str = "participant"
    position_in_fact: int = 0
    confidence: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fact_unit_id": self.fact_unit_id,
            "entity_id": self.entity_id,
            "role": self.role,
            "position_in_fact": self.position_in_fact,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class NeurosymbolicLink:
    """A link between neural (embedding) and symbolic (ontology) representations.

    This bridges:
    - Neural: embedding vectors, similarity scores, attention weights
    - Symbolic: ontology classes, logical rules, constraints
    """
    entity_id: str
    entity_name: str

    # Neural representation
    embedding: Optional[List[float]] = None
    embedding_model: str = "text-embedding-3-small"
    cluster_id: Optional[str] = None

    # Symbolic representation
    ontology_class: Optional[str] = None
    ontology_domain: str = "unknown"
    dikw_layer: str = "PERCEPTION"
    external_ids: Dict[str, str] = field(default_factory=dict)  # ICD-10, SNOMED, etc.

    # Bridge metrics
    embedding_ontology_alignment: float = 0.0  # How well embedding matches ontology
    symbolic_coverage: float = 0.0  # % of entity properties covered by ontology

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "embedding_model": self.embedding_model,
            "cluster_id": self.cluster_id,
            "ontology_class": self.ontology_class,
            "ontology_domain": self.ontology_domain,
            "dikw_layer": self.dikw_layer,
            "external_ids": self.external_ids,
            "embedding_ontology_alignment": round(self.embedding_ontology_alignment, 4),
            "symbolic_coverage": round(self.symbolic_coverage, 4),
        }


@dataclass
class CoOccurrenceContext:
    """Context for entity co-occurrence within a chunk.

    Used to determine if co-occurring entities should form a FactUnit.
    """
    chunk_id: str
    document_id: str
    entities: List[EntityMention] = field(default_factory=list)
    chunk_text: str = ""
    chunk_embedding: Optional[List[float]] = None

    # Co-occurrence statistics
    entity_count: int = 0
    type_diversity: int = 0  # Number of unique entity types
    avg_extraction_confidence: float = 0.0

    # Derived signals
    is_fact_candidate: bool = False
    suggested_fact_type: Optional[FactType] = None

    def analyze(self) -> None:
        """Analyze the co-occurrence context."""
        self.entity_count = len(self.entities)
        self.type_diversity = len(set(e.entity_type for e in self.entities))

        if self.entities:
            self.avg_extraction_confidence = sum(
                e.extraction_confidence for e in self.entities
            ) / len(self.entities)

        # Determine if this is a fact candidate
        # At least 2 entities with reasonable confidence
        self.is_fact_candidate = (
            self.entity_count >= 2 and
            self.avg_extraction_confidence >= 0.6 and
            self.type_diversity >= 1
        )

        # Suggest fact type based on entity types
        self._suggest_fact_type()

    def _suggest_fact_type(self) -> None:
        """Suggest a fact type based on participating entity types."""
        types = set(e.entity_type.lower() for e in self.entities)

        if {"drug", "disease"} & types and {"treatment", "medication"} & types:
            self.suggested_fact_type = FactType.TREATMENT
        elif {"cause", "effect"} & types or "causes" in self.chunk_text.lower():
            self.suggested_fact_type = FactType.CAUSATION
        elif self.type_diversity == 1:
            self.suggested_fact_type = FactType.HIERARCHICAL
        else:
            self.suggested_fact_type = FactType.ASSOCIATION

    def to_fact_unit(self) -> Optional[FactUnit]:
        """Convert to a FactUnit if this is a valid fact candidate."""
        if not self.is_fact_candidate:
            return None

        fact = FactUnit(
            fact_type=self.suggested_fact_type or FactType.ASSOCIATION,
            source_chunk_id=self.chunk_id,
            source_document_id=self.document_id,
            participants=self.entities.copy(),
            fact_text=self.chunk_text[:200],
            extraction_method="co_occurrence",
        )

        # Add co-occurrence confidence
        fact.add_confidence(ConfidenceScore(
            value=self.avg_extraction_confidence,
            source=ConfidenceSource.CO_OCCURRENCE,
            evidence=f"Co-occurrence of {self.entity_count} entities in chunk",
        ))

        return fact

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "entities": [e.to_dict() for e in self.entities],
            "entity_count": self.entity_count,
            "type_diversity": self.type_diversity,
            "avg_extraction_confidence": round(self.avg_extraction_confidence, 4),
            "is_fact_candidate": self.is_fact_candidate,
            "suggested_fact_type": self.suggested_fact_type.value if self.suggested_fact_type else None,
        }


@dataclass
class BridgeStatistics:
    """Statistics about the neurosymbolic bridge layer."""
    total_fact_units: int = 0
    total_hyperedges: int = 0
    total_neurosymbolic_links: int = 0

    # Coverage
    entities_with_facts: int = 0
    entities_with_ontology: int = 0
    entities_with_embeddings: int = 0

    # Quality
    avg_fact_confidence: float = 0.0
    validated_facts_ratio: float = 0.0
    ontology_alignment_score: float = 0.0

    # Distribution
    facts_by_type: Dict[str, int] = field(default_factory=dict)
    facts_by_source: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_fact_units": self.total_fact_units,
            "total_hyperedges": self.total_hyperedges,
            "total_neurosymbolic_links": self.total_neurosymbolic_links,
            "entities_with_facts": self.entities_with_facts,
            "entities_with_ontology": self.entities_with_ontology,
            "entities_with_embeddings": self.entities_with_embeddings,
            "avg_fact_confidence": round(self.avg_fact_confidence, 4),
            "validated_facts_ratio": round(self.validated_facts_ratio, 4),
            "ontology_alignment_score": round(self.ontology_alignment_score, 4),
            "facts_by_type": self.facts_by_type,
            "facts_by_source": self.facts_by_source,
        }


# ─── HyperNetX Analytics Result Models ──────────────────────────────


@dataclass
class CentralityResult:
    """Centrality score for a single entity in the hypergraph."""
    entity_id: str
    entity_name: str
    entity_type: str
    centrality_score: float
    participating_fact_count: int


@dataclass
class CommunityResult:
    """A detected community of related entities."""
    community_id: int
    member_entity_ids: List[str]
    member_count: int
    dominant_types: List[str]
    modularity_contribution: float


@dataclass
class CommunityDetectionResult:
    """Full community detection output."""
    total_communities: int
    overall_modularity: float
    communities: List[CommunityResult] = field(default_factory=list)


@dataclass
class ConnectivityComponent:
    """A single s-connected component."""
    component_id: int
    size: int
    entity_ids: List[str]
    is_knowledge_island: bool = False  # True if size < 3


@dataclass
class ConnectivityResult:
    """Connectivity analysis at a specific s value."""
    s_value: int
    component_count: int
    components: List[ConnectivityComponent] = field(default_factory=list)


@dataclass
class DistanceResult:
    """Distance from a source entity to another entity."""
    entity_id: str
    entity_name: str
    distance: float
    reachable: bool = True


@dataclass
class TopologicalSummary:
    """Topological summary of the hypergraph."""
    node_count: int
    edge_count: int
    density: float
    avg_edge_size: float
    max_edge_size: int
    avg_node_degree: float
    diameter: Optional[int] = None


@dataclass
class HypergraphDiff:
    """Diff between two hypergraph snapshots."""
    added_edges: List[str] = field(default_factory=list)
    removed_edges: List[str] = field(default_factory=list)
    added_nodes: List[str] = field(default_factory=list)
    removed_nodes: List[str] = field(default_factory=list)
    modified_edges: List[str] = field(default_factory=list)
