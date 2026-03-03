## ADDED Requirements

### Requirement: Benchmark harness for conversion quality
The system SHALL provide a benchmark harness at `tests/benchmarks/benchmark_conversion.py` that runs all available PDF converters on the same documents and collects quality metrics.

#### Scenario: Run benchmark on a single PDF
- **WHEN** the benchmark is executed with a path to a PDF file
- **THEN** it SHALL run MarkItDown plus all available alternative converters and output a JSON results file with per-converter quality scores

#### Scenario: Run benchmark on a document corpus
- **WHEN** the benchmark is executed with a directory containing PDFs
- **THEN** it SHALL process each PDF through all converters and produce aggregate results

### Requirement: Quality scoring dimensions
The benchmark SHALL score each converter output across 5 dimensions on a 1-5 scale:
- **Table preservation**: Presence of markdown table syntax vs flattened text
- **Heading structure**: Proper `#` headings vs ALL-CAPS or unstyled headings
- **Bullet formatting**: Proper list markers (`-`, `*`, `1.`) vs garbled characters
- **Page artifact removal**: Absence of leaked page footers, headers, and page numbers
- **Content completeness**: Character count ratio relative to the richest output, no missing sections

#### Scenario: Quality scores computed for each converter
- **WHEN** a benchmark run completes for a document
- **THEN** each converter SHALL have a score (1-5) for each of the 5 dimensions plus a weighted average

### Requirement: Side-by-side output preservation
The benchmark SHALL save each converter's raw markdown output to `tests/benchmarks/results/conversion/<document_name>/<converter_name>.md` for manual inspection.

#### Scenario: Raw outputs saved
- **WHEN** a benchmark run completes
- **THEN** raw markdown from each converter SHALL be saved as separate files alongside the JSON results

### Requirement: Converter performance metrics
The benchmark SHALL measure and record conversion time (seconds) and output size (characters) for each converter.

#### Scenario: Performance metrics in results
- **WHEN** a benchmark run completes
- **THEN** the JSON results SHALL include `conversion_time_seconds` and `output_chars` for each converter
