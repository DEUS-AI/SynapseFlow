## ADDED Requirements

### Requirement: Dry-run endpoint previews remediation impact
The API SHALL expose `POST /api/ontology/remediation/dry-run` that returns a preview of what batch remediation would change, including per-query entity counts and total entities that would be updated, without modifying any data.

#### Scenario: Dry-run returns preview counts
- **WHEN** a POST request is made to `/api/ontology/remediation/dry-run`
- **THEN** the response SHALL include `pre_stats` (total, knowledge, mapped counts), `unmapped_types` (top types by count), `remediation_preview` (per-query counts), and `total_would_update`

#### Scenario: Dry-run does not modify data
- **WHEN** a dry-run is executed
- **THEN** no entity properties SHALL be modified in Neo4j

### Requirement: Execute endpoint runs batch remediation
The API SHALL expose `POST /api/ontology/remediation/execute` that runs the full batch remediation pipeline (mark structural, mark noise, type mapping queries) and returns results including a `batch_id` for rollback.

#### Scenario: Successful execution returns batch results
- **WHEN** a POST request is made to `/api/ontology/remediation/execute`
- **THEN** the response SHALL include `batch_id`, per-step results with counts, `total_updated`, and `coverage_before`/`coverage_after` percentages

#### Scenario: Execution accepts options
- **WHEN** the request body includes `{"mark_structural": false, "mark_noise": false}`
- **THEN** the remediation SHALL skip the structural and noise marking steps

### Requirement: Rollback endpoint reverts a batch
The API SHALL expose `POST /api/ontology/remediation/rollback/{batch_id}` that removes all `_ontology_mapped`, `_canonical_type`, `_remediation_date`, and `_remediation_batch` properties from entities that were updated in the specified batch.

#### Scenario: Successful rollback
- **WHEN** a POST request is made to `/api/ontology/remediation/rollback/20260212_153000`
- **THEN** the response SHALL include the count of rolled-back entities and all remediation properties SHALL be removed from those entities

#### Scenario: Rollback of nonexistent batch
- **WHEN** a rollback is requested for a batch_id that doesn't match any entities
- **THEN** the response SHALL return successfully with `rolled_back: 0`

### Requirement: Remediation logic is extracted into a reusable service
The remediation logic (queries, dry-run, execute, rollback) SHALL be encapsulated in a `RemediationService` class in `src/application/services/` that accepts a Neo4j backend dependency. Both the API endpoints and the CLI script SHALL use this service.

#### Scenario: CLI script uses RemediationService
- **WHEN** the CLI script `scripts/ontology_batch_remediation.py` runs with `--execute`
- **THEN** it SHALL delegate to `RemediationService` rather than running Cypher queries directly

#### Scenario: API endpoint uses RemediationService
- **WHEN** the API endpoint `/api/ontology/remediation/execute` is called
- **THEN** it SHALL delegate to the same `RemediationService` instance

### Requirement: Orphan node listing endpoint
The API SHALL expose `GET /api/ontology/orphans` that returns entities flagged with `_is_orphan=true`, including their name, type, labels, and properties.

#### Scenario: Orphans are listed after remediation
- **WHEN** a GET request is made to `/api/ontology/orphans` after remediation has flagged orphan nodes
- **THEN** the response SHALL include a list of orphan entities with their metadata
