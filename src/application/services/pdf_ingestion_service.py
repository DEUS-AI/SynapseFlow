"""PDF Knowledge Ingestion Service.

This service handles the extraction of knowledge from PDF documents:
1. Converts PDF to Markdown using markitdown
2. Cleans and preprocesses the Markdown content
3. Extracts entities using Graphiti (LLM-powered)
4. Persists knowledge graph to FalkorDB

Workflow:
    PDF → Markdown → Clean → Graphiti Entity Extraction → FalkorDB Persistence
"""

import re
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

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False

from infrastructure.falkor_backend import FalkorBackend

logger = logging.getLogger(__name__)


@dataclass
class PDFDocument:
    """Represents a PDF document with metadata."""
    path: Path
    filename: str
    category: Optional[str]  # e.g., "general", "lupus", "ibd"
    size_bytes: int

    @property
    def size_mb(self) -> float:
        """Return size in MB."""
        return self.size_bytes / (1024 * 1024)


@dataclass
class MarkdownContent:
    """Represents converted Markdown content."""
    raw_markdown: str
    cleaned_markdown: str
    document: PDFDocument
    metadata: Dict[str, Any]

    @property
    def word_count(self) -> int:
        """Approximate word count."""
        return len(self.cleaned_markdown.split())

    @property
    def char_count(self) -> int:
        """Character count."""
        return len(self.cleaned_markdown)


@dataclass
class ExtractionResult:
    """Results from Graphiti entity extraction."""
    document: PDFDocument
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    extraction_time_seconds: float
    token_count: Optional[int] = None

    @property
    def entity_count(self) -> int:
        """Number of entities extracted."""
        return len(self.entities)

    @property
    def relationship_count(self) -> int:
        """Number of relationships extracted."""
        return len(self.relationships)


class PDFToMarkdownConverter:
    """Converts PDF files to Markdown format using markitdown."""

    def __init__(self):
        """Initialize the converter."""
        if not MARKITDOWN_AVAILABLE:
            raise ImportError(
                "markitdown is not available. Install with: uv add 'markitdown[pdf]'"
            )

        self.converter = MarkItDown()
        logger.info("PDFToMarkdownConverter initialized")

    def convert(self, pdf_path: Path) -> str:
        """Convert a PDF file to Markdown.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Raw Markdown content

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            Exception: If conversion fails
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info(f"Converting PDF to Markdown: {pdf_path.name}")

        try:
            # markitdown returns a Result object with .text_content attribute
            result = self.converter.convert(str(pdf_path))
            markdown = result.text_content

            logger.info(
                f"Converted {pdf_path.name}: {len(markdown)} chars, "
                f"{len(markdown.split())} words"
            )

            return markdown

        except Exception as e:
            logger.error(f"Failed to convert {pdf_path.name}: {e}")
            raise


class MarkdownCleaner:
    """Cleans and preprocesses Markdown content for better entity extraction."""

    # Patterns to remove or normalize
    REMOVE_PATTERNS = [
        r'\n{3,}',  # Multiple newlines → 2 newlines
        r'[ \t]+\n',  # Trailing whitespace
        r'\n[ \t]+',  # Leading whitespace
        r'---+',  # Horizontal rules (often metadata separators)
    ]

    # Patterns to normalize
    NORMALIZE_PATTERNS = [
        (r'\*\*\*(.+?)\*\*\*', r'**\1**'),  # Bold+italic → bold
        (r'__(.+?)__', r'**\1**'),  # Underline bold → ** bold
        (r'_(.+?)_', r'*\1*'),  # Underline italic → * italic
    ]

    def clean(self, markdown: str) -> str:
        """Clean and preprocess Markdown content.

        Args:
            markdown: Raw Markdown content

        Returns:
            Cleaned Markdown content
        """
        logger.info(f"Cleaning Markdown: {len(markdown)} chars")

        cleaned = markdown

        # Remove unwanted patterns
        for pattern in self.REMOVE_PATTERNS:
            cleaned = re.sub(pattern, '\n\n', cleaned)

        # Normalize formatting
        for pattern, replacement in self.NORMALIZE_PATTERNS:
            cleaned = re.sub(pattern, replacement, cleaned)

        # Remove excessive whitespace
        cleaned = cleaned.strip()

        # Remove very short lines (likely artifacts)
        lines = cleaned.split('\n')
        filtered_lines = [
            line for line in lines
            if len(line.strip()) > 2 or line.strip() in ['', '#']
        ]
        cleaned = '\n'.join(filtered_lines)

        logger.info(
            f"Cleaned Markdown: {len(cleaned)} chars "
            f"({len(markdown) - len(cleaned)} chars removed)"
        )

        return cleaned


class GraphitiEntityExtractor:
    """Extracts entities and relationships from text using Graphiti (LLM-powered)."""

    def __init__(
        self,
        openai_api_key: str,
        model: str = "gpt-4o-mini"
    ):
        """Initialize Graphiti entity extractor.

        Args:
            openai_api_key: OpenAI API key for LLM-based extraction
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        """
        if not GRAPHITI_AVAILABLE:
            raise ImportError(
                "graphiti_core is not available. Install with: uv add 'graphiti-core[openai]'"
            )

        self.api_key = openai_api_key
        self.model = model

        # Initialize Graphiti client
        # Note: Graphiti uses in-memory graph for extraction
        self.graphiti = Graphiti(
            uri="bolt://localhost:7687",  # Placeholder - not actually used for extraction
            user="neo4j",
            password="password"
        )

        logger.info(f"GraphitiEntityExtractor initialized with model={model}")

    async def extract(
        self,
        text: str,
        source_name: str,
        episode_type: str = "document"
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract entities and relationships from text.

        Args:
            text: Cleaned Markdown content to extract from
            source_name: Name of the source document
            episode_type: Type of episode (default: "document")

        Returns:
            Tuple of (entities, relationships)
        """
        logger.info(
            f"Extracting entities from {source_name}: "
            f"{len(text)} chars, {len(text.split())} words"
        )

        start_time = datetime.now()

        try:
            # Add episode to Graphiti (triggers LLM-based entity extraction)
            await self.graphiti.add_episode(
                name=source_name,
                episode_body=text,
                source=EpisodeType.text,
                reference_time=datetime.now()
            )

            # Retrieve extracted entities and relationships from Graphiti's graph
            # Note: This is simplified - in practice, we'd query the Graphiti graph
            # For now, we'll return empty lists and rely on direct extraction

            # TODO: Query Graphiti's internal graph to get extracted entities
            entities = []
            relationships = []

            extraction_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Extracted from {source_name}: "
                f"{len(entities)} entities, {len(relationships)} relationships "
                f"in {extraction_time:.2f}s"
            )

            return entities, relationships

        except Exception as e:
            logger.error(f"Failed to extract from {source_name}: {e}")
            raise


