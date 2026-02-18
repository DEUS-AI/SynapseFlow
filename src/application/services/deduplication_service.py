"""Batch entity deduplication service.

Detects and merges duplicate entities in the knowledge graph
by case-insensitive exact name matching within the same type,
plus cross-type detection via semantic normalization.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DuplicatePair:
    """A pair of entities identified as duplicates."""

    entity_a_id: str
    entity_a_name: str
    entity_b_id: str
    entity_b_name: str
    entity_type: str
    a_relationship_count: int = 0
    b_relationship_count: int = 0
    a_confidence: float = 0.0
    b_confidence: float = 0.0


@dataclass
class MergePlan:
    """Plan for merging a duplicate pair."""

    winner_id: str
    winner_name: str
    loser_id: str
    loser_name: str
    entity_type: str
    rationale: str


@dataclass
class MergeSummary:
    """Summary of a completed deduplication execution."""

    total_merged: int = 0
    total_relationships_transferred: int = 0
    batch_id: str = ""
    details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CrossTypeDuplicateGroup:
    """A group of entities with the same canonical name but different types."""

    canonical_form: str
    entities: list[dict[str, Any]]
    entity_count: int


FETCH_ALL_ENTITIES_QUERY = """
MATCH (n)
WHERE n.name IS NOT NULL
  AND n.type IS NOT NULL
  AND NOT coalesce(n._merged_into, '') <> ''
  AND NOT coalesce(n._is_structural, false)
  AND NOT coalesce(n._dedup_skip, false)
WITH n, size([(n)-[]-() | 1]) AS rel_count
RETURN n.id AS id, n.name AS name, n.type AS type, rel_count
ORDER BY n.name
"""

DISMISS_ENTITIES_QUERY = """
UNWIND $entity_ids AS eid
MATCH (n {id: eid})
SET n._dedup_skip = true
RETURN count(n) AS dismissed
"""

UNDISMISS_ENTITIES_QUERY = """
UNWIND $entity_ids AS eid
MATCH (n {id: eid})
REMOVE n._dedup_skip
RETURN count(n) AS undismissed
"""

DETECT_DUPLICATES_QUERY = """
MATCH (a), (b)
WHERE a.type = b.type
  AND a.type IS NOT NULL
  AND toLower(trim(a.name)) = toLower(trim(b.name))
  AND a.name IS NOT NULL
  AND id(a) < id(b)
  AND NOT coalesce(a._merged_into, '') <> ''
  AND NOT coalesce(b._merged_into, '') <> ''
  AND NOT coalesce(a._is_structural, false)
  AND NOT coalesce(b._is_structural, false)
  AND NOT coalesce(a._dedup_skip, false)
  AND NOT coalesce(b._dedup_skip, false)
WITH a, b,
     size([(a)-[]-() | 1]) AS a_rels,
     size([(b)-[]-() | 1]) AS b_rels
RETURN a.id AS a_id, a.name AS a_name,
       b.id AS b_id, b.name AS b_name,
       a.type AS type,
       a_rels, b_rels,
       coalesce(a.confidence, 0.0) AS a_confidence,
       coalesce(b.confidence, 0.0) AS b_confidence
ORDER BY type, a.name
"""

TRANSFER_INCOMING_RELS_QUERY = """
MATCH (source)-[r]->(loser:Entity {id: $loser_id})
WHERE source.id <> $winner_id
WITH source, r, type(r) AS rel_type
MATCH (winner:Entity {id: $winner_id})
WHERE NOT EXISTS {
    MATCH (source)-[existing]->(winner)
    WHERE type(existing) = rel_type
}
CALL apoc.create.relationship(source, rel_type, properties(r), winner) YIELD rel
DELETE r
RETURN count(rel) AS transferred
"""

TRANSFER_OUTGOING_RELS_QUERY = """
MATCH (loser:Entity {id: $loser_id})-[r]->(target)
WHERE target.id <> $winner_id
WITH target, r, type(r) AS rel_type
MATCH (winner:Entity {id: $winner_id})
WHERE NOT EXISTS {
    MATCH (winner)-[existing]->(target)
    WHERE type(existing) = rel_type
}
CALL apoc.create.relationship(winner, rel_type, properties(r), target) YIELD rel
DELETE r
RETURN count(rel) AS transferred
"""

DELETE_REMAINING_RELS_QUERY = """
MATCH (loser:Entity {id: $loser_id})-[r]-()
DELETE r
RETURN count(r) AS deleted
"""

MARK_MERGED_QUERY = """
MATCH (loser:Entity {id: $loser_id})
SET loser._merged_into = $winner_id,
    loser._merged_date = datetime(),
    loser._dedup_batch = $batch_id
