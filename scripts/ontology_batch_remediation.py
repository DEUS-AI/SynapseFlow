#!/usr/bin/env python
"""Ontology Batch Remediation Script.

Updates existing entities to map them to the ontology registry.
Run with --dry-run to preview changes without applying them.

Usage:
    uv run python scripts/ontology_batch_remediation.py --dry-run
    uv run python scripts/ontology_batch_remediation.py --execute
    uv run python scripts/ontology_batch_remediation.py --execute --mark-structural --mark-noise
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

# Add src to path
sys.path.insert(0, "src")

from neo4j import AsyncGraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ========================================
# Remediation Queries
# ========================================

REMEDIATION_QUERIES: List[Tuple[str, str, str]] = [
    # (name, description, cypher_query)

    # 1. BusinessConcept variants
    (
        "business_concept_mapping",
        "Map BusinessConcept/Concept variants to canonical form",
        """
        MATCH (n)
        WHERE (n.type IN ['BusinessConcept', 'businessconcept', 'Concept', 'concept', 'business_concept']
               OR any(label IN labels(n) WHERE label IN ['BusinessConcept', 'Concept']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'business_concept',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 2. Person/People/User mapping
    (
        "person_mapping",
        "Map Person/People/User variants to person",
        """
        MATCH (n)
        WHERE (n.type IN ['Person', 'person', 'People', 'people', 'User', 'user', 'Owner', 'owner', 'Stakeholder']
               OR any(label IN labels(n) WHERE label IN ['Person', 'People', 'User']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'person',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 3. Data Product mapping
    (
        "data_product_mapping",
        "Map DataProduct variants to data_product",
        """
        MATCH (n)
        WHERE (n.type IN ['DataProduct', 'data_product', 'Data Product', 'dataproduct', 'Product']
               OR any(label IN labels(n) WHERE label IN ['DataProduct', 'InformationAsset']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'data_product',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 4. Table/DataEntity mapping
    (
        "table_mapping",
        "Map Table/DataEntity variants to table",
        """
        MATCH (n)
        WHERE (n.type IN ['Table', 'table', 'DataEntity', 'data_entity', 'Entity', 'entity']
               OR any(label IN labels(n) WHERE label IN ['Table', 'DataEntity']))
          AND NOT any(label IN labels(n) WHERE label IN ['Chunk', 'Document', 'ExtractedEntity'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'table',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 5. Column/Attribute mapping
    (
        "column_mapping",
        "Map Column/Attribute variants to column",
        """
        MATCH (n)
        WHERE (n.type IN ['Column', 'column', 'Attribute', 'attribute', 'Field', 'field']
               OR any(label IN labels(n) WHERE label IN ['Column', 'Attribute']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'column',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 6. Process/Pipeline mapping
    (
        "process_mapping",
        "Map Process/Pipeline/ETL variants to process",
        """
        MATCH (n)
        WHERE (n.type IN ['Process', 'process', 'Pipeline', 'pipeline', 'ETL', 'Job', 'job', 'Workflow']
               OR any(label IN labels(n) WHERE label IN ['Process', 'Pipeline']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'process',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 7. Disease/Condition mapping (medical)
    (
        "disease_mapping",
        "Map Disease/Condition variants to disease",
        """
        MATCH (n)
        WHERE (n.type IN ['Disease', 'disease', 'medical_condition', 'MedicalCondition', 'Condition', 'condition', 'Disorder']
               OR any(label IN labels(n) WHERE label IN ['Disease', 'Condition']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'disease',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 8. Drug/Medication mapping (medical)
    (
        "drug_mapping",
        "Map Drug/Medication variants to drug",
        """
        MATCH (n)
        WHERE (n.type IN ['Drug', 'drug', 'Medication', 'medication', 'Medicine', 'Pharmaceutical']
               OR any(label IN labels(n) WHERE label IN ['Drug', 'Medication']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'drug',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 9. Symptom mapping (medical)
    (
        "symptom_mapping",
        "Map Symptom variants to symptom",
        """
        MATCH (n)
        WHERE (n.type IN ['Symptom', 'symptom', 'Sign', 'Manifestation']
               OR any(label IN labels(n) WHERE label IN ['Symptom']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'symptom',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 10. Treatment mapping (medical)
    (
        "treatment_mapping",
        "Map Treatment/Therapy variants to treatment",
        """
        MATCH (n)
        WHERE (n.type IN ['Treatment', 'treatment', 'Therapy', 'therapy', 'Procedure', 'Intervention']
               OR any(label IN labels(n) WHERE label IN ['Treatment', 'Therapy']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'treatment',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 11. Organization mapping
    (
        "organization_mapping",
        "Map Organization variants to organization",
        """
        MATCH (n)
        WHERE (n.type IN ['Organization', 'organization', 'Company', 'company', 'Institution', 'University', 'Hospital']
               OR any(label IN labels(n) WHERE label IN ['Organization']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'organization',
            n.layer = COALESCE(n.layer, 'APPLICATION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 12. Gene mapping (medical)
    (
        "gene_mapping",
        "Map Gene variants to gene",
        """
        MATCH (n)
        WHERE (n.type IN ['Gene', 'gene', 'GeneticMarker', 'genetic_marker']
               OR any(label IN labels(n) WHERE label IN ['Gene']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'gene',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 13. Metric/KPI mapping
    (
        "metric_mapping",
        "Map Metric/KPI variants to metric",
        """
        MATCH (n)
        WHERE (n.type IN ['Metric', 'metric', 'KPI', 'kpi', 'Indicator', 'Measure']
               OR any(label IN labels(n) WHERE label IN ['Metric', 'KPI']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'metric',
            n.layer = COALESCE(n.layer, 'APPLICATION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 14. System/Application mapping
    (
        "system_mapping",
        "Map System/Application variants to system",
        """
        MATCH (n)
        WHERE (n.type IN ['System', 'system', 'Application', 'application', 'Service', 'service']
               OR any(label IN labels(n) WHERE label IN ['System', 'Application']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'system',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 15. Database mapping
    (
        "database_mapping",
        "Map Database variants to database",
        """
        MATCH (n)
        WHERE (n.type IN ['Database', 'database', 'DB', 'db']
               OR any(label IN labels(n) WHERE label IN ['Database']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'database',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 16. FactUnit mapping (hypergraph bridge entities)
    (
        "factunit_mapping",
        "Map FactUnit/Bridge entities to business_concept (reasoning layer)",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['FactUnit', 'Bridge'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'business_concept',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 17. Patient mapping
    (
        "patient_mapping",
        "Map Patient entities to person (semantic layer)",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['Patient', 'patient'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'person',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 18. Medication mapping
    (
        "medication_mapping",
        "Map Medication/MedicalEntity entities to drug",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['Medication', 'MedicalEntity'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'drug',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 19. Diagnosis mapping
    (
        "diagnosis_mapping",
        "Map Diagnosis entities to disease",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['Diagnosis'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'disease',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),

    # 20. ConversationSession/Message mapping (application layer entities)
    (
        "conversation_mapping",
        "Map ConversationSession/Message to usage (application layer)",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['ConversationSession', 'Message'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'usage',
            n.layer = COALESCE(n.layer, 'APPLICATION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
]

# Mark structural entities query
MARK_STRUCTURAL_QUERY = """
MATCH (n)
WHERE any(label IN labels(n) WHERE label IN ['Chunk', 'StructuralChunk', 'Document', 'DocumentQuality', 'ExtractedEntity'])
  AND NOT coalesce(n._is_structural, false)
SET n._is_structural = true,
    n._exclude_from_ontology = true,
    n._marked_structural_at = datetime()
RETURN count(n) as updated
"""

# Mark noise entities query
STOPWORDS = [
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
]

MARK_NOISE_QUERY = f"""
MATCH (e)
WHERE e.name IS NOT NULL
  AND NOT coalesce(e._is_structural, false)
  AND NOT coalesce(e._is_noise, false)
  AND (
    size(e.name) < 3
    OR toLower(trim(e.name)) IN {STOPWORDS}
  )
SET e._is_noise = true,
    e._exclude_from_ontology = true,
    e._noise_reason = CASE
        WHEN size(e.name) < 3 THEN 'short_name'
        ELSE 'stopword'
    END,
    e._marked_noise_at = datetime()
RETURN count(e) as updated
"""


async def get_driver():
    """Get Neo4j async driver from environment."""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    return AsyncGraphDatabase.driver(uri, auth=(username, password))


async def get_pre_remediation_stats(driver) -> Dict[str, Any]:
    """Get current statistics before remediation."""
    query = """
    MATCH (n)
    WHERE n.id IS NOT NULL
    WITH n,
         coalesce(n._exclude_from_ontology, false) as excluded,
         coalesce(n._ontology_mapped, false) as mapped,
         any(label IN labels(n) WHERE label IN ['Chunk', 'Document', 'ExtractedEntity']) as is_structural
    RETURN
        count(n) as total,
        sum(CASE WHEN NOT is_structural AND NOT excluded THEN 1 ELSE 0 END) as knowledge_entities,
        sum(CASE WHEN mapped THEN 1 ELSE 0 END) as already_mapped,
        sum(CASE WHEN is_structural THEN 1 ELSE 0 END) as structural_entities,
        sum(CASE WHEN excluded THEN 1 ELSE 0 END) as excluded_entities
    """
    async with driver.session() as session:
        result = await session.run(query)
        record = await result.single()

    return dict(record) if record else {}


async def get_unmapped_types(driver, limit: int = 20) -> List[Dict[str, Any]]:
    """Get top unmapped entity types."""
    query = f"""
    MATCH (n)
    WHERE n.id IS NOT NULL
      AND NOT coalesce(n._ontology_mapped, false)
      AND NOT any(label IN labels(n) WHERE label IN ['Chunk', 'Document', 'ExtractedEntity'])
    RETURN n.type as type, count(n) as count
    ORDER BY count DESC
    LIMIT {limit}
    """
    async with driver.session() as session:
        result = await session.run(query)
        records = [record async for record in result]

    return [{"type": r["type"], "count": r["count"]} for r in records]


def _convert_to_count_query(query: str) -> str:
    """Convert a remediation query to a count-only query for dry-run.

    Extracts MATCH and WHERE clauses and creates a simple count query.
    """
    lines = query.strip().split("\n")
    match_where_lines = []
    in_set_block = False

    for line in lines:
        stripped = line.strip()
        # Stop collecting when we hit SET
        if stripped.startswith("SET "):
            in_set_block = True
            continue
        # Stop when we hit RETURN
        if stripped.startswith("RETURN "):
            break
        # Skip lines that are part of SET block (continuation lines)
        if in_set_block and (stripped.startswith("n.") or stripped.startswith("n._") or stripped == ""):
            continue
        # Collect MATCH and WHERE lines
        if not in_set_block:
            match_where_lines.append(line)

    # Build count query
    count_query = "\n".join(match_where_lines) + "\nRETURN count(n) as would_update"
    return count_query


async def run_dry_run(driver) -> Dict[str, Any]:
    """Run dry-run to preview what would be updated."""
    logger.info("Running dry-run analysis...")

    stats = await get_pre_remediation_stats(driver)
    unmapped = await get_unmapped_types(driver)

    # For each remediation query, count how many would be affected
    preview = []
    for name, description, query in REMEDIATION_QUERIES:
        count_query = _convert_to_count_query(query)

        try:
            async with driver.session() as session:
                result = await session.run(count_query, {"batch_id": "dry_run"})
                record = await result.single()
                count = record["would_update"] if record else 0
                preview.append({
                    "name": name,
                    "description": description,
                    "would_update": count,
                })
        except Exception as e:
            logger.warning(f"Could not preview {name}: {e}")
            preview.append({
                "name": name,
                "description": description,
                "would_update": -1,  # Use -1 for error instead of string
                "error": str(e),
            })

    return {
        "pre_stats": stats,
        "unmapped_types": unmapped,
        "remediation_preview": preview,
        "total_would_update": sum(
            p["would_update"] for p in preview
            if isinstance(p["would_update"], int) and p["would_update"] >= 0
        ),
    }


async def run_remediation(
    driver,
    mark_structural: bool = True,
    mark_noise: bool = True
) -> Dict[str, Any]:
    """Execute the batch remediation."""
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f"Starting batch remediation: {batch_id}")

    results = {
        "batch_id": batch_id,
        "started_at": datetime.now().isoformat(),
        "steps": [],
    }

    # Step 0: Mark structural entities
    if mark_structural:
        logger.info("Marking structural entities...")
        async with driver.session() as session:
            result = await session.run(MARK_STRUCTURAL_QUERY)
            record = await result.single()
            count = record["updated"] if record else 0
            results["structural_marked"] = count
            logger.info(f"  Marked {count} structural entities")

    # Step 0b: Mark noise entities
    if mark_noise:
        logger.info("Marking noise entities...")
        async with driver.session() as session:
            result = await session.run(MARK_NOISE_QUERY)
            record = await result.single()
            count = record["updated"] if record else 0
            results["noise_marked"] = count
            logger.info(f"  Marked {count} noise entities")

    # Run remediation queries
    total_updated = 0
    for name, description, query in REMEDIATION_QUERIES:
        logger.info(f"Running: {name}")
        try:
            async with driver.session() as session:
                result = await session.run(query, {"batch_id": batch_id})
                record = await result.single()
                count = record["updated"] if record else 0
                total_updated += count
                results["steps"].append({
                    "name": name,
                    "description": description,
                    "updated": count,
                    "status": "success",
                })
                logger.info(f"  Updated {count} entities")
        except Exception as e:
            logger.error(f"  Error: {e}")
            results["steps"].append({
                "name": name,
                "description": description,
                "updated": 0,
                "status": "error",
                "error": str(e),
            })

    results["total_updated"] = total_updated
    results["completed_at"] = datetime.now().isoformat()

    # Get post-remediation stats
    results["post_stats"] = await get_pre_remediation_stats(driver)

    # Calculate coverage improvement
    pre_mapped = results.get("pre_stats", {}).get("already_mapped", 0)
    post_mapped = results["post_stats"].get("already_mapped", 0)
    knowledge_entities = results["post_stats"].get("knowledge_entities", 1)

    results["coverage_before"] = round(pre_mapped / knowledge_entities * 100, 2) if knowledge_entities else 0
    results["coverage_after"] = round(post_mapped / knowledge_entities * 100, 2) if knowledge_entities else 0

    return results


async def rollback_batch(driver, batch_id: str) -> Dict[str, Any]:
    """Rollback a specific batch remediation."""
    logger.info(f"Rolling back batch: {batch_id}")

    query = """
    MATCH (n)
    WHERE n._remediation_batch = $batch_id
    REMOVE n._ontology_mapped, n._canonical_type, n._remediation_date, n._remediation_batch
    RETURN count(n) as rolled_back
    """

    async with driver.session() as session:
        result = await session.run(query, {"batch_id": batch_id})
        record = await result.single()

    count = record["rolled_back"] if record else 0
    logger.info(f"Rolled back {count} entities")

    return {"batch_id": batch_id, "rolled_back": count}


def print_report(results: Dict[str, Any], is_dry_run: bool = False):
    """Print a formatted report."""
    print("\n" + "=" * 60)
    if is_dry_run:
        print("ONTOLOGY REMEDIATION - DRY RUN REPORT")
    else:
        print(f"ONTOLOGY REMEDIATION REPORT - Batch: {results.get('batch_id', 'N/A')}")
    print("=" * 60)

    if is_dry_run:
        print("\n## Pre-Remediation Statistics")
        stats = results.get("pre_stats", {})
        print(f"  Total Entities: {stats.get('total', 0):,}")
        print(f"  Knowledge Entities: {stats.get('knowledge_entities', 0):,}")
        print(f"  Already Mapped: {stats.get('already_mapped', 0):,}")
        print(f"  Structural: {stats.get('structural_entities', 0):,}")

        print("\n## Top Unmapped Types")
        for item in results.get("unmapped_types", [])[:10]:
            print(f"  - {item['type']}: {item['count']:,}")

        print("\n## Remediation Preview")
        for step in results.get("remediation_preview", []):
            count = step['would_update']
            if count < 0:
                print(f"  - {step['name']}: ERROR")
            else:
                print(f"  - {step['name']}: {count:,}")

        print(f"\n## Total Would Update: {results.get('total_would_update', 0):,}")

    else:
        print(f"\nStarted: {results.get('started_at', 'N/A')}")
        print(f"Completed: {results.get('completed_at', 'N/A')}")

        if "structural_marked" in results:
            print(f"\nStructural entities marked: {results['structural_marked']:,}")
        if "noise_marked" in results:
            print(f"Noise entities marked: {results['noise_marked']:,}")

        print("\n## Remediation Steps")
        for step in results.get("steps", []):
            status = "OK" if step["status"] == "success" else "ERROR"
            print(f"  [{status}] {step['name']}: {step['updated']:,}")

        print(f"\n## Total Updated: {results.get('total_updated', 0):,}")
        print(f"\n## Coverage Improvement")
        print(f"  Before: {results.get('coverage_before', 0)}%")
        print(f"  After: {results.get('coverage_after', 0)}%")

    print("\n" + "=" * 60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ontology Batch Remediation Script"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the remediation"
    )
    parser.add_argument(
        "--rollback",
        type=str,
        help="Rollback a specific batch by ID"
    )
    parser.add_argument(
        "--mark-structural",
        action="store_true",
        default=True,
        help="Mark structural entities (default: True)"
    )
    parser.add_argument(
        "--mark-noise",
        action="store_true",
        default=True,
        help="Mark noise/stopword entities (default: True)"
    )
    parser.add_argument(
        "--no-mark-structural",
        action="store_true",
        help="Skip marking structural entities"
    )
    parser.add_argument(
        "--no-mark-noise",
        action="store_true",
        help="Skip marking noise entities"
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute and not args.rollback:
        parser.print_help()
        print("\nError: Must specify --dry-run, --execute, or --rollback")
        sys.exit(1)

    driver = await get_driver()

    try:
        if args.rollback:
            results = await rollback_batch(driver, args.rollback)
            print(f"Rolled back {results['rolled_back']} entities from batch {args.rollback}")

        elif args.dry_run:
            results = await run_dry_run(driver)
            print_report(results, is_dry_run=True)

        elif args.execute:
            # Get pre-stats first
            pre_stats = await get_pre_remediation_stats(driver)

            mark_structural = args.mark_structural and not args.no_mark_structural
            mark_noise = args.mark_noise and not args.no_mark_noise

            results = await run_remediation(
                driver,
                mark_structural=mark_structural,
                mark_noise=mark_noise
            )
            results["pre_stats"] = pre_stats
            print_report(results)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
