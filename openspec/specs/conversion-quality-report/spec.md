## ADDED Requirements

### Requirement: Conversion quality report generator
The system SHALL provide a report generator at `tests/benchmarks/generate_conversion_report.py` that reads benchmark JSON results and produces a Markdown comparison report.

#### Scenario: Report generated from benchmark results
- **WHEN** the report generator is run with a benchmark results JSON path
- **THEN** it SHALL produce a Markdown report with sections: Executive Summary, Per-Converter Scores, Quality Dimension Analysis, Performance Comparison, and Recommendation

### Requirement: Scoring summary table
The report SHALL include a summary table showing each converter's score across all 5 quality dimensions plus weighted average.

#### Scenario: Summary table content
- **WHEN** the report is generated
- **THEN** it SHALL include a markdown table with columns: Converter, Table Preservation, Heading Structure, Bullet Formatting, Artifact Removal, Content Completeness, Weighted Average

### Requirement: Actionable recommendation
The report SHALL conclude with a recommendation: which converter to adopt, or whether to stay with MarkItDown.

#### Scenario: Recommendation with justification
- **WHEN** the report is generated
- **THEN** the Recommendation section SHALL state the recommended converter and provide 2-3 bullet points justifying the choice based on benchmark scores and trade-offs (quality vs speed vs dependency size)
