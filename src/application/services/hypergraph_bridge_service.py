"""Hypergraph Bridge Service.

Implements the neurosymbolic bridge between Document Graph (neural/dense)
and Knowledge Graph (symbolic/sparse) using FactUnits as hyperedges.

Architecture:

    ┌─────────────────┐         ┌──────────────────┐
    │  DOCUMENT GRAPH │         │  KNOWLEDGE GRAPH │
    │  (Neural Layer) │         │ (Symbolic Layer) │
    ├─────────────────┤         ├──────────────────┤
    │ Chunk           │         │ Disease          │
    │ ExtractedEntity │◄───────►│ Drug             │
    │ Embedding       │    │    │ Treatment        │
    │ Co-occurrence   │    │    │ Ontology classes │
    └─────────────────┘    │    └──────────────────┘
                           │
                   ┌───────┴────────┐
                   │  BRIDGE LAYER  │
                   │   (FactUnit)   │
                   ├────────────────┤
                   │ Hyperedges     │
                   │ Confidence     │
                   │ Provenance     │
                   └────────────────┘

Usage:
    from application.services.hypergraph_bridge_service import HypergraphBridgeService

    service = HypergraphBridgeService(neo4j_backend)

    # Build bridge from existing co-occurrences
    stats = await service.build_bridge_layer()

    # Query through the bridge
    facts = await service.get_facts_for_entity("diabetes")
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from domain.hypergraph_models import (
    FactUnit,
    FactType,
    HyperEdge,
    EntityMention,
    ConfidenceScore,
    ConfidenceSource,
    CoOccurrenceContext,
    NeurosymbolicLink,
    BridgeStatistics,
)
from domain.ontologies.registry import (
    get_ontology_config,
    is_known_type,
    resolve_entity_type,
    get_domain_for_type,
    get_layer_for_type,
)

logger = logging.getLogger(__name__)


class HypergraphBridgeService:
    """Service for building and querying the neurosymbolic bridge layer.

    The bridge layer consists of:
    1. FactUnit nodes: Hyperedges connecting multiple entities from shared context
    2. PARTICIPATES_IN relationships: Connecting entities to their FactUnits
    3. Confidence propagation: From neural (extraction) to symbolic (ontology)
    """

    # Cypher queries for bridge operations
    QUERIES = {
        "get_co_occurrences": """
            MATCH (c:Chunk)-[:MENTIONS]->(e1)
            MATCH (c)-[:MENTIONS]->(e2)
            WHERE id(e1) < id(e2)
            WITH c, collect(DISTINCT e1) + collect(DISTINCT e2) as entities
            WHERE size(entities) >= 2
            RETURN
                c.id as chunk_id,
                c.document_id as document_id,
                c.text as chunk_text,
                [e IN entities | {
                    id: coalesce(e.id, e.name),
                    name: e.name,
                    type: coalesce(e.type, labels(e)[0]),
                    confidence: coalesce(e.extraction_confidence, e.confidence, 0.7)
                }] as entities
            LIMIT $limit
        """,

        "create_fact_unit": """
            MERGE (f:FactUnit {id: $id})
            SET f += $properties
            SET f:Bridge
            RETURN f
        """,

        "create_participation": """
            MATCH (f:FactUnit {id: $fact_id})
            MATCH (e) WHERE e.id = $entity_id OR e.name = $entity_id
            MERGE (e)-[r:PARTICIPATES_IN]->(f)
            SET r.role = $role
            SET r.position = $position
            SET r.confidence = $confidence
            RETURN r
        """,

        "get_facts_for_entity": """
            MATCH (e)-[:PARTICIPATES_IN]->(f:FactUnit)
            WHERE e.id = $entity_id OR e.name = $entity_id
            OPTIONAL MATCH (other)-[:PARTICIPATES_IN]->(f)
            WHERE other <> e
            RETURN
                f as fact,
                collect(DISTINCT {
                    id: coalesce(other.id, other.name),
                    name: other.name,
                    type: labels(other)[0]
                }) as co_participants
            ORDER BY f.aggregate_confidence DESC
            LIMIT $limit
        """,

        "get_bridge_statistics": """
            MATCH (f:FactUnit)
            WITH count(f) as fact_count
            OPTIONAL MATCH ()-[r:PARTICIPATES_IN]->()
            WITH fact_count, count(r) as edge_count
            OPTIONAL MATCH (e)-[:PARTICIPATES_IN]->()
            WITH fact_count, edge_count, count(DISTINCT e) as entities_with_facts
            OPTIONAL MATCH (f:FactUnit)
            WITH fact_count, edge_count, entities_with_facts,
                 avg(f.aggregate_confidence) as avg_confidence
            RETURN
                fact_count,
                edge_count,
                entities_with_facts,
                avg_confidence
        """,

        "propagate_to_kg": """
            MATCH (e1)-[:PARTICIPATES_IN]->(f:FactUnit)<-[:PARTICIPATES_IN]-(e2)
            WHERE f.aggregate_confidence >= $threshold
              AND e1 <> e2
              AND NOT (e1)-[:RELATED_TO]-(e2)
            WITH e1, e2, f,
                 CASE f.fact_type
                   WHEN 'treatment' THEN 'MAY_TREAT'
                   WHEN 'causation' THEN 'MAY_CAUSE'
                   ELSE 'RELATED_TO'
                 END as rel_type
            MERGE (e1)-[r:INFERRED_FROM_FACT]->(e2)
            SET r.fact_id = f.id
            SET r.confidence = f.aggregate_confidence
            SET r.inferred_at = datetime()
            RETURN count(r) as created_relationships
        """,

        "get_fact_chains": """
            MATCH path = (e1)-[:PARTICIPATES_IN]->(f1:FactUnit)<-[:PARTICIPATES_IN]-(bridge)-[:PARTICIPATES_IN]->(f2:FactUnit)<-[:PARTICIPATES_IN]-(e2)
            WHERE e1.id = $entity_id OR e1.name = $entity_id
              AND e1 <> e2
              AND f1 <> f2
            RETURN
                e1.name as source,
                bridge.name as bridge_entity,
                e2.name as target,
                f1.fact_type as fact1_type,
                f2.fact_type as fact2_type,
                (f1.aggregate_confidence + f2.aggregate_confidence) / 2 as chain_confidence
            ORDER BY chain_confidence DESC
            LIMIT $limit
        """,

        "cleanup_low_confidence": """
            MATCH (f:FactUnit)
            WHERE f.aggregate_confidence < $threshold
              AND f.validated = false
            DETACH DELETE f
            RETURN count(*) as deleted
        """,
    }

    def __init__(self, neo4j_backend):
        """Initialize the bridge service.

        Args:
            neo4j_backend: Neo4j backend for graph operations
        """
        self.backend = neo4j_backend

    async def build_bridge_layer(
        self,
        limit: int = 10000,
        min_confidence: float = 0.5,
    ) -> BridgeStatistics:
        """Build the bridge layer from existing co-occurrences.

        Scans chunks for entity co-occurrences and creates FactUnits
        that act as hyperedges connecting related entities.

        Args:
            limit: Maximum number of chunks to process
            min_confidence: Minimum confidence threshold

        Returns:
            BridgeStatistics with creation metrics
        """
        logger.info(f"Building bridge layer from co-occurrences (limit={limit})")
        stats = BridgeStatistics()

        # Get co-occurrence contexts from chunks
        contexts = await self._get_co_occurrence_contexts(limit)
        logger.info(f"Found {len(contexts)} co-occurrence contexts")

        # Create FactUnits for valid contexts
        for context in contexts:
            context.analyze()

            if not context.is_fact_candidate:
                continue

            if context.avg_extraction_confidence < min_confidence:
                continue

            # Create FactUnit
            fact = context.to_fact_unit()
            if fact:
                await self._create_fact_unit(fact)
                stats.total_fact_units += 1
                stats.total_hyperedges += len(fact.participants)

                # Track by type
                fact_type = fact.fact_type.value
                stats.facts_by_type[fact_type] = stats.facts_by_type.get(fact_type, 0) + 1

        # Enrich with ontology mappings
        await self._enrich_with_ontology(stats)

        # Get final statistics from database
        db_stats = await self._get_database_statistics()
        stats.total_fact_units = db_stats.get("fact_count", stats.total_fact_units)
        stats.total_hyperedges = db_stats.get("edge_count", stats.total_hyperedges)
        stats.entities_with_facts = db_stats.get("entities_with_facts", 0)
        stats.avg_fact_confidence = db_stats.get("avg_confidence", 0.0) or 0.0

        logger.info(
            f"Bridge layer built: {stats.total_fact_units} facts, "
            f"{stats.total_hyperedges} hyperedges"
        )

        return stats

    async def _get_co_occurrence_contexts(self, limit: int) -> List[CoOccurrenceContext]:
        """Get co-occurrence contexts from chunks."""
        contexts = []

        try:
            results = await self.backend.query_raw(
                self.QUERIES["get_co_occurrences"],
                {"limit": limit}
            )

            for row in results:
                entities = [
                    EntityMention(
                        entity_id=e.get("id", ""),
                        entity_name=e.get("name", ""),
                        entity_type=e.get("type", "Unknown"),
                        chunk_id=row.get("chunk_id", ""),
                        extraction_confidence=e.get("confidence", 0.7),
                    )
                    for e in row.get("entities", [])
                ]

                context = CoOccurrenceContext(
                    chunk_id=row.get("chunk_id", ""),
                    document_id=row.get("document_id", ""),
                    entities=entities,
                    chunk_text=row.get("chunk_text", "")[:500],
                )
                contexts.append(context)

        except Exception as e:
            logger.error(f"Failed to get co-occurrences: {e}")

        return contexts

    async def _create_fact_unit(self, fact: FactUnit) -> bool:
        """Create a FactUnit node and its participation edges."""
        try:
            # Create the FactUnit node
            await self.backend.query_raw(
                self.QUERIES["create_fact_unit"],
                {
                    "id": fact.id,
                    "properties": fact.to_neo4j_properties(),
                }
            )

            # Create participation edges
            for i, participant in enumerate(fact.participants):
                role = fact.participant_roles.get(participant.entity_id, "participant")
                await self.backend.query_raw(
                    self.QUERIES["create_participation"],
                    {
                        "fact_id": fact.id,
                        "entity_id": participant.entity_id or participant.entity_name,
                        "role": role,
                        "position": i,
                        "confidence": participant.extraction_confidence,
                    }
                )

            return True

        except Exception as e:
            logger.warning(f"Failed to create FactUnit {fact.id}: {e}")
            return False

    async def _enrich_with_ontology(self, stats: BridgeStatistics) -> None:
        """Enrich FactUnits with ontology information."""
        try:
            # Get entities participating in facts
            results = await self.backend.query_raw(
                """
                MATCH (e)-[:PARTICIPATES_IN]->(f:FactUnit)
                WITH DISTINCT e
                RETURN e.name as name, labels(e) as labels, e.type as type
                LIMIT 1000
                """,
                {}
            )

            ontology_count = 0
            for row in results:
                entity_type = row.get("type") or (row.get("labels", ["Unknown"])[0])
                if is_known_type(entity_type):
                    ontology_count += 1

            stats.entities_with_ontology = ontology_count
            if results:
                stats.ontology_alignment_score = ontology_count / len(results)

        except Exception as e:
            logger.warning(f"Failed to enrich with ontology: {e}")

    async def _get_database_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics from database."""
        try:
            results = await self.backend.query_raw(
                self.QUERIES["get_bridge_statistics"],
                {}
            )
            return results[0] if results else {}
        except Exception as e:
            logger.warning(f"Failed to get statistics: {e}")
            return {}

    async def get_facts_for_entity(
        self,
        entity_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get all FactUnits involving an entity.

        Args:
            entity_id: Entity ID or name
            limit: Maximum facts to return

        Returns:
            List of facts with co-participants
        """
        try:
            results = await self.backend.query_raw(
                self.QUERIES["get_facts_for_entity"],
                {"entity_id": entity_id, "limit": limit}
            )

            facts = []
            for row in results:
                fact_node = row.get("fact", {})
                facts.append({
                    "fact_id": fact_node.get("id"),
                    "fact_type": fact_node.get("fact_type"),
                    "fact_text": fact_node.get("fact_text"),
                    "confidence": fact_node.get("aggregate_confidence"),
                    "source_chunk": fact_node.get("source_chunk_id"),
                    "co_participants": row.get("co_participants", []),
                })

            return facts

        except Exception as e:
            logger.error(f"Failed to get facts for {entity_id}: {e}")
            return []

    async def propagate_to_knowledge_graph(
        self,
        confidence_threshold: float = 0.7,
    ) -> int:
        """Propagate high-confidence facts to knowledge graph relationships.

        Creates INFERRED_FROM_FACT relationships between entities
        that share high-confidence FactUnits.

        Args:
            confidence_threshold: Minimum confidence for propagation

        Returns:
            Number of relationships created
        """
        try:
            results = await self.backend.query_raw(
                self.QUERIES["propagate_to_kg"],
                {"threshold": confidence_threshold}
            )
            created = results[0].get("created_relationships", 0) if results else 0
            logger.info(f"Propagated {created} relationships to knowledge graph")
            return created

        except Exception as e:
            logger.error(f"Failed to propagate to KG: {e}")
            return 0

    async def find_fact_chains(
        self,
        entity_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find chains of facts connecting entities through bridges.

        This discovers transitive relationships:
        Entity1 --[fact1]--> BridgeEntity --[fact2]--> Entity2

        Args:
            entity_id: Starting entity
            limit: Maximum chains to return

        Returns:
            List of fact chains with confidence
        """
        try:
            results = await self.backend.query_raw(
                self.QUERIES["get_fact_chains"],
                {"entity_id": entity_id, "limit": limit}
            )

            return [
                {
                    "source": row.get("source"),
                    "bridge": row.get("bridge_entity"),
                    "target": row.get("target"),
                    "fact1_type": row.get("fact1_type"),
                    "fact2_type": row.get("fact2_type"),
                    "chain_confidence": row.get("chain_confidence"),
                }
                for row in results
            ]

        except Exception as e:
            logger.error(f"Failed to find fact chains: {e}")
            return []

    async def cleanup_low_confidence_facts(
        self,
        threshold: float = 0.3,
    ) -> int:
        """Remove low-confidence unvalidated facts.

        Args:
            threshold: Facts below this confidence are removed

        Returns:
            Number of facts deleted
        """
        try:
            results = await self.backend.query_raw(
                self.QUERIES["cleanup_low_confidence"],
                {"threshold": threshold}
            )
            deleted = results[0].get("deleted", 0) if results else 0
            logger.info(f"Cleaned up {deleted} low-confidence facts")
            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup facts: {e}")
            return 0

    async def validate_fact(self, fact_id: str, validated: bool = True) -> bool:
        """Mark a fact as validated by user or system.

        Args:
            fact_id: The fact to validate
            validated: Validation status

        Returns:
            Success status
        """
        try:
            await self.backend.query_raw(
                """
                MATCH (f:FactUnit {id: $id})
                SET f.validated = $validated
                SET f.validation_count = coalesce(f.validation_count, 0) + 1
                SET f.validated_at = datetime()
                RETURN f
                """,
                {"id": fact_id, "validated": validated}
            )
            return True

        except Exception as e:
            logger.error(f"Failed to validate fact {fact_id}: {e}")
            return False

    async def get_bridge_report(self) -> Dict[str, Any]:
        """Generate a comprehensive bridge layer report.

        Returns:
            Report with statistics, coverage, and recommendations
        """
        stats = await self._get_database_statistics()

        # Get fact type distribution
        try:
            type_results = await self.backend.query_raw(
                """
                MATCH (f:FactUnit)
                RETURN f.fact_type as type, count(f) as count
                ORDER BY count DESC
                """,
                {}
            )
            facts_by_type = {
                row.get("type", "unknown"): row.get("count", 0)
                for row in type_results
            }
        except Exception:
            facts_by_type = {}

        # Get confidence distribution
        try:
            conf_results = await self.backend.query_raw(
                """
                MATCH (f:FactUnit)
                RETURN
                    CASE
                        WHEN f.aggregate_confidence >= 0.8 THEN 'high'
                        WHEN f.aggregate_confidence >= 0.5 THEN 'medium'
                        ELSE 'low'
                    END as confidence_level,
                    count(f) as count
                """,
                {}
            )
            confidence_dist = {
                row.get("confidence_level"): row.get("count", 0)
                for row in conf_results
            }
        except Exception:
            confidence_dist = {}

        # Generate recommendations
        recommendations = []

        fact_count = stats.get("fact_count", 0)
        if fact_count == 0:
            recommendations.append("Run build_bridge_layer() to create FactUnits from co-occurrences")
        elif fact_count < 100:
            recommendations.append("Low fact count - consider processing more documents")

        avg_confidence = stats.get("avg_confidence", 0) or 0
        if avg_confidence < 0.5:
            recommendations.append("Low average confidence - review extraction quality")

        if confidence_dist.get("high", 0) > fact_count * 0.3:
            recommendations.append("Good high-confidence fact ratio - ready for KG propagation")

        return {
            "generated_at": datetime.now().isoformat(),
            "statistics": {
                "total_fact_units": stats.get("fact_count", 0),
                "total_hyperedges": stats.get("edge_count", 0),
                "entities_with_facts": stats.get("entities_with_facts", 0),
                "avg_fact_confidence": round(avg_confidence, 4),
            },
            "facts_by_type": facts_by_type,
            "confidence_distribution": confidence_dist,
            "recommendations": recommendations,
        }


async def run_bridge_builder(
    neo4j_uri: str = None,
    neo4j_user: str = None,
    neo4j_password: str = None,
) -> BridgeStatistics:
    """Convenience function to build the bridge layer.

    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password

    Returns:
        BridgeStatistics with creation metrics
    """
    import os
    from infrastructure.neo4j_backend import Neo4jBackend

    uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
    password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")

    backend = Neo4jBackend(uri, user, password)

    try:
        service = HypergraphBridgeService(backend)
        stats = await service.build_bridge_layer()

        # Generate report
        report = await service.get_bridge_report()
        print("\n========== BRIDGE LAYER REPORT ==========")
        print(f"Total FactUnits: {report['statistics']['total_fact_units']}")
        print(f"Total Hyperedges: {report['statistics']['total_hyperedges']}")
        print(f"Entities with Facts: {report['statistics']['entities_with_facts']}")
        print(f"Avg Confidence: {report['statistics']['avg_fact_confidence']:.2%}")
        print("\nFacts by Type:")
        for fact_type, count in report.get("facts_by_type", {}).items():
            print(f"  {fact_type}: {count}")
        print("\nRecommendations:")
        for rec in report.get("recommendations", []):
            print(f"  - {rec}")

        return stats

    finally:
        await backend.close()


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build hypergraph bridge layer between Document and Knowledge graphs"
    )
    parser.add_argument(
        "--propagate",
        action="store_true",
        help="Propagate high-confidence facts to KG"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for propagation"
    )

    args = parser.parse_args()

    async def main():
        stats = await run_bridge_builder()

        if args.propagate:
            from infrastructure.neo4j_backend import Neo4jBackend
            import os

            backend = Neo4jBackend(
                os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                os.getenv("NEO4J_USERNAME", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "password"),
            )

            try:
                service = HypergraphBridgeService(backend)
                created = await service.propagate_to_knowledge_graph(args.threshold)
                print(f"\nPropagated {created} relationships to Knowledge Graph")
            finally:
                await backend.close()

    asyncio.run(main())