class PDFKnowledgeIngestionService:
    """Main service for ingesting knowledge from PDF documents.

    This orchestrates the complete workflow:
    1. Discover PDF files
    2. Convert to Markdown
    3. Clean Markdown
    4. Extract entities with Graphiti
    5. Persist to FalkorDB
    """

    def __init__(
        self,
        pdf_directory: Path,
        falkor_host: str = "localhost",
        falkor_port: int = 6379,
        graph_name: str = "medical_knowledge",
        openai_api_key: Optional[str] = None
    ):
        """Initialize the PDF ingestion service.

        Args:
            pdf_directory: Root directory containing PDF files
            falkor_host: FalkorDB host
            falkor_port: FalkorDB port
            graph_name: Name of the knowledge graph in FalkorDB
            openai_api_key: OpenAI API key (required for Graphiti)
        """
        self.pdf_directory = Path(pdf_directory)

        if not self.pdf_directory.exists():
            raise ValueError(f"PDF directory does not exist: {pdf_directory}")

        # Initialize components
        self.pdf_converter = PDFToMarkdownConverter()
        self.markdown_cleaner = MarkdownCleaner()

        if openai_api_key:
            self.entity_extractor = GraphitiEntityExtractor(openai_api_key)
        else:
            logger.warning("No OpenAI API key provided - entity extraction disabled")
            self.entity_extractor = None

        self.backend = FalkorBackend(
            host=falkor_host,
            port=falkor_port,
            graph_name=graph_name
        )

        logger.info(
            f"PDFKnowledgeIngestionService initialized: "
            f"pdf_dir={pdf_directory}, graph={graph_name}"
        )

    def discover_pdfs(self) -> List[PDFDocument]:
        """Discover all PDF files in the directory tree.

        Returns:
            List of PDFDocument objects
        """
        logger.info(f"Discovering PDFs in {self.pdf_directory}")

        pdf_files = list(self.pdf_directory.rglob("*.pdf"))

        documents = []
        for pdf_path in pdf_files:
            # Determine category from directory structure
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

    def convert_pdf_to_markdown(self, document: PDFDocument) -> MarkdownContent:
        """Convert a PDF document to cleaned Markdown.

        Args:
            document: PDF document to convert

        Returns:
            MarkdownContent with raw and cleaned versions
        """
        # Convert to Markdown
        raw_markdown = self.pdf_converter.convert(document.path)

        # Clean Markdown
        cleaned_markdown = self.markdown_cleaner.clean(raw_markdown)

        # Extract metadata
        metadata = {
            "source_file": document.filename,
            "category": document.category,
            "size_mb": document.size_mb,
            "converted_at": datetime.now().isoformat()
        }

        return MarkdownContent(
            raw_markdown=raw_markdown,
            cleaned_markdown=cleaned_markdown,
            document=document,
            metadata=metadata
        )

    async def extract_knowledge(
        self,
        markdown_content: MarkdownContent
    ) -> ExtractionResult:
        """Extract entities and relationships from Markdown content.

        Args:
            markdown_content: Cleaned Markdown content

        Returns:
            ExtractionResult with entities and relationships
        """
        if not self.entity_extractor:
            raise ValueError("Entity extractor not initialized (missing OpenAI API key)")

        start_time = datetime.now()

        # Extract entities and relationships using Graphiti
        entities, relationships = await self.entity_extractor.extract(
            text=markdown_content.cleaned_markdown,
            source_name=markdown_content.document.filename
        )

        extraction_time = (datetime.now() - start_time).total_seconds()

        return ExtractionResult(
            document=markdown_content.document,
            entities=entities,
            relationships=relationships,
            extraction_time_seconds=extraction_time
        )

    async def persist_to_falkordb(
        self,
        extraction_result: ExtractionResult
    ) -> Dict[str, Any]:
        """Persist extracted knowledge to FalkorDB.

        Args:
            extraction_result: Extraction result with entities and relationships

        Returns:
            Statistics about persisted data
        """
        logger.info(
            f"Persisting to FalkorDB: "
            f"{extraction_result.entity_count} entities, "
            f"{extraction_result.relationship_count} relationships"
        )

        entities_added = 0
        relationships_added = 0

        # Add entities
        for entity in extraction_result.entities:
            entity_id = f"{entity.get('type', 'Entity')}:{entity.get('id', 'unknown')}"
            properties = {
                **entity,
                "source_document": extraction_result.document.filename,
                "category": extraction_result.document.category,
                "layer": "PERCEPTION",  # Initial layer in DIKW hierarchy
                "created_at": datetime.now().isoformat()
            }

            await self.backend.add_entity(entity_id, properties)
            entities_added += 1

        # Add relationships
        for rel in extraction_result.relationships:
            source_id = rel.get("source_id")
            target_id = rel.get("target_id")
            rel_type = rel.get("type", "RELATES_TO")

            if source_id and target_id:
                await self.backend.add_relationship(
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=rel_type,
                    properties={
                        "source_document": extraction_result.document.filename,
                        "created_at": datetime.now().isoformat()
                    }
                )
                relationships_added += 1

        logger.info(
            f"Persisted: {entities_added} entities, {relationships_added} relationships"
        )

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
        """Ingest a single PDF document through the complete pipeline.

        Args:
            document: PDF document to ingest
            save_markdown: Whether to save intermediate Markdown files
            markdown_output_dir: Directory to save Markdown files (if save_markdown=True)

        Returns:
            Ingestion statistics and results
        """
        logger.info(f"Ingesting document: {document.filename}")

        start_time = datetime.now()

        try:
            # Step 1: Convert PDF to Markdown
            markdown_content = self.convert_pdf_to_markdown(document)

            # Optionally save Markdown
            if save_markdown and markdown_output_dir:
                markdown_output_dir.mkdir(parents=True, exist_ok=True)
                markdown_path = markdown_output_dir / f"{document.path.stem}.md"
                markdown_path.write_text(markdown_content.cleaned_markdown, encoding='utf-8')
                logger.info(f"Saved Markdown: {markdown_path}")

            # Step 2: Extract knowledge with Graphiti
            extraction_result = await self.extract_knowledge(markdown_content)

            # Step 3: Persist to FalkorDB
            persistence_stats = await self.persist_to_falkordb(extraction_result)

            total_time = (datetime.now() - start_time).total_seconds()

            return {
                "document": document.filename,
                "category": document.category,
                "size_mb": document.size_mb,
                "markdown_chars": markdown_content.char_count,
                "markdown_words": markdown_content.word_count,
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
        """Ingest all PDF documents in the directory.

        Args:
            max_documents: Maximum number of documents to process (None = all)
            save_markdown: Whether to save intermediate Markdown files
            markdown_output_dir: Directory to save Markdown files

        Returns:
            List of ingestion results for each document
        """
        documents = self.discover_pdfs()

        if max_documents:
            documents = documents[:max_documents]

        logger.info(f"Ingesting {len(documents)} documents")

        # Create markdown output directory if needed
        if save_markdown and markdown_output_dir:
            markdown_output_dir = Path(markdown_output_dir)
            markdown_output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for i, document in enumerate(documents, 1):
            logger.info(f"Processing document {i}/{len(documents)}: {document.filename}")

            try:
                result = await self.ingest_document(
                    document,
                    save_markdown=save_markdown,
                    markdown_output_dir=markdown_output_dir
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Failed to process {document.filename}: {e}")
                results.append({
                    "document": document.filename,
                    "error": str(e)
                })

        # Summary statistics
        total_time = sum(r.get("total_time_seconds", 0) for r in results)
        total_entities = sum(r.get("entities_added", 0) for r in results)
        total_relationships = sum(r.get("relationships_added", 0) for r in results)

        logger.info(
            f"Ingestion complete: {len(results)} documents, "
            f"{total_entities} entities, {total_relationships} relationships "
            f"in {total_time:.2f}s"
        )

        return results
