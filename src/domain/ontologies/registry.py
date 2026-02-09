"""Unified Ontology Registry.

Provides a single access point for all ODIN domain extensions.
Combines data architecture and medical ontologies into a unified registry
while maintaining domain separation.

Usage:
    from domain.ontologies.registry import (
        get_ontology_config,
        is_known_type,
        resolve_entity_type,
        UNIFIED_ONTOLOGY_REGISTRY,
    )

    # Works transparently across all domains
    config = get_ontology_config("Disease")      # -> medical extension
    config = get_ontology_config("DataEntity")   # -> data architecture
    config = get_ontology_config("table")        # -> data architecture (with alias)
"""

from typing import Dict, List, Any, Optional, Set
from enum import Enum

# Import core ODIN
from domain.ontologies.odin import ODIN

# Import medical extension
from domain.ontologies.odin_medical import (
    ODINMedical,
    MEDICAL_ONTOLOGY_REGISTRY,
    MEDICAL_TYPE_ALIASES,
    MedicalOntologySystem,
    resolve_medical_type,
    get_medical_ontology_config,
    is_medical_type,
)


class OntologyDomain(str, Enum):
    """Available ontology domains."""
    DATA_ARCHITECTURE = "data_architecture"
    MEDICAL = "medical"
    UNKNOWN = "unknown"


# ========================================
# Data Architecture Ontology Registry
# ========================================
# Extracted from the current odin.py usage patterns

