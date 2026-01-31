"""Ontology Quality Metrics Models.

Defines quality assessment metrics for ontology evaluation:
- Ontology Coverage (entity mapping to classes)
- Schema Compliance (required properties per class)
- Taxonomy Coherence (is-a hierarchy)
- Mapping Consistency (type uniformity)
- Semantic Normalization Quality
- Cross-Reference Validity
- Interoperability Score (Schema.org coverage)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum


class OntologyQualityLevel(Enum):
    """Ontology quality classification levels."""
    EXCELLENT = "excellent"     # 0.9+ - Production ready
    GOOD = "good"               # 0.7-0.9 - Minor issues
    ACCEPTABLE = "acceptable"   # 0.5-0.7 - Needs improvement
    POOR = "poor"               # 0.3-0.5 - Significant issues
    CRITICAL = "critical"       # <0.3 - Major restructuring needed


@dataclass
class OntologyCoverageScore:
    """Measures how well entities are mapped to ontology classes.

    High coverage means most entities have proper ontology type assignments.
    """
    # Core metrics
    total_entities: int = 0
    mapped_entities: int = 0           # Entities with ontology class
    unmapped_entities: int = 0         # Entities without ontology mapping
    coverage_ratio: float = 0.0        # mapped / total

    # ODIN coverage
    odin_mapped: int = 0               # Entities mapped to ODIN classes
    odin_coverage: float = 0.0

    # Schema.org coverage (interoperability)
    schema_org_mapped: int = 0         # Entities mapped to Schema.org
    schema_org_coverage: float = 0.0

    # Distribution by class
    class_distribution: Dict[str, int] = field(default_factory=dict)
    unmapped_types: List[str] = field(default_factory=list)  # Types without mapping


@dataclass
class SchemaComplianceScore:
    """Measures compliance with ontology schema requirements.

    Each ontology class has required/optional properties. This tracks
    how well entities conform to their class schemas.
    """
    # Compliance metrics
    total_validated: int = 0
    fully_compliant: int = 0           # All required properties present
    partially_compliant: int = 0       # Some required properties missing
    non_compliant: int = 0             # Critical properties missing

    compliance_ratio: float = 0.0      # fully_compliant / total

    # Property coverage
    avg_required_coverage: float = 0.0   # Avg % of required props present
    avg_optional_coverage: float = 0.0   # Avg % of optional props present

    # Issues by class
    violations_by_class: Dict[str, List[str]] = field(default_factory=dict)
    missing_required: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TaxonomyCoherenceScore:
    """Measures the coherence of taxonomy (is-a) relationships.

    Checks that parent-child relationships follow ontology hierarchy.
    """
    # Hierarchy metrics
    total_relationships: int = 0
    valid_relationships: int = 0       # Follow ontology hierarchy
    invalid_relationships: int = 0     # Violate hierarchy
    coherence_ratio: float = 0.0

    # Hierarchy depth
    max_depth: int = 0
    avg_depth: float = 0.0

    # Orphan detection
    orphan_nodes: int = 0              # Nodes without parent in hierarchy
    disconnected_subgraphs: int = 0    # Isolated clusters

    # Violations
    hierarchy_violations: List[Dict[str, Any]] = field(default_factory=list)
    circular_references: List[str] = field(default_factory=list)


@dataclass
class MappingConsistencyScore:
    """Measures consistency of ontology type assignments.

    Same entity types should always map to same ontology classes.
    """
    # Consistency metrics
    total_types: int = 0
    consistent_types: int = 0          # Always mapped to same class
    inconsistent_types: int = 0        # Multiple different mappings
    consistency_ratio: float = 0.0

    # Mapping ambiguity
    ambiguous_mappings: Dict[str, Set[str]] = field(default_factory=dict)
    one_to_many_mappings: int = 0      # Types with multiple class mappings

    # Recommendations
    suggested_canonical: Dict[str, str] = field(default_factory=dict)


@dataclass
class NormalizationQualityScore:
    """Measures quality of semantic normalization.

    Tracks how well entity names are normalized to canonical forms.
    """
    # Normalization metrics
    total_names: int = 0
    normalized_names: int = 0          # Successfully normalized
    already_canonical: int = 0         # Already in canonical form
    normalization_rate: float = 0.0

    # Abbreviation handling
    abbreviations_expanded: int = 0
    unknown_abbreviations: List[str] = field(default_factory=list)

    # Synonym resolution
    synonyms_resolved: int = 0
    unresolved_synonyms: List[str] = field(default_factory=list)

    # Duplicate detection
    potential_duplicates: List[Dict[str, Any]] = field(default_factory=list)
    deduplication_candidates: int = 0


@dataclass
class CrossReferenceValidityScore:
    """Measures validity of cross-references between ontology-mapped entities.

    Validates that relationships between entities respect their ontology types.
    """
    # Reference metrics
    total_references: int = 0
    valid_references: int = 0          # Respect type constraints
    invalid_references: int = 0        # Violate type constraints
    validity_ratio: float = 0.0

    # Relationship type analysis
    relationships_by_type: Dict[str, int] = field(default_factory=dict)
    invalid_combinations: List[Dict[str, Any]] = field(default_factory=list)

    # Domain constraints
    domain_violations: List[str] = field(default_factory=list)
    range_violations: List[str] = field(default_factory=list)


@dataclass
class InteroperabilityScore:
    """Measures interoperability for external systems.

    Focuses on Schema.org and standard ontology mappings for data exchange.
    """
    # Schema.org coverage
    schema_org_types: int = 0          # Types with Schema.org mapping
    schema_org_properties: int = 0     # Properties with Schema.org mapping
    schema_org_coverage: float = 0.0

    # Standard compliance
    linked_data_ready: bool = False    # Can export as JSON-LD
    sparql_compatible: bool = False    # Can query with SPARQL
    rdf_exportable: bool = False       # Can export as RDF

    # Missing mappings
    missing_schema_types: List[str] = field(default_factory=list)
    missing_property_mappings: List[str] = field(default_factory=list)

    # Data exchange readiness
    exchange_readiness: float = 0.0


@dataclass
class OntologyQualityReport:
    """Complete ontology quality assessment report."""

    # Identification
    assessment_id: str
    ontology_name: str
    assessed_at: datetime = field(default_factory=datetime.now)

    # Individual scores
    coverage: OntologyCoverageScore = field(default_factory=OntologyCoverageScore)
    compliance: SchemaComplianceScore = field(default_factory=SchemaComplianceScore)
    taxonomy: TaxonomyCoherenceScore = field(default_factory=TaxonomyCoherenceScore)
    consistency: MappingConsistencyScore = field(default_factory=MappingConsistencyScore)
    normalization: NormalizationQualityScore = field(default_factory=NormalizationQualityScore)
    cross_reference: CrossReferenceValidityScore = field(default_factory=CrossReferenceValidityScore)
    interoperability: InteroperabilityScore = field(default_factory=InteroperabilityScore)

    # Overall assessment
    overall_score: float = 0.0
    quality_level: OntologyQualityLevel = OntologyQualityLevel.ACCEPTABLE

    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    improvement_priority: List[str] = field(default_factory=list)

    # Metadata
    entity_count: int = 0
    relationship_count: int = 0
    class_count: int = 0
    processing_time_ms: int = 0

    def compute_overall_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Compute weighted overall quality score.

        Args:
            weights: Optional custom weights for each metric category.

        Returns:
            Overall quality score between 0 and 1.
        """
        default_weights = {
            "coverage": 0.25,           # Entity mapping is crucial
            "compliance": 0.20,         # Schema compliance
            "taxonomy": 0.15,           # Hierarchy coherence
            "consistency": 0.15,        # Mapping consistency
            "normalization": 0.10,      # Name normalization
            "cross_reference": 0.10,    # Reference validity
            "interoperability": 0.05,   # External compatibility
        }
        weights = weights or default_weights

        scores = {
            "coverage": self.coverage.coverage_ratio,
            "compliance": self.compliance.compliance_ratio,
            "taxonomy": self.taxonomy.coherence_ratio,
            "consistency": self.consistency.consistency_ratio,
            "normalization": self.normalization.normalization_rate,
            "cross_reference": self.cross_reference.validity_ratio,
            "interoperability": self.interoperability.exchange_readiness,
        }

        self.overall_score = sum(
            scores[k] * weights[k] for k in weights if k in scores
        )

        # Determine quality level
        if self.overall_score >= 0.9:
            self.quality_level = OntologyQualityLevel.EXCELLENT
        elif self.overall_score >= 0.7:
            self.quality_level = OntologyQualityLevel.GOOD
        elif self.overall_score >= 0.5:
            self.quality_level = OntologyQualityLevel.ACCEPTABLE
        elif self.overall_score >= 0.3:
            self.quality_level = OntologyQualityLevel.POOR
        else:
            self.quality_level = OntologyQualityLevel.CRITICAL

        return self.overall_score

    def generate_recommendations(self) -> List[str]:
        """Generate improvement recommendations based on scores."""
        recommendations = []
        critical = []

        # Coverage issues
        if self.coverage.coverage_ratio < 0.8:
            msg = f"Low ontology coverage ({self.coverage.coverage_ratio:.1%}). " \
                  f"{self.coverage.unmapped_entities} entities need type mapping."
            recommendations.append(msg)
            if self.coverage.coverage_ratio < 0.5:
                critical.append(msg)

        if self.coverage.unmapped_types:
            recommendations.append(
                f"Add ontology mappings for types: {', '.join(self.coverage.unmapped_types[:5])}"
            )

        # Compliance issues
        if self.compliance.compliance_ratio < 0.7:
            recommendations.append(
                f"Schema compliance is low ({self.compliance.compliance_ratio:.1%}). "
                f"Add missing required properties."
            )

        if self.compliance.non_compliant > 0:
            critical.append(
                f"{self.compliance.non_compliant} entities are non-compliant with their schema"
            )

        # Taxonomy issues
        if self.taxonomy.coherence_ratio < 0.9:
            recommendations.append(
                f"Fix {self.taxonomy.invalid_relationships} taxonomy hierarchy violations"
            )

        if self.taxonomy.circular_references:
            critical.append(
                f"Circular references detected: {', '.join(self.taxonomy.circular_references[:3])}"
            )

        if self.taxonomy.orphan_nodes > 0:
            recommendations.append(
                f"Connect {self.taxonomy.orphan_nodes} orphan nodes to the hierarchy"
            )

        # Consistency issues
        if self.consistency.consistency_ratio < 0.9:
            recommendations.append(
                f"Resolve {self.consistency.inconsistent_types} inconsistent type mappings"
            )

        # Normalization issues
        if self.normalization.normalization_rate < 0.8:
            recommendations.append(
                f"Normalize {self.normalization.total_names - self.normalization.normalized_names} "
                "entity names to canonical forms"
            )

        if self.normalization.deduplication_candidates > 0:
            recommendations.append(
                f"Review {self.normalization.deduplication_candidates} potential duplicate entities"
            )

        # Cross-reference issues
        if self.cross_reference.validity_ratio < 0.9:
            recommendations.append(
                f"Fix {self.cross_reference.invalid_references} invalid cross-references"
            )

        # Interoperability issues
        if self.interoperability.schema_org_coverage < 0.5:
            recommendations.append(
                "Improve Schema.org coverage for better interoperability"
            )

        self.recommendations = recommendations
        self.critical_issues = critical

        # Prioritize by impact
        self.improvement_priority = critical + [
            r for r in recommendations if r not in critical
        ][:5]

        return self.recommendations

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "assessment_id": self.assessment_id,
            "ontology_name": self.ontology_name,
            "assessed_at": self.assessed_at.isoformat(),
            "overall_score": round(self.overall_score, 3),
            "quality_level": self.quality_level.value,
            "scores": {
                "coverage": {
                    "ratio": self.coverage.coverage_ratio,
                    "total_entities": self.coverage.total_entities,
                    "mapped": self.coverage.mapped_entities,
                    "unmapped": self.coverage.unmapped_entities,
                    "odin_coverage": self.coverage.odin_coverage,
                    "schema_org_coverage": self.coverage.schema_org_coverage,
                },
                "compliance": {
                    "ratio": self.compliance.compliance_ratio,
                    "fully_compliant": self.compliance.fully_compliant,
                    "partially_compliant": self.compliance.partially_compliant,
                    "non_compliant": self.compliance.non_compliant,
                },
                "taxonomy": {
                    "coherence": self.taxonomy.coherence_ratio,
                    "valid_relationships": self.taxonomy.valid_relationships,
                    "invalid_relationships": self.taxonomy.invalid_relationships,
                    "orphans": self.taxonomy.orphan_nodes,
                },
                "consistency": {
                    "ratio": self.consistency.consistency_ratio,
                    "consistent_types": self.consistency.consistent_types,
                    "inconsistent_types": self.consistency.inconsistent_types,
                },
                "normalization": {
                    "rate": self.normalization.normalization_rate,
                    "duplicates": self.normalization.deduplication_candidates,
                },
                "cross_reference": {
                    "validity": self.cross_reference.validity_ratio,
                    "invalid_refs": self.cross_reference.invalid_references,
                },
                "interoperability": {
                    "exchange_readiness": self.interoperability.exchange_readiness,
                    "schema_org_coverage": self.interoperability.schema_org_coverage,
                },
            },
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations[:10],
            "improvement_priority": self.improvement_priority,
            "metadata": {
                "entity_count": self.entity_count,
                "relationship_count": self.relationship_count,
                "class_count": self.class_count,
                "processing_time_ms": self.processing_time_ms,
            },
        }


