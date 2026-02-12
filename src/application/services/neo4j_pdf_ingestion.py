"""Neo4j-based PDF Knowledge Ingestion Service.

Workflow: PDF → Markdown (markitdown) → Clean → LLM Entity Extraction → Neo4j

This version writes directly to Neo4j with proper layer structure for neurosymbolic reasoning:
- PERCEPTION layer: Raw entities from PDFs
- SEMANTIC layer: Cross-graph relationships (handled by medical_data_linker)
- REASONING layer: Validated/inferred knowledge (future)
- APPLICATION layer: Query patterns (future)
"""

import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

from openai import AsyncOpenAI
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


@dataclass
class PDFDocument:
    """Represents a PDF document."""
    path: Path
    filename: str
    category: Optional[str]
    size_bytes: int

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


@dataclass
class ExtractionResult:
    """Results from entity extraction."""
    document: PDFDocument
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    extraction_time_seconds: float
    raw_response: Optional[str] = None


class Neo4jPDFIngestionService:
    """PDF ingestion service that writes to Neo4j with layer structure."""

    # LLM extraction prompt (same as FalkorDB version for consistency)
    EXTRACTION_PROMPT = """You are a medical knowledge extraction AI. Extract key entities and relationships from the following medical text.

Extract entities of these types:
- Disease: Medical conditions, syndromes
- Treatment: Medications, therapies, procedures
- Symptom: Clinical manifestations, signs
- Test: Diagnostic tests, biomarkers
- Drug: Medications, compounds
- Gene: Genes, genetic markers
- Pathway: Biological pathways, mechanisms
- Organization: Research institutions, pharma companies
- Study: Clinical trials, research studies

For each entity, provide:
- name: Entity name (use full names, not abbreviations when possible)
- type: Entity type from the list above
- description: Brief description
- confidence: Your confidence in this extraction (0.0-1.0)

Also extract relationships between entities:
- source: Source entity name (MUST match an entity name from your entities list)
- target: Target entity name (MUST match an entity name from your entities list)
- type: Relationship type (TREATS, CAUSES, INDICATES, ASSOCIATED_WITH, etc.)
- description: Brief description of the relationship

IMPORTANT RULES:
1. Use FULL entity names consistently (e.g., "National Institutes of Health" not "NIH")
2. If you use an abbreviation in a relationship, make sure the full name is in your entities list
3. ONLY create relationships between entities you included in the entities array
4. DO NOT reference entities in relationships that are not in your entity list
5. If an entity appears in multiple forms (abbreviation + full name), choose ONE consistent form

Return as JSON with this structure:
{{
  "entities": [
    {{"name": "...", "type": "...", "description": "...", "confidence": 0.9}}
  ],
  "relationships": [
    {{"source": "...", "target": "...", "type": "...", "description": "..."}}
  ]
}}

Text to analyze:
---
{text}
---

Extract entities and relationships as JSON:"""

    # Abbreviation mapping (same as before)
    ABBREVIATION_MAP = {
        "NIEHS": "National Institute of Environmental Health Sciences",
        "NIH": "National Institutes of Health",
        "EBV": "Epstein-Barr Virus",
        "EXACT-PLAN": "Exposome in Autoimmune Diseases Collaborating Teams Planning Awards",
        "CD": "Crohn's Disease",
        "UC": "Ulcerative Colitis",
        "MS": "Multiple Sclerosis",
        "RA": "Rheumatoid Arthritis",
        "SLE": "Systemic Lupus Erythematosus",
        "IBD": "Inflammatory Bowel Disease",
        "MHC": "Major Histocompatibility Complex",
        "HLA": "Human Leukocyte Antigen",
        "TNF": "Tumor Necrosis Factor",
        "IL": "Interleukin",
        "ANA": "Antinuclear Antibodies",
        "OADR-ORWH": "Office of Autoimmune Disease Research - Office of Research on Women's Health",
    }

    def __init__(
        self,
        pdf_directory: Path,
        openai_api_key: str,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        """Initialize the service."""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        self.pdf_directory = Path(pdf_directory)
        if not self.pdf_directory.exists():
            raise ValueError(f"PDF directory not found: {pdf_directory}")

        # Initialize OpenAI client
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.model = model

        # Initialize PDF converter
        if not MARKITDOWN_AVAILABLE:
            raise ImportError("markitdown not available")
        self.converter = MarkItDown()

        # Initialize Neo4j connection
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        if '\n' in self.neo4j_uri:
            self.neo4j_uri = self.neo4j_uri.split('\n')[-1].strip()

        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "")

        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )

        logger.info(
            f"Neo4jPDFIngestionService initialized: "
            f"pdf_dir={pdf_directory}, model={model}, neo4j={self.neo4j_uri}"
        )

    def __del__(self):
        """Close Neo4j connection."""
        if hasattr(self, 'driver'):
            self.driver.close()

    def discover_pdfs(self) -> List[PDFDocument]:
        """Discover all PDF files (same as FalkorDB version)."""
        pdf_files = list(self.pdf_directory.rglob("*.pdf"))

        documents = []
        for pdf_path in pdf_files:
            # Categorize by directory structure
            relative = pdf_path.relative_to(self.pdf_directory)
            parts = relative.parts

            if len(parts) > 1:
                category = parts[0]  # Use parent folder as category
            else:
                category = "general"

            doc = PDFDocument(
                path=pdf_path,
                filename=pdf_path.name,
                category=category,
                size_bytes=pdf_path.stat().st_size
            )
            documents.append(doc)

        # Sort by category then filename
        documents.sort(key=lambda d: (d.category, d.filename))

        logger.info(f"Discovered {len(documents)} PDF documents")
        return documents

    async def extract_knowledge(
        self,
        markdown_content: str,
        document: PDFDocument,
        chunk_size: int = 8000
    ) -> ExtractionResult:
        """Extract entities and relationships using LLM (same logic as FalkorDB version)."""
        start_time = datetime.now()

        # Same chunking and extraction logic as before
        words = markdown_content.split()
        if len(words) > chunk_size:
            logger.info(f"Document too large ({len(words)} words), chunking...")
            chunk = " ".join(words[:chunk_size])
        else:
            chunk = markdown_content

        # Call LLM
        prompt = self.EXTRACTION_PROMPT.format(text=chunk)

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical knowledge extraction expert. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            raw_response = response.choices[0].message.content

            # Parse JSON with fallback strategies (same as before)
            try:
                data = json.loads(raw_response)
            except json.JSONDecodeError:
                # Fallback strategies...
                json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    data = {"entities": [], "relationships": []}

            entities = data.get("entities", [])
            relationships = data.get("relationships", [])

            end_time = datetime.now()
            extraction_time = (end_time - start_time).total_seconds()

            return ExtractionResult(
                document=document,
                entities=entities,
                relationships=relationships,
                extraction_time_seconds=extraction_time,
                raw_response=raw_response
            )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            raise

    async def persist_to_neo4j(
        self,
        extraction_result: ExtractionResult
    ) -> Dict[str, Any]:
        """Persist extracted knowledge to Neo4j with proper Document→Chunk→ExtractedEntity structure.

        Creates the standard graph pattern used throughout SynapseFlow:
        - (Document)-[:HAS_CHUNK]->(Chunk)-[:MENTIONS]->(ExtractedEntity)
        - (ExtractedEntity)-[:LINKS_TO]->(ExtractedEntity)
        """
        import hashlib

        entities_added = 0
        relationships_added = 0
        skipped = 0
        doc = extraction_result.document
        doc_name = doc.filename

        with self.driver.session() as session:
            # Step 1: Create Document node
            session.run(
                """
                MERGE (d:Document {name: $name})
                SET d.path = $path,
                    d.category = $category,
                    d.size_bytes = $size_bytes,
                    d.ingested_at = datetime(),
                    d.entity_count = $entity_count,
                    d.relationship_count = $rel_count
                """,
                name=doc_name,
                path=str(doc.path),
                category=doc.category or "general",
                size_bytes=doc.size_bytes,
                entity_count=len(extraction_result.entities),
                rel_count=len(extraction_result.relationships)
            )

            # Step 2: Create a Chunk node for the document content
            chunk_id = hashlib.sha256(f"{doc_name}:chunk:0".encode()).hexdigest()[:16]
            session.run(
                """
                MATCH (d:Document {name: $doc_name})
                MERGE (c:Chunk {id: $chunk_id})
                SET c.chunk_num = 0,
                    c.source_document = $doc_name
                MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                doc_name=doc_name,
                chunk_id=chunk_id
            )

            # Step 3: Create ExtractedEntity nodes
            entity_id_map = {}  # normalized_name -> entity_id
            for entity in extraction_result.entities:
                entity_type = entity.get("type", "Entity")
                entity_name_raw = entity.get("name", "Unknown")
                entity_name = self._normalize_entity_name(entity_name_raw)
                sanitized_type = self._sanitize_label(entity_type)

                # Create stable entity ID
                entity_id = f"extracted:{entity_name.lower().replace(' ', '_')}"
                entity_id_map[entity_name] = entity_id
                entity_id_map[entity_name_raw] = entity_id
                entity_id_map[entity_name.lower()] = entity_id

                # Add abbreviation mappings
                for abbrev, full_name in self.ABBREVIATION_MAP.items():
                    if entity_name.lower() == full_name.lower():
                        entity_id_map[abbrev] = entity_id
                        entity_id_map[abbrev.lower()] = entity_id

                try:
                    # Create with ExtractedEntity label + type-specific label
                    session.run(
                        f"""
                        MERGE (e:ExtractedEntity:{sanitized_type} {{name: $name}})
                        SET e.id = $id,
                            e.type = $type,
                            e.description = $description,
                            e.confidence = $confidence,
                            e.extraction_confidence = $confidence,
                            e.source_document = $source_document,
                            e.category = $category,
                            e.layer = 'PERCEPTION',
                            e.created_at = $created_at
                        """,
                        name=entity_name.lower().replace(' ', '_'),
                        id=entity_id,
                        type=entity_type,
                        description=entity.get("description", ""),
                        confidence=entity.get("confidence", 0.5),
                        source_document=doc_name,
                        category=doc.category or "general",
                        created_at=datetime.now().isoformat()
                    )

                    # Link entity to chunk via MENTIONS
                    session.run(
                        """
                        MATCH (c:Chunk {id: $chunk_id})
                        MATCH (e:ExtractedEntity {id: $entity_id})
                        MERGE (c)-[:MENTIONS]->(e)
                        """,
                        chunk_id=chunk_id,
                        entity_id=entity_id
                    )

                    entities_added += 1
                except Exception as e:
                    logger.warning(f"Failed to add entity {entity_name}: {e}")

            # Step 4: Create relationships between entities
            for rel in extraction_result.relationships:
                source_name = rel.get("source", "")
                target_name = rel.get("target", "")
                rel_type = rel.get("type", "RELATED_TO")

                source_id = entity_id_map.get(source_name) or entity_id_map.get(source_name.lower())
                target_id = entity_id_map.get(target_name) or entity_id_map.get(target_name.lower())

                if not source_id or not target_id:
                    logger.debug(f"Skipping relationship {source_name} -> {target_name} (entity not found)")
                    skipped += 1
                    continue

                try:
                    rel_type_sanitized = self._sanitize_label(rel_type)
                    session.run(
                        f"""
                        MATCH (source:ExtractedEntity {{id: $source_id}})
                        MATCH (target:ExtractedEntity {{id: $target_id}})
                        MERGE (source)-[r:LINKS_TO]->(target)
                        SET r.type = $rel_type,
                            r.description = $description,
                            r.layer = 'PERCEPTION',
                            r.created_at = $created_at
                        """,
                        source_id=source_id,
                        target_id=target_id,
                        rel_type=rel_type,
                        description=rel.get("description", ""),
                        created_at=datetime.now().isoformat()
                    )
                    relationships_added += 1
                except Exception as e:
                    logger.warning(f"Failed to add relationship {source_name} -> {target_name}: {e}")

        return {
            "entities_added": entities_added,
            "relationships_added": relationships_added,
            "relationships_skipped": skipped
        }

    def _normalize_entity_name(self, name: str) -> str:
        """Normalize entity name (same as FalkorDB version)."""
        normalized = name.title()
        normalized = normalized.replace("'S ", "'s ")
        normalized = normalized.replace("'T ", "'t ")
        return normalized

    def _sanitize_label(self, label: str) -> str:
        """Sanitize label for Neo4j (remove spaces, special chars)."""
        sanitized = label.replace(" ", "").replace("-", "").replace("_", "")
        if sanitized and not sanitized[0].isalpha():
            sanitized = "Entity" + sanitized
        if not sanitized:
            sanitized = "Entity"
        return sanitized

    def convert_and_clean(self, document: PDFDocument) -> str:
        """Convert PDF to Markdown and clean."""
        logger.info(f"Converting: {document.filename}")

        # Convert
        result = self.converter.convert(str(document.path))
        markdown = result.text_content

        # Clean
        cleaned = self._clean_markdown(markdown)

        logger.info(
            f"Converted {document.filename}: {len(cleaned)} chars, "
            f"{len(cleaned.split())} words"
        )

        return cleaned

    def _clean_markdown(self, markdown: str) -> str:
        """Clean Markdown content."""
        # Remove excessive newlines
        cleaned = re.sub(r'\n{3,}', '\n\n', markdown)

        # Remove trailing whitespace
        cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)

        # Remove horizontal rules (metadata separators)
        cleaned = re.sub(r'---+', '', cleaned)

        # Normalize bold/italic
        cleaned = re.sub(r'\*\*\*(.+?)\*\*\*', r'**\1**', cleaned)
        cleaned = re.sub(r'__(.+?)__', r'**\1**', cleaned)

        # Remove very short lines (artifacts)
        lines = cleaned.split('\n')
        filtered_lines = [
            line for line in lines
            if len(line.strip()) > 2 or line.strip() in ['', '#']
        ]
        cleaned = '\n'.join(filtered_lines)

        return cleaned.strip()

    async def ingest_document(
        self,
        document: PDFDocument,
        save_markdown: bool = False,
        markdown_output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Ingest a single PDF document to Neo4j.

        Args:
            document: The PDF document to ingest
            save_markdown: Whether to save the markdown output
            markdown_output_dir: Directory to save markdown files

        Returns:
            Dictionary with ingestion statistics
        """
        logger.info(f"Ingesting to Neo4j: {document.filename}")

        start_time = datetime.now()

        try:
            # Step 1: Convert PDF to cleaned Markdown
            cleaned_markdown = self.convert_and_clean(document)

            # Optionally save Markdown
            if save_markdown and markdown_output_dir:
                markdown_output_dir.mkdir(parents=True, exist_ok=True)
                markdown_path = markdown_output_dir / f"{document.path.stem}.md"
                markdown_path.write_text(cleaned_markdown, encoding='utf-8')
                logger.info(f"Saved Markdown: {markdown_path}")

            # Step 2: Extract entities with LLM
            extraction_result = await self.extract_knowledge(cleaned_markdown, document)

            # Step 3: Persist to Neo4j
            persistence_stats = await self.persist_to_neo4j(extraction_result)

            total_time = (datetime.now() - start_time).total_seconds()

            return {
                "document": document.filename,
                "category": document.category,
                "size_mb": document.size_mb,
                "markdown_chars": len(cleaned_markdown),
                "markdown_words": len(cleaned_markdown.split()),
                "extraction_time_seconds": extraction_result.extraction_time_seconds,
                "total_time_seconds": total_time,
                "entities_added": persistence_stats.get("entities_added", 0),
                "relationships_added": persistence_stats.get("relationships_added", 0),
            }

        except Exception as e:
            logger.error(f"Failed to ingest {document.filename}: {e}")
            raise
