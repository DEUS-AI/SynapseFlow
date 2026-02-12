"""Ontology Mapper Service.

This service is responsible for mapping internal entity types to the
Hybrid Ontology (ODIN + Schema.org). It ensures that every entity
in the graph carries both the specific domain semantics (ODIN) and
general interoperability annotations (Schema.org).

Enhanced to use the unified ontology registry which supports multiple
domains (data architecture, medical, etc.).
"""

from typing import Dict, List, Any, Tuple, Optional
from domain.ontologies.odin import ODIN
from domain.ontologies.schema_org import SCHEMA
from domain.ontologies.registry import (
    get_ontology_config,
    is_known_type,
    resolve_entity_type,
    get_domain_for_type,
    get_layer_for_type,
    get_hierarchy_path,
    get_auto_relationships,
    suggest_type_mapping,
    OntologyDomain,
)


class OntologyMapper:
    """Maps internal entities to Hybrid Ontology (ODIN + Schema.org).

    Uses the unified ontology registry to support multiple domains
    including data architecture and medical entities.
    """

    def __init__(self):
        """Initialize the ontology mapper."""
        # Legacy Schema.org mappings for backward compatibility
        self._schema_org_mappings = {
            "table": SCHEMA.DATASET,
            "file": SCHEMA.DATASET,
            "column": SCHEMA.PROPERTY,
            "field": SCHEMA.PROPERTY,
            "report": SCHEMA.ARTICLE,
            "dashboard": SCHEMA.ARTICLE,
            "domain": SCHEMA.ORGANIZATION,
            "concept": SCHEMA.DEFINED_TERM,
            "user": SCHEMA.PERSON,
            "owner": SCHEMA.PERSON,
        }

    def map_entity(
        self, entity_type: str, properties: Dict[str, Any]
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Map an entity to ontology classes and enrich properties.

        Uses the unified registry to look up entity configuration
        across all ontology domains.

        Args:
            entity_type: The raw type (e.g., 'Table', 'Disease', 'Drug')
            properties: The raw properties

        Returns:
            labels: List of labels (e.g., ['DataEntity', 'Dataset', 'Table'])
            properties: Enriched properties with ontology metadata
        """
        labels = []
        enriched_props = dict(properties)

        # Resolve to canonical type
        canonical_type = resolve_entity_type(entity_type)

        # Look up in unified registry
        config = get_ontology_config(entity_type)

        if config:
            # 1. Add ODIN class as primary label
            odin_class = config.get("odin_class")
            if odin_class:
                labels.append(odin_class)

            # 2. Add Schema.org mapping if available (for interoperability)
            schema_type = self._get_schema_org_type(canonical_type, config)
            if schema_type:
                labels.append(schema_type)

            # 3. Enrich properties with ontology metadata
            enriched_props["_ontology_mapped"] = True
            enriched_props["_canonical_type"] = canonical_type
            enriched_props["_ontology_domain"] = get_domain_for_type(entity_type).value

            # Add layer if not already present
            if "layer" not in enriched_props:
                layer = config.get("layer")
                if layer:
                    enriched_props["layer"] = layer

            # Add hierarchy path for IS_A relationship creation
            hierarchy = config.get("hierarchy_path", [])
            if hierarchy:
                enriched_props["_hierarchy_path"] = hierarchy

        else:
            # Unknown type - use legacy mapping as fallback
            odin_type = self._map_to_odin_legacy(entity_type)
            if odin_type:
                labels.append(odin_type)

            schema_type = self._map_to_schema_legacy(entity_type)
            if schema_type:
                labels.append(schema_type)

            enriched_props["_ontology_mapped"] = False
            enriched_props["_unmapped_type"] = entity_type

        # 4. Preserve original type as label for specificity
        normalized_type = entity_type.replace(" ", "").replace("-", "")
        if normalized_type[0].isalpha():
            normalized_type = normalized_type[0].upper() + normalized_type[1:]
        if normalized_type not in labels:
            labels.append(normalized_type)

        return labels, enriched_props

    def _get_schema_org_type(
        self, canonical_type: str, config: Dict[str, Any]
    ) -> Optional[str]:
        """Get Schema.org type from config or legacy mapping.

        Args:
            canonical_type: Resolved canonical type
            config: Ontology configuration

        Returns:
            Schema.org type string or None
        """
        # Check if external_systems includes schema.org
        external = config.get("external_systems", [])
        for system in external:
            if isinstance(system, str) and system.startswith("schema.org:"):
                return system.split(":")[1]

        # Fall back to legacy mapping
        return self._schema_org_mappings.get(canonical_type)

    def _map_to_odin_legacy(self, entity_type: str) -> Optional[str]:
        """Legacy ODIN mapping for backward compatibility.

        Args:
            entity_type: Raw entity type

        Returns:
            ODIN class or None
        """
        t = entity_type.lower()

        mapping = {
            "table": ODIN.DATA_ENTITY,
            "file": ODIN.DATA_ENTITY,
            "column": ODIN.ATTRIBUTE,
            "field": ODIN.ATTRIBUTE,
            "report": ODIN.INFORMATION_ASSET,
            "dashboard": ODIN.INFORMATION_ASSET,
            "domain": ODIN.DOMAIN,
            "concept": ODIN.BUSINESS_CONCEPT,
            "rule": ODIN.DATA_QUALITY_RULE,
            "score": ODIN.DATA_QUALITY_SCORE,
            "usage": ODIN.USAGE_STATS,
            "lineage": ODIN.TRANSFORMS_INTO,
        }
        return mapping.get(t)

    def _map_to_schema_legacy(self, entity_type: str) -> Optional[str]:
        """Legacy Schema.org mapping for backward compatibility.

        Args:
            entity_type: Raw entity type

        Returns:
            Schema.org class or None
        """
        t = entity_type.lower()
        return self._schema_org_mappings.get(t)

    def is_type_mapped(self, entity_type: str) -> bool:
        """Check if an entity type has ontology mapping.

        Args:
            entity_type: Entity type to check

        Returns:
            True if type is mapped in unified registry
        """
        return is_known_type(entity_type)

    def get_suggested_mappings(self, unknown_type: str) -> List[Dict[str, Any]]:
        """Get suggested mappings for an unknown type.

        Uses string similarity to find potential matches.

        Args:
            unknown_type: The unmapped type string

        Returns:
            List of suggested mappings with similarity scores
        """
        return suggest_type_mapping(unknown_type)

    def get_valid_relationships(self, entity_type: str) -> List[str]:
        """Get valid relationship types for an entity.

        Args:
            entity_type: Entity type

        Returns:
            List of valid relationship type strings
        """
        return get_auto_relationships(entity_type)

    def get_entity_layer(self, entity_type: str) -> Optional[str]:
        """Get the DIKW layer for an entity type.

        Args:
            entity_type: Entity type

        Returns:
            Layer name or None if not mapped
        """
        return get_layer_for_type(entity_type)

    def get_entity_hierarchy(self, entity_type: str) -> List[str]:
        """Get the hierarchy path for an entity type.

        Args:
            entity_type: Entity type

        Returns:
            Hierarchy path list
        """
        return get_hierarchy_path(entity_type)
