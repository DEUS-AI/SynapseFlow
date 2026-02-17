### Requirement: Dry-run endpoint previews remediation impact
The API SHALL expose `POST /api/ontology/remediation/dry-run` that returns a preview of what batch remediation would change, including per-query entity counts and total entities that would be updated, without modifying any data.

#### Scenario: Dry-run returns preview counts
- **WHEN** a POST request is made to `/api/ontology/remediation/dry-run`
- **THEN** the response SHALL include `pre_stats` (total, knowledge, mapped counts), `unmapped_types` (top types by count), `remediation_preview` (per-query counts), and `total_would_update`

#### Scenario: Dry-run does not modify data
- **WHEN** a dry-run is executed
- **THEN** no entity properties SHALL be modified in Neo4j

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
The API SHALL expose `GET /api/ontology/orphans` that returns entities flagged with `_is_orphan=true`, including their name, type, labels, properties, and `_orphan_source` classification.

#### Scenario: Orphans are listed after remediation
- **WHEN** a GET request is made to `/api/ontology/orphans` after remediation has flagged orphan nodes
- **THEN** the response SHALL include a list of orphan entities with their metadata

#### Scenario: Orphan listing includes source classification
- **WHEN** a GET request is made to `/api/ontology/orphans` after remediation has classified orphans
- **THEN** each orphan entity in the response SHALL include an `orphan_source` field with value `'episodic'`, `'knowledge'`, or `'unclassified'`

### Requirement: Remediation includes food_component type mapping query
`REMEDIATION_QUERIES` SHALL include a `food_component_mapping` query that matches entities with `type IN ['FoodComponent', 'food_component', 'Food Component', 'Nutrient', 'nutrient', 'Vitamin', 'vitamin', 'DietarySubstance']` or labels `['FoodComponent', 'Nutrient']`, and sets `_ontology_mapped=true`, `_canonical_type='food_component'`, `layer=COALESCE(n.layer, 'SEMANTIC')`.

#### Scenario: FoodComponent entities are remediated
- **WHEN** batch remediation runs and entities with type `"FoodComponent"` exist
- **THEN** those entities SHALL have `_ontology_mapped=true` and `_canonical_type="food_component"` set

#### Scenario: Nutrient variant is remediated as food_component
- **WHEN** batch remediation runs and an entity has `type = "Nutrient"`
- **THEN** it SHALL be mapped with `_canonical_type="food_component"`

#### Scenario: Already-mapped food components are skipped
- **WHEN** batch remediation runs and an entity already has `_ontology_mapped=true`
- **THEN** the food_component_mapping query SHALL skip that entity

### Requirement: Remediation includes genus-to-organism mapping
`REMEDIATION_QUERIES` SHALL include a `genus_mapping` query that matches entities with `type IN ['Genus', 'genus']` or labels `['Genus']`, and sets `_ontology_mapped=true`, `_canonical_type='organism'`, `layer=COALESCE(n.layer, 'SEMANTIC')`.

#### Scenario: Genus entities are remediated as organism
- **WHEN** batch remediation runs and entities with type `"Genus"` exist
- **THEN** those entities SHALL have `_ontology_mapped=true` and `_canonical_type="organism"` set

### Requirement: Remediation includes model-organism-to-organism mapping
`REMEDIATION_QUERIES` SHALL include a `model_organism_mapping` query that matches entities with `type IN ['Model Organism', 'model_organism', 'ModelOrganism']` or labels `['ModelOrganism']`, and sets `_ontology_mapped=true`, `_canonical_type='organism'`, `layer=COALESCE(n.layer, 'SEMANTIC')`.

#### Scenario: Model Organism entities are remediated as organism
- **WHEN** batch remediation runs and entities with type `"Model Organism"` exist
- **THEN** those entities SHALL have `_ontology_mapped=true` and `_canonical_type="organism"` set

