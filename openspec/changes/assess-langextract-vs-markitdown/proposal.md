## Why

SynapseFlow's document ingestion pipeline currently uses MarkItDown for PDF→Markdown conversion, followed by separate LLM-based entity extraction. Google's LangExtract offers a fundamentally different approach: LLM-driven structured extraction with source grounding, potentially replacing both the conversion and extraction steps in a single pass. We need to assess whether LangExtract produces better extraction quality, preserves source provenance, and integrates cleanly with our DIKW-layered knowledge graph — before committing to a migration.

## What Changes

- Add LangExtract as an optional dependency alongside MarkItDown
- Create a benchmarking harness that runs both tools against the same document corpus
- Implement a LangExtract-based ingestion adapter following the existing service pattern
- Produce a comparison report covering extraction quality, source grounding, performance, and cost
- Identify integration gaps (schema mapping, DIKW layer assignment, chunking differences)

## Capabilities

### New Capabilities
- `langextract-adapter`: LangExtract integration adapter implementing the document ingestion interface, with entity/relationship extraction and DIKW layer mapping
- `extraction-benchmark`: Side-by-side benchmarking harness comparing MarkItDown+LLM extraction vs LangExtract extraction on the same document set, measuring quality, coverage, and performance
- `extraction-comparison-report`: Structured report template and scoring rubric for evaluating extraction results across dimensions (entity recall, relationship accuracy, source grounding, cost)

### Modified Capabilities

_(none — this is an assessment; no existing spec-level requirements change)_

## Impact

- **Dependencies**: New optional dependency `langextract` in `pyproject.toml`
- **Code**: New adapter service in `src/application/services/`, new benchmark scripts in `tests/benchmarks/`
- **Infrastructure**: LangExtract requires a Gemini or OpenAI API key; Gemini recommended for structured output support
- **Existing pipeline**: No changes to existing MarkItDown pipeline — assessment runs in parallel
- **Agents affected**: None directly — this is an evaluation-only change with no production behavior modifications
