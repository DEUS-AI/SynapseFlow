## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Orphan node listing endpoint
The API SHALL expose `GET /api/ontology/orphans` that returns entities flagged with `_is_orphan=true`, including their name, type, labels, properties, and `_orphan_source` classification.

#### Scenario: Orphans are listed after remediation
- **WHEN** a GET request is made to `/api/ontology/orphans` after remediation has flagged orphan nodes
- **THEN** the response SHALL include a list of orphan entities with their metadata

#### Scenario: Orphan listing includes source classification
- **WHEN** a GET request is made to `/api/ontology/orphans` after remediation has classified orphans
- **THEN** each orphan entity in the response SHALL include an `orphan_source` field with value `'episodic'`, `'knowledge'`, or `'unclassified'`