# --- Ontology Schema Definitions ---

@dataclass
class OntologyClassSchema:
    """Defines the schema for an ontology class."""
    class_name: str
    namespace: str                           # "odin" or "schema.org"
    parent_class: Optional[str] = None       # For hierarchy
    required_properties: List[str] = field(default_factory=list)
    optional_properties: List[str] = field(default_factory=list)
    allowed_relationships: List[str] = field(default_factory=list)
    description: str = ""


# ODIN class schemas
ODIN_SCHEMAS: Dict[str, OntologyClassSchema] = {
    "DataEntity": OntologyClassSchema(
        class_name="DataEntity",
        namespace="odin",
        required_properties=["name", "id"],
        optional_properties=["description", "origin", "layer", "status"],
        allowed_relationships=["hasAttribute", "derivedFrom", "transformsInto"],
        description="Raw data (Table, File)"
    ),
    "Attribute": OntologyClassSchema(
        class_name="Attribute",
        namespace="odin",
        parent_class="DataEntity",
        required_properties=["name", "id"],
        optional_properties=["dataType", "nullable", "description"],
        allowed_relationships=["belongsTo", "references"],
        description="Field or column"
    ),
    "InformationAsset": OntologyClassSchema(
        class_name="InformationAsset",
        namespace="odin",
        required_properties=["name", "id"],
        optional_properties=["description", "owner", "domain"],
        allowed_relationships=["derivedFrom", "belongsToDomain"],
        description="Contextualized data (Report, Dashboard)"
    ),
    "BusinessConcept": OntologyClassSchema(
        class_name="BusinessConcept",
        namespace="odin",
        required_properties=["name", "id"],
        optional_properties=["description", "domain", "confidence"],
        allowed_relationships=["represents", "relatedTo"],
        description="Abstract concept (Customer, Disease)"
    ),
    "Domain": OntologyClassSchema(
        class_name="Domain",
        namespace="odin",
        required_properties=["name", "id"],
        optional_properties=["description", "owner"],
        allowed_relationships=["contains", "subDomainOf"],
        description="Business domain (Sales, Healthcare)"
    ),
    "DataQualityRule": OntologyClassSchema(
        class_name="DataQualityRule",
        namespace="odin",
        required_properties=["name", "id", "rule_type"],
        optional_properties=["description", "severity", "enabled"],
        allowed_relationships=["appliesTo", "triggers"],
        description="Validation rule"
    ),
}

# Schema.org mappings
SCHEMA_ORG_MAPPINGS: Dict[str, str] = {
    "DataEntity": "Dataset",
    "Attribute": "Property",
    "InformationAsset": "Article",
    "BusinessConcept": "DefinedTerm",
    "Domain": "Organization",
    "Person": "Person",
}
