"""
Migration script to add layer property to existing nodes in Neo4j.

This script implements the 4-layer Knowledge Graph architecture:
- PERCEPTION: Raw extracted data from PDFs
- SEMANTIC: Validated concepts linked to ontologies
- REASONING: Inferred knowledge with provenance
- APPLICATION: Query patterns and cached results

Run with: uv run python scripts/migration/migrate_layers.py
"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Dict, List, Tuple

from neo4j import AsyncGraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LayerMigration:
    """Migrates existing Neo4j nodes to the 4-layer architecture."""

    # Node labels that belong to each layer
    # DIKW Pyramid alignment:
    # - PERCEPTION (Data): Raw extracted, unvalidated entities
    # - SEMANTIC (Information): Validated, ontology-mapped entities
    # - REASONING (Knowledge): Inferred relationships, business rules
    # - APPLICATION (Wisdom): Query patterns, user feedback, cached insights
    LAYER_ASSIGNMENTS = {
        "PERCEPTION": [
            # Medical entities from PDFs (raw extractions)
            "MedicalEntity",
            "Entity",
            "PDFSource",
            "RawConcept",
            "Chunk",
            "Document",
            # DDA entities (start here, promoted after validation)
            "Catalog",
            "Schema",
            "Table",
            "Column",
            "DataType",
            # Lowercase variants from Graphiti LLM extraction
            "document",
            "unknown",
            "resource",
            "concept",
        ],
        "SEMANTIC": [
            # Validated medical concepts with ontology mappings
            "SemanticConcept",
            "Disease",
            "Treatment",
            "Drug",
            "Symptom",
            "Gene",
            "Pathway",
            "Diagnosis",
            "Medication",
            "Allergy",
            "BusinessConcept",
            # Lowercase variants from Graphiti LLM extraction
            "medication",
            "treatment",
            "medical_condition",
            "body_part",
            "profession",
            # Note: Catalog/Schema/Table/Column promoted here after validation
        ],
        "REASONING": [
            # Inferred knowledge and executable rules
            "InferredConcept",
            "QualityRule",
            "InferenceResult",
            "DataQualityRule",
            "DataQualityScore",
            "Constraint",
            "Policy",
            "BusinessRule",  # Executable business rules from DDAs
        ],
        "APPLICATION": [
            # Query patterns, user feedback, cached results
            "QueryPattern",
            "CachedResult",
            "UsageMetric",
            "Patient",
            "Session",
            "Message",
            "UserFeedback",
        ],
        # Note: LayerTransition and __User__ are audit/system nodes - they should NOT
        # have a layer property as they are metadata, not knowledge entities.
        # They are excluded from layer assignment to keep the KG visualization clean.
    }

    # Required indexes for layer-based queries
    # Note: Neo4j requires indexes to be on specific labels, not generic (n)
    INDEXES = [
        # Entity layer indexes
        ("idx_entity_layer", "CREATE INDEX idx_entity_layer IF NOT EXISTS FOR (n:Entity) ON (n.layer)"),
        ("idx_table_layer", "CREATE INDEX idx_table_layer IF NOT EXISTS FOR (n:Table) ON (n.layer)"),
        ("idx_catalog_layer", "CREATE INDEX idx_catalog_layer IF NOT EXISTS FOR (n:Catalog) ON (n.layer)"),
        # Confidence indexes for promotion queries
        ("idx_entity_confidence", """
            CREATE INDEX idx_entity_confidence IF NOT EXISTS
            FOR (n:Entity) ON (n.layer, n.confidence)
        """),
        ("idx_table_confidence", """
            CREATE INDEX idx_table_confidence IF NOT EXISTS
            FOR (n:Table) ON (n.layer, n.confidence)
        """),
        # Ontology lookups
        ("idx_ontology_codes", """
            CREATE INDEX idx_ontology_codes IF NOT EXISTS
            FOR (n:SemanticConcept) ON (n.ontology_codes)
        """),
        ("idx_canonical_name", """
            CREATE INDEX idx_canonical_name IF NOT EXISTS
            FOR (n:SemanticConcept) ON (n.canonical_name)
        """),
        # Application layer
        ("idx_query_frequency", """
            CREATE INDEX idx_query_frequency IF NOT EXISTS
            FOR (n:QueryPattern) ON (n.query_frequency)
        """),
        # Layer transition tracking
        ("idx_layer_transition", """
            CREATE INDEX idx_layer_transition IF NOT EXISTS
            FOR (n:LayerTransition) ON (n.completed_at)
        """),
    ]

    def __init__(self, uri: str, username: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        self.stats = {
            "nodes_updated": 0,
            "indexes_created": 0,
            "errors": [],
        }

    async def close(self):
        await self.driver.close()

    async def run_migration(self, dry_run: bool = False) -> Dict:
        """
        Run the complete layer migration.

        Args:
            dry_run: If True, only report what would be done without making changes.

        Returns:
            Dictionary with migration statistics.
        """
        logger.info(f"Starting layer migration (dry_run={dry_run})")
        start_time = datetime.now()

        try:
            # Step 1: Create indexes
            await self._create_indexes(dry_run)

            # Step 2: Migrate nodes by label
            await self._migrate_nodes_by_label(dry_run)

            # Step 3: Migrate remaining nodes without layer
            await self._migrate_unlabeled_nodes(dry_run)

            # Step 4: Verify migration
            layer_counts = await self._verify_migration()

            elapsed = (datetime.now() - start_time).total_seconds()
            self.stats["elapsed_seconds"] = elapsed
            self.stats["layer_counts"] = layer_counts

            logger.info(f"Migration completed in {elapsed:.2f}s")
            logger.info(f"Layer distribution: {layer_counts}")

            return self.stats

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.stats["errors"].append(str(e))
            raise

    async def _create_indexes(self, dry_run: bool):
        """Create required indexes for layer-based queries."""
        logger.info("Creating indexes...")

        async with self.driver.session() as session:
            for index_name, index_query in self.INDEXES:
                if dry_run:
                    logger.info(f"[DRY RUN] Would create index: {index_name}")
                    continue

                try:
                    await session.run(index_query)
                    self.stats["indexes_created"] += 1
                    logger.info(f"Created/verified index: {index_name}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Failed to create index {index_name}: {e}")
                        self.stats["errors"].append(f"Index {index_name}: {e}")

    async def _migrate_nodes_by_label(self, dry_run: bool):
        """Migrate nodes based on their labels to appropriate layers."""
        logger.info("Migrating nodes by label...")

        async with self.driver.session() as session:
            for layer, labels in self.LAYER_ASSIGNMENTS.items():
                for label in labels:
                    # Count nodes to migrate
                    count_query = f"""
                        MATCH (n:{label})
                        WHERE n.layer IS NULL
                        RETURN count(n) as count
                    """
                    result = await session.run(count_query)
                    record = await result.single()
                    count = record["count"] if record else 0

                    if count == 0:
                        continue

                    if dry_run:
                        logger.info(f"[DRY RUN] Would migrate {count} {label} nodes to {layer}")
                        continue

                    # Migrate nodes
                    # PERCEPTION layer nodes get pending_validation status
                    # Other layers are considered already validated (existing data)
                    migrate_query = f"""
                        MATCH (n:{label})
                        WHERE n.layer IS NULL
                        SET n.layer = $layer,
                            n.status = CASE WHEN $layer = 'PERCEPTION' THEN 'pending_validation' ELSE 'validated' END,
                            n.layer_assigned_at = datetime(),
                            n.layer_assignment_method = 'migration_by_label',
                            n.confidence = COALESCE(n.confidence, CASE WHEN $layer = 'PERCEPTION' THEN 0.7 ELSE 0.9 END)
                        RETURN count(n) as migrated
                    """
                    result = await session.run(migrate_query, {"layer": layer})
                    record = await result.single()
                    migrated = record["migrated"] if record else 0

                    self.stats["nodes_updated"] += migrated
                    logger.info(f"Migrated {migrated} {label} nodes to {layer}")

    async def _migrate_unlabeled_nodes(self, dry_run: bool):
        """Migrate nodes without specific labels to PERCEPTION as default."""
        logger.info("Migrating remaining unlabeled nodes...")

        async with self.driver.session() as session:
            # Count remaining nodes without layer
            count_query = """
                MATCH (n)
                WHERE n.layer IS NULL
                RETURN count(n) as count
            """
            result = await session.run(count_query)
            record = await result.single()
            count = record["count"] if record else 0

            if count == 0:
                logger.info("No unlabeled nodes to migrate")
                return

            if dry_run:
                logger.info(f"[DRY RUN] Would migrate {count} unlabeled nodes to PERCEPTION")
                return

            # Default to PERCEPTION for any unclassified nodes
            migrate_query = """
                MATCH (n)
                WHERE n.layer IS NULL
                SET n.layer = 'PERCEPTION',
                    n.status = 'pending_validation',
                    n.layer_assigned_at = datetime(),
                    n.layer_assignment_method = 'migration_default'
                RETURN count(n) as migrated
            """
            result = await session.run(migrate_query)
            record = await result.single()
            migrated = record["migrated"] if record else 0

            self.stats["nodes_updated"] += migrated
            logger.info(f"Migrated {migrated} unlabeled nodes to PERCEPTION")

    async def _verify_migration(self) -> Dict[str, int]:
        """Verify migration by counting nodes per layer."""
        logger.info("Verifying migration...")

        async with self.driver.session() as session:
            query = """
                MATCH (n)
                RETURN n.layer as layer, count(n) as count
                ORDER BY layer
            """
            result = await session.run(query)
            records = await result.data()

            layer_counts = {r["layer"]: r["count"] for r in records}
            return layer_counts

    async def rollback(self):
        """Remove layer property from all nodes (use with caution)."""
        logger.warning("Rolling back layer migration...")

        async with self.driver.session() as session:
            query = """
                MATCH (n)
                WHERE n.layer IS NOT NULL
                REMOVE n.layer, n.layer_assigned_at, n.layer_assignment_method, n.status
                RETURN count(n) as count
            """
            result = await session.run(query)
            record = await result.single()
            count = record["count"] if record else 0

            logger.info(f"Rolled back {count} nodes")
            return count


async def main():
    """Main entry point for the migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Neo4j nodes to 4-layer architecture")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--rollback", action="store_true", help="Remove layer property from all nodes")
    args = parser.parse_args()

    # Get Neo4j connection from environment
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    migration = LayerMigration(uri, username, password)

    try:
        if args.rollback:
            await migration.rollback()
        else:
            stats = await migration.run_migration(dry_run=args.dry_run)
            print("\n=== Migration Statistics ===")
            print(f"Nodes updated: {stats['nodes_updated']}")
            print(f"Indexes created: {stats['indexes_created']}")
            print(f"Elapsed time: {stats.get('elapsed_seconds', 0):.2f}s")
            print(f"Layer distribution: {stats.get('layer_counts', {})}")
            if stats["errors"]:
                print(f"Errors: {stats['errors']}")
    finally:
        await migration.close()


if __name__ == "__main__":
    asyncio.run(main())
