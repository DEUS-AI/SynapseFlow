### Requirement: ODINMedical class includes FoodComponent constant
The `ODINMedical` class SHALL define a `FOOD_COMPONENT = "FoodComponent"` constant in the SEMANTIC layer section.

#### Scenario: FoodComponent constant exists
- **WHEN** accessing `ODINMedical.FOOD_COMPONENT`
- **THEN** it SHALL return `"FoodComponent"`

### Requirement: MEDICAL_ONTOLOGY_REGISTRY includes food_component entry
The `MEDICAL_ONTOLOGY_REGISTRY` SHALL include a `"food_component"` entry with `odin_class=ODINMedical.FOOD_COMPONENT`, `layer="SEMANTIC"`, `parent_type="biological_entity"`, `auto_relationships=["ASSOCIATED_WITH", "INTERACTS_WITH"]`, `external_systems=[MeSH, SNOMED-CT]`, `hierarchy_path=["biological_entity", "food_component"]`, and `confidence_threshold=0.85`.

#### Scenario: food_component config is retrievable
- **WHEN** `get_medical_ontology_config("food_component")` is called
- **THEN** it SHALL return a config dict with `odin_class` set to `ODINMedical.FOOD_COMPONENT` and `layer` set to `"SEMANTIC"`

#### Scenario: food_component is recognized as medical type
- **WHEN** `is_medical_type("food_component")` is called
- **THEN** it SHALL return `True`

### Requirement: MEDICAL_TYPE_ALIASES includes aliases for new and existing type variants
`MEDICAL_TYPE_ALIASES` SHALL include the following alias mappings:
- `"genus"` → `"organism"`
- `"model organism"` → `"organism"`
- `"model_organism"` → `"organism"`
- `"food component"` → `"food_component"`
- `"food_component"` → `"food_component"`
- `"food components"` → `"food_component"`
- `"nutrient"` → `"food_component"`
- `"nutrients"` → `"food_component"`
- `"dietary substance"` → `"food_component"`
- `"dietary_substance"` → `"food_component"`
- `"vitamin"` → `"food_component"`
- `"vitamins"` → `"food_component"`

#### Scenario: Genus resolves to organism
- **WHEN** `resolve_medical_type("Genus")` is called
- **THEN** it SHALL return `"organism"`

#### Scenario: Model Organism resolves to organism
- **WHEN** `resolve_medical_type("Model Organism")` is called
- **THEN** it SHALL return `"organism"`

#### Scenario: Food Component resolves to food_component
- **WHEN** `resolve_medical_type("Food Component")` is called
- **THEN** it SHALL return `"food_component"`

#### Scenario: Nutrient resolves to food_component
- **WHEN** `resolve_medical_type("nutrient")` is called
- **THEN** it SHALL return `"food_component"`

#### Scenario: Vitamin resolves to food_component
- **WHEN** `resolve_medical_type("Vitamin")` is called
- **THEN** it SHALL return `"food_component"`

### Requirement: Unknown type entities are flagged for review not mapped
Entities with `type = 'Unknown'` or `type = 'unknown'` SHALL NOT receive an ontology mapping. The remediation pipeline SHALL flag them with `_needs_review = true` and `_review_reason = 'unknown_type'`.

#### Scenario: Unknown type is not mapped
- **WHEN** `resolve_medical_type("Unknown")` is called
- **THEN** it SHALL return `"unknown"` (passthrough, no alias match)

#### Scenario: Unknown type is not in the registry
- **WHEN** `is_medical_type("Unknown")` is called
- **THEN** it SHALL return `False`

#### Scenario: Unknown type entity is flagged during remediation
- **WHEN** batch remediation runs and an entity has `type = 'Unknown'`
- **THEN** the entity SHALL have `_needs_review = true` and `_review_reason = 'unknown_type'` set, and SHALL NOT have `_ontology_mapped = true`

### Requirement: Orphan nodes are classified by source graph
After orphan detection, a classification step SHALL set `_orphan_source` on each orphan node based on its Neo4j labels:
- `'episodic'` if the node has any Graphiti-specific labels (`EntityNode`, `EpisodicNode`)
- `'knowledge'` if the node has any ODIN/medical labels (any type in `ODINMedical` or ODIN core types)
- `'unclassified'` if the node has neither

#### Scenario: Episodic orphan is classified
- **WHEN** an orphan node has the `EntityNode` label
- **THEN** remediation SHALL set `_orphan_source = 'episodic'`

#### Scenario: Knowledge orphan is classified
- **WHEN** an orphan node has the `Disease` label
- **THEN** remediation SHALL set `_orphan_source = 'knowledge'`

#### Scenario: Unclassified orphan is classified
- **WHEN** an orphan node has no Graphiti or ODIN labels
- **THEN** remediation SHALL set `_orphan_source = 'unclassified'`

#### Scenario: Classification only runs on orphan nodes
- **WHEN** remediation runs the orphan source classification step
- **THEN** it SHALL only modify nodes where `_is_orphan = true`

### Requirement: Inconsistent type mappings are normalized
A consistency normalization remediation step SHALL detect entities where `_ontology_mapped = true` but `_canonical_type` does not match the expected canonical form for their `type` value (based on `MEDICAL_TYPE_ALIASES`). The step SHALL update `_canonical_type` to the correct canonical form and set `_consistency_fixed = true`.

#### Scenario: Inconsistent mapping is corrected
- **WHEN** an entity has `type = 'Condition'`, `_ontology_mapped = true`, and `_canonical_type = 'condition'` but the alias table maps "Condition" to `"disease"`
- **THEN** remediation SHALL update `_canonical_type` to the correct form per the alias table

#### Scenario: Consistent mapping is not modified
- **WHEN** an entity has `type = 'Drug'`, `_ontology_mapped = true`, and `_canonical_type = 'drug'`
- **THEN** remediation SHALL NOT modify the entity

#### Scenario: Fixed entities are auditable
- **WHEN** a consistency fix is applied to an entity
- **THEN** the entity SHALL have `_consistency_fixed = true` set for audit tracking

### Requirement: Food component DIKW layer is SEMANTIC
`get_layer_for_medical_type("food_component")` SHALL return `"SEMANTIC"`.

#### Scenario: Food component layer lookup
- **WHEN** `get_layer_for_medical_type("food_component")` is called
- **THEN** it SHALL return `"SEMANTIC"`