RETURN loser.id AS marked
"""

DELETE_LOSER_QUERY = """
MATCH (loser:Entity {id: $loser_id})
WHERE loser._merged_into IS NOT NULL
DELETE loser
RETURN count(loser) AS deleted
"""


class DeduplicationService:
    """Batch entity deduplication for the knowledge graph."""

    def __init__(self, driver):
        """Initialize with a Neo4j async driver.

        Args:
            driver: Neo4j async driver instance.
        """
        self.driver = driver

    async def detect_duplicates(self, database: str = "neo4j") -> list[DuplicatePair]:
        """Detect case-insensitive exact name duplicates within the same type.

        Returns:
            List of DuplicatePair objects.
        """
        async with self.driver.session(database=database) as session:
            result = await session.run(DETECT_DUPLICATES_QUERY)
            pairs = []
            async for record in result:
                pairs.append(DuplicatePair(
                    entity_a_id=record["a_id"],
                    entity_a_name=record["a_name"],
                    entity_b_id=record["b_id"],
                    entity_b_name=record["b_name"],
                    entity_type=record["type"],
                    a_relationship_count=record["a_rels"],
                    b_relationship_count=record["b_rels"],
                    a_confidence=record["a_confidence"],
                    b_confidence=record["b_confidence"],
                ))
            return pairs

    def create_merge_plan(self, pairs: list[DuplicatePair]) -> list[MergePlan]:
        """Create a merge plan selecting winner/loser for each pair.

        Winner selection: most relationships > highest confidence > entity A.

        Returns:
            List of MergePlan objects.
        """
        plans = []
        for pair in pairs:
            # Select winner: most relationships, then highest confidence
            a_wins = True
            rationale_parts = []

            if pair.a_relationship_count > pair.b_relationship_count:
                rationale_parts.append(
                    f"A has more relationships ({pair.a_relationship_count} vs {pair.b_relationship_count})"
                )
            elif pair.b_relationship_count > pair.a_relationship_count:
                a_wins = False
                rationale_parts.append(
                    f"B has more relationships ({pair.b_relationship_count} vs {pair.a_relationship_count})"
                )
            elif pair.a_confidence >= pair.b_confidence:
                rationale_parts.append(
                    f"Equal relationships; A has higher/equal confidence ({pair.a_confidence} vs {pair.b_confidence})"
                )
            else:
                a_wins = False
                rationale_parts.append(
                    f"Equal relationships; B has higher confidence ({pair.b_confidence} vs {pair.a_confidence})"
                )

            if a_wins:
                plans.append(MergePlan(
                    winner_id=pair.entity_a_id,
                    winner_name=pair.entity_a_name,
                    loser_id=pair.entity_b_id,
                    loser_name=pair.entity_b_name,
                    entity_type=pair.entity_type,
                    rationale="; ".join(rationale_parts),
                ))
            else:
                plans.append(MergePlan(
                    winner_id=pair.entity_b_id,
                    winner_name=pair.entity_b_name,
                    loser_id=pair.entity_a_id,
                    loser_name=pair.entity_a_name,
                    entity_type=pair.entity_type,
                    rationale="; ".join(rationale_parts),
                ))

        return plans

    async def execute_merge(
        self, plan: list[MergePlan], database: str = "neo4j"
    ) -> MergeSummary:
        """Execute the merge plan — transfer relationships and delete losers.

        Args:
            plan: List of MergePlan objects from create_merge_plan().
            database: Neo4j database name.

        Returns:
            MergeSummary with counts and details.
        """
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = MergeSummary(batch_id=batch_id)

        async with self.driver.session(database=database) as session:
            for merge in plan:
                params = {
                    "winner_id": merge.winner_id,
                    "loser_id": merge.loser_id,
                    "batch_id": batch_id,
                }
                transferred = 0

                # Transfer incoming relationships
                result = await session.run(TRANSFER_INCOMING_RELS_QUERY, params)
                record = await result.single()
                if record:
                    transferred += record["transferred"]

                # Transfer outgoing relationships
                result = await session.run(TRANSFER_OUTGOING_RELS_QUERY, params)
                record = await result.single()
                if record:
                    transferred += record["transferred"]

                # Delete remaining duplicate relationships
                await session.run(DELETE_REMAINING_RELS_QUERY, params)

                # Mark loser as merged
                await session.run(MARK_MERGED_QUERY, params)

                # Delete loser node
                await session.run(DELETE_LOSER_QUERY, params)

                summary.total_merged += 1
                summary.total_relationships_transferred += transferred
                summary.details.append({
                    "winner": merge.winner_id,
                    "loser": merge.loser_id,
                    "type": merge.entity_type,
                    "relationships_transferred": transferred,
                })

        return summary

    async def detect_cross_type_duplicates(
        self, database: str = "neo4j"
    ) -> list[CrossTypeDuplicateGroup]:
        """Detect entities with the same canonical name but different types.

        Uses SemanticNormalizer for canonical form computation.

        Returns:
            List of CrossTypeDuplicateGroup objects.
        """
        from application.services.semantic_normalizer import SemanticNormalizer

        normalizer = SemanticNormalizer()

        async with self.driver.session(database=database) as session:
            result = await session.run(FETCH_ALL_ENTITIES_QUERY)
            entities = [record.data() async for record in result]

        # Group by canonical form
        canonical_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entity in entities:
            canonical = normalizer.normalize(entity["name"])
            canonical_groups[canonical].append(entity)

        # Return only groups spanning multiple types
        groups = []
        for canonical, group_entities in canonical_groups.items():
            if len(group_entities) < 2:
                continue
            types_in_group = {e["type"] for e in group_entities}
            if len(types_in_group) < 2:
                continue
            groups.append(CrossTypeDuplicateGroup(
                canonical_form=canonical,
                entities=[
                    {
                        "id": e["id"],
                        "name": e["name"],
                        "type": e["type"],
                        "relationship_count": e["rel_count"],
                    }
                    for e in group_entities
                ],
                entity_count=len(group_entities),
            ))

        return groups

    async def dismiss_entities(
        self, entity_ids: list[str], undo: bool = False, database: str = "neo4j"
    ) -> int:
        """Set or remove _dedup_skip on entities.

        Args:
            entity_ids: List of entity IDs to dismiss/undismiss.
            undo: If True, remove the _dedup_skip flag instead of setting it.
            database: Neo4j database name.

        Returns:
            Number of entities affected.
        """
        query = UNDISMISS_ENTITIES_QUERY if undo else DISMISS_ENTITIES_QUERY
        async with self.driver.session(database=database) as session:
            result = await session.run(query, {"entity_ids": entity_ids})
            record = await result.single()
            return record["undismissed" if undo else "dismissed"] if record else 0
