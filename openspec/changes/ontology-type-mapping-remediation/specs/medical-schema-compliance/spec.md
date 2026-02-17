## MODIFIED Requirements

### Requirement: ODIN_SCHEMAS includes medical entity type definitions
The `ODIN_SCHEMAS` dict SHALL contain `OntologyClassSchema` entries for all medical entity types defined in `ODINMedical`: Symptom, Test, Observation, Measurement, Disease, Condition, Drug, Treatment, Anatomy, Pathway, Gene, Mechanism, Interaction, Guideline, Protocol, Study, Organization, Protein, Biomarker, CellType, Organism, Virus, and **FoodComponent**.

#### Scenario: Medical entity passes compliance check
- **WHEN** a Disease entity has `name` and `id` properties
- **THEN** the compliance checker SHALL evaluate it against the Disease schema and report it as fully compliant

#### Scenario: Medical entity without required properties is non-compliant
- **WHEN** a Drug entity is missing the `id` property
- **THEN** the compliance checker SHALL report it as non-compliant with a violation listing the missing property

#### Scenario: All medical types have schema definitions
- **WHEN** querying `ODIN_SCHEMAS` for any type constant in `ODINMedical`
- **THEN** a matching `OntologyClassSchema` entry SHALL exist

#### Scenario: FoodComponent has a schema definition
- **WHEN** querying `ODIN_SCHEMAS` for `"FoodComponent"`
- **THEN** a matching `OntologyClassSchema` entry SHALL exist with `namespace="odin:medical"`, `required_properties=["name", "id"]`, and `allowed_relationships` including `"ASSOCIATED_WITH"` and `"INTERACTS_WITH"`

### Requirement: Schema.org mappings exist for medical types
`SCHEMA_ORG_MAPPINGS` SHALL include mappings for medical entity types to their Schema.org equivalents (e.g., Disease→MedicalCondition, Drug→Drug, Symptom→MedicalSignOrSymptom, Study→MedicalStudy, Organization→Organization, **FoodComponent→Thing**).

#### Scenario: Interoperability score includes medical types
- **WHEN** the interoperability assessment runs
- **THEN** medical entities with Schema.org mappings SHALL contribute positively to the `schema_org_coverage` metric

#### Scenario: FoodComponent has a Schema.org mapping
- **WHEN** looking up `SCHEMA_ORG_MAPPINGS["FoodComponent"]`
- **THEN** it SHALL return `"Thing"`
