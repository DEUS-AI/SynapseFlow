"""Ontology Quality Service.

Evaluates ontology quality using multiple metrics:
- Ontology Coverage (entity mapping to classes)
- Schema Compliance (required properties per class)
- Taxonomy Coherence (is-a hierarchy)
- Mapping Consistency (type uniformity)
- Semantic Normalization Quality
- Cross-Reference Validity
- Interoperability Score (Schema.org coverage)
"""

import time
import uuid
import logging
from typing import List, Dict, Any, Optional, Set
from collections import Counter, defaultdict

from domain.ontology_quality_models import (
    OntologyQualityReport,
    OntologyCoverageScore,
    SchemaComplianceScore,
    TaxonomyCoherenceScore,
    MappingConsistencyScore,
    NormalizationQualityScore,
    CrossReferenceValidityScore,
    InteroperabilityScore,
    OntologyQualityLevel,
    ODIN_SCHEMAS,
    SCHEMA_ORG_MAPPINGS,
)
from application.services.semantic_normalizer import SemanticNormalizer

logger = logging.getLogger(__name__)


class OntologyQualityService:
    """Evaluates ontology quality for knowledge graphs."""

    def __init__(
        self,
        kg_backend: Any,
        normalizer: Optional[SemanticNormalizer] = None,
    ):
        """Initialize the ontology quality service.

        Args:
            kg_backend: Knowledge graph backend for querying entities
            normalizer: Optional semantic normalizer for name analysis
        """
        self.backend = kg_backend
        self.normalizer = normalizer or SemanticNormalizer()

        # Known ontology classes
        self.odin_classes = set(ODIN_SCHEMAS.keys())
        self.schema_org_types = set(SCHEMA_ORG_MAPPINGS.values())

    async def assess_ontology_quality(
        self,
        ontology_name: str = "ODIN",
    ) -> OntologyQualityReport:
        """Perform complete ontology quality assessment.

        Args:
            ontology_name: Name of the ontology being assessed

        Returns:
            OntologyQualityReport with all metrics
        """
        start_time = time.time()
        assessment_id = str(uuid.uuid4())[:8]

        report = OntologyQualityReport(
            assessment_id=assessment_id,
            ontology_name=ontology_name,
        )

        try:
            # Fetch all entities from the graph
            entities = await self._fetch_all_entities()
            relationships = await self._fetch_all_relationships()

            report.entity_count = len(entities)
            report.relationship_count = len(relationships)
            report.class_count = len(self._get_unique_classes(entities))

            # Compute individual metrics
            report.coverage = await self._assess_coverage(entities)
            report.compliance = await self._assess_compliance(entities)
            report.taxonomy = await self._assess_taxonomy(entities, relationships)
            report.consistency = await self._assess_consistency(entities)
            report.normalization = await self._assess_normalization(entities)
            report.cross_reference = await self._assess_cross_references(relationships, entities)
            report.interoperability = await self._assess_interoperability(entities)

            # Compute overall score and generate recommendations
            report.compute_overall_score()
            report.generate_recommendations()

        except Exception as e:
            logger.error(f"Error during ontology quality assessment: {e}")
            report.critical_issues.append(f"Assessment error: {str(e)}")

        report.processing_time_ms = int((time.time() - start_time) * 1000)

        return report

    async def _fetch_all_entities(self) -> List[Dict[str, Any]]:
        """Fetch all entities from the knowledge graph."""
        try:
            query = """
            MATCH (n)
            WHERE n.id IS NOT NULL
            RETURN n.id as id,
                   n.name as name,
                   n.type as type,
                   labels(n) as labels,
                   n.layer as layer,
                   n.confidence as confidence,
                   properties(n) as properties
            LIMIT 10000
            """
            results = await self.backend.query_raw(query, {})
            return [dict(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"Error fetching entities: {e}")
            return []

    async def _fetch_all_relationships(self) -> List[Dict[str, Any]]:
        """Fetch all relationships from the knowledge graph."""
        try:
            query = """
            MATCH (a)-[r]->(b)
            WHERE a.id IS NOT NULL AND b.id IS NOT NULL
            RETURN a.id as source_id,
                   a.name as source_name,
                   labels(a) as source_labels,
                   type(r) as relationship_type,
                   b.id as target_id,
                   b.name as target_name,
                   labels(b) as target_labels
            LIMIT 50000
            """
            results = await self.backend.query_raw(query, {})
            return [dict(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"Error fetching relationships: {e}")
            return []

    def _get_unique_classes(self, entities: List[Dict[str, Any]]) -> Set[str]:
        """Get unique ontology classes from entities."""
        classes = set()
        for entity in entities:
            labels = entity.get("labels", [])
            for label in labels:
                if label in self.odin_classes or label in self.schema_org_types:
                    classes.add(label)
        return classes

    async def _assess_coverage(self, entities: List[Dict[str, Any]]) -> OntologyCoverageScore:
        """Assess ontology coverage of entities."""
        score = OntologyCoverageScore()
        score.total_entities = len(entities)

        if not entities:
            return score

        class_distribution = Counter()
        unmapped_types = set()

        for entity in entities:
            labels = set(entity.get("labels", []))
            entity_type = entity.get("type", "Unknown")

            # Check ODIN mapping
            has_odin = bool(labels & self.odin_classes)
            if has_odin:
                score.odin_mapped += 1

            # Check Schema.org mapping
            has_schema = bool(labels & self.schema_org_types)
            if has_schema:
                score.schema_org_mapped += 1

            # Overall mapping
            if has_odin or has_schema:
                score.mapped_entities += 1
                # Track class distribution
                for label in labels:
                    if label in self.odin_classes or label in self.schema_org_types:
                        class_distribution[label] += 1
            else:
                score.unmapped_entities += 1
                unmapped_types.add(entity_type)

        # Calculate ratios
        score.coverage_ratio = score.mapped_entities / score.total_entities
        score.odin_coverage = score.odin_mapped / score.total_entities
        score.schema_org_coverage = score.schema_org_mapped / score.total_entities

        score.class_distribution = dict(class_distribution.most_common(20))
        score.unmapped_types = list(unmapped_types)[:10]

        return score

    async def _assess_compliance(self, entities: List[Dict[str, Any]]) -> SchemaComplianceScore:
        """Assess schema compliance of entities."""
        score = SchemaComplianceScore()

        if not entities:
            return score

        violations_by_class = defaultdict(list)
        required_coverage_sum = 0
        optional_coverage_sum = 0
        validated_count = 0

        for entity in entities:
            labels = entity.get("labels", [])
            properties = entity.get("properties", {}) or {}

            # Find applicable schema
            for label in labels:
                if label in ODIN_SCHEMAS:
                    schema = ODIN_SCHEMAS[label]
                    validated_count += 1
                    score.total_validated += 1

                    # Check required properties
                    missing_required = []
                    for prop in schema.required_properties:
                        if prop not in properties or properties[prop] is None:
                            missing_required.append(prop)

                    # Calculate coverage
                    if schema.required_properties:
                        required_present = len(schema.required_properties) - len(missing_required)
                        req_coverage = required_present / len(schema.required_properties)
                        required_coverage_sum += req_coverage
                    else:
                        required_coverage_sum += 1.0

                    # Check optional properties
                    if schema.optional_properties:
                        optional_present = sum(
                            1 for prop in schema.optional_properties
                            if prop in properties and properties[prop] is not None
                        )
                        opt_coverage = optional_present / len(schema.optional_properties)
                        optional_coverage_sum += opt_coverage
                    else:
                        optional_coverage_sum += 1.0

                    # Classify compliance
                    if not missing_required:
                        score.fully_compliant += 1
                    elif len(missing_required) <= len(schema.required_properties) / 2:
                        score.partially_compliant += 1
                        violations_by_class[label].append(
                            f"{entity.get('name', entity.get('id'))}: missing {', '.join(missing_required)}"
                        )
                    else:
                        score.non_compliant += 1
                        score.missing_required.append({
                            "entity_id": entity.get("id"),
                            "class": label,
                            "missing": missing_required
                        })
                        violations_by_class[label].append(
                            f"{entity.get('name', entity.get('id'))}: missing {', '.join(missing_required)}"
                        )

                    break  # Only check first matching schema

        # Calculate ratios
        if score.total_validated > 0:
            score.compliance_ratio = score.fully_compliant / score.total_validated
            score.avg_required_coverage = required_coverage_sum / score.total_validated
            score.avg_optional_coverage = optional_coverage_sum / score.total_validated
        else:
            # No entities with known schemas - assume partial compliance
            score.compliance_ratio = 0.5

        score.violations_by_class = dict(violations_by_class)

        return score

    async def _assess_taxonomy(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> TaxonomyCoherenceScore:
        """Assess taxonomy hierarchy coherence."""
        score = TaxonomyCoherenceScore()

        if not relationships:
            return score

        # Define valid hierarchy relationships
        hierarchy_rels = {"IS_A", "SUBCLASS_OF", "PART_OF", "BELONGS_TO", "hasAttribute"}

        # Track parent-child relationships
        parents = defaultdict(set)
        children = defaultdict(set)
        all_nodes = set()

        for rel in relationships:
            rel_type = rel.get("relationship_type", "")
            source_id = rel.get("source_id")
            target_id = rel.get("target_id")

            if source_id and target_id:
                all_nodes.add(source_id)
                all_nodes.add(target_id)

            if rel_type in hierarchy_rels:
                score.total_relationships += 1

                # Source is child, target is parent
                parents[source_id].add(target_id)
                children[target_id].add(source_id)

                # Validate relationship
                source_labels = set(rel.get("source_labels", []))
                target_labels = set(rel.get("target_labels", []))

                # Check if relationship makes ontological sense
                if self._is_valid_hierarchy(source_labels, target_labels, rel_type):
                    score.valid_relationships += 1
                else:
                    score.invalid_relationships += 1
                    score.hierarchy_violations.append({
                        "source": source_id,
                        "target": target_id,
                        "relationship": rel_type,
                        "reason": "Invalid parent-child type combination"
                    })

        # Calculate coherence
        if score.total_relationships > 0:
            score.coherence_ratio = score.valid_relationships / score.total_relationships
        else:
            score.coherence_ratio = 1.0  # No hierarchy relationships = not invalid

        # Detect orphans (nodes with no parents in hierarchy)
        entity_ids = {e.get("id") for e in entities}
        nodes_with_parents = set(parents.keys())
        root_nodes = entity_ids - nodes_with_parents

        # Not all root nodes are orphans - some are legitimate roots
        # Orphans are leaf nodes without any hierarchy connections
        potential_orphans = 0
        for entity in entities:
            eid = entity.get("id")
            if eid not in nodes_with_parents and eid not in children:
                # No parent and no children - completely isolated from hierarchy
                potential_orphans += 1

        score.orphan_nodes = potential_orphans

        # Calculate hierarchy depth
        depths = self._calculate_hierarchy_depths(parents)
        if depths:
            score.max_depth = max(depths.values())
            score.avg_depth = sum(depths.values()) / len(depths)

        # Detect circular references
        score.circular_references = self._detect_cycles(parents)

        return score

    def _is_valid_hierarchy(
        self,
        source_labels: Set[str],
        target_labels: Set[str],
        rel_type: str
    ) -> bool:
        """Check if a hierarchy relationship is valid."""
        # Define valid parent-child combinations
        valid_combinations = {
            # Attribute can belong to DataEntity
            ("Attribute", "DataEntity"),
            ("Column", "Table"),
            # InformationAsset derives from DataEntity
            ("InformationAsset", "DataEntity"),
            # Concepts can be related
            ("BusinessConcept", "BusinessConcept"),
            ("BusinessConcept", "Domain"),
            # Domain hierarchy
            ("Domain", "Domain"),
        }

        # Check if any valid combination matches
        for source_label in source_labels:
            for target_label in target_labels:
                if (source_label, target_label) in valid_combinations:
                    return True

        # Allow same-type relationships
        if source_labels & target_labels:
            return True

        return False

    def _calculate_hierarchy_depths(self, parents: Dict[str, Set[str]]) -> Dict[str, int]:
        """Calculate depth of each node in hierarchy."""
        depths = {}

        def get_depth(node: str, visited: Set[str]) -> int:
            if node in depths:
                return depths[node]
            if node in visited:
                return 0  # Cycle detected
            if node not in parents or not parents[node]:
                return 0  # Root node

            visited.add(node)
            max_parent_depth = max(
                get_depth(p, visited) for p in parents[node]
            )
            depths[node] = max_parent_depth + 1
            return depths[node]

        for node in parents:
            get_depth(node, set())

        return depths

    def _detect_cycles(self, parents: Dict[str, Set[str]]) -> List[str]:
        """Detect circular references in hierarchy."""
        cycles = []

        def dfs(node: str, path: List[str], visited: Set[str]) -> bool:
            if node in path:
                # Found cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(" -> ".join(cycle))
                return True

            if node in visited:
                return False

            visited.add(node)
            path.append(node)

            for parent in parents.get(node, []):
                if dfs(parent, path.copy(), visited):
                    break

            return False

        for node in parents:
            dfs(node, [], set())

        return cycles[:5]  # Limit to first 5

    async def _assess_consistency(self, entities: List[Dict[str, Any]]) -> MappingConsistencyScore:
        """Assess consistency of type mappings."""
        score = MappingConsistencyScore()

        # Group entities by their raw type
        type_to_classes = defaultdict(set)

        for entity in entities:
            raw_type = entity.get("type", "Unknown")
            labels = set(entity.get("labels", []))
            ontology_classes = labels & (self.odin_classes | self.schema_org_types)

            if ontology_classes:
                for oc in ontology_classes:
                    type_to_classes[raw_type].add(oc)

        score.total_types = len(type_to_classes)

        for raw_type, classes in type_to_classes.items():
            if len(classes) == 1:
                score.consistent_types += 1
            else:
                score.inconsistent_types += 1
                score.ambiguous_mappings[raw_type] = classes
                score.one_to_many_mappings += 1

                # Suggest most common class as canonical
                # (would need frequency data for better suggestion)
                score.suggested_canonical[raw_type] = list(classes)[0]

        # Calculate consistency ratio
        if score.total_types > 0:
            score.consistency_ratio = score.consistent_types / score.total_types
        else:
            score.consistency_ratio = 1.0

        return score

    async def _assess_normalization(self, entities: List[Dict[str, Any]]) -> NormalizationQualityScore:
        """Assess quality of entity name normalization."""
        score = NormalizationQualityScore()

        if not entities:
            return score

        score.total_names = len(entities)
        seen_canonical = defaultdict(list)

        for entity in entities:
            name = entity.get("name", "")
            if not name:
                continue

            # Normalize the name
            canonical = self.normalizer.normalize(name)

            if canonical == name.lower().replace(" ", "_"):
                score.already_canonical += 1
            else:
                score.normalized_names += 1

            # Track for duplicate detection
            seen_canonical[canonical].append({
                "id": entity.get("id"),
                "original_name": name
            })

            # Check for abbreviations
            if any(abbr in name.lower() for abbr in self.normalizer._abbreviation_map):
                score.abbreviations_expanded += 1

            # Check for synonyms
            if any(syn in name.lower() for syn in self.normalizer._synonym_map):
                score.synonyms_resolved += 1

        # Find potential duplicates (same canonical form)
        for canonical, instances in seen_canonical.items():
            if len(instances) > 1:
                score.potential_duplicates.append({
                    "canonical_form": canonical,
                    "instances": instances[:5]  # Limit
                })

        score.deduplication_candidates = len(score.potential_duplicates)
        score.normalization_rate = (
            (score.normalized_names + score.already_canonical) / score.total_names
            if score.total_names > 0 else 0
        )

        return score

    async def _assess_cross_references(
        self,
        relationships: List[Dict[str, Any]],
        entities: List[Dict[str, Any]]
    ) -> CrossReferenceValidityScore:
        """Assess validity of cross-references between entities."""
        score = CrossReferenceValidityScore()

        if not relationships:
            return score

        # Build entity type lookup
        entity_types = {}
        for entity in entities:
            eid = entity.get("id")
            labels = set(entity.get("labels", []))
            entity_types[eid] = labels & (self.odin_classes | self.schema_org_types)

        # Define valid relationship combinations
        valid_rel_types = {
            "hasAttribute": [("DataEntity", "Attribute"), ("Table", "Column")],
            "belongsToDomain": [("*", "Domain")],
            "derivedFrom": [("InformationAsset", "DataEntity")],
            "represents": [("DataEntity", "BusinessConcept")],
            "relatedTo": [("*", "*")],  # Generic relationship
        }

        rel_type_counts = Counter()

        for rel in relationships:
            rel_type = rel.get("relationship_type", "")
            source_id = rel.get("source_id")
            target_id = rel.get("target_id")

            score.total_references += 1
            rel_type_counts[rel_type] += 1

            source_types = entity_types.get(source_id, set())
            target_types = entity_types.get(target_id, set())

            # Check if relationship is valid
            is_valid = self._is_valid_relationship(
                rel_type, source_types, target_types, valid_rel_types
            )

            if is_valid:
                score.valid_references += 1
            else:
                score.invalid_references += 1
                score.invalid_combinations.append({
                    "relationship": rel_type,
                    "source_types": list(source_types),
                    "target_types": list(target_types),
                })

        score.relationships_by_type = dict(rel_type_counts.most_common(20))

        if score.total_references > 0:
            score.validity_ratio = score.valid_references / score.total_references
        else:
            score.validity_ratio = 1.0

        return score

    def _is_valid_relationship(
        self,
        rel_type: str,
        source_types: Set[str],
        target_types: Set[str],
        valid_combinations: Dict[str, List]
    ) -> bool:
        """Check if a relationship is valid given the types."""
        if rel_type not in valid_combinations:
            # Unknown relationship type - allow it
            return True

        allowed = valid_combinations[rel_type]

        for source_allowed, target_allowed in allowed:
            # Wildcard matches everything
            if source_allowed == "*" or source_allowed in source_types:
                if target_allowed == "*" or target_allowed in target_types:
                    return True

        return False

    async def _assess_interoperability(self, entities: List[Dict[str, Any]]) -> InteroperabilityScore:
        """Assess interoperability with external systems."""
        score = InteroperabilityScore()

        if not entities:
            return score

        # Count Schema.org mappings
        schema_type_count = 0
        missing_schema_types = set()

        for entity in entities:
            labels = set(entity.get("labels", []))

            # Check for Schema.org type
            if labels & self.schema_org_types:
                schema_type_count += 1
            else:
                # What Schema.org type should it have?
                for label in labels:
                    if label in SCHEMA_ORG_MAPPINGS:
                        # Has ODIN but not Schema.org
                        missing_schema_types.add(label)

        score.schema_org_types = schema_type_count
        score.schema_org_coverage = schema_type_count / len(entities)

        # Check for standard property names
        standard_props = {"name", "description", "id", "dateCreated", "dateModified"}
        prop_coverage = 0

        for entity in entities:
            props = set(entity.get("properties", {}).keys())
            if props & standard_props:
                prop_coverage += 1

        score.schema_org_properties = prop_coverage

        # Interoperability features
        score.linked_data_ready = score.schema_org_coverage >= 0.5
        score.rdf_exportable = score.schema_org_coverage >= 0.7
        score.sparql_compatible = True  # Neo4j supports Cypher, not SPARQL directly

        score.missing_schema_types = list(missing_schema_types)[:10]

        # Calculate exchange readiness
        score.exchange_readiness = (
            score.schema_org_coverage * 0.6 +
            (prop_coverage / len(entities) if entities else 0) * 0.4
        )

        return score


async def quick_ontology_check(kg_backend: Any) -> Dict[str, Any]:
    """Quick ontology quality check for dashboards.

    Args:
        kg_backend: Knowledge graph backend

    Returns:
        Quick quality summary
    """
    service = OntologyQualityService(kg_backend)
    report = await service.assess_ontology_quality()

    return {
        "quality_level": report.quality_level.value,
        "overall_score": round(report.overall_score, 2),
        "entity_count": report.entity_count,
        "coverage_ratio": round(report.coverage.coverage_ratio, 2),
        "compliance_ratio": round(report.compliance.compliance_ratio, 2),
        "critical_issues": report.critical_issues[:3],
        "top_recommendations": report.improvement_priority[:3],
    }
