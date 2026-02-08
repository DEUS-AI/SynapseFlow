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
    # PERCEPTION Layer
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

    # SEMANTIC Layer
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

    # REASONING Layer
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

    # APPLICATION Layer
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
}

# Data architecture type aliases
DATA_TYPE_ALIASES: Dict[str, str] = {
    "tables": "table",
    "files": "file",
    "columns": "column",
    "fields": "field",
    "attribute": "field",
    "attributes": "field",
    "reports": "report",
    "dashboards": "dashboard",
    "domains": "domain",
    "concepts": "concept",
    "businessconcept": "business_concept",
    "rules": "rule",
    "qualityrule": "data_quality_rule",
    "scores": "score",
    "qualityscore": "score",
    "usagestats": "usage",
    "decisions": "decision",
    "dataentity": "table",
    "data_entity": "table",
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

    Works across all ontology domains.

    Args:
        raw_type: Raw entity type string (e.g., "Medical Condition", "tables")

    Returns:
        Canonical type string (e.g., "disease", "table")
    """
    normalized = raw_type.lower().strip().replace("-", "_").replace(" ", "_")
    return UNIFIED_TYPE_ALIASES.get(normalized, normalized)


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
