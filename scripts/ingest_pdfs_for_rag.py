#!/usr/bin/env python3
"""
Ingest PDFs into FAISS for RAG retrieval

This script:
1. Finds all PDFs in the PDFs/ directory
2. Converts them to markdown
3. Chunks the text
4. Generates embeddings (using OpenAI)
5. Stores in FAISS index at data/faiss_index
6. Links entities to Neo4j graph

Usage:
    uv run python ingest_pdfs_for_rag.py
    uv run python ingest_pdfs_for_rag.py --limit 3  # Only first 3 PDFs
"""

import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import os
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from application.services.document_service import DocumentService
from infrastructure.neo4j_backend import Neo4jBackend

load_dotenv()


def print_header(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


async def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs for RAG retrieval")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of PDFs to ingest (for testing)"
    )
    parser.add_argument(
        "--pdf-dir",
        type=str,
        default="PDFs",
        help="Directory containing PDFs (default: PDFs)"
    )

    args = parser.parse_args()

    print_header("PDF Ingestion for RAG")

    # Initialize Neo4j backend
    print("\n📊 Initializing Neo4j backend...")
    try:
        backend = Neo4jBackend(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "")
        )
        print("✓ Neo4j backend connected")
    except Exception as e:
        print(f"✗ Neo4j connection failed: {e}")
        return 1

    # Initialize document service
    print("\n📚 Initializing Document Service...")
    try:
        doc_service = DocumentService(
            kg_backend=backend,
            chunk_size=1500,
            chunk_overlap=300,
            faiss_index_path="data/faiss_index"
        )
        print("✓ Document service initialized")
    except Exception as e:
        print(f"✗ Document service initialization failed: {e}")
        return 1

    # Find all PDFs
    print(f"\n🔍 Scanning for PDFs in {args.pdf_dir}/...")
    pdf_dir = Path(args.pdf_dir)

    if not pdf_dir.exists():
        print(f"✗ PDF directory not found: {pdf_dir}")
        return 1

    pdfs = list(pdf_dir.rglob("*.pdf"))

    if not pdfs:
        print(f"✗ No PDFs found in {pdf_dir}")
        return 1

    # Apply limit if specified
    if args.limit:
        pdfs = pdfs[:args.limit]
        print(f"  Found {len(pdfs)} PDFs (limited to first {args.limit})")
    else:
        print(f"  Found {len(pdfs)} PDFs")

    # Ingest each PDF
    print_header("Processing PDFs")

    successful = 0
    failed = 0

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] Processing: {pdf_path.name}")
        print(f"  Path: {pdf_path}")

        try:
            # Ingest the document
            doc = await doc_service.ingest_document(
                str(pdf_path),
                source_name=pdf_path.name,
                metadata={"category": pdf_path.parent.name}
            )

            print(f"  ✓ Success!")
            print(f"    - Document ID: {doc.id}")
            print(f"    - Chunks created: {doc.chunk_count}")
            successful += 1

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed += 1

    # Summary
    print_header("Ingestion Complete")

    print(f"\n  Successful: {successful}/{len(pdfs)}")
    print(f"  Failed: {failed}/{len(pdfs)}")

    # Show FAISS index stats
    print(f"\n📊 FAISS Index Statistics:")
    print(f"  - Total chunks: {len(doc_service._chunk_store)}")
    print(f"  - Index path: {doc_service.faiss_index_path}.index")

    # Test search
    if doc_service._faiss_index is not None:
        print(f"\n🔍 Testing search...")
        try:
            results = await doc_service.search_similar("Crohn's disease", top_k=3)
            print(f"  ✓ Search working! Found {len(results)} results")
            if results:
                print(f"    Top result score: {results[0]['score']:.3f}")
        except Exception as e:
            print(f"  ✗ Search test failed: {e}")

    print("\n✅ PDF ingestion complete!")
    print("\nNow you can use the chat service with RAG retrieval enabled.")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
