## MODIFIED Requirements

### Requirement: Dry-run endpoint previews remediation impact
The API SHALL expose `POST /api/ontology/remediation/dry-run` that returns a preview of what batch remediation would change, including per-query entity counts and total entities that would be updated, without modifying any data. Additionally, the dry-run SHALL report any remediation query that returns zero matches as a "no-op query" so operators can identify queries that may have become stale or misconfigured.

#### Scenario: Dry-run returns preview counts
- **WHEN** a POST request is made to `/api/ontology/remediation/dry-run`
- **THEN** the response SHALL include `pre_stats` (total, knowledge, mapped counts), `unmapped_types` (top types by count), `remediation_preview` (per-query counts), and `total_would_update`

#### Scenario: Dry-run does not modify data
- **WHEN** a dry-run is executed
- **THEN** no entity properties SHALL be modified in Neo4j

#### Scenario: No-op queries are identified in dry-run
- **WHEN** a dry-run runs and a remediation query matches zero entities
- **THEN** that query SHALL be flagged as a "no-op query" in the response with its query name and the reason it matched nothing

### Requirement: Rollback endpoint reverts a batch
The API SHALL expose `POST /api/ontology/remediation/rollback/{batch_id}` that removes all `_ontology_mapped`, `_canonical_type`, `_remediation_date`, and `_remediation_batch` properties from entities that were updated in the specified batch. The rollback SHALL also produce a verification report confirming that all properties were successfully removed.

#### Scenario: Successful rollback
- **WHEN** a POST request is made to `/api/ontology/remediation/rollback/20260212_153000`
- **THEN** the response SHALL include the count of rolled-back entities and all remediation properties SHALL be removed from those entities

#### Scenario: Rollback of nonexistent batch
- **WHEN** a rollback is requested for a batch_id that doesn't match any entities
- **THEN** the response SHALL return successfully with `rolled_back: 0`

#### Scenario: Rollback verification report is included
- **WHEN** a rollback completes
- **THEN** the response SHALL include a verification section confirming zero entities remain with the rolled-back `_remediation_batch` value

## ADDED Requirements

### Requirement: Remediation query coverage audit
The audit SHALL compare the set of entity types present in the graph against the set of types covered by REMEDIATION_QUERIES. Types present in the graph but not matched by any remediation query SHALL be reported as remediation gaps.

#### Scenario: Uncovered graph type is identified
- **WHEN** the graph contains entities with `type = "Biomarker"` but no remediation query matches this type
- **THEN** the audit SHALL report `"Biomarker"` as a remediation coverage gap

#### Scenario: Covered type is confirmed
- **WHEN** the graph contains entities with `type = "Disease"` and the `disease_mapping` query covers it
- **THEN** the audit SHALL confirm coverage

### Requirement: Rollback scenario completeness assessment
The audit SHALL verify that rollback correctly handles: partial batch execution (some queries succeeded, some failed), batches with consistency normalization fixes (`_consistency_fixed` property), batches that flagged unknown types (`_needs_review`, `_review_reason`), and batches that classified orphan sources (`_orphan_source`). Each scenario SHALL be assessed as tested or untested.

#### Scenario: Partial batch rollback is assessed
- **WHEN** the audit checks rollback handling for partial batch execution
- **THEN** it SHALL report whether the rollback correctly removes only properties from the specified batch without affecting other batches

#### Scenario: Consistency fix rollback is assessed
- **WHEN** the audit checks rollback handling for `_consistency_fixed` properties
- **THEN** it SHALL report whether rollback removes `_consistency_fixed` alongside other remediation properties

### Requirement: Remediation idempotency verification
The audit SHALL verify that running remediation execute twice on the same graph produces identical results — no entities are double-mapped, no counters are inflated, and no properties are overwritten with different values.

#### Scenario: Double execution produces same results
- **WHEN** the audit compares results from two consecutive remediation executions
- **THEN** the second execution SHALL report zero new entities mapped (all already mapped)

#### Scenario: Property values are stable across runs
- **WHEN** remediation runs on already-remediated entities
- **THEN** `_canonical_type`, `_ontology_mapped`, and `layer` values SHALL remain unchanged
