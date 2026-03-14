## ADDED Requirements

### Requirement: Comparison report template
The system SHALL provide a Markdown report template at `tests/benchmarks/report_template.md` that structures the comparison findings across multiple evaluation dimensions.

**Primary files**: `tests/benchmarks/report_template.md`, `tests/benchmarks/generate_report.py`

#### Scenario: Report generated from benchmark results
- **WHEN** `generate_report.py` is run with a path to a benchmark results JSON file
- **THEN** it SHALL produce a Markdown report with sections: Executive Summary, Entity Extraction Quality, Relationship Extraction Quality, Source Grounding Analysis, Performance & Cost, Integration Assessment, and Recommendation

### Requirement: Scoring rubric
The report generator SHALL score each pipeline across these dimensions on a 1-5 scale:
- **Entity Recall**: How many relevant entities were found
- **Entity Precision**: How many extracted entities are actually correct/relevant
- **Relationship Accuracy**: Correctness of extracted relationships
- **Source Grounding**: Quality of provenance linking (LangExtract advantage)
- **Processing Speed**: Time to extract per document
- **Cost Efficiency**: Estimated API cost per document
- **Integration Effort**: How much work to integrate into SynapseFlow's pipeline

#### Scenario: Scoring output
- **WHEN** the report is generated
- **THEN** each dimension SHALL have a numeric score (1-5), a brief justification, and a comparison note indicating which pipeline scored better

### Requirement: Integration gap analysis
The report SHALL include a dedicated section analyzing integration challenges for adopting LangExtract, covering: dependency additions, API key management, schema mapping complexity, DIKW layer compatibility, and impact on existing tests.

#### Scenario: Gap analysis content
- **WHEN** the integration assessment section is generated
- **THEN** it SHALL list each integration gap with severity (low/medium/high), estimated effort, and a proposed mitigation approach

### Requirement: Actionable recommendation
The report SHALL conclude with a clear recommendation: adopt LangExtract, stay with MarkItDown, or pursue a hybrid approach. The recommendation SHALL be justified by the scoring results and integration analysis.

#### Scenario: Recommendation with justification
- **WHEN** the report is generated
- **THEN** the Recommendation section SHALL state one of: "ADOPT", "STAY", or "HYBRID", followed by 2-3 bullet points justifying the choice based on benchmark data
