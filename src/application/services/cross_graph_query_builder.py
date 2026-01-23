"""
Cross-Graph Query Builder

Provides query templates and utilities for traversing the unified Neo4j graph
containing both medical knowledge and DDA metadata.

Supports common query patterns:
- Medical entity → Data entities
- Data entities → Medical concepts
- Multi-hop traversals across SEMANTIC layer
- Layer-filtered queries
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from neo4j import GraphDatabase
import os

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result from a cross-graph query."""
    query: str
    parameters: Dict[str, Any]
    records: List[Dict[str, Any]]
    record_count: int


class CrossGraphQueryBuilder:
    """Builds and executes cross-graph queries in Neo4j."""

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """Initialize with Neo4j connection."""
        self.uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        if '\n' in self.uri:
            self.uri = self.uri.split('\n')[-1].strip()

        self.user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = neo4j_password or os.getenv("NEO4J_PASSWORD", "")

        logger.info(f"Connecting to Neo4j at {self.uri}")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def __del__(self):
        """Close Neo4j connection."""
        if hasattr(self, 'driver'):
            self.driver.close()

    def find_tables_for_disease(self, disease_name: str) -> QueryResult:
        """
        Find all data tables containing information about a specific disease.

        Args:
            disease_name: Name of the disease (case-insensitive)

        Returns:
            QueryResult with tables linked to the disease
        """
        query = """
        MATCH (disease:MedicalEntity)
        WHERE toLower(disease.name) = toLower($disease_name)
          AND disease.type = 'Disease'
        OPTIONAL MATCH (disease)-[r:APPLICABLE_TO]->(table)
        WHERE r.layer = 'SEMANTIC' AND table:Table
        RETURN
            disease.name as disease,
            disease.description as disease_description,
            collect(DISTINCT {
                table_name: table.name,
                table_description: table.description,
                domain: table.domain,
                confidence: r.confidence,
                linking_strategy: r.linking_strategy
            }) as tables
        """

        with self.driver.session() as session:
            result = session.run(query, disease_name=disease_name)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters={"disease_name": disease_name},
                records=records,
                record_count=len(records)
            )

    def find_medical_concepts_in_data(
        self,
        confidence_threshold: float = 0.75
    ) -> QueryResult:
        """
        Find all medical concepts that are represented in the data catalog.

        Args:
            confidence_threshold: Minimum confidence for SEMANTIC relationships

        Returns:
            QueryResult with medical concepts and their data entities
        """
        query = """
        MATCH (m:MedicalEntity)-[r:APPLICABLE_TO|RELATES_TO]->(d)
        WHERE r.layer = 'SEMANTIC' AND r.confidence >= $threshold
        RETURN
            m.name as medical_entity,
            m.type as medical_type,
            m.description as medical_description,
            type(r) as relationship_type,
            r.confidence as confidence,
            d.name as data_entity,
            labels(d)[0] as data_type,
            d.description as data_description
        ORDER BY r.confidence DESC, m.type, m.name
        """

        with self.driver.session() as session:
            result = session.run(query, threshold=confidence_threshold)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters={"threshold": confidence_threshold},
                records=records,
                record_count=len(records)
            )

    def find_treatments_for_disease(self, disease_name: str) -> QueryResult:
        """
        Find treatments for a specific disease and related data tables.

        Args:
            disease_name: Name of the disease

        Returns:
            QueryResult with treatments and data context
        """
        query = """
        MATCH (disease:MedicalEntity {name: $disease_name})
        WHERE disease.type = 'Disease'
        OPTIONAL MATCH (treatment:MedicalEntity)-[r1:TREATS]->(disease)
        WHERE treatment.type = 'Treatment' OR treatment.type = 'Drug'
        OPTIONAL MATCH (disease)-[r2:APPLICABLE_TO]->(table:Table)
        WHERE r2.layer = 'SEMANTIC'
        OPTIONAL MATCH (treatment)-[r3:APPLICABLE_TO|RELATES_TO]->(data_entity)
        WHERE r3.layer = 'SEMANTIC'
        RETURN
            disease.name as disease,
            collect(DISTINCT {
                treatment_name: treatment.name,
                treatment_type: treatment.type,
                treatment_description: treatment.description,
                relationship: r1.description
            }) as treatments,
            collect(DISTINCT {
                table_name: table.name,
                domain: table.domain
            }) as disease_tables,
            collect(DISTINCT {
                data_entity: data_entity.name,
                data_type: labels(data_entity)[0]
            }) as treatment_data
        """

        with self.driver.session() as session:
            result = session.run(query, disease_name=disease_name)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters={"disease_name": disease_name},
                records=records,
                record_count=len(records)
            )

    def find_full_context_for_entity(
        self,
        entity_name: str,
        max_depth: int = 2
    ) -> QueryResult:
        """
        Find full context around a medical entity (multi-hop traversal).

        Args:
            entity_name: Name of the medical entity
            max_depth: Maximum relationship depth to traverse

        Returns:
            QueryResult with entity context
        """
        query = f"""
        MATCH (entity:MedicalEntity {{name: $entity_name}})
        OPTIONAL MATCH path = (entity)-[*1..{max_depth}]-(related)
        RETURN
            entity.name as entity_name,
            entity.type as entity_type,
            entity.description as entity_description,
            collect(DISTINCT {{
                related_name: related.name,
                related_type: coalesce(related.type, labels(related)[0]),
                related_description: related.description,
                relationship_path: [r in relationships(path) | type(r)],
                layer: [r in relationships(path) | r.layer]
            }}) as context
        """

        with self.driver.session() as session:
            result = session.run(query, entity_name=entity_name)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters={"entity_name": entity_name, "max_depth": max_depth},
                records=records,
                record_count=len(records)
            )

    def find_columns_for_medical_concept(
        self,
        concept_name: str
    ) -> QueryResult:
        """
        Find data columns that represent a medical concept.

        Args:
            concept_name: Name of the medical concept

        Returns:
            QueryResult with columns and their tables
        """
        query = """
        MATCH (concept:MedicalEntity)
        WHERE toLower(concept.name) CONTAINS toLower($concept_name)
        OPTIONAL MATCH (concept)-[r:RELATES_TO]->(col:Column)
        WHERE r.layer = 'SEMANTIC'
        OPTIONAL MATCH (col)<-[:HAS_COLUMN]-(table:Table)
        RETURN
            concept.name as medical_concept,
            concept.type as concept_type,
            collect(DISTINCT {
                column_name: col.name,
                column_type: col.data_type,
                table_name: table.name,
                domain: table.domain,
                confidence: r.confidence
            }) as columns
        """

        with self.driver.session() as session:
            result = session.run(query, concept_name=concept_name)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters={"concept_name": concept_name},
                records=records,
                record_count=len(records)
            )

    def search_medical_entities(
        self,
        search_term: str,
        entity_types: Optional[List[str]] = None
    ) -> QueryResult:
        """
        Search for medical entities by name or description.

        Args:
            search_term: Term to search for (case-insensitive)
            entity_types: Optional list of entity types to filter (e.g., ['Disease', 'Treatment'])

        Returns:
            QueryResult with matching entities
        """
        # Build type filter
        type_filter = ""
        params = {"search_term": search_term}

        if entity_types:
            type_filter = "AND m.type IN $entity_types"
            params["entity_types"] = entity_types

        query = f"""
        MATCH (m:MedicalEntity)
        WHERE (toLower(m.name) CONTAINS toLower($search_term)
           OR toLower(m.description) CONTAINS toLower($search_term))
          {type_filter}
        RETURN
            m.name as name,
            m.type as type,
            m.description as description,
            m.confidence as confidence,
            m.source_document as source
        ORDER BY m.name
        LIMIT 50
        """

        with self.driver.session() as session:
            result = session.run(query, **params)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters=params,
                records=records,
                record_count=len(records)
            )

    def get_cross_graph_statistics(self) -> QueryResult:
        """
        Get statistics about the unified graph.

        Returns:
            QueryResult with entity and relationship counts by type and layer
        """
        query = """
        // Medical entities
        MATCH (m:MedicalEntity)
        WITH count(m) as medical_count

        // Data entities
        MATCH (d)
        WHERE d:Table OR d:Column OR d:BusinessConcept
        WITH medical_count, count(d) as data_count

        // SEMANTIC relationships
        MATCH ()-[r]-()
        WHERE r.layer = 'SEMANTIC'
        WITH medical_count, data_count, count(r) as semantic_links

        // All relationships
        MATCH ()-[r2]-()

        RETURN
            medical_count,
            data_count,
            semantic_links,
            count(r2) as total_relationships,
            medical_count + data_count as total_entities
        """

        with self.driver.session() as session:
            result = session.run(query)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters={},
                records=records,
                record_count=len(records)
            )

    def find_related_entities(
        self,
        entity_name: str,
        relationship_types: Optional[List[str]] = None,
        max_results: int = 20
    ) -> QueryResult:
        """
        Find entities directly related to a given entity.

        Args:
            entity_name: Name of the entity
            relationship_types: Optional list of relationship types to filter
            max_results: Maximum number of results

        Returns:
            QueryResult with related entities
        """
        # Build relationship filter
        rel_filter = ""
        params = {"entity_name": entity_name, "max_results": max_results}

        if relationship_types:
            rel_filter = f"AND type(r) IN $relationship_types"
            params["relationship_types"] = relationship_types

        query = f"""
        MATCH (entity {{name: $entity_name}})
        MATCH (entity)-[r]-(related)
        WHERE related.name IS NOT NULL {rel_filter}
        RETURN DISTINCT
            entity.name as source_entity,
            type(r) as relationship,
            related.name as related_entity,
            coalesce(related.type, labels(related)[0]) as related_type,
            r.layer as layer,
            r.confidence as confidence,
            r.description as relationship_description
        ORDER BY r.confidence DESC
        LIMIT $max_results
        """

        with self.driver.session() as session:
            result = session.run(query, **params)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters=params,
                records=records,
                record_count=len(records)
            )

    def execute_custom_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Execute a custom Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            QueryResult with query results
        """
        params = parameters or {}

        with self.driver.session() as session:
            result = session.run(query, **params)
            records = [dict(record) for record in result]

            return QueryResult(
                query=query,
                parameters=params,
                records=records,
                record_count=len(records)
            )
