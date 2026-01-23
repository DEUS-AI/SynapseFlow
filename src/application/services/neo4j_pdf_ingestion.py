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
        """Persist extracted knowledge to Neo4j with PERCEPTION layer structure."""

        entities_added = 0
        relationships_added = 0
        skipped = 0

        with self.driver.session() as session:
            # Add entities to PERCEPTION layer
            for entity in extraction_result.entities:
                entity_type = entity.get("type", "Entity")
                entity_name_raw = entity.get("name", "Unknown")

                # Normalize entity name (same logic as before)
                entity_name = self._normalize_entity_name(entity_name_raw)

                # Sanitize entity type for label
                sanitized_type = self._sanitize_label(entity_type)

                properties = {
                    "name": entity_name,
                    "type": entity_type,
                    "description": entity.get("description", ""),
                    "confidence": entity.get("confidence", 0.5),
                    "source_document": extraction_result.document.filename,
                    "category": extraction_result.document.category,
                    "layer": "PERCEPTION",  # Mark as PERCEPTION layer
                    "created_at": datetime.now().isoformat()
                }

                try:
                    # Create with MedicalEntity label + type-specific label
                    session.run(
                        f"""
                        MERGE (n:MedicalEntity:{sanitized_type} {{name: $name}})
                        SET n.type = $type,
                            n.description = $description,
                            n.confidence = $confidence,
                            n.source_document = $source_document,
                            n.category = $category,
                            n.layer = $layer,
                            n.created_at = $created_at
                        """,
                        **properties
                    )
                    entities_added += 1
                except Exception as e:
                    logger.warning(f"Failed to add entity {entity_name}: {e}")

            # Build entity lookup map with abbreviations
            entity_map = {}
            for entity in extraction_result.entities:
                entity_name_raw = entity.get("name", "Unknown")
                entity_name = self._normalize_entity_name(entity_name_raw)

                entity_map[entity_name] = entity_name
                entity_map[entity_name_raw] = entity_name
                entity_map[entity_name.lower()] = entity_name

                # Add abbreviation mappings
                for abbrev, full_name in self.ABBREVIATION_MAP.items():
                    if entity_name.lower() == full_name.lower():
                        entity_map[abbrev] = entity_name
                        entity_map[abbrev.lower()] = entity_name

            # Add relationships to PERCEPTION layer
            for rel in extraction_result.relationships:
                source_name = rel.get("source", "")
                target_name = rel.get("target", "")
                rel_type = rel.get("type", "RELATED_TO")

                # Lookup entity names
                source_id = entity_map.get(source_name) or entity_map.get(source_name.lower())
                target_id = entity_map.get(target_name) or entity_map.get(target_name.lower())

                if not source_id or not target_id:
                    logger.debug(f"Skipping relationship {source_name} -> {target_name} (entity not found)")
                    skipped += 1
                    continue

                try:
                    # Sanitize relationship type
                    rel_type_sanitized = self._sanitize_label(rel_type)

                    session.run(
                        f"""
                        MATCH (source:MedicalEntity {{name: $source_name}})
                        MATCH (target:MedicalEntity {{name: $target_name}})
                        MERGE (source)-[r:{rel_type_sanitized}]->(target)
                        SET r.description = $description,
                            r.layer = 'PERCEPTION',
                            r.created_at = $created_at
                        """,
                        source_name=source_id,
                        target_name=target_id,
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
