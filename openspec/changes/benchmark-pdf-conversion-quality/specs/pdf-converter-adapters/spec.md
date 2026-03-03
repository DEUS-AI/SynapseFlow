## ADDED Requirements

### Requirement: Common PDF converter interface
All PDF converter adapters SHALL implement a `convert_to_markdown(file_path: str) -> Optional[str]` method matching the existing `MarkItDownWrapper` interface. Each adapter SHALL be in a separate file under `src/application/services/`.

#### Scenario: Consistent interface across converters
- **WHEN** any converter adapter receives a valid PDF file path
- **THEN** it SHALL return a markdown string or None on failure, matching `MarkItDownWrapper`'s contract

### Requirement: Docling adapter
The system SHALL provide a `DoclingWrapper` class in `src/application/services/docling_wrapper.py` that uses IBM's Docling library for PDF→Markdown conversion with table detection and structured output.

#### Scenario: Docling converts a PDF with tables
- **WHEN** `DoclingWrapper.convert_to_markdown()` receives a PDF containing tables
- **THEN** it SHALL return markdown with tables formatted using pipe syntax (`| col | col |`)

#### Scenario: Docling unavailable
- **WHEN** the `docling` package is not installed
- **THEN** the module SHALL set `DOCLING_AVAILABLE = False` and raise `ImportError` on instantiation

### Requirement: pymupdf4llm adapter
The system SHALL provide a `PyMuPDF4LLMWrapper` class in `src/application/services/pymupdf4llm_wrapper.py` that uses pymupdf4llm for fast PDF→Markdown conversion.

#### Scenario: pymupdf4llm converts a PDF
- **WHEN** `PyMuPDF4LLMWrapper.convert_to_markdown()` receives a valid PDF file path
- **THEN** it SHALL return markdown text preserving headings, bullets, and basic structure

#### Scenario: pymupdf4llm unavailable
- **WHEN** the `pymupdf4llm` package is not installed
- **THEN** the module SHALL set `PYMUPDF4LLM_AVAILABLE = False` and raise `ImportError` on instantiation

### Requirement: Marker adapter
The system SHALL provide a `MarkerWrapper` class in `src/application/services/marker_wrapper.py` that uses the Marker library for ML-based PDF→Markdown conversion.

#### Scenario: Marker converts a PDF with mixed layout
- **WHEN** `MarkerWrapper.convert_to_markdown()` receives a PDF with mixed text, tables, and headings
- **THEN** it SHALL return markdown with detected headings using `#` syntax and tables using pipe syntax

#### Scenario: Marker unavailable
- **WHEN** the `marker-pdf` package is not installed
- **THEN** the module SHALL set `MARKER_AVAILABLE = False` and raise `ImportError` on instantiation
