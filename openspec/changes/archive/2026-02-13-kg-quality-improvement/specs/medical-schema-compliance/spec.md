## ADDED Requirements

### Requirement: ODIN_SCHEMAS includes medical entity type definitions
The `ODIN_SCHEMAS` dict SHALL contain `OntologyClassSchema` entries for all medical entity types defined in `ODINMedical`: Symptom, Test, Observation, Measurement, Disease, Condition, Drug, Treatment, Anatomy, Pathway, Gene, Mechanism, Interaction, Guideline, Protocol, Study, Organization, Protein, Biomarker, CellType, Organism, and Virus.

#### Scenario: Medical entity passes compliance check
- **WHEN** a Disease entity has `name` and `id` properties
- **THEN** the compliance checker SHALL evaluate it against the Disease schema and report it as fully compliant

#### Scenario: Medical entity without required properties is non-compliant
- **WHEN** a Drug entity is missing the `id` property
- **THEN** the compliance checker SHALL report it as non-compliant with a violation listing the missing property

#### Scenario: All medical types have schema definitions
- **WHEN** querying `ODIN_SCHEMAS` for any type constant in `ODINMedical`
- **THEN** a matching `OntologyClassSchema` entry SHALL exist

### Requirement: Medical schemas define type-specific optional properties
Each medical schema entry SHALL include optional properties relevant to the entity type: `layer`, `confidence`, and `_canonical_type` as common optionals, plus type-specific properties (e.g., Drug includes `dosage`, `route`; Disease includes `severity`, `stage`).

#### Scenario: Optional property coverage is reported
- **WHEN** a Disease entity has `name`, `id`, `layer`, and `confidence` but not `severity`
- **THEN** the compliance checker SHALL report it as fully compliant (all required present) with partial optional coverage

### Requirement: Schema.org mappings exist for medical types
`SCHEMA_ORG_MAPPINGS` SHALL include mappings for medical entity types to their Schema.org equivalents (e.g., Disease→MedicalCondition, Drug→Drug, Symptom→MedicalSignOrSymptom, Study→MedicalStudy, Organization→Organization).

#### Scenario: Interoperability score includes medical types
- **WHEN** the interoperability assessment runs
- **THEN** medical entities with Schema.org mappings SHALL contribute positively to the `schema_org_coverage` metric

### Requirement: ODINMedical class includes Protein, Biomarker, CellType, Organism, and Virus
The `ODINMedical` class SHALL define constants for `PROTEIN`, `BIOMARKER`, `CELL_TYPE`, `ORGANISM`, and `VIRUS`. The `MEDICAL_ONTOLOGY_REGISTRY` SHALL include entries for each with appropriate layer, aliases, and external system mappings. `MEDICAL_TYPE_ALIASES` SHALL include common aliases (e.g., "cell type"→"cell_type", "virus"→"virus", "proteins"→"protein").

#### Scenario: Biomarker resolves as its own type
- **WHEN** `resolve_medical_type("Biomarker")` is called
- **THEN** it SHALL return `"biomarker"` (not `"test"`)

#### Scenario: New types have registry entries
- **WHEN** `get_medical_ontology_config("protein")` is called
- **THEN** it SHALL return a valid config dict with `odin_class`, `layer`, and `auto_relationships`

### Requirement: Batch remediation covers all entity types present in the graph
The batch remediation script SHALL include Cypher queries for Protein, Biomarker, CellType, Organism, and Virus entity types, setting `_ontology_mapped=true` and `_canonical_type` to the appropriate canonical form.

#### Scenario: Biomarker entities are remediated
- **WHEN** batch remediation runs and entities with type "Biomarker" exist
- **THEN** those entities SHALL have `_ontology_mapped=true` and `_canonical_type="biomarker"` set

#### Scenario: Previously aliased biomarkers are not double-mapped
- **WHEN** batch remediation runs and an entity already has `_ontology_mapped=true`
- **THEN** the remediation query SHALL skip that entity (via `NOT coalesce(n._ontology_mapped, false)` guard)

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
