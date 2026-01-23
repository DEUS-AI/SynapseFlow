#!/usr/bin/env python3
"""
Demo: Batch DDA Processing

This demo processes all DDA (Domain Design Artifact) documents using the
neurosymbolic AI pipeline:

1. Scan examples/ directory for DDA markdown files
2. Parse each DDA with MarkdownDDAParser
3. Execute Data Architect workflow (architecture graph creation)
4. Trigger Data Engineer workflow (metadata generation with LLM enrichment)
5. Track progress and display statistics

This populates the knowledge graph with multi-layer metadata (PERCEPTION → APPLICATION)
including LLM-extracted BusinessConcepts.

Usage:
    python demos/demo_batch_dda_processing.py [--max-ddas N] [--validate-only]
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from composition_root import (
    bootstrap_command_bus,
    bootstrap_knowledge_management,
    create_modeling_command_handler,
    create_generate_metadata_command_handler
)
from application.commands.modeling_command import ModelingCommand
from application.commands.metadata_command import GenerateMetadataCommand
from infrastructure.parsers.markdown_parser import MarkdownDDAParser
from infrastructure.graphiti import get_graphiti

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


def print_dda_summary(dda_files: List[Path]):
    """Print summary of discovered DDAs."""
    print_section("Discovered DDAs")

    # Group by domain type if possible (extract from filename)
    disease_ddas = []
    other_ddas = []

    for dda_path in dda_files:
        if any(term in dda_path.stem.lower() for term in ['disease', 'lupus', 'arthritis', 'diabetes', 'celiac', 'crohn', 'colitis', 'sclerosis', 'psoriasis', 'spondylitis', 'vasculitis', 'syndrome', 'ibd']):
            disease_ddas.append(dda_path)
        else:
            other_ddas.append(dda_path)

    if disease_ddas:
        print(f"\n  Disease Management DDAs: {len(disease_ddas)}")
        for dda in sorted(disease_ddas):
            print(f"    - {dda.stem}")

    if other_ddas:
        print(f"\n  Other DDAs: {len(other_ddas)}")
        for dda in sorted(other_ddas):
            print(f"    - {dda.stem}")

    print(f"\n  TOTAL: {len(dda_files)} DDAs")


def print_processing_result(result: Dict[str, Any], index: int, total: int):
    """Print result of processing a single DDA."""
    if "error" in result:
        print(f"\n  [{index}/{total}] ✗ {result['dda']}")
        print(f"         Error: {result['error']}")
        return

    print(f"\n  [{index}/{total}] ✓ {result['dda']}")
    print(f"         Domain: {result.get('domain', 'N/A')}")
    print(f"         Entities: {result.get('entities_count', 0)}")
    print(f"         Relationships: {result.get('relationships_count', 0)}")
    print(f"         Architecture Graph: {result.get('architecture_created', False)}")
    print(f"         Metadata Graph: {result.get('metadata_created', False)}")
    print(f"         Business Concepts: {result.get('business_concepts_count', 0)}")
    print(f"         Time: {result.get('processing_time_seconds', 0):.2f}s")


def print_summary_statistics(results: List[Dict[str, Any]]):
    """Print overall summary statistics."""
    print_section("Summary Statistics")

    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    print(f"\n  DDAs Processed: {len(results)}")
    print(f"    ✓ Successful: {len(successful)}")
    print(f"    ✗ Failed: {len(failed)}")

    if successful:
        total_entities = sum(r.get("entities_count", 0) for r in successful)
        total_relationships = sum(r.get("relationships_count", 0) for r in successful)
        total_business_concepts = sum(r.get("business_concepts_count", 0) for r in successful)
        architecture_created = sum(1 for r in successful if r.get("architecture_created", False))
        metadata_created = sum(1 for r in successful if r.get("metadata_created", False))
        total_time = sum(r.get("processing_time_seconds", 0) for r in successful)

        print(f"\n  Knowledge Graph Created:")
        print(f"    Architecture Graphs: {architecture_created}")
        print(f"    Metadata Graphs: {metadata_created}")
        print(f"    Total Entities: {total_entities:,}")
        print(f"    Total Relationships: {total_relationships:,}")
        print(f"    Business Concepts Extracted: {total_business_concepts:,}")

        print(f"\n  Performance:")
        print(f"    Total Time: {total_time:.2f}s")
        print(f"    Avg Time per DDA: {total_time / len(successful):.2f}s")

        if total_entities > 0:
            print(f"    Avg Entities per DDA: {total_entities / len(successful):.1f}")
        if total_relationships > 0:
            print(f"    Avg Relationships per DDA: {total_relationships / len(successful):.1f}")

    if failed:
        print(f"\n  Failed DDAs:")
        for result in failed:
            print(f"    - {result['dda']}: {result['error']}")


async def process_single_dda(
    dda_path: Path,
    modeling_handler,
    metadata_handler,
    validate_only: bool = False
) -> Dict[str, Any]:
    """Process a single DDA through the neurosymbolic pipeline."""
    start_time = datetime.now()
    result = {
        "dda": dda_path.stem,
        "path": str(dda_path),
        "processing_time_seconds": 0
    }

    try:
        # Parse DDA to extract basic info
        parser = MarkdownDDAParser()
        dda_doc = await parser.parse(str(dda_path))

        result["domain"] = dda_doc.domain
        result["entities_count"] = len(dda_doc.entities)
        result["relationships_count"] = len(dda_doc.relationships)

        if validate_only:
            logger.info(f"✓ Validated {dda_path.stem}: {result['domain']}")
            result["architecture_created"] = False
            result["metadata_created"] = False
            result["business_concepts_count"] = 0
            return result

        # Step 1: Create Modeling Command (Data Architect)
        modeling_command = ModelingCommand(
            dda_path=str(dda_path),
            domain=dda_doc.domain,
            update_existing=False,
            validate_only=False
        )

        # Execute modeling workflow
        logger.info(f"Processing architecture for: {dda_path.stem}")
        modeling_result = await modeling_handler.handle(modeling_command)

        result["architecture_created"] = modeling_result.get("success", False)
        result["architecture_graph_ref"] = modeling_result.get("graph_ref", "")

        # Step 2: Generate Metadata (Data Engineer)
        if result["architecture_created"]:
            metadata_command = GenerateMetadataCommand(
                dda_path=str(dda_path),
                domain=dda_doc.domain,
                architecture_graph_ref=result["architecture_graph_ref"]
            )

            logger.info(f"Generating metadata for: {dda_path.stem}")
            metadata_result = await metadata_handler.handle(metadata_command)

            result["metadata_created"] = metadata_result.get("success", False)
            result["business_concepts_count"] = metadata_result.get("business_concepts_extracted", 0)
        else:
            logger.warning(f"Skipping metadata generation for {dda_path.stem} (architecture failed)")
            result["metadata_created"] = False
            result["business_concepts_count"] = 0

    except Exception as e:
        logger.error(f"Error processing {dda_path.stem}: {e}", exc_info=True)
        result["error"] = str(e)

    # Calculate processing time
    end_time = datetime.now()
    result["processing_time_seconds"] = (end_time - start_time).total_seconds()

    return result


async def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="Batch DDA Processing Demo")
    parser.add_argument(
        "--max-ddas",
        type=int,
        default=None,
        help="Maximum number of DDAs to process (default: all)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate DDAs without creating graphs"
    )
    parser.add_argument(
        "--examples-dir",
        type=str,
        default="examples",
        help="Directory containing DDA markdown files (default: examples/)"
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Load environment
    load_dotenv()

    print_header("Batch DDA Processing - Neurosymbolic AI Pipeline")

    # Step 1: Discover DDAs
    examples_dir = Path(args.examples_dir)
    if not examples_dir.exists():
        print(f"\n✗ Examples directory not found: {examples_dir}")
        return 1

    dda_files = sorted(examples_dir.glob("*.md"))

    if not dda_files:
        print(f"\n✗ No DDA markdown files found in {examples_dir}")
        return 1

    # Apply max_ddas limit if specified
    if args.max_ddas:
        dda_files = dda_files[:args.max_ddas]

    print_dda_summary(dda_files)

    # Step 2: Confirm processing
    if not args.auto_confirm:
        print_section("Confirmation")
        print(f"\n  This will process {len(dda_files)} DDAs through the neurosymbolic pipeline:")
        print(f"    1. Data Architect: Create architecture graphs")
        print(f"    2. Data Engineer: Generate metadata with LLM enrichment")
        print(f"    3. Knowledge Graph: Populate with multi-layer entities")

        confirm = input("\n  Proceed? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\n✗ Cancelled by user")
            return 0

    # Step 3: Initialize system components
    print_section("Initialization")

    try:
        # Initialize knowledge graph backend and event bus
        kg_backend, event_bus = await bootstrap_knowledge_management()

        # Initialize Graphiti for LLM operations
        graphiti = await get_graphiti({
            "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j")),
            "password": os.environ.get("NEO4J_PASSWORD", "password"),
        })

        # Create command handlers
        modeling_handler = create_modeling_command_handler(
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j")),
            neo4j_password=os.environ.get("NEO4J_PASSWORD", "password")
        )

        metadata_handler = create_generate_metadata_command_handler(
            graph=graphiti,
            kg_backend=kg_backend
        )

        print("✓ System initialized successfully")

    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        logger.error("Initialization error", exc_info=True)
        return 1

    # Step 4: Process DDAs
    print_section("Processing DDAs")

    results = []
    for index, dda_path in enumerate(dda_files, 1):
        result = await process_single_dda(
            dda_path,
            modeling_handler,
            metadata_handler,
            validate_only=args.validate_only
        )
        results.append(result)
        print_processing_result(result, index, len(dda_files))

    # Step 5: Print summary
    print_summary_statistics(results)

    # Step 6: Verify knowledge graph
    if not args.validate_only and any("error" not in r for r in results):
        print_section("Knowledge Graph Verification")

        try:
            from falkordb import FalkorDB

            db = FalkorDB(
                host=os.environ.get("FALKORDB_HOST", "localhost"),
                port=int(os.environ.get("FALKORDB_PORT", 6379))
            )
            graph = db.select_graph('medical_knowledge')

            # Count nodes by layer
            layers = ["PERCEPTION", "SEMANTIC", "REASONING", "APPLICATION"]
            print("\n  Knowledge Graph Statistics:")

            for layer in layers:
                result = graph.query(f"MATCH (n) WHERE n.layer = '{layer}' RETURN count(n)")
                count = result.result_set[0][0] if result.result_set else 0
                print(f"    {layer} layer: {count} entities")

            # Count total nodes and relationships
            total_nodes = graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
            total_rels = graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]

            print(f"\n  Total Entities: {total_nodes}")
            print(f"  Total Relationships: {total_rels}")

            # Count BusinessConcepts
            bc_result = graph.query("MATCH (n) WHERE n.type = 'BusinessConcept' RETURN count(n)")
            bc_count = bc_result.result_set[0][0] if bc_result.result_set else 0
            print(f"  Business Concepts: {bc_count}")

        except Exception as e:
            logger.warning(f"Could not verify knowledge graph: {e}")

    print_header("Batch Processing Complete")

    return 0 if all("error" not in r for r in results) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
