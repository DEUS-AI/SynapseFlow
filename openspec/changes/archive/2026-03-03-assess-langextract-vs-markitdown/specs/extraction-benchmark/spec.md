## ADDED Requirements

### Requirement: Benchmark harness for extraction comparison
The system SHALL provide a benchmark harness at `tests/benchmarks/benchmark_extraction.py` that runs both the existing MarkItDown+LLM extraction pipeline and the new LangExtract pipeline against the same set of documents, collecting structured metrics for comparison.

**Primary files**: `tests/benchmarks/benchmark_extraction.py`, `tests/benchmarks/conftest.py`

#### Scenario: Run benchmark on a single document
- **WHEN** the benchmark is executed with a path to a PDF document
- **THEN** it SHALL run both extraction pipelines on that document and output a JSON results file containing entity counts, relationship counts, extraction time, and per-entity details for each pipeline

#### Scenario: Run benchmark on a document corpus
- **WHEN** the benchmark is executed with a directory path containing multiple PDFs
- **THEN** it SHALL process each document through both pipelines and produce an aggregate results file with per-document and overall summary metrics

### Requirement: Metrics collection
The benchmark SHALL collect the following metrics for each pipeline run:
- Entity count (total and per type)
- Relationship count (total and per type)
- Extraction time (seconds)
- Unique entity names (for overlap calculation)
- Source grounding coverage (percentage of entities with grounding data, LangExtract only)

#### Scenario: Metrics output format
- **WHEN** a benchmark run completes
- **THEN** results SHALL be written to a JSON file at `tests/benchmarks/results/<timestamp>_comparison.json` with keys `markitdown_results`, `langextract_results`, and `metadata` (document name, run timestamp, model versions)

### Requirement: Entity overlap analysis
The benchmark SHALL compute entity overlap between the two pipelines: how many entities were found by both, only by MarkItDown+LLM, and only by LangExtract. Overlap SHALL be computed using fuzzy name matching (case-insensitive, stripped whitespace) within the same entity type.

#### Scenario: Overlap computation
- **WHEN** both pipelines have produced entity lists for the same document
- **THEN** the benchmark SHALL output `overlap_count`, `markitdown_only_count`, `langextract_only_count`, and `overlap_percentage` in the results

### Requirement: Reproducible benchmark runs
The benchmark SHALL use fixed random seeds where applicable and log all configuration parameters (model IDs, chunk sizes, extraction passes) to ensure runs are reproducible.

#### Scenario: Deterministic configuration logging
- **WHEN** a benchmark run starts
- **THEN** the configuration (model IDs, API endpoints, chunk sizes, extraction_passes, max_workers) SHALL be logged to the results JSON under the `config` key
