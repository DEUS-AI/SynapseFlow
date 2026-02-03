#!/usr/bin/env python3
"""
Migrate Medical Entities from FalkorDB to Neo4j

This script migrates medical knowledge graph entities from FalkorDB to Neo4j
to consolidate everything in a single database for easier cross-graph queries.

Usage:
    python demos/migrate_medical_entities_to_neo4j.py [--batch-size 100]
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
import logging
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from falkordb import FalkorDB
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_section(text: str):
    """Print a formatted section header."""
    print(f"\n--- {text} ---")


def migrate_entities_and_relationships():
    """Migrate entities and relationships from FalkorDB to Neo4j."""
    print_header("Medical Knowledge Migration: FalkorDB → Neo4j")

    # Load environment
    load_dotenv()

    # Connect to FalkorDB
    print_section("Connecting to FalkorDB")
    falkor_db = FalkorDB(host='localhost', port=6379)
    falkor_graph = falkor_db.select_graph('medical_knowledge')
    print("✓ Connected to FalkorDB")

    # Connect to Neo4j
    print_section("Connecting to Neo4j")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    if '\n' in neo4j_uri:
        neo4j_uri = neo4j_uri.split('\n')[-1].strip()
    neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    print(f"✓ Connected to Neo4j at {neo4j_uri}")

    # Get entities from FalkorDB
    print_section("Fetching Medical Entities from FalkorDB")

    query = """
    MATCH (n)
    WHERE n.source_document IS NOT NULL
    RETURN
        n.name as name,
        n.type as type,
        n.description as description,
        n.confidence as confidence,
        n.source_document as source_document,
        n.category as category,
        n.layer as layer
    """

    result = falkor_graph.query(query)
    entities = []

    for row in result.result_set:
        entities.append({
            "name": row[0],
            "type": row[1],
            "description": row[2] if len(row) > 2 else "",
            "confidence": row[3] if len(row) > 3 else 0.5,
            "source_document": row[4] if len(row) > 4 else "",
            "category": row[5] if len(row) > 5 else "",
            "layer": row[6] if len(row) > 6 else "PERCEPTION"
        })

    print(f"✓ Found {len(entities)} medical entities")

    # Get relationships from FalkorDB
    print_section("Fetching Relationships from FalkorDB")

    rel_query = """
    MATCH (source)-[r]->(target)
    WHERE source.source_document IS NOT NULL
      AND target.source_document IS NOT NULL
    RETURN
        source.name as source_name,
        type(r) as rel_type,
        target.name as target_name,
        r.description as description
    """

    rel_result = falkor_graph.query(rel_query)
    relationships = []

    for row in rel_result.result_set:
        relationships.append({
            "source_name": row[0],
            "rel_type": row[1],
            "target_name": row[2],
            "description": row[3] if len(row) > 3 else ""
        })

    print(f"✓ Found {len(relationships)} relationships")

    # Migrate to Neo4j
    print_section("Migrating to Neo4j")

    with neo4j_driver.session() as session:
        # Create entities
        entities_created = 0
        for entity in entities:
            try:
                session.run(
                    """
                    MERGE (n:MedicalEntity {name: $name})
                    SET n.type = $type,
                        n.description = $description,
                        n.confidence = $confidence,
                        n.source_document = $source_document,
                        n.category = $category,
                        n.layer = $layer,
                        n.migrated_at = $migrated_at
                    """,
                    name=entity["name"],
                    type=entity["type"],
                    description=entity["description"],
                    confidence=entity["confidence"],
                    source_document=entity["source_document"],
                    category=entity["category"],
                    layer=entity["layer"],
                    migrated_at=datetime.now().isoformat()
                )
                entities_created += 1

                if entities_created % 50 == 0:
                    print(f"  Migrated {entities_created}/{len(entities)} entities...")

            except Exception as e:
                logger.error(f"Failed to migrate entity {entity['name']}: {e}")

        print(f"✓ Migrated {entities_created} entities")

        # Create relationships
        relationships_created = 0
        for rel in relationships:
            try:
                session.run(
                    f"""
                    MATCH (source:MedicalEntity {{name: $source_name}})
                    MATCH (target:MedicalEntity {{name: $target_name}})
                    MERGE (source)-[r:{rel['rel_type']}]->(target)
                    SET r.description = $description,
                        r.migrated_at = $migrated_at
                    """,
                    source_name=rel["source_name"],
                    target_name=rel["target_name"],
                    description=rel["description"],
                    migrated_at=datetime.now().isoformat()
                )
                relationships_created += 1

                if relationships_created % 50 == 0:
                    print(f"  Migrated {relationships_created}/{len(relationships)} relationships...")

            except Exception as e:
                logger.error(f"Failed to migrate relationship: {e}")

        print(f"✓ Migrated {relationships_created} relationships")

    # Verify migration
    print_section("Verification")

    with neo4j_driver.session() as session:
        # Count medical entities
        result = session.run("MATCH (n:MedicalEntity) RETURN count(n) as count")
        medical_count = result.single()["count"]

        # Count relationships
        result = session.run("MATCH (n:MedicalEntity)-[r]->() RETURN count(r) as count")
        rel_count = result.single()["count"]

        # Count data entities (from DDAs)
        result = session.run("MATCH (n) WHERE n:Table OR n:Column RETURN count(n) as count")
        data_count = result.single()["count"]

        print(f"\n  Neo4j Status:")
        print(f"    Medical Entities: {medical_count}")
        print(f"    Medical Relationships: {rel_count}")
        print(f"    Data Entities (DDAs): {data_count}")
        print(f"    Total: {medical_count + data_count} entities")

    neo4j_driver.close()
    print_header("Migration Complete")

    return entities_created, relationships_created


if __name__ == "__main__":
    entities, relationships = migrate_entities_and_relationships()
    print(f"\n✅ Successfully migrated {entities} entities and {relationships} relationships")
    print(f"✅ Neo4j is now the unified backend for medical KG + DDA metadata")
