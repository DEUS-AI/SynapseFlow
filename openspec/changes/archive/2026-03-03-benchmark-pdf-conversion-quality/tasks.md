## 1. Setup & Dependencies

- [x] 1.1 Add docling, pymupdf4llm, and marker-pdf as optional dependencies in pyproject.toml
- [x] 1.2 Create benchmark conversion output directories (tests/benchmarks/results/conversion/)

## 2. PDF Converter Adapters

- [x] 2.1 Create DoclingWrapper in src/application/services/docling_wrapper.py with convert_to_markdown() and DOCLING_AVAILABLE flag
- [x] 2.2 Create PyMuPDF4LLMWrapper in src/application/services/pymupdf4llm_wrapper.py with convert_to_markdown() and PYMUPDF4LLM_AVAILABLE flag
- [x] 2.3 Create MarkerWrapper in src/application/services/marker_wrapper.py with convert_to_markdown() and MARKER_AVAILABLE flag
- [x] 2.4 Write unit tests for all three adapters (initialization, conversion, graceful degradation)

## 3. Quality Scoring Engine

- [x] 3.1 Implement table preservation scorer (detect markdown pipe tables vs flattened text)
- [x] 3.2 Implement heading structure scorer (count proper # headings vs ALL-CAPS)
- [x] 3.3 Implement bullet formatting scorer (proper list markers vs garbled characters)
- [x] 3.4 Implement page artifact removal scorer (detect leaked footers, page numbers, headers)
- [x] 3.5 Implement content completeness scorer (character count ratio, section detection)
- [x] 3.6 Implement weighted average aggregation across all 5 dimensions

## 4. Benchmark Harness

- [x] 4.1 Create benchmark_conversion.py with runner that accepts a file/directory and runs all available converters
- [x] 4.2 Implement per-converter metrics collection (conversion time, output size, quality scores)
- [x] 4.3 Save raw markdown outputs to tests/benchmarks/results/conversion/<doc>/<converter>.md
- [x] 4.4 Implement JSON results output with all metrics and scores
- [x] 4.5 Add CLI entry point and pytest benchmark test

## 5. Comparison Report

- [x] 5.1 Create generate_conversion_report.py that reads benchmark JSON and produces Markdown report
- [x] 5.2 Implement summary table with per-converter scores across all dimensions
- [x] 5.3 Implement recommendation logic based on weighted scores and trade-offs