### Requirement: Remediation flags Unknown-type entities for review
`REMEDIATION_QUERIES` SHALL include an `unknown_type_flag_review` query that matches entities with `type IN ['Unknown', 'unknown']` that are not already flagged, and sets `_needs_review=true`, `_review_reason='unknown_type'`. It SHALL NOT set `_ontology_mapped=true`.

#### Scenario: Unknown-type entity is flagged
- **WHEN** batch remediation runs and an entity has `type = 'Unknown'`
- **THEN** the entity SHALL have `_needs_review=true` and `_review_reason='unknown_type'`

#### Scenario: Unknown-type entity is not ontology-mapped
- **WHEN** batch remediation runs and an entity has `type = 'Unknown'`
- **THEN** the entity SHALL NOT have `_ontology_mapped=true` set by this query

### Requirement: Remediation classifies orphan nodes by source
`REMEDIATION_QUERIES` SHALL include an `orphan_source_classification` query that runs after `orphan_node_flagging` and sets `_orphan_source` on nodes where `_is_orphan=true`:
- `'episodic'` if the node has any label in `['EntityNode', 'EpisodicNode']`
- `'knowledge'` if the node has any label in the set of ODIN/medical type names
- `'unclassified'` otherwise

#### Scenario: Orphan with EntityNode label classified as episodic
- **WHEN** remediation runs and an orphan node has the `EntityNode` label
- **THEN** `_orphan_source` SHALL be set to `'episodic'`

#### Scenario: Orphan with Disease label classified as knowledge
- **WHEN** remediation runs and an orphan node has the `Disease` label
- **THEN** `_orphan_source` SHALL be set to `'knowledge'`

#### Scenario: Orphan with no recognized labels classified as unclassified
- **WHEN** remediation runs and an orphan node has no Graphiti or ODIN labels
- **THEN** `_orphan_source` SHALL be set to `'unclassified'`

### Requirement: Remediation includes type consistency normalization
`REMEDIATION_QUERIES` SHALL include a `type_consistency_normalization` query as the **last** query in the list. It SHALL match entities where `_ontology_mapped=true` and `_canonical_type` does not match the expected canonical form for their `type` value. It SHALL update `_canonical_type` to the correct form and set `_consistency_fixed=true`.

#### Scenario: Inconsistent canonical type is corrected
- **WHEN** remediation runs and an entity has `_ontology_mapped=true` with a mismatched `_canonical_type`
- **THEN** `_canonical_type` SHALL be updated to the correct canonical form

#### Scenario: Consistency fix is auditable
- **WHEN** a consistency correction is applied
- **THEN** the entity SHALL have `_consistency_fixed=true` set

#### Scenario: Correctly mapped entities are not modified
- **WHEN** remediation runs and an entity has `_ontology_mapped=true` with a correct `_canonical_type`
- **THEN** the entity SHALL NOT be modified by this query

### Requirement: Null-type entities are handled via label inference
The batch remediation SHALL include a query that infers entity types from Neo4j labels for entities where `n.type IS NULL`. Labels matching known ODIN types (e.g., label "Disease") SHALL be used to set the `type` and `_canonical_type` properties.

#### Scenario: Null-type entity with Disease label gets typed
- **WHEN** an entity has `type=null` but carries the Neo4j label `Disease`
- **THEN** remediation SHALL set `type="Disease"`, `_canonical_type="disease"`, and `_ontology_mapped=true`

#### Scenario: Null-type entity with no matching labels is flagged
- **WHEN** an entity has `type=null` and no labels matching known ODIN types
- **THEN** it SHALL remain unmapped but be flagged with `_needs_review=true`

### Requirement: Orphan nodes are flagged for review
The batch remediation SHALL include a query that identifies entities with zero relationships and flags them with `_is_orphan=true` without deleting them.

#### Scenario: Orphan node is flagged
- **WHEN** an entity has no incoming or outgoing relationships
- **THEN** remediation SHALL set `_is_orphan=true` on that entity

#### Scenario: Connected entity is not flagged
- **WHEN** an entity has at least one relationship
- **THEN** remediation SHALL NOT set `_is_orphan=true`