DATA_ONTOLOGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    # PERCEPTION Layer - Raw data structures and sources
    "table": {
        "odin_class": ODIN.DATA_ENTITY,
        "layer": "PERCEPTION",
        "parent_type": "data_entity",
        "auto_relationships": ["HAS_ATTRIBUTE", "TRANSFORMS_INTO", "BELONGS_TO_DOMAIN"],
        "external_systems": ["schema.org:Dataset"],
        "hierarchy_path": ["data_entity", "table"],
        "confidence_threshold": 0.7,
    },
    "file": {
        "odin_class": ODIN.DATA_ENTITY,
        "layer": "PERCEPTION",
        "parent_type": "data_entity",
        "auto_relationships": ["HAS_ATTRIBUTE", "DERIVED_FROM"],
        "external_systems": ["schema.org:Dataset"],
        "hierarchy_path": ["data_entity", "file"],
        "confidence_threshold": 0.7,
    },
    "column": {
        "odin_class": ODIN.ATTRIBUTE,
        "layer": "PERCEPTION",
        "parent_type": "attribute",
        "auto_relationships": ["BELONGS_TO"],
        "external_systems": ["schema.org:Property"],
        "hierarchy_path": ["attribute", "column"],
        "confidence_threshold": 0.7,
    },
    "field": {
        "odin_class": ODIN.ATTRIBUTE,
        "layer": "PERCEPTION",
        "parent_type": "attribute",
        "auto_relationships": ["BELONGS_TO"],
        "external_systems": ["schema.org:Property"],
        "hierarchy_path": ["attribute", "field"],
        "confidence_threshold": 0.7,
    },
    "database": {
        "odin_class": ODIN.DATA_ENTITY,
        "layer": "PERCEPTION",
        "parent_type": "data_entity",
        "auto_relationships": ["CONTAINS", "HOSTS", "BELONGS_TO_DOMAIN"],
        "external_systems": ["schema.org:Dataset"],
        "hierarchy_path": ["data_entity", "database"],
        "confidence_threshold": 0.7,
    },
    "schema": {
        "odin_class": ODIN.DATA_ENTITY,
        "layer": "PERCEPTION",
        "parent_type": "data_entity",
        "auto_relationships": ["CONTAINS", "BELONGS_TO"],
        "external_systems": ["schema.org:Dataset"],
        "hierarchy_path": ["data_entity", "schema"],
        "confidence_threshold": 0.7,
    },
    "system": {
        "odin_class": ODIN.DATA_ENTITY,
        "layer": "PERCEPTION",
        "parent_type": "data_entity",
        "auto_relationships": ["CONTAINS", "HOSTS", "PRODUCES"],
        "external_systems": ["schema.org:SoftwareApplication"],
        "hierarchy_path": ["data_entity", "system"],
        "confidence_threshold": 0.7,
    },

    # SEMANTIC Layer - Validated concepts with business meaning
    "report": {
        "odin_class": ODIN.INFORMATION_ASSET,
        "layer": "SEMANTIC",
        "parent_type": "information_asset",
        "auto_relationships": ["DERIVED_FROM", "REPRESENTS"],
        "external_systems": ["schema.org:Article"],
        "hierarchy_path": ["information_asset", "report"],
        "confidence_threshold": 0.85,
    },
    "dashboard": {
        "odin_class": ODIN.INFORMATION_ASSET,
        "layer": "SEMANTIC",
        "parent_type": "information_asset",
        "auto_relationships": ["DERIVED_FROM", "REPRESENTS"],
        "external_systems": ["schema.org:Article"],
        "hierarchy_path": ["information_asset", "dashboard"],
        "confidence_threshold": 0.85,
    },
    "domain": {
        "odin_class": ODIN.DOMAIN,
        "layer": "SEMANTIC",
        "parent_type": "domain",
        "auto_relationships": ["BELONGS_TO_DOMAIN"],
        "external_systems": ["schema.org:Organization"],
        "hierarchy_path": ["domain"],
        "confidence_threshold": 0.85,
    },
    "data_product": {
        "odin_class": ODIN.INFORMATION_ASSET,
        "layer": "SEMANTIC",
        "parent_type": "information_asset",
        "auto_relationships": ["DERIVED_FROM", "REPRESENTS", "PRODUCES", "CONSUMES"],
        "external_systems": ["schema.org:Dataset"],
        "hierarchy_path": ["information_asset", "data_product"],
        "confidence_threshold": 0.85,
    },
    "person": {
        "odin_class": ODIN.DOMAIN,
        "layer": "SEMANTIC",
        "parent_type": "stakeholder",
        "auto_relationships": ["OWNS", "MANAGES", "RESPONSIBLE_FOR", "ASSOCIATED_WITH"],
        "external_systems": ["schema.org:Person"],
        "hierarchy_path": ["stakeholder", "person"],
        "confidence_threshold": 0.85,
    },
    "team": {
        "odin_class": ODIN.DOMAIN,
        "layer": "SEMANTIC",
        "parent_type": "stakeholder",
        "auto_relationships": ["OWNS", "MANAGES", "RESPONSIBLE_FOR"],
        "external_systems": ["schema.org:Organization"],
        "hierarchy_path": ["stakeholder", "team"],
        "confidence_threshold": 0.85,
    },

    # REASONING Layer - Inferred knowledge and business rules
    "concept": {
        "odin_class": ODIN.BUSINESS_CONCEPT,
        "layer": "REASONING",
        "parent_type": "business_concept",
        "auto_relationships": ["REPRESENTS", "RELATED_TO"],
        "external_systems": ["schema.org:DefinedTerm"],
        "hierarchy_path": ["business_concept", "concept"],
        "confidence_threshold": 0.9,
    },
    "business_concept": {
        "odin_class": ODIN.BUSINESS_CONCEPT,
        "layer": "REASONING",
        "parent_type": "business_concept",
        "auto_relationships": ["REPRESENTS", "RELATED_TO"],
        "external_systems": ["schema.org:DefinedTerm"],
        "hierarchy_path": ["business_concept"],
        "confidence_threshold": 0.9,
    },
    "rule": {
        "odin_class": ODIN.DATA_QUALITY_RULE,
        "layer": "REASONING",
        "parent_type": "quality_rule",
        "auto_relationships": ["APPLIES_TO", "VALIDATES"],
        "external_systems": [],
        "hierarchy_path": ["quality_rule", "rule"],
        "confidence_threshold": 0.9,
    },
    "data_quality_rule": {
        "odin_class": ODIN.DATA_QUALITY_RULE,
        "layer": "REASONING",
        "parent_type": "quality_rule",
        "auto_relationships": ["APPLIES_TO", "VALIDATES"],
        "external_systems": [],
        "hierarchy_path": ["quality_rule"],
        "confidence_threshold": 0.9,
    },
    "process": {
        "odin_class": ODIN.BUSINESS_CONCEPT,
        "layer": "REASONING",
        "parent_type": "business_concept",
        "auto_relationships": ["TRANSFORMS", "USES", "PRODUCES", "CONSUMES"],
        "external_systems": ["schema.org:Action"],
        "hierarchy_path": ["business_concept", "process"],
        "confidence_threshold": 0.9,
    },
    "pipeline": {
        "odin_class": ODIN.BUSINESS_CONCEPT,
        "layer": "REASONING",
        "parent_type": "business_concept",
        "auto_relationships": ["TRANSFORMS", "USES", "PRODUCES", "CONTAINS"],
        "external_systems": [],
        "hierarchy_path": ["business_concept", "pipeline"],
        "confidence_threshold": 0.9,
    },
    "workflow": {
        "odin_class": ODIN.BUSINESS_CONCEPT,
        "layer": "REASONING",
        "parent_type": "business_concept",
        "auto_relationships": ["TRANSFORMS", "USES", "PRODUCES", "CONTAINS"],
        "external_systems": [],
        "hierarchy_path": ["business_concept", "workflow"],
        "confidence_threshold": 0.9,
    },

    # APPLICATION Layer - Query patterns, cached results, operational data
    "score": {
        "odin_class": ODIN.DATA_QUALITY_SCORE,
        "layer": "APPLICATION",
        "parent_type": "quality_score",
        "auto_relationships": ["HAS_QUALITY_SCORE"],
        "external_systems": [],
        "hierarchy_path": ["quality_score", "score"],
        "confidence_threshold": 0.95,
    },
    "usage": {
        "odin_class": ODIN.USAGE_STATS,
        "layer": "APPLICATION",
        "parent_type": "usage_stats",
        "auto_relationships": ["USED_BY"],
        "external_systems": [],
        "hierarchy_path": ["usage_stats", "usage"],
        "confidence_threshold": 0.95,
    },
    "decision": {
        "odin_class": ODIN.DECISION,
        "layer": "APPLICATION",
        "parent_type": "decision",
        "auto_relationships": ["BASED_ON", "LEADS_TO"],
        "external_systems": [],
        "hierarchy_path": ["decision"],
        "confidence_threshold": 0.95,
    },
    "metric": {
        "odin_class": ODIN.DATA_QUALITY_SCORE,
        "layer": "APPLICATION",
        "parent_type": "quality_score",
        "auto_relationships": ["MEASURES", "DERIVED_FROM", "APPLIES_TO"],
        "external_systems": [],
        "hierarchy_path": ["quality_score", "metric"],
        "confidence_threshold": 0.95,
    },
    "kpi": {
        "odin_class": ODIN.DATA_QUALITY_SCORE,
        "layer": "APPLICATION",
        "parent_type": "quality_score",
        "auto_relationships": ["MEASURES", "DERIVED_FROM", "APPLIES_TO"],
        "external_systems": [],
        "hierarchy_path": ["quality_score", "kpi"],
        "confidence_threshold": 0.95,
    },
    "policy": {
        "odin_class": ODIN.DATA_QUALITY_RULE,
        "layer": "APPLICATION",
        "parent_type": "governance",
        "auto_relationships": ["APPLIES_TO", "GOVERNS", "ENFORCES"],
        "external_systems": [],
        "hierarchy_path": ["governance", "policy"],
        "confidence_threshold": 0.95,
    },
    "sla": {
        "odin_class": ODIN.DATA_QUALITY_RULE,
        "layer": "APPLICATION",
        "parent_type": "governance",
        "auto_relationships": ["APPLIES_TO", "GOVERNS", "MEASURES"],
        "external_systems": [],
        "hierarchy_path": ["governance", "sla"],
        "confidence_threshold": 0.95,
    },
}

