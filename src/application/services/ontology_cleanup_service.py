"""Ontology Cleanup Service.

Marks structural and noise entities for exclusion from ontology coverage calculations.
This service ensures accurate coverage metrics by separating:
- Structural entities (Chunk, Document, DocumentQuality) - infrastructure, not knowledge
- Noise entities (stopwords, short strings) - extraction artifacts

Usage:
    service = OntologyCleanupService(neo4j_driver)
    results = await service.mark_structural_entities()
    results = await service.mark_noise_entities()
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# Structural entity labels that should be excluded from coverage
STRUCTURAL_LABELS = {
    "Chunk",
    "StructuralChunk",
    "Document",
    "DocumentQuality",
    "ExtractedEntity",  # Raw extractions before validation
}

# Stopwords and noise patterns
STOPWORDS = {
    "the", "a", "an", "and", "or", "is", "are", "was", "were",
    "this", "that", "these", "those", "it", "its",
    "however", "therefore", "thus", "hence",
    "also", "although", "because", "since", "while",
    "but", "yet", "so", "for", "nor",
    "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "can",
    "not", "no", "none", "all", "any", "some",
    "of", "in", "on", "at", "to", "from", "by", "with",
    "as", "if", "then", "else", "when", "where", "which", "who",
}

# Minimum entity name length to be considered valid
MIN_ENTITY_NAME_LENGTH = 3


class OntologyCleanupService:
    """Service for marking entities for ontology exclusion."""

    def __init__(self, driver):
        """Initialize with Neo4j driver.

        Args:
            driver: Async Neo4j driver instance
        """
        self.driver = driver

    async def mark_structural_entities(self, dry_run: bool = False) -> Dict[str, Any]:
        """Mark structural entities for exclusion from ontology coverage.

        Args:
            dry_run: If True, only count entities without marking them

        Returns:
            Statistics about marked entities
        """
        labels_str = ", ".join(f"'{label}'" for label in STRUCTURAL_LABELS)

        if dry_run:
            query = f"""
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN [{labels_str}])
            WITH labels(n) as nodeLabels, count(n) as count
            UNWIND nodeLabels as label
            WITH label, sum(count) as total
            WHERE label IN [{labels_str}]
            RETURN label, total
            ORDER BY total DESC
            """
        else:
            query = f"""
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN [{labels_str}])
              AND NOT coalesce(n._is_structural, false)
            SET n._is_structural = true,
                n._exclude_from_ontology = true,
                n._marked_structural_at = datetime()
            RETURN count(n) as marked_count
            """

        async with self.driver.session() as session:
            result = await session.run(query)
            records = [record async for record in result]

        if dry_run:
            by_label = {r["label"]: r["total"] for r in records}
            total = sum(by_label.values())
            return {
                "dry_run": True,
                "structural_entities_found": total,
                "by_label": by_label,
            }
        else:
            marked = records[0]["marked_count"] if records else 0
            logger.info(f"Marked {marked} structural entities for ontology exclusion")
            return {
                "dry_run": False,
                "marked_count": marked,
                "structural_labels": list(STRUCTURAL_LABELS),
            }

    async def mark_noise_entities(self, dry_run: bool = False) -> Dict[str, Any]:
        """Mark stopword and short-name entities as noise.

        Args:
            dry_run: If True, only count entities without marking them

        Returns:
            Statistics about marked noise entities
        """
        stopwords_str = ", ".join(f"'{word}'" for word in STOPWORDS)

        if dry_run:
            query = f"""
            MATCH (e)
            WHERE e.name IS NOT NULL
              AND NOT coalesce(e._is_structural, false)
              AND (
                size(e.name) < {MIN_ENTITY_NAME_LENGTH}
                OR toLower(trim(e.name)) IN [{stopwords_str}]
              )
            WITH CASE
                WHEN size(e.name) < {MIN_ENTITY_NAME_LENGTH} THEN 'short_name'
                ELSE 'stopword'
            END as reason, count(e) as count
            RETURN reason, count
            """
        else:
            query = f"""
            MATCH (e)
            WHERE e.name IS NOT NULL
              AND NOT coalesce(e._is_structural, false)
              AND NOT coalesce(e._is_noise, false)
              AND (
                size(e.name) < {MIN_ENTITY_NAME_LENGTH}
                OR toLower(trim(e.name)) IN [{stopwords_str}]
              )
            SET e._is_noise = true,
                e._exclude_from_ontology = true,
                e._noise_reason = CASE
                    WHEN size(e.name) < {MIN_ENTITY_NAME_LENGTH} THEN 'short_name'
                    ELSE 'stopword'
                END,
                e._marked_noise_at = datetime()
            RETURN count(e) as marked_count
            """

        async with self.driver.session() as session:
            result = await session.run(query)
            records = [record async for record in result]

        if dry_run:
            by_reason = {r["reason"]: r["count"] for r in records}
            total = sum(by_reason.values())
            return {
                "dry_run": True,
                "noise_entities_found": total,
                "by_reason": by_reason,
            }
        else:
            marked = records[0]["marked_count"] if records else 0
            logger.info(f"Marked {marked} noise entities for ontology exclusion")
            return {
                "dry_run": False,
                "marked_count": marked,
                "stopword_count": len(STOPWORDS),
                "min_name_length": MIN_ENTITY_NAME_LENGTH,
            }

    async def get_exclusion_statistics(self) -> Dict[str, Any]:
        """Get statistics about excluded entities.

        Returns:
            Breakdown of excluded entities by type
        """
        query = """
        MATCH (n)
        WHERE n._exclude_from_ontology = true
        WITH
            CASE WHEN n._is_structural = true THEN 'structural' ELSE 'noise' END as exclusion_type,
            labels(n) as nodeLabels
        WITH exclusion_type, head(nodeLabels) as primary_label, count(*) as count
        RETURN exclusion_type, primary_label, count
        ORDER BY exclusion_type, count DESC
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            records = [record async for record in result]

        structural = {}
        noise = {}

        for r in records:
            if r["exclusion_type"] == "structural":
                structural[r["primary_label"]] = r["count"]
            else:
                noise[r["primary_label"]] = r["count"]

        return {
            "total_excluded": sum(structural.values()) + sum(noise.values()),
            "structural": {
                "total": sum(structural.values()),
                "by_label": structural,
            },
            "noise": {
                "total": sum(noise.values()),
                "by_label": noise,
            },
        }

    async def calculate_adjusted_coverage(self) -> Dict[str, Any]:
        """Calculate ontology coverage excluding structural and noise entities.

        Returns:
            Coverage metrics for knowledge entities only
        """
        query = """
        MATCH (n)
        WHERE n.id IS NOT NULL
        WITH n,
             coalesce(n._exclude_from_ontology, false) as excluded,
             coalesce(n._ontology_mapped, false) as mapped
        WITH
            sum(CASE WHEN NOT excluded THEN 1 ELSE 0 END) as knowledge_entities,
            sum(CASE WHEN NOT excluded AND mapped THEN 1 ELSE 0 END) as mapped_entities,
            sum(CASE WHEN excluded THEN 1 ELSE 0 END) as excluded_entities,
            count(n) as total_entities
        RETURN
            total_entities,
            knowledge_entities,
            mapped_entities,
            excluded_entities,
            CASE WHEN knowledge_entities > 0
                THEN round(toFloat(mapped_entities) / knowledge_entities * 100, 2)
                ELSE 0.0
            END as coverage_pct
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            record = await result.single()

        if not record:
            return {"error": "No data found"}

        return {
            "total_entities": record["total_entities"],
            "knowledge_entities": record["knowledge_entities"],
            "mapped_entities": record["mapped_entities"],
            "excluded_entities": record["excluded_entities"],
            "coverage_pct": record["coverage_pct"],
            "timestamp": datetime.now().isoformat(),
        }

    async def reset_exclusions(self, reset_structural: bool = True, reset_noise: bool = True) -> Dict[str, Any]:
        """Reset exclusion flags (for rollback).

        Args:
            reset_structural: Reset structural entity flags
            reset_noise: Reset noise entity flags

        Returns:
            Count of entities reset
        """
        results = {"structural_reset": 0, "noise_reset": 0}

        if reset_structural:
            query = """
            MATCH (n)
            WHERE n._is_structural = true
            REMOVE n._is_structural, n._exclude_from_ontology, n._marked_structural_at
            RETURN count(n) as reset_count
            """
            async with self.driver.session() as session:
                result = await session.run(query)
                record = await result.single()
                results["structural_reset"] = record["reset_count"] if record else 0

        if reset_noise:
            query = """
            MATCH (n)
            WHERE n._is_noise = true
            REMOVE n._is_noise, n._exclude_from_ontology, n._noise_reason, n._marked_noise_at
            RETURN count(n) as reset_count
            """
            async with self.driver.session() as session:
                result = await session.run(query)
                record = await result.single()
                results["noise_reset"] = record["reset_count"] if record else 0

        logger.info(f"Reset exclusions: {results}")
        return results

    async def get_top_noise_entities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top noise entities by connection count.

        Args:
            limit: Maximum number of entities to return

        Returns:
            List of noise entities with their connection counts
        """
        query = f"""
        MATCH (e)
        WHERE e._is_noise = true
        OPTIONAL MATCH (e)-[r]-()
        WITH e, count(r) as connections
        RETURN e.name as name, e.type as type, e._noise_reason as reason, connections
        ORDER BY connections DESC
        LIMIT {limit}
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            records = [record async for record in result]

        return [
            {
                "name": r["name"],
                "type": r["type"],
                "reason": r["reason"],
                "connections": r["connections"],
            }
            for r in records
        ]


async def run_full_cleanup(driver, dry_run: bool = True) -> Dict[str, Any]:
    """Run the complete cleanup process.

    Args:
        driver: Neo4j driver
        dry_run: If True, only report what would be done

    Returns:
        Complete cleanup results
    """
    service = OntologyCleanupService(driver)

    results = {
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
    }

    # Step 1: Mark structural entities
    structural_results = await service.mark_structural_entities(dry_run=dry_run)
    results["structural"] = structural_results

    # Step 2: Mark noise entities
    noise_results = await service.mark_noise_entities(dry_run=dry_run)
    results["noise"] = noise_results

    # Step 3: Calculate adjusted coverage
    if not dry_run:
        coverage = await service.calculate_adjusted_coverage()
        results["coverage"] = coverage

    return results
