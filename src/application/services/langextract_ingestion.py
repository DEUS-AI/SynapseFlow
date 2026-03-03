"""LangExtract-based Knowledge Ingestion Service.

Workflow: File -> Markdown (MarkItDown) -> LangExtract entity extraction -> ExtractionResult

Uses LangExtract's few-shot example-driven extraction to pull medical entities
from documents, producing PERCEPTION-layer entities for the DIKW pyramid.
"""

import os
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import langextract as lx

    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False

from application.services.neo4j_pdf_ingestion import ExtractionResult, PDFDocument

logger = logging.getLogger(__name__)

# SynapseFlow entity taxonomy
ENTITY_TYPES = [
    "Disease",
    "Treatment",
    "Symptom",
    "Test",
    "Drug",
    "Gene",
    "Pathway",
    "Organization",
    "Study",
]


class LangExtractIngestionService:
    """Ingestion service using LangExtract for few-shot entity extraction.

    Converts files to markdown via MarkItDown, then uses LangExtract
    with few-shot examples to extract medical entities aligned to the
    SynapseFlow taxonomy.
    """

    def __init__(
        self,
        model_id: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        extraction_passes: int = 1,
        max_workers: int = 5,
        max_char_buffer: int = 10000,
    ):
        if not LANGEXTRACT_AVAILABLE:
            raise ImportError(
                "langextract is not installed. "
                "Install it with: uv pip install langextract "
                "or: uv sync --extra langextract"
            )

        self.model_id = model_id
        self.api_key = api_key or os.getenv("LANGEXTRACT_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.extraction_passes = extraction_passes
        self.max_workers = max_workers
        self.max_char_buffer = max_char_buffer

        # Model-specific settings
        self._is_openai_model = model_id.startswith(("gpt-", "o1-", "o3-"))
        self.fence_output = self._is_openai_model
        self.use_schema_constraints = not self._is_openai_model

        # Initialize MarkItDown for file conversion
        from application.services.markitdown_wrapper import MarkItDownWrapper

        self._converter = MarkItDownWrapper()

        # Build few-shot examples
        self._examples = self._build_examples()

        logger.info(
            "LangExtractIngestionService initialized: model=%s, passes=%d, workers=%d",
            self.model_id,
            self.extraction_passes,
            self.max_workers,
        )

    def _build_examples(self) -> list:
        """Build few-shot extraction examples for medical entities.

        Each example demonstrates the expected extraction output for a
        representative medical text snippet, covering the full SynapseFlow
        entity taxonomy.
        """
        if not LANGEXTRACT_AVAILABLE:
            return []

        return [
            lx.data.ExampleData(
                text=(
                    "Methotrexate is a first-line disease-modifying antirheumatic drug "
                    "(DMARD) used in rheumatoid arthritis. It inhibits dihydrofolate "
                    "reductase in the folate metabolism pathway. Common side effects "
                    "include nausea, fatigue, and elevated liver enzymes detected by "
                    "liver function tests."
                ),
                extractions=[
                    lx.data.Extraction(
                        extraction_class="Drug",
                        extraction_text="Methotrexate",
                        attributes={
                            "description": "First-line DMARD for rheumatoid arthritis",
                            "confidence": 0.95,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Disease",
                        extraction_text="rheumatoid arthritis",
                        attributes={
                            "description": "Chronic autoimmune inflammatory joint disease",
                            "confidence": 0.95,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Treatment",
                        extraction_text="disease-modifying antirheumatic drug",
                        attributes={
                            "description": "Class of drugs that slow disease progression in RA",
                            "confidence": 0.90,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Pathway",
                        extraction_text="folate metabolism pathway",
                        attributes={
                            "description": "Metabolic pathway involving folic acid processing",
                            "confidence": 0.85,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Gene",
                        extraction_text="dihydrofolate reductase",
                        attributes={
                            "description": "Enzyme in folate metabolism inhibited by methotrexate",
                            "confidence": 0.90,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Symptom",
                        extraction_text="nausea",
                        attributes={
                            "description": "Common side effect of methotrexate therapy",
                            "confidence": 0.85,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Test",
                        extraction_text="liver function tests",
                        attributes={
                            "description": "Blood tests measuring liver enzyme levels",
                            "confidence": 0.90,
                        },
                    ),
                ],
            ),
            lx.data.ExampleData(
                text=(
                    "A phase III clinical trial conducted by the National Institutes "
                    "of Health demonstrated that combination therapy with adalimumab "
                    "and methotrexate significantly reduced joint inflammation in "
                    "patients with moderate-to-severe rheumatoid arthritis. TNF-alpha "
                    "inhibition was confirmed via serum biomarker assays."
                ),
                extractions=[
                    lx.data.Extraction(
                        extraction_class="Study",
                        extraction_text="phase III clinical trial",
                        attributes={
                            "description": "Late-stage clinical trial for combination RA therapy",
                            "confidence": 0.90,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Organization",
                        extraction_text="National Institutes of Health",
                        attributes={
                            "description": "US federal biomedical research agency",
                            "confidence": 0.95,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Drug",
                        extraction_text="adalimumab",
                        attributes={
                            "description": "TNF-alpha inhibitor biologic drug",
                            "confidence": 0.95,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Symptom",
                        extraction_text="joint inflammation",
                        attributes={
                            "description": "Inflammatory process in joints characteristic of RA",
                            "confidence": 0.85,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Pathway",
                        extraction_text="TNF-alpha",
                        attributes={
                            "description": "Tumor necrosis factor alpha inflammatory signaling pathway",
                            "confidence": 0.90,
                        },
                    ),
                    lx.data.Extraction(
                        extraction_class="Test",
                        extraction_text="serum biomarker assays",
                        attributes={
                            "description": "Blood-based tests measuring biological markers",
                            "confidence": 0.85,
                        },
                    ),
                ],
            ),
        ]

    def extract_from_file(self, file_path: str) -> ExtractionResult:
        """Extract entities and relationships from a file.

        Converts the file to markdown via MarkItDown, runs LangExtract
        extraction with few-shot examples, then maps the results into
        an ExtractionResult with source grounding and DIKW layer metadata.

        Args:
            file_path: Path to the file to process.

        Returns:
            ExtractionResult with extracted entities and relationships.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Build PDFDocument metadata
        document = PDFDocument(
            path=path,
            filename=path.name,
            category=path.parent.name if path.parent.name != path.root else "general",
            size_bytes=path.stat().st_size,
        )

        # Step 1: Convert file to markdown
        logger.info("Converting file to markdown: %s", path.name)
        markdown_text = self._converter.convert_to_markdown(str(path))
        if not markdown_text:
            logger.warning("MarkItDown returned empty content for %s", path.name)
            return ExtractionResult(
                document=document,
                entities=[],
                relationships=[],
                extraction_time_seconds=0.0,
            )

        # Step 2: Run LangExtract extraction
        logger.info(
            "Running LangExtract extraction: %d chars, model=%s",
            len(markdown_text),
            self.model_id,
        )
        start = time.time()

        prompt_description = (
            "Extract medical and biomedical entities from the text. "
            "Entity types: " + ", ".join(ENTITY_TYPES) + ". "
            "For each entity, provide a description and confidence score (0.0-1.0)."
        )

        extract_kwargs = {
            "text_or_documents": markdown_text,
            "prompt_description": prompt_description,
            "examples": self._examples,
            "model_id": self.model_id,
            "extraction_passes": self.extraction_passes,
            "max_workers": self.max_workers,
            "max_char_buffer": self.max_char_buffer,
        }
        if self.api_key:
            extract_kwargs["api_key"] = self.api_key
        if self.fence_output:
            extract_kwargs["fence_output"] = True
        if self.use_schema_constraints:
            extract_kwargs["use_schema_constraints"] = True

        result = lx.extract(**extract_kwargs)

        extraction_time = time.time() - start
        logger.info("Extraction completed in %.2fs", extraction_time)

        # Step 3: Convert raw extractions to entity dicts
        raw_extractions = self._parse_lx_result(result)

        # Step 4: Map source grounding metadata
        entities = self._map_source_grounding(raw_extractions)

        # Step 5: Assign DIKW PERCEPTION layer
        entities = self._assign_dikw_layer(entities)

        logger.info(
            "Extracted %d entities from %s",
            len(entities),
            path.name,
        )

        return ExtractionResult(
            document=document,
            entities=entities,
            relationships=[],
            extraction_time_seconds=extraction_time,
        )

    def _parse_lx_result(self, result: Any) -> List[Dict[str, Any]]:
        """Parse LangExtract result into a list of raw extraction dicts.

        Args:
            result: The object returned by lx.extract().

        Returns:
            List of dicts with extraction_class, extraction_text, attributes,
            and any source grounding data from the result.
        """
        extractions = []

        # lx.extract returns a result with an extractions attribute/list
        items = []
        if hasattr(result, "extractions"):
            items = result.extractions
        elif isinstance(result, list):
            items = result
        elif hasattr(result, "__iter__"):
            items = list(result)

        for item in items:
            entry: Dict[str, Any] = {}
            if hasattr(item, "extraction_class"):
                entry["type"] = item.extraction_class
            elif isinstance(item, dict):
                entry["type"] = item.get("extraction_class", "Entity")

            if hasattr(item, "extraction_text"):
                entry["name"] = item.extraction_text
            elif isinstance(item, dict):
                entry["name"] = item.get("extraction_text", "")

            # Attributes (description, confidence)
            attrs = {}
            if hasattr(item, "attributes"):
                attrs = item.attributes if isinstance(item.attributes, dict) else {}
            elif isinstance(item, dict):
                attrs = item.get("attributes", {})
            entry["description"] = attrs.get("description", "")
            entry["confidence"] = attrs.get("confidence", 0.7)

            # Preserve raw source grounding from LangExtract
            if hasattr(item, "source_text"):
                entry["_source_text"] = item.source_text
            if hasattr(item, "source_start"):
                entry["_source_start"] = item.source_start
            if hasattr(item, "source_end"):
                entry["_source_end"] = item.source_end
            if hasattr(item, "grounding"):
                entry["_grounding"] = item.grounding

            extractions.append(entry)

        return extractions

    def _map_source_grounding(
        self, raw_extractions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Map LangExtract source grounding to entity metadata.

        Collects any source grounding fields (source_text, source_start,
        source_end, grounding) from the raw extraction and stores them
        under the ``source_grounding`` key in each entity dict.

        Args:
            raw_extractions: Raw extraction dicts from LangExtract.

        Returns:
            Entities with source_grounding metadata attached.
        """
        entities = []
        for raw in raw_extractions:
            entity = {
                "name": raw.get("name", ""),
                "type": raw.get("type", "Entity"),
                "description": raw.get("description", ""),
                "confidence": raw.get("confidence", 0.7),
            }

            # Build source grounding metadata from internal fields
            grounding: Dict[str, Any] = {}
            if "_source_text" in raw:
                grounding["source_text"] = raw["_source_text"]
            if "_source_start" in raw:
                grounding["start_offset"] = raw["_source_start"]
            if "_source_end" in raw:
                grounding["end_offset"] = raw["_source_end"]
            if "_grounding" in raw:
                grounding["raw_grounding"] = raw["_grounding"]

            entity["source_grounding"] = grounding if grounding else {}
            entities.append(entity)

        return entities

    def _assign_dikw_layer(
        self, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Assign DIKW PERCEPTION layer and confidence to entities.

        All entities extracted from raw documents enter the knowledge graph
        at the PERCEPTION layer with a baseline confidence of 0.7, matching
        SynapseFlow's DIKW pyramid conventions.

        Args:
            entities: Entity dicts to annotate.

        Returns:
            Entities with layer and confidence fields set.
        """
        for entity in entities:
            entity["layer"] = "PERCEPTION"
            entity["confidence"] = 0.7
        return entities