# Data architecture type aliases - comprehensive normalization
DATA_TYPE_ALIASES: Dict[str, str] = {
    # Table/Entity aliases
    "tables": "table",
    "dataentity": "table",
    "data_entity": "table",
    "entity": "table",
    "entities": "table",

    # File aliases
    "files": "file",

    # Column/Field aliases
    "columns": "column",
    "fields": "field",
    "attribute": "field",
    "attributes": "field",

    # Database/Schema aliases
    "databases": "database",
    "db": "database",
    "schemas": "schema",

    # System aliases
    "systems": "system",
    "application": "system",
    "applications": "system",
    "service": "system",
    "services": "system",

    # Report/Dashboard aliases
    "reports": "report",
    "dashboards": "dashboard",

    # Domain aliases
    "domains": "domain",
    "business_domain": "domain",
    "businessdomain": "domain",

    # Data Product aliases (critical fix)
    "data_product": "data_product",
    "dataproduct": "data_product",
    "data product": "data_product",
    "product": "data_product",
    "products": "data_product",
    "data_products": "data_product",

    # Person/Stakeholder aliases (critical fix)
    "people": "person",
    "persons": "person",
    "user": "person",
    "users": "person",
    "owner": "person",
    "owners": "person",
    "stakeholder": "person",
    "stakeholders": "person",
    "steward": "person",
    "stewards": "person",
    "data_owner": "person",
    "data_steward": "person",

    # Team aliases
    "teams": "team",
    "group": "team",
    "groups": "team",
    "department": "team",
    "departments": "team",

    # Concept aliases (critical fix - BusinessConcept normalization)
    "concepts": "concept",
    "businessconcept": "business_concept",
    "business concept": "business_concept",
    "business_concepts": "business_concept",
    "businessconcepts": "business_concept",

    # Process aliases
    "processes": "process",
    "etl": "process",
    "job": "process",
    "jobs": "process",
    "task": "process",
    "tasks": "process",

    # Pipeline/Workflow aliases
    "pipelines": "pipeline",
    "data_pipeline": "pipeline",
    "datapipeline": "pipeline",
    "workflows": "workflow",
    "flow": "workflow",
    "flows": "workflow",

    # Rule aliases
    "rules": "rule",
    "qualityrule": "data_quality_rule",
    "quality_rule": "data_quality_rule",
    "validation_rule": "data_quality_rule",
    "validationrule": "data_quality_rule",

    # Score/Metric aliases
    "scores": "score",
    "qualityscore": "score",
    "quality_score": "score",
    "metrics": "metric",
    "kpis": "kpi",
    "indicator": "kpi",
    "indicators": "kpi",
    "measure": "metric",
    "measures": "metric",

    # Usage aliases
    "usagestats": "usage",
    "usage_stats": "usage",
    "statistics": "usage",

    # Decision aliases
    "decisions": "decision",

    # Policy/SLA aliases
    "policies": "policy",
    "governance": "policy",
    "slas": "sla",
    "agreement": "sla",
    "agreements": "sla",
}


