## Context

SynapseFlow ingests documents (primarily medical PDFs) through a multi-step pipeline:

1. **MarkItDown** converts PDF → Markdown (`MarkItDownWrapper.convert_to_markdown()`)
2. Markdown is cleaned and chunked (`TextChunker`, regex normalization)
3. An LLM-based `EntityExtractor` pulls entities and relationships from chunks
4. Results are stored in Neo4j/FalkorDB at the PERCEPTION layer with confidence ~0.7

This pipeline is implemented across four services: `DocumentService`, `SimplePDFIngestionService`, `PDFKnowledgeIngestionService`, and `Neo4jPDFIngestionService` — all using MarkItDown directly or via `MarkItDownWrapper`.

**LangExtract** (Google) takes a fundamentally different approach: it uses LLMs to extract structured entities directly from text with source grounding. It could collapse steps 1-3 into a single extraction pass, and its source-grounding feature maps every extraction back to its exact position in the source text — something the current pipeline lacks entirely.

## Goals / Non-Goals

**Goals:**
- Produce a working LangExtract adapter that follows the same interface pattern as existing ingestion services
- Run a controlled benchmark comparing extraction quality (entity recall, relationship accuracy, source grounding) between MarkItDown+LLM and LangExtract on the same medical PDFs
- Identify concrete integration gaps: DIKW layer mapping, schema compatibility, confidence scoring differences
- Deliver a structured comparison report with actionable recommendations

**Non-Goals:**
- Replacing MarkItDown in production (this is assessment-only)
- Supporting all LangExtract features (Vertex AI batch, visualization HTML generation)
- Benchmarking performance at production scale (we test on a representative sample)
- Modifying any existing ingestion service code

## Decisions

### D1: LangExtract as a parallel adapter, not a MarkItDown replacement

LangExtract will be implemented as a new `LangExtractIngestionService` alongside existing services. It will NOT replace `MarkItDownWrapper` or modify any existing service. This isolates the assessment and avoids risk to the production pipeline.

*Alternative considered*: Swapping MarkItDown inside `DocumentService`. Rejected because it couples assessment risk to production code and makes A/B comparison harder.

### D2: Use Gemini 2.5 Flash as the default LangExtract model

LangExtract's structured output (schema constraints) works best with Gemini models. Flash balances cost and quality for assessment purposes. OpenAI support exists but lacks structured output enforcement.

*Alternative considered*: Using OpenAI GPT-4o (already in stack). Rejected because `use_schema_constraints=False` is required for OpenAI, losing LangExtract's key structured output advantage.

### D3: Pre-convert PDFs to text before LangExtract processing

LangExtract operates on text input, not raw PDFs. We'll use MarkItDown to get text from PDFs first, then feed that text into LangExtract. This means the benchmark compares: *MarkItDown → LLM extraction* vs *MarkItDown → LangExtract extraction* — isolating the extraction quality difference.

*Alternative considered*: Using a separate PDF-to-text tool for LangExtract input. Rejected because it introduces a confounding variable (different text from different converters).

### D4: Map LangExtract extractions to ExtractionResult dataclass

LangExtract outputs `Extraction` objects with `extraction_class`, `extraction_text`, and `attributes`. These will be mapped to the existing `ExtractionResult` dataclass pattern (entities list + relationships list) used by all ingestion services. Confidence will be derived from LangExtract's extraction metadata.

### D5: Benchmark on 3-5 representative medical PDFs from the existing corpus

Use documents already in `markdown_output/` that have been through the current pipeline. This gives us ground truth for comparison. Include varying sizes and complexity levels.

## Risks / Trade-offs

- **[API key dependency]** → LangExtract needs a Gemini API key. Mitigation: make it configurable, document setup, support OpenAI fallback.
- **[Cost of LLM calls]** → LangExtract uses LLM calls per chunk. Multi-pass extraction (`extraction_passes=3`) multiplies cost. Mitigation: start with single-pass, increase only if recall is low.
- **[Source grounding mapping]** → LangExtract's character-offset grounding doesn't map directly to SynapseFlow's chunk-based system. Mitigation: store grounding metadata as supplementary data, not as a replacement for chunk references.
- **[Schema mismatch]** → LangExtract entity types (arbitrary `extraction_class`) don't match SynapseFlow's fixed entity taxonomy (Disease, Treatment, Symptom, etc.). Mitigation: define extraction examples that match our taxonomy.

## Parallelism Considerations

The three capabilities are naturally independent:

1. **langextract-adapter** — New service file + tests. Touches `src/application/services/` only. No shared state with other capabilities.
2. **extraction-benchmark** — Benchmark harness in `tests/benchmarks/`. Depends on the adapter being importable, but can be scaffolded in parallel using a mock.
3. **extraction-comparison-report** — Report template and scoring logic. Pure data analysis, no code dependencies on the other two.

**Shared interface contract** (must be defined before parallel work):
- `LangExtractIngestionService` must produce `ExtractionResult`-compatible output (entities list + relationships list)
- Benchmark harness expects both MarkItDown and LangExtract services to accept a file path and return structured extraction results

**Serialization point**: The benchmark cannot produce real results until the adapter works. But the harness structure, scoring rubric, and report template can all be built independently.

## Open Questions

- Should we evaluate LangExtract's multi-pass extraction (`extraction_passes > 1`) or keep it single-pass for fair comparison?
- What minimum entity recall improvement would justify a migration effort?
- Should the benchmark include non-medical documents (DDAs) to test generalizability?
