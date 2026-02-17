## MODIFIED Requirements

### Requirement: Execute endpoint runs batch remediation
The API SHALL expose `POST /api/ontology/remediation/execute` that runs the full batch remediation pipeline (mark structural, mark noise, type mapping queries) and returns results including a `batch_id` for rollback. The structural marking step SHALL include ConversationSession and Message labels alongside Chunk, Document, and ExtractedEntity. The pipeline SHALL NOT include a conversation-to-usage ontology mapping query.

#### Scenario: Successful execution returns batch results
- **WHEN** a POST request is made to `/api/ontology/remediation/execute`
- **THEN** the response SHALL include `batch_id`, per-step results with counts, `total_updated`, and `coverage_before`/`coverage_after` percentages

#### Scenario: Execution accepts options
- **WHEN** the request body includes `{"mark_structural": false, "mark_noise": false}`
- **THEN** the remediation SHALL skip the structural and noise marking steps

#### Scenario: Structural marking includes conversation nodes
- **WHEN** the structural marking step executes during remediation
- **THEN** ConversationSession and Message nodes SHALL be marked with `_is_structural=true` and `_exclude_from_ontology=true`

#### Scenario: No conversation-to-usage mapping exists
- **WHEN** the remediation query list is inspected
- **THEN** there SHALL be no query that sets `_canonical_type='usage'` on ConversationSession or Message nodes