# ========================================
# Unified Registry
# ========================================

# Merge all registries
UNIFIED_ONTOLOGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    **DATA_ONTOLOGY_REGISTRY,
    **MEDICAL_ONTOLOGY_REGISTRY,
}

# Merge all aliases
UNIFIED_TYPE_ALIASES: Dict[str, str] = {
    **DATA_TYPE_ALIASES,
    **MEDICAL_TYPE_ALIASES,
}


def resolve_entity_type(raw_type: str) -> str:
    """Normalize and resolve an entity type to its canonical form.

    Works across all ontology domains with robust normalization.

    Args:
        raw_type: Raw entity type string (e.g., "Medical Condition", "tables", "BusinessConcept")

    Returns:
        Canonical type string (e.g., "disease", "table", "business_concept")
    """
    if not raw_type:
        return "unknown"

    # Step 1: Basic normalization - lowercase, trim, replace delimiters
    normalized = raw_type.lower().strip().replace("-", "_").replace(" ", "_")

    # Step 2: Remove special characters (keep alphanumeric and underscore)
    normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')

    # Step 3: Remove consecutive underscores
    while "__" in normalized:
        normalized = normalized.replace("__", "_")

    # Step 4: Remove leading/trailing underscores
    normalized = normalized.strip("_")

    if not normalized:
        return "unknown"

    # Step 5: Check alias first
    if normalized in UNIFIED_TYPE_ALIASES:
        return UNIFIED_TYPE_ALIASES[normalized]

    # Step 6: Check if already in registry
    if normalized in UNIFIED_ONTOLOGY_REGISTRY:
        return normalized

    # Step 7: Try singular form (remove trailing 's')
    if normalized.endswith('s') and len(normalized) > 2:
        singular = normalized[:-1]
        if singular in UNIFIED_TYPE_ALIASES:
            return UNIFIED_TYPE_ALIASES[singular]
        if singular in UNIFIED_ONTOLOGY_REGISTRY:
            return singular

    # Step 8: Try common suffix variations
    # e.g., "extracted_entity" -> "entity"
    for suffix in ["_entity", "_concept", "_type"]:
        if normalized.endswith(suffix):
            base = normalized[:-len(suffix)]
            if base in UNIFIED_ONTOLOGY_REGISTRY:
                return base
            if base in UNIFIED_TYPE_ALIASES:
                return UNIFIED_TYPE_ALIASES[base]

    return normalized


