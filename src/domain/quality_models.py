"""Document Quality Metrics Models.

Defines quality assessment metrics for RAG document evaluation.
Based on RAGAS, DeepEval, and custom information theory metrics.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class QualityLevel(Enum):
    """Quality classification levels."""
    EXCELLENT = "excellent"     # 0.9+
    GOOD = "good"               # 0.7-0.9
    ACCEPTABLE = "acceptable"   # 0.5-0.7
    POOR = "poor"               # 0.3-0.5
    CRITICAL = "critical"       # <0.3


@dataclass
class ContextualRelevancyScore:
    """Contextual Relevancy & Precision metrics.

    Measures how well retrieved chunks answer potential queries.
    Based on RAGAS context_precision and context_relevancy.
    """
    # Core metrics
    context_precision: float = 0.0  # Fraction of retrieved chunks that are relevant
    context_recall: float = 0.0     # Fraction of relevant info that was retrieved
    context_relevancy: float = 0.0  # How relevant the context is to the query

    # Derived scores
    f1_score: float = 0.0           # Harmonic mean of precision and recall

    # Sample queries used for evaluation
    sample_queries: List[str] = field(default_factory=list)
    query_coverage: Dict[str, float] = field(default_factory=dict)  # Query -> score

    def compute_f1(self) -> float:
        """Compute F1 score from precision and recall."""
        if self.context_precision + self.context_recall == 0:
            return 0.0
        self.f1_score = 2 * (self.context_precision * self.context_recall) / \
                        (self.context_precision + self.context_recall)
        return self.f1_score


@dataclass
class ContextSufficiencyScore:
    """Context Sufficiency metrics.

    Measures whether retrieved context contains enough information
    to answer questions comprehensively.
    """
    # Coverage metrics
    topic_coverage: float = 0.0      # % of expected topics present
    claim_coverage: float = 0.0      # % of claims that can be verified
    completeness: float = 0.0        # Overall content completeness

    # Expected vs found
    expected_topics: List[str] = field(default_factory=list)
    found_topics: List[str] = field(default_factory=list)
    missing_topics: List[str] = field(default_factory=list)

    # Gap analysis
    information_gaps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class InformationDensityScore:
    """Information Density metrics.

    Measures the concentration of useful information per unit of text.
    """
    # Core metrics
    unique_facts_per_chunk: float = 0.0    # Average unique facts per chunk
    redundancy_ratio: float = 0.0          # % of duplicate information
    signal_to_noise: float = 0.0           # Useful info vs filler content

    # Token efficiency
    information_per_token: float = 0.0     # Facts per 100 tokens
    semantic_density: float = 0.0          # Unique concepts per chunk

    # Chunk-level analysis
    chunk_densities: List[float] = field(default_factory=list)
    low_density_chunks: List[str] = field(default_factory=list)  # Chunk IDs
    high_redundancy_chunks: List[str] = field(default_factory=list)


@dataclass
class StructuralClarityScore:
    """Structural Clarity metrics.

    Measures document organization, heading hierarchy, and section coherence.
    """
    # Hierarchy metrics
    heading_hierarchy_score: float = 0.0   # Proper H1 > H2 > H3 nesting
    section_coherence: float = 0.0         # Content matches section headers
    logical_flow: float = 0.0              # Sections follow logical order

    # Structure details
    heading_count: int = 0
    max_depth: int = 0
    orphan_sections: int = 0               # Sections without proper parent

    # Issues found
    hierarchy_violations: List[Dict[str, Any]] = field(default_factory=list)
    incoherent_sections: List[str] = field(default_factory=list)


@dataclass
class EntityDensityScore:
    """Entity Density & Coherence metrics.

    Measures the quality of extractable entities and their relationships.
    """
    # Density metrics
    entities_per_chunk: float = 0.0        # Average entities extracted per chunk
    entity_extraction_rate: float = 0.0    # % of chunks with extractable entities
    relationship_density: float = 0.0      # Relationships per entity

    # Coherence metrics
    entity_consistency: float = 0.0        # Same entity referenced consistently
    cross_reference_score: float = 0.0     # Entities connected across chunks
    ontology_alignment: float = 0.0        # Entities match known ontologies

    # Entity details
    total_entities: int = 0
    unique_entities: int = 0
    total_relationships: int = 0

    # Quality issues
    ambiguous_entities: List[str] = field(default_factory=list)
    orphan_entities: List[str] = field(default_factory=list)  # No relationships


@dataclass
class ChunkingQualityScore:
    """Chunking Quality metrics.

    Measures how well the document was chunked for RAG retrieval.
    Based on HOPE (Holistic Passage Evaluation) framework.
    """
    # HOPE-inspired metrics
    self_containment: float = 0.0          # Chunks are self-explanatory
    boundary_coherence: float = 0.0        # Chunks end at natural boundaries
    context_preservation: float = 0.0      # Important context not split

    # Size distribution
    size_variance: float = 0.0             # Variance in chunk sizes (lower is better)
    optimal_size_ratio: float = 0.0        # % of chunks near optimal size

    # Retrieval readiness
    retrieval_quality: float = 0.0         # Estimated retrieval effectiveness


@dataclass
class DocumentQualityReport:
    """Complete document quality assessment report."""

    # Document identification
    document_id: str
    document_name: str
    assessed_at: datetime = field(default_factory=datetime.now)

    # Individual metric scores
    contextual_relevancy: ContextualRelevancyScore = field(default_factory=ContextualRelevancyScore)
    context_sufficiency: ContextSufficiencyScore = field(default_factory=ContextSufficiencyScore)
    information_density: InformationDensityScore = field(default_factory=InformationDensityScore)
    structural_clarity: StructuralClarityScore = field(default_factory=StructuralClarityScore)
    entity_density: EntityDensityScore = field(default_factory=EntityDensityScore)
    chunking_quality: ChunkingQualityScore = field(default_factory=ChunkingQualityScore)

    # Overall scores
    overall_score: float = 0.0
    quality_level: QualityLevel = QualityLevel.ACCEPTABLE

    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    improvement_priority: List[str] = field(default_factory=list)

    # Metadata
    chunk_count: int = 0
    total_tokens: int = 0
    processing_time_ms: int = 0

    def compute_overall_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Compute weighted overall quality score.

        Args:
            weights: Optional custom weights for each metric category.
                     Default weights prioritize RAG retrieval quality.

        Returns:
            Overall quality score between 0 and 1.
        """
        default_weights = {
            "contextual_relevancy": 0.25,   # Most important for RAG
            "context_sufficiency": 0.20,
            "information_density": 0.15,
            "structural_clarity": 0.15,
            "entity_density": 0.15,
            "chunking_quality": 0.10,
        }
        weights = weights or default_weights

        scores = {
            "contextual_relevancy": self.contextual_relevancy.f1_score,
            "context_sufficiency": self.context_sufficiency.completeness,
            "information_density": self.information_density.signal_to_noise,
            "structural_clarity": self.structural_clarity.section_coherence,
            "entity_density": self.entity_density.entity_consistency,
            "chunking_quality": self.chunking_quality.retrieval_quality,
        }

        self.overall_score = sum(
            scores[k] * weights[k] for k in weights
        )

        # Determine quality level
        if self.overall_score >= 0.9:
            self.quality_level = QualityLevel.EXCELLENT
        elif self.overall_score >= 0.7:
            self.quality_level = QualityLevel.GOOD
        elif self.overall_score >= 0.5:
            self.quality_level = QualityLevel.ACCEPTABLE
        elif self.overall_score >= 0.3:
            self.quality_level = QualityLevel.POOR
        else:
            self.quality_level = QualityLevel.CRITICAL

        return self.overall_score

    def generate_recommendations(self) -> List[str]:
        """Generate improvement recommendations based on scores."""
        recommendations = []

        # Contextual relevancy issues
        if self.contextual_relevancy.f1_score < 0.7:
            if self.contextual_relevancy.context_precision < 0.7:
                recommendations.append(
                    "Improve chunk boundaries to ensure relevant information is grouped together"
                )
            if self.contextual_relevancy.context_recall < 0.7:
                recommendations.append(
                    "Reduce chunk size or add cross-references to improve recall"
                )

        # Sufficiency issues
        if self.context_sufficiency.topic_coverage < 0.8:
            missing = ", ".join(self.context_sufficiency.missing_topics[:3])
            recommendations.append(
                f"Document is missing coverage of topics: {missing}"
            )

        # Density issues
        if self.information_density.redundancy_ratio > 0.3:
            recommendations.append(
                "High redundancy detected - consider deduplication or summarization"
            )
        if self.information_density.unique_facts_per_chunk < 3:
            recommendations.append(
                "Low information density - chunks may be too verbose or lack substance"
            )

        # Structure issues
        if self.structural_clarity.heading_hierarchy_score < 0.7:
            recommendations.append(
                "Fix heading hierarchy (ensure proper H1 > H2 > H3 nesting)"
            )
        if self.structural_clarity.orphan_sections > 0:
            recommendations.append(
                f"Found {self.structural_clarity.orphan_sections} orphan sections without proper headers"
            )

        # Entity issues
        if self.entity_density.entity_extraction_rate < 0.5:
            recommendations.append(
                "Low entity extraction rate - document may lack concrete concepts"
            )
        if len(self.entity_density.ambiguous_entities) > 0:
            recommendations.append(
                f"Resolve ambiguous entity references: {', '.join(self.entity_density.ambiguous_entities[:3])}"
            )

        # Chunking issues
        if self.chunking_quality.boundary_coherence < 0.7:
            recommendations.append(
                "Improve chunk boundaries - many chunks end mid-sentence or mid-thought"
            )

        self.recommendations = recommendations

        # Prioritize based on impact
        self.improvement_priority = sorted(
            recommendations,
            key=lambda r: self._priority_score(r),
            reverse=True
        )[:5]

        return self.recommendations

    def _priority_score(self, recommendation: str) -> float:
        """Score recommendation priority (higher = more important)."""
        priority_keywords = {
            "missing": 0.9,
            "redundancy": 0.8,
            "hierarchy": 0.7,
            "boundary": 0.8,
            "ambiguous": 0.6,
            "extraction": 0.5,
        }

        for keyword, score in priority_keywords.items():
            if keyword in recommendation.lower():
                return score
        return 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "assessed_at": self.assessed_at.isoformat(),
            "overall_score": self.overall_score,
            "quality_level": self.quality_level.value,
            "scores": {
                "contextual_relevancy": {
                    "precision": self.contextual_relevancy.context_precision,
                    "recall": self.contextual_relevancy.context_recall,
                    "f1": self.contextual_relevancy.f1_score,
                },
                "context_sufficiency": {
                    "topic_coverage": self.context_sufficiency.topic_coverage,
                    "completeness": self.context_sufficiency.completeness,
                    "missing_topics": self.context_sufficiency.missing_topics,
                },
                "information_density": {
                    "facts_per_chunk": self.information_density.unique_facts_per_chunk,
                    "redundancy": self.information_density.redundancy_ratio,
                    "signal_to_noise": self.information_density.signal_to_noise,
                },
                "structural_clarity": {
                    "hierarchy_score": self.structural_clarity.heading_hierarchy_score,
                    "section_coherence": self.structural_clarity.section_coherence,
                    "logical_flow": self.structural_clarity.logical_flow,
                },
                "entity_density": {
                    "entities_per_chunk": self.entity_density.entities_per_chunk,
                    "extraction_rate": self.entity_density.entity_extraction_rate,
                    "consistency": self.entity_density.entity_consistency,
                },
                "chunking_quality": {
                    "self_containment": self.chunking_quality.self_containment,
                    "boundary_coherence": self.chunking_quality.boundary_coherence,
                    "retrieval_quality": self.chunking_quality.retrieval_quality,
                },
            },
            "recommendations": self.recommendations,
            "improvement_priority": self.improvement_priority,
            "metadata": {
                "chunk_count": self.chunk_count,
                "total_tokens": self.total_tokens,
                "processing_time_ms": self.processing_time_ms,
            },
        }
