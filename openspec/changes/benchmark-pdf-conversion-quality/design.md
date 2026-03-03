## Context

SynapseFlow uses `MarkItDownWrapper` to convert PDFs to Markdown before entity extraction. The current output has significant readability issues on structured medical documents: tables flatten, bullet hierarchies break, page artifacts leak in, and special characters garble. Since the entire extraction pipeline (chunking → LLM entity extraction → KG storage) depends on markdown quality, poor conversion directly degrades downstream results.

Several open-source alternatives exist with better layout preservation:
- **Docling** (IBM): ML-based document understanding with table detection, OCR, and structured output
- **pymupdf4llm** (PyMuPDF): Fast PDF→Markdown with good structure preservation
- **Marker**: ML-based PDF→Markdown with table and heading detection

## Goals / Non-Goals

**Goals:**
- Build adapter wrappers for 3 alternative converters following the same interface as `MarkItDownWrapper`
- Create a benchmark harness that runs all converters on the same PDFs and scores readability
- Produce a structured comparison report with actionable recommendations
- Evaluate on the existing medical PDF corpus (documents already in `markdown_output/`)

**Non-Goals:**
- Replacing MarkItDown in production (assessment only)
- OCR evaluation (assuming text-based PDFs)
- Evaluating cloud-based conversion services (Azure Document Intelligence, Google Document AI)
- Benchmarking extraction quality (already covered by `assess-langextract-vs-markitdown` change)

## Decisions

### D1: Common `PDFConverter` protocol for all adapters

All converters will implement a simple protocol: `convert_to_markdown(file_path: str) -> Optional[str]`. This matches `MarkItDownWrapper`'s existing interface exactly, making it trivial to swap converters in the pipeline.

*Alternative considered*: Returning structured output (sections, tables as objects). Rejected because the downstream pipeline expects raw markdown text.

### D2: Automated quality scoring via heuristics + LLM

Quality will be scored across 5 dimensions using a mix of regex heuristics and LLM-based evaluation:
1. **Table preservation** (heuristic): detect markdown table syntax (`|---|`) vs flattened text
2. **Heading structure** (heuristic): count proper `#` headings vs ALL-CAPS or unstyled headings
3. **Bullet formatting** (heuristic): detect proper `-`/`*`/`1.` bullets vs garbled characters (`Ì`)
4. **Page artifact removal** (heuristic): detect leaked footers, page numbers, headers
5. **Content completeness** (heuristic): character count ratio vs original, missing sections

*Alternative considered*: Pure LLM evaluation for all dimensions. Rejected because heuristic scoring is deterministic, fast, and doesn't require API calls for every document.

### D3: Benchmark on 5 representative medical PDFs

Select documents with varying structure complexity:
- Simple text-heavy document (e.g., patient guide)
- Table-heavy document (e.g., drug reference)
- Mixed layout with figures and callouts
- Multi-column academic paper
- Long document (100+ pages)

### D4: Docling, pymupdf4llm, and Marker as the three challengers

These three represent different approaches:
- **Docling**: ML document understanding (highest accuracy potential, slowest)
- **pymupdf4llm**: Native PDF parsing (fastest, no ML overhead)
- **Marker**: ML-based conversion (balance of speed and quality)

Unstructured was considered but has heavier infrastructure requirements and overlaps with Docling's approach.

## Risks / Trade-offs

- **[Large dependencies]** → Docling and Marker pull in ML model weights (potentially GB+). Mitigation: make all converters optional extras, document size impact.
- **[Scoring subjectivity]** → Automated heuristics may not capture all readability issues. Mitigation: save raw outputs for manual side-by-side review.
- **[Version sensitivity]** → Converter quality changes across versions. Mitigation: log exact package versions in benchmark results.
- **[PDF variability]** → Results may not generalize across all document types. Mitigation: test on 5 diverse documents from the corpus.

## Open Questions

- Should we include a human evaluation step (e.g., rate outputs 1-5) in addition to automated scoring?
- What weight should each quality dimension have in the overall score?
