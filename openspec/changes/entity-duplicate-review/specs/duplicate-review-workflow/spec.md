## ADDED Requirements

### Requirement: Cross-type duplicate detection via normalizer
The deduplication service SHALL provide a `detect_cross_type_duplicates()` method that uses `SemanticNormalizer.normalize()` to compute canonical forms for all entity names, then groups entities by canonical form across types. Groups where entities span multiple `type` values SHALL be reported as cross-type duplicates. Each group SHALL include the canonical form, the list of entity IDs/names/types, and the count of entities.

#### Scenario: Cross-type duplicates are detected
- **WHEN** entities with `name = "corticosteroids"` exist as both `type = "Drug"` and `type = "Treatment"`
- **THEN** the service SHALL report them as a cross-type duplicate group with canonical form `"corticosteroids"`

#### Scenario: Same-type normalizer matches are excluded from cross-type results
- **WHEN** entities with `name = "Aspirin"` and `name = "aspirin"` both have `type = "Drug"`
- **THEN** the cross-type detection SHALL NOT include them (they are same-type duplicates handled by the existing detection)

#### Scenario: Normalizer-only matches are detected
- **WHEN** entities with `name = "Cust"` and `name = "Customer"` exist
- **THEN** the service SHALL report them as duplicates because both normalize to the same canonical form

### Requirement: Categorized dry-run response
The `POST /api/ontology/remediation/deduplication/dry-run` endpoint SHALL return a categorized response with `same_type` pairs (auto-mergeable) and `cross_type` groups (review-only). The response SHALL include `total_same_type`, `total_cross_type`, `same_type_plan` (list of merge plans), and `cross_type_groups` (list of grouped entities).

#### Scenario: Dry-run returns both categories
- **WHEN** the graph contains both same-type and cross-type duplicates
- **THEN** the dry-run response SHALL include both `same_type_plan` and `cross_type_groups` sections with their respective counts

#### Scenario: Cross-type groups include entity details
- **WHEN** a cross-type group contains entities of types Drug and Treatment
- **THEN** the `cross_type_groups` entry SHALL include `canonical_form`, `entities` (list with id, name, type, relationship_count), and `entity_count`

#### Scenario: Empty graph returns zero counts
- **WHEN** no duplicate entities exist
- **THEN** the dry-run SHALL return `total_same_type: 0` and `total_cross_type: 0` with empty plan lists

### Requirement: False-positive dismissal endpoint
The API SHALL expose `POST /api/ontology/remediation/deduplication/dismiss` that accepts `{ "entity_ids": ["id1", "id2", ...] }` and sets `_dedup_skip = true` on each specified entity. Dismissed entities SHALL be excluded from all future duplicate detection (both same-type and cross-type).

#### Scenario: Entities are marked as dismissed
- **WHEN** a POST request is made to `/dismiss` with `entity_ids = ["e1", "e2"]`
- **THEN** both entities SHALL have `_dedup_skip = true` set in the graph

#### Scenario: Dismissed entities are excluded from same-type detection
- **WHEN** entity A has `_dedup_skip = true` and entity B has the same name and type
- **THEN** the same-type detection SHALL NOT report them as a duplicate pair

#### Scenario: Dismissed entities are excluded from cross-type detection
- **WHEN** entity A has `_dedup_skip = true` and entity B has the same canonical name but different type
- **THEN** the cross-type detection SHALL NOT include entity A in the duplicate group

#### Scenario: Dismissal can be undone
- **WHEN** a POST request is made to `/dismiss` with `entity_ids = ["e1"]` and `undo = true`
- **THEN** entity e1 SHALL have `_dedup_skip` removed

### Requirement: Execute excludes cross-type duplicates
The `POST /api/ontology/remediation/deduplication/execute` endpoint SHALL only merge same-type duplicate pairs. Cross-type duplicate groups SHALL NOT be auto-merged. The response SHALL include a `skipped_cross_type` count indicating how many cross-type groups were detected but not merged.

#### Scenario: Only same-type pairs are merged
- **WHEN** the graph contains 10 same-type pairs and 3 cross-type groups
- **THEN** execute SHALL merge only the 10 same-type pairs and return `skipped_cross_type: 3`

#### Scenario: Cross-type entities are unmodified after execute
- **WHEN** a cross-type group with "corticosteroids" (Drug + Treatment) exists and execute runs
- **THEN** both entities SHALL remain in the graph with no modifications

### Requirement: Assessment excludes dismissed and merged entities from duplicate count
The quality assessment's `_assess_normalization` method SHALL skip entities with `_dedup_skip = true` or `_merged_into` set when computing the `potential_duplicates` list and `deduplication_candidates` count. This ensures the recommendation count reflects only actionable duplicates.

#### Scenario: Dismissed entities are excluded from assessment duplicate count
- **WHEN** 5 duplicate groups exist but 2 groups consist entirely of dismissed entities
- **THEN** the assessment SHALL report `deduplication_candidates = 3`

#### Scenario: Entities with _merged_into are excluded
- **WHEN** an entity has `_merged_into` set (surviving a partial merge)
- **THEN** the assessment SHALL exclude it from duplicate detection

#### Scenario: Assessment count matches dedup service count
- **WHEN** no entities have `_dedup_skip` or `_merged_into` set
- **THEN** the assessment's `deduplication_candidates` SHALL equal the sum of same-type pairs and cross-type groups from the dedup service

### Requirement: Remediation router is mounted and accessible
The remediation router SHALL be mounted in `main.py` at the `/api/ontology/remediation` prefix. The deduplication service SHALL be initialized during application lifespan and injected into the router.

#### Scenario: Dry-run endpoint is reachable
- **WHEN** a POST request is made to `/api/ontology/remediation/deduplication/dry-run`
- **THEN** the server SHALL return a 200 response (not 404)

#### Scenario: Execute endpoint is reachable
- **WHEN** a POST request is made to `/api/ontology/remediation/deduplication/execute`
- **THEN** the server SHALL return a 200 response (not 404)

#### Scenario: Dismiss endpoint is reachable
- **WHEN** a POST request is made to `/api/ontology/remediation/deduplication/dismiss`
- **THEN** the server SHALL return a 200 response (not 404)
