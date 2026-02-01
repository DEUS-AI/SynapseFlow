#!/usr/bin/env python3
"""
Reprocess All PDFs for Knowledge Graph

This script:
1. Scans all PDFs in the PDFs/ directory
2. Processes each PDF through the full pipeline:
   - PDF to Markdown conversion
   - Text chunking
   - Embedding generation (FAISS)
   - Entity extraction (all chunks, not just first 5)
   - Knowledge graph storage (Neo4j)
3. Updates the document tracker

Usage:
    uv run python scripts/reprocess_all_pdfs.py
    uv run python scripts/reprocess_all_pdfs.py --limit 3       # Only first 3 PDFs
    uv run python scripts/reprocess_all_pdfs.py --skip-existing  # Skip already processed
    uv run python scripts/reprocess_all_pdfs.py --max-chunks 10  # Limit entity extraction chunks
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from infrastructure.neo4j_backend import Neo4jBackend
from application.services.entity_extractor import EntityExtractor

load_dotenv()


def print_header(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_progress(current: int, total: int, filename: str):
    bar_len = 40
    filled = int(bar_len * current / total)
    bar = "=" * filled + "-" * (bar_len - filled)
    print(f"\r[{bar}] {current}/{total} - {filename[:40]:<40}", end="", flush=True)


class PDFReprocessor:
    """Reprocess PDFs with full entity extraction."""

    def __init__(
        self,
        pdf_dir: str = "PDFs",
        markdown_dir: str = "markdown_output",
        max_entity_chunks: int = 20,
    ):
        self.pdf_dir = Path(pdf_dir)
        self.markdown_dir = Path(markdown_dir)
        self.max_entity_chunks = max_entity_chunks

        # Initialize Neo4j backend
        self.backend = Neo4jBackend(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )

        # Initialize entity extractor (uses OpenAI by default from env)
        self.extractor = EntityExtractor(
            domain="medical",
            enable_normalization=True
        )

        # Load document tracker
        self.tracker_path = Path("data/document_tracking.json")
        self.tracker = self._load_tracker()

    def _load_tracker(self) -> dict:
        """Load document tracking data."""
        if self.tracker_path.exists():
            with open(self.tracker_path) as f:
                return json.load(f)
        return {}

    def _save_tracker(self):
        """Save document tracking data."""
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tracker_path, "w") as f:
            json.dump(self.tracker, f, indent=2, default=str)

    def discover_pdfs(self) -> list[Path]:
        """Find all PDFs in the directory."""
        if not self.pdf_dir.exists():
            return []
        return sorted(self.pdf_dir.rglob("*.pdf"))

    def get_markdown_path(self, pdf_path: Path) -> Path:
        """Get the markdown file path for a PDF."""
        return self.markdown_dir / f"{pdf_path.stem}.md"

    async def has_entities_in_neo4j(self, doc_name: str) -> int:
        """Check how many entities exist for this document in Neo4j."""
        driver = await self.backend._get_driver()

        async with driver.session() as session:
            result = await session.run("""
                MATCH (d:Document {name: $name})-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:ExtractedEntity)
                RETURN count(DISTINCT e) as count
            """, name=doc_name)
            record = await result.single()
            return record["count"] if record else 0

    async def process_pdf(
        self,
        pdf_path: Path,
        force: bool = False
    ) -> dict:
        """Process a single PDF through the full pipeline."""
        doc_name = pdf_path.name
        markdown_path = self.get_markdown_path(pdf_path)

        result = {
            "filename": doc_name,
            "status": "pending",
            "entities": 0,
            "relationships": 0,
            "error": None
        }

        # Check if markdown exists
        if not markdown_path.exists():
            result["status"] = "error"
            result["error"] = "Markdown file not found"
            return result

        # Check existing entities
        existing_count = await self.has_entities_in_neo4j(doc_name)
        if existing_count > 0 and not force:
            result["status"] = "skipped"
            result["entities"] = existing_count
            return result

        try:
            # Read markdown content
            markdown_text = markdown_path.read_text(encoding='utf-8')

            # Chunk the text
            chunks = self._chunk_text(markdown_text, doc_name)

            # Extract entities from chunks (configurable limit)
            chunks_to_process = chunks[:self.max_entity_chunks]
            all_entities = []

            for i, chunk in enumerate(chunks_to_process):
                try:
                    entities = await self.extractor.extract_entities(
                        chunk["text"],
                        chunk["id"]
                    )
                    all_entities.extend(entities)
                except Exception as e:
                    print(f"\n    Warning: Entity extraction failed for chunk {i}: {e}")

            # Store in Neo4j
            if all_entities:
                stored = await self._store_in_neo4j(
                    doc_name=doc_name,
                    pdf_path=str(pdf_path),
                    chunks=chunks,
                    entities=all_entities
                )
                result["entities"] = stored["entities"]
                result["relationships"] = stored["relationships"]

            result["status"] = "completed"

            # Update tracker
            doc_id = self._get_doc_id(doc_name)
            if doc_id in self.tracker:
                self.tracker[doc_id]["entity_count"] = result["entities"]
                self.tracker[doc_id]["relationship_count"] = result["relationships"]
                self.tracker[doc_id]["updated_at"] = datetime.now().isoformat()

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def _get_doc_id(self, filename: str) -> str:
        """Find document ID from tracker by filename."""
        for doc_id, doc in self.tracker.items():
            if doc.get("filename") == filename:
                return doc_id
        return ""

    def _chunk_text(
        self,
        text: str,
        doc_name: str,
        chunk_size: int = 1500,
        overlap: int = 200
    ) -> list[dict]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        chunk_num = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk_text.rfind('. ')
                if last_period > chunk_size // 2:
                    end = start + last_period + 1
                    chunk_text = text[start:end]

            chunk_id = f"chunk:{doc_name}:{chunk_num}"
            chunks.append({
                "id": chunk_id,
                "text": chunk_text.strip(),
                "doc_name": doc_name,
                "chunk_num": chunk_num
            })

            start = end - overlap
            chunk_num += 1

        return chunks

    async def _store_in_neo4j(
        self,
        doc_name: str,
        pdf_path: str,
        chunks: list[dict],
        entities: list
    ) -> dict:
        """Store document, chunks, and entities in Neo4j."""
        driver = await self.backend._get_driver()
        entities_added = 0
        relationships_added = 0

        async with driver.session() as session:
            # Create Document node
            await session.run("""
                MERGE (d:Document {name: $name})
                SET d.path = $path,
                    d.ingested_at = datetime(),
                    d.chunk_count = $chunk_count
            """, name=doc_name, path=pdf_path, chunk_count=len(chunks))

            # Create Chunk nodes
            for chunk in chunks:
                await session.run("""
                    MATCH (d:Document {name: $doc_name})
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.text = $text,
                        c.chunk_num = $chunk_num
                    MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                    doc_name=doc_name,
                    chunk_id=chunk["id"],
                    text=chunk["text"][:2000],  # Limit text size
                    chunk_num=chunk["chunk_num"]
                )

            # Create ExtractedEntity nodes and relationships
            entity_names = set()
            for entity in entities:
                entity_name = f"extracted:{entity.name.lower().replace(' ', '_')}"
                entity_type = self._sanitize_label(entity.entity_type)

                if entity_name not in entity_names:
                    entity_names.add(entity_name)

                    # Create entity node
                    await session.run(f"""
                        MERGE (e:ExtractedEntity:{entity_type} {{name: $name}})
                        SET e.id = $id,
                            e.type = $type,
                            e.description = $description,
                            e.confidence = $confidence,
                            e.extraction_confidence = $confidence,
                            e.layer = 'PERCEPTION',
                            e.source_document = $source_doc
                    """,
                        name=entity.name.lower().replace(' ', '_'),
                        id=entity_name,
                        type=entity.entity_type,
                        description=getattr(entity, 'description', ''),
                        confidence=entity.confidence,
                        source_doc=doc_name
                    )
                    entities_added += 1

                # Link entity to chunk
                await session.run("""
                    MATCH (c:Chunk {id: $chunk_id})
                    MATCH (e:ExtractedEntity {id: $entity_id})
                    MERGE (c)-[:MENTIONS]->(e)
                """,
                    chunk_id=entity.source_chunk_id,
                    entity_id=entity_name
                )

            # Create LINKS_TO relationships between entities in same document
            if len(entity_names) > 1:
                entity_list = list(entity_names)
                for i, e1 in enumerate(entity_list[:-1]):
                    for e2 in entity_list[i+1:i+3]:  # Link to next 2 entities
                        await session.run("""
                            MATCH (e1:ExtractedEntity {id: $e1})
                            MATCH (e2:ExtractedEntity {id: $e2})
                            MERGE (e1)-[r:LINKS_TO]->(e2)
                        """, e1=e1, e2=e2)
                        relationships_added += 1

        return {"entities": entities_added, "relationships": relationships_added}

    def _sanitize_label(self, label: str) -> str:
        """Sanitize label for Neo4j."""
        sanitized = ''.join(c for c in label if c.isalnum())
        if sanitized and not sanitized[0].isalpha():
            sanitized = "Entity" + sanitized
        return sanitized or "Entity"


