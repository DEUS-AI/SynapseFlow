## 1. Setup & Dependencies

- [x] 1.1 Add langextract as optional dependency in pyproject.toml with `[langextract]` extra
  <!-- Files: pyproject.toml -->
- [x] 1.2 Add LANGEXTRACT_API_KEY / GEMINI_API_KEY to environment variable documentation and .env.example
  <!-- Files: .env.example -->
- [x] 1.3 Create benchmark directories and __init__.py files
  <!-- Files: tests/benchmarks/__init__.py, tests/benchmarks/conftest.py, tests/benchmarks/results/.gitkeep -->

## 2. LangExtract Adapter - Core Service

- [x] 2.1 Create LangExtractIngestionService with configurable model, API key, extraction_passes, and max_workers
  <!-- Files: src/application/services/langextract_ingestion.py -->
- [x] 2.2 Define medical entity extraction examples (few-shot) for Disease, Treatment, Symptom, Drug, Test, Gene entity types
  <!-- Files: src/application/services/langextract_ingestion.py -->
- [x] 2.3 Implement extract_from_file() method: file → MarkItDown text → LangExtract extraction → ExtractionResult
  <!-- Files: src/application/services/langextract_ingestion.py -->
- [x] 2.4 Implement source grounding metadata mapping (character offsets → entity metadata dict)
  <!-- Files: src/application/services/langextract_ingestion.py -->
- [x] 2.5 Implement DIKW PERCEPTION layer assignment with default confidence 0.7
  <!-- Files: src/application/services/langextract_ingestion.py -->
- [x] 2.6 Add graceful handling for missing langextract package (LANGEXTRACT_AVAILABLE flag pattern)
  <!-- Files: src/application/services/langextract_ingestion.py -->

## 3. LangExtract Adapter - Tests

- [x] 3.1 Write unit tests for LangExtractIngestionService initialization and configuration
  <!-- Files: tests/application/test_langextract_ingestion.py -->
- [x] 3.2 Write unit tests for entity extraction with mocked LangExtract responses
  <!-- Files: tests/application/test_langextract_ingestion.py -->
- [x] 3.3 Write unit tests for source grounding metadata mapping
  <!-- Files: tests/application/test_langextract_ingestion.py -->
- [x] 3.4 Write unit tests for DIKW layer assignment and confidence scoring
  <!-- Files: tests/application/test_langextract_ingestion.py -->
- [x] 3.5 Write unit tests for missing package graceful degradation
  <!-- Files: tests/application/test_langextract_ingestion.py -->

## 4. Benchmark Harness

- [x] 4.1 Create benchmark runner that accepts a file path or directory and runs both pipelines
  <!-- Files: tests/benchmarks/benchmark_extraction.py -->
- [x] 4.2 Implement metrics collection: entity counts, relationship counts, extraction time, per-type breakdowns
  <!-- Files: tests/benchmarks/benchmark_extraction.py -->
- [x] 4.3 Implement entity overlap analysis with fuzzy name matching (case-insensitive, whitespace-stripped)
  <!-- Files: tests/benchmarks/benchmark_extraction.py -->
- [x] 4.4 Implement JSON results output to tests/benchmarks/results/<timestamp>_comparison.json
  <!-- Files: tests/benchmarks/benchmark_extraction.py -->
- [x] 4.5 Add configuration logging (model IDs, chunk sizes, passes) for reproducibility
  <!-- Files: tests/benchmarks/benchmark_extraction.py -->

## 5. Comparison Report

- [x] 5.1 Create Markdown report template with all required sections (Executive Summary, Quality, Grounding, Performance, Integration, Recommendation)
  <!-- Files: tests/benchmarks/report_template.md -->
- [x] 5.2 Create report generator script that reads benchmark JSON and produces filled Markdown report
  <!-- Files: tests/benchmarks/generate_report.py -->
- [x] 5.3 Implement 1-5 scoring rubric across all dimensions (recall, precision, relationships, grounding, speed, cost, integration)
  <!-- Files: tests/benchmarks/generate_report.py -->
- [x] 5.4 Implement integration gap analysis section with severity, effort, and mitigation
  <!-- Files: tests/benchmarks/generate_report.py -->
- [x] 5.5 Implement recommendation logic (ADOPT/STAY/HYBRID) based on aggregate scores
  <!-- Files: tests/benchmarks/generate_report.py -->
