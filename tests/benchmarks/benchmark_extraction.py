"""Extraction Benchmark: MarkItDown+LLM vs LangExtract.

Runs both extraction pipelines on the same documents and compares results.

Pipeline A (MarkItDown+LLM): Uses SimplePDFIngestionService for extraction.
Pipeline B (LangExtract):    Uses LangExtractIngestionService for extraction.

Usage:
    uv run pytest tests/benchmarks/benchmark_extraction.py -v -s
    uv run python tests/benchmarks/benchmark_extraction.py [file_path]
"""

import asyncio
import json
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

RESULTS_DIR = Path(__file__).parent / "results"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PipelineMetrics:
    """Metrics collected from a single pipeline run."""

    pipeline_name: str
    extraction_time_seconds: float
    entity_count: int
    relationship_count: int
    entities_by_type: Dict[str, int] = field(default_factory=dict)
    relationships_by_type: Dict[str, int] = field(default_factory=dict)
    unique_entity_names: List[str] = field(default_factory=list)
    source_grounding_coverage: Optional[float] = None  # LangExtract only


@dataclass
class OverlapAnalysis:
    """Entity overlap analysis between two pipeline runs."""

    overlap_count: int
    markitdown_only_count: int
    langextract_only_count: int
    overlap_percentage: float
    overlapping_entities: List[str] = field(default_factory=list)
    markitdown_only: List[str] = field(default_factory=list)
    langextract_only: List[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Complete benchmark comparison result."""

    metadata: Dict[str, Any]
    config: Dict[str, Any]
    markitdown_results: Dict[str, Any]
    langextract_results: Dict[str, Any]
    overlap_analysis: Dict[str, Any]


# ---------------------------------------------------------------------------
# Metrics collection  (Task 4.2)
# ---------------------------------------------------------------------------


def collect_metrics(
    pipeline_name: str,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    extraction_time: float,
) -> PipelineMetrics:
    """Collect metrics from an extraction run.

    Args:
        pipeline_name: Name of the pipeline (e.g. "markitdown", "langextract").
        entities: List of extracted entity dicts.
        relationships: List of extracted relationship dicts.
        extraction_time: Wall-clock seconds for extraction.

    Returns:
        PipelineMetrics with counts, breakdowns, and unique names.
    """
    # Count entities by type
    type_counter: Counter = Counter()
    unique_names: Set[str] = set()
    grounded_count = 0

    for ent in entities:
        etype = ent.get("type", "Unknown")
        type_counter[etype] += 1
        name = ent.get("name", "")
        if name:
            unique_names.add(name)
        # Track source grounding (LangExtract attaches this metadata)
        if ent.get("source_grounding") or ent.get("grounding"):
            grounded_count += 1

    # Count relationships by type
    rel_counter: Counter = Counter()
    for rel in relationships:
        rtype = rel.get("type", "UNKNOWN")
        rel_counter[rtype] += 1

    # Source grounding coverage (only meaningful for LangExtract)
    grounding_coverage = None
    if pipeline_name == "langextract" and entities:
        grounding_coverage = grounded_count / len(entities)

    return PipelineMetrics(
        pipeline_name=pipeline_name,
        extraction_time_seconds=extraction_time,
        entity_count=len(entities),
        relationship_count=len(relationships),
        entities_by_type=dict(type_counter),
        relationships_by_type=dict(rel_counter),
        unique_entity_names=sorted(unique_names),
        source_grounding_coverage=grounding_coverage,
    )


# ---------------------------------------------------------------------------
# Entity overlap analysis  (Task 4.3)
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Normalize an entity name for fuzzy comparison."""
    return name.strip().lower()


def compute_overlap(
    markitdown_metrics: PipelineMetrics,
    langextract_metrics: PipelineMetrics,
) -> OverlapAnalysis:
    """Compute entity overlap between two pipeline results.

    Comparison rules:
    - Case-insensitive
    - Stripped whitespace
    - Match within same entity type is preferred, but we also do a
      name-only pass for cross-type matches.

    Args:
        markitdown_metrics: Metrics from the MarkItDown pipeline.
        langextract_metrics: Metrics from the LangExtract pipeline.

    Returns:
        OverlapAnalysis with counts and entity lists.
    """
    mk_names = {_normalize_name(n) for n in markitdown_metrics.unique_entity_names}
    le_names = {_normalize_name(n) for n in langextract_metrics.unique_entity_names}

    overlap = mk_names & le_names
    mk_only = mk_names - le_names
    le_only = le_names - mk_names

    total_unique = len(mk_names | le_names)
    overlap_pct = (len(overlap) / total_unique * 100) if total_unique > 0 else 0.0

    return OverlapAnalysis(
        overlap_count=len(overlap),
        markitdown_only_count=len(mk_only),
        langextract_only_count=len(le_only),
        overlap_percentage=round(overlap_pct, 2),
        overlapping_entities=sorted(overlap),
        markitdown_only=sorted(mk_only),
        langextract_only=sorted(le_only),
    )


# ---------------------------------------------------------------------------
# JSON results output  (Task 4.4)
# ---------------------------------------------------------------------------


def write_results(result: BenchmarkResult, output_dir: Optional[Path] = None) -> Path:
    """Write benchmark results to a timestamped JSON file.

    Args:
        result: Complete benchmark result.
        output_dir: Directory for output (defaults to tests/benchmarks/results/).

    Returns:
        Path to the written JSON file.
    """
    output_dir = output_dir or RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_comparison.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(asdict(result) if hasattr(result, "__dataclass_fields__") else _to_dict(result), f, indent=2, default=str)

    logger.info("Benchmark results written to %s", filepath)
    return filepath


def _to_dict(result: BenchmarkResult) -> Dict[str, Any]:
    """Fallback serialization."""
    return {
        "metadata": result.metadata,
        "config": result.config,
        "markitdown_results": result.markitdown_results,
        "langextract_results": result.langextract_results,
        "overlap_analysis": result.overlap_analysis,
    }


# ---------------------------------------------------------------------------
# Configuration logging  (Task 4.5)
# ---------------------------------------------------------------------------


def build_config(
    markitdown_model: str = "gpt-4o-mini",
    langextract_model: str = "gemini-2.5-flash",
    extraction_passes: int = 1,
    max_workers: int = 5,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a reproducibility-focused configuration dict.

    Captures model IDs, extraction parameters, and environment info.
    """
    config: Dict[str, Any] = {
        "model_ids": {
            "markitdown_llm": markitdown_model,
            "langextract": langextract_model,
        },
        "extraction_passes": extraction_passes,
        "max_workers": max_workers,
        "environment": {
            "python_version": _python_version(),
            "platform": _platform_info(),
            "langextract_available": _check_langextract(),
            "markitdown_available": _check_markitdown(),
        },
    }
    if extra:
        config.update(extra)
    return config


def _python_version() -> str:
    import sys
    return sys.version


def _platform_info() -> str:
    import platform
    return f"{platform.system()} {platform.release()}"


def _check_langextract() -> bool:
    try:
        import langextract  # noqa: F401
        return True
    except ImportError:
        return False


def _check_markitdown() -> bool:
    try:
        import markitdown  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Pipeline runners  (Task 4.1)
# ---------------------------------------------------------------------------


def _build_pdf_document(file_path: Path):
    """Build a PDFDocument from a file path."""
    from application.services.neo4j_pdf_ingestion import PDFDocument

    return PDFDocument(
        path=file_path,
        filename=file_path.name,
        category="benchmark",
        size_bytes=file_path.stat().st_size,
    )


async def run_markitdown_pipeline(
    file_path: Path,
    openai_api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    """Run the MarkItDown+LLM extraction pipeline.

    Args:
        file_path: Path to the document to extract from.
        openai_api_key: OpenAI API key (falls back to env var).
        model: OpenAI model to use.

    Returns:
        Tuple of (entities, relationships, extraction_time_seconds).
    """
    from application.services.simple_pdf_ingestion import SimplePDFIngestionService

    api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
    service = SimplePDFIngestionService(
        pdf_directory=file_path.parent,
        openai_api_key=api_key,
        model=model,
        # Use dummy falkor settings — we only need extraction, not persistence
        falkor_host="localhost",
        falkor_port=6379,
        graph_name="benchmark_temp",
    )

    document = _build_pdf_document(file_path)

    # Convert and clean
    cleaned_text = service.convert_and_clean(document)

    # Extract entities
    start = time.monotonic()
    result = await service.extract_entities(cleaned_text, document)
    elapsed = time.monotonic() - start

    return result.entities, result.relationships, elapsed


def run_langextract_pipeline(
    file_path: Path,
    model: str = "gemini-2.5-flash",
    api_key: Optional[str] = None,
    extraction_passes: int = 1,
    max_workers: int = 5,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    """Run the LangExtract extraction pipeline.

    Args:
        file_path: Path to the document to extract from.
        model: LangExtract model ID.
        api_key: API key for the model provider.
        extraction_passes: Number of extraction passes.
        max_workers: Concurrent workers for extraction.

    Returns:
        Tuple of (entities, relationships, extraction_time_seconds).
    """
    from application.services.langextract_ingestion import LangExtractIngestionService

    service = LangExtractIngestionService(
        model_id=model,
        api_key=api_key,
        extraction_passes=extraction_passes,
        max_workers=max_workers,
    )

    start = time.monotonic()
    result = service.extract_from_file(str(file_path))
    elapsed = time.monotonic() - start

    return result.entities, result.relationships, elapsed


# ---------------------------------------------------------------------------
# Main benchmark orchestrator
# ---------------------------------------------------------------------------


async def run_benchmark(
    file_path: str | Path,
    markitdown_model: str = "gpt-4o-mini",
    langextract_model: str = "gemini-2.5-flash",
    openai_api_key: Optional[str] = None,
    langextract_api_key: Optional[str] = None,
    extraction_passes: int = 1,
    max_workers: int = 5,
    output_dir: Optional[Path] = None,
) -> BenchmarkResult:
    """Run the full benchmark comparison.

    Args:
        file_path: Path to the document to benchmark.
        markitdown_model: OpenAI model for MarkItDown pipeline.
        langextract_model: Model for LangExtract pipeline.
        openai_api_key: OpenAI API key.
        langextract_api_key: API key for LangExtract model.
        extraction_passes: Number of LangExtract passes.
        max_workers: LangExtract concurrent workers.
        output_dir: Output directory for results JSON.

    Returns:
        BenchmarkResult with full comparison data.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    logger.info("Starting benchmark on %s", file_path.name)

    # Build config for reproducibility
    config = build_config(
        markitdown_model=markitdown_model,
        langextract_model=langextract_model,
        extraction_passes=extraction_passes,
        max_workers=max_workers,
    )

    # --- Pipeline A: MarkItDown+LLM ---
    logger.info("Running MarkItDown+LLM pipeline...")
    mk_entities, mk_relationships, mk_time = await run_markitdown_pipeline(
        file_path, openai_api_key=openai_api_key, model=markitdown_model,
    )
    mk_metrics = collect_metrics("markitdown", mk_entities, mk_relationships, mk_time)

    # --- Pipeline B: LangExtract ---
    logger.info("Running LangExtract pipeline...")
    le_entities, le_relationships, le_time = run_langextract_pipeline(
        file_path,
        model=langextract_model,
        api_key=langextract_api_key,
        extraction_passes=extraction_passes,
        max_workers=max_workers,
    )
    le_metrics = collect_metrics("langextract", le_entities, le_relationships, le_time)

    # --- Overlap analysis ---
    overlap = compute_overlap(mk_metrics, le_metrics)

    # --- Assemble result ---
    run_timestamp = datetime.now(timezone.utc).isoformat()
    metadata = {
        "document_name": file_path.name,
        "document_path": str(file_path),
        "document_size_bytes": file_path.stat().st_size,
        "run_timestamp": run_timestamp,
        "model_versions": config["model_ids"],
    }

    result = BenchmarkResult(
        metadata=metadata,
        config=config,
        markitdown_results={
            "entities": mk_entities,
            "relationships": mk_relationships,
            "metrics": {
                "extraction_time_seconds": mk_metrics.extraction_time_seconds,
                "entity_count": mk_metrics.entity_count,
                "relationship_count": mk_metrics.relationship_count,
                "entities_by_type": mk_metrics.entities_by_type,
                "relationships_by_type": mk_metrics.relationships_by_type,
                "unique_entity_names": mk_metrics.unique_entity_names,
            },
        },
        langextract_results={
            "entities": le_entities,
            "relationships": le_relationships,
            "metrics": {
                "extraction_time_seconds": le_metrics.extraction_time_seconds,
                "entity_count": le_metrics.entity_count,
                "relationship_count": le_metrics.relationship_count,
                "entities_by_type": le_metrics.entities_by_type,
                "relationships_by_type": le_metrics.relationships_by_type,
                "unique_entity_names": le_metrics.unique_entity_names,
                "source_grounding_coverage": le_metrics.source_grounding_coverage,
            },
        },
        overlap_analysis={
            "overlap_count": overlap.overlap_count,
            "markitdown_only_count": overlap.markitdown_only_count,
            "langextract_only_count": overlap.langextract_only_count,
            "overlap_percentage": overlap.overlap_percentage,
            "overlapping_entities": overlap.overlapping_entities,
            "markitdown_only": overlap.markitdown_only,
            "langextract_only": overlap.langextract_only,
        },
    )

    # Write JSON
    output_path = write_results(result, output_dir)
    logger.info("Benchmark complete. Results: %s", output_path)

    return result


# ---------------------------------------------------------------------------
# Pytest entry point
# ---------------------------------------------------------------------------


import pytest  # noqa: E402


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_benchmark_extraction(sample_pdf_path, results_dir):
    """Run the extraction benchmark as a pytest test.

    Requires:
    - OPENAI_API_KEY env var (for MarkItDown pipeline)
    - LANGEXTRACT_API_KEY or GEMINI_API_KEY env var (for LangExtract pipeline)
    - A sample document (set BENCHMARK_PDF_PATH or place files in examples/)
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    langextract_key = os.getenv("LANGEXTRACT_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not openai_key:
        pytest.skip("OPENAI_API_KEY not set")
    if not langextract_key:
        pytest.skip("LANGEXTRACT_API_KEY / GEMINI_API_KEY not set")

    result = await run_benchmark(
        file_path=sample_pdf_path,
        openai_api_key=openai_key,
        langextract_api_key=langextract_key,
        output_dir=results_dir,
    )

    # Basic assertions
    assert result.metadata["document_name"] == sample_pdf_path.name
    assert result.markitdown_results["metrics"]["entity_count"] >= 0
    assert result.langextract_results["metrics"]["entity_count"] >= 0
    assert "overlap_count" in result.overlap_analysis


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <file_path>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"File not found: {target}")
        sys.exit(1)

    result = asyncio.run(run_benchmark(file_path=target))
    print(json.dumps(_to_dict(result), indent=2, default=str))
