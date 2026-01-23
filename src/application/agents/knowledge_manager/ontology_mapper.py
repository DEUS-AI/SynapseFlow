"""Ontology Mapper Service.

This service is responsible for mapping internal entity types to the
Hybrid Ontology (ODIN + Schema.org). It ensures that every entity
in the graph carries both the specific domain semantics (ODIN) and
general interoperability annotations (Schema.org).
"""

from typing import Dict, List, Any, Tuple, Optional
from domain.ontologies.odin import ODIN
from domain.ontologies.schema_org import SCHEMA

class OntologyMapper:
    """Maps internal entities to Hybrid Ontology (ODIN + Schema.org)."""

    def map_entity(self, entity_type: str, properties: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
        """
        Returns (labels, properties) with ontology mappings applied.
        
        Args:
            entity_type: The raw type (e.g., 'Table', 'Column')
            properties: The raw properties
            
        Returns:
            labels: List of labels (e.g., ['DataEntity', 'Dataset', 'Table'])
            properties: Enriched properties (keys mapped to ontology predicates if needed)
        """
        labels = []
        
        # 1. Map to ODIN (Primary)
        odin_type = self._map_to_odin(entity_type)
        if odin_type:
            labels.append(odin_type)
            
        # 2. Map to Schema.org (Secondary)
        schema_type = self._map_to_schema(entity_type)
        if schema_type:
            labels.append(schema_type)
            
        # 3. Preserve original type as label for backward compatibility/specificity
        # We capitalize it to match Neo4j convention if it's not already
        normalized_type = entity_type.capitalize()
        if normalized_type not in labels:
            labels.append(normalized_type)
            
        return labels, properties

    def _map_to_odin(self, entity_type: str) -> Optional[str]:
        """Maps internal type to ODIN class."""
        # Normalize input
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
            "lineage": ODIN.TRANSFORMS_INTO # Usually a relationship, but if node...
        }
        return mapping.get(t)

    def _map_to_schema(self, entity_type: str) -> Optional[str]:
        """Maps internal type to Schema.org class."""
        t = entity_type.lower()
        
        mapping = {
            "table": SCHEMA.DATASET,
            "file": SCHEMA.DATASET,
            "column": SCHEMA.PROPERTY,
            "field": SCHEMA.PROPERTY,
            "report": SCHEMA.ARTICLE,
            "dashboard": SCHEMA.ARTICLE,
            "domain": SCHEMA.ORGANIZATION,
            "concept": SCHEMA.DEFINED_TERM,
            "user": SCHEMA.PERSON,
            "owner": SCHEMA.PERSON
        }
        return mapping.get(t)
