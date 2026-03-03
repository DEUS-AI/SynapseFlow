## Why

MarkItDown's PDF→Markdown conversion produces poor readability for structured medical documents: tables flatten into disconnected lines, bullet hierarchies break, page footers leak into content, and special characters garble. Since SynapseFlow's entire extraction pipeline depends on markdown quality, poor conversion directly degrades entity and relationship extraction. We need to benchmark alternative PDF converters (Docling, pymupdf4llm, Unstructured, Marker) to find the best fit for our medical document corpus.

## What Changes

- Add Docling, pymupdf4llm, and Marker as optional dependencies for evaluation
- Create a conversion quality benchmark harness that runs multiple converters on the same PDF and scores readability
- Implement a scoring rubric covering table preservation, heading structure, bullet formatting, content accuracy, and artifact removal
- Build a side-by-side comparison viewer for manual inspection of converter outputs
- Produce a structured recommendation report

## Capabilities

### New Capabilities
- `pdf-converter-adapters`: Thin adapter wrappers for each PDF converter (Docling, pymupdf4llm, Marker) following the same interface as MarkItDownWrapper
- `conversion-quality-benchmark`: Harness that runs all converters on the same documents and collects quality metrics (table preservation, heading structure, bullet formatting, page artifact removal, character accuracy)
- `conversion-quality-report`: Scoring rubric and report generator for comparing converter outputs and producing an actionable recommendation

### Modified Capabilities

_(none — assessment only, no existing specs change)_

## Impact

- **Dependencies**: New optional deps: `docling`, `pymupdf4llm`, `marker-pdf` in pyproject.toml
- **Code**: New adapter wrappers in `src/application/services/`, benchmark harness in `tests/benchmarks/`
- **Existing pipeline**: No changes — MarkItDownWrapper remains the production converter
- **Documents**: Benchmark uses existing medical PDFs from `markdown_output/` corpus for ground truth comparison