def get_ontology_config(entity_type: str) -> Optional[Dict[str, Any]]:
    """Get ontology configuration for any entity type.

    Searches across all registered ontology domains.

    Args:
        entity_type: Entity type (raw or canonical)

    Returns:
        Ontology configuration dict with:
        - odin_class: ODIN class constant
        - layer: DIKW layer (PERCEPTION, SEMANTIC, REASONING, APPLICATION)
        - parent_type: Parent in hierarchy
        - auto_relationships: Valid relationship types for this entity
        - external_systems: External ontology systems (SNOMED, ICD-10, etc.)
        - hierarchy_path: Path in type hierarchy
        - confidence_threshold: Minimum confidence for this layer

        Returns None if type is not recognized.
    """
    resolved = resolve_entity_type(entity_type)
    return UNIFIED_ONTOLOGY_REGISTRY.get(resolved)


def is_known_type(entity_type: str) -> bool:
    """Check if an entity type is recognized in any ontology domain.

    Args:
        entity_type: Entity type to check

    Returns:
        True if the type is registered in any domain
    """
    resolved = resolve_entity_type(entity_type)
    return resolved in UNIFIED_ONTOLOGY_REGISTRY


def get_domain_for_type(entity_type: str) -> OntologyDomain:
    """Determine which ontology domain an entity type belongs to.

    Args:
        entity_type: Entity type to check

    Returns:
        OntologyDomain enum value
    """
    resolved = resolve_entity_type(entity_type)

    if resolved in MEDICAL_ONTOLOGY_REGISTRY:
        return OntologyDomain.MEDICAL
    elif resolved in DATA_ONTOLOGY_REGISTRY:
        return OntologyDomain.DATA_ARCHITECTURE
    else:
        return OntologyDomain.UNKNOWN


def get_layer_for_type(entity_type: str) -> Optional[str]:
    """Get the DIKW layer for an entity type.

    Args:
        entity_type: Entity type

    Returns:
        Layer name (PERCEPTION, SEMANTIC, REASONING, APPLICATION) or None
    """
    config = get_ontology_config(entity_type)
    return config.get("layer") if config else None


def get_auto_relationships(entity_type: str) -> List[str]:
    """Get valid automatic relationship types for an entity type.

    Args:
        entity_type: Entity type

    Returns:
        List of valid relationship type strings
    """
    config = get_ontology_config(entity_type)
    return config.get("auto_relationships", []) if config else []


