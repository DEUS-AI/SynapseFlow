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
- `"cytokine"` → `"protein"`
- `"cytokines"` → `"protein"`
- `"chemical"` → `"drug"`
- `"chemicals"` → `"drug"`

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

#### Scenario: Cytokine resolves to protein
- **WHEN** `resolve_medical_type("Cytokine")` is called
- **THEN** it SHALL return `"protein"`

#### Scenario: Chemical resolves to drug
- **WHEN** `resolve_medical_type("Chemical")` is called
- **THEN** it SHALL return `"drug"`

### Requirement: Unknown type entities are flagged for review not mapped
Entities with `type = 'Unknown'` or `type = 'unknown'` SHALL NOT receive an ontology mapping. The remediation pipeline SHALL flag them with `_needs_review = true` and `_review_reason = 'unknown_type'`. Additionally, the audit SHALL query the graph for ALL distinct type values not covered by any registry (DATA_ONTOLOGY_REGISTRY, MEDICAL_ONTOLOGY_REGISTRY, MEDICAL_TYPE_ALIASES) — not limited to `Unknown` — and produce a complete unmapped type inventory with entity counts per type.

#### Scenario: Unknown type is not mapped
- **WHEN** `resolve_medical_type("Unknown")` is called
- **THEN** it SHALL return `"unknown"` (passthrough, no alias match)

#### Scenario: Unknown type is not in the registry
- **WHEN** `is_medical_type("Unknown")` is called
- **THEN** it SHALL return `False`

#### Scenario: Unknown type entity is flagged during remediation
- **WHEN** batch remediation runs and an entity has `type = 'Unknown'`
- **THEN** the entity SHALL have `_needs_review = true` and `_review_reason = 'unknown_type'` set, and SHALL NOT have `_ontology_mapped = true`

#### Scenario: All unmapped types are inventoried
- **WHEN** the audit queries all distinct `type` values from the graph
- **THEN** it SHALL produce a list of every type not found in DATA_ONTOLOGY_REGISTRY, MEDICAL_ONTOLOGY_REGISTRY, or MEDICAL_TYPE_ALIASES, with the count of entities per unmapped type

#### Scenario: Registry-vs-graph drift is quantified
- **WHEN** the unmapped type inventory is complete
- **THEN** the audit SHALL report the drift ratio: (unmapped entity count) / (total entity count) as a percentage

### Requirement: Orphan nodes are classified by source graph
After orphan detection, a classification step SHALL set `_orphan_source` on each orphan node based on its Neo4j labels:
- `'episodic'` if the node has any Graphiti-specific labels (`EntityNode`, `EpisodicNode`)
- `'knowledge'` if the node has any ODIN/medical labels (any type in `ODINMedical` or ODIN core types)
- `'unclassified'` if the node has neither

Additionally, the audit SHALL produce orphan statistics broken down by source (`episodic`, `knowledge`, `unclassified`) with counts and representative examples (top 5 per source).

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

#### Scenario: Orphan statistics are produced per source
- **WHEN** orphan classification is complete
- **THEN** the audit SHALL report counts per source category and the top 5 representative orphan nodes for each

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

### Requirement: Stale alias detection
The audit SHALL compare all entries in MEDICAL_TYPE_ALIASES against actual type values present in the graph. Aliases that map types not present in the graph SHALL be flagged as potentially stale. Aliases that map to canonical types not in any registry SHALL be flagged as broken.

#### Scenario: Stale alias is detected
- **WHEN** MEDICAL_TYPE_ALIASES contains `"dietary substance" → "food_component"` but no entity with `type = "dietary substance"` exists in the graph
- **THEN** the audit SHALL flag this alias as stale (source type not found in graph)

#### Scenario: Broken alias is detected
- **WHEN** an alias maps to a canonical type that is not registered in MEDICAL_ONTOLOGY_REGISTRY
- **THEN** the audit SHALL flag this alias as broken (target type not in registry)

#### Scenario: Active alias is confirmed
- **WHEN** an alias maps a type that exists in the graph to a canonical type in the registry
- **THEN** the audit SHALL confirm it as active

### Requirement: Type normalization consistency check
The audit SHALL verify that every entity with `_ontology_mapped = true` has a `_canonical_type` that matches what the current MEDICAL_TYPE_ALIASES and registry would produce for its `type` value. Mismatches indicate drift since the last remediation.

#### Scenario: Post-remediation drift is detected
- **WHEN** an entity has `type = "Genus"`, `_canonical_type = "genus"`, but MEDICAL_TYPE_ALIASES now maps "genus" → "organism"
- **THEN** the audit SHALL flag this entity as having post-remediation drift

#### Scenario: Consistent mapping passes
- **WHEN** an entity has `type = "Drug"`, `_canonical_type = "drug"`, and the registry confirms this mapping
- **THEN** the audit SHALL NOT flag it

### Requirement: Food component DIKW layer is SEMANTIC
`get_layer_for_medical_type("food_component")` SHALL return `"SEMANTIC"`.

#### Scenario: Food component layer lookup
- **WHEN** `get_layer_for_medical_type("food_component")` is called
- **THEN** it SHALL return `"SEMANTIC"`