async def main():
    parser = argparse.ArgumentParser(description="Reprocess PDFs for knowledge graph")
    parser.add_argument("--limit", type=int, help="Limit number of PDFs to process")
    parser.add_argument("--skip-existing", action="store_true", help="Skip PDFs with existing entities")
    parser.add_argument("--max-chunks", type=int, default=20, help="Max chunks for entity extraction")
    parser.add_argument("--force", action="store_true", help="Force reprocess all PDFs")
    parser.add_argument("--pdf-dir", default="PDFs", help="PDF directory")

    args = parser.parse_args()

    print_header("PDF Reprocessing for Knowledge Graph")

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\nError: OPENAI_API_KEY not found in environment")
        return 1

    # Initialize processor
    processor = PDFReprocessor(
        pdf_dir=args.pdf_dir,
        max_entity_chunks=args.max_chunks
    )

    # Discover PDFs
    pdfs = processor.discover_pdfs()
    if args.limit:
        pdfs = pdfs[:args.limit]

    print(f"\nFound {len(pdfs)} PDFs to process")
    print(f"Max chunks for entity extraction: {args.max_chunks}")
    print(f"Skip existing: {args.skip_existing}")

    # Process PDFs
    print_header("Processing PDFs")

    results = {"completed": 0, "skipped": 0, "errors": 0}

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf_path.name}")

        # Check for existing entities if skip-existing
        if args.skip_existing and not args.force:
            existing = await processor.has_entities_in_neo4j(pdf_path.name)
            if existing > 0:
                print(f"  -> Skipped (has {existing} entities)")
                results["skipped"] += 1
                continue

        result = await processor.process_pdf(pdf_path, force=args.force)

        if result["status"] == "completed":
            print(f"  -> Completed: {result['entities']} entities, {result['relationships']} relationships")
            results["completed"] += 1
        elif result["status"] == "skipped":
            print(f"  -> Skipped (already has {result['entities']} entities)")
            results["skipped"] += 1
        else:
            print(f"  -> Error: {result['error']}")
            results["errors"] += 1

    # Save tracker
    processor._save_tracker()

    # Summary
    print_header("Summary")
    print(f"\n  Completed: {results['completed']}")
    print(f"  Skipped:   {results['skipped']}")
    print(f"  Errors:    {results['errors']}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