def get_confidence_threshold(entity_type: str) -> float:
    """Get the confidence threshold for an entity type's layer.

    Args:
        entity_type: Entity type

    Returns:
        Minimum confidence threshold (default 0.7)
    """
    config = get_ontology_config(entity_type)
    return config.get("confidence_threshold", 0.7) if config else 0.7


def get_hierarchy_path(entity_type: str) -> List[str]:
    """Get the hierarchy path for an entity type.

    Args:
        entity_type: Entity type

    Returns:
        List representing path from root to type
    """
    config = get_ontology_config(entity_type)
    return config.get("hierarchy_path", []) if config else []


def get_all_types_for_layer(layer: str) -> List[str]:
    """Get all entity types assigned to a specific DIKW layer.

    Args:
        layer: Layer name (PERCEPTION, SEMANTIC, REASONING, APPLICATION)

    Returns:
        List of canonical entity type names
    """
    return [
        entity_type
        for entity_type, config in UNIFIED_ONTOLOGY_REGISTRY.items()
        if config.get("layer") == layer
    ]


def get_all_types_for_domain(domain: OntologyDomain) -> List[str]:
    """Get all entity types for a specific ontology domain.

    Args:
        domain: Ontology domain

    Returns:
        List of canonical entity type names
    """
    if domain == OntologyDomain.MEDICAL:
        return list(MEDICAL_ONTOLOGY_REGISTRY.keys())
    elif domain == OntologyDomain.DATA_ARCHITECTURE:
        return list(DATA_ONTOLOGY_REGISTRY.keys())
    else:
        return []


def get_unmapped_type_config() -> Dict[str, Any]:
    """Get default configuration for unmapped entity types.

    Returns:
        Default config for unknown types
    """
    return {
        "odin_class": "Unknown",
        "layer": "PERCEPTION",
        "parent_type": "unknown",
        "auto_relationships": ["RELATED_TO"],
        "external_systems": [],
        "hierarchy_path": ["unknown"],
        "confidence_threshold": 0.5,
    }


def suggest_type_mapping(unknown_type: str) -> List[Dict[str, Any]]:
    """Suggest potential type mappings for an unknown type.

    Uses string similarity to suggest the most likely canonical types.

    Args:
        unknown_type: The unknown type string

    Returns:
        List of suggestions with type, domain, and similarity score
    """
    from difflib import SequenceMatcher

    normalized = unknown_type.lower().strip().replace("-", "_").replace(" ", "_")
    suggestions = []

    for canonical_type in UNIFIED_ONTOLOGY_REGISTRY.keys():
        # Calculate similarity
        ratio = SequenceMatcher(None, normalized, canonical_type).ratio()

        if ratio > 0.4:  # Threshold for suggestions
            suggestions.append({
                "suggested_type": canonical_type,
                "domain": get_domain_for_type(canonical_type).value,
                "similarity": round(ratio, 3),
                "layer": get_layer_for_type(canonical_type),
            })

    # Sort by similarity descending
    suggestions.sort(key=lambda x: x["similarity"], reverse=True)

    return suggestions[:5]  # Top 5 suggestions


def get_registry_statistics() -> Dict[str, Any]:
    """Get statistics about the unified ontology registry.

    Returns:
        Dictionary with registry statistics
    """
    stats = {
        "total_types": len(UNIFIED_ONTOLOGY_REGISTRY),
        "medical_types": len(MEDICAL_ONTOLOGY_REGISTRY),
        "data_architecture_types": len(DATA_ONTOLOGY_REGISTRY),
        "total_aliases": len(UNIFIED_TYPE_ALIASES),
        "types_by_layer": {},
    }

    # Count types by layer
    for layer in ["PERCEPTION", "SEMANTIC", "REASONING", "APPLICATION"]:
        stats["types_by_layer"][layer] = len(get_all_types_for_layer(layer))

    return stats
