"""Domain models for Chunk Separation Analysis.

Models for analyzing the structural (Document Graph) vs semantic (Knowledge Graph)
separation in the knowledge graph, and evaluating chunk separation options.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum


class SubgraphType(str, Enum):
    """Types of subgraphs in the knowledge graph."""
    DOCUMENT_GRAPH = "document_graph"    # Document, Chunk, ExtractedEntity
    KNOWLEDGE_GRAPH = "knowledge_graph"  # Disease, Drug, BusinessConcept, etc.
    BRIDGE = "bridge"                    # Nodes connecting both subgraphs
    UNKNOWN = "unknown"


class ChunkSeparationOption(str, Enum):
    """Options for chunk separation strategy."""
    OPTION_A = "keep_neo4j_with_indexes"      # Add indexes/labels, no migration
    OPTION_B = "move_to_postgresql"            # Dual-write to PostgreSQL
    OPTION_C = "separate_neo4j_database"       # Dedicated RAG database


class ImpactSeverity(str, Enum):
    """Severity levels for service impact."""
    CRITICAL = "critical"  # Service would break
    HIGH = "high"          # Significant degradation
    MEDIUM = "medium"      # Noticeable impact
    LOW = "low"            # Minimal impact


@dataclass
class SubgraphMetrics:
    """Metrics for a specific subgraph (Document or Knowledge)."""
    subgraph_type: SubgraphType
    node_count: int = 0
    relationship_count: int = 0
    node_labels: Dict[str, int] = field(default_factory=dict)
    relationship_types: Dict[str, int] = field(default_factory=dict)
    avg_degree: float = 0.0
    isolated_nodes: int = 0
    percentage_of_total: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "subgraph_type": self.subgraph_type.value,
            "node_count": self.node_count,
            "relationship_count": self.relationship_count,
            "node_labels": self.node_labels,
            "relationship_types": self.relationship_types,
            "avg_degree": round(self.avg_degree, 2),
            "isolated_nodes": self.isolated_nodes,
            "percentage_of_total": round(self.percentage_of_total, 2),
        }


@dataclass
class BridgeNodeMetrics:
    """Metrics for nodes that connect Document Graph to Knowledge Graph."""
    bridge_node_count: int = 0
    bridge_relationship_count: int = 0
    bridge_node_types: Dict[str, int] = field(default_factory=dict)
    bridge_relationship_types: Dict[str, int] = field(default_factory=dict)
    top_bridge_nodes: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "bridge_node_count": self.bridge_node_count,
            "bridge_relationship_count": self.bridge_relationship_count,
            "bridge_node_types": self.bridge_node_types,
            "bridge_relationship_types": self.bridge_relationship_types,
            "top_bridge_nodes": self.top_bridge_nodes[:10],
        }


@dataclass
class CoOccurrencePattern:
    """Entity type co-occurrence within chunks/documents."""
    type_pair: Tuple[str, str]
    co_occurrence_count: int
    avg_confidence: float = 0.0
    sample_documents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type_pair": list(self.type_pair),
            "co_occurrence_count": self.co_occurrence_count,
            "avg_confidence": round(self.avg_confidence, 3),
            "sample_documents": self.sample_documents[:5],
        }


@dataclass
class QueryPathAnalysis:
    """Analysis of common query traversal paths."""
    path_pattern: str
    frequency: int
    avg_traversal_depth: int
    services_using: List[str] = field(default_factory=list)
    estimated_latency_ms: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "path_pattern": self.path_pattern,
            "frequency": self.frequency,
            "avg_traversal_depth": self.avg_traversal_depth,
            "services_using": self.services_using,
            "estimated_latency_ms": round(self.estimated_latency_ms, 2),
        }


@dataclass
class ServiceImpact:
    """Impact of chunk separation on a specific service."""
    service_name: str
    file_path: str
    impact_severity: ImpactSeverity
    affected_queries: List[str] = field(default_factory=list)
    refactoring_required: str = ""
    estimated_effort_hours: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "service_name": self.service_name,
            "file_path": self.file_path,
            "impact_severity": self.impact_severity.value,
            "affected_queries": self.affected_queries,
            "refactoring_required": self.refactoring_required,
            "estimated_effort_hours": self.estimated_effort_hours,
        }


@dataclass
class ChunkSeparationRecommendation:
    """Recommendation for chunk separation strategy."""
    recommended_option: ChunkSeparationOption
    confidence: float
    rationale: List[str] = field(default_factory=list)
    decision_criteria_met: Dict[str, bool] = field(default_factory=dict)
    next_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "recommended_option": self.recommended_option.value,
            "confidence": round(self.confidence, 2),
            "rationale": self.rationale,
            "decision_criteria_met": self.decision_criteria_met,
            "next_steps": self.next_steps,
        }


@dataclass
class ChunkImpactReport:
    """Complete report on chunk separation impact."""
    report_id: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: int = 0

    # Service impacts
    service_impacts: List[ServiceImpact] = field(default_factory=list)

    # Performance estimates
    read_latency_impact: Dict[str, float] = field(default_factory=dict)
    write_latency_impact: Dict[str, float] = field(default_factory=dict)

    # Data integrity
    cross_store_join_complexity: str = "none"  # "none", "simple", "complex"
    consistency_risk: str = "low"  # "low", "medium", "high"

    # Migration estimates
    data_volume_mb: float = 0.0
    estimated_migration_time_hours: float = 0.0
    rollback_complexity: str = "low"

    # Recommendation
    recommendation: Optional[ChunkSeparationRecommendation] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "service_impacts": [s.to_dict() for s in self.service_impacts],
            "read_latency_impact": self.read_latency_impact,
            "write_latency_impact": self.write_latency_impact,
            "cross_store_join_complexity": self.cross_store_join_complexity,
            "consistency_risk": self.consistency_risk,
            "data_volume_mb": round(self.data_volume_mb, 2),
            "estimated_migration_time_hours": round(self.estimated_migration_time_hours, 2),
            "rollback_complexity": self.rollback_complexity,
            "recommendation": self.recommendation.to_dict() if self.recommendation else None,
        }


@dataclass
class ExtendedKGAuditReport:
    """Complete extended KG audit report with subgraph analysis."""
    audit_id: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: int = 0

    # Basic counts (from Phase 0)
    total_entities: int = 0
    total_relationships: int = 0
    total_orphans: int = 0
    orphan_rate: float = 0.0
    ontology_coverage: float = 0.0

    # Subgraph analysis
    document_graph: Optional[SubgraphMetrics] = None
    knowledge_graph: Optional[SubgraphMetrics] = None
    bridge_metrics: Optional[BridgeNodeMetrics] = None

    # Co-occurrence patterns
    co_occurrence_patterns: List[CoOccurrencePattern] = field(default_factory=list)

    # Query path analysis
    query_paths: List[QueryPathAnalysis] = field(default_factory=list)

    # Relationship distribution by subgraph
    relationships_by_subgraph: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Recommendations
    separation_readiness: str = "not_ready"  # "ready", "needs_work", "not_ready"
    identified_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "audit_id": self.audit_id,
            "generated_at": self.generated_at.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships,
            "total_orphans": self.total_orphans,
            "orphan_rate": round(self.orphan_rate, 4),
            "ontology_coverage": round(self.ontology_coverage, 4),
            "document_graph": self.document_graph.to_dict() if self.document_graph else None,
            "knowledge_graph": self.knowledge_graph.to_dict() if self.knowledge_graph else None,
            "bridge_metrics": self.bridge_metrics.to_dict() if self.bridge_metrics else None,
            "co_occurrence_patterns": [p.to_dict() for p in self.co_occurrence_patterns[:20]],
            "query_paths": [p.to_dict() for p in self.query_paths],
            "relationships_by_subgraph": self.relationships_by_subgraph,
            "separation_readiness": self.separation_readiness,
            "identified_issues": self.identified_issues,
            "recommendations": self.recommendations,
        }

    def compute_separation_readiness(self) -> str:
        """Evaluate readiness for chunk separation."""
        issues = 0

        # Check if subgraphs are clearly separated
        if self.bridge_metrics:
            bridge_ratio = self.bridge_metrics.bridge_node_count / max(self.total_entities, 1)
            if bridge_ratio > 0.1:  # >10% bridge nodes
                issues += 1
                self.identified_issues.append(
                    f"High bridge node ratio ({bridge_ratio:.1%}) - subgraphs are tightly coupled"
                )

        # Check Document Graph dominance
        if self.document_graph:
            doc_ratio = self.document_graph.node_count / max(self.total_entities, 1)
            if doc_ratio > 0.7:
                self.identified_issues.append(
                    f"Document Graph dominates ({doc_ratio:.1%}) - separation would significantly reduce Neo4j size"
                )

        # Check co-occurrence complexity
        if len(self.co_occurrence_patterns) > 50:
            issues += 1
            self.identified_issues.append(
                f"High co-occurrence complexity ({len(self.co_occurrence_patterns)} patterns) - cross-store queries may be complex"
            )

        if issues == 0:
            self.separation_readiness = "ready"
        elif issues == 1:
            self.separation_readiness = "needs_work"
        else:
            self.separation_readiness = "not_ready"

        return self.separation_readiness
