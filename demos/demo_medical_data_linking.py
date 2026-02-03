#!/usr/bin/env python3
"""
Demo: Medical-to-Data Entity Linking

This demo creates semantic bridges between:
- Medical knowledge entities (diseases, treatments, drugs from PDFs)
- DDA metadata entities (tables, columns from DDAs)

Links are created using multiple strategies:
1. Exact name matching
2. Description/context matching
3. Semantic similarity (future)
4. LLM inference (future)

Usage:
    python demos/demo_medical_data_linking.py [--confidence-threshold 0.75]
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from application.services.medical_data_linker import MedicalDataLinker
from dotenv import load_dotenv

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


def print_linking_results(result):
    """Print detailed linking results."""
    print_section("Linking Results")

    print(f"\n  Total Links Created: {result.links_created}")
    print(f"    ✓ Exact matches: {result.exact_count}")
    print(f"    ✓ Description matches: {result.description_count}")
    print(f"    ✓ Semantic matches: {result.semantic_count}")
    print(f"    ✓ LLM inferred: {result.llm_count}")
    print(f"    ✗ Skipped: {result.skipped_count}")

    if result.links_created > 0:
        print(f"\n  Sample Links (first 10):")
        for i, link in enumerate(result.links[:10], 1):
            print(f"\n  {i}. {link.medical_entity_name} ({link.medical_entity_type})")
            print(f"     → {link.data_entity_name} ({link.data_entity_type})")
            print(f"     Relationship: {link.relationship_type}")
            print(f"     Confidence: {link.confidence:.2f}")
            print(f"     Strategy: {link.linking_strategy}")
            print(f"     Reasoning: {link.reasoning}")


def print_link_examples(linker: MedicalDataLinker):
    """Print example queries showing linked entities."""
    print_section("Example Queries")

    # Try a few common disease names
    test_entities = [
        "Crohn's Disease",
        "Lupus",
        "Rheumatoid Arthritis",
        "Type 1 Diabetes",
        "Multiple Sclerosis"
    ]

    for entity_name in test_entities:
        links = linker.get_links_for_medical_entity(entity_name)

        if links:
            print(f"\n  {entity_name}:")
            for link in links:
                print(f"    → {link['relationship']}: {link['data_entity']} ({link['data_type']})")
                print(f"      Confidence: {link['confidence']:.2f} ({link['strategy']})")
        else:
            print(f"\n  {entity_name}: No links found")


async def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="Medical-to-Data Entity Linking Demo")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.75,
        help="Minimum confidence score to create a link (default: 0.75)"
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Load environment
    load_dotenv()

    print_header("Medical-to-Data Entity Linking Demo")

    print_section("Configuration")
    print(f"\n  Confidence Threshold: {args.confidence_threshold}")
    print(f"  Neo4j: bolt://localhost:7687")
    print(f"  Backend: Unified Neo4j (medical KG + DDA metadata)")

    # Confirm execution
    if not args.auto_confirm:
        print_section("Confirmation")
        print("\n  This will create SEMANTIC layer relationships between:")
        print("    - Medical entities (diseases, treatments, drugs)")
        print("    - Data entities (tables, columns from DDAs)")

        confirm = input("\n  Proceed? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\n✗ Cancelled by user")
            return 0

    # Initialize linker
    print_section("Initialization")
    try:
        linker = MedicalDataLinker()
        print("✓ Medical Data Linker initialized (Neo4j backend)")
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        logger.error("Initialization error", exc_info=True)
        return 1

    # Perform linking
    print_section("Entity Linking")
    start_time = datetime.now()

    try:
        result = await linker.link_medical_to_data(
            confidence_threshold=args.confidence_threshold
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Print results
        print_linking_results(result)

        print_section("Performance")
        print(f"\n  Total Time: {duration:.2f}s")
        if result.links_created > 0:
            print(f"  Avg Time per Link: {duration / result.links_created:.3f}s")

        # Show example queries
        if result.links_created > 0:
            print_link_examples(linker)

    except Exception as e:
        print(f"\n✗ Linking failed: {e}")
        logger.error("Linking error", exc_info=True)
        return 1

    print_header("Entity Linking Complete")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
