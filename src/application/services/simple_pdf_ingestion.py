"""Simplified PDF Knowledge Ingestion Service.

Workflow: PDF → Markdown (markitdown) → Clean → LLM Entity Extraction → FalkorDB

This is a streamlined version that:
1. Converts PDFs to Markdown using markitdown
2. Cleans the Markdown content
3. Extracts entities using direct OpenAI LLM calls
4. Persists to FalkorDB as structured knowledge

No complex Graphiti dependency - just clean, simple extraction.
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

from infrastructure.falkor_backend import FalkorBackend

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


class SimplePDFIngestionService:
    """Simplified PDF ingestion service."""

    # LLM extraction prompt (note: double braces {{ }} are escaped for .format())
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

    def __init__(
        self,
        pdf_directory: Path,
        openai_api_key: str,
        falkor_host: str = "localhost",
        falkor_port: int = 6379,
        graph_name: str = "medical_knowledge",
        model: str = "gpt-4o-mini"
    ):
        """Initialize the service."""
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

        # Initialize FalkorDB backend
        self.backend = FalkorBackend(
            host=falkor_host,
            port=falkor_port,
            graph_name=graph_name
        )

        logger.info(
            f"SimplePDFIngestionService initialized: "
            f"pdf_dir={pdf_directory}, model={model}, graph={graph_name}"
        )

    def discover_pdfs(self) -> List[PDFDocument]:
        """Discover all PDF files."""
        pdf_files = list(self.pdf_directory.rglob("*.pdf"))

        documents = []
        for pdf_path in pdf_files:
            relative_path = pdf_path.relative_to(self.pdf_directory)
            category = relative_path.parts[0] if len(relative_path.parts) > 1 else "general"

            doc = PDFDocument(
                path=pdf_path,
                filename=pdf_path.name,
                category=category,
                size_bytes=pdf_path.stat().st_size
            )
            documents.append(doc)

        logger.info(
            f"Discovered {len(documents)} PDFs: "
            f"{sum(d.size_mb for d in documents):.2f} MB total"
        )

        return documents

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

    def _extract_json_object(self, text: str) -> Optional[str]:
        """Extract the first complete JSON object from text using balanced brace matching."""
        start_idx = text.find('{')
        if start_idx == -1:
            return None

        brace_count = 0
        in_string = False
        escape_next = False

        for i in range(start_idx, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found complete JSON object
                        return text[start_idx:i+1]

        return None

    def _extract_arrays_fallback(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        """Fallback: Extract entities and relationships arrays directly from text."""
        entities = []
        relationships = []

        try:
            # Try to find entities array
            entities_match = re.search(
                r'"entities"\s*:\s*(\[[^\]]*(?:\[[^\]]*\][^\]]*)*\])',
                text,
                re.DOTALL
            )
            if entities_match:
                entities_json = entities_match.group(1)
                entities = json.loads(entities_json)
                logger.info(f"Fallback: Extracted {len(entities)} entities")

            # Try to find relationships array
            rels_match = re.search(
                r'"relationships"\s*:\s*(\[[^\]]*(?:\[[^\]]*\][^\]]*)*\])',
                text,
                re.DOTALL
            )
            if rels_match:
                rels_json = rels_match.group(1)
                relationships = json.loads(rels_json)
                logger.info(f"Fallback: Extracted {len(relationships)} relationships")

        except Exception as e:
            logger.error(f"Fallback extraction failed: {e}")

        return entities, relationships

    async def extract_entities(
        self,
        text: str,
        document: PDFDocument
    ) -> ExtractionResult:
        """Extract entities using LLM."""
        logger.info(f"Extracting entities from {document.filename}")

        start_time = datetime.now()

        try:
            # Chunk text if too long (keep under 8000 words)
            words = text.split()
            if len(words) > 8000:
                logger.warning(
                    f"Text too long ({len(words)} words), taking first 8000 words"
                )
                text = ' '.join(words[:8000])

            # Call LLM with JSON mode for reliable formatting
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical knowledge extraction AI that extracts entities and relationships from medical texts. You must respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": self.EXTRACTION_PROMPT.format(text=text)
                    }
                ],
                response_format={"type": "json_object"},  # Force JSON output
                temperature=0.3,
                max_tokens=4000
            )

            raw_response = response.choices[0].message.content

            # Parse JSON response with multiple fallback strategies
            entities = []
            relationships = []

            # Strategy 1: Extract from markdown code block
            json_match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # Strategy 2: Find outermost JSON object using balanced brace matching
                json_str = self._extract_json_object(raw_response)

            if json_str:
                try:
                    data = json.loads(json_str)
                    entities = data.get("entities", [])
                    relationships = data.get("relationships", [])
                    logger.debug(f"Successfully parsed JSON: {len(entities)} entities, {len(relationships)} rels")
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse failed: {e}")
                    # Strategy 3: Try to extract arrays directly from response
                    entities, relationships = self._extract_arrays_fallback(raw_response)
            else:
                logger.warning("No JSON object found in response")
                # Strategy 3: Try to extract arrays directly
                entities, relationships = self._extract_arrays_fallback(raw_response)

            extraction_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Extracted from {document.filename}: "
                f"{len(entities)} entities, {len(relationships)} relationships "
                f"in {extraction_time:.2f}s"
            )

            return ExtractionResult(
                document=document,
                entities=entities,
                relationships=relationships,
                extraction_time_seconds=extraction_time,
                raw_response=raw_response
            )

        except Exception as e:
            logger.error(f"Extraction failed for {document.filename}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _normalize_entity_name(self, name: str) -> str:
        """Normalize entity name for consistency.

        This prevents duplicates like 'Autoimmune Diseases' vs 'autoimmune diseases'.
        Uses title case but preserves common patterns like 'McDonald's'.
        """
        # First apply title case
        normalized = name.title()

        # Fix common patterns where title() incorrectly capitalizes after apostrophe
        # e.g., "Crohn'S Disease" -> "Crohn's Disease"
        normalized = normalized.replace("'S ", "'s ")
        normalized = normalized.replace("'T ", "'t ")

        return normalized

    def _sanitize_label(self, entity_type: str) -> str:
        """Sanitize entity type for use as Cypher label.

        Cypher labels cannot contain spaces or special characters.
        This converts 'Environmental Factor' -> 'EnvironmentalFactor'
        """
        # Remove spaces, hyphens, and other special characters
        sanitized = entity_type.replace(" ", "").replace("-", "").replace("_", "")

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "Entity" + sanitized

        # Fallback to generic label if empty
        if not sanitized:
            sanitized = "Entity"

        return sanitized

    # Common medical abbreviations mapping
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

    async def persist_to_falkordb(
        self,
        extraction_result: ExtractionResult
    ) -> Dict[str, Any]:
        """Persist extracted knowledge to FalkorDB."""
        logger.info(
            f"Persisting: {len(extraction_result.entities)} entities, "
            f"{len(extraction_result.relationships)} relationships"
        )

        entities_added = 0
        relationships_added = 0

        # Add entities
        for entity in extraction_result.entities:
            entity_type = entity.get("type", "Entity")
            entity_name_raw = entity.get("name", "Unknown")

            # Normalize entity name to title case for consistency
            entity_name = self._normalize_entity_name(entity_name_raw)

            # Sanitize entity type for use as Cypher label
            sanitized_type = self._sanitize_label(entity_type)

            # Create unique ID with sanitized label
            entity_id = f"{sanitized_type}:{entity_name.replace(' ', '_')}"

            properties = {
                "name": entity_name,
                "type": entity_type,  # Keep original type in properties
                "description": entity.get("description", ""),
                "confidence": entity.get("confidence", 0.5),
                "source_document": extraction_result.document.filename,
                "category": extraction_result.document.category,
                "layer": "PERCEPTION",
                "created_at": datetime.now().isoformat()
            }

            try:
                await self.backend.add_entity(entity_id, properties)
                entities_added += 1
            except Exception as e:
                logger.warning(f"Failed to add entity {entity_id}: {e}")

        # Build entity lookup map (name -> full_id with type)
        entity_map = {}
        for entity in extraction_result.entities:
            entity_type = entity.get("type", "Entity")
            entity_name_raw = entity.get("name", "Unknown")

            # Normalize entity name to title case
            entity_name = self._normalize_entity_name(entity_name_raw)

            # Sanitize entity type for consistent ID format
            sanitized_type = self._sanitize_label(entity_type)
            entity_id = f"{sanitized_type}:{entity_name.replace(' ', '_')}"

            # Store normalized name, original name, and lowercase as keys
            entity_map[entity_name] = entity_id
            entity_map[entity_name_raw] = entity_id  # Original from LLM
            entity_map[entity_name.lower()] = entity_id

            # Also store by potential abbreviations
            # Check if the full name has a known abbreviation
            for abbrev, full_name in self.ABBREVIATION_MAP.items():
                if entity_name.lower() == full_name.lower():
                    entity_map[abbrev] = entity_id
                    entity_map[abbrev.lower()] = entity_id

        # Add relationships
        for rel in extraction_result.relationships:
            source_name = rel.get("source", "")
            target_name = rel.get("target", "")
            rel_type = rel.get("type", "RELATES_TO")

            if not source_name or not target_name:
                continue

            # Look up actual entity IDs from the entity map
            source_id = entity_map.get(source_name) or entity_map.get(source_name.lower())
            target_id = entity_map.get(target_name) or entity_map.get(target_name.lower())

            if not source_id or not target_id:
                logger.warning(
                    f"Skipping relationship {source_name} -> {target_name}: "
                    f"entities not found (available: {list(entity_map.keys())})"
                )
                continue

            try:
                await self.backend.add_relationship(
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=rel_type,
                    properties={
                        "description": rel.get("description", ""),
                        "source_document": extraction_result.document.filename,
                        "created_at": datetime.now().isoformat()
                    }
                )
                relationships_added += 1
            except Exception as e:
                logger.warning(f"Failed to add relationship {source_id} -> {target_id}: {e}")

        logger.info(f"Persisted: {entities_added} entities, {relationships_added} relationships")

        return {
            "entities_added": entities_added,
            "relationships_added": relationships_added,
            "document": extraction_result.document.filename
        }

    async def ingest_document(
        self,
        document: PDFDocument,
        save_markdown: bool = False,
        markdown_output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Ingest a single PDF document."""
        logger.info(f"Ingesting: {document.filename}")

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
            extraction_result = await self.extract_entities(cleaned_markdown, document)

            # Step 3: Persist to FalkorDB
            persistence_stats = await self.persist_to_falkordb(extraction_result)

            total_time = (datetime.now() - start_time).total_seconds()

            return {
                "document": document.filename,
                "category": document.category,
                "size_mb": document.size_mb,
                "markdown_chars": len(cleaned_markdown),
                "markdown_words": len(cleaned_markdown.split()),
                "extraction_time_seconds": extraction_result.extraction_time_seconds,
                "total_time_seconds": total_time,
                **persistence_stats
            }

        except Exception as e:
            logger.error(f"Failed to ingest {document.filename}: {e}")
            raise

    async def ingest_all(
        self,
        max_documents: Optional[int] = None,
        save_markdown: bool = False,
        markdown_output_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """Ingest all PDF documents."""
        documents = self.discover_pdfs()

        if max_documents:
            documents = documents[:max_documents]

        logger.info(f"Ingesting {len(documents)} documents")

        results = []
        for i, document in enumerate(documents, 1):
            logger.info(f"Processing {i}/{len(documents)}: {document.filename}")

            try:
                result = await self.ingest_document(
                    document,
                    save_markdown=save_markdown,
                    markdown_output_dir=markdown_output_dir
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Failed: {document.filename}: {e}")
                results.append({
                    "document": document.filename,
                    "error": str(e)
                })

        return results
