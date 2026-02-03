#!/usr/bin/env python3
"""
Demo: PDF Knowledge Ingestion

This demo shows how to ingest medical PDF documents into the knowledge graph:
1. Discover PDFs in the PDFs/ directory
2. Convert PDFs to Markdown
3. Extract entities with Graphiti (LLM-powered)
4. Persist to FalkorDB

Usage:
    python demos/demo_pdf_ingestion.py [--max-docs N] [--save-markdown]
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from application.services.simple_pdf_ingestion import SimplePDFIngestionService
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


def format_size(bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} TB"


def print_document_summary(documents: list):
    """Print summary of discovered documents."""
    print_section("Discovered Documents")

    # Group by category
    by_category = {}
    for doc in documents:
        category = doc.category
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(doc)

    # Print by category
    for category, docs in sorted(by_category.items()):
        total_size = sum(d.size_bytes for d in docs)
        print(f"\n  {category.upper()}: {len(docs)} documents ({format_size(total_size)})")
        for doc in sorted(docs, key=lambda d: d.filename):
            print(f"    - {doc.filename} ({format_size(doc.size_bytes)})")

    total_size = sum(d.size_bytes for d in documents)
    print(f"\n  TOTAL: {len(documents)} documents ({format_size(total_size)})")


def print_ingestion_result(result: Dict[str, Any], index: int, total: int):
    """Print result of ingesting a single document."""
    if "error" in result:
        print(f"\n  [{index}/{total}] ✗ {result['document']}")
        print(f"         Error: {result['error']}")
        return

    print(f"\n  [{index}/{total}] ✓ {result['document']}")
    print(f"         Category: {result.get('category', 'N/A')}")
    print(f"         Size: {result.get('size_mb', 0):.2f} MB")
    print(f"         Markdown: {result.get('markdown_words', 0):,} words")
    print(f"         Entities: {result.get('entities_added', 0)}")
    print(f"         Relationships: {result.get('relationships_added', 0)}")
    print(f"         Time: {result.get('total_time_seconds', 0):.2f}s")


def print_summary_statistics(results: list):
    """Print overall summary statistics."""
    print_section("Summary Statistics")

    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    print(f"\n  Documents Processed: {len(results)}")
    print(f"    ✓ Successful: {len(successful)}")
    print(f"    ✗ Failed: {len(failed)}")

    if successful:
        total_entities = sum(r.get("entities_added", 0) for r in successful)
        total_relationships = sum(r.get("relationships_added", 0) for r in successful)
        total_time = sum(r.get("total_time_seconds", 0) for r in successful)
        total_words = sum(r.get("markdown_words", 0) for r in successful)

        print(f"\n  Knowledge Extracted:")
        print(f"    Entities: {total_entities:,}")
        print(f"    Relationships: {total_relationships:,}")
        print(f"    Total Words Processed: {total_words:,}")

        print(f"\n  Performance:")
        print(f"    Total Time: {total_time:.2f}s")
        print(f"    Avg Time per Document: {total_time / len(successful):.2f}s")

        if total_entities > 0:
            print(f"    Avg Entities per Document: {total_entities / len(successful):.1f}")
        if total_relationships > 0:
            print(f"    Avg Relationships per Document: {total_relationships / len(successful):.1f}")

    if failed:
        print(f"\n  Failed Documents:")
        for result in failed:
            print(f"    - {result['document']}: {result['error']}")


async def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="PDF Knowledge Ingestion Demo")
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Maximum number of documents to process (default: all)"
    )
    parser.add_argument(
        "--save-markdown",
        action="store_true",
        help="Save intermediate Markdown files"
    )
    parser.add_argument(
        "--markdown-dir",
        type=str,
        default="markdown_output",
        help="Directory to save Markdown files (default: markdown_output)"
    )
    parser.add_argument(
        "--pdf-dir",
        type=str,
        default="PDFs",
        help="Directory containing PDF files (default: PDFs)"
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Skip confirmation prompt (useful for automation)"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY not found in .env file")
        return 1

    print_header("PDF Knowledge Ingestion Demo")
    print(f"\nConfiguration:")
    print(f"  PDF Directory: {args.pdf_dir}")
    print(f"  Max Documents: {args.max_docs or 'All'}")
    print(f"  Save Markdown: {args.save_markdown}")
    if args.save_markdown:
        print(f"  Markdown Directory: {args.markdown_dir}")
    print(f"  Graph Database: FalkorDB (localhost:6379)")
    print(f"  Graph Name: medical_knowledge")

    # Initialize service
    print_section("Initializing Service")
    try:
        service = SimplePDFIngestionService(
            pdf_directory=Path(args.pdf_dir),
            openai_api_key=openai_api_key,
            falkor_host="localhost",
            falkor_port=6379,
            graph_name="medical_knowledge",
            model="gpt-4o-mini"
        )
        print("  ✓ Service initialized successfully")
    except Exception as e:
        print(f"  ✗ Failed to initialize service: {e}")
        return 1

    # Discover documents
    print_section("Discovering Documents")
    try:
        documents = service.discover_pdfs()
        print_document_summary(documents)
    except Exception as e:
        print(f"  ✗ Failed to discover documents: {e}")
        return 1

    if not documents:
        print("\n  No PDF documents found!")
        return 1

    # Limit documents if requested
    if args.max_docs:
        documents = documents[:args.max_docs]
        print(f"\n  Limited to {len(documents)} documents")

    # Confirm before proceeding
    print_section("Ready to Ingest")
    total_size = sum(d.size_bytes for d in documents)
    print(f"\n  Documents to process: {len(documents)}")
    print(f"  Total size: {format_size(total_size)}")
    print(f"  Estimated time: {len(documents) * 2:.0f}-{len(documents) * 5:.0f} minutes")
    print(f"  Estimated API cost: ${len(documents) * 0.50:.2f}-${len(documents) * 2.00:.2f}")

    if not args.auto_confirm:
        response = input("\n  Proceed with ingestion? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\n  Ingestion cancelled.")
            return 0
    else:
        print("\n  Auto-confirming (--auto-confirm flag set)")

    # Ingest documents
    print_section("Ingesting Documents")
    print(f"\n  Processing {len(documents)} documents...")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start_time = datetime.now()

    try:
        markdown_dir = Path(args.markdown_dir) if args.save_markdown else None

        # Process documents one by one for better progress reporting
        results = []
        for i, document in enumerate(documents, 1):
            try:
                result = await service.ingest_document(
                    document,
                    save_markdown=args.save_markdown,
                    markdown_output_dir=markdown_dir
                )
                results.append(result)
                print_ingestion_result(result, i, len(documents))

            except Exception as e:
                error_result = {
                    "document": document.filename,
                    "error": str(e)
                }
                results.append(error_result)
                print_ingestion_result(error_result, i, len(documents))

    except Exception as e:
        print(f"\n  ✗ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()

    print(f"\n  Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Total time: {total_time:.2f}s ({total_time / 60:.2f} minutes)")

    # Print summary
    print_summary_statistics(results)

    print_header("Ingestion Complete")
    print(f"\nKnowledge graph 'medical_knowledge' updated in FalkorDB")
    print(f"View at: http://localhost:3000")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
