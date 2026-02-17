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
from typing import Any, Dict

# Add src to path
sys.path.insert(0, "src")

from neo4j import AsyncGraphDatabase

from application.services.remediation_service import RemediationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def get_driver():
    """Get Neo4j async driver from environment."""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    return AsyncGraphDatabase.driver(uri, auth=(username, password))


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
    service = RemediationService(driver)

    try:
        if args.rollback:
            results = await service.rollback(args.rollback)
            print(f"Rolled back {results['rolled_back']} entities from batch {args.rollback}")

        elif args.dry_run:
            results = await service.dry_run()
            print_report(results, is_dry_run=True)

        elif args.execute:
            mark_structural = args.mark_structural and not args.no_mark_structural
            mark_noise = args.mark_noise and not args.no_mark_noise

            results = await service.execute(
                mark_structural=mark_structural,
                mark_noise=mark_noise,
            )
            print_report(results)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
