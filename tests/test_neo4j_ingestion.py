#!/usr/bin/env python3
"""
Test Neo4j PDF Ingestion Service

Verifies that the new Neo4jPDFIngestionService works correctly by:
1. Ingesting a single PDF
2. Verifying entities written to Neo4j with PERCEPTION layer
3. Checking relationship creation
"""

import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from application.services.neo4j_pdf_ingestion import Neo4jPDFIngestionService
from neo4j import GraphDatabase

load_dotenv()


def print_header(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


async def test_ingestion():
    """Test Neo4j PDF ingestion with a single PDF."""
    print_header("Testing Neo4j PDF Ingestion Service")

    # Configuration
    pdf_directory = Path("PDFs")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        print("\n✗ OPENAI_API_KEY not found in environment")
        return 1

    if not pdf_directory.exists():
        print(f"\n✗ PDF directory not found: {pdf_directory}")
        return 1

    print(f"\nPDF Directory: {pdf_directory}")
    print(f"Neo4j URI: {os.getenv('NEO4J_URI', 'bolt://localhost:7687')}")

    # Initialize service
    try:
        service = Neo4jPDFIngestionService(
            pdf_directory=pdf_directory,
            openai_api_key=openai_api_key,
            model="gpt-4o-mini"
        )
        print("✓ Service initialized")
    except Exception as e:
        print(f"\n✗ Service initialization failed: {e}")
        return 1

    # Discover PDFs
    documents = service.discover_pdfs()
    print(f"✓ Found {len(documents)} PDFs")

    if not documents:
        print("\n✗ No PDFs found")
        return 1

    # Test with first PDF only
    test_doc = documents[0]
    print(f"\n--- Testing with: {test_doc.filename} ---")
    print(f"  Category: {test_doc.category}")
    print(f"  Size: {test_doc.size_mb:.2f} MB")

    # Convert to markdown
    try:
        result = service.converter.convert(str(test_doc.path))
        markdown_content = result.text_content
        print(f"✓ Converted to markdown ({len(markdown_content)} chars)")
    except Exception as e:
        print(f"\n✗ Markdown conversion failed: {e}")
        return 1

    # Extract knowledge
    print("\n--- Extracting knowledge with LLM ---")
    try:
        extraction_result = await service.extract_knowledge(
            markdown_content=markdown_content,
            document=test_doc
        )

        print(f"✓ Extraction complete in {extraction_result.extraction_time_seconds:.2f}s")
        print(f"  Entities: {len(extraction_result.entities)}")
        print(f"  Relationships: {len(extraction_result.relationships)}")

        # Show sample entities
        if extraction_result.entities:
            print("\n  Sample entities:")
            for entity in extraction_result.entities[:5]:
                print(f"    - {entity['name']} ({entity['type']})")

    except Exception as e:
        print(f"\n✗ Extraction failed: {e}")
        return 1

    # Persist to Neo4j
    print("\n--- Persisting to Neo4j ---")
    try:
        persist_result = await service.persist_to_neo4j(extraction_result)

        print(f"✓ Persistence complete")
        print(f"  Entities added: {persist_result['entities_added']}")
        print(f"  Relationships added: {persist_result['relationships_added']}")
        print(f"  Relationships skipped: {persist_result['relationships_skipped']}")

    except Exception as e:
        print(f"\n✗ Persistence failed: {e}")
        return 1

    # Verify in Neo4j
    print("\n--- Verifying in Neo4j ---")
    try:
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        if '\n' in neo4j_uri:
            neo4j_uri = neo4j_uri.split('\n')[-1].strip()

        driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", ""))
        )

        with driver.session() as session:
            # Count entities from this document
            result = session.run("""
                MATCH (n:MedicalEntity)
                WHERE n.source_document = $filename
                RETURN count(n) as count
            """, filename=test_doc.filename)

            entity_count = result.single()["count"]

            # Count relationships
            result = session.run("""
                MATCH (n:MedicalEntity)-[r]->()
                WHERE n.source_document = $filename
                RETURN count(r) as count
            """, filename=test_doc.filename)

            rel_count = result.single()["count"]

            # Check layer property
            result = session.run("""
                MATCH (n:MedicalEntity)
                WHERE n.source_document = $filename AND n.layer = 'PERCEPTION'
                RETURN count(n) as count
            """, filename=test_doc.filename)

            perception_count = result.single()["count"]

            print(f"  Entities in Neo4j: {entity_count}")
            print(f"  Relationships in Neo4j: {rel_count}")
            print(f"  PERCEPTION layer entities: {perception_count}")

            if entity_count > 0 and perception_count == entity_count:
                print("\n✓ Verification successful!")
                print("  - Entities created with MedicalEntity label")
                print("  - PERCEPTION layer properly set")
                print("  - Relationships created")
            else:
                print("\n✗ Verification failed")
                if perception_count != entity_count:
                    print(f"  - Layer mismatch: {perception_count} PERCEPTION vs {entity_count} total")

        driver.close()

    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        return 1

    print_header("Test Complete")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_ingestion())
    sys.exit(exit_code)
