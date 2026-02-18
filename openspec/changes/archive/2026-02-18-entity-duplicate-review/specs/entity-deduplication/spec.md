## MODIFIED Requirements

### Requirement: Batch duplicate detection by exact case-insensitive match
The deduplication service SHALL query all entities from Neo4j grouped by type, and identify pairs where entity names match case-insensitively within the same type. Each pair SHALL include both entity IDs, names, types, relationship counts, and confidence scores. The detection query SHALL exclude entities with `_dedup_skip = true` in addition to those with `_merged_into` set or `_is_structural = true`.

#### Scenario: Case-insensitive duplicates are detected
- **WHEN** entities with `name = "Aspirin"` and `name = "aspirin"` of type `drug` exist
- **THEN** the service SHALL report them as a duplicate pair

#### Scenario: Different-type entities are not duplicates
- **WHEN** entities with `name = "Mercury"` exist as both type `chemical` and type `planet`
- **THEN** the service SHALL NOT report them as duplicates

#### Scenario: Already-merged entities are excluded
- **WHEN** an entity has `_merged_into` set
- **THEN** the service SHALL exclude it from duplicate detection

#### Scenario: Dismissed entities are excluded
- **WHEN** an entity has `_dedup_skip = true`
- **THEN** the service SHALL exclude it from duplicate detection

### Requirement: Deduplication dry-run endpoint
The API SHALL expose `POST /api/ontology/remediation/deduplication/dry-run` that returns a merge plan without modifying any data. The plan SHALL list each duplicate pair with the proposed winner (entity to keep) and loser (entity to merge), along with the merge rationale. The response SHALL be categorized into `same_type` and `cross_type` sections per the duplicate-review-workflow spec.

#### Scenario: Dry-run returns merge plan
- **WHEN** a POST request is made to `/api/ontology/remediation/deduplication/dry-run`
- **THEN** the response SHALL include `total_same_type`, `same_type_plan` (list of pairs with winner/loser/rationale), `total_cross_type`, and `cross_type_groups`, and no data SHALL be modified

#### Scenario: Winner selection prefers more relationships
- **WHEN** a duplicate pair has entity A with 5 relationships and entity B with 2 relationships
- **THEN** the merge plan SHALL select entity A as the winner

#### Scenario: Winner selection breaks ties by confidence
- **WHEN** a duplicate pair has equal relationship counts but entity A has `confidence = 0.95` and entity B has `confidence = 0.80`
- **THEN** the merge plan SHALL select entity A as the winner

### Requirement: Deduplication execute endpoint
The API SHALL expose `POST /api/ontology/remediation/deduplication/execute` that executes the merge plan for same-type duplicates only. For each pair, it SHALL transfer all relationships from the loser to the winner, copy any unique properties, mark the loser with `_merged_into=<winner_id>` and `_merged_date`, and then delete the loser node. The response SHALL include `skipped_cross_type` indicating how many cross-type groups were not merged.

#### Scenario: Relationships are transferred
- **WHEN** deduplication merges entity B into entity A
- **THEN** all relationships previously connected to entity B SHALL be reconnected to entity A

#### Scenario: Merged entity is marked before deletion
- **WHEN** entity B is merged into entity A
- **THEN** entity B SHALL have `_merged_into=<entity_A_id>` and `_merged_date` set before deletion

#### Scenario: Execute returns summary
- **WHEN** a POST request is made to `/api/ontology/remediation/deduplication/execute`
- **THEN** the response SHALL include `total_merged`, `total_relationships_transferred`, `batch_id`, and `skipped_cross_type`

#### Scenario: Duplicate relationships are not created
- **WHEN** both the winner and loser have a relationship of the same type to the same target
- **THEN** the merge SHALL keep only one relationship (the winner's) and discard the duplicate
